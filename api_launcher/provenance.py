from __future__ import annotations

import hashlib
import json
from typing import Iterable


SUPPORTED_SOURCE_FORMATS = {
    "api",
    "csv",
    "csv.gz",
    "geojson",
    "geojson.gz",
    "json",
    "json.gz",
    "jsonl",
    "jsonl.gz",
    "manual",
    "ndjson",
    "ndjson.gz",
    "sqlite",
    "tar",
    "tar.bz2",
    "tar.gz",
    "tar.xz",
    "tgz",
    "unknown",
    "zip",
}


def normalize_source_format(value: str) -> str:
    # source_format 會寫進 install registry；未知格式不能靜默降級，否則 repair/import 會誤判。
    source_format = value.strip().lower() or "unknown"
    if source_format not in SUPPORTED_SOURCE_FORMATS:
        raise ValueError(f"Unsupported source format: {value!r}")
    return source_format


def schema_fingerprint(columns: Iterable[str]) -> str:
    # fingerprint 只描述欄位集合與順序，不把資料列內容放進 hash，避免洩漏資料也方便 drift 偵測。
    normalized = [column.strip().lower() for column in columns if column.strip()]
    payload = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
