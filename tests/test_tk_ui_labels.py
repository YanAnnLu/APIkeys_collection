import unittest
from types import SimpleNamespace

from frontends.tk.ui_labels import (
    crawler_next_action_label,
    data_store_next_action_message,
    localized_database_repair_description,
    localized_database_repair_label,
    localized_download_label,
    localized_download_reason,
    localized_download_repair_label,
)


def zh(zh_text: str, en_text: str) -> str:
    return zh_text


class TkUiLabelTests(unittest.TestCase):
    def test_download_label_localizes_status_and_api_key(self) -> None:
        # 下載資格是 backend 穩定碼；UI helper 負責把它壓成表格短標籤。
        eligibility = SimpleNamespace(status="adapter_required", label="Adapter", requires_api_key=True)

        self.assertEqual("需要轉接器+金鑰", localized_download_label(eligibility, "zh-TW"))
        self.assertEqual("Adapter+Key", localized_download_label(eligibility, "en-US"))

    def test_download_reason_localizes_known_status(self) -> None:
        eligibility = SimpleNamespace(status="metadata_only", reason="Docs only")

        self.assertIn("目前只有文件", localized_download_reason(eligibility, "zh-TW"))
        self.assertEqual("Docs only", localized_download_reason(eligibility, "en-US"))

    def test_repair_labels_keep_fallbacks(self) -> None:
        # 未知 action_id 要回落到 backend label，避免 UI 顯示空字串。
        known_download = SimpleNamespace(action_id="requeue_download", label="Requeue")
        unknown_database = SimpleNamespace(action_id="new_action", label="Inspect upstream")

        self.assertEqual("重新排下載", localized_download_repair_label(known_download, "zh-TW"))
        self.assertEqual("Inspect upstream", localized_database_repair_label(unknown_database, "zh-TW"))

    def test_database_repair_description_prioritizes_sql_dry_run_boundary(self) -> None:
        suggestion = SimpleNamespace(
            action_id="restore_or_reimport_table",
            description="Restore table",
            details={"sql_dry_run_available": True},
        )

        message = localized_database_repair_description(suggestion, "zh-TW", zh)

        self.assertIn("dry-run SQL", message)
        self.assertIn("DBA", message)

    def test_data_store_next_action_message_uses_backend_next_action(self) -> None:
        result = SimpleNamespace(profile_id="mysql_default", status="missing_env", details={})

        self.assertIn("寫出 env 範本", data_store_next_action_message(result, zh))

    def test_crawler_next_action_label_guides_parser_repair(self) -> None:
        message = crawler_next_action_label("repair_crawler_query_or_parser", zh)

        self.assertIn("回傳 0 筆", message)
        self.assertEqual("unknown_action", crawler_next_action_label("unknown_action", zh))


if __name__ == "__main__":
    unittest.main()
