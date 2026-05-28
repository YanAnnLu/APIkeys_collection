from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from api_launcher.crawler_asset_download import run_crawler_seed_download_import
from api_launcher.crawler_asset_profiles import crawler_asset_favorite_seed_uids
from api_launcher.crawler_asset_service import (
    CrawlerAssetListingResult,
    crawler_asset_listing_event_context,
    run_crawler_asset_listing,
)
from api_launcher.crawler_assets import load_crawler_asset_source
from api_launcher.crawler_seed_registry import (
    DEFAULT_CRAWLER_SEED_PAGE_SIZE,
    crawler_seed_page,
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
    parser.add_argument(
        "--crawler-asset-seeds",
        action="append",
        default=[],
        metavar="ASSET_ID",
        help="read one crawler asset's enumerated seed page from the local catalog",
    )
    parser.add_argument(
        "--crawler-asset-seeds-json",
        action="store_true",
        help="emit --crawler-asset-seeds results as agent-readable JSON",
    )
    parser.add_argument(
        "--crawler-asset-seeds-provider-id",
        default="",
        help="provider_id override for --crawler-asset-seeds; defaults from the crawler asset source profile",
    )
    parser.add_argument(
        "--crawler-asset-seed-page",
        type=int,
        default=1,
        help="1-based seed page number for --crawler-asset-seeds",
    )
    parser.add_argument(
        "--crawler-asset-seed-page-size",
        type=int,
        default=DEFAULT_CRAWLER_SEED_PAGE_SIZE,
        help="seed rows per page for --crawler-asset-seeds; capped by the shared seed registry service",
    )
    parser.add_argument(
        "--crawler-asset-profile-path",
        default="",
        help="optional crawler asset profile path used to read seed favorites",
    )
    parser.add_argument(
        "--run-crawler-seed-download-import",
        action="append",
        default=[],
        nargs=2,
        metavar=("ASSET_ID", "DATASET_UID"),
        help="download/import one visible crawler seed through the formal crawler seed service",
    )
    parser.add_argument(
        "--crawler-seed-download-import-json",
        action="store_true",
        help="emit --run-crawler-seed-download-import results as agent-readable JSON",
    )


def crawler_asset_command_active(args: argparse.Namespace) -> bool:
    return bool(
        args.run_crawler_asset_listing
        or args.crawler_asset_seeds
        or getattr(args, "run_crawler_seed_download_import", [])
    )


def run_crawler_asset_cli(
    args: argparse.Namespace,
    repository: ApiCatalogRepository,
    log_event_func: LogEvent,
) -> None:
    listing_asset_ids = tuple(str(asset_id).strip() for asset_id in args.run_crawler_asset_listing if str(asset_id).strip())
    seed_asset_ids = tuple(str(asset_id).strip() for asset_id in args.crawler_asset_seeds if str(asset_id).strip())
    seed_download_requests = tuple(
        (str(asset_id).strip(), str(dataset_uid).strip())
        for asset_id, dataset_uid in getattr(args, "run_crawler_seed_download_import", [])
        if str(asset_id).strip() and str(dataset_uid).strip()
    )
    if not listing_asset_ids and not seed_asset_ids and not seed_download_requests:
        return

    results: list[CrawlerAssetListingResult] = []
    for asset_id in listing_asset_ids:
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

    seed_results = [
        crawler_asset_seed_page_cli_result(
            repository,
            asset_id=asset_id,
            provider_id_override=args.crawler_asset_seeds_provider_id,
            page=args.crawler_asset_seed_page,
            page_size=args.crawler_asset_seed_page_size,
            profile_path=args.crawler_asset_profile_path,
        )
        for asset_id in seed_asset_ids
    ]
    seed_download_results = [
        crawler_seed_download_import_cli_result(
            args,
            repository,
            asset_id=asset_id,
            dataset_uid=dataset_uid,
        )
        for asset_id, dataset_uid in seed_download_requests
    ]

    payload = crawler_asset_cli_payload(
        listing_results=results,
        seed_results=seed_results,
        seed_download_results=seed_download_results,
    )
    if args.crawler_asset_listing_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if args.crawler_asset_seeds_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if getattr(args, "crawler_seed_download_import_json", False):
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
    for result in seed_results:
        if result.get("blocked"):
            print(
                f"[crawler-asset-seeds] {result.get('asset_id', '')}: blocked; "
                f"reason={result.get('blocked_reason', '')}; "
                f"next_action={result.get('next_action', 'review_crawler_asset_source')}"
            )
            continue
        summary = result.get("page_summary")
        summary = summary if isinstance(summary, dict) else {}
        print(
            f"[crawler-asset-seeds] {result.get('asset_id', '')}: "
            f"showing={summary.get('shown_start', 0)}-{summary.get('shown_end', 0)} "
            f"of {result.get('total', 0)}; has_more={result.get('has_more', False)}; "
            f"next_action={summary.get('next_action', 'seed_page_complete')}"
        )
    for result in seed_download_results:
        print(
            f"[crawler-seed-download] {result.get('asset_id', '')}: "
            f"stage={result.get('stage', '')}; succeeded={result.get('succeeded', False)}; "
            f"next_action={result.get('next_action', '')}"
        )


def crawler_asset_cli_payload(
    *,
    listing_results: list[CrawlerAssetListingResult],
    seed_results: list[dict[str, object]],
    seed_download_results: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    listing_payload = crawler_asset_listing_cli_payload(listing_results)
    seed_payload = crawler_asset_seed_page_cli_payload(seed_results)
    seed_download_payload = crawler_seed_download_import_cli_payload(seed_download_results or [])
    return {
        "command": "crawler_asset",
        "listing": listing_payload,
        "seed_pages": seed_payload,
        "seed_download_import": seed_download_payload,
        "next_action": "review_crawler_asset_results",
    }


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


def crawler_asset_seed_page_cli_result(
    repository: ApiCatalogRepository,
    *,
    asset_id: str,
    provider_id_override: str = "",
    page: int = 1,
    page_size: int = DEFAULT_CRAWLER_SEED_PAGE_SIZE,
    profile_path: str = "",
) -> dict[str, object]:
    clean_asset_id = str(asset_id or "").strip()
    clean_provider_id = str(provider_id_override or "").strip()
    source_found = False
    provider_id_source = "override" if clean_provider_id else ""
    if not clean_provider_id:
        source = load_crawler_asset_source(clean_asset_id)
        source_found = source is not None
        clean_provider_id = str(getattr(source, "provider_id", "") or "").strip() if source is not None else ""
        provider_id_source = "source_profile" if clean_provider_id else ""
    if not clean_asset_id or not clean_provider_id:
        return {
            "asset_id": clean_asset_id,
            "provider_id": clean_provider_id,
            "source_found": source_found,
            "provider_id_source": provider_id_source,
            "blocked": True,
            "blocked_reason": "crawler_asset_source_not_found_or_provider_id_required",
            "next_action": "provide_crawler_asset_provider_id_or_fix_source_profile",
        }

    favorite_seed_uids = crawler_asset_favorite_seed_uids(clean_asset_id, profile_path or None)
    payload = crawler_seed_page(
        repository,
        asset_id=clean_asset_id,
        provider_id=clean_provider_id,
        page=page,
        page_size=page_size,
        favorite_seed_uids=favorite_seed_uids,
    )
    payload["source_found"] = source_found
    payload["provider_id_source"] = provider_id_source
    payload["blocked"] = False
    payload["blocked_reason"] = ""
    payload["next_action"] = (
        str(payload.get("page_summary", {}).get("next_action", "seed_page_complete"))
        if isinstance(payload.get("page_summary"), dict)
        else "seed_page_complete"
    )
    return payload


def crawler_asset_seed_page_cli_payload(results: list[dict[str, object]]) -> dict[str, object]:
    blocked = sum(1 for result in results if result.get("blocked"))
    has_more = sum(1 for result in results if result.get("has_more"))
    return {
        "command": "crawler_asset_seed_page",
        "asset_count": len(results),
        "blocked_count": blocked,
        "has_more_count": has_more,
        "seed_count": sum(int(result.get("total") or 0) for result in results if not result.get("blocked")),
        "next_action": "show_next_seed_page" if has_more else "review_seed_page_results",
        "results": results,
    }


def crawler_seed_download_import_cli_result(
    args: argparse.Namespace,
    repository: ApiCatalogRepository,
    *,
    asset_id: str,
    dataset_uid: str,
) -> dict[str, object]:
    """Run one seed-level download/import and return a JSON-safe payload.

    CLI uses the same service as Web/Tk.  This gives the second bounded closure
    path an agent-readable smoke surface without teaching the CLI how to build
    plans, download files, or import artifacts itself.
    """

    clean_asset_id = str(asset_id or "").strip()
    clean_dataset_uid = str(dataset_uid or "").strip()
    root = Path(getattr(args, "downloads_root", "state/crawler_asset_downloads"))
    target_downloads = root / "crawler_seed_downloads" / safe_seed_download_dirname(clean_asset_id, clean_dataset_uid)
    plan_path = target_downloads / "resolved_seed_download_plan.json"
    result = run_crawler_seed_download_import(
        clean_asset_id,
        clean_dataset_uid,
        repository,
        target_downloads,
        import_sqlite_path=getattr(args, "import_sqlite_db", None),
        plan_path=plan_path,
        timeout=float(getattr(args, "download_timeout", 30.0) or 30.0),
        import_existing_table_policy=str(getattr(args, "plan_import_existing_table_policy", "rename") or "rename"),
    )
    return result.to_dict()


def crawler_seed_download_import_cli_payload(results: list[dict[str, object]]) -> dict[str, object]:
    succeeded = sum(1 for result in results if result.get("succeeded"))
    return {
        "command": "crawler_seed_download_import",
        "request_count": len(results),
        "succeeded_count": succeeded,
        "failed_or_blocked_count": max(0, len(results) - succeeded),
        "next_action": "review_seed_download_import_results" if results else "select_seed_to_download",
        "results": results,
    }


def safe_seed_download_dirname(asset_id: str, dataset_uid: str) -> str:
    """Return a stable, filesystem-safe folder segment for seed CLI artifacts."""

    raw = f"{asset_id}__{dataset_uid}".strip("_") or "crawler_seed"
    safe = []
    for char in raw:
        safe.append(char if char.isalnum() or char in {"-", "_", "."} else "_")
    return "".join(safe)[:160].strip("._") or "crawler_seed"


__all__ = [
    "add_crawler_asset_args",
    "crawler_asset_cli_payload",
    "crawler_asset_command_active",
    "crawler_asset_listing_cli_payload",
    "crawler_seed_download_import_cli_payload",
    "crawler_seed_download_import_cli_result",
    "crawler_asset_seed_page_cli_payload",
    "crawler_asset_seed_page_cli_result",
    "run_crawler_asset_cli",
]
