from __future__ import annotations

import io
import json
import zipfile
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.domain.rules import (
    validate_project_name,
    validate_project_description,
    validate_state_payload,
    check_revision_conflict,
)


def _create_synthetic_product_image(width: int = 400, height: int = 500) -> bytes:
    """Create a synthetic e-commerce product image (e.g. shoe on plain background)"""
    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    # Draw a synthetic colored product box in center
    for y in range(100, 400):
        for x in range(100, 300):
            img.putpixel((x, y), (79, 70, 229, 255))  # Indigo product
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_e2e_marketplace_presets_specs():
    """Verify all marketplace presets adhere to official platform specifications"""
    client = TestClient(app)
    res = client.get("/v1/presets")
    assert res.status_code == 200
    data = res.json()
    items = data["items"]
    presets_by_id = {p["id"]: p for p in items}

    # 1. Shopee
    shopee = presets_by_id["shopee_1_1"]
    assert shopee["width"] == 1024
    assert shopee["height"] == 1024
    assert shopee["aspect_ratio"] == "1:1"
    assert "webp" in shopee["formats"]

    # 2. TikTok Shop 3:4 Vertical
    tiktok = presets_by_id["tiktok_3_4"]
    assert tiktok["width"] == 1200
    assert tiktok["height"] == 1600
    assert tiktok["aspect_ratio"] == "3:4"
    assert tiktok["safe_zone"]["top"] > 0
    assert tiktok["safe_zone"]["bottom"] > 0

    # 3. Amazon White Hero 85% Rule
    amazon = presets_by_id["amazon_white_85"]
    assert amazon["background_rgb"] == [255, 255, 255]
    assert amazon["subject_area_ratio"] == 0.85
    assert amazon["width"] >= 1000


def test_e2e_full_project_asset_and_proofing_workflow():
    """Full end-to-end studio workflow: project -> asset upload -> state mutation -> proofing session -> feedback"""
    client = TestClient(app)

    # 1. Create new project
    proj_res = client.post("/v1/projects", json={"name": "E2E Nike Sneaker Campaign"})
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    # 2. Upload synthetic product photo
    raw_img = _create_synthetic_product_image()
    upload_res = client.post(
        f"/v1/projects/{proj_id}/assets",
        files={"file": ("sneaker_hero.png", raw_img, "image/png")},
    )
    assert upload_res.status_code == 201
    asset_data = upload_res.json()
    asset_id = asset_data["asset_id"]
    assert asset_data["width"] == 400
    assert asset_data["height"] == 500

    # 3. Download asset file byte-for-byte
    file_res = client.get(f"/v1/assets/{asset_id}/file")
    assert file_res.status_code == 200
    assert file_res.content == raw_img

    # 4. Update non-destructive editing state (Marketplace preset, physical shadow, Float32 adjustments)
    state_res = client.get(f"/v1/projects/{proj_id}/state")
    assert state_res.status_code == 200
    rev_id = state_res.json()["revision_id"]

    mutation_payload = {
        "state": {
            "commands": [
                {"type": "cutout_rmbg", "timestamp": "2026-11-26T12:00:00Z"},
                {"type": "physical_shadow", "shadow_type": "contact", "opacity": 0.55, "blur": 16},
                {"type": "float32_light", "exposure": 10, "contrast": 5, "temperature": 0},
            ],
            "preset": "amazon_white_85",
            "active_asset_id": asset_id,
        },
        "active_variant": "amazon_white_85",
        "expected_revision_id": rev_id,
    }
    update_res = client.put(f"/v1/projects/{proj_id}/state", json=mutation_payload)
    assert update_res.status_code == 200
    updated_state = update_res.json()
    assert updated_state["active_variant"] == "amazon_white_85"
    assert updated_state["state"]["preset"] == "amazon_white_85"

    # 5. Create client proofing session
    proof_res = client.post(
        "/v1/proofing",
        json={
            "project_id": proj_id,
            "title": "Duyệt ảnh bìa Amazon Hero Sneaker",
            "client_name": "Nike Vietnam Brand Team",
            "allow_comments": True,
        },
    )
    assert proof_res.status_code == 201
    session_data = proof_res.json()
    session_id = session_data["id"]
    assert session_data["status"] == "pending"

    # 6. Client submits approval and comments
    comment_res = client.post(
        f"/v1/proofing/{session_id}/feedback",
        json={
            "action": "approve",
            "comment": "Ảnh rất đẹp, nền trắng 100% chuẩn Amazon và bóng chân rất tự nhiên. Đã duyệt!",
            "author": "Nike Brand Manager",
        },
    )
    assert comment_res.status_code == 200
    updated_session = comment_res.json()
    assert updated_session["status"] == "approved"
    assert len(updated_session["feedback"]) == 1
    assert "Đã duyệt" in updated_session["feedback"][0]["comment"]


def test_e2e_batch_export_packaging():
    """Verify batch export endpoint generates a valid ZIP archive containing transformed images"""
    client = TestClient(app)

    export_req = {
        "project_id": "test_proj_export",
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
                "include_shadow": True,
            },
        ],
    }

    res = client.post("/v1/export/batch", json=export_req)
    assert res.status_code == 200
    export_resp = res.json()
    assert export_resp["status"] == "completed"
    assert export_resp["total_images"] == 2

    # Download ZIP
    download_url = export_resp["download_url"]
    dl_res = client.get(download_url)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/zip"

    # Verify binary ZIP structure
    zip_bytes = io.BytesIO(dl_res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        file_list = zf.namelist()
        assert len(file_list) >= 3  # manifest.txt + 2 images
        assert "manifest.txt" in file_list
        assert any("shopee_square" in name for name in file_list)
        assert any("amazon_hero" in name for name in file_list)
