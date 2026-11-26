from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ExportRecipe(BaseModel):
    preset_id: str
    format: str = "JPEG"
    quality: int = 90
    include_shadow: bool = True
    watermark_text: Optional[str] = None

class BatchExportRequest(BaseModel):
    project_id: str
    recipes: List[ExportRecipe]

class BatchExportResponse(BaseModel):
    export_id: str
    total_images: int
    download_url: str
    status: str
