from __future__ import annotations

import unittest

from api_launcher.adapters.gebco import GEBCOTopographyAdapter
from api_launcher.dataset_versions import DatasetVersionOption, sort_version_options, version_options_for_dataset
from api_launcher.models import Provider
from api_launcher.renderer_contracts import GEBCO_PROVIDER_ID


class DatasetVersionTests(unittest.TestCase):
    def test_metadata_versions_become_download_options(self) -> None:
        provider = Provider(
            provider_id=GEBCO_PROVIDER_ID,
            name="GEBCO",
            owner="General Bathymetric Chart of the Oceans",
            categories=("bathymetry",),
            geographic_scope="global",
            docs_url="https://www.gebco.net/data-products/gridded-bathymetry-data",
            auth_type="no_key_for_download_pages",
        )
        dataset = GEBCOTopographyAdapter().discover(provider)[0]

        options = version_options_for_dataset(dataset)

        self.assertEqual(["2026", "2025"], [option.version for option in options])
        self.assertEqual("latest_known", options[0].status)
        self.assertEqual("compatibility_pinned", options[1].status)
        self.assertEqual("compare_then_replace_or_keep_legacy", options[0].update_strategy)
        self.assertEqual("keep_legacy_for_renderer_compatibility", options[1].update_strategy)

    def test_version_sorting_is_generic_not_gebco_specific(self) -> None:
        options = sort_version_options(
            [
                DatasetVersionOption("uid", "dataset", "Legacy", "1.0", "legacy", "", ""),
                DatasetVersionOption("uid", "dataset", "Latest", "2.0", "latest", "", ""),
                DatasetVersionOption("uid", "dataset", "Pinned", "1.5", "compatibility_pinned", "", ""),
            ]
        )

        self.assertEqual(["latest", "compatibility_pinned", "legacy"], [option.status for option in options])
        self.assertTrue(options[0].is_latest)
        self.assertTrue(options[1].is_legacy)


if __name__ == "__main__":
    unittest.main()
