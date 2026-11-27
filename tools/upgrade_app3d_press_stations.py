"""Overlay the approved upper-station parts on the final new-hand viewer bundle."""
import argparse
from itertools import product
import json
from pathlib import Path
import struct

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import catalog_records, layers, object_pose, tube
from upgrade_app3d_machines import PartCatalogPacker, decompose_frames, pack_clip, strip_fake_animation
from upgrade_app3d_pull_stations import (
    HERE, PLATE_SIZE, avatar_at_key_times, load, load_source, projected_clear,
    slider_bottom, verify_skin, vertices, world,
)
from bench_fit import fit
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER, MAT_SILVER
from scene_lat_parts import build_stickers, palette
from selector_tower import cylinder, drilled_slider

PASSAGES = {"weight_guide", "selector_rod", "selector_pin", "weight_selector"}


def pin_clear(triangles, pin):
    """Test only casting triangles that could touch the actual pin, including a shallow tongue."""
    # The upper lateral plate already grazes the selector by 0.5 mm.
    tolerance = .001
    lo, hi = pin.min(0), pin.max(0)
    nearby = ((triangles.max(1) > lo + tolerance) & (triangles.min(1) < hi - tolerance)).all(1)
    planes = np.unique(ConvexHull(pin).equations.round(10), axis=0)
    for poly in triangles[nearby]:
        for plane in planes:
            distance = poly @ plane[:3] + plane[3] + tolerance
            inside = distance <= 0
            if not inside.any():
                break
            if not inside.all():
                following = np.roll(poly, -1, axis=0)
                crossing = inside != np.roll(inside, -1)
                edge = np.divide(distance, distance - np.roll(distance, -1),
                                 out=np.zeros_like(distance), where=crossing)
                cuts = poly + (following - poly) * edge[:, None]
                pairs = np.stack((poly, cuts), axis=1)
                poly = pairs[np.column_stack((inside, crossing))]
        else:
            return False
    return True


def check_casting(mesh, faces, positions, obstacles):
    local = mesh - positions[0]
    for name, geometry, pin in obstacles:
        if pin:
            relative = geometry - positions[:, None, :]
            _, ids = np.unique(relative[:, 0].round(5), axis=0, return_index=True)
            clear = all(pin_clear(local[faces], relative[i]) for i in ids)
        else:
            clear = projected_clear(local, faces, geometry[0] - positions[0], [0, 1])
        if not clear:
            raise ValueError(f"{name}: existing pin or guide is obstructed")


def skin_envelope(row):
    """Bound the moving cable crosspiece at every angle about its original horizontal axis."""
    if row["name"] != "cable_bracket":
        return row
    axis = Rotation.from_quat(row["quats"]).apply([1, 0, 0])
    if not np.allclose(abs(axis), [1, 0, 0], atol=3e-5):
        raise ValueError(f"{row['name']}: changes its crosspiece axis")
    local = row["verts"] * row["sc"].max(0)
    radius = np.hypot(local[:, 1], local[:, 2]).max()
    extent = abs(local[:, 0]).max()
    envelope = np.array(list(product((-extent, extent), (-radius, radius), (-radius, radius))))
    return dict(row, verts=envelope, quats=np.tile([0, 0, 0, 1], (len(axis), 1)),
                sc=np.ones_like(row["sc"]))


