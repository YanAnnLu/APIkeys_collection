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
    local_file_import_error_message,
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


class DownloadPlanPanelUiTests(unittest.TestCase):
    def test_download_skip_next_action_message_guides_partial_skip(self) -> None:
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh

        message = fake_ui.download_skip_next_action_message("下載工作已開始：1；略過：1", partial=True)

        self.assertIn("已啟動的 direct download 會繼續排隊", message)
        self.assertIn("解析 Adapter 計畫", message)

    def test_start_download_plan_items_warns_when_some_items_are_skipped(self) -> None:
        class FakeQueue:
            def __init__(self) -> None:
                self.submitted: list[dict[str, object]] = []

            def submit(self, entry: dict[str, object]) -> SimpleNamespace:
                # 測試只需要鎖定 UI 決策邊界，不啟動真正的下載 worker。
                self.submitted.append(entry)
                return SimpleNamespace(job_id=f"job-{len(self.submitted)}")

        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        fake_ui.prepare_provider_for_download = lambda _plan_key: True
        fake_ui.plan_entry_for_item = lambda _row, _version, plan_key: (
            {
                "download_url": "https://example.test/data.csv",
                "target_path": "downloads/data.csv",
                "download_eligibility": {"status": "direct_download"},
            }
            if plan_key == "direct"
            else {
                "download_eligibility": {
                    "status": "adapter_required",
                    "reason": "需要 Adapter 審核後才能下載",
                },
                "adapter_review": {"reason": "selector"},
            },
            None,
        )
        fake_ui.download_queue = FakeQueue()
        fake_ui.download_status_by_provider = {}
        fake_ui.import_status_by_plan_key = {}
        fake_ui.download_jobs_by_provider = {}
        fake_ui.download_providers_by_job = {}
        fake_ui.download_plan_entries_by_provider = {}
        fake_ui.update_download_jobs_panel = lambda: None
        status_messages: list[str] = []
        fake_ui.status_var = SimpleNamespace(set=lambda message: status_messages.append(message))

        with patch("frontends.tk.launcher_ui.messagebox.showinfo") as showinfo:
            fake_ui.start_download_plan_items(
                [
                    ("direct", SimpleNamespace(name="Direct source"), None),
                    ("adapter", SimpleNamespace(name="Adapter source"), None),
                ]
            )

        self.assertEqual(1, len(fake_ui.download_queue.submitted))
        self.assertEqual(("queued", "0%", str(Path("downloads/data.csv"))), fake_ui.download_status_by_provider["direct"])
        self.assertEqual("skipped", fake_ui.download_status_by_provider["adapter"][0])
        self.assertIn("下載工作已開始：1；略過：1", status_messages[-1])
        showinfo.assert_called_once()
        self.assertEqual("部分項目未啟動下載", showinfo.call_args.args[0])
        self.assertIn("已啟動的 direct download 會繼續排隊", showinfo.call_args.args[1])

    def test_download_plan_toggle_label_tracks_visibility(self) -> None:
        labels: list[str] = []
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        fake_ui.download_plan_toggle_var = SimpleNamespace(set=lambda value: labels.append(value))

        fake_ui.download_plan_visible = True
        fake_ui.update_download_plan_toggle_label()
        fake_ui.download_plan_visible = False
        fake_ui.update_download_plan_toggle_label()

        self.assertEqual(["收合下載計畫", "展開下載計畫"], labels)

    def test_toggle_download_plan_panel_hides_body_but_keeps_state(self) -> None:
        events: list[str] = []
        body = SimpleNamespace(
            pack=lambda **_kwargs: events.append("pack"),
            pack_forget=lambda: events.append("forget"),
        )
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        fake_ui.download_plan_visible = True
        fake_ui.download_plan_body = body
        fake_ui.download_plan_toggle_var = SimpleNamespace(set=lambda value: events.append(f"label:{value}"))
        fake_ui.status_var = SimpleNamespace(set=lambda value: events.append(f"status:{value}"))

        fake_ui.toggle_download_plan_panel()

        self.assertFalse(fake_ui.download_plan_visible)
        self.assertIn("forget", events)
        self.assertIn("label:展開下載計畫", events)
        self.assertIn("status:已收合下載計畫。", events)


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
    def test_local_file_import_error_message_keeps_guided_format_repair_clean(self) -> None:
        message = local_file_import_error_message(ValueError("Unsupported manual import format 'xlsx' for workbook.xlsx; 請先轉成支援格式。"))

        self.assertTrue(message.startswith("Unsupported manual import format"))
        self.assertNotIn("ValueError:", message)

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

    def test_import_local_file_worker_shows_guided_unsupported_format_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workbook_path = root / "weather.xlsx"
            workbook_path.write_bytes(b"not really excel")
            launcher_db = root / "launcher.sqlite"
            curated_db = root / "curated.sqlite"
            with closing(connect_db(launcher_db)) as conn:
                ApiCatalogRepository(conn).init_schema()
            messages: list[str] = []
            fake_ui = object.__new__(ApiCollectionUi)
            fake_ui.root = SimpleNamespace(after=lambda _delay, callback: callback())
            fake_ui._connect = lambda: connect_db(launcher_db)
            fake_ui.tr = lambda zh, en: zh
            fake_ui.status_var = SimpleNamespace(set=lambda message: messages.append(message))

            with (
                patch("frontends.tk.launcher_ui.state_file", lambda name: root / name),
                patch("frontends.tk.launcher_ui.messagebox.showerror") as showerror,
                patch("frontends.tk.launcher_ui.log_exception"),
            ):
                fake_ui.import_local_file_worker(workbook_path, curated_db, "weather")

            error_text = showerror.call_args.args[1]

        self.assertIn("Unsupported manual import format", error_text)
        self.assertIn("請先轉成支援格式", error_text)
        self.assertNotIn("ValueError:", error_text)
        self.assertTrue(any("Unsupported manual import format" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
