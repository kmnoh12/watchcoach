#!/usr/bin/env python3
"""Run the machine_fly ablation cases through the production detector (one Kotlin test class)."""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import subprocess
import sys
import tempfile

from gen_virtual_watch_pilot import REPO, digest

TEST = "dev.kyungmin.watchcoach.core.VirtualWatchMachineFlyTest"


def write_index(cases, staging):
    index = staging / "index.tsv"
    with index.open("w") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["case_path", "signal", "feed_ns", "time_s", "acceleration", "gyro", "output_path"])
        for case in cases:
            manifest = json.loads((case / "manifest.json").read_text())
            truth = json.loads((case / "truth.json").read_text())
            times = ",".join(f"{t:.4f}" for t in manifest["time_s"])
            acc = ";".join(",".join(f"{v:.6f}" for v in row) for row in manifest["acceleration"])
            gyr = ";".join(",".join(f"{v:.6f}" for v in row) for row in manifest["gyro"])
            writer.writerow([case, truth["signal"], truth["preparation"]["end_ns"], times, acc, gyr, staging / case.name])
    return index


def compare(truth, events):
    live = [e for e in events if e["channel"] == "live"]
    groups = {r["index"]: [] for r in truth["repetitions"]}
    extra = []
    for i, e in enumerate(events):
        if e["channel"] != "live":
            continue
        ref = next((r for r in truth["repetitions"] if r["start_ns"] <= e["turnaround_ns"] < r["end_ns"]), None)
        if ref is None:
            extra.append(i)
        else:
            groups[ref["index"]].append((i, e))
    matched, missing = [], []
    for r in truth["repetitions"]:
        if not groups[r["index"]]:
            missing.append(r["index"])
            continue
        groups[r["index"]].sort(key=lambda item: abs(item[1]["turnaround_ns"] - r["turnaround_ns"]))
        i, e = groups[r["index"]][0]
        extra.extend(index for index, _ in groups[r["index"]][1:])
        matched.append({"truth_index": r["index"], "turnaround_error_ms": (e["turnaround_ns"] - r["turnaround_ns"]) / 1e6,
                        "end_error_ms": (e["end_ns"] - r["end_ns"]) / 1e6,
                        "duration_ms": e["duration_ms"], "spread": e["trajectory_spread"],
                        "displacement": e["motion_displacement"]})
    return {"expected_reps": truth["expected_reps"], "live_count": len(live),
            "offline_flush_count": sum(e["channel"] == "offline_flush" for e in events),
            "missing_indices": missing, "extra_event_indices": extra, "matched": matched}


def analyse_moments(truth, trace):
    """Per authored half, the moments the production detector would collect, by held axis.

    The detector holds the dominant blended axis; it moves only when a lobe closes, which is read from the
    events file elsewhere. Here each half reports which axis dominates and how many axis-0 moments its
    integration contributed, so a targeted attribution can be checked against it.
    """
    halves = []
    for r in truth["repetitions"]:
        halves.append({"rep": r["index"], "half": "pressed_to_stretched",
                       "start_ns": r["start_ns"], "end_ns": r["turnaround_ns"]})
        halves.append({"rep": r["index"], "half": "stretched_to_pressed",
                       "start_ns": r["turnaround_ns"], "end_ns": r["end_ns"]})
    out = []
    for h in halves:
        rows = [r for r in trace if h["start_ns"] <= float(r[0]) * 1e9 < h["end_ns"]]
        if not rows:
            continue
        dominant = [max(range(3), key=lambda i: abs(float(r[7 + i]))) for r in rows]
        axis0_sec = sum(1 for d in dominant if d == 0) / 50
        out.append({"rep": h["rep"], "half": h["half"],
                    "duration_s": round(len(rows) / 50, 2),
                    "axes_seen": sorted(set(dominant)),
                    "axis0_dominant_share": round(axis0_sec / (len(rows) / 50), 3)})
    return out


def read_events(path):
    integer = {"start_ns", "turnaround_ns", "end_ns", "duration_ms"}
    floating = {"peak_motion_rate", "motion_displacement", "trajectory_spread", "confidence"}
    with path.open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return [{k: int(float(v)) if k in integer else float(v) if k in floating else v for k, v in row.items()} for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--log", type=pathlib.Path, required=True)
    parser.add_argument("--gradle", type=pathlib.Path, default=REPO.parent / "안드로이드-에뮬레이터/gradle-8.11.1/bin/gradle")
    parser.add_argument("--java-home", type=pathlib.Path, default=REPO.parent / "안드로이드-에뮬레이터/jdk17/Contents/Home")
    args = parser.parse_args()
    args.root = args.root.resolve()
    cases = [args.root / name for name in json.loads((args.root / "index.json").read_text())["cases"]]
    with tempfile.TemporaryDirectory(prefix=".replay-", dir=args.root) as folder:
        staging = pathlib.Path(folder)
        index = write_index(cases, staging)
        env = dict(os.environ, JAVA_HOME=str(args.java_home), WATCHCOACH_MACHINE_FLY_INDEX=str(index))
        sdk = args.java_home.parent.parent.parent / "android-sdk"
        if sdk.is_dir():
            env.setdefault("ANDROID_SDK_ROOT", str(sdk))
        command = [str(args.gradle), ":core:test", "--tests", TEST, "--rerun", "--console=plain"]
        args.log.parent.mkdir(parents=True, exist_ok=True)
        with args.log.open("w") as handle:
            process = subprocess.run(command, cwd=REPO, env=env, stdout=handle, stderr=subprocess.STDOUT)
        print("kotlin", process.returncode)
        summary = []
        for case in cases:
            truth = json.loads((case / "truth.json").read_text())
            stats = dict(csv.reader((staging / case.name / "stats.tsv").read_text().splitlines(), delimiter="\t"))
            events = read_events(staging / case.name / "events.tsv") if (staging / case.name / "events.tsv").exists() else []
            trace = [r.split("\t") for r in (staging / case.name / "trace.tsv").read_text().splitlines()[1:] if r]
            moments = analyse_moments(truth, trace)
            (case / "trace.tsv").write_text((staging / case.name / "trace.tsv").read_text())
            if (staging / case.name / "lobes.tsv").exists():
                (case / "lobes.tsv").write_text((staging / case.name / "lobes.tsv").read_text())
            (case / "moments.json").write_text(json.dumps(moments, indent=1))
            summary.append({"case": case.name, "moments": moments, "scenario": truth["scenario"], "signal": truth["signal"],
                            "noise": truth["noise"], "stats": stats, "comparison": compare(truth, events),
                            "events": events})
        (args.root / "result.json").write_text(json.dumps({"kotlin_exit": process.returncode, "cases": summary},
                                                          ensure_ascii=False, indent=1))
        for row in summary:
            c = row["comparison"]
            print(f'{row["case"]:52s} live {c["live_count"]:2d}/{c["expected_reps"]} flush {c["offline_flush_count"]} missing {c["missing_indices"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
