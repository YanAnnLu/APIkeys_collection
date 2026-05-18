#!/usr/bin/env python3
"""
APIkeys_collection.py

Registry-driven launcher core for a local big-data source downloader.

This tool is intentionally conservative:
- It catalogs official API/documentation/sign-up URLs as downloadable sources.
- It creates a local SQLite database named APIkeys_collection.sqlite by default.
- It generates .env.example and api_keys.txt.template placeholders.
- It does not search for, scrape, validate, or collect real API keys/secrets.
- It plans and checks downloads before later dataset adapters fetch bulk data.

Typical usage:
    python APIkeys_collection.py --init-db --seed --generate-templates
    python APIkeys_collection.py --crawl --provider noaa_ncei_cdo
    python APIkeys_collection.py --self-check
"""

from __future__ import annotations

import argparse
import csv
import contextlib
import concurrent.futures
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from api_launcher.cli_discovery import (
    add_discovery_args,
    add_local_discovery_seed,
    discover_source_candidates,
    discovery_command_active,
)
from api_launcher.cli_dataset_discovery import (
    add_dataset_discovery_args,
    dataset_discovery_command_active,
    discover_dataset_candidates_cli,
)
from api_launcher.adapter_review import adapter_review_agent_payload, adapter_review_items
from api_launcher.adapter_plan_resolver import resolve_adapter_review_plan_payload
from api_launcher.dataset_discovery import (
    DEFAULT_DATASET_DISCOVERY_SOURCES_NAME,
    DatasetCrawlOptions,
    crawl_dataset_sources,
    dataset_with_candidate_metadata,
    load_dataset_discovery_sources,
)
from api_launcher.importers.csv_importer import import_csv_manifest_to_sqlite, import_verified_csv_manifests_to_sqlite
from api_launcher.data_store_connections import data_store_profiles_from_config, test_data_store_connection
from api_launcher.database_self_check import (
    DatabaseAssetVerifier,
    database_self_check_agent_payload,
    database_self_check_issues,
)
from api_launcher.dataset_adapters import adapters_for_provider
from api_launcher.dataset_updates import DatasetUpdatePlan, plan_dataset_update
from api_launcher.dataset_versions import DatasetVersionOption, version_options_for_dataset, version_options_for_datasets
from api_launcher.db import SCRIPT_DIR, connect_db, init_db, resolve_project_path, utc_now_iso
from api_launcher.downloads.eligibility import DownloadEligibility, assess_provider_download, looks_like_direct_download
from api_launcher.downloads.plan_runner import load_download_plan_file, run_download_plan_payload
from api_launcher.environment import EnvironmentCheck, run_startup_checks
from api_launcher.event_log import latest_events, log_event, log_exception
from api_launcher.handoff import build_handoff_snapshot, render_handoff_markdown
from api_launcher.downloads.http import HTTPDownloadAdapter, download_target_from_plan_entry
from api_launcher.integrations import (
    active_ai_profile,
    active_database_client,
    active_download_policy,
    active_download_tool,
    ai_summary_profiles,
    database_client_profiles,
    download_tool_profiles,
    download_policy_from_config,
    ensure_local_integration_config,
    generate_provider_summary,
    load_integration_config,
    local_integrations_path,
    open_database_client,
    set_active_ai_profile,
    set_active_database_client,
)
from api_launcher.importers.json_importer import import_json_manifest_to_sqlite, import_verified_json_manifests_to_sqlite
from api_launcher.library_actions import LibraryContext, build_library_actions, library_action_agent_payload
from api_launcher.manifests import read_manifest
from api_launcher.models import Dataset, Provider
from api_launcher.paths import catalog_file
from api_launcher.plans import (
    build_dataset_download_plan,
    build_download_plan,
    provider_dataset_version_plan_entry,
    provider_plan_entry,
)
from api_launcher.renderer_contracts import (
    GEBCO_2025_TOPOGRAPHY_CONTRACT,
    HYG_V38_STAR_CONTRACT,
    TAICHI_GLOBAL_BATHYMETRY_CONTRACTS,
    TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID,
)
from api_launcher.downloads.repair import download_repair_agent_payload, repair_summary, scan_download_manifests
from api_launcher.repository import (
    ApiCatalogRepository,
    PROVIDERS,
    load_provider_rows,
    load_providers,
    row_categories,
    seed_providers,
)
from api_launcher.render_effects import DEFAULT_RENDER_EFFECT_LAYERS
from api_launcher.rendering_profiles import build_render_backend_profile
from api_launcher.registry import provider_from_dict
from api_launcher.simulation_bridge import DEFAULT_SIMULATION_BACKENDS, DEFAULT_SIMULATION_INPUT_CONTRACTS
from api_launcher.downloads.transfer_tools import TransferCommand, build_external_transfer_command, selected_transfer_tool, transfer_url_from_plan_entry
from api_launcher.tile_manifests import build_global_grid_manifest, write_tile_manifest
from api_launcher.unreal_bridge import build_unreal_bridge_targets


DB_NAME = "APIkeys_collection.sqlite"
ENV_TEMPLATE_NAME = ".env.example"
TEXT_TEMPLATE_NAME = "api_keys.txt.template"
KEY_REFERENCE_NAME = "APIkeys_collection_reference.json"
CREDENTIALS_TEMPLATE_NAME = "APIkeys_collection_credentials.private.template.json"
USER_AGENT = "APIkeys_collection/0.2 (+metadata-checks; downloader-launcher planning)"
DEFAULT_MAX_BYTES = 256_000
DEFAULT_TIMEOUT_SECONDS = 15.0


