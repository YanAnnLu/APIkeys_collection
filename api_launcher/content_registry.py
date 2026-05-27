from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.adapter_plan_resolvers.resource_formats import normalize_resource_format, source_format_from_url


SUPPORTED_SQLITE_IMPORTERS: dict[str, str] = {
    "csv": "csv_to_sqlite",
    "csv.gz": "csv_to_sqlite",
    "json": "json_to_sqlite",
    "json.gz": "json_to_sqlite",
    "jsonl": "json_to_sqlite",
    "jsonl.gz": "json_to_sqlite",
    "ndjson": "json_to_sqlite",
    "ndjson.gz": "json_to_sqlite",
    "geojson": "json_to_sqlite",
    "geojson.gz": "json_to_sqlite",
}

ARCHIVE_OR_COMPRESSED_FORMATS = frozenset({"csv.zst", "zst", "zip", "tar", "tar.gz", "7z", "bz2", "xz"})
SCIENTIFIC_GRID_FORMATS = frozenset({"netcdf", "hdf", "hdf5", "zarr", "grib", "grb"})
GEOSPATIAL_ASSET_FORMATS = frozenset(
    {"geotiff", "cog", "shapefile", "geopackage", "flatgeobuf", "mbtiles", "pmtiles"}
)
COLUMNAR_FORMATS = frozenset({"parquet", "arrow", "feather"})
DATABASE_SNAPSHOT_FORMATS = frozenset({"sqlite"})
DOCUMENT_FORMATS = frozenset({"pdf", "xml", "html", "txt"})

FORMAT_ALIASES = {
    "nc": "netcdf",
    "cdf": "netcdf",
    "h5": "hdf5",
    "hdf": "hdf",
    "tif": "geotiff",
    "tiff": "geotiff",
    "gpkg": "geopackage",
    "shp": "shapefile",
    "fgb": "flatgeobuf",
    "grb": "grib",
    "db": "sqlite",
    "sqlite3": "sqlite",
}


@dataclass(frozen=True)
class ContentImportProfile:
    """UI-neutral import capability contract for one content format.

    Source-pattern adapters answer "how do we find resources"; this profile
    answers "what can RRKAL safely do with the downloaded bytes".  Keep this
    contract declarative so Tk/Web/Qt can render the same next action without
    duplicating content-format rules.
    """

    source_format: str
    content_family: str
    import_status: str
    parser_id: str
    importability: str
    pipeline_lane: str
    review_required: bool
    review_bucket: str
    next_action: str
    display_label: str
    display_tone: str
    supported_importer: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source_format": self.source_format,
            "content_family": self.content_family,
            "import_status": self.import_status,
            "parser_id": self.parser_id,
            "importability": self.importability,
            "pipeline_lane": self.pipeline_lane,
            "review_required": self.review_required,
            "review_bucket": self.review_bucket,
            "next_action": self.next_action,
            "display_label": self.display_label,
            "display_tone": self.display_tone,
            "supported_importer": self.supported_importer,
        }


@dataclass(frozen=True)
class ContentParserCapability:
    source_format: str
    content_family: str
    import_status: str
    parser_id: str
    reason: str
    review_bucket: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source_format": self.source_format,
            "content_family": self.content_family,
            "import_status": self.import_status,
            "parser_id": self.parser_id,
            "reason": self.reason,
            "review_bucket": self.review_bucket,
            "import_profile": content_import_profile_from_capability(self).to_dict(),
        }


@dataclass(frozen=True)
class ContentDetection:
    source_format: str
    confidence: float
    evidence: tuple[str, ...]
    capability: ContentParserCapability

    def to_dict(self) -> dict[str, object]:
        return {
            "source_format": self.source_format,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "capability": self.capability.to_dict(),
            "import_profile": content_import_profile_from_capability(self.capability).to_dict(),
        }


def normalize_content_format(value: str) -> str:
    normalized = normalize_resource_format(value)
    return FORMAT_ALIASES.get(normalized, normalized or "unknown")


