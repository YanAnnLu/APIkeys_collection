from __future__ import annotations

import urllib.parse


def resource_is_ogc_records_metadata_link(entry: dict[str, object], resource: dict[str, object]) -> bool:
    if not entry_is_ogc_records_candidate(entry):
        return False
    rel = str(resource.get("rel") or "").strip().lower()
    return rel in {
        "alternate",
        "canonical",
        "collection",
        "describedby",
        "items",
        "parent",
        "related",
        "root",
        "self",
        "service-desc",
        "service-doc",
    }


def resource_is_cmr_metadata_link(entry: dict[str, object], resource: dict[str, object], url: str) -> bool:
    # CMR links 常把 metadata、browse、OPeNDAP、service 與 data 混在 links 陣列內；這裡只做排除判斷。
    if not (entry_is_cmr_candidate(entry) or resource_url_is_cmr_api_metadata(url)):
        return False
    rels = resource_link_rels(resource)
    if any(cmr_link_rel_is_data(rel) for rel in rels):
        return False
    if any(cmr_link_rel_is_metadata(rel) for rel in rels):
        return True
    if resource_value_is_truthy(resource.get("inherited")):
        return True
    return resource_url_is_cmr_api_metadata(url)


def entry_is_cmr_candidate(entry: dict[str, object]) -> bool:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    markers = [
        str(entry.get("provider_id") or ""),
        str(entry.get("source_format") or ""),
        str(entry.get("data_type") or ""),
        str(option_metadata.get("native_format") or ""),
        str(option_metadata.get("source_format") or ""),
        str(option_metadata.get("discovery_source_type") or ""),
        str(option_metadata.get("source_type") or ""),
    ]
    categories = entry.get("categories")
    if isinstance(categories, (list, tuple)):
        markers.extend(str(value) for value in categories)
    review = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
    markers.append(str(review.get("adapter_id") or ""))
    return any("cmr" in marker.strip().lower() for marker in markers)


def resource_link_rels(resource: dict[str, object]) -> list[str]:
    rel = resource.get("rel")
    if isinstance(rel, str):
        return [rel]
    if isinstance(rel, list):
        return [str(value) for value in rel if str(value).strip()]
    return []


def cmr_link_rel_is_data(rel: str) -> bool:
    token = cmr_link_rel_token(rel)
    return token in {"data", "download", "enclosure"}


def cmr_link_rel_is_metadata(rel: str) -> bool:
    token = cmr_link_rel_token(rel)
    return token in {
        "alternate",
        "browse",
        "canonical",
        "collection",
        "describedby",
        "documentation",
        "metadata",
        "opendap",
        "parent",
        "related",
        "root",
        "self",
        "service",
        "service-desc",
        "service-doc",
    }


def cmr_link_rel_token(rel: str) -> str:
    cleaned = rel.strip().lower().rstrip("#/")
    if not cleaned:
        return ""
    return cleaned.rsplit("/", 1)[-1]


def resource_value_is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def resource_url_is_cmr_api_metadata(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != "cmr.earthdata.nasa.gov":
        return False
    path = parsed.path.rstrip("/").lower()
    return path.startswith("/search/") and (
        path.endswith("/collections")
        or path.endswith("/collections.json")
        or path.endswith("/granules")
        or path.endswith("/granules.json")
        or "/concepts/" in path
    )


def entry_is_ogc_records_candidate(entry: dict[str, object]) -> bool:
    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    option_metadata = version_meta.get("metadata") if isinstance(version_meta.get("metadata"), dict) else {}
    markers = {
        str(entry.get("source_format") or "").strip().lower(),
        str(option_metadata.get("native_format") or "").strip().lower(),
        str(option_metadata.get("source_format") or "").strip().lower(),
        str(option_metadata.get("discovery_source_type") or "").strip().lower(),
        str(option_metadata.get("source_type") or "").strip().lower(),
    }
    return "ogc_api_records" in markers or "ogc_record" in markers
