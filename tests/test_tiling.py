from pathlib import Path

from PIL import Image

from hd_image_system.tiling import generate_tiles


def test_generate_tiles_grid(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    Image.new("RGB", (512, 256), (255, 255, 255)).save(src, format="PNG")

    info = generate_tiles(src, tmp_path / "tiles", quality=90)

    assert info == {"width": 512, "height": 256, "zmax": 1}
    tiles1 = tmp_path / "tiles" / "1"
    assert (tiles1 / "0_0.jpg").is_file()
    assert (tiles1 / "1_0.jpg").is_file()
    tiles0 = tmp_path / "tiles" / "0"
    assert (tiles0 / "0_0.jpg").is_file()
    with Image.open(tiles1 / "0_0.jpg") as im:
        assert im.size == (256, 256)
    with Image.open(tiles0 / "0_0.jpg") as im:
        assert im.size == (256, 128)
