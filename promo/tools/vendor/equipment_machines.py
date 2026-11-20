"""Photo-referenced low-poly machines (design/equipment-reference). Same conventions as equipment_kit: metres, +Z up,
the lifter faces -Y, each machine is an empty P_<name> whose origin is on the floor under the seat/centre.
exec() after equipment_kit; build_machines() lays them out in a row for a showcase."""
import math
from mathutils import Vector
import equipment_kit as K
from equipment_kit import cyl, box, part, _obj
import bmesh

K.COL.update({"silver": (0.055, 0.060, 0.068, 1), "stack": (0.024, 0.027, 0.032, 1), "red": (0.72, 0.04, 0.05, 1),
              "wood": (0.45, 0.28, 0.14, 1), "frame": (0.68, 0.035, 0.040, 1), "pad": (0.022, 0.024, 0.028, 1), "plate": (0.018, 0.019, 0.023, 1),
              "grip": (0.014, 0.015, 0.018, 1), "accent": (0.95, 0.72, 0.04, 1)})
THICK = 1.55   # photo machines are built from fat tube; thin beams read as scaffolding


def beam(name, p, a, b, s=0.06, mat="frame", s2=None):
    """Beveled structural square tube from point a to point b."""
    a, b = Vector(a), Vector(b); d = b - a
    if d.length < 1e-4:
        return None
    s = s * THICK; s2 = s if s2 is None else s2 * THICK
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((d.length, s, s2)), verts=bm.verts)
    ob = _obj(name, bm, p, mat, tuple((a + b) / 2))
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = d.to_track_quat("X", "Z")
    K._add_bevel(ob, min(0.010, min(s, s2) * 0.24), segments=2)
    return ob


def rod(name, p, a, b, r=0.016, mat="steel", sides=20):
    a, b = Vector(a), Vector(b); d = b - a
    if d.length < 1e-4:
        return None
    seg = max(sides, 20)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d.length)
    ob = _obj(name, bm, p, mat, tuple((a + b) / 2))
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = d.to_track_quat("Z", "Y")
    return K._smooth_cyl(ob)


def pad(name, p, size, loc, rot=(0, 0, 0), mat="pad"):
    """Loft a tapered cushion with a recessed welt around its edge."""
    thin = min(range(3), key=size.__getitem__)
    wide, long = [i for i in range(3) if i != thin]
    bm = bmesh.new()
    rings = []
    for depth, fullness in ((-.50,.89),(-.35,.98),(-.18,.99),(-.12,.965),
                            (-.05,1.0),(.27,.985),(.46,.92),(.50,.77)):
        ring = []
        for i in range(24):
            t = math.tau*i/24
            u, v = math.cos(t), math.sin(t)
            u = math.copysign(abs(u)**.40, u)
            v = math.copysign(abs(v)**.40, v)
            co = [0,0,0]
            co[wide] = .5*size[wide]*u*fullness*(1-.10*max(0,v))
            co[long] = .5*size[long]*v*fullness
            co[thin] = max(.085,size[thin])*depth
            ring.append(bm.verts.new(co))
        if rings:
            for i in range(24):
                j = (i+1)%24
                bm.faces.new((rings[-1][i],rings[-1][j],ring[j],ring[i]))
        rings.append(ring)
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    ob = _obj(name,bm,p,mat,loc,rot)
    for face in ob.data.polygons:
        face.use_smooth = len(face.vertices)==4
    return ob


def _label(p, body, loc, height, rotation=(90,0,0)):
    import bpy
    font = bpy.data.curves.new("Equipment print", "FONT")
    font.body, font.size, font.align_x = body, height, "CENTER"
    font.resolution_u = 2
    ob = bpy.data.objects.new("Equipment print", font)
    bpy.data.collections["Kit"].objects.link(ob)
    ob.parent, ob.location = p, loc
    ob.rotation_euler = tuple(math.radians(a) for a in rotation)
    font.materials.append(K.mat("steel"))


def _dial(p,x,y,z,r=.095):
    cyl("range_sector",p,r,.028,"X","silver",(x,y,z))
    cyl("bearing",p,r*.44,.038,"X","steel",(x,y,z))
    for i in (0,1,3,4,5):
        t = math.radians(30+25*i)
        cyl("range_index",p,.008,.006,"X","accent" if i==2 else "steel",
            (x+.016,y+r*.72*math.cos(t),z+r*.72*math.sin(t)))
    cyl("pop_pin",p,.017,.034,"X","accent",(x+.028,y+r*.72*math.cos(math.radians(80)),z+r*.72*math.sin(math.radians(80))))


def _seat_lever(p,y,z):
    rod("seat_release",p,(0,y,z),(.16,y-.035,z+.014),.009,"steel")
    rod("yellow_paddle",p,(.13,y-.03,z+.012),(.19,y-.047,z+.019),.017,"accent")


def _drive(p, hub, tower_y, top):
    x,y,z = hub
    cyl("drive_cam",p,.082,.042,"X","silver",hub)
    pivot_hub("axle",p,hub,.043,.055)
    # Outer tangent runs along the back of the press to the stack return sheave.
    rod("drive_cable",p,(x,y+.02,z+.078),(x,tower_y,top+.045),.005,"grip")
    cyl("return_sheave",p,.048,.026,"X","silver",(x,tower_y,top))
    rod("cable_return",p,(x,tower_y+.047,top),(x,tower_y+.047,top-.35),.005,"grip")
    beam("sheave_mount",p,(0,tower_y,top-.045),(x,tower_y,top),.024,"silver")


