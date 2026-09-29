# Linux manual pass

Automated tests do not prove the global shortcut or a hand-dragged equation. Run this on the desktop after `./scripts/run.sh` reports Ready.

The shortcut on this Ubuntu GNOME Wayland session is **Ctrl+Alt+Shift+S**. It runs the conda interpreter as `python -m texgrab --trigger`. Print, Shift+Print, and Alt+Print stay the desktop's screenshot chords.

The selector is TexGrab's own rectangle on a frozen frame. Drag, then release. Escape cancels and must not notify or change the clipboard. The next press opens the rectangle again.

The first snip can show **Allow Applications to Take Screenshots?** Allow it. That dialog is the permission. The rectangle comes after it. The screen may flash once while the frame is taken.

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

Machine: Ubuntu GNOME on Wayland (`XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=ubuntu:GNOME`). One monitor, 1920×1080, scale 1. GlobalShortcuts is not on this portal, so the binding is one GNOME custom keybinding plus `$XDG_RUNTIME_DIR/texgrab.sock`.

The first build opened the GNOME screenshot UI. The user reported that a drag did not finish the snip, Enter put the image on the clipboard, and Escape left the snip running. The log at 13:06:12 was `shortcut ignored; snip already running`, and later presses repeated that line until Quit. That UI is no longer used.

1. Passed. `./scripts/run.sh` logged `status Ready` after `pix2tex model ready`. Weights were already cached.
2. The keys were not pressed from another window by a person. A silent portal frame returned 1920×1080 and the Pictures file was removed. The clipboard gained no image. A fullscreen overlay on a generated frame accepted a drag and, on a second call, Escape. Both returned on the GTK thread the app uses. A hand drag over a real window is not passed.
3. Escape was checked on that overlay and returned no image, and a following selection ran. It was not pressed by a person over a live equation. No notification is sent for that path in the unit tests.
4. Not passed. No equation was snipped by a person.
5. Not passed as a saved screenshot. After TexGrab registered and after it quit, the GNOME bindings were still `Print`, `<Shift>Print`, and `<Alt>Print`. Print was not pressed.
6. Not passed from the menu. The command `python -m texgrab --test-ocr src/texgrab/resources/sample_equation.png --clipboard` printed `E=m C^{2}+\int_{0}^{1}\!X^{2}\,Q X`, and `wl-paste -n -t text/plain` printed that same line and nothing else.
7. Not passed. The shortcut recorder was not opened.
8. Passed. SIGTERM logged `TexGrab quitting` and `shortcut unregistered`. `/run/user/1000/texgrab.sock` was gone, `custom-keybindings` was `@as []` again, and no `python -m texgrab` process remained.

A second `./scripts/run.sh` while the first was up logged `TexGrab is already running` and exited. The first process stayed up.
