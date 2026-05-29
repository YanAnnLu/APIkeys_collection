from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from api_launcher.db import utc_now_iso
from api_launcher.handoff import crawler_handler_smoke_handoff_summary, parse_open_gtd_items
from api_launcher.paths import project_path


REPO_SLUG = "Kagamihara-Ruruka/APIkeys_collection"
DEFAULT_REPORT_PATH = Path("state/heartbeat/heartbeat.md")
DEFAULT_PLAN_PATH = Path("state/heartbeat/heartbeat_plan.json")
DEFAULT_AGENT_PROMPT_PATH = Path("state/heartbeat/agent_prompt.md")


@dataclass(frozen=True)
class CommandResult:
    # heartbeat 需要保留 command stdout/stderr，讓自動 agent 判斷是否能安全續跑。
    ok: bool
    stdout: str
    stderr: str
    returncode: int

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
        }


def build_heartbeat_payload(
    *,
    gtd_path: str | Path = "docs/PROJECT_GTD.md",
    handoff_path: str | Path = "docs/AGENT_HANDOFF.zh-TW.md",
    include_ci: bool = True,
) -> dict[str, object]:
    # heartbeat 只產生報告、JSON plan 與 agent prompt；不直接修改 repo 或執行開發工作。
    gtd_file = project_path(gtd_path)
    handoff_file = project_path(handoff_path)
    handoff_text = read_optional_text(handoff_file)
    gtd_text = read_optional_text(gtd_file)
    git_status = run_command(["git", "status", "--short", "--branch"])
    git_head = run_command(["git", "log", "-1", "--oneline"])
    open_items = parse_open_gtd_items(gtd_file)
    repo_state = repo_state_from_status(git_status.stdout)
    latest_ci = latest_github_actions_run() if include_ci else {"status": "not_checked", "reason": "CI check disabled"}
    plan = select_next_heartbeat_task(open_items, repo_state=repo_state, latest_ci=latest_ci)
    crawler_contract = crawler_handler_smoke_handoff_summary()
    return {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "heartbeat_policy": {
            "interval_minutes": 45,
            "max_work_minutes": 30,
            "quality_rule": "quality_first_no_forced_rushed_checkpoint",
            "automation_stage": "report_plan_and_agent_prompt",
        },
        "inputs": {
            "handoff_path": str(handoff_file),
            "handoff_exists": handoff_file.exists(),
            "handoff_bytes": len(handoff_text.encode("utf-8")) if handoff_text else 0,
            "gtd_path": str(gtd_file),
            "gtd_exists": gtd_file.exists(),
            "gtd_bytes": len(gtd_text.encode("utf-8")) if gtd_text else 0,
        },
        "git": {
            "status": git_status.as_dict(),
            "head": git_head.as_dict(),
            "repo_state": repo_state,
        },
        "ci": latest_ci,
        "crawler_handler_smoke_summary": crawler_contract,
        "open_gtd_count": len(open_items),
        "recommended_plan": plan,
        "top_gtd_candidates": plan.get("candidate_preview", []),
        "safety_rules": safety_rules(),
        "completion_rules": completion_rules(),
        "stop_rules": stop_rules(),
    }


