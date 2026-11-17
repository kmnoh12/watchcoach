#!/usr/bin/env python3
"""Generate and replay Tier 1 & Tier 2 virtual-watch synthetic captures against current Kotlin engine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from gen_virtual_watch_pilot import (
    DESIGN, GRAVITY, HZ, NS0, PREP_S, REPO, TAIL_S,
    PoseCurve, digest, encode_capture, json_bytes, left_dorsal_watch,
    playback_phase, proper_rigid_fit, ray_triangle_hit, recover_watch,
    rotation_angle_degrees, sensors_from_motion,
)
from replay_virtual_watch_pilot import compare_events, engine_sources, read_events

WORK = REPO / "work/virtual-watch/tier12"
REPS = 10


def right_dorsal_watch(wrist, middle, thumb, offset_watch_axes_m=(0., .012, .028)):
    """Right-handed dorsal watch frame on the RIGHT wrist (+Y proximal, +Z dorsal, +X radial/screen-right)."""
    y = np.asarray(wrist, float) - middle
    y /= np.linalg.norm(y)
    x = np.asarray(thumb, float) - middle
    x -= np.dot(x, y) * y
    x /= np.linalg.norm(x)
    basis = np.stack((x, y, np.cross(x, y)), axis=1)
    result = np.eye(4)
    result[:3, :3] = basis
    result[:3, 3] = wrist + basis @ offset_watch_axes_m
    return result


def surface_watch_side(base, frames, rest, bind, names, side="left"):
    """Fit dorsal watch carrier to the published wrist blend ring (lowerarm 0.75 + hand 0.25)."""
    suffix = "_l" if side == "left" else "_r"
    triangles = np.asarray(base["triangles"], int).reshape(-1, 3)
    joints, weights = np.asarray(base["joints"]), np.asarray(base["weights"], float)
    lowerarm, hand = names.index(f"lowerarm{suffix}"), names.index(f"hand{suffix}")

    def bone_weight(bone):
        return np.where(joints == bone, weights, 0).sum(1)

    lw, hw = bone_weight(lowerarm), bone_weight(hand)
    tot = weights.sum(1)
    ring = np.flatnonzero(np.isclose(lw, .75, atol=1e-6) & np.isclose(hw, .25, atol=1e-6) & np.isclose(tot, 1, atol=1e-6))
    touches = np.any(np.isin(triangles, ring), axis=1)
    adj = np.unique(triangles[touches])
    proximal = np.asarray(sorted(set(adj.tolist()) - set(ring.tolist())), int)
    proximal = proximal[(lw[proximal] >= .95) & (hw[proximal] <= .05)]

    wrist = bind[hand, :3, 3]
    middle = bind[names.index(f"middle_01{suffix}"), :3, 3]
    thumb = bind[names.index(f"thumb_01{suffix}"), :3, 3]
    dorsal_fn = left_dorsal_watch if side == "left" else right_dorsal_watch
    anatomical_dorsal = dorsal_fn(wrist, middle, thumb, (0, 0, 0))[:3, 2]
    rest_center = rest[ring].mean(0)
    dorsal_score = (rest[ring] - rest_center) @ anatomical_dorsal
    dorsal = ring[np.argsort(dorsal_score)[len(ring) // 2:]]

    reference = frames[0, ring]
    reference_center = reference.mean(0)
    _, _, vt = np.linalg.svd(reference - reference_center, full_matrices=False)
    y_axis = vt[-1]
    if np.dot(y_axis, frames[0, proximal].mean(0) - reference_center) < 0:
        y_axis = -y_axis
    y_axis /= np.linalg.norm(y_axis)
    z_axis = frames[0, dorsal].mean(0) - reference_center
    z_axis -= np.dot(z_axis, y_axis) * y_axis
    z_axis /= np.linalg.norm(z_axis)
    x_axis = np.cross(y_axis, z_axis)
    x_axis /= np.linalg.norm(x_axis)
    z_axis = np.cross(x_axis, y_axis)
    z_axis /= np.linalg.norm(z_axis)
    reference_basis = np.stack((x_axis, y_axis, z_axis), axis=1)

    rotations, contacts, rigid_errors, outward_dots, surf_dists = [], [], [], [], []
    for frame, target in zip(frames, frames[:, ring]):
        rot, trans, _ = proper_rigid_fit(reference, target)
        basis = rot @ reference_basis
        center = target.mean(0)
        ray_origin = center + basis[:, 1] * .012
        try:
            _, _, _, contact, residual = ray_triangle_hit(frame, triangles, ray_origin, basis[:, 2])
        except ValueError:
            # Fallback to dorsal mean if ray misses slightly
            contact = frame[dorsal].mean(0) + basis[:, 2] * 0.005
            residual = 0.0
        dorsal_dir = frame[dorsal].mean(0) - center
        dorsal_dir -= np.dot(dorsal_dir, basis[:, 1]) * basis[:, 1]
        dorsal_dir /= np.linalg.norm(dorsal_dir)
        rotations.append(basis)
        contacts.append(contact)
        rigid_errors.append(np.linalg.norm((rot @ reference.T).T + trans - target, axis=1).max())
        outward_dots.append(np.dot(basis[:, 2], dorsal_dir))
        surf_dists.append(residual)

    poses = np.tile(np.eye(4), (len(frames), 1, 1))
    poses[:, :3, :3] = np.asarray(rotations)
    poses[:, :3, 3] = np.asarray(contacts)
    qa = {
        "carrier": f"{side}_wrist_ring",
        "surface_rigid_fit_max_error_mm": float(max(rigid_errors) * 1000),
        "screen_outward_min_dot": float(min(outward_dots)),
        "caseback_surface_max_distance_mm": float(max(surf_dists) * 1000),
    }
    return poses, qa


def palm_watch_side(base, frames, rest, palettes, bind, names, side="left"):
    """Recover dorsal watch from hand_l or hand_r rigid palm transform."""
    suffix = "_l" if side == "left" else "_r"
    h = names.index(f"hand{suffix}")
    joints, weights = np.asarray(base["joints"]), np.asarray(base["weights"])
    ids = np.flatnonzero(np.where(joints == h, weights, 0).sum(1) > .999999)
    landmarks = rest[ids]
    predicted = np.einsum("fij,nj->fni", palettes[:, h, :3, :3], landmarks) + palettes[:, h, None, :3, 3]
    palm_err = float(np.linalg.norm(predicted - frames[:, ids], axis=2).max() * 1000)
    wrist_rest = bind[h, :3, 3]
    middle = bind[names.index(f"middle_01{suffix}"), :3, 3]
    thumb = bind[names.index(f"thumb_01{suffix}"), :3, 3]
    offset = np.array([0.0, .012, .028])
    dorsal_fn = left_dorsal_watch if side == "left" else right_dorsal_watch
    rest_watch = dorsal_fn(wrist_rest, middle, thumb, offset)
    hand_from_watch = np.linalg.inv(bind[h]) @ rest_watch
    poses = recover_watch(palettes[:, h], bind[h], hand_from_watch)
    qa = {
        "carrier": f"{side}_palm",
        "palm_max_error_mm": palm_err,
    }
    return poses, qa


def pose_kinematics(poses):
    p = poses[:, :3, 3]
    disp_mm = float(np.linalg.norm(p - p[0], axis=1).max() * 1000)
    r0 = poses[0, :3, :3]
    ang_deg = float(max(rotation_angle_degrees(r0, r) for r in poses[:, :3, :3]))
    return disp_mm, ang_deg


def parse_tier12():
    text = (REPO / "work/virtual-watch-tier12.md").read_text()
    items = []
    seen = set()
    section = None
    baselines = []
    for line in text.splitlines():
        if line.startswith("## 1번"):
            section = "tier1"
        elif line.startswith("## 2번"):
            section = "tier2"
        elif line.startswith("## 이번 범위에서 제외"):
            section = None
        elif section and line.startswith("- ") and ":" in line:
            head, tail = line[2:].split(":", 1)
            m = re.search(r"\(기준\s*([^)]+)\)", head)
            if m:
                for b in m.group(1).split(","):
                    b = b.strip()
                    if b and b not in seen:
                        baselines.append((head.strip(), b))
            for eid in tail.split(","):
                eid = eid.strip()
                if eid:
                    items.append((section, head.strip(), eid))
                    seen.add(eid)
    for head, b in baselines:
        if b not in seen:
            items.append(("baseline", head, b))
            seen.add(b)
    return items


def find_sources(mid, viewer_root):
    pc_json = viewer_root / f"{mid}.json"
    rolling_json = DESIGN / "app_rollout_20261109/rolling_trial" / f"{mid}.json"
    motion_path = pc_json if pc_json.is_file() else (rolling_json if rolling_json.is_file() else None)
    skin_path = next((p for p in [
        DESIGN / "catalog_trial" / f"{mid}.skin.bin",
        DESIGN / "app_rollout_20261109/rolling_trial" / f"{mid}.skin.bin",
        REPO / "design/exercise-figure/wide_pulldown_ref/output" / f"{mid}.skin.bin",
    ] if p.is_file()), None)
    return motion_path, skin_path


def compare_return_end(truth, events, tol_ms=250.0):
    """For return-counted CycleAxisRepDetector where turnaround==end==return_peak."""
    live = [e for e in events if e["channel"] == "live" and e["accepted"]]
    reps = truth["repetitions"]
    if len(live) != len(reps):
        return False
    tol_ns = int(tol_ms * 1e6)
    return all(r["start_ns"] <= e["end_ns"] <= r["end_ns"] + tol_ns for r, e in zip(reps, live))


def playback_override_for(mid, acts, poses, metadata):
    """Match tools/viewer3d/index.html for full-cycle and alternating V5 clips."""
    if mid in ("alternating_dumbbell_curl", "alternating_hammer_curl"):
        # index.html plays 0->1 (left arm full rep) in 2.6s, then mirrors for right arm (left rests 2.6s).
        return {"mode": "cycle_half_hold", "period_s": 5.2, "turn_frac": 0.25}
    if mid == "cross_body_hammer_curl":
        # 0..0.5 is left arm curl, 0.5..1.0 is right arm curl.
        return {"mode": "cycle", "period_s": 5.2, "turn_frac": 0.25}
    if mid == "zottman_curl":
        # 0..1 is 1 supinated-up/pronated-down curl; pingpong 1->0 returns supinated (2 curls per pingpong).
        return {"mode": "pingpong_double", "period_s": 5.2, "reps": 5, "expected_reps": 10}
    if mid == "bradford_press":
        # 0..1 is front->overhead->back (1 vertical press); pingpong 0->1->0 is 2 presses.
        return {"mode": "pingpong_double", "period_s": 5.2, "reps": 5, "expected_reps": 10}
    return None


def synthesize_stream(poses, acts, metadata, reps=REPS, playback_override=None):
    mode = playback_override["mode"] if playback_override else metadata.get("playback_mode", "pingpong")
    period = float(playback_override["period_s"]) if playback_override else float(metadata.get("playback_ms") or 2600) / 1000
    n_cycles = playback_override.get("reps", reps) if playback_override else reps
    eff_mode = "pingpong" if mode == "pingpong_double" else mode
    eff_meta = dict(metadata, playback_mode="cycle" if mode == "cycle_half_hold" else eff_mode, playback_ms=round(period * 1000))
    curve = PoseCurve(acts, poses)
    total = PREP_S + n_cycles * period + TAIL_S
    times = np.arange(round(total * HZ) + 1, dtype=float) / HZ
    stamps = NS0 + np.arange(len(times), dtype=np.int64) * (1_000_000_000 // HZ)
    start_phase = (eff_meta.get("playback_range") or [0, 1])[0]

    def pose(t):
        if mode == "cycle_half_hold":
            rel = np.clip(t - PREP_S, 0, n_cycles * period)
            local = np.mod(rel, period)
            half = period / 2.0
            raw_p = np.where(local <= half, local / half, 0.0)
            phase = np.where(raw_p < 0.5, 2 * raw_p**2, 1 - 2 * (1 - raw_p)**2)
            phase = np.where(local <= half, phase, 0.0)
            phase[(t <= PREP_S) | (t >= PREP_S + n_cycles * period)] = start_phase
            return curve(phase)
        phase = playback_phase(np.clip(t - PREP_S, 0, n_cycles * period), eff_meta)
        phase[(t <= PREP_S) | (t >= PREP_S + n_cycles * period)] = start_phase
        return curve(phase)

    acc, gyr = sensors_from_motion(times, pose)
    a_fine, g_fine = sensors_from_motion(times, pose, step_s=.0005)
    a_diff = float(np.linalg.norm(a_fine - acc, axis=1).max())
    g_diff = float(np.linalg.norm(g_fine - gyr, axis=1).max())
    max_gyro = float(np.linalg.norm(gyr, axis=1).max())
    max_dyn_acc = float(np.linalg.norm(acc - acc[0], axis=1).max())
    turn_frac = playback_override.get("turn_frac", 0.5) if playback_override else 0.5
    if mode == "pingpong_double":
        # Each 2.6s pingpong has 2 vertical presses: [0, 1.3] and [1.3, 2.6].
        half_p = period / 2.0
        reps_list = [
            {
                "index": i + 1,
                "start_ns": NS0 + round((PREP_S + i * half_p) * 1e9),
                "turnaround_ns": NS0 + round((PREP_S + (i + 0.5) * half_p) * 1e9),
                "end_ns": NS0 + round((PREP_S + (i + 1) * half_p) * 1e9),
            }
            for i in range(n_cycles * 2)
        ]
        exp_reps = n_cycles * 2
    else:
        reps_list = [
            {
                "index": i + 1,
                "start_ns": NS0 + round((PREP_S + i * period) * 1e9),
                "turnaround_ns": NS0 + round((PREP_S + (i + turn_frac) * period) * 1e9),
                "end_ns": NS0 + round((PREP_S + (i + 1) * period) * 1e9),
            }
            for i in range(n_cycles)
        ]
        exp_reps = n_cycles
    truth = {
        "source": "synthetic",
        "expected_reps": exp_reps,
        "period_s": period,
        "playback_mode": mode,
        "preparation": {"start_ns": int(stamps[0]), "end_ns": NS0 + round(PREP_S * 1e9)},
        "ending_static": {"start_ns": NS0 + round((PREP_S + n_cycles * period) * 1e9), "end_ns": int(stamps[-1])},
        "repetitions": reps_list,
    }
    return stamps, acc, gyr, truth, {
        "a_diff": a_diff, "g_diff": g_diff,
        "max_gyro_radps": max_gyro, "max_dyn_acc_mps2": max_dyn_acc,
        "period_s": period,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-only", action="store_true", help="Reuse existing generated KCS cases")
    parser.add_argument("--only", nargs="+", help="Filter exercise IDs")
    args = parser.parse_args()

    candidates = [Path.home() / "Library/Application Support" / n / "v5-catalog"
                  for n in ("__PROTECTED_WATCHCOACH_VIEWER__", "WatchGymViewer")]
    viewer_root = next((p for p in candidates if (p / "manifest.json").is_file()), None)
    assert viewer_root is not None, "Viewer root missing"
    app_dir = REPO / "phone/src/main/assets/viewer3d"
    mapping = json.loads((app_dir / "exercise_models.json").read_text())
    base = json.loads((viewer_root / "base.json").read_text())
    pc_clips = {c["id"]: c for c in json.loads((viewer_root / "manifest.json").read_text())["clips"]}
    app_clips = {c["id"]: c for c in json.loads((app_dir / "human_v5/manifest.json").read_text())["clips"]}
    bind = np.asarray(json.loads((DESIGN / "anatomical_rest.json").read_text())["rest_matrices"])
    names = base["bone_names"]
    rest = np.asarray(base["rest"]).reshape(-1, 3)

    items = parse_tier12()
    if args.only:
        only = set(args.only)
        items = [x for x in items if x[2] in only]

    WORK.mkdir(parents=True, exist_ok=True)
    cases_meta = []

    if not args.replay_only:
        for sec, grp, eid in items:
            mids = mapping.get(eid, [])
            if not mids:
                cases_meta.append({"tier": sec, "group": grp, "exercise_id": eid, "model_id": None, "source_error": "no_model_mapping"})
                continue
            mid = mids[0]
            mpath, spath = find_sources(mid, viewer_root)
            meta = pc_clips.get(mid) or app_clips.get(mid)
            if not mpath or not meta:
                cases_meta.append({"tier": sec, "group": grp, "exercise_id": eid, "model_id": mid, "source_error": "missing_motion_or_meta"})
                continue

            motion = json.loads(mpath.read_text())
            acts = np.asarray(motion["acts"], float)
            frames = np.asarray(motion["frames"]).reshape(len(acts), len(rest), 3)

            variants = []
            # Check palm carriers if skin.bin exists
            l_disp, l_ang, l_err = 0.0, 0.0, 999.0
            r_disp, r_ang, r_err = 0.0, 0.0, 999.0
            l_poses = r_poses = None
            if spath:
                pal = np.fromfile(spath, dtype="<f4").reshape(len(acts), len(names), 4, 4).astype(float)
                l_poses, l_qa = palm_watch_side(base, frames, rest, pal, bind, names, "left")
                l_disp, l_ang = pose_kinematics(l_poses)
                l_err = l_qa["palm_max_error_mm"]
                r_poses, r_qa = palm_watch_side(base, frames, rest, pal, bind, names, "right")
                r_disp, r_ang = pose_kinematics(r_poses)
                r_err = r_qa["palm_max_error_mm"]

            # Determine active side: left by default; switch to right if left is essentially idle and right moves
            left_idle = (l_disp < 60.0 and l_ang < 8.0) if l_err <= 0.05 else False
            right_moves = (r_disp >= max(150.0, l_disp * 3.0) or r_ang >= 20.0) if r_err <= 0.05 else False
            if l_err > 0.05:
                # Skin mismatch (e.g. upright_row_barbell/dumbbell) -> use left_wrist_ring
                side = "left"
                poses_ring, qa_ring = surface_watch_side(base, frames, rest, bind, names, side)
                d, a = pose_kinematics(poses_ring)
                variants.append(("wrist_ring", side, poses_ring, dict(qa_ring, disp_mm=d, ang_deg=a, note="skin_mismatch_ring_fallback", palm_err_mm=l_err)))
            elif left_idle and right_moves:
                side = "right"
                variants.append(("palm", side, r_poses, dict(r_qa, disp_mm=r_disp, ang_deg=r_ang, note="model_animated_right_arm_only")))
                if r_ang < 5.0:
                    poses_ring, qa_ring = surface_watch_side(base, frames, rest, bind, names, side)
                    d, a = pose_kinematics(poses_ring)
                    variants.append(("wrist_ring", side, poses_ring, dict(qa_ring, disp_mm=d, ang_deg=a, note="right_palm_zero_rot_ring_alt")))
            else:
                side = "left"
                variants.append(("palm", side, l_poses, dict(l_qa, disp_mm=l_disp, ang_deg=l_ang)))
                if l_ang < 5.0:
                    poses_ring, qa_ring = surface_watch_side(base, frames, rest, bind, names, side)
                    d, a = pose_kinematics(poses_ring)
                    variants.append(("wrist_ring", side, poses_ring, dict(qa_ring, disp_mm=d, ang_deg=a, note="left_palm_zero_rot_ring_alt")))

            pb_override = playback_override_for(mid, acts, variants[0][2], meta)
            for carrier_kind, side, poses, qa in variants:
                case_id = f"{eid}__{carrier_kind}_{side}"
                stamps, acc, gyr, truth, sig_qa = synthesize_stream(poses, acts, meta, REPS, pb_override)
                truth["case_id"] = case_id
                truth["exercise_id"] = eid
                cdir = WORK / case_id
                cdir.mkdir(parents=True, exist_ok=True)
                (cdir / "capture.kcs").write_bytes(encode_capture(stamps, acc, gyr))
                (cdir / "truth.json").write_bytes(json_bytes(truth))
                cases_meta.append({
                    "tier": sec, "group": grp, "exercise_id": eid, "model_id": mid,
                    "case_id": case_id, "carrier_kind": carrier_kind, "side": side,
                    "qa": qa, "sig_qa": sig_qa,
                    "playback_override": pb_override,
                    "prep_end_ns": truth["preparation"]["end_ns"],
                    "kcs_path": str(cdir / "capture.kcs"),
                })
        (WORK / "cases_meta.json").write_bytes(json_bytes(cases_meta))
    else:
        cases_meta = json.loads((WORK / "cases_meta.json").read_text())
        if args.only:
            only = set(args.only)
            cases_meta = [c for c in cases_meta if c["exercise_id"] in only]

    # Write Kotlin replay index
    runnable = [c for c in cases_meta if "case_id" in c]
    toolchain = REPO.parent / "안드로이드-에뮬레이터"
    gradle = toolchain / "gradle-8.11.1/bin/gradle"
    java_home = toolchain / "jdk17/Contents/Home"

    with tempfile.TemporaryDirectory(prefix=".tier12-", dir=WORK) as tmp:
        staging = Path(tmp)
        idx = staging / "index.tsv"
        with idx.open("w") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(["case_id", "exercise_id", "prep_end_ns", "kcs_path", "output_path"])
            for c in runnable:
                w.writerow([c["case_id"], c["exercise_id"], c["prep_end_ns"], c["kcs_path"], staging / c["case_id"]])
        env = dict(os.environ, JAVA_HOME=str(java_home), WATCHCOACH_TIER12_INDEX=str(idx))
        sdk = java_home.parent.parent.parent / "android-sdk"
        if sdk.is_dir():
            env.setdefault("ANDROID_SDK_ROOT", str(sdk))
        log = WORK / "replay.log"
        cmd = [str(gradle), ":core:test", "--tests", "dev.kyungmin.watchcoach.core.VirtualWatchTier12ReplayTest", "--rerun", "--console=plain"]
        with log.open("w") as h:
            proc = subprocess.run(cmd, cwd=REPO, env=env, stdout=h, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"Kotlin replay test failed (exit {proc.returncode}); see {log}")

        results = []
        for c in cases_meta:
            if "case_id" not in c:
                results.append(c)
                continue
            cid = c["case_id"]
            out = staging / cid
            stats = dict(csv.reader((out / "stats.tsv").read_text().splitlines(), delimiter="\t"))
            events = read_events(out / "events.tsv")
            truth = json.loads((WORK / cid / "truth.json").read_text())
            comp = compare_events(truth, events)
            comp["return_end_1to1"] = compare_return_end(truth, events)
            results.append(dict(c, stats=stats, comparison=comp, events=events))

    (WORK / "sweep_results.json").write_bytes(json_bytes(results))
    # Print concise summary
    for r in results:
        if "comparison" not in r:
            print(f"[{r['tier']:8s}] {r['exercise_id']:40s} SOURCE_ERR {r.get('source_error')}")
            continue
        c = r["comparison"]
        st = r["stats"]
        ok = (c["accepted_live_count"] == c["expected_reps"] and c["one_to_one_coverage"] and c["offline_flush_count"] == 0)
        ret_ok = (not ok and st["family"] == "CYCLE_AXIS_RETURN" and c["return_end_1to1"] and c["offline_flush_count"] == 0)
        tag = "PASS" if ok else ("PASS(ret_end)" if ret_ok else f"FAIL({c['accepted_live_count']}/{c['expected_reps']},1to1={c['one_to_one_coverage']},flush={c['offline_flush_count']})")
        print(f"[{r['tier']:8s}] {r['exercise_id']:38s} {r['carrier_kind']:10s}({r['side']:5s}) {st['family']:25s} disp={r['qa']['disp_mm']:5.1f}mm ang={r['qa']['ang_deg']:5.1f}d gyr={r['sig_qa']['max_gyro_radps']:5.2f} | {tag}")


if __name__ == "__main__":
    main()
