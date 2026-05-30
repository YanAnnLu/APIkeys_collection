from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from api_launcher.adapter_plan_resolver import AdapterPlanResolution, resolve_adapter_review_plan_payload
from api_launcher.crawlers.orchestrator import DatasetCrawlOptions, DatasetCrawlResult, crawl_dataset_sources
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource, dataset_with_candidate_metadata
from api_launcher.dataset_versions import DatasetVersionOption, version_options_for_dataset
from api_launcher.ingestion_pipeline import DownloadImportPipelineOptions, DownloadImportPipelineRun, run_download_import_slice
from api_launcher.models import Dataset, Provider
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class CredentialGate:
    provider_id: str
    status: str
    reason: str
    required_env_vars: tuple[str, ...] = ()
    configured_env_vars: tuple[str, ...] = ()

    @property
    def allows_download(self) -> bool:
        return self.status in {"not_required", "configured"}

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "reason": self.reason,
            "required_env_vars": list(self.required_env_vars),
            "configured_env_vars": list(self.configured_env_vars),
        }


@dataclass(frozen=True)
class SourceDownloadBounds:
    # 「界」是正式下載服務的輸入契約；UI/CLI 只要填這裡，後端就會盡量套到 crawler 與 resolver。
    # 有些來源只能套用部分界線，所以所有欄位也會保留在 plan metadata，避免後續 adapter 遺失使用者意圖。
    candidate_limit: int = 0
    version_limit: int = 1
    sample_limit: int = 25
    max_pages: int = 0
    full_crawl: bool = False
    start_date: str = ""
    end_date: str = ""
    bbox: tuple[float, float, float, float] | None = None
    max_bytes: int = 0
    search_terms: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = ()
    time_field: str = ""
    longitude_field: str = ""
    latitude_field: str = ""
    schema_probe_required: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_limit": self.candidate_limit,
            "version_limit": self.version_limit,
            "sample_limit": self.sample_limit,
            "max_pages": self.max_pages,
            "full_crawl": self.full_crawl,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "bbox": list(self.bbox) if self.bbox else [],
            "max_bytes": self.max_bytes,
            "search_terms": list(self.search_terms),
            "required_columns": list(self.required_columns),
            "time_field": self.time_field,
            "longitude_field": self.longitude_field,
            "latitude_field": self.latitude_field,
            "schema_probe_required": self.schema_probe_required,
        }


@dataclass(frozen=True)
class SourceDownloadOptions:
    bounds: SourceDownloadBounds = field(default_factory=SourceDownloadBounds)
    timeout: float = 12.0
    max_results_override: int = 0
    search_terms_override: tuple[str, ...] = ()
    full_crawl: bool = False
    max_pages: int = 0
    max_workers: int = 4
    min_candidates_per_source_override: int = -1
    include_all_versions: bool = False
    max_versions_per_dataset: int = 1
    selected_versions: dict[str, tuple[str, ...]] = field(default_factory=dict)
    import_supported_results: bool = False
    import_row_limit: int = 0
    import_existing_table_policy: str = "rename"

    def crawl_options(self) -> DatasetCrawlOptions:
        effective_terms = self.search_terms_override or self.bounds.search_terms
        return DatasetCrawlOptions(
            timeout=self.timeout,
            max_results_override=self.max_results_override or self.bounds.candidate_limit,
            search_terms_override=effective_terms,
            full_crawl=self.full_crawl or self.bounds.full_crawl,
            max_pages=self.max_pages or self.bounds.max_pages,
            max_workers=self.max_workers,
            min_candidates_per_source_override=self.min_candidates_per_source_override,
        )


@dataclass(frozen=True)
class SourceDownloadPlanBuild:
    crawl_result: DatasetCrawlResult
    candidate_count: int
    upserted_candidate_count: int
    original_plan: dict[str, object]
    resolved_plan: dict[str, object]
    resolution: AdapterPlanResolution
    credential_gates: tuple[CredentialGate, ...]
    missing_provider_ids: tuple[str, ...] = ()
    selected_version_count: int = 0
    filtered_version_count: int = 0
    candidate_snapshot_signature: str = ""
    candidate_snapshot_count: int = 0

    @property
    def direct_download_count(self) -> int:
        summary = self.resolved_plan.get("summary") if isinstance(self.resolved_plan.get("summary"), dict) else {}
        return int(summary.get("direct_download_count") or 0)

    @property
    def blocked_credential_count(self) -> int:
        return sum(1 for gate in self.credential_gates if not gate.allows_download)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "upserted_candidate_count": self.upserted_candidate_count,
            "selected_version_count": self.selected_version_count,
            "filtered_version_count": self.filtered_version_count,
            "candidate_snapshot_signature": self.candidate_snapshot_signature,
            "candidate_snapshot_count": self.candidate_snapshot_count,
            "direct_download_count": self.direct_download_count,
            "blocked_credential_count": self.blocked_credential_count,
            "missing_provider_ids": list(self.missing_provider_ids),
            "credential_gates": [gate.to_dict() for gate in self.credential_gates],
            "crawl_audit_summary": self.crawl_result.audit_summary,
            "adapter_resolution": self.resolution.to_dict(),
        }


