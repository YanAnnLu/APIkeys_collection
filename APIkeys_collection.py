#!/usr/bin/env python3
"""Compatibility entry point for the APIkeys_collection launcher."""

from __future__ import annotations

from api_launcher.core import *  # re-exported for the existing Tk UI
from api_launcher.core import main


if __name__ == "__main__":
    raise SystemExit(main())
