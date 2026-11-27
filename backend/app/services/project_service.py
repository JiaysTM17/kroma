from __future__ import annotations

import json
from typing import Any

from app.core.errors import ConflictError, NotFoundError, PayloadTooLargeError, ValidationAppError
from app.core.ids import new_id, utc_now_iso
from app.domain.enums import ErrorCode
from app.domain.models import Project, ProjectState
from app.domain.rules import (
    check_revision_conflict,
    validate_project_description,
    validate_project_name,
    validate_state_payload,
    validate_variant_name,
)
from app.storage.ports import BlobStorePort, DatabasePort


class ProjectService:
    def __init__(
        self,
        repo: DatabasePort,
        blob_store: BlobStorePort | None = None,
        max_state_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self._repo = repo
        self._blob_store = blob_store
        self._max_state_bytes = max_state_bytes

    def create_project(
        self,
        name: str,
        description: str = "",
        active_variant: str = "default",
    ) -> Project:
        try:
            clean_name = validate_project_name(name)
            clean_description = validate_project_description(description)
            clean_variant = validate_variant_name(active_variant, allow_default=True)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        now = utc_now_iso()
        project_id = new_id()
        project = Project(
            id=project_id,
            name=clean_name,
            description=clean_description,
            active_variant=clean_variant,
            created_at=now,
            updated_at=now,
        )
        initial_state = ProjectState(
            project_id=project_id,
            schema_version=1,
            revision_id=new_id(),
            active_variant=clean_variant,
            state={
                "commands": [],
                "layers": [],
                "variants": {clean_variant: {}},
                "shadow": None,
                "preset_id": None,
            },
            updated_at=now,
        )
        return self._repo.create_project(project, initial_state)

    def list_projects(self) -> list[Project]:
        return self._repo.list_projects()

    def get_project(self, project_id: str) -> Project:
        project = self._repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")
        return project

    def delete_project(self, project_id: str) -> None:
        storage_keys = self._repo.delete_project(project_id)
        if storage_keys is None:
            raise NotFoundError(f"Project '{project_id}' not found")
        if self._blob_store is not None:
            for key in storage_keys:
                if self._repo.count_storage_key_refs(key) == 0:
                    self._blob_store.delete_blob(key)

    def get_project_state(self, project_id: str) -> ProjectState:
        self.get_project(project_id)
        state = self._repo.get_project_state(project_id)
        if state is None:
            raise NotFoundError(f"State for project '{project_id}' not found")
        return state

    def update_project_state(
        self,
        project_id: str,
        state_payload: dict[str, Any],
        active_variant: str | None = None,
        expected_revision_id: str | None = None,
        schema_version: int = 1,
    ) -> ProjectState:
        current = self.get_project_state(project_id)
        if check_revision_conflict(expected_revision_id, current.revision_id):
            raise ConflictError(
                f"Revision conflict: expected '{expected_revision_id}', current is '{current.revision_id}'"
            )

        try:
            validate_state_payload(state_payload, schema_version=schema_version)
            variant = validate_variant_name(
                active_variant if active_variant is not None else current.active_variant,
                allow_default=True,
            )
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        serialized_bytes = len(
            json.dumps(state_payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        )
        if serialized_bytes > self._max_state_bytes:
            raise PayloadTooLargeError(
                f"Project state exceeds maximum size of {self._max_state_bytes} bytes",
                code=ErrorCode.PAYLOAD_TOO_LARGE,
            )

        next_state = ProjectState(
            project_id=project_id,
            schema_version=schema_version,
            revision_id=new_id(),
            active_variant=variant,
            state=state_payload,
            updated_at=utc_now_iso(),
        )
        return self._repo.put_project_state(next_state, expected_revision_id=expected_revision_id)
