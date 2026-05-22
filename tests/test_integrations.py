# 這份測試保護本機 integration 偏好設定，避免 data-store active profile 寫到 Git-tracked example。
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.integrations import active_data_store_profile, set_active_data_store_profile


class IntegrationDataStoreProfileTests(unittest.TestCase):
    def test_active_data_store_profile_reads_configured_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "launcher_integrations.local.json"
            local_path.write_text(
                json.dumps(
                    {
                        "active_data_store_profile": "postgres_default",
                        "data_store_connection_profiles": [
                            {
                                "id": "mysql_default",
                                "label": "MySQL default",
                                "store_kind": "relational_sql",
                                "engine": "mysql",
                                "required_env_vars": ["MYSQL_HOST"],
                            },
                            {
                                "id": "postgres_default",
                                "label": "PostgreSQL default",
                                "store_kind": "relational_sql",
                                "engine": "postgresql",
                                "required_env_vars": ["PG_HOST"],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch("api_launcher.integrations.local_integrations_path", return_value=local_path):
                profile = active_data_store_profile()

        self.assertIsNotNone(profile)
        self.assertEqual("postgres_default", profile.profile_id)

    def test_set_active_data_store_profile_writes_ignored_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "launcher_integrations.local.json"
            example_path = Path(tmpdir) / "launcher_integrations.example.json"
            example_path.write_text(
                json.dumps(
                    {
                        "data_store_connection_profiles": [
                            {
                                "id": "mysql_default",
                                "label": "MySQL default",
                                "store_kind": "relational_sql",
                                "engine": "mysql",
                                "required_env_vars": ["MYSQL_HOST"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch("api_launcher.integrations.local_integrations_path", return_value=local_path):
                with patch("api_launcher.integrations.example_integrations_path", return_value=example_path):
                    profile = set_active_data_store_profile("mysql_default")
            saved = json.loads(local_path.read_text(encoding="utf-8"))

        self.assertEqual("mysql_default", profile.profile_id)
        self.assertEqual("mysql_default", saved["active_data_store_profile"])

    def test_cli_sets_active_data_store_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "launcher_integrations.local.json"
            example_path = Path(tmpdir) / "launcher_integrations.example.json"
            example_path.write_text(
                json.dumps(
                    {
                        "data_store_connection_profiles": [
                            {
                                "id": "sqlite_local",
                                "label": "SQLite local",
                                "store_kind": "embedded_sql",
                                "engine": "sqlite",
                                "required_env_vars": ["APIKEYS_SQLITE_PATH"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()

            with patch("api_launcher.integrations.local_integrations_path", return_value=local_path):
                with patch("api_launcher.integrations.example_integrations_path", return_value=example_path):
                    with redirect_stdout(output):
                        rc = main(
                            [
                                "--db",
                                str(Path(tmpdir) / "launcher.sqlite"),
                                "--set-active-data-store-profile",
                                "sqlite_local",
                            ]
                        )
            saved = json.loads(local_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual("sqlite_local", saved["active_data_store_profile"])
        self.assertIn("active_profile=sqlite_local", output.getvalue())


if __name__ == "__main__":
    unittest.main()
