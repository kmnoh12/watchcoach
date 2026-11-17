import hashlib
import tempfile
import unittest
from pathlib import Path

from virtual_watch_campaign_inventory import provenance, queue_role, read_profiles, routing_hash


class CampaignInventoryTest(unittest.TestCase):
    def test_bundle_report_is_not_proof_when_source_or_packed_file_changed(self):
        self.assertEqual("matches_recorded_source", provenance("a", "a", "b", "b"))
        self.assertEqual("source_mismatch", provenance("c", "a", "b", "b"))
        self.assertEqual("packed_hash_mismatch", provenance("a", "a", "c", "b"))
        self.assertEqual("missing_evidence", provenance(None, "a", "b", "b"))

    def test_regression_control_is_not_mislabeled_as_user_reported_failure(self):
        issues = {"regression_controls": ["good"], "issues": [
            {"id": "issue", "priority": 1, "reported_ids": ["bad"], "related_ids": ["good"]}]}
        self.assertEqual("regression_control", queue_role({"exercise_id": "good"}, issues)["role"])
        self.assertEqual("reported_failure", queue_role({"exercise_id": "bad"}, issues)["role"])

    def test_stale_catalog_and_duplicate_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            catalog = root / "catalog.kt"
            catalog.write_text("catalog")
            core = root / "core"
            core.mkdir()
            detector = core / "Detector.kt"
            detector.write_text("detector")
            header = ("#catalog_sha256\t" + hashlib.sha256(catalog.read_bytes()).hexdigest()
                      + "\n#engine_sha256\t" + routing_hash(core) + "\nexercise_id\n")
            profiles = root / "profiles.tsv"
            profiles.write_text(header + "one\n")
            self.assertEqual("one", read_profiles(profiles, catalog, core)[0]["exercise_id"])
            profiles.write_text(header + "one\none\n")
            with self.assertRaises(ValueError):
                read_profiles(profiles, catalog, core)
            profiles.write_text(header + "one\n")
            detector.write_text("changed detector")
            with self.assertRaises(ValueError):
                read_profiles(profiles, catalog, core)
            detector.write_text("detector")
            catalog.write_text("changed")
            with self.assertRaises(ValueError):
                read_profiles(profiles, catalog, core)


if __name__ == "__main__":
    unittest.main()
