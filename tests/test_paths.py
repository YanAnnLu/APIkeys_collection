from __future__ import annotations

import unittest

from api_launcher.paths import CATALOG_DIR, CONFIG_DIR, PROJECT_ROOT, catalog_file, config_file, local_config_file, state_file


class PathResolverTests(unittest.TestCase):
    def test_catalog_file_prefers_catalog_directory(self) -> None:
        self.assertEqual(CATALOG_DIR / "APIkeys_collection_catalog.json", catalog_file("APIkeys_collection_catalog.json"))

    def test_config_file_prefers_config_directory(self) -> None:
        self.assertEqual(CONFIG_DIR / "launcher_integrations.example.json", config_file("launcher_integrations.example.json"))

    def test_local_config_keeps_legacy_root_file_when_present(self) -> None:
        legacy = PROJECT_ROOT / "launcher_integrations.local.json"
        expected = legacy if legacy.exists() else CONFIG_DIR / "launcher_integrations.local.json"
        self.assertEqual(expected, local_config_file("launcher_integrations.local.json"))

    def test_state_file_keeps_legacy_sqlite_when_present(self) -> None:
        legacy = PROJECT_ROOT / "APIkeys_collection.sqlite"
        expected = legacy if legacy.exists() else PROJECT_ROOT / "state" / "APIkeys_collection.sqlite"
        self.assertEqual(expected, state_file("APIkeys_collection.sqlite"))


if __name__ == "__main__":
    unittest.main()
