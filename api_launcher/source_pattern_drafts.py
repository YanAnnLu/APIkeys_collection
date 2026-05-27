from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from pathlib import Path

from api_launcher.crawlers.dataset_sources import (
    SUPPORTED_DATASET_SOURCE_TYPES,
    append_dataset_discovery_source,
    source_to_dict,
)
from api_launcher.crawlers.source_patterns import (
    DEFAULT_PATTERN_MINIMUM_CONFIDENCE,
    HTML_DATA_FILE_EXTENSION_ALTERNATION,
    PatternFetcher,
    SourcePatternDetection,
    UNKNOWN_PATTERN_ID,
    detect_source_interface_pattern,
)
from api_launcher.crawlers.source_type_registry import source_type_is_file_index
from api_launcher.crawlers.types import DatasetDiscoverySource
from api_launcher.discovery_drafts import (
    LOCAL_DISCOVERY_AUDIT_COMMAND,
    LOCAL_DISCOVERY_AUDIT_NEXT_ACTION,
    normalize_endpoint_for_source_type,
)


SourcePatternDraftDetector = Callable[[str], SourcePatternDetection]
DEFAULT_HTML_FILE_INDEX_REGEX = (
    rf"(?i)\.({HTML_DATA_FILE_EXTENSION_ALTERNATION})(?:$|[?#])"
)
SOURCE_PATTERN_DRAFT_REVIEW_NEXT_ACTION = "review_source_profile_or_add_detector"
SOURCE_PATTERN_DRAFT_NEXT_ACTION_LABELS = {
    SOURCE_PATTERN_DRAFT_REVIEW_NEXT_ACTION: {
        "zh_TW": "檢查來源入口；若它是常用範式，補 detector 或 source profile",
        "en": "Review the source URL; add a detector or source profile if it is a reusable pattern.",
    },
    LOCAL_DISCOVERY_AUDIT_NEXT_ACTION: {
        "zh_TW": "先執行本機 discovery audit，通過後再提升 catalog",
        "en": "Run the local discovery audit before promoting the source into the catalog.",
    },
}


