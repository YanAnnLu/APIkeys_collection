from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.db import connect_db
from api_launcher.handoff import build_handoff_snapshot, render_handoff_markdown
from api_launcher.repository import ApiCatalogRepository


class HandoffTests(unittest.TestCase):
    def test_handoff_report_contains_git_catalog_and_resume_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect_db(Path(tmpdir) / "test.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()

                report = render_handoff_markdown(build_handoff_snapshot(repo))
            finally:
                conn.close()

        self.assertIn("# APIkeys_collection Handoff", report)
        self.assertIn("providers:", report)
        self.assertIn("py -m unittest discover -s tests", report)


if __name__ == "__main__":
    unittest.main()
