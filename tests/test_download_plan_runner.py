from __future__ import annotations

import io
import gzip
import json
import sqlite3
import tarfile
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


def zip_ndjson_gz_bytes() -> bytes:
    payload = gzip.compress(b'{"name":"alpha","value":1}\n{"name":"beta","value":2}\n')
    handle = io.BytesIO()
    with zipfile.ZipFile(handle, "w") as archive:
        archive.writestr("nested/sample.ndjson.gz", payload)
    return handle.getvalue()


def tar_geojson_gz_bytes() -> bytes:
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "alpha", "value": 1}, "geometry": None},
            {"type": "Feature", "properties": {"name": "beta", "value": 2}, "geometry": None},
        ],
    }
    payload = gzip.compress(json.dumps(geojson).encode("utf-8"))
    handle = io.BytesIO()
    with tarfile.open(fileobj=handle, mode="w:gz") as archive:
        member = tarfile.TarInfo("nested/sample.geojson.gz")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
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

    def test_import_supported_plan_results_skips_existing_table_on_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture(CSV_BYTES) as url:
            output_path = Path(tmpdir) / "downloads" / "sample.csv"
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            conn = connect_db(Path(tmpdir) / "launcher.sqlite")
            try:
                repo = ApiCatalogRepository(conn)
                repo.init_schema()
                repo.seed_builtin_providers()
                plan = sample_plan(url, output_path, native_format="csv")

                first = run_download_plan_payload(
                    plan,
                    repo,
                    policy=PoliteDownloadPolicy(max_parallel_jobs=1, min_delay_per_host_seconds=0),
                    timeout=5,
                    import_supported_results=True,
                    import_sqlite_path=sqlite_path,
                )
                second = run_download_plan_payload(
                    plan,
                    repo,
                    policy=PoliteDownloadPolicy(max_parallel_jobs=1, min_delay_per_host_seconds=0),
                    timeout=5,
                    import_supported_results=True,
                    import_sqlite_path=sqlite_path,
                )
            finally:
                conn.close()

            db = sqlite3.connect(sqlite_path)
            try:
                rows = db.execute("SELECT name, value FROM hyg_sample ORDER BY name").fetchall()
            finally:
                db.close()

        self.assertEqual(1, first.imported)
        self.assertEqual(0, first.import_skipped)
        self.assertEqual(0, first.import_failed)
        self.assertEqual(0, second.imported)
        self.assertEqual(1, second.import_skipped)
        self.assertEqual(0, second.import_failed)
        self.assertEqual(0, second.failed)
        self.assertEqual([("alpha", "1"), ("beta", "2")], rows)

    def test_cli_can_rename_existing_table_when_importing_plan_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture(CSV_BYTES) as url:
            output_path = Path(tmpdir) / "downloads" / "sample.csv"
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "plan.json"
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            plan_path.write_text(json.dumps(sample_plan(url, output_path, native_format="csv"), ensure_ascii=False), encoding="utf-8")
            first_stdout = io.StringIO()
            second_stdout = io.StringIO()
            base_args = [
                "--db",
                str(db_path),
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

            with redirect_stdout(first_stdout):
                first_rc = main(base_args)
            with redirect_stdout(second_stdout):
                second_rc = main([*base_args, "--plan-import-existing-table-policy", "rename"])

            conn = sqlite3.connect(sqlite_path)
            try:
                base_rows = conn.execute("SELECT name, value FROM hyg_sample ORDER BY name").fetchall()
                renamed_rows = conn.execute("SELECT name, value FROM hyg_sample_2 ORDER BY name").fetchall()
            finally:
                conn.close()

        self.assertEqual(0, first_rc)
        self.assertEqual(0, second_rc)
        self.assertEqual([("alpha", "1"), ("beta", "2")], base_rows)
        self.assertEqual([("alpha", "1"), ("beta", "2")], renamed_rows)
        self.assertIn("imported=1", second_stdout.getvalue())

    def test_cli_can_replace_existing_table_when_importing_plan_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture(CSV_BYTES) as url:
            output_path = Path(tmpdir) / "downloads" / "sample.csv"
            db_path = Path(tmpdir) / "launcher.sqlite"
            plan_path = Path(tmpdir) / "plan.json"
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            plan_path.write_text(json.dumps(sample_plan(url, output_path, native_format="csv"), ensure_ascii=False), encoding="utf-8")
            first_stdout = io.StringIO()
            second_stdout = io.StringIO()
            base_args = [
                "--db",
                str(db_path),
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

            with redirect_stdout(first_stdout):
                first_rc = main(base_args)
            conn = sqlite3.connect(sqlite_path)
            try:
                conn.execute("INSERT INTO hyg_sample (name, value) VALUES (?, ?)", ("stale", "999"))
                conn.commit()
            finally:
                conn.close()

            with redirect_stdout(second_stdout):
                second_rc = main([*base_args, "--plan-import-existing-table-policy", "replace"])

            conn = sqlite3.connect(sqlite_path)
            try:
                rows = conn.execute("SELECT name, value FROM hyg_sample ORDER BY name").fetchall()
                renamed_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'hyg_sample_2'").fetchone()
            finally:
                conn.close()

        self.assertEqual(0, first_rc)
        self.assertEqual(0, second_rc)
        self.assertEqual([("alpha", "1"), ("beta", "2")], rows)
        self.assertIsNone(renamed_exists)
        self.assertIn("imported=1", second_stdout.getvalue())

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

    def test_cli_can_unpack_ndjson_gz_zip_member_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture(zip_ndjson_gz_bytes()) as url:
            output_path = Path(tmpdir) / "downloads" / "sample.zip"
            plan_path = Path(tmpdir) / "plan.json"
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            plan = sample_plan(url, output_path, native_format="zip")
            plan["providers"][0]["import_plan"] = {
                "status": "requires_unpack_or_adapter",
                "table_hint": "hyg_sample_json",
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
                rows = conn.execute("SELECT name, value FROM hyg_sample_json ORDER BY name").fetchall()
            finally:
                conn.close()

        self.assertEqual(0, rc)
        self.assertEqual([("alpha", "1"), ("beta", "2")], rows)
        self.assertIn("imported=1", stdout.getvalue())

    def test_cli_can_unpack_geojson_gz_tar_member_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, HTTPServerFixture(tar_geojson_gz_bytes()) as url:
            output_path = Path(tmpdir) / "downloads" / "sample.tar.gz"
            plan_path = Path(tmpdir) / "plan.json"
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            plan = sample_plan(url, output_path, native_format="tar.gz")
            plan["providers"][0]["import_plan"] = {
                "status": "requires_unpack_or_adapter",
                "table_hint": "hyg_sample_geojson",
                "source_format": "tar.gz",
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
                rows = conn.execute("SELECT name, value FROM hyg_sample_geojson ORDER BY name").fetchall()
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
