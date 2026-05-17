from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.adapters import dataset_uid
from api_launcher.db import connect_db
from api_launcher.models import Dataset, Provider
from api_launcher.repository import ApiCatalogRepository


class DatasetCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.conn = connect_db(Path(self.tmpdir.name) / "test.sqlite")
        self.repo = ApiCatalogRepository(self.conn)
        self.repo.init_schema()
        self.repo.upsert_provider(
            Provider(
                provider_id="sample_provider",
                name="Sample Provider",
                owner="Sample Owner",
                categories=("test",),
                geographic_scope="global",
                docs_url="https://example.test/docs",
            )
        )

    def tearDown(self) -> None:
        self.conn.close()
        self.tmpdir.cleanup()

    def test_dataset_uid_is_stable(self) -> None:
        first = dataset_uid("Sample_Provider", "Dataset_A")
        second = dataset_uid("sample_provider", "dataset_a")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("ds_"))

    def test_upsert_dataset_creates_sync_state(self) -> None:
        uid = dataset_uid("sample_provider", "dataset_a")
        self.repo.upsert_dataset(
            Dataset(
                dataset_uid=uid,
                provider_id="sample_provider",
                dataset_id="dataset_a",
                title="Dataset A",
                categories=("test", "demo"),
                native_format="csv",
                metadata={"source": "unit-test"},
            )
        )

        datasets = self.repo.list_datasets("sample_provider")
        sync_state = self.conn.execute(
            "SELECT diff_status FROM dataset_sync_state WHERE dataset_uid = ?",
            (uid,),
        ).fetchone()

        self.assertEqual(1, len(datasets))
        self.assertEqual("Dataset A", datasets[0].title)
        self.assertEqual(("test", "demo"), datasets[0].categories)
        self.assertEqual({"source": "unit-test"}, datasets[0].metadata)
        self.assertEqual("unknown", sync_state["diff_status"])


if __name__ == "__main__":
    unittest.main()
