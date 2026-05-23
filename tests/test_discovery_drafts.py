import json
import tempfile
import unittest
from pathlib import Path

from api_launcher.core import main
from api_launcher.crawlers.dataset_sources import load_dataset_discovery_sources
from api_launcher.discovery_drafts import dataset_source_from_provider_candidate
from api_launcher.discovery_drafts import write_provider_candidate_source_drafts


class DiscoveryDraftTests(unittest.TestCase):
    def test_explicit_supported_source_type_becomes_local_dataset_source(self) -> None:
        # 明確標出 crawler type 的候選可以直接變成本機草稿，但仍不代表正式 catalog 已通過審核。
        source = dataset_source_from_provider_candidate(
            {
                "provider_id": "example_data",
                "name": "Example Data",
                "categories": ["open_data", "ckan"],
                "geographic_scope": "global",
                "source_type": "ckan_package_search",
                "endpoint_url": "https://data.example.test/api/3/action/package_search",
                "docs_url": "https://data.example.test/docs",
                "search_terms": ["climate", "transport"],
            }
        )

        self.assertEqual("example_data_ckan_package_search", source.source_id)
        self.assertEqual("example_data", source.provider_id)
        self.assertEqual("ckan_package_search", source.source_type)
        self.assertEqual("https://data.example.test/api/3/action/package_search", source.endpoint_url)
        self.assertEqual(("climate", "transport"), source.search_terms)
        self.assertEqual(("open_data", "ckan"), source.categories)

    def test_stac_api_base_is_normalized_to_collections_endpoint(self) -> None:
        source = dataset_source_from_provider_candidate(
            {
                "provider_id": "planetary_computer",
                "name": "Planetary Computer",
                "categories": ["stac", "satellite"],
                "api_base_url": "https://planetarycomputer.microsoft.com/api/stac/v1",
            }
        )

        self.assertEqual("stac_collections", source.source_type)
        self.assertEqual("https://planetarycomputer.microsoft.com/api/stac/v1/collections", source.endpoint_url)
        self.assertEqual(("stac", "satellite"), source.search_terms)

    def test_unknown_shape_stays_in_review(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported dataset discovery source type"):
            dataset_source_from_provider_candidate(
                {
                    "provider_id": "landing_only",
                    "name": "Landing Only",
                    "source_url": "https://example.test/about",
                }
            )

    def test_missing_boundary_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider_id"):
            dataset_source_from_provider_candidate({"name": "No Provider", "endpoint_url": "https://api.example.test"})

    def test_batch_write_keeps_unknown_candidates_in_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "dataset_discovery_sources.local.json"

            summary = write_provider_candidate_source_drafts(provider_candidate_payload(), output_path)
            sources = load_dataset_discovery_sources(output_path)

        self.assertEqual(1, summary["source_draft_count"])
        self.assertEqual(1, summary["skipped_count"])
        self.assertEqual("run_local_discovery_audit_before_catalog_promotion", summary["next_action"])
        self.assertIn("--promote-local-discovery-catalog", summary["audit_command"])
        self.assertEqual(["sample_ckan_ckan_package_search"], summary["audit_source_ids"])
        self.assertEqual("sample_ckan_ckan_package_search", sources[0].source_id)
        self.assertIn("supported dataset discovery source type", summary["skipped"][0]["reason"])

    def test_cli_writes_provider_candidate_source_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "provider_candidates.review.json"
            local_sources_path = Path(tmpdir) / "dataset_discovery_sources.local.json"
            summary_path = Path(tmpdir) / "source_draft_summary.json"
            review_path.write_text(json.dumps(provider_candidate_payload(), ensure_ascii=False), encoding="utf-8")

            rc = main(
                [
                    "--db",
                    str(Path(tmpdir) / "launcher.sqlite"),
                    "--write-provider-candidate-source-drafts",
                    "--provider-candidate-source-drafts-input",
                    str(review_path),
                    "--provider-candidate-source-drafts-local",
                    str(local_sources_path),
                    "--write-provider-candidate-source-drafts-json",
                    str(summary_path),
                ]
            )
            sources = load_dataset_discovery_sources(local_sources_path)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(0, rc)
        self.assertEqual(1, len(sources))
        self.assertEqual(1, summary["source_draft_count"])
        self.assertEqual(1, summary["skipped_count"])
        self.assertEqual("run_local_discovery_audit_before_catalog_promotion", summary["next_action"])
        self.assertIn("--write-local-discovery-audit-json", summary["audit_command"])


def provider_candidate_payload() -> dict[str, object]:
    # 批次測試同時覆蓋可證明的 CKAN 來源，以及必須留在 review 的 landing page。
    return {
        "schema_version": 1,
        "candidates": [
            {
                "provider_id": "sample_ckan",
                "name": "Sample CKAN",
                "categories": ["open_data", "ckan"],
                "geographic_scope": "global",
                "source_type": "ckan_package_search",
                "endpoint_url": "https://data.example.test/api/3/action/package_search",
            },
            {
                "provider_id": "landing_only",
                "name": "Landing Only",
                "source_url": "https://example.test/about",
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
