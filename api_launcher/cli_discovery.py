from __future__ import annotations

import argparse
import json
import sqlite3

from api_launcher.db import resolve_project_path, utc_now_iso
from api_launcher.discovery import (
    DEFAULT_SEEDS_NAME,
    LOCAL_SEEDS_NAME,
    ProviderSeed,
    append_discovery_seed,
    discover_provider_candidates,
    load_all_discovery_seeds,
)
from api_launcher.repository import load_providers
from api_launcher.paths import catalog_file, local_config_file, state_file


def add_discovery_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--discover-provider-candidates", action="store_true", help="crawl official source pages into reviewable provider candidates")
    parser.add_argument("--provider-discovery-seeds", default=DEFAULT_SEEDS_NAME, help="JSON seed list for provider discovery")
    parser.add_argument("--provider-discovery-local-seeds", default=LOCAL_SEEDS_NAME, help="local JSON seed list for user-added source sites")
    parser.add_argument("--write-provider-candidates", default="provider_candidates.discovered.json", help="output JSON for discovered provider candidates")
    parser.add_argument("--add-discovery-seed", action="store_true", help="append one local source-site seed for future provider discovery")
    parser.add_argument("--seed-provider-id", default="", help="provider/source id for --add-discovery-seed")
    parser.add_argument("--seed-name", default="", help="display name for --add-discovery-seed")
    parser.add_argument("--seed-owner", default="", help="owner for --add-discovery-seed")
    parser.add_argument("--seed-category", action="append", default=[], help="category for --add-discovery-seed; can be repeated")
    parser.add_argument("--seed-scope", default="global", help="geographic scope for --add-discovery-seed")
    parser.add_argument("--seed-homepage-url", default="", help="homepage URL for --add-discovery-seed")
    parser.add_argument("--seed-docs-url", default="", help="docs URL for --add-discovery-seed")
    parser.add_argument("--seed-api-base-url", default="", help="API base URL for --add-discovery-seed")
    parser.add_argument("--seed-signup-url", default="", help="signup URL for --add-discovery-seed")
    parser.add_argument("--seed-auth-type", default="unknown", help="expected auth type for --add-discovery-seed")


def discovery_command_active(args: argparse.Namespace) -> bool:
    return bool(args.discover_provider_candidates or args.add_discovery_seed)


def add_local_discovery_seed(args: argparse.Namespace) -> None:
    if not args.add_discovery_seed:
        return
    required = {
        "--seed-provider-id": args.seed_provider_id,
        "--seed-name": args.seed_name,
        "--seed-owner": args.seed_owner,
        "--seed-homepage-url": args.seed_homepage_url,
    }
    missing = [flag for flag, value in required.items() if not value.strip()]
    if missing:
        raise SystemExit(f"--add-discovery-seed missing required fields: {', '.join(missing)}")
    seed = ProviderSeed(
        provider_id=args.seed_provider_id.strip(),
        name=args.seed_name.strip(),
        owner=args.seed_owner.strip(),
        categories=tuple(args.seed_category or ["custom"]),
        geographic_scope=args.seed_scope.strip() or "global",
        homepage_url=args.seed_homepage_url.strip(),
        docs_url=args.seed_docs_url.strip(),
        api_base_url=args.seed_api_base_url.strip(),
        signup_url=args.seed_signup_url.strip(),
        expected_auth_type=args.seed_auth_type.strip() or "unknown",
    )
    path = local_config_file(args.provider_discovery_local_seeds)
    append_discovery_seed(path, seed)
    print(f"[discover] added local source seed {seed.provider_id} to {path}")


def discover_source_candidates(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if not args.discover_provider_candidates:
        return
    seed_path = catalog_file(args.provider_discovery_seeds)
    local_seed_path = local_config_file(args.provider_discovery_local_seeds)
    output_path = state_file(args.write_provider_candidates)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {provider.provider_id for provider in load_providers(conn)}
    seeds = load_all_discovery_seeds(seed_path, local_seed_path)
    candidates = discover_provider_candidates(seeds, existing_provider_ids=existing, timeout=args.timeout)
    payload = {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "role": "reviewable source candidates; metadata only; no API secrets collected",
        "candidate_count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[discover] wrote {len(candidates)} provider candidates to {output_path}")
