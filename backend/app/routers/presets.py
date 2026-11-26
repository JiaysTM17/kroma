from fastapi import APIRouter, HTTPException
from typing import List
from ..database import get_connection
from ..models.preset import MarketplacePreset

router = APIRouter(prefix="/presets", tags=["Marketplace Presets"])

@router.get("", response_model=List[MarketplacePreset])
def list_presets():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM presets ORDER BY marketplace ASC, name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@router.get("/{preset_id}", response_model=MarketplacePreset)
def get_preset(preset_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM presets WHERE id = ?", (preset_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Preset không tồn tại")
    return dict(row)
