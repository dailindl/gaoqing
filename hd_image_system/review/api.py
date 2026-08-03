"""人工评审工具 FastAPI 后端（REQ §11）。"""

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from hd_image_system.records import ProcessingRecord, load_record, save_record

Kind = Literal["bw", "hook"]
KINDS: tuple[Kind, ...] = ("bw", "hook")


class SelectRequest(BaseModel):
    """选择确认请求。

    Attributes:
        kind: 版本类型（bw/hook）。
        candidate_id: 候选标识。
        operator: 操作者标识。
    """

    kind: Kind
    candidate_id: str
    operator: str


def _check_kind(kind: str) -> Kind:
    """校验版本类型。

    Args:
        kind: 版本类型字符串。

    Returns:
        合法类型。

    Raises:
        HTTPException: 类型非法。
    """
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail=f"未知类型: {kind}")
    return kind  # type: ignore[return-value]


def _load_record(storage_root: Path, version_id: str) -> ProcessingRecord:
    """加载处理记录。

    Args:
        storage_root: 存储根前缀。
        version_id: 作品级唯一标识。

    Returns:
        处理记录。
    """
    records_path = storage_root / version_id / "records" / "processing.json"
    return load_record(records_path, version_id)


def _kind_data(record: ProcessingRecord, kind: Kind) -> dict[str, Any]:
    """取版本候选数据（bw 或 hook）。

    Args:
        record: 处理记录。
        kind: 版本类型。

    Returns:
        候选与选中信息。
    """
    data = record.bw if kind == "bw" else record.hook
    if data is None:
        return {"candidates": [], "selected": None}
    return data


def _find_candidate(candidates: list[Any], candidate_id: str) -> dict[str, Any] | None:
    """按候选标识查找候选记录。

    Args:
        candidates: 候选记录列表。
        candidate_id: 候选标识。

    Returns:
        候选记录或 None。
    """
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("candidate_id") == candidate_id:
            return candidate
    return None


def create_app(storage_root: Path) -> FastAPI:
    """创建评审工具应用。

    Args:
        storage_root: 存储根前缀。

    Returns:
        FastAPI 应用。
    """
    app = FastAPI(title="书法高清大图人工评审工具")
    app.state.storage_root = storage_root
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        """返回评审工具页面。"""
        return FileResponse(str(static_dir / "index.html"))

    @app.get("/api/versions/{version_id}/candidates/{kind}")
    def list_candidates(version_id: str, kind: str) -> dict[str, Any]:
        """列出指定类型的候选与已选信息。"""
        checked_kind = _check_kind(kind)
        record = _load_record(storage_root, version_id)
        data = _kind_data(record, checked_kind)
        return {
            "version_id": version_id,
            "kind": checked_kind,
            "candidates": data.get("candidates") or [],
            "selected": data.get("selected"),
        }

    @app.get("/api/versions/{version_id}/original")
    def original_file(version_id: str) -> FileResponse:
        """提供原图用于坐标对照。"""
        record = _load_record(storage_root, version_id)
        if not record.original or not record.original.get("path"):
            raise HTTPException(status_code=404, detail="原图未生成")
        path = Path(record.original["path"])
        if not path.is_file():
            raise HTTPException(status_code=404, detail="原图文件不存在")
        return FileResponse(str(path))

    @app.get("/api/versions/{version_id}/candidates/{kind}/{candidate_id}.png")
    def candidate_file(version_id: str, kind: str, candidate_id: str) -> FileResponse:
        """提供候选图片文件。"""
        checked_kind = _check_kind(kind)
        record = _load_record(storage_root, version_id)
        data = _kind_data(record, checked_kind)
        candidate = _find_candidate(data.get("candidates") or [], candidate_id)
        if candidate is None or not candidate.get("path"):
            raise HTTPException(status_code=404, detail="候选不存在")
        path = Path(candidate["path"])
        if not path.is_file():
            raise HTTPException(status_code=404, detail="候选文件不存在")
        return FileResponse(str(path))

    @app.post("/api/versions/{version_id}/select")
    def select(version_id: str, payload: SelectRequest) -> dict[str, Any]:
        """确认选择候选并回写处理记录。"""
        record = _load_record(storage_root, version_id)
        data = _kind_data(record, payload.kind)
        candidate = _find_candidate(data.get("candidates") or [], payload.candidate_id)
        if candidate is None or not candidate.get("path"):
            raise HTTPException(status_code=404, detail="候选不存在")
        src = Path(candidate["path"])
        if not src.is_file():
            raise HTTPException(status_code=404, detail="候选文件不存在")
        selected_png = storage_root / version_id / payload.kind / "selected.png"
        selected_png.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, selected_png)
        selected = {
            "candidate_id": candidate.get("candidate_id"),
            "strategy": candidate.get("strategy"),
            "params": candidate.get("params"),
            "path": str(selected_png),
            "operator": payload.operator,
            "time": datetime.now(UTC).isoformat(),
        }
        data["selected"] = selected
        if payload.kind == "bw":
            record.bw = data
        else:
            record.hook = data
        record.status[payload.kind] = "selected"
        save_record(record, storage_root / version_id / "records" / "processing.json")
        return {"ok": True, "selected": selected}

    return app