def render_heartbeat_report(payload: dict[str, object]) -> str:
    # 報告面向人類閱讀，保留決策、Git、CI 與建議 checkpoint 的最短摘要。
    plan = payload.get("recommended_plan") if isinstance(payload.get("recommended_plan"), dict) else {}
    repo = payload.get("git") if isinstance(payload.get("git"), dict) else {}
    repo_state = repo.get("repo_state") if isinstance(repo.get("repo_state"), dict) else {}
    ci = payload.get("ci") if isinstance(payload.get("ci"), dict) else {}
    crawler_contract = (
        payload.get("crawler_handler_smoke_summary")
        if isinstance(payload.get("crawler_handler_smoke_summary"), dict)
        else {}
    )
    lines = [
        "# RuRuKa Asset Launcher Heartbeat Report",
        "",
        f"Generated at: {payload.get('generated_at', '')}",
        "",
        "## Decision",
        "",
        f"- safe_to_progress: {plan.get('safe_to_progress', False)}",
        f"- recommended_action: {plan.get('recommended_action', '')}",
        f"- priority_lane: {plan.get('priority_lane', '')}",
        f"- reason: {plan.get('reason', '')}",
        f"- stop_required: {plan.get('stop_required', False)}",
        "",
        "## Repository",
        "",
        f"- head: {short_text((repo.get('head') or {}).get('stdout', '') if isinstance(repo.get('head'), dict) else '')}",
        f"- tracked_changes: {repo_state.get('tracked_change_count', 0)}",
        f"- untracked_files: {repo_state.get('untracked_count', 0)}",
        f"- branch_line: {repo_state.get('branch_line', '') or 'unknown'}",
        "",
        "## CI",
        "",
        f"- status: {ci.get('status', '')}",
        f"- conclusion: {ci.get('conclusion', '')}",
        f"- title: {ci.get('displayTitle', ci.get('title', ''))}",
        f"- run_id: {ci.get('databaseId', ci.get('id', ''))}",
        "",
        "## Crawler Handler Contract Smoke",
        "",
        f"- command: {crawler_contract.get('command', '')}",
        f"- supported_source_type_count: {crawler_contract.get('supported_source_type_count', 0)}",
        f"- empty_case_zero_candidates: {crawler_contract.get('empty_case_zero_candidates', 0)}",
        f"- candidate_case_pass_sources: {crawler_contract.get('candidate_case_pass_sources', 0)}",
        f"- next_action: {crawler_contract.get('next_action', '')}",
        "",
        "## Suggested Checkpoint",
        "",
        f"- area: {plan.get('area', '')}",
        f"- status: {plan.get('status', '')}",
        f"- next_step: {plan.get('next_step', '')}",
        "",
        "## Verification Commands",
        "",
        "```powershell",
        *[str(command) for command in plan.get("verification_commands", [])],
        "```",
        "",
        "## Stop Conditions",
        "",
    ]
    stop_conditions = plan.get("stop_conditions") if isinstance(plan.get("stop_conditions"), list) else []
    if not stop_conditions:
        lines.append("- none")
    else:
        lines.extend(f"- {condition}" for condition in stop_conditions)
    lines.extend(
        [
            "",
            "## Candidate Preview",
            "",
        ]
    )
    candidates = payload.get("top_gtd_candidates") if isinstance(payload.get("top_gtd_candidates"), list) else []
    if not candidates:
        lines.append("- no open GTD candidates found")
    else:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            lines.append(
                f"- {candidate.get('area', '')} [{candidate.get('status', '')}] "
                f"lane={candidate.get('priority_lane', '')}: {candidate.get('next_step', '')}"
            )
    lines.append("")
    return "\n".join(lines)


def write_heartbeat_report(payload: dict[str, object], path: str | Path) -> Path:
    output_path = project_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_heartbeat_report(payload), encoding="utf-8")
    return output_path


def write_heartbeat_json(payload: dict[str, object], path: str | Path) -> Path:
    output_path = project_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def render_heartbeat_agent_prompt(payload: dict[str, object]) -> str:
    # prompt 必須自足，因為外部 agent 可能沒有目前聊天上下文。
    plan = payload.get("recommended_plan") if isinstance(payload.get("recommended_plan"), dict) else {}
    safety = payload.get("safety_rules") if isinstance(payload.get("safety_rules"), list) else safety_rules()
    completion = payload.get("completion_rules") if isinstance(payload.get("completion_rules"), list) else completion_rules()
    stop = payload.get("stop_rules") if isinstance(payload.get("stop_rules"), list) else stop_rules()
    commands = plan.get("verification_commands") if isinstance(plan.get("verification_commands"), list) else default_verification_commands()
    crawler_contract = (
        payload.get("crawler_handler_smoke_summary")
        if isinstance(payload.get("crawler_handler_smoke_summary"), dict)
        else {}
    )
    lines = [
        "# RuRuKa Asset Launcher Heartbeat Agent Prompt",
        "",
        "你是接手 RuRuKa Asset Launcher（內部相容名稱：APIkeys_collection）的自動 heartbeat agent。請不要依賴聊天記憶，必須以 repo 內文件與目前工作區狀態為準。",
        "",
        "## Mandatory Startup",
        "",
        "1. Read `docs/AGENT_HANDOFF.zh-TW.md`.",
        "2. Read `docs/PROJECT_GTD.md`.",
        "3. Run `git status --short --branch`.",
        "4. Check latest commit and latest CI status.",
        "5. Preserve user/other-agent changes; do not overwrite unexpected files.",
        "6. Continue unfinished work only if it is clearly safe.",
        "",
        "## Current Heartbeat Decision",
        "",
        f"- safe_to_progress: {plan.get('safe_to_progress', False)}",
        f"- recommended_action: {plan.get('recommended_action', '')}",
        f"- priority_lane: {plan.get('priority_lane', '')}",
        f"- area: {plan.get('area', '')}",
        f"- status: {plan.get('status', '')}",
        f"- next_step: {plan.get('next_step', '')}",
        f"- reason: {plan.get('reason', '')}",
        "",
        "## Crawler Handler Contract Smoke",
        "",
        f"- command: {crawler_contract.get('command', '')}",
        f"- supported_source_type_count: {crawler_contract.get('supported_source_type_count', 0)}",
        f"- empty_case_zero_candidates: {crawler_contract.get('empty_case_zero_candidates', 0)}",
        f"- candidate_case_pass_sources: {crawler_contract.get('candidate_case_pass_sources', 0)}",
        f"- next_action: {crawler_contract.get('next_action', '')}",
        "",
        "## Safety Rules",
        "",
    ]
    lines.extend(f"- {rule}" for rule in safety)
    lines.extend(["", "## Completion Rules", ""])
    lines.extend(f"- {rule}" for rule in completion)
    lines.extend(["", "## Stop Rules", ""])
    lines.extend(f"- {rule}" for rule in stop)
    lines.extend(
        [
            "",
            "## Verification Commands",
            "",
            "```powershell",
        ]
    )
    lines.extend(str(command) for command in commands)
    lines.extend(
        [
            "```",
            "",
            "## Required Final Report",
            "",
            "回報 repo 狀態、已完成內容、測試結果、未完成風險與建議下一步。若有 commit/push，必須附上 commit hash 與 GitHub Actions run 結果。",
            "",
        ]
    )
    return "\n".join(lines)


