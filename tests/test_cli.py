import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from PIL import Image

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
            json.dumps([{"img_id": "u1", "source_url": f"{base_url}/a.png", "img_num": 1}]),
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
