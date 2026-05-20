from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.heartbeat import (
    build_heartbeat_payload,
    classify_priority_lane,
    render_heartbeat_agent_prompt,
    render_heartbeat_report,
    repo_state_from_status,
    select_next_heartbeat_task,
)


class HeartbeatTests(unittest.TestCase):
    def test_repo_state_separates_tracked_and_untracked_changes(self) -> None:
        state = repo_state_from_status("## main...origin/main\n M api_launcher/core.py\n?? scratch.py\n")

        self.assertFalse(state["clean_tracked"])
        self.assertEqual(1, state["tracked_change_count"])
        self.assertEqual(1, state["untracked_count"])
        self.assertEqual(["scratch.py"], state["untracked_files"])

    def test_planner_stops_when_tracked_changes_exist(self) -> None:
        plan = select_next_heartbeat_task(
            [
                {
                    "area": "Download repair scanner",
                    "status": "MVP",
                    "next_step": "Expand repair suggestions to adapter-specific datasets.",
                }
            ],
            repo_state=repo_state_from_status("## main...origin/main\n M api_launcher/core.py\n"),
            latest_ci={"status": "completed", "conclusion": "success"},
        )

        self.assertFalse(plan["safe_to_progress"])
        self.assertTrue(plan["stop_required"])
        self.assertIn("tracked_worktree_changes_present", plan["stop_conditions"])

    def test_planner_prefers_repair_observability_lane(self) -> None:
        plan = select_next_heartbeat_task(
            [
                {
                    "area": "Documentation",
                    "status": "In progress",
                    "next_step": "Keep updating docs after each functional change.",
                },
                {
                    "area": "Download repair scanner",
                    "status": "MVP",
                    "next_step": "Expand repair suggestions to adapter-specific datasets.",
                },
            ],
            repo_state=repo_state_from_status("## main...origin/main\n?? scratch.py\n"),
            latest_ci={"status": "completed", "conclusion": "success"},
        )

        self.assertTrue(plan["safe_to_progress"])
        self.assertEqual("repair_observability", plan["priority_lane"])
        self.assertEqual("Download repair scanner", plan["area"])

    def test_clean_planner_payload_is_json_serializable(self) -> None:
        plan = select_next_heartbeat_task(
            [
                {
                    "area": "Download repair scanner",
                    "status": "MVP",
                    "next_step": "Expand repair suggestions.",
                }
            ],
            repo_state=repo_state_from_status("## main...origin/main\n"),
            latest_ci={"status": "completed", "conclusion": "success"},
        )

        self.assertTrue(plan["safe_to_progress"])
        json.dumps(plan)
        self.assertNotIn("sort_key", plan)
        self.assertNotIn("sort_key", plan["candidate_preview"][0])

    def test_catalog_text_does_not_match_log_lane(self) -> None:
        lane, _rank = classify_priority_lane("source catalog planning")

        self.assertNotEqual("repair_observability", lane)

    def test_heartbeat_report_contains_decision_and_commands(self) -> None:
        payload = {
            "generated_at": "2026-05-20T00:00:00+00:00",
            "recommended_plan": {
                "safe_to_progress": True,
                "recommended_action": "implement_bounded_slice",
                "priority_lane": "repair_observability",
                "reason": "ok",
                "stop_required": False,
                "area": "Download repair scanner",
                "status": "MVP",
                "next_step": "Expand suggestions.",
                "verification_commands": ["py -B -m unittest tests.test_heartbeat -v"],
                "stop_conditions": [],
            },
            "git": {
                "head": {"stdout": "abc123 test"},
                "repo_state": {
                    "tracked_change_count": 0,
                    "untracked_count": 1,
                    "branch_line": "## main...origin/main",
                },
            },
            "ci": {"status": "completed", "conclusion": "success", "displayTitle": "CI", "databaseId": 1},
            "top_gtd_candidates": [],
        }

        report = render_heartbeat_report(payload)

        self.assertIn("# APIkeys_collection Heartbeat Report", report)
        self.assertIn("safe_to_progress: True", report)
        self.assertIn("py -B -m unittest tests.test_heartbeat -v", report)

    def test_heartbeat_agent_prompt_contains_bounded_task(self) -> None:
        payload = {
            "recommended_plan": {
                "safe_to_progress": True,
                "recommended_action": "implement_bounded_slice",
                "priority_lane": "repair_observability",
                "area": "Download repair scanner",
                "status": "MVP",
                "next_step": "Expand suggestions.",
                "reason": "ok",
                "verification_commands": ["py -B -m unittest tests.test_heartbeat -v"],
            },
            "safety_rules": ["Do not run destructive DB/file operations."],
            "completion_rules": ["Run targeted tests for code changes."],
            "stop_rules": ["Requirement is unclear."],
        }

        prompt = render_heartbeat_agent_prompt(payload)

        self.assertIn("APIkeys_collection Heartbeat Agent Prompt", prompt)
        self.assertIn("Download repair scanner", prompt)
        self.assertIn("Do not run destructive DB/file operations.", prompt)
        self.assertIn("py -B -m unittest tests.test_heartbeat -v", prompt)

    def test_cli_heartbeat_plan_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "heartbeat.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["--db", str(db_path), "--heartbeat-plan-json", "--heartbeat-skip-ci"])

        self.assertEqual(0, rc)
        payload = json.loads(output.getvalue())
        self.assertEqual(1, payload["schema_version"])
        self.assertIn("recommended_plan", payload)

    def test_cli_writes_heartbeat_agent_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "heartbeat.sqlite"
            prompt_path = root / "agent_prompt.md"
            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--heartbeat-agent-prompt",
                    str(prompt_path),
                    "--heartbeat-skip-ci",
                ]
            )

            self.assertEqual(0, rc)
            self.assertTrue(prompt_path.exists())
            self.assertIn("Heartbeat Agent Prompt", prompt_path.read_text(encoding="utf-8"))

    def test_build_payload_can_skip_ci_for_offline_reports(self) -> None:
        payload = build_heartbeat_payload(include_ci=False)

        self.assertEqual("not_checked", payload["ci"]["status"])
        self.assertIn("recommended_plan", payload)


if __name__ == "__main__":
    unittest.main()
