#!/usr/bin/env python3
"""Read-only V5 wrist extraction and offline synthetic KCS v2 generation.

The C2 sensor path is a diagnostic variation through published frame knots,
not the viewer's piecewise-linear surface or physical ground truth.
No engine tuning, app writes or device claims.
Requires only NumPy. See docs/VIRTUAL_WATCH_DESIGN.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import tempfile
from pathlib import Path

import numpy as np

GRAVITY = 9.80665
REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild"
WORK = REPO / "work/virtual-watch"
VERSION = "virtual-watch-5-published-surface-c2-variation"
NS0 = 1_000_000_000
HZ = 50
PREP_S, TAIL_S = 3.0, 8.0
PILOT = {
    "dumbbell_curl": ("dumbbell_curl", "덤벨 컬", 10),
    "dumbbell_lateral_raise": ("dumbbell_lateral_raise", "덤벨 레터럴 레이즈", 10),
    "barbell_overhead_press": ("barbell_overhead_press", "바벨 오버헤드 프레스", 8),
}
C2_VARIATIONS = {
    "lying_dumbbell_pullover": ("dumbbell_pullover", "덤벨 풀오버", 10),
}
CASES = {**PILOT, **C2_VARIATIONS}


def motion_provenance():
    """Describe the two intentionally distinct motion lanes."""
    return {
        "same_published_frame_knots": True,
        "viewer_surface": {
            "lane_id": "published_viewer_linear_surface",
            "interpolation": "piecewise_linear_vertex_positions",
            "derivative_authority": False,
        },
        "sensor_motion": {
            "lane_id": "synthetic_c2_sensor_variation",
            "interpolation": "natural_c2_pose_spline",
            "classification": "diagnostic_variation",
            "physical_ground_truth": False,
        },
        "relationship": "bounded_geometric_variation_not_equivalent_motion",
    }


def encode_capture(timestamps_ns, acceleration, gyro):
    """KCS v2, matching Java DataOutputStream's big-endian wire format."""
    t = np.asarray(timestamps_ns)
    a, g = np.asarray(acceleration), np.asarray(gyro)
    if (t.ndim != 1 or a.shape != (len(t), 3) or g.shape != a.shape
            or np.any(t < 0) or np.any(np.diff(t) <= 0)
            or not np.isfinite(a).all() or not np.isfinite(g).all()):
        raise ValueError("Invalid capture samples or timestamps")
    data = bytearray(struct.pack(">4siid", b"KCS1", 2, len(t), float(HZ)))
    for stamp, av, gv in zip(t, a, g):
        # No real accuracy, HR, callback arrival clock, or device identity. The app's SensorCaptureFormat V2 record
        # layout keeps six per-axis floats (SensorSample is float); pandas "/" division was producing doubles and
        # the original three-long v2 tail never matched the 76-byte reader.
        data.extend(struct.pack(">qffffff", int(stamp), *av, *gv))
        data.extend(struct.pack(">iiqqqiq", -1, -1, -1, -1, -1, -1, -1))
    return bytes(data)


def playback_phase(elapsed_s, metadata):
    """Exact viewer timing, not a new arm cycle; input is elapsed seconds."""
    duration = float(metadata.get("playback_ms") or 2600) / 1000
    start, end = metadata.get("playback_range") or [0.0, 1.0]
    if duration <= 0 or not 0 <= start < end <= 1:
        raise ValueError("Invalid viewer playback configuration")
    t = np.mod(np.asarray(elapsed_s, float) / duration, 1.0)
    mode = metadata.get("playback_mode", "pingpong")
    if mode == "cycle":
        phase = t
    elif mode == "pingpong":
        half = np.where(t < 0.5, t * 2, (1 - t) * 2)
        phase = np.where(half < 0.5, 2 * half**2, 1 - 2 * (1 - half)**2)
    else:
        raise ValueError("Unsupported viewer playback mode")
    return start + (end - start) * phase


def recover_watch(palettes, bind_hand, hand_from_watch):
    """Undo the inverse-bind convention before applying the rigid mounting."""
    result = np.asarray(palettes, float) @ bind_hand @ hand_from_watch
    if result.ndim != 3 or result.shape[1:] != (4, 4) or not np.isfinite(result).all():
        raise ValueError("Expected finite frame x 4 x 4 transforms")
    rotation = result[:, :3, :3]
    if (not np.allclose(result[:, 3], [0, 0, 0, 1], atol=1e-7)
            or not np.allclose(rotation.transpose(0, 2, 1) @ rotation, np.eye(3), atol=2e-5)
            or not np.allclose(np.linalg.det(rotation), 1, atol=2e-5)):
        raise ValueError("Non-rigid or reflected wrist transform")
    # Only remove accepted float32 round-off, never repair a bad source.
    u, _, vt = np.linalg.svd(rotation)
    result[:, :3, :3] = u @ vt
    return result


