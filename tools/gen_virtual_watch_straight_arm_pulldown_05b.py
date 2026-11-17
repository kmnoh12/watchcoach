#!/usr/bin/env python3
"""05B phase A: independent dorsal-watch source oracle + KCS v2 fixtures for straight_arm_pulldown.

Truth comes from the current published V5 viewer source only: the point-cache rest vertices, skin
weights and per-frame positions, the viewer's phase bracket, its 2600 ms full round trip and its
ease curve. No detector is imported, run, or consulted anywhere in this file, and no boundary, sign,
window or direction is derived from a detector event.

Outputs (all under the 05B session root):
  evidence/source-oracle.json, evidence/source-verification.json
  fixtures/manifest.json
  fixtures/cases/<case>/{watch.kcs, truth.json, case.manifest.json}

Usage:  python3 tools/gen_virtual_watch_straight_arm_pulldown_05b.py
        python3 tools/gen_virtual_watch_straight_arm_pulldown_05b.py --check   (writes nothing)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import struct
import sys
from pathlib import Path

EXERCISE_ID = "straight_arm_pulldown"
CLIP_ID = "cable_tower~h=high~g=straight~p=straight_arm"
SESSION_LABEL = "05B"
GEN_VERSION = "05b-gen-1"

REPO = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO / "work/virtual-watch/campaign/dsh-sessions/05b-straight-arm-pulldown-corrected-oracle"
SOURCE_ROOT = SESSION_ROOT / "evidence/source"
EVIDENCE = SESSION_ROOT / "evidence"
FIXTURES = SESSION_ROOT / "fixtures"
CASES_DIR = FIXTURES / "cases"

BASE_JSON = SOURCE_ROOT / "base.json"
CLIP_JSON = SOURCE_ROOT / "clip.json"
VIEWER_HTML = SOURCE_ROOT / "viewer-index.html"

# ---------------------------------------------------------------- constants
GRAVITY_VEC = (0.0, 0.0, -9.80665)  # metric world: x right, y forward (out of chest), z up
SAMPLE_RATE_HZ = 50.0
SAMPLE_INTERVAL_NS = 20_000_000
SAMPLES_PER_SECOND = 50
PREP_SAMPLES = 150
PREP_SECONDS = PREP_SAMPLES / SAMPLE_RATE_HZ  # 3.0 s of actual stationary data in the capture
REP_COUNT = 10
CYCLE_BASE_NS = 2_600_000_000  # viewer "REP = 2600; // ms for one full rep: 0 -> 1 -> 0"
CLEAN_SCALES = (1.0,) * REP_COUNT
TEMPO_SCALES = (1.00, 1.06, 0.95, 1.09, 0.92, 1.04, 0.97, 1.08, 0.94, 1.02)  # bounded tempo variation
TEMPO_SEED = 20_261_116
HOLD_SAMPLES = 200  # 4.0 s hold at the pulled turnaround
HALF_STEPS = 64  # the viewer rebuilds phase 0->1->0 out of a 65-frame half; this grid mirrors 2 x 64 steps
TEMPO_NOISE_ACC_MPS2 = 0.05  # not physically calibrated
TEMPO_NOISE_GYRO_RADPS = 0.02  # not physically calibrated
TERMINAL_SAMPLES = 64  # 1.28 s monotone handle set-down
TERMINAL_AXIS_DOT_MIN = 0.85
TERMINAL_FOREARM_CLEAR_DEG = 20.0
TERMINAL_CANDIDATES = (
    (15.0, 80.0, 12.0), (20.0, 100.0, 12.0), (25.0, 120.0, 10.0), (30.0, 140.0, 10.0),
    (15.0, 150.0, 8.0), (20.0, 160.0, 8.0), (25.0, 60.0, 10.0), (30.0, 90.0, 10.0),
)
STILL_AFTER_TERMINAL_SAMPLES = 100  # 2.0 s of stillness after the set-down

WATCH_WRIST = "left"
WATCH_MOUNT = "dorsal"
HAND_BONE = "hand_l"
HAND_VERTEX_WEIGHT_MIN = 0.9
HAND_BONE_GROUP_MAX_DISTANCE_M = 0.12  # hand_l group centroid to the frame-0 rigid wrist anchor
SOUP_THRESHOLD_M = 0.0002
WATCH_BASE_OFFSET_M = (0.0, 0.0, 0.0)  # relaxed viewer hand surface: watch origin on the wrist anchor

# Watch mount (metric watch frame S = [forward = fingers, out = dorsal/display, up => -up = elbow]).
MOUNT_BASE_OFFSET_LOCAL_M = (0.0, 0.0, 0.03)  # 3 cm from the wrist anchor toward -z (elbow side)
WATCH_DISPLAY_TILT_FWD_DEG = 0.0  # B is exactly A; keep explicit so a future mount change is visible

TERMINAL_SHOULDER_SWING_DEG = 18.0  # handle carried down and back at the end of the swing
TERMINAL_ELBOW_BEND_DEG = 22.0      # elbow folds as the handle comes to the floor
TERMINAL_WRIST_RELAX_DEG = 10.0     # wrist relaxes (flexion toward the palm side)

PERFORMANCE_BASE_NS = 1_000_000_000_000
RECEIVED_LEAD_NS = 2_000_000

CASES = (
    "continuous_10_clean",
    "continuous_10_tempo_variation",
    "return_boundary_hold",
    "ten_then_handle_down",
    "handle_down_only",
)

ORIENTATION_PLAIN = {
    "watch": "LEFT wrist. The watch sits on the DORSAL side (back of the hand). The display faces away from "
             "the skin; the back plate and heart-rate sensor face the skin on the palm side.",
    "sensor_frame": "Rigid to the watch. x points to the fingers (watch forward), y points out of the hand back "
                    "(the display side), z is watch up and -z points toward the elbow. Android accelerometer and "
                    "gyroscope values are read in this frame.",
    "metric_world": "x right, y forward (out of the chest), z up, metres. Gravity is (0, 0, -9.80665) m/s^2. "
                    "Accelerometer = R^T(-g) + R^T(C''); gyroscope = R^T w. The centripetal term w x (w x r) is "
                    "zero because the sensor origin rides the wrist rotation axis with r = 0.",
    "mesh_frame": "As the viewer states it: anatomical left is +X, head +Z, nose/chest -Y. The published V5 "
                  "guide is in metres.",
    "viewer_semantics": "A clip phase a in [0,1] brackets frames F[i], F[j] and blends them. Viewer playback runs "
                        "0 -> 1 -> 0 over 2600 ms with ease(t*2) on the first half and ease((1-t)*2) on the "
                        "second. The clip stores one half (authored pull, frame 0 to frame 64); the viewer's own "
                        "playback reconstructs the return pass, so a full viewer round trip is two mirrored passes.",
    "truth": "A full cycle is start -> straight-arm pull -> pulled turnaround -> full return to start. The "
             "turnaround is source phase 1 and the full return is source phase 0 again. The clip's own frame 64 "
             "is the end of the authored pull, not a return.",
    "terminal_motion": "handle set-down: one monotone, non-returning motion from the start pose to an end pose "
                       "(arm swing down/back following the chest-front circle, elbow fold, small wrist relax). "
                       "It is constructed for transport only, marked as constructed (not authored by the viewer).",
}


# ---------------------------------------------------------------- helpers
def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def ease(t):
    return 2.0 * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0


def viewer_phase(z):
    z = clamp01(z)
    return ease(z * 2.0) if z < 0.5 else ease((1.0 - z) * 2.0)


def phase_bracket(acts, a):
    n = len(acts)
    if n == 1 or a <= acts[0]:
        return 0, 0, 0.0
    if a >= acts[n - 1]:
        return n - 1, n - 1, 0.0
    lo, hi = 0, n - 1
    while hi - lo > 1:
        mid = (lo + hi) >> 1
        if acts[mid] <= a:
            lo = mid
        else:
            hi = mid
    span = acts[hi] - acts[lo]
    return lo, hi, (a - acts[lo]) / span if span > 0 else 0.0


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n")


# ---------------------------------------------------------------- vectors and 3x3 matrices
def madd(a, b):
    return [a[i] + b[i] for i in range(3)]


def msub(a, b):
    return [a[i] - b[i] for i in range(3)]


def mscale(a, s):
    return [a[i] * s for i in range(3)]


def mdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def mcross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def mnorm(a):
    return math.sqrt(mdot(a, a))


def munit(a):
    n = mnorm(a)
    if n < 1e-15:
        raise ValueError("cannot normalize a zero vector")
    return [a[i] / n for i in range(3)]


def mmul(A, B):
    return [[sum(A[i][p] * B[p][j] for p in range(3)) for j in range(3)] for i in range(3)]


def mT(A):
    return [list(r) for r in zip(*A)]


def mv(A, v):
    return [sum(A[i][j] * v[j] for j in range(3)) for i in range(3)]


def ident():
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def cols(c1, c2, c3):
    return [[c1[i], c2[i], c3[i]] for i in range(3)]


def column(A, j):
    return [A[0][j], A[1][j], A[2][j]]


def orthonormalize_cols(c1, c2):
    e1 = munit(c1)
    e2 = munit(msub(c2, mscale(e1, mdot(c2, e1))))
    return cols(e1, e2, mcross(e1, e2))


def rot_angle_deg(A):
    c = (A[0][0] + A[1][1] + A[2][2] - 1.0) / 2.0
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def axis_angle(A):
    c = (A[0][0] + A[1][1] + A[2][2] - 1.0) / 2.0
    theta = math.acos(max(-1.0, min(1.0, c)))
    if theta < 1e-12:
        return [0.0, 0.0, 0.0], 0.0
    ax = [A[2][1] - A[1][2], A[0][2] - A[2][0], A[1][0] - A[0][1]]
    return munit(ax), theta


def rot_axis_angle(axis, angle):
    k = munit(axis)
    K = [[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]]
    KK = mmul(K, K)
    c, s = math.cos(angle), math.sin(angle)
    return [[(1.0 if i == j else 0.0) + s * K[i][j] + (1.0 - c) * KK[i][j] for j in range(3)] for i in range(3)]


def rot_exp(w):
    theta = mnorm(w)
    return ident() if theta < 1e-15 else rot_axis_angle(w, theta)


# ---------------------------------------------------------------- KCS v2 (local encoder, per SensorCaptureFormat.kt)
def encode_kcs(records):
    out = bytearray()
    out += b"KCS1"
    out += struct.pack("<i", 2)
    out += struct.pack("<i", len(records))
    out += struct.pack("<d", SAMPLE_RATE_HZ)
    for r in records:
        out += struct.pack("<q", int(r["timestamp_ns"]))
        out += struct.pack("<3f", *r["acc"])
        out += struct.pack("<3f", *r["gyro"])
        out += struct.pack("<i", int(r["sensor_accuracy"]))
        out += struct.pack("<i", -1)                          # heart rate unavailable
        out += struct.pack("<q", -1)                          # accelerationTimestampNs null (allowed)
        out += struct.pack("<q", int(r["timestamp_ns"]))      # gyroscopeTimestampNs == sample timestamp
        out += struct.pack("<q", int(r["received_elapsed_ns"]))
        out += struct.pack("<i", -1)                          # accelerationAccuracy null (allowed)
        out += struct.pack("<q", -1)                          # heart-rate timestamp unavailable
    return bytes(out)


def decode_kcs(data):
    if len(data) < 20 or data[:4] != b"KCS1":
        raise ValueError("KCS magic")
    version, count = struct.unpack_from("<ii", data, 4)
    rate = struct.unpack_from("<d", data, 12)[0]
    if version != 2:
        raise ValueError("KCS version")
    if len(data) != 20 + count * 76:
        raise ValueError("KCS length")
    records = []
    off = 20
    for _ in range(count):
        ts = struct.unpack_from("<q", data, off)[0]
        acc = list(struct.unpack_from("<3f", data, off + 8))
        gyro = list(struct.unpack_from("<3f", data, off + 20))
        acc_sensor = struct.unpack_from("<i", data, off + 32)[0]
        hr = struct.unpack_from("<i", data, off + 36)[0]
        acc_ts, gyro_ts, recv = struct.unpack_from("<qqq", data, off + 40)
        acc_q = struct.unpack_from("<i", data, off + 64)[0]
        hr_ts = struct.unpack_from("<q", data, off + 68)[0]
        records.append({
            "timestamp_ns": ts, "acc": acc, "gyro": gyro,
            "sensor_accuracy": None if acc_sensor < 0 else acc_sensor,
            "heart_rate_bpm": None if hr < 0 else hr,
            "acceleration_timestamp_ns": None if acc_ts == -1 else acc_ts,
            "gyroscope_timestamp_ns": None if gyro_ts == -1 else gyro_ts,
            "received_elapsed_ns": None if recv == -1 else recv,
            "acceleration_accuracy": None if acc_q < 0 else acc_q,
            "heart_rate_timestamp_ns": None if hr_ts == -1 else hr_ts,
        })
        off += 76
    return version, rate, records


def acceleration_fault(record):
    """Exact mirror of SensorRecordQuality.hasAccelerationFault for one decoded KCS v2 record."""
    if record["acceleration_accuracy"] == 0:
        return True
    acc_ts = record["acceleration_timestamp_ns"]
    if acc_ts is None:
        return False
    gyro_ns = record["timestamp_ns"]
    return acc_ts < 0 or acc_ts > gyro_ns or gyro_ns - acc_ts > 40_000_000


# ---------------------------------------------------------------- source loading and validation
def validate_source(base, clip, viewer_text):
    names = base["bone_names"]
    rest = base["rest"]
    verts = int(base["vertices"])
    if len(rest) != verts * 3:
        raise SystemExit("base.json rest length does not match the vertex count")
    joints, weights = base["joints"], base["weights"]
    if len(joints) != verts or len(weights) != verts:
        raise SystemExit("base.json skin arrays do not match the vertex count")
    for v in range(verts):
        if len(joints[v]) != 4 or len(weights[v]) != 4:
            raise SystemExit("base.json skin arrays are not four per vertex")
        if abs(sum(weights[v]) - 1.0) > 1e-5 or any(w < 0 for w in weights[v]):
            raise SystemExit("base.json skin weights are invalid")
        if any(j < 0 or j >= len(names) for j in joints[v]):
            raise SystemExit("base.json joint index out of range")
    tris = base["triangles"]
    if len(tris) % 3 or min(tris) < 0 or max(tris) >= verts:
        raise SystemExit("base.json triangles are invalid")
    acts = list(clip["acts"])
    frames = clip["frames"]
    if clip["machine"] != CLIP_ID or len(frames) != len(acts):
        raise SystemExit("clip identity or frame count mismatch")
    if any(len(f) != verts * 3 for f in frames):
        raise SystemExit("clip frames do not match the base vertex count")
    for i in range(1, len(acts)):
        if not (acts[i] > acts[i - 1]) or acts[i] > 1.0 or acts[i] < 0.0:
            raise SystemExit("clip acts are not strictly increasing inside 0..1")
    if list(clip["tris"]) != list(tris):
        raise SystemExit("clip point-cache topology differs from base")
    if base.get("body_shape", {}).get("source_rig_motion_and_original_weights_unchanged") is not True:
        raise SystemExit("base body_shape does not declare unchanged rig motion and weights")
    required = [
        "const REP = 2600; // ms for one full rep: 0 -> 1 -> 0",
        "function ease(t) { return t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }",
        "(t < .5 ? ease(t * 2) : ease((1 - t) * 2))",
        "function phaseBracket(acts, a) {",
        "const [i, j, t] = phaseBracket(h.acts, a);",
        "// Bind mesh: anatomical left is +X, head is +Z, nose/chest is -Y.",
        "throw Error(\"human topology mismatch\")",
        "d.frames?.length !== meta.frames || !Array.isArray(meta.acts) || !Array.isArray(d.acts) || d.acts.length !== meta.acts.length",
    ]
    for line in required:
        if line not in viewer_text:
            raise SystemExit("viewer semantics line missing: " + line[:70])
    return {"bone_count": len(names), "vertices": verts, "triangles": len(tris) // 3,
            "frames": len(frames), "acts": acts}


class Source:
    """The published viewer pose path, read the way the viewer reads it."""

    def __init__(self, base, clip, viewer_text, files):
        self.info = validate_source(base, clip, viewer_text)
        self.files = files
        self.names = base["bone_names"]
        self.acts = [float(a) for a in clip["acts"]]
        self.vertices = int(base["vertices"])
        self.joints = base["joints"]
        self.weights = base["weights"]
        r = base["rest"]
        self.rest = [[r[3 * v], r[3 * v + 1], r[3 * v + 2]] for v in range(self.vertices)]
        self.frames = [[[f[3 * v], f[3 * v + 1], f[3 * v + 2]] for v in range(self.vertices)] for f in clip["frames"]]

        self.hand_bone = self.names.index(HAND_BONE)
        dominant = [v for v in range(self.vertices)
                    if any(self.joints[v][s] == self.hand_bone and self.weights[v][s] >= HAND_VERTEX_WEIGHT_MIN
                           for s in range(4))]
        if not dominant:
            raise SystemExit("no hand_l dominant mesh vertex")
        for a, v in enumerate(dominant):
            for w in dominant[a + 1:]:
                if mnorm(msub(self.rest[v], self.rest[w])) < SOUP_THRESHOLD_M:
                    raise SystemExit("hand vertex has a duplicate (soup); skinning would split its weights")
        self.anchor = self.bone_group_centroid(self.frames[0], self.hand_bone, vertex_filter=dominant)
        near = [v for v in dominant
                if mnorm(msub(self.bone_group_centroid(self.frames[0], HAND_BONE, vertex_filter=[v]), self.anchor))
                <= HAND_BONE_GROUP_MAX_DISTANCE_M]
        if not near:
            raise SystemExit("hand mesh selection does not sit near the hand_l bone")
        self.selected_mesh_vertices = near
        self.selected_weights = [self.weights[v] for v in near]
        self.selected_joint_names = [[self.names[j] for j in self.joints[v]] for v in near]
        self.rest_palm_center = mscale([sum(self.rest[v][k] for v in near) for k in range(3)], 1.0 / len(near))
        self.mount()

    def bone_group_centroid(self, P, bone, vertex_filter=None):
        bi = self.names.index(bone) if isinstance(bone, str) else bone
        verts = range(self.vertices) if vertex_filter is None else vertex_filter
        c = [0.0, 0.0, 0.0]
        total = 0.0
        for v in verts:
            for s in range(4):
                if self.joints[v][s] == bi and self.weights[v][s] > 0:
                    w = self.weights[v][s]
                    c = madd(c, mscale(P[v], w))
                    total += w
        if total <= 0:
            raise SystemExit(f"bone {self.names[bi]} has no weighted vertex")
        return mscale(c, 1.0 / total)

    def continuous(self, a):
        """Viewer-equivalent continuous pose of the selected hand vertices (phase bracket + linear blend
        of the two cached frames, then a Kabsch fit on the same selected vertices)."""
        i, j, t = phase_bracket(self.acts, a)
        fi = [self.frames[i][v] for v in self.selected_mesh_vertices]
        if j == i or t == 0.0:
            blended = fi
        else:
            fj = [self.frames[j][v] for v in self.selected_mesh_vertices]
            blended = [madd(fi[n], mscale(msub(fj[n], fi[n]), t)) for n in range(len(fi))]
        thr = [self.rest[v] for v in self.selected_mesh_vertices]
        return kabsch(thr, blended)

    def pose_cache(self):
        cache = {}
        for idx in range(len(self.acts)):
            cache[idx] = kabsch([self.rest[v] for v in self.selected_mesh_vertices],
                                [self.frames[idx][v] for v in self.selected_mesh_vertices])
        return cache

    def mount(self):
        P0 = self.frames[0]
        pelvis = self.bone_group_centroid(P0, "pelvis")
        neck = self.bone_group_centroid(P0, "neck_01")
        clav_l = self.bone_group_centroid(P0, "clavicle_l")
        clav_r = self.bone_group_centroid(P0, "clavicle_r")
        across = munit(msub(clav_l, clav_r))
        neck_up = msub(neck, pelvis)
        world_up = munit(msub(neck_up, mscale(across, mdot(neck_up, across))))
        self.frame0 = {
            "pelvis": pelvis, "neck": neck, "clavicle_l": clav_l, "clavicle_r": clav_r,
            "world_up": world_up, "world_right": mscale(across, -1.0), "across": across,
            "chest_front": munit(mcross(across, msub(neck, pelvis))),
        }
        self.frame_bases = [self.basis_at(P) for P in self.frames]
        self.frame_anchor = [self.bone_group_centroid(P, HAND_BONE) for P in self.frames]
        R0 = self.frame_bases[0]
        wrist0 = self.frame_anchor[0]
        elbow0 = self.bone_group_centroid(P0, "lowerarm_l")
        shoulder0 = self.bone_group_centroid(P0, "upperarm_l")
        # u = shoulder -> wrist (distal, toward the fingers): elbow -> wrist vs upperarm -> elbow are
        # nearly collinear in a straight arm, so the elbow bone cannot define the hand axis.
        u0 = munit(msub(wrist0, shoulder0))
        toward_elbow = msub(elbow0, wrist0)
        v0 = munit(msub(toward_elbow, mscale(u0, mdot(toward_elbow, u0))))
        z0 = mcross(u0, v0)
        self.G_h0 = cols(u0, v0, z0)  # A: local hand basis in the mesh frame
        # Dorsal normal resolves to palm_out = -z (hand back). Unit check with the body frame:
        out0 = munit(mscale(z0, -1.0))
        if mdot(out0, self.frame0["chest_front"]) > 0:
            out0 = mscale(out0, -1.0)
        # B: watch frame expressed in the mesh frame with x = fingers (u), y = dorsal normal, z = up.
        bx = u0
        by = mscale(out0, 1.0)
        by = munit(msub(by, mscale(bx, mdot(by, bx))))
        bz = mcross(bx, by)
        self.B = cols(bx, by, bz)
        self.A = self.G_h0
        self.W_rel = mmul(self.B, mT(self.A))  # watch frame in the hand basis
        self.dorsal_out_world0 = munit(by)
        self.dorsal_dot_chest = mdot(self.dorsal_out_world0, self.frame0["chest_front"])
        self.dorsal_dot_up = mdot(self.dorsal_out_world0, world_up)
        self.fwd_world0 = munit(bx)
        self.watch_up_world0 = munit(bz)
        self.wrist_world0 = wrist0
        self.elbow0 = elbow0
        self.shoulder0 = shoulder0
        self.upper_len = mnorm(msub(elbow0, shoulder0))
        self.fore_len = mnorm(msub(wrist0, elbow0))
        self.mount_offset_local = list(MOUNT_BASE_OFFSET_LOCAL_M)

    def watch_pose(self, a):
        """A = orthonormal hand basis built from the blended frame's weighted bone centres
        (hand_l, lowerarm_l, upperarm_l); R = A0 A^T moves the rigid watch from the start pose to a;
        C = hand anchor + R * mount offset (offset zero: the watch rides the wrist anchor)."""
        i, j, t = phase_bracket(self.acts, a)
        if j == i or t == 0.0:
            A = self.frame_bases[i]
        else:
            A = self.blend_basis(self.frames[i], self.frames[j], t)
        R = mmul(self.G_h0, mT(A))
        anchor_a = self.blend_anchor(i, j, t)
        C = madd(anchor_a, mv(R, self.mount_offset_local))
        return R, C

    def basis_at(self, P):
        hand = self.bone_group_centroid(P, HAND_BONE)
        elbow = self.bone_group_centroid(P, "lowerarm_l")
        shoulder = self.bone_group_centroid(P, "upperarm_l")
        u = munit(msub(hand, shoulder))
        v = msub(shoulder, elbow)
        v = munit(msub(v, mscale(u, mdot(v, u))))
        return cols(u, v, mcross(u, v))

    def blend_basis(self, Pi, Pj, t):
        Ai, Aj = self.basis_at(Pi), self.basis_at(Pj)
        c = [madd(mscale(column(Ai, k), 1.0 - t), mscale(column(Aj, k), t)) for k in range(3)]
        return orthonormalize_cols(c[0], c[1])

    def blend_anchor(self, i, j, t):
        ai = self.frame_anchor[i]
        if j == i or t == 0.0:
            return ai
        return madd(ai, mscale(msub(self.frame_anchor[j], ai), t))


# ---------------------------------------------------------------- Kabsch
def _sym_eig3(A):
    a = [row[:] for row in A]
    V = ident()
    for _ in range(100):
        p, q = 0, 1
        best = abs(a[0][1])
        for (i, j) in ((0, 2), (1, 2)):
            if abs(a[i][j]) > best:
                best, p, q = abs(a[i][j]), i, j
        if best < 1e-15:
            break
        theta = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(theta), math.sin(theta)
        R = ident()
        R[p][p], R[p][q], R[q][p], R[q][q] = c, -s, s, c
        a = mmul(mT(R), mmul(a, R))
        V = mmul(V, R)
    return [a[i][i] for i in range(3)], V


def kabsch(P0, P):
    n = len(P0)
    c0 = [sum(P0[i][k] for i in range(n)) / n for k in range(3)]
    c = [sum(P[i][k] for i in range(n)) / n for k in range(3)]
    H = [[sum((P0[i][a] - c0[a]) * (P[i][b] - c[b]) for i in range(n)) for b in range(3)] for a in range(3)]
    vals, Vm = _sym_eig3(mmul(mT(H), H))
    order = sorted(range(3), key=lambda i: -vals[i])
    V = orthonormalize_cols([Vm[i][order[0]] for i in range(3)], [Vm[i][order[1]] for i in range(3)])
    HV = mmul(H, V)
    U = orthonormalize_cols([HV[i][0] for i in range(3)], [HV[i][1] for i in range(3)])
    # chirality from the third singular vector (robust for symmetric hands)
    s3 = mdot(column(U, 2), column(HV, 2))
    Vd = V if s3 > 0 else cols(column(V, 0), mscale(column(V, 1), -1.0), column(V, 2))
    R = mmul(U, mT(Vd))
    t = msub(c, mv(R, c0))
    return R, t


def rig_residual(R, t, P0, P):
    return max(mnorm(msub(madd(mv(R, P0[i]), t), P[i])) for i in range(len(P0)))


# ---------------------------------------------------------------- source analysis
def analyse_cycle_breakdown(src):
    def hand_height(f):
        P = src.frames[f]
        return mdot(msub(src.bone_group_centroid(P, HAND_BONE), src.frame0["pelvis"]), src.frame0["world_up"])

    def fore_forward(f):
        P = src.frames[f]
        return mdot(msub(src.bone_group_centroid(P, HAND_BONE), src.frame0["pelvis"]), src.frame0["chest_front"])

    def lateral(f):
        P = src.frames[f]
        return mdot(msub(src.bone_group_centroid(P, HAND_BONE), src.frame0["pelvis"]), src.frame0["world_right"])

    rows = []
    for f in range(len(src.acts)):
        P = src.frames[f]
        sh = src.bone_group_centroid(P, "upperarm_l")
        el = src.bone_group_centroid(P, "lowerarm_l")
        hb = src.bone_group_centroid(P, HAND_BONE)
        a1 = munit(msub(el, sh))
        a2 = munit(msub(hb, el))
        R, t = src.pose_cache()[f]
        Rw = mmul(R, src.B)
        rows.append({
            "frame": f,
            "phase": src.acts[f],
            "hand_height_m": hand_height(f),
            "fore_forward_m": fore_forward(f),
            "lateral_m": lateral(f),
            "elbow_angle_deg": 180.0 - math.degrees(math.acos(max(-1.0, min(1.0, mdot(a1, a2))))),
            "forearm_elevation_deg": math.degrees(math.asin(max(-1.0, min(1.0, munit(msub(hb, el))[2])))),
            "dorsal_out_dot_chest": mdot(column(Rw, 1), src.frame0["chest_front"]),
            "dorsal_out_dot_up": mdot(column(Rw, 1), src.frame0["world_up"]),
            "watch_fwd_dot_forearm": mdot(column(Rw, 0), munit(msub(hb, el))),
            "hand_rigid_residual_mm": rig_residual(R, t,
                                                   [src.rest[v] for v in src.selected_mesh_vertices],
                                                   [P[v] for v in src.selected_mesh_vertices]) * 1000.0,
        })
    return rows


def analyse(src):
    steps = 128
    samples = []
    for k in range(steps + 1):
        z = k / steps
        a = viewer_phase(z)
        Rw, C = src.watch_pose(a)
        samples.append({"z": z, "phase": a, "C": C, "forward": column(Rw, 0), "out": column(Rw, 1)})

    def speeds():
        out = []
        eps = 1e-4
        for k in range(steps):
            z = samples[k]["z"] + eps
            if z > 1.0:
                break
            C0 = samples[k]["C"]
            C1 = src.watch_pose(viewer_phase(z))[1]
            out.append(mnorm(msub(C1, C0)) / eps)
        return max(out)

    z_of = lambda s: s["C"][2]
    half = samples[: steps // 2 + 1]
    rows = analyse_cycle_breakdown(src)
    R_start, C_start = src.watch_pose(0.0)
    R_end, C_end = src.watch_pose(1.0)
    R_back, C_back = src.watch_pose(0.0)
    R_auth, t_auth = src.pose_cache()[len(src.acts) - 1]
    energy = sweep_energy(src)
    R_0, t_0 = src.pose_cache()[0]
    return {
        "samples": samples,
        "rows": rows,
        "trajectory": {
            "z_max_m": max(z_of(s) for s in samples),
            "z_min_m": min(z_of(s) for s in samples),
            "z_drop_m": max(z_of(s) for s in samples) - min(z_of(s) for s in samples),
            "half_monotone_down": all(z_of(half[i + 1]) <= z_of(half[i]) + 1e-12 for i in range(len(half) - 1)),
            "y_range_m": max(s["C"][1] for s in samples) - min(s["C"][1] for s in samples),
            "x_range_m": max(s["C"][0] for s in samples) - min(s["C"][0] for s in samples),
            "sample_stride_mm": round(mnorm(msub(samples[1]["C"], samples[0]["C"])) * 1000.0, 3),
            "peak_speed_per_viewer_time_mps": speeds(),
        },
        "turnaround": {"R": R_end, "C": C_end, "rotation_from_start_deg": rot_angle_deg(mmul(R_end, mT(R_start))),
                       "translation_from_start_m": mnorm(msub(C_end, C_start))},
        "full_return": {"rotation_from_start_deg": rot_angle_deg(mmul(R_back, mT(R_start))),
                        "translation_from_start_m": mnorm(msub(C_back, C_start))},
        "authored_clip_end": {"hand_rotation_from_start_deg": rot_angle_deg(mmul(R_auth, mT(R_0))),
                              "hand_translation_from_start_m": mnorm(msub(t_auth, t_0))},
        "sweep_energy": energy,
        "watch_forward_axis_turns": {
            "start": column(src.watch_pose(0.0)[0], 0),
            "turnaround": column(R_end, 0),
            "angle_deg": math.degrees(math.acos(max(-1.0, min(1.0, mdot(column(src.watch_pose(0.0)[0], 0),
                                                                   column(R_end, 0)))))),
        },
    }


# ---------------------------------------------------------------- path pieces
class Piece:
    __slots__ = ("t0_ns", "t1_ns", "R0", "C0", "R1", "C1", "w", "v", "kind")

    def __init__(self, t0_ns, R0, C0, t1_ns, R1, C1, kind):
        self.t0_ns, self.t1_ns = int(t0_ns), int(t1_ns)
        self.R0, self.C0, self.R1, self.C1, self.kind = R0, C0, R1, C1, kind
        dt = (self.t1_ns - self.t0_ns) / 1e9
        rel = mmul(R1, mT(R0))
        c = (rel[0][0] + rel[1][1] + rel[2][2] - 1.0) / 2.0
        th = math.acos(max(-1.0, min(1.0, c)))
        ax = [rel[2][1] - rel[1][2], rel[0][2] - rel[2][0], rel[1][0] - rel[0][1]]
        n = mnorm(ax)
        self.w = [0.0, 0.0, 0.0] if (th < 1e-12 or n < 1e-12 or dt <= 0) else mscale(ax, th / (dt * n))
        self.v = mscale(msub(C1, C0), 1.0 / dt) if dt > 0 else [0.0, 0.0, 0.0]

    def R_at(self, t_ns):
        if self.t1_ns <= self.t0_ns:
            return self.R1
        f = (t_ns - self.t0_ns) / (self.t1_ns - self.t0_ns)
        return mmul(rot_exp(mscale(self.w, f * (self.t1_ns - self.t0_ns) / 1e9)), self.R0)

    def C_at(self, t_ns):
        if self.t1_ns <= self.t0_ns:
            return self.C1
        f = (t_ns - self.t0_ns) / (self.t1_ns - self.t0_ns)
        return madd(self.C0, mscale(msub(self.C1, self.C0), f))


class Path:
    """Ordered pieces over absolute sample times; outside a piece the watch is still."""

    def __init__(self, R_rest, C_rest):
        self.R_rest, self.C_rest = R_rest, C_rest
        self.pieces = []
        self.t_end = 0

    def append_segments(self, t_start_ns, segments, kind):
        prev_t, prev_R, prev_C = t_start_ns, segments[0][1], segments[0][2]
        for (tn, R, C) in segments:
            self.pieces.append(Piece(prev_t, prev_R, prev_C, tn, R, C, kind))
            prev_t, prev_R, prev_C = tn, R, C
        self.t_end = max(self.t_end, prev_t)
        return prev_t

    def piece_at(self, t_ns):
        for p in self.pieces:
            if p.t0_ns <= t_ns <= p.t1_ns and p.kind != "hold":
                return p
        return None

    def pose(self, t_ns):
        p = self.piece_at(t_ns)
        if p is None:
            still = [q for q in self.pieces if q.kind == "hold" and q.t0_ns <= t_ns <= q.t1_ns]
            if still:
                return still[0].R0, still[0].C0
            if self.pieces and t_ns > self.pieces[-1].t1_ns:
                return self.pieces[-1].R1, self.pieces[-1].C1
            return self.R_rest, self.C_rest
        return p.R_at(t_ns), p.C_at(t_ns)

    def static_hold(self, t0_ns, t1_ns):
        R, C = self.pose(t1_ns if not self.pieces else self.pieces[-1].t1_ns)
        self.pieces.append(Piece(t0_ns, R, C, t1_ns, R, C, "hold"))
        self.t_end = max(self.t_end, t1_ns)
        return R, C


def cycle_segments(src, scale, hold_samples=0):
    """Knots for one full viewer round trip: forward pass phase 0 -> 1 (ease(t*2)), optional hold at the
    pulled turnaround, mirrored return pass phase 1 -> 0 (ease((1-t)*2))."""
    cycle_s = CYCLE_BASE_NS / 1e9 * scale
    knots = []
    for k in range(1, HALF_STEPS + 1):
        z = k / (2.0 * HALF_STEPS)
        a = ease(z * 2.0)
        R, C = src.watch_pose(a)
        knots.append((int(round(cycle_s * z * 1e9)), R, C, "move"))
    turn_t = knots[-1][0]
    if hold_samples:
        hold_ns = hold_samples * SAMPLE_INTERVAL_NS
        knots.append((turn_t + hold_ns, knots[-1][1], knots[-1][2], "hold"))
        turn_t += hold_ns
    for k in range(1, HALF_STEPS + 1):
        z = 0.5 + k / (2.0 * HALF_STEPS)
        a = ease((1.0 - z) * 2.0)
        R, C = src.watch_pose(a)
        knots.append((turn_t + int(round(cycle_s * (z - 0.5) * 1e9)), R, C, "move"))
    return knots, turn_t, knots[-1][0]


def build_cycles(src, scales, hold_samples=0, t_start_ns=0):
    all_knots = []
    truth = []
    t = t_start_ns
    for rep, scale in enumerate(scales):
        local, turn, back = cycle_segments(src, scale, hold_samples)
        knots = [(t + lt, R, C, kind) for (lt, R, C, kind) in local]
        all_knots.extend(knots)
        truth.append({"rep": rep + 1, "cycle_scale": scale,
                      "cycle_duration_ms": round(scale * CYCLE_BASE_NS / 1e6, 3),
                      "start_ns": t, "turnaround_ns": t + turn, "full_return_ns": t + back})
        t = t + back
    return all_knots, truth, t


def add_knots(path, knots, t_start_ns, kind_action):
    prev_t, prev_R, prev_C = t_start_ns, knots[0][1], knots[0][2]
    for (tn, R, C, kind) in knots:
        k = "hold" if kind == "hold" else kind_action
        path.pieces.append(Piece(prev_t, prev_R, prev_C, tn, R, C, k))
        prev_t, prev_R, prev_C = tn, R, C
    path.t_end = max(path.t_end, prev_t)


# ---------------------------------------------------------------- sweep energy and terminal set-down
def sweep_energy(src):
    """Common-mode baseline (slow-moving gravity direction) vs per-pass rotation, sampled from the
    source path. Used only to describe the handle-down problem; not a detector and not truth."""
    R_start, C_start = src.watch_pose(0.0)
    prev_fwd = column(R_start, 0)
    baseline = list(prev_fwd)
    tau_s = 1.0
    forwards = []
    steps = 1280
    for k in range(steps + 1):
        a = viewer_phase(k / steps)
        Rw, _ = src.watch_pose(a)
        fwd = column(Rw, 0)
        forwards.append(fwd)
        baseline = madd(baseline, mscale(msub(fwd, baseline), 1.0 - math.exp(-(2.6 / steps) / tau_s)))
    dev = [msub(f, baseline) for f in forwards]
    dev_max = max(mnorm(d) for d in dev)
    common_max = max(mnorm(msub(f, mscale(baseline, mdot(f, baseline)))) for f in forwards)

    def of(rot):
        return [rot[0][i] * f[0] + rot[0][1] * f[1] + rot[0][2] * f[2] for i in range(3)] if False else mv(rot, f)

    fore = src.frame0["chest_front"]
    up = src.frame0["world_up"]
    samples = []
    for k in range(steps + 1):
        f = forwards[k]
        samples.append({
            "z": k / steps,
            "fwd": f,
            "fwd_within_5deg_of_forearm_axis": abs(mdot(f, src.frame0["chest_front"])) >= math.cos(math.radians(5)),
            "fwd_dot_up": round(mdot(f, up), 4),
        })
    return {
        "baseline_tau_s": tau_s,
        "max_deviation_from_baseline_mps": dev_max,
        "max_component_orthogonal_to_baseline_mps": common_max,
        "watch_forward_near_forearm_axis_fraction": sum(1 for s in samples if s["fwd_within_5deg_of_forearm_axis"]) / len(samples),
        "watch_forward_dot_up_range": [round(min(s["fwd_dot_up"] for s in samples), 3),
                                       round(max(s["fwd_dot_up"] for s in samples), 3)],
        "min_dot_forward_with_principal_axis": round(min(mdot(s["fwd"], PRINCIPAL_AXIS) for s in samples), 4),
        "principal_axis_method": "clean clip: min over the round trip of dot(watch_forward, principal axis), "
                                 "axis fixed as the 0.5 s boxcar mean of watch_forward / its norm (near constant)",
        "half_pass_rotation_deg": None,
    }


PRINCIPAL_AXIS = None  # set after Source exists (see set_principal_axis)


def set_principal_axis(src):
    global PRINCIPAL_AXIS
    us = [column(src.watch_pose(viewer_phase(k / 64.0))[0], 0) for k in range(65)]
    m = [sum(u[i] for u in us) for i in range(3)]
    PRINCIPAL_AXIS = munit(m) if mnorm(m) > 1e-9 else munit(us[0])


def terminal_plan(src):
    """Phase 0 -> phase 1 handle set-down built as one monotone chain of rotations (no reversal).

    A: shoulder swing about the chest-forward axis through the shoulder, signed so the watch centre
       rises (the handle is carried down and out at the end of the swing).
    B: forearm pronation about the forearm axis (when the forearm is clear of that axis), so the
       display rolls toward the palm side - a finer, genuinely different axis than the pull-down sweep.
    C: wrist relax: small painless flexion toward the palm side about the watch right (-x) axis.
    The end pose must keep the pull-down sweep axis (watch forward aligned with the clip's sweep axis
    and away from the forearm axis), so the common-mode baseline never re-locks onto the set-down axis.
    """
    R0, C0 = src.watch_pose(0.0)
    shoulder = src.shoulder0
    front = src.frame0["chest_front"]
    thrust = munit(msub(C0, shoulder))
    best = None
    for swing_sign in (1.0, -1.0):
        for swing_deg, pron_deg, relax_deg in TERMINAL_CANDIDATES:
            Rsw = rot_axis_angle(front, swing_sign * math.radians(swing_deg))
            R = mmul(Rsw, R0)
            C = madd(shoulder, mv(Rsw, msub(C0, shoulder)))
            fwd = column(R, 0)
            if abs(mdot(fwd, thrust)) < math.cos(math.radians(12)):
                R = mmul(rot_axis_angle(thrust, math.radians(pron_deg)), R)
            R = mmul(rot_axis_angle(mscale(column(R, 0), -1.0), math.radians(relax_deg)), R)
            drop = C0[2] - C[2]
            fwd_end = column(R, 0)
            aligned = mdot(fwd_end, PRINCIPAL_AXIS) >= TERMINAL_AXIS_DOT_MIN
            clear_of_forearm = abs(mdot(fwd_end, thrust)) <= math.cos(math.radians(TERMINAL_FOREARM_CLEAR_DEG))
            cand = {"swing_sign": swing_sign, "swing_deg": swing_deg, "pronation_deg": pron_deg,
                    "wrist_relax_deg": relax_deg, "R_end": R, "C_end": C, "drop_m": drop,
                    "forward_dot_sweep_axis": mdot(fwd_end, PRINCIPAL_AXIS),
                    "forward_dot_forearm_axis": abs(mdot(fwd_end, thrust)),
                    "keeps_sweep_axis": bool(aligned and clear_of_forearm)}
            if not cand["keeps_sweep_axis"]:
                continue
            if best is None or cand["drop_m"] > best["drop_m"]:
                best = cand
    if best is None:
        raise SystemExit("no non-returning terminal motion keeps the pull-down sweep axis")

    knots = []
    for k in range(1, TERMINAL_SAMPLES + 1):
        f = k / TERMINAL_SAMPLES
        fsw = min(1.0, f / 0.6)
        fpr = clamp01((f - 0.5) / 0.35)
        frl = clamp01((f - 0.65) / 0.35)
        Rsw = rot_axis_angle(front, best["swing_sign"] * math.radians(best["swing_deg"] * fsw))
        R = mmul(Rsw, R0)
        C = madd(shoulder, mv(Rsw, msub(C0, shoulder)))
        fwd = column(R, 0)
        if abs(mdot(fwd, thrust)) < math.cos(math.radians(12)):
            R = mmul(rot_axis_angle(thrust, math.radians(best["pronation_deg"]) * fpr), R)
        R = mmul(rot_axis_angle(mscale(column(R, 0), -1.0), math.radians(best["wrist_relax_deg"]) * frl), R)
        knots.append((R, C))
    best["knots"] = knots
    return best


# ---------------------------------------------------------------- sampling
def sensor_values(path, t_ns):
    """Accelerometer and gyroscope of the rigid watch at an exact 50 Hz sample instant.

    Rotation uses the three-point (central-difference) angular velocity, so no sample is dropped at piece
    boundaries. Translation is sampled on the grid at t-1, t, t+1 and unless all three are stationary the
    second difference is used; a sample is never split across a piece boundary. Centripetal term is zero
    because the sensor origin sits on the wrist rotation axis."""
    dt = SAMPLE_INTERVAL_NS
    R, C = path.pose(t_ns)
    Rm, Cm = (R, C) if t_ns <= 0 else path.pose(t_ns - dt)
    Rp, Cp = path.pose(t_ns + dt)
    Rt = mT(R)
    w = scale_axis(mmul(Rp, mT(Rm)), 2 * dt / 1e9)
    stationary = (mnorm(msub(Cp, C)) < 1e-12 and mnorm(msub(C, Cm)) < 1e-12
                  and rot_angle_deg(mmul(Rp, mT(R))) < 1e-9 and rot_angle_deg(mmul(R, mT(Rm))) < 1e-9)
    acc_world = mscale(GRAVITY_VEC, -1.0) if stationary else madd(mscale(GRAVITY_VEC, -1.0),
                                                                 mscale(madd(msub(Cp, C), msub(Cm, C)), 1.0 / (dt / 1e9) ** 2))
    return mv(Rt, acc_world), mv(Rt, w)


def scale_axis(Rrel, dt_s):
    c = (Rrel[0][0] + Rrel[1][1] + Rrel[2][2] - 1.0) / 2.0
    th = math.acos(max(-1.0, min(1.0, c)))
    if th < 1e-12:
        return [0.0, 0.0, 0.0]
    ax = [Rrel[2][1] - Rrel[1][2], Rrel[0][2] - Rrel[2][0], Rrel[1][0] - Rrel[0][1]]
    n = mnorm(ax)
    return mscale(ax, th / (dt_s * n)) if n > 1e-12 else [0.0, 0.0, 0.0]


# ---------------------------------------------------------------- case assembly
def assemble_path(src, cycles_scales, hold_samples, terminal, t_start=0):
    R_start, C_start = src.watch_pose(0.0)
    path = Path(R_start, C_start)
    knots, truth, t_end = build_cycles(src, cycles_scales, hold_samples, t_start)
    prev = (t_start, R_start, C_start)
    for (tn, R, C, kind) in knots:
        path.pieces.append(Piece(prev[0], prev[1], prev[2], tn, R, C, "hold" if kind == "hold" else "cycle"))
        prev = (tn, R, C)
    path.t_end = t_end
    term = None
    if terminal is not None:
        plan = src.terminal
        base_t = t_end
        base_R, base_C = src.watch_pose(0.0)
        prev = (base_t, base_R, base_C)
        for k, (R, C) in enumerate(plan["knots"], start=1):
            tn = base_t + k * SAMPLE_INTERVAL_NS
            path.pieces.append(Piece(prev[0], prev[1], prev[2], tn, R, C, "terminal"))
            prev = (tn, R, C)
        path.t_end = prev[0]
        term = {"start_ns": base_t, "end_ns": prev[0], "samples": len(plan["knots"]),
                "plan": {k: v for k, v in plan.items() if k not in ("R_end", "C_end", "knots")},
                "end_R": plan["R_end"], "end_C": plan["C_end"]}
    return path, truth, t_end, term


def render_case(path):
    total_ns = path.t_end + STILL_AFTER_TERMINAL_SAMPLES * SAMPLE_INTERVAL_NS
    n = total_ns // SAMPLE_INTERVAL_NS + 1
    records = []
    for i in range(n):
        t = i * SAMPLE_INTERVAL_NS
        a, g = sensor_values(path, t)
        records.append({
            "timestamp_ns": t,
            "acc": [f32(a[0]), f32(a[1]), f32(a[2])],
            "gyro": [f32(g[0]), f32(g[1]), f32(g[2])],
            "sensor_accuracy": 3,
            "received_elapsed_ns": PERFORMANCE_BASE_NS + t + RECEIVED_LEAD_NS,
        })
    return records


def snap(ns):
    return int(round(ns / SAMPLE_INTERVAL_NS)) * SAMPLE_INTERVAL_NS


def truth_reps(raw_truth):
    reps = []
    for r in raw_truth:
        turn = snap(r["turnaround_ns"])
        back = snap(r["full_return_ns"])
        reps.append({
            "rep": r["rep"],
            "cycle_scale": r["cycle_scale"],
            "cycle_duration_ms": r["cycle_duration_ms"],
            "start_ns": int(r["start_ns"]),
            "turnaround_ns": turn,
            "full_return_ns": back,
            "halfway_ns": int(round((r["start_ns"] + turn) / 2.0 / SAMPLE_INTERVAL_NS)) * SAMPLE_INTERVAL_NS,
        })
    return reps


def case_truth(name, reps, path, term):
    truth = {
        "schema": "vw05b-truth-1",
        "case": name,
        "exercise_id": EXERCISE_ID,
        "clip_id": CLIP_ID,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "prep": {"kind": "actual_stationary_sensor_data", "samples": PREP_SAMPLES, "seconds": PREP_SECONDS,
                 "count_window_start_ns": PREP_SAMPLES * SAMPLE_INTERVAL_NS},
        "cycle_semantics": "viewer 0 -> 1 -> 0 over 2600 ms (ease first half, mirrored ease second half); "
                           "start = phase 0, pull turnaround = phase 1, full return = phase 0 again",
        "reps": reps,
        "reps_expected": len(reps),
        "inputs_forecast": None,
        "sample_count": None,
        "duration_s": None,
        "terminal_motion": None,
        "truth_source": "source-oracle.json (viewer point-cache path), never a detector",
    }
    if term is not None:
        truth["terminal_motion"] = {
            "start_ns": term["start_ns"],
            "end_ns": term["end_ns"],
            "samples": term["samples"],
            "is_return": False,
            "returns_to_start": False,
        }
    return truth


def forecast_inputs(cases):
    """Inputs the Wear service would derive WITHOUT any rep knowledge: the set-end and tempo guards
    consume only lastMotionNs (motion detection) and pre-target tempo, so the forecast is the time when
    motion actually stops (source path), and a tempo guard estimate cannot fire on this longer swing."""
    stop_ns = {}
    for name, data in cases.items():
        recs = data["records"]
        last_move = 0
        for i in range(1, len(recs)):
            p, q = recs[i - 1], recs[i]
            if any(abs(q["acc"][k] - p["acc"][k]) > 1e-6 for k in range(3)) or any(abs(q["gyro"][k]) > 1e-6 for k in range(3)):
                last_move = q["timestamp_ns"]
        stop_ns[name] = last_move
    return {
        "method": "last sample whose accelerometer or gyroscope differs from its predecessor (source path), "
                  "the signal that drives lastMotionNs",
        "motion_stop_ns": stop_ns,
        "forecast": "no rep is known to the set-end or tempo guards before reps exist, so the service observes "
                    "stillness after the source motion stops and ends the set after its silence window; "
                    "that order is exercised by the test's documented delivery model",
    }


def mitchell_noise(n, seed):
    """Deterministic smooth noise in [-1, 1] (three uniforms, box-filtered): std ~0.27."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        x = (rng.uniform(-0.5, 0.5) + rng.uniform(-0.5, 0.5) + rng.uniform(-0.5, 0.5)) / 1.5
        out.append(float(max(-1.0, min(1.0, x))))
    return out


