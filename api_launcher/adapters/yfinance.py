from __future__ import annotations

import csv
import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from api_launcher.adapters.base import DatasetAdapter, dataset_uid
from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.models import Dataset, Provider
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry


YFINANCE_PROVIDER_ID = "yahoo_finance_yfinance"
YFINANCE_DOCS_URL = "https://ericpien.github.io/yfinance/index.html"
YFINANCE_DOWNLOAD_DOCS_URL = "https://ericpien.github.io/yfinance/reference/api/yfinance.download.html"
YFINANCE_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,31}$")
DEFAULT_YFINANCE_SYMBOLS = ("AAPL", "MSFT")
YFINANCE_DEMO_RECEIVED_AT = "2026-05-21T00:00:00Z"
YFINANCE_DEMO_INGEST_RUN_ID = "fixture_yfinance_demo_2026_05_21"


@dataclass(frozen=True)
class YFinanceDemoPlanResult:
    plan_path: Path
    fixture_path: Path
    symbols: tuple[str, ...]


class YFinanceMarketDataAdapter(DatasetAdapter):
    # yfinance 是非官方 client，不是授權資料庫；adapter 先暴露 query contract，不自動打 Yahoo。
    provider_id = YFINANCE_PROVIDER_ID

    def discover(self, provider: Provider, max_items: int | None = None) -> list[Dataset]:
        if provider.provider_id != self.provider_id:
            return []
        dataset = yfinance_query_template_dataset()
        return [dataset][:max_items]


def yfinance_provider() -> Provider:
    return Provider(
        provider_id=YFINANCE_PROVIDER_ID,
        name="Yahoo Finance via yfinance",
        owner="Yahoo Finance / yfinance open-source client",
        categories=("finance", "stocks", "market_data", "timeseries"),
        geographic_scope="global",
        docs_url=YFINANCE_DOCS_URL,
        api_base_url="yfinance://download",
        auth_type="optional_unofficial_personal_research_client",
        terms_url=YFINANCE_DOCS_URL,
        notes=(
            "Unofficial yfinance adapter candidate. Use only for personal/research workflows; "
            "do not treat Yahoo Finance data as redistribution-safe or commercial-source data."
        ),
    )


def yfinance_query_template_dataset() -> Dataset:
    # 這不是固定資料集，而是「使用者提供 symbols 後才能執行」的時間序列查詢模板。
    dataset_id = "yfinance_ohlcv_query_template"
    return Dataset(
        dataset_uid=dataset_uid(YFINANCE_PROVIDER_ID, dataset_id),
        provider_id=YFINANCE_PROVIDER_ID,
        dataset_id=dataset_id,
        title="Yahoo Finance via yfinance OHLCV query template",
        categories=("finance", "stocks", "market_data", "timeseries"),
        data_type="realtime_timeseries",
        native_format="yfinance_query",
        geographic_scope="global",
        temporal_coverage="rolling_market_history",
        landing_url=YFINANCE_DOCS_URL,
        api_url=yfinance_query_uri(DEFAULT_YFINANCE_SYMBOLS),
        version="query-template",
        metadata={
            "adapter": "YFinanceMarketDataAdapter",
            "official_status": "unofficial_client",
            "intended_use": "personal_research_only",
            "requires_opt_in_live_fetch": True,
            "requires_user_symbols": True,
            "do_not_make_hard_dependency": True,
            "data_family": "realtime_timeseries",
            "temporal_resolution": "1d_default",
            "update_strategy": "live_market_data",
            "dedupe_keys": ("symbol", "event_time", "interval", "ingest_run_id"),
            "required_fields": (
                "event_time",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "received_at",
                "ingest_run_id",
            ),
            "source_docs_url": YFINANCE_DOWNLOAD_DOCS_URL,
            "available_versions": [
                {
                    "label": "Daily OHLCV query template",
                    "version": "query-template",
                    "version_status": "adapter_required",
                    "download_url": yfinance_query_uri(DEFAULT_YFINANCE_SYMBOLS),
                    "landing_url": YFINANCE_DOCS_URL,
                    "update_strategy": "live_market_data",
                    "native_format": "yfinance_query",
                    "notes": "Requires an explicit yfinance adapter execution step before any live Yahoo data is fetched.",
                }
            ],
            "notes": (
                "This template keeps yfinance out of CI and base dependencies. "
                "Use fixture-backed plans for tests; live fetch must be explicit and separately documented."
            ),
        },
    )


