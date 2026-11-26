from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

_CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_correlation_id(value: str | None) -> str:
    if value is not None:
        trimmed = value.strip()
        if _CORRELATION_ID_RE.fullmatch(trimmed):
            return trimmed
    return new_id()
