#!/usr/bin/env python3
"""Replay the straight_arm_pulldown virtual-watch cases through the production detector (one Kotlin test class).

Both replay modes (production baseline and the test-only return-counting counterfactual) run inside the single
allowed Gradle invocation. Detector output is measured against truth.json only; unmatched events are never hidden.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from collections import defaultdict

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
TEST = "dev.kyungmin.watchcoach.core.VirtualWatchStraightArmPulldownTest"
GRADLE_TASK = ":core:test"
MODES = ("baseline", "counterfactual_return_counting")
# The test reads its inputs through an environment variable, which Gradle's execution cache does not track.
INPUT_OPTIONS = ["-Dorg.gradle.caching=false", "--no-build-cache"]
SAMPLE_NS = 20_000_000


def parse_int_float(row):
    out = {}
    for key, value in row.items():
        if key in ("channel",):
            out[key] = value
        elif key in ("confidence", "peak_motion_rate", "motion_displacement", "trajectory_spread"):
            out[key] = float(value)
        else:
            out[key] = int(float(value))
    return out


def read_events(path):
    if not path.is_file():
        return []
    with path.open() as handle:
        return [parse_int_float(row) for row in csv.DictReader(handle, delimiter="\t")]


def match(truth, events):
    """One event to at most one rep by `pull_start <= event.end < return_end`; everything unmatched is reported."""
    owners = []
    for event in events:
        owner = None
        for i, start in enumerate(truth["pull_start_ns"]):
            if start <= event["end_ns"] < truth["return_end_ns"][i]:
                owner = i
                break
        owners.append(owner)
    matches, duplicates = [], []
    for i, index in enumerate(truth["rep_index"]):
        members = [j for j, owner in enumerate(owners) if owner == i]
        if not members:
            continue
        rep = {"index": index, "pull_start_ns": truth["pull_start_ns"][i],
               "turnaround_ns": truth["turnaround_ns"][i], "return_end_ns": truth["return_end_ns"][i]}
        ordered = sorted(members, key=lambda j: (events[j]["end_ns"], j))
        matches.append((rep, events[ordered[0]]))
        duplicates += ordered[1:]
    missing = [index for i, index in enumerate(truth["rep_index"]) if not any(owner == i for owner in owners)]
    extra = [j for j, owner in enumerate(owners) if owner is None]
    return {"matches": matches, "missing": missing, "extra": extra, "duplicates": duplicates}


def measure(events, truth):
    """Names every event that lands at a pull turnaround or halfway point, and post-workout events."""
    notes = {"turnaround_events": [], "halfway_events": [], "post_workout_events": []}
    stillness = truth["stillness"]["start_ns"]
    for j, e in enumerate(events):
        end = e["end_ns"]
        for r in truth["repetitions"]:
            if abs(end - r["turnaround_ns"]) <= SAMPLE_NS:
                notes["turnaround_events"].append(j)
            halfway = (r["pull_start_ns"] + r["turnaround_ns"]) // 2
            if abs(end - halfway) <= SAMPLE_NS:
                notes["halfway_events"].append(j)
        if end > stillness:
            notes["post_workout_events"].append(j)
    return notes


def window_by_end(start_key, end_key):
    def inside(rep, event):
        start = rep[start_key]
        stop = rep[end_key]
        return start <= event["end_ns"] < stop
    return inside


def analyse_case(root, case, out_dir):
    columns = {key: json.loads((root / case / f"{key}.json").read_text())[key]
               for key in ("prep_end_ns", "rep_index", "turnaround_ns", "return_end_ns", "histogram",
                           "handle_down_lowest_ns", "stillness_end_ns", "pull_start_ns", "case_id")}
    truth = {key: columns[key] for key in ("rep_index", "turnaround_ns", "return_end_ns", "pull_start_ns")}
    repetitions = [{"pull_start_ns": a, "turnaround_ns": b, "return_end_ns": c}
                   for a, b, c in zip(columns["pull_start_ns"], columns["turnaround_ns"], columns["return_end_ns"])]
    events = read_events(out_dir / "events.tsv")
    live = [e for e in events if e["channel"] == "live"]
    flush = [e for e in events if e["channel"] == "offline_flush"]
    live_match = match(truth, live)
    flush_match = match(truth, flush)
    notes = measure(events, {"repetitions": repetitions, "stillness": {"start_ns": columns["stillness_end_ns"]}})
    rows = []
    for rep, event in live_match["matches"]:
        rows.append({
            "rep": rep["index"],
            "end_timestamp_ns": event["end_ns"],
            "detector_emitted_at_ns": event["detector_emitted_at_ns"],
            "expected_user_delivery_ns": event["detector_emitted_at_ns"],
            "truth_rep_end_ns": rep["return_end_ns"],
            "truth_turnaround_ns": rep["turnaround_ns"],
            "early_or_late_ms_event_end": round((event["end_ns"] - rep["return_end_ns"]) / 1e6, 3),
            "early_or_late_ms_delivery": round((event["detector_emitted_at_ns"] - rep["return_end_ns"]) / 1e6, 3),
            "channel": event["channel"],
            "accepted_at_turnaround": abs(event["end_ns"] - rep["turnaround_ns"]) <= SAMPLE_NS,
            "expected_delivery_before_return_by_ms": round((rep["return_end_ns"] - event["detector_emitted_at_ns"]) / 1e6, 3),
        })
    late = [r for r in rows if r["early_or_late_ms_delivery"] > SAMPLE_NS / 1e6]
    matched_rep = {r["rep"]: 1 for r in rows}
    first_two_then_stop = None
    if truth["rep_index"]:
        delivered = defaultdict(int)
        for rep, _ in live_match["matches"]:
            delivered[rep["index"]] += 1
        first_two_then_stop = all(delivered.get(i, 0) == 1 for i in (1, 2)) and all(delivered.get(i, 0) == 0 for i in range(3, 11))
    last_end = columns["return_end_ns"][-1] if columns["return_end_ns"] else None
    hist = np.asarray(columns["histogram"] or np.zeros(101), dtype=float)
    return {
        "case": case,
        "expected_reps": len(truth["rep_index"]),
        "live_count": len(live),
        "offline_flush_count": len(flush),
        "event_table": rows,
        "matched_rep_indices": sorted(matched_rep),
        "unmatched_live_events": [live[j] for j in live_match["extra"] + live_match["duplicates"]],
        "missing": live_match["missing"],
        "duplicates": live_match["duplicates"],
        "extra": live_match["extra"],
        "flush_match": {"matched": len(flush_match["matches"]), "missing": flush_match["missing"],
                        "unmatched": [flush[j] for j in flush_match["extra"] + flush_match["duplicates"]]},
        "turnaround_events": notes["turnaround_events"],
        "halfway_events": notes["halfway_events"],
        "post_workout_events": notes["post_workout_events"],
        "late_delivery_reps": [r["rep"] for r in late],
        "early_or_late_delivery_ms_range": [min((r["early_or_late_ms_delivery"] for r in rows), default=None),
                                            max((r["early_or_late_ms_delivery"] for r in rows), default=None)],
        "first_two_then_stop": first_two_then_stop,
        "live_after_rep10": len([e for e in live if last_end is not None and e["end_ns"] > last_end]),
        "flush_after_rep10": len([e for e in flush if last_end is not None and e["end_ns"] > last_end]),
        "authored_phase_histogram": {"bins_1pct_nonempty": int((hist > 0).sum()),
                                     "at_start_or_end": int(hist[0] + hist[100]),
                                     "interior": int(hist[1:100].sum())},
    }


def acceptance(rows):
    failures = []
    for row in rows:
        if row["expected_reps"] == 10:
            if row["live_count"] != 10:
                failures.append(f'{row["case"]}: live {row["live_count"]} != 10')
            if row["matched_rep_indices"] != list(range(1, 11)):
                failures.append(f'{row["case"]}: matched reps {row["matched_rep_indices"]} != 1..10')
            if row["missing"] or row["duplicates"] or row["extra"] or row["offline_flush_count"]:
                failures.append(f'{row["case"]}: missing {row["missing"]} duplicates {row["duplicates"]} '
                                f'extra {row["extra"]} flush {row["offline_flush_count"]}')
        if row["turnaround_events"] or row["halfway_events"]:
            failures.append(f'{row["case"]}: event at turnaround {row["turnaround_events"]} or halfway {row["halfway_events"]}')
        early = [r for r in row["event_table"] if r["expected_delivery_before_return_by_ms"] > SAMPLE_NS / 1e6]
        if early:
            failures.append(f'{row["case"]}: rep {early[0]["rep"]} delivery {early[0]["expected_delivery_before_return_by_ms"]} ms before full return')
        if row["case"] == "ten_then_handle_down" and (row["live_after_rep10"] or row["flush_after_rep10"]):
            failures.append(f'ten_then_handle_down: {row["live_after_rep10"]} live / {row["flush_after_rep10"]} flush events after rep 10')
        if row["case"] == "handle_down_only" and (row["live_count"] or row["offline_flush_count"]):
            failures.append(f'handle_down_only: {row["live_count"]} live / {row["offline_flush_count"]} flush events')
    return failures


def run_gradle(mode, index, log, gradle, java_home):
    env = dict(os.environ, JAVA_HOME=str(java_home), WATCHCOACH_STRAIGHT_ARM_PULLDOWN_ROOT=str(index))
    sdk = java_home.parent.parent.parent / "android-sdk"
    if sdk.is_dir():
        env.setdefault("ANDROID_SDK_ROOT", str(sdk))
    command = [str(gradle), GRADLE_TASK, "--tests", TEST, "--console=plain"] + INPUT_OPTIONS
    with log.open("a") as handle:
        handle.write(f"\n===== {mode} =====\n")
        handle.flush()
        return subprocess.run(command, cwd=REPO, env=env, stdout=handle, stderr=subprocess.STDOUT).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--log", type=pathlib.Path, required=True)
    parser.add_argument("--invocations", type=int, default=1)
    parser.add_argument("--first-out", type=pathlib.Path, required=True)
    parser.add_argument("--gradle", type=pathlib.Path, default=REPO.parent / "안드로이드-에뮬레이터/gradle-8.11.1/bin/gradle")
    parser.add_argument("--java-home", type=pathlib.Path, default=REPO.parent / "안드로이드-에뮬레이터/jdk17/Contents/Home")
    args = parser.parse_args()
    root = args.root.resolve()
    grader = args.gradle if args.gradle.is_file() else pathlib.Path("gradle")
    java_home = args.java_home if args.java_home.is_dir() else pathlib.Path(os.environ.get("JAVA_HOME", ""))
    cases = json.loads((root / "index.json").read_text())["cases"]
    results = {}
    exits = []
    # Real paths on both sides: /var is a symlink to /private/var on macOS and the test compares canonical paths.
    staging = root / ".replay-staging"
    staging.mkdir(exist_ok=True)
    import shutil
    for stale in staging.iterdir():
        shutil.rmtree(stale) if stale.is_dir() else stale.unlink()
    try:
        return _run(args, root, staging, cases, grader, java_home, {}, [])
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _run(args, root, staging, cases, grader, java_home, results, exits):
    for run in range(args.invocations):
        modes = MODES if run == 0 else ("final",)
        index = staging / f"index-{run}.tsv"
        lines = ["case_path\tmode\toutput_path"]
        for mode in modes:
            for case in cases:
                (staging / f"{run}-{mode}" / case).mkdir(parents=True, exist_ok=True)
                lines.append("\t".join([str(root / case), "baseline" if mode == "final" else mode,
                                        str(staging / f"{run}-{mode}" / case)]))
        index.write_text("\n".join(lines) + "\n")
        code = run_gradle(modes[0], index, args.log, grader, java_home)
        exits.append(code)
        if code != 0:
            print("kotlin exit", code, "see", args.log)
            return code
        for mode in modes:
            results[mode] = [analyse_case(root, case, staging / f"{run}-{mode}" / case) for case in cases]
        if args.first_out is not None and run == 0:
            for mode in MODES:
                target = args.first_out / f"{mode}-result.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"kotlin_exit": code, "cases": results[mode],
                                              "acceptance_failures": acceptance(results[mode])},
                                             ensure_ascii=False, indent=1))
    summary = {}
    for mode, rows in results.items():
        failures = acceptance(rows)
        summary[mode] = {"cases": rows, "acceptance_failures": failures}
        print(mode, "failures:", len(failures))
        for row in rows:
            print(f'  {row["case"]:32s} live {row["live_count"]:2d}/{row["expected_reps"]:2d} flush {row["offline_flush_count"]} '
                  f'missing {row["missing"]} extra {row["extra"]} first_two_then_stop {row["first_two_then_stop"]} '
                  f'late {row["early_or_late_delivery_ms_range"]} hd_after10 {row["live_after_rep10"]}/{row["flush_after_rep10"]}')
    print(json.dumps({"kotlin_exit": exits, "summary": {m: {"failures": v["acceptance_failures"]} for m, v in summary.items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
