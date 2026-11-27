"""Stage 1+ App 3D Machine Upgrader & WGM2 Binary Packer.

Upgrades machine JSON files in phone/src/main/assets/viewer3d/data/ (without touching
raw JSONs or Blender scenes) into:
  - data/parts.bin       (WGC2 shared quantized geometry catalog)
  - data/<id>.wgm        (WGM2 compact binary clips with quantized TRS + material presets)
  - data/wgm_manifest.json (list of upgraded model IDs so index.html loads WGM2 with zero 404s)

Runs 3 automated safety gates before writing:
  1. Contact invariance (mm diff): LOCKED_GRIP == 0.00 mm, SURFACE_LOCKED <= 0.50 mm
  2. Full-frame human-machine penetration check against human_v5/<id>.bin (all 65 frames)
  3. Size, triangle, and draw-call budget report

Usage:
  python3 tools/upgrade_app3d_machines.py --prefix lat_pulldown
  python3 tools/upgrade_app3d_machines.py --ids lat_pulldown~g=lat,lat_pulldown~g=rope
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools/viewer3d"))

from part_catalog import (  # noqa: E402
    CATALOG_BUILDERS,
    SubPart,
    build_carabiner_ring,
    build_stack_acrylic_shield,
)
from selector_tower import COAT, RUBBER, STEEL, adjuster_kit, lat_station
from body_fit import SkinSweep, fit_body_part, roller_depth_bound
from lat_stack_labels import atlas
from part_registry import MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER, classify_object, normalize_base_name  # noqa: E402


# ---------------------------------------------------------------------------
# Transform & WGP2 / WGM2 binary helpers
# ---------------------------------------------------------------------------

def decompose_frames(m_list: list[list[float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Decompose list of column-major 4x4 matrices into (pos, quat_xyzw, scale)."""
    arr = np.asarray(m_list, dtype=np.float64).reshape(-1, 4, 4).transpose(0, 2, 1)
    pos = arr[:, :3, 3]
    M3 = arr[:, :3, :3]
    sc = np.linalg.norm(M3, axis=1)
    safe_sc = np.where(sc > 1e-9, sc, 1.0)
    R = M3 / safe_sc[:, None, :]
    dets = np.linalg.det(R)
    neg = dets < 0
    if np.any(neg):
        R[neg, :, 0] *= -1.0
        sc[neg, 0] *= -1.0
    quats = Rotation.from_matrix(R).as_quat()  # xyzw
    for i in range(1, len(quats)):
        if np.dot(quats[i - 1], quats[i]) < 0:
            quats[i] = -quats[i]
    return pos, quats, sc


