"""Second batch: the remaining apparatus from design/equipment-reference/taxonomy.py. Same conventions as equipment_machines."""
import math
import equipment_kit as K
from equipment_kit import cyl, box, part, _plate
from equipment_machines import beam, rod, pad, stack_tower, _seat_unit, pivot_hub, grip_handle, _drive, _dial, _seat_lever, _trolley, _rack_post, _chin_grips, _hinge, _linkage


def _base(p, y0=-0.65, y1=0.95, mat="silver"):
    beam("base", p, (0, y0, 0.05), (0, y1, 0.05), 0.14, mat, 0.08)


def lateral_raise_machine():
    p = part("lateral_raise_machine"); _base(p, -0.5, 0.9); stack_tower(p, 0, 0.78, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.12)
    _drive(p,(.28,.10,1.25))
    beam("pivot_bridge",p,(-.28,.10,1.25),(.28,.10,1.25),.045,"silver")
    beam("bridge_stay",p,(0,.68,1.21),(0,.10,1.25),.052,"silver")
    for s in (-1, 1):
        beam("arm", p, (s * 0.30, 0.0, 1.0), (s * 0.55, -0.12, 1.0), 0.05, "silver")
        pad("elbow", p, (0.10, 0.22, 0.10), (s * 0.55, -0.12, 0.98)); rod("grip", p, (s * 0.52, -0.20, 0.80), (s * 0.52, -0.20, 0.95), 0.02, "grip")
        beam("pivot", p, (s * 0.30, 0.0, 1.0), (s * 0.28, 0.1, 1.25), 0.05, "silver")
        grip_handle("neutral",p,(s*.52,-.20,.93),(s*.44,-.20,.93),.018)
        rod("grip_stem",p,(s*.52,-.20,.95),(s*.55,-.12,.99),.019)
    for side in (-1,1):
        _hinge(p,(side*.28,.10,1.25),("arm","elbow","grip","pivot","neutral","grip_stem"),
               1,-side*44,side)
    return p


def shoulder_press_machine():
    p = part("shoulder_press_machine")
    stack_tower(p,0,.72,.47,.35,1.70,.07)
    _drive(p,(.45,.45,1.90))
    for side in (-1,1):
        beam("runner",p,(side*.60,-.55,.04),(side*.60,.95,.04),.10,"silver",.08)
        beam("upright",p,(side*.55,.56,.06),(side*.45,.45,2.05),.064,"frame")
        if side < 0:
            pivot_hub("press_bearing",p,(side*.45,.45,1.90),.074,.10)
        beam("upper_lever",p,(side*.45,.45,1.90),(side*.47,.04,1.64),.055,"frame")
        beam("lower_lever",p,(side*.47,.04,1.64),(side*.34,-.23,1.28),.048,"silver")
        grip_handle("overhand",p,(side*.34,-.23,1.28),(side*.18,-.23,1.28))
        grip_handle("neutral",p,(side*.34,-.23,1.28),(side*.34,-.37,1.28))
        beam("rear_tie",p,(0,.72,.09),(side*.60,.72,.09),.042,"silver")
        cyl("storage_horn",p,.025,.34,"X","steel",(side*.72,.47,.62))
        beam("storage_mount",p,(side*.50,.53,.62),(side*.57,.47,.62),.052,"silver")
    beam("crosshead",p,(-.45,.45,2.05),(.45,.45,2.05),.065,"silver")
    pad("seat",p,(.40,.40,.09),(0,.05,.46))
    beam("seat_post",p,(0,.05,.42),(0,.05,.07),.072,"silver")
    beam("seat_base",p,(0,.05,.07),(0,.72,.09),.072,"silver")
    _seat_lever(p,.05,.34)
    pad("lumbar",p,(.39,.10,.24),(0,.254,.702),(-12,0,0))
    pad("back",p,(.40,.10,.45),(0,.328,1.055),(-12,0,0))
    beam("back_stay",p,(0,.15,.37),(0,.43,1.21),.05,"silver")
    for side in (-1,1):
        _hinge(p,(side*.45,.45,1.90),("upper_lever","lower_lever","overhand","neutral"),0,-35,side)
    return p


def shrug_machine():
    p = part("shrug_machine")
    for s in (-1, 1):
        beam("foot", p, (s * 0.60, -0.5, 0.04), (s * 0.60, 0.9, 0.04), 0.10, "frame", 0.08)
        beam("arm", p, (s * 0.40, 0.35, 1.2), (s * 0.40, -0.25, 0.95), 0.06)
        rod("handle", p, (s * 0.40, -0.25, 0.95), (s * 0.40, -0.25, 0.60), 0.022, "grip")
        cyl("peg", p, 0.03, 0.35, "X", "steel", (s * 0.60, 0.35, 1.2), 6)
        for i in range(2): cyl("plate", p, 0.22, 0.03, "X", "plate", (s * (0.68 + i * 0.04), 0.35, 1.2), 12)
        beam("up", p, (s * 0.50, 0.40, 0.04), (s * 0.50, 0.40, 1.2), 0.06)
    pad("back", p, (0.40, 0.10, 0.90), (0, 0.50, 1.05)); pad("seat", p, (0.40, 0.36, 0.09), (0, 0.25, 0.46)); beam("seat_post", p, (0, 0.25, 0.4), (0, 0.25, 0.05), 0.08)
    return p


