from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from api_launcher.crawlers.fetch import USER_AGENT


UNKNOWN_PATTERN_ID = "unknown"
DEFAULT_PATTERN_MINIMUM_CONFIDENCE = 0.35


SOURCE_TYPE_HINTS: dict[str, str] = {
    "stac": "stac_collections",
    "ckan": "ckan_package_search",
    "erddap": "erddap_all_datasets",
    "socrata": "socrata_catalog_search",
    "ogc": "ogc_api_records",
    "ogc_wms": "ogc_wms_capabilities",
    "cmr": "cmr_collections",
    "ncei": "ncei_search",
    "gbif": "gbif_dataset_search",
    "dataverse": "dataverse_search",
    "zenodo": "zenodo_records_search",
    "datacite": "datacite_dois",
    "openalex": "openalex_works_search",
    "html_file_index": "html_file_index",
}


@dataclass(frozen=True)
class PatternProbeResponse:
    url: str
    text: str
    headers: dict[str, str] | None = None
    status_code: int = 200

    def json_payload(self) -> Any | None:
        content_type = (self.headers or {}).get("content-type", "").lower()
        if "json" not in content_type and not self.text.lstrip().startswith(("{", "[")):
            return None
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            return None


@dataclass(frozen=True)
class SourcePatternCandidate:
    pattern_id: str
    confidence: float
    evidence: tuple[str, ...] = ()
    source_type_hint: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "pattern_id": self.pattern_id,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "source_type_hint": self.source_type_hint,
        }