def left_dorsal_watch(wrist, middle, thumb, offset_watch_axes_m=(0., .012, .028)):
    """Build the assumed left-wrist device frame from anatomical landmarks."""
    y = np.asarray(wrist, float) - middle
    y /= np.linalg.norm(y)
    # With +Y proximal on a LEFT wrist, screen-right is ulnar, not radial.
    # Radial +X would put cross(X, Y) on the palm. Flip X AND Z (a proper
    # 180-degree rotation about Y), not Z alone (an invalid reflection).
    x = np.asarray(middle, float) - thumb
    x -= np.dot(x, y) * y
    x /= np.linalg.norm(x)
    basis = np.stack((x, y, np.cross(x, y)), axis=1)
    result = np.eye(4)
    result[:3, :3] = basis
    result[:3, 3] = wrist + basis @ offset_watch_axes_m
    return result


def proper_rigid_fit(source, target):
    """Return the proper rigid transform that best maps source to target."""
    source, target = np.asarray(source, float), np.asarray(target, float)
    if (source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3
            or len(source) < 3 or not np.isfinite(source).all() or not np.isfinite(target).all()):
        raise ValueError("Expected matching finite point sets")
    source_center, target_center = source.mean(0), target.mean(0)
    u, singular, vt = np.linalg.svd((source - source_center).T @ (target - target_center))
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(vt.T @ u.T)
    rotation = vt.T @ correction @ u.T
    translation = target_center - rotation @ source_center
    if (not np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-7)
            or not np.isclose(np.linalg.det(rotation), 1, atol=2e-7)):
        raise ValueError("Rigid fit produced a reflected or non-rigid transform")
    return rotation, translation, singular


def rotation_angle_degrees(first, second):
    delta = np.asarray(first, float).T @ np.asarray(second, float)
    return float(np.degrees(np.arccos(np.clip((np.trace(delta) - 1) / 2, -1, 1))))


