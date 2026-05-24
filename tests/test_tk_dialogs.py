from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api_launcher.schema_probe import SchemaProbeColumn, SchemaProbeResult, json_schema_probe
from api_launcher.source_download import SourceDownloadBounds
from frontends.tk import detail_panel_workflows as detail_panel_module
from frontends.tk.app_lifecycle_workflows import AppLifecycleWorkflowMixin
from api_launcher.bound_form import build_bound_form_spec, source_download_bounds_from_form_values
from frontends.tk.bound_form_dialog import DatasetBoundFormDialog
from frontends.tk.dialogs import (
    AdapterReviewDialog,
    AiModelSettingsDialog,
    DataStoreConnectionSettingsDialog,
    DatabaseClientSettingsDialog,
    DatasetCandidateReviewDialog,
    DeveloperCliDialog,
    GoogleGeminiSettingsDialog,
    ImportExistingTablePolicyDialog,
    ProviderCandidateReviewDialog,
    ProviderEditorDialog,
    RecentEventLogsDialog,
    StartupEnvironmentChecksDialog,
    UiLanguageSettingsDialog,
)
from frontends.tk.ai_summary_workflows import AiSummaryWorkflowMixin
from frontends.tk.crawler_asset_workflows import CrawlerAssetWorkflowMixin
from frontends.tk.detail_panel_workflows import DetailPanelWorkflowMixin
from frontends.tk.discovery_workflows import DiscoveryWorkflowMixin
from frontends.tk.download_plan_panel_workflows import DownloadPlanPanelWorkflowMixin
from frontends.tk.download_workflows import DownloadWorkflowMixin
from frontends.tk.import_workflows import ImportWorkflowMixin
from frontends.tk.mvp_demo_workflows import MvpDemoWorkflowMixin
from frontends.tk.oauth_workflows import OAuthWorkflowMixin
from frontends.tk.plan_workflows import PlanWorkflowMixin
from frontends.tk.provider_settings_workflows import ProviderSettingsWorkflowMixin
from frontends.tk.repair_workflows import RepairWorkflowMixin
from frontends.tk.responsive_layout_workflows import ResponsiveLayoutWorkflowMixin
from frontends.tk.showcase_workflows import ShowcaseWorkflowMixin
from frontends.tk.sidebar_workflows import SidebarWorkflowMixin
from frontends.tk.source_action_workflows import SourceActionWorkflowMixin
from frontends.tk.table_data_workflows import TableDataWorkflowMixin
from frontends.tk.table_interaction_workflows import TableInteractionWorkflowMixin
from frontends.tk.window_layout_workflows import WindowLayoutWorkflowMixin
from frontends.tk.yfinance_workflows import YfinanceWorkflowMixin


class _FakeVar:
    def __init__(self, value: str):
        self.value = value

    def get(self) -> str:
        return self.value


