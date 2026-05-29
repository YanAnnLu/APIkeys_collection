"""Display helpers for crawler seed enumeration status.

The crawler service decides the enumeration status.  This module owns the
UI-neutral label/tone/help table so Tk, Web, and future Qt skins do not each
rebuild the same status branching.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedEnumerationDisplayProfile:
    """Shared UI text contract for crawler seed enumeration outcomes."""

    status: str
    display_tone: str
    label_template: str
    help: str
    default_next_action: str
    limited_by_max_results: bool
    completion_confidence: str

    def payload(
        self,
        *,
        candidate_count: int,
        max_results: int,
        remote_pagination: dict[str, object],
        warning_count: int = 0,
        next_action: str = "",
        completion_confidence: str = "",
    ) -> dict[str, object]:
        label = self.label_template.format(
            candidate_count=candidate_count,
            max_results=max_results,
            warning_count=warning_count,
        )
        return {
            "status": self.status,
            "display_tone": self.display_tone,
            "label": label,
            "help": self.help,
            "next_action": next_action or self.default_next_action,
            "limited_by_max_results": self.limited_by_max_results,
            "candidate_count": candidate_count,
            "max_results": max_results,
            "remote_pagination": remote_pagination,
            "completion_confidence": completion_confidence or self.completion_confidence,
        }


SEED_ENUMERATION_DISPLAY_PROFILES = {
    "blocked": SeedEnumerationDisplayProfile(
        status="blocked",
        display_tone="warning",
        label_template="需要登入或啟用後才能枚舉 seed",
        help="完成登入設定、解除封存或啟用入口後再重新枚舉。",
        default_next_action="",
        limited_by_max_results=False,
        completion_confidence="blocked",
    ),
    "error": SeedEnumerationDisplayProfile(
        status="error",
        display_tone="danger",
        label_template="seed 枚舉發生錯誤",
        help="請查看 crawler audit 或事件紀錄中的錯誤來源。",
        default_next_action="inspect_crawler_error",
        limited_by_max_results=False,
        completion_confidence="error",
    ),
    "empty": SeedEnumerationDisplayProfile(
        status="empty",
        display_tone="warning",
        label_template="尚未找到 seed",
        help="可調整界域、檢查入口 URL、登入狀態或 crawler parser。",
        default_next_action="adjust_bounds_or_refresh_source_listing",
        limited_by_max_results=False,
        completion_confidence="zero_candidates",
    ),
    "local_limit_reached": SeedEnumerationDisplayProfile(
        status="local_limit_reached",
        display_tone="warning",
        label_template="已枚舉前 {candidate_count} 筆 seed",
        help="結果已達本機安全上限，遠端可能還有更多 seed；可縮小界域或提高枚舉上限。",
        default_next_action="narrow_bounds_or_raise_seed_limit",
        limited_by_max_results=True,
        completion_confidence="local_limit_only",
    ),
    "warning": SeedEnumerationDisplayProfile(
        status="warning",
        display_tone="warning",
        label_template="已枚舉 {candidate_count} 筆 seed，但有 {warning_count} 個警告",
        help="候選已寫入本機 catalog；建議先查看 crawler audit，再建立下載計畫。",
        default_next_action="inspect_source_audit_results_before_upsert_or_promotion",
        limited_by_max_results=False,
        completion_confidence="warning_with_unknown_remote_completion",
    ),
    "within_current_limits": SeedEnumerationDisplayProfile(
        status="within_current_limits",
        display_tone="success",
        label_template="已枚舉 {candidate_count} 筆 seed",
        help="結果低於本機枚舉上限；若來源支援遠端分頁，完整性仍以 crawler audit 為準。",
        default_next_action="review_seed_list_or_build_download_plan",
        limited_by_max_results=False,
        completion_confidence="within_current_local_limits",
    ),
    "bounded_sample": SeedEnumerationDisplayProfile(
        status="bounded_sample",
        display_tone="info",
        label_template="已取得 {candidate_count} 筆 seed 樣本",
        help="這是 bounded/sample 模式；若要完整列入口 seed，請重新枚舉 seed。",
        default_next_action="rerun_complete_seed_enumeration",
        limited_by_max_results=False,
        completion_confidence="bounded_sample",
    ),
}


def seed_enumeration_display_payload(
    status: str,
    *,
    candidate_count: int,
    max_results: int,
    remote_pagination: dict[str, object],
    warning_count: int = 0,
    next_action: str = "",
    completion_confidence: str = "",
) -> dict[str, object]:
    profile = SEED_ENUMERATION_DISPLAY_PROFILES[status]
    return profile.payload(
        candidate_count=candidate_count,
        max_results=max_results,
        remote_pagination=remote_pagination,
        warning_count=warning_count,
        next_action=next_action,
        completion_confidence=completion_confidence,
    )


__all__ = [
    "SEED_ENUMERATION_DISPLAY_PROFILES",
    "SeedEnumerationDisplayProfile",
    "seed_enumeration_display_payload",
]
