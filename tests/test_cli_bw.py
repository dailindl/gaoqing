from pathlib import Path

from PIL import Image

from hd_image_system.cli import main
from hd_image_system.records import load_record, new_record, save_record


def _make_doc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (100, 80), (255, 255, 255))
    px = img.load()
    for y in range(10, 40):
        for x in range(10, 50):
            px[x, y] = (0, 0, 0)
    img.save(path, format="PNG")


def test_cli_bw_ok(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    original = storage / "v1" / "original.jpg"
    _make_doc(original)
    record = new_record("v1")
    record.original = {"width": 100, "height": 80, "path": str(original), "source_maps": []}
    record.status["original"] = "selected"
    save_record(record, storage / "v1" / "records" / "processing.json")

    rc = main(["bw", "--version-id", "v1", "--storage-root", str(storage)])

    assert rc == 0
    loaded = load_record(storage / "v1" / "records" / "processing.json", "v1")
    assert loaded.status["bw"] == "pending_selection"
    assert loaded.bw is not None
    candidates = loaded.bw["candidates"]
    assert 2 <= len(candidates) <= 10
    assert (storage / "v1" / "bw" / "candidates").is_dir()
