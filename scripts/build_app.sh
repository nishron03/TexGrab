#!/bin/bash
# Build a menu-bar .app that launches the latex-snipper interpreter.
# The package must already be installed in that env (pip install -e .).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="/opt/anaconda3/envs/latex-snipper/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Missing $PYTHON. Create the conda env first." >&2
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