@dataclass(frozen=True)
class SourcePatternDetection:
    pattern_id: str
    confidence: float
    evidence: tuple[str, ...]
    source_type_hint: str = ""
    candidates: tuple[SourcePatternCandidate, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "pattern_id": self.pattern_id,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "source_type_hint": self.source_type_hint,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


PatternFetcher = Callable[[str, float], PatternProbeResponse | None]
PatternDetector = Callable[[str, PatternFetcher, float], SourcePatternCandidate]

HTML_DATA_FILE_EXTENSION_ALTERNATION = (
    r"csv(?:\.(?:gz|zst))?|geojson(?:\.gz)?|json(?:l|\.gz)?|ndjson(?:\.gz)?|shp\.zip|tar\.gz|zip|nc|cdf|hdf|hdf5|h5|tiff|tif|gpkg|fgb|pmtiles|mbtiles|zarr|grib2?|grb2?|sqlite3?|db|xml|parquet"
)
HTML_DATA_FILE_PATTERN = re.compile(
    r"\.(" + HTML_DATA_FILE_EXTENSION_ALTERNATION + r")(?=$|[?#\"'<>\\s])",
    re.IGNORECASE,
)


def fetch_pattern_probe(url: str, timeout: float) -> PatternProbeResponse | None:
    request = urllib.request.Request(url, headers={"User-Agent": f"{USER_AGENT} source-pattern-detector/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(128 * 1024)
            charset = response.headers.get_content_charset() or "utf-8"
            headers = {key.lower(): value for key, value in response.headers.items()}
            return PatternProbeResponse(
                url=response.geturl(),
                text=data.decode(charset, errors="replace"),
                headers=headers,
                status_code=getattr(response, "status", 200),
            )
    except Exception:
        return None


def detect_source_interface_pattern(
    url: str,
    *,
    fetcher: PatternFetcher = fetch_pattern_probe,
    timeout: float = 8.0,
    minimum_confidence: float = DEFAULT_PATTERN_MINIMUM_CONFIDENCE,
) -> SourcePatternDetection:
    """辨識資料入口範式，只回答「這個 URL 像哪種來源介面」。

    Detector 不下載資料，也不把 NASA/NOAA 這種品牌當作 crawler 類別；它只根據端點、
    payload 欄位、HTML 連結、capabilities 等證據，回傳可交給 crawler adapter 的 pattern。
    """

    guarded_fetcher = guarded_pattern_fetcher(fetcher)
    candidates = tuple(
        sorted(
            (detector(url, guarded_fetcher, timeout) for detector in DETECTORS),
            key=lambda item: item.confidence,
            reverse=True,
        )
    )
    best = candidates[0] if candidates else score_pattern(UNKNOWN_PATTERN_ID, ())
    if best.confidence < minimum_confidence:
        return SourcePatternDetection(
            pattern_id=UNKNOWN_PATTERN_ID,
            confidence=best.confidence,
            evidence=best.evidence,
            candidates=candidates[:3],
        )
    return SourcePatternDetection(
        pattern_id=best.pattern_id,
        confidence=best.confidence,
        evidence=best.evidence,
        source_type_hint=best.source_type_hint,
        candidates=candidates[:3],
    )


def guarded_pattern_fetcher(fetcher: PatternFetcher) -> PatternFetcher:
    def guarded(url: str, timeout: float) -> PatternProbeResponse | None:
        try:
            return fetcher(url, timeout)
        except Exception:
            return None

    return guarded


def detect_stac(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    for probe_url in stac_probe_urls(url):
        data = json_from(fetcher(probe_url, timeout))
        if isinstance(data, dict):
            if "stac_version" in data:
                evidence.append("json_contains_stac_version")
            links = [link for link in data.get("links", []) if isinstance(link, dict)]
            stac_like_link = any(
                str(link.get("rel", "")).lower() in {"root", "self", "parent", "search", "child", "collection"}
                for link in links
            )
            if any(link.get("rel") == "search" for link in links):
                evidence.append("json_has_search_link")
            if "collections" in data or any("collections" in str(link.get("href", "")) for link in links):
                evidence.append("json_references_collections")
            if "collections" in data and probe_url.rstrip("/").endswith("/collections") and stac_like_link:
                evidence.append("stac_collections_endpoint")
            if evidence:
                break
    return score_pattern("stac", evidence)


def detect_ckan(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    for probe_url in ckan_probe_urls(url):
        response = fetcher(probe_url, timeout)
        data = json_from(response)
        if isinstance(data, dict):
            if data.get("success") is True and "result" in data:
                evidence.append("ckan_package_search_success")
            if response is not None and "/api/3/action/" in response.url:
                evidence.append("ckan_api_action_endpoint")
            if evidence:
                break
    return score_pattern("ckan", evidence)


def detect_erddap(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    parsed = urllib.parse.urlparse(url)
    if "/erddap" in parsed.path.lower():
        evidence.append("url_path_contains_erddap")
    response = fetcher(erddap_info_index_url(url), timeout)
    data = json_from(response)
    if isinstance(data, dict) and "table" in data:
        evidence.append("erddap_info_index_table")
    if response is not None and "erddap" in response.text[:2000].lower():
        evidence.append("response_mentions_erddap")
    return score_pattern("erddap", evidence)


def detect_socrata(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.startswith("data.") or "socrata" in parsed.netloc:
        evidence.append("host_looks_like_socrata")
    for probe_url in socrata_probe_urls(url):
        data = json_from(fetcher(probe_url, timeout))
        if isinstance(data, list):
            evidence.append("socrata_views_returns_list")
            break
        if isinstance(data, dict) and "error" not in data:
            evidence.append("socrata_views_json_response")
            break
    return score_pattern("socrata", evidence)


def detect_ogc(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    api_evidence: list[str] = []
    wms_evidence: list[str] = []
    for probe_url in ogc_api_probe_urls(url):
        data = json_from(fetcher(probe_url, timeout))
        if isinstance(data, dict):
            conforms_to = data.get("conformsTo", [])
            if "conformsTo" in data:
                api_evidence.append("json_contains_conforms_to")
            if "collections" in data:
                api_evidence.append("json_contains_collections")
            if any("ogcapi" in str(item).lower() or "opengis" in str(item).lower() for item in conforms_to):
                api_evidence.append("conforms_to_mentions_ogc")
        if len(unique_evidence(api_evidence)) >= 3:
            break
    cap_response = fetcher(wms_capabilities_probe_url(url), timeout)
    if cap_response is not None and ("GetCapabilities" in cap_response.text[:8000] or "WMS_Capabilities" in cap_response.text[:8000]):
        wms_evidence.append("wms_get_capabilities_response")
        if "WMS_Capabilities" in cap_response.text[:8000] or "opengis.net/wms" in cap_response.text[:8000].lower():
            wms_evidence.append("wms_capabilities_document")
    api_evidence = unique_evidence(api_evidence)
    wms_evidence = unique_evidence(wms_evidence)
    if api_evidence:
        return score_pattern("ogc", api_evidence + wms_evidence)
    if wms_evidence:
        return score_pattern("ogc_wms", wms_evidence)
    return score_pattern("ogc", ())


def detect_cmr(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    parsed = urllib.parse.urlparse(url)
    if "cmr.earthdata.nasa.gov" in parsed.netloc:
        evidence.append("host_is_nasa_cmr")
    else:
        return score_pattern("cmr", evidence)
    probe_url = "https://cmr.earthdata.nasa.gov/search/collections.json?page_size=1"
    data = json_from(fetcher(probe_url, timeout))
    if isinstance(data, dict) and "feed" in data:
        evidence.append("cmr_collections_feed")
    return score_pattern("cmr", evidence)


def detect_ncei(url: str, _fetcher: PatternFetcher, _timeout: float) -> SourcePatternCandidate:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    evidence: list[str] = []
    if "ncei.noaa.gov" in parsed.netloc.lower():
        evidence.append("host_is_noaa_ncei")
    if "/access/services/search/v1" in path:
        evidence.append("ncei_search_api_path")
    return score_pattern("ncei", evidence)


def detect_gbif(url: str, _fetcher: PatternFetcher, _timeout: float) -> SourcePatternCandidate:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    evidence: list[str] = []
    if parsed.netloc.lower() == "api.gbif.org":
        evidence.append("host_is_gbif_api")
    if "/v1/dataset" in path:
        evidence.append("gbif_dataset_api_path")
    return score_pattern("gbif", evidence)


def detect_dataverse(url: str, _fetcher: PatternFetcher, _timeout: float) -> SourcePatternCandidate:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    evidence: list[str] = []
    if "dataverse" in parsed.netloc.lower():
        evidence.append("host_mentions_dataverse")
    if path.endswith("/api/search") or "/api/search/" in path:
        evidence.append("dataverse_search_api_path")
    return score_pattern("dataverse", evidence)


def detect_zenodo(url: str, _fetcher: PatternFetcher, _timeout: float) -> SourcePatternCandidate:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    evidence: list[str] = []
    if parsed.netloc.lower().endswith("zenodo.org"):
        evidence.append("host_is_zenodo")
    if path.startswith("/api/records"):
        evidence.append("zenodo_records_api_path")
    return score_pattern("zenodo", evidence)


def detect_datacite(url: str, _fetcher: PatternFetcher, _timeout: float) -> SourcePatternCandidate:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    evidence: list[str] = []
    if parsed.netloc.lower() == "api.datacite.org":
        evidence.append("host_is_datacite_api")
    if path.startswith("/dois"):
        evidence.append("datacite_dois_api_path")
    return score_pattern("datacite", evidence)


def detect_openalex(url: str, _fetcher: PatternFetcher, _timeout: float) -> SourcePatternCandidate:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    evidence: list[str] = []
    if parsed.netloc.lower() == "api.openalex.org":
        evidence.append("host_is_openalex_api")
    if path.startswith("/works"):
        evidence.append("openalex_works_api_path")
    return score_pattern("openalex", evidence)


def detect_html_file_index(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    response = fetcher(url, timeout)
    if response is None:
        return score_pattern("html_file_index", evidence)
    text = response.text.lower()
    if "<a " in text and "href=" in text:
        evidence.append("html_contains_links")
    hits = html_data_file_extension_hits(text)
    if hits:
        evidence.append("html_mentions_data_file_extensions:" + ",".join(hits[:5]))
    return score_pattern("html_file_index", evidence)


def html_data_file_extension_hits(text: str) -> tuple[str, ...]:
    # HTML index 是 fallback detector；這裡只辨識檔案線索，不解析下載內容。
    seen: set[str] = set()
    hits: list[str] = []
    for match in HTML_DATA_FILE_PATTERN.finditer(text):
        extension = "." + match.group(1).lower()
        if extension in seen:
            continue
        seen.add(extension)
        hits.append(extension)
    return tuple(hits)


def score_pattern(pattern_id: str, evidence: list[str] | tuple[str, ...]) -> SourcePatternCandidate:
    confidence = min(0.25 * len(evidence), 0.95)
    return SourcePatternCandidate(
        pattern_id=pattern_id,
        confidence=confidence,
        evidence=tuple(evidence),
        source_type_hint=SOURCE_TYPE_HINTS.get(pattern_id, ""),
    )


def json_from(response: PatternProbeResponse | None) -> Any | None:
    return response.json_payload() if response is not None else None


def join_url(base: str, relative: str) -> str:
    parsed = urllib.parse.urlparse(base)
    clean_base = urllib.parse.urlunparse(parsed._replace(query="", fragment=""))
    return urllib.parse.urljoin(clean_base.rstrip("/") + "/", relative)


def origin_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/") + "/"
    return f"{parsed.scheme}://{parsed.netloc}/"


def unique_urls(*urls: str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return tuple(ordered)


def unique_evidence(evidence: list[str]) -> list[str]:
    return list(dict.fromkeys(evidence))


def stac_probe_urls(url: str) -> tuple[str, ...]:
    return unique_urls(url, join_url(url, "collections"))


def erddap_info_index_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path_lower = parsed.path.lower()
    if "/erddap" in path_lower:
        erddap_start = path_lower.index("/erddap")
        base_path = parsed.path[:erddap_start]
        base = urllib.parse.urlunparse(parsed._replace(path=base_path, query="", fragment="")).rstrip("/")
    else:
        base = url.rstrip("/")
    return base + "/erddap/info/index.json"


def ckan_probe_urls(url: str) -> tuple[str, ...]:
    endpoint = "api/3/action/package_search?rows=1"
    return unique_urls(join_url(url, endpoint), urllib.parse.urljoin(origin_url(url), endpoint))


def socrata_probe_urls(url: str) -> tuple[str, ...]:
    endpoint = "api/views.json?limit=1"
    return unique_urls(join_url(url, endpoint), urllib.parse.urljoin(origin_url(url), endpoint))


def ogc_api_probe_urls(url: str) -> tuple[str, ...]:
    return unique_urls(
        url,
        join_url(url, "conformance"),
        join_url(url, "collections"),
        urllib.parse.urljoin(origin_url(url), "conformance"),
        urllib.parse.urljoin(origin_url(url), "collections"),
    )


def wms_capabilities_probe_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query_lower = {key.lower(): value for key, value in query_pairs}
    service = query_lower.get("service", "").lower()
    request = query_lower.get("request", "").lower()
    if service == "wms" and request == "getcapabilities":
        return urllib.parse.urlunparse(parsed._replace(fragment="")) if parsed.fragment else url
    # URL fragment 不會送到伺服器；先用 parser 合成 query，避免產生 /wms#x?service=...
    filtered_pairs = [(key, value) for key, value in query_pairs if key.lower() not in {"service", "request"}]
    filtered_pairs.extend([("service", "WMS"), ("request", "GetCapabilities")])
    return urllib.parse.urlunparse(
        parsed._replace(
            query=urllib.parse.urlencode(filtered_pairs),
            fragment="",
        )
    )


DETECTORS: tuple[PatternDetector, ...] = (
    detect_stac,
    detect_ckan,
    detect_erddap,
    detect_socrata,
    detect_ogc,
    detect_cmr,
    detect_ncei,
    detect_gbif,
    detect_dataverse,
    detect_zenodo,
    detect_datacite,
    detect_openalex,
    detect_html_file_index,
)


__all__ = [
    "DEFAULT_PATTERN_MINIMUM_CONFIDENCE",
    "HTML_DATA_FILE_EXTENSION_ALTERNATION",
    "PatternProbeResponse",
    "SourcePatternCandidate",
    "SourcePatternDetection",
    "UNKNOWN_PATTERN_ID",
    "detect_source_interface_pattern",
    "fetch_pattern_probe",
]
