"""Gym free-weight detail pass (package key: gym_freeweight).

Back-left corner of the gym (left of the hazard-wrapped column WallCol_L, x -7.47 .. -3.19, y up to the back
wall at 4.97) was bare black wall. It becomes a Korean-gym dumbbell zone:
  * mirror wall: 4 full-height mirror panels, thin black aluminium joints, top cap and a black steel kick rail
    at the floor (refs gym 177 178 174 252); continues the existing back-wall mirror line (top z 2.46).
  * 2-tier commercial dumbbell rack, black steel, tilted saddle tiers with rubber strips (refs 139 239 244 164)
    holding rubber hex dumbbells 2-20 kg (top, 2 kg steps) and 22.5-40 kg (bottom, 2.5 kg steps), head size
    scaled by weight, weight number printed on the end faces (ref 164).
  * Ref-269 style silver barbell storage rack against the left wall with 5 fixed straight barbells
    10-30 kg, black urethane heads with green ring faces (ref 276).
  * Ref-270 style plate tree on casters with colour bumpers (red 25 / blue 20 / yellow 15 / green 10 / grey 5)
    and black iron grip plates on top.
  * Lived-in: the 14 kg pair is missing from the rack and lies on the floor in front of it; a 10 kg pair
    lies next to the existing adjustable bench.

Usage (scene open, cwd = repo):
    import sys; sys.path.insert(0, "promo/tools"); import detail_gym_freeweight; detail_gym_freeweight.apply()
Textures (only needed if promo/parts/detail_gym_freeweight/*.png are missing):
    ~/.venvs/pdf/bin/python promo/tools/detail_gym_freeweight.py
"""
import math
import os
import sys

KEY = "gym_freeweight"
COLL = "DETAIL_gym_freeweight"
P = "Dgym_freeweight_"
HERE = os.path.dirname(os.path.abspath(__file__))
PARTS_DIR = os.path.join(os.path.dirname(HERE), "parts", "detail_" + KEY)

# ---------------------------------------------------------------- shared data (used by PIL + Blender)
DB_TOP = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
DB_BOT = [22.5, 25, 27.5, 30, 32.5, 35, 37.5, 40]
BAR_KG = [10, 15, 20, 25, 30]
ATLAS_COLS, ATLAS_ROWS, CELL = 6, 4, 256          # dumbbell / barbell head-face atlas
PLATES = [  # key: (label, colour rgb 0-255, kind)
    ("b25", "25", (172, 22, 24), "bumper"),
    ("b20", "20", (22, 70, 160), "bumper"),
    ("b15", "15", (222, 178, 20), "bumper"),
    ("b10", "10", (30, 120, 52), "bumper"),
    ("b5", "5", (128, 130, 134), "bumper"),
    ("i20", "20", (30, 31, 34), "iron"),
    ("i10", "10", (30, 31, 34), "iron"),
    ("i5", "5", (30, 31, 34), "iron"),
]
PLATE_COLS, PLATE_ROWS, PCELL = 4, 2, 512


def _fmt(kg):
    return ("%g" % kg)


def head_labels():
    """Atlas cell order: rack dumbbells, then barbells; last cell stays plain rubber."""
    return [("db", k) for k in DB_TOP + DB_BOT] + [("bar", k) for k in BAR_KG]


