# 這份測試鎖定使用者自備本機檔案的 manifest 與 SQLite 匯入入口，避免手動匯入又退回手工 JSON。
from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.manual_import import (
    DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
    default_local_file_manifest_path,
    write_local_file_manifest,
)
from api_launcher.manifests import read_manifest
from api_launcher.db import connect_db


class ManualImportTests(unittest.TestCase):
    def test_writes_local_file_manifest_with_default_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "Weather Sample.csv"
            csv_path.write_text("station,temp\nTPE,28\n", encoding="utf-8")
            manifest_path = Path(tmpdir) / "weather.manifest.json"

            result = write_local_file_manifest(csv_path, manifest_path)
            manifest = read_manifest(result.manifest_path)
            verification = verify_manifest_file(result.manifest_path)

        self.assertEqual("ok", verification.status)
        self.assertEqual(DEFAULT_MANUAL_LOCAL_PROVIDER_ID, manifest.provider_id)
        self.assertEqual("weather_sample", manifest.dataset_id)
        self.assertTrue(manifest.source_url.startswith("file:"))
        self.assertEqual("csv", manifest.metadata["source_format"])
        self.assertEqual(True, manifest.metadata["manual_import"])
        self.assertIn("--import-csv-manifest", result.next_command)

    def test_rejects_unsupported_manual_file_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload_path = Path(tmpdir) / "notes.txt"
            payload_path.write_text("not importable yet", encoding="utf-8")

            with self.assertRaises(ValueError) as context:
                write_local_file_manifest(payload_path, Path(tmpdir) / "notes.manifest.json")

        self.assertIn("Unsupported manual import format", str(context.exception))

    def test_default_manifest_path_keeps_provider_dataset_version_layers(self) -> None:
        path = default_local_file_manifest_path(
            "Samples/Weather 2026.json.gz",
            manifest_dir="state/manual_imports",
            provider_id="manual_local_files",
            version="draft 1",
        )

        self.assertEqual(Path("state/manual_imports/manual_local_files/weather_2026/draft_1/Weather 2026.json.gz.manifest.json"), path)

    def test_cli_imports_local_csv_and_registers_manual_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "weather.csv"
            csv_path.write_text("station,temp\nTPE,28\nKHH,30\n", encoding="utf-8")
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            manifest_dir = Path(tmpdir) / "manual_manifests"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(launcher_db),
                        "--init-db",
                        "--import-local-file",
                        str(csv_path),
                        "--local-file-manifest-dir",
                        str(manifest_dir),
                        "--import-sqlite-db",
                        str(curated_db),
                        "--import-table",
                        "weather_manual",
                    ]
                )

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT station, temp FROM "weather_manual" ORDER BY station').fetchall()
            with closing(connect_db(launcher_db)) as conn:
                provider = conn.execute(
                    "SELECT provider_id, auth_type FROM providers WHERE provider_id = ?",
                    (DEFAULT_MANUAL_LOCAL_PROVIDER_ID,),
                ).fetchone()
                manifest_count = conn.execute(
                    "SELECT COUNT(*) FROM dataset_asset_manifests WHERE provider_id = ? AND status = 'ok'",
                    (DEFAULT_MANUAL_LOCAL_PROVIDER_ID,),
                ).fetchone()[0]
                table_count = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM provider_installation_assets
                    WHERE asset_kind = 'table' AND asset_role = 'curated' AND asset_name = 'weather_manual'
                    """
                ).fetchone()[0]

        self.assertEqual(0, rc)
        self.assertEqual([("KHH", "30"), ("TPE", "28")], rows)
        self.assertEqual((DEFAULT_MANUAL_LOCAL_PROVIDER_ID, "local_file"), tuple(provider))
        self.assertEqual(1, manifest_count)
        self.assertEqual(1, table_count)
        self.assertIn("[local-import] manifest=", stdout.getvalue())
        self.assertIn("table=weather_manual rows=2", stdout.getvalue())

    def test_cli_writes_local_manifest_and_next_import_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "records.json"
            json_path.write_text('[{"id": 1, "name": "alpha"}]\n', encoding="utf-8")
            manifest_path = Path(tmpdir) / "records.manifest.json"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--init-db",
                        "--write-local-file-manifest",
                        str(manifest_path),
                        "--local-file",
                        str(json_path),
                    ]
                )

            verification = verify_manifest_file(manifest_path)

        self.assertEqual(0, rc)
        self.assertEqual("ok", verification.status)
        self.assertIn("[local-manifest] wrote", stdout.getvalue())
        self.assertIn("--import-json-manifest", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
