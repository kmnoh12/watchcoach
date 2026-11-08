"""Capture the list-row preview animations (assets/previews/<id>.webp) from the phone 3D viewer.

NOT run automatically. Steps, once the exercises to ship are decided:
  1. python3 tools/build_app3d_v5.py --extra <rolling_trial dir>      # fresh viewer3d bundle with camera_views.json
  2. python3 tools/preview_capture.py --ids pull_up,squat             # or --ids-file approved.txt (one id per line)
  3. Open the printed URL in a browser (Claude's browser pane or Chrome) and leave it until it says "done".
The script then turns the saved PNG frames into 192px looping WebP files with ffmpeg.
Default output is a scratch folder; pass --out phone/src/main/assets/previews to replace the app's previews.
Frames: 24 per rep (progress 0 -> 1 -> 0, the same easing the viewer plays), 10 fps, loop forever.
"""
import argparse
import base64
import http.server
import json
import shutil
import subprocess
import threading
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / 'phone/src/main/assets/viewer3d'
FRAMES = 24
PAGE = '''<!doctype html><meta charset=utf-8><title>capture</title>
<body style="background:#111;color:#ccc;font:14px sans-serif"><p id=s>starting</p>
<iframe id=f style="width:256px;height:256px;border:0"></iframe>
<script>
const ids = %IDS%, FRAMES = %FRAMES%;
const f = document.getElementById("f"), s = document.getElementById("s");
const ease = t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
const loaded = () => new Promise(ok => { f.onload = () => { const t = setInterval(() => { if (f.contentWindow.__snap) { clearInterval(t); ok(); } }, 50); }; });
(async () => {
  for (let n = 0; n < ids.length; n++) {
    f.src = "index.html?ex=" + ids[n] + "&snap=0&c=" + n; await loaded();
    for (let i = 0; i < FRAMES; i++) {
      const t = i / FRAMES, a = t < .5 ? ease(t * 2) : ease((1 - t) * 2);   // same 0 -> 1 -> 0 shape the viewer plays
      const png = f.contentWindow.__snap(a);
      await fetch("/save?n=" + ids[n] + "__" + String(i).padStart(2, "0"), { method: "POST", body: png });
    }
    await fetch("/done?n=" + ids[n], { method: "POST", body: "" });
    s.textContent = (n + 1) + " / " + ids.length + "  " + ids[n];
  }
  await fetch("/finish", { method: "POST", body: "" }); s.textContent = "done";
})();
</script>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ids', default='')
    ap.add_argument('--ids-file', type=Path)
    ap.add_argument('--out', type=Path, default=REPO / 'work/previews-out')
    ap.add_argument('--port', type=int, default=8792)
    args = ap.parse_args()
    ids = [i for i in args.ids.split(',') if i]
    if args.ids_file:
        ids += [l.strip() for l in args.ids_file.read_text().splitlines() if l.strip() and not l.startswith('#')]
    known = json.loads((ASSETS / 'exercise_models.json').read_text())
    bad = [i for i in ids if i not in known]
    assert ids and not bad, f'no ids, or unknown ids: {bad}'
    frames = REPO / 'work/previews-frames'
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    args.out.mkdir(parents=True, exist_ok=True)
    finished = threading.Event()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(ASSETS), **k)

        def do_GET(self):
            if self.path.split('?')[0] == '/capture.html':
                body = PAGE.replace('%IDS%', json.dumps(ids)).replace('%FRAMES%', str(FRAMES)).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(body)
            else:
                super().do_GET()

        def do_POST(self):
            url = urllib.parse.urlparse(self.path)
            name = urllib.parse.parse_qs(url.query).get('n', [''])[0]
            data = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
            if url.path == '/save':
                (frames / f'{name}.png').write_bytes(base64.b64decode(data.split(',', 1)[1]))
            elif url.path == '/done':
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '10', '-i', str(frames / f'{name}__%02d.png'),
                                '-vf', 'scale=192:192:flags=lanczos', '-c:v', 'libwebp_anim', '-quality', '75',
                                '-compression_level', '6', '-loop', '0', str(args.out / f'{name}.webp')], check=True)
                for png in frames.glob(f'{name}__*.png'):
                    png.unlink()
            elif url.path == '/finish':
                finished.set()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'ok')

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f'open http://127.0.0.1:{args.port}/capture.html   ({len(ids)} exercises -> {args.out})', flush=True)
    finished.wait()
    server.shutdown()
    print('done', len(list(args.out.glob('*.webp'))), 'webp files in', args.out)


if __name__ == '__main__':
    main()