def _trolley(p,x,z):
    rod("guide",p,(x,-.115,.22),(x,-.115,2.24),.015)
    box("slider",p,(.105,.11,.15),"silver",(x,-.118,z))
    cyl("swivel",p,.05,.055,"X","steel",(x,-.17,z))
    cyl("lock_pin",p,.018,.040,"X","accent",(x+.059,-.119,z))
    for height in (.42,.67,.92,1.17,1.42,1.67,1.92):
        cyl("index",p,.008,.012,"Y","grip",(x,-.128,height))
    rod("wire",p,(x,-.176,z),(x,-.176,2.22),.004,"grip")
    for side in (-1,1):
        rod("stirrup",p,(x,-.19,z),(x+side*.073,-.23,z-.13),.009)
    grip_handle("stirrup_grip",p,(x-.073,-.23,z-.13),(x+.073,-.23,z-.13),.016)


def pivot_hub(name, p, loc, r=0.052, width=0.06, axis="X"):
    """Machined chrome/charcoal bearing housing at machine pivot joints."""
    cyl(name + "_body", p, r, width, axis, "silver", loc, sides=24)
    cyl(name + "_cap", p, r * 0.62, width + 0.016, axis, "steel", loc, sides=24)


def grip_handle(name, p, a, b, r=0.022):
    """Rubberized ergonomic handle with chrome end-caps."""
    a, b = Vector(a), Vector(b); d = b - a
    if d.length < 1e-4:
        return
    u = d.normalized()
    rod(name, p, a, b, r, "grip", sides=20)
    rod(name + "_cap1", p, a - u * 0.008, a + u * 0.010, r * 1.12, "steel", sides=20)
    rod(name + "_cap2", p, b - u * 0.010, b + u * 0.008, r * 1.12, "steel", sides=20)


def stack_tower(p, x, y, w=0.46, d=0.40, h=1.55, z0=0.05, mat="silver"):
    """Commercial selectorised weight stack: beveled shroud, twin chrome guide rods, 14 plates, T-pin & top pulley."""
    # Base plinth + rubber feet
    box("housing", p, (w + 0.02, d + 0.02, 0.055), mat, (x, y, z0 + 0.027), bevel=0.008)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl("tower_foot", p, 0.032, z0+.008, "Z", "grip",
                (x + sx * (w * 0.42), y + sy * (d * 0.40), (z0+.008)/2), sides=16)
    # Beveled side shrouds & back panel
    for s in (-1, 1):
        box("hside", p, (0.038, d, h), mat, (x + s * (w / 2 - 0.019), y, z0 + h / 2), bevel=0.010)
    # The camera sees the service side. Leave a vented inspection well
    # between its tapered shoulders, with the moving stack visible inside.
    rear = y+d/2-.016
    for side in (-1,1):
        box("rear_shoulder",p,(w*.205,.033,h-.032),mat,
            (x+side*w*.303,rear,z0+h*.50),bevel=.012)
    for frac, height in ((.105,.21),(.876,.248)):
        box("service_panel",p,(w*.43,.032,h*height),mat,
            (x,rear-.006,z0+h*frac),bevel=.009)
    for frac in (.28,.36,.44,.52,.60,.68,.74):
        box("vent_louver",p,(w*.425,.028,.044),"silver",
            (x,rear-.010,z0+h*frac),(-18,0,0),bevel=.004)
    _label(p,"WATCHCOACH",(x,rear+.013,z0+h*.865),w*.061,(90,0,180))
    box("service_flash",p,(w*.19,.007,.012),"accent",(x,rear+.012,z0+h*.835))
    # Twin front shroud wings leaving a clean vertical selector slot in the middle
    wing_w = w * 0.24
    for s in (-1, 1):
        box("hfront_wing", p, (wing_w, 0.024, h * 0.86), "grip",
            (x + s * (w / 2 - wing_w / 2 - 0.02), y - d / 2 + 0.014, z0 + h * 0.44), bevel=0.005)
    # Molded top cap + angled instructional placard
    box("hcap", p, (w + 0.02, d + 0.02, 0.065), mat, (x, y, z0 + h), bevel=0.014)
    box("cover", p, (w + 0.01, 0.035, h * 0.22), mat, (x, y - d / 2 - 0.006, z0 + h * 0.89), bevel=0.008)
    face = y - d/2 - .033
    label_z = z0+h*.90
    box("placard",p,(w*.82,.018,.135),"grip",(x,face,label_z))
    _label(p,p.name.removeprefix("P_").split(".")[0].replace("_machine","").replace("_"," ").upper(),
           (x,face-.011,label_z+.025),min(.027,w*.10))
    _label(p,"SET SEAT   /   SELECT LOAD",(x,face-.011,label_z-.025),min(.014,w*.055))
    # Twin chrome vertical guide rods
    for s in (-1, 1):
        rod("guide_rod", p, (x + s * (w * 0.26), y, z0 + 0.05), (x + s * (w * 0.26), y, z0 + h - 0.03), 0.011, "steel", sides=16)
    # 14 beveled weight plates with clean separation gaps + front weight sticker accents
    n = 14
    plate_h = 0.068
    pitch = 0.078
    for i in range(n):
        pz = z0 + 0.10 + i * pitch
        if pz > z0 + h - 0.18:
            break
        box("slab", p, (w - 0.11, d - 0.11, plate_h), "stack", (x, y, pz), bevel=0.005)
        if i % 2 == 0:
            _label(p,str((i+1)*5),(x+w*.105,y-(d-.11)/2-.0018,pz-.009),.025)
    # Yellow T-handle selector pin inserted into plate #5
    pin_z = z0 + 0.10 + 4 * pitch
    rod("pin_shaft", p, (x, y - d / 2 - 0.045, pin_z), (x, y + 0.05, pin_z), 0.007, "steel", sides=16)
    cyl("pin", p, 0.022, 0.038, "Y", "accent", (x, y - d / 2 - 0.050, pin_z), sides=20)
    # Top pulley wheel & vertical steel cable
    cyl("top_pulley", p, 0.062, 0.028, "X", "steel", (x, y - 0.04, z0 + h + 0.055), sides=24)
    rod("stack_cable", p, (x, y, z0 + 0.10 + (n - 2) * pitch), (x, y, z0 + h + 0.055), 0.0045, "grip", sides=12)


