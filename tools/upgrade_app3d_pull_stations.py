"""Add the role-mapped pull-station overlays to the final new-hand app viewer."""

import argparse
from collections import Counter
import json
from pathlib import Path
import struct

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import catalog_records, tube
from upgrade_app3d_machines import (
    PartCatalogPacker, decompose_frames, load_wgp2_human_frames, pack_clip, strip_fake_animation,
)
from body_fit import SkinSweep, fit_body_part
from part_registry import (
    MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER, MAT_SELECTOR_WINDOW, MAT_SILVER,
)
from scene_lat_parts import _nine, build_roller, build_seat, build_stickers, palette
from selector_tower import cylinder, drilled_slider

HERE = Path(__file__).resolve().parent / "viewer3d"
PLATE_SIZE = np.array([.34, .28, .075])
PASSAGES = {"weight_guide", "selector_rod", "link_rod", "selector_pin", "fastening_pin"}


def load(path):
    return json.loads(path.read_text())


def load_source():
    return {
        **load(HERE/"scene_cable_source.json"),
        **load(HERE/"scene_cable_mount_source.json"),
        **load(HERE/"scene_pull_source.json"),
    }


def vertices(obj):
    return np.asarray(obj["verts"]).reshape(-1, 3)


def world(obj):
    m = np.asarray(obj["m"]).reshape(-1, 4, 4)
    return vertices(obj) @ m[:, :3, :3] + m[:, None, 3, :3]


def avatar_at_key_times(path, acts):
    frames = load_wgp2_human_frames(path)
    if frames is None or frames.shape[1] != 1401:
        raise ValueError("Missing final new-hand avatar clip")
    times = np.frombuffer(path.read_bytes(), "<f4", len(frames), 40)
    clock = np.union1d(times, np.asarray(acts, "<f4"))
    if len(frames) == 1:
        return clock, np.repeat(frames, len(clock), axis=0)
    i = np.searchsorted(times, clock, side="right").clip(1, len(times)-1)
    weight = ((clock-times[i-1])/(times[i]-times[i-1])).clip(0, 1)[:, None, None]
    return clock, frames[i-1] + weight*(frames[i]-frames[i-1])


def verify_skin(rows, clock, skin, acts, faces):
    static = SkinSweep(skin, faces)
    for row in rows:
        q, sc, pos = row["quats"], row["sc"], row["pos"]
        if not np.allclose(q, q[0], atol=3e-5) or not np.allclose(sc, sc[0], atol=3e-5):
            raise ValueError(f"{row['name']}: tower part has a non-translational track")
        mesh = Rotation.from_quat(q[0]).apply(row["verts"]*sc[0])
        if len(pos) == 1:
            clear = static.clear(mesh + pos[0], margin=.0001)
        else:
            travel = np.column_stack([np.interp(clock, np.asarray(acts, "<f4"), p) for p in pos.T])
            relative = skin - travel[:, None, :]
            clear = not ((relative.max((0, 1)) >= mesh.min(0))
                         & (relative.min((0, 1)) <= mesh.max(0))).all()
            if not clear:
                clear = SkinSweep(relative, faces).clear(mesh, margin=.0001)
        if not clear:
            raise ValueError(f"{row['name']}: swept skin intersects the fitted part envelope")


def projected_clear(mesh, faces, points, axes):
    """Positive-area separation between projected casting faces and a convex shaft."""
    p = points[:, axes]
    hull = p[ConvexHull(p).vertices]
    tris = mesh[:, axes][faces]
    hit = ((tris.min(1) < p.max(0)) & (tris.max(1) > p.min(0))).all(1)
    for tri in tris[hit]:
        edges = np.roll(tri, -1, axis=0) - tri
        if abs(np.linalg.det(edges[:2])) < 1e-13:
            continue
        edges = np.vstack([edges, np.roll(hull, -1, axis=0) - hull])
        normals = edges[:, ::-1] * [-1, 1]
        normals = normals[np.linalg.norm(normals, axis=1) > 1e-12]
        a, b = tri @ normals.T, hull @ normals.T
        if not ((a.max(0) <= b.min(0) + 1e-13) | (b.max(0) <= a.min(0) + 1e-13)).any():
            return False
    return True


