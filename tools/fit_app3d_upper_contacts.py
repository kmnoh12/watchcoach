"""Register six reviewed upper-body contacts on the completed V5/new-hand viewer stage."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from build_v5_hand_viewer_copy import rigid
from check_app3d_stage1 import read_clip, read_parts
from fit_app3d_dumbbell_contacts import reach, swing_segment
from fit_app3d_lower_contacts import mats, move, save_mats, store_skin, translate_record, weights, wgm_offsets, world
from upgrade_app3d_machines import load_wgp2_human_frames

SEAL = 'seal_row'
SPIDER = 'spider_curl'
PREACHER = 'single_arm_dumbbell_preacher_curl'
ROW = 'chest_supported_dumbbell_row'
SINGLE = 'single_arm_' + ROW
KICK = 'glute_kickback_machine'
KEYS = (SEAL, SPIDER, PREACHER, ROW, SINGLE, KICK)
# Joint heads on the 1401-vertex V5 rig (metres, mirror x for the right arm).
REST = {'spine_01': [0, -.05, 1.07], 'upperarm': [.155232, -.05, 1.38],
        'lowerarm': [.342427, -.07, 1.10], 'hand': [.47, -.19, .89]}


def joint(base, skin, bone, side=None):
    w = weights(base, [bone + '_' + side if side else bone])
    ix = w >= w.max() - .005
    r, t = rigid(np.reshape(base['rest'], (-1, 3))[ix], skin[:, ix])
    head = np.array(REST[bone]) * [-1 if side == 'r' else 1, 1, 1]
    return np.einsum('i,fij->fj', head, r) + t


def arm(base, skin, side):
    names = [b for b in base['bone_names'] if b.endswith('_' + side) and
             b.split('_')[0] in ('hand', 'index', 'middle', 'pinky', 'ring', 'thumb')]
    return ([joint(base, skin, b, side) for b in ('upperarm', 'lowerarm', 'hand')],
            [weights(base, group)[None, :, None] for group in
             (['upperarm_' + side], ['lowerarm_' + side], names)])


def turn(skin, centre, rotation, to):
    return np.einsum('fvi,fji->fvj', skin - centre[:, None], rotation) + to[:, None]


def straddle_preacher_post(base, skin, deg=10.0):
    """Open both legs slightly around the vertical hip axes so thighs clear the center pad post."""
    rest = np.reshape(base['rest'], (-1, 3))
    wp = weights(base, ['pelvis'])
    posed = skin.copy()
    for side, sign in [('l', 1), ('r', -1)]:
        wt = weights(base, ['thigh_' + side])
        wleg = weights(base, [b + '_' + side for b in ('thigh', 'calf', 'foot', 'ball')
                              if b + '_' + side in base['bone_names']])
        pure = wt >= wt.max() - .005
        r, t = rigid(rest[pure], skin[:, pure])
        hip_rest = rest[(wp > .1) & (wt > .1)].mean(0)
        hip = np.einsum('i,fij->fj', hip_rest, r) + t
        rot = Rotation.from_euler('z', sign * deg, degrees=True).as_matrix()
        posed += (((skin - hip[:, None]) @ rot.T + hip[:, None]) - skin) * wleg[None, :, None]
    return posed


def rest_hand(base, skin, delta):
    (s, e, w), (upper, lower, hand) = arm(base, skin, 'l')
    en, ru, rl = reach(s, e, w, w + delta)
    return skin + upper*(turn(skin, s, ru, s)-skin) + lower*(turn(skin, e, rl, en)-skin) + hand*delta


def brace_kickback(base, skin):
    # Less flexion at the lumbar joint: the sternum bears against the chest pad,
    # not the neck. Keep the hip/leg tracks and gripping hands entirely fixed.
    c = joint(base, skin, 'spine_01')
    rot = Rotation.from_euler('x', -7.0, degrees=True).as_matrix()
    spine = ('spine_01', 'spine_02', 'spine_03', 'clavicle_l', 'clavicle_r', 'neck_01', 'head')
    posed = skin + (turn(skin, c, rot[None], c)-skin)*weights(base, spine)[None, :, None]
    for side, sign in [('l', 1), ('r', -1)]:
        (s, e, w), (upper, lower, _) = arm(base, skin, side)
        sn = (s-c) @ rot.T + c
        # Two rigid links to the stationary palm. Choose the solution nearest
        # the old elbow, biased towards its own forearm rest, not the chest pad.
        axis = w-sn
        d = np.linalg.norm(axis, axis=1, keepdims=True)
        axis = axis/d
        l2 = np.sum((e-s)**2, axis=1, keepdims=True)
        along = (d*d + l2 - np.sum((w-e)**2, axis=1, keepdims=True))/(2*d)
        radius = l2-along*along
        if (radius <= 0).any():
            raise ValueError('Kickback hand beyond reach')
        pole = e-sn + [sign*.015, 0., 0.]
        pole -= axis*np.sum(pole*axis, axis=1, keepdims=True)
        en = sn + along*axis + np.sqrt(radius)*pole/np.linalg.norm(pole, axis=1, keepdims=True)
        posed += upper*(turn(skin, s, swing_segment(e-s, en-sn), sn)-skin)
        posed += lower*(turn(skin, e, swing_segment(w-e, w-en), en)-skin)
    return posed


def seat_chest_pad(raw, wp, parts):
    # The old pad's rear-face normal was mirrored in Z relative to its fixed
    # mounting stalk. Square both layers to the stalk, then seat the rear face
    # on the actual (chamfered) end; do not extend a rail or relocate the post.
    objs = {o['name']: o for o in raw['objects']}
    pad, mount = objs['chest_pad'], objs['chest_mount']
    m = mats(pad)
    c, old = m[0, 3, :3].copy(), m[0, 1, :3].copy()
    normal = mats(mount)[0, 0, :3]
    normal = normal / np.linalg.norm(normal)
    r = Rotation.from_matrix(swing_segment(old[None], normal[None])[0])
    _, rows = read_clip(wp, parts)
    cushion, trim, post = [rows[i] for i in (40, 41, 58)]
    def bounds(vertices):
        return np.array([vertices.min(0), vertices.max(0)])
    if (any(row['nf'] != 1 for row in (cushion, trim, post)) or
            any(not np.allclose(bounds(row['world'][0]), bounds(world(obj)[0]), atol=.015)
                for row, obj in ((cushion, pad), (trim, pad), (post, mount)))):
        raise ValueError('Expected the static kickback chest cushion, trim and stalk')
    rear = np.min((r.apply(cushion['world'][0]-c)+c) @ normal)
    delta = normal*(np.max(post['world'][0] @ normal)-rear-.002)
    blob = bytearray(wp.read_bytes())
    offsets = wgm_offsets(blob)
    for slot in (40, 41):
        pose = np.frombuffer(blob, '<f4', 7, offsets[slot]+10)
        pose[:3] = r.apply(pose[:3]-c)+c+delta
        pose[3:] = (r*Rotation.from_quat(pose[3:])).as_quat()
    wp.write_bytes(blob)
    m[0, 3, :3] = c+delta
    m[0, :3, :3] = m[0, :3, :3] @ r.as_matrix().T
    save_mats(pad, m)


def curl_lane(sign):
    return np.array([sign*.145, -.015, .040])


def open_curl_lanes(base, skin):
    # Translate each entire dumbbell stroke intact. Two rigid arm links reach
    # the same grasp in the wider lane; roll the elbow away from the pad edge.
    posed = skin.copy()
    for side, sign in [('l', 1), ('r', -1)]:
        (s, e, w), (upper, lower, hand) = arm(base, skin, side)
        delta = curl_lane(sign)
        target = w + delta
        en, _, _ = reach(s, e, w, target)
        axis = target-s
        axis /= np.linalg.norm(axis, axis=1, keepdims=True)
        en = s + Rotation.from_rotvec(axis*np.deg2rad(sign*55)).apply(en-s)
        posed += upper*(turn(skin, s, swing_segment(e-s, en-s), s)-skin)
        posed += lower*(turn(skin, e, swing_segment(w-e, target-en), en)-skin) + hand*delta
    return posed


def register_bench(key, raw, wp, parts, base, skin):
    acts, rows = read_clip(wp, parts)
    if not np.array_equal(acts, np.asarray(raw['acts'], '<f4')):
        raise ValueError(f'{key}: expected matching equipment times')
    # These four clips contain only the static bench and the animated free weights.
    # Guard both partitions, including the plate/detail overlays and raw fallback.
    expected = {SEAL: (13, 9, 13, 14), SPIDER: (21, 6, 4, 6),
                ROW: (13, 10, 15, 10), SINGLE: (15, 5, 17, 5)}[key]
    objs = raw['objects']
    row_weights = {'contoured_chrome_grip', 'neck', 'rubber_hex_head'}
    loads = {SEAL: {'bumper', 'collar', 'hub', 'shaft', 'sleeve'},
             SPIDER: {'dumbbell_head', 'handle'}, ROW: row_weights, SINGLE: row_weights}
    if {o['name'].split('.')[0] for o in objs if len(o['m']) > 1} != loads[key]:
        raise ValueError(f'{key}: unrecognised free weights')
    lengths = ([len(o['m']) for o in objs], [r['nf'] for r in rows])
    if tuple(x.count(n) for x in lengths for n in [1, len(acts)]) != expected or any(
            set(x) != {1, len(acts)} for x in lengths):
        raise ValueError(f'{key}: unrecognised bench/weight partition')
    delta = np.array([0., {SEAL: .59, SPIDER: -.045, ROW: -.099, SINGLE: -.099}[key], 0.])
    lift = np.array([0., 0., .063])
    posed = skin.copy()
    if key == SPIDER:
        posed = open_curl_lanes(base, skin)
    elif key == SINGLE:
        posed = rest_hand(base, skin, delta)  # support handle is on the moving bench
    elif key == SEAL:
        posed += lift
    for o in objs:
        if len(o['m']) == 1:
            move(o, delta)
        elif key == SEAL:
            move(o, lift)
        elif key == SPIDER:
            move(o, curl_lane(np.sign(mats(o)[0, 3, 0])))
    blob = bytearray(wp.read_bytes())
    offsets = wgm_offsets(blob)
    for i, row in enumerate(rows):
        if row['nf'] == 1:
            translate_record(blob, offsets, i, delta)
        elif key == SEAL:
            translate_record(blob, offsets, i, lift)
        elif key == SPIDER:
            translate_record(blob, offsets, i, curl_lane(np.sign(row['pos'][0, 0])))
    wp.write_bytes(blob)
    return posed


def apply(view, keys=KEYS):
    data, human = view/'data', view/'human_v5'
    base = json.loads((human/'base.json').read_text())
    if base['vertices'] != 1401 or not (human/'watch.json').is_file():
        raise ValueError('Requires the completed new-hand stage')
    parts = read_parts(data/'parts.bin')
    for key in keys:
        hp = human/(key+'.bin')
        skin = load_wgp2_human_frames(hp).astype(float)
        times = np.frombuffer(hp.read_bytes(), '<f4', len(skin), 40)
        if key == PREACHER:
            # Rest the inactive hand on the OUTSIDE top corner, not beneath the cushion,
            # and open the knees slightly so both thighs straddle the center pad post cleanly.
            posed = straddle_preacher_post(base, rest_hand(base, skin, np.array([.10, .07, .189])))
        else:
            path = data/(key+'.json')
            raw = json.loads(path.read_text())
            wp = data/(key+'.wgm')
            if key == KICK:
                seat_chest_pad(raw, wp, parts)
                posed = brace_kickback(base, skin)
            else:
                posed = register_bench(key, raw, wp, parts, base, skin)
            path.write_text(json.dumps(raw, separators=(',', ':'), allow_nan=False))
        if not np.isfinite(posed).all():
            raise ValueError(f'{key}: invalid posed vertices')
        if key != ROW:
            store_skin(hp, posed, times)
        print(key, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('view', type=Path)
    parser.add_argument('--keys', nargs='+', choices=KEYS, default=KEYS)
    args = parser.parse_args()
    apply(args.view, args.keys)
