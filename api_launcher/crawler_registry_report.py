from __future__ import annotations

from collections import Counter
from typing import Any

from api_launcher.crawlers import dataset_sources


def crawler_registry_report() -> dict[str, object]:
    """Return the full crawler registry report for developer diagnostics.

    This is a UI-neutral view of the declarative crawler table.  It is not a
    smoke test and it does not call live sources; it only reports the registry
    that dispatch already uses.
    """

    specs = dataset_sources.list_registered_crawlers()
    matrix = dataset_sources.CRAWLER_SPEC_MATRIX
    capability_index = dataset_sources.CRAWLER_CAPABILITY_INDEX
    return {
        "schema_version": 1,
        "role": "crawler_registry_declarative_matrix_report",
        "source_type_count": len(specs),
        "supported_source_types": [spec.source_type for spec in specs],
        "dimensions": _dimension_summary(specs),
        "matrix_cell_count": len(matrix),
        "matrix": [
            {
                "source_family": key[0],
                "transport": key[1],
                "auth_profile": key[2],
                "result_shape": key[3],
                "source_types": list(source_types),
                "source_type_count": len(source_types),
            }
            for key, source_types in sorted(matrix.items())
        ],
        "capability_groups": [
            {
                "capability_bits": bits,
                "capability_binary": format(bits, "04b"),
                "source_types": list(source_types),
                "source_type_count": len(source_types),
            }
            for bits, source_types in sorted(capability_index.items())
        ],
        "specs": [spec.to_dict() for spec in specs],
        "next_action": "use_registry_report_for_filters_before_adding_source_type_branches",
    }


def crawler_registry_summary() -> dict[str, object]:
    """Return a compact registry summary for handoff and diagnostics payloads."""

    report = crawler_registry_report()
    dimensions = report.get("dimensions") if isinstance(report.get("dimensions"), dict) else {}
    return {
        "source_type_count": int(report.get("source_type_count") or 0),
        "matrix_cell_count": int(report.get("matrix_cell_count") or 0),
        "source_families": _dimension_values(dimensions, "source_family"),
        "transports": _dimension_values(dimensions, "transport"),
        "auth_profiles": _dimension_values(dimensions, "auth_profile"),
        "result_shapes": _dimension_values(dimensions, "result_shape"),
        "seed_scopes": _dimension_values(dimensions, "seed_scope"),
        "capability_group_count": len(report.get("capability_groups") or []),
        "next_action": str(report.get("next_action") or ""),
    }


def _dimension_summary(specs: tuple[dataset_sources.CrawlerSpec, ...]) -> dict[str, dict[str, int]]:
    counters: dict[str, Counter[str]] = {
        "source_family": Counter(spec.source_family for spec in specs),
        "transport": Counter(spec.transport for spec in specs),
        "auth_profile": Counter(spec.auth_profile for spec in specs),
        "result_shape": Counter(spec.result_shape for spec in specs),
        "seed_scope": Counter(spec.seed_scope for spec in specs),
    }
    return {
        dimension: dict(sorted(counter.items()))
        for dimension, counter in counters.items()
    }


def _dimension_values(dimensions: dict[str, Any], key: str) -> list[str]:
    values = dimensions.get(key)
    if not isinstance(values, dict):
        return []
    return sorted(str(value) for value in values)


__all__ = [
    "crawler_registry_report",
    "crawler_registry_summary",
]
