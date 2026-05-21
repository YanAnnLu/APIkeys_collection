# 這份測試鎖定 Unreal preview export，避免低解析橋接資產與 manifest 形狀漂移。
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

np_spec = importlib.util.find_spec("numpy")
if np_spec is not None:
    import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_unreal_preview.py"


def load_export_module():
    spec = importlib.util.spec_from_file_location("export_unreal_preview", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UnrealPreviewExportTests(unittest.TestCase):
    def test_project_output_dir_defaults_to_content_bridge_preview(self) -> None:
        module = load_export_module()

        out_dir = module.resolve_output_dir("", "K:/Twin/Twin.uproject", "APIkeysCollection")

        self.assertTrue(str(out_dir).replace("\\", "/").endswith("K:/Twin/Content/APIkeysCollection/Preview"))

    def test_exports_preview_files_and_streaming_manifest(self) -> None:
        if np_spec is None:
            self.skipTest("numpy is an optional renderer dependency")
        module = load_export_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topo = root / "topo.npy"
            stars = root / "stars.npy"
            out = root / "Content" / "APIkeysCollection" / "Preview"
            np.save(topo, np.array([[-2000, -10, 300], [50, 1400, 4200], [-5000, 0, 6000]], dtype=np.int16))
            np.save(stars, np.array([[1.0, 0.0, 0.0, 1.2], [0.0, 1.0, 0.0, 2.3]], dtype=np.float32))

            rc = module.main_from_args_for_test(
                [
                    "--topography",
                    str(topo),
                    "--stars",
                    str(stars),
                    "--out",
                    str(out),
                    "--sample-step",
                    "1",
                ]
            )

            self.assertEqual(0, rc)
            self.assertTrue((out / "EarthPreview.obj").exists())
            self.assertTrue((out / "EarthPreview.mtl").exists())
            self.assertTrue((out / "StarsPreview.csv").exists())
            self.assertTrue((out / "TileManifest.json").exists())
            manifest = json.loads((out / "APIkeysBridgeManifest.json").read_text(encoding="utf-8"))
            self.assertIn("camera_driven_streaming", manifest)
            self.assertIn("first_person", manifest["camera_driven_streaming"])
            self.assertIn("render_backend_profiles", manifest)
            self.assertIn("unreal_frontend", manifest["render_backend_profiles"])
            self.assertTrue(manifest["assets"]["tile_manifest"].endswith("TileManifest.json"))


if __name__ == "__main__":
    unittest.main()
