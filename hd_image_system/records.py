"""processing.json 处理记录与状态机（REQ §6.3、§9.2）。"""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from hd_image_system.models import DownloadResult

VersionState = Literal[
    "not_generated",
    "generating_candidates",
    "pending_selection",
    "selected",
    "generating_tiles",
    "published",
    "failed",
]


class ProcessingRecord(BaseModel):
    """单件作品的内部处理记录。

    Attributes:
        version_id: 作品级唯一标识。
        status: 三版本的版本状态（REQ §6.3）。
        sources: 各来源图的下载与处理记录。
        original: 原图处理结果（拼接阶段填写）。
        bw: 黑白图处理结果（黑白阶段填写）。
        hook: 双钩图处理结果（双钩阶段填写）。
        manifest: Manifest 发布信息（装配阶段填写）。
    """

    version_id: str
    status: dict[str, VersionState]
    sources: list[DownloadResult] = []
    original: dict[str, Any] | None = None
    bw: dict[str, Any] | None = None
    hook: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None


def new_record(version_id: str) -> ProcessingRecord:
    """创建初始处理记录。

    Args:
        version_id: 作品级唯一标识。

    Returns:
        三版本均为 not_generated 的初始记录。
    """
    return ProcessingRecord(
        version_id=version_id,
        status={
            "original": "not_generated",
            "bw": "not_generated",
            "hook": "not_generated",
        },
        sources=[],
    )


def load_record(path: Path, version_id: str) -> ProcessingRecord:
    """读取处理记录；文件不存在时返回初始记录。

    Args:
        path: processing.json 路径。
        version_id: 作品级唯一标识。

    Returns:
        已加载或新建的处理记录。
    """
    if path.is_file():
        return ProcessingRecord.model_validate_json(path.read_text(encoding="utf-8"))
    return new_record(version_id)


def save_record(record: ProcessingRecord, path: Path) -> None:
    """保存处理记录（UTF-8、缩进 2）。

    Args:
        record: 处理记录。
        path: 目标路径。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
