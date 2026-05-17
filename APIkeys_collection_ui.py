#!/usr/bin/env python3
"""Compatibility entry point for the Tk launcher frontend."""

from __future__ import annotations

from frontends.tk.launcher_ui import main


if __name__ == "__main__":
    raise SystemExit(main())
