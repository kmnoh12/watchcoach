"""Detail package `gym_lockers`: men's and women's locker rooms (detail pass 2).

Run inside Blender (scene_gym.blend open):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_gym_lockers; detail_gym_lockers.apply()

Regenerate the printed notices (PIL, outside Blender):
    ~/.venvs/pdf/bin/python promo/tools/detail_gym_lockers.py --textures

Reference photos (work/refs/interior):
  005 008 014 020 011  walls and a free-standing double-sided island of 2-tier lockers, full-height end panels
  004 014 192 193 197  numbered acrylic key fobs hanging from the cam locks (men black/gold, women red)
  191 196              narrow (~300 mm) 2-tier doors with the lock at mid height
  003 035 032          upholstered / padded centre bench in the aisle
  037 185 023 031      powder corner: desk fan on the counter, amenity bottles, cotton swabs, combs, tissue,
                       vertical LED bars beside the mirror, lamp above the mirror (036 brass for women)
  183                  dial body scale in front of the full mirror;  181 186 foot-standing body dryer
  148                  clean towel stacks on a wall shelf above the used-towel return
  185 148              printed notices in thin frames (usage rules, lost & found)
Layout per room (u = distance from the central partition, both suites share the frame of gym_locker_suites):
  pass 3 (deeper 5.4 m room): no island any more (it left 0.6 m aisles). One column beside the entry and a 3-column
  run on the partition wall between the vanity and the towel return -> 8 new lockers per room (men 241-248,
  women 341-348) + fobs on the builder's 40; one long padded bench down the middle with >= 1.2 m aisles.
Existing objects touched: the old centre bench (top/legs/feet) is hidden (the padded bench supersedes it);
the gym bag and folded towel are moved onto the new bench. Originals are stored in custom props.
"""
import math
import os
import random
import sys

try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
except ImportError:  # texture generation runs outside Blender
    bpy = None

KEY = "gym_lockers"
COLL = "DETAIL_gym_lockers"
PFX = "Dgym_lockers_"
HERE = os.path.dirname(os.path.abspath(__file__))
PART_DIR = os.path.normpath(os.path.join(HERE, "..", "parts", "detail_gym_lockers"))
FONT = os.path.normpath(os.path.join(HERE, "..", "parts", "fonts", "NanumGothic-Bold.ttf"))

# Suite frame (gym_locker_suites.py, verified by probe)
PART_X, PART_T = 11.60, 0.10
WIDTH = 4.15
Y_FRONT, Y_WALL_B = -6.92, -12.25     # room faces of front liner / locker back wall (Y_LBACK -12.30)
PLINTH, BODY_H = 0.10, 1.90
CW, DEPTH = 0.30, 0.45
SUITE_CW = 0.33                       # gym_locker_suites.LOCKER_CW (fob matching on the builder's lockers)
VANITY_Y = -9.72                      # gym_locker_suites.VANITY_Y
BENCH_U, BENCH_Y = 2.26, (-8.70, -10.60)  # gym_locker_suites.BENCH_U / BENCH_Y
PART_RUN_Y = (-10.90, -11.80)         # 3 narrow columns on the partition wall behind the vanity
SLIPPER_Y = -8.22                     # slipper rack on the partition wall, past the entry landing

SUITES = (
    dict(tag="Men", s=-1, first=241, fob="black", bench=(0.02, 0.02, 0.022), metal="black",
         slipper=(0.16, 0.20, 0.30), fan=(0.86, 0.87, 0.86)),
    dict(tag="Women", s=1, first=341, fob="red", bench=(0.62, 0.55, 0.46), metal="brass",
         slipper=(0.86, 0.62, 0.68), fan=(0.62, 0.46, 0.26)),
)


