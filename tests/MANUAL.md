# Manual tests

Automated tests do not drive the selection overlay or the global shortcut. Run these with TexGrab already started (`scripts/run.sh`) and another app focused.

Log file: `~/Library/Logs/TexGrab/texgrab.log`.

## Shortcut from another app

1. Focus Safari, Preview, or TextEdit. TexGrab must not be the active app.
2. Press ⌘⌃⇧S.
3. The macOS region-selection overlay appears (crosshair, drag a rectangle, Escape cancels).
4. The log contains `shortcut activated` and then either `capture cancelled` or `capture ok`.

## Cancel

1. Press ⌘⌃⇧S and press Escape.
2. No notification appears.
3. The clipboard is unchanged (`pbpaste` prints the same text as before).

## Successful equation

1. Open a page or PDF that shows a printed equation.
2. Press ⌘⌃⇧S and drag a tight rectangle around just the equation.
3. The menu-bar title shows `TexGrab…` while the model runs, then returns to `TexGrab`.
4. A notification says `LaTeX copied to clipboard`.
5. Focus TextEdit and press ⌘V. The paste is LaTeX text, not an image.
6. `pbpaste` prints that LaTeX. It does not mention a TIFF or PNG.

## Ordinary screenshots still work

1. With TexGrab running, press ⌘⇧4 and take a normal screenshot.
2. That screenshot is saved by macOS as usual. TexGrab does not run OCR for it and does not replace it with LaTeX.

## Test OCR menu

1. Open the TexGrab menu and choose Test OCR.
2. The bundled sample equation is recognized and the LaTeX is copied.
3. ⌘V pastes that LaTeX.

## Permission failure

1. In System Settings, turn off Screen Recording for the process that launched TexGrab.
2. Press ⌘⌃⇧S.
3. The menu status says `Needs Screen Recording` and a notification says permission is required.
4. The log names System Settings and does not contain image data.

## Quit

1. Choose Quit.
2. `pgrep -fl texgrab` prints nothing.
3. ⌘⌃⇧S does nothing.