def detect_content_format(
    *,
    url: str = "",
    media_type: str = "",
    format_hint: str = "",
    filename: str = "",
) -> ContentDetection:
    """只判斷下載物內容格式；不判斷 STAC/CKAN/ERDDAP 這類來源入口範式。"""

    candidates: list[tuple[str, str]] = []
    if format_hint.strip():
        candidates.append((normalize_content_format(format_hint), "format_hint"))
    if media_type.strip():
        candidates.append((normalize_content_format(media_type), "media_type"))
    if filename.strip():
        candidates.append((format_from_path_or_url(filename), "filename"))
    if url.strip():
        candidates.append((format_from_path_or_url(url), "url_suffix"))

    known = [(value, source) for value, source in candidates if value and value != "unknown"]
    source_format = known[0][0] if known else "unknown"
    evidence = tuple(f"{source}={value}" for value, source in candidates if value)
    confidence = confidence_for_detection(source_format, known)
    return ContentDetection(
        source_format=source_format,
        confidence=confidence,
        evidence=evidence,
        capability=content_parser_capability(source_format),
    )


def format_from_path_or_url(value: str) -> str:
    # filename / URL 都只拿副檔名當弱證據；真正內容仍要由 manifest + parser 驗證。
    text = value.strip()
    if not text:
        return "unknown"
    if "://" in text:
        return normalize_content_format(source_format_from_url(text))
    suffixes = [suffix.lower().lstrip(".") for suffix in Path(text).suffixes]
    if not suffixes:
        return "unknown"
    compound = {
        ("geojson", "gz"): "geojson.gz",
        ("shp", "zip"): "shapefile",
        ("jsonl", "gz"): "jsonl.gz",
        ("ndjson", "gz"): "ndjson.gz",
        ("json", "gz"): "json.gz",
        ("csv", "gz"): "csv.gz",
        ("csv", "zst"): "csv.zst",
        ("tar", "gz"): "tar.gz",
    }
    for parts, result in compound.items():
        if len(suffixes) >= len(parts) and tuple(suffixes[-len(parts) :]) == parts:
            return result
    return normalize_content_format(suffixes[-1])


def confidence_for_detection(source_format: str, known: list[tuple[str, str]]) -> float:
    if source_format == "unknown":
        return 0.0
    matching_sources = {source for value, source in known if value == source_format}
    if {"format_hint", "media_type"} & matching_sources and {"filename", "url_suffix"} & matching_sources:
        return 0.95
    if "format_hint" in matching_sources or "media_type" in matching_sources:
        return 0.8
    return 0.6


def content_parser_capability(source_format: str) -> ContentParserCapability:
    normalized = normalize_content_format(source_format)
    importer = SUPPORTED_SQLITE_IMPORTERS.get(normalized)
    if importer:
        return ContentParserCapability(
            source_format=normalized,
            content_family="tabular_or_document_json",
            import_status="supported_after_download",
            parser_id=importer,
            reason=(
                "This content format has an MVP SQLite importer after download verification."
                if importer == "csv_to_sqlite"
                else "This JSON-family format can be flattened into SQLite after download verification."
            ),
        )
    if normalized in ARCHIVE_OR_COMPRESSED_FORMATS:
        return ContentParserCapability(
            source_format=normalized,
            content_family="archive_or_compressed",
            import_status="requires_unpack_or_adapter",
            parser_id="archive_review",
            review_bucket="downloaded_payload_transform",
            reason="The file can be downloaded, but it needs an extraction or transform step before curated import.",
        )
    if normalized in SCIENTIFIC_GRID_FORMATS:
        return ContentParserCapability(
            source_format=normalized,
            content_family="scientific_grid_or_array",
            import_status="manual_review_required",
            parser_id="scientific_grid_review",
            review_bucket="content_parser_required",
            reason="Scientific grid/array payloads need a dedicated NetCDF/HDF/Zarr parser before curated import.",
        )
    if normalized in GEOSPATIAL_ASSET_FORMATS:
        return ContentParserCapability(
            source_format=normalized,
            content_family="geospatial_asset",
            import_status="manual_review_required",
            parser_id="geospatial_asset_review",
            review_bucket="content_parser_required",
            reason="Geospatial raster, vector, and tile payloads should first become manifests or renderer-ready assets.",
        )
    if normalized in COLUMNAR_FORMATS:
        return ContentParserCapability(
            source_format=normalized,
            content_family="columnar_table",
            import_status="manual_review_required",
            parser_id="columnar_table_review",
            review_bucket="content_parser_required",
            reason="Columnar payloads need a Parquet/Arrow parser before curated SQLite or lakehouse import.",
        )
    if normalized in DATABASE_SNAPSHOT_FORMATS:
        return ContentParserCapability(
            source_format=normalized,
            content_family="database_snapshot",
            import_status="manual_review_required",
            parser_id="database_snapshot_review",
            review_bucket="content_parser_required",
            reason="Database snapshots are downloaded as raw artifacts first; opening or importing them requires ownership, provenance, and schema review.",
        )
    if normalized in DOCUMENT_FORMATS:
        return ContentParserCapability(
            source_format=normalized,
            content_family="document_or_markup",
            import_status="manual_review_required",
            parser_id="document_review",
            review_bucket="content_parser_required",
            reason="Document or markup payloads are kept as raw artifacts until a document parser is explicit.",
        )
    return ContentParserCapability(
        source_format=normalized or "unknown",
        content_family="unknown",
        import_status="manual_review_required",
        parser_id="unknown_content_review",
        review_bucket="unsupported_payload_format",
        reason="No MVP content parser is registered for this source format yet.",
    )


