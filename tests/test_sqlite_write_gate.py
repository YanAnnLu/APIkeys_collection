from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from api_launcher.importers.csv_importer import import_rows_to_sqlite
from api_launcher.sqlite_write_gate import (
    sqlite_write_gate,
    sqlite_write_gate_key,
    sqlite_write_gate_profile,
)


class SQLiteWriteGateTests(unittest.TestCase):
    def test_write_gate_serializes_same_sqlite_path_inside_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = Path(tmpdir) / "curated.sqlite"
            worker_started = threading.Event()
            worker_entered = threading.Event()

            def worker() -> None:
                worker_started.set()
                with sqlite_write_gate(sqlite_path):
                    worker_entered.set()

            with sqlite_write_gate(sqlite_path):
                thread = threading.Thread(target=worker)
                thread.start()
                self.assertTrue(worker_started.wait(timeout=1.0))
                self.assertFalse(worker_entered.wait(timeout=0.05))

            self.assertTrue(worker_entered.wait(timeout=1.0))
            thread.join(timeout=1.0)
            self.assertFalse(thread.is_alive())

    def test_write_gate_is_reentrant_for_import_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = Path(tmpdir) / "curated.sqlite"

            with sqlite_write_gate(sqlite_path):
                imported = import_rows_to_sqlite(
                    sqlite_path,
                    "items",
                    ("name",),
                    [["alpha"], ["beta"]],
                    replace=False,
                    row_limit=0,
                )

            with closing(sqlite3.connect(sqlite_path)) as conn:
                rows = conn.execute('SELECT name FROM "items" ORDER BY name').fetchall()

        self.assertEqual(2, imported)
        self.assertEqual([("alpha",), ("beta",)], rows)

    def test_write_gate_profile_is_agent_readable(self) -> None:
        profile = sqlite_write_gate_profile().to_dict()

        self.assertEqual("sqlite_write_gate", profile["gate_id"])
        self.assertEqual("process_per_sqlite_path", profile["scope"])
        self.assertEqual(1, profile["max_active_writers_per_database"])
        self.assertIn("csv_to_sqlite", profile["protects"])
        self.assertIn("json_to_sqlite", profile["protects"])

    def test_write_gate_key_normalizes_equivalent_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = Path(tmpdir) / "nested" / ".." / "curated.sqlite"
            plain_path = Path(tmpdir) / "curated.sqlite"

            self.assertEqual(sqlite_write_gate_key(sqlite_path), sqlite_write_gate_key(plain_path))


if __name__ == "__main__":
    unittest.main()
