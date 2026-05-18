from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from api_launcher.core import main
from api_launcher.db import connect_db
from api_launcher.downloads.plan_runner import run_download_plan_payload
from api_launcher.downloads.policy import PoliteDownloadPolicy
from api_launcher.repository import ApiCatalogRepository


PLAN_BYTES = b"download-plan-runner-payload"
CSV_BYTES = b"name,value\nalpha,1\nbeta,2\n"


def zip_csv_bytes() -> bytes:
    handle = io.BytesIO()
    with zipfile.ZipFile(handle, "w") as archive:
        archive.writestr("nested/sample.csv", CSV_BYTES)
    return handle.getvalue()


class PlanRunnerHandler(BaseHTTPRequestHandler):
    request_count: int = 0
    payload: bytes = PLAN_BYTES

    def do_GET(self) -> None:
        self.__class__.request_count += 1
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.__class__.payload)))
        self.end_headers()
        self.wfile.write(self.__class__.payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class HTTPServerFixture:
    def __init__(self, payload: bytes = PLAN_BYTES):
        self.payload = payload

    def __enter__(self) -> str:
        PlanRunnerHandler.request_count = 0
        PlanRunnerHandler.payload = self.payload
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PlanRunnerHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/sample.bin"

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        PlanRunnerHandler.payload = PLAN_BYTES


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

    def test_cli_can_import_supported_plan_results_after_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture(CSV_BYTES) as url:
            output_path = Path(tmpdir) / "downloads" / "sample.csv"
            plan_path = Path(tmpdir) / "plan.json"
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            plan_path.write_text(json.dumps(sample_plan(url, output_path, native_format="csv"), ensure_ascii=False), encoding="utf-8")
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
                        "--import-supported-plan-results",
                        "--import-sqlite-db",
                        str(sqlite_path),
                    ]
                )
            conn = sqlite3.connect(sqlite_path)
            try:
                rows = conn.execute("SELECT name, value FROM hyg_sample ORDER BY name").fetchall()
            finally:
                conn.close()

        self.assertEqual(0, rc)
        self.assertEqual([("alpha", "1"), ("beta", "2")], rows)
        self.assertIn("imported=1", stdout.getvalue())

    def test_cli_can_unpack_zip_plan_result_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture(zip_csv_bytes()) as url:
            output_path = Path(tmpdir) / "downloads" / "sample.zip"
            plan_path = Path(tmpdir) / "plan.json"
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            plan = sample_plan(url, output_path, native_format="zip")
            plan["providers"][0]["import_plan"] = {
                "status": "requires_unpack_or_adapter",
                "table_hint": "hyg_sample",
                "source_format": "zip",
            }
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
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
                        "--import-supported-plan-results",
                        "--import-sqlite-db",
                        str(sqlite_path),
                    ]
                )
            conn = sqlite3.connect(sqlite_path)
            try:
                rows = conn.execute("SELECT name, value FROM hyg_sample ORDER BY name").fetchall()
            finally:
                conn.close()

        self.assertEqual(0, rc)
        self.assertEqual([("alpha", "1"), ("beta", "2")], rows)
        self.assertIn("imported=1", stdout.getvalue())


def sample_plan(url: str, output_path: Path, native_format: str = "bin") -> dict[str, object]:
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
                    "metadata": {"native_format": native_format},
                },
                "import_plan": {
                    "status": "supported_after_download" if native_format == "csv" else "manual_review_required",
                    "importer": "csv_to_sqlite" if native_format == "csv" else "",
                    "table_hint": "hyg_sample",
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
