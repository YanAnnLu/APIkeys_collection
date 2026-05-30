"""Display profiles for crawler asset plan outcome buckets.

Plan outcome buckets are backend contracts such as ``ready_to_download`` or
``review_required``.  This module owns the human label, tone, summary, and
short-label mapping so Tk, Web, CLI diagnostics, and future Qt skins do not
translate those buckets independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from api_launcher.crawler_next_action_display import next_action_display_label_or_fallback


# Outcome buckets are machine contracts.  This table is the UI-neutral display
# layer for those buckets.
PLAN_OUTCOME_DISPLAY = {
    "ready_to_download": {
        "display_label": "可開始下載",
        "display_tone": "success",
        "summary": "已建立可直接下載的計畫。",
    },
    "partial_review_required": {
        "display_label": "部分可下載",
        "display_tone": "warning",
        "summary": "部分項目已可下載，仍有項目需要 Adapter 審核。",
    },
    "review_required": {
        "display_label": "待 Adapter 審核",
        "display_tone": "review",
        "summary": "目前沒有可直接下載項目，需要先審核或調整界域。",
    },
    "zero_candidates": {
        "display_label": "零候選",
        "display_tone": "neutral",
        "summary": "本次界域沒有抓到候選資料。",
    },
    "empty_plan": {
        "display_label": "空計畫",
        "display_tone": "neutral",
        "summary": "後端沒有產生可執行的下載計畫。",
    },
    "blocked": {
        "display_label": "已阻擋",
        "display_tone": "danger",
        "summary": "此爬蟲資產目前被設定或狀態擋下。",
    },
}


@dataclass(frozen=True)
class DisplayProfile:
    """UI-neutral display contract for one backend status.

    Keep label/tone/next-action decisions in the backend so UI skins render
    the same state without reimplementing business branching.
    """

    profile_id: str
    display_label: str
    display_tone: str = "neutral"
    short_label: str = ""
    summary: str = ""
    next_action: str = ""
    next_action_label: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "profile_id": self.profile_id,
            "display_label": self.display_label,
            "display_tone": self.display_tone,
            "short_label": self.short_label,
            "summary": self.summary,
            "next_action": self.next_action,
            "next_action_label": self.next_action_label,
        }


def plan_outcome_display_label(bucket: str) -> str:
    return plan_outcome_display_profile(bucket).display_label


def plan_outcome_short_label(bucket: str, *, added_count: int = 0, review_count: int = 0) -> str:
    return plan_outcome_display_profile(bucket, review=review_count, added_count=added_count).short_label


def plan_outcome_display_profile(
    bucket: str,
    *,
    direct: int = 0,
    review: int = 0,
    added_count: int = 0,
    blocked_reason: str = "",
    next_action: str = "",
) -> DisplayProfile:
    display = PLAN_OUTCOME_DISPLAY.get(bucket, PLAN_OUTCOME_DISPLAY["empty_plan"])
    summary = _plan_outcome_summary(
        bucket,
        default_summary=str(display["summary"]),
        direct=direct,
        review=review,
        added_count=added_count,
        blocked_reason=blocked_reason,
    )
    return DisplayProfile(
        profile_id=bucket,
        display_label=str(display["display_label"]),
        display_tone=str(display["display_tone"]),
        short_label=_plan_outcome_short_label(
            bucket,
            direct=direct,
            review=review,
            added_count=added_count,
            blocked_reason=blocked_reason,
        ),
        summary=summary,
        next_action=next_action,
        next_action_label=next_action_display_label_or_fallback(next_action, fallback="檢查下載計畫結果"),
    )


def _plan_outcome_summary(
    bucket: str,
    *,
    default_summary: str,
    direct: int,
    review: int,
    added_count: int,
    blocked_reason: str,
) -> str:
    if bucket == "ready_to_download":
        return f"直接下載 {direct} 筆；已加入下載器 {added_count} 筆。"
    if bucket == "partial_review_required":
        return f"已加入下載器 {added_count} 筆；仍有 {review} 筆需要 Adapter 審核。"
    if bucket == "review_required":
        return f"{review} 筆需要 Adapter 審核；目前沒有可直接下載項目。"
    if bucket == "zero_candidates":
        return "本次界域沒有候選資料；請放寬時間、空間或查詢條件。"
    if bucket == "blocked" and blocked_reason:
        return f"被阻擋：{blocked_reason}。"
    return default_summary


def _plan_outcome_short_label(
    bucket: str,
    *,
    direct: int,
    review: int,
    added_count: int,
    blocked_reason: str,
) -> str:
    if bucket == "ready_to_download":
        return f"可下載 {added_count or direct}"
    if bucket == "partial_review_required":
        return f"可下載 {added_count} / 待辦 {review}"
    if bucket == "review_required":
        return f"待 Adapter {review}"
    if bucket == "zero_candidates":
        return "零候選"
    if bucket == "blocked":
        return f"已阻擋 {blocked_reason or 'blocked'}"
    return "需檢查"


__all__ = [
    "DisplayProfile",
    "PLAN_OUTCOME_DISPLAY",
    "plan_outcome_display_label",
    "plan_outcome_display_profile",
    "plan_outcome_short_label",
]
