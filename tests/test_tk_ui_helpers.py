import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api_launcher.paths import PROJECT_ROOT
from frontends.tk.crawler_asset_ui_helpers import (
    cache_crawler_asset_plan_state,
    crawler_asset_bound_payload_from_cache,
    crawler_asset_download_plan_built_event_context,
    crawler_asset_download_plan_bounds_schema,
    crawler_asset_detail_text,
    crawler_asset_listing_outcome_event_payload,
    crawler_asset_plan_outcome_event_payload,
    crawler_asset_recommended_seed_closure_event_context,
    crawler_asset_recommended_seed_closure_target_paths,
    crawler_asset_recommended_seed_closure_ui_message,
    crawler_seed_download_import_event_context,
    crawler_seed_schema_probe_event_context,
    crawler_seed_download_import_target_paths,
    crawler_seed_download_import_ui_message,
    write_crawler_asset_download_plan_artifacts,
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

    def test_recommended_seed_closure_target_paths_use_stable_seed_segment(self) -> None:
        with patch("frontends.tk.crawler_asset_ui_helpers.default_local_downloads_root", return_value=Path("C:/downloads")):
            targets = crawler_asset_recommended_seed_closure_target_paths("asset/demo")

        self.assertEqual(Path("C:/downloads/crawler_assets/asset_demo/recommended_seed_closure"), targets.downloads_root)
        self.assertEqual(targets.downloads_root / "curated_sources.db", targets.import_sqlite_path)

    def test_recommended_seed_closure_ui_message_hides_raw_next_action(self) -> None:
        result = SimpleNamespace(
            succeeded=False,
            closure_stage="no_recommended_seed",
            recommended_seed_uid="",
            download_import_result=None,
            to_dict=lambda: {
                "asset_id": "demo_index",
                "provider_id": "demo_provider",
                "closure_stage": "no_recommended_seed",
                "succeeded": False,
                "recommended_seed_uid": "",
                "next_action": "review_seed_page_or_adjust_source_listing",
                "next_action_label": "檢查 seed 清單或調整入口界域",
                "artifacts": {
                    "downloads_root": "downloads/demo",
                    "curated_sqlite": "downloads/demo/curated_sources.db",
                },
            },
        )

        message = crawler_asset_recommended_seed_closure_ui_message(result, lambda zh, _en: zh)

        self.assertFalse(message.succeeded)
        self.assertIn("檢查 seed 清單或調整入口界域", message.body)
        self.assertNotIn("review_seed_page_or_adjust_source_listing", message.body)

    def test_recommended_seed_closure_event_context_keeps_compact_seed_summary(self) -> None:
        result = SimpleNamespace(
            succeeded=False,
            closure_stage="no_recommended_seed",
            recommended_seed_uid="",
            download_import_result=None,
            to_dict=lambda: {
                "asset_id": "demo_index",
                "provider_id": "demo_provider",
                "closure_stage": "no_recommended_seed",
                "succeeded": False,
                "recommended_seed_uid": "",
                "next_action": "review_seed_page_or_adjust_source_listing",
                "seed_page": {
                    "total": 50,
                    "page": 1,
                    "page_size": 50,
                    "recommended_seed_uid": "",
                    "seeds": [{"dataset_uid": f"seed_{index}"} for index in range(50)],
                },
            },
        )

        context = crawler_asset_recommended_seed_closure_event_context(result)

        self.assertEqual("no_recommended_seed", context["closure_stage"])
        self.assertEqual({"total": 50, "page": 1, "page_size": 50, "recommended_seed_uid": ""}, context["seed_page_summary"])
        self.assertNotIn("seeds", context)

    def test_crawler_asset_download_plan_bounds_schema_uses_capability_contract(self) -> None:
        build_capability = SimpleNamespace(capability_id="build_download_plan", bounds_schema=("time", "bbox"))
        asset = SimpleNamespace(
            capabilities=(
                SimpleNamespace(capability_id="fetch_metadata", bounds_schema=("ignored",)),
                build_capability,
            )
        )

        self.assertEqual(("time", "bbox"), crawler_asset_download_plan_bounds_schema(asset))

    def test_crawler_asset_download_plan_bounds_schema_handles_missing_capability(self) -> None:
        asset = SimpleNamespace(capabilities=(SimpleNamespace(capability_id="fetch_metadata", bounds_schema=("ignored",)),))

        self.assertEqual((), crawler_asset_download_plan_bounds_schema(asset))

    def test_crawler_asset_detail_text_uses_maturity_and_risk_labels(self) -> None:
        asset = SimpleNamespace(
            display_name="Demo crawler",
            source_surface="catalog",
            source_type_label="CKAN package search",
            access_requirement="crawler_managed_auth",
            maturity="unbuilt",
            risk_tier="needs_handler",
            trust_score=10,
            seed_summary="0 seeds",
            capabilities=(
                SimpleNamespace(
                    capability_id="fetch_metadata",
                    label="元資料",
                    status="supported",
                    detail="ok",
                    bounds_schema=(),
                ),
            ),
            health=None,
            archived=False,
            enabled=True,
            capability_profile={"seed_scope_label": "入口列表"},
        )

        text = crawler_asset_detail_text(
            asset,
            last_plan_outcome="",
            content_review="",
            resolved_plan={},
            plan_passport={},
            credential_status={},
            tr=lambda zh, _en: zh,
        )

        self.assertIn("成熟度：待補 handler", text)
        self.assertIn("風險：待補 handler", text)
        self.assertIn("入口：資料目錄 / CKAN package search", text)
        self.assertIn("存取邊界：需登入 / API key", text)
        self.assertNotIn("unbuilt", text)
        self.assertNotIn("needs_handler", text)
        self.assertNotIn("catalog /", text)
        self.assertNotIn("crawler_managed_auth", text)

    def test_crawler_asset_bound_payload_from_cache_rehydrates_dict_payload(self) -> None:
        payload = crawler_asset_bound_payload_from_cache(
            {
                "demo_asset": {
                    "asset_id": "demo_asset",
                    "facet_values": {"limit": 25},
                    "field_values": {"limit": "25"},
                    "maps_to_values": {"SourceDownloadBounds.limit": 25},
                    "warning_codes": ["sample_scope"],
                }
            },
            "demo_asset",
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("demo_asset", payload.asset_id)
        self.assertEqual({"limit": 25}, payload.facet_values)
        self.assertEqual(("sample_scope",), payload.warning_codes)

    def test_crawler_asset_bound_payload_from_cache_preserves_dataclass_payload(self) -> None:
        cached = SimpleNamespace()
        from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload

        payload = CrawlerAssetBoundPayload(
            asset_id="demo_asset",
            facet_values={"limit": 25},
            field_values={},
            maps_to_values={},
            warning_codes=(),
        )

        self.assertIs(crawler_asset_bound_payload_from_cache({"demo_asset": payload}, "demo_asset"), payload)
        self.assertIsNone(crawler_asset_bound_payload_from_cache(cached, "demo_asset"))

    def test_crawler_asset_download_plan_built_event_context_is_compact(self) -> None:
        result = SimpleNamespace(direct_download_count=2, review_required_count=1)

        context = crawler_asset_download_plan_built_event_context(
            "demo_asset",
            result,
            {"resolved": "state/crawler_asset_plans/demo.resolved.json"},
        )

        self.assertEqual(
            {
                "asset_id": "demo_asset",
                "direct_download_count": 2,
                "review_required_count": 1,
                "resolved_plan": "state/crawler_asset_plans/demo.resolved.json",
            },
            context,
        )

    def test_cache_crawler_asset_plan_state_updates_display_caches(self) -> None:
        owner = SimpleNamespace()
        resolved_plan = {"entries": [{"url": "https://example.test/data.csv"}]}
        result = SimpleNamespace(
            asset_id="demo_asset",
            outcome_bucket="ready_to_download",
            direct_download_count=1,
            review_required_count=0,
            resolved_plan=resolved_plan,
            user_next_action="start_download_queue",
        )

        payload = cache_crawler_asset_plan_state(owner, result, 1)

        self.assertEqual(1, payload["added_count"])
        self.assertIn("demo_asset", owner.crawler_asset_plan_outcomes)
        self.assertIs(owner.crawler_asset_resolved_plans["demo_asset"], resolved_plan)
        self.assertTrue(owner.crawler_asset_plan_passports["demo_asset"]["has_resolved_plan"])

    def test_cache_crawler_asset_plan_state_clears_stale_optional_caches(self) -> None:
        owner = SimpleNamespace(
            crawler_asset_plan_outcomes={},
            crawler_asset_resolved_plans={"demo_asset": {"old": True}},
            crawler_asset_content_review_outcomes={"demo_asset": "內容 Parser 待辦 1"},
            crawler_asset_plan_passports={},
        )
        result = SimpleNamespace(
            asset_id="demo_asset",
            outcome_bucket="blocked",
            blocked=True,
            blocked_reason="missing credential",
            direct_download_count=0,
            review_required_count=0,
            resolved_plan=None,
            user_next_action="edit_local_credentials_before_live_download",
        )

        cache_crawler_asset_plan_state(owner, result, 0)

        self.assertNotIn("demo_asset", owner.crawler_asset_resolved_plans)
        self.assertNotIn("demo_asset", owner.crawler_asset_content_review_outcomes)
        self.assertFalse(owner.crawler_asset_plan_passports["demo_asset"]["has_resolved_plan"])

    def test_crawler_asset_plan_outcome_event_payload_adds_tk_artifact_fields(self) -> None:
        resolved_plan = {
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
        result = SimpleNamespace(
            asset_id="demo_asset",
            outcome_bucket="review_required",
            direct_download_count=0,
            review_required_count=1,
            resolved_plan=resolved_plan,
            user_next_action="open_adapter_review_or_adjust_bounds",
            to_dict=lambda: {
                "run_record": {
                    "stage": "download_plan_build",
                    "status": "review",
                    "outcome_bucket": "review_required",
                    "next_action": "open_adapter_review_or_adjust_bounds",
                }
            },
        )

        payload = crawler_asset_plan_outcome_event_payload(
            result,
            added_count=0,
            written_paths={"resolved": "state/demo.resolved.json"},
        )

        self.assertEqual("demo_asset", payload.asset_id)
        self.assertEqual("state/demo.resolved.json", payload.context["resolved_plan"])
        self.assertEqual(1, payload.context["review_queue_count"])
        self.assertEqual("demo_asset", payload.plan_passport["asset_id"])
        self.assertTrue(payload.plan_passport["has_resolved_plan"])

    def test_crawler_asset_listing_outcome_event_payload_keeps_preview_bounded(self) -> None:
        result = SimpleNamespace(
            asset_id="demo_index",
            listing_mode="complete_seed",
            source_found=True,
            blocked=False,
            candidate_count=1000,
            upserted_count=998,
            skipped_provider_count=0,
            duplicate_count=1,
            error_count=0,
            warning_count=1,
            next_action="review_or_upsert_dataset_candidates",
            max_results=1000,
            max_pages=10,
            complete_seed=True,
            search_scope="full",
            remote_pagination_status="has_more",
            remote_exhausted=False,
            remote_next_page_token="secret-token",
            to_dict=lambda: {
                "run_record": {
                    "stage": "listing",
                    "status": "warning",
                    "next_action": "review_or_upsert_dataset_candidates",
                }
            },
        )

        payload = crawler_asset_listing_outcome_event_payload(result)

        self.assertEqual("demo_index", payload.asset_id)
        self.assertEqual("has_more", payload.context["remote_pagination"]["status"])
        self.assertEqual("has_more", payload.preview["remote_pagination"]["status"])
        self.assertNotIn("secret-token", repr(payload.context))
        self.assertNotIn("secret-token", repr(payload.preview))

    def test_crawler_seed_schema_probe_event_context_is_bounded(self) -> None:
        probe = SimpleNamespace(to_dict=lambda: {"status": "ok", "columns": [{"name": "time"}]})
        spec = SimpleNamespace(schema_probe_required_count=1, warning_codes=("schema_probe_applied",))

        context = crawler_seed_schema_probe_event_context("demo_asset", "demo_seed", probe, spec)

        self.assertEqual("demo_asset", context["asset_id"])
        self.assertEqual("demo_seed", context["dataset_uid"])
        self.assertEqual("ok", context["probe"]["status"])
        self.assertEqual(1, context["schema_probe_required_count"])
        self.assertEqual(["schema_probe_applied"], context["warning_codes"])

    def test_crawler_seed_download_import_event_context_uses_structured_result(self) -> None:
        result = SimpleNamespace(
            pipeline=SimpleNamespace(
                stage="download_import_completed",
                to_dict=lambda: {"stage": "download_import_completed", "succeeded": True},
            ),
            succeeded=True,
            to_dict=lambda: {
                "artifacts": {
                    "downloads_root": "downloads/demo",
                    "curated_sqlite": "downloads/demo/curated_sources.db",
                }
            },
        )

        context = crawler_seed_download_import_event_context("demo_asset", "demo_seed", result)

        self.assertEqual("demo_asset", context["asset_id"])
        self.assertEqual("demo_seed", context["dataset_uid"])
        self.assertEqual("download_import_completed", context["stage"])
        self.assertTrue(context["succeeded"])
        self.assertEqual("downloads/demo", context["artifacts"]["downloads_root"])

    def test_write_crawler_asset_download_plan_artifacts_persists_utf8_json(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            def fake_state_file(relative_path: str) -> Path:
                return base / relative_path

            with patch("frontends.tk.crawler_asset_ui_helpers.state_file", side_effect=fake_state_file):
                paths = write_crawler_asset_download_plan_artifacts(
                    "demo asset",
                    {"title": "原始計畫"},
                    {"title": "解析後計畫"},
                )

            self.assertIn("original", paths)
            self.assertIn("resolved", paths)
            self.assertEqual({"title": "原始計畫"}, json.loads(Path(paths["original"]).read_text(encoding="utf-8")))
            self.assertEqual({"title": "解析後計畫"}, json.loads(Path(paths["resolved"]).read_text(encoding="utf-8")))

    def test_write_crawler_asset_download_plan_artifacts_skips_missing_plan_pair(self) -> None:
        self.assertEqual({}, write_crawler_asset_download_plan_artifacts("demo_asset", None, {"resolved": True}))

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
