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
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry, sql_table_hint
from api_launcher.sql_assets import validate_sql_identifier


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
DEFAULT_YFINANCE_QUERY_WINDOW_PRESET = "daily_1mo"
DEFAULT_YFINANCE_STORAGE_TARGET = "auto"
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
    query_window_preset: str = ""
    storage_target: str = DEFAULT_YFINANCE_STORAGE_TARGET
    warning: str = YFINANCE_LIVE_WARNING


@dataclass(frozen=True)
class YFinanceStorageReviewResult:
    review_path: Path
    plan_path: Path
    storage_target: str
    dry_run_sql_path: Path | None
    action_count: int


@dataclass(frozen=True)
class YFinanceStorageHandoffResult:
    handoff_path: Path
    review_path: Path
    storage_target: str
    dry_run_sql_path: Path | None
    action_count: int


@dataclass(frozen=True)
class YFinanceQueryWindowPreset:
    key: str
    label: str
    period: str
    interval: str
    chart_profile: str
    storage_hint: str
    notes: str


@dataclass(frozen=True)
class YFinanceStorageTargetProfile:
    key: str
    label: str
    engine: str
    asset_role: str
    table_shape: str
    recommended_for: str
    status: str
    notes: str


YFINANCE_QUERY_WINDOW_PRESETS: dict[str, YFinanceQueryWindowPreset] = {
    "intraday_5d_5m": YFinanceQueryWindowPreset(
        key="intraday_5d_5m",
        label="Intraday 5 days / 5 minute candles",
        period="5d",
        interval="5m",
        chart_profile="intraday_candles",
        storage_hint="short_horizon_sqlite_or_mysql_cache",
        notes="Good for UI smoke checks and short intraday chart previews; still requires explicit user fetch.",
    ),
    "daily_1mo": YFinanceQueryWindowPreset(
        key="daily_1mo",
        label="Daily 1 month",
        period="1mo",
        interval="1d",
        chart_profile="daily_candles",
        storage_hint="sqlite_or_mysql_mvp_table",
        notes="Default chart-friendly daily window for MVP download/import validation.",
    ),
    "daily_6mo": YFinanceQueryWindowPreset(
        key="daily_6mo",
        label="Daily 6 months",
        period="6mo",
        interval="1d",
        chart_profile="daily_candles_medium_horizon",
        storage_hint="mysql_or_parquet_duckdb_candidate",
        notes="Useful for medium-horizon chart review without moving into heavy tick storage.",
    ),
    "weekly_1y": YFinanceQueryWindowPreset(
        key="weekly_1y",
        label="Weekly 1 year",
        period="1y",
        interval="1wk",
        chart_profile="weekly_candles",
        storage_hint="sqlite_mysql_or_parquet_archive_candidate",
        notes="Lower-density long chart window for trend previews and storage-target planning.",
    ),
}


YFINANCE_STORAGE_TARGET_PROFILES: dict[str, YFinanceStorageTargetProfile] = {
    "sqlite_mvp_table": YFinanceStorageTargetProfile(
        key="sqlite_mvp_table",
        label="SQLite curated OHLCV table",
        engine="sqlite",
        asset_role="curated_table",
        table_shape="one_row_per_symbol_event_time",
        recommended_for="MVP fixture/live plan import and single-user validation.",
        status="mvp_supported_via_csv_import",
        notes="Uses the existing CSV-to-SQLite importer after the user explicitly runs download/import.",
    ),
    "mysql_timeseries_table": YFinanceStorageTargetProfile(
        key="mysql_timeseries_table",
        label="MySQL OHLCV table",
        engine="mysql",
        asset_role="curated_table",
        table_shape="one_row_per_symbol_event_time_with_ingest_run_id",
        recommended_for="Team-visible MVP storage when a configured MySQL profile exists.",
        status="metadata_only",
        notes="Records the target intent only; the launcher does not write MySQL tables from yfinance live plans yet.",
    ),
    "parquet_duckdb_archive": YFinanceStorageTargetProfile(
        key="parquet_duckdb_archive",
        label="Parquet / DuckDB analytical archive",
        engine="parquet_duckdb",
        asset_role="analysis_or_cache_asset",
        table_shape="partitionable_symbol_date_ohlcv",
        recommended_for="Medium-horizon local analytics and chart replay without committing to an always-on database.",
        status="planned_metadata_only",
        notes="Useful for later export/import planning; no Parquet writer is invoked by the current yfinance plan.",
    ),
    "timescaledb_hypertable": YFinanceStorageTargetProfile(
        key="timescaledb_hypertable",
        label="TimescaleDB / PostgreSQL hypertable",
        engine="timescaledb_postgresql",
        asset_role="timeseries_table",
        table_shape="hypertable_event_time_symbol",
        recommended_for="Future higher-volume append/backfill workflows.",
        status="planned_metadata_only",
        notes="Requires an explicit PostgreSQL/TimescaleDB execution path before it can mutate a remote database.",
    ),
    "clickhouse_ohlcv_table": YFinanceStorageTargetProfile(
        key="clickhouse_ohlcv_table",
        label="ClickHouse OHLCV columnar table",
        engine="clickhouse",
        asset_role="timeseries_columnar_table",
        table_shape="columnar_symbol_event_time_ohlcv",
        recommended_for="Future high-volume chart and aggregation workloads.",
        status="planned_metadata_only",
        notes="Kept as a target passport entry only; no ClickHouse dependency or writer is added.",
    ),
}


