from __future__ import annotations

from typing import Any

from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES
from api_launcher.crawlers.orchestrator import DatasetCrawlOptions, DatasetCrawlResult, crawl_dataset_sources
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.models import Dataset


def crawler_handler_smoke_sources() -> list[DatasetDiscoverySource]:
    """產生每個 crawler handler 的離線 contract source，不碰正式 catalog 或網路。"""

    return [
        DatasetDiscoverySource(
            source_id=f"smoke_{source_type}",
            provider_id="rrkal_smoke",
            name=f"Smoke {source_type}",
            source_type=source_type,
            endpoint_url=f"https://example.test/rrkal-smoke/{source_type}",
            search_terms=("smoke",),
            max_results=1,
            min_expected_candidates=1,
        )
        for source_type in SUPPORTED_DATASET_SOURCE_TYPES
    ]


def crawler_handler_audit_smoke_report() -> dict[str, object]:
    """回報所有 supported source_type 是否能走同一套 audit summary / next_action。

    這不是 live crawler 測試；它刻意用注入式 fake runner 驗證 audit 層契約：
    零候選要有 warning/next_action，正常候選要能 pass。真正遠端 payload parser
    仍由各 handler 的 fixture 測試負責。
    """

    sources = crawler_handler_smoke_sources()
    options = DatasetCrawlOptions(max_workers=1, min_candidates_per_source_override=1)
    empty_result = crawl_dataset_sources(sources, options, source_crawler=_empty_candidate_runner)
    candidate_result = crawl_dataset_sources(sources, options, source_crawler=_single_candidate_runner)
    return {
        "schema_version": 1,
        "role": "offline crawler handler audit contract smoke; no live network requests",
        "supported_source_type_count": len(SUPPORTED_DATASET_SOURCE_TYPES),
        "supported_source_types": list(SUPPORTED_DATASET_SOURCE_TYPES),
        "empty_case": _crawl_result_payload(empty_result),
        "candidate_case": _crawl_result_payload(candidate_result),
        "next_action": "repair_contract_if_any_supported_source_type_missing_audit_status",
    }


def crawler_handler_audit_smoke_summary() -> dict[str, object]:
    """Return the compact contract summary shared by handoff and diagnostics.

    這份摘要刻意不回傳 per-source `source_results`。完整 smoke report 仍留給 CLI
    與測試追查；handoff、heartbeat、Web developer diagnostics 只需要知道整體契約
    是否仍可重跑、零候選是否能導到修復 next_action、正常候選是否全部 pass。
    """

    report = crawler_handler_audit_smoke_report()
    empty_summary = _audit_summary(report.get("empty_case"))
    candidate_summary = _audit_summary(report.get("candidate_case"))
    return {
        "command": "python APIkeys_collection.py --dataset-discovery-handler-smoke-json",
        "supported_source_type_count": int(report.get("supported_source_type_count") or 0),
        "empty_case_status": str(empty_summary.get("status") or ""),
        "empty_case_zero_candidates": int(
            _dict_value(empty_summary.get("by_warning_code"), "zero_candidates")
        ),
        "empty_case_next_action_count": int(
            _dict_value(empty_summary.get("by_next_action"), "repair_crawler_query_or_parser")
        ),
        "candidate_case_status": str(candidate_summary.get("status") or ""),
        "candidate_case_pass_sources": int(_dict_value(candidate_summary.get("by_status"), "pass")),
        "next_action": str(report.get("next_action") or ""),
    }


def _empty_candidate_runner(_source: DatasetDiscoverySource, _options: DatasetCrawlOptions) -> list[DatasetCandidate]:
    return []


def _single_candidate_runner(source: DatasetDiscoverySource, _options: DatasetCrawlOptions) -> list[DatasetCandidate]:
    dataset_id = f"{source.source_type}_fixture"
    return [
        DatasetCandidate(
            dataset=Dataset(
                dataset_uid=f"{source.source_id}_{dataset_id}",
                provider_id=source.provider_id,
                dataset_id=dataset_id,
                title=f"{source.name} fixture",
                categories=("crawler_smoke",),
                metadata={"candidate_status": "needs_review", "source_type": source.source_type},
            ),
            source_id=source.source_id,
            source_type=source.source_type,
            source_url=source.endpoint_url,
            confidence=0.9,
            evidence=("offline crawler audit contract smoke",),
        )
    ]


def _crawl_result_payload(result: DatasetCrawlResult) -> dict[str, object]:
    return {
        "candidate_count": result.candidate_count,
        "duplicate_count": result.duplicate_count,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "next_action": result.next_action,
        "audit_summary": result.audit_summary,
        "source_results": [
            {
                "source_id": source.source_id,
                "source_type": source.source_type,
                "candidate_count": source.candidate_count,
                "audit_status": source.audit_status,
                "warning_codes": list(source.warning_codes),
                "next_action": source.next_action,
                "error": source.error,
            }
            for source in result.source_results
        ],
    }


def _audit_summary(case_payload: object) -> dict[str, Any]:
    if not isinstance(case_payload, dict):
        return {}
    audit_summary = case_payload.get("audit_summary")
    return audit_summary if isinstance(audit_summary, dict) else {}


def _dict_value(value: object, key: str) -> int:
    if not isinstance(value, dict):
        return 0
    try:
        return int(value.get(key) or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "crawler_handler_audit_smoke_report",
    "crawler_handler_audit_smoke_summary",
    "crawler_handler_smoke_sources",
]
