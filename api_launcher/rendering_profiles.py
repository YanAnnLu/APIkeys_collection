from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderBackendProfile:
    # backend profile 是 runtime 能力摘要，用來選擇 Taichi/Unreal 預設而非硬編環境。
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
    # CUDA_VISIBLE_DEVICES 明確停用時尊重使用者設定，即使機器上有 nvidia-smi。
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip().lower()
    if visible in {"-1", "none", "no", "false"}:
        return False
    return bool(shutil.which("nvidia-smi") or os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME"))


def is_probable_mobile() -> bool:
    # 行動/低功耗裝置可由環境變數覆寫；自動判斷只做保守提示。
    machine = platform.machine().lower()
    marker = os.environ.get("APIKEYS_RENDER_DEVICE_CLASS", "").strip().lower()
    if marker in {"mobile", "tablet", "low_power"}:
        return True
    return machine in {"arm", "arm64", "aarch64"} and platform.system() != "Darwin"


def default_taichi_backend_order(system: str | None = None) -> tuple[str, ...]:
    # Taichi backend 順序按平台慣例排列；最後永遠保留 CPU fallback。
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
    # Unreal graphics API 只給偏好順序，實際可用性仍由 Unreal 專案/平台決定。
    system = system or platform.system()
    if system == "Darwin":
        return ("metal",)
    if system == "Windows":
        return ("directx12", "vulkan", "directx11")
    if system == "Linux":
        return ("vulkan", "opengl")
    return ("vulkan", "opengl")


def infer_performance_tier() -> str:
    # 使用者可用 env 明確覆蓋 tier，方便 CI 或低階機器測試 renderer 路徑。
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
    # 回傳 max_parallel_tiles / stream_radius / target_fps，供 tile streaming 先有保守預設。
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
    # profile 是 capability summary，不在這裡啟動 renderer 或檢查完整引擎安裝。
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
