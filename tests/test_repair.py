from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.repair import repair_summary, repair_suggestion_for_result, scan_download_manifests, verify_manifest_file


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

    def test_missing_payload_with_source_url_can_be_requeued(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(
                build_asset_manifest(payload, {"provider_id": "sample", "download_url": "https://example.test/sample.bin"}),
                payload.with_suffix(".bin.manifest.json"),
            )
            payload.unlink()

            suggestion = repair_suggestion_for_result(verify_manifest_file(manifest_path))

        self.assertEqual("requeue_download", suggestion.action_id)
        self.assertTrue(suggestion.can_requeue)
        self.assertEqual("sample", suggestion.plan_entry["provider_id"])
        self.assertEqual("https://example.test/sample.bin", suggestion.plan_entry["download_url"])

    def test_missing_source_url_requires_manual_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(build_asset_manifest(payload, {"provider_id": "sample"}), payload.with_suffix(".bin.manifest.json"))
            payload.unlink()

            suggestion = repair_suggestion_for_result(verify_manifest_file(manifest_path))

        self.assertEqual("manual_recover", suggestion.action_id)
        self.assertFalse(suggestion.can_requeue)

    def test_scan_download_manifests_summarizes_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            write_manifest(build_asset_manifest(payload, {"provider_id": "sample"}), payload.with_suffix(".bin.manifest.json"))

            results = scan_download_manifests(tmpdir)

        self.assertEqual({"ok": 1, "missing": 0, "size_mismatch": 0, "checksum_mismatch": 0, "manifest_error": 0}, repair_summary(results))


if __name__ == "__main__":
    unittest.main()