# ================================================================ PIL texture generator (run outside Blender)
def make_textures():
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import random
    os.makedirs(PARTS_DIR, exist_ok=True)
    font_path = os.path.join(os.path.dirname(HERE), "parts", "fonts", "NanumGothic-Bold.ttf")
    rnd = random.Random(7)

    def grain(img, amount):
        px = img.load()
        w, h = img.size
        for _ in range(w * h // 6):
            x, y = rnd.randrange(w), rnd.randrange(h)
            r, g, b = px[x, y][:3]
            d = rnd.randint(-amount, amount)
            px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))

    # ---- head faces: black rubber, painted light-grey number (ref 164), barbells get the green ring (ref 276)
    W, H = ATLAS_COLS * CELL, ATLAS_ROWS * CELL
    img = Image.new("RGB", (W, H), (9, 9, 10))
    d = ImageDraw.Draw(img)
    for i, (kind, kg) in enumerate(head_labels()):
        cx0, cy0 = (i % ATLAS_COLS) * CELL, (i // ATLAS_COLS) * CELL
        c = (cx0 + CELL / 2, cy0 + CELL / 2)
        if kind == "db":
            # moulded hexagon lip just inside the edge
            R = CELL * 0.47
            pts = [(c[0] + R * math.cos(math.radians(a)), c[1] + R * math.sin(math.radians(a))) for a in range(0, 360, 60)]
            d.polygon(pts, outline=(24, 24, 26), width=7)
            label = _fmt(kg)
            size = 92 if len(label) <= 2 else 70
            f = ImageFont.truetype(font_path, size)
            d.text((c[0], c[1] - 10), label, font=f, fill=(196, 198, 200), anchor="mm")
            d.text((c[0], c[1] + 56), "KG", font=ImageFont.truetype(font_path, 30), fill=(150, 152, 155), anchor="mm")
        else:
            r1, r2 = CELL * 0.44, CELL * 0.37
            d.ellipse([c[0] - r1, c[1] - r1, c[0] + r1, c[1] + r1], fill=(40, 190, 90))
            d.ellipse([c[0] - r2, c[1] - r2, c[0] + r2, c[1] + r2], fill=(12, 12, 13))
            d.text((c[0], c[1] - 8), _fmt(kg), font=ImageFont.truetype(font_path, 84), fill=(40, 190, 90), anchor="mm")
            d.text((c[0], c[1] + 50), "KG", font=ImageFont.truetype(font_path, 28), fill=(40, 190, 90), anchor="mm")
    grain(img, 5)
    img.filter(ImageFilter.GaussianBlur(0.6)).save(os.path.join(PARTS_DIR, "head_faces.png"))

    # ---- plate faces: one full face per plate type (rim colour reaches the cell edge for the plate rim UVs)
    W, H = PLATE_COLS * PCELL, PLATE_ROWS * PCELL
    img = Image.new("RGB", (W, H), (20, 20, 22))
    d = ImageDraw.Draw(img)
    for i, (key, label, col, kind) in enumerate(PLATES):
        x0, y0 = (i % PLATE_COLS) * PCELL, (i // PLATE_COLS) * PCELL
        c = (x0 + PCELL / 2, y0 + PCELL / 2)
        d.rectangle([x0, y0, x0 + PCELL - 1, y0 + PCELL - 1], fill=col)
        dark = tuple(int(v * 0.72) for v in col)
        light = tuple(min(255, int(v * 1.18) + 14) for v in col)
        R = PCELL / 2
        if kind == "bumper":
            # raised outer lip, flat field, recessed ring round the steel hub, white print (refs 270 174)
            d.ellipse([c[0] - R * .97, c[1] - R * .97, c[0] + R * .97, c[1] + R * .97], outline=dark, width=10)
            d.ellipse([c[0] - R * .40, c[1] - R * .40, c[0] + R * .40, c[1] + R * .40], fill=dark)
            f = ImageFont.truetype(font_path, 74)
            ink = (238, 238, 236) if kind == "bumper" and label != "5" else (30, 30, 32)
            d.text((c[0], c[1] - R * .62), label + " KG", font=f, fill=ink, anchor="mm")
            d.text((c[0], c[1] + R * .64), "BUMPER PLATE", font=ImageFont.truetype(font_path, 34), fill=ink, anchor="mm")
        else:
            # cast-iron tri-grip: three dark kidney slots, machined rim, raised weight (ref 174 270 top row)
            d.ellipse([c[0] - R * .98, c[1] - R * .98, c[0] + R * .98, c[1] + R * .98], outline=(52, 53, 57), width=16)
            for k in range(3):
                a = math.radians(90 + k * 120)
                sx, sy = c[0] + math.cos(a) * R * .55, c[1] + math.sin(a) * R * .55
                for t in range(-14, 15):
                    aa = a + math.radians(t * 1.6)
                    px, py = c[0] + math.cos(aa) * R * .58, c[1] + math.sin(aa) * R * .58
                    d.ellipse([px - 30, py - 30, px + 30, py + 30], fill=(4, 4, 5))
            d.ellipse([c[0] - R * .30, c[1] - R * .30, c[0] + R * .30, c[1] + R * .30], fill=(46, 47, 50))
            f = ImageFont.truetype(font_path, 58)
            for k in range(3):
                a = math.radians(30 + k * 120)
                d.text((c[0] + math.cos(a) * R * .70, c[1] + math.sin(a) * R * .70), label + "KG", font=f,
                       fill=(92, 94, 98), anchor="mm")
    grain(img, 6)
    img.filter(ImageFilter.GaussianBlur(0.7)).save(os.path.join(PARTS_DIR, "plate_faces.png"))
    print("textures written to", PARTS_DIR)


if __name__ == "__main__" and "bpy" not in sys.modules:
    make_textures()
    sys.exit(0)

# ================================================================ Blender side
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

sys.path.insert(0, HERE)

# ---- zone (world metres). Verified free on scene_gym.blend: back wall face y 4.97 (wainscot), left wall face
# x -7.47, column WallCol_L x -3.17..-2.73, EZ-bar rack x >= -3.61, cable crossover x >= -4.65 & y <= 3.72,
# stretching-zone props y <= 2.85. Vestigial strip Baseboard_Left runs along x -4.53..-4.44 (z <= .12): no
# feet are placed there.
MIR_X = (-7.462, -3.195)
MIR_TOP = 2.46
RACK_X = (-7.325, -3.705)   # outer faces of the end frames
RACK_Y = (4.16, 4.905)
BAR_RACK_Y = 3.45            # barbell rack centre on the left wall
TREE_XY = (-5.06, 3.45)      # plate tree centre

TOP_DB = [k for k in DB_TOP if k != 14]      # 14 kg pair is out on the floor


# ---------------------------------------------------------------- generic helpers
_ROOT = {}
_new = []


def _coll():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.data.collections["SET"].children.link(c)
    return c


def _link(ob, parent=None):
    _coll().objects.link(ob)
    ob.parent = parent if parent is not None else _ROOT.get("root")
    _new.append(ob)
    return ob


def _mat_basic(name, color, rough=0.5, metal=0.0, coat=0.0):
    m = bpy.data.materials.get(P + name)
    if m:
        return m
    m = bpy.data.materials.new(P + name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.25
    return m


def _image(fname):
    path = os.path.join(PARTS_DIR, fname)
    img = bpy.data.images.load(path, check_existing=True)
    if not img.packed_file:
        img.pack()
    return img


def _mat_tex(name, fname, rough, metal=0.0, bump=0.0):
    m = bpy.data.materials.get(P + name)
    if m:
        return m
    m = bpy.data.materials.new(P + name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = _image(fname)
    t.interpolation = "Linear"
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if bump:
        bm = nt.nodes.new("ShaderNodeBump")
        bm.inputs["Strength"].default_value = bump
        bm.inputs["Distance"].default_value = 0.0015
        nt.links.new(t.outputs["Color"], bm.inputs["Height"])
        nt.links.new(bm.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = (0.03, 0.03, 0.03, 1)
    return m


def _mat_knurl(name):
    """Hard-chrome handle with fine diamond knurl (bump from a scaled wave/checker)."""
    m = bpy.data.materials.get(P + name)
    if m:
        return m
    m = bpy.data.materials.new(P + name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.78, 0.79, 0.80, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.30
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ck = nt.nodes.new("ShaderNodeTexChecker")
    ck.inputs["Scale"].default_value = 900.0
    bm = nt.nodes.new("ShaderNodeBump")
    bm.inputs["Strength"].default_value = 0.35
    bm.inputs["Distance"].default_value = 0.0004
    nt.links.new(tc.outputs["Object"], ck.inputs["Vector"])
    nt.links.new(ck.outputs["Fac"], bm.inputs["Height"])
    nt.links.new(bm.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = (0.7, 0.7, 0.72, 1)
    return m


def _mesh_from_bm(name, bm, mats, smooth_angle=None):
    me = bpy.data.meshes.new(P + name)
    bm.to_mesh(me)
    bm.free()
    for mt in mats:
        me.materials.append(mt)
    if smooth_angle is not None:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    return me


def _ob(name, me, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), parent=None):
    ob = bpy.data.objects.new(P + name, me)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return _link(ob, parent)


def _bevel(ob, width=0.003, seg=2):
    md = ob.modifiers.new("Bevel", "BEVEL")
    md.width = width
    md.segments = seg
    md.limit_method = "ANGLE"
    md.angle_limit = math.radians(40)
    md.harden_normals = False
    return ob


def _bar(name, p0, p1, w, t, mat, hint=(0, 0, 1), bevel=0.003):
    """Rectangular tube from p0 to p1: w across `hint`-perpendicular side axis, t along hint-ish axis."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    Y = d.normalized()
    hz = Vector(hint)
    if abs(hz.normalized().dot(Y)) > 0.95:
        hz = Vector((1, 0, 0)) if abs(Y.x) < 0.9 else Vector((0, 1, 0))
    Z = (hz - hz.dot(Y) * Y).normalized()
    X = Y.cross(Z)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(w, L, t), verts=bm.verts)
    me = _mesh_from_bm(name, bm, [mat])
    ob = _ob(name, me)
    ob.matrix_basis = Matrix.Translation((p0 + p1) / 2) @ Matrix((X, Y, Z)).transposed().to_4x4()
    if bevel:
        _bevel(ob, bevel)
    return ob


def _box(name, size, loc, mat, bevel=0.002, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    ob = _ob(name, _mesh_from_bm(name, bm, [mat]), loc, rot)
    if bevel:
        _bevel(ob, bevel)
    return ob


def _cyl_mesh(name, r, h, mat, seg=24, r2=None, caps=True, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    return _mesh_from_bm(name, bm, [mat], 30 if smooth else None)


def _rod(name, p0, p1, r, mat, seg=16, caps=True):
    p0, p1 = Vector(p0), Vector(p1)
    me = _cyl_mesh(name, r, (p1 - p0).length, mat, seg, caps=caps)
    ob = _ob(name, me)
    q = (p1 - p0).to_track_quat("Z", "Y")
    ob.matrix_basis = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
    return ob


def _lathe(bm, profile, seg, uv_fn=None, uvl=None, axis_len_index=1):
    """Revolve [(r, z), ...] around Z; returns ring vert lists."""
    rings = []
    for r, z in profile:
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    faces = []
    for i in range(len(rings) - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append(bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k])))
    return rings, faces


# ---------------------------------------------------------------- UV atlases
def _cell_uv(index, cols, rows):
    """(u0, v0, w, h) of a cell (row 0 at the image top)."""
    w, h = 1.0 / cols, 1.0 / rows
    col, row = index % cols, index // cols
    return col * w, 1.0 - (row + 1) * h, w, h


PLAIN_CELL = ATLAS_COLS * ATLAS_ROWS - 1


# ---------------------------------------------------------------- dumbbells
def db_dims(kg):
    """Rubber hex dumbbell: across-flats f, head length L (real 2 kg ~ 89 mm / 40 kg ~ 207 mm)."""
    return 0.050 + 0.023 * math.sqrt(kg), 0.060 + 0.0024 * kg


HEX_W = 1.08   # flat face down, so the side-to-side width is across the (chamfered) corners: 1.08 x across-flats


GRIP_HALF = 0.0675


def _hex_profile(f):
    R = f / math.sqrt(3)
    hexv = [Vector((R * math.cos(math.radians(a)), R * math.sin(math.radians(a)))) for a in range(0, 360, 60)]
    out, c = [], 0.13 * R
    for i, v in enumerate(hexv):
        a, b = hexv[i - 1], hexv[(i + 1) % 6]
        out.append(v + (a - v).normalized() * c)
        out.append(v + (b - v).normalized() * c)
    return out, R


def dumbbell_mesh(kg, rubber, chrome, knurl, cell):
    """Axis along local Y, flat hex face down, centred at origin. Outer end faces carry the weight print."""
    key = "DB_%s" % _fmt(kg)
    me = bpy.data.meshes.get(P + key)
    if me:
        return me
    f, L = db_dims(kg)
    prof, R = _hex_profile(f)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    u0, v0, cw, ch = _cell_uv(cell, ATLAS_COLS, ATLAS_ROWS)
    pu0, pv0, pw, ph = _cell_uv(PLAIN_CELL, ATLAS_COLS, ATLAS_ROWS)
    plain = (pu0 + pw * 0.5, pv0 + ph * 0.5)
    e = 0.009
    for side in (-1, 1):
        a, b = GRIP_HALF, GRIP_HALF + L
        ys = [(a, 0.90), (a + e, 1.0), (b - e, 1.0), (b, 0.93)]
        rings = []
        for y, s in ys:
            rings.append([bm.verts.new((p.x * s, side * y, p.y * s)) for p in prof])
        n = len(prof)
        for i in range(3):
            for k in range(n):
                k2 = (k + 1) % n
                q = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
                if side < 0:
                    q.reverse()
                fc = bm.faces.new(q)
                fc.material_index = 0
        inner = list(reversed(rings[0])) if side > 0 else list(rings[0])
        outer = list(rings[3]) if side > 0 else list(reversed(rings[3]))
        bm.faces.new(inner).material_index = 0
        fo = bm.faces.new(outer)
        fo.material_index = 0
        fo.select = True  # tag for UV pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    for fc in bm.faces:
        for lp in fc.loops:
            lp[uvl].uv = plain
    for fc in bm.faces:
        if fc.select:
            ny = fc.normal.y
            for lp in fc.loops:
                x, z = lp.vert.co.x, lp.vert.co.z
                u = x if ny < 0 else -x      # read correctly from outside either end
                lp[uvl].uv = (u0 + (u / (2.12 * R) + 0.5) * cw, v0 + (z / (2.12 * R) + 0.5) * ch)
            fc.select = False
    # chrome collars + knurled grip
    for side in (-1, 1):
        y0 = side * (GRIP_HALF - 0.011)
        y1 = side * (GRIP_HALF + 0.002)
        ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.0245, radius2=0.0245, depth=abs(y1 - y0))
        bmesh.ops.rotate(bm, verts=ret["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        bmesh.ops.translate(bm, verts=ret["verts"], vec=(0, (y0 + y1) / 2, 0))
        for fc in {f for v in ret["verts"] for f in v.link_faces}:
            fc.material_index = 1
    ret = bmesh.ops.create_cone(bm, cap_ends=False, segments=18, radius1=0.0165, radius2=0.0165, depth=2 * GRIP_HALF + 0.01)
    bmesh.ops.rotate(bm, verts=ret["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    for fc in {f for v in ret["verts"] for f in v.link_faces}:
        fc.material_index = 2
    me = _mesh_from_bm(key, bm, [rubber, chrome, knurl], smooth_angle=35)
    return me


# ---------------------------------------------------------------- plates
def plate_dims(key):
    return {"b25": (.225, .066), "b20": (.225, .056), "b15": (.225, .046), "b10": (.225, .036), "b5": (.225, .028),
            "i20": (.225, .034), "i10": (.165, .030), "i5": (.1325, .025)}[key]


def plate_mesh(key, faces_mat, steel):
    me = bpy.data.meshes.get(P + "Plate_" + key)
    if me:
        return me
    idx = [p[0] for p in PLATES].index(key)
    R, t = plate_dims(key)
    seg = 40
    h = t / 2
    ch = min(0.010, t * 0.25)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    u0, v0, cw, chh = _cell_uv(idx, PLATE_COLS, PLATE_ROWS)
    # rubber/iron body: from hub ring r=.05 out to R, chamfered rim
    prof = [(0.050, -h + .002), (R - ch, -h), (R, -h + ch), (R, h - ch), (R - ch, h), (0.050, h - .002)]
    rings, faces = _lathe(bm, prof, seg)
    for k in range(seg):  # close the inner bore wall
        k2 = (k + 1) % seg
        faces.append(bm.faces.new((rings[-1][k], rings[-1][k2], rings[0][k2], rings[0][k])))
    bm.normal_update()
    for fc in faces:
        fc.material_index = 0
        flat = abs(fc.normal.z) > 0.95 and all(abs(abs(l.vert.co.z) - h) < .003 for l in fc.loops)
        for lp in fc.loops:
            x, y = lp.vert.co.x, lp.vert.co.y
            if flat:
                u = x if fc.normal.z > 0 else -x
                lp[uvl].uv = (u0 + (u / (2 * R) + .5) * cw, v0 + (y / (2 * R) + .5) * chh)
            else:
                lp[uvl].uv = (u0 + cw * 0.5, v0 + chh * 0.985)
    # steel hub insert, proud by 2 mm each side
    hub = [(0.0262, -h - .002), (0.050, -h - .002), (0.050, h + .002), (0.0262, h + .002), (0.0262, -h - .002)]
    hr, hf = _lathe(bm, hub[:-1], seg)
    for k in range(seg):
        k2 = (k + 1) % seg
        hf.append(bm.faces.new((hr[-1][k], hr[-1][k2], hr[0][k2], hr[0][k])))
    for fc in hf:
        fc.material_index = 1
        for lp in fc.loops:
            lp[uvl].uv = (u0 + cw * .5, v0 + chh * .5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return _mesh_from_bm("Plate_" + key, bm, [faces_mat, steel], smooth_angle=40)


# ---------------------------------------------------------------- build parts
def _layout_tier(weights, x0, x1, fx, gap_frame=0.035, clr=0.008, pair_gap=0.02):
    """x centres of every dumbbell (2 per weight), left group / right group split around centre frame fx."""
    widths = [db_dims(k)[0] * HEX_W + clr for k in weights]
    best = None
    for k in range(1, len(weights)):
        lw = sum(2 * w for w in widths[:k]) + pair_gap * (k - 1)
        rw = sum(2 * w for w in widths[k:]) + pair_gap * (len(weights) - k - 1)
        la, ra = fx - gap_frame - x0, x1 - fx - gap_frame
        if lw <= la and rw <= ra:
            score = abs((la - lw) - (ra - rw))
            if best is None or score < best[0]:
                best = (score, k, lw, rw)
    if best is None:
        return None
    _, k, lw, rw = best
    out = []
    for grp, start, width_total in ((range(0, k), (x0 + fx - gap_frame) / 2 - lw / 2, lw),
                                    (range(k, len(weights)), (fx + gap_frame + x1) / 2 - rw / 2, rw)):
        x = start
        for i in grp:
            w = widths[i]
            out.append((weights[i], x + w / 2))
            out.append((weights[i], x + w * 1.5))
            x += 2 * w + pair_gap
    return out


def ensure_mirror_probe():
    """Idempotently ensure the freeweight/rack mirror wall has a clean silvered material and planar EEVEE probe."""
    mat = bpy.data.materials.get(P + "Mirror_Silvered")
    if mat and mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.93, 0.94, 0.93, 1.0)
            bsdf.inputs["Metallic"].default_value = 1.0
            bsdf.inputs["Roughness"].default_value = 0.01
            bsdf.inputs["Coat Weight"].default_value = 0.0
    x0, x1 = MIR_X
    zb, zt = 0.165, MIR_TOP
    y_front = 4.960  # front face of Mirror_glass_0..3
    probe_name = P + "MirrorProbe"
    coll = _coll()
    ob = bpy.data.objects.get(probe_name)
    if ob is not None and ob.type != "LIGHT_PROBE":
        bpy.data.objects.remove(ob, do_unlink=True)
        ob = None
    if ob is None:
        lp = bpy.data.lightprobes.new(probe_name, "PLANE")
        ob = bpy.data.objects.new(probe_name, lp)
        coll.objects.link(ob)
    else:
        lp = ob.data
        if coll not in ob.users_collection:
            coll.objects.link(ob)
    lp.influence_distance = 0.12
    lp.clip_start = 0.001
    ob.parent = None
    ob.location = (0.5 * (x0 + x1), y_front - 0.010, 0.5 * (zb + zt))
    ob.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    ob.scale = (0.5 * (x1 - x0) + 0.05, 0.5 * (zt - zb) + 0.05, 1.0)
    return ob


def build_mirror(mats):
    glass, alu, steel, rubber = mats["mirror"], mats["alu_black"], mats["steel"], mats["rubber"]
    x0, x1 = MIR_X
    n = 4
    pw = (x1 - x0) / n
    zb, zt = 0.165, MIR_TOP
    y_back = 4.966                       # 4 mm off the wainscot face (y 4.97)
    for i in range(n):
        a, b = x0 + i * pw + 0.0015, x0 + (i + 1) * pw - 0.0015
        _box("Mirror_glass_%d" % i, (b - a, 0.006, zt - zb), ((a + b) / 2, y_back - 0.003, (zb + zt) / 2), glass, bevel=0)
    # thin black aluminium T joints and end trims (ref 177: hairline black joints)
    for i in range(n + 1):
        x = x0 + i * pw
        w = 0.014 if 0 < i < n else 0.022
        xc = x if 0 < i < n else (x0 + 0.004 if i == 0 else x1 - 0.004)
        _box("Mirror_joint_%d" % i, (w, 0.010, zt - zb + 0.02), (xc, y_back - 0.009, (zb + zt) / 2), alu, bevel=0.0015)
    _box("Mirror_top_cap", (x1 - x0 + 0.004, 0.030, 0.034), ((x0 + x1) / 2, y_back - 0.016, zt + 0.012), alu, bevel=0.002)
    # protective kick rail: black steel channel + rubber bumper (refs 177 floor channel, 174 kick plinth)
    # split round the existing floor strip Baseboard_Left (x -4.53..-4.44) so nothing intersects it
    for i, (a, b) in enumerate(((x0, -4.545), (-4.425, x1))):
        _box("Mirror_kick_rail_%d" % i, (b - a, 0.034, 0.170), ((a + b) / 2, y_back - 0.018, 0.085), steel, bevel=0.003)
        _box("Mirror_kick_bumper_%d" % i, (b - a - 0.01, 0.018, 0.045), ((a + b) / 2, y_back - 0.042, 0.115), rubber,
             bevel=0.004)
    ensure_mirror_probe()


def build_dumbbell_rack(mats, dbm):
    steel, rubber = mats["steel"], mats["rubber"]
    xa, xb = RACK_X
    tw = 0.05
    x_in0, x_in1 = xa + tw, xb - tw
    th = math.radians(15)
    tiers = {  # centre (y, z of the saddle surface), tilt; rails at local y = +-0.125
        "bot": (4.40, 0.36, DB_BOT),
        "top": (4.655, 0.80, TOP_DB),
    }
    fx = None
    lays = {}
    for cand in [(xa + xb) / 2 + d * 0.01 * sg for d in range(0, 30) for sg in (1, -1)]:
        lb = _layout_tier(DB_BOT, x_in0, x_in1, cand)
        lt = _layout_tier(DB_TOP, x_in0, x_in1, cand)   # layout with the full set so the 14 kg slots stay empty
        if lb and lt:
            fx, lays = cand, {"bot": lb, "top": lt}
            break
    assert fx is not None, "dumbbells do not fit the rack"

    def tier_pt(tier, ly, lz):
        yc, zc, _ = tiers[tier]
        return Vector((0, yc + ly * math.cos(th) - lz * math.sin(th), zc + ly * math.sin(th) + lz * math.cos(th)))

    # rails (50x50 tube, top at saddle surface) + rubber strips embedded 2 mm
    for tier in tiers:
        for ly in (-0.125, 0.125):
            c = tier_pt(tier, ly, -0.025)
            r = _bar("Rack_rail_%s_%s" % (tier, "f" if ly < 0 else "b"), (xa, c.y, c.z), (xb, c.y, c.z), 0.05, 0.05,
                     steel, hint=(0, -math.sin(th), math.cos(th)))
            c2 = tier_pt(tier, ly, 0.001)
            _bar("Rack_strip_%s_%s" % (tier, "f" if ly < 0 else "b"), (x_in0, c2.y, c2.z), (x_in1, c2.y, c2.z), 0.056,
                 0.006, rubber, hint=(0, -math.sin(th), math.cos(th)), bevel=0.0015)
    # frames: two ends + one centre frame in a pair gap (ref 239/139 black frames)
    y0, y1 = RACK_Y
    for name, x in (("L", xa + tw / 2), ("C", fx), ("R", xb - tw / 2)):
        _bar("Rack_foot_%s" % name, (x, y0, 0.034), (x, y1, 0.034), tw, 0.05, steel, hint=(0, 0, 1))
        for yy in (y0 + 0.04, y1 - 0.04):
            _box("Rack_pad_%s_%.2f" % (name, yy), (0.07, 0.06, 0.010), (x, yy, 0.005), rubber, bevel=0.002)
        yr = y1 - 0.025
        _bar("Rack_post_%s" % name, (x, yr, 0.059), (x, yr, 0.955), tw, 0.05, steel, hint=(0, 1, 0))
        _box("Rack_cap_%s" % name, (tw + 0.004, 0.054, 0.012), (x, yr, 0.961), rubber, bevel=0.002)
        fb = tier_pt("bot", -0.125, -0.05)
        _bar("Rack_front_leg_%s" % name, (x, y0 + 0.05, 0.059), (x, fb.y, fb.z), tw, 0.05, steel, hint=(0, 1, 0))
        # tier arms along the tilt, under the rails, into the rear post
        for tier in tiers:
            a = tier_pt(tier, -0.15, -0.075)
            back_t = (yr - 0.025 - tiers[tier][0] + 0.0) / math.cos(th)
            b = tier_pt(tier, back_t, -0.075)
            _bar("Rack_arm_%s_%s" % (tier, name), (x, a.y, a.z), (x, b.y, b.z), tw * 0.9, 0.05, steel,
                 hint=(0, -math.sin(th), math.cos(th)))
        # strut from bottom arm up under the top tier front rail
        tf = tier_pt("top", -0.125, -0.05)
        zb = tiers["bot"][1] - 0.075 + (tf.y - tiers["bot"][0]) * math.tan(th)
        _bar("Rack_strut_%s" % name, (x, tf.y, zb), (x, tf.y, tf.z), tw * 0.9, 0.04, steel, hint=(0, 1, 0))
    # dumbbells (linked mesh data per weight)
    placed = 0
    for tier, lay in lays.items():
        for kg, x in lay:
            if tier == "top" and kg not in TOP_DB:
                continue
            f, L = db_dims(kg)
            c = tier_pt(tier, 0.0, 0.0045 + f / 2)
            _ob("DB_%s_%d" % (_fmt(kg), placed), dbm[kg], (x, c.y, c.z), (th, 0, 0))
            placed += 1
    return fx, placed


def build_barbell_rack(mats, heads):
    """Ref 269 silver barbell rack, plane parallel to the left wall; ref 276 fixed straight barbells."""
    silver, rubber, chrome, knurl = mats["silver"], mats["rubber"], mats["chrome"], mats["knurl"]
    yc = BAR_RACK_Y
    hooks_z = [1.26, 1.04, 0.82, 0.60, 0.38]           # 10 kg on top .. 30 kg at the bottom
    lean = math.radians(9)

    def ux(z):  # upright centre x, leaning back toward the wall
        return -7.16 - (z - 0.06) * math.tan(lean)

    for s in (-1, 1):
        y = yc + s * 0.31
        _bar("BarRack_foot_%d" % s, (-7.44, y, 0.03), (-6.96, y, 0.03), 0.06, 0.045, silver, hint=(0, 0, 1))
        for xx in (-7.40, -7.00):
            _box("BarRack_pad_%d_%.2f" % (s, xx), (0.06, 0.07, 0.012), (xx, y, 0.006), rubber, bevel=0.002)
        _bar("BarRack_upright_%d" % s, (ux(0.052), y, 0.052), (ux(1.42), y, 1.42), 0.07, 0.045, silver, hint=(1, 0, 0))
        _box("BarRack_cap_%d" % s, (0.052, 0.074, 0.012), (ux(1.42), y, 1.425), rubber, bevel=0.002,
             rot=(0, -lean, 0))
        for z in hooks_z:
            x = ux(z) + 0.0225
            # black moulded J-hook (ref 269): angled tongue + front lip
            _box("BarRack_hook_%d_%.2f" % (s, z), (0.090, 0.050, 0.030), (x + 0.040, y, z - 0.025), rubber,
                 bevel=0.006, rot=(0, math.radians(-12), 0))
            _box("BarRack_lip_%d_%.2f" % (s, z), (0.022, 0.050, 0.055), (x + 0.088, y, z - 0.002), rubber, bevel=0.006)
    _bar("BarRack_cross", (ux(0.70) - 0.0, yc - 0.31, 0.70), (ux(0.70), yc + 0.31, 0.70), 0.05, 0.04, silver,
         hint=(1, 0, 0))
    # fixed straight barbells: 1.15 m, black urethane heads, green faces
    for kg, z in zip(BAR_KG, hooks_z):
        x = ux(z) + 0.0225 + 0.060
        r = 0.0145
        zc = z - 0.008 + r + 0.003
        _rod("Barbell_%d_shaft" % kg, (x, yc - 0.575, zc), (x, yc + 0.575, zc), r, knurl, seg=16)
        hr, hl = 0.065 + kg * 0.0011, 0.07 + kg * 0.0017
        for s in (-1, 1):
            yh = yc + s * (0.575 - hl / 2)
            _ob("Barbell_%d_head_%d" % (kg, s), heads[kg], (x, yh, zc), (math.radians(-90 * s), 0, 0))
            _rod("Barbell_%d_collar_%d" % (kg, s), (x, yh - s * (hl / 2 + 0.012), zc), (x, yh - s * (hl / 2 - 0.002), zc),
                 0.024, chrome, seg=20)


def barbell_head_mesh(kg, rubber, cell):
    me = bpy.data.meshes.get(P + "BarHead_%d" % kg)
    if me:
        return me
    r, L = 0.065 + kg * 0.0011, 0.07 + kg * 0.0017
    seg = 32
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    e = 0.010
    prof = [(r - e, -L / 2), (r, -L / 2 + e), (r, L / 2 - e), (r - e, L / 2)]
    rings, faces = _lathe(bm, prof, seg)
    cap0 = bm.faces.new(list(reversed(rings[0])))
    cap1 = bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    u0, v0, cw, ch = _cell_uv(cell, ATLAS_COLS, ATLAS_ROWS)
    pu0, pv0, pw, ph = _cell_uv(PLAIN_CELL, ATLAS_COLS, ATLAS_ROWS)
    for fc in faces + [cap0]:
        for lp in fc.loops:
            lp[uvl].uv = (pu0 + pw / 2, pv0 + ph / 2)
    for lp in cap1.loops:  # +Z end face = outer face (object is rotated so +Z points away from the bar centre)
        x, y = lp.vert.co.x, lp.vert.co.y
        lp[uvl].uv = (u0 + (x / (2 * r * 1.03) + .5) * cw, v0 + (y / (2 * r * 1.03) + .5) * ch)
    return _mesh_from_bm("BarHead_%d" % kg, bm, [rubber], smooth_angle=35)


def build_plate_tree(mats, plates):
    steel, rubber, chrome = mats["steel"], mats["rubber"], mats["chrome"]
    cx, cy = TREE_XY
    wheel = _cyl_mesh("Tree_caster_wheel", 0.034, 0.024, rubber, 16)
    # base: two long tubes along x on casters + cross tube (ref 270)
    for s in (-1, 1):
        y = cy + s * 0.19
        _bar("Tree_base_%d" % s, (cx - 0.34, y, 0.095), (cx + 0.34, y, 0.095), 0.05, 0.05, steel, hint=(0, 0, 1))
        for xx in (cx - 0.29, cx + 0.29):
            _box("Tree_caster_fork_%d_%.2f" % (s, xx), (0.04, 0.035, 0.03), (xx, y, 0.057), steel, bevel=0.002)
            _ob("Tree_caster_%d_%.2f" % (s, xx), wheel, (xx, y, 0.0345), (math.pi / 2, 0, 0))
    _bar("Tree_cross", (cx, cy - 0.215, 0.095), (cx, cy + 0.215, 0.095), 0.06, 0.05, steel, hint=(0, 0, 1))
    _bar("Tree_post", (cx, cy, 0.12), (cx, cy, 1.48), 0.06, 0.06, steel, hint=(1, 0, 0))
    _rod("Tree_bar_sleeve", (cx, cy, 1.48), (cx, cy, 1.61), 0.031, steel, seg=20)
    _rod("Tree_bar_sleeve_lip", (cx, cy, 1.603), (cx, cy, 1.615), 0.036, rubber, seg=20)
    levels = {
        0.37: {+1: ["b25", "b25"], -1: ["b25", "b20", "b20"]},
        0.86: {+1: ["b15", "b15", "b10"], -1: ["b10", "b10", "b5"]},
        1.35: {+1: ["i20", "i20", "i20"], -1: ["i10", "i10", "i5"]},
    }
    for z, sides in levels.items():
        for s, stack in sides.items():
            _rod("Tree_horn_%.2f_%d" % (z, s), (cx + s * 0.03, cy, z), (cx + s * 0.33, cy, z), 0.025, chrome, seg=20)
            _rod("Tree_horn_tip_%.2f_%d" % (z, s), (cx + s * 0.33, cy, z), (cx + s * 0.345, cy, z), 0.031, rubber, seg=20)
            x = cx + s * 0.034
            for i, key in enumerate(stack):
                R, t = plate_dims(key)
                xc = x + s * (t / 2 + 0.0035)
                zc = z + 0.025 - 0.0262   # the bore rests on the top of the horn
                pl = _ob("Plate_%s_%.2f_%d_%d" % (key, z, s, i), plates[key], (xc, cy, zc))
                # spin about the plate's own axis first, then turn that axis onto the horn (world X)
                pl.rotation_mode = "QUATERNION"
                pl.rotation_quaternion = (Matrix.Rotation(math.pi / 2 * s, 4, "Y")
                                          @ Matrix.Rotation(math.radians(37 * i + 55 * s + 90 * z), 4, "Z")).to_quaternion()
                x = xc + s * (t / 2 + 0.0035)


def build_floor_dumbbells(dbm):
    out = []
    for kg, xy, yaw in ((14, (-6.36, 3.58), 28), (14, (-6.10, 3.34), -12), (10, (-1.73, 2.27), 86), (10, (-1.71, 2.44), 94)):
        f, L = db_dims(kg)
        out.append(_ob("DB_floor_%s_%.2f" % (_fmt(kg), xy[0] + xy[1]), dbm[kg], (xy[0], xy[1], f / 2 + 0.001),
                       (0, 0, math.radians(yaw))))
    return out


# ---------------------------------------------------------------- public API
def _clear():
    c = bpy.data.collections.get(COLL)
    if c is None:
        return
    for ob in list(c.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.name.startswith(P) and me.users == 0:
            bpy.data.meshes.remove(me)


def _materials():
    return {
        "steel": _mat_basic("RackSteel_Black", (0.020, 0.021, 0.023), rough=0.42, metal=0.55, coat=0.3),
        "silver": _mat_basic("RackSteel_Silver", (0.42, 0.44, 0.46), rough=0.35, metal=0.75),
        "rubber": _mat_basic("Rubber_Black", (0.012, 0.012, 0.013), rough=0.78),
        "chrome": _mat_basic("Chrome", (0.86, 0.87, 0.88), rough=0.10, metal=1.0),
        "knurl": _mat_knurl("Chrome_Knurl"),
        "alu_black": _mat_basic("Alu_BlackAnodised", (0.025, 0.026, 0.028), rough=0.32, metal=0.85),
        "mirror": _mat_basic("Mirror_Silvered", (0.93, 0.94, 0.93), rough=0.015, metal=1.0),
        "heads": _mat_tex("DB_HeadRubber", "head_faces.png", rough=0.62, bump=0.15),
        "plates": _mat_tex("PlateFaces", "plate_faces.png", rough=0.55, bump=0.12),
    }


def _tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for ob in objs:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        ev.to_mesh_clear()
    return n


def apply() -> dict:
    global _new
    _clear()
    _new = []
    root = bpy.data.objects.new(P + "ROOT", None)
    root.empty_display_size = 0.3
    _coll().objects.link(root)
    _ROOT["root"] = root
    mats = _materials()
    labels = head_labels()
    dbm = {}
    for kg in DB_TOP + DB_BOT:
        dbm[kg] = dumbbell_mesh(kg, mats["heads"], mats["chrome"], mats["knurl"], labels.index(("db", kg)))
    heads = {kg: barbell_head_mesh(kg, mats["heads"], labels.index(("bar", kg))) for kg in BAR_KG}
    plates = {p[0]: plate_mesh(p[0], mats["plates"], mats["chrome"]) for p in PLATES}

    build_mirror(mats)
    fx, n_rack = build_dumbbell_rack(mats, dbm)
    build_barbell_rack(mats, heads)
    build_plate_tree(mats, plates)
    build_floor_dumbbells(dbm)
    bpy.context.view_layer.update()

    objs = list(_new)
    mn, mx = [9e9] * 3, [-9e9] * 3
    for ob in objs:
        if ob.type != "MESH":
            continue
        for c in ob.bound_box:
            p = ob.matrix_world @ Vector(c)
            for i in range(3):
                mn[i], mx[i] = min(mn[i], p[i]), max(mx[i], p[i])
    return {
        "package": KEY,
        "collection": COLL,
        "objects_added": len(objs) + 1,
        "triangles_added": _tri_count(objs),
        "dumbbells_on_rack": n_rack,
        "rack_centre_frame_x": round(fx, 3),
        "existing_objects_touched": [],
        "bbox_world": [[round(v, 3) for v in mn], [round(v, 3) for v in mx]],
    }
