"""瓦片金字塔层级与来源位置映射（REQ §5.2、§7.1、§8.4）。"""

import math

from hd_image_system.models import LayerMap, SourceMap
from hd_image_system.stitcher import Placement

TILE_SIZE = 256


def zmax_for_size(width: int, height: int, tile_size: int = TILE_SIZE) -> int:
    """计算金字塔最大层（原始分辨率层）。

    Args:
        width: 画布宽度。
        height: 画布高度。
        tile_size: 瓦片边长。

    Returns:
        Zmax；Zmax 层保留原始像素分辨率。
    """
    max_dim = max(width, height)
    if max_dim <= tile_size:
        return 0
    return math.ceil(math.log2(max_dim / tile_size))


def scale_for_z(z: int, zmax: int) -> float:
    """计算层级缩放系数 scale_z = 2^(z - Zmax)。

    Args:
        z: 层级。
        zmax: 最大层。

    Returns:
        缩放系数。
    """
    return 2.0 ** (z - zmax)


def tile_x_range(
    x_start: int, x_end: int, z: int, zmax: int, tile_size: int = TILE_SIZE
) -> tuple[int, int]:
    """返回物理 X 区间 [x_start, x_end) 在指定层覆盖的 tile-X 闭区间。

    Args:
        x_start: 区间起点（含）。
        x_end: 区间终点（不含）。
        z: 层级。
        zmax: 最大层。
        tile_size: 瓦片边长。

    Returns:
        (tile_x_start, tile_x_end)，均为含端点。
    """
    scale = scale_for_z(z, zmax)
    start = math.floor((x_start * scale) / tile_size)
    end = math.floor(((x_end - 1) * scale) / tile_size)
    return start, end


def tile_x_for_center(
    x_start: int, x_end: int, z: int, zmax: int, tile_size: int = TILE_SIZE
) -> int:
    """将物理区间中心 X 换算为指定层 tile-X 索引（REQ §8.4）。

    Args:
        x_start: 区间起点（含）。
        x_end: 区间终点（不含）。
        z: 层级。
        zmax: 最大层。
        tile_size: 瓦片边长。

    Returns:
        tile-X 索引。
    """
    center = (x_start + x_end - 1) / 2.0
    scale = scale_for_z(z, zmax)
    return math.floor((center * scale) / tile_size)


def build_source_maps(
    placements: list[Placement], width: int, height: int, tile_size: int = TILE_SIZE
) -> list[SourceMap]:
    """构建全部来源图的位置映射（REQ §5.2）。

    Args:
        placements: 按 img_num 升序的放置信息。
        width: 拼接画布宽度。
        height: 拼接画布高度。
        tile_size: 瓦片边长。

    Returns:
        按 source_index 升序的位置映射列表。
    """
    zmax = zmax_for_size(width, height, tile_size)
    maps: list[SourceMap] = []
    for placement in placements:
        center = (placement.x_start + placement.x_end - 1) / 2.0
        layers = []
        for z in range(zmax + 1):
            t_start, t_end = tile_x_range(placement.x_start, placement.x_end, z, zmax, tile_size)
            layers.append(
                LayerMap(
                    z=z,
                    tile_x_start=t_start,
                    tile_x_end=t_end,
                    tile_x_center=tile_x_for_center(
                        placement.x_start, placement.x_end, z, zmax, tile_size
                    ),
                )
            )
        maps.append(
            SourceMap(
                source_index=placement.source_index,
                x_start=placement.x_start,
                x_end=placement.x_end,
                center_x=center,
                layers=layers,
            )
        )
    return maps
