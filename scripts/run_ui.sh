#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  .venv/bin/python APIkeys_collection_ui.py
else
  python3 APIkeys_collection_ui.py
fi
