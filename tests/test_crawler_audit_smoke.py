from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest

from api_launcher.cli_dataset_discovery import add_dataset_discovery_args, dataset_discovery_command_active, discover_dataset_candidates_cli
from api_launcher.crawler_audit_smoke import crawler_handler_audit_smoke_report, crawler_handler_smoke_sources
from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES


class CrawlerAuditSmokeTest(unittest.TestCase):
    def test_smoke_sources_cover_every_supported_handler(self) -> None:
        sources = crawler_handler_smoke_sources()

        self.assertEqual(set(SUPPORTED_DATASET_SOURCE_TYPES), {source.source_type for source in sources})
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), len({source.source_id for source in sources}))
        self.assertTrue(all(source.min_expected_candidates == 1 for source in sources))

    def test_handler_audit_smoke_reports_zero_candidate_next_action_for_all_handlers(self) -> None:
        report = crawler_handler_audit_smoke_report()
        empty_case = report["empty_case"]
        summary = empty_case["audit_summary"]

        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), report["supported_source_type_count"])
        self.assertEqual("warning", summary["status"])
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), summary["by_warning_code"]["zero_candidates"])
        self.assertEqual(
            len(SUPPORTED_DATASET_SOURCE_TYPES),
            summary["by_next_action"]["repair_crawler_query_or_parser"],
        )
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), summary["problem_source_count"])
        for result in empty_case["source_results"]:
            self.assertEqual("warning", result["audit_status"])
            self.assertEqual(["zero_candidates"], result["warning_codes"])
            self.assertEqual("repair_crawler_query_or_parser", result["next_action"])

    def test_handler_audit_smoke_reports_pass_for_valid_fixture_candidates(self) -> None:
        report = crawler_handler_audit_smoke_report()
        candidate_case = report["candidate_case"]
        summary = candidate_case["audit_summary"]

        self.assertEqual("pass", summary["status"])
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), candidate_case["candidate_count"])
        self.assertEqual(0, candidate_case["warning_count"])
        self.assertEqual(0, summary["problem_source_count"])
        self.assertEqual({"pass": len(SUPPORTED_DATASET_SOURCE_TYPES), "warning": 0, "error": 0}, summary["by_status"])

    def test_cli_can_emit_handler_smoke_json_without_live_crawl(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--timeout", type=float, default=1.0)
        parser.add_argument("--provider", action="append", default=[])
        add_dataset_discovery_args(parser)
        args = parser.parse_args(["--dataset-discovery-handler-smoke-json"])

        self.assertTrue(dataset_discovery_command_active(args))
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            discover_dataset_candidates_cli(None, args)  # type: ignore[arg-type]

        payload = json.loads(stream.getvalue())
        self.assertEqual("offline crawler handler audit contract smoke; no live network requests", payload["role"])
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), payload["supported_source_type_count"])


if __name__ == "__main__":
    unittest.main()