def tbar_row_machine():
    """Chest-supported T-bar row: inclined chest pad, pivoting lever with V handle and a plate peg."""
    p = part("tbar_row_machine")
    for s in (-1, 1): beam("foot", p, (s * 0.50, -0.6, 0.04), (s * 0.50, 1.0, 0.04), 0.10, "frame", 0.08)
    beam("frame", p, (0, 0.5, 0.05), (0, -0.3, 0.80), 0.10)
    pad("chest", p, (0.40, 0.70, 0.09), (0, 0.15, 0.72), (-38, 0, 0), "pad")
    beam("foot_tie",p,(-.50,.50,.07),(.50,.50,.07),.055,"silver")
    beam("chest_mount",p,(0,.15,.37),(0,.15,.71),.062,"silver")
    lv = part("tbar_lever")
    lv.parent, lv.location = p,(0,.30,.50)
    for side in (-1,1):
        x = side*.28
        beam("pivot_stand",p,(side*.50,.80,.08),(x,.80,.47),.043,"silver")
        pivot_hub("lever_bearing",lv,(x,.50,0),.066,.075)
        arm = part("tbar_arm_L" if side < 0 else "tbar_arm_R")
        arm.parent, arm.location = lv, (x, .50, 0)
        K._stroke(arm,"rotation_euler",0,p,-.42,"Stroke L" if side<0 else "Stroke R")
        beam("lever", arm, (0, .04, 0), (0, -1.05, .22), .043, "silver")
        cyl("counterweight", arm, .083, .065, "X", "silver", (0, .08, 0))
        cyl("weight_horn", arm, .024, .19, "X", "steel", (side*.10, -.74, .16))
        _plate(arm, .16, .034, (side*.06, -.74, .16), True)
        grip_handle("wide_grip", arm, (0, -1.05, .22), (side*.15, -1.05, .22))
        grip_handle("parallel_grip", arm, (0, -1.05, .22), (0, -.88, .27))
        box("incline_footrest",p,(.23,.38,.04),"silver",(side*.35,.60,.22),(18,0,0))
        beam("footrest_stay",p,(side*.50,.59,.06),(side*.35,.61,.21),.038,"silver")
    return p


def pullover_machine():
    p = part("pullover_machine"); _base(p, -0.6, 0.9); stack_tower(p, 0, 0.78, 0.48, 0.40, 1.45, 0.07)
    pad("seat", p, (0.42, 0.40, 0.09), (0, 0.0, 0.45)); beam("seat_post", p, (0, 0, 0.4), (0, 0, 0.06), 0.09, "silver")
    pad("back", p, (0.42, 0.10, 0.62), (0, 0.25, 0.82), (-15, 0, 0))
    for s in (-1, 1):
        beam("arm", p, (s * 0.25, 0.20, 1.45), (s * 0.30, -0.35, 1.05), 0.05, "silver"); pad("elbow", p, (0.10, 0.22, 0.08), (s * 0.30, -0.05, 1.25), (-35, 0, 0))
    beam("cam", p, (-0.25, 0.20, 1.45), (0.25, 0.20, 1.45), 0.07, "silver")
    return p


def dip_machine():
    p = part("dip_machine"); _base(p, -0.5, 0.9); stack_tower(p, 0, 0.78, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.15)
    for s in (-1, 1):
        beam("arm", p, (s * 0.28, 0.0, 0.85), (s * 0.34, -0.40, 0.70), 0.05, "silver"); rod("grip", p, (s * 0.34, -0.40, 0.70), (s * 0.34, -0.55, 0.70), 0.022, "grip")
    box("foot_bar", p, (0.55, 0.06, 0.05), "silver", (0, -0.30, 0.25))
    return p


