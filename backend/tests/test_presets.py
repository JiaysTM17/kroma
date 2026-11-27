from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_marketplace_presets(client: TestClient) -> None:
    response = client.get("/api/v1/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) >= 5

    marketplaces = [p["marketplace"] for p in presets]
    assert "Shopee" in marketplaces
    assert "TikTok Shop" in marketplaces
    assert "Amazon" in marketplaces

    amazon_preset = next(p for p in presets if p["id"] == "amazon_hero")
    assert amazon_preset["subject_scale"] == 0.85
    assert amazon_preset["bg_color"] == "#FFFFFF"
    assert amazon_preset["width"] == 2000
    assert amazon_preset["height"] == 2000


def test_get_preset_by_id(client: TestClient) -> None:
    response = client.get("/api/v1/presets/shopee_square")
    assert response.status_code == 200
    preset = response.json()
    assert preset["id"] == "shopee_square"
    assert preset["width"] == 1024
    assert preset["height"] == 1024
