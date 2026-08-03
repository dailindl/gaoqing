from pathlib import Path

import numpy as np
from PIL import Image

from hd_image_system.cli import main
from hd_image_system.records import load_record, new_record, save_record


def _make_bw(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("L", (100, 80), 255)
    arr = np.asarray(img).copy()
    arr[10:50, 20:60] = 0
    Image.fromarray(arr, mode="L").save(path, format="PNG")


def test_cli_hook_ok(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    bw_selected = storage / "v1" / "bw" / "selected.png"
    _make_bw(bw_selected)
    record = new_record("v1")
    record.bw = {
        "candidates": [],
        "selected": {"candidate_id": "cand_01_otsu", "operator": "tester", "time": "2026-08-03"},
    }
    record.status["bw"] = "selected"
    save_record(record, storage / "v1" / "records" / "processing.json")

    rc = main(["hook", "--version-id", "v1", "--storage-root", str(storage)])

    assert rc == 0
    loaded = load_record(storage / "v1" / "records" / "processing.json", "v1")
    assert loaded.status["hook"] == "pending_selection"
    assert loaded.hook is not None
    candidates = loaded.hook["candidates"]
    assert 2 <= len(candidates) <= 10
    assert (storage / "v1" / "hook" / "candidates").is_dir()
