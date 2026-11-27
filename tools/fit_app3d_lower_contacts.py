"""Fit reviewed leg contacts on the completed new-hand viewer geometry."""
import argparse
import json
import struct
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation, Slerp

from build_v5_hand_viewer_copy import rigid
from build_app3d_v5 import pack_motion
from check_app3d_stage1 import read_clip, read_parts
from upgrade_app3d_machines import PartCatalogPacker, decompose_frames, load_wgp2_human_frames
from upgrade_app3d_adjust_bench import catalog_records
from part_catalog import make_chamfered_box
from fit_app3d_dumbbell_contacts import swing_segment

KEYS = ("lying_leg_curl", "seated_leg_curl", "standing_leg_curl",
        "decline_sit_up", "leg_press_calf", "lat_pulldown~g=d", "decline_push_up", "seated_calf")


def mats(obj):
    return np.asarray(obj["m"]).reshape(-1, 4, 4)


def world(obj):
    m = mats(obj)
    return np.reshape(obj["verts"], (-1, 3)) @ m[:, :3, :3] + m[:, None, 3, :3]


def save_mats(obj, m):
    obj["m"] = m.reshape(-1, 16).tolist()


def move(obj, delta):
    m = mats(obj)
    m[:, 3, :3] += delta
    save_mats(obj, m)


def spin_x(points, centre, angle):
    rotation = Rotation.from_rotvec([angle, 0, 0]).as_matrix()
    return np.einsum("ij,vj->vi", rotation, points - centre) + centre


def faces_for(base, names):
    joint = np.array(base["joints"])
    dominant = np.asarray(base["bone_names"])[joint[np.arange(len(joint)), np.argmax(base["weights"], axis=1)]]
    faces = np.reshape(base["triangles"], (-1, 3))
    return faces[np.isin(dominant, names)[faces].any(axis=1)]


def profile(v):
    section = np.unique(np.round(v[:, 1:], 9), axis=0)
    return section[ConvexHull(section).vertices]


def normals(edges):
    axes = edges[..., ::-1] * [-1, 1]
    return axes / np.maximum(np.linalg.norm(axes, axis=-1, keepdims=True), 1e-15)


def section_gap(poly, triangles):
    """Signed separating-axis gap between a transverse extrusion and projected skin."""
    axis = normals(np.roll(poly, -1, axis=0) - poly)
    trange = np.einsum("tvi,ai->tva", triangles, axis)
    prange = np.einsum("vi,ai->va", poly, axis)
    gap = np.maximum(trange.min(1) - prange.max(0), prange.min(0) - trange.max(1)).max(1)
    other = normals(np.roll(triangles, -1, axis=1) - triangles)
    trange = np.einsum("tvc,tac->tva", triangles, other)
    prange = np.einsum("vc,tac->tva", poly, other)
    gaps = np.maximum(trange.min(1) - prange.max(1), prange.min(1) - trange.max(1))
    # Projected triangle edges parallel to the axle have no separating axis.
    gaps[np.linalg.norm(other, axis=2) < .9] = -np.inf
    return np.maximum(gap, gaps.max(1)).min()


def leg_triangles(base, bones, side=None):
    return faces_for(base, [b + "_" + s for b in bones for s in (side or "lr")])


# Rest joint centres on the shipped V5/new-hand skeleton, in metres.
REST = {"thigh": [.10, -.06, .95], "calf": [.21, -.04, .49], "foot": [.260001, -.04, .10]}


def weights(base, names):
    names = [base["bone_names"].index(n) for n in names]
    return (np.asarray(base["weights"]) * np.isin(base["joints"], names)).sum(1)


def joint(base, skin, name, side):
    w = weights(base, [name + "_" + side])
    mask = w >= min(.99, w.max() - .05)
    r, t = rigid(np.reshape(base["rest"], (-1,3))[mask], skin[:, mask])
    centre = np.array(REST[name]) * [1 if side == "l" else -1, 1, 1]
    return np.einsum("i,fij->fj", centre, r) + t


def rotate_leg(frame, centre, angle, w):
    return frame + (spin_x(frame, centre, angle) - frame) * w[:, None]


