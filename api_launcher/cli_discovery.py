from __future__ import annotations

import argparse
import json
import sqlite3

from api_launcher.crawlers.source_patterns import DEFAULT_PATTERN_MINIMUM_CONFIDENCE
from api_launcher.crawlers.dataset_sources import LOCAL_DATASET_DISCOVERY_SOURCES_NAME
from api_launcher.db import resolve_project_path, utc_now_iso
from api_launcher.discovery import (
    DEFAULT_PROVIDER_DISCOVERY_FETCH_MAX_BYTES,
    DEFAULT_SEEDS_NAME,
    LOCAL_SEEDS_NAME,
    ProviderSeed,
    append_discovery_seed,
    discover_provider_candidates,
    load_all_discovery_seeds,
)
from api_launcher.discovery_drafts import write_provider_candidate_source_drafts
from api_launcher.event_log import log_event
from api_launcher.repository import load_providers
from api_launcher.paths import catalog_file, local_config_file, state_file
from api_launcher.source_pattern_drafts import SourcePatternDraftError, write_source_draft_from_url


def add_discovery_args(parser: argparse.ArgumentParser) -> None:
    # provider discovery CLI 只處理 provider seed/candidate，不負責 dataset crawler。
    parser.add_argument("--discover-provider-candidates", action="store_true", help="crawl official source pages into reviewable provider candidates")
    parser.add_argument("--provider-discovery-seeds", default=DEFAULT_SEEDS_NAME, help="JSON seed list for provider discovery")
    parser.add_argument("--provider-discovery-local-seeds", default=LOCAL_SEEDS_NAME, help="local JSON seed list for user-added source sites")
    parser.add_argument("--provider-discovery-max-bytes", type=int, default=DEFAULT_PROVIDER_DISCOVERY_FETCH_MAX_BYTES, help="maximum homepage/docs bytes to read per provider discovery seed")
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
    parser.add_argument("--write-provider-candidate-source-drafts", action="store_true", help="write supported provider candidates as ignored local dataset discovery source drafts")
    parser.add_argument("--provider-candidate-source-drafts-input", default="", help="provider candidate review JSON to convert; defaults to the current discovery output or state/provider_candidates.ui.json")
    parser.add_argument("--provider-candidate-source-drafts-local", default=LOCAL_DATASET_DISCOVERY_SOURCES_NAME, help="ignored local dataset discovery sources JSON to update")
    parser.add_argument("--provider-candidate-source-provider-id", action="append", default=[], help="only convert candidates for this provider_id; can be repeated")
    parser.add_argument("--write-provider-candidate-source-drafts-json", default="", help="optional JSON summary for the local source draft write")
    parser.add_argument("--write-source-draft-from-url", default="", help="detect one source URL and append an ignored local dataset discovery source draft")
    parser.add_argument("--source-draft-provider-id", default="", help="provider/source id for --write-source-draft-from-url; defaults to the URL host")
    parser.add_argument("--source-draft-name", default="", help="display name for --write-source-draft-from-url; defaults to host plus detected pattern")
    parser.add_argument("--source-draft-source-id", default="", help="explicit source_id for --write-source-draft-from-url")
    parser.add_argument("--source-draft-category", action="append", default=[], help="category for --write-source-draft-from-url; can be repeated")
    parser.add_argument("--source-draft-scope", default="global", help="geographic scope for --write-source-draft-from-url")
    parser.add_argument("--source-draft-max-results", type=int, default=10, help="max candidates for the generated local source draft")
    parser.add_argument("--source-draft-min-expected-candidates", type=int, default=1, help="minimum expected candidates for crawler audit")
    parser.add_argument("--source-draft-local", default=LOCAL_DATASET_DISCOVERY_SOURCES_NAME, help="ignored local dataset discovery sources JSON to update")
    parser.add_argument("--source-draft-detector-timeout", type=float, default=8.0, help="seconds for source-pattern detector probes")
    parser.add_argument(
        "--source-draft-detector-min-confidence",
        type=float,
        default=DEFAULT_PATTERN_MINIMUM_CONFIDENCE,
        help="minimum detector confidence before keeping the URL in review",
    )
    parser.add_argument("--write-source-draft-json", default="", help="optional JSON summary for --write-source-draft-from-url")


def discovery_command_active(args: argparse.Namespace) -> bool:
    # core.py 用這個函式決定是否進入 CLI 命令模式，避免互動 UI 被意外啟動。
    return bool(
        args.discover_provider_candidates
        or args.add_discovery_seed
        or args.write_provider_candidate_source_drafts
        or bool(args.write_source_draft_from_url)
    )


def add_local_discovery_seed(args: argparse.Namespace) -> None:
    if not args.add_discovery_seed:
        return
    # 本機 seed 需要最小可審核欄位；缺欄位就停止，不寫半成品到 local config。
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
    # append_discovery_seed 會做 source id 去重，讓同一命令重跑不產生重複 seed。
    append_discovery_seed(path, seed)
    print(f"[discover] added local source seed {seed.provider_id} to {path}")


