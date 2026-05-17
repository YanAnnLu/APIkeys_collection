from __future__ import annotations

import unittest

from api_launcher.data_store_connections import (
    DEFAULT_DATA_STORE_PROFILES,
    data_store_profile,
    data_store_profiles_by_kind,
)


class DataStoreConnectionTests(unittest.TestCase):
    def test_profiles_cover_relational_and_non_relational_stores(self) -> None:
        kinds = {profile.store_kind for profile in DEFAULT_DATA_STORE_PROFILES}

        self.assertIn("relational_sql", kinds)
        self.assertIn("document_nosql", kinds)
        self.assertIn("object_storage", kinds)
        self.assertIn("vector_database", kinds)

    def test_mongodb_profile_uses_uri_env(self) -> None:
        profile = data_store_profile("mongodb_default")

        self.assertIsNotNone(profile)
        self.assertEqual(("APIKEYS_MONGODB_URI",), profile.required_env_vars)

    def test_mysql_profile_keeps_sql_credentials_in_env_contract(self) -> None:
        profile = data_store_profile("mysql_default")

        self.assertIsNotNone(profile)
        self.assertEqual("relational_sql", profile.store_kind)
        self.assertIn("APIKEYS_MYSQL_PASSWORD", profile.required_env_vars)
        self.assertIn("APIKEYS_MYSQL_PORT", profile.optional_env_vars)

    def test_profiles_can_be_filtered_by_kind(self) -> None:
        profiles = data_store_profiles_by_kind("relational_sql")

        self.assertTrue(all(profile.store_kind == "relational_sql" for profile in profiles))


if __name__ == "__main__":
    unittest.main()
