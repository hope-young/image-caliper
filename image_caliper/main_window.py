from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QColorDialog,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFontDialog,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QWidget,
)

from .image_canvas import ImageCanvas
from .legacy_config import LegacyConfig, load_config, save_config
from .magnifier_panel import MagnifierPanel
from .resources import asset_path


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ImageCaliper")

        self.workspace_root = Path(__file__).resolve().parents[1]
        self.settings_path = self.workspace_root / "settings.ini"
        self.legacy_config = load_config(self.settings_path, self.workspace_root.parent / "Processing.ini")
        self.icon_path = asset_path("imagecaliper-icon.png")
        if self.icon_path.exists():
            self.setWindowIcon(QIcon(str(self.icon_path)))

        self.canvas = ImageCanvas()
        self.canvas.calibration_value = self.legacy_config.calibrate_value
        self.setCentralWidget(self.canvas)

        self.magnifier_panel = MagnifierPanel()
        self.magnifier_dock = QDockWidget("Browser Mag", self)
        self.magnifier_dock.setObjectName("browserMagDock")
        self.magnifier_dock.setWidget(self.magnifier_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.magnifier_dock)
        self._build_measurements_dock()
        self.splitDockWidget(self.magnifier_dock, self.measurements_dock, Qt.Orientation.Vertical)

        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._coord_label = "X = 0, Y = 0"
        self._measurement_label = ""
        self._annotation_color = QColor(self.legacy_config.annotation_color)
        if not self._annotation_color.isValid():
            self._annotation_color = QColor("#00a6d6")

        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._apply_loaded_settings()
        self._connect_signals()
        self._update_status()

    def _build_measurements_dock(self) -> None:
        self.measurement_table = QTableWidget(0, 2, self)
        self.measurement_table.setHorizontalHeaderLabels(["#", "Result"])
        self.measurement_table.verticalHeader().setVisible(False)
        self.measurement_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.measurement_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.measurement_table.setAlternatingRowColors(True)
        self.measurement_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.measurement_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.measurements_dock = QDockWidget("Measurements", self)
        self.measurements_dock.setObjectName("measurementsDock")
        self.measurements_dock.setWidget(self.measurement_table)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.measurements_dock)

    def _build_actions(self) -> None:
        self.open_action = QAction("Open", self)
        self.save_action = QAction("Save", self)
        self.save_as_action = QAction("Save as", self)
        self.export_measurements_action = QAction("Export Measurements CSV", self)
        self.save_settings_action = QAction("Save Settings", self)
        self.exit_action = QAction("Exit", self)
        self.fit_action = QAction("Fit to Window", self)
        self.clear_measure_action = QAction("Clear Measurements", self)
        self.undo_action = QAction("Undo", self)
        self.font_action = QAction("Font", self)
        self.color_action = QAction("Color", self)

        self.mouse_action = QAction("Mouse", self, checkable=True)
        self.calibration_action = QAction("Calibration", self, checkable=True)
        self.curve_action = QAction("Curve", self, checkable=True)
        self.arrow_action = QAction("Arrow", self, checkable=True)
        self.text_action = QAction("Text", self, checkable=True)
        self.measure_x_action = QAction("Width(x)", self, checkable=True)
        self.measure_y_action = QAction("Height(y)", self, checkable=True)
        self.measure_distance_action = QAction("Distance(z)", self, checkable=True)
        self.measure_angle_action = QAction("Angle", self, checkable=True)
        self.measure_area_action = QAction("Circle Area", self, checkable=True)

        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        for action in (
            self.mouse_action,
            self.calibration_action,
            self.curve_action,
            self.arrow_action,
            self.text_action,
            self.measure_x_action,
            self.measure_y_action,
            self.measure_distance_action,
            self.measure_angle_action,
            self.measure_area_action,
        ):
            self.tool_group.addAction(action)
        self.mouse_action.setChecked(True)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.export_measurements_action)
        file_menu.addAction(self.save_settings_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        select_menu = self.menuBar().addMenu("Select")
        select_menu.addAction(self.mouse_action)
        select_menu.addSeparator()
        select_menu.addAction(self.calibration_action)
        select_menu.addAction(self.curve_action)
        select_menu.addAction(self.arrow_action)
        select_menu.addAction(self.text_action)
        select_menu.addSeparator()
        select_menu.addAction(self.measure_x_action)
        select_menu.addAction(self.measure_y_action)
        select_menu.addAction(self.measure_distance_action)
        select_menu.addAction(self.measure_angle_action)
        select_menu.addAction(self.measure_area_action)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.undo_action)
        view_menu.addAction(self.fit_action)
        view_menu.addAction(self.clear_measure_action)

        format_menu = self.menuBar().addMenu("Format")
        format_menu.addAction(self.font_action)
        format_menu.addAction(self.color_action)

    def _build_toolbars(self) -> None:
        tools = QToolBar("Tools", self)
        tools.setObjectName("toolsToolbar")
        tools.setMovable(True)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tools)
        tools.addAction(self.mouse_action)
        tools.addSeparator()
        tools.addAction(self.calibration_action)
        tools.addAction(self.curve_action)
        tools.addAction(self.arrow_action)
        tools.addAction(self.text_action)
        tools.addSeparator()
        tools.addAction(self.measure_x_action)
        tools.addAction(self.measure_y_action)
        tools.addAction(self.measure_distance_action)
        tools.addAction(self.measure_angle_action)
        tools.addAction(self.measure_area_action)

        settings = QToolBar("Calibration", self)
        settings.setObjectName("calibrationToolbar")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, settings)

        panel = QWidget(self)
        layout = QFormLayout(panel)
        layout.setContentsMargins(8, 2, 8, 2)

        self.calibration_spin = QDoubleSpinBox(panel)
        self.calibration_spin.setDecimals(8)
        self.calibration_spin.setRange(0.00000001, 1_000_000.0)
        self.calibration_spin.setValue(self.legacy_config.calibrate_value)
        self.calibration_spin.setSingleStep(0.1)
        self.calibration_spin.setToolTip("Real unit per pixel")

        self.unit_combo = QComboBox(panel)
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(["nm", "um"])
        self.unit_combo.setCurrentText(self.legacy_config.unit)
        self.unit_combo.setToolTip("Measurement unit; common choices are nm and um")

        self.decimal_places_spin = QSpinBox(panel)
        self.decimal_places_spin.setRange(0, 8)
        self.decimal_places_spin.setValue(self.legacy_config.decimal_places)
        self.decimal_places_spin.setToolTip("Decimal places for measurement results")

        self.show_pixel_values_check = QCheckBox("Show px", panel)
        self.show_pixel_values_check.setChecked(self.legacy_config.show_pixel_values)
        self.show_pixel_values_check.setToolTip("Show pixel values in measurement result text")

        self.measurement_mode_combo = QComboBox(panel)
        self.measurement_mode_combo.addItem("Click points", "click")
        self.measurement_mode_combo.addItem("Drag", "drag")
        mode_index = self.measurement_mode_combo.findData(self.legacy_config.measurement_interaction_mode)
        self.measurement_mode_combo.setCurrentIndex(max(0, mode_index))
        self.measurement_mode_combo.setToolTip("Linear measurement interaction")

        layout.addRow("Calibrate", self.calibration_spin)
        layout.addRow("Unit", self.unit_combo)
        layout.addRow("Decimals", self.decimal_places_spin)
        layout.addRow("Measure mode", self.measurement_mode_combo)
        layout.addRow("", self.show_pixel_values_check)
        settings.addWidget(panel)

        style = QToolBar("Format", self)
        style.setObjectName("formatToolbar")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, style)

        style_panel = QWidget(self)
        style_layout = QFormLayout(style_panel)
        style_layout.setContentsMargins(8, 2, 8, 2)

        self.color_button = QPushButton("Color", style_panel)
        self.color_button.setToolTip("Annotation color")
        self.color_button.setFixedWidth(72)
        self._update_color_button()

        self.font_size_spin = QSpinBox(style_panel)
        self.font_size_spin.setRange(6, 96)
        self.font_size_spin.setValue(self.legacy_config.annotation_font_size)
        self.font_size_spin.setToolTip("Text size")

        self.line_width_spin = QSpinBox(style_panel)
        self.line_width_spin.setRange(1, 20)
        self.line_width_spin.setValue(self.legacy_config.line_width)
        self.line_width_spin.setToolTip("Line width")

        style_layout.addRow("Color", self.color_button)
        style_layout.addRow("Text size", self.font_size_spin)
        style_layout.addRow("Line width", self.line_width_spin)
        style.addWidget(style_panel)

    def _connect_signals(self) -> None:
        self.open_action.triggered.connect(self._open_image)
        self.save_action.triggered.connect(self._save_as_image)
        self.save_as_action.triggered.connect(self._save_as_image)
        self.export_measurements_action.triggered.connect(self._export_measurements_csv)
        self.save_settings_action.triggered.connect(self._save_settings)
        self.exit_action.triggered.connect(self.close)
        self.fit_action.triggered.connect(self.canvas.reset_view)
        self.clear_measure_action.triggered.connect(self.canvas.clear_measurements)
        self.undo_action.triggered.connect(self.canvas.undo_last_operation)
        self.font_action.triggered.connect(self._choose_font)
        self.color_action.triggered.connect(self._choose_color)

        self.mouse_action.triggered.connect(lambda: self.canvas.set_tool("mouse"))
        self.calibration_action.triggered.connect(lambda: self.canvas.set_tool("calibration"))
        self.curve_action.triggered.connect(lambda: self.canvas.set_tool("curve"))
        self.arrow_action.triggered.connect(lambda: self.canvas.set_tool("arrow"))
        self.text_action.triggered.connect(lambda: self.canvas.set_tool("text"))
        self.measure_x_action.triggered.connect(lambda: self.canvas.set_tool("measure_x"))
        self.measure_y_action.triggered.connect(lambda: self.canvas.set_tool("measure_y"))
        self.measure_distance_action.triggered.connect(lambda: self.canvas.set_tool("measure_distance"))
        self.measure_angle_action.triggered.connect(lambda: self.canvas.set_tool("measure_angle"))
        self.measure_area_action.triggered.connect(lambda: self.canvas.set_tool("measure_area"))

        self.calibration_spin.valueChanged.connect(self._set_calibration)
        self.unit_combo.currentTextChanged.connect(self._set_unit)
        self.decimal_places_spin.valueChanged.connect(self._set_decimal_places)
        self.show_pixel_values_check.toggled.connect(self._set_show_pixel_values)
        self.measurement_mode_combo.currentIndexChanged.connect(self._set_measurement_interaction_mode)
        self.color_button.clicked.connect(self._choose_color)
        self.font_size_spin.valueChanged.connect(self._set_font_size)
        self.line_width_spin.valueChanged.connect(self.canvas.set_line_width)
        self.canvas.cursor_position_changed.connect(self._set_cursor_position)
        self.canvas.measurement_changed.connect(self._set_measurement)
        self.canvas.image_loaded.connect(self._on_image_loaded)
        self.canvas.image_loaded.connect(lambda _path: self.magnifier_panel.set_image(self.canvas.image_bgr))
        self.canvas.cursor_image_position_changed.connect(self.magnifier_panel.update_position)
        self.canvas.calibration_changed.connect(self._on_canvas_calibration_changed)
        self.canvas.operation_recorded.connect(self._append_measurement_result)
        self.canvas.operation_removed.connect(self._remove_last_measurement_result)
        self.canvas.operations_cleared.connect(self._clear_measurement_results)

    def _open_image(self) -> None:
        try:
            self.canvas.open_image_dialog(self.legacy_config.last_directory)
        except Exception as exc:
            QMessageBox.critical(self, "Error Loading Image", str(exc))

    def _save_as_image(self) -> None:
        try:
            self.canvas.save_rendered_image_dialog()
        except Exception as exc:
            QMessageBox.critical(self, "Error Saving Image", str(exc))

    def _export_measurements_csv(self) -> None:
        rows = self._measurement_rows()
        if not rows:
            QMessageBox.information(self, "Export Measurements CSV", "No measurements to export.")
            return

        start_name = "measurements.csv"
        image_path = self.canvas.image_path
        if image_path is not None:
            start_name = str(image_path.with_name(f"{image_path.stem}_measurements.csv"))

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Measurements CSV",
            start_name,
            "CSV (*.csv);;All Files (*.*)",
        )
        if not file_name:
            return

        try:
            with Path(file_name).open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["index", "result"])
                writer.writerows(rows)
        except OSError as exc:
            QMessageBox.critical(self, "Export Measurements CSV", str(exc))
            return

        self._status.showMessage(f"Measurements exported: {file_name}", 3000)

    def _save_settings(self) -> None:
        self._write_settings()
        self._status.showMessage(f"Settings saved: {self.settings_path}", 3000)

    def _write_settings(self) -> None:
        image_path = self.canvas.image_path
        directory = image_path.parent if image_path is not None else self.legacy_config.last_directory
        save_config(
            self.settings_path,
            LegacyConfig(
                calibrate_value=self.calibration_spin.value(),
                last_directory=directory,
                unit=self.unit_combo.currentText().strip() or "nm",
                decimal_places=self.decimal_places_spin.value(),
                show_pixel_values=self.show_pixel_values_check.isChecked(),
                measurement_interaction_mode=self.measurement_mode_combo.currentData(),
                magnifier_zoom=self.magnifier_panel.zoom(),
                annotation_color=self._annotation_color.name(),
                annotation_font_family=self.canvas.annotation_font.family(),
                annotation_font_size=self.canvas.annotation_font.pointSize(),
                line_width=self.canvas.line_width,
                window_geometry=self._encode_qbytearray(self.saveGeometry()),
                window_state=self._encode_qbytearray(self.saveState()),
                magnifier_splitter_sizes=",".join(str(size) for size in self.magnifier_panel.splitter_sizes()),
            ),
        )

    def _apply_loaded_settings(self) -> None:
        font = QFont(self.legacy_config.annotation_font_family) if self.legacy_config.annotation_font_family else QFont()
        font.setPointSize(self.legacy_config.annotation_font_size)
        self.canvas.set_annotation_font(font)
        self.canvas.set_annotation_color(self._annotation_color)
        self.canvas.set_annotation_font_size(self.font_size_spin.value())
        self.canvas.set_line_width(self.line_width_spin.value())
        self.canvas.unit = self.unit_combo.currentText()
        self.canvas.set_decimal_places(self.decimal_places_spin.value())
        self.canvas.show_pixel_values = self.show_pixel_values_check.isChecked()
        self.canvas.set_measurement_interaction_mode(self.measurement_mode_combo.currentData())
        self.magnifier_panel.set_zoom(self.legacy_config.magnifier_zoom)
        self.magnifier_panel.set_splitter_sizes(self._parse_int_list(self.legacy_config.magnifier_splitter_sizes))

        geometry = self._decode_qbytearray(self.legacy_config.window_geometry)
        if geometry:
            self.restoreGeometry(geometry)
        state = self._decode_qbytearray(self.legacy_config.window_state)
        if state:
            self.restoreState(state)

    def _set_calibration(self, value: float) -> None:
        self.canvas.calibration_value = value
        self._update_status()

    def _on_canvas_calibration_changed(self, value: float) -> None:
        self.canvas.calibration_value = value
        self.calibration_spin.blockSignals(True)
        self.calibration_spin.setValue(value)
        self.calibration_spin.blockSignals(False)
        self._update_status()

    def _set_unit(self, unit: str) -> None:
        self.canvas.unit = unit.strip() or "nm"
        self._update_status()

    def _set_decimal_places(self, decimal_places: int) -> None:
        self.canvas.set_decimal_places(decimal_places)
        self._update_status()

    def _set_show_pixel_values(self, show: bool) -> None:
        self.canvas.show_pixel_values = show

    def _set_measurement_interaction_mode(self, *_args) -> None:
        self.canvas.set_measurement_interaction_mode(self.measurement_mode_combo.currentData())

    def _choose_font(self) -> None:
        font, accepted = QFontDialog.getFont(self.canvas.annotation_font, self, "Font")
        if not accepted:
            return
        self.canvas.set_annotation_font(font)
        point_size = font.pointSize()
        if point_size <= 0:
            point_size = self.font_size_spin.value()
            self.canvas.set_annotation_font_size(point_size)
        self.font_size_spin.blockSignals(True)
        self.font_size_spin.setValue(point_size)
        self.font_size_spin.blockSignals(False)
        self._update_status()

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self._annotation_color, self, "Color")
        if not color.isValid():
            return
        self._annotation_color = color
        self.canvas.set_annotation_color(color)
        self._update_color_button()

    def _set_font_size(self, point_size: int) -> None:
        self.canvas.set_annotation_font_size(point_size)
        self._update_status()

    def _update_color_button(self) -> None:
        color_name = self._annotation_color.name()
        self.color_button.setStyleSheet(
            f"QPushButton {{ background-color: {color_name}; color: white; border: 1px solid #555; }}"
        )

    def _set_cursor_position(self, x: float, y: float) -> None:
        self._coord_label = f"X = {x:.0f}, Y = {y:.0f}"
        self._update_status()

    def _set_measurement(self, text: str) -> None:
        self._measurement_label = text
        self._update_status()

    def _append_measurement_result(self, text: str) -> None:
        row = self.measurement_table.rowCount()
        self.measurement_table.insertRow(row)
        self.measurement_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.measurement_table.setItem(row, 1, QTableWidgetItem(text))
        self.measurement_table.scrollToBottom()

    def _remove_last_measurement_result(self, _text: str) -> None:
        row = self.measurement_table.rowCount() - 1
        if row >= 0:
            self.measurement_table.removeRow(row)

    def _clear_measurement_results(self) -> None:
        self.measurement_table.setRowCount(0)

    def _measurement_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for row in range(self.measurement_table.rowCount()):
            index_item = self.measurement_table.item(row, 0)
            result_item = self.measurement_table.item(row, 1)
            index = index_item.text() if index_item is not None else str(row + 1)
            result = result_item.text() if result_item is not None else ""
            rows.append((index, result))
        return rows

    def _on_image_loaded(self, path: str) -> None:
        self._status.showMessage(f"Loaded: {path}", 3000)

    def _update_status(self) -> None:
        calibration = f"CALIBRATE = {self.calibration_spin.value():.8f} {self.unit_combo.currentText()}/px"
        parts = ["Status:", self._coord_label, calibration]
        if self._measurement_label:
            parts.append(self._measurement_label)
        self._status.showMessage("   |   ".join(parts))

    def closeEvent(self, event) -> None:
        self._write_settings()
        super().closeEvent(event)

    @staticmethod
    def _parse_int_list(raw: str) -> list[int]:
        values: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(int(part))
            except ValueError:
                continue
        return values

    @staticmethod
    def _encode_qbytearray(data: QByteArray) -> str:
        return bytes(data.toBase64()).decode("ascii")

    @staticmethod
    def _decode_qbytearray(data: str) -> QByteArray:
        if not data:
            return QByteArray()
        return QByteArray.fromBase64(data.encode("ascii"))

    def _not_implemented(self) -> None:
        QMessageBox.information(self, "Not Implemented", "This function is planned for the next MVP step.")
