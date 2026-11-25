# Smart Door Camera — 3D Printable Enclosure (`/sim/enclosure`)

Weatherproof outdoor enclosure designed for **Raspberry Pi 4 / 5**, **Camera Module 3 (Wide)**, **HC-SR501 PIR Sensor**, **0.96" SSD1306 I2C OLED**, and a **16 mm Illuminated Momentary Doorbell Button**.

## Files
- `generate_case.py` — Parametric CadQuery script (with built-in binary STL mesh fallback) that outputs `smart_door_case.stl`.
- `smart_door_case.stl` — Ready-to-slice 3D model in millimeters (`112 × 82 × 38 mm` + integrated top rain hood & wall-mount ears).

## Regenerating the STL
```bash
python sim/enclosure/generate_case.py
```
If `cadquery` is installed (`pip install cadquery`), it exports the filleted B-rep solid; otherwise, the built-in mesh generator writes the binary `smart_door_case.stl` directly.

## Recommended 3D Printing Settings
| Parameter | Recommendation |
|---|---|
| **Material** | **PETG** or **ASA** (UV & outdoor weather resistant; avoid PLA in direct sun) |
| **Layer Height** | `0.20 mm` |
| **Wall Perimeters** | `4` (`1.6 mm` shell minimum) |
| **Infill** | `25%` Gyroid |
| **Supports** | Build-plate only (for side mounting flanges if printed back-down) |
| **Hardware** | 4× `M2.5 × 6 mm` screws for Raspberry Pi standoffs (`58 × 49 mm`), silicone O-ring or clear acrylic disk (`Ø 20 mm`) over camera bezel |
