"""detail8 restroom_split: move the two in-suite restrooms out of the locker suites into one public restroom
behind the gym front wall, and grow both suite showers into the freed space.

Plan: work/restroom_20261128/plan_before_after.png (+ ADDENDUM_1.md).

Public restroom block (world, floor z 0, ceiling 3.00), between the posing room (x <= 0.52) and the men suite (x >= 7.25):
  interior x 1.25 .. 7.25, y -6.91 (back face of Wall_Front) .. -13.00
  entrance   doorless opening 0.91 x 2.18 in Wall_Front centred on x 4.25 (cut like gym_annex.cut_wall_opening:
             Wall_Front + Wainscot_Front + Locker wall mural), charcoal jambs/header + "RESTROOM 화장실 남·여" plaque
  screen     wall x 2.25 .. 6.25 at y -8.10 (1.2 m in front of the entrance); 1 m doorless passages at both ends
  partition  x 4.20 .. 4.30, y -8.15 .. -13.00
  women      x 1.25 .. 4.20 (old women restroom moved here, same orientation)
  men        x 4.30 .. 7.25 (old men restroom moved here, same orientation; right wall = men suite outer wall + tile liner)
The restroom fixtures are MOVED (not rebuilt): vanity wall items keep their wall, far-wall items (cleaning cabinet,
urinals, sanitary vending) move 0.90 m further out, the two WC cubicles widen from 1.025 m to 1.475 m each
(pilasters / headrail stretched, side-wall accessories follow their wall), ceiling items spread proportionally.

Suites (addendum): the shower / old-restroom divider wall is deleted, the shower floor and ceiling run the full
suite width, the old restroom walls get the shower marble, the old restroom door is closed with the locker wall,
the booth row on the partition wall is mirrored onto the outer wall (booths 4-6), aisle lights / drains added.
Leftover restroom objects (door, divider walls) are deleted, never hidden.

Run (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python-exit-code 1 --python promo/tools/detail8_restroom_split.py [-- --save]
Booth number decals 04-06 (PIL, outside Blender, once):
  python3 promo/tools/detail8_restroom_split.py --textures
"""
import math
import os
import re
import sys

try:
    import bpy
    from mathutils import Matrix, Vector
except ImportError:  # texture generation runs outside Blender
    bpy = None

HERE = os.path.dirname(os.path.abspath(__file__))
WET_DIR = os.path.normpath(os.path.join(HERE, "..", "parts", "detail_gym_wet"))
FONT = os.path.normpath(os.path.join(HERE, "..", "parts", "fonts", "NanumGothic-Bold.ttf"))
MARK = "detail8_restroom_split"
COLL = "Annex - Public Restroom"
PFX = "PublicWC "

CEIL = 3.00
X_L, X_R = 1.25, 7.25          # restroom interior
X_MID, MID_T = 4.25, 0.10      # partition women | men
Y_F = -6.912                   # back face of Wall_Front
LINER = 0.02
Y_SCR, SCR_T = -8.10, 0.10     # screen wall
X_SCR = (2.25, 6.25)
Y_B, SHELL_T = -13.00, 0.15
DOOR_X, DOOR_W, DOOR_H = 4.25, 0.91, 2.18
W_OLD, W_NEW = 2.05, 2.95      # restroom width (vanity wall -> far wall)
D_OLD, D_NEW = 4.75, 4.85      # restroom depth (front -> back wall)
D0_OLD, D0_NEW = -12.35, -8.15  # restroom front face (old: locker back wall, new: screen wall back face)
FAR_SHIFT = 0.90               # far-wall fixtures move with the far wall
URINAL_DD = 0.15               # urinal group a little deeper (more room after the cleaning corner)
BACK_DD = D_NEW - D_OLD        # back-wall items follow the back wall
CUBE_OLD = (0.0, 1.025, 2.05)  # cubicle edges, a = distance from the vanity wall
CUBE_NEW = (0.0, 1.475, 2.95)
DOOR_HALF = 0.31               # cubicle door 0.62 m
CUBE_D_OLD = 3.25              # cubicle front line (d)

# Restroom frame per gender: a runs from the vanity wall (old suite divider) toward the far wall.
G = {
    "Men": dict(sx=-1, a0_old=9.45, a0_new=X_R, sign=5.85, main="MEN", sub="남자 화장실"),
    "Women": dict(sx=1, a0_old=13.75, a0_new=X_L, sign=2.65, main="WOMEN", sub="여자 화장실"),
}
# Suite frame (gym_locker_suites): x = x0 + s * u, shower u 0..2.00, restroom u 2.10..4.15
SUITE = {"Men": dict(x0=11.55, s=-1), "Women": dict(x0=11.65, s=1)}
SUITE_W = 4.15


# ------------------------------------------------------------------ textures (outside Blender)

def make_textures():
    """Booth number plates 04-06, same look as detail_gym_wet booth_1..3."""
    from PIL import Image, ImageDraw, ImageFont
    ink = (28, 28, 30)
    for n in (4, 5, 6):
        im = Image.new("RGB", (200, 200), (178, 180, 182))
        d = ImageDraw.Draw(im)
        for y in range(0, 200, 3):
            d.line([0, y, 200, y], fill=(168 + (y * 7) % 18, 170 + (y * 7) % 18, 172 + (y * 7) % 18))
        d.ellipse([12, 12, 188, 188], outline=(60, 60, 64), width=6)
        f = ImageFont.truetype(FONT, 96)
        t = f"{n:02d}"
        w = d.textlength(t, font=f)
        d.text((100 - w / 2, 40), t, font=f, fill=ink)
        im.save(os.path.join(WET_DIR, f"booth_{n}.png"))
    print("TEXTURES_OK")


