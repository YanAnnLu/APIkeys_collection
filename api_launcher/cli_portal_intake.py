from __future__ import annotations

import argparse
from pathlib import Path

from api_launcher.db import resolve_project_path
from api_launcher.portal_intake import (
    DEFAULT_PORTAL_INTAKE_PATH,
    build_portal_intake_payload,
    portal_intake_payload_to_json,
)


def add_portal_intake_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--portal-intake-report", action="store_true", help="parse the team database-portal intake Markdown and print an engineering summary")
    parser.add_argument("--portal-intake-path", default=DEFAULT_PORTAL_INTAKE_PATH, help="Markdown file containing the team database-portal intake table")
    parser.add_argument("--write-portal-intake-json", default="", help="write the parsed portal-intake review payload to JSON")
    parser.add_argument("--portal-intake-strict", action="store_true", help="exit with failure when portal-intake parsing finds warnings")


def portal_intake_command_active(args: argparse.Namespace) -> bool:
    return bool(args.portal_intake_report or args.write_portal_intake_json)


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


def write_portal_intake_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(portal_intake_payload_to_json(payload), encoding="utf-8")
