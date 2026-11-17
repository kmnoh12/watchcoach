#!/usr/bin/env python3
"""Replay named synthetic cases through unmodified production Kotlin.

JSON stays authoritative in Python. A hashed TSV bridge avoids adding a JSON
dependency to the app/core for this optional offline experiment.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from gen_virtual_watch_pilot import CASES, HZ, REPO, WORK, digest, json_bytes, motion_provenance, verify_case


def validate_truth(manifest, truth):
    for field in ("source", "case_id", "exercise_id"):
        if manifest[field] != truth[field]:
            raise ValueError("Capture/truth identity mismatch: " + field)
    allowed_exercises = {exercise_id for exercise_id, _, _ in CASES.values()}
    provenance = motion_provenance()
    if truth["source"] != "synthetic" or truth["exercise_id"] not in allowed_exercises:
        raise ValueError("Only named synthetic cases are allowed")
    if manifest.get("motion_provenance") != provenance:
        raise ValueError("Synthetic motion provenance mismatch")
    if truth.get("motion_lane") != provenance["sensor_motion"]["lane_id"]:
        raise ValueError("Synthetic motion lane must remain the C2 diagnostic variation")
    model_id = manifest.get("model_id")
    if model_id in CASES and CASES[model_id][0] != truth["exercise_id"]:
        raise ValueError("Capture/truth model mapping mismatch")
    prep, tail, reps = truth["preparation"], truth["ending_static"], truth["repetitions"]
    if (prep["start_ns"] != manifest["start_ns"] or tail["end_ns"] != manifest["end_ns"]
            or not prep["start_ns"] < prep["end_ns"] < tail["start_ns"] < tail["end_ns"]
            or len(reps) != truth["expected_reps"] or not reps):
        raise ValueError("Invalid independent truth timeline")
    previous = prep["end_ns"]
    for i, rep in enumerate(reps, 1):
        if (rep["index"] != i or rep["start_ns"] != previous
                or not rep["start_ns"] < rep["turnaround_ns"] < rep["end_ns"]):
            raise ValueError("Independent repetitions must be ordered and contiguous")
        previous = rep["end_ns"]
    if previous != tail["start_ns"]:
        raise ValueError("Independent repetitions must join ending static")


def compare_events(truth, events):
    """Match by scheduled cycle containing the turnaround, not by total count.

    Each cycle owns [start, end). Nearest turnaround wins if there are duplicate
    events, and the others stay visible. Early means more than one sample before
    the authored full return, not a judgment about acceptable real-world timing.
    """
    live = [(i, e) for i, e in enumerate(events) if e["channel"] == "live" and e["accepted"]]
    groups = {r["index"]: [] for r in truth["repetitions"]}
    extra = []
    for i, event in live:
        ref = next((r for r in truth["repetitions"]
                    if r["start_ns"] <= event["turnaround_ns"] < r["end_ns"]), None)
        if ref is None:
            extra.append(i)
        else:
            groups[ref["index"]].append((i, event))
    matched, missing = [], []
    for ref in truth["repetitions"]:
        candidates = groups[ref["index"]]
        if not candidates:
            missing.append(ref["index"])
            continue
        candidates.sort(key=lambda item: (abs(item[1]["turnaround_ns"] - ref["turnaround_ns"]), item[0]))
        i, event = candidates[0]
        extra.extend(index for index, _ in candidates[1:])
        matched.append({"truth_index": ref["index"], "event_index": i,
                        "start_error_ms": (event["start_ns"] - ref["start_ns"]) / 1e6,
                        "turnaround_error_ms": (event["turnaround_ns"] - ref["turnaround_ns"]) / 1e6,
                        "end_error_ms": (event["end_ns"] - ref["end_ns"]) / 1e6,
                        "emission_error_ms": (event["emitted_at_ns"] - ref["end_ns"]) / 1e6,
                        "delivery_delay_ms": (event["emitted_at_ns"] - event["end_ns"]) / 1e6})
    return {"expected_reps": truth["expected_reps"], "accepted_live_count": len(live),
            "raw_live_count": sum(e["channel"] == "live" for e in events),
            "rejected_live_count": sum(e["channel"] == "live" and not e["accepted"] for e in events),
            "offline_flush_count": sum(e["channel"] == "offline_flush" for e in events),
            "count_difference": len(live) - truth["expected_reps"],
            "one_to_one_coverage": not missing and not extra,
            "missing_repetition_indices": missing, "extra_live_event_indices": sorted(extra),
            "boundary_tolerance_ms": 1000 / HZ,
            "early_emission_count": sum(r["emission_error_ms"] < -1000 / HZ for r in matched),
            "early_event_end_count": sum(r["end_error_ms"] < -1000 / HZ for r in matched),
            "matched_repetitions": matched}


def exact_cycle_timing_failures(comparison):
    """Return user-visible failures for one live event per completed cycle."""
    failures = []
    if comparison["accepted_live_count"] != comparison["expected_reps"]:
        failures.append(
            f"accepted live {comparison['accepted_live_count']}/{comparison['expected_reps']}"
        )
    if not comparison["one_to_one_coverage"]:
        failures.append(
            "one-to-one coverage failed "
            f"(missing={comparison['missing_repetition_indices']}, "
            f"extra={comparison['extra_live_event_indices']})"
        )
    if comparison["early_emission_count"]:
        failures.append(
            f"{comparison['early_emission_count']} event(s) emitted more than one sample before cycle end"
        )
    if comparison["offline_flush_count"]:
        failures.append(f"{comparison['offline_flush_count']} event(s) only appeared during offline flush")
    return failures


def fingerprint_sources(root, paths):
    root = Path(root)
    hashes = {str(Path(p).relative_to(root)): digest(p) for p in sorted(paths)}
    return hashlib.sha256(json_bytes(hashes)).hexdigest(), hashes


def engine_sources():
    paths = list((REPO / "core/src/main").rglob("*.kt"))
    paths += [REPO / p for p in (
        "core/src/test/kotlin/dev/kyungmin/watchcoach/core/VirtualWatchReplayTest.kt",
        "wear/src/main/kotlin/dev/kyungmin/watchcoach/wear/WearWorkoutService.kt",
        "core/build.gradle.kts", "build.gradle.kts", "settings.gradle.kts",
        "tools/replay_virtual_watch_pilot.py",
    )]
    return fingerprint_sources(REPO, paths)


def read_events(path):
    integer = {"emitted_at_ns", "start_ns", "turnaround_ns", "end_ns", "duration_ms"}
    floating = {"peak_motion_rate", "motion_displacement", "trajectory_spread", "confidence"}
    with path.open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return [{k: int(v) if k in integer else float(v) if k in floating else v == "true" if k == "accepted" else v
             for k, v in row.items()} for row in rows]


def replay_cases(case_ids, gradle, java_home):
    revision, sources = engine_sources()
    cases = []
    for case_id in case_ids:
        if Path(case_id).name != case_id:
            raise ValueError("Case IDs must not contain paths")
        case = WORK / case_id
        manifest = verify_case(case)
        truth = json.loads((case / "truth.json").read_text())
        validate_truth(manifest, truth)
        cases.append((case, manifest, truth))
    if not cases:
        raise ValueError("No indexed synthetic cases")
    log = WORK / f"replay-{revision[:16]}.log"
    with tempfile.TemporaryDirectory(prefix=".replay-", dir=WORK) as folder:
        staging = Path(folder)
        index = staging / "inputs.tsv"
        with index.open("w") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["case_path", "exercise_id", "prep_end_ns", "capture_sha256", "truth_sha256", "output_path"])
            for case, manifest, truth in cases:
                writer.writerow([case, truth["exercise_id"], truth["preparation"]["end_ns"],
                                 manifest["files"]["capture.kcs"], manifest["files"]["truth.json"], staging / case.name])
        env = dict(os.environ, JAVA_HOME=str(java_home), WATCHCOACH_VIRTUAL_WATCH_INDEX=str(index))
        sdk = java_home.parent.parent.parent / "android-sdk"
        if sdk.is_dir():
            env.setdefault("ANDROID_SDK_ROOT", str(sdk))
        command = [str(gradle), ":core:test", "--tests", "dev.kyungmin.watchcoach.core.VirtualWatchReplayTest", "--console=plain"]
        print("Replaying", len(cases), "synthetic case(s) with unchanged core; log:", log.name, flush=True)
        with log.open("w") as handle:
            process = subprocess.run(command, cwd=REPO, env=env, stdout=handle, stderr=subprocess.STDOUT)
        if process.returncode:
            raise RuntimeError(f"Selected Kotlin test failed; inspect {log}")
        if engine_sources() != (revision, sources):
            raise RuntimeError("Engine source changed during replay; no result published")
        for case, manifest, truth in cases:
            verify_case(case)
            output = staging / case.name
            stats = dict(csv.reader((output / "stats.tsv").read_text().splitlines(), delimiter="\t"))
            events = read_events(output / "events.tsv")
            comparison = compare_events(truth, events)
            result = {"schema": 1, "source": "synthetic", "case_id": case.name,
                      "exercise_id": truth["exercise_id"], "engine_revision": revision,
                      "motion_lane": truth["motion_lane"], "motion_provenance": manifest["motion_provenance"],
                      "engine_source_sha256": sources, "capture_sha256": digest(case / "capture.kcs"),
                      "truth_sha256": digest(case / "truth.json"), "manifest_sha256": digest(case / "manifest.json"),
                      "baseline": "production generic detector plus production vertical-amplitude filter",
                      "preparation_policy": "skip preparation including boundary; beginCounting before first working sample, as in Wear service",
                      "offline_flush_policy": "reported separately; never included in live count",
                      "matching_policy": "scheduled cycle containing detector turnaround, nearest turnaround wins duplicates",
                      "stats": stats, "comparison": comparison, "events": events,
                      "limitations": ["Synthetic signal, no real Watch8 validation or visual approval",
                          "C2 sensor path is a diagnostic variation, not the viewer-linear path or physical truth",
                          "No learned pattern, start gate, set-end gate, post-target guard or service lifecycle replay",
                          "Ending is static, without putting weights down", "Same repeated ideal animation, no noise or timing variation",
                          "PC-published V5 source, not a verified current phone asset match"]}
            destination = case / "replays" / revision
            encoded = json_bytes(result)
            if destination.exists():
                if (destination / "result.json").read_bytes() != encoded:
                    raise ValueError("Existing replay differs; not overwriting an immutable result")
            else:
                destination.parent.mkdir(exist_ok=True)
                temporary = destination.parent / (".publishing-" + revision)
                temporary.mkdir()
                (temporary / "result.json").write_bytes(encoded)
                shutil.copyfile(output / "events.tsv", temporary / "events.tsv")
                temporary.rename(destination)
            print(case.name, "live", comparison["accepted_live_count"], "/", comparison["expected_reps"],
                  "rejected", comparison["rejected_live_count"], "flush_only", comparison["offline_flush_count"],
                  "early", comparison["early_emission_count"], "one_to_one", comparison["one_to_one_coverage"], flush=True)
    return revision


def main():
    toolchain = REPO.parent / "안드로이드-에뮬레이터"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", help="Defaults to the existing pilot-cases.json; never regenerates captures")
    parser.add_argument("--require-exact-cycle-timing", action="store_true",
                        help="Fail unless every truth cycle gets exactly one live event at its completed-return boundary")
    parser.add_argument("--gradle", type=Path, default=toolchain / "gradle-8.11.1/bin/gradle")
    parser.add_argument("--java-home", type=Path, default=toolchain / "jdk17/Contents/Home")
    args = parser.parse_args()
    case_ids = args.cases or json.loads((WORK / "pilot-cases.json").read_text())["cases"]
    revision = replay_cases(case_ids, args.gradle, args.java_home)
    if args.require_exact_cycle_timing:
        failures = []
        for case_id in case_ids:
            result = json.loads((WORK / case_id / "replays" / revision / "result.json").read_text())
            failures.extend(f"{case_id}: {failure}"
                            for failure in exact_cycle_timing_failures(result["comparison"]))
        if failures:
            print("EXACT CYCLE TIMING FAILED", flush=True)
            for failure in failures:
                print(" -", failure, flush=True)
            raise SystemExit(1)
    print("ENGINE", revision)


if __name__ == "__main__":
    main()
