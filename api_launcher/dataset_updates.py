from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.models import Dataset


UpdateDecision = Literal[
    "install_new",
    "skip_same_version",
    "compare_then_update",
    "keep_legacy_and_install_new",
    "append_incremental",
    "maintain_realtime_stream",
]
VersionDirection = Literal["install", "same", "upgrade", "downgrade", "partial_forward", "partial_backward", "unknown"]
UpdateMode = Literal[
    "static_versioned",
    "incremental_append",
    "append_only_timeseries",
    "revisable_timeseries",
    "realtime_stream",
]

TIMESERIES_UPDATE_STRATEGIES = {
    "incremental_append": "incremental_append",
    "append_only_timeseries": "append_only_timeseries",
    "append_only_time_series": "append_only_timeseries",
    "append_only_with_revisions": "revisable_timeseries",
    "revisable_timeseries": "revisable_timeseries",
    "revisable_time_series": "revisable_timeseries",
    "realtime_stream": "realtime_stream",
    "real_time_stream": "realtime_stream",
    "live_timeseries": "realtime_stream",
    "live_market_data": "realtime_stream",
}


@dataclass(frozen=True)
class DatasetUpdatePlan:
    # update plan 是版本決策摘要，不直接執行下載或替換本機資料。
    dataset_uid: str
    current_version: str
    target_version: str
    direction: VersionDirection
    decision: UpdateDecision
    update_strategy: str
    reason: str

    @property
    def needs_download(self) -> bool:
        return self.needs_ingest

    @property
    def needs_ingest(self) -> bool:
        return self.decision in {
            "install_new",
            "compare_then_update",
            "keep_legacy_and_install_new",
            "append_incremental",
            "maintain_realtime_stream",
        }


@dataclass(frozen=True)
class DatasetUpdateContract:
    mode: UpdateMode
    write_pattern: str
    version_strategy: str
    required_fields: tuple[str, ...]
    recommended_backends: tuple[str, ...]
    reason: str

    @property
    def is_time_series(self) -> bool:
        return self.mode in {"append_only_timeseries", "revisable_timeseries", "realtime_stream"}


def plan_dataset_update(current: Dataset | None, target: DatasetVersionOption) -> DatasetUpdatePlan:
    # 版本比較只產生保守建議；真正 install/update 還要經過 manifest 與 adapter policy。
    target_mode = update_mode_for_strategy(target.update_strategy)
    if current is None or not current.version:
        return DatasetUpdatePlan(
            dataset_uid=target.dataset_uid,
            current_version="",
            target_version=target.version,
            direction="install",
            decision="install_new",
            update_strategy=target.update_strategy,
            reason="No installed/current dataset version is known.",
        )

    direction = compare_versions(current.version, target.version)
    if current.version == target.version:
        if target_mode == "realtime_stream":
            return DatasetUpdatePlan(
                dataset_uid=target.dataset_uid,
                current_version=current.version,
                target_version=target.version,
                direction="same",
                decision="maintain_realtime_stream",
                update_strategy=target.update_strategy,
                reason="Realtime/time-series sources continue ingesting even when the dataset version label is unchanged.",
            )
        if target_mode in {"incremental_append", "append_only_timeseries", "revisable_timeseries"}:
            return DatasetUpdatePlan(
                dataset_uid=target.dataset_uid,
                current_version=current.version,
                target_version=target.version,
                direction="same",
                decision="append_incremental",
                update_strategy=target.update_strategy,
                reason="Append-oriented sources may add new records or revisions without changing the dataset version label.",
            )
        return DatasetUpdatePlan(
            dataset_uid=target.dataset_uid,
            current_version=current.version,
            target_version=target.version,
            direction="same",
            decision="skip_same_version",
            update_strategy=target.update_strategy,
            reason="Target version matches the known current version.",
        )

    if target.update_strategy == "keep_legacy_for_renderer_compatibility":
        return DatasetUpdatePlan(
            dataset_uid=target.dataset_uid,
            current_version=current.version,
            target_version=target.version,
            direction=direction,
            decision="keep_legacy_and_install_new",
            update_strategy=target.update_strategy,
            reason="Legacy or compatibility-pinned versions should remain available.",
        )

    return DatasetUpdatePlan(
        dataset_uid=target.dataset_uid,
        current_version=current.version,
        target_version=target.version,
        direction=direction,
        decision="compare_then_update",
        update_strategy=target.update_strategy,
        reason=f"Compare manifest/checksum/schema before applying a {direction} transition.",
    )


