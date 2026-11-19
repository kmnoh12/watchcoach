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
    """Molded rounded leather cushion with smooth pillowed edges."""
    sz = list(size); i = sz.index(min(sz)); sz[i] = max(sz[i], 0.085)
    ob = box(name, p, tuple(sz), mat, loc, rot, bevel=0.0)
    K._add_bevel(ob, min(0.024, min(sz) * 0.34), segments=4)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    return ob


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
            cyl("tower_foot", p, 0.032, 0.024, "Z", "grip",
                (x + sx * (w * 0.42), y + sy * (d * 0.40), 0.012), sides=16)
    # Beveled side shrouds & back panel
    for s in (-1, 1):
        box("hside", p, (0.038, d, h), mat, (x + s * (w / 2 - 0.019), y, z0 + h / 2), bevel=0.010)
    box("hback", p, (w - 0.02, 0.035, h), mat, (x, y + d / 2 - 0.018, z0 + h / 2), bevel=0.008)
    # Twin front shroud wings leaving a clean vertical selector slot in the middle
    wing_w = w * 0.24
    for s in (-1, 1):
        box("hfront_wing", p, (wing_w, 0.024, h * 0.86), "grip",
            (x + s * (w / 2 - wing_w / 2 - 0.02), y - d / 2 + 0.014, z0 + h * 0.44), bevel=0.005)
    # Molded top cap + angled instructional placard
    box("hcap", p, (w + 0.02, d + 0.02, 0.065), mat, (x, y, z0 + h), bevel=0.014)
    box("cover", p, (w + 0.01, 0.035, h * 0.22), mat, (x, y - d / 2 - 0.006, z0 + h * 0.89), bevel=0.008)
    box("console", p, (w * 0.62, 0.022, 0.16), "grip", (x, y - d / 2 - 0.026, z0 + h * 0.90), (-14, 0, 0), bevel=0.005)
    box("placard_strip", p, (w * 0.54, 0.008, 0.028), "accent", (x, y - d / 2 - 0.035, z0 + h * 0.935), (-14, 0, 0), bevel=0.002)
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
        box("slab_tag", p, (0.042, 0.006, 0.022), "accent" if i % 4 == 0 else "steel",
            (x + 0.065, y - (d - 0.11) / 2 - 0.002, pz), bevel=0.001)
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
        beam("base", p, (sx * W / 2, -D / 2 - 0.35, 0.035), (sx * W / 2, D / 2 + 0.25, 0.035), 0.07, "frame", 0.07)
        beam("brace", p, (sx * W / 2, -D / 2, 0.35), (sx * W / 2, D / 2, 1.15), 0.04)
        for sy in (-1,):
            box("jhook", p, (0.05, 0.10, 0.07), "accent", (sx * (W / 2 - 0.06), sy * D / 2 - 0.05, 1.35))
            box("safety", p, (0.04, 0.45, 0.04), "steel", (sx * (W / 2 - 0.04), -D / 2 + 0.2, 0.60))
        for z in (0.55, 0.90, 1.25, 1.60, 1.95): box("hole", p, (0.075, 0.075, 0.025), "grip", (sx * W / 2, -D / 2, z))
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
        for z in (0.55, 1.0, 1.45): cyl("peg", p, 0.022, 0.20, "Y", "steel", (s * 0.72, 0.10 + 0.12, z), 6)
    beam("top", p, (-0.72, 0, H), (0.72, 0, H), 0.09)
    sb = part("smith_bar"); sb.parent = p; sb.location = (0, -0.10, 1.30)
    cyl("bar", sb, 0.016, 2.0, "X", "steel", sides=8)
    for s in (-1, 1):
        box("slider", sb, (0.09, 0.12, 0.16), "accent", (s * 0.72, 0.03, 0))
        for i, r in enumerate((0.2, 0.2)): cyl("plate", sb, r, 0.03, "X", "plate", (s * (0.90 + i * 0.04), 0, 0), 12)
        box("hook", sb, (0.04, 0.08, 0.04), "steel", (s * 0.66, -0.02, 0.05))
    return p


