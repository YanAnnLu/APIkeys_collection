# 這份測試鎖定 library action policy，避免 UI/agent 顯示不安全或錯誤動作。
from __future__ import annotations

import unittest
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.library_actions import (
    LibraryContext,
    build_library_actions,
    enabled_action_ids,
    library_action_agent_payload,
    library_action_map,
    library_action_menu_label,
    ordered_library_actions,
)
from api_launcher.manifests import build_asset_manifest, write_manifest


class LibraryActionTests(unittest.TestCase):
    def test_downloadable_uninstalled_source_can_be_added_and_installed(self) -> None:
        context = LibraryContext(provider_id="sample", has_direct_download=True)

        self.assertEqual(("add_to_plan", "install"), enabled_action_ids(context))

    def test_installed_stale_source_can_update_open_render_and_uninstall(self) -> None:
        context = LibraryContext(
            provider_id="sample",
            local_status="managed",
            update_status="stale",
            install_id="inst_123",
            has_direct_download=True,
            has_render_assets=True,
        )

        self.assertEqual(
            ("add_to_plan", "update", "open_database", "render_preview", "uninstall"),
            enabled_action_ids(context),
        )

    def test_manifest_problem_enables_repair(self) -> None:
        context = LibraryContext(
            provider_id="sample",
            local_status="imported",
            install_id="inst_123",
            manifest_health="checksum_mismatch",
        )

        self.assertIn("repair", enabled_action_ids(context))

    def test_repair_action_carries_download_requeue_suggestion(self) -> None:
        context = LibraryContext(
            provider_id="sample",
            local_status="imported",
            install_id="inst_123",
            manifest_health="missing",
            repair_suggestion={
                "action_id": "requeue_download",
                "can_requeue": True,
                "plan_entry": {"provider_id": "sample", "download_url": "https://example.test/sample.bin"},
            },
        )

        action = library_action_map(context)["repair"]

        self.assertTrue(action.enabled)
        self.assertEqual("repair_requeue_ready", action.status_badge)
        self.assertEqual("requeue_download", action.related_repair_suggestion["action_id"])
        self.assertIn("safe requeue", action.reason)

    def test_status_badges_summarize_action_state_for_agents(self) -> None:
        context = LibraryContext(
            provider_id="sample",
            local_status="managed",
            update_status="stale",
            install_id="inst_123",
            has_direct_download=True,
            has_render_assets=False,
        )

        actions = library_action_map(context)

        self.assertEqual("ready_to_plan", actions["add_to_plan"].status_badge)
        self.assertEqual("already_installed", actions["install"].status_badge)
        self.assertEqual("update_available", actions["update"].status_badge)
        self.assertEqual("missing_render_assets", actions["render_preview"].status_badge)
        self.assertEqual("guarded_uninstall_ready", actions["uninstall"].status_badge)

    def test_uninstall_is_marked_destructive(self) -> None:
        context = LibraryContext(provider_id="sample", local_status="managed", install_id="inst_123")
        actions = {action.action_id: action for action in build_library_actions(context)}

        self.assertEqual("destructive", actions["uninstall"].risk)

    def test_action_helpers_keep_ui_from_rebuilding_policy(self) -> None:
        context = LibraryContext(provider_id="sample")
        action_map = library_action_map(context)
        ordered_ids = tuple(action.action_id for action in ordered_library_actions(context))

        self.assertIn("add_to_plan", action_map)
        self.assertEqual("add_to_plan", ordered_ids[0])
        self.assertIn("No direct download", library_action_menu_label(action_map["add_to_plan"]))

    def test_agent_payload_reuses_shared_policy(self) -> None:
        context = LibraryContext(provider_id="sample", local_status="managed", install_id="inst_123")

        payload = library_action_agent_payload(context)

        self.assertEqual("sample", payload["provider_id"])
        self.assertIn("open_database", payload["enabled_action_ids"])
        uninstall = next(action for action in payload["actions"] if action["action_id"] == "uninstall")
        self.assertEqual("guarded_uninstall_ready", uninstall["status_badge"])
        self.assertEqual("destructive", uninstall["risk"])

    def test_cli_prints_library_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(Path(tmp) / "test.sqlite"),
                        "--show-library-actions",
                        "sample",
                        "--library-local-status",
                        "managed",
                        "--library-install-id",
                        "inst_123",
                        "--library-render-assets",
                    ]
                )

        self.assertEqual(0, rc)
        text = output.getvalue()
        self.assertIn("[library-action] open_database enabled", text)
        self.assertIn("[library-action] render_preview enabled", text)
        self.assertIn("badge=guarded_uninstall_ready", text)
        self.assertIn("risk=destructive", text)

    def test_cli_prints_library_actions_json_for_agent_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(Path(tmp) / "test.sqlite"),
                        "--show-library-actions",
                        "sample",
                        "--library-local-status",
                        "managed",
                        "--library-install-id",
                        "inst_123",
                        "--library-actions-json",
                    ]
                )

        self.assertEqual(0, rc)
        payload = json.loads(output.getvalue())
        self.assertEqual("sample", payload["provider_id"])
        self.assertIn("open_database", payload["enabled_action_ids"])
        self.assertEqual("managed", payload["context"]["local_status"])

    def test_cli_library_actions_json_can_attach_repair_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload_file = root / "sample.bin"
            payload_file.write_bytes(b"abc")
            manifest_path = write_manifest(
                build_asset_manifest(
                    payload_file,
                    {"provider_id": "sample", "download_url": "https://example.test/sample.bin"},
                ),
                payload_file.with_suffix(".bin.manifest.json"),
            )
            payload_file.unlink()
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(root / "test.sqlite"),
                        "--show-library-actions",
                        "sample",
                        "--library-local-status",
                        "imported",
                        "--library-install-id",
                        "inst_123",
                        "--library-actions-json",
                        "--library-repair-manifest",
                        str(manifest_path),
                    ]
                )

        self.assertEqual(0, rc)
        payload = json.loads(output.getvalue())
        self.assertEqual("missing", payload["context"]["manifest_health"])
        self.assertEqual(str(manifest_path), payload["context"]["manifest_path"])
        self.assertIn("repair", payload["enabled_action_ids"])
        repair = next(action for action in payload["actions"] if action["action_id"] == "repair")
        self.assertEqual("requeue_download", repair["related_repair_suggestion"]["action_id"])
        self.assertTrue(repair["related_repair_suggestion"]["can_requeue"])


if __name__ == "__main__":
    unittest.main()
