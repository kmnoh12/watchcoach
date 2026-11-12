"""Bundle reviewed V5 surface caches and equipment for the offline Android viewer.

Run with the project's NumPy environment. Generated assets remain gitignored.
No Blender regeneration or legacy-avatar fallback is performed here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import numpy as np

REPO = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def pack_motion(data, vertices):
    acts = np.asarray(data['acts'], dtype='<f4')
    points = np.asarray(data['frames'], dtype=np.float32).reshape(len(acts), vertices, 3)
    assert np.isfinite(points).all() and np.isfinite(acts).all() and (np.diff(acts) > 0).all()
    minimum = points.min(axis=(0, 1)).astype('<f4')
    scale = np.maximum((points.max(axis=(0, 1))-minimum)/65535, 1e-9).astype('<f4')
    quantized = np.rint((points-minimum)/scale).clip(0, 65535).astype('<u2')
    decoded = minimum+quantized.astype(np.float32)*scale
    error_mm = float(np.linalg.norm(decoded-points, axis=-1).max()*1000)
    assert error_mm < .1, f'Cache precision loss: {error_mm} mm'
    delta = np.diff(quantized.astype(np.int32), axis=0, prepend=np.zeros_like(quantized[:1], dtype=np.int32)).astype('<u2')   # wraps mod 65536, lossless
    assert (np.cumsum(delta.astype(np.uint32), axis=0).astype('<u2') == quantized).all()
    blob = struct.pack('<4sIII', b'WGP2', len(acts), vertices, 0) + minimum.tobytes() + scale.tobytes() + acts.tobytes() + delta.tobytes()
    assert len(blob) == 40+len(acts)*4+len(acts)*vertices*6
    return blob, error_mm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--viewer-root', type=Path, default=Path.home()/'Library/Application Support/WatchGymViewer')
    parser.add_argument('--extra', type=Path, required=True, help='Reviewed rolling-triceps conversion directory')
    parser.add_argument('--output', type=Path, default=REPO/'phone/src/main/assets/viewer3d')
    args = parser.parse_args()
    source = args.viewer_root/'v5-catalog'
    base = read(source/'base.json')
    clips = {c['id']: c for c in read(source/'manifest.json')['clips']}
    for c in read(args.extra/'manifest.json')['clips']:
        assert c['id'] == 'rolling_triceps_extension'
        clips[c['id']] = c
    models = read(args.output/'exercise_models.json')
    assert all(len(v) == 1 for v in models.values()), 'Unexpected combined equipment entry'
    keys = sorted({m for value in models.values() for m in value})
    assert not set(keys)-clips.keys(), 'App model missing V5 motion'
    stage = args.output.with_name('viewer3d-v5-building')
    if stage.exists():
        shutil.rmtree(stage)
    (stage/'human_v5').mkdir(parents=True)
    (stage/'data').mkdir()
    shutil.copytree(args.output/'three', stage/'three')
    (stage/'index.html').write_text((REPO/'tools/viewer3d/index.html').read_text())
    (stage/'human_stats.html').write_text((REPO/'tools/viewer3d/human_stats.html').read_text())
    (stage/'camera_views.json').write_text((REPO/'tools/viewer3d/camera_views.json').read_text())
    (stage/'exercise_models.json').write_text(json.dumps(models, ensure_ascii=False, separators=(',', ':')))
    (stage/'human_v5/base.json').write_text(json.dumps(base, separators=(',', ':')))
    report = dict(revision='v5-app-20261109-2', exercises=len(models), models=len(keys),
                  legacy_avatar_fallback=False, rows=[])
    for key in keys:
        folder = args.extra if key == 'rolling_triceps_extension' else source
        path = folder/f'{key}.json'
        data = read(path)
        assert data['machine'] == key and data['tris'] == base['triangles']
        assert data['acts'] == clips[key]['acts'] and len(data['frames']) == clips[key]['frames']
        blob, error = pack_motion(data, base['vertices'])
        (stage/'human_v5'/f'{key}.bin').write_bytes(blob)
        equipment = source/'equipment'/f'{key}.json'
        if not equipment.exists():
            equipment = args.viewer_root/'data'/f'{key}.json'
        machine = read(equipment)
        assert machine['objects'] is not None
        (stage/'data'/f'{key}.json').write_bytes(equipment.read_bytes())
        report['rows'].append(dict(id=key, source_sha256=sha(path), packed_sha256=sha(stage/'human_v5'/f'{key}.bin'),
                                   equipment_sha256=sha(equipment), maximum_error_mm=error, frames=len(data['acts'])))
    manifest = dict(revision=report['revision'], format='WGP2', clips=[clips[k] for k in keys])
    (stage/'human_v5/manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
    report['maximum_error_mm'] = max(r['maximum_error_mm'] for r in report['rows'])
    report['bytes'] = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
    (stage/'v5_bundle_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    module = re.search(r'<script type="module">(.*?)</script>', (stage/'index.html').read_text(), re.S).group(1)
    check = REPO/'work/v5-app-module-check.mjs'
    check.parent.mkdir(exist_ok=True)
    check.write_text(module)
    import subprocess
    subprocess.run(['node', '--check', str(check)], check=True)
    # Replace only regenerable app assets, after all inputs and output files passed.
    shutil.rmtree(args.output)
    stage.rename(args.output)
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
