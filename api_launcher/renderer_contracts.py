from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.adapters.base import dataset_uid
from api_launcher.models import Dataset, RenderBridgeAsset


TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID = "taichi_global_bathymetry"
TAICHI_EARTH_CACHE_DIR = Path.home() / ".cache" / "taichi_earth"

GEBCO_PROVIDER_ID = "gebco"
GEBCO_2025_DATASET_ID = "gebco_2025_elevation"
GEBCO_2025_TOPO_SOURCE = "gebco_2025"
GEBCO_2025_OPENDAP_URL = (
    "https://dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/"
    "gebco_2025/ice_surface_elevation/netcdf/GEBCO_2025.nc"
)

HYG_PROVIDER_ID = "hyg_database"
HYG_V38_DATASET_ID = "hyg_v38_bright_star_catalog"
HYG_V38_URL = "https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/v3/hyg_v38.csv.gz"


@dataclass(frozen=True)
class RendererDatasetContract:
    # contract 描述資料集如何交給 renderer，不直接載入或轉換大型 payload。
    renderer: str
    provider_id: str
    dataset_id: str
    title: str
    categories: tuple[str, ...]
    bridge_asset_role: str
    bridge_storage_format: str
    cache_path_template: str
    source_url: str
    metadata: dict[str, object]

    @property
    def dataset_uid(self) -> str:
        return dataset_uid(self.provider_id, self.dataset_id)

    def cache_path(self, **values: object) -> str:
        # cache path 只描述 renderer cache 位置；不代表檔案已存在或已納管。
        return str(TAICHI_EARTH_CACHE_DIR / self.cache_path_template.format(**values))

    def dataset(self) -> Dataset:
        # contract 可轉成一般 Dataset，讓 renderer 需求也能進入 catalog/version/download 流程。
        return Dataset(
            dataset_uid=self.dataset_uid,
            provider_id=self.provider_id,
            dataset_id=self.dataset_id,
            title=self.title,
            categories=self.categories,
            data_type=str(self.metadata.get("data_type") or ""),
            native_format=str(self.metadata.get("native_format") or ""),
            geographic_scope=str(self.metadata.get("geographic_scope") or ""),
            landing_url=self.source_url,
            api_url=self.source_url,
            metadata=dict(self.metadata),
        )

    def bridge_asset(self, path: str, checksum: str = "") -> RenderBridgeAsset:
        # bridge asset 是 derived/cache 類資產，必須保留 source_url 與 dataset_id 方便重建。
        return RenderBridgeAsset(
            asset_id=f"{self.renderer}:{self.dataset_id}:{self.bridge_asset_role}",
            dataset_uid=self.dataset_uid,
            renderer=self.renderer,
            asset_role=self.bridge_asset_role,
            storage_format=self.bridge_storage_format,
            path=path,
            checksum=checksum,
            metadata={
                "provider_id": self.provider_id,
                "dataset_id": self.dataset_id,
                "source_url": self.source_url,
                **self.metadata,
            },
        )


GEBCO_2025_TOPOGRAPHY_CONTRACT = RendererDatasetContract(
    renderer=TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID,
    provider_id=GEBCO_PROVIDER_ID,
    dataset_id=GEBCO_2025_DATASET_ID,
    title="GEBCO 2025 Global Elevation Grid",
    categories=("bathymetry", "terrain", "renderer_bridge"),
    bridge_asset_role="topography_grid",
    bridge_storage_format="npy:int16:lat_lon_grid",
    cache_path_template="gebco_2025_topo_cache_step{step}.npy",
    source_url=GEBCO_2025_OPENDAP_URL,
    metadata={
        "data_type": "raster_grid",
        "native_format": "netcdf",
        "geographic_scope": "global",
        "renderer_variable": "elevation",
        "topo_source": GEBCO_2025_TOPO_SOURCE,
    },
)

HYG_V38_STAR_CONTRACT = RendererDatasetContract(
    renderer=TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID,
    provider_id=HYG_PROVIDER_ID,
    dataset_id=HYG_V38_DATASET_ID,
    title="HYG v3.8 Bright Star Catalog",
    categories=("astronomy", "stars", "renderer_bridge"),
    bridge_asset_role="star_catalog",
    bridge_storage_format="npy:float32:xyz_mag",
    cache_path_template="stars_cache.npy",
    source_url=HYG_V38_URL,
    metadata={
        "data_type": "point_catalog",
        "native_format": "csv.gz",
        "geographic_scope": "celestial",
        "renderer_columns": ("x", "y", "z", "mag"),
    },
)

TAICHI_GLOBAL_BATHYMETRY_CONTRACTS = (
    GEBCO_2025_TOPOGRAPHY_CONTRACT,
    HYG_V38_STAR_CONTRACT,
)


def canonical_dataset_key(name: str, version: str = "", scope: str = "") -> str:
    # canonical key 給 renderer/adapter 做穩定比對；空欄位不放入 key，降低無意義差異。
    parts = [name.strip().lower(), version.strip().lower(), scope.strip().lower()]
    return "::".join(part for part in parts if part)
