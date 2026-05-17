from __future__ import annotations

import hashlib
from typing import Protocol

from api_launcher.models import Dataset, Provider


class DatasetAdapter(Protocol):
    provider_id: str

    def discover(self, provider: Provider, max_items: int | None = None) -> list[Dataset]:
        """Return dataset records without downloading bulk data."""


def dataset_uid(provider_id: str, dataset_id: str) -> str:
    normalized = f"{provider_id.strip().lower()}::{dataset_id.strip().lower()}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"ds_{digest}"
