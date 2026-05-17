from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.download_plan_runner import run_download_plan_payload
from api_launcher.download_policy import PoliteDownloadPolicy
from api_launcher.repository import ApiCatalogRepository


PLAN_BYTES = b"download-plan-runner-payload"


class PlanRunnerHandler(BaseHTTPRequestHandler):
    request_count: int = 0

    def do_GET(self) -> None:
        self.__class__.request_count += 1
        self.send_response(200)
        self.send_header("Content-Length", str(len(PLAN_BYTES)))
        self.end_headers()
        self.wfile.write(PLAN_BYTES)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class HTTPServerFixture:
    def __enter__(self) -> str:
        PlanRunnerHandler.request_count = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PlanRunnerHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/sample.bin"

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class DownloadPlanRunnerTests(unittest.TestCase):
    def test_runner_downloads_direct_entries_and_registers_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture() as url:
            output_path = Path(tmpdir) / "downloads" / "sample.bin"
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()

                result = run_download_plan_payload(
                    sample_plan(url, output_path),
                    repo,
                    policy=PoliteDownloadPolicy(max_parallel_jobs=1, min_delay_per_host_seconds=0),
                    timeout=5,
                )
                manifests = repo.list_dataset_asset_manifests("hyg_database")
                assets = repo.managed_asset_records("hyg_database")
                payload_bytes = output_path.read_bytes()
                manifest_exists = output_path.with_suffix(".bin.manifest.json").exists()
            finally:
                conn.close()

        self.assertEqual(PLAN_BYTES, payload_bytes)
        self.assertTrue(manifest_exists)
        self.assertEqual(1, PlanRunnerHandler.request_count)
        self.assertEqual(2, result.entry_count)
        self.assertEqual(1, result.submitted)
        self.assertEqual(1, result.completed)
        self.assertEqual(0, result.failed)
        self.assertEqual(1, result.skipped)
        self.assertEqual(1, result.registered_assets)
        self.assertEqual(1, len(manifests))
        self.assertEqual("ok", manifests[0].status)
        self.assertEqual(1, len(assets))
        self.assertEqual("file", assets[0].asset_kind)

    def test_cli_runs_download_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture() as url:
            output_path = Path(tmpdir) / "downloads" / "sample.bin"
            plan_path = Path(tmpdir) / "plan.json"
            plan_path.write_text(json.dumps(sample_plan(url, output_path), ensure_ascii=False), encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--db",
                        str(Path(tmpdir) / "launcher.sqlite"),
                        "--init-db",
                        "--seed",
                        "--run-download-plan",
                        str(plan_path),
                        "--download-timeout",
                        "5",
                    ]
                )
            payload_bytes = output_path.read_bytes()

        self.assertEqual(0, rc)
        self.assertEqual(PLAN_BYTES, payload_bytes)
        self.assertIn("submitted=1 completed=1 failed=0 skipped=1 registered_assets=1", stdout.getvalue())


def sample_plan(url: str, output_path: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "providers": [
            {
                "provider_id": "hyg_database",
                "download_url": url,
                "target_path": str(output_path),
                "use_staging": True,
                "download_eligibility": {"status": "direct_download"},
                "dataset_version": {
                    "dataset_uid": "ds_test_hyg",
                    "dataset_id": "hyg_sample",
                    "version": "1.0",
                    "download_url": url,
                    "metadata": {"native_format": "bin"},
                },
            },
            {
                "provider_id": "gebco",
                "adapter_review_url": "https://download.gebco.net/downloads",
                "download_eligibility": {"status": "adapter_required"},
                "dataset_version": {
                    "dataset_uid": "ds_test_gebco",
                    "dataset_id": "gebco_selector",
                    "version": "2026",
                },
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