def write_yfinance_demo_plan(
    plan_path: str | Path,
    symbols: Iterable[str] = DEFAULT_YFINANCE_SYMBOLS,
    downloads_root: str | Path = "downloads",
) -> YFinanceDemoPlanResult:
    normalized_symbols = normalize_yfinance_symbols(symbols)
    output_path = Path(plan_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path = output_path.with_name(f"{output_path.stem}.fixture.csv")
    write_yfinance_fixture_csv(fixture_path, normalized_symbols)
    payload = build_yfinance_demo_plan(fixture_path, normalized_symbols, downloads_root=downloads_root)
    output_path.write_text(plan_payload_json(payload), encoding="utf-8")
    return YFinanceDemoPlanResult(plan_path=output_path, fixture_path=fixture_path, symbols=normalized_symbols)


def build_yfinance_demo_plan(
    fixture_path: str | Path,
    symbols: Iterable[str] = DEFAULT_YFINANCE_SYMBOLS,
    downloads_root: str | Path = "downloads",
) -> dict[str, object]:
    normalized_symbols = normalize_yfinance_symbols(symbols)
    fixture = Path(fixture_path)
    provider = yfinance_provider()
    dataset = yfinance_fixture_dataset(normalized_symbols, fixture)
    option = DatasetVersionOption(
        dataset_uid=dataset.dataset_uid,
        dataset_id=dataset.dataset_id,
        label=f"Offline OHLCV fixture ({', '.join(normalized_symbols)})",
        version="offline-fixture-2026-05-21",
        status="fixture",
        download_url=fixture.resolve().as_uri(),
        landing_url=YFINANCE_DOCS_URL,
        update_strategy="append_only_timeseries_fixture",
        notes="Offline fixture for validating financial time-series download/import without live Yahoo requests.",
        metadata={
            "native_format": "csv",
            "source_format": "csv",
            "adapter": "YFinanceMarketDataAdapter",
            "official_status": "unofficial_client_fixture",
            "intended_use": "personal_research_only",
            "symbols": normalized_symbols,
            "interval": "1d",
            "period": "fixture",
            "fixture_only": True,
        },
    )
    entry = provider_dataset_version_plan_entry(provider, dataset, option, downloads_root=downloads_root)
    # 金融資料的 closed-loop 驗收要保留時間序列欄位契約，避免日後被當成靜態版本檔。
    entry["time_series_contract"] = {
        "kind": "append_only_or_revisable_market_data",
        "event_time_column": "event_time",
        "received_at_column": "received_at",
        "ingest_run_id_column": "ingest_run_id",
        "symbol_column": "symbol",
        "revision_column": "revision",
        "source_sequence_column": "source_sequence",
        "symbols": list(normalized_symbols),
        "interval": "1d",
    }
    payload = build_dataset_download_plan([entry], plan_name="yfinance_offline_ohlcv_demo")
    payload["source"] = {
        "kind": "yfinance_offline_fixture",
        "provider_id": YFINANCE_PROVIDER_ID,
        "symbols": list(normalized_symbols),
        "fixture_path": fixture.as_posix(),
        "warning": "Fixture-only plan. Live yfinance fetch must remain explicit opt-in and outside CI.",
        "docs_url": YFINANCE_DOCS_URL,
    }
    return payload


def yfinance_fixture_dataset(symbols: tuple[str, ...], fixture_path: Path) -> Dataset:
    dataset_id = yfinance_fixture_dataset_id(symbols)
    return Dataset(
        dataset_uid=dataset_uid(YFINANCE_PROVIDER_ID, dataset_id),
        provider_id=YFINANCE_PROVIDER_ID,
        dataset_id=dataset_id,
        title=f"Yahoo Finance via yfinance offline OHLCV fixture ({', '.join(symbols)})",
        categories=("finance", "stocks", "market_data", "timeseries"),
        data_type="realtime_timeseries",
        native_format="csv",
        geographic_scope="global",
        temporal_coverage="fixture_2026-05-18_to_2026-05-20",
        landing_url=YFINANCE_DOCS_URL,
        api_url=fixture_path.resolve().as_uri(),
        version="offline-fixture-2026-05-21",
        metadata={
            "adapter": "YFinanceMarketDataAdapter",
            "official_status": "unofficial_client_fixture",
            "data_family": "realtime_timeseries",
            "temporal_resolution": "1d",
            "update_strategy": "append_only_timeseries_fixture",
            "dedupe_keys": ("symbol", "event_time", "ingest_run_id"),
            "symbols": symbols,
            "download_url": fixture_path.resolve().as_uri(),
            "source_format": "csv",
            "fixture_only": True,
        },
    )


def write_yfinance_fixture_csv(path: str | Path, symbols: Iterable[str] = DEFAULT_YFINANCE_SYMBOLS) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "event_time",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "received_at",
        "ingest_run_id",
        "source_sequence",
        "revision",
    )
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(yfinance_fixture_rows(normalize_yfinance_symbols(symbols)))
    return output


