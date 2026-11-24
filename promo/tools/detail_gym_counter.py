"""Detail package `gym_counter`: info desk dressing + member amenities corner.

Run inside Blender (scene_gym.blend open):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_gym_counter; detail_gym_counter.apply()

Regenerate the printed graphics (PIL, outside Blender):
    ~/.venvs/pdf/bin/python promo/tools/detail_gym_counter.py --textures

Reference photos (work/refs/gym): 159/160/166/187 counter LED plinth glow, plants beside counter,
187 desk clutter (monitor, keyboard, POP, card stands) and shelving behind the counter,
188/190/192/194/196 counter tops (monitor + keyboard, small plant, card terminal),
165 consult desk with tablet/stand, 197 bench + air purifier entrance, 260/263/264 water/amenity
corner (beige plastic bins, printed notices taped next to the purifier), 265 InBody corner.
Everything is new geometry in collection DETAIL_gym_counter; no existing object is modified.
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

KEY = "gym_counter"
COLL = "DETAIL_gym_counter"
PFX = "Dgym_counter_"
HERE = os.path.dirname(os.path.abspath(__file__))
PART_DIR = os.path.normpath(os.path.join(HERE, "..", "parts", "detail_gym_counter"))
FONT = os.path.normpath(os.path.join(HERE, "..", "parts", "fonts", "NanumGothic-Bold.ttf"))

# Scene frame (world metres, verified by ray casts on scene_gym.blend)
WALL_FRONT_Y = -6.68      # "Locker wall mural" face behind the desk / along the front wall
WALL_LEFT_X = -7.475      # Wainscot_Left face (entrance wall, inside)
HIGH_TOP_Z = 1.041        # Desk high top (check-in block) upper surface
LOW_TOP_Z = 0.764         # Desk low top (consultation) upper surface
PAD_Z = 0.012             # InfoDesk epoxy pad upper surface


# --------------------------------------------------------------------------------------------
# Texture generation (PIL) -------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def make_textures():
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(PART_DIR, exist_ok=True)

    def F(sz):
        return ImageFont.truetype(FONT, sz)

    RED = (214, 34, 40)
    INK = (24, 24, 26)
    GREY = (110, 112, 118)

    def centered(d, y, text, font, fill, W):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)

    # 1) Membership price list (A2 portrait, 0.42 x 0.594 m)
    W, H = 840, 1188
    im = Image.new("RGB", (W, H), (246, 245, 242))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 170], fill=INK)
    centered(d, 34, "WATCH COACH", F(46), (255, 255, 255), W)
    centered(d, 100, "회원권 가격표", F(44), RED, W)
    rows = [("1개월", "79,000원"), ("3개월", "210,000원"), ("6개월", "390,000원"), ("12개월", "690,000원")]
    y = 215
    d.text((60, y), "헬스 이용권", font=F(34), fill=RED)
    y += 58
    for a, b in rows:
        d.text((70, y), a, font=F(40), fill=INK)
        d.text((W - 70 - d.textlength(b, font=F(40)), y), b, font=F(40), fill=INK)
        y += 46
        d.line([70, y + 10, W - 70, y + 10], fill=(205, 205, 205), width=2)
        y += 26
    y += 18
    d.text((60, y), "PT 개인레슨", font=F(34), fill=RED)
    y += 58
    for a, b in (("PT 10회", "650,000원"), ("PT 20회", "1,200,000원"), ("PT 30회", "1,650,000원")):
        d.text((70, y), a, font=F(40), fill=INK)
        d.text((W - 70 - d.textlength(b, font=F(40)), y), b, font=F(40), fill=INK)
        y += 46
        d.line([70, y + 10, W - 70, y + 10], fill=(205, 205, 205), width=2)
        y += 26
    y += 18
    d.text((60, y), "부가 서비스", font=F(34), fill=RED)
    y += 58
    for a, b in (("개인 락커 (월)", "10,000원"), ("운동복 대여 (월)", "10,000원"), ("일일권", "15,000원")):
        d.text((70, y), a, font=F(34), fill=INK)
        d.text((W - 70 - d.textlength(b, font=F(34)), y), b, font=F(34), fill=INK)
        y += 56
    d.rectangle([0, H - 96, W, H], fill=(232, 230, 226))
    centered(d, H - 74, "* 부가세 포함 · 카드 / 계좌이체 가능", F(30), GREY, W)
    im.save(os.path.join(PART_DIR, "notice_price.png"))

    # 2) Opening hours (A2 portrait)
    im = Image.new("RGB", (W, H), (246, 245, 242))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 170], fill=RED)
    centered(d, 34, "OPEN HOURS", F(46), (255, 255, 255), W)
    centered(d, 100, "운영시간 안내", F(44), (255, 255, 255), W)
    y = 240
    for day, hrs in (("평일", "06:00 - 24:00"), ("토요일", "08:00 - 22:00"), ("일요일 · 공휴일", "10:00 - 20:00")):
        centered(d, y, day, F(40), RED, W)
        centered(d, y + 56, hrs, F(66), INK, W)
        y += 190
    d.line([90, y, W - 90, y], fill=(200, 200, 200), width=3)
    y += 40
    for line in ("매월 둘째 · 넷째 일요일 휴관", "마감 30분 전 입장 마감", "PT 상담은 인포데스크에 문의해 주세요"):
        centered(d, y, line, F(34), INK, W)
        y += 62
    d.rectangle([0, H - 96, W, H], fill=(232, 230, 226))
    centered(d, H - 74, "WATCH COACH FITNESS", F(30), GREY, W)
    im.save(os.path.join(PART_DIR, "notice_hours.png"))

    # 3) Towel return sign (A5 landscape acrylic sign, 0.21 x 0.148 m)
    W2, H2 = 630, 444
    im = Image.new("RGB", (W2, H2), (250, 250, 250))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W2, 110], fill=INK)
    centered(d, 26, "TOWEL RETURN", F(52), (255, 255, 255), W2)
    centered(d, 150, "사용한 수건은", F(60), INK, W2)
    centered(d, 232, "여기에 넣어주세요", F(60), RED, W2)
    centered(d, 340, "수건은 1회 1장만 사용해 주세요", F(30), GREY, W2)
    im.save(os.path.join(PART_DIR, "sign_towel.png"))

    # 4) Drinks fridge header (0.52 x 0.10 m)
    W3, H3 = 1040, 200
    im = Image.new("RGB", (W3, H3), (20, 20, 22))
    d = ImageDraw.Draw(im)
    centered(d, 22, "PROTEIN DRINK", F(70), (255, 255, 255), W3)
    centered(d, 118, "단백질 음료 3,500원 · 카운터 결제", F(44), (255, 196, 40), W3)
    im.save(os.path.join(PART_DIR, "fridge_header.png"))

    # 5) Check-in tablet screen (landscape)
    W4, H4 = 800, 540
    im = Image.new("RGB", (W4, H4), (16, 18, 22))
    d = ImageDraw.Draw(im)
    d.text((40, 34), "WATCH COACH", font=F(34), fill=(255, 255, 255))
    d.text((40, 84), "출석 체크", font=F(52), fill=(255, 255, 255))
    d.text((40, 156), "휴대폰 번호 뒤 4자리를 입력하세요", font=F(26), fill=(170, 172, 180))
    for i in range(4):
        d.rounded_rectangle([40 + i * 82, 220, 108 + i * 82, 300], 10, outline=(90, 94, 104), width=3)
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "←", "0", "확인"]
    for k, t in enumerate(keys):
        cx, cy = 470 + (k % 3) * 104, 60 + (k // 3) * 112
        fill = RED if t == "확인" else (44, 47, 55)
        d.rounded_rectangle([cx, cy, cx + 92, cy + 98], 14, fill=fill)
        f = F(40 if len(t) == 1 else 30)
        d.text((cx + 46 - d.textlength(t, font=f) / 2, cy + 26), t, font=f, fill=(255, 255, 255))
    d.text((40, 360), "오늘도 득근하세요!", font=F(36), fill=(255, 196, 40))
    im.save(os.path.join(PART_DIR, "screen_checkin.png"))

    # 6) Card terminal top face (keys + LCD + card slot), portrait, top of image = far (printer) end
    W5, H5 = 256, 600
    im = Image.new("RGB", (W5, H5), (30, 31, 34))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 18, W5 - 20, 60], fill=(70, 70, 74))              # paper exit slot
    d.rectangle([36, 90, W5 - 36, 230], fill=(120, 150, 120))          # mono LCD
    d.text((52, 120), "금액을", font=F(30), fill=(20, 40, 20))
    d.text((52, 166), "입력하세요", font=F(30), fill=(20, 40, 20))
    for r in range(5):
        for cidx in range(3):
            x0, y0 = 34 + cidx * 66, 262 + r * 62
            col = (60, 62, 68)
            if r == 4:
                col = ((200, 40, 40), (220, 180, 40), (40, 150, 60))[cidx]
            d.rounded_rectangle([x0, y0, x0 + 56, y0 + 48], 8, fill=col)
    d.rectangle([12, H5 - 18, W5 - 12, H5 - 10], fill=(8, 8, 8))        # IC card slot
    im.save(os.path.join(PART_DIR, "terminal_face.png"))

    # 7) Keyboard top (key grid)
    W6, H6 = 1024, 340
    im = Image.new("RGB", (W6, H6), (26, 27, 30))
    d = ImageDraw.Draw(im)
    rows_k = [15, 14, 13, 12]
    for r, n in enumerate(rows_k):
        kw = (W6 - 40) / 15.0
        off = 20 + r * kw * 0.25
        for k in range(n):
            x0 = off + k * kw
            d.rounded_rectangle([x0 + 4, 20 + r * 62, x0 + kw - 4, 72 + r * 62], 6, fill=(52, 54, 60))
    d.rounded_rectangle([280, 270, 740, 322], 6, fill=(52, 54, 60))  # space bar
    im.save(os.path.join(PART_DIR, "keyboard_top.png"))

    # 8) Locker key cabinet label
    W7, H7 = 600, 90
    im = Image.new("RGB", (W7, H7), (24, 24, 26))
    d = ImageDraw.Draw(im)
    centered(d, 18, "LOCKER KEY · 락커키", F(46), (255, 255, 255), W7)
    im.save(os.path.join(PART_DIR, "keybox_label.png"))

    # 9) Business cards (front face of the stack)
    W8, H8 = 360, 200
    im = Image.new("RGB", (W8, H8), (250, 250, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 14, H8], fill=RED)
    d.text((34, 40), "WATCH COACH", font=F(36), fill=INK)
    d.text((34, 100), "퍼스널 트레이닝 · PT 상담", font=F(22), fill=GREY)
    d.text((34, 140), "인포데스크 문의", font=F(22), fill=GREY)
    im.save(os.path.join(PART_DIR, "bizcard.png"))

    # 10) Slipper rack tag
    W9, H9 = 480, 120
    im = Image.new("RGB", (W9, H9), (250, 250, 250))
    d = ImageDraw.Draw(im)
    centered(d, 14, "실내화 · SLIPPERS", F(44), INK, W9)
    centered(d, 72, "실내에서는 실내화를 신어주세요", F(28), RED, W9)
    im.save(os.path.join(PART_DIR, "sign_slipper.png"))
    print("textures written to", PART_DIR)


# --------------------------------------------------------------------------------------------
# Blender helpers ----------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
_ROOT = None
_C = None
_ADDED = []


def _mat(name, color, rough=0.5, metal=0.0, emit=0.0, emit_color=None, alpha=None, sheen=0.0,
         transmission=0.0):
    name = PFX + name
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(b.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (*color[:3], 1 if alpha is None else alpha)
    b.inputs["Base Color"].default_value = (*color[:3], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Emission Color"].default_value = (*(emit_color or color)[:3], 1)
    b.inputs["Emission Strength"].default_value = emit
    b.inputs["Alpha"].default_value = 1.0 if alpha is None else alpha
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Transmission Weight"].default_value = transmission
    m.roughness = rough
    m.metallic = metal
    return m


def _img_mat(name, fname, emit=0.25, rough=0.45):
    """Printed / screen surface: image as base colour plus a little emission so it reads in the dark gym."""
    name = PFX + name
    path = os.path.join(PART_DIR, fname)
    img = bpy.data.images.load(path, check_existing=True)
    if not img.packed_file:
        img.pack()
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = emit
    b.inputs["Roughness"].default_value = rough
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return m


def _finish(ob, smooth=False):
    _C.objects.link(ob)
    if smooth and ob.type == "MESH":
        for p in ob.data.polygons:
            p.use_smooth = True
    if _ROOT is not None:
        # world = root @ root^-1 @ basis = basis, so loc/rot stay in world coordinates
        ob.parent = _ROOT
        ob.matrix_parent_inverse = _ROOT.matrix_world.inverted()
    ob["detail_pkg"] = KEY
    _ADDED.append(ob)
    return ob


def _obj_from_bm(name, bm, mats, loc=(0, 0, 0), rot=(0, 0, 0), smooth=False, data=None):
    if data is None:
        data = bpy.data.meshes.new(PFX + name)
        bm.to_mesh(data)
        for m in mats:
            data.materials.append(m)
    if bm is not None:
        bm.free()
    ob = bpy.data.objects.new(PFX + name, data)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    return _finish(ob, smooth)


def _inst(name, data, loc, rot=(0, 0, 0), scale=None):
    """Linked duplicate of a shared mesh (repeats: bottles, towels, slippers, key bands, leaves)."""
    ob = bpy.data.objects.new(PFX + name, data)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    if scale:
        ob.scale = scale
    return _finish(ob)


def _bevel(ob, w, seg=2):
    md = ob.modifiers.new("Bevel", "BEVEL")
    md.width = w
    md.segments = seg
    md.limit_method = "ANGLE"
    return ob


def box(name, size, mat, loc, rot=(0, 0, 0), bevel=0.0, seg=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = _obj_from_bm(name, bm, [mat], loc, rot)
    if bevel:
        _bevel(ob, min(bevel, min(size) * 0.45), seg)
    return ob


def box_mesh(name, size, mat):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return me


def cyl(name, r, h, mat, loc, rot=(0, 0, 0), seg=16, r2=None, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    ob = _obj_from_bm(name, bm, [mat], loc, rot)
    if smooth:
        _smooth_sides(ob)
    return ob


def _smooth_sides(ob):
    """Smooth the curved sides, keep flat caps flat (auto-smooth by angle in 5.x is a modifier; avoid it)."""
    for p in ob.data.polygons:
        p.use_smooth = abs(p.normal.z) < 0.5


def lathe_mesh(name, profile, mats, seg=16, mat_idx=None):
    """Revolve [(r, z), ...] around Z. Rings with r == 0 are collapsed to a pole."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z))
                          for i in range(seg)])
    for k in range(len(rings) - 1):
        a, b = rings[k], rings[k + 1]
        mi = mat_idx[k] if mat_idx else 0
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                f = bm.faces.new((a[0], b[j], b[i]))
            elif len(b) == 1:
                f = bm.faces.new((a[i], a[j], b[0]))
            else:
                f = bm.faces.new((a[i], a[j], b[j], b[i]))
            f.material_index = mi
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return me


