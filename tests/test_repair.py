from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.repository import ApiCatalogRepository
from api_launcher.downloads.repair import (
    download_repair_agent_payload,
    repair_summary,
    repair_suggestion_for_result,
    scan_download_manifests,
    verify_manifest_file,
)


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

    def test_agent_payload_includes_repair_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(
                build_asset_manifest(payload, {"provider_id": "sample", "download_url": "https://example.test/sample.bin"}),
                payload.with_suffix(".bin.manifest.json"),
            )
            payload.unlink()

            agent_payload = download_repair_agent_payload([verify_manifest_file(manifest_path)])

        self.assertEqual(1, agent_payload["issue_count"])
        self.assertEqual(1, agent_payload["requeue_count"])
        self.assertEqual("requeue_download", agent_payload["issues"][0]["repair_suggestion"]["action_id"])
        self.assertEqual("sample", agent_payload["issues"][0]["repair_suggestion"]["plan_entry"]["provider_id"])

    def test_cli_verify_downloads_json_uses_selected_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "downloads"
            root.mkdir()
            payload = root / "sample.bin"
            payload.write_bytes(b"abc")
            write_manifest(
                build_asset_manifest(payload, {"provider_id": "gebco", "download_url": "https://example.test/sample.bin"}),
                payload.with_suffix(".bin.manifest.json"),
            )
            payload.unlink()
            launcher_db = Path(tmpdir) / "launcher.sqlite"
            conn = connect_db(launcher_db)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
            finally:
                conn.close()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(launcher_db),
                        "--verify-downloads-json",
                        "--downloads-root",
                        str(root),
                    ]
                )

        self.assertEqual(0, rc)
        agent_payload = json.loads(output.getvalue())
        self.assertEqual(1, agent_payload["checked_count"])
        self.assertEqual("missing", agent_payload["issues"][0]["status"])


if __name__ == "__main__":
    unittest.main()
