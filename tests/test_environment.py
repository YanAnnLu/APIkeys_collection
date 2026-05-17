from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.environment import check_path, run_startup_checks


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


if __name__ == "__main__":
    unittest.main()
