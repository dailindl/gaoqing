from pathlib import Path

from hd_image_system.manifest import build_manifest, validate_manifest
from hd_image_system.models import Jump2xItem, ThumbnailInfo
from hd_image_system.records import ProcessingRecord, new_record


def _thumbnails(zmax: int = 4) -> list[ThumbnailInfo]:
    return [
        ThumbnailInfo(
            url=f"/storage/v1/thumbs/{index}.jpg",
            index=index,
            jump2x=[Jump2xItem(z=z, x=0) for z in range(zmax + 1)],
        )
        for index in (1, 2, 3)
    ]


def _record() -> ProcessingRecord:
    record = new_record("v1")
    record.original = {"width": 3000, "height": 2000, "path": "orig.jpg", "source_maps": []}
    record.status["original"] = "generating_tiles"
    record.status["bw"] = "pending_selection"
    return record


def test_build_manifest_rules(tmp_path: Path) -> None:
    record = _record()

    manifest = build_manifest("v1", record, _thumbnails())

    assert manifest["manifest_version"] == 1
    assert manifest["version_id"] == "v1"
    assert manifest["max_z"] == 4
    assert manifest["url_template"] != ""
    assert manifest["url_template_bw"] == ""
    assert manifest["url_template_hook"] == ""
    assert len(manifest["layers"]) == 5
    assert [t["index"] for t in manifest["thumbnails"]] == [3, 2, 1]
    result = validate_manifest(manifest)
    assert result.valid is True
    assert result.errors == []


def test_validate_manifest_rejects_broken() -> None:
    record = _record()
    manifest = build_manifest("v1", record, _thumbnails())
    manifest["thumbnails"][0]["jump2x"] = manifest["thumbnails"][0]["jump2x"][:-1]

    result = validate_manifest(manifest)

    assert result.valid is False
    assert any("jump2x" in error for error in result.errors)


def test_validate_manifest_rejects_out_of_range() -> None:
    record = _record()
    manifest = build_manifest("v1", record, _thumbnails())
    manifest["thumbnails"][0]["jump2x"][-1]["x"] = 999

    result = validate_manifest(manifest)

    assert result.valid is False
    assert any("越界" in error for error in result.errors)


def test_validate_manifest_rejects_order() -> None:
    record = _record()
    manifest = build_manifest("v1", record, _thumbnails())
    manifest["thumbnails"].reverse()

    result = validate_manifest(manifest)

    assert result.valid is False
    assert any("倒序" in error for error in result.errors)
