from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main


class CliRendererContractTests(unittest.TestCase):
    def test_cli_prints_render_profile_without_default_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["--db", str(db_path), "--show-render-profile", "taichi", "--show-render-profile", "unreal"])

        self.assertEqual(0, rc)
        text = output.getvalue()
        self.assertIn("[render-profile]", text)
        self.assertIn("frontend=taichi", text)
        self.assertIn("frontend=unreal", text)

    def test_cli_lists_render_effect_and_simulation_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["--db", str(db_path), "--list-render-effects", "--list-simulation-contracts"])

        self.assertEqual(0, rc)
        text = output.getvalue()
        self.assertIn("[render-effect] water_surface", text)
        self.assertIn("[simulation-input] water_boundary_conditions", text)
        self.assertIn("[simulation-backend] water_visual_physics_bridge", text)


if __name__ == "__main__":
    unittest.main()
