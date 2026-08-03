"""来源图片下载与归档（REQ §4）。"""

from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

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
        ValueError: 文件不可读或格式不支持。
    """
    try:
        with Image.open(path) as im:
            fmt = im.format or ""
    except Exception as exc:  # noqa: BLE001 - 转换为统一错误语义
        raise ValueError(f"图片不可读: {exc}") from exc
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
    http_client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with http_client.stream("GET", source.source_url) as resp:
            resp.raise_for_status()
            ext = _guess_ext(resp.headers.get("content-type"), source.source_url)
            path = dest_dir / f"{source_index}{ext}"
            with path.open("wb") as file_handle:
                for chunk in resp.iter_bytes():
                    file_handle.write(chunk)
        fmt, width, height = _validate_image(path)
        return base.model_copy(
            update={
                "downloaded_at": datetime.now(UTC).isoformat(),
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
            http_client.close()
