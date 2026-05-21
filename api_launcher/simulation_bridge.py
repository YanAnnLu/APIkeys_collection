from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class SimulationInputContract:
    # simulation bridge 目前只定義輸入契約，不假裝物理模擬已經實作。
    input_id: str
    domain: str
    description: str
    required_roles: tuple[str, ...]
    optional_roles: tuple[str, ...] = ()
    expected_units: dict[str, str] = dataclasses.field(default_factory=dict)
    notes: str = ""


@dataclasses.dataclass(frozen=True)
class SimulationBackendContract:
    # backend contract 描述未來模擬後端該吃什麼、吐什麼，不綁定任何實作框架。
    backend_id: str
    domain: str
    maturity: str
    frontend_targets: tuple[str, ...]
    input_contracts: tuple[str, ...]
    output_roles: tuple[str, ...]
    implementation_status: str
    notes: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


WATER_INPUT_CONTRACT = SimulationInputContract(
    input_id="water_boundary_conditions",
    domain="hydrosphere",
    description="Boundary-condition inputs for future water simulation and visual water behavior.",
    required_roles=("coastline_mask", "bathymetry_grid"),
    optional_roles=("wind_field", "tide_timeseries", "current_vector_field", "river_network"),
    expected_units={
        "bathymetry_grid": "meters",
        "wind_field": "m/s",
        "tide_timeseries": "meters",
        "current_vector_field": "m/s",
    },
    notes="Datasets define where water is and what drives it; the simulation backend defines how water moves.",
)


AIR_QUALITY_INPUT_CONTRACT = SimulationInputContract(
    input_id="air_quality_boundary_conditions",
    domain="atmosphere",
    description="Boundary-condition inputs for future air-quality volume rendering and simplified dispersion.",
    required_roles=("pollutant_concentration", "time_index"),
    optional_roles=("wind_field", "humidity_grid", "terrain_grid", "station_locations"),
    expected_units={
        "pollutant_concentration": "provider-specific; must normalize per pollutant",
        "wind_field": "m/s",
        "humidity_grid": "percent",
        "terrain_grid": "meters",
    },
    notes="Full CFD is out of scope for the launcher; start with coarse advection/dispersion or visualization-only modes.",
)


WATER_SIMULATION_BACKEND = SimulationBackendContract(
    backend_id="water_visual_physics_bridge",
    domain="hydrosphere",
    maturity="planned",
    frontend_targets=("unreal", "taichi"),
    input_contracts=(WATER_INPUT_CONTRACT.input_id,),
    output_roles=("water_surface_parameters", "foam_mask", "flow_map", "wave_lod_policy"),
    implementation_status="contract_only",
    notes=(
        "No water physics engine is implemented yet. This bridge reserves the interface for future Gerstner/FFT, "
        "shallow-water, flow-map, or renderer-native water systems."
    ),
)


AIR_QUALITY_SIMULATION_BACKEND = SimulationBackendContract(
    backend_id="air_quality_volume_bridge",
    domain="atmosphere",
    maturity="planned",
    frontend_targets=("unreal", "taichi"),
    input_contracts=(AIR_QUALITY_INPUT_CONTRACT.input_id,),
    output_roles=("volume_density_grid", "volume_color_parameters", "advection_lod_policy"),
    implementation_status="contract_only",
    notes=(
        "No atmospheric physics engine is implemented yet. This bridge starts as a visualization and simplified "
        "transport contract for volumetric fog or coarse voxel previews."
    ),
)


DEFAULT_SIMULATION_INPUT_CONTRACTS = (
    # 這些 contract 是資料角色清單，讓 adapter 知道哪些資料能餵給未來模擬。
    WATER_INPUT_CONTRACT,
    AIR_QUALITY_INPUT_CONTRACT,
)

DEFAULT_SIMULATION_BACKENDS = (
    WATER_SIMULATION_BACKEND,
    AIR_QUALITY_SIMULATION_BACKEND,
)


def simulation_backends_for_domain(domain: str) -> tuple[SimulationBackendContract, ...]:
    # 僅做 domain 精準篩選；沒有後端時應由呼叫端顯示「尚未實作」而不是硬猜。
    wanted = domain.strip().lower()
    return tuple(backend for backend in DEFAULT_SIMULATION_BACKENDS if backend.domain == wanted)
