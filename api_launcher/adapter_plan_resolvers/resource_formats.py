from __future__ import annotations

import urllib.parse
from pathlib import Path


def normalize_resource_format(value: str) -> str:
    # 各入口的 format/mediaType 寫法很不一致，先壓成 importer 與 manifest 共同理解的穩定格式代號。
    normalized = value.strip().lower().split(";", 1)[0].strip()
    if not normalized:
        return "unknown"
    normalized = normalized.replace("application/", "").replace("text/", "").replace("image/", "")
    normalized = normalized.replace("x-", "").replace(" ", "_")
    if "csv" in normalized and ("zst" in normalized or "zstandard" in normalized):
        return "csv.zst"
    if "csv" in normalized and "gz" in normalized:
        return "csv.gz"
    if ("geojson" in normalized or "geo+json" in normalized) and "gz" in normalized:
        return "geojson.gz"
    if ("jsonl" in normalized or "ndjson" in normalized) and "gz" in normalized:
        return "jsonl.gz" if "jsonl" in normalized else "ndjson.gz"
    if "json" in normalized and "gz" in normalized:
        return "json.gz"
    if "geojson" in normalized or "geo+json" in normalized:
        return "geojson"
    if "jsonl" in normalized:
        return "jsonl"
    if "ndjson" in normalized:
        return "ndjson"
    if "json" in normalized:
        return "json"
    if "parquet" in normalized:
        return "parquet"
    if "netcdf" in normalized or normalized in {"nc", "cdf"}:
        return "netcdf"
    if "geotiff" in normalized or "tiff" in normalized:
        return "geotiff"
    if "geopackage" in normalized or "gpkg" in normalized:
        return "geopackage"
    if "hdf5" in normalized:
        return "hdf5"
    if normalized == "hdf" or normalized.endswith("+hdf"):
        return "hdf"
    if "grib" in normalized:
        return "grib"
    if "zip" in normalized:
        return "zip"
    if "tar" in normalized and "gz" in normalized:
        return "tar.gz"
    if "zst" in normalized or "zstandard" in normalized:
        return "zst"
    return normalized or "unknown"


def source_format_from_url(url: str) -> str:
    suffixes = [suffix.lower().lstrip(".") for suffix in Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).suffixes]
    if not suffixes:
        return "unknown"
    # 複合副檔名會直接影響後續 importer 與 archive transform；必須優先於最後一段副檔名判斷。
    compound_suffixes = (
        (("geojson", "gz"), "geojson.gz"),
        (("jsonl", "gz"), "jsonl.gz"),
        (("ndjson", "gz"), "ndjson.gz"),
        (("json", "gz"), "json.gz"),
        (("csv", "gz"), "csv.gz"),
        (("csv", "zst"), "csv.zst"),
        (("tar", "gz"), "tar.gz"),
    )
    for parts, source_format in compound_suffixes:
        if len(suffixes) >= len(parts) and tuple(suffixes[-len(parts) :]) == parts:
            return source_format
    return suffixes[-1]
