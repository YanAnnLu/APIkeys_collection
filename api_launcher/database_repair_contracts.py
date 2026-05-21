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
    # 同一份 label 給 CLI/UI 錯誤訊息使用，避免文件說可修、程式卻拒絕的落差。
    return ", ".join(SUPPORTED_REIMPORT_SOURCE_FORMATS)


def is_supported_reimport_source_format(source_format: str) -> bool:
    # 自動 reimport 只允許目前 importer 能安全重建的格式；其他格式維持人工審核。
    return source_format.strip().lower() in SUPPORTED_REIMPORT_SOURCE_FORMATS


def manifest_path_from_notes(notes: str) -> str:
    # 舊 registry 把 manifest path 塞在 notes；集中解析可避免 repair 流程各自寫 brittle regex。
    match = re.search(r"(?:^|\s)manifest=(?P<path>.+?)(?:\s+payload=|\s+source_url=|$)", notes.strip())
    if not match:
        return ""
    return match.group("path").strip().strip("'\"")
