from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataStoreConnectionProfile:
    profile_id: str
    label: str
    store_kind: str
    engine: str
    required_env_vars: tuple[str, ...]
    optional_env_vars: tuple[str, ...] = ()
    status: str = "skeleton"
    notes: str = ""


DEFAULT_DATA_STORE_PROFILES = (
    DataStoreConnectionProfile(
        profile_id="mysql_default",
        label="MySQL default",
        store_kind="relational_sql",
        engine="mysql",
        required_env_vars=("APIKEYS_MYSQL_HOST", "APIKEYS_MYSQL_DATABASE", "APIKEYS_MYSQL_USER", "APIKEYS_MYSQL_PASSWORD"),
        optional_env_vars=("APIKEYS_MYSQL_PORT",),
        notes="Relational SQL profile for MySQL self-check and future install/uninstall adapters.",
    ),
    DataStoreConnectionProfile(
        profile_id="postgres_default",
        label="PostgreSQL default",
        store_kind="relational_sql",
        engine="postgresql",
        required_env_vars=("APIKEYS_POSTGRES_HOST", "APIKEYS_POSTGRES_DATABASE", "APIKEYS_POSTGRES_USER", "APIKEYS_POSTGRES_PASSWORD"),
        optional_env_vars=("APIKEYS_POSTGRES_PORT",),
        notes="Reserved for PostgreSQL introspection.",
    ),
    DataStoreConnectionProfile(
        profile_id="sqlite_local",
        label="SQLite local",
        store_kind="embedded_sql",
        engine="sqlite",
        required_env_vars=("APIKEYS_SQLITE_PATH",),
        notes="Local file-backed SQLite path for lightweight testing.",
    ),
    DataStoreConnectionProfile(
        profile_id="mongodb_default",
        label="MongoDB default",
        store_kind="document_nosql",
        engine="mongodb",
        required_env_vars=("APIKEYS_MONGODB_URI",),
        notes="Reserved for document database datasets and imported JSON collections.",
    ),
    DataStoreConnectionProfile(
        profile_id="s3_compatible_default",
        label="S3-compatible object store",
        store_kind="object_storage",
        engine="s3_compatible",
        required_env_vars=("APIKEYS_S3_ENDPOINT", "APIKEYS_S3_BUCKET", "APIKEYS_S3_ACCESS_KEY", "APIKEYS_S3_SECRET_KEY"),
        optional_env_vars=("APIKEYS_S3_REGION",),
        notes="Reserved for object storage, data lakes, and large raw/curated asset buckets.",
    ),
    DataStoreConnectionProfile(
        profile_id="vector_db_default",
        label="Vector DB default",
        store_kind="vector_database",
        engine="generic_vector_db",
        required_env_vars=("APIKEYS_VECTOR_DB_ENDPOINT", "APIKEYS_VECTOR_DB_API_KEY"),
        notes="Reserved for embeddings, semantic dataset search, and future local LLM workflows.",
    ),
)


def data_store_profile(profile_id: str) -> DataStoreConnectionProfile | None:
    wanted = profile_id.strip().lower()
    return next((profile for profile in DEFAULT_DATA_STORE_PROFILES if profile.profile_id == wanted), None)


def data_store_profiles_by_kind(kind: str) -> tuple[DataStoreConnectionProfile, ...]:
    wanted = kind.strip().lower()
    return tuple(profile for profile in DEFAULT_DATA_STORE_PROFILES if profile.store_kind == wanted)