def write_heartbeat_agent_prompt(payload: dict[str, object], path: str | Path) -> Path:
    output_path = project_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_heartbeat_agent_prompt(payload), encoding="utf-8")
    return output_path


def repo_state_from_status(status_text: str) -> dict[str, object]:
    lines = [line for line in status_text.splitlines() if line.strip()]
    branch_line = lines[0] if lines and lines[0].startswith("##") else ""
    change_lines = [line for line in lines if not line.startswith("##")]
    untracked = [line[3:] if line.startswith("?? ") else line for line in change_lines if line.startswith("??")]
    tracked = [line for line in change_lines if not line.startswith("??")]
    return {
        "branch_line": branch_line,
        "tracked_change_count": len(tracked),
        "untracked_count": len(untracked),
        "tracked_changes": tracked,
        "untracked_files": untracked,
        "clean_tracked": not tracked,
    }


def select_next_heartbeat_task(
    open_items: list[dict[str, str]],
    *,
    repo_state: dict[str, object],
    latest_ci: dict[str, object],
) -> dict[str, object]:
    stop_conditions: list[str] = []
    if not repo_state.get("clean_tracked", False):
        stop_conditions.append("tracked_worktree_changes_present")
    ci_status = str(latest_ci.get("status") or "")
    ci_conclusion = str(latest_ci.get("conclusion") or "")
    if ci_status and ci_status not in {"completed", "not_checked"}:
        stop_conditions.append(f"ci_not_completed:{ci_status}")
    if ci_conclusion and ci_conclusion not in {"success", "skipped"}:
        stop_conditions.append(f"ci_not_success:{ci_conclusion}")

    if stop_conditions:
        return {
            "safe_to_progress": False,
            "stop_required": True,
            "recommended_action": "stop_and_report",
            "priority_lane": "safety",
            "reason": "Heartbeat found state that should be resolved before autonomous progress.",
            "stop_conditions": stop_conditions,
            "verification_commands": default_verification_commands(),
            "candidate_preview": candidate_preview(open_items),
        }

    candidates = sorted((candidate_for_item(item) for item in open_items), key=lambda item: item["sort_key"])
    selected = next((candidate for candidate in candidates if not candidate.get("deferred", False)), None)
    if selected is None:
        return {
            "safe_to_progress": False,
            "stop_required": True,
            "recommended_action": "stop_and_report",
            "priority_lane": "none",
            "reason": "No suitable open MVP task was found in PROJECT_GTD.md.",
            "stop_conditions": ["no_suitable_open_gtd_task"],
            "verification_commands": default_verification_commands(),
            "candidate_preview": serialize_candidates(candidates),
        }
    selected_payload = serialize_candidate(selected)
    selected_payload.update(
        {
            "safe_to_progress": True,
            "stop_required": False,
            "recommended_action": "implement_bounded_slice",
            "reason": "Tracked worktree is clean and latest CI is acceptable; choose the highest-priority MVP lane.",
            "stop_conditions": [],
            "verification_commands": default_verification_commands(),
            "candidate_preview": serialize_candidates(candidates),
        }
    )
    return selected_payload


def candidate_for_item(item: dict[str, str]) -> dict[str, object]:
    area = item.get("area", "")
    status = item.get("status", "")
    next_step = item.get("next_step", "")
    haystack = f"{area} {status} {next_step}".lower()
    lane, lane_rank = classify_priority_lane(haystack)
    status_rank = {"in progress": 0, "skeleton": 1, "mvp": 2, "planned": 3}.get(status.strip().lower(), 5)
    deferred = is_deferred_roadmap_lane(haystack)
    return {
        "area": area,
        "status": status,
        "next_step": next_step,
        "priority_lane": lane,
        "deferred": deferred,
        "risk_level": "medium" if status.strip().lower() in {"in progress", "skeleton"} else "low",
        "sort_key": (200 if deferred else lane_rank, status_rank, area),
    }


