"""Skin only the fixed back/forearm pads and stroke-driven knee platforms on seven towers."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_lower_press_pads import common_shapes, upholstery
from upgrade_app3d_lower_towers import center, pose, vertices
from fixed_pad_contact import penetration

TARGETS = "pull_tower_pad_targets.json"
REPORT = "pull_tower_pad_fit.json"
SOURCE = "scene_pull_tower_pad_source.json"


def upgrade(view):
    # back_pad__003 already exists on the pullover; reuse its exact catalogue geometry.
    shared = common_shapes(view)
    back = load(HERE / "scene_lower_pad_source.json")["back_pad"]

    def build(key, raw, mapping, source, frames, base):
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        clock = np.frombuffer(
            (view / "human_v5" / (key + ".bin")).read_bytes(), "<f4", len(frames), 40
        )
        entries, meta = [], {}
        for name, (i, group) in mapping.items():
            obj = raw["objects"][i]
            assert obj["name"] == name
            role = group.split("__")[0]
            p, rot, s = pose(obj)
            if not np.allclose(s, s[0]) or not np.allclose(
                rot.as_matrix(), np.eye(3), atol=1e-5
            ):
                raise ValueError(f"{name}: unexpected carrier axes")
            travel = np.ptp(p, axis=0)
            if role == "knee_pad":
                if (
                    len(p) != len(raw["acts"])
                    or travel[2] < 0.01
                    or max(travel[:2]) > 0.001
                ):
                    raise ValueError(
                        f"{name}: expected guided vertical exercise stroke"
                    )
            elif len(p) != 1:
                raise ValueError(f"{name}: fixed pad unexpectedly moves")
            old = vertices(obj) * s[0]
            dims = np.ptp(old, axis=0)
            if group not in shared:
                shared[group] = upholstery(
                    back if role == "back_pad" else source[role], dims
                )
            parts = shared[group]
            proto = np.vstack([part[0] for part in parts])
            scale = dims / np.ptp(proto, axis=0)
            # The avatar leans against the negative Y face. Put the finished face there.
            face = (
                Rotation.from_euler("z", 180, degrees=True)
                if role == "back_pad"
                else Rotation.identity()
            )
            local = face.apply(proto * scale)
            shift = center(old) - center(local)
            local += shift
            hit = penetration(
                frames, faces, clock, raw["acts"], old, local, p, rot.as_quat()
            )
            if hit["added_hull_mm"] > 10:
                raise ValueError(f"{name}: new skin intrusion {hit}")
            for v, t, mat, color in parts:
                entries.append(
                    dict(
                        name=name,
                        verts=v,
                        tris=np.ravel(t),
                        pos=p + rot.apply(shift),
                        quats=(rot * face).as_quat(),
                        sc=np.tile(scale, (len(p), 1)),
                        mat=mat,
                        color=color,
                        smooth=True,
                    )
                )
            # None of these supports has an indexed body-size setting: the knee carrier is
            # counterweighted and guided, the back/arm pads mount directly to stationary rails.
            meta[name] = dict(
                group=group,
                records=len(parts),
                adjustment_axis=None,
                stroke_axis=[0, 0, 1] if role == "knee_pad" else None,
                stroke_mm=round(1000 * travel[2], 3),
                collision=hit,
            )
        return entries, meta

    return append_batch(
        view,
        targets_file=TARGETS,
        source_file=SOURCE,
        report_file=REPORT,
        build_model=build,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    upgrade(parser.parse_args().view)
