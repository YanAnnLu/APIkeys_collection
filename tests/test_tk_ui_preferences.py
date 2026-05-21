# 這份測試鎖定 Tk UI 偏好設定，避免欄寬與匯入策略 config 回歸。
from __future__ import annotations

import unittest

from api_launcher.import_policies import DEFAULT_UI_IMPORT_POLICY, normalized_ui_import_policy


class TkUiPreferenceTests(unittest.TestCase):
    def test_import_policy_preference_accepts_supported_values(self) -> None:
        self.assertEqual("rename", normalized_ui_import_policy(" rename "))
        self.assertEqual("skip", normalized_ui_import_policy("SKIP"))
        self.assertEqual("replace", normalized_ui_import_policy("replace"))

    def test_import_policy_preference_falls_back_to_safe_rename(self) -> None:
        self.assertEqual(DEFAULT_UI_IMPORT_POLICY, normalized_ui_import_policy(""))
        self.assertEqual(DEFAULT_UI_IMPORT_POLICY, normalized_ui_import_policy(None))
        self.assertEqual(DEFAULT_UI_IMPORT_POLICY, normalized_ui_import_policy("drop"))
        self.assertEqual(DEFAULT_UI_IMPORT_POLICY, normalized_ui_import_policy("drop", default="also_drop"))
        self.assertEqual("skip", normalized_ui_import_policy("skip", default="drop"))


if __name__ == "__main__":
    unittest.main()
