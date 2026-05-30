from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from api_launcher.crawler_next_action_display import next_action_display_label_or_fallback


class CrawlerAssetCapabilityLike(Protocol):
    capability_id: str
    status: str
    next_action: str


@dataclass(frozen=True)
class CrawlerAssetHealth:
    """爬蟲資產的 UI-neutral 健康狀態。

    Tk/Qt 只應消費這個狀態，不要各自重新推斷哪些爬蟲失效、待審或可用。
    """

    asset_id: str
    status_code: str
    status_gate: str
    status_emoji: str
    health_reason: str
    warning_codes: tuple[str, ...] = ()
    last_success_at: str = ""
    last_failure_at: str = ""
    next_action: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "status_code": self.status_code,
            "status_label": health_status_label_or_fallback(self.status_code),
            "status_tone": health_status_tone(self.status_code),
            "status_gate": self.status_gate,
            "status_emoji": self.status_emoji,
            "health_reason": self.health_reason,
            "warning_codes": list(self.warning_codes),
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
            "next_action": self.next_action,
            "next_action_label": next_action_display_label_or_fallback(
                self.next_action,
                fallback="檢查爬蟲資產狀態",
            ),
        }


def evaluate_crawler_asset_health(
    *,
    asset_id: str,
    enabled: bool,
    archived: bool,
    risk_tier: str,
    maturity: str,
    capabilities: Iterable[CrawlerAssetCapabilityLike],
    next_action: str,
    warning_codes: Iterable[str] = (),
    last_success_at: str = "",
    last_failure_at: str = "",
) -> CrawlerAssetHealth:
    """把 profile、能力契約與稽核結果收斂成卡片可直接顯示的狀態。"""

    warnings = tuple(str(code).strip() for code in warning_codes if str(code).strip())
    if archived:
        return _health(asset_id, "archived", "restricted", "🗄", "crawler asset is archived", ("archived",), "unarchive_before_crawl")
    if not enabled:
        return _health(asset_id, "disabled", "staged", "⏸", "crawler asset is disabled", ("disabled",), "enable_before_crawl")
    if risk_tier == "needs_handler":
        return _health(
            asset_id,
            "missing_handler",
            "adapter_review",
            "🧩",
            "source type has no crawler handler yet",
            warnings or ("needs_handler",),
            "implement_source_handler",
        )
    if any(item.status == "needs_bounds_or_adapter" for item in capabilities):
        return _health(
            asset_id,
            "needs_bounds",
            "review",
            "🧭",
            "schema probe or adapter mapping is required before download",
            warnings or ("needs_bounds_or_adapter",),
            "probe_schema_then_define_bounds",
        )
    if risk_tier == "needs_review":
        return _health(
            asset_id,
            "review_needed",
            "review",
            "⚠",
            "crawler output or seed coverage needs review",
            warnings or ("needs_review",),
            next_action or "review_candidates",
        )
    if maturity in {"ready", "bounded", "assembled"}:
        return _health(
            asset_id,
            "healthy",
            "completed",
            "✅",
            "crawler asset is available for the current workflow",
            warnings,
            next_action or "list_datasets",
            last_success_at=last_success_at,
            last_failure_at=last_failure_at,
        )
    return _health(
        asset_id,
        "unknown",
        "staged",
        "？",
        "crawler asset state is not classified yet",
        warnings or ("unknown_state",),
        next_action or "review_crawler_asset",
        last_success_at=last_success_at,
        last_failure_at=last_failure_at,
    )


def _health(
    asset_id: str,
    status_code: str,
    status_gate: str,
    status_emoji: str,
    health_reason: str,
    warning_codes: tuple[str, ...],
    next_action: str,
    *,
    last_success_at: str = "",
    last_failure_at: str = "",
) -> CrawlerAssetHealth:
    return CrawlerAssetHealth(
        asset_id=asset_id,
        status_code=status_code,
        status_gate=status_gate,
        status_emoji=status_emoji,
        health_reason=health_reason,
        warning_codes=warning_codes,
        last_success_at=last_success_at,
        last_failure_at=last_failure_at,
        next_action=next_action,
    )


def health_status_label(status_code: str) -> str:
    labels = {
        "healthy": "可用",
        "needs_bounds": "需界域",
        "blocked": "阻擋",
        "missing_handler": "缺 handler",
        "review_needed": "待審核",
        "disabled": "停用",
        "archived": "封存",
        "failed": "失敗",
        "unknown": "未知",
    }
    return labels.get(status_code, status_code)


def health_status_label_or_fallback(status_code: str, *, fallback: str = "未知") -> str:
    label = health_status_label(status_code)
    return label if label != status_code else fallback


def health_status_tone(status_code: str) -> str:
    if status_code in {"healthy", "ready", "bounded"}:
        return "success"
    if status_code in {"needs_bounds", "review_needed", "disabled", "archived"}:
        return "warning"
    if status_code in {"missing_handler", "blocked", "failed"}:
        return "danger"
    return "neutral"


__all__ = [
    "CrawlerAssetHealth",
    "evaluate_crawler_asset_health",
    "health_status_label",
    "health_status_label_or_fallback",
    "health_status_tone",
]
