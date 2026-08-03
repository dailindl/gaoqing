"""黑白候选生成与质量校验（REQ §6.1）。"""

from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from doxapy import Binarization
from PIL import Image

from hd_image_system.models import BWCandidate, BwValidation

# 候选策略族（REQ §6.1：每次 2–10 个，含参数/策略标识）
CANDIDATE_STRATEGIES: list[tuple[str, dict[str, int | float]]] = [
    ("otsu", {}),
    ("adaptive_mean", {"block_size": 31, "c": 5}),
    ("adaptive_mean", {"block_size": 51, "c": 10}),
    ("adaptive_gaussian", {"block_size": 31, "c": 5}),
    ("adaptive_gaussian", {"block_size": 51, "c": 10}),
    ("sauvola", {"window": 25, "k": 0.2}),
    ("sauvola", {"window": 45, "k": 0.3}),
    ("wolf", {"window": 25, "k": 0.2}),
]


def _seal_mask(rgb: np.ndarray) -> np.ndarray:
    """检测红色印章区域掩码。

    Args:
        rgb: RGB 图像数组。

    Returns:
        布尔掩码，True 表示印章像素。
    """
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    return (r > 100) & ((r - g) > 40) & ((r - b) > 40)


def _otsu(gray: np.ndarray) -> np.ndarray:
    """Otsu 全局阈值二值化。"""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _adaptive(gray: np.ndarray, method: int, params: dict[str, int | float]) -> np.ndarray:
    """自适应阈值二值化。"""
    block_size = int(params["block_size"])
    c = int(params["c"])
    return cv2.adaptiveThreshold(gray, 255, method, cv2.THRESH_BINARY, block_size, c)


def _doxapy(gray: np.ndarray, algorithm: object, params: dict[str, int | float]) -> np.ndarray:
    """DoxaPy 局部阈值二值化（Sauvola/Wolf）。"""
    binarizer = Binarization(algorithm)
    binarizer.initialize(gray)
    out = np.zeros_like(gray)
    binarizer.to_binary(out, {"window": int(params["window"]), "k": float(params["k"])})
    return out


def _apply_strategy(strategy: str, params: dict[str, int | float], gray: np.ndarray) -> np.ndarray:
    """按策略标识执行二值化。

    Args:
        strategy: 策略标识。
        params: 策略参数。
        gray: 灰度图。

    Returns:
        二值图（0/255 uint8）。

    Raises:
        ValueError: 未知策略。
    """
    if strategy == "otsu":
        return _otsu(gray)
    if strategy == "adaptive_mean":
        return _adaptive(gray, cv2.ADAPTIVE_THRESH_MEAN_C, params)
    if strategy == "adaptive_gaussian":
        return _adaptive(gray, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, params)
    if strategy == "sauvola":
        return _doxapy(gray, Binarization.Algorithms.SAUVOLA, params)
    if strategy == "wolf":
        return _doxapy(gray, Binarization.Algorithms.WOLF, params)
    raise ValueError(f"未知策略: {strategy}")


def _normalize_polarity(binary: np.ndarray, seal: np.ndarray, dark_source: bool) -> np.ndarray:
    """统一为白底黑字，并将印章归入黑色前景（REQ §6.1）。

    Args:
        binary: 二值图。
        seal: 印章掩码。
        dark_source: 原图是否为黑底白字（灰度均值 < 128）。

    Returns:
        白底黑字二值图（背景 255、笔画/印章 0）。
    """
    out = binary.copy()
    black_ratio = float(np.count_nonzero(out == 0)) / out.size
    if dark_source or black_ratio > 0.5:
        out = np.where(out == 0, 255, 0).astype(np.uint8)
    out[seal] = 0
    return out


def generate_bw_candidates(original_path: Path, dest_dir: Path) -> list[BWCandidate]:
    """基于原图生成 2–10 个黑白候选（REQ §6.1；AC-05）。

    Args:
        original_path: 拼接原图路径。
        dest_dir: 候选输出目录（{storage}/{version_id}/bw/candidates）。

    Returns:
        候选记录列表（含标识、策略、参数、时间、路径）。
    """
    with Image.open(original_path) as im:
        rgb = np.asarray(im.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    seal = _seal_mask(rgb)
    dark_source = bool(gray.mean() < 128)
    dest_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    candidates: list[BWCandidate] = []
    for index, (strategy, params) in enumerate(CANDIDATE_STRATEGIES, start=1):
        binary = _apply_strategy(strategy, params, gray)
        binary = _normalize_polarity(binary, seal, dark_source)
        candidate_id = f"cand_{index:02d}_{strategy}"
        out_path = dest_dir / f"{candidate_id}.png"
        Image.fromarray(binary, mode="L").save(out_path, format="PNG")
        candidates.append(
            BWCandidate(
                candidate_id=candidate_id,
                strategy=strategy,
                params=params,
                generated_at=generated_at,
                path=str(out_path),
            )
        )
    return candidates


def validate_bw_master(path: Path, expected_size: tuple[int, int]) -> BwValidation:
    """校验已选黑白图 master 的强制质量边界（REQ §6.1；AC-06）。

    Args:
        path: 已选黑白图 PNG 路径。
        expected_size: 期望画布尺寸 (宽, 高)。

    Returns:
        校验结果与错误列表。
    """
    errors: list[str] = []
    with Image.open(path) as im:
        if im.size != expected_size:
            errors.append(f"尺寸不一致: {im.size} != {expected_size}")
        arr = np.asarray(im.convert("L"))
    values = set(np.unique(arr).tolist())
    if not values.issubset({0, 255}):
        errors.append(f"非二值图: {sorted(values)}")
    if arr.size:
        white_ratio = float(np.count_nonzero(arr == 255)) / arr.size
        black_ratio = float(np.count_nonzero(arr == 0)) / arr.size
        if white_ratio < 0.5:
            errors.append("背景非白底")
        if black_ratio <= 0.0:
            errors.append("缺少黑色前景")
    return BwValidation(valid=not errors, errors=errors)
