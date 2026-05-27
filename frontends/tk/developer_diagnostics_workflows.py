"""Developer-only diagnostics workflows for the Tk control panel."""

from __future__ import annotations

from typing import Any
from tkinter import messagebox

from api_launcher.developer_diagnostics import (
    crawler_handler_smoke_diagnostics_payload as backend_crawler_handler_smoke_diagnostics_payload,
)
from api_launcher.event_log import log_event


def crawler_handler_smoke_diagnostics_payload() -> dict[str, object]:
    """Return the same compact crawler handler smoke payload used by Web Preview."""

    return backend_crawler_handler_smoke_diagnostics_payload("tk")


def crawler_handler_smoke_diagnostics_message(payload: dict[str, object]) -> str:
    """Render a short human-readable Tk message without exposing per-source reports."""

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    return "\n".join(
        [
            "Crawler handler contract smoke",
            "",
            f"Surface: {payload.get('surface', '')}",
            f"Scope: {payload.get('scope', '')}",
            f"Supported source types: {summary.get('supported_source_type_count', 0)}",
            f"Empty-case status: {summary.get('empty_case_status', '')}",
            f"Empty-case zero-candidate warnings: {summary.get('empty_case_zero_candidates', 0)}",
            f"Candidate-case status: {summary.get('candidate_case_status', '')}",
            f"Candidate-case pass sources: {summary.get('candidate_case_pass_sources', 0)}",
            "",
            f"Next action: {payload.get('next_action_label') or summary.get('next_action') or payload.get('next_action', '')}",
            f"Command: {summary.get('command', '')}",
            "",
            "Developer-only: this is an offline contract smoke. It does not prove live NASA/NOAA/CKAN endpoints are reachable.",
        ]
    )


class DeveloperDiagnosticsWorkflowMixin:
    """Thin Tk hooks for diagnostics; business logic stays in api_launcher."""

    def open_crawler_handler_smoke_diagnostics(self) -> dict[str, object]:
        payload = crawler_handler_smoke_diagnostics_payload()
        summary = payload.get("summary")
        context: dict[str, Any] = {
            "diagnostic_id": payload.get("diagnostic_id"),
            "developer_only": payload.get("developer_only"),
        }
        if isinstance(summary, dict):
            context.update(
                {
                    "supported_source_type_count": summary.get("supported_source_type_count"),
                    "empty_case_status": summary.get("empty_case_status"),
                    "candidate_case_status": summary.get("candidate_case_status"),
                }
            )
        log_event(
            "tk_crawler_handler_smoke_diagnostics_opened",
            "Tk developer diagnostics opened crawler handler contract smoke summary.",
            component="ui.developer_diagnostics",
            context=context,
        )
        messagebox.showinfo(
            self.tr("開發者診斷：Crawler handler smoke", "Developer diagnostics: crawler handler smoke"),
            crawler_handler_smoke_diagnostics_message(payload),
            parent=self.root,
        )
        self.status_var.set(
            self.tr(
                "已顯示開發者診斷：Crawler handler contract smoke。",
                "Developer diagnostics shown: crawler handler contract smoke.",
            )
        )
        return payload
