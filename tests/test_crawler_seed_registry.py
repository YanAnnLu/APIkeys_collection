import unittest

from api_launcher.crawler_seed_registry import (
    MAX_CRAWLER_SEED_PAGE_SIZE,
    crawler_seed_belongs_to_asset,
    crawler_seed_favorite_key,
    crawler_seed_page,
    crawler_seed_row,
    normalize_crawler_seed_page,
)
from api_launcher.models import Dataset


class FakeSeedRepository:
    def __init__(self, datasets: list[Dataset]) -> None:
        self.datasets = datasets
        self.calls: list[tuple[str | None, str | None]] = []

    def list_dataset_candidates(self, status: str | None = "needs_review", provider_id: str | None = None) -> list[Dataset]:
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
        self.assertEqual(1, page["favorite_seed_count"])
        self.assertEqual("seed_00", page["seeds"][0]["dataset_id"])
        self.assertTrue(page["seeds"][0]["favorite"])

    def test_seed_page_returns_later_window_without_refetch_semantics(self) -> None:
        repo = FakeSeedRepository([seed_dataset(f"seed_{index:02d}") for index in range(55)])

        page = crawler_seed_page(repo, asset_id="demo_asset", provider_id="demo_provider", page=2, page_size=50)

        self.assertEqual(2, page["page"])
        self.assertEqual(5, len(page["seeds"]))
        self.assertFalse(page["has_more"])
        self.assertEqual("seed_50", page["seeds"][0]["dataset_id"])

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


if __name__ == "__main__":
    unittest.main()
