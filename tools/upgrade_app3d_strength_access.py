"""Apply scene-derived rack, step-box and landmine exteriors after round plates."""

import argparse
from pathlib import Path
import shutil

import numpy as np

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_adjust_bench_rest import exterior
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import check_round_target, parts as bar_parts, round_parts
from fixed_pad_contact import penetration
from part_registry import MAT_CHROME, MAT_FRAME, MAT_PLYO_WOOD, MAT_RUBBER, MAT_SILVER


TARGETS = "strength_access_targets.json"
SOURCE = "scene_strength_access_source.json"
REPORT = "strength_access_fit.json"
WOOD_TEXTURE = HERE.parents[1] / "promo/parts/gym_wall_opt/walnut_wood.jpg"
RACK_ADJUSTERS = {"j_cup", "j_cup_bed", "j_cup_lip", "safety", "safety_pin", "safety_bracket", "pin_mount"}
BAR_SOURCES = {
    "barbell_shaft__001": "barbell_shaft__001",
    "bar_sleeve__001": "bar_sleeve__001",
    "bar_collar__001": "bar_collar__001",
    "bar_collar__003": "bar_collar__001",
    "sleeve_shoulder__002": "sleeve_shoulder__004",
    "v_branch__001": "barbell_shaft__001",
}
SCENE_SOURCES = {
    "floor_anchor__001": "base_beam__001",
    "floor_anchor__002": "base_beam__001",
    "frame_foot__006": "base_beam__001",
    "frame_flange__001": "frame_panel__001",
    "frame_flange__002": "frame_panel__001",
    "footplate__001": "frame_panel__001",
    "seat_pad__002": "frame_panel__001",
}


def scene_profile(group, slot, name):
    v = np.asarray(slot["v"])
    t = np.asarray(slot["t"])
    if group in {"hand_grip__007", "pullup_bar__001"}:
        sides = 12 if group == "hand_grip__007" else 8
        rubber = name.startswith("neutral_grip")
        material = MAT_RUBBER if rubber else MAT_CHROME
        color = slot["rgb"][0] if rubber or sides == 8 else [.76, .79, .84]
        dims, meshes = round_parts(slot, sides, material, True)
        return dims, [(p, t, color, mat, smooth) for p, t, smooth, mat in meshes]
    # The box uses its complete rounded profile for each board; its top and
    # bottom contact planes and existing side handle slots stay in place.
    materials = np.asarray(slot["material"])
    result = []
    for idx, color in enumerate(slot["rgb"]):
        faces = t[materials == idx]
        used, indices = np.unique(faces, return_inverse=True)
        mat = MAT_SILVER if idx else MAT_FRAME
        if slot["object"] == "Plyo box":
            mat = MAT_PLYO_WOOD
            if name.startswith("hinge_cheek"):
                mat, color = MAT_FRAME, [.56, .004, .005]
        result.append((v[used], indices.ravel(), color, mat, False))
    return np.ptp(v, axis=0), result


def upgrade(view):
    bars = load(HERE / "scene_rest_bar_source.json")
    bench = load(HERE / "scene_adjust_bench_rest_source.json")
    targets = load(HERE / TARGETS)
    bar_templates = {}
    for group, source in BAR_SOURCES.items():
        slot = bars[source]
        if group == "v_branch__001":
            dims, meshes = round_parts(slot, 12, MAT_FRAME, True)
        elif group in {"bar_sleeve__001", "sleeve_shoulder__002"}:
            # Several landmine clips grip the sleeve itself. Keep the old
            # twelve contact planes with the scene sleeve's surface samples.
            dims, meshes = round_parts(slot, 12, MAT_CHROME, True)
        else:
            dims, meshes = bar_parts(source, slot)
        bar_templates[group] = dims, [(v, t, slot["rgb"], mat, smooth) for v, t, smooth, mat in meshes]

    covered = {}
    for key, mapping in targets.items():
        if "rack_post" in mapping:
            raw = load(view / "data" / (key + ".json"))
            # Both faces of the new tube have real bores. The old offsets were
            # separate dark discs that would float in front of these holes.
            covered[key] = {str(i): obj["name"] for i, obj in enumerate(raw["objects"])
                            if obj["name"].split(".")[0] == "adjust_hole"}

    def assemble(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3):
            raise ValueError("missing final hand poses")
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        hp = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(hp.read_bytes(), "<f4", len(frames), 40)
        acts = np.asarray(raw["acts"], "<f4")
        rows, audit = [], {}
        for name, (index, group) in mapping.items():
            obj = raw["objects"][index]
            if name != obj["name"]:
                raise ValueError(f"{name}: stale target index")
            old = np.asarray(obj["verts"]).reshape(-1, 3)
            size = np.ptp(old, axis=0)
            center = (old.min(0) + old.max(0)) / 2
            pos, quats, scale = decompose_frames(strip_fake_animation(obj["m"]))
            if np.any(size <= 0) or np.any(scale <= 0) or not np.allclose(scale, scale[0], atol=1e-5):
                raise ValueError(f"{name}: exterior requires a rigid track")
            if group == "pullup_bar__001":
                check_round_target(name, old, 8)
            elif group in {"hand_grip__007", "barbell_shaft__001", "bar_sleeve__001"}:
                check_round_target(name, old, 12)
            if group in bar_templates:
                dims, layers = bar_templates[group]
            elif group.startswith("dumbbell_"):
                dims = np.ones(3)
                layers = [exterior(group.split("__")[0], bench, old, np.asarray(obj["tris"]))]
            else:
                slot = source[SCENE_SOURCES.get(group, group)]
                dims, layers = scene_profile(group, slot, name)
            if np.max(abs(center)) > 1e-6:
                raise ValueError(f"{name}: target is off its local centre")
            sized = scale * size / dims
            fitted = np.vstack([v for v, *_ in layers]) * sized[0]
            collision = penetration(frames, faces, times, acts, old * scale[0], fitted, pos, quats)
            if collision["added_hull_mm"] > 10:
                raise ValueError(f"{name}: visible new body overlap ({collision})")
            for v, tris, color, mat, smooth in layers:
                rows.append(dict(name=name, verts=v, tris=tris, color=color, mat=mat, smooth=smooth,
                                 pos=pos, quats=quats, sc=sized))
            audit[name] = dict(group=group, collision=collision, count=len(layers), frames=len(pos),
                               adjustment_axis=[0, 0, 1] if group == "frame_post__002" else None)
        for obj in raw["objects"]:
            if obj["name"].split(".")[0] in RACK_ADJUSTERS:
                # The supports catch the bar, and are not fitted against skin.
                # Preserve their mounted position and record their vertical axis.
                audit[obj["name"]] = dict(count=0, adjustment_axis=[0, 0, 1], contact="bar")
        return rows, audit

    report = append_batch(view, targets_file=TARGETS, source_file=SOURCE, report_file=REPORT,
                          build_model=assemble, covered_slots=covered)
    if any("unchanged" not in report[key] for key in ("step_up", "box_squat")):
        shutil.copyfile(WOOD_TEXTURE, view / "data/plyo_wood.jpg")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    upgrade(parser.parse_args().view)
