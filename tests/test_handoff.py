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
    mvp_readiness_summary,
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

        self.assertIn("# RuRuKa Asset Launcher Handoff", report)
        self.assertIn("providers:", report)
        self.assertIn("MVP Readiness", report)
        self.assertIn("mvp_readiness_status:", report)
        self.assertIn("remaining_percent_estimate:", report)
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
        self.assertIn("latest_mvp_demo_smoke_event_at:", report)
        self.assertIn("latest_mvp_demo_smoke_stage:", report)
        self.assertIn("Open GTD Focus", report)
        self.assertIn("open_gtd_total:", report)
        self.assertIn("Portal Intake / Local Discovery", report)
        self.assertIn("portal_intake_actionable:", report)
        self.assertIn("local_dataset_sources:", report)
        self.assertIn("py -m unittest discover -s tests", report)
        self.assertIn("--run-mvp-demo-smoke-json", report)

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
        self.assertIn("mvp_readiness", payload)
        self.assertIn("open_gtd_items", payload)
        self.assertIn("recent_logs", payload)
        self.assertIn("verification_summary", encoded)
        self.assertIn("mvp_readiness", encoded)

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

    def test_verification_summary_reports_latest_mvp_demo_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                summary = verification_summary(
                    repo,
                    [
                        {
                            "timestamp": "2026-05-22T11:11:00+00:00",
                            "event": "mvp_demo_smoke_completed",
                            "context": {
                                "stage": "download_import_completed",
                                "succeeded": True,
                                "table_name": "nyc_open_data_socrata_socrata_311_sample",
                                "row_count": 3,
                            },
                        }
                    ],
                )
            finally:
                conn.close()

        self.assertEqual("2026-05-22T11:11:00+00:00", summary["latest_mvp_demo_smoke_event_at"])
        self.assertEqual("download_import_completed", summary["latest_mvp_demo_smoke_stage"])
        self.assertIn("'succeeded': True", summary["latest_mvp_demo_smoke_result"])
        self.assertIn("'row_count': 3", summary["latest_mvp_demo_smoke_result"])
        self.assertEqual("true", summary["latest_mvp_demo_smoke_succeeded"])
        self.assertEqual("nyc_open_data_socrata_socrata_311_sample", summary["latest_mvp_demo_smoke_table_name"])
        self.assertEqual("3", summary["latest_mvp_demo_smoke_row_count"])

    def test_mvp_readiness_marks_successful_canonical_smoke_ready(self) -> None:
        readiness = mvp_readiness_summary(
            {
                "latest_mvp_demo_smoke_event_at": "2026-05-22T11:11:00+00:00",
                "latest_mvp_demo_smoke_stage": "download_import_completed",
                "latest_mvp_demo_smoke_succeeded": "true",
                "latest_mvp_demo_smoke_table_name": "nyc_open_data_socrata_socrata_311_sample",
                "latest_mvp_demo_smoke_row_count": "3",
            },
            {"ok": 1},
        )

        self.assertEqual("ready_for_mvp_demo", readiness["status"])
        self.assertEqual("0% for canonical MVP demo closure", readiness["remaining_percent_estimate"])
        self.assertEqual([], readiness["blockers"])
        self.assertEqual(3, readiness["canonical_smoke"]["row_count"])

    def test_mvp_readiness_keeps_missing_smoke_as_blocker(self) -> None:
        readiness = mvp_readiness_summary({}, {})

        self.assertEqual("needs_mvp_smoke", readiness["status"])
        self.assertIn("no_canonical_mvp_demo_smoke_event", readiness["blockers"])
        self.assertIn("canonical_smoke_imported_zero_rows", readiness["blockers"])


if __name__ == "__main__":
    unittest.main()
