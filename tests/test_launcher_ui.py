# 這份測試鎖定 Tk 視窗生命週期錯誤 suppressor，避免吞掉非預期例外。
import unittest
from types import SimpleNamespace
from tkinter import TclError

from frontends.tk.launcher_ui import contextlib_suppress_tcl_error, database_sql_dry_run_available


class TclErrorSuppressorTests(unittest.TestCase):
    def test_suppresses_tcl_errors(self) -> None:
        with contextlib_suppress_tcl_error():
            raise TclError("window no longer exists")

    def test_does_not_suppress_unexpected_errors(self) -> None:
        with self.assertRaises(RuntimeError):
            with contextlib_suppress_tcl_error():
                raise RuntimeError("unexpected")


class DatabaseDryRunUiHelperTests(unittest.TestCase):
    def test_database_sql_dry_run_available_reads_self_check_flag(self) -> None:
        suggestion = SimpleNamespace(details={"sql_dry_run_available": True})

        self.assertTrue(database_sql_dry_run_available(suggestion))

    def test_database_sql_dry_run_available_defaults_to_false(self) -> None:
        self.assertFalse(database_sql_dry_run_available(SimpleNamespace(details={})))
        self.assertFalse(database_sql_dry_run_available(SimpleNamespace(details="not-a-dict")))


if __name__ == "__main__":
    unittest.main()