def discover_source_candidates(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    if not args.discover_provider_candidates:
        return
    # provider discovery 只輸出 review JSON，不直接把候選寫入 catalog。
    seed_path = catalog_file(args.provider_discovery_seeds)
    local_seed_path = local_config_file(args.provider_discovery_local_seeds)
    output_path = state_file(args.write_provider_candidates)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {provider.provider_id for provider in load_providers(conn)}
    seeds = load_all_discovery_seeds(seed_path, local_seed_path)
    candidates = discover_provider_candidates(
        seeds,
        existing_provider_ids=existing,
        timeout=args.timeout,
        max_bytes=args.provider_discovery_max_bytes,
    )
    payload = {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "role": "reviewable source candidates; metadata only; no API secrets collected",
        "candidate_count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[discover] wrote {len(candidates)} provider candidates to {output_path}")


def write_provider_candidate_source_drafts_cli(args: argparse.Namespace) -> None:
    if not args.write_provider_candidate_source_drafts:
        return
    # 同一個命令若剛跑完 provider discovery，就沿用該輸出；否則預設讀 Tk review JSON。
    if args.provider_candidate_source_drafts_input:
        input_path = resolve_project_path(args.provider_candidate_source_drafts_input)
    elif args.discover_provider_candidates:
        input_path = state_file(args.write_provider_candidates)
    else:
        input_path = state_file("provider_candidates.ui.json")
    if not input_path.exists():
        raise SystemExit(f"--write-provider-candidate-source-drafts input not found: {input_path}")

    output_path = local_config_file(args.provider_candidate_source_drafts_local)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    summary = write_provider_candidate_source_drafts(
        payload,
        output_path,
        provider_ids=tuple(args.provider_candidate_source_provider_id or ()),
    )
    summary_path_text = ""
    print(
        "[discover] wrote "
        f"{summary['source_draft_count']} local dataset source drafts to {output_path} "
        f"(skipped {summary['skipped_count']})"
    )
    if args.write_provider_candidate_source_drafts_json:
        summary_path = resolve_project_path(args.write_provider_candidate_source_drafts_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary_path_text = str(summary_path)
        print(f"[discover] wrote provider candidate source draft summary to {summary_path}")
    # 這個事件是 Mac/heartbeat 接力用的最小索引：只記 staging 路徑與下一步 audit，不把草稿內容塞進 log。
    log_event(
        "provider_candidate_source_drafts_written",
        "provider candidate source drafts written to local discovery config",
        component="discovery",
        context={
            "input_path": str(input_path),
            "dataset_source_path": str(output_path),
            "summary_path": summary_path_text,
            "source_draft_count": summary.get("source_draft_count", 0),
            "skipped_count": summary.get("skipped_count", 0),
            "provider_filter": summary.get("provider_filter", []),
            "audit_source_ids": summary.get("audit_source_ids", []),
            "next_action": summary.get("next_action", ""),
            "audit_command": summary.get("audit_command", ""),
        },
    )


def write_source_draft_from_url_cli(args: argparse.Namespace) -> None:
    if not args.write_source_draft_from_url:
        return
    # URL detector 只寫入 ignored local source draft；真正 catalog promotion 仍需 local discovery audit。
    output_path = local_config_file(args.source_draft_local)
    try:
        summary = write_source_draft_from_url(
            args.write_source_draft_from_url,
            output_path,
            provider_id=args.source_draft_provider_id,
            name=args.source_draft_name,
            source_id=args.source_draft_source_id,
            categories=tuple(args.source_draft_category or ()),
            geographic_scope=args.source_draft_scope,
            max_results=args.source_draft_max_results,
            min_expected_candidates=args.source_draft_min_expected_candidates,
            timeout=args.source_draft_detector_timeout,
            minimum_confidence=args.source_draft_detector_min_confidence,
        )
    except SourcePatternDraftError as exc:
        summary = exc.to_dict()
        summary_path_text = ""
        if args.write_source_draft_json:
            summary_path = resolve_project_path(args.write_source_draft_json)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            summary_path_text = str(summary_path)
            print(f"[discover] wrote blocked source draft summary to {summary_path}")
        log_event(
            "source_pattern_source_draft_blocked",
            "source pattern detector kept a URL in review before writing local config",
            level="warning",
            component="discovery",
            context={
                "source_url": args.write_source_draft_from_url,
                "dataset_source_path": str(output_path),
                "summary_path": summary_path_text,
                "review_reason": summary.get("review_reason", ""),
                "minimum_confidence": summary.get("minimum_confidence", ""),
                "source_pattern_detection": summary.get("source_pattern_detection", {}),
                "next_action": summary.get("next_action", ""),
            },
        )
        raise
    summary_path_text = ""
    detection = summary.get("source_pattern_detection", {})
    print(
        "[discover] detected "
        f"{detection.get('pattern_id', 'unknown')} -> {detection.get('source_type_hint', '')} "
        f"and wrote 1 local dataset source draft to {output_path}"
    )
    if args.write_source_draft_json:
        summary_path = resolve_project_path(args.write_source_draft_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary_path_text = str(summary_path)
        print(f"[discover] wrote detected source draft summary to {summary_path}")
    log_event(
        "source_pattern_source_draft_written",
        "source pattern detector wrote a local dataset discovery source draft",
        component="discovery",
        context={
            "source_url": args.write_source_draft_from_url,
            "dataset_source_path": str(output_path),
            "summary_path": summary_path_text,
            "source_draft_count": summary.get("source_draft_count", 0),
            "audit_source_ids": summary.get("audit_source_ids", []),
            "source_pattern_detection": summary.get("source_pattern_detection", {}),
            "next_action": summary.get("next_action", ""),
            "audit_command": summary.get("audit_command", ""),
        },
    )
