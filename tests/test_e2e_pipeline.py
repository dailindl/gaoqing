import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from hd_image_system.cli import main
from hd_image_system.manifest import validate_manifest
from hd_image_system.records import load_record
from hd_image_system.review.api import create_app


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


def _png_bytes(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_full_pipeline_e2e(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    version_id = "e2e"
    _Handler.content = {
        "/1.png": _png_bytes((200, 100), (255, 0, 0)),
        "/2.png": _png_bytes((160, 80), (0, 0, 255)),
    }
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        list_path = tmp_path / "list.json"
        list_path.write_text(
            json.dumps(
                [
                    {"img_id": "u1", "source_url": f"{base_url}/1.png", "img_num": 1},
                    {"img_id": "u2", "source_url": f"{base_url}/2.png", "img_num": 2},
                ]
            ),
            encoding="utf-8",
        )

        assert (
            main(
                [
                    "download",
                    "--version-id",
                    version_id,
                    "--input-list",
                    str(list_path),
                    "--storage-root",
                    str(storage),
                ]
            )
            == 0
        )
        assert main(["stitch", "--version-id", version_id, "--storage-root", str(storage)]) == 0
        assert main(["bw", "--version-id", version_id, "--storage-root", str(storage)]) == 0

        client = TestClient(create_app(storage))
        resp = client.post(
            f"/api/versions/{version_id}/select",
            json={"kind": "bw", "candidate_id": "cand_01_otsu", "operator": "tester"},
        )
        assert resp.status_code == 200

        assert main(["hook", "--version-id", version_id, "--storage-root", str(storage)]) == 0
        resp = client.post(
            f"/api/versions/{version_id}/select",
            json={
                "kind": "hook",
                "candidate_id": "hook_01_external_contour",
                "operator": "tester",
            },
        )
        assert resp.status_code == 200

        for kind in ("original", "bw", "hook"):
            assert (
                main(
                    [
                        "tile",
                        "--version-id",
                        version_id,
                        "--storage-root",
                        str(storage),
                        "--kind",
                        kind,
                    ]
                )
                == 0
            )
        assert main(["manifest", "--version-id", version_id, "--storage-root", str(storage)]) == 0

        manifest_path = storage / version_id / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validation = validate_manifest(manifest)
        assert validation.valid, validation.errors
        assert manifest["url_template"] != ""
        assert manifest["url_template_bw"] != ""
        assert manifest["url_template_hook"] != ""
        assert [t["index"] for t in manifest["thumbnails"]] == [2, 1]

        record = load_record(storage / version_id / "records" / "processing.json", version_id)
        assert record.status == {
            "original": "published",
            "bw": "published",
            "hook": "published",
        }
        assert record.sources[0].x_range == (160, 320)
        assert record.sources[0].scaled is True
        assert record.sources[1].x_range == (0, 160)
        assert (storage / version_id / "tiles" / "original" / "1" / "1_0.jpg").is_file()
        assert (storage / version_id / "tiles" / "bw" / "1" / "0_0.jpg").is_file()
        assert (storage / version_id / "tiles" / "hook" / "1" / "0_0.jpg").is_file()
        assert (storage / version_id / "bw" / "selected.png").is_file()
        assert (storage / version_id / "hook" / "selected.png").is_file()
    finally:
        server.shutdown()
        thread.join(timeout=5)
