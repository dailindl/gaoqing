from pathlib import Path

from PIL import Image

from hd_image_system.thumbnails import generate_thumbnails


def _make_image(path: Path, size: tuple[int, int]) -> None:
    Image.new("RGB", size, (255, 255, 255)).save(path, format="PNG")


def test_single_mode_thumbnails(tmp_path: Path) -> None:
    src = tmp_path / "orig.png"
    _make_image(src, (3000, 2000))

    thumbs = generate_thumbnails(src, tmp_path / "thumbs", "v1", "single", [])

    assert [t.index for t in thumbs] == [1, 2, 3]
    for thumb in thumbs:
        assert (tmp_path / "thumbs" / f"{thumb.index}.jpg").is_file()
        with Image.open(tmp_path / "thumbs" / f"{thumb.index}.jpg") as im:
            assert im.size == (1080, 1920)
        assert len(thumb.jump2x) == 5  # Zmax=4
        assert [item.z for item in thumb.jump2x] == [0, 1, 2, 3, 4]


def test_single_mode_short_height_no_special(tmp_path: Path) -> None:
    src = tmp_path / "orig.png"
    _make_image(src, (3000, 1000))

    generate_thumbnails(src, tmp_path / "thumbs", "v1", "single", [])

    with Image.open(tmp_path / "thumbs" / "1.jpg") as im:
        assert im.size == (1080, 1000)


def test_multi_mode_thumbnails(tmp_path: Path) -> None:
    src = tmp_path / "orig.png"
    _make_image(src, (3000, 2000))
    source_maps = [
        {"source_index": 1, "x_start": 1920, "x_end": 3000},
        {"source_index": 2, "x_start": 840, "x_end": 1920},
        {"source_index": 3, "x_start": 0, "x_end": 840},
    ]

    thumbs = generate_thumbnails(src, tmp_path / "thumbs", "v1", "multi", source_maps)

    assert [t.index for t in thumbs] == [1, 2, 3]
    for thumb in thumbs:
        with Image.open(tmp_path / "thumbs" / f"{thumb.index}.jpg") as im:
            expected_width = 1080 if thumb.index in (1, 2) else 840
            assert im.size == (expected_width, 1920)
        assert len(thumb.jump2x) == 5
    # 第 1 个分屏图（最右侧）index 为 1
    assert thumbs[0].index == 1
    assert thumbs[0].jump2x[-1].x == 9  # 中心 2459.5 -> z4 tile 9
