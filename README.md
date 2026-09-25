# TexGrab

TexGrab is a menu-bar utility for macOS. Press **⌘⌃⇧S** in any application, drag a rectangle around an equation, and the LaTeX is copied to the clipboard. Paste it with ⌘V.

The screenshot never goes on the clipboard. TexGrab does not watch the clipboard, so a normal screenshot (⌘⇧3, ⌘⇧4, ⌘⇧5) is unaffected. Recognition runs locally with [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR). No image is uploaded.

## Architecture

```
⌘⌃⇧S
  Carbon RegisterEventHotKey     (no Accessibility permission)
        │
        ▼
screencapture -i -t png <temp file>
        │  no -c flag; the pasteboard is not used
        ▼
image in memory, temp file deleted
        │
        ▼
pix2tex (local weights)
        │
        ▼
NSPasteboard writes the LaTeX string only
        │
        ▼
notification: "LaTeX copied to clipboard"
```

The OCR engine sits behind a small protocol (`texgrab.ocr.base.OCREngine`). A different local engine can replace `Pix2TexEngine` without changing capture or the clipboard.

## Requirements

- Apple Silicon Mac. Developed on macOS 26.6 (arm64).
- Anaconda or Miniconda. This machine uses `/opt/anaconda3`.
- Screen Recording permission for the process that launches TexGrab.
- Network access the first time pix2tex downloads its checkpoint. After that, recognition is offline.

Do not use the system Python. Homebrew Python on this machine is 3.14, and pix2tex's pinned stack (`timm==0.5.4`) is installed into Python 3.11 instead.

Accessibility permission is not required. The shortcut uses Carbon's `RegisterEventHotKey`, not a keyboard event tap.

## Conda environment

From the `TexGrab` directory:

```bash
conda env create -f environment.yml
conda activate latex-snipper
```

`environment.yml` installs Python 3.11 from conda-forge and then pip-installs `requirements.txt` inside that environment. Nothing is installed into the base environment or the system Python.

Confirm the interpreter:

```bash
python -c "import sys; print(sys.prefix); print(sys.version)"
```

The prefix must end in `latex-snipper` and the version must be 3.11.x.

Recreate the environment from scratch:

```bash
conda env remove -n latex-snipper
conda env create -f environment.yml
```

## Installation

Inside the activated environment, from the `TexGrab` directory:

```bash
pip install -e .
```

That registers the `texgrab` package without copying it out of this checkout. Re-run it after moving the directory.

The first real recognition downloads the pix2tex checkpoint into the location pix2tex chooses (logged as `checkpoint=` in `~/Library/Logs/TexGrab/texgrab.log`, typically under the pix2tex package data or `~/Library/Application Support/pix2tex`).

## Running in development

```bash
conda activate latex-snipper
./scripts/run.sh
```

`scripts/run.sh` ignores your shell's Python and executes `/opt/anaconda3/envs/latex-snipper/bin/python -m texgrab`.

Check the interpreter without opening the menu:

```bash
python -m texgrab --check
```

Recognize one image file, without the menu bar:

```bash
python scripts/smoke_ocr.py path/to/equation.png
python scripts/smoke_ocr.py path/to/equation.png --clipboard
```

`--clipboard` copies the LaTeX string and nothing else. Without it, the clipboard is not modified.

## macOS permissions

Screen Recording is required. macOS grants it to the **host process**, not to Python in the abstract.

While you run `scripts/run.sh` from a terminal, enable Screen Recording for **Terminal** or **iTerm**. If you launch it from an editor's integrated terminal, enable that editor (Cursor, for example). After `scripts/build_app.sh`, enable **TexGrab.app** itself. A grant for Terminal does not cover the `.app`, and the reverse is also true.

1. Open System Settings → Privacy & Security → Screen Recording.
2. Enable the process named above. If capture still fails after a rebuild, remove the entry and add it again. macOS ties the grant to the app's signature and path.
3. Quit and relaunch TexGrab.

The app calls `CGRequestScreenCaptureAccess` on startup, which prompts the first time. If you have already denied it, macOS will not prompt again; use System Settings.

TexGrab does not request Accessibility or Input Monitoring.

## How to use

1. Start TexGrab. The menu bar shows **TexGrab**. The menu reads:

   - TexGrab
   - Status: Ready (or Loading model…, Recognizing…, Needs Screen Recording)
   - Shortcut: ⌘⌃⇧S
   - Test OCR
   - Preferences → Show notifications, Debug logging
   - Quit

2. Focus whatever you are reading (PDF, browser, Obsidian, Preview).
3. Press **⌘⌃⇧S**.
4. Drag a rectangle around the equation. Escape cancels and does not change the clipboard.
5. When the notification says **LaTeX copied to clipboard**, press ⌘V.