def compose_matrix(pos: np.ndarray, quat_xyzw: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """Return 4x4 row-major transform matrix."""
    R = Rotation.from_quat(quat_xyzw).as_matrix()
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = R * scale[None, :]
    M[:3, 3] = pos
    return M


def strip_fake_animation(m_list: list[list[float]]) -> list[list[float]]:
    if len(m_list) <= 1:
        return m_list
    arr = np.asarray(m_list, dtype=np.float64)
    if np.max(np.abs(arr - arr[0])) < 1e-5:
        return [m_list[0]]
    return m_list


def load_wgp2_human_frames(bin_path: Path) -> np.ndarray | None:
    """Load all (N_frames, N_verts, 3) float32 human vertices from human_v5/<id>.bin."""
    if not bin_path.exists():
        return None
    raw = bin_path.read_bytes()
    magic, n, n_verts, _ = struct.unpack_from("<4sIII", raw, 0)
    if magic != b"WGP2":
        return None
    mn = np.array(struct.unpack_from("<3f", raw, 16), dtype=np.float64)
    sc = np.array(struct.unpack_from("<3f", raw, 28), dtype=np.float64)
    q_off = 40 + n * 4
    q_delta = np.frombuffer(raw, dtype="<u2", offset=q_off).reshape(n, n_verts, 3)
    # Time-delta decode with uint16 wrap-around
    q = np.cumsum(q_delta.astype(np.uint32), axis=0) & 0xFFFF
    return mn[None, None, :] + q.astype(np.float64) * sc[None, None, :]


class PartCatalogPacker:
    """Deduplicates SubPart meshes into WGC2 binary parts.bin."""

    def __init__(self) -> None:
        self._map: dict[str, int] = {}
        self._blobs: list[bytes] = []
        self._stats: list[tuple[int, int, bool]] = []

    def add(self, verts: np.ndarray, tris: np.ndarray, smooth: bool, uv=None) -> int:
        v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
        t = np.asarray(tris, dtype=np.int32).reshape(-1)
        assert len(v) <= 65535 and len(t) // 3 <= 65535, f"Mesh too large: v={len(v)}, t={len(t)//3}"
        key_bytes = np.round(v, 4).astype("<f4").tobytes() + t.astype("<u2").tobytes() + bytes([1 if smooth else 0])
        uv_bytes = b""
        if uv is not None:
            uv = np.asarray(uv)
            assert uv.shape == (len(v), 2) and np.all((uv >= 0) & (uv <= 1))
            uv_bytes = np.rint(uv * 65535).astype("<u2").tobytes()
            key_bytes += uv_bytes
        h = hashlib.sha1(key_bytes).hexdigest()[:20]
        if h in self._map:
            return self._map[h]

        pid = len(self._blobs)
        self._map[h] = pid
        nv = len(v)
        nt = len(t) // 3
        mn = v.min(axis=0)
        mx = v.max(axis=0)
        sc = np.maximum((mx - mn) / 65535.0, 1e-9)
        q = np.rint((v - mn) / sc).clip(0, 65535).astype("<u2")
        idx = t.astype("<u2")
        flags = int(smooth) | (2 if uv_bytes else 0)
        hdr = struct.pack("<HHB3x6f", nv, nt, flags, *mn.tolist(), *sc.tolist())
        self._blobs.append(hdr + q.tobytes() + idx.tobytes() + uv_bytes)
        self._stats.append((nv, nt, smooth))
        return pid

    def build_bytes(self) -> bytes:
        out = bytearray(struct.pack("<4sI", b"WGC2", len(self._blobs)))
        for b in self._blobs:
            out += b
        return bytes(out)

    @property
    def count(self) -> int:
        return len(self._blobs)


# ---------------------------------------------------------------------------
# Machine upgrade logic
# ---------------------------------------------------------------------------

def _compute_stack_world_bbox(objs: list[dict]) -> tuple[np.ndarray, np.ndarray] | None:
    pts = []
    for o in objs:
        low = o["name"].lower()
        if any(k in low for k in ("rest_plate", "selected_plate", "unselected_weight", "resting_plate")):
            v = np.asarray(o["verts"], dtype=np.float64).reshape(-1, 3)
            m0 = np.asarray(o["m"][0], dtype=np.float64).reshape(4, 4).T
            pts.append(v @ m0[:3, :3].T + m0[:3, 3])
    if not pts:
        return None
    all_pts = np.vstack(pts)
    return all_pts.min(axis=0), all_pts.max(axis=0)


# Opt in by full clip ID: never fit a new machine family to these mounting points by accident.
STAGE1 = tuple('lat_pulldown~' + variant for variant in
               ('g=d', 'g=lat', 'g=mag', 'g=neutral', 'g=rope', 'g=straight', 'm=behind_neck'))
REPLACED = {'stack_guard', 'stack_base', 'selected_plate', 'rest_plate', 'pulley', 'pulley_hub',
            'selector_rod', 'selector_pin', 'rear_brace', 'mast', 'arm'}
LAT_RED_FRAME = {'base', 'foot', 'seat_post', 'seat_sleeve'}


def improved_d_handle_contact(key, obj, part, human, base):
    """Only the D-handle's existing right hand/wrist path may still touch its +X roller."""
    m = np.asarray(obj['m'][0]).reshape(4,4)
    if key != 'lat_pulldown~g=d' or m[3,0] <= 0 or normalize_base_name(obj['name']) != 'thigh_roller':
        return False
    faces = np.asarray(base['triangles']).reshape(-1,3)
    dominant = np.asarray(base['joints'])[np.arange(human.shape[1]), np.asarray(base['weights']).argmax(1)]
    bones = np.asarray(base['bone_names'])[dominant]
    wrist = np.array([b.endswith('_r') and b.split('_')[0] in
                      ('lowerarm','hand','thumb','index','middle','ring','pinky') for b in bones])
    if not SkinSweep(human, faces[~wrist[faces].all(1)]).clear(part):
        return False
    # Compare against legacy convex foam at its original mount on THIS body, not a
    # fixed mm allowance. Ignoring old caps only lowers the reference. Enclosing
    # the new foam + caps in their hull only raises the candidate depth bound.
    v = np.asarray(obj['verts']).reshape(-1,3)
    foam, _ = CATALOG_BUILDERS['roller_contoured'](v.min(0), v.max(0), obj['color'], MAT_PAD)
    previous = roller_depth_bound(human[:,wrist], foam.verts @ m[:3,:3] + m[3,:3], swept=False)
    current = roller_depth_bound(human, part, swept=True)
    print(f'  D-handle wrist/roller: legacy >= {previous*1000:.3f} mm; fitted <= {current*1000:.3f} mm')
    return previous > 0 and current <= previous


def fit_lat_rollers(ex_id, objs, human, base):
    """Prefer vertical adjustment. Pitch the post only if another limb crosses the pad.
    Never move the axle out of its original thigh footprint just to clear a hand.
    """
    from scene_lat_parts import build_roller
    pads = []
    for o in objs:
        if normalize_base_name(o['name']) != 'thigh_roller': continue
        assert len(strip_fake_animation(o['m'])) == 1
        m = np.asarray(o['m'][0]).reshape(4,4); pos = m[3,:3]
        v = np.asarray(o['verts']).reshape(-1,3)
        pieces = build_roller(v.min(0), v.max(0), int(np.sign(pos[0]*m[2,0])))
        world = np.vstack([p.verts for p in pieces]) @ m[:3,:3] + pos
        pads.append((o['name'], pos, world, m[2,:3]))
    assert len(pads) == 2
    sweep = SkinSweep(human, np.asarray(base['triangles']).reshape(-1,3))
    reach = min(np.ptp(v[:,1])/2 for _,_,v,_ in pads)
    for dy in [0., *(s*y for y in np.arange(.005,reach+.00001,.005) for s in (1,-1))]:
        fits = {}; ok = True
        for name,pos,v,axle in pads:
            offset = np.array([0.,dy,0.]); centre = pos+offset
            fit = fit_body_part(human, base, 'thigh_roller', centre, v+offset, [0,0,1], axle)
            fits[name] = (pos,fit)
            ok &= sweep.clear(v+fit-pos)
        if ok: return fits, sweep, True
        if dy == 0: vertical = fits
    by_name = {o['name']: o for o in objs}
    for name,pos,v,_ in pads:
        part = v + vertical[name][1] - pos
        if not sweep.clear(part) and not improved_d_handle_contact(ex_id, by_name[name], part, human, base):
            return vertical, sweep, False
    return vertical, sweep, True


def fit_lat_station(objs, packer, n, fits):
    by_name = {}
    for obj in objs:
        by_name.setdefault(normalize_base_name(obj['name']), []).append(obj)
    assert REPLACED <= by_name.keys(), 'Unknown lat station mounts'

    def points(obj):
        m = np.asarray(obj['m'][0]).reshape(4, 4).T
        return np.asarray(obj['verts']).reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]

    def center(obj):
        v = points(obj)
        return (v.min(0) + v.max(0))/2

    pin = by_name['selector_pin'][0]
    pin_pos = np.array(pin['m'])[:, 12:15]
    root = pin_pos[0].copy(); root[2] = points(by_name['stack_base'][0])[:, 2].min()
    lift = pin_pos - pin_pos[0]
    assert len(lift) == n and np.max(np.abs(lift[:, :2])) < .0005, 'Expected a vertical selector stroke'
    for plate in by_name['selected_plate']:
        pos = np.asarray(plate['m'])[:, 12:15]
        assert np.max(np.abs(pos-pos[0]-lift)) < .0005, 'Selected plates do not travel with pin'
    # Snap the shared stroke once. Offsetting each plate before rounding a half-step
    # can put neighbouring plates on different 0.1 mm ticks of the WGM2 track.
    lift = np.rint(lift * 10000.0) / 10000.0
    wheels = sorted(by_name['pulley'], key=lambda o: -center(o)[1]); assert len(wheels) == 3
    # Snap fixture dimensions, not animation, to the nearest mm to share meshes across exporters.
    sheaves = [(np.round(center(o)-root, 3), round(np.ptp(points(o)[:, 1])/2, 3)) for o in wheels]
    thigh = np.round(center(by_name['thigh_cross'][0])-root, 3)
    foot = np.round(center(by_name['foot'][0])-root, 3); foot[0] = round(points(by_name['foot'][0])[:,0].max()-root[0], 3)
    kit = lat_station(*sheaves, round(pin_pos[0,2]-root[2], 3), thigh, foot)
    for orig,target in fits.values():
        arm, = [center(o) for o in by_name['thigh_arm'] if center(o)[0]*orig[0]>0]
        kit.extend(adjuster_kit(thigh, arm-root, orig-root, target-root))
    from scene_lat_parts import palette

    lower_red = palette()['lower_red']
    entries = []
    for part in kit:
        sp = part.part
        pos = root + part.at + (lift if part.lift else np.zeros((1,3)))
        entries.append(dict(name=part.name, role='BODY_FIT' if part.name.startswith('adjuster_') else 'STATION', catalog_id=part.name,
                            part_id=packer.add(sp.verts, sp.tris, sp.smooth), verts=sp.verts, tris=sp.tris,
                            color=lower_red if part.name == 'anchor' else sp.color,
                            mat=sp.mat_preset, smooth=sp.smooth, pos=pos,
                            quats=np.tile(Rotation.from_rotvec([part.pitch,0,0]).as_quat(), (len(pos),1)), sc=np.ones_like(pos)))
    socket = next(e for e in entries if e['name'] == 'load_socket')
    eye = socket['pos'][:,2] + socket['verts'][:,2].max()
    assert max(eye) + .002 < root[2]+sheaves[0][0][2]-sheaves[0][1], 'Load socket hits head sheave at full travel'
    return entries, eye