def floor_feet(p, w, d, y0=0.0, mat="frame", s=0.07):
    for sx in (-1, 1):
        beam("foot", p, (sx * w / 2, y0 - d / 2, s / 2), (sx * w / 2, y0 + d / 2, s / 2), s, mat, s)


# ---------------------------------------------------------------- free-weight stations
def power_rack():
    """Four-post power rack: top frame, J-hooks, safety bars, plate pegs, pull-up bar."""
    p = part("power_rack"); W, D, H = 1.25, 1.10, 2.30
    for sx in (-1, 1):
        for sy in (-1, 1):
            beam("post", p, (sx * W / 2, sy * D / 2, 0), (sx * W / 2, sy * D / 2, H), 0.07, "frame")
        beam("side_top", p, (sx * W / 2, -D / 2, H), (sx * W / 2, D / 2, H), 0.07)
        beam("base", p, (sx * W / 2, -D / 2 - 0.35, 0.035), (sx * W / 2, D / 2 + 0.25, 0.035), 0.074, "frame", 0.07)
        beam("brace", p, (sx * W / 2, -D / 2, 0.35), (sx * W / 2, D / 2, 1.15), 0.04)
        x = sx * W/2
        box("cup_back",p,(.085,.045,.15),"silver",(x,-D/2-.066,1.40))
        box("cup_cradle",p,(.079,.091,.022),"grip",(x,-D/2-.091,1.35))
        box("cup_lip",p,(.083,.021,.046),"silver",(x,-D/2-.132,1.36))
        beam("safety",p,(x,-D/2,.62),(x,D/2,.62),.036,"silver")
        for i in range(10):
            cyl("rack_index",p,.010,.005,"Y","grip",(x,-D/2-.055,.46+i*.16))
        grip_handle("neutral_pull",p,(x*.57,-D/2,H-.035),(x*.55,-D/2-.22,H-.05),.017)
    beam("front_top", p, (-W / 2, -D / 2, H), (W / 2, -D / 2, H), 0.07)
    beam("back_top", p, (-W / 2, D / 2, H), (W / 2, D / 2, H), 0.07)
    rod("pullup", p, (-W / 2, -D / 2 - 0.22, H - 0.05), (W / 2, -D / 2 - 0.22, H - 0.05), 0.017)
    for sx in (-1, 1): beam("pu_arm", p, (sx * W / 2, -D / 2, H - 0.05), (sx * W / 2, -D / 2 - 0.22, H - 0.05), 0.05)
    for sx in (-1, 1):
        for z in (0.5, 1.0): cyl("peg", p, 0.025, 0.22, "Y", "steel", (sx * (W / 2 + 0.05), D / 2 + 0.08, z), 6)
    return p


def smith_machine():
    """Smith: guide-rod uprights with long feet, top beam, counter-balanced bar with hooks, plate pegs, safety catches."""
    p = part("smith_machine"); H = 2.25
    for s in (-1, 1):
        beam("post", p, (s * 0.72, 0, 0), (s * 0.72, 0, H), 0.09)
        rod("rail", p, (s * 0.72, -0.07, 0.10), (s * 0.72, -0.07, H - 0.05), 0.016)
        beam("foot", p, (s * 0.72, -0.55, 0.04), (s * 0.72, 0.55, 0.04), 0.09, "frame", 0.08)
        beam("brace", p, (s * 0.72, 0.5, 0.06), (s * 0.72, 0.03, H - 0.4), 0.05)
        for i in range(8): box("catch", p, (0.05, 0.09, 0.03), "accent" if i == 1 else "steel", (s * 0.72, -0.08, 0.30 + i * 0.22))
        for z in (0.55, 1.0, 1.45): cyl("peg", p, 0.022, 0.25, "Y", "steel", (s * 0.72, 0.18, z), 6)
    beam("top", p, (-0.72, 0, H), (0.72, 0, H), 0.09)
    sb = part("smith_bar"); sb.parent = p; sb.location = (0, -0.10, 1.30)
    cyl("bar", sb, 0.016, 2.0, "X", "steel", sides=8)
    for s in (-1, 1):
        cyl("linear_sleeve",sb,.040,.18,"Z","silver",(s*.72,.03,0))
        for z in (-.088,.088):
            cyl("wiper",sb,.042,.014,"Z","grip",(s*.72,.03,z))
        rod("safety_hook",sb,(s*.72,.03,0),(s*.68,.062,.071),.015)
        rod("hook_return",sb,(s*.68,.062,.071),(s*.68,.096,.052),.014)
        for i, r in enumerate((0.2, 0.2)): cyl("plate", sb, r, 0.03, "X", "plate", (s * (0.90 + i * 0.04), 0, 0), 12)

    return p