def nearest_root(fun, limit):
    v = fun(0.)
    if abs(v) < 1e-7:
        return 0.
    for amount in np.linspace(limit/12, limit, 12):
        for angle in (amount, -amount):
            if v * fun(angle) <= 0:
                return brentq(fun, min(0., angle), max(0., angle), xtol=1e-8)
    raise ValueError("Contact target exceeds the permitted joint arc")


def roller_at(obj, acts, times):
    p, q, sc = decompose_frames(obj["m"])
    assert np.allclose(sc, sc[0], atol=3e-5)
    rot = Slerp(acts, Rotation.from_quat(q))(times)
    verts = np.reshape(obj["verts"], (-1, 3)) * sc[0]
    pos = np.column_stack([np.interp(times, acts, c) for c in p.T])
    return verts @ rot.as_matrix().transpose(0, 2, 1) + pos[:, None]


def fit_leg_curl(key, objs, skin, frames, acts, base):
    # One fixed lever-to-cam index, the complete original stroke and rail setting.
    # Side-to-side ankle differences are taken up by small changes in knee flexion.
    clock = {"lying_leg_curl": 4., "seated_leg_curl": 7., "standing_leg_curl": 0.}[key]
    if clock:
        pivot = mats(objs["knee_axle"])[0, 3, :3]
        rot = Rotation.from_euler("x", clock, degrees=True).as_matrix()
        for n in ("ankle_roller", "roller_axle", "roller_adjust_rail", "lever", "adjust_pin"):
            m = mats(objs[n])
            m[:, 3, :3] = (m[:, 3, :3] - pivot) @ rot.T + pivot
            m[:, :3, :3] = m[:, :3, :3] @ rot.T
            save_mats(objs[n], m)
    rollers = roller_at(objs["ankle_roller"], acts, frames)
    info = {"fixed_lever_index_degrees": clock}
    for side in ("l" if key == "standing_leg_curl" else "lr"):
        bones = ["calf", "foot", "ball"]
        faces = leg_triangles(base, bones, side)
        weight = weights(base, [b + "_" + side for b in bones])
        centres = joint(base, skin, "calf", side)
        angles = []
        for i, (frame, mid, roller) in enumerate(zip(skin, centres, rollers)):
            p = profile(roller)
            sel = faces[np.linalg.norm(frame[faces, 1:].mean(1) - p.mean(0), axis=1) < .30]
            def clearance(ang):
                return section_gap(p, rotate_leg(frame, mid, ang, weight)[sel, 1:]) - .0008
            angle = nearest_root(clearance, .28)
            skin[i] = rotate_leg(frame, mid, angle, weight)
            angles.append(np.rad2deg(angle))
        info["knee_delta_deg_" + side] = [round(float(min(angles)), 3), round(float(max(angles)), 3)]
    return info


def fixed_clearance(v, skin, faces, direction):
    tri = skin[:, faces].reshape(-1, 3, 3)
    lo, hi = v.min(0), v.max(0)
    tri = tri[(tri[:, :, 0].min(1) < hi[0]) & (tri[:, :, 0].max(1) > lo[0])]
    tri = tri[np.linalg.norm(tri.mean(1)[:, 1:] - v.mean(0)[1:], axis=1) < .36, :, 1:]
    p = profile(v)
    return brentq(lambda x: section_gap(p + x * direction[1:], tri) - .0005, 0, .23)


def extend_to(obj, delta, root_extension=0.):
    """Aim the arm from its original fixed socket to the relocated transverse axle."""
    m = mats(obj)
    length = np.ptp(np.reshape(obj["verts"], (-1, 3))[:, 0])
    old = m[0, 0, :3] * length
    new = old + delta
    r, _ = Rotation.align_vectors(new[None], old[None])
    m[0, :3, :3] = m[0, :3, :3] @ r.as_matrix().T
    new_length = np.linalg.norm(new)
    m[0, 0, :3] *= (new_length + root_extension) / np.linalg.norm(old)
    m[0, 3, :3] += .5 * (delta - root_extension * (new / new_length))
    save_mats(obj, m)


def wgm_offsets(blob):
    nf, count = struct.unpack_from("<HH", blob, 4)
    off = 8 + 4 * nf
    result = []
    for _ in range(count):
        result.append(off)
        flags, n = struct.unpack_from("<BxH", blob, off + 6)
        off += 50 + (n - 1) * (6 + (0 if flags & 2 else 8) + (0 if flags & 1 else 6))
    if off != len(blob):
        raise ValueError("Invalid WGM record length")
    return result


