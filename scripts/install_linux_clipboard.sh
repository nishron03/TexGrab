#!/bin/bash
# Install GNU wl-clipboard into the latex-snipper env and ~/.local/bin.
# GNOME does not implement wlr-data-control. The conda-forge package
# wl-clipboard-rs speaks only that protocol, so it cannot copy or paste here.
# This downloads the Ubuntu wl-clipboard package and extracts the two binaries.
# It does not use sudo and it does not change the system package database.
set -euo pipefail

if command -v wl-copy >/dev/null 2>&1 && wl-copy --version 2>&1 | grep -q 'wl-clipboard'; then
  system_ok=1
else
  system_ok=0
fi

ENV_BIN=""
if [[ -n "${CONDA_PREFIX:-}" && "$(basename "$CONDA_PREFIX")" == "latex-snipper" ]]; then
  ENV_BIN="$CONDA_PREFIX/bin"
elif command -v conda >/dev/null 2>&1; then
  base="$(conda info --base 2>/dev/null || true)"
  if [[ -n "$base" && -d "$base/envs/latex-snipper/bin" ]]; then
    ENV_BIN="$base/envs/latex-snipper/bin"
  fi
fi
if [[ -z "$ENV_BIN" && -d "$HOME/miniconda3/envs/latex-snipper/bin" ]]; then
  ENV_BIN="$HOME/miniconda3/envs/latex-snipper/bin"
fi

need_install=0
if [[ "$system_ok" -eq 0 ]]; then
  need_install=1
fi
if [[ -n "$ENV_BIN" ]]; then
  if [[ ! -x "$ENV_BIN/wl-copy" ]] || ! "$ENV_BIN/wl-copy" --version 2>&1 | grep -q 'wl-clipboard'; then
    need_install=1
  fi
fi
if [[ "$need_install" -eq 0 ]]; then
  exit 0
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
(
  cd "$workdir"
  apt-get download wl-clipboard
  dpkg-deb -x wl-clipboard_*.deb extracted
)
install -d "$HOME/.local/bin"
install -m 0755 "$workdir/extracted/usr/bin/wl-copy" "$HOME/.local/bin/wl-copy"
install -m 0755 "$workdir/extracted/usr/bin/wl-paste" "$HOME/.local/bin/wl-paste"
if [[ -n "$ENV_BIN" ]]; then
  install -m 0755 "$workdir/extracted/usr/bin/wl-copy" "$ENV_BIN/wl-copy"
  install -m 0755 "$workdir/extracted/usr/bin/wl-paste" "$ENV_BIN/wl-paste"
fi
echo "Installed GNU wl-clipboard into ${ENV_BIN:-$HOME/.local/bin}"
