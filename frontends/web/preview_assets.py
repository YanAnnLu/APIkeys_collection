"""Crawler asset read-model helpers for the Web Preview.

This module owns browser-facing asset cards, detail payloads, seed windows, and
seed favorite updates.  Endpoint handlers should call these helpers instead of
rebuilding asset display shapes inline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from api_launcher.crawler_asset_display import (
    crawler_asset_bound_form_payload,
    crawler_asset_card_capabilities,
    crawler_asset_flow_steps,
)
from api_launcher.crawler_next_action_display import next_action_display_label
from api_launcher.crawler_asset_profiles import crawler_asset_favorite_seed_uids
from api_launcher.crawler_assets import CrawlerAsset, load_crawler_assets
from api_launcher.crawler_seed_registry import crawler_seed_page, crawler_seed_row, save_crawler_seed_favorite
from api_launcher.event_log import log_event
from api_launcher.local_credentials import crawler_asset_credential_status
from frontends.web.preview_context import (
    crawler_asset_bound_form,
    crawler_asset_for_preview,
    web_preview_repository_context,
)
from frontends.web.preview_events import (
    recent_crawler_asset_listing_outcomes,
    recent_crawler_asset_plan_outcomes,
    recent_crawler_asset_plan_passports,
)


def crawler_asset_cards(
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Return compact cards for the Web Preview asset rail."""

    assets = load_crawler_assets(primary_path, local_path, profile_path)
    latest_plan_outcomes = recent_crawler_asset_plan_outcomes()
    latest_plan_passports = recent_crawler_asset_plan_passports()
    latest_listings = recent_crawler_asset_listing_outcomes()
    return {
        "count": len(assets),
        "assets": [
            crawler_asset_card(
                asset,
                latest_plan_outcome=latest_plan_outcomes.get(asset.asset_id),
                latest_plan_passport=asset.latest_plan_passport or latest_plan_passports.get(asset.asset_id),
                latest_listing=latest_listings.get(asset.asset_id),
                env_path=env_path,
            )
            for asset in assets
        ],
    }


def crawler_asset_card(
    asset: CrawlerAsset,
    *,
    latest_plan_outcome: dict[str, object] | None = None,
    latest_plan_passport: dict[str, object] | None = None,
    latest_listing: dict[str, object] | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Build the compact card payload shown in the asset rail."""

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
        "capability_profile": asset.capability_profile.to_dict(),
        "capabilities": crawler_asset_card_capabilities(asset.capabilities),
        "credentials": crawler_asset_credential_status(asset, env_path=env_path),
        "next_action": asset.next_action,
        "next_action_label": next_action_display_label(asset.next_action),
        "latest_listing": latest_listing or {},
        "latest_plan_outcome": latest_plan_outcome or {},
        "latest_plan_passport": latest_plan_passport or {},
    }


def crawler_asset_detail(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    """Return detail payload for one asset, including form and flow contracts."""

    asset = crawler_asset_for_preview(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    form_spec = crawler_asset_bound_form(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    return {
        "asset": asset.to_dict(),
        "card": crawler_asset_card(
            asset,
            latest_plan_outcome=recent_crawler_asset_plan_outcomes().get(asset.asset_id),
            latest_plan_passport=asset.latest_plan_passport
            or recent_crawler_asset_plan_passports().get(asset.asset_id),
            latest_listing=recent_crawler_asset_listing_outcomes().get(asset.asset_id),
            env_path=env_path,
        ),
        "bound_form": crawler_asset_bound_form_payload(form_spec),
        "flow_steps": crawler_asset_flow_steps(asset, form_spec),
    }


def crawler_asset_seed_page(
    asset_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    db_path: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Return a paged view of seeds already enumerated into the local catalog."""

    asset = crawler_asset_for_preview(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    favorite_seed_uids = set(crawler_asset_favorite_seed_uids(asset.asset_id, profile_path))
    with web_preview_repository_context(db_path) as session:
        return crawler_seed_page(
            session.repository,
            asset_id=asset.asset_id,
            provider_id=asset.provider_id,
            page=page,
            page_size=page_size,
            favorite_seed_uids=favorite_seed_uids,
        )


def crawler_asset_seed_row(
    dataset: object,
    *,
    favorite_seed_uids: set[str] | frozenset[str] | None = None,
) -> dict[str, object]:
    return crawler_seed_row(dataset, favorite_seed_uids=favorite_seed_uids or ())


def save_crawler_asset_seed_favorite(
    asset_id: str,
    payload: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, object]:
    """Persist a seed-level favorite for shared crawler asset profile state."""

    asset = crawler_asset_for_preview(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    dataset_uid = str(payload.get("dataset_uid") or "").strip()
    favorite = bool(payload.get("favorite", True))
    result = save_crawler_seed_favorite(
        asset_id=asset.asset_id,
        dataset_uid=dataset_uid,
        favorite=favorite,
        profile_path=profile_path,
    )
    log_event(
        "crawler_asset_seed_favorite_updated",
        "Web Preview updated a seed-level favorite.",
        component="web.crawler_assets",
        context=result,
    )
    return result


def crawler_asset_credential_detail(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict[str, object]:
    asset = crawler_asset_for_preview(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    return crawler_asset_credential_status(asset, env_path=env_path)