@dataclass(frozen=True)
class SourceDownloadRun:
    plan_build: SourceDownloadPlanBuild
    pipeline: DownloadImportPipelineRun
    destination_dir: Path
    curated_sqlite_path: Path

    @property
    def succeeded(self) -> bool:
        return self.pipeline.succeeded

    def to_dict(self) -> dict[str, object]:
        return {
            "succeeded": self.succeeded,
            "destination_dir": str(self.destination_dir),
            "curated_sqlite_path": str(self.curated_sqlite_path),
            "plan_build": self.plan_build.to_dict(),
            "download_import": self.pipeline.to_dict(),
        }


def build_source_download_plan(
    sources: list[DatasetDiscoverySource],
    repository: ApiCatalogRepository,
    destination_dir: str | Path,
    options: SourceDownloadOptions | None = None,
) -> SourceDownloadPlanBuild:
    """Crawl source catalogs and turn their versions into a resolved download plan.

    This is the reusable service boundary for Tk, CLI, and future Qt UI.  It
    deliberately does not assume that every crawler result can be downloaded:
    credential-required providers are gated, metadata-only catalog entries are
    handed to the adapter resolver, and only bounded/direct entries reach the
    download runner.
    """

    active_options = options or SourceDownloadOptions()
    crawl_result = crawl_dataset_sources(sources, active_options.crawl_options())
    crawled_candidates = tuple(crawl_result.candidates)
    candidate_snapshot_signature = source_candidate_snapshot_signature(crawled_candidates)
    candidate_snapshot_count = len(crawled_candidates)
    provider_map = {provider.provider_id: provider for provider in repository.load_providers()}
    entries: list[dict[str, object]] = []
    credential_gates: dict[str, CredentialGate] = {}
    missing_provider_ids: set[str] = set()
    upserted_candidate_count = 0
    selected_version_count = 0
    filtered_version_count = 0

    for candidate in crawled_candidates:
        dataset = dataset_with_candidate_metadata(candidate)
        provider = provider_map.get(dataset.provider_id)
        if provider is None:
            missing_provider_ids.add(dataset.provider_id)
            continue
        repository.upsert_dataset(dataset)
        upserted_candidate_count += 1

        gate = credential_gate_for_provider(provider)
        credential_gates[provider.provider_id] = gate
        version_options = selected_version_options(dataset, active_options)
        selected_version_count += len(version_options)
        all_options = version_options_for_dataset(dataset)
        filtered_version_count += max(0, len(all_options) - len(version_options))
        for option in version_options:
            entry = provider_dataset_version_plan_entry(provider, dataset, option, downloads_root=destination_dir)
            entry = apply_source_download_bounds(entry, active_options.bounds)
            if not gate.allows_download:
                entry = credential_blocked_plan_entry(entry, gate)
            entries.append(entry)

    original_plan = build_dataset_download_plan(entries, plan_name="source_discovery_download_plan")
    original_plan["source"] = {
        "kind": "dataset_source_crawl_download_plan",
        "source_count": len(sources),
        "candidate_count": crawl_result.candidate_count,
        "missing_provider_ids": sorted(missing_provider_ids),
        "version_policy": {
            "include_all_versions": active_options.include_all_versions,
            "max_versions_per_dataset": active_options.max_versions_per_dataset,
            "selected_versions": {key: list(value) for key, value in active_options.selected_versions.items()},
        },
        "bounds": active_options.bounds.to_dict(),
    }
    resolved_plan, resolution = resolve_adapter_review_plan_payload(original_plan, downloads_root=destination_dir)
    return SourceDownloadPlanBuild(
        crawl_result=crawl_result,
        candidate_count=crawl_result.candidate_count,
        upserted_candidate_count=upserted_candidate_count,
        original_plan=original_plan,
        resolved_plan=resolved_plan,
        resolution=resolution,
        credential_gates=tuple(sorted(credential_gates.values(), key=lambda item: item.provider_id)),
        missing_provider_ids=tuple(sorted(missing_provider_ids)),
        selected_version_count=selected_version_count,
        filtered_version_count=filtered_version_count,
        candidate_snapshot_signature=candidate_snapshot_signature,
        candidate_snapshot_count=candidate_snapshot_count,
    )


