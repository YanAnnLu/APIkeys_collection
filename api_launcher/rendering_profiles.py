from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderBackendProfile:
    id: str
    frontend: str
    platform_name: str
    backend_order: tuple[str, ...]
    graphics_api_order: tuple[str, ...]
    performance_tier: str
    max_parallel_tiles: int
    default_stream_radius_tiles: int
    target_fps: int
    notes: str


def cuda_runtime_available() -> bool:
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip().lower()
    if visible in {"-1", "none", "no", "false"}:
        return False
    return bool(shutil.which("nvidia-smi") or os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME"))


def is_probable_mobile() -> bool:
    machine = platform.machine().lower()
    marker = os.environ.get("APIKEYS_RENDER_DEVICE_CLASS", "").strip().lower()
    if marker in {"mobile", "tablet", "low_power"}:
        return True
    return machine in {"arm", "arm64", "aarch64"} and platform.system() != "Darwin"


def default_taichi_backend_order(system: str | None = None) -> tuple[str, ...]:
    system = system or platform.system()
    if system == "Darwin":
        return ("metal", "vulkan", "opengl", "cpu")
    if system == "Windows":
        if cuda_runtime_available():
            return ("cuda", "vulkan", "opengl", "cpu")
        return ("vulkan", "opengl", "cpu")
    if system == "Linux":
        if cuda_runtime_available():
            return ("cuda", "vulkan", "opengl", "cpu")
        return ("vulkan", "opengl", "cpu")
    return ("vulkan", "opengl", "cpu")


def default_unreal_graphics_api_order(system: str | None = None) -> tuple[str, ...]:
    system = system or platform.system()
    if system == "Darwin":
        return ("metal",)
    if system == "Windows":
        return ("directx12", "vulkan", "directx11")
    if system == "Linux":
        return ("vulkan", "opengl")
    return ("vulkan", "opengl")


def infer_performance_tier() -> str:
    explicit = os.environ.get("APIKEYS_RENDER_PERFORMANCE_TIER", "").strip().lower()
    if explicit in {"mobile", "low", "medium", "high", "workstation"}:
        return explicit
    if is_probable_mobile():
        return "mobile"
    if cuda_runtime_available():
        return "high"
    if platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        return "medium"
    return "medium"


def tile_budget_for_tier(tier: str) -> tuple[int, int, int]:
    if tier == "mobile":
        return 2, 3, 30
    if tier == "low":
        return 3, 4, 30
    if tier == "high":
        return 8, 10, 60
    if tier == "workstation":
        return 12, 14, 60
    return 5, 6, 60


def build_render_backend_profile(frontend: str = "taichi", system: str | None = None) -> RenderBackendProfile:
    system = system or platform.system()
    tier = infer_performance_tier()
    max_parallel_tiles, stream_radius, target_fps = tile_budget_for_tier(tier)
    frontend = frontend.strip().lower()
    backend_order = default_taichi_backend_order(system) if frontend == "taichi" else ()
    graphics_order = default_unreal_graphics_api_order(system) if frontend == "unreal" else ()
    if frontend == "taichi":
        notes = "Reference renderer profile. Use for GPU/CPU smoke tests and algorithm prototyping."
    elif frontend == "unreal":
        notes = "Final frontend profile. Unreal should render and stream data, not own raw scientific datasets."
    else:
        notes = "Generic renderer profile."
    return RenderBackendProfile(
        id=f"{frontend}_{system.lower()}_{tier}",
        frontend=frontend,
        platform_name=system,
        backend_order=backend_order,
        graphics_api_order=graphics_order,
        performance_tier=tier,
        max_parallel_tiles=max_parallel_tiles,
        default_stream_radius_tiles=stream_radius,
        target_fps=target_fps,
        notes=notes,
    )
