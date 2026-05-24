#!/usr/bin/env python3
"""Compatibility entry point for the APIkeys_collection launcher."""

from __future__ import annotations

# 相容入口只保留 thin wrapper；實際業務邏輯仍在 api_launcher/ 內，避免 root 檔繼續膨脹。
from api_launcher.core import *  # re-exported for the existing Tk UI
from api_launcher.core import main
from api_launcher.integrations import active_download_policy  # re-exported for the existing Tk UI


if __name__ == "__main__":
    raise SystemExit(main())