def ray_triangle_hit(vertices, triangles, origin, direction):
    """Nearest non-negative Moller-Trumbore hit, including its residual."""
    vertices, triangles = np.asarray(vertices, float), np.asarray(triangles, int)
    origin, direction = np.asarray(origin, float), np.asarray(direction, float)
    norm = np.linalg.norm(direction)
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or triangles.ndim != 2
            or triangles.shape[1] != 3 or not np.isfinite(origin).all() or norm < 1e-12):
        raise ValueError("Invalid ray or triangle surface")
    direction = direction / norm
    vertex0 = vertices[triangles[:, 0]]
    edge1 = vertices[triangles[:, 1]] - vertex0
    edge2 = vertices[triangles[:, 2]] - vertex0
    cross = np.cross(direction[None, :], edge2)
    determinant = np.einsum("ij,ij->i", edge1, cross)
    valid = np.abs(determinant) > 1e-10
    inverse = np.zeros_like(determinant)
    inverse[valid] = 1 / determinant[valid]
    relative = origin - vertex0
    u = np.einsum("ij,ij->i", relative, cross) * inverse
    q = np.cross(relative, edge1)
    v = np.einsum("j,ij->i", direction, q) * inverse
    distance = np.einsum("ij,ij->i", edge2, q) * inverse
    valid &= (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (distance >= -1e-9)
    hits = np.flatnonzero(valid)
    if not len(hits):
        raise ValueError("Watch caseback ray missed the published wrist surface")
    triangle_id = int(hits[np.argmin(distance[hits])])
    barycentric = np.array([1 - u[triangle_id] - v[triangle_id], u[triangle_id], v[triangle_id]])
    contact = barycentric @ vertices[triangles[triangle_id]]
    residual = float(np.linalg.norm(contact - (origin + direction * distance[triangle_id])))
    return triangle_id, float(distance[triangle_id]), barycentric, contact, residual


def published_surface_watch(base, frames, rest, palettes, bind, names):
    """Fit the pullover watch to the published point-cache wrist surface."""
    triangles = np.asarray(base["triangles"], int).reshape(-1, 3)
    joints, weights = np.asarray(base["joints"]), np.asarray(base["weights"], float)
    lowerarm, hand = names.index("lowerarm_l"), names.index("hand_l")

    def bone_weight(bone):
        return np.where(joints == bone, weights, 0).sum(1)

    lowerarm_weight, hand_weight = bone_weight(lowerarm), bone_weight(hand)
    total_weight = weights.sum(1)
    ring = np.flatnonzero(np.isclose(lowerarm_weight, .75, atol=1e-6)
                          & np.isclose(hand_weight, .25, atol=1e-6)
                          & np.isclose(total_weight, 1, atol=1e-6))
    if len(ring) < 6 or len(ring) % 2:
        raise ValueError("Published wrist blend ring was not found unambiguously")
    touches_ring = np.any(np.isin(triangles, ring), axis=1)
    adjacent = np.unique(triangles[touches_ring])
    proximal = np.asarray(sorted(set(adjacent.tolist()) - set(ring.tolist())), int)
    proximal = proximal[(lowerarm_weight[proximal] >= .95) & (hand_weight[proximal] <= .05)]
    if len(proximal) < 3:
        raise ValueError("Published proximal wrist neighbours were not found")

    wrist = bind[hand, :3, 3]
    middle = bind[names.index("middle_01_l"), :3, 3]
    thumb = bind[names.index("thumb_01_l"), :3, 3]
    anatomical_dorsal = left_dorsal_watch(wrist, middle, thumb, (0, 0, 0))[:3, 2]
    rest_center = rest[ring].mean(0)
    dorsal_score = (rest[ring] - rest_center) @ anatomical_dorsal
    dorsal = ring[np.argsort(dorsal_score)[len(ring) // 2:]]

    reference = frames[0, ring]
    reference_center = reference.mean(0)
    _, ring_singular, vt = np.linalg.svd(reference - reference_center, full_matrices=False)
    y_axis = vt[-1]
    proximal_direction = frames[0, proximal].mean(0) - reference_center
    if np.dot(y_axis, proximal_direction) < 0:
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
    if not np.isclose(np.linalg.det(reference_basis), 1, atol=2e-7):
        raise ValueError("Published wrist frame is not right handed")

    rotations, contacts, ring_centers = [], [], []
    rigid_errors, outward_dots, surface_distances = [], [], []
    triangle_ids, ray_distances, predicted_contacts = [], [], []
    reference_contact = None
    for frame, target in zip(frames, frames[:, ring]):
        rotation, translation, _ = proper_rigid_fit(reference, target)
        basis = rotation @ reference_basis
        center = target.mean(0)
        ray_origin = center + basis[:, 1] * .012
        triangle_id, ray_distance, _, contact, residual = ray_triangle_hit(
            frame, triangles, ray_origin, basis[:, 2])
        dorsal_direction = frame[dorsal].mean(0) - center
        dorsal_direction -= np.dot(dorsal_direction, basis[:, 1]) * basis[:, 1]
        dorsal_direction /= np.linalg.norm(dorsal_direction)
        rotations.append(basis)
        contacts.append(contact)
        ring_centers.append(center)
        triangle_ids.append(triangle_id)
        ray_distances.append(ray_distance)
        rigid_errors.append(np.linalg.norm((rotation @ reference.T).T + translation - target, axis=1).max())
        outward_dots.append(np.dot(basis[:, 2], dorsal_direction))
        surface_distances.append(residual)
        if reference_contact is None:
            reference_contact = contact
        predicted_contacts.append(rotation @ reference_contact + translation)

    rotations, contacts, ring_centers = map(np.asarray, (rotations, contacts, ring_centers))
    predicted_contacts = np.asarray(predicted_contacts)
    poses = np.tile(np.eye(4), (len(frames), 1, 1))
    poses[:, :3, :3] = rotations
    # This is a surface-contact proxy, not a claimed physical IMU location.
    poses[:, :3, 3] = contacts
    palette_ring = (np.einsum("fij,nj->fni", palettes[:, lowerarm, :3, :3], rest[ring])
                    + palettes[:, lowerarm, None, :3, 3])
    palette_error = float(np.linalg.norm(palette_ring - frames[:, ring], axis=2).max() * 1000)
    orientation_span = max(rotation_angle_degrees(a, b) for i, a in enumerate(rotations)
                           for b in rotations[i + 1:])
    adjacent_step = max(rotation_angle_degrees(a, b) for a, b in zip(rotations, rotations[1:]))
    offset = rotations[0].T @ (contacts[0] - ring_centers[0])
    qa = {
        "surface_ring_vertex_ids": ring.tolist(),
        "surface_proximal_vertex_ids": proximal.tolist(),
        "surface_dorsal_vertex_ids": dorsal.tolist(),
        "surface_ring_singular_values_mm": (ring_singular * 1000).tolist(),
        "surface_ring_min_to_max_singular_ratio": float(ring_singular[-1] / ring_singular[0]),
        "surface_rigid_fit_max_error_mm": float(max(rigid_errors) * 1000),
        "surface_orientation_span_deg": orientation_span,
        "adjacent_orientation_max_step_deg": adjacent_step,
        "screen_outward_min_dot": float(min(outward_dots)),
        "caseback_surface_max_distance_mm": float(max(surface_distances) * 1000),
        "caseback_rigid_prediction_max_error_mm": float(
            np.linalg.norm(predicted_contacts - contacts, axis=1).max() * 1000),
        "caseback_triangle_ids": sorted(set(triangle_ids)),
        "caseback_ray_distance_range_mm": [float(min(ray_distances) * 1000),
                                               float(max(ray_distances) * 1000)],
        "palette_only_ring_max_error_mm": palette_error,
        "palette_only_carrier_rejected": palette_error > 1.0,
        "frame_count": len(frames),
    }
    if (not qa["palette_only_carrier_rejected"] or qa["surface_rigid_fit_max_error_mm"] >= 1
            or qa["screen_outward_min_dot"] <= .99 or qa["caseback_surface_max_distance_mm"] >= .001
            or not np.allclose(np.linalg.det(rotations), 1, atol=2e-5)):
        raise ValueError("Published wrist surface attachment validation failed")
    mount = {
        "arm": "left", "surface": "dorsal", "carrier": "published final wrist surface",
        "dynamic_orientation_source": "published point-cache vertices only",
        "caseback_contact_source": "published point-cache triangle ray hit",
        "offset_watch_axes_m": offset.tolist(),
        "preview_watch_center_offset_device_m": [0, 0, .0045],
        "axes": "+X screen right (ulnar), +Y screen top (proximal), +Z screen outward (dorsal); assumed strap alignment",
        "screen_normal_device": [0, 0, 1], "case_back_normal_device": [0, 0, -1],
        "pose_origin": "caseback surface contact proxy", "physically_calibrated": False,
    }
    return poses, ring_centers, qa, mount


def sensors_from_motion(times_s, pose, step_s=0.001):
    """Differentiate a continuous (position, world-from-watch rotation) path.

    Gyro is the log of the relative rotation, expressed at the central sample.
    The differentiation step is independent of the 50 Hz capture grid.
    """
    t = np.asarray(times_s, dtype=float)
    if step_s <= 0 or not np.isfinite(step_s):
        raise ValueError("Positive derivative step required")
    p, r = pose(t)
    before, rb = pose(t - step_s)
    after, ra = pose(t + step_s)
    world_acceleration = (after - 2 * p + before) / step_s**2
    acceleration = np.einsum("nji,nj->ni", r, world_acceleration - [0, 0, -GRAVITY])
    relative = np.einsum("nji,njk->nik", rb, ra)
    angle = np.arccos(np.clip((np.trace(relative, axis1=1, axis2=2) - 1) / 2, -1, 1))
    if np.any(angle > np.pi * 0.9):
        raise ValueError("Rotation jumps too far within a derivative step")
    factor = np.ones_like(angle)
    np.divide(angle, np.sin(angle), out=factor, where=angle > 1e-7)
    vector = np.stack((relative[:, 2, 1] - relative[:, 1, 2],
                       relative[:, 0, 2] - relative[:, 2, 0],
                       relative[:, 1, 0] - relative[:, 0, 1]), axis=1) * factor[:, None] / (4 * step_s)
    world_rate = np.einsum("nij,nj->ni", rb, vector)
    gyro = np.einsum("nji,nj->ni", r, world_rate)
    if not np.isfinite(acceleration).all() or not np.isfinite(gyro).all():
        raise ValueError("Non-finite synthetic sensor values")
    return acceleration, gyro


class CubicCurve:
    """Natural C2 interpolant through the published samples (NumPy only)."""
    def __init__(self, phases, values):
        self.x, self.y = np.asarray(phases, float), np.asarray(values, float)
        h = np.diff(self.x)
        if len(self.x) < 2 or np.any(h <= 0) or not np.isfinite(self.y).all():
            raise ValueError("Invalid interpolation samples")
        n = len(self.x)
        a, rhs = np.eye(n), np.zeros_like(self.y)
        for i in range(1, n - 1):
            a[i, i - 1:i + 2] = [h[i - 1], 2 * (h[i - 1] + h[i]), h[i]]
            rhs[i] = 6 * ((self.y[i + 1] - self.y[i]) / h[i]
                          - (self.y[i] - self.y[i - 1]) / h[i - 1])
        self.second = np.linalg.solve(a, rhs)

    def __call__(self, phase):
        phase = np.clip(np.asarray(phase, float), self.x[0], self.x[-1])
        i = np.clip(np.searchsorted(self.x, phase, side="right") - 1, 0, len(self.x) - 2)
        h = self.x[i + 1] - self.x[i]
        b = ((phase - self.x[i]) / h)[:, None]
        a = 1 - b
        return (a * self.y[i] + b * self.y[i + 1]
                + ((a**3 - a) * self.second[i] + (b**3 - b) * self.second[i + 1]) * h[:, None]**2 / 6)


def rotation_quaternions(rotations):
    """xyzw, with a continuous sign lift rather than per-frame hemisphere cuts."""
    values = []
    for m in rotations:
        trace = np.trace(m)
        if trace > 0:
            s = np.sqrt(trace + 1) * 2
            q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s,
                 (m[1, 0] - m[0, 1]) / s, s / 4]
        else:
            i = int(np.argmax(np.diag(m)))
            j, k = (i + 1) % 3, (i + 2) % 3
            s = np.sqrt(1 + m[i, i] - m[j, j] - m[k, k]) * 2
            q = np.zeros(4)
            q[i], q[j], q[k], q[3] = s / 4, (m[j, i] + m[i, j]) / s, (m[k, i] + m[i, k]) / s, (m[k, j] - m[j, k]) / s
        q = np.asarray(q) / np.linalg.norm(q)
        if values and np.dot(q, values[-1]) < 0:
            q = -q
        values.append(q)
    return np.asarray(values)


def quaternion_rotations(quaternions):
    norm = np.linalg.norm(quaternions, axis=1, keepdims=True)
    if np.any(norm < 0.1):
        raise ValueError("Quaternion interpolation crossed a singularity")
    x, y, z, w = (quaternions / norm).T
    return np.stack((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
                     2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
                     2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)), axis=1).reshape(-1, 3, 3)


class PoseCurve:
    def __init__(self, phases, poses):
        self.position = CubicCurve(phases, poses[:, :3, 3])
        self.rotation = CubicCurve(phases, rotation_quaternions(poses[:, :3, :3]))

    def __call__(self, phase):
        return self.position(phase), quaternion_rotations(self.rotation(phase))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_clip(model_id, viewer_root=None):
    """Recover a watch carrier and independently check it against the surface."""
    if model_id not in CASES:
        raise ValueError("This generator only supports its named C2 variation cases")
    if viewer_root is None:
        candidates = [Path.home() / "Library/Application Support" / name / "v5-catalog"
                      for name in ("__PROTECTED_WATCHCOACH_VIEWER__", "WatchGymViewer")]
        viewer_root = next((p for p in candidates if (p / "base.json").is_file()), None)
    if viewer_root is None:
        raise FileNotFoundError("Published V5 catalog is unavailable; pass --viewer-root")
    viewer_root = Path(viewer_root)
    paths = {
        "published_motion": viewer_root / f"{model_id}.json",
        "published_base": viewer_root / "base.json",
        "published_manifest": viewer_root / "manifest.json",
        "final_skin": DESIGN / "catalog_trial" / f"{model_id}.skin.bin",
        "anatomical_bind": DESIGN / "anatomical_rest.json",
        "viewer_timing": REPO / "tools/viewer3d/index.html",
    }
    hashes = {name: digest(p) for name, p in paths.items()}
    base = json.loads(paths["published_base"].read_text())
    motion = json.loads(paths["published_motion"].read_text())
    metadata = next(c for c in json.loads(paths["published_manifest"].read_text())["clips"] if c["id"] == model_id)
    bind = np.asarray(json.loads(paths["anatomical_bind"].read_text())["rest_matrices"])
    names = base["bone_names"]
    acts = np.asarray(motion["acts"], float)
    rest = np.asarray(base["rest"]).reshape(-1, 3)
    frames = np.asarray(motion["frames"]).reshape(len(acts), len(rest), 3)
    palettes = np.fromfile(paths["final_skin"], dtype="<f4").reshape(len(acts), len(names), 4, 4).astype(float)
    if not np.isfinite(frames).all() or np.any(np.diff(acts) <= 0):
        raise ValueError("Invalid published motion")
    if motion["tris"] != base["triangles"] or bind.shape != (len(names), 4, 4):
        raise ValueError("Published topology or bind does not match")
    h = names.index("hand_l")
    joints, weights = np.asarray(base["joints"]), np.asarray(base["weights"])
    if model_id == "lying_dumbbell_pullover":
        poses, wrist, qa, mount = published_surface_watch(
            base, frames, rest, palettes, bind, names)
        qa["source_unchanged"] = hashes == {k: digest(p) for k, p in paths.items()}
        if not qa["source_unchanged"]:
            raise ValueError("Published source changed during surface validation")
        return {"model_id": model_id, "base": base, "frames": frames, "acts": acts, "poses": poses,
                "wrist": wrist, "metadata": metadata, "qa": qa, "mount": mount,
                "sources": {k: {"path": str(p.resolve()), "sha256": hashes[k]} for k, p in paths.items()}}
    ids = np.flatnonzero(np.where(joints == h, weights, 0).sum(1) > .999999)
    landmarks = rest[ids]
    if len(ids) < 3 or np.linalg.matrix_rank(landmarks - landmarks.mean(0), tol=1e-6) < 2:
        raise ValueError("Not enough noncollinear rigid palm landmarks")
    predicted = np.einsum("fij,nj->fni", palettes[:, h, :3, :3], landmarks) + palettes[:, h, None, :3, 3]
    palm_error = float(np.linalg.norm(predicted - frames[:, ids], axis=2).max() * 1000)
    if palm_error > .02:
        raise ValueError(f"Final skin does not match published palm: {palm_error:.4f} mm")
    wrist_rest = bind[h, :3, 3]
    # Frame derived from this hand's anatomy, not from a different exercise.
    middle = bind[names.index("middle_01_l"), :3, 3]
    thumb = bind[names.index("thumb_01_l"), :3, 3]
    offset = np.array([0.0, .012, .028])  # m: proximal and dorsal; simulation, not Watch8 calibration
    rest_watch = left_dorsal_watch(wrist_rest, middle, thumb, offset)
    basis = rest_watch[:3, :3]
    hand_from_watch = np.linalg.inv(bind[h]) @ rest_watch
    poses = recover_watch(palettes[:, h], bind[h], hand_from_watch)
    wrist = recover_watch(palettes[:, h], bind[h], np.eye(4))[:, :3, 3]
    # A separate rigid fit to the displayed surface checks both origin AND axes.
    wrist_errors, orientation_errors = [], []
    centered = landmarks - landmarks.mean(0)
    for target, actual_wrist, actual_pose in zip(frames[:, ids], wrist, poses):
        u, _, vt = np.linalg.svd(centered.T @ (target - target.mean(0)))
        correction = np.eye(3)
        correction[-1, -1] = np.linalg.det(vt.T @ u.T)
        r = vt.T @ correction @ u.T
        shift = target.mean(0) - r @ landmarks.mean(0)
        wrist_errors.append(np.linalg.norm(r @ wrist_rest + shift - actual_wrist) * 1000)
        delta = (r @ basis).T @ actual_pose[:3, :3]
        orientation_errors.append(np.degrees(np.arccos(np.clip((np.trace(delta)-1)/2, -1, 1))))
    qa = {"rigid_palm_vertex_ids": ids.tolist(), "palm_max_error_mm": palm_error,
          "independent_wrist_fit_max_error_mm": float(max(wrist_errors)),
          "independent_orientation_fit_max_error_deg": float(max(orientation_errors)),
          "frame_count": len(acts), "source_unchanged": hashes == {k: digest(p) for k, p in paths.items()}}
    if max(wrist_errors) > .05 or max(orientation_errors) > .05 or not qa["source_unchanged"]:
        raise ValueError("Independent surface attachment validation failed")
    return {"model_id": model_id, "base": base, "frames": frames, "acts": acts, "poses": poses,
            "wrist": wrist, "metadata": metadata, "qa": qa,
            "mount": {"arm": "left", "surface": "dorsal", "carrier": "rigid hand at anatomical wrist", "offset_watch_axes_m": offset.tolist(),
                      "preview_watch_center_offset_device_m": [0, 0, 0],
                      "axes": "+X screen right (ulnar), +Y screen top (proximal), +Z screen outward (dorsal); assumed strap alignment",
                      "screen_normal_device": [0, 0, 1], "case_back_normal_device": [0, 0, -1],
                      "hand_from_watch": hand_from_watch.tolist(), "physically_calibrated": False},
            "sources": {k: {"path": str(p.resolve()), "sha256": hashes[k]} for k, p in paths.items()}}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sample_clip(clip, reps):
    metadata = clip["metadata"]
    if metadata.get("playback_mode", "pingpong") != "pingpong":
        raise ValueError("Explicit-cycle sources need authored reversal labels; not in this pilot")
    period = float(metadata.get("playback_ms") or 2600) / 1000
    curve = PoseCurve(clip["acts"], clip["poses"])
    total = PREP_S + reps * period + TAIL_S
    times = np.arange(round(total * HZ) + 1, dtype=float) / HZ
    stamps = NS0 + np.arange(len(times), dtype=np.int64) * (1_000_000_000 // HZ)
    start_phase = (metadata.get("playback_range") or [0, 1])[0]

    def pose(t):
        phase = playback_phase(np.clip(t - PREP_S, 0, reps * period), metadata)
        phase[(t <= PREP_S) | (t >= PREP_S + reps * period)] = start_phase
        return curve(phase)

    acceleration, gyro = sensors_from_motion(times, pose)
    a_fine, g_fine = sensors_from_motion(times, pose, step_s=.0005)
    a_difference = float(np.linalg.norm(a_fine - acceleration, axis=1).max())
    g_difference = float(np.linalg.norm(g_fine - gyro, axis=1).max())
    if a_difference > .15 or g_difference > .005:
        raise ValueError(f"Unstable sensor differentiation: accel={a_difference}, gyro={g_difference}")
    static = (times < PREP_S - .002) | (times > PREP_S + reps * period + .002)
    if np.max(np.abs(np.linalg.norm(acceleration[static], axis=1) - GRAVITY)) > 1e-6 or np.max(np.abs(gyro[static])) > 1e-7:
        raise ValueError("Static prep/tail contains synthetic motion")
    joins = PREP_S + np.arange(reps * 2 + 1) * period / 2
    before, _ = pose(joins - .001)
    after, _ = pose(joins + .001)
    join_speed = float(np.linalg.norm((after - before) / .002, axis=1).max())
    if join_speed > .02:
        raise ValueError("Motion is not stationary at a rep/reversal/static join")
    # Compare the smooth derivative path to what the point-cache viewer draws.
    phases = np.linspace(clip["acts"][0], clip["acts"][-1], 1001)
    p, r = curve(phases)
    surface_carrier = "surface_ring_vertex_ids" in clip["qa"]
    ids = clip["qa"]["surface_ring_vertex_ids" if surface_carrier else "rigid_palm_vertex_ids"]
    local = (clip["frames"][0, ids] - clip["poses"][0, :3, 3]) @ clip["poses"][0, :3, :3]
    carried = np.einsum("fij,nj->fni", r, local) + p[:, None]
    i = np.clip(np.searchsorted(clip["acts"], phases, side="right") - 1, 0, len(clip["acts"]) - 2)
    f = ((phases - clip["acts"][i]) / (clip["acts"][i+1] - clip["acts"][i]))[:, None, None]
    shown = clip["frames"][i][:, ids] * (1-f) + clip["frames"][i+1][:, ids] * f
    interpolation_error = float(np.linalg.norm(carried - shown, axis=2).max() * 1000)
    position_fraction = f[:, 0, 0][:, None]
    linear_positions = (clip["poses"][i, :3, 3] * (1 - position_fraction)
                        + clip["poses"][i + 1, :3, 3] * position_fraction)
    position_interpolation_error = float(np.linalg.norm(p - linear_positions, axis=1).max() * 1000)
    if surface_carrier:
        # This 3 mm bound describes this diagnostic C2-vs-viewer variation only;
        # it is not a physical-watch or measurement-accuracy tolerance.
        interpolation_limit = 3.0
        if interpolation_error > interpolation_limit:
            raise ValueError(f"C2 wrist carrier exceeds its diagnostic variation boundary: {interpolation_error:.3f} mm")
    elif interpolation_error > 2:
        raise ValueError(f"Smoothed watch deviates from displayed palm: {interpolation_error:.3f} mm")
    qa = dict(clip["qa"], derivative_step_s=.001,
              derivative_halving_max_acceleration_delta_mps2=a_difference,
              derivative_halving_max_gyro_delta_radps=g_difference,
              static_gravity_checked=True, static_gyro_checked=True,
              join_max_speed_mps=join_speed,
              max_acceleration_norm_mps2=float(np.linalg.norm(acceleration, axis=1).max()),
              max_gyro_norm_radps=float(np.linalg.norm(gyro, axis=1).max()))
    if surface_carrier:
        qa.update(interpolated_carrier_max_deviation_mm=interpolation_error,
                  interpolated_caseback_max_deviation_mm=position_interpolation_error,
                  interpolated_carrier_variation_limit_mm=interpolation_limit,
                  interpolated_carrier_limit_meaning="diagnostic C2-vs-published-linear variation boundary, not accuracy tolerance")
    else:
        qa["interpolated_palm_max_deviation_mm"] = interpolation_error
    return stamps, acceleration, gyro, qa, period, curve


def generate_case(model_id, root=WORK, viewer_root=None):
    clip = load_clip(model_id, viewer_root)
    exercise_id, label, reps = CASES[model_id]
    stamps, acceleration, gyro, qa, period, curve = sample_clip(clip, reps)
    provenance = motion_provenance()
    generator_hash = digest(__file__)
    preview_template = Path(__file__).with_name("virtual_watch_preview.html")
    sources = dict(clip["sources"], generator={"path": str(Path(__file__).resolve()), "sha256": generator_hash},
                   preview_template={"path": str(preview_template), "sha256": digest(preview_template)})
    configuration = {"model_id": model_id, "exercise_id": exercise_id, "reps": reps, "hz": HZ,
                     "prep_s": PREP_S, "tail_s": TAIL_S, "mount": clip["mount"],
                     "metadata": clip["metadata"], "motion_provenance": provenance,
                     "source_sha256": {k: v["sha256"] for k, v in sources.items()}}
    fingerprint = hashlib.sha256(json_bytes(configuration)).hexdigest()
    case_id = f"{model_id}-{fingerprint[:16]}"
    truth = {"source": "synthetic", "case_id": case_id, "exercise_id": exercise_id,
             "motion_lane": provenance["sensor_motion"]["lane_id"],
             "reference": "viewer playback schedule only; sensor motion is a C2 diagnostic variation independent of detector output",
             "expected_reps": reps,
             "preparation": {"start_ns": int(stamps[0]), "end_ns": NS0 + round(PREP_S * 1e9)},
             "ending_static": {"start_ns": NS0 + round((PREP_S + period * reps) * 1e9), "end_ns": int(stamps[-1])},
             "repetitions": [{"index": i + 1, "start_ns": NS0 + round((PREP_S + i * period) * 1e9),
                              "turnaround_ns": NS0 + round((PREP_S + (i + .5) * period) * 1e9),
                              "end_ns": NS0 + round((PREP_S + (i + 1) * period) * 1e9)} for i in range(reps)]}
    capture = encode_capture(stamps, acceleration, gyro)
    # Same sensor interpolant, with the unmodified displayed surface alongside it.
    preview_times = np.linspace(0, period, round(period * 200) + 1)
    pp, rr = curve(playback_phase(preview_times, clip["metadata"]))
    preview = {"label": label, "model_id": model_id, "case_id": case_id, "period_s": period,
               "motion_provenance": provenance,
               "metadata": clip["metadata"], "acts": clip["acts"].tolist(),
               "frames": clip["frames"].reshape(len(clip["acts"]), -1).tolist(), "triangles": clip["base"]["triangles"],
               "sample_times_s": preview_times.tolist(), "positions": pp.tolist(),
               "quaternions": rotation_quaternions(rr).tolist(), "mount": clip["mount"], "qa": qa}
    manifest = {"source": "synthetic", "schema": 1, "case_id": case_id, "label": label,
                "exercise_id": exercise_id, "model_id": model_id, "generator_version": VERSION,
                "fingerprint": fingerprint, "configuration": configuration,
                "motion_provenance": provenance, "sources": sources,
                "sample_count": len(stamps), "start_ns": int(stamps[0]), "end_ns": int(stamps[-1]),
                "units": {"length": "m", "acceleration": "m/s^2 incl gravity", "gyro": "rad/s", "clock": "synthetic monotonic ns"},
                "qa": qa, "limitations": ["No physical Watch8 or strap calibration", "No noise, drift, latency or dropped samples",
                    "C2 sensor motion is a bounded diagnostic variation, not viewer-exact or physical ground truth",
                    "Rigid hand/wrist carrier, not soft-tissue or strap simulation", "Source publication metadata is not a visual approval",
                    "Offline generic detector only; no learned user pattern or service/start/end gates", "No app data, assets or release modified"],
                "files": {"capture.kcs": hashlib.sha256(capture).hexdigest(),
                          "truth.json": hashlib.sha256(json_bytes(truth)).hexdigest()}}
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / case_id
    if target.exists():
        verify_case(target)
        if (target / "capture.kcs").read_bytes() != capture or (target / "truth.json").read_bytes() != json_bytes(truth):
            raise ValueError("Deterministic case collision; existing result was not overwritten")
        return target
    with tempfile.TemporaryDirectory(prefix=".generating-", dir=root) as temporary:
        out = Path(temporary)
        (out / "capture.kcs").write_bytes(capture)
        (out / "truth.json").write_bytes(json_bytes(truth))
        (out / "manifest.json").write_bytes(json_bytes(manifest))
        (out / "preview.json").write_bytes(json.dumps(preview, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
        (out / "preview.html").write_bytes(preview_template.read_bytes())
        verify_case(out)
        out.rename(target)
    return target


def verify_case(case):
    case = Path(case)
    manifest = json.loads((case / "manifest.json").read_text())
    truth = json.loads((case / "truth.json").read_text())
    if manifest["source"] != "synthetic" or truth["source"] != "synthetic":
        raise ValueError("Synthetic provenance is missing")
    if manifest.get("motion_provenance") != motion_provenance():
        raise ValueError("Synthetic motion provenance is missing or ambiguous")
    for name, expected in manifest["files"].items():
        if digest(case / name) != expected:
            raise ValueError(f"Capture integrity mismatch: {name}")
    data = (case / "capture.kcs").read_bytes()
    magic, version, count, hz = struct.unpack(">4siid", data[:20])
    if (magic, version, hz) != (b"KCS1", 2, float(HZ)) or len(data) != 20 + count * 76 or count != manifest["sample_count"]:
        raise ValueError("Invalid KCS v2 structure")
    previous = None
    for record in struct.iter_unpack(">q6fiiqqqiq", data[20:]):
        stamp = record[0]
        if previous is not None and stamp - previous != 1_000_000_000 // HZ:
            raise ValueError("Unexpected synthetic sample clock")
        if record[7:] != (-1, -1, stamp, stamp, -1, -1, -1) or not np.isfinite(record[1:7]).all():
            raise ValueError("Unexpected device-only metadata or invalid sensor value")
        previous = stamp
    if len(truth["repetitions"]) != truth["expected_reps"]:
        raise ValueError("Invalid independent repetition labels")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clips", nargs="+", choices=list(CASES), default=list(PILOT))
    parser.add_argument("--viewer-root", type=Path)
    parser.add_argument("--verify", action="store_true", help="Verify only the cases in pilot-cases.json")
    args = parser.parse_args()
    index = WORK / "pilot-cases.json"
    if args.verify:
        for case_id in json.loads(index.read_text())["cases"]:
            verify_case(WORK / case_id)
            print("VERIFIED", case_id)
    else:
        cases = [generate_case(key, viewer_root=args.viewer_root) for key in args.clips]
        index.write_bytes(json_bytes({"source": "synthetic", "cases": [p.name for p in cases]}))
        for case in cases:
            m = verify_case(case)
            print("GENERATED", case.name, "samples", m["sample_count"], "QA", json.dumps(m["qa"], ensure_ascii=False))


if __name__ == "__main__":
    main()