def assisted_pullup():
    p = part("assisted_pullup"); H = 2.3
    stack_tower(p, 0, 0.62, 0.46, 0.38, 1.4, 0.07)
    for s in (-1, 1):
        beam("post", p, (s * 0.50, 0.20, 0), (s * 0.50, 0.20, H), 0.08, "silver"); beam("foot", p, (s * 0.50, -0.5, 0.04), (s * 0.50, 0.7, 0.04), 0.09, "frame", 0.08)
        beam("handle_arm", p, (s * 0.50, 0.20, H - 0.05), (s * 0.50, -0.20, H - 0.05), 0.06, "silver"); rod("pull", p, (s * 0.50, -0.20, H - 0.05), (s * 0.50, -0.20, H - 0.35), 0.02, "grip")
    rod("bar", p, (-0.5, -0.2, H - 0.05), (0.5, -0.2, H - 0.05), 0.017)
    pad("knee", p, (0.40, 0.30, 0.08), (0, -0.10, 0.90)); beam("knee_post", p, (0, -0.1, 0.9), (0, 0.2, 0.9), 0.06, "silver")
    for side in (-1,1):
        for z in (.67,.82):
            beam("knee_link",p,(side*.17,.41,z+.09),(side*.17,-.09,z),.029,"silver")
            pivot_hub("link_bush",p,(side*.17,.41,z+.09),.036,.048)
        beam("link_anchor",p,(side*.5,.2,.76),(side*.17,.41,.89),.038,"silver")
        beam("knee_carrier",p,(side*.17,-.09,.67),(side*.17,-.09,.88),.03,"silver")
        box("step",p,(.18,.28,.035),"silver",(side*.40,-.27,.42))
        beam("step_support",p,(side*.50,.20,.31),(side*.40,-.27,.41),.036,"silver")
        grip_handle("dip_grip",p,(side*.50,.19,1.32),(side*.49,-.16,1.32))
    # Parallel links keep the knee platform level through the assisted descent.
    carriage = _linkage(p,(0,-.09,.82),("knee","knee_post","knee_carrier"))
    theta = ".53*v"
    for target,path,index,expr in (
        (carriage,"location",1,".41-.50*cos("+theta+")+.09*sin("+theta+")"),
        (carriage,"location",2,".91-.50*sin("+theta+")-.09*cos("+theta+")")):
        K._driver(target,path,index,p,expr,v="Stroke")
    for link in [ob for ob in p.children if ob.name.split(".")[0]=="knee_link"]:
        joint = part("Assist link bearing")
        joint.parent = p
        joint.location = (link.location.x,.41,link.location.z+.045)
        link.parent = joint
        link.location -= joint.location
        K._stroke(joint,"rotation_euler",0,p,.53)
    return p


def preacher_machine():
    p = part("preacher_machine"); _base(p, -0.5, 0.9); stack_tower(p, 0, 0.78, 0.48, 0.40, 1.45, 0.07)
    pad("seat", p, (0.40, 0.36, 0.09), (0, 0.30, 0.46)); beam("seat_post", p, (0, 0.30, 0.428), (0, 0.30, 0.06), 0.08, "silver")
    pad("arm_pad", p, (0.42, 0.50, 0.08), (0, 0.0, 0.85), (-40, 0, 0)); beam("pad_post", p, (0, 0.0, 0.80), (0, -0.05, 0.06), 0.09, "silver")
    for s in (-1, 1):
        beam("arm", p, (s * 0.14, 0.05, 1.0), (s * 0.20, -0.45, 0.88), 0.04, "silver"); rod("grip", p, (s * 0.20, -0.45, 0.88), (s * 0.20, -0.45, 1.0), 0.022, "grip")
    _dial(p,.177,.05,1.00,.084)
    beam("lever_mount",p,(0,.04,.73),(.14,.05,1.0),.038,"silver")
    _seat_lever(p,.30,.34)
    _hinge(p,(0,.05,1.0),("arm","grip"),0,-58)
    return p


def leg_press_horizontal():
    p = part("leg_press_horizontal"); _base(p, -0.9, 0.9); stack_tower(p, 0, 0.85, 0.48, 0.40, 1.4, 0.07)
    pad("seat", p, (0.46, 0.46, 0.10), (0, 0.30, 0.46)); beam("seat_post", p, (0, 0.30, 0.428), (0, 0.30, 0.06), 0.1, "silver")
    pad("back", p, (0.46, 0.10, 0.62), (0, 0.55, 0.85), (-12, 0, 0))
    box("foot_plate", p, (0.55, 0.06, 0.55), "silver", (0, -0.55, 0.70), (-10, 0, 0))
    for s in (-1, 1): beam("rail", p, (s * 0.30, -0.55, 0.40), (s * 0.30, 0.1, 0.40), 0.05, "silver")
    return p


def pendulum_squat():
    p = part("pendulum_squat")
    for s in (-1, 1):
        beam("foot", p, (s * 0.55, -0.9, 0.04), (s * 0.55, 0.9, 0.04), 0.10, "frame", 0.08)
        beam("post", p, (s * 0.55, 0.75, 0.04), (s * 0.55, 0.75, 1.9), 0.08)
    beam("top", p, (-0.55, 0.75, 1.9), (0.55, 0.75, 1.9), 0.08)
    lv = part("pendulum_arm"); lv.parent = p; lv.location = (0, 0.75, 1.9)
    beam("arm", lv, (0, 0, 0), (0, -0.45, -1.30), 0.10, "silver")
    pad("shoulder", lv, (0.45, 0.14, 0.16), (0, -0.38, -1.10), (0, 0, 0))
    cyl("peg", lv, 0.03, 0.9, "X", "steel", (0, 0.1, -0.5), 6)
    for s in (-1, 1):
        for i in range(2): cyl("plate", lv, 0.22, 0.03, "X", "plate", (s * (0.38 + i * 0.04), 0.1, -0.5), 12)
    box("foot_plate", p, (0.6, 0.55, 0.05), "silver", (0, -0.40, 0.18), (-20, 0, 0))
    return p