def check_station_clearance(entries, frames, faces):
    # A separating axis between each padded part box and EVERY human triangle is a
    # conservative non-penetration proof, including thin surfaces that contain no body vertex.
    lo, hi = frames.min(1), frames.max(1)
    face_bounds = {}
    for e in entries:
        if e['role'] != 'STATION':
            continue
        a = e['pos'] + e['verts'].min(0) - .0003
        b = e['pos'] + e['verts'].max(0) + .0003
        for f in np.flatnonzero(np.all((b >= lo) & (a <= hi), axis=1)):
            if f not in face_bounds:
                tris = frames[f][faces]; face_bounds[f] = tris.min(1), tris.max(1)
            mn,mx = face_bounds[f]; i = f if len(a)>1 else 0
            assert not np.any(np.all((mn <= b[i]) & (mx >= a[i]), axis=1)), f"Body clearance not proved: {e['name']} at frame {f}"


def upgrade_machine(
    ex_id: str,
    raw_data: dict,
    packer: PartCatalogPacker,
    human_frames: np.ndarray | None,
    human_faces: np.ndarray | None = None,
    audit: list | None = None,
    *, human_base: dict | None = None,
) -> tuple[bytes, dict]:
    objs = raw_data["objects"]
    acts = raw_data["acts"]

    stack_world_bbox = _compute_stack_world_bbox(objs)

    # Separate carabiner slices so we can merge all 12 into 1 clean ring
    carabiner_slices = []
    other_objs = []
    for o in objs:
        spec = classify_object(o["name"], o.get("color", [0.5, 0.5, 0.5]))
        if spec.role == "CARABINER_SLICE":
            carabiner_slices.append((o, spec))
        else:
            other_objs.append((o, spec))

    upgraded_entries: list[dict] = []  # {name, role, part_id, verts, tris, color, mat, smooth, pos, quats, sc}
    fake_anim_stripped = 0
    max_grip_diff_mm = 0.0
    max_surface_diff_mm = 0.0

    pilot = ex_id in STAGE1
    if pilot:
        from scene_lat_parts import build_roller, build_seat, palette

        lower_red = palette()['lower_red']
        assert human_frames is not None and len(human_frames) == len(acts) and human_faces is not None, f'[{ex_id}] missing matching human frames/faces'
        fits, sweep, roller_clear = fit_lat_rollers(ex_id, objs, human_frames, human_base)
        upgraded_entries, cable_eye = fit_lat_station(objs, packer, len(acts), fits)
        blocked = [] if roller_clear else ['thigh_roller']
        for e in upgraded_entries:
            if e['role'] == 'BODY_FIT':
                w = Rotation.from_quat(e['quats'][0]).apply(e['verts']) + e['pos'][0]
                if not sweep.clear(w): blocked.append(e['name'])

    for o, spec in other_objs:
        if pilot and (spec.base_name in REPLACED or spec.base_name == 'thigh_arm'):
            continue
        v_orig = np.asarray(o["verts"], dtype=np.float64).reshape(-1, 3)
        t_orig = np.asarray(o["tris"], dtype=np.int32).reshape(-1)
        m_list_raw = o["m"]
        m_list = strip_fake_animation(m_list_raw)
        if len(m_list) < len(m_list_raw):
            fake_anim_stripped += 1

        mn, mx = v_orig.min(axis=0), v_orig.max(axis=0)
        color = list(o.get("color", [0.5, 0.5, 0.5]))
        if pilot and spec.base_name.startswith('cable_stack_'):
            # Unit-Z cable. Seat the lower end in the new socket; keep the old upper endpoint fixed.
            assert np.allclose([mn[2], mx[2]], [0, 1])
            m = np.asarray(m_list).reshape(-1,4,4).copy()
            shift = (cable_eye - .003 - m[:,3,2]) / m[:,2,2]
            assert np.all((shift >= 0) & (shift < 1)), 'Cable would invert'
            offset = shift[:,None] * m[:,2,:3]; m[:,3,:3] += offset; m[:,2,:3] -= offset
            m_list = m.reshape(-1,16).tolist()
        pos, quats, sc = decompose_frames(m_list)

        if spec.role in ("LOCKED_GRIP", "KEEP_ORIGINAL") or spec.catalog_id is None:
            # Preserve exact geometry (0.000 mm diff)
            smooth = spec.base_name.startswith(("bar_", "grip_", "handle_", "rope_", "swivel_"))
            subparts = [SubPart(v_orig, t_orig, color, spec.mat_preset, smooth=smooth)]
        elif spec.catalog_id == "stack_acrylic_shield":
            # Convert stack world bbox into stack_guard's local space
            local_stack_bbox = None
            if stack_world_bbox is not None:
                m0 = np.asarray(m_list[0], dtype=np.float64).reshape(4, 4).T
                m0_inv = np.linalg.inv(m0)
                s_mn, s_mx = stack_world_bbox
                corners = np.array([
                    [x, y, z]
                    for x in (s_mn[0], s_mx[0])
                    for y in (s_mn[1], s_mx[1])
                    for z in (s_mn[2], s_mx[2])
                ])
                lc = corners @ m0_inv[:3, :3].T + m0_inv[:3, 3]
                local_stack_bbox = (lc.min(axis=0), lc.max(axis=0))
            subparts = build_stack_acrylic_shield(mn, mx, color, spec.mat_preset, local_stack_bbox)
        else:
            builder = CATALOG_BUILDERS[spec.catalog_id]
            subparts = builder(mn, mx, color, spec.mat_preset)
        if pilot and spec.catalog_id == 'pad_contoured_seat':
            cushion, trim = subparts
            subparts = [*build_seat(cushion.verts.min(0), cushion.verts.max(0)), trim]
        elif pilot and spec.catalog_id == 'roller_contoured':
            # Preserve the original local axle and motion; which end faces out
            # depends on the placement and signed local-Z basis of each instance.
            m0 = compose_matrix(pos[0], quats[0], sc[0])
            outer_sign = np.sign(pos[0, 0] * m0[0, 2])
            assert outer_sign, 'Expected a mirrored pair of off-axis lat rollers'
            all_orig = np.vstack([sp.verts for sp in subparts])
            subparts = build_roller(all_orig.min(0), all_orig.max(0), int(outer_sign))
            pos = fits[o['name']][1][None,:]

        # Gate 1: Contact invariance check
        if spec.role == "LOCKED_GRIP":
            diff_mm = float(np.max(np.abs(subparts[0].verts - v_orig)) * 1000.0)
            max_grip_diff_mm = max(max_grip_diff_mm, diff_mm)
            assert diff_mm == 0.0, f"[{ex_id}] LOCKED_GRIP {o['name']} moved {diff_mm:.3f} mm!"
        elif spec.role == "SURFACE_LOCKED":
            all_v = np.vstack([sp.verts for sp in subparts])
            if spec.catalog_id == "pad_contoured_seat":
                # World max Z (top sitting surface) must match <= 0.5 mm
                m0 = compose_matrix(pos[0], quats[0], sc[0])
                w_orig = v_orig @ m0[:3, :3].T + m0[:3, 3]
                w_new = all_v @ m0[:3, :3].T + m0[:3, 3]
                z_diff_mm = abs(float(w_new[:, 2].max() - w_orig[:, 2].max())) * 1000.0
                max_surface_diff_mm = max(max_surface_diff_mm, z_diff_mm)
                assert z_diff_mm <= 0.5, f"[{ex_id}] seat {o['name']} top Z shifted {z_diff_mm:.3f} mm!"
            elif spec.catalog_id == "roller_contoured":
                r_orig = float(np.max(np.hypot(v_orig[:, 0], v_orig[:, 1])))
                r_new = float(np.max(np.hypot(all_v[:, 0], all_v[:, 1])))
                r_diff_mm = abs(r_new - r_orig) * 1000.0
                max_surface_diff_mm = max(max_surface_diff_mm, r_diff_mm)
                assert r_diff_mm <= 0.5, f"[{ex_id}] roller {o['name']} radius shifted {r_diff_mm:.3f} mm!"

        for sp in subparts:
            if pilot and spec.catalog_id:
                if spec.catalog_id == 'frame_tube_chamfer' or spec.base_name == 'seat_lock' or sp.name_suffix in ('_caps', '_undertrim'):
                    if spec.catalog_id != 'roller_contoured':
                        sp.color, sp.mat_preset = COAT, MAT_FRAME
                elif spec.catalog_id == 'foot_flange_rubber':
                    sp.color = RUBBER if sp.mat_preset == MAT_RUBBER else COAT
                    if sp.mat_preset != MAT_RUBBER: sp.mat_preset = MAT_FRAME
                elif sp.mat_preset in (MAT_PAD, MAT_RUBBER) and spec.role != 'SURFACE_LOCKED':
                    sp.color = RUBBER
                elif sp.mat_preset == MAT_CHROME:
                    sp.color = STEEL
                if spec.base_name in LAT_RED_FRAME and sp.mat_preset == MAT_FRAME:
                    sp.color = lower_red
            pid = packer.add(sp.verts, sp.tris, sp.smooth)
            upgraded_entries.append({
                "name": o["name"] + sp.name_suffix,
                "role": spec.role,
                "catalog_id": spec.catalog_id or "original",
                "part_id": pid,
                "verts": sp.verts,
                "tris": sp.tris,
                "color": sp.color,
                "mat": sp.mat_preset,
                "smooth": sp.smooth,
                "pos": pos,
                "quats": quats,
                "sc": sc,
            })

    # Merge 12 carabiner slices into 1 smooth oval carabiner ring
    carabiner_merged_count = 0
    if carabiner_slices:
        carabiner_merged_count = len(carabiner_slices)
        # Compute world bbox of all 12 slices at frame 0
        w_pts = []
        for o, _ in carabiner_slices:
            v = np.asarray(o["verts"], dtype=np.float64).reshape(-1, 3)
            m0 = np.asarray(o["m"][0], dtype=np.float64).reshape(4, 4).T
            w_pts.append(v @ m0[:3, :3].T + m0[:3, 3])
        all_w = np.vstack(w_pts)
        w_mn, w_mx = all_w.min(axis=0), all_w.max(axis=0)
        w_center0 = 0.5 * (w_mn + w_mx)
        w_half = 0.5 * (w_mx - w_mn)

        # Follow rigid translation delta of slice 0 across all frames
        ref_pos, _, _ = decompose_frames(carabiner_slices[0][0]["m"])
        ring_pos = w_center0[None, :] + (ref_pos - ref_pos[0:1])
        nf = len(ring_pos)
        ring_quats = np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (nf, 1))
        ring_sc = np.ones((nf, 3), dtype=np.float64)

        tube_r = 0.0045
        rx = max(float(w_half[0]) - tube_r, 0.008)
        rz = max(float(w_half[2]) - tube_r, 0.014)
        sp = build_carabiner_ring(rx, rz, tube_r=tube_r)
        pid = packer.add(sp.verts, sp.tris, sp.smooth)
        upgraded_entries.append({
            "name": "carabiner_main",
            "role": "CLEANUP",
            "catalog_id": "carabiner_merged",
            "part_id": pid,
            "verts": sp.verts,
            "tris": sp.tris,
            "color": sp.color,
            "mat": sp.mat_preset,
            "smooth": sp.smooth,
            "pos": ring_pos,
            "quats": ring_quats,
            "sc": ring_sc,
        })

    # Gate 2: Full-frame human-machine AABB clearance check for newly added/expanded SHELL parts (e.g. acrylic shroud)
    new_human_penetration_mm = 0.0
    if pilot:
        check_station_clearance(upgraded_entries, human_frames, human_faces)
    elif human_frames is not None:
        h_mn_all = human_frames.min(axis=(0, 1))
        h_mx_all = human_frames.max(axis=(0, 1))
        for e in upgraded_entries:
            if e["name"].endswith("_acrylic") or e["name"].endswith("_shroud_caps"):
                m0 = compose_matrix(e["pos"][0], e["quats"][0], e["sc"][0])
                wv = e["verts"] @ m0[:3, :3].T + m0[:3, 3]
                emn, emx = wv.min(axis=0), wv.max(axis=0)
                overlap = np.minimum(emx, h_mx_all) - np.maximum(emn, h_mn_all)
                if np.all(overlap > 0):
                    pen_mm = float(np.min(overlap)) * 1000.0
                    new_human_penetration_mm = max(new_human_penetration_mm, pen_mm)
        assert new_human_penetration_mm <= 2.0, (
            f"[{ex_id}] Acrylic/shroud overlaps human AABB by {new_human_penetration_mm:.1f} mm!"
        )

    blob, total_tris, groups = pack_clip(ex_id, acts, upgraded_entries)
    orig_tris = sum(len(o["tris"]) // 3 for o in objs)
    stats = {
        "id": ex_id,
        "orig_objs": len(objs),
        "new_objs": len(upgraded_entries),
        "merged_draw_calls": groups,
        "orig_tris": orig_tris,
        "new_tris": total_tris,
        "fake_anim_stripped": fake_anim_stripped,
        "carabiner_merged_from": carabiner_merged_count,
        "max_grip_diff_mm": round(max_grip_diff_mm, 4),
        "max_surface_diff_mm": round(max_surface_diff_mm, 4),
        "new_human_pen_mm": round(new_human_penetration_mm, 4),
        "blocked_body_fit": sorted(set(blocked)) if pilot else [],
    }
    if audit is not None:
        audit.extend(upgraded_entries)
    return blob, stats


def pack_clip(ex_id, acts, upgraded_entries):
    # Pack WGM2 binary clip
    buf = bytearray(struct.pack("<4sHH", b"WGM2", len(acts), len(upgraded_entries)))
    buf += np.asarray(acts, dtype="<f4").tobytes()

    total_tris = 0
    static_groups = set()
    anim_groups = set()
    for e in upgraded_entries:
        total_tris += len(e["tris"]) // 3
        pos, quats, sc = e["pos"], e["quats"], e["sc"]
        nf = len(pos)
        r, g, b = [min(255, max(0, round(c * 255))) for c in e["color"]]
        if nf == 1:
            static_groups.add((e["mat"], r, g, b, e["smooth"]))
        else:
            anim_groups.add((e["part_id"], e["mat"], r, g, b))

        const_scale = (nf == 1) or (np.max(np.abs(sc - sc[0])) < 1e-4)
        const_rot = (nf == 1) or (np.max(np.abs(quats - quats[0])) < 1e-4)
        flags = (1 if const_scale else 0) | (2 if const_rot else 0)

        buf += struct.pack("<H3BBBxH", e["part_id"], r, g, b, e["mat"], flags, nf)
        buf += struct.pack("<10f", *pos[0].tolist(), *quats[0].tolist(), *sc[0].tolist())
        if nf > 1:
            dp_raw = np.diff(np.rint((pos-pos[0]) * 10000.0), axis=0)
            assert np.max(np.abs(dp_raw)) <= 32767, f"[{ex_id}] {e['name']} pos delta overflow!"
            buf += dp_raw.astype("<i2").tobytes()
            if not const_rot:
                dq_raw = np.diff(np.rint((quats-quats[0]) * 32767.0), axis=0)
                assert np.max(np.abs(dq_raw)) <= 32767, f"[{ex_id}] quaternion delta overflow"
                buf += dq_raw.astype("<i2").tobytes()
            if not const_scale:
                ds_raw = np.diff(np.rint((sc-sc[0]) * 10000.0), axis=0)
                assert np.max(np.abs(ds_raw)) <= 32767, f"[{ex_id}] {e['name']} scale delta overflow!"
                buf += ds_raw.astype("<i2").tobytes()

    return bytes(buf), total_tris, len(static_groups) + len(anim_groups)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--viewer-dir", type=Path, default=REPO / "phone/src/main/assets/viewer3d")
    parser.add_argument("--stage1", action="store_true", help="Build precisely the seven verified lat variants")
    parser.add_argument("--plates", action="store_true", help="Append role-mapped plate overlays to --stage1")
    parser.add_argument("--prefix", help="Upgrade all JSON models whose stem starts with this prefix")
    parser.add_argument("--ids", help="Comma-separated model stems to upgrade")
    parser.add_argument("--all", action="store_true", help="Upgrade all JSON models in data/")
    args = parser.parse_args()

    data_dir = args.viewer_dir / "data"
    human_dir = args.viewer_dir / "human_v5"

    if args.stage1:
        files = [data_dir / f"{w}.json" for w in STAGE1]
        assert all(f.is_file() for f in files), "Incomplete Stage 1 source bundle"
    elif args.ids:
        wanted = [x.strip() for x in args.ids.split(",") if x.strip()]
        files = [data_dir / f"{w}.json" for w in wanted]
    elif args.prefix:
        files = sorted(data_dir.glob(f"{args.prefix}*.json"))
    elif args.all:
        files = sorted(data_dir.glob("*.json"))
    else:
        parser.error("Specify --prefix, --ids, or --all")

    files = [f for f in files if f.exists() and f.name != "wgm_manifest.json"]
    assert files, "No matching machine JSON files found."

    packer = PartCatalogPacker()
    clip_blobs: dict[str, bytes] = {}
    rows = []
    orig_raw_sum = 0
    orig_zip_sum = 0
    new_raw_sum = 0
    new_zip_sum = 0

    base = json.loads((human_dir / "base.json").read_text()) if any(f.stem in STAGE1 for f in files) else None
    faces = np.asarray(base['triangles']).reshape(-1,3) if base else None
    for f in files:
        raw_bytes = f.read_bytes()
        orig_raw_sum += len(raw_bytes)
        orig_zip_sum += len(zlib.compress(raw_bytes, level=6))

        raw_data = json.loads(raw_bytes)
        human_frames = load_wgp2_human_frames(human_dir / f"{f.stem}.bin")
        wgm_bytes, st = upgrade_machine(f.stem, raw_data, packer, human_frames, faces, human_base=base)
        if st['blocked_body_fit']:
            raise ValueError(f"{f.stem}: body clearance not proved for {st['blocked_body_fit']}; not writing catalogue")
        clip_blobs[f.stem] = wgm_bytes

        w_zip = len(zlib.compress(wgm_bytes, level=6))
        new_raw_sum += len(wgm_bytes)
        new_zip_sum += w_zip
        st["orig_kb"] = round(len(raw_bytes) / 1024, 1)
        st["orig_zip_kb"] = round(len(zlib.compress(raw_bytes, level=6)) / 1024, 1)
        st["wgm_kb"] = round(len(wgm_bytes) / 1024, 1)
        st["wgm_zip_kb"] = round(w_zip / 1024, 1)
        rows.append(st)

    overlays = {}
    if args.plates:
        if not args.stage1:
            parser.error("--plates requires --stage1 to preserve the existing catalogue")
        from scene_plates import build_overlays
        overlays, overlay_blobs = build_overlays(data_dir, packer, pack_clip)
        assert not clip_blobs.keys() & overlay_blobs.keys()
        clip_blobs.update(overlay_blobs)
    parts_bytes = packer.build_bytes()
    parts_zip = len(zlib.compress(parts_bytes, level=6))

    # Write outputs
    (data_dir / "parts.bin").write_bytes(parts_bytes)
    if any(k in STAGE1 for k in clip_blobs):
        (data_dir / 'lat_stack_labels.svg').write_text(atlas()[0], encoding='ascii')
    for stem, blob in clip_blobs.items():
        (data_dir / f"{stem}.wgm").write_bytes(blob)

    manifest = {
        "version": 2,
        "parts": "parts.bin",
        "clips": sorted(clip_blobs.keys()),
    }
    if overlays:
        manifest['plateOverlays'] = overlays
    (data_dir / "wgm_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    )

    if overlays:
        texture_size = (data_dir/'plate_faces.webp').stat().st_size
        print(f"Built {len(clip_blobs)} clips, {packer.count} shared parts ({len(parts_bytes)} B), "
              f"plate overlays {sum(map(len, overlay_blobs.values()))} B, shared atlas {texture_size} B; originals retained.")
        return
    total_new_raw = len(parts_bytes) + new_raw_sum
    total_new_zip = parts_zip + new_zip_sum

    print(f"Upgraded {len(rows)} clips -> {packer.count} unique shared parts in parts.bin")
    print(f"  parts.bin : {len(parts_bytes)/1024:.1f} KB raw / {parts_zip/1024:.1f} KB zip")
    print(f"  clips sum : {new_raw_sum/1024:.1f} KB raw / {new_zip_sum/1024:.1f} KB zip")
    print(
        f"  TOTAL     : {orig_raw_sum/1024:.1f} KB -> {total_new_raw/1024:.1f} KB raw "
        f"({(total_new_raw/orig_raw_sum - 1)*100:+.1f}%) | "
        f"{orig_zip_sum/1024:.1f} KB -> {total_new_zip/1024:.1f} KB zip "
        f"({(total_new_zip/orig_zip_sum - 1)*100:+.1f}%)"
    )
    print("\nPer-clip verification:")
    for r in rows:
        print(
            f"  {r['id']:28s} objs={r['orig_objs']:2d}->{r['new_objs']:2d} (dc={r['merged_draw_calls']:2d}) "
            f"tris={r['orig_tris']:4d}->{r['new_tris']:4d} "
            f"size={r['orig_kb']:5.1f}->{r['wgm_kb']:4.1f}KB (zip {r['orig_zip_kb']:4.1f}->{r['wgm_zip_kb']:3.1f}KB) "
            f"grip={r['max_grip_diff_mm']:.2f}mm surf={r['max_surface_diff_mm']:.2f}mm pen={r['new_human_pen_mm']:.2f}mm"
        )


if __name__ == "__main__":
    main()
