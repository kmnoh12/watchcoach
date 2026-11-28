"""Pose corrections for the three lower-body dumbbell clips, before WGM assembly.

All transforms are applied to the posed new hand and the named rigid assembly;
never move a weight head independently or change the lower-body motion.
"""

import numpy as np
from scipy.spatial.transform import Rotation

PAIRED = (
    "dumbbell_end",
    "dumbbell_end.001",
    "dumbbell_handle",
    "dumbbell_head",
    "dumbbell_head.001",
)
OTHER = (
    "dumbbell_end.002",
    "dumbbell_end.003",
    "dumbbell_handle.001",
    "dumbbell_head.002",
    "dumbbell_head.003",
)
HAMMER_L = ("handle", "dumbbell_head", "dumbbell_head.001")
HAMMER_R = ("handle.001", "dumbbell_head.002", "dumbbell_head.003")
CLIPS = {"curtsy_lunge", "dumbbell_squat", "lateral_lunge", "incline_hammer_curl"}


def normalize(a):
    return a / np.linalg.norm(a, axis=-1, keepdims=True)


def ease(t):
    u = np.clip(t, 0, 1)
    return u * u * (3 - 2 * u)


def arm(tr, skin, side, q, t):
    from build_v5_hand_viewer_copy import rigid

    upper, lower, hand = (b + "_" + side for b in ("upperarm", "lowerarm", "hand"))
    ui, li = (tr.names.index(n) for n in (upper, lower))
    pure = tr.u[:, ui] > 0.999
    ur, ut = rigid(tr.n[pure], skin[:, pure])
    shoulder = tr.heads[upper] @ ur + ut
    elbow = tr.heads[lower] @ q[lower] + t[lower]
    wrist = tr.heads[hand] @ q[hand] + t[hand]
    fingers = [
        j
        for j, n in enumerate(tr.names)
        if n.endswith("_" + side)
        and n.split("_")[0] in ("hand", "thumb", "index", "middle", "ring", "pinky")
    ]
    return shoulder, elbow, wrist, (tr.u[:, ui], tr.u[:, li], tr.u[:, fingers].sum(1))


def swing(points, origin, rotation, target):
    return (points - origin[:, None]) @ rotation.transpose(0, 2, 1) + target[:, None]


def swing_segment(a, b):
    a, b = normalize(a), normalize(b)
    return Rotation.from_quat(
        np.column_stack((np.cross(a, b), 1 + (a * b).sum(1)))
    ).as_matrix()


def reach(shoulder, elbow, wrist, target):
    """Two rigid links, preserving lengths and the original elbow bend plane."""
    upper, lower = elbow - shoulder, wrist - elbow
    aim = normalize(target - shoulder)
    pole = normalize(upper - (upper * aim).sum(1)[:, None] * aim)
    d = np.linalg.norm(target - shoulder, axis=1)
    l2 = (upper * upper).sum(1)
    axial = (d * d + l2 - (lower * lower).sum(1)) / (2 * d)
    radius2 = l2 - axial * axial
    if np.any(radius2 <= 0):
        raise ValueError("goblet support is beyond arm reach")
    joint = shoulder + aim * axial[:, None] + pole * np.sqrt(radius2)[:, None]
    return (
        joint,
        swing_segment(upper, joint - shoulder),
        swing_segment(lower, target - joint),
    )


