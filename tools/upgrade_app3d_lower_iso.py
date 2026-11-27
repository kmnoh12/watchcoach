"""Append lower-machine exteriors to the fitted pad, tower and plate overlays."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER, infer_metal_preset
from upgrade_app3d_lower_towers import center, pose, vertices
from upgrade_app3d_rest_bars import check_round_target, round_parts as grip_parts
from upgrade_app3d_rest_cables import round_parts as cable_parts


TARGETS = 'lower_iso_targets.json'
SOURCE = 'scene_lower_iso_source.json'
REPORT = 'lower_iso_fit.json'
GRIPS = {'hand_grip', 'support_handle', 'upper_handle_bar'}
CAPS = {'handle_end_cap', 'pivot_cover', 'roller_end_cap'}
PLATES = {'footplate', 'step_platform'}
POSTS = {'frame_post', 'frame_leg', 'tower_post', 'tower_side_member', 'seat_post', 'pad_post'}
TIES = {'base_crossfoot', 'frame_crossbeam', 'frame_brace', 'frame_stay', 'top_beam', 'pad_crossbeam'}
FOOT = {'base_beam', 'frame_foot', 'frame_link', 'frame_rail', 'frame_spine'}
PANEL_TURN = Rotation.from_euler('z', 90, degrees=True)
PLATE_TURN = Rotation.from_euler('x', 90, degrees=True)
X_TO_Z = Rotation.from_euler('y', 90, degrees=True)
IDENTITY = Rotation.identity()


def stock_planes(v):
    return np.unique(ConvexHull(v).equations.round(10), axis=0)


def outline(v, planes):
    return float((np.einsum('vi,fi->vf', v, planes[:, :3]) + planes[:, 3]).max())


def orientation(role, group, size):
    if role == 'sign_panel' and size.argmin() == 0:
        return PANEL_TURN
    if group == 'footplate__003':
        return PLATE_TURN
    if group == 'footplate_tread__001' and size[0] < size[1]:
        return PANEL_TURN
    if role == 'handle_bridge' and group == 'handle_bridge__001':
        return X_TO_Z
    if role in POSTS and size[2] > max(size[0], size[1]) and size[1] < .15:
        return Rotation.from_euler('y', -90, degrees=True)
    return IDENTITY


def shell(role, source):
    if role in CAPS | {'sign_panel', 'rubber_foot'}:
        material = {
            'handle_end_cap': MAT_CHROME, 'roller_end_cap': MAT_CHROME, 'pivot_cover': MAT_FRAME,
            'sign_panel': MAT_FRAME, 'rubber_foot': MAT_RUBBER,
        }[role]
        return source[role], material
    if role in PLATES:
        return source['footplate'], MAT_FRAME
    if role == 'footplate_tread':
        return source['footplate_tread'], MAT_RUBBER
    if role in TIES:
        return source['frame_crossbeam'], None
    if role in FOOT:
        return source['frame_foot'], None
    if role in POSTS:
        return source['frame_post'], None
    if role in {'lever_arm', 'load_arm', 'lever_yoke', 'pad_arm'}:
        return source['lever_arm' if role != 'load_arm' else role], None
    if role == 'footplate_support':
        return source['footplate_support'], None
    return source['base_runner'], None


def shared_shells(source, models, targets):
    """Intersect the members' local envelopes in a common unit-size coordinate system.

    Preserve both the end planes and the welded face silhouette of the old
    chamfered tubes. Project the scene's corner samples only where a legacy
    chamfer is wider, so every instance uses the same catalogue mesh.
    """
    limits = {}
    for key, mapping in targets.items():
        for name, (index, group) in mapping.items():
            obj = models[key]['objects'][index]
            assert obj['name'] == name
            old = vertices(obj)
            role = group.split('__')[0]
            rot = orientation(role, group, np.ptp(old, axis=0))
            local = rot.inv().apply(old - center(old))
            limits.setdefault(group, []).append(stock_planes(local / np.ptp(local, axis=0)))
    out = {}
    for group, hulls in limits.items():
        role = group.split('__')[0]
        if role in GRIPS | {'cable_segment'} or group in {'handle_bridge__001', 'footplate_tread__002'}:
            continue
        scene, material = shell(role, source)
        v = np.array(scene['v'])
        dims = np.ptp(v, axis=0)
        planes = np.unique(np.vstack(hulls), axis=0)
        uvw = v / dims
        if role in PLATES | {'footplate_tread'}:
            # Inset the bevel within every horizontal section. The original
            # foot contact and the lower mounting plane keep their heights.
            lateral = np.linalg.norm(planes[:, :2], axis=1) > 1e-8
            allowance = np.maximum(0, -planes[lateral, 3] - uvw[:, 2, None] * planes[lateral, 2])
            distance = np.einsum('vi,fi->vf', uvw[:, :2], planes[lateral, :2])
            ratio = np.divide(allowance, distance, out=np.ones_like(distance), where=distance > 1e-10)
            fitted = v.copy()
            fitted[:, :2] *= ratio.min(1).clip(0, 1)[:, None]
        else:
            rho = np.einsum('vi,fi->vf', uvw, planes[:, :3]) / -planes[:, 3]
            fitted = v / np.maximum(1, rho.max(1))[:, None]
        out[group] = (dims, fitted, scene['t'], any(scene['smooth']), material, scene['rgb'])
    return out


def component(obj, group, source, shells):
    old = vertices(obj)
    role = group.split('__')[0]
    original_size = np.ptp(old, axis=0)
    rotation = orientation(role, group, original_size)
    origin = center(old)
    ref = rotation.inv().apply(old - origin)
    if role == 'cable_segment':
        factor, layers = cable_parts(group, old, source)
        return IDENTITY, np.zeros(3), factor, layers, True
    size = np.ptp(ref, axis=0)
    if role in GRIPS or group in {'handle_bridge__001', 'footplate_tread__002'}:
        sides = len(old) // 2
        check_round_target(obj['name'], ref, sides)
        material = MAT_CHROME if role in {'handle_bridge', 'upper_handle_bar'} else MAT_RUBBER
        donor = source['hand_grip']
        color = source['metal_grip' if material == MAT_CHROME else 'hand_grip']['rgb']
        dims, parts = grip_parts(donor, sides, material, True)
        return rotation, origin, size / dims, [(v, t, sm, m, color) for v, t, sm, m in parts], True
    dims, v, t, smooth, material, color = shells[group]
    if material is None:
        material = infer_metal_preset(obj['color'])
        # Preserve the original model's two-tone frame and moving-arm contrast.
        color = obj['color']
    elif role in PLATES or role == 'footplate_tread':
        material = MAT_RUBBER if max(obj['color']) < .25 else MAT_SILVER
        color = obj['color'] if material == MAT_SILVER else color
    return rotation, origin, size / dims, [(v, t, smooth, material, color)], False


def upgrade(view):
    targets = load(HERE / TARGETS)
    models = {key: load(view / 'data' / (key + '.json')) for key in targets}
    pull = load(HERE / 'scene_rest_pull_source.json')
    cable = load(HERE / 'scene_rest_cable_source.json')
    shared = {**pull, **load(HERE / SOURCE), 'metal_grip': cable['lat_bar'],
              'cable_segment': cable['cable_segment']}
    shells = shared_shells(shared, models, targets)

    def build(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3) or not np.isfinite(frames).all():
            raise ValueError('Missing final posed V6 body')
        rows, audit = [], {}
        for name, (index, group) in mapping.items():
            obj = raw['objects'][index]
            assert obj['name'] == name
            p, r, s = pose(obj)
            linear = r.as_matrix() * s[:, None, :]
            if not np.allclose(linear, np.asarray(obj['m'][:len(p)]).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1), atol=2e-5):
                raise ValueError(f'{name}: incompatible original transform')
            rot, c, scale, layers, locked = component(obj, group, shared, shells)
            old = vertices(obj)
            fitted = rot.apply(np.vstack([v * scale for v, *_ in layers])) + c
            outward = outline(fitted, stock_planes(old))
            inward = outline(old, stock_planes(fitted)) if locked else 0
            if outward > .000015 or inward > .000015:
                raise ValueError(f'{name}: exterior leaves the original envelope or changes a contact plane')
            if len(p) > 1 and abs(c).max() > .000015:
                raise ValueError(f'{name}: moving part would require changing the pivot')
            axis_order = abs(rot.as_matrix()).argmax(0)
            for v, t, smooth, material, color in layers:
                rows.append(dict(name=name, verts=v, tris=np.ravel(t), pos=p + (linear @ c),
                                 quats=(r * rot).as_quat(), sc=s[:, axis_order] * scale,
                                 smooth=smooth, mat=material, color=color))
            audit[name] = dict(group=group, records=len(layers), poses=len(p),
                               locked=locked, max_outward_mm=round(1000 * max(0, outward), 6))
        return rows, audit

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE, report_file=REPORT, build_model=build)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer', type=Path)
    upgrade(parser.parse_args().viewer)
