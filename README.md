# ImageCaliper

Version: 1.0.0

ImageCaliper is a modern cross-platform image measurement and annotation tool, rewritten from the legacy `Image Processing English V1.0` workflow.

Initial target:

- Windows-first development
- macOS and Linux compatible architecture
- Python + PySide6 + OpenCV

## Run

```powershell
cd image-caliper
python -m image_caliper
```

On macOS or Linux, install Python 3.11+ first, then run:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m image_caliper
```

## Current MVP Scope

- Load legacy `Processing.ini`
- Open image files
- Pan and zoom image canvas
- Show cursor coordinates
- Interactive calibration
- Width, height, distance, angle, and circle area measurement
- Editable measurement unit, with common choices `nm` and `um`
- Configurable measurement decimal places
- Linear measurements, calibration, arrow, angle, and circle area support click-point or drag interaction
- Linear measurement guides render as double-headed arrows with end caps
- Optional pixel-value details in measurement text, off by default
- Curve, arrow, and text annotations
- Annotation font, color, text size, and line width controls
- Browser magnifier dock
- Measurement results dock
- Measurement CSV export
- Persistent settings in `settings.ini`

## Assets

- Application icon: `assets/imagecaliper-icon.png`
- Windows icon bundle: `assets/imagecaliper-icon.ico`
