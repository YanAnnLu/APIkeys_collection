from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.tile_manifests import build_global_grid_manifest, read_tile_manifest, tile_id, write_tile_manifest


class TileManifestTests(unittest.TestCase):
    def test_tile_id_is_stable_and_path_like(self) -> None:
        self.assertEqual(
            "gebco_2025/2025/lod2/x3/y4",
            tile_id("gebco:2025", "2025", 2, 3, 4),
        )

    def test_global_grid_manifest_builds_expected_tiles(self) -> None:
        manifest = build_global_grid_manifest(
            dataset_uid="gebco:2025",
            version="2025",
            lod=0,
            lon_step_degrees=180.0,
            lat_step_degrees=90.0,
            uri_template="tiles/{tile_id}.npy",
            tile_format="npy:int16:elevation",
            role="topography_tile",
        )

        self.assertEqual(4, len(manifest.tiles))
        self.assertEqual(-180.0, manifest.tiles[0].bounds.west)
        self.assertEqual(0.0, manifest.tiles[0].bounds.south)
        self.assertEqual("tiles/gebco_2025/2025/lod0/x0/y0.npy", manifest.tiles[0].uri)

    def test_manifest_round_trips_json(self) -> None:
        manifest = build_global_grid_manifest(
            dataset_uid="hyg:v38",
            version="3.8",
            lod=1,
            lon_step_degrees=360.0,
            lat_step_degrees=180.0,
            uri_template="stars/{tile_id}.csv",
            tile_format="csv:xyz_mag",
            metadata={"frontend_consumers": ["taichi", "unreal"]},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tile_manifest.json"
            write_tile_manifest(manifest, path)
            loaded = read_tile_manifest(path)

        self.assertEqual(manifest.manifest_id, loaded.manifest_id)
        self.assertEqual(("taichi", "unreal"), tuple(loaded.metadata["frontend_consumers"]))

    def test_global_grid_manifest_rejects_uneven_steps(self) -> None:
        with self.assertRaises(ValueError):
            build_global_grid_manifest(
                dataset_uid="bad",
                version="",
                lod=0,
                lon_step_degrees=7.0,
                lat_step_degrees=90.0,
                uri_template="{tile_id}",
                tile_format="bin",
            )


if __name__ == "__main__":
    unittest.main()
