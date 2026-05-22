from __future__ import annotations

import csv
import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from api_launcher.adapters.base import DatasetAdapter, dataset_uid
from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.models import Dataset, Provider
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry


YFINANCE_PROVIDER_ID = "yahoo_finance_yfinance"
YFINANCE_DOCS_URL = "https://ericpien.github.io/yfinance/index.html"
YFINANCE_DOWNLOAD_DOCS_URL = "https://ericpien.github.io/yfinance/reference/api/yfinance.download.html"
YFINANCE_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,31}$")
YFINANCE_PERIOD_RE = re.compile(r"^(?:[1-9][0-9]*(?:d|wk|mo|y)|ytd|max)$")
YFINANCE_INTERVAL_RE = re.compile(r"^(?:[1-9][0-9]*(?:m|h|d|wk|mo))$")
DEFAULT_YFINANCE_SYMBOLS = ("AAPL", "MSFT")
DEFAULT_YFINANCE_RETENTION_DAYS = 365
MIN_YFINANCE_RETENTION_DAYS = 1
MAX_YFINANCE_RETENTION_DAYS = 3650
YFINANCE_DEMO_RECEIVED_AT = "2026-05-21T00:00:00Z"
YFINANCE_DEMO_INGEST_RUN_ID = "fixture_yfinance_demo_2026_05_21"
YFINANCE_LIVE_WARNING = (
    "Yahoo Finance via yfinance is an unofficial client path for personal/research workflows only. "
    "Review Yahoo/yfinance terms yourself before use; do not treat fetched data as redistribution-safe."
)
YFINANCE_CSV_FIELDNAMES = (
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


@dataclass(frozen=True)
class YFinanceDemoPlanResult:
    plan_path: Path
    fixture_path: Path
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class YFinanceLivePlanResult:
    plan_path: Path
    csv_path: Path
    symbols: tuple[str, ...]
    rows_written: int
    period: str
    interval: str
    retention_days: int
    warning: str = YFINANCE_LIVE_WARNING


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


def write_yfinance_live_plan(
    plan_path: str | Path,
    symbols: Iterable[str] = DEFAULT_YFINANCE_SYMBOLS,
    period: str = "1mo",
    interval: str = "1d",
    downloads_root: str | Path = "downloads",
    retention_days: int = DEFAULT_YFINANCE_RETENTION_DAYS,
    *,
    acknowledge_unofficial: bool = False,
    fetcher: Callable[[tuple[str, ...], str, str], object] | None = None,
    received_at: str | None = None,
    ingest_run_id: str | None = None,
) -> YFinanceLivePlanResult:
    # live fetch 只允許在呼叫端明確 opt-in 後執行，避免 discovery/CI/背景流程偷打 Yahoo。
    if not acknowledge_unofficial:
        raise ValueError(
            "Live yfinance fetch is unofficial and personal/research-only. "
            "Pass --yfinance-acknowledge-unofficial only after reviewing the warning and provider terms."
        )
    normalized_symbols = normalize_yfinance_symbols(symbols)
    normalized_period = normalize_yfinance_period(period)
    normalized_interval = normalize_yfinance_interval(interval)
    normalized_retention_days = normalize_yfinance_retention_days(retention_days)
    output_path = Path(plan_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = output_path.with_name(f"{output_path.stem}.live.csv")
    received_at_value = received_at or _utc_now_iso()
    ingest_id = ingest_run_id or _yfinance_live_ingest_run_id(normalized_symbols, normalized_period, normalized_interval, received_at_value)
    frame = (fetcher or _download_yfinance_frame)(normalized_symbols, normalized_period, normalized_interval)
    rows = yfinance_live_rows_from_frame(
        frame,
        normalized_symbols,
        received_at=received_at_value,
        ingest_run_id=ingest_id,
    )
    write_yfinance_rows_csv(csv_path, rows)
    payload = build_yfinance_live_plan(
        csv_path,
        normalized_symbols,
        period=normalized_period,
        interval=normalized_interval,
        downloads_root=downloads_root,
        retention_days=normalized_retention_days,
        received_at=received_at_value,
        ingest_run_id=ingest_id,
    )
    output_path.write_text(plan_payload_json(payload), encoding="utf-8")
    return YFinanceLivePlanResult(
        plan_path=output_path,
        csv_path=csv_path,
        symbols=normalized_symbols,
        rows_written=len(rows),
        period=normalized_period,
        interval=normalized_interval,
        retention_days=normalized_retention_days,
    )


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


def build_yfinance_live_plan(
    csv_path: str | Path,
    symbols: Iterable[str] = DEFAULT_YFINANCE_SYMBOLS,
    period: str = "1mo",
    interval: str = "1d",
    downloads_root: str | Path = "downloads",
    retention_days: int = DEFAULT_YFINANCE_RETENTION_DAYS,
    received_at: str = "",
    ingest_run_id: str = "",
) -> dict[str, object]:
    normalized_symbols = normalize_yfinance_symbols(symbols)
    normalized_period = normalize_yfinance_period(period)
    normalized_interval = normalize_yfinance_interval(interval)
    normalized_retention_days = normalize_yfinance_retention_days(retention_days)
    csv_file = Path(csv_path)
    provider = yfinance_provider()
    dataset = yfinance_live_dataset(
        normalized_symbols,
        csv_file,
        normalized_period,
        normalized_interval,
        normalized_retention_days,
    )
    retention_policy = yfinance_retention_policy(normalized_retention_days)
    option = DatasetVersionOption(
        dataset_uid=dataset.dataset_uid,
        dataset_id=dataset.dataset_id,
        label=f"Live OHLCV CSV ({', '.join(normalized_symbols)} / {normalized_period} / {normalized_interval})",
        version=f"live-{normalized_period}-{normalized_interval}",
        status="live_csv",
        download_url=csv_file.resolve().as_uri(),
        landing_url=YFINANCE_DOCS_URL,
        update_strategy="append_only_or_revisable_market_data",
        notes="Explicit opt-in yfinance live CSV output; review provider terms before use.",
        metadata={
            "native_format": "csv",
            "source_format": "csv",
            "adapter": "YFinanceMarketDataAdapter",
            "official_status": "unofficial_client_live_opt_in",
            "intended_use": "personal_research_only",
            "symbols": normalized_symbols,
            "interval": normalized_interval,
            "period": normalized_period,
            "received_at": received_at,
            "ingest_run_id": ingest_run_id,
            "live_fetch": True,
            "retention_policy": retention_policy,
        },
    )
    entry = provider_dataset_version_plan_entry(provider, dataset, option, downloads_root=downloads_root)
    entry["time_series_contract"] = {
        "kind": "append_only_or_revisable_market_data",
        "event_time_column": "event_time",
        "received_at_column": "received_at",
        "ingest_run_id_column": "ingest_run_id",
        "symbol_column": "symbol",
        "revision_column": "revision",
        "source_sequence_column": "source_sequence",
        "symbols": list(normalized_symbols),
        "period": normalized_period,
        "interval": normalized_interval,
        "retention_policy": retention_policy,
    }
    payload = build_dataset_download_plan([entry], plan_name="yfinance_live_ohlcv_opt_in")
    payload["source"] = {
        "kind": "yfinance_live_csv",
        "provider_id": YFINANCE_PROVIDER_ID,
        "symbols": list(normalized_symbols),
        "period": normalized_period,
        "interval": normalized_interval,
        "csv_path": csv_file.as_posix(),
        "warning": YFINANCE_LIVE_WARNING,
        "docs_url": YFINANCE_DOCS_URL,
        "received_at": received_at,
        "ingest_run_id": ingest_run_id,
        "retention_policy": retention_policy,
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


def yfinance_live_dataset(
    symbols: tuple[str, ...],
    csv_path: Path,
    period: str,
    interval: str,
    retention_days: int,
) -> Dataset:
    # live CSV 被視為「使用者剛剛明確抓取的 raw asset」，不是可自由散布的官方資料集版本。
    dataset_id = f"yfinance_ohlcv_live_{'_'.join(_safe_symbol_slug(symbol) for symbol in symbols)}"
    retention_policy = yfinance_retention_policy(retention_days)
    return Dataset(
        dataset_uid=dataset_uid(YFINANCE_PROVIDER_ID, dataset_id),
        provider_id=YFINANCE_PROVIDER_ID,
        dataset_id=dataset_id,
        title=f"Yahoo Finance via yfinance live OHLCV CSV ({', '.join(symbols)})",
        categories=("finance", "stocks", "market_data", "timeseries"),
        data_type="realtime_timeseries",
        native_format="csv",
        geographic_scope="global",
        temporal_coverage=f"live_query_{period}_{interval}",
        landing_url=YFINANCE_DOCS_URL,
        api_url=yfinance_query_uri(symbols, period=period, interval=interval),
        version=f"live-{period}-{interval}",
        metadata={
            "adapter": "YFinanceMarketDataAdapter",
            "official_status": "unofficial_client_live_opt_in",
            "data_family": "realtime_timeseries",
            "temporal_resolution": interval,
            "update_strategy": "append_only_or_revisable_market_data",
            "dedupe_keys": ("symbol", "event_time", "ingest_run_id"),
            "symbols": symbols,
            "period": period,
            "interval": interval,
            "download_url": csv_path.resolve().as_uri(),
            "source_format": "csv",
            "live_fetch": True,
            "retention_policy": retention_policy,
        },
    )


def write_yfinance_fixture_csv(path: str | Path, symbols: Iterable[str] = DEFAULT_YFINANCE_SYMBOLS) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=YFINANCE_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(yfinance_fixture_rows(normalize_yfinance_symbols(symbols)))
    return output


def write_yfinance_rows_csv(path: str | Path, rows: list[dict[str, object]]) -> Path:
    if not rows:
        raise ValueError("yfinance returned no rows for the requested symbols/period/interval.")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=YFINANCE_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
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


def yfinance_live_rows_from_frame(frame: object, symbols: tuple[str, ...], received_at: str, ingest_run_id: str) -> list[dict[str, object]]:
    # 這裡只把 yfinance/pandas 常見 OHLCV shape 攤平成穩定 CSV；缺欄位就留空，不猜測欄位語意。
    if bool(getattr(frame, "empty", False)):
        raise ValueError("yfinance returned an empty result.")
    iterrows = getattr(frame, "iterrows", None)
    if not callable(iterrows):
        raise ValueError("yfinance result does not look like a tabular frame.")
    rows: list[dict[str, object]] = []
    sequence_by_symbol = {symbol: 0 for symbol in symbols}
    single_symbol = len(symbols) == 1
    for timestamp, row in iterrows():
        event_time = _yfinance_event_time(timestamp)
        for symbol in symbols:
            values = {
                "open": _yfinance_row_value(row, symbol, ("Open", "open"), single_symbol=single_symbol),
                "high": _yfinance_row_value(row, symbol, ("High", "high"), single_symbol=single_symbol),
                "low": _yfinance_row_value(row, symbol, ("Low", "low"), single_symbol=single_symbol),
                "close": _yfinance_row_value(row, symbol, ("Close", "close"), single_symbol=single_symbol),
                "adj_close": _yfinance_row_value(row, symbol, ("Adj Close", "AdjClose", "adj_close"), single_symbol=single_symbol),
                "volume": _yfinance_row_value(row, symbol, ("Volume", "volume"), single_symbol=single_symbol),
            }
            if not any(values.values()):
                continue
            sequence_by_symbol[symbol] += 1
            rows.append(
                {
                    "event_time": event_time,
                    "symbol": symbol,
                    **values,
                    "received_at": received_at,
                    "ingest_run_id": ingest_run_id,
                    "source_sequence": sequence_by_symbol[symbol],
                    "revision": "0",
                }
            )
    if not rows:
        raise ValueError("yfinance result did not contain OHLCV rows for the requested symbols.")
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


def normalize_yfinance_period(period: str) -> str:
    value = str(period or "").strip().lower()
    if not YFINANCE_PERIOD_RE.match(value):
        raise ValueError(f"Unsupported yfinance period: {period!r}")
    return value


def normalize_yfinance_interval(interval: str) -> str:
    value = str(interval or "").strip().lower()
    if not YFINANCE_INTERVAL_RE.match(value):
        raise ValueError(f"Unsupported yfinance interval: {interval!r}")
    return value


def normalize_yfinance_retention_days(retention_days: int | str) -> int:
    # retention 是本機治理 metadata，不會自動刪檔；先把範圍收斂，避免 plan 記錄無界快取承諾。
    try:
        value = int(retention_days)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported yfinance retention days: {retention_days!r}") from exc
    if value < MIN_YFINANCE_RETENTION_DAYS or value > MAX_YFINANCE_RETENTION_DAYS:
        raise ValueError(
            "Unsupported yfinance retention days: "
            f"{retention_days!r}; expected {MIN_YFINANCE_RETENTION_DAYS}-{MAX_YFINANCE_RETENTION_DAYS}."
        )
    return value


def yfinance_retention_policy(retention_days: int) -> dict[str, object]:
    normalized_days = normalize_yfinance_retention_days(retention_days)
    return {
        "retention_days": normalized_days,
        "scope": "local_personal_research_cache",
        "automatic_delete": False,
        "background_refresh": False,
        "notes": "Retention is metadata for local cache governance; the launcher does not delete files automatically.",
    }


def yfinance_query_uri(symbols: Iterable[str], period: str = "1mo", interval: str = "1d") -> str:
    normalized_symbols = normalize_yfinance_symbols(symbols)
    normalized_period = normalize_yfinance_period(period)
    normalized_interval = normalize_yfinance_interval(interval)
    query = urllib.parse.urlencode(
        {
            "symbols": ",".join(normalized_symbols),
            "period": normalized_period,
            "interval": normalized_interval,
            "auto_adjust": "false",
        }
    )
    return f"yfinance://download?{query}"


def yfinance_fixture_dataset_id(symbols: tuple[str, ...]) -> str:
    symbol_part = "_".join(_safe_symbol_slug(symbol) for symbol in symbols)
    return f"yfinance_ohlcv_fixture_{symbol_part or 'symbols'}"


def _download_yfinance_frame(symbols: tuple[str, ...], period: str, interval: str) -> object:
    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "The optional 'yfinance' package is not installed in this Python environment. "
            "Install it only in the project environment if you intend to use live Yahoo Finance fetches."
        ) from exc
    # group_by=ticker 讓多 ticker 回傳可以用 (symbol, field) 讀取；threads=False 讓手動執行更可重現。
    return yf.download(
        tickers=" ".join(symbols),
        period=period,
        interval=interval,
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=False,
    )


def _yfinance_row_value(row: object, symbol: str, field_names: tuple[str, ...], *, single_symbol: bool) -> str:
    keys: list[object] = []
    if not single_symbol:
        for field_name in field_names:
            keys.append((symbol, field_name))
            keys.append((field_name, symbol))
    keys.extend(field_names)
    getter = getattr(row, "get", None)
    for key in keys:
        if not callable(getter):
            break
        value = getter(key, None)
        formatted = _format_yfinance_csv_value(value)
        if formatted:
            return formatted
    return ""


def _format_yfinance_csv_value(value: object) -> str:
    if value is None:
        return ""
    with_nan_guard = value
    try:
        if with_nan_guard != with_nan_guard:
            return ""
    except Exception:
        pass
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.8f}".rstrip("0").rstrip(".")
    return str(value)


def _yfinance_event_time(value: object) -> str:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, date):
        timestamp = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    else:
        text = str(value)
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return f"{text}T00:00:00Z"
        return text
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _yfinance_live_ingest_run_id(symbols: tuple[str, ...], period: str, interval: str, received_at: str) -> str:
    timestamp = re.sub(r"[^0-9A-Za-z]+", "_", received_at).strip("_").lower()
    symbol_part = "_".join(_safe_symbol_slug(symbol) for symbol in symbols)
    return f"yfinance_live_{symbol_part}_{period}_{interval}_{timestamp}"


def _safe_symbol_slug(symbol: str) -> str:
    return re.sub(r"[^0-9A-Z]+", "_", symbol).strip("_").lower()


def plan_payload_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
