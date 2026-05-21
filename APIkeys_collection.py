#!/usr/bin/env python3
"""Compatibility entry point for the APIkeys_collection launcher."""

from __future__ import annotations

# 這個檔案只保留舊入口相容性；新的業務邏輯應放在 api_launcher/ 內。
from api_launcher.core import *  # re-exported for the existing Tk UI
from api_launcher.core import main


if __name__ == "__main__":
    raise SystemExit(main())
