"""三版本统一金字塔瓦片生成（REQ §7）。"""

import math
from pathlib import Path

import pyvips

from hd_image_system.mapping import TILE_SIZE, level_size, zmax_for_size


def generate_tiles(image_path: Path, out_dir: Path, quality: int = 90) -> dict[str, int]:
    """生成 z/x_y.jpg 金字塔瓦片（z=0 最小层 → z=Zmax 原始分辨率）。

    Args:
        image_path: 版本 master 图片路径。
        out_dir: 瓦片输出目录（{storage}/{version_id}/tiles/{kind}）。
        quality: JPEG 质量（1–100）。

    Returns:
        {"width": W, "height": H, "zmax": Zmax}。
    """
    img = pyvips.Image.new_from_file(str(image_path))
    width, height = img.width, img.height
    zmax = zmax_for_size(width, height)
    out_dir.mkdir(parents=True, exist_ok=True)
    for z in range(zmax + 1):
        level_w, level_h = level_size(width, height, z, zmax)
        if z == zmax:
            level = img
        else:
            level = img.resize(level_w / width, kernel="lanczos3")
            if level.width != level_w or level.height != level_h:
                level = level.crop(0, 0, min(level.width, level_w), min(level.height, level_h))
                if level.width != level_w or level.height != level_h:
                    level = level.resize(level_w / level.width, kernel="lanczos3")
        tiles_x = math.ceil(level_w / TILE_SIZE)
        tiles_y = math.ceil(level_h / TILE_SIZE)
        zdir = out_dir / str(z)
        zdir.mkdir(parents=True, exist_ok=True)
        for tx in range(tiles_x):
            for ty in range(tiles_y):
                tile = level.crop(
                    tx * TILE_SIZE,
                    ty * TILE_SIZE,
                    min(TILE_SIZE, level_w - tx * TILE_SIZE),
                    min(TILE_SIZE, level_h - ty * TILE_SIZE),
                )
                tile.jpegsave(str(zdir / f"{tx}_{ty}.jpg"), Q=quality)
    return {"width": width, "height": height, "zmax": zmax}
