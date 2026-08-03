import io
from pathlib import Path

import httpx
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
    assert "不可读" in (result.failure_reason or "")


def test_content_type_wins_over_url_suffix(tmp_path: Path) -> None:
    png = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=png, headers={"content-type": "image/jpeg"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = SourceItem(img_id="u1", source_url="http://example.com/x.png", img_num=1)

    result = download_source(source, 1, tmp_path, client=client)

    assert result.status == "ok"
    assert (tmp_path / "1.jpg").is_file()
