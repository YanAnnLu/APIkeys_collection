from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Iterable

from api_launcher.db import utc_now_iso
from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility, assess_provider_download, looks_like_direct_download
from api_launcher.models import Dataset, Provider
from api_launcher.downloads.staging import safe_path_part


def build_download_plan(
    providers: Iterable[Provider],
    plan_name: str,
    downstream_renderer: str = "taichi_global_bathymetry.py",
) -> dict[str, object]:
    provider_list = list(providers)
    return {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "plan_name": plan_name.strip() or "Untitled download plan",
        "role": "download plan only; no bulk data has been downloaded",
        "downstream_renderer": downstream_renderer,
        "summary": {
            "provider_count": len(provider_list),
            "status": "planned",
        },
        "download_policy": {
            "io_model": "nonblocking",
            "max_parallel_jobs": 3,
            "supports_pause": True,
            "supports_resume": True,
            "supports_retry": True,
        },
        "providers": [provider_plan_entry(provider) for provider in provider_list],
    }


def provider_plan_entry(provider: Provider) -> dict[str, object]:
    eligibility = assess_provider_download(provider)
    return {
        "provider_id": provider.provider_id,
        "name": provider.name,
        "owner": provider.owner,
        "categories": provider.categories,
        "auth_type": provider.auth_type,
        "key_env_var": provider.key_env_var,
        "docs_url": provider.docs_url,
        "api_base_url": provider.api_base_url,
        "signup_url": provider.signup_url,
        "geographic_scope": provider.geographic_scope,
        "plan_status": "planned",
        "priority": "normal",
        "target": "local_dataset_or_database",
        "download_eligibility": eligibility.to_dict(),
        "notes": provider.notes,
    }


def build_dataset_download_plan(
    entries: Iterable[dict[str, object]],
    plan_name: str,
    downstream_renderer: str = "taichi_global_bathymetry.py",
) -> dict[str, object]:
    entry_list = list(entries)
    provider_ids = {str(entry.get("provider_id") or "") for entry in entry_list if entry.get("provider_id")}
    direct_count = sum(
        1
        for entry in entry_list
        if isinstance(entry.get("download_eligibility"), dict)
        and entry["download_eligibility"].get("status") == "direct_download"
    )
    return {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "plan_name": plan_name.strip() or "Untitled dataset download plan",
        "role": "dataset download plan only; no bulk data has been downloaded",
        "downstream_renderer": downstream_renderer,
        "summary": {
            "provider_count": len(provider_ids),
            "dataset_version_count": len(entry_list),
            "direct_download_count": direct_count,
            "review_required_count": len(entry_list) - direct_count,
            "status": "planned",
        },
        "download_policy": {
            "io_model": "nonblocking",
            "max_parallel_jobs": 3,
            "supports_pause": True,
            "supports_resume": True,
            "supports_retry": True,
        },
        "providers": entry_list,
    }


def provider_dataset_version_plan_entry(
    provider: Provider,
    dataset: Dataset,
    option: DatasetVersionOption,
    downloads_root: str | Path = "downloads",
) -> dict[str, object]:
    eligibility = assess_dataset_version_download(option)
    import_plan = dataset_import_plan_entry(dataset, option, eligibility)
    entry = provider_plan_entry(provider)
    entry.update(
        {
            "dataset_uid": dataset.dataset_uid,
            "dataset_id": dataset.dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": dataset.native_format or "unknown",
            "data_type": dataset.data_type,
            "target": "local_file_asset",
            "use_staging": True,
            "download_eligibility": eligibility.to_dict(),
            "import_plan": import_plan,
            "plan_status": "planned" if eligibility.status == "direct_download" else "needs_adapter_review",
        }
    )
    if option.landing_url:
        entry["landing_url"] = option.landing_url
    if eligibility.status == "direct_download":
        entry["download_url"] = option.download_url
        entry["target_path"] = dataset_download_target_path(provider.provider_id, dataset, option, downloads_root).as_posix()
    elif option.download_url:
        entry["adapter_review_url"] = option.download_url
    if eligibility.status != "direct_download" or import_plan.get("status") in {"requires_unpack_or_adapter", "manual_review_required"}:
        entry["adapter_review"] = adapter_review_plan_entry(provider, dataset, option, eligibility, import_plan)
    return entry


