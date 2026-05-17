from __future__ import annotations

import argparse
import json
import sqlite3

from api_launcher.dataset_discovery import (
    DEFAULT_DATASET_DISCOVERY_SOURCES_NAME,
    DatasetCandidate,
    discover_dataset_candidates,
    load_dataset_discovery_sources,
)
from api_launcher.db import utc_now_iso
from api_launcher.paths import catalog_file, state_file
from api_launcher.repository import ApiCatalogRepository, load_providers


def add_dataset_discovery_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--discover-dataset-candidates", action="store_true", help="crawl configured source catalogs into reviewable dataset candidates")
    parser.add_argument("--dataset-discovery-sources", default=DEFAULT_DATASET_DISCOVERY_SOURCES_NAME, help="JSON source list for dataset discovery")
    parser.add_argument("--dataset-discovery-source", action="append", default=[], help="source_id to crawl; can be repeated")
    parser.add_argument("--dataset-discovery-term", action="append", default=[], help="override search term for searchable sources; can be repeated")
    parser.add_argument("--dataset-discovery-limit", type=int, default=0, help="max candidates per source request; 0 uses source config")
    parser.add_argument("--write-dataset-candidates", default="dataset_candidates.discovered.json", help="output JSON for discovered dataset candidates")
    parser.add_argument("--upsert-dataset-candidates", action="store_true", help="upsert discovered dataset candidates into the datasets table for review")
    parser.add_argument("--list-dataset-candidates", action="store_true", help="list reviewable dataset candidates stored in the datasets table")
    parser.add_argument("--dataset-candidate-status", default="needs_review", help="candidate status to list: needs_review, approved, planned, rejected, or all")
    parser.add_argument("--dataset-candidates-json", action="store_true", help="emit dataset candidate listing as JSON")
    parser.add_argument("--review-dataset-candidate", action="append", default=[], help="dataset_uid to mark with --dataset-candidate-decision; can be repeated")
    parser.add_argument("--dataset-candidate-decision", default="approved", choices=("needs_review", "approved", "planned", "rejected"), help="review decision for --review-dataset-candidate")
    parser.add_argument("--dataset-candidate-note", default="", help="review note to store in candidate metadata")


def dataset_discovery_command_active(args: argparse.Namespace) -> bool:
    return bool(args.discover_dataset_candidates or args.list_dataset_candidates or args.review_dataset_candidate)


def discover_dataset_candidates_cli(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if args.discover_dataset_candidates:
        source_path = catalog_file(args.dataset_discovery_sources)
        sources = load_dataset_discovery_sources(source_path)
        if args.provider:
            wanted_providers = set(args.provider)
            sources = [source for source in sources if source.provider_id in wanted_providers]
        if args.dataset_discovery_source:
            wanted_sources = set(args.dataset_discovery_source)
            sources = [source for source in sources if source.source_id in wanted_sources]
        candidates = discover_dataset_candidates(
            sources,
            timeout=args.timeout,
            max_results_override=args.dataset_discovery_limit,
            search_terms_override=tuple(args.dataset_discovery_term),
        )
        output_path = state_file(args.write_dataset_candidates)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "created_at": utc_now_iso(),
            "role": "reviewable dataset candidates; metadata only; no bulk data downloaded",
            "source_count": len(sources),
            "candidate_count": len(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[dataset-discover] wrote {len(candidates)} dataset candidates to {output_path}")
        if args.upsert_dataset_candidates:
            count = upsert_candidates(conn, candidates)
            print(f"[dataset-discover] upserted {count} dataset candidates")

    review_dataset_candidates_cli(conn, args)


def upsert_candidates(conn: sqlite3.Connection, candidates: list[DatasetCandidate]) -> int:
    existing_provider_ids = {provider.provider_id for provider in load_providers(conn)}
    repository = ApiCatalogRepository(conn)
    count = 0
    for candidate in candidates:
        if candidate.dataset.provider_id not in existing_provider_ids:
            continue
        repository.upsert_dataset(candidate.dataset)
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
