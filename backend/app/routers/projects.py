from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_project_service
from app.core.errors import NotFoundError
from app.services.project_service import ProjectService

from ..models.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


def _default_manifest() -> dict:
    return {
        "images": [],
        "layers": [],
        "selected_preset": "shopee_square",
        "shadow": {"enabled": False, "type": "drop", "blur": 12, "opacity": 0.4},
    }


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    project_service: ProjectService = Depends(get_project_service),
) -> list[ProjectResponse]:
    projects = project_service.list_projects()
    results: list[ProjectResponse] = []
    for proj in projects:
        try:
            state = project_service.get_project_state(proj.id)
            manifest = state.state
            schema_version = state.schema_version
        except NotFoundError:
            manifest = _default_manifest()
            schema_version = 1
        results.append(
            ProjectResponse(
                id=proj.id,
                name=proj.name,
                created_at=proj.created_at,
                updated_at=proj.updated_at,
                schema_version=schema_version,
                manifest=manifest,
            )
        )
    return results


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = project_service.create_project(name=data.name)
    manifest = data.manifest if data.manifest is not None else _default_manifest()
    state = project_service.update_project_state(
        project.id,
        state_payload=manifest,
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        updated_at=state.updated_at,
        schema_version=state.schema_version,
        manifest=state.state,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = project_service.get_project(project_id)
    state = project_service.get_project_state(project_id)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at,
        schema_version=state.schema_version,
        manifest=state.state,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    data: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = project_service.update_project_name(project_id, data.name)
    manifest = data.manifest if data.manifest is not None else {}
    state = project_service.update_project_state(
        project_id,
        state_payload=manifest,
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        updated_at=state.updated_at,
        schema_version=state.schema_version,
        manifest=state.state,
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
) -> dict[str, str]:
    try:
        project_service.delete_project(project_id)
    except NotFoundError:
        pass
    return {"status": "deleted", "id": project_id}
