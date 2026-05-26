from __future__ import annotations

import json
import socket
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from api_launcher.crawler_asset_display import (
    adapter_review_display_payload,
    crawler_asset_plan_outcome_payload,
    crawler_asset_plan_passport_payload,
    plan_entry_content_status_payload,
)
from api_launcher.crawler_asset_profiles import (
    load_crawler_asset_profiles,
    update_crawler_asset_plan_passport,
    update_crawler_asset_profile,
)
from frontends.web.server import build_web_preview_server, web_preview_runtime_status
from frontends.web.preview_api import (
    crawler_asset_cards,
    crawler_asset_detail,
    crawler_asset_plan_event_context,
    crawler_asset_plan_preview,
    web_preview_recent_events,
    web_preview_status,
)


class WebPreviewApiTest(unittest.TestCase):
    def test_status_declares_thin_uiux_surface(self) -> None:
        status = web_preview_status()

        self.assertEqual("web_preview", status["surface"])
        self.assertEqual("uiux_review", status["purpose"])
        self.assertEqual("api_launcher", status["business_logic_owner"])

    def test_server_runtime_status_reports_actual_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen(1)
            busy_port = blocker.getsockname()[1]

            with build_web_preview_server("127.0.0.1", busy_port, port_scan=3) as server:
                payload = web_preview_runtime_status(server)

        runtime = payload["server"]
        self.assertEqual(busy_port, runtime["requested_port"])
        self.assertNotEqual(busy_port, runtime["port"])
        self.assertTrue(runtime["port_scanned"])
        self.assertEqual(3, runtime["port_scan"])
        self.assertEqual(f"http://127.0.0.1:{runtime['port']}/", runtime["url"])

    def test_crawler_asset_cards_use_backend_asset_contract(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)

            payload = crawler_asset_cards(
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )

        self.assertEqual(1, payload["count"])
        card = payload["assets"][0]
        self.assertEqual("demo_stac", card["asset_id"])
        self.assertEqual("Demo STAC", card["display_name"])
        self.assertEqual("stac_collections", card["source_type"])
        self.assertTrue(card["capabilities"])
        self.assertEqual("抓取元資料", card["capabilities"][0]["display_label"])
        self.assertEqual({}, card["latest_plan_outcome"])
        self.assertEqual({}, card["latest_plan_passport"])

    def test_crawler_asset_cards_include_recent_plan_outcome_event(self) -> None:
        events = [
            {
                "event": "crawler_asset_plan_outcome_recorded",
                "context": {
                    "asset_id": "demo_stac",
                    "outcome_bucket": "review_required",
                    "outcome_label": "待 Adapter 1",
                    "review_required_count": 1,
                    "review_queue_count": 1,
                    "content_review": {
                        "display_label": "內容 Parser 待辦 1",
                        "display_tone": "review",
                        "count": 1,
                        "has_review": True,
                        "buckets": [],
                    },
                    "user_next_action": "open_adapter_review_or_adjust_bounds",
                },
            }
        ]
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)

            with patch("frontends.web.preview_api.latest_events", return_value=events):
                payload = crawler_asset_cards(
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                )

        outcome = payload["assets"][0]["latest_plan_outcome"]
        self.assertEqual("review_required", outcome["outcome_bucket"])
        self.assertEqual("待 Adapter 1", outcome["short_label"])
        self.assertEqual("review", outcome["display_tone"])
        self.assertEqual("內容 Parser 待辦 1", outcome["content_review"]["display_label"])

    def test_crawler_asset_cards_include_recent_compact_plan_passport_event(self) -> None:
        events = [
            {
                "event": "crawler_asset_plan_outcome_recorded",
                "context": {
                    "asset_id": "demo_stac",
                    "outcome_bucket": "partial_review_required",
                    "outcome_label": "可下載 1 / 待辦 1",
                    "plan_passport": {
                        "asset_id": "demo_stac",
                        "has_resolved_plan": True,
                        "outcome_bucket": "partial_review_required",
                        "short_label": "可下載 1 / 待辦 1",
                        "candidate_count": 3,
                        "direct_download_count": 1,
                        "review_required_count": 1,
                        "adapter_review_count": 1,
                        "content_review_count": 1,
                        "next_action": "open_downloader_and_start_or_pause_queue",
                        "bounds": {"candidate_limit": 3},
                        "providers": [{"provider_id": "demo"}],
                        "resolved_plan": {"providers": [{"provider_id": "demo"}]},
                    },
                },
            }
        ]
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)

            with patch("frontends.web.preview_api.latest_events", return_value=events):
                payload = crawler_asset_cards(
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                )
                detail = crawler_asset_detail(
                    "demo_stac",
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                )

        passport = payload["assets"][0]["latest_plan_passport"]
        detail_passport = detail["card"]["latest_plan_passport"]
        self.assertEqual("demo_stac", passport["asset_id"])
        self.assertTrue(passport["has_resolved_plan"])
        self.assertEqual(3, passport["candidate_count"])
        self.assertEqual(1, passport["direct_download_count"])
        self.assertEqual(1, passport["review_required_count"])
        self.assertEqual(1, passport["adapter_review_count"])
        self.assertEqual(1, passport["content_review_count"])
        self.assertEqual({"candidate_limit": 3}, passport["bounds"])
        self.assertEqual(passport, detail_passport)
        self.assertNotIn("providers", passport)
        self.assertNotIn("resolved_plan", passport)

    def test_crawler_asset_cards_prefer_profile_plan_passport_over_event_fallback(self) -> None:
        events = [
            {
                "event": "crawler_asset_plan_outcome_recorded",
                "context": {
                    "asset_id": "demo_stac",
                    "plan_passport": {
                        "asset_id": "demo_stac",
                        "candidate_count": 1,
                        "direct_download_count": 1,
                    },
                },
            }
        ]
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)
            update_crawler_asset_plan_passport(
                "demo_stac",
                {
                    "asset_id": "demo_stac",
                    "candidate_count": 7,
                    "direct_download_count": 2,
                    "adapter_review_count": 5,
                    "providers": [{"provider_id": "too_large"}],
                },
                profile_path,
            )

            with patch("frontends.web.preview_api.latest_events", return_value=events):
                payload = crawler_asset_cards(
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                )
                detail = crawler_asset_detail(
                    "demo_stac",
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                )

        passport = payload["assets"][0]["latest_plan_passport"]
        self.assertEqual(7, passport["candidate_count"])
        self.assertEqual(2, passport["direct_download_count"])
        self.assertFalse(passport["stale"])
        self.assertEqual("active", passport["profile_state"])
        self.assertEqual(5, detail["card"]["latest_plan_passport"]["adapter_review_count"])
        self.assertNotIn("providers", passport)

    def test_crawler_asset_cards_surface_stale_profile_plan_passport(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)
            update_crawler_asset_plan_passport(
                "demo_stac",
                {
                    "asset_id": "demo_stac",
                    "candidate_count": 3,
                    "direct_download_count": 1,
                },
                profile_path,
            )
            update_crawler_asset_profile("demo_stac", profile_path, enabled=False)

            payload = crawler_asset_cards(
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )

        passport = payload["assets"][0]["latest_plan_passport"]
        self.assertTrue(passport["stale"])
        self.assertEqual("asset_disabled", passport["stale_reason"])
        self.assertEqual("warning", passport["display_tone"])

    def test_web_plan_event_context_keeps_badge_payload_compact(self) -> None:
        result = SimpleNamespace(
            asset_id="demo_stac",
            outcome_bucket="review_required",
            direct_download_count=0,
            review_required_count=1,
            user_next_action="open_adapter_review_or_adjust_bounds",
            resolved_plan={"providers": [{"provider_id": "demo"}]},
        )

        context = crawler_asset_plan_event_context(
            result,
            {
                "outcome_bucket": "review_required",
                "short_label": "待 Adapter 1",
                "content_review_label": "內容 Parser 待辦 1",
                "content_review": {
                    "display_label": "內容 Parser 待辦 1",
                    "display_tone": "review",
                    "count": 1,
                    "has_review": True,
                    "buckets": [],
                },
            },
        )

        self.assertEqual("demo_stac", context["asset_id"])
        self.assertEqual("review_required", context["outcome_bucket"])
        self.assertEqual("待 Adapter 1", context["outcome_label"])
        self.assertEqual(1, context["review_queue_count"])
        self.assertEqual("內容 Parser 待辦 1", context["content_review"]["display_label"])
        self.assertEqual("", context["resolved_plan"])
        self.assertTrue(context["resolved_plan_available"])
        self.assertEqual({}, context["plan_passport"])

        context_with_passport = crawler_asset_plan_event_context(
            result,
            {"outcome_bucket": "review_required", "short_label": "待 Adapter 1"},
            plan_passport={
                "asset_id": "demo_stac",
                "candidate_count": 3,
                "providers": [{"provider_id": "demo"}],
                "resolved_plan": {"providers": []},
            },
        )

        self.assertEqual(3, context_with_passport["plan_passport"]["candidate_count"])
        self.assertNotIn("providers", context_with_passport["plan_passport"])
        self.assertNotIn("resolved_plan", context_with_passport["plan_passport"])

    def test_web_preview_recent_events_returns_bounded_summaries(self) -> None:
        events = [
            {
                "timestamp": "2026-05-26T10:00:00+08:00",
                "level": "info",
                "event": "crawler_asset_plan_outcome_recorded",
                "component": "crawler_asset_service",
                "message": "plan outcome recorded",
                "context": {
                    "asset_id": "demo_stac",
                    "outcome_bucket": "review_required",
                    "direct_download_count": 0,
                    "review_required_count": 1,
                    "resolved_plan": {"providers": [{"provider_id": "demo"}]},
                    "content_review": {
                        "display_label": "內容 Parser 待辦 1",
                        "display_tone": "review",
                        "count": 1,
                        "has_review": True,
                    },
                },
            }
        ]

        with patch("frontends.web.preview_api.latest_events", return_value=events) as latest_events:
            payload = web_preview_recent_events(limit=999)

        latest_events.assert_called_once_with(80)
        self.assertEqual(1, payload["count"])
        self.assertEqual(80, payload["limit"])
        event = payload["events"][0]
        self.assertEqual("crawler_asset_plan_outcome_recorded", event["event"])
        self.assertEqual("demo_stac", event["context_summary"]["asset_id"])
        self.assertEqual("review_required", event["context_summary"]["outcome_bucket"])
        self.assertNotIn("resolved_plan", event["context_summary"])
        self.assertEqual("內容 Parser 待辦 1", event["context_summary"]["content_review"]["display_label"])

    def test_plan_passport_summarizes_resolved_plan_without_copying_body(self) -> None:
        result = SimpleNamespace(
            asset_id="demo_stac",
            outcome_bucket="partial_review_required",
            direct_download_count=1,
            review_required_count=2,
            user_next_action="open_downloader_and_start_or_pause_queue",
            bounds=SimpleNamespace(to_dict=lambda: {"candidate_limit": 3}),
            plan_build=SimpleNamespace(
                candidate_count=3,
                upserted_candidate_count=2,
                selected_version_count=2,
                filtered_version_count=1,
                blocked_credential_count=0,
                credential_gates=(),
                missing_provider_ids=("missing_provider",),
            ),
            resolved_plan={
                "summary": {"direct_download_count": 1, "review_required_count": 2},
                "providers": [
                    {
                        "provider_id": "demo_provider",
                        "dataset_id": "demo_dataset",
                        "download_eligibility": {"status": "adapter_required"},
                        "adapter_review": {"source_url": "https://example.test/catalog"},
                        "content_parser": {
                            "parser_id": "scientific_grid_review",
                            "review_bucket": "content_parser_required",
                        },
                    }
                ],
            },
        )

        passport = crawler_asset_plan_passport_payload(
            result,
            plan_outcome=crawler_asset_plan_outcome_payload(result, added_count=1),
        )

        self.assertEqual("demo_stac", passport["asset_id"])
        self.assertTrue(passport["has_resolved_plan"])
        self.assertEqual("partial_review_required", passport["outcome_bucket"])
        self.assertEqual(3, passport["candidate_count"])
        self.assertEqual(1, passport["direct_download_count"])
        self.assertEqual(2, passport["review_required_count"])
        self.assertEqual(1, passport["adapter_review_count"])
        self.assertEqual(1, passport["content_review_count"])
        self.assertEqual(1, passport["missing_provider_count"])
        self.assertEqual({"candidate_limit": 3}, passport["bounds"])
        self.assertNotIn("providers", passport)

    def test_detail_returns_dynamic_bounds_form(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)

            detail = crawler_asset_detail(
                "demo_stac",
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )

        field_ids = [field["field_id"] for field in detail["bound_form"]["fields"]]
        self.assertEqual("demo_stac", detail["asset"]["asset_id"])
        self.assertIn("start_date", field_ids)
        self.assertIn("bbox_west", field_ids)
        self.assertIn("limit", field_ids)
        fields = {field["field_id"]: field for field in detail["bound_form"]["fields"]}
        self.assertEqual("起始日期", fields["start_date"]["display_label"])
        self.assertEqual("西界經度", fields["bbox_west"]["display_label"])
        group_display = {item["group"]: item for item in detail["bound_form"]["group_display"]}
        self.assertEqual("資料集選擇", group_display["DatasetBounds"]["display_label"])
        self.assertEqual("時間界域", group_display["TimeBounds"]["display_label"])
        self.assertEqual("空間界域", group_display["SpatialBounds"]["display_label"])
        flow_step_ids = [step["step_id"] for step in detail["flow_steps"]]
        self.assertEqual(
            ["seed", "source_pattern", "bounds", "download_plan", "review_gate"],
            flow_step_ids,
        )
        self.assertEqual("Seed 註冊", detail["flow_steps"][0]["label"])

    def test_detail_returns_separate_version_and_version_limit_form_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_file_index_source(tmp)

            detail = crawler_asset_detail(
                "demo_file_index",
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )

        fields = {field["field_id"]: field for field in detail["bound_form"]["fields"]}
        self.assertIn("version", fields)
        self.assertIn("version_limit", fields)
        self.assertEqual("", fields["version"]["default"])
        self.assertEqual(1, fields["version_limit"]["default"])
        self.assertEqual(("SourceDownloadOptions.selected_versions",), tuple(fields["version"]["maps_to"]))
        self.assertEqual(("SourceDownloadBounds.version_limit",), tuple(fields["version_limit"]["maps_to"]))
        group_display = {item["group"]: item for item in detail["bound_form"]["group_display"]}
        self.assertEqual("版本控制", group_display["VersionBounds"]["display_label"])
        self.assertIn("留空", group_display["VersionBounds"]["display_help"])

    def test_static_ui_uses_rrkal_product_vocabulary(self) -> None:
        web_root = Path(__file__).resolve().parents[1] / "frontends" / "web" / "static"
        combined = "\n".join(
            [
                (web_root / "index.html").read_text(encoding="utf-8"),
                (web_root / "app.js").read_text(encoding="utf-8"),
            ]
        )
        styles = (web_root / "styles.css").read_text(encoding="utf-8")

        self.assertIn("爬蟲資產", combined)
        self.assertIn("資產護照", combined)
        self.assertIn("後端流程狀態", combined)
        self.assertIn("抓取元資料", combined)
        self.assertIn("西界經度", combined)
        self.assertIn("contentReviewBadge", combined)
        self.assertIn("setContentReviewBadge", combined)
        self.assertIn("groupedBoundFields", combined)
        self.assertIn("serverRuntimeLabel", combined)
        self.assertIn("planBadgeHtml", combined)
        self.assertIn("latestPlanOutcomeForAsset", combined)
        self.assertIn("planOutcomePanelHtml", combined)
        self.assertIn("refreshSelectedAssetOutcomeViews", combined)
        self.assertIn("selectedAssetDetail.card.latest_plan_outcome", combined)
        self.assertIn('data-workspace="downloader"', combined)
        self.assertIn("downloaderQueue", combined)
        self.assertIn("reviewSummary", combined)
        self.assertIn("eventList", combined)
        self.assertIn("eventRefreshButton", combined)
        self.assertIn("showWorkspace", combined)
        self.assertIn("renderDownloaderWorkspace", combined)
        self.assertIn("loadRecentEvents", combined)
        self.assertIn("/api/events/recent", combined)
        self.assertIn("content-review-badge", styles)
        self.assertIn("bounds-group", styles)
        self.assertIn("plan-badge", styles)
        self.assertIn("plan-outcome-panel", styles)
        self.assertIn("plan-passport-panel", styles)
        self.assertIn("queue-grid", styles)
        self.assertIn("review-summary", styles)
        self.assertIn("event-row", styles)
        self.assertIn("@media (max-width: 980px)", styles)
        self.assertIn("中寬度仍要保留中文標籤", styles)
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr));", styles)
        self.assertIn("max-height: 220px", styles)
        self.assertIn("grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));", styles)
        self.assertNotIn("font-size: 0", styles)
        self.assertIn("assetPlanPassports", combined)
        self.assertIn("plan_passport", combined)
        self.assertNotIn("Mission Queue", combined)
        self.assertNotIn("Season Pass", combined)
        self.assertNotIn("Workshop", combined)

    def test_plan_preview_can_build_bounds_payload_without_executing_crawler(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)

            payload = crawler_asset_plan_preview(
                "demo_stac",
                {
                    "collection": "landsat-c2",
                    "time_field": "datetime",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "bbox_west": "120",
                    "bbox_south": "22",
                    "bbox_east": "122",
                    "bbox_north": "25",
                    "limit": "10",
                },
                execute=False,
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )

        self.assertFalse(payload["execute"])
        self.assertNotIn("plan_result", payload)
        bounds = payload["bounds_payload"]
        self.assertEqual("landsat-c2", bounds["facet_values"]["collection"])
        self.assertEqual((120.0, 22.0, 122.0, 25.0), bounds["facet_values"]["bbox"])
        self.assertEqual(10, bounds["facet_values"]["limit"])

    def test_plan_preview_execute_returns_compact_plan_passport(self) -> None:
        fake_result = SimpleNamespace(
            asset_id="demo_stac",
            outcome_bucket="ready_to_download",
            direct_download_count=1,
            review_required_count=0,
            user_next_action="open_downloader_and_start_or_pause_queue",
            next_action="download_ready",
            source_signature="source-demo",
            bounds_signature="bounds-demo",
            bounds=SimpleNamespace(to_dict=lambda: {"candidate_limit": 1}),
            plan_build=SimpleNamespace(
                candidate_count=1,
                upserted_candidate_count=1,
                selected_version_count=1,
                filtered_version_count=0,
                blocked_credential_count=0,
                credential_gates=(),
                missing_provider_ids=(),
            ),
            resolved_plan={"summary": {"direct_download_count": 1}, "providers": []},
        )
        fake_result.to_dict = lambda: {"asset_id": "demo_stac"}
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)
            with patch("frontends.web.preview_api.build_crawler_asset_download_plan", return_value=fake_result):
                with patch("frontends.web.preview_api.log_event"):
                    payload = crawler_asset_plan_preview(
                        "demo_stac",
                        {"limit": "1"},
                        execute=True,
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                    )
            profiles = load_crawler_asset_profiles(profile_path)

        passport = payload["plan_passport"]
        persisted_passport = profiles["demo_stac"].latest_plan_passport
        self.assertEqual("demo_stac", passport["asset_id"])
        self.assertTrue(passport["has_resolved_plan"])
        self.assertEqual(1, passport["candidate_count"])
        self.assertEqual(1, passport["direct_download_count"])
        self.assertNotIn("providers", passport)
        self.assertEqual(1, persisted_passport["candidate_count"])
        self.assertEqual(1, persisted_passport["direct_download_count"])
        self.assertEqual("source-demo", persisted_passport["source_signature"])
        self.assertEqual("bounds-demo", persisted_passport["bounds_signature"])
        self.assertNotIn("providers", persisted_passport)
        self.assertNotIn("resolved_plan", persisted_passport)

    def test_shared_display_schema_describes_plan_outcome(self) -> None:
        result = SimpleNamespace(
            blocked=False,
            outcome_bucket="partial_review_required",
            direct_download_count=1,
            review_required_count=2,
            user_next_action="open_downloader_and_start_or_pause_queue",
            next_action="adapter_review_required",
            blocked_reason="",
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

        payload = crawler_asset_plan_outcome_payload(result, added_count=1)

        self.assertEqual("partial_review_required", payload["outcome_bucket"])
        self.assertEqual("部分可下載", payload["display_label"])
        self.assertEqual("可下載 1 / 待辦 2", payload["short_label"])
        self.assertEqual("warning", payload["display_tone"])
        self.assertIn("仍有 2 筆需要 Adapter 審核", payload["summary"])
        self.assertEqual("前往下載器開始或暫停佇列", payload["next_action_label"])
        self.assertEqual("內容 Parser 待辦 1", payload["content_review_label"])
        self.assertEqual("內容 Parser 待辦 1", payload["content_review"]["display_label"])
        self.assertEqual("review", payload["content_review"]["display_tone"])
        self.assertEqual(1, payload["content_review"]["count"])
        self.assertTrue(payload["content_review"]["has_review"])

    def test_shared_display_schema_summarizes_adapter_review_outcomes(self) -> None:
        plan = {
            "providers": [
                {
                    "provider_id": "demo_provider",
                    "dataset_id": "demo_dataset",
                    "dataset_title": "Demo Dataset",
                    "download_eligibility": {"status": "adapter_required"},
                    "import_plan": {"status": "adapter_review_required"},
                    "adapter_review": {
                        "adapter_id": "demo_adapter",
                        "source_url": "https://example.test/catalog",
                        "required_action": "resolve_source_to_direct_download_entries",
                    },
                    "content_detection": {"source_format": "netcdf", "confidence": 0.8},
                    "content_parser": {
                        "source_format": "netcdf",
                        "content_family": "scientific_grid_or_array",
                        "import_status": "manual_review_required",
                        "parser_id": "scientific_grid_review",
                        "review_bucket": "content_parser_required",
                        "reason": "NetCDF requires a dedicated parser.",
                    },
                }
            ]
        }

        payload = adapter_review_display_payload(plan)

        self.assertEqual(1, payload["item_count"])
        self.assertEqual({"source_resolution_required": 1}, payload["by_outcome"])
        self.assertEqual("來源解析待辦", payload["outcomes"][0]["display_label"])
        self.assertEqual({"content_parser_required": 1}, payload["by_content_review_bucket"])
        self.assertEqual({"scientific_grid_review": 1}, payload["by_content_parser"])
        self.assertEqual("內容 Parser 待辦", payload["content_review_buckets"][0]["display_label"])
        self.assertEqual("scientific_grid_review", payload["content_parsers"][0]["parser_id"])

    def test_plan_entry_content_status_payload_labels_parser_review(self) -> None:
        payload = plan_entry_content_status_payload(
            {
                "source_format": "netcdf",
                "import_plan": {
                    "status": "manual_review_required",
                    "source_format": "netcdf",
                    "content_parser": "scientific_grid_review",
                    "review_bucket": "content_parser_required",
                    "reason": "NetCDF requires a dedicated parser.",
                },
            }
        )

        self.assertEqual("內容 Parser 待辦", payload["display_label"])
        self.assertEqual("review", payload["display_tone"])
        self.assertEqual("netcdf", payload["source_format"])
        self.assertEqual("scientific_grid_review", payload["parser_id"])

    def test_server_scans_next_port_when_preferred_port_is_busy(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen(1)
            busy_port = blocker.getsockname()[1]

            with build_web_preview_server("127.0.0.1", busy_port, port_scan=3) as server:
                actual_port = server.server_address[1]

        self.assertNotEqual(busy_port, actual_port)
        self.assertGreater(actual_port, busy_port)


def write_preview_source(tmpdir: str) -> tuple[Path, Path, Path]:
    root = Path(tmpdir)
    source_path = root / "sources.json"
    local_path = root / "missing-local-sources.json"
    profile_path = root / "missing-profiles.json"
    source_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_id": "demo_stac",
                        "provider_id": "demo_provider",
                        "name": "Demo STAC",
                        "source_type": "stac_collections",
                        "endpoint_url": "https://example.test/stac",
                        "search_terms": ["landsat"],
                        "categories": ["geospatial"],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return source_path, local_path, profile_path


def write_preview_file_index_source(tmpdir: str) -> tuple[Path, Path, Path]:
    root = Path(tmpdir)
    source_path = root / "sources.json"
    local_path = root / "missing-local-sources.json"
    profile_path = root / "missing-profiles.json"
    source_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_id": "demo_file_index",
                        "provider_id": "demo_provider",
                        "name": "Demo File Index",
                        "source_type": "html_file_index",
                        "endpoint_url": "https://example.test/files/",
                        "search_terms": ["csv"],
                        "categories": ["geospatial"],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return source_path, local_path, profile_path


if __name__ == "__main__":
    unittest.main()
