from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from api_launcher.workspace_inventory import (
    build_workspace_inventory,
    render_workspace_inventory,
    workspace_inventory_to_json,
)


class WorkspaceInventoryTests(unittest.TestCase):
    def test_inventory_classifies_files_and_skips_runtime_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_lines(root / "api_launcher" / "core.py", 601)
            write_lines(root / "frontends" / "tk" / "launcher_ui.py", 602)
            write_text(root / "docs" / "README.md", "# Docs\n")
            write_text(root / "config" / "launcher_integrations.example.json", "{}\n")
            write_text(root / "APIkeys_collection.sqlite", "")
            write_lines(root / "state" / "ignored.py", 900)
            write_lines(root / ".venv" / "ignored.py", 900)

            inventory = build_workspace_inventory(root)

        self.assertEqual(1, inventory.category_counts["api_launcher/core_infra"])
        self.assertEqual(1, inventory.category_counts["frontend"])
        self.assertEqual(1, inventory.category_counts["docs"])
        self.assertIn("APIkeys_collection.sqlite", inventory.root_runtime_files)
        large_paths = {item["path"] for item in inventory.large_python_files}
        self.assertEqual({"api_launcher/core.py", "frontends/tk/launcher_ui.py"}, large_paths)

    def test_inventory_render_and_json_are_handoff_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_lines(root / "api_launcher" / "crawlers" / "dataset_sources.py", 600)

            inventory = build_workspace_inventory(root)
            payload = json.loads(workspace_inventory_to_json(inventory))
            report = render_workspace_inventory(inventory)

        self.assertIn("category_counts", payload)
        self.assertIn("large_python_files", payload)
        self.assertIn("api_launcher/crawlers/dataset_sources.py", report)
        self.assertIn("Split by source type", report)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_lines(path: Path, count: int) -> None:
    write_text(path, "\n".join("print('x')" for _ in range(count)) + "\n")


if __name__ == "__main__":
    unittest.main()
