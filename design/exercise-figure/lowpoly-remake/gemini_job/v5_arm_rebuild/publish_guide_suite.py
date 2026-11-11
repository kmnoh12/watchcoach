"""Install only the explicitly selected local review lane in the existing viewer.
Default viewer and app model selection remain unchanged. No network publishing.
"""
from pathlib import Path
import argparse,json,shutil,hashlib
D=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--front',action='store_true');parser.add_argument('--include-overhead',action='store_true');args=parser.parse_args()
source=D/('guide_front_visual' if args.front else 'guide_suite')
installed=Path.home()/'Library/Application Support/WatchGymViewer'
assert installed.is_dir() and (installed/'index.html').is_file()
manifest=json.loads((source/'manifest.json').read_text());assert manifest['stage']==('unapproved visual comparison' if args.front else 'unapproved review')
base=json.loads((source/'base.json').read_text());n=base['vertices']
sources={c['id']:source for c in manifest['clips']}
if args.include_overhead:
 extra=D/('guide_front_overhead' if args.front else 'guide_overhead')
 extra_manifest=json.loads((extra/'manifest.json').read_text())
 assert json.loads((extra/'base.json').read_text())==base,'Incompatible overhead topology/skin'
 assert extra_manifest['stage']==manifest['stage']
 for clip in extra_manifest['clips']:
  assert clip['id'] not in sources,'Duplicate review clip'
  sources[clip['id']]=extra
 manifest['clips']+=extra_manifest['clips']
files=['base.json','manifest.json',*[c['json'] for c in manifest['clips']]]
for clip in manifest['clips']:
 data=json.loads((sources[clip['id']]/clip['json']).read_text());assert data['machine']==clip['id'] and data['acts']==clip['acts']
 assert len(data['frames'])==clip['frames'] and all(len(f)==n*3 for f in data['frames'])
 assert data['tris']==base['triangles']
# Preflight the complete inputs before touching any installed path.
html=(D.parents[2]/'viewer/index.html').read_bytes()
assert b'GUIDE_REVIEW' in html and b'validatePointCache' in html
out=installed/('v5-guide-front' if args.front else 'v5-guide');out.mkdir(exist_ok=True)
shutil.copyfile(source/'base.json',out/'base.json')
for clip in manifest['clips']:shutil.copyfile(sources[clip['id']]/clip['json'],out/clip['json'])
# Publish the manifest last, after every referenced motion file is available.
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(installed/'index.html').write_bytes(html)
assert (out/'base.json').read_bytes()==(source/'base.json').read_bytes()
assert json.loads((out/'manifest.json').read_text())==manifest
assert all((out/c['json']).read_bytes()==(sources[c['id']]/c['json']).read_bytes() for c in manifest['clips'])
print(json.dumps({'url':'http://127.0.0.1:8765/?human=v5-guide'+('&front=moderate' if args.front else ''),'review_clips':len(manifest['clips']),'default_selection_changed':False,'app_changed':False,'files':files},ensure_ascii=False))
