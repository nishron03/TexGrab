# TexGrab

TexGrab is a macOS menu-bar utility. Select an equation anywhere on the screen and the LaTeX is copied to the clipboard. Paste it with ⌘V.

Recognition runs on your Mac with [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR). The image is not uploaded. TexGrab does not watch the clipboard, so a normal screenshot (⌘⇧3, ⌘⇧4, ⌘⇧5) is left alone.

## Install

You need an Apple Silicon Mac and [Anaconda or Miniconda](https://docs.conda.io/en/latest/miniconda.html). The app uses its own conda environment, `latex-snipper` (Python 3.11). Do not install it into the system Python.

```bash
git clone https://github.com/nishron03/TexGrab.git
cd TexGrab
conda env create -f environment.yml
conda activate latex-snipper
pip install -e .
./scripts/run.sh
```

`environment.yml` installs Python, then pip-installs PyTorch, pix2tex, and the menu-bar libraries inside that environment only.

Check that the right interpreter is active:

```bash
python -m texgrab --check
```

The prefix must end in `latex-snipper` and the version must be 3.11. The first snip downloads the pix2tex weights (about 120 MB). After that, recognition works offline.

To recreate the environment:

```bash
conda env remove -n latex-snipper
conda env create -f environment.yml
conda activate latex-snipper
pip install -e .
```

## Allow screen capture

macOS will not give TexGrab the screen until you allow **Screen Recording** for the app that launched it.

1. Start TexGrab once (`./scripts/run.sh`).
2. Open **System Settings → Privacy & Security → Screen Recording**.
3. Enable **Terminal** or **iTerm** if you started it from a terminal. If you started it from an editor's terminal, enable that editor instead.
4. Quit TexGrab and start it again.

If you later open `dist/TexGrab.app`, grant Screen Recording to **TexGrab** itself. A grant for Terminal does not cover the app, and the reverse is also true. If capture still fails after a rebuild, remove the entry in that list and add it again.

TexGrab does not need Accessibility or Input Monitoring.

## Use

1. TexGrab appears in the menu bar. Wait until the menu says **Status: Ready**. The first launch says **Loading model…** while the weights load.
2. Go to the equation (a PDF, a browser, Obsidian, anywhere).
3. Press **⌘⌃⇧S** (Command, Control, Shift, S).
4. Drag a tight rectangle around the equation. Escape cancels and does not change the clipboard.
5. When the notification says **LaTeX copied to clipboard**, press ⌘V.

Only the LaTeX text is copied. While a snip is running the menu-bar title is **TexGrab…**, and a second press is ignored.

**Test OCR** in the menu runs a built-in sample and copies that LaTeX, so you can check the model without selecting anything. The sample is not the font pix2tex was trained on, so that result can be imperfect even when a real equation works. Crop printed equations tightly.

**Matrices.** Include the brackets or parentheses in the selection. TexGrab reads a fenced grid at a size the model can handle. A large matrix, or one with no fences, can still come out wrong. Snip those a few rows at a time.

### Change the shortcut

The default is **⌘⌃⇧S**, chosen so it is not ⌘⇧3, ⌘⇧4, or ⌘⇧5.

- **Preferences → Change shortcut…** asks you to press a new combination. ⌘ or ⌃ is required, so the shortcut cannot swallow ordinary typing. Shift and Option can be added, so ⌘⌃⇧S itself is allowed. The window shows the modifiers you are holding. Escape cancels.
- **Preferences → Reset shortcut to ⌘⌃⇧S** puts the original combination back.
- **Preferences → Show notifications** and **Debug logging** are saved as well.

The choice is stored in `~/Library/Application Support/TexGrab/config.json` and kept across restarts.

### Quit

Choose **Quit** in the TexGrab menu. The shortcut does nothing after that.

## Optional: a menu-bar app, and launch at login

This builds a small `.app` that starts the same conda environment. It does not show a Dock icon.

```bash
conda activate latex-snipper
pip install -e .
./scripts/build_app.sh
open dist/TexGrab.app
```

Grant Screen Recording to **TexGrab** after the first launch.

To open it at login, add `dist/TexGrab.app` in **System Settings → General → Login Items**, or run `./scripts/install_login_item.sh`. If you move the project folder, remove the old login item and add the new app.

## Troubleshooting

**The menu says "Needs Screen Recording", or the log says `could not create image from rect`.**
Screen Recording is not granted for the process that launched TexGrab. See the section above.

**The shortcut does nothing.**
TexGrab must be running. The menu should show your shortcut, not "failed to register". It works while another app is focused.

**The model fails to load.**
The first run needs a network connection to download the weights. The traceback is in `~/Library/Logs/TexGrab/texgrab.log`. The notification only says that OCR failed.

**The LaTeX is wrong.**
Select just the formula, not the whole page. pix2tex is best on a tight crop of a printed equation. Handwriting is weak. This project does not train the model.

**⌘V pastes an image.**
TexGrab never puts the screenshot on the clipboard. If you get an image, the snip did not finish and some other capture still owns the pasteboard. After a successful snip, `pbpaste` prints the LaTeX.

## How it works

```
shortcut
  Carbon global hotkey (no Accessibility permission)
        │
        ▼
native rectangle selection, saved to a private temp file
        │  the clipboard is not used
        ▼
image in memory, temp file deleted
        │
        ▼
pix2tex, on this Mac
        │
        ▼
clipboard receives the LaTeX string only
```

Logs are at `~/Library/Logs/TexGrab/texgrab.log`. They record sizes and whether each step succeeded. They do not record the captured image. Turn on **Debug logging** in Preferences if you also want the LaTeX text in the log.

`PROJECT_STATE.md` is the development log. `tests/MANUAL.md` is the click-through check for the shortcut and the selection overlay. With the conda environment active, `pytest` runs the automated tests.
