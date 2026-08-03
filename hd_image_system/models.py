"""数据模型与输入清单解析（REQ §4.1、§4.2）。"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SUPPORTED_FORMATS: tuple[str, ...] = ("JPEG", "PNG", "TIFF")


class SourceItem(BaseModel):
    """输入清单中的单个来源项。

    Attributes:
        img_id: 来源图唯一标识（实测为 UUID）。
        source_url: 原始 HTTP 地址。
        img_num: 来源图顺序号，1 起始；多图拼接权威排序字段。
    """

    img_id: str
    source_url: str
    img_num: int = Field(ge=1)


class DownloadResult(BaseModel):
    """单个来源图的下载与校验结果（REQ §4.2）。

    Attributes:
        source_index: 在清单中的 1 起始位置。
        img_id: 来源图唯一标识。
        source_url: 原始 HTTP 地址。
        status: ok 或 failed。
        failure_reason: 失败原因。
        downloaded_at: 下载完成时间（ISO 8601）。
        local_path: 归档文件路径。
        original_filename: 归档文件名。
        file_format: 校验后的图片格式（jpeg/png/tif）。
        width: 图片像素宽。
        height: 图片像素高。
        scaled: 是否经过高度统一缩放（拼接阶段填写）。
        original_size: 缩放前尺寸（拼接阶段填写）。
        unified_size: 统一后尺寸（拼接阶段填写）。
        x_range: 分屏图在拼接原图中的物理 X 区间（拼接阶段填写）。
    """

    source_index: int
    img_id: str
    source_url: str
    status: Literal["ok", "failed"]
    failure_reason: str | None = None
    downloaded_at: str | None = None
    local_path: str | None = None
    original_filename: str | None = None
    file_format: str | None = None
    width: int | None = None
    height: int | None = None
    scaled: bool = False
    original_size: tuple[int, int] | None = None
    unified_size: tuple[int, int] | None = None
    x_range: tuple[int, int] | None = None


def parse_input_list(path: Path) -> list[SourceItem]:
    """解析输入清单 JSON 并按 img_num 升序返回。

    Args:
        path: 清单 JSON 文件路径。

    Returns:
        按 img_num 排序的来源项列表。

    Raises:
        ValueError: 文件不存在、JSON 非法或非数组。
    """
    if not path.is_file():
        raise ValueError(f"输入清单不存在: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"输入清单 JSON 非法: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("输入清单必须是 JSON 数组")
    items = [SourceItem.model_validate(item) for item in raw]
    items.sort(key=lambda s: s.img_num)
    return items


def processing_mode(items: list[SourceItem]) -> Literal["single", "multi"]:
    """根据来源项数量判定处理模式（REQ §4.1）。

    Args:
        items: 已排序的来源项列表。

    Returns:
        单图模式或多图模式。
    """
    return "single" if len(items) == 1 else "multi"
