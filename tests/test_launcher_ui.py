# 這份測試鎖定 Tk 視窗生命週期錯誤 suppressor，避免吞掉非預期例外。
import unittest
from types import SimpleNamespace
from tkinter import TclError
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from frontends.tk.launcher_ui import (
    ApiCollectionUi,
    PROJECT_ROOT,
    contextlib_suppress_tcl_error,
    data_store_env_template_path,
    database_sql_dry_run_available,
    local_file_provenance_review_message,
    yfinance_project_path_from_ui_text,
    yfinance_storage_review_paths_from_ui,
    yfinance_symbols_from_ui_text,
)
from api_launcher.db import connect_db
from api_launcher.repository import ApiCatalogRepository


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


class DataStoreUiHelperTests(unittest.TestCase):
    def test_data_store_env_template_path_sanitizes_profile_id(self) -> None:
        # local JSON 的 profile id 不一定乾淨；UI helper 要保證範本永遠落在 state 子目錄。
        path = data_store_env_template_path("../mysql default")

        self.assertEqual(PROJECT_ROOT / "state/data_store_env_templates/mysql_default.env.template", path)

    def test_data_store_next_action_message_guides_missing_env(self) -> None:
        # 測試 Tk 顯示文字跟 backend next_action 對齊；缺 env 時應引導使用者先寫範本。
        fake_ui = SimpleNamespace(tr=lambda zh, en: zh)
        result = SimpleNamespace(profile_id="mysql_default", status="missing_env", details={})

        hint = ApiCollectionUi.data_store_next_action_message(fake_ui, result)

        self.assertIn("寫出 env 範本", hint)


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


class LocalFileImportUiWorkerTests(unittest.TestCase):
    def test_local_file_provenance_review_message_summarizes_boundaries(self) -> None:
        message = local_file_provenance_review_message(
            {
                "source_label_zh_TW": "使用者自備本機檔案",
                "format_label_zh_TW": "CSV 表格檔",
                "trust_boundary_zh_TW": "只驗證 checksum，不驗證授權。",
                "blocked_operations_zh_TW": ["不掃描整個資料夾", "不移動或刪除來源檔", "不推定授權可商用", "不背景下載"],
                "recommended_next_step_zh_TW": "執行資料庫自檢。",
            }
        )

        self.assertIn("來源審查：使用者自備本機檔案（CSV 表格檔）", message)
        self.assertIn("不掃描整個資料夾、不移動或刪除來源檔、不推定授權可商用", message)
        self.assertIn("下一步：執行資料庫自檢。", message)

    def test_import_local_file_worker_writes_manifest_and_renames_existing_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            csv_path = root / "weather.csv"
            csv_path.write_text("station,temp\nTPE,28\n", encoding="utf-8")
            launcher_db = root / "launcher.sqlite"
            curated_db = root / "curated.sqlite"
            with closing(connect_db(launcher_db)) as conn:
                ApiCatalogRepository(conn).init_schema()
            with closing(sqlite3.connect(curated_db)) as curated:
                curated.execute('CREATE TABLE "weather" (station TEXT)')
                curated.execute('INSERT INTO "weather" VALUES (?)', ("OLD",))
                curated.commit()
            messages: list[str] = []
            fake_ui = object.__new__(ApiCollectionUi)
            fake_ui.root = SimpleNamespace(after=lambda _delay, callback: callback())
            fake_ui._connect = lambda: connect_db(launcher_db)
            fake_ui.tr = lambda zh, en: zh
            fake_ui.reload_data = lambda: None
            fake_ui.status_var = SimpleNamespace(set=lambda message: messages.append(message))

            with (
                patch("frontends.tk.launcher_ui.state_file", lambda name: root / name),
                patch("frontends.tk.launcher_ui.messagebox.showinfo") as showinfo,
                patch("frontends.tk.launcher_ui.messagebox.showerror"),
                patch("frontends.tk.launcher_ui.log_event"),
            ):
                fake_ui.import_local_file_worker(csv_path, curated_db, "weather")

            with closing(sqlite3.connect(curated_db)) as curated:
                original_rows = curated.execute('SELECT station FROM "weather"').fetchall()
                imported_rows = curated.execute('SELECT station, temp FROM "weather_2"').fetchall()
            with closing(connect_db(launcher_db)) as conn:
                manifest_count = conn.execute(
                    "SELECT COUNT(*) FROM dataset_asset_manifests WHERE provider_id = 'manual_local_files' AND status = 'ok'"
                ).fetchone()[0]

        self.assertEqual([("OLD",)], original_rows)
        self.assertEqual([("TPE", "28")], imported_rows)
        self.assertEqual(1, manifest_count)
        self.assertTrue(any("本機檔案已匯入：weather_2" in message for message in messages))
        self.assertIn("來源審查：使用者自備本機檔案", showinfo.call_args.args[1])
        self.assertIn("不會執行：不掃描整個資料夾", showinfo.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
