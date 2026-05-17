from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.repair import repair_summary, scan_download_manifests, verify_manifest_file


class RepairTests(unittest.TestCase):
    def test_verify_manifest_accepts_matching_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(
                build_asset_manifest(payload, {"provider_id": "sample", "dataset_version": {"version": "1"}}),
                payload.with_suffix(".bin.manifest.json"),
            )

            result = verify_manifest_file(manifest_path)

        self.assertEqual("ok", result.status)
        self.assertFalse(result.needs_repair)

    def test_verify_manifest_detects_missing_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(build_asset_manifest(payload, {"provider_id": "sample"}), payload.with_suffix(".bin.manifest.json"))
            payload.unlink()

            result = verify_manifest_file(manifest_path)

        self.assertEqual("missing", result.status)
        self.assertTrue(result.needs_repair)

    def test_scan_download_manifests_summarizes_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            write_manifest(build_asset_manifest(payload, {"provider_id": "sample"}), payload.with_suffix(".bin.manifest.json"))

            results = scan_download_manifests(tmpdir)

        self.assertEqual({"ok": 1, "missing": 0, "size_mismatch": 0, "checksum_mismatch": 0, "manifest_error": 0}, repair_summary(results))


if __name__ == "__main__":
    unittest.main()