def belt_squat():
    p = part("belt_squat")
    beam("base", p, (0, -0.8, 0.04), (0, 0.4, 0.04), 0.9, "frame", 0.06)
    for s in (-1, 1):
        beam("post", p, (s * 0.30, 0.45, 0.04), (s * 0.30, 0.45, 2.0), 0.08)
        cyl("peg", p, 0.03, 0.4, "X", "steel", (s * 0.30, 0.0, 0.20), 6)
    beam("top", p, (-0.3, 0.45, 2.0), (0.3, 0.45, 2.0), 0.08)
    lv = part("belt_lever"); lv.parent = p; lv.location = (0, 0.45, 1.8)
    rod("chain", lv, (0, 0, 0), (0, -0.2, -1.0), 0.015, "steel"); box("belt", lv, (0.4, 0.06, 0.18), "pad", (0, -0.2, -1.05))
    for s in (-1, 1): box("hand_post", p, (0.04, 0.04, 0.6), "steel", (s * 0.35, -0.2, 1.0))
    return p


def _curl_base(p, lying=False):
    _base(p, -0.65, 0.95); stack_tower(p, 0, 0.82, 0.46, 0.38, 1.3, 0.07)


def seated_leg_curl():
    p = part("seated_leg_curl"); _curl_base(p)
    pad("seat", p, (0.42, 0.50, 0.09), (0, 0.0, 0.50), (8, 0, 0))
    beam("seat_post", p, (0, 0, 0.45), (0, 0, 0.06), 0.075, "silver")
    pad("back", p, (0.42, 0.10, 0.62), (0, 0.38, 0.88), (-15, 0, 0))
    beam("back_post", p, (0, 0.44, 0.45), (0, 0.48, 1.05), 0.065, "silver")
    pad("thigh", p, (0.36, 0.26, 0.10), (0, -0.20, 0.68))
    beam("thigh_arm", p, (0, -0.2, 0.65), (0, -0.2, 0.2), 0.045, "silver")
    cyl("thigh_pop_pin", p, 0.018, 0.045, "X", "accent", (0.06, -0.20, 0.52), sides=16)
    for s in (-1, 1):
        grip_handle("curl_grip", p, (s * 0.24, -0.26, 0.72), (s * 0.24, -0.10, 0.72), 0.020)
    lv = part("curl_lever"); lv.parent = p; lv.location = (0, -0.38, 0.35)
    pivot_hub("curl_pivot", lv, (0.21, 0.08, 0.08), r=0.056, width=0.06, axis="X")
    _dial(lv,.239,.08,.08,.111)
    cyl("roller", lv, 0.062, 0.42, "X", "pad", (0, -0.1, -0.1), sides=24)
    cyl("roller_cap_l", lv, 0.045, 0.016, "X", "steel", (-0.215, -0.1, -0.1), sides=20)
    cyl("roller_cap_r", lv, 0.045, 0.016, "X", "steel", (0.215, -0.1, -0.1), sides=20)
    for s in (-1, 1):
        beam("arm", lv, (s * 0.20, 0.1, 0.1), (s * 0.20, -0.1, -0.1), 0.045, "silver")
    # The roller swings about the side bearing, offset from the lever's legacy origin.
    axle = _linkage(p,(0,-.30,.43),("P_curl_lever",))
    K._stroke(axle,"rotation_euler",0,p,.86)
    return p


def lying_leg_curl():
    p = part("lying_leg_curl"); _curl_base(p)
    pad("bed", p, (0.40, 0.95, 0.09), (0, -0.05, 0.62), (14, 0, 0)); beam("bed_post", p, (0, -0.25, 0.6), (0, -0.25, 0.06), 0.09, "silver"); beam("bed_post2", p, (0, 0.30, 0.55), (0, 0.30, 0.06), 0.09, "silver")
    lv = part("curl_lever"); lv.parent = p; lv.location = (0, -0.60, 0.72)
    cyl("roller", lv, 0.055, 0.34, "X", "pad", (0, -0.0, 0.0), 8)
    for s in (-1, 1): beam("arm", lv, (s * 0.18, 0, 0), (s * 0.18, 0.55, -0.15), 0.04, "silver")
    pad("handle", p, (0.4, 0.04, 0.04), (0, 0.45, 0.78), (0, 0, 0), "grip")
    return p


def standing_leg_curl():
    p = part("standing_leg_curl")
    beam("base", p, (0, -0.55, 0.04), (0, 0.5, 0.04), 0.5, "silver", 0.06)
    beam("post", p, (0, 0.35, 0.04), (0, 0.35, 1.45), 0.18, "silver")
    pad("chest", p, (0.36, 0.14, 0.50), (0, 0.12, 1.20), (-10, 0, 0)); pad("knee", p, (0.30, 0.20, 0.10), (0, 0.08, 0.60), (-30, 0, 0))
    lv = part("curl_lever"); lv.parent = p; lv.location = (0, 0.20, 0.50)
    beam("arm", lv, (0, 0, 0), (0, -0.2, -0.30), 0.05, "silver"); cyl("roller", lv, 0.055, 0.30, "X", "pad", (0, 0.2, -0.25), 8)
    for s in (-1, 1): rod("grip", p, (s * 0.2, -0.05, 1.05), (s * 0.2, -0.20, 1.05), 0.02, "grip")
    box("stack", p, (0.35, 0.2, 0.9), "stack", (0, 0.55, 0.5))
    return p


