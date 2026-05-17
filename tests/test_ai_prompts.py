from __future__ import annotations

import unittest

from api_launcher.ai_prompts import DATASET_DESCRIPTION_PROMPT, provider_description_prompt
from api_launcher.models import Provider


class AiPromptTests(unittest.TestCase):
    def test_dataset_description_prompt_declares_output_contract(self) -> None:
        self.assertEqual("dataset_launcher_description_v1", DATASET_DESCRIPTION_PROMPT.prompt_id)
        self.assertTrue(any("Traditional Chinese" in rule for rule in DATASET_DESCRIPTION_PROMPT.output_contract))
        self.assertTrue(any("Do not invent" in rule for rule in DATASET_DESCRIPTION_PROMPT.output_contract))

    def test_provider_description_prompt_includes_source_metadata(self) -> None:
        provider = Provider(
            provider_id="sample",
            name="Sample Data API",
            owner="Example Org",
            categories=("ocean", "weather"),
            geographic_scope="global",
            docs_url="https://example.test/docs",
            api_base_url="https://example.test/api",
            auth_type="api_key_required",
            key_env_var="SAMPLE_API_KEY",
        )

        prompt = provider_description_prompt(provider)

        self.assertIn("Sample Data API", prompt)
        self.assertIn("SAMPLE_API_KEY", prompt)
        self.assertIn("virtual-twin", prompt)
        self.assertIn("Output contract", prompt)


if __name__ == "__main__":
    unittest.main()
