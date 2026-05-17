from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.asset_verifier import AssetRecord, AssetVerificationResult
from api_launcher.data_store_connections import DataStoreConnectionProfile, test_data_store_connection


@dataclass(frozen=True)
class DatabaseSelfCheckTarget:
    engine: str
    asset_name: str
    path: str = ""


def database_self_check_target(asset: AssetRecord) -> DatabaseSelfCheckTarget:
    engine = asset.engine.strip().lower()
    if engine == "sqlite":
        return DatabaseSelfCheckTarget(engine=engine, asset_name=asset.asset_name, path=asset.source_uri or asset.asset_name)
    return DatabaseSelfCheckTarget(engine=engine, asset_name=asset.asset_name)


class DatabaseAssetVerifier:
    def verify(self, asset: AssetRecord) -> AssetVerificationResult:
        if asset.asset_kind != "database":
            return AssetVerificationResult(asset.asset_id, "error", f"Unsupported asset kind: {asset.asset_kind}")
        target = database_self_check_target(asset)
        if target.engine == "sqlite":
            return self._verify_sqlite(asset, target)
        if target.engine in {"mysql", "mariadb"}:
            return self._verify_mysql(asset, target)
        if target.engine in {"postgres", "postgresql"}:
            return self._verify_postgresql(asset, target)
        return AssetVerificationResult(asset.asset_id, "error", f"No database self-check adapter for engine: {target.engine or 'unknown'}")

    def _verify_sqlite(self, asset: AssetRecord, target: DatabaseSelfCheckTarget) -> AssetVerificationResult:
        if not target.path:
            return AssetVerificationResult(asset.asset_id, "error", "SQLite asset has no source_uri or path-like asset_name.")
        result = test_data_store_connection(
            DataStoreConnectionProfile(
                profile_id=f"asset_{asset.asset_id}",
                label=f"SQLite asset {asset.asset_name}",
                store_kind="embedded_sql",
                engine="sqlite",
                required_env_vars=("APIKEYS_SQLITE_PATH",),
            ),
            {"APIKEYS_SQLITE_PATH": str(Path(target.path))},
        )
        if result.status == "ok":
            return AssetVerificationResult(asset.asset_id, "present")
        if result.status == "missing_target":
            return AssetVerificationResult(asset.asset_id, "missing", result.message)
        return AssetVerificationResult(asset.asset_id, "error", result.message)

    def _verify_mysql(self, asset: AssetRecord, target: DatabaseSelfCheckTarget) -> AssetVerificationResult:
        result = test_data_store_connection(
            DataStoreConnectionProfile(
                profile_id="mysql_default",
                label="MySQL default",
                store_kind="relational_sql",
                engine="mysql",
                required_env_vars=("APIKEYS_MYSQL_HOST", "APIKEYS_MYSQL_DATABASE", "APIKEYS_MYSQL_USER", "APIKEYS_MYSQL_PASSWORD"),
                optional_env_vars=("APIKEYS_MYSQL_PORT",),
            )
        )
        if result.status == "ok":
            connected_database = str(result.details.get("database") or "")
            if connected_database and connected_database != target.asset_name:
                return AssetVerificationResult(
                    asset.asset_id,
                    "error",
                    f"MySQL profile connected to {connected_database}, but registry asset expects {target.asset_name}.",
                )
            return AssetVerificationResult(asset.asset_id, "present")
        return AssetVerificationResult(asset.asset_id, "error", result.message)

    def _verify_postgresql(self, asset: AssetRecord, target: DatabaseSelfCheckTarget) -> AssetVerificationResult:
        result = test_data_store_connection(
            DataStoreConnectionProfile(
                profile_id="postgres_default",
                label="PostgreSQL default",
                store_kind="relational_sql",
                engine="postgresql",
                required_env_vars=("APIKEYS_POSTGRES_HOST", "APIKEYS_POSTGRES_DATABASE", "APIKEYS_POSTGRES_USER", "APIKEYS_POSTGRES_PASSWORD"),
                optional_env_vars=("APIKEYS_POSTGRES_PORT",),
            )
        )
        if result.status == "ok":
            connected_database = str(result.details.get("database") or "")
            if connected_database and connected_database != target.asset_name:
                return AssetVerificationResult(
                    asset.asset_id,
                    "error",
                    f"PostgreSQL profile connected to {connected_database}, but registry asset expects {target.asset_name}.",
                )
            return AssetVerificationResult(asset.asset_id, "present")
        return AssetVerificationResult(asset.asset_id, "error", result.message)
