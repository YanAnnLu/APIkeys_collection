from __future__ import annotations

import argparse
import json
from typing import Callable

from api_launcher.crawler_asset_service import (
    CrawlerAssetListingResult,
    crawler_asset_listing_event_context,
    run_crawler_asset_listing,
)
from api_launcher.repository import ApiCatalogRepository

LogEvent = Callable[..., None]


def add_crawler_asset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--run-crawler-asset-listing",
        action="append",
        default=[],
        metavar="ASSET_ID",
        help="run one crawler asset listing and write a crawler listing event",
    )
    parser.add_argument(
        "--crawler-asset-listing-json",
        action="store_true",
        help="emit --run-crawler-asset-listing results as agent-readable JSON",
    )
    parser.add_argument(
        "--crawler-asset-listing-timeout",
        type=float,
        default=12.0,
        help="timeout in seconds for crawler asset listing probes",
    )
    parser.add_argument(
        "--crawler-asset-listing-limit",
        type=int,
        default=100,
        help="maximum candidates to request from each crawler asset listing",
    )
    parser.add_argument(
        "--crawler-asset-listing-max-pages",
        type=int,
        default=0,
        help="maximum HTML/index pages to crawl when the source supports bounded full crawl",
    )


def crawler_asset_command_active(args: argparse.Namespace) -> bool:
    return bool(args.run_crawler_asset_listing)


def run_crawler_asset_cli(
    args: argparse.Namespace,
    repository: ApiCatalogRepository,
    log_event_func: LogEvent,
) -> None:
    asset_ids = tuple(str(asset_id).strip() for asset_id in args.run_crawler_asset_listing if str(asset_id).strip())
    if not asset_ids:
        return

    results: list[CrawlerAssetListingResult] = []
    for asset_id in asset_ids:
        result = run_crawler_asset_listing(
            asset_id,
            repository.conn,
            timeout=args.crawler_asset_listing_timeout,
            max_results=max(1, int(args.crawler_asset_listing_limit)),
            max_pages=max(0, int(args.crawler_asset_listing_max_pages)),
        )
        results.append(result)
        log_event_func(
            "crawler_asset_listing_recorded",
            "CLI crawler asset listing recorded a backend listing outcome.",
            component="cli.crawler_assets",
            context=crawler_asset_listing_event_context(result),
        )

    payload = crawler_asset_listing_cli_payload(results)
    if args.crawler_asset_listing_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    for result in results:
        status = "blocked" if result.blocked else "ok"
        print(
            f"[crawler-asset] {result.asset_id}: {status}; "
            f"candidates={result.candidate_count}; upserted={result.upserted_count}; "
            f"warnings={result.warning_count}; errors={result.error_count}; "
            f"next_action={result.next_action or 'review_candidates'}"
        )


def crawler_asset_listing_cli_payload(results: list[CrawlerAssetListingResult]) -> dict[str, object]:
    blocked = sum(1 for result in results if result.blocked)
    return {
        "command": "crawler_asset_listing",
        "asset_count": len(results),
        "blocked_count": blocked,
        "candidate_count": sum(result.candidate_count for result in results),
        "upserted_count": sum(result.upserted_count for result in results),
        "warning_count": sum(result.warning_count for result in results),
        "error_count": sum(result.error_count for result in results),
        "next_action": "review_crawler_asset_listing_events" if results else "select_crawler_asset",
        "results": [result.to_dict() for result in results],
    }


__all__ = [
    "add_crawler_asset_args",
    "crawler_asset_command_active",
    "crawler_asset_listing_cli_payload",
    "run_crawler_asset_cli",
]
