#!/usr/bin/env python3
"""Generate the machine_fly virtual-watch ablation cases (read-only sources, no app writes).

The degrees here are a phase slerp of the published arm cycle, so "80% range" is a smaller
arc of the same motion, not a scaled sensor output. No numerical threshold lives here;
the detector and the ablation flags are the production core read from the Kotlin harness.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

import numpy as np

from gen_virtual_watch_pilot import (
    HZ, REPO, NS0, PoseCurve, digest, encode_capture, json_bytes, left_dorsal_watch, recover_watch,
    sensors_from_motion,
)

EXERCISE_ID = "machine_fly"
MODEL_ID = "pec_deck~m=fly"
REPS = 10
# Compare only: start the cycle from the published display start instead of its far end.
OUT_FROM = "stop"
HOLD_S = 0.35
APP_MAPPING = REPO / "phone/src/main/assets/viewer3d/exercise_models.json"
APP_CLIP = REPO / "phone/src/main/assets/viewer3d/human_v5" / f"{MODEL_ID}.bin"

# scenario -> explicit (out_s, return_s, hold_s, range_fraction). Names state the real half times.
SPEC = {"normal_2.0out_2.0ret_full": (2.0, 2.0, 0.0, 1.0),
        "comfortable80_2.0out_2.0ret": (2.0, 2.0, 0.0, 0.80),
        "comfortable80_2.0out_hold_0.35ret_2.0": (2.0, 2.0, HOLD_S, 0.80),
        "period_1.25x_1.6out_1.6ret": (1.6, 1.6, 0.0, 1.0),
        "period_0.8x_2.5out_2.5ret": (2.5, 2.5, 0.0, 1.0),
        "slow_8.0out_8.0ret_80rom": (8.0, 8.0, 0.0, 0.80),
        "fast_0.7out_0.7ret_full": (0.7, 0.7, 0.0, 1.0)}
SIGNALS = ("fusion", "accel_only", "gyro_only")
NOISE = {"clean": (0.0, 0.0), "noise_std_010_002_seed11": (0.10, 0.02)}


def app_mapping_check():
    models = json.loads(APP_MAPPING.read_text())
    return {"asset": str(APP_MAPPING.relative_to(REPO)), "exercise_id": EXERCISE_ID,
            "mapped_models": models.get(EXERCISE_ID), "matches": models.get(EXERCISE_ID) == [MODEL_ID]}


def direct_decode_check():
    """Decode only this clip from the app bundle and compare against the published PC clip."""
    if not APP_CLIP.is_file():
        return {"app_decode_verified": False, "reason": "app clip missing"}
    blob = APP_CLIP.read_bytes()
    magic, count, vertices, _ = struct.unpack_from("<4sIII", blob, 0)
    if magic != b"WGP2" or len(blob) != 40 + count * 4 + count * vertices * 6:
        return {"app_decode_verified": False, "reason": "unexpected WGP2 header"}
    minimum = np.frombuffer(blob, "<f4", 3, 16)
    scale = np.frombuffer(blob, "<f4", 3, 28)
    acts = np.frombuffer(blob, "<f4", count, 40)
    delta = np.frombuffer(blob, "<u2", count * vertices * 3, 40 + count * 4)
    quantized = np.cumsum(delta.reshape(count, vertices * 3).astype(np.uint32), axis=0).astype("<u2")
    decoded = minimum + quantized.astype(np.float32).reshape(count, vertices, 3) * scale
    clip = load_fly_clip()
    reference = clip["frames"]
    acts_error = float(np.abs(acts.astype(float) - clip["acts"]).max())
    position_error_mm = float(np.linalg.norm(decoded - reference, axis=2).max() * 1000)
    verified = count == len(clip["acts"]) and vertices == reference.shape[1] and \
        acts_error <= 1e-6 and position_error_mm < 0.1
    return {"app_decode_verified": verified, "app_clip_sha256": digest(APP_CLIP), "frames": int(count),
            "vertices": int(vertices), "acts_max_error": acts_error,
            "vertex_max_error_mm": position_error_mm,
            "published_frames_equal": bool(np.allclose(decoded, reference, atol=1e-6))}


def clip_travel(pose_fn, period):
    """Independent ROM reference: wrist-position path length over one authored cycle."""
    p = pose_fn(np.linspace(-0.002, period, 201))[0]
    return {"wrist_path_length_mm": float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum() * 1000),
            "stretched_displacement_mm": float(np.linalg.norm(p[p.shape[0] // 2] - p[0]) * 1000)}


def make_pose(curve, metadata, out_s, return_s, hold_s, rom):
    """Explicit out / hold / return times. The 80% arc is interpolated start->stop, not clipped,
    so nothing is held at the turnaround unless hold_s says so."""
    start, end = metadata.get("playback_range") or [0.0, 1.0]
    span = end - start
    # OUT_FROM: "start" = the published display start (phase 0, arm the more swung side), "stop" = the other end.
    origin, target = (start, start + span * rom) if OUT_FROM == "start" else (start + span * rom, start)
    cycle_s = out_s + hold_s + return_s

    def schedule(t):
        # Phase inside the repeated cycle; cycle_s is the real out + hold + return time.
        local = np.mod(np.asarray(t, float), cycle_s)
        out = origin + (target - origin) * np.clip(local / out_s, 0.0, 1.0)
        back = target - (target - origin) * np.clip((local - out_s - hold_s) / return_s, 0.0, 1.0)
        return np.where(local <= out_s + hold_s, out, back)

    def pose(times):
        # One phase per sample: the shared cubic interpolator picks a single interval for a vector of phases.
        times = np.asarray(times, float)
        phases = schedule(times)
        p = np.empty((len(times), 3))
        r = np.empty((len(times), 3, 3))
        for index, phase in enumerate(phases):
            pi, ri = curve(np.array([float(phase)]))
            p[index], r[index] = pi[0], ri[0]
        return p, r
    return pose, cycle_s, (origin, target)


def load_fly_clip():
    """Read this one model's published clip and final palette without touching the pilot tool."""
    roots = [pathlib.Path.home() / "Library/Application Support" / name / "v5-catalog"
             for name in ("__PROTECTED_WATCHCOACH_VIEWER__", "WatchGymViewer")]
    viewer_root = next((p for p in roots if (p / "base.json").is_file()), None)
    if viewer_root is None:
        raise FileNotFoundError("Published V5 catalog is unavailable")
    design = REPO / "design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild"
    base = json.loads((viewer_root / "base.json").read_text())
    motion = json.loads((viewer_root / f"{MODEL_ID}.json").read_text())
    metadata = next(c for c in json.loads((viewer_root / "manifest.json").read_text())["clips"] if c["id"] == MODEL_ID)
    bind = np.asarray(json.loads((design / "anatomical_rest.json").read_text())["rest_matrices"])
    names = base["bone_names"]
    acts = np.asarray(motion["acts"], float)
    rest = np.asarray(base["rest"]).reshape(-1, 3)
    frames = np.asarray(motion["frames"]).reshape(len(acts), len(rest), 3)
    skin = np.fromfile(design / "catalog_trial" / f"{MODEL_ID}.skin.bin", dtype="<f4").astype(float)
    palettes = skin.reshape(len(acts), len(names), 4, 4)
    h = names.index("hand_l")
    joints, weights = np.asarray(base["joints"]), np.asarray(base["weights"])
    ids = np.flatnonzero(np.where(joints == h, weights, 0).sum(1) > .999999)
    landmarks = rest[ids]
    predicted = np.einsum("fij,nj->fni", palettes[:, h, :3, :3], landmarks) + palettes[:, h, None, :3, 3]
    palm_error = float(np.linalg.norm(predicted - frames[:, ids], axis=2).max() * 1000)
    if palm_error > .02:
        raise ValueError(f"Final skin does not match published palm: {palm_error:.4f} mm")
    wrist_rest = bind[h, :3, 3]
    middle = bind[names.index("middle_01_l"), :3, 3]
    thumb = bind[names.index("thumb_01_l"), :3, 3]
    offset = np.array([0.0, .012, .028])
    rest_watch = left_dorsal_watch(wrist_rest, middle, thumb, offset)
    hand_from_watch = np.linalg.inv(bind[h]) @ rest_watch
    poses = recover_watch(palettes[:, h], bind[h], hand_from_watch)
    return {"acts": acts, "poses": poses, "frames": frames, "metadata": metadata,
            "landmark_ids": ids.tolist(), "mount": {"arm": "left", "surface": "dorsal",
            "offset_watch_axes_m": offset.tolist(), "physically_calibrated": False,
            "proven": False, "note": "assumed rigid frame from anatomical landmarks; attachment unverified"}}