# --------------------------------------------------------------------------------------------
# Texture generation (PIL)
# --------------------------------------------------------------------------------------------
def make_textures():
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(PART_DIR, exist_ok=True)

    def F(sz):
        return ImageFont.truetype(FONT, sz)

    INK, RED, GREY = (28, 28, 30), (200, 36, 40), (120, 122, 126)

    def centered(d, y, text, font, fill, W):
        d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)

    def sheet(name, title, sub, lines, accent):
        W, H = 840, 1188
        im = Image.new("RGB", (W, H), (247, 246, 242))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W, 190], fill=accent)
        centered(d, 40, title, F(64), (255, 255, 255), W)
        centered(d, 124, sub, F(30), (255, 255, 255), W)
        y = 250
        for i, ln in enumerate(lines, 1):
            d.ellipse([60, y + 6, 104, y + 50], fill=accent)
            centered_num = str(i)
            d.text((82 - d.textlength(centered_num, font=F(30)) / 2, y + 10), centered_num, font=F(30), fill=(255, 255, 255))
            words, cur, rows = ln.split(" "), "", []
            for w in words:
                t = (cur + " " + w).strip()
                if d.textlength(t, font=F(34)) > W - 190:
                    rows.append(cur)
                    cur = w
                else:
                    cur = t
            rows.append(cur)
            for r in rows:
                d.text((128, y + 8), r, font=F(34), fill=INK)
                y += 50
            y += 34
        d.line([60, H - 150, W - 60, H - 150], fill=(200, 200, 200), width=3)
        centered(d, H - 120, "WATCH COACH FITNESS", F(34), INK, W)
        centered(d, H - 70, "문의: 1층 인포데스크", F(26), GREY, W)
        im.save(os.path.join(PART_DIR, name), quality=92)

    sheet("notice_rules.png", "락커 이용 안내", "LOCKER ROOM RULES", [
        "락커 키는 손목에 착용하고 운동 후 반드시 반납해 주세요.",
        "귀중품은 인포데스크에 맡겨 주세요. 분실 시 책임지지 않습니다.",
        "사용한 수건과 운동복은 반납함에 넣어 주세요.",
        "젖은 몸으로 락커 앞에 서지 마시고 바디 드라이어를 이용해 주세요.",
        "장기 보관은 월 락커 신청 후 이용 가능합니다.",
    ], (30, 30, 34))
    sheet("notice_lost.png", "분실물 보관 안내", "LOST & FOUND", [
        "습득된 분실물은 인포데스크에서 2주간 보관합니다.",
        "보관 기간이 지난 물품은 기부 또는 폐기됩니다.",
        "락커 키 분실 시 재발급 비용 10,000원이 부과됩니다.",
    ], RED)
    sheet("notice_slipper.png", "샤워실 슬리퍼", "SHOWER SLIPPERS", [
        "샤워실 이용 시 슬리퍼를 신어 주세요.",
        "사용 후 제자리에 가지런히 놓아 주세요.",
        "운동화는 탈의실 안까지 신고 들어오실 수 있습니다.",
    ], (40, 110, 150))
    print("textures ->", PART_DIR)


# --------------------------------------------------------------------------------------------
# Blender helpers
# --------------------------------------------------------------------------------------------
_MESH = {}
_STATS = {"objects": 0}


def _coll():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.data.collections["SET"].children.link(c)
    return c


def _clear(c):
    for ob in list(c.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.curves):
        for d in list(coll):
            if d.name.startswith(PFX) and d.users == 0:
                coll.remove(d)


def _mat(name, color, rough=0.5, metal=0.0, emit=0.0, alpha=None, coat=0.0):
    nm = PFX + name
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.diffuse_color = (*color[:3], 1)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color[:3], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*color[:3], 1)
        b.inputs["Emission Strength"].default_value = emit
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.05
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("use_transparent_shadow", True)):
            try:
                setattr(m, attr, val)
            except (AttributeError, TypeError):
                pass
        m.diffuse_color = (*color[:3], alpha)
    return m


def _img_mat(name, file):
    nm = PFX + name
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(os.path.join(PART_DIR, file), check_existing=True)
    if not img.packed_file:
        img.pack()
    tex.image = img
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.35
    b.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.12  # paper reads as paper in the dim room
    m.diffuse_color = (0.9, 0.9, 0.9, 1)
    return m


def _existing(name, fallback):
    return bpy.data.materials.get(name) or fallback


def _finish(bm, name, mat, smooth=False):
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    if mat:
        me.materials.append(mat)
    return me


def _box_mesh(name, size, mat, bevel=0.0):
    key = ("box", name, tuple(round(v, 5) for v in size), mat.name if mat else None, bevel)
    if key in _MESH:
        return _MESH[key]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) * 0.45), segments=1 if bevel < 0.02 else 2,
                        affect="EDGES", profile=0.5)
    me = _finish(bm, name, mat)
    _MESH[key] = me
    return me


def _cyl_mesh(name, r, h, mat, seg=16, r2=None, axis="Z"):
    """Cylinder centred on the origin; axis 'Z' upright, 'Y' pointing to the fixture front."""
    key = ("cyl", name, r, h, mat.name if mat else None, seg, r2, axis)
    if key in _MESH:
        return _MESH[key]
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    if axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, "X"))
    me = _finish(bm, name, mat)
    for p in me.polygons:
        p.use_smooth = len(p.vertices) == 4
    _MESH[key] = me
    return me


