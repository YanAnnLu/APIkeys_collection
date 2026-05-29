# 這份測試鎖定 favicon cache 行為；未來 SVG-first 仍需保留 Tk bitmap 邊界。
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_launcher.favicons import (
    DEFAULT_FAVICON_MAX_BYTES,
    download_favicon_png,
    favicon_cache_path,
    favicon_url_for_page,
    normalize_http_url,
    provider_home_url,
)


class FaviconTests(unittest.TestCase):
    def test_provider_home_url_uses_first_http_url(self) -> None:
        self.assertEqual("https://example.test", provider_home_url("", "example.test/docs", "https://api.example.test/v1"))

    def test_favicon_url_points_at_site_root_icon(self) -> None:
        self.assertEqual("https://example.test/favicon.ico", favicon_url_for_page("https://example.test/docs/api"))

    def test_non_http_url_is_ignored(self) -> None:
        self.assertEqual("", normalize_http_url("file:///tmp/icon.ico"))

    def test_cache_path_is_png_under_state(self) -> None:
        path = favicon_cache_path("https://example.test/favicon.ico")
        self.assertEqual(".png", path.suffix)
        self.assertIn("favicons", path.parts)

    def test_download_favicon_png_uses_named_bounded_read(self) -> None:
        read_sizes: list[int] = []

        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, _exc_type, _exc, _tb) -> None:
                return None

            def read(self, size: int) -> bytes:
                read_sizes.append(size)
                return b"not an image"

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "icon.png"
            with patch("api_launcher.favicons.urllib.request.urlopen", return_value=FakeResponse()):
                with self.assertRaises(Exception):
                    download_favicon_png("https://example.test/favicon.ico", target, max_bytes=23)

        self.assertEqual([23], read_sizes)
        self.assertEqual(128 * 1024, DEFAULT_FAVICON_MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
