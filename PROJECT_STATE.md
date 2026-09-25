# Project State

## Current Status

TexGrab is not running. On branch `custom-hotkey` (baseline is `main`), Preferences → Change shortcut… records a new global hotkey and registers it immediately. The default remains ⌘⌃⇧S. A chord must include ⌘ or ⌃. Fenced matrices are still scaled and recognized with the single-line resizer off.

## Architecture

Menu-bar app (`rumps`) on Python 3.11.16 in conda env `latex-snipper` (`/opt/anaconda3/envs/latex-snipper`). Project root: `/Users/nishron/PetProjects/TexGrab`.

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

Nothing is mid-implementation. The remaining check is the manual pass in `tests/MANUAL.md`: press ⌘⌃⇧S from another app, drag a rectangle, paste LaTeX, and confirm an ordinary ⌘⇧4 screenshot is untouched.

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
