from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.adapters.gebco import GEBCOTopographyAdapter
from api_launcher.db import connect_db
from api_launcher.models import Provider
from api_launcher.renderer_contracts import GEBCO_2025_DATASET_ID, GEBCO_2025_OPENDAP_URL, GEBCO_PROVIDER_ID
from api_launcher.repository import ApiCatalogRepository


class GEBCOAdapterTests(unittest.TestCase):
    def test_gebco_adapter_discovers_renderer_dataset(self) -> None:
        provider = Provider(
            provider_id=GEBCO_PROVIDER_ID,
            name="GEBCO",
            owner="General Bathymetric Chart of the Oceans",
            categories=("bathymetry", "ocean", "terrain"),
            geographic_scope="global",
            docs_url="https://www.gebco.net/data-products/gridded-bathymetry-data",
            api_base_url="https://www.gebco.net/data-products/gridded-bathymetry-data",
            auth_type="no_key_for_download_pages",
        )

        datasets = GEBCOTopographyAdapter().discover(provider)

        self.assertEqual(1, len(datasets))
        self.assertEqual(GEBCO_2025_DATASET_ID, datasets[0].dataset_id)
        self.assertEqual(GEBCO_2025_OPENDAP_URL, datasets[0].api_url)
        self.assertEqual("netcdf", datasets[0].native_format)
        self.assertEqual("GEBCOTopographyAdapter", datasets[0].metadata["adapter"])
        self.assertEqual("unknown", datasets[0].metadata["training_allowed"])
        self.assertEqual("compatibility_pinned", datasets[0].metadata["version_status"])
        self.assertTrue(datasets[0].metadata["freshness_review_required"])

    def test_gebco_dataset_can_be_upserted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                provider = repo.load_providers([GEBCO_PROVIDER_ID])[0]
                dataset = GEBCOTopographyAdapter().discover(provider)[0]
                repo.upsert_dataset(dataset)

                stored = repo.list_datasets(GEBCO_PROVIDER_ID)
            finally:
                conn.close()

        self.assertEqual(1, len(stored))
        self.assertEqual(GEBCO_2025_DATASET_ID, stored[0].dataset_id)


if __name__ == "__main__":
    unittest.main()
