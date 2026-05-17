from __future__ import annotations

import unittest

from api_launcher.adapters.base import dataset_uid
from api_launcher.dataset_updates import compare_versions, plan_dataset_update
from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.models import Dataset


class DatasetUpdateTests(unittest.TestCase):
    def test_same_version_is_skipped(self) -> None:
        current = self.dataset("2025")
        target = self.option("2025", "compare_then_replace_or_keep_legacy")

        plan = plan_dataset_update(current, target)

        self.assertEqual("skip_same_version", plan.decision)
        self.assertEqual("same", plan.direction)
        self.assertFalse(plan.needs_download)

    def test_new_version_compares_before_update(self) -> None:
        current = self.dataset("2025")
        target = self.option("2026", "compare_then_replace_or_keep_legacy")

        plan = plan_dataset_update(current, target)

        self.assertEqual("compare_then_update", plan.decision)
        self.assertEqual("upgrade", plan.direction)
        self.assertTrue(plan.needs_download)

    def test_legacy_compatibility_version_is_kept_side_by_side(self) -> None:
        current = self.dataset("2026")
        target = self.option("2025", "keep_legacy_for_renderer_compatibility")

        plan = plan_dataset_update(current, target)

        self.assertEqual("keep_legacy_and_install_new", plan.decision)
        self.assertEqual("downgrade", plan.direction)

    def test_version_direction_supports_middle_and_rollback_targets(self) -> None:
        self.assertEqual("partial_forward", compare_versions("2022", "2025"))
        self.assertEqual("partial_backward", compare_versions("2026", "2024"))
        self.assertEqual("unknown", compare_versions("v1-beta", "v2"))

    def dataset(self, version: str) -> Dataset:
        return Dataset(
            dataset_uid=dataset_uid("provider", "sample"),
            provider_id="provider",
            dataset_id="sample",
            title="Sample",
            categories=("test",),
            version=version,
        )

    def option(self, version: str, strategy: str) -> DatasetVersionOption:
        return DatasetVersionOption(
            dataset_uid=dataset_uid("provider", "sample"),
            dataset_id="sample",
            label=f"Sample {version}",
            version=version,
            status="latest_known",
            download_url="https://example.test/sample.dat",
            landing_url="https://example.test/",
            update_strategy=strategy,
        )


if __name__ == "__main__":
    unittest.main()
