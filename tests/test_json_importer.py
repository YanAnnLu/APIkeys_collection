from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.json_importer import import_json_manifest_to_sqlite, import_verified_json_manifests_to_sqlite
from api_launcher.manifests import build_asset_manifest, read_manifest, write_manifest
from api_launcher.repository import ApiCatalogRepository


class JsonImporterTests(unittest.TestCase):
    def test_import_verified_json_manifest_to_sqlite_table_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "stars.json"
            json_path.write_text(
                json.dumps(
                    [
                        {"Name": "Sirius", "Magnitude": -1.46, "meta": {"catalog": "HYG"}},
                        {"Name": "Vega", "Magnitude": 0.03, "discoverer": None},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest_path = write_manifest(
                build_asset_manifest(json_path, json_plan_entry()),
                json_path.with_suffix(".json.manifest.json"),
            )
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()

                result = import_json_manifest_to_sqlite(manifest_path, curated_db, repo)
                assets = repo.managed_asset_records("hyg_database")
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute(
                    'SELECT name, magnitude, meta, discoverer FROM "hyg_sample_1_0" ORDER BY name'
                ).fetchall()

        self.assertEqual(2, result.rows_imported)
        self.assertEqual(("name", "magnitude", "meta", "discoverer"), result.columns)
        self.assertEqual("array", result.source_shape)
        self.assertEqual("hyg_sample_1_0", result.table_name)
        self.assertEqual([("Sirius", "-1.46", '{"catalog": "HYG"}', ""), ("Vega", "0.03", "", "")], rows)
        table_assets = [asset for asset in assets if asset.asset_kind == "table"]
        self.assertEqual(1, len(table_assets))
        self.assertEqual("curated", table_assets[0].asset_role)
        self.assertEqual("json", table_assets[0].source_format)
        self.assertEqual(str(curated_db), table_assets[0].source_uri)
        self.assertEqual(result.schema_fingerprint, table_assets[0].schema_fingerprint)

    def test_cli_imports_jsonl_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "stars.jsonl"
            jsonl_path.write_text('{"name":"Sirius","mag":-1.46}\n{"name":"Vega","mag":0.03}\n', encoding="utf-8")
            manifest_path = write_manifest(
                build_asset_manifest(jsonl_path, json_plan_entry()),
                jsonl_path.with_suffix(".jsonl.manifest.json"),
            )
            curated_db = Path(tmpdir) / "curated.sqlite"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--init-db",
                        "--seed",
                        "--import-json-manifest",
                        str(manifest_path),
                        "--import-sqlite-db",
                        str(curated_db),
                        "--import-table",
                        "stars_json_curated",
                        "--import-row-limit",
                        "1",
                    ]
                )

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, mag FROM "stars_json_curated"').fetchall()

        self.assertEqual(0, rc)
        self.assertEqual([("Sirius", "-1.46")], rows)
        self.assertIn("[json-import] provider=hyg_database table=stars_json_curated rows=1 columns=2", stdout.getvalue())
        self.assertIn("shape=json_lines", stdout.getvalue())

    def test_batch_imports_only_healthy_json_registry_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            json_manifest, csv_manifest, missing_manifest = sample_manifest_set(Path(tmpdir))
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                repo.upsert_dataset_asset_manifest(read_manifest(json_manifest), json_manifest, status="ok")
                repo.upsert_dataset_asset_manifest(read_manifest(csv_manifest), csv_manifest, status="ok")
                repo.upsert_dataset_asset_manifest(read_manifest(missing_manifest), missing_manifest, status="missing")

                result = import_verified_json_manifests_to_sqlite(repo, curated_db)
                second = import_verified_json_manifests_to_sqlite(repo, curated_db)
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, mag FROM "hyg_sample_1_0"').fetchall()

        self.assertEqual([("Sirius", "-1.46")], rows)
        self.assertEqual(3, result.checked)
        self.assertEqual(1, result.imported)
        self.assertEqual(1, result.skipped_non_json)
        self.assertEqual(1, result.skipped_unhealthy)
        self.assertEqual(0, result.skipped_existing)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, second.imported)
        self.assertEqual(1, second.skipped_existing)

    def test_imports_geojson_feature_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            geojson_path = Path(tmpdir) / "places.geojson"
            geojson_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "id": "alpha",
                                "properties": {"name": "Port", "depth": 12},
                                "geometry": {"type": "Point", "coordinates": [120.0, 23.0]},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = write_manifest(
                build_asset_manifest(geojson_path, json_plan_entry(dataset_id="places")),
                geojson_path.with_suffix(".geojson.manifest.json"),
            )
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            curated_db = Path(tmpdir) / "curated.sqlite"
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                result = import_json_manifest_to_sqlite(manifest_path, curated_db, repo)
            finally:
                conn.close()

            with closing(sqlite3.connect(curated_db)) as curated:
                rows = curated.execute('SELECT name, depth, feature_id, geometry_json FROM "places_1_0"').fetchall()

        self.assertEqual("geojson_feature_collection", result.source_shape)
        self.assertEqual(
            [("Port", "12", "alpha", '{"coordinates": [120.0, 23.0], "type": "Point"}')],
            rows,
        )


def json_plan_entry(dataset_id: str = "hyg_sample") -> dict[str, object]:
    return {
        "provider_id": "hyg_database",
        "download_url": f"https://example.test/{dataset_id}.json",
        "dataset_version": {
            "dataset_uid": f"ds_test_{dataset_id}",
            "dataset_id": dataset_id,
            "version": "1.0",
            "download_url": f"https://example.test/{dataset_id}.json",
        },
    }


def sample_manifest_set(root: Path) -> tuple[Path, Path, Path]:
    json_path = root / "stars.json"
    json_path.write_text('[{"name":"Sirius","mag":-1.46}]', encoding="utf-8")
    json_manifest = write_manifest(build_asset_manifest(json_path, json_plan_entry()), json_path.with_suffix(".json.manifest.json"))

    csv_path = root / "stars.csv"
    csv_path.write_text("name,mag\nVega,0.03\n", encoding="utf-8")
    csv_manifest = write_manifest(build_asset_manifest(csv_path, json_plan_entry()), csv_path.with_suffix(".csv.manifest.json"))

    missing_path = root / "missing.json"
    missing_path.write_text('[{"name":"Altair","mag":0.76}]', encoding="utf-8")
    missing_manifest = write_manifest(build_asset_manifest(missing_path, json_plan_entry()), missing_path.with_suffix(".json.manifest.json"))
    return json_manifest, csv_manifest, missing_manifest


if __name__ == "__main__":
    unittest.main()