def source_candidate_snapshot_signature(candidates: Iterable[DatasetCandidate]) -> str:
    """Return a stable digest for the crawl candidates that shaped a plan.

    This is intentionally a snapshot of the candidates already returned by a
    crawl.  It does not claim to know whether the remote catalog changed later;
    callers need a fresh crawl before comparing this digest against a new one.
    """

    normalized = [_candidate_snapshot_payload(candidate) for candidate in candidates]
    normalized.sort(
        key=lambda item: (
            str(item.get("provider_id") or ""),
            str(item.get("dataset_uid") or ""),
            str(item.get("dataset_id") or ""),
            str(item.get("version") or ""),
            str(item.get("source_id") or ""),
            str(item.get("source_url") or ""),
        )
    )
    return _stable_digest({"candidates": normalized})


def _candidate_snapshot_payload(candidate: DatasetCandidate) -> dict[str, object]:
    dataset = candidate.dataset
    return {
        "source_id": candidate.source_id,
        "source_type": candidate.source_type,
        "source_url": candidate.source_url,
        "dataset_uid": dataset.dataset_uid,
        "provider_id": dataset.provider_id,
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "native_format": dataset.native_format,
        "api_url": dataset.api_url,
        "landing_url": dataset.landing_url,
        "version": dataset.version,
        "remote_updated_at": dataset.remote_updated_at,
        "remote_etag": dataset.remote_etag,
        "remote_hash": dataset.remote_hash,
        "metadata_signature": _stable_digest(dataset.metadata),
    }


