import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from typing import List
from ..database import get_connection
from ..models.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("", response_model=List[ProjectResponse])
def list_projects():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append(ProjectResponse(
            id=r["id"],
            name=r["name"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            schema_version=r["schema_version"],
            manifest=json.loads(r["manifest_json"])
        ))
    return results

@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate):
    proj_id = f"proj_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    manifest = data.manifest or {
        "images": [],
        "layers": [],
        "selected_preset": "shopee_square",
        "shadow": {"enabled": False, "type": "drop", "blur": 12, "opacity": 0.4}
    }
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO projects (id, name, created_at, updated_at, schema_version, manifest_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (proj_id, data.name, now, now, 1, json.dumps(manifest)))
    conn.commit()
    conn.close()
    
    return ProjectResponse(
        id=proj_id,
        name=data.name,
        created_at=now,
        updated_at=now,
        schema_version=1,
        manifest=manifest
    )

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")
    
    return ProjectResponse(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        schema_version=row["schema_version"],
        manifest=json.loads(row["manifest_json"])
    )

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, data: ProjectCreate):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")
    
    manifest_json = json.dumps(data.manifest) if data.manifest else "{}"
    cursor.execute("""
        UPDATE projects SET name = ?, updated_at = ?, manifest_json = ?
        WHERE id = ?
    """, (data.name, now, manifest_json, project_id))
    conn.commit()
    conn.close()
    
    return get_project(project_id)

@router.delete("/{project_id}")
def delete_project(project_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": project_id}
