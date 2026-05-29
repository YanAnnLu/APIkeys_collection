"""Shared setup helpers for RRKAL Web Preview endpoints.

The route module should decide endpoint behavior explicitly.  This module only
normalizes repeated setup: repository sessions, crawler asset lookup, bounds
payload parsing, and local credential status lookup.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection
from typing import Iterator, Mapping

from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundFormSpec,
    CrawlerAssetBoundPayload,
    crawler_asset_bound_payload_from_form_values,
)
from api_launcher.crawler_asset_schema_probe import crawler_asset_bound_form_spec
from api_launcher.crawler_assets import CrawlerAsset, load_crawler_assets
from api_launcher.db import connect_db
from api_launcher.local_credentials import crawler_asset_credential_status
from api_launcher.paths import state_file
from api_launcher.repository import ApiCatalogRepository
from frontends.web.preview_payloads import WEB_PREVIEW_DB_NAME


@dataclass(frozen=True)
class WebPreviewRepositorySession:
    db_path: Path
    conn: Connection
    repository: ApiCatalogRepository


@dataclass(frozen=True)
class WebCrawlerAssetActionContext:
    asset: CrawlerAsset
    credential_guard: Mapping[str, object]
    bounds_payload: CrawlerAssetBoundPayload


def crawler_asset_for_preview(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAsset:
    """Return one configured crawler asset or fail with the existing KeyError."""

    key = asset_id.strip()
    for asset in load_crawler_assets(primary_path, local_path, profile_path):
        if asset.asset_id == key:
            return asset
    raise KeyError(f"crawler asset not found: {asset_id}")


def crawler_asset_bound_form(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAssetBoundFormSpec:
    return crawler_asset_bound_form_spec(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )


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


def web_crawler_asset_action_context(
    asset_id: str,
    values: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> WebCrawlerAssetActionContext:
    """Resolve common endpoint inputs without making route policy choices."""

    asset = crawler_asset_for_preview(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    return WebCrawlerAssetActionContext(
        asset=asset,
        credential_guard=crawler_asset_credential_status(asset, env_path=env_path),
        bounds_payload=crawler_asset_payload_from_web_values(
            asset_id,
            values,
            primary_path=primary_path,
            local_path=local_path,
            profile_path=profile_path,
        ),
    )


@contextlib.contextmanager
def web_preview_repository_context(
    db_path: str | Path | None = None,
    *,
    seed_builtin_providers: bool = False,
) -> Iterator[WebPreviewRepositorySession]:
    """Open a Web Preview repository session without hiding commit policy."""

    target_db = Path(db_path) if db_path is not None else state_file(WEB_PREVIEW_DB_NAME)
    with contextlib.closing(connect_db(target_db)) as conn:
        repository = ApiCatalogRepository(conn)
        repository.init_schema()
        if seed_builtin_providers:
            repository.seed_builtin_providers()
        yield WebPreviewRepositorySession(db_path=target_db, conn=conn, repository=repository)
