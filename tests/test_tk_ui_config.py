import unittest
from unittest.mock import patch

from api_launcher.paths import default_local_curated_db_path
from frontends.tk import ui_config


class TkUiConfigTests(unittest.TestCase):
    def test_configured_ui_language_uses_traditional_chinese_default(self) -> None:
        # local config 缺語言欄位時，Tk UI 應維持專案預設的繁體中文介面。
        with patch("frontends.tk.ui_config.core.load_integration_config", return_value={}):
            self.assertEqual(ui_config.DEFAULT_UI_LANGUAGE, ui_config.configured_ui_language())

    def test_configured_ui_language_accepts_supported_language(self) -> None:
        # 設定頁寫入的支援語言碼要原樣保留，避免下次開 UI 時退回預設。
        with patch("frontends.tk.ui_config.core.load_integration_config", return_value={"ui_language": "en-US"}):
            self.assertEqual("en-US", ui_config.configured_ui_language())

    def test_configured_ui_language_rejects_unknown_language(self) -> None:
        # 人工改壞 local config 時要安全 fallback，不讓後續 tr()/combobox 找不到 label。
        with patch("frontends.tk.ui_config.core.load_integration_config", return_value={"ui_language": "xx-YY"}):
            self.assertEqual(ui_config.DEFAULT_UI_LANGUAGE, ui_config.configured_ui_language())

    def test_product_and_runtime_paths_remain_compatible(self) -> None:
        # 對外產品名可重塑品牌，但下載計畫檔名仍保留 APIkeys_collection 相容名稱。
        self.assertEqual("RuRuKa Asset Launcher", ui_config.PRODUCT_DISPLAY_NAME)
        self.assertEqual("RRKAL", ui_config.PRODUCT_SHORT_NAME)
        self.assertEqual("APIkeys_collection_download_plan.json", ui_config.DOWNLOAD_PLAN_NAME)
        self.assertEqual(default_local_curated_db_path(), ui_config.curated_imports_path())

    def test_table_columns_keep_required_action_column(self) -> None:
        # 表格欄位設定被 resize / click routing 共用；action 欄要保留在最後，避免按鈕欄判斷錯位。
        names = [column[0] for column in ui_config.TABLE_COLUMNS]

        self.assertEqual("star", names[0])
        self.assertEqual("action", names[-1])
        self.assertIn("column_manual_max", ui_config.LAYOUT)


if __name__ == "__main__":
    unittest.main()
