from __future__ import annotations

import unittest
import io
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.core import main
from api_launcher.library_actions import LibraryContext, build_library_actions, enabled_action_ids


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


if __name__ == "__main__":
    unittest.main()
