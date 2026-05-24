# 這份測試鎖定 HTTP 下載、續傳、staging 與 manifest 重用邏輯。
from __future__ import annotations

import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from api_launcher.downloads.jobs import NonBlockingDownloadQueue
from api_launcher.downloads.policy import PoliteDownloadPolicy
from api_launcher.downloads.http import (
    HTTPDownloadAdapter,
    build_download_request,
    download_target_from_plan_entry,
    reusable_completed_download,
)
from api_launcher.manifests import build_asset_manifest, write_manifest
from api_launcher.paths import default_local_downloads_root


TEST_BYTES = b"0123456789abcdefghijklmnopqrstuvwxyz" * 128


class RangeHandler(BaseHTTPRequestHandler):
    ranges: list[str] = []
    request_count: int = 0

    def do_GET(self) -> None:
        self.__class__.request_count += 1
        range_header = self.headers.get("Range", "")
        if range_header:
            self.__class__.ranges.append(range_header)
        start = 0
        if range_header.startswith("bytes=") and range_header.endswith("-"):
            start = int(range_header.removeprefix("bytes=").removesuffix("-"))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(TEST_BYTES) - 1}/{len(TEST_BYTES)}")
        else:
            self.send_response(200)
        payload = TEST_BYTES[start:]
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        for index in range(0, len(payload), 113):
            self.wfile.write(payload[index : index + 113])

    def log_message(self, _format: str, *_args: object) -> None:
        return


class HTTPServerFixture:
    def __enter__(self) -> str:
        RangeHandler.ranges = []
        RangeHandler.request_count = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/sample.bin"

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class HTTPDownloadAdapterTests(unittest.TestCase):
    def test_build_download_request_adds_range_header_for_resume(self) -> None:
        request = build_download_request("https://example.test/file.bin", resume_from=42)
        self.assertEqual("bytes=42-", request.headers["Range"])

    def test_download_target_uses_default_download_path(self) -> None:
        target = download_target_from_plan_entry(
            {"provider_id": "sample_provider", "download_url": "https://example.test/path/data.nc"}
        )
        expected_suffix = default_local_downloads_root() / "sample_provider" / "data.nc"
        self.assertTrue(str(target.output_path).endswith(str(expected_suffix)))
        self.assertTrue(str(target.part_path).endswith("data.nc.part"))

    def test_adapter_downloads_direct_url_with_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, HTTPServerFixture() as url:
            output = Path(temp_dir) / "sample.bin"
            adapter = HTTPDownloadAdapter(chunk_size=97, policy=PoliteDownloadPolicy(min_delay_per_host_seconds=0))
            queue = NonBlockingDownloadQueue(adapter, max_workers=1)
            try:
                job = queue.submit({"provider_id": "sample_provider", "download_url": url, "target_path": str(output)})
                queue.wait(job.job_id, timeout=5)
                final = queue.snapshot(job.job_id)
            finally:
                queue.shutdown()

            self.assertEqual(TEST_BYTES, output.read_bytes())
            self.assertTrue(output.with_suffix(output.suffix + ".manifest.json").exists())
            self.assertEqual(len(TEST_BYTES), final.bytes_done)
            self.assertEqual(100.0, final.percent)
            self.assertEqual(1, RangeHandler.request_count)

    def test_adapter_reuses_existing_verified_download(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, HTTPServerFixture() as url:
            output = Path(temp_dir) / "sample.bin"
            plan_entry = {"provider_id": "sample_provider", "download_url": url, "target_path": str(output)}
            output.write_bytes(TEST_BYTES)
            write_manifest(
                build_asset_manifest(output, plan_entry),
                output.with_suffix(output.suffix + ".manifest.json"),
            )

            adapter = HTTPDownloadAdapter(chunk_size=97, policy=PoliteDownloadPolicy(min_delay_per_host_seconds=0))
            queue = NonBlockingDownloadQueue(adapter, max_workers=1)
            try:
                job = queue.submit(plan_entry)
                queue.wait(job.job_id, timeout=5)
                final = queue.snapshot(job.job_id)
            finally:
                queue.shutdown()

            self.assertEqual(TEST_BYTES, output.read_bytes())
            self.assertEqual(0, RangeHandler.request_count)
            self.assertEqual(100.0, final.percent)

    def test_reuse_requires_manifest_to_match_requested_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample.bin"
            old_plan = {
                "provider_id": "sample_provider",
                "download_url": "https://example.test/sample.bin",
                "target_path": str(output),
                "dataset_version": {"dataset_uid": "sample:grid", "dataset_id": "grid", "version": "2025"},
            }
            new_plan = {
                **old_plan,
                "dataset_version": {"dataset_uid": "sample:grid", "dataset_id": "grid", "version": "2026"},
            }
            output.write_bytes(TEST_BYTES)
            write_manifest(
                build_asset_manifest(output, old_plan),
                output.with_suffix(output.suffix + ".manifest.json"),
            )

            self.assertFalse(reusable_completed_download(download_target_from_plan_entry(new_plan), new_plan))

    def test_adapter_resumes_existing_part_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, HTTPServerFixture() as url:
            output = Path(temp_dir) / "sample.bin"
            part = output.with_suffix(output.suffix + ".part")
            part.write_bytes(TEST_BYTES[:100])

            adapter = HTTPDownloadAdapter(chunk_size=101, policy=PoliteDownloadPolicy(min_delay_per_host_seconds=0))
            queue = NonBlockingDownloadQueue(adapter, max_workers=1)
            try:
                job = queue.submit({"provider_id": "sample_provider", "download_url": url, "target_path": str(output)})
                queue.wait(job.job_id, timeout=5)
            finally:
                queue.shutdown()

            self.assertEqual(TEST_BYTES, output.read_bytes())
            self.assertIn("bytes=100-", RangeHandler.ranges)

    def test_adapter_can_opt_out_of_staging_for_legacy_paths(self) -> None:
        target = download_target_from_plan_entry(
            {
                "provider_id": "sample_provider",
                "download_url": "https://example.test/path/data.nc",
                "target_path": "downloads/sample_provider/data.nc",
                "use_staging": False,
            }
        )

        self.assertTrue(str(target.part_path).endswith(str(Path("downloads") / "sample_provider" / "data.nc.part")))
        self.assertIsNone(target.staging_paths)


if __name__ == "__main__":
    unittest.main()
