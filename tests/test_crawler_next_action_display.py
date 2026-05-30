from __future__ import annotations

import unittest

from api_launcher.crawler_next_action_display import (
    next_action_display_label,
    next_action_display_label_or_fallback,
)


class CrawlerNextActionDisplayTest(unittest.TestCase):
    def test_known_action_keeps_shared_label(self) -> None:
        self.assertEqual("先選擇一筆 seed", next_action_display_label("select_seed"))
        self.assertEqual("先選擇一筆 seed", next_action_display_label_or_fallback("select_seed"))

    def test_unknown_backend_id_uses_safe_fallback(self) -> None:
        self.assertEqual(
            "檢查下一步設定",
            next_action_display_label_or_fallback("new_backend_action_id"),
        )
        self.assertEqual(
            "檢查測試設定",
            next_action_display_label_or_fallback("new_backend_action_id", fallback="檢查測試設定"),
        )

    def test_human_text_is_preserved(self) -> None:
        self.assertEqual(
            "Open the review panel",
            next_action_display_label_or_fallback("Open the review panel"),
        )


if __name__ == "__main__":
    unittest.main()
