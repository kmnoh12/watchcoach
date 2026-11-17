"""Focused offline virtual-watch contracts; never runs or changes the app."""
import unittest
import struct
import hashlib
import tempfile
from pathlib import Path

import numpy as np

import gen_virtual_watch_pilot as watch


class VirtualWatchTest(unittest.TestCase):
    def test_stationary_watch_reports_gravity_and_no_rotation(self):
        times = np.arange(0.0, 1.0, 0.02)

        def stationary(t):
            return np.tile([1.0, 2.0, 3.0], (len(t), 1)), np.tile(np.eye(3), (len(t), 1, 1))

        acceleration, gyro = watch.sensors_from_motion(times, stationary)
        np.testing.assert_allclose(acceleration, np.tile([0, 0, 9.80665], (len(times), 1)), atol=1e-8)
        np.testing.assert_allclose(gyro, 0, atol=1e-12)

    def test_translation_and_tilt_are_in_device_coordinates(self):
        times = np.arange(0.1, 1.0, 0.02)
        tilt = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])

        def translation(t):
            return np.column_stack((2 * t, -3 * t, t)), np.tile(tilt, (len(t), 1, 1))

        acceleration, gyro = watch.sensors_from_motion(times, translation)
        np.testing.assert_allclose(acceleration, np.tile([0, 9.80665, 0], (len(times), 1)), atol=2e-9)
        np.testing.assert_allclose(gyro, 0, atol=1e-12)

    def test_positive_world_rotation_is_positive_device_gyro(self):
        times = np.arange(0.0, 8.0, 0.02)  # cross the quaternion sign boundary
        tilt = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])

        def rotation(t):
            r = np.zeros((len(t), 3, 3))
            r[:, 0, 0] = r[:, 1, 1] = np.cos(1.25 * t)
            r[:, 1, 0] = np.sin(1.25 * t)
            r[:, 0, 1] = -np.sin(1.25 * t)
            r[:, 2, 2] = 1
            return np.zeros((len(t), 3)), r @ tilt

        _, gyro = watch.sensors_from_motion(times, rotation)
        np.testing.assert_allclose(gyro, np.tile([0, 1.25, 0], (len(times), 1)), atol=1e-10)

    def test_skin_translation_is_not_the_wrist_origin(self):
        palette = np.array([[[0, -1, 0, 3], [1, 0, 0, 4], [0, 0, 1, 5], [0, 0, 0, 1]]], float)
        bind = np.eye(4)
        bind[:3, 3] = [1, 2, 3]
        mount = np.eye(4)
        mount[2, 3] = 0.025
        pose = watch.recover_watch(palette, bind, mount)
        np.testing.assert_allclose(pose[0, :3, 3], [1, 5, 8.025])
        np.testing.assert_allclose(pose[0, :3, :3], [[0, -1, 0], [1, 0, 0], [0, 0, 1]])

    def test_reflected_skin_is_rejected_instead_of_repaired(self):
        reflected = np.eye(4)[None]
        reflected[0, 0, 0] = -1
        with self.assertRaisesRegex(ValueError, "reflected"):
            watch.recover_watch(reflected, np.eye(4), np.eye(4))

    def test_left_watch_is_dorsal_and_keeps_a_right_handed_sensor_frame(self):
        # Left hand viewed from its back: fingers down, thumb to screen left.
        # +Z is the known dorsal side, not a normal derived by the test.
        mount = watch.left_dorsal_watch(
            np.array([0., 0., 0.]),
            np.array([0., -.08, 0.]),
            np.array([-.04, -.03, 0.]))
        np.testing.assert_allclose(mount[:3, :3], np.eye(3), atol=1e-12)
        np.testing.assert_allclose(mount[:3, 3], [0., .012, .028], atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(mount[:3, :3]), 1.)
        # The screen is outside; its underside faces back toward the skin.
        self.assertGreater((mount @ [0., 0., .005, 1.])[2], mount[2, 3])
        self.assertLess((mount @ [0., 0., -.0045, 1.])[2], mount[2, 3])

    def test_schedule_uses_viewer_range_duration_and_easing(self):
        meta = {"playback_range": [0.0, 0.93], "playback_ms": 2600}
        np.testing.assert_allclose(watch.playback_phase(np.array([0, .65, 1.3, 1.95, 2.6]), meta),
                                   [0, .465, .93, .465, 0], atol=1e-12)
        np.testing.assert_allclose(watch.playback_phase(np.array([0, .325]), {}), [0, .125])

    def test_kcs_v2_is_big_endian_and_does_not_invent_device_fields(self):
        data = watch.encode_capture(np.array([1_000_000_000, 1_020_000_000]),
                                    np.array([[0, 0, 9.80665], [0, 0, 9.80665]]), np.zeros((2, 3)))
        self.assertEqual(len(data), 20 + 76 * 2)
        self.assertEqual(struct.unpack(">4siid", data[:20]), (b"KCS1", 2, 2, 50.0))
        record = struct.unpack(">q6fiiqqqiq", data[20:96])
        self.assertEqual(record[0], 1_000_000_000)
        self.assertAlmostEqual(record[3], 9.80665, places=5)
        self.assertEqual(record[7:], (-1, -1, 1_000_000_000, 1_000_000_000, -1, -1, -1))

    def test_pose_interpolation_keeps_linear_motion_and_source_knots(self):
        phases = np.array([0.0, 0.5, 1.0])
        poses = np.tile(np.eye(4), (3, 1, 1))
        poses[:, 0, 3] = [0, 1, 2]
        curve = watch.PoseCurve(phases, poses)
        points, rotations = curve(np.array([0, .125, .5, .875, 1.0]))
        np.testing.assert_allclose(points[:, 0], [0, .25, 1, 1.75, 2])
        np.testing.assert_allclose(rotations, np.tile(np.eye(3), (5, 1, 1)))

    def test_linear_viewer_knots_are_step_sensitive_while_c2_variation_is_stable(self):
        phases = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        positions = np.array([0.0, 0.02, 0.08, 0.09, 0.12])
        poses = np.tile(np.eye(4), (len(phases), 1, 1))
        poses[:, 0, 3] = positions
        identity = np.tile(np.eye(3), (1, 1, 1))

        def viewer_linear(t):
            return np.interp(t, phases, positions)[:, None] * np.array([[1.0, 0.0, 0.0]]), np.repeat(identity, len(t), axis=0)

        knot = np.array([0.5])
        linear_h, _ = watch.sensors_from_motion(knot, viewer_linear, step_s=.001)
        linear_h2, _ = watch.sensors_from_motion(knot, viewer_linear, step_s=.0005)
        self.assertGreater(np.linalg.norm(linear_h2 - linear_h), 50.0)

        c2 = watch.PoseCurve(phases, poses)
        c2_h, _ = watch.sensors_from_motion(knot, c2, step_s=.001)
        c2_h2, _ = watch.sensors_from_motion(knot, c2, step_s=.0005)
        self.assertLess(np.linalg.norm(c2_h2 - c2_h), .15)

    def test_sensor_lane_provenance_keeps_viewer_linear_and_c2_variation_distinct(self):
        provenance = watch.motion_provenance()
        self.assertEqual(provenance["viewer_surface"]["interpolation"], "piecewise_linear_vertex_positions")
        self.assertEqual(provenance["sensor_motion"]["interpolation"], "natural_c2_pose_spline")
        self.assertEqual(provenance["sensor_motion"]["classification"], "diagnostic_variation")
        self.assertFalse(provenance["sensor_motion"]["physical_ground_truth"])
        self.assertTrue(provenance["same_published_frame_knots"])
        self.assertNotEqual(provenance["viewer_surface"]["lane_id"], provenance["sensor_motion"]["lane_id"])

    def test_pullover_is_available_only_as_the_named_c2_variation_case(self):
        self.assertNotIn("lying_dumbbell_pullover", watch.PILOT)
        self.assertEqual(watch.C2_VARIATIONS["lying_dumbbell_pullover"],
                         ("dumbbell_pullover", "덤벨 풀오버", 10))

    def test_pullover_watch_pose_comes_from_the_published_wrist_surface(self):
        clip = watch.load_clip("lying_dumbbell_pullover")
        qa = clip["qa"]
        mount = clip["mount"]

        self.assertEqual(mount["carrier"], "published final wrist surface")
        self.assertEqual(mount["dynamic_orientation_source"], "published point-cache vertices only")
        self.assertEqual(mount["caseback_contact_source"], "published point-cache triangle ray hit")
        self.assertTrue(qa["palette_only_carrier_rejected"])
        self.assertGreater(qa["palette_only_ring_max_error_mm"], 10.0)
        self.assertLess(qa["surface_rigid_fit_max_error_mm"], 1.0)
        self.assertGreater(qa["surface_orientation_span_deg"], 70.0)
        self.assertGreater(qa["screen_outward_min_dot"], 0.99)
        self.assertLess(qa["caseback_surface_max_distance_mm"], 0.001)
        self.assertLess(qa["adjacent_orientation_max_step_deg"], 8.0)
        np.testing.assert_allclose(np.linalg.det(clip["poses"][:, :3, :3]), 1.0, atol=2e-5)

    def test_constant_acceleration_is_added_to_gravity(self):
        times = np.arange(.1, 1, .02)

        def accelerated(t):
            return np.column_stack((1.5 * t**2, -t**2, .5 * t**2)), np.tile(np.eye(3), (len(t), 1, 1))

        acceleration, gyro = watch.sensors_from_motion(times, accelerated)
        np.testing.assert_allclose(acceleration, np.tile([3, -2, 10.80665], (len(times), 1)), atol=2e-9)
        np.testing.assert_allclose(gyro, 0, atol=1e-12)

    def test_quaternion_spline_crosses_180_degrees_without_a_gyro_spike(self):
        angles = np.deg2rad([150, 170, 190, 210])
        poses = np.tile(np.eye(4), (4, 1, 1))
        poses[:, 0, 0] = poses[:, 1, 1] = np.cos(angles)
        poses[:, 1, 0] = np.sin(angles)
        poses[:, 0, 1] = -np.sin(angles)
        curve = watch.PoseCurve(np.arange(4), poses)
        _, gyro = watch.sensors_from_motion(np.arange(.2, 2.8, .02), curve)
        np.testing.assert_allclose(gyro[:, :2], 0, atol=1e-10)
        np.testing.assert_allclose(gyro[:, 2], np.deg2rad(20), atol=.01)
        _, rotations = curve(np.arange(4))
        np.testing.assert_allclose(rotations, poses[:, :3, :3], atol=1e-12)

    def test_modified_capture_is_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder)
            capture = watch.encode_capture(np.array([1_000_000_000, 1_020_000_000]),
                                            np.tile([0, 0, 9.80665], (2, 1)), np.zeros((2, 3)))
            truth = watch.json_bytes({"source": "synthetic", "expected_reps": 1,
                "repetitions": [{"start_ns": 1_000_000_000, "turnaround_ns": 1_010_000_000, "end_ns": 1_020_000_000}]})
            (case / "capture.kcs").write_bytes(capture)
            (case / "truth.json").write_bytes(truth)
            (case / "manifest.json").write_bytes(watch.json_bytes({"source": "synthetic",
                "motion_provenance": watch.motion_provenance(), "sample_count": 2,
                "files": {"capture.kcs": hashlib.sha256(capture).hexdigest(), "truth.json": hashlib.sha256(truth).hexdigest()}}))
            watch.verify_case(case)
            damaged = bytearray(capture)
            damaged[30] ^= 1
            (case / "capture.kcs").write_bytes(damaged)
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                watch.verify_case(case)

    def test_missing_motion_lane_provenance_is_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder)
            capture = watch.encode_capture(np.array([1_000_000_000, 1_020_000_000]),
                                           np.tile([0, 0, 9.80665], (2, 1)), np.zeros((2, 3)))
            truth = watch.json_bytes({"source": "synthetic", "expected_reps": 1,
                "repetitions": [{"start_ns": 1_000_000_000, "turnaround_ns": 1_010_000_000, "end_ns": 1_020_000_000}]})
            (case / "capture.kcs").write_bytes(capture)
            (case / "truth.json").write_bytes(truth)
            (case / "manifest.json").write_bytes(watch.json_bytes({"source": "synthetic", "sample_count": 2,
                "files": {"capture.kcs": hashlib.sha256(capture).hexdigest(), "truth.json": hashlib.sha256(truth).hexdigest()}}))
            with self.assertRaisesRegex(ValueError, "motion provenance"):
                watch.verify_case(case)


if __name__ == "__main__":
    unittest.main()
