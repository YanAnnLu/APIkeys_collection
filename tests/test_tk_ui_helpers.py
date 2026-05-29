import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api_launcher.paths import PROJECT_ROOT
from frontends.tk.crawler_asset_ui_helpers import (
    crawler_seed_download_import_target_paths,
    crawler_seed_download_import_ui_message,
)
from frontends.tk.crawler_asset_event_state import (
    crawler_asset_listing_outcomes_from_events,
    crawler_asset_plan_state_from_events,
)
from frontends.tk.ui_helpers import (
    yfinance_project_path_from_ui_text,
    yfinance_storage_review_paths_from_ui,
    yfinance_symbols_from_ui_text,
)


class YFinanceUiHelperTests(unittest.TestCase):
    def test_yfinance_symbols_from_ui_text_accepts_comma_and_space(self) -> None:
        # UI 允許一般人常用的逗號/空白輸入，並把重複 symbol 收斂成 adapter 使用的穩定 tuple。
        self.assertEqual(("AAPL", "MSFT"), yfinance_symbols_from_ui_text("aapl, MSFT AAPL"))

    def test_yfinance_symbols_from_ui_text_rejects_shell_like_input(self) -> None:
        with self.assertRaises(ValueError):
            yfinance_symbols_from_ui_text("AAPL;rm -rf")

    def test_yfinance_storage_review_paths_from_ui_normalizes_relative_paths(self) -> None:
        # Tk dialog 收到的是文字欄位；helper 先固定相對路徑基準，避免 review 寫到不可預期的工作目錄。
        plan_path, review_path = yfinance_storage_review_paths_from_ui("state/live_plan.json", "state/review.json")

        self.assertEqual(PROJECT_ROOT / "state/live_plan.json", plan_path)
        self.assertEqual(PROJECT_ROOT / "state/review.json", review_path)

    def test_yfinance_storage_review_paths_from_ui_rejects_empty_paths(self) -> None:
        with self.assertRaises(ValueError):
            yfinance_storage_review_paths_from_ui("", "state/review.json")

    def test_yfinance_project_path_from_ui_text_normalizes_handoff_path(self) -> None:
        # storage review dialog 會同時產生 JSON、SQL 與 Markdown；handoff 欄位也要套同一個 project-root 基準。
        self.assertEqual(
            PROJECT_ROOT / "state/storage_handoff.md",
            yfinance_project_path_from_ui_text("state/storage_handoff.md", "Handoff"),
        )

    def test_crawler_seed_download_import_ui_message_uses_backend_display_payload(self) -> None:
        result = SimpleNamespace(
            to_dict=lambda: {
                "dataset_uid": "demo_provider:dataset_a",
                "stage": "blocked_before_download",
                "succeeded": False,
                "artifacts": {
                    "downloads_root": "downloads/demo",
                    "curated_sqlite": "downloads/demo/curated_sources.db",
                },
                "next_action": "run_adapter_review_or_resolve_adapter_plan_before_downloading",
                "next_action_label": "先處理 Adapter 審核或解析計畫，再下載",
            }
        )

        message = crawler_seed_download_import_ui_message(result, lambda zh, _en: zh)

        self.assertFalse(message.succeeded)
        self.assertEqual("blocked_before_download", message.stage)
        self.assertIn("demo_provider:dataset_a", message.body)
        self.assertIn("先處理 Adapter 審核或解析計畫，再下載", message.body)
        self.assertNotIn("run_adapter_review_or_resolve_adapter_plan_before_downloading", message.body)

    def test_crawler_seed_download_import_ui_message_surfaces_callback_diagnostics(self) -> None:
        result = SimpleNamespace(
            pipeline=SimpleNamespace(
                to_dict=lambda: {
                    "stage": "download_import_completed",
                    "succeeded": True,
                    "result": {
                        "callback_errors": ["job-1 progress: RuntimeError: ui callback down"],
                    },
                }
            ),
            to_dict=lambda: {
                "dataset_uid": "demo_provider:dataset_a",
                "stage": "download_import_completed",
                "succeeded": True,
                "artifacts": {
                    "downloads_root": "downloads/demo",
                    "curated_sqlite": "downloads/demo/curated_sources.db",
                },
            },
        )

        message = crawler_seed_download_import_ui_message(result, lambda zh, _en: zh)

        self.assertTrue(message.succeeded)
        self.assertIn("進度回報：進度回報有警告 (1)", message.body)
        self.assertIn("檢查事件紀錄或 UI 進度回報", message.body)

    def test_crawler_seed_download_import_target_paths_sanitizes_asset_and_seed(self) -> None:
        with patch("frontends.tk.crawler_asset_ui_helpers.default_local_downloads_root", return_value=Path("C:/downloads")):
            targets = crawler_seed_download_import_target_paths("asset/demo", "provider:dataset/a")

        self.assertEqual(Path("C:/downloads/crawler_assets/asset_demo/provider_dataset_a"), targets.downloads_root)
        self.assertEqual(targets.downloads_root / "curated_sources.db", targets.import_sqlite_path)
        self.assertEqual(
            PROJECT_ROOT / "state/crawler_asset_seed_plans/asset_demo.provider_dataset_a.resolved.json",
            targets.plan_path,
        )

    def test_crawler_asset_plan_state_from_events_restores_display_caches(self) -> None:
        resolved_plan = {
            "providers": [
                {
                    "provider_id": "demo_provider",
                    "dataset_id": "demo_dataset",
                    "adapter_review": {
                        "adapter_id": "demo_adapter",
                        "source_url": "https://example.test/catalog",
                    },
                    "content_parser": {
                        "source_format": "netcdf",
                        "parser_id": "scientific_grid_review",
                        "import_status": "manual_review_required",
                        "review_bucket": "content_parser_required",
                    },
                    "download_eligibility": {"status": "adapter_required"},
                }
            ]
        }
        events = [
            {
                "event": "crawler_asset_plan_outcome_recorded",
                "context": {
                    "asset_id": "demo_index",
                    "outcome_label": "待 Adapter 1",
                    "plan_passport": {
                        "asset_id": "demo_index",
                        "candidate_count": 3,
                    },
                    "resolved_plan": "state/demo.resolved.json",
                },
            }
        ]

        state = crawler_asset_plan_state_from_events(events, read_plan=lambda _path: resolved_plan)

        self.assertEqual("待 Adapter 1", state.plan_outcomes["demo_index"])
        self.assertEqual("內容 Parser 待辦 1", state.content_review_outcomes["demo_index"])
        self.assertEqual(resolved_plan, state.resolved_plans["demo_index"])
        self.assertEqual(3, state.plan_passports["demo_index"]["candidate_count"])

    def test_crawler_asset_listing_outcomes_from_events_keeps_compact_seed_state(self) -> None:
        events = [
            {"event": "unrelated", "context": {"asset_id": "ignored"}},
            {
                "event": "crawler_asset_listing_recorded",
                "context": {
                    "asset_id": "demo_index",
                    "candidate_count": 55,
                    "upserted_count": 50,
                    "warning_count": 1,
                    "seed_enumeration": {"status": "limited_by_local_page", "label": "本機顯示上限"},
                    "remote_pagination": {"status": "has_more", "next_page_token_present": True},
                },
            },
        ]

        outcomes = crawler_asset_listing_outcomes_from_events(events)

        self.assertEqual(55, outcomes["demo_index"]["candidate_count"])
        self.assertEqual("limited_by_local_page", outcomes["demo_index"]["seed_enumeration"]["status"])
        self.assertEqual("has_more", outcomes["demo_index"]["remote_pagination"]["status"])
