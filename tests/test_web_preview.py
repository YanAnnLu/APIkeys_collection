from __future__ import annotations

import http.client
import json
import os
import socket
import threading
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
from api_launcher.crawler_asset_service import CrawlerAssetListingResult
from api_launcher.crawler_asset_profiles import (
    load_crawler_asset_profiles,
    set_crawler_asset_seed_favorite,
    update_crawler_asset_plan_passport,
    update_crawler_asset_profile,
)
from api_launcher.web_real_download_demo import (
    WEB_REAL_DEMO_TABLE,
    WEB_REAL_DEMO_URL,
    build_web_real_download_plan,
)
from api_launcher.local_credentials import read_env_values
from api_launcher.db import connect_db
from api_launcher.models import Dataset, Provider
from api_launcher.repository import ApiCatalogRepository
from frontends.web.server import build_web_preview_server, web_preview_runtime_status
from frontends.web.preview_api import (
    crawler_asset_cards,
    crawler_asset_credential_detail,
    crawler_asset_detail,
    crawler_asset_download_import,
    crawler_asset_listing,
    crawler_asset_plan_event_context,
    crawler_asset_plan_preview,
    crawler_asset_seed_page,
    crawler_seed_download_import,
    crawler_handler_smoke_diagnostics,
    developer_real_download_demo,
    save_crawler_asset_seed_favorite,
    save_crawler_asset_credentials,
    web_real_download_demo,
    web_preview_recent_events,
    web_preview_status,
)


