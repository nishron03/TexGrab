# Project State

## Current Status

Linux port on branch `linux` (from `main`). TexGrab is not running. The GNOME custom shortcut was removed on quit (`custom-keybindings` is `@as []`). No `texgrab.sock` is left.

Session on this machine, 2026-09-29:

- `uname -a`: Linux Wintermute 6.17.0-1032-oem #32-Ubuntu SMP PREEMPT_DYNAMIC Fri Jul 24 05:46:26 UTC 2026 x86_64 GNU/Linux
- `XDG_SESSION_TYPE=wayland`
- `XDG_CURRENT_DESKTOP=ubuntu:GNOME`
- `DESKTOP_SESSION=ubuntu`
- `XDG_RUNTIME_DIR=/run/user/1000`
- `XDG_CONFIG_HOME` and `XDG_STATE_HOME` unset (defaults `~/.config` and `~/.local/state`)
- conda 26.1.1, base `/home/nish/miniconda3`
- Present: `notify-send`, `gsettings`, `busctl`
- Absent on the system PATH at the start: `wl-copy`, `wl-paste`, `xclip`, `xsel`, `grim`, `slurp`, `spectacle`, `gnome-screenshot`, `maim`
- Screenshot portal is present. `org.freedesktop.portal.GlobalShortcuts` is not.
- GNOME screenshot chords, left alone: `show-screenshot-ui=['Print']`, `screenshot=['<Shift>Print']`, `screenshot-window=['<Alt>Print']`. Ctrl+Alt+Shift+S was free and is the default.

## Linux bindings

- Wayland, and GlobalShortcuts missing: one GNOME custom keybinding named TexGrab, command `<conda>/bin/python3.11 -m texgrab --trigger`, binding `<Control><Alt><Shift>s`. Other custom shortcuts are kept. Quit removes only the TexGrab path. gsettings is `/usr/bin/gsettings`. The conda glib `gsettings` writes a keyfile GNOME Shell does not read.
- X11 (`XDG_SESSION_TYPE=x11` only): in-process `XGrabKey`. Not used on this Wayland session.
- GlobalShortcuts portal is implemented and was tried. Bind failed because the interface is absent. The socket `$XDG_RUNTIME_DIR/texgrab.sock` is always listening. `texgrab --trigger` sends `snip`.
- Sway and Hyprland print a bind line and do not edit the user's config. KDE writes one kglobalaccel entry. Neither was run here.
- Capture: a silent portal frame, then TexGrab's own drag overlay (release crops, Escape cancels). The GNOME screenshot UI is not the selector. grim/slurp, spectacle, gnome-screenshot, and maim stay as fallbacks and are absent here. The portal Response signal is matched without the well-known bus name, because that comparison dropped the reply and left the snip running.
- Clipboard: GNU wl-clipboard 2.2.1 (`wl-copy` / `wl-paste`), installed by `scripts/install_linux_clipboard.sh` into the env bin. conda-forge `wl-clipboard-rs` 0.9.4 cannot speak to this compositor.

## Torch

`torch==2.14.0+cpu`, `torchvision==0.29.0+cpu`, `pix2tex==0.1.4`, Python 3.11.16. `torch.cuda.is_available()` is false. The PyPI `torch==2.14.0` manylinux wheel depends on CUDA 13, so the CPU index `https://download.pytorch.org/whl/cpu` is used. Recorded in `requirements-linux.lock.txt`.

## Manual steps actually run

See `tests/MANUAL-linux.md`. Passed earlier: startup reaches `status Ready`; quit removes the shortcut, the socket, and the process; a second `./scripts/run.sh` exits as already running. On 2026-09-29 the user tried the GNOME screenshot UI: selecting a region did not finish the snip, Enter put the image on the clipboard, and Escape left `shortcut ignored; snip already running` (13:06:12). That UI is no longer the selector. A silent frame plus the drag overlay was checked from this session for size, Escape, a second selection, and an unchanged clipboard. A person has not yet dragged a real equation, pressed Print, used Test OCR, or changed the shortcut.

`pytest`: 56 passed, 2 skipped (the Mac pasteboard and screencapture modules). `--test-ocr` on `sample_equation.png` printed `E=m C^{2}+\int_{0}^{1}\!X^{2}\,Q X`. With `--clipboard`, `wl-paste -n -t text/plain` printed that same line only.

## Mac architecture (unchanged)

Menu-bar app (`rumps`) on Python 3.11.16 in conda env `latex-snipper`. The Mac tree still uses Carbon, `screencapture` without `-c`, NSPasteboard, and `osascript`. Darwin config and logs stay under `~/Library`. A Mac `conda env create -f environment.yml` still installs `requirements.txt` (common + macOS pins).

