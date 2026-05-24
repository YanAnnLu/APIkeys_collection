from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api_launcher.showcase_download import build_showcase_resumable_download_plan
from frontends.tk.showcase_workflows import (
    showcase_download_progress_message,
    showcase_resumable_plan_message,
    showcase_seed_coverage_message,
)


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

    def test_showcase_resumable_message_guides_pause_resume_without_sql(self) -> None:
        # 續傳展示是給人現場照著按的流程，文字必須同時說明 Pause/Resume 與 SQL 短路邊界。
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = build_showcase_resumable_download_plan(tmpdir)
            message = showcase_resumable_plan_message(plan, lambda zh, _en="": zh)

        self.assertIn("續傳展示下載已加入下載面板", message)
        self.assertIn("暫停", message)
        self.assertIn("繼續", message)
        self.assertIn("短路 SQL 匯入", message)

    def test_showcase_progress_message_discloses_fallback_source(self) -> None:
        message = showcase_download_progress_message("fallback_public_csv", {}, lambda zh, _en="": zh)

        self.assertIn("備援公開 CSV", message)
        self.assertIn("真下載", message)
        self.assertIn("SQLite", message)


if __name__ == "__main__":
    unittest.main()
