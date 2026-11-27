"""Append gym chest-press exteriors after the fitted pads and selector stations."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from part_registry import MAT_ACCENT, MAT_FRAME, MAT_RUBBER, MAT_SILVER
from upgrade_app3d_lower_iso import outline, stock_planes
from upgrade_app3d_lower_towers import center, pose, vertices
from upgrade_app3d_rest_bars import check_round_target, round_parts as grip_parts
from upgrade_app3d_rest_cables import round_parts as cable_parts


TARGETS = 'chest_press_rest_targets.json'
SOURCE = 'scene_chest_press_rest_source.json'
REPORT = 'chest_press_rest_fit.json'
DONORS = {
    'base_beam': 'base_runner', 'frame_foot': 'base_runner',
    'frame_post': 'pad_support', 'frame_spine': 'base_runner',
    'pad_mount': 'frame_crossbeam', 'pad_post': 'pad_support', 'pad_rail': 'base_runner',
    'roller_support': 'pad_support', 'spine_mount': 'frame_crossbeam',
    'tower_side_member': 'pad_support',
}
LOCKED = {'hand_grip', 'footplate', 'cable_segment'}


def layer(part, material, vertices=None):
    return (np.asarray(part['v']) if vertices is None else vertices,
            np.ravel(part['t']), any(part['smooth']), material, part['rgb'])


def panel_layers(parts):
    # Position the printed diagram on the user-facing side of the original panel.
    # Adapt the backing to the panel height and keep the diagram and type proportional.
    backing = np.asarray(parts[0]['v'])
    origin = center(backing)
    size = np.ptp(backing, axis=0)
    half_depth = size[1] / 2
    shell = (backing - origin) * [1, .82, 1] + [0, .18 * half_depth, 0]
    face = -.64 * half_depth
    result = [layer(parts[0], MAT_RUBBER, shell)]
    art_scale = .300 / size[0] / (.220 / size[2])
    for part in parts[1:]:
        art = (np.asarray(part['v']) - origin) * [1, .4, art_scale]
        art[:, 1] += face + .4 * half_depth
        mat = MAT_ACCENT if part['rgb'][0] > .9 else MAT_FRAME
        result.append(layer(part, mat, art))
    return size, result


def shared_shapes(models, targets, source):
    """Use one local shape per group, inset within every original joint profile."""
    bounds = {}
    for key, mapping in targets.items():
        for name, (index, group) in mapping.items():
            role = group.split('__')[0]
            if role in LOCKED or role == 'sign_panel':
                continue
            obj = models[key]['objects'][index]
            assert obj['name'] == name
            v = vertices(obj)
            bounds.setdefault(group, []).append(stock_planes((v - center(v)) / np.ptp(v, axis=0)))

    shapes = {}
    for group, limits in bounds.items():
        role = group.split('__')[0]
        part = source[DONORS.get(role, role)]
        v = np.asarray(part['v'])
        size = np.ptp(v, axis=0)
        local = v - center(v)
        planes = np.unique(np.vstack(limits), axis=0)
        rho = np.einsum('vi,fi->vf', local / size, planes[:, :3]) / -planes[:, 3]
        fitted = local / np.maximum(1., rho.max(1))[:, None]
        mat = MAT_RUBBER if role == 'rubber_foot' else MAT_FRAME
        shapes[group] = size, [layer(part, mat, fitted)]
    return shapes


def build_part(group, original, source, shapes):
    role = group.split('__')[0]
    origin = center(original)
    if role == 'cable_segment':
        scale, parts = cable_parts(group, original, source)
        return np.zeros(3), scale, parts
    if role in {'hand_grip', 'footplate'}:
        ref = original - origin
        check_round_target(role, ref, len(ref) // 2)
        donor = source[role]
        material = MAT_RUBBER if role == 'hand_grip' else MAT_SILVER
        size, pieces = grip_parts(donor, len(ref) // 2, material, True)
        parts = [(v, t, smooth, mat, donor['rgb']) for v, t, smooth, mat in pieces]
    elif role == 'sign_panel':
        size, parts = panel_layers(source[role])
    else:
        size, parts = shapes[group]
    return origin, np.ptp(original, axis=0) / size, parts


def upgrade(view):
    targets = load(HERE / TARGETS)
    models = {key: load(view / 'data' / (key + '.json')) for key in targets}
    cable = load(HERE / 'scene_rest_cable_source.json')
    pulls = load(HERE / 'scene_rest_pull_source.json')
    lower = load(HERE / 'scene_lower_iso_source.json')
    shared = {**pulls, **load(HERE / SOURCE), 'hand_grip': lower['hand_grip'],
              'cable_segment': cable['cable_segment']}
    shapes = shared_shapes(models, targets, shared)

    def build(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3) or not np.isfinite(frames).all():
            raise ValueError('Missing final posed body')
        rows, audit = [], {}
        for name, (index, group) in mapping.items():
            obj = raw['objects'][index]
            assert obj['name'] == name
            old = vertices(obj)
            p, r, s = pose(obj)
            linear = r.as_matrix() * s[:, None, :]
            stock = np.asarray(obj['m'][:len(p)]).reshape(-1, 4, 4)
            if not np.allclose(linear, stock[:, :3, :3].transpose(0, 2, 1), atol=2e-5):
                raise ValueError(f'{name}: incompatible original transform')
            origin, scale, parts = build_part(group, old, shared, shapes)
            fitted = np.vstack([v * scale for v, *_ in parts]) + origin
            role = group.split('__')[0]
            locked = role in LOCKED
            outward = outline(fitted, stock_planes(old))
            inward = outline(old, stock_planes(fitted)) if locked else 0.
            if outward > .000015 or inward > .000015:
                raise ValueError(f'{name}: changes the original envelope or contact planes')
            if len(p) > 1 and abs(origin).max() > .000015:
                raise ValueError(f'{name}: moving part would change its local pivot')
            for v, t, smooth, mat, color in parts:
                rows.append(dict(name=name, verts=v, tris=t, pos=p + linear @ origin,
                                 quats=r.as_quat(), sc=s * scale, smooth=smooth, mat=mat, color=color))
            audit[name] = dict(group=group, records=len(parts), poses=len(p), locked=locked,
                               max_outward_mm=round(1000 * max(0., outward), 6))
        return rows, audit

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE,
                        report_file=REPORT, build_model=build)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer', type=Path)
    upgrade(parser.parse_args().viewer)
