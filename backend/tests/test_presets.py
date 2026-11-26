from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

init_db()
client = TestClient(app)

def test_list_marketplace_presets():
    response = client.get("/api/v1/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) >= 5
    
    # Check that Shopee, TikTok Shop, and Amazon presets exist
    marketplaces = [p["marketplace"] for p in presets]
    assert "Shopee" in marketplaces
    assert "TikTok Shop" in marketplaces
    assert "Amazon" in marketplaces
    
    # Verify Amazon preset specs (85% subject scale, pure white bg)
    amazon_preset = next(p for p in presets if p["id"] == "amazon_hero")
    assert amazon_preset["subject_scale"] == 0.85
    assert amazon_preset["bg_color"] == "#FFFFFF"
    assert amazon_preset["width"] == 2000
    assert amazon_preset["height"] == 2000

def test_get_preset_by_id():
    response = client.get("/api/v1/presets/shopee_square")
    assert response.status_code == 200
    preset = response.json()
    assert preset["id"] == "shopee_square"
    assert preset["width"] == 1024
    assert preset["height"] == 1024
