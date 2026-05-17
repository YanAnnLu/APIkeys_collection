from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.integrations import AiSummaryProfile, _find_ai_profile, _generate_with_gemini, ai_summary_profiles_from_config


class AiSummaryGenerationTests(unittest.TestCase):
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