def hip_abductor():
    p = part("hip_abductor"); _base(p, -0.55, 0.9); stack_tower(p, 0, 0.78, 0.48, 0.40, 1.4, 0.07)
    _seat_unit(p, 0.15)
    _dial(p,.19,-.03,.407,.079)
    beam("range_mount",p,(0,.00,.38),(.19,-.03,.407),.031,"silver")
    for s in (-1, 1):
        beam("arm", p, (s * 0.10, -0.05, 0.50), (s * 0.40, -0.05, 0.56), 0.045, "silver")
        pivot_hub("abductor_hub", p, (s * 0.14, -0.05, 0.50), r=0.048, width=0.05, axis="Z")
        pad("knee_pad", p, (0.10, 0.18, 0.32), (s * 0.40, -0.05, 0.68))
        # Foot rest pegs & side seat handles
        beam("foot_peg_arm", p, (s * 0.40, -0.05, 0.52), (s * 0.40, -0.22, 0.26), 0.032, "silver")
        rod("foot_peg", p, (s * 0.32, -0.22, 0.26), (s * 0.46, -0.22, 0.26), 0.018, "grip")
        grip_handle("side_grip", p, (s * 0.27, -0.14, 0.45), (s * 0.27, 0.06, 0.45), 0.020)
    for side in (-1,1):
        _hinge(p,(side*.14,-.05,.50),("arm","knee_pad","foot_peg","foot_peg_arm"),2,side*23,side)
    return p


def hip_thrust_machine():
    p = part("hip_thrust_machine")
    for s in (-1, 1): beam("foot", p, (s * 0.55, -0.6, 0.04), (s * 0.55, 1.1, 0.04), 0.10, "frame", 0.08)
    pad("back", p, (0.60, 0.50, 0.12), (0, 0.60, 0.45), (-20, 0, 0)); beam("back_post", p, (0, 0.6, 0.4), (0, 0.75, 0.05), 0.1)
    box("foot_plate", p, (0.60, 0.5, 0.04), "silver", (0, -0.35, 0.18), (-15, 0, 0))
    lv = part("hip_belt"); lv.parent = p; lv.location = (0, 0.15, 0.55)
    for s in (-1, 1): beam("arm", lv, (s * 0.3, 0.3, 0), (s * 0.3, -0.1, 0.4), 0.05, "silver"); cyl("peg", lv, 0.03, 0.3, "X", "steel", (s * 0.4, 0.3, 0), 6)
    pad("belt", lv, (0.6, 0.12, 0.14), (0, -0.1, 0.40))
    return p


def standing_calf():
    p = part("standing_calf")
    beam("base", p, (0, -0.75, 0.04), (0, 0.65, 0.04), 0.7, "frame", 0.06)
    for s in (-1, 1): beam("post", p, (s * 0.25, 0.30, 0.04), (s * 0.25, 0.30, 1.55), 0.08, "silver")
    for s in (-1, 1): pad("shoulder", p, (0.18, 0.40, 0.14), (s * 0.20, 0.15, 1.25))
    beam("yoke", p, (-0.25, 0.30, 1.35), (0.25, 0.30, 1.35), 0.08, "silver")
    box("step", p, (0.60, 0.30, 0.10), "silver", (0, -0.45, 0.14), (-10, 0, 0))
    for s in (-1, 1): box("peg", p, (0.04, 0.4, 0.04), "steel", (s * 0.40, 0.30, 0.7))
    return p


def seated_calf():
    p = part("seated_calf")
    beam("base", p, (0, -0.7, 0.04), (0, 0.8, 0.04), 0.9, "frame", 0.06)
    pad("seat", p, (0.40, 0.36, 0.09), (0, 0.45, 0.44)); beam("seat_post", p, (0, 0.45, 0.4), (0, 0.45, 0.06), 0.1)
    for s in (-1, 1): pad("knee", p, (0.16, 0.20, 0.30), (s * 0.15, 0.10, 0.65), (-20, 0, 0))
    beam("lever", p, (0, 0.10, 0.60), (0, -0.2, 0.60), 0.07, "silver")
    box("toe", p, (0.55, 0.30, 0.04), "silver", (0, -0.40, 0.20), (-10, 0, 0))
    cyl("peg", p, 0.03, 0.9, "X", "steel", (0, -0.1, 0.32), 6)
    for s in (-1, 1):
        for i in range(2): cyl("plate", p, 0.20, 0.03, "X", "plate", (s * (0.34 + i * 0.04), -0.1, 0.32), 12)
    return p


def glute_kickback_machine():
    p = part("glute_kickback_machine"); _base(p, -0.6, 0.9); stack_tower(p, 0, 0.78, 0.48, 0.40, 1.4, 0.07)
    box("step", p, (0.50, 0.30, 0.04), "silver", (0, -0.15, 0.20))
    pad("chest", p, (0.40, 0.12, 0.34), (0, 0.20, 1.10)); beam("post", p, (0, 0.25, 0.1), (0, 0.25, 1.1), 0.10, "silver")
    for s in (-1, 1): rod("grip", p, (s * 0.2, 0.10, 1.0), (s * 0.2, 0.0, 1.0), 0.02, "grip")
    lv = part("kick_lever"); lv.parent = p; lv.location = (0, 0.30, 0.55)
    beam("arm", lv, (0, 0, 0), (0, -0.2, -0.40), 0.05, "silver"); pad("heel", lv, (0.20, 0.14, 0.12), (0, -0.2, -0.40))
    return p


