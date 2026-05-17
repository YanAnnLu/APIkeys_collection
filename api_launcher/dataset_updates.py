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
]
VersionDirection = Literal["install", "same", "upgrade", "downgrade", "partial_forward", "partial_backward", "unknown"]


@dataclass(frozen=True)
class DatasetUpdatePlan:
    dataset_uid: str
    current_version: str
    target_version: str
    direction: VersionDirection
    decision: UpdateDecision
    update_strategy: str
    reason: str

    @property
    def needs_download(self) -> bool:
        return self.decision in {"install_new", "compare_then_update", "keep_legacy_and_install_new"}


def plan_dataset_update(current: Dataset | None, target: DatasetVersionOption) -> DatasetUpdatePlan:
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
