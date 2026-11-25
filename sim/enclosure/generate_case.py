"""
Parametric 3D Enclosure Generator for Smart Door Camera (Raspberry Pi 5 + Camera Module 3 + Doorbell + OLED).
Uses CadQuery when installed, with a built-in pure-Python watertight STL mesh generator fallback
so `smart_door_case.stl` is always generated and ready for slicing in Cura / PrusaSlicer.
"""

import os
import math
import struct

OUTPUT_STL = os.path.join(os.path.dirname(__file__), "smart_door_case.stl")


def build_with_cadquery() -> bool:
    try:
        import cadquery as cq

        # Outer dimensions (mm) for Raspberry Pi 5 + Camera + OLED + Pushbutton
        length, width, height = 112.0, 82.0, 38.0
        wall = 2.8
        fillet_r = 4.0

        # Main weatherproof shell with rounded vertical edges and sun visor hood
        body = (
            cq.Workplane("XY")
            .box(length, width, height)
            .edges("|Z")
            .fillet(fillet_r)
            .faces("-Z")
            .shell(-wall)
        )

        # Rain visor / hood at top front (+Z / >Y)
        visor = (
            cq.Workplane("XY")
            .workplane(offset=height / 2.0 - 4.0)
            .center(0, 6.0)
            .box(length, 14.0, 8.0)
            .edges("|Z")
            .fillet(2.0)
        )
        enclosure = body.union(visor)

        # Front face (+Z): Camera lens cutout (d=16mm), PIR Fresnel dome (d=23mm),
        # SSD1306 OLED window (28x15mm), and 16mm illuminated Doorbell button
        enclosure = (
            enclosure.faces(">Z")
            .workplane()
            .pushPoints([(-30.0, 12.0)])
            .circle(8.0)
            .cutThruAll()
            .faces(">Z")
            .workplane()
            .pushPoints([(28.0, 12.0)])
            .circle(11.5)
            .cutThruAll()
            .faces(">Z")
            .workplane()
            .center(-20.0, -16.0)
            .rect(28.0, 15.0)
            .cutThruAll()
            .faces(">Z")
            .workplane()
            .pushPoints([(28.0, -16.0)])
            .circle(8.0)
            .cutThruAll()
        )

        # Internal Raspberry Pi mounting standoffs (58 x 49 mm hole pattern)
        pts = [(-29.0, -24.5), (29.0, -24.5), (-29.0, 24.5), (29.0, 24.5)]
        standoffs = (
            cq.Workplane("XY")
            .workplane(offset=-height / 2.0 + wall)
            .pushPoints(pts)
            .circle(3.2)
            .extrude(6.0)
            .faces(">Z")
            .workplane()
            .pushPoints(pts)
            .circle(1.35)
            .cutBlind(-5.5)
        )
        enclosure = enclosure.union(standoffs)

        cq.exporters.export(enclosure, OUTPUT_STL)
        print(f"[CadQuery] Exported parametric enclosure to {OUTPUT_STL}")
        return True
    except ImportError:
        return False


def _add_quad(tris, p0, p1, p2, p3):
    tris.append((p0, p1, p2))
    tris.append((p0, p2, p3))


