"""Check the seven *installed* WGM2 clips against the original hand-adjusted JSONs.

python3 tools/check_app3d_stage1.py [phone/src/main/assets/viewer3d]
The independent wire reader checks geometry and motion after both quantizers, not just input meshes.
"""
import io
import json
from collections import defaultdict
from pathlib import Path
import struct
import sys
import zlib

import numpy as np
from scipy.spatial.transform import Rotation

import upgrade_app3d_machines as build
from part_registry import MAT_ACRYLIC, MAT_FRAME, MAT_LAT_STACK_LABEL, MAT_SELECTOR_WINDOW, classify_object
from lat_stack_labels import atlas, load_numbers
from body_fit import SkinSweep, contact_region, surface_peak


def read(f, fmt):
    return struct.unpack(fmt, f.read(struct.calcsize(fmt)))


def array(f, dtype, shape):
    n = int(np.prod(shape))
    return np.frombuffer(f.read(n * np.dtype(dtype).itemsize), dtype=dtype).reshape(shape)


def read_parts(path, *, uvs=None):
    f = io.BytesIO(path.read_bytes()); magic, count = read(f, '<4sI')
    assert magic == b'WGC2'
    parts = []
    for _ in range(count):
        nv, nt, _flags = read(f, '<HHB3x')
        lo, scale = array(f, '<f4', (2, 3)).astype(float)
        v = lo + array(f, '<u2', (nv, 3))*scale
        triangles = array(f, '<u2', (nt, 3)); assert triangles.max() < nv
        uv = array(f, '<u2', (nv, 2)) if _flags & 2 else None
        if uvs is not None:
            uvs.append(uv)
        parts.append((v, triangles))
    assert not f.read(1)
    return parts


def read_clip(path, parts):
    f = io.BytesIO(path.read_bytes()); magic, n, count = read(f, '<4sHH')
    assert magic == b'WGM2'
    acts = array(f, '<f4', (n,)); rows = []
    for _ in range(count):
        pid, r, g, b, mat, flags, nf = read(f, '<H3BBBxH')
        first = array(f, '<f4', (10,)).astype(float)
        def track(start, step, variable):
            t = np.broadcast_to(start, (nf, len(start))).copy()
            if nf > 1 and variable:
                t[1:] += array(f, '<i2', (nf-1, len(start))).cumsum(0)*step
            return t
        pos = track(first[:3], .0001, True)
        quat = track(first[3:7], 1/32767, not flags & 2)
        scale = track(first[7:], .0001, not flags & 1)
        v, faces = parts[pid]
        linear = Rotation.from_quat(quat).as_matrix()*scale[:,None,:]
        world = v @ linear.transpose(0,2,1) + pos[:,None,:]
        rows.append(dict(pid=pid, rgb=(r,g,b), mat=mat, nf=nf, pos=pos, quat=quat, scale=scale, faces=faces, world=world))
    assert not f.read(1)
    return acts, rows


def original(obj):
    m = np.asarray(obj['m']).reshape(-1,4,4)
    return np.asarray(obj['verts']).reshape(-1,3) @ m[:,:3,:3] + m[:,None,3,:3]