def _correct_incline_hammer_curl(machine, acts, tr, skin, grips):
    """Restore left-right arm symmetry and open both shoulders slightly clear of seat and thighs."""
    from scipy.spatial import cKDTree
    from build_v5_hand_viewer_copy import rigid

    objects = {o["name"]: o for o in machine["objects"]}
    needed = set(HAMMER_L + HAMMER_R)
    if (
        not needed <= set(objects)
        or not np.array_equal(acts, machine["acts"])
        or any(len(objects[n]["m"]) != len(acts) for n in needed)
    ):
        raise ValueError("incline_hammer_curl: unexpected dumbbell assembly or key times")
    if {s: g["part"] for s, g in grips.items()} != {"l": HAMMER_L[0], "r": HAMMER_R[0]}:
        raise ValueError("incline_hammer_curl: expected both fitted hands")

    def arm_weight(side):
        cols = [
            j
            for j, n in enumerate(tr.names)
            if n.endswith("_" + side)
            and n.split("_")[0]
            in ("upperarm", "lowerarm", "hand", "thumb", "index", "middle", "ring", "pinky")
        ]
        return tr.u[:, cols].sum(1)

    wl, wr = arm_weight("l"), arm_weight("r")
    l_ids = np.flatnonzero(wl > 0)
    dists, r_match = cKDTree(tr.n).query(tr.n[l_ids] * np.array([-1.0, 1.0, 1.0]))
    if dists.max() > 1e-4:
        raise ValueError(f"incline_hammer_curl: asymmetric rest arm ({dists.max():.6f})")

    # The legacy source clip shifted both hammer handles by -34 mm in X, pulling the left arm
    # inward through the bench seat and thigh while leaving the right arm's motion clean.
    alpha = wl[l_ids][None, :, None]
    skin[:, l_ids] = (
        skin[:, l_ids] * (1.0 - alpha)
        + (skin[:, r_match] * np.array([-1.0, 1.0, 1.0])) * alpha
    )
    mirror_x = np.diag([-1.0, 1.0, 1.0])
    for l_name, r_name in zip(HAMMER_L, HAMMER_R):
        mats = np.asarray(objects[r_name]["m"], float).reshape(-1, 4, 4)
        mirrored = mats.copy()
        mirrored[:, 3, :3] *= np.array([-1.0, 1.0, 1.0])
        mirrored[:, :3, :3] = mirror_x @ mats[:, :3, :3] @ mirror_x
        objects[l_name]["m"] = mirrored.reshape(-1, 16).tolist()
    grips["l"]["pad_mm"] = {k: list(v) for k, v in grips["r"]["pad_mm"].items()}

    # Open both arms symmetrically around the shoulders (3 deg abduction, 1.5 deg external
    # rotation) so both dumbbells clear the seat and outer thighs throughout the curl.
    sym = skin.copy()
    for side, group, weight, sign in (
        ("l", HAMMER_L, wl, 1),
        ("r", HAMMER_R, wr, -1),
    ):
        upper = "upperarm_" + side
        pure = tr.u[:, tr.names.index(upper)] > 0.999
        ur, ut = rigid(tr.n[pure], sym[:, pure])
        shoulder = tr.heads[upper] @ ur + ut
        rot = Rotation.from_euler("yz", [-sign * 3.0, sign * 1.5], degrees=True).as_matrix()
        skin += (
            (sym - shoulder[:, None]) @ rot.T + shoulder[:, None] - sym
        ) * weight[None, :, None]
        for name in group:
            mats = np.asarray(objects[name]["m"], float).reshape(-1, 4, 4)
            mats[:, 3, :3] = (mats[:, 3, :3] - shoulder) @ rot.T + shoulder
            mats[:, :3, :3] = mats[:, :3, :3] @ rot.T
            objects[name]["m"] = mats.reshape(-1, 16).tolist()

    if not np.isfinite(skin).all() or not all(
        np.isfinite(objects[n]["m"]).all() for n in needed
    ):
        raise ValueError("incline_hammer_curl: non-finite corrected pose")
    return {}


