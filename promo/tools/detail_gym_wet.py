"""Detail package `gym_wet`: showers and restrooms of both locker suites (gym_locker_suites.py).

Run inside Blender (scene_gym.blend open):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_gym_wet; detail_gym_wet.apply()

Regenerate the printed decals (PIL, outside Blender):
    ~/.venvs/pdf/bin/python promo/tools/detail_gym_wet.py --textures

Reference photos (work/refs/interior):
  026  per-booth white wall dispenser beside the mixer, dark matte 300x300 anti-slip floor tile, light wall tile
  041  dispenser/mirror per booth, square ceiling exhaust grille, striped mat at the shower door
  042  grey textured wall + floor tile with visible grout, linear drain, round mirror per booth
  046  black matte floor tile with light grout and a square stainless floor drain, 300x600 wall tile
  047  wooden duckboard at the shower entry, hooks + towel
  049/050  booth fronts, linear/square drains, square ceiling exhaust diffuser
  021/025/027/040/043/044/048  booth numbering, towels on hooks, shelf bottles, white tile with dark grout
  061/063/064/069/070  restroom vanity (under-counter LED glow, paper towel dispenser by the mirror,
           marble walls), signage, pictograms
Korean public-restroom conventions (cleaning checklist on the cleaning cabinet, "휴지는 변기에" notice,
"한 걸음 더 가까이" urinal sticker, sanitary pad vending box + sanitary bin label in the women's room,
yellow wet-floor A-frame, plastic bath stools + basin) follow common Korean gym/bathhouse practice.

Suite frame (from gym_locker_suites): u = distance from the central partition face toward the outer wall,
Men x = 11.55 - u, Women x = 11.65 + u; shower u 0..2.00, restroom u 2.10..4.15, y -10.55..-15.30.
Existing objects touched (material swap only, object-linked slot, original kept in custom props):
  {Men,Women} Floor shower                -> D gym_wet anti-slip 300x300 matte tile
  {Men,Women} shower walls (marble)        -> same marble look with wider, darker grout so tiles read
"""
import math
import os
import sys

try:
    import bpy
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
except ImportError:  # texture generation runs outside Blender
    bpy = None

KEY = "gym_wet"
COLL = "DETAIL_gym_wet"
PFX = "Dgym_wet_"
HERE = os.path.dirname(os.path.abspath(__file__))
PART_DIR = os.path.normpath(os.path.join(HERE, "..", "parts", "detail_gym_wet"))
FONT = os.path.normpath(os.path.join(HERE, "..", "parts", "fonts", "NanumGothic-Bold.ttf"))

# Suite constants (mirrors gym_locker_suites, read-only)
PART_X, PART_T = 11.60, 0.10
WIDTH = 4.15
Y_IN = -10.55          # shower / restroom side face of the locker back wall
Y_BACK = -15.30
CEIL_TILE_Z = 2.985    # underside of the tiled ceiling in shower / restroom
U_SHOWER_IN = 2.00     # shower side face of the divider wall
U_WC_IN = 2.10         # restroom side face of the divider wall
BOOTH_Y = (-12.30, -13.30, -14.30, -15.30)
BOOTH_D = 1.05
CUBE_U = (2.10, 3.125, 4.15)
CUBE_Y = -13.80
SUITES = (("Men", -1), ("Women", 1))


