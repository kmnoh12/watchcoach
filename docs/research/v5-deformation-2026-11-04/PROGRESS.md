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

## Goal continuation: front-face inversion constraint (progress, still incomplete)

Previous goal turn classified as PROGRESS: identified the correct FRONT target, saved opt-in loader integration, and generated evidence that changed the next action. This turn found actual front fold orientation reversals, not merely enlarged radii. On original face164 `[118,138,128]`, the bone-relative signed area ratio goes negative by bench frame24; face184 flips soon afterward; face196 nearly collapses by frame32. Their expected normals are computed from the face's original skin influences and current rigid palette, NOT a fixed world axis.

New `front_orientation.py` changes ONLY the 12 mirrored front vertices (117,118,128,138,145,151 and mirrors). It imposes positive projected area on the six critical faces, preserves incident face orientation, and minimizes displacement from the preserved guide. No rest-edge spring refit: that earlier energy caused abrupt ~12mm correction at activation and was removed. Safe poses whose critical areas are already >=.2 are exact no-ops. `test_front_orientation.py`: THREE focused tests passed, including finite-difference checks of the actual analytic area Jacobian and no-op / outside-domain invariants.

Actual contact points are queried from all faces incident to moving vertices, not only the six critical faces; limiting query coverage missed newly introduced neighboring collisions. However forcing every unrelated inherited collision apart made the problem infeasible and dragged the skin to its bounds. Current solver blocks NEW incident-face contacts and addresses inherited contacts involving an already inverted critical front face; it explicitly preserves unrelated old contacts. This is an incremental correction, NOT a declaration that old errors may be ignored in the final goal. The exact independent pair-set audit still compares against the entire guide.

`triangle_contact_samples.py` / two focused tests investigate contact along the whole crossing interval. The interval-sampling variant regressed in this candidate and is NOT the default. Current bake uses the original single-point, persistent contact band (`interval_contact=false`). The default local candidate was baked by `bake_front_orientation_bench.py`, tracked exec 4592, COMPLETED. All 33 per-pose optimizations succeeded. Frames0..20 exact no-ops; frame21 max correction .72mm, growing to29.28mm at frame32. All outside-front points, including fingers and elbow, stay exact; source bone lengths, weights and original rest are unchanged.

Current persisted output `front_orientation_bench/flat_bench_press.positions.bin` SHA256 `1f5fd22ef0ad9595d9924373522a7f6ad4f9c38c452b8d243227f687d0cf1473`. BOTH `delta_audit.json` and `surface_audit.json` include and MATCH this hash; do not interpret stale reports after overwriting a candidate. Across 33 stored poses +32 true float32 interpolation midpoints (65 samples), exact pair-set delta audit found ZERO new face-pair intersections, up to17 old pairs removed at one sample. Surface audit vs ORIGINAL pilot (different baseline) reports max5 new pairs, max5 arm pairs; these are unresolved, not a pass of the full deformation goal. The full arm/hand baseline still has old issues.

`front_orientation_bench/front_axilla/` renders the current corrected front/inner/side view. Qualitative result: large backfold at edge `[118,138]` improves from178.9deg to20.8deg (rest10.9). But the INNER connection still has an overly sharp fold: edge `[128,151]` rest11.1deg -> original153.9 -> corrected119.9; `[121,151]` rest54.4 ->original166 ->corrected125.0. Therefore NOT yet a natural finished front biceps/axilla shape, and NOT installed. Numeric no-new-crossing PASS alone is insufficient. Keep the user's current browser on the preserved guide.

Next available focused action: address the remaining sharp adjacent-face hinge at the front fold while preserving the new orientation/contact gates. Do NOT return to rear-shoulder radial shrink or whole-body FEM. Candidate options need evidence: an orientation-cone/adjacent-face bend constraint on this same front patch, or local conforming support points combined with the new fold solver (NOT the rejected unconstrained subdivision). Maintain original rest and exact grip. Full continuous-time collision verification beyond the65 samples remains unproven; do not call65 samples an all-time guarantee. Full five-exercise / extreme-pose /265-clip readiness still incomplete.

Current tracked render/review session is in this chat tool state: `render_guide_suite.py -- --case front_orientation_bench`, log `/tmp/watchgym-front-bench-review.log`. Check it, then preserve the result/source. No running worker should be killed or restarted to add instructions.

## USER ACCEPTANCE OVERRIDE — 2026-11-04 (latest, authoritative)

