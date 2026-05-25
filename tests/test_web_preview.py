from __future__ import annotations

import json
import socket
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from api_launcher.crawler_asset_display import adapter_review_display_payload, crawler_asset_plan_outcome_payload
from frontends.web.server import build_web_preview_server
from frontends.web.preview_api import (
    crawler_asset_cards,
    crawler_asset_detail,
    crawler_asset_plan_preview,
    web_preview_status,
)


class WebPreviewApiTest(unittest.TestCase):
    def test_status_declares_thin_uiux_surface(self) -> None:
        status = web_preview_status()

        self.assertEqual("web_preview", status["surface"])
        self.assertEqual("uiux_review", status["purpose"])
        self.assertEqual("api_launcher", status["business_logic_owner"])

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
        flow_step_ids = [step["step_id"] for step in detail["flow_steps"]]
        self.assertEqual(
            ["seed", "source_pattern", "bounds", "download_plan", "review_gate"],
            flow_step_ids,
        )
        self.assertEqual("Seed 註冊", detail["flow_steps"][0]["label"])

    def test_static_ui_uses_rrkal_product_vocabulary(self) -> None:
        web_root = Path(__file__).resolve().parents[1] / "frontends" / "web" / "static"
        combined = "\n".join(
            [
                (web_root / "index.html").read_text(encoding="utf-8"),
                (web_root / "app.js").read_text(encoding="utf-8"),
            ]
        )

        self.assertIn("爬蟲資產", combined)
        self.assertIn("資產護照", combined)
        self.assertIn("後端流程狀態", combined)
        self.assertIn("抓取元資料", combined)
        self.assertIn("西界經度", combined)
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

    def test_shared_display_schema_describes_plan_outcome(self) -> None:
        result = SimpleNamespace(
            blocked=False,
            outcome_bucket="partial_review_required",
            direct_download_count=1,
            review_required_count=2,
            user_next_action="open_downloader_and_start_or_pause_queue",
            next_action="adapter_review_required",
            blocked_reason="",
        )

        payload = crawler_asset_plan_outcome_payload(result, added_count=1)

        self.assertEqual("partial_review_required", payload["outcome_bucket"])
        self.assertEqual("部分可下載", payload["display_label"])
        self.assertEqual("可下載 1 / 待辦 2", payload["short_label"])
        self.assertEqual("warning", payload["display_tone"])
        self.assertIn("仍有 2 筆需要 Adapter 審核", payload["summary"])
        self.assertEqual("前往下載器開始或暫停佇列", payload["next_action_label"])

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


if __name__ == "__main__":
    unittest.main()
