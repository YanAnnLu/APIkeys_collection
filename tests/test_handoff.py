# 這份測試鎖定 handoff report 欄位，避免接力時缺少 Git、manifest 或 GTD 脈絡。
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.db import connect_db
from api_launcher.handoff import (
    build_handoff_snapshot,
    data_store_handoff_summary,
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
        self.assertIn("Open GTD Focus", report)
        self.assertIn("open_gtd_total:", report)
        self.assertIn("Portal Intake / Local Discovery", report)
        self.assertIn("portal_intake_actionable:", report)
        self.assertIn("local_dataset_sources:", report)
        self.assertIn("py -m unittest discover -s tests", report)

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


if __name__ == "__main__":
    unittest.main()
