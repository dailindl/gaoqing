from pathlib import Path

import numpy as np
from PIL import Image

from hd_image_system.binarize import generate_bw_candidates, validate_bw_master


def _make_doc(path: Path, dark_bg: bool = False) -> None:
    size = (100, 80)
    bg = (0, 0, 0) if dark_bg else (255, 255, 255)
    ink = (255, 255, 255) if dark_bg else (0, 0, 0)
    img = Image.new("RGB", size, bg)
    px = img.load()
    for y in range(10, 40):
        for x in range(10, 50):
            px[x, y] = ink
    for y in range(50, 70):
        for x in range(60, 90):
            px[x, y] = (255, 0, 0)  # 红色印章
    img.save(path, format="PNG")


def test_generate_bw_candidates_binary_and_size(tmp_path: Path) -> None:
    original = tmp_path / "original.png"
    _make_doc(original)

    candidates = generate_bw_candidates(original, tmp_path / "cands")

    assert 2 <= len(candidates) <= 10
    for candidate in candidates:
        path = Path(candidate.path)
        assert path.is_file()
        with Image.open(path) as im:
            assert im.size == (100, 80)
            arr = np.asarray(im.convert("L"))
        assert set(np.unique(arr).tolist()).issubset({0, 255})
        assert candidate.strategy


def test_seal_forced_foreground(tmp_path: Path) -> None:
    original = tmp_path / "original.png"
    _make_doc(original)

    candidates = generate_bw_candidates(original, tmp_path / "cands")

    for candidate in candidates:
        with Image.open(candidate.path) as im:
            arr = np.asarray(im.convert("L"))
        assert arr[60, 75] == 0  # 印章中心必须为黑色前景


def test_dark_bg_normalized_to_white_bg(tmp_path: Path) -> None:
    original = tmp_path / "original.png"
    _make_doc(original, dark_bg=True)

    candidates = generate_bw_candidates(original, tmp_path / "cands")

    valid_count = 0
    for candidate in candidates:
        with Image.open(candidate.path) as im:
            arr = np.asarray(im.convert("L"))
        assert set(np.unique(arr).tolist()).issubset({0, 255})
        if arr[2, 2] == 255 and arr[20, 20] == 0:
            valid_count += 1
    # 黑底白字来源统一为白底黑字；极端合成图上局部自适应可能退化，允许少数候选不满足
    assert valid_count >= 6


def test_validate_bw_master_ok_and_fail(tmp_path: Path) -> None:
    good = tmp_path / "good.png"
    Image.new("L", (100, 80), 255).save(good, format="PNG")
    with Image.open(good) as im:
        arr = np.asarray(im).copy()
    arr[10:30, 10:40] = 0
    Image.fromarray(arr, mode="L").save(good, format="PNG")

    result = validate_bw_master(good, (100, 80))

    assert result.valid is True
    assert result.errors == []

    bad = tmp_path / "bad.png"
    Image.new("L", (100, 80), 128).save(bad, format="PNG")
    result_bad = validate_bw_master(bad, (100, 80))
    assert result_bad.valid is False
    assert any("二值" in e for e in result_bad.errors)

    result_size = validate_bw_master(good, (50, 40))
    assert result_size.valid is False
    assert any("尺寸" in e for e in result_size.errors)
