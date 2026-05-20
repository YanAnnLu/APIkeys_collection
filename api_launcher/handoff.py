from __future__ import annotations

import subprocess
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME, load_dataset_discovery_sources
from api_launcher.db import utc_now_iso
from api_launcher.discovery import LOCAL_SEEDS_NAME, load_discovery_seeds
from api_launcher.event_log import latest_events
from api_launcher.paths import local_config_file, project_path
from api_launcher.portal_intake import DEFAULT_PORTAL_INTAKE_PATH, build_portal_intake_payload
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class HandoffSnapshot:
    generated_at: str
    git_status: str
    git_head: str
    provider_count: int
    dataset_count: int
    manifest_health: dict[str, int]
    verification_summary: dict[str, str]
    open_gtd_summary: dict[str, Any]
    open_gtd_items: list[dict[str, str]]
    recent_logs: list[dict[str, object]]
    portal_intake_summary: dict[str, Any]
    local_discovery_summary: dict[str, Any]


def build_handoff_snapshot(repository: ApiCatalogRepository, log_limit: int = 5) -> HandoffSnapshot:
    provider_count = repository.conn.execute("SELECT COUNT(*) AS n FROM providers").fetchone()["n"]
    dataset_count = repository.conn.execute("SELECT COUNT(*) AS n FROM datasets").fetchone()["n"]
    display_log_limit = max(0, log_limit)
    recent_logs = latest_events(max(display_log_limit, 50))
    open_gtd_items = parse_open_gtd_items(project_path("docs/PROJECT_GTD.md"))
    return HandoffSnapshot(
        generated_at=utc_now_iso(),
        git_status=_git_output("git", "status", "--short", "--branch"),
        git_head=_git_output("git", "log", "-1", "--oneline"),
        provider_count=int(provider_count),
        dataset_count=int(dataset_count),
        manifest_health=repository.dataset_asset_manifest_health_summary(),
        verification_summary=verification_summary(repository, recent_logs),
        open_gtd_summary=gtd_status_summary(open_gtd_items),
        open_gtd_items=open_gtd_items[:12],
        recent_logs=recent_logs[-display_log_limit:] if display_log_limit else [],
        portal_intake_summary=portal_intake_summary(project_path(DEFAULT_PORTAL_INTAKE_PATH)),
        local_discovery_summary=local_discovery_summary(),
    )


