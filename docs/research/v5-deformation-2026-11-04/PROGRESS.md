# V5 deformation continuation — active, not complete

## Current user target and corrections

The user asked to resume Codex2's interrupted goal, keep exercising difficult poses until the usage limit, and prepare reliable integration into the existing approximately 250-exercise viewer. Latest clarification: the unwanted bump is at the **FRONT upper-biceps / axilla junction**, NOT the outside of the arm or rear deltoid. Earlier rear-shoulder radial measurements (notably vertex 135, 28mm radial excess) do not answer that target. Do not present those as proof about the user's front-fold complaint.

The user identified `guide_review/elastic_32_oblique.png` as a useful existing shape, and rejected `refined_standard_case/elastic_32_oblique.png` as visibly crumpled. Preserve the useful guide; do not restart whole-body modeling or adopt a physical candidate based only on intersection counts. Neither image approves the full motion or every angle. The later complaint specifically rejects the front-fold bulge when the arms extend.

## Recovered Codex2 state

Local session `~/.codex2/sessions/2026/11/04/rollout-2026-11-04T01-22-14-01a1a237-e646-73a0-b7d2-2e03cab49e71.jsonl` ended with `usage_limit_exceeded`. There was no surviving pose-solver process. Its last cold joint-local FEM run subsequently FAILED at continuation 0.9038995; `joint_local_case/` was empty. Do not adopt or resume it as a completed seed. The prior warm/full-volume results crumpled visibly.

## Completed useful work in this continuation

- `build_guide_suite.py`: the SAME preserved guide applied to the five already saved original-source pilots (squat, bench, deadlift, curl, assisted pullup), without a new FEM solve or edits to original model, original weights or source clips.
- 237 stored poses, 469 endpoint/midpoint playback samples. Hands/grip coordinates remain float32-exact. Rest displacement was numerical roundoff (~7e-13 mm). Bench matches the preserved guide within 0.001mm.
- `guide_suite/` contains manifests, original 871-vertex / 1738-triangle base, exact point caches and original phase arrays. No clip is marked approved. Existing collisions remain; maximum new pairs vs original pilot: squat 19, bench 20, deadlift 17, curl 106, pullup 12. These counts do not certify anatomy or rank visual severity.
- `render_guide_suite.py` rendered start/middle/end plus worst sample, front/oblique/reverse and wire checks; worst-frame generic mesh QA passed on all five. That mesh QA does NOT establish absence of self-contact or acceptable deformation. The curl and some other poses still fail visually/contact-wise.
- Existing canonical viewer now has an OPT-IN guide lane at `?human=v5-guide`; it reuses the existing full exercise list. Only these five clips use V5; other clips retain the existing model and are labeled as such. Default model selection and Android app assets were not changed.
- Strict point-cache/base/phase/topology validation, explicit review/fallback labels. Slow stale exercise loads are discarded so rapid selection cannot attach an earlier person's pose to the later machine. 25 focused Node tests passed (23 data-loading/roundtrip + 2 selection-race regressions). No full Android build/test suite.
- Local publication: `publish_guide_suite.py` preflights all inputs, copies ONLY `v5-guide/` review files and the canonical viewer HTML to the existing localhost 8765 viewer. No external hosting, push, APK installation or production model replacement. Native IAB visibly loaded bench with `V5 동작 확인 중`, at 100%, and no browser error/warn messages. The user's current camera is manually positioned in that IAB tab; avoid needlessly reloading it.

## FRONT fold diagnosis (latest target)

`render_front_axilla.py` marks the front crease / proximal biceps vertices 117,118,128,138,145,151 (and their geometric mirrors for trials). Their rest Y is negative. Rear vertices 135,147,152 have positive rest Y and were the mistaken earlier focus.

At bench phase 1 / frame32, original face196 `[128,151,121]` has only 9.735% of its resting area; neighboring face177 `[118,142,138]` expands to ~1.529x rest area. The front fold is also involved in actual nonadjacent face crossings. This supports a folded/piled-up connection surface, not a conclusion that the whole biceps was uniformly inflated. Large per-vertex DQ vs LBS differences at this FRONT patch reach ~17mm, but simply switching skinning does not fix the fold.

`guide_suite/front_axilla/` has orange-marked front/inner/side diagnostic renders and a metrics JSON. These are diagnostic, not installed corrections. User-facing reporting should discuss the FRONT upper-biceps/armpit connection, not rear shoulder.

## Rejected experiments in this continuation

- Minimal halfspace surface-separation QP/penalty: failed; new pair count grew dramatically. `guide_local_case/` is rejected and never installed. Do not tune that model repeatedly.
- Source-upperarm-frame alternative: bench/curl not improved; deadlift counts improved but not a universal solution. `guide_source_suite/` is not installed.
- `shoulder_blend.py` rear/proximal mixed shoulder trials at strengths .5/.75, and `build_shoulder_weight_trial.py`: these pursued the WRONG anatomical focus for the latest complaint. They also introduce new face-pair intersections, even where worst-case counts decrease. They were NEVER installed; do not use them as seeds. The original guide stays installed.
- `front_axilla_blend.py`: correct front patch, 6 vertices per side, .5 DQ/LBS blend. Original outside vertices exact, bench changes <=8.49mm; face196 area rises to ~25% but remains collapsed. Actual-set delta audit still finds new pairs (bench max4; deadlift9; curl3; pullup8). Rejected for adoption. No blanket whole-arm shrink.
- Important gate correction: a lower maximum intersection COUNT is not proof of no new errors. `audit_shoulder_delta.py` compares actual pair SETS against the preserved guide at all 469 samples.