def fit_adjusters(objects, groups, human, avatar, emit):
    colors = palette()
    fits = {}
    eye = Rotation.identity()
    sv, st = drilled_slider()
    slider = (sv + [0, 0, .12], st)

    def piece(name, shape, origin, orientation, scale, material, color, smooth=False):
        emit(name, *shape, material, color, pose=(origin, orientation, scale), smooth=smooth)

    def column(post, rail, knob, xy, bottom, bore, top, width, shaft, rotation, handle):
        # The outer post stays anchored. Its hollow collar and the inner index
        # holes share a transverse pin axis at the installed height.
        zlo, zhi = bottom
        dims = np.array(width) / .042
        if zlo >= bore - .01 or zhi <= bore + .009 or top <= zhi - .002:
            raise ValueError(f"{rail}: fitted support exceeds the physical post")
        at = lambda z: np.array([*xy, z])
        for low, high in ((zlo, bore - .01), (bore + .01, zhi)):
            if high > low:
                piece(post, tube(), at(low), rotation, [*dims, high-low], MAT_FRAME, colors["casting"])
        piece(post, tube(True), at(bore), rotation, [*dims, 1], MAT_FRAME, colors["casting"])
        low = slider_bottom(max(zlo + .008, bore-.075), top, bore)
        if not zlo <= low < bore < top:
            raise ValueError(f"{rail}: slider would leave its receiver")
        piece(rail, slider, at((top+low)/2), rotation, [*np.array(shaft)/.026, (top-low)/.24],
              MAT_CHROME, colors["steel"])
        axis = rotation.apply([1, 0, 0])
        extension = np.dot(handle - at(bore), axis)
        piece(knob, cylinder(.0029, width[0]/2 + extension, 0, 16),
              at(bore) + axis*(extension-width[0]/2)/2, rotation, [1]*3, MAT_CHROME, colors["steel"])
        piece(knob, cylinder(.011, .016, 0, 24), handle, rotation, [1]*3, MAT_ACCENT, [.95, .72, .04])
        return dict(axis=[0, 0, 1], origin=at(bore).tolist(), pin_axis=axis.round(7).tolist(),
                    receiver_z_m=[zlo, zhi], indexed_insert_z_m=[low, top])

    for name, role in groups.items():
        if role != "seat_pad":
            continue
        obj = objects[name]
        pos, rot, _ = object_pose(obj)
        source = load(HERE/"scene_bench_source.json")["seat_pad"]
        meshes = layers(source, obj)
        v = np.vstack([m[0] for m in meshes[:2]])
        f = np.vstack((meshes[0][1], meshes[1][1] + len(meshes[0][0])))
        rot, fitted, gap = fit(human, avatar, role, (pos, rot), (v, f))
        if not .002 <= gap <= .005:
            raise ValueError(f"{name}: fitted skin clearance is {gap*1000:.2f} mm")
        for mesh, part in zip(meshes, source):
            pad = part["material"] != "E_grip"
            piece(name, mesh, fitted, rot, [1]*3, MAT_PAD if pad else MAT_RUBBER, part["rgb"], pad)

        post, rail, knob = (next(n for n, r in groups.items() if r == g)
                            for g in ("seat_post", "adjustment_rail", "seat_adjuster"))
        post_v, rail_v = world(objects[post])[0], world(objects[rail])[0]
        center = post_v.mean(0)[:2]
        # Intersect the receiver axis with the tilted cushion's underside.
        h = min(m[0][:, 2].min() for m in meshes)
        normal = rot.apply([0, 0, 1])
        underside = fitted[2] + (h - normal[:2] @ (center-fitted[:2]))/normal[2]
        handle = np.asarray(objects[knob]["m"][0][12:15]).copy()
        original_bore = handle[2]
        bore = min(original_bore, underside-.023)
        handle[2] = bore
        outer = np.ptp(post_v, axis=0)[:2]
        inner = np.ptp(rail_v, axis=0)[:2]
        sleeve_top = min(post_v[:, 2].max(), underside-.004)
        meta = column(post, rail, knob, center, (post_v[:, 2].min(), sleeve_top),
                      bore, underside+.012, outer, inner, eye, handle)
        fits[name] = dict(**meta, gap_mm=gap*1000, offset_mm=1000*(fitted[2]-pos[2]),
                          pin_z_offset_mm=1000*(bore-original_bore))

    # The standing machine's handle heights are already keyed to the V6
    # grasp. Model the rail detents at that setting and keep both grip tracks.
    for rail, role in groups.items():
        if role != "adjustment_rail" or not rail.startswith("rail_adjust"):
            continue
        suffix = rail.removeprefix("rail_adjust")
        post, knob = "rail_socket"+suffix, "rail_pin"+suffix
        post_v, rail_v = world(objects[post])[0], world(objects[rail])[0]
        handle = np.asarray(objects[knob]["m"][0][12:15])
        fits[rail] = column(
            post, rail, knob, rail_v.mean(0)[:2], (post_v[:, 2].min(), post_v[:, 2].max()),
            handle[2], rail_v[:, 2].max(), np.ptp(post_v, axis=0)[:2], [.030, .030],
            Rotation.from_euler("z", -90, degrees=True), handle,
        )
    return fits


