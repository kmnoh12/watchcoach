"""Install only the explicitly selected local review lane in the existing viewer.
Default viewer and app model selection remain unchanged. No network publishing.
"""
from pathlib import Path
import argparse,json,shutil,hashlib
D=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--front',action='store_true');args=parser.parse_args()
source=D/('guide_front_visual' if args.front else 'guide_suite')
installed=Path.home()/'Library/Application Support/WatchGymViewer'
assert installed.is_dir() and (installed/'index.html').is_file()
manifest=json.loads((source/'manifest.json').read_text());assert manifest['stage']==('unapproved visual comparison' if args.front else 'unapproved review')
files=['base.json','manifest.json',*[c['json'] for c in manifest['clips']]]
base=json.loads((source/'base.json').read_text());n=base['vertices']
for clip in manifest['clips']:
 data=json.loads((source/clip['json']).read_text());assert data['machine']==clip['id'] and data['acts']==clip['acts']
 assert len(data['frames'])==clip['frames'] and all(len(f)==n*3 for f in data['frames'])
 assert data['tris']==base['triangles']
# Preflight the complete inputs before touching any installed path.
html=(D.parents[2]/'viewer/index.html').read_bytes()
assert b'GUIDE_REVIEW' in html and b'validatePointCache' in html
out=installed/('v5-guide-front' if args.front else 'v5-guide');out.mkdir(exist_ok=True)
for f in files:shutil.copyfile(source/f,out/f)
(installed/'index.html').write_bytes(html)
assert all((out/f).read_bytes()==(source/f).read_bytes() for f in files)
print(json.dumps({'url':'http://127.0.0.1:8765/?human=v5-guide'+('&front=moderate' if args.front else ''),'review_clips':len(manifest['clips']),'default_selection_changed':False,'app_changed':False,'files':files},ensure_ascii=False))
