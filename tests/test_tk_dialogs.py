from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api_launcher.schema_probe import SchemaProbeColumn, SchemaProbeResult, json_schema_probe
from api_launcher.source_download import SourceDownloadBounds
from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundPayload,
    apply_schema_probe_to_crawler_asset_bound_form_spec,
    build_crawler_asset_bound_form_spec,
)
from api_launcher.crawler_asset_schema_probe import CrawlerAssetSchemaProbeResult
from api_launcher.crawler_asset_service import CrawlerAssetListingResult
from api_launcher.crawler_assets import crawler_asset_from_source
from api_launcher.crawlers.source_patterns import DEFAULT_PATTERN_MINIMUM_CONFIDENCE, SourcePatternDetection
from api_launcher.crawlers.types import DatasetDiscoverySource
from api_launcher.downloads.jobs import DownloadProgress, JobStatus
from api_launcher.source_pattern_drafts import SourcePatternDraftError
from frontends.tk import detail_panel_workflows as detail_panel_module
from frontends.tk.app_lifecycle_workflows import AppLifecycleWorkflowMixin
from api_launcher.bound_form import build_bound_form_spec, source_download_bounds_from_form_values
from frontends.tk.bound_form_dialog import DatasetBoundFormDialog
from frontends.tk.crawler_asset_bound_dialog import CrawlerAssetBoundDialog, crawler_asset_bound_warning_text
from frontends.tk.crawler_asset_credential_dialog import (
    crawler_asset_credential_edit_payload,
    crawler_asset_credential_next_action_text,
)
from frontends.tk.crawler_asset_profile_dialog import CrawlerAssetProfileDialog
from frontends.tk.crawler_asset_seed_dialog import (
    CrawlerAssetSeedDialog,
    crawler_seed_dialog_recommended_text,
    crawler_seed_dialog_recommended_uid,
    crawler_seed_dialog_row_values,
    crawler_seed_dialog_rows,
    crawler_seed_dialog_schema_probe_entry,
)
from frontends.tk.source_pattern_draft_dialog import SourcePatternDraftDialog
from frontends.tk.source_pattern_draft_ui_helpers import (
    source_pattern_draft_blocked_event_context,
    source_pattern_draft_written_event_context,
)
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
from frontends.tk.crawler_asset_ui_helpers import (
    crawler_asset_credential_badge_label,
    crawler_asset_credential_event_context,
    crawler_asset_credential_guard_message,
    crawler_asset_credential_summary_text,
    crawler_asset_detail_text,
    crawler_asset_download_plan_summary_text,
    crawler_asset_listing_blocked_status_text,
    crawler_asset_listing_event_preview_payload,
    crawler_asset_plan_outcome_label,
    crawler_asset_plan_passport_summary_text,
    crawler_asset_row_values,
    crawler_asset_review_count_from_plan,
    crawler_asset_seed_enumeration_note_text,
    crawler_asset_seed_page_preview_text,
    crawler_asset_seed_page_status_text,
    crawler_seed_download_import_ui_message,
)
from frontends.tk.developer_diagnostics_workflows import (
    DeveloperDiagnosticsWorkflowMixin,
    crawler_handler_smoke_diagnostics_message,
    crawler_handler_smoke_diagnostics_payload,
)
from frontends.tk.detail_panel_workflows import DetailPanelWorkflowMixin
from frontends.tk.discovery_workflows import DiscoveryWorkflowMixin
from frontends.tk.download_plan_panel_workflows import DownloadPlanPanelWorkflowMixin
from frontends.tk.download_workflows import DownloadWorkflowMixin
from frontends.tk.import_workflows import ImportWorkflowMixin
from frontends.tk.mvp_demo_workflows import MvpDemoWorkflowMixin
from frontends.tk.oauth_workflows import OAuthWorkflowMixin
from frontends.tk.plan_workflows import PlanWorkflowMixin
from frontends.tk.project_maturity_workflows import (
    ProjectMaturityWorkflowMixin,
    project_maturity_message,
)
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

    def set(self, value: str) -> None:
        self.value = value


class _FakeTree:
    def __init__(self, selection: tuple[str, ...] = ()) -> None:
        self._selection = selection

    def selection(self) -> tuple[str, ...]:
        return self._selection