def translate_record(blob, offsets, slot, delta):
    off = offsets[slot] + 10
    p = np.frombuffer(blob, "<f4", 3, off)
    p[:] += delta


def tread_contact(foot, faces, top):
    """Lowest sole clearance and contact station on a piecewise linear tread."""
    tri = foot[faces, 1:]
    (y, z), (ey, ez) = tri.T, np.roll(tri, -1, axis=1).T
    on = (y >= top[0, 0]) & (y <= top[-1, 0])
    stations = [y[on]]
    gaps = [z[on] - np.interp(y[on], *top.T)]
    for station, height in top:
        cross = (y < station) != (ey < station)
        if cross.any():
            gap = z[cross] + (ez[cross]-z[cross])*(station-y[cross])/(ey[cross]-y[cross]) - height
            stations.append([station]); gaps.append([gap.min()])
    distances = np.concatenate(gaps)
    i = distances.argmin()
    return np.concatenate(stations)[i], distances[i]


def foot_roll_path(reference, faces, ball, tread, sign):
    # Roll about each successive sole contact rather than sliding a fixed toe
    # along the platform. At the neutral setting the forefoot rests on its rear lip.
    section = profile(tread)
    ys = np.unique(np.round(section[:, 0], 8))
    top = np.array([(y, section[np.isclose(section[:, 0], y, atol=1e-8, rtol=0), 1].max()) for y in ys])
    offsets = {}
    for direction, stop in ((-1, -51), (1, 26)):
        origin = ball + [sign*.035, .131, 0.]
        for angle in range(-10, stop, direction):
            if angle != -10:
                origin = spin_x(origin[None], pivot, np.deg2rad(direction))[0]
            foot = spin_x(reference, ball, np.deg2rad(angle)) + origin - ball
            y, gap = tread_contact(foot, faces, top)
            origin[2] += .0007 - gap
            pivot = np.array([0., y, np.interp(y, *top.T) + .0007])
            offsets[angle] = origin - ball
    grid = sorted(offsets)
    return PchipInterpolator(grid, [offsets[a] for a in grid], extrapolate=False)


def park_calf_catch(objs, rows, blob):
    # The rep is under load, not racked. Swing the cradle AND its operating
    # handle as one piece about the fixed post, clear of the rising heel.
    pivot = mats(objs['rest_post'])[0, 3, :3]
    turn = Rotation.from_euler('z', -90, degrees=True)
    handle = world(objs['rest_handle'])[0]
    bounds = [handle.min(0), handle.max(0)]
    offsets = wgm_offsets(blob)
    for slot in (21, 22):
        row = rows[slot]
        v = row['world'][0]
        if row['nf'] != 1 or not np.allclose([v.min(0), v.max(0)], bounds, atol=.001):
            raise ValueError('Expected both static seated calf catch handle overlays')
        off = offsets[slot] + 10
        pose = np.frombuffer(blob, '<f4', 7, off)
        pose[:3] = turn.apply(row['pos'][0] - pivot) + pivot
        pose[3:] = (turn * Rotation.from_quat(row['quat'][0])).as_quat()
    for name in ('rest_handle', 'rest_cradle'):
        m = mats(objs[name])
        m[:, 3, :3] = turn.apply(m[:, 3, :3] - pivot) + pivot
        m[:, :3, :3] = np.einsum('fij,kj->fik', m[:, :3, :3], turn.as_matrix())
        save_mats(objs[name], m)


