from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_settings
from app.core.config import Settings

from ..database import get_connection
from ..models.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=list[ProjectResponse])
def list_projects(settings: Settings = Depends(get_settings)):
    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        rows = cursor.fetchall()
    finally:
        conn.close()

    results = []
    for r in rows:
        results.append(
            ProjectResponse(
                id=r["id"],
                name=r["name"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                schema_version=r["schema_version"],
                manifest=json.loads(r["manifest_json"]),
            )
        )
    return results


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    settings: Settings = Depends(get_settings),
):
    proj_id = f"proj_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    manifest = data.manifest or {
        "images": [],
        "layers": [],
        "selected_preset": "shopee_square",
        "shadow": {"enabled": False, "type": "drop", "blur": 12, "opacity": 0.4},
    }

    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (id, name, created_at, updated_at, schema_version, manifest_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (proj_id, data.name, now, now, 1, json.dumps(manifest)),
        )
        conn.commit()
    finally:
        conn.close()

    return ProjectResponse(
        id=proj_id,
        name=data.name,
        created_at=now,
        updated_at=now,
        schema_version=1,
        manifest=manifest,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    settings: Settings = Depends(get_settings),
):
    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    return ProjectResponse(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        schema_version=row["schema_version"],
        manifest=json.loads(row["manifest_json"]),
    )


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    data: ProjectCreate,
    settings: Settings = Depends(get_settings),
):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        manifest_json = json.dumps(data.manifest) if data.manifest else "{}"
        cursor.execute(
            """
            UPDATE projects SET name = ?, updated_at = ?, manifest_json = ?
            WHERE id = ?
            """,
            (data.name, now, manifest_json, project_id),
        )
        conn.commit()
    finally:
        conn.close()

    return get_project(project_id, settings=settings)


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    settings: Settings = Depends(get_settings),
):
    conn = get_connection(settings.sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "deleted", "id": project_id}
