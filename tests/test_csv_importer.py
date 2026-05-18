from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite, import_verified_csv_manifests_to_sqlite
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

    def test_import_tolerates_non_utf8_csv_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "legacy.csv"
            csv_path.write_bytes("name,notes\nSirius,smart quote \u2019\n".encode("cp1252"))
            manifest_path = write_manifest(build_asset_manifest(csv_path, csv_plan_entry()), csv_path.with_suffix(".csv.manifest.json"))
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()

                result = import_csv_manifest_to_sqlite(manifest_path, curated_db, repo, replace=False, row_limit=10)
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, notes FROM "hyg_sample_1_0"').fetchall()

        self.assertEqual(1, result.rows_imported)
        self.assertEqual("Sirius", rows[0][0])
        self.assertIn("smart quote", rows[0][1])

    def test_batch_imports_only_healthy_csv_registry_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            csv_manifest, bin_manifest, missing_manifest = sample_manifest_set(Path(tmpdir))
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset_asset_manifest(read_manifest_for_test(csv_manifest), csv_manifest, status="ok")
                repo.upsert_dataset_asset_manifest(read_manifest_for_test(bin_manifest), bin_manifest, status="ok")
                repo.upsert_dataset_asset_manifest(read_manifest_for_test(missing_manifest), missing_manifest, status="missing")

                result = import_verified_csv_manifests_to_sqlite(repo, curated_db)
                second = import_verified_csv_manifests_to_sqlite(repo, curated_db)
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, mag FROM "hyg_sample_1_0"').fetchall()

        self.assertEqual([("Sirius", "-1.46")], rows)
        self.assertEqual(3, result.checked)
        self.assertEqual(1, result.imported)
        self.assertEqual(1, result.skipped_non_csv)
        self.assertEqual(1, result.skipped_unhealthy)
        self.assertEqual(0, result.skipped_existing)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, second.imported)
        self.assertEqual(1, second.skipped_existing)

    def test_cli_batch_imports_registry_csv_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            csv_manifest, _bin_manifest, _missing_manifest = sample_manifest_set(Path(tmpdir))
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset_asset_manifest(read_manifest_for_test(csv_manifest), csv_manifest, status="ok")
            finally:
                conn.close()
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(launcher_db),
                        "--import-verified-csv-manifests",
                        "--import-sqlite-db",
                        str(curated_db),
                    ]
                )

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, mag FROM "hyg_sample_1_0"').fetchall()

        self.assertEqual(0, rc)
        self.assertEqual([("Sirius", "-1.46")], rows)
        self.assertIn("[csv-import-batch] checked=1 imported=1 skipped=0", stdout.getvalue())


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


def sample_manifest_set(root: Path) -> tuple[Path, Path, Path]:
    csv_path = root / "stars.csv"
    csv_path.write_text("name,mag\nSirius,-1.46\n", encoding="utf-8")
    csv_manifest = write_manifest(build_asset_manifest(csv_path, csv_plan_entry()), csv_path.with_suffix(".csv.manifest.json"))

    bin_path = root / "sample.bin"
    bin_path.write_bytes(b"binary")
    bin_manifest = write_manifest(build_asset_manifest(bin_path, csv_plan_entry()), bin_path.with_suffix(".bin.manifest.json"))

    missing_path = root / "missing.csv"
    missing_path.write_text("name,mag\nVega,0.03\n", encoding="utf-8")
    missing_manifest = write_manifest(build_asset_manifest(missing_path, csv_plan_entry()), missing_path.with_suffix(".csv.manifest.json"))
    return csv_manifest, bin_manifest, missing_manifest


def read_manifest_for_test(path: Path):
    from api_launcher.manifests import read_manifest

    return read_manifest(path)


if __name__ == "__main__":
    unittest.main()
