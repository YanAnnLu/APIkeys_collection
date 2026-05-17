from __future__ import annotations

import unittest

from api_launcher.render_effects import DEFAULT_RENDER_EFFECT_LAYERS, render_effect_layers_for_domain


class RenderEffectTests(unittest.TestCase):
    def test_default_effect_layers_cover_water_and_air(self) -> None:
        layer_ids = {layer.layer_id for layer in DEFAULT_RENDER_EFFECT_LAYERS}

        self.assertIn("water_surface", layer_ids)
        self.assertIn("air_quality_volume", layer_ids)

    def test_water_layer_is_data_driven_but_not_dataset_only(self) -> None:
        water = next(layer for layer in DEFAULT_RENDER_EFFECT_LAYERS if layer.layer_id == "water_surface")

        self.assertIn("bathymetry", water.driving_datasets)
        self.assertIn("particle", water.unreal_strategy.lower())
        self.assertIn("shader", water.performance_notes.lower())
        self.assertIn("physics", water.simulation_model.lower())
        self.assertIn("gerstner", water.simulation_model.lower())

    def test_domain_filter_returns_atmosphere_layers(self) -> None:
        layers = render_effect_layers_for_domain("atmosphere")

        self.assertGreaterEqual(len(layers), 2)
        self.assertTrue(all(layer.domain == "atmosphere" for layer in layers))


if __name__ == "__main__":
    unittest.main()
