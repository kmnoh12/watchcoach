"""Only the round_plate rows from the reviewed role map. Retain the original JSON for every other part."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation

from part_registry import MAT_CHROME, MAT_PLATE_FACE

HERE = Path(__file__).resolve().parent


def fit(obj, source):
    verts = np.asarray(obj['verts']).reshape(-1, 3)
    m = np.asarray(obj['m']).reshape(-1, 4, 4)
    if np.max(np.abs(m - m[0])) < 1e-5:
        m = m[:1]
    basis = m[:, :3, :3]
    scales = np.linalg.norm(basis, axis=2)
    axes = basis / scales[:, :, None]
    assert np.allclose(scales, scales[0], atol=.0001) and np.allclose(axes @ axes.transpose(0,2,1), np.eye(3), atol=.0001)
    center = (verts.min(0) + verts.max(0)) / 2
    extent = np.ptp(verts, axis=0) * scales[0]
    axle = np.argmin(extent)
    radial = [i for i in range(3) if i != axle]
    diameter = 2 * np.linalg.norm(((verts - center) * scales[0])[:, radial], axis=1).max()
    thick = extent[axle]
    def score(key):
        v, hub = source[key]
        dia = np.ptp(v['v'], axis=0)[0]; width = np.ptp(hub['v'], axis=0)[2]
        return (round(abs(dia - diameter), 4), abs(width * diameter / dia - thick))
    keys = source.keys()
    if '20kg' in obj['name'] or '45lb' in obj['name']:
        keys = ['b20','i20']
    elif 'with_bore' in obj['name']:
        # This is a pinch grip on two touching thin plates. Use the narrow bumper,
        # not the smaller-diameter but proportionally much thicker iron casting.
        keys = ['b5']
    elif 'light_back_plate' in obj['name']:
        keys = ['b5']  # the machine's contrasting light/grey auxiliary plate
    key = min(keys, key=score)
    factor = diameter / np.ptp(source[key][0]['v'], axis=0)[0]
    # Uniform scale, including the hub. Place the label upright in the initial
    # pose, then follow ALL the original rotations rather than facing the camera.
    normal = axes[0, axle]
    up = np.array([0., 0., 1.]); up -= np.dot(up, normal) * normal
    if np.linalg.norm(up) < .001:
        up = axes[0, radial[1]]
    up /= np.linalg.norm(up)
    frame = np.column_stack([np.cross(up, normal), up, normal])
    local = axes[0] @ frame
    q = Rotation.from_matrix(axes.transpose(0,2,1) @ local).as_quat()
    for i in range(1,len(q)):
        if np.dot(q[i-1], q[i]) < 0:
            q[i] *= -1
    return key, center @ basis + m[:, 3, :3], q, np.full((len(m),3), factor)


def build_overlays(data_dir, packer, pack_clip):
    targets = json.loads((HERE/'plate_targets.json').read_text())
    source = json.loads((HERE/'scene_plate_source.json').read_text())
    clips = {}
    for model, targets_by_index in targets.items():
        raw = json.loads((data_dir/f'{model}.json').read_text()); entries = []
        for idx, name in targets_by_index.items():
            obj = raw['objects'][int(idx)]
            assert obj['name'] == name, f'{model}: plate target changed at {idx}'
            key, pos, quats, sc = fit(obj, source)
            for slot, part in enumerate(source[key]):
                pid = packer.add(part['v'], part['t'], True, uv=part['uv'] if slot == 0 else None)
                entries.append(dict(name=name, part_id=pid, tris=part['t'], pos=pos, quats=quats, sc=sc,
                                    mat=MAT_CHROME if slot else MAT_PLATE_FACE, smooth=True,
                                    color=[.86,.87,.88] if slot else [1,1,1]))
        clips[model], _, _ = pack_clip(model, raw['acts'], entries)
    with Image.open(HERE.parents[1]/'promo/parts/detail_gym_freeweight/plate_faces.png') as image:
        image.save(data_dir/'plate_faces.webp', 'WEBP', lossless=True, method=4)
    print(f'Plate overlays: {len(clips)} clips, {sum(map(len,targets.values()))} plates')
    return targets, clips
