from __future__ import annotations

from fastapi.testclient import TestClient


def test_project_crud_and_state_round_trip(client: TestClient) -> None:
    empty_list = client.get("/v1/projects")
    assert empty_list.status_code == 200
    assert empty_list.json() == {"items": []}

    created_res = client.post(
        "/v1/projects",
        json={"name": "Bộ ảnh nước hoa", "description": "Chụp nền trắng"},
    )
    assert created_res.status_code == 201
    created = created_res.json()
    project_id = created["id"]
    assert created["name"] == "Bộ ảnh nước hoa"
    assert created["active_variant"] == "default"

    list_res = client.get("/v1/projects")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == project_id

    detail_res = client.get(f"/v1/projects/{project_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["assets"] == []

    state_res = client.get(f"/v1/projects/{project_id}/state")
    assert state_res.status_code == 200
    initial_rev = state_res.json()["revision_id"]

    updated_res = client.put(
        f"/v1/projects/{project_id}/state",
        json={
            "state": {
                "commands": [{"id": "cmd-1", "type": "backdrop", "value": "white"}],
                "layers": [{"id": "orig", "opacity": 1.0}],
            },
            "active_variant": "shopee_1_1",
            "expected_revision_id": initial_rev,
        },
    )
    assert updated_res.status_code == 200
    updated_data = updated_res.json()
    assert updated_data["revision_id"] != initial_rev
    assert updated_data["active_variant"] == "shopee_1_1"
    assert updated_data["state"]["commands"][0]["id"] == "cmd-1"

    # Stale expected_revision_id returns 409 unified error JSON
    conflict_res = client.put(
        f"/v1/projects/{project_id}/state",
        json={
            "state": {"commands": []},
            "expected_revision_id": initial_rev,
        },
    )
    assert conflict_res.status_code == 409
    err = conflict_res.json()
    assert err["code"] == "CONFLICT"
    assert "correlation_id" in err
    assert err["retryable"] is False


def test_missing_project_returns_unified_404(client: TestClient) -> None:
    res = client.get("/v1/projects/non-existent-id")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["retryable"] is False
    assert isinstance(body["correlation_id"], str)