def safe_fetch_metadata(url: str, max_bytes: int, timeout: float) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json,text/plain,*/*;q=0.2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            content_type = response.headers.get("Content-Type", "")
            content_length = response.headers.get("Content-Length")
            raw = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        body = exc.read(min(max_bytes, 8192)) if exc.fp else b""
        return {
            "status_code": exc.code,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "content_length": None,
            "title": "",
            "sha256": hashlib.sha256(body).hexdigest() if body else "",
            "excerpt": decode_excerpt(body),
            "error": f"HTTPError: {exc}",
        }
    except Exception as exc:
        return {
            "status_code": None,
            "content_type": "",
            "content_length": None,
            "title": "",
            "sha256": "",
            "excerpt": "",
            "error": f"{type(exc).__name__}: {exc}",
        }

    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    decoded = decode_excerpt(raw)
    return {
        "status_code": int(status_code),
        "content_type": content_type,
        "content_length": parse_int_or_none(content_length),
        "title": extract_title(decoded),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "excerpt": decoded[:1000],
        "error": "",
    }


def parse_int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    with contextlib.suppress(ValueError):
        return int(value)
    return None


def decode_excerpt(raw: bytes) -> str:
    if not raw:
        return ""
    for encoding in ("utf-8", "latin-1"):
        with contextlib.suppress(UnicodeDecodeError):
            text = raw.decode(encoding, errors="replace")
            return re.sub(r"\s+", " ", text).strip()
    return ""


def extract_title(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())[:240]
    if text.lstrip().startswith("{"):
        return "JSON response"
    return text[:120]


def record_crawl_result(
    conn: sqlite3.Connection,
    provider_id: str,
    url: str,
    result: dict[str, object],
) -> None:
    conn.execute(
        """
        INSERT INTO crawl_results (
            provider_id, url, fetched_at, status_code, content_type, content_length,
            title, sha256, excerpt, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_id, url) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            status_code = excluded.status_code,
            content_type = excluded.content_type,
            content_length = excluded.content_length,
            title = excluded.title,
            sha256 = excluded.sha256,
            excerpt = excluded.excerpt,
            error = excluded.error
        """,
        (
            provider_id,
            url,
            utc_now_iso(),
            result.get("status_code"),
            result.get("content_type"),
            result.get("content_length"),
            result.get("title"),
            result.get("sha256"),
            result.get("excerpt"),
            result.get("error"),
        ),
    )
    conn.commit()
    ApiCatalogRepository(conn).refresh_provider_download_state([provider_id])


def crawl_provider(
    conn: sqlite3.Connection,
    provider: Provider,
    max_bytes: int,
    timeout: float,
    delay: float,
) -> None:
    for url in provider.target_urls():
        print(f"[crawl] {provider.provider_id}: {url}")
        result = safe_fetch_metadata(url, max_bytes=max_bytes, timeout=timeout)
        record_crawl_result(conn, provider.provider_id, url, result)
        status = result.get("status_code") or "ERR"
        title = result.get("title") or result.get("error") or ""
        print(f"        -> {status} {title}")
        if delay > 0:
            time.sleep(delay)


def crawl_providers_nonblocking(
    conn: sqlite3.Connection,
    providers: list[Provider],
    max_bytes: int,
    timeout: float,
    delay: float = 0.0,
    concurrency: int = 4,
    per_host: int = 2,
) -> None:
    del per_host
    jobs: list[tuple[str, str]] = []
    for provider in providers:
        for url in provider.target_urls():
            jobs.append((provider.provider_id, url))

    def fetch(job: tuple[str, str]) -> tuple[str, str, dict[str, object]]:
        provider_id, url = job
        result = safe_fetch_metadata(url, max_bytes=max_bytes, timeout=timeout)
        if delay > 0:
            time.sleep(delay)
        return provider_id, url, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        for provider_id, url, result in executor.map(fetch, jobs):
            record_crawl_result(conn, provider_id, url, result)


def generate_templates(conn: sqlite3.Connection, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT tk.env_var, tk.placeholder, tk.auth_type, tk.notes,
               p.provider_id, p.name, p.signup_url, p.docs_url
        FROM template_keys tk
        JOIN providers p ON p.provider_id = tk.provider_id
        ORDER BY tk.env_var
        """
    ).fetchall()
    no_key_rows = conn.execute(
        """
        SELECT provider_id, name, docs_url, auth_type
        FROM providers
        WHERE COALESCE(key_env_var, '') = ''
        ORDER BY provider_id
        """
    ).fetchall()

    env_lines = [
        "# APIkeys_collection generated template",
        "# Fill only keys you own. Do not commit real secrets.",
        "",
    ]
    text_lines = [
        "APIkeys_collection generated template",
        "Fill only keys you own. Do not paste leaked or third-party secrets.",
        "",
        "[KEYS]",
    ]
    for row in rows:
        env_lines.append(f"# {row['name']} ({row['provider_id']})")
        env_lines.append(f"# Docs: {row['docs_url']}")
        if row["signup_url"]:
            env_lines.append(f"# Signup: {row['signup_url']}")
        env_lines.append(f"{row['env_var']}={row['placeholder']}")
        env_lines.append("")

        text_lines.append(f"{row['env_var']} = {row['placeholder']}")
        text_lines.append(f"  provider: {row['name']} ({row['provider_id']})")
        text_lines.append(f"  auth: {row['auth_type']}")
        text_lines.append(f"  docs: {row['docs_url']}")
        if row["signup_url"]:
            text_lines.append(f"  signup: {row['signup_url']}")
        text_lines.append("")

    text_lines.append("[NO_KEY_OR_PUBLIC_METADATA]")
    for row in no_key_rows:
        text_lines.append(f"{row['provider_id']} | {row['auth_type']} | {row['docs_url']}")

    (output_dir / ENV_TEMPLATE_NAME).write_text("\n".join(env_lines).rstrip() + "\n", encoding="utf-8")
    (output_dir / TEXT_TEMPLATE_NAME).write_text("\n".join(text_lines).rstrip() + "\n", encoding="utf-8")
    print(f"[template] wrote {output_dir / ENV_TEMPLATE_NAME}")
    print(f"[template] wrote {output_dir / TEXT_TEMPLATE_NAME}")


def provider_catalog_rows(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute("SELECT * FROM providers ORDER BY provider_id").fetchall()
    catalog = []
    for row in rows:
        catalog.append(
            {
                "provider_id": row["provider_id"],
                "name": row["name"],
                "owner": row["owner"],
                "categories": json.loads(row["categories_json"]),
                "geographic_scope": row["geographic_scope"],
                "docs_url": row["docs_url"],
                "api_base_url": row["api_base_url"] or "",
                "signup_url": row["signup_url"] or "",
                "auth_type": row["auth_type"],
                "key_env_var": row["key_env_var"] or "",
                "license_url": row["license_url"] or "",
                "terms_url": row["terms_url"] or "",
                "notes": row["notes"] or "",
            }
        )
    return catalog


def export_json(conn: sqlite3.Connection, path: Path) -> None:
    path = resolve_project_path(path)
    path.write_text(json.dumps(provider_catalog_rows(conn), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[export] wrote {path}")


def export_csv(conn: sqlite3.Connection, path: Path) -> None:
    path = resolve_project_path(path)
    rows = provider_catalog_rows(conn)
    fieldnames = [
        "provider_id",
        "name",
        "owner",
        "categories",
        "geographic_scope",
        "docs_url",
        "api_base_url",
        "signup_url",
        "auth_type",
        "key_env_var",
        "license_url",
        "terms_url",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            copy = dict(row)
            copy["categories"] = ", ".join(copy["categories"])
            writer.writerow(copy)
    print(f"[export] wrote {path}")


def export_markdown(conn: sqlite3.Connection, path: Path) -> None:
    path = resolve_project_path(path)
    lines = [
        "# APIkeys_collection Provider Catalog",
        "",
        "| Provider | Categories | Auth | Docs | Signup |",
        "|---|---|---|---|---|",
    ]
    for row in provider_catalog_rows(conn):
        docs = f"[docs]({row['docs_url']})" if row["docs_url"] else ""
        signup = f"[signup]({row['signup_url']})" if row["signup_url"] else ""
        categories = ", ".join(row["categories"])
        lines.append(f"| {row['name']} (`{row['provider_id']}`) | {categories} | {row['auth_type']} | {docs} | {signup} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[export] wrote {path}")


def write_sample_registry(path: Path) -> None:
    path = resolve_project_path(path)
    payload = {
        "providers": [
            {
                "provider_id": "example_provider",
                "name": "Example Provider",
                "owner": "Example Organization",
                "categories": ["weather", "metadata"],
                "geographic_scope": "global",
                "docs_url": "https://example.com/docs",
                "api_base_url": "https://api.example.com/v1",
                "signup_url": "https://example.com/signup",
                "auth_type": "api_key_required",
                "key_env_var": "EXAMPLE_API_KEY",
                "secret_env_vars": [],
                "license_url": "https://example.com/license",
                "terms_url": "https://example.com/terms",
                "notes": "Official metadata endpoint only; do not add bulk data URLs here.",
                "crawl_urls": ["https://example.com/status"],
            }
        ]
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[sample] wrote {path}")


def seed_json_registry(conn: sqlite3.Connection, path: Path) -> int:
    path = resolve_project_path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    providers = [provider_from_dict(item) for item in data.get("providers", [])]
    providers = [provider for provider in providers if provider.provider_id and provider.name]
    seed_providers(conn, providers)
    return len(providers)


def write_sample_key_reference(path: Path) -> None:
    path = resolve_project_path(path)
    payload = {
        "schema_version": 1,
        "description": "Crawler credential reference. Keep real key values out of source control.",
        "crawler": {
            "relative_file": "APIkeys_collection.py",
            "path_resolution": "Crawler defaults resolve relative to this folder.",
            "downstream_renderer": "taichi_global_bathymetry.py",
            "role": "launcher credential reference only; not a secret store",
        },
        "credentials": [
            {
                "provider_id": "noaa_ncei_cdo",
                "provider_name": "NOAA NCEI Climate Data Online",
                "env_var": "NOAA_NCEI_CDO_TOKEN",
                "auth_type": "api_token_required",
                "placeholder": "paste_your_own_noaa_ncei_cdo_token_here",
                "value": "",
                "docs_url": "https://www.ncei.noaa.gov/cdo-web/webservices/v2",
                "signup_url": "https://www.ncei.noaa.gov/cdo-web/token",
                "usage": {"header": "token", "query_param": "", "example": "Send HTTP header: token=${NOAA_NCEI_CDO_TOKEN}"},
                "notes": "NOAA CDO v2 uses the token HTTP header. Leave value empty here.",
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[sample] wrote {path}")


def write_credentials_template(path: Path = Path(CREDENTIALS_TEMPLATE_NAME)) -> None:
    path = resolve_project_path(path)
    payload = {
        "schema_version": 1,
        "description": "Private credential reference for credentials you own. Keep the real file local and out of version control.",
        "security_model": {
            "preferred": "Put real secrets in environment variables or a local private file.",
            "do_not": "Do not commit this file after filling real values.",
            "template_file": CREDENTIALS_TEMPLATE_NAME,
            "private_file": "APIkeys_collection_credentials.private.json",
        },
        "credentials": [
            {
                "provider_id": "noaa_ncei_cdo",
                "provider_name": "NOAA NCEI Climate Data Online",
                "auth_method": "api_token_header",
                "env_var": "NOAA_NCEI_CDO_TOKEN",
                "value": "",
                "login_url": "https://www.ncei.noaa.gov/cdo-web/token",
                "dashboard_url": "https://www.ncei.noaa.gov/cdo-web/token",
                "notes": "NOAA CDO uses the token HTTP header. Prefer setting NOAA_NCEI_CDO_TOKEN in your shell.",
            },
            {
                "provider_id": "nasa_earthdata",
                "provider_name": "NASA Earthdata",
                "auth_method": "earthdata_login_or_token",
                "env_var": "NASA_EARTHDATA_TOKEN",
                "value": "",
                "username_env_var": "NASA_EARTHDATA_USERNAME",
                "username_value": "",
                "password_env_var": "NASA_EARTHDATA_PASSWORD",
                "password_value": "",
                "login_url": "https://urs.earthdata.nasa.gov/",
                "dashboard_url": "https://urs.earthdata.nasa.gov/profile",
                "notes": "Use only your own Earthdata credentials. Prefer env vars over plaintext values.",
            },
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[template] wrote {path}")


def print_summary(conn: sqlite3.Connection) -> None:
    provider_count = conn.execute("SELECT COUNT(*) AS n FROM providers").fetchone()["n"]
    key_count = conn.execute("SELECT COUNT(*) AS n FROM template_keys").fetchone()["n"]
    crawl_count = conn.execute("SELECT COUNT(*) AS n FROM crawl_results").fetchone()["n"]
    by_auth = conn.execute(
        "SELECT auth_type, COUNT(*) AS n FROM providers GROUP BY auth_type ORDER BY n DESC, auth_type"
    ).fetchall()
    print(f"[summary] providers={provider_count}, key_placeholders={key_count}, crawl_results={crawl_count}")
    for row in by_auth:
        print(f"          {row['auth_type']}: {row['n']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local catalog for a big-data downloader launcher.")
    parser.add_argument("--db", default=DB_NAME, help="SQLite database path")
    parser.add_argument("--init-db", action="store_true", help="create SQLite schema")
    parser.add_argument("--seed", action="store_true", help="upsert built-in provider registry")
    parser.add_argument("--seed-json", action="append", default=[], help="seed providers from a JSON registry file")
    parser.add_argument("--seed-key-reference", action="store_true", help="seed credential placeholders from the key reference file")
    parser.add_argument("--generate-templates", action="store_true", help="write .env.example and api_keys.txt.template")
    parser.add_argument("--output-dir", default=".", help="directory for generated templates")
    parser.add_argument("--crawl", action="store_true", help="fetch small metadata pages for selected providers")
    parser.add_argument("--all", action="store_true", help="crawl all providers")
    parser.add_argument("--provider", action="append", default=[], help="provider_id to crawl; can be repeated")
    parser.add_argument("--category", action="append", default=[], help="provider category filter; can be repeated")
    parser.add_argument("--auth-type", action="append", default=[], help="auth_type filter; can be repeated")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="maximum bytes to read per URL")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout seconds")
    parser.add_argument("--delay", type=float, default=0.25, help="polite delay between URL fetches")
    parser.add_argument("--list-providers", action="store_true", help="print provider ids and exit")
    parser.add_argument("--list-categories", action="store_true", help="print provider categories and exit")
    parser.add_argument("--self-check", action="store_true", help="refresh launcher remote/local status from crawl metadata")
    parser.add_argument("--verify-downloads", action="store_true", help="verify downloaded payloads against sidecar manifests")
    parser.add_argument("--verify-downloads-json", action="store_true", help="verify downloaded payloads and emit agent-readable JSON")
    parser.add_argument("--downloads-root", default="downloads", help="directory containing download sidecar manifests")
    parser.add_argument("--run-download-plan", help="run direct HTTP downloads from a plan JSON and register completed assets")
    parser.add_argument("--download-plan-limit", type=int, default=0, help="maximum direct plan entries to run; 0 means all direct entries")
    parser.add_argument("--download-timeout", type=float, default=30.0, help="HTTP timeout seconds for --run-download-plan")
    parser.add_argument("--adapter-review-plan", help="list adapter-required items from a download plan JSON")
    parser.add_argument("--adapter-review-json", action="store_true", help="emit --adapter-review-plan as agent-readable JSON")
    parser.add_argument("--resolve-adapter-plan", help="resolve reviewable resource entries in a download plan JSON")
    parser.add_argument("--write-resolved-adapter-plan", default="", help="output JSON for --resolve-adapter-plan; defaults beside the input plan")
    parser.add_argument("--keep-original-adapter-entries", action="store_true", help="keep original review entries when --resolve-adapter-plan adds direct entries")
    parser.add_argument("--import-supported-plan-results", action="store_true", help="after --run-download-plan, import supported CSV/JSON plan results into --import-sqlite-db")
    parser.add_argument("--import-csv-manifest", help="import a verified CSV/CSV.GZ payload manifest into a curated SQLite table")
    parser.add_argument("--import-verified-csv-manifests", action="store_true", help="import healthy CSV/CSV.GZ manifests from the registry into curated SQLite tables")
    parser.add_argument("--import-json-manifest", help="import a verified JSON/JSONL/GeoJSON payload manifest into a curated SQLite table")
    parser.add_argument("--import-verified-json-manifests", action="store_true", help="import healthy JSON/JSONL/GeoJSON manifests from the registry into curated SQLite tables")
    parser.add_argument("--import-sqlite-db", default="state/curated_imports.sqlite", help="target SQLite database for manifest imports")
    parser.add_argument("--import-table", default="", help="target table name for single-manifest import; defaults to dataset/version")
    parser.add_argument("--import-row-limit", type=int, default=0, help="maximum rows to import from CSV/JSON; 0 means all rows")
    parser.add_argument("--import-replace-table", action="store_true", help="drop and recreate the target table before manifest import")
    parser.add_argument("--manifest-health", action="store_true", help="print SQLite dataset manifest health summary")
    parser.add_argument("--list-manifests", action="store_true", help="print registered dataset asset manifests")
    parser.add_argument("--show-logs", type=int, default=0, help="print recent structured launcher log events")
    parser.add_argument("--handoff-report", help="write a Markdown handoff report for humans and agents")
    parser.add_argument("--unreal-bridge-plan", action="store_true", help="print planned Unreal bridge asset sync targets")
    parser.add_argument("--show-render-profile", action="append", default=[], help="print inferred renderer profile for a frontend, e.g. taichi or unreal")
    parser.add_argument("--list-render-effects", action="store_true", help="print data-driven render effect layer contracts")
    parser.add_argument("--list-simulation-contracts", action="store_true", help="print simulation bridge input/backend contracts")
    parser.add_argument("--show-library-actions", help="print Steam-like library actions for a provider/context")
    parser.add_argument("--library-actions-json", action="store_true", help="emit --show-library-actions as agent-readable JSON")
    parser.add_argument("--library-local-status", default="not_imported", help="local status for --show-library-actions")
    parser.add_argument("--library-remote-status", default="unchecked", help="remote status for --show-library-actions")
    parser.add_argument("--library-update-status", default="unknown", help="update status for --show-library-actions")
    parser.add_argument("--library-install-id", default="", help="install_id for --show-library-actions")
    parser.add_argument("--library-manifest-health", default="unknown", help="manifest health for --show-library-actions")
    parser.add_argument("--library-direct-download", action="store_true", help="mark context as having a direct download")
    parser.add_argument("--library-adapter", action="store_true", help="mark context as having a dataset adapter")
    parser.add_argument("--library-render-assets", action="store_true", help="mark context as having renderer bridge assets")
    parser.add_argument("--test-data-store", action="append", default=[], help="test data-store connection profile id; use 'all' for every configured profile")
    parser.add_argument("--self-check-databases", action="store_true", help="verify managed database assets against configured data-store checks")
    parser.add_argument("--self-check-databases-json", action="store_true", help="verify managed database assets and emit issues as agent-readable JSON")
    parser.add_argument("--generate-ai-summary", help="generate an AI description for a provider_id")
    parser.add_argument("--ai-profile", help="AI summary profile id, e.g. gemini_flash or local_ollama")
    parser.add_argument("--write-ai-summary", action="store_true", help="save generated AI summary back into provider notes when empty")
    parser.add_argument("--ai-timeout", type=float, default=30.0, help="AI summary request timeout seconds")
    parser.add_argument("--write-tile-manifest", help="write a global tile manifest skeleton JSON")
    parser.add_argument("--tile-dataset-uid", default="gebco:2025", help="dataset uid for --write-tile-manifest")
    parser.add_argument("--tile-version", default="2025", help="dataset version for --write-tile-manifest")
    parser.add_argument("--tile-lod", type=int, default=0, help="LOD number for --write-tile-manifest")
    parser.add_argument("--tile-degrees", type=float, default=30.0, help="global tile size in degrees for --write-tile-manifest")
    parser.add_argument("--tile-format", default="npy:int16:elevation", help="tile format label for --write-tile-manifest")
    parser.add_argument("--tile-role", default="data_tile", help="tile asset role for --write-tile-manifest")
    parser.add_argument("--tile-uri-template", default="tiles/{tile_id}", help="URI template for generated tile entries")
    parser.add_argument("--export-json", help="write provider catalog JSON")
    parser.add_argument("--export-csv", help="write provider catalog CSV")
    parser.add_argument("--export-markdown", help="write provider catalog Markdown")
    parser.add_argument("--export-dataset-plan", help="write adapter-discovered dataset-version download plan JSON")
    parser.add_argument("--export-candidate-plan", help="write crawler-discovered dataset candidates as a download/import plan JSON")
    parser.add_argument("--candidate-plan-status", default="approved", help="candidate status for --export-candidate-plan: needs_review, approved, planned, rejected, or all")
    parser.add_argument("--candidate-plan-dataset", action="append", default=[], help="dataset_uid to include in --export-candidate-plan; can be repeated")
    parser.add_argument("--candidate-plan-limit", type=int, default=0, help="maximum dataset-version entries to export from candidates; 0 means all")
    parser.add_argument("--mark-candidate-plan-planned", action="store_true", help="mark exported candidate datasets as planned after writing --export-candidate-plan")
    parser.add_argument("--write-sample-registry", help="write a sample provider registry JSON")
    parser.add_argument("--write-sample-key-reference", help="write a sample key reference JSON")
    parser.add_argument("--write-credentials-template", action="store_true", help="write a private credentials template")
    parser.add_argument("--discover-datasets", action="store_true", help="placeholder for future provider-specific dataset adapters")
    add_discovery_args(parser)
    add_dataset_discovery_args(parser)
    parser.add_argument("--summary", action="store_true", help="print database summary")
    return parser.parse_args(argv)


class CatalogLauncherCli:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.db_path = resolve_project_path(args.db)
        self.conn = connect_db(self.db_path)
        self.repository = ApiCatalogRepository(self.conn)

    def run(self) -> int:
        try:
            self.apply_default_action()
            self.ensure_schema()
            self.seed_sources()
            self.show_lists()
            self.write_templates()
            self.crawl_sources()
            self.refresh_state()
            self.run_download_plan()
            self.show_adapter_review_plan()
            self.resolve_adapter_plan()
            self.import_csv_manifest()
            self.import_verified_csv_manifests()
            self.import_json_manifest()
            self.import_verified_json_manifests()
            self.verify_downloads()
            self.show_manifest_health()
            self.list_manifests()
            self.show_logs()
            self.write_handoff_report()
            self.show_unreal_bridge_plan()
            self.show_render_profiles()
            self.list_render_effects()
            self.list_simulation_contracts()
            self.show_library_actions()
            self.test_data_store_connections()
            self.self_check_databases()
            self.generate_ai_summary()
            self.write_tile_manifest()
            self.export_catalogs()
            add_local_discovery_seed(self.args)
            discover_source_candidates(self.conn, self.args)
            discover_dataset_candidates_cli(self.conn, self.args)
            self.write_samples()
            self.handle_dataset_discovery()
            self.export_candidate_plan()
            self.export_dataset_plan()
            self.show_summary()
            return 0
        except Exception as exc:
            log_exception(
                "cli_failed",
                exc,
                component="cli",
                context={"db_path": str(self.db_path), "args": vars(self.args)},
            )
            raise
        finally:
            self.conn.close()

    def apply_default_action(self) -> None:
        command_flags = (
            self.args.init_db,
            self.args.seed,
            bool(self.args.seed_json),
            self.args.seed_key_reference,
            self.args.generate_templates,
            self.args.crawl,
            self.args.list_providers,
            self.args.list_categories,
            self.args.self_check,
            self.args.verify_downloads,
            self.args.verify_downloads_json,
            bool(self.args.run_download_plan),
            bool(self.args.adapter_review_plan),
            self.args.adapter_review_json,
            bool(self.args.resolve_adapter_plan),
            bool(self.args.write_resolved_adapter_plan),
            self.args.keep_original_adapter_entries,
            self.args.import_supported_plan_results,
            bool(self.args.import_csv_manifest),
            self.args.import_verified_csv_manifests,
            bool(self.args.import_json_manifest),
            self.args.import_verified_json_manifests,
            self.args.manifest_health,
            self.args.list_manifests,
            self.args.show_logs > 0,
            bool(self.args.handoff_report),
            self.args.unreal_bridge_plan,
            bool(self.args.show_render_profile),
            self.args.list_render_effects,
            self.args.list_simulation_contracts,
            bool(self.args.show_library_actions),
            self.args.library_actions_json,
            bool(self.args.test_data_store),
            self.args.self_check_databases,
            self.args.self_check_databases_json,
            bool(self.args.generate_ai_summary),
            bool(self.args.write_tile_manifest),
            bool(self.args.export_json),
            bool(self.args.export_csv),
            bool(self.args.export_markdown),
            bool(self.args.export_dataset_plan),
            bool(self.args.export_candidate_plan),
            bool(self.args.write_sample_registry),
            bool(self.args.write_sample_key_reference),
            self.args.write_credentials_template,
            self.args.discover_datasets,
            discovery_command_active(self.args),
            dataset_discovery_command_active(self.args),
            self.args.summary,
        )
        if any(command_flags):
            return
        self.args.init_db = True
        self.args.seed = True
        self.args.seed_key_reference = True
        self.args.generate_templates = True
        self.args.summary = True

    def ensure_schema(self) -> None:
        self.repository.init_schema()
        if self.args.init_db:
            print(f"[db] initialized {self.db_path}")

    def seed_sources(self) -> None:
        if self.args.seed:
            self.repository.seed_builtin_providers()
            print(f"[seed] upserted {len(PROVIDERS)} providers")
        for registry_path in self.args.seed_json:
            count = seed_json_registry(self.conn, Path(registry_path))
            print(f"[seed] upserted {count} providers from {registry_path}")
        if self.args.seed_key_reference:
            count = self.repository.seed_key_reference_if_exists(catalog_file(KEY_REFERENCE_NAME))
            print(f"[seed] upserted {count} credential references")

    def show_lists(self) -> None:
        if self.args.list_providers:
            for provider in self.selected_providers(required=False):
                print(f"{provider.provider_id:28s} {provider.auth_type:28s} {provider.name}")
        if self.args.list_categories:
            categories = sorted({category for row in load_provider_rows(self.conn) for category in row_categories(row)})
            for category in categories:
                print(category)

    def write_templates(self) -> None:
        if self.args.generate_templates:
            generate_templates(self.conn, resolve_project_path(self.args.output_dir))

    def crawl_sources(self) -> None:
        if not self.args.crawl:
            return
        for provider in self.selected_providers(required=True):
            crawl_provider(self.conn, provider, max_bytes=self.args.max_bytes, timeout=self.args.timeout, delay=self.args.delay)

    def refresh_state(self) -> None:
        if self.args.self_check:
            count = self.repository.refresh_provider_download_state(self.args.provider or None)
            print(f"[self-check] refreshed {count} provider states")

    def verify_downloads(self) -> None:
        if self.args.verify_downloads or self.args.verify_downloads_json:
            results = scan_download_manifests(resolve_project_path(self.args.downloads_root))
            summary = repair_summary(results)
            for result in results:
                if result.status == "manifest_error":
                    continue
                manifest = read_manifest(result.manifest_path)
                self.repository.upsert_dataset_asset_manifest(
                    manifest,
                    result.manifest_path,
                    status=result.status,
                    verify_error=result.message if result.needs_repair else "",
                )
                if result.status == "ok":
                    self.repository.register_downloaded_manifest_asset(manifest, result.manifest_path)
            if self.args.verify_downloads_json:
                print(json.dumps(download_repair_agent_payload(results), ensure_ascii=False, indent=2))
                return
            print(f"[verify-downloads] checked {len(results)} manifests: {summary}")
            for result in results:
                if result.needs_repair:
                    print(f"[verify-downloads] {result.status}: {result.payload_path} ({result.message})")

    def run_download_plan(self) -> None:
        if not self.args.run_download_plan:
            return
        payload = load_download_plan_file(resolve_project_path(self.args.run_download_plan))
        result = run_download_plan_payload(
            payload,
            self.repository,
            policy=active_download_policy(),
            timeout=self.args.download_timeout,
            limit=self.args.download_plan_limit,
            import_supported_results=self.args.import_supported_plan_results,
            import_sqlite_path=resolve_project_path(self.args.import_sqlite_db),
            import_row_limit=self.args.import_row_limit,
            import_replace=self.args.import_replace_table,
        )
        print(
            "[download-plan] "
            f"entries={result.entry_count} submitted={result.submitted} "
            f"completed={result.completed} failed={result.failed} "
            f"skipped={result.skipped} registered_assets={result.registered_assets} "
            f"imported={result.imported} import_skipped={result.import_skipped} import_failed={result.import_failed}"
        )
        for error in result.errors:
            print(f"[download-plan] error {error}")

    def show_adapter_review_plan(self) -> None:
        if not self.args.adapter_review_plan:
            return
        payload = load_download_plan_file(resolve_project_path(self.args.adapter_review_plan))
        if self.args.adapter_review_json:
            print(json.dumps(adapter_review_agent_payload(payload), ensure_ascii=False, indent=2))
            return
        items = adapter_review_items(payload)
        adapter_count = len({item.adapter_id for item in items})
        print(f"[adapter-review] items={len(items)} adapters={adapter_count}")
        for item in items:
            print(
                "[adapter-review] "
                f"#{item.plan_index} provider={item.provider_id} dataset={item.dataset_id or '-'} "
                f"version={item.version or '-'} adapter={item.adapter_id} action={item.required_action} "
                f"source={item.source_url or item.landing_url or '-'}"
            )
            if item.reason:
                print(f"[adapter-review]    reason={item.reason}")

    def resolve_adapter_plan(self) -> None:
        if not self.args.resolve_adapter_plan:
            return
        input_path = resolve_project_path(self.args.resolve_adapter_plan)
        payload = load_download_plan_file(input_path)
        resolved_payload, result = resolve_adapter_review_plan_payload(
            payload,
            downloads_root=self.args.downloads_root,
            keep_original_review_entries=self.args.keep_original_adapter_entries,
        )
        if self.args.write_resolved_adapter_plan:
            output_path = resolve_project_path(self.args.write_resolved_adapter_plan)
        else:
            output_path = input_path.with_name(f"{input_path.stem}.resolved{input_path.suffix}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(resolved_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            "[adapter-resolve] "
            f"wrote {output_path} entries={result.entry_count}->{result.output_entry_count} "
            f"resolved={result.resolved_review_entries} unresolved={result.unresolved_review_entries} "
            f"direct_added={result.direct_entries_added}"
        )
        for warning in result.warnings:
            print(f"[adapter-resolve] warning {warning}")

    def import_csv_manifest(self) -> None:
        if not self.args.import_csv_manifest:
            return
        result = import_csv_manifest_to_sqlite(
            resolve_project_path(self.args.import_csv_manifest),
            resolve_project_path(self.args.import_sqlite_db),
            self.repository,
            table_name=self.args.import_table,
            replace=self.args.import_replace_table,
            row_limit=self.args.import_row_limit,
        )
        print(
            "[csv-import] "
            f"provider={result.provider_id} table={result.table_name} rows={result.rows_imported} "
            f"columns={len(result.columns)} sqlite={result.sqlite_path} asset={result.table_asset_id}"
        )

    def import_verified_csv_manifests(self) -> None:
        if not self.args.import_verified_csv_manifests:
            return
        result = import_verified_csv_manifests_to_sqlite(
            self.repository,
            resolve_project_path(self.args.import_sqlite_db),
            provider_ids=self.args.provider or None,
            replace=self.args.import_replace_table,
            row_limit=self.args.import_row_limit,
        )
        print(
            "[csv-import-batch] "
            f"checked={result.checked} imported={result.imported} skipped={result.skipped} "
            f"non_csv={result.skipped_non_csv} unhealthy={result.skipped_unhealthy} "
            f"existing={result.skipped_existing} failed={result.failed} sqlite={resolve_project_path(self.args.import_sqlite_db)}"
        )
        for item in result.results:
            print(f"[csv-import-batch] imported provider={item.provider_id} table={item.table_name} rows={item.rows_imported}")
        for error in result.errors:
            print(f"[csv-import-batch] error {error}")

    def import_json_manifest(self) -> None:
        if not self.args.import_json_manifest:
            return
        result = import_json_manifest_to_sqlite(
            resolve_project_path(self.args.import_json_manifest),
            resolve_project_path(self.args.import_sqlite_db),
            self.repository,
            table_name=self.args.import_table,
            replace=self.args.import_replace_table,
            row_limit=self.args.import_row_limit,
        )
        print(
            "[json-import] "
            f"provider={result.provider_id} table={result.table_name} rows={result.rows_imported} "
            f"columns={len(result.columns)} shape={result.source_shape} sqlite={result.sqlite_path} "
            f"asset={result.table_asset_id}"
        )

    def import_verified_json_manifests(self) -> None:
        if not self.args.import_verified_json_manifests:
            return
        result = import_verified_json_manifests_to_sqlite(
            self.repository,
            resolve_project_path(self.args.import_sqlite_db),
            provider_ids=self.args.provider or None,
            replace=self.args.import_replace_table,
            row_limit=self.args.import_row_limit,
        )
        print(
            "[json-import-batch] "
            f"checked={result.checked} imported={result.imported} skipped={result.skipped} "
            f"non_json={result.skipped_non_json} unhealthy={result.skipped_unhealthy} "
            f"existing={result.skipped_existing} failed={result.failed} sqlite={resolve_project_path(self.args.import_sqlite_db)}"
        )
        for item in result.results:
            print(
                "[json-import-batch] "
                f"imported provider={item.provider_id} table={item.table_name} "
                f"rows={item.rows_imported} shape={item.source_shape}"
            )
        for error in result.errors:
            print(f"[json-import-batch] error {error}")

    def show_manifest_health(self) -> None:
        if self.args.manifest_health:
            summary = self.repository.dataset_asset_manifest_health_summary()
            total = sum(summary.values())
            print(f"[manifest-health] total={total} {summary}")

    def list_manifests(self) -> None:
        if self.args.list_manifests:
            records = self.repository.list_dataset_asset_manifests()
            if not records:
                print("[manifests] no registered manifests")
                return
            for record in records:
                print(
                    "[manifest] "
                    f"{record.status:18s} "
                    f"{record.provider_id:24s} "
                    f"{record.dataset_id or '-':24s} "
                    f"{record.version or '-':10s} "
                    f"{record.path}"
                )

    def show_logs(self) -> None:
        if self.args.show_logs > 0:
            for event in latest_events(self.args.show_logs):
                print(
                    "[log] "
                    f"{event.get('timestamp', '')} "
                    f"{event.get('level', '')} "
                    f"{event.get('component', '')}:{event.get('event', '')} "
                    f"{event.get('message', '')}"
                )

    def write_handoff_report(self) -> None:
        if self.args.handoff_report:
            snapshot = build_handoff_snapshot(self.repository)
            output_path = resolve_project_path(self.args.handoff_report)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(render_handoff_markdown(snapshot), encoding="utf-8")
            print(f"[handoff] wrote {output_path}")

    def show_unreal_bridge_plan(self) -> None:
        if self.args.unreal_bridge_plan:
            targets = build_unreal_bridge_targets(self.repository.list_render_bridge_assets())
            if not targets:
                print("[unreal] no render bridge assets registered")
                return
            for target in targets:
                print(f"[unreal] {target.status:14s} {target.asset_role:18s} {target.source_path} -> {target.target_path or target.message}")

    def show_render_profiles(self) -> None:
        for frontend in self.args.show_render_profile:
            profile = build_render_backend_profile(frontend)
            backend_order = ",".join(profile.backend_order) if profile.backend_order else "-"
            graphics_order = ",".join(profile.graphics_api_order) if profile.graphics_api_order else "-"
            print(
                "[render-profile] "
                f"{profile.id} frontend={profile.frontend} platform={profile.platform_name} "
                f"tier={profile.performance_tier} backends={backend_order} graphics={graphics_order} "
                f"tiles={profile.max_parallel_tiles} radius={profile.default_stream_radius_tiles} fps={profile.target_fps}"
            )

    def list_render_effects(self) -> None:
        if not self.args.list_render_effects:
            return
        for layer in DEFAULT_RENDER_EFFECT_LAYERS:
            datasets = ",".join(layer.driving_datasets)
            requirements = ",".join(layer.data_requirements)
            print(
                "[render-effect] "
                f"{layer.layer_id} domain={layer.domain} datasets={datasets} "
                f"requirements={requirements}"
            )

    def list_simulation_contracts(self) -> None:
        if not self.args.list_simulation_contracts:
            return
        for contract in DEFAULT_SIMULATION_INPUT_CONTRACTS:
            required = ",".join(contract.required_roles)
            optional = ",".join(contract.optional_roles) or "-"
            print(
                "[simulation-input] "
                f"{contract.input_id} domain={contract.domain} required={required} optional={optional}"
            )
        for backend in DEFAULT_SIMULATION_BACKENDS:
            inputs = ",".join(backend.input_contracts)
            outputs = ",".join(backend.output_roles)
            print(
                "[simulation-backend] "
                f"{backend.backend_id} domain={backend.domain} status={backend.implementation_status} "
                f"maturity={backend.maturity} inputs={inputs} outputs={outputs}"
            )

    def show_library_actions(self) -> None:
        if self.args.library_actions_json and not self.args.show_library_actions:
            raise RuntimeError("--library-actions-json requires --show-library-actions PROVIDER_ID")
        if not self.args.show_library_actions:
            return
        context = LibraryContext(
            provider_id=self.args.show_library_actions,
            local_status=self.args.library_local_status,
            remote_status=self.args.library_remote_status,
            update_status=self.args.library_update_status,
            install_id=self.args.library_install_id,
            manifest_health=self.args.library_manifest_health,
            has_direct_download=self.args.library_direct_download,
            has_adapter=self.args.library_adapter,
            has_render_assets=self.args.library_render_assets,
        )
        if self.args.library_actions_json:
            print(json.dumps(library_action_agent_payload(context), ensure_ascii=False, indent=2))
            return
        for action in build_library_actions(context):
            status = "enabled" if action.enabled else "disabled"
            print(
                "[library-action] "
                f"{action.action_id} {status} risk={action.risk} label={action.label} reason={action.reason}"
            )

    def test_data_store_connections(self) -> None:
        if not self.args.test_data_store:
            return
        profiles = data_store_profiles_from_config(load_integration_config())
        requested = {value.strip() for value in self.args.test_data_store if value.strip()}
        if "all" in {value.lower() for value in requested}:
            selected = profiles
        else:
            selected = tuple(profile for profile in profiles if profile.profile_id in requested)
            missing = sorted(requested - {profile.profile_id for profile in selected})
            if missing:
                raise RuntimeError(f"Unknown data-store connection profile(s): {', '.join(missing)}")
        for profile in selected:
            result = test_data_store_connection(profile)
            details = json.dumps(result.details, ensure_ascii=False, sort_keys=True)
            print(
                "[data-store] "
                f"{result.profile_id} status={result.status} engine={result.engine} "
                f"message={result.message} details={details}"
            )

    def self_check_databases(self) -> None:
        if not (self.args.self_check_databases or self.args.self_check_databases_json):
            return
        profiles = data_store_profiles_from_config(load_integration_config())
        summary = self.repository.verify_provider_assets(
            self.args.provider or None,
            verifier=DatabaseAssetVerifier(profiles),
            asset_kinds=("database", "table"),
        )
        if not self.args.self_check_databases_json:
            print(f"[database-self-check] {summary}")
        issues = database_self_check_issues(self.conn, self.args.provider or None)
        if self.args.self_check_databases_json:
            print(json.dumps(database_self_check_agent_payload(summary, issues), ensure_ascii=False, indent=2))
            return
        for issue in issues:
            suggestion = issue.repair_suggestion()
            print(
                "[database-self-check] "
                f"{issue.provider_id} {issue.asset_kind} {issue.engine or '-'}:{issue.asset_name} "
                f"status={issue.status} suggestion={suggestion.action_id} error={issue.error or '-'}"
            )

    def generate_ai_summary(self) -> None:
        if not self.args.generate_ai_summary:
            return
        providers = self.repository.load_providers([self.args.generate_ai_summary])
        if not providers:
            raise RuntimeError(f"Unknown provider_id: {self.args.generate_ai_summary}")
        provider = providers[0]
        summary = generate_provider_summary(provider, profile_id=self.args.ai_profile, timeout=self.args.ai_timeout)
        print(f"[ai-summary] provider={provider.provider_id} profile={self.args.ai_profile or 'active'}")
        print(summary)
        if self.args.write_ai_summary and not provider.notes:
            self.repository.upsert_provider(
                Provider(
                    provider_id=provider.provider_id,
                    name=provider.name,
                    owner=provider.owner,
                    categories=provider.categories,
                    geographic_scope=provider.geographic_scope,
                    docs_url=provider.docs_url,
                    api_base_url=provider.api_base_url,
                    signup_url=provider.signup_url,
                    auth_type=provider.auth_type,
                    key_env_var=provider.key_env_var,
                    secret_env_vars=provider.secret_env_vars,
                    license_url=provider.license_url,
                    terms_url=provider.terms_url,
                    notes=summary,
                    crawl_urls=provider.crawl_urls,
                )
            )
            print("[ai-summary] saved to provider notes")

    def write_tile_manifest(self) -> None:
        if not self.args.write_tile_manifest:
            return
        manifest = build_global_grid_manifest(
            dataset_uid=self.args.tile_dataset_uid,
            version=self.args.tile_version,
            lod=self.args.tile_lod,
            lon_step_degrees=self.args.tile_degrees,
            lat_step_degrees=self.args.tile_degrees,
            uri_template=self.args.tile_uri_template,
            tile_format=self.args.tile_format,
            role=self.args.tile_role,
            metadata={
                "status": "skeleton",
                "generated_by": "APIkeys_collection --write-tile-manifest",
            },
        )
        output = write_tile_manifest(manifest, resolve_project_path(self.args.write_tile_manifest))
        print(f"[tile-manifest] wrote {output} tiles={len(manifest.tiles)}")

    def export_catalogs(self) -> None:
        exporters = (
            (self.args.export_json, export_json),
            (self.args.export_csv, export_csv),
            (self.args.export_markdown, export_markdown),
        )
        for output_path, exporter in exporters:
            if output_path:
                exporter(self.conn, Path(output_path))

    def write_samples(self) -> None:
        sample_writers = (
            (self.args.write_sample_registry, write_sample_registry),
            (self.args.write_sample_key_reference, write_sample_key_reference),
        )
        for output_path, writer in sample_writers:
            if output_path:
                writer(Path(output_path))
        if self.args.write_credentials_template:
            write_credentials_template()

    def handle_dataset_discovery(self) -> None:
        if self.args.discover_datasets:
            providers = self.selected_providers(required=False) if self.args.provider else load_providers(self.conn)
            discovered = 0
            for provider in providers:
                for adapter in adapters_for_provider(provider):
                    datasets = adapter.discover(provider)
                    for dataset in datasets:
                        self.repository.upsert_dataset(dataset)
                    discovered += len(datasets)
                    print(f"[dataset] {provider.provider_id}: {len(datasets)} datasets via {adapter.__class__.__name__}")
            if discovered == 0:
                print("[dataset] no dataset adapters matched the selected providers")

    def export_candidate_plan(self) -> None:
        if not self.args.export_candidate_plan:
            return
        provider_filter = set(self.args.provider or [])
        if self.args.candidate_plan_dataset:
            datasets = []
            for dataset_uid in self.args.candidate_plan_dataset:
                dataset = self.repository.get_dataset(dataset_uid)
                if dataset is None:
                    raise SystemExit(f"Unknown dataset_uid for --candidate-plan-dataset: {dataset_uid}")
                if not dataset.metadata.get("candidate_status"):
                    raise SystemExit(f"Dataset is not a crawler candidate: {dataset_uid}")
                datasets.append(dataset)
        else:
            datasets = self.repository.list_dataset_candidates(self.args.candidate_plan_status)
        if provider_filter:
            datasets = [dataset for dataset in datasets if dataset.provider_id in provider_filter]

        provider_map = {provider.provider_id: provider for provider in load_providers(self.conn)}
        entries: list[dict[str, object]] = []
        planned_dataset_uids: set[str] = set()
        missing_provider_ids: set[str] = set()
        for dataset in datasets:
            provider = provider_map.get(dataset.provider_id)
            if provider is None:
                missing_provider_ids.add(dataset.provider_id)
                continue
            for option in version_options_for_dataset(dataset):
                if self.args.candidate_plan_limit and len(entries) >= self.args.candidate_plan_limit:
                    break
                entry = provider_dataset_version_plan_entry(
                    provider,
                    dataset,
                    option,
                    downloads_root=self.args.downloads_root,
                )
                entry["candidate_review"] = {
                    "candidate_status": dataset.metadata.get("candidate_status") or "",
                    "discovery_source_id": dataset.metadata.get("discovery_source_id") or "",
                    "discovery_source_type": dataset.metadata.get("discovery_source_type") or "",
                    "source_url": dataset.metadata.get("source_url") or "",
                    "confidence": dataset.metadata.get("confidence") or "",
                }
                entries.append(entry)
                planned_dataset_uids.add(dataset.dataset_uid)
            if self.args.candidate_plan_limit and len(entries) >= self.args.candidate_plan_limit:
                break

        output_path = resolve_project_path(self.args.export_candidate_plan)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_dataset_download_plan(entries, plan_name=output_path.stem)
        payload["source"] = {
            "kind": "crawler_dataset_candidates",
            "status_filter": self.args.candidate_plan_status,
            "dataset_uid_filter": list(self.args.candidate_plan_dataset),
            "candidate_count": len(datasets),
            "missing_provider_ids": sorted(missing_provider_ids),
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if self.args.mark_candidate_plan_planned:
            for dataset_uid in planned_dataset_uids:
                self.repository.mark_dataset_candidate_status(
                    dataset_uid,
                    "planned",
                    reviewed_by="cli",
                    note=f"Exported to candidate plan: {output_path}",
                )

        direct_count = int(payload["summary"]["direct_download_count"])
        review_count = int(payload["summary"]["review_required_count"])
        print(
            "[candidate-plan] "
            f"wrote {output_path} candidates={len(datasets)} entries={len(entries)} "
            f"direct={direct_count} review_required={review_count} missing_providers={len(missing_provider_ids)}"
        )
        for provider_id in sorted(missing_provider_ids):
            print(f"[candidate-plan] missing_provider {provider_id}")

    def export_dataset_plan(self) -> None:
        if not self.args.export_dataset_plan:
            return
        providers = self.selected_providers(required=False) if (
            self.args.provider or self.args.category or self.args.auth_type or self.args.all
        ) else load_providers(self.conn)
        entries: list[dict[str, object]] = []
        discovered_count = 0
        for provider in providers:
            datasets = list(self.repository.list_datasets(provider.provider_id))
            if not datasets:
                for adapter in adapters_for_provider(provider):
                    discovered = adapter.discover(provider)
                    for dataset in discovered:
                        self.repository.upsert_dataset(dataset)
                    datasets.extend(discovered)
                    discovered_count += len(discovered)
            for dataset in datasets:
                for option in version_options_for_dataset(dataset):
                    entries.append(
                        provider_dataset_version_plan_entry(
                            provider,
                            dataset,
                            option,
                            downloads_root=self.args.downloads_root,
                        )
                    )
        output_path = resolve_project_path(self.args.export_dataset_plan)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_dataset_download_plan(entries, plan_name=output_path.stem)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            "[dataset-plan] "
            f"wrote {output_path} entries={len(entries)} discovered={discovered_count}"
        )

    def show_summary(self) -> None:
        if self.args.summary:
            print_summary(self.conn)

    def selected_providers(self, required: bool) -> list[Provider]:
        if self.args.all:
            return load_providers(self.conn, categories=self.args.category or None, auth_types=self.args.auth_type or None)
        if required and not self.args.provider and not self.args.category and not self.args.auth_type:
            raise SystemExit("--crawl requires --provider PROVIDER_ID, --category CATEGORY, --auth-type AUTH_TYPE, or --all")
        providers = load_providers(self.conn, self.args.provider or None, self.args.category or None, self.args.auth_type or None)
        missing = sorted(set(self.args.provider) - {provider.provider_id for provider in providers})
        if missing:
            raise SystemExit(f"Unknown provider_id(s): {', '.join(missing)}")
        return providers


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return CatalogLauncherCli(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
