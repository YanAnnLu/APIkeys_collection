# 這份測試鎖定 simulation bridge contract，避免未實作物理流程被誤當可用。
from __future__ import annotations

import unittest

from api_launcher.simulation_bridge import (
    AIR_QUALITY_SIMULATION_BACKEND,
    WATER_INPUT_CONTRACT,
    WATER_SIMULATION_BACKEND,
    simulation_backends_for_domain,
)


class SimulationBridgeTests(unittest.TestCase):
    def test_water_contract_separates_data_from_simulation(self) -> None:
        self.assertIn("coastline_mask", WATER_INPUT_CONTRACT.required_roles)
        self.assertIn("bathymetry_grid", WATER_INPUT_CONTRACT.required_roles)
        self.assertIn("wind_field", WATER_INPUT_CONTRACT.optional_roles)
        self.assertIn("simulation backend", WATER_INPUT_CONTRACT.notes)

    def test_backends_are_contract_only_for_now(self) -> None:
        self.assertEqual("contract_only", WATER_SIMULATION_BACKEND.implementation_status)
        self.assertEqual("contract_only", AIR_QUALITY_SIMULATION_BACKEND.implementation_status)
        self.assertEqual("planned", WATER_SIMULATION_BACKEND.maturity)

    def test_domain_filter_returns_water_backend(self) -> None:
        backends = simulation_backends_for_domain("hydrosphere")

        self.assertEqual((WATER_SIMULATION_BACKEND,), backends)


if __name__ == "__main__":
    unittest.main()
