from pathlib import Path

from hd_image_system.config import TaskConfig


def test_task_config_defaults() -> None:
    cfg = TaskConfig(version_id="v1", input_list_path=Path("list.json"))

    assert cfg.version_id == "v1"
    assert cfg.storage_root == Path("storage")
    assert cfg.timeout_seconds == 60.0