# ---------------------------------------------------------------- benches
def flat_bench():
    p = part("flat_bench")
    pad("top", p, (0.30, 1.20, 0.07), (0, 0, 0.43)); box("trim", p, (0.28, 1.18, 0.03), "grip", (0, 0, 0.39))
    for s in (-1, 1):
        beam("leg", p, (0, s * 0.50, 0.38), (0, s * 0.56, 0.02), 0.07)
        box("foot", p, (0.46, 0.06, 0.04), "frame", (0, s * 0.56, 0.02))
    beam("spine", p, (0, -0.5, 0.36), (0, 0.5, 0.36), 0.06)
    return p


def adjustable_bench(angle=45):
    """Back pad hinged at the seat rear (child P_adj_back, rotation_euler.x = -angle)."""
    p = part("adjustable_bench")
    pad("seat", p, (0.30, 0.38, 0.08), (0, -0.10, 0.45)); box("seat_trim", p, (0.28, 0.36, 0.03), "grip", (0, -0.10, 0.405))
    beam("spine", p, (0, -0.28, 0.33), (0, 0.55, 0.33), 0.07)
    beam("leg_f", p, (0, -0.22, 0.40), (0, -0.28, 0.02), 0.07); box("foot_f", p, (0.50, 0.06, 0.04), "frame", (0, -0.28, 0.02))
    beam("leg_b", p, (0, 0.45, 0.33), (0, 0.55, 0.02), 0.07); box("foot_b", p, (0.50, 0.06, 0.04), "frame", (0, 0.55, 0.02))
    beam("ratchet", p, (0, 0.10, 0.34), (0, 0.45, 0.62), 0.04, "steel")
    pv = part("adj_back"); pv.parent = p; pv.location = (0, 0.12, 0.47)
    pad("back", pv, (0.30, 0.78, 0.08), (0, 0.39, 0)); box("back_trim", pv, (0.28, 0.76, 0.03), "grip", (0, 0.39, -0.045))
    beam("back_frame", pv, (0, 0.05, -0.07), (0, 0.72, -0.07), 0.06)
    pv.rotation_euler.x = -math.radians(angle)
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
        beam("link", p, (s * W / 2, 0, H * 0.78), (s * W / 2, 0.30, H * 0.78), 0.10, "silver")
        stack_tower(p, s * W / 2, 0.58, 0.40, 0.34, 1.25, 0.05)
        beam("foot", p, (s * W / 2, -0.30, 0.04), (s * W / 2, 0.80, 0.04), 0.10, "frame", 0.08)
        box("slot", p, (0.04, 0.03, 1.8), "grip", (s * W / 2, -0.065, 1.2))
        cyl("top_pulley", p, 0.09, 0.04, "X", "accent", (s * W / 2, -0.04, H - 0.05), 10)
        cyl("low_pulley", p, 0.07, 0.04, "X", "accent", (s * W / 2, -0.08, 1.45), 10)
        box("carriage", p, (0.12, 0.10, 0.16), "steel", (s * W / 2, -0.06, 1.45))
    beam("top", p, (-W / 2, 0, H), (W / 2, 0, H), 0.12, "silver", 0.10)
    return p


def lat_pulldown():
    p = part("lat_pulldown"); H = 2.20
    stack_tower(p, 0, 0.58, 0.46, 0.38, 1.3, 0.05)
    beam("mast", p, (0, 0.20, 0), (0, 0.20, H), 0.12, "silver", 0.10)
    beam("arm", p, (0, 0.20, H), (0, -0.55, H - 0.05), 0.10, "silver", 0.08)
    cyl("pulley", p, 0.08, 0.05, "X", "accent", (0, -0.45, H - 0.12), 10)
    box("seat", p, (0.36, 0.34, 0.08), "pad", (0, -0.18, 0.46)); beam("seat_post", p, (0, -0.18, 0.42), (0, -0.18, 0.05), 0.08)
    for s in (-1, 1): pad("thigh", p, (0.12, 0.40, 0.12), (s * 0.14, -0.58, 0.66), (0, 0, 0)); beam("thigh_arm", p, (s * 0.14, -0.35, 0.66), (s * 0.14, -0.55, 0.66), 0.04)
    beam("base", p, (0, -0.55, 0.04), (0, 0.80, 0.04), 0.10, "frame", 0.08)
    box("foot", p, (0.80, 0.08, 0.06), "frame", (0, -0.55, 0.05))
    lb = part("lat_bar"); lb.parent = p; lb.location = (0, -0.45, H - 0.40)
    rod("bar", lb, (-0.55, 0, -0.02), (-0.30, 0, 0.06), 0.017, "steel"); rod("bar", lb, (-0.30, 0, 0.06), (0.30, 0, 0.06), 0.017, "steel")
    rod("bar", lb, (0.30, 0, 0.06), (0.55, 0, -0.02), 0.017, "steel")
    for s in (-1, 1): cyl("grip", lb, 0.022, 0.12, "X", "grip", (s * 0.46, 0, 0.02), 8)
    return p


