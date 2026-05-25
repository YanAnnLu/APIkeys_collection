from __future__ import annotations

import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api_launcher.schema_probe import SchemaProbeColumn, SchemaProbeResult, json_schema_probe
from api_launcher.source_download import SourceDownloadBounds
from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload
from api_launcher.crawler_assets import crawler_asset_from_source
from api_launcher.crawlers.source_patterns import DEFAULT_PATTERN_MINIMUM_CONFIDENCE
from api_launcher.crawlers.types import DatasetDiscoverySource
from api_launcher.downloads.jobs import DownloadProgress, JobStatus
from frontends.tk import detail_panel_workflows as detail_panel_module
from frontends.tk.app_lifecycle_workflows import AppLifecycleWorkflowMixin
from api_launcher.bound_form import build_bound_form_spec, source_download_bounds_from_form_values
from frontends.tk.bound_form_dialog import DatasetBoundFormDialog
from frontends.tk.crawler_asset_bound_dialog import CrawlerAssetBoundDialog
from frontends.tk.crawler_asset_profile_dialog import CrawlerAssetProfileDialog
from frontends.tk.source_pattern_draft_dialog import SourcePatternDraftDialog
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
from frontends.tk.crawler_asset_workflows import (
    CrawlerAssetWorkflowMixin,
    crawler_asset_download_plan_summary_text,
    crawler_asset_plan_outcome_label,
    crawler_asset_review_count_from_plan,
)
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
            patch("frontends.tk.crawler_asset_workflows.threading.Thread", FakeThread),
        ):
            CrawlerAssetWorkflowMixin.prepare_selected_crawler_asset_download(ui)

        dialog_class.assert_called_once()
        self.assertEqual("demo_provider", ui.active_provider_id)
        self.assertEqual(payload.to_dict(), ui.crawler_asset_bound_payloads["demo_stac"])
        self.assertTrue(thread_call.started)
        self.assertEqual(("demo_stac", payload), thread_call.args)
        self.assertIn("Building download plan from crawler asset", ui.status_var.value)

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

        values = CrawlerAssetWorkflowMixin.crawler_asset_row_values(ui, asset)

        self.assertEqual("可下載 1", values[-1])

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
                        "resolved_plan": plan_path,
                    },
                }
            ]
            ui = object.__new__(CrawlerAssetWorkflowMixin)
            with patch("frontends.tk.crawler_asset_workflows.latest_events", return_value=events):
                CrawlerAssetWorkflowMixin.load_crawler_asset_plan_outcomes_from_events(ui)

        self.assertEqual("待 Adapter 1", ui.crawler_asset_plan_outcomes["demo_index"])
        self.assertEqual(1, crawler_asset_review_count_from_plan(ui.crawler_asset_resolved_plans["demo_index"]))

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
