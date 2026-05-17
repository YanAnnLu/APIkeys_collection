from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from APIkeys_collection import main
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

    def test_dataset_candidates_can_be_listed_and_reviewed(self) -> None:
        uid = dataset_uid("sample_provider", "candidate_a")
        self.repo.upsert_dataset(
            Dataset(
                dataset_uid=uid,
                provider_id="sample_provider",
                dataset_id="candidate_a",
                title="Candidate A",
                categories=("test",),
                native_format="csv",
                metadata={
                    "candidate_status": "needs_review",
                    "data_family": "table",
                    "source_url": "https://example.test/candidate.csv",
                },
            )
        )

        candidates = self.repo.list_dataset_candidates()
        reviewed = self.repo.mark_dataset_candidate_status(uid, "approved", reviewed_by="unit-test", note="Looks usable.")

        self.assertEqual([uid], [candidate.dataset_uid for candidate in candidates])
        self.assertEqual("approved", reviewed.metadata["candidate_status"])
        self.assertEqual("unit-test", reviewed.metadata["candidate_reviewed_by"])
        self.assertEqual("Looks usable.", reviewed.metadata["candidate_review_note"])
        self.assertEqual([], self.repo.list_dataset_candidates())
        self.assertEqual([uid], [candidate.dataset_uid for candidate in self.repo.list_dataset_candidates("approved")])

    def test_dataset_candidate_rejects_unknown_status(self) -> None:
        uid = dataset_uid("sample_provider", "candidate_b")
        self.repo.upsert_dataset(
            Dataset(
                dataset_uid=uid,
                provider_id="sample_provider",
                dataset_id="candidate_b",
                title="Candidate B",
                categories=("test",),
                metadata={"candidate_status": "needs_review"},
            )
        )

        with self.assertRaises(ValueError):
            self.repo.mark_dataset_candidate_status(uid, "maybe_later")

    def test_cli_can_list_and_review_dataset_candidates(self) -> None:
        uid = dataset_uid("sample_provider", "candidate_cli")
        self.repo.upsert_dataset(
            Dataset(
                dataset_uid=uid,
                provider_id="sample_provider",
                dataset_id="candidate_cli",
                title="Candidate CLI",
                categories=("test",),
                metadata={"candidate_status": "needs_review"},
            )
        )
        self.conn.close()
        db_path = Path(self.tmpdir.name) / "test.sqlite"

        listed_output = io.StringIO()
        with contextlib.redirect_stdout(listed_output):
            rc = main(["--db", str(db_path), "--list-dataset-candidates", "--dataset-candidates-json"])
        payload = json.loads(listed_output.getvalue())

        reviewed_output = io.StringIO()
        with contextlib.redirect_stdout(reviewed_output):
            review_rc = main(
                [
                    "--db",
                    str(db_path),
                    "--review-dataset-candidate",
                    uid,
                    "--dataset-candidate-decision",
                    "rejected",
                    "--dataset-candidate-note",
                    "not suitable for MVP",
                ]
            )

        self.conn = connect_db(db_path)
        self.repo = ApiCatalogRepository(self.conn)
        reviewed = self.repo.list_dataset_candidates("rejected")

        self.assertEqual(0, rc)
        self.assertEqual(0, review_rc)
        self.assertEqual(1, payload["candidate_count"])
        self.assertEqual(uid, payload["candidates"][0]["dataset_uid"])
        self.assertEqual([uid], [dataset.dataset_uid for dataset in reviewed])
        self.assertEqual("not suitable for MVP", reviewed[0].metadata["candidate_review_note"])


if __name__ == "__main__":
    unittest.main()
