from __future__ import annotations

import argparse

from api_launcher.adapters.yfinance import (
    DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
    DEFAULT_YFINANCE_RETENTION_DAYS,
    DEFAULT_YFINANCE_STORAGE_TARGET,
    YFINANCE_LIVE_WARNING,
    YFINANCE_QUERY_WINDOW_PRESETS,
    YFINANCE_STORAGE_TARGET_PROFILES,
    write_yfinance_demo_plan as write_yfinance_demo_plan_files,
    write_yfinance_live_plan as write_yfinance_live_plan_files,
    write_yfinance_storage_handoff as write_yfinance_storage_handoff_files,
    write_yfinance_storage_review as write_yfinance_storage_review_files,
)
from api_launcher.db import resolve_project_path


def add_yfinance_args(parser: argparse.ArgumentParser) -> None:
    # yfinance 是 optional/unofficial 的金融資料入口；旗標集中在這裡，避免 core.py 繼續累積特權適配器細節。
    parser.add_argument("--write-yfinance-demo-plan", help="write a fixture-backed Yahoo Finance/yfinance OHLCV demo plan")
    parser.add_argument("--write-yfinance-live-plan", help="explicit opt-in: fetch Yahoo Finance/yfinance live OHLCV data into a local CSV-backed plan")
    parser.add_argument("--yfinance-symbol", action="append", default=[], help="symbol for yfinance demo/live plans; can be repeated")
    parser.add_argument("--yfinance-period", default=None, help="period for --write-yfinance-live-plan, for example 5d, 1mo, 1y, ytd, or max")
    parser.add_argument("--yfinance-interval", default=None, help="interval for --write-yfinance-live-plan, for example 1d, 1h, or 5m")
    parser.add_argument(
        "--yfinance-query-window",
        default=DEFAULT_YFINANCE_QUERY_WINDOW_PRESET,
        choices=tuple(YFINANCE_QUERY_WINDOW_PRESETS),
        help="chart-friendly yfinance period/interval preset; explicit --yfinance-period/--yfinance-interval can override it",
    )
    parser.add_argument(
        "--yfinance-retention-days",
        type=int,
        default=DEFAULT_YFINANCE_RETENTION_DAYS,
        help="local retention metadata for yfinance live CSV plans; default 365 days",
    )
    parser.add_argument(
        "--yfinance-storage-target",
        default=DEFAULT_YFINANCE_STORAGE_TARGET,
        choices=(DEFAULT_YFINANCE_STORAGE_TARGET, *YFINANCE_STORAGE_TARGET_PROFILES),
        help="metadata-only storage target hint for yfinance live CSV plans; does not write to MySQL/Parquet/ClickHouse",
    )
    parser.add_argument("--yfinance-acknowledge-unofficial", action="store_true", help="required for --write-yfinance-live-plan after reviewing unofficial personal/research-only warning")
    parser.add_argument("--write-yfinance-storage-review", help="write a dry-run storage review JSON for an existing yfinance plan")
    parser.add_argument("--yfinance-storage-review-plan", default="", help="input yfinance plan JSON for --write-yfinance-storage-review")
    parser.add_argument(
        "--yfinance-storage-review-target",
        default="",
        choices=("", DEFAULT_YFINANCE_STORAGE_TARGET, *YFINANCE_STORAGE_TARGET_PROFILES),
        help="optional dry-run review target override; omitted means use the plan storage policy",
    )
    parser.add_argument("--write-yfinance-storage-review-sql", default="", help="optional companion dry-run SQL output path for --write-yfinance-storage-review")
    parser.add_argument("--write-yfinance-storage-handoff", help="write a human/DBA Markdown handoff from a yfinance storage review JSON")
    parser.add_argument("--yfinance-storage-handoff-review", default="", help="input yfinance storage review JSON for --write-yfinance-storage-handoff")


def yfinance_command_active(args: argparse.Namespace) -> bool:
    # 只有輸出型 yfinance 主旗標算命令；symbol/period/storage 只是其附屬參數。
    return bool(
        args.write_yfinance_demo_plan
        or args.write_yfinance_live_plan
        or args.write_yfinance_storage_review
        or args.write_yfinance_storage_handoff
    )


def run_yfinance_cli(args: argparse.Namespace) -> None:
    # core.py 只負責調度到這個邊界；具體 yfinance guard、review-only 文案與 writer 都留在本模組。
    write_yfinance_demo_plan(args)
    write_yfinance_live_plan(args)
    write_yfinance_storage_review(args)
    write_yfinance_storage_handoff(args)


