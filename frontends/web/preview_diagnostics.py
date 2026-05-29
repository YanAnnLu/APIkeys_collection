"""Developer diagnostics and status helpers for the Web Preview."""

from __future__ import annotations

from pathlib import Path

from api_launcher.developer_diagnostics import crawler_handler_smoke_diagnostics_payload
from api_launcher.event_log import log_event
from api_launcher.project_maturity import build_project_maturity_payload
from api_launcher.web_real_download_demo import run_web_real_download_demo
from frontends.web.preview_context import web_preview_repository_context


def web_preview_status() -> dict[str, object]:
    """Return a small machine-readable status for browser smoke checks."""

    return {
        "product": "RuRuKa Asset Launcher",
        "surface": "web_preview",
        "purpose": "uiux_review",
        "business_logic_owner": "api_launcher",
    }


def web_project_maturity(*, db_path: str | Path | None = None) -> dict[str, object]:
    """Return the maturity matrix for the Web Preview maturity tab."""

    with web_preview_repository_context(db_path) as session:
        return build_project_maturity_payload(session.repository, db_path=session.db_path)


def crawler_handler_smoke_diagnostics() -> dict[str, object]:
    """Return a compact developer-only crawler handler contract diagnostic."""

    return crawler_handler_smoke_diagnostics_payload("web_preview")


def web_real_download_demo() -> dict[str, object]:
    """Run the narrow real-download proof path for Web Preview."""

    result = run_web_real_download_demo()
    payload = result.to_dict()
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    log_event(
        "web_real_download_demo_completed",
        "Web Preview completed a real public CSV download/import demo.",
        component="web.demo",
        context={
            "stage": payload.get("stage"),
            "succeeded": payload.get("succeeded"),
            "row_count": payload.get("row_count"),
            "table_name": payload.get("table_name"),
            "source_url": payload.get("source_url"),
            "downloaded_file": artifacts.get("downloaded_file"),
            "manifest": artifacts.get("manifest"),
            "curated_sqlite": artifacts.get("curated_sqlite"),
            "next_action": payload.get("next_action"),
        },
    )
    return payload


def developer_real_download_demo() -> dict[str, object]:
    """Run the public CSV proof path as a developer-only diagnostic."""

    payload = web_real_download_demo()
    payload["developer_only"] = True
    payload["scope"] = "developer_diagnostic_public_csv_not_main_download_flow"
    payload["main_download_endpoint"] = "POST /api/crawler-assets/{asset_id}/download-import"
    payload["seed_download_endpoint"] = "POST /api/crawler-assets/{asset_id}/seed-download-import"
    return payload

