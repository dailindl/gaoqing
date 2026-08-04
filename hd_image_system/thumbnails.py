"""缩略图与 jump2x 生成（REQ §8）。"""

import math
from pathlib import Path
from typing import Any

from PIL import Image

from hd_image_system.mapping import TILE_SIZE, scale_for_z, zmax_for_size
from hd_image_system.models import Jump2xItem, ThumbnailInfo

THUMB_WIDTH = 1080
THUMB_HEIGHT = 1920


def _jump2x(center_x: float, width: int, height: int) -> list[Jump2xItem]:
    """按物理中心 X 生成覆盖全部层级的 jump2x（REQ §8.4）。

    Args:
        center_x: 缩略图对应原图区域的物理中心 X。
        width: 原图宽度。
        height: 原图高度。

    Returns:
        每层一项的导航数组。
    """
    zmax = zmax_for_size(width, height)
    items: list[Jump2xItem] = []
    for z in range(zmax + 1):
        scale = scale_for_z(z, zmax)
        items.append(Jump2xItem(z=z, x=math.floor((center_x * scale) / TILE_SIZE)))
    return items


def generate_thumbnails(
    original_path: Path,
    dest_dir: Path,
    version_id: str,
    mode: str,
    source_maps: list[dict[str, Any]] | None = None,
    width: int = THUMB_WIDTH,
    root_prefix: str = "/storage",
    quality: int = 90,
) -> list[ThumbnailInfo]:
    """生成 9:16 缩略图与 jump2x（REQ §8）。

    单图模式：从右向左按 width 分段，末段不足时强制 [0, width] 允许重叠。
    多图模式：每分屏图一张，按物理中心裁取，区域必须落在该分屏图 X 区间内。
    区域高度不足 THUMB_HEIGHT 时不做特殊处理，按实际高度输出。

    Args:
        original_path: 拼接原图路径。
        dest_dir: 缩略图输出目录（{storage}/{version_id}/thumbs）。
        version_id: 作品级唯一标识。
        mode: single 或 multi。
        source_maps: 多图模式下的来源位置映射。
        width: 分段宽度。
        root_prefix: 存储根前缀（URL 用）。
        quality: JPEG 质量。

    Returns:
        缩略图导航信息列表。
    """
    with Image.open(original_path) as im:
        rgb = im.convert("RGB")
        orig_w, orig_h = rgb.size
    dest_dir.mkdir(parents=True, exist_ok=True)

    segments: list[tuple[int, int, int, float]] = []
    if mode == "multi" and source_maps:
        for sm in source_maps:
            x_start = int(sm["x_start"])
            x_end = int(sm["x_end"])
            center = (x_start + x_end - 1) / 2.0
            segments.append((int(sm["source_index"]), x_start, x_end, center))
    else:
        count = max(1, math.ceil(orig_w / width))
        for k in range(1, count + 1):
            x_end = orig_w - (k - 1) * width
            x_start = max(0, orig_w - k * width)
            if k == count and (x_end - x_start) < width:
                x_start = 0
                x_end = min(width, orig_w)
            center = (x_start + x_end - 1) / 2.0
            segments.append((k, x_start, x_end, center))

    thumbnails: list[ThumbnailInfo] = []
    for index, x_start, x_end, center in segments:
        region_w = x_end - x_start
        if mode == "multi" and source_maps:
            thumb_w = min(width, region_w)
            x0 = min(max(round(center - thumb_w / 2), x_start), x_end - thumb_w)
            if x_end - thumb_w <= x_start:
                x0 = x_start
        else:
            thumb_w = region_w
            x0 = x_start
        crop = rgb.crop((x0, 0, x0 + thumb_w, orig_h))
        if orig_h >= THUMB_HEIGHT:
            y0 = (orig_h - THUMB_HEIGHT) // 2
            thumb = crop.crop((0, y0, thumb_w, y0 + THUMB_HEIGHT))
        else:
            thumb = crop
        out_path = dest_dir / f"{index}.jpg"
        thumb.save(out_path, format="JPEG", quality=quality)
        thumbnails.append(
            ThumbnailInfo(
                url=f"{root_prefix}/{version_id}/thumbs/{index}.jpg",
                index=index,
                jump2x=_jump2x(center, orig_w, orig_h),
            )
        )
    return thumbnails
