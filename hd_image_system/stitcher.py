"""原图拼接与高度统一（REQ §4.3、§5.1）。"""

from dataclasses import dataclass
from pathlib import Path

import pyvips
from PIL import Image

from hd_image_system.models import DownloadResult


@dataclass(frozen=True)
class UnifiedImage:
    """统一高度后的分屏图信息。

    Attributes:
        source_index: 来源图 1 起始位置。
        img_id: 来源图唯一标识。
        original_path: 原始归档文件路径。
        unified_path: 统一后文件路径（未缩放时复用原文件）。
        original_size: 原始尺寸 (宽, 高)。
        unified_size: 统一后尺寸 (宽, 高)。
        scaled: 是否经过等比缩放。
    """

    source_index: int
    img_id: str
    original_path: Path
    unified_path: Path
    original_size: tuple[int, int]
    unified_size: tuple[int, int]
    scaled: bool


@dataclass(frozen=True)
class Placement:
    """来源图在拼接画布中的放置信息。

    Attributes:
        source_index: 来源图 1 起始位置。
        x_start: 物理 X 区间起点（含）。
        x_end: 物理 X 区间终点（不含）。
    """

    source_index: int
    x_start: int
    x_end: int


def unify_heights(sources: list[DownloadResult], dest_dir: Path) -> list[UnifiedImage]:
    """将多图模式各分屏图统一到最小公共高度（等比缩放，REQ §4.3）。

    高度等于最小高度的图不缩放，直接复用归档文件。

    Args:
        sources: 下载成功的结果记录（按 img_num 升序）。
        dest_dir: 统一图输出目录。

    Returns:
        统一高度后的分屏图列表。

    Raises:
        ValueError: 没有可用来源图。
    """
    ok: list[DownloadResult] = []
    for s in sources:
        if s.status == "ok" and s.local_path and s.width is not None and s.height is not None:
            ok.append(s)
    if not ok:
        raise ValueError("没有可用的来源图")
    min_h = min(s.height for s in ok if s.height is not None)
    dest_dir.mkdir(parents=True, exist_ok=True)
    unified: list[UnifiedImage] = []
    for s in ok:
        local_path = s.local_path
        width = s.width
        height = s.height
        if local_path is None or width is None or height is None:
            continue
        original = Path(local_path)
        original_size = (width, height)
        if height == min_h:
            unified.append(
                UnifiedImage(
                    source_index=s.source_index,
                    img_id=s.img_id,
                    original_path=original,
                    unified_path=original,
                    original_size=original_size,
                    unified_size=original_size,
                    scaled=False,
                )
            )
            continue
        with Image.open(original) as img:
            new_w = max(1, round(width * min_h / height))
            resized = img.resize((new_w, min_h), Image.Resampling.LANCZOS)
            out = dest_dir / f"{s.source_index}.png"
            resized.save(out, format="PNG")
        unified.append(
            UnifiedImage(
                source_index=s.source_index,
                img_id=s.img_id,
                original_path=original,
                unified_path=out,
                original_size=original_size,
                unified_size=(new_w, min_h),
                scaled=True,
            )
        )
    return unified


def compute_placements(images: list[UnifiedImage]) -> list[Placement]:
    """计算各分屏图在拼接画布中的物理 X 区间。

    拼接方向从右向左：第 1 个分屏图（img_num=1）位于最右侧（REQ §5.1）。

    Args:
        images: 按 img_num 升序的统一图列表。

    Returns:
        与 images 顺序一致的放置信息。
    """
    widths = [img.unified_size[0] for img in images]
    total = sum(widths)
    placements: list[Placement] = []
    cursor = total
    for img, w in zip(images, widths, strict=True):
        cursor -= w
        placements.append(
            Placement(source_index=img.source_index, x_start=cursor, x_end=cursor + w)
        )
    return placements


def stitch(images: list[UnifiedImage], dest_path: Path, quality: int = 95) -> tuple[int, int]:
    """按 img_num 升序从右向左拼接分屏图为原图（REQ §5.1）。

    使用 libvips 流式拼接，避免全分辨率画布常驻内存。

    Args:
        images: 统一高度后的分屏图列表（按 img_num 升序）。
        dest_path: 原图输出路径（.jpg）。
        quality: JPEG 质量（1–100）。

    Returns:
        拼接画布 (宽, 高)。

    Raises:
        ValueError: 无可用图片。
    """
    if not images:
        raise ValueError("没有可拼接的图片")
    total_width = sum(img.unified_size[0] for img in images)
    height = images[0].unified_size[1]
    vips_images = [pyvips.Image.new_from_file(str(img.unified_path)) for img in images]
    joined = pyvips.Image.black(total_width, height, bands=3)
    cursor = total_width
    for vimg, width in zip(vips_images, (img.unified_size[0] for img in images), strict=True):
        cursor -= width
        joined = joined.insert(vimg, cursor, 0)
    if joined.bands > 3:
        joined = joined.flatten(background=[255, 255, 255])
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    joined.jpegsave(str(dest_path), Q=quality)
    return total_width, height