def high_pulley():
    p = part("high_pulley"); H = 2.3
    beam("base", p, (0, -0.4, 0.04), (0, 0.6, 0.04), 0.5, "frame", 0.06)
    beam("post", p, (0, 0.0, 0.04), (0, 0.0, H), 0.12, "silver", 0.10)
    stack_tower(p, 0, 0.42, 0.40, 0.34, 1.3, 0.05)
    cyl("pulley", p, 0.09, 0.04, "X", "accent", (0, -0.08, H - 0.1), 10)
    box("slot", p, (0.04, 0.03, 1.9), "grip", (0, -0.065, 1.2)); box("carriage", p, (0.12, 0.10, 0.16), "steel", (0, -0.06, 1.7))
    return p


def functional_trainer():
    p = part("functional_trainer"); W = 1.1; H = 2.3
    for s in (-1, 1):
        _rack_post(p,s*W/2,0,H,.155,.155)
        beam("post_b", p, (s * W / 2, 0.40, 0), (s * W / 2, 0.40, H), 0.10, "frame", 0.10)
        beam("link", p, (s * W / 2, 0, H), (s * W / 2, 0.40, H), 0.08, "frame")
        stack_tower(p, s * (W / 2 + 0.28), 0.2, 0.22, 0.34, 1.6, 0.05)
        beam("foot", p, (s * W / 2, -0.3, 0.04), (s * W / 2, 0.7, 0.04), 0.106, "frame", 0.083)
        _trolley(p,s*W/2,1.30)
        cyl("Storage pin",p,.021,.16,"X","steel",(s*(W/2+.13),.40,.57))
    beam("top", p, (-W / 2, 0, H), (W / 2, 0, H), 0.10); beam("top_b", p, (-W / 2, 0.4, H), (W / 2, 0.4, H), 0.10)
    beam("mid", p, (-W / 2, 0.4, 1.2), (W / 2, 0.4, 1.2), 0.08)
    _chin_grips(p,W/2,H,.18)
    return p


def decline_sit_up():
    p = part("decline_sit_up")
    pad("back", p, (0.34, 1.0, 0.10), (0, 0.15, 0.50), (-22, 0, 0)); pad("seat", p, (0.34, 0.20, 0.10), (0, 0.78, 0.30), (-22, 0, 0))
    beam("spine", p, (0, 0.80, 0.30), (0, -0.35, 0.55), 0.06)
    beam("leg_f", p, (0, -0.30, 0.55), (0, -0.40, 0.02), 0.07); box("foot_f", p, (0.55, 0.07, 0.05), "frame", (0, -0.40, 0.02))
    beam("leg_b", p, (0, 0.80, 0.28), (0, 0.85, 0.02), 0.07); box("foot_b", p, (0.55, 0.07, 0.05), "frame", (0, 0.85, 0.02))
    beam("ankle_post", p, (0, -0.35, 0.55), (0, -0.50, 0.95), 0.05, "steel")
    for z in (0.72, 0.88): cyl("roller", p, 0.055, 0.38, "X", "pad", (0, -0.52, z), 8)
    return p


def inverted_row_bar():
    p = part("inverted_row_bar")
    for s in (-1, 1):
        beam("post", p, (s * 0.65, 0.0, 0.0), (s * 0.65, 0.0, 1.3), 0.08)
        beam("foot", p, (s * 0.65, -0.6, 0.04), (s * 0.65, 0.6, 0.04), 0.09, "frame", 0.08)
        beam("brace", p, (s * 0.65, 0.5, 0.05), (s * 0.65, 0.0, 1.1), 0.05)
    rod("bar", p, (-0.75, 0.0, 1.0), (0.75, 0.0, 1.0), 0.017)
    return p


def plyo_box():
    p = part("plyo_box"); box("box", p, (0.76, 0.61, 0.51), "wood", (0, 0, 0.255)); box("rim", p, (0.78, 0.63, 0.03), "wood", (0, 0, 0.51))
    for s in (-1, 1): box("hole", p, (0.22, 0.01, 0.09), "grip", (0, s * 0.31, 0.30)); box("hole", p, (0.01, 0.22, 0.09), "grip", (s * 0.38, 0, 0.30))
    return p


def ab_wheel():
    p = part("ab_wheel"); cyl("wheel", p, 0.11, 0.07, "X", "plate", (0, 0, 0.11), 12); cyl("hub", p, 0.05, 0.09, "X", "steel", (0, 0, 0.11), 8)
    cyl("axle", p, 0.014, 0.34, "X", "steel", (0, 0, 0.11), 6)
    for s in (-1, 1): cyl("grip", p, 0.028, 0.12, "X", "grip", (s * 0.15, 0, 0.11), 8)
    return p


def nordic_pad():
    p = part("nordic_pad"); box("base", p, (0.60, 0.7, 0.05), "frame", (0, 0, 0.025)); pad("knee_pad", p, (0.45, 0.35, 0.05), (0, 0.25, 0.075))
    for s in (-1, 1): beam("post", p, (s * 0.20, -0.2, 0.05), (s * 0.20, -0.2, 0.60), 0.06)
    for z in (0.46, 0.60): cyl("roller", p, 0.045, 0.50, "X", "pad", (0, -0.2, z), 8)
    return p