def _stable_digest(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def run_source_download_to_folder(
    sources: list[DatasetDiscoverySource],
    repository: ApiCatalogRepository,
    destination_dir: str | Path,
    options: SourceDownloadOptions | None = None,
    import_sqlite_path: str | Path | None = None,
) -> SourceDownloadRun:
    active_options = options or SourceDownloadOptions()
    destination = Path(destination_dir).expanduser()
    curated_sqlite_path = Path(import_sqlite_path) if import_sqlite_path is not None else destination / "curated_sources.db"
    plan_build = build_source_download_plan(sources, repository, destination, active_options)
    pipeline = run_download_import_slice(
        plan_build.resolved_plan,
        repository,
        DownloadImportPipelineOptions(
            timeout=active_options.timeout,
            import_supported_results=active_options.import_supported_results,
            import_sqlite_path=curated_sqlite_path,
            import_row_limit=active_options.import_row_limit,
            import_existing_table_policy=active_options.import_existing_table_policy,
        ),
    )
    return SourceDownloadRun(
        plan_build=plan_build,
        pipeline=pipeline,
        destination_dir=destination,
        curated_sqlite_path=curated_sqlite_path,
    )


def selected_version_options(dataset: Dataset, options: SourceDownloadOptions) -> list[DatasetVersionOption]:
    version_options = version_options_for_dataset(dataset)
    wanted = set(options.selected_versions.get(dataset.dataset_uid, ()))
    wanted.update(options.selected_versions.get(dataset.dataset_id, ()))
    # Source-level crawler asset forms can choose a version before a concrete
    # dataset candidate exists.  Keep that selector explicit instead of
    # overloading version_limit, so UI/Qt can offer real version picks.
    wanted.update(options.selected_versions.get("*", ()))
    if wanted:
        return [
            option
            for option in version_options
            if option.version in wanted or option.label in wanted or option.download_url in wanted
        ]
    if options.include_all_versions:
        return version_options
    limit = options.bounds.version_limit or options.max_versions_per_dataset
    if limit <= 0:
        return version_options
    return version_options[:limit]


def apply_source_download_bounds(entry: dict[str, object], bounds: SourceDownloadBounds) -> dict[str, object]:
    bounded = dict(entry)
    metadata_bounds = bounds.to_dict()
    bounded["download_bounds"] = metadata_bounds
    bounded["download_bound_status"] = bound_status_for_entry(bounded, bounds)
    version_meta = dict(bounded.get("dataset_version") or {}) if isinstance(bounded.get("dataset_version"), dict) else {}
    version_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    version_metadata["download_bounds"] = metadata_bounds
    version_metadata["download_bound_status"] = bounded["download_bound_status"]
    version_meta["metadata"] = version_metadata
    bounded["dataset_version"] = version_meta

    url = str(bounded.get("download_url") or "").strip()
    if not url:
        return bounded
    bounded_url = bounded_url_for_source(url, bounded, bounds)
    if bounded_url != url:
        bounded["download_url"] = bounded_url
        eligibility = dict(bounded.get("download_eligibility") or {})
        if eligibility:
            eligibility["direct_url"] = bounded_url
            eligibility["reason"] = "Direct URL was bounded by user-selected limits and recorded bound status."
            bounded["download_eligibility"] = eligibility
        version_meta["download_url"] = bounded_url
        bounded["dataset_version"] = version_meta
    return bounded


def bound_status_for_entry(entry: dict[str, object], bounds: SourceDownloadBounds) -> dict[str, object]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    known_columns = known_column_names(metadata)
    applied: list[str] = []
    needs_probe: list[str] = []
    unsupported: list[str] = []
    if bounds.sample_limit:
        applied.append("sample_limit")
    if bounds.start_date or bounds.end_date:
        if bounds.time_field or inferred_time_field(known_columns):
            applied.append("time_range")
        else:
            needs_probe.append("time_range")
    if bounds.bbox:
        if bounds.longitude_field and bounds.latitude_field:
            applied.append("bbox")
        else:
            needs_probe.append("bbox")
    if bounds.required_columns:
        if known_columns:
            missing = [column for column in bounds.required_columns if column not in known_columns]
            if missing:
                unsupported.append("required_columns_missing:" + ",".join(missing))
            else:
                applied.append("required_columns")
        else:
            needs_probe.append("required_columns")
    if bounds.max_bytes:
        # HTTPDownloadAdapter consumes this bound at execution time; expose it as
        # enforced so UI/agent payloads do not treat the byte cap as review-only.
        applied.append("max_bytes_enforced")
    if bounds.schema_probe_required and needs_probe:
        next_action = "run_schema_probe_before_precise_bounded_download"
    elif unsupported:
        next_action = "adjust_bounds_or_choose_another_dataset_version"
    else:
        next_action = "ready_for_bounded_download_plan"
    return {
        "applied": applied,
        "needs_schema_probe": needs_probe,
        "unsupported": unsupported,
        "known_columns": sorted(known_columns),
        "next_action": next_action,
    }


def known_column_names(metadata: dict[str, object]) -> set[str]:
    columns = metadata.get("columns")
    names: set[str] = set()
    if isinstance(columns, list):
        for column in columns:
            if not isinstance(column, dict):
                continue
            for key in ("name", "field_name", "id"):
                value = str(column.get(key) or "").strip()
                if value:
                    names.add(value)
    return names


def inferred_time_field(columns: set[str]) -> str:
    preferred = ("time", "date", "datetime", "timestamp", "created_date", "updated_at")
    lowered = {column.lower(): column for column in columns}
    for name in preferred:
        if name in lowered:
            return lowered[name]
    for column in columns:
        lower = column.lower()
        if "time" in lower or "date" in lower:
            return column
    return ""


def bounded_url_for_source(url: str, entry: dict[str, object], bounds: SourceDownloadBounds) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return url
    lower_path = parsed.path.lower()
    source_markers = source_markers_for_entry(entry)
    if "socrata_resource" in source_markers or "/resource/" in lower_path:
        return replace_query_items(url, {"$limit": str(max(1, bounds.sample_limit or 25))})
    if "ncei_search" in source_markers or "/access/services/search/v1/" in lower_path:
        values = {"limit": str(max(1, bounds.sample_limit or 25)), "offset": "0"}
        if bounds.start_date:
            values["startDate"] = bounds.start_date
        if bounds.end_date:
            values["endDate"] = bounds.end_date
        if bounds.bbox:
            values["bbox"] = ",".join(format_bound_number(value) for value in bounds.bbox)
        return replace_query_items(url, values)
    if "stac_collection" in source_markers or lower_path.endswith("/items"):
        values = {"limit": str(max(1, bounds.sample_limit or 1))}
        if bounds.bbox:
            values["bbox"] = ",".join(format_bound_number(value) for value in bounds.bbox)
        if bounds.start_date or bounds.end_date:
            values["datetime"] = f"{bounds.start_date or '..'}/{bounds.end_date or '..'}"
        return replace_query_items(url, values)
    if "cmr_collection" in source_markers or "/search/granules" in lower_path:
        values = {"page_size": str(max(1, bounds.sample_limit or 1))}
        if bounds.start_date or bounds.end_date:
            values["temporal"] = f"{bounds.start_date or ''},{bounds.end_date or ''}"
        if bounds.bbox:
            values["bounding_box"] = ",".join(format_bound_number(value) for value in bounds.bbox)
        return replace_query_items(url, values)
    if "/erddap/tabledap/" in lower_path and bounds.sample_limit:
        return replace_query_items(url, {".limit": str(max(1, bounds.sample_limit))})
    return url


def source_markers_for_entry(entry: dict[str, object]) -> set[str]:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    return {
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("provider_id") or "").strip().lower(),
        str(metadata.get("native_format") or "").strip().lower(),
        str(metadata.get("source_format") or "").strip().lower(),
        str(metadata.get("discovery_source_type") or "").strip().lower(),
    }