def seated_cable_row():
    p = part("seated_cable_row")
    beam("base", p, (0, -0.65, 0.05), (0, 1.05, 0.05), 0.12, "silver", 0.08)
    stack_tower(p, 0, 0.95, 0.46, 0.38, 1.35, 0.08)
    pad("seat", p, (0.36, 0.34, 0.09), (0, 0.05, 0.42)); beam("seat_post", p, (0, 0.05, 0.38), (0, 0.05, 0.08), 0.08, "silver")
    pad("chest", p, (0.40, 0.10, 0.30), (0, -0.32, 0.78)); beam("chest_post", p, (0, -0.32, 0.60), (0, -0.40, 0.08), 0.08, "silver")
    box("foot_plate", p, (0.50, 0.30, 0.04), "silver", (0, -0.62, 0.20), (35, 0, 0))
    h = part("row_handle"); h.parent = p; h.location = (0, -0.20, 0.82)
    for s in (-1, 1): rod("grip", h, (s * 0.15, 0, 0), (s * 0.15, 0.0, 0.0), 0.02, "grip"); cyl("grip", h, 0.02, 0.14, "Y", "grip", (s * 0.12, -0.08, 0), 8)
    return p


# ---------------------------------------------------------------- selectorised / plate-loaded machines
def _seat_unit(p, back_y=0.20):
    pad("seat", p, (0.42, 0.40, 0.09), (0, back_y - 0.20, 0.45))
    beam("seat_post", p, (0, back_y - 0.2, 0.44), (0, back_y - 0.2, 0.06), 0.07, "silver")
    rod("seat_slide", p, (0, back_y - 0.2, 0.20), (0, back_y - 0.2, 0.44), 0.024, "steel")
    cyl("seat_pop_pin", p, 0.018, 0.045, "Y", "accent", (0, back_y - 0.29, 0.30), sides=16)
    pad("back", p, (0.42, 0.10, 0.62), (0, back_y, 0.82), (-8, 0, 0))
    beam("back_post", p, (0, back_y + 0.06, 0.44), (0, back_y + 0.11, 1.12), 0.065, "silver")
    cyl("back_pop_pin", p, 0.016, 0.04, "X", "accent", (0.06, back_y + 0.08, 0.60), sides=16)