def write_yfinance_demo_plan(args: argparse.Namespace) -> None:
    if not args.write_yfinance_demo_plan:
        return
    # yfinance demo plan 只寫離線 fixture，讓 CI/新手驗證時間序列 schema，不隱性打 Yahoo。
    result = write_yfinance_demo_plan_files(
        resolve_project_path(args.write_yfinance_demo_plan),
        symbols=args.yfinance_symbol,
        downloads_root=args.downloads_root,
    )
    print(
        "[yfinance-demo] "
        f"wrote {result.plan_path} fixture={result.fixture_path} symbols={','.join(result.symbols)}"
    )
    print(
        "[yfinance-demo] "
        "next="
        f"--run-download-plan {result.plan_path} --downloads-root {args.downloads_root} "
        "--import-supported-plan-results --plan-import-existing-table-policy rename"
    )


def write_yfinance_live_plan(args: argparse.Namespace) -> None:
    if not args.write_yfinance_live_plan:
        return
    # live yfinance 必須由使用者明確加 acknowledgement；這裡只產生本機 CSV + file:// plan，不接背景 crawler。
    result = write_yfinance_live_plan_files(
        resolve_project_path(args.write_yfinance_live_plan),
        symbols=args.yfinance_symbol,
        period=args.yfinance_period,
        interval=args.yfinance_interval,
        downloads_root=args.downloads_root,
        retention_days=args.yfinance_retention_days,
        query_window_preset=args.yfinance_query_window,
        storage_target=args.yfinance_storage_target,
        acknowledge_unofficial=args.yfinance_acknowledge_unofficial,
    )
    print(f"[yfinance-live] warning={YFINANCE_LIVE_WARNING}")
    print(
        "[yfinance-live] "
        f"wrote {result.plan_path} csv={result.csv_path} symbols={','.join(result.symbols)} "
        f"rows={result.rows_written} period={result.period} interval={result.interval} "
        f"retention_days={result.retention_days} query_window={result.query_window_preset or '-'} "
        f"storage_target={result.storage_target or '-'}"
    )
    print(
        "[yfinance-live] "
        "next="
        f"--run-download-plan {result.plan_path} --downloads-root {args.downloads_root} "
        "--import-supported-plan-results --plan-import-existing-table-policy rename"
    )


def write_yfinance_storage_review(args: argparse.Namespace) -> None:
    if not args.write_yfinance_storage_review:
        return
    if not args.yfinance_storage_review_plan:
        raise ValueError("--write-yfinance-storage-review requires --yfinance-storage-review-plan.")
    # storage review 是 yfinance metadata 到實際匯出/匯入之間的人工審查閘門；這裡只寫檔，不連資料庫。
    result = write_yfinance_storage_review_files(
        resolve_project_path(args.yfinance_storage_review_plan),
        resolve_project_path(args.write_yfinance_storage_review),
        storage_target=args.yfinance_storage_review_target or None,
        dry_run_sql_path=(
            resolve_project_path(args.write_yfinance_storage_review_sql)
            if args.write_yfinance_storage_review_sql
            else None
        ),
    )
    print(
        "[yfinance-storage-review] "
        f"wrote {result.review_path} plan={result.plan_path} target={result.storage_target} "
        f"actions={result.action_count} dry_run=true"
    )
    if result.dry_run_sql_path:
        print(f"[yfinance-storage-review] sql={result.dry_run_sql_path}")
    print(
        "[yfinance-storage-review] "
        "next=review the JSON/SQL, then run the existing download/import plan or a separately approved DBA path"
    )


def write_yfinance_storage_handoff(args: argparse.Namespace) -> None:
    if not args.write_yfinance_storage_handoff:
        return
    if not args.yfinance_storage_handoff_review:
        raise ValueError("--write-yfinance-storage-handoff requires --yfinance-storage-handoff-review.")
    # handoff 是給人類/DBA 的簽核材料；此命令只讀 review JSON 並寫 Markdown，不提升成 SQL executor。
    result = write_yfinance_storage_handoff_files(
        resolve_project_path(args.yfinance_storage_handoff_review),
        resolve_project_path(args.write_yfinance_storage_handoff),
    )
    print(
        "[yfinance-storage-handoff] "
        f"wrote {result.handoff_path} review={result.review_path} target={result.storage_target} "
        f"actions={result.action_count} dry_run=true"
    )
    if result.dry_run_sql_path:
        print(f"[yfinance-storage-handoff] sql={result.dry_run_sql_path}")
    print(
        "[yfinance-storage-handoff] "
        "next=human/DBA review only; no database connection or mutation was performed"
    )