def fit_seated_calf(objs, skin, frames, acts, base, rows, blob):
    # Engage the next existing hole. The twin knee pads, their arms, the
    # insert, and its markings share one rigid adjustment in lever space.
    holes = ('adjust_hole', 'adjust_hole.001', 'adjust_hole.002')
    delta = mats(objs[holes[1]])[:, 3, :3] - mats(objs[holes[0]])[:, 3, :3]
    if not np.allclose(delta, .05*mats(objs['knee_insert'])[:, 2, :3], atol=1e-5):
        raise ValueError('Unexpected calf lever insert pitch')
    for n in ('knee_insert', 'knee_cross', 'pad_carrier', 'pad_carrier.001', 'knee', 'knee.001', *holes):
        move(objs[n], delta)
    # Seat each backing rail in the pad (the stock faces stop 0.8 mm apart).
    # Both rails remain engaged in the same crossbar; neither pad is moved alone.
    for n in ('pad_carrier', 'pad_carrier.001'):
        move(objs[n], -.002*mats(objs['knee_insert'])[:, 2, :3])
    park_calf_catch(objs, rows, blob)
    tread = rows[30]['world'][0]
    if rows[30]['nf'] != 1 or not np.allclose(tread.max(0), world(objs['tread'])[0].max(0), atol=.001):
        raise ValueError('Unexpected seated calf tread overlay')
    source = skin.copy()
    ref = source[0]
    rest = np.reshape(base['rest'], (-1, 3))
    # Keep the seated pelvis and the part of the thigh resting on the saddle.
    u = np.clip((.16-ref[:, 1])/.09, 0, 1)
    fade = (u*u*(3-2*u))[:, None]
    for side, pad_name, sign in [('l', 'knee.001', 1), ('r', 'knee', -1)]:
        def centre(bone, position):
            w = weights(base, [bone+'_'+side])
            mask = w >= min(.75, w.max() - .05)
            rot, pos = rigid(rest[mask], ref[None, mask])
            return np.einsum('i,ij->j', np.array(position)*[sign, 1, 1], rot[0]) + pos[0]

        hip, knee, ankle, ball = (centre(b, p) for b, p in (
            ('thigh', REST['thigh']), ('calf', REST['calf']), ('calf', REST['foot']), ('ball', [.29, -.14, .04])))
        thigh, shin, sole = [weights(base, [b+'_'+side for b in bones])[:, None] * fade
                             for bones in (['thigh'], ['calf'], ['foot', 'ball'])]
        feet = leg_triangles(base, ['foot', 'ball'], side)
        path = foot_roll_path(ref, feet, ball, tread, sign)
        legs = leg_triangles(base, ['thigh', 'calf'], side)
        upper, lower = knee-hip, ankle-knee
        for i, pad in enumerate(roller_at(objs[pad_name], acts, frames)):
            section = profile(pad)

            def pose(angle):
                rad = np.deg2rad(angle)
                foot = spin_x(ref, ball, rad) + path(angle)
                dest = spin_x(ankle[None], ball, rad)[0] + path(angle)
                # Solve the upright knee bend with the original rigid link lengths.
                d = np.linalg.norm(dest-hip)
                axis = (dest-hip)/d
                along = (d*d + upper.dot(upper) - lower.dot(lower))/(2*d)
                pole = np.array([0., 0., 1.]) - axis*axis[2]
                k = hip + axis*along + pole/np.linalg.norm(pole)*np.sqrt(upper.dot(upper) - along*along)
                def swung(points, old_link, new_link):
                    rot = swing_segment(old_link[None], new_link[None])[0]
                    return np.einsum('ij,vj->vi', rot, points)
                old = source[i]
                return ((swung(ref-hip, upper, k-hip) + hip-old)*thigh
                        + (swung(ref-knee, lower, dest-k) + k-old)*shin + (foot-old)*sole)

            def clearance(angle):
                tri = (source[i] + pose(angle))[legs]
                tri = tri[(tri[:, :, 0].min(1) < pad[:, 0].max()) & (tri[:, :, 0].max(1) > pad[:, 0].min())]
                return section_gap(section, tri[:, :, 1:]) - .0013

            skin[i] += pose(brentq(clearance, -50., 25.))
    return {'insert_holes_raised': 1, 'parked_catch_degrees': -90, 'knee_pad_clearance_mm': 1.3}


def sled_cross_profile(vertices, scale):
    # Preserve the existing crossmember on each rail sleeve. A welded dogleg
    # puts the centre span behind the heels without moving the sled or plate.
    cross = profile(vertices)
    stations = [(-.540, 0.), (-.325, 0.), (-.257, -.125),
                (.257, -.125), (.325, 0.), (.540, 0.)]
    v = np.concatenate([
        np.column_stack((np.full(len(cross), x / scale[0]),
                         cross + [y / scale[1], 0.])) for x, y in stations
    ])
    n = len(cross)
    triangles = [(0, i + 1, i) for i in range(1, n - 1)]
    for index in range(len(stations) - 1):
        lo, hi = index * n, (index + 1) * n
        for i in range(n):
            j = (i + 1) % n
            triangles.extend(((lo+i, lo+j, hi+j), (lo+i, hi+j, hi+i)))
    end = (len(stations) - 1) * n
    triangles.extend((end, end + i, end + i + 1) for i in range(1, n - 1))
    return v, triangles


