from __future__ import annotations

import hashlib
import io
import json
import zipfile

from fastapi.testclient import TestClient
from PIL import Image


def _make_png(width: int = 240, height: int = 180) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (width, height), (34, 197, 94, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_export_batch_renders_real_pillow_images_for_project_assets(
    client: TestClient,
) -> None:
    proj = client.post("/v1/projects", json={"name": "Real Export Project"}).json()
    pid = proj["id"]
    client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("product.png", _make_png(), "image/png")},
    )

    res = client.post(
        "/api/v1/export/batch",
        json={
            "project_id": pid,
            "recipes": [
                {
                    "preset_id": "shopee_square",
                    "format": "WEBP",
                    "quality": 90,
                    "include_shadow": True,
                },
                {
                    "preset_id": "amazon_hero",
                    "format": "JPEG",
                    "quality": 95,
                    "include_shadow": False,
                    "watermark_text": "KROMA",
                },
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    assert body["total_images"] == 2
    assert body["download_url"].startswith("/api/v1/export/download/")

    dl_res = client.get(body["download_url"])
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(dl_res.content), "r") as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "manifest.txt" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["total_images"] == 2
        for item in manifest["items"]:
            raw_img = zf.read(item["output_filename"])
            assert raw_img != b"KROMA_SAMPLE_IMAGE_DATA"
            assert item["sha256"] == hashlib.sha256(raw_img).hexdigest()
            with Image.open(io.BytesIO(raw_img)) as im:
                if item["resolved_preset_id"] == "shopee_1_1":
                    assert im.size == (1024, 1024)
                    assert im.format == "WEBP"
                elif item["resolved_preset_id"] == "amazon_white_85":
                    assert im.size == (2000, 2000)
                    assert im.format == "JPEG"
                    assert im.getpixel((0, 0)) == (255, 255, 255)


def test_export_batch_legacy_assetless_uses_real_pillow_pipeline(
    client: TestClient,
) -> None:
    res = client.post(
        "/v1/export/batch",
        json={
            "project_id": "legacy_assetless_proj",
            "recipes": [
                {"preset_id": "shopee_square", "format": "WEBP", "quality": 85},
                {"preset_id": "amazon_hero", "format": "JPEG", "quality": 90},
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["download_url"].startswith("/v1/export/download/")
    dl = client.get(body["download_url"])
    assert dl.status_code == 200

    with zipfile.ZipFile(io.BytesIO(dl.content), "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        for item in manifest["items"]:
            raw = zf.read(item["output_filename"])
            assert raw != b"KROMA_SAMPLE_IMAGE_DATA"
            assert item["sha256"] == hashlib.sha256(raw).hexdigest()
            with Image.open(io.BytesIO(raw)) as im:
                assert im.width >= 1024 and im.height >= 1024


def test_export_batch_rejects_bool_and_path_traversal(client: TestClient) -> None:
    bad_bool = client.post(
        "/v1/export/batch",
        json={
            "project_id": "any",
            "recipes": [{"preset_id": "shopee_1_1", "quality": True}],
        },
    )
    assert bad_bool.status_code == 422
    assert bad_bool.json()["code"] == "VALIDATION_ERROR"

    missing_proj = client.post(
        "/v1/export/batch",
        json={
            "project_id": "missing_proj",
            "asset_ids": ["asset_1"],
            "recipes": [{"preset_id": "shopee_1_1"}],
        },
    )
    assert missing_proj.status_code == 404

    trav1 = client.get("/v1/export/download/..%2F..%2Fetc")
    assert trav1.status_code == 422
    assert trav1.json()["code"] == "PATH_TRAVERSAL_DETECTED"

    trav2 = client.get("/api/v1/export/download/..%2Fsecret")
    assert trav2.status_code == 422
    assert trav2.json()["code"] == "PATH_TRAVERSAL_DETECTED"