# --------------------------------------------------------------------------------------------
# Texture generation (PIL) -------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def make_textures():
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(PART_DIR, exist_ok=True)

    def F(sz):
        return ImageFont.truetype(FONT, sz)

    INK = (28, 28, 30)

    def ctext(d, cx, y, text, font, fill):
        w = d.textlength(text, font=font)
        d.text((cx - w / 2, y), text, font=font, fill=fill)

    def save(im, name):
        im.save(os.path.join(PART_DIR, name))

    # 1) 3-chamber wall dispenser face (0.30 x 0.20 m): white ABS, three smoked windows with liquid, labels
    W, H = 600, 400
    im = Image.new("RGB", (W, H), (238, 238, 236))
    d = ImageDraw.Draw(im)
    liquids = [((236, 168, 60), "샴푸", "SHAMPOO"), ((240, 236, 226), "린스", "CONDITIONER"),
               ((120, 196, 120), "바디워시", "BODY WASH")]
    for i, (col, ko, en) in enumerate(liquids):
        x0 = 22 + i * 192
        d.rounded_rectangle([x0, 40, x0 + 172, 300], 18, fill=(200, 202, 204))
        d.rounded_rectangle([x0 + 10, 50, x0 + 162, 290], 14, fill=(70, 74, 78))
        level = (150, 110, 190)[i]
        d.rounded_rectangle([x0 + 14, level, x0 + 158, 286], 10, fill=col)
        d.rectangle([x0 + 20, level, x0 + 34, 280], fill=tuple(min(255, c + 30) for c in col))
        ctext(d, x0 + 86, 312, ko, F(34), INK)
        ctext(d, x0 + 86, 354, en, F(18), (110, 112, 116))
    d.rectangle([0, 0, W, 22], fill=(214, 216, 216))
    save(im, "disp_front.png")

    # 2) Booth number plates (brushed steel, black numerals)
    for n in (1, 2, 3):
        im = Image.new("RGB", (200, 200), (178, 180, 182))
        d = ImageDraw.Draw(im)
        for y in range(0, 200, 3):
            d.line([0, y, 200, y], fill=(168 + (y * 7) % 18, 170 + (y * 7) % 18, 172 + (y * 7) % 18))
        d.ellipse([12, 12, 188, 188], outline=(60, 60, 64), width=6)
        ctext(d, 100, 40, f"{n:02d}", F(96), INK)
        save(im, f"booth_{n}.png")

    # 3) Shower room rules (acrylic sign, 0.40 x 0.30 m)
    W, H = 800, 600
    im = Image.new("RGB", (W, H), (250, 250, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 120], fill=(22, 84, 150))
    ctext(d, W / 2, 26, "샤워실 이용 안내", F(60), (255, 255, 255))
    rules = ["샤워 후 물기를 닦고 나가 주세요", "샴푸·바디워시는 각 부스에 있습니다",
             "사용한 수건은 수거함에 넣어 주세요", "바닥이 미끄러우니 뛰지 마세요",
             "개인 용품은 사물함에 보관해 주세요"]
    y = 150
    for r in rules:
        d.ellipse([52, y + 14, 70, y + 32], fill=(22, 84, 150))
        d.text((92, y), r, font=F(38), fill=INK)
        y += 78
    ctext(d, W / 2, 560, "WATCHCOACH GYM", F(26), (120, 120, 124))
    save(im, "shower_rules.png")

    # 4) Wet-floor A-frame face (0.28 x 0.56 m)
    W, H = 400, 800
    im = Image.new("RGB", (W, H), (246, 196, 18))
    d = ImageDraw.Draw(im)
    d.polygon([(200, 70), (360, 340), (40, 340)], fill=INK)
    d.polygon([(200, 105), (330, 322), (70, 322)], fill=(246, 196, 18))
    # slipping figure
    d.ellipse([178, 170, 208, 200], fill=INK)
    d.line([(192, 205), (210, 260)], fill=INK, width=14)
    d.line([(210, 260), (250, 300)], fill=INK, width=12)
    d.line([(210, 260), (170, 300)], fill=INK, width=12)
    d.line([(196, 220), (150, 210)], fill=INK, width=10)
    d.line([(198, 222), (245, 235)], fill=INK, width=10)
    d.line([(110, 312), (290, 312)], fill=INK, width=6)
    ctext(d, W / 2, 390, "미끄럼 주의", F(64), INK)
    ctext(d, W / 2, 480, "CAUTION", F(56), INK)
    ctext(d, W / 2, 550, "WET FLOOR", F(52), INK)
    ctext(d, W / 2, 640, "바닥이 젖어 있습니다", F(32), INK)
    save(im, "wetfloor.png")

    # 5) Restroom cleaning checklist (A4 in a sleeve)
    W, H = 630, 891
    im = Image.new("RGB", (W, H), (252, 252, 250))
    d = ImageDraw.Draw(im)
    ctext(d, W / 2, 30, "화장실 청소 점검표", F(46), INK)
    d.text((40, 100), "11월   담당: 시설관리", font=F(24), fill=(80, 80, 84))
    cols = [40, 150, 270, 390, 510, 590]
    heads = ["시간", "바닥", "변기", "세면대", "확인"]
    y0 = 140
    d.rectangle([40, y0, 590, y0 + 44], fill=(225, 230, 236))
    for i, h in enumerate(heads):
        ctext(d, (cols[i] + cols[i + 1]) / 2, y0 + 8, h, F(24), INK)
    times = ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00", "23:00"]
    rh = 72
    for r, t in enumerate(times):
        y = y0 + 44 + r * rh
        ctext(d, (cols[0] + cols[1]) / 2, y + 22, t, F(24), INK)
        if r < 6:  # filled in up to the afternoon
            for c in (1, 2, 3):
                cx, cy = (cols[c] + cols[c + 1]) / 2, y + rh / 2
                d.line([(cx - 14, cy), (cx - 3, cy + 12), (cx + 16, cy - 14)], fill=(30, 60, 160), width=5)
            cx = (cols[4] + cols[5]) / 2
            d.line([(cx - 26, y + 44), (cx - 10, y + 24), (cx + 4, y + 46), (cx + 24, y + 26)], fill=(30, 60, 160), width=4)
    for c in cols:
        d.line([c, y0, c, y0 + 44 + len(times) * rh], fill=(90, 90, 96), width=2)
    for r in range(len(times) + 2):
        yy = y0 + (0 if r == 0 else 44 + (r - 1) * rh)
        d.line([40, yy, 590, yy], fill=(90, 90, 96), width=2)
    save(im, "checklist.png")

    # 6) Cleaning cabinet label
    im = Image.new("RGB", (600, 150), (250, 250, 248))
    d = ImageDraw.Draw(im)
    ctext(d, 300, 22, "청소도구함", F(70), INK)
    d.rectangle([0, 0, 599, 149], outline=(40, 40, 44), width=6)
    save(im, "cabinet_label.png")

    # 7) Toilet notice
    W, H = 630, 450
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 110], fill=(30, 150, 120))
    ctext(d, W / 2, 26, "휴지는 변기에", F(56), (255, 255, 255))
    ctext(d, W / 2, 150, "사용한 화장지는 변기에 버리고", F(34), INK)
    ctext(d, W / 2, 205, "물을 내려 주세요.", F(34), INK)
    ctext(d, W / 2, 285, "물티슈·생리대는 휴지통에", F(34), (200, 40, 40))
    ctext(d, W / 2, 380, "깨끗한 화장실, 함께 지켜요", F(28), (110, 110, 114))
    save(im, "toilet_notice.png")

    # 8) Urinal sticker
    W, H = 600, 420
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, W - 10, H - 10], 40, outline=(22, 84, 150), width=10)
    ctext(d, W / 2, 60, "한 걸음 더 가까이", F(62), (22, 84, 150))
    ctext(d, W / 2, 170, "남자가 흘리지 말아야 할 것은", F(34), INK)
    ctext(d, W / 2, 225, "눈물만이 아닙니다", F(34), INK)
    d.polygon([(300, 300), (340, 360), (260, 360)], fill=(22, 84, 150))
    save(im, "urinal_notice.png")

    # 9) Sanitary pad vending box (0.32 x 0.45 m)
    W, H = 640, 900
    im = Image.new("RGB", (W, H), (246, 244, 242))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 170], fill=(222, 92, 132))
    ctext(d, W / 2, 30, "생리대 자판기", F(58), (255, 255, 255))
    ctext(d, W / 2, 110, "SANITARY PADS", F(32), (255, 236, 242))
    d.rounded_rectangle([70, 230, 570, 560], 20, fill=(200, 200, 204))
    d.rounded_rectangle([90, 250, 550, 540], 16, fill=(90, 94, 100))
    for i in range(3):
        d.rectangle([120 + i * 140, 300, 220 + i * 140, 500], fill=(250, 210, 226))
    for i, t in enumerate(("중형", "대형", "오버")):
        ctext(d, 170 + i * 140, 385, t, F(30), (150, 40, 80))
    d.rounded_rectangle([250, 610, 390, 650], 10, fill=(40, 40, 44))
    ctext(d, W / 2, 680, "500원 동전 / 무료 비치", F(30), INK)
    d.rounded_rectangle([200, 760, 440, 840], 14, fill=(60, 62, 66))
    save(im, "sanitary_vend.png")

    # 10) Sanitary bin label
    im = Image.new("RGB", (300, 150), (250, 214, 226))
    d = ImageDraw.Draw(im)
    ctext(d, 150, 28, "위생용품", F(44), (150, 40, 80))
    ctext(d, 150, 86, "수거함", F(40), (150, 40, 80))
    save(im, "sanitary_label.png")
    print("textures ->", PART_DIR)


