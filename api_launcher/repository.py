from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable

from api_launcher.asset_roles import normalize_asset_role
from api_launcher.asset_verifier import AssetRecord, AssetVerifier, RegistryOnlyVerifier
from api_launcher.db import init_db, resolve_project_path, utc_now_iso
from api_launcher.manifests import AssetManifest
from api_launcher.models import Dataset, DatasetAssetManifestRecord, Provider, ProviderCatalogEntry, RenderBridgeAsset
from api_launcher.paths import catalog_file
from api_launcher.provenance import normalize_source_format
from api_launcher.registry import PROVIDER_CATALOG_NAME, load_provider_catalog
from api_launcher.sql_assets import database_uninstall_command


PROVIDERS: tuple[Provider, ...] = load_provider_catalog(catalog_file(PROVIDER_CATALOG_NAME))


def seed_providers(conn: sqlite3.Connection, providers: Iterable[Provider]) -> None:
    now = utc_now_iso()
    for provider in providers:
        existing = conn.execute(
            "SELECT created_at FROM providers WHERE provider_id = ?",
            (provider.provider_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO providers (
                provider_id, name, owner, categories_json, geographic_scope,
                docs_url, api_base_url, signup_url, auth_type, key_env_var,
                license_url, terms_url, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                name = excluded.name,
                owner = excluded.owner,
                categories_json = excluded.categories_json,
                geographic_scope = excluded.geographic_scope,
                docs_url = excluded.docs_url,
                api_base_url = excluded.api_base_url,
                signup_url = excluded.signup_url,
                auth_type = excluded.auth_type,
                key_env_var = excluded.key_env_var,
                license_url = excluded.license_url,
                terms_url = excluded.terms_url,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                provider.provider_id,
                provider.name,
                provider.owner,
                json.dumps(provider.categories, ensure_ascii=True),
                provider.geographic_scope,
                provider.docs_url,
                provider.api_base_url,
                provider.signup_url,
                provider.auth_type,
                provider.key_env_var,
                provider.license_url,
                provider.terms_url,
                provider.notes,
                created_at,
                now,
            ),
        )
        for env_var in provider.template_env_vars():
            placeholder = f"your_{env_var.lower()}"
            if env_var == "NOAA_NCEI_CDO_TOKEN":
                placeholder = "paste_your_own_noaa_ncei_cdo_token_here"
            conn.execute(
                """
                INSERT INTO template_keys (
                    env_var, provider_id, auth_type, placeholder, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(env_var) DO UPDATE SET
                    provider_id = excluded.provider_id,
                    auth_type = excluded.auth_type,
                    placeholder = excluded.placeholder,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    env_var,
                    provider.provider_id,
                    provider.auth_type,
                    placeholder,
                    provider.notes,
                    now,
                ),
            )
        conn.execute(
            """
            INSERT INTO provider_download_state (
                provider_id, remote_status, local_status, update_status, updated_at
            ) VALUES (?, 'unchecked', 'not_imported', 'unknown', ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                updated_at = provider_download_state.updated_at
            """,
            (provider.provider_id, now),
        )
        conn.execute(
            """
            INSERT INTO provider_preferences (
                provider_id, is_starred, display_order, updated_at
            ) VALUES (?, 0, 0, ?)
            ON CONFLICT(provider_id) DO NOTHING
            """,
            (provider.provider_id, now),
        )
    conn.commit()


def provider_from_row(row: sqlite3.Row) -> Provider:
    return Provider(
        provider_id=row["provider_id"],
        name=row["name"],
        owner=row["owner"],
        categories=tuple(json.loads(row["categories_json"])),
        geographic_scope=row["geographic_scope"],
        docs_url=row["docs_url"],
        api_base_url=row["api_base_url"] or "",
        signup_url=row["signup_url"] or "",
        auth_type=row["auth_type"],
        key_env_var=row["key_env_var"] or "",
        license_url=row["license_url"] or "",
        terms_url=row["terms_url"] or "",
        notes=row["notes"] or "",
    )


def row_categories(row: sqlite3.Row) -> tuple[str, ...]:
    return tuple(json.loads(row["categories_json"]))


def provider_row_matches(row: sqlite3.Row, categories: list[str] | None, auth_types: list[str] | None) -> bool:
    if categories:
        wanted = {value.lower() for value in categories}
        row_values = {value.lower() for value in row_categories(row)}
        if not wanted.intersection(row_values):
            return False
    if auth_types and row["auth_type"] not in set(auth_types):
        return False
    return True


def load_provider_rows(
    conn: sqlite3.Connection,
    provider_ids: list[str] | None = None,
    categories: list[str] | None = None,
    auth_types: list[str] | None = None,
) -> list[sqlite3.Row]:
    if provider_ids:
        placeholders = ",".join("?" for _ in provider_ids)
        rows = conn.execute(
            f"SELECT * FROM providers WHERE provider_id IN ({placeholders}) ORDER BY provider_id",
            provider_ids,
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM providers ORDER BY provider_id").fetchall()
    return [row for row in rows if provider_row_matches(row, categories, auth_types)]


def load_providers(
    conn: sqlite3.Connection,
    provider_ids: list[str] | None = None,
    categories: list[str] | None = None,
    auth_types: list[str] | None = None,
) -> list[Provider]:
    rows = load_provider_rows(conn, provider_ids, categories, auth_types)
    return [provider_from_row(row) for row in rows]


def dataset_from_row(row: sqlite3.Row) -> Dataset:
    return Dataset(
        dataset_uid=row["dataset_uid"],
        provider_id=row["provider_id"],
        dataset_id=row["dataset_id"],
        title=row["title"],
        categories=tuple(json.loads(row["categories_json"])),
        data_type=row["data_type"] or "",
        native_format=row["native_format"] or "",
        geographic_scope=row["geographic_scope"] or "",
        temporal_coverage=row["temporal_coverage"] or "",
        landing_url=row["landing_url"] or "",
        api_url=row["api_url"] or "",
        license_url=row["license_url"] or "",
        version=row["version"] or "",
        remote_updated_at=row["remote_updated_at"] or "",
        remote_etag=row["remote_etag"] or "",
        remote_hash=row["remote_hash"] or "",
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def render_bridge_asset_from_row(row: sqlite3.Row) -> RenderBridgeAsset:
    return RenderBridgeAsset(
        asset_id=row["asset_id"],
        dataset_uid=row["dataset_uid"],
        renderer=row["renderer"],
        asset_role=row["asset_role"],
        storage_format=row["storage_format"],
        path=row["path"],
        spatial_index_path=row["spatial_index_path"] or "",
        temporal_index_path=row["temporal_index_path"] or "",
        checksum=row["checksum"] or "",
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def dataset_asset_manifest_from_row(row: sqlite3.Row) -> DatasetAssetManifestRecord:
    return DatasetAssetManifestRecord(
        manifest_id=row["manifest_id"],
        provider_id=row["provider_id"],
        dataset_uid=row["dataset_uid"] or "",
        dataset_id=row["dataset_id"] or "",
        version=row["version"] or "",
        path=row["path"],
        manifest_path=row["manifest_path"],
        source_url=row["source_url"] or "",
        size_bytes=int(row["size_bytes"] or 0),
        sha256=row["sha256"],
        schema_fingerprint=row["schema_fingerprint"] or "",
        status=row["status"] or "unknown",
        last_verified_at=row["last_verified_at"] or "",
        last_verify_error=row["last_verify_error"] or "",
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def dataset_manifest_id(provider_id: str, dataset_uid: str, dataset_id: str, version: str, path: str) -> str:
    value = "::".join([provider_id, dataset_uid, dataset_id, version, path])
    return "manifest_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


class ApiCatalogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def init_schema(self) -> None:
        init_db(self.conn)

    def seed_builtin_providers(self) -> None:
        seed_providers(self.conn, PROVIDERS)

    def upsert_provider(self, provider: Provider) -> None:
        seed_providers(self.conn, (provider,))

    def load_providers(self, provider_ids: list[str] | None = None) -> list[Provider]:
        return load_providers(self.conn, provider_ids)

    def upsert_dataset(self, dataset: Dataset) -> None:
        now = utc_now_iso()
        existing = self.conn.execute(
            "SELECT created_at FROM datasets WHERE dataset_uid = ?",
            (dataset.dataset_uid,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        self.conn.execute(
            """
            INSERT INTO datasets (
                dataset_uid, provider_id, dataset_id, title, categories_json,
                data_type, native_format, geographic_scope, temporal_coverage,
                landing_url, api_url, license_url, version, remote_updated_at,
                remote_etag, remote_hash, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_uid) DO UPDATE SET
                provider_id = excluded.provider_id,
                dataset_id = excluded.dataset_id,
                title = excluded.title,
                categories_json = excluded.categories_json,
                data_type = excluded.data_type,
                native_format = excluded.native_format,
                geographic_scope = excluded.geographic_scope,
                temporal_coverage = excluded.temporal_coverage,
                landing_url = excluded.landing_url,
                api_url = excluded.api_url,
                license_url = excluded.license_url,
                version = excluded.version,
                remote_updated_at = excluded.remote_updated_at,
                remote_etag = excluded.remote_etag,
                remote_hash = excluded.remote_hash,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                dataset.dataset_uid,
                dataset.provider_id,
                dataset.dataset_id,
                dataset.title,
                json.dumps(dataset.categories, ensure_ascii=True),
                dataset.data_type,
                dataset.native_format,
                dataset.geographic_scope,
                dataset.temporal_coverage,
                dataset.landing_url,
                dataset.api_url,
                dataset.license_url,
                dataset.version,
                dataset.remote_updated_at,
                dataset.remote_etag,
                dataset.remote_hash,
                json.dumps(dataset.metadata, ensure_ascii=False, sort_keys=True),
                created_at,
                now,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO dataset_sync_state (
                dataset_uid, diff_status, updated_at
            ) VALUES (?, 'unknown', ?)
            ON CONFLICT(dataset_uid) DO NOTHING
            """,
            (dataset.dataset_uid, now),
        )
        self.conn.commit()

    def list_datasets(self, provider_id: str | None = None) -> list[Dataset]:
        if provider_id:
            rows = self.conn.execute(
                "SELECT * FROM datasets WHERE provider_id = ? ORDER BY title COLLATE NOCASE",
                (provider_id,),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM datasets ORDER BY provider_id, title COLLATE NOCASE").fetchall()
        return [dataset_from_row(row) for row in rows]

    def upsert_render_bridge_asset(self, asset: RenderBridgeAsset) -> None:
        now = utc_now_iso()
        existing = self.conn.execute(
            "SELECT created_at FROM render_bridge_assets WHERE asset_id = ?",
            (asset.asset_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        self.conn.execute(
            """
            INSERT INTO render_bridge_assets (
                asset_id, dataset_uid, renderer, asset_role, storage_format,
                path, spatial_index_path, temporal_index_path, checksum,
                metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                dataset_uid = excluded.dataset_uid,
                renderer = excluded.renderer,
                asset_role = excluded.asset_role,
                storage_format = excluded.storage_format,
                path = excluded.path,
                spatial_index_path = excluded.spatial_index_path,
                temporal_index_path = excluded.temporal_index_path,
                checksum = excluded.checksum,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                asset.asset_id,
                asset.dataset_uid,
                asset.renderer,
                asset.asset_role,
                asset.storage_format,
                asset.path,
                asset.spatial_index_path,
                asset.temporal_index_path,
                asset.checksum,
                json.dumps(asset.metadata, ensure_ascii=False, sort_keys=True),
                created_at,
                now,
            ),
        )
        self.conn.execute(
            """
            UPDATE dataset_sync_state
            SET bridge_asset_id = ?, curated_path = ?, updated_at = ?
            WHERE dataset_uid = ?
            """,
            (asset.asset_id, asset.path, now, asset.dataset_uid),
        )
        self.conn.commit()

    def list_render_bridge_assets(self, renderer: str | None = None) -> list[RenderBridgeAsset]:
        if renderer:
            rows = self.conn.execute(
                "SELECT * FROM render_bridge_assets WHERE renderer = ? ORDER BY asset_role, asset_id",
                (renderer,),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM render_bridge_assets ORDER BY renderer, asset_role, asset_id").fetchall()
        return [render_bridge_asset_from_row(row) for row in rows]

    def upsert_dataset_asset_manifest(
        self,
        manifest: AssetManifest,
        manifest_path: str | Path,
        status: str = "unknown",
        verify_error: str = "",
    ) -> str:
        now = utc_now_iso()
        manifest_id = dataset_manifest_id(manifest.provider_id, manifest.dataset_uid, manifest.dataset_id, manifest.version, manifest.path)
        existing = self.conn.execute(
            "SELECT created_at FROM dataset_asset_manifests WHERE manifest_id = ?",
            (manifest_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        self.conn.execute(
            """
            INSERT INTO dataset_asset_manifests (
                manifest_id, provider_id, dataset_uid, dataset_id, version,
                path, manifest_path, source_url, size_bytes, sha256,
                schema_fingerprint, status, last_verified_at, last_verify_error,
                metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(manifest_id) DO UPDATE SET
                provider_id = excluded.provider_id,
                dataset_uid = excluded.dataset_uid,
                dataset_id = excluded.dataset_id,
                version = excluded.version,
                path = excluded.path,
                manifest_path = excluded.manifest_path,
                source_url = excluded.source_url,
                size_bytes = excluded.size_bytes,
                sha256 = excluded.sha256,
                schema_fingerprint = excluded.schema_fingerprint,
                status = excluded.status,
                last_verified_at = excluded.last_verified_at,
                last_verify_error = excluded.last_verify_error,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                manifest_id,
                manifest.provider_id,
                manifest.dataset_uid,
                manifest.dataset_id,
                manifest.version,
                manifest.path,
                str(manifest_path),
                manifest.source_url,
                manifest.size_bytes,
                manifest.sha256,
                manifest.schema_fingerprint,
                status,
                now if status != "unknown" else "",
                verify_error,
                json.dumps(manifest.metadata, ensure_ascii=False, sort_keys=True),
                created_at,
                now,
            ),
        )
        self.conn.commit()
        return manifest_id

    def list_dataset_asset_manifests(self, provider_id: str | None = None) -> list[DatasetAssetManifestRecord]:
        if provider_id:
            rows = self.conn.execute(
                "SELECT * FROM dataset_asset_manifests WHERE provider_id = ? ORDER BY updated_at DESC",
                (provider_id,),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM dataset_asset_manifests ORDER BY updated_at DESC").fetchall()
        return [dataset_asset_manifest_from_row(row) for row in rows]

    def dataset_asset_manifest_health_summary(self) -> dict[str, int]:
        summary = {"ok": 0, "missing": 0, "size_mismatch": 0, "checksum_mismatch": 0, "manifest_error": 0, "unknown": 0}
        rows = self.conn.execute("SELECT status, COUNT(*) AS n FROM dataset_asset_manifests GROUP BY status").fetchall()
        for row in rows:
            summary[row["status"] or "unknown"] = int(row["n"])
        return summary

    def seed_key_reference_if_exists(self, path: str | Path) -> int:
        path = resolve_project_path(path)
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        now = utc_now_iso()
        count = 0
        for item in data.get("credentials", []):
            provider_id = (item.get("provider_id") or "").strip()
            env_var = (item.get("env_var") or "").strip()
            if not provider_id or not env_var:
                continue
            self.conn.execute(
                """
                INSERT INTO template_keys (
                    env_var, provider_id, auth_type, placeholder, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(env_var) DO UPDATE SET
                    provider_id = excluded.provider_id,
                    auth_type = excluded.auth_type,
                    placeholder = excluded.placeholder,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    env_var,
                    provider_id,
                    item.get("auth_type") or "unknown",
                    item.get("placeholder") or f"your_{env_var.lower()}",
                    item.get("notes") or "",
                    now,
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def list_provider_catalog_entries(self) -> list[ProviderCatalogEntry]:
        rows = self.conn.execute(
            """
            SELECT
                p.*,
                cr.status_code AS latest_status,
                cr.fetched_at AS latest_fetched_at,
                cr.error AS latest_error,
                COALESCE(pds.remote_status, 'unchecked') AS remote_status,
                COALESCE(pds.local_status, 'not_imported') AS local_status,
                COALESCE(pds.update_status, 'unknown') AS update_status,
                COALESCE(pds.last_downloaded_at, '') AS last_downloaded_at,
                COALESCE(pds.dataset_path, '') AS dataset_path,
                COALESCE(pi.install_id, '') AS install_id,
                COALESCE(pi.install_fingerprint, '') AS install_fingerprint,
                COALESCE(pp.is_starred, 0) AS is_starred,
                COALESCE(pp.display_order, 0) AS display_order
            FROM providers p
            LEFT JOIN provider_download_state pds ON pds.provider_id = p.provider_id
            LEFT JOIN provider_preferences pp ON pp.provider_id = p.provider_id
            LEFT JOIN provider_installations pi
                ON pi.install_id = (
                    SELECT install_id
                    FROM provider_installations
                    WHERE provider_id = p.provider_id
                    ORDER BY
                        CASE status WHEN 'managed' THEN 0 WHEN 'unmanaged' THEN 1 ELSE 2 END,
                        updated_at DESC
                    LIMIT 1
                )
            LEFT JOIN crawl_results cr
                ON cr.id = (
                    SELECT id
                    FROM crawl_results
                    WHERE provider_id = p.provider_id
                    ORDER BY fetched_at DESC, id DESC
                    LIMIT 1
                )
            ORDER BY is_starred DESC, display_order ASC, p.name COLLATE NOCASE
            """
        ).fetchall()
        return [self._catalog_entry_from_row(row) for row in rows]

    def _catalog_entry_from_row(self, row: sqlite3.Row) -> ProviderCatalogEntry:
        return ProviderCatalogEntry(
            provider_id=row["provider_id"],
            name=row["name"],
            owner=row["owner"],
            categories=tuple(json.loads(row["categories_json"])),
            geographic_scope=row["geographic_scope"],
            docs_url=row["docs_url"],
            api_base_url=row["api_base_url"] or "",
            signup_url=row["signup_url"] or "",
            auth_type=row["auth_type"],
            key_env_var=row["key_env_var"] or "",
            notes=row["notes"] or "",
            latest_status=row["latest_status"],
            latest_fetched_at=row["latest_fetched_at"] or "",
            latest_error=row["latest_error"] or "",
            remote_status=row["remote_status"],
            local_status=row["local_status"],
            update_status=row["update_status"],
            last_downloaded_at=row["last_downloaded_at"],
            dataset_path=row["dataset_path"],
            install_id=row["install_id"],
            install_fingerprint=row["install_fingerprint"],
            is_starred=bool(row["is_starred"]),
        )

    def set_provider_starred(self, provider_id: str, is_starred: bool) -> None:
        now = utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO provider_preferences (
                provider_id, is_starred, display_order, updated_at
            ) VALUES (?, ?, 0, ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                is_starred = excluded.is_starred,
                updated_at = excluded.updated_at
            """,
            (provider_id, 1 if is_starred else 0, now),
        )
        self.conn.commit()

    def toggle_provider_starred(self, provider_id: str) -> bool:
        current = self.conn.execute(
            "SELECT is_starred FROM provider_preferences WHERE provider_id = ?",
            (provider_id,),
        ).fetchone()
        next_value = not bool(current["is_starred"]) if current else True
        self.set_provider_starred(provider_id, next_value)
        return next_value

    def manage_provider_installation(
        self,
        provider_id: str,
        location: str = "",
        local_fingerprint: str = "",
        notes: str = "",
    ) -> str:
        provider = self.conn.execute("SELECT provider_id FROM providers WHERE provider_id = ?", (provider_id,)).fetchone()
        if provider is None:
            raise ValueError(f"Unknown provider_id: {provider_id}")
        now = utc_now_iso()
        location = location.strip()
        install_fingerprint = local_fingerprint.strip() or provider_install_fingerprint(provider_id, location)
        existing = self.conn.execute(
            """
            SELECT install_id
            FROM provider_installations
            WHERE provider_id = ? AND install_fingerprint = ?
            """,
            (provider_id, install_fingerprint),
        ).fetchone()
        install_id = existing["install_id"] if existing else f"inst_{uuid.uuid4().hex}"
        if existing:
            self.conn.execute(
                """
                UPDATE provider_installations
                SET location = ?, status = 'managed', notes = ?, updated_at = ?
                WHERE install_id = ?
                """,
                (location, notes, now, install_id),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO provider_installations (
                    install_id, provider_id, source_kind, install_scope,
                    install_fingerprint, location, status, notes, created_at, updated_at
                ) VALUES (?, ?, 'provider', 'provider', ?, ?, 'managed', ?, ?, ?)
                """,
                (install_id, provider_id, install_fingerprint, location, notes, now, now),
            )
        self.conn.execute(
            """
            INSERT INTO provider_download_state (
                provider_id, last_downloaded_at, local_status, update_status, dataset_path, updated_at
            ) VALUES (?, ?, 'imported', 'current', ?, ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                last_downloaded_at = excluded.last_downloaded_at,
                local_status = excluded.local_status,
                update_status = excluded.update_status,
                dataset_path = excluded.dataset_path,
                updated_at = excluded.updated_at
            """,
            (provider_id, now, location, now),
        )
        self.conn.commit()
        return install_id

    def register_installation_asset(
        self,
        install_id: str,
        asset_kind: str,
        asset_name: str,
        asset_role: str = "source",
        derived_from_asset_id: str = "",
        engine: str = "",
        source_format: str = "unknown",
        source_uri: str = "",
        schema_fingerprint: str = "",
        uninstall_command: str = "",
        notes: str = "",
    ) -> str:
        installation = self.conn.execute(
            "SELECT install_id FROM provider_installations WHERE install_id = ?",
            (install_id,),
        ).fetchone()
        if installation is None:
            raise ValueError(f"Unknown install_id: {install_id}")
        now = utc_now_iso()
        asset_kind = asset_kind.strip()
        asset_role = normalize_asset_role(asset_role)
        derived_from_asset_id = derived_from_asset_id.strip()
        engine = engine.strip()
        asset_name = asset_name.strip()
        source_format = normalize_source_format(source_format)
        source_uri = source_uri.strip()
        schema_fingerprint = schema_fingerprint.strip()
        if not asset_kind or not asset_name:
            raise ValueError("asset_kind and asset_name are required")
        asset_id = provider_asset_id(install_id, asset_kind, engine, asset_name)
        self.conn.execute(
            """
            INSERT INTO provider_installation_assets (
                asset_id, install_id, asset_kind, engine, asset_name,
                asset_role, derived_from_asset_id,
                source_format, source_uri, schema_fingerprint,
                uninstall_command, status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'managed', ?, ?, ?)
            ON CONFLICT(install_id, asset_kind, engine, asset_name) DO UPDATE SET
                asset_role = excluded.asset_role,
                derived_from_asset_id = excluded.derived_from_asset_id,
                source_format = excluded.source_format,
                source_uri = excluded.source_uri,
                schema_fingerprint = excluded.schema_fingerprint,
                uninstall_command = excluded.uninstall_command,
                status = 'managed',
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                asset_id,
                install_id,
                asset_kind,
                engine,
                asset_name,
                asset_role,
                derived_from_asset_id,
                source_format,
                source_uri,
                schema_fingerprint,
                uninstall_command,
                notes,
                now,
                now,
            ),
        )
        self.conn.commit()
        return asset_id

    def managed_asset_records(self, provider_id: str | None = None) -> list[AssetRecord]:
        params: tuple[str, ...] = ()
        provider_filter = ""
        if provider_id:
            provider_filter = "AND pi.provider_id = ?"
            params = (provider_id,)
        rows = self.conn.execute(
            f"""
            SELECT
                pia.asset_id,
                pia.install_id,
                pi.provider_id,
                pia.asset_kind,
                COALESCE(pia.asset_role, 'source') AS asset_role,
                COALESCE(pia.derived_from_asset_id, '') AS derived_from_asset_id,
                COALESCE(pia.engine, '') AS engine,
                pia.asset_name,
                COALESCE(pia.source_format, 'unknown') AS source_format,
                COALESCE(pia.source_uri, '') AS source_uri,
                COALESCE(pia.schema_fingerprint, '') AS schema_fingerprint
            FROM provider_installation_assets pia
            JOIN provider_installations pi ON pi.install_id = pia.install_id
            WHERE pia.status IN ('managed', 'present', 'missing', 'error')
              AND pi.status IN ('managed', 'missing', 'error')
              {provider_filter}
            ORDER BY pi.provider_id, pia.asset_kind, pia.asset_name
            """,
            params,
        ).fetchall()
        return [
            AssetRecord(
                asset_id=row["asset_id"],
                install_id=row["install_id"],
                provider_id=row["provider_id"],
                asset_kind=row["asset_kind"],
                asset_role=row["asset_role"],
                derived_from_asset_id=row["derived_from_asset_id"],
                engine=row["engine"],
                asset_name=row["asset_name"],
                source_format=row["source_format"],
                source_uri=row["source_uri"],
                schema_fingerprint=row["schema_fingerprint"],
            )
            for row in rows
        ]

    def verify_provider_assets(
        self,
        provider_ids: list[str] | None = None,
        verifier: AssetVerifier | None = None,
    ) -> dict[str, int]:
        verifier = verifier or RegistryOnlyVerifier()
        now = utc_now_iso()
        summary = {"present": 0, "missing": 0, "error": 0, "checked": 0}
        provider_filter = set(provider_ids or [])
        assets = [
            asset
            for asset in self.managed_asset_records()
            if not provider_filter or asset.provider_id in provider_filter
        ]
        install_status: dict[str, str] = {}
        for asset in assets:
            result = verifier.verify(asset)
            status = result.status if result.status in {"present", "missing", "error"} else "error"
            error = result.error if status == "error" else ""
            self.conn.execute(
                """
                UPDATE provider_installation_assets
                SET status = ?, last_verified_at = ?, last_verify_error = ?, updated_at = ?
                WHERE asset_id = ?
                """,
                (status, now, error, now, asset.asset_id),
            )
            summary[status] += 1
            summary["checked"] += 1
            previous = install_status.get(asset.install_id)
            if status == "error" or previous == "error":
                install_status[asset.install_id] = "error"
            elif status == "missing" or previous == "missing":
                install_status[asset.install_id] = "missing"
            else:
                install_status[asset.install_id] = "managed"
        for install_id, status in install_status.items():
            self.conn.execute(
                """
                UPDATE provider_installations
                SET status = ?, updated_at = ?
                WHERE install_id = ?
                """,
                (status, now, install_id),
            )
            provider = self.conn.execute(
                "SELECT provider_id FROM provider_installations WHERE install_id = ?",
                (install_id,),
            ).fetchone()
            if provider:
                local_status = {
                    "managed": "imported",
                    "missing": "missing",
                    "error": "error",
                }[status]
                self.conn.execute(
                    """
                    INSERT INTO provider_download_state (
                        provider_id, local_status, update_status, updated_at
                    ) VALUES (?, ?, 'unknown', ?)
                    ON CONFLICT(provider_id) DO UPDATE SET
                        local_status = excluded.local_status,
                        update_status = excluded.update_status,
                        updated_at = excluded.updated_at
                    """,
                    (provider["provider_id"], local_status, now),
                )
        self.conn.commit()
        return summary

    def register_provider_database_asset(
        self,
        provider_id: str,
        engine: str,
        database_name: str,
        location: str = "",
        asset_role: str = "source",
        derived_from_asset_id: str = "",
        source_format: str = "unknown",
        source_uri: str = "",
        schema_fingerprint: str = "",
        notes: str = "",
    ) -> str:
        install_id = self.manage_provider_installation(provider_id, location=location or f"{engine}://{database_name}")
        return self.register_installation_asset(
            install_id,
            asset_kind="database",
            asset_role=asset_role,
            derived_from_asset_id=derived_from_asset_id,
            engine=engine,
            asset_name=database_name,
            source_format=source_format,
            source_uri=source_uri,
            schema_fingerprint=schema_fingerprint,
            uninstall_command=database_uninstall_command(engine, database_name),
            notes=notes,
        )

    def uninstall_provider_installation(self, provider_id: str, execute: bool = False) -> dict[str, object]:
        if execute:
            raise RuntimeError("Destructive uninstall execution is not implemented until database adapters are available.")
        now = utc_now_iso()
        row = self.conn.execute(
            """
            SELECT install_id
            FROM provider_installations
            WHERE provider_id = ? AND status = 'managed'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (provider_id,),
        ).fetchone()
        if row is None:
            return {"install_id": None, "assets": [], "executed": False}
        install_id = row["install_id"]
        assets = [
            dict(asset)
            for asset in self.conn.execute(
                """
                SELECT asset_id, asset_kind, asset_role, derived_from_asset_id, engine, asset_name, uninstall_command
                FROM provider_installation_assets
                WHERE install_id = ? AND status = 'managed'
                ORDER BY asset_kind, asset_name
                """,
                (install_id,),
            ).fetchall()
        ]
        self.conn.execute(
            """
            UPDATE provider_installation_assets
            SET status = 'removed', updated_at = ?
            WHERE install_id = ? AND status = 'managed'
            """,
            (now, install_id),
        )
        self.conn.execute(
            """
            UPDATE provider_installations
            SET status = 'removed', updated_at = ?
            WHERE install_id = ?
            """,
            (now, install_id),
        )
        self.conn.execute(
            """
            INSERT INTO provider_download_state (
                provider_id, local_status, update_status, dataset_path, updated_at
            ) VALUES (?, 'not_imported', 'unknown', '', ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                local_status = excluded.local_status,
                update_status = excluded.update_status,
                dataset_path = excluded.dataset_path,
                updated_at = excluded.updated_at
            """,
            (provider_id, now),
        )
        self.conn.commit()
        return {"install_id": install_id, "assets": assets, "executed": False}

    def unmanage_provider_installation(self, provider_id: str) -> str | None:
        now = utc_now_iso()
        row = self.conn.execute(
            """
            SELECT install_id
            FROM provider_installations
            WHERE provider_id = ? AND status = 'managed'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (provider_id,),
        ).fetchone()
        if row is None:
            return None
        install_id = row["install_id"]
        self.conn.execute(
            """
            UPDATE provider_installations
            SET status = 'unmanaged', updated_at = ?
            WHERE install_id = ?
            """,
            (now, install_id),
        )
        self.conn.execute(
            """
            INSERT INTO provider_download_state (
                provider_id, local_status, update_status, updated_at
            ) VALUES (?, 'not_imported', 'unknown', ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                local_status = excluded.local_status,
                update_status = excluded.update_status,
                updated_at = excluded.updated_at
            """,
            (provider_id, now),
        )
        self.conn.commit()
        return install_id

    def refresh_provider_download_state(self, provider_ids: list[str] | None = None) -> int:
        providers = load_providers(self.conn, provider_ids)
        now = utc_now_iso()
        changed = 0
        for provider in providers:
            latest = self.conn.execute(
                """
                SELECT fetched_at, status_code, sha256, error
                FROM crawl_results
                WHERE provider_id = ?
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (provider.provider_id,),
            ).fetchone()
            existing = self.conn.execute(
                "SELECT last_remote_hash FROM provider_download_state WHERE provider_id = ?",
                (provider.provider_id,),
            ).fetchone()
            if latest is None:
                remote_status = "unchecked"
                update_status = "unknown"
                last_checked_at = None
                remote_hash = ""
            else:
                remote_hash = latest["sha256"] or ""
                last_checked_at = latest["fetched_at"]
                remote_status = "error" if latest["error"] else "checked"
                if remote_status == "error":
                    update_status = "unknown"
                elif existing and existing["last_remote_hash"] and existing["last_remote_hash"] != remote_hash:
                    update_status = "remote_updated"
                elif remote_hash:
                    update_status = "current"
                else:
                    update_status = "checked_no_hash"
            self.conn.execute(
                """
                INSERT INTO provider_download_state (
                    provider_id, last_checked_at, last_remote_hash, remote_status,
                    local_status, update_status, updated_at
                ) VALUES (?, ?, ?, ?, 'not_imported', ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    last_checked_at = excluded.last_checked_at,
                    last_remote_hash = excluded.last_remote_hash,
                    remote_status = excluded.remote_status,
                    update_status = excluded.update_status,
                    updated_at = excluded.updated_at
                """,
                (provider.provider_id, last_checked_at, remote_hash, remote_status, update_status, now),
            )
            changed += 1
        self.conn.commit()
        return changed


def provider_install_fingerprint(provider_id: str, location: str = "") -> str:
    normalized = f"{provider_id.strip().lower()}|{location.strip().replace('\\', '/').lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def provider_asset_id(install_id: str, asset_kind: str, engine: str, asset_name: str) -> str:
    normalized = "|".join(
        [
            install_id.strip().lower(),
            asset_kind.strip().lower(),
            engine.strip().lower(),
            asset_name.strip().lower(),
        ]
    )
    return "asset_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
