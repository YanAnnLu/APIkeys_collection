from __future__ import annotations

import unittest

from api_launcher.adapters.base import dataset_uid
from api_launcher.dataset_updates import compare_versions, dataset_update_contract, plan_dataset_update
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

    def test_same_version_append_only_timeseries_still_ingests(self) -> None:
        current = self.dataset("live")
        target = self.option("live", "append_only_timeseries")

        plan = plan_dataset_update(current, target)

        self.assertEqual("append_incremental", plan.decision)
        self.assertEqual("same", plan.direction)
        self.assertTrue(plan.needs_ingest)

    def test_same_version_realtime_stream_is_not_skipped(self) -> None:
        current = self.dataset("live")
        target = self.option("live", "realtime_stream")

        plan = plan_dataset_update(current, target)

        self.assertEqual("maintain_realtime_stream", plan.decision)
        self.assertTrue(plan.needs_ingest)

    def test_financial_tick_dataset_infers_realtime_contract(self) -> None:
        dataset = self.dataset(
            "live",
            categories=("finance", "crypto", "market_data"),
            data_type="tick_time_series",
            metadata={"temporal_resolution": "1s", "update_strategy": "live_market_data"},
        )

        contract = dataset_update_contract(dataset)

        self.assertEqual("realtime_stream", contract.mode)
        self.assertIn("event_time", contract.required_fields)
        self.assertIn("received_at", contract.required_fields)
        self.assertIn("PostgreSQL/TimescaleDB", contract.recommended_backends)

    def test_static_dataset_contract_keeps_version_manifest_logic(self) -> None:
        contract = dataset_update_contract(self.dataset("2025"))

        self.assertEqual("static_versioned", contract.mode)
        self.assertFalse(contract.is_time_series)
        self.assertIn("manifest_sha256", contract.required_fields)

    def dataset(
        self,
        version: str,
        categories: tuple[str, ...] = ("test",),
        data_type: str = "",
        metadata: dict[str, object] | None = None,
    ) -> Dataset:
        return Dataset(
            dataset_uid=dataset_uid("provider", "sample"),
            provider_id="provider",
            dataset_id="sample",
            title="Sample",
            categories=categories,
            data_type=data_type,
            version=version,
            metadata=metadata or {},
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
