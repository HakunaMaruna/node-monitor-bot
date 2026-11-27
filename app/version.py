from pathlib import Path

_version_file = Path(__file__).resolve().parent.parent / "VERSION"
VERSION = _version_file.read_text(encoding="utf-8").strip() if _version_file.exists() else "1.12"
