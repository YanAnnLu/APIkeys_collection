from __future__ import annotations

import argparse
from pathlib import Path

from api_launcher.db import resolve_project_path
from api_launcher.discovery import LOCAL_SEEDS_NAME
from api_launcher.dataset_discovery import LOCAL_DATASET_DISCOVERY_SOURCES_NAME
from api_launcher.paths import local_config_file
from api_launcher.portal_intake import (
    DEFAULT_PORTAL_INTAKE_PATH,
    build_portal_intake_payload,
    portal_intake_payload_to_json,
    promote_portal_intake_payload,
)


def add_portal_intake_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--portal-intake-report", action="store_true", help="parse the team database-portal intake Markdown and print an engineering summary")
    parser.add_argument("--portal-intake-path", default=DEFAULT_PORTAL_INTAKE_PATH, help="Markdown file containing the team database-portal intake table")
    parser.add_argument("--write-portal-intake-json", default="", help="write the parsed portal-intake review payload to JSON")
    parser.add_argument("--promote-portal-intake-local", action="store_true", help="promote clean portal-intake drafts into ignored local provider/source JSON files")
    parser.add_argument("--portal-intake-provider-seeds", default=LOCAL_SEEDS_NAME, help="ignored local provider discovery seed file for --promote-portal-intake-local")
    parser.add_argument("--portal-intake-dataset-sources-local", default=LOCAL_DATASET_DISCOVERY_SOURCES_NAME, help="ignored local dataset discovery source file for --promote-portal-intake-local")
    parser.add_argument("--portal-intake-strict", action="store_true", help="exit with failure when portal-intake parsing finds warnings")


def portal_intake_command_active(args: argparse.Namespace) -> bool:
    return bool(args.portal_intake_report or args.write_portal_intake_json or args.promote_portal_intake_local)


def portal_intake_cli(args: argparse.Namespace) -> None:
    if not portal_intake_command_active(args):
        return
    intake_path = resolve_project_path(args.portal_intake_path)
    payload = build_portal_intake_payload(intake_path)
    summary = payload["summary"]
    print(
        "[portal-intake] "
        f"rows={summary['row_count']} actionable={summary['actionable_count']} "
        f"ignored={summary['ignored_count']} warnings={summary['warning_count']}"
    )
    for action, count in summary["actions"].items():
        print(f"[portal-intake] action {action}={count}")
    for warning in payload.get("parse_warnings", []):
        print(f"[portal-intake] warning {warning}")
    for entry in payload.get("entries", []):
        for warning in entry.get("warnings", []):
            print(f"[portal-intake] row {entry['row_number']} warning {warning}")
    if args.write_portal_intake_json:
        output_path = resolve_project_path(args.write_portal_intake_json)
        write_portal_intake_json(output_path, payload)
        print(f"[portal-intake] wrote {output_path}")
    if args.portal_intake_strict and summary["warning_count"]:
        raise SystemExit("[portal-intake] strict audit failed")
    if args.promote_portal_intake_local:
        provider_seed_path = local_config_file(args.portal_intake_provider_seeds)
        dataset_source_path = local_config_file(args.portal_intake_dataset_sources_local)
        result = promote_portal_intake_payload(payload, provider_seed_path, dataset_source_path)
        print(
            "[portal-intake] promoted "
            f"provider_seeds={result['provider_seed_count']} "
            f"dataset_sources={result['dataset_source_count']} "
            f"skipped={result['skipped_count']}"
        )
        print(f"[portal-intake] provider_seed_path={result['provider_seed_path']}")
        print(f"[portal-intake] dataset_source_path={result['dataset_source_path']}")


def write_portal_intake_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(portal_intake_payload_to_json(payload), encoding="utf-8")
