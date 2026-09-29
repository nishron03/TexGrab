# TexGrab

TexGrab is a tray utility. Point it at an equation anywhere on the screen and it copies only the LaTeX to the clipboard.

Recognition runs locally with [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR). The image is not uploaded. TexGrab does not watch the clipboard, so the desktop's normal screenshot shortcut still takes a normal screenshot.

## Linux

This port runs on Python 3.11 in a conda environment named `latex-snipper`. It was brought up on Ubuntu GNOME 46, Wayland (`XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=ubuntu:GNOME`). An X11 session grabs the chord in-process. Other Wayland desktops try the GlobalShortcuts portal, then one desktop shortcut.

Do not install it into the distro Python or conda base.

```bash
git clone https://github.com/nishron03/TexGrab.git
cd TexGrab
conda env create -f environment-linux.yml
conda activate latex-snipper
pip install -e .
./scripts/run.sh
```

`environment-linux.yml` installs Python 3.11, GTK, and the shared pins (pix2tex 0.1.4, Pillow, pytest). On Linux, torch is the CPU build `2.14.0+cpu` because the matching PyPI wheel depends on CUDA. The resolved set is `requirements-linux.lock.txt`.

Check the interpreter:

```bash
python -m texgrab --check
```

The prefix's last component must be `latex-snipper`, Python must be 3.11, and texgrab must be 0.1.0. The first recognition downloads `weights.pth` and `image_resizer.pth` from the pix2tex `v0.0.1` release if they are not already present. After that, recognition works offline.

### Allow screen capture

Capture uses the xdg-desktop-portal Screenshot dialog (an interactive region selection). The image is written to a private temp file and deleted before OCR. Nothing is copied to the clipboard by the capture tool.

The first snip can show a permission dialog. Allow screen capture for the app that launched TexGrab (the terminal, or TexGrab if you started it from a menu). If you dismiss that dialog, the status line says **Needs screen capture** and the notification says **Screen capture permission is required**. Escape, or closing the selector without a region, is silent: no notification, and the clipboard is unchanged.

This GNOME session does not offer the GlobalShortcuts portal. TexGrab registers one custom shortcut instead. It does not replace Print, Shift+Print, or Alt+Print.

### Use

1. Start `./scripts/run.sh`. Wait until the tray says **Status: Ready**. The first launch says **Loading model…** while torch imports.
2. Focus the equation.
3. Press **Ctrl+Alt+Shift+S**.
4. Drag a tight rectangle around the equation. Include the brackets when the equation is a matrix.
5. When the notification says **LaTeX copied to clipboard**, paste. The paste is text.

A second press while a snip is running is ignored. While a snip is in progress the tooltip is **TexGrab…**.

**Test OCR** runs the built-in sample and copies that LaTeX. The sample is matplotlib mathtext, not the font pix2tex was trained on, so that result can be imperfect even when a printed equation works.

**Matrices.** Include the fences. A fenced grid of at least two rows is scaled to about 40 pixels per row and recognized as one image. A parenthesized fraction stays on the normal path.

### Change the shortcut

The default is **Ctrl+Alt+Shift+S**, chosen because it is not Print or Super+Shift+S.

- **Preferences → Change shortcut…** waits until the menu has closed, then asks for a chord. Ctrl or Super is required. Alt and Shift can be added, so Ctrl+Alt+Shift+S itself is allowed. A bare letter, and Alt+Shift with no Ctrl or Super, are rejected. The window shows the modifiers you are holding. Escape keeps the old shortcut.
- **Preferences → Reset shortcut to Ctrl+Alt+Shift+S** puts the default back.
- If the new chord cannot be registered, the previous one is restored.

On this GNOME session the choice is one custom keybinding whose command is `python -m texgrab --trigger`. Changing it in Preferences updates that one entry and leaves your other custom shortcuts in place. Quit removes only the TexGrab entry.

The choice is stored in `$XDG_CONFIG_HOME/texgrab/config.json` (default `~/.config/texgrab/config.json`).

On Sway or Hyprland, TexGrab prints a `bindsym` or `bind` line for you to paste. It does not edit those config files.

### Quit

Choose **Quit**, or send the process SIGTERM. The shortcut is unregistered, `$XDG_RUNTIME_DIR/texgrab.sock` is removed, and the icon goes away.

