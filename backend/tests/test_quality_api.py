from __future__ import annotations

import io
from fastapi.testclient import TestClient
from PIL import Image


def _create_test_image(width: int = 1024, height: int = 1024, bg_color=(255, 255, 255)) -> bytes:
    img = Image.new("RGBA", (width, height), bg_color + (255,))
    # Draw a colored subject in the center
    for x in range(width // 4, 3 * width // 4):
        for y in range(height // 4, 3 * height // 4):
            img.putpixel((x, y), (50, 100, 200, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_quality_inspect_shopee_compliant(client: TestClient) -> None:
    img_bytes = _create_test_image(1024, 1024, (255, 255, 255))
    res = client.post(
        "/v1/quality/inspect?marketplace=shopee",
        files={"file": ("test_shopee.png", img_bytes, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["marketplace"] == "shopee"
    assert data["is_compliant"] is True
    assert data["overall_score"] >= 80.0
    check_ids = [c["check_id"] for c in data["checks"]]
    assert "resolution" in check_ids
    assert "aspect_ratio" in check_ids
    assert "background_purity" in check_ids


def test_quality_inspect_tiktok_aspect_ratio_warn(client: TestClient) -> None:
    # 1:1 image on TikTok which expects 3:4 (1200x1600)
    img_bytes = _create_test_image(800, 800, (255, 255, 255))
    res = client.post(
        "/v1/quality/inspect?marketplace=tiktok",
        files={"file": ("test_tiktok.png", img_bytes, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["marketplace"] == "tiktok"
    # Resolution < 1200x1600 should fail or warn
    res_check = next(c for c in data["checks"] if c["check_id"] == "resolution")
    assert res_check["status"] == "fail"
    assert len(data["recommended_actions"]) > 0


def test_quality_inspect_amazon_85_rule(client: TestClient) -> None:
    img_bytes = _create_test_image(1200, 1200, (255, 255, 255))
    res = client.post(
        "/v1/quality/inspect?marketplace=amazon",
        files={"file": ("test_amazon.png", img_bytes, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["marketplace"] == "amazon"
    amazon_check = next(c for c in data["checks"] if c["check_id"] == "amazon_85_rule")
    assert amazon_check is not None
