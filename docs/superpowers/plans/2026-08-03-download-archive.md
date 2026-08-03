# 获取与归档模块（M1+M2）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现可运行的「基建 + 获取归档」切片：输入清单解析、来源图片下载与校验归档、processing.json 处理记录，全部通过 pytest。

**Architecture:** 新建 `hd_image_system` 包，按职责拆分 `config` / `models` / `downloader` / `records` / `cli` 五个模块；输入清单按 `img_num` 排序，下载失败只记录不中断，最终状态写入 `records/processing.json`。本切片不涉及拼接、瓦片、黑白/双钩与 Manifest（后续计划）。

**Tech Stack:** Python 3.11（conda env `zgy_hd_py311`）、pydantic v2、httpx、Pillow、pytest、ruff、mypy、black、isort。

## Global Constraints

- Python 3.11+；所有函数必须有 type hints，docstring 使用 Google 风格（AGENTS.md）。
- 路径操作必须使用 `pathlib.Path`，禁止 `os.path`（AGENTS.md）。
- 当前阶段不引入数据库；状态与记录写入 `records/processing.json`（REQ §12）。
- 输入清单契约：JSON 数组，字段 `img_id` / `source_url` / `img_num`（1 起始，权威排序字段）（REQ §4.1）。
- 支持的图片格式：JPG、PNG、TIF（REQ §4.1）。
- 下载失败/不可读/格式不支持：记录失败原因，停止后续处理且不发布 Manifest（REQ §4.3）。
- 运行测试：`conda run -n zgy_hd_py311 python -m pytest`；质量门禁：`black --check . && isort --check . && ruff check . && mypy hd_image_system`。
- 提交信息关联需求编号：`feat(REQ-calligraphy-hd-image-system): ...`（AGENTS.md D3）。

---

### Task 1: 项目脚手架（pyproject + 包骨架）

**Files:**
- Create: `pyproject.toml`
- Create: `hd_image_system/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: 无。
- Produces: 可被 pytest 发现并导入的 `hd_image_system` 包。

- [ ] **Step 1: 写失败测试**

`tests/test_smoke.py`：
```python
def test_package_importable() -> None:
    import hd_image_system  # noqa: F401

    assert hd_image_system.__doc__ is not None
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_smoke.py -v`
Expected: FAIL（ModuleNotFoundError: No module named 'hd_image_system'）

- [ ] **Step 3: 脚手架实现**

`pyproject.toml`：
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 100

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B"]

[tool.mypy]
python_version = "3.11"
plugins = ["pydantic.mypy"]
disallow_untyped_defs = true
check_untyped_defs = true
```

`hd_image_system/__init__.py`：
```python
"""书法高清大图系统（REQ-calligraphy-hd-image-system）。"""
```

`tests/__init__.py`（空文件）。

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml hd_image_system/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 项目脚手架"
```

---

### Task 2: 配置模块

**Files:**
- Create: `hd_image_system/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 无。
- Produces: `TaskConfig(version_id: str, input_list_path: Path, storage_root: Path = Path("storage"), timeout_seconds: float = 60.0)`，frozen dataclass。

- [ ] **Step 1: 写失败测试**

`tests/test_config.py`：
```python
from pathlib import Path

from hd_image_system.config import TaskConfig


def test_task_config_defaults() -> None:
    cfg = TaskConfig(version_id="v1", input_list_path=Path("list.json"))

    assert cfg.version_id == "v1"
    assert cfg.storage_root == Path("storage")
    assert cfg.timeout_seconds == 60.0
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_config.py -v`
Expected: FAIL（ModuleNotFoundError: No module named 'hd_image_system.config'）

- [ ] **Step 3: 实现**

`hd_image_system/config.py`：
```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/config.py tests/test_config.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 任务配置模块"
```

---

### Task 3: 数据模型与输入清单解析

**Files:**
- Create: `hd_image_system/models.py`
- Test: `tests/test_models.py`
- Test fixture: `tests/fixtures/sample_list.json`

