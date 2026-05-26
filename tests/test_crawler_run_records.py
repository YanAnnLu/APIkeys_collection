from __future__ import annotations

import unittest
from types import SimpleNamespace

from api_launcher.crawler_run_records import crawler_run_record_from_result


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


if __name__ == "__main__":
    unittest.main()