def check_passages(cast, faces, pos, obstacles):
    mesh = cast - pos[0]
    lower, upper = mesh.min(0), mesh.max(0)
    for name, geometry, pin in obstacles:
        if not pin:
            if not projected_clear(mesh, faces, geometry[0] - pos[0], [0, 1]):
                raise ValueError(f"{name}: casting blocks the original guide or lift rod")
            continue
        # Inspect only phases where the pin can actually enter this casting.
        relative = geometry - pos[:, None, :]
        mask = ((relative.max(1) > lower + .0001) & (relative.min(1) < upper - .0001)).all(1)
        _, unique = np.unique(relative[mask, 0].round(4), axis=0, return_index=True)
        for points in relative[mask][unique]:
            if not projected_clear(mesh, faces, points, [0, 2]):
                raise ValueError(f"{name}: original pin exceeds the casting socket")


def fitted_layers(raw, mapping, source, human, base, emit):
    """Adjust only panels that have attachment hardware in the original station."""
    objects = {o["name"]: o for o in raw["objects"]}
    fits = {}
    sweep = SkinSweep(human, np.asarray(base["triangles"]).reshape(-1, 3))
    colors = palette()

    def fit(name, role, pieces, normal, across, rail, limit):
        obj = objects[name]
        position = np.asarray(obj["m"][0][12:15])
        matrix = np.asarray(obj["m"][0]).reshape(4, 4)[:3, :3]
        surface = np.vstack([p[0] for p in pieces]) @ matrix + position
        target = fit_body_part(human, base, role, position, surface, normal, across)
        distance = np.dot(target - position, normal) / np.dot(rail, normal)
        shift = rail * distance
        if abs(distance) > limit or not sweep.clear(surface + shift):
            raise ValueError(f"{name}: no 2–5 mm fit within the mounted adjustment range")
        residual = fit_body_part(human, base, role, position + shift, surface + shift, normal, across)
        gap = .0035 - np.dot(residual - position - shift, normal)
        if not .002 <= gap <= .005:
            raise ValueError(f"{name}: clearance on the actual adjustment axis is {gap*1000:.1f} mm")
        for v, t, mat, color, smooth in pieces:
            emit(name, v, t, mat, color, shift=shift, smooth=smooth, contact=True)
        fits[name] = dict(role=role, axis=rail.tolist(), normal=normal.tolist(), across=across.tolist(),
                          origin=position.tolist(), offset=shift.tolist(), gap_mm=gap*1000)
        return shift

    def hardware(name, shape, center, scale, rotation, mat, color):
        emit(name, *shape, mat, color, scale=scale, pose=(center, rotation), contact=True)

    def pieces(subparts):
        return [(p.verts, p.tris, p.mat_preset, p.color, p.smooth) for p in subparts]

    up, x, y = np.eye(3)[[2, 0, 1]]
    eye = np.array([0., 0., 0., 1.])
    gray, steel = colors["casting"], colors["steel"]
    slider_v, slider_t = drilled_slider()
    slider_v[:, 2] += .12
    slider_shape = slider_v, slider_t
    seats = [name for name, (_, group) in mapping.items()
             if group.startswith("seat_pad__") and "seat_sleeve" in objects]
    for name in seats:
        obj = objects[name]
        v = vertices(obj)
        scale = decompose_frames(obj["m"][:1])[2][0]
        cushion = build_seat(v.min(0), v.max(0))
        matrix = np.asarray(obj["m"][0]).reshape(4, 4)[:3, :3] / scale[:, None]
        post = next(n for n in ("seat_telescoping_post", "seat_post", "mopt_seat_stem") if n in objects)
        post_v = world(objects[post])[0]
        rail = up
        shift = fit(
            name, "seat_pad", pieces(cushion), -matrix[2], matrix[0], rail, .055,
        )
        top = post_v[:, 2].max()
        height = np.ptp(post_v[:, 2])
        sleeve_name = "seat_sleeve"
        sleeve = world(objects[sleeve_name])[0]
        lower, upper = sleeve.min(0), sleeve.max(0)
        collar = (lower + upper) / 2
        lock = objects.get("seat_lock", objects.get("seat_pop_pin"))
        collar[2] = lock["m"][0][14]
        lower_height = lower[2] + .015 - post_v[:, 2].min()
        ratio = lower_height / height
        emit(post, vertices(objects[post]), objects[post]["tris"], MAT_FRAME, objects[post]["color"],
             scale=[ratio, 1, 1], shift=rail*(lower_height-height)/2, contact=True)
        dims = (upper-lower)[:2]/.042
        z0, z1 = collar[2]-.018, collar[2]+.018
        hardware(sleeve_name, tube(True), collar, [*dims, 1.8], eye, MAT_FRAME, gray)
        for bottom, tip in ((lower[2], z0), (z1, upper[2])):
            at = collar.copy()
            at[2] = bottom
            hardware(sleeve_name, tube(), at, [*dims, tip-bottom], eye, MAT_FRAME, gray)
        stick_top = top + shift[2]
        stick_bottom = slider_bottom(lower[2]+.010, stick_top, collar[2])
        stick = collar.copy()
        stick[2] = (stick_top+stick_bottom)/2
        hardware(post, slider_shape, stick, [2, 2, (stick_top-stick_bottom)/.24],
                 eye, MAT_CHROME, steel)

    for name, (_, group) in mapping.items():
        if not group.startswith("leg_roller__"):
            continue
        obj = objects[name]
        v = vertices(obj)
        matrix = np.asarray(obj["m"][0]).reshape(4, 4)
        position = matrix[3, :3]
        axle = matrix[2, :3] / np.linalg.norm(matrix[2, :3])
        rad = np.hypot(*v[:, :2].T).max()
        layers = build_roller([-rad, -rad, v[:, 2].min()], [rad, rad, v[:, 2].max()],
                              int(np.sign(position[0]*axle[0])))
        shift = fit(name, "thigh_roller", pieces(layers), up, axle, up, .055)
        suffix = name[len("thigh_roller"):]
        anchor_name = "roller_support" + suffix
        if anchor_name not in objects:
            raise ValueError(f"{name}: the station uses a common axle with its own detent track")
        anchor = np.asarray(objects[anchor_name]["m"][0][12:15])
        anchor[1:] = position[1:]
        head = anchor + shift
        # At the end of each original arm, a hollow index collar captures the perforated slider.
        # A short transverse spindle connects the slider to the end cap of this roller.
        collar = anchor + up*.022
        slider = head + up*.067
        index = round((collar[2]-slider[2])/.013-.5)+.5
        slider[2] = collar[2]-index*.013
        hardware(name, tube(True), collar, [1, 1, 2], eye, MAT_FRAME, gray)
        hardware(name, slider_shape, slider, [1, 1, .65], eye, MAT_CHROME, steel)
        edge = position[0] + np.sign(position[0])*max(abs(v[:, 2]))
        center = head.copy()
        center[0] = (edge + head[0])/2
        hardware(name, cylinder(.013, abs(edge - head[0]) + .008, 0, 20), center, [1]*3, eye, MAT_CHROME, steel)
        pin = collar + x*np.sign(position[0])*.022
        hardware(name, cylinder(.008, .016, 0, 20), pin, [1]*3, eye, MAT_ACCENT, [.98, .61, .016])
        hardware(name, cylinder(.0031, .042, 0, 20), collar, [1]*3, eye, MAT_CHROME, steel)

    if "chest_pad" in mapping:
        name = "chest_pad"
        obj = objects[name]
        v = vertices(obj)
        size = np.ptp(v, axis=0)
        template = source["chest_pad"]
        bounds = np.vstack([p["v"] for p in template])
        half = np.ptp(bounds, axis=0)/2
        layers = []
        for p in template:
            vv = _nine_mesh(p["v"], half, size/2)
            color = colors["pad" if p["slot"] == 0 else "stitch"]
            layers.append((vv, p["t"], MAT_PAD, color, True))
        shift = fit(name, "back_pad", layers, -y, x, y, .180)
        # Anchor the horizontal slide to the original back plate/post. Travel remains
        # on the existing pad normal, and the inserted end stays inside the receiver.
        back = world(objects["pad_back"])[0]
        center = (back.min(0) + back.max(0))/2
        center[2] = obj["m"][0][14]
        direction = Rotation.from_euler("x", -90, degrees=True).as_quat()
        hardware(name, tube(False), center, [1, 1, .042], direction, MAT_FRAME, gray)
        collar = center + y*.052
        hardware(name, tube(True), collar, [1]*3, direction, MAT_FRAME, gray)
        hardware(name, cylinder(.0031, .048, 0, 20), collar, [1]*3, eye, MAT_CHROME, steel)
        hardware(name, cylinder(.009, .014, 0, 20), collar+x*.026,
                 [1]*3, eye, MAT_ACCENT, [.98, .61, .016])
        back_face = world(obj)[0][:, 1].min() + shift[1]
        end = slider_bottom(center[1]+.030, back_face+.004, collar[1])
        inner = center.copy()
        length = back_face+.004-end
        inner[1] = end+length/2
        hardware(name, slider_shape, inner, [1, 1, length/.24], direction, MAT_CHROME, steel)
    return fits


