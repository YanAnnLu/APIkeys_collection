"""Tk project maturity view backed by the shared maturity payload."""

from __future__ import annotations

import contextlib
from pathlib import Path
from tkinter import messagebox
from typing import Any

import APIkeys_collection as core
from api_launcher.event_log import log_event
from api_launcher.project_maturity import build_project_maturity_payload
from frontends.tk.ui_config import DB_PATH


def project_maturity_payload(*, db_path: str | Path | None = None) -> dict[str, object]:
    """Return the same project maturity payload used by CLI and Web Preview."""

    target_db = Path(db_path) if db_path is not None else DB_PATH
    with contextlib.closing(core.connect_db(target_db)) as conn:
        repository = core.ApiCatalogRepository(conn)
        repository.init_schema()
        return build_project_maturity_payload(repository, db_path=target_db)


def project_maturity_message(payload: dict[str, object]) -> str:
    """Render a compact Tk message without reinterpreting maturity rules."""

    closure = payload.get("canonical_delivery_scope")
    if not isinstance(closure, dict):
        closure = {}
    rows = payload.get("rows")
    if not isinstance(rows, list):
        rows = []
    row_lines = [_project_maturity_row_line(row) for row in rows if isinstance(row, dict)]
    return "\n".join(
        [
            "RRKAL project maturity matrix",
            "",
            "Delivery scope: "
            f"{closure.get('closure_percent', 'unknown')}% / "
            f"{closure.get('status_label') or '交付狀態待確認'}",
            str(payload.get("answer_template_zh_TW") or payload.get("reporting_rule") or ""),
            "",
            "Rows:",
            *(row_lines or ["No maturity rows returned."]),
            "",
            "Tk only displays backend payload. It does not calculate a single project percentage.",
        ]
    )


def _project_maturity_row_line(row: dict[str, Any]) -> str:
    display_profile = row.get("display_profile")
    if not isinstance(display_profile, dict):
        display_profile = {}
    icon = str(row.get("status_icon") or display_profile.get("status_icon") or "?")
    area = str(row.get("area_label") or "成熟度面向待確認")
    label = str(row.get("display_label") or row.get("maturity_label_zh_TW") or "成熟度狀態待確認")
    limitation_count = len(row.get("current_limitations") or []) if isinstance(row.get("current_limitations"), list) else 0
    suffix = f" ({limitation_count} limit)" if limitation_count == 1 else f" ({limitation_count} limits)" if limitation_count else ""
    return f"- {icon} {area}: {label}{suffix}"


class ProjectMaturityWorkflowMixin:
    """Thin Tk hook for project maturity; backend owns the matrix semantics."""

    def open_project_maturity_matrix(self) -> dict[str, object]:
        payload = project_maturity_payload()
        log_event(
            "tk_project_maturity_matrix_opened",
            "Tk opened the project maturity matrix summary.",
            component="ui.project_maturity",
            context={
                "matrix_version": payload.get("matrix_version"),
                "row_count": len(payload.get("rows") or []) if isinstance(payload.get("rows"), list) else 0,
            },
        )
        messagebox.showinfo(
            self.tr("專案成熟度矩陣", "Project maturity matrix"),
            project_maturity_message(payload),
            parent=self.root,
        )
        self.status_var.set(self.tr("已顯示專案成熟度矩陣。", "Project maturity matrix shown."))
        return payload
