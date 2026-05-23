"""Tk 啟動與視窗生命週期輔助工具。"""

from __future__ import annotations

from tkinter import TclError


class contextlib_suppress_tcl_error:
    """只給 Tk 視窗關閉邊界使用的 `TclError` suppressor。

    Tk 在使用者快速關窗、root 被銷毀或 delayed callback 還沒跑完時，
    可能拋出 `TclError`。既有 UI 路徑會吞掉這類錯誤，避免關窗流程
    變成噪音；這個 helper 先保持原本「所有 TclError 都吞掉」的行為，
    後續若要收窄訊息比對，應另開一個行為變更 checkpoint。
    """

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return isinstance(exc, TclError)


def tk_startup_failure_message(error: Exception) -> str:
    """回傳 Tk root 建立失敗時可直接印到 stderr 的修復提示。"""

    # Tk root 還沒建立時不能依賴 messagebox；這裡回傳純文字，讓 wrapper/CLI stderr 也能提示修復方向。
    detail = f"{type(error).__name__}: {error}"
    return (
        "Tk UI 無法啟動。\n\n"
        f"錯誤：{detail}\n\n"
        "修復建議：\n"
        "1. 如果錯誤提到 init.tcl、Tcl 或 Tk，代表目前 Python 環境的 Tcl/Tk runtime 不完整；"
        "請先改用系統 Python 執行 `py -B APIkeys_collection_ui.py`。\n"
        "2. 如果一定要使用 `.venv`，請用包含 Tcl/Tk 的 Python 重新建立 venv，"
        "不要把 base/system Python 套件直接混進專案環境。\n"
        "3. 如果錯誤提到 display、DISPLAY 或圖形環境，請在有桌面 session 的機器上開啟 UI；"
        "後端可先用 `py -B APIkeys_collection.py --summary` 檢查。"
    )
