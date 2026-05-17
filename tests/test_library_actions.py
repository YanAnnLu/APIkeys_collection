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
            local_status="downloaded",
            install_id="inst_123",
            manifest_health="checksum_mismatch",
        )

        self.assertIn("repair", enabled_action_ids(context))

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


if __name__ == "__main__":
    unittest.main()