**Interfaces:**
- Consumes: 无。
- Produces:
  - `SourceItem(img_id: str, source_url: str, img_num: int)`
  - `DownloadResult(...)`（字段见 models.py）
  - `parse_input_list(path: Path) -> list[SourceItem]`（按 img_num 升序）
  - `processing_mode(items: list[SourceItem]) -> Literal["single", "multi"]`

- [ ] **Step 1: 写失败测试**

`tests/fixtures/sample_list.json`（img_num 故意乱序）：
```json
[
  {"img_id": "b", "source_url": "https://example.com/2.jpg", "img_num": 2},
  {"img_id": "a", "source_url": "https://example.com/1.jpg", "img_num": 1}
]
```

`tests/test_models.py`：
```python
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
    fixture.write_text(json.dumps([{"img_id": "a", "source_url": "https://example.com/1.jpg"}]), encoding="utf-8")

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
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_models.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`hd_image_system/models.py`：
```python
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
        width/height: 图片像素宽高。
        scaled: 是否经过高度统一缩放（拼接阶段填写）。
        original_size/unified_size: 缩放前/后尺寸（拼接阶段填写）。
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
```

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/models.py tests/test_models.py tests/fixtures/sample_list.json
git commit -m "feat(REQ-calligraphy-hd-image-system): 数据模型与输入清单解析"
```

---

### Task 4: 下载与归档

**Files:**
- Create: `hd_image_system/downloader.py`
- Test: `tests/test_downloader.py`

**Interfaces:**
- Consumes: `TaskConfig`、`SourceItem`、`DownloadResult`、`SUPPORTED_FORMATS`。
- Produces: `download_source(source: SourceItem, source_index: int, dest_dir: Path, timeout_seconds: float = 60.0, client: httpx.Client | None = None) -> DownloadResult`

- [ ] **Step 1: 写失败测试**

`tests/test_downloader.py`：
```python
import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from hd_image_system.downloader import download_source
from hd_image_system.models import SourceItem


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 2), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_download_ok(tmp_path: Path) -> None:
    png = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=png, headers={"content-type": "image/png"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = SourceItem(img_id="u1", source_url="http://example.com/a.png", img_num=1)

    result = download_source(source, 1, tmp_path, client=client)

    assert result.status == "ok"
    assert result.file_format == "png"
    assert result.width == 4
    assert result.height == 2
    assert result.failure_reason is None
    assert (tmp_path / "1.png").is_file()


def test_download_http_404(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = SourceItem(img_id="u1", source_url="http://example.com/missing.jpg", img_num=1)

    result = download_source(source, 1, tmp_path, client=client)

    assert result.status == "failed"
    assert result.failure_reason is not None


def test_download_unreadable_content(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-an-image", headers={"content-type": "image/jpeg"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = SourceItem(img_id="u1", source_url="http://example.com/bad.jpg", img_num=1)

    result = download_source(source, 1, tmp_path, client=client)

    assert result.status == "failed"
    assert "格式" in (result.failure_reason or "")


def test_content_type_wins_over_url_suffix(tmp_path: Path) -> None:
    png = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=png, headers={"content-type": "image/jpeg"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = SourceItem(img_id="u1", source_url="http://example.com/x.png", img_num=1)

    result = download_source(source, 1, tmp_path, client=client)

    assert result.status == "ok"
    assert (tmp_path / "1.jpg").is_file()
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_downloader.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`hd_image_system/downloader.py`：
```python
"""来源图片下载与归档（REQ §4）。"""

from datetime import datetime, timezone
from pathlib import Path

import httpx
from PIL import Image

from hd_image_system.config import TaskConfig
from hd_image_system.models import SUPPORTED_FORMATS, DownloadResult, SourceItem

_CONTENT_TYPE_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tif",
}


