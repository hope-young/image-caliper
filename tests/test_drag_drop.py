from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication

from image_caliper.__main__ import DragDropMainWindow


class FakeDropEvent:
    def __init__(self, paths: list[Path]) -> None:
        self._mime_data = QMimeData()
        self._mime_data.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
        self.accepted = False
        self.ignored = False

    def mimeData(self) -> QMimeData:
        return self._mime_data

    def acceptProposedAction(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


class DragDropMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = DragDropMainWindow()

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def _temp_file(self, suffix: str) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_canvas_routes_drops_to_top_level_window(self) -> None:
        self.assertTrue(self.window.acceptDrops())
        self.assertFalse(self.window.canvas.acceptDrops())
        self.assertFalse(self.window.canvas.viewport().acceptDrops())

    def test_accepts_finder_style_local_image_url_case_insensitively(self) -> None:
        image_path = self._temp_file(".PNG")
        event = FakeDropEvent([image_path])

        self.window.dragEnterEvent(event)

        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)

    def test_drop_opens_first_supported_local_image(self) -> None:
        text_path = self._temp_file(".txt")
        image_path = self._temp_file(".jpg")
        loaded: list[Path] = []
        self.window.canvas.load_image = lambda path: loaded.append(path)
        event = FakeDropEvent([text_path, image_path])

        self.window.dropEvent(event)

        self.assertEqual(loaded, [image_path])
        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)

    def test_rejects_unsupported_file(self) -> None:
        text_path = self._temp_file(".pdf")
        event = FakeDropEvent([text_path])

        self.window.dropEvent(event)

        self.assertFalse(event.accepted)
        self.assertTrue(event.ignored)


if __name__ == "__main__":
    unittest.main()