class TkDialogModuleTest(unittest.TestCase):
    def test_dialog_classes_are_importable(self) -> None:
        # 這個測試保護 launcher_ui.py 拆分後的公開匯入點，不需要真的開 Tk 視窗。
        self.assertTrue(callable(ProviderEditorDialog))
        self.assertTrue(callable(AdapterReviewDialog))
        self.assertTrue(callable(AiModelSettingsDialog))
        self.assertTrue(callable(DatabaseClientSettingsDialog))
        self.assertTrue(callable(CrawlerAssetBoundDialog))
        self.assertTrue(callable(CrawlerAssetProfileDialog))
        self.assertTrue(callable(CrawlerAssetSeedDialog))
        self.assertTrue(callable(SourcePatternDraftDialog))
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
        self.assertTrue(callable(DeveloperDiagnosticsWorkflowMixin))
        self.assertTrue(callable(DeveloperDiagnosticsWorkflowMixin.open_crawler_handler_smoke_diagnostics))
        self.assertTrue(callable(DetailPanelWorkflowMixin))
        self.assertTrue(callable(DetailPanelWorkflowMixin.update_detail_panel))
        self.assertTrue(callable(DiscoveryWorkflowMixin))
        self.assertTrue(callable(DiscoveryWorkflowMixin.discover_dataset_candidates_from_ui))
        self.assertTrue(callable(DownloadPlanPanelWorkflowMixin))
        self.assertTrue(callable(DownloadPlanPanelWorkflowMixin.toggle_download_plan_panel))
        self.assertTrue(callable(DownloadWorkflowMixin))
        self.assertTrue(callable(DownloadWorkflowMixin.start_download_plan_items))
        self.assertTrue(callable(DownloadWorkflowMixin.toggle_primary_download_action))
        self.assertTrue(callable(DownloadWorkflowMixin.update_primary_download_action_label))
        self.assertTrue(callable(ImportWorkflowMixin))
        self.assertTrue(callable(ImportWorkflowMixin.import_supported_plan_results_from_ui))
        self.assertTrue(callable(MvpDemoWorkflowMixin))
        self.assertTrue(callable(MvpDemoWorkflowMixin.write_mvp_demo_flow_from_ui))
        self.assertTrue(callable(OAuthWorkflowMixin))
        self.assertTrue(callable(OAuthWorkflowMixin.open_ai_profile_browser_login_dialog))
        self.assertTrue(callable(PlanWorkflowMixin))
        self.assertTrue(callable(PlanWorkflowMixin.current_download_plan_payload))
        self.assertTrue(callable(PlanWorkflowMixin.configure_selected_plan_bounds_from_ui))
        self.assertTrue(callable(ProjectMaturityWorkflowMixin))
        self.assertTrue(callable(ProjectMaturityWorkflowMixin.open_project_maturity_matrix))
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

    def test_oauth_background_job_uses_single_flight_helper(self) -> None:
        ui = object.__new__(OAuthWorkflowMixin)
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            started = OAuthWorkflowMixin._start_oauth_background_job(
                ui,
                ("oauth_browser_login", "profile-a", ""),
                lambda: None,
                on_duplicate=lambda: None,
            )

        self.assertTrue(started)
        self.assertTrue(thread_call.started)
        self.assertEqual((), thread_call.args)
        self.assertIn(("oauth_browser_login", "profile-a", ""), ui.oauth_active_jobs)

    def test_oauth_background_job_rejects_duplicate_before_thread_start(self) -> None:
        ui = object.__new__(OAuthWorkflowMixin)
        ui.oauth_active_jobs = {("oauth_device_poll", "profile-a", "device-code")}
        duplicate_calls: list[str] = []

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            started = OAuthWorkflowMixin._start_oauth_background_job(
                ui,
                ("oauth_device_poll", "profile-a", "device-code"),
                lambda: None,
                on_duplicate=lambda: duplicate_calls.append("duplicate"),
            )

        self.assertFalse(started)
        thread_class.assert_not_called()
        self.assertEqual(["duplicate"], duplicate_calls)

    def test_oauth_background_job_blocks_when_queue_full(self) -> None:
        ui = object.__new__(OAuthWorkflowMixin)
        ui.oauth_active_jobs = {
            ("oauth_browser_login", "profile-a", ""),
            ("oauth_device_poll", "profile-b", "device-code"),
        }
        capacity_calls: list[str] = []

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            started = OAuthWorkflowMixin._start_oauth_background_job(
                ui,
                ("oauth_browser_login", "profile-c", ""),
                lambda: None,
                on_duplicate=lambda: capacity_calls.append("duplicate"),
                on_capacity=lambda: capacity_calls.append("capacity"),
            )

        self.assertFalse(started)
        thread_class.assert_not_called()
        self.assertEqual(["capacity"], capacity_calls)

    def test_sidebar_favicon_fetch_uses_single_flight_job(self) -> None:
        ui = object.__new__(SidebarWorkflowMixin)
        ui.provider_icon_loading = set()
        ui.favicon_url_for_owner = lambda _owner: "https://example.test/favicon.ico"
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            SidebarWorkflowMixin.fetch_provider_icon_async(ui, "Example")

        self.assertTrue(thread_call.started)
        self.assertEqual((), thread_call.args)
        self.assertIn("Example", ui.provider_icon_loading)
        self.assertIn(("provider_favicon", "Example", "https://example.test/favicon.ico"), ui.sidebar_active_jobs)

    def test_sidebar_favicon_fetch_skips_duplicate_single_flight_job(self) -> None:
        ui = object.__new__(SidebarWorkflowMixin)
        ui.provider_icon_loading = set()
        ui.favicon_url_for_owner = lambda _owner: "https://example.test/favicon.ico"
        ui.sidebar_active_jobs = {("provider_favicon", "Example", "https://example.test/favicon.ico")}

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            SidebarWorkflowMixin.fetch_provider_icon_async(ui, "Example")

        thread_class.assert_not_called()
        self.assertEqual(set(), ui.provider_icon_loading)

    def test_sidebar_favicon_fetch_skips_when_queue_full(self) -> None:
        ui = object.__new__(SidebarWorkflowMixin)
        ui.provider_icon_loading = set()
        ui.favicon_url_for_owner = lambda _owner: "https://example.test/favicon.ico"
        ui.sidebar_active_jobs = {
            ("provider_favicon", f"Example {index}", f"https://example.test/{index}.ico")
            for index in range(4)
        }

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            SidebarWorkflowMixin.fetch_provider_icon_async(ui, "Example")

        thread_class.assert_not_called()
        self.assertEqual(set(), ui.provider_icon_loading)

    def test_provider_discovery_uses_single_flight_job(self) -> None:
        ui = object.__new__(DiscoveryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            DiscoveryWorkflowMixin.discover_provider_candidates_from_ui(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual((), thread_call.args)
        self.assertIn(("provider_discovery", "all", ""), ui.discovery_active_jobs)
        self.assertIn("Discovering provider candidates", ui.status_var.value)

    def test_provider_discovery_blocks_when_discovery_queue_full(self) -> None:
        ui = object.__new__(DiscoveryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.discovery_active_jobs = {
            ("dataset_candidate_discovery", "provider_a", ""),
            ("local_discovery_audit", "dry_run", ""),
        }

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            DiscoveryWorkflowMixin.discover_provider_candidates_from_ui(ui)

        thread_class.assert_not_called()
        self.assertIn("at capacity", ui.status_var.value)

    def test_dataset_candidate_discovery_is_single_flight_per_scope(self) -> None:
        ui = object.__new__(DiscoveryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.selected_provider_ids = lambda: ("provider_a", "provider_b")
        ui.discovery_active_jobs = {("dataset_candidate_discovery", "provider_a,provider_b", "")}

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            DiscoveryWorkflowMixin.discover_dataset_candidates_from_ui(ui)

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_dataset_candidate_discovery_blocks_when_discovery_queue_full(self) -> None:
        ui = object.__new__(DiscoveryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.selected_provider_ids = lambda: ("provider_c",)
        ui.discovery_active_jobs = {
            ("provider_discovery", "all", ""),
            ("local_discovery_audit", "dry_run", ""),
        }

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            DiscoveryWorkflowMixin.discover_dataset_candidates_from_ui(ui)

        thread_class.assert_not_called()
        self.assertIn("at capacity", ui.status_var.value)

    def test_local_discovery_audit_uses_single_flight_job(self) -> None:
        ui = object.__new__(DiscoveryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            DiscoveryWorkflowMixin.audit_local_discovery_from_ui(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual((), thread_call.args)
        self.assertIn(("local_discovery_audit", "dry_run", ""), ui.discovery_active_jobs)
        self.assertIn("Auditing local discovery drafts", ui.status_var.value)

    def test_local_discovery_audit_blocks_when_discovery_queue_full(self) -> None:
        ui = object.__new__(DiscoveryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.discovery_active_jobs = {
            ("provider_discovery", "all", ""),
            ("dataset_candidate_discovery", "provider_a", ""),
        }

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            DiscoveryWorkflowMixin.audit_local_discovery_from_ui(ui)

        thread_class.assert_not_called()
        self.assertIn("at capacity", ui.status_var.value)

    def test_source_action_metadata_crawl_uses_single_flight_job(self) -> None:
        ui = object.__new__(SourceActionWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        provider_ids = ["provider_b", "provider_a"]
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            SourceActionWorkflowMixin.crawl_provider_ids(ui, provider_ids)

        self.assertTrue(thread_call.started)
        self.assertEqual((provider_ids,), thread_call.args)
        self.assertIn(("metadata_crawl", "provider_a,provider_b", ""), ui.source_action_active_jobs)

    def test_source_action_metadata_crawl_is_single_flight_per_provider_scope(self) -> None:
        ui = object.__new__(SourceActionWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.source_action_active_jobs = {("metadata_crawl", "provider_a,provider_b", "")}

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            SourceActionWorkflowMixin.crawl_provider_ids(ui, ["provider_b", "provider_a"])

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_source_action_metadata_crawl_blocks_when_queue_full(self) -> None:
        ui = object.__new__(SourceActionWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.source_action_active_jobs = {
            ("metadata_crawl", "provider_a", ""),
            ("metadata_crawl", "provider_b", ""),
        }

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            SourceActionWorkflowMixin.crawl_provider_ids(ui, ["provider_c"])

        thread_class.assert_not_called()
        self.assertIn("at capacity", ui.status_var.value)

    def test_ai_summary_uses_single_flight_job(self) -> None:
        ui = object.__new__(AiSummaryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.active_provider_id = "provider_a"
        ui.selected_ai_profile_id = "local_ollama"
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.row_by_provider_id = lambda _provider_id: SimpleNamespace(provider_id="provider_a", name="Provider A")
        profile = SimpleNamespace(id="local_ollama", label="Local Ollama", kind="ollama", enabled=True)
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.ai_summary_workflows.core.ai_summary_profiles", return_value=[profile]), patch(
            "frontends.tk.background_jobs.threading.Thread", FakeThread
        ):
            AiSummaryWorkflowMixin.generate_active_summary(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual(("provider_a", "local_ollama"), thread_call.args)
        self.assertIn(("ai_summary", "provider_a", "local_ollama"), ui.ai_summary_active_jobs)
        self.assertIn("Local Ollama", ui.status_var.value)

    def test_ai_summary_is_single_flight_per_provider_and_profile(self) -> None:
        ui = object.__new__(AiSummaryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.active_provider_id = "provider_a"
        ui.selected_ai_profile_id = "local_ollama"
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.row_by_provider_id = lambda _provider_id: SimpleNamespace(provider_id="provider_a", name="Provider A")
        ui.ai_summary_active_jobs = {("ai_summary", "provider_a", "local_ollama")}
        profile = SimpleNamespace(id="local_ollama", label="Local Ollama", kind="ollama", enabled=True)

        with patch("frontends.tk.ai_summary_workflows.core.ai_summary_profiles", return_value=[profile]), patch(
            "frontends.tk.background_jobs.threading.Thread"
        ) as thread_class:
            AiSummaryWorkflowMixin.generate_active_summary(ui)

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_ai_summary_blocks_when_queue_full(self) -> None:
        ui = object.__new__(AiSummaryWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.active_provider_id = "provider_c"
        ui.selected_ai_profile_id = "local_ollama"
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.row_by_provider_id = lambda _provider_id: SimpleNamespace(provider_id="provider_c", name="Provider C")
        ui.ai_summary_active_jobs = {
            ("ai_summary", "provider_a", "local_ollama"),
            ("ai_summary", "provider_b", "local_ollama"),
        }
        profile = SimpleNamespace(id="local_ollama", label="Local Ollama", kind="ollama", enabled=True)

        with patch("frontends.tk.ai_summary_workflows.core.ai_summary_profiles", return_value=[profile]), patch(
            "frontends.tk.background_jobs.threading.Thread"
        ) as thread_class:
            AiSummaryWorkflowMixin.generate_active_summary(ui)

        thread_class.assert_not_called()
        self.assertIn("at capacity", ui.status_var.value)

    def test_detail_panel_module_keeps_widget_dependencies_local(self) -> None:
        # launcher_ui.py 不再集中 import 所有 Tk 元件；detail panel mixin 自己要帶齊用到的 widget/helper。
        self.assertTrue(callable(detail_panel_module.StringVar))
        self.assertTrue(callable(detail_panel_module.Canvas))
        self.assertIn("panel", detail_panel_module.COLORS)

    def test_tk_crawler_handler_smoke_diagnostics_uses_compact_payload(self) -> None:
        payload = crawler_handler_smoke_diagnostics_payload()
        message = crawler_handler_smoke_diagnostics_message(payload)

        self.assertEqual("tk", payload["surface"])
        self.assertEqual("developer_diagnostics", payload["purpose"])
        self.assertTrue(payload["developer_only"])
        self.assertNotIn("source_results", json.dumps(payload, ensure_ascii=False))
        self.assertIn("Supported source types", message)
        self.assertIn("offline contract smoke", message)
        self.assertIn("摘要失敗時，執行 handler smoke JSON 診斷", message)
        self.assertNotIn("run_dataset_discovery_handler_smoke_json_if_summary_fails", message)

    def test_tk_crawler_handler_smoke_diagnostics_dialog_sets_status(self) -> None:
        class _Ui(DeveloperDiagnosticsWorkflowMixin):
            root = None

            def __init__(self) -> None:
                self.status_var = _FakeVar("")

            def tr(self, zh_tw: str, en_us: str = "") -> str:
                return zh_tw

        ui = _Ui()
        with patch("frontends.tk.developer_diagnostics_workflows.log_event") as log_event_mock, patch(
            "frontends.tk.developer_diagnostics_workflows.messagebox.showinfo"
        ) as showinfo_mock:
            payload = ui.open_crawler_handler_smoke_diagnostics()

        self.assertEqual("crawler_handler_contract_smoke", payload["diagnostic_id"])
        self.assertIn("開發者診斷", showinfo_mock.call_args.args[0])
        self.assertIn("Crawler handler contract smoke", showinfo_mock.call_args.args[1])
        self.assertIn("Crawler handler", ui.status_var.get())
        self.assertEqual(1, log_event_mock.call_count)

    def test_project_maturity_message_shows_backend_construction_state(self) -> None:
        payload = {
            "canonical_delivery_scope": {"closure_percent": 100, "status": "ready_for_mvp_demo"},
            "answer_template_zh_TW": "不要用單一百分比回答。",
            "rows": [
                {
                    "area_label": "Renderer / Unreal / simulation bridge",
                    "status_icon": "🚧",
                    "display_label": "施工中 / 合約",
                    "current_limitations": ["contract only"],
                }
            ],
        }

        message = project_maturity_message(payload)

        self.assertIn("100% / ready_for_mvp_demo", message)
        self.assertIn("🚧 Renderer / Unreal / simulation bridge: 施工中 / 合約", message)
        self.assertIn("does not calculate a single project percentage", message)

    def test_project_maturity_dialog_uses_backend_payload_and_sets_status(self) -> None:
        class _Ui(ProjectMaturityWorkflowMixin):
            root = None

            def __init__(self) -> None:
                self.status_var = _FakeVar("")

            def tr(self, zh_tw: str, en_us: str = "") -> str:
                return zh_tw

        ui = _Ui()
        payload = {
            "matrix_version": "test",
            "canonical_delivery_scope": {"closure_percent": 100, "status": "ready_for_mvp_demo"},
            "rows": [{"area_label": "Renderer", "status_icon": "🚧", "display_label": "施工中 / 合約"}],
        }
        with patch("frontends.tk.project_maturity_workflows.project_maturity_payload", return_value=payload) as backend, patch(
            "frontends.tk.project_maturity_workflows.log_event"
        ) as log_event_mock, patch("frontends.tk.project_maturity_workflows.messagebox.showinfo") as showinfo_mock:
            result = ui.open_project_maturity_matrix()

        backend.assert_called_once_with()
        self.assertIs(result, payload)
        self.assertIn("專案成熟度矩陣", showinfo_mock.call_args.args[0])
        self.assertIn("🚧 Renderer", showinfo_mock.call_args.args[1])
        self.assertIn("專案成熟度矩陣", ui.status_var.get())
        log_event_mock.assert_called_once()

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

    def test_crawler_asset_bound_dialog_values_without_tk_mainloop(self) -> None:
        dialog = object.__new__(CrawlerAssetBoundDialog)
        dialog.vars = {
            "collection": _FakeVar("landsat-c2"),
            "start_date": _FakeVar("2026-01-01"),
            "limit": _FakeVar("10"),
        }
        dialog.multi_vars = {"columns": {"datetime": SimpleNamespace(get=lambda: True), "quality": SimpleNamespace(get=lambda: False)}}

        values = dialog.form_values()

        self.assertEqual("landsat-c2", values["collection"])
        self.assertEqual("2026-01-01", values["start_date"])
        self.assertEqual("10", values["limit"])
        self.assertEqual(["datetime"], values["columns"])

    def test_crawler_asset_bound_dialog_applies_recommended_values_without_guessing(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo Taiwan STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
            search_terms=("landsat",),
            geographic_scope="taiwan",
            max_results=80,
        )
        asset = crawler_asset_from_source(source)
        spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema, source=source)
        dialog = object.__new__(CrawlerAssetBoundDialog)
        dialog.spec = spec
        dialog.vars = {
            field.field_id: _FakeVar("")
            for field in spec.fields
            if field.control != "multiselect"
        }
        dialog.multi_vars = {}

        dialog.apply_recommended_values()

        self.assertEqual("25", dialog.vars["limit"].get())
        self.assertEqual("", dialog.vars["collection"].get())
        self.assertEqual("", dialog.vars["time_field"].get())
        self.assertEqual("", dialog.vars["bbox_west"].get())

    def test_crawler_asset_bound_dialog_applies_named_bbox_preset(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo Taiwan STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
            geographic_scope="taiwan",
        )
        asset = crawler_asset_from_source(source)
        spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema, source=source)
        dialog = object.__new__(CrawlerAssetBoundDialog)
        dialog.spec = spec
        dialog.vars = {
            field.field_id: _FakeVar("")
            for field in spec.fields
            if field.control != "multiselect"
        }
        dialog.multi_vars = {}

        applied = dialog.apply_preset("taiwan")

        self.assertTrue(applied)
        self.assertEqual("119.0", dialog.vars["bbox_west"].get())
        self.assertEqual("21.5", dialog.vars["bbox_south"].get())
        self.assertEqual("123.5", dialog.vars["bbox_east"].get())
        self.assertEqual("25.5", dialog.vars["bbox_north"].get())
        self.assertFalse(dialog.apply_preset("missing_region"))

    def test_crawler_asset_bound_warning_text_does_not_leak_warning_codes(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo Taiwan STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
            geographic_scope="taiwan",
        )
        asset = crawler_asset_from_source(source)
        spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema, source=source)

        text = crawler_asset_bound_warning_text(spec, lambda zh, _en: zh)

        self.assertIn("欄位探測", text)
        self.assertNotIn("warning_codes", text)
        self.assertNotIn("schema_probe_recommended", text)

    def test_crawler_asset_bound_warning_text_explains_applied_probe_without_raw_code(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo Taiwan STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
            geographic_scope="taiwan",
        )
        asset = crawler_asset_from_source(source)
        spec = build_crawler_asset_bound_form_spec(asset.asset_id, asset.capabilities[2].bounds_schema, source=source)
        probe = SchemaProbeResult(
            status="ok",
            source_url="https://example.test/stac/items",
            columns=(SchemaProbeColumn("created_date", "2026-01-01", "datetime"),),
            row_count=1,
        )
        enriched = apply_schema_probe_to_crawler_asset_bound_form_spec(spec, probe)

        text = crawler_asset_bound_warning_text(enriched, lambda zh, _en: zh)

        self.assertIn("欄位探測結果已套用", text)
        self.assertNotIn("schema_probe_applied", text)

    def test_crawler_asset_workflow_stores_bounds_payload_before_building_plan(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )
        asset = crawler_asset_from_source(source)
        payload = CrawlerAssetBoundPayload(
            asset_id=asset.asset_id,
            facet_values={"limit": 5},
            field_values={"limit": 5},
            maps_to_values={"SourceDownloadBounds.sample_limit": 5},
        )
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.selected_crawler_asset = lambda: asset
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda _zh, en: en
        ui.root = object()
        ui.downloader_tab = "downloader"
        ui.main_notebook = SimpleNamespace(selected=None)
        ui.main_notebook.select = lambda tab: setattr(ui.main_notebook, "selected", tab)
        thread_call = SimpleNamespace(target=None, args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.target = target
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with (
            patch("frontends.tk.crawler_asset_workflows.CrawlerAssetBoundDialog", return_value=SimpleNamespace(result=payload)) as dialog_class,
            patch("frontends.tk.background_jobs.threading.Thread", FakeThread),
        ):
            CrawlerAssetWorkflowMixin.prepare_selected_crawler_asset_download(ui)

        dialog_class.assert_called_once()
        self.assertEqual("demo_provider", ui.active_provider_id)
        self.assertEqual(payload.to_dict(), ui.crawler_asset_bound_payloads["demo_stac"])
        self.assertTrue(thread_call.started)
        self.assertEqual(("demo_stac", payload), thread_call.args)
        self.assertIn("Building download plan from crawler asset", ui.status_var.value)

    def test_crawler_asset_download_plan_is_single_flight_before_bounds_dialog(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.selected_crawler_asset = lambda: asset
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda _zh, en: en
        ui.crawler_asset_active_jobs = {("asset_download_plan", "demo_stac", "")}

        with (
            patch("frontends.tk.crawler_asset_workflows.CrawlerAssetBoundDialog") as dialog_class,
            patch("frontends.tk.background_jobs.threading.Thread") as thread_class,
        ):
            CrawlerAssetWorkflowMixin.prepare_selected_crawler_asset_download(ui)

        dialog_class.assert_not_called()
        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_crawler_asset_listing_is_single_flight_per_asset(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.selected_crawler_asset = lambda: asset
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda _zh, en: en
        ui.crawler_asset_active_jobs = {("asset_listing", "demo_index", "")}

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            CrawlerAssetWorkflowMixin.run_selected_crawler_asset_listing(ui)

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_source_pattern_draft_dialog_form_values_without_tk_mainloop(self) -> None:
        dialog = object.__new__(SourcePatternDraftDialog)
        dialog.tr = lambda zh, _en: zh
        dialog.vars = {
            "url": _FakeVar(" https://example.test/stac "),
            "provider_id": _FakeVar("demo_provider"),
            "name": _FakeVar("Demo STAC"),
            "source_id": _FakeVar("demo_stac"),
            "categories": _FakeVar("raster, satellite\nscience"),
            "geographic_scope": _FakeVar("global"),
            "max_results": _FakeVar("25"),
            "min_expected_candidates": _FakeVar("2"),
            "timeout": _FakeVar("4.5"),
            "minimum_confidence": _FakeVar("0.6"),
        }

        values = dialog.form_values()

        self.assertEqual("https://example.test/stac", values["url"])
        self.assertEqual(("raster", "satellite", "science"), values["categories"])
        self.assertEqual(25, values["max_results"])
        self.assertEqual(2, values["min_expected_candidates"])
        self.assertEqual(4.5, values["timeout"])
        self.assertEqual(0.6, values["minimum_confidence"])

    def test_source_pattern_draft_dialog_uses_single_flight_job(self) -> None:
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.root = object()
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        result = {"url": "https://example.test/stac", "provider_id": "demo_provider"}
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with (
            patch("frontends.tk.crawler_asset_workflows.SourcePatternDraftDialog", return_value=SimpleNamespace(result=result)),
            patch("frontends.tk.background_jobs.threading.Thread", FakeThread),
        ):
            CrawlerAssetWorkflowMixin.open_source_pattern_draft_dialog(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual((result,), thread_call.args)
        self.assertIn(("source_pattern_draft", "https://example.test/stac", ""), ui.crawler_asset_active_jobs)
        self.assertIn("Detecting source URL", ui.status_var.value)

    def test_source_pattern_draft_dialog_is_single_flight_per_url(self) -> None:
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.root = object()
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.crawler_asset_active_jobs = {("source_pattern_draft", "https://example.test/stac", "")}
        result = {"url": "https://example.test/stac", "provider_id": "demo_provider"}

        with (
            patch("frontends.tk.crawler_asset_workflows.SourcePatternDraftDialog", return_value=SimpleNamespace(result=result)),
            patch("frontends.tk.background_jobs.threading.Thread") as thread_class,
        ):
            CrawlerAssetWorkflowMixin.open_source_pattern_draft_dialog(ui)

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_source_pattern_draft_message_keeps_audit_next_step_visible(self) -> None:
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda zh, _en: zh
        summary = {
            "dataset_source_path": "state/private/dataset_discovery_sources.local.json",
            "audit_command": "python APIkeys_collection.py --promote-local-discovery-dry-run",
            "source_pattern_detection": {
                "pattern_id": "stac",
                "confidence": 0.95,
                "source_type_hint": "stac_collections",
                "evidence": ("json_contains_stac_version", "json_references_collections"),
            },
            "sources": [
                {
                    "source_id": "demo_stac",
                    "source_type": "stac_collections",
                    "endpoint_url": "https://example.test/stac",
                }
            ],
        }

        message = CrawlerAssetWorkflowMixin.source_pattern_draft_message(ui, summary)

        self.assertIn("不是正式 catalog promotion", message)
        self.assertIn("Pattern：stac", message)
        self.assertIn("Source ID：demo_stac", message)
        self.assertIn("--promote-local-discovery-dry-run", message)

    def test_source_pattern_draft_worker_uses_backend_default_confidence(self) -> None:
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.root = SimpleNamespace(after=lambda _delay, callback: callback())
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.refresh_crawler_asset_tab = lambda: None
        summary = {
            "dataset_source_path": "state/private/dataset_discovery_sources.local.json",
            "audit_command": "python APIkeys_collection.py --promote-local-discovery-dry-run",
            "source_pattern_detection": {"pattern_id": "stac", "confidence": 0.95, "source_type_hint": "stac_collections"},
            "sources": [{"source_id": "demo_stac", "source_type": "stac_collections", "endpoint_url": "https://example.test/stac"}],
            "audit_source_ids": ["demo_stac"],
        }

        with (
            patch("frontends.tk.crawler_asset_workflows.write_source_draft_from_url", return_value=summary) as writer,
            patch("frontends.tk.crawler_asset_workflows.log_event"),
            patch("frontends.tk.crawler_asset_workflows.messagebox.showinfo"),
        ):
            CrawlerAssetWorkflowMixin._source_pattern_draft_worker(ui, {"url": "https://example.test/stac"})

        self.assertEqual(DEFAULT_PATTERN_MINIMUM_CONFIDENCE, writer.call_args.kwargs["minimum_confidence"])

    def test_source_pattern_draft_written_event_context_is_compact(self) -> None:
        summary = {
            "audit_source_ids": ["demo_stac"],
            "source_pattern_detection": {"pattern_id": "stac", "confidence": 0.95},
        }

        context = source_pattern_draft_written_event_context(
            summary,
            source_url="https://example.test/stac",
            output_path="state/private/dataset_discovery_sources.local.json",
        )

        self.assertEqual("https://example.test/stac", context["source_url"])
        self.assertEqual("state/private/dataset_discovery_sources.local.json", context["output_path"])
        self.assertEqual(["demo_stac"], context["audit_source_ids"])
        self.assertEqual({"pattern_id": "stac", "confidence": 0.95}, context["source_pattern_detection"])

    def test_source_pattern_draft_blocked_event_context_is_compact(self) -> None:
        summary = {
            "review_reason": "source_pattern_unknown",
            "next_action": "review_source_profile_or_add_detector",
            "source_pattern_detection": {"pattern_id": "unknown", "confidence": 0.1},
        }

        context = source_pattern_draft_blocked_event_context(
            summary,
            source_url="https://example.test/landing",
        )

        self.assertEqual("https://example.test/landing", context["source_url"])
        self.assertEqual("source_pattern_unknown", context["review_reason"])
        self.assertEqual("review_source_profile_or_add_detector", context["next_action"])
        self.assertEqual({"pattern_id": "unknown", "confidence": 0.1}, context["source_pattern_detection"])

    def test_source_pattern_draft_review_message_uses_human_next_action_label(self) -> None:
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        summary = {
            "review_reason": "source_pattern_unknown",
            "next_action": "review_source_profile_or_add_detector",
            "next_action_label_en": "Review the source URL before adding a detector.",
            "source_pattern_detection": {
                "pattern_id": "unknown",
                "confidence": 0.1,
                "source_type_hint": "",
                "evidence": ["below_minimum_confidence"],
            },
        }

        message = CrawlerAssetWorkflowMixin.source_pattern_draft_review_message(ui, summary)

        self.assertIn("kept in review", message)
        self.assertIn("source_pattern_unknown", message)
        self.assertIn("unknown", message)
        self.assertIn("0.10", message)
        self.assertIn("Review the source URL", message)
        self.assertNotIn("review_source_profile_or_add_detector", message)

    def test_source_pattern_draft_success_message_uses_human_next_action_label(self) -> None:
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        summary = {
            "dataset_source_path": "state/private/dataset_discovery_sources.local.json",
            "audit_command": "python APIkeys_collection.py --promote-local-discovery-dry-run",
            "next_action": "run_local_discovery_audit_before_catalog_promotion",
            "next_action_label_en": "Run the local discovery audit before promotion.",
            "source_pattern_detection": {
                "pattern_id": "stac",
                "confidence": 0.95,
                "source_type_hint": "stac_collections",
                "evidence": ["json_contains_stac_version"],
            },
            "sources": [{"source_id": "demo_stac", "source_type": "stac_collections", "endpoint_url": "https://example.test/stac"}],
        }

        message = CrawlerAssetWorkflowMixin.source_pattern_draft_message(ui, summary)

        self.assertIn("Run the local discovery audit", message)
        self.assertIn("Command: python APIkeys_collection.py", message)
        self.assertNotIn("run_local_discovery_audit_before_catalog_promotion", message)

    def test_source_pattern_draft_worker_shows_review_warning_for_structured_block(self) -> None:
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.root = SimpleNamespace(after=lambda _delay, callback: callback())
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.refresh_crawler_asset_tab = lambda: (_ for _ in ()).throw(AssertionError("should not refresh"))
        error = SourcePatternDraftError(
            "source_pattern_unknown",
            "source pattern detector returned unknown; keep this URL in review",
            source_url="https://example.test/landing",
            detection=SourcePatternDetection(
                pattern_id="unknown",
                confidence=0.1,
                evidence=("below_minimum_confidence",),
            ),
        )

        with (
            patch("frontends.tk.crawler_asset_workflows.write_source_draft_from_url", side_effect=error),
            patch("frontends.tk.crawler_asset_workflows.log_event") as event_log,
            patch("frontends.tk.crawler_asset_workflows.log_exception") as exception_log,
            patch("frontends.tk.crawler_asset_workflows.messagebox.showwarning") as showwarning,
            patch("frontends.tk.crawler_asset_workflows.messagebox.showerror") as showerror,
        ):
            CrawlerAssetWorkflowMixin._source_pattern_draft_worker(ui, {"url": "https://example.test/landing"})

        showwarning.assert_called_once()
        showerror.assert_not_called()
        exception_log.assert_not_called()
        event_log.assert_called_once()
        self.assertIn("source_pattern_unknown", ui.status_var.value)
        self.assertIn("source_pattern_unknown", showwarning.call_args.args[1])

    def test_crawler_asset_download_plan_summary_guides_review_required(self) -> None:
        result = SimpleNamespace(
            blocked=False,
            outcome_bucket="review_required",
            direct_download_count=0,
            review_required_count=2,
            user_next_action="open_adapter_review_or_adjust_bounds",
        )

        message = crawler_asset_download_plan_summary_text(result, 0, "state/crawler_asset_plans/demo.resolved.json", lambda zh, _en: zh)

        self.assertIn("目前沒有可直接下載項目", message)
        self.assertIn("2 筆需要 Adapter 待辦", message)
        self.assertIn("界域設定調整條件", message)
        self.assertIn("state/crawler_asset_plans/demo.resolved.json", message)

    def test_crawler_asset_download_plan_summary_guides_ready_queue(self) -> None:
        result = SimpleNamespace(
            blocked=False,
            outcome_bucket="ready_to_download",
            direct_download_count=3,
            review_required_count=0,
            user_next_action="open_downloader_and_start_or_pause_queue",
        )

        message = crawler_asset_download_plan_summary_text(result, 3, "", lambda zh, _en: zh)

        self.assertIn("直接下載 3 筆", message)
        self.assertIn("已加入下載器 3 筆", message)
        self.assertIn("開始 / 暫停", message)

    def test_crawler_asset_download_plan_summary_blocked_uses_human_next_action_label(self) -> None:
        result = SimpleNamespace(
            blocked=True,
            blocked_reason="crawler_asset_disabled",
            outcome_bucket="blocked",
            direct_download_count=0,
            review_required_count=0,
            user_next_action="enable_before_building_download_plan",
        )

        message = crawler_asset_download_plan_summary_text(result, 0, "", lambda zh, _en: zh)

        self.assertIn("crawler_asset_disabled", message)
        self.assertIn("先啟用爬蟲資產", message)
        self.assertNotIn("enable_before_building_download_plan", message)

    def test_crawler_asset_download_plan_summary_mentions_content_review(self) -> None:
        result = SimpleNamespace(
            blocked=False,
            outcome_bucket="review_required",
            direct_download_count=0,
            review_required_count=1,
            user_next_action="open_adapter_review_or_adjust_bounds",
            resolved_plan={
                "providers": [
                    {
                        "provider_id": "demo_provider",
                        "dataset_id": "demo_dataset",
                        "download_eligibility": {"status": "adapter_required"},
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
                    }
                ]
            },
        )

        message = crawler_asset_download_plan_summary_text(result, 0, "", lambda zh, _en: zh)

        self.assertIn("內容格式待辦：內容 Parser 待辦 1", message)

    def test_crawler_asset_plan_outcome_label_shortens_common_buckets(self) -> None:
        ready = SimpleNamespace(blocked=False, outcome_bucket="ready_to_download", review_required_count=0)
        partial = SimpleNamespace(blocked=False, outcome_bucket="partial_review_required", review_required_count=2)
        review = SimpleNamespace(blocked=False, outcome_bucket="review_required", review_required_count=2)
        zero = SimpleNamespace(blocked=False, outcome_bucket="zero_candidates", review_required_count=0)
        blocked = SimpleNamespace(blocked=True, outcome_bucket="blocked", blocked_reason="missing_credentials")

        self.assertEqual("可下載 3", crawler_asset_plan_outcome_label(ready, 3))
        self.assertEqual("可下載 1 / 待辦 2", crawler_asset_plan_outcome_label(partial, 1))
        self.assertEqual("待 Adapter 2", crawler_asset_plan_outcome_label(review, 0))
        self.assertEqual("零候選", crawler_asset_plan_outcome_label(zero, 0))
        self.assertEqual("已阻擋 missing_credentials", crawler_asset_plan_outcome_label(blocked, 0))

    def test_crawler_asset_row_values_use_last_plan_outcome(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.crawler_asset_plan_outcomes = {"demo_index": "可下載 1"}
        ui.crawler_asset_content_review_outcomes = {"demo_index": "內容 Parser 待辦 1"}

        with patch(
            "frontends.tk.crawler_asset_workflows.crawler_asset_credential_status",
            return_value={"display_label": "免登入", "configured_count": 0, "field_count": 0},
        ):
            values = CrawlerAssetWorkflowMixin.crawler_asset_row_values(ui, asset)

        self.assertIn("免登入", values)
        self.assertEqual("入口列表", values[-2])
        self.assertEqual("可下載 1 / 內容 Parser 待辦 1", values[-1])

    def test_crawler_asset_row_values_fallback_uses_human_next_action_label(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)

        values = crawler_asset_row_values(
            asset,
            credential_status={"display_label": "免登入", "configured_count": 0, "field_count": 0},
        )

        self.assertIn("候選", values[-1])
        self.assertNotIn("review_or_upsert_dataset_candidates", values[-1])

    def test_crawler_asset_detail_text_uses_seed_scope_display_label(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_ckan",
            provider_id="demo_provider",
            name="Demo CKAN",
            source_type="ckan_package_search",
            endpoint_url="https://catalog.example.test",
        )
        asset = crawler_asset_from_source(source)

        detail = crawler_asset_detail_text(
            asset,
            last_plan_outcome="",
            content_review="",
            resolved_plan=None,
            plan_passport=None,
            credential_status={"display_label": "免登入", "configured_count": 0, "field_count": 0},
            tr=lambda zh, _en: zh,
        )

        self.assertIn("Seed：", detail)
        self.assertIn("分頁 catalog", detail)
        self.assertNotIn("paginated_catalog", detail)

    def test_crawler_asset_credential_badge_and_summary_use_backend_payload(self) -> None:
        payload = {
            "display_label": "需要登入 / API Key",
            "display_badge_label": "後端徽章 1/2",
            "display_summary_zh_TW": "後端摘要：缺少 NASA_TOKEN",
            "display_summary_en": "Backend summary: missing NASA_TOKEN",
            "configured_count": 1,
            "field_count": 2,
            "missing_required": ["NASA_TOKEN"],
            "next_action": "edit_local_credentials_before_live_download",
        }

        self.assertEqual("後端徽章 1/2", crawler_asset_credential_badge_label(payload))
        summary = crawler_asset_credential_summary_text(payload, lambda zh, _en: zh)

        self.assertIn("後端摘要", summary)
        self.assertIn("NASA_TOKEN", summary)

    def test_crawler_asset_credential_summary_fallback_uses_human_next_action_label(self) -> None:
        payload = {
            "display_label": "需要登入 / API Key",
            "configured_count": 0,
            "field_count": 1,
            "missing_required": ["EARTHDATA_TOKEN"],
            "next_action": "edit_local_credentials_before_live_download",
            "display_profile": {
                "next_action_label_zh_TW": "先完成登入設定，再下載資料",
                "next_action_label_en": "Finish login settings before downloading",
            },
        }

        summary = crawler_asset_credential_summary_text(payload, lambda zh, _en: zh)

        self.assertIn("先完成登入設定", summary)
        self.assertNotIn("edit_local_credentials_before_live_download", summary)

    def test_crawler_asset_credential_summary_hides_unknown_raw_next_action(self) -> None:
        payload = {
            "display_label": "需要登入 / API Key",
            "configured_count": 0,
            "field_count": 1,
            "missing_required": ["EARTHDATA_TOKEN"],
            "next_action": "new_backend_credential_action",
        }

        summary = crawler_asset_credential_summary_text(payload, lambda zh, _en: zh)

        self.assertIn("檢查登入設定", summary)
        self.assertNotIn("new_backend_credential_action", summary)

    def test_crawler_asset_listing_blocked_status_uses_human_next_action_label(self) -> None:
        result = SimpleNamespace(
            blocked_reason="disabled",
            next_action="enable_before_crawl",
        )

        message = crawler_asset_listing_blocked_status_text(result, lambda zh, _en: zh)

        self.assertIn("先啟用爬蟲資產，再枚舉 seed", message)
        self.assertNotIn("enable_before_crawl", message)

    def test_crawler_asset_seed_page_preview_uses_shared_page_payload(self) -> None:
        payload = {
            "total": 55,
            "has_more": True,
            "page_summary": {
                "shown_start": 1,
                "shown_end": 50,
                "remaining": 5,
                "next_action": "show_next_seed_page",
            },
            "seeds": [
                {
                    "title": "Taiwan Rainfall",
                    "dataset_id": "rainfall",
                    "native_format": "csv",
                    "version": "2026-05",
                    "content_display_label": "可匯入 SQLite",
                    "favorite": True,
                },
                {
                    "title": "Taiwan Temperature",
                    "dataset_id": "temperature",
                    "native_format": "json",
                    "version": "",
                    "favorite": False,
                },
            ],
        }

        text = crawler_asset_seed_page_preview_text(payload, lambda zh, _en: zh, preview_limit=1)

        self.assertIn("顯示第 1-50 筆，共 55 筆", text)
        self.assertIn("★ Taiwan Rainfall", text)
        self.assertIn("csv, 2026-05", text)
        self.assertIn("可匯入 SQLite", text)
        self.assertIn("本頁另有 1 筆", text)
        self.assertIn("顯示更多 Seed", text)

    def test_crawler_asset_seed_page_preview_includes_remote_pagination_note(self) -> None:
        payload = {
            "total": 1,
            "has_more": False,
            "page_summary": {"shown_start": 1, "shown_end": 1, "remaining": 0},
            "seeds": [{"title": "Remote Seed", "dataset_id": "remote_seed"}],
        }
        listing = {
            "seed_enumeration": {
                "label": "已枚舉前 1000 筆 seed",
                "help": "遠端可能還有更多 seed。",
                "remote_pagination": {
                    "status": "has_more",
                    "exhausted": False,
                    "next_page_token_present": True,
                },
            }
        }

        text = crawler_asset_seed_page_preview_text(payload, lambda zh, _en: zh, listing_outcome=listing)

        self.assertIn("已枚舉前 1000 筆 seed", text)
        self.assertIn("還有下一頁線索", text)
        self.assertIn("token 已由後端遮蔽", text)
        self.assertIn("Remote Seed", text)

    def test_crawler_asset_seed_enumeration_note_handles_not_reported(self) -> None:
        listing = {"seed_enumeration": {"label": "已枚舉 3 筆 seed", "remote_pagination": {"status": "not_reported"}}}

        text = crawler_asset_seed_enumeration_note_text(listing, lambda zh, _en: zh)

        self.assertIn("尚未回報", text)
        self.assertIn("本機 catalog", text)

    def test_crawler_asset_listing_event_preview_payload_keeps_seed_status(self) -> None:
        context = {
            "asset_id": "demo_index",
            "candidate_count": 1000,
            "upserted_count": 998,
            "warning_count": 1,
            "max_results": 1000,
            "complete_seed": True,
            "seed_enumeration": {
                "status": "local_limit_reached",
                "label": "已枚舉前 1000 筆 seed",
                "remote_pagination": {"status": "has_more", "next_page_token_present": True},
            },
            "remote_pagination": {"status": "has_more", "next_page_token_present": True},
        }

        payload = crawler_asset_listing_event_preview_payload(context)

        self.assertEqual("demo_index", payload["asset_id"])
        self.assertEqual(1000, payload["candidate_count"])
        self.assertEqual("local_limit_reached", payload["seed_enumeration"]["status"])
        self.assertEqual("has_more", payload["remote_pagination"]["status"])

    def test_crawler_asset_seed_page_status_guides_empty_catalog(self) -> None:
        payload = {"total": 0, "page_summary": {"shown_start": 0, "shown_end": 0, "remaining": 0}, "seeds": []}

        text = crawler_asset_seed_page_status_text(payload, lambda zh, _en: zh)

        self.assertIn("本機 catalog", text)
        self.assertIn("清單擷取", text)

    def test_load_crawler_asset_seed_page_reads_shared_registry(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        status_values: list[str] = []
        seed_page_values: list[str] = []
        ui.tr = lambda zh, _en: zh
        ui.status_var = SimpleNamespace(set=lambda value: status_values.append(value))
        ui.crawler_asset_seed_page_var = SimpleNamespace(set=lambda value: seed_page_values.append(value))
        ui.crawler_asset_seed_pages = {}
        ui._connect = lambda: SimpleNamespace(close=lambda: None)
        payload = {
            "total": 1,
            "has_more": False,
            "page_summary": {"shown_start": 1, "shown_end": 1, "remaining": 0},
            "seeds": [{"title": "Seed 1", "dataset_id": "seed_1", "favorite": True}],
        }

        with (
            patch("frontends.tk.crawler_asset_workflows.load_crawler_asset_source", return_value=source),
            patch("frontends.tk.crawler_asset_workflows.ApiCatalogRepository", return_value="repository") as repository_class,
            patch("frontends.tk.crawler_asset_workflows.crawler_asset_favorite_seed_uids", return_value=("demo_provider:seed_1",)),
            patch("frontends.tk.crawler_asset_workflows.crawler_seed_page", return_value=payload) as seed_page,
        ):
            CrawlerAssetWorkflowMixin.load_crawler_asset_seed_page(ui, asset, page=2)

        repository_class.assert_called_once()
        seed_page.assert_called_once_with(
            "repository",
            asset_id="demo_index",
            provider_id="demo_provider",
            page=2,
            favorite_seed_uids=("demo_provider:seed_1",),
        )
        self.assertIs(payload, ui.crawler_asset_seed_pages["demo_index"])
        self.assertTrue(seed_page_values)
        self.assertTrue(status_values)
        self.assertIn("已到最後一頁", status_values[-1])

    def test_crawler_asset_seed_dialog_rows_are_ui_only_projection(self) -> None:
        payload = {
            "seeds": [
                {
                    "dataset_uid": "demo_provider:seed_1",
                    "dataset_id": "seed_1",
                    "title": "Seed 1",
                    "native_format": "csv",
                    "content_display_label": "可匯入 SQLite",
                    "version": "2026",
                    "candidate_status": "new",
                    "favorite": True,
                },
                "bad-row",
            ]
        }

        rows = crawler_seed_dialog_rows(payload)
        values = crawler_seed_dialog_row_values(rows[0])

        self.assertEqual(1, len(rows))
        self.assertEqual(("★", "Seed 1", "csv", "可匯入 SQLite", "2026", "demo_provider:seed_1", "new"), values)

    def test_crawler_asset_seed_dialog_surfaces_backend_recommended_seed(self) -> None:
        payload = {
            "recommended_seed_uid": "demo_provider:seed_1",
            "recommended_seed": {
                "dataset_uid": "demo_provider:seed_1",
                "title": "Seed 1",
                "content_display_label": "可匯入 SQLite",
            },
        }

        text = crawler_seed_dialog_recommended_text(payload, lambda zh, _en: zh)

        self.assertEqual("demo_provider:seed_1", crawler_seed_dialog_recommended_uid(payload))
        self.assertIn("推薦 seed", text)
        self.assertIn("Seed 1", text)
        self.assertIn("下載推薦 Seed", text)

    def test_crawler_asset_seed_dialog_schema_probe_entry_prefers_api_url(self) -> None:
        entry = crawler_seed_dialog_schema_probe_entry(
            {
                "api_url": "https://example.test/api.json",
                "landing_url": "https://example.test/page",
            }
        )

        self.assertEqual({"api_url": "https://example.test/api.json"}, entry)
        self.assertEqual(
            {"download_url": "https://example.test/page"},
            crawler_seed_dialog_schema_probe_entry({"landing_url": "https://example.test/page"}),
        )
        self.assertEqual({}, crawler_seed_dialog_schema_probe_entry({"title": "No URL"}))

    def test_open_selected_crawler_asset_seed_dialog_routes_favorite_action(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        payload = {
            "asset_id": "demo_index",
            "page": 2,
            "total": 1,
            "seeds": [{"dataset_uid": "demo_provider:seed_1", "title": "Seed 1", "favorite": False}],
        }
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.selected_crawler_asset = lambda: asset
        ui.tr = lambda zh, _en: zh
        ui.root = object()
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.crawler_asset_seed_pages = {"demo_index": payload}
        reloaded: list[tuple[str, int]] = []
        ui.load_crawler_asset_seed_page = lambda selected_asset, page=1: reloaded.append((selected_asset.asset_id, page))

        with (
            patch(
                "frontends.tk.crawler_asset_workflows.CrawlerAssetSeedDialog",
                return_value=SimpleNamespace(result={"action": "favorite", "dataset_uid": "demo_provider:seed_1", "favorite": True}),
            ),
            patch("frontends.tk.crawler_asset_workflows.save_crawler_seed_favorite", return_value={"asset_id": "demo_index"}) as save,
            patch("frontends.tk.crawler_asset_workflows.log_event") as event_log,
        ):
            CrawlerAssetWorkflowMixin.open_selected_crawler_asset_seed_dialog(ui)

        save.assert_called_once_with(asset_id="demo_index", dataset_uid="demo_provider:seed_1", favorite=True)
        event_log.assert_called_once()
        self.assertEqual([("demo_index", 2)], reloaded)
        self.assertIn("Seed 收藏已加入", ui.status_var.value)

    def test_open_selected_crawler_asset_seed_dialog_routes_schema_probe_action(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        payload = {
            "asset_id": "demo_index",
            "page": 1,
            "total": 1,
            "seeds": [{"dataset_uid": "demo_provider:seed_1", "title": "Seed 1", "api_url": "https://example.test/api.json"}],
        }
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.selected_crawler_asset = lambda: asset
        ui.tr = lambda zh, _en: zh
        ui.root = object()
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.crawler_asset_seed_pages = {"demo_index": payload}
        calls: list[tuple[str, str, dict[str, object]]] = []
        ui.run_crawler_asset_seed_schema_probe_from_ui = (
            lambda selected_asset, dataset_uid, entry: calls.append((selected_asset.asset_id, dataset_uid, entry))
        )

        with patch(
            "frontends.tk.crawler_asset_workflows.CrawlerAssetSeedDialog",
            return_value=SimpleNamespace(
                result={
                    "action": "schema_probe",
                    "dataset_uid": "demo_provider:seed_1",
                    "entry": {"api_url": "https://example.test/api.json"},
                }
            ),
        ):
            CrawlerAssetWorkflowMixin.open_selected_crawler_asset_seed_dialog(ui)

        self.assertEqual([("demo_index", "demo_provider:seed_1", {"api_url": "https://example.test/api.json"})], calls)

    def test_seed_schema_probe_worker_enriches_bounds_form_and_stores_payload(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )
        asset = crawler_asset_from_source(source)
        bounds_schema = asset.capabilities[2].bounds_schema
        payload = CrawlerAssetBoundPayload(
            asset_id="demo_stac",
            facet_values={"time": {"time_field": "created_at"}},
            field_values={"time_field": "created_at"},
            maps_to_values={"SourceDownloadBounds.time_field": "created_at"},
        )
        probe = SchemaProbeResult(
            status="ok",
            source_url="https://example.test/api.json",
            probe_url="https://example.test/api.json?$limit=5",
            row_count=1,
            columns=(SchemaProbeColumn("created_at", "2026-01-01", "date"), SchemaProbeColumn("value", "1", "integer")),
        )
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda zh, _en: zh
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.root = SimpleNamespace(after=lambda _delay, callback: callback())

        base_spec = build_crawler_asset_bound_form_spec("demo_stac", bounds_schema, source=source)
        service_result = CrawlerAssetSchemaProbeResult(
            asset_id="demo_stac",
            probe=probe,
            bound_form=apply_schema_probe_to_crawler_asset_bound_form_spec(base_spec, probe),
        )

        with (
            patch(
                "frontends.tk.crawler_asset_workflows.crawler_asset_bound_form_schema_probe_result",
                return_value=service_result,
            ) as schema_probe_service,
            patch("frontends.tk.crawler_asset_workflows.CrawlerAssetBoundDialog", return_value=SimpleNamespace(result=payload)) as dialog_class,
            patch("frontends.tk.crawler_asset_workflows.log_event") as event_log,
        ):
            CrawlerAssetWorkflowMixin._crawler_asset_seed_schema_probe_worker(
                ui,
                "demo_stac",
                "demo_provider:seed_1",
                {"api_url": "https://example.test/api.json"},
            )

        schema_probe_service.assert_called_once_with(
            "demo_stac",
            {"entry": {"api_url": "https://example.test/api.json"}, "row_limit": 5, "timeout": 8.0},
        )
        dialog_class.assert_called_once()
        spec = dialog_class.call_args.args[1]
        time_field = next(field for field in spec.fields if field.field_id == "time_field")
        self.assertIn("created_at", time_field.options)
        self.assertEqual(payload.to_dict(), ui.crawler_asset_bound_payloads["demo_stac"])
        event_log.assert_called_once()
        self.assertIn("已用 seed 欄位探測更新界域", ui.status_var.value)

    def test_run_crawler_asset_seed_download_import_starts_background_worker(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        payload = CrawlerAssetBoundPayload(asset_id="demo_index", facet_values={"limit": 5})
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.crawler_asset_bound_payloads = {"demo_index": payload.to_dict()}
        thread_call = SimpleNamespace(target=None, args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.target = target
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            CrawlerAssetWorkflowMixin.run_crawler_asset_seed_download_import_from_ui(
                ui,
                asset,
                dataset_uid="demo_provider:seed_1",
            )

        self.assertTrue(thread_call.started)
        self.assertEqual("demo_index", thread_call.args[0])
        self.assertEqual("demo_provider:seed_1", thread_call.args[1])
        self.assertIsInstance(thread_call.args[2], CrawlerAssetBoundPayload)
        self.assertEqual({"limit": 5}, thread_call.args[2].facet_values)
        self.assertIn("Downloading / importing seed", ui.status_var.value)

    def test_seed_background_jobs_are_single_flight_per_seed_action(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.crawler_asset_active_jobs = {("seed_download_import", "demo_index", "demo_provider:seed_1")}

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            CrawlerAssetWorkflowMixin.run_crawler_asset_seed_download_import_from_ui(
                ui,
                asset,
                dataset_uid="demo_provider:seed_1",
            )

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_seed_schema_probe_is_single_flight_per_seed(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_stac",
            provider_id="demo_provider",
            name="Demo STAC",
            source_type="stac_collections",
            endpoint_url="https://example.test/stac",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.crawler_asset_active_jobs = {("seed_schema_probe", "demo_stac", "demo_provider:seed_1")}

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            CrawlerAssetWorkflowMixin.run_crawler_asset_seed_schema_probe_from_ui(
                ui,
                asset,
                dataset_uid="demo_provider:seed_1",
                entry={"api_url": "https://example.test/api.json"},
            )

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_credential_dialog_payload_keeps_values_and_clear_flags_separate(self) -> None:
        payload = crawler_asset_credential_edit_payload(
            {"EARTHDATA_TOKEN": " token-secret ", "FRED_API_KEY": ""},
            {"EARTHDATA_TOKEN": True, "FRED_API_KEY": True},
            remember_local=False,
        )

        self.assertFalse(payload["remember_local"])
        self.assertEqual({"EARTHDATA_TOKEN": "token-secret"}, payload["values"])
        self.assertEqual(["FRED_API_KEY"], payload["clear"])

    def test_credential_dialog_next_action_uses_display_label_not_raw_id(self) -> None:
        label = crawler_asset_credential_next_action_text(
            {
                "display_profile": {
                    "next_action_label_zh_TW": "先完成登入設定，再下載資料",
                    "next_action_label_en": "Finish login settings before downloading",
                },
                "next_action": "edit_local_credentials_before_live_download",
            }
        )

        self.assertEqual("先完成登入設定，再下載資料", label)
        self.assertNotIn("edit_local_credentials_before_live_download", label)

    def test_seed_download_import_opens_credential_dialog_before_worker(self) -> None:
        source = DatasetDiscoverySource(
            source_id="earthdata_cmr",
            provider_id="demo_provider",
            name="Earthdata CMR",
            source_type="cmr_collections",
            endpoint_url="https://cmr.earthdata.nasa.gov/search/collections.json",
            credential_mode="user_credential_required",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda zh, _en: zh
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))

        with (
            patch("frontends.tk.background_jobs.threading.Thread") as thread_class,
            patch("frontends.tk.crawler_asset_workflows.CrawlerAssetCredentialDialog") as credential_dialog,
        ):
            credential_dialog.return_value = SimpleNamespace(result=None)
            CrawlerAssetWorkflowMixin.run_crawler_asset_seed_download_import_from_ui(
                ui,
                asset,
                dataset_uid="demo_provider:seed_1",
            )

        thread_class.assert_not_called()
        credential_dialog.assert_called_once()
        self.assertIn("Seed 下載已暫停", ui.status_var.value)

    def test_open_crawler_asset_credential_dialog_saves_through_backend(self) -> None:
        source = DatasetDiscoverySource(
            source_id="earthdata_cmr",
            provider_id="demo_provider",
            name="Earthdata CMR",
            source_type="cmr_collections",
            endpoint_url="https://cmr.earthdata.nasa.gov/search/collections.json",
            credential_mode="user_credential_required",
        )
        asset = crawler_asset_from_source(source)
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda zh, _en: zh
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))

        with (
            patch("frontends.tk.crawler_asset_workflows.CrawlerAssetCredentialDialog") as credential_dialog,
            patch("frontends.tk.crawler_asset_workflows.update_crawler_asset_credentials") as update_credentials,
            patch("frontends.tk.crawler_asset_workflows.log_event") as event_log,
        ):
            credential_dialog.return_value = SimpleNamespace(
                result={
                    "remember_local": True,
                    "values": {"EARTHDATA_TOKEN": "token-secret"},
                    "clear": [],
                }
            )
            update_credentials.return_value = {
                "status": "configured",
                "display_label": "已設定登入",
                "configured_count": 1,
                "field_count": 1,
                "fields": [
                    {
                        "env_var": "EARTHDATA_TOKEN",
                        "configured": True,
                        "value_preview": "****cret",
                    }
                ],
                "missing_required": [],
                "remember_local": True,
                "next_action": "continue_to_bounds_or_download_plan",
            }
            result = CrawlerAssetWorkflowMixin.open_selected_crawler_asset_credential_dialog(ui, asset)

        self.assertEqual("configured", result["status"])
        update_credentials.assert_called_once_with(asset, credential_dialog.return_value.result)
        event_log.assert_called_once()
        context = event_log.call_args.kwargs["context"]
        self.assertEqual("configured", context["status"])
        self.assertEqual(["EARTHDATA_TOKEN"], context["field_names"])
        self.assertNotIn("token-secret", json.dumps(context, ensure_ascii=False))
        self.assertIn("登入設定已儲存", ui.status_var.value)

    def test_crawler_asset_credential_event_context_masks_secret_values(self) -> None:
        source = DatasetDiscoverySource(
            source_id="earthdata_cmr",
            provider_id="demo_provider",
            name="Earthdata CMR",
            source_type="cmr_collections",
            endpoint_url="https://cmr.earthdata.nasa.gov/search/collections.json",
        )
        asset = crawler_asset_from_source(source)
        context = crawler_asset_credential_event_context(
            asset,
            {
                "status": "configured",
                "display_label": "已設定登入",
                "configured_count": 1,
                "field_count": 1,
                "fields": [{"env_var": "EARTHDATA_TOKEN", "value_preview": "****cret"}],
                "missing_required": [],
                "remember_local": True,
                "next_action": "continue_to_bounds_or_download_plan",
            },
        )

        self.assertEqual(["EARTHDATA_TOKEN"], context["field_names"])
        self.assertNotIn("****cret", json.dumps(context, ensure_ascii=False))

    def test_crawler_asset_credential_guard_message_uses_human_next_action_label(self) -> None:
        message = crawler_asset_credential_guard_message(
            {
                "display_label": "需要登入 / API Key",
                "display_profile": {
                    "label": "需要登入 / API Key",
                    "next_action_label_zh_TW": "先完成登入設定，再下載資料",
                    "next_action_label_en": "Finish login settings before downloading",
                },
                "provider_name": "NASA Earthdata",
                "missing_required": ["EARTHDATA_TOKEN"],
                "credential_entry_label": "開啟官方登入 / 申請 API Key",
                "next_action": "edit_local_credentials_before_live_download",
            },
            lambda zh, _en: zh,
        )

        self.assertIn("NASA Earthdata", message)
        self.assertIn("EARTHDATA_TOKEN", message)
        self.assertIn("先完成登入設定", message)
        self.assertNotIn("edit_local_credentials_before_live_download", message)

    def test_crawler_asset_credential_guard_message_hides_unknown_raw_next_action(self) -> None:
        message = crawler_asset_credential_guard_message(
            {
                "display_label": "需要登入 / API Key",
                "provider_name": "NASA Earthdata",
                "missing_required": ["EARTHDATA_TOKEN"],
                "next_action": "new_backend_credential_action",
            },
            lambda zh, _en: zh,
        )

        self.assertIn("檢查登入設定", message)
        self.assertNotIn("new_backend_credential_action", message)

    def test_crawler_seed_download_import_message_hides_unknown_raw_next_action(self) -> None:
        pipeline = SimpleNamespace(
            stage="blocked_before_download",
            succeeded=False,
            next_action="new_backend_download_action",
            to_dict=lambda: {
                "stage": "blocked_before_download",
                "succeeded": False,
                "next_action": "new_backend_download_action",
            },
        )
        plan_result = SimpleNamespace(
            blocked=True,
            blocked_reason="demo_block",
            outcome_bucket="blocked",
            direct_download_count=0,
            review_required_count=0,
            user_next_action="",
            resolved_plan={},
            to_dict=lambda: {"outcome_bucket": "blocked"},
        )
        result = SimpleNamespace(
            pipeline=pipeline,
            plan_result=plan_result,
            to_dict=lambda: {
                "stage": "blocked_before_download",
                "succeeded": False,
                "dataset_uid": "demo_seed",
                "next_action": "new_backend_download_action",
                "artifacts": {},
            },
        )

        message = crawler_seed_download_import_ui_message(result, lambda zh, _en: zh)

        self.assertIn("檢查下載 / 匯入結果", message.body)
        self.assertNotIn("new_backend_download_action", message.body)

    def test_seed_download_import_worker_uses_formal_service_and_local_download_root(self) -> None:
        fake_pipeline = SimpleNamespace(
            stage="download_import_completed",
            succeeded=True,
            next_action="",
            to_dict=lambda: {"stage": "download_import_completed", "succeeded": True},
        )
        fake_result = SimpleNamespace(
            asset_id="demo_index",
            dataset_uid="demo_provider:seed_1",
            pipeline=fake_pipeline,
            succeeded=True,
            to_dict=lambda: {
                "asset_id": "demo_index",
                "dataset_uid": "demo_provider:seed_1",
                "stage": "download_import_completed",
                "succeeded": True,
                "artifacts": {
                    "downloads_root": "downloads-root",
                    "curated_sqlite": "downloads-root/curated_sources.db",
                },
            },
        )
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda zh, _en: zh
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.root = SimpleNamespace(after=lambda _delay, callback: callback())
        ui._connect = lambda: SimpleNamespace(commit=lambda: None, close=lambda: None)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            with (
                patch("frontends.tk.crawler_asset_ui_helpers.default_local_downloads_root", return_value=tmp_root / "downloads"),
                patch("frontends.tk.crawler_asset_ui_helpers.state_file", return_value=tmp_root / "plans" / "seed.resolved.json"),
                patch("frontends.tk.crawler_asset_workflows.ApiCatalogRepository", return_value="repository") as repository_class,
                patch("frontends.tk.crawler_asset_workflows.run_crawler_seed_download_import", return_value=fake_result) as run_service,
                patch("frontends.tk.crawler_asset_workflows.log_event") as event_log,
                patch("frontends.tk.crawler_asset_workflows.messagebox.showinfo") as showinfo,
            ):
                CrawlerAssetWorkflowMixin._crawler_asset_seed_download_import_worker(
                    ui,
                    "demo_index",
                    "demo_provider:seed_1",
                    None,
                )

        repository_class.assert_called_once()
        run_service.assert_called_once()
        self.assertIn("downloads", str(run_service.call_args.args[3]))
        self.assertEqual("crawler_seed_download_import_completed", event_log.call_args.args[0])
        showinfo.assert_called_once()
        self.assertIn("Seed 下載 / 匯入完成", ui.status_var.value)

    def test_seed_download_import_finish_uses_human_next_action_label(self) -> None:
        class Var:
            value = ""

            def set(self, value: str) -> None:
                self.value = value

        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.tr = lambda zh, _en: zh
        ui.status_var = Var()
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

        with patch("frontends.tk.crawler_asset_workflows.messagebox.showwarning") as showwarning:
            CrawlerAssetWorkflowMixin._finish_crawler_asset_seed_download_import(ui, result)

        showwarning.assert_called_once()
        message = showwarning.call_args.args[1]
        self.assertIn("先處理 Adapter 審核或解析計畫，再下載", message)
        self.assertNotIn("run_adapter_review_or_resolve_adapter_plan_before_downloading", message)

    def test_crawler_asset_review_count_reads_resolved_plan(self) -> None:
        payload = {
            "providers": [
                {
                    "provider_id": "demo_provider",
                    "dataset_id": "demo_dataset",
                    "adapter_review": {
                        "adapter_id": "demo_adapter",
                        "required_action": "resolve_source_to_direct_download_entries",
                        "source_url": "https://example.test/catalog",
                    },
                    "download_eligibility": {"status": "adapter_required"},
                },
                {
                    "provider_id": "demo_provider",
                    "dataset_id": "direct_dataset",
                    "download_url": "https://example.test/data.csv",
                    "download_eligibility": {"status": "direct_download"},
                    "import_plan": {"status": "ready"},
                },
            ]
        }

        self.assertEqual(1, crawler_asset_review_count_from_plan(payload))
        self.assertEqual(0, crawler_asset_review_count_from_plan(None))

    def test_open_selected_crawler_asset_adapter_review_uses_current_resolved_plan(self) -> None:
        source = DatasetDiscoverySource(
            source_id="demo_index",
            provider_id="demo_provider",
            name="Demo file index",
            source_type="html_file_index",
            endpoint_url="https://example.test/data/",
        )
        asset = crawler_asset_from_source(source)
        payload = {
            "providers": [
                {
                    "provider_id": "demo_provider",
                    "dataset_id": "demo_dataset",
                    "adapter_review": {
                        "adapter_id": "demo_adapter",
                        "required_action": "resolve_source_to_direct_download_entries",
                        "source_url": "https://example.test/catalog",
                    },
                    "download_eligibility": {"status": "adapter_required"},
                }
            ]
        }
        ui = object.__new__(CrawlerAssetWorkflowMixin)
        ui.selected_crawler_asset = lambda: asset
        ui.crawler_asset_resolved_plans = {"demo_index": payload}
        ui.tr = lambda zh, _en: zh

        with patch("frontends.tk.crawler_asset_workflows.AdapterReviewDialog") as dialog_class:
            CrawlerAssetWorkflowMixin.open_selected_crawler_asset_adapter_review(ui)

        dialog_class.assert_called_once()
        self.assertIs(ui, dialog_class.call_args.args[0])
        self.assertEqual(1, len(dialog_class.call_args.args[1]))

    def test_crawler_asset_plan_outcomes_restore_from_events(self) -> None:
        payload = {
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
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = f"{tmpdir}/resolved.json"
            with open(plan_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            events = [
                {
                    "event": "crawler_asset_plan_outcome_recorded",
                    "context": {
                        "asset_id": "demo_index",
                        "outcome_label": "待 Adapter 1",
                        "plan_passport": {
                            "asset_id": "demo_index",
                            "has_resolved_plan": True,
                            "candidate_count": 3,
                            "direct_download_count": 1,
                            "review_required_count": 1,
                            "adapter_review_count": 1,
                            "content_review_count": 1,
                        },
                        "resolved_plan": plan_path,
                    },
                }
            ]
            ui = object.__new__(CrawlerAssetWorkflowMixin)
            with patch("frontends.tk.crawler_asset_workflows.latest_events", return_value=events):
                CrawlerAssetWorkflowMixin.load_crawler_asset_plan_outcomes_from_events(ui)

        self.assertEqual("待 Adapter 1", ui.crawler_asset_plan_outcomes["demo_index"])
        self.assertEqual("內容 Parser 待辦 1", ui.crawler_asset_content_review_outcomes["demo_index"])
        self.assertEqual(1, crawler_asset_review_count_from_plan(ui.crawler_asset_resolved_plans["demo_index"]))
        self.assertEqual(3, ui.crawler_asset_plan_passports["demo_index"]["candidate_count"])

    def test_crawler_asset_plan_passport_summary_uses_compact_counts(self) -> None:
        text = crawler_asset_plan_passport_summary_text(
            {
                "has_resolved_plan": True,
                "candidate_count": 3,
                "direct_download_count": 1,
                "review_required_count": 2,
                "adapter_review_count": 2,
                "content_review_count": 1,
                "blocked_credential_count": 0,
                "missing_provider_count": 1,
                "stale": True,
                "stale_reason": "asset_disabled",
                "stale_label": "資產已停用，啟用後重新建立下載計畫",
                "stale_next_action": "enable_before_building_download_plan",
                "stale_next_action_label": "先啟用爬蟲資產",
                "candidate_snapshot_changed": True,
            },
            lambda _zh, en: en,
        )

        self.assertIn("Plan Passport", text)
        self.assertIn("candidates 3", text)
        self.assertIn("direct 1", text)
        self.assertIn("review 2", text)
        self.assertIn("content 1", text)
        self.assertIn("missing providers 1", text)
        self.assertIn("stale 先啟用爬蟲資產", text)
        self.assertNotIn("enable_before_building_download_plan", text)
        self.assertIn("candidate snapshot changed", text)

        zh_text = crawler_asset_plan_passport_summary_text(
            {
                "has_resolved_plan": True,
                "candidate_count": 3,
                "direct_download_count": 1,
                "review_required_count": 2,
                "stale": True,
                "stale_reason": "asset_disabled",
                "stale_label": "資產已停用，啟用後重新建立下載計畫",
            },
            lambda zh, _en: zh,
        )
        self.assertIn("資產已停用，啟用後重新建立下載計畫", zh_text)
        self.assertNotIn("asset_disabled", zh_text)

    def test_crawler_asset_plan_passport_summary_tolerates_bad_event_counts(self) -> None:
        text = crawler_asset_plan_passport_summary_text(
            {
                "has_resolved_plan": False,
                "candidate_count": "not-a-number",
                "direct_download_count": None,
                "review_required_count": "2",
                "adapter_review_count": object(),
                "content_review_count": "",
            },
            lambda _zh, en: en,
        )

        self.assertIn("resolved plan unavailable", text)
        self.assertIn("candidates 0", text)
        self.assertIn("review 2", text)
        self.assertIn("adapter 0", text)

    def test_crawler_asset_plan_outcome_event_records_content_review_badge(self) -> None:
        result = SimpleNamespace(
            asset_id="demo_index",
            blocked=False,
            outcome_bucket="review_required",
            direct_download_count=0,
            review_required_count=1,
            user_next_action="open_adapter_review_or_adjust_bounds",
            resolved_plan={
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
            },
        )
        result.to_dict = lambda: {
            "run_record": {
                "record_key": "abc123def4567890",
                "stage": "download_plan_build",
                "status": "review",
                "outcome_bucket": "review_required",
                "next_action": "open_adapter_review_or_adjust_bounds",
            }
        }
        ui = object.__new__(CrawlerAssetWorkflowMixin)

        with patch("frontends.tk.crawler_asset_workflows.log_event") as event_log:
            CrawlerAssetWorkflowMixin.record_crawler_asset_plan_outcome(ui, result, 0, {"resolved": "state/demo.resolved.json"})

        context = event_log.call_args.kwargs["context"]
        self.assertEqual("內容 Parser 待辦 1", context["content_review_label"])
        self.assertEqual("內容 Parser 待辦 1", context["content_review"]["display_label"])
        self.assertEqual("review", context["content_review"]["display_tone"])
        self.assertEqual(1, context["content_review"]["count"])
        self.assertTrue(context["content_review"]["has_review"])
        self.assertEqual("demo_index", context["plan_passport"]["asset_id"])
        self.assertTrue(context["plan_passport"]["has_resolved_plan"])
        self.assertEqual(1, context["plan_passport"]["adapter_review_count"])
        self.assertEqual(1, context["plan_passport"]["content_review_count"])
        self.assertEqual("download_plan_build", context["run_record"]["stage"])
        self.assertEqual("review", context["run_record"]["status"])

    def test_crawler_asset_listing_outcome_event_records_run_record(self) -> None:
        result = CrawlerAssetListingResult(
            asset_id="demo_index",
            source_found=True,
            candidate_count=5,
            upserted_count=3,
            skipped_provider_count=1,
            duplicate_count=2,
            warning_count=1,
            next_action="review_candidates",
        )
        ui = object.__new__(CrawlerAssetWorkflowMixin)

        with patch("frontends.tk.crawler_asset_workflows.log_event") as event_log:
            CrawlerAssetWorkflowMixin.record_crawler_asset_listing_outcome(ui, result)

        event_log.assert_called_once()
        context = event_log.call_args.kwargs["context"]
        self.assertEqual("demo_index", context["asset_id"])
        self.assertEqual(5, context["candidate_count"])
        self.assertEqual(3, context["upserted_count"])
        self.assertEqual("crawler_listing", context["run_record"]["stage"])
        self.assertEqual("warning", context["run_record"]["status"])

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
        self.assertIn("樣本上限", ui.status_var.value)
        self.assertNotIn("sample_limit", ui.status_var.value)

    def test_plan_bounds_probe_uses_single_flight_job(self) -> None:
        ui = object.__new__(PlanWorkflowMixin)
        ui.cart_tree = SimpleNamespace(selection=lambda: ("plan-1",))
        ui.provider_id_for_plan_key = lambda _plan_key: "demo_provider"
        ui.row_by_provider_id = lambda _provider_id: SimpleNamespace(name="Demo provider")
        ui.plan_version_by_provider = {}
        entry = {"download_url": "https://example.test/data.csv"}
        ui.plan_entry_for_item = lambda _row, _option, plan_key="": (dict(entry), "")
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda _zh, en: en
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            PlanWorkflowMixin.configure_selected_plan_bounds_from_ui(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual(("plan-1", entry), thread_call.args)
        self.assertIn(("plan_bounds_probe", "plan-1", ""), ui.plan_bounds_active_jobs)
        self.assertIn("Probing dataset fields", ui.status_var.value)

    def test_plan_bounds_probe_is_single_flight_per_plan_item(self) -> None:
        ui = object.__new__(PlanWorkflowMixin)
        ui.cart_tree = SimpleNamespace(selection=lambda: ("plan-1",))
        ui.provider_id_for_plan_key = lambda _plan_key: "demo_provider"
        ui.row_by_provider_id = lambda _provider_id: SimpleNamespace(name="Demo provider")
        ui.plan_version_by_provider = {}
        ui.plan_entry_for_item = lambda _row, _option, plan_key="": ({"download_url": "https://example.test/data.csv"}, "")
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda _zh, en: en
        ui.plan_bounds_active_jobs = {("plan_bounds_probe", "plan-1", "")}

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            PlanWorkflowMixin.configure_selected_plan_bounds_from_ui(ui)

        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_plan_bounds_probe_blocks_when_probe_queue_full(self) -> None:
        ui = object.__new__(PlanWorkflowMixin)
        ui.cart_tree = SimpleNamespace(selection=lambda: ("plan-3",))
        ui.provider_id_for_plan_key = lambda _plan_key: "demo_provider"
        ui.row_by_provider_id = lambda _provider_id: SimpleNamespace(name="Demo provider")
        ui.plan_version_by_provider = {}
        ui.plan_entry_for_item = lambda _row, _option, plan_key="": ({"download_url": "https://example.test/data.csv"}, "")
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda _zh, en: en
        ui.plan_bounds_active_jobs = {
            ("plan_bounds_probe", "plan-1", ""),
            ("plan_bounds_probe", "plan-2", ""),
        }

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            PlanWorkflowMixin.configure_selected_plan_bounds_from_ui(ui)

        thread_class.assert_not_called()
        self.assertIn("at capacity", ui.status_var.value)

    def test_import_status_label_surfaces_content_parser_review(self) -> None:
        ui = object.__new__(ImportWorkflowMixin)
        ui.import_status_by_plan_key = {}
        ui.download_plan_entries_by_provider = {
            "plan-1": {
                "source_format": "netcdf",
                "import_plan": {
                    "status": "manual_review_required",
                    "source_format": "netcdf",
                    "content_parser": "scientific_grid_review",
                    "review_bucket": "content_parser_required",
                },
            }
        }
        ui.tr = lambda _zh, en: en

        self.assertEqual(
            "Content parser needed: netcdf / scientific_grid_review",
            ImportWorkflowMixin.import_status_label(ui, "plan-1"),
        )

    def test_import_supported_plan_results_uses_single_flight_job(self) -> None:
        ui = object.__new__(ImportWorkflowMixin)
        sqlite_path = Path("state/test_curated.sqlite")
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.selected_plan_items = lambda: [("plan-1", SimpleNamespace(name="Direct CSV"), None)]
        ui.plan_item_label = lambda _plan_key, row, _option=None: row.name
        ui.download_plan_entries_by_provider = {
            "plan-1": {
                "import_plan": {"status": "supported_after_download"},
                "download_url": "https://example.test/data.csv",
            }
        }
        ui.ask_import_existing_table_policy = lambda: "rename"
        ui.import_existing_table_policy_label = lambda _policy: "rename"
        ui.import_skipped_detail_message = lambda _skipped, limit=6: ""
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.import_workflows.curated_imports_path", return_value=sqlite_path), patch(
            "frontends.tk.import_workflows.messagebox.askyesno", return_value=True
        ), patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            ImportWorkflowMixin.import_supported_plan_results_from_ui(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual(sqlite_path, thread_call.args[1])
        self.assertEqual("rename", thread_call.args[2])
        self.assertIn(("sqlite_import", str(sqlite_path), ""), ui.import_active_jobs)
        self.assertIn("Importing 1 downloaded results", ui.status_var.value)

    def test_import_supported_plan_results_blocks_duplicate_sqlite_import(self) -> None:
        ui = object.__new__(ImportWorkflowMixin)
        sqlite_path = Path("state/test_curated.sqlite")
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.selected_plan_items = lambda: [("plan-1", SimpleNamespace(name="Direct CSV"), None)]
        ui.plan_item_label = lambda _plan_key, row, _option=None: row.name
        ui.download_plan_entries_by_provider = {
            "plan-1": {
                "import_plan": {"status": "supported_after_download"},
                "download_url": "https://example.test/data.csv",
            }
        }
        ui.import_active_jobs = {("sqlite_import", str(sqlite_path), "")}
        policy_calls: list[str] = []
        ui.ask_import_existing_table_policy = lambda: policy_calls.append("called") or "rename"

        with patch("frontends.tk.import_workflows.curated_imports_path", return_value=sqlite_path), patch(
            "frontends.tk.background_jobs.threading.Thread"
        ) as thread_class:
            ImportWorkflowMixin.import_supported_plan_results_from_ui(ui)

        thread_class.assert_not_called()
        self.assertEqual([], policy_calls)
        self.assertIn("already running", ui.status_var.value)

    def test_import_supported_plan_results_blocks_when_sqlite_import_queue_full(self) -> None:
        ui = object.__new__(ImportWorkflowMixin)
        sqlite_path = Path("state/test_curated.sqlite")
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.selected_plan_items = lambda: [("plan-1", SimpleNamespace(name="Direct CSV"), None)]
        ui.plan_item_label = lambda _plan_key, row, _option=None: row.name
        ui.download_plan_entries_by_provider = {
            "plan-1": {
                "import_plan": {"status": "supported_after_download"},
                "download_url": "https://example.test/data.csv",
            }
        }
        ui.import_active_jobs = {("sqlite_import", "state/other_curated.sqlite", "")}
        policy_calls: list[str] = []
        ui.ask_import_existing_table_policy = lambda: policy_calls.append("called") or "rename"

        with patch("frontends.tk.import_workflows.curated_imports_path", return_value=sqlite_path), patch(
            "frontends.tk.background_jobs.threading.Thread"
        ) as thread_class:
            ImportWorkflowMixin.import_supported_plan_results_from_ui(ui)

        thread_class.assert_not_called()
        self.assertEqual([], policy_calls)
        self.assertIn("already running", ui.status_var.value)

    def test_import_local_file_uses_single_flight_job(self) -> None:
        ui = object.__new__(ImportWorkflowMixin)
        sqlite_path = Path("state/test_curated.sqlite")
        ui.root = None
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.import_workflows.curated_imports_path", return_value=sqlite_path), patch(
            "frontends.tk.import_workflows.filedialog.askopenfilename", return_value="C:/tmp/data.csv"
        ), patch("frontends.tk.import_workflows.simpledialog.askstring", return_value="demo_table"), patch(
            "frontends.tk.import_workflows.messagebox.askyesno", return_value=True
        ), patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            ImportWorkflowMixin.import_local_file_from_ui(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual(Path("C:/tmp/data.csv"), thread_call.args[0])
        self.assertEqual(sqlite_path, thread_call.args[1])
        self.assertEqual("demo_table", thread_call.args[2])
        self.assertIn(("sqlite_import", str(sqlite_path), ""), ui.import_active_jobs)

    def test_import_local_file_blocks_duplicate_before_file_picker(self) -> None:
        ui = object.__new__(ImportWorkflowMixin)
        sqlite_path = Path("state/test_curated.sqlite")
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.import_active_jobs = {("sqlite_import", str(sqlite_path), "")}

        with patch("frontends.tk.import_workflows.curated_imports_path", return_value=sqlite_path), patch(
            "frontends.tk.import_workflows.filedialog.askopenfilename"
        ) as file_picker, patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            ImportWorkflowMixin.import_local_file_from_ui(ui)

        file_picker.assert_not_called()
        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_import_local_file_blocks_when_sqlite_import_queue_full_before_file_picker(self) -> None:
        ui = object.__new__(ImportWorkflowMixin)
        sqlite_path = Path("state/test_curated.sqlite")
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.import_active_jobs = {("sqlite_import", "state/other_curated.sqlite", "")}

        with patch("frontends.tk.import_workflows.curated_imports_path", return_value=sqlite_path), patch(
            "frontends.tk.import_workflows.filedialog.askopenfilename"
        ) as file_picker, patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            ImportWorkflowMixin.import_local_file_from_ui(ui)

        file_picker.assert_not_called()
        thread_class.assert_not_called()
        self.assertIn("already running", ui.status_var.value)

    def test_showcase_download_uses_single_flight_job(self) -> None:
        ui = object.__new__(ShowcaseWorkflowMixin)
        ui.root = None
        ui.tr = lambda _zh, en: en
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.open_showcase_download_progress_dialog = lambda destination, sample_limit: setattr(ui, "opened_progress", (destination, sample_limit))
        ui.download_policy = None
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.showcase_workflows.filedialog.askdirectory", return_value="C:/tmp/showcase"), patch(
            "frontends.tk.showcase_workflows.simpledialog.askinteger", return_value=25
        ), patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            ShowcaseWorkflowMixin.run_showcase_download_from_ui(ui)

        self.assertTrue(thread_call.started)
        self.assertEqual((Path("C:/tmp/showcase"), 25), thread_call.args)
        self.assertIn(("showcase_download", "bounded_public", ""), ui.showcase_active_jobs)
        self.assertTrue(ui.showcase_download_running)
        self.assertIn("limit 25", ui.status_var.value)

    def test_showcase_download_running_guard_does_not_prompt_for_folder(self) -> None:
        ui = object.__new__(ShowcaseWorkflowMixin)
        ui.root = None
        ui.tr = lambda _zh, en: en
        ui.showcase_download_running = True

        with patch("frontends.tk.showcase_workflows.messagebox.showinfo") as showinfo, patch(
            "frontends.tk.showcase_workflows.filedialog.askdirectory"
        ) as askdirectory, patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            ShowcaseWorkflowMixin.run_showcase_download_from_ui(ui)

        showinfo.assert_called_once()
        askdirectory.assert_not_called()
        thread_class.assert_not_called()

    def test_download_primary_action_label_reflects_selected_job_status(self) -> None:
        ui = object.__new__(DownloadWorkflowMixin)
        ui.download_primary_action_var = _FakeVar("")
        ui.download_tree = _FakeTree(("plan-1",))
        ui.cart_tree = _FakeTree(())
        ui.active_provider_id = "provider-1"
        ui.download_progress_by_provider = {}
        ui.tr = lambda zh, _en: zh

        DownloadWorkflowMixin.update_primary_download_action_label(ui)
        self.assertEqual("開始", ui.download_primary_action_var.value)

        ui.download_progress_by_provider["plan-1"] = DownloadProgress("job-1", "provider-1", JobStatus.RUNNING)
        DownloadWorkflowMixin.update_primary_download_action_label(ui)
        self.assertEqual("暫停", ui.download_primary_action_var.value)

        ui.download_progress_by_provider["plan-1"] = DownloadProgress("job-1", "provider-1", JobStatus.PAUSED)
        DownloadWorkflowMixin.update_primary_download_action_label(ui)
        self.assertEqual("繼續", ui.download_primary_action_var.value)

        ui.download_progress_by_provider["plan-1"] = DownloadProgress("job-1", "provider-1", JobStatus.COMPLETED)
        DownloadWorkflowMixin.update_primary_download_action_label(ui)
        self.assertEqual("開始", ui.download_primary_action_var.value)

    def test_download_primary_action_routes_to_pause_resume_or_start(self) -> None:
        ui = object.__new__(DownloadWorkflowMixin)
        ui.download_tree = _FakeTree(("plan-1",))
        ui.cart_tree = _FakeTree(())
        ui.active_provider_id = "provider-1"
        ui.download_progress_by_provider = {"plan-1": DownloadProgress("job-1", "provider-1", JobStatus.RUNNING)}
        calls: list[str] = []
        ui.pause_active_download = lambda: calls.append("pause")
        ui.resume_active_download = lambda: calls.append("resume")
        ui.start_download_plan = lambda: calls.append("start")

        DownloadWorkflowMixin.toggle_primary_download_action(ui)
        self.assertEqual(["pause"], calls)

        ui.download_progress_by_provider["plan-1"] = DownloadProgress("job-1", "provider-1", JobStatus.PAUSED)
        DownloadWorkflowMixin.toggle_primary_download_action(ui)
        self.assertEqual(["pause", "resume"], calls)

        ui.download_progress_by_provider.clear()
        DownloadWorkflowMixin.toggle_primary_download_action(ui)
        self.assertEqual(["pause", "resume", "start"], calls)

    def test_downloader_list_double_click_starts_selected_item_only(self) -> None:
        ui = object.__new__(DownloadWorkflowMixin)
        ui.cart_tree = _FakeTree(("plan-2",))
        ui.status_var = SimpleNamespace(value="", set=lambda value: setattr(ui.status_var, "value", value))
        ui.tr = lambda zh, _en: zh
        row_1 = SimpleNamespace(provider_id="provider-1")
        row_2 = SimpleNamespace(provider_id="provider-2")
        submitted: list[list[tuple[str, object, object | None]]] = []
        ui.selected_plan_items = lambda: [("plan-1", row_1, None), ("plan-2", row_2, "v2")]
        ui.start_download_plan_items = lambda items: submitted.append(items)

        DownloadWorkflowMixin.start_selected_download_plan_item(ui)

        self.assertEqual("plan-2", ui.active_provider_id)
        self.assertEqual([[("plan-2", row_2, "v2")]], submitted)

    def test_crawler_asset_profile_dialog_form_values_preserve_references(self) -> None:
        dialog = object.__new__(CrawlerAssetProfileDialog)
        dialog.bool_vars = {"enabled": SimpleNamespace(get=lambda: True), "archived": SimpleNamespace(get=lambda: False)}
        dialog.vars = {
            "credential_profile_id": _FakeVar("nasa_personal"),
            "api_key_env_var": _FakeVar("NASA_EARTHDATA_TOKEN"),
            "account_hint": _FakeVar("Earthdata login"),
            "schedule_policy": _FakeVar("manual"),
            "rate_limit_policy": _FakeVar("polite_1rps"),
            "retry_policy": _FakeVar("retry_3_backoff"),
            "seed_scope_policy": _FakeVar("bounded"),
            "status_note": _FakeVar("ready for bounded crawl"),
            "local_logo_path": _FakeVar("K:/logos/nasa.png"),
            "official_logo_url": _FakeVar("https://example.test/logo.png"),
            "favicon_url": _FakeVar("https://example.test/favicon.ico"),
            "logo_source": _FakeVar("official_site"),
            "logo_license_note": _FakeVar("local presentation only"),
        }

        values = dialog.form_values()

        self.assertTrue(values["enabled"])
        self.assertFalse(values["archived"])
        self.assertEqual("NASA_EARTHDATA_TOKEN", values["api_key_env_var"])
        self.assertEqual("K:/logos/nasa.png", values["local_logo_path"])

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
        with patch("frontends.tk.data_store_connection_settings_dialog.active_data_store_profile", return_value=SimpleNamespace(profile_id="mysql_local")):
            self.assertEqual("目前作用中 profile：mysql_local", dialog._active_profile_label())

        with patch("frontends.tk.data_store_connection_settings_dialog.active_data_store_profile", return_value=None):
            self.assertEqual("目前作用中 profile：-", dialog._active_profile_label())

    def test_developer_cli_split_command_preserves_quoted_arguments(self) -> None:
        # 開發者 CLI 允許輸入單行命令；quoted argument 必須維持為同一個 argv。
        self.assertEqual(
            ["python", "APIkeys_collection.py", "--summary", "hello world"],
            DeveloperCliDialog.split_command('python APIkeys_collection.py --summary "hello world"'),
        )

    def test_developer_cli_run_command_uses_single_flight_job(self) -> None:
        dialog = object.__new__(DeveloperCliDialog)
        dialog.command_var = _FakeVar('python APIkeys_collection.py --summary "hello world"')
        dialog.ui = SimpleNamespace(
            tr=lambda _zh, en: en,
            status_var=SimpleNamespace(value="", set=lambda value: setattr(dialog.ui.status_var, "value", value)),
        )
        outputs: list[str] = []
        dialog.set_output = lambda text: outputs.append(text)
        thread_call = SimpleNamespace(args=None, started=False)

        class FakeThread:
            def __init__(self, target, args, daemon):
                thread_call.args = args
                self.daemon = daemon

            def start(self):
                thread_call.started = True

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            DeveloperCliDialog.run_command(dialog)

        self.assertTrue(thread_call.started)
        self.assertEqual((["python", "APIkeys_collection.py", "--summary", "hello world"],), thread_call.args)
        self.assertIn(("developer_cli", "command", ""), dialog.developer_cli_active_jobs)
        self.assertEqual('$ python APIkeys_collection.py --summary "hello world"\n\n', outputs[0])
        self.assertIn("Running CLI", dialog.ui.status_var.value)

    def test_developer_cli_run_command_blocks_duplicate_without_clearing_output(self) -> None:
        dialog = object.__new__(DeveloperCliDialog)
        dialog.command_var = _FakeVar("python APIkeys_collection.py --summary")
        dialog.developer_cli_active_jobs = {("developer_cli", "command", "")}
        dialog.ui = SimpleNamespace(
            tr=lambda _zh, en: en,
            status_var=SimpleNamespace(value="", set=lambda value: setattr(dialog.ui.status_var, "value", value)),
        )
        outputs: list[str] = []
        dialog.set_output = lambda text: outputs.append(text)

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            DeveloperCliDialog.run_command(dialog)

        thread_class.assert_not_called()
        self.assertEqual([], outputs)
        self.assertIn("still running", dialog.ui.status_var.value)

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
            content_source_format="netcdf",
            content_family="scientific_grid_or_array",
            content_parser_id="scientific_grid_review",
            content_import_status="manual_review_required",
            content_review_bucket="content_parser_required",
            content_pipeline_lane="content_parser_review",
            content_next_action="add_content_parser_or_keep_raw_artifact",
            content_reason="NetCDF requires a dedicated parser.",
            reason="selector",
        )

        self.assertEqual(
            ("socrata", "解析 API，產生可下載 resources", "來源解析待辦", "nyc_open_data", "trees", "latest", "https://example.test/api"),
            AdapterReviewDialog.review_item_row_values(item),
        )
        detail = AdapterReviewDialog.review_item_detail_text(item)
        self.assertIn("adapter_id: socrata", detail)
        self.assertIn("outcome_bucket: 來源解析待辦", detail)
        self.assertIn("dataset_uid: abcd-1234", detail)
        self.assertIn("content_source_format: netcdf", detail)
        self.assertIn("content_parser_id: scientific_grid_review", detail)
        self.assertIn("content_import_status: 需內容 Parser review", detail)
        self.assertIn("content_review_bucket: 內容 Parser 待辦", detail)
        self.assertIn("content_pipeline_lane: 內容 Parser 待辦", detail)
        self.assertIn("required_action: 解析 API", detail)
        self.assertIn("content_next_action: 新增內容 Parser 或保留原始檔", detail)
        self.assertNotIn("resolve_api", detail)
        self.assertNotIn("source_resolution_required", detail)
        self.assertNotIn("content_parser_required", detail)
        self.assertNotIn("content_parser_review", detail)
        self.assertNotIn("add_content_parser_or_keep_raw_artifact", detail)
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
            ("待審核", "example_provider", "Example Dataset", "tabular", "CSV", "0.88"),
            DatasetCandidateReviewDialog.candidate_row_values(dataset),
        )
        detail = DatasetCandidateReviewDialog.candidate_detail_text(dataset, lambda zh, _en: zh)
        self.assertIn("標題: Example Dataset", detail)
        self.assertIn("審核狀態: 待審核", detail)
        self.assertNotIn("審核狀態: needs_review", detail)
        self.assertIn("來源: https://example.test/source.csv", detail)
        self.assertIn('"source_type": "ckan"', detail)


if __name__ == "__main__":
    unittest.main()
