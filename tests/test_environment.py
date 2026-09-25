import subprocess
import sys
from pathlib import Path

import texgrab
from texgrab.clipboard import change_count
from texgrab.ocr.pix2tex_engine import Pix2TexEngine, sample_equation_path
from tests.test_clipboard import restore_pasteboard, save_pasteboard


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


def test_pix2tex_on_sample_equation():
    path = sample_equation_path()
    assert path.is_file(), "sample equation was not generated"
    from PIL import Image

    with Image.open(path) as image:
        image.load()
        loaded = image.copy()
    saved = save_pasteboard()
    before = change_count()
    try:
        text = Pix2TexEngine().recognize(loaded)
        assert change_count() == before
    finally:
        restore_pasteboard(saved)
    assert isinstance(text, str)
    assert text.strip()
