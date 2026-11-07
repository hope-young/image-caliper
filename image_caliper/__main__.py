from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent
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
        self.image_tabs.setAcceptDrops(True)
        self.image_tabs.installEventFilter(self)

    def _add_image_tab(self, path: Path | None = None):
        canvas = super()._add_image_tab(path)
        canvas.setAcceptDrops(True)
        canvas.installEventFilter(self)
        canvas.viewport().setAcceptDrops(True)
        canvas.viewport().installEventFilter(self)
        return canvas

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.DragEnter:
            self.dragEnterEvent(event)
            return True
        if event.type() == QEvent.Type.DragMove:
            event.acceptProposedAction()
            return True
        if event.type() == QEvent.Type.Drop:
            self.dropEvent(event)
            return True
        return super().eventFilter(watched, event)

    @classmethod
    def _supported_images(cls, event: QDragEnterEvent | QDropEvent) -> list[Path]:
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return []

        images: list[Path] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in cls.SUPPORTED_IMAGE_EXTENSIONS:
                images.append(path)
        return images

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._supported_images(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        image_paths = self._supported_images(event)
        if not image_paths:
            event.ignore()
            return

        try:
            self.open_image_paths(image_paths)
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
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
