from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, BeforeValidator, Field

from app.api.deps import get_asset_service, get_project_service
from app.api.v1.assets import AssetResponse
from app.domain.models import Project, ProjectState
from app.services.asset_service import AssetService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Boolean value is not allowed for numeric field")
    return value


NoBoolInt = Annotated[int, BeforeValidator(_reject_bool)]


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    active_variant: str = Field(default="default", max_length=64)


class UpdateProjectStateRequest(BaseModel):
    state: dict[str, Any]
    active_variant: str | None = Field(default=None, max_length=64)
    expected_revision_id: str | None = Field(default=None, max_length=128)
    schema_version: NoBoolInt = Field(default=1, ge=1)


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    active_variant: str
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, project: Project) -> ProjectResponse:
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            active_variant=project.active_variant,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class ProjectStateResponse(BaseModel):
    project_id: str
    schema_version: int
    revision_id: str
    active_variant: str
    state: dict[str, Any]
    updated_at: str

    @classmethod
    def from_domain(cls, state: ProjectState) -> ProjectStateResponse:
        return cls(
            project_id=state.project_id,
            schema_version=state.schema_version,
            revision_id=state.revision_id,
            active_variant=state.active_variant,
            state=state.state,
            updated_at=state.updated_at,
        )


class ProjectDetailResponse(ProjectResponse):
    state: ProjectStateResponse
    assets: list[AssetResponse]


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class DeleteProjectResponse(BaseModel):
    deleted: bool
    project_id: str


@router.get("", response_model=ProjectListResponse)
def list_projects(
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectListResponse:
    projects = project_service.list_projects()
    items = [ProjectResponse.from_domain(project) for project in projects]
    return ProjectListResponse(
        projects=items,
        total=len(items),
    )


@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    project = project_service.create_project(
        name=body.name,
        description=body.description,
        active_variant=body.active_variant,
    )
    state = project_service.get_project_state(project.id)
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        active_variant=project.active_variant,
        created_at=project.created_at,
        updated_at=project.updated_at,
        state=ProjectStateResponse.from_domain(state),
        assets=[],
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    asset_service: AssetService = Depends(get_asset_service),
) -> ProjectDetailResponse:
    project = project_service.get_project(project_id)
    state = project_service.get_project_state(project_id)
    assets = asset_service.list_project_assets(project_id)
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        active_variant=project.active_variant,
        created_at=project.created_at,
        updated_at=project.updated_at,
        state=ProjectStateResponse.from_domain(state),
        assets=[AssetResponse.from_domain(asset) for asset in assets],
    )


@router.delete("/{project_id}", response_model=DeleteProjectResponse)
def delete_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
) -> DeleteProjectResponse:
    project_service.delete_project(project_id)
    return DeleteProjectResponse(deleted=True, project_id=project_id)


@router.get("/{project_id}/state", response_model=ProjectStateResponse)
def get_project_state(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectStateResponse:
    state = project_service.get_project_state(project_id)
    return ProjectStateResponse.from_domain(state)


@router.put("/{project_id}/state", response_model=ProjectStateResponse)
def update_project_state(
    project_id: str,
    body: UpdateProjectStateRequest,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectStateResponse:
    updated = project_service.update_project_state(
        project_id=project_id,
        state_payload=body.state,
        active_variant=body.active_variant,
        expected_revision_id=body.expected_revision_id,
        schema_version=body.schema_version,
    )
    return ProjectStateResponse.from_domain(updated)
