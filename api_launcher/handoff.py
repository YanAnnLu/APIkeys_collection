from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME, load_dataset_discovery_sources
from api_launcher.discovery import LOCAL_SEEDS_NAME, load_discovery_seeds
from api_launcher.event_log import latest_events
from api_launcher.paths import local_config_file, project_path
from api_launcher.portal_intake import DEFAULT_PORTAL_INTAKE_PATH, build_portal_intake_payload
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class HandoffSnapshot:
    git_status: str
    git_head: str
    provider_count: int
    dataset_count: int
    manifest_health: dict[str, int]
    recent_logs: list[dict[str, object]]
    portal_intake_summary: dict[str, Any]
    local_discovery_summary: dict[str, Any]


def build_handoff_snapshot(repository: ApiCatalogRepository, log_limit: int = 5) -> HandoffSnapshot:
    provider_count = repository.conn.execute("SELECT COUNT(*) AS n FROM providers").fetchone()["n"]
    dataset_count = repository.conn.execute("SELECT COUNT(*) AS n FROM datasets").fetchone()["n"]
    return HandoffSnapshot(
        git_status=_git_output("git", "status", "--short", "--branch"),
        git_head=_git_output("git", "log", "-1", "--oneline"),
        provider_count=int(provider_count),
        dataset_count=int(dataset_count),
        manifest_health=repository.dataset_asset_manifest_health_summary(),
        recent_logs=latest_events(log_limit),
        portal_intake_summary=portal_intake_summary(project_path(DEFAULT_PORTAL_INTAKE_PATH)),
        local_discovery_summary=local_discovery_summary(),
    )


def render_handoff_markdown(snapshot: HandoffSnapshot) -> str:
    lines = [
        "# APIkeys_collection Handoff",
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
