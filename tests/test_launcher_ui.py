# 這份測試鎖定 Tk 視窗生命週期錯誤 suppressor，避免吞掉非預期例外。
import unittest
from tkinter import TclError

from frontends.tk.launcher_ui import contextlib_suppress_tcl_error


class TclErrorSuppressorTests(unittest.TestCase):
    def test_suppresses_tcl_errors(self) -> None:
        with contextlib_suppress_tcl_error():
            raise TclError("window no longer exists")

    def test_does_not_suppress_unexpected_errors(self) -> None:
        with self.assertRaises(RuntimeError):
            with contextlib_suppress_tcl_error():
                raise RuntimeError("unexpected")


if __name__ == "__main__":
    unittest.main()
