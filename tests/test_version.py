from pathlib import Path

from app.version import VERSION


def test_version_is_1_0():
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    assert version_file.read_text(encoding="utf-8").strip() == "1.0"
    assert VERSION == "1.0"
