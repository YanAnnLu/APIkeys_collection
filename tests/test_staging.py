from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.manifests import build_asset_manifest, read_manifest, write_manifest
from api_launcher.downloads.staging import promote_staged_payload, safe_path_part, staging_paths_for_plan_entry, staging_root_for_final_path


class StagingTests(unittest.TestCase):
    def test_staging_paths_are_stable_for_resume(self) -> None:
        entry = {
            "provider_id": "sample/provider",
            "dataset_version": {"dataset_id": "grid", "version": "2026"},
        }

        first = staging_paths_for_plan_entry(entry, Path("downloads/sample/grid.nc"))
        second = staging_paths_for_plan_entry(entry, Path("downloads/sample/grid.nc"))

        self.assertEqual(first.part_path, second.part_path)
        self.assertIn("sample_provider", str(first.part_path))
        self.assertIn("2026", str(first.part_path))

    def test_promote_writes_final_payload_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            final = Path(tmpdir) / "downloads" / "sample.bin"
            entry = {
                "provider_id": "sample",
                "download_url": "https://example.test/sample.bin",
                "dataset_version": {"dataset_uid": "sample:grid", "dataset_id": "grid", "version": "1.0"},
            }
            paths = staging_paths_for_plan_entry(entry, final)
            paths.payload_path.parent.mkdir(parents=True, exist_ok=True)
            paths.payload_path.write_bytes(b"payload")

            promote_staged_payload(paths, entry)

            self.assertEqual(b"payload", final.read_bytes())
            manifest = read_manifest(paths.final_manifest_path)
            self.assertEqual("sample", manifest.provider_id)
            self.assertEqual("1.0", manifest.version)
            self.assertEqual(7, manifest.size_bytes)

    def test_manifest_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "payload.bin"
            payload.write_bytes(b"abc")
            manifest = build_asset_manifest(payload, {"provider_id": "sample", "download_url": "https://example.test"})
            path = write_manifest(manifest, Path(tmpdir) / "payload.manifest.json")

            self.assertEqual(manifest.sha256, read_manifest(path).sha256)

    def test_safe_path_part_removes_path_separators(self) -> None:
        self.assertEqual("a_b_c", safe_path_part("a/b:c"))

    def test_absolute_external_target_stages_near_target_for_atomic_promote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            final = Path(tmpdir) / "downloads" / "sample.bin"

            self.assertEqual(final.parent / ".apikeys_staging", staging_root_for_final_path(final))


if __name__ == "__main__":
    unittest.main()