# ---------------------------------------------------------------- benches
def _bench_transport(p,front,rear):
    for side in (-1,1):
        cyl("transport_wheel",p,.043,.026,"X","grip",(side*.17,rear,.047))
        cyl("axle_cap",p,.016,.034,"X","steel",(side*.17,rear,.047))
        rod("lift_bracket",p,(side*.078,front,.04),(side*.078,front-.045,.12),.012)
    grip_handle("lift_grip",p,(-.078,front-.045,.12),(.078,front-.045,.12),.016)


def flat_bench():
    p = part("flat_bench")
    _bench_transport(p,-.55,.55)
    pad("seat",p,(.30,.36,.085),(0,-.42,.43))
    pad("back",p,(.30,.828,.085),(0,.186,.43))
    box("trim", p, (0.28, 1.18, 0.03), "grip", (0, 0, 0.39))
    for s in (-1, 1):
        beam("leg", p, (0, s * 0.50, 0.38), (0, s * 0.56, 0.02), 0.07)
        box("foot", p, (0.46, 0.06, 0.04), "frame", (0, s * 0.56, 0.02))
    beam("spine", p, (0, -0.5, 0.36), (0, 0.5, 0.36), 0.06)
    return p


def adjustable_bench(angle=45):
    """Back pad hinged at the seat rear (child P_adj_back, rotation_euler.x = -angle)."""
    p = part("adjustable_bench")
    pad("seat", p, (0.30, 0.38, 0.08), (0, -0.10, 0.45)); box("seat_trim", p, (0.28, 0.36, 0.03), "grip", (0, -0.10, 0.405))
    beam("spine", p, (0, -0.28, 0.33), (0, 0.55, 0.33), 0.063)
    beam("leg_f", p, (0, -0.22, 0.40), (0, -0.28, 0.02), 0.07); box("foot_f", p, (0.50, 0.06, 0.04), "frame", (0, -0.28, 0.02))
    beam("leg_b", p, (0, 0.45, 0.33), (0, 0.55, 0.02), 0.07); box("foot_b", p, (0.50, 0.06, 0.04), "frame", (0, 0.55, 0.02))
    for side in (-1,1):
        beam("ladder_rail",p,(side*.061,.12,.34),(side*.061,.45,.62),.018,"silver")
    for i in range(6):
        cyl("ladder_rung",p,.013,.13,"X","steel",(0,.135+i*.06,.353+i*.051))
    _bench_transport(p,-.28,.55)
    pv = part("adj_back"); pv.parent = p; pv.location = (0, 0.12, 0.47)
    pad("back", pv, (0.30, 0.78, 0.08), (0, 0.39, 0)); box("back_trim", pv, (0.28, 0.76, 0.03), "grip", (0, 0.39, -0.045))
    beam("back_frame", pv, (0, 0.05, -0.07), (0, 0.72, -0.07), 0.06)
    pv.rotation_euler.x = -math.radians(angle)
    theta = pv.rotation_euler.x
    beam("locking_stay",p,(0,.255,.455),(0,.12+.22*math.cos(theta)+.07*math.sin(theta),
         .47+.22*math.sin(theta)-.07*math.cos(theta)),.027,"silver")
    return p


def decline_bench():
    p = part("decline_bench")
    pad("seat", p, (0.30, 0.38, 0.08), (0, -0.28, 0.58), (-12, 0, 0)); pad("back", p, (0.30, 0.90, 0.08), (0, 0.38, 0.46), (-12, 0, 0))
    beam("spine", p, (0, -0.4, 0.45), (0, 0.75, 0.30), 0.07)
    beam("leg_f", p, (0, -0.36, 0.52), (0, -0.40, 0.02), 0.08); box("foot_f", p, (0.55, 0.06, 0.04), "frame", (0, -0.40, 0.02))
    beam("leg_b", p, (0, 0.75, 0.30), (0, 0.80, 0.02), 0.07); box("foot_b", p, (0.50, 0.06, 0.04), "frame", (0, 0.80, 0.02))
    beam("roller_arm", p, (0, -0.40, 0.55), (0, -0.62, 0.62), 0.05)
    for z in (0.60, 0.74): cyl("roller", p, 0.055, 0.40, "X", "pad", (0, -0.66, z), 8)
    return p


def preacher_bench():
    p = part("preacher_bench")
    pad("seat", p, (0.34, 0.30, 0.08), (0, 0.22, 0.46))
    pad("arm_pad", p, (0.40, 0.55, 0.08), (0, -0.20, 0.82), (-38, 0, 0))
    beam("post", p, (0, 0.2, 0.40), (0, 0.2, 0.02), 0.07); box("foot_b", p, (0.55, 0.06, 0.04), "frame", (0, 0.2, 0.02))
    beam("arm_post", p, (0, -0.05, 0.75), (0, -0.30, 0.05), 0.07); box("foot_f", p, (0.55, 0.06, 0.04), "frame", (0, -0.30, 0.02))
    beam("link", p, (0, -0.05, 0.60), (0, 0.2, 0.40), 0.05)
    return p


