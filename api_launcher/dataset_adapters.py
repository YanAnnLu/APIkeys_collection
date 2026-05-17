from __future__ import annotations

from api_launcher.adapters import DatasetAdapter, HYGStarCatalogAdapter
from api_launcher.models import Provider


DATASET_ADAPTERS: tuple[DatasetAdapter, ...] = (
    HYGStarCatalogAdapter(),
)


def adapters_for_provider(provider: Provider) -> list[DatasetAdapter]:
    return [adapter for adapter in DATASET_ADAPTERS if adapter.provider_id == provider.provider_id]
