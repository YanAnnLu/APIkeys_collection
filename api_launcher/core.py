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
from api_launcher.dataset_adapters import adapters_for_provider
from api_launcher.dataset_updates import DatasetUpdatePlan, plan_dataset_update
from api_launcher.dataset_versions import DatasetVersionOption, version_options_for_dataset, version_options_for_datasets
from api_launcher.db import SCRIPT_DIR, connect_db, init_db, resolve_project_path, utc_now_iso
from api_launcher.download_eligibility import DownloadEligibility, assess_provider_download, looks_like_direct_download
from api_launcher.environment import EnvironmentCheck, run_startup_checks
from api_launcher.event_log import latest_events, log_event, log_exception
from api_launcher.http_downloader import HTTPDownloadAdapter, download_target_from_plan_entry
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
    local_integrations_path,
    open_database_client,
    set_active_database_client,
)
from api_launcher.models import Dataset, Provider
from api_launcher.paths import catalog_file
from api_launcher.plans import build_download_plan
from api_launcher.renderer_contracts import (
    GEBCO_2025_TOPOGRAPHY_CONTRACT,
    HYG_V38_STAR_CONTRACT,
    TAICHI_GLOBAL_BATHYMETRY_CONTRACTS,
    TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID,
)
from api_launcher.repair import repair_summary, scan_download_manifests
from api_launcher.repository import (
    ApiCatalogRepository,
    PROVIDERS,
    load_provider_rows,
    load_providers,
    row_categories,
    seed_providers,
)
from api_launcher.registry import provider_from_dict
from api_launcher.transfer_tools import TransferCommand, build_external_transfer_command, selected_transfer_tool, transfer_url_from_plan_entry


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
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
    parser.add_argument("--show-logs", type=int, default=0, help="print recent structured launcher log events")
    parser.add_argument("--export-json", help="write provider catalog JSON")
    parser.add_argument("--export-csv", help="write provider catalog CSV")
    parser.add_argument("--export-markdown", help="write provider catalog Markdown")
    parser.add_argument("--write-sample-registry", help="write a sample provider registry JSON")
    parser.add_argument("--write-sample-key-reference", help="write a sample key reference JSON")
    parser.add_argument("--write-credentials-template", action="store_true", help="write a private credentials template")
    parser.add_argument("--discover-datasets", action="store_true", help="placeholder for future provider-specific dataset adapters")
    add_discovery_args(parser)
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
            self.verify_downloads()
            self.show_logs()
            self.export_catalogs()
            add_local_discovery_seed(self.args)
            discover_source_candidates(self.conn, self.args)
            self.write_samples()
            self.handle_dataset_discovery()
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
            self.args.show_logs > 0,
            bool(self.args.export_json),
            bool(self.args.export_csv),
            bool(self.args.export_markdown),
            bool(self.args.write_sample_registry),
            bool(self.args.write_sample_key_reference),
            self.args.write_credentials_template,
            self.args.discover_datasets,
            discovery_command_active(self.args),
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
        if self.args.verify_downloads:
            results = scan_download_manifests()
            summary = repair_summary(results)
            print(f"[verify-downloads] checked {len(results)} manifests: {summary}")
            for result in results:
                if result.needs_repair:
                    print(f"[verify-downloads] {result.status}: {result.payload_path} ({result.message})")

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