# ---------------------------------------------------------------- cable stations
def cable_crossover():
    """Two stack towers joined by a top beam; adjustable pulley carriages on slotted uprights."""
    p = part("cable_crossover"); W = 2.1; H = 2.3
    for s in (-1, 1):
        beam("post", p, (s * W / 2, 0, 0), (s * W / 2, 0, H), 0.12, "silver", 0.10)
        beam("post_b", p, (s * W / 2, 0.30, 0), (s * W / 2, 0.30, H * 0.78), 0.10, "silver", 0.10)
        beam("link", p, (s * W / 2, 0, H * 0.78), (s * W / 2, 0.30, H * 0.78), 0.084, "silver")
        stack_tower(p, s * W / 2, 0.58, 0.40, 0.34, 1.25, 0.05)
        beam("foot", p, (s * W / 2, -0.30, 0.04), (s * W / 2, 0.80, 0.04), 0.106, "frame", 0.083)
        _trolley(p,s*W/2,1.45)
    beam("top", p, (-W / 2, 0, H), (W / 2, 0, H), 0.12, "silver", 0.10)
    return p


def lat_pulldown():
    p = part("lat_pulldown"); H = 2.20
    stack_tower(p, 0, 0.58, 0.46, 0.38, 1.3, 0.05)
    beam("mast", p, (0, 0.20, 0), (0, 0.20, H), 0.12, "silver", 0.10)
    beam("arm", p, (0, 0.20, H), (0, -0.55, H - 0.05), 0.10, "silver", 0.08)
    cyl("pulley", p, 0.08, 0.05, "X", "accent", (0, -0.45, H - 0.12), 10)
    box("seat", p, (0.36, 0.34, 0.08), "pad", (0, -0.18, 0.46)); beam("seat_post", p, (0, -0.18, 0.42), (0, -0.18, 0.05), 0.08)
    beam("roller_stay",p,(0,-.18,.31),(0,-.53,.65),.032,"silver")
    for side in (-1,1):
        beam("front_foot",p,(side*.28,-.54,.049),(side*.28,-.77,.049),.044,"silver")
        cyl("thigh_roller",p,.066,.21,"X","pad",(side*.12,-.53,.66))
        cyl("roller_end",p,.046,.016,"X","steel",(side*.23,-.53,.66))
    rod("bar_cable",p,(0,-.45,1.86),(0,-.45,H-.12),.005,"grip")
    beam("base", p, (0, -0.55, 0.04), (0, 0.80, 0.04), 0.106, "frame", 0.083)
    box("foot", p, (0.80, 0.08, 0.06), "frame", (0, -0.55, 0.05))
    lb = part("lat_bar"); lb.parent = p; lb.location = (0, -0.45, H - 0.40)
    rod("bar", lb, (-0.55, 0, -0.02), (-0.30, 0, 0.06), 0.017, "steel"); rod("bar", lb, (-0.30, 0, 0.06), (0.30, 0, 0.06), 0.017, "steel")
    rod("bar", lb, (0.30, 0, 0.06), (0.55, 0, -0.02), 0.017, "steel")
    for side in (-1,1):
        grip_handle("outer_grip",lb,(side*.36,0,.041),(side*.54,0,-.017),.022)
    return p


def seated_cable_row():
    p = part("seated_cable_row")
    beam("base", p, (0, -0.65, 0.05), (0, 1.05, 0.05), 0.12, "silver", 0.08)
    stack_tower(p, 0, 0.95, 0.46, 0.38, 1.35, 0.08)
    pad("seat", p, (0.36, 0.34, 0.09), (0, 0.05, 0.42)); beam("seat_post", p, (0, 0.05, 0.38), (0, 0.05, 0.08), 0.08, "silver")
    pad("chest", p, (0.40, 0.10, 0.30), (0, -0.32, 0.78)); beam("chest_post", p, (0, -0.32, 0.60), (0, -0.40, 0.08), 0.08, "silver")
    beam("footboard_mount",p,(0,-.60,.06),(0,-.62,.20),.043,"silver")
    box("foot_plate", p, (0.50, 0.30, 0.04), "silver", (0, -0.62, 0.20), (35, 0, 0))
    h = part("row_handle"); h.parent = p; h.location = (0, -0.20, 0.82)
    for side in (-1,1):
        rod("v_handle",h,(0,-.18,.04),(side*.12,-.12,0),.014)
        grip_handle("row_grip",h,(side*.12,-.12,0),(side*.12,.02,0),.020)
    rod("low_cable",p,(0,-.38,.86),(0,-.55,.29),.005,"grip")
    for i in range(-2,3):
        t=i*.047
        box("foot_rib",p,(.47,.012,.008),"grip",(0,-.634+t*.819,.221+t*.574),(35,0,0))
    return p


