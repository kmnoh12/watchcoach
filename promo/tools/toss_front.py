"""Toss Front (1st gen) customer payment terminal, modelled from product photos.

Build the standalone model file (run from the repo root):
    Blender -b --python promo/tools/toss_front.py -- --build promo/models/toss_front.blend

Put something on the display (image / PNG sequence / video, e.g. an HTML animation rendered to mp4):
    Blender -b promo/models/toss_front.blend --python promo/tools/toss_front.py -- --screen anim.mp4 --save
or from Python: set_toss_front_screen("TossFront", "/path/anim.mp4").
The display is portrait 800 x 1280 px (7", 94.2 x 150.7 mm). By default it is a black, switched-off panel.

Device frame: screen faces -Y, X = right, Z = up, origin at the floor under the front edge.
Size: 118 W x 146 D x 195 H mm, head leaning back 20 degrees on a wedge base.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wc_lib as W  # noqa: E402

MM = 0.001
SCREEN_PX = (800, 1280)

# Head slab (head-local: x across, y up along the slab from its bottom edge, z out of the screen; back face z = 0)
HEAD_W, HEAD_L, HEAD_R = 118.0, 198.0, 12.0
SHELL_T, COVER_T = 11.0, 6.0
HEAD_T = SHELL_T + COVER_T
TILT = 20.0                                  # degrees the head leans back from vertical
FEET_H = 3.0
DISP_W, DISP_H, DISP_R = 94.2, 150.7, 4.0
DISP_TOP_GAP = 13.0                          # bezel above the display
SLOT_Y = 20.5                                # IC card slot centre height on the head
BASE_W, BASE_D = 104.0, 145.5                # wedge base width, overall device depth


def _m(v):
    return v * MM


def _mat(name, color, rough=0.4, metal=0.0, coat=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.15
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = (*color, 1)
    return m


def _rrect(w, h, r, n=10):
    """Counter-clockwise rounded rectangle outline centred on the origin (mm in, mm out)."""
    r = min(r, w / 2, h / 2)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _prism(name, pts, z0, z1, material, c, parent, loc=(0, 0, 0), axis="Z"):
    """Extrude a convex outline (mm). axis Z: pts are (x, y); axis X: pts are (y, z) extruded along x."""
    bm = bmesh.new()

    def co(p, d):
        return (_m(d), _m(p[0]), _m(p[1])) if axis == "X" else (_m(p[0]), _m(p[1]), _m(d))

    lo = [bm.verts.new(co(p, z0)) for p in pts]
    hi = [bm.verts.new(co(p, z1)) for p in pts]
    bm.faces.new(hi)
    bm.faces.new(list(reversed(lo)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return W.mesh_obj(name, bm, material, c, loc, (0, 0, 0), parent)


def _disc(name, r, z0, z1, material, c, parent, xy, seg=40):
    ob = W.cyl(name, _m(r), _m(z1 - z0), material, c, (_m(xy[0]), _m(xy[1]), _m((z0 + z1) / 2)), parent=parent, seg=seg)
    return _smooth(ob)


def _smooth(ob, angle=35.0):
    try:
        ob.data.shade_smooth()
        ob.data.set_sharp_from_angle(angle=math.radians(angle))
    except (AttributeError, TypeError):
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def _bevel(ob, width_mm, segments=4, angle=35.0):
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width = _m(width_mm)
    bv.segments = segments
    bv.limit_method = "ANGLE"
    bv.angle_limit = math.radians(angle)
    bv.harden_normals = False
    return bv


def _bake(ob, cutters=()):
    """Apply the modifier stack plus boolean cuts (cut faces take the cutter's material)."""
    for k, cu in enumerate(cutters):
        md = ob.modifiers.new(f"Cut{k}", "BOOLEAN")
        md.operation = "DIFFERENCE"
        md.object = cu
        md.solver = "EXACT"
        md.material_mode = "TRANSFER"
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = ob.name
    bpy.data.meshes.remove(old)
    for cu in cutters:
        cm = cu.data
        bpy.data.objects.remove(cu, do_unlink=True)
        bpy.data.meshes.remove(cm)
    return _smooth(ob)


def _screen_material(name):
    """Display glass: black glossy panel whose emission comes from one image node (blank black by default)."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.004, 0.004, 0.005, 1)
    b.inputs["Roughness"].default_value = 0.05
    b.inputs["Emission Strength"].default_value = 1.0
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.name = tex.label = "ScreenImage"
    blank = bpy.data.images.get("TossFront_Screen_Blank") or bpy.data.images.new(
        "TossFront_Screen_Blank", 8, 8 * SCREEN_PX[1] // SCREEN_PX[0])
    blank.generated_color = (0, 0, 0, 1)
    tex.image = blank
    tex.extension = "CLIP"
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    m.diffuse_color = (0.01, 0.01, 0.012, 1)
    return m


def _sequence_length(path):
    folder, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    prefix = stem.rstrip("0123456789")
    if prefix == stem:
        return 1
    return sum(1 for f in os.listdir(folder)
               if f.startswith(prefix) and f.endswith(ext) and f[len(prefix):len(f) - len(ext)].isdigit())


def set_toss_front_screen(root_name="TossFront", source=None, strength=1.0, frame_start=1):
    """Show an image, a numbered PNG sequence (pass its first frame, e.g. frame_0001.png) or a video on the
    display; it loops from scene frame `frame_start`. source=None turns the display back to black.
    strength = screen brightness (emission)."""
    m = bpy.data.materials[f"{root_name}_Screen"]
    tex = m.node_tree.nodes["ScreenImage"]
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Emission Strength"].default_value = strength
    if not source:
        tex.image = bpy.data.images["TossFront_Screen_Blank"]
        return None
    path = os.path.abspath(source)
    im = bpy.data.images.load(path, check_existing=True)
    frames = 1
    if os.path.splitext(path)[1].lower() in (".mp4", ".mov", ".webm", ".mkv", ".avi"):
        im.source = "MOVIE"
        frames = im.frame_duration
    elif _sequence_length(path) > 1:
        im.source = "SEQUENCE"
        frames = _sequence_length(path)
    tex.image = im
    if frames > 1:
        iu = tex.image_user
        iu.frame_duration = frames
        iu.frame_start = frame_start
        iu.use_auto_refresh = True
        iu.use_cyclic = True
    return im


def build_toss_front(c, parent=None, loc=(0, 0, 0), rot_z_deg=0.0, name="TossFront"):
    """Toss Front (1st gen): white tilted 7" display head with a single top camera and an IC card slot under the
    screen, light grey back shell (grey band + round badge on the back), wedge base with rounded back end,
    cable tunnel underneath, green status LED + round power button on its left flank, four grey rubber feet."""
    root = W.empty(name, c, loc, parent=parent, size=0.05)
    root.rotation_euler.z = math.radians(rot_z_deg)

    white_m = _mat("TossFront_WhiteBody", (0.88, 0.885, 0.88), rough=0.36, coat=0.15)
    shell_m = _mat("TossFront_GreyShell", (0.80, 0.805, 0.80), rough=0.42)
    band_m = _mat("TossFront_BackBand", (0.58, 0.59, 0.60), rough=0.5)
    rubber_m = _mat("TossFront_RubberFoot", (0.52, 0.53, 0.54), rough=0.85)
    slot_rim_m = _mat("TossFront_SlotRim", (0.60, 0.61, 0.62), rough=0.45)
    slot_m = _mat("TossFront_SlotDark", (0.015, 0.015, 0.017), rough=0.6)
    lens_m = _mat("TossFront_CameraLens", (0.01, 0.01, 0.012), rough=0.05, coat=1.0)
    ring_m = _mat("TossFront_CameraRing", (0.06, 0.06, 0.065), rough=0.3)
    led_m = _mat("TossFront_StatusLED", (0.2, 0.9, 0.3), rough=0.2, emit=(0.25, 1.0, 0.35), strength=6.0)
    gap_m = _mat("TossFront_Seam", (0.45, 0.46, 0.46), rough=0.6)
    screen_m = _screen_material(f"{name}_Screen")

    # ---- head: rotate about X so local +y runs up the slab and local +z faces out of the screen -----------------
    s, co_ = math.sin(math.radians(TILT)), math.cos(math.radians(TILT))
    front_bottom_z = FEET_H + HEAD_T * s                      # back-bottom edge rests at feet height
    head = W.empty(f"{name}_Head", c, (0, _m(HEAD_T * co_), _m(front_bottom_z - HEAD_T * s)), parent=root, size=0.03)
    head.rotation_euler.x = math.radians(90 - TILT)
    plan = [(x, y + HEAD_L / 2) for x, y in _rrect(HEAD_W, HEAD_L, HEAD_R, 12)]

    shell = _prism(f"{name}_BackShell", plan, 0.0, SHELL_T - 0.15, shell_m, c, head)
    _bevel(shell, 2.6, 4)
    band = _prism(f"{name}_BandCutter", [(x, y + HEAD_L - 10 - 15) for x, y in _rrect(96, 30, 7, 8)],
                  -2.0, 0.7, band_m, c, head)
    badge = _disc(f"{name}_BadgeCutter", 7.5, -1.0, 0.35, gap_m, c, head, (0, HEAD_L * 0.55), 48)
    _bake(shell, [band, badge])
    _disc(f"{name}_BackBadge", 6.2, 0.20, 1.0, shell_m, c, head, (0, HEAD_L * 0.55), 48)

    cover = _prism(f"{name}_FrontCover", plan, SHELL_T, HEAD_T, white_m, c, head)
    _bevel(cover, 2.4, 4)
    disp_cy = HEAD_L - DISP_TOP_GAP - DISP_H / 2
    disp_cut = _prism(f"{name}_DisplayCutter", [(x, y + disp_cy) for x, y in _rrect(DISP_W + 0.6, DISP_H + 0.6, DISP_R, 8)],
                      HEAD_T - 0.6, HEAD_T + 2, gap_m, c, head)
    slot_recess = _prism(f"{name}_SlotRecessCutter", [(y, x + SLOT_Y) for x, y in _rrect(7.0, 64.0, 3.5, 10)],
                         HEAD_T - 1.3, HEAD_T + 2, slot_rim_m, c, head)
    slot_deep = _prism(f"{name}_SlotCutter", [(y, x + SLOT_Y) for x, y in _rrect(1.8, 58.0, 0.9, 6)],
                       HEAD_T - 14, HEAD_T + 2, slot_m, c, head)
    _bake(cover, [disp_cut, slot_recess, slot_deep])

    # display glass: thin black border ring + inner face carrying the screen material and full 0..1 UVs
    bm = bmesh.new()
    outline = [(x, y + disp_cy) for x, y in _rrect(DISP_W, DISP_H, DISP_R, 10)]
    z_glass = HEAD_T - 0.05
    lo = [bm.verts.new((_m(x), _m(y), _m(HEAD_T - 0.6))) for x, y in outline]
    hi = [bm.verts.new((_m(x), _m(y), _m(z_glass))) for x, y in outline]
    top = bm.faces.new(hi)
    bm.faces.new(list(reversed(lo)))
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.inset_individual(bm, faces=[top], thickness=_m(0.9), depth=0.0)
    uv = bm.loops.layers.uv.new("UVMap")
    x0, x1 = -DISP_W / 2 + 0.9, DISP_W / 2 - 0.9
    y0, y1 = disp_cy - DISP_H / 2 + 0.9, disp_cy + DISP_H / 2 - 0.9
    for f in bm.faces:
        is_screen = f.normal.z > 0.9 and all(abs(v.co.x) < _m(DISP_W / 2 - 0.5) and
                                             _m(y0 - 0.2) < v.co.y < _m(y1 + 0.2) for v in f.verts)
        f.material_index = 1 if is_screen else 0
        for lp in f.loops:
            lp[uv].uv = ((lp.vert.co.x / MM - x0) / (x1 - x0), (lp.vert.co.y / MM - y0) / (y1 - y0))
    disp = W.mesh_obj(f"{name}_Display", bm, lens_m, c, (0, 0, 0), (0, 0, 0), head)
    disp.data.materials.append(screen_m)

    # top camera (single round lens) + tiny ambient-light sensor dot under it
    cam_y = HEAD_L - 6.5
    _disc(f"{name}_CameraRing", 2.4, HEAD_T - 0.4, HEAD_T + 0.12, ring_m, c, head, (0, cam_y), 32)
    _disc(f"{name}_CameraLens", 1.55, HEAD_T, HEAD_T + 0.28, lens_m, c, head, (0, cam_y), 32)
    _disc(f"{name}_LightSensor", 0.45, HEAD_T - 0.2, HEAD_T + 0.06, ring_m, c, head, (0, cam_y - 3.6), 16)

    # ---- wedge base (side profile in (y, z), extruded across x) -------------------------------------------------
    back_bottom = Vector((HEAD_T * co_, FEET_H))          # head back-bottom edge in (y, z)
    up = Vector((s, co_))                                  # along the head
    into_head = Vector((-co_, s))                          # from the head back face toward the screen
    joint = back_bottom + up * ((96.0 - FEET_H) / co_)     # slope meets the head back at z = 96 mm
    corner = Vector((BASE_D, 52.0))
    u1, u2 = Vector((0, 1)), (joint - corner).normalized()
    alpha = math.acos(max(-1.0, min(1.0, (-u1).dot(u2))))
    R = 17.0
    t = R / math.tan(alpha / 2)
    t1, t2 = corner - u1 * t, corner + u2 * t
    ctr = t1 + Vector((-1, 0)) * R
    a1, a2 = math.atan2(t1.y - ctr.y, t1.x - ctr.x), math.atan2(t2.y - ctr.y, t2.x - ctr.x)
    arc = [ctr + R * Vector((math.cos(a1 + (a2 - a1) * k / 10), math.sin(a1 + (a2 - a1) * k / 10))) for k in range(11)]
    inner_top = joint + into_head * 7.0
    inner_bot = back_bottom + into_head * 7.0 + up * 1.5
    profile = [(inner_bot.x, FEET_H), (BASE_D, FEET_H)] + [(p.x, p.y) for p in arc] + \
              [(joint.x, joint.y), (inner_top.x, inner_top.y), (inner_bot.x, inner_bot.y)]
    base = _prism(f"{name}_Base", profile, -BASE_W / 2, BASE_W / 2, white_m, c, root, axis="X")
    _bevel(base, 6.5, 5, 30.0)
    tunnel = _prism(f"{name}_CableTunnelCutter",
                    _rrect(46.0, 26.0, 6.0, 8),
                    BASE_D - 58, BASE_D + 5, gap_m, c, root)
    tunnel.rotation_euler.x = math.radians(-90)
    tunnel.location = (0, 0, _m(FEET_H))
    _bake(base, [tunnel])

    # status LED + round power button on the left flank near the back end
    side = W.empty(f"{name}_LeftFlank", c, (_m(-BASE_W / 2), 0, 0), parent=root, size=0.02)
    side.rotation_euler = (math.radians(90), 0, math.radians(-90))   # local z -> -X (out of the flank)
    btn_y, btn_z, led_z = BASE_D - 19.0, 22.0, 35.0
    _bake(base, [_disc(f"{name}_ButtonRingCutter", 6.0, -1.0, 0.55, gap_m, c, side, (-btn_y, btn_z), 40)])
    btn = _disc(f"{name}_PowerButton", 5.1, -0.4, 0.45, white_m, c, side, (-btn_y, btn_z), 40)
    _bevel(btn, 0.4, 3)
    _disc(f"{name}_StatusLED", 0.85, -0.3, 0.25, led_m, c, side, (-btn_y, led_z), 20)

    # rubber feet: two under the head's back-bottom edge, two under the base's back end
    for k, (fx, fy) in enumerate(((-42, 13), (42, 13), (-36, BASE_D - 14), (36, BASE_D - 14))):
        foot = W.cyl(f"{name}_Foot{k}", _m(6.0), _m(FEET_H + 0.6), rubber_m, c,
                     (_m(fx), _m(fy), _m((FEET_H + 0.6) / 2)), parent=root, seg=28)
        _bevel(foot, 0.8, 2)
    return root


def _build_file(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    c = bpy.data.collections.new("TossFront")
    sc.collection.children.link(c)
    build_toss_front(c)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
    print("saved", path)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--build" in argv:
        _build_file(argv[argv.index("--build") + 1])
    elif "--screen" in argv:
        src = argv[argv.index("--screen") + 1]
        set_toss_front_screen("TossFront", None if src.lower() in ("none", "off", "black") else src)
        if "--save" in argv:
            bpy.ops.wm.save_mainfile()
            print("saved", bpy.data.filepath)
