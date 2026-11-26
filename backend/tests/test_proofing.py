from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_proofing_session_workflow():
    # 1. Create proofing session
    session_payload = {
        "project_id": "proj_demo_fashion",
        "title": "Bộ sưu tập Đầm dạ hội - Duyệt bản in Shopee",
        "client_name": "Fashion Store VIP",
        "allow_comments": True
    }
    res = client.post("/api/v1/proofing", json=session_payload)
    assert res.status_code == 201
    session = res.json()
    session_id = session["id"]
    assert session["status"] == "pending"
    assert len(session["feedback"]) == 0
    
    # 2. Submit change request feedback with pin coordinates
    feedback_1 = {
        "author": "Chị Mai (Brand Manager)",
        "action": "request_change",
        "comment": "Chỉnh viền cổ áo mềm hơn một chút, bóng sàn tăng độ blur lên 18px",
        "pin_x": 0.45,
        "pin_y": 0.32
    }
    res_fb1 = client.post(f"/api/v1/proofing/{session_id}/feedback", json=feedback_1)
    assert res_fb1.status_code == 200
    updated_session = res_fb1.json()
    assert updated_session["status"] == "revision_requested"
    assert len(updated_session["feedback"]) == 1
    assert updated_session["feedback"][0]["author"] == "Chị Mai (Brand Manager)"
    assert updated_session["feedback"][0]["pin_x"] == 0.45
    
    # 3. Submit approval feedback
    feedback_2 = {
        "author": "Chị Mai (Brand Manager)",
        "action": "approve",
        "comment": "Đã sửa hoàn hảo, duyệt xuất ảnh chuẩn sàn Shopee!"
    }
    res_fb2 = client.post(f"/api/v1/proofing/{session_id}/feedback", json=feedback_2)
    assert res_fb2.status_code == 200
    approved_session = res_fb2.json()
    assert approved_session["status"] == "approved"
    assert len(approved_session["feedback"]) == 2
