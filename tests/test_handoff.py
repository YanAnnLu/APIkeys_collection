# 這份測試鎖定 handoff report 欄位，避免接力時缺少 Git、manifest 或 GTD 脈絡。
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.handoff import (
    build_handoff_snapshot,
    data_store_handoff_summary,
    handoff_snapshot_to_dict,
    markdown_table_cells,
    parse_open_gtd_items,
    render_handoff_markdown,
    verification_summary,
)
from api_launcher.repository import ApiCatalogRepository


class HandoffTests(unittest.TestCase):
    def test_handoff_report_contains_git_catalog_and_resume_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()

                report = render_handoff_markdown(build_handoff_snapshot(repo))
            finally:
                conn.close()

        self.assertIn("# APIkeys_collection Handoff", report)
        self.assertIn("providers:", report)
        self.assertIn("Data Store Profile", report)
        self.assertIn("test_json_command:", report)
        self.assertIn("Verification Timestamps", report)
        self.assertIn("latest_download_requeue_event_at:", report)
        self.assertIn("latest_download_requeue_outcome:", report)
        self.assertIn("latest_adapter_review_json_event_at:", report)
        self.assertIn("latest_adapter_review_json_output:", report)
        self.assertIn("latest_adapter_plan_resolved_event_at:", report)
        self.assertIn("latest_adapter_plan_resolved_output:", report)
        self.assertIn("latest_download_plan_event_at:", report)
        self.assertIn("latest_download_plan_stage:", report)
        self.assertIn("Open GTD Focus", report)
        self.assertIn("open_gtd_total:", report)
        self.assertIn("Portal Intake / Local Discovery", report)
        self.assertIn("portal_intake_actionable:", report)
        self.assertIn("local_dataset_sources:", report)
        self.assertIn("py -m unittest discover -s tests", report)

    def test_handoff_snapshot_json_payload_is_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()

                payload = handoff_snapshot_to_dict(build_handoff_snapshot(repo))
            finally:
                conn.close()

        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertIn("verification_summary", payload)
        self.assertIn("open_gtd_items", payload)
        self.assertIn("recent_logs", payload)
        self.assertIn("verification_summary", encoded)

    def test_cli_emits_handoff_report_json_without_human_setup_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--init-db",
                        "--seed",
                        "--handoff-report-json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(0, rc)
        self.assertIn("git_status", payload)
        self.assertIn("verification_summary", payload)
        self.assertIn("open_gtd_summary", payload)
        self.assertNotIn("[db]", stdout.getvalue())
        self.assertNotIn("[seed]", stdout.getvalue())

    def test_open_gtd_parser_keeps_code_span_pipes_inside_cells(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "PROJECT_GTD.md"
            path.write_text(
                "\n".join(
                    [
                        "| Area | Status | Current Progress | Next Step |",
                        "| --- | --- | --- | --- |",
                        "| Done area | Done | complete | ignore this |",
                        "| Data store connections | Skeleton | CLI `PROFILE_ID|all` works. | Add HDFS probes. |",
                    ]
                ),
                encoding="utf-8",
            )

            items = parse_open_gtd_items(path)

        self.assertEqual(
            ["Area", "Status", "Current Progress", "Next Step"],
            markdown_table_cells("| Area | Status | Current Progress | Next Step |"),
        )
        self.assertEqual(1, len(items))
        self.assertEqual("Data store connections", items[0]["area"])
        self.assertEqual("Skeleton", items[0]["status"])
        self.assertEqual("Add HDFS probes.", items[0]["next_step"])

    def test_data_store_handoff_summary_has_safe_commands_without_secret_values(self) -> None:
        summary = data_store_handoff_summary()

        self.assertIn("active_profile", summary)
        self.assertIn("--test-data-store", summary["test_command"])
        self.assertIn("--test-data-store-json", summary["test_json_command"])
        self.assertIn("--write-data-store-env-template", summary["env_template_command"])
        self.assertNotIn("PASSWORD=", " ".join(summary.values()))

    def test_verification_summary_reports_latest_adapter_review_json_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                summary = verification_summary(
                    repo,
                    [
                        {
                            "timestamp": "2026-05-22T09:00:00+00:00",
                            "event": "adapter_review_json_written",
                            "context": {
                                "output_path": "state/adapter_review.json",
                                "by_outcome": {"source_resolution_required": 1},
                            },
                        }
                    ],
                )
            finally:
                conn.close()

        self.assertEqual("2026-05-22T09:00:00+00:00", summary["latest_adapter_review_json_event_at"])
        self.assertEqual("state/adapter_review.json", summary["latest_adapter_review_json_output"])
        self.assertIn("source_resolution_required", summary["latest_adapter_review_json_outcomes"])

    def test_verification_summary_reports_latest_adapter_plan_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                summary = verification_summary(
                    repo,
                    [
                        {
                            "timestamp": "2026-05-22T10:00:00+00:00",
                            "event": "adapter_plan_resolved",
                            "context": {
                                "output_path": "state/resolved_plan.json",
                                "direct_entries_added": 2,
                                "resolved_review_entries": 3,
                                "unresolved_review_entries": 1,
                                "warning_count": 0,
                            },
                        }
                    ],
                )
            finally:
                conn.close()

        self.assertEqual("2026-05-22T10:00:00+00:00", summary["latest_adapter_plan_resolved_event_at"])
        self.assertEqual("state/resolved_plan.json", summary["latest_adapter_plan_resolved_output"])
        self.assertIn("'direct_entries_added': 2", summary["latest_adapter_plan_resolved_counts"])
        self.assertIn("'unresolved_review_entries': 1", summary["latest_adapter_plan_resolved_counts"])

    def test_verification_summary_reports_latest_download_plan_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                summary = verification_summary(
                    repo,
                    [
                        {
                            "timestamp": "2026-05-22T10:30:00+00:00",
                            "event": "download_plan_executed",
                            "context": {
                                "input_plan": "state/candidate_plan.resolved.json",
                                "stage": "download_completed",
                                "next_action": "run_adapter_review_or_resolve_adapter_plan_before_downloading",
                                "entry_count": 2,
                                "submitted": 1,
                                "completed": 1,
                                "failed": 0,
                                "skipped": 1,
                                "imported": 0,
                                "import_failed": 0,
                                "skip_summary": {"adapter_required": 1},
                            },
                        }
                    ],
                )
            finally:
                conn.close()

        self.assertEqual("2026-05-22T10:30:00+00:00", summary["latest_download_plan_event_at"])
        self.assertEqual("state/candidate_plan.resolved.json", summary["latest_download_plan_input"])
        self.assertEqual("download_completed", summary["latest_download_plan_stage"])
        self.assertIn("'completed': 1", summary["latest_download_plan_counts"])
        self.assertIn("adapter_required", summary["latest_download_plan_counts"])


if __name__ == "__main__":
    unittest.main()