YFINANCE_QUERY_WINDOW_STORAGE_TARGETS: dict[str, tuple[str, ...]] = {
    "intraday_5d_5m": ("sqlite_mvp_table", "mysql_timeseries_table", "clickhouse_ohlcv_table"),
    "daily_1mo": ("sqlite_mvp_table", "mysql_timeseries_table", "parquet_duckdb_archive"),
    "daily_6mo": ("mysql_timeseries_table", "parquet_duckdb_archive", "timescaledb_hypertable"),
    "weekly_1y": ("parquet_duckdb_archive", "mysql_timeseries_table", "timescaledb_hypertable"),
}


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
            "default_query_window_preset": DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
            "query_window_presets": [yfinance_query_window_preset_metadata(preset) for preset in YFINANCE_QUERY_WINDOW_PRESETS.values()],
            "default_storage_target": DEFAULT_YFINANCE_STORAGE_TARGET,
            "storage_target_profiles": [
                yfinance_storage_target_profile_metadata(profile)
                for profile in YFINANCE_STORAGE_TARGET_PROFILES.values()
            ],
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
    period: str | None = None,
    interval: str | None = None,
    downloads_root: str | Path = "downloads",
    retention_days: int = DEFAULT_YFINANCE_RETENTION_DAYS,
    query_window_preset: str | None = DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
    storage_target: str | None = DEFAULT_YFINANCE_STORAGE_TARGET,
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
    query_window = yfinance_query_window_policy(period=period, interval=interval, query_window_preset=query_window_preset)
    storage_policy = yfinance_storage_target_policy(query_window=query_window, storage_target=storage_target)
    normalized_period = str(query_window["period"])
    normalized_interval = str(query_window["interval"])
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
        query_window_preset=str(query_window.get("preset_key") or ""),
        storage_target=str(storage_policy.get("selection") or DEFAULT_YFINANCE_STORAGE_TARGET),
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
        query_window_preset=str(query_window.get("preset_key") or ""),
        storage_target=str(storage_policy.get("selection") or DEFAULT_YFINANCE_STORAGE_TARGET),
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
    period: str | None = None,
    interval: str | None = None,
    downloads_root: str | Path = "downloads",
    retention_days: int = DEFAULT_YFINANCE_RETENTION_DAYS,
    query_window_preset: str | None = DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
    storage_target: str | None = DEFAULT_YFINANCE_STORAGE_TARGET,
    received_at: str = "",
    ingest_run_id: str = "",
) -> dict[str, object]:
    normalized_symbols = normalize_yfinance_symbols(symbols)
    query_window = yfinance_query_window_policy(period=period, interval=interval, query_window_preset=query_window_preset)
    storage_policy = yfinance_storage_target_policy(query_window=query_window, storage_target=storage_target)
    normalized_period = str(query_window["period"])
    normalized_interval = str(query_window["interval"])
    normalized_retention_days = normalize_yfinance_retention_days(retention_days)
    csv_file = Path(csv_path)
    provider = yfinance_provider()
    dataset = yfinance_live_dataset(
        normalized_symbols,
        csv_file,
        normalized_period,
        normalized_interval,
        normalized_retention_days,
        storage_policy=storage_policy,
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
            "query_window": query_window,
            "storage_policy": storage_policy,
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
        "query_window": query_window,
        "storage_policy": storage_policy,
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
        "query_window": query_window,
        "storage_policy": storage_policy,
    }
    return payload


