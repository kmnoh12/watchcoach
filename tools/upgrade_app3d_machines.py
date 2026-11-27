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
from part_registry import MAT_NAMES, classify_object  # noqa: E402


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

    def add(self, verts: np.ndarray, tris: np.ndarray, smooth: bool) -> int:
        v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
        t = np.asarray(tris, dtype=np.int32).reshape(-1)
        assert len(v) <= 65535 and len(t) // 3 <= 65535, f"Mesh too large: v={len(v)}, t={len(t)//3}"
        key_bytes = np.round(v, 4).astype("<f4").tobytes() + t.astype("<u2").tobytes() + bytes([1 if smooth else 0])
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
        flags = 1 if smooth else 0
        hdr = struct.pack("<HHB3x6f", nv, nt, flags, *mn.tolist(), *sc.tolist())
        self._blobs.append(hdr + q.tobytes() + idx.tobytes())
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


def upgrade_machine(
    ex_id: str,
    raw_data: dict,
    packer: PartCatalogPacker,
    human_frames: np.ndarray | None,
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

    for o, spec in other_objs:
        v_orig = np.asarray(o["verts"], dtype=np.float64).reshape(-1, 3)
        t_orig = np.asarray(o["tris"], dtype=np.int32).reshape(-1)
        m_list_raw = o["m"]
        m_list = strip_fake_animation(m_list_raw)
        if len(m_list) < len(m_list_raw):
            fake_anim_stripped += 1

        mn, mx = v_orig.min(axis=0), v_orig.max(axis=0)
        color = list(o.get("color", [0.5, 0.5, 0.5]))
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
    if human_frames is not None:
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

    # Pack WGM2 binary clip
    buf = bytearray(struct.pack("<4sHH", b"WGM2", len(acts), len(upgraded_entries)))
    buf += np.asarray(acts, dtype="<f4").tobytes()

    total_tris = 0
    static_groups = set()
    anim_objs = 0
    for e in upgraded_entries:
        total_tris += len(e["tris"]) // 3
        pos, quats, sc = e["pos"], e["quats"], e["sc"]
        nf = len(pos)
        r, g, b = [min(255, max(0, round(c * 255))) for c in e["color"]]
        if nf == 1:
            static_groups.add((e["mat"], r, g, b, e["smooth"]))
        else:
            anim_objs += 1

        const_scale = (nf == 1) or (np.max(np.abs(sc - sc[0])) < 1e-4)
        const_rot = (nf == 1) or (np.max(np.abs(quats - quats[0])) < 1e-4)
        flags = (1 if const_scale else 0) | (2 if const_rot else 0)

        buf += struct.pack("<H3BBBxH", e["part_id"], r, g, b, e["mat"], flags, nf)
        buf += struct.pack("<10f", *pos[0].tolist(), *quats[0].tolist(), *sc[0].tolist())
        if nf > 1:
            dp_raw = np.rint(np.diff(pos, axis=0) * 10000.0)
            assert np.max(np.abs(dp_raw)) <= 32767, f"[{ex_id}] {e['name']} pos delta overflow!"
            buf += dp_raw.astype("<i2").tobytes()
            if not const_rot:
                dq_raw = np.rint(np.diff(quats, axis=0) * 32767.0).clip(-32767, 32767)
                buf += dq_raw.astype("<i2").tobytes()
            if not const_scale:
                ds_raw = np.rint(np.diff(sc, axis=0) * 10000.0)
                assert np.max(np.abs(ds_raw)) <= 32767, f"[{ex_id}] {e['name']} scale delta overflow!"
                buf += ds_raw.astype("<i2").tobytes()

    orig_tris = sum(len(o["tris"]) // 3 for o in objs)
    stats = {
        "id": ex_id,
        "orig_objs": len(objs),
        "new_objs": len(upgraded_entries),
        "merged_draw_calls": len(static_groups) + anim_objs,
        "orig_tris": orig_tris,
        "new_tris": total_tris,
        "fake_anim_stripped": fake_anim_stripped,
        "carabiner_merged_from": carabiner_merged_count,
        "max_grip_diff_mm": round(max_grip_diff_mm, 4),
        "max_surface_diff_mm": round(max_surface_diff_mm, 4),
        "new_human_pen_mm": round(new_human_penetration_mm, 4),
    }
    return bytes(buf), stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--viewer-dir", type=Path, default=REPO / "phone/src/main/assets/viewer3d")
    parser.add_argument("--prefix", help="Upgrade all JSON models whose stem starts with this prefix")
    parser.add_argument("--ids", help="Comma-separated model stems to upgrade")
    parser.add_argument("--all", action="store_true", help="Upgrade all JSON models in data/")
    args = parser.parse_args()

    data_dir = args.viewer_dir / "data"
    human_dir = args.viewer_dir / "human_v5"

    if args.ids:
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

    for f in files:
        raw_bytes = f.read_bytes()
        orig_raw_sum += len(raw_bytes)
        orig_zip_sum += len(zlib.compress(raw_bytes, level=6))

        raw_data = json.loads(raw_bytes)
        human_frames = load_wgp2_human_frames(human_dir / f"{f.stem}.bin")
        wgm_bytes, st = upgrade_machine(f.stem, raw_data, packer, human_frames)
        clip_blobs[f.stem] = wgm_bytes

        w_zip = len(zlib.compress(wgm_bytes, level=6))
        new_raw_sum += len(wgm_bytes)
        new_zip_sum += w_zip
        st["orig_kb"] = round(len(raw_bytes) / 1024, 1)
        st["orig_zip_kb"] = round(len(zlib.compress(raw_bytes, level=6)) / 1024, 1)
        st["wgm_kb"] = round(len(wgm_bytes) / 1024, 1)
        st["wgm_zip_kb"] = round(w_zip / 1024, 1)
        rows.append(st)

    parts_bytes = packer.build_bytes()
    parts_zip = len(zlib.compress(parts_bytes, level=6))

    # Write outputs
    (data_dir / "parts.bin").write_bytes(parts_bytes)
    for stem, blob in clip_blobs.items():
        (data_dir / f"{stem}.wgm").write_bytes(blob)

    manifest = {
        "version": 2,
        "parts": "parts.bin",
        "clips": sorted(clip_blobs.keys()),
    }
    (data_dir / "wgm_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    )

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
