#!/usr/bin/env bash
# Install dependencies and run the standard checks. Fix any failure before new work.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> Working directory: $PWD"
echo "==> Syncing dependencies"
uv sync --locked

echo "==> Running baseline verification"
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest

echo "==> Startup command"
echo "    uv run streamlit run streamlit_app.py"

if [ "${RUN_START_COMMAND:-0}" = "1" ]; then
  echo "==> Starting the app"
  exec uv run streamlit run streamlit_app.py
fi

echo "Set RUN_START_COMMAND=1 if you want init.sh to launch the app directly."