def slider_bottom(bottom, top, bore):
    """Keep the pad end in place and align a real index hole with the collar pin."""
    index = np.clip(round((bore-bottom)/(top-bottom)*12-.5), 0, 11)
    return top - (top-bore)/(1-(index+.5)/12)


def _nine_mesh(vertices, half, target):
    v = np.array(vertices)
    for i in range(3):
        v[:, i] = _nine(v[:, i], half[i], target[i], .030)
    return v


def assemble(key, raw, mapping, source, human, base):
    objects = raw["objects"]
    groups = {}
    for name, (idx, group) in mapping.items():
        if objects[idx]["name"] != name:
            raise ValueError(f"role map index {idx} no longer describes {name}")
        groups[name] = group.rsplit("__", 1)[0]
    colors = palette()
    entries = []

    def emit(name, vv, tt, mat, color, *, scale=(1, 1, 1), shift=(0, 0, 0), pose=None, rotate=None,
             smooth=False, contact=False):
        idx, group = mapping[name]
        obj = objects[idx]
        pos, quat, sc = decompose_frames(strip_fake_animation(obj["m"]))
        if pose is not None:
            pos, quat, sc = np.array([pose[0]]), np.array([pose[1]]), np.ones((1, 3))
        if rotate is not None:
            quat = (Rotation.from_quat(quat)*rotate).as_quat()
        entries.append(dict(index=idx, name=name, group=group, verts=np.asarray(vv),
                            tris=np.asarray(tt).ravel(), mat=mat, color=color, smooth=smooth,
                            pos=pos + shift, quats=quat, sc=sc * scale, contact=contact))

    plates = sorted((n for n, g in groups.items() if g.endswith("stack_plate")),
                    key=lambda n: -objects[mapping[n][0]]["m"][0][14])
    obstacles = [(name, world(objects[mapping[name][0]]), "pin" in role)
                 for name, role in groups.items() if role in PASSAGES]
    for name, (index, _) in mapping.items():
        obj, role = objects[index], groups[name]
        v = vertices(obj)
        center = (v.max(0) + v.min(0))/2
        size = np.ptp(v, axis=0)
        matrix = np.asarray(obj["m"][0]).reshape(4, 4)
        if role.endswith("stack_plate"):
            layer, = source["stack_casting"]
            if not np.allclose(matrix[:3, :3], np.eye(3)*matrix[0, 0], atol=3e-5):
                raise ValueError(f"{name}: plate local up/shaft axes differ")
            emit(name, layer["v"], layer["t"], MAT_FRAME, colors["casting"],
                 scale=size/PLATE_SIZE, shift=center @ matrix[:3, :3])
            row = entries[-1]
            pos = row["pos"]
            try:
                check_passages(row["verts"]*row["sc"][0]+pos[0], row["tris"].reshape(-1, 3), pos, obstacles)
            except ValueError as exc:
                raise ValueError(f"{name}: {exc}") from exc
            kg = 2.5 + 5 * plates.index(name)
            pin = next(o for _, o, is_pin in obstacles if is_pin)
            side = -1 if pin[0, :, 1].mean() <= matrix[3, 1] else 1
            facing = Rotation.from_quat([0, 0, 1, 0]) if side > 0 else None
            # Offset paired labels around the socket; carry them on their own plate's original track.
            for p in build_stickers(*PLATE_SIZE, kg, round(kg * 2.20462262)):
                vv = p.verts.copy()
                vv[:, 0] += .013*np.sign(vv[:, 0])
                shift = center + np.array([0, side*(size[1] - PLATE_SIZE[1])/2, 0])
                emit(name, vv, p.tris, p.mat_preset, p.color, shift=shift @ matrix[:3, :3], rotate=facing)
        elif role in ("pulley_wheel", "pulley_hub"):
            diameter = 2*np.hypot(v[:, 0], v[:, 1]).max()
            material = [(MAT_ACCENT, [.95, .72, .04]), (MAT_RUBBER, colors["grip"]), (MAT_CHROME, colors["steel"])]
            for p in source[role]:
                mat, color = material[p["slot"]]
                dims = np.ptp(p["v"], axis=0)
                reference = [.148, .148, .027] if role == "pulley_wheel" else dims
                emit(name, p["v"], p["t"], mat, color, scale=np.array([diameter, diameter, size[2]])/reference)
        elif role == "pulley_bracket" or role.startswith("shroud_"):
            donor = "shroud_panel" if role == "shroud_rear" else role
            p, = source[donor]
            vv = np.asarray(p["v"])
            if role in {"shroud_panel", "shroud_cap"} and size[2] < min(size[:2]):
                orientation = Rotation.from_euler("x", 90, degrees=True)
                dims = np.ptp(orientation.apply(vv), axis=0)
                sc = (size/dims)[[0, 2, 1]]
                pos, quat, stock_sc = decompose_frames(obj["m"][:1])
                if not np.allclose(stock_sc, stock_sc[0, 0], atol=3e-5):
                    raise ValueError(f"{name}: cap needs an orthogonal mounting transform")
                q = (Rotation.from_quat(quat[0])*orientation).as_quat()
                emit(name, vv, p["t"], MAT_FRAME, colors["casting"], scale=sc*stock_sc[0],
                     pose=(pos[0]+center @ matrix[:3, :3], q))
            else:
                mat = MAT_SILVER if role in ("pulley_bracket", "shroud_side", "shroud_cap") else MAT_SELECTOR_WINDOW
                color = colors["silver"] if mat == MAT_SILVER else [.16, .18, .22]
                emit(name, vv, p["t"], mat, color, scale=size/np.ptp(vv, axis=0),
                     shift=center @ matrix[:3, :3])
    fits = fitted_layers(raw, mapping, source, human, base, emit)
    return entries, fits


