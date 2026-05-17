#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m py_compile APIkeys_collection.py APIkeys_collection_ui.py
.venv/bin/python APIkeys_collection.py --summary

echo
echo "Environment ready."
echo "Activate with: source .venv/bin/activate"
echo "Run UI with: ./scripts/run_ui.sh"
