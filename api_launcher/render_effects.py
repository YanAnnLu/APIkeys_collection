from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class RenderEffectLayer:
    # render effect 是 renderer bridge 的提示資料，不代表 Tk/CLI 已經實作特效管線。
    layer_id: str
    domain: str
    purpose: str
    driving_datasets: tuple[str, ...]
    unreal_strategy: str
    taichi_strategy: str
    data_requirements: tuple[str, ...]
    performance_notes: str
    simulation_model: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


WATER_SURFACE_LAYER = RenderEffectLayer(
    layer_id="water_surface",
    domain="hydrosphere",
    purpose="Render oceans, lakes, rivers, waves, foam, and shoreline interaction.",
    driving_datasets=(
        "bathymetry",
        "coastline",
        "tides",
        "currents",
        "wind",
    ),
    unreal_strategy=(
        "Use water materials, normal/displacement maps, particle foam, shoreline interaction, and optional Niagara effects. "
        "Scientific datasets provide bathymetry, coastline masks, tides, currents, and wind parameters; "
        "the renderer/simulation layer generates motion, waves, foam, and small-scale detail."
    ),
    taichi_strategy=(
        "Use simplified height/normal fields or particles for preview. Keep it suitable for GPU/CPU smoke tests "
        "without requiring Unreal water plugins."
    ),
    data_requirements=(
        "coastline mask",
        "bathymetry/elevation grid",
        "optional tide/current/wind time series",
    ),
    performance_notes="Use camera-distance LOD. Near field can use particles/foam; far field should use shader-only waves.",
    simulation_model=(
        "Hybrid water simulation: data-driven boundary conditions plus procedural/simplified physics. "
        "Use Gerstner/FFT-style waves for open water, shallow-water or flow-map approximations near shore/rivers, "
        "and particles for foam/spray where close to camera."
    ),
)


ATMOSPHERE_QUALITY_LAYER = RenderEffectLayer(
    layer_id="air_quality_volume",
    domain="atmosphere",
    purpose="Render air quality, haze, fog, smoke, aerosol, and other volumetric signals.",
    driving_datasets=(
        "air_quality",
        "weather",
        "wind",
        "humidity",
        "terrain",
    ),
    unreal_strategy=(
        "Use volumetric fog, material parameter collections, 3D textures, Niagara sprites, or sparse volume textures. "
        "Datasets should drive density, color, altitude bands, wind drift, and temporal changes."
    ),
    taichi_strategy=(
        "Use coarse voxel grids or screen-space overlays for reference previews. Favor low resolution volume cells "
        "and time-step controls for cross-platform use."
    ),
    data_requirements=(
        "lat/lon/alt grid or station interpolation",
        "pollutant concentration",
        "time coverage",
        "wind vector or drift proxy",
    ),
    performance_notes="Use sparse volumes and update rates lower than frame rate. Mobile should use overlays or low-res fog.",
    simulation_model=(
        "Advection/dispersion approximation: datasets provide pollutant concentration and weather fields; "
        "renderer updates coarse density volumes with wind drift, decay, and interpolation rather than full CFD."
    ),
)


CLOUD_WEATHER_LAYER = RenderEffectLayer(
    layer_id="cloud_weather",
    domain="atmosphere",
    purpose="Render cloud cover, precipitation hints, storm systems, and weather context.",
    driving_datasets=(
        "satellite_imagery",
        "weather",
        "radar",
        "humidity",
    ),
    unreal_strategy="Use sky atmosphere, volumetric clouds, weather materials, and time-sliced texture updates.",
    taichi_strategy="Use low-resolution cloud masks or billboards for preview and algorithm tests.",
    data_requirements=(
        "cloud mask or satellite texture",
        "time coverage",
        "optional precipitation/radar field",
    ),
    performance_notes="Global orbit views can use texture layers; first-person views need localized volumetric detail.",
    simulation_model="Texture/volume evolution driven by weather time slices; full cloud physics is out of scope for MVP.",
)


DEFAULT_RENDER_EFFECT_LAYERS = (
    # 目前只列預設效果契約；真正 renderer 啟用哪些 layer 由前端或 bridge profile 決定。
    WATER_SURFACE_LAYER,
    ATMOSPHERE_QUALITY_LAYER,
    CLOUD_WEATHER_LAYER,
)


def render_effect_layers_for_domain(domain: str) -> tuple[RenderEffectLayer, ...]:
    # domain 查詢是給 renderer/文件產生器使用，不應在這裡做模糊推斷。
    wanted = domain.strip().lower()
    return tuple(layer for layer in DEFAULT_RENDER_EFFECT_LAYERS if layer.domain == wanted)
