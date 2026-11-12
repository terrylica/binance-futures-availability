#!/usr/bin/env bash
# Local quality gate (local-first CI): lint, format, full test suite with coverage ratchet.
# Run before every push. GitHub Actions only runs the data pipeline, never tests or lint.
set -euo pipefail
cd "$(dirname "$0")/.."

PY_DIRS=(src tests scripts .github/scripts)
# pytest and ruff live in the `dev` extra; without it a freshly built .venv has no pytest.
uv run --extra dev ruff check "${PY_DIRS[@]}"
uv run --extra dev ruff format --check "${PY_DIRS[@]}"
uv run --extra dev pytest -q "$@"
