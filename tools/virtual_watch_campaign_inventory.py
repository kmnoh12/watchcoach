#!/usr/bin/env python3
"""Join real Kotlin routing with app-to-viewer identity; never infer accuracy."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORK = REPO / "work/virtual-watch/campaign"
CATALOG = REPO / "phone/src/main/kotlin/dev/kyungmin/watchcoach/phone/WorkoutData.kt"
APP = REPO / "phone/src/main/assets/viewer3d"
DESIGN = REPO / "design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def routing_hash(core):
    paths = sorted(Path(core).rglob("*.kt"))
    if not paths:
        raise ValueError("No production Kotlin sources")
    index = "".join(p.relative_to(core).as_posix() + "\t" + sha(p) + "\n" for p in paths)
    return hashlib.sha256(index.encode()).hexdigest()


def read_profiles(path, catalog=CATALOG, core=REPO / "core/src/main"):
    lines = Path(path).read_text().splitlines()
    if not lines or lines[0] != "#catalog_sha256\t" + sha(catalog):
        raise ValueError("Kotlin export does not match current phone catalog; export again")
    if len(lines) < 2 or lines[1] != "#engine_sha256\t" + routing_hash(core):
        raise ValueError("Kotlin export does not match current measurement code; export again")
    rows = list(csv.DictReader(lines[2:], delimiter="\t"))
    ids = [r["exercise_id"] for r in rows]
    if not rows or len(set(ids)) != len(ids):
        raise ValueError("Empty or duplicate catalog IDs")
    return rows


def queue_role(row, issues):
    id_ = row["exercise_id"]
    reported = [i for i in issues["issues"] if id_ in i["reported_ids"]]
    related = [i for i in issues["issues"] if id_ in i["related_ids"]]
    role = ("reported_failure" if reported else "regression_control"
            if id_ in issues["regression_controls"] else "related_review" if related else "catalog_sweep")
    return {"role": role, "priority": min([i["priority"] for i in reported + related] or [3]),
            "issue_ids": [i["id"] for i in reported + related]}


def provenance(source_hash, recorded_source_hash, packed_hash, recorded_packed_hash):
    if not all((source_hash, recorded_source_hash, packed_hash, recorded_packed_hash)):
        return "missing_evidence"
    if source_hash != recorded_source_hash:
        return "source_mismatch"
    if packed_hash != recorded_packed_hash:
        return "packed_hash_mismatch"
    return "matches_recorded_source"


def build_inventory(profiles, viewer_root, app=APP, design=DESIGN):
    viewer_root, app, design = map(Path, (viewer_root, app, design))
    issues_path = Path(__file__).with_name("virtual_watch_campaign_issues.json")
    issues = json.loads(issues_path.read_text())
    ids = {r["exercise_id"] for r in profiles}
    assigned = set(issues["regression_controls"])
    assigned.update(x for issue in issues["issues"] for k in ("reported_ids", "related_ids") for x in issue[k])
    if assigned - ids:
        raise ValueError("Issue aliases not in current catalog: " + str(sorted(assigned - ids)))
    mapping_path = app / "exercise_models.json"
    report_path = app / "v5_bundle_report.json"
    pc_manifest = viewer_root / "manifest.json"
    app_manifest = app / "human_v5/manifest.json"
    mapping = json.loads(mapping_path.read_text())
    pc_clips = {r["id"]: r for r in json.loads(pc_manifest.read_text())["clips"]}
    app_clips = {r["id"]: r for r in json.loads(app_manifest.read_text())["clips"]}
    bundle = {r["id"]: r for r in json.loads(report_path.read_text())["rows"]}
    hash_cache = {}

    def file_hash(p):
        if p not in hash_cache:
            hash_cache[p] = sha(p) if p.is_file() else None
        return hash_cache[p]

    models = {}
    rows = []
    for profile in profiles:
        id_ = profile["exercise_id"]
        model_ids = mapping.get(id_, [])
        if not isinstance(model_ids, list) or any(not isinstance(m, str) or Path(m).name != m for m in model_ids):
            raise ValueError("Invalid app model mapping: " + id_)
        for model_id in model_ids:
            if model_id in models:
                continue
            source = viewer_root / (model_id + ".json")
            packed = app / "human_v5" / (model_id + ".bin")
            skin = design / "catalog_trial" / (model_id + ".skin.bin")
            record = bundle.get(model_id, {})
            pc_meta, app_meta = pc_clips.get(model_id), app_clips.get(model_id)
            timing_keys = ("playback_ms", "playback_range", "playback_mode")
            models[model_id] = {
                "pc_manifest_present": pc_meta is not None, "app_manifest_present": app_meta is not None,
                "published_motion": str(source), "published_motion_sha256": file_hash(source),
                "final_skin": str(skin), "final_skin_sha256": file_hash(skin),
                "packed_motion": str(packed), "packed_motion_sha256": file_hash(packed),
                "bundle_provenance": provenance(file_hash(source), record.get("source_sha256"), file_hash(packed), record.get("packed_sha256")),
                "metadata_timing_matches": pc_meta is not None and app_meta is not None and all(pc_meta.get(k) == app_meta.get(k) for k in timing_keys),
                "recorded_maximum_error_mm": record.get("maximum_error_mm"),
                "app_decode_verified": False, "surface_attachment_verified": False,
                "visual_approval": (pc_meta or {}).get("visual_approved", False),
            }
        rows.append(dict(profile, **queue_role(profile, issues), model_ids=model_ids,
                         current_policy="hold" if profile["kind"] == "HOLD" else "manual_policy_review"
                         if profile["mode"] == "MANUAL_REQUIRED" else "auto_candidate",
                         result="UNTESTED", physical_accuracy="UNVERIFIED"))
    rows.sort(key=lambda r: (r["priority"], r["family"], r["exercise_id"]))
    sources = {str(p): sha(p) for p in (CATALOG, mapping_path, report_path, pc_manifest, app_manifest, issues_path)}
    sources.update({str(p): sha(p) for p in sorted((REPO / "core/src/main").rglob("*.kt"))})
    return {"schema": 1, "evidence": "inventory_only_not_measurement_success", "sources": sources,
            "denominator": len(rows), "current_policy_counts": dict(Counter(r["current_policy"] for r in rows)),
            "family_counts": dict(Counter(r["family"] for r in rows)),
            "model_provenance_counts": dict(Counter(m["bundle_provenance"] for m in models.values())),
            "rows_without_model": [r["exercise_id"] for r in rows if not r["model_ids"]],
            "models_without_final_skin": [id_ for id_, m in models.items() if not m["final_skin_sha256"]],
            "models": models, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=WORK / "resolved-profiles.tsv")
    parser.add_argument("--viewer-root", type=Path)
    parser.add_argument("--output", type=Path, default=WORK / "inventory.json")
    args = parser.parse_args()
    root = args.viewer_root
    if root is None:
        candidates = [Path.home() / "Library/Application Support" / n / "v5-catalog"
                      for n in ("__PROTECTED_WATCHCOACH_VIEWER__", "WatchGymViewer")]
        root = next((p for p in candidates if (p / "manifest.json").is_file()), None)
    if root is None:
        raise FileNotFoundError("No published viewer catalog; supply --viewer-root")
    result = build_inventory(read_profiles(args.profiles), root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("denominator", "current_policy_counts", "family_counts", "model_provenance_counts", "rows_without_model", "models_without_final_skin")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
