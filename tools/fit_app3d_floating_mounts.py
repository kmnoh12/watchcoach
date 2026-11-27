"""Seat fixed equipment mounts before the final exterior overlay is packed."""

import argparse
import json
from pathlib import Path

import numpy as np

# The viewer part tools are registered by the machine conversion scripts.
from upgrade_app3d_machines import compose_matrix
from part_catalog import make_chamfered_box
from scene_lat_parts import palette


REVERSE_PEC_DECKS = ("pec_deck~m=reverse", "pec_deck~m=reverse_single")


def seat_hip_thrust_rests(parts, objects):
    color = palette()["casting"]
    for suffix in ("", ".001"):
        rest = objects["horn_rest" + suffix]
        rail = objects["floor_rail" + suffix]
        rest_pose, = rest["m"]
        rail_pose, = rail["m"]
        # The moving plates descend past the old stop at the top of the rep.
        rest_pose[14] = .335
        for end, rail_y, rest_y in (("front", .780, .800), ("rear", .870, 1.055)):
            name = f"horn_rest_brace_{end}{suffix}"
            if name in objects:
                continue
            # The diagonal risers cover both ends of the stop. Horizontal cuts
            # seat the risers inside the rail and the stop without exposed ends.
            base = np.array([rail_pose[12], rail_y, .040])
            tip = np.array([rest_pose[12], rest_y, .308])
            half_width = .022
            height = tip[2] - base[2]
            verts, tris = make_chamfered_box(
                np.array([-half_width, -half_width, 0.]),
                np.array([half_width, half_width, height]),
                bevel=.002,
            )
            verts[:, :2] += (verts[:, 2] / height)[:, None] * (tip - base)[:2]
            pose = compose_matrix(base, np.array([0., 0., 0., 1.]), np.ones(3))
            parts.append(dict(
                name=name, color=color, verts=verts.ravel().tolist(),
                tris=tris.tolist(), m=[pose.T.ravel().tolist()],
            ))


def seat_pec_deck_panel(objects):
    panel = objects["instruction_panel"]
    mount = objects["panel_mount"]
    tower = objects["tower_side"]
    # The 460 mm backing plate laps the front corners of both uprights.
    # Move the sign and its backing together so the print stays on the face.
    panel_pose, = panel["m"]
    mount_pose, = mount["m"]
    tower_pose, = tower["m"]
    depth = tower_pose[13] - .045
    panel_pose[13] += depth - mount_pose[13]
    mount_pose[13] = depth


def apply(view):
    for key in ("hip_thrust_machine", *REVERSE_PEC_DECKS):
        path = view / "data" / (key + ".json")
        raw = json.loads(path.read_text())
        parts = raw["objects"]
        objects = {part["name"]: part for part in parts}
        if key == "hip_thrust_machine":
            seat_hip_thrust_rests(parts, objects)
        else:
            seat_pec_deck_panel(objects)
        path.write_text(json.dumps(raw, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    apply(parser.parse_args().view)