class SourcePatternDraftError(ValueError):
    """Source draft is intentionally blocked before writing local config."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        source_url: str,
        detection: SourcePatternDetection | None = None,
        minimum_confidence: float = DEFAULT_PATTERN_MINIMUM_CONFIDENCE,
        detected_source_type: str = "",
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.source_url = source_url
        self.detection = detection
        self.minimum_confidence = minimum_confidence
        self.detected_source_type = detected_source_type

    def to_dict(self) -> dict[str, object]:
        # 這份 payload 是給 CLI/Tk/Web/agent 的 review handoff；被擋下的 URL 不應只剩 traceback。
        detection_payload = self.detection.to_dict() if self.detection is not None else {}
        skipped_item = {
            "source_url": self.source_url,
            "reason_code": self.reason_code,
            "message": str(self),
            "source_pattern_detection": detection_payload,
        }
        if self.detected_source_type:
            skipped_item["detected_source_type"] = self.detected_source_type
        action_labels = source_pattern_draft_next_action_labels(SOURCE_PATTERN_DRAFT_REVIEW_NEXT_ACTION)
        return {
            "schema_version": 1,
            "role": "source pattern draft blocked for review; no local source was written",
            "source_url": self.source_url,
            "source_draft_count": 0,
            "skipped_count": 1,
            "review_reason": self.reason_code,
            "review_message": str(self),
            "minimum_confidence": self.minimum_confidence,
            "next_action": SOURCE_PATTERN_DRAFT_REVIEW_NEXT_ACTION,
            "next_action_label": action_labels["zh_TW"],
            "next_action_label_zh_TW": action_labels["zh_TW"],
            "next_action_label_en": action_labels["en"],
            "source_pattern_detection": detection_payload,
            "sources": [],
            "skipped": [skipped_item],
        }


def source_pattern_draft_next_action_labels(action: str) -> dict[str, str]:
    """Return UI text for source-draft next-action codes.

    The machine-readable ``next_action`` remains stable for agents and JSON
    handoff.  Human surfaces should prefer these labels so they do not expose
    review codes such as ``review_source_profile_or_add_detector``.
    """

    action_id = str(action or "").strip()
    labels = SOURCE_PATTERN_DRAFT_NEXT_ACTION_LABELS.get(action_id)
    if labels is None:
        return {"zh_TW": action_id, "en": action_id}
    return labels


def dataset_source_from_detected_url(
    url: str,
    *,
    provider_id: str = "",
    name: str = "",
    source_id: str = "",
    categories: tuple[str, ...] = (),
    geographic_scope: str = "global",
    max_results: int = 10,
    min_expected_candidates: int = 1,
    timeout: float = 8.0,
    minimum_confidence: float = DEFAULT_PATTERN_MINIMUM_CONFIDENCE,
    fetcher: PatternFetcher | None = None,
    detector: SourcePatternDraftDetector | None = None,
) -> tuple[DatasetDiscoverySource, SourcePatternDetection]:
    # 這裡只產生 local draft，不直接提升到 catalog；detector 的信心分數仍要交給 crawler audit 驗證。
    normalized_url = url.strip()
    if not normalized_url:
        raise ValueError("source URL is required")
    validate_source_url(normalized_url)

    detection = detect_url_pattern(
        normalized_url,
        timeout=timeout,
        minimum_confidence=minimum_confidence,
        fetcher=fetcher,
        detector=detector,
    )
    if detection.pattern_id == UNKNOWN_PATTERN_ID:
        raise SourcePatternDraftError(
            "source_pattern_unknown",
            "source pattern detector returned unknown; keep this URL in review",
            source_url=normalized_url,
            detection=detection,
            minimum_confidence=minimum_confidence,
        )
    if detection.confidence < minimum_confidence:
        raise SourcePatternDraftError(
            "source_pattern_below_minimum_confidence",
            "source pattern detector confidence is below minimum; keep this URL in review",
            source_url=normalized_url,
            detection=detection,
            minimum_confidence=minimum_confidence,
        )
    source_type = detection.source_type_hint.strip()
    if not source_type:
        raise SourcePatternDraftError(
            "source_pattern_missing_source_type",
            "source pattern detector returned no supported source type; keep this URL in review",
            source_url=normalized_url,
            detection=detection,
            minimum_confidence=minimum_confidence,
        )
    if source_type not in SUPPORTED_DATASET_SOURCE_TYPES:
        raise SourcePatternDraftError(
            "source_pattern_unsupported_source_type",
            f"detected source type is not supported by a dataset crawler: {source_type}",
            source_url=normalized_url,
            detection=detection,
            minimum_confidence=minimum_confidence,
            detected_source_type=source_type,
        )

    parsed = urllib.parse.urlparse(normalized_url)
    provider = safe_identifier(provider_id) or provider_id_from_url(parsed)
    display_name = name.strip() or default_name_from_url(parsed, detection)
    source = DatasetDiscoverySource(
        source_id=safe_identifier(source_id) or default_source_id(provider, parsed, source_type),
        provider_id=provider,
        name=display_name,
        source_type=source_type,
        endpoint_url=normalize_endpoint_for_source_type(source_type, normalized_url),
        search_terms=tuple(part for part in categories if part.strip()),
        categories=tuple(part for part in categories if part.strip()) or ("detected_source", detection.pattern_id),
        geographic_scope=geographic_scope.strip() or "global",
        max_results=max(int(max_results or 10), 1),
        file_url_regex=DEFAULT_HTML_FILE_INDEX_REGEX if source_type_is_file_index(source_type) else "",
        min_expected_candidates=max(int(min_expected_candidates or 1), 1),
        notes=detection_notes(detection),
    )
    return source, detection


def write_source_draft_from_url(
    url: str,
    output_path: str | Path,
    *,
    provider_id: str = "",
    name: str = "",
    source_id: str = "",
    categories: tuple[str, ...] = (),
    geographic_scope: str = "global",
    max_results: int = 10,
    min_expected_candidates: int = 1,
    timeout: float = 8.0,
    minimum_confidence: float = DEFAULT_PATTERN_MINIMUM_CONFIDENCE,
    fetcher: PatternFetcher | None = None,
    detector: SourcePatternDraftDetector | None = None,
) -> dict[str, object]:
    source, detection = dataset_source_from_detected_url(
        url,
        provider_id=provider_id,
        name=name,
        source_id=source_id,
        categories=categories,
        geographic_scope=geographic_scope,
        max_results=max_results,
        min_expected_candidates=min_expected_candidates,
        timeout=timeout,
        minimum_confidence=minimum_confidence,
        fetcher=fetcher,
        detector=detector,
    )
    output = Path(output_path)
    append_dataset_discovery_source(output, source)
    source_payload = source_to_dict(source)
    source_payload["source_pattern_detection"] = detection.to_dict()
    action_labels = source_pattern_draft_next_action_labels(LOCAL_DISCOVERY_AUDIT_NEXT_ACTION)
    return {
        "schema_version": 1,
        "role": "local dataset discovery source draft from source pattern detector; ignored local config only",
        "source_url": url,
        "dataset_source_path": str(output),
        "source_draft_count": 1,
        "skipped_count": 0,
        "next_action": LOCAL_DISCOVERY_AUDIT_NEXT_ACTION,
        "next_action_label": action_labels["zh_TW"],
        "next_action_label_zh_TW": action_labels["zh_TW"],
        "next_action_label_en": action_labels["en"],
        "audit_command": LOCAL_DISCOVERY_AUDIT_COMMAND,
        "audit_source_ids": [source.source_id],
        "source_pattern_detection": detection.to_dict(),
        "sources": [source_payload],
        "skipped": [],
    }


def detect_url_pattern(
    url: str,
    *,
    timeout: float,
    minimum_confidence: float,
    fetcher: PatternFetcher | None,
    detector: SourcePatternDraftDetector | None,
) -> SourcePatternDetection:
    if detector is not None:
        return detector(url)
    if fetcher is not None:
        return detect_source_interface_pattern(
            url,
            fetcher=fetcher,
            timeout=timeout,
            minimum_confidence=minimum_confidence,
        )
    return detect_source_interface_pattern(url, timeout=timeout, minimum_confidence=minimum_confidence)


def validate_source_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("source URL must not embed credentials")


def provider_id_from_url(parsed: urllib.parse.ParseResult) -> str:
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    host = re.sub(r"^www\.", "", host)
    return safe_identifier(host.replace(".", "_")) or "detected_source"


def default_name_from_url(parsed: urllib.parse.ParseResult, detection: SourcePatternDetection) -> str:
    host = parsed.netloc.split("@")[-1].split(":")[0] or "detected source"
    return f"{host} {detection.pattern_id.upper()} source"


def default_source_id(provider_id: str, parsed: urllib.parse.ParseResult, source_type: str) -> str:
    path_slug = safe_identifier(parsed.path.strip("/").replace("/", "_"))[:48]
    parts = [provider_id, path_slug, source_type]
    return safe_identifier("_".join(part for part in parts if part)) or f"{provider_id}_{source_type}"


def safe_identifier(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized


def detection_notes(detection: SourcePatternDetection) -> str:
    evidence = "; ".join(detection.evidence[:8]) or "no evidence recorded"
    return (
        "Drafted from source pattern detector. "
        f"pattern={detection.pattern_id}; confidence={detection.confidence:.2f}; evidence={evidence}. "
        "This local source must pass crawler audit before catalog promotion."
    )
