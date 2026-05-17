from __future__ import annotations

from api_launcher.adapters.base import DatasetAdapter
from api_launcher.models import Dataset, Provider
from api_launcher.renderer_contracts import (
    GEBCO_2025_OPENDAP_URL,
    GEBCO_2025_TOPOGRAPHY_CONTRACT,
    GEBCO_PROVIDER_ID,
)


GEBCO_2025_GRID_HOME = "https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2025-grid"
GEBCO_CURRENT_GRID_HOME = "https://www.gebco.net/data-products/gridded-bathymetry-data"
GEBCO_CEDA_CATALOG_2025 = "https://catalogue.ceda.ac.uk/uuid/05fba4c5b8fe4daea8ff751026daf438/"


class GEBCOTopographyAdapter(DatasetAdapter):
    provider_id = GEBCO_PROVIDER_ID

    def discover(self, provider: Provider, max_items: int | None = None) -> list[Dataset]:
        if provider.provider_id != self.provider_id:
            return []
        dataset = GEBCO_2025_TOPOGRAPHY_CONTRACT.dataset()
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
                landing_url=GEBCO_2025_GRID_HOME,
                api_url=GEBCO_2025_OPENDAP_URL,
                license_url=provider.license_url,
                version="2025",
                metadata={
                    **dataset.metadata,
                    "adapter": "GEBCOTopographyAdapter",
                    "download_url": GEBCO_2025_OPENDAP_URL,
                    "opendap_url": GEBCO_2025_OPENDAP_URL,
                    "ceda_catalog_url": GEBCO_CEDA_CATALOG_2025,
                    "current_grid_home": GEBCO_CURRENT_GRID_HOME,
                    "estimated_global_netcdf_size": "7.5 GB",
                    "grid_interval": "15 arc-second",
                    "grid_shape": "43200x86400",
                    "citation_required": True,
                    "training_allowed": "unknown",
                    "rag_suitability": "low",
                    "version_status": "compatibility_pinned",
                    "latest_known_version": "2026",
                    "latest_known_release_date": "2026-04-23",
                    "freshness_review_required": True,
                    "notes": (
                        "Renderer bridge is currently pinned to GEBCO 2025 for cache compatibility. "
                        "GEBCO 2026 exists and should be evaluated before migrating cache IDs. "
                        "Do not assume a seed or adapter target is the latest available version."
                    ),
                },
            )
        ][:max_items]
