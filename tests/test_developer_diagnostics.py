from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.developer_diagnostics import (
    CRAWLER_HANDLER_SMOKE_DIAGNOSTIC_ID,
    OFFLINE_CONTRACT_SMOKE_SCOPE,
    crawler_handler_smoke_diagnostics_payload,
)
from api_launcher.crawler_registry_report import crawler_registry_report, crawler_registry_summary
from api_launcher.crawlers.dataset_sources import SUPPORTED_DATASET_SOURCE_TYPES


class DeveloperDiagnosticsTests(unittest.TestCase):
    def test_crawler_handler_smoke_payload_is_surface_scoped_and_compact(self) -> None:
        payload = crawler_handler_smoke_diagnostics_payload("qt_preview")

        self.assertEqual("qt_preview", payload["surface"])
        self.assertEqual("developer_diagnostics", payload["purpose"])
        self.assertEqual(CRAWLER_HANDLER_SMOKE_DIAGNOSTIC_ID, payload["diagnostic_id"])
        self.assertTrue(payload["developer_only"])
        self.assertEqual(OFFLINE_CONTRACT_SMOKE_SCOPE, payload["scope"])
        self.assertEqual("摘要失敗時，執行 handler smoke JSON 診斷", payload["next_action_label"])
        self.assertIn("--dataset-discovery-handler-smoke-json", payload["summary"]["command"])
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), payload["registry_summary"]["source_type_count"])
        self.assertIn("catalog_search", payload["registry_summary"]["source_families"])
        self.assertNotIn("source_results", json.dumps(payload, ensure_ascii=False))

    def test_crawler_handler_smoke_payload_normalizes_blank_surface(self) -> None:
        payload = crawler_handler_smoke_diagnostics_payload("  ")

        self.assertEqual("unknown", payload["surface"])

    def test_crawler_registry_report_is_dimension_indexed(self) -> None:
        report = crawler_registry_report()
        summary = crawler_registry_summary()

        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), report["source_type_count"])
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), len(report["specs"]))
        self.assertGreaterEqual(report["matrix_cell_count"], 4)
        self.assertIn("optional_api_key", report["dimensions"]["auth_profile"])
        self.assertIn("file_links", report["dimensions"]["result_shape"])
        self.assertIn("entry_listing", report["dimensions"]["seed_scope"])
        self.assertIn("paginated_catalog", summary["seed_scopes"])
        self.assertEqual(report["source_type_count"], summary["source_type_count"])
        self.assertIn("use_registry_report", summary["next_action"])

    def test_cli_emits_crawler_registry_report_json_without_setup_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--init-db",
                        "--seed",
                        "--crawler-registry-report-json",
                    ]
                )

            payload = json.loads(stdout.getvalue())

        self.assertEqual(0, rc)
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual(len(SUPPORTED_DATASET_SOURCE_TYPES), payload["source_type_count"])
        self.assertIn("catalog_search", payload["dimensions"]["source_family"])
        self.assertNotIn("[db]", stdout.getvalue())
        self.assertNotIn("[seed]", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
