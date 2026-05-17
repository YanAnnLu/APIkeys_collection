from __future__ import annotations

import unittest

from api_launcher.integrations import UnrealProjectProfile, unreal_project_profiles_from_config
from api_launcher.models import RenderBridgeAsset
from api_launcher.unreal_bridge import build_unreal_bridge_targets, safe_name, unreal_content_root


class UnrealBridgeTests(unittest.TestCase):
    def test_unreal_profile_loads_from_config(self) -> None:
        profiles = unreal_project_profiles_from_config(
            {
                "unreal_projects": [
                    {
                        "id": "ue",
                        "label": "UE",
                        "enabled": True,
                        "engine_root": "C:/UE",
                        "editor_command": ["UnrealEditor"],
                        "project_path": "K:/Twin/Twin.uproject",
                    }
                ]
            }
        )

        self.assertEqual(1, len(profiles))
        self.assertEqual("ue", profiles[0].id)

    def test_content_root_defaults_next_to_uproject(self) -> None:
        profile = UnrealProjectProfile(
            id="ue",
            label="UE",
            enabled=True,
            engine_root="",
            editor_command=(),
            project_path="K:/Twin/Twin.uproject",
        )

        self.assertTrue(str(unreal_content_root(profile)).replace("\\", "/").endswith("K:/Twin/Content"))

    def test_bridge_targets_are_planned_from_render_assets(self) -> None:
        profile = UnrealProjectProfile(
            id="ue",
            label="UE",
            enabled=True,
            engine_root="",
            editor_command=(),
            project_path="K:/Twin/Twin.uproject",
            bridge_subdir="APIkeysCollection",
        )
        asset = RenderBridgeAsset(
            asset_id="renderer:dataset:topography",
            dataset_uid="gebco:2025",
            renderer="taichi",
            asset_role="topography_grid",
            storage_format="npy",
            path="downloads/gebco/topo.npy",
        )

        targets = build_unreal_bridge_targets([asset], profile)

        self.assertEqual("planned", targets[0].status)
        self.assertIn("/Game/APIkeysCollection/gebco_2025/topography_grid/topo", targets[0].unreal_mount_path)

    def test_safe_name_removes_unreal_unfriendly_chars(self) -> None:
        self.assertEqual("gebco_2025", safe_name("gebco:2025"))


if __name__ == "__main__":
    unittest.main()