### Tray icon

The icon uses AppIndicator. On GNOME, install and enable **AppIndicator and KStatusNotifierItem Support** (`gnome-shell-extension-appindicator`) if the top bar has no TexGrab icon. TexGrab still runs, and `python -m texgrab --trigger` still snips.

### Clipboard tools

Wayland copy and paste use GNU `wl-copy` and `wl-paste` (`text/plain` only). GNOME does not implement the `wlr-data-control` protocol, so the conda-forge `wl-clipboard-rs` package does not work here. `./scripts/run.sh` runs `scripts/install_linux_clipboard.sh`, which downloads the Ubuntu `wl-clipboard` package and extracts the two binaries into the conda env. That script does not use sudo.

X11 uses `xclip`, or `xsel` if `xclip` is absent.

### Optional autostart

`./scripts/linux-autostart.sh` prints an XDG autostart entry. It writes the file only if you pass `--install`. Nothing is enabled by default.

### Logs and troubleshooting

Logs are `$XDG_STATE_HOME/texgrab/texgrab.log` (default `~/.local/state/texgrab/texgrab.log`), rotated at 1 MB with 3 backups. They record width, height, and character counts. The LaTeX text is logged only when **Debug logging** is on. Pixels are not logged.

**The shortcut does nothing.** TexGrab must be running. On this GNOME session the binding is a custom shortcut; a second copy of the app exits because the first one is already listening. After Quit, the chord does nothing until you start it again.

**Capture opens and then the status says Needs screen capture.** The portal denied permission. Allow screen capture for the launching app and snip again.

**The model fails to load.** The first run needs a network connection for the pix2tex weights. The traceback is in the log. The notification only says that OCR failed.

**The LaTeX is wrong.** Select just the formula. pix2tex is best on a tight crop of a printed equation. This project does not train the model.

**Paste is an image.** TexGrab does not put the screenshot on the clipboard. A successful snip is text. `wl-paste -n -t text/plain` prints that text.

## macOS

The Mac app is unchanged. Select an equation and the LaTeX is copied to the clipboard. Paste it with ⌘V. A normal screenshot (⌘⇧3, ⌘⇧4, ⌘⇧5) is left alone.

You need an Apple Silicon Mac and [Anaconda or Miniconda](https://docs.conda.io/en/latest/miniconda.html). The app uses the same conda environment name, `latex-snipper` (Python 3.11).

```bash
git clone https://github.com/nishron03/TexGrab.git
cd TexGrab
conda env create -f environment.yml
conda activate latex-snipper
pip install -e .
./scripts/run.sh
```

`environment.yml` installs Python, then pip-installs the Mac pins: PyTorch, pix2tex, rumps, and PyObjC. Do not point a Linux install at that file.

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

### Allow screen capture

macOS will not give TexGrab the screen until you allow **Screen Recording** for the app that launched it.

1. Start TexGrab once (`./scripts/run.sh`).
2. Open **System Settings → Privacy & Security → Screen Recording**.
3. Enable **Terminal** or **iTerm** if you started it from a terminal. If you started it from an editor's terminal, enable that editor instead.
4. Quit TexGrab and start it again.

If you later open `dist/TexGrab.app`, grant Screen Recording to **TexGrab** itself. A grant for Terminal does not cover the app, and the reverse is also true. If capture still fails after a rebuild, remove the entry in that list and add it again.

TexGrab does not need Accessibility or Input Monitoring.

### Use

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

### Optional: a menu-bar app, and launch at login

This builds a small `.app` that starts the same conda environment. It does not show a Dock icon.

```bash
conda activate latex-snipper
pip install -e .
./scripts/build_app.sh
open dist/TexGrab.app
```

Grant Screen Recording to **TexGrab** after the first launch.

To open it at login, add `dist/TexGrab.app` in **System Settings → General → Login Items**, or run `./scripts/install_login_item.sh`. If you move the project folder, remove the old login item and add the new app.

### Troubleshooting

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

### How it works

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

`PROJECT_STATE.md` is the development log. `tests/MANUAL.md` is the Mac click-through. `tests/MANUAL-linux.md` is the Linux one. With the conda environment active, `pytest` runs the automated tests.
