from __future__ import annotations

import unittest
from types import SimpleNamespace

from api_launcher.crawler_run_records import (
    crawler_run_context_summary,
    crawler_run_event_summary,
    crawler_run_record_from_result,
    crawler_run_summary_from_events,
)


class CrawlerRunRecordTest(unittest.TestCase):
    def test_run_record_from_result_returns_empty_payload_for_missing_contract(self) -> None:
        self.assertEqual({}, crawler_run_record_from_result(SimpleNamespace()))

    def test_run_record_from_result_returns_empty_payload_when_to_dict_fails(self) -> None:
        def broken_to_dict() -> dict[str, object]:
            raise RuntimeError("boom")

        self.assertEqual({}, crawler_run_record_from_result(SimpleNamespace(to_dict=broken_to_dict)))

    def test_run_record_from_result_copies_compact_record(self) -> None:
        record = {"stage": "download_plan_build", "status": "review"}
        result = SimpleNamespace(to_dict=lambda: {"run_record": record})

        extracted = crawler_run_record_from_result(result)

        self.assertEqual(record, extracted)
        self.assertIsNot(record, extracted)

    def test_context_summary_keeps_run_record_counts_without_resolved_plan_body(self) -> None:
        summary = crawler_run_context_summary(
            {
                "asset_id": "sample_asset",
                "candidate_count": 4,
                "resolved_plan": {"providers": [{"large": "payload"}]},
                "run_record": {
                    "record_key": "abc123",
                    "stage": "download_plan_build",
                    "status": "review",
                    "candidate_count": 4,
                    "direct_download_count": 1,
                    "review_required_count": 3,
                    "source_signature": "hidden-from-compact-summary",
                },
            }
        )

        self.assertEqual("sample_asset", summary["asset_id"])
        self.assertEqual(4, summary["candidate_count"])
        self.assertEqual("download_plan_build", summary["run_record"]["stage"])
        self.assertEqual(1, summary["run_record"]["direct_download_count"])
        self.assertNotIn("resolved_plan", summary)
        self.assertNotIn("source_signature", summary["run_record"])

    def test_event_summary_reports_resolved_plan_presence_without_copying_payload(self) -> None:
        summary = crawler_run_event_summary(
            {
                "timestamp": "2026-05-26T13:00:00+00:00",
                "level": "info",
                "event": "crawler_asset_plan_outcome_recorded",
                "context": {
                    "asset_id": "sample_asset",
                    "resolved_plan": {},
                    "run_record": {
                        "record_key": "def456",
                        "stage": "download_plan_build",
                        "status": "ready",
                        "direct_download_count": 2,
                    },
                },
            }
        )

        self.assertEqual("crawler_asset_plan_outcome_recorded", summary["event"])
        self.assertEqual("sample_asset", summary["asset_id"])
        self.assertEqual(2, summary["direct_download_count"])
        self.assertTrue(summary["resolved_plan_available"])
        self.assertNotIn("resolved_plan", summary)

    def test_summary_from_events_uses_latest_listing_and_plan_events(self) -> None:
        summary = crawler_run_summary_from_events(
            [
                {
                    "timestamp": "old",
                    "event": "crawler_asset_listing_recorded",
                    "context": {"asset_id": "old_asset", "candidate_count": 1},
                },
                {
                    "timestamp": "latest-listing",
                    "event": "crawler_asset_listing_recorded",
                    "context": {"asset_id": "new_asset", "candidate_count": 5},
                },
                {
                    "timestamp": "latest-plan",
                    "event": "crawler_asset_plan_outcome_recorded",
                    "context": {
                        "asset_id": "new_asset",
                        "direct_download_count": 2,
                        "resolved_plan": {"providers": [{"large": "payload"}]},
                    },
                },
            ]
        )

        self.assertEqual("new_asset", summary["latest_listing"]["asset_id"])
        self.assertEqual(5, summary["latest_listing"]["candidate_count"])
        self.assertEqual(2, summary["latest_download_plan_build"]["direct_download_count"])
        self.assertTrue(summary["latest_download_plan_build"]["resolved_plan_available"])
        self.assertNotIn("resolved_plan", summary["latest_download_plan_build"])


if __name__ == "__main__":
    unittest.main()
