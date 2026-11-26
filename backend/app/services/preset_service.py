from __future__ import annotations

from app.domain.enums import MarketplaceId
from app.domain.models import MarketplacePreset, SafeZone

_DEFAULT_PRESETS: tuple[MarketplacePreset, ...] = (
    MarketplacePreset(
        id="shopee_1_1",
        marketplace=MarketplaceId.SHOPEE,
        name_en="Shopee (1:1 · 1024×1024)",
        name_vi="Shopee (1:1 · 1024×1024)",
        version="1.0.0",
        aspect_ratio="1:1",
        width=1024,
        height=1024,
        formats=("webp", "jpeg"),
        background_rgb=None,
        subject_area_ratio=None,
        safe_zone=None,
        editable=True,
    ),
    MarketplacePreset(
        id="tiktok_3_4",
        marketplace=MarketplaceId.TIKTOK_SHOP,
        name_en="TikTok Shop Vertical (3:4 · 1200×1600)",
        name_vi="TikTok Shop Dọc (3:4 · 1200×1600)",
        version="1.0.0",
        aspect_ratio="3:4",
        width=1200,
        height=1600,
        formats=("webp", "jpeg", "png"),
        background_rgb=None,
        subject_area_ratio=None,
        safe_zone=SafeZone(top=0.08, right=0.14, bottom=0.22, left=0.06),
        editable=True,
    ),
    MarketplacePreset(
        id="tiktok_1_1",
        marketplace=MarketplaceId.TIKTOK_SHOP,
        name_en="TikTok Shop Square (1:1 · 1024×1024)",
        name_vi="TikTok Shop Vuông (1:1 · 1024×1024)",
        version="1.0.0",
        aspect_ratio="1:1",
        width=1024,
        height=1024,
        formats=("webp", "jpeg", "png"),
        background_rgb=None,
        subject_area_ratio=None,
        safe_zone=SafeZone(top=0.06, right=0.06, bottom=0.14, left=0.06),
        editable=True,
    ),
    MarketplacePreset(
        id="lazada_1_1",
        marketplace=MarketplaceId.LAZADA,
        name_en="Lazada (1:1 · 1000×1000)",
        name_vi="Lazada (1:1 · 1000×1000)",
        version="1.0.0",
        aspect_ratio="1:1",
        width=1000,
        height=1000,
        formats=("jpeg", "png", "webp"),
        background_rgb=None,
        subject_area_ratio=None,
        safe_zone=None,
        editable=True,
    ),
    MarketplacePreset(
        id="amazon_white_85",
        marketplace=MarketplaceId.AMAZON,
        name_en="Amazon / Google Shopping (Pure White 85%)",
        name_vi="Amazon / Google Shopping (Nền trắng 85%)",
        version="1.0.0",
        aspect_ratio="1:1",
        width=2000,
        height=2000,
        formats=("jpeg", "png"),
        background_rgb=(255, 255, 255),
        subject_area_ratio=0.85,
        safe_zone=None,
        editable=True,
    ),
)


class PresetService:
    def __init__(self, presets: tuple[MarketplacePreset, ...] = _DEFAULT_PRESETS) -> None:
        self._presets = presets

    def list_presets(self) -> list[MarketplacePreset]:
        return list(self._presets)
