from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api_launcher.downloads.plan_runner import plan_entries


REVIEW_IMPORT_STATUSES = {
    # 這些 import 狀態代表「不能直接下載後就當完成」，需要 adapter 或人工規則接手。
    "adapter_review_required",
    "requires_unpack_or_adapter",
    "manual_review_required",
}


@dataclass(frozen=True)
class AdapterReviewItem:
    # Adapter 待辦是給 UI/CLI/agent 共用的穩定摘要，不直接引用原始 plan entry。
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
    outcome_bucket: str
    download_status: str
    import_status: str
    plan_status: str

    def to_dict(self) -> dict[str, object]:
        # 輸出欄位維持扁平結構，讓 CLI JSON、Tk table 與 agent prompt 都容易消費。
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
            "outcome_bucket": self.outcome_bucket,
            "download_status": self.download_status,
            "import_status": self.import_status,
            "plan_status": self.plan_status,
        }


def adapter_review_items(plan_payload: dict[str, Any]) -> list[AdapterReviewItem]:
    # plan_entries() 是共用入口，避免這裡重新猜測 download plan 的 providers/items 形狀。
    items: list[AdapterReviewItem] = []
    for index, entry in enumerate(plan_entries(plan_payload), start=1):
        item = adapter_review_item_from_entry(index, entry)
        if item is not None:
            items.append(item)
    return items


def adapter_review_item_from_entry(index: int, entry: dict[str, object]) -> AdapterReviewItem | None:
    # 舊版 plan 可能沒有 adapter_review 區塊，所以也要從 download/import status 推導。
    eligibility = entry.get("download_eligibility") if isinstance(entry.get("download_eligibility"), dict) else {}
    import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
    review = entry.get("adapter_review") if isinstance(entry.get("adapter_review"), dict) else {}
    download_status = str(eligibility.get("status") or "")
    import_status = str(import_plan.get("status") or "")
    needs_review = bool(review) or download_status == "adapter_required" or import_status in REVIEW_IMPORT_STATUSES
    if not needs_review:
        # direct 且已支援匯入的項目不用進 Adapter 待辦，避免隊列被可執行項目污染。
        return None

    version_meta = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    provider_id = str(entry.get("provider_id") or "")
    dataset_id = str(entry.get("dataset_id") or version_meta.get("dataset_id") or "")
    adapter_id = str(review.get("adapter_id") or "").strip() or f"{provider_id}_adapter"
    # source_url 依序找最具體的 review URL，再退回 plan/download/docs URL，讓接手者有入口可查。
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
    # source_kind 用來區分「要找 direct files」與「已下載但需轉換」，兩者後續 adapter 工作不同。
    source_kind = first_text(review.get("source_kind")) or ("direct_file_needs_transform" if download_status == "direct_download" else "api_landing_or_selector")
    reason = first_text(review.get("reason"), import_plan.get("reason"), eligibility.get("reason"))
    outcome_bucket = infer_outcome_bucket(download_status, import_status, required_action)
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
        outcome_bucket=outcome_bucket,
        download_status=download_status,
        import_status=import_status,
        plan_status=str(entry.get("plan_status") or ""),
    )


def infer_required_action(download_status: str, import_status: str) -> str:
    # direct_download 仍可能需要解壓或格式轉換；不要把它誤派成 source resolver。
    if download_status == "direct_download" and import_status in {"requires_unpack_or_adapter", "manual_review_required"}:
        return "unpack_or_transform_downloaded_payload"
    return "resolve_source_to_direct_download_entries"


def infer_outcome_bucket(download_status: str, import_status: str, required_action: str) -> str:
    # outcome_bucket 是給 agent/UI 的粗分類；真正實作仍由 required_action 與 adapter_id 接手。
    if required_action == "unpack_or_transform_downloaded_payload":
        return "downloaded_payload_transform"
    if download_status == "adapter_required":
        return "source_resolution_required"
    if download_status == "direct_download" and import_status in REVIEW_IMPORT_STATUSES:
        return "import_transform_required"
    if import_status in REVIEW_IMPORT_STATUSES:
        return "import_adapter_required"
    return "adapter_review_required"


def first_text(*values: object) -> str:
    # Adapter 待辦只需要可讀文字；複雜物件應留在原始 plan metadata 裡。
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def adapter_review_agent_payload(plan_payload: dict[str, Any]) -> dict[str, object]:
    # by_adapter/by_action 讓 agent 可以先挑同類工作批次處理，而不是逐筆掃完整 items。
    items = adapter_review_items(plan_payload)
    by_adapter: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for item in items:
        # 同時統計 adapter 與 action，可以看出是同一來源缺 resolver，還是多種轉換工作混在一起。
        by_adapter[item.adapter_id] = by_adapter.get(item.adapter_id, 0) + 1
        by_action[item.required_action] = by_action.get(item.required_action, 0) + 1
        by_outcome[item.outcome_bucket] = by_outcome.get(item.outcome_bucket, 0) + 1
    return {
        "summary": {
            "item_count": len(items),
            "adapter_count": len(by_adapter),
            "by_adapter": by_adapter,
            "by_action": by_action,
            "by_outcome": by_outcome,
        },
        "items": [item.to_dict() for item in items],
    }
