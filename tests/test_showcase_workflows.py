from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from frontends.tk.showcase_workflows import showcase_seed_coverage_message


class ShowcaseWorkflowHelperTests(unittest.TestCase):
    def test_compat_wrapper_exports_download_policy_for_tk_ui(self) -> None:
        # Tk 主程式仍透過相容 wrapper 匯入核心能力；這個測試避免 wrapper 漏匯出導致 UI 啟動後才崩潰。
        import APIkeys_collection as core

        self.assertTrue(callable(core.active_download_policy))

    def test_showcase_seed_coverage_message_is_user_visible_and_safe(self) -> None:
        # 展示模式摘要必須明確告知「只讀 metadata」，避免展示時被誤解為已經下載或寫入資料庫。
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            message = showcase_seed_coverage_message(
                {
                    "showcase_status": "all_sources_have_complete_seed_attempt_path",
                    "source_count": 23,
                    "complete_seed_capable_count": 23,
                    "complete_seed_ready_count": 1,
                    "needs_complete_seed_action_count": 22,
                    "max_pages_effective_cap": 3,
                },
                root / "dataset_seed_coverage.json",
                root / "dataset_seed_coverage.md",
                lambda zh, _en="": zh,
            )

        self.assertIn("展示模式 seed 覆蓋報告已建立", message)
        self.assertIn("已登錄入口 source：23", message)
        self.assertIn("具備完整 seed 嘗試路徑：23", message)
        self.assertIn("不會執行網路爬蟲、下載資料或寫入資料庫", message)


if __name__ == "__main__":
    unittest.main()
