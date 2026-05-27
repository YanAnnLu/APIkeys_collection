import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from api_launcher.crawlers.fetch import fetch_text, search_endpoint_url


class CrawlerFetchTests(unittest.TestCase):
    def test_search_endpoint_url_appends_query_before_fragment(self) -> None:
        url = search_endpoint_url("https://data.example.test/api#docs", {"q": "roads"})

        self.assertEqual("https://data.example.test/api?q=roads#docs", url)

    def test_search_endpoint_url_preserves_existing_query_and_fragment(self) -> None:
        url = search_endpoint_url(
            "https://data.example.test/api?domains=data.example.test#docs",
            {"limit": "25", "q": "taxi trips"},
        )

        self.assertEqual(
            "https://data.example.test/api?domains=data.example.test&limit=25&q=taxi+trips#docs",
            url,
        )

    def test_search_endpoint_url_keeps_url_when_no_params_survive(self) -> None:
        url = search_endpoint_url("https://data.example.test/api?domains=data.example.test#docs", {"q": ""})

        self.assertEqual("https://data.example.test/api?domains=data.example.test#docs", url)

    def test_fetch_text_rejects_metadata_response_over_byte_limit(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "large-catalog.txt"
            path.write_text("x" * 32, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "exceeded 8 bytes"):
                fetch_text(path.as_uri(), timeout=1.0, max_bytes=8)


if __name__ == "__main__":
    unittest.main()