- Global shortcut: Carbon `RegisterEventHotKey` for ⌘⌃⇧S (`kVK_ANSI_S` = 0x01, modifiers command `1<<8`, shift `1<<9`, control `1<<12`). No Accessibility permission. The callback returns immediately and starts a worker.
- Capture: `screencapture -i -x -t png <private temp file>`. No `-c`. The file is deleted before OCR. Cancel (no file, no stderr) is silent. A non-zero exit with stderr raises `CaptureError`.
- OCR: `Pix2TexEngine` behind `OCREngine`. Upstream `LatexOCR.__call__` copies to the clipboard as a side effect; that copy is disabled for the duration of `recognize`, so only `clipboard.write_text` writes, and only after a non-empty string.
- Clipboard: `NSPasteboard.clearContents` then a single `public.utf8-plain-text` value.
- Notifications: `osascript` display notification. Success: "LaTeX copied to clipboard". OCR or capture failure: "LaTeX OCR failed". Missing Screen Recording: "Screen Recording permission is required".
- Config: `~/Library/Application Support/TexGrab/config.json`.
- Logs: `~/Library/Logs/TexGrab/texgrab.log`. Width, height, and character counts. The LaTeX text is logged only at DEBUG.
- Weights: `/opt/anaconda3/envs/latex-snipper/lib/python3.11/site-packages/pix2tex/model/checkpoints/` (`weights.pth` 97.4 MB, `image_resizer.pth` 18.5 MB). Downloaded once on 2026-09-24. Later loads use that cache.
- Package: `dist/TexGrab.app` is a menu-bar agent (`LSUIElement`) whose executable runs the conda interpreter. It is not a vendored PyTorch bundle.

Python 3.14 (Homebrew) is unused. pix2tex 0.1.4 is installed with the pins in `requirements.txt` (torch 2.14.0, torchvision 0.29.0). `requirements.lock.txt` is the full freeze.

## Completed

- 2026-09-24: Inspected the machine. macOS 26.6.2 arm64, Anaconda 24.1.2, Swift 6.3 command-line tools, empty `TexGrab/`.
- 2026-09-24: Created conda env `latex-snipper` (Python 3.11.16) and installed pix2tex 0.1.4 without the `[gui]` extra.
- 2026-09-24: Phase 1. `scripts/smoke_ocr.py` on a matplotlib mathtext rendering of `E = mc^{2} + \int_{0}^{1} x^{2}\, dx` returned `E=m C^{2}+\int_{0}^{1}\!X^{2}\,Q X` in about 38 seconds, including the weight download. A second load used the cache (no second download).
- 2026-09-24: Phase 2. `pytest` — 22 passed. Covers preprocess, pipeline errors, clipboard round-trip with pasteboard restore, capture command shape (no `-c`, temp dir removed), shortcut mask, conda prefix, and a real pix2tex call that does not change the pasteboard. `--test-ocr --clipboard` wrote that same LaTeX string and nothing else.
- 2026-09-24: Phase 3. `RegisterEventHotKey` for ⌘⌃⇧S returns success and `UnregisterEventHotKey` succeeds. A synthesized keystroke could not be sent: `osascript` exit 1002, "osascript is not allowed to send keystrokes."
- 2026-09-24: Phase 4. `screencapture -x -R 0,0,80,40` produced an 80×40 PNG after Screen Recording was available. The first attempt, before the grant, failed with `could not create image from rect`. The interactive `-i` overlay was not driven from this session.
- 2026-09-24: Phase 5 and 6. `SnipService` tests cover cancel (no notification, no clipboard write), capture errors, success, overlapping snips, and suppressed notifications. A live `python -m texgrab` logged `shortcut registered ⌘⌃⇧S`, `screen recording permission granted=True`, and `pix2tex model ready`, then was stopped. The menu contains TexGrab, Status, Shortcut: ⌘⌃⇧S, Test OCR, Preferences (Show notifications, Debug logging), a separator, and Quit.
- 2026-09-24: Phase 7. `scripts/build_app.sh` wrote `dist/TexGrab.app`. `plutil -lint` passed and `LSUIElement` is true. Login-item script is `scripts/install_login_item.sh`. It was not run.

## In Progress

The Linux steps that still need a person are in `tests/MANUAL-linux.md`: a real equation drag, Print, the tray Test OCR item, and the shortcut recorder. The Mac pass in `tests/MANUAL.md` was not re-run on this machine.

## Known Issues