def torus_mesh(name, R, r, mat, seg=14, sides=6):
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(sides):
            b = 2 * math.pi * j / sides
            rr = R + r * math.cos(b)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), r * math.sin(b))))
        rings.append(ring)
    for i in range(seg):
        for j in range(sides):
            f = bm.faces.new((rings[i][j], rings[(i + 1) % seg][j], rings[(i + 1) % seg][(j + 1) % sides],
                              rings[i][(j + 1) % sides]))
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return me


def blob_mesh(name, size, mat, subdiv=2, noise=0.18, seed=0):
    """Soft lump (crumpled towel / leaf): displaced, scaled icosphere."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=0.5)
    for v in bm.verts:
        v.co *= 1.0 + rnd.uniform(-noise, noise)
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return me


def img_plane(name, w, h, mat, loc, rot=(0, 0, 0), facing="+y"):
    """Quad with 0..1 UVs. facing '+y'/'-y' = vertical in XZ, '+z' = lying flat (image top towards +y)."""
    a, b = w / 2, h / 2
    if facing == "-y":
        co = [(-a, 0, -b), (a, 0, -b), (a, 0, b), (-a, 0, b)]
    elif facing == "+y":
        co = [(a, 0, -b), (-a, 0, -b), (-a, 0, b), (a, 0, b)]
    elif facing == "+z":
        co = [(-a, -b, 0), (a, -b, 0), (a, b, 0), (-a, b, 0)]
    elif facing == "+z_flip":  # lying flat, image top towards -y (read from the +y side)
        co = [(a, b, 0), (-a, b, 0), (-a, -b, 0), (a, -b, 0)]
    uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
    me = bpy.data.meshes.new(PFX + name)
    me.from_pydata(co, [], [(0, 1, 2, 3)])
    layer = me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        layer.data[li].uv = uv[loop.vertex_index]
    me.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, me)
    ob.location = loc
    ob.rotation_euler = [math.radians(x) for x in rot]
    return _finish(ob)


def _empty_parent(name, loc, rot_z=0.0):
    e = bpy.data.objects.new(PFX + name, None)
    e.empty_display_size = 0.1
    e.location = loc
    e.rotation_euler.z = math.radians(rot_z)
    return _finish(e)


def _child(ob, parent):
    """Re-parent `ob` (built in parent-local coordinates) under a local empty."""
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    return ob


# --------------------------------------------------------------------------------------------
# Materials ----------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def _materials():
    M = {}
    M["white"] = _mat("WhitePlastic", (0.80, 0.80, 0.78), rough=0.38)
    M["black"] = _mat("BlackPlastic", (0.018, 0.018, 0.02), rough=0.42)
    M["graphite"] = _mat("Graphite", (0.06, 0.062, 0.068), rough=0.5, metal=0.2)
    M["alu"] = _mat("BrushedAlu", (0.74, 0.75, 0.77), rough=0.32, metal=1.0)
    M["chrome"] = _mat("Chrome", (0.86, 0.87, 0.88), rough=0.12, metal=1.0)
    M["melamine"] = _mat("WhiteMelamine", (0.80, 0.78, 0.74), rough=0.55)
    M["led"] = _mat("LEDStripWarm", (1.0, 0.86, 0.66), rough=0.4, emit=18.0)
    M["led_channel"] = _mat("LEDChannelAlu", (0.62, 0.63, 0.65), rough=0.35, metal=1.0)
    M["glass"] = _mat("FridgeGlass", (0.82, 0.88, 0.9), rough=0.04, alpha=0.14)
    M["fridge_light"] = _mat("FridgeInteriorLit", (0.93, 0.95, 1.0), rough=0.5, emit=2.2)
    M["wire"] = _mat("WireShelf", (0.70, 0.71, 0.73), rough=0.35, metal=0.9)
    M["towel_grey"] = _mat("TowelGrey", (0.30, 0.31, 0.33), rough=0.95, sheen=0.6)
    M["towel_white"] = _mat("TowelWhite", (0.78, 0.78, 0.76), rough=0.95, sheen=0.6)
    M["towel_navy"] = _mat("TowelNavy", (0.05, 0.07, 0.14), rough=0.95, sheen=0.6)
    M["bin_beige"] = _mat("BinBeigePlastic", (0.66, 0.62, 0.52), rough=0.5)
    M["leaf"] = _mat("RubberPlantLeaf", (0.035, 0.12, 0.03), rough=0.35)
    M["stem"] = _mat("PlantStem", (0.16, 0.11, 0.06), rough=0.8)
    M["soil"] = _mat("PotSoil", (0.05, 0.035, 0.025), rough=1.0)
    M["ceramic"] = _mat("CeramicPotWhite", (0.86, 0.86, 0.84), rough=0.22)
    M["gel"] = _mat("SanitiserGel", (0.55, 0.75, 0.85), rough=0.08, alpha=0.55)
    M["acrylic"] = _mat("ClearAcrylic", (0.9, 0.92, 0.93), rough=0.05, alpha=0.25)
    M["paper"] = _mat("ReceiptPaper", (0.92, 0.92, 0.9), rough=0.7)
    M["eva_navy"] = _mat("SlipperEVANavy", (0.04, 0.06, 0.12), rough=0.75)
    M["eva_grey"] = _mat("SlipperEVAGrey", (0.22, 0.23, 0.25), rough=0.75)
    M["eva_sole"] = _mat("SlipperSole", (0.75, 0.75, 0.73), rough=0.8)
    M["rack"] = _mat("RackBlackPowder", (0.025, 0.025, 0.028), rough=0.55, metal=0.4)
    M["wood"] = bpy.data.materials.get("InfoRef_WarmWood") or _mat("Wood", (0.42, 0.28, 0.16), rough=0.7)
    # bottle labels / caps
    M["lab_choco"] = _mat("LabelChoco", (0.20, 0.09, 0.04), rough=0.45)
    M["lab_vanilla"] = _mat("LabelVanilla", (0.88, 0.84, 0.70), rough=0.45)
    M["lab_banana"] = _mat("LabelBanana", (0.95, 0.72, 0.08), rough=0.45)
    M["lab_blue"] = _mat("LabelBlue", (0.05, 0.25, 0.65), rough=0.45)
    M["cap_red"] = _mat("CapRed", (0.6, 0.04, 0.04), rough=0.4)
    M["band_red"] = _mat("KeyBandRed", (0.65, 0.04, 0.05), rough=0.35)
    M["band_blue"] = _mat("KeyBandBlue", (0.03, 0.18, 0.62), rough=0.35)
    M["band_yellow"] = _mat("KeyBandYellow", (0.9, 0.7, 0.05), rough=0.35)
    M["band_black"] = _mat("KeyBandBlack", (0.02, 0.02, 0.02), rough=0.35)
    M["brass"] = _mat("KeyBrass", (0.78, 0.62, 0.30), rough=0.25, metal=1.0)
    # printed graphics
    M["price"] = _img_mat("NoticePrice", "notice_price.png", emit=0.35)
    M["hours"] = _img_mat("NoticeHours", "notice_hours.png", emit=0.35)
    M["towel_sign"] = _img_mat("SignTowel", "sign_towel.png", emit=0.3)
    M["fridge_header"] = _img_mat("FridgeHeader", "fridge_header.png", emit=2.0)
    M["checkin"] = _img_mat("ScreenCheckin", "screen_checkin.png", emit=1.6, rough=0.15)
    M["terminal"] = _img_mat("TerminalFace", "terminal_face.png", emit=0.3, rough=0.3)
    M["keyboard"] = _img_mat("KeyboardTop", "keyboard_top.png", emit=0.0, rough=0.6)
    M["keybox_label"] = _img_mat("KeyboxLabel", "keybox_label.png", emit=0.6)
    M["bizcard"] = _img_mat("BizCard", "bizcard.png", emit=0.15, rough=0.6)
    M["slipper_sign"] = _img_mat("SignSlipper", "sign_slipper.png", emit=0.3)
    return M


# --------------------------------------------------------------------------------------------
# Builders -----------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def _led_strips(M):
    """Warm under-counter LED: under the high top lip and at the plinth (refs 159/160/166/187)."""
    # High check-in block body face y=-5.28, top underside z=0.999, body x -7.07..-6.01.
    box("LED high lip channel", (1.02, 0.012, 0.008), M["led_channel"], (-6.54, -5.274, 0.995))
    box("LED high lip diffuser", (1.00, 0.004, 0.004), M["led"], (-6.54, -5.2665, 0.993))
    box("LED high plinth channel", (1.02, 0.012, 0.008), M["led_channel"], (-6.54, -5.274, PAD_Z + 0.004))
    box("LED high plinth diffuser", (1.00, 0.004, 0.004), M["led"], (-6.54, -5.2665, PAD_Z + 0.006))
    # Low consultation top: strip glued under the front edge (underside z=0.716).
    box("LED low lip channel", (1.96, 0.012, 0.008), M["led_channel"], (-5.0, -5.262, 0.712))
    box("LED low lip diffuser", (1.94, 0.004, 0.004), M["led"], (-5.0, -5.262, 0.7065))
    # Soft wash so the glow actually lands on the counter face / floor (EEVEE light, ~3000 K).
    for nm, loc, size, power in (("LED wash high", (-6.54, -5.262, 0.985), 1.0, 6.0),
                                 ("LED wash low", (-5.0, -5.255, 0.70), 1.9, 7.0)):
        ld = bpy.data.lights.new(PFX + nm, "AREA")
        ld.shape = "RECTANGLE"
        ld.size = size
        ld.size_y = 0.02
        ld.energy = power
        ld.color = (1.0, 0.80, 0.56)
        lo = bpy.data.objects.new(PFX + nm, ld)
        lo.location = loc
        _finish(lo)


def _keyboard(name, M, loc, rot_z=0.0):
    e = _empty_parent(name, loc, rot_z)
    _child(box(name + " base", (0.36, 0.125, 0.014), M["black"], (0, 0, 0.007), bevel=0.004), e)
    _child(img_plane(name + " keys", 0.35, 0.115, M["keyboard"], (0, 0, 0.0145), facing="+z"), e)
    return e


def _mouse(name, M, loc, rot_z=0.0):
    me = lathe_mesh(name, [(0, 0), (0.030, 0), (0.0315, 0.006), (0.028, 0.02), (0.017, 0.031), (0, 0.034)],
                    [M["black"]], seg=16)
    return _inst(name, me, loc, (0, 0, rot_z), scale=(1.0, 1.75, 1.0))


def _desk_props(M):
    # --- keyboards + mice in front of both existing monitors (staff side, -Y) ---
    _keyboard("Checkin keyboard", M, (-6.68, -5.855, HIGH_TOP_Z), 0)
    _mouse("Checkin mouse", M, (-6.40, -5.86, HIGH_TOP_Z), 4)
    _keyboard("Consult keyboard", M, (-5.63, -5.86, LOW_TOP_Z), 0)
    _mouse("Consult mouse", M, (-5.37, -5.865, LOW_TOP_Z), -6)

    # --- member check-in tablet on an aluminium stand, facing the customer (+Y) (ref 165/187) ---
    t = _empty_parent("Checkin tablet", (-6.92, -5.40, HIGH_TOP_Z), 0)
    _child(cyl("Tablet stand base", 0.055, 0.008, M["alu"], (0, 0, 0.004), seg=24), t)
    _child(cyl("Tablet stand neck", 0.009, 0.177, M["alu"], (0, -0.026, 0.0965), seg=10), t)
    tab = _empty_parent("Tablet head", (0, -0.020, 0.185), 0)
    _child(tab, t)
    tab.rotation_euler.x = math.radians(22)
    _child(box("Tablet body", (0.25, 0.008, 0.174), M["black"], (0, 0, 0), bevel=0.006), tab)
    _child(img_plane("Tablet screen", 0.236, 0.160, M["checkin"], (0, 0.0055, 0), facing="+y"), tab)
    _child(box("Tablet clamp", (0.05, 0.02, 0.03), M["alu"], (0, -0.012, 0), bevel=0.004), tab)

    # --- hand sanitiser pump bottle (high top, customer corner) ---
    s = _empty_parent("Sanitiser", (-6.10, -5.33, HIGH_TOP_Z), 0)
    bottle = lathe_mesh("Sanitiser bottle", [(0, 0), (0.032, 0), (0.034, 0.004), (0.034, 0.120), (0.026, 0.132),
                                             (0.014, 0.140), (0, 0.140)], [M["gel"]], seg=20)
    _child(_inst("Sanitiser bottle", bottle, (0, 0, 0)), s)
    _child(cyl("Sanitiser collar", 0.016, 0.014, M["white"], (0, 0, 0.146), seg=16), s)
    _child(cyl("Sanitiser pump stem", 0.005, 0.03, M["white"], (0, 0, 0.165), seg=10), s)
    _child(box("Sanitiser pump head", (0.026, 0.05, 0.016), M["white"], (0, 0.012, 0.186), bevel=0.005), s)
    _child(cyl("Sanitiser nozzle", 0.003, 0.02, M["white"], (0, 0.044, 0.184), rot=(90, 0, 0), seg=8), s)

    # --- card terminal with receipt printer on a swivel plate (low desk, customer side) ---
    ct = _empty_parent("Card terminal", (-5.82, -5.42, LOW_TOP_Z), 0)
    _child(cyl("Terminal swivel plate", 0.06, 0.012, M["graphite"], (0, 0, 0.006), seg=24), ct)
    body = _empty_parent("Terminal body", (0, 0, 0.012), 0)
    _child(body, ct)
    body.rotation_euler.x = math.radians(-7)
    _child(box("Terminal shell", (0.088, 0.205, 0.040), M["black"], (0, 0, 0.022), bevel=0.008), body)
    _child(img_plane("Terminal face", 0.078, 0.183, M["terminal"], (0, 0.004, 0.0435), facing="+z_flip"), body)
    paper = _child(box("Receipt paper", (0.050, 0.002, 0.06), M["paper"], (0, -0.093, 0.068)), body)
    paper.rotation_euler.x = math.radians(-14)

    # --- pen holder (staff side, between divider and file box) ---
    p = _empty_parent("Pen holder", (-5.12, -5.80, LOW_TOP_Z), 0)
    cup = lathe_mesh("Pen cup", [(0, 0.0), (0.034, 0.0), (0.034, 0.10), (0.031, 0.10), (0.031, 0.006),
                                 (0, 0.006)], [M["graphite"]], seg=20)
    _child(_inst("Pen cup", cup, (0, 0, 0)), p)
    pen_cols = [M["black"], M["lab_blue"], M["cap_red"], M["black"], M["white"]]
    for i, (dx, dy, tx, ty) in enumerate(((0.012, 0.0, 8, 3), (-0.01, 0.01, -6, 7), (0.0, -0.012, 4, -9),
                                           (-0.012, -0.006, -9, -4), (0.008, 0.012, 10, 6))):
        _child(cyl(f"Pen {i}", 0.0045, 0.145, pen_cols[i], (dx, dy, 0.074), rot=(tx, ty, 0), seg=8), p)

    # --- business-card holder (low desk, customer side) ---
    b = _empty_parent("Card holder", (-5.10, -5.36, LOW_TOP_Z), 0)
    _child(box("Card holder base", (0.10, 0.05, 0.008), M["acrylic"], (0, 0, 0.004), bevel=0.002), b)
    back = _child(box("Card holder back", (0.10, 0.004, 0.05), M["acrylic"], (0, -0.02, 0.031)), b)
    back.rotation_euler.x = math.radians(-15)
    stack = _empty_parent("Card stack", (0, -0.008, 0.008), 0)
    _child(stack, b)
    stack.rotation_euler.x = math.radians(-15)
    _child(box("Card stack paper", (0.09, 0.008, 0.052), M["paper"], (0, 0, 0.027)), stack)
    _child(img_plane("Card stack face", 0.088, 0.050, M["bizcard"], (0, 0.0055, 0.027), facing="+y"), stack)

    # --- small potted plant on the consultation desk (refs 190/192/194) ---
    pl = _empty_parent("Desk plant", (-4.22, -5.79, LOW_TOP_Z), 0)
    _child(box("Desk plant pot", (0.11, 0.11, 0.115), M["ceramic"], (0, 0, 0.0575), bevel=0.008, seg=3), pl)
    _child(box("Desk plant soil", (0.096, 0.096, 0.004), M["soil"], (0, 0, 0.108)), pl)
    leaf = blob_mesh("Desk leaf", (0.035, 0.07, 0.006), M["leaf"], subdiv=1, noise=0.0)
    rnd = random.Random(7)
    for i in range(11):
        a = i * 137.5
        r = 0.02 + 0.012 * (i % 3)
        z = 0.15 + 0.012 * i
        lx, ly = r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
        _child(_inst(f"Desk leaf {i}", leaf, (lx, ly, z), (rnd.uniform(25, 45), 0, a - 90 + rnd.uniform(-10, 10))), pl)
        _child(cyl(f"Desk stem {i}", 0.0025, z - 0.10, M["stem"], (lx * 0.5, ly * 0.5, 0.11 + (z - 0.11) / 2),
                   seg=5, smooth=False), pl)


def _floor_plant(M):
    """Tall rubber plant in a white square pot beside the counter (refs 160/166)."""
    pl = _empty_parent("Floor plant", (-3.86, -5.02, PAD_Z), 0)
    _child(box("Floor plant pot", (0.30, 0.30, 0.44), M["ceramic"], (0, 0, 0.22), bevel=0.012, seg=3), pl)
    _child(box("Floor plant soil", (0.27, 0.27, 0.006), M["soil"], (0, 0, 0.42)), pl)
    leaf = blob_mesh("Rubber leaf", (0.075, 0.16, 0.008), M["leaf"], subdiv=1, noise=0.0)
    rnd = random.Random(11)
    trunks = [(-0.03, 0.02, 1.25), (0.04, -0.02, 1.05), (0.0, 0.05, 0.85)]
    for ti, (tx, ty, top) in enumerate(trunks):
        _child(cyl(f"Plant trunk {ti}", 0.012, top - 0.42, M["stem"], (tx, ty, 0.42 + (top - 0.42) / 2),
                   rot=(rnd.uniform(-3, 3), rnd.uniform(-3, 3), 0), seg=8), pl)
        for k in range(9):
            z = top - 0.045 * k - rnd.uniform(0, 0.02)
            a = k * 137.5 + ti * 40
            r = 0.07   # leaf base sits on the trunk, blade points radially out and up
            lx = tx + r * math.cos(math.radians(a))
            ly = ty + r * math.sin(math.radians(a))
            _child(_inst(f"Rubber leaf {ti}_{k}", leaf, (lx, ly, z),
                         (rnd.uniform(30, 55), 0, a - 90 + rnd.uniform(-15, 15))), pl)


def _key_cabinet(M):
    """Locker-key board behind the check-in block: open wooden box with hooks + coloured spiral bands."""
    x0, x1, z0, z1 = -6.95, -6.45, 1.32, 1.78
    yb = WALL_FRONT_Y + 0.002
    d = 0.085
    cx, cz, w, h = (x0 + x1) / 2, (z0 + z1) / 2, x1 - x0, z1 - z0
    t = 0.016
    box("Keybox back", (w, 0.008, h), M["melamine"], (cx, yb + 0.004, cz))
    for sx in (x0 + t / 2, x1 - t / 2):
        box("Keybox side", (t, d, h), M["wood"], (sx, yb + d / 2, cz), bevel=0.002)
    for sz in (z0 + t / 2, z1 - t / 2):
        box("Keybox rail", (w - 2 * t - 0.001, d, t), M["wood"], (cx, yb + d / 2, sz), bevel=0.002)
    box("Keybox label board", (w - 2 * t - 0.001, 0.006, 0.05), M["black"], (cx, yb + d - 0.003, z1 - t - 0.026))
    img_plane("Keybox label", w - 0.06, 0.042, M["keybox_label"], (cx, yb + d + 0.0015, z1 - t - 0.026))
    hook_me = None
    bands = [torus_mesh("Key band " + c, 0.026, 0.0055, M["band_" + c]) for c in ("red", "blue", "yellow", "black")]
    tag_me = box_mesh("Key tag", (0.018, 0.004, 0.026), M["brass"])
    rows = (z1 - 0.10, z1 - 0.21, z1 - 0.32)
    n = 7
    for ri, hz in enumerate(rows):
        for k in range(n):
            hx = x0 + t + 0.035 + k * ((w - 2 * t - 0.07) / (n - 1))
            if hook_me is None:
                hook = cyl("Key hook", 0.0025, 0.045, M["chrome"], (hx, yb + 0.008 + 0.0225, hz), rot=(90, 0, 0), seg=6)
                hook_me = hook.data
            else:
                _inst("Key hook", hook_me, (hx, yb + 0.008 + 0.0225, hz), (90, 0, 0))
            if (ri * n + k) % 5 == 3:      # a few keys are out (members in the gym)
                continue
            band = bands[(ri * 3 + k) % 4]
            _inst("Key band", band, (hx, yb + 0.040, hz - 0.027), (90, 0, 0))
            _inst("Key tag", tag_me, (hx, yb + 0.040, hz - 0.066))


def _towel_shelf(M):
    """Wall-mounted 3x2 cubby shelf with folded towels behind the consultation desk (ref 187)."""
    x0, x1, z0, z1 = -5.00, -4.10, 1.40, 2.02
    yb = WALL_FRONT_Y + 0.002
    d = 0.30
    t = 0.018
    cx, w = (x0 + x1) / 2, x1 - x0
    box("Shelf back", (w, 0.006, z1 - z0), M["melamine"], (cx, yb + 0.003, (z0 + z1) / 2))
    for sz in (z0 + t / 2, (z0 + z1) / 2, z1 - t / 2):
        box("Shelf board", (w, d - 0.006, t), M["melamine"], (cx, yb + 0.006 + (d - 0.006) / 2, sz), bevel=0.002)
    xs = [x0 + t / 2, x0 + w / 3, x0 + 2 * w / 3, x1 - t / 2]
    for sx in xs:
        box("Shelf upright", (t, d - 0.006, z1 - z0 - 2 * t - 0.001), M["melamine"],
            (sx, yb + 0.006 + (d - 0.006) / 2, (z0 + z1) / 2), bevel=0.002)
    # folded towel: 4 layers visible as one rounded slab; shared meshes, two colours
    tw_grey = box_mesh("Folded towel grey", (0.235, 0.21, 0.034), M["towel_grey"])
    tw_white = box_mesh("Folded towel white", (0.235, 0.21, 0.034), M["towel_white"])
    for me in (tw_grey, tw_white):
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.012, segments=2, affect="EDGES")
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
        bm.free()
    rnd = random.Random(3)
    shelf_tops = (z0 + t, (z0 + z1) / 2 + t / 2)
    counts = ((7, 6, 5), (5, 7, 3))
    for si, zt in enumerate(shelf_tops):
        for ci in range(3):
            ccx = (xs[ci] + xs[ci + 1]) / 2
            for k in range(counts[si][ci]):
                me = tw_white if (si == 1 and ci == 0) or (k % 4 == 3) else tw_grey
                _inst("Folded towel", me, (ccx + rnd.uniform(-0.008, 0.008), yb + 0.006 + 0.125 + rnd.uniform(-0.01, 0.01),
                                            zt + 0.017 + k * 0.0345), (0, 0, rnd.uniform(-2.5, 2.5)))


def _drinks_fridge(M):
    """Single-door glass beverage showcase with protein drinks, right of the louver screen."""
    X0, X1 = -3.53, -3.01
    Yb = WALL_FRONT_Y + 0.04
    D = 0.52
    Yf = Yb + D
    cx, cy = (X0 + X1) / 2, Yb + D / 2
    w = X1 - X0
    t = 0.03
    for nm, sx in (("left", X0 + t / 2), ("right", X1 - t / 2)):
        box(f"Fridge side {nm}", (t, D, 1.24), M["black"], (sx, cy, 0.03 + 0.62), bevel=0.004)
    box("Fridge top", (w - 2 * t, D, t), M["black"], (cx, cy, 1.27 - t / 2))
    box("Fridge plinth", (w - 2 * t, D, 0.10), M["black"], (cx, cy, 0.08))
    box("Fridge back light panel", (w - 2 * t, 0.02, 1.01), M["fridge_light"], (cx, Yb + 0.01, 0.13 + 0.505 + 0.001))
    box("Fridge header", (w - 2 * t, 0.03, 0.10), M["black"], (cx, Yf - 0.015, 1.19))
    img_plane("Fridge header print", w - 0.07, 0.085, M["fridge_header"], (cx, Yf + 0.0015, 1.19))
    box("Fridge kick grille", (w - 0.10, 0.004, 0.05), M["graphite"], (cx, Yf + 0.002, 0.08))
    for fx in (X0 + 0.04, X1 - 0.04):
        for fy in (Yb + 0.04, Yf - 0.04):
            cyl("Fridge foot", 0.016, 0.03, M["graphite"], (fx, fy, 0.015), seg=10)
    # Door (proud of the carcass by 2.5 cm): frame bars + glass
    yd = Yf + 0.0125
    fw = 0.04
    box("Fridge door stile L", (fw, 0.025, 1.01), M["black"], (X0 + fw / 2, yd, 0.635), bevel=0.003)
    box("Fridge door stile R", (fw, 0.025, 1.01), M["black"], (X1 - fw / 2, yd, 0.635), bevel=0.003)
    box("Fridge door rail top", (w - 2 * fw - 0.001, 0.025, 0.04), M["black"], (cx, yd, 1.12), bevel=0.003)
    box("Fridge door rail bottom", (w - 2 * fw - 0.001, 0.025, 0.04), M["black"], (cx, yd, 0.15), bevel=0.003)
    box("Fridge glass", (w - 2 * fw + 0.01, 0.006, 0.94), M["glass"], (cx, yd, 0.635))
    hx = X1 - fw / 2
    box("Fridge handle", (0.016, 0.022, 0.42), M["alu"], (hx, yd + 0.0125 + 0.024 + 0.011, 0.66), bevel=0.004)
    for hz in (0.47, 0.85):
        box("Fridge handle post", (0.012, 0.024, 0.02), M["alu"], (hx, yd + 0.0125 + 0.012, hz))
    # Shelves and drinks
    sh_w, sh_d = w - 2 * t - 0.004, D - 0.06
    levels = [0.13, 0.40, 0.66, 0.92]
    for lz in levels[1:]:
        box("Fridge wire shelf", (sh_w, sh_d, 0.008), M["wire"], (cx, Yb + 0.03 + sh_d / 2, lz - 0.004))
    glass_body = M["white"]
    bottle_profile = [(0, 0), (0.030, 0), (0.032, 0.006), (0.032, 0.115), (0.024, 0.140), (0.014, 0.150),
                      (0.014, 0.160), (0.016, 0.160), (0.016, 0.178), (0, 0.178)]
    #            seg idx:   0    1      2      3      4      5      6      7      8
    def bottle(label, cap):
        return lathe_mesh("Protein bottle " + label.name, bottle_profile, [glass_body, label, cap], seg=14,
                          mat_idx=[0, 0, 1, 0, 0, 0, 2, 2, 2])
    can_profile = [(0, 0), (0.028, 0), (0.033, 0.012), (0.033, 0.108), (0.029, 0.122), (0, 0.122)]
    def can(label):
        return lathe_mesh("Protein can " + label.name, can_profile, [M["alu"], label], seg=16,
                          mat_idx=[0, 1, 1, 0, 0])
    kinds = [bottle(M["lab_choco"], M["lab_choco"]), bottle(M["lab_vanilla"], M["lab_blue"]),
             bottle(M["lab_banana"], M["lab_banana"]), can(M["lab_blue"])]
    per_row = 5
    for li, lz in enumerate(levels):
        me = kinds[[3, 0, 1, 2][li]]
        for row, yy in enumerate((Yf - 0.09, Yf - 0.18, Yf - 0.27)):
            for k in range(per_row):
                if li == 3 and row == 0 and k == 1:
                    continue  # one sold
                xx = X0 + t + 0.045 + k * ((sh_w - 0.09) / (per_row - 1))
                _inst("Protein drink", me, (xx, yy, lz + 0.0005), (0, 0, k * 37.0))


def _towel_bin(M):
    """Beige plastic return bin with used towels (ref 260) + wall sign above it."""
    cx, cy = -2.33, WALL_FRONT_Y + 0.04 + 0.21
    prof = [(0, 0.0), (0.19, 0.0), (0.19, 0.01), (0.212, 0.62), (0.218, 0.625), (0.218, 0.64), (0.204, 0.64),
            (0.198, 0.62), (0.178, 0.018), (0, 0.018)]
    me = lathe_mesh("Towel bin shell", prof, [M["bin_beige"]], seg=32)
    _inst("Towel bin", me, (cx, cy, 0.0))
    rnd = random.Random(5)
    mats = [M["towel_grey"], M["towel_grey"], M["towel_white"], M["towel_grey"], M["towel_white"]]
    for i in range(5):
        a = i * 72 + rnd.uniform(-15, 15)
        r = 0.07 + rnd.uniform(0, 0.04)
        blob = blob_mesh(f"Used towel {i}", (0.26, 0.20, 0.10), mats[i], subdiv=2, noise=0.22, seed=i + 1)
        _inst("Used towel", blob, (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)),
                                   0.56 + 0.02 * (i % 2)), (rnd.uniform(-15, 15), rnd.uniform(-15, 15), a))
    # A5 acrylic sign on the wall above
    box("Towel sign backer", (0.22, 0.004, 0.158), M["acrylic"], (cx, WALL_FRONT_Y + 0.004, 1.02))
    img_plane("Towel sign print", 0.21, 0.148, M["towel_sign"], (cx, WALL_FRONT_Y + 0.0075, 1.02))
    for sx in (-0.095, 0.095):
        for sz in (-0.064, 0.064):
            cyl("Sign standoff", 0.006, 0.012, M["chrome"], (cx + sx, WALL_FRONT_Y + 0.008, 1.02 + sz),
                rot=(90, 0, 0), seg=10)


def _notice_frames(M):
    """A2 aluminium snap frames: 가격표 + 운영시간 on the front wall beside the counter."""
    for nm, fx, mat in (("price", -3.27, M["price"]), ("hours", -2.77, M["hours"])):
        fz, fw, fh = 1.80, 0.42, 0.594
        yb = WALL_FRONT_Y
        box(f"Frame {nm} backing", (fw, 0.008, fh), M["white"], (fx, yb + 0.005, fz))
        img_plane(f"Frame {nm} print", fw - 0.004, fh - 0.004, mat, (fx, yb + 0.0105, fz))
        bw, bd = 0.022, 0.016
        box(f"Frame {nm} top", (fw + 2 * bw, bd, bw), M["alu"], (fx, yb + 0.001 + bd / 2, fz + fh / 2 + bw / 2), bevel=0.004)
        box(f"Frame {nm} bottom", (fw + 2 * bw, bd, bw), M["alu"], (fx, yb + 0.001 + bd / 2, fz - fh / 2 - bw / 2), bevel=0.004)
        box(f"Frame {nm} left", (bw, bd, fh), M["alu"], (fx - fw / 2 - bw / 2, yb + 0.001 + bd / 2, fz), bevel=0.004)
        box(f"Frame {nm} right", (bw, bd, fh), M["alu"], (fx + fw / 2 + bw / 2, yb + 0.001 + bd / 2, fz), bevel=0.004)


def _slipper_rack(M):
    """Low 2-tier slipper rack just inside the entrance, against the entrance wall."""
    X0, X1 = WALL_LEFT_X + 0.006, -7.245
    Y0, Y1 = -4.62, -3.98
    cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
    post = 0.018
    for px in (X0 + post / 2, X1 - post / 2):
        for py in (Y0 + post / 2, Y1 - post / 2):
            box("Rack post", (post, post, 0.34), M["rack"], (px, py, 0.17), bevel=0.003)
    for tz in (0.06, 0.26):
        for py in (Y0 + post / 2, Y1 - post / 2):
            box("Rack end rail", (X1 - X0 - 2 * post, post, post), M["rack"], (cx, py, tz))
        for k in range(4):
            sx = X0 + post + 0.02 + k * ((X1 - X0 - 2 * post - 0.04) / 3)
            box("Rack slat", (0.012, Y1 - Y0 - 2 * post, 0.012), M["chrome"], (sx, cy, tz + 0.003))
    box("Rack top rail", (X1 - X0, Y1 - Y0, 0.016), M["rack"], (cx, cy, 0.348), bevel=0.003)
    img_plane("Rack sign", 0.24, 0.06, M["slipper_sign"], (WALL_LEFT_X + 0.0015, cy, 0.56), rot=(0, 0, -90))
    # slide slippers (toe into the rack, heel toward the room)
    sole = box_mesh("Slipper sole", (0.255, 0.092, 0.024), M["eva_sole"])
    for me, off in ((sole, 0.0),):
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.010, segments=2, affect="EDGES")
        bm.to_mesh(me)
        bm.free()
    straps = {}
    for key in ("eva_navy", "eva_grey"):
        st = box_mesh("Slipper strap " + key, (0.10, 0.10, 0.04), M[key])
        bm = bmesh.new()
        bm.from_mesh(st)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.016, segments=3, affect="EDGES")
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(st)
        bm.free()
        straps[key] = st
    rnd = random.Random(9)
    for tz in (0.06 + 0.009, 0.26 + 0.009):   # slat tops
        for pi in range(3):
            key = ("eva_navy", "eva_grey")[(pi + int(tz > 0.1)) % 2]
            pcy = Y0 + 0.11 + pi * 0.21
            for side in (-1, 1):
                sx = cx + 0.035 + rnd.uniform(-0.008, 0.008)
                sy = pcy + side * 0.05
                rz = rnd.uniform(-4, 4)
                _inst("Slipper sole", sole, (sx, sy, tz + 0.012), (0, 0, rz))
                _inst("Slipper strap", straps[key], (sx - 0.06, sy, tz + 0.024 + 0.012), (0, 0, rz))


# --------------------------------------------------------------------------------------------
def _clear():
    c = bpy.data.collections.get(COLL)
    if not c:
        return
    meshes = set()
    lights = set()
    for ob in list(c.all_objects):
        if ob.type == "MESH":
            meshes.add(ob.data)
        elif ob.type == "LIGHT":
            lights.add(ob.data)
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    for ld in lights:
        if ld.users == 0:
            bpy.data.lights.remove(ld)


def apply() -> dict:
    global _ROOT, _C, _ADDED
    _clear()
    parent = bpy.data.collections.get("SET")
    _C = bpy.data.collections.get(COLL)
    if _C is None:
        _C = bpy.data.collections.new(COLL)
        (parent or bpy.context.scene.collection).children.link(_C)
    _ROOT = bpy.data.objects.get("Gym_InfoDesk")   # follow the desk if the integrator moves it
    _ADDED = []
    M = _materials()
    _led_strips(M)
    _desk_props(M)
    _floor_plant(M)
    _key_cabinet(M)
    _towel_shelf(M)
    _drinks_fridge(M)
    _towel_bin(M)
    _notice_frames(M)
    _slipper_rack(M)

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in _C.all_objects:
        if ob.type == "MESH":
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            tris += len(me.loop_triangles)
            ev.to_mesh_clear()
    return {
        "collection": COLL,
        "objects_added": len(_C.all_objects),
        "triangles_added": tris,
        "existing_objects_touched": [],
        "parent": _ROOT.name if _ROOT else None,
    }


if __name__ == "__main__" and (bpy is None or "--textures" in sys.argv):
    if bpy is None:
        make_textures()
