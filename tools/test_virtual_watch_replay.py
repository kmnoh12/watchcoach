"""Small replay accounting contracts, without Gradle or published assets."""
import copy
import tempfile
import unittest
from pathlib import Path

import gen_virtual_watch_pilot as watch
import replay_virtual_watch_pilot as replay


class ReplayAccountingTest(unittest.TestCase):
    def setUp(self):
        self.truth = {
            "source": "synthetic", "case_id": "fixture", "exercise_id": "dumbbell_curl",
            "motion_lane": watch.motion_provenance()["sensor_motion"]["lane_id"],
            "expected_reps": 2, "preparation": {"start_ns": 1_000_000_000, "end_ns": 4_000_000_000},
            "ending_static": {"start_ns": 8_000_000_000, "end_ns": 16_000_000_000},
            "repetitions": [
                {"index": 1, "start_ns": 4_000_000_000, "turnaround_ns": 5_000_000_000, "end_ns": 6_000_000_000},
                {"index": 2, "start_ns": 6_000_000_000, "turnaround_ns": 7_000_000_000, "end_ns": 8_000_000_000},
            ],
        }
        self.manifest = {"source": "synthetic", "case_id": "fixture", "exercise_id": "dumbbell_curl",
                         "motion_provenance": watch.motion_provenance(),
                         "start_ns": 1_000_000_000, "end_ns": 16_000_000_000, "sample_count": 751}

    def event(self, index, emitted=None, channel="live", accepted=True):
        result = dict(self.truth["repetitions"][index - 1])
        result.update(emitted_at_ns=emitted or result["end_ns"], channel=channel, accepted=accepted)
        return result

    def test_exact_counts_and_boundaries(self):
        report = replay.compare_events(self.truth, [self.event(1), self.event(2)])
        self.assertEqual(report["accepted_live_count"], 2)
        self.assertTrue(report["one_to_one_coverage"])
        self.assertEqual(report["early_emission_count"], 0)
        self.assertEqual([r["emission_error_ms"] for r in report["matched_repetitions"]], [0, 0])

    def test_equal_total_does_not_hide_duplicate_and_missing_reps(self):
        report = replay.compare_events(self.truth, [self.event(1), self.event(1, emitted=6_020_000_000)])
        self.assertEqual(report["count_difference"], 0)
        self.assertFalse(report["one_to_one_coverage"])
        self.assertEqual(report["missing_repetition_indices"], [2])
        self.assertEqual(len(report["extra_live_event_indices"]), 1)
        failures = replay.exact_cycle_timing_failures(report)
        self.assertTrue(any("one-to-one" in failure for failure in failures))

    def test_offline_flush_and_vertical_rejections_are_not_live_counts(self):
        report = replay.compare_events(self.truth, [self.event(1, emitted=5_800_000_000),
            self.event(2, accepted=False), self.event(2, channel="offline_flush", emitted=16_000_000_000)])
        self.assertEqual(report["accepted_live_count"], 1)
        self.assertEqual(report["rejected_live_count"], 1)
        self.assertEqual(report["offline_flush_count"], 1)
        self.assertEqual(report["early_emission_count"], 1)
        self.assertEqual(report["missing_repetition_indices"], [2])
        failures = replay.exact_cycle_timing_failures(report)
        self.assertTrue(any("before cycle end" in failure for failure in failures))
        self.assertTrue(any("offline flush" in failure for failure in failures))

    def test_exact_cycle_timing_accepts_one_event_at_each_completed_return(self):
        report = replay.compare_events(self.truth, [self.event(1), self.event(2)])
        self.assertEqual(replay.exact_cycle_timing_failures(report), [])

    def test_truth_cannot_be_swapped_between_cases(self):
        replay.validate_truth(self.manifest, self.truth)
        bad = copy.deepcopy(self.truth)
        bad["case_id"] = "a-different-case"
        with self.assertRaisesRegex(ValueError, "identity"):
            replay.validate_truth(self.manifest, bad)

    def test_truth_must_cover_contiguous_independent_cycles(self):
        bad = copy.deepcopy(self.truth)
        bad["repetitions"][1]["start_ns"] += 20_000_000
        with self.assertRaisesRegex(ValueError, "contiguous"):
            replay.validate_truth(self.manifest, bad)

    def test_named_c2_variation_is_accepted_without_becoming_viewer_truth(self):
        manifest = copy.deepcopy(self.manifest)
        truth = copy.deepcopy(self.truth)
        manifest.update(exercise_id="dumbbell_pullover", model_id="lying_dumbbell_pullover")
        truth["exercise_id"] = "dumbbell_pullover"
        replay.validate_truth(manifest, truth)

        truth["motion_lane"] = watch.motion_provenance()["viewer_surface"]["lane_id"]
        with self.assertRaisesRegex(ValueError, "motion lane"):
            replay.validate_truth(manifest, truth)

    def test_engine_fingerprint_includes_uncommitted_file_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "engine.kt"
            source.write_text("old")
            old, _ = replay.fingerprint_sources(root, [source])
            source.write_text("new, not committed")
            new, _ = replay.fingerprint_sources(root, [source])
            self.assertNotEqual(old, new)


if __name__ == "__main__":
    unittest.main()
