# 這份測試鎖定 Tk 視窗生命週期錯誤 suppressor，避免吞掉非預期例外。
import io
import unittest
from types import SimpleNamespace
from tkinter import TclError
import sqlite3
import tempfile
from contextlib import closing, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from frontends.tk.launcher_ui import (
    ApiCollectionUi,
    PROJECT_ROOT,
    main as launcher_ui_main,
)
from frontends.tk.dialogs import ProviderCandidateReviewDialog
from frontends.tk.startup_helpers import (
    contextlib_suppress_tcl_error,
    tk_startup_failure_message,
)
from frontends.tk.ui_helpers import (
    data_store_env_template_path,
    database_sql_dry_run_available,
    local_file_import_error_message,
    local_file_provenance_review_message,
    mvp_demo_smoke_exception_message,
    mvp_demo_smoke_result_message,
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

    def test_tk_startup_failure_message_guides_missing_tcl_runtime(self) -> None:
        message = tk_startup_failure_message(TclError("Can't find a usable init.tcl"))

        self.assertIn("Tk UI 無法啟動", message)
        self.assertIn("init.tcl", message)
        self.assertIn("py -B APIkeys_collection_ui.py", message)

    def test_main_returns_error_code_when_tk_root_cannot_start(self) -> None:
        output = io.StringIO()

        with (
            patch("frontends.tk.launcher_ui.Tk", side_effect=TclError("no display name")),
            patch("frontends.tk.launcher_ui.log_exception"),
            redirect_stderr(output),
        ):
            rc = launcher_ui_main()

        self.assertEqual(2, rc)
        self.assertIn("Tk UI 無法啟動", output.getvalue())


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


class CrawlerAuditUiHelperTests(unittest.TestCase):
    def test_provider_discovery_message_marks_metadata_review_boundary(self) -> None:
        # Provider discovery 只產生 review JSON；UI 文字要避免團隊誤以為已正式納管或抓取秘密。
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        payload = {
            "candidate_count": 1,
            "candidates": [{"provider_id": "example_provider", "confidence": 0.8}],
        }

        message = fake_ui.provider_discovery_message(payload, Path("state/provider_candidates.ui.json"))

        self.assertIn("Provider 候選發現完成：1 筆", message)
        self.assertIn("metadata-only review JSON", message)
        self.assertIn("example_provider: confidence=0.8", message)
        self.assertIn("state\\provider_candidates.ui.json", message.replace("/", "\\"))

    def test_provider_candidate_detail_text_keeps_review_only_warning(self) -> None:
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        candidate = {
            "provider_id": "example_provider",
            "name": "Example Provider",
            "categories": ["science", "metadata"],
            "confidence": 0.85,
            "source_url": "https://example.test/source",
            "docs_url": "https://example.test/docs",
            "evidence": ["crawled: https://example.test/source"],
        }

        detail = ProviderCandidateReviewDialog.candidate_detail_text(candidate, lambda _zh, en: en)

        self.assertIn("Provider ID: example_provider", detail)
        self.assertIn("Categories: science, metadata", detail)
        self.assertIn("Evidence:", detail)
        self.assertIn("does not mean the provider is managed", detail)

    def test_provider_seed_from_candidate_preserves_local_review_fields(self) -> None:
        # UI 寫入的是 ignored local seed，後續還要經過 promotion audit；這裡只驗證欄位轉換不遺失來源線索。
        fake_ui = object.__new__(ApiCollectionUi)
        candidate = {
            "provider_id": "example_provider",
            "name": "Example Provider",
            "owner": "Example Org",
            "categories": ["science", "metadata"],
            "geographic_scope": "global",
            "source_url": "https://example.test/source",
            "docs_url": "https://example.test/docs",
            "api_base_url": "https://api.example.test",
            "signup_url": "https://example.test/signup",
            "auth_type": "api_key",
        }

        seed = ProviderCandidateReviewDialog.provider_seed_from_candidate(candidate)

        self.assertEqual("example_provider", seed.provider_id)
        self.assertEqual(("science", "metadata"), seed.categories)
        self.assertEqual("https://example.test/source", seed.homepage_url)
        self.assertEqual("https://example.test/docs", seed.docs_url)
        self.assertEqual("api_key", seed.expected_auth_type)

    def test_provider_seed_from_candidate_rejects_missing_boundary_fields(self) -> None:
        fake_ui = object.__new__(ApiCollectionUi)

        with self.assertRaisesRegex(ValueError, "owner"):
            ProviderCandidateReviewDialog.provider_seed_from_candidate({"provider_id": "example_provider", "name": "Example"})

    def test_provider_dataset_source_from_candidate_creates_local_source_draft(self) -> None:
        # Provider review 面板的 source 草稿只進 ignored local config；正式 catalog 仍需 local discovery audit。
        fake_ui = object.__new__(ApiCollectionUi)
        candidate = {
            "provider_id": "example_provider",
            "name": "Example Provider",
            "source_type": "ckan_package_search",
            "endpoint_url": "https://data.example.test/api/3/action/package_search",
            "categories": ["open_data", "metadata"],
            "search_terms": ["ocean"],
        }

        source = ProviderCandidateReviewDialog.provider_dataset_source_from_candidate(candidate)

        self.assertEqual("example_provider_ckan_package_search", source.source_id)
        self.assertEqual("ckan_package_search", source.source_type)
        self.assertEqual(("ocean",), source.search_terms)

    def test_crawler_next_action_label_guides_zero_candidate_repair(self) -> None:
        # Tk 不解析 warning 文字；它只把 crawler 後端的 next_action 狀態碼翻成可操作的繁中提示。
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh

        label = fake_ui.crawler_next_action_label("repair_crawler_query_or_parser")

        self.assertIn("回傳 0 筆", label)
        self.assertIn("搜尋詞", label)

    def test_crawler_audit_issue_lines_include_source_next_action(self) -> None:
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        source_result = SimpleNamespace(
            source_id="ncei",
            error="",
            warnings=("zero_candidates: source returned 0 candidates",),
            next_action="repair_crawler_query_or_parser",
        )

        lines = fake_ui.crawler_audit_issue_lines((source_result,), limit=4)

        self.assertTrue(any("下一步" in line and "回傳 0 筆" in line for line in lines))
        self.assertTrue(any("zero_candidates" in line for line in lines))

    def test_crawler_audit_summary_lines_group_problem_sources(self) -> None:
        # UI 先顯示後端彙總過的 audit_summary，讓人類不必從逐 source warning 反推整體狀態。
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        summary = {
            "status": "warning",
            "source_count": 3,
            "candidate_count": 7,
            "problem_source_count": 1,
            "next_action": "inspect_source_audit_results_before_upsert_or_promotion",
            "by_warning_code": {"zero_candidates": 1},
            "by_next_action": {"repair_crawler_query_or_parser": 1},
            "problem_sources": [{"source_id": "ncei", "next_action": "repair_crawler_query_or_parser"}],
        }

        lines = fake_ui.crawler_audit_summary_lines(summary)

        self.assertTrue(any("整體狀態：warning" in line and "候選 7" in line for line in lines))
        self.assertTrue(any("總體下一步" in line and "來源審核結果" in line for line in lines))
        self.assertTrue(any("zero_candidates=1" in line for line in lines))
        self.assertTrue(any("優先檢查來源：ncei" in line for line in lines))

    def test_local_discovery_audit_message_marks_dry_run_and_summary(self) -> None:
        # promotion 前的 UI 必須明確說這只是 dry-run，並重用 crawler audit summary 的分組資訊。
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        payload = {
            "audited_source_count": 2,
            "promoted_provider_count": 1,
            "promoted_source_count": 1,
            "skipped_count": 1,
            "audit": {
                "audit_issue_count": 1,
                "audit_summary": {
                    "status": "warning",
                    "source_count": 2,
                    "candidate_count": 5,
                    "problem_source_count": 1,
                    "next_action": "inspect_source_audit_results_before_upsert_or_promotion",
                    "by_warning_code": {"zero_candidates": 1},
                    "problem_sources": [{"source_id": "local_ckan"}],
                },
            },
            "skipped": [{"source_id": "local_ckan", "reason": "audit_warning"}],
        }

        message = fake_ui.local_discovery_audit_message(payload, Path("state/local_discovery_audit.ui.json"))

        self.assertIn("dry-run，未寫入正式 catalog", message)
        self.assertIn("審核來源 2", message)
        self.assertIn("zero_candidates=1", message)
        self.assertIn("local_ckan: audit_warning", message)


class DownloadPlanPanelUiTests(unittest.TestCase):
    def test_mvp_demo_smoke_result_message_summarizes_user_visible_closure(self) -> None:
        payload = {
            "stage": "download_import_completed",
            "succeeded": True,
            "table_name": "demo_table",
            "row_count": 3,
            "artifacts": {
                "flow_manifest": "state/mvp_demo/flow.json",
                "curated_sqlite": "state/mvp_demo/curated_demo.sqlite",
            },
            "download_import": {
                "result": {
                    "completed": 1,
                    "imported": 1,
                    "failed": 0,
                    "import_failed": 0,
                }
            },
        }

        message = mvp_demo_smoke_result_message(payload, lambda zh, _en="": zh)

        self.assertIn("MVP Demo Smoke 通過", message)
        self.assertIn("匯入資料表：demo_table", message)
        self.assertIn("匯入筆數：3", message)
        self.assertIn("state/mvp_demo/curated_demo.sqlite", message)

    def test_mvp_demo_smoke_result_message_guides_failed_closure(self) -> None:
        payload = {
            "stage": "failed",
            "succeeded": False,
            "table_name": "",
            "row_count": 0,
            "next_action": "inspect_manifest",
            "download_import": {"result": {"completed": 0, "imported": 0, "failed": 1, "import_failed": 0}},
        }

        message = mvp_demo_smoke_result_message(payload, lambda zh, _en="": zh)

        self.assertIn("MVP Demo Smoke 未通過", message)
        self.assertIn("下一步：檢查 manifest 與最近事件紀錄", message)
        self.assertNotIn("inspect_manifest", message)
        self.assertIn("修復建議", message)

    def test_mvp_demo_smoke_exception_message_includes_cli_fallback(self) -> None:
        message = mvp_demo_smoke_exception_message(
            RuntimeError("sqlite locked"),
            PROJECT_ROOT / "state/mvp_demo/flow.json",
            lambda zh, _en="": zh,
        )

        self.assertIn("MVP Demo Smoke 無法完成", message)
        self.assertIn("--run-mvp-demo-smoke-json", message)
        self.assertIn("sqlite locked", message)

    def test_download_skip_next_action_message_guides_partial_skip(self) -> None:
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh

        message = fake_ui.download_skip_next_action_message("下載工作已開始：1；略過：1", partial=True)

        self.assertIn("已啟動的 direct download 會繼續排隊", message)
        self.assertIn("解析 Adapter 計畫", message)

    def test_import_skipped_detail_message_lists_reasons_and_limits_preview(self) -> None:
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh

        message = fake_ui.import_skipped_detail_message(
            [
                "Adapter page: 需要 Adapter 審核",
                "Metadata only: 只有 metadata",
                "Missing manifest: 請先完成下載",
            ],
            limit=2,
        )

        self.assertIn("會略過：3 個", message)
        self.assertIn("- Adapter page: 需要 Adapter 審核", message)
        self.assertIn("- Metadata only: 只有 metadata", message)
        self.assertNotIn("Missing manifest", message)
        self.assertIn("還有 1 個項目未列出", message)

    def test_import_supported_plan_results_confirmation_lists_skipped_reasons(self) -> None:
        fake_ui = object.__new__(ApiCollectionUi)
        fake_ui.tr = lambda zh, en: zh
        direct_row = SimpleNamespace(name="Direct CSV")
        adapter_row = SimpleNamespace(name="Adapter page")
        fake_ui.selected_plan_items = lambda: [
            ("direct", direct_row, None),
            ("adapter", adapter_row, None),
        ]
        fake_ui.plan_item_label = lambda _plan_key, row, _option=None: row.name
        fake_ui.download_plan_entries_by_provider = {
            "direct": {
                "import_plan": {"status": "supported_after_download"},
                "download_url": "https://example.test/data.csv",
            },
            "adapter": {
                "import_plan": {"status": "adapter_required", "reason": "需要 Adapter 審核後才能匯入"},
            },
        }
        fake_ui.ask_import_existing_table_policy = lambda: "rename"
        fake_ui.import_existing_table_policy_label = lambda _policy: "安全改名"

        with patch("frontends.tk.import_workflows.messagebox.askyesno", return_value=False) as askyesno:
            fake_ui.import_supported_plan_results_from_ui()

        askyesno.assert_called_once()
        message = askyesno.call_args.args[1]
        self.assertIn("將把 1 個已支援項目匯入 SQLite", message)
        self.assertIn("會略過：1 個", message)
        self.assertIn("- Adapter page: 需要 Adapter 審核後才能匯入", message)
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
                patch("frontends.tk.import_workflows.state_file", lambda name: root / name),
                patch("frontends.tk.import_workflows.messagebox.showinfo") as showinfo,
                patch("frontends.tk.import_workflows.messagebox.showerror"),
                patch("frontends.tk.import_workflows.log_event"),
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
                patch("frontends.tk.import_workflows.state_file", lambda name: root / name),
                patch("frontends.tk.import_workflows.messagebox.showerror") as showerror,
                patch("frontends.tk.import_workflows.log_exception"),
            ):
                fake_ui.import_local_file_worker(workbook_path, curated_db, "weather")

            error_text = showerror.call_args.args[1]

        self.assertIn("Unsupported manual import format", error_text)
        self.assertIn("請先轉成支援格式", error_text)
        self.assertNotIn("ValueError:", error_text)
        self.assertTrue(any("Unsupported manual import format" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