The user clarified: “면끼리 절대겹치지마라 이런게아님 그냥 시각적으로 뷰어에서 팔이 뒤틀리거나 갑자기 얇아지는거만 없으면된다고 근ㅇㄱ수축이나 뒤집힘등.” The acceptance target is VISUAL stable playback: no sudden twisting, thinning/collapse, inside-out-looking muscles, or exaggerated unnatural bunching. Small visually harmless intersections/natural folding are ALLOWED. Stop treating zero new triangle pairs, positive face-area thresholds, or perfect contact separation as mandatory adoption gates. Numerical audits are diagnostic support, not the user's approval criterion. Earlier rejection of candidates solely for a few new face pairs must be reconsidered visually. Do not spend the next turn on continuous collision certification or pushing all faces apart.

The assistant acknowledged that the earlier overly strict collision gate displaced the user's actual visual goal. Reuse the useful guide and compare simple FRONT-only moderation in actual repeated viewer playback. Pay particular attention to the front upper-biceps/axilla junction, not rear deltoid. Preserve rest, fingers/grip and general stable silhouette; do not impose additional idealized tissue requirements.

Current orientation/contact candidate improved a near180deg backfold but still leaves a sharp INNER ridge, so it must not be preferred merely because its 65-sample exact new-pair gate passes. `guide_front_axilla/` .5 front-only DQ/LBS candidate is a simpler previously rejected trial worth VISUAL comparison now: 12 mirrored front points only, bench max8.49mm change, no original model/weight edit. Its few new triangle pairs are NOT an automatic failure under the user's corrected criterion.

## Latest: USER-directed chestward reduction about 2cm

The user rejected the visible .5 DQ/LBS view and explicitly requested: “돌출을 한 2센치줄이면어떨까 이두볼륨은 살리되 지금처럼 가슴까지 튀어나온 과장만줄이게”. Acceptance is visual stable replay, not zero face overlap.

Mapped the EXACT live user camera to the displayed mesh using own-app CDP debugger camera/point readout. This identified the visible medial/anterior biceps PEAK as original vertex142 and its mirror. The previous six-point crease blend excluded142, explaining the unchanged visible spike. Captures/projections: `guide_front_axilla/browser_review/current_view.json`, `current_bounds.json`, `front_target_labels.png`.

Implemented `front_biceps_visual.py`, `build_front_visual.py`, `test_front_biceps_visual.py`. Move only the medial/chestward protrusion OUTWARD in the upper-arm cross-plane, not radially toward the bone. Original anterior muscle thickness is retained to <0.5mm at the peak, with rest + deeply bent pose exact. Smooth activation depends on forward arm elevation +elbow extension; Gaussian rest-space falloff centers on142/mirror. Max relief20mm, capped to avoid crossing the arm axis. Actual bench peak20.000008mm; maximum adjacent stored-frame correction change3.50mm. Exactly9 points change across bench:118,138,142,174,178,317,321,353,357. Other862 points exact, including rear shoulder and fingers. Squat unchanged; deadlift max20mm in forward extended posture; curl <=0.20mm; pullup <=0.15mm.

Five NEW narrow tests PASSED: original rest/bent exact, actual visible peak20mm, chestward-only direction with anterior thickness/axial length retained, outside/rear exact, no mutation.26 Node loader/race tests PASSED after adding the FIXED `front=moderate` review-directory branch. Do not rerun old checks without a relevant change.

`guide_front_visual/` is now the source for `publish_guide_suite.py --front`. Current URL is still `http://127.0.0.1:8765/?human=v5-guide&front=moderate`; baseline `?human=v5-guide` and default remain unchanged. Local publisher preflights every clip, source phases and topology, then copies only localhost review data +canonical HTML. No Android production installation /full265 adoption.

Current user's camera was preserved: published static JSON first; then own-app CDP debugger invoked the EXISTING strict `fetchGuideHuman` loader and swapped the current review mesh at phase1. DOM marker `data-visual-review-version=front-chestward-20mm` confirmed refresh. The change persists in disk/HTTP, not merely temporary page memory. Actual same-camera screenshots: `guide_front_axilla/browser_review/before_20mm.png` and `after_20mm.png`.

Native CUA wrapper returns `browser.user is unavailable`; the documented DIRECT API works: `reviewBrowser = await agent.browsers.get("2")`, then `reviewBrowser.tabs.*` and returned tab Playwright/CDP. Current review tab was created with that direct API. Preserve the user's camera; no new Chrome profile/proxy needed.

Local commit224992c5 saves the2cm implementation. A Python stdin encoding error prevented the earlier long checkpoint append; this shell-written note corrects the record. The actual corrective build, five tests, local publish and browser update succeeded before that unrelated documentation error.

Goal remains ACTIVE. The2cm change is a current visual comparison, not proof every pose /all265 exercises are finished. Continue actual replay and major-exercise visuals; do NOT return to rear-shoulder shrink, zero-intersection gating, or broad FEM. The older orientation/contact candidate remains a diagnostic with a visibly sharp INNER ridge, and must not replace the user's desired simple visual correction merely for a better collision count.
