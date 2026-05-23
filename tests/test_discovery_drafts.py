import unittest

from api_launcher.discovery_drafts import dataset_source_from_provider_candidate


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


if __name__ == "__main__":
    unittest.main()
