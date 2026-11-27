"""Seat the six outgoing spans on their existing pulley grooves and moving eyes.

Run on the final hand-adjusted tracks, before packing the cable exteriors. Do not
move a pulley, stack, handle or hand to compensate for a distorted free span.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from retarget_app3d_cable_hands import span, unit

HERE = Path(__file__).resolve().parent / 'viewer3d'
FLY = {f'cable_crossover~h={h}~g=d~p=fly_{h}' for h in ('high', 'mid')}
OVERHEAD = {'cable_overhead_extension', 'rope_overhead_extension'}


def matrices(obj):
    return np.asarray(obj['m']).reshape(-1, 4, 4)


def outlet(wheel, rubber, eye, cross_pull):
    # Same local wheel frame and template scale as the preceding pulley exterior.
    m, = matrices(wheel)
    basis = m[:3, :3]
    v = np.asarray(wheel['verts']).reshape(-1, 3)
    scale = np.linalg.norm(v[:, :2], axis=1).max() / .074
    local_eye = np.einsum('ij,kj->ik', eye - m[3, :3], basis)
    if not np.allclose(basis @ basis.T, np.eye(3)):
        raise ValueError('Expected a stationary, unscaled outlet wheel')
    # Cross-pulls leave over the near lip; the two nearly in-plane overhead
    # pulls wrap under the low pulley and leave from the groove floor.
    height = abs(rubber[:, 2])
    level = height.max() if cross_pull else height.min()
    ring = rubber[np.isclose(rubber[:, 2], level), :2] * scale
    radius = np.linalg.norm(ring, axis=1).max()
    xy = local_eye[:, :2]
    d = np.linalg.norm(xy, axis=1, keepdims=True)
    if d.min() <= radius:
        raise ValueError('Eye is inside outlet wheel')
    u = xy / d
    perp = np.column_stack((-u[:, 1], u[:, 0]))
    cos = radius / d
    radial = cos * u + (-1 if cross_pull else 1) * np.sqrt(1 - cos*cos) * perp
    # Intersect each smooth tangent bearing with the authored polygon, not an
    # ideal cylinder. This keeps contact continuous as the bearing crosses a facet.
    ring = ring[np.argsort(np.arctan2(ring[:, 1], ring[:, 0]))]
    edge = np.roll(ring, -1, axis=0) - ring
    normal = unit(np.c_[edge[:, 1], -edge[:, 0]])
    distance = 1 / np.max(np.einsum('ij,kj->ik', radial, normal) / (ring * normal).sum(1), axis=1)
    axial = np.sign(local_eye[:, 2]) * level * np.ptp(v[:, 2]) / .027 if cross_pull else np.zeros(len(eye))
    return np.einsum('ij,jk->ik', np.c_[distance[:, None] * radial, axial], basis) + m[3, :3]


def retarget(key, raw, rubber, crown):
    objects = {o['name']: o for o in raw['objects']}
    fly = key in FLY
    for side, wheel in ([('l', 'pulley.004'), ('r', 'pulley')] if fly else [('main', 'pulley.041')]):
        if key == 'rope_overhead_extension':
            clip = objects['rope_clip']
            v = np.asarray(clip['verts']).reshape(-1, 3)
            # The crown edge of the original one-piece snap hook, not its pivot.
            tip = v[np.isclose(v[:, 2], v[:, 2].max())].mean(0)
            m = matrices(clip)
            eye = np.einsum('j,ijk->ik', tip, m[:, :3, :3]) + m[:, 3, :3]
        else:
            def joint(i):
                return matrices(objects[f'carabiner_{side}_{i}'])[:, 3, :3]
            # The existing exterior maps catalogue z=+/-27 mm to joints 3/9.
            half = (joint(3) - joint(9)) / 2
            eye = joint(3) + half * (crown / .027 - 1)
        cable = objects['cable_out_' + side]
        v = np.asarray(cable['verts']).reshape(-1, 3)
        if not np.allclose(v.min(0), [-1, -1, 0]) or not np.allclose(v.max(0), [1, 1, 1]):
            raise ValueError(f'{key}: unexpected free-span mesh')
        if len(eye) != len(raw['acts']) or len(cable['m']) != len(eye):
            raise ValueError(f'{key}: stale eye or outgoing cable phase count')
        start = outlet(objects[wheel], rubber, eye, fly)
        span(cable, start, eye, radial=.0045)  # original 9 mm cable, local Z from 0 to 1


def apply(stage):
    def source(name):
        return json.loads((HERE / name).read_text())
    wheel = source('scene_cable_source.json')['pulley_wheel']
    rubber, = [np.asarray(layer['v']) for layer in wheel if layer['slot'] == 1]
    crown = np.max(np.asarray(source('scene_rest_cable_source.json')['carabiner_link_ring']['v'])[:, 2])
    for key in sorted(FLY | OVERHEAD):
        path = stage / 'data' / (key + '.json')
        raw = json.loads(path.read_text())
        retarget(key, raw, rubber, crown)
        path.write_text(json.dumps(raw, separators=(',', ':'), allow_nan=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', type=Path)
    apply(parser.parse_args().stage)
