from __future__ import annotations

import hashlib
import io

from fastapi.testclient import TestClient
from PIL import Image


def _make_bytes(fmt: str, mode: str = "RGB", size: tuple[int, int] = (32, 24)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color=(79, 70, 229)).save(buf, format=fmt)
    return buf.getvalue()


def test_asset_upload_sha256_and_immutable_download(client: TestClient) -> None:
    proj = client.post("/v1/projects", json={"name": "Asset Test"}).json()
    project_id = proj["id"]

    for ext, mime, fmt, mode in [
        ("jpg", "image/jpeg", "JPEG", "RGB"),
        ("png", "image/png", "PNG", "RGBA"),
        ("webp", "image/webp", "WEBP", "RGBA"),
    ]:
        raw = _make_bytes(fmt, mode=mode)
        expected_sha = hashlib.sha256(raw).hexdigest()

        upload_res = client.post(
            f"/v1/projects/{project_id}/assets",
            files={"file": (f"product.{ext}", raw, mime)},
        )
        assert upload_res.status_code == 201
        meta = upload_res.json()
        assert meta["project_id"] == project_id
        assert meta["sha256"] == expected_sha
        assert meta["width"] == 32
        assert meta["height"] == 24
        assert meta["byte_size"] == len(raw)
        assert meta["mime_type"] == mime
        assert meta["is_readonly"] is True

        # Exact byte-for-byte download + ETag
        file_res = client.get(f"/v1/assets/{meta['asset_id']}/file")
        assert file_res.status_code == 200
        assert file_res.content == raw
        assert file_res.headers["etag"] == f'"{expected_sha}"'
        assert file_res.headers["x-content-type-options"] == "nosniff"


def test_asset_upload_rejects_spoofed_mime_and_missing_project(client: TestClient) -> None:
    missing_proj_res = client.post(
        "/v1/projects/missing-id/assets",
        files={"file": ("a.png", _make_bytes("PNG"), "image/png")},
    )
    assert missing_proj_res.status_code == 404
    assert missing_proj_res.json()["code"] == "NOT_FOUND"

    proj = client.post("/v1/projects", json={"name": "Security Check"}).json()
    spoof_res = client.post(
        f"/v1/projects/{proj['id']}/assets",
        files={"file": ("fake.jpg", _make_bytes("PNG"), "image/jpeg")},
    )
    assert spoof_res.status_code == 422
    err = spoof_res.json()
    assert err["code"] == "MIME_SPOOF_DETECTED"
    assert err["retryable"] is False
    assert "correlation_id" in err

    missing_asset_res = client.get("/v1/assets/missing-asset/file")
    assert missing_asset_res.status_code == 404
    assert missing_asset_res.json()["code"] == "NOT_FOUND"