def append_batch(view):
    data, humans = view/"data", view/"human_v5"
    base = load(humans/"base.json")
    if base["vertices"] != 1401:
        raise ValueError("Pull stations require the final new-hand body bundle")
    manifest = load(data/"wgm_manifest.json")
    targets = load(HERE/"pull_station_targets.json")
    if set(targets) & set(manifest["clips"]):
        raise ValueError("Pull stations must be appended to the preceding catalogue once")
    source = load_source()
    stock = (data/"parts.bin").read_bytes()
    indices = {p: i for i, p in enumerate(catalog_records(stock))}
    count = struct.unpack_from("<I", stock, 4)[0]
    extra, updates, report = [], {}, {}
    for key, mapping in targets.items():
        raw = load(data/f"{key}.json")
        try:
            clock, human = avatar_at_key_times(humans/f"{key}.bin", raw["acts"])
            entries, fits = assemble(key, raw, mapping, source, human, base)
            verify_skin(entries, clock, human, raw["acts"], np.asarray(base["triangles"]).reshape(-1, 3))
        except ValueError as exc:
            report[key] = {"unchanged": str(exc)}
            print(f"{key}: unchanged ({exc})", flush=True)
            continue
        for row in entries:
            packer = PartCatalogPacker()
            packer.add(row["verts"], row["tris"], row["smooth"])
            part = packer.build_bytes()[8:]
            if part not in indices:
                indices[part] = count + len(extra)
                extra.append(part)
            row["part_id"] = indices[part]
        updates[key], triangles, _ = pack_clip(key, raw["acts"], entries)
        manifest.setdefault("machineOverlays", {})[key] = {
            "targets": {str(e["index"]): e["name"] for e in entries}, "count": len(entries),
        }
        report[key] = dict(fits=fits, records=len(entries), triangles=triangles)
        print(f"{key}: {len(entries)} records, {triangles} triangles", flush=True)
    if not updates:
        raise ValueError("No pull-station overlays passed")
    for key, blob in updates.items():
        (data/f"{key}.wgm").write_bytes(blob)
    (data/"parts.bin").write_bytes(struct.pack("<4sI", b"WGC2", count+len(extra)) + stock[8:] + b"".join(extra))
    manifest["clips"] = sorted(set(manifest["clips"]) | set(updates))
    (data/"wgm_manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    (data/"pull_station_fit.json").write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    append_batch(parser.parse_args().view)
