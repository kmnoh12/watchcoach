"""Append the lower-machine tower skins to the final new-hand phone viewer bundle."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from upgrade_app3d_cable_towers import HERE, append_overlays, assemble as cable_parts
from upgrade_app3d_adjust_bench import ends, layers, tube
from upgrade_app3d_machines import decompose_frames, load_wgp2_human_frames, strip_fake_animation
from bench_fit import swept_clear, top_gap
from body_fit import SkinSweep, contact_region, fit_body_part
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER, MAT_SELECTOR_WINDOW
from scene_lat_parts import _nine, build_stickers, palette
from selector_tower import CHARCOAL, STEEL, YELLOW, cylinder, drilled_slider


# Original supports and their actual adjustment axis. The seat post and thigh restraint
# are the two moving contact assemblies that can be fitted without changing the exercise.
ADJUSTABLE = {
    "leg_extension": ("seat", "seat_pad", "mopt_seat_stem", None, None),
    "seated_leg_curl": ("thigh_roller", "thigh_roller", "restraint_support", "restraint_axle", "restraint_pin"),
}
UPPER_SHEAVES = {
    "leg_extension": ("pulley", "pulley.001"),
    "lying_leg_curl": ("pulley.001", "pulley.002"),
    "seated_leg_curl": ("pulley.001", "pulley.002"),
}


def load(path):
    return json.loads(path.read_text())


def vertices(obj):
    return np.asarray(obj["verts"]).reshape(-1, 3)


def pose(obj):
    pos, quat, scale = decompose_frames(strip_fake_animation(obj["m"]))
    return pos, Rotation.from_quat(quat), scale


def center(v):
    return (v.min(0) + v.max(0)) / 2


def entry(index, name, v, t, pos, rotation, scale, material, color, smooth=False):
    return dict(index=index, name=name, verts=v, tris=t, pos=pos, quats=rotation.as_quat(),
                sc=scale, mat=material, color=color, smooth=smooth)


def upper_mounts(raw, key, source, indices):
    """Extend the existing pulley bracket to carry both upper sheave axles."""
    objects = raw["objects"]
    wheel, return_wheel, cap = [objects[indices[n]] for n in (*UPPER_SHEAVES[key], "tower_cap")]
    a, b, cap_pos = [pose(obj)[0][0] for obj in (wheel, return_wheel, cap)]
    assert np.allclose(a[[0, 2]], b[[0, 2]]) and b[1] < a[1]
    (mesh,) = source["pulley_bracket"]
    dims = np.ptp(mesh["v"], axis=0)
    duct = np.array([0.043, 0, 0])
    colors = palette()

    def beam(position, size, rotation):
        return entry(indices["pulley_bracket"], "pulley_bracket", mesh["v"], mesh["t"],
                     position[None, :], rotation, np.asarray(size)[None, :] / dims,
                     MAT_FRAME, colors["casting"])

    # The crosspiece sits outside the original cable plane at a hub's end.
    span = beam((a + b) / 2 + duct, [a[1] - b[1] + 0.058, 0.032, 0.042],
                Rotation.from_euler("z", [90], degrees=True))
    base = cap_pos[2] + np.ptp(vertices(cap)[:, 2]) / 2 - 0.012
    head = a[2] + 0.018
    riser = a + duct + [0, 0.026, 0]
    riser[2] = (head + base) / 2
    foot = beam(riser, [head - base, 0.038, 0.042],
                Rotation.from_euler("y", [-90], degrees=True))
    return [span, foot]


def assemble(key, raw, slots, source):
    objects = raw["objects"]
    by_index = {int(i): group.split("__")[0] for i, (name, group) in slots.items()}
    for i, (name, _) in slots.items():
        assert objects[int(i)]["name"] == name, f"{key}: stale lower-machine role map for {name}"
    cable = {i: value for i, value in slots.items()
             if by_index[int(i)].startswith("pulley_")}
    result = cable_parts(raw, cable, source, batch=3)
    if key in UPPER_SHEAVES:
        result.extend(upper_mounts(raw, key, source, {obj["name"]: i for i, obj in enumerate(objects)}))
    plates = sorted((i for i, role in by_index.items() if role.endswith("stack_plate")),
                    key=lambda i: -(objects[i]["m"][0][14] + center(vertices(objects[i]))[2]))
    numbers = {i: rank for rank, i in enumerate(plates)}
    # The torso machine's selector and twin guides face sideways.
    plate_rotation = Rotation.from_euler("z", -90 if key == "torso_rotation_machine" else 0, degrees=True)
    colors = palette()
    for i, role in by_index.items():
        obj = objects[i]
        if role.startswith("pulley_"):
            continue
        v = vertices(obj)
        pos, rot, scale = pose(obj)
        pos = pos + rot.apply(scale * center(v))
        size = np.ptp(v, axis=0)
        if i in numbers:
            rot = rot * plate_rotation
            factor = abs(plate_rotation.inv().apply(size)) / [0.34, 0.28, 0.075]
            (mesh,) = source["stack_casting"]
            result.append(entry(i, role, mesh["v"], mesh["t"], pos, rot, scale * factor,
                                MAT_FRAME, colors["casting"]))
            kg = 2.5 + 5 * numbers[i]
            for decal in build_stickers(0.34, 0.28, 0.075, kg, round(kg * 2.20462262)):
                vv = decal.verts.copy()
                vv[:, 0] += 0.023 * np.sign(vv[:, 0])
                result.append(entry(i, role, vv, decal.tris, pos, rot, scale * factor,
                                    decal.mat_preset, decal.color))
        elif role.startswith("shroud_"):
            assert len(pos) == 1
            (mesh,) = source["shroud_panel"]
            # Align the panel's thickness with the original face normal.
            panel_rotation = (Rotation.from_euler("z", 90) if size.argmin() == 0 else
                              Rotation.from_euler("x", 90) if size.argmin() == 2 else Rotation.identity())
            factor = abs(panel_rotation.inv().apply(size)) / np.ptp(mesh["v"], axis=0)
            is_cap = role == "shroud_cap" and size.argmin() == 2
            material = MAT_FRAME if is_cap else MAT_SELECTOR_WINDOW
            color = colors["casting"] if is_cap else [0.16, 0.18, 0.22]
            result.append(entry(i, role, mesh["v"], mesh["t"], pos, rot * panel_rotation,
                                scale * factor, material, color))
    return result


def sources():
    return {key: value for name in ("scene_cable_source", "scene_cable_mount_source",
                                    "scene_lower_tower_source", "scene_bench_source")
            for key, value in load(HERE / f"{name}.json").items()}


def roller_layers(parts, obj):
    reference = np.vstack([part["v"] for part in parts])
    original = vertices(obj)
    factor = np.hypot(original[:, 0], original[:, 1]).max() / np.hypot(reference[:, 0], reference[:, 1]).max()
    half = np.ptp(reference[:, 2]) / 2
    goal = np.ptp(original[:, 2]) / 2
    result = []
    for part in parts:
        v = np.array(part["v"])
        v[:, :2] *= factor
        v[:, 2] = _nine(v[:, 2], half, goal, 0.041)
        result.append((v, np.array(part["t"]).reshape(-1, 3)))
    return result


def fit_support(key, raw, source, human, base):
    name, anatomy, support, axle, pin = ADJUSTABLE[key]
    index = {o["name"]: i for i, o in enumerate(raw["objects"])}
    objects = {o["name"]: o for o in raw["objects"]}
    obj = objects[name]
    p, rot, _ = pose(obj)
    assert len(p) == 1
    low, high = ends(objects[support])
    rail = high - low
    axis = rail / np.linalg.norm(rail)
    towards_skin = axis if axle is None else -axis
    if axle is None:
        parts = source["seat_pad"]
        meshes = layers(parts, obj)
        finishes = [(MAT_RUBBER if s["material"] == "E_grip" else MAT_PAD, s["rgb"]) for s in parts]
    else:
        meshes = roller_layers(source["leg_roller"], obj)
        finishes = [(MAT_PAD, palette()["pad"]), (MAT_RUBBER, palette()["grip"])]

    surface = np.vstack([rot[0].apply(v) + p[0] for v, _ in meshes])
    offsets = np.cumsum([0] + [len(v) for v, _ in meshes[:-1]])
    triangles = np.vstack([t + i for i, (_, t) in zip(offsets, meshes)])
    across = np.array([1.0, 0.0, 0.0])
    guess = fit_body_part(human, base, anatomy, p[0], surface, -towards_skin, across) - p[0]
    # Refine the bounding-plane fit against the actual curved upholstery.
    basis = np.stack((across, np.cross(towards_skin, across), towards_skin))
    contact, _ = contact_region(base, anatomy)
    skin = np.einsum("fvi,ji->fvj", human, basis)[:, contact].reshape(-1, 3, 3)
    gap = top_gap(skin, (surface + guess) @ basis.T, triangles)
    delta = guess + (gap - 0.0035) * towards_skin
    if np.linalg.norm(delta) > 0.04:
        raise ValueError(f"{name}: fitted contact outside the indexed travel")
    all_faces = np.asarray(base["triangles"]).reshape(-1, 3)
    sweep = SkinSweep(human, all_faces)
    if not swept_clear(sweep, surface + delta):
        raise ValueError(f"{name}: indexed contact intersects the V6 skin")

    rows = []

    def put(original, role, mesh, position, rotation, scale, material, color, smooth=False):
        vv, tt = mesh
        world = rotation.apply(vv * scale) + position
        if not swept_clear(sweep, world):
            raise ValueError(f"{original}: adjuster overlaps the V6 skin")
        rows.append(entry(index[original], role, vv, tt.ravel(), np.array([position]),
                          Rotation.from_quat([rotation.as_quat()]), np.array([scale]),
                          material, color, smooth))

    ones = np.ones(3)
    for mesh, (material, color) in zip(meshes, finishes):
        put(name, "seat_pad" if axle is None else "leg_roller", mesh, p[0] + delta, rot[0],
            ones, material, color, True)

    head = high + delta
    r = Rotation.from_matrix(np.stack((across, np.cross(axis, across), axis), axis=1))
    length = np.dot(head - low, axis)
    exposed = 0.09
    width = np.ptp(vertices(objects[support]), axis=0)
    width = np.median(width) / 0.042
    collar = head - exposed * axis
    frame = np.array([width, width, 1.0])
    put(support, "adjustment_rail", tube(), low, r, [width, width, length - exposed - 0.01],
        MAT_FRAME, CHARCOAL)
    put(support, "adjustment_rail", tube(True), collar, r, frame, MAT_FRAME, CHARCOAL)
    put(support, "adjustment_rail", drilled_slider(), head, r, frame, MAT_CHROME, STEEL)
    pin_target = support if pin is None else pin
    put(pin_target, "adjustment_pin", cylinder(0.003, 0.054, 0, 16), collar, r, frame, MAT_CHROME, STEEL)
    put(pin_target, "adjustment_pin", cylinder(0.009, 0.011, 0, 20),
        collar + (0.026 * width * across * (-1 if pin else 1)), r, frame, MAT_ACCENT, YELLOW)
    if axle:
        original = objects[axle]
        at, orientation, scale = pose(original)
        put(axle, "roller_axle", (vertices(original), np.asarray(original["tris"])), at[0] + delta,
            orientation[0], scale[0], MAT_CHROME, STEEL)

    return rows, dict(part=name, axis=axis.round(7).tolist(), anchor=low.tolist(), anatomy=anatomy,
                      gap_mm=round(1000 * top_gap(skin, (surface + delta) @ basis.T, triangles), 4),
                      offset_mm=round(1000 * np.dot(delta, axis), 4))


def append_batch(view):
    data = view / "data"
    source = sources()
    human_dir = view / "human_v5"
    base = load(human_dir / "base.json")
    assert base["vertices"] == 1401, "Use the final new-hand human mesh for the fit"
    clips, overlays = {}, {}
    fits = {}
    for key, slots in load(HERE / "lower_tower_targets.json").items():
        raw = load(data / f"{key}.json")
        entries = assemble(key, raw, slots, source)
        replaced = {i: name for i, (name, _) in slots.items()}
        if key in ADJUSTABLE:
            human = load_wgp2_human_frames(human_dir / f"{key}.bin")
            try:
                fitted, fits[key] = fit_support(key, raw, source, human, base)
            except ValueError as exc:
                fits[key] = {"exception": str(exc)}
            else:
                entries.extend(fitted)
                replaced.update({str(e["index"]): raw["objects"][e["index"]]["name"] for e in fitted})
        clips[key] = (raw["acts"], entries)
        overlays[key] = dict(targets=replaced, count=len(entries))
    append_overlays(view, clips, overlays)
    (data / "lower_tower_fit.json").write_text(json.dumps(fits, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    append_batch(parser.parse_args().view)
