from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import get_asset_service, get_project_service
from app.domain.models import Asset, Project, ProjectState
from app.services.asset_service import AssetService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class UpdateProjectStateRequest(BaseModel):
    state: dict[str, Any]
    active_variant: str | None = Field(default=None, max_length=64)
    expected_revision_id: str | None = Field(default=None, max_length=128)
    schema_version: int = Field(default=1, ge=1)


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


class AssetSummaryResponse(BaseModel):
    asset_id: str
    project_id: str
    kind: str
    filename: str
    mime_type: str
    sha256: str
    byte_size: int
    width: int
    height: int
    exif_orientation: int
    is_readonly: bool
    created_at: str

    @classmethod
    def from_domain(cls, asset: Asset) -> AssetSummaryResponse:
        return cls(
            asset_id=asset.id,
            project_id=asset.project_id,
            kind=asset.kind.value,
            filename=asset.filename,
            mime_type=asset.mime_type.value,
            sha256=asset.sha256,
            byte_size=asset.byte_size,
            width=asset.width,
            height=asset.height,
            exif_orientation=asset.exif_orientation,
            is_readonly=asset.is_readonly,
            created_at=asset.created_at,
        )


class ProjectDetailResponse(ProjectResponse):
    assets: list[AssetSummaryResponse]


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]


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


@router.get("", response_model=ProjectListResponse)
def list_projects(
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectListResponse:
    projects = project_service.list_projects()
    return ProjectListResponse(
        items=[ProjectResponse.from_domain(project) for project in projects]
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = project_service.create_project(name=body.name, description=body.description)
    return ProjectResponse.from_domain(project)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    asset_service: AssetService = Depends(get_asset_service),
) -> ProjectDetailResponse:
    project = project_service.get_project(project_id)
    assets = asset_service.list_project_assets(project_id)
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        active_variant=project.active_variant,
        created_at=project.created_at,
        updated_at=project.updated_at,
        assets=[AssetSummaryResponse.from_domain(asset) for asset in assets],
    )


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
