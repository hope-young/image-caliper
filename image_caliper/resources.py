from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def asset_path(name: str) -> Path:
    return app_root() / "assets" / name
