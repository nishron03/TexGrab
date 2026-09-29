import subprocess
import sys
from pathlib import Path

import pytest

import texgrab
from texgrab.clipboard import change_count, read_text, write_text
from texgrab.ocr.pix2tex_engine import Pix2TexEngine, sample_equation_path


def _save_clipboard():
    if sys.platform == "darwin":
        from tests.test_clipboard import save_pasteboard

        return save_pasteboard()
    return read_text()


def _restore_clipboard(saved) -> None:
    if sys.platform == "darwin":
        from tests.test_clipboard import restore_pasteboard

        restore_pasteboard(saved)
        return
    if saved:
        write_text(saved)


def test_running_inside_latex_snipper():
    assert Path(sys.prefix).name == "latex-snipper"


def test_package_imports():
    assert texgrab.__version__


def test_module_check_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "texgrab", "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "latex-snipper" in completed.stdout
    assert "texgrab=" in completed.stdout


def test_check_fails_when_prefix_is_not_latex_snipper(monkeypatch, capsys):
    import texgrab.__main__ as entry

    monkeypatch.setattr(entry.sys, "prefix", "/tmp/not-the-env")
    assert entry._check() == 1
    captured = capsys.readouterr()
    assert "latex-snipper" in captured.err


@pytest.mark.slow
def test_pix2tex_on_sample_equation():
    path = sample_equation_path()
    assert path.is_file(), "sample equation was not generated"
    from PIL import Image

    with Image.open(path) as image:
        image.load()
        loaded = image.copy()
    saved = _save_clipboard()
    before = change_count()
    try:
        text = Pix2TexEngine().recognize(loaded)
        assert change_count() == before
    finally:
        _restore_clipboard(saved)
    assert isinstance(text, str)
    assert text.strip()
