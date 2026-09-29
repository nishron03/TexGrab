# Linux manual pass

Automated tests do not prove the global shortcut or the region overlay. Run this on the desktop after `./scripts/run.sh` reports Ready.

The shortcut on this Ubuntu GNOME Wayland session is **Ctrl+Alt+Shift+S**. It runs the conda interpreter as `python -m texgrab --trigger`. Print, Shift+Print, and Alt+Print stay the desktop's screenshot chords.

If a portal dialog asks TexGrab (or the terminal that launched it) for permission to take a screenshot, choose Allow. Then drag the region. Escape cancels that dialog and must not notify or change the clipboard.

If the tray icon is missing, enable the GNOME extension **AppIndicator and KStatusNotifierItem Support** (`gnome-shell-extension-appindicator`). TexGrab keeps running without the icon. `python -m texgrab --trigger` still snips.

## Steps

1. `./scripts/run.sh`. The status becomes Ready. The first launch may spend several seconds importing torch and, if the files are absent, downloading pix2tex weights.
2. Focus another window. Press the shortcut. A region selector appears. The log contains `shortcut activated` and then `capture cancelled` or `capture ok`.
3. Escape: no notification, clipboard unchanged.
4. Snip a tight crop of a printed equation. The notification says `LaTeX copied to clipboard`. Paste is text, not an image. The log has no pixel data.
5. The desktop's normal screenshot shortcut still saves a normal screenshot. TexGrab does not OCR it.
6. Test OCR copies the sample LaTeX.
7. Change the shortcut, then change it back to the default. Escape leaves the current shortcut in place.
8. Quit. The icon is gone, the socket is gone, and the shortcut does nothing. No leftover process.

## What was run on 2026-09-29

Machine: Ubuntu GNOME on Wayland (`XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=ubuntu:GNOME`). GlobalShortcuts is not on this portal, so the binding is one GNOME custom keybinding plus `$XDG_RUNTIME_DIR/texgrab.sock`.

1. Passed. `./scripts/run.sh` logged `status Ready` after `pix2tex model ready`. Weights were already cached.
2. Not passed. The keys were not pressed from another window. `python -m texgrab --trigger`, which is the command that binding runs, logged `shortcut activated`, `status Selecting…`, and `capture start backend=portal`. The clipboard text was unchanged. The overlay itself was not driven.
3. Not passed. Escape was not pressed. Quitting while the portal call was still open did not log `capture cancelled`.
4. Not passed. No equation was snipped.
5. Not passed as a saved screenshot. After TexGrab registered and after it quit, the GNOME bindings were still `Print`, `<Shift>Print`, and `<Alt>Print`. Print was not pressed.
6. Not passed from the menu. The command `python -m texgrab --test-ocr src/texgrab/resources/sample_equation.png --clipboard` printed `E=m C^{2}+\int_{0}^{1}\!X^{2}\,Q X`, and `wl-paste -n -t text/plain` printed that same line and nothing else.
7. Not passed. The shortcut recorder was not opened.
8. Passed. SIGTERM logged `TexGrab quitting` and `shortcut unregistered`. `/run/user/1000/texgrab.sock` was gone, `custom-keybindings` was `@as []` again, and no `python -m texgrab` process remained.

A second `./scripts/run.sh` while the first was up logged `TexGrab is already running` and exited. The first process stayed up.