def correct(key, machine, acts, tr, skin, q, t, grips):
    """Mutate only the selected pose and equipment tracks. Return separate support metadata."""
    if key == "incline_hammer_curl":
        return _correct_incline_hammer_curl(machine, acts, tr, skin, grips)
    goblet = key == "lateral_lunge"
    objects = {o["name"]: o for o in machine["objects"]}
    if (
        set(objects) != set(PAIRED if goblet else PAIRED + OTHER)
        or not np.array_equal(acts, machine["acts"])
        or any(len(o["m"]) != len(acts) for o in objects.values())
    ):
        raise ValueError(f"{key}: unexpected dumbbell assembly or key times")
    if {s: g["part"] for s, g in grips.items()} != {
        "l": PAIRED[2],
        "r": PAIRED[2] if goblet else OTHER[2],
    }:
        raise ValueError(f"{key}: expected both fitted hands")
    before = skin.copy()
    support = {}
    if goblet:
        # At the first key the bell is upright. Keep a fixed rest grasp on
        # opposite sides of its shaft, just below the flat face of the upper head.
        def rest_points(name):
            o = objects[name]
            m = np.asarray(o["m"][0]).reshape(4, 4)
            return np.asarray(o["verts"]).reshape(-1, 3) @ m[:3, :3] + m[3, :3]

        shaft = rest_points(PAIRED[2])
        top = rest_points(PAIRED[3])
        bottom = rest_points(PAIRED[4])
        if (
            top[:, 2].min() <= shaft[:, 2].mean()
            or bottom[:, 2].max() >= shaft[:, 2].mean()
        ):
            raise ValueError("expected upright goblet rest frame")
        gm = np.asarray(objects[PAIRED[2]]["m"]).reshape(-1, 4, 4)
        rel = Rotation.from_matrix(gm[:, :3, :3].transpose(0, 2, 1))
        follow = (rel * rel[0].inv()).as_matrix()
        origin = gm[:, 3, :3].copy()
        # Lift the complete weight in its own frame; do not stretch the grip.
        lift = follow @ [0, 0, 0.050]
        for obj in objects.values():
            mats = np.asarray(obj["m"]).reshape(-1, 4, 4)
            mats[:, 3, :3] += lift
            obj["m"] = mats.reshape(-1, 16).tolist()
    for side, group, sign in [("l", PAIRED, 1), ("r", OTHER, -1)]:
        if key == "curtsy_lunge" and side == "r":
            continue  # Only the left bell crosses the trailing right thigh.
        shoulder, elbow, wrist, weights = arm(tr, before, side, q, t)
        if not goblet:
            deg = (
                7.5 * ease((acts - 0.50) / 0.48)
                if key == "curtsy_lunge"
                else 4 + 4 * ease((acts - 0.32) / 0.48)
            )
            rot = Rotation.from_euler("y", -sign * deg, degrees=True).as_matrix()
            skin += (swing(before, shoulder, rot, shoulder) - before) * sum(weights)[
                None, :, None
            ]
            for name in group:
                mats = np.asarray(objects[name]["m"]).reshape(-1, 4, 4)
                mats[:, 3, :3] = (rot @ (mats[:, 3, :3] - shoulder)[:, :, None])[
                    :, :, 0
                ] + shoulder
                mats[:, :3, :3] = mats[:, :3, :3] @ rot.transpose(0, 2, 1)
                objects[name]["m"] = mats.reshape(-1, 16).tolist()
            continue
        # Cup the rim instead of closing both hands through the same shaft.
        turn = Rotation.from_euler("y", sign * 46, degrees=True).as_matrix()
        palm = (before[0] - wrist[0]) @ turn.T + wrist[0]
        hand = weights[2] > 0.5
        offset = np.zeros(3)
        offset[0] = sign * (
            (sign * shaft[:, 0]).max() + 0.0008 - (sign * palm[hand, 0]).min()
        )
        # The finished head is recessed ~1.44 mm inside its flat source
        # envelope here. Seat each hand on that face, leaving packing tolerance.
        offset[2] = top[:, 2].min() + lift[0, 2] + 0.00125 - palm[hand, 2].max()

        def carry(rest):
            return (rest - origin[0]) @ follow.transpose(0, 2, 1) + origin[:, None]

        grasp = carry(palm + offset)
        target = carry(wrist[0, None] + offset)[:, 0]
        joint, ru, rl = reach(shoulder, elbow, wrist, target)
        for posed, w in zip(
            (
                swing(before, shoulder, ru, shoulder),
                swing(before, elbow, rl, joint),
                grasp,
            ),
            weights,
        ):
            skin += (posed - before) * w[None, :, None]
        support[side] = {"part": PAIRED[3], "contact": "underside"}
    if goblet:
        grips.clear()  # Shaft pad measurements were for the seed pose, not the final support grip.
    if not np.isfinite(skin).all() or not all(
        np.isfinite(o["m"]).all() for o in objects.values()
    ):
        raise ValueError(f"{key}: non-finite corrected pose")
    return support
