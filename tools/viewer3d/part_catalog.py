"""Parametric lightweight commercial-gym 3D part generators (pure Python + NumPy).

Each generator returns one or more SubPart(verts, tris, color, mat_preset, smooth)
in the EXACT local coordinate space of the original object so transforms (`m`) remain valid.
All triangle winding is strictly outward-facing (CCW when viewed from outside).
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from part_registry import (
    MAT_ACRYLIC,
    MAT_ACCENT,
    MAT_CHROME,
    MAT_FRAME,
    MAT_PAD,
    MAT_RUBBER,
    MAT_SILVER,
)


@dataclass
class SubPart:
    verts: np.ndarray     # (N, 3) float64
    tris: np.ndarray      # (M*3,) int32
    color: list[float]    # [r, g, b] in 0..1
    mat_preset: int
    smooth: bool
    name_suffix: str = ""


def _ensure_outward(verts: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """Verify closed mesh has positive signed volume; flip winding if inverted."""
    t = tris.reshape(-1, 3)
    v0, v1, v2 = verts[t[:, 0]], verts[t[:, 1]], verts[t[:, 2]]
    vol6 = np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2)))
    if vol6 < 0:
        t = t[:, [0, 2, 1]].copy()
    return t.reshape(-1).astype(np.int32)


def _merge_meshes(parts: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    vs, ts = [], []
    off = 0
    for v, t in parts:
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.vstack(vs), np.concatenate(ts).astype(np.int32)


def make_box(mn: np.ndarray, mx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x0, y0, z0 = mn
    x1, y1, z1 = mx
    verts = np.array([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ], dtype=np.float64)
    tris = np.array([
        0, 2, 1, 0, 3, 2,  # -Z
        4, 5, 6, 4, 6, 7,  # +Z
        0, 1, 5, 0, 5, 4,  # -Y
        2, 3, 7, 2, 7, 6,  # +Y
        0, 4, 7, 0, 7, 3,  # -X
        1, 2, 6, 1, 6, 5,  # +X
    ], dtype=np.int32)
    return verts, _ensure_outward(verts, tris)


def make_chamfered_box(mn: np.ndarray, mx: np.ndarray, bevel: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Watertight 1-step 45-degree chamfered box (24 verts, 44 tris) with exact bounds [mn, mx]."""
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    if bevel is None:
        short = float(np.sort(half)[0])
        bevel = min(max(short * 0.22, 0.0025), 0.009)
    bx = min(bevel, half[0] * 0.35)
    by = min(bevel, half[1] * 0.35)
    bz = min(bevel, half[2] * 0.35)

    # Loft 4 rings along Z: bottom cap, bottom shoulder, top shoulder, top cap
    # Each ring is an 8-point chamfered rectangle in XY
    def xy_ring(hx: float, hy: float, cx: float, cy: float) -> list[tuple[float, float]]:
        return [
            (hx - cx, -hy), (hx, -hy + cy),
            (hx, hy - cy), (hx - cx, hy),
            (-hx + cx, hy), (-hx, hy - cy),
            (-hx, -hy + cy), (-hx + cx, -hy),
        ]

    hx, hy, hz = half
    z_levels = [
        (-hz, hx - bx, hy - by, max(bx * 0.4, 1e-4), max(by * 0.4, 1e-4)),
        (-hz + bz, hx, hy, bx, by),
        (hz - bz, hx, hy, bx, by),
        (hz, hx - bx, hy - by, max(bx * 0.4, 1e-4), max(by * 0.4, 1e-4)),
    ]

    verts = []
    for z, rx, ry, cx, cy in z_levels:
        for x, y in xy_ring(rx, ry, cx, cy):
            verts.append([x, y, z])
    verts = np.array(verts, dtype=np.float64) + center

    tris = []
    n = 8
    # Side quads between consecutive rings (0->1, 1->2, 2->3)
    for r in range(3):
        b0 = r * n
        b1 = (r + 1) * n
        for i in range(n):
            j = (i + 1) % n
            tris.extend([b0 + i, b0 + j, b1 + j, b0 + i, b1 + j, b1 + i])
    # Bottom cap (ring 0, facing -Z)
    for i in range(1, n - 1):
        tris.extend([0, i + 1, i])
    # Top cap (ring 3, facing +Z)
    top = 3 * n
    for i in range(1, n - 1):
        tris.extend([top, top + i, top + i + 1])

    return verts, _ensure_outward(verts, np.array(tris, dtype=np.int32))