# ---------------------------------------------------------------- selectorised / plate-loaded machines
def _seat_unit(p, back_y=0.20):
    pad("seat", p, (0.42, 0.40, 0.09), (0, back_y - 0.20, 0.45))
    beam("seat_post", p, (0, back_y - 0.2, 0.30), (0, back_y - 0.2, 0.06), 0.07, "silver")
    rod("seat_slide", p, (0, back_y - 0.2, 0.20), (0, back_y - 0.2, 0.44), 0.024, "steel")
    cyl("seat_pop_pin", p, 0.018, 0.045, "Y", "accent", (0, back_y - 0.260, 0.285), sides=16)
    _seat_lever(p,back_y-.20,.33)
    pad("lumbar",p,(.38,.105,.22),(0,back_y-.028,.619),(-8,0,0))
    pad("back",p,(.42,.10,.39),(0,back_y+.017,.937),(-8,0,0))
    beam("back_post", p, (0, back_y + 0.06, 0.44), (0, back_y + 0.11, 1.12), 0.065, "silver")
    cyl("back_pop_pin", p, 0.016, 0.04, "X", "accent", (0.06, back_y + 0.08, 0.60), sides=16)


def chest_press_machine():
    p = part("chest_press_machine")
    beam("base", p, (0, -0.85, 0.05), (0, 1.0, 0.05), 0.12, "silver", 0.07)
    for s in (-1, 1):
        beam("footbar", p, (s * 0.40, -0.85, 0.05), (s * 0.40, 0.4, 0.05), 0.06, "silver")
    stack_tower(p, 0, 0.82, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.15)
    _drive(p,(.32,.20,.95),.82,1.50)
    # Foot assist pedal & overhead pivot bridge
    beam("pedal_stem",p,(0,-.51,.07),(0,-.58,.16),.023,"silver")
    beam("base_cross",p,(-.40,.20,.065),(.40,.20,.065),.044,"silver")
    rod("foot_pedal", p, (-0.28, -0.58, 0.16), (0.28, -0.58, 0.16), 0.018, "steel")
    beam("pivot_bridge", p, (-0.34, 0.20, 0.56), (0.34, 0.20, 0.56), 0.05, "silver")
    for s in (-1, 1):
        beam("lever_knuckle",p,(s*.32,.20,.95),(s*.41,-.065,1.035),.040,"frame")
        beam("press_forearm",p,(s*.41,-.065,1.035),(s*.40,-.30,.95),.039,"frame")
        beam("pivot_arm", p, (s * 0.32, 0.20, 0.95), (s * 0.32, 0.20, 0.55), 0.05, "silver")
        if s < 0:
            pivot_hub("press_hub", p, (s * 0.32, 0.20, 0.95), r=0.052, width=0.07, axis="X")
        # Dual horizontal + neutral press handles
        grip_handle("handle", p, (s * 0.40, -0.30, 0.95), (s * 0.40, -0.46, 0.95), 0.022)
        grip_handle("handle_v", p, (s * 0.40, -0.32, 0.86), (s * 0.40, -0.32, 1.04), 0.020)
    return p


def pec_deck():
    p = part("pec_deck")
    beam("base", p, (0, -0.45, 0.05), (0, 0.9, 0.05), 0.12, "silver", 0.07)
    stack_tower(p, 0, 0.78, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.15)
    beam("overhead_spine",p,(0,.76,1.42),(0,.03,1.46),.065,"silver")
    for s in (-1,1):
        x = s*.19
        beam("crosshead",p,(0,.03,1.46),(x,.03,1.46),.045,"silver")
        pivot_hub("fly_hinge",p,(x,.03,1.47),.068,.068,"Z")
        rod("fly_cable",p,(x,.04,1.50),(s*.11,.76,1.53),.005,"grip")
        beam("swing_arm",p,(x,.03,1.43),(s*.40,-.19,1.38),.038,"frame")
        beam("arm_drop",p,(s*.40,-.19,1.38),(s*.40,-.28,.82),.039,"silver")
        grip_handle("fly_outer",p,(s*.40,-.28,.85),(s*.34,-.34,.85),.018)
        pad("pad", p, (0.10, 0.12, 0.34), (s * 0.40, -0.28, 0.98))
        grip_handle("pec_grip", p, (s * 0.40, -0.28, 0.74), (s * 0.40, -0.28, 0.88), 0.020)
    return p


def leg_extension():
    p = part("leg_extension")
    beam("base", p, (0, -0.65, 0.05), (0, 0.95, 0.05), 0.12, "silver", 0.07)
    stack_tower(p, 0, 0.80, 0.46, 0.38, 1.35, 0.07)
    pad("seat", p, (0.42, 0.44, 0.09), (0, 0.0, 0.44))
    beam("seat_post", p, (0, 0.0, 0.40), (0, 0.0, 0.06), 0.075, "silver")
    pad("back", p, (0.42, 0.10, 0.50), (0, 0.28, 0.76), (-12, 0, 0))
    beam("back_post", p, (0, 0.34, 0.5), (0, 0.38, 0.9), 0.06, "silver")
    for s in (-1, 1):
        grip_handle("side_grip", p, (s * 0.27, -0.14, 0.44), (s * 0.27, 0.06, 0.44), 0.020)
    lv = part("leg_lever"); lv.parent = p; lv.location = (0, -0.25, 0.30)
    pivot_hub("leg_pivot", lv, (0.22, 0, 0), r=0.058, width=0.06, axis="X")
    _dial(lv,.246,0,0,.11)
    for s in (-1, 1):
        beam("arm", lv, (s * 0.20, 0, 0), (s * 0.20, -0.30, -0.02), 0.045, "silver")
    cyl("roller", lv, 0.062, 0.42, "X", "pad", (0, -0.32, -0.02), sides=24)
    cyl("roller_cap_l", lv, 0.045, 0.016, "X", "steel", (-0.215, -0.32, -0.02), sides=20)
    cyl("roller_cap_r", lv, 0.045, 0.016, "X", "steel", (0.215, -0.32, -0.02), sides=20)
    beam("cam", p, (0.2, -0.25, 0.30), (0.2, 0.45, 0.50), 0.035, "silver")
    return p


