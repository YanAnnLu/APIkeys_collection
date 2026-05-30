# 這份測試鎖定 core metadata probe 的錯誤回應讀取邊界，避免 HTTP error body 被無界讀入。
from __future__ import annotations

import unittest
import urllib.error
from unittest.mock import patch

from api_launcher.core import DEFAULT_HTTP_ERROR_EXCERPT_MAX_BYTES, safe_fetch_metadata


class MetadataProbeTests(unittest.TestCase):
    def test_safe_fetch_metadata_marks_success_excerpt_as_truncated(self) -> None:
        read_sizes: list[int] = []

        class FakeResponse:
            status = 200
            headers = {"Content-Type": "text/plain", "Content-Length": "128"}

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                read_sizes.append(size)
                return b"x" * size

        with patch("api_launcher.core.urllib.request.urlopen", return_value=FakeResponse()):
            payload = safe_fetch_metadata("https://example.test/metadata", max_bytes=17, timeout=1.0)

        self.assertTrue(payload["truncated"])
        self.assertEqual(17, len(payload["excerpt"]))
        self.assertEqual([18], read_sizes)

    def test_safe_fetch_metadata_limits_http_error_excerpt_body(self) -> None:
        read_sizes: list[int] = []

        class FakeBody:
            def read(self, size: int) -> bytes:
                read_sizes.append(size)
                return b"error body"

            def close(self) -> None:
                return None

        error = urllib.error.HTTPError(
            "https://example.test/metadata",
            500,
            "server error",
            {"Content-Type": "text/plain"},
            FakeBody(),
        )

        with patch("api_launcher.core.urllib.request.urlopen", side_effect=error):
            payload = safe_fetch_metadata("https://example.test/metadata", max_bytes=100_000, timeout=1.0)

        self.assertEqual(500, payload["status_code"])
        self.assertIn("error body", payload["excerpt"])
        self.assertEqual([DEFAULT_HTTP_ERROR_EXCERPT_MAX_BYTES], read_sizes)

    def test_safe_fetch_metadata_respects_smaller_user_max_for_http_error_excerpt(self) -> None:
        read_sizes: list[int] = []

        class FakeBody:
            def read(self, size: int) -> bytes:
                read_sizes.append(size)
                return b"short"

            def close(self) -> None:
                return None

        error = urllib.error.HTTPError(
            "https://example.test/metadata",
            404,
            "not found",
            {"Content-Type": "text/plain"},
            FakeBody(),
        )

        with patch("api_launcher.core.urllib.request.urlopen", side_effect=error):
            safe_fetch_metadata("https://example.test/metadata", max_bytes=17, timeout=1.0)

        self.assertEqual([17], read_sizes)


if __name__ == "__main__":
    unittest.main()
