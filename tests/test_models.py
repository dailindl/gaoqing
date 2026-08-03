import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hd_image_system.models import SourceItem, parse_input_list, processing_mode


def test_parse_input_list_sorts_by_img_num(tmp_path: Path) -> None:
    fixture = tmp_path / "list.json"
    fixture.write_text(
        json.dumps(
            [
                {"img_id": "b", "source_url": "https://example.com/2.jpg", "img_num": 2},
                {"img_id": "a", "source_url": "https://example.com/1.jpg", "img_num": 1},
            ]
        ),
        encoding="utf-8",
    )

    items = parse_input_list(fixture)

    assert [i.img_num for i in items] == [1, 2]
    assert [i.img_id for i in items] == ["a", "b"]


def test_parse_input_list_rejects_missing_img_num(tmp_path: Path) -> None:
    fixture = tmp_path / "list.json"
    fixture.write_text(
        json.dumps([{"img_id": "a", "source_url": "https://example.com/1.jpg"}]), encoding="utf-8"
    )

    with pytest.raises(ValidationError):
        parse_input_list(fixture)


def test_parse_input_list_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        parse_input_list(tmp_path / "nope.json")


def test_processing_mode() -> None:
    one = [SourceItem(img_id="a", source_url="https://example.com/1.jpg", img_num=1)]
    two = one + [SourceItem(img_id="b", source_url="https://example.com/2.jpg", img_num=2)]

    assert processing_mode(one) == "single"
    assert processing_mode(two) == "multi"


def test_parse_real_sample() -> None:
    sample = Path(__file__).resolve().parents[1] / "deepseek_json_20260731_ba67e1.json"
    items = parse_input_list(sample)

    assert len(items) == 27
    assert [i.img_num for i in items] == list(range(1, 28))
