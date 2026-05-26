from __future__ import annotations

import argparse
import json

from api_launcher.crawler_run_records import DEFAULT_CRAWLER_RUN_EVENT_SCAN_LIMIT, crawler_run_summary_from_events
from api_launcher.event_log import latest_events


def add_crawler_run_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--crawler-run-summary-json",
        action="store_true",
        help="emit latest crawler listing/download-plan run summary as agent-readable JSON",
    )
    parser.add_argument(
        "--crawler-run-summary-limit",
        type=int,
        default=DEFAULT_CRAWLER_RUN_EVENT_SCAN_LIMIT,
        help="structured event count to scan for --crawler-run-summary-json",
    )


def crawler_run_record_command_active(args: argparse.Namespace) -> bool:
    return bool(args.crawler_run_summary_json)


def run_crawler_run_record_cli(args: argparse.Namespace) -> None:
    if not args.crawler_run_summary_json:
        return
    # 這條 CLI 只讀 structured event log，不能重跑 crawler，也不能讀回完整 resolved plan。
    event_limit = max(1, int(args.crawler_run_summary_limit))
    events = latest_events(event_limit)
    payload = crawler_run_summary_from_events(events)
    payload["event_count"] = len(events)
    payload["event_limit"] = event_limit
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


__all__ = [
    "add_crawler_run_record_args",
    "crawler_run_record_command_active",
    "run_crawler_run_record_cli",
]