# ------------------------------------------------------------------ helpers

def O(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise SystemExit(f"missing object: {name}")
    return ob


def tree(ob):
    return [ob] + list(ob.children_recursive)


def move(ob, dx, dy, dz=0.0):
    assert ob.parent is None, ob.name
    ob.location = (ob.location.x + dx, ob.location.y + dy, ob.location.z + dz)


def _mw(ob):
    # parentless objects: matrix_basis is current even right after a location change (matrix_world updates later)
    return ob.matrix_basis.copy() if ob.parent is None else ob.matrix_world.copy()


def mesh_bbox(ob):
    mw = _mw(ob)
    pts = [mw @ v.co for v in ob.data.vertices]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def set_extent(ob, x=None, y=None, z=None):
    """Stretch a box-like mesh so its world extent along each given axis becomes (lo, hi)."""
    if ob.data.users > 1:
        ob.data = ob.data.copy()
    lo, hi = mesh_bbox(ob)
    mw = _mw(ob)
    mi = mw.inverted()
    for v in ob.data.vertices:
        w = mw @ v.co
        for k, rng in enumerate((x, y, z)):
            if rng is None:
                continue
            a, b = sorted(rng)
            t = 0.0 if hi[k] - lo[k] < 1e-9 else (w[k] - lo[k]) / (hi[k] - lo[k])
            w[k] = a + t * (b - a)
        v.co = mi @ w
    ob.data.update()


def relink(ob, c):
    for o in tree(ob):
        for u in list(o.users_collection):
            u.objects.unlink(o)
        c.objects.link(o)


def delete_tree(ob):
    names = [o.name for o in tree(ob)]
    for o in reversed(tree(ob)):
        bpy.data.objects.remove(o, do_unlink=True)
    return names


def obj_mat(ob, src):
    """Give `ob` the same (object-linked) finish as slot 0 of `src`."""
    m = src.material_slots[0].material
    slot = ob.material_slots[0]
    ob["d8rs_orig_mat"] = slot.material.name if slot.material else ""
    slot.link = "OBJECT"
    slot.material = m


def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        raise SystemExit(f"missing material: {name}")
    return m


def wbox(c, name, x, y, z, m, bevel=0.0):
    import wc_lib as W
    ob = W.box(name, (x[1] - x[0], y[1] - y[0], z[1] - z[0]), m, c, ((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2))
    if bevel:
        bv = ob.modifiers.new("Bevel", "BEVEL")
        bv.width = min(bevel, min(x[1] - x[0], y[1] - y[0], z[1] - z[0]) * 0.42)
        bv.segments = 2
    return ob


# ------------------------------------------------------------------ restroom move

def _xa(g, a, new=True):
    return (g["a0_new"] if new else g["a0_old"]) + g["sx"] * a


def _a_of(g, x):
    return (x - g["a0_old"]) * g["sx"]


def _shift(g, da, dd):
    """World delta for an old restroom item that keeps its offset from the vanity wall + da and front + dd."""
    return g["a0_new"] - g["a0_old"] + g["sx"] * da, (D0_NEW - D0_OLD) - dd


def _prop_target(g, x, y):
    a, d = _a_of(g, x), D0_OLD - y
    return _xa(g, a * W_NEW / W_OLD), D0_NEW - d * D_NEW / D_OLD


def move_restroom(tag, c, log):
    g = G[tag]
    T = lambda n: n.replace("{t}", tag)
    moved = []

    def mv(name, da, dd):
        ob = O(T(name))
        dx, dy = _shift(g, da, dd)
        move(ob, dx, dy)
        relink(ob, c)
        moved.append(ob.name)
        return ob

    # vanity wall: vanity, its probe + spill light, hose under it, bin, steel unit, paper towels
    for n in ("{t} Restroom vanity", "{t} Fluted glass spill", "{t} restroom pill probe", "{t} Floor hose",
              "{t} Teal bin", "{t} Steel towel unit", "Dgym_wet_{t} Vanity LED", "Dgym_wet_{t} Paper towel box"):
        mv(n, 0.0, 0.0)
    # far wall
    for n in ("Dgym_wet_{t} Cleaning cabinet", "Dgym_wet_{t} Mop bucket", "Dgym_wet_{t} Mop"):
        mv(n, FAR_SHIFT, 0.0)
    if tag == "Men":
        for n in ("Men Urinal 0", "Men Urinal 1", "Men Urinal screen 0", "Men Urinal screen 1", "Men Urinal screen 2",
                  "Dgym_wet_Men Urinal sticker 0", "Dgym_wet_Men Urinal sticker 1"):
            mv(n, FAR_SHIFT, URINAL_DD)
    else:
        mv("Dgym_wet_Women Sanitary vending", FAR_SHIFT, 0.0)

    # cubicles: widen 1.025 -> 1.475 m each
    da_c = [((CUBE_NEW[i] + CUBE_NEW[i + 1]) - (CUBE_OLD[i] + CUBE_OLD[i + 1])) / 2 for i in range(2)]
    side = (CUBE_NEW[1] - CUBE_NEW[0] - (CUBE_OLD[1] - CUBE_OLD[0])) / 2   # each side wall moves this far out
    for i in range(2):
        mv(f"{{t}} Cubicle door hinge {i}", da_c[i], BACK_DD)
        for n in (f"{{t}} WC {i}", f"Dgym_wet_{{t}} WC spare rolls {i}") + \
                 ((f"Dgym_wet_Women Sanitary bin label {i}",) if tag == "Women" else ()):
            ob = mv(n, da_c[i], BACK_DD)
            assert abs(ob.rotation_euler.z) < 1e-4, ob.name
            for ch in ob.children:
                if abs(ch.location.x) > 0.30:  # accessory on a cubicle side wall: follow the wall
                    ch.location.x += math.copysign(side, ch.location.x)
    for ob in [o for o in bpy.data.objects if o.name.startswith(f"{tag} Cubicle leg")]:
        a = _a_of(g, ob.matrix_world.translation.x)
        i = 0 if a < CUBE_OLD[1] else 1
        mv(ob.name, da_c[i], BACK_DD)
    for n in ("{t} Cubicle divider", "{t} Cubicle divider leg"):
        mv(n, CUBE_NEW[1] - CUBE_OLD[1], BACK_DD)
    for i in range(2):
        cn = (CUBE_NEW[i] + CUBE_NEW[i + 1]) / 2
        for p, (a0, a1) in (("a", (CUBE_NEW[i], cn - DOOR_HALF - 0.005)), ("b", (cn + DOOR_HALF + 0.005, CUBE_NEW[i + 1]))):
            ob = mv(f"{{t}} Cubicle pilaster {p}{i}", 0.0, BACK_DD)
            set_extent(ob, x=(_xa(g, a0), _xa(g, a1)))
    ob = mv("{t} Cubicle headrail", 0.0, BACK_DD)
    set_extent(ob, x=(_xa(g, 0.0), _xa(g, W_NEW)))

    # ceiling items spread over the bigger room
    for n in ("{t} SuiteCeiling LED panel", "{t} SuiteCeiling LED panel.001", "{t} Restroom light", "{t} Cubicle light",
              "{t} Restroom reflection probe"):
        ob = O(T(n))
        nx, ny = _prop_target(g, ob.location.x, ob.location.y)
        move(ob, nx - ob.location.x, ny - ob.location.y)
        relink(ob, c)
        moved.append(ob.name)
        if ob.type == "LIGHT":
            ob.data.size *= W_NEW / W_OLD
            ob.data.size_y *= D_NEW / D_OLD
        elif ob.type == "LIGHT_PROBE":
            ob.scale = (W_NEW / 2, D_NEW / 2, ob.scale.z)
    ex = O(f"Dgym_wet_{tag} Restroom exhaust")   # root at the origin, grilles are its children in world units
    groups = []
    for ch in ex.children:
        p = ch.matrix_world.translation
        for gr in groups:
            if abs(gr[0] - p.x) < 0.35 and abs(gr[1] - p.y) < 0.35:
                gr[2].append(ch)
                break
        else:
            groups.append([p.x, p.y, [ch]])
    for gx, gy, chs in groups:
        cx = sum(ch.matrix_world.translation.x for ch in chs) / len(chs)
        cy = sum(ch.matrix_world.translation.y for ch in chs) / len(chs)
        nx, ny = _prop_target(g, cx, cy)
        for ch in chs:
            ch.location.x += nx - cx
            ch.location.y += ny - cy
    relink(ex, c)
    moved.append(ex.name)
    log.append(f"{tag}: exhaust groups={len(groups)}")

    # surfaces: floor + tiled ceiling move with the room
    x_lo, x_hi = (X_L - SHELL_T, X_MID) if tag == "Women" else (X_MID, X_R)
    ob = O(f"{tag} Floor restroom")
    set_extent(ob, x=(x_lo, x_hi), y=(Y_F, Y_B - SHELL_T))
    ob.name = f"{PFX}{tag} floor"
    relink(ob, c)
    moved.append(ob.name)
    ob = O(f"{tag} SuiteCeiling restroom tiles")
    set_extent(ob, x=(X_L if tag == "Women" else X_MID, X_MID if tag == "Women" else X_R),
               y=(Y_F - LINER, Y_B))
    ob.name = f"{PFX}{tag} SuiteCeiling tiles"
    relink(ob, c)
    moved.append(ob.name)

    # the old door sign becomes the MEN / WOMEN sign at the passage on the screen wall (eye level)
    sg = O(f"{tag} Restroom sign")
    sg.location = (g["sign"], Y_SCR + SCR_T / 2, 1.70 - 2.36)
    sg.rotation_euler = (0, 0, 0)
    for ch in sg.children:
        if ch.type == "FONT":
            ch.data.body = g["sub"] if ch.name.endswith(" sub") else g["main"]
    relink(sg, c)
    moved.append(sg.name)
    return moved


# ------------------------------------------------------------------ new restroom shell, entrance

def cut_wall_opening(target_names, center, size, cutter_coll):
    """Same as gym_annex.cut_wall_opening (Boolean DIFFERENCE, FLOAT solver, hidden wire cutter)."""
    import wc_lib as W
    cutter = W.box(f"DoorCutter_{center[0]:.1f}_{center[1]:.1f}", size, W.mat("CutterMat", (0.1, 0.1, 0.1)), cutter_coll, center)
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    cutter.hide_viewport = True
    for name in target_names:
        ob = bpy.data.objects.get(name)
        if not ob or ob.type != "MESH":
            continue
        mod = ob.modifiers.new(f"Cut_{cutter.name}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        try:
            mod.solver = "FLOAT"
        except (AttributeError, TypeError):
            pass
    return cutter


def _text(c, parent, name, body, xyz, size, material):
    import wc_lib as W
    data = bpy.data.curves.new(name, "FONT")
    data.body = body
    data.font = W.load_font(W.KFONT)
    data.size = size
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.fill_mode = "FRONT"
    data.materials.append(material)
    ob = bpy.data.objects.new(name, data)
    ob.location = xyz
    ob.rotation_euler = (math.pi / 2, 0, 0)
    ob.parent = parent
    c.objects.link(ob)
    return ob


def build_entrance(log):
    """Doorless opening in the room-door style of gym_annex.build_room_door: charcoal jambs + header and the
    overhead plaque, no leaf / kickplate / lever."""
    import wc_lib as W
    doors = bpy.data.collections["Gym Doors"]
    cutters = bpy.data.collections["Gym Door Cutters"]
    cut = cut_wall_opening(("Wall_Front", "Wainscot_Front", "Locker wall mural"), (DOOR_X, -6.75, DOOR_H / 2),
                           (DOOR_W, 0.60, DOOR_H), cutters)
    # the FLOAT solver silently leaves Wall_Front closed with this 4th cutter: verify each cut, fall back to EXACT
    for wn in ("Wall_Front", "Wainscot_Front", "Locker wall mural"):
        ob = O(wn)
        mod = ob.modifiers[f"Cut_{cut.name}"]
        z = 0.05 if wn == "Wainscot_Front" else 1.0
        for solver in ("FLOAT", "EXACT"):
            mod.solver = solver
            dg = bpy.context.evaluated_depsgraph_get()
            ev = ob.evaluated_get(dg)
            mi = ev.matrix_world.inverted()
            hit, *_ = ev.ray_cast(mi @ Vector((DOOR_X, -6.30, z)), (mi.to_3x3() @ Vector((0, -1, 0))).normalized(), distance=1.0)
            if not hit:
                break
        log.append(f"entrance cut {wn}: solver {mod.solver}, open={not hit}")
    root = W.empty("Door_PublicRestroom", doors, (DOOR_X, -6.72, 0))
    root.rotation_euler.z = math.pi
    frame_m = W.mat("RoomDoorFrame_Charcoal", (0.022, 0.024, 0.028), rough=0.40, metal=0.55)
    plaque_bg = W.mat("RoomPlaque_BG", (0.018, 0.020, 0.024), rough=0.36, metal=0.40)
    txt = W.shadeless("RoomPlaque_Text_PublicRestroom", (0.94, 0.96, 0.98), strength=1.55)
    acc = W.shadeless("RoomPlaque_Acc_PublicRestroom", (0.15, 0.72, 0.78), strength=2.2)
    w, h = 0.95, DOOR_H

    def molded(name, size, m, xyz, radius):
        ob = W.box(name, size, m, doors, xyz, parent=root)
        bv = ob.modifiers.new("Bevel", "BEVEL")
        bv.width = min(radius, min(size) * 0.42)
        bv.segments = 2
        return ob

    for sd in (-1, 1):
        molded("Room door jamb", (0.058, 0.24, h), frame_m, (sd * (w / 2 - 0.029), 0, h / 2), 0.004)
    molded("Room door header", (w, 0.24, 0.062), frame_m, (0, 0, h - 0.031), 0.004)
    molded("Room plaque", (0.56, 0.024, 0.16), plaque_bg, (0, -0.115, h + 0.16), 0.005)
    molded("Room plaque strip", (0.52, 0.006, 0.014), acc, (0, -0.128, h + 0.224), 0.002)
    _text(doors, root, "Label_PublicRestroom", "RESTROOM", (0, -0.130, h + 0.172), 0.056, txt)
    _text(doors, root, "Sublabel_PublicRestroom", "화장실  남 · 여", (0, -0.130, h + 0.116), 0.036, txt)
    log.append(f"entrance: cutter {cut.name}, Door_PublicRestroom (no leaf)")
    return root


def build_shell(c, log):
    wxz, wyz = mat("Suite_Porcelain_XZ"), mat("Suite_Porcelain_YZ")
    # the men suite outer wall (x 7.25..7.40) is the restroom's right wall: give it a 15 mm tile liner inside its
    # own thickness so the restroom face stays at x 7.25 (suite side face at 7.40 unchanged)
    for n in ("Men Outer wall locker", "Men Outer wall restroom"):
        set_extent(O(n), x=(X_R + 0.015, X_R + SHELL_T))
    steel, chrome = mat("Suite_BlackSteel"), mat("Suite_Chrome")
    floor_m, ceil_m = mat("Suite_PorcelainFloor"), mat("Suite_Ceiling")
    hw = DOOR_W / 2
    yl = Y_F - LINER
    made = [
        wbox(c, PFX + "Outer wall left", (X_L - SHELL_T, X_L), (Y_B - SHELL_T, Y_F), (0, CEIL), wyz),
        wbox(c, PFX + "Back wall", (X_L - SHELL_T, X_R), (Y_B - SHELL_T, Y_B), (0, CEIL), wxz),
        wbox(c, PFX + "Liner on men suite wall", (X_R, X_R + 0.015), (Y_B, yl), (0, CEIL), wyz),
        wbox(c, PFX + "Front liner a", (X_L, DOOR_X - hw), (yl, Y_F), (0, CEIL), wxz),
        wbox(c, PFX + "Front liner b", (DOOR_X + hw, X_R), (yl, Y_F), (0, CEIL), wxz),
        wbox(c, PFX + "Front liner header", (DOOR_X - hw, DOOR_X + hw), (yl, Y_F), (DOOR_H, CEIL), wxz),
        wbox(c, PFX + "Screen wall", X_SCR, (Y_SCR - SCR_T / 2, Y_SCR + SCR_T / 2), (0, CEIL), wxz),
        wbox(c, PFX + "Partition", (X_MID - MID_T / 2, X_MID + MID_T / 2), (Y_B, Y_SCR - SCR_T / 2), (0, CEIL), wyz),
        wbox(c, PFX + "Ceiling slab", (X_L - SHELL_T, X_R), (Y_B - SHELL_T, Y_F), (CEIL, CEIL + 0.08), ceil_m),
        wbox(c, PFX + "Entry reveal floor", (DOOR_X - hw, DOOR_X + hw), (Y_F, Y_F + 0.21), (-0.05, 0.004), floor_m),
        wbox(c, PFX + "Entry threshold", (DOOR_X - hw, DOOR_X + hw), (Y_F - 0.04, Y_F + 0.06), (0, 0.012), chrome, 0.003),
        wbox(c, PFX + "Entry casing head", (DOOR_X - hw - 0.075, DOOR_X + hw + 0.075), (yl - 0.025, yl), (DOOR_H, DOOR_H + 0.07),
             steel, 0.004),
    ]
    for sd in (-1, 1):
        a, b = sorted((DOOR_X + sd * (hw + 0.035), DOOR_X + sd * (hw - 0.005)))
        made.append(wbox(c, PFX + "Entry casing", (a, b), (yl - 0.025, yl), (0, DOOR_H + 0.04), steel, 0.004))
    # lobby light between the entrance and the screen wall
    ld = bpy.data.lights.new(PFX + "Lobby light", "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = 3.6, 0.8
    ld.energy = 70
    ld.color = (1.0, 0.97, 0.93)
    lo = bpy.data.objects.new(PFX + "Lobby light", ld)
    lo.location = (DOOR_X, (yl + Y_SCR + SCR_T / 2) / 2, CEIL - 0.05)
    c.objects.link(lo)
    made.append(lo)
    log.append(f"shell: {len(made)} new objects")
    return [o.name for o in made]


def move_posters(log):
    """Gym-side posters in front of the new entrance step aside (training + student discount left, plates right)."""
    moves = {("Gym poster student_discount.png", "Aluminum snap frame.002"): -0.86,
             ("Gym poster training.png", "Aluminum snap frame.001"): -0.86,
             ("Gym poster plates.png", "Aluminum snap frame"): 0.645}
    for names, dx in moves.items():
        for n in names:
            ob = O(n)
            ob.matrix_world = Matrix.Translation((dx, 0, 0)) @ ob.matrix_world
    log.append("posters moved: student/training -0.86 m, plates +0.645 m")


# ------------------------------------------------------------------ suite showers (addendum B)

BOOTH_PATTERNS = [
    r"{t} Booth door hinge \d", r"{t} Booth drain \d", r"{t} Booth fixed (clear|frosted) \d", r"{t} Booth side (clear|frosted) \d",
    r"{t} Booth spot \d", r"{t} Glass floor pin \d", r"{t} Glass wall clamp \d(\.\d+)?", r"{t} Shower column \d",
    r"{t} SuiteCeiling diffuser( vent)? \d", r"{t} SuiteCeiling shower downlight \d",
    r"Dgym_wet_{t} Booth plate \d", r"Dgym_wet_{t} Booth wall \d", r"Dgym_wet_{t} Booth stool( basin)?",
    r"{t} Aisle spot -1[24]\.\d", r"{t} SuiteCeiling aisle downlight(\.\d+)?", r"Dgym_wet_{t} Aisle drain -1\d\.\d+",
]


def _is_decal(ob):
    if ob.type == "FONT":
        return True
    if ob.type != "MESH":
        return False
    for s in ob.material_slots:
        m = s.material
        if m and m.node_tree and any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes):
            return True
    return False


def _booth_no_mat(n):
    name = f"Dgym_wet_BoothNo{n}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials["Dgym_wet_BoothNo1"].copy()
    m.name = name
    path = os.path.join(WET_DIR, f"booth_{n}.png")
    if not os.path.exists(path):
        raise SystemExit(f"missing {path}: run with --textures first")
    im = bpy.data.images.load(path, check_existing=True)
    if not im.packed_file:
        im.pack()
    for nd in m.node_tree.nodes:
        if nd.type == "TEX_IMAGE":
            nd.image = im
    return m


def mirror_booths(tag, log):
    sp = SUITE[tag]
    xp = sp["x0"] + sp["s"] * SUITE_W / 2           # mirror plane: centre of the widened shower
    Mm = Matrix.Translation((xp, 0, 0)) @ Matrix.Diagonal((-1, 1, 1, 1)) @ Matrix.Translation((-xp, 0, 0))
    Sx = Matrix.Diagonal((-1, 1, 1, 1))
    pats = [re.compile("^" + p.replace("{t}", tag) + "$") for p in BOOTH_PATTERNS]
    roots = [o for o in bpy.data.objects if o.parent is None and any(p.match(o.name) for p in pats)]
    pairs = []
    for r in roots:
        src = tree(r)
        cp = {}
        for o in src:
            n = o.copy()
            for c in o.users_collection:
                c.objects.link(n)
            cp[o] = n
        for o, n in cp.items():
            if o.parent in cp:
                n.parent = cp[o.parent]
                n.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        cp[r].matrix_world = Mm @ r.matrix_world
        pairs.append((r, cp))
    bpy.context.view_layer.update()
    n_dec = 0
    for r, cp in pairs:
        m = re.match(rf"Dgym_wet_{tag} Booth plate (\d)", r.name)
        new_no = 7 - int(m.group(1)) if m else None
        for o, n in cp.items():
            if _is_decal(o):
                n.matrix_world = Mm @ o.matrix_world @ Sx   # mirrored place, readable (not mirrored) print
                n_dec += 1
                if new_no and o.type == "MESH" and "number" in o.name.lower():
                    n.data = o.data.copy()
                    n.data.materials[0] = _booth_no_mat(new_no)
        for o, n in cp.items():
            if o is r and new_no:
                n.name = f"Dgym_wet_{tag} Booth plate {new_no}"
            else:
                n.name = f"{o.name} mirror"
    log.append(f"{tag}: mirrored {len(roots)} booth roots ({sum(len(c) for _, c in pairs)} objects, {n_dec} decals kept readable)")
    return [n.name for _, cp in pairs for n in cp.values()]


def widen_shower(tag, log):
    sp = SUITE[tag]
    x = lambda u: sp["x0"] + sp["s"] * u
    deleted = []
    for n in (f"{tag} Divider wall shower side", f"{tag} Divider wall restroom side"):
        deleted += delete_tree(O(n))
    set_extent(O(f"{tag} Floor shower"), x=(x(-0.05), x(SUITE_W + 0.15)))
    set_extent(O(f"{tag} SuiteCeiling shower tiles"), x=(x(0.0), x(SUITE_W)))
    obj_mat(O(f"{tag} Outer wall restroom"), O(f"{tag} Partition shower"))
    obj_mat(O(f"{tag} Back wall restroom"), O(f"{tag} Back wall shower"))
    for n in ("111", "121", "141"):
        obj_mat(O(f"{tag} Locker back wall {n}"), O(f"{tag} Locker back wall 110"))
    # close the old restroom door with the locker back wall (both halves: paint / marble)
    for n in ("040", "141"):
        set_extent(O(f"{tag} Locker back wall {n}"), z=(0.0, CEIL))
    # towel hook rail moves from the deleted divider to the locker back wall, right of the doorway
    hr = O(f"{tag} Hook rail")
    hr.matrix_world = Matrix.Translation((x(2.95), -12.35, 0)) @ Matrix.Rotation(math.pi, 4, "Z")
    # light / probe cover the full width
    fl = O(f"{tag} Shower fill")
    fl.location.x = x(SUITE_W / 2)
    fl.data.size = SUITE_W - 0.3
    pr = O(f"{tag} Shower reflection probe")
    pr.location.x = x(SUITE_W / 2)
    pr.scale.x = SUITE_W / 2
    # extra aisle downlights + spots down the middle of the booth aisle
    dl, spot = O(f"{tag} SuiteCeiling aisle downlight"), O(f"{tag} Aisle spot -12.9")
    for y in (-15.60, -16.80):
        for src in (dl, spot):
            n = src.copy()
            n.name = f"{src.name.split(' -')[0]} centre {y}"
            for cc in src.users_collection:
                cc.objects.link(n)
            n.location = (x(SUITE_W / 2), y, src.location.z)
    log.append(f"{tag}: shower widened to u 0..{SUITE_W}, divider deleted, door closed, hook rail moved")
    return deleted


# ------------------------------------------------------------------ checks

def _bb_tree(ob):
    lo, hi = [1e9] * 3, [-1e9] * 3
    for o in tree(ob):
        if o.type in ("MESH", "CURVE", "FONT"):
            for cpt in o.bound_box:
                w = o.matrix_world @ Vector(cpt)
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], w[k]), max(hi[k], w[k])
    return lo, hi


def _ov(a, b, tol=0.003):
    return all(min(a[1][k], b[1][k]) - max(a[0][k], b[0][k]) > tol for k in range(3))


def checks(c):
    out = []
    bpy.context.view_layer.update()
    # 1) fixtures (roots in the restroom collection that are not shell surfaces) stay inside their room
    rooms = {"Women": ((X_L, X_MID - MID_T / 2), (Y_B, Y_F - LINER)), "Men": ((X_MID + MID_T / 2, X_R), (Y_B, Y_F - LINER))}
    fixtures = [o for o in c.objects if o.parent is None and o.type in ("EMPTY", "MESH")
                and not o.name.startswith(PFX) and not re.search(r"Restroom exhaust", o.name)]
    bad = []
    info = {}
    for o in fixtures:
        lo, hi = _bb_tree(o)
        if lo[0] > 1e8:
            continue
        tag = "Women" if (lo[0] + hi[0]) / 2 < X_MID else "Men"
        (x0, x1), (y0, y1) = rooms[tag]
        pen = max(x0 - lo[0], hi[0] - x1, y0 - lo[1], hi[1] - y1, 0)
        # inside the screen wall slab?
        if lo[0] < X_SCR[1] and hi[0] > X_SCR[0] and lo[1] < Y_SCR + SCR_T / 2 - 0.003 and hi[1] > Y_SCR - SCR_T / 2 + 0.003:
            pen = max(pen, 0.01)
        info[o.name] = (tag, lo, hi)
        if pen > 0.003:
            bad.append(f"{o.name} {pen:.3f}")
    # supported = on the floor, on a wall / screen wall, at the ceiling, or touching a supported fixture
    sup = set()
    for n, (tag, lo, hi) in info.items():
        (x0, x1), (y0, y1) = rooms[tag]
        on_wall = min(abs(lo[0] - x0), abs(hi[0] - x1), abs(hi[1] - y1), abs(lo[1] - y0),
                      abs(lo[1] - (Y_SCR + SCR_T / 2)), abs(hi[1] - (Y_SCR - SCR_T / 2))) < 0.02
        if lo[2] < 0.01 or on_wall or hi[2] > CEIL - 0.05:
            sup.add(n)
    for _ in range(4):
        for n, (tag, lo, hi) in info.items():
            if n not in sup and any(_ov((lo, hi), info[m][1:], -0.02) for m in sup if info[m][0] == tag):
                sup.add(n)
    bad += [f"{n} floating z={info[n][1][2]:.3f}" for n in info if n not in sup]
    out.append(f"CHECK fixtures={len(info)} wall_penetration_or_floating={bad or 'none'}")
    # 2) fixture-fixture overlaps (bounding boxes, 3 mm tolerance)
    names = sorted(info)
    ovs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if info[a][0] == info[b][0] and _ov(info[a][1:], info[b][1:]):
                ovs.append(f"{a} x {b}")
    # real triangle intersections for those bbox pairs (evaluated meshes, BVH overlap)
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    bvh_cache = {}

    def bvhs(name):
        if name not in bvh_cache:
            lst = []
            for o in tree(O(name)):
                if o.type == "MESH" and not o.hide_render:
                    ev = o.evaluated_get(dg)
                    me = ev.to_mesh()
                    vs = [ev.matrix_world @ v.co for v in me.vertices]
                    lst.append((o.name, BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons])))
                    ev.to_mesh_clear()
            bvh_cache[name] = lst
        return bvh_cache[name]
    real = []
    for pair in ovs:
        a, b = pair.split(" x ")
        hits = [(na, nb) for na, ta in bvhs(a) for nb, tb in bvhs(b) if ta.overlap(tb)]
        real.append(f"{pair}: {len(hits)} part pairs touch/intersect" + (f" e.g. {hits[0]}" if hits else ""))
    out.append(f"CHECK fixture_bbox_overlaps={len(ovs)}")
    for r in real:
        out.append(f"CHECK   {r}")
    # showers: mirrored booth row vs everything else standing in the shower (not walls / floor / ceiling)
    for tag, sp in SUITE.items():
        def in_shower(lo, hi):
            us = sorted(((lo[0] - sp["x0"]) * sp["s"], (hi[0] - sp["x0"]) * sp["s"]))
            return us[0] > -0.01 and us[1] < SUITE_W + 0.01 and lo[1] > -17.11 and hi[1] < -12.34
        mir, oth = {}, {}
        for o in bpy.data.objects:
            if o.parent is not None or o.type not in ("MESH", "EMPTY", "CURVE"):
                continue
            if re.search(r"Floor shower|wall|Wall|SuiteCeiling shower tiles|exhaust", o.name):
                continue
            lo, hi = _bb_tree(o)
            if lo[0] > 1e8 or not in_shower(lo, hi):
                continue
            (mir if ("mirror" in o.name or re.search(r"Booth plate [456]$", o.name)) else oth)[o.name] = (lo, hi)
        hits = []
        for a_, ba in mir.items():
            for b_, bb_ in oth.items():
                if _ov(ba, bb_, 0.0):
                    n = sum(1 for _, ta in bvhs(a_) for _, tb in bvhs(b_) if ta.overlap(tb))
                    if n:
                        hits.append(f"{a_} x {b_} ({n})")
        out.append(f"CHECK {tag} shower: mirrored roots={len(mir)} others={len(oth)} mesh contacts mirrored-vs-existing={hits or 'none'}")
    # gym side: moved posters vs other wall-mounted things on the gym face of Wall_Front
    posters = [O(n) for n in ("Gym poster student_discount.png", "Gym poster training.png", "Gym poster plates.png")]
    pb = {p.name: _bb_tree(p) for p in posters}
    door_bb = _bb_tree(O("Door_PublicRestroom"))
    clash = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.hide_render or o.name in pb or "snap frame" in o.name or o.name in (
                "Locker wall mural", "Wall_Front", "Wainscot_Front"):
            continue
        lo, hi = _bb_tree(o)
        if hi[1] < -6.70 or lo[1] > -6.40 or hi[0] - lo[0] > 5:
            continue
        for n, bbx in pb.items():
            if _ov((lo, hi), bbx, 0.001):
                clash.append(f"{n} x {o.name}")
    for n, bbx in pb.items():
        if _ov(door_bb, bbx, 0.001):
            clash.append(f"{n} x Door_PublicRestroom")
    out.append(f"CHECK posters x ({', '.join(f'{n[11:-4]} {b[0][0]:.3f}..{b[1][0]:.3f}' for n, b in pb.items())}) "
               f"door frame x {door_bb[0][0]:.3f}..{door_bb[1][0]:.3f} clashes={clash or 'none'}")
    # 3) aisle widths
    def bb(n):
        return info[n][1], info[n][2]
    m_van, m_scr = bb("Men Restroom vanity"), bb("Men Urinal screen 1")
    w_van, w_cab = bb("Women Restroom vanity"), bb("Dgym_wet_Women Cleaning cabinet")
    out.append(f"CHECK men_aisle vanity_front_x={m_van[0][0]:.3f} urinal_screen_front_x={m_scr[1][0]:.3f} "
               f"clear={m_van[0][0] - m_scr[1][0]:.3f}")
    out.append(f"CHECK women_aisle vanity_front_x={w_van[1][0]:.3f} cabinet_front_x={w_cab[0][0]:.3f} "
               f"clear={w_cab[0][0] - w_van[1][0]:.3f}")
    out.append(f"CHECK passages women={X_SCR[0] - X_L:.2f} men={X_R - X_SCR[1]:.2f} lobby_depth="
               f"{(Y_F - LINER) - (Y_SCR + SCR_T / 2):.3f}")
    for tag in G:
        pil = {p: mesh_bbox(O(f"{tag} Cubicle pilaster {p}"))[0:2] for p in ("a0", "b0", "a1", "b1")}
        hr = mesh_bbox(O(f"{tag} Cubicle headrail"))
        cw = [abs(CUBE_NEW[i + 1] - CUBE_NEW[i]) for i in range(2)]
        out.append(f"CHECK {tag} cubicles width={cw} headrail_x={hr[0][0]:.3f}..{hr[1][0]:.3f} front_y={hr[0][1]:.3f}..{hr[1][1]:.3f}")
    # 4) entrance: ray-cast through Wall_Front at z 1.0 / 2.0 to find the opening edges
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    for wn in ("Wall_Front", "Locker wall mural"):
        wall = O(wn).evaluated_get(dg)
        mi = wall.matrix_world.inverted()
        for z in (0.3, 1.0, 1.5, 2.0, 2.15, 2.25):
            open_x = []
            for i in range(0, 1001):
                xx = 3.25 + i * 0.002
                o_l = mi @ Vector((xx, -6.30, z))
                d_l = (mi.to_3x3() @ Vector((0, -1, 0))).normalized()
                hit, *_ = wall.ray_cast(o_l, d_l, distance=1.0)
                if not hit:
                    open_x.append(xx)
            rng = f"{min(open_x):.3f}..{max(open_x):.3f}" if open_x else "closed"
            out.append(f"CHECK {wn} z={z}: no wall at x {rng} (target {DOOR_X - DOOR_W / 2:.3f}..{DOOR_X + DOOR_W / 2:.3f})")
    for z in (1.0, 2.0):
        clear = []
        for i in range(0, 1001):
            xx = 3.25 + i * 0.002
            hit, loc, *_ = sc.ray_cast(dg, Vector((xx, -6.30, z)), Vector((0, -1, 0)), distance=0.70)
            if not hit:
                clear.append(xx)
        rng = f"{min(clear):.3f}..{max(clear):.3f}" if clear else "closed"
        out.append(f"CHECK clear passage through frame + liner z={z}: x {rng}")
    hit, loc, nrm, idx, ob, mtx = sc.ray_cast(dg, Vector((DOOR_X, -5.0, 1.5)), Vector((0, -1, 0)))
    out.append(f"CHECK sightline through entrance hits {ob.name if hit else None} at y={loc.y:.3f}")
    for tag in SUITE:
        sp = SUITE[tag]
        fronts = []
        for o in bpy.data.objects:
            if re.match(rf"{tag} Booth fixed frosted \d( mirror)?$", o.name):
                lo, hi = mesh_bbox(o)
                fronts.append((lo[0] + hi[0]) / 2)
        us = sorted(round((f - sp["x0"]) * sp["s"], 3) for f in fronts)
        out.append(f"CHECK {tag} shower booth front u={us} aisle={us[-1] - us[0] - 0.01:.3f}")
        hit, loc, nrm, idx, ob, mtx = sc.ray_cast(dg, Vector((sp["x0"] + sp["s"] * 3.0, -12.0, 1.0)), Vector((0, -1, 0)), distance=0.6)
        out.append(f"CHECK {tag} old WC door closed: ray hits {ob.name if hit else None}")
    # 5) leftovers in the old restroom zones (centre inside u 2.10..4.15 that are not shower / mirrored / walls)
    left = []
    for o in bpy.data.objects:
        if o.type not in ("MESH", "EMPTY", "LIGHT", "CURVE", "FONT", "LIGHT_PROBE") or o.parent is not None:
            continue
        lo, hi = _bb_tree(o) if o.type in ("MESH", "EMPTY", "CURVE", "FONT") else (o.location, o.location)
        if lo[0] > 1e8:
            lo = hi = o.matrix_world.translation
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        for tag, sp in SUITE.items():
            u = (cx - sp["x0"]) * sp["s"]
            if 2.10 < u < 4.15 and -17.10 < cy < -12.35 and "mirror" not in o.name and " centre " not in o.name \
                    and "Hook rail" not in o.name and not re.search(r"Booth plate [456]$|Floor shower$", o.name):
                left.append(o.name)
    out.append(f"CHECK objects_centred_in_old_restroom_zone={left or 'none'}")
    hidden = [o.name for o in c.all_objects if o.hide_render or o.hide_viewport]
    out.append(f"CHECK hidden_objects_in_restroom={hidden or 'none'}")
    return out


