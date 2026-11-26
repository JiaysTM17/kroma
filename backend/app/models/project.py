from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ImageTransform(BaseModel):
    crop: Optional[Dict[str, float]] = None
    rotation: float = 0.0
    flip_h: bool = False
    flip_v: bool = False
    brightness: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0

class ShadowParams(BaseModel):
    enabled: bool = False
    type: str = "drop" # drop, floor, reflection
    blur: float = 12.0
    opacity: float = 0.4
    angle: float = 90.0
    distance: float = 16.0
    color: str = "#000000"

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    manifest: Optional[Dict[str, Any]] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    schema_version: int = 1
    manifest: Dict[str, Any]
