from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from hd_image_system.cli import build_parser
from hd_image_system.records import load_record, new_record, save_record
from hd_image_system.review.api import create_app


def _make_png(path: Path, size: tuple[int, int] = (100, 80)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", size, 255).save(path, format="PNG")


def _setup_storage(tmp_path: Path) -> Path:
    storage = tmp_path / "storage"
    original = storage / "v1" / "original.jpg"
    _make_png(original)
    cand_dir = storage / "v1" / "bw" / "candidates"
    cand_a = cand_dir / "cand_01_otsu.png"
    cand_b = cand_dir / "cand_02_adaptive_mean.png"
    _make_png(cand_a)
    _make_png(cand_b)
    record = new_record("v1")
    record.original = {"width": 100, "height": 80, "path": str(original), "source_maps": []}
    record.status["original"] = "selected"
    record.bw = {
        "candidates": [
            {
                "candidate_id": "cand_01_otsu",
                "strategy": "otsu",
                "params": {},
                "generated_at": "2026-08-04T00:00:00+00:00",
                "path": str(cand_a),
            },
            {
                "candidate_id": "cand_02_adaptive_mean",
                "strategy": "adaptive_mean",
                "params": {"block_size": 31, "c": 5},
                "generated_at": "2026-08-04T00:00:00+00:00",
                "path": str(cand_b),
            },
        ],
        "selected": None,
    }
    record.status["bw"] = "pending_selection"
    save_record(record, storage / "v1" / "records" / "processing.json")
    return storage


def test_index_served(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    client = TestClient(create_app(storage))

    resp = client.get("/")

    assert resp.status_code == 200
    assert "openseadragon" in resp.text.lower()
    assert "确认选择" in resp.text


def test_list_candidates(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    client = TestClient(create_app(storage))

    resp = client.get("/api/versions/v1/candidates/bw")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 2
    assert data["candidates"][0]["candidate_id"] == "cand_01_otsu"


def test_original_served(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    client = TestClient(create_app(storage))

    resp = client.get("/api/versions/v1/original")

    assert resp.status_code == 200


def test_candidate_file_served(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    client = TestClient(create_app(storage))

    resp = client.get("/api/versions/v1/candidates/bw/cand_01_otsu.png")

    assert resp.status_code == 200


def test_select_ok(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    client = TestClient(create_app(storage))

    resp = client.post(
        "/api/versions/v1/select",
        json={"kind": "bw", "candidate_id": "cand_01_otsu", "operator": "tester"},
    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    selected_png = storage / "v1" / "bw" / "selected.png"
    assert selected_png.is_file()
    record = load_record(storage / "v1" / "records" / "processing.json", "v1")
    assert record.status["bw"] == "selected"
    assert record.bw is not None
    assert record.bw["selected"]["operator"] == "tester"
    assert record.bw["selected"]["path"] == str(selected_png)


def test_select_unknown_candidate(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    client = TestClient(create_app(storage))

    resp = client.post(
        "/api/versions/v1/select",
        json={"kind": "bw", "candidate_id": "nope", "operator": "tester"},
    )

    assert resp.status_code == 404


def test_parser_supports_review() -> None:
    args = build_parser().parse_args(["review", "--storage-root", "storage", "--port", "9000"])

    assert args.command == "review"
    assert args.port == 9000