def leg_press_45():
    """Twin 45-degree guide rods with a captive sled and flip-up safety catches."""
    p = part("leg_press_45")
    sl = part("sled")
    sl.parent, sl.location = p,(0,-.60,.62)
    for side in (-1,1):
        x=side*.40
        beam("base_runner",p,(x,-1.30,.055),(x,.90,.055),.073,"silver")
        beam("rear_stay",p,(x,-1.25,.09),(x,-1.04,1.06),.066)
        beam("incline_stringer",p,(x,.18,.10),(x,-1.04,.99),.053,"silver")
        rod("chrome_guide",p,(x,-.10,.12),(x,-1.04,1.06),.028)
        for y,z in ((-.10,.12),(-1.04,1.06)):
            box("guide_socket",p,(.112,.095,.10),"frame",(x,y,z),(45,0,0))
        rod("linear_bearing",sl,(x,.093,-.093),(x,-.093,.093),.049,"silver")
        rod("dust_seal",sl,(x,-.096,.096),(x,-.11,.11),.05,"grip")
        beam("seat_cradle",p,(x,.76,.10),(side*.16,.71,.43),.045,"silver")
        rod("release_shaft",p,(x,-.46,.37),(x,.39,.39),.014)
        rod("lock_handle",p,(x,.39,.39),(x,.32,.54),.016)
        grip_handle("safety_grip",p,(x,.32,.54),(x,.17,.54),.02)
        rod("side_grip_mount",p,(x,.58,.10),(side*.29,.58,.29),.022)
        grip_handle("side_grip",p,(side*.29,.58,.29),(side*.29,.42,.29),.02)
        cyl("load_horn",sl,.025,.37,"X","steel",(side*.565,0,0))
        cyl("rubber_stop",sl,.063,.037,"X","grip",(side*.474,0,0))
        for i in range(2):
            K._plate(sl,.205,.043,(side*(.518+i*.052),0,0),grips=True)
    for y in (-1.15,.62):
        beam("cross_member",p,(-.4,y,.08),(.4,y,.08),.061,"silver")
    beam("seat_saddle",p,(0,.62,.083),(0,.62,.18),.12,"silver")
    beam("backbone",p,(0,.90,.15),(0,.67,.88),.070,"silver")
    pad("seat",p,(.46,.46,.10),(0,.62,.20))
    pad("back",p,(.46,.10,.51),(0,.805,.552),(30,0,0))
    pad("headrest",p,(.32,.105,.176),(0,.629,.851),(30,0,0))
    beam("sled_axle",sl,(-.43,0,0),(.43,0,0),.065,"silver")
    box("footplate",sl,(.91,.061,.61),"silver",(0,0,0),(45,0,0),.019)
    for i in range(-4,5):
        t=i*.059
        y=(.034-t)*math.sqrt(.5)
        z=(.034+t)*math.sqrt(.5)
        box("traction_rib",sl,(.82,.013,.019),"grip",(0,y,z),(45,0,0),.004)
    return p


def hack_squat():
    p = part("hack_squat")
    for s in (-1, 1):
        beam("rail", p, (s * 0.35, 0.80, 0.10), (s * 0.35, -0.35, 1.65), 0.07)
        beam("foot", p, (s * 0.45, -0.85, 0.04), (s * 0.45, 1.00, 0.04), 0.09, "frame", 0.08)
        beam("brace", p, (s * 0.45, -0.55, 0.04), (s * 0.35, 0.15, 1.15), 0.05)
    box("foot_plate", p, (0.60, 0.50, 0.04), "silver", (0, -0.58, 0.14), (-25, 0, 0))
    pad("back", p, (0.46, 0.10, 0.90), (0, 0.55, 0.78), (-30, 0, 0))
    for s in (-1, 1):
        pad("shoulder", p, (0.16, 0.14, 0.20), (s * 0.20, 0.38, 1.20), (-30, 0, 0))
        cyl("peg", p, 0.025, 0.35, "X", "steel", (s * 0.58, 0.60, 0.30), 6)
    return p