def support_lateral_pulleys(objects, source, emit):
    """Connect the original combined wheel/hubs to the fixed frame, outside the stack travel."""
    beam, = source["pulley_bracket"]
    hub, = source["pulley_hub"]
    steel = palette()["steel"]
    eye = Rotation.identity()

    def piece(name, mesh, size, center, mat, orientation=eye):
        scale = np.asarray(size) / np.ptp(mesh["v"], axis=0)
        emit(name, mesh["v"], mesh["t"], mat, steel, pose=(center, orientation, scale))

    returns = [name for name in objects if name.split(".")[0] == "return_pulley"]
    returns.sort()
    first = returns[0]
    p = np.asarray(objects[first]["m"][0][12:15])
    left, right = (np.asarray(objects[n]["m"][0][12:15])
                   for n in ("tower_post", "tower_post.001"))
    front = p[1] - .050
    z = p[2]
    xlo = min(left[0]-.019, p[0]-.020)
    xhi = right[0]+.019
    piece(first, beam, [xhi-xlo, .032, .034], [(xlo+xhi)/2, front, z], MAT_SILVER)
    for post in (left, right):
        piece(first, beam, [.038, post[1]-front+.022, .034],
              [post[0], (post[1]+front)/2, z], MAT_SILVER)
    axle_y = Rotation.from_euler("x", -90, degrees=True)
    for name in returns:
        x, y, z = objects[name]["m"][0][12:15]
        end = world(objects[name])[0, :, 1].max() + .004
        piece(name, hub, [.026, .026, end-front+.012],
              [x, (end+front-.012)/2, z], MAT_CHROME, axle_y)

    name = "stack_pulley"
    x, y, z = objects[name]["m"][0][12:15]
    half_width = np.ptp(world(objects[name])[0, :, 0])/2
    top = world(objects["tower_cap"])[0, :, 2].min() + .016
    low = z-.013
    for side in (-1, 1):
        piece(name, beam, [.016, .038, top-low],
              [x+side*(half_width+.008), y, (top+low)/2], MAT_SILVER)
    axle_x = Rotation.from_euler("y", 90, degrees=True)
    piece(name, hub, [.030, .030, 2*(half_width+.018)], [x, y, z], MAT_CHROME, axle_x)


def assemble(raw, mapping, source, human, avatar):
    objects = {o["name"]: o for o in raw["objects"]}
    groups = {name: group.rsplit("__", 1)[0] for name, (_, group) in mapping.items()}
    if any(raw["objects"][idx]["name"] != name for name, (idx, _) in mapping.items()):
        raise ValueError("Upper-station role map has stale object indices")
    rows = []
    colors = palette()

    def emit(name, v, t, mat, color, *, factor=(1, 1, 1), offset=(0, 0, 0), rotate=None,
             pose=None, smooth=False):
        obj = objects[name]
        p, q, sc = decompose_frames(strip_fake_animation(obj["m"]))
        if pose is not None:
            at, r, dims = pose
            p, q, sc = np.asarray([at]), np.asarray([r.as_quat()]), np.asarray([dims])
        rotation = Rotation.from_quat(q)
        if rotate is not None:
            q = (rotation * rotate).as_quat()
        rows.append(dict(index=mapping[name][0], name=name, verts=np.asarray(v), tris=np.ravel(t),
                         mat=mat, color=color, smooth=smooth, pos=p + rotation.apply(sc*offset),
                         quats=q, sc=sc*np.asarray(factor)))

    plates = sorted((n for n, r in groups.items() if r.endswith("stack_plate")),
                    key=lambda n: -objects[n]["m"][0][14])
    obstacles = [(n, world(objects[n]), r in {"selector_pin", "weight_selector"})
                 for n, r in groups.items() if r in PASSAGES]
    lateral = "selector" in objects
    for name, role in groups.items():
        obj = objects[name]
        v = vertices(obj)
        size, center = np.ptp(v, axis=0), (v.max(0) + v.min(0))/2
        if role.endswith("stack_plate"):
            mesh, = source["stack_casting"]
            emit(name, mesh["v"], mesh["t"], MAT_FRAME, colors["casting"],
                 factor=size/PLATE_SIZE, offset=center)
            row = rows[-1]
            rotation = Rotation.from_quat(row["quats"])
            if not np.allclose(rotation.as_matrix(), np.eye(3), atol=3e-5):
                raise ValueError(f"{name}: casting requires the stack's original upright orientation")
            check_casting(row["verts"]*row["sc"][0]+row["pos"][0],
                          row["tris"].reshape(-1, 3), row["pos"], obstacles)
            # Same scene numbers as the cable stations, sized to fit the shorter plate.
            kg = 2.5 + 5*plates.index(name)
            for label in build_stickers(.34, .28, .032 if lateral else .075, kg, round(kg*2.20462262)):
                vv = label.verts.copy()
                vv[:, 0] += .022 * np.sign(vv[:, 0])
                emit(name, vv, label.tris, label.mat_preset, label.color,
                     offset=center+[0, (.28-size[1])/2, 0])
        elif role in {"pulley_wheel", "pulley_hub"}:
            material = [(MAT_ACCENT, [.95, .72, .04]), (MAT_RUBBER, colors["grip"]),
                        (MAT_CHROME, colors["steel"])]
            d = 2*np.hypot(v[:, 0]-center[0], v[:, 1]-center[1]).max()
            for mesh in source[role]:
                mat, color = material[mesh["slot"]]
                ref = [.148, .148, .027] if role == "pulley_wheel" else np.ptp(mesh["v"], axis=0)
                emit(name, mesh["v"], mesh["t"], mat, color, factor=[d, d, size[2]]/np.asarray(ref),
                     offset=center)
        elif role in {"pulley_bracket", "cable_mount", "shroud_rear", "shroud_cap", "shroud_panel"}:
            donor = {"cable_mount": "pulley_bracket", "shroud_rear": "shroud_panel",
                     "shroud_panel": "shroud_side"}.get(role, role)
            mesh, = source[donor]
            ref = np.ptp(mesh["v"], axis=0)
            mat = MAT_SILVER if role in {"pulley_bracket", "cable_mount"} else MAT_FRAME
            color = colors["silver" if mat == MAT_SILVER else "casting"]
            if role == "shroud_cap":
                emit(name, mesh["v"], mesh["t"], mat, color, factor=size[[0, 2, 1]]/ref,
                     offset=center, rotate=Rotation.from_euler("x", 90, degrees=True))
            else:
                emit(name, mesh["v"], mesh["t"], mat, color, factor=size/ref, offset=center)

    if lateral:
        support_lateral_pulleys(objects, source, emit)
    return rows, fit_adjusters(objects, groups, human, avatar, emit)


