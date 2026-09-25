#!/bin/bash
# Register dist/TexGrab.app as a login item. Build the app first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$ROOT/dist/TexGrab.app}"
if [[ ! -d "$APP" ]]; then
  echo "App not found: $APP" >&2
  echo "Run scripts/build_app.sh first." >&2
  exit 1
fi
osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP\", hidden:false}"
echo "Added login item: $APP"