def check(directory):
    data, humans = directory/'data', directory/'human_v5'
    manifest = json.loads((data/'wgm_manifest.json').read_text())
    assert set(manifest['clips']) - set(manifest.get('plateOverlays', {})) - set(manifest.get('machineOverlays', {})) == set(build.STAGE1)
    assert (data/'lat_stack_labels.svg').read_text() == atlas()[0]
    assert load_numbers(13) == ('2.5', '6') and load_numbers(-14) == ('137.5', '303')
    parts = read_parts(data/'parts.bin'); names = build.PartCatalogPacker(); common = None
    base = json.loads((humans/'base.json').read_text()); assert base['vertices'] == 1401
    human_faces = np.asarray(base['triangles']).reshape(-1,3)
    thigh_faces, _ = contact_region(base, 'thigh_roller')
    failures = []
    for key in build.STAGE1:
        raw = json.loads((data/f'{key}.json').read_text()); hb = humans/f'{key}.bin'
        human = build.load_wgp2_human_frames(hb); audit = []
        # Recover names only; all measurements below use bytes read back from the viewer directory.
        build.upgrade_machine(key, raw, names, human, human_faces, audit, human_base=base)
        sweep = SkinSweep(human, human_faces)
        acts, rows = read_clip(data/f'{key}.wgm', parts)
        assert np.array_equal(acts, np.asarray(raw['acts'], dtype='<f4'))
        assert np.array_equal(acts, np.frombuffer(hb.read_bytes(), '<f4', len(acts), 40))
        assert len(acts) == len(human) and len(rows) == len(audit)
        by = defaultdict(list); shared = []; grip = surface = 0.; n_grips = 0
        for e, row in zip(audit, rows):
            assert row['pid'] == e['part_id']; by[e['name']].append(row)
            if e['role'] == 'STATION': shared.append((e['name'], row['pid'], row['rgb'], row['mat']))
            if e['role'] == 'BODY_FIT':
                assert row['nf'] == 1
                if not sweep.clear(row['world'][0]): failures.append((key,e['name']))
        assert common is None or shared == common; common = shared
        tris = sum(len(row['faces']) for row in rows)
        static = {(e['smooth'], r['mat'], r['rgb']) for e, r in zip(audit, rows) if r['nf']==1}
        moving = [(r['pid'], r['mat'], r['rgb']) if r['mat'] not in (MAT_ACRYLIC, MAT_SELECTOR_WINDOW)
                  and np.all(r['scale'] > 0) else (i,) for i, r in enumerate(rows) if r['nf']>1]
        groups = len(static) + len(set(moving))
        for o in raw['objects']:
            name = o['name']; spec = classify_object(name, o['color'])
            if spec.role == 'LOCKED_GRIP':
                row, = by[name]; n_grips += 1
                assert np.array_equal(row['faces'].ravel(), o['tris'])
                grip = max(grip, np.linalg.norm(row['world']-original(o), axis=2).max())
            if spec.role == 'SURFACE_LOCKED':
                ref = original(o)[0]; m = np.array(o['m'][0]).reshape(4,4)
                if spec.catalog_id == 'pad_contoured_seat':
                    v = by[name+'_cushion'][0]['world'][0]; err = abs(v[:,2].max()-ref[:,2].max())
                else:
                    assert spec.catalog_id == 'roller_contoured'
                    v = by[name+'_foam'][0]['world'][0]; caps = by[name+'_caps'][0]['world'][0]
                    axis = m[2,:3]/np.linalg.norm(m[2,:3]); center = m[3,:3]
                    foam, cap = by[name+'_foam'][0], by[name+'_caps'][0]
                    assert foam['nf'] == cap['nf'] == 1
                    assert np.array_equal(foam['pos'],cap['pos'])
                    part = np.vstack([v,caps]); shift = foam['pos'][0]-center
                    assert abs(shift[0]) < .00001 and abs(shift[1]) <= np.ptp(ref[:,1])/2+.00001
                    assert np.allclose(axis[1:], 0, atol=1e-5)
                    # Transverse endpoints, radius and both centerline coordinates in the fitted frame.
                    p = part-shift-center; r = ref-center
                    err = max(np.max(abs(p.min(0)-r.min(0))),np.max(abs(p.max(0)-r.max(0))),
                              abs(np.linalg.norm(np.cross(p,axis),axis=1).max()-np.linalg.norm(np.cross(r,axis),axis=1).max()))
                    peak = surface_peak(human, thigh_faces, part[:,:2].min(0), part[:,:2].max(0))
                    gap = part[:,2].min()-peak
                    assert .002 <= gap <= .005, (key,name,gap)
                    clear = sweep.clear(part)
                    if not clear and not build.improved_d_handle_contact(key, o, part, human, base):
                        failures.append((key,name))
                    print(f'  {name}: dz={shift[2]*1000:+.2f} dy={shift[1]*1000:+.2f} gap={gap*1000:.3f} mm; swept-clear={clear}')
                surface = max(surface, err)
        assert n_grips and grip < .00020 and surface < .0005, (key, grip, surface)
        windows = sorted(by['window'], key=lambda w: w['pos'][0,0]); left, right = windows
        assert sum(r['mat'] in (MAT_ACRYLIC, MAT_SELECTOR_WINDOW) for r in rows) == 2
        for w in windows:
            assert w['mat']==MAT_SELECTOR_WINDOW and len(set(w['rgb']))==1 and abs(np.ptp(w['world'][0,:,1])-.004)<1e-6
        assert abs(right['world'][0,:,0].min()-left['world'][0,:,0].max()-.072)<1e-6
        plate = by['cast_plate']; assert len(plate)==28 and len({r['pid'] for r in plate})==1
        pin = by['selector_knob'][0]; z = pin['pos'][:,2]
        source_pin, = [o for o in raw['objects'] if build.normalize_base_name(o['name'])=='selector_pin']
        assert np.max(abs(z-np.asarray(source_pin['m'])[:,14])) < .00011
        for i,p in enumerate(plate):
            assert p['nf'] == (1 if i<14 else len(acts))
            assert np.max(abs(p['pos'][:,2]-(z[0] if i<14 else z)-(i-14)*.039)) < 1e-6
            assert np.allclose(np.ptp(p['world'][0],axis=0), [.380,.310,.035], atol=1e-6)
        for label, source, n in [('fixed_stack_labels', plate[14], 1), ('lift_stack_labels', plate[14], len(acts))]:
            decal, = by[label]
            assert decal['mat'] == MAT_LAT_STACK_LABEL and decal['nf'] == n and len(decal['faces']) == 2
            assert np.max(np.abs(decal['pos'] - source['pos'][:n])) < 1e-6
            v = decal['world'][0]
            assert .0001 < plate[0]['world'][0,:,1].min() - v[:,1].max() < .002
            assert np.allclose(np.ptp(v,axis=0)[2], 14*.039, atol=1e-6)
        from scene_lat_parts import palette
        for entry, row in zip(audit, rows):
            if build.normalize_base_name(entry['name']) in build.LAT_RED_FRAME and row['mat'] == MAT_FRAME:
                assert row['rgb'] == tuple(round(c*255) for c in palette()['lower_red'])
        assert abs(plate[0]['world'][0,:,2].min()-by['plinth'][0]['world'][0,:,2].max()) < 1e-6
        assert max(w['world'][0,:,1].max() for w in windows) < plate[0]['world'][0,:,1].min()
        assert len(by['anchor'])==4 and all(abs(a['world'][0,:,2].min())<1e-5 for a in by['anchor'])
        socket = by['load_socket'][0]['world'][:,:,2].max(1)
        assert socket.max()+.002 < by['sheave'][0]['world'][0,:,2].min()
        cable, = [o for o in raw['objects'] if o['name'].startswith('cable_stack_')]
        wire = by[cable['name']][0]['world'][:,:,2]
        assert np.max(abs(wire.max(1)-original(cable)[:,:,2].max(1))) < .0002
        assert np.max(abs(wire.min(1)-socket+.003)) < .0002
        blob = (data/f'{key}.wgm').read_bytes()
        print(f'{key}: {len(acts)} poses; {tris}t, {groups} groups, {len(blob)}/{len(zlib.compress(blob,6))} B raw/deflate; '
              f'{n_grips} locked grips; max world error: grip {grip*1000:.4f} mm, contact {surface*1000:.4f} mm')
    if failures: raise ValueError(f'Unproved whole-body clearance: {failures}')


if __name__ == '__main__':
    check(Path(sys.argv[1]) if len(sys.argv)>1 else build.REPO/'phone/src/main/assets/viewer3d')