def replace_query_items(url: str, values: dict[str, str]) -> str:
    parts = urlsplit(url)
    remove_keys = {key.lower() for key in values}
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in remove_keys]
    query.extend((key, value) for key, value in values.items() if value)
    encoded = urlencode(query, doseq=True, safe="$,:/")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, encoded, parts.fragment))


def format_bound_number(value: float) -> str:
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    return text or "0"


def credential_gate_for_provider(provider: Provider) -> CredentialGate:
    required_env_vars = provider.template_env_vars()
    if not provider_requires_credentials(provider):
        return CredentialGate(
            provider_id=provider.provider_id,
            status="not_required",
            reason="Provider metadata says this source is public or does not require local credentials.",
            required_env_vars=required_env_vars,
        )
    configured = tuple(env_var for env_var in required_env_vars if os.environ.get(env_var))
    if required_env_vars and len(configured) == len(required_env_vars):
        return CredentialGate(
            provider_id=provider.provider_id,
            status="configured",
            reason="All required provider credential environment variables are configured.",
            required_env_vars=required_env_vars,
            configured_env_vars=configured,
        )
    missing = tuple(env_var for env_var in required_env_vars if env_var not in configured)
    detail = ", ".join(missing) if missing else "provider account/API credential"
    return CredentialGate(
        provider_id=provider.provider_id,
        status="missing",
        reason=f"Provider requires credentials before live download: {detail}.",
        required_env_vars=required_env_vars,
        configured_env_vars=configured,
    )


def provider_requires_credentials(provider: Provider) -> bool:
    auth_type = (provider.auth_type or "").strip().lower()
    if not auth_type or auth_type in {"none", "public", "unknown"}:
        return bool(provider.template_env_vars())
    if auth_type.startswith("no_key") or auth_type in {"local_file"}:
        return False
    credential_tokens = ("api_key", "api token", "api_token", "token", "oauth", "account", "login", "credential")
    return bool(provider.template_env_vars()) or any(token in auth_type for token in credential_tokens)


def credential_blocked_plan_entry(entry: dict[str, object], gate: CredentialGate) -> dict[str, object]:
    blocked = dict(entry)
    blocked.pop("download_url", None)
    blocked.pop("target_path", None)
    eligibility = dict(blocked.get("download_eligibility") or {})
    eligibility.update(
        {
            "status": "credential_required",
            "label": "Credential",
            "reason": gate.reason,
            "requires_credential": True,
            "required_env_vars": list(gate.required_env_vars),
            "configured_env_vars": list(gate.configured_env_vars),
        }
    )
    blocked["download_eligibility"] = eligibility
    blocked["plan_status"] = "credential_required"
    review = dict(blocked.get("adapter_review") or {})
    review.update(
        {
            "status": "credential_required",
            "adapter_id": review.get("adapter_id") or "credential_configuration",
            "required_action": "configure_credentials_before_download",
            "reason": gate.reason,
            "required_env_vars": list(gate.required_env_vars),
        }
    )
    blocked["adapter_review"] = review
    blocked["credential_gate"] = gate.to_dict()
    return blocked
