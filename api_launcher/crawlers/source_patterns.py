from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from api_launcher.crawlers.fetch import USER_AGENT


SOURCE_TYPE_HINTS: dict[str, str] = {
    "stac": "stac_collections",
    "ckan": "ckan_package_search",
    "erddap": "erddap_all_datasets",
    "socrata": "socrata_catalog_search",
    "ogc": "ogc_api_records",
    "cmr": "cmr_collections",
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
    minimum_confidence: float = 0.35,
) -> SourcePatternDetection:
    """辨識資料入口範式，只回答「這個 URL 像哪種來源介面」。

    Detector 不下載資料，也不把 NASA/NOAA 這種品牌當作 crawler 類別；它只根據端點、
    payload 欄位、HTML 連結、capabilities 等證據，回傳可交給 crawler adapter 的 pattern。
    """

    candidates = tuple(sorted((detector(url, fetcher, timeout) for detector in DETECTORS), key=lambda item: item.confidence, reverse=True))
    best = candidates[0] if candidates else score_pattern("unknown", ())
    if best.confidence < minimum_confidence:
        return SourcePatternDetection(
            pattern_id="unknown",
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


def detect_stac(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    data = json_from(fetcher(url, timeout))
    if isinstance(data, dict):
        if "stac_version" in data:
            evidence.append("json_contains_stac_version")
        links = [link for link in data.get("links", []) if isinstance(link, dict)]
        if any(link.get("rel") == "search" for link in links):
            evidence.append("json_has_search_link")
        if "collections" in data or any("collections" in str(link.get("href", "")) for link in links):
            evidence.append("json_references_collections")
    return score_pattern("stac", evidence)


def detect_ckan(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    probe_url = join_url(url, "api/3/action/package_search?rows=1")
    response = fetcher(probe_url, timeout)
    data = json_from(response)
    if isinstance(data, dict):
        if data.get("success") is True and "result" in data:
            evidence.append("ckan_package_search_success")
        if response is not None and "/api/3/action/" in response.url:
            evidence.append("ckan_api_action_endpoint")
    return score_pattern("ckan", evidence)


def detect_erddap(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    if "/erddap" in urllib.parse.urlparse(url).path.lower():
        evidence.append("url_path_contains_erddap")
    base = url.split("/erddap", 1)[0] if "/erddap" in url else url.rstrip("/")
    response = fetcher(base.rstrip("/") + "/erddap/info/index.json", timeout)
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
    data = json_from(fetcher(url.rstrip("/") + "/api/views.json?limit=1", timeout))
    if isinstance(data, list):
        evidence.append("socrata_views_returns_list")
    elif isinstance(data, dict) and "error" not in data:
        evidence.append("socrata_views_json_response")
    return score_pattern("socrata", evidence)


def detect_ogc(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    data = json_from(fetcher(url, timeout))
    if isinstance(data, dict):
        conforms_to = data.get("conformsTo", [])
        if "conformsTo" in data:
            evidence.append("json_contains_conforms_to")
        if "collections" in data:
            evidence.append("json_contains_collections")
        if any("ogcapi" in str(item).lower() or "opengis" in str(item).lower() for item in conforms_to):
            evidence.append("conforms_to_mentions_ogc")
    cap_response = fetcher(url + ("&" if urllib.parse.urlparse(url).query else "?") + "service=WMS&request=GetCapabilities", timeout)
    if cap_response is not None and ("GetCapabilities" in cap_response.text[:8000] or "WMS_Capabilities" in cap_response.text[:8000]):
        evidence.append("wms_get_capabilities_response")
        if "WMS_Capabilities" in cap_response.text[:8000] or "opengis.net/wms" in cap_response.text[:8000].lower():
            evidence.append("wms_capabilities_document")
    return score_pattern("ogc", evidence)


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


def detect_html_file_index(url: str, fetcher: PatternFetcher, timeout: float) -> SourcePatternCandidate:
    evidence: list[str] = []
    response = fetcher(url, timeout)
    if response is None:
        return score_pattern("html_file_index", evidence)
    text = response.text.lower()
    if "<a " in text and "href=" in text:
        evidence.append("html_contains_links")
    file_extensions = (".csv", ".zip", ".nc", ".hdf", ".h5", ".tif", ".tiff", ".json", ".xml", ".parquet")
    hits = tuple(extension for extension in file_extensions if extension in text)
    if hits:
        evidence.append("html_mentions_data_file_extensions:" + ",".join(hits[:5]))
    return score_pattern("html_file_index", evidence)


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
    return urllib.parse.urljoin(base.rstrip("/") + "/", relative)


DETECTORS: tuple[PatternDetector, ...] = (
    detect_stac,
    detect_ckan,
    detect_erddap,
    detect_socrata,
    detect_ogc,
    detect_cmr,
    detect_html_file_index,
)


__all__ = [
    "PatternProbeResponse",
    "SourcePatternCandidate",
    "SourcePatternDetection",
    "detect_source_interface_pattern",
    "fetch_pattern_probe",
]
