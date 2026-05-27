from contextlib import redirect_stdout
from io import StringIO
import json
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from api_launcher.cli_crawler_assets import (
    crawler_asset_command_active,
    crawler_asset_seed_page_cli_result,
    run_crawler_asset_cli,
)
from api_launcher.crawler_asset_profiles import load_crawler_asset_profiles
from api_launcher.crawler_seed_registry import (
    MAX_CRAWLER_SEED_PAGE_SIZE,
    crawler_seed_belongs_to_asset,
    crawler_seed_favorite_key,
    crawler_seed_page,
    crawler_seed_page_summary,
    crawler_seed_row,
    normalize_crawler_seed_page,
    save_crawler_seed_favorite,
)
from api_launcher.models import Dataset


class FakeSeedRepository:
    def __init__(self, datasets: list[Dataset]) -> None:
        self.datasets = datasets
        self.calls: list[tuple[str | None, str | None]] = []

    def list_dataset_candidates(
        self,
        status: str | None = "needs_review",
        provider_id: str | None = None,
    ) -> list[Dataset]:
        self.calls.append((status, provider_id))
        return [dataset for dataset in self.datasets if dataset.provider_id == provider_id]


def seed_dataset(
    uid: str,
    *,
    provider_id: str = "demo_provider",
    source_id: str = "demo_asset",
    title: str | None = None,
) -> Dataset:
    index = uid.rsplit("_", 1)[-1]
    return Dataset(
        dataset_uid=f"{provider_id}:{uid}",
        provider_id=provider_id,
        dataset_id=uid,
        title=title or f"Seed {index}",
        categories=("demo",),
        native_format="csv",
        data_type="tabular",
        version="v1",
        landing_url=f"https://example.test/{uid}",
        api_url=f"https://example.test/api/{uid}",
        metadata={
            "candidate_status": "needs_review",
            "discovery_source_id": source_id,
            "discovery_source_type": "stac_collections",
            "data_family": "catalog",
        },
    )


