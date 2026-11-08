"""Assign a default 3D camera (yaw, elevation) to every exercise and write tools/viewer3d/camera_views.json.

yaw  = degrees off the front of the person (0 front, 90 pure side, >90 from behind).
       For a lying person it is degrees off the SIDE, toward the head (90 = pure side view).
elev = camera height above the torso line, in degrees (positive looks down).
The viewer picks the left or right side itself so the machine does not hide the person.
First matching rule wins; an exercise that matches nothing keeps the viewer default (40 / 25).
Rules follow docs/handoff/2026-11-09-camera-and-preview-plan.md.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RULES = [
    # --- vertical pulls and hangs: from behind (150), the back is what the lift trains and rack posts stay out of the way
    (r'^(pull_up|chin_up|weighted_pull_up|neutral_grip_pull_up|assisted_pull_up|assisted_chin_up)$', 150, 5),
    (r'lat_pull_?down|pulldown', 30, 5),
    (r'^straight_arm_pulldown$|^cable_pullover$|^machine_pullover$', 90, 0),
    (r'^face_pull$', 35, 0),
    # --- rows and hinges: side
    (r'high_row', 30, 0),
    (r'row|^hyperextension$|^good_morning$|^rack_pull$', 90, 0),
    (r'deadlift', 90, 0),
    # --- curls
    (r'^(incline_curl|incline_hammer_curl|single_arm_incline_bench_curl|preacher_curl|preacher_curl_dumbbell|single_arm_dumbbell_preacher_curl|spider_curl)$', 90, 5),
    (r'^concentration_curl$', 45, 10),
    (r'drag_curl|bayesian', 90, 0),
    (r'curl$', 28, 0),
    # --- triceps
    (r'skullcrusher|jm_press|tate_press|lying_extension|dumbbell_triceps_extension', 80, 8),
    (r'close_grip_bench', 35, 12),
    (r'machine_dip|assisted_dip|^chest_dip$|^weighted_dip$', 40, 0),
    (r'pushdown|extension|kickback', 90, 0),
    # --- chest
    (r'pullover', 85, 5),
    (r'push_up', 90, 8),
    (r'cable_fly|crossover', 12, 5),
    (r'machine_fly|pec_deck', 30, 5),
    (r'incline_dumbbell_fly', 40, 12),
    (r'landmine', 60, 5),
    (r'machine_chest_press|chest_press|machine_bench|flat_machine|incline_machine|decline_machine', 65, 5),
    (r'bench_press|^flat_bench$|^incline_bench$|^dumbbell_bench$|floor_press|hex_press|guillotine', 35, 12),
    # --- shoulders
    (r'lateral_raise|cable_lateral', 35, 5),
    (r'front_raise', 90, 0),
    (r'rear_delt|reverse_fly|crossover_reverse', 120, 12),
    (r'shrug', 12, 0),
    (r'upright_row', 15, 0),
    (r'external_rotation', 35, 5),
    (r'cuban_press', 0, 0),
    (r'push_press|bradford|overhead_press|landmine_shoulder', 50, 5),
    (r'shoulder_press|arnold|viking', 35, 5),
    # --- legs
    (r'lateral_lunge|cossack', 0, 5),
    (r'curtsy', 40, 5),
    (r'goblet', 70, 5),
    (r'squat|lunge|step_up|sissy', 90, 5),
    (r'leg_press|leg_curl|leg_extension|calf|nordic|belt_squat', 90, 0),
    (r'hip_adduction|hip_abduction', 15, 5),
    (r'hip_thrust|glute_bridge|glute_kickback|donkey', 90, 0),
    # --- core
    (r'russian_twist', 30, 28),
    (r'torso_rotation', 30, 35),
    (r'woodchopper', 45, 10),
    (r'pallof', 35, 5),
    (r'side_plank', 20, 10),
    (r'windshield', 0, 5),
    (r'dead_bug|bicycle', 60, 20),
    (r'plank|hollow|ab_wheel|crunch|sit_up|leg_raise|knee_raise', 90, 3),
    # --- forearm and full body
    (r'wrist_curl', 70, 20),
    (r'plate_pinch|farmers', 35, 5),
    (r'turkish', 45, 15),
    (r'clean|snatch|thruster|kettlebell_swing', 90, 0),
]


def main():
    models = json.loads((REPO / 'phone/src/main/assets/viewer3d/exercise_models.json').read_text())
    views, missing = {}, []
    for key in sorted(models):
        for pattern, yaw, elev in RULES:
            if re.search(pattern, key):
                views[key] = {'yaw': yaw, 'elev': elev}
                break
        else:
            missing.append(key)
    out = REPO / 'tools/viewer3d/camera_views.json'
    out.write_text(json.dumps(views, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(views)} assigned, {len(missing)} left on the viewer default: {missing}')


if __name__ == '__main__':
    sys.exit(main())
