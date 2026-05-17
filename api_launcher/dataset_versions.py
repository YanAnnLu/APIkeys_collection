from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api_launcher.models import Dataset


VERSION_STATUS_ORDER = {
    "latest": 0,
    "latest_known": 0,
    "current": 1,
    "pinned_current_adapter": 2,
    "compatibility_pinned": 3,
    "stable": 4,
    "legacy": 5,
    "deprecated": 6,
    "unknown": 7,
}


@dataclass(frozen=True)
class DatasetVersionOption:
    dataset_uid: str
    dataset_id: str
    label: str
    version: str
    status: str
    download_url: str
    landing_url: str
    update_strategy: str = "full_replace_if_needed"
    notes: str = ""
    metadata: dict[str, Any] | None = None

    @property
    def is_latest(self) -> bool:
        return self.status in {"latest", "latest_known", "current"}

    @property
    def is_legacy(self) -> bool:
        return self.status in {"compatibility_pinned", "legacy", "deprecated"}

    @property
    def menu_label(self) -> str:
        status = human_version_status(self.status)
        version = f"v{self.version}" if self.version else "unknown version"
        return f"{self.label} ({version}, {status})"

    def to_plan_metadata(self) -> dict[str, Any]:
        return {
            "dataset_uid": self.dataset_uid,
            "dataset_id": self.dataset_id,
            "label": self.label,
            "version": self.version,
            "version_status": self.status,
            "download_url": self.download_url,
            "landing_url": self.landing_url,
            "update_strategy": self.update_strategy,
            "notes": self.notes,
            "metadata": self.metadata or {},
        }


def human_version_status(status: str) -> str:
    labels = {
        "latest": "latest",
        "latest_known": "latest known",
        "current": "current",
        "pinned_current_adapter": "adapter pinned",
        "compatibility_pinned": "compatibility pinned",
        "stable": "stable",
        "legacy": "legacy",
        "deprecated": "deprecated",
        "unknown": "unknown",
    }
    return labels.get(status or "unknown", status or "unknown")


def sort_version_options(options: list[DatasetVersionOption]) -> list[DatasetVersionOption]:
    return sorted(
        options,
        key=lambda option: (
            VERSION_STATUS_ORDER.get(option.status, VERSION_STATUS_ORDER["unknown"]),
            _version_sort_key(option.version),
            option.label.lower(),
        ),
    )


def version_options_for_dataset(dataset: Dataset) -> list[DatasetVersionOption]:
    raw_versions = dataset.metadata.get("available_versions")
    if isinstance(raw_versions, list):
        options = [_version_option_from_mapping(dataset, item) for item in raw_versions if isinstance(item, dict)]
        if options:
            return sort_version_options(options)

    return sort_version_options(
        [
            DatasetVersionOption(
                dataset_uid=dataset.dataset_uid,
                dataset_id=dataset.dataset_id,
                label=dataset.version or dataset.title,
                version=dataset.version,
                status=str(dataset.metadata.get("version_status") or "unknown"),
                download_url=str(dataset.metadata.get("download_url") or dataset.api_url),
                landing_url=dataset.landing_url,
                update_strategy=str(dataset.metadata.get("update_strategy") or "full_replace_if_needed"),
                notes=str(dataset.metadata.get("notes") or ""),
                metadata=dict(dataset.metadata),
            )
        ]
    )


def version_options_for_datasets(datasets: list[Dataset]) -> list[DatasetVersionOption]:
    options: list[DatasetVersionOption] = []
    for dataset in datasets:
        options.extend(version_options_for_dataset(dataset))
    return sort_version_options(options)


def _version_option_from_mapping(dataset: Dataset, item: dict[str, Any]) -> DatasetVersionOption:
    version = str(item.get("version") or "")
    status = str(item.get("version_status") or item.get("status") or "unknown")
    label = str(item.get("label") or version or dataset.title)
    return DatasetVersionOption(
        dataset_uid=dataset.dataset_uid,
        dataset_id=dataset.dataset_id,
        label=label,
        version=version,
        status=status,
        download_url=str(item.get("download_url") or item.get("api_url") or dataset.api_url),
        landing_url=str(item.get("landing_url") or dataset.landing_url),
        update_strategy=str(item.get("update_strategy") or dataset.metadata.get("update_strategy") or "full_replace_if_needed"),
        notes=str(item.get("notes") or ""),
        metadata={key: value for key, value in item.items() if key not in {"download_url", "landing_url", "notes"}},
    )


def _version_sort_key(version: str) -> tuple[int, tuple[int, ...], str]:
    parts = []
    for chunk in version.replace("_", ".").replace("-", ".").split("."):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            return (1, tuple(parts), version)
    return (0, tuple(-part for part in parts), version)
