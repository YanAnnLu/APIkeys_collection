from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.db import connect_db
from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.repository import ApiCatalogRepository


class ManifestRegistryTests(unittest.TestCase):
    def test_manifest_can_be_registered_in_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                manifest = build_asset_manifest(
                    payload,
                    {
                        "provider_id": "gebco",
                        "download_url": "https://example.test/sample.bin",
                        "dataset_version": {"dataset_uid": "gebco:sample", "dataset_id": "sample", "version": "2025"},
                    },
                )

                manifest_id = repo.upsert_dataset_asset_manifest(manifest, payload.with_suffix(".manifest.json"), status="ok")
                records = repo.list_dataset_asset_manifests("gebco")
            finally:
                conn.close()

        self.assertTrue(manifest_id.startswith("manifest_"))
        self.assertEqual(1, len(records))
        self.assertEqual("ok", records[0].status)
        self.assertEqual("2025", records[0].version)

    def test_ok_manifest_can_register_downloaded_file_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            payload = Path(tmpdir) / "sample.csv"
            payload.write_text("x,y\n1,2\n", encoding="utf-8")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                manifest = build_asset_manifest(
                    payload,
                    {
                        "provider_id": "gebco",
                        "download_url": "https://example.test/sample.csv",
                        "dataset_version": {"dataset_uid": "gebco:sample", "dataset_id": "sample", "version": "2025"},
                    },
                )
                manifest_path = write_manifest(manifest, payload.with_suffix(".csv.manifest.json"))
                repo.upsert_dataset_asset_manifest(manifest, manifest_path, status="ok")

                asset_id = repo.register_downloaded_manifest_asset(manifest, manifest_path)
                asset = repo.managed_asset_records("gebco")[0]
            finally:
                conn.close()

        self.assertTrue(asset_id.startswith("asset_"))
        self.assertEqual("file", asset.asset_kind)
        self.assertEqual("filesystem", asset.engine)
        self.assertEqual("csv", asset.source_format)
        self.assertEqual("https://example.test/sample.csv", asset.source_uri)

    def test_downloaded_file_asset_records_compound_source_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            payload = Path(tmpdir) / "sample.geojson.gz"
            payload.write_bytes(b"{}")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                manifest = build_asset_manifest(
                    payload,
                    {
                        "provider_id": "gebco",
                        "download_url": "https://example.test/sample.geojson.gz",
                        "dataset_version": {"dataset_uid": "gebco:sample", "dataset_id": "sample", "version": "2025"},
                    },
                )
                manifest_path = write_manifest(manifest, payload.with_suffix(".geojson.gz.manifest.json"))

                repo.register_downloaded_manifest_asset(manifest, manifest_path)
                asset = repo.managed_asset_records("gebco")[0]
            finally:
                conn.close()

        self.assertEqual("geojson.gz", asset.source_format)

    def test_manifest_health_summary_counts_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                manifest = build_asset_manifest(payload, {"provider_id": "gebco"})
                repo.upsert_dataset_asset_manifest(manifest, payload.with_suffix(".manifest.json"), status="missing")

                summary = repo.dataset_asset_manifest_health_summary()
            finally:
                conn.close()

        self.assertEqual(1, summary["missing"])


if __name__ == "__main__":
    unittest.main()
