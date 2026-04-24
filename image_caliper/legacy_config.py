from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class LegacyConfig:
    calibrate_value: float = 1.0
    last_directory: Path | None = None
    unit: str = "nm"
    decimal_places: int = 4
    show_pixel_values: bool = False
    measurement_interaction_mode: str = "click"
    magnifier_zoom: int = 2
    annotation_color: str = "#00a6d6"
    annotation_font_family: str = ""
    annotation_font_size: int = 10
    line_width: int = 2
    window_geometry: str = ""
    window_state: str = ""
    magnifier_splitter_sizes: str = ""


def load_legacy_config(path: Path) -> LegacyConfig:
    config = LegacyConfig()
    if not path.exists():
        return config

    parser = ConfigParser()
    parser.read(path, encoding="utf-8")

    if parser.has_section("Calibrate"):
        try:
            config.calibrate_value = parser.getfloat("Calibrate", "Value", fallback=1.0)
        except ValueError:
            config.calibrate_value = 1.0

    # Keep the legacy misspelling for compatibility with the old INI.
    for section_name in ("Diretory", "Directory"):
        if parser.has_section(section_name):
            raw = parser.get(section_name, "string", fallback="").strip()
            if raw:
                config.last_directory = Path(raw)
            break

    if parser.has_section("Display"):
        unit = parser.get("Display", "Unit", fallback=config.unit).strip()
        if unit:
            config.unit = unit
        config.decimal_places = parser.getint("Display", "DecimalPlaces", fallback=config.decimal_places)
        config.decimal_places = max(0, min(8, config.decimal_places))
        config.show_pixel_values = parser.getboolean("Display", "ShowPixelValues", fallback=config.show_pixel_values)
        mode = parser.get("Display", "MeasurementInteractionMode", fallback=config.measurement_interaction_mode).strip()
        if mode in {"click", "drag"}:
            config.measurement_interaction_mode = mode
        config.magnifier_zoom = parser.getint("Display", "MagnifierZoom", fallback=config.magnifier_zoom)
        config.magnifier_zoom = max(1, min(12, config.magnifier_zoom))
        config.magnifier_splitter_sizes = parser.get("Display", "MagnifierSplitterSizes", fallback="").strip()

    if parser.has_section("Annotation"):
        color = parser.get("Annotation", "Color", fallback=config.annotation_color).strip()
        if color:
            config.annotation_color = color
        config.annotation_font_family = parser.get("Annotation", "FontFamily", fallback="").strip()
        config.annotation_font_size = parser.getint("Annotation", "FontSize", fallback=config.annotation_font_size)
        config.annotation_font_size = max(6, min(96, config.annotation_font_size))
        config.line_width = parser.getint("Annotation", "LineWidth", fallback=config.line_width)
        config.line_width = max(1, min(20, config.line_width))

    if parser.has_section("Window"):
        config.window_geometry = parser.get("Window", "Geometry", fallback="").strip()
        config.window_state = parser.get("Window", "State", fallback="").strip()

    return config


def load_config(primary_path: Path, legacy_path: Path) -> LegacyConfig:
    if primary_path.exists():
        return load_legacy_config(primary_path)
    return load_legacy_config(legacy_path)


def save_config(path: Path, config: LegacyConfig) -> None:
    parser = ConfigParser()
    parser["Calibrate"] = {"Value": repr(config.calibrate_value)}
    parser["Diretory"] = {"string": str(config.last_directory or "")}
    parser["Display"] = {
        "Unit": config.unit,
        "DecimalPlaces": str(config.decimal_places),
        "ShowPixelValues": str(config.show_pixel_values),
        "MeasurementInteractionMode": config.measurement_interaction_mode,
        "MagnifierZoom": str(config.magnifier_zoom),
        "MagnifierSplitterSizes": config.magnifier_splitter_sizes,
    }
    parser["Annotation"] = {
        "Color": config.annotation_color,
        "FontFamily": config.annotation_font_family,
        "FontSize": str(config.annotation_font_size),
        "LineWidth": str(config.line_width),
    }
    parser["Window"] = {
        "Geometry": config.window_geometry,
        "State": config.window_state,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        parser.write(file)