def content_import_profile(source_format: str) -> ContentImportProfile:
    """Return the declarative import profile for a normalized or hinted format."""

    return content_import_profile_from_capability(content_parser_capability(source_format))


def content_import_profile_from_capability(capability: ContentParserCapability) -> ContentImportProfile:
    """Convert parser capability into the smaller import/review routing contract."""

    if capability.import_status == "supported_after_download":
        return ContentImportProfile(
            source_format=capability.source_format,
            content_family=capability.content_family,
            import_status=capability.import_status,
            parser_id=capability.parser_id,
            importability="direct_sqlite_import_after_verified_download",
            pipeline_lane="sqlite_curated_import",
            review_required=False,
            review_bucket="",
            next_action="download_then_import_verified_payload",
            display_label="可匯入 SQLite",
            display_tone="success",
            supported_importer=capability.parser_id,
        )
    if capability.import_status == "requires_unpack_or_adapter":
        return ContentImportProfile(
            source_format=capability.source_format,
            content_family=capability.content_family,
            import_status=capability.import_status,
            parser_id=capability.parser_id,
            importability="transform_required_before_curated_import",
            pipeline_lane="downloaded_payload_transform",
            review_required=True,
            review_bucket=capability.review_bucket,
            next_action="unpack_or_transform_downloaded_payload",
            display_label="下載後需解壓或轉換",
            display_tone="warning",
        )
    if capability.review_bucket == "unsupported_payload_format":
        return ContentImportProfile(
            source_format=capability.source_format,
            content_family=capability.content_family,
            import_status=capability.import_status,
            parser_id=capability.parser_id,
            importability="unsupported_content_review",
            pipeline_lane="adapter_review",
            review_required=True,
            review_bucket=capability.review_bucket,
            next_action="review_payload_format_or_keep_raw_artifact",
            display_label="未知內容格式",
            display_tone="danger",
        )
    return ContentImportProfile(
        source_format=capability.source_format,
        content_family=capability.content_family,
        import_status=capability.import_status,
        parser_id=capability.parser_id,
        importability="content_parser_required_before_curated_import",
        pipeline_lane="content_parser_review",
        review_required=True,
        review_bucket=capability.review_bucket,
        next_action="add_content_parser_or_keep_raw_artifact",
        display_label="內容 Parser 待辦",
        display_tone="warning",
    )


__all__ = [
    "ContentDetection",
    "ContentImportProfile",
    "ContentParserCapability",
    "content_import_profile",
    "content_import_profile_from_capability",
    "content_parser_capability",
    "detect_content_format",
    "normalize_content_format",
]
