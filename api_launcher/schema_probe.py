from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from api_launcher.downloads.policy import PoliteDownloadPolicy


DEFAULT_SCHEMA_PROBE_MAX_BYTES = 128 * 1024


@dataclass(frozen=True)
class SchemaProbeColumn:
    name: str
    sample_value: str = ""
    inferred_type: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "sample_value": self.sample_value,
            "inferred_type": self.inferred_type,
        }


@dataclass(frozen=True)
class SchemaProbeResult:
    status: str
    source_url: str
    probe_url: str = ""
    row_count: int = 0
    columns: tuple[SchemaProbeColumn, ...] = ()
    error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_url": self.source_url,
            "probe_url": self.probe_url,
            "row_count": self.row_count,
            "columns": [column.to_dict() for column in self.columns],
            "error": self.error,
        }


def probe_plan_entry_schema(entry: dict[str, object], *, row_limit: int = 5, timeout: float = 12.0) -> SchemaProbeResult:
    url = str(entry.get("download_url") or entry.get("api_url") or "").strip()
    if not url:
        return SchemaProbeResult(status="unavailable", source_url="", error="entry has no downloadable or API URL")
    probe_url = schema_probe_url(url, row_limit=row_limit)
    try:
        payload = fetch_probe_bytes(probe_url, timeout=timeout)
        if probe_url.lower().split("?", 1)[0].endswith(".csv"):
            return csv_schema_probe(url, probe_url, payload)
        return json_schema_probe(url, probe_url, payload)
    except Exception as exc:
        return SchemaProbeResult(status="error", source_url=url, probe_url=probe_url, error=f"{type(exc).__name__}: {exc}")


def schema_probe_url(url: str, row_limit: int = 5) -> str:
    parsed = urlsplit(url)
    limit = str(max(1, row_limit))
    lower_path = parsed.path.lower()
    if "/resource/" in lower_path:
        return replace_query_items(url, {"$limit": limit})
    if "/access/services/search/v1/" in lower_path:
        return replace_query_items(url, {"limit": limit, "offset": "0"})
    if lower_path.endswith("/items") or "/search/granules" in lower_path:
        key = "page_size" if "/search/granules" in lower_path else "limit"
        return replace_query_items(url, {key: limit})
    if "/erddap/tabledap/" in lower_path:
        return replace_query_items(url, {".limit": limit})
    return url


def fetch_probe_bytes(url: str, timeout: float, max_bytes: int = DEFAULT_SCHEMA_PROBE_MAX_BYTES) -> bytes:
    request = Request(url, headers={"User-Agent": PoliteDownloadPolicy().user_agent})
    with urlopen(request, timeout=timeout) as response:
        return response.read(max(1, int(max_bytes)))


def csv_schema_probe(source_url: str, probe_url: str, payload: bytes) -> SchemaProbeResult:
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    columns = tuple(
        SchemaProbeColumn(
            name=name,
            sample_value=first_row_value(rows, name),
            inferred_type=infer_value_type(first_row_value(rows, name)),
        )
        for name in (reader.fieldnames or [])
        if name
    )
    return SchemaProbeResult(status="ok", source_url=source_url, probe_url=probe_url, row_count=len(rows), columns=columns)


def json_schema_probe(source_url: str, probe_url: str, payload: bytes) -> SchemaProbeResult:
    data = json.loads(payload.decode("utf-8-sig", errors="replace"))
    rows = json_rows(data)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    columns = tuple(
        SchemaProbeColumn(
            name=key,
            sample_value=stringify_sample(rows[0].get(key)) if rows else "",
            inferred_type=infer_value_type(rows[0].get(key) if rows else None),
        )
        for key in keys
    )
    return SchemaProbeResult(status="ok", source_url=source_url, probe_url=probe_url, row_count=len(rows), columns=columns)


def json_rows(data: object) -> list[dict[str, object]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("data", "results", "features"):
            value = data.get(key)
            if isinstance(value, list):
                if key == "features":
                    return [feature.get("properties", feature) for feature in value if isinstance(feature, dict)]
                return [row for row in value if isinstance(row, dict)]
        return [data]
    return []


def first_row_value(rows: list[dict[str, str]], name: str) -> str:
    if not rows:
        return ""
    return str(rows[0].get(name) or "")


def infer_value_type(value: object) -> str:
    text = str(value or "").strip()
    if text == "":
        return "empty"
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return "boolean"
    try:
        int(text)
        return "integer"
    except ValueError:
        pass
    try:
        float(text)
        return "number"
    except ValueError:
        pass
    if "t" in lowered and ("-" in text or ":" in text):
        return "datetime"
    if len(text) >= 8 and text[4:5] == "-" and text[7:8] == "-":
        return "date"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "text"


def stringify_sample(value: object) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)[:120]
    return str(value or "")[:120]


def replace_query_items(url: str, values: dict[str, str]) -> str:
    parts = urlsplit(url)
    remove_keys = {key.lower() for key in values}
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in remove_keys]
    query.extend((key, value) for key, value in values.items() if value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True, safe="$,:/"), parts.fragment))
