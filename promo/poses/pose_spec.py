"""Pose library source. Each pose is written as *directions* in the character's frame, then baked to per-bone local
transforms (pose_library.json + poses.blend actions marked as Pose assets).

Character frame: x = character's LEFT, f = FORWARD (towards Cam_Front), z = UP.
  root   : {"pitch": bend forward +, "side": lean to own left +, "twist": turn to own left +, "lift": metres}
  rot    : {bone: {"pitch"/"side"/"twist": deg}}  world-axis turn about the bone's head (spine, neck, head, clavicle, hand, foot)
  aim    : {bone: [x, f, z]}                         point the bone along this direction (arms, legs)
  sym    : same as aim but without _l/_r: written for the LEFT side, mirrored to the right
  fingers: {"l"/"r": "fist" | "relax" | "open" | "point" | "grip"}
  feet   : "flat" (default, feet stay level) | "follow" (feet keep their angle to the calf: kneeling, lying)
  ground : True (default) lowest vertex goes to the floor; False keeps the root height (+lift)
  base   : another pose to start from (its spec is merged first)
  mirror : name of a pose to mirror left<->right (walk_b, run_b ...)
"""

P = {}

P["stand"] = {"desc": "서있기 (기본)", "sym": {"upperarm": [0.18, 0.02, -1], "lowerarm": [0.10, 0.12, -1], "thigh": [0.07, 0, -1], "calf": [0.04, 0, -1]},
              "fingers": {"l": "relax", "r": "relax"}}

P["hands_on_hips"] = {"desc": "허리에 손 (으쓱)", "root": {"pitch": -4}, "rot": {"head": {"pitch": -8}},
                      "sym": {"upperarm": [0.75, -0.25, -0.62], "lowerarm": [-0.72, 0.18, -0.62], "thigh": [0.13, 0, -1], "calf": [0.06, 0, -1]},
                      "fingers": {"l": "fist", "r": "fist"}}

P["triumph"] = {"desc": "의기양양 (더블 바이셉스)", "root": {"pitch": -6},
                "rot": {"spine_03": {"pitch": -6}, "head": {"pitch": -14}},
                "sym": {"upperarm": [1, 0.05, 0.12], "lowerarm": [0.18, 0.05, 1], "thigh": [0.2, 0, -1], "calf": [0.1, 0, -1]},
                "fingers": {"l": "fist", "r": "fist"}}

P["surprise"] = {"desc": "놀람 (손 번쩍, 한쪽 다리 들림)", "root": {"pitch": -10},
                 "rot": {"spine_03": {"pitch": -6}, "head": {"pitch": -16}},
                 "sym": {"upperarm": [0.75, 0.15, 0.55], "lowerarm": [0.35, 0.25, 1]},
                 "aim": {"thigh_l": [0.18, 0.55, -1], "calf_l": [0.1, -0.35, -1], "thigh_r": [-0.12, -0.05, -1], "calf_r": [-0.05, 0, -1]},
                 "fingers": {"l": "open", "r": "open"}}

P["despair_kneel"] = {"desc": "절망 (무릎 꿇고 고개 푹)", "feet": "follow",
                      "rot": {"spine_01": {"pitch": 18}, "spine_02": {"pitch": 14}, "spine_03": {"pitch": 10}, "neck_01": {"pitch": 18}, "head": {"pitch": 22}},
                      "sym": {"upperarm": [0.12, 0.25, -1], "lowerarm": [0.06, 0.3, -1], "thigh": [0.13, 0.05, -1], "calf": [0.04, -1, -0.08]},
                      "rot_after": {"foot_l": {"pitch": 75}, "foot_r": {"pitch": 75}},
                      "fingers": {"l": "relax", "r": "relax"}}

P["despair_orz"] = {"desc": "절망 orz (엎드려 손 짚기)", "feet": "follow", "root": {"pitch": 72},
                    "rot": {"neck_01": {"pitch": 15}, "head": {"pitch": 25}},
                    "sym": {"upperarm": [0.16, 0.08, -1], "lowerarm": [0.06, 0.04, -1], "thigh": [0.12, 0.0, -1], "calf": [0.04, -1, -0.1]},
                    "rot_after": {"hand_l": {"pitch": -60}, "hand_r": {"pitch": -60}, "foot_l": {"pitch": 75}, "foot_r": {"pitch": 75}},
                    "fingers": {"l": "open", "r": "open"}}

