from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFormLayout, QLabel, QSizePolicy, QSlider, QSpinBox, QSplitter, QVBoxLayout, QWidget


class MagnifierPanel(QWidget):
    MIN_PREVIEW_SIZE = 120

    def __init__(self) -> None:
        super().__init__()
        self._image_bgr: np.ndarray | None = None
        self._last_position: tuple[float, float] | None = None
        self._user_resized_preview = False

        self.preview_label = QLabel("No image", self)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(self.MIN_PREVIEW_SIZE, self.MIN_PREVIEW_SIZE)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setStyleSheet("QLabel { background: #111; color: #bbb; border: 1px solid #555; }")

        self.zoom_spin = QSpinBox(self)
        self.zoom_spin.setRange(1, 12)
        self.zoom_spin.setValue(2)
        self.zoom_spin.setSuffix("x")

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.zoom_slider.setRange(1, 12)
        self.zoom_slider.setValue(2)

        self.position_label = QLabel("X = -, Y = -", self)
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        form = QFormLayout()
        form.addRow("Magnification", self.zoom_spin)
        form.addRow("", self.zoom_slider)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.addLayout(form)
        controls_layout.addWidget(self.position_label)
        controls_layout.addStretch(1)

        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.splitter.addWidget(self.preview_label)
        self.splitter.addWidget(controls)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([220, 180])
        self.splitter.splitterMoved.connect(self._mark_preview_resized)

        layout = QVBoxLayout(self)
        layout.addWidget(self.splitter)

        self.zoom_spin.valueChanged.connect(self.zoom_slider.setValue)
        self.zoom_slider.valueChanged.connect(self.zoom_spin.setValue)
        self.zoom_spin.valueChanged.connect(lambda _value: self._refresh())

    def set_image(self, image_bgr: np.ndarray | None) -> None:
        self._image_bgr = image_bgr
        self._last_position = None
        if image_bgr is None:
            self.preview_label.setText("No image")
            self.preview_label.setPixmap(QPixmap())
            self.position_label.setText("X = -, Y = -")

    def set_zoom(self, zoom: int) -> None:
        self.zoom_spin.setValue(max(self.zoom_spin.minimum(), min(self.zoom_spin.maximum(), zoom)))

    def zoom(self) -> int:
        return self.zoom_spin.value()

    def set_splitter_sizes(self, sizes: list[int]) -> None:
        if sizes:
            self._user_resized_preview = True
            self.splitter.setSizes(sizes)

    def splitter_sizes(self) -> list[int]:
        return self.splitter.sizes()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._user_resized_preview:
            self._apply_default_square_preview()
        self._refresh()

    def update_position(self, x: float, y: float) -> None:
        self._last_position = (x, y)
        self.position_label.setText(f"X = {x:.0f}, Y = {y:.0f}")
        self._refresh()

    def _refresh(self) -> None:
        if self._image_bgr is None or self._last_position is None:
            return

        x, y = self._last_position
        height, width = self._image_bgr.shape[:2]
        ix = int(round(max(0, min(width - 1, x))))
        iy = int(round(max(0, min(height - 1, y))))

        zoom = self.zoom_spin.value()
        target_size = max(
            self.MIN_PREVIEW_SIZE,
            min(self.preview_label.width(), self.preview_label.height()),
        )
        crop_size = max(8, int(target_size / zoom))
        half = crop_size // 2

        x0 = ix - half
        y0 = iy - half
        x1 = x0 + crop_size
        y1 = y0 + crop_size

        src_x0 = max(0, x0)
        src_y0 = max(0, y0)
        src_x1 = min(width, x1)
        src_y1 = min(height, y1)
        if src_x0 >= src_x1 or src_y0 >= src_y1:
            return

        crop = np.full((crop_size, crop_size, 3), 32, dtype=self._image_bgr.dtype)
        dst_x0 = src_x0 - x0
        dst_y0 = src_y0 - y0
        dst_x1 = dst_x0 + (src_x1 - src_x0)
        dst_y1 = dst_y0 + (src_y1 - src_y0)
        crop[dst_y0:dst_y1, dst_x0:dst_x1] = self._image_bgr[src_y0:src_y1, src_x0:src_x1]

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (target_size, target_size), interpolation=cv2.INTER_NEAREST)
        self._draw_crosshair(rgb)

        qimage = QImage(
            rgb.data,
            rgb.shape[1],
            rgb.shape[0],
            rgb.shape[1] * rgb.shape[2],
            QImage.Format.Format_RGB888,
        ).copy()
        self.preview_label.setPixmap(QPixmap.fromImage(qimage))

    def _apply_default_square_preview(self) -> None:
        width = self.preview_label.width()
        if width <= self.MIN_PREVIEW_SIZE:
            return
        controls_height = max(self.height() - width, self.MIN_PREVIEW_SIZE)
        self.splitter.setSizes([width, controls_height])

    def _mark_preview_resized(self) -> None:
        self._user_resized_preview = True

    @staticmethod
    def _draw_crosshair(rgb: np.ndarray) -> None:
        height, width = rgb.shape[:2]
        cx = width // 2
        cy = height // 2
        rgb[cy, :, :] = [255, 60, 48]
        rgb[:, cx, :] = [255, 60, 48]
