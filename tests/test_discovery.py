# 這份測試鎖定 provider discovery parser，避免來源候選與官方 provider 混淆。
from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_launcher.discovery import (
    DEFAULT_PROVIDER_DISCOVERY_FETCH_MAX_BYTES,
    ProviderSeed,
    append_discovery_seed,
    auth_type_requires_secret,
    dedupe_key,
    discover_provider_candidates,
    fetch_text,
    infer_auth_type,
    key_env_var,
    load_all_discovery_seeds,
    load_discovery_seeds,
)
from api_launcher.models import Provider
from api_launcher.cli_discovery import add_discovery_args


class DiscoveryTests(unittest.TestCase):
    def test_seed_loader_keeps_provider_source_metadata_outside_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "seeds.json"
            path.write_text(
                """
                {
                  "schema_version": 1,
                  "seeds": [
                    {
                      "provider_id": "sample",
                      "name": "Sample",
                      "owner": "Owner",
                      "categories": ["weather"],
                      "geographic_scope": "global",
                      "homepage_url": "https://example.test",
                      "expected_auth_type": "no_key_for_public_data"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            seeds = load_discovery_seeds(path)

        self.assertEqual("sample", seeds[0].provider_id)
        self.assertEqual(("weather",), seeds[0].categories)

    def test_provider_discovery_cli_exposes_fetch_byte_budget(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--timeout", type=float, default=12.0)
        add_discovery_args(parser)

        defaults = parser.parse_args([])
        custom = parser.parse_args(["--provider-discovery-max-bytes", "321"])

        self.assertEqual(DEFAULT_PROVIDER_DISCOVERY_FETCH_MAX_BYTES, defaults.provider_discovery_max_bytes)
        self.assertEqual(321, custom.provider_discovery_max_bytes)

    def test_auth_inference_never_returns_secret_values(self) -> None:
        auth_type, evidence = infer_auth_type("Use your API key in the key parameter.", "unknown")

        self.assertEqual("api_key_required", auth_type)
        self.assertIn("mentions", evidence)

    def test_seed_expected_auth_type_takes_precedence_over_page_noise(self) -> None:
        auth_type, evidence = infer_auth_type("This page links to key figures and OAuth examples.", "no_key_for_public_data")

        self.assertEqual("no_key_for_public_data", auth_type)
        self.assertEqual("seed expected auth type", evidence)

    def test_no_key_auth_type_does_not_require_secret_env_var(self) -> None:
        self.assertFalse(auth_type_requires_secret("no_key_for_public_data"))
        self.assertFalse(auth_type_requires_secret("account_or_email_required"))
        self.assertTrue(auth_type_requires_secret("api_key_required"))

    def test_env_var_and_dedupe_key_are_stable(self) -> None:
        first = Provider(
            provider_id="sample",
            name="Sample",
            owner="Owner",
            categories=("test",),
            geographic_scope="global",
            docs_url="https://EXAMPLE.test/api/",
            api_base_url="https://EXAMPLE.test/api/",
        )
        second = Provider(
            provider_id="sample_mirror",
            name="Sample Mirror",
            owner="Owner",
            categories=("test",),
            geographic_scope="global",
            docs_url="https://example.test/api",
            api_base_url="https://example.test/api",
        )

        self.assertEqual("US_CENSUS_API_KEY", key_env_var("us_census"))
        self.assertEqual(dedupe_key(first), dedupe_key(second))

    def test_discovery_skips_existing_provider_ids(self) -> None:
        seed = ProviderSeed(
            provider_id="already_known",
            name="Known",
            owner="Owner",
            categories=("test",),
            geographic_scope="global",
            homepage_url="https://example.test",
            docs_url="https://example.test",
            api_base_url="https://example.test/api",
            expected_auth_type="no_key_for_public_data",
        )

        candidates = discover_provider_candidates([seed], existing_provider_ids={"already_known"})

        self.assertEqual([], candidates)

    def test_fetch_text_uses_named_bounded_read(self) -> None:
        read_sizes: list[int] = []

        class FakeHeaders:
            def get_content_charset(self) -> str:
                return "utf-8"

        class FakeResponse:
            headers = FakeHeaders()

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                read_sizes.append(size)
                return b"<html>ok</html>"

            def geturl(self) -> str:
                return "https://example.test/final"

        with patch("api_launcher.discovery.urllib.request.urlopen", return_value=FakeResponse()):
            text, final_url = fetch_text("https://example.test", timeout=1.0, max_bytes=17)

        self.assertEqual("<html>ok</html>", text)
        self.assertEqual("https://example.test/final", final_url)
        self.assertEqual([18], read_sizes)
        self.assertEqual(120_000, DEFAULT_PROVIDER_DISCOVERY_FETCH_MAX_BYTES)

    def test_fetch_text_rejects_oversized_response(self) -> None:
        class FakeHeaders:
            def get_content_charset(self) -> str:
                return "utf-8"

        class FakeResponse:
            headers = FakeHeaders()

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                return b"x" * size

            def geturl(self) -> str:
                return "https://example.test/final"

        with patch("api_launcher.discovery.urllib.request.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(ValueError, "exceeded 3 bytes"):
                fetch_text("https://example.test", timeout=1.0, max_bytes=3)

    def test_local_source_site_seed_can_be_added_without_touching_builtin_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            primary = Path(tmpdir) / "primary.json"
            local = Path(tmpdir) / "local.json"
            primary.write_text('{"schema_version": 1, "seeds": []}', encoding="utf-8")
            append_discovery_seed(
                local,
                ProviderSeed(
                    provider_id="taiwan_open_data",
                    name="Taiwan Open Data",
                    owner="Taiwan government",
                    categories=("open_data", "taiwan"),
                    geographic_scope="taiwan",
                    homepage_url="https://data.gov.tw/",
                    expected_auth_type="no_key_for_public_data",
                ),
            )

            seeds = load_all_discovery_seeds(primary, local)

        self.assertEqual(1, len(seeds))
        self.assertEqual("taiwan_open_data", seeds[0].provider_id)


if __name__ == "__main__":
    unittest.main()
