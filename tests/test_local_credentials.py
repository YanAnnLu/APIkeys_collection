from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from api_launcher.local_credentials import read_env_values, write_env_updates


class LocalCredentialsTest(unittest.TestCase):
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
