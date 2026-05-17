from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from api_launcher.rendering_profiles import (
    build_render_backend_profile,
    default_taichi_backend_order,
    default_unreal_graphics_api_order,
    tile_budget_for_tier,
)


class RenderingProfileTests(unittest.TestCase):
    def test_taichi_backend_order_is_platform_aware(self) -> None:
        self.assertEqual(("metal", "vulkan", "opengl", "cpu"), default_taichi_backend_order("Darwin"))
        with patch("api_launcher.rendering_profiles.cuda_runtime_available", return_value=False):
            self.assertEqual(("vulkan", "opengl", "cpu"), default_taichi_backend_order("Windows"))
        with patch("api_launcher.rendering_profiles.cuda_runtime_available", return_value=True):
            self.assertEqual(("cuda", "vulkan", "opengl", "cpu"), default_taichi_backend_order("Linux"))

    def test_unreal_graphics_api_order_is_platform_aware(self) -> None:
        self.assertEqual(("metal",), default_unreal_graphics_api_order("Darwin"))
        self.assertEqual(("directx12", "vulkan", "directx11"), default_unreal_graphics_api_order("Windows"))
        self.assertEqual(("vulkan", "opengl"), default_unreal_graphics_api_order("Linux"))

    def test_performance_tier_controls_tile_budget(self) -> None:
        self.assertEqual((2, 3, 30), tile_budget_for_tier("mobile"))
        self.assertEqual((12, 14, 60), tile_budget_for_tier("workstation"))

    def test_profile_can_be_forced_for_mobile_unreal(self) -> None:
        with patch.dict(os.environ, {"APIKEYS_RENDER_PERFORMANCE_TIER": "mobile"}):
            profile = build_render_backend_profile("unreal", "Darwin")

        self.assertEqual("unreal", profile.frontend)
        self.assertEqual(("metal",), profile.graphics_api_order)
        self.assertEqual("mobile", profile.performance_tier)
        self.assertEqual(3, profile.default_stream_radius_tiles)


if __name__ == "__main__":
    unittest.main()