def make_revolved_profile(
    profile_rz: list[tuple[float, float]],
    n_seg: int = 16,
    axis: int = 2,
    center: np.ndarray | None = None,
    cap_bottom: bool = True,
    cap_top: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Revolve a (radius, axial_coord) profile around X(0), Y(1), or Z(2)."""
    angles = np.linspace(0.0, 2.0 * np.pi, n_seg, endpoint=False)
    ca, sa = np.cos(angles), np.sin(angles)

    verts = []
    for r, z in profile_rz:
        for i in range(n_seg):
            u, v = r * ca[i], r * sa[i]
            if axis == 2:
                verts.append([u, v, z])
            elif axis == 1:
                verts.append([u, z, v])
            else:
                verts.append([z, u, v])

    tris = []
    m = len(profile_rz)
    for k in range(m - 1):
        b0 = k * n_seg
        b1 = (k + 1) * n_seg
        for i in range(n_seg):
            j = (i + 1) % n_seg
            tris.extend([b0 + i, b0 + j, b1 + j, b0 + i, b1 + j, b1 + i])

    if cap_bottom and profile_rz[0][0] > 1e-6:
        c_idx = len(verts)
        z0 = profile_rz[0][1]
        verts.append([0.0, 0.0, z0] if axis == 2 else ([0.0, z0, 0.0] if axis == 1 else [z0, 0.0, 0.0]))
        for i in range(n_seg):
            j = (i + 1) % n_seg
            tris.extend([c_idx, j, i])

    if cap_top and profile_rz[-1][0] > 1e-6:
        c_idx = len(verts)
        z1 = profile_rz[-1][1]
        verts.append([0.0, 0.0, z1] if axis == 2 else ([0.0, z1, 0.0] if axis == 1 else [z1, 0.0, 0.0]))
        top = (m - 1) * n_seg
        for i in range(n_seg):
            j = (i + 1) % n_seg
            tris.extend([c_idx, top + i, top + j])

    verts_arr = np.array(verts, dtype=np.float64)
    if center is not None:
        verts_arr = verts_arr + center
    return verts_arr, _ensure_outward(verts_arr, np.array(tris, dtype=np.int32))


# ---------------------------------------------------------------------------
# Catalog part builders (Stage 1: 11 commercial-gym parts)
# ---------------------------------------------------------------------------

def build_frame_tube_chamfer(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    v, t = make_chamfered_box(mn, mx)
    return [SubPart(v, t, color, mat_preset, smooth=False)]


def build_foot_flange_rubber(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    """Chamfered steel foot crossbar + dark rubber floor end-pads (bottom min Z strictly preserved)."""
    sz = mx - mn
    long_ax = int(np.argmax(sz[:2]))  # 0 (X) or 1 (Y)
    # Main steel crossbar sits slightly inset at ends so rubber caps flush-finish the ends
    pad_len = min(sz[long_ax] * 0.12, 0.085)
    bar_mn = mn.copy(); bar_mx = mx.copy()
    bar_mn[long_ax] += pad_len * 0.5
    bar_mx[long_ax] -= pad_len * 0.5
    bar_mn[2] += min(0.006, sz[2] * 0.12)  # lift steel beam 6mm onto rubber pads

    vb, tb = make_chamfered_box(bar_mn, bar_mx, bevel=min(sz[2] * 0.18, 0.007))

    # Left & right rubber end-caps flush with floor (mn[2])
    caps = []
    for side in (0, 1):
        cmn = mn.copy(); cmx = mx.copy()
        if side == 0:
            cmx[long_ax] = mn[long_ax] + pad_len
        else:
            cmn[long_ax] = mx[long_ax] - pad_len
        # Slightly wider rubber shoe (+4mm each side) for commercial-gym anchor look
        other_ax = 1 - long_ax
        cmn[other_ax] -= 0.005
        cmx[other_ax] += 0.005
        cmx[2] = mn[2] + sz[2] * 1.02
        caps.append(make_chamfered_box(cmn, cmx, bevel=0.005))
    vr, tr = _merge_meshes(caps)

    return [
        SubPart(vb, tb, color, mat_preset, smooth=False),
        SubPart(vr, tr, [0.09, 0.09, 0.10], MAT_RUBBER, smooth=False, name_suffix="_rubber"),
    ]


def build_stack_plate_bevel(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    """Cast-iron beveled weight stack plate with subtle chamfered edges."""
    sz = mx - mn
    bevel = min(sz[2] * 0.16, 0.008)
    v, t = make_chamfered_box(mn, mx, bevel=bevel)
    return [SubPart(v, t, [0.16, 0.17, 0.19], MAT_FRAME, smooth=False)]


def build_stack_acrylic_shield(
    mn: np.ndarray,
    mx: np.ndarray,
    color: list[float],
    mat_preset: int,
    stack_local_bbox: tuple[np.ndarray, np.ndarray] | None = None,
) -> list[SubPart]:
    """Commercial-gym weight stack shroud:
    - Chamfered rear metal backplate (where original stack_guard sits)
    - Smoked translucent 2-panel acrylic front/side shroud with a 76 mm center selector-pin slot
    - Top & bottom dark metal trim caps
    """
    parts: list[SubPart] = []
    # 1. Rear chamfered backplate (exact original bounds)
    v_back, t_back = make_chamfered_box(mn, mx, bevel=0.005)
    parts.append(SubPart(v_back, t_back, [0.19, 0.20, 0.23], MAT_FRAME, smooth=False, name_suffix="_back"))

    if stack_local_bbox is None:
        return parts

    smn, smx = stack_local_bbox
    # Determine which Y side of stack_guard faces the plates
    guard_cy = 0.5 * (mn[1] + mx[1])
    stack_cy = 0.5 * (smn[1] + smx[1])
    front_sign = -1.0 if stack_cy < guard_cy else 1.0

    x0 = min(mn[0], smn[0] - 0.022)
    x1 = max(mn[0], smx[0] + 0.022)
    z0 = mn[2]
    z1 = mx[2]
    front_y = (smn[1] - 0.020) if front_sign < 0 else (smx[1] + 0.020)
    back_y = mx[1] if front_sign < 0 else mn[1]
    y_lo, y_hi = min(front_y, back_y), max(front_y, back_y)

    # 2. Top & bottom slim metal header/footer brackets
    cap_h = 0.036
    v_top, t_top = make_chamfered_box(
        np.array([x0, y_lo, z1 - cap_h]), np.array([x1, y_hi, z1]), bevel=0.006
    )
    v_bot, t_bot = make_chamfered_box(
        np.array([x0, y_lo, z0]), np.array([x1, y_hi, z0 + cap_h]), bevel=0.006
    )
    v_caps, t_caps = _merge_meshes([(v_top, t_top), (v_bot, t_bot)])
    parts.append(SubPart(v_caps, t_caps, [0.22, 0.23, 0.26], MAT_FRAME, smooth=False, name_suffix="_shroud_caps"))

    # 3. Smoked translucent acrylic panels (left + right front panels leaving 76mm center slot, plus 2 side panels)
    t_ac = 0.006
    slot_half = 0.038  # 76 mm center pin slot
    cx = 0.5 * (x0 + x1)
    az0, az1 = z0 + cap_h, z1 - cap_h
    fy0 = front_y - t_ac * 0.5
    fy1 = front_y + t_ac * 0.5

    acrylic_boxes = [
        # Front-left panel
        make_box(np.array([x0, fy0, az0]), np.array([cx - slot_half, fy1, az1])),
        # Front-right panel
        make_box(np.array([cx + slot_half, fy0, az0]), np.array([x1, fy1, az1])),
        # Left side panel
        make_box(np.array([x0, y_lo, az0]), np.array([x0 + t_ac, y_hi, az1])),
        # Right side panel
        make_box(np.array([x1 - t_ac, y_lo, az0]), np.array([x1, y_hi, az1])),
    ]
    v_ac, t_ac_arr = _merge_meshes(acrylic_boxes)
    parts.append(SubPart(v_ac, t_ac_arr, [0.16, 0.20, 0.24], MAT_ACRYLIC, smooth=False, name_suffix="_acrylic"))

    return parts


def build_pulley_guarded(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    """Grooved commercial pulley wheel + sleek U-cheek metallic guard (local Z is wheel axle)."""
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    r = 0.5 * (half[0] + half[1])
    hz = half[2]

    # Grooved wheel profile along Z: outer lip -> V-groove -> outer lip
    r_inner = r * 0.78
    profile = [
        (r * 0.90, -hz),
        (r, -hz * 0.80),
        (r, -hz * 0.45),
        (r_inner, 0.0),
        (r, hz * 0.45),
        (r, hz * 0.80),
        (r * 0.90, hz),
    ]
    vw, tw = make_revolved_profile(profile, n_seg=16, axis=2, center=center)

    # U-cheek pulley guard: two slim rounded cheek plates flanking ±Z + half-rim bridge
    cheek_t = max(hz * 0.22, 0.004)
    z_out = hz * 1.12
    g_r = r * 1.06
    cheek_meshes = []
    for sgn in (-1.0, 1.0):
        z0 = center[2] + (z_out if sgn > 0 else -z_out - cheek_t)
        z1 = center[2] + (z_out + cheek_t if sgn > 0 else -z_out)
        # Compact cheek bracket covering center hub to outer edge
        cheek_meshes.append(make_chamfered_box(
            np.array([center[0] - g_r * 0.55, center[1] - g_r * 0.55, z0]),
            np.array([center[0] + g_r * 0.55, center[1] + g_r * 0.55, z1]),
            bevel=0.003,
        ))
    vg, tg = _merge_meshes(cheek_meshes)

    return [
        SubPart(vw, tw, [0.18, 0.19, 0.22], MAT_FRAME, smooth=True, name_suffix="_wheel"),
        SubPart(vg, tg, [0.48, 0.51, 0.56], MAT_SILVER, smooth=False, name_suffix="_guard"),
    ]


def build_pulley_hub_cap(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    r = 0.5 * (half[0] + half[1])
    hz = half[2]
    profile = [
        (r * 0.72, -hz),
        (r, -hz * 0.72),
        (r, hz * 0.72),
        (r * 0.72, hz),
    ]
    v, t = make_revolved_profile(profile, n_seg=14, axis=2, center=center)
    return [SubPart(v, t, color, MAT_ACCENT, smooth=True)]


def build_guide_rod_chrome(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    axis = int(np.argmax(half))
    other = [half[i] for i in range(3) if i != axis]
    r = 0.5 * (other[0] + other[1])
    hl = half[axis]
    profile = [(r, -hl), (r, hl)]
    v, t = make_revolved_profile(profile, n_seg=12, axis=axis, center=center)
    return [SubPart(v, t, [0.82, 0.85, 0.89], MAT_CHROME, smooth=True)]


def build_pad_contoured_seat(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    """SURFACE_LOCKED contoured ergonomic seat pad:
    - Top contact plane max Z is locked to exact original mx[2] (0.000 mm diff!)
    - XY never exceeds original [mn, mx]
    - Top 74% is smooth superellipse leather cushion, bottom 26% is recessed dark ABS under-trim.
    """
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    hx, hy, hz = half
    z_top = mx[2]
    z_bot = mn[2]
    h_tot = z_top - z_bot

    # ABS under-trim shell (bottom 26%, slightly inset in XY)
    abs_h = h_tot * 0.26
    v_abs, t_abs = make_chamfered_box(
        np.array([mn[0] + hx * 0.06, mn[1] + hy * 0.06, z_bot]),
        np.array([mx[0] - hx * 0.06, mx[1] - hy * 0.06, z_bot + abs_h]),
        bevel=min(abs_h * 0.3, 0.006),
    )

    # Superellipse lofted leather cushion from z_bot + abs_h*0.85 up to exact z_top
    cz0 = z_bot + abs_h * 0.85
    cz1 = z_top
    ch = cz1 - cz0
    n_seg = 20
    angles = np.linspace(0.0, 2.0 * np.pi, n_seg, endpoint=False)
    ca, sa = np.cos(angles), np.sin(angles)
    # Superellipse exponent p = 4.0 -> rounded square cushion silhouette
    p = 4.0
    sx_u = np.sign(ca) * (np.abs(ca) ** (2.0 / p))
    sy_u = np.sign(sa) * (np.abs(sa) ** (2.0 / p))

    # 5 loft rings: bottom tuck -> full shoulder -> upper shoulder -> bevel crown -> flat contact top
    rings = [
        (cz0, 0.94, 0.94),
        (cz0 + ch * 0.20, 1.00, 1.00),
        (cz0 + ch * 0.72, 0.99, 0.99),
        (cz0 + ch * 0.92, 0.93, 0.93),
        (cz1, 0.84, 0.84),  # exact z_top = mx[2] (0.000 mm diff!)
    ]
    verts = []
    for z, rx, ry in rings:
        for i in range(n_seg):
            verts.append([center[0] + hx * rx * sx_u[i], center[1] + hy * ry * sy_u[i], z])

    tris = []
    for k in range(len(rings) - 1):
        b0 = k * n_seg
        b1 = (k + 1) * n_seg
        for i in range(n_seg):
            j = (i + 1) % n_seg
            tris.extend([b0 + i, b0 + j, b1 + j, b0 + i, b1 + j, b1 + i])

    # Bottom cap
    cb = len(verts)
    verts.append([center[0], center[1], cz0])
    for i in range(n_seg):
        j = (i + 1) % n_seg
        tris.extend([cb, j, i])
    # Top flat contact cap at exact z_top
    ct = len(verts)
    verts.append([center[0], center[1], cz1])
    top_off = (len(rings) - 1) * n_seg
    for i in range(n_seg):
        j = (i + 1) % n_seg
        tris.extend([ct, top_off + i, top_off + j])

    v_pad = np.array(verts, dtype=np.float64)
    t_pad = _ensure_outward(v_pad, np.array(tris, dtype=np.int32))

    return [
        SubPart(v_pad, t_pad, [0.11, 0.12, 0.14], MAT_PAD, smooth=True, name_suffix="_cushion"),
        SubPart(v_abs, t_abs, [0.18, 0.19, 0.21], MAT_FRAME, smooth=False, name_suffix="_undertrim"),
    ]


def build_roller_contoured(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    """SURFACE_LOCKED foam thigh/leg roller:
    - Cylinder along local Z, exact outer radius r and length [-hz, hz] preserved (0.000 mm diff!)
    - Smooth rounded bolster foam + dark concentric end-caps.
    """
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    r = 0.5 * (half[0] + half[1])
    hz = half[2]

    # Rounded bolster foam profile (max radius == exact r)
    bevel_z = min(hz * 0.16, r * 0.22)
    profile = [
        (r * 0.76, -hz + 0.002),
        (r * 0.94, -hz + bevel_z * 0.45),
        (r, -hz + bevel_z),
        (r, hz - bevel_z),
        (r * 0.94, hz - bevel_z * 0.45),
        (r * 0.76, hz - 0.002),
    ]
    vf, tf = make_revolved_profile(profile, n_seg=16, axis=2, center=center)

    # Concentric vinyl/metal end-caps
    cap_r = r * 0.62
    c1 = make_revolved_profile([(cap_r, -hz), (cap_r, -hz + 0.004)], n_seg=14, axis=2, center=center)
    c2 = make_revolved_profile([(cap_r, hz - 0.004), (cap_r, hz)], n_seg=14, axis=2, center=center)
    vc, tc = _merge_meshes([c1, c2])

    return [
        SubPart(vf, tf, [0.11, 0.12, 0.14], MAT_PAD, smooth=True, name_suffix="_foam"),
        SubPart(vc, tc, [0.24, 0.26, 0.29], MAT_SILVER, smooth=True, name_suffix="_caps"),
    ]


def build_selector_pin_t(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    """Ergonomic anodized accent knob + chrome steel pin along longest local axis."""
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    axis = int(np.argmax(half))
    other = [half[i] for i in range(3) if i != axis]
    r_knob = max(min(other) * 0.95, 0.014)
    r_pin = min(r_knob * 0.35, 0.007)
    hl = half[axis]

    # Chrome pin spans full length; anodized knob sits at the front (-axis) end
    vp, tp = make_revolved_profile([(r_pin, -hl), (r_pin, hl)], n_seg=10, axis=axis, center=center)
    k_len = min(hl * 0.30, 0.038)
    vk, tk = make_revolved_profile(
        [(r_knob * 0.85, -hl), (r_knob, -hl + k_len * 0.2), (r_knob, -hl + k_len * 0.8), (r_knob * 0.85, -hl + k_len)],
        n_seg=12, axis=axis, center=center,
    )
    return [
        SubPart(vk, tk, color, MAT_ACCENT, smooth=True, name_suffix="_knob"),
        SubPart(vp, tp, [0.80, 0.83, 0.87], MAT_CHROME, smooth=True, name_suffix="_shaft"),
    ]


def build_cable_coated(mn: np.ndarray, mx: np.ndarray, color: list[float], mat_preset: int) -> list[SubPart]:
    """Smooth 8-sided black coated cable preserving exact local axis & [mn, mx]."""
    center = 0.5 * (mn + mx)
    half = 0.5 * (mx - mn)
    # Detect axis: cables in app JSON can be unit cylinders ([-1,1]x[-1,1]x[0,1]) or real-scale ([±0.005]x[0,1]x[±0.005])
    if abs(mn[2] - 0.0) < 1e-4 and abs(mx[2] - 1.0) < 1e-4 and abs(half[0] - 1.0) < 1e-2:
        # Unit cylinder along Z in [0, 1]
        v, t = make_revolved_profile([(1.0, 0.0), (1.0, 1.0)], n_seg=8, axis=2, center=np.zeros(3))
        return [SubPart(v, t, [0.07, 0.07, 0.08], MAT_RUBBER, smooth=True)]
    axis = int(np.argmax(half))
    other = [half[i] for i in range(3) if i != axis]
    r = 0.5 * (other[0] + other[1])
    hl = half[axis]
    v, t = make_revolved_profile([(r, -hl), (r, hl)], n_seg=8, axis=axis, center=center)
    return [SubPart(v, t, [0.07, 0.07, 0.08], MAT_RUBBER, smooth=True)]


def build_carabiner_ring(rx: float, rz: float, tube_r: float = 0.0045) -> SubPart:
    """Clean 14-segment oval torus carabiner ring in XZ plane, centered at origin."""
    n_major = 14
    n_minor = 8
    u = np.linspace(0.0, 2.0 * np.pi, n_major, endpoint=False)
    v_ang = np.linspace(0.0, 2.0 * np.pi, n_minor, endpoint=False)

    verts = []
    for ui in u:
        cx = rx * np.cos(ui)
        cz = rz * np.sin(ui)
        # Tangent in XZ plane
        tx = -rx * np.sin(ui)
        tz = rz * np.cos(ui)
        t_len = np.hypot(tx, tz) + 1e-9
        # Outward normal in XZ plane
        nx = tz / t_len
        nz = -tx / t_len
        for vi in v_ang:
            cv, sv = np.cos(vi), np.sin(vi)
            x = cx + tube_r * cv * nx
            y = tube_r * sv
            z = cz + tube_r * cv * nz
            verts.append([x, y, z])

    tris = []
    for i in range(n_major):
        i_next = (i + 1) % n_major
        for j in range(n_minor):
            j_next = (j + 1) % n_minor
            a = i * n_minor + j
            b = i_next * n_minor + j
            c = i_next * n_minor + j_next
            d = i * n_minor + j_next
            tris.extend([a, b, c, a, c, d])

    va = np.array(verts, dtype=np.float64)
    ta = _ensure_outward(va, np.array(tris, dtype=np.int32))
    return SubPart(va, ta, [0.76, 0.79, 0.84], MAT_CHROME, smooth=True)


CATALOG_BUILDERS = {
    "frame_tube_chamfer": build_frame_tube_chamfer,
    "foot_flange_rubber": build_foot_flange_rubber,
    "stack_plate_bevel": build_stack_plate_bevel,
    "pulley_guarded": build_pulley_guarded,
    "pulley_hub_cap": build_pulley_hub_cap,
    "guide_rod_chrome": build_guide_rod_chrome,
    "pad_contoured_seat": build_pad_contoured_seat,
    "roller_contoured": build_roller_contoured,
    "selector_pin_t": build_selector_pin_t,
    "cable_coated": build_cable_coated,
}