def chest_press_machine():
    p = part("chest_press_machine")
    beam("base", p, (0, -0.85, 0.05), (0, 1.0, 0.05), 0.12, "silver", 0.07)
    for s in (-1, 1):
        beam("footbar", p, (s * 0.40, -0.85, 0.05), (s * 0.40, 0.4, 0.05), 0.06, "silver")
    stack_tower(p, 0, 0.82, 0.48, 0.40, 1.45, 0.07)
    _seat_unit(p, 0.15)
    # Foot assist pedal & overhead pivot bridge
    rod("foot_pedal", p, (-0.28, -0.58, 0.16), (0.28, -0.58, 0.16), 0.018, "steel")
    beam("pivot_bridge", p, (-0.34, 0.20, 0.56), (0.34, 0.20, 0.56), 0.05, "silver")
    for s in (-1, 1):
        beam("arm", p, (s * 0.32, 0.20, 0.95), (s * 0.40, -0.30, 0.95), 0.045, "silver")
        beam("pivot_arm", p, (s * 0.32, 0.20, 0.95), (s * 0.32, 0.20, 0.55), 0.05, "silver")
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
    beam("hub", p, (0, -0.05, 0.80), (0, -0.05, 1.25), 0.09, "silver")
    pivot_hub("pec_hub", p, (0, -0.05, 1.25), r=0.068, width=0.06, axis="Z")
    for s in (-1, 1):
        beam("arm", p, (s * 0.05, -0.05, 1.15), (s * 0.38, -0.20, 1.15), 0.05, "silver")
        beam("arm_dn", p, (s * 0.38, -0.20, 1.15), (s * 0.40, -0.28, 0.82), 0.05, "silver")
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
    cyl("cam_wheel", lv, 0.12, 0.028, "X", "steel", (0.26, 0, 0), sides=28)
    for s in (-1, 1):
        beam("arm", lv, (s * 0.20, 0, 0), (s * 0.20, -0.30, -0.02), 0.045, "silver")
    cyl("roller", lv, 0.062, 0.42, "X", "pad", (0, -0.32, -0.02), sides=24)
    cyl("roller_cap_l", lv, 0.045, 0.016, "X", "steel", (-0.215, -0.32, -0.02), sides=20)
    cyl("roller_cap_r", lv, 0.045, 0.016, "X", "steel", (0.215, -0.32, -0.02), sides=20)
    beam("cam", p, (0.2, -0.25, 0.30), (0.2, 0.45, 0.50), 0.035, "silver")
    return p


def leg_press_45():
    """Plate-loaded 45-degree press: base frame, inclined rails, backrest, carriage with plate pegs."""
    p = part("leg_press_45"); a = math.radians(40)
    for s in (-1, 1):
        beam("rail", p, (s * 0.40, 0.55, 0.12), (s * 0.40, -1.15, 1.05), 0.07, "frame")
        beam("foot", p, (s * 0.50, -1.30, 0.04), (s * 0.50, 0.90, 0.04), 0.09, "frame", 0.08)
        beam("leg", p, (s * 0.40, -0.7, 0.04), (s * 0.40, -0.7, 0.62), 0.06)
        beam("handle", p, (s * 0.36, 0.40, 0.40), (s * 0.36, 0.40, 0.55), 0.04, "steel")
    pad("seat", p, (0.46, 0.46, 0.10), (0, 0.62, 0.20))
    pad("back", p, (0.46, 0.10, 0.70), (0, 0.78, 0.60), (30, 0, 0))
    sl = part("sled"); sl.parent = p; sl.location = (0, -0.60, 0.62)
    box("plate_top", sl, (0.95, 0.08, 0.70), "frame", (0, 0.0, 0.0), (-50, 0, 0))
    box("foot_pad", sl, (0.80, 0.03, 0.60), "silver", (0.0, 0.07, 0.0), (-50, 0, 0))
    for s in (-1, 1):
        cyl("peg", sl, 0.025, 0.40, "X", "steel", (s * 0.55, -0.04, -0.05), 6)
        for i in range(3): cyl("plate", sl, 0.22, 0.03, "X", "plate", (s * (0.60 + i * 0.04), -0.06, -0.05), 12)
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
    for s in (-1, 1):
        beam("foot", p, (s * 0.55, -0.40, 0.04), (s * 0.55, 1.0, 0.04), 0.10, "frame", 0.08)
        beam("arm", p, (s * 0.40, 0.30, 0.80), (s * 0.40, -0.40, 0.55), 0.06)
        beam("arm_back", p, (s * 0.40, 0.30, 0.80), (s * 0.45, 0.85, 0.50), 0.06)
        rod("handle", p, (s * 0.40, -0.40, 0.55), (s * 0.40, -0.55, 0.70), 0.022, "grip")
        cyl("peg", p, 0.03, 0.30, "X", "steel", (s * 0.58, 0.85, 0.50), 6)
        for i in range(2): cyl("plate", p, 0.22, 0.03, "X", "plate", (s * (0.64 + i * 0.04), 0.85, 0.50), 12)
    box("cross", p, (1.10, 0.10, 0.10), "frame", (0, 0.30, 0.78))
    pad("chest", p, (0.40, 0.10, 0.46), (0, 0.0, 0.95), (-15, 0, 0)); beam("post", p, (0, 0.05, 0.5), (0, 0.10, 0.04), 0.09)
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
