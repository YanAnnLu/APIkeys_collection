from __future__ import annotations

import unittest

from api_launcher.importers.curation import CleaningSpec, FieldRule, clean_records


class CurationTests(unittest.TestCase):
    def test_clean_records_renames_casts_and_deduplicates(self) -> None:
        spec = CleaningSpec(
            name="sample",
            fields=(
                FieldRule("id", "dataset_id", required=True),
                FieldRule("depth", "depth_m", cast="float"),
                FieldRule("title", "title", required=True),
            ),
            dedupe_keys=("dataset_id",),
        )
        result = clean_records(
            [
                {"id": "a", "depth": "12.5", "title": " Alpha "},
                {"id": "a", "depth": "12.5", "title": "Alpha Duplicate"},
                {"id": "b", "depth": "7", "title": "Beta"},
            ],
            spec,
        )

        self.assertEqual(
            [
                {"dataset_id": "a", "depth_m": 12.5, "title": "Alpha"},
                {"dataset_id": "b", "depth_m": 7.0, "title": "Beta"},
            ],
            result.rows,
        )
        self.assertEqual(1, len(result.issues))
        self.assertEqual("warning", result.issues[0].severity)

    def test_clean_records_skips_missing_required_values(self) -> None:
        spec = CleaningSpec(
            name="sample",
            fields=(FieldRule("id", "dataset_id", required=True),),
        )
        result = clean_records([{"id": ""}, {"id": "ok"}], spec)

        self.assertEqual([{"dataset_id": "ok"}], result.rows)
        self.assertEqual("error", result.issues[0].severity)


if __name__ == "__main__":
    unittest.main()
