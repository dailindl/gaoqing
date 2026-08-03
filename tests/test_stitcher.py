from pathlib import Path

from PIL import Image

from hd_image_system.models import DownloadResult
from hd_image_system.stitcher import UnifiedImage, compute_placements, stitch, unify_heights


def _make_png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    Image.new("RGB", size, color).save(path, format="PNG")


def _source(index: int, path: Path, size: tuple[int, int]) -> DownloadResult:
    return DownloadResult(
        source_index=index,
        img_id=f"u{index}",
        source_url="http://example.com/x.jpg",
        status="ok",
        local_path=str(path),
        file_format="png",
        width=size[0],
        height=size[1],
    )


def test_unify_heights_scales_to_min(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    _make_png(a, (200, 100), (255, 0, 0))
    _make_png(b, (160, 80), (0, 255, 0))
    _make_png(c, (120, 60), (0, 0, 255))

    unified = unify_heights(
        [_source(1, a, (200, 100)), _source(2, b, (160, 80)), _source(3, c, (120, 60))],
        tmp_path / "out",
    )

    assert [u.unified_size[1] for u in unified] == [60, 60, 60]
    assert [u.scaled for u in unified] == [True, True, False]
    assert unified[0].unified_size[0] == 120
    assert unified[2].unified_path == c


def test_compute_placements_right_to_left() -> None:
    images = [
        UnifiedImage(1, "u1", Path("a"), Path("a"), (200, 60), (200, 60), False),
        UnifiedImage(2, "u2", Path("b"), Path("b"), (160, 60), (160, 60), False),
        UnifiedImage(3, "u3", Path("c"), Path("c"), (120, 60), (120, 60), False),
    ]

    placements = compute_placements(images)

    assert [(p.source_index, p.x_start, p.x_end) for p in placements] == [
        (1, 280, 480),
        (2, 120, 280),
        (3, 0, 120),
    ]


def _assert_color_close(
    pixel: tuple[int, int, int], expected: tuple[int, int, int], tol: int = 12
) -> None:
    assert all(abs(a - b) <= tol for a, b in zip(pixel, expected, strict=True))


def test_stitch_right_to_left(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    _make_png(a, (200, 60), (255, 0, 0))
    _make_png(b, (160, 60), (0, 255, 0))
    _make_png(c, (120, 60), (0, 0, 255))
    images = [
        UnifiedImage(1, "u1", a, a, (200, 60), (200, 60), False),
        UnifiedImage(2, "u2", b, b, (160, 60), (160, 60), False),
        UnifiedImage(3, "u3", c, c, (120, 60), (120, 60), False),
    ]

    width, height = stitch(images, tmp_path / "original.jpg", quality=90)

    assert (width, height) == (480, 60)
    out = Image.open(tmp_path / "original.jpg").convert("RGB")
    assert out.size == (480, 60)
    _assert_color_close(out.getpixel((420, 30)), (255, 0, 0))  # 最右侧：第 1 张
    _assert_color_close(out.getpixel((200, 30)), (0, 255, 0))  # 中间：第 2 张
    _assert_color_close(out.getpixel((60, 30)), (0, 0, 255))  # 最左侧：第 3 张
