from __future__ import annotations

import subprocess
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME, load_dataset_discovery_sources
from api_launcher.data_store_connections import data_store_env_template_filename
from api_launcher.db import utc_now_iso
from api_launcher.discovery import LOCAL_SEEDS_NAME, load_discovery_seeds
from api_launcher.event_log import latest_events
from api_launcher.integrations import active_data_store_profile
from api_launcher.paths import local_config_file, project_path
from api_launcher.portal_intake import DEFAULT_PORTAL_INTAKE_PATH, build_portal_intake_payload
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class HandoffSnapshot:
    # 這份 snapshot 是 CLI 輸出的中介資料；保持純資料結構，方便測試與未來 UI 重用。
    generated_at: str
    git_status: str
    git_head: str
    provider_count: int
    dataset_count: int
    manifest_health: dict[str, int]
    data_store_summary: dict[str, str]
    verification_summary: dict[str, str]
    mvp_readiness: dict[str, Any]
    open_gtd_summary: dict[str, Any]
    open_gtd_items: list[dict[str, str]]
    recent_logs: list[dict[str, object]]
    portal_intake_summary: dict[str, Any]
    local_discovery_summary: dict[str, Any]


def build_handoff_snapshot(repository: ApiCatalogRepository, log_limit: int = 5) -> HandoffSnapshot:
    # Handoff 報告故意只做讀取與彙整，不修改 registry 或任何本機設定。
    provider_count = repository.conn.execute("SELECT COUNT(*) AS n FROM providers").fetchone()["n"]
    dataset_count = repository.conn.execute("SELECT COUNT(*) AS n FROM datasets").fetchone()["n"]
    display_log_limit = max(0, log_limit)
    # 讀取比顯示更多的事件，讓時間摘要仍能找到最近的修復或驗證事件。
    recent_logs = latest_events(max(display_log_limit, 50))
    open_gtd_items = parse_open_gtd_items(project_path("docs/PROJECT_GTD.md"))
    manifest_health = repository.dataset_asset_manifest_health_summary()
    verification = verification_summary(repository, recent_logs)
    return HandoffSnapshot(
        generated_at=utc_now_iso(),
        git_status=_git_output("git", "status", "--short", "--branch"),
        git_head=_git_output("git", "log", "-1", "--oneline"),
        provider_count=int(provider_count),
        dataset_count=int(dataset_count),
        manifest_health=manifest_health,
        data_store_summary=data_store_handoff_summary(),
        verification_summary=verification,
        mvp_readiness=mvp_readiness_summary(verification, manifest_health),
        open_gtd_summary=gtd_status_summary(open_gtd_items),
        open_gtd_items=open_gtd_items[:12],
        recent_logs=recent_logs[-display_log_limit:] if display_log_limit else [],
        portal_intake_summary=portal_intake_summary(project_path(DEFAULT_PORTAL_INTAKE_PATH)),
        local_discovery_summary=local_discovery_summary(),
    )


