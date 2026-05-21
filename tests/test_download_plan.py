# 這份測試鎖定 provider-level download plan，避免舊 schema 與新 runner 不相容。
from __future__ import annotations

import unittest

from api_launcher.models import Provider
from api_launcher.plans import build_download_plan


class DownloadPlanTests(unittest.TestCase):
    def test_build_download_plan_uses_shared_schema(self) -> None:
        provider = Provider(
            provider_id="sample_provider",
            name="Sample Provider",
            owner="Sample Owner",
            categories=("test",),
            geographic_scope="global",
            docs_url="https://example.test/docs",
            auth_type="api_key_required",
            key_env_var="SAMPLE_KEY",
        )

        plan = build_download_plan([provider], plan_name="Test Plan")

        self.assertEqual(1, plan["schema_version"])
        self.assertEqual("Test Plan", plan["plan_name"])
        self.assertEqual({"provider_count": 1, "status": "planned"}, plan["summary"])
        self.assertEqual("nonblocking", plan["download_policy"]["io_model"])
        self.assertTrue(plan["download_policy"]["supports_pause"])
        self.assertTrue(plan["download_policy"]["supports_resume"])
        self.assertEqual("sample_provider", plan["providers"][0]["provider_id"])
        self.assertEqual("planned", plan["providers"][0]["plan_status"])
        self.assertEqual("local_dataset_or_database", plan["providers"][0]["target"])
        self.assertEqual("metadata_only", plan["providers"][0]["download_eligibility"]["status"])


if __name__ == "__main__":
    unittest.main()
