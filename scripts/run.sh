#!/bin/bash
# Start the menu-bar app with the latex-snipper conda env, not whatever python is first on PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

find_env_python() {
  local base="" candidate
  local candidates=()
  if [[ -n "${CONDA_EXE:-}" ]]; then
    base="$(cd "$(dirname "$CONDA_EXE")/.." && pwd)"
  elif command -v conda >/dev/null 2>&1; then
    base="$(conda info --base 2>/dev/null || true)"
  fi
  if [[ -n "$base" ]]; then
    candidates+=("$base/envs/latex-snipper/bin/python")
  fi
  candidates+=(
    "/opt/anaconda3/envs/latex-snipper/bin/python"
    "/opt/miniconda3/envs/latex-snipper/bin/python"
    "$HOME/anaconda3/envs/latex-snipper/bin/python"
    "$HOME/miniconda3/envs/latex-snipper/bin/python"
    "$HOME/miniforge3/envs/latex-snipper/bin/python"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON="$(find_env_python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "Could not find the latex-snipper conda environment." >&2
  echo "From the TexGrab directory, run:" >&2
  echo "  conda env create -f environment.yml" >&2
  echo "  conda activate latex-snipper" >&2
  echo "  pip install -e ." >&2
  exit 1
fi
cd "$ROOT"
exec "$PYTHON" -m texgrab "$@"
