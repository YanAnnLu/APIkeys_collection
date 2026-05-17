from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.csv_importer import import_csv_manifest_to_sqlite
from api_launcher.db import connect_db
from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.repository import ApiCatalogRepository


class CsvImporterTests(unittest.TestCase):
    def test_import_verified_csv_manifest_to_sqlite_table_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "stars.csv"
            csv_path.write_text("Star ID,Magnitude,Star ID\nSirius,-1.46,alpha\nVega,0.03,beta\n", encoding="utf-8")
            manifest_path = write_manifest(build_asset_manifest(csv_path, csv_plan_entry()), csv_path.with_suffix(".csv.manifest.json"))
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()

                result = import_csv_manifest_to_sqlite(manifest_path, curated_db, repo, replace=False)
                assets = repo.managed_asset_records("hyg_database")
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute(
                    'SELECT star_id, magnitude, star_id_2 FROM "hyg_sample_1_0" ORDER BY star_id'
                ).fetchall()

        self.assertEqual(2, result.rows_imported)
        self.assertEqual(("star_id", "magnitude", "star_id_2"), result.columns)
        self.assertEqual("hyg_sample_1_0", result.table_name)
        self.assertEqual([("Sirius", "-1.46", "alpha"), ("Vega", "0.03", "beta")], rows)
        table_assets = [asset for asset in assets if asset.asset_kind == "table"]
        self.assertEqual(1, len(table_assets))
        self.assertEqual("curated", table_assets[0].asset_role)
        self.assertEqual("csv", table_assets[0].source_format)
        self.assertEqual(str(curated_db), table_assets[0].source_uri)
        self.assertEqual(result.schema_fingerprint, table_assets[0].schema_fingerprint)

    def test_cli_imports_csv_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "stars.csv"
            csv_path.write_text("name,mag\nSirius,-1.46\n", encoding="utf-8")
            manifest_path = write_manifest(build_asset_manifest(csv_path, csv_plan_entry()), csv_path.with_suffix(".csv.manifest.json"))
            curated_db = Path(tmpdir) / "curated.sqlite"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--init-db",
                        "--seed",
                        "--import-csv-manifest",
                        str(manifest_path),
                        "--import-sqlite-db",
                        str(curated_db),
                        "--import-table",
                        "stars_curated",
                    ]
                )

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, mag FROM "stars_curated"').fetchall()

        self.assertEqual(0, rc)
        self.assertEqual([("Sirius", "-1.46")], rows)
        self.assertIn("[csv-import] provider=hyg_database table=stars_curated rows=1 columns=2", stdout.getvalue())


def csv_plan_entry() -> dict[str, object]:
    return {
        "provider_id": "hyg_database",
        "download_url": "https://example.test/stars.csv",
        "dataset_version": {
            "dataset_uid": "ds_test_hyg",
            "dataset_id": "hyg_sample",
            "version": "1.0",
            "download_url": "https://example.test/stars.csv",
        },
    }


if __name__ == "__main__":
    unittest.main()