P["facepalm"] = {"desc": "절망 (얼굴 감싸기)", "rot": {"spine_02": {"pitch": 8}, "head": {"pitch": 16}},
                 "aim": {"upperarm_r": [-0.12, 0.85, -0.5], "lowerarm_r": [0.42, -0.25, 0.85], "upperarm_l": [0.2, 0.02, -1], "lowerarm_l": [0.1, 0.1, -1]},
                 "sym": {"thigh": [0.06, 0, -1], "calf": [0.03, 0, -1]},
                 "fingers": {"l": "relax", "r": "open"}}

P["scared"] = {"desc": "겁먹음 (움츠리고 팔로 막기)", "root": {"pitch": -8, "twist": 12},
               "rot": {"spine_02": {"pitch": 14}, "spine_03": {"pitch": 10}, "head": {"pitch": 10, "twist": -25}},
               "sym": {"upperarm": [0.35, 0.65, -0.45], "lowerarm": [-0.35, 0.35, 1], "thigh": [-0.02, 0.45, -1], "calf": [0.16, -0.25, -1]},
               "fingers": {"l": "open", "r": "open"}}

P["point"] = {"desc": "가리킴 (화면 오른쪽 앞)", "root": {"twist": 12},
              "rot": {"head": {"twist": 22, "pitch": -4}},
              "aim": {"upperarm_l": [1, 0.55, 0.18], "lowerarm_l": [1, 0.55, 0.22],
                      "upperarm_r": [-0.75, -0.25, -0.62], "lowerarm_r": [0.72, 0.18, -0.62]},
              "sym": {"thigh": [0.12, 0, -1], "calf": [0.06, 0, -1]},
              "fingers": {"l": "point", "r": "fist"}}

P["fallen"] = {"desc": "쓰러짐 (대자로 뻗음)", "feet": "follow", "root": {"pitch": -90},
               "rot": {"head": {"side": 25}},
               "sym": {"upperarm": [1, -0.45, 0.0], "lowerarm": [1, -0.85, 0.02], "thigh": [0.32, 1, 0.0], "calf": [0.36, 1, 0.0]},
               "fingers": {"l": "relax", "r": "relax"}}

P["walk_a"] = {"desc": "걷기 1 (왼발 앞)", "root": {"twist": -6},
               "aim": {"thigh_l": [0.05, 0.42, -1], "calf_l": [0.03, 0.12, -1], "thigh_r": [-0.05, -0.32, -1], "calf_r": [-0.03, -0.62, -1],
                       "upperarm_r": [-0.16, 0.42, -1], "lowerarm_r": [-0.08, 0.95, -0.55], "upperarm_l": [0.16, -0.38, -1], "lowerarm_l": [0.08, -0.12, -1]},
               "fingers": {"l": "relax", "r": "relax"}}
P["walk_b"] = {"desc": "걷기 2 (오른발 앞)", "mirror": "walk_a"}

P["run_a"] = {"desc": "달리기 1", "root": {"pitch": 14, "twist": -8}, "ground": True,
              "rot": {"head": {"pitch": -10}},
              "aim": {"thigh_l": [0.06, 0.55, -1], "calf_l": [0.02, 0.12, -1], "thigh_r": [-0.05, -0.42, -1], "calf_r": [-0.02, -1, -0.45],
                      "upperarm_r": [-0.12, 0.65, -1], "lowerarm_r": [-0.05, 1, 0.65], "upperarm_l": [0.12, -0.75, -1], "lowerarm_l": [0.05, 0.55, -0.6]},
              "fingers": {"l": "fist", "r": "fist"}}
P["run_b"] = {"desc": "달리기 2", "mirror": "run_a"}

P["phone_look"] = {"desc": "폰 보기 (고개 푹)", "rot": {"spine_02": {"pitch": 6}, "neck_01": {"pitch": 18}, "head": {"pitch": 22}},
                   "aim": {"upperarm_r": [-0.14, 0.12, -1], "lowerarm_r": [0.32, 1, 0.42], "upperarm_l": [0.18, 0.02, -1], "lowerarm_l": [0.1, 0.1, -1]},
                   "sym": {"thigh": [0.07, 0, -1], "calf": [0.04, 0, -1]},
                   "rot_after": {"hand_r": {"pitch": -25}},
                   "fingers": {"l": "relax", "r": "grip"}}

P["mirror_flex"] = {"desc": "거울 앞 폼 (한팔 알통)", "root": {"twist": -18},
                    "rot": {"head": {"twist": 30, "pitch": -6}},
                    "aim": {"upperarm_l": [1, 0.0, 0.1], "lowerarm_l": [0.1, 0.05, 1],
                            "upperarm_r": [-0.75, -0.25, -0.62], "lowerarm_r": [0.72, 0.18, -0.62]},
                    "sym": {"thigh": [0.12, 0, -1], "calf": [0.06, 0, -1]},
                    "fingers": {"l": "fist", "r": "fist"}}

