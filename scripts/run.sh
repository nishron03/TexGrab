#!/bin/bash
# Start the menu-bar app with the project conda env, ignoring the caller's Python.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="/opt/anaconda3/envs/latex-snipper/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Missing $PYTHON" >&2
  echo "Create the env from the TexGrab directory: conda env create -f environment.yml" >&2
  exit 1
fi
cd "$ROOT"
exec "$PYTHON" -m texgrab "$@"
