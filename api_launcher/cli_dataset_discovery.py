from __future__ import annotations

import argparse
import json
import sqlite3

from api_launcher.dataset_discovery import (
    DEFAULT_DATASET_DISCOVERY_SOURCES_NAME,
    LOCAL_DATASET_DISCOVERY_SOURCES_NAME,
    DatasetCandidate,
    DatasetCrawlOptions,
    crawl_dataset_sources,
    dataset_with_candidate_metadata,
    load_all_dataset_discovery_sources,
)
from api_launcher.db import resolve_project_path, utc_now_iso
from api_launcher.discovery_promotion import promote_local_discovery_catalog
from api_launcher.paths import catalog_file, local_config_file, state_file
from api_launcher.registry import PROVIDER_CATALOG_NAME
from api_launcher.repository import ApiCatalogRepository, load_providers


def add_dataset_discovery_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--discover-dataset-candidates", action="store_true", help="crawl configured source catalogs into reviewable dataset candidates")
    parser.add_argument("--dataset-discovery-sources", default=DEFAULT_DATASET_DISCOVERY_SOURCES_NAME, help="JSON source list for dataset discovery")
    parser.add_argument("--dataset-discovery-local-sources", default=LOCAL_DATASET_DISCOVERY_SOURCES_NAME, help="ignored local JSON source list for user-added dataset discovery sources")
    parser.add_argument("--dataset-discovery-source", action="append", default=[], help="source_id to crawl; can be repeated")
    parser.add_argument("--dataset-discovery-term", action="append", default=[], help="override search term for searchable sources; can be repeated")
    parser.add_argument("--dataset-discovery-limit", type=int, default=0, help="page size / max candidates per source request; 0 uses source config")
    parser.add_argument("--dataset-discovery-full-crawl", action="store_true", help="page through each source until it ends or the safety max-pages cap is reached")
    parser.add_argument("--dataset-discovery-max-pages", type=int, default=0, help="max pages per source for full crawl; 0 uses crawler safety cap")
    parser.add_argument("--dataset-discovery-workers", type=int, default=4, help="parallel source crawlers for dataset discovery")
    parser.add_argument("--dataset-discovery-min-candidates-per-source", type=int, default=-1, help="audit minimum candidates per source; -1 uses source config")
    parser.add_argument("--dataset-discovery-strict-audit", action="store_true", help="exit with failure when any crawler source has errors or audit warnings")
    parser.add_argument("--write-dataset-candidates", default="dataset_candidates.discovered.json", help="output JSON for discovered dataset candidates")
    parser.add_argument("--upsert-dataset-candidates", action="store_true", help="upsert discovered dataset candidates into the datasets table for review")
    parser.add_argument("--list-dataset-candidates", action="store_true", help="list reviewable dataset candidates stored in the datasets table")
    parser.add_argument("--dataset-candidate-status", default="needs_review", help="candidate status to list: needs_review, approved, planned, rejected, or all")
    parser.add_argument("--dataset-candidates-json", action="store_true", help="emit dataset candidate listing as JSON")
    parser.add_argument("--review-dataset-candidate", action="append", default=[], help="dataset_uid to mark with --dataset-candidate-decision; can be repeated")
    parser.add_argument("--dataset-candidate-decision", default="approved", choices=("needs_review", "approved", "planned", "rejected"), help="review decision for --review-dataset-candidate")
    parser.add_argument("--dataset-candidate-note", default="", help="review note to store in candidate metadata")
    parser.add_argument("--promote-local-discovery-catalog", action="store_true", help="audit local dataset discovery sources and promote passing drafts into official catalog files")
    parser.add_argument("--promote-local-discovery-dry-run", action="store_true", help="run local discovery promotion audit without writing official catalog files")
    parser.add_argument("--write-local-discovery-audit-json", default="", help="write promotion audit result JSON for --promote-local-discovery-catalog")


def dataset_discovery_command_active(args: argparse.Namespace) -> bool:
    return bool(
        args.discover_dataset_candidates
        or args.list_dataset_candidates
        or args.review_dataset_candidate
        or args.promote_local_discovery_catalog
    )


