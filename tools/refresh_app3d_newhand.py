"""Turn the old-hand V5 bundle into the phone's new-hand bundle (plus the left-wrist watch).

  python3 tools/refresh_app3d_newhand.py

The PC catalog and the clip tools (build_app3d_v5.py, update_app3d_v5_clips.py) still work on the
old 893-vertex hand. They write the old-hand master bundle in work/viewer3d-oldhand. This script
converts that master with tools/build_v5_hand_viewer_copy.py, adds human_v5/watch.json, checks the
grip report and only then replaces phone/src/main/assets/viewer3d. Both folders are regenerable and gitignored.
"""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
BLENDER = {
    "Darwin": "/Applications/Blender.app/Contents/MacOS/Blender",
    "Windows": r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
}.get(platform.system(), "blender")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--oldhand", type=Path, default=REPO / "work/viewer3d-oldhand")
    parser.add_argument("--output", type=Path, default=REPO / "phone/src/main/assets/viewer3d")
    parser.add_argument("--blender", default=BLENDER)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    old = args.oldhand
    assert (old / "human_v5/base.json").exists(), f"old-hand master missing: {old}"
    assert json.loads((old / "human_v5/base.json").read_text())["vertices"] == 893, "master is not the old-hand bundle"
    stage = args.output.with_name("viewer3d-newhand-building")
    if stage.exists():
        shutil.rmtree(stage)
    subprocess.run([sys.executable, str(REPO / "tools/build_v5_hand_viewer_copy.py"), str(old), str(stage),
                    "--blender", args.blender, "--workers", str(args.workers)], check=True)
    fit = json.loads((stage / "hand_fit_report.json").read_text())
    worst = min((min(p[0] for p in g["pad_mm"].values()), key, side)
                for key, row in fit.items() for side, g in row["grips"].items())
    watch = REPO / "tools/viewer3d/watch_v5.json"
    if watch.exists():
        shutil.copyfile(watch, stage / "human_v5/watch.json")
    # The hand converter copies the old viewer. Install the current renderer and rebuild
    # the shared machine catalogue against the final hand-adjusted grips before replacing anything.
    shutil.copyfile(REPO / "tools/viewer3d/index.html", stage / "index.html")
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_machines.py"),
                    "--viewer-dir", str(stage), "--stage1", "--plates"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_cable_towers.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_adjust_bench.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_bench_pads.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_bench_pads.py"), str(stage), "--batch", "2"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_bench_pads.py"), str(stage), "--batch", "3"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_cable_towers.py"),
                    str(stage), "--batch-03"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_cable_towers.py"),
                    str(stage), "--batch", "2"], check=True)
    # Accessory benches share clips with the cable stations: append after the towers.
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_bench_pads.py"), str(stage), "--batch", "4"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_pull_stations.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_pull_pads.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_row_pads.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_pull_stations.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_upper_stations.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_lower_towers.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_lower_pads.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_lower_press_pads.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_press_stations.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_chest_press_pads.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_arm_press_pads.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_bars.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_bench.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_adjust_bench_rest.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_bars.py"), str(stage), "--batch", "2"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_adjust_bench_rest.py"), str(stage), "--fixed"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_adjust_bench_rest.py"), str(stage), "--flat"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_strength_access.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_cables.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_cables.py"),
                    str(stage), "--batch-03"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_bench.py"),
                    str(stage), "--handweights"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_bench.py"),
                    str(stage), "--handweights-02"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_rest_bench.py"),
                    str(stage), "--handweights-03"], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_cable_rest.py"), str(stage)], check=True)
    subprocess.run([sys.executable, str(REPO / "tools/upgrade_app3d_pull_rest.py"), str(stage)], check=True)
    report = json.loads((old / "v5_bundle_report.json").read_text())
    manifest = json.loads((stage / "human_v5/manifest.json").read_text())
    manifest["revision"] = report["revision"] + "+newhand"
    (stage / "human_v5/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
    report.update(
        hand="V5 new hand (promo/models/fix_v5_hands.py), converted by tools/build_v5_hand_viewer_copy.py",
        vertices=json.loads((stage / "human_v5/base.json").read_text())["vertices"],
        worst_finger_gap_mm=dict(gap=worst[0], clip=worst[1], side=worst[2]),
        watch=watch.exists(),
        bytes=sum(p.stat().st_size for p in stage.rglob("*") if p.is_file()),
    )
    (stage / "v5_bundle_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if worst[0] < -1:
        print(f"WARNING: fingers cut {-worst[0]:.1f} mm into {worst[1]} ({worst[2]}); fix that motion in the catalog")
    # The stats figure finds its muscle faces by position on this body; refuse to replace the phone bundle if they no longer fit.
    shutil.copyfile(REPO / "tools/viewer3d/human_stats.html", stage / "human_stats.html")
    subprocess.run([sys.executable, str(REPO / "tools/check_stats_faces.py"), str(stage)], check=True)
    shutil.rmtree(args.output)
    stage.rename(args.output)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