def exercise_mat():
    p = part("exercise_mat"); box("mat", p, (0.60, 1.80, 0.02), "plate", (0, 0, 0.01)); box("edge", p, (0.62, 0.04, 0.022), "accent", (0, 0.88, 0.011)); return p


def landmine():
    p = part("landmine"); cyl("base", p, 0.08, 0.05, "Z", "frame", (0, 0, 0.025), 8)
    cyl("pivot", p, 0.03, 0.12, "Z", "steel", (0, 0, 0.10), 6)
    rod("bar", p, (0, 0, 0.12), (0, -1.9, 0.60), 0.016); cyl("sleeve", p, 0.026, 0.3, "Y", "steel", (0, -1.6, 0.52), 8).rotation_euler.x = math.radians(90 - 14)
    return p


def trap_bar():
    p = part("trap_bar")
    pts = [(0, -0.46), (0.30, -0.22), (0.30, 0.22), (0, 0.46), (-0.30, 0.22), (-0.30, -0.22)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]): rod("tube", p, (x0, y0, 0), (x1, y1, 0), 0.02)
    for s in (-1, 1):
        rod("tube", p, (0, s * 0.46, 0), (0, s * 0.62, 0), 0.022); cyl("sleeve", p, 0.028, 0.42, "Y", "steel", (0, s * 0.84, 0.0), 8)
        cyl("grip", p, 0.024, 0.14, "Y", "grip", (s * 0.30, 0.0, 0.0), 8)
    return p


def kettlebell():
    p = part("kettlebell")
    cyl("base", p, 0.07, 0.02, "Z", "plate", (0, 0, 0.01), 8); cyl("belly", p, 0.125, 0.12, "Z", "plate", (0, 0, 0.10), 10); cyl("shoulder", p, 0.085, 0.07, "Z", "plate", (0, 0, 0.19), 10)
    for s in (-1, 1): rod("handle", p, (s * 0.075, 0, 0.19), (s * 0.075, 0, 0.30), 0.022, "accent")
    rod("handle", p, (-0.075, 0, 0.31), (0.075, 0, 0.31), 0.022, "accent"); return p


def weight_plate():
    p = part("weight_plate")
    _plate(p,.225,.055,(0,0,.225),grips=True)
    return p


def hip_thrust_machine():
    p = part("hip_thrust_machine")
    for s in (-1, 1): beam("foot", p, (s * 0.55, -0.7, 0.04), (s * 0.55, 1.1, 0.04), 0.10, "frame", 0.08)
    box("bench", p, (0.60, 0.55, 0.40), "frame", (0, 0.70, 0.24)); pad("bench_pad", p, (0.60, 0.55, 0.10), (0, 0.70, 0.47))
    box("foot_plate", p, (0.60, 0.5, 0.05), "silver", (0, -0.40, 0.14), (-15, 0, 0))
    lv = part("hip_belt"); lv.parent = p; lv.location = (0, 0.25, 0.50)
    for s in (-1, 1):
        beam("arm", lv, (s * 0.30, 0.35, 0.10), (s * 0.30, -0.05, 0.55), 0.06, "silver"); beam("up", lv, (s * 0.30, 0.35, 0.10), (s * 0.45, 0.35, 0.10), 0.06, "silver")
        cyl("peg", lv, 0.03, 0.30, "X", "steel", (s * 0.50, 0.35, 0.10), 6)
        for i in range(2): cyl("plate", lv, 0.20, 0.03, "X", "plate", (s * (0.58 + i * 0.04), 0.35, 0.10), 12)
    pad("belt", lv, (0.60, 0.16, 0.16), (0, -0.05, 0.58))
    return p


def hyperextension():
    p = part("hyperextension")
    for z, y in ((0.02, -0.55), (0.02, 0.60)): box("foot", p, (0.62, 0.08, 0.05), "silver", (0, y, z))
    beam("frame", p, (0, 0.55, 0.04), (0, -0.20, 0.82), 0.08, "silver"); beam("frame_b", p, (0, -0.55, 0.04), (0, -0.20, 0.82), 0.07, "silver")
    pad("hip_pad", p, (0.32, 0.36, 0.10), (0, -0.20, 0.90), (-30, 0, 0)); pad("ankle_pad", p, (0.32, 0.30, 0.10), (0, 0.40, 0.36), (-30, 0, 0))
    for s in (-1, 1): rod("roller", p, (s * 0.12, 0.52, 0.28), (s * 0.12, 0.60, 0.40), 0.05, "pad")
    return p


def pec_deck():
    p = part("pec_deck"); _base(p, -0.55, 0.9); stack_tower(p, 0, 0.80, 0.48, 0.40, 1.5, 0.07)
    _seat_unit(p, 0.15)
    beam("hub", p, (0, 0.05, 1.20), (0, 0.05, 1.70), 0.12, "silver")
    for s in (-1, 1):
        beam("top_arm", p, (s * 0.05, 0.05, 1.62), (s * 0.30, -0.05, 1.62), 0.07, "silver")
        beam("arm", p, (s * 0.30, -0.05, 1.62), (s * 0.45, -0.20, 0.90), 0.07, "silver")
        pad("pad", p, (0.10, 0.14, 0.46), (s * 0.45, -0.20, 1.05)); rod("grip", p, (s * 0.45, -0.28, 0.82), (s * 0.45, -0.40, 0.82), 0.025, "grip")
    return p