def _guess_ext(content_type: str | None, source_url: str) -> str:
    """根据响应 Content-Type 优先推断扩展名，其次使用 URL 后缀。

    Args:
        content_type: HTTP 响应 Content-Type。
        source_url: 原始 URL。

    Returns:
        文件扩展名（.jpg/.png/.tif）。
    """
    if content_type:
        ext = _CONTENT_TYPE_EXT.get(content_type.lower())
        if ext:
            return ext
    suffix = Path(source_url.split("?")[0]).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff"} else ".jpg"


def _validate_image(path: Path) -> tuple[str, int, int]:
    """校验图片可读性与格式，返回 (格式, 宽, 高)。

    Args:
        path: 已下载的图片文件路径。

    Returns:
        小写格式名与像素宽高。

    Raises:
        ValueError: 格式不支持或文件不可读。
    """
    with Image.open(path) as im:
        fmt = im.format or ""
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的图片格式: {fmt}")
    with Image.open(path) as im:
        width, height = im.size
    return fmt.lower(), width, height


def download_source(
    source: SourceItem,
    source_index: int,
    dest_dir: Path,
    timeout_seconds: float = 60.0,
    client: httpx.Client | None = None,
) -> DownloadResult:
    """下载单个来源图并校验归档。

    下载或校验失败时不抛异常，返回 status=failed 的记录（REQ §4.3）。

    Args:
        source: 来源项。
        source_index: 1 起始位置。
        dest_dir: 归档目录（{storage_root}/{version_id}/source）。
        timeout_seconds: 下载超时秒数。
        client: 可注入的 httpx.Client（便于测试）。

    Returns:
        下载与校验结果记录。
    """
    base = DownloadResult(
        source_index=source_index,
        img_id=source.img_id,
        source_url=source.source_url,
        status="ok",
    )
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout_seconds, follow_redirects=True)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with client.stream("GET", source.source_url) as resp:
            resp.raise_for_status()
            ext = _guess_ext(resp.headers.get("content-type"), source.source_url)
            path = dest_dir / f"{source_index}{ext}"
            with path.open("wb") as file_handle:
                for chunk in resp.iter_bytes():
                    file_handle.write(chunk)
        fmt, width, height = _validate_image(path)
        return base.model_copy(
            update={
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "local_path": str(path),
                "original_filename": path.name,
                "file_format": fmt,
                "width": width,
                "height": height,
            }
        )
    except Exception as exc:  # noqa: BLE001 - 下载失败需记录而非抛出
        return base.model_copy(update={"status": "failed", "failure_reason": str(exc)})
    finally:
        if owns_client:
            client.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_downloader.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/downloader.py tests/test_downloader.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 来源图片下载与归档"
```

---

### Task 5: processing.json 记录

**Files:**
- Create: `hd_image_system/records.py`
- Test: `tests/test_records.py`

**Interfaces:**
- Consumes: `DownloadResult`。
- Produces:
  - `ProcessingRecord(version_id, status, sources, original, bw, hook, manifest)`
  - `new_record(version_id: str) -> ProcessingRecord`
  - `load_record(path: Path, version_id: str) -> ProcessingRecord`
  - `save_record(record: ProcessingRecord, path: Path) -> None`

- [ ] **Step 1: 写失败测试**

`tests/test_records.py`：
```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_records.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`hd_image_system/records.py`：
```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_records.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/records.py tests/test_records.py
git commit -m "feat(REQ-calligraphy-hd-image-system): processing.json 处理记录"
```

---

### Task 6: CLI 命令与端到端测试

**Files:**
- Create: `hd_image_system/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `parse_input_list`、`processing_mode`、`download_source`、`load_record`、`save_record`。
- Produces: `build_parser() -> argparse.ArgumentParser`、`main(argv: list[str] | None = None) -> int`；`download` 子命令。

- [ ] **Step 1: 写失败测试**

`tests/test_cli.py`：
```python
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from hd_image_system.cli import main
from hd_image_system.records import load_record