Test OCR runs the bundled sample equation through pix2tex and copies that LaTeX, so you can check the model without a capture.

While a snip is running the menu-bar title becomes **TexGrab…**. A second shortcut press during that time is ignored.

## Shortcut

The default is **⌘⌃⇧S** (Command, Control, Shift, S). It was chosen because it is not ⌘⇧3, ⌘⇧4, or ⌘⇧5.

To change it, edit `~/Library/Application Support/TexGrab/config.json` and relaunch:

```json
{
  "shortcut_key": "s",
  "shortcut_command": true,
  "shortcut_control": true,
  "shortcut_shift": true,
  "shortcut_option": false,
  "notifications": true,
  "debug": false
}
```

`shortcut_key` is a single character from the US ANSI virtual-key set (letters, digits, and `-` `=` `[` `]` `\\` `;` `'` `,` `.` `/` `` ` ``). The key code is the physical key, not the character produced when Shift is held.

Preferences in the menu toggles notifications and debug logging. Those two are saved to the same file.

## Logging

Logs: `~/Library/Logs/TexGrab/texgrab.log` (rotated, three backups).

They record shortcut activation, capture success or cancel, image width and height, OCR start and end, the character count, clipboard success or failure, and permission problems. They do not record pixels. The LaTeX string itself is written only when debug logging is on.

## Troubleshooting

**Status stays on "Needs Screen Recording", or the log says `could not create image from rect`.**
The launching app does not have Screen Recording. `screencapture` exits with that message and does not write a file. See the permissions section. The log line is `screen recording permission granted=False`.

**The shortcut does nothing.**
Confirm the menu says `Shortcut: ⌘⌃⇧S` and not `failed to register`. Registration errors include the Carbon status code in the log. The shortcut only works while TexGrab is running. It does not require TexGrab to be the focused app.

**OCR fails immediately with an import or checkpoint error.**
Read the traceback in the log. The first run needs network access to download weights. A later `Model failed to load` status means `LatexOCR()` raised; the traceback is the useful part, not the notification.

**The LaTeX is wrong.**
pix2tex is best on a tight crop of a printed equation, not a photo of handwriting and not a whole page. Select just the formula. This project does not train or fine-tune the model. Test OCR uses a matplotlib mathtext sample, which is not the font the model was trained on, so that menu item can return imperfect LaTeX even when the pipeline is healthy. On this machine it returned `E=m C^{2}+\int_{0}^{1}\!X^{2}\,Q X` for `E = mc^{2} + \int_{0}^{1} x^{2}\, dx`.

**Matrices.**
Include the brackets or parentheses in the selection. TexGrab notices a fenced grid and reads it at a height the model can handle, instead of squashing it into one line. A 2 by 2 bracket matrix of digits comes back as `\begin{array}` with the right entries. A matrix with many rows is still squeezed into the model's 192-pixel limit, and a grid with no fences is read as an ordinary formula. Restart TexGrab after updating so this path is loaded.

**The clipboard contains an image.**
TexGrab never writes an image type. If ⌘V pastes an image, the shortcut flow did not complete and some other capture still owns the pasteboard. `pbpaste` after a successful snip prints the LaTeX.

**`conda env create` fails on pix2tex.**
Stay on Python 3.11 in this environment. Do not retry the install with system Python 3.14. If `timm==0.5.4` or `torch.load` fails, the resolution that worked is recorded in `requirements.lock.txt` and `PROJECT_STATE.md`.

## Packaging

The `.app` is a launcher around the conda environment. PyTorch is not vendored into the bundle; that kind of freeze is large and brittle. The machine that runs the app needs the `latex-snipper` environment.

```bash
conda activate latex-snipper
pip install -e .
./scripts/build_app.sh
open dist/TexGrab.app
```

The bundle is a menu-bar agent (`LSUIElement`), so it does not show a Dock icon. Grant Screen Recording to **TexGrab** after the first launch.

Moving this checkout breaks the editable install. Run `pip install -e .` again from the new path, then rebuild the app.

### Launch at login

Build the app, then either:

- System Settings → General → Login Items, and add `dist/TexGrab.app`, or
- `./scripts/install_login_item.sh`

The login item points at that `.app` path. Rebuilds in place keep the same path. If you move the checkout, remove the old login item and add the new one.

## Tests

With the conda environment activated and the package installed:

```bash
pytest
```

That includes one real pix2tex inference on the bundled sample equation. The selection overlay and the global shortcut are covered by `tests/MANUAL.md` because they need a person at the keyboard.

## Project memory

`PROJECT_STATE.md` is the development log: what works, what does not, and what was tried. Read it before changing the capture or OCR path.
