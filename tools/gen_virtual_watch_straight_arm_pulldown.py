#!/usr/bin/env python3
"""Independent virtual-watch input oracle for straight_arm_pulldown (synthetic diagnosis only).

Truth is an explicit exercise cycle (start position -> straight-arm pull -> turnaround -> full return)
built from the published V5 clip's authored phase 0 -> 1 and the published viewer's ping-pong schedule.
No detector output, threshold, axis sign or peak is consulted while the truth is built.

Watch: left wrist, dorsal side; the display faces away from the skin and the sensor frame is rigid
to the watch. The frame reuses the pilot's verified dorsal anatomical basis (left_dorsal_watch) and
is carried by a rigid fit to the published hand vertices of this clip. Mounting and noise are not
physically calibrated; nothing here is Watch8 accuracy evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_virtual_watch_pilot import (  # noqa: E402
    NS0, REPO, PoseCurve, digest, encode_capture, json_bytes, left_dorsal_watch, sensors_from_motion,
)

EXERCISE_ID = "straight_arm_pulldown"
PLAYBACK_RANGE = (0.0, 1.0)  # authored start / pulled phase, read from the published manifest before any case
MODEL_ID = "cable_tower~h=high~g=straight~p=straight_arm"
APP_MAPPING = REPO / "phone/src/main/assets/viewer3d/exercise_models.json"
VIEWER_HTML = REPO / "tools/viewer3d/index.html"
HZ = 50
SAMPLE_NS = 1_000_000_000 // HZ
PREP_S = 3.0
TAIL_S = 3.0
BASE_PERIOD_S = 2.0  # the published viewer rep (REP = 2600 ms) is the authored cycle played as 0->1->0

CASES = ("continuous_10_clean", "continuous_10_tempo_variation", "return_boundary_hold",
         "ten_then_handle_down", "handle_down_only")

# case -> list of (pull_s, hold_s, return_s, amplitude). Amplitudes are phase fractions of the full
# 0 -> 1 authored travel; every case's truth states the exact times it used.
SCENARIOS = {
    "continuous_10_clean": [(1.0, 0.0, 1.0, 1.0)] * 10,
    "continuous_10_tempo_variation": [(1.0 + 0.08 * ((i % 3) - 1), 0.0, 1.0 + 0.06 * ((i % 2) * 2 - 1), 1.0)
                                      for i in range(10)],
    "return_boundary_hold": [(1.0, 0.3, 1.0, 1.0)] * 10,
    "ten_then_handle_down": [(1.0, 0.0, 1.0, 1.0)] * 10,
    "handle_down_only": [],
}
NOISE = {"continuous_10_tempo_variation": (0.35, 0.015)}  # m/s^2, rad/s; not physically calibrated
HANDLE_DOWN = (1.0, 0.2, 1.0)  # phase 1 -> 0 progress, then stillness

MOUNT_STATEMENT = ("왼손목 손등 쪽 착용. +Z는 피부에서 바깥으로(화면이 보이는 쪽), +Y는 손목에서 팔꿈치 방향, "
                   "+X는 왼손 기준 화면 오른쪽(자쪽). 손목 뼈에 딱 맞춰 고정됐다고 가정한 합성 장착이라 실제 "
                   "Watch8 장착오차·부착 위치는 반영하지 않는다.")


def catalog_root() -> pathlib.Path:
    return pathlib.Path.home() / "Library/Application Support/WatchGymViewer/v5-catalog"


def hand_rotation(rest_hand_points, target):
    a, b = np.asarray(rest_hand_points, float), np.asarray(target, float)
    ca, cb = a.mean(0), b.mean(0)
    u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(vt.T @ u.T)
    rotation = vt.T @ correction @ u.T
    if not np.isclose(np.linalg.det(rotation), 1, atol=2e-7):
        raise ValueError("Palm fit produced a reflection")
    residual = float(np.linalg.norm((a - ca) @ rotation.T + cb - b, axis=1).max() * 1000)
    return rotation, cb - rotation @ ca, residual


def load_clip():
    global PLAYBACK_RANGE
    root = catalog_root()
    base = json.loads((root / "base.json").read_text())
    motion = json.loads((root / f"{MODEL_ID}.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    clip_meta = next(c for c in manifest["clips"] if c["id"] == MODEL_ID)
    names = base["bone_names"]
    rest = np.asarray(base["rest"]).reshape(-1, 3)
    acts = np.asarray(motion["acts"], float)
    frames = np.asarray(motion["frames"]).reshape(len(acts), len(rest), 3)
    viewer = VIEWER_HTML.read_text()
    if "t<.5 ? ease(t*2) : ease((1-t)*2)" not in viewer or "REP = 2600" not in viewer:
        raise ValueError("Published viewer no longer plays a ping-pong 0->1->0 rep")
    h, middle, thumb = names.index("hand_l"), names.index("middle_01_l"), names.index("thumb_01_l")
    joints, weights = np.asarray(base["joints"]), np.asarray(base["weights"], float)
    hand_ids = np.flatnonzero(np.where(joints == h, weights, 0).sum(1) > .999999)
    if len(hand_ids) < 3:
        raise ValueError("No rigid hand vertices in the published base")
    bind = np.asarray(json.loads((REPO / "design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild"
                                  "/anatomical_rest.json").read_text())["rest_matrices"])
    rest_watch = left_dorsal_watch(bind[h, :3, 3], bind[middle, :3, 3], bind[thumb, :3, 3], (0.0, .012, .028))
    hand_from_watch = np.linalg.inv(bind[h]) @ rest_watch
    poses, fit_errors = [], []
    for f in range(len(acts)):
        rotation, translation, residual = hand_rotation(rest[hand_ids], frames[f, hand_ids])
        fit_errors.append(residual)
        world_from_hand = np.eye(4)
        world_from_hand[:3, :3], world_from_hand[:3, 3] = rotation, translation
        poses.append(world_from_hand @ hand_from_watch)
    poses = np.asarray(poses)
    if max(fit_errors) > .01:
        raise ValueError(f"Hand is not rigid in the published clip: {max(fit_errors):.4f} mm")
    hand = names.index("hand_l")
    arm = frames[:, hand] - frames[:, names.index("upperarm_l")]
    rng = clip_meta.get("playback_range") or [float(acts[0]), float(acts[-1])]
    if not (0.0 <= rng[0] < rng[1] <= 1.0) or not np.any(np.isclose(acts, rng[0])) or not np.any(np.isclose(acts, rng[1])):
        raise ValueError(f"Published playback range is not on authored phases: {rng}")
    PLAYBACK_RANGE = (float(rng[0]), float(rng[1]))
    ext = float(np.linalg.norm(arm, axis=1).max())
    if ext < .20:
        raise ValueError(f"Arm is not straight in the published clip ({ext * 1000:.0f} mm)")
    travel = float(np.linalg.norm(frames[:, hand] - frames[0, hand], axis=1).max() * 1000)
    return {
        "acts": acts, "poses": poses, "metadata": clip_meta, "hand_ids": hand_ids.tolist(),
        "hand_from_watch": hand_from_watch.tolist(),
        "hand_fit_max_error_mm": float(max(fit_errors)),
        "arm_max_extension_m": ext, "hand_travel_from_phase0_mm": travel,
        "sources": {
            "base": {"path": str((root / "base.json")), "sha256": digest(root / "base.json")},
            "clip": {"path": str((root / f"{MODEL_ID}.json")), "sha256": digest(root / f"{MODEL_ID}.json")},
            "manifest": {"path": str(root / "manifest.json"), "sha256": digest(root / "manifest.json")},
            "viewer": {"path": str(VIEWER_HTML), "sha256": digest(VIEWER_HTML)},
            "anatomical_rest": {"path": str(REPO / "design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild"
                                           "/anatomical_rest.json"),
                                "sha256": digest(REPO / "design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild"
                                                 "/anatomical_rest.json")},
        },
    }


def ease(t):
    t = np.clip(np.asarray(t, float), 0.0, 1.0)
    return np.where(t < .5, 2 * t * t, 1 - np.power(-2 * t + 2, 2) / 2)


def ease_rate(t):
    t = np.clip(np.asarray(t, float), 0.0, 1.0)
    return np.where(t < .5, 4 * t, 4 * (1 - t))


def coarse_progress(coarse_s, pull, hold, ret):
    """Authored progress (the published viewer's ease) for the elapsed time inside one cycle."""
    if coarse_s <= pull:
        return ease(np.array([coarse_s / pull]))[0]
    if coarse_s <= pull + hold:
        return 1.0
    return 1.0 - ease(np.array([(coarse_s - pull - hold) / ret]))[0]


def cycle_clock(spec, amplitude, samples_per_second=2000):
    """One cycle on a normalised clock; authored progress at each clock tick.

    Normalised clock 0..1 runs through the cycle; the pull, optional hold and return take their explicit share of it,
    and the published viewer ease shapes each pull and return. Clock nodes therefore sit exactly at the authored
    turnaround, the end of a hold and the full return, whatever the segment lengths. Samples later land on these
    nodes by choosing the cycle grid length from the 50 Hz lattice.
    """
    if not spec:
        return np.array([0.0]), np.array([0.0])
    fractions = [(pull, hold, ret, amp) for pull, hold, ret, amp in
                 ((p / (p + h + r), h / (p + h + r), r / (p + h + r), amp) for p, h, r, amp in spec)]
    starts = np.cumsum([0.0] + [p + h + r for p, h, r, _ in fractions])
    x = np.arange(samples_per_second + 1) / samples_per_second
    phases = np.zeros(len(x))
    k = np.clip(np.searchsorted(starts, x, side="right") - 1, 0, len(fractions) - 1)
    for i, value in enumerate(x):
        if value >= starts[-1]:
            phases[i] = 0.0
            continue
        pull, hold, ret, amp = fractions[k[i]]
        local = value - starts[k[i]]
        if local <= pull:
            phases[i] = amplitude * amp * ease(np.array([local / pull if pull > 0 else 1.0]))[0]
        elif local <= pull + hold:
            phases[i] = amplitude * amp
        else:
            phases[i] = amplitude * amp * (1.0 - ease(np.array([(local - pull - hold) / ret if ret > 0 else 1.0]))[0])
    return x, phases


SPEC_TAIL_S = 0.5  # held pulled pose after the last return before stillness
NOMINAL_CYCLE = 2.0  # s, published viewer rep length; each cycle is snapped up to whole 50 Hz samples if needed


RAC_EDGE = 0.86  # share of each half spent ramping; middle speed is the authored peak speed


def authored_halves(beats, start_phase, pulled_phase, down_total):
    """(start_s, end_s, phase_start, phase_end) for every half of the authored cycle."""
    halves = []
    clock = 0.0
    halves.append((0.0, 0.0, start_phase, start_phase))
    for pull, hold, ret, amp in beats:
        span = amp * (pulled_phase - start_phase)
        halves.append((clock, clock + pull, start_phase, start_phase + span))
        clock += pull
        if hold > 0.0:
            halves.append((clock, clock + hold, start_phase + span, start_phase + span))
            clock += hold
        halves.append((clock, clock + ret, start_phase + span, start_phase))
        clock += ret
    if down_total > 0.0:
        # Pull-start -> held position -> phase 0, the same authored down move the pull takes.
        span = (pulled_phase - start_phase) / 2.0
        halves.append((clock, clock + down_total / 2.0, start_phase, start_phase + span))
        halves.append((clock + down_total / 2.0, clock + down_total, start_phase + span, start_phase))
    return halves


def bump(u, edge=RAC_EDGE):
    """C2 phase profile: cosine speed ramp in and out, linear speed across the middle; zero speed at both ends."""
    u = np.clip(np.asarray(u, float), 0.0, 1.0)
    e = edge / 2.0

    def integral(v):
        v = np.asarray(v, float)
        return np.where(v < e, v * v / (4 * e), np.where(v <= 1 - e, v / 2 - e / 4, 1 - (1 - v) * (1 - v) / (4 * e)))
    return integral(u) / integral(1.0)


def phase_on_halves(times_s, halves, start_phase):
    # Segments are merged in time order, so the last defined segment wins at a shared boundary.
    out = np.full(len(times_s), start_phase)
    for start, stop, p0, p1 in sorted((h for h in halves if h[1] > h[0]), key=lambda h: h[0]):
        inside = (times_s >= start - 1e-12) & (times_s <= stop + 1e-12)
        if not inside.any():
            continue
        duration = stop - start
        total = float(bump(np.array([1.0]))[0])
        out[inside] = p0 + (p1 - p0) * bump((times_s[inside] - start) / duration) / total
    return out


def build_case(root, name, clip):
    curve = PoseCurve(clip["acts"], clip["poses"])
    spec = SCENARIOS[name]
    handle_down = name in ("ten_then_handle_down", "handle_down_only")
    start_phase, pulled_phase = PLAYBACK_RANGE
    snap = lambda seconds: round(seconds * HZ) / HZ
    beats = [(snap(p), snap(h), snap(r), amp) for p, h, r, amp in spec]
    period = float(np.mean([p + h + r for p, h, r, _ in beats])) if beats else NOMINAL_CYCLE
    down_total = sum(HANDLE_DOWN) if handle_down else 0.0
    lead = 0.0 if beats else 0.02
    halves = authored_halves(beats, start_phase, pulled_phase, down_total)
    if beats and down_total > 0.0:
        # A finished set leaves from the pull-start position (where the last rep's pull began), not from phase 0,
        # so the set-down repeats that authored down move: pull-start -> held position -> phase 0 for one slot.
        rep_end = sum(p + h + r for p, h, r, _ in beats)
        halves = [h for h in halves if h[0] < rep_end - 1e-9]
    if not beats:
        halves = [(lead + t0, lead + t1, p0, p1) for t0, t1, p0, p1 in halves[1:]]
        lead = 0.0
    motion_end = sum(p + h + r for p, h, r, _ in beats) + down_total
    hold_end = motion_end + (0.0 if down_total > 0.0 else SPEC_TAIL_S)
    count = int(round((hold_end + TAIL_S) * HZ)) + 1
    lattice = np.arange(count, dtype=np.int64) * SAMPLE_NS
    stamps = NS0 + lattice
    times = lattice / 1e9
    phases = phase_on_halves(times, halves, start_phase)
    if beats and down_total <= 0.0:
        phases[(times > motion_end) & (times <= hold_end)] = pulled_phase
    if not beats:
        phases[times <= lead] = pulled_phase

    # Acceleration probe: the same authored halves with a C2 speed profile, so a 1 ms step differentiates cleanly.
    static_phase = start_phase
    last_stop = max((h[1] for h in halves), default=0.0)

    def smooth(values):
        elapsed = values - NS0 / 1e9
        out = np.where((elapsed >= 0.0) & (elapsed <= last_stop), phase_on_halves(elapsed, halves, start_phase), static_phase)
        return curve(out)

    acceleration, gyro = sensors_from_motion(times, smooth)
    stable = {}
    for step in (.0005, .0001, .00005):
        _, probe = sensors_from_motion(times, smooth, step_s=step)
        stable[str(step)] = float(np.linalg.norm(probe - gyro, axis=1).max())
    if max(stable.values()) > .02:
        raise ValueError(f"Unstable differentiation for {name}: {stable}")
    std_a, std_g = NOISE.get(name, (0.0, 0.0))
    noise_manifest = {"enabled": bool(std_a), "acceleration_std_mps2": std_a, "gyro_std_radps": std_g,
                      "seed": 11, "generator": "numpy.random.default_rng(11).normal(0, std, shape)",
                      "physically_calibrated": False}
    if std_a:
        rng = np.random.default_rng(11)
        acceleration = acceleration + rng.normal(0, std_a, acceleration.shape)
        gyro = gyro + rng.normal(0, std_g, gyro.shape)
    offsets = np.cumsum([0.0] + [p + h + r for p, h, r, _ in beats]) + lead
    reps = []
    for k, (pull, hold, ret, amp) in enumerate(beats):
        base = offsets[k]
        span = amp * (pulled_phase - start_phase)
        reps.append({"index": k + 1, "start_ns": NS0 + round(base * 1e9), "pull_start_ns": NS0 + round(base * 1e9),
                     "turnaround_ns": NS0 + round((base + pull) * 1e9),
                     "hold_end_ns": NS0 + round((base + pull + hold) * 1e9),
                     "return_end_ns": NS0 + round((base + pull + hold + ret) * 1e9),
                     "authored_phase_at_turnaround": start_phase + span,
                     "pull_s": pull, "hold_s": hold, "return_s": ret, "amplitude": amp})
    down = None
    if down_total > 0.0:
        d = sum(HANDLE_DOWN)
        start_ns = NS0 + round((sum(p + h + r for p, h, r, _ in beats) + lead) * 1e9)
        down = {"start_ns": start_ns, "lowest_ns": start_ns + round(HANDLE_DOWN[0] * 1e9),
                "end_ns": start_ns + round(d * 1e9),
                "description": ("one monotonic non-returning handle set-down from the pulled turnaround to the start "
                                "position, then stillness; no pull follows" if beats else
                                "preparation at the pulled turnaround, then one monotonic non-returning set-down to the "
                                "start position and stillness; no pull at all")}
    truth = {
        "source": "synthetic", "exercise_id": EXERCISE_ID, "model_id": MODEL_ID, "case_id": name,
        "expected_reps": len(beats),
        "cycle_definition": "start position (authored phase range_[0]) -> straight-arm pull to authored phase range_[1] "
                            "-> turnaround -> optional hold -> full return to range_[0]; the pull and return follow "
                            "the published viewer ease, each lever segment snapped up to whole 20 ms samples",
        "playback_range": [start_phase, pulled_phase],
        "reference": "authored model phase and explicit exercise cycle only; no detector output, threshold, axis sign or peak",
        "pinned_local_ns": NS0, "period_s": period,
        "preparation": {"start_ns": int(stamps[0]), "end_ns": NS0 + round(PREP_S * 1e9)},
        "repetitions": reps,
        "handle_down": down,
        "stillness": {"start_ns": NS0 + round((hold_end + lead) * 1e9), "end_ns": int(stamps[-1])},
        "noise": noise_manifest,
    }
    target = pathlib.Path(root) / name
    target.mkdir(parents=True, exist_ok=True)
    capture = encode_capture(stamps, acceleration, gyro)
    (target / "capture.kcs").write_bytes(capture)
    (target / "truth.json").write_bytes(json_bytes(truth))
    manifest = {
        "source": "synthetic", "case_id": name, "exercise_id": EXERCISE_ID, "model_id": MODEL_ID,
        "hz": HZ, "time_s": times.tolist(), "authored_progress": phases.tolist(),
        "acceleration": acceleration.tolist(), "gyro": gyro.tolist(),
        "sensor_frame": {"origin": "caseback contact proxy on the left wrist (watch frame)", "units": "m, rad/s, m/s^2",
                         "gravity": "world -Z (accelerometer reads at rest)", "time": "pinned synthetic local clock"},
        "mount": {
            "arm": "left", "wrist": "left", "surface": "dorsal", "display_facing": "outward, away from the skin",
            "rigid_to_watch": True,
            "construction": "left_dorsal_watch(anatomical bind) carried by a rigid fit to this clip's published hand vertices",
            "hand_from_watch": clip["hand_from_watch"], "hand_fit_max_error_mm": clip["hand_fit_max_error_mm"],
            "axes": "+X screen right (ulnar on the left wrist), +Y screen top (proximal), +Z screen outward (dorsal)",
            "offset_watch_axes_m": [0.0, .012, .028],
            "plain_language": MOUNT_STATEMENT,
            "physically_calibrated": False, "watch8_mounting_verified": False,
        },
        "synthetic_limits": {"mounting": "not physically calibrated", "noise": noise_manifest,
                             "note": "diagnosis input only; never Watch8 accuracy evidence"},
        "differentiation": {"step_s": .001, "gyro_probe_max_delta_radps": stable,
                            "probe_phase_profile": f"C2 raised-cosine per authored half (edge fraction {RAC_EDGE})"},
        "oracle": {"arm_max_extension_m": clip["arm_max_extension_m"],
                   "hand_travel_from_phase0_mm": clip["hand_travel_from_phase0_mm"],
                   "clip_frames": int(len(clip["acts"])), "clip_acts_first_last": [float(clip["acts"][0]), float(clip["acts"][-1])]},
        "files": {"capture.kcs": digest(target / "capture.kcs"), "truth.json": digest(target / "truth.json")},
    }
    columns = {
        "prep_end_ns": NS0 + round(PREP_S * 1e9),
        "case_id": name,
        "rep_index": [r["index"] for r in reps],
        "pull_start_ns": [r["pull_start_ns"] for r in reps],
        "turnaround_ns": [r["turnaround_ns"] for r in reps],
        "return_end_ns": [r["return_end_ns"] for r in reps],
        "histogram": np.bincount(np.round(np.asarray(phases) * 100).astype(int), minlength=101) if beats else [],
        "hand_height_m": curve(np.asarray(phases))[0][:, 2].tolist() if beats else [],
        "weights": {w: int(np.count_nonzero(np.isclose(np.asarray(phases), w) & (times > 0.0) & (times < motion_end)))
                    for w in (0.0, 0.25, 0.5, 0.75, 1.0)},
        "handle_down_lowest_ns": None if down is None else down["lowest_ns"],
        "stillness_end_ns": int(stamps[-1]),
    }
    for key, value in columns.items():
        if isinstance(value, np.ndarray):
            value = np.asarray(value).tolist()
        elif isinstance(value, np.generic):
            value = value.item()
        (target / f"{key}.json").write_bytes(json_bytes({"case_id": name, "exercise_id": EXERCISE_ID, key: value}))
        manifest[key] = f"{key}.json"
    (target / "manifest.json").write_bytes(json_bytes(manifest))
    return name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--cases", nargs="+", default=list(CASES), choices=list(CASES))
    args = parser.parse_args()
    clip = load_clip()
    mapping = json.loads(APP_MAPPING.read_text())
    oracle = {
        "source": "synthetic", "exercise_id": EXERCISE_ID, "model_id": MODEL_ID,
        "clip_frames": int(len(clip["acts"])), "acts_start_end": [float(clip["acts"][0]), float(clip["acts"][-1])],
        "playback_range": list(PLAYBACK_RANGE),
        "viewer_playback": {"playback_mode": clip["metadata"].get("playback_mode", "pingpong"),
                            "playback_ms": clip["metadata"].get("playback_ms"),
                            "schedule": "start -> end -> start with the published ease()"},
        "authored_direction_check": {
            "arm_max_extension_m": clip["arm_max_extension_m"],
            "hand_travel_from_phase0_mm": clip["hand_travel_from_phase0_mm"],
            "statement": "the authored clip already has a straight (locked) arm; phase range_[0] is one end of its travel and range_[1] the other",
        },
        "hand_fit_max_error_mm": clip["hand_fit_max_error_mm"],
        "mount": {"surface": "dorsal", "plain_language": MOUNT_STATEMENT, "physically_calibrated": False},
        "app_model_mapping": mapping.get(EXERCISE_ID),
        "sources": clip["sources"],
    }
    (pathlib.Path(args.root) / "oracle.json").write_bytes(json_bytes(oracle))
    cases = [build_case(args.root, name, clip) for name in args.cases]
    (pathlib.Path(args.root) / "index.json").write_bytes(json_bytes({"exercise_id": EXERCISE_ID, "cases": cases}))
    for name in cases:
        print("CASE", name, flush=True)


if __name__ == "__main__":
    sys.exit(main())
