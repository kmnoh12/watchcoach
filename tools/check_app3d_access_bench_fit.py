"""Read-only body-fit trials for the coupled accessory benches withheld from batch 04.
Run on a posed viewer bundle to retry with a different avatar. No partial assembly is installed.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, ends, load, object_pose
from upgrade_app3d_bench_pads import cushion
from upgrade_app3d_machines import load_wgp2_human_frames
from bench_fit import fit, swept_clear, top_gap
from body_fit import SkinSweep, contact_region, roller_depth_bound


def check(view):
    human = view / 'human_v5'
    base = load(human / 'base.json')
    src = load(HERE / 'scene_flat_bench_source.json')
    result = {}
    for key, names in {
        'decline_sit_up': ['rounded_decline_back'],
        'preacher_curl_dumbbell': ['arm_pad', 'arm_pad.001', 'seat'],
        'single_arm_dumbbell_preacher_curl': ['arm_pad', 'seat'],
    }.items():
        objects = {o['name']: o for o in load(view / 'data' / (key + '.json'))['objects']}
        frames = load_wgp2_human_frames(human / (key + '.bin'))
        sweep = SkinSweep(frames, np.asarray(base['triangles']).reshape(-1, 3))
        model = result[key] = {}
        for name in names:
            obj = objects[name]
            p, r, s = object_pose(obj)
            dims = np.ptp(np.asarray(obj['verts']).reshape(-1, 3), axis=0) * s
            role = 'back_pad' if name == 'rounded_decline_back' else (
                'seat_pad' if name == 'seat' else 'arm_pad')
            pivot = None
            if role == 'back_pad':
                # Reorient the contact plane so +Y runs uphill, as expected by the hinge solver.
                r = r * Rotation.from_rotvec([0, 0, np.pi])
                pivot = object_pose(objects['board_pivot'])[0]
                axis = r.apply([1, 0, 0])
            else:
                if r.apply([0, 0, 1])[2] < 0:
                    r = r * Rotation.from_rotvec([np.pi, 0, 0])
                post = 'seat_post' if role == 'seat_pad' else name.replace('arm_pad', 'pad_post')
                bottom, head = ends(objects[post])
                axis = (head - bottom) / np.linalg.norm(head - bottom)
                assert np.allclose(axis, [0, 0, 1], atol=1.e-5)
            parts = list(cushion(src, 'back_pad' if pivot is not None else 'seat_pad', dims))
            v = np.vstack([x[0] for x in parts[:2]])
            t = np.vstack([parts[0][1].reshape(-1, 3), parts[1][1].reshape(-1, 3) + len(parts[0][0])])
            skin = contact_region(base, role)[0]
            local = np.einsum('fvi,ij->fvj', frames - p, r.as_matrix())
            row = model[name] = dict(axis=axis.round(7).tolist(), pivot=None if pivot is None else pivot.tolist(),
                                     initial_gap_mm=round(1000 * top_gap(local[:, skin].reshape(-1, 3, 3), v, t), 3))
            try:
                rot, at, gap = fit(frames, base, role, (p, r), (v, t), pivot)
                if not (.002 <= gap <= .005 and swept_clear(sweep, rot.apply(np.vstack([x[0] for x in parts])) + at)):
                    raise ValueError('body clearance or swept support envelope failed')
                row.update(gap_mm=round(1000 * gap, 3), dz_mm=round(1000 * (at - p)[2], 3))
            except ValueError as ex:
                row['not_fitted'] = str(ex)
        if 'height_insert' in objects:
            # Two bilateral pairs share one indexed column. Never slide the four foam pads
            # individually off their axles to make a mannequin pass. Record original depths only.
            a, b = ends(objects['height_insert'])
            slide = (b - a) / np.linalg.norm(b - a)
            for i, name in enumerate(('roller', 'roller.001', 'roller.002', 'roller.003')):
                obj = objects[name]
                p, r, s = object_pose(obj)
                axle, ar, _ = object_pose(objects['roller_axle' if i < 2 else 'roller_axle.001'])
                axis = ar.apply([0, 0, 1])
                assert np.linalg.norm(np.cross(p - axle, axis)) < 1.e-5
                surface = r.apply(np.asarray(obj['verts']).reshape(-1, 3) * s) + p
                model[name] = dict(axle=axis.round(7).tolist(), axle_center=axle.tolist(),
                                   shared_slide=slide.round(7).tolist(),
                                   original_vertex_depth_mm=round(1000 * roller_depth_bound(frames, surface, swept=False), 3))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer', type=Path)
    print(json.dumps(check(parser.parse_args().viewer), indent=2))
