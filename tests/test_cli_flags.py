from __future__ import annotations

import json
import subprocess
import sys
import unittest


class CliFlagsTests(unittest.TestCase):
    def test_cli_flags_import_does_not_load_command_modules(self) -> None:
        script = """
import json
import sys

import api_launcher.cli_flags

loaded = sorted(
    name
    for name in sys.modules
    if name.startswith("api_launcher.cli_") and name != "api_launcher.cli_flags"
)
print(json.dumps(loaded))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", script],
            check=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual([], json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
