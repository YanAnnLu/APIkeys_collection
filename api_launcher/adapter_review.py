from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api_launcher.downloads.plan_runner import plan_entries


REVIEW_IMPORT_STATUSES = {
    "adapter_review_required",
    "requires_unpack_or_adapter",
    "manual_review_required",
}


@dataclass(frozen=True)
class AdapterReviewItem:
    plan_index: int
    provider_id: str
    dataset_uid: str
    dataset_id: str
    dataset_title: str
    version: str
    adapter_id: str
    status: str
    source_url: str
    landing_url: str
    source_kind: str
    required_action: str
    expected_output: str
    reason: str
    download_status: str
    import_status: str
    plan_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_index": self.plan_index,
            "provider_id": self.provider_id,
            "dataset_uid": self.dataset_uid,
            "dataset_id": self.dataset_id,
            "dataset_title": self.dataset_title,
            "version": self.version,
            "adapter_id": self.adapter_id,
            "status": self.status,
            "source_url": self.source_url,
            "landing_url": self.landing_url,
            "source_kind": self.source_kind,
            "required_action": self.required_action,
            "expected_output": self.expected_output,
            "reason": self.reason,
            "download_status": self.download_status,
            "import_status": self.import_status,
            "plan_status": self.plan_status,
        }


def adapter_review_items(plan_payload: dict[str, Any]) -> list[AdapterReviewItem]:
    items: list[AdapterReviewItem] = []
    for index, entry in enumerate(plan_entries(plan_payload), start=1):
        item = adapter_review_item_from_entry(index, entry)
        if item is not None:
            items.append(item)
    return items


def adapter_review_item_from_entry(index: int, entry: dict[str, object]) -> AdapterReviewItem | None:
    eligibility = entry.get("download_eligibility") if isinstance(entry.get("download_eligibility"), dict) else {}
    import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
    review = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
    download_status = str(eligibility.get("status") or "")
    import_status = str(import_plan.get("status") or "")
    needs_review = bool(review) or download_status == "adapter_required" or import_status in REVIEW_IMPORT_STATUSES
    if not needs_review:
        return None

    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    provider_id = str(entry.get("provider_id") or "")
    dataset_id = str(entry.get("dataset_id") or version_meta.get("dataset_id") or "")
    adapter_id = str(review.get("adapter_id") or "").strip() or f"{provider_id}_adapter"
    source_url = first_text(
        review.get("source_url"),
        entry.get("adapter_review_url"),
        entry.get("download_url"),
        version_meta.get("download_url"),
        entry.get("api_base_url"),
        entry.get("docs_url"),
    )
    landing_url = first_text(review.get("landing_url"), entry.get("landing_url"), version_meta.get("landing_url"), entry.get("docs_url"))
    required_action = first_text(review.get("required_action")) or infer_required_action(download_status, import_status)
    source_kind = first_text(review.get("source_kind")) or ("direct_file_needs_transform" if download_status == "direct_download" else "api_landing_or_selector")
    reason = first_text(review.get("reason"), import_plan.get("reason"), eligibility.get("reason"))
    return AdapterReviewItem(
        plan_index=index,
        provider_id=provider_id,
        dataset_uid=str(entry.get("dataset_uid") or version_meta.get("dataset_uid") or ""),
        dataset_id=dataset_id,
        dataset_title=str(entry.get("dataset_title") or entry.get("name") or dataset_id),
        version=str(version_meta.get("version") or entry.get("version") or ""),
        adapter_id=adapter_id,
        status=first_text(review.get("status")) or "needs_adapter_review",
        source_url=source_url,
        landing_url=landing_url,
        source_kind=source_kind,
        required_action=required_action,
        expected_output=first_text(review.get("expected_output")) or "direct_download_plan_entries_with_manifests_and_import_plan",
        reason=reason,
        download_status=download_status,
        import_status=import_status,
        plan_status=str(entry.get("plan_status") or ""),
    )


def infer_required_action(download_status: str, import_status: str) -> str:
    if download_status == "direct_download" and import_status in {"requires_unpack_or_adapter", "manual_review_required"}:
        return "unpack_or_transform_downloaded_payload"
    return "resolve_source_to_direct_download_entries"


def first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def adapter_review_agent_payload(plan_payload: dict[str, Any]) -> dict[str, object]:
    items = adapter_review_items(plan_payload)
    by_adapter: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for item in items:
        by_adapter[item.adapter_id] = by_adapter.get(item.adapter_id, 0) + 1
        by_action[item.required_action] = by_action.get(item.required_action, 0) + 1
    return {
        "summary": {
            "item_count": len(items),
            "adapter_count": len(by_adapter),
            "by_adapter": by_adapter,
            "by_action": by_action,
        },
        "items": [item.to_dict() for item in items],
    }
