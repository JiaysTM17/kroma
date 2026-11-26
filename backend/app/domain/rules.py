from __future__ import annotations

import re
import unicodedata
from typing import Any

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def validate_project_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Project name must be a string")
    normalized = unicodedata.normalize("NFC", name).strip()
    if not normalized:
        raise ValueError("Project name cannot be empty")
    if len(normalized) > 120:
        raise ValueError("Project name cannot exceed 120 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError("Project name contains invalid control characters")
    return normalized


def validate_project_description(description: str) -> str:
    if not isinstance(description, str):
        raise ValueError("Project description must be a string")
    normalized = unicodedata.normalize("NFC", description).strip()
    if len(normalized) > 1000:
        raise ValueError("Project description cannot exceed 1000 characters")
    return normalized


def _check_depth_and_types(value: Any, depth: int, max_depth: int) -> None:
    if depth > max_depth:
        raise ValueError(f"State payload exceeds maximum nesting depth of {max_depth}")
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, list):
        for item in value:
            _check_depth_and_types(item, depth + 1, max_depth)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("State object keys must be strings")
            _check_depth_and_types(item, depth + 1, max_depth)
        return
    raise ValueError(f"Unsupported value type in project state: {type(value).__name__}")


def validate_state_payload(
    state: dict[str, Any],
    schema_version: int = 1,
    max_depth: int = 16,
) -> None:
    if schema_version < 1:
        raise ValueError("schema_version must be >= 1")
    if not isinstance(state, dict):
        raise ValueError("State payload must be a JSON object")
    _check_depth_and_types(state, depth=1, max_depth=max_depth)


def check_revision_conflict(
    expected_revision_id: str | None,
    current_revision_id: str,
) -> bool:
    if expected_revision_id is None:
        return False
    return expected_revision_id != current_revision_id