def apply_tempo_noise(records):
    n = len(records)
    na = mitchell_noise(3 * n, TEMPO_SEED)
    ng = mitchell_noise(3 * n, TEMPO_SEED + 1)
    a_sigma = TEMPO_NOISE_ACC_MPS2
    g_sigma = TEMPO_NOISE_GYRO_RADPS
    for i, r in enumerate(records):
        r["acc"] = [f32(r["acc"][k] + a_sigma * na[3 * i + k]) for k in range(3)]
        r["gyro"] = [f32(r["gyro"][k] + g_sigma * ng[3 * i + k]) for k in range(3)]
    return records


def build_all():
    base = json.loads(BASE_JSON.read_text())
    clip = json.loads(CLIP_JSON.read_text())
    viewer = VIEWER_HTML.read_text()
    files = {"base_json_sha256": sha256_bytes(BASE_JSON.read_bytes()),
             "clip_json_sha256": sha256_bytes(CLIP_JSON.read_bytes()),
             "viewer_index_sha256": sha256_bytes(VIEWER_HTML.read_bytes())}
    src = Source(base, clip, viewer, files)
    set_principal_axis(src)
    src.terminal = terminal_plan(src)
    analysis = analyse(src)

    cases = {}
    specs = [
        ("continuous_10_clean", CLEAN_SCALES, 0, None, False),
        ("continuous_10_tempo_variation", TEMPO_SCALES, 0, None, True),
        ("return_boundary_hold", CLEAN_SCALES, HOLD_SAMPLES, None, False),
        ("ten_then_handle_down", CLEAN_SCALES, 0, "terminal", False),
        ("handle_down_only", (), 0, "terminal", False),
    ]
    for (name, scales, hold, terminal, noisy) in specs:
        if name == "handle_down_only":
            R_start, C_start = src.watch_pose(0.0)
            path = Path(R_start, C_start)
            path.pieces.append(Piece(0, R_start, C_start, PREP_SAMPLES * SAMPLE_INTERVAL_NS, R_start, C_start, "hold"))
            path.t_end = PREP_SAMPLES * SAMPLE_INTERVAL_NS
        else:
            path, _, _, _ = assemble_path(src, scales, hold, terminal)
        records = render_case(path)
        if noisy:
            records = apply_tempo_noise(records)
        cases[name] = {"path": path, "records": records, "prep_end_ns": PREP_SAMPLES * SAMPLE_INTERVAL_NS}

    # truth for each case
    R_start, C_start = src.watch_pose(0.0)
    truth = {}
    terminal_ref = None
    for (name, scales, hold, terminal, noisy) in specs:
        if scales:
            _, raw_truth, t_end = build_cycles(src, scales, hold, 0)
            reps = truth_reps(raw_truth)
        else:
            t_end = PREP_SAMPLES * SAMPLE_INTERVAL_NS
            reps = []
        term = None
        if terminal:
            if terminal_ref is None:
                term_t0 = t_end
                terminal_ref = {
                    "start_ns": term_t0,
                    "end_ns": term_t0 + TERMINAL_SAMPLES * SAMPLE_INTERVAL_NS,
                    "samples": TERMINAL_SAMPLES,
                    "source": "constructed",
                    "plan": {k: (round(v, 6) if isinstance(v, float) else v)
                             for k, v in src.terminal.items() if k not in ("R_end", "C_end", "knots")},
                    "end_R": src.terminal["R_end"],
                    "end_C": src.terminal["C_end"],
                    "returns_to_start": False,
                }
            term = terminal_ref
        truth[name] = case_truth(name, reps, None, term)
        truth[name]["sample_count"] = len(cases[name]["records"])
        truth[name]["duration_s"] = (len(cases[name]["records"]) - 1) / SAMPLE_RATE_HZ
        cases[name]["truth"] = truth[name]

    # identical terminal segment proofs
    a = cases["ten_then_handle_down"]
    b = cases["handle_down_only"]
    t0 = terminal_ref["start_ns"]
    k0 = t0 // SAMPLE_INTERVAL_NS
    seg_a = a["records"][k0:k0 + TERMINAL_SAMPLES]
    seg_b = b["records"][k0:k0 + TERMINAL_SAMPLES]
    terminals = {
        "start_ns": t0,
        "samples": TERMINAL_SAMPLES,
        "source": "constructed (not authored by the viewer)",
        "spec": terminal_ref["plan"],
        "end_pose": {"R": terminal_ref["end_R"], "C": terminal_ref["end_C"]},
        "returns_to_start": False,
        "case_terminal_segment_sha256": sha256_bytes(encode_kcs(seg_a)),
        "handle_down_only_segment_sha256": sha256_bytes(encode_kcs(seg_b)),
        "identical": encode_kcs(seg_a) == encode_kcs(seg_b),
        "how": "both cases render the same segment object from one terminal plan at the same absolute sample "
               "instants (prep is identical and the set-down starts at the same sample index)",
    }
    if not terminals["identical"]:
        raise SystemExit("terminal segments are not identical")

    forecast = forecast_inputs(cases)
    return {"src": src, "analysis": analysis, "cases": cases, "terminals": terminals,
            "forecast": forecast, "files": files}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv[1:])
    built = build_all()
    planned = plan_outputs(built)
    if args.check:
        ok = True
        for rel, data in planned.items():
            path = SESSION_ROOT / rel
            if not path.exists() or path.read_bytes() != data:
                ok = False
                print("DIFF", rel)
        print("CHECK", "OK" if ok else "MISMATCH")
        return 0 if ok else 1
    for rel, data in planned.items():
        path = SESSION_ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print("WROTE", len(planned), "files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
