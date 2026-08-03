from pathlib import Path

import pytest
from pydantic import ValidationError

from hd_image_system.models import DownloadResult
from hd_image_system.records import ProcessingRecord, load_record, new_record, save_record


def test_new_record_defaults() -> None:
    record = new_record("v1")

    assert record.version_id == "v1"
    assert record.status == {
        "original": "not_generated",
        "bw": "not_generated",
        "hook": "not_generated",
    }
    assert record.sources == []


def test_save_load_roundtrip(tmp_path: Path) -> None:
    record = new_record("v1")
    record.sources = [
        DownloadResult(
            source_index=1,
            img_id="u1",
            source_url="http://example.com/1.jpg",
            status="ok",
            file_format="jpeg",
            width=100,
            height=50,
        )
    ]
    path = tmp_path / "processing.json"

    save_record(record, path)
    loaded = load_record(path, "v1")

    assert loaded == record


def test_invalid_status_rejected() -> None:
    with pytest.raises(ValidationError):
        ProcessingRecord(
            version_id="v1",
            status={"original": "bogus", "bw": "not_generated", "hook": "not_generated"},
            sources=[],
        )
