from __future__ import annotations

import hashlib
import json
from typing import Iterable


SUPPORTED_SOURCE_FORMATS = {"api", "csv", "json", "sqlite", "manual", "unknown"}


def normalize_source_format(value: str) -> str:
    source_format = value.strip().lower() or "unknown"
    if source_format not in SUPPORTED_SOURCE_FORMATS:
        raise ValueError(f"Unsupported source format: {value!r}")
    return source_format


def schema_fingerprint(columns: Iterable[str]) -> str:
    normalized = [column.strip().lower() for column in columns if column.strip()]
    payload = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
