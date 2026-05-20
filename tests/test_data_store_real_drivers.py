from __future__ import annotations

import os
import unittest

from api_launcher.data_store_connections import data_store_profile, test_data_store_connection


REAL_DB_SMOKE_FLAG = "APIKEYS_RUN_REAL_DB_SMOKE"


class RealDataStoreDriverSmokeTests(unittest.TestCase):
    def test_mysql_real_driver_smoke_when_enabled(self) -> None:
        env = _real_db_env_or_skip(
            self,
            (
                REAL_DB_SMOKE_FLAG,
                "APIKEYS_MYSQL_HOST",
                "APIKEYS_MYSQL_DATABASE",
                "APIKEYS_MYSQL_USER",
                "APIKEYS_MYSQL_PASSWORD",
            ),
        )
        profile = data_store_profile("mysql_default")
        self.assertIsNotNone(profile)

        result = test_data_store_connection(profile, env, include_schema_summary=True)

        if result.status == "dependency_missing":
            self.skipTest(result.message)
        self.assertEqual("ok", result.status, result.message)
        self.assertEqual(env["APIKEYS_MYSQL_DATABASE"], result.details["database"])
        self.assertIsInstance(result.details["table_count"], int)
        self.assertEqual(64, len(str(result.details["schema_fingerprint"])))

    def test_postgresql_real_driver_smoke_when_enabled(self) -> None:
        env = _real_db_env_or_skip(
            self,
            (
                REAL_DB_SMOKE_FLAG,
                "APIKEYS_POSTGRES_HOST",
                "APIKEYS_POSTGRES_DATABASE",
                "APIKEYS_POSTGRES_USER",
                "APIKEYS_POSTGRES_PASSWORD",
            ),
        )
        profile = data_store_profile("postgres_default")
        self.assertIsNotNone(profile)
        schema_name = str(env.get("APIKEYS_POSTGRES_SCHEMA") or "public").strip() or "public"

        result = test_data_store_connection(
            profile,
            env,
            include_schema_summary=True,
            schema_name=schema_name,
        )

        if result.status == "dependency_missing":
            self.skipTest(result.message)
        self.assertEqual("ok", result.status, result.message)
        self.assertEqual(env["APIKEYS_POSTGRES_DATABASE"], result.details["database"])
        self.assertEqual(schema_name, result.details["schema"])
        self.assertIsInstance(result.details["table_count"], int)
        self.assertEqual(64, len(str(result.details["schema_fingerprint"])))


def _real_db_env_or_skip(test_case: unittest.TestCase, required_names: tuple[str, ...]) -> dict[str, str]:
    env = {name: str(os.environ.get(name) or "").strip() for name in required_names}
    if env.get(REAL_DB_SMOKE_FLAG) != "1":
        test_case.skipTest(f"Set {REAL_DB_SMOKE_FLAG}=1 to run real database driver smoke tests.")
    missing = tuple(name for name, value in env.items() if not value)
    if missing:
        test_case.skipTest(f"Missing real database smoke env vars: {', '.join(missing)}")
    return dict(os.environ)


if __name__ == "__main__":
    unittest.main()