def write_yfinance_storage_review(
    plan_path: str | Path,
    review_path: str | Path,
    *,
    storage_target: str | None = None,
    dry_run_sql_path: str | Path | None = None,
) -> YFinanceStorageReviewResult:
    source_plan = Path(plan_path)
    output_path = Path(review_path)
    payload = json.loads(source_plan.read_text(encoding="utf-8"))
    review = build_yfinance_storage_review(
        payload,
        plan_path=source_plan,
        review_path=output_path,
        storage_target=storage_target,
    )
    sql_text = str(review.get("dry_run_sql") or "")
    sql_output: Path | None = None
    if sql_text:
        sql_output = Path(dry_run_sql_path) if dry_run_sql_path else output_path.with_suffix(".dry_run.sql")
        sql_output.parent.mkdir(parents=True, exist_ok=True)
        sql_output.write_text(sql_text, encoding="utf-8", newline="\n")
        review["dry_run_sql_path"] = sql_output.as_posix()
        review["dry_run_sql"] = ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(plan_payload_json(review), encoding="utf-8")
    return YFinanceStorageReviewResult(
        review_path=output_path,
        plan_path=source_plan,
        storage_target=str(review["target"]["key"]),
        dry_run_sql_path=sql_output,
        action_count=len(review.get("review_actions", [])),
    )


def write_yfinance_storage_handoff(review_path: str | Path, handoff_path: str | Path) -> YFinanceStorageHandoffResult:
    source_review = Path(review_path)
    output_path = Path(handoff_path)
    review = json.loads(source_review.read_text(encoding="utf-8"))
    markdown = build_yfinance_storage_handoff_markdown(review, review_path=source_review)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8", newline="\n")
    target = review.get("target") if isinstance(review.get("target"), dict) else {}
    dry_run_sql = str(review.get("dry_run_sql_path") or "").strip()
    return YFinanceStorageHandoffResult(
        handoff_path=output_path,
        review_path=source_review,
        storage_target=str(target.get("key") or ""),
        dry_run_sql_path=Path(dry_run_sql) if dry_run_sql else None,
        action_count=len(review.get("review_actions", [])) if isinstance(review.get("review_actions"), list) else 0,
    )


