from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
import json
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from api_launcher.cli_crawler_assets import (
    crawler_asset_command_active,
    crawler_seed_download_import_cli_payload,
    crawler_seed_download_import_cli_result,
    crawler_asset_seed_page_cli_result,
    run_crawler_asset_cli,
    safe_seed_download_dirname,
)
from api_launcher.core import main
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
        self.assertEqual("sqlite_curated_import", row["content_pipeline_lane"])
        self.assertEqual("可匯入 SQLite", row["content_display_label"])
        self.assertEqual("success", row["content_display_tone"])
        self.assertFalse(row["content_review_required"])

    def test_seed_row_marks_archive_format_as_transform_required(self) -> None:
        dataset = replace(seed_dataset("seed_zip"), native_format="zip")

        row = crawler_seed_row(dataset)

        self.assertEqual("downloaded_payload_transform", row["content_pipeline_lane"])
        self.assertEqual("下載後需解壓或轉換", row["content_display_label"])
        self.assertEqual("unpack_or_transform_downloaded_payload", row["content_next_action"])
        self.assertTrue(row["content_review_required"])

    def test_seed_row_detects_content_profile_from_url_when_format_missing(self) -> None:
        dataset = Dataset(
            dataset_uid="demo_provider:seed_json",
            provider_id="demo_provider",
            dataset_id="seed_json",
            title="Seed JSON",
            categories=("demo",),
            native_format="",
            api_url="https://example.test/data/seed.json",
            metadata={
                "candidate_status": "needs_review",
                "discovery_source_id": "demo_asset",
                "discovery_source_type": "html_file_index",
            },
        )

        row = crawler_seed_row(dataset)

        self.assertEqual("json", row["content_import_profile"]["source_format"])
        self.assertEqual("sqlite_curated_import", row["content_pipeline_lane"])

    def test_seed_row_marks_socrata_resource_as_resolver_backed_import(self) -> None:
        dataset = Dataset(
            dataset_uid="nyc_open_data:ds_demo",
            provider_id="nyc_open_data",
            dataset_id="abcd-1234",
            title="Socrata Seed",
            categories=("open-data",),
            native_format="socrata_resource",
            api_url="https://data.cityofnewyork.us/resource/abcd-1234.json",
            metadata={
                "candidate_status": "needs_review",
                "discovery_source_id": "nyc_open_data_socrata_catalog",
                "discovery_source_type": "socrata_catalog_search",
            },
        )

        row = crawler_seed_row(dataset)

        self.assertEqual("socrata_resource", row["content_import_profile"]["source_format"])
        self.assertEqual("socrata_bounded_sample_query_resolver", row["content_import_profile"]["parser_id"])
        self.assertEqual("sqlite_curated_import", row["content_pipeline_lane"])
        self.assertEqual("可有界匯入 SQLite", row["content_display_label"])
        self.assertEqual("resolve_bounded_api_sample_then_download_import", row["content_next_action"])
        self.assertFalse(row["content_review_required"])

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
            run_crawler_seed_download_import=[],
            crawler_seed_download_import_json=False,
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
        args = SimpleNamespace(
            run_crawler_asset_listing=[],
            crawler_asset_seeds=["demo_asset"],
            run_crawler_seed_download_import=[],
        )

        self.assertTrue(crawler_asset_command_active(args))

    def test_crawler_asset_command_active_includes_seed_download_import_command(self) -> None:
        args = SimpleNamespace(
            run_crawler_asset_listing=[],
            crawler_asset_seeds=[],
            run_crawler_seed_download_import=[["demo_asset", "demo_provider:seed_01"]],
        )

        self.assertTrue(crawler_asset_command_active(args))

    def test_seed_download_import_cli_result_uses_formal_service(self) -> None:
        repo = FakeSeedRepository([seed_dataset("seed_01")])
        args = SimpleNamespace(
            downloads_root="state/test_downloads",
            import_sqlite_db="state/test_curated.db",
            download_timeout=7.5,
            plan_import_existing_table_policy="rename",
        )
        fake_result = Mock()
        fake_result.to_dict.return_value = {
            "asset_id": "demo_asset",
            "dataset_uid": "demo_provider:seed_01",
            "stage": "download_import_completed",
            "succeeded": True,
            "next_action": "inspect_imported_table",
        }

        with patch("api_launcher.cli_crawler_assets.run_crawler_seed_download_import", return_value=fake_result) as runner:
            payload = crawler_seed_download_import_cli_result(
                args,
                repo,
                asset_id="demo_asset",
                dataset_uid="demo_provider:seed_01",
            )

        self.assertTrue(payload["succeeded"])
        runner.assert_called_once()
        self.assertEqual("demo_asset", runner.call_args.args[0])
        self.assertEqual("demo_provider:seed_01", runner.call_args.args[1])
        self.assertIs(runner.call_args.args[2], repo)
        self.assertIn("crawler_seed_downloads", str(runner.call_args.args[3]))
        self.assertEqual("state/test_curated.db", runner.call_args.kwargs["import_sqlite_path"])
        self.assertEqual(7.5, runner.call_args.kwargs["timeout"])
        self.assertEqual("rename", runner.call_args.kwargs["import_existing_table_policy"])
        self.assertTrue(str(runner.call_args.kwargs["plan_path"]).endswith("resolved_seed_download_plan.json"))

    def test_seed_download_import_cli_payload_summarizes_results(self) -> None:
        payload = crawler_seed_download_import_cli_payload(
            [
                {"succeeded": True},
                {"succeeded": False},
            ]
        )

        self.assertEqual("crawler_seed_download_import", payload["command"])
        self.assertEqual(2, payload["request_count"])
        self.assertEqual(1, payload["succeeded_count"])
        self.assertEqual(1, payload["failed_or_blocked_count"])
        self.assertEqual("review_seed_download_import_results", payload["next_action"])

    def test_safe_seed_download_dirname_removes_path_separators(self) -> None:
        name = safe_seed_download_dirname("demo/asset", "provider:seed 01")

        self.assertNotIn("/", name)
        self.assertNotIn(":", name)
        self.assertIn("demo_asset", name)

    def test_cli_seed_download_import_json_suppresses_human_setup_lines(self) -> None:
        fake_result = Mock()
        fake_result.to_dict.return_value = {
            "asset_id": "demo_asset",
            "dataset_uid": "demo_provider:seed_01",
            "stage": "download_import_completed",
            "succeeded": True,
        }
        with TemporaryDirectory() as tmp:
            stdout = StringIO()
            with patch("api_launcher.cli_crawler_assets.run_crawler_seed_download_import", return_value=fake_result):
                with redirect_stdout(stdout):
                    rc = main(
                        [
                            "--db",
                            f"{tmp}/launcher.sqlite",
                            "--init-db",
                            "--seed",
                            "--run-crawler-seed-download-import",
                            "demo_asset",
                            "demo_provider:seed_01",
                            "--crawler-seed-download-import-json",
                        ]
                    )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(0, rc)
        self.assertEqual(1, payload["seed_download_import"]["request_count"])
        self.assertEqual(1, payload["seed_download_import"]["succeeded_count"])
        self.assertNotIn("[db]", stdout.getvalue())
        self.assertNotIn("[seed]", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