def adapter_review_plan_entry(
    provider: Provider,
    dataset: Dataset,
    option: DatasetVersionOption,
    eligibility: DownloadEligibility,
    import_plan: dict[str, object],
) -> dict[str, object]:
    adapter_id = str(dataset.metadata.get("adapter") or "").strip() or f"{provider.provider_id}_adapter"
    source_url = option.download_url or option.landing_url or dataset.api_url or dataset.landing_url or provider.api_base_url or provider.docs_url
    source_kind = "direct_file_needs_transform" if eligibility.status == "direct_download" else "api_landing_or_selector"
    required_action = "unpack_or_transform_downloaded_payload" if eligibility.status == "direct_download" else "resolve_source_to_direct_download_entries"
    return {
        "status": "needs_adapter_review",
        "adapter_id": adapter_id,
        "source_url": source_url,
        "landing_url": option.landing_url or dataset.landing_url or provider.docs_url,
        "source_kind": source_kind,
        "required_action": required_action,
        "expected_output": "direct_download_plan_entries_with_manifests_and_import_plan",
        "reason": str(import_plan.get("reason") or eligibility.reason),
    }


def dataset_import_plan_entry(
    dataset: Dataset,
    option: DatasetVersionOption,
    eligibility: DownloadEligibility,
) -> dict[str, object]:
    source_format = (dataset.native_format or str((option.metadata or {}).get("native_format") or "")).strip().lower()
    data_family = str(dataset.metadata.get("data_family") or dataset.data_type or "").strip()
    base = {
        "target_engine": "sqlite_mvp",
        "source_format": source_format or "unknown",
        "data_family": data_family or "unknown",
        "table_hint": safe_path_part(f"{dataset.provider_id}_{dataset.dataset_id}").lower(),
        "post_download": True,
    }
    if eligibility.status != "direct_download":
        return {
            **base,
            "status": "adapter_review_required",
            "reason": "Download/import must wait until an adapter turns this catalog/API/landing URL into bounded files.",
        }
    if source_format in {"csv", "csv.gz"}:
        return {
            **base,
            "status": "supported_after_download",
            "importer": "csv_to_sqlite",
            "reason": "CSV/CSV.GZ manifests can be imported by the current SQLite MVP importer after download verification.",
        }
    if source_format in {"json", "jsonl", "geojson"}:
        return {
            **base,
            "status": "supported_after_download",
            "importer": "json_to_sqlite",
            "reason": "JSON/JSONL/GeoJSON manifests can be imported by the current SQLite MVP importer after download verification.",
        }
    if source_format in {"csv.zst", "zst", "zip", "tar", "tar.gz", "7z", "bz2", "xz"}:
        return {
            **base,
            "status": "requires_unpack_or_adapter",
            "reason": "The file can be downloaded, but the MVP importer needs a decompression/extraction step before curated SQLite import.",
        }
    return {
        **base,
        "status": "manual_review_required",
        "reason": "The file can be downloaded, but no MVP importer is registered for this source format yet.",
    }


def assess_dataset_version_download(option: DatasetVersionOption) -> DownloadEligibility:
    url = option.download_url.strip()
    if not url:
        return DownloadEligibility(
            status="unavailable",
            label="Unavailable",
            reason="This dataset version does not expose a download URL yet.",
            requires_adapter=True,
        )
    if looks_like_direct_download(url):
        return DownloadEligibility(
            status="direct_download",
            label="Direct",
            reason="The dataset version URL looks like a direct file URL.",
            direct_url=url,
        )
    return DownloadEligibility(
        status="adapter_required",
        label="Adapter",
        reason="The dataset version URL is a landing page, API endpoint, or selector rather than a direct file.",
        requires_adapter=True,
    )


def dataset_download_target_path(
    provider_id: str,
    dataset: Dataset,
    option: DatasetVersionOption,
    downloads_root: str | Path = "downloads",
) -> Path:
    return (
        Path(downloads_root)
        / safe_path_part(provider_id)
        / safe_path_part(dataset.dataset_id)
        / safe_path_part(option.version or "unversioned")
        / dataset_download_filename(dataset, option)
    )


def dataset_download_filename(dataset: Dataset, option: DatasetVersionOption) -> str:
    parsed = urllib.parse.urlparse(option.download_url)
    filename = Path(urllib.parse.unquote(parsed.path)).name
    if filename and "." in filename:
        return safe_path_part(filename)
    stem = safe_path_part(f"{dataset.dataset_id}-{option.version or 'unversioned'}")
    return f"{stem}{extension_for_native_format(dataset.native_format)}"


def extension_for_native_format(native_format: str) -> str:
    normalized = native_format.strip().lower().replace("_", "-")
    if not normalized:
        return ".download"
    known = {
        "csv": ".csv",
        "csv.gz": ".csv.gz",
        "csv.zst": ".csv.zst",
        "geojson": ".geojson",
        "json": ".json",
        "netcdf": ".nc",
        "sqlite": ".sqlite",
        "sqlite3": ".sqlite",
        "parquet": ".parquet",
        "zarr": ".zarr",
        "zst": ".zst",
    }
    if normalized in known:
        return known[normalized]
    if normalized.startswith("."):
        clean = safe_path_part(normalized[1:])
        return f".{clean}" if clean else ".download"
    if "." in normalized:
        return f".{safe_path_part(normalized)}"
    return ".download"
