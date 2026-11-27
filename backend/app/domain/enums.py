from __future__ import annotations

from enum import Enum


class AssetKind(str, Enum):
    ORIGINAL = "original"
    MASK = "mask"
    AI_OUTPUT = "ai_output"
    THUMBNAIL = "thumbnail"


class ImageMime(str, Enum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"


class MarketplaceId(str, Enum):
    SHOPEE = "shopee"
    TIKTOK_SHOP = "tiktok_shop"
    LAZADA = "lazada"
    AMAZON = "amazon"
    CUSTOM = "custom"


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    GONE = "GONE"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    MIME_SPOOF_DETECTED = "MIME_SPOOF_DETECTED"
    PATH_TRAVERSAL_DETECTED = "PATH_TRAVERSAL_DETECTED"
    ZIP_SLIP_DETECTED = "ZIP_SLIP_DETECTED"
    PIXEL_BOMB_DETECTED = "PIXEL_BOMB_DETECTED"
    UNSUPPORTED_COLOR_SPACE_CMYK = "UNSUPPORTED_COLOR_SPACE_CMYK"
    UNSUPPORTED_BIT_DEPTH = "UNSUPPORTED_BIT_DEPTH"
    UNSUPPORTED_RAW_FORMAT = "UNSUPPORTED_RAW_FORMAT"
    UNSUPPORTED_HDR_IMAGE = "UNSUPPORTED_HDR_IMAGE"
    UNSUPPORTED_ANIMATED_IMAGE = "UNSUPPORTED_ANIMATED_IMAGE"
    CORRUPT_IMAGE = "CORRUPT_IMAGE"
    IMMUTABLE_ASSET_VIOLATION = "IMMUTABLE_ASSET_VIOLATION"
    BACKEND_NOT_CONFIGURED = "BACKEND_NOT_CONFIGURED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class BatchStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class BatchItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProofingStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"
    ARCHIVED = "archived"


class ProofingAction(str, Enum):
    COMMENT = "comment"
    APPROVE = "approve"
    REQUEST_CHANGE = "request_change"


class ProofingDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGE = "request_change"
    REOPEN = "reopen"
    ARCHIVE = "archive"
    REVOKE = "revoke"
