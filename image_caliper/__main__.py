from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import __app_name__
from .main_window import MainWindow
from .resources import asset_path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    icon_path = asset_path("imagecaliper-icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