def append_batch(view):
    data, humans = view/"data", view/"human_v5"
    avatar = load(humans/"base.json")
    if avatar["vertices"] != 1401:
        raise ValueError("Upper stations require the final new-hand avatar")
    manifest = load(data/"wgm_manifest.json")
    targets = load(HERE/"press_station_targets.json")
    source = {**load_source(), **load(HERE/"scene_press_source.json")}
    stock = (data/"parts.bin").read_bytes()
    indices = {record: i for i, record in enumerate(catalog_records(stock))}
    count = struct.unpack_from("<I", stock, 4)[0]
    extra, updates, report = [], {}, {}
    for key, mapping in targets.items():
        raw = load(data/f"{key}.json")
        human_file = humans/f"{key}.bin"
        try:
            clock, human = avatar_at_key_times(human_file, raw["acts"])
            rows, fits = assemble(raw, mapping, source, human, avatar)
            verify_skin([skin_envelope(r) for r in rows], clock, human, raw["acts"],
                        np.asarray(avatar["triangles"]).reshape(-1, 3))
        except ValueError as exc:
            report[key] = {"unchanged": str(exc)}
            print(f"{key}: unchanged ({exc})", flush=True)
            continue
        new_targets = {str(e["index"]): e["name"] for e in rows}
        preceding = manifest.get("machineOverlays", {}).get(key)
        old_targets = (preceding or {}).get("targets", manifest.get("plateOverlays", {}).get(key, {}))
        if set(new_targets) & set(old_targets) or (key in manifest["clips"] and not old_targets):
            raise ValueError(f"{key}: upper-station overlay overlaps existing equipment records")
        for row in rows:
            packer = PartCatalogPacker()
            packer.add(row["verts"], row["tris"], row["smooth"])
            record = packer.build_bytes()[8:]
            if record not in indices:
                indices[record] = count + len(extra)
                extra.append(record)
            row["part_id"] = indices[record]
        blob, triangles, _ = pack_clip(key, raw["acts"], rows)
        old_count = 0
        if old_targets:
            old = (data/f"{key}.wgm").read_bytes()
            off = 8 + 4*len(raw["acts"])
            if old[:6] != blob[:6] or old[8:off] != blob[8:off]:
                raise ValueError(f"{key}: preceding overlay uses a different timeline")
            old_count = struct.unpack_from("<H", old, 6)[0]
            blob = old[:6] + struct.pack("<H", old_count + len(rows)) + old[8:] + blob[off:]
        updates[key] = blob
        manifest.setdefault("machineOverlays", {})[key] = dict(targets={**old_targets, **new_targets},
                                                                count=len(rows)+old_count)
        report[key] = dict(fits=fits, records=len(rows), preceding=old_count, triangles=triangles)
        print(f"{key}: {len(rows)} records, {triangles} triangles", flush=True)
    for key, blob in updates.items():
        (data/f"{key}.wgm").write_bytes(blob)
    (data/"parts.bin").write_bytes(stock[:4]+struct.pack("<I", count+len(extra))+stock[8:]+b"".join(extra))
    manifest["clips"] = sorted(set(manifest["clips"]) | set(updates))
    (data/"wgm_manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    (data/"press_station_fit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    append_batch(parser.parse_args().view)
