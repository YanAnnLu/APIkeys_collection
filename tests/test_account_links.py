# 這份測試鎖定帳號/AI 能力路由，避免 UI 把尚未完成的登入流程當 MVP。
from __future__ import annotations

import unittest

from api_launcher.account_links import (
    DEFAULT_ACCOUNT_PROVIDERS,
    account_auth_mode_label,
    account_provider,
    account_status_label,
    capability_route,
)


class AccountLinkTests(unittest.TestCase):
    def test_google_is_primary_gemini_account_provider(self) -> None:
        google = account_provider("google")

        self.assertIsNotNone(google)
        self.assertIn("gemini_summary", google.capability_targets)
        self.assertEqual("oauth_device_qr", google.auth_mode)

    def test_apple_is_reserved_without_gemini_claim(self) -> None:
        apple = account_provider("apple")

        self.assertIsNotNone(apple)
        self.assertEqual("reserved", apple.status)
        self.assertNotIn("gemini_summary", apple.capability_targets)

    def test_ai_summary_routes_to_google_with_local_fallback(self) -> None:
        route = capability_route("ai_dataset_summary")

        self.assertIsNotNone(route)
        self.assertEqual("google", route.preferred_provider)
        self.assertIn("local_ollama", route.fallback_providers)

    def test_reserved_providers_exist_for_future_expansion(self) -> None:
        provider_ids = {provider.provider_id for provider in DEFAULT_ACCOUNT_PROVIDERS}

        self.assertIn("apple", provider_ids)
        self.assertIn("microsoft", provider_ids)
        self.assertIn("github", provider_ids)

    def test_account_provider_display_labels_hide_raw_status_ids(self) -> None:
        self.assertEqual("掃碼 / 裝置碼登入", account_auth_mode_label("oauth_device_qr"))
        self.assertEqual("規劃中", account_status_label("planned"))
        self.assertEqual("🚧 施工中", account_status_label("skeleton"))


if __name__ == "__main__":
    unittest.main()