class CrawlerSeedRegistryTests(unittest.TestCase):
    def test_seed_page_filters_by_asset_and_caps_page_size(self) -> None:
        datasets = [seed_dataset(f"seed_{index:02d}") for index in range(55)]
        datasets.append(seed_dataset("other_seed", source_id="other_asset", title="Other"))
        repo = FakeSeedRepository(datasets)

        page = crawler_seed_page(
            repo,
            asset_id="demo_asset",
            provider_id="demo_provider",
            page=1,
            page_size=999,
            favorite_seed_uids={"demo_provider:seed_00"},
        )

        self.assertEqual([("all", "demo_provider")], repo.calls)
        self.assertEqual(MAX_CRAWLER_SEED_PAGE_SIZE, page["page_size"])
        self.assertEqual(55, page["total"])
        self.assertEqual(MAX_CRAWLER_SEED_PAGE_SIZE, len(page["seeds"]))
        self.assertTrue(page["has_more"])
        self.assertEqual(1, page["page_summary"]["shown_start"])
        self.assertEqual(50, page["page_summary"]["shown_end"])
        self.assertEqual(5, page["page_summary"]["remaining"])
        self.assertEqual(2, page["page_summary"]["page_count"])
        self.assertEqual(2, page["page_summary"]["next_page"])
        self.assertEqual("show_next_seed_page", page["page_summary"]["next_action"])
        self.assertEqual(1, page["favorite_seed_count"])
        self.assertEqual("seed_00", page["seeds"][0]["dataset_id"])
        self.assertTrue(page["seeds"][0]["favorite"])

    def test_seed_page_returns_later_window_without_refetch_semantics(self) -> None:
        repo = FakeSeedRepository([seed_dataset(f"seed_{index:02d}") for index in range(55)])

        page = crawler_seed_page(repo, asset_id="demo_asset", provider_id="demo_provider", page=2, page_size=50)

        self.assertEqual(2, page["page"])
        self.assertEqual(5, len(page["seeds"]))
        self.assertFalse(page["has_more"])
        self.assertEqual(51, page["page_summary"]["shown_start"])
        self.assertEqual(55, page["page_summary"]["shown_end"])
        self.assertEqual(0, page["page_summary"]["remaining"])
        self.assertEqual(0, page["page_summary"]["next_page"])
        self.assertEqual("seed_page_complete", page["page_summary"]["next_action"])
        self.assertEqual("seed_50", page["seeds"][0]["dataset_id"])

    def test_seed_page_summary_handles_empty_and_more_pages(self) -> None:
        empty = crawler_seed_page_summary(total=0, page=1, page_size=50, row_count=0)
        more = crawler_seed_page_summary(total=125, page=2, page_size=50, row_count=50)

        self.assertEqual(0, empty["shown_start"])
        self.assertEqual(0, empty["shown_end"])
        self.assertEqual(0, empty["page_count"])
        self.assertEqual("seed_page_complete", empty["next_action"])
        self.assertEqual(51, more["shown_start"])
        self.assertEqual(100, more["shown_end"])
        self.assertEqual(25, more["remaining"])
        self.assertEqual(3, more["page_count"])
        self.assertEqual(3, more["next_page"])
        self.assertEqual("show_next_seed_page", more["next_action"])

    def test_seed_row_uses_dataset_uid_as_favorite_key(self) -> None:
        dataset = seed_dataset("seed_01")

        row = crawler_seed_row(dataset, favorite_seed_uids={"demo_provider:seed_01"})

        self.assertEqual("demo_provider:seed_01", row["favorite_key"])
        self.assertTrue(row["favorite"])
        self.assertEqual("stac_collections", row["source_type"])
        self.assertEqual("catalog", row["data_family"])

    def test_seed_belongs_to_asset_requires_metadata_match(self) -> None:
        self.assertTrue(crawler_seed_belongs_to_asset(seed_dataset("seed_01"), "demo_asset"))
        self.assertFalse(crawler_seed_belongs_to_asset(seed_dataset("seed_01"), "other_asset"))

    def test_normalize_seed_page_clamps_invalid_input(self) -> None:
        self.assertEqual((1, 1), normalize_crawler_seed_page(page=-5, page_size=-2))
        self.assertEqual((1, MAX_CRAWLER_SEED_PAGE_SIZE), normalize_crawler_seed_page(page=0, page_size=500))

    def test_favorite_key_falls_back_to_dataset_id_and_title(self) -> None:
        without_uid = Dataset(
            dataset_uid="",
            provider_id="demo_provider",
            dataset_id="dataset-id",
            title="Dataset Title",
            categories=("demo",),
        )
        without_ids = Dataset(
            dataset_uid="",
            provider_id="demo_provider",
            dataset_id="",
            title="Dataset Title",
            categories=("demo",),
        )

        self.assertEqual("dataset-id", crawler_seed_favorite_key(without_uid))
        self.assertEqual("Dataset Title", crawler_seed_favorite_key(without_ids))

    def test_save_seed_favorite_persists_profile_state(self) -> None:
        with TemporaryDirectory() as tmp:
            profile_path = f"{tmp}/crawler_assets.local.json"

            saved = save_crawler_seed_favorite(
                asset_id="demo_asset",
                dataset_uid="demo_provider:seed_01",
                favorite=True,
                profile_path=profile_path,
            )
            removed = save_crawler_seed_favorite(
                asset_id="demo_asset",
                dataset_uid="demo_provider:seed_01",
                favorite=False,
                profile_path=profile_path,
            )
            profiles = load_crawler_asset_profiles(profile_path)

        self.assertTrue(saved["favorite"])
        self.assertEqual(1, saved["favorite_seed_count"])
        self.assertEqual("seed_favorite_saved", saved["next_action"])
        self.assertFalse(removed["favorite"])
        self.assertEqual(0, removed["favorite_seed_count"])
        self.assertEqual((), profiles["demo_asset"].favorite_seed_uids)

    def test_save_seed_favorite_requires_dataset_uid(self) -> None:
        with self.assertRaisesRegex(ValueError, "dataset_uid is required"):
            save_crawler_seed_favorite(asset_id="demo_asset", dataset_uid="")

    def test_cli_seed_page_reads_shared_registry_payload(self) -> None:
        repo = FakeSeedRepository([seed_dataset(f"seed_{index:02d}") for index in range(55)])
        result = crawler_asset_seed_page_cli_result(
            repo,
            asset_id="demo_asset",
            provider_id_override="demo_provider",
            page=2,
            page_size=50,
        )

        self.assertFalse(result["blocked"])
        self.assertEqual("demo_provider", result["provider_id"])
        self.assertEqual("override", result["provider_id_source"])
        self.assertEqual(55, result["total"])
        self.assertEqual(5, len(result["seeds"]))
        self.assertFalse(result["has_more"])
        self.assertEqual("seed_page_complete", result["next_action"])

    def test_cli_seed_page_blocks_when_source_and_provider_are_missing(self) -> None:
        repo = FakeSeedRepository([])

        result = crawler_asset_seed_page_cli_result(repo, asset_id="missing_asset")

        self.assertTrue(result["blocked"])
        self.assertEqual("", result["provider_id_source"])
        self.assertEqual("crawler_asset_source_not_found_or_provider_id_required", result["blocked_reason"])
        self.assertEqual("provide_crawler_asset_provider_id_or_fix_source_profile", result["next_action"])

    def test_run_crawler_asset_cli_emits_seed_page_json(self) -> None:
        repo = FakeSeedRepository([seed_dataset(f"seed_{index:02d}") for index in range(55)])
        args = SimpleNamespace(
            run_crawler_asset_listing=[],
            crawler_asset_listing_timeout=12.0,
            crawler_asset_listing_limit=100,
            crawler_asset_listing_max_pages=0,
            crawler_asset_listing_json=False,
            crawler_asset_seeds=["demo_asset"],
            crawler_asset_seeds_json=True,
            crawler_asset_seeds_provider_id="demo_provider",
            crawler_asset_seed_page=1,
            crawler_asset_seed_page_size=50,
            crawler_asset_profile_path="",
        )
        stdout = StringIO()

        with redirect_stdout(stdout):
            run_crawler_asset_cli(args, repo, lambda *args, **kwargs: None)

        payload = json.loads(stdout.getvalue())
        seed_pages = payload["seed_pages"]
        self.assertEqual("crawler_asset", payload["command"])
        self.assertEqual(1, seed_pages["asset_count"])
        self.assertEqual(55, seed_pages["seed_count"])
        self.assertEqual(1, seed_pages["has_more_count"])
        self.assertEqual("show_next_seed_page", seed_pages["next_action"])
        self.assertEqual(50, len(seed_pages["results"][0]["seeds"]))

    def test_crawler_asset_command_active_includes_seed_page_command(self) -> None:
        args = SimpleNamespace(run_crawler_asset_listing=[], crawler_asset_seeds=["demo_asset"])

        self.assertTrue(crawler_asset_command_active(args))


if __name__ == "__main__":
    unittest.main()
