from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.adapters.hyg import HYGStarCatalogAdapter
from api_launcher.db import connect_db
from api_launcher.models import Provider
from api_launcher.renderer_contracts import HYG_PROVIDER_ID, HYG_V38_DATASET_ID, HYG_V38_URL
from api_launcher.repository import ApiCatalogRepository


class HYGAdapterTests(unittest.TestCase):
    def test_hyg_adapter_discovers_renderer_dataset(self) -> None:
        provider = Provider(
            provider_id=HYG_PROVIDER_ID,
            name="HYG Database",
            owner="Astronexus",
            categories=("astronomy", "stars"),
            geographic_scope="celestial",
            docs_url="https://codeberg.org/astronexus/hyg",
            api_base_url=HYG_V38_URL,
            auth_type="no_key_for_public_data",
        )

        datasets = HYGStarCatalogAdapter().discover(provider)

        self.assertEqual(1, len(datasets))
        self.assertEqual(HYG_V38_DATASET_ID, datasets[0].dataset_id)
        self.assertEqual(HYG_V38_URL, datasets[0].api_url)
        self.assertEqual("csv.gz", datasets[0].native_format)
        self.assertEqual("HYGStarCatalogAdapter", datasets[0].metadata["adapter"])

    def test_hyg_dataset_can_be_upserted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                provider = repo.load_providers([HYG_PROVIDER_ID])[0]
                dataset = HYGStarCatalogAdapter().discover(provider)[0]
                repo.upsert_dataset(dataset)

                stored = repo.list_datasets(HYG_PROVIDER_ID)
            finally:
                conn.close()

        self.assertEqual(1, len(stored))
        self.assertEqual(HYG_V38_DATASET_ID, stored[0].dataset_id)


if __name__ == "__main__":
    unittest.main()
