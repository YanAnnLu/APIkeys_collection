from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from api_launcher.db import connect_db
from api_launcher.ingestion_pipeline import (
    DOWNLOAD_BLOCKED_NEXT_ACTION,
    DownloadImportPipelineOptions,
    render_download_import_cli_lines,
    run_existing_download_import_slice,
    run_download_import_slice,
)
from api_launcher.mvp_demo import write_mvp_demo_flow
from api_launcher.repository import ApiCatalogRepository


class IngestionPipelineTests(unittest.TestCase):
    def test_download_import_slice_runs_offline_fixture_to_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            flow = write_mvp_demo_flow(Path(tmpdir) / "flow.json")
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                run = run_download_import_slice(
                    _read_json(flow.offline_plan_path),
                    repo,
                    DownloadImportPipelineOptions(
                        import_supported_results=True,
                        import_sqlite_path=flow.import_sqlite_path,
                        import_existing_table_policy="rename",
                    ),
                )
            finally:
                conn.close()

            sqlite_conn = sqlite3.connect(flow.import_sqlite_path)
            try:
                row_count = sqlite_conn.execute(
                    "SELECT COUNT(*) FROM nyc_open_data_socrata_socrata_311_sample"
                ).fetchone()[0]
            finally:
                sqlite_conn.close()

        self.assertEqual("download_import_completed", run.stage)
        self.assertTrue(run.succeeded)
        self.assertEqual(1, run.result.completed)
        self.assertEqual(1, run.result.imported)
        self.assertEqual(3, row_count)

    def test_download_import_slice_guides_adapter_only_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                run = run_download_import_slice(adapter_only_plan(), repo)
            finally:
                conn.close()

        lines = render_download_import_cli_lines(run)
        self.assertEqual("blocked_before_download", run.stage)
        self.assertTrue(run.blocked)
        self.assertEqual(DOWNLOAD_BLOCKED_NEXT_ACTION, run.next_action)
        self.assertIn("[download-plan] skip_summary adapter_required=1", lines)
        self.assertIn(f"[download-plan] next_action={DOWNLOAD_BLOCKED_NEXT_ACTION}", lines)

    def test_download_import_slice_keeps_next_action_for_partial_adapter_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            flow = write_mvp_demo_flow(Path(tmpdir) / "flow.json")
            plan = _read_json(flow.offline_plan_path)
            plan["providers"].extend(adapter_only_plan()["providers"])
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                run = run_download_import_slice(plan, repo)
            finally:
                conn.close()

        lines = render_download_import_cli_lines(run)
        self.assertEqual("download_completed", run.stage)
        self.assertEqual(1, run.result.completed)
        self.assertEqual(1, run.result.skipped)
        self.assertEqual(DOWNLOAD_BLOCKED_NEXT_ACTION, run.next_action)
        self.assertIn(f"[download-plan] next_action={DOWNLOAD_BLOCKED_NEXT_ACTION}", lines)

    def test_existing_download_import_slice_reuses_manifest_without_redownloading(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            flow = write_mvp_demo_flow(Path(tmpdir) / "flow.json")
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                download_run = run_download_import_slice(_read_json(flow.offline_plan_path), repo)
                import_run = run_existing_download_import_slice(
                    _read_json(flow.offline_plan_path),
                    repo,
                    DownloadImportPipelineOptions(
                        import_supported_results=True,
                        import_sqlite_path=flow.import_sqlite_path,
                        import_existing_table_policy="rename",
                    ),
                )
                import_again = run_existing_download_import_slice(
                    _read_json(flow.offline_plan_path),
                    repo,
                    DownloadImportPipelineOptions(
                        import_supported_results=True,
                        import_sqlite_path=flow.import_sqlite_path,
                        import_existing_table_policy="rename",
                    ),
                )
            finally:
                conn.close()

            sqlite_conn = sqlite3.connect(flow.import_sqlite_path)
            try:
                row_count = sqlite_conn.execute(
                    "SELECT COUNT(*) FROM nyc_open_data_socrata_socrata_311_sample"
                ).fetchone()[0]
                renamed_row_count = sqlite_conn.execute(
                    "SELECT COUNT(*) FROM nyc_open_data_socrata_socrata_311_sample_2"
                ).fetchone()[0]
            finally:
                sqlite_conn.close()

        self.assertEqual("download_completed", download_run.stage)
        self.assertEqual("download_import_completed", import_run.stage)
        self.assertEqual(1, import_run.result.imported)
        self.assertEqual("imported", import_run.item_statuses[0].status)
        self.assertEqual("nyc_open_data_socrata_socrata_311_sample_2", import_again.item_statuses[0].detail)
        self.assertEqual(3, row_count)
        self.assertEqual(3, renamed_row_count)


def adapter_only_plan() -> dict[str, object]:
    return {
        "providers": [
            {
                "provider_id": "metadata_source",
                "dataset_id": "landing_page_only",
                "download_eligibility": {"status": "adapter_required"},
                "adapter_review": {
                    "required_action": "resolve_source_to_direct_download_entries",
                    "source_url": "https://example.test/catalog",
                },
            }
        ]
    }


def _read_json(path: Path) -> dict[str, object]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