# --------------------------------------------------------------------------------------------
# Blender side -------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
_C = None


def _sx(s, u):
    x0 = PART_X + s * PART_T / 2
    return x0 + s * u


def _new_mesh(name, bm, mat, parent, loc=(0, 0, 0), rot=(0, 0, 0), smooth=False):
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, me)
    _C.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def _bevel(ob, w, seg=2):
    if w <= 0:
        return ob
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width = w
    bv.segments = seg
    bv.limit_method = "ANGLE"
    bv.harden_normals = False
    return ob


def box(name, size, mat, parent, loc, rot=(0, 0, 0), bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = _new_mesh(name, bm, mat, parent, loc, rot)
    return _bevel(ob, min(bevel, min(size) * 0.45))


def cyl(name, r, h, mat, parent, loc, rot=(0, 0, 0), seg=16, r2=None, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    ob = _new_mesh(name, bm, mat, parent, loc, rot)
    for p in ob.data.polygons:
        p.use_smooth = smooth and len(p.vertices) == 4
    return ob


def frustum(name, bot, top, h, mat, parent, loc, rot=(0, 0, 0), bevel=0.0):
    """Rectangular frustum: bottom (w, d) at z 0, top (w, d) at z h (local origin at the bottom centre)."""
    bm = bmesh.new()
    vs = [bm.verts.new((sx * w / 2, sy * d / 2, z)) for (w, d), z in ((bot, 0.0), (top, h))
          for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = _new_mesh(name, bm, mat, parent, loc, rot)
    return _bevel(ob, bevel, 3)


def lathe(name, profile, mat, parent, loc, seg=24, rot=(0, 0, 0), cap_bottom=True):
    """Revolve [(r, z), ...] (bottom to top) around local Z. Open top; outer and inner walls come from the profile."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r < 1e-5:
            rings.append([bm.verts.new((0, 0, z))])
            continue
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z))
                      for i in range(seg)])
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 or len(b) == 1:
            ring, c = (b, a[0]) if len(a) == 1 else (a, b[0])
            for i in range(seg):
                bm.faces.new((ring[i], ring[(i + 1) % seg], c) if len(a) == 1 else (ring[(i + 1) % seg], ring[i], c))
            continue
        for i in range(seg):
            bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = _new_mesh(name, bm, mat, parent, loc, rot, smooth=True)
    return ob


def quad(name, w, h, mat, parent, loc, rot=(0, 0, 0)):
    """Decal facing local +Y, image upright and readable from +Y (UV 0..1)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new(p) for p in ((w / 2, 0, -h / 2), (-w / 2, 0, -h / 2), (-w / 2, 0, h / 2), (w / 2, 0, h / 2))]
    f = bm.faces.new(vs)
    for loop, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = t
    return _new_mesh(name, bm, mat, parent, loc, rot)


def frame(tag, s, name, u, y, face, z=0.0):
    """Empty whose local +Y points `face` ('+u', '-u', '+y', '-y'); same convention as gym_locker_suites."""
    rot = {"+u": -s * 90, "-u": s * 90, "+y": 0, "-y": 180}[face]
    e = bpy.data.objects.new(f"{PFX}{tag} {name}", None)
    e.empty_display_size = 0.1
    _C.objects.link(e)
    e.location = (_sx(s, u), y, z)
    e.rotation_euler.z = math.radians(rot)
    return e


# ------------------------------------------------------------------ materials


def _pbsdf(name, color, rough=0.5, metal=0.0, alpha=None, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color[:3], 1)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color[:3], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            pass
    if emit:
        b.inputs["Emission Color"].default_value = (*color[:3], 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def _img(fname):
    path = os.path.join(PART_DIR, fname)
    im = bpy.data.images.load(path, check_existing=True)
    if not im.packed_file:
        try:
            im.pack()
        except RuntimeError:
            pass
    return im


def _decal(name, fname, rough=0.35, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _img(fname)
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    if emit:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = (0.8, 0.8, 0.8, 1)
    return m


def _world_xy(N, L, axes):
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    L.new(sep.outputs[axes[0]], comb.inputs["X"])
    L.new(sep.outputs[axes[1]], comb.inputs["Y"])
    return comb.outputs[0]


def _antislip_tile(name):
    """Matte anti-slip porcelain floor tile (refs 026/046): 300x300 charcoal tiles, light 4 mm grout,
    per-tile tone variation, fine grit bump."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    base = (0.062, 0.064, 0.070)
    m = _pbsdf(name, base, rough=0.78)
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    vec = _world_xy(N, L, "XY")
    br = N.new("ShaderNodeTexBrick")
    br.offset = 0.0
    L.new(vec, br.inputs["Vector"])
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 0.30
    br.inputs["Row Height"].default_value = 0.30
    br.inputs["Mortar Size"].default_value = 0.004
    br.inputs["Mortar Smooth"].default_value = 0.2
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (*base, 1)
    br.inputs["Color2"].default_value = (0.078, 0.080, 0.086, 1)
    br.inputs["Mortar"].default_value = (0.36, 0.36, 0.35, 1)
    # grit speckle
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0
    nz.inputs["Detail"].default_value = 2.0
    L.new(vec, nz.inputs["Vector"])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = "MULTIPLY"
    ins = {s.identifier: s for s in mx.inputs}
    ins["Factor_Float"].default_value = 0.35
    L.new(br.outputs["Color"], ins["A_Color"])
    L.new(nz.outputs["Color"], ins["B_Color"])
    L.new(next(s for s in mx.outputs if s.identifier == "Result_Color"), b.inputs["Base Color"])
    # grout roughness: grout a bit rougher
    rmap = N.new("ShaderNodeMapRange")
    rmap.inputs["To Min"].default_value = 0.74
    rmap.inputs["To Max"].default_value = 0.92
    L.new(br.outputs["Fac"], rmap.inputs["Value"])
    L.new(rmap.outputs["Result"], b.inputs["Roughness"])
    # bumps: grit, then grout recess
    bg = N.new("ShaderNodeBump")
    bg.inputs["Strength"].default_value = 0.25
    bg.inputs["Distance"].default_value = 0.0004
    L.new(nz.outputs["Fac"], bg.inputs["Height"])
    bt = N.new("ShaderNodeBump")
    bt.invert = True
    bt.inputs["Strength"].default_value = 0.6
    bt.inputs["Distance"].default_value = 0.002
    L.new(br.outputs["Fac"], bt.inputs["Height"])
    L.new(bg.outputs["Normal"], bt.inputs["Normal"])
    L.new(bt.outputs["Normal"], b.inputs["Normal"])
    return m


def _wall_marble(name, axes):
    """Shower wall marble with readable grout: same porcelain look as the suite builder, but 4 mm darker grout."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    import gym_locker_suites as G
    return G._stone_mat(name, base=(0.80, 0.80, 0.78), vein=(0.50, 0.51, 0.52), grout=(0.46, 0.46, 0.45),
                        tile_w=0.60, tile_h=1.20, axes=axes, rough=0.10, grout_w=0.004)


def _materials():
    ex = bpy.data.materials.get
    M = {
        "abs": _pbsdf(PFX + "WhiteABS", (0.84, 0.84, 0.83), 0.32),
        "chrome": ex("Suite_Chrome") or _pbsdf(PFX + "Chrome", (0.72, 0.73, 0.74), 0.12, 1.0),
        "steel": ex("Suite_BrushedSteel") or _pbsdf(PFX + "Steel", (0.60, 0.61, 0.62), 0.30, 1.0),
        "grate": ex("Suite_DrainGrate") or _pbsdf(PFX + "Grate", (0.55, 0.56, 0.57), 0.3, 1.0),
        "dark": _pbsdf(PFX + "DarkSlot", (0.012, 0.012, 0.014), 0.7),
        "towel": ex("Suite_TowelWhite") or _pbsdf(PFX + "Towel", (0.84, 0.84, 0.82), 0.95),
        "towel_grey": _pbsdf(PFX + "TowelGrey", (0.30, 0.31, 0.33), 0.95),
        "stool_m": _pbsdf(PFX + "StoolBlue", (0.20, 0.42, 0.62), 0.38),
        "stool_w": _pbsdf(PFX + "StoolPink", (0.78, 0.36, 0.45), 0.38),
        "basin": _pbsdf(PFX + "BasinWhite", (0.80, 0.80, 0.78), 0.30),
        "rubber": _pbsdf(PFX + "BlackRubber", (0.02, 0.02, 0.022), 0.6),
        "squeegee": _pbsdf(PFX + "SqueegeeGreen", (0.10, 0.36, 0.20), 0.45),
        "teak": _pbsdf(PFX + "Teak", (0.30, 0.16, 0.07), 0.55),
        "yellow": _pbsdf(PFX + "SafetyYellow", (0.80, 0.52, 0.02), 0.40),
        "cabinet": _pbsdf(PFX + "CabinetGrey", (0.36, 0.37, 0.38), 0.45, 0.3),
        "mop": _pbsdf(PFX + "MopCotton", (0.70, 0.68, 0.62), 0.95),
        "bucket": _pbsdf(PFX + "BucketBlue", (0.05, 0.20, 0.45), 0.40),
        "water": _pbsdf(PFX + "GreyWater", (0.12, 0.13, 0.12), 0.05),
        "roll": _pbsdf(PFX + "PaperRoll", (0.86, 0.86, 0.84), 0.95),
        "led": W_shadeless(PFX + "UnderCounterLED", (1.0, 0.82, 0.60), 3.0),
        "backer": _pbsdf(PFX + "SignBacker", (0.62, 0.63, 0.64), 0.25, 0.6),
        "smoke": _pbsdf(PFX + "SmokeWindow", (0.08, 0.09, 0.10), 0.1),
        "d_disp": _decal(PFX + "DispenserFace", "disp_front.png", 0.30),
        "d_rules": _decal(PFX + "ShowerRules", "shower_rules.png", 0.20),
        "d_wet": _decal(PFX + "WetFloorFace", "wetfloor.png", 0.40),
        "d_check": _decal(PFX + "Checklist", "checklist.png", 0.60),
        "d_cab": _decal(PFX + "CabinetLabel", "cabinet_label.png", 0.40),
        "d_toilet": _decal(PFX + "ToiletNotice", "toilet_notice.png", 0.25),
        "d_urinal": _decal(PFX + "UrinalNotice", "urinal_notice.png", 0.25),
        "d_vend": _decal(PFX + "SanitaryVend", "sanitary_vend.png", 0.30),
        "d_sanlabel": _decal(PFX + "SanitaryLabel", "sanitary_label.png", 0.40),
        "antislip": _antislip_tile(PFX + "AntiSlipTile"),
        "marble_yz": _wall_marble(PFX + "ShowerMarble_YZ", "YZ"),
        "marble_xz": _wall_marble(PFX + "ShowerMarble_XZ", "XZ"),
    }
    for n in (1, 2, 3):
        M[f"d_booth{n}"] = _decal(PFX + f"BoothNo{n}", f"booth_{n}.png", 0.25)
    return M


def W_shadeless(name, color, strength):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (*color, 1)
    return m


# ------------------------------------------------------------------ existing-object edits (material swaps)


def _swap(ob, mat):
    """Object-linked material on slot 0; the mesh and the original material stay untouched. Re-runs don't stack."""
    if ob is None or not ob.material_slots:
        return None
    slot = ob.material_slots[0]
    if ob.get("detail_pkg") != KEY:
        ob["detail_pkg"] = KEY
        ob["dwet_orig_link"] = slot.link
        ob["dwet_orig_mat"] = slot.material.name if slot.material else ""
    slot.link = "OBJECT"
    slot.material = mat
    return ob.name


def restore_existing():
    """Undo the material swaps (for the integrator)."""
    for ob in bpy.data.objects:
        if ob.get("detail_pkg") == KEY and "dwet_orig_link" in ob:
            slot = ob.material_slots[0]
            slot.material = None
            slot.link = ob["dwet_orig_link"]
            for k in ("detail_pkg", "dwet_orig_link", "dwet_orig_mat"):
                del ob[k]


def _wet_surfaces(M):
    touched = []
    for tag, s in SUITES:
        touched.append(_swap(bpy.data.objects.get(f"{tag} Floor shower"), M["antislip"]))
        for n in ("Partition shower", "Divider wall shower side"):
            touched.append(_swap(bpy.data.objects.get(f"{tag} {n}"), M["marble_yz"]))
        touched.append(_swap(bpy.data.objects.get(f"{tag} Back wall shower"), M["marble_xz"]))
        for ob in bpy.data.objects:
            if ob.name.startswith(f"{tag} Locker back wall 1") and ob.material_slots:
                orig = ob.get("dwet_orig_mat") or (ob.material_slots[0].material.name
                                                   if ob.material_slots[0].material else "")
                if orig == "Suite_Marble_XZ":
                    touched.append(_swap(ob, M["marble_xz"]))
    return [t for t in touched if t]


# ------------------------------------------------------------------ fixtures


def _dispenser(M, root, p):
    """Wall-mounted 3-chamber dispenser (shampoo / conditioner / body wash), back at local y = 0.002."""
    x, z = p
    box("Dispenser body", (0.30, 0.085, 0.20), M["abs"], root, (x, 0.0445, z), bevel=0.012)
    box("Dispenser lid seam", (0.296, 0.004, 0.004), M["dark"], root, (x, 0.0875, z + 0.074))
    quad("Dispenser face", 0.28, 0.17, M["d_disp"], root, (x, 0.0885, z - 0.004))
    for i in range(3):
        box("Dispenser push", (0.07, 0.03, 0.022), M["abs"], root, (x - 0.096 + i * 0.096, 0.072, z - 0.111), bevel=0.006)


def _hook_towel(M, root, x, z, towel, mat=None):
    box("Robe hook plate", (0.035, 0.008, 0.06), M["chrome"], root, (x, 0.006, z), bevel=0.003)
    cyl("Robe hook arm", 0.007, 0.05, M["chrome"], root, (x, 0.033, z + 0.005), (90, 0, 0), seg=10)
    cyl("Robe hook tip", 0.010, 0.012, M["chrome"], root, (x, 0.058, z + 0.012), seg=10)
    if towel:
        t = mat or M["towel"]
        # folded over the hook: front and back layers + rounded top
        box("Towel back layer", (0.17, 0.014, 0.48), t, root, (x, 0.042, z - 0.22), bevel=0.006)
        box("Towel front layer", (0.17, 0.014, 0.30), t, root, (x, 0.068, z - 0.13), bevel=0.006)
        cyl("Towel fold", 0.02, 0.17, t, root, (x, 0.055, z + 0.02), (0, 90, 0), seg=10)


def _booth_plate(M, tag, s, n, ya):
    """Number plate on the outside of the fixed front glass panel (glass u 1.045..1.055)."""
    root = frame(tag, s, f"Booth plate {n}", BOOTH_D + 0.0055, ya - 0.185, "+u", 1.86)
    box("Booth plate", (0.085, 0.003, 0.085), M["steel"], root, (0, 0.0015, 0), bevel=0.002)
    quad("Booth plate number", 0.078, 0.078, M[f"d_booth{n}"], root, (0, 0.0035, 0))


def _bath_stool(M, mat, parent, loc, rz=0.0):
    """Korean plastic bath stool: rounded seat, splayed skirt with a finger slot. Local origin on the floor."""
    e = bpy.data.objects.new(PFX + "Bath stool", None)
    e.empty_display_size = 0.05
    _C.objects.link(e)
    e.parent = parent
    e.location = loc
    e.rotation_euler.z = math.radians(rz)
    frustum("Bath stool skirt", (0.29, 0.225), (0.25, 0.195), 0.19, mat, e, (0, 0, 0.001), bevel=0.02)
    box("Bath stool seat", (0.30, 0.235, 0.028), mat, e, (0, 0, 0.205), bevel=0.012)
    box("Bath stool slot", (0.08, 0.004, 0.02), M["dark"], e, (0, 0.1185, 0.205))
    return e


def _basin(M, parent, loc, mat=None):
    prof = [(0.0, 0.0), (0.10, 0.0), (0.135, 0.075), (0.140, 0.082), (0.134, 0.084), (0.125, 0.074), (0.093, 0.006), (0.0, 0.006)]
    return lathe("Wash basin", prof, mat or M["basin"], parent, loc, seg=32)


def _square_drain(M, parent, loc, size=0.15):
    box("Floor drain frame", (size + 0.02, size + 0.02, 0.0055), M["chrome"], parent,
        (loc[0], loc[1], -0.003 + 0.00275 + 0.0015), bevel=0.002)
    box("Floor drain grate", (size, size, 0.004), M["grate"], parent, (loc[0], loc[1], 0.0025))


def _exhaust(M, parent, loc, size=0.30):
    """Square ceiling exhaust grille under the tile ceiling (top 1 mm below CEIL_TILE_Z)."""
    x, y = loc
    z = CEIL_TILE_Z - 0.001 - 0.007          # 2.970 .. 2.984
    b = 0.025
    for dx, dy, sx, sy in ((0, 1, size, b), (0, -1, size, b), (1, 0, b, size - 2 * b), (-1, 0, b, size - 2 * b)):
        box("Exhaust frame", (sx, sy, 0.014), M["abs"], parent,
            (x + dx * (size - b) / 2, y + dy * (size - b) / 2, z), bevel=0.003)
    box("Exhaust throat", (size - 2 * b + 0.004, size - 2 * b + 0.004, 0.002), M["dark"], parent, (x, y, CEIL_TILE_Z - 0.002))
    n = 7
    span = size - 2 * b - 0.02
    for i in range(n):
        yy = y - span / 2 + i * span / (n - 1)
        box("Exhaust vane", (size - 2 * b - 0.002, 0.005, 0.011), M["abs"], parent, (x, yy, z - 0.0005), rot=(30, 0, 0))


def _wet_floor_sign(M, parent, loc, rz):
    e = bpy.data.objects.new(PFX + "Wet floor sign", None)
    e.empty_display_size = 0.1
    _C.objects.link(e)
    e.parent = parent
    e.location = loc
    e.rotation_euler.z = math.radians(rz)
    H, Wd, tilt = 0.62, 0.30, 12.0
    for side in (1, -1):
        # each board leans toward the apex at y = 0; its local +Y face points outward
        cy = side * ((H / 2) * math.sin(math.radians(tilt)) + 0.008)
        board = box("Wet sign board", (Wd, 0.012, H), M["yellow"], e, (0, cy, H / 2 * math.cos(math.radians(tilt)) + 0.001),
                    rot=(tilt, 0, 0 if side > 0 else 180), bevel=0.004)
        quad("Wet sign face", 0.26, 0.52, M["d_wet"], board, (0, 0.0065, -0.03))
    box("Wet sign handle", (0.12, 0.04, 0.03), M["yellow"], e, (0, 0, H * math.cos(math.radians(tilt)) + 0.02), bevel=0.008)
    return e


def _squeegee(M, root):
    """Floor squeegee leaning on the wall: root at the blade centre on the floor, local +Y away from the wall."""
    box("Squeegee blade holder", (0.45, 0.035, 0.04), M["squeegee"], root, (0, 0.0, 0.034), bevel=0.006)
    box("Squeegee rubber", (0.45, 0.008, 0.016), M["rubber"], root, (0, 0.0, 0.009))
    # handle from the holder up to the wall (wall at local y = -0.27, top z 1.25)
    dy, dz = -0.25, 1.22
    L = math.hypot(dy, dz)
    ang = math.degrees(math.atan2(-dy, dz))   # +X rotation tips local Z toward -Y (the wall)
    cyl("Squeegee handle", 0.012, L, M["steel"], root, (0, dy / 2, 0.055 + dz / 2), (ang, 0, 0), seg=12)
    cyl("Squeegee grip", 0.016, 0.14, M["rubber"], root, (0, dy * 0.9, 0.055 + dz * 0.9), (ang, 0, 0), seg=12)


def _duckboard(M, parent, u0, u1, y0, y1, s, tag):
    """Teak slatted duckboard just inside the shower doorway (ref 047)."""
    cu = (u0 + u1) / 2
    lu = abs(u1 - u0)
    for yy in (y0 - 0.06, y1 + 0.06):
        box(f"{tag} Duckboard runner", (lu - 0.06, 0.04, 0.010), M["teak"], parent, (_sx(s, cu), yy, 0.006), bevel=0.002)
    n = 8
    step = (y0 - y1) / n
    for i in range(n):
        yy = y0 - step * (i + 0.5)
        box(f"{tag} Duckboard slat", (lu, step - 0.015, 0.012), M["teak"], parent, (_sx(s, cu), yy, 0.0175), bevel=0.003)


def _cleaning_cabinet(M, tag, s):
    """Grey steel cleaning cabinet in the restroom corner by the door, checklist on its door, mop + bucket beside."""
    root = frame(tag, s, "Cleaning cabinet", WIDTH, -10.87, "-u")
    w, d, h = 0.48, 0.38, 1.85
    box("Cabinet body", (w, d - 0.02, h), M["cabinet"], root, (0, 0.002 + (d - 0.02) / 2, h / 2 + 0.002), bevel=0.006)
    box("Cabinet door", (w - 0.02, 0.016, h - 0.06), M["cabinet"], root, (0, d - 0.009, h / 2 + 0.02), bevel=0.004)
    for i in range(6):
        box("Cabinet louver", (0.20, 0.004, 0.012), M["dark"], root, (0, d - 0.0015, 1.62 + i * 0.03))
        box("Cabinet louver low", (0.20, 0.004, 0.012), M["dark"], root, (0, d - 0.0015, 0.16 + i * 0.03))
    box("Cabinet handle", (0.02, 0.025, 0.14), M["chrome"], root, (-w / 2 + 0.05, d + 0.012, 1.00), bevel=0.005)
    box("Cabinet label plate", (0.24, 0.002, 0.06), M["abs"], root, (0, d + 0.002, 1.45))
    quad("Cabinet label", 0.23, 0.057, M["d_cab"], root, (0, d + 0.0035, 1.45))
    # checklist on a clipboard-style backer on the door
    box("Checklist backer", (0.23, 0.004, 0.33), M["backer"], root, (0.03, d + 0.003, 1.08), bevel=0.0015)
    box("Checklist clip", (0.08, 0.01, 0.025), M["chrome"], root, (0.03, d + 0.008, 1.235), bevel=0.003)
    quad("Checklist", 0.21, 0.297, M["d_check"], root, (0.03, d + 0.0055, 1.07))
    box("Pen on string", (0.008, 0.008, 0.13), M["bucket"], root, (0.17, d + 0.006, 0.88), rot=(0, 8, 0))
    # mop bucket with wringer + mop leaning on the wall
    b = frame(tag, s, "Mop bucket", WIDTH - 0.24, -11.36, "-u")
    frustum("Mop bucket body", (0.34, 0.25), (0.38, 0.28), 0.28, M["bucket"], b, (0, 0, 0.004), bevel=0.02)
    box("Mop bucket water", (0.34, 0.24, 0.004), M["water"], b, (0.04, 0, 0.24))
    box("Mop wringer", (0.12, 0.26, 0.16), M["yellow"], b, (-0.12, 0, 0.36), bevel=0.012)
    box("Wringer press", (0.10, 0.20, 0.02), M["rubber"], b, (-0.12, 0, 0.45), bevel=0.004)
    cyl("Wringer lever", 0.011, 0.70, M["yellow"], b, (-0.12, -0.10, 0.70), (-12, 0, 0), seg=10)
    for wx in (-0.17, 0.17):
        cyl("Bucket caster", 0.022, 0.02, M["rubber"], b, (wx, 0.11, 0.024), (90, 0, 0), seg=12)
        cyl("Bucket caster b", 0.022, 0.02, M["rubber"], b, (wx, -0.11, 0.024), (90, 0, 0), seg=12)
    m = frame(tag, s, "Mop", WIDTH, -11.78, "-u")
    p0, p1 = (0.30, 0.13), (0.022, 1.40)        # (local y, z): mop head -> top resting on the wall
    dy, dz = p1[0] - p0[0], p1[1] - p0[1]
    ang = math.degrees(math.atan2(-dy, dz))
    cyl("Mop handle", 0.012, math.hypot(dy, dz), M["steel"], m, (0, (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2),
        (ang, 0, 0), seg=12)
    cyl("Mop head clamp", 0.03, 0.05, M["bucket"], m, (0, 0.30, 0.11), seg=12)
    # cotton strands flopping out on the floor around the head
    for i in range(16):
        a = 2 * math.pi * i / 16
        ln = 0.20 + 0.04 * ((i * 7) % 3)
        tilt = 62 + 8 * ((i * 5) % 3)
        cx = math.cos(a) * (0.03 + ln / 2 * math.sin(math.radians(tilt)))
        cy = 0.30 + math.sin(a) * (0.03 + ln / 2 * math.sin(math.radians(tilt)))
        t = math.radians(tilt)
        cz = ln / 2 * math.cos(t) + 0.022 * math.sin(t) + 0.002      # lowest point just above the floor
        st = cyl("Mop strand", 0.022, ln, M["mop"], m, (cx, cy, cz), seg=6, r2=0.014)
        # strand axis (bottom -> top) points back up toward the head: (-cos a sin t, -sin a sin t, cos t)
        st.rotation_euler = (math.asin(math.sin(a) * math.sin(t)), math.atan2(-math.cos(a) * math.sin(t), math.cos(t)), 0)


def _spare_rolls(M, tag, s, i):
    """Two spare rolls on a chrome post on the cubicle side wall that already holds the paper holder."""
    ua, ub = CUBE_U[i], CUBE_U[i + 1]
    cu = (ua + ub) / 2
    # frame local +x = world +x: toward smaller u for men, larger u for women
    side_u = cu - 0.5125 if s < 0 else cu + 0.5125
    wall_off = 0.0 if abs(side_u - CUBE_U[1]) > 0.05 else 0.0125
    x_wall = 0.5125 - wall_off
    root = frame(tag, s, f"WC spare rolls {i}", cu, Y_BACK, "+y")
    xb = x_wall - 0.0045
    box("Spare roll bracket", (0.008, 0.05, 0.03), M["chrome"], root, (xb, 0.80, 1.14), bevel=0.002)
    xr = x_wall - 0.07
    cyl("Spare roll arm", 0.005, 0.062, M["chrome"], root, (xr + 0.031, 0.80, 1.14), (0, 90, 0), seg=8)
    cyl("Spare roll post", 0.007, 0.32, M["chrome"], root, (xr, 0.80, 0.97), seg=10)
    for k, zr in enumerate((0.875, 0.99)):
        lathe("Spare roll", [(0.0, 0.0), (0.055, 0.0), (0.055, 0.108), (0.0, 0.108)], M["roll"], root,
              (xr, 0.80, zr - 0.054), seg=20)
    # notice above the flush plate
    box("Toilet notice plate", (0.22, 0.003, 0.16), M["backer"], root, (0, 0.0035, 1.40), bevel=0.001)
    quad("Toilet notice", 0.21, 0.15, M["d_toilet"], root, (0, 0.0055, 1.40))


def _shower(M, tag, s):
    stool = M["stool_m"] if s < 0 else M["stool_w"]
    for i, (ya, yb) in enumerate(zip(BOOTH_Y[:-1], BOOTH_Y[1:])):
        yc = (ya + yb) / 2
        root = frame(tag, s, f"Booth wall {i}", 0.002, yc, "+u")
        _dispenser(M, root, (0.19, 1.52))
        _hook_towel(M, root, -0.38, 1.74, towel=(i != 1), mat=M["towel"] if i == 0 else M["towel_grey"])
        _booth_plate(M, tag, s, i + 1, ya)
    # Booth 1 (door open) has a stool with a basin, the others are bare
    root = frame(tag, s, "Booth stool", 0.55, -13.65, "+u")
    _bath_stool(M, stool, root, (0, 0, 0), rz=8)
    # Spare stools stacked + basin in the aisle corner by the back wall
    root = frame(tag, s, "Stool stack", 1.82, -15.08, "+u")
    _bath_stool(M, stool, root, (0, 0, 0), rz=90)
    _bath_stool(M, stool, root, (0, 0, 0.222), rz=93)
    root2 = frame(tag, s, "Booth stool basin", 0.55, -13.65, "+u", 0.2195)
    _basin(M, root2, (0, 0, 0))
    # Squeegee leaning on the back wall
    sq = frame(tag, s, "Squeegee", 1.38, Y_BACK + 0.27, "+y")
    _squeegee(M, sq)
    # Square drains in the dry aisle (ref 046)
    for y in (-11.95, -14.45):
        e = frame(tag, s, f"Aisle drain {y}", 1.52, y, "+y")
        _square_drain(M, e, (0, 0))
    # Exhaust fans
    e = frame(tag, s, "Shower exhaust", 0, 0, "+y")
    e.location = (0, 0, 0)
    e.rotation_euler.z = 0
    _exhaust(M, e, (_sx(s, 1.55), -13.95))
    _exhaust(M, e, (_sx(s, 0.52), -11.30))
    # Duckboard inside the doorway
    _duckboard(M, e, 0.80, 1.60, -10.86, -11.42, s, tag)
    # Rules sign left of the doorway (on the locker back wall's shower face)
    r = frame(tag, s, "Shower rules", 0.36, Y_IN, "-y")
    box("Rules sign plate", (0.42, 0.006, 0.32), M["backer"], r, (0, 0.005, 1.55), bevel=0.002)
    quad("Rules sign", 0.40, 0.30, M["d_rules"], r, (0, 0.0090, 1.55))
    # Wet-floor A-frame in the free corner before booth 0
    _wet_floor_sign(M, e, (_sx(s, 0.45), -11.75, 0.0), rz=-20 * s)


def _restroom(M, tag, s):
    # Under-counter LED glow (mirror/vanity lighting, refs 061/070): strip under the counter apron
    v = frame(tag, s, "Vanity LED", U_WC_IN, -11.75, "+u")
    box("Under counter LED", (1.36, 0.012, 0.006), M["led"], v, (0, 0.49, 0.714))
    # Paper towel dispenser next to the vanity (ref 063): white box with smoked window
    p = frame(tag, s, "Paper towel box", U_WC_IN + 0.002, -10.80, "+u")
    box("Towel box body", (0.27, 0.11, 0.34), M["abs"], p, (0, 0.055, 1.38), bevel=0.012)
    box("Towel box window", (0.10, 0.004, 0.14), M["smoke"], p, (0, 0.111, 1.42), bevel=0.002)
    box("Towel box slot", (0.20, 0.03, 0.012), M["dark"], p, (0, 0.06, 1.2045))
    box("Towel sheet", (0.12, 0.004, 0.06), M["towel"], p, (0, 0.06, 1.18))
    # Cleaning cabinet, checklist, mop & bucket
    _cleaning_cabinet(M, tag, s)
    # Cubicles: spare rolls + notice
    for i in range(2):
        _spare_rolls(M, tag, s, i)
    # Exhaust fans: one over the urinal / free side, one per cubicle
    e = frame(tag, s, "Restroom exhaust", 0, 0, "+y")
    e.location = (0, 0, 0)
    e.rotation_euler.z = 0
    _exhaust(M, e, (_sx(s, 3.70), -12.25), 0.25)
    for i in range(2):
        _exhaust(M, e, (_sx(s, (CUBE_U[i] + CUBE_U[i + 1]) / 2), -14.30), 0.25)
    if s < 0:
        # Urinal sticker above each urinal (outer wall, u = 4.15)
        for i, y in enumerate((-12.30, -13.00)):
            r = frame(tag, s, f"Urinal sticker {i}", WIDTH, y, "-u")
            quad("Urinal notice", 0.20, 0.14, M["d_urinal"], r, (0, 0.002, 1.74))
    else:
        # Sanitary pad vending box on the outer wall + labels on the cubicle sanitary bins
        r = frame(tag, s, "Sanitary vending", WIDTH, -12.40, "-u")
        box("Vending body", (0.32, 0.14, 0.45), M["abs"], r, (0, 0.072, 1.38), bevel=0.01)
        quad("Vending face", 0.31, 0.44, M["d_vend"], r, (0, 0.1425, 1.38))
        for i in range(2):
            ua, ub = CUBE_U[i], CUBE_U[i + 1]
            half_w = (ub - ua) / 2 - 0.02
            t = frame(tag, s, f"Sanitary bin label {i}", (ua + ub) / 2, Y_BACK, "+y")
            # existing bin: centre local (-half_w + 0.12, 0.30, 0.15), size (0.18, 0.28, 0.30): front face y = 0.44
            quad("Sanitary bin label", 0.12, 0.06, M["d_sanlabel"], t, (-half_w + 0.12, 0.4415, 0.20))
            box("Sanitary bin pedal", (0.08, 0.04, 0.015), M["chrome"], t, (-half_w + 0.12, 0.463, 0.022), bevel=0.004)


# ------------------------------------------------------------------ apply


def _clear():
    c = bpy.data.collections.get(COLL)
    if c:
        for ob in list(c.all_objects):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)


def _tri_count():
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in _C.all_objects:
        if ob.type == "MESH":
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            tris += len(me.loop_triangles)
            ev.to_mesh_clear()
    return tris


def _bounds():
    out = {}
    for tag, s in SUITES:
        lo, hi = [1e9] * 3, [-1e9] * 3
        for ob in _C.all_objects:
            if ob.type != "MESH" or tag not in _suite_of(ob):
                continue
            for c in ob.bound_box:
                w = ob.matrix_world @ Vector(c)
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], w[k]), max(hi[k], w[k])
        out[tag] = [round(v, 3) for v in lo + hi]
    return out


def _suite_of(ob):
    xs = [(ob.matrix_world @ Vector(c)).x for c in ob.bound_box]
    return "Men" if (min(xs) + max(xs)) / 2 < PART_X else "Women"


def apply() -> dict:
    global _C
    _clear()
    parent = bpy.data.collections.get("SET")
    _C = bpy.data.collections.get(COLL)
    if _C is None:
        _C = bpy.data.collections.new(COLL)
        (parent or bpy.context.scene.collection).children.link(_C)
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    M = _materials()
    touched = _wet_surfaces(M)
    for tag, s in SUITES:
        _shower(M, tag, s)
        _restroom(M, tag, s)
    bpy.context.view_layer.update()
    return {
        "collection": COLL,
        "objects_added": len(_C.all_objects),
        "triangles_added": _tri_count(),
        "existing_objects_touched": touched,
        "bounds": _bounds(),
    }


if __name__ == "__main__" and (bpy is None or "--textures" in sys.argv):
    make_textures()