- Screen Recording is granted to the process that launches TexGrab, not to Python in the abstract. Before it was granted, `screencapture` exited 1 with `could not create image from rect` and `CGPreflightScreenCaptureAccess` was false. Grant it to Terminal or iTerm when using `scripts/run.sh`, or to TexGrab.app when using the bundle. If a rebuilt app is listed but still cannot capture, remove the entry and add it again.
- The interactive region UI and a real ⌘⌃⇧S press were not exercised here. Synthetic keystrokes are blocked for `osascript`.
- The bundled sample is matplotlib mathtext, not a Computer Modern render. pix2tex misread it as `E=m C^{2}+\int_{0}^{1}\!X^{2}\,Q X`. The pipeline is working; accuracy on that fixture is not. Tight crops of printed equations are what the model was trained on. This project does not train it.
- pix2tex runs on CPU. A cold process spends several seconds importing torch. Warm recognition of one equation is a few seconds.
- Matrices: the checkpoint is capped at about 192 pixels of height, and its default resizer assumes one line. As of 2026-09-24 a fenced grid (both sides) is scaled to about 40 pixels per row and recognized with `resize=False`. Cell-by-cell OCR was tried and rejected: isolated digits came back as unrelated symbols. Unfenced matrices, and grids with many rows, can still collapse. A parenthesized fraction is left on the normal path.
- `LatexOCR` sets the root logger to FATAL during construction. `Pix2TexEngine.load` restores the previous level. Albumentations emits deprecation warnings on first import; they are not fatal.
- The `.app` depends on `/opt/anaconda3/envs/latex-snipper` and on `pip install -e .` in that env. Moving the checkout breaks the editable install until it is reinstalled.
- Launch-at-login is documented and scripted, not installed.

## Next Steps

1. From Terminal: `./scripts/run.sh`. Grant Screen Recording to Terminal if the menu says `Needs Screen Recording`.
2. Walk `tests/MANUAL.md`: shortcut from another app, Escape cancels, a real equation pastes as text, ⌘⇧4 still takes a normal screenshot, Quit leaves no process.
3. If the dev launch is right, `open dist/TexGrab.app` and grant Screen Recording to TexGrab itself. Then `./scripts/install_login_item.sh` if it should start at login.

## Development Log

### 2026-09-24

- Read pix2tex `cli.py`. `LatexOCR.__call__` always tries `pandas.io.clipboard.copy`. TexGrab patches that to a no-op during `recognize` so a failed or empty result cannot clear the clipboard. The real-model test asserts the pasteboard change count is unchanged across `recognize`, and a separate `--clipboard` run asserts the pasted text equals the printed LaTeX.
- Confirmed against the macOS 26.5 SDK headers: `kEventHotKeyPressed` is 5, `kVK_ANSI_S` is 0x01, modifier bits as above. Live `RegisterEventHotKey` succeeded.
- `conda env create -f environment.yml` succeeded. Resolved stack includes torch 2.14.0, torchvision 0.29.0, transformers 5.17.0, timm 0.5.4, numpy 2.4.6, pandas 3.0.6, Pillow 12.3.0, rumps 0.4.0, PyObjC 12.2.2. Importing `pix2tex.cli` works on that stack. `torch.load` of the official checkpoint succeeded without a `weights_only` shim.
- First smoke test downloaded the checkpoints into the pix2tex package directory and printed a non-empty LaTeX string. `pytest`: 22 passed in 10.85 seconds (model already cached).
- Screen capture permission was false at the start of the session (`could not create image from rect`). A later `python -m texgrab` logged `screen recording permission granted=True`, and `screencapture -R` then wrote an 80×40 PNG, which was deleted without being inspected.
- Menu-bar process started, reached `pix2tex model ready`, and was stopped with SIGTERM so this session would not leave a shortcut registered. Build of `dist/TexGrab.app` verified with `plutil`.
- 01:33: Started `scripts/run.sh`. Log: shortcut registered, screen recording granted, model ready. The user stopped that process; it was not restarted.
- 02:04: Matrix path. Reading each cell failed (a clean digit `1` became `\bigcup_{i}`). Scaling the whole fenced grid to ~80px tall and calling `LatexOCR` with `resize=False` returned the correct `1 & 2 \\ 3 & 4` array. A fraction and a one-line formula still take the normal path. `tests/test_matrix.py`: 7 passed.
- 2026-09-25: Git repository created. `main` is the initial snipper. Shortcut editing is on branch `custom-hotkey`: Preferences → Change shortcut…, saved in the existing config file, Carbon hotkey replaced live. ⌘ or ⌃ is required.
- 2026-09-25: The recorder window opened but received no keys. A status-item app is not active, and the menu closing returns focus to the previous app. The recorder now waits until the menu has closed, switches to a regular activation policy, and listens with a local key monitor. Escape and the new chord are handled there. The previous activation policy is restored when the window closes.
- 2026-09-25: Shift was never disallowed. ⌘D records because it is a Command key-equivalent. ⌘⌃⇧S is delivered as a normal keyDown, which the window was not receiving. The recorder now takes that path too, shows the modifiers being held, and Preferences has "Reset shortcut to ⌘⌃⇧S".
- 2026-09-25: README rewritten around install and everyday use. `scripts/run.sh` looks up the `latex-snipper` env instead of assuming `/opt/anaconda3`. Published as a public GitHub repo.
- 2026-09-29: The GNOME interactive screenshot UI left the snip running after Escape and copied an image on Enter. Capture now takes a non-interactive portal frame and crops it with TexGrab's drag overlay. The portal Response match no longer compares the well-known bus name, which had dropped the reply.