def classify_priority_lane(text: str) -> tuple[str, int]:
    lanes = [
        ("ci_or_tests", 0, ("ci failure", "test failure", "tests", "failing")),
        ("repair_observability", 10, ("repair", "manifest", "observability", "event", "log", "self-check", "retry")),
        ("adapter_resolver", 20, ("adapter", "resolver", "resolve", "review", "doi", "ncei", "cmr", "datacite")),
        ("crawler_source_cleanup", 30, ("crawler", "discovery source", "source type", "candidate", "portal")),
        ("ui_backend_connection", 40, ("ui", "tk", "launcher", "panel", "button", "guided")),
        ("docs_handoff_sync", 50, ("docs", "documentation", "handoff", "guide", "architecture")),
    ]
    for lane, rank, keywords in lanes:
        if any(keyword_matches(text, keyword) for keyword in keywords):
            return lane, rank
    return "general_mvp", 90


def keyword_matches(text: str, keyword: str) -> bool:
    if any(separator in keyword for separator in (" ", "-", "_", "/")):
        return keyword in text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def is_deferred_roadmap_lane(text: str) -> bool:
    roadmap_terms = ("qt", "oauth", "hadoop", "k8s", "p2p", "mobile", "render studio")
    return any(term in text for term in roadmap_terms) and not any(term in text for term in ("mvp", "bounded", "guarded"))


def candidate_preview(open_items: list[dict[str, str]], limit: int = 8) -> list[dict[str, object]]:
    return serialize_candidates([candidate_for_item(item) for item in open_items[:limit]], limit=limit)


def serialize_candidate(candidate: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in candidate.items() if key != "sort_key"}


def serialize_candidates(candidates: list[dict[str, object]], limit: int = 8) -> list[dict[str, object]]:
    return [serialize_candidate(candidate) for candidate in candidates[:limit]]


def latest_github_actions_run() -> dict[str, object]:
    result = run_command(
        [
            "gh",
            "run",
            "list",
            "--repo",
            REPO_SLUG,
            "--limit",
            "1",
            "--json",
            "databaseId,displayTitle,status,conclusion,headSha,createdAt",
        ],
        timeout=30,
    )
    if not result.ok:
        return {
            "status": "unknown",
            "conclusion": "",
            "reason": "gh_run_list_failed",
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    try:
        runs = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "unknown",
            "conclusion": "",
            "reason": f"gh_json_decode_failed:{exc}",
        }
    if not runs:
        return {"status": "unknown", "conclusion": "", "reason": "no_runs_found"}
    return dict(runs[0])


def run_command(args: list[str], *, timeout: int = 15) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            cwd=project_path("."),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return CommandResult(False, "", f"{type(exc).__name__}: {exc}", 1)
    return CommandResult(completed.returncode == 0, completed.stdout.strip(), completed.stderr.strip(), completed.returncode)


def default_verification_commands() -> list[str]:
    return [
        "$env:PYTHONDONTWRITEBYTECODE='1'; py -B -m unittest TARGETED_TESTS -v",
        "$env:PYTHONDONTWRITEBYTECODE='1'; py -B -m unittest discover -s tests",
        "$env:PYTHONDONTWRITEBYTECODE='1'; py -B -c \"import py_compile; [py_compile.compile(path, doraise=True) for path in ['APIkeys_collection.py','APIkeys_collection_ui.py','api_launcher/core.py','api_launcher/cli_flags.py','api_launcher/heartbeat.py']]\"",
        "git diff --check",
        "git push origin BRANCH_OR_MAIN",
        "gh run watch RUN_ID --repo Kagamihara-Ruruka/APIkeys_collection --exit-status",
    ]


def safety_rules() -> list[str]:
    return [
        "Do not run destructive DB/file operations.",
        "Do not read or write secrets, API keys, tokens, cookies, or private config.",
        "Do not install packages into base/system Python.",
        "Do not overwrite user or other-agent changes.",
        "Do not directly merge unverified work.",
    ]


def completion_rules() -> list[str]:
    return [
        "Run targeted tests for code changes.",
        "Run full unittest when reasonable.",
        "Run py_compile and git diff --check.",
        "Use a commit message that describes one bounded slice.",
        "After push, watch GitHub Actions to completion.",
        "Update AGENT_HANDOFF and PROJECT_GTD when behavior changes.",
    ]


def stop_rules() -> list[str]:
    return [
        "Requirement is unclear or needs user decision.",
        "Credentials, API keys, paid services, or destructive operations are required.",
        "Tests or CI fail and there is not enough time to fix safely.",
        "There is not enough remaining time for a safe checkpoint.",
    ]


def short_text(value: object, limit: int = 240) -> str:
    text = str(value or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def read_optional_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
