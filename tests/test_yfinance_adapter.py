# 這份測試鎖定 yfinance 的「可選非官方」邊界，避免 CI 或一般流程偷偷打 Yahoo。
from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api_launcher.adapters.yfinance import (
    DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
    DEFAULT_YFINANCE_RETENTION_DAYS,
    DEFAULT_YFINANCE_STORAGE_TARGET,
    YFINANCE_PROVIDER_ID,
    YFinanceMarketDataAdapter,
    build_yfinance_demo_plan,
    build_yfinance_live_plan,
    build_yfinance_storage_review,
    normalize_yfinance_query_window_preset,
    normalize_yfinance_retention_days,
    normalize_yfinance_storage_target,
    normalize_yfinance_symbols,
    write_yfinance_demo_plan,
    write_yfinance_live_plan,
    write_yfinance_storage_review,
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

    def test_live_plan_requires_explicit_unofficial_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "unofficial"):
                write_yfinance_live_plan(
                    Path(tmpdir) / "live_plan.json",
                    symbols=("AAPL",),
                    fetcher=lambda _symbols, _period, _interval: FakeYFinanceFrame(),
                )

    def test_live_plan_writes_csv_backed_direct_plan_with_fake_fetcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "live_plan.json"
            result = write_yfinance_live_plan(
                plan_path,
                symbols=("aapl", "MSFT"),
                period="5d",
                interval="1d",
                retention_days=90,
                fetcher=lambda _symbols, _period, _interval: FakeYFinanceFrame(),
                acknowledge_unofficial=True,
                received_at="2026-05-22T00:00:00Z",
                ingest_run_id="test_yfinance_live",
            )
            payload = json.loads(result.plan_path.read_text(encoding="utf-8"))
            csv_text = result.csv_path.read_text(encoding="utf-8")

        self.assertEqual(("AAPL", "MSFT"), result.symbols)
        self.assertEqual(4, result.rows_written)
        self.assertEqual(90, result.retention_days)
        self.assertEqual("yfinance_live_csv", payload["source"]["kind"])
        self.assertEqual(90, payload["source"]["retention_policy"]["retention_days"])
        self.assertEqual("direct_download", payload["providers"][0]["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", payload["providers"][0]["import_plan"]["status"])
        self.assertEqual(False, payload["providers"][0]["time_series_contract"]["retention_policy"]["background_refresh"])
        self.assertIn("unofficial", payload["source"]["warning"])
        self.assertIn("2026-05-21T00:00:00Z,AAPL,100,103,99,102,102,1000000", csv_text)
        self.assertIn("test_yfinance_live", csv_text)

    def test_cli_writes_yfinance_live_plan_through_opt_in_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "live_plan.json"
            output = io.StringIO()
            fake_result = SimpleNamespace(
                plan_path=plan_path,
                csv_path=Path(tmpdir) / "live_plan.live.csv",
                symbols=("AAPL",),
                rows_written=2,
                period="5d",
                interval="1d",
                retention_days=30,
                query_window_preset=DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
                storage_target="mysql_timeseries_table",
            )

            with patch("api_launcher.core.write_yfinance_live_plan_files", return_value=fake_result) as live_mock:
                with redirect_stdout(output):
                    rc = main(
                        [
                            "--write-yfinance-live-plan",
                            str(plan_path),
                            "--yfinance-symbol",
                            "AAPL",
                            "--yfinance-period",
                            "5d",
                            "--yfinance-interval",
                            "1d",
                            "--yfinance-retention-days",
                            "30",
                            "--yfinance-storage-target",
                            "mysql_timeseries_table",
                            "--yfinance-acknowledge-unofficial",
                        ]
                    )

        self.assertEqual(0, rc)
        self.assertIn("[yfinance-live] warning=", output.getvalue())
        self.assertIn("retention_days=30", output.getvalue())
        self.assertIn("storage_target=mysql_timeseries_table", output.getvalue())
        live_mock.assert_called_once()
        self.assertTrue(live_mock.call_args.kwargs["acknowledge_unofficial"])
        self.assertEqual(30, live_mock.call_args.kwargs["retention_days"])
        self.assertEqual(DEFAULT_YFINANCE_QUERY_WINDOW_PRESET, live_mock.call_args.kwargs["query_window_preset"])
        self.assertEqual("mysql_timeseries_table", live_mock.call_args.kwargs["storage_target"])

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

    def test_build_live_plan_uses_direct_csv_import_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "live.csv"
            csv_path.write_text("event_time,symbol\n", encoding="utf-8")
            payload = build_yfinance_live_plan(
                csv_path,
                symbols=("AAPL",),
                period="1mo",
                interval="1d",
                retention_days=45,
                received_at="2026-05-22T00:00:00Z",
                ingest_run_id="test_run",
            )

        entry = payload["providers"][0]
        self.assertEqual("yfinance_live_csv", payload["source"]["kind"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual("append_only_or_revisable_market_data", entry["time_series_contract"]["kind"])
        self.assertEqual(45, payload["source"]["retention_policy"]["retention_days"])
        self.assertEqual(45, entry["dataset_version"]["metadata"]["retention_policy"]["retention_days"])
        self.assertEqual("auto", payload["source"]["storage_policy"]["selection"])
        self.assertEqual("sqlite_mvp_table", payload["source"]["storage_policy"]["recommended_target"])

    def test_query_window_preset_supplies_chart_friendly_period_interval(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetcher(symbols: tuple[str, ...], period: str, interval: str) -> FakeYFinanceFrame:
            captured["symbols"] = symbols
            captured["period"] = period
            captured["interval"] = interval
            return FakeYFinanceFrame()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_yfinance_live_plan(
                Path(tmpdir) / "live_plan.json",
                symbols=("AAPL", "MSFT"),
                query_window_preset="intraday-5d-5m",
                fetcher=fake_fetcher,
                acknowledge_unofficial=True,
                received_at="2026-05-22T00:00:00Z",
                ingest_run_id="test_yfinance_window",
            )
            payload = json.loads(result.plan_path.read_text(encoding="utf-8"))

        query_window = payload["source"]["query_window"]
        self.assertEqual("5d", captured["period"])
        self.assertEqual("5m", captured["interval"])
        self.assertEqual("5d", result.period)
        self.assertEqual("5m", result.interval)
        self.assertEqual("intraday_5d_5m", result.query_window_preset)
        self.assertEqual("intraday_5d_5m", query_window["preset_key"])
        self.assertEqual(False, query_window["background_refresh"])
        self.assertEqual("short_horizon_sqlite_or_mysql_cache", query_window["storage_hint"])
        self.assertEqual("auto", payload["source"]["storage_policy"]["selection"])
        self.assertEqual("sqlite_mvp_table", payload["source"]["storage_policy"]["recommended_target"])

    def test_query_window_preset_records_manual_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "live.csv"
            csv_path.write_text("event_time,symbol\n", encoding="utf-8")
            payload = build_yfinance_live_plan(
                csv_path,
                symbols=("AAPL",),
                period="5d",
                interval="1d",
                query_window_preset="daily_6mo",
            )

        query_window = payload["source"]["query_window"]
        self.assertEqual("daily_6mo", query_window["preset_key"])
        self.assertEqual("5d", query_window["period"])
        self.assertEqual("1d", query_window["interval"])
        self.assertEqual(True, query_window["manual_override"])
        self.assertEqual("mysql_timeseries_table", payload["source"]["storage_policy"]["recommended_target"])

    def test_live_plan_can_record_explicit_storage_target_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "live.csv"
            csv_path.write_text("event_time,symbol\n", encoding="utf-8")
            payload = build_yfinance_live_plan(
                csv_path,
                symbols=("AAPL",),
                query_window_preset="daily_6mo",
                storage_target="parquet-duckdb-archive",
            )

        policy = payload["source"]["storage_policy"]
        self.assertEqual("parquet_duckdb_archive", policy["selection"])
        self.assertEqual("explicit_user_selection", policy["mode"])
        self.assertEqual("parquet_duckdb_archive", policy["recommended_target"])
        self.assertEqual(False, policy["background_write"])
        self.assertEqual(False, policy["automatic_migration"])
        self.assertEqual(True, policy["requires_explicit_user_import_or_export"])
        self.assertEqual("parquet_duckdb_archive", payload["providers"][0]["time_series_contract"]["storage_policy"]["recommended_target"])

    def test_storage_review_writes_mysql_dry_run_without_mutating_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            csv_path = root / "live.csv"
            plan_path = root / "live_plan.json"
            review_path = root / "storage_review.json"
            csv_path.write_text("event_time,symbol\n", encoding="utf-8")
            plan_payload = build_yfinance_live_plan(
                csv_path,
                symbols=("AAPL",),
                query_window_preset="daily_6mo",
                storage_target="mysql_timeseries_table",
                received_at="2026-05-22T00:00:00Z",
                ingest_run_id="test_run",
            )
            plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False), encoding="utf-8")

            result = write_yfinance_storage_review(plan_path, review_path)
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            sql_text = result.dry_run_sql_path.read_text(encoding="utf-8") if result.dry_run_sql_path else ""

        self.assertEqual("mysql_timeseries_table", result.storage_target)
        self.assertEqual("yfinance_storage_review", review_payload["kind"])
        self.assertTrue(review_payload["dry_run"])
        self.assertEqual(False, review_payload["execution_guard"]["will_write_database"])
        self.assertEqual("mysql_timeseries_table", review_payload["target"]["key"])
        self.assertEqual("mysql_timeseries_table", review_payload["storage_policy"]["review_target"])
        self.assertIn("CREATE TABLE IF NOT EXISTS", sql_text)
        self.assertIn("LOAD DATA LOCAL INFILE", sql_text)

    def test_storage_review_target_override_can_prepare_clickhouse_sql(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "live.csv"
            csv_path.write_text("event_time,symbol\n", encoding="utf-8")
            plan_payload = build_yfinance_live_plan(
                csv_path,
                symbols=("AAPL",),
                storage_target="sqlite_mvp_table",
            )
            review_payload = build_yfinance_storage_review(
                plan_payload,
                plan_path=Path(tmpdir) / "live_plan.json",
                storage_target="clickhouse_ohlcv_table",
            )

        self.assertEqual("clickhouse_ohlcv_table", review_payload["target"]["key"])
        self.assertEqual("clickhouse_ohlcv_table", review_payload["storage_policy"]["review_target"])
        self.assertEqual(False, review_payload["execution_guard"]["will_connect_to_database"])
        self.assertIn("ENGINE = MergeTree", review_payload["dry_run_sql"])

    def test_cli_writes_yfinance_storage_review_from_existing_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            csv_path = root / "live.csv"
            plan_path = root / "live_plan.json"
            review_path = root / "review.json"
            sql_path = root / "review.sql"
            csv_path.write_text("event_time,symbol\n", encoding="utf-8")
            plan_payload = build_yfinance_live_plan(
                csv_path,
                symbols=("AAPL",),
                storage_target="mysql_timeseries_table",
            )
            plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--write-yfinance-storage-review",
                        str(review_path),
                        "--yfinance-storage-review-plan",
                        str(plan_path),
                        "--write-yfinance-storage-review-sql",
                        str(sql_path),
                    ]
                )

            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            sql_exists = sql_path.exists()

        self.assertEqual(0, rc)
        self.assertTrue(sql_exists)
        self.assertIn("[yfinance-storage-review] wrote", output.getvalue())
        self.assertEqual("mysql_timeseries_table", review_payload["target"]["key"])

    def test_query_window_preset_normalization_is_bounded(self) -> None:
        self.assertEqual("intraday_5d_5m", normalize_yfinance_query_window_preset("intraday-5d-5m").key)
        with self.assertRaises(ValueError):
            normalize_yfinance_query_window_preset("background-live")

    def test_retention_days_are_bounded_for_live_plan_metadata(self) -> None:
        self.assertEqual(DEFAULT_YFINANCE_RETENTION_DAYS, normalize_yfinance_retention_days(str(DEFAULT_YFINANCE_RETENTION_DAYS)))
        with self.assertRaises(ValueError):
            normalize_yfinance_retention_days(0)
        with self.assertRaises(ValueError):
            normalize_yfinance_retention_days(3651)

    def test_storage_target_normalization_is_bounded(self) -> None:
        self.assertEqual(DEFAULT_YFINANCE_STORAGE_TARGET, normalize_yfinance_storage_target(""))
        self.assertEqual("parquet_duckdb_archive", normalize_yfinance_storage_target("parquet-duckdb-archive"))
        with self.assertRaises(ValueError):
            normalize_yfinance_storage_target("direct-mysql-write-now")


class FakeYFinanceFrame:
    empty = False

    def iterrows(self):
        yield date(2026, 5, 21), FakeYFinanceRow(
            {
                ("AAPL", "Open"): 100.0,
                ("AAPL", "High"): 103.0,
                ("AAPL", "Low"): 99.0,
                ("AAPL", "Close"): 102.0,
                ("AAPL", "Adj Close"): 102.0,
                ("AAPL", "Volume"): 1_000_000.0,
                ("MSFT", "Open"): 210.0,
                ("MSFT", "High"): 212.0,
                ("MSFT", "Low"): 208.0,
                ("MSFT", "Close"): 211.0,
                ("MSFT", "Adj Close"): 211.0,
                ("MSFT", "Volume"): 2_000_000.0,
            }
        )
        yield date(2026, 5, 22), FakeYFinanceRow(
            {
                ("AAPL", "Open"): 101.0,
                ("AAPL", "High"): 104.0,
                ("AAPL", "Low"): 100.0,
                ("AAPL", "Close"): 103.0,
                ("AAPL", "Adj Close"): 103.0,
                ("AAPL", "Volume"): 1_100_000.0,
                ("MSFT", "Open"): 211.0,
                ("MSFT", "High"): 213.0,
                ("MSFT", "Low"): 209.0,
                ("MSFT", "Close"): 212.0,
                ("MSFT", "Adj Close"): 212.0,
                ("MSFT", "Volume"): 2_100_000.0,
            }
        )


class FakeYFinanceRow:
    def __init__(self, values: dict[object, object]) -> None:
        self.values = values

    def get(self, key: object, default: object = None) -> object:
        return self.values.get(key, default)


if __name__ == "__main__":
    unittest.main()
