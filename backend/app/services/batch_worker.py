from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
import warnings
import zipfile
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.core.config import Settings
from app.core.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    SecurityError,
    ValidationAppError,
)
from app.core.ids import new_id, utc_now_iso
from app.core.security import assert_safe_relative_path, sanitize_upload_filename
from app.domain.enums import AssetKind, BatchItemStatus, BatchStatus, ErrorCode
from app.domain.models import (
    Asset,
    BatchAdjustments,
    BatchJob,
    BatchJobItem,
    BatchRecipeInput,
    MarketplacePreset,
)
from app.domain.rules import (
    derive_batch_status,
    validate_background_rgb,
    validate_batch_adjustments,
    validate_batch_asset_ids,
    validate_batch_format,
    validate_batch_quality,
    validate_subject_area_ratio,
    validate_watermark_text,
)
from app.storage.ports import BlobStorePort, DatabasePort

LEGACY_PRESET_ID_ALIASES: dict[str, str] = {
    "shopee_square": "shopee_1_1",
    "tiktok_shop_feed": "tiktok_3_4",
    "tiktok_shop_square": "tiktok_1_1",
    "lazada_square": "lazada_1_1",
    "amazon_hero": "amazon_white_85",
}

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PIL_LOCK = threading.Lock()


def validate_safe_archive_id(raw_id: str, label: str = "job_id") -> str:
    if not isinstance(raw_id, str) or not _SAFE_ID_RE.fullmatch(raw_id):
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            f"Invalid {label}: path segments or unsafe characters are forbidden",
            status_code=422,
        )
    return raw_id


