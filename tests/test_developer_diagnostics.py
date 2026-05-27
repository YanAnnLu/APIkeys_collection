from __future__ import annotations

import json
import unittest

from api_launcher.developer_diagnostics import (
    CRAWLER_HANDLER_SMOKE_DIAGNOSTIC_ID,
    OFFLINE_CONTRACT_SMOKE_SCOPE,
    crawler_handler_smoke_diagnostics_payload,
)


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
        self.assertNotIn("source_results", json.dumps(payload, ensure_ascii=False))

    def test_crawler_handler_smoke_payload_normalizes_blank_surface(self) -> None:
        payload = crawler_handler_smoke_diagnostics_payload("  ")

        self.assertEqual("unknown", payload["surface"])


if __name__ == "__main__":
    unittest.main()
