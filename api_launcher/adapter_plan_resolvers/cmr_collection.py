from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Callable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.downloads.eligibility import DownloadEligibility
from api_launcher.models import Dataset
from api_launcher.plans import dataset_download_target_path, dataset_import_plan_entry


FirstText = Callable[..., str]

CMR_GRANULE_RESOLVER_ID = "cmr_bounded_granule_search_resolver"
CMR_GRANULE_SAMPLE_LIMIT = 1


def cmr_bounded_granule_search_entry(
    entry: dict[str, object],
    plan_index: int,
    downloads_root: str | Path,
    *,
    first_text: FirstText,
    resolver_id: str = CMR_GRANULE_RESOLVER_ID,
    sample_limit: int = CMR_GRANULE_SAMPLE_LIMIT,
) -> dict[str, object]:
    # CMR collection resolver 只抓 granule metadata 小樣本，不直接下載科學資料檔。
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = dict(version_meta.get("metadata") or {}) if isinstance(version_meta.get("metadata"), dict) else {}
    sample_url, source_url, concept_id = cmr_bounded_granule_search_url(
        entry,
        version_meta,
        option_metadata,
        first_text=first_text,
        sample_limit=sample_limit,
    )
    if not sample_url:
        return {}

    provider_id = first_text(entry.get("provider_id"), "unknown_provider")
    dataset_uid = first_text(entry.get("dataset_uid"), version_meta.get("dataset_uid"), concept_id)
    dataset_id = first_text(entry.get("dataset_id"), version_meta.get("dataset_id"), concept_id, "cmr_collection")
    version = first_text(version_meta.get("version"), entry.get("version"), "discovered")
    sample_version = f"{version}-cmr-granules-sample" if version else "cmr-granules-sample"
    data_family = str(option_metadata.get("data_family") or entry.get("data_type") or "raster_or_grid")
    dataset = Dataset(
        dataset_uid=dataset_uid,
        provider_id=provider_id,
        dataset_id=dataset_id,
        title=first_text(entry.get("dataset_title"), entry.get("name"), dataset_id),
        categories=(
            tuple(str(value) for value in entry.get("categories", ()) if str(value).strip())
            if isinstance(entry.get("categories"), (list, tuple))
            else ()
        ),
        data_type=data_family,
        native_format="json",
        geographic_scope=str(entry.get("geographic_scope") or ""),
        landing_url=first_text(entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url")),
        api_url=sample_url,
        license_url=str(entry.get("license_url") or ""),
        version=sample_version,
        metadata={
            **option_metadata,
            "data_family": data_family,
            "bounded_query": {
                "resolver_id": resolver_id,
                "source_url": source_url,
                "sample_limit": sample_limit,
                "cmr_concept_id": concept_id,
            },
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset_uid,
        dataset_id=dataset_id,
        label="CMR bounded granule metadata sample JSON",
        version=sample_version,
        status="resolved_sample",
        download_url=sample_url,
        landing_url=dataset.landing_url,
        update_strategy="sample_then_review",
        notes="Bounded NASA CMR granule metadata sample generated from collection metadata; this downloads metadata only, not science data assets.",
        metadata={"native_format": "json", "resolver_id": resolver_id, "cmr_concept_id": concept_id},
    )
    eligibility = DownloadEligibility(
        status="direct_download",
        label="Bounded API",
        reason=f"The NASA CMR collection was resolved into a bounded granule metadata request with page_size={sample_limit}.",
        direct_url=sample_url,
    )
    resolved = dict(entry)
    resolved.update(
        {
            "dataset_uid": dataset_uid,
            "dataset_id": dataset_id,
            "dataset_title": dataset.title,
            "dataset_version": option.to_plan_metadata(),
            "source_format": "json",
            "target": "local_file_asset",
            "use_staging": True,
            "download_eligibility": eligibility.to_dict(),
            "download_url": sample_url,
            "target_path": dataset_download_target_path(provider_id, dataset, option, downloads_root).as_posix(),
            "import_plan": dataset_import_plan_entry(dataset, option, eligibility),
            "plan_status": "planned",
            "adapter_resolution": {
                "resolver_id": resolver_id,
                "original_plan_index": plan_index,
                "sample_url": sample_url,
                "policy": "bounded_granule_metadata_sample_only",
                "sample_limit": sample_limit,
                "source_url": source_url,
                "cmr_concept_id": concept_id,
            },
        }
    )
    resolved.pop("adapter_review", None)
    resolved.pop("adapter_review_url", None)
    return resolved


def cmr_bounded_granule_search_url(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
    sample_limit: int = CMR_GRANULE_SAMPLE_LIMIT,
) -> tuple[str, str, str]:
    if not entry_is_cmr_collection(entry, option_metadata):
        return "", "", ""
    concept_id = first_text(
        option_metadata.get("cmr_concept_id"),
        option_metadata.get("collection_concept_id"),
        option_metadata.get("concept_id"),
    )
    if not concept_id:
        return "", "", ""
    for raw_url in cmr_candidate_urls(entry, version_meta, option_metadata, first_text=first_text):
        sample_url = bounded_cmr_granules_url(raw_url, concept_id, sample_limit=sample_limit)
        if sample_url:
            return sample_url, raw_url, concept_id
    return "", "", ""


def entry_is_cmr_collection(entry: dict[str, object], option_metadata: dict[str, object]) -> bool:
    markers = {
        str(entry.get("provider_id") or "").strip().lower(),
        str(entry.get("source_format") or "").strip().lower(),
        str(entry.get("data_type") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    if {"cmr_collection", "cmr_collections"} & markers:
        return True
    return any("cmr" in marker for marker in markers) and bool(
        option_metadata.get("cmr_concept_id")
        or option_metadata.get("collection_concept_id")
        or option_metadata.get("concept_id")
    )


def cmr_candidate_urls(
    entry: dict[str, object],
    version_meta: dict[str, object],
    option_metadata: dict[str, object],
    *,
    first_text: FirstText,
) -> list[str]:
    candidates = [
        option_metadata.get("cmr_granules_url"),
        option_metadata.get("api_url"),
        version_meta.get("download_url"),
        (entry.get("adapter_review") or {}).get("source_url") if isinstance(entry.get("adapter_review"), dict) else "",
        entry.get("adapter_review_url"),
        entry.get("api_base_url"),
        option_metadata.get("source_url"),
        entry.get("landing_url"),
        version_meta.get("landing_url"),
        entry.get("docs_url"),
    ]
    urls: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = first_text(candidate)
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def bounded_cmr_granules_url(raw_url: str, concept_id: str, *, sample_limit: int = CMR_GRANULE_SAMPLE_LIMIT) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    if lower_path.endswith("/search/collections.json"):
        path = f"{path.rsplit('/', 1)[0]}/granules.json"
    elif lower_path.endswith("/search/collections"):
        path = f"{path.rsplit('/', 1)[0]}/granules.json"
    elif lower_path.endswith("/search/granules"):
        path = f"{path}.json"
    elif not lower_path.endswith("/search/granules.json"):
        return ""

    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"page_size", "page_num", "offset"}
    ]
    keys = {key.lower() for key, _value in query_pairs}
    if "collection_concept_id" not in keys:
        query_pairs.insert(0, ("collection_concept_id", concept_id))
    query_pairs.append(("page_size", str(sample_limit)))
    query = urllib.parse.urlencode(query_pairs, doseq=True, safe=",")
    return urllib.parse.urlunparse(parsed._replace(path=path, query=query, fragment=""))
