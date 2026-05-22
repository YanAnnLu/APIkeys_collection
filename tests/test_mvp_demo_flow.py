from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from api_launcher.adapter_plan_resolver import resolve_adapter_review_plan_payload
from api_launcher.core import main
from api_launcher.mvp_demo import (
    MVP_DEMO_DATASET_ID,
    MVP_DEMO_FLOW_ID,
    build_mvp_demo_review_plan,
    write_mvp_demo_flow,
)


class MvpDemoFlowTests(unittest.TestCase):
    def test_demo_review_plan_resolves_to_bounded_socrata_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = build_mvp_demo_review_plan(downloads_root=Path(tmpdir) / "downloads")
            resolved_payload, resolution = resolve_adapter_review_plan_payload(
                plan,
                downloads_root=Path(tmpdir) / "downloads",
            )

        self.assertEqual("canonical_mvp_demo_flow", plan["source"]["kind"])
        self.assertEqual(1, plan["summary"]["review_required_count"])
        self.assertEqual("adapter_required", plan["providers"][0]["download_eligibility"]["status"])
        self.assertEqual(1, resolution.resolved_review_entries)
        self.assertEqual(1, resolution.direct_entries_added)

        resolved_entry = resolved_payload["providers"][0]
        self.assertEqual("direct_download", resolved_entry["download_eligibility"]["status"])
        self.assertEqual("supported_after_download", resolved_entry["import_plan"]["status"])
        self.assertEqual("json", resolved_entry["source_format"])
        self.assertIn(f"/resource/{MVP_DEMO_DATASET_ID}.json", resolved_entry["download_url"])
        self.assertIn("$limit=25", resolved_entry["download_url"])
        self.assertEqual(MVP_DEMO_FLOW_ID, resolved_entry["mvp_demo"]["flow_id"])

    def test_cli_writes_demo_flow_manifest_and_review_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            flow_path = Path(tmpdir) / "flow.json"
            db_path = Path(tmpdir) / "launcher.sqlite"
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--init-db",
                        "--seed",
                        "--write-mvp-demo-flow",
                        str(flow_path),
                    ]
                )

            review_plan_path = flow_path.with_name("socrata_311.review.json")
            review_payload_path = flow_path.with_name("socrata_311.adapter_review.json")
            offline_plan_path = flow_path.with_name("socrata_311.offline_direct.json")
            offline_sample_path = flow_path.with_name("socrata_311.offline_sample.json")
            flow_payload = json.loads(flow_path.read_text(encoding="utf-8"))
            review_plan = json.loads(review_plan_path.read_text(encoding="utf-8"))
            review_payload = json.loads(review_payload_path.read_text(encoding="utf-8"))
            review_plan_exists = review_plan_path.exists()
            review_payload_exists = review_payload_path.exists()
            offline_plan = json.loads(offline_plan_path.read_text(encoding="utf-8"))
            offline_sample_exists = offline_sample_path.exists()

        self.assertEqual(0, rc)
        self.assertIn("[mvp-demo] wrote", output.getvalue())
        self.assertTrue(review_plan_exists)
        self.assertTrue(review_payload_exists)
        self.assertTrue(offline_sample_exists)
        self.assertEqual(MVP_DEMO_FLOW_ID, flow_payload["flow_id"])
        self.assertEqual(1, review_plan["summary"]["review_required_count"])
        self.assertEqual({"source_resolution_required": 1}, review_payload["summary"]["by_outcome"])
        self.assertEqual(1, offline_plan["summary"]["direct_download_count"])
        self.assertEqual("launcher.sqlite", Path(flow_payload["artifacts"]["launcher_db"]).name)
        self.assertEqual("socrata_311.review.json", Path(flow_payload["artifacts"]["review_plan"]).name)
        self.assertEqual("socrata_311.adapter_review.json", Path(flow_payload["artifacts"]["adapter_review_json"]).name)
        self.assertEqual("socrata_311.offline_direct.json", Path(flow_payload["artifacts"]["offline_direct_plan"]).name)
        self.assertTrue(any("--db" in item["command"] for item in flow_payload["commands"]))
        self.assertTrue(any("--write-adapter-review-json" in item["command"] for item in flow_payload["commands"]))
        self.assertTrue(any("--resolve-adapter-plan" in item["command"] for item in flow_payload["commands"]))
        self.assertTrue(any("--run-download-plan" in item["command"] for item in flow_payload["commands"]))

    def test_demo_offline_plan_can_download_and_import_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            flow_path = Path(tmpdir) / "flow.json"
            db_path = Path(tmpdir) / "launcher.sqlite"
            result = write_mvp_demo_flow(flow_path)
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--init-db",
                        "--seed",
                        "--run-download-plan",
                        str(result.offline_plan_path),
                        "--downloads-root",
                        str(result.downloads_root),
                        "--import-supported-plan-results",
                        "--import-sqlite-db",
                        str(result.import_sqlite_path),
                        "--plan-import-existing-table-policy",
                        "rename",
                    ]
                )

        self.assertEqual(0, rc)
        self.assertIn("submitted=1 completed=1", output.getvalue())
        self.assertIn("imported=1", output.getvalue())

    def test_cli_runs_demo_smoke_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            flow_path = Path(tmpdir) / "flow.json"
            db_path = Path(tmpdir) / "launcher.sqlite"
            output = io.StringIO()

            with redirect_stdout(output):
                rc = main(
                    [
                        "--db",
                        str(db_path),
                        "--init-db",
                        "--seed",
                        "--run-mvp-demo-smoke-json",
                        str(flow_path),
                    ]
                )

            payload = json.loads(output.getvalue())

        self.assertEqual(0, rc)
        self.assertTrue(payload["succeeded"])
        self.assertEqual("download_import_completed", payload["stage"])
        self.assertEqual("nyc_open_data_socrata_socrata_311_sample", payload["table_name"])
        self.assertEqual(3, payload["row_count"])
        self.assertEqual(1, payload["download_import"]["result"]["submitted"])
        self.assertEqual(1, payload["download_import"]["result"]["imported"])
        self.assertEqual("flow.json", Path(payload["artifacts"]["flow_manifest"]).name)


if __name__ == "__main__":
    unittest.main()