P["shrug"] = {"desc": "어깨 으쓱 (몰라~)", "rot": {"head": {"side": 12}, "clavicle_l": {"side": 10}, "clavicle_r": {"side": -10}},
              "sym": {"upperarm": [0.38, 0.12, -0.9], "lowerarm": [0.75, 0.55, 0.1], "thigh": [0.07, 0, -1], "calf": [0.04, 0, -1]},
              "fingers": {"l": "open", "r": "open"}}

P["check_watch"] = {"desc": "손목 시계 보기", "rot": {"neck_01": {"pitch": 12}, "head": {"pitch": 18, "twist": 14}},
                    "aim": {"upperarm_l": [0.35, 0.45, -0.85], "lowerarm_l": [-0.55, 0.85, 0.2], "upperarm_r": [-0.18, 0.02, -1], "lowerarm_r": [-0.1, 0.1, -1]},
                    "sym": {"thigh": [0.07, 0, -1], "calf": [0.04, 0, -1]},
                    "rot_after": {"hand_l": {"twist": 0}},
                    "fingers": {"l": "relax", "r": "relax"}}

P["jump_joy"] = {"desc": "점프 환호", "ground": False, "root": {"lift": 0.1, "pitch": -4},
                 "rot": {"head": {"pitch": -12}},
                 "sym": {"upperarm": [0.55, 0.1, 1], "lowerarm": [0.38, 0.1, 1], "thigh": [0.1, 0.25, -1], "calf": [0.05, -0.85, -0.6]},
                 "fingers": {"l": "fist", "r": "fist"}}

P["sit"] = {"desc": "앉기 (벤치)", "rot": {"spine_02": {"pitch": 6}},
            "sym": {"upperarm": [0.2, 0.25, -1], "lowerarm": [0.0, 1, -0.25], "thigh": [0.14, 1, 0.0], "calf": [0.08, 0.05, -1]},
            "fingers": {"l": "relax", "r": "relax"}}

P["sit_phone"] = {"desc": "앉아서 폰 (휴식 10분)", "base": "sit",
                  "rot": {"spine_02": {"pitch": 12}, "neck_01": {"pitch": 18}, "head": {"pitch": 22}},
                  "aim": {"upperarm_r": [-0.1, 0.35, -1], "lowerarm_r": [0.3, 1, 0.5], "upperarm_l": [0.18, 0.3, -1], "lowerarm_l": [-0.05, 1, -0.3]},
                  "rot_after": {"hand_r": {"pitch": -25}},
                  "fingers": {"l": "relax", "r": "grip"}}

P["carry_plate"] = {"desc": "원판 들고 걷기 자세 (엑스트라)", "base": "walk_a",
                    "aim": {"upperarm_l": [0.05, 0.35, -1], "lowerarm_l": [-0.2, 1, 0.1], "upperarm_r": [-0.05, 0.35, -1], "lowerarm_r": [0.2, 1, 0.1]},
                    "fingers": {"l": "grip", "r": "grip"}}

P["sneak"] = {"desc": "살금살금 (자리 맡고 도망)", "root": {"pitch": 18},
              "rot": {"head": {"pitch": -18}},
              "aim": {"thigh_l": [0.08, 0.75, -0.75], "calf_l": [0.04, 0.0, -1], "thigh_r": [-0.08, -0.2, -1], "calf_r": [-0.03, -0.55, -1]},
              "sym": {"upperarm": [0.3, 0.55, -0.6], "lowerarm": [0.05, 0.55, 0.85]},
              "rot_after": {"hand_l": {"pitch": 45}, "hand_r": {"pitch": 45}},
              "fingers": {"l": "relax", "r": "relax"}}

P["point_r"] = {"desc": "가리킴 (화면 왼쪽 앞)", "mirror": "point"}
P["walk_c"] = {"desc": "걷기 중간 (지나가는 자세)", "aim": {"thigh_l": [0.06, 0.25, -1], "calf_l": [0.03, -0.35, -1], "thigh_r": [-0.06, -0.05, -1], "calf_r": [-0.03, 0, -1]},
               "sym": {"upperarm": [0.16, 0.02, -1], "lowerarm": [0.08, 0.2, -1]}, "fingers": {"l": "relax", "r": "relax"}}