def build_yfinance_storage_handoff_markdown(review_payload: dict[str, object], *, review_path: str | Path | None = None) -> str:
    # handoff Markdown 是給人類/DBA 審查的包裝層；它只重述 guard 與待審項，不產生任何可自動執行的批准動作。
    if review_payload.get("kind") != "yfinance_storage_review":
        raise ValueError("YFinance storage handoff expects a yfinance_storage_review JSON payload.")
    if review_payload.get("dry_run") is not True:
        raise ValueError("YFinance storage handoff only accepts dry-run review payloads.")
    target = review_payload.get("target") if isinstance(review_payload.get("target"), dict) else {}
    source = review_payload.get("source") if isinstance(review_payload.get("source"), dict) else {}
    table = review_payload.get("table") if isinstance(review_payload.get("table"), dict) else {}
    guard = review_payload.get("execution_guard") if isinstance(review_payload.get("execution_guard"), dict) else {}
    actions = review_payload.get("review_actions") if isinstance(review_payload.get("review_actions"), list) else []
    dry_run_sql_path = str(review_payload.get("dry_run_sql_path") or "").strip()
    symbols = source.get("symbols") if isinstance(source.get("symbols"), list) else []
    symbols_text = ", ".join(str(symbol) for symbol in symbols if symbol)
    lines = [
        "# yfinance 儲存審查交接",
        "",
        "> 這份文件是人工 / DBA 審查用 handoff。launcher 產生它時不會連線、不會建表、不會匯入，也不代表已經批准執行。",
        "",
        "## 審查摘要",
        "",
        f"- Review JSON：`{review_path or review_payload.get('review_path') or ''}`",
        f"- 目標：`{target.get('key') or ''}` / {target.get('label') or ''}",
        f"- Engine：`{target.get('engine') or ''}`",
        f"- 表格：`{table.get('name') or ''}`",
        f"- CSV 來源：`{source.get('csv_uri') or ''}`",
        f"- Symbols：`{symbols_text}`",
        f"- 查詢視窗：period=`{source.get('period') or ''}` interval=`{source.get('interval') or ''}`",
        f"- Dry-run SQL：`{dry_run_sql_path or '無，請看 next_command 或 SQLite import path'}`",
        "",
        "## 執行 guard",
        "",
        f"- will_connect_to_database：`{bool(guard.get('will_connect_to_database'))}`",
        f"- will_write_database：`{bool(guard.get('will_write_database'))}`",
        f"- will_create_table：`{bool(guard.get('will_create_table'))}`",
        f"- will_import_rows：`{bool(guard.get('will_import_rows'))}`",
        f"- requires_user_review：`{bool(guard.get('requires_user_review'))}`",
        f"- requires_separate_execution：`{bool(guard.get('requires_separate_execution'))}`",
        "",
        "## 審查清單",
        "",
    ]
    for action in actions:
        if not isinstance(action, dict):
            continue
        lines.append(
            "- [ ] "
            f"{action.get('action') or 'review'} "
            f"({action.get('status') or 'required'})：{action.get('notes') or ''}"
        )
    lines.extend(
        [
            "",
            "## 下一步邊界",
            "",
            "- 若目標是 SQLite，仍走既有 `--run-download-plan ... --import-supported-plan-results` 路徑。",
            "- 若目標是 MySQL、TimescaleDB/PostgreSQL、ClickHouse 或 Parquet/DuckDB，必須先完成條款、schema、rollback、credential 與 ownership 審查。",
            "- 任何真正連線、建表、匯入或排程都應該是另一個明確 opt-in 的執行命令，不應由這份 handoff 自動觸發。",
            "",
        ]
    )
    next_command = review_payload.get("next_command")
    if next_command:
        lines.extend(["## 參考 next_command", "", "```text", json.dumps(next_command, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def build_yfinance_storage_review(
    plan_payload: dict[str, object],
    *,
    plan_path: str | Path | None = None,
    review_path: str | Path | None = None,
    storage_target: str | None = None,
) -> dict[str, object]:
    # 這個 review 是 metadata -> 人工審查 -> 明確執行 的中間層；它刻意不觸發任何資料庫連線。
    entry = _single_yfinance_plan_entry(plan_payload)
    source = plan_payload.get("source") if isinstance(plan_payload.get("source"), dict) else {}
    contract = entry.get("time_series_contract") if isinstance(entry.get("time_series_contract"), dict) else {}
    import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
    dataset_version = entry.get("dataset_version") if isinstance(entry.get("dataset_version"), dict) else {}
    storage_policy = _yfinance_review_storage_policy(source, contract, storage_target)
    target_key = str(storage_policy.get("review_target") or storage_policy.get("recommended_target") or "sqlite_mvp_table")
    profile = YFINANCE_STORAGE_TARGET_PROFILES[target_key]
    table_name = sql_table_hint(str(import_plan.get("table_hint") or "yfinance_ohlcv"))
    csv_uri = str(source.get("csv_path") or entry.get("download_url") or "")
    sql_text = _yfinance_storage_review_sql(profile, table_name, csv_uri)
    command = _yfinance_review_command(plan_path, profile, table_name)
    return {
        "kind": "yfinance_storage_review",
        "schema_version": 1,
        "dry_run": True,
        "plan_path": str(plan_path or ""),
        "review_path": str(review_path or ""),
        "review_status": "requires_human_review",
        "source_warning": YFINANCE_LIVE_WARNING,
        "source": {
            "kind": source.get("kind") or "yfinance_plan",
            "provider_id": source.get("provider_id") or YFINANCE_PROVIDER_ID,
            "symbols": list(source.get("symbols") or contract.get("symbols") or []),
            "period": source.get("period") or contract.get("period") or "",
            "interval": source.get("interval") or contract.get("interval") or "",
            "csv_uri": csv_uri,
            "received_at": source.get("received_at") or "",
            "ingest_run_id": source.get("ingest_run_id") or "",
        },
        "dataset": {
            "provider_id": entry.get("provider_id") or YFINANCE_PROVIDER_ID,
            "dataset_id": entry.get("dataset_id") or dataset_version.get("dataset_id") or "",
            "dataset_uid": entry.get("dataset_uid") or dataset_version.get("dataset_uid") or "",
            "version": dataset_version.get("version") or entry.get("version") or "",
        },
        "target": yfinance_storage_target_profile_metadata(profile),
        "storage_policy": storage_policy,
        "table": {
            "name": table_name,
            "shape": profile.table_shape,
            "dedupe_keys": ["symbol", "event_time", "ingest_run_id"],
            "columns": _yfinance_storage_review_columns(profile.engine),
        },
        "execution_guard": {
            "will_connect_to_database": False,
            "will_write_database": False,
            "will_create_table": False,
            "will_import_rows": False,
            "requires_user_review": True,
            "requires_separate_execution": True,
        },
        "review_actions": [
            {
                "step": 1,
                "action": "review_terms_and_license",
                "status": "required",
                "notes": "確認 Yahoo/yfinance 條款與 personal/research-only 邊界後，才進入任何實際匯出或匯入。",
            },
            {
                "step": 2,
                "action": "verify_source_csv_manifest",
                "status": "required",
                "notes": "先用既有 download/manifest flow 驗證 CSV，避免直接把未驗證檔案寫入資料庫。",
            },
            {
                "step": 3,
                "action": "review_storage_target",
                "status": "dry_run_only",
                "target": profile.key,
                "notes": "本檔只列出目標 schema、命令或 SQL 草稿，不會自動執行。",
            },
        ],
        "next_command": command,
        "dry_run_sql": sql_text,
    }


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
    storage_policy: dict[str, object] | None = None,
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
            "storage_policy": storage_policy or yfinance_storage_target_policy(
                query_window=yfinance_query_window_policy(period=period, interval=interval),
            ),
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


def normalize_yfinance_query_window_preset(preset: str | None) -> YFinanceQueryWindowPreset | None:
    value = str(preset or "").strip().lower().replace("-", "_")
    if not value:
        return None
    if value not in YFINANCE_QUERY_WINDOW_PRESETS:
        allowed = ", ".join(sorted(YFINANCE_QUERY_WINDOW_PRESETS))
        raise ValueError(f"Unsupported yfinance query window preset: {preset!r}; expected one of: {allowed}.")
    return YFINANCE_QUERY_WINDOW_PRESETS[value]


def yfinance_query_window_preset_metadata(preset: YFinanceQueryWindowPreset) -> dict[str, str]:
    return {
        "preset_key": preset.key,
        "label": preset.label,
        "period": preset.period,
        "interval": preset.interval,
        "chart_profile": preset.chart_profile,
        "storage_hint": preset.storage_hint,
        "notes": preset.notes,
    }


def normalize_yfinance_storage_target(storage_target: str | None) -> str:
    value = str(storage_target or DEFAULT_YFINANCE_STORAGE_TARGET).strip().lower().replace("-", "_")
    if not value:
        return DEFAULT_YFINANCE_STORAGE_TARGET
    if value == DEFAULT_YFINANCE_STORAGE_TARGET:
        return value
    if value not in YFINANCE_STORAGE_TARGET_PROFILES:
        allowed = ", ".join([DEFAULT_YFINANCE_STORAGE_TARGET, *sorted(YFINANCE_STORAGE_TARGET_PROFILES)])
        raise ValueError(f"Unsupported yfinance storage target: {storage_target!r}; expected one of: {allowed}.")
    return value


def yfinance_storage_target_profile_metadata(profile: YFinanceStorageTargetProfile) -> dict[str, object]:
    return {
        "key": profile.key,
        "label": profile.label,
        "engine": profile.engine,
        "asset_role": profile.asset_role,
        "table_shape": profile.table_shape,
        "recommended_for": profile.recommended_for,
        "status": profile.status,
        "notes": profile.notes,
    }


def yfinance_storage_target_policy(
    *,
    query_window: dict[str, object] | None = None,
    storage_target: str | None = DEFAULT_YFINANCE_STORAGE_TARGET,
) -> dict[str, object]:
    selected = normalize_yfinance_storage_target(storage_target)
    preset_key = str((query_window or {}).get("preset_key") or "")
    if selected == DEFAULT_YFINANCE_STORAGE_TARGET:
        target_keys = list(
            YFINANCE_QUERY_WINDOW_STORAGE_TARGETS.get(
                preset_key,
                ("sqlite_mvp_table", "mysql_timeseries_table", "parquet_duckdb_archive"),
            )
        )
        mode = "auto_suggestion"
    else:
        target_keys = [selected]
        mode = "explicit_user_selection"
    profiles = [
        yfinance_storage_target_profile_metadata(YFINANCE_STORAGE_TARGET_PROFILES[key])
        for key in target_keys
        if key in YFINANCE_STORAGE_TARGET_PROFILES
    ]
    # storage target 目前是資料護照 metadata；真正寫入 MySQL/Parquet/ClickHouse 仍需之後的明確匯出或匯入流程。
    recommended = str(profiles[0]["key"]) if profiles else "sqlite_mvp_table"
    return {
        "selection": selected,
        "mode": mode,
        "recommended_target": recommended,
        "targets": profiles,
        "background_write": False,
        "automatic_migration": False,
        "requires_explicit_user_import_or_export": True,
        "notes": "Storage targets are planning metadata only; yfinance live plans still write local CSV and require explicit user download/import.",
    }


def yfinance_query_window_policy(
    *,
    period: str | None = None,
    interval: str | None = None,
    query_window_preset: str | None = None,
) -> dict[str, object]:
    preset = normalize_yfinance_query_window_preset(query_window_preset)
    # preset 是圖表/儲存語意，不是排程；使用者仍可用 period/interval 明確覆寫實際查詢範圍。
    base_period = preset.period if preset else "1mo"
    base_interval = preset.interval if preset else "1d"
    normalized_period = normalize_yfinance_period(period if period not in (None, "") else base_period)
    normalized_interval = normalize_yfinance_interval(interval if interval not in (None, "") else base_interval)
    policy: dict[str, object] = {
        "period": normalized_period,
        "interval": normalized_interval,
        "manual_override": bool(
            preset and (normalized_period != preset.period or normalized_interval != preset.interval)
        ),
        "background_refresh": False,
        "notes": "Query window presets are chart/storage metadata only; they do not schedule live refreshes.",
    }
    if preset:
        preset_metadata = yfinance_query_window_preset_metadata(preset)
        policy.update(
            {
                "preset_key": preset_metadata["preset_key"],
                "label": preset_metadata["label"],
                "chart_profile": preset_metadata["chart_profile"],
                "storage_hint": preset_metadata["storage_hint"],
            }
        )
        policy["preset_period"] = preset.period
        policy["preset_interval"] = preset.interval
        policy["preset_notes"] = preset.notes
    return policy


def yfinance_retention_policy(retention_days: int) -> dict[str, object]:
    normalized_days = normalize_yfinance_retention_days(retention_days)
    return {
        "retention_days": normalized_days,
        "scope": "local_personal_research_cache",
        "automatic_delete": False,
        "background_refresh": False,
        "notes": "Retention is metadata for local cache governance; the launcher does not delete files automatically.",
    }


def _single_yfinance_plan_entry(plan_payload: dict[str, object]) -> dict[str, object]:
    providers = plan_payload.get("providers")
    if not isinstance(providers, list):
        raise ValueError("YFinance storage review expects a download plan with a providers list.")
    for entry in providers:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("provider_id") or "") == YFINANCE_PROVIDER_ID:
            return entry
    raise ValueError("YFinance storage review could not find a Yahoo Finance/yfinance plan entry.")


def _yfinance_review_storage_policy(
    source: dict[str, object],
    contract: dict[str, object],
    storage_target: str | None,
) -> dict[str, object]:
    raw_policy = source.get("storage_policy") if isinstance(source.get("storage_policy"), dict) else contract.get("storage_policy")
    policy = dict(raw_policy) if isinstance(raw_policy, dict) else yfinance_storage_target_policy()
    # review target 是可審查的具體目標；plan 裡若是 auto，就收斂到當時的 recommended target。
    if storage_target not in (None, ""):
        normalized = normalize_yfinance_storage_target(storage_target)
        if normalized != DEFAULT_YFINANCE_STORAGE_TARGET:
            policy = yfinance_storage_target_policy(storage_target=normalized)
    target_key = str(policy.get("recommended_target") or "sqlite_mvp_table")
    if target_key not in YFINANCE_STORAGE_TARGET_PROFILES:
        target_key = "sqlite_mvp_table"
    policy["review_target"] = target_key
    policy["review_is_dry_run"] = True
    policy["review_requires_separate_execution"] = True
    return policy


def _yfinance_storage_review_columns(engine: str) -> list[dict[str, str]]:
    if engine in {"mysql", "timescaledb_postgresql"}:
        time_type = "DATETIME" if engine == "mysql" else "TIMESTAMPTZ"
        numeric_type = "DECIMAL(20,8)" if engine == "mysql" else "NUMERIC"
        return [
            {"name": "event_time", "type": time_type, "nullable": "false"},
            {"name": "symbol", "type": "VARCHAR(32)", "nullable": "false"},
            {"name": "open", "type": numeric_type, "nullable": "true"},
            {"name": "high", "type": numeric_type, "nullable": "true"},
            {"name": "low", "type": numeric_type, "nullable": "true"},
            {"name": "close", "type": numeric_type, "nullable": "true"},
            {"name": "adj_close", "type": numeric_type, "nullable": "true"},
            {"name": "volume", "type": "BIGINT" if engine == "mysql" else "NUMERIC", "nullable": "true"},
            {"name": "received_at", "type": time_type, "nullable": "false"},
            {"name": "ingest_run_id", "type": "VARCHAR(128)", "nullable": "false"},
            {"name": "source_sequence", "type": "INTEGER", "nullable": "true"},
            {"name": "revision", "type": "VARCHAR(64)", "nullable": "true"},
        ]
    if engine == "clickhouse":
        return [
            {"name": "event_time", "type": "DateTime64(3, 'UTC')", "nullable": "false"},
            {"name": "symbol", "type": "LowCardinality(String)", "nullable": "false"},
            {"name": "open", "type": "Nullable(Decimal(20,8))", "nullable": "true"},
            {"name": "high", "type": "Nullable(Decimal(20,8))", "nullable": "true"},
            {"name": "low", "type": "Nullable(Decimal(20,8))", "nullable": "true"},
            {"name": "close", "type": "Nullable(Decimal(20,8))", "nullable": "true"},
            {"name": "adj_close", "type": "Nullable(Decimal(20,8))", "nullable": "true"},
            {"name": "volume", "type": "Nullable(UInt64)", "nullable": "true"},
            {"name": "received_at", "type": "DateTime64(3, 'UTC')", "nullable": "false"},
            {"name": "ingest_run_id", "type": "String", "nullable": "false"},
            {"name": "source_sequence", "type": "Nullable(UInt32)", "nullable": "true"},
            {"name": "revision", "type": "Nullable(String)", "nullable": "true"},
        ]
    return [{"name": name, "type": "TEXT", "nullable": "true"} for name in YFINANCE_CSV_FIELDNAMES]


def _yfinance_storage_review_sql(profile: YFinanceStorageTargetProfile, table_name: str, csv_uri: str) -> str:
    engine = profile.engine
    if engine == "sqlite":
        return ""
    if engine == "mysql":
        table = _quote_yfinance_identifier(engine, table_name)
        columns = ",\n  ".join(_mysql_column_sql(column) for column in _yfinance_storage_review_columns(engine))
        return (
            _storage_review_sql_header(profile, table_name, csv_uri)
            + f"CREATE TABLE IF NOT EXISTS {table} (\n  {columns},\n"
            + "  PRIMARY KEY (`symbol`, `event_time`, `ingest_run_id`)\n);\n\n"
            + "-- Review-only import sketch; adjust LOCAL INFILE policy, timezone parsing, and transaction scope before execution.\n"
            + f"-- LOAD DATA LOCAL INFILE {_sql_literal(csv_uri)} INTO TABLE {table} FIELDS TERMINATED BY ',' ENCLOSED BY '\"' IGNORE 1 LINES;\n"
        )
    if engine == "timescaledb_postgresql":
        table = _quote_yfinance_identifier(engine, table_name)
        columns = ",\n  ".join(_postgres_column_sql(column) for column in _yfinance_storage_review_columns(engine))
        return (
            _storage_review_sql_header(profile, table_name, csv_uri)
            + f"CREATE TABLE IF NOT EXISTS {table} (\n  {columns},\n"
            + f"  PRIMARY KEY (symbol, event_time, ingest_run_id)\n);\n\n"
            + f"-- SELECT create_hypertable({_sql_literal(table_name)}, 'event_time', if_not_exists => TRUE);\n"
            + "-- Review-only import sketch; use COPY from a vetted local path after manifest verification.\n"
            + f"-- COPY {table} FROM {_sql_literal(csv_uri)} WITH (FORMAT csv, HEADER true);\n"
        )
    if engine == "clickhouse":
        table = _quote_yfinance_identifier(engine, table_name)
        columns = ",\n  ".join(_clickhouse_column_sql(column) for column in _yfinance_storage_review_columns(engine))
        return (
            _storage_review_sql_header(profile, table_name, csv_uri)
            + f"CREATE TABLE IF NOT EXISTS {table} (\n  {columns}\n)\n"
            + "ENGINE = MergeTree\nORDER BY (symbol, event_time, ingest_run_id);\n\n"
            + "-- Review-only import sketch; adapt file() path and permissions before execution.\n"
            + f"-- INSERT INTO {table} SELECT * FROM file({_sql_literal(csv_uri)}, 'CSVWithNames');\n"
        )
    if engine == "parquet_duckdb":
        parquet_path = f"{table_name}.parquet"
        return (
            _storage_review_sql_header(profile, table_name, csv_uri)
            + "-- DuckDB/Parquet export sketch; this is not executed by the launcher.\n"
            + f"COPY (SELECT * FROM read_csv_auto({_sql_literal(csv_uri)}, header=true)) "
            + f"TO {_sql_literal(parquet_path)} (FORMAT PARQUET);\n"
        )
    return _storage_review_sql_header(profile, table_name, csv_uri)


def _yfinance_review_command(
    plan_path: str | Path | None,
    profile: YFinanceStorageTargetProfile,
    table_name: str,
) -> dict[str, str]:
    plan_label = str(plan_path or "<PLAN_PATH>")
    if profile.engine == "sqlite":
        return {
            "kind": "sqlite_import",
            "command": (
                "python APIkeys_collection.py "
                f"--run-download-plan {plan_label} --import-supported-plan-results "
                "--plan-import-existing-table-policy rename"
            ),
            "notes": "SQLite 是目前唯一已接上既有 importer 的 yfinance storage execution path。",
        }
    return {
        "kind": "dry_run_review",
        "command": f"review generated SQL for target={profile.key} table={table_name}",
        "notes": "先由人或 DBA 審查 dry-run SQL；launcher 本輪不會連線、不會建表、不會匯入。",
    }


def _storage_review_sql_header(profile: YFinanceStorageTargetProfile, table_name: str, csv_uri: str) -> str:
    return (
        "-- APIkeys_collection yfinance storage review dry-run\n"
        "-- 本檔只供審查；launcher 不會自動執行，也不會連線或寫入資料庫。\n"
        f"-- target={profile.key} engine={profile.engine} table={table_name}\n"
        f"-- source_csv={csv_uri}\n\n"
    )


def _mysql_column_sql(column: dict[str, str]) -> str:
    nullable = "NOT NULL" if column["nullable"] == "false" else "NULL"
    return f"`{validate_sql_identifier(column['name'])}` {column['type']} {nullable}"


def _postgres_column_sql(column: dict[str, str]) -> str:
    nullable = "NOT NULL" if column["nullable"] == "false" else "NULL"
    return f'"{validate_sql_identifier(column["name"])}" {column["type"]} {nullable}'


def _clickhouse_column_sql(column: dict[str, str]) -> str:
    return f"`{validate_sql_identifier(column['name'])}` {column['type']}"


def _quote_yfinance_identifier(engine: str, identifier: str) -> str:
    clean = validate_sql_identifier(identifier)
    if engine in {"mysql", "clickhouse"}:
        return f"`{clean}`"
    return f'"{clean}"'


def _sql_literal(value: str) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


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