class WebPreviewApiTest(unittest.TestCase):
    def test_status_declares_thin_uiux_surface(self) -> None:
        status = web_preview_status()

        self.assertEqual("web_preview", status["surface"])
        self.assertEqual("uiux_review", status["purpose"])
        self.assertEqual("api_launcher", status["business_logic_owner"])

    def test_crawler_handler_smoke_diagnostics_is_developer_only_and_compact(self) -> None:
        payload = crawler_handler_smoke_diagnostics()

        self.assertEqual("web_preview", payload["surface"])
        self.assertEqual("developer_diagnostics", payload["purpose"])
        self.assertEqual("crawler_handler_contract_smoke", payload["diagnostic_id"])
        self.assertTrue(payload["developer_only"])
        self.assertEqual("offline_contract_smoke_no_live_network", payload["scope"])
        summary = payload["summary"]
        self.assertIsInstance(summary, dict)
        self.assertIn("--dataset-discovery-handler-smoke-json", summary["command"])
        self.assertGreater(summary["supported_source_type_count"], 0)
        self.assertEqual("warning", summary["empty_case_status"])
        self.assertEqual("pass", summary["candidate_case_status"])
        self.assertNotIn("source_results", json.dumps(payload, ensure_ascii=False))

    def test_web_real_download_demo_plan_uses_public_csv_import_contract(self) -> None:
        with TemporaryDirectory() as tmp:
            payload = build_web_real_download_plan(downloads_root=Path(tmp) / "downloads", version="test-version")

        entry = payload["providers"][0]
        self.assertEqual("web_preview_real_public_csv_download", payload["plan_name"])
        self.assertEqual(WEB_REAL_DEMO_URL, entry["download_url"])
        self.assertEqual("direct_download", entry["download_eligibility"]["status"])
        self.assertEqual("csv", entry["source_format"])
        self.assertEqual("supported_after_download", entry["import_plan"]["status"])
        self.assertEqual("csv_to_sqlite", entry["import_plan"]["importer"])
        self.assertEqual(WEB_REAL_DEMO_TABLE, entry["import_plan"]["table_hint"])
        self.assertEqual("web_preview_real_download_demo", payload["source"]["kind"])

    def test_web_real_download_demo_endpoint_returns_payload_and_logs_event(self) -> None:
        fake_result = SimpleNamespace(
            to_dict=lambda: {
                "demo_id": "web_real_download_public_csv",
                "source_url": WEB_REAL_DEMO_URL,
                "stage": "download_import_completed",
                "succeeded": True,
                "row_count": 249,
                "table_name": WEB_REAL_DEMO_TABLE,
                "artifacts": {
                    "downloaded_file": "state/web_demo/downloads/data.csv",
                    "manifest": "state/web_demo/downloads/data.csv.manifest.json",
                    "curated_sqlite": "state/web_demo/web_real_download_curated.sqlite",
                },
                "next_action": "open_downloaded_file_or_review_sqlite_import",
            }
        )

        with patch("frontends.web.preview_api.run_web_real_download_demo", return_value=fake_result) as run_demo:
            with patch("frontends.web.preview_api.log_event") as log_event:
                payload = web_real_download_demo()

        run_demo.assert_called_once_with()
        self.assertTrue(payload["succeeded"])
        self.assertEqual(249, payload["row_count"])
        self.assertEqual(WEB_REAL_DEMO_TABLE, payload["table_name"])
        log_event.assert_called_once()
        event_name = log_event.call_args.args[0]
        context = log_event.call_args.kwargs["context"]
        self.assertEqual("web_real_download_demo_completed", event_name)
        self.assertTrue(context["succeeded"])
        self.assertEqual(249, context["row_count"])
        self.assertEqual("state/web_demo/downloads/data.csv", context["downloaded_file"])

    def test_developer_real_download_demo_is_explicitly_not_main_flow(self) -> None:
        fake_result = SimpleNamespace(
            to_dict=lambda: {
                "demo_id": "web_real_download_public_csv",
                "stage": "download_import_completed",
                "succeeded": True,
                "row_count": 3,
                "artifacts": {},
                "next_action": "open_downloaded_file_or_review_sqlite_import",
            }
        )

        with patch("frontends.web.preview_api.run_web_real_download_demo", return_value=fake_result):
            with patch("frontends.web.preview_api.log_event"):
                payload = developer_real_download_demo()

        self.assertTrue(payload["developer_only"])
        self.assertEqual("developer_diagnostic_public_csv_not_main_download_flow", payload["scope"])
        self.assertEqual("POST /api/crawler-assets/{asset_id}/download-import", payload["main_download_endpoint"])
        self.assertEqual("POST /api/crawler-assets/{asset_id}/seed-download-import", payload["seed_download_endpoint"])

    def test_real_download_demo_route_is_developer_diagnostic_only(self) -> None:
        with build_web_preview_server("127.0.0.1", 0, port_scan=0) as server:
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch(
                    "frontends.web.server.developer_real_download_demo",
                    return_value={
                        "developer_only": True,
                        "stage": "download_import_completed",
                        "succeeded": True,
                    },
                ) as demo:
                    conn = http.client.HTTPConnection(host, port, timeout=5)
                    conn.request("POST", "/api/diagnostics/real-download-demo", body="{}", headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    body = json.loads(response.read().decode("utf-8"))
                    conn.close()

                    legacy = http.client.HTTPConnection(host, port, timeout=5)
                    legacy.request("POST", "/api/demo/real-download", body="{}", headers={"Content-Type": "application/json"})
                    legacy_response = legacy.getresponse()
                    legacy_body = json.loads(legacy_response.read().decode("utf-8"))
                    legacy.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)

        demo.assert_called_once_with()
        self.assertEqual(200, response.status)
        self.assertTrue(body["developer_only"])
        self.assertEqual(404, legacy_response.status)
        self.assertEqual(404, legacy_body["status"])

    def test_crawler_asset_download_import_uses_formal_asset_service_and_logs_event(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)
            fake_plan_build = SimpleNamespace(
                candidate_count=1,
                candidate_snapshot_signature="candidate-demo",
                candidate_snapshot_count=1,
                upserted_candidate_count=1,
                selected_version_count=1,
                filtered_version_count=0,
                credential_gates=(),
                blocked_credential_count=0,
                missing_provider_ids=(),
            )
            fake_plan_result = SimpleNamespace(
                asset_id="demo_stac",
                outcome_bucket="ready_to_download",
                direct_download_count=1,
                review_required_count=0,
                blocked=False,
                blocked_reason="",
                user_next_action="open_downloader_and_start_or_pause_queue",
                next_action="",
                resolved_plan={"summary": {"direct_download_count": 1}},
                plan_build=fake_plan_build,
                candidate_snapshot_changed=False,
                bounds=SimpleNamespace(to_dict=lambda: {}),
                source_signature="source-demo",
                bounds_signature="bounds-demo",
                to_dict=lambda: {"asset_id": "demo_stac", "outcome_bucket": "ready_to_download"},
            )
            fake_pipeline = SimpleNamespace(
                stage="download_import_completed",
                succeeded=True,
                next_action="",
                to_dict=lambda: {"stage": "download_import_completed", "succeeded": True},
            )
            fake_result = SimpleNamespace(
                asset_id="demo_stac",
                plan_result=fake_plan_result,
                pipeline=fake_pipeline,
                succeeded=True,
                to_dict=lambda: {
                    "asset_id": "demo_stac",
                    "stage": "download_import_completed",
                    "succeeded": True,
                    "artifacts": {
                        "downloads_root": "state/web_preview/downloads/demo_stac",
                        "curated_sqlite": "state/web_preview/downloads/demo_stac/curated_sources.db",
                    },
                },
            )

            with patch("frontends.web.preview_api.run_crawler_asset_download_import", return_value=fake_result) as run_service:
                with patch("frontends.web.preview_api.log_event") as log_event:
                    payload = crawler_asset_download_import(
                        "demo_stac",
                        {},
                        db_path=Path(tmp) / "preview.sqlite",
                        downloads_root=Path(tmp) / "downloads",
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                    )

        run_service.assert_called_once()
        self.assertEqual("demo_stac", payload["asset_id"])
        self.assertEqual("download_import_completed", payload["download_import"]["stage"])
        self.assertEqual("ready_to_download", payload["plan_outcome"]["outcome_bucket"])
        self.assertEqual(1, payload["plan_passport"]["direct_download_count"])
        log_event.assert_called_once()
        self.assertEqual("crawler_asset_download_import_completed", log_event.call_args.args[0])
        context = log_event.call_args.kwargs["context"]
        self.assertTrue(context["succeeded"])
        self.assertEqual("download_import_completed", context["stage"])

    def test_crawler_seed_download_import_uses_selected_seed_and_logs_event(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)
            fake_plan_build = SimpleNamespace(
                candidate_count=1,
                candidate_snapshot_signature="candidate-seed",
                candidate_snapshot_count=1,
                upserted_candidate_count=0,
                selected_version_count=1,
                filtered_version_count=0,
                credential_gates=(),
                blocked_credential_count=0,
                missing_provider_ids=(),
            )
            fake_plan_result = SimpleNamespace(
                asset_id="demo_stac",
                outcome_bucket="ready_to_download",
                direct_download_count=1,
                review_required_count=0,
                blocked=False,
                blocked_reason="",
                user_next_action="open_downloader_and_start_or_pause_queue",
                next_action="",
                resolved_plan={"summary": {"direct_download_count": 1}},
                plan_build=fake_plan_build,
                candidate_snapshot_changed=False,
                bounds=SimpleNamespace(to_dict=lambda: {}),
                source_signature="source-demo",
                bounds_signature="bounds-demo",
                to_dict=lambda: {"asset_id": "demo_stac", "outcome_bucket": "ready_to_download"},
            )
            fake_pipeline = SimpleNamespace(
                stage="download_import_completed",
                succeeded=True,
                next_action="",
                to_dict=lambda: {"stage": "download_import_completed", "succeeded": True},
            )
            fake_result = SimpleNamespace(
                asset_id="demo_stac",
                dataset_uid="demo_provider:dataset_a",
                plan_result=fake_plan_result,
                pipeline=fake_pipeline,
                succeeded=True,
                to_dict=lambda: {
                    "asset_id": "demo_stac",
                    "dataset_uid": "demo_provider:dataset_a",
                    "stage": "download_import_completed",
                    "succeeded": True,
                    "artifacts": {
                        "downloads_root": "state/web_preview/downloads/demo_stac/demo_provider_dataset_a",
                        "curated_sqlite": "state/web_preview/downloads/demo_stac/demo_provider_dataset_a/curated_sources.db",
                    },
                },
            )

            with patch("frontends.web.preview_api.run_crawler_seed_download_import", return_value=fake_result) as run_service:
                with patch("frontends.web.preview_api.log_event") as log_event:
                    payload = crawler_seed_download_import(
                        "demo_stac",
                        {"dataset_uid": "demo_provider:dataset_a"},
                        db_path=Path(tmp) / "preview.sqlite",
                        downloads_root=Path(tmp) / "downloads",
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                    )

        run_service.assert_called_once()
        self.assertEqual("demo_stac", payload["asset_id"])
        self.assertEqual("demo_provider:dataset_a", payload["dataset_uid"])
        self.assertEqual("download_import_completed", payload["download_import"]["stage"])
        self.assertEqual("ready_to_download", payload["plan_outcome"]["outcome_bucket"])
        log_event.assert_called_once()
        self.assertEqual("crawler_seed_download_import_completed", log_event.call_args.args[0])
        context = log_event.call_args.kwargs["context"]
        self.assertEqual("demo_provider:dataset_a", context["dataset_uid"])
        self.assertTrue(context["succeeded"])

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
        self.assertEqual("資產已停用，啟用後重新建立下載計畫", passport["stale_label"])
        self.assertEqual("enable_before_building_download_plan", passport["stale_next_action"])
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
        result.to_dict = lambda: {
            "run_record": {
                "record_key": "abc123def4567890",
                "stage": "download_plan_build",
                "status": "review",
                "outcome_bucket": "review_required",
                "next_action": "open_adapter_review_or_adjust_bounds",
            }
        }

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
        self.assertEqual("download_plan_build", context["run_record"]["stage"])
        self.assertEqual("review", context["run_record"]["status"])

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
                    "run_record": {
                        "record_key": "abc123def4567890",
                        "stage": "download_plan_build",
                        "status": "review",
                        "outcome_bucket": "review_required",
                        "next_action": "open_adapter_review_or_adjust_bounds",
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
        self.assertEqual("download_plan_build", event["context_summary"]["run_record"]["stage"])
        self.assertEqual("review", event["context_summary"]["run_record"]["status"])
        self.assertEqual("內容 Parser 待辦 1", event["context_summary"]["content_review"]["display_label"])

    def test_web_preview_recent_events_keeps_listing_run_counts(self) -> None:
        events = [
            {
                "timestamp": "2026-05-26T11:00:00+08:00",
                "level": "warning",
                "event": "crawler_asset_listing_recorded",
                "component": "tk.crawler_assets",
                "message": "crawler listing recorded",
                "context": {
                    "asset_id": "demo_stac",
                    "source_found": True,
                    "blocked": False,
                    "candidate_count": 12,
                    "upserted_count": 9,
                    "skipped_provider_count": 1,
                    "duplicate_count": 2,
                    "error_count": 0,
                    "warning_count": 1,
                    "next_action": "review_candidates_or_build_plan",
                    "run_record": {
                        "record_key": "listing123456789",
                        "stage": "crawler_listing",
                        "status": "warning",
                        "outcome_bucket": "listing_warning",
                        "candidate_count": 12,
                        "direct_download_count": 0,
                        "review_required_count": 0,
                        "error_count": 0,
                        "warning_count": 1,
                        "duplicate_count": 2,
                        "candidate_snapshot_count": 12,
                        "next_action": "review_candidates_or_build_plan",
                    },
                    "resolved_plan": {"providers": [{"provider_id": "demo"}]},
                },
            }
        ]

        with patch("frontends.web.preview_api.latest_events", return_value=events):
            payload = web_preview_recent_events(limit=20)

        event = payload["events"][0]
        summary = event["context_summary"]
        self.assertEqual("crawler_asset_listing_recorded", event["event"])
        self.assertEqual("demo_stac", summary["asset_id"])
        self.assertEqual(12, summary["candidate_count"])
        self.assertEqual(9, summary["upserted_count"])
        self.assertEqual(1, summary["skipped_provider_count"])
        self.assertEqual(2, summary["duplicate_count"])
        self.assertEqual(1, summary["warning_count"])
        self.assertNotIn("resolved_plan", summary)
        self.assertEqual("crawler_listing", summary["run_record"]["stage"])
        self.assertEqual(12, summary["run_record"]["candidate_count"])
        self.assertEqual(2, summary["run_record"]["duplicate_count"])
        self.assertEqual(1, summary["run_record"]["warning_count"])

    def test_crawler_asset_listing_endpoint_records_event_payload(self) -> None:
        listing_result = CrawlerAssetListingResult(
            asset_id="demo_stac",
            source_found=True,
            listing_mode="complete_seed",
            candidate_count=3,
            upserted_count=2,
            skipped_provider_count=1,
            duplicate_count=1,
            warning_count=0,
            next_action="review_or_upsert_dataset_candidates",
            audit_summary={"status": "pass", "candidate_count": 3},
            max_results=1000,
            complete_seed=True,
        )
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)
            with patch("frontends.web.preview_api.run_crawler_asset_listing", return_value=listing_result) as run_listing:
                with patch("frontends.web.preview_api.log_event") as log_event:
                    payload = crawler_asset_listing(
                        "demo_stac",
                        db_path=Path(tmp) / "web-preview.sqlite",
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                    )

        run_listing.assert_called_once()
        listing_kwargs = run_listing.call_args.kwargs
        self.assertTrue(listing_kwargs["complete_seed"])
        self.assertEqual(1000, listing_kwargs["max_results"])
        self.assertEqual(0, listing_kwargs["max_pages"])
        self.assertEqual("demo_stac", payload["asset_id"])
        self.assertEqual("review_or_upsert_dataset_candidates", payload["next_action"])
        self.assertEqual(3, payload["listing_result"]["candidate_count"])
        self.assertEqual("complete_seed", payload["listing_options"]["listing_mode"])
        self.assertEqual(2, payload["listing_result"]["upserted_count"])
        self.assertEqual("within_current_limits", payload["listing_result"]["seed_enumeration"]["status"])
        self.assertEqual({"status": "pass", "candidate_count": 3}, payload["audit_summary"])
        log_event.assert_called_once()
        event_name = log_event.call_args.args[0]
        context = log_event.call_args.kwargs["context"]
        self.assertEqual("crawler_asset_listing_recorded", event_name)
        self.assertEqual("crawler_listing", context["run_record"]["stage"])
        self.assertEqual(3, context["candidate_count"])
        self.assertEqual("within_current_limits", context["seed_enumeration"]["status"])

    def test_crawler_asset_listing_blocks_missing_credentials_before_live_crawler(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_credential_source(tmp)
            env_path = Path(tmp) / ".env"
            with patch("frontends.web.preview_api.run_crawler_asset_listing") as run_listing:
                payload = crawler_asset_listing(
                    "demo_cmr",
                    db_path=Path(tmp) / "web-preview.sqlite",
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                    env_path=env_path,
                )

        run_listing.assert_not_called()
        self.assertEqual("edit_local_credentials_before_live_download", payload["next_action"])
        self.assertEqual("missing_credentials", payload["credential_guard"]["status"])
        self.assertTrue(payload["listing_result"]["blocked"])
        self.assertEqual("credential_setup_required", payload["listing_result"]["blocked_reason"])
        self.assertEqual("blocked", payload["listing_result"]["seed_enumeration"]["status"])

    def test_crawler_asset_seed_page_returns_first_50_then_more(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)
            db_path = Path(tmp) / "web-preview.sqlite"
            conn = connect_db(db_path)
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.upsert_provider(
                    Provider(
                        provider_id="demo_provider",
                        name="Demo Provider",
                        owner="Demo",
                        categories=("demo",),
                        geographic_scope="sample",
                        docs_url="https://example.test/docs",
                    )
                )
                for index in range(55):
                    repo.upsert_dataset(
                        Dataset(
                            dataset_uid=f"demo_provider:seed_{index:02d}",
                            provider_id="demo_provider",
                            dataset_id=f"seed_{index:02d}",
                            title=f"Seed {index:02d}",
                            categories=("demo",),
                            native_format="csv",
                            metadata={
                                "candidate_status": "needs_review",
                                "discovery_source_id": "demo_stac",
                                "discovery_source_type": "stac_collections",
                            },
                        )
                    )
            finally:
                conn.close()
            set_crawler_asset_seed_favorite("demo_stac", "demo_provider:seed_00", True, profile_path)

            page1 = crawler_asset_seed_page(
                "demo_stac",
                page=1,
                page_size=50,
                db_path=db_path,
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )
            page2 = crawler_asset_seed_page(
                "demo_stac",
                page=2,
                page_size=50,
                db_path=db_path,
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )

        self.assertEqual(55, page1["total"])
        self.assertEqual(50, len(page1["seeds"]))
        self.assertTrue(page1["has_more"])
        self.assertEqual("seed_00", page1["seeds"][0]["dataset_id"])
        self.assertEqual("demo_provider:seed_00", page1["seeds"][0]["favorite_key"])
        self.assertTrue(page1["seeds"][0]["favorite"])
        self.assertEqual(1, page1["favorite_seed_count"])
        self.assertEqual(5, len(page2["seeds"]))
        self.assertFalse(page2["has_more"])

    def test_save_crawler_asset_seed_favorite_persists_to_profile(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_source(tmp)

            saved = save_crawler_asset_seed_favorite(
                "demo_stac",
                {"dataset_uid": "demo_provider:seed_01", "favorite": True},
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )
            removed = save_crawler_asset_seed_favorite(
                "demo_stac",
                {"dataset_uid": "demo_provider:seed_01", "favorite": False},
                primary_path=source_path,
                local_path=local_path,
                profile_path=profile_path,
            )
            profiles = load_crawler_asset_profiles(profile_path)

        self.assertTrue(saved["favorite"])
        self.assertEqual(1, saved["favorite_seed_count"])
        self.assertFalse(removed["favorite"])
        self.assertEqual(0, removed["favorite_seed_count"])
        self.assertEqual((), profiles["demo_stac"].favorite_seed_uids)

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
        self.assertEqual(10, detail["bound_form"]["recommended_values"]["limit"])
        self.assertTrue(detail["bound_form"]["presets"])
        self.assertEqual("global", detail["bound_form"]["presets"][0]["preset_id"])
        self.assertIn("bbox_west", detail["bound_form"]["presets"][0]["values"])
        flow_step_ids = [step["step_id"] for step in detail["flow_steps"]]
        self.assertEqual(
            ["seed", "source_pattern", "bounds", "download_plan", "review_gate"],
            flow_step_ids,
        )
        self.assertEqual("Seed 註冊", detail["flow_steps"][0]["label"])

    def test_detail_surfaces_local_credential_status_without_secret_values(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_credential_source(tmp)
            env_path = Path(tmp) / ".env"

            with patch.dict(
                os.environ,
                {
                    "NASA_EARTHDATA_TOKEN": "",
                    "NASA_EARTHDATA_USERNAME": "",
                    "NASA_EARTHDATA_PASSWORD": "",
                },
                clear=False,
            ):
                detail = crawler_asset_detail(
                    "demo_cmr",
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                    env_path=env_path,
                )

        credentials = detail["card"]["credentials"]
        self.assertTrue(credentials["requires_credentials"])
        self.assertEqual("missing_credentials", credentials["status"])
        field_names = {field["env_var"] for field in credentials["fields"]}
        self.assertIn("NASA_EARTHDATA_TOKEN", field_names)
        self.assertIn("NASA_EARTHDATA_USERNAME", field_names)
        self.assertIn("NASA_EARTHDATA_PASSWORD", field_names)
        self.assertNotIn("token-secret", json.dumps(credentials, ensure_ascii=False))

    def test_save_crawler_asset_credentials_writes_local_env_and_masks_response(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_credential_source(tmp)
            env_path = Path(tmp) / ".env"

            with patch.dict(
                os.environ,
                {
                    "NASA_EARTHDATA_TOKEN": "",
                    "NASA_EARTHDATA_USERNAME": "",
                    "NASA_EARTHDATA_PASSWORD": "",
                },
                clear=False,
            ):
                status = save_crawler_asset_credentials(
                    "demo_cmr",
                    {
                        "values": {
                            "NASA_EARTHDATA_TOKEN": "token-secret-1234",
                            "NASA_EARTHDATA_USERNAME": "earth-user",
                            "NASA_EARTHDATA_PASSWORD": "earth-password",
                        }
                    },
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                    env_path=env_path,
                )
                env_values = read_env_values(env_path)
                refreshed = crawler_asset_credential_detail(
                    "demo_cmr",
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                    env_path=env_path,
                )

        self.assertEqual("configured", status["status"])
        self.assertEqual("configured", refreshed["status"])
        self.assertEqual("token-secret-1234", env_values["NASA_EARTHDATA_TOKEN"])
        self.assertEqual("earth-user", env_values["NASA_EARTHDATA_USERNAME"])
        self.assertEqual("earth-password", env_values["NASA_EARTHDATA_PASSWORD"])
        response_text = json.dumps(status, ensure_ascii=False)
        self.assertNotIn("token-secret-1234", response_text)
        self.assertNotIn("earth-password", response_text)
        previews = {field["env_var"]: field["value_preview"] for field in status["fields"]}
        self.assertTrue(previews["NASA_EARTHDATA_TOKEN"].endswith("1234"))
        self.assertNotIn("token-secret", previews["NASA_EARTHDATA_TOKEN"])

    def test_save_crawler_asset_credentials_can_remember_session_only(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_credential_source(tmp)
            env_path = Path(tmp) / ".env"

            with patch.dict(
                os.environ,
                {
                    "NASA_EARTHDATA_TOKEN": "",
                    "NASA_EARTHDATA_USERNAME": "",
                    "NASA_EARTHDATA_PASSWORD": "",
                },
                clear=False,
            ):
                status = save_crawler_asset_credentials(
                    "demo_cmr",
                    {
                        "values": {
                            "NASA_EARTHDATA_TOKEN": "session-token-1234",
                            "NASA_EARTHDATA_USERNAME": "session-user",
                            "NASA_EARTHDATA_PASSWORD": "session-password",
                        },
                        "remember_local": False,
                    },
                    primary_path=source_path,
                    local_path=local_path,
                    profile_path=profile_path,
                    env_path=env_path,
                )
                env_values = read_env_values(env_path)
                self.assertEqual("session-token-1234", os.environ["NASA_EARTHDATA_TOKEN"])

        self.assertEqual("configured", status["status"])
        self.assertFalse(status["remember_local"])
        self.assertEqual({}, env_values)

    def test_plan_preview_execute_blocks_missing_credentials_before_live_crawler(self) -> None:
        with TemporaryDirectory() as tmp:
            source_path, local_path, profile_path = write_preview_credential_source(tmp)
            env_path = Path(tmp) / ".env"

            with patch.dict(
                os.environ,
                {
                    "NASA_EARTHDATA_TOKEN": "",
                    "NASA_EARTHDATA_USERNAME": "",
                    "NASA_EARTHDATA_PASSWORD": "",
                },
                clear=False,
            ):
                with patch("frontends.web.preview_api.build_crawler_asset_download_plan") as build_plan:
                    payload = crawler_asset_plan_preview(
                        "demo_cmr",
                        {"limit": "5"},
                        execute=True,
                        primary_path=source_path,
                        local_path=local_path,
                        profile_path=profile_path,
                        env_path=env_path,
                    )

        build_plan.assert_not_called()
        self.assertEqual("edit_local_credentials_before_live_download", payload["next_action"])
        self.assertEqual("missing_credentials", payload["credential_guard"]["status"])
        self.assertEqual("credential_setup_required", payload["plan_outcome"]["outcome_bucket"])
        self.assertEqual("需要登入", payload["plan_passport"]["short_label"])
        self.assertFalse(payload["plan_passport"]["has_resolved_plan"])

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
        self.assertIn("planOutcomeLabel", combined)
        self.assertIn("boundPresetPanel", combined)
        self.assertIn("applyBoundPreset", combined)
        self.assertIn("credentialPanelHtml", combined)
        self.assertIn("credentialGuardBanner", combined)
        self.assertIn("credentialBlocksLivePlan", combined)
        self.assertIn("openCredentialEditorById", combined)
        self.assertIn("saveCredentialEditor", combined)
        self.assertIn("handleBuildPlanClick", combined)
        self.assertIn("applyRecommendedValuesSilently", combined)
        self.assertIn("runCrawlerAssetListingById", combined)
        self.assertIn("crawlerAssetDownloadButton", combined)
        self.assertIn("下載 / 匯入目前資產", combined)
        self.assertIn("/download-import", combined)
        self.assertNotIn("realDownloadDemoButton", combined)
        self.assertNotIn("執行真下載示範", combined)
        self.assertIn("/list-datasets", combined)
        self.assertIn("自動枚舉 seed", combined)
        self.assertIn("/seeds?page=", combined)
        self.assertIn("seed_enumeration", combined)
        self.assertIn("seed-limit-badge", combined)
        self.assertIn("顯示更多 seed", combined)
        self.assertIn("toggleSeedFavorite", combined)
        self.assertIn("/seed-favorites", combined)
        self.assertIn("rememberSeedFavorites", combined)
        self.assertIn("runCrawlerSeedDownloadImportById", combined)
        self.assertIn("/seed-download-import", combined)
        self.assertIn("下載此 seed", combined)
        self.assertNotIn("rrkal.favoriteSeeds", combined)
        self.assertIn("credentialLoginStepsHtml", combined)
        self.assertIn("credential_entry_url", combined)
        self.assertIn("先設定登入 / API Key", combined)
        self.assertIn("記住我的帳號", combined)
        self.assertIn("完成登入設定", combined)
        self.assertIn("file_index", combined)
        self.assertIn("map_service", combined)
        self.assertNotIn("buildPlanButton.disabled = !credentialBlocksLivePlan(credentials);", combined)
        self.assertNotIn("儲存到本機 .env", combined)
        self.assertNotIn("本機憑證", combined)
        self.assertIn("/credentials", combined)
        self.assertIn("快速界域", combined)
        self.assertIn("planPassportLabel", combined)
        self.assertIn("reviewOutcomeLabel", combined)
        self.assertNotIn("outcome.short_label || outcome.display_label || outcome.outcome_bucket", combined)
        self.assertNotIn("outcome.display_label || outcome.outcome_bucket", combined)
        self.assertIn("stalePassportLabel", combined)
        self.assertIn("stalePassportNextAction", combined)
        self.assertNotIn("passport.stale_label || passport.stale_reason", combined)
        self.assertNotIn("計畫需重建：${passport.stale_reason", combined)
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
        self.assertIn("bounds-preset-panel", styles)
        self.assertIn("credential-panel", styles)
        self.assertIn("credential-modal", styles)
        self.assertIn("credential-badge", styles)
        self.assertIn("credential-guard-banner", styles)
        self.assertIn("credential-remember-row", styles)
        self.assertIn("credential-login-steps", styles)
        self.assertIn("bounds-autofill-note", styles)
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
        self.assertIn("candidate_snapshot_changed", combined)
        self.assertIn("候選快照已變更", combined)
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
            candidate_snapshot_changed=True,
            bounds=SimpleNamespace(to_dict=lambda: {"candidate_limit": 1}),
            plan_build=SimpleNamespace(
                candidate_count=1,
                candidate_snapshot_signature="candidate-demo",
                candidate_snapshot_count=1,
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
        self.assertEqual("candidate-demo", passport["candidate_snapshot_signature"])
        self.assertEqual(1, passport["candidate_snapshot_count"])
        self.assertTrue(passport["candidate_snapshot_changed"])
        self.assertEqual(1, passport["direct_download_count"])
        self.assertNotIn("providers", passport)
        self.assertEqual(1, persisted_passport["candidate_count"])
        self.assertEqual("candidate-demo", persisted_passport["candidate_snapshot_signature"])
        self.assertEqual(1, persisted_passport["candidate_snapshot_count"])
        self.assertTrue(persisted_passport["candidate_snapshot_changed"])
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


def write_preview_credential_source(tmpdir: str) -> tuple[Path, Path, Path]:
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
                        "source_id": "demo_cmr",
                        "provider_id": "nasa_earthdata",
                        "name": "Demo CMR Earthdata",
                        "source_type": "cmr_collections",
                        "endpoint_url": "https://cmr.earthdata.nasa.gov/search/collections.json",
                        "docs_url": "https://www.earthdata.nasa.gov/learn/use-data/data-use-policy/api",
                        "search_terms": ["modis"],
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