def dataset_update_contract(dataset: Dataset) -> DatasetUpdateContract:
    mode = _dataset_update_mode(dataset)
    if mode == "realtime_stream":
        return DatasetUpdateContract(
            mode=mode,
            write_pattern="append_only_hot_stream",
            version_strategy="Use event_time and received_at windows instead of treating a stable version label as complete.",
            required_fields=("symbol", "event_time", "received_at", "ingest_run_id"),
            recommended_backends=("PostgreSQL/TimescaleDB", "ClickHouse", "Parquet/DuckDB", "Redis/Kafka for hot stream"),
            reason="Realtime market data changes continuously and must not be skipped just because the version label is unchanged.",
        )
    if mode == "revisable_timeseries":
        return DatasetUpdateContract(
            mode=mode,
            write_pattern="append_only_with_revisions",
            version_strategy="Preserve original observations and later corrections as separate revisions.",
            required_fields=("symbol", "event_time", "received_at", "revision", "ingest_run_id"),
            recommended_backends=("PostgreSQL/TimescaleDB", "ClickHouse", "Parquet/DuckDB"),
            reason="Some time-series vendors backfill or correct historical bars, so overwrite-in-place would hide what changed.",
        )
    if mode == "append_only_timeseries":
        return DatasetUpdateContract(
            mode=mode,
            write_pattern="append_only_batches",
            version_strategy="Track completed event_time windows and append new windows instead of replacing the whole dataset.",
            required_fields=("event_time", "received_at", "ingest_run_id"),
            recommended_backends=("PostgreSQL/TimescaleDB", "ClickHouse", "Parquet/DuckDB"),
            reason="Time-series datasets grow by time window and should keep historical observations stable.",
        )
    if mode == "incremental_append":
        return DatasetUpdateContract(
            mode=mode,
            write_pattern="append_incremental_batches",
            version_strategy="Track source cursors, manifests, or checkpoints for each incremental batch.",
            required_fields=("source_cursor", "received_at", "ingest_run_id"),
            recommended_backends=("SQLite for MVP", "PostgreSQL", "Parquet/DuckDB"),
            reason="Incremental sources publish new batches under the same logical dataset.",
        )
    return DatasetUpdateContract(
        mode="static_versioned",
        write_pattern="replace_or_keep_side_by_side",
        version_strategy="Use dataset version, manifest checksum, and schema fingerprint before replacing or keeping legacy copies.",
        required_fields=("version", "manifest_sha256"),
        recommended_backends=("SQLite manifest registry", "GeoPackage/Shapefile/GeoJSON for GIS files", "Parquet/DuckDB"),
        reason="Static datasets are usually complete snapshots where a stable version can safely mean no new ingest is needed.",
    )


def update_mode_for_strategy(strategy: str) -> UpdateMode:
    normalized = strategy.strip().lower()
    return TIMESERIES_UPDATE_STRATEGIES.get(normalized, "static_versioned")  # type: ignore[return-value]


def _dataset_update_mode(dataset: Dataset) -> UpdateMode:
    metadata = dataset.metadata
    explicit = str(metadata.get("update_mode") or metadata.get("update_class") or "").strip().lower()
    if explicit in {
        "static_versioned",
        "incremental_append",
        "append_only_timeseries",
        "revisable_timeseries",
        "realtime_stream",
    }:
        return explicit  # type: ignore[return-value]
    strategy_mode = update_mode_for_strategy(str(metadata.get("update_strategy") or ""))
    if strategy_mode != "static_versioned":
        return strategy_mode
    if _looks_like_realtime_market_data(dataset):
        return "realtime_stream"
    if _truthy(metadata.get("revision_prone")) or _truthy(metadata.get("backfill_corrections")):
        return "revisable_timeseries"
    if _truthy(metadata.get("append_only")) or "time_series" in _metadata_words(dataset):
        return "append_only_timeseries"
    return "static_versioned"


def _looks_like_realtime_market_data(dataset: Dataset) -> bool:
    words = _metadata_words(dataset)
    market_words = {"finance", "financial", "market_data", "stocks", "forex", "crypto", "futures", "quote", "quotes", "tick"}
    realtime_words = {"realtime", "real_time", "live", "stream", "tick", "1s", "second", "intraday"}
    return bool(words & market_words) and bool(words & realtime_words)


def _metadata_words(dataset: Dataset) -> set[str]:
    values = [
        dataset.data_type,
        dataset.native_format,
        dataset.temporal_coverage,
        *dataset.categories,
        *(str(value) for value in dataset.metadata.values() if isinstance(value, (str, int, float, bool))),
    ]
    words: set[str] = set()
    for value in values:
        normalized = str(value).replace("-", "_").replace(" ", "_").lower()
        words.update(part for part in normalized.split("_") if part)
        if normalized:
            words.add(normalized)
    return words


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def compare_versions(current: str, target: str) -> VersionDirection:
    current_key = _version_key(current)
    target_key = _version_key(target)
    if current_key is None or target_key is None:
        return "unknown"
    if current_key == target_key:
        return "same"
    if target_key > current_key:
        return "upgrade" if _is_adjacent(current_key, target_key) else "partial_forward"
    return "downgrade" if _is_adjacent(target_key, current_key) else "partial_backward"


def _version_key(version: str) -> tuple[int, ...] | None:
    chunks: list[int] = []
    for chunk in version.replace("_", ".").replace("-", ".").split("."):
        if not chunk:
            continue
        if not chunk.isdigit():
            return None
        chunks.append(int(chunk))
    return tuple(chunks) if chunks else None


def _is_adjacent(lower: tuple[int, ...], higher: tuple[int, ...]) -> bool:
    max_len = max(len(lower), len(higher))
    padded_lower = lower + (0,) * (max_len - len(lower))
    padded_higher = higher + (0,) * (max_len - len(higher))
    diffs = [new - old for old, new in zip(padded_lower, padded_higher)]
    return sum(1 for diff in diffs if diff != 0) == 1 and any(diff == 1 for diff in diffs)