def yfinance_fixture_rows(symbols: tuple[str, ...]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    dates = ("2026-05-18", "2026-05-19", "2026-05-20")
    for symbol_index, symbol in enumerate(symbols, start=1):
        base_price = 90 + symbol_index * 35
        for day_index, day in enumerate(dates, start=1):
            open_price = base_price + day_index
            rows.append(
                {
                    "event_time": f"{day}T00:00:00Z",
                    "symbol": symbol,
                    "open": f"{open_price:.2f}",
                    "high": f"{open_price + 2.5:.2f}",
                    "low": f"{open_price - 1.5:.2f}",
                    "close": f"{open_price + 0.75:.2f}",
                    "adj_close": f"{open_price + 0.70:.2f}",
                    "volume": str(1_000_000 * symbol_index + day_index * 10_000),
                    "received_at": YFINANCE_DEMO_RECEIVED_AT,
                    "ingest_run_id": YFINANCE_DEMO_INGEST_RUN_ID,
                    "source_sequence": day_index,
                    "revision": "0",
                }
            )
    return rows


def normalize_yfinance_symbols(symbols: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw_symbol in symbols:
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        if not YFINANCE_SYMBOL_RE.match(symbol):
            raise ValueError(f"Unsupported yfinance symbol for demo plan: {raw_symbol!r}")
        if symbol not in normalized:
            normalized.append(symbol)
    return tuple(normalized or DEFAULT_YFINANCE_SYMBOLS)


def yfinance_query_uri(symbols: Iterable[str], period: str = "1mo", interval: str = "1d") -> str:
    normalized_symbols = normalize_yfinance_symbols(symbols)
    query = urllib.parse.urlencode(
        {
            "symbols": ",".join(normalized_symbols),
            "period": period,
            "interval": interval,
            "auto_adjust": "false",
        }
    )
    return f"yfinance://download?{query}"


def yfinance_fixture_dataset_id(symbols: tuple[str, ...]) -> str:
    symbol_part = "_".join(re.sub(r"[^0-9A-Z]+", "_", symbol).strip("_").lower() for symbol in symbols)
    return f"yfinance_ohlcv_fixture_{symbol_part or 'symbols'}"


def plan_payload_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
