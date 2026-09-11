from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __app_name__
from .main_window import MainWindow
from .resources import asset_path


class DragDropMainWindow(MainWindow):
    """Main window with support for opening images via file drag and drop."""

    SUPPORTED_IMAGE_EXTENSIONS = frozenset(
        {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".pcx"}
    )

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    @classmethod
    def _first_supported_image(cls, event: QDragEnterEvent | QDropEvent) -> Path | None:
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return None

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in cls.SUPPORTED_IMAGE_EXTENSIONS:
                return path
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._first_supported_image(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        image_path = self._first_supported_image(event)
        if image_path is None:
            event.ignore()
            return

        try:
            self.canvas.load_image(image_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error Loading Image", str(exc))
            event.ignore()
            return

        event.acceptProposedAction()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    icon_path = asset_path("imagecaliper-icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = DragDropMainWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
