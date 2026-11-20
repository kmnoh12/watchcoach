"""Check that the stats figure's muscle faces still exist on the bundled body model.

  python3 tools/check_stats_faces.py [bundle folder, default phone/src/main/assets/viewer3d]

human_stats.html stores each muscle face by its rest-pose centre (the #muscle-faces JSON block) and looks it up
in human_v5/base.json, then paints its mirror twin too. This runs the same lookup and exits 1 when a face or its
twin is missing, so a changed body model stops the build instead of quietly painting the wrong faces.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
TOLERANCE = 0.002  # metres; must match FACE_TOLERANCE in human_stats.html


def check(bundle: Path) -> list[str]:
    html = (bundle / "human_stats.html").read_text()
    block = re.search(r'<script type="application/json" id="muscle-faces">(.*?)</script>', html, re.S)
    if not block:
        return ["human_stats.html has no #muscle-faces block"]
    data = json.loads(block.group(1))
    base = json.loads((bundle / "human_v5/base.json").read_text())
    points = np.array(base["rest"], dtype=np.float32).reshape(-1, 3).astype(np.float64)
    tris = np.array(base["triangles"]).reshape(-1, 3)
    centres = points[tris].mean(1)
    # Mirror lookup exactly as the page does it: vertex positions rounded to 0.1 mm, faces by their sorted corners.
    key = lambda p: tuple(int(round(c * 1e4)) for c in p)
    vertex_at = {key(p): v for v, p in enumerate(points)}
    face_of = {tuple(sorted(t)): f for f, t in enumerate(tris.tolist())}

    def twin(f):
        corners = [vertex_at.get(key((-points[v][0], points[v][1], points[v][2]))) for v in tris[f]]
        return None if None in corners else face_of.get(tuple(sorted(corners)))

    groups = [(name, faces) for name, faces in data["muscles"].items()]
    groups += [(f'{c["above"]}/{c["below"]} cut', c["faces"]) for c in data["cuts"]]
    problems = []
    for name, faces in groups:
        for p in faces:
            d = np.linalg.norm(centres - p, axis=1)
            f = int(d.argmin())
            if d[f] > TOLERANCE:
                problems.append(f"{name}: no face at {p} (nearest {d[f] * 1000:.1f} mm away)")
            elif twin(f) is None:
                problems.append(f"{name}: face at {p} has no mirror twin")
    return problems


def main():
    bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "phone/src/main/assets/viewer3d"
    problems = check(bundle)
    if problems:
        print("통계 인체 근육 면이 인체 모델과 안 맞아:\n  " + "\n  ".join(problems), file=sys.stderr)
        sys.exit(1)
    print(f"stats faces ok: {bundle}")


if __name__ == "__main__":
    main()
