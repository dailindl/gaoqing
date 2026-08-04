import json
from pathlib import Path

from PIL import Image

from hd_image_system.cli import main
from hd_image_system.records import load_record, new_record, save_record


def _make_rgb(path: Path, size: tuple[int, int] = (512, 256)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (255, 255, 255)).save(path, format="PNG")


def test_manifest_end_to_end(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    original = storage / "v1" / "original.jpg"
    _make_rgb(original)
    record = new_record("v1")
    record.original = {"width": 512, "height": 256, "path": str(original), "source_maps": []}
    record.status["original"] = "selected"
    save_record(record, storage / "v1" / "records" / "processing.json")

    rc = main(["manifest", "--version-id", "v1", "--storage-root", str(storage)])

    assert rc == 0
    assert (storage / "v1" / "manifest.json").is_file()
    assert (storage / "v1" / "tiles" / "original" / "1" / "0_0.jpg").is_file()
    assert (storage / "v1" / "tiles" / "original" / "1" / "1_0.jpg").is_file()
    assert (storage / "v1" / "thumbs" / "1.jpg").is_file()
    loaded = load_record(storage / "v1" / "records" / "processing.json", "v1")
    assert loaded.status["original"] == "published"
    manifest = json.loads((storage / "v1" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version_id"] == "v1"
    assert manifest["url_template"] != ""
    assert manifest["url_template_bw"] == ""
    assert all(len(t["jump2x"]) == manifest["max_z"] + 1 for t in manifest["thumbnails"])


def test_tile_bw_then_manifest_url(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    original = storage / "v1" / "original.jpg"
    bw_selected = storage / "v1" / "bw" / "selected.png"
    _make_rgb(original)
    _make_rgb(bw_selected)
    record = new_record("v1")
    record.original = {"width": 512, "height": 256, "path": str(original), "source_maps": []}
    record.status["original"] = "selected"
    record.status["bw"] = "selected"
    save_record(record, storage / "v1" / "records" / "processing.json")

    assert (
        main(["tile", "--version-id", "v1", "--storage-root", str(storage), "--kind", "original"])
        == 0
    )
    assert main(["tile", "--version-id", "v1", "--storage-root", str(storage), "--kind", "bw"]) == 0
    assert main(["manifest", "--version-id", "v1", "--storage-root", str(storage)]) == 0

    manifest = json.loads((storage / "v1" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["url_template_bw"] != ""
    assert (storage / "v1" / "tiles" / "bw" / "1" / "0_0.jpg").is_file()
