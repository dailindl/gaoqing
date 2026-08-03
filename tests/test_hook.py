from pathlib import Path

import numpy as np
from PIL import Image

from hd_image_system.hook import generate_hook_candidates


def _make_bw(path: Path) -> None:
    """生成白底黑字的实心矩形黑白图（模拟已选黑白图）。"""
    img = Image.new("L", (100, 80), 255)
    arr = np.asarray(img).copy()
    arr[10:50, 20:60] = 0
    Image.fromarray(arr, mode="L").save(path, format="PNG")


def test_generate_hook_candidates_binary_and_size(tmp_path: Path) -> None:
    bw = tmp_path / "selected.png"
    _make_bw(bw)

    candidates = generate_hook_candidates(bw, tmp_path / "hooks")

    assert 2 <= len(candidates) <= 10
    for candidate in candidates:
        assert candidate.width == 100
        assert candidate.height == 80
        path = Path(candidate.path)
        assert path.is_file()
        with Image.open(path) as im:
            assert im.size == (100, 80)
            arr = np.asarray(im.convert("L"))
        assert set(np.unique(arr).tolist()).issubset({0, 255})
        assert arr[2, 2] == 255  # 白底
        assert candidate.strategy


def test_hook_line_positions(tmp_path: Path) -> None:
    bw = tmp_path / "selected.png"
    _make_bw(bw)

    candidates = generate_hook_candidates(bw, tmp_path / "hooks")

    for candidate in candidates:
        with Image.open(candidate.path) as im:
            arr = np.asarray(im.convert("L"))
        if candidate.strategy in ("external_contour", "all_contours", "canny"):
            assert arr[10, 20] == 0  # 矩形边缘为黑线
            assert arr[30, 40] == 255  # 内部中空
        else:
            assert arr[30, 40] == 0  # 骨架中轴为黑线
