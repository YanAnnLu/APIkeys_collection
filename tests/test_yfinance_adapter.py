# 這份測試鎖定 yfinance 的「可選非官方」邊界，避免 CI 或一般流程偷偷打 Yahoo。
from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from api_launcher.adapters.yfinance import (
    YFINANCE_PROVIDER_ID,
    YFinanceMarketDataAdapter,
    build_yfinance_demo_plan,
    normalize_yfinance_symbols,
    write_yfinance_demo_plan,
    yfinance_provider,
)
from api_launcher.core import main
from api_launcher.dataset_versions import version_options_for_dataset
from api_launcher.plans import provider_dataset_version_plan_entry


class YFinanceAdapterTests(unittest.TestCase):
    def test_adapter_discovers_query_template_without_live_fetch(self) -> None:
        provider = yfinance_provider()
        dataset = YFinanceMarketDataAdapter().discover(provider)[0]
        option = version_options_for_dataset(dataset)[0]
        entry = provider_dataset_version_plan_entry(provider, dataset, option)

        self.assertEqual(YFINANCE_PROVIDER_ID, dataset.provider_id)
        self.assertEqual("yfinance_query", dataset.native_format)
        self.assertTrue(dataset.metadata["requires_opt_in_live_fetch"])
        self.assertEqual("adapter_required", entry["download_eligibility"]["status"])
        self.assertEqual("adapter_review_required", entry["import_plan"]["status"])
        self.assertIn("yfinance://download", entry["adapter_review"]["source_url"])

    def test_demo_plan_writes_fixture_backed_direct_csv_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "yfinance_plan.json"
            result = write_yfinance_demo_plan(plan_path, symbols=("aapl", "MSFT"))
            payload = json.loads(result.plan_path.read_text(encoding="utf-8"))
            fixture_exists = result.fixture_path.exists()

        entry = payload["providers"][0]
        self.assertTrue(fixture_exists)
        self.assertEqual(("AAPL", "MSFT"), result.symbols)
        self.assertEqual("yfinance_offline_fixture", payload["source"]["kind"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual("append_only_or_revisable_market_data", entry["time_series_contract"]["kind"])

    def test_cli_writes_yfinance_demo_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "yfinance_plan.json"
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(["--write-yfinance-demo-plan", str(plan_path), "--yfinance-symbol", "AAPL"])

            payload = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertIn("[yfinance-demo] wrote", output.getvalue())
        self.assertEqual(["AAPL"], payload["source"]["symbols"])
        self.assertEqual(1, payload["summary"]["direct_download_count"])

    def test_demo_plan_can_download_and_import_without_yfinance_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "yfinance_plan.json"
            db_path = Path(tmpdir) / "launcher.sqlite"
            import_db = Path(tmpdir) / "curated.sqlite"
            downloads_root = Path(tmpdir) / "downloads"
            result = write_yfinance_demo_plan(plan_path, symbols=("AAPL",), downloads_root=downloads_root)
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--init-db",
                        "--seed",
                        "--run-download-plan",
                        str(result.plan_path),
                        "--downloads-root",
                        str(downloads_root),
                        "--import-supported-plan-results",
                        "--import-sqlite-db",
                        str(import_db),
                        "--plan-import-existing-table-policy",
                        "rename",
                    ]
            )

            with closing(sqlite3.connect(import_db)) as conn:
                row_count = conn.execute(
                    "SELECT COUNT(*) FROM yahoo_finance_yfinance_yfinance_ohlcv_fixture_aapl"
                ).fetchone()[0]

        self.assertEqual(0, rc)
        self.assertIn("submitted=1 completed=1", output.getvalue())
        self.assertIn("imported=1", output.getvalue())
        self.assertEqual(3, row_count)

    def test_symbol_normalization_rejects_unsafe_values(self) -> None:
        self.assertEqual(("AAPL", "MSFT"), normalize_yfinance_symbols(("aapl", "MSFT", "aapl")))
        with self.assertRaises(ValueError):
            normalize_yfinance_symbols(("AAPL;rm -rf",))

    def test_build_plan_uses_defaults_when_symbols_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = Path(tmpdir) / "fixture.csv"
            fixture.write_text("event_time,symbol\n", encoding="utf-8")
            payload = build_yfinance_demo_plan(fixture, symbols=())

        self.assertEqual(["AAPL", "MSFT"], payload["source"]["symbols"])


if __name__ == "__main__":
    unittest.main()