def _load_watermark_font(font_size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for font_name in ("segoeui.ttf", "arial.ttf", "tahoma.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size=font_size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


def generate_synthetic_product_canvas(width: int = 512, height: int = 512) -> bytes:
    """Create a clean studio product RGBA PNG for assetless legacy export requests."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    pad_x = width // 5
    pad_y = height // 6
    draw.rounded_rectangle(
        (pad_x, pad_y, width - pad_x, height - pad_y),
        radius=max(16, width // 16),
        fill=(79, 70, 229, 255),
        outline=(49, 46, 129, 255),
        width=max(2, width // 128),
    )
    inner_x = width // 3
    inner_y = height // 3
    draw.ellipse(
        (inner_x, inner_y, width - inner_x, height - inner_y),
        fill=(255, 255, 255, 220),
    )
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def render_recipe_image(
    raw_bytes: bytes,
    snapshot: dict[str, Any],
    *,
    max_pixels: int = 50_000_000,
    max_dimension: int = 16_384,
) -> tuple[bytes, int, int]:
    """Render an input image into a MarketplacePreset-compliant output buffer via Pillow."""
    target_w = int(snapshot["width"])
    target_h = int(snapshot["height"])
    if (
        target_w <= 0
        or target_h <= 0
        or target_w > max_dimension
        or target_h > max_dimension
        or (target_w * target_h) > max_pixels
    ):
        raise ValidationAppError(
            f"Target dimensions ({target_w}x{target_h}) exceed safety bounds",
            code=ErrorCode.PIXEL_BOMB_DETECTED,
        )

    fmt = str(snapshot.get("format") or "webp").lower()
    if fmt == "jpg":
        fmt = "jpeg"
    quality = int(snapshot.get("quality") or 90)
    bg_raw = snapshot.get("background_rgb")
    bg_rgb: tuple[int, int, int] | None = (
        (int(bg_raw[0]), int(bg_raw[1]), int(bg_raw[2]))
        if isinstance(bg_raw, (list, tuple)) and len(bg_raw) == 3
        else None
    )
    subject_ratio_raw = snapshot.get("subject_area_ratio")
    subject_ratio = float(subject_ratio_raw) if subject_ratio_raw is not None else None
    safe_zone = snapshot.get("safe_zone")
    include_shadow = bool(snapshot.get("include_shadow", False))
    watermark_text = snapshot.get("watermark_text")
    adj = snapshot.get("adjustments") or {}

    with _PIL_LOCK:
        previous_max_pixels = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = max_pixels
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                try:
                    with Image.open(
                        io.BytesIO(raw_bytes), formats=["JPEG", "PNG", "WEBP"]
                    ) as opened:
                        opened.load()
                        im = ImageOps.exif_transpose(opened)
                        subject = im.convert("RGBA")
                except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
                    raise ValidationAppError(
                        "Source image exceeds pixel decompression safety limit",
                        code=ErrorCode.PIXEL_BOMB_DETECTED,
                    ) from exc
                except (OSError, SyntaxError, ValueError) as exc:
                    raise ValidationAppError(
                        f"Unable to decode source image: {exc}",
                        code=ErrorCode.CORRUPT_IMAGE,
                    ) from exc
        finally:
            Image.MAX_IMAGE_PIXELS = previous_max_pixels

    # Subject-only tonal adjustments before background compositing
    exposure = adj.get("exposure")
    if exposure is not None:
        brightness_factor = max(0.1, min(3.0, 2.0 ** (float(exposure) / 50.0)))
    else:
        brightness_factor = float(adj.get("brightness", 1.0))
    contrast_factor = float(adj.get("contrast", 1.0))
    saturation_factor = float(adj.get("saturation", 1.0))
    sharpness_factor = float(adj.get("sharpness", 1.0))

    if (
        abs(brightness_factor - 1.0) > 1e-4
        or abs(contrast_factor - 1.0) > 1e-4
        or abs(saturation_factor - 1.0) > 1e-4
        or abs(sharpness_factor - 1.0) > 1e-4
    ):
        rgb_part = subject.convert("RGB")
        alpha_part = subject.getchannel("A")
        if abs(brightness_factor - 1.0) > 1e-4:
            rgb_part = ImageEnhance.Brightness(rgb_part).enhance(brightness_factor)
        if abs(contrast_factor - 1.0) > 1e-4:
            rgb_part = ImageEnhance.Contrast(rgb_part).enhance(contrast_factor)
        if abs(saturation_factor - 1.0) > 1e-4:
            rgb_part = ImageEnhance.Color(rgb_part).enhance(saturation_factor)
        if abs(sharpness_factor - 1.0) > 1e-4:
            rgb_part = ImageEnhance.Sharpness(rgb_part).enhance(sharpness_factor)
        rgb_part.putalpha(alpha_part)
        subject = rgb_part

    # Fit within safe zone & subject_area_ratio
    if isinstance(safe_zone, dict):
        sz_l = int(round(target_w * float(safe_zone.get("left", 0.0))))
        sz_r = int(round(target_w * float(safe_zone.get("right", 0.0))))
        sz_t = int(round(target_h * float(safe_zone.get("top", 0.0))))
        sz_b = int(round(target_h * float(safe_zone.get("bottom", 0.0))))
    else:
        sz_l = sz_r = sz_t = sz_b = 0

    avail_w = max(1, target_w - sz_l - sz_r)
    avail_h = max(1, target_h - sz_t - sz_b)

    if subject_ratio is not None:
        box_w = min(avail_w, max(1, int(round(target_w * subject_ratio))))
        box_h = min(avail_h, max(1, int(round(target_h * subject_ratio))))
    else:
        box_w = avail_w
        box_h = avail_h

    src_w, src_h = subject.size
    scale = min(box_w / max(1, src_w), box_h / max(1, src_h))
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    resized = subject.resize((new_w, new_h), Image.Resampling.LANCZOS)

    paste_x = sz_l + (avail_w - new_w) // 2
    paste_y = sz_t + (avail_h - new_h) // 2

    if bg_rgb is not None:
        canvas_color = (bg_rgb[0], bg_rgb[1], bg_rgb[2], 255)
    elif fmt == "jpeg":
        canvas_color = (255, 255, 255, 255)
    else:
        canvas_color = (0, 0, 0, 0)

    canvas = Image.new("RGBA", (target_w, target_h), canvas_color)

    if include_shadow:
        shadow_layer = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_layer)
        sh_w = max(8, int(new_w * 0.82))
        sh_h = max(6, int(new_h * 0.08))
        cx = paste_x + new_w // 2
        x0 = max(0, cx - sh_w // 2)
        x1 = min(target_w, cx + sh_w // 2)
        y0 = min(max(0, target_h - sh_h - 1), paste_y + new_h - max(2, sh_h // 2))
        y1 = min(target_h, y0 + sh_h)
        if x1 > x0 and y1 > y0:
            sdraw.ellipse((x0, y0, x1, y1), fill=(15, 23, 42, 92))
            blur_radius = max(3, min(24, int(new_w * 0.025)))
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            canvas = Image.alpha_composite(canvas, shadow_layer)

    canvas.alpha_composite(resized, dest=(paste_x, paste_y))

    if watermark_text:
        wm_layer = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        wdraw = ImageDraw.Draw(wm_layer)
        font_size = max(14, min(64, int(min(target_w, target_h) * 0.03)))
        font = _load_watermark_font(font_size)
        bbox = wdraw.textbbox((0, 0), str(watermark_text), font=font)
        text_w = max(1, bbox[2] - bbox[0])
        text_h = max(1, bbox[3] - bbox[1])
        margin = max(12, int(min(target_w, target_h) * 0.02))
        wx = max(sz_l + 8, target_w - sz_r - margin - text_w)
        wy = max(sz_t + 8, target_h - sz_b - margin - text_h)

        if bg_rgb is not None:
            lum = 0.2126 * bg_rgb[0] + 0.7152 * bg_rgb[1] + 0.0722 * bg_rgb[2]
            ink = (255, 255, 255, 165) if lum < 128 else (15, 23, 42, 150)
        else:
            ink = (15, 23, 42, 160)
        wdraw.text((wx, wy), str(watermark_text), font=font, fill=ink)
        canvas = Image.alpha_composite(canvas, wm_layer)

    out = io.BytesIO()
    if fmt == "jpeg":
        canvas.convert("RGB").save(out, format="JPEG", quality=quality, optimize=True)
    elif fmt == "png":
        canvas.save(out, format="PNG", optimize=True)
    elif fmt == "webp":
        canvas.save(out, format="WEBP", quality=quality, method=4)
    else:
        raise ValidationAppError(f"Unsupported output format '{fmt}'")

    return out.getvalue(), target_w, target_h


def _build_recipe_snapshot(
    preset: MarketplacePreset,
    *,
    fmt: str,
    quality: int,
    bg_rgb: tuple[int, int, int] | None,
    subject_ratio: float | None,
    include_shadow: bool,
    watermark_text: str | None,
    adjustments: BatchAdjustments,
    prefer_ai_output: bool,
    output_preset_label: str | None = None,
) -> dict[str, Any]:
    return {
        "preset_id": preset.id,
        "output_preset_label": output_preset_label or preset.id,
        "preset_version": preset.version,
        "preset_name_en": preset.name_en,
        "preset_name_vi": preset.name_vi,
        "width": preset.width,
        "height": preset.height,
        "background_rgb": list(bg_rgb) if bg_rgb is not None else None,
        "subject_area_ratio": subject_ratio,
        "safe_zone": (
            {
                "top": preset.safe_zone.top,
                "right": preset.safe_zone.right,
                "bottom": preset.safe_zone.bottom,
                "left": preset.safe_zone.left,
            }
            if preset.safe_zone is not None
            else None
        ),
        "format": fmt,
        "quality": quality,
        "include_shadow": include_shadow,
        "watermark_text": watermark_text,
        "adjustments": {
            "brightness": adjustments.brightness,
            "contrast": adjustments.contrast,
            "saturation": adjustments.saturation,
            "sharpness": adjustments.sharpness,
            "exposure": adjustments.exposure,
        },
        "prefer_ai_output": prefer_ai_output,
    }


def _atomic_write_zip(
    zip_path: Path,
    exports_dir: Path,
    entries: list[tuple[str, bytes]],
) -> None:
    exports_dir.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=exports_dir,
            prefix=".tmp_zip_",
            suffix=".zip",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
        with zipfile.ZipFile(str(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for member_name, member_bytes in entries:
                zf.writestr(member_name, member_bytes)
        os.replace(tmp_path, zip_path)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


class BatchWorkerService:
    def __init__(
        self,
        repo: DatabasePort,
        blob_store: BlobStorePort,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._blob_store = blob_store
        self._settings = settings
        self._lock = threading.Lock()
        self._shutting_down = threading.Event()
        self._cancel_events: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[None]] = {}
        self._active_run_tokens: dict[str, str] = {}
        self._executor: ThreadPoolExecutor | None = None

    def _ensure_executor(self) -> ThreadPoolExecutor:
        with self._lock:
            if self._executor is None or self._shutting_down.is_set():
                self._shutting_down.clear()
                self._executor = ThreadPoolExecutor(
                    max_workers=max(1, self._settings.batch_max_workers),
                    thread_name_prefix="kroma-batch",
                )
            return self._executor

    def start(self) -> None:
        self._settings.exports_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_executor()
        unfinished = self._repo.list_unfinished_batch_jobs()
        now = utc_now_iso()
        for job in unfinished:
            if job.status == BatchStatus.CANCEL_REQUESTED:
                self._repo.finalize_batch_job(
                    job.id,
                    status=BatchStatus.CANCELLED,
                    zip_filename=None,
                    error_message="Job cancelled before shutdown",
                    completed_at=now,
                    updated_at=now,
                    cancel_pending_items=True,
                )
                self._cleanup_staging(job.id)
            else:
                if job.status == BatchStatus.RUNNING:
                    self._repo.reset_running_batch_items_to_pending(job.id, now)
                self._enqueue_job(job.id)

    def shutdown(self, wait: bool = True) -> None:
        self._shutting_down.set()
        with self._lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=wait, cancel_futures=False)

    def _get_cancel_event(self, job_id: str) -> threading.Event:
        with self._lock:
            ev = self._cancel_events.get(job_id)
            if ev is None:
                ev = threading.Event()
                self._cancel_events[job_id] = ev
            return ev

    def _enqueue_job(self, job_id: str) -> None:
        executor = self._ensure_executor()
        token = uuid.uuid4().hex
        with self._lock:
            ev = self._cancel_events.get(job_id)
            if ev is None:
                ev = threading.Event()
                self._cancel_events[job_id] = ev
            ev.clear()
            self._active_run_tokens[job_id] = token
            future = executor.submit(self._run_job, job_id, token)
            self._futures[job_id] = future

    def _cleanup_job_handles(self, job_id: str, run_token: str | None) -> None:
        with self._lock:
            current_token = self._active_run_tokens.get(job_id)
            if run_token is not None and current_token != run_token:
                return
            self._active_run_tokens.pop(job_id, None)
            self._futures.pop(job_id, None)
            self._cancel_events.pop(job_id, None)

    def _staging_dir(self, job_id: str) -> Path:
        return assert_safe_relative_path(f".staging/{job_id}", self._settings.exports_dir)

    def _cleanup_staging(self, job_id: str) -> None:
        try:
            staging = self._staging_dir(job_id)
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        except Exception:
            pass

    def _resolve_source_asset(
        self,
        project_id: str,
        asset: Asset,
        preset_id: str,
        prefer_ai_output: bool,
    ) -> Asset:
        if asset.kind != AssetKind.ORIGINAL or not prefer_ai_output:
            return asset
        ai_outputs = self._repo.list_project_assets(
            project_id,
            kind=AssetKind.AI_OUTPUT,
            parent_asset_id=asset.id,
        )
        if not ai_outputs:
            return asset
        matching_variant = [a for a in ai_outputs if a.variant == preset_id]
        candidates = matching_variant if matching_variant else ai_outputs
        candidates.sort(key=lambda a: (a.updated_at or a.created_at, a.created_at), reverse=True)
        return candidates[0]

    def submit_batch_job(
        self,
        *,
        project_id: str,
        asset_ids: list[str],
        recipes: list[BatchRecipeInput],
        include_shadow: bool = False,
        watermark_text: str | None = None,
        adjustments: BatchAdjustments | dict[str, Any] | None = None,
        prefer_ai_output: bool = True,
    ) -> tuple[BatchJob, list[BatchJobItem]]:
        project = self._repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")

        if not recipes:
            raise ValidationAppError("recipes must contain at least one recipe")
        if len(recipes) > self._settings.batch_max_recipes_per_job:
            raise ValidationAppError(
                f"recipes cannot exceed {self._settings.batch_max_recipes_per_job} per batch job"
            )

        try:
            clean_asset_ids = validate_batch_asset_ids(
                asset_ids, max_assets=self._settings.batch_max_assets_per_job
            )
            clean_adjustments = validate_batch_adjustments(adjustments)
            clean_job_watermark = validate_watermark_text(watermark_text)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        total_items = len(clean_asset_ids) * len(recipes)
        if total_items > self._settings.batch_max_items_per_job:
            raise ValidationAppError(
                f"Batch item count ({total_items}) exceeds maximum of {self._settings.batch_max_items_per_job}"
            )

        resolved_assets: list[Asset] = []
        for aid in clean_asset_ids:
            asset = self._repo.get_asset(aid)
            if asset is None:
                raise NotFoundError(f"Asset '{aid}' not found")
            if asset.project_id != project_id:
                raise ValidationAppError(
                    f"Asset '{aid}' does not belong to project '{project_id}'"
                )
            resolved_assets.append(asset)

        resolved_recipes: list[tuple[BatchRecipeInput, MarketplacePreset, str, int, tuple[int, int, int] | None, float | None, bool, str | None]] = []
        for recipe in recipes:
            preset = self._repo.get_preset(recipe.preset_id)
            if preset is None:
                raise NotFoundError(f"Preset '{recipe.preset_id}' not found")
            try:
                fmt = validate_batch_format(recipe.format, preset.formats)
                quality = validate_batch_quality(recipe.quality)
                bg_rgb = (
                    validate_background_rgb(recipe.background_rgb)
                    if recipe.background_rgb is not None
                    else preset.background_rgb
                )
                subject_ratio = (
                    validate_subject_area_ratio(recipe.subject_area_ratio)
                    if recipe.subject_area_ratio is not None
                    else preset.subject_area_ratio
                )
                eff_shadow = (
                    bool(recipe.include_shadow)
                    if recipe.include_shadow is not None
                    else bool(include_shadow)
                )
                eff_watermark = validate_watermark_text(
                    recipe.watermark_text
                    if recipe.watermark_text is not None
                    else clean_job_watermark
                )
            except ValueError as exc:
                raise ValidationAppError(str(exc)) from exc
            resolved_recipes.append(
                (recipe, preset, fmt, quality, bg_rgb, subject_ratio, eff_shadow, eff_watermark)
            )

        now = utc_now_iso()
        job_id = f"batch_{uuid.uuid4().hex[:12]}"
        items: list[BatchJobItem] = []
        seq = 0
        for asset in resolved_assets:
            stem = os.path.splitext(sanitize_upload_filename(asset.filename))[0] or "asset"
            for (
                _recipe,
                preset,
                fmt,
                quality,
                bg_rgb,
                subject_ratio,
                eff_shadow,
                eff_watermark,
            ) in resolved_recipes:
                seq += 1
                source_asset = self._resolve_source_asset(
                    project_id, asset, preset.id, prefer_ai_output
                )
                snapshot = _build_recipe_snapshot(
                    preset,
                    fmt=fmt,
                    quality=quality,
                    bg_rgb=bg_rgb,
                    subject_ratio=subject_ratio,
                    include_shadow=eff_shadow,
                    watermark_text=eff_watermark,
                    adjustments=clean_adjustments,
                    prefer_ai_output=prefer_ai_output,
                )
                ext = "jpg" if fmt == "jpeg" else fmt
                safe_preset = sanitize_upload_filename(preset.id).replace(".", "_")
                safe_version = sanitize_upload_filename(preset.version)
                output_filename = f"{seq:03d}_{stem}_{safe_preset}_v{safe_version}.{ext}"
                items.append(
                    BatchJobItem(
                        id=new_id(),
                        job_id=job_id,
                        seq=seq,
                        asset_id=asset.id,
                        source_asset_id=source_asset.id,
                        preset_id=preset.id,
                        preset_version=preset.version,
                        format=fmt,
                        quality=quality,
                        recipe_snapshot=snapshot,
                        status=BatchItemStatus.PENDING,
                        output_filename=output_filename,
                        output_byte_size=0,
                        output_width=0,
                        output_height=0,
                        error_code=None,
                        error_message=None,
                        attempts=0,
                        created_at=now,
                        started_at=None,
                        completed_at=None,
                    )
                )

        job = BatchJob(
            id=job_id,
            project_id=project_id,
            status=BatchStatus.QUEUED,
            total_items=len(items),
            completed_items=0,
            failed_items=0,
            progress=0.0,
            zip_filename=None,
            error_message=None,
            config={
                "asset_ids": list(clean_asset_ids),
                "recipe_count": len(resolved_recipes),
                "include_shadow": bool(include_shadow),
                "watermark_text": clean_job_watermark,
                "prefer_ai_output": bool(prefer_ai_output),
            },
            created_at=now,
            started_at=None,
            completed_at=None,
            updated_at=now,
        )
        self._repo.create_batch_job(job, items)
        self._enqueue_job(job_id)
        return job, items

    def get_batch_job(self, job_id: str) -> tuple[BatchJob, list[BatchJobItem]]:
        loaded = self._repo.get_batch_job(job_id)
        if loaded is None:
            raise NotFoundError(f"Batch job '{job_id}' not found")
        return loaded

    def list_project_batches(self, project_id: str) -> list[BatchJob]:
        if self._repo.get_project(project_id) is None:
            raise NotFoundError(f"Project '{project_id}' not found")
        return self._repo.list_project_batch_jobs(project_id)

    def cancel_batch_job(self, job_id: str) -> tuple[BatchJob, list[BatchJobItem]]:
        self._get_cancel_event(job_id).set()
        try:
            result = self._repo.request_batch_job_cancel(job_id, utc_now_iso())
        except Exception:
            with self._lock:
                if job_id not in self._active_run_tokens:
                    self._cancel_events.pop(job_id, None)
                    self._futures.pop(job_id, None)
            raise
        if result is None:
            with self._lock:
                if job_id not in self._active_run_tokens:
                    self._cancel_events.pop(job_id, None)
                    self._futures.pop(job_id, None)
            raise NotFoundError(f"Batch job '{job_id}' not found")
        job, _items = result
        if job.status == BatchStatus.CANCELLED:
            self._cleanup_staging(job_id)
            with self._lock:
                if job_id not in self._active_run_tokens:
                    self._cancel_events.pop(job_id, None)
                    self._futures.pop(job_id, None)
        return result

    def retry_batch_job(self, job_id: str) -> tuple[BatchJob, list[BatchJobItem]]:
        result = self._repo.reset_batch_job_for_retry(job_id, utc_now_iso())
        if result is None:
            raise NotFoundError(f"Batch job '{job_id}' not found")
        self._enqueue_job(job_id)
        return result

    def get_download_zip_path(self, job_id: str) -> tuple[BatchJob, Path]:
        clean_id = validate_safe_archive_id(job_id, "job_id")
        assert_safe_relative_path(f"{clean_id}.zip", self._settings.exports_dir)
        job, _items = self.get_batch_job(clean_id)
        if job.status not in (BatchStatus.COMPLETED, BatchStatus.PARTIAL_FAILED) or not job.zip_filename:
            raise ConflictError(
                f"Batch archive for '{clean_id}' is not ready (status: '{job.status.value}')"
            )
        zip_path = assert_safe_relative_path(job.zip_filename, self._settings.exports_dir)
        if not zip_path.is_file():
            raise NotFoundError(f"Batch archive '{job.zip_filename}' not found on disk")
        return job, zip_path

    def _is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            ev = self._cancel_events.get(job_id)
        if ev is not None and ev.is_set():
            return True
        loaded = self._repo.get_batch_job(job_id)
        if loaded is None:
            return True
        return loaded[0].status in (BatchStatus.CANCEL_REQUESTED, BatchStatus.CANCELLED)

    def _render_item(self, item: BatchJobItem) -> tuple[bytes, int, int]:
        source_asset = self._repo.get_asset(item.source_asset_id)
        if source_asset is None:
            raise NotFoundError(f"Source asset '{item.source_asset_id}' not found")
        raw_bytes = self._blob_store.get_bytes(source_asset.storage_key)
        return render_recipe_image(
            raw_bytes,
            item.recipe_snapshot,
            max_pixels=self._settings.max_image_pixels,
            max_dimension=self._settings.max_image_dimension,
        )

    def _run_job(self, job_id: str, run_token: str | None = None) -> None:
        try:
            self._run_job_inner(job_id)
        finally:
            self._cleanup_job_handles(job_id, run_token)

    def _run_job_inner(self, job_id: str) -> None:
        if self._shutting_down.is_set():
            return
        loaded = self._repo.get_batch_job(job_id)
        if loaded is None:
            return
        job, items = loaded
        if job.status in (
            BatchStatus.COMPLETED,
            BatchStatus.PARTIAL_FAILED,
            BatchStatus.FAILED,
            BatchStatus.CANCELLED,
        ):
            return

        if self._is_cancelled(job_id):
            now = utc_now_iso()
            self._repo.finalize_batch_job(
                job_id,
                status=BatchStatus.CANCELLED,
                zip_filename=None,
                error_message="Batch job cancelled",
                completed_at=now,
                updated_at=now,
                cancel_pending_items=True,
            )
            self._cleanup_staging(job_id)
            return

        claimed = self._repo.claim_batch_job_running(job_id, utc_now_iso())
        if claimed is None:
            return

        staging_dir = self._staging_dir(job_id)
        staging_dir.mkdir(parents=True, exist_ok=True)

        cancelled = False
        for item in items:
            if self._shutting_down.is_set():
                return
            if self._is_cancelled(job_id):
                cancelled = True
                break
            if (
                item.status == BatchItemStatus.COMPLETED
                and item.output_filename
                and assert_safe_relative_path(item.output_filename, staging_dir).is_file()
            ):
                continue

            item_start = utc_now_iso()
            running_item = BatchJobItem(
                id=item.id,
                job_id=item.job_id,
                seq=item.seq,
                asset_id=item.asset_id,
                source_asset_id=item.source_asset_id,
                preset_id=item.preset_id,
                preset_version=item.preset_version,
                format=item.format,
                quality=item.quality,
                recipe_snapshot=item.recipe_snapshot,
                status=BatchItemStatus.RUNNING,
                output_filename=item.output_filename,
                output_byte_size=0,
                output_width=0,
                output_height=0,
                error_code=None,
                error_message=None,
                attempts=item.attempts + 1,
                created_at=item.created_at,
                started_at=item_start,
                completed_at=None,
            )
            self._repo.update_batch_job_item(running_item)

            try:
                rendered_bytes, out_w, out_h = self._render_item(running_item)
                out_name = running_item.output_filename or f"{running_item.seq:03d}.bin"
                staged_file = assert_safe_relative_path(out_name, staging_dir)
                if self._is_cancelled(job_id):
                    staged_file.unlink(missing_ok=True)
                    cancelled_item = BatchJobItem(
                        id=running_item.id,
                        job_id=running_item.job_id,
                        seq=running_item.seq,
                        asset_id=running_item.asset_id,
                        source_asset_id=running_item.source_asset_id,
                        preset_id=running_item.preset_id,
                        preset_version=running_item.preset_version,
                        format=running_item.format,
                        quality=running_item.quality,
                        recipe_snapshot=running_item.recipe_snapshot,
                        status=BatchItemStatus.CANCELLED,
                        output_filename=running_item.output_filename,
                        output_byte_size=0,
                        output_width=0,
                        output_height=0,
                        error_code=None,
                        error_message=None,
                        attempts=running_item.attempts,
                        created_at=running_item.created_at,
                        started_at=item_start,
                        completed_at=utc_now_iso(),
                    )
                    self._repo.update_batch_job_item(cancelled_item)
                    cancelled = True
                    break
                staged_file.write_bytes(rendered_bytes)
                finished_item = BatchJobItem(
                    id=running_item.id,
                    job_id=running_item.job_id,
                    seq=running_item.seq,
                    asset_id=running_item.asset_id,
                    source_asset_id=running_item.source_asset_id,
                    preset_id=running_item.preset_id,
                    preset_version=running_item.preset_version,
                    format=running_item.format,
                    quality=running_item.quality,
                    recipe_snapshot=running_item.recipe_snapshot,
                    status=BatchItemStatus.COMPLETED,
                    output_filename=out_name,
                    output_byte_size=len(rendered_bytes),
                    output_width=out_w,
                    output_height=out_h,
                    error_code=None,
                    error_message=None,
                    attempts=running_item.attempts,
                    created_at=running_item.created_at,
                    started_at=item_start,
                    completed_at=utc_now_iso(),
                )
                self._repo.update_batch_job_item(finished_item)
            except Exception as exc:
                err_code = (
                    exc.code.value
                    if isinstance(exc, AppError) and hasattr(exc.code, "value")
                    else "RENDER_ERROR"
                )
                failed_item = BatchJobItem(
                    id=running_item.id,
                    job_id=running_item.job_id,
                    seq=running_item.seq,
                    asset_id=running_item.asset_id,
                    source_asset_id=running_item.source_asset_id,
                    preset_id=running_item.preset_id,
                    preset_version=running_item.preset_version,
                    format=running_item.format,
                    quality=running_item.quality,
                    recipe_snapshot=running_item.recipe_snapshot,
                    status=BatchItemStatus.FAILED,
                    output_filename=running_item.output_filename,
                    output_byte_size=0,
                    output_width=0,
                    output_height=0,
                    error_code=err_code,
                    error_message=str(exc),
                    attempts=running_item.attempts,
                    created_at=running_item.created_at,
                    started_at=item_start,
                    completed_at=utc_now_iso(),
                )
                self._repo.update_batch_job_item(failed_item)

            if self._is_cancelled(job_id):
                cancelled = True
                break

        if self._shutting_down.is_set():
            return

        refreshed = self._repo.get_batch_job(job_id)
        if refreshed is None:
            self._cleanup_staging(job_id)
            return
        cur_job, cur_items = refreshed

        has_cancelable_items = any(
            it.status
            in (
                BatchItemStatus.PENDING,
                BatchItemStatus.RUNNING,
                BatchItemStatus.CANCELLED,
            )
            for it in cur_items
        )
        if cancelled and has_cancelable_items:
            now = utc_now_iso()
            self._repo.finalize_batch_job(
                job_id,
                status=BatchStatus.CANCELLED,
                zip_filename=None,
                error_message="Batch job cancelled",
                completed_at=now,
                updated_at=now,
                cancel_pending_items=True,
            )
            self._cleanup_staging(job_id)
            return

        completed_items = [it for it in cur_items if it.status == BatchItemStatus.COMPLETED]
        failed_items = [it for it in cur_items if it.status == BatchItemStatus.FAILED]
        cancelled_items = [it for it in cur_items if it.status == BatchItemStatus.CANCELLED]

        final_status = derive_batch_status(
            total_items=len(cur_items),
            completed_items=len(completed_items),
            failed_items=len(failed_items),
            cancelled_items=len(cancelled_items),
            cancel_requested=False,
        )
        now = utc_now_iso()

        if len(completed_items) == 0:
            self._repo.finalize_batch_job(
                job_id,
                status=BatchStatus.FAILED,
                zip_filename=None,
                error_message="All batch items failed; inspect item errors",
                completed_at=now,
                updated_at=now,
            )
            self._cleanup_staging(job_id)
            return

        zip_filename = f"{job_id}.zip"
        zip_path = assert_safe_relative_path(zip_filename, self._settings.exports_dir)
        entries: list[tuple[str, bytes]] = []
        manifest_items: list[dict[str, Any]] = []
        missing_staged_items: list[BatchJobItem] = []

        for it in cur_items:
            item_sha256: str | None = None
            if it.status == BatchItemStatus.COMPLETED:
                staged_file = (
                    assert_safe_relative_path(it.output_filename, staging_dir)
                    if it.output_filename
                    else None
                )
                if staged_file is None or not staged_file.is_file():
                    missing_staged_items.append(it)
                    continue
                file_bytes = staged_file.read_bytes()
                item_sha256 = hashlib.sha256(file_bytes).hexdigest()
                entries.append((it.output_filename, file_bytes))
            manifest_items.append(
                {
                    "id": it.id,
                    "seq": it.seq,
                    "asset_id": it.asset_id,
                    "source_asset_id": it.source_asset_id,
                    "preset_id": it.preset_id,
                    "preset_version": it.preset_version,
                    "format": it.format,
                    "quality": it.quality,
                    "status": it.status.value,
                    "output_filename": it.output_filename,
                    "output_byte_size": it.output_byte_size,
                    "output_width": it.output_width,
                    "output_height": it.output_height,
                    "sha256": item_sha256,
                    "error_code": it.error_code,
                    "error_message": it.error_message,
                }
            )

        if missing_staged_items:
            fail_ts = utc_now_iso()
            for missing_it in missing_staged_items:
                self._repo.update_batch_job_item(
                    BatchJobItem(
                        id=missing_it.id,
                        job_id=missing_it.job_id,
                        seq=missing_it.seq,
                        asset_id=missing_it.asset_id,
                        source_asset_id=missing_it.source_asset_id,
                        preset_id=missing_it.preset_id,
                        preset_version=missing_it.preset_version,
                        format=missing_it.format,
                        quality=missing_it.quality,
                        recipe_snapshot=missing_it.recipe_snapshot,
                        status=BatchItemStatus.FAILED,
                        output_filename=missing_it.output_filename,
                        output_byte_size=0,
                        output_width=0,
                        output_height=0,
                        error_code="STAGING_MISSING",
                        error_message=(
                            f"Staged output file '{missing_it.output_filename}' "
                            "missing during ZIP packaging"
                        ),
                        attempts=missing_it.attempts,
                        created_at=missing_it.created_at,
                        started_at=missing_it.started_at,
                        completed_at=fail_ts,
                    )
                )
            self._repo.finalize_batch_job(
                job_id,
                status=BatchStatus.FAILED,
                zip_filename=None,
                error_message="ZIP packaging aborted: staged output missing for completed item(s)",
                completed_at=fail_ts,
                updated_at=fail_ts,
            )
            self._cleanup_staging(job_id)
            raise RuntimeError(
                f"Batch job '{job_id}' aborted ZIP packaging due to missing staged file(s)"
            )

        manifest_payload = {
            "job_id": job_id,
            "project_id": cur_job.project_id,
            "status": final_status.value,
            "created_at": cur_job.created_at,
            "completed_at": now,
            "total_items": len(cur_items),
            "completed_items": len(completed_items),
            "failed_items": len(failed_items),
            "items": manifest_items,
        }
        entries.insert(
            0,
            (
                "manifest.json",
                json.dumps(manifest_payload, indent=2, ensure_ascii=False).encode("utf-8"),
            ),
        )
        try:
            _atomic_write_zip(zip_path, self._settings.exports_dir, entries)
        except Exception as exc:
            fail_ts = utc_now_iso()
            self._repo.finalize_batch_job(
                job_id,
                status=BatchStatus.FAILED,
                zip_filename=None,
                error_message=f"ZIP packaging failed: {exc}",
                completed_at=fail_ts,
                updated_at=fail_ts,
            )
            self._cleanup_staging(job_id)
            raise

        self._repo.finalize_batch_job(
            job_id,
            status=final_status,
            zip_filename=zip_filename,
            error_message=(
                f"{len(failed_items)} item(s) failed; partial archive created"
                if failed_items
                else None
            ),
            completed_at=now,
            updated_at=now,
        )
        if final_status in (BatchStatus.COMPLETED, BatchStatus.FAILED):
            self._cleanup_staging(job_id)

    def execute_sync_export(
        self,
        *,
        project_id: str,
        recipes: list[BatchRecipeInput],
        asset_ids: list[str] | None = None,
        adjustments: BatchAdjustments | dict[str, Any] | None = None,
        prefer_ai_output: bool = True,
    ) -> tuple[str, int, str]:
        """Execute a synchronous real Pillow export for /export/batch compatibility."""
        if not recipes:
            raise ValidationAppError("recipes must contain at least one recipe")
        if len(recipes) > self._settings.batch_max_recipes_per_job:
            raise ValidationAppError(
                f"recipes cannot exceed {self._settings.batch_max_recipes_per_job} per export"
            )
        try:
            clean_adjustments = validate_batch_adjustments(adjustments)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        project = self._repo.get_project(project_id)
        source_inputs: list[tuple[str, bytes, Asset | None]] = []

        if asset_ids is not None:
            if project is None:
                raise NotFoundError(f"Project '{project_id}' not found")
            try:
                clean_asset_ids = validate_batch_asset_ids(
                    asset_ids, max_assets=self._settings.batch_max_assets_per_job
                )
            except ValueError as exc:
                raise ValidationAppError(str(exc)) from exc
            for aid in clean_asset_ids:
                asset = self._repo.get_asset(aid)
                if asset is None:
                    raise NotFoundError(f"Asset '{aid}' not found")
                if asset.project_id != project_id:
                    raise ValidationAppError(
                        f"Asset '{aid}' does not belong to project '{project_id}'"
                    )
                source_inputs.append((asset.filename, b"", asset))
        elif project is not None:
            originals = self._repo.list_project_assets(project_id, kind=AssetKind.ORIGINAL)
            candidates = originals or self._repo.list_project_assets(project_id)
            for asset in candidates:
                source_inputs.append((asset.filename, b"", asset))

        if not source_inputs:
            source_inputs = [("studio_product.png", generate_synthetic_product_canvas(), None)]

        if len(source_inputs) * len(recipes) > self._settings.batch_max_items_per_job:
            raise ValidationAppError(
                f"Export item count exceeds maximum of {self._settings.batch_max_items_per_job}"
            )

        export_id = f"exp_{uuid.uuid4().hex[:12]}"
        zip_filename = f"{export_id}.zip"
        zip_path = assert_safe_relative_path(zip_filename, self._settings.exports_dir)
        now = utc_now_iso()

        entries: list[tuple[str, bytes]] = []
        manifest_items: list[dict[str, Any]] = []
        seq = 0

        for raw_filename, synthetic_bytes, base_asset in source_inputs:
            stem = os.path.splitext(sanitize_upload_filename(raw_filename))[0] or "image"
            for recipe in recipes:
                seq += 1
                canonical_id = LEGACY_PRESET_ID_ALIASES.get(recipe.preset_id, recipe.preset_id)
                preset = self._repo.get_preset(recipe.preset_id) or self._repo.get_preset(
                    canonical_id
                )
                if preset is None:
                    raise NotFoundError(f"Preset '{recipe.preset_id}' not found")
                try:
                    fmt = validate_batch_format(recipe.format, preset.formats)
                    quality = validate_batch_quality(recipe.quality)
                    bg_rgb = (
                        validate_background_rgb(recipe.background_rgb)
                        if recipe.background_rgb is not None
                        else preset.background_rgb
                    )
                    subject_ratio = (
                        validate_subject_area_ratio(recipe.subject_area_ratio)
                        if recipe.subject_area_ratio is not None
                        else preset.subject_area_ratio
                    )
                    eff_shadow = bool(recipe.include_shadow) if recipe.include_shadow is not None else False
                    eff_watermark = validate_watermark_text(recipe.watermark_text)
                except ValueError as exc:
                    raise ValidationAppError(str(exc)) from exc

                if base_asset is not None:
                    chosen = self._resolve_source_asset(
                        project_id, base_asset, preset.id, prefer_ai_output
                    )
                    raw_bytes = self._blob_store.get_bytes(chosen.storage_key)
                    src_asset_id: str | None = chosen.id
                else:
                    raw_bytes = synthetic_bytes
                    src_asset_id = None

                snapshot = _build_recipe_snapshot(
                    preset,
                    fmt=fmt,
                    quality=quality,
                    bg_rgb=bg_rgb,
                    subject_ratio=subject_ratio,
                    include_shadow=eff_shadow,
                    watermark_text=eff_watermark,
                    adjustments=clean_adjustments,
                    prefer_ai_output=prefer_ai_output,
                    output_preset_label=recipe.preset_id,
                )
                rendered_bytes, out_w, out_h = render_recipe_image(
                    raw_bytes,
                    snapshot,
                    max_pixels=self._settings.max_image_pixels,
                    max_dimension=self._settings.max_image_dimension,
                )
                ext = "jpg" if fmt == "jpeg" else fmt
                safe_label = sanitize_upload_filename(recipe.preset_id).replace(".", "_")
                member_name = f"image_{seq:03d}_{stem}_{safe_label}.{ext}"
                file_sha256 = hashlib.sha256(rendered_bytes).hexdigest()
                entries.append((member_name, rendered_bytes))
                manifest_items.append(
                    {
                        "seq": seq,
                        "asset_id": base_asset.id if base_asset is not None else None,
                        "source_asset_id": src_asset_id,
                        "preset_id": recipe.preset_id,
                        "resolved_preset_id": preset.id,
                        "preset_version": preset.version,
                        "format": fmt,
                        "quality": quality,
                        "output_filename": member_name,
                        "output_byte_size": len(rendered_bytes),
                        "output_width": out_w,
                        "output_height": out_h,
                        "sha256": file_sha256,
                    }
                )

        manifest_json = {
            "export_id": export_id,
            "project_id": project_id,
            "timestamp": now,
            "total_images": len(manifest_items),
            "items": manifest_items,
        }
        manifest_txt = (
            f"KROMA Batch Export Manifest\n"
            f"Export ID: {export_id}\n"
            f"Project ID: {project_id}\n"
            f"Timestamp: {now}\n"
            f"Total Images: {len(manifest_items)}\n"
        )
        all_entries: list[tuple[str, bytes]] = [
            ("manifest.txt", manifest_txt.encode("utf-8")),
            (
                "manifest.json",
                json.dumps(manifest_json, indent=2, ensure_ascii=False).encode("utf-8"),
            ),
            *entries,
        ]
        _atomic_write_zip(zip_path, self._settings.exports_dir, all_entries)
        return export_id, len(manifest_items), zip_filename
