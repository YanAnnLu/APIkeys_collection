"""Developer diagnostics payloads shared by CLI, Tk, Web Preview, and future Qt."""

from __future__ import annotations

from api_launcher.crawler_asset_display import next_action_display_label
from api_launcher.crawler_audit_smoke import crawler_handler_audit_smoke_summary


CRAWLER_HANDLER_SMOKE_DIAGNOSTIC_ID = "crawler_handler_contract_smoke"
DEVELOPER_DIAGNOSTICS_PURPOSE = "developer_diagnostics"
OFFLINE_CONTRACT_SMOKE_SCOPE = "offline_contract_smoke_no_live_network"
HANDLER_SMOKE_NEXT_ACTION = "run_dataset_discovery_handler_smoke_json_if_summary_fails"


def crawler_handler_smoke_diagnostics_payload(surface: str) -> dict[str, object]:
    """Return a compact developer-only crawler handler contract diagnostic payload."""

    clean_surface = surface.strip() if surface.strip() else "unknown"
    return {
        "surface": clean_surface,
        "purpose": DEVELOPER_DIAGNOSTICS_PURPOSE,
        "diagnostic_id": CRAWLER_HANDLER_SMOKE_DIAGNOSTIC_ID,
        "developer_only": True,
        "scope": OFFLINE_CONTRACT_SMOKE_SCOPE,
        "summary": crawler_handler_audit_smoke_summary(),
        "next_action": HANDLER_SMOKE_NEXT_ACTION,
        "next_action_label": next_action_display_label(HANDLER_SMOKE_NEXT_ACTION),
    }


__all__ = [
    "CRAWLER_HANDLER_SMOKE_DIAGNOSTIC_ID",
    "DEVELOPER_DIAGNOSTICS_PURPOSE",
    "HANDLER_SMOKE_NEXT_ACTION",
    "OFFLINE_CONTRACT_SMOKE_SCOPE",
    "crawler_handler_smoke_diagnostics_payload",
]
