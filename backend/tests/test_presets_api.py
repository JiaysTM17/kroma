from __future__ import annotations

from fastapi.testclient import TestClient


def test_presets_returns_five_versioned_marketplace_presets(client: TestClient) -> None:
    res = client.get("/v1/presets")
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    items = body["items"]
    assert len(items) == 5

    by_id = {item["id"]: item for item in items}
    assert set(by_id.keys()) == {
        "shopee_1_1",
        "tiktok_3_4",
        "tiktok_1_1",
        "lazada_1_1",
        "amazon_white_85",
    }

    assert by_id["shopee_1_1"]["width"] == 1024
    assert by_id["shopee_1_1"]["height"] == 1024
    assert by_id["tiktok_3_4"]["width"] == 1200
    assert by_id["tiktok_3_4"]["height"] == 1600
    assert by_id["tiktok_3_4"]["safe_zone"] is not None
    assert by_id["tiktok_1_1"]["width"] == 1024
    assert by_id["tiktok_1_1"]["height"] == 1024
    assert by_id["lazada_1_1"]["width"] == 1000
    assert by_id["lazada_1_1"]["height"] == 1000
    assert by_id["amazon_white_85"]["background_rgb"] == [255, 255, 255]
    assert by_id["amazon_white_85"]["subject_area_ratio"] == 0.85