def discover_dataset_candidates_cli(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if args.discover_dataset_candidates:
        source_path = catalog_file(args.dataset_discovery_sources)
        local_source_path = local_config_file(args.dataset_discovery_local_sources)
        sources = load_all_dataset_discovery_sources(source_path, local_source_path)
        if args.provider:
            wanted_providers = set(args.provider)
            sources = [source for source in sources if source.provider_id in wanted_providers]
        if args.dataset_discovery_source:
            wanted_sources = set(args.dataset_discovery_source)
            sources = [source for source in sources if source.source_id in wanted_sources]
        crawl_result = crawl_dataset_sources(
            sources,
            DatasetCrawlOptions(
                timeout=args.timeout,
                max_results_override=args.dataset_discovery_limit,
                search_terms_override=tuple(args.dataset_discovery_term),
                full_crawl=args.dataset_discovery_full_crawl,
                max_pages=args.dataset_discovery_max_pages,
                max_workers=args.dataset_discovery_workers,
                min_candidates_per_source_override=args.dataset_discovery_min_candidates_per_source,
            ),
        )
        candidates = list(crawl_result.candidates)
        output_path = state_file(args.write_dataset_candidates)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "created_at": utc_now_iso(),
            "role": "reviewable dataset candidates; metadata only; no bulk data downloaded",
            "source_count": len(sources),
            "candidate_count": len(candidates),
            "duplicate_count": crawl_result.duplicate_count,
            "error_count": crawl_result.error_count,
            "warning_count": crawl_result.warning_count,
            "full_crawl": args.dataset_discovery_full_crawl,
            "source_results": [
                {
                    "source_id": result.source_id,
                    "provider_id": result.provider_id,
                    "source_type": result.source_type,
                    "candidate_count": result.candidate_count,
                    "unique_candidate_count": result.unique_candidate_count,
                    "duplicate_candidate_count": result.duplicate_candidate_count,
                    "audit_status": result.audit_status,
                    "error": result.error,
                    "warnings": list(result.warnings),
                }
                for result in crawl_result.source_results
            ],
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(
            "[dataset-discover] "
            f"wrote {len(candidates)} dataset candidates to {output_path} "
            f"sources={len(sources)} errors={crawl_result.error_count} "
            f"warnings={crawl_result.warning_count} duplicates={crawl_result.duplicate_count}"
        )
        for result in crawl_result.source_results:
            if result.error:
                print(f"[dataset-discover] source_error {result.source_id}: {result.error}")
            for warning in result.warnings:
                print(f"[dataset-discover] source_warning {result.source_id}: {warning}")
        if args.upsert_dataset_candidates:
            count = upsert_candidates(conn, candidates)
            print(f"[dataset-discover] upserted {count} dataset candidates")
        if args.dataset_discovery_strict_audit and crawl_result.audit_issue_count:
            raise SystemExit(
                "[dataset-discover] strict audit failed: "
                f"errors={crawl_result.error_count} warnings={crawl_result.warning_count}"
            )

    review_dataset_candidates_cli(conn, args)
    promote_local_discovery_catalog_cli(args)


def promote_local_discovery_catalog_cli(args: argparse.Namespace) -> None:
    if not args.promote_local_discovery_catalog:
        return
    result = promote_local_discovery_catalog(
        local_provider_seed_path=local_config_file(args.provider_discovery_local_seeds),
        local_dataset_source_path=local_config_file(args.dataset_discovery_local_sources),
        provider_catalog_path=catalog_file(PROVIDER_CATALOG_NAME),
        dataset_source_catalog_path=catalog_file(args.dataset_discovery_sources),
        options=DatasetCrawlOptions(
            timeout=args.timeout,
            max_results_override=args.dataset_discovery_limit,
            search_terms_override=tuple(args.dataset_discovery_term),
            full_crawl=args.dataset_discovery_full_crawl,
            max_pages=args.dataset_discovery_max_pages,
            max_workers=args.dataset_discovery_workers,
            min_candidates_per_source_override=args.dataset_discovery_min_candidates_per_source,
        ),
        source_ids=set(args.dataset_discovery_source),
        dry_run=args.promote_local_discovery_dry_run,
    )
    payload = result.to_dict()
    print(
        "[local-discovery-promote] "
        f"audited={result.audited_source_count} "
        f"providers={result.promoted_provider_count} "
        f"sources={result.promoted_source_count} "
        f"skipped={result.skipped_count} "
        f"audit_issues={payload['audit']['audit_issue_count']}"
    )
    for skipped in result.skipped:
        print(
            "[local-discovery-promote] skipped "
            f"source={skipped.get('source_id') or '-'} "
            f"provider={skipped.get('provider_id') or '-'} "
            f"reason={skipped.get('reason') or '-'}"
        )
    if args.write_local_discovery_audit_json:
        output_path = resolve_project_path(args.write_local_discovery_audit_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[local-discovery-promote] wrote {output_path}")


def upsert_candidates(conn: sqlite3.Connection, candidates: list[DatasetCandidate]) -> int:
    existing_provider_ids = {provider.provider_id for provider in load_providers(conn)}
    repository = ApiCatalogRepository(conn)
    count = 0
    for candidate in candidates:
        if candidate.dataset.provider_id not in existing_provider_ids:
            continue
        repository.upsert_dataset(dataset_with_candidate_metadata(candidate))
        count += 1
    return count


def review_dataset_candidates_cli(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    repository = ApiCatalogRepository(conn)
    for dataset_uid in args.review_dataset_candidate:
        dataset = repository.mark_dataset_candidate_status(
            dataset_uid,
            args.dataset_candidate_decision,
            reviewed_by="cli",
            note=args.dataset_candidate_note,
        )
        print(
            "[dataset-candidate] "
            f"{dataset.dataset_uid} status={dataset.metadata.get('candidate_status')} title={dataset.title}"
        )
    if not args.list_dataset_candidates:
        return
    candidates = repository.list_dataset_candidates(args.dataset_candidate_status)
    provider_filter = set(args.provider or [])
    if provider_filter:
        candidates = [dataset for dataset in candidates if dataset.provider_id in provider_filter]
    if args.dataset_candidates_json:
        payload = {
            "schema_version": 1,
            "created_at": utc_now_iso(),
            "candidate_count": len(candidates),
            "status_filter": args.dataset_candidate_status,
            "candidates": [
                {
                    "dataset_uid": dataset.dataset_uid,
                    "provider_id": dataset.provider_id,
                    "dataset_id": dataset.dataset_id,
                    "title": dataset.title,
                    "native_format": dataset.native_format,
                    "data_type": dataset.data_type,
                    "api_url": dataset.api_url,
                    "landing_url": dataset.landing_url,
                    "candidate_status": dataset.metadata.get("candidate_status", ""),
                    "metadata": dataset.metadata,
                }
                for dataset in candidates
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not candidates:
        print(f"[dataset-candidate] no candidates status={args.dataset_candidate_status}")
        return
    for dataset in candidates:
        metadata = dataset.metadata
        print(
            "[dataset-candidate] "
            f"{str(metadata.get('candidate_status') or '-'):12s} "
            f"{dataset.provider_id:28s} "
            f"{dataset.dataset_uid:28s} "
            f"{dataset.title}"
        )