class TkDialogModuleTest(unittest.TestCase):
    def test_dialog_classes_are_importable(self) -> None:
        # 這個測試保護 launcher_ui.py 拆分後的公開匯入點，不需要真的開 Tk 視窗。
        self.assertTrue(callable(ProviderEditorDialog))
        self.assertTrue(callable(AdapterReviewDialog))
        self.assertTrue(callable(AiModelSettingsDialog))
        self.assertTrue(callable(DatabaseClientSettingsDialog))
        self.assertTrue(callable(DataStoreConnectionSettingsDialog))
        self.assertTrue(callable(DatasetBoundFormDialog))
        self.assertTrue(callable(DatasetCandidateReviewDialog))
        self.assertTrue(callable(DeveloperCliDialog))
        self.assertTrue(callable(GoogleGeminiSettingsDialog))
        self.assertTrue(callable(ImportExistingTablePolicyDialog))
        self.assertTrue(callable(ProviderCandidateReviewDialog))
        self.assertTrue(callable(UiLanguageSettingsDialog))
        self.assertTrue(callable(StartupEnvironmentChecksDialog))
        self.assertTrue(callable(RecentEventLogsDialog))
        self.assertTrue(callable(AppLifecycleWorkflowMixin))
        self.assertTrue(callable(AppLifecycleWorkflowMixin.present_main_window))
        self.assertTrue(callable(AiSummaryWorkflowMixin))
        self.assertTrue(callable(AiSummaryWorkflowMixin.generate_active_summary))
        self.assertTrue(callable(CrawlerAssetWorkflowMixin))
        self.assertTrue(callable(CrawlerAssetWorkflowMixin.refresh_crawler_asset_tab))
        self.assertTrue(callable(DetailPanelWorkflowMixin))
        self.assertTrue(callable(DetailPanelWorkflowMixin.update_detail_panel))
        self.assertTrue(callable(DiscoveryWorkflowMixin))
        self.assertTrue(callable(DiscoveryWorkflowMixin.discover_dataset_candidates_from_ui))
        self.assertTrue(callable(DownloadPlanPanelWorkflowMixin))
        self.assertTrue(callable(DownloadPlanPanelWorkflowMixin.toggle_download_plan_panel))
        self.assertTrue(callable(DownloadWorkflowMixin))
        self.assertTrue(callable(DownloadWorkflowMixin.start_download_plan_items))
        self.assertTrue(callable(ImportWorkflowMixin))
        self.assertTrue(callable(ImportWorkflowMixin.import_supported_plan_results_from_ui))
        self.assertTrue(callable(MvpDemoWorkflowMixin))
        self.assertTrue(callable(MvpDemoWorkflowMixin.write_mvp_demo_flow_from_ui))
        self.assertTrue(callable(OAuthWorkflowMixin))
        self.assertTrue(callable(OAuthWorkflowMixin.open_ai_profile_browser_login_dialog))
        self.assertTrue(callable(PlanWorkflowMixin))
        self.assertTrue(callable(PlanWorkflowMixin.current_download_plan_payload))
        self.assertTrue(callable(PlanWorkflowMixin.configure_selected_plan_bounds_from_ui))
        self.assertTrue(callable(ProviderSettingsWorkflowMixin))
        self.assertTrue(callable(ProviderSettingsWorkflowMixin.open_database_tool))
        self.assertTrue(callable(RepairWorkflowMixin))
        self.assertTrue(callable(RepairWorkflowMixin.open_repair_panel))
        self.assertTrue(callable(ResponsiveLayoutWorkflowMixin))
        self.assertTrue(callable(ResponsiveLayoutWorkflowMixin.open_detail_drawer))
        self.assertTrue(callable(ShowcaseWorkflowMixin))
        self.assertTrue(callable(ShowcaseWorkflowMixin.write_showcase_seed_coverage_from_ui))
        self.assertTrue(callable(ShowcaseWorkflowMixin.run_showcase_download_from_ui))
        self.assertTrue(callable(ShowcaseWorkflowMixin.start_showcase_resumable_download_from_ui))
        self.assertTrue(callable(SidebarWorkflowMixin))
        self.assertTrue(callable(SidebarWorkflowMixin.refresh_sidebar_filters))
        self.assertTrue(callable(SourceActionWorkflowMixin))
        self.assertTrue(callable(SourceActionWorkflowMixin.run_row_action))
        self.assertTrue(callable(TableDataWorkflowMixin))
        self.assertTrue(callable(TableDataWorkflowMixin.reload_data))
        self.assertTrue(callable(TableInteractionWorkflowMixin))
        self.assertTrue(callable(TableInteractionWorkflowMixin.set_category))
        self.assertTrue(callable(WindowLayoutWorkflowMixin))
        self.assertTrue(callable(WindowLayoutWorkflowMixin._build_layout))
        self.assertTrue(callable(YfinanceWorkflowMixin))
        self.assertTrue(callable(YfinanceWorkflowMixin.write_yfinance_demo_plan_from_ui))

    def test_detail_panel_module_keeps_widget_dependencies_local(self) -> None:
        # launcher_ui.py 不再集中 import 所有 Tk 元件；detail panel mixin 自己要帶齊用到的 widget/helper。
        self.assertTrue(callable(detail_panel_module.StringVar))
        self.assertTrue(callable(detail_panel_module.Canvas))
        self.assertIn("panel", detail_panel_module.COLORS)

    def test_database_client_profile_label_marks_enabled_state(self) -> None:
        # _profile_label 是 dialog 內部資料呈現邊界，可在 headless CI 中直接測。
        dialog = object.__new__(DatabaseClientSettingsDialog)
        enabled_profile = SimpleNamespace(id="sqlitebrowser", label="DB Browser", enabled=True)
        disabled_profile = SimpleNamespace(id="dbeaver", label="DBeaver", enabled=False)

        self.assertEqual(
            "sqlitebrowser - DB Browser (enabled)",
            dialog._profile_label(enabled_profile),
        )
        self.assertEqual(
            "dbeaver - DBeaver (disabled)",
            dialog._profile_label(disabled_profile),
        )
        self.assertEqual("", dialog._profile_label(None))

    def test_dataset_bound_form_dialog_values_convert_to_bounds_without_tk_mainloop(self) -> None:
        probe = json_schema_probe(
            "https://example.test/data.json",
            "https://example.test/data.json",
            b'[{"created_date":"2026-01-01T00:00:00","longitude":121.5,"latitude":25.0,"value":3}]',
        )
        dialog = object.__new__(DatasetBoundFormDialog)
        dialog.vars = {
            "sample_limit": _FakeVar("20"),
            "time_field": _FakeVar("created_date"),
            "start_date": _FakeVar("2026-01-01"),
            "end_date": _FakeVar("2026-01-31"),
            "longitude_field": _FakeVar("longitude"),
            "latitude_field": _FakeVar("latitude"),
            "bbox_west": _FakeVar("120.0"),
            "bbox_south": _FakeVar("23.0"),
            "bbox_east": _FakeVar("122.0"),
            "bbox_north": _FakeVar("25.0"),
        }
        dialog.multi_vars = {"required_columns": {"created_date": SimpleNamespace(get=lambda: True), "value": SimpleNamespace(get=lambda: False)}}

        bounds = source_download_bounds_from_form_values(dialog.form_values())

        self.assertEqual(20, bounds.sample_limit)
        self.assertEqual("created_date", bounds.time_field)
        self.assertEqual((120.0, 23.0, 122.0, 25.0), bounds.bbox)
        self.assertEqual(("created_date",), bounds.required_columns)

    def test_dataset_bound_form_spec_can_feed_tk_dialog_fields(self) -> None:
        probe = json_schema_probe(
            "https://example.test/data.json",
            "https://example.test/data.json",
            b'[{"created_date":"2026-01-01T00:00:00","longitude":121.5,"latitude":25.0}]',
        )

        spec = build_bound_form_spec(probe)

        self.assertTrue(any(field.field_id == "time_field" and field.default == "created_date" for field in spec.fields))
        self.assertTrue(any(field.field_id == "required_columns" and field.control == "multiselect" for field in spec.fields))

    def test_plan_workflow_applies_bounds_from_dynamic_dialog(self) -> None:
        ui = object.__new__(PlanWorkflowMixin)
        ui.download_plan_entries_by_provider = {}
        ui.plan_version_by_provider = {}
        ui.import_status_by_plan_key = {"plan-1": ("pending", "old")}
        ui.updated = False
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda zh, _en: zh
        ui.version_option_from_plan_entry = lambda _entry: None
        ui.update_download_plan_panel = lambda: setattr(ui, "updated", True)
        entry = {
            "provider_id": "demo",
            "download_url": "https://data.example.test/resource/demo.csv",
            "dataset_version": {"metadata": {"columns": ["created_date", "longitude", "latitude"]}},
        }
        probe = SchemaProbeResult(
            status="ok",
            source_url=str(entry["download_url"]),
            columns=(
                SchemaProbeColumn("created_date", "2026-01-01T00:00:00", "datetime"),
                SchemaProbeColumn("longitude", "121.5", "number"),
                SchemaProbeColumn("latitude", "25.0", "number"),
            ),
            row_count=1,
        )

        with patch("frontends.tk.plan_workflows.DatasetBoundFormDialog", return_value=SimpleNamespace(result=SourceDownloadBounds(sample_limit=7, time_field="created_date", start_date="2026-01-01"))):
            PlanWorkflowMixin._finish_plan_bounds_probe(ui, "plan-1", entry, probe)

        self.assertTrue(ui.updated)
        self.assertNotIn("plan-1", ui.import_status_by_plan_key)
        self.assertEqual(7, ui.download_plan_entries_by_provider["plan-1"]["download_bounds"]["sample_limit"])
        self.assertIn("已套用下載界域", ui.status_var.value)

    def test_database_client_selected_profile_reads_selected_id(self) -> None:
        # selected_profile 只依 combobox 標籤前段 id 配對，避免 label 變動影響 profile 選取。
        dialog = object.__new__(DatabaseClientSettingsDialog)
        sqlite_profile = SimpleNamespace(id="sqlitebrowser", label="DB Browser", enabled=True)
        dbeaver_profile = SimpleNamespace(id="dbeaver", label="DBeaver", enabled=True)
        dialog.profiles = [sqlite_profile, dbeaver_profile]
        dialog.profile_var = _FakeVar("dbeaver - DBeaver (enabled)")

        self.assertIs(dbeaver_profile, dialog.selected_profile())

    def test_data_store_active_profile_label_uses_ui_translation(self) -> None:
        # DataStore dialog 用主 UI 的 tr callback，避免抽出 class 後失去語言設定。
        dialog = object.__new__(DataStoreConnectionSettingsDialog)
        dialog.ui = SimpleNamespace(tr=lambda zh, _en: zh)
        with patch("frontends.tk.dialogs.active_data_store_profile", return_value=SimpleNamespace(profile_id="mysql_local")):
            self.assertEqual("目前作用中 profile：mysql_local", dialog._active_profile_label())

        with patch("frontends.tk.dialogs.active_data_store_profile", return_value=None):
            self.assertEqual("目前作用中 profile：-", dialog._active_profile_label())

    def test_developer_cli_split_command_preserves_quoted_arguments(self) -> None:
        # 開發者 CLI 允許輸入單行命令；quoted argument 必須維持為同一個 argv。
        self.assertEqual(
            ["python", "APIkeys_collection.py", "--summary", "hello world"],
            DeveloperCliDialog.split_command('python APIkeys_collection.py --summary "hello world"'),
        )

    def test_ui_language_codes_by_label_round_trips_display_labels(self) -> None:
        # 語言 combobox 顯示 label，但設定檔需要寫回穩定語言代碼。
        self.assertEqual(
            {"繁體中文": "zh-TW", "English": "en-US"},
            UiLanguageSettingsDialog.language_codes_by_label({"zh-TW": "繁體中文", "en-US": "English"}),
        )

    def test_recent_event_log_row_values_are_stable(self) -> None:
        # 事件表格欄位順序是 UI/測試共享契約，避免後續解耦時插入錯欄。
        event = {
            "timestamp": "2026-05-23T12:00:00Z",
            "level": "info",
            "component": "tk",
            "event": "demo",
            "message": "ok",
        }

        self.assertEqual(
            ("2026-05-23T12:00:00Z", "info", "tk", "demo", "ok"),
            RecentEventLogsDialog.event_row_values(event),
        )

    def test_ai_model_profile_row_values_mark_active_profile(self) -> None:
        # AI profile 表格用同一個 helper 產生 row，避免選用勾選欄位在拆分後失真。
        profile = SimpleNamespace(
            id="gemini_flash",
            label="Gemini Flash",
            kind="gemini",
            model="gemini-2.5-flash",
            enabled=True,
            notes="cloud",
        )

        self.assertEqual(
            ("✓", "Gemini Flash", "gemini", "gemini-2.5-flash", "API key ready", "啟用", "cloud"),
            AiModelSettingsDialog.profile_row_values(
                profile,
                active_profile_id="gemini_flash",
                login_status="API key ready",
                enabled_label="啟用",
                disabled_label="停用",
            ),
        )

    def test_google_gemini_account_provider_row_values_are_stable(self) -> None:
        # Google/Gemini 連線視窗抽成 class 後，帳號支援表格仍維持固定欄位順序。
        provider = SimpleNamespace(
            label="Google",
            auth_mode="oauth",
            status="planned",
            capability_targets=("gemini", "drive"),
        )

        self.assertEqual(
            ("Google", "oauth", "planned", "gemini, drive"),
            GoogleGeminiSettingsDialog.account_provider_row_values(provider),
        )

    def test_import_existing_table_policy_values_are_stable(self) -> None:
        # 同名資料表策略會傳進匯入 pipeline；value 不能因 UI 文案調整而漂移。
        self.assertEqual(("rename", "skip", "replace"), ImportExistingTablePolicyDialog.policy_option_values())

    def test_adapter_review_row_and_detail_text_are_stable(self) -> None:
        # Adapter review panel 是 agent 接力常看的表格；row/detail 形狀要固定。
        item = SimpleNamespace(
            adapter_id="socrata",
            required_action="resolve_api",
            outcome_bucket="source_resolution_required",
            expected_output="direct_plan_entry",
            provider_id="nyc_open_data",
            dataset_uid="abcd-1234",
            dataset_id="trees",
            version="latest",
            source_url="https://example.test/api",
            landing_url="https://example.test/page",
            download_status="adapter_required",
            import_status="pending",
            reason="selector",
        )

        self.assertEqual(
            ("socrata", "resolve_api", "source_resolution_required", "nyc_open_data", "trees", "latest", "https://example.test/api"),
            AdapterReviewDialog.review_item_row_values(item),
        )
        detail = AdapterReviewDialog.review_item_detail_text(item)
        self.assertIn("adapter_id: socrata", detail)
        self.assertIn("dataset_uid: abcd-1234", detail)
        self.assertIn("reason: selector", detail)

    def test_dataset_candidate_review_row_and_detail_text_are_stable(self) -> None:
        # Dataset candidate review 會讀 crawler 證據並改 registry 狀態；抽成 class 後仍要保住 row/detail 契約。
        dataset = SimpleNamespace(
            metadata={
                "candidate_status": "needs_review",
                "data_family": "tabular",
                "storage_hint": "sqlite",
                "analysis_hint": "pandas",
                "viewer_hint": "table",
                "confidence": 0.88,
                "source_url": "https://example.test/source.csv",
                "evidence": {"source_type": "ckan"},
            },
            provider_id="example_provider",
            title="Example Dataset",
            dataset_id="example_dataset",
            data_type="csv",
            native_format="CSV",
            geographic_scope="global",
            landing_url="https://example.test/landing",
            api_url="https://example.test/api",
        )

        self.assertEqual(
            ("needs_review", "example_provider", "Example Dataset", "tabular", "CSV", "0.88"),
            DatasetCandidateReviewDialog.candidate_row_values(dataset),
        )
        detail = DatasetCandidateReviewDialog.candidate_detail_text(dataset, lambda zh, _en: zh)
        self.assertIn("標題: Example Dataset", detail)
        self.assertIn("來源: https://example.test/source.csv", detail)
        self.assertIn('"source_type": "ckan"', detail)


if __name__ == "__main__":
    unittest.main()