## Active next experiment

`refine_front_fold.py` creates **planar, conforming local support points** across the front crease and the two long underarm bridge faces, preserving ALL original 871 rest and posed vertices exactly. Output: `guide_front_support/`, 961 vertices /1918 triangles; original weights unchanged; new points have interpolated, normalized <=4 influences. No whole-body remesh, no rest inflation, no source edits. New points sample the same coherent DQ field, rather than a long straight triangle.

Tracked audit shell session 97659 (completed successfully), `/tmp/watchgym-front-support-audit.log`: `audit_guide_suite.py -- --case guide_front_support`. This compares against an exactly bound linear guide on the same refined topology (`*.baseline.bin`), so raw pair counts must NOT be directly compared to the old 1738-triangle counts. `binding.json` stores parent faces; a grouped parent-face comparison is still needed if the candidate looks promising. Rest and posed mesh QA plus visual review remain REQUIRED. Do not install this candidate just because it adds loops or keeps original vertices exact.

## Reproduction tools

Blender: `/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python <script> -- <options>`.
SciPy environment: project `work/deformation-venv/bin/python` (system python lacks scipy).
Root directory for these scripts: `design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild/`.
Narrow viewer tests: `node --test design/exercise-figure/viewer/tests/test_guide_loader.mjs design/exercise-figure/viewer/tests/test_selection_race.mjs` (25 passed; do not rerun without relevant changes).
Narrow outward-only shoulder test: 7 passed, but it belongs to the wrong/rejected rear-shoulder investigation, not a certification of the front fold.

The main goal remains ACTIVE and incomplete. No push, release, installation, full-catalog retargeting or production asset replacement is authorized by these diagnostic checks. Latest user expects the front axillary fold issue to be understood and addressed precisely.

### Front support result and next causal test

Support refinement completed (469 samples + multi-angle renders + generic mesh QA). The original points were exact, but interpolated DQ support points still fold and introduce intersections; the rendered front-crease geometry is not accepted. No installation. Do not repeat uniform subdivision as a fix.

A concrete motion observation: in bench samples 0/16/32 the clavicle relative to spine stays at ~0.000008 degrees, while upperarm relative clavicle goes ~23.84 /25.46 /78.54 degrees. Thus the fold is pulled across a largely fixed support; this is an animation observation, not a medical/anatomical diagnosis. A small coherent clavicle protraction test, maintaining fixed arm lengths, original rest and exact grip, is the next planned isolated causal experiment. No such candidate has passed or been installed.

### Current exact checkpoint — front-fold causal work

Latest user correction was emphatic: “바깥문제가아니고 이두상단 즉 이두랑 겨드랑이사이가 부풀었다고 후면어깨말고.” The assistant acknowledged the anatomical misidentification. Do NOT continue tuning rear deltoid or cite the rear 28mm radius as this problem.

The orange front diagnosis renders are at `guide_suite/front_axilla/guide_front.png`, `guide_inner.png`, `guide_side.png`; the six labeled left-front vertices are 117,118,128,138,145,151. Face196 `[128,151,121]` collapses to 9.735% rest area at full extension, while face177 expands ~1.529x. They also intersect other nonadjacent faces. This is the precise FRONT-fold target.

`guide_front_axilla/` (.5 DQ/LBS on exactly these 12 mirrored points) increases face196 to ~25% but introduces new face pairs; NOT accepted. `guide_front_support/` (961 verts /1918 tris, original 871 points exact) was rendered and mesh-QA passed, but still folds visibly and adds surface contacts; NOT accepted. Do not mistake generic QA PASS for deformation approval.

`clavicle_protraction.py` is a NEW bounded geometric trial, default disabled in `supported_skin.deform`. The first rest test correctly failed because the original rest upper arm already has a small forward component; fixed activation by subtracting that REST component, rather than relaxing the rest threshold. Six NEW narrow tests passed: rest exactness, length preservation, rigid covariance, rotated-rest invariance, mirror symmetry, backward/zero disabled input. Do not rerun old unrelated tests. `build_guide_suite.py -- --protraction-deg 10` generated `guide_protraction/`: all five grips exact, rest error ~7e-13mm, bone lengths fixed. Bench top actually activates ~7.52deg and shifts shoulder ~17.18mm. Face196 improves from .097 to .229 rest area; face177 ~1.529 to1.499. This is PARTIAL causal evidence, not a natural-shoulder solution. Exact pair-set audit still fails (bench max6 new pairs, deadlift7; other three none). No installation. No further blind parameter sweep is justified.

All focused posture candidates remain unapproved. The installed `?human=v5-guide` lane STILL shows the preserved guide only; user camera was not reset. Source/root HTML was updated with the already-tested selection-race guard, but no experimental correction replaced the guide. Android assets and external hosting unchanged.

Local commit `8d5f148f` saves the opt-in review integration and 25 passing focused loader/race tests. Later protraction/diagnostic source edits may be pending in git; do not discard them or overwrite the prior author's unrelated result-reference directory. Original broad goal remains active, but the front-fold correction is not solved.
