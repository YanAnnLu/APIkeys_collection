# 這份測試鎖定啟動環境檢查，避免跨平台路徑或本機狀態阻斷 launcher。
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.environment import check_path, check_unreal_profile_path, run_startup_checks
from api_launcher.platform_paths import is_foreign_platform_path, normalize_path_for_platform, platform_config_path


class EnvironmentCheckTests(unittest.TestCase):
    def test_check_path_reports_missing_path(self) -> None:
        missing = Path(tempfile.gettempdir()) / "apikeys_collection_missing_path_for_test"
        check = check_path("missing", missing, must_exist=True, must_be_writable=False)
        self.assertEqual(check.status, "error")
        self.assertIn("Missing path", check.detail)

    def test_startup_checks_return_named_results(self) -> None:
        checks = run_startup_checks()
        names = {check.name for check in checks}
        self.assertIn("project_root", names)
        self.assertIn("database_parent", names)
        self.assertIn("integration_config", names)
        self.assertIn("python_encoding", names)

    def test_windows_unreal_path_is_foreign_on_macos(self) -> None:
        self.assertTrue(is_foreign_platform_path(r"K:\UnrealProjects\Twin\Twin.uproject", "Darwin"))
        self.assertFalse(is_foreign_platform_path(r"K:\UnrealProjects\Twin\Twin.uproject", "Windows"))

    def test_foreign_unreal_path_is_warning_not_error(self) -> None:
        check = check_unreal_profile_path(
            "unreal_project:local",
            r"K:\UnrealProjects\Twin\Twin.uproject",
            "Darwin",
            must_be_writable=False,
        )

        self.assertEqual("warning", check.status)
        self.assertIn("another platform", check.detail)

    def test_platform_config_path_picks_current_system_and_normalizes_slashes(self) -> None:
        item = {
            "project_path": r"K:\UnrealProjects\Twin\Twin.uproject",
            "project_path_by_platform": {
                "Darwin": r"/Users/example/UnrealProjects/Twin/Twin.uproject",
            },
        }

        self.assertEqual(
            "/Users/example/UnrealProjects/Twin/Twin.uproject",
            platform_config_path(item, "project_path", "Darwin"),
        )
        self.assertEqual("", platform_config_path(item, "project_path", "Linux"))
        self.assertEqual("relative/path", normalize_path_for_platform(r"relative\path", "Darwin"))


if __name__ == "__main__":
    unittest.main()
