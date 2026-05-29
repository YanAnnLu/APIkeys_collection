# 這份測試鎖定 structured event log，避免 repair/download 診斷事件失去可讀脈絡。
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_launcher.event_log import DEFAULT_EVENT_LOG_TAIL_BLOCK_BYTES, latest_events, log_event, log_exception


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

    def test_latest_events_streams_only_tail_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            for index in range(5):
                log_event(f"event_{index}", "hello", component="test", log_path=path)

            events = latest_events(limit=2, log_path=path)
            none_events = latest_events(limit=0, log_path=path)

        self.assertEqual(["event_3", "event_4"], [event["event"] for event in events])
        self.assertEqual([], none_events)
        self.assertEqual(8192, DEFAULT_EVENT_LOG_TAIL_BLOCK_BYTES)

    def test_latest_events_falls_back_when_seek_tail_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            for index in range(4):
                log_event(f"event_{index}", "hello", component="test", log_path=path)

            with patch("api_launcher.event_log._tail_text_lines_seek", side_effect=OSError("cloud seek failed")):
                events = latest_events(limit=2, log_path=path)

        self.assertEqual(["event_2", "event_3"], [event["event"] for event in events])

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
