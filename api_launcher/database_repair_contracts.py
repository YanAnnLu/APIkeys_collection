from __future__ import annotations

import re


CSV_REIMPORT_FORMATS = ("csv", "csv.gz")
JSON_REIMPORT_FORMATS = (
    "json",
    "json.gz",
    "jsonl",
    "jsonl.gz",
    "ndjson",
    "ndjson.gz",
    "geojson",
    "geojson.gz",
)
SUPPORTED_REIMPORT_SOURCE_FORMATS = CSV_REIMPORT_FORMATS + JSON_REIMPORT_FORMATS


def supported_reimport_source_formats_label() -> str:
    return ", ".join(SUPPORTED_REIMPORT_SOURCE_FORMATS)


def is_supported_reimport_source_format(source_format: str) -> bool:
    return source_format.strip().lower() in SUPPORTED_REIMPORT_SOURCE_FORMATS


def manifest_path_from_notes(notes: str) -> str:
    match = re.search(r"(?:^|\s)manifest=(?P<path>.+?)(?:\s+payload=|\s+source_url=|$)", notes.strip())
    if not match:
        return ""
    return match.group("path").strip().strip("'\"")
