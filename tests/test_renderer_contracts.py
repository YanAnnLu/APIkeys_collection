# 這份測試鎖定 renderer dataset contract，避免 Taichi/Unreal 資產識別不一致。
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.db import connect_db
from api_launcher.renderer_contracts import (
    GEBCO_2025_TOPOGRAPHY_CONTRACT,
    HYG_V38_STAR_CONTRACT,
    TAICHI_GLOBAL_BATHYMETRY_CONTRACTS,
    TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID,
)
from api_launcher.repository import ApiCatalogRepository


class RendererContractTests(unittest.TestCase):
    def test_contract_ids_are_stable_and_renderer_specific(self) -> None:
        dataset_ids = {contract.dataset_id for contract in TAICHI_GLOBAL_BATHYMETRY_CONTRACTS}

        self.assertEqual(TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID, GEBCO_2025_TOPOGRAPHY_CONTRACT.renderer)
        self.assertIn("gebco_2025_elevation", dataset_ids)
        self.assertIn("hyg_v38_bright_star_catalog", dataset_ids)
        self.assertEqual("topography_grid", GEBCO_2025_TOPOGRAPHY_CONTRACT.bridge_asset_role)
        self.assertEqual("star_catalog", HYG_V38_STAR_CONTRACT.bridge_asset_role)

    def test_contract_cache_paths_match_renderer_expectations(self) -> None:
        self.assertTrue(
            GEBCO_2025_TOPOGRAPHY_CONTRACT.cache_path(step=2).endswith(
                ".cache\\taichi_earth\\gebco_2025_topo_cache_step2.npy"
            )
            or GEBCO_2025_TOPOGRAPHY_CONTRACT.cache_path(step=2).endswith(
                ".cache/taichi_earth/gebco_2025_topo_cache_step2.npy"
            )
        )
        self.assertTrue(HYG_V38_STAR_CONTRACT.cache_path().endswith("stars_cache.npy"))

    def test_contracts_can_seed_datasets_and_bridge_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                for contract in TAICHI_GLOBAL_BATHYMETRY_CONTRACTS:
                    repo.upsert_dataset(contract.dataset())
                    repo.upsert_render_bridge_asset(contract.bridge_asset(contract.cache_path(step=2)))

                assets = repo.list_render_bridge_assets(TAICHI_GLOBAL_BATHYMETRY_RENDERER_ID)
                datasets = repo.list_datasets()
            finally:
                conn.close()

        self.assertEqual(2, len(datasets))
        self.assertEqual(2, len(assets))
        self.assertEqual({"star_catalog", "topography_grid"}, {asset.asset_role for asset in assets})


if __name__ == "__main__":
    unittest.main()
