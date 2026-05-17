from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from api_launcher.integrations import AiSummaryProfile, ai_summary_profiles_from_config
from api_launcher.oauth_device import (
    OAuthDeviceConfig,
    activate_saved_oauth_token,
    build_oauth_device_login_request,
    oauth_device_config_from_profile,
    oauth_token_status,
    poll_oauth_device_token,
    save_oauth_device_token,
)


class OAuthDeviceTests(unittest.TestCase):
    def profile(self, token_store: str = "state/private/ai_oauth_tokens/test.json") -> AiSummaryProfile:
        return AiSummaryProfile(
            id="test_ai",
            label="Test AI",
            kind="openai_compatible",
            enabled=True,
            model="test-model",
            endpoint="https://example.test/v1/chat/completions",
            api_key_env="TEST_AI_API_KEY",
            oauth_token_env="TEST_AI_OAUTH_ACCESS_TOKEN",
            token_store=token_store,
            oauth_device={
                "enabled": True,
                "provider": "test",
                "client_id_env": "TEST_AI_CLIENT_ID",
                "client_secret_env": "TEST_AI_CLIENT_SECRET",
                "device_code_url": "https://example.test/device/code",
                "token_url": "https://example.test/token",
                "verification_url": "https://example.test/device",
                "scopes": ["summary"],
                "token_env": "TEST_AI_OAUTH_ACCESS_TOKEN",
                "token_store": token_store,
            },
        )

    def test_profile_can_carry_oauth_device_config(self) -> None:
        profiles = ai_summary_profiles_from_config(
            {
                "ai_summary_profiles": [
                    {
                        "id": "test_ai",
                        "label": "Test AI",
                        "kind": "openai_compatible",
                        "enabled": True,
                        "model": "test-model",
                        "endpoint": "https://example.test/v1/chat/completions",
                        "api_key_env": "TEST_AI_API_KEY",
                        "oauth_device": {
                            "provider": "test",
                            "client_id_env": "TEST_AI_CLIENT_ID",
                            "device_code_url": "https://example.test/device/code",
                            "token_url": "https://example.test/token",
                            "token_env": "TEST_AI_OAUTH_ACCESS_TOKEN",
                        },
                    }
                ]
            }
        )

        self.assertEqual("TEST_AI_OAUTH_ACCESS_TOKEN", profiles[0].oauth_token_env)
        self.assertEqual("TEST_AI_CLIENT_ID", profiles[0].oauth_device["client_id_env"])

    def test_known_profile_gets_default_qr_config_when_local_config_is_old(self) -> None:
        profile = AiSummaryProfile(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            enabled=True,
            model="gemini",
            endpoint="https://example.test",
            api_key_env="GEMINI_API_KEY",
        )

        config = oauth_device_config_from_profile(profile)

        self.assertIsNotNone(config)
        self.assertEqual("GOOGLE_OAUTH_CLIENT_ID", config.client_id_env)
        self.assertEqual("GOOGLE_OAUTH_ACCESS_TOKEN", config.token_env)

    def test_device_request_uses_profile_config(self) -> None:
        config = oauth_device_config_from_profile(self.profile())
        self.assertIsInstance(config, OAuthDeviceConfig)
        response = {
            "device_code": "device-code",
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://example.test/device",
            "expires_in": 1800,
            "interval": 5,
        }
        with patch.dict(os.environ, {"TEST_AI_CLIENT_ID": "client-id"}), patch(
            "api_launcher.oauth_device._post_form", return_value=response
        ) as post_form:
            request = build_oauth_device_login_request(config)

        self.assertEqual("authorization_pending", request.status)
        self.assertEqual("test_ai", request.profile_id)
        self.assertEqual("ABCD-EFGH", request.user_code)
        self.assertEqual("client-id", post_form.call_args.args[1]["client_id"])

    def test_poll_and_save_token_can_activate_profile_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.profile(token_store=os.path.join(tmp, "token.json"))
            config = oauth_device_config_from_profile(profile)
            with patch.dict(os.environ, {"TEST_AI_CLIENT_ID": "client-id"}, clear=True), patch(
                "api_launcher.oauth_device._post_form",
                side_effect=[
                    {
                        "device_code": "device-code",
                        "user_code": "ABCD-EFGH",
                        "verification_uri": "https://example.test/device",
                        "expires_in": 1800,
                        "interval": 5,
                    },
                    {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600, "token_type": "Bearer"},
                ],
            ):
                request = build_oauth_device_login_request(config)
                result = poll_oauth_device_token(request)

            self.assertEqual("success", result.status)
            save_oauth_device_token(result, request)
            status, _message = oauth_token_status(config.token_store, label=profile.label)
            self.assertEqual("ready", status)

            with patch.dict(os.environ, {}, clear=True):
                activate_saved_oauth_token(config.token_store, config.token_env, label=profile.label)
                self.assertEqual("access", os.environ["TEST_AI_OAUTH_ACCESS_TOKEN"])


if __name__ == "__main__":
    unittest.main()
