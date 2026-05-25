from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Mapping

from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundFormSpec,
    CrawlerAssetBoundPayload,
    build_crawler_asset_bound_form_spec,
    crawler_asset_bound_payload_from_form_values,
)
from api_launcher.crawler_asset_service import build_crawler_asset_download_plan
from api_launcher.crawler_assets import BUILD_DOWNLOAD_PLAN, CrawlerAsset, load_crawler_assets
from api_launcher.db import connect_db
from api_launcher.paths import default_local_downloads_root, state_file
from api_launcher.repository import ApiCatalogRepository


WEB_PREVIEW_DB_NAME = "web_preview.sqlite"


def web_preview_status() -> dict[str, object]:
    """Return a small machine-readable status for browser smoke checks."""

    return {
        "product": "RuRuKa Asset Launcher",
        "surface": "web_preview",
        "purpose": "uiux_review",
        "business_logic_owner": "api_launcher",
    }


def crawler_asset_cards(
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Return cards for the Web Preview asset rail.

    The payload is deliberately smaller than CrawlerAsset.to_dict() so the web
    layer can render a stable UX contract without depending on every internal
    field.  The detail endpoint can still expose the full asset when needed.
    """

    assets = load_crawler_assets(primary_path, local_path, profile_path)
    return {
        "count": len(assets),
        "assets": [crawler_asset_card(asset) for asset in assets],
    }


def crawler_asset_card(asset: CrawlerAsset) -> dict[str, object]:
    return {
        "asset_id": asset.asset_id,
        "display_name": asset.display_name,
        "provider_id": asset.provider_id,
        "source_type": asset.source_type,
        "source_surface": asset.source_surface,
        "endpoint_url": asset.endpoint_url,
        "docs_url": asset.docs_url,
        "categories": list(asset.categories),
        "geographic_scope": asset.geographic_scope,
        "maturity": asset.maturity,
        "risk_tier": asset.risk_tier,
        "trust_score": asset.trust_score,
        "seed_summary": asset.seed_summary,
        "current_seed_scope": asset.current_seed_scope,
        "enabled": asset.enabled,
        "archived": asset.archived,
        "health": asset.health.to_dict(),
        "capabilities": [
            {
                "capability_id": capability.capability_id,
                "label": capability.label,
                "status": capability.status,
                "next_action": capability.next_action,
            }
            for capability in asset.capabilities
        ],
        "next_action": asset.next_action,
    }


def crawler_asset_detail(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    form_spec = crawler_asset_bound_form(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    return {
        "asset": asset.to_dict(),
        "card": crawler_asset_card(asset),
        "bound_form": form_spec.to_dict(),
        "flow_steps": crawler_asset_flow_steps(asset, form_spec),
    }


def crawler_asset_flow_steps(
    asset: CrawlerAsset,
    form_spec: CrawlerAssetBoundFormSpec,
) -> list[dict[str, object]]:
    """Build a backend-owned visual flow for Web/Tk/Qt surfaces.

    The web preview should not infer crawler readiness from ad hoc UI strings.
    This compact flow keeps the UI visual while still grounding every step in
    crawler asset metadata, capabilities, and the dynamic bounds form contract.
    """

    plan_capability = next(
        (capability for capability in asset.capabilities if capability.capability_id == BUILD_DOWNLOAD_PLAN),
        None,
    )
    source_type_known = bool(asset.source_type and asset.source_type != "unknown")
    has_bounds_form = bool(form_spec.fields)
    plan_status = plan_capability.status if plan_capability is not None else "missing_handler"
    review_needed = asset.health.status_code not in {"healthy", "ready"} or "review" in plan_status
    return [
        {
            "step_id": "seed",
            "label": "Seed 註冊",
            "status": "complete" if asset.seed_count else "warning",
            "summary": asset.seed_summary or f"{asset.seed_count} seed",
            "evidence": asset.endpoint_url,
        },
        {
            "step_id": "source_pattern",
            "label": "來源範式",
            "status": "complete" if source_type_known else "review",
            "summary": asset.source_type or "unknown",
            "evidence": asset.source_surface,
        },
        {
            "step_id": "bounds",
            "label": "界域表單",
            "status": "complete" if has_bounds_form else "neutral",
            "summary": f"{len(form_spec.fields)} 個欄位" if has_bounds_form else "不需或尚未定義界域",
            "evidence": ", ".join(form_spec.groups),
            "warning_codes": list(form_spec.warning_codes),
        },
        {
            "step_id": "download_plan",
            "label": "下載計畫",
            "status": "complete" if plan_status in {"selectable", "ready", "bounded"} else "review",
            "summary": plan_status,
            "evidence": plan_capability.next_action if plan_capability is not None else "implement_source_handler",
        },
        {
            "step_id": "review_gate",
            "label": "審核門檻",
            "status": "review" if review_needed else "complete",
            "summary": asset.health.status_code,
            "evidence": asset.next_action,
        },
    ]


def crawler_asset_bound_form(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAssetBoundFormSpec:
    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    plan_capability = next(
        (capability for capability in asset.capabilities if capability.capability_id == BUILD_DOWNLOAD_PLAN),
        None,
    )
    bounds_schema = plan_capability.bounds_schema if plan_capability is not None else ()
    return build_crawler_asset_bound_form_spec(asset.asset_id, bounds_schema)


def crawler_asset_payload_from_web_values(
    asset_id: str,
    values: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAssetBoundPayload:
    form_spec = crawler_asset_bound_form(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    return crawler_asset_bound_payload_from_form_values(form_spec, values)


def crawler_asset_plan_preview(
    asset_id: str,
    values: Mapping[str, object],
    *,
    execute: bool = False,
    db_path: str | Path | None = None,
    downloads_root: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Preview or execute the crawler-asset plan build.

    ``execute=False`` is the default for UIUX work: it proves the dynamic form
    can produce the same backend payload without making a live crawl.  When the
    user explicitly clicks the build-plan button, ``execute=True`` calls the
    existing crawler asset service and keeps unresolved work in adapter review.
    """

    payload = crawler_asset_payload_from_web_values(
        asset_id,
        values,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    response: dict[str, object] = {
        "asset_id": asset_id,
        "execute": execute,
        "bounds_payload": payload.to_dict(),
        "next_action": "click_build_plan_to_call_backend" if not execute else "review_plan_outcome",
    }
    if not execute:
        return response

    target_db = Path(db_path) if db_path is not None else state_file(WEB_PREVIEW_DB_NAME)
    target_downloads = Path(downloads_root) if downloads_root is not None else default_local_downloads_root()
    with contextlib.closing(connect_db(target_db)) as conn:
        repository = ApiCatalogRepository(conn)
        repository.init_schema()
        repository.seed_builtin_providers()
        result = build_crawler_asset_download_plan(
            asset_id,
            conn,
            bounds_payload=payload,
            downloads_root=target_downloads,
            primary_path=primary_path,
            local_path=local_path,
            profile_path=profile_path,
        )
        conn.commit()
    response["plan_result"] = result.to_dict()
    response["next_action"] = result.user_next_action
    return response


def _crawler_asset(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAsset:
    key = asset_id.strip()
    for asset in load_crawler_assets(primary_path, local_path, profile_path):
        if asset.asset_id == key:
            return asset
    raise KeyError(f"crawler asset not found: {asset_id}")
