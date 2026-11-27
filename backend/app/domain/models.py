from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import AssetKind, ImageMime, MarketplaceId


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
