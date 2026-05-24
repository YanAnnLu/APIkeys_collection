from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from api_launcher.db import connect_db, init_db
from api_launcher.repository import ApiCatalogRepository
from api_launcher.showcase_download import (
    SHOWCASE_CURATED_DB_NAME,
    SHOWCASE_DOWNLOAD_DIRNAME,
    SHOWCASE_FALLBACK_CSV_URL,
    SHOWCASE_FALLBACK_PROVIDER_ID,
    SHOWCASE_FULL_EXPORT_URL,
    SHOWCASE_RESUMABLE_CSV_NAME,
    apply_socrata_sample_limit,
    build_showcase_fallback_csv_plan,
    build_showcase_resumable_download_plan,
    emit_showcase_progress,
    normalize_showcase_sample_limit,
    seed_showcase_repository,
    showcase_download_flow_percent,
    showcase_download_paths,
    showcase_socrata_rows_json_url,
    sqlite_table_counts,
    socrata_url_with_limit,
)
from api_launcher.downloads.jobs import DownloadProgress, JobStatus


class ShowcaseDownloadCoreTests(unittest.TestCase):
    def test_showcase_download_paths_stay_under_user_chosen_folder(self) -> None:
        # 展示模式不能把成果藏回 repo state；使用者選哪個根目錄，就在該處建立固定展示子資料夾。
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = showcase_download_paths(tmpdir)

        self.assertEqual(Path(tmpdir) / SHOWCASE_DOWNLOAD_DIRNAME, paths.root)
        self.assertEqual(paths.root / "downloads", paths.downloads_root)
        self.assertEqual(paths.root / SHOWCASE_CURATED_DB_NAME, paths.curated_sqlite)

    def test_sqlite_table_counts_ignores_internal_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "curated.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE sample(id INTEGER)")
                conn.executemany("INSERT INTO sample(id) VALUES (?)", [(1,), (2,), (3,)])
                conn.commit()

            self.assertEqual({"sample": 3}, sqlite_table_counts(db_path))

    def test_resumable_showcase_plan_targets_full_csv_without_sql_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = build_showcase_resumable_download_plan(tmpdir)
            payload = json.loads(plan.plan_path.read_text(encoding="utf-8"))

        entry = payload["providers"][0]
        self.assertEqual("showcase_resumable_nyc_311_full_csv", payload["plan_name"])
        self.assertEqual(SHOWCASE_FULL_EXPORT_URL, entry["download_url"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("manual_review_required", entry["import_plan"]["status"])
        self.assertTrue(str(plan.target_path).endswith(str(Path("downloads") / "nyc_open_data_socrata" / SHOWCASE_RESUMABLE_CSV_NAME)))
        self.assertIn("local_folder_only", payload["summary"]["sql_short_circuit"])

    def test_fallback_showcase_plan_is_truthful_public_csv_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = showcase_download_paths(tmpdir)
            payload = build_showcase_fallback_csv_plan(paths, 12)

        entry = payload["providers"][0]
        self.assertEqual(SHOWCASE_FALLBACK_PROVIDER_ID, entry["provider_id"])
        self.assertEqual(SHOWCASE_FALLBACK_CSV_URL, entry["download_url"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(12, entry["dataset_version"]["metadata"]["showcase_sample_limit"])
        self.assertEqual("fallback_planned", payload["summary"]["status"])

    def test_showcase_sample_limit_is_user_controlled_but_bounded(self) -> None:
        self.assertEqual(1, normalize_showcase_sample_limit(0))
        self.assertEqual(100, normalize_showcase_sample_limit(100))
        self.assertEqual(50000, normalize_showcase_sample_limit(999999))

        url = socrata_url_with_limit("https://data.example.test/resource/abcd.json?$limit=25&$select=name", 123)

        self.assertIn("$limit=123", url)
        self.assertIn("%24select=name", url)
        self.assertNotIn("$limit=25", url)

    def test_showcase_socrata_rows_json_url_uses_gui_controlled_length(self) -> None:
        url = showcase_socrata_rows_json_url(321)

        self.assertIn("/api/views/erm2-nwe9/rows.json", url)
        self.assertIn("accessType=DOWNLOAD", url)
        self.assertIn("method=getByIds", url)
        self.assertIn("asHashes=true", url)
        self.assertIn("length=321", url)

    def test_emit_showcase_progress_clamps_percent_and_preserves_context(self) -> None:
        events: list[tuple[float, str, dict[str, object]]] = []

        callback = lambda percent, stage, context: events.append((percent, stage, context))

        emit_showcase_progress(callback, 125, "download", bytes_done=10, bytes_total=20)
        emit_showcase_progress(callback, -5, "prepare_paths")

        self.assertEqual(100.0, events[0][0])
        self.assertEqual("download", events[0][1])
        self.assertEqual(10, events[0][2]["bytes_done"])
        self.assertEqual(0.0, events[1][0])

    def test_fallback_download_flow_percent_never_regresses_below_fallback_notice(self) -> None:
        # 主來源 timeout 後會先顯示 fallback 提示在 36%；備援下載開始時不能倒退到 35%，
        # 否則現場展示者會以為進度條壞掉或下載重新卡住。
        running = DownloadProgress(job_id="fallback", provider_id="fallback", status=JobStatus.RUNNING, bytes_done=0, bytes_total=5_000)
        completed = DownloadProgress(job_id="fallback", provider_id="fallback", status=JobStatus.COMPLETED, bytes_done=5_000, bytes_total=5_000)

        self.assertEqual(35.0, showcase_download_flow_percent(running, fallback_active=False))
        self.assertGreaterEqual(showcase_download_flow_percent(running, fallback_active=True), 37.0)
        self.assertEqual(75.0, showcase_download_flow_percent(completed, fallback_active=True))

    def test_apply_socrata_sample_limit_updates_plan_and_version_metadata(self) -> None:
        plan_payload = {
            "summary": {"status": "planned"},
            "providers": [
                {
                    "download_url": "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=25",
                    "dataset_version": {"download_url": "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=25", "metadata": {}},
                    "download_eligibility": {"status": "direct_download", "direct_url": "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=25"},
                    "adapter_resolution": {"sample_url": "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=25"},
                }
            ],
        }

        updated = apply_socrata_sample_limit(plan_payload, 250)
        entry = updated["providers"][0]

        self.assertIn("rows.json", entry["download_url"])
        self.assertIn("length=250", entry["download_url"])
        self.assertEqual(250, entry["dataset_version"]["metadata"]["showcase_sample_limit"])
        self.assertEqual(entry["download_url"], entry["download_eligibility"]["direct_url"])
        self.assertEqual(entry["download_url"], entry["adapter_resolution"]["sample_url"])
        self.assertEqual(250, updated["summary"]["showcase_sample_limit"])

    def test_seed_showcase_repository_creates_provider_and_dataset_from_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "catalog.db"
            conn = connect_db(db_path)
            try:
                init_db(conn)
                repo = ApiCatalogRepository(conn)
                seed_showcase_repository(
                    repo,
                    {
                        "providers": [
                            {
                                "provider_id": "showcase_provider",
                                "name": "Showcase Provider",
                                "owner": "Showcase Owner",
                                "categories": ["showcase", "demo"],
                                "geographic_scope": "local",
                                "docs_url": "https://example.test/docs",
                                "auth_type": "none",
                                "dataset_uid": "showcase_provider:demo",
                                "dataset_id": "demo",
                                "dataset_title": "Showcase Dataset",
                                "source_format": "json",
                                "download_url": "https://example.test/demo.json",
                                "dataset_version": {"version": "demo-v1", "metadata": {"native_format": "json"}},
                            }
                        ]
                    },
                )
                provider = conn.execute("SELECT provider_id FROM providers WHERE provider_id = 'showcase_provider'").fetchone()
                dataset = conn.execute("SELECT dataset_uid FROM datasets WHERE dataset_uid = 'showcase_provider:demo'").fetchone()
            finally:
                conn.close()

        self.assertIsNotNone(provider)
        self.assertIsNotNone(dataset)


if __name__ == "__main__":
    unittest.main()