# ------------------------------------------------------------------ main

def main():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    sc = bpy.context.scene
    if sc.get(MARK):
        print("RESTROOM_ALREADY_APPLIED (nothing changed)")
        return
    log, deleted = [], []
    parent = next(p for p in bpy.data.collections if "Annex - Men Suite" in p.children)
    c = bpy.data.collections.get(COLL) or bpy.data.collections.new(COLL)
    if COLL not in parent.children:
        parent.children.link(c)
    # leftovers of the old restroom door
    for tag in G:
        for n in (f"{tag} WC door head", f"{tag} WC door jamb", f"{tag} WC door jamb.001", f"{tag} WC door hinge"):
            deleted += delete_tree(O(n))
    moved = []
    for tag in G:
        moved += move_restroom(tag, c, log)
    new = build_shell(c, log)
    build_entrance(log)
    move_posters(log)
    mirrored = []
    for tag in SUITE:
        mirrored += mirror_booths(tag, log)
        deleted += widen_shower(tag, log)
    sc[MARK] = 1
    for line in log:
        print("LOG", line)
    print(f"LOG moved_roots={len(moved)} new_shell={len(new)} mirrored_objects={len(mirrored)} deleted={len(deleted)}")
    print("LOG deleted:", ", ".join(deleted))
    for line in checks(c):
        print(line)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--save" in argv:
        bpy.ops.wm.save_mainfile(compress=True)
        print("RESTROOM_SAVED")


if bpy is None or "--textures" in sys.argv:
    if bpy is None:
        make_textures()
else:
    main()
