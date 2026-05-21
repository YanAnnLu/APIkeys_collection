from __future__ import annotations

from api_launcher.adapters import DatasetAdapter, GEBCOTopographyAdapter, HYGStarCatalogAdapter
from api_launcher.models import Provider


DATASET_ADAPTERS: tuple[DatasetAdapter, ...] = (
    GEBCOTopographyAdapter(),
    HYGStarCatalogAdapter(),
)


def adapters_for_provider(provider: Provider) -> list[DatasetAdapter]:
    # 目前用明確 registry；新增 adapter 時先確認它服務 MVP 的 discovery/plan 路徑。
    return [adapter for adapter in DATASET_ADAPTERS if adapter.provider_id == provider.provider_id]