def fit_sled_cross(obj, rows, blob, parts, stock):
    slot = 50
    row = rows[slot]
    v, faces = parts[row["pid"]]
    original = world(obj)
    if (not np.allclose(row["pos"], original.mean(1), atol=.001)
            or not np.allclose(row["scale"], row["scale"][0])
            or not np.allclose(row["quat"], [0, 0, 0, 1])):
        raise ValueError("Unexpected leg-press crossmember record or track")
    verts, triangles = sled_cross_profile(v, row["scale"][0])
    count = struct.unpack_from("<I", stock, 4)[0]
    smooth = bool(list(catalog_records(stock))[row["pid"]][4] & 1)
    packer = PartCatalogPacker()
    packer.add(verts, triangles, smooth)
    struct.pack_into("<H", blob, wgm_offsets(blob)[slot], count)
    obj["verts"] = (verts * row["scale"][0] / .9).ravel().tolist()
    obj["tris"] = np.ravel(triangles).tolist()
    return struct.pack("<4sI", b"WGC2", count + 1) + stock[8:] + packer.build_bytes()[8:]


def set_push_up_toes(skin, base):
    # Pivot the forefoot at the ball of the foot while the ankle and calf keep
    # their original track. Both toes stay on the plate as the torso lowers.
    for side in "lr":
        w = weights(base, ["ball_" + side])
        toes = w > .5
        sign = 1 if side == "l" else -1
        mask = w > .65
        rotation, location = rigid(np.reshape(base["rest"], (-1, 3))[mask], skin[:, mask])
        centres = np.einsum("i,fij->fj", [.29 * sign, -.14, .04], rotation) + location
        for index, centre in enumerate(centres):
            frame = skin[index].copy()
            def face_height(angle):
                shaped = rotate_leg(frame, centre, angle, w)
                return shaped[toes, 2].min() - .4505
            angle = nearest_root(face_height, 1.05)
            skin[index] = rotate_leg(frame, centre, angle, w)
    return {"toe_support_plane_mm": 450.5}


def clear_lat_foot(skin, base, rail):
    # Widen the right foot's floor placement while preserving floor height and
    # tapering its translation to zero as the lower leg approaches the knee.
    w = weights(base, ["foot_r", "ball_r"])
    edge = rail[:, 0].max() + .002
    shifts = []
    for frame in skin:
        low = (w > .02) & (frame[:, 2] < rail[:, 2].max() + .002)
        shift = max(0., float(np.max((edge - frame[low, 0]) / w[low])))
        shifts.append(shift)
        frame[:, 0] += w * shift
    return {"rail_lateral_clearance_mm": 2, "right_foot_shift_mm": 1000 * max(shifts)}


def set_decline_rollers(objs, skin, base, rows, blob):
    faces = leg_triangles(base, ["thigh", "calf", "foot", "ball"])
    offsets = wgm_offsets(blob)
    result = {}
    for names, axle, arm, caps, direction in [
        (("roller", "roller.001"), "roller_axle", "knee_arm", ("end_cap", "end_cap.001"), [0., -.34202, -.93969]),
        (("roller.002", "roller.003"), "roller_axle.001", "ankle_arm", ("end_cap.002", "end_cap.003"), [0., -.64279, .76604]),
    ]:
        direction = np.array(direction)
        dist = max(fixed_clearance(world(objs[n])[0], skin, faces, direction) for n in names)
        delta = dist * direction
        for cap in caps:
            centre = world(objs[cap])[0].mean(0)
            matches = [i for i, r in enumerate(rows) if np.linalg.norm(r["world"][0].mean(0)-centre)<.001]
            if len(matches) != 1:
                raise ValueError("Expected one co-axial cap")
            translate_record(blob, offsets, matches[0], delta)
        for n in (*names, axle, *caps):
            move(objs[n], delta)
        extend_to(objs[arm], delta, root_extension=.025 if arm == "ankle_arm" else 0.)
        result[axle] = delta.round(6).tolist()
    return result


