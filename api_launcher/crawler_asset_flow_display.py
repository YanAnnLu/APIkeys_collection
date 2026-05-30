"""Display helpers for crawler asset cards and flow steps.

This module owns the small read-model used by Tk/Web/Qt skins to show what an
asset can do and where it sits in the source -> bounds -> download-plan flow.
It deliberately does not build plans, run crawlers, or decide download policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from api_launcher.crawler_asset_bound_display import capability_display_label
from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundFormSpec
from api_launcher.crawler_asset_capabilities import BUILD_DOWNLOAD_PLAN, CrawlerAssetCapability, status_label_or_fallback
from api_launcher.crawler_assets import CrawlerAsset
from api_launcher.crawler_next_action_display import next_action_display_label_or_fallback


@dataclass(frozen=True)
class CrawlerAssetFlowStep:
    step_id: str
    label: str
    status: str
    summary: str
    evidence: str = ""
    warning_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "label": self.label,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "warning_codes": list(self.warning_codes),
        }


def crawler_asset_card_capabilities(
    capabilities: Iterable[CrawlerAssetCapability],
) -> list[dict[str, object]]:
    """Return compact capability rows for asset cards and lists."""

    return [
        {
            "capability_id": capability.capability_id,
            "label": capability.label,
            "display_label": capability_display_label(capability),
            "status": capability.status,
            "status_label": status_label_or_fallback(capability.status),
            "next_action": capability.next_action,
            "next_action_label": next_action_display_label_or_fallback(
                capability.next_action,
                fallback="檢查能力設定",
            ),
        }
        for capability in capabilities
    ]


def crawler_asset_flow_steps(
    asset: CrawlerAsset,
    form_spec: CrawlerAssetBoundFormSpec,
) -> list[dict[str, object]]:
    """Return UI-neutral flow steps for one crawler asset.

    The flow is a display projection only: it describes current evidence from
    asset metadata, capability status, and form availability.  It must not run
    crawler probes or alter download/import policy.
    """

    plan_capability = next(
        (capability for capability in asset.capabilities if capability.capability_id == BUILD_DOWNLOAD_PLAN),
        None,
    )
    source_type_known = bool(asset.source_type and asset.source_type != "unknown")
    source_type_label = getattr(asset, "source_type_label", "") or "來源範式待確認"
    has_bounds_form = bool(form_spec.fields)
    plan_status = plan_capability.status if plan_capability is not None else "missing_handler"
    review_needed = asset.health.status_code not in {"healthy", "ready"} or "review" in plan_status
    steps = (
        CrawlerAssetFlowStep(
            step_id="seed",
            label="Seed 註冊",
            status="complete" if asset.seed_count else "warning",
            summary=asset.seed_summary or f"{asset.seed_count} seed",
            evidence=asset.endpoint_url,
        ),
        CrawlerAssetFlowStep(
            step_id="source_pattern",
            label="來源範式",
            status="complete" if source_type_known else "review",
            summary=source_type_label,
            evidence=asset.source_surface,
        ),
        CrawlerAssetFlowStep(
            step_id="bounds",
            label="界域表單",
            status="complete" if has_bounds_form else "neutral",
            summary=f"{len(form_spec.fields)} 個欄位" if has_bounds_form else "未提供界域表單",
            evidence=", ".join(form_spec.groups),
            warning_codes=tuple(form_spec.warning_codes),
        ),
        CrawlerAssetFlowStep(
            step_id="download_plan",
            label="下載計畫",
            status="complete" if plan_status in {"selectable", "ready", "bounded"} else "review",
            summary=plan_status,
            evidence=plan_capability.next_action if plan_capability is not None else "implement_source_handler",
        ),
        CrawlerAssetFlowStep(
            step_id="review_gate",
            label="審核閘門",
            status="review" if review_needed else "complete",
            summary=asset.health.status_code,
            evidence=asset.next_action,
        ),
    )
    return [step.to_dict() for step in steps]


__all__ = [
    "CrawlerAssetFlowStep",
    "crawler_asset_card_capabilities",
    "crawler_asset_flow_steps",
]
