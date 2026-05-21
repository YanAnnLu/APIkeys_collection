#!/usr/bin/env python3
"""Compatibility entry point for the Tk launcher frontend."""

from __future__ import annotations

# UI 啟動入口保持很薄，讓 Tk 實作可以在 frontends/tk/ 內獨立維護。
from frontends.tk.launcher_ui import main


if __name__ == "__main__":
    raise SystemExit(main())
