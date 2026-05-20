from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from api_launcher.database_repair import (
    manifest_path_from_notes,
    reimport_missing_sqlite_table_asset,
    supported_reimport_source_formats_label,
)
from api_launcher.database_self_check import DatabaseAssetVerifier
from api_launcher.db import connect_db
from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite
from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.repository import ApiCatalogRepository


class DatabaseRepairTests(unittest.TestCase):
    def test_reimport_missing_sqlite_table_asset_from_recorded_csv_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            csv_path = root / "stars.csv"
            csv_path.write_text("name,mag\nSirius,-1.46\nVega,0.03\n", encoding="utf-8")
            manifest_path = write_manifest(
                build_asset_manifest(csv_path, csv_plan_entry()),
                csv_path.with_suffix(".csv.manifest.json"),
            )
            launcher_db = root / "launcher.sqlite"
            curated_db = root / "curated.sqlite"
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                imported = import_csv_manifest_to_sqlite(
                    manifest_path,
                    curated_db,
                    repo,
                    table_name="stars_curated",
                )
                with closing(sqlite3.connect(curated_db)) as curated:
                    curated.execute('DROP TABLE "stars_curated"')
                    curated.commit()
                repo.verify_provider_assets(verifier=DatabaseAssetVerifier(), asset_kinds=("database", "table"))

                repair = reimport_missing_sqlite_table_asset(repo, imported.table_asset_id)
                repo.verify_provider_assets(verifier=DatabaseAssetVerifier(), asset_kinds=("database", "table"))
                asset_status = conn.execute(
                    "SELECT status FROM provider_installation_assets WHERE asset_id = ?",
                    (imported.table_asset_id,),
                ).fetchone()["status"]
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, mag FROM "stars_curated" ORDER BY name').fetchall()

        self.assertEqual("reimport_missing_sqlite_table", repair.action_id)
        self.assertEqual(2, repair.rows_imported)
        self.assertEqual([("Sirius", "-1.46"), ("Vega", "0.03")], rows)
        self.assertEqual("present", asset_status)

    def test_reimport_missing_sqlite_table_accepts_geojson_source_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            geojson_path = root / "stations.geojson"
            geojson_path.write_text(
                """
                {
                  "type": "FeatureCollection",
                  "features": [
                    {
                      "type": "Feature",
                      "properties": {"name": "Harbor"},
                      "geometry": {"type": "Point", "coordinates": [121.5, 25.0]}
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            manifest_path = write_manifest(
                build_asset_manifest(geojson_path, geojson_plan_entry()),
                geojson_path.with_suffix(".geojson.manifest.json"),
            )
            launcher_db = root / "launcher.sqlite"
            curated_db = root / "curated.sqlite"
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                imported = import_json_manifest_to_sqlite(
                    manifest_path,
                    curated_db,
                    repo,
                    table_name="stations_curated",
                )
                with closing(sqlite3.connect(curated_db)) as curated:
                    curated.execute('DROP TABLE "stations_curated"')
                    curated.commit()
                repo.verify_provider_assets(verifier=DatabaseAssetVerifier(), asset_kinds=("database", "table"))

                repair = reimport_missing_sqlite_table_asset(repo, imported.table_asset_id)
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, geometry_json FROM "stations_curated"').fetchall()

        self.assertEqual("reimport_missing_sqlite_table", repair.action_id)
        self.assertEqual(1, repair.rows_imported)
        self.assertEqual("Harbor", rows[0][0])
        self.assertIn('"Point"', rows[0][1])

    def test_reimport_missing_sqlite_table_does_not_replace_existing_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            csv_path = root / "stars.csv"
            csv_path.write_text("name,mag\nSirius,-1.46\n", encoding="utf-8")
            manifest_path = write_manifest(
                build_asset_manifest(csv_path, csv_plan_entry()),
                csv_path.with_suffix(".csv.manifest.json"),
            )
            conn = connect_db(root / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                imported = import_csv_manifest_to_sqlite(
                    manifest_path,
                    root / "curated.sqlite",
                    repo,
                    table_name="stars_curated",
                )
                conn.execute(
                    "UPDATE provider_installation_assets SET status = 'missing' WHERE asset_id = ?",
                    (imported.table_asset_id,),
                )
                conn.commit()

                with self.assertRaisesRegex(ValueError, "already exists"):
                    reimport_missing_sqlite_table_asset(repo, imported.table_asset_id)
            finally:
                conn.close()

    def test_reimport_missing_sqlite_table_requires_recorded_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                asset_id = repo.register_provider_table_asset(
                    "hyg_database",
                    engine="sqlite",
                    database_name="curated.sqlite",
                    table_name="missing_table",
                    source_format="csv",
                    source_uri=str(Path(tmpdir) / "curated.sqlite"),
                    notes="Imported before source manifest tracking existed.",
                )
                conn.execute(
                    "UPDATE provider_installation_assets SET status = 'missing' WHERE asset_id = ?",
                    (asset_id,),
                )
                conn.commit()

                with self.assertRaisesRegex(ValueError, "No source manifest"):
                    reimport_missing_sqlite_table_asset(repo, asset_id)
            finally:
                conn.close()

    def test_reimport_missing_sqlite_table_reports_supported_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            conn = connect_db(root / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                asset_id = repo.register_provider_table_asset(
                    "hyg_database",
                    engine="sqlite",
                    database_name="curated.sqlite",
                    table_name="unsupported_table",
                    source_format="api",
                    source_uri=str(root / "curated.sqlite"),
                    notes=f"manifest={root / 'unsupported.api.manifest.json'} payload={root / 'unsupported.api'}",
                )
                conn.execute(
                    "UPDATE provider_installation_assets SET status = 'missing' WHERE asset_id = ?",
                    (asset_id,),
                )
                conn.commit()

                with self.assertRaisesRegex(ValueError, "Supported formats: .*geojson\\.gz"):
                    reimport_missing_sqlite_table_asset(repo, asset_id)
            finally:
                conn.close()

        self.assertIn("csv.gz", supported_reimport_source_formats_label())
        self.assertIn("geojson.gz", supported_reimport_source_formats_label())

    def test_manifest_path_from_notes_allows_spaces_before_payload_marker(self) -> None:
        self.assertEqual(
            r"K:\data exports\stars.csv.manifest.json",
            manifest_path_from_notes(
                r"Curated table. manifest=K:\data exports\stars.csv.manifest.json payload=K:\data exports\stars.csv"
            ),
        )


def csv_plan_entry() -> dict[str, object]:
    return {
        "provider_id": "hyg_database",
        "dataset_uid": "hyg_sample",
        "dataset_id": "hyg_sample",
        "dataset_version": {"version": "1.0"},
        "download_url": "https://example.test/stars.csv",
        "native_format": "csv",
        "import_plan": {"status": "supported_after_download", "importer": "csv_to_sqlite"},
    }


def geojson_plan_entry() -> dict[str, object]:
    return {
        "provider_id": "hyg_database",
        "dataset_uid": "hyg_geojson_sample",
        "dataset_id": "hyg_geojson_sample",
        "dataset_version": {"version": "1.0"},
        "download_url": "https://example.test/stations.geojson",
        "native_format": "geojson",
        "import_plan": {"status": "supported_after_download", "importer": "json_to_sqlite"},
    }


if __name__ == "__main__":
    unittest.main()
