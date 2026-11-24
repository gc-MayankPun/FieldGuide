#!/usr/bin/env bash
# Start FieldGuide from the project folder, creating the virtual environment on first use.
set -e
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  python -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi
exec python -m fieldguide "$@"
