from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from api_launcher.core import main
from api_launcher.project_maturity import (
    build_project_maturity_payload,
    maturity_display_profile,
    render_project_maturity_markdown,
)


class ProjectMaturityTests(unittest.TestCase):
    def assert_no_mojibake_fragments(self, value: object) -> None:
        damaged_fragments = (
            "\ufffd",
            chr(0x5687),
            chr(0x929D),
            chr(0x8763),
            chr(0x9708),
            chr(0x6470),
            chr(0x95AC),
            chr(0x876F),
        )

        if isinstance(value, str):
            for fragment in damaged_fragments:
                self.assertNotIn(fragment, value)
            for char in value:
                self.assertFalse(0xE000 <= ord(char) <= 0xF8FF, value)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                self.assert_no_mojibake_fragments(key)
                self.assert_no_mojibake_fragments(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                self.assert_no_mojibake_fragments(item)

    def test_project_maturity_payload_scopes_delivery_without_single_percent(self) -> None:
        with patch(
            "api_launcher.project_maturity.build_mvp_readiness_payload",
            return_value={
                "closure_id": "canonical_mvp_demo_closure",
                "closure_percent": 100,
                "status": "ready_for_mvp_demo",
                "scope": "bounded demo scope",
                "not_product_scope": "not whole product",
            },
        ):
            payload = build_project_maturity_payload(object())  # type: ignore[arg-type]

        self.assertNotIn("overall_percent", payload)
        self.assertIn("Do not report RRKAL progress as one percentage", payload["reporting_rule"])
        self.assertEqual(100, payload["canonical_delivery_scope"]["closure_percent"])
        self.assertEqual("可展示小閉環", payload["canonical_delivery_scope"]["status_label"])
        rows = {row["area_id"]: row for row in payload["rows"]}
        self.assertEqual("deliverable_100", rows["canonical_mvp_demo_closure"]["maturity_level"])
        self.assertEqual("partial_bounded", rows["provider_specific_deep_adapters"]["maturity_level"])
        self.assertEqual(3, rows["provider_specific_deep_adapters"]["metrics"]["dataset_adapter_count"])
        self.assertEqual("contract_only", rows["renderer_unreal_simulation"]["maturity_level"])
        self.assertEqual("🚧", rows["renderer_unreal_simulation"]["status_icon"])
        self.assertEqual("review", rows["renderer_unreal_simulation"]["display_tone"])
        scheduler_metrics = rows["background_jobs_and_scheduler"]["metrics"]
        self.assertTrue(scheduler_metrics["policy_registry_available"])
        self.assertGreaterEqual(scheduler_metrics["bounded_tk_policy_count"], 8)
        self.assertEqual(1, scheduler_metrics["max_active_jobs_by_policy"]["sqlite_import"])
        self.assertTrue(scheduler_metrics["sqlite_write_gate_available"])
        self.assertEqual(
            "process_per_sqlite_path",
            scheduler_metrics["sqlite_write_gate"]["scope"],
        )
        self.assertEqual(1, scheduler_metrics["sqlite_write_gate"]["max_active_writers_per_database"])
        self.assertTrue(scheduler_metrics["capacity_policy_call_site_guarded"])
        self.assertTrue(scheduler_metrics["direct_thread_spawn_guarded"])
        self.assertEqual("frontends/tk/background_jobs.py", scheduler_metrics["direct_thread_spawn_owner"])
        self.assertIn(
            "test_tk_single_flight_call_sites_use_capacity_policy",
            scheduler_metrics["guard_tests"]["capacity_policy_call_sites"],
        )
        self.assertIn(
            "test_tk_modules_do_not_spawn_threads_directly",
            scheduler_metrics["guard_tests"]["direct_thread_spawn_owner"],
        )
        crawler_metrics = rows["source_pattern_and_crawler_handlers"]["metrics"]
        self.assertGreater(crawler_metrics["supported_source_type_count"], 0)
        self.assertGreater(crawler_metrics["registry_matrix_cell_count"], 0)
        self.assertEqual(4, crawler_metrics["capability_address_width"])
        self.assertGreater(crawler_metrics["capability_address_group_count"], 0)
        self.assertEqual(
            crawler_metrics["supported_source_type_count"],
            crawler_metrics["seed_scope_counts"]["entry_listing"]
            + crawler_metrics["seed_scope_counts"]["paginated_catalog"],
        )
        self.assertEqual("api_launcher.crawlers.registry", crawler_metrics["dispatch_owner"])
        import_metrics = rows["content_parser_and_import"]["metrics"]
        self.assertEqual(("csv_to_sqlite", "json_to_sqlite"), tuple(import_metrics["supported_sqlite_importers"]))
        self.assertEqual(1, import_metrics["compatibility_shim_count"])
        self.assertEqual("scoped_importer_boundary", import_metrics["compatibility_shim_runtime_scope"])
        self.assertFalse(import_metrics["global_monkeypatch"])
        self.assertEqual(
            "external_table_shape_normalizer",
            import_metrics["compatibility_shims"][0]["shim_id"],
        )

    def test_project_maturity_payload_and_markdown_do_not_contain_mojibake(self) -> None:
        with patch(
            "api_launcher.project_maturity.build_mvp_readiness_payload",
            return_value={
                "closure_id": "canonical_mvp_demo_closure",
                "closure_percent": 100,
                "status": "ready_for_mvp_demo",
                "scope": "bounded demo scope",
                "not_product_scope": "not whole product",
            },
        ):
            payload = build_project_maturity_payload(object())  # type: ignore[arg-type]

        self.assert_no_mojibake_fragments(payload)
        self.assert_no_mojibake_fragments(render_project_maturity_markdown(payload))

    def test_project_maturity_markdown_renders_matrix_without_claiming_all_done(self) -> None:
        payload = {
            "matrix_version": "test",
            "reporting_rule": "Use matrix.",
            "why_no_single_percent": "No single percent.",
            "canonical_delivery_scope": {
                "closure_id": "canonical_mvp_demo_closure",
                "closure_percent": 100,
                "status": "ready_for_mvp_demo",
                "status_label": "可展示小閉環",
                "scope": "bounded",
                "not_product_scope": "not all",
            },
            "rows": [
                {
                    "area_label": "Renderer",
                    "maturity_level": "contract_only",
                    "maturity_label_zh_TW": "合約 / planned",
                    "deliverable_scope": "contract",
                    "current_limitations": ["no real I/O"],
                    "next_actions": ["implement real I/O"],
                }
            ],
        }

        markdown = render_project_maturity_markdown(payload)

        self.assertIn("# RRKAL Project Maturity Matrix", markdown)
        self.assertIn("closure_percent: 100", markdown)
        self.assertIn("status_label: 可展示小閉環", markdown)
        self.assertIn("🚧 合約 / planned", markdown)
        self.assertIn("合約 / planned", markdown)
        self.assertIn("no real I/O", markdown)

    def test_maturity_display_profile_marks_contract_work_as_construction(self) -> None:
        self.assertEqual(
            {
                "status_icon": "🚧",
                "display_tone": "review",
                "display_label": "施工中 / 合約",
            },
            maturity_display_profile("contract_only"),
        )

    def test_cli_emits_project_maturity_json_without_human_setup_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with patch(
                "api_launcher.core.build_project_maturity_payload",
                return_value={
                    "matrix_version": "test",
                    "reporting_rule": "Use matrix.",
                    "rows": [],
                    "canonical_delivery_scope": {"closure_percent": 100},
                },
            ):
                with redirect_stdout(stdout):
                    rc = main(
                        [
                            "--db",
                            str(Path(tmpdir) / "launcher.sqlite"),
                            "--init-db",
                            "--seed",
                            "--project-maturity-json",
                        ]
                    )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(0, rc)
        self.assertEqual("test", payload["matrix_version"])
        self.assertEqual(100, payload["canonical_delivery_scope"]["closure_percent"])
        self.assertNotIn("[db]", stdout.getvalue())
        self.assertNotIn("[seed]", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
