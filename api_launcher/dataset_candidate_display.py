"""Display helpers for dataset candidate review state.

Dataset candidate status is a registry/review contract.  UI surfaces should
render the labels here and pass raw status ids only at repository boundaries.
"""

from __future__ import annotations


DATASET_CANDIDATE_STATUS_DISPLAY: dict[str, dict[str, str]] = {
    "needs_review": {"zh_TW": "待審核", "en": "Needs review", "tone": "review"},
    "approved": {"zh_TW": "可用", "en": "Approved", "tone": "success"},
    "planned": {"zh_TW": "已排入", "en": "Planned", "tone": "info"},
    "rejected": {"zh_TW": "已拒絕", "en": "Rejected", "tone": "danger"},
    "all": {"zh_TW": "全部", "en": "All", "tone": "neutral"},
}


def dataset_candidate_status_label(status: str, *, locale: str = "zh_TW") -> str:
    normalized = str(status or "").strip().lower()
    profile = DATASET_CANDIDATE_STATUS_DISPLAY.get(normalized)
    if not profile:
        return "已發現" if locale == "zh_TW" else "Discovered"
    return profile.get(locale) or profile["zh_TW"]


def dataset_candidate_status_value(label_or_status: str) -> str:
    value = str(label_or_status or "").strip()
    normalized = value.lower()
    if normalized in DATASET_CANDIDATE_STATUS_DISPLAY:
        return normalized
    for status, profile in DATASET_CANDIDATE_STATUS_DISPLAY.items():
        if value in {profile.get("zh_TW", ""), profile.get("en", "")}:
            return status
    return normalized


def dataset_candidate_status_labels(*, include_all: bool = True, locale: str = "zh_TW") -> tuple[str, ...]:
    statuses = ("needs_review", "approved", "planned", "rejected")
    if include_all:
        statuses = (*statuses, "all")
    return tuple(dataset_candidate_status_label(status, locale=locale) for status in statuses)


__all__ = [
    "DATASET_CANDIDATE_STATUS_DISPLAY",
    "dataset_candidate_status_label",
    "dataset_candidate_status_labels",
    "dataset_candidate_status_value",
]
