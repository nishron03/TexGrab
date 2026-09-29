#!/bin/bash
# Print an XDG autostart entry for TexGrab. Nothing is installed unless
# --install is passed. Do not pass --install unless you want TexGrab at login.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/texgrab.desktop"
CONTENT="[Desktop Entry]
Type=Application
Name=TexGrab
Comment=Copy an equation as LaTeX
Exec=${ROOT}/scripts/run.sh
Terminal=false
X-GNOME-Autostart-enabled=true"
if [[ "${1:-}" == "--install" ]]; then
  mkdir -p "$(dirname "$DEST")"
  printf '%s\n' "$CONTENT" > "$DEST"
  echo "Wrote $DEST"
  exit 0
fi
echo "Autostart is not enabled. To write the file, run: $0 --install"
echo
printf '%s\n' "$CONTENT"