def store_skin(path, skin, times):
    # Preserve the original codec grid and every unaffected quantized coordinate.
    original = path.read_bytes()
    lo, step = np.frombuffer(original, "<f4", 6, 16).reshape(2, 3)
    start = 40 + 4 * len(times)
    quantized = np.rint((skin - lo) / step)
    if quantized.min() >= 0 and quantized.max() <= 65535:
        values = quantized.astype("uint16")
        delta = np.diff(values, axis=0, prepend=np.zeros_like(values[:1])).astype("<u2")
        path.write_bytes(original[:start] + delta.tobytes())
    else:
        blob, _ = pack_motion({"acts": times, "frames": skin}, skin.shape[1])
        path.write_bytes(blob)


def attach_standing_pad(raw, objs):
    pad = objs["thigh_support"]
    m = mats(pad)[0]
    end = m[3, :3] - .038 * m[1, :3]
    start = np.array([0., -.33, end[2] - .045])
    axis = end - start
    length = np.linalg.norm(axis)
    verts, tris = make_chamfered_box(np.array([-.022, -.022, 0.]),
                                     np.array([.022, .022, length]), bevel=.002)
    rot, _ = Rotation.align_vectors((axis / length)[None], [[0., 0., 1.]])
    m = np.eye(4)
    m[:3, :3] = rot.as_matrix().T
    m[3, :3] = start
    raw["objects"].append(dict(name="thigh_pad_standoff", color=objs["front_post"]["color"],
                               verts=verts.ravel().tolist(), tris=tris.ravel().tolist(),
                               m=[m.ravel().tolist()]))


def apply(view, keys=KEYS):
    data, human = view / "data", view / "human_v5"
    base = json.loads((human / "base.json").read_text())
    assert base["vertices"] == 1401 and (human / "watch.json").is_file()
    parts = read_parts(data / "parts.bin")
    stock = (data / "parts.bin").read_bytes()
    catalogue = stock
    results = {}
    for key in keys:
        path = data / (key + ".json")
        raw = json.loads(path.read_text())
        objs = {o["name"]: o for o in raw["objects"]}
        hp = human / (key + ".bin")
        skin = load_wgp2_human_frames(hp)
        ts = np.frombuffer(hp.read_bytes(), "<f4", len(skin), 40)
        wp = data / (key + ".wgm")
        acts, rows = read_clip(wp, parts)
        assert np.array_equal(acts, np.array(raw["acts"], dtype="<f4"))
        blob = bytearray(wp.read_bytes())
        if key in ("lying_leg_curl", "seated_leg_curl"):
            result = fit_leg_curl(key, objs, skin, ts, acts, base)
        elif key == "standing_leg_curl":
            pad = objs["thigh_support"]
            result = fit_leg_curl(key, objs, skin, ts, acts, base)
            move(pad, [.15, 0., 0.])
            direction = np.array([0., -1., 0.])
            offset = fixed_clearance(world(pad)[0], skin, leg_triangles(base, ["thigh", "calf"]), direction)
            move(pad, offset * direction)
            result["pad_forward_m"] = offset
            attach_standing_pad(raw, objs)
        elif key == "decline_sit_up":
            result = set_decline_rollers(objs, skin, base, rows, blob)
        elif key == "leg_press_calf":
            catalogue = fit_sled_cross(objs["sled_cross"], rows, blob, parts, stock)
            result = {"sled_cross_recess_mm": 125}
        elif key == "lat_pulldown~g=d":
            result = clear_lat_foot(skin, base, rows[105]["world"][0])
        elif key == "decline_push_up":
            result = set_push_up_toes(skin, base)
        elif key == "seated_calf":
            result = fit_seated_calf(objs, skin, ts, acts, base, rows, blob)
        else:
            raise ValueError(key)
        if key in ("lying_leg_curl", "seated_leg_curl", "standing_leg_curl", "lat_pulldown~g=d", "decline_push_up", "seated_calf"):
            store_skin(hp, skin, ts)
        if blob != wp.read_bytes():
            wp.write_bytes(blob)
        path.write_text(json.dumps(raw, separators=(",", ":"), allow_nan=False))
        results[key] = result
        print(key, result, flush=True)
    if catalogue != stock:
        (data / "parts.bin").write_bytes(catalogue)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    parser.add_argument("--keys", nargs="+", choices=KEYS, default=KEYS)
    args = parser.parse_args()
    apply(args.view, args.keys)
