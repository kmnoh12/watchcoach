"""Pack scene-derived numerals into one 28-row atlas, not 28 moving draw groups."""
from __future__ import annotations

from functools import lru_cache

import numpy as np


WIDTH, DEPTH, PITCH, FIXED_ROWS, LIFT_ROWS = .380, .310, .039, 14, 14


def load_numbers(row: int) -> tuple[str, str]:
    # Scene convention (vendor/equipment_machines.py::_plate_stack), extended to
    # the app's 28 physical slots. Visual markings only, not measured resistance.
    kg = 2.5 + (LIFT_ROWS - 1 - row) * 5
    return f'{kg:g}', str(round(kg * 2.20462262))


def _srgb_hex(linear):
    def channel(v):
        return round(255 * (12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055))
    return '#' + ''.join(f'{channel(c):02x}' for c in linear)


@lru_cache(maxsize=1)
def atlas():
    from scene_lat_parts import build_stickers

    rows = range(-FIXED_ROWS, LIFT_ROWS)
    layers = {}
    extent = 0.
    y = 0.
    for row in rows:
        for part in build_stickers(WIDTH, DEPTH, PITCH-.004, *load_numbers(row)):
            v = np.asarray(part.verts)
            assert np.max(v[:, 1]) < -DEPTH/2, 'Sticker lies inside casting'
            assert np.all(abs(v[:, 2]) < PITCH/2), 'Sticker exceeds row pitch'
            assert np.min(abs(v[:, 0])) > .008, 'Sticker overlaps the selector pocket'
            extent = max(extent, float(np.max(abs(v[:, 0]))))
            y = min(y, float(np.min(v[:, 1])))
            tris = v[np.asarray(part.tris).reshape(-1, 3)][:, :, [0, 2]] * [1000, -1000]
            tris[:, :, 1] -= row * PITCH * 1000
            paths = layers.setdefault(_srgb_hex(part.color), [])
            for a, b, c in tris:
                paths.append(f'M{a[0]:.3f},{a[1]:.3f}L{b[0]:.3f},{b[1]:.3f} {c[0]:.3f},{c[1]:.3f}Z')
    x = extent + .002
    assert x < WIDTH/2
    lo, mid, hi = (rows.start-.5)*PITCH, -.5*PITCH, (rows.stop-.5)*PITCH
    ink = ''.join(f'<path fill="{color}" d="{"".join(paths)}"/>' for color, paths in layers.items())
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="2048" '
           f'viewBox="{-1000*x:.3f} {-1000*hi:.3f} {2000*x:.3f} {1000*(hi-lo):.3f}" '
           f'preserveAspectRatio="none">{ink}</svg>')
    # Exactly two decals. Local Z retains the sign of the half's midpoint for
    # projection in the renderer. The lift decal uses the original stack track.
    def quad(z0, z1):
        v = np.array([[-x,y,z0], [x,y,z0], [x,y,z1], [-x,y,z1]])
        return v, np.array([0,1,2,0,2,3])  # front normal -Y
    return svg, quad(lo, mid), quad(mid, hi)