def render_handoff_markdown(snapshot: HandoffSnapshot) -> str:
    lines = [
        "# APIkeys_collection Handoff",
        "",
        f"Generated at: {snapshot.generated_at}",
        "",
        "## Git",
        "",
        "```text",
        snapshot.git_status.strip() or "(clean status unavailable)",
        snapshot.git_head.strip() or "(head unavailable)",
        "```",
        "",
        "## Catalog",
        "",
        f"- providers: {snapshot.provider_count}",
        f"- datasets: {snapshot.dataset_count}",
        f"- manifest_health: {snapshot.manifest_health}",
        "",
        "## Verification Timestamps",
        "",
        f"- latest_manifest_verified_at: {snapshot.verification_summary.get('latest_manifest_verified_at', '') or 'none'}",
        f"- latest_asset_verified_at: {snapshot.verification_summary.get('latest_asset_verified_at', '') or 'none'}",
        f"- latest_verification_event_at: {snapshot.verification_summary.get('latest_verification_event_at', '') or 'none'}",
        f"- latest_verification_event: {snapshot.verification_summary.get('latest_verification_event', '') or 'none'}",
        "",
        "## Open GTD Focus",
        "",
        f"- open_gtd_total: {snapshot.open_gtd_summary.get('total', 0)}",
        f"- open_gtd_by_status: {snapshot.open_gtd_summary.get('by_status', {})}",
        "",
    ]
    if not snapshot.open_gtd_items:
        lines.append("- no open GTD items found")
    for item in snapshot.open_gtd_items:
        lines.append(f"- {item.get('area', '')} [{item.get('status', '')}]: {item.get('next_step', '')}")
    lines.extend(
        [
            "",
            "## Portal Intake / Local Discovery",
            "",
            f"- portal_intake_rows: {snapshot.portal_intake_summary.get('row_count', 0)}",
            f"- portal_intake_actionable: {snapshot.portal_intake_summary.get('actionable_count', 0)}",
            f"- portal_intake_warnings: {snapshot.portal_intake_summary.get('warning_count', 0)}",
            f"- portal_intake_actions: {snapshot.portal_intake_summary.get('actions', {})}",
            f"- local_provider_seeds: {snapshot.local_discovery_summary.get('local_provider_seed_count', 0)}",
            f"- local_dataset_sources: {snapshot.local_discovery_summary.get('local_dataset_source_count', 0)}",
            f"- local_provider_seed_path: {snapshot.local_discovery_summary.get('local_provider_seed_path', '')}",
            f"- local_dataset_source_path: {snapshot.local_discovery_summary.get('local_dataset_source_path', '')}",
            "",
            "Promotion flow:",
            "",
            "```bash",
            "conda run -n metal_trade_312 python APIkeys_collection.py --portal-intake-report --write-portal-intake-json state/portal_intake.review.json",
            "conda run -n metal_trade_312 python APIkeys_collection.py --promote-portal-intake-local",
            "conda run -n metal_trade_312 python APIkeys_collection.py --promote-local-discovery-catalog --promote-local-discovery-dry-run --write-local-discovery-audit-json state/local_discovery_audit.json",
            "```",
            "",
            "## Recent Logs",
            "",
        ]
    )
    if not snapshot.recent_logs:
        lines.append("- no recent structured log events")
    for event in snapshot.recent_logs:
        lines.append(
            "- "
            f"{event.get('timestamp', '')} "
            f"{event.get('level', '')} "
            f"{event.get('component', '')}:{event.get('event', '')} "
            f"{event.get('message', '')}"
        )
    lines.append("")
    lines.extend(
        [
            "## Suggested Resume Checks",
            "",
            "```powershell",
            "git status --short --branch",
            "$env:PYTHONDONTWRITEBYTECODE='1'; py -m unittest discover -s tests",
            "py APIkeys_collection.py --verify-downloads --manifest-health",
            "py APIkeys_collection.py --verify-downloads-json",
            "docker compose -f docker-compose.yml run --rm --build launcher",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def parse_open_gtd_items(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [
            {
                "area": "PROJECT_GTD.md",
                "status": "error",
                "next_step": f"{type(exc).__name__}: {exc}",
            }
        ]
    items: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = markdown_table_cells(line)
        if len(cells) < 4:
            continue
        area, status, _progress, next_step = cells[:4]
        normalized_status = status.strip().lower()
        if area.lower() == "area" or set(status) <= {"-", " "}:
            continue
        if not next_step or normalized_status == "done":
            continue
        items.append({"area": area, "status": status, "next_step": next_step})
    return sorted(items, key=_gtd_sort_key)


def gtd_status_summary(items: list[dict[str, str]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    for item in items:
        status = item.get("status", "unknown") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
    return {"total": len(items), "by_status": by_status}


def markdown_table_cells(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    for char in text:
        if char == "`":
            in_code = not in_code
            current.append(char)
            continue
        if char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def verification_summary(repository: ApiCatalogRepository, events: list[dict[str, object]]) -> dict[str, str]:
    latest_event = latest_verification_event(events)
    return {
        "latest_manifest_verified_at": latest_table_timestamp(
            repository.conn,
            "dataset_asset_manifests",
            "last_verified_at",
        ),
        "latest_asset_verified_at": latest_table_timestamp(
            repository.conn,
            "provider_installation_assets",
            "last_verified_at",
        ),
        "latest_verification_event_at": str(latest_event.get("timestamp") or "") if latest_event else "",
        "latest_verification_event": str(latest_event.get("event") or "") if latest_event else "",
    }


def latest_table_timestamp(conn: sqlite3.Connection, table: str, column: str) -> str:
    if not table.replace("_", "").isalnum() or not column.replace("_", "").isalnum():
        return ""
    try:
        row = conn.execute(
            f"SELECT MAX({column}) AS value FROM {table} WHERE COALESCE({column}, '') != ''"
        ).fetchone()
    except sqlite3.Error:
        return ""
    return str(row["value"] or "") if row and row["value"] else ""


def latest_verification_event(events: list[dict[str, object]]) -> dict[str, object]:
    for event in reversed(events):
        event_name = str(event.get("event") or "").lower()
        component = str(event.get("component") or "").lower()
        haystack = f"{component} {event_name}"
        if any(token in haystack for token in ("verify", "verification", "self_check", "repair", "manifest")):
            return event
    return {}


def _gtd_sort_key(item: dict[str, str]) -> tuple[int, str]:
    order = {
        "in progress": 0,
        "skeleton": 1,
        "planned": 2,
        "mvp": 3,
    }
    return (order.get(item.get("status", "").strip().lower(), 9), item.get("area", ""))


def portal_intake_summary(path: Path) -> dict[str, Any]:
    try:
        payload = build_portal_intake_payload(path)
    except Exception as exc:
        return {
            "row_count": 0,
            "actionable_count": 0,
            "warning_count": 1,
            "actions": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    summary = payload.get("summary", {})
    return {
        "row_count": int(summary.get("row_count") or 0),
        "actionable_count": int(summary.get("actionable_count") or 0),
        "warning_count": int(summary.get("warning_count") or 0),
        "actions": dict(summary.get("actions") or {}),
    }


def local_discovery_summary() -> dict[str, Any]:
    provider_seed_path = local_config_file(LOCAL_SEEDS_NAME)
    dataset_source_path = local_config_file(LOCAL_DATASET_DISCOVERY_SOURCES_NAME)
    provider_seed_count = safe_count_provider_seeds(provider_seed_path)
    dataset_source_count = safe_count_dataset_sources(dataset_source_path)
    return {
        "local_provider_seed_path": str(provider_seed_path),
        "local_dataset_source_path": str(dataset_source_path),
        "local_provider_seed_count": provider_seed_count,
        "local_dataset_source_count": dataset_source_count,
    }


def safe_count_provider_seeds(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(load_discovery_seeds(path))
    except Exception:
        return 0


def safe_count_dataset_sources(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(load_dataset_discovery_sources(path))
    except Exception:
        return 0


def _git_output(*args: str) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return (result.stdout or result.stderr).strip()
