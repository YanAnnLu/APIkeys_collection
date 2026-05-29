# 這份測試鎖定 AI summary 產生流程，避免 profile/key 邊界與輸出寫回回歸。
from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.ai_api_keys import load_saved_ai_api_keys, save_ai_api_key
from api_launcher.integrations import (
    DEFAULT_AI_SUMMARY_RESPONSE_MAX_BYTES,
    AiSummaryProfile,
    _find_ai_profile,
    _generate_with_gemini,
    _generate_with_openai_compatible,
    _post_json,
    ai_summary_profiles_from_config,
    generate_provider_summary,
)
from api_launcher.models import Provider


class AiSummaryGenerationTests(unittest.TestCase):
    def test_post_json_uses_named_bounded_read(self) -> None:
        read_sizes: list[int] = []

        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                read_sizes.append(size)
                return b'{"ok": true}'

        with patch("api_launcher.integrations.request.urlopen", return_value=FakeResponse()):
            payload = _post_json("https://example.test/summary", {"prompt": "x"}, None, timeout=1.0, max_bytes=41)

        self.assertEqual({"ok": True}, payload)
        self.assertEqual([42], read_sizes)
        self.assertEqual(2 * 1024 * 1024, DEFAULT_AI_SUMMARY_RESPONSE_MAX_BYTES)

    def test_post_json_rejects_oversized_response(self) -> None:
        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                return b"x" * size

        with patch("api_launcher.integrations.request.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(ValueError, "exceeded 3 bytes"):
                _post_json("https://example.test/summary", {"prompt": "x"}, None, timeout=1.0, max_bytes=3)

    def test_gemini_generation_extracts_candidate_text(self) -> None:
        profile = AiSummaryProfile(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            enabled=True,
            model="gemini-test",
            endpoint="https://example.test/{model}:generateContent",
            api_key_env="GEMINI_API_KEY",
        )
        response = {"candidates": [{"content": {"parts": [{"text": "資料庫描述"}]}}]}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch(
            "api_launcher.integrations._post_json", return_value=response
        ) as post_json:
            text = _generate_with_gemini(profile, "prompt", timeout=3.0)

        self.assertEqual("資料庫描述", text)
        self.assertIn("x-goog-api-key", post_json.call_args.kwargs["headers"])

    def test_gemini_generation_can_use_oauth_token(self) -> None:
        profile = AiSummaryProfile(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            enabled=True,
            model="gemini-test",
            endpoint="https://example.test/{model}:generateContent",
            api_key_env="GEMINI_API_KEY",
        )
        response = {"candidates": [{"content": {"parts": [{"text": "OAuth 描述"}]}}]}
        with patch.dict(os.environ, {"GOOGLE_OAUTH_ACCESS_TOKEN": "access-token"}, clear=True), patch(
            "api_launcher.integrations._post_json", return_value=response
        ) as post_json:
            text = _generate_with_gemini(profile, "prompt", timeout=3.0)

        self.assertEqual("OAuth 描述", text)
        self.assertEqual("Bearer access-token", post_json.call_args.kwargs["headers"]["Authorization"])

    def test_saved_ai_api_key_loads_into_environment(self) -> None:
        profile = AiSummaryProfile(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            enabled=True,
            model="gemini-test",
            endpoint="https://example.test/{model}:generateContent",
            api_key_env="GEMINI_API_KEY",
        )
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            store = Path(tmp) / "ai_api_keys.private.json"
            save_ai_api_key(profile, "saved-key", store=store)
            loaded = load_saved_ai_api_keys([profile], store=store)
            self.assertEqual("saved-key", os.environ["GEMINI_API_KEY"])

        self.assertEqual(["Gemini Flash"], loaded)

    def test_generate_provider_summary_loads_saved_ai_key(self) -> None:
        profile = AiSummaryProfile(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            enabled=True,
            model="gemini-test",
            endpoint="https://example.test/{model}:generateContent",
            api_key_env="GEMINI_API_KEY",
        )
        provider = Provider(
            provider_id="gebco",
            name="GEBCO",
            owner="GEBCO",
            categories=("bathymetry",),
            geographic_scope="global",
            docs_url="https://example.test",
            api_base_url="",
            signup_url="",
            auth_type="none",
            key_env_var="",
            notes="",
        )
        response = {"candidates": [{"content": {"parts": [{"text": "saved key 描述"}]}}]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True), patch(
            "api_launcher.ai_api_keys.DEFAULT_AI_API_KEY_STORE", str(Path(tmp) / "ai_api_keys.private.json")
        ), patch("api_launcher.integrations.ai_summary_profiles", return_value=[profile]), patch(
            "api_launcher.integrations._post_json", return_value=response
        ) as post_json:
            save_ai_api_key(profile, "saved-key")
            text = generate_provider_summary(provider, profile_id="gemini_flash", timeout=3.0)

        self.assertEqual("saved key 描述", text)
        self.assertEqual("saved-key", post_json.call_args.kwargs["headers"]["x-goog-api-key"])

    def test_ai_profiles_can_load_gemini_config(self) -> None:
        profiles = ai_summary_profiles_from_config(
            {
                "ai_summary_profiles": [
                    {
                        "id": "gemini_flash",
                        "label": "Gemini Flash",
                        "kind": "gemini",
                        "enabled": True,
                        "model": "gemini-2.0-flash",
                        "endpoint": "https://example.test/{model}",
                        "api_key_env": "GEMINI_API_KEY",
                    }
                ]
            }
        )

        self.assertEqual("gemini_flash", profiles[0].id)
        self.assertEqual("GEMINI_API_KEY", profiles[0].api_key_env)

    def test_openai_compatible_generation_extracts_message(self) -> None:
        profile = AiSummaryProfile(
            id="openai_compatible",
            label="OpenAI Compatible",
            kind="openai_compatible",
            enabled=True,
            model="test-model",
            endpoint="https://example.test/v1/chat/completions",
            api_key_env="OPENAI_API_KEY",
        )
        response = {"choices": [{"message": {"content": "OpenAI-compatible 描述"}}]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "api_launcher.integrations._post_json", return_value=response
        ) as post_json:
            text = _generate_with_openai_compatible(profile, "prompt", timeout=3.0)

        self.assertEqual("OpenAI-compatible 描述", text)
        self.assertEqual("Bearer test-key", post_json.call_args.kwargs["headers"]["Authorization"])

    def test_openai_compatible_generation_can_use_oauth_token(self) -> None:
        profile = AiSummaryProfile(
            id="openai_compatible",
            label="OpenAI Compatible",
            kind="openai_compatible",
            enabled=True,
            model="test-model",
            endpoint="https://example.test/v1/chat/completions",
            api_key_env="OPENAI_API_KEY",
            oauth_token_env="OPENAI_COMPATIBLE_OAUTH_TOKEN",
        )
        response = {"choices": [{"message": {"content": "OAuth OpenAI-compatible 描述"}}]}
        with patch.dict(os.environ, {"OPENAI_COMPATIBLE_OAUTH_TOKEN": "oauth-token"}, clear=True), patch(
            "api_launcher.integrations._post_json", return_value=response
        ) as post_json:
            text = _generate_with_openai_compatible(profile, "prompt", timeout=3.0)

        self.assertEqual("OAuth OpenAI-compatible 描述", text)
        self.assertEqual("Bearer oauth-token", post_json.call_args.kwargs["headers"]["Authorization"])

    def test_openai_compatible_generation_uses_default_profile_oauth_env(self) -> None:
        profile = AiSummaryProfile(
            id="openai_compatible",
            label="OpenAI Compatible",
            kind="openai_compatible",
            enabled=True,
            model="test-model",
            endpoint="https://example.test/v1/chat/completions",
            api_key_env="OPENAI_API_KEY",
        )
        response = {"choices": [{"message": {"content": "Default OAuth env 描述"}}]}
        with patch.dict(os.environ, {"AI_OAUTH_ACCESS_TOKEN_OPENAI_COMPATIBLE": "oauth-token"}, clear=True), patch(
            "api_launcher.integrations._post_json", return_value=response
        ) as post_json:
            text = _generate_with_openai_compatible(profile, "prompt", timeout=3.0)

        self.assertEqual("Default OAuth env 描述", text)
        self.assertEqual("Bearer oauth-token", post_json.call_args.kwargs["headers"]["Authorization"])

    def test_explicit_ai_profile_can_be_disabled_in_config(self) -> None:
        profile = AiSummaryProfile(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            enabled=False,
            model="gemini",
            endpoint="https://example.test",
        )
        with patch("api_launcher.integrations.ai_summary_profiles", return_value=[profile]):
            selected = _find_ai_profile("gemini_flash")

        self.assertEqual("gemini_flash", selected.id)

    def test_cli_generate_ai_summary_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch("api_launcher.core.generate_provider_summary", return_value="AI generated description"):
                with redirect_stdout(output):
                    rc = main(
                        [
                            "--db",
                            str(Path(tmp) / "test.sqlite"),
                            "--init-db",
                            "--seed",
                            "--generate-ai-summary",
                            "gebco",
                            "--ai-profile",
                            "gemini_flash",
                        ]
                    )

        self.assertEqual(0, rc)
        self.assertIn("[ai-summary] provider=gebco", output.getvalue())
        self.assertIn("AI generated description", output.getvalue())


if __name__ == "__main__":
    unittest.main()
