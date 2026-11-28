from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import (
    AssetKind,
    BatchItemStatus,
    BatchStatus,
    ImageMime,
    MarketplaceId,
    ProofingAction,
    ProofingStatus,
)


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    description: str
    active_variant: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Asset:
    id: str
    project_id: str
    kind: AssetKind
    filename: str
    mime_type: ImageMime
    sha256: str
    byte_size: int
    width: int
    height: int
    exif_orientation: int
    storage_key: str
    is_readonly: bool
    created_at: str
    parent_asset_id: str | None = None
    variant: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""


@dataclass(frozen=True)
class ProjectState:
    project_id: str
    schema_version: int
    revision_id: str
    active_variant: str
    state: dict[str, Any]
    updated_at: str


@dataclass(frozen=True)
class SafeZone:
    top: float
    right: float
    bottom: float
    left: float


@dataclass(frozen=True)
class MarketplacePreset:
    id: str
    marketplace: MarketplaceId
    name_en: str
    name_vi: str
    version: str
    aspect_ratio: str
    width: int
    height: int
    formats: tuple[str, ...]
    background_rgb: tuple[int, int, int] | None
    subject_area_ratio: float | None
    safe_zone: SafeZone | None
    editable: bool = True
    rule_description_en: str = ""
    rule_description_vi: str = ""
    is_system: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class BatchAdjustments:
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 1.0
    exposure: float | None = None


@dataclass(frozen=True)
class BatchRecipeInput:
    preset_id: str
    format: str | None = None
    quality: int = 90
    background_rgb: tuple[int, int, int] | None = None
    subject_area_ratio: float | None = None
    include_shadow: bool | None = None
    watermark_text: str | None = None


@dataclass(frozen=True)
class BatchJobItem:
    id: str
    job_id: str
    seq: int
    asset_id: str
    source_asset_id: str
    preset_id: str
    preset_version: str
    format: str
    quality: int
    recipe_snapshot: dict[str, Any]
    status: BatchItemStatus
    output_filename: str | None = None
    output_byte_size: int = 0
    output_width: int = 0
    output_height: int = 0
    error_code: str | None = None
    error_message: str | None = None
    attempts: int = 0
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True)
class BatchJob:
    id: str
    project_id: str
    status: BatchStatus
    total_items: int
    completed_items: int
    failed_items: int
    progress: float
    zip_filename: str | None = None
    error_message: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str = ""


@dataclass(frozen=True)
class ProofingComment:
    id: str
    session_id: str
    author: str
    action: ProofingAction
    body: str
    pin_x: float | None = None
    pin_y: float | None = None
    resolved: bool = False
    resolved_by: str | None = None
    resolved_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class ProofingEvent:
    id: str
    session_id: str
    actor: str
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    note: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass(frozen=True)
class ProofingSession:
    id: str
    project_id: str
    asset_id: str | None
    project_revision_id: str | None
    title: str
    client_name: str | None
    status: ProofingStatus
    allow_comments: bool
    approved_by: str | None = None
    approved_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    comments: tuple[ProofingComment, ...] = ()
    events: tuple[ProofingEvent, ...] = ()


@dataclass(frozen=True)
class ComplianceCheckResult:
    check_id: str
    title: str
    status: str  # "pass" | "warn" | "fail"
    score: float  # 0.0 - 100.0
    message: str
    expected: str
    actual: str


@dataclass(frozen=True)
class MarketplacePreFlightReport:
    marketplace: str
    preset_id: str
    is_compliant: bool
    overall_score: float  # 0.0 - 100.0
    checks: list[ComplianceCheckResult]
    recommended_actions: list[str]