def leg_extension():
    p = part("leg_extension"); _base(p, -0.70, 0.95); stack_tower(p, 0, 0.82, 0.46, 0.38, 1.35, 0.07)
    pad("seat", p, (0.42, 0.46, 0.10), (0, 0.0, 0.46)); beam("seat_post", p, (0, 0.0, 0.40), (0, 0.0, 0.06), 0.10, "silver")
    pad("back", p, (0.42, 0.10, 0.60), (0, 0.30, 0.82), (-14, 0, 0)); beam("back_post", p, (0, 0.34, 0.5), (0, 0.40, 1.0), 0.08, "silver")
    lv = part("leg_lever"); lv.parent = p; lv.location = (0, -0.20, 0.34)
    for s in (-1, 1):
        beam("arm", lv, (s * 0.24, 0.05, 0.0), (s * 0.24, -0.32, -0.04), 0.06, "silver"); cyl("cam", lv, 0.14, 0.05, "X", "silver", (s * 0.30, 0.05, 0.0), 10)
    cyl("roller", lv, 0.06, 0.42, "X", "pad", (0, -0.34, -0.04), 8)
    return p


def dip_machine():
    p = part("dip_machine"); _base(p, -0.60, 0.9); stack_tower(p, 0, 0.80, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.18)
    for s in (-1, 1):
        beam("arm", p, (s * 0.30, 0.10, 1.05), (s * 0.36, -0.30, 0.78), 0.07, "silver")
        rod("grip", p, (s * 0.36, -0.30, 0.78), (s * 0.36, -0.45, 0.78), 0.025, "grip")
    beam("footbar_stem",p,(0,-.30,.075),(0,-.30,.218),.032,"silver")
    _dial(p,.385,.12,1.05,.084)
    for side in (-1,1):
        beam("dip_mount",p,(0,.31,.65),(side*.30,.10,1.05),.039,"silver")
    box("foot_bar", p, (0.55, 0.08, 0.06), "silver", (0, -0.30, 0.22))
    _hinge(p,(0,.10,1.05),("arm","grip"),0,29)
    return p


BUILD2 = [("lateral_raise_machine", lateral_raise_machine), ("shoulder_press_machine", shoulder_press_machine), ("shrug_machine", shrug_machine),
          ("tbar_row_machine", tbar_row_machine), ("pullover_machine", pullover_machine), ("dip_machine", dip_machine),
          ("assisted_pullup", assisted_pullup), ("preacher_machine", preacher_machine), ("leg_press_horizontal", leg_press_horizontal),
          ("pendulum_squat", pendulum_squat), ("belt_squat", belt_squat), ("seated_leg_curl", seated_leg_curl),
          ("lying_leg_curl", lying_leg_curl), ("standing_leg_curl", standing_leg_curl), ("hip_abductor", hip_abductor),
          ("hip_thrust_machine", hip_thrust_machine), ("standing_calf", standing_calf), ("seated_calf", seated_calf),
          ("glute_kickback_machine", glute_kickback_machine), ("high_pulley", high_pulley), ("functional_trainer", functional_trainer),
          ("decline_sit_up", decline_sit_up), ("inverted_row_bar", inverted_row_bar), ("plyo_box", plyo_box), ("ab_wheel", ab_wheel),
          ("nordic_pad", nordic_pad), ("exercise_mat", exercise_mat), ("landmine", landmine), ("trap_bar", trap_bar),
          ("kettlebell", kettlebell), ("weight_plate", weight_plate)]


def build_all_machines(cols=6, dx=2.7, dy=3.6):
    """Everything (batch 1 + batch 2 + the free-weight kit) laid out in a grid for a showcase."""
    import equipment_kit as K, equipment_machines as M
    M.bpy_col()
    items = [(n, f) for n, f in K.BUILD] + M.BUILD + BUILD2
    over = {'hyperextension': hyperextension, 'pec_deck': pec_deck, 'leg_extension': leg_extension}
    try:
        import machine_rig; over.update(machine_rig.OVERRIDE)
    except ImportError:
        pass
    items = [(n, over.get(n, f)) for n, f in items]
    out = {}
    for i, (n, f) in enumerate(items):
        e = f(); out[n] = e; e.location = ((i % cols) * dx, -(i // cols) * dy, 0)
    return out


def organise_collections():
    """One sub-collection `M_<name>` per machine under `Kit`, so each can be shown/hidden (eye) or isolated (ctrl+click the eye)."""
    import bpy
    kit = bpy.data.collections["Kit"]
    tops = [o for o in kit.objects if o.type == "EMPTY" and o.parent is None]
    for t in tops:
        col = bpy.data.collections.new("M_" + t.name[2:]); kit.children.link(col)
        for o in [t] + list(t.children_recursive):
            for c in list(o.users_collection): c.objects.unlink(o)
            col.objects.link(o); o.hide_render = False; o.hide_viewport = False
    return len(tops)
