from __future__ import annotations

import math
import unittest

from api_launcher.importers.compatibility_shims import normalize_external_cell_value, normalize_external_header_label
from api_launcher.importers.csv_importer import normalized_column_names, normalized_row_values


class ImporterCompatibilityShimTests(unittest.TestCase):
    def test_flattens_tuple_like_header_labels(self) -> None:
        headers = [
            ("Price", "Adj Close"),
            "('Price', 'Close')",
            ("Ticker", "AAPL"),
            ("", "Volume"),
        ]

        self.assertEqual(
            ("price_adj_close", "price_close", "ticker_aapl", "volume"),
            normalized_column_names(headers),
        )

    def test_ignores_pandas_unnamed_multiindex_labels(self) -> None:
        self.assertEqual("", normalize_external_header_label(("Unnamed: 0_level_0", "")))
        self.assertEqual(
            ("date", "column_2", "price_close"),
            normalized_column_names(["Date", ("Unnamed: 1_level_0", ""), ("Price", "Close")]),
        )

    def test_normalizes_external_cell_values_without_global_patches(self) -> None:
        row = [
            "Sirius",
            None,
            math.nan,
            {"catalog": "HYG", "rank": 1},
            ["alpha", "beta"],
            ("x", "y"),
        ]

        self.assertEqual(
            (
                "Sirius",
                "",
                "",
                '{"catalog": "HYG", "rank": 1}',
                '["alpha", "beta"]',
                '["x", "y"]',
            ),
            normalized_row_values(row, width=6),
        )
        self.assertEqual("", normalize_external_cell_value(None))


if __name__ == "__main__":
    unittest.main()