class _Handler(BaseHTTPRequestHandler):
    content: dict[str, bytes] = {}

    def do_GET(self) -> None:
        body = self.content.get(self.path)
        if body is None:
            self.send_response(404)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
        self.end_headers()
        if body is not None:
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def test_cli_download_ok(tmp_path: Path) -> None:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 2), (255, 255, 255)).save(buf, format="PNG")
    _Handler.content = {"/a.png": buf.getvalue()}
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        list_path = tmp_path / "list.json"
        list_path.write_text(
            json.dumps(
                [{"img_id": "u1", "source_url": f"{base_url}/a.png", "img_num": 1}]
            ),
            encoding="utf-8",
        )
        storage = tmp_path / "storage"

        rc = main(
            [
                "download",
                "--version-id",
                "v1",
                "--input-list",
                str(list_path),
                "--storage-root",
                str(storage),
            ]
        )

        assert rc == 0
        record = load_record(storage / "v1" / "records" / "processing.json", "v1")
        assert record.sources[0].status == "ok"
        assert record.sources[0].file_format == "png"
    finally:
        server.shutdown()
        thread.join(timeout=5)
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_cli.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`hd_image_system/cli.py`：
```python
"""命令行入口（获取与归档阶段，REQ §4）。"""

import argparse
from pathlib import Path

from hd_image_system.downloader import download_source
from hd_image_system.models import parse_input_list, processing_mode
from hd_image_system.records import load_record, save_record


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        含 download 子命令的解析器。
    """
    parser = argparse.ArgumentParser(prog="hd-image", description="书法高清大图处理管线")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="下载并归档来源图片（REQ §4）")
    download.add_argument("--version-id", required=True, help="作品级唯一标识")
    download.add_argument("--input-list", required=True, type=Path, help="输入清单 JSON 路径")
    download.add_argument("--storage-root", type=Path, default=Path("storage"), help="存储根前缀")
    return parser


def cmd_download(args: argparse.Namespace) -> int:
    """执行下载与归档阶段。

    Args:
        args: 解析后的命令行参数。

    Returns:
        全部成功返回 0，存在失败返回 1。
    """
    items = parse_input_list(args.input_list)
    mode = processing_mode(items)
    records_path = args.storage_root / args.version_id / "records" / "processing.json"
    record = load_record(records_path, args.version_id)
    dest_dir = args.storage_root / args.version_id / "source"

    results = []
    for index, source in enumerate(items, start=1):
        result = download_source(source, index, dest_dir)
        results.append(result)
        if result.status == "failed":
            print(f"下载失败 source_index={index}: {result.failure_reason}")
    record.sources = results
    save_record(record, records_path)

    failed = sum(1 for r in results if r.status == "failed")
    print(f"模式={mode} 来源数={len(results)} 成功={len(results) - failed} 失败={failed}")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """程序入口。

    Args:
        argv: 命令行参数列表；None 表示使用 sys.argv。

    Returns:
        退出码。
    """
    args = build_parser().parse_args(argv)
    if args.command == "download":
        return cmd_download(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行确认通过**

Run: `conda run -n zgy_hd_py311 python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add hd_image_system/cli.py tests/test_cli.py
git commit -m "feat(REQ-calligraphy-hd-image-system): 获取归档 CLI 命令"
```

---

## 全量验证

Run: `conda run -n zgy_hd_py311 python -m pytest` 全绿；`conda run -n zgy_hd_py311 python -m ruff check .`；`conda run -n zgy_hd_py311 python -m black --check .`；`conda run -n zgy_hd_py311 python -m isort --check .`；`conda run -n zgy_hd_py311 python -m mypy hd_image_system`。

## Self-Review 结论

- 覆盖：REQ §4.1（清单契约）、§4.2（来源记录）、§4.3（失败处理）、§6.3（状态机）、§9.2（records 对象键）均有对应任务；拼接/瓦片/黑白/双钩/评审/Manifest 属后续计划（按 writing-plans 子系统拆分原则）。
- 无占位符；各任务含完整测试与实现代码。
- 类型一致性：`parse_input_list -> list[SourceItem]`、`download_source -> DownloadResult`、`load_record/save_record` 签名在 Task 6 与 Task 3/4/5 一致。
