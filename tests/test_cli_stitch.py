from pathlib import Path

from PIL import Image

from hd_image_system.cli import main
from hd_image_system.models import DownloadResult
from hd_image_system.records import load_record, new_record, save_record


def _make_png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")


def test_cli_stitch_ok(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    source_dir = storage / "v1" / "source"
    _make_png(source_dir / "1.png", (200, 100), (255, 0, 0))
    _make_png(source_dir / "2.png", (120, 60), (0, 0, 255))
    record = new_record("v1")
    record.sources = [
        DownloadResult(
            source_index=1,
            img_id="u1",
            source_url="http://x",
            status="ok",
            local_path=str(source_dir / "1.png"),
            file_format="png",
            width=200,
            height=100,
        ),
        DownloadResult(
            source_index=2,
            img_id="u2",
            source_url="http://x",
            status="ok",
            local_path=str(source_dir / "2.png"),
            file_format="png",
            width=120,
            height=60,
        ),
    ]
    save_record(record, storage / "v1" / "records" / "processing.json")

    rc = main(["stitch", "--version-id", "v1", "--storage-root", str(storage), "--quality", "90"])

    assert rc == 0
    assert (storage / "v1" / "original.jpg").is_file()
    loaded = load_record(storage / "v1" / "records" / "processing.json", "v1")
    assert loaded.status["original"] == "selected"
    assert loaded.original is not None
    assert loaded.original["width"] == 240
    assert loaded.sources[0].x_range == (120, 240)
    assert loaded.sources[1].x_range == (0, 120)
    assert loaded.sources[0].scaled is True
    assert len(loaded.original["source_maps"]) == 2
