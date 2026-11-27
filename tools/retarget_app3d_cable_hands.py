"""Retarget six reviewed phone towers AFTER new-hand conversion, BEFORE exterior packing.

The desktop and phone assemblies are not slot-compatible. Only named world-space
landmarks are shared. Regenerate the small tracked input with --extract <equipment-dir>.
Neither the desktop machine geometry nor a replacement hand animation is shipped.
"""
import argparse
import json
from pathlib import Path
import re

import numpy as np
from scipy.spatial.transform import Rotation

SOURCE = Path(__file__).resolve().parent / 'viewer3d/cable_hand_landmarks.json'
KEYS = ['cable_tower~' + s for s in ('h=high~g=rope~p=down', 'h=low~g=d~p=kick',
        'h=low~g=d~p=row_floor', 'h=low~g=d~p=up', 'h=low~g=rope~p=up', 'h=low~g=straight~p=up')]


def ends(obj, axis=2):
    v = np.asarray(obj['verts']).reshape(-1, 3)[:, axis]
    m = np.asarray(obj['m']).reshape(-1, 4, 4)
    return tuple(m[:, 3, :3] + t * m[:, axis, :3] for t in (v.min(), v.max()))


def extract(folder):
    result = {}
    for k in KEYS:
        raw = json.loads((folder / (k + '.json')).read_text())
        ob = {o['name']: o for o in raw['objects']}
        row = k.endswith('p=row_floor')
        axle, eye = ends(ob['cable.003' if row else 'cable_out_main'], 1 if row else 2)
        pts = dict(eye=eye)
        if '~g=rope~' in k:
            for side in 'lr':
                pts['start_' + side], pts['tip_' + side] = ends(ob['rope_grip_' + side])
                pts['bend_' + side] = ends(ob['rope_link2_' + side])[0]
                start, tip = ends(ob['rope_stop_' + side])
                pts['stop_dir_' + side] = tip - start
        else:
            pts['start'], pts['tip'] = ends(ob['grip' if row else 'bar_main' if '~g=straight~' in k else 'grip_main'])
        if not np.allclose(axle, axle[0]) or any(len(p) != len(raw['acts']) for p in pts.values()):
            raise ValueError(f'{k}: expected stationary outlet and one landmark per desktop phase')
        result[k] = dict(acts=raw['acts'], axle=axle[0].tolist(), points={n: p.round(6).tolist() for n, p in pts.items()})
    # Keep each point on its own line for small, reviewable regeneration diffs.
    encoded = json.dumps(result, indent=2, allow_nan=False)
    numeric_list = re.compile(r'\[\s*([-\d.,eE+\s]+)\]')
    encoded = numeric_list.sub(lambda m: '[' + ' '.join(m[1].split()) + ']', encoded)
    SOURCE.write_text(encoded + chr(10), encoding='utf-8')


def length(v):
    return np.linalg.norm(v, axis=-1, keepdims=True)


def unit(v):
    d = length(v)
    if not np.isfinite(d).all() or d.min() < 1e-6:
        raise ValueError('Degenerate cable landmark')
    return v / d


def set_matrix(obj, basis, origin):
    m = np.broadcast_to(np.eye(4), (len(origin), 4, 4)).copy()
    m[:, :3, :3] = basis
    m[:, 3, :3] = origin
    obj['m'] = m.reshape(-1, 16).round(8).tolist()


def span(obj, start, tip, axis=2, radial=1., hint=None):
    """Place both native end planes, retaining radius and the object's own pivot."""
    direction = unit(tip - start)
    if hint is None:
        # One roll reference for the entire track; never switch axes between poses.
        hint = np.eye(3)[np.abs(direction).max(axis=0).argmin()]
    x = unit(hint - (hint * direction).sum(axis=1, keepdims=True) * direction)
    if axis == 2:
        axes = [x, np.cross(direction, x), direction]
    else:
        axes = [x, direction, np.cross(x, direction)]
    v = np.asarray(obj['verts']).reshape(-1, 3)[:, axis]
    basis = np.stack(axes, axis=1) * radial
    basis[:, axis] = (tip - start) / np.ptp(v)
    set_matrix(obj, basis, start - basis[:, axis] * v.min())


