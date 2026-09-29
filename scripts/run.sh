#!/bin/bash
# Start the menu-bar app with the latex-snipper conda env, not whatever python is first on PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

find_env_python() {
  local base="" candidate
  local candidates=()
  # An already-activated latex-snipper env wins, including `conda activate`.
  if [[ -n "${CONDA_PREFIX:-}" && "$(basename "$CONDA_PREFIX")" == "latex-snipper" ]]; then
    candidates+=("$CONDA_PREFIX/bin/python")
  fi
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
    "$HOME/mambaforge/envs/latex-snipper/bin/python"
    "$HOME/.local/share/miniconda3/envs/latex-snipper/bin/python"
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
  if [[ "$(uname -s)" == "Linux" ]]; then
    echo "  conda env create -f environment-linux.yml" >&2
  else
    echo "  conda env create -f environment.yml" >&2
  fi
  echo "  conda activate latex-snipper" >&2
  echo "  pip install -e ." >&2
  exit 1
fi
# The editable install and wl-copy live next to this interpreter.
export PATH="$(dirname "$PYTHON"):${PATH}"
if [[ "$(uname -s)" == "Linux" ]]; then
  typelibs="/usr/lib/girepository-1.0:/usr/lib/x86_64-linux-gnu/girepository-1.0"
  if [[ -n "${GI_TYPELIB_PATH:-}" ]]; then
    export GI_TYPELIB_PATH="${typelibs}:${GI_TYPELIB_PATH}"
  else
    export GI_TYPELIB_PATH="${typelibs}"
  fi
  export NO_ALBUMENTATIONS_UPDATE=1
fi
cd "$ROOT"
if [[ "$(uname -s)" == "Linux" ]]; then
  # GNU wl-clipboard, not the conda-forge Rust build. See the script.
  "$ROOT/scripts/install_linux_clipboard.sh" || echo "GNU wl-clipboard is not available" >&2
fi
exec "$PYTHON" -m texgrab "$@"
