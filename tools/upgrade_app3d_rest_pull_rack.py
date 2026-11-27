"""Fit gym rack and dip-tower exteriors to the seven remaining pull models."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from body_fit import fit_body_part
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER
from upgrade_app3d_lower_iso import outline, stock_planes
from upgrade_app3d_lower_sled import compact_mitre
from upgrade_app3d_lower_towers import center, pose, vertices
from upgrade_app3d_rest_bars import check_round_target, round_parts


TARGETS = "rest_pull_rack_targets.json"
SOURCE = "scene_rest_pull_rack_source.json"
REPORT = "rest_pull_rack_fit.json"
GRIPS = {"dip_handle", "hand_grip", "pullup_bar", "row_bar", "support_handle"}
HARDWARE = {"fastener", "handle_mount"}
RUBBER = {"rubber_foot", "step_platform"}
SHELLS = {
    "floor_anchor": "step_platform",
    "footplate_support": "tower_brace",
    "frame_gusset": "frame_brace",
    "frame_stay": "handle_support",
    "lever_arm": "handle_support",
}


def prototypes(view, targets, source):
    """Pack each group once. Only the scale and old transform vary by instance."""
    tower = load(HERE / "scene_rest_pull_tower_source.json")
    cable = load(HERE / "scene_rest_cable_source.json")
    lower = load(HERE / "scene_lower_iso_source.json")
    donors = {**tower, **source, "rubber_foot": cable["rubber_foot"],
              "tower_brace": tower["frame_brace"]}
    references, rejected = {}, {}
    for key, mapping in targets.items():
        objects = load(view / "data" / f"{key}.json")["objects"]
        for name, (index, group) in mapping.items():
            obj = objects[index]
            if obj["name"] != name:
                rejected[key] = f"{name}: stale exterior index"
                break
            old = vertices(obj)
            references.setdefault(group, []).append(old - center(old))

    result = {}
    for group, refs in references.items():
        role = group.split("__")[0]
        if role in GRIPS | HARDWARE:
            metal = role in HARDWARE | {"pullup_bar", "row_bar"}
            donor = source["pullup_bar"] if metal else tower["dip_handle"]
            if group in {"pullup_bar__001", "handle_mount__003", "dip_handle__002"}:
                donor = tower["pullup_bar"]
            elif group == "hand_grip__002":
                donor = lower["hand_grip"]
            dims, layers = round_parts(donor, len(refs[0]) // 2,
                                       MAT_SILVER if role == "fastener" else MAT_CHROME if metal else MAT_RUBBER,
                                       role != "fastener")
            finish = donor["rgb"] if metal else tower["dip_handle"]["rgb"]
            result[group] = dims, [(*part, finish) for part in layers]
            continue

        donor = donors[SHELLS.get(role, role)]
        shape = np.asarray(donor["v"])
        dims = np.ptp(shape, axis=0)
        shape = shape - center(shape)
        fitted = [compact_mitre(shape, ref) for ref in refs if len(ref) == 24 and role not in RUBBER]
        if fitted:
            if all(part is not None for part in fitted):
                shape, dims = fitted[0]
            else:
                # The short neutral-grip mounts have deeper end mitres.
                # Clip across the tube without shortening its weld-to-weld span.
                limits = np.unique(np.vstack([stock_planes(ref / np.ptp(ref, axis=0)) for ref in refs]), axis=0)
                local = shape / dims
                across = local[:, 1:] @ limits[:, 1:3].T
                allowed = np.maximum(0., -limits[:, 3] - local[:, :1] * limits[:, 0])
                ratio = np.divide(allowed, across, out=np.ones_like(across), where=across > 1e-10)
                shape[:, 1:] *= ratio.min(1).clip(0., 1.)[:, None]
        material = MAT_RUBBER if role in RUBBER else MAT_FRAME
        color = cable["rubber_foot"]["rgb"] if role in RUBBER else source["base_beam"]["rgb"]
        result[group] = dims, [(shape, np.ravel(donor["t"]), False, material, color)]
    return result, rejected


def row_height(raw, frames, base):
    """Record the indexed height and the torso-clearance fit for the fixed hand track."""
    objects = raw["objects"]
    bar = next(obj for obj in objects if obj["name"] == "row_bar")
    p, r, s = pose(bar)
    surface = r[0].apply(vertices(bar) * s[0]) + p[0]
    up, axle = [0, 0, 1], [1, 0, 0]
    # At the top of the row the torso approaches the bar from below. The
    # phase-locked palms wrap its sides. Moving the bar alone would break that grasp.
    fitted = fit_body_part(frames, base, "back_pad", p[0], surface, up, axle)
    pins = [pose(obj)[0][0] for obj in objects if obj["name"].split(".")[0] == "pin"]
    holes = [pose(obj)[0][0][2] for obj in objects if obj["name"].split(".")[0] == "height_hole"]
    return dict(axis=up, bar_z_mm=round(float(p[0, 2]) * 1000, 3),
                pin_z_mm=sorted({round(float(pos[2]) * 1000, 3) for pos in pins}),
                other_holes_z_mm=sorted({round(float(z) * 1000, 3) for z in holes}),
                requested_clearance_mm=3.5,
                fitted_bar_z_mm=round(float(fitted[2]) * 1000, 3),
                applied_shift_mm=0, status="preserved recorded grip and indexed mounting")


def upgrade(view):
    targets = load(HERE / TARGETS)
    shapes, rejected = prototypes(view, targets, load(HERE / SOURCE))

    def build(key, raw, mapping, source, frames, base):
        if key in rejected:
            raise ValueError(rejected[key])
        if frames is None or frames.shape[1:] != (1401, 3) or not np.isfinite(frames).all():
            raise ValueError("Missing final posed body")
        rows, audit = [], {}
        for name, (index, group) in mapping.items():
            obj = raw["objects"][index]
            old = vertices(obj)
            origin = center(old)
            role = group.split("__")[0]
            dims, layers = shapes[group]
            p, r, s = pose(obj)
            linear = r.as_matrix() * s[:, None, :]
            stock = np.asarray(obj["m"][:len(p)]).reshape(-1, 4, 4)
            if len(p) != 1 or not np.allclose(linear, stock[:, :3, :3].transpose(0, 2, 1), atol=2e-5):
                raise ValueError(f"{name}: unexpected exterior track")
            if role in GRIPS | HARDWARE:
                check_round_target(name, old - origin, len(old) // 2)
            scale = np.ptp(old, axis=0) / dims
            fitted = np.vstack([v * scale + origin for v, *_ in layers])
            outward = outline(fitted, stock_planes(old))
            change = outline(old, stock_planes(fitted)) if role in GRIPS else 0.
            if role == "step_platform":
                change = abs(old[:, 2].max() - fitted[:, 2].max())
            if max(outward, change) > .000025:
                raise ValueError(f"{name}: scene mesh changed the original joint or contact surface")
            for v, t, smooth, mat, color in layers:
                rows.append(dict(name=name, verts=v, tris=t, pos=p + linear @ origin,
                                 quats=r.as_quat(), sc=s * scale, smooth=smooth, mat=mat, color=color))
            audit[name] = dict(group=group, records=len(layers), poses=len(p),
                               contact_mm=round(max(0., change) * 1000, 6))
            if role == "row_bar":
                audit[name]["height"] = row_height(raw, frames, base)
        return rows, audit

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE,
                        report_file=REPORT, build_model=build)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
