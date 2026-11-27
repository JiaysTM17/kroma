from __future__ import annotations

import io
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings


def _png_bytes(width: int = 32, height: int = 32) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (width, height), (79, 70, 229, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _create_project(client: TestClient, name: str = "Proofing Project") -> dict:
    res = client.post("/v1/projects", json={"name": name})
    assert res.status_code == 201
    return res.json()


def test_proofing_session_workflow(client: TestClient) -> None:
    proj = _create_project(client, "Bộ sưu tập Đầm dạ hội")
    project_id = proj["id"]

    session_payload = {
        "project_id": project_id,
        "title": "Bộ sưu tập Đầm dạ hội - Duyệt bản in Shopee",
        "client_name": "Fashion Store VIP",
        "allow_comments": True,
    }
    res = client.post("/api/v1/proofing", json=session_payload)
    assert res.status_code == 201
    session = res.json()
    session_id = session["id"]
    assert session["status"] == "pending"
    assert session["feedback"] == []
    assert session["comments"] == []
    assert session["project_revision_id"] == proj["state"]["revision_id"]
    assert session["revision_stale"] is False

    feedback_1 = {
        "author": "Chị Mai (Brand Manager)",
        "action": "request_change",
        "comment": "Chỉnh viền cổ áo mềm hơn một chút, bóng sàn tăng độ blur lên 18px",
        "pin_x": 0.45,
        "pin_y": 0.32,
    }
    res_fb1 = client.post(f"/api/v1/proofing/{session_id}/feedback", json=feedback_1)
    assert res_fb1.status_code == 200
    updated_session = res_fb1.json()
    assert updated_session["status"] == "revision_requested"
    assert len(updated_session["feedback"]) == 1
    assert updated_session["feedback"][0]["author"] == "Chị Mai (Brand Manager)"
    assert updated_session["feedback"][0]["pin_x"] == 0.45
    assert updated_session["comments"][0]["body"] == feedback_1["comment"]
    assert updated_session["comments"][0]["comment"] == feedback_1["comment"]

    feedback_2 = {
        "author": "Chị Mai (Brand Manager)",
        "action": "approve",
        "comment": "Đã sửa hoàn hảo, duyệt xuất ảnh chuẩn sàn Shopee!",
    }
    res_fb2 = client.post(f"/api/v1/proofing/{session_id}/feedback", json=feedback_2)
    assert res_fb2.status_code == 200
    approved_session = res_fb2.json()
    assert approved_session["status"] == "approved"
    assert approved_session["approved_by"] == "Chị Mai (Brand Manager)"
    assert approved_session["approved_at"] is not None
    assert len(approved_session["feedback"]) == 2


def test_proofing_project_asset_validation_and_listing(client: TestClient) -> None:
    missing_res = client.post(
        "/v1/proofing",
        json={"project_id": "nonexistent-proj", "title": "Should 404"},
    )
    assert missing_res.status_code == 404
    assert missing_res.json()["code"] == "NOT_FOUND"

    proj_a = _create_project(client, "Project A")
    proj_b = _create_project(client, "Project B")
    asset_b = client.post(
        f"/v1/projects/{proj_b['id']}/assets",
        files={"file": ("b.png", _png_bytes(), "image/png")},
    ).json()

    # Cross-project asset_id -> 422
    mismatch_res = client.post(
        "/v1/proofing",
        json={
            "project_id": proj_a["id"],
            "asset_id": asset_b["id"],
            "title": "Cross Project Asset",
        },
    )
    assert mismatch_res.status_code == 422
    assert mismatch_res.json()["code"] == "VALIDATION_ERROR"

    # Missing asset_id -> 404
    missing_asset_res = client.post(
        "/v1/proofing",
        json={
            "project_id": proj_a["id"],
            "asset_id": "missing-asset",
            "title": "Missing Asset",
        },
    )
    assert missing_asset_res.status_code == 404

    asset_a = client.post(
        f"/v1/projects/{proj_a['id']}/assets",
        files={"file": ("a.png", _png_bytes(), "image/png")},
    ).json()
    created = client.post(
        "/v1/proofing",
        json={
            "project_id": proj_a["id"],
            "asset_id": asset_a["id"],
            "title": "Hero Check",
            "client_name": "Acme Brand",
        },
    )
    assert created.status_code == 201
    detail = created.json()
    assert detail["asset_id"] == asset_a["id"]
    assert detail["asset_url"] == f"/v1/assets/{asset_a['id']}/file"

    listed = client.get(f"/v1/projects/{proj_a['id']}/proofing")
    assert listed.status_code == 200
    list_body = listed.json()
    assert list_body["total"] == 1
    assert list_body["sessions"][0]["id"] == detail["id"]
    assert list_body["sessions"][0]["asset_url"] == f"/v1/assets/{asset_a['id']}/file"


def test_proofing_pin_bounds_booleans_and_allow_comments(client: TestClient) -> None:
    proj = _create_project(client, "Pin Validation")
    session = client.post(
        "/v1/proofing",
        json={
            "project_id": proj["id"],
            "title": "Read-only comments check",
            "allow_comments": False,
        },
    ).json()
    sid = session["id"]

    # allow_comments=False blocks 'comment' with 403
    blocked = client.post(
        f"/v1/proofing/{sid}/comments",
        json={"author": "Client", "action": "comment", "body": "Please tweak"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "FORBIDDEN"

    # allow_comments=False still permits 'request_change' / 'approve'
    req_change = client.post(
        f"/v1/proofing/{sid}/feedback",
        json={"author": "Client", "action": "request_change", "comment": "Make brighter", "pin_x": 0.0, "pin_y": 1.0},
    )
    assert req_change.status_code == 200
    assert req_change.json()["status"] == "revision_requested"

    # Invalid pin coordinates & booleans -> 422 unified envelope
    for bad_payload in (
        {"author": "Client", "action": "request_change", "comment": "bad", "pin_x": -0.01, "pin_y": 0.5},
        {"author": "Client", "action": "request_change", "comment": "bad", "pin_x": 0.5, "pin_y": 1.01},
        {"author": "Client", "action": "request_change", "comment": "bad", "pin_x": 0.5},
        {"author": "Client", "action": "request_change", "comment": "bad", "pin_x": True, "pin_y": 0.5},
        {"author": "Client", "action": "request_change", "comment": "bad", "pin_x": 0.5, "pin_y": False},
    ):
        bad_res = client.post(f"/v1/proofing/{sid}/feedback", json=bad_payload)
        assert bad_res.status_code == 422
        body = bad_res.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert "detail" not in body


def test_proofing_comments_crud_decisions_and_gone_states(
    client: TestClient, test_settings: Settings
) -> None:
    proj = _create_project(client, "Comment & Decision Lifecycle")
    created = client.post(
        "/v1/proofing",
        json={"project_id": proj["id"], "title": "Lifecycle Proof", "expires_hours": 24},
    ).json()
    sid = created["id"]

    # Add comment via /comments alias
    add_res = client.post(
        f"/v1/proofing/{sid}/comments",
        json={"author": "Designer", "body": "Initial pin note", "pin_x": 0.25, "pin_y": 0.75},
    )
    assert add_res.status_code == 200
    after_add = add_res.json()
    assert after_add["status"] == "in_review"
    cid = after_add["comments"][0]["id"]

    # PATCH comment: edit body + resolve
    patch_res = client.patch(
        f"/v1/proofing/{sid}/comments/{cid}",
        json={"body": "Updated pin note", "resolved": True, "resolved_by": "Lead"},
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["body"] == "Updated pin note"
    assert patched["comment"] == "Updated pin note"
    assert patched["resolved"] is True
    assert patched["resolved_by"] == "Lead"
    assert patched["resolved_at"] is not None

    # Unresolve comment
    unresolve_res = client.patch(
        f"/v1/proofing/{sid}/comments/{cid}",
        json={"resolved": False},
    )
    assert unresolve_res.status_code == 200
    assert unresolve_res.json()["resolved"] is False
    assert unresolve_res.json()["resolved_at"] is None

    # DELETE comment
    del_res = client.delete(f"/v1/proofing/{sid}/comments/{cid}")
    assert del_res.status_code == 200
    assert del_res.json() == {"deleted": True, "comment_id": cid}
    assert len(client.get(f"/v1/proofing/{sid}").json()["comments"]) == 0

    # Decisions: archive -> 409 on feedback/approve -> reopen -> approve -> revoke -> 410
    arch_res = client.post(
        f"/v1/proofing/{sid}/decision",
        json={"actor": "Owner", "decision": "archive", "note": "Archiving temporarily"},
    )
    assert arch_res.status_code == 200
    assert arch_res.json()["status"] == "archived"

    archived_fb = client.post(
        f"/v1/proofing/{sid}/feedback",
        json={"author": "Client", "action": "comment", "comment": "Too late"},
    )
    assert archived_fb.status_code == 409
    assert archived_fb.json()["code"] == "CONFLICT"

    reopen_res = client.post(
        f"/v1/proofing/{sid}/decision",
        json={"actor": "Owner", "decision": "reopen"},
    )
    assert reopen_res.status_code == 200
    assert reopen_res.json()["status"] == "pending"

    revoked_res = client.post(
        f"/v1/proofing/{sid}/decision",
        json={"actor": "Owner", "decision": "revoke", "note": "Link leaked"},
    )
    assert revoked_res.status_code == 200
    assert revoked_res.json()["revoked_at"] is not None

    # GET remains 200, mutations return 410 GONE
    assert client.get(f"/v1/proofing/{sid}").status_code == 200
    gone_fb = client.post(
        f"/v1/proofing/{sid}/feedback",
        json={"author": "Client", "action": "comment", "comment": "After revoke"},
    )
    assert gone_fb.status_code == 410
    assert gone_fb.json()["code"] == "GONE"

    gone_dec = client.post(
        f"/v1/proofing/{sid}/decision",
        json={"actor": "Owner", "decision": "approve"},
    )
    assert gone_dec.status_code == 410

    # Expired session also returns 410 GONE on mutations
    s2 = client.post(
        "/v1/proofing",
        json={"project_id": proj["id"], "title": "Expiry Test", "expires_hours": 1},
    ).json()
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(test_settings.sqlite_path) as conn:
        conn.execute(
            "UPDATE proofing_sessions SET expires_at = ? WHERE id = ?;",
            (past_iso, s2["id"]),
        )
        conn.commit()
    exp_res = client.post(
        f"/v1/proofing/{s2['id']}/feedback",
        json={"author": "Client", "action": "approve", "comment": "Expired"},
    )
    assert exp_res.status_code == 410
    assert exp_res.json()["code"] == "GONE"


def test_proofing_br14_revision_invalidation_on_project_state_update(
    client: TestClient,
) -> None:
    proj = _create_project(client, "BR14 Revision Binding")
    project_id = proj["id"]
    rev_1 = proj["state"]["revision_id"]

    session = client.post(
        "/v1/proofing",
        json={"project_id": project_id, "title": "Approve Before Edit"},
    ).json()
    sid = session["id"]
    assert session["project_revision_id"] == rev_1
    assert session["revision_stale"] is False

    approved = client.post(
        f"/v1/proofing/{sid}/decision",
        json={"actor": "Brand Lead", "decision": "approve", "note": "Looks great"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "Brand Lead"

    # Mutate project state -> advances revision_id -> atomically invalidates approved session
    state_update = client.put(
        f"/v1/projects/{project_id}/state",
        json={
            "state": {"commands": [{"type": "exposure", "value": 0.25}]},
            "expected_revision_id": rev_1,
        },
    )
    assert state_update.status_code == 200
    rev_2 = state_update.json()["revision_id"]
    assert rev_2 != rev_1

    refreshed = client.get(f"/v1/proofing/{sid}")
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["status"] == "pending"
    assert body["approved_by"] is None
    assert body["approved_at"] is None
    assert body["revision_stale"] is True
    event_types = [ev["event_type"] for ev in body["events"]]
    assert "project_revision_updated" in event_types
    inv_event = next(ev for ev in body["events"] if ev["event_type"] == "project_revision_updated")
    assert inv_event["from_status"] == "approved"
    assert inv_event["to_status"] == "pending"
    assert inv_event["payload"]["new_revision_id"] == rev_2