def _torus_mesh(name, R, r, mat, seg=20, rseg=6, plane="XZ"):
    key = ("torus", name, R, r, mat.name, seg, rseg, plane)
    if key in _MESH:
        return _MESH[key]
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(rseg):
            b = 2 * math.pi * j / rseg
            p, q, z = (R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)
            ring.append(bm.verts.new((p, z, q) if plane == "XZ" else (p, q, z)))
        rings.append(ring)
    for i in range(seg):
        for j in range(rseg):
            bm.faces.new((rings[i][j], rings[(i + 1) % seg][j], rings[(i + 1) % seg][(j + 1) % rseg], rings[i][(j + 1) % rseg]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = _finish(bm, name, mat, smooth=True)
    _MESH[key] = me
    return me


def _ob(name, me, root, xyz, rot=(0, 0, 0)):
    ob = bpy.data.objects.new(PFX + name, me)
    _coll().objects.link(ob)
    ob.parent = root
    ob.location = xyz
    ob.rotation_euler = [math.radians(a) for a in rot]
    _STATS["objects"] += 1
    return ob


def B(name, root, size, mat, xyz, bevel=0.0, rot=(0, 0, 0)):
    return _ob(name, _box_mesh(name, size, mat, bevel), root, xyz, rot)


def C(name, root, r, h, mat, xyz, seg=16, r2=None, axis="Z", rot=(0, 0, 0)):
    return _ob(name, _cyl_mesh(name, r, h, mat, seg, r2, axis), root, xyz, rot)


def _label(name, root, body, xyz, size, mat, align="CENTER"):
    data = bpy.data.curves.new(PFX + name, "FONT")
    data.body = body
    data.font = bpy.data.fonts.load(FONT, check_existing=True)
    if not data.font.packed_file:
        data.font.pack()
    data.size = size
    data.align_x = align
    data.align_y = "CENTER"
    data.resolution_u = 2
    data.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, data)
    _coll().objects.link(ob)
    ob.parent = root
    ob.location = xyz
    ob.rotation_euler = (math.pi / 2, 0, math.pi)  # readable from local +Y, like gym_locker_suites._label
    _STATS["objects"] += 1
    return ob


class Room:
    def __init__(self, spec):
        self.spec, self.tag, self.s = spec, spec["tag"], spec["s"]
        self.x0 = PART_X + self.s * PART_T / 2
        t = self.tag
        self.M = M = {
            "door": _existing(f"Suite_LockerDoor_{t}", _mat(f"door_{t}", (0.3, 0.3, 0.3), 0.42)),
            "carcass": _existing("Suite_Carcass", _mat("carcass", (0.05, 0.052, 0.056), 0.55)),
            "steel": _existing("Suite_BlackSteel", _mat("steel", (0.028, 0.029, 0.032), 0.42, 0.65)),
            "wood": _existing(f"Suite_Wood_{t}", _mat(f"wood_{t}", (0.3, 0.2, 0.1), 0.48)),
            "accent": _existing(f"Suite_Accent_{t}", _mat(f"accent_{t}", (0.5, 0.5, 0.9), emit=2.0)),
            "chrome": _existing("Suite_Chrome", _mat("chrome", (0.72, 0.73, 0.74), 0.12, 1.0)),
            "plate": _existing("Suite_NumberPlate", _mat("plate", (0.58, 0.6, 0.62), 0.3, 0.85)),
            "plate_text": _existing("Suite_PlateText", _mat("plate_text", (0.02, 0.02, 0.025), 0.5)),
            "dark": _existing("Suite_DarkSlot", _mat("dark", (0.012, 0.012, 0.014), 0.7)),
            "towel": _existing("Suite_TowelWhite", _mat("towel", (0.84, 0.84, 0.82), 0.95)),
            "glow": _existing("Suite_GlowWarm", _mat("glow", (1.0, 0.8, 0.56), emit=3.2)),
            "gold": _mat("gold", (0.80, 0.60, 0.26), 0.28, 1.0),
            "brass": _mat("brass", (0.70, 0.52, 0.28), 0.32, 1.0),
            "black_metal": _mat("black_metal", (0.02, 0.02, 0.022), 0.38, 0.7),
            "fob_black": _mat("fob_black", (0.008, 0.008, 0.01), 0.12, coat=0.8),
            "fob_red": _mat("fob_red", (0.62, 0.02, 0.025), 0.10, coat=0.8),
            "fob_clear": _mat("fob_clear", (0.85, 0.88, 0.88), 0.05, alpha=0.35),
            "bench": _mat(f"bench_{t}", spec["bench"], 0.45, coat=0.2),
            "white_abs": _mat("white_abs", (0.86, 0.86, 0.85), 0.32),
            "slipper": _mat(f"slipper_{t}", spec["slipper"], 0.7),
            "fan": _mat(f"fan_{t}", spec["fan"], 0.35, 0.9 if t == "Women" else 0.0),
            "grey_plastic": _mat("grey_plastic", (0.20, 0.21, 0.22), 0.45),
            "dryer_body": _mat("dryer_body", (0.08, 0.13, 0.11), 0.38),
            "screen": _mat("screen", (0.05, 0.6, 0.9), 0.2, emit=2.0),
            "dial": _mat("dial", (0.92, 0.92, 0.90), 0.3),
            "needle": _mat("needle", (0.85, 0.05, 0.05), 0.4),
            "rubber": _mat("rubber", (0.015, 0.015, 0.016), 0.8),
            "glass_jar": _mat("glass_jar", (0.86, 0.92, 0.92), 0.05, alpha=0.3),
            "blue_liquid": _mat("blue_liquid", (0.05, 0.35, 0.75), 0.05, alpha=0.75),
            "cotton": _mat("cotton", (0.95, 0.95, 0.94), 0.9),
            "bottle_white": _mat("bottle_white", (0.90, 0.90, 0.88), 0.25),
            "bottle_blue": _mat("bottle_blue", (0.55, 0.72, 0.86), 0.2),
            "bottle_amber": _mat("bottle_amber", (0.45, 0.24, 0.08), 0.18),
            "bottle_pink": _mat("bottle_pink", (0.90, 0.66, 0.70), 0.25),
            "towel_grey": _mat("towel_grey", (0.42, 0.42, 0.42), 0.95),
            "led_white": _mat("led_white", (1.0, 0.95, 0.86), emit=6.0),
            "comb": _mat("comb", (0.02, 0.02, 0.02), 0.3),
        }
        M["lamp"] = M["brass"] if spec["metal"] == "brass" else M["black_metal"]
        M["fob"] = M["fob_red"] if spec["fob"] == "red" else M["fob_black"]
        M["fob_num"] = M["gold"]

    def x(self, u):
        return self.x0 + self.s * u

    def frame(self, name, u, y, face, z=0.0):
        rot = {"+u": -self.s * 90, "-u": self.s * 90, "+y": 0, "-y": 180}[face]
        e = bpy.data.objects.new(PFX + f"{self.tag} {name}", None)
        e.empty_display_size = 0.2
        _coll().objects.link(e)
        e.location = (self.x(u), y, z)
        e.rotation_euler.z = math.radians(rot)
        return e


# --------------------------------------------------------------------------------------------
# Lockers
# --------------------------------------------------------------------------------------------
def _fob(R, root, no, lock_xyz, rng=None):
    """Key in the cam lock with a split ring and a numbered acrylic fob hanging in front of the door.
    lock_xyz = centre of the lock's front face in the fixture frame (front = +Y)."""
    M = R.M
    x, y, z = lock_xyz
    B("Key bow", root, (0.016, 0.004, 0.020), M["chrome"], (x, y + 0.006, z))
    _ob("Key ring", _torus_mesh("Key ring", 0.009, 0.0012, M["chrome"], 8, 3), root, (x, y + 0.013, z - 0.016))
    zf = z - 0.044
    C("Fob rim", root, 0.019, 0.004, M["fob_clear"] if R.spec["fob"] == "black" else M["fob"],
      (x, y + 0.016, zf), seg=12, axis="Y")
    C("Fob disc", root, 0.0155, 0.0046, M["fob"] if R.spec["fob"] == "red" else M["fob_black"],
      (x, y + 0.016, zf), seg=12, axis="Y")
    if R.spec["fob"] == "black":
        _ob("Fob gold rim", _torus_mesh("Fob gold rim", 0.0150, 0.0009, M["gold"], 12, 3), root, (x, y + 0.0187, zf))
    # fob numbers (9 mm) are below one pixel at room distances: left off to keep the triangle budget


def _locker_run(R, root, n, numbers, keyed, depth=DEPTH, cw=CW, carcass=True, crown_over=0.01):
    """2-tier run in a fixture frame (back at y = 0, front +Y), columns from local x = 0 to n*cw.
    numbers: list of (upper, lower) per column in local-x order."""
    M = R.M
    L = n * cw
    if carcass:
        B("Locker carcass", root, (L, depth - 0.002, BODY_H), M["carcass"], (L / 2, depth / 2 + 0.001, PLINTH + BODY_H / 2))
        B("Locker plinth", root, (L, depth - 0.06, PLINTH), M["steel"], (L / 2, (depth - 0.06) / 2 + 0.001, PLINTH / 2 + 0.001))
    B("Locker crown", root, (L + 2 * crown_over, depth + 0.03, 0.05), M["wood"],
      (L / 2, (depth + 0.03) / 2 + 0.001, PLINTH + BODY_H + 0.025), 0.006)
    B("Locker accent strip", root, (L, 0.006, 0.012), M["accent"], (L / 2, depth + 0.035, PLINTH + BODY_H + 0.010))
    th = BODY_H / 2
    for i in range(n):
        cx = (i + 0.5) * cw
        for t, no in zip((1, 0), numbers[i]):
            zc = PLINTH + th * (t + 0.5)
            B("Locker door", root, (cw - 0.014, 0.020, th - 0.014), M["door"], (cx, depth + 0.010, zc), 0.004)
            B("Locker pull", root, (0.016, 0.024, 0.16), M["chrome"], (cx + cw * 0.30, depth + 0.032, zc), 0.004)
            C("Locker key lock", root, 0.011, 0.012, M["chrome"], (cx + cw * 0.30, depth + 0.026, zc + 0.13), seg=12, axis="Y")
            B("Locker number plate", root, (0.085, 0.004, 0.046), M["plate"], (cx - 0.05, depth + 0.022, zc + th * 0.33), 0.002)
            _label(f"{R.tag} locker no {no}", root, str(no), (cx - 0.05, depth + 0.0245, zc + th * 0.33), 0.032, M["plate_text"])
            for vz in (-0.012, 0.012):
                B("Locker vent", root, (0.14, 0.004, 0.006), M["dark"], (cx - 0.02, depth + 0.021, zc - th * 0.32 + vz))
            if keyed(no):
                _fob(R, root, no, (cx + cw * 0.30, depth + 0.032, zc + 0.13))
    return 2 * n


def _lockers(R):
    rng = random.Random(1000 + R.spec["first"])
    keyed = lambda no: rng.random() > 0.28  # ~28 % in use: the member wears the key
    no = R.spec["first"]
    count = 0
    # 1) one column beside the entry, on the front wall (faces into the room)
    xs = (R.x(1.097), R.x(1.383))
    root = R.frame("Lockers entry column", 1.097, Y_FRONT - 0.03, "-y")
    root.location.x = max(xs)
    count += _locker_run(R, root, 1, [(no, no + 1)], keyed, depth=DEPTH, cw=0.286, crown_over=0.0)
    no += 2
    # 2) short run on the partition wall between the vanity and the used-towel return (local +x runs +y for men,
    #    -y for women, so the frame sits at the far end for men)
    n = round(abs(PART_RUN_Y[1] - PART_RUN_Y[0]) / CW)
    root = R.frame("Lockers partition", 0.0, PART_RUN_Y[1] if R.s < 0 else PART_RUN_Y[0], "+u")
    nums = [(no + 2 * i, no + 2 * i + 1) for i in range(n)]
    count += _locker_run(R, root, n, nums, keyed, crown_over=0.0)
    no += 2 * n
    for ye in PART_RUN_Y:  # full-height end panels in the door finish (refs 005 020)
        B("Run end panel", None, (0.02, DEPTH + 0.03, PLINTH + BODY_H + 0.05), R.M["door"],
          (R.x((DEPTH + 0.03) / 2 + 0.001), ye + (0.011 if ye == max(PART_RUN_Y) else -0.011),
           (PLINTH + BODY_H + 0.05) / 2 + 0.001), 0.004, rot=(0, 0, 90))
    return count, no - 1


def _fobs_on_existing(R, keyed_rate=0.72):
    """Numbered fobs on the existing locker keys (new objects parented to the existing run frames)."""
    rng = random.Random(77 + R.spec["first"])
    coll = bpy.data.collections.get(f"Annex - {R.tag} Suite")
    if not coll:
        return 0
    labels = {}
    for ob in coll.objects:
        if ob.type == "FONT" and ob.name.startswith(f"{R.tag} locker no "):
            labels.setdefault(ob.parent, []).append(ob)
    n = 0
    for ob in coll.objects:
        if not ob.name.startswith("Locker key lock") or ob.parent is None:
            continue
        lx, ly, lz = ob.location
        best = None
        for lb in labels.get(ob.parent, []):
            d = abs(lb.location.x - (lx - (SUITE_CW * 0.33 + 0.05))) + abs(lb.location.z - (lz + 0.1835))
            if d < 0.03 and (best is None or d < best[0]):
                best = (d, lb)
        if best is None or rng.random() > keyed_rate:
            continue
        no = best[1].data.body
        _fob(R, ob.parent, no, (lx, ly + 0.006, lz))
        n += 1
    return n


# --------------------------------------------------------------------------------------------
# Bench, existing bench handling
# --------------------------------------------------------------------------------------------
def _bench(R):
    M = R.M
    root = R.frame("Bench", BENCH_U, sum(BENCH_Y) / 2, "+u")  # bench runs along y, down the middle of the room
    L, W_ = abs(BENCH_Y[1] - BENCH_Y[0]), 0.36
    B("Bench cushion", root, (L, W_, 0.075), M["bench"], (0, 0, 0.41), 0.025)
    B("Bench base board", root, (L - 0.04, W_ - 0.04, 0.03), M["steel"], (0, 0, 0.358), 0.004)
    for sx in (-1, 1):  # flat-bar sled legs
        xl = sx * (L / 2 - 0.12)
        B("Bench leg post", root, (0.04, 0.025, 0.33), M["lamp"], (xl, W_ / 2 - 0.06, 0.18), 0.004)
        B("Bench leg post", root, (0.04, 0.025, 0.33), M["lamp"], (xl, -W_ / 2 + 0.06, 0.18), 0.004)
        B("Bench leg foot", root, (0.04, W_ - 0.06, 0.02), M["lamp"], (xl, 0, 0.011), 0.004)
        B("Bench leg glide", root, (0.045, 0.03, 0.004), M["rubber"], (xl, W_ / 2 - 0.06, 0.0025))
        B("Bench leg glide", root, (0.045, 0.03, 0.004), M["rubber"], (xl, -W_ / 2 + 0.06, 0.0025))
    return root


def _touch_existing(R):
    """Hide the old centre bench (superseded) and move the bag + towel onto the new bench."""
    touched = []
    seat = 0.4475 + 0.0025
    yc = sum(BENCH_Y) / 2
    moves = {f"{R.tag} Gym bag on bench": yc + 0.45, f"{R.tag} Folded towel bench": yc - 0.40}
    for ob in bpy.data.objects:
        nm = ob.name
        if not ob.users_collection or ob.users_collection[0].name != f"Annex - {R.tag} Suite":
            continue
        is_bench = nm.startswith(f"{R.tag} Bench ")
        if not (is_bench or nm in moves):
            continue
        if "detail_orig_matrix" not in ob:
            ob["detail_orig_matrix"] = [v for row in ob.matrix_world for v in row]
            ob["detail_orig_hide"] = [ob.hide_render, ob.hide_viewport]
        ob["detail_pkg"] = KEY
        m0 = Matrix([ob["detail_orig_matrix"][i * 4:(i + 1) * 4] for i in range(4)])
        if is_bench:
            ob.hide_render = ob.hide_viewport = True
        else:
            loc0, rot0, sc0 = m0.decompose()
            half_h = ob.dimensions.z / 2
            ob.matrix_world = Matrix.LocRotScale(Vector((R.x(BENCH_U), moves[nm], seat + half_h + 0.0005)), rot0, sc0)
        touched.append(nm)
    return touched


def restore():
    """Undo the edits on existing objects (for testing)."""
    for ob in bpy.data.objects:
        if ob.get("detail_pkg") == KEY and "detail_orig_matrix" in ob:
            m = ob["detail_orig_matrix"]
            ob.matrix_world = Matrix([m[i * 4:(i + 1) * 4] for i in range(4)])
            ob.hide_render, ob.hide_viewport = ob["detail_orig_hide"]


# --------------------------------------------------------------------------------------------
# Room dressing
# --------------------------------------------------------------------------------------------
def _slipper(R, root, x, y, z, tilt):
    M = R.M
    for sx in (-0.052, 0.052):
        B("Slipper sole", root, (0.095, 0.25, 0.022), M["slipper"], (x + sx, y, z + 0.011), 0.02, rot=(tilt, 0, 0))
        B("Slipper strap", root, (0.098, 0.085, 0.04), M["slipper"],
          (x + sx, y - 0.045 * math.cos(math.radians(tilt)), z + 0.035 - 0.045 * math.sin(math.radians(tilt))),
          0.018, rot=(tilt, 0, 0))


def _slipper_rack(R):
    """Low 3-tier slanted slipper rack on the partition wall just inside the entry."""
    M = R.M
    root = R.frame("Slipper rack", 0.0, SLIPPER_Y, "+u")
    w, d = 0.64, 0.26
    for sx in (-1, 1):
        B("Slipper rack side", root, (0.02, d, 0.58), M["lamp"], (sx * (w / 2 - 0.01), d / 2 + 0.002, 0.291), 0.003)
    tilt = 12
    for i, z in enumerate((0.07, 0.26, 0.45)):
        B("Slipper rack shelf", root, (w - 0.04, d - 0.01, 0.012), M["white_abs"], (0, d / 2 + 0.004, z), 0.002, rot=(tilt, 0, 0))
        B("Slipper rack lip", root, (w - 0.04, 0.012, 0.03), M["lamp"],
          (0, d - 0.004, z + 0.012 - (d / 2) * math.sin(math.radians(tilt))), 0.002)
        for j, px in enumerate((-0.20, 0.0, 0.20)):
            if (i, j) in ((1, 2), (2, 0)):
                continue  # two pairs are in use
            _slipper(R, root, px, d / 2 + 0.005, z + 0.006, tilt)
    return root


def _notice(R, name, root, xyz, file, w=0.21, h=0.297):
    M = R.M
    m = _img_mat(f"notice_{file.split('.')[0]}", file)
    B(f"Notice frame {name}", root, (w + 0.024, 0.012, h + 0.024), M["lamp"], (xyz[0], xyz[1] + 0.007, xyz[2]), 0.003)
    me = _box_mesh(f"Notice print {name}", (w, 0.002, h), m)
    if not me.uv_layers:
        me.uv_layers.new()
        uv = me.uv_layers[0].data
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uv[li].uv = (0.5 - co.x / w, co.z / h + 0.5)  # readable from local +Y (viewer's right = -x)
    _ob(f"Notice print {name}", me, root, (xyz[0], xyz[1] + 0.0142, xyz[2]))
    B(f"Notice glass {name}", root, (w + 0.004, 0.001, h + 0.004), M["fob_clear"], (xyz[0], xyz[1] + 0.0166, xyz[2]))


def _powder(R):
    """Amenities on the existing vanity (frame of gym_locker_suites: u 0, y -8.85, facing +u)."""
    M = R.M
    root = R.frame("Powder corner", 0.0, VANITY_Y, "+u")
    top = 0.8175 + 0.0005
    # desk fan (refs 037 185)
    fx, fy = 1.00, 0.30
    C("Desk fan base", root, 0.075, 0.025, M["fan"], (fx, fy, top + 0.0125), seg=24, r2=0.068)
    C("Desk fan stem", root, 0.011, 0.20, M["fan"], (fx, fy - 0.02, top + 0.125), seg=12)
    C("Desk fan motor", root, 0.045, 0.10, M["fan"], (fx, fy - 0.045, top + 0.255), seg=20, axis="Y")
    hub_y = fy + 0.035
    C("Desk fan hub", root, 0.022, 0.03, M["fan"], (fx, hub_y, top + 0.255), seg=16, axis="Y")
    for a in (0, 120, 240):
        B("Desk fan blade", root, (0.085, 0.004, 0.045), M["bottle_white"] if R.s < 0 else M["fan"],
          (fx + 0.055 * math.cos(math.radians(a)), hub_y + 0.004, top + 0.255 + 0.055 * math.sin(math.radians(a))),
          0.01, rot=(0, -a, 0))
    for dy in (-0.015, 0.035):
        _ob("Desk fan cage", _torus_mesh("Desk fan cage", 0.118, 0.003, M["fan"], 32, 5), root, (fx, hub_y + dy, top + 0.255))
    for a in range(0, 180, 30):
        B("Desk fan cage wire", root, (0.236, 0.002, 0.002), M["fan"], (fx, hub_y + 0.035, top + 0.255), rot=(0, a, 0))
    # amenity tray: toner / lotion / skin pump bottles + cotton swab cup (refs 023 037)
    tx, ty = 0.59, 0.43
    B("Amenity tray", root, (0.24, 0.10, 0.014), M["white_abs"] if R.s > 0 else M["black_metal"], (tx, ty, top + 0.007), 0.004)
    for i, (bx, mat, h) in enumerate(((-0.085, M["bottle_white"], 0.16), (-0.04, M["bottle_blue"], 0.17),
                                     (0.005, M["bottle_amber"] if R.s < 0 else M["bottle_pink"], 0.15))):
        C("Amenity bottle", root, 0.019, h, mat, (tx + bx, ty, top + 0.014 + h / 2), seg=16)
        C("Amenity pump collar", root, 0.011, 0.02, M["bottle_white"], (tx + bx, ty, top + 0.014 + h + 0.01), seg=12)
        B("Amenity pump nozzle", root, (0.008, 0.03, 0.008), M["bottle_white"], (tx + bx, ty + 0.012, top + 0.014 + h + 0.024))
    C("Cotton swab cup", root, 0.026, 0.075, M["glass_jar"], (tx + 0.075, ty, top + 0.014 + 0.0375), seg=20)
    rng = random.Random(5)
    for k in range(9):
        a = 2 * math.pi * k / 9
        C("Cotton swab stick", root, 0.0018, 0.085, M["cotton"],
          (tx + 0.075 + 0.012 * math.cos(a), ty + 0.012 * math.sin(a), top + 0.014 + 0.06), seg=5,
          rot=(rng.uniform(-8, 8), rng.uniform(-8, 8), 0))
        C("Cotton swab tip", root, 0.004, 0.012, M["cotton"],
          (tx + 0.075 + 0.012 * math.cos(a), ty + 0.012 * math.sin(a), top + 0.014 + 0.105), seg=6)
    # comb disinfectant jar (blue liquid) + combs (Korean bathhouse classic)
    jx, jy = 0.12, 0.40
    C("Comb jar glass", root, 0.04, 0.17, M["glass_jar"], (jx, jy, top + 0.085), seg=24)
    C("Comb jar liquid", root, 0.036, 0.12, M["blue_liquid"], (jx, jy, top + 0.062), seg=24)
    C("Comb jar lid", root, 0.042, 0.015, M["black_metal"], (jx, jy, top + 0.178), seg=24)
    for k, a in enumerate((-10, 6, 18)):
        B("Comb in jar", root, (0.032, 0.004, 0.17), M["comb"], (jx - 0.015 + 0.015 * k, jy, top + 0.13), 0.001, rot=(0, a, 0))
    B("Comb on counter", root, (0.18, 0.035, 0.005), M["comb"], (0.84, 0.47, top + 0.0025), 0.002, rot=(0, 0, 8))
    # mirror lights: vertical LED bars beside the mirror + linear lamp above it (refs 037 031 036)
    for sx in (-1, 1):
        B("Mirror LED bar housing", root, (0.035, 0.028, 0.95), M["lamp"], (sx * 1.13, 0.0155, 1.53), 0.004)
        B("Mirror LED bar glow", root, (0.022, 0.003, 0.92), M["led_white"], (sx * 1.13, 0.031, 1.53))
    B("Mirror lamp housing", root, (1.90, 0.07, 0.035), M["lamp"], (0, 0.036, 2.10), 0.006)
    B("Mirror lamp glow", root, (1.84, 0.045, 0.003), M["led_white"], (0, 0.038, 2.0805))
    for sx in (-0.8, 0.8):
        B("Mirror lamp arm", root, (0.02, 0.02, 0.02), M["lamp"], (sx, 0.011, 2.10))
    return root


def _towel_shelf(R):
    """Clean towel shelf above the existing used-towel return (ref 148)."""
    M = R.M
    root = R.frame("Clean towel shelf", 0.0, Y_WALL_B + 0.225, "+u")
    for z in (1.30, 1.66):
        B("Towel shelf board", root, (0.40, 0.30, 0.025), M["wood"], (0, 0.152, z), 0.004)
        for sx in (-0.17, 0.17):
            B("Towel shelf bracket", root, (0.012, 0.24, 0.05), M["lamp"], (sx, 0.122, z - 0.037), 0.002)
        for k, n in enumerate((4, 3)):
            for j in range(n):
                B("Clean towel", root, (0.17, 0.25, 0.042), M["towel"] if k % 2 == 0 else M["towel_grey"],
                  (-0.095 + 0.19 * k, 0.15, z + 0.0125 + 0.022 + 0.043 * j), 0.016)
    B("Towel shelf tag", root, (0.20, 0.004, 0.05), M["lamp"], (0, 0.30, 1.26), 0.002)
    _label(f"{R.tag} clean towel tag", root, "CLEAN TOWEL", (0, 0.3025, 1.26), 0.026, M["towel"])
    return root


def _wall_fan(R):
    """Wall-mounted fan above the front-wall lockers, aimed down into the room."""
    M = R.M
    root = R.frame("Wall fan", 2.45, Y_FRONT, "-y")
    B("Wall fan bracket", root, (0.11, 0.04, 0.16), M["grey_plastic"] if R.s < 0 else M["fan"], (0, 0.022, 2.45), 0.01)
    B("Wall fan arm", root, (0.04, 0.12, 0.04), M["grey_plastic"] if R.s < 0 else M["fan"], (0, 0.09, 2.45), 0.008)
    head = bpy.data.objects.new(PFX + f"{R.tag} Wall fan head", None)
    _coll().objects.link(head)
    head.parent = root
    head.location = (0, 0.16, 2.43)
    head.rotation_euler = (math.radians(-22), 0, 0)
    mat = M["bottle_white"] if R.s < 0 else M["fan"]
    C("Wall fan motor", head, 0.06, 0.11, mat, (0, 0.0, 0), seg=20, axis="Y")
    C("Wall fan hub", head, 0.03, 0.03, mat, (0, 0.09, 0), seg=16, axis="Y")
    for a in (0, 72, 144, 216, 288):
        B("Wall fan blade", head, (0.12, 0.004, 0.06), M["fob_clear"] if R.s < 0 else mat,
          (0.075 * math.cos(math.radians(a)), 0.095, 0.075 * math.sin(math.radians(a))), 0.015, rot=(0, -a, 0))
    for dy in (0.06, 0.13):
        _ob("Wall fan cage", _torus_mesh("Wall fan cage", 0.17, 0.004, mat, 36, 5), head, (0, dy, 0))
    for a in range(0, 180, 22):
        B("Wall fan cage wire", head, (0.34, 0.002, 0.002), mat, (0, 0.13, 0), rot=(0, a, 0))
    return root


def _scale(R):
    """Mechanical dial body scale (ref 183) in the front corner nook between the front run and the outer run."""
    M = R.M
    root = R.frame("Body scale", 3.78, Y_FRONT - 0.01, "-y")
    B("Scale body", root, (0.30, 0.38, 0.05), M["chrome"], (0, 0.19, 0.026), 0.02)
    for sx in (-0.072, 0.072):
        B("Scale foot pad", root, (0.11, 0.20, 0.004), M["rubber"], (sx, 0.25, 0.0525), 0.01)
    C("Scale dial housing", root, 0.072, 0.03, M["chrome"], (0, 0.075, 0.066), seg=28)
    C("Scale dial face", root, 0.06, 0.002, M["dial"], (0, 0.075, 0.082), seg=28)
    C("Scale dial glass", root, 0.062, 0.002, M["fob_clear"], (0, 0.075, 0.0845), seg=28)
    B("Scale needle", root, (0.004, 0.05, 0.0015), M["needle"], (0.006, 0.075, 0.0835), rot=(0, 0, -20))
    return root


def _body_dryer(R):
    """Foot-standing body dryer (refs 181 186) in front of the full-length mirror."""
    M = R.M
    root = R.frame("Body dryer", 2.12, Y_WALL_B, "+y")
    B("Body dryer platform", root, (0.48, 0.40, 0.055), M["dryer_body"], (0, 0.245, 0.028), 0.02)
    for k in range(7):
        B("Body dryer grille slot", root, (0.30, 0.012, 0.004), M["dark"], (0, 0.18 + 0.035 * k, 0.0555))
    B("Body dryer head", root, (0.26, 0.11, 0.17), M["dryer_body"], (0, 0.095, 0.14), 0.03)
    B("Body dryer display", root, (0.12, 0.004, 0.05), M["screen"], (0, 0.152, 0.17), rot=(-25, 0, 0))
    C("Body dryer cord", root, 0.004, 0.04, M["dark"], (0.11, 0.05, 0.021), seg=6)
    return root


def _notices(R):
    root = R.frame("Entry notices", 0.0, -7.42, "+u")  # partition wall beside the entry landing
    _notice(R, "rules", root, (0.20, 0, 1.45), "notice_rules.png")
    _notice(R, "lost", root, (-0.20, 0, 1.45), "notice_lost.png")
    root = R.frame("Slipper notice", 0.0, SLIPPER_Y, "+u")
    _notice(R, "slipper", root, (0, 0, 1.35), "notice_slipper.png")


# --------------------------------------------------------------------------------------------
def _tris(c):
    dg = bpy.context.evaluated_depsgraph_get()
    t = 0
    for ob in c.objects:
        if ob.type in ("MESH", "FONT", "CURVE"):
            ev = ob.evaluated_get(dg)
            try:
                me = ev.to_mesh()
            except RuntimeError:
                continue
            if me:
                me.calc_loop_triangles()
                t += len(me.loop_triangles)
                ev.to_mesh_clear()
    return t


def apply() -> dict:
    if not os.path.exists(os.path.join(PART_DIR, "notice_rules.png")):
        raise FileNotFoundError("run `python promo/tools/detail_gym_lockers.py --textures` first")
    c = _coll()
    restore()
    _clear(c)
    _MESH.clear()
    _STATS["objects"] = 0
    touched, lockers = [], {}
    for spec in SUITES:
        R = Room(spec)
        n, last = _lockers(R)
        fobs = _fobs_on_existing(R)
        _bench(R)
        touched += _touch_existing(R)
        _slipper_rack(R)
        _powder(R)
        _towel_shelf(R)
        _wall_fan(R)
        _scale(R)
        _body_dryer(R)
        _notices(R)
        lockers[R.tag] = dict(new=n, total=2 * (14 + 6) + n, numbers=f"{spec['first']}-{last}", fobs_on_existing=fobs)
    bpy.context.view_layer.update()
    return {"collection": COLL, "objects_added": len(c.objects), "triangles_added": _tris(c),
            "existing_touched": touched, "lockers": lockers}


if __name__ == "__main__":
    if "--textures" in sys.argv:
        make_textures()