def build_case(root, scenario, signal, noise):
    clip = load_fly_clip()
    curve = PoseCurve(clip["acts"], clip["poses"])
    metadata = clip["metadata"]
    out_s, return_s, hold_s, rom = SPEC[scenario]
    pose_fn, period, (origin, target) = make_pose(curve, metadata, out_s, return_s, hold_s, rom)
    prep = 3.0
    total = prep + REPS * period + 4.0
    stamps = NS0 + np.arange(round(total * HZ) + 1, dtype=np.int64) * (1_000_000_000 // HZ)
    times = (stamps - NS0) / 1e9

    def pose(t):
        # Static outside [prep, prep + reps*period); the motion clock starts at the first working sample.
        active = (t > prep) & (t < prep + REPS * period)
        p, r = pose_fn(np.clip(t - prep, 0.0, REPS * period))
        q, qr = pose_fn(np.where(t <= prep, 0.0, REPS * period))
        return np.where(active[:, None], p, q), np.where(active[:, None, None], r, qr)

    acceleration, gyro = sensors_from_motion(times, pose)
    std_a, std_g = NOISE[noise]
    rng = np.random.default_rng(11)
    if std_a:
        acceleration = acceleration + rng.normal(0, std_a, acceleration.shape)
        gyro = gyro + rng.normal(0, std_g, gyro.shape)
    capture = encode_capture(stamps, acceleration, gyro)
    turn = out_s + hold_s
    truth = {"source": "synthetic", "exercise_id": EXERCISE_ID, "case_id": f"{scenario}-{signal}-{noise}",
             "expected_reps": REPS, "scenario": scenario, "signal": signal, "noise": noise,
             "out_s": out_s, "return_s": return_s, "hold_s": hold_s, "range_fraction": rom,
             "out_phase_from": float(origin), "out_phase_to": float(target),
             "period_s": period, "turnaround_s": turn,
             "reference": "model-frame schedule: out from pressed to the authored stop, optional still hold, return",
             "preparation": {"start_ns": int(stamps[0]), "end_ns": NS0 + round(prep * 1e9)},
             "ending_static": {"start_ns": NS0 + round((prep + REPS * period) * 1e9), "end_ns": int(stamps[-1])},
             "repetitions": [{"index": i + 1, "start_ns": NS0 + round((prep + i * period) * 1e9),
                              "turnaround_ns": NS0 + round((prep + i * period + turn) * 1e9),
                              "end_ns": NS0 + round((prep + (i + 1) * period) * 1e9)} for i in range(REPS)]}
    name = truth["case_id"]
    target = pathlib.Path(root) / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "capture.kcs").write_bytes(capture)
    (target / "truth.json").write_bytes(json_bytes(truth))
    (target / "manifest.json").write_bytes(json_bytes({
        "source": "synthetic", "case_id": name, "exercise_id": EXERCISE_ID, "model_id": MODEL_ID,
        "time_s": times.tolist(),
        "acceleration": acceleration.tolist(), "gyro": gyro.tolist(),
        "rom_reference": clip_travel(pose_fn, period), "mount": clip["mount"],
        "files": {"capture.kcs": digest(target / "capture.kcs"), "truth.json": digest(target / "truth.json")}}))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--names", nargs="+", required=True, help="scenario|signal|noise")
    args = parser.parse_args()
    mapping = app_mapping_check()
    decode = direct_decode_check()
    cases = []
    for name in args.names:
        scenario, signal, noise = name.split("|")
        case = build_case(args.root, scenario, signal, noise)
        cases.append(case.name)
        print("CASE", case.name, flush=True)
    (args.root / "index.json").write_bytes(json_bytes({"app_mapping": mapping, "app_decode": decode,
                                                       "cases": cases}))


if __name__ == "__main__":
    sys.exit(main())