def plate_row():
    """Plate-loaded iso row / chest-supported row: low frame, chest pad on a post, two long handles on arms with plate pegs."""
    p = part("plate_row")
    for side in (-1, 1):
        x = side * .40
        beam("foot", p, (side*.55, -.40, .04), (side*.55, 1.0, .04), .10, "frame", .08)
        beam("bearing_support", p, (side*.55, .42, .09), (x, .30, .79), .045, "silver")
        pivot_hub("iso_bearing", p, (x, .30, .80), .079, .12)
        lever = part("row_lever_L" if side < 0 else "row_lever_R")
        lever.parent, lever.location = p, (x, .30, .80)
        beam("pull_arm", lever, (0, 0, 0), (0, -.70, -.25), .060)
        beam("load_arm", lever, (0, 0, 0), (side*.05, .55, -.30), .060)
        cyl("balance_slug", lever, .078, .085, "X", "silver", (side*.05, .47, -.26))
        grip_handle("wide_grip", lever, (0, -.70, -.25), (-side*.16, -.70, -.25), .019)
        grip_handle("neutral_grip", lever, (0, -.70, -.25), (0, -.85, -.10), .022)
        cyl("peg", lever, .025, .30, "X", "steel", (side*.18, .55, -.30))
        for i in range(2):
            K._plate(lever, .22, .033, (side*(.24+i*.041), .55, -.30), grips=True)
        box("footboard", p, (.19,.28,.034), "silver", (side*.37,-.19,.19), (25,0,0))
        beam("footrest_stay", p, (side*.52,-.14,.06), (side*.37,-.19,.17), .028, "silver")
    box("cross", p, (1.10, 0.10, 0.10), "frame", (0, 0.30, 0.78))
    pad("chest", p, (0.40, 0.10, 0.46), (0, 0.0, 0.95), (-15, 0, 0)); beam("post", p, (0, 0.05, 0.92), (0, 0.10, 0.04), 0.09)
    pad("seat", p, (0.40, 0.34, 0.09), (0, 0.50, 0.44)); beam("seat_post", p, (0, 0.5, 0.4), (0, 0.5, 0.05), 0.08)
    return p


def pullup_dip_tower():
    """Captain's chair / VKR tower: two uprights, back pad, forearm pads with grips, dip handles, pull-up bars."""
    p = part("pullup_dip_tower"); H = 2.35
    for s in (-1, 1):
        beam("post", p, (s * 0.38, 0.35, 0), (s * 0.38, 0.35, H), 0.08)
        beam("foot", p, (s * 0.38, -0.35, 0.04), (s * 0.38, 0.75, 0.04), 0.09, "frame", 0.08)
        beam("front", p, (s * 0.38, 0.35, 1.05), (s * 0.38, -0.20, 1.05), 0.06)
        pad("forearm", p, (0.10, 0.34, 0.06), (s * 0.38, -0.02, 1.12))
        rod("grip", p, (s * 0.38, -0.20, 1.12), (s * 0.38, -0.20, 1.28), 0.02, "grip")
        beam("pu_arm", p, (s * 0.38, 0.35, H), (s * 0.38, 0.0, H), 0.07)
        rod("dip", p, (s * 0.38, 0.12, 1.60), (s * 0.38, -0.22, 1.60), 0.02, "grip")
        beam("dip_post", p, (s * 0.38, 0.35, 1.60), (s * 0.38, 0.12, 1.60), 0.06)
    pad("back", p, (0.46, 0.08, 0.70), (0, 0.38, 1.35)); beam("back_bar", p, (-0.38, 0.35, 1.30), (0.38, 0.35, 1.30), 0.06)
    rod("pullup", p, (-0.48, 0.0, H), (0.48, 0.0, H), 0.017)
    return p


def hyperextension():
    p = part("hyperextension")
    beam("frame_f", p, (0, -0.35, 0.05), (0, -0.25, 0.85), 0.08); beam("frame_b", p, (0, 0.55, 0.05), (0, 0.35, 0.68), 0.08)
    box("foot_f", p, (0.60, 0.06, 0.04), "frame", (0, -0.35, 0.02)); box("foot_b", p, (0.60, 0.06, 0.04), "frame", (0, 0.55, 0.02))
    pad("hip_pad", p, (0.30, 0.34, 0.09), (0, -0.20, 0.90), (-20, 0, 0)); pad("ankle", p, (0.34, 0.12, 0.10), (0, 0.38, 0.72))
    beam("link", p, (0, -0.35, 0.40), (0, 0.45, 0.40), 0.05)
    return p


BUILD = [("power_rack", power_rack), ("smith_machine", smith_machine), ("flat_bench", flat_bench),
         ("adjustable_bench", adjustable_bench), ("decline_bench", decline_bench), ("preacher_bench", preacher_bench),
         ("cable_crossover", cable_crossover), ("lat_pulldown", lat_pulldown), ("seated_cable_row", seated_cable_row),
         ("chest_press_machine", chest_press_machine), ("pec_deck", pec_deck), ("leg_extension", leg_extension),
         ("leg_press_45", leg_press_45), ("hack_squat", hack_squat), ("plate_row", plate_row),
         ("pullup_dip_tower", pullup_dip_tower), ("hyperextension", hyperextension)]


def build_machines(row=True):
    old = bpy_col()
    out = {}
    x = 0.0
    for n, f in BUILD:
        e = f(); out[n] = e
        if row:
            e.location.x = x; x += 2.6 if n in ("power_rack", "smith_machine", "cable_crossover", "plate_row", "leg_press_45") else 1.9
    return out


def bpy_col():
    import bpy
    old = bpy.data.collections.get("Kit")
    if old:
        for o in list(old.all_objects): bpy.data.objects.remove(o, do_unlink=True)
        for c in list(old.children_recursive): bpy.data.collections.remove(c)
        bpy.data.collections.remove(old)
    for ob in [o for o in bpy.data.objects if o.name.startswith("P_") and o.users_collection == ()]: bpy.data.objects.remove(ob, do_unlink=True)
    col = bpy.data.collections.new("Kit"); bpy.context.scene.collection.children.link(col)
    return col
