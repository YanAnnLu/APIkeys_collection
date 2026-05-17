from __future__ import annotations

import unittest

from api_launcher.favicons import favicon_cache_path, favicon_url_for_page, normalize_http_url, provider_home_url


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


if __name__ == "__main__":
    unittest.main()
