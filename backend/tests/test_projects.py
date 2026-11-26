from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_project_crud_lifecycle():
    # 1. Create project
    create_payload = {
        "name": "Giày Sneaker Collection Shopee",
        "manifest": {
            "images": ["img_01.jpg"],
            "selected_preset": "shopee_square",
            "shadow": {"enabled": True, "type": "drop", "blur": 14}
        }
    }
    res_create = client.post("/api/v1/projects", json=create_payload)
    assert res_create.status_code == 201
    proj_data = res_create.json()
    proj_id = proj_data["id"]
    assert proj_data["name"] == "Giày Sneaker Collection Shopee"
    assert proj_data["manifest"]["shadow"]["enabled"] is True
    
    # 2. Get project
    res_get = client.get(f"/api/v1/projects/{proj_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == proj_id
    
    # 3. Update project
    update_payload = {
        "name": "Giày Sneaker Collection Shopee (Đã duyệt)",
        "manifest": {
            "images": ["img_01.jpg", "img_02.jpg"],
            "selected_preset": "shopee_square",
            "shadow": {"enabled": True, "type": "floor", "blur": 20}
        }
    }
    res_update = client.put(f"/api/v1/projects/{proj_id}", json=update_payload)
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "Giày Sneaker Collection Shopee (Đã duyệt)"
    assert res_update.json()["manifest"]["shadow"]["type"] == "floor"
    
    # 4. List projects contains new project
    res_list = client.get("/api/v1/projects")
    assert res_list.status_code == 200
    ids = [p["id"] for p in res_list.json()]
    assert proj_id in ids
    
    # 5. Delete project
    res_del = client.delete(f"/api/v1/projects/{proj_id}")
    assert res_del.status_code == 200
    assert client.get(f"/api/v1/projects/{proj_id}").status_code == 404
