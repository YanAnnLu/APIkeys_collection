#!/usr/bin/env python3
"""Compatibility entry point for the Tk launcher frontend."""

from __future__ import annotations

# 這個檔案只保留舊啟動路徑的相容性；真正的 Tk UI 實作在 frontends/tk/launcher_ui.py。
from frontends.tk.launcher_ui import main


if __name__ == "__main__":
    raise SystemExit(main())
