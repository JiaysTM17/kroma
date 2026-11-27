from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_settings
from app.core.config import Settings

from ..database import get_connection
from ..models.proofing import (
    ProofingFeedbackSubmit,
    ProofingSessionCreate,
    ProofingSessionResponse,
)

router = APIRouter(prefix="/proofing", tags=["Client Proofing"])


@router.post("", response_model=ProofingSessionResponse, status_code=201)
def create_proofing_session(
    data: ProofingSessionCreate,
    settings: Settings = Depends(get_settings),
):
    session_id = f"proof_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO proofing_sessions (id, project_id, title, client_name, status, created_at, allow_comments, feedback_json)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, '[]')
            """,
            (
                session_id,
                data.project_id,
                data.title,
                data.client_name,
                now,
                1 if data.allow_comments else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return ProofingSessionResponse(
        id=session_id,
        project_id=data.project_id,
        title=data.title,
        client_name=data.client_name,
        status="pending",
        created_at=now,
        allow_comments=data.allow_comments,
        feedback=[],
    )


@router.get("/{session_id}", response_model=ProofingSessionResponse)
def get_proofing_session(
    session_id: str,
    settings: Settings = Depends(get_settings),
):
    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM proofing_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Phiên duyệt ảnh không tồn tại")

    return ProofingSessionResponse(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        client_name=row["client_name"],
        status=row["status"],
        created_at=row["created_at"],
        allow_comments=bool(row["allow_comments"]),
        feedback=json.loads(row["feedback_json"]),
    )


@router.post("/{session_id}/feedback", response_model=ProofingSessionResponse)
def submit_feedback(
    session_id: str,
    data: ProofingFeedbackSubmit,
    settings: Settings = Depends(get_settings),
):
    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM proofing_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Phiên duyệt ảnh không tồn tại")

        current_feedback = json.loads(row["feedback_json"])
        now = datetime.now(timezone.utc).isoformat()
        new_item = {
            "id": f"fb_{uuid.uuid4().hex[:8]}",
            "author": data.author,
            "action": data.action,
            "comment": data.comment,
            "pin_x": data.pin_x,
            "pin_y": data.pin_y,
            "created_at": now,
        }
        current_feedback.append(new_item)

        new_status = row["status"]
        if data.action == "approve":
            new_status = "approved"
        elif data.action == "request_change":
            new_status = "revision_requested"

        cursor.execute(
            """
            UPDATE proofing_sessions
            SET feedback_json = ?, status = ?
            WHERE id = ?
            """,
            (json.dumps(current_feedback), new_status, session_id),
        )
        conn.commit()
    finally:
        conn.close()

    return get_proofing_session(session_id, settings=settings)
