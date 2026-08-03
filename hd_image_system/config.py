"""任务配置（REQ §4、§9）。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TaskConfig:
    """单件作品的批处理任务配置。

    Attributes:
        version_id: 作品级唯一标识，存储分区与 Manifest 使用。
        input_list_path: 输入清单 JSON 文件路径。
        storage_root: 本地存储根前缀（对应 OSS 根前缀）。
        timeout_seconds: 单次 HTTP 下载超时秒数。
    """

    version_id: str
    input_list_path: Path
    storage_root: Path = Path("storage")
    timeout_seconds: float = 60.0
