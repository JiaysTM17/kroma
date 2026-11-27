from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image


def _png_bytes(color: tuple[int, int, int, int] = (200, 100, 50, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (24, 24), color=color).save(buf, format="PNG")
    return buf.getvalue()


def test_project_crud_and_state_round_trip(client: TestClient) -> None:
    empty_list = client.get("/v1/projects")
    assert empty_list.status_code == 200
    assert empty_list.json() == {"projects": [], "total": 0}

    created_res = client.post(
        "/v1/projects",
        json={"name": "Bộ ảnh nước hoa", "description": "Chụp nền trắng"},
    )
    assert created_res.status_code == 201
    created = created_res.json()
    project_id = created["id"]
    assert created["name"] == "Bộ ảnh nước hoa"
    assert created["active_variant"] == "default"
    assert created["assets"] == []
    assert created["state"]["project_id"] == project_id
    assert created["state"]["revision_id"]

    list_res = client.get("/v1/projects")
    assert list_res.status_code == 200
    list_body = list_res.json()
    assert list_body["total"] == 1
    items = list_body["projects"]
    assert len(items) == 1
    assert items[0]["id"] == project_id

    detail_res = client.get(f"/v1/projects/{project_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["assets"] == []
    assert detail["state"]["revision_id"] == created["state"]["revision_id"]

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


def test_delete_project_cascades_assets_and_blobs(client: TestClient) -> None:
    proj = client.post(
        "/v1/projects",
        json={"name": "Cascade Delete", "active_variant": "tiktok_3_4"},
    ).json()
    project_id = proj["id"]
    assert proj["active_variant"] == "tiktok_3_4"

    asset = client.post(
        f"/v1/projects/{project_id}/assets",
        files={"file": ("item.png", _png_bytes(), "image/png")},
    ).json()
    asset_id = asset["id"]

    detail = client.get(f"/v1/projects/{project_id}").json()
    assert len(detail["assets"]) == 1
    assert detail["assets"][0]["id"] == asset_id

    del_res = client.delete(f"/v1/projects/{project_id}")
    assert del_res.status_code == 200
    assert del_res.json() == {"deleted": True, "project_id": project_id}

    assert client.get(f"/v1/projects/{project_id}").status_code == 404
    assert client.get(f"/v1/assets/{asset_id}").status_code == 404
    assert client.get(f"/v1/assets/{asset_id}/file").status_code == 404
    assert client.delete(f"/v1/projects/{project_id}").status_code == 404


def test_missing_project_returns_unified_404(client: TestClient) -> None:
    res = client.get("/v1/projects/non-existent-id")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["retryable"] is False
    assert isinstance(body["correlation_id"], str)


def test_project_state_rejects_boolean_schema_version_with_unified_422(client: TestClient) -> None:
    proj = client.post("/v1/projects", json={"name": "Schema Bool Check"}).json()
    res = client.put(
        f"/v1/projects/{proj['id']}/state",
        json={"state": {"commands": []}, "schema_version": True},
    )
    assert res.status_code == 422
    body = res.json()
    assert "detail" not in body
    assert body["code"] == "VALIDATION_ERROR"
    assert body["retryable"] is False
    assert isinstance(body["correlation_id"], str)
