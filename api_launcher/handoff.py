from __future__ import annotations

import subprocess
from dataclasses import dataclass

from api_launcher.event_log import latest_events
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class HandoffSnapshot:
    git_status: str
    git_head: str
    provider_count: int
    dataset_count: int
    manifest_health: dict[str, int]
    recent_logs: list[dict[str, object]]


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


def _git_output(*args: str) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return (result.stdout or result.stderr).strip()