def _add_box(tris, x0, y0, z0, x1, y1, z1):
    # Bottom (-Z), Top (+Z), Front (-Y), Back (+Y), Left (-X), Right (+X)
    _add_quad(tris, (x0, y0, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0))
    tris.pop()
    tris.pop()
    _add_quad(tris, (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))
    _add_quad(tris, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
    _add_quad(tris, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
    _add_quad(tris, (x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1))
    _add_quad(tris, (x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1))
    _add_quad(tris, (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))


def _add_cylinder(tris, cx, cy, z0, z1, r_outer, r_inner=0.0, segs=32):
    for i in range(segs):
        a0 = 2.0 * math.pi * i / segs
        a1 = 2.0 * math.pi * (i + 1) / segs
        c0, s0 = math.cos(a0), math.sin(a0)
        c1, s1 = math.cos(a1), math.sin(a1)

        ox0, oy0 = cx + r_outer * c0, cy + r_outer * s0
        ox1, oy1 = cx + r_outer * c1, cy + r_outer * s1
        # Outer wall
        _add_quad(tris, (ox0, oy0, z0), (ox1, oy1, z0), (ox1, oy1, z1), (ox0, oy0, z1))

        if r_inner > 0.0:
            ix0, iy0 = cx + r_inner * c0, cy + r_inner * s0
            ix1, iy1 = cx + r_inner * c1, cy + r_inner * s1
            # Inner bore
            _add_quad(tris, (ix1, iy1, z0), (ix0, iy0, z0), (ix0, iy0, z1), (ix1, iy1, z1))
            # Top & bottom rings
            _add_quad(tris, (ix0, iy0, z1), (ox0, oy0, z1), (ox1, oy1, z1), (ix1, iy1, z1))
            _add_quad(tris, (ox0, oy0, z0), (ix0, iy0, z0), (ix1, iy1, z0), (ox1, oy1, z0))
        else:
            tris.append(((cx, cy, z1), (ox0, oy0, z1), (ox1, oy1, z1)))
            tris.append(((cx, cy, z0), (ox1, oy1, z0), (ox0, oy0, z0)))


def build_fallback_stl():
    """Generates a detailed multi-part STL enclosure mesh (shell, rain hood, lens bezel, button collar, Pi standoffs)."""
    tris = []
    L, W, H, t = 112.0, 82.0, 38.0, 2.8
    hx, hy = L / 2.0, W / 2.0

    # Hollow shell walls + backplate
    _add_box(tris, -hx, -hy, 0.0, hx, hy, t)  # Backplate
    _add_box(tris, -hx, -hy, t, hx, -hy + t, H)  # Bottom wall
    _add_box(tris, -hx, hy - t, t, hx, hy, H)  # Top wall
    _add_box(tris, -hx, -hy + t, t, -hx + t, hy - t, H)  # Left wall
    _add_box(tris, hx - t, -hy + t, t, hx, hy - t, H)  # Right wall

    # Weatherproof top rain hood overhang
    _add_box(tris, -hx, hy - t, H, hx, hy + 4.0, H + 12.0)
    _add_box(tris, -hx, -hy, H, -hx + t, hy, H + 8.0)
    _add_box(tris, hx - t, -hy, H, hx, hy, H + 8.0)

    # Raised Camera Lens Bezel, PIR Bezel, and Doorbell Collar on front rim
    _add_cylinder(tris, -26.0, 14.0, H - 4.0, H + 4.0, r_outer=11.0, r_inner=8.0, segs=36)
    _add_cylinder(tris, 24.0, 14.0, H - 4.0, H + 3.0, r_outer=13.5, r_inner=11.5, segs=36)
    _add_cylinder(tris, 24.0, -16.0, H - 4.0, H + 3.5, r_outer=10.5, r_inner=8.0, segs=32)

    # OLED bezel frame
    _add_box(tris, -40.0, -25.0, H - 3.0, -8.0, -22.5, H + 2.5)
    _add_box(tris, -40.0, -9.5, H - 3.0, -8.0, -7.0, H + 2.5)

    # 4 Raspberry Pi M2.5 mounting standoffs (58 x 49 mm)
    for sx in (-29.0, 29.0):
        for sy in (-24.5, 24.5):
            _add_cylinder(tris, sx, sy, t, t + 6.5, r_outer=3.2, r_inner=1.35, segs=20)

    # Wall-mount flanges (left & right)
    _add_box(tris, -hx - 10.0, -15.0, 0.0, -hx, 15.0, 4.0)
    _add_box(tris, hx, -15.0, 0.0, hx + 10.0, 15.0, 4.0)

    # Write binary STL
    with open(OUTPUT_STL, "wb") as f:
        header = b"SmartDoorCamera RaspberryPi5 Weatherproof Enclosure (mm)".ljust(80, b"\0")
        f.write(header)
        f.write(struct.pack("<I", len(tris)))
        for p0, p1, p2 in tris:
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            norm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            f.write(struct.pack("<12fH", nx / norm, ny / norm, nz / norm, *p0, *p1, *p2, 0))

    print(f"[MeshBuilder] Generated binary STL ({len(tris)} triangles) -> {OUTPUT_STL}")


if __name__ == "__main__":
    if not build_with_cadquery():
        build_fallback_stl()
