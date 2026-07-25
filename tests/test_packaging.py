from pathlib import Path


def test_pyinstaller_bundle_includes_textual_stylesheet():
    spec = Path("tiamat.spec").read_text(encoding="utf-8")

    assert "('tiamat\\\\tiamat.tcss', '.')" in spec
