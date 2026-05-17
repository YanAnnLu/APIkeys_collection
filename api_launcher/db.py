from __future__ import annotations

import contextlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_project_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def connect_db(path: str | Path) -> sqlite3.Connection:
    path = resolve_project_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    with contextlib.suppress(sqlite3.DatabaseError):
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS providers (
            provider_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner TEXT NOT NULL,
            categories_json TEXT NOT NULL,
            geographic_scope TEXT NOT NULL,
            docs_url TEXT NOT NULL,
            api_base_url TEXT,
            signup_url TEXT,
            auth_type TEXT NOT NULL,
            key_env_var TEXT,
            license_url TEXT,
            terms_url TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS crawl_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id TEXT NOT NULL REFERENCES providers(provider_id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            status_code INTEGER,
            content_type TEXT,
            content_length INTEGER,
            title TEXT,
            sha256 TEXT,
            excerpt TEXT,
            error TEXT,
            extracted_json TEXT,
            UNIQUE(provider_id, url)
        );

        CREATE TABLE IF NOT EXISTS template_keys (
            env_var TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL REFERENCES providers(provider_id) ON DELETE CASCADE,
            auth_type TEXT NOT NULL,
            placeholder TEXT NOT NULL,
            notes TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS provider_download_state (
            provider_id TEXT PRIMARY KEY REFERENCES providers(provider_id) ON DELETE CASCADE,
            last_checked_at TEXT,
            last_downloaded_at TEXT,
            last_remote_hash TEXT,
            last_local_hash TEXT,
            remote_status TEXT NOT NULL DEFAULT 'unchecked',
            local_status TEXT NOT NULL DEFAULT 'not_imported',
            update_status TEXT NOT NULL DEFAULT 'unknown',
            dataset_path TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS datasets (
            dataset_uid TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL REFERENCES providers(provider_id) ON DELETE CASCADE,
            dataset_id TEXT NOT NULL,
            title TEXT NOT NULL,
            categories_json TEXT NOT NULL,
            data_type TEXT,
            native_format TEXT,
            geographic_scope TEXT,
            temporal_coverage TEXT,
            landing_url TEXT,
            api_url TEXT,
            license_url TEXT,
            version TEXT,
            remote_updated_at TEXT,
            remote_etag TEXT,
            remote_hash TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dataset_sync_state (
            dataset_uid TEXT PRIMARY KEY REFERENCES datasets(dataset_uid) ON DELETE CASCADE,
            last_remote_checked_at TEXT,
            last_downloaded_at TEXT,
            last_imported_at TEXT,
            remote_fingerprint TEXT,
            local_fingerprint TEXT,
            diff_status TEXT NOT NULL DEFAULT 'unknown',
            raw_path TEXT,
            curated_path TEXT,
            bridge_asset_id TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS render_bridge_assets (
            asset_id TEXT PRIMARY KEY,
            dataset_uid TEXT NOT NULL REFERENCES datasets(dataset_uid) ON DELETE CASCADE,
            renderer TEXT NOT NULL,
            asset_role TEXT NOT NULL,
            storage_format TEXT NOT NULL,
            path TEXT NOT NULL,
            spatial_index_path TEXT,
            temporal_index_path TEXT,
            checksum TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_providers_auth_type ON providers(auth_type);
        CREATE INDEX IF NOT EXISTS idx_providers_owner ON providers(owner);
        CREATE INDEX IF NOT EXISTS idx_crawl_provider ON crawl_results(provider_id);
        CREATE INDEX IF NOT EXISTS idx_datasets_provider ON datasets(provider_id);
        """
    )
    ensure_column(conn, "crawl_results", "extracted_json", "TEXT")
    conn.commit()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
