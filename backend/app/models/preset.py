from pydantic import BaseModel
from typing import Optional

class MarketplacePreset(BaseModel):
    id: str
    name: str
    marketplace: str
    width: int
    height: int
    aspect_ratio: str
    bg_color: str
    subject_scale: float
    format: str
    description: Optional[str] = None
