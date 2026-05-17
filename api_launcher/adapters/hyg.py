from __future__ import annotations

from api_launcher.adapters.base import DatasetAdapter
from api_launcher.models import Dataset, Provider
from api_launcher.renderer_contracts import HYG_PROVIDER_ID, HYG_V38_STAR_CONTRACT, HYG_V38_URL


HYG_CODEBERG_HOME = "https://codeberg.org/astronexus/hyg"
HYG_GITHUB_ARCHIVE_HOME = "https://github.com/astronexus/HYG-Database"


class HYGStarCatalogAdapter(DatasetAdapter):
    provider_id = HYG_PROVIDER_ID

    def discover(self, provider: Provider, max_items: int | None = None) -> list[Dataset]:
        if provider.provider_id != self.provider_id:
            return []
        dataset = HYG_V38_STAR_CONTRACT.dataset()
        return [
            Dataset(
                dataset_uid=dataset.dataset_uid,
                provider_id=dataset.provider_id,
                dataset_id=dataset.dataset_id,
                title=dataset.title,
                categories=dataset.categories,
                data_type=dataset.data_type,
                native_format=dataset.native_format,
                geographic_scope=dataset.geographic_scope,
                landing_url=HYG_CODEBERG_HOME,
                api_url=HYG_V38_URL,
                license_url=provider.license_url,
                version="3.8",
                metadata={
                    **dataset.metadata,
                    "download_url": HYG_V38_URL,
                    "mirrors": (HYG_GITHUB_ARCHIVE_HOME, HYG_CODEBERG_HOME),
                    "adapter": "HYGStarCatalogAdapter",
                    "notes": "GitHub repository is archived; Codeberg is listed upstream as the future home. The v3.8 raw CSV.GZ URL remains available through the GitHub archive.",
                },
            )
        ][:max_items]
