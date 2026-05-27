from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from api_launcher.local_credentials import credential_display_profile, read_env_values, write_env_updates


class LocalCredentialsTest(unittest.TestCase):
    def test_credential_display_profile_exposes_badge_and_summaries(self) -> None:
        profile = credential_display_profile(
            status="missing_credentials",
            configured_count=1,
            field_count=2,
            missing_required=["NASA_TOKEN"],
            next_action="edit_local_credentials_before_live_download",
        )

        payload = profile.to_dict()

        self.assertEqual("需要登入 / API Key 1/2", payload["badge_label"])
        self.assertEqual("warning", payload["tone"])
        self.assertIn("NASA_TOKEN", payload["summary_zh_TW"])
        self.assertEqual("edit_local_credentials_before_live_download", payload["next_action"])
        self.assertEqual("先完成登入設定，再下載資料", payload["next_action_label_zh_TW"])
        self.assertIn("Complete login settings", payload["summary_en"])

    def test_write_env_updates_keeps_existing_file_if_replace_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("NASA_EARTHDATA_TOKEN=old-token\n", encoding="utf-8")

            with patch("api_launcher.local_credentials.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    write_env_updates(
                        env_path,
                        values={"NASA_EARTHDATA_TOKEN": "new-token"},
                        clear=set(),
                    )

            self.assertEqual("old-token", read_env_values(env_path)["NASA_EARTHDATA_TOKEN"])
            self.assertEqual([], list(Path(tmp).glob(".env.*.tmp")))


if __name__ == "__main__":
    unittest.main()