def render_handoff_markdown(snapshot: HandoffSnapshot) -> str:
    # Markdown 是給人與下一位 agent 共讀的格式；不要在這裡塞 UI 專用結構。
    lines = [
        "# RuRuKa Asset Launcher Handoff",
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
        "## MVP Readiness",
        "",
        f"- mvp_readiness_status: {snapshot.mvp_readiness.get('status', '')}",
        f"- mvp_readiness_status_zh_TW: {snapshot.mvp_readiness.get('status_zh_TW', '')}",
        f"- remaining_percent_estimate: {snapshot.mvp_readiness.get('remaining_percent_estimate', '')}",
        f"- canonical_smoke: {snapshot.mvp_readiness.get('canonical_smoke', {})}",
        f"- blockers: {snapshot.mvp_readiness.get('blockers', [])}",
        f"- warnings: {snapshot.mvp_readiness.get('warnings', [])}",
        "",
        "## Data Store Profile",
        "",
        f"- active_profile: {snapshot.data_store_summary.get('active_profile', '') or 'none'}",
        f"- active_engine: {snapshot.data_store_summary.get('engine', '') or 'none'}",
        f"- active_store_kind: {snapshot.data_store_summary.get('store_kind', '') or 'none'}",
        f"- required_env_vars: {snapshot.data_store_summary.get('required_env_vars', '') or '-'}",
        f"- test_command: {snapshot.data_store_summary.get('test_command', '') or '-'}",
        f"- test_json_command: {snapshot.data_store_summary.get('test_json_command', '') or '-'}",
        f"- env_template_command: {snapshot.data_store_summary.get('env_template_command', '') or '-'}",
        "",
        "## Verification Timestamps",
        "",
        f"- latest_manifest_verified_at: {snapshot.verification_summary.get('latest_manifest_verified_at', '') or 'none'}",
        f"- latest_asset_verified_at: {snapshot.verification_summary.get('latest_asset_verified_at', '') or 'none'}",
        f"- latest_verification_event_at: {snapshot.verification_summary.get('latest_verification_event_at', '') or 'none'}",
        f"- latest_verification_event: {snapshot.verification_summary.get('latest_verification_event', '') or 'none'}",
        f"- latest_download_requeue_event_at: {snapshot.verification_summary.get('latest_download_requeue_event_at', '') or 'none'}",
        f"- latest_download_requeue_outcome: {snapshot.verification_summary.get('latest_download_requeue_outcome', '') or 'none'}",
        f"- latest_adapter_review_json_event_at: {snapshot.verification_summary.get('latest_adapter_review_json_event_at', '') or 'none'}",
        f"- latest_adapter_review_json_output: {snapshot.verification_summary.get('latest_adapter_review_json_output', '') or 'none'}",
        f"- latest_adapter_review_json_outcomes: {snapshot.verification_summary.get('latest_adapter_review_json_outcomes', '') or '{}'}",
        f"- latest_adapter_plan_resolved_event_at: {snapshot.verification_summary.get('latest_adapter_plan_resolved_event_at', '') or 'none'}",
        f"- latest_adapter_plan_resolved_output: {snapshot.verification_summary.get('latest_adapter_plan_resolved_output', '') or 'none'}",
        f"- latest_adapter_plan_resolved_counts: {snapshot.verification_summary.get('latest_adapter_plan_resolved_counts', '') or '{}'}",
        f"- latest_download_plan_event_at: {snapshot.verification_summary.get('latest_download_plan_event_at', '') or 'none'}",
        f"- latest_download_plan_input: {snapshot.verification_summary.get('latest_download_plan_input', '') or 'none'}",
        f"- latest_download_plan_stage: {snapshot.verification_summary.get('latest_download_plan_stage', '') or 'none'}",
        f"- latest_download_plan_counts: {snapshot.verification_summary.get('latest_download_plan_counts', '') or '{}'}",
        f"- latest_mvp_demo_smoke_event_at: {snapshot.verification_summary.get('latest_mvp_demo_smoke_event_at', '') or 'none'}",
        f"- latest_mvp_demo_smoke_stage: {snapshot.verification_summary.get('latest_mvp_demo_smoke_stage', '') or 'none'}",
        f"- latest_mvp_demo_smoke_result: {snapshot.verification_summary.get('latest_mvp_demo_smoke_result', '') or '{}'}",
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
        # 只列 Next Step，避免把 GTD 的長篇 Current Progress 整段灌進 handoff。
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
        # recent_logs 保持一行一事件，讓終端機與 GitHub comment 都容易掃讀。
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
            "py APIkeys_collection.py --db state/mvp_demo/launcher.sqlite --init-db --seed --run-mvp-demo-smoke-json state/mvp_demo/flow.json",
            "py APIkeys_collection.py --verify-downloads --manifest-health",
            "py APIkeys_collection.py --verify-downloads-json",
            "docker compose -f docker-compose.yml run --rm --build launcher",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def handoff_snapshot_to_dict(snapshot: HandoffSnapshot) -> dict[str, Any]:
    # JSON handoff 給 heartbeat/agent 直接解析；欄位與 Markdown snapshot 同源，避免兩套交接資料分歧。
    return asdict(snapshot)


def parse_open_gtd_items(path: Path) -> list[dict[str, str]]:
    # 這裡直接解析 Markdown 表格，避免 handoff 依賴額外產物或手動同步的 JSON。
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
            # Done 或沒有下一步的項目不該進入 resume focus，避免干擾下一輪開發。
            continue
        items.append({"area": area, "status": status, "next_step": next_step})
    return sorted(items, key=_gtd_sort_key)


def gtd_status_summary(items: list[dict[str, str]]) -> dict[str, Any]:
    # summary 保留狀態分布，讓 heartbeat 或外部 agent 能快速判斷待辦壓力。
    by_status: dict[str, int] = {}
    for item in items:
        status = item.get("status", "unknown") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
    return {"total": len(items), "by_status": by_status}


def data_store_handoff_summary() -> dict[str, str]:
    # Handoff 只列 profile 與命令，不跑連線測試，避免接力報告觸發網路或資料庫 side effect。
    profile = active_data_store_profile()
    if profile is None:
        return {}
    template_path = f"state/data_store_env_templates/{data_store_env_template_filename(profile.profile_id)}"
    return {
        "active_profile": profile.profile_id,
        "engine": profile.engine,
        "store_kind": profile.store_kind,
        "required_env_vars": ", ".join(profile.required_env_vars),
        "test_command": f"python APIkeys_collection.py --test-data-store {profile.profile_id}",
        "test_json_command": f"python APIkeys_collection.py --test-data-store {profile.profile_id} --test-data-store-json",
        "env_template_command": (
            f"python APIkeys_collection.py --write-data-store-env-template {template_path} "
            f"--data-store-env-template-profile {profile.profile_id}"
        ),
    }


def markdown_table_cells(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    # GTD 表格會放模組路徑與 CLI 片段；反引號內的 | 是內容，不是欄位分隔。
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
    # timestamp 來源同時看資料庫與 event log，因為有些驗證流程只更新其中一邊。
    latest_event = latest_verification_event(events)
    latest_requeue_event = latest_event_by_name(events, "download_repair_requeue_requested")
    latest_requeue_context = latest_requeue_event.get("context") if isinstance(latest_requeue_event.get("context"), dict) else {}
    latest_adapter_review_event = latest_event_by_name(events, "adapter_review_json_written")
    latest_adapter_review_context = (
        latest_adapter_review_event.get("context") if isinstance(latest_adapter_review_event.get("context"), dict) else {}
    )
    latest_adapter_plan_event = latest_event_by_name(events, "adapter_plan_resolved")
    latest_adapter_plan_context = (
        latest_adapter_plan_event.get("context") if isinstance(latest_adapter_plan_event.get("context"), dict) else {}
    )
    latest_download_plan_event = latest_event_by_name(events, "download_plan_executed")
    latest_download_plan_context = (
        latest_download_plan_event.get("context") if isinstance(latest_download_plan_event.get("context"), dict) else {}
    )
    latest_mvp_demo_smoke_event = latest_event_by_name(events, "mvp_demo_smoke_completed")
    latest_mvp_demo_smoke_context = (
        latest_mvp_demo_smoke_event.get("context") if isinstance(latest_mvp_demo_smoke_event.get("context"), dict) else {}
    )
    # Resolver 事件可能帶很多路徑與統計；handoff 只固定列出接力判斷最需要的幾個數字。
    adapter_plan_counts = {
        "direct_entries_added": latest_adapter_plan_context.get("direct_entries_added", 0),
        "resolved_review_entries": latest_adapter_plan_context.get("resolved_review_entries", 0),
        "unresolved_review_entries": latest_adapter_plan_context.get("unresolved_review_entries", 0),
        "warning_count": latest_adapter_plan_context.get("warning_count", 0),
    }
    # Download plan 摘要只放穩定計數與下一步，避免 handoff 夾帶龐大的 per-item payload。
    download_plan_counts = {
        "entry_count": latest_download_plan_context.get("entry_count", 0),
        "submitted": latest_download_plan_context.get("submitted", 0),
        "completed": latest_download_plan_context.get("completed", 0),
        "failed": latest_download_plan_context.get("failed", 0),
        "skipped": latest_download_plan_context.get("skipped", 0),
        "imported": latest_download_plan_context.get("imported", 0),
        "import_failed": latest_download_plan_context.get("import_failed", 0),
        "skip_summary": latest_download_plan_context.get("skip_summary", {}),
        "next_action": latest_download_plan_context.get("next_action", ""),
    }
    # MVP demo smoke 是 release/agent 最短閉環；handoff 只列最小驗收欄位，不夾帶完整 pipeline payload。
    mvp_demo_smoke_result = {
        "succeeded": latest_mvp_demo_smoke_context.get("succeeded", False),
        "table_name": latest_mvp_demo_smoke_context.get("table_name", ""),
        "row_count": latest_mvp_demo_smoke_context.get("row_count", 0),
    }
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
        "latest_download_requeue_event_at": str(latest_requeue_event.get("timestamp") or "") if latest_requeue_event else "",
        "latest_download_requeue_outcome": str(latest_requeue_context.get("outcome") or "") if latest_requeue_context else "",
        "latest_adapter_review_json_event_at": (
            str(latest_adapter_review_event.get("timestamp") or "") if latest_adapter_review_event else ""
        ),
        "latest_adapter_review_json_output": (
            str(latest_adapter_review_context.get("output_path") or "") if latest_adapter_review_context else ""
        ),
        "latest_adapter_review_json_outcomes": (
            str(latest_adapter_review_context.get("by_outcome") or {}) if latest_adapter_review_context else ""
        ),
        "latest_adapter_plan_resolved_event_at": (
            str(latest_adapter_plan_event.get("timestamp") or "") if latest_adapter_plan_event else ""
        ),
        "latest_adapter_plan_resolved_output": (
            str(latest_adapter_plan_context.get("output_path") or "") if latest_adapter_plan_context else ""
        ),
        "latest_adapter_plan_resolved_counts": str(adapter_plan_counts) if latest_adapter_plan_context else "",
        "latest_download_plan_event_at": (
            str(latest_download_plan_event.get("timestamp") or "") if latest_download_plan_event else ""
        ),
        "latest_download_plan_input": (
            str(latest_download_plan_context.get("input_plan") or "") if latest_download_plan_context else ""
        ),
        "latest_download_plan_stage": (
            str(latest_download_plan_context.get("stage") or "") if latest_download_plan_context else ""
        ),
        "latest_download_plan_counts": str(download_plan_counts) if latest_download_plan_context else "",
        "latest_mvp_demo_smoke_event_at": (
            str(latest_mvp_demo_smoke_event.get("timestamp") or "") if latest_mvp_demo_smoke_event else ""
        ),
        "latest_mvp_demo_smoke_stage": (
            str(latest_mvp_demo_smoke_context.get("stage") or "") if latest_mvp_demo_smoke_context else ""
        ),
        "latest_mvp_demo_smoke_result": str(mvp_demo_smoke_result) if latest_mvp_demo_smoke_context else "",
        "latest_mvp_demo_smoke_succeeded": (
            "true" if bool(latest_mvp_demo_smoke_context.get("succeeded")) else "false"
        )
        if latest_mvp_demo_smoke_context
        else "",
        "latest_mvp_demo_smoke_table_name": (
            str(latest_mvp_demo_smoke_context.get("table_name") or "") if latest_mvp_demo_smoke_context else ""
        ),
        "latest_mvp_demo_smoke_row_count": (
            str(latest_mvp_demo_smoke_context.get("row_count") or "0") if latest_mvp_demo_smoke_context else ""
        ),
    }


def mvp_readiness_summary(
    verification: dict[str, str],
    manifest_health: dict[str, int],
) -> dict[str, Any]:
    # 這個判斷只收斂 canonical MVP demo，不把 GTD 內的 post-MVP 擴充誤判成 blocker。
    stage = verification.get("latest_mvp_demo_smoke_stage", "")
    succeeded = verification.get("latest_mvp_demo_smoke_succeeded", "") == "true"
    table_name = verification.get("latest_mvp_demo_smoke_table_name", "")
    row_count = parse_int_or_zero(verification.get("latest_mvp_demo_smoke_row_count", ""))
    blockers: list[str] = []
    warnings: list[str] = []

    if not verification.get("latest_mvp_demo_smoke_event_at"):
        blockers.append("no_canonical_mvp_demo_smoke_event")
    if stage != "download_import_completed":
        blockers.append(f"canonical_smoke_stage_not_completed:{stage or 'none'}")
    if not succeeded:
        blockers.append("canonical_smoke_not_successful")
    if row_count <= 0:
        blockers.append("canonical_smoke_imported_zero_rows")

    manifest_issues = {
        status: count
        for status, count in manifest_health.items()
        if status not in {"ok"} and safe_positive_int(count) > 0
    }
    if manifest_issues:
        # manifest 問題可能是非 demo 資產；先列 warning，避免把 post-MVP repair 誤當成 MVP 閉環未完成。
        warnings.append(f"manifest_health_has_non_ok_entries:{manifest_issues}")

    ready = not blockers
    return {
        "status": "ready_for_mvp_demo" if ready else "needs_mvp_smoke",
        "status_zh_TW": "MVP Demo 閉環可交付" if ready else "MVP Demo 閉環仍需重跑或修復",
        "remaining_percent_estimate": "0% for canonical MVP demo closure" if ready else "0.8% to 1.2%",
        "canonical_smoke": {
            "stage": stage,
            "succeeded": succeeded,
            "table_name": table_name,
            "row_count": row_count,
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def parse_int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_positive_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def latest_table_timestamp(conn: sqlite3.Connection, table: str, column: str) -> str:
    # 這裡只應接收內部表名/欄名；保留動態 SQL guard，避免日後誤傳外部字串。
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
        # Handoff 需要最近的健康訊號，不只 manifest 掃描，所以關鍵字刻意放寬。
        if any(token in haystack for token in ("verify", "verification", "self_check", "repair", "manifest")):
            return event
    return {}


def latest_event_by_name(events: list[dict[str, object]], event_name: str) -> dict[str, object]:
    # events 已按時間排序；倒著找可以拿到最近一次同名事件。
    target = event_name.lower()
    for event in reversed(events):
        if str(event.get("event") or "").lower() == target:
            return event
    return {}


def _gtd_sort_key(item: dict[str, str]) -> tuple[int, str]:
    # 排序把較不穩定的 Skeleton/Planned 放前面，MVP 項目通常是擴充而非立即修補。
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
        # intake 表可能正在被人編輯；handoff 仍要能產出，錯誤留在摘要裡。
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
    # local discovery 是 ignored staging；handoff 只報數量與路徑，不把草稿內容寫進報告。
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
        # 本機草稿 config 只是 staging；壞掉時應在別處回報，不阻斷 handoff。
        return 0


def safe_count_dataset_sources(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(load_dataset_discovery_sources(path))
    except Exception:
        # 本機草稿 config 只是 staging；壞掉時應在別處回報，不阻斷 handoff。
        return 0


def _git_output(*args: str) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        # 雲端或遠端檔案系統曾破壞 Git metadata；回傳診斷字串，不中斷報告。
        return f"{type(exc).__name__}: {exc}"
    return (result.stdout or result.stderr).strip()
