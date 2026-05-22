# 這份測試鎖定下載 manifest repair 掃描，避免 missing/checksum/size 狀態回歸。
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.repository import ApiCatalogRepository
from api_launcher.downloads.repair import (
    download_manifest_verification_event_context,
    download_repair_agent_payload,
    log_download_requeue_requested,
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
        self.assertEqual("source_url_missing", suggestion.outcome_bucket)
        self.assertEqual("inspect_manifest_or_recreate_plan", suggestion.next_action)

    def test_adapter_manifest_without_source_url_routes_to_adapter_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(
                build_asset_manifest(
                    payload,
                    {
                        "provider_id": "sample",
                        "dataset_version": {
                            "dataset_id": "sample-dataset",
                            "metadata": {
                                "adapter_review": {
                                    "adapter_id": "sample_adapter",
                                    "required_action": "resolve_download_url",
                                    "outcome_bucket": "source_resolution_required",
                                }
                            },
                        },
                    },
                ),
                payload.with_suffix(".bin.manifest.json"),
            )
            payload.unlink()

            result = verify_manifest_file(manifest_path)
            suggestion = repair_suggestion_for_result(result)

        self.assertEqual("adapter_repair_review", suggestion.action_id)
        self.assertFalse(suggestion.can_requeue)
        self.assertEqual("adapter_source_missing", suggestion.outcome_bucket)
        self.assertEqual("run_adapter_review_or_resolve_adapter_plan", suggestion.next_action)
        self.assertEqual("sample_adapter", suggestion.adapter_id)
        self.assertEqual("source_resolution_required", suggestion.review_hint["outcome_bucket"])

    def test_adapter_non_http_source_url_stays_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = Path(tmpdir) / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(
                build_asset_manifest(
                    payload,
                    {
                        "provider_id": "sample",
                        "api_base_url": "s3://example-bucket/sample.bin",
                        "dataset_version": {"metadata": {"adapter_id": "s3_adapter"}},
                    },
                ),
                payload.with_suffix(".bin.manifest.json"),
            )
            payload.unlink()

            suggestion = repair_suggestion_for_result(verify_manifest_file(manifest_path))

        self.assertEqual("adapter_repair_review", suggestion.action_id)
        self.assertFalse(suggestion.can_requeue)
        self.assertEqual("adapter_source_not_requeueable", suggestion.outcome_bucket)
        self.assertEqual("run_adapter_specific_repair_or_export_review", suggestion.next_action)
        self.assertEqual("s3_adapter", suggestion.adapter_id)

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

    def test_manifest_verification_event_context_bounds_issue_preview(self) -> None:
        agent_payload = {
            "summary": {"missing": 25},
            "checked_count": 25,
            "issue_count": 25,
            "requeue_count": 25,
            "issues": [
                {
                    "status": "missing",
                    "provider_id": f"provider-{index}",
                    "dataset_id": "sample",
                    "version": "1",
                    "manifest_path": f"downloads/{index}.manifest.json",
                    "payload_path": f"downloads/{index}.bin",
                    "repair_suggestion": {
                        "action_id": "requeue_download",
                        "can_requeue": True,
                        "outcome_bucket": "requeue_ready",
                        "next_action": "requeue_download",
                        "adapter_id": "sample_adapter",
                    },
                }
                for index in range(25)
            ],
        }

        context = download_manifest_verification_event_context(
            agent_payload,
            db_path="state/test.sqlite",
            downloads_root="downloads",
        )

        self.assertEqual("state/test.sqlite", context["db_path"])
        self.assertEqual("downloads", context["downloads_root"])
        self.assertEqual(20, context["issue_preview_count"])
        self.assertEqual(20, len(context["issues"]))
        self.assertEqual("provider-0", context["issues"][0]["provider_id"])
        self.assertEqual("provider-19", context["issues"][-1]["provider_id"])
        self.assertEqual("requeue_ready", context["issues"][0]["repair_outcome_bucket"])
        self.assertEqual("requeue_download", context["issues"][0]["repair_next_action"])
        self.assertEqual("sample_adapter", context["issues"][0]["adapter_id"])

    def test_log_download_requeue_requested_includes_outcome_and_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = root / "sample.bin"
            payload.write_bytes(b"abc")
            manifest_path = write_manifest(
                build_asset_manifest(payload, {"provider_id": "sample", "download_url": "https://example.test/sample.bin"}),
                payload.with_suffix(".bin.manifest.json"),
            )
            payload.unlink()
            result = verify_manifest_file(manifest_path)
            suggestion = repair_suggestion_for_result(result)
            calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            def fake_logger(*args: object, **kwargs: object) -> None:
                calls.append((args, kwargs))

            log_download_requeue_requested(
                result,
                suggestion,
                outcome="queued",
                job_id="job-1",
                db_path="state/test.sqlite",
                downloads_root=root,
                logger=fake_logger,
            )

        self.assertEqual("download_repair_requeue_requested", calls[0][0][0])
        self.assertEqual("download_repair", calls[0][1]["component"])
        self.assertEqual("info", calls[0][1]["level"])
        context = calls[0][1]["context"]
        self.assertEqual("queued", context["outcome"])
        self.assertEqual("sample", context["provider_id"])
        self.assertEqual("missing", context["status"])
        self.assertEqual("requeue_download", context["repair_action_id"])
        self.assertEqual("requeue_ready", context["repair_outcome_bucket"])
        self.assertEqual("requeue_download", context["repair_next_action"])
        self.assertEqual("job-1", context["job_id"])
        self.assertEqual("state/test.sqlite", context["db_path"])

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

            with redirect_stdout(output), patch("api_launcher.core.log_event") as log_event_mock:
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
        log_event_mock.assert_called_once()
        self.assertEqual("download_manifest_verification_completed", log_event_mock.call_args.args[0])
        self.assertEqual("download_repair", log_event_mock.call_args.kwargs["component"])
        self.assertEqual("warning", log_event_mock.call_args.kwargs["level"])
        event_context = log_event_mock.call_args.kwargs["context"]
        self.assertEqual(1, event_context["checked_count"])
        self.assertEqual(1, event_context["issue_count"])
        self.assertEqual(1, event_context["requeue_count"])
        self.assertEqual("missing", event_context["issues"][0]["status"])
        self.assertEqual("requeue_download", event_context["issues"][0]["repair_action_id"])
        self.assertEqual("requeue_ready", event_context["issues"][0]["repair_outcome_bucket"])


if __name__ == "__main__":
    unittest.main()
