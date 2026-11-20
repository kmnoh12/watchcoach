"""Refresh only some V5 clips in the phone's 3D bundle (phone/src/main/assets/viewer3d), no full rebuild.

  python3 tools/update_app3d_v5_clips.py --update upright_row_barbell upright_row_dumbbell
  python3 tools/update_app3d_v5_clips.py --remove cable_rear_delt_fly
  python3 tools/update_app3d_v5_clips.py --add wide_pulldown_machine:wide_pulldown_machine   # model_key:exercise_id, a new clip

--update re-packs the clip from the PC viewer's v5-catalog (the one you review at
http://127.0.0.1:8765/v5-catalog/?human=v5-guide&front=moderate) with the same packer as build_app3d_v5.py.
--remove drops a model key that no exercise uses any more (bundle, report, manifest, equipment).
Other clips stay byte-identical. It edits the old-hand master bundle (work/viewer3d-oldhand); afterwards run
tools/refresh_app3d_newhand.py to rebuild the phone's new-hand bundle. Both are gitignored; rebuild/deploy the app separately.
"""
import argparse, hashlib, importlib.util, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_app3d_v5', REPO/'tools/build_app3d_v5.py')
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--update', nargs='*', default=[])
    parser.add_argument('--remove', nargs='*', default=[])
    parser.add_argument('--add', nargs='*', default=[], help='model_key:exercise_id for a clip that is not in the bundle yet')
    parser.add_argument('--viewer-root', type=Path, default=Path.home()/'Library/Application Support/__PROTECTED_WATCHCOACH_VIEWER__')
    parser.add_argument('--bundle', type=Path, default=REPO/'work/viewer3d-oldhand')
    args = parser.parse_args()
    source = args.viewer_root/'v5-catalog'
    bundle = args.bundle
    base = json.loads((source/'base.json').read_text())
    report_path = bundle/'v5_bundle_report.json'
    report = json.loads(report_path.read_text())
    manifest_path = bundle/'human_v5/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    models_path = bundle/'exercise_models.json'
    models = json.loads(models_path.read_text())
    for key in args.update:
        data = json.loads((source/f'{key}.json').read_text())
        clip = next(c for c in manifest['clips'] if c['id'] == key)
        assert data['machine'] == key and data['tris'] == base['triangles']
        assert data['acts'] == clip['acts'] and len(data['frames']) == clip['frames'], 'frame count changed: run build_app3d_v5.py'
        blob, error = builder.pack_motion(data, base['vertices'])
        (bundle/'human_v5'/f'{key}.bin').write_bytes(blob)
        row = next(r for r in report['rows'] if r['id'] == key)
        row.update(source_sha256=sha(source/f'{key}.json'), packed_sha256=sha(bundle/'human_v5'/f'{key}.bin'), maximum_error_mm=error)
    source_clips = {c['id']: c for c in json.loads((source/'manifest.json').read_text())['clips']}
    for spec in args.add:
        key, exercise = spec.split(':')
        assert key not in {c['id'] for c in manifest['clips']}, f'{key} is already in the bundle: use --update'
        data = json.loads((source/f'{key}.json').read_text())
        clip = source_clips[key]
        assert data['machine'] == key and data['tris'] == base['triangles']
        assert data['acts'] == clip['acts'] and len(data['frames']) == clip['frames']
        blob, error = builder.pack_motion(data, base['vertices'])
        (bundle/'human_v5'/f'{key}.bin').write_bytes(blob)
        equipment = source/'equipment'/f'{key}.json'
        if not equipment.exists():
            equipment = args.viewer_root/'data'/f'{key}.json'
        assert json.loads(equipment.read_text())['objects'] is not None
        (bundle/'data'/f'{key}.json').write_bytes(equipment.read_bytes())
        manifest['clips'] = sorted(manifest['clips'] + [clip], key=lambda c: c['id'])
        report['rows'] = sorted(report['rows'] + [dict(id=key, source_sha256=sha(source/f'{key}.json'), packed_sha256=sha(bundle/'human_v5'/f'{key}.bin'),
                                equipment_sha256=sha(equipment), maximum_error_mm=error, frames=len(data['acts']))], key=lambda r: r['id'])
        models[exercise] = [key]
        models_path.write_text(json.dumps(models, ensure_ascii=False, separators=(',', ':')))
    for key in args.remove:
        assert not any(key in v for v in models.values()), f'{key} is still used by an exercise'
        for path in (bundle/'human_v5'/f'{key}.bin', bundle/'data'/f'{key}.json'):
            path.unlink(missing_ok=True)
        manifest['clips'] = [c for c in manifest['clips'] if c['id'] != key]
        report['rows'] = [r for r in report['rows'] if r['id'] != key]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
    report['models'] = len(report['rows'])
    report['exercises'] = len(models)
    report['maximum_error_mm'] = max(r['maximum_error_mm'] for r in report['rows'])
    report['bytes'] = sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file())
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(f'updated {len(args.update)}, removed {len(args.remove)}, clips {len(report["rows"])}')


if __name__ == '__main__':
    main()
