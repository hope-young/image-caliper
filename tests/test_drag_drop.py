from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QUrl
from PySide6.QtWidgets import QApplication

from image_caliper.__main__ import DragDropMainWindow


class FakeDropEvent:
    def __init__(self, paths: list[Path], event_type: QEvent.Type = QEvent.Type.Drop) -> None:
        self._mime_data = QMimeData()
        self._mime_data.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
        self._event_type = event_type
        self.accepted = False
        self.ignored = False

    def mimeData(self) -> QMimeData:
        return self._mime_data

    def type(self) -> QEvent.Type:
        return self._event_type

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
        self.assertTrue(self.window.image_tabs.acceptDrops())
        self.assertTrue(self.window.canvas.acceptDrops())
        self.assertTrue(self.window.canvas.viewport().acceptDrops())

    def test_accepts_finder_style_local_image_url_case_insensitively(self) -> None:
        image_path = self._temp_file(".PNG")
        event = FakeDropEvent([image_path])

        self.window.dragEnterEvent(event)

        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)

    def test_child_drag_events_are_forwarded_to_main_window(self) -> None:
        image_path = self._temp_file(".png")
        event = FakeDropEvent([image_path], QEvent.Type.DragEnter)

        handled = self.window.eventFilter(self.window.canvas.viewport(), event)

        self.assertTrue(handled)
        self.assertTrue(event.accepted)

    def test_drop_opens_all_supported_local_images(self) -> None:
        text_path = self._temp_file(".txt")
        image_path = self._temp_file(".jpg")
        image_path_two = self._temp_file(".png")
        opened: list[Path] = []
        self.window.open_image_paths = lambda paths: opened.extend(paths)
        event = FakeDropEvent([text_path, image_path, image_path_two])

        self.window.dropEvent(event)

        self.assertEqual(opened, [image_path, image_path_two])
        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)

    def test_rejects_unsupported_file(self) -> None:
        text_path = self._temp_file(".pdf")
        event = FakeDropEvent([text_path])

        self.window.dropEvent(event)

        self.assertFalse(event.accepted)
        self.assertTrue(event.ignored)

    def test_open_image_paths_creates_switchable_tabs(self) -> None:
        import cv2
        import numpy as np

        first = self._temp_file(".png")
        second = self._temp_file(".png")
        pixels = np.zeros((8, 8, 3), dtype=np.uint8)
        cv2.imwrite(str(first), pixels)
        cv2.imwrite(str(second), pixels)

        self.window.open_image_paths([first, second])

        self.assertEqual(self.window.image_tabs.count(), 2)
        self.assertEqual(self.window.canvas.image_path, second)
        self.window.image_tabs.setCurrentIndex(0)
        self.assertEqual(self.window.canvas.image_path, first)


if __name__ == "__main__":
    unittest.main()
