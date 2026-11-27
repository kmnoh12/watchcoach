"""Fasten three detached lower-machine mounts in the final viewer conversion."""

import argparse
import json
from pathlib import Path

import numpy as np

from upgrade_app3d_machines import compose_matrix
from part_catalog import make_chamfered_box


def brace(name, start, end, width, color):
    start, end = np.asarray(start), np.asarray(end)
    length = np.linalg.norm(end - start)
    along = (end - start) / length
    normal = np.array([0., 0., 1.] if abs(along[2]) < .8 else [1., 0., 0.])
    across = np.cross(normal, along)
    across /= np.linalg.norm(across)
    axes = np.column_stack((across, np.cross(along, across), along))
    half = width / 2
    verts, tris = make_chamfered_box(
        np.array([-half, -half, 0.]), np.array([half, half, length]), bevel=.002,
    )
    matrix = compose_matrix(start, np.array([0., 0., 0., 1.]), np.ones(3))
    matrix[:3, :3] = axes
    return dict(name=name, color=color, verts=verts.ravel().tolist(),
                tris=tris.tolist(), m=[matrix.T.ravel().tolist()])


def lying_pivot(color):
    # Fasten both fixed supports to the floor crossmember and the respective
    # axle ends. The bearing tabs turn inboard of the rotating lever.
    for side, suffix in ((-1, ""), (1, ".001")):
        yield brace("pivot_bearing_tab" + suffix, (side * .313, .510, .806),
                    (side * .281, .490, .887), .030, color)
        yield brace("pivot_base_brace" + suffix, (side * .318, .609, .237),
                    (side * .318, .720, .068), .038, color)
    yield brace("pivot_crossfoot_join", (0., .537, .087), (0., .720, .069), .041, color)


def seated_curl_rail(color):
    # Slip the lower-profile end members inside the rail and the crossfeet.
    yield brace("base_rail_join_front", (0., -.477, .087), (0., -.620, .069), .041, color)
    yield brace("base_rail_join_rear", (0., .426, .087), (0., .570, .069), .041, color)
    yield brace("base_rail_join_tower", (.010, .420, .102), (.110, .420, .117), .033, color)


def calf_rear_tie(color):
    # The rear tie sits higher and behind the runner tips. Land the two end
    # brackets inside the runners so the tie carries load to both sides.
    for side, suffix in ((-1, ""), (1, ".001")):
        yield brace("rear_tie_runner_brace" + suffix, (side * .277, .560, .080),
                    (side * .380, .533, .062), .032, color)


def apply(view):
    for key, reference, make_braces in (
        ("lying_leg_curl", "pivot_support", lying_pivot),
        ("seated_leg_curl", "base_rail", seated_curl_rail),
        ("seated_calf", "rear_tie", calf_rear_tie),
    ):
        path = view / "data" / (key + ".json")
        clip = json.loads(path.read_text())
        parts = clip["objects"]
        by_name = {part["name"]: part for part in parts}
        # Keep the existing WGM source slots stable by appending static braces.
        parts.extend(part for part in make_braces(by_name[reference]["color"])
                     if part["name"] not in by_name)
        path.write_text(json.dumps(clip, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    apply(parser.parse_args().viewer)
