#!/bin/bash
# Build a menu-bar .app that launches the latex-snipper interpreter.
# The package must already be installed in that env (pip install -e .).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON=""
base=""
if [[ -n "${CONDA_EXE:-}" ]]; then
  base="$(cd "$(dirname "$CONDA_EXE")/.." && pwd)"
elif command -v conda >/dev/null 2>&1; then
  base="$(conda info --base 2>/dev/null || true)"
fi
candidates=()
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
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "Could not find the latex-snipper conda environment. Create it first." >&2
  exit 1
fi
APP="$ROOT/dist/TexGrab.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$ROOT/packaging/Info.plist" "$APP/Contents/Info.plist"
cat > "$APP/Contents/MacOS/TexGrab" <<EOF
#!/bin/bash
export PYTHONUNBUFFERED=1
exec "$PYTHON" -m texgrab
EOF
chmod +x "$APP/Contents/MacOS/TexGrab"
echo "Built $APP"
echo "Grant Screen Recording to TexGrab.app, not only to your terminal."
