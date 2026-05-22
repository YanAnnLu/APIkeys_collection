# 這份測試鎖定 Tk 視窗生命週期錯誤 suppressor，避免吞掉非預期例外。
import unittest
from types import SimpleNamespace
from tkinter import TclError

from frontends.tk.launcher_ui import (
    PROJECT_ROOT,
    contextlib_suppress_tcl_error,
    database_sql_dry_run_available,
    yfinance_project_path_from_ui_text,
    yfinance_storage_review_paths_from_ui,
    yfinance_symbols_from_ui_text,
)


class TclErrorSuppressorTests(unittest.TestCase):
    def test_suppresses_tcl_errors(self) -> None:
        with contextlib_suppress_tcl_error():
            raise TclError("window no longer exists")

    def test_does_not_suppress_unexpected_errors(self) -> None:
        with self.assertRaises(RuntimeError):
            with contextlib_suppress_tcl_error():
                raise RuntimeError("unexpected")


class DatabaseDryRunUiHelperTests(unittest.TestCase):
    def test_database_sql_dry_run_available_reads_self_check_flag(self) -> None:
        suggestion = SimpleNamespace(details={"sql_dry_run_available": True})

        self.assertTrue(database_sql_dry_run_available(suggestion))

    def test_database_sql_dry_run_available_defaults_to_false(self) -> None:
        self.assertFalse(database_sql_dry_run_available(SimpleNamespace(details={})))
        self.assertFalse(database_sql_dry_run_available(SimpleNamespace(details="not-a-dict")))


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


if __name__ == "__main__":
    unittest.main()
