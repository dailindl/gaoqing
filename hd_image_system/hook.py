"""书法双钩候选生成（REQ §6.2）。"""

from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from hd_image_system.models import HookCandidate

# 双钩候选策略族（REQ §6.2：每次 2–10 个）
HOOK_STRATEGIES: list[tuple[str, dict[str, int | float]]] = [
    ("external_contour", {"thickness": 1}),
    ("external_contour", {"thickness": 2}),
    ("all_contours", {"thickness": 1}),
    ("all_contours", {"thickness": 2}),
    ("canny", {"low": 50, "high": 150}),
    ("canny", {"low": 100, "high": 200}),
    ("skeleton", {"width": 1}),
    ("skeleton", {"width": 2}),
]


def _contour_hook(ink: np.ndarray, hierarchy_mode: int, thickness: int) -> np.ndarray:
    """按轮廓层级绘制双钩线。

    Args:
        ink: 笔画为前景（255）的二值图。
        hierarchy_mode: RETR_EXTERNAL 或 RETR_LIST。
        thickness: 轮廓线宽。

    Returns:
        白底黑线双钩图。
    """
    canvas = np.full_like(ink, 255)
    contours, _ = cv2.findContours(ink, hierarchy_mode, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(canvas, contours, -1, 0, thickness)
    return canvas


def _canny_hook(ink: np.ndarray, low: int, high: int) -> np.ndarray:
    """Canny 边缘 + 形态学闭合生成双钩线。

    Args:
        ink: 笔画为前景的二值图。
        low: Canny 低阈值。
        high: Canny 高阈值。

    Returns:
        白底黑线双钩图。
    """
    edges = cv2.Canny(ink, low, high)
    kernel = np.ones((3, 3), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return np.where(closed > 0, 0, 255).astype(np.uint8)


def _skeleton_hook(ink: np.ndarray, width: int) -> np.ndarray:
    """骨架化（中轴）并按宽度膨胀重建双钩线。

    Args:
        ink: 笔画为前景的二值图。
        width: 重建线宽。

    Returns:
        白底黑线双钩图。
    """
    skeleton = cv2.ximgproc.thinning(ink)
    kernel_size = width * 2 + 1
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    dilated = cv2.dilate(skeleton, kernel, iterations=1)
    return np.where(dilated > 0, 0, 255).astype(np.uint8)


def _apply_hook_strategy(
    strategy: str, params: dict[str, int | float], ink: np.ndarray
) -> np.ndarray:
    """按策略标识生成双钩图。

    Args:
        strategy: 策略标识。
        params: 策略参数。
        ink: 笔画为前景的二值图。

    Returns:
        白底黑线双钩图。

    Raises:
        ValueError: 未知策略。
    """
    if strategy == "external_contour":
        return _contour_hook(ink, cv2.RETR_EXTERNAL, int(params["thickness"]))
    if strategy == "all_contours":
        return _contour_hook(ink, cv2.RETR_LIST, int(params["thickness"]))
    if strategy == "canny":
        return _canny_hook(ink, int(params["low"]), int(params["high"]))
    if strategy == "skeleton":
        return _skeleton_hook(ink, int(params["width"]))
    raise ValueError(f"未知策略: {strategy}")


def generate_hook_candidates(bw_selected_path: Path, dest_dir: Path) -> list[HookCandidate]:
    """基于已选黑白图生成 2–10 个双钩候选（REQ §6.2；AC-07）。

    Args:
        bw_selected_path: 已选黑白图路径。
        dest_dir: 候选输出目录（{storage}/{version_id}/hook/candidates）。

    Returns:
        候选记录列表。
    """
    with Image.open(bw_selected_path) as im:
        arr = np.asarray(im.convert("L"))
        size = im.size
    ink = np.where(arr == 0, 255, 0).astype(np.uint8)
    dest_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    candidates: list[HookCandidate] = []
    for index, (strategy, params) in enumerate(HOOK_STRATEGIES, start=1):
        hook_image = _apply_hook_strategy(strategy, params, ink)
        candidate_id = f"hook_{index:02d}_{strategy}"
        out_path = dest_dir / f"{candidate_id}.png"
        Image.fromarray(hook_image, mode="L").save(out_path, format="PNG")
        candidates.append(
            HookCandidate(
                candidate_id=candidate_id,
                strategy=strategy,
                params=params,
                generated_at=generated_at,
                path=str(out_path),
                width=size[0],
                height=size[1],
            )
        )
    return candidates