def retarget(k, raw, ref):
    # Keep BOTH clocks: phone equipment keys (25) and the untouched human keys (65).
    t, times = raw['acts'], ref['acts']
    if t[0] != times[0] or t[-1] != times[-1] or min(np.diff(times)) <= 0 or min(np.diff(t)) <= 0:
        raise ValueError(f'{k}: incompatible phase domain')
    p = {n: np.column_stack([np.interp(t, times, col) for col in np.asarray(a).T]) for n, a in ref['points'].items()}
    ob = {o['name']: o for o in raw['objects']}
    axle = np.array(ob['pulley.007']['m'][0][12:15])
    eye = p['eye']
    if np.linalg.norm(axle - ref['axle']) >= .001:
        raise ValueError(f'{k}: outlet registration changed')
    if '~g=rope~' in k:
        # The native Y has one rigid cord per hand; a bent rope cannot be both
        # taut at the saddle and tangent to the curled fingers with a single TRS.
        # Keep the indexed cord as the hand-contact sleeve. Append its two upper
        # spans after ALL original slots, reusing its mesh (no PC tower or slot swap).
        toward = unit(axle - eye)
        shoulder = eye - .060 * toward
        across = unit(p['start_r'] - p['start_l'])
        span(ob['rope_block'], shoulder, eye, hint=across)
        for side, cord, stop, sign in [('l', 'rope.002', 'rope_stop', -1), ('r', 'rope.003', 'rope_stop.001', 1)]:
            start, tip, bend = (p[n + '_' + side] for n in ('start', 'tip', 'bend'))
            root = shoulder + sign * .016 * across
            for label, a, b in [('lead', root, bend), ('bend', bend, start)]:
                name = 'upper_rope_' + label + '_' + side
                if name in ob:
                    raise ValueError(f'{k}: retargeting requires the fresh hand-conversion stage')
                extra = dict(ob[cord], name=name)
                span(extra, a, b, radial=.014/.017)
                raw['objects'].append(extra)
                # The appended runtime mesh is made of triangles, not Blender polygons.
                raw['faces'] += len(extra['tris']) // 3
            span(ob[cord], start, tip, radial=.014/.017)
            # The rubber stop starts at the tail, not at the centre of the hand.
            span(ob[stop], tip, tip + .036 * unit(p['stop_dir_' + side]), radial=.029/.032)
    else:
        start, tip = p['start'], p['tip']
        if '~g=d~' in k:
            span(ob['grip.011'], start, tip)
            span(ob['handle_link.004'], eye, start)
            span(ob['handle_link.005'], eye, tip)
        else:
            span(ob['bar.005'], start, tip)
            span(ob['handle_stem'], eye, (start + tip) / 2)
    span(ob['cable.025'], axle, eye, axis=1)
    payout = length(eye - axle)[:, 0]
    # Direct 1:1 reeving. The minimum free span is the resting stack height,
    # not necessarily phase zero (front raises briefly move toward the outlet).
    lift = payout - payout.min()
    stack = ob['cable.022']
    low, high = ends(stack, axis=1)
    dz = lift[:, None] * [0, 0, 1]
    span(stack, low[0] + dz, np.broadcast_to(high[0], dz.shape), axis=1)
    for name, obj in ob.items():
        if name.startswith(('selected_plate.', 'selector_pin.', 'selector_pin_knob.', 'selector_rod.')):
            rest = np.asarray(obj['m'][0]).reshape(4, 4)
            set_matrix(obj, rest[:3, :3], rest[3, :3] + dz)
    for name, sign in [('pulley.007', -1), ('pulley.008', 1), ('pulley.009', 1)]:
        wheel = ob[name]
        rest = np.asarray(wheel['m'][0]).reshape(4, 4)
        radius = np.linalg.norm(np.asarray(wheel['verts']).reshape(-1, 3)[:, :2], axis=1).max()
        spin = Rotation.from_euler('z', sign * (payout - payout[0]) / radius).as_matrix()
        set_matrix(wheel, spin.transpose(0, 2, 1) @ rest[:3, :3], np.broadcast_to(rest[3, :3], dz.shape))


def apply(view):
    refs = json.loads(SOURCE.read_text())
    for k in KEYS:
        path = view / 'data' / (k + '.json')
        raw = json.loads(path.read_text())
        retarget(k, raw, refs[k])
        path.write_text(json.dumps(raw, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--extract', type=Path)
    mode.add_argument('--stage', type=Path)
    args = parser.parse_args()
    if args.extract:
        extract(args.extract)
    else:
        apply(args.stage)
