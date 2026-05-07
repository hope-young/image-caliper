from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QFileDialog, QGraphicsPixmapItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QInputDialog, QMenu


class EditableLabelItem(QGraphicsTextItem):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.background_color = QColor("#ffffff")

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.background_color))
        painter.drawRect(self.boundingRect().adjusted(-2.0, -1.0, 2.0, 1.0))
        painter.restore()
        super().paint(painter, option, widget)


class ImageCanvas(QGraphicsView):
    cursor_position_changed = Signal(float, float)
    cursor_image_position_changed = Signal(float, float)
    image_loaded = Signal(str)
    measurement_changed = Signal(str)
    calibration_changed = Signal(float)
    operation_recorded = Signal(str)
    operation_removed = Signal(str)
    operations_cleared = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._image_bgr: np.ndarray | None = None
        self._image_path: Path | None = None
        self._zoom_steps = 0
        self._tool = "mouse"
        self._measure_start: QPointF | None = None
        self._measure_points: list[QPointF] = []
        self._measure_items: list = []
        self._pending_items: list = []
        self._operations: list[tuple[list, str]] = []
        self._current_path: QPainterPath | None = None
        self._current_path_item = None
        self._arrow_start: QPointF | None = None
        self._drag_measure_start: QPointF | None = None
        self._drag_preview_items: list = []
        self._selected_label: QGraphicsTextItem | None = None
        self._selected_label_frame = None
        self._selected_label_handles: list = []
        self._label_drag_mode: str | None = None
        self._label_last_pos: QPointF | None = None
        self._label_resize_anchor: QPointF | None = None
        self._label_resize_start_size = 10
        self.calibration_value = 1.0
        self.unit = "nm"
        self.decimal_places = 4
        self.show_pixel_values = False
        self.measurement_interaction_mode = "click"
        self.annotation_color = QColor("#ff3b30")
        self.measurement_color = QColor("#ff3b30")
        self.calibration_color = QColor("#34c759")
        self.annotation_font = QFont()
        self.annotation_font.setPointSize(10)
        self.line_width = 2

    @property
    def image_path(self) -> Path | None:
        return self._image_path

    @property
    def image_bgr(self) -> np.ndarray | None:
        return self._image_bgr

    def open_image_dialog(self, start_dir: Path | None = None) -> None:
        filters = "Images (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.pcx);;All Files (*.*)"
        directory = str(start_dir) if start_dir and start_dir.exists() else ""
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", directory, filters)
        if file_name:
            self.load_image(Path(file_name))

    def load_image(self, path: Path) -> None:
        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Error Loading Image: {path}")

        self._image_bgr = image
        self._image_path = path
        pixmap = self._cv_bgr_to_pixmap(image)

        self._clear_label_selection()
        self.scene().clear()
        self._drag_preview_items.clear()
        self._measure_items.clear()
        self._operations.clear()
        self.operations_cleared.emit()
        self._pixmap_item = self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        self.reset_view()
        self.image_loaded.emit(str(path))

    def reset_view(self) -> None:
        self.resetTransform()
        self._zoom_steps = 0
        if self._pixmap_item is not None:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        self._clear_label_selection()
        self._measure_start = None
        self._measure_points.clear()
        self._pending_items.clear()
        self._arrow_start = None
        self._drag_measure_start = None
        self._clear_drag_preview()
        if tool == "mouse":
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_annotation_color(self, color: QColor) -> None:
        if color.isValid():
            self.annotation_color = QColor(color)
            if self._selected_label is not None:
                self._selected_label.setDefaultTextColor(self.annotation_color)

    def set_annotation_font(self, font: QFont) -> None:
        self.annotation_font = QFont(font)
        if self._selected_label is not None:
            self._selected_label.setFont(self.annotation_font)
            self._update_label_frame()

    def set_annotation_font_size(self, point_size: int) -> None:
        self.annotation_font.setPointSize(point_size)
        if self._selected_label is not None:
            font = QFont(self._selected_label.font())
            font.setPointSize(point_size)
            self._selected_label.setFont(font)
            self._update_label_frame()

    def set_line_width(self, width: int) -> None:
        self.line_width = max(1, width)

    def set_measurement_interaction_mode(self, mode: str) -> None:
        if mode in {"click", "drag"}:
            self.measurement_interaction_mode = mode
            self._measure_start = None
            self._drag_measure_start = None
            self._clear_drag_preview()

    def set_decimal_places(self, decimal_places: int) -> None:
        self.decimal_places = max(0, min(8, decimal_places))

    def clear_measurements(self) -> None:
        self._clear_drag_preview()
        self._clear_label_selection()
        for item in self._measure_items:
            self.scene().removeItem(item)
        self._measure_items.clear()
        self._measure_start = None
        self._measure_points.clear()
        self._pending_items.clear()
        self._operations.clear()
        self.measurement_changed.emit("")
        self.operations_cleared.emit()

    def undo_last_operation(self) -> None:
        if not self._operations:
            return
        items, result_text = self._operations.pop()
        for item in items:
            if item is self._selected_label:
                self._clear_label_selection()
            self.scene().removeItem(item)
            if item in self._measure_items:
                self._measure_items.remove(item)
        self.measurement_changed.emit("")
        if result_text:
            self.operation_removed.emit(result_text)

    def save_rendered_image_dialog(self) -> None:
        if self._pixmap_item is None:
            raise ValueError("No image loaded.")

        start_name = "measurement_result.png"
        if self._image_path is not None:
            start_name = f"{self._image_path.stem}_result.png"

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save as",
            start_name,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;Bitmap (*.bmp);;TIFF (*.tif *.tiff)",
        )
        if not file_name:
            return
        self.save_rendered_image(Path(file_name))

    def save_rendered_image(self, path: Path) -> None:
        if self._pixmap_item is None:
            raise ValueError("No image loaded.")

        rect = self.scene().itemsBoundingRect()
        image = QImage(rect.size().toSize(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        label_controls_were_visible = self._label_controls_visible()
        self._set_label_controls_visible(False)
        painter = QPainter(image)
        self.scene().render(painter, QRectF(image.rect()), rect)
        painter.end()
        self._set_label_controls_visible(label_controls_were_visible)

        if not image.save(str(path)):
            raise ValueError(f"Error Saving Image: {path}")

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item is None:
            super().wheelEvent(event)
            return

        if event.angleDelta().y() > 0:
            factor = 1.25
            self._zoom_steps += 1
        else:
            factor = 0.8
            self._zoom_steps -= 1
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        if self._tool == "mouse" and event.button() == Qt.MouseButton.LeftButton:
            if self._try_begin_label_edit(scene_pos):
                return
            self._clear_label_selection()

        if self._tool in {"calibration", "measure_x", "measure_y", "measure_distance", "measure_angle", "measure_area", "arrow", "text"} and self._pixmap_item is not None:
            if self._pixmap_item.contains(scene_pos):
                if self._tool == "text":
                    self._handle_text_click(scene_pos)
                elif self.measurement_interaction_mode == "drag" and self._is_drag_supported_tool():
                    self._drag_measure_start = QPointF(self._constrain_tool_point(scene_pos, event.modifiers()))
                    self._clear_drag_preview()
                elif self._tool == "arrow":
                    self._handle_arrow_click(scene_pos)
                elif self._tool == "calibration":
                    self._handle_calibration_click(scene_pos)
                else:
                    self._handle_measure_click(scene_pos, event.modifiers())
                return

        if self._tool == "curve" and self._pixmap_item is not None and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._pixmap_item.contains(scene_pos):
                self._current_path = QPainterPath(scene_pos)
                self._current_path_item = self.scene().addPath(self._current_path, self._annotation_pen())
                self._measure_items.append(self._current_path_item)
                return

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_measure_start is not None and self._is_drag_supported_tool():
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._pixmap_item is not None and self._pixmap_item.contains(scene_pos):
                self._finish_drag_tool(self._drag_measure_start, self._constrain_tool_point(scene_pos, event.modifiers()))
            self._drag_measure_start = None
            self._clear_drag_preview()
            return

        if self._label_drag_mode is not None:
            self._label_drag_mode = None
            self._label_last_pos = None
            self._label_resize_anchor = None
            return

        if self._tool == "curve" and self._current_path_item is not None:
            self._add_operation([self._current_path_item])
            self._current_path = None
            self._current_path_item = None
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.position().toPoint())
        if self._label_drag_mode is not None:
            self._update_label_edit(scene_pos)
            return

        if self._tool == "mouse":
            self._update_label_hover_cursor(scene_pos)

        if self._pixmap_item is not None and self._pixmap_item.contains(scene_pos):
            self.cursor_position_changed.emit(scene_pos.x(), scene_pos.y())
            self.cursor_image_position_changed.emit(scene_pos.x(), scene_pos.y())
            if self._drag_measure_start is not None and self._is_drag_supported_tool():
                self._update_drag_preview(self._drag_measure_start, self._constrain_tool_point(scene_pos, event.modifiers()))
                return
            if self._tool == "curve" and self._current_path is not None and self._current_path_item is not None:
                self._current_path.lineTo(scene_pos)
                self._current_path_item.setPath(self._current_path)
                return
        super().mouseMoveEvent(event)

    def _handle_measure_click(self, pos: QPointF, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        if self._tool == "measure_angle":
            if len(self._measure_points) == 1:
                pos = self._axis_constrained_point(self._measure_points[0], pos, modifiers)
            elif len(self._measure_points) == 2:
                pos = self._axis_constrained_point(self._measure_points[1], pos, modifiers)
            marker = self._add_marker(pos, self.annotation_color, self._annotation_pen())
            self._measure_points.append(QPointF(pos))
            self._pending_items.append(marker)
            if len(self._measure_points) == 3:
                self._finish_angle_measurement()
            return

        if self._tool == "measure_area":
            marker = self._add_marker(pos, self.annotation_color, self._annotation_pen())
            self._measure_points.append(QPointF(pos))
            self._pending_items.append(marker)
            if len(self._measure_points) == 2:
                self._finish_circle_area_measurement()
            return

        if self._measure_start is None:
            self._measure_start = QPointF(pos)
            return

        self._finish_linear_measurement(self._measure_start, pos)
        self._measure_start = None
        self._pending_items.clear()

    def _handle_calibration_click(self, pos: QPointF) -> None:
        marker = self.scene().addEllipse(pos.x() - 2, pos.y() - 2, 4, 4, self._calibration_pen(), self.calibration_color)
        self._measure_items.append(marker)
        self._pending_items.append(marker)

        if self._measure_start is None:
            self._measure_start = QPointF(pos)
            self.measurement_changed.emit("Calibration: select end point")
            return

        self._finish_calibration(self._measure_start, pos, self._pending_items)
        self._measure_start = None
        self._pending_items.clear()

    def _finish_angle_measurement(self) -> None:
        p1, center, p2 = self._measure_points
        pen = self._measurement_pen()
        line1 = self.scene().addLine(center.x(), center.y(), p1.x(), p1.y(), pen)
        line2 = self.scene().addLine(center.x(), center.y(), p2.x(), p2.y(), pen)
        self._measure_items.extend([line1, line2])

        v1 = np.array([p1.x() - center.x(), p1.y() - center.y()])
        v2 = np.array([p2.x() - center.x(), p2.y() - center.y()])
        denominator = float(np.linalg.norm(v1) * np.linalg.norm(v2))
        angle = 0.0 if denominator == 0 else float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / denominator, -1.0, 1.0))))
        text = f"Center-Angle = {self._format_number(angle)} angle"
        text_item = self._add_label(text)
        text_item.setPos(center + QPointF(6, 6))
        self._measure_items.append(text_item)
        self._add_operation([*self._pending_items, line1, line2, text_item], text)
        self.measurement_changed.emit(text)
        self._measure_points.clear()
        self._pending_items.clear()

    def _finish_circle_area_measurement(self) -> None:
        center, edge = self._measure_points
        self._finish_circle_area(center, edge, self._pending_items)
        self._measure_points.clear()
        self._pending_items.clear()

    def _handle_arrow_click(self, pos: QPointF) -> None:
        if self._arrow_start is None:
            self._arrow_start = QPointF(pos)
            return

        self._finish_arrow(self._arrow_start, pos)
        self._arrow_start = None

    def _handle_text_click(self, pos: QPointF) -> None:
        text, accepted = QInputDialog.getText(self, "Text", "Label")
        if not accepted or not text.strip():
            return
        item = self._add_label(text.strip())
        item.setPos(pos)
        self._measure_items.append(item)
        self._add_operation([item])

    def _add_operation(self, items: list, result_text: str = "") -> None:
        if items:
            self._operations.append((items, result_text))
            if result_text:
                self.operation_recorded.emit(result_text)

    def _finish_drag_tool(self, start: QPointF, end: QPointF) -> None:
        if self._is_linear_measure_tool():
            self._finish_linear_measurement(start, end)
        elif self._tool == "calibration":
            self._finish_calibration(start, end, [])
        elif self._tool == "arrow":
            self._finish_arrow(start, end)
        elif self._tool == "measure_area":
            self._finish_circle_area(start, end, [])
        elif self._tool == "measure_angle":
            self._finish_drag_angle(start, end)

    def _update_drag_preview(self, start: QPointF, end: QPointF) -> None:
        if self._is_linear_measure_tool():
            self._update_drag_measure_preview(start, end)
        elif self._tool == "calibration":
            self._update_drag_calibration_preview(start, end)
        elif self._tool == "arrow":
            self._update_drag_arrow_preview(start, end)
        elif self._tool == "measure_area":
            self._update_drag_circle_area_preview(start, end)
        elif self._tool == "measure_angle":
            self._update_drag_angle_preview(start, end)

    def _finish_calibration(self, start: QPointF, end: QPointF, pending_items: list) -> None:
        pixels = self._distance_pixels(start, end)
        if pixels == 0:
            self.measurement_changed.emit("Calibration failed: zero pixel length")
            return

        real_length, accepted = QInputDialog.getDouble(
            self,
            "Calibration INPUT",
            f"Reference length ({self.unit})",
            pixels * self.calibration_value,
            0.00000001,
            1_000_000_000.0,
            8,
        )
        if not accepted:
            self.measurement_changed.emit("")
            return

        self.calibration_value = real_length / pixels
        ruler_items = self._add_ruler(start, end, self._calibration_pen(), self.calibration_color)
        text = f"CALIBRATE = {self.calibration_value:.8f} {self.unit}/px"
        text_item = self._add_label(text)
        text_item.setPos(self._midpoint_label_pos(start, end))
        self._measure_items.extend([*ruler_items, text_item])
        result = self._format_calibration_result(text, pixels, real_length)
        self._add_operation([*pending_items, *ruler_items, text_item], result)
        self.calibration_changed.emit(self.calibration_value)
        self.measurement_changed.emit(result)

    def _finish_arrow(self, start: QPointF, end: QPointF) -> None:
        arrow_items = self._add_single_arrow(start, end, self._annotation_pen(), self.annotation_color)
        if not arrow_items:
            return
        self._measure_items.extend(arrow_items)
        self._add_operation(arrow_items)

    def _finish_circle_area(self, center: QPointF, edge: QPointF, pending_items: list) -> None:
        radius_px = self._distance_pixels(center, edge)
        if radius_px == 0:
            return
        radius_unit = radius_px * self.calibration_value
        area = float(np.pi * radius_unit * radius_unit)

        circle = self._add_circle(center, radius_px, self._measurement_pen())
        text = f"Circle of Area = {self._format_number(area)} {self.unit}^2"
        text_item = self._add_label(text)
        text_item.setPos(edge + QPointF(6, 6))
        self._measure_items.extend([circle, text_item])
        self._add_operation([*pending_items, circle, text_item], text)
        self.measurement_changed.emit(text)

    def _finish_drag_angle(self, center: QPointF, end: QPointF) -> None:
        angle_items, text = self._add_drag_angle(center, end, self._measurement_pen(), preview=False)
        if not angle_items:
            return
        self._measure_items.extend(angle_items)
        self._add_operation(angle_items, text)
        self.measurement_changed.emit(text)

    def _finish_linear_measurement(self, start: QPointF, raw_end: QPointF) -> None:
        end = self._constrain_linear_end(start, raw_end)
        pixels = self._distance_pixels(start, end)
        if pixels == 0:
            return

        ruler_items = self._add_ruler(start, end, self._measurement_pen(), self.measurement_color)
        text = self._format_linear_measurement_text(pixels)
        text_item = self._add_label(text)
        text_item.setPos(end + QPointF(6, 6))

        operation_items = [*self._pending_items, *ruler_items, text_item]
        self._measure_items.extend([*ruler_items, text_item])
        self._add_operation(operation_items, text)
        self.measurement_changed.emit(text)

    def _update_drag_measure_preview(self, start: QPointF, raw_end: QPointF) -> None:
        self._clear_drag_preview()
        end = self._constrain_linear_end(start, raw_end)
        pixels = self._distance_pixels(start, end)
        if pixels == 0:
            return

        pen = self._measurement_pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        ruler_items = self._add_ruler(start, end, pen, self.measurement_color)
        text = self._format_linear_measurement_text(pixels)
        text_item = self._add_label(text)
        text_item.setPos(end + QPointF(6, 6))
        self._drag_preview_items = [*ruler_items, text_item]
        self.measurement_changed.emit(text)

    def _update_drag_calibration_preview(self, start: QPointF, end: QPointF) -> None:
        self._clear_drag_preview()
        pixels = self._distance_pixels(start, end)
        if pixels == 0:
            return
        pen = self._calibration_pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        ruler_items = self._add_ruler(start, end, pen, self.calibration_color)
        text = f"Calibration length = {pixels:.2f} px"
        text_item = self._add_label(text)
        text_item.setPos(self._midpoint_label_pos(start, end))
        self._drag_preview_items = [*ruler_items, text_item]
        self.measurement_changed.emit(text)

    def _update_drag_arrow_preview(self, start: QPointF, end: QPointF) -> None:
        self._clear_drag_preview()
        pen = self._annotation_pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        self._drag_preview_items = self._add_single_arrow(start, end, pen, self.annotation_color)

    def _update_drag_circle_area_preview(self, center: QPointF, edge: QPointF) -> None:
        self._clear_drag_preview()
        radius_px = self._distance_pixels(center, edge)
        if radius_px == 0:
            return
        pen = self._measurement_pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        circle = self._add_circle(center, radius_px, pen)
        radius_unit = radius_px * self.calibration_value
        area = float(np.pi * radius_unit * radius_unit)
        text = f"Circle of Area = {self._format_number(area)} {self.unit}^2"
        text_item = self._add_label(text)
        text_item.setPos(edge + QPointF(6, 6))
        self._drag_preview_items = [circle, text_item]
        self.measurement_changed.emit(text)

    def _update_drag_angle_preview(self, center: QPointF, end: QPointF) -> None:
        self._clear_drag_preview()
        pen = self._measurement_pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        angle_items, text = self._add_drag_angle(center, end, pen, preview=True)
        self._drag_preview_items = angle_items
        if text:
            self.measurement_changed.emit(text)

    def _clear_drag_preview(self) -> None:
        for item in self._drag_preview_items:
            self.scene().removeItem(item)
        self._drag_preview_items.clear()

    def _add_ruler(self, start: QPointF, end: QPointF, pen: QPen, fill_color: QColor) -> list:
        vector = np.array([end.x() - start.x(), end.y() - start.y()], dtype=float)
        length = float(np.linalg.norm(vector))
        if length == 0:
            return []

        direction = vector / length
        normal = np.array([-direction[1], direction[0]])
        head_len = max(10.0, self.line_width * 4.0)
        head_w = max(5.0, self.line_width * 2.0)
        cap_len = max(12.0, self.line_width * 5.0)

        line = self.scene().addLine(start.x(), start.y(), end.x(), end.y(), pen)
        start_head = self.scene().addPolygon(
            self._arrow_head_polygon(start, -direction, normal, head_len, head_w),
            pen,
            fill_color,
        )
        end_head = self.scene().addPolygon(
            self._arrow_head_polygon(end, direction, normal, head_len, head_w),
            pen,
            fill_color,
        )
        start_cap = self._add_end_cap(start, normal, cap_len, pen)
        end_cap = self._add_end_cap(end, normal, cap_len, pen)
        return [line, start_head, end_head, start_cap, end_cap]

    def _add_single_arrow(self, start: QPointF, end: QPointF, pen: QPen, fill_color: QColor) -> list:
        vector = np.array([end.x() - start.x(), end.y() - start.y()], dtype=float)
        length = float(np.linalg.norm(vector))
        if length == 0:
            return []

        direction = vector / length
        normal = np.array([-direction[1], direction[0]])
        line = self.scene().addLine(start.x(), start.y(), end.x(), end.y(), pen)
        head = self.scene().addPolygon(
            self._arrow_head_polygon(end, direction, normal, 14.0, 7.0),
            pen,
            fill_color,
        )
        return [line, head]

    def _add_circle(self, center: QPointF, radius_px: float, pen: QPen):
        return self.scene().addEllipse(
            center.x() - radius_px,
            center.y() - radius_px,
            radius_px * 2,
            radius_px * 2,
            pen,
        )

    def _add_drag_angle(self, center: QPointF, end: QPointF, pen: QPen, preview: bool) -> tuple[list, str]:
        radius = self._distance_pixels(center, end)
        if radius == 0:
            return [], ""

        baseline_length = max(28.0, min(44.0, self.line_width * 14.0))
        baseline = QPointF(center.x() + baseline_length, center.y())
        line1 = self.scene().addLine(center.x(), center.y(), baseline.x(), baseline.y(), pen)
        line2 = self.scene().addLine(center.x(), center.y(), end.x(), end.y(), pen)

        vector = np.array([end.x() - center.x(), end.y() - center.y()], dtype=float)
        angle = float(np.degrees(np.arctan2(-vector[1], vector[0])))
        if angle < 0:
            angle += 360.0
        angle = min(angle, 360.0 - angle)
        text = f"Center-Angle = {self._format_number(angle)} angle"
        text_item = self._add_label(text)
        text_item.setPos(center + QPointF(6, 6))
        return [line1, line2, text_item], text

    def _add_end_cap(self, point: QPointF, normal: np.ndarray, cap_len: float, pen: QPen):
        half = normal * (cap_len / 2.0)
        p1 = np.array([point.x(), point.y()]) - half
        p2 = np.array([point.x(), point.y()]) + half
        return self.scene().addLine(p1[0], p1[1], p2[0], p2[1], pen)

    @staticmethod
    def _arrow_head_polygon(tip: QPointF, direction: np.ndarray, normal: np.ndarray, head_len: float, head_w: float) -> QPolygonF:
        tip_array = np.array([tip.x(), tip.y()])
        left = tip_array - direction * head_len + normal * head_w
        right = tip_array - direction * head_len - normal * head_w
        return QPolygonF([QPointF(*tip_array), QPointF(*left), QPointF(*right)])

    def _add_marker(self, pos: QPointF, color: QColor, pen: QPen):
        marker = self.scene().addEllipse(pos.x() - 2, pos.y() - 2, 4, 4, pen, color)
        self._measure_items.append(marker)
        return marker

    @staticmethod
    def _midpoint_label_pos(start: QPointF, end: QPointF) -> QPointF:
        return QPointF((start.x() + end.x()) / 2.0 + 6.0, (start.y() + end.y()) / 2.0 - 18.0)

    def _constrain_linear_end(self, start: QPointF, raw_end: QPointF) -> QPointF:
        end = QPointF(raw_end)
        if self._tool == "measure_x":
            end.setY(start.y())
        elif self._tool == "measure_y":
            end.setX(start.x())
        return end

    def _constrain_tool_point(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> QPointF:
        if self._tool == "measure_angle" and self._drag_measure_start is not None:
            return self._axis_constrained_point(self._drag_measure_start, pos, modifiers)
        return pos

    @staticmethod
    def _axis_constrained_point(anchor: QPointF, pos: QPointF, modifiers: Qt.KeyboardModifier) -> QPointF:
        if not modifiers & Qt.KeyboardModifier.ShiftModifier:
            return pos
        dx = pos.x() - anchor.x()
        dy = pos.y() - anchor.y()
        if abs(dx) >= abs(dy):
            return QPointF(pos.x(), anchor.y())
        return QPointF(anchor.x(), pos.y())

    @staticmethod
    def _distance_pixels(start: QPointF, end: QPointF) -> float:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        return float((dx * dx + dy * dy) ** 0.5)

    def _format_linear_measurement_text(self, pixels: float) -> str:
        measured = pixels * self.calibration_value
        label = {
            "measure_x": "X Length",
            "measure_y": "Y Length",
            "measure_distance": "Z Length",
        }[self._tool]
        text = f"{label} = {self._format_number(measured)} {self.unit}"
        if self.show_pixel_values:
            text = f"{text} ({pixels:.2f} px)"
        return text

    def _is_linear_measure_tool(self) -> bool:
        return self._tool in {"measure_x", "measure_y", "measure_distance"}

    def _is_drag_supported_tool(self) -> bool:
        return self._tool in {
            "calibration",
            "measure_x",
            "measure_y",
            "measure_distance",
            "measure_angle",
            "measure_area",
            "arrow",
        }

    def _format_calibration_result(self, text: str, pixels: float, real_length: float) -> str:
        if not self.show_pixel_values:
            return text
        return f"{text} ({pixels:.2f} px -> {self._format_number(real_length)} {self.unit})"

    def _format_number(self, value: float) -> str:
        return f"{value:.{self.decimal_places}f}"

    def _annotation_pen(self) -> QPen:
        return QPen(self.annotation_color, self.line_width)

    def _measurement_pen(self) -> QPen:
        return QPen(self.measurement_color, self.line_width)

    def _calibration_pen(self) -> QPen:
        return QPen(self.calibration_color, self.line_width)

    def _apply_text_style(self, item, color: QColor) -> None:
        item.setDefaultTextColor(color)
        item.setFont(self.annotation_font)

    def _add_label(self, text: str, color: QColor | None = None) -> QGraphicsTextItem:
        item = EditableLabelItem(text)
        self.scene().addItem(item)
        self._apply_text_style(item, color or self.annotation_color)
        item.setZValue(10)
        item.setData(0, "editable_label")
        return item

    def _try_begin_label_edit(self, scene_pos: QPointF) -> bool:
        handle_role = self._label_handle_at(scene_pos)
        if handle_role is not None:
            self._label_drag_mode = "resize"
            self._label_last_pos = QPointF(scene_pos)
            self._label_resize_anchor = self._selected_label.sceneBoundingRect().center() if self._selected_label is not None else QPointF(scene_pos)
            self._label_resize_start_size = max(1, self._selected_label.font().pointSize()) if self._selected_label is not None else 10
            return True

        if self._selected_label is not None and self._label_frame_rect().contains(scene_pos):
            self._label_drag_mode = "move"
            self._label_last_pos = QPointF(scene_pos)
            self._label_resize_anchor = self._selected_label.sceneBoundingRect().center()
            self._label_resize_start_size = max(1, self._selected_label.font().pointSize())
            return True

        for item in self.scene().items(scene_pos):
            if item is self._selected_label_frame:
                continue
            if isinstance(item, QGraphicsTextItem) and item.data(0) == "editable_label":
                self._select_label(item)
                self._label_drag_mode = "move"
                self._label_last_pos = QPointF(scene_pos)
                self._label_resize_anchor = item.sceneBoundingRect().center()
                self._label_resize_start_size = max(1, item.font().pointSize())
                return True
        return False

    def _select_label(self, item: QGraphicsTextItem) -> None:
        self._selected_label = item
        self._update_label_frame()

    def _clear_label_selection(self) -> None:
        for handle in self._selected_label_handles:
            self.scene().removeItem(handle)
        self._selected_label_handles.clear()
        if self._selected_label_frame is not None:
            self.scene().removeItem(self._selected_label_frame)
            self._selected_label_frame = None
        self._selected_label = None
        self._label_drag_mode = None
        self._label_last_pos = None
        self._label_resize_anchor = None

    def _update_label_edit(self, scene_pos: QPointF) -> None:
        if self._selected_label is None or self._label_last_pos is None:
            return

        if self._label_drag_mode == "move":
            delta = scene_pos - self._label_last_pos
            self._selected_label.setPos(self._selected_label.pos() + delta)
            self._label_last_pos = QPointF(scene_pos)
        elif self._label_drag_mode == "resize" and self._label_resize_anchor is not None:
            start_distance = max(1.0, self._distance_pixels(self._label_resize_anchor, self._label_last_pos))
            current_distance = max(1.0, self._distance_pixels(self._label_resize_anchor, scene_pos))
            new_size = round(self._label_resize_start_size * current_distance / start_distance)
            font = QFont(self._selected_label.font())
            font.setPointSize(max(4, min(96, new_size)))
            self._selected_label.setFont(font)

        self._update_label_frame()

    def _update_label_frame(self) -> None:
        if self._selected_label is None:
            return
        rect = self._label_frame_rect()
        pen = QPen(QColor("#111111"), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        if self._selected_label_frame is None:
            self._selected_label_frame = self.scene().addRect(rect, pen)
            self._selected_label_frame.setZValue(self._selected_label.zValue() + 1)
            self._selected_label_frame.setData(0, "label_frame")
        else:
            self._selected_label_frame.setRect(rect)
            self._selected_label_frame.setPen(pen)
        self._update_label_handles(rect)

    def _label_frame_rect(self) -> QRectF:
        if self._selected_label is None:
            return QRectF()
        return self._selected_label.sceneBoundingRect().adjusted(-4.0, -3.0, 4.0, 3.0)

    def _update_label_handles(self, rect: QRectF) -> None:
        roles_and_points = {
            "top_left": rect.topLeft(),
            "top": QPointF(rect.center().x(), rect.top()),
            "top_right": rect.topRight(),
            "right": QPointF(rect.right(), rect.center().y()),
            "bottom_right": rect.bottomRight(),
            "bottom": QPointF(rect.center().x(), rect.bottom()),
            "bottom_left": rect.bottomLeft(),
            "left": QPointF(rect.left(), rect.center().y()),
        }
        size = max(5.0, 8.0 / max(0.1, self.transform().m11()))
        pen = QPen(QColor("#111111"), 1)
        brush = QBrush(QColor("#ffffff"))
        existing = {handle.data(1): handle for handle in self._selected_label_handles}
        for role, point in roles_and_points.items():
            handle_rect = QRectF(point.x() - size / 2.0, point.y() - size / 2.0, size, size)
            handle = existing.get(role)
            if handle is None:
                handle = self.scene().addRect(handle_rect, pen, brush)
                handle.setData(0, "label_handle")
                handle.setData(1, role)
                handle.setZValue((self._selected_label.zValue() if self._selected_label is not None else 10) + 2)
                self._selected_label_handles.append(handle)
            else:
                handle.setRect(handle_rect)
                handle.setPen(pen)
                handle.setBrush(brush)

    def _label_handle_at(self, scene_pos: QPointF) -> str | None:
        for handle in self._selected_label_handles:
            if handle.sceneBoundingRect().contains(scene_pos):
                return handle.data(1)
        return None

    def _update_label_hover_cursor(self, scene_pos: QPointF) -> None:
        role = self._label_handle_at(scene_pos)
        if role is not None:
            self.viewport().setCursor(self._cursor_for_label_handle(role))
        elif self._selected_label is not None and self._label_frame_rect().contains(scene_pos):
            self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.viewport().unsetCursor()

    @staticmethod
    def _cursor_for_label_handle(role: str) -> Qt.CursorShape:
        if role in {"top_left", "bottom_right"}:
            return Qt.CursorShape.SizeFDiagCursor
        if role in {"top_right", "bottom_left"}:
            return Qt.CursorShape.SizeBDiagCursor
        if role in {"left", "right"}:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor

    def _label_controls_visible(self) -> bool:
        if self._selected_label_frame is None:
            return False
        return self._selected_label_frame.isVisible()

    def _set_label_controls_visible(self, visible: bool) -> None:
        if self._selected_label_frame is not None:
            self._selected_label_frame.setVisible(visible)
        for handle in self._selected_label_handles:
            handle.setVisible(visible)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        reset_action = QAction("Fit to Window", self)
        clear_action = QAction("Clear Measurements", self)
        reset_action.triggered.connect(self.reset_view)
        clear_action.triggered.connect(self.clear_measurements)
        menu.addAction(reset_action)
        menu.addAction(clear_action)
        menu.exec(global_pos)

    @staticmethod
    def _cv_bgr_to_pixmap(image: np.ndarray) -> QPixmap:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        qimage = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(qimage)
