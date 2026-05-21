# 這份測試鎖定 structured event log，避免 repair/download 診斷事件失去可讀脈絡。
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from api_launcher.event_log import latest_events, log_event, log_exception


class EventLogTests(unittest.TestCase):
    def test_event_log_writes_jsonl_for_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"

            log_event("sample_event", "hello", component="test", context={"provider_id": "sample"}, log_path=path)
            events = latest_events(log_path=path)

        self.assertEqual(1, len(events))
        self.assertEqual("sample_event", events[0]["event"])
        self.assertEqual("sample", events[0]["context"]["provider_id"])
        self.assertIn("platform", events[0])

    def test_exception_log_includes_error_type_and_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            try:
                raise RuntimeError("boom")
            except RuntimeError as exc:
                log_exception("sample_failure", exc, component="test", log_path=path)

            record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual("error", record["level"])
        self.assertEqual("RuntimeError", record["error_type"])
        self.assertIn("RuntimeError: boom", record["traceback"])


if __name__ == "__main__":
    unittest.main()
