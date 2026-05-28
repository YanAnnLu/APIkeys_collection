import unittest
from types import SimpleNamespace

from api_launcher.paths import PROJECT_ROOT
from frontends.tk.ui_helpers import (
    crawler_seed_download_import_ui_message,
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
