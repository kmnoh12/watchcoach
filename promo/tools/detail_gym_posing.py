"""Detail package `gym_posing`: posing room overhaul (stage, light rig, pump-up corner, amenities).

Run inside Blender (scene_gym.blend open):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_gym_posing; detail_gym_posing.apply()

Regenerate the printed graphics / wood textures (PIL, outside Blender):
    python3 promo/tools/detail_gym_posing.py --textures   (needs PIL + numpy)

Room frame (world metres, from gym_posing_room.py, verified by probe): x -3.30 (wall mirror) .. +0.40 (feature
wall, ledge front at x 0.0), y -10.50 (back side wall) .. -6.935 (door wall lining), floor z 0, ceiling z 3.20.
The poser stands at POSE_SPOT (-0.50, -8.70) facing the wall mirror (-X); the hero's selfie tripod at (-1.55, -8.10)
is NOT touched.

Reference photos:
  stage       work/refs/interior/180 (raised oak posing counter with LED-lit arched mirrors),
              work/refs/gym/247, 250 (wood platforms with warm LED under the edge), 253 (stage marking)
  light rig   gym/253, interior/180 (vertical LED bars between mirror panels), gym/247 (ceiling track spots),
              interior/084 (black linear bar with gold cylinder heads), interior/096 (selfie posing with ring light)
  arch mirror interior/152, 180 (arched mirror with halo backlight)
  pump-up     interior/076, 079 (rubber flooring, light hex dumbbell racks), gym/247 (props on the platform)
  amenities   interior/091-100 (body-profile shoots: oil, towels, water), gym/278/280/282 (acrylic LED sign)
  fan         interior/100 (cream fan beside the posing spot), interior/073/078 (fans everywhere in Korean gyms)
  floor       gym/253, 254 (dark wood plank floor in mirror/stretch rooms)
New objects only (collection DETAIL_gym_posing); no existing object is modified.
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

KEY = "gym_posing"
COLL = "DETAIL_gym_posing"
PFX = "Dgym_posing_"
HERE = os.path.dirname(os.path.abspath(__file__))
PART_DIR = os.path.normpath(os.path.join(HERE, "..", "parts", "detail_gym_posing"))
FONT = os.path.normpath(os.path.join(HERE, "..", "parts", "fonts", "NanumGothic-Bold.ttf"))

# Room frame
X0, X1 = -3.30, 0.40          # wall-mirror wall / feature wall inner faces
MIR_X = -3.284                # wall-mirror glass front face
LEDGE_X = 0.0                 # feature-wall ledge front
YB, YF = -10.50, -6.935       # back side wall face / door-wall lining face
H = 3.20
POSE = (-0.50, -8.70)
# Posing stage (public: the integrator lifts a poser on POSE_SPOT by STAGE_TOP)
SX0, SX1, SY0, SY1 = -1.05, -0.07, -9.35, -8.05
STAGE_TOP = 0.12
FLOOR_Z = 0.003               # plank overlay top (3 mm over the existing concrete floor)
PLANK_TILE = 2.4              # metres covered by one floor texture tile
OAK_TILE = 1.2


# --------------------------------------------------------------------------------------------
# Texture generation (PIL) -------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def make_textures():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    os.makedirs(PART_DIR, exist_ok=True)
    rnd = np.random.default_rng(7)

    def F(sz):
        return ImageFont.truetype(FONT, sz)

    def grain_field(w, h, stretch, rng):
        """Long fibrous wood grain: low-res noise stretched along x, plus fine streaks."""
        small = rng.random((max(2, h // 3), max(2, w // stretch)))
        g = Image.fromarray((small * 255).astype("uint8")).resize((w, h), Image.BILINEAR)
        g = np.asarray(g.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32) / 255.0
        streak = rng.random((h, max(2, w // (stretch * 3))))
        s = Image.fromarray((streak * 255).astype("uint8")).resize((w, h), Image.BILINEAR)
        s = np.asarray(s, dtype=np.float32) / 255.0
        return 0.65 * g + 0.35 * s

    def planks(size, tile_m, plank_w, len_rng, base, var, seam, name, along_x=True, seed=1):
        rng = np.random.default_rng(seed)
        px_m = size / tile_m
        pw = int(round(plank_w * px_m))
        n_rows = size // pw
        pw = size // n_rows
        img = np.zeros((size, size, 3), np.float32)
        for r in range(n_rows):
            y0, y1 = r * pw, (r + 1) * pw
            x = -int(rng.uniform(0, len_rng[1]) * px_m)
            while x < size:
                L = int(rng.uniform(*len_rng) * px_m)
                xa, xb = max(0, x), min(size, x + L)
                if xb > xa:
                    tone = np.array(base) * (1 + rng.uniform(-var, var)) + rng.uniform(-2, 2, 3)
                    g = grain_field(xb - xa, pw, 40, rng)
                    knot = rng.random() < 0.25
                    block = tone[None, None, :] * (0.78 + 0.42 * g[..., None])
                    if knot:
                        ky, kx = rng.integers(4, pw - 4), rng.integers(0, xb - xa)
                        yy, xx = np.mgrid[0:pw, 0:xb - xa]
                        d = np.sqrt(((yy - ky) * 2.5) ** 2 + ((xx - kx) * 0.6) ** 2)
                        block *= (0.75 + 0.25 * np.clip(d / 18.0, 0, 1))[..., None]
                    img[y0:y1, xa:xb] = block
                    img[y0:y1, xa:min(size, xa + 2)] = seam      # butt joint
                x += L
            img[y0:y0 + 2, :] = seam                              # long seam
        im = Image.fromarray(np.clip(img, 0, 255).astype("uint8"))
        if not along_x:
            im = im.transpose(Image.ROTATE_90)
        im.save(os.path.join(PART_DIR, name), optimize=True)

    # Dark smoked-oak vinyl planks (gym/253-254), planks run along world X (towards the wall mirror)
    planks(2048, PLANK_TILE, 0.18, (0.9, 1.8), (64, 47, 35), 0.18, (16, 12, 10), "floor_planks.png", seed=3)
    # Natural oak stage top (interior/180, gym/247), boards run along world Y
    planks(1024, OAK_TILE, 0.12, (0.6, 1.2), (168, 124, 84), 0.10, (70, 48, 30), "stage_oak.png",
           along_x=True, seed=5)

    # ---- Pose-guide poster (A1 portrait 0.594 x 0.841) --------------------------------------
    W, Hh = 1188, 1682
    im = Image.new("RGB", (W, Hh), (20, 20, 22))
    d = ImageDraw.Draw(im)
    RED = (214, 34, 40)
    d.rectangle([0, 0, W, 210], fill=(12, 12, 13))
    d.text((60, 40), "POSING GUIDE", font=F(92), fill=(245, 245, 245))
    d.text((64, 148), "바디프로필 · 규정 포즈 7", font=F(44), fill=RED)
    d.rectangle([0, 206, W, 214], fill=RED)

    def figure(cx, cy, s, pose):
        """Pictogram bodybuilder; joint coords in a 0..1 box (y down)."""
        P = {k: (cx + (v[0] - 0.5) * s, cy + (v[1] - 0.5) * s) for k, v in pose.items()}
        col = (236, 236, 236)
        lw = int(s * 0.085)

        def limb(a, b, w=lw):
            d.line([P[a], P[b]], fill=col, width=w)
            for p in (P[a], P[b]):
                d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=col)
        # torso: V-taper polygon
        d.polygon([P["sl"], P["sr"], P["hr"], P["hl"]], fill=col)
        hx, hy = P["head"]
        r = s * 0.065
        d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=col)
        limb("neck", "head", int(lw * 0.9))
        for side in "lr":
            limb("s" + side, "e" + side, int(lw * 1.1))
            limb("e" + side, "w" + side, int(lw * 0.9))
            limb("h" + side, "k" + side, int(lw * 1.25))
            limb("k" + side, "f" + side, int(lw * 1.0))

    base = dict(head=(0.5, 0.10), neck=(0.5, 0.18), sl=(0.33, 0.23), sr=(0.67, 0.23), hl=(0.43, 0.52),
                hr=(0.57, 0.52), kl=(0.40, 0.73), kr=(0.60, 0.73), fl=(0.39, 0.95), fr=(0.61, 0.95))
    poses = [
        ("프론트 더블 바이셉스", "FRONT DOUBLE BICEPS",
         dict(el=(0.14, 0.22), wl=(0.20, 0.04), er=(0.86, 0.22), wr=(0.80, 0.04))),
        ("프론트 랫 스프레드", "FRONT LAT SPREAD",
         dict(el=(0.20, 0.38), wl=(0.42, 0.50), er=(0.80, 0.38), wr=(0.58, 0.50))),
        ("사이드 체스트", "SIDE CHEST",
         dict(sl=(0.38, 0.23), sr=(0.62, 0.23), el=(0.40, 0.42), wl=(0.58, 0.44), er=(0.66, 0.44),
              wr=(0.58, 0.46), kl=(0.46, 0.73), fl=(0.50, 0.95))),
        ("백 더블 바이셉스", "BACK DOUBLE BICEPS",
         dict(el=(0.12, 0.20), wl=(0.18, 0.03), er=(0.88, 0.20), wr=(0.82, 0.03), kl=(0.36, 0.74),
              fl=(0.33, 0.95))),
        ("백 랫 스프레드", "BACK LAT SPREAD",
         dict(sl=(0.29, 0.23), sr=(0.71, 0.23), el=(0.17, 0.38), wl=(0.42, 0.50), er=(0.83, 0.38),
              wr=(0.58, 0.50))),
        ("사이드 트라이셉스", "SIDE TRICEPS",
         dict(sl=(0.38, 0.23), sr=(0.62, 0.23), el=(0.38, 0.40), wl=(0.42, 0.56), er=(0.62, 0.40),
              wr=(0.50, 0.56), kl=(0.46, 0.73), fl=(0.50, 0.95))),
        ("앱도미널 앤 타이", "ABDOMINALS & THIGH",
         dict(el=(0.18, 0.06), wl=(0.42, 0.06), er=(0.82, 0.06), wr=(0.58, 0.06), kr=(0.66, 0.72),
              fr=(0.70, 0.95))),
    ]
    cw, ch = W // 2, 350
    for i, (ko, en, over) in enumerate(poses):
        col_, row = i % 2, i // 2
        x0, y0 = col_ * cw, 240 + row * ch
        d.rounded_rectangle([x0 + 24, y0 + 8, x0 + cw - 24, y0 + ch - 14], 14, fill=(34, 34, 37))
        d.text((x0 + 44, y0 + 22), f"{i + 1:02d}", font=F(40), fill=RED)
        pose = dict(base)
        pose.update(over)
        figure(x0 + 180, y0 + 190, 260, pose)
        d.text((x0 + 300, y0 + 110), ko, font=F(34), fill=(240, 240, 240))
        d.text((x0 + 300, y0 + 160), en, font=F(22), fill=(160, 160, 166))
        d.line([x0 + 300, y0 + 205, x0 + cw - 50, y0 + 205], fill=(70, 70, 76), width=2)
        d.text((x0 + 300, y0 + 220), "3초 유지 · 호흡 멈추지 않기", font=F(20), fill=(150, 150, 156))
    # last cell: tips
    x0, y0 = cw, 240 + 3 * ch
    d.rounded_rectangle([x0 + 24, y0 + 8, x0 + cw - 24, y0 + ch - 14], 14, fill=RED)
    tips = ["촬영 전 체크", "· 펌핑 10분 (밴드·덤벨)", "· 오일은 얇게 고르게", "· 조명 정면 45°", "· 무대 X 표시에 서기"]
    for k, t in enumerate(tips):
        d.text((x0 + 50, y0 + 34 + k * 56), t, font=F(36 if k == 0 else 28), fill=(255, 255, 255))
    d.rectangle([0, Hh - 90, W, Hh], fill=(12, 12, 13))
    d.text((60, Hh - 66), "WATCHCOACH  POSING ROOM", font=F(38), fill=(200, 200, 204))
    d.text((W - 330, Hh - 60), "사용 후 정리 부탁드려요", font=F(26), fill=RED)
    im.save(os.path.join(PART_DIR, "poster_pose_guide.png"), optimize=True)

    # ---- Tanning-oil label (wraps ~200 deg of a 30 mm bottle) ---------------------------------
    im = Image.new("RGB", (512, 256), (52, 26, 12))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 512, 16], fill=(196, 150, 70))
    d.rectangle([0, 240, 512, 256], fill=(196, 150, 70))
    d.text((60, 50), "BRONZE", font=F(64), fill=(232, 190, 110))
    d.text((64, 130), "TANNING OIL  · 250ml", font=F(28), fill=(240, 222, 190))
    d.text((64, 180), "컬러 오일 · 무대용", font=F(28), fill=(240, 222, 190))
    im.save(os.path.join(PART_DIR, "label_tan_oil.png"), optimize=True)

    # ---- Water bottle label --------------------------------------------------------------------
    im = Image.new("RGB", (512, 128), (232, 242, 250))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 512, 34], fill=(26, 98, 178))
    d.rectangle([0, 100, 512, 128], fill=(26, 98, 178))
    d.text((40, 40), "생수 500ml", font=F(46), fill=(26, 98, 178))
    d.text((330, 50), "MINERAL", font=F(30), fill=(70, 130, 190))
    im.save(os.path.join(PART_DIR, "label_water.png"), optimize=True)

    # ---- Arched mirror halo (RGBA glow on the wall around the mirror) --------------------------
    S = 512
    W2, H2 = 384, 1024        # plane 0.90 x 2.40 m -> ~2.35 mm/px
    yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float32)
    # arch: half-width 0.325 m -> 139 px, straight side from bottom, round top
    cx, rpx = W2 / 2, 139.0
    # halo plane spans z 0.00 .. 2.40 (see _arch_mirror): arc centre z 1.855, mirror bottom z 0.30
    top_c = H2 - 1.855 / 2.40 * H2
    y_b = H2 - 0.30 / 2.40 * H2
    dx = np.abs(xx - cx)
    dist_side = dx - rpx
    dist_arc = np.sqrt((xx - cx) ** 2 + (yy - top_c) ** 2) - rpx
    dist = np.where(yy < top_c, dist_arc, dist_side)
    dist = np.where(yy > y_b, np.maximum(dist, (yy - y_b) * 1.5), dist)
    glow = np.clip(1.0 - np.maximum(dist, 0) / 70.0, 0, 1) ** 2.2
    glow = np.where(dist < -8, 0, glow)
    a = (glow * 255).astype("uint8")
    rgb = np.zeros((H2, W2, 4), "uint8")
    rgb[..., 0], rgb[..., 1], rgb[..., 2], rgb[..., 3] = 255, 214, 160, a
    Image.fromarray(rgb, "RGBA").save(os.path.join(PART_DIR, "arch_halo.png"), optimize=True)
    del S
    print("textures written to", PART_DIR)


# --------------------------------------------------------------------------------------------
# Blender helpers ----------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
_C = None
_ADDED = []


def _mat(name, color, rough=0.5, metal=0.0, emit=0.0, emit_color=None, alpha=None, transmission=0.0, ior=1.45,
         coat=0.0):
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
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    b.inputs["Coat Weight"].default_value = coat
    m.roughness = rough
    m.metallic = metal
    if alpha is not None or transmission > 0:
        try:
            m.surface_render_method = "BLENDED" if alpha is not None else "DITHERED"
        except AttributeError:
            pass
    return m


def _image(fname):
    img = bpy.data.images.load(os.path.join(PART_DIR, fname), check_existing=True)
    if not img.packed_file:
        img.pack()
    return img


def _img_mat(name, fname, emit=0.0, rough=0.45, metal=0.0, coat=0.0, alpha_glow=None):
    """Image-textured Principled material. alpha_glow=(strength): emissive, alpha-blended halo decal."""
    name = PFX + name
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _image(fname)
    tex.interpolation = "Cubic"
    if alpha_glow is not None:
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = alpha_glow
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            pass
        m.diffuse_color = (1.0, 0.84, 0.63, 0.4)
        return m
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    if emit:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return m


def _emit_mat(name, color, strength):
    name = PFX + name
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (*color, 1)
    return m


def _finish(ob, smooth=False, parent=None):
    _C.objects.link(ob)
    if smooth and ob.type == "MESH":
        for p in ob.data.polygons:
            p.use_smooth = True
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    ob["detail_pkg"] = KEY
    _ADDED.append(ob)
    return ob


def _rot(rot):
    return [math.radians(a) for a in rot]


def _obj(name, data, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, smooth=False, scale=None):
    ob = bpy.data.objects.new(PFX + name, data)
    ob.location = loc
    ob.rotation_euler = _rot(rot)
    if scale:
        ob.scale = scale
    return _finish(ob, smooth, parent)


def _bm_mesh(name, bm, mats):
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return me


def _bevel(ob, w, seg=2):
    md = ob.modifiers.new("Bevel", "BEVEL")
    md.width = w
    md.segments = seg
    md.limit_method = "ANGLE"
    return ob


def box_mesh(name, size, mat):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    return _bm_mesh(name, bm, [mat])


def box(name, size, mat, loc, rot=(0, 0, 0), bevel=0.0, seg=2, parent=None):
    ob = _obj(name, box_mesh(name, size, mat), loc, rot, parent)
    if bevel:
        _bevel(ob, min(bevel, min(size) * 0.45), seg)
    return ob


def cyl_mesh(name, r, h, mat, seg=16, r2=None, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    for f in bm.faces:
        f.smooth = smooth and abs(f.normal.z) < 0.5
    return _bm_mesh(name, bm, [mat])


def cyl(name, r, h, mat, loc, rot=(0, 0, 0), seg=16, r2=None, smooth=True, parent=None):
    return _obj(name, cyl_mesh(name, r, h, mat, seg, r2, smooth), loc, rot, parent)


def rod(name, a, b, r, mat, seg=8, parent=None):
    """Cylinder from point a to point b (in parent space)."""
    a, b = Vector(a), Vector(b)
    ob = _obj(name, cyl_mesh(name, r, (b - a).length, mat, seg), tuple((a + b) / 2), parent=parent)
    ob.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    return ob


def lathe_mesh(name, profile, mats, seg=16, mat_idx=None):
    """Revolve [(r, z), ...] around Z. r == 0 rings collapse to a pole."""
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
    return _bm_mesh(name, bm, mats)


def torus_mesh(name, R, r, mat, seg=24, sides=8, rx=1.0):
    """Torus in XY; rx scales the tube cross-section along the axis (flat ring diffusers)."""
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(sides):
            b = 2 * math.pi * j / sides
            rr = R + r * math.cos(b)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), r * rx * math.sin(b))))
        rings.append(ring)
    for i in range(seg):
        for j in range(sides):
            f = bm.faces.new((rings[i][j], rings[(i + 1) % seg][j], rings[(i + 1) % seg][(j + 1) % sides],
                              rings[i][(j + 1) % sides]))
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _bm_mesh(name, bm, [mat])


def sweep_mesh(name, path, width, thick, mat, closed=True):
    """Flat strap swept along a polyline in the XZ plane; width along Y (resistance bands)."""
    bm = bmesh.new()
    n = len(path)
    rings = []
    for i, p in enumerate(path):
        p = Vector(p)
        a = Vector(path[(i - 1) % n] if closed or i > 0 else path[i])
        b = Vector(path[(i + 1) % n] if closed or i < n - 1 else path[i])
        t = (b - a).normalized()
        nrm = Vector((-t.z, 0, t.x))  # in-plane normal
        ring = []
        for (u, v) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            ring.append(bm.verts.new(p + nrm * (u * thick / 2) + Vector((0, v * width / 2, 0))))
        rings.append(ring)
    segs = n if closed else n - 1
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(4):
            f = bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
            f.smooth = False
    if not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _bm_mesh(name, bm, [mat])


def label_band_mesh(name, r, h, arc_deg, mat, seg=12):
    """Open cylinder patch (front arc) with 0..1 UVs, centred on -Y (faces the viewer at rot 0)."""
    co, faces, uvs = [], [], []
    for i in range(seg + 1):
        a = math.radians(-90 - arc_deg / 2 + arc_deg * i / seg)
        for z in (-h / 2, h / 2):
            co.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(seg):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    me = bpy.data.meshes.new(PFX + name)
    me.from_pydata(co, [], faces)
    layer = me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        vi = loop.vertex_index
        layer.data[li].uv = ((vi // 2) / seg, vi % 2)
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    return me


def quad_mesh(name, w, h, mat, facing="+y", uv_rect=(0, 0, 1, 1)):
    """Quad centred at origin. '+y': normal +Y (vertical, XZ); '-y': normal -Y; '+z': lying flat."""
    a, b = w / 2, h / 2
    if facing == "-y":
        co = [(-a, 0, -b), (a, 0, -b), (a, 0, b), (-a, 0, b)]
    elif facing == "+y":
        co = [(a, 0, -b), (-a, 0, -b), (-a, 0, b), (a, 0, b)]
    else:
        co = [(-a, -b, 0), (a, -b, 0), (a, b, 0), (-a, b, 0)]
    u0, v0, u1, v1 = uv_rect
    uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    me = bpy.data.meshes.new(PFX + name)
    me.from_pydata(co, [], [(0, 1, 2, 3)])
    layer = me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        layer.data[li].uv = uv[loop.vertex_index]
    me.materials.append(mat)
    return me


def _empty(name, loc, rot=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(PFX + name, None)
    e.empty_display_size = 0.1
    e.location = loc
    e.rotation_euler = _rot(rot)
    return _finish(e, parent=parent)


def _area(name, loc, rot, size, size_y, energy, color, shadow=False, specular=0.0, parent=None):
    li = bpy.data.lights.new(PFX + name, "AREA")
    li.shape = "RECTANGLE"
    li.size, li.size_y = size, size_y
    li.energy = energy
    li.color = color
    li.use_shadow = shadow
    li.specular_factor = specular
    ob = _obj(name, li, loc, rot, parent)
    ob.visible_glossy = specular > 0
    return ob


def _spot(name, loc, target, energy, size_deg, blend, color, soft=0.03, shadow=True):
    li = bpy.data.lights.new(PFX + name, "SPOT")
    li.energy = energy
    li.color = color
    li.spot_size = math.radians(size_deg)
    li.spot_blend = blend
    li.shadow_soft_size = soft
    li.use_shadow = shadow
    ob = _obj(name, li, loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


def _text(name, body, loc, rot, size, mat, extrude=0.0015, parent=None):
    cu = bpy.data.curves.new(PFX + name, "FONT")
    cu.body = body
    f = bpy.data.fonts.load(FONT, check_existing=True)
    if not f.packed_file:
        f.pack()
    cu.font = f
    cu.size = size
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.extrude = extrude
    cu.materials.append(mat)
    return _obj(name, cu, loc, rot, parent)


# --------------------------------------------------------------------------------------------
# Materials ----------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def _materials():
    M = {}
    M["planks"] = _img_mat("FloorPlanks", "floor_planks.png", rough=0.38, coat=0.15)
    M["oak"] = _img_mat("StageOak", "stage_oak.png", rough=0.32, coat=0.35)
    M["stage_black"] = _mat("StageBlack", (0.010, 0.010, 0.011), rough=0.55)
    M["led_warm"] = _emit_mat("LEDWarm", (1.0, 0.80, 0.56), 6.0)
    M["led_white"] = _emit_mat("LEDNeutral", (1.0, 0.93, 0.84), 9.0)
    M["tape_white"] = _mat("TapeWhite", (0.80, 0.80, 0.78), rough=0.7)
    M["tape_yellow"] = _mat("TapeYellow", (0.85, 0.62, 0.04), rough=0.7)
    M["alu"] = _mat("AluAnodised", (0.62, 0.63, 0.65), rough=0.35, metal=1.0)
    M["black_metal"] = _mat("BlackSteel", (0.015, 0.015, 0.016), rough=0.45, metal=0.6)
    M["matte_black"] = _mat("MatteBlackPlastic", (0.018, 0.018, 0.019), rough=0.6)
    M["gold"] = _mat("BrushedBrass", (0.80, 0.60, 0.32), rough=0.30, metal=1.0)
    M["rubber"] = _mat("RubberTile", (0.022, 0.022, 0.024), rough=0.85)
    M["chrome"] = _mat("Chrome", (0.80, 0.80, 0.82), rough=0.12, metal=1.0)
    M["hex_rubber"] = _mat("HexRubber", (0.025, 0.025, 0.027), rough=0.65)
    M["fan_white"] = _mat("FanWhite", (0.78, 0.78, 0.76), rough=0.45)
    M["fan_blade"] = _mat("FanBladeGrey", (0.35, 0.37, 0.40), rough=0.4)
    M["mirror"] = _mat("Mirror", (0.88, 0.89, 0.90), rough=0.0, metal=1.0)
    M["acrylic"] = _mat("Acrylic", (0.9, 0.95, 0.97), rough=0.03, alpha=0.18)
    M["sign_text"] = _emit_mat("SignText", (1.0, 0.96, 0.90), 7.0)
    M["foam"] = _mat("GripFoam", (0.03, 0.03, 0.032), rough=0.9)
    M["roller"] = _mat("FoamRollerBlue", (0.03, 0.12, 0.40), rough=0.8)
    M["towel_white"] = _mat("TowelWhite", (0.80, 0.80, 0.78), rough=0.95)
    M["towel_grey"] = _mat("TowelGrey", (0.22, 0.22, 0.23), rough=0.95)
    M["amber"] = _mat("AmberBottle", (0.30, 0.12, 0.03), rough=0.12, transmission=0.6, ior=1.5)
    M["pet"] = _mat("PETBottle", (0.92, 0.96, 1.0), rough=0.05, transmission=1.0, ior=1.45)
    M["cap_blue"] = _mat("CapBlue", (0.03, 0.18, 0.55), rough=0.4)
    M["spray_white"] = _mat("SprayWhite", (0.85, 0.85, 0.83), rough=0.35)
    M["label_tan"] = _img_mat("LabelTan", "label_tan_oil.png", rough=0.35)
    M["label_water"] = _img_mat("LabelWater", "label_water.png", rough=0.3)
    M["poster"] = _img_mat("PoseGuidePoster", "poster_pose_guide.png", emit=0.08, rough=0.35)
    M["halo"] = _img_mat("ArchHalo", "arch_halo.png", alpha_glow=4.0)
    M["cardboard"] = _mat("Cardboard", (0.42, 0.30, 0.18), rough=0.85)
    M["bands"] = {k: _mat(f"Band{k}", c, rough=0.55) for k, c in (
        ("Yellow", (0.80, 0.62, 0.03)), ("Red", (0.55, 0.02, 0.02)), ("Black", (0.02, 0.02, 0.022)),
        ("Purple", (0.20, 0.04, 0.35)), ("Green", (0.04, 0.30, 0.08)))}
    return M


# --------------------------------------------------------------------------------------------
# Builders -----------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def _floor(M):
    """Dark smoked-oak vinyl planks over the whole room (gym/253-254); planks run toward the mirror."""
    xs, ys = (X0, X1), (YB, YF)
    co = [(xs[0], ys[0], FLOOR_Z), (xs[1], ys[0], FLOOR_Z), (xs[1], ys[1], FLOOR_Z), (xs[0], ys[1], FLOOR_Z)]
    me = bpy.data.meshes.new(PFX + "Floor planks")
    me.from_pydata(co, [], [(0, 1, 2, 3)])
    layer = me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        x, y, _ = co[loop.vertex_index]
        layer.data[li].uv = ((x - X0) / PLANK_TILE, (y - YB) / PLANK_TILE)
    me.materials.append(M["planks"])
    _obj("Floor planks", me)
    # aluminium threshold strip in the door opening (gym concrete -> planks)
    box("Door threshold strip", (0.882, 0.030, 0.006), M["alu"], (-1.45, -6.92, 0.003), bevel=0.002)


def _stage(M):
    """Low oak posing stage with warm LED under the lip and gaffer-tape marks (interior/180, gym/247/250)."""
    cx, cy = (SX0 + SX1) / 2, (SY0 + SY1) / 2
    w, d = SX1 - SX0, SY1 - SY0
    lip, top_t, inset = 0.035, 0.035, 0.05
    plinth_h = STAGE_TOP - top_t
    box("Stage plinth", (w - 2 * inset, d - 2 * inset, plinth_h - 0.002), M["stage_black"],
        (cx, cy, (plinth_h - 0.002) / 2 + FLOOR_Z + 0.001), bevel=0.004)
    # oak top with UVs from world XY
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((w, d, top_t)), verts=bm.verts)
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for lp in f.loops:
            v = lp.vert.co
            if abs(f.normal.z) > 0.5:
                lp[uvl].uv = ((v.y + cy) / OAK_TILE, (v.x + cx) / OAK_TILE)
            elif abs(f.normal.x) > 0.5:
                lp[uvl].uv = ((v.y + cy) / OAK_TILE, (v.z * 4) / OAK_TILE)
            else:
                lp[uvl].uv = ((v.x + cx) / OAK_TILE, (v.z * 4) / OAK_TILE)
    top = _obj("Stage oak top", _bm_mesh("Stage oak top", bm, [M["oak"]]), (cx, cy, STAGE_TOP - top_t / 2 + FLOOR_Z))
    _bevel(top, 0.006, 3)
    # LED strip under the lip, on the plinth face; light from 4 hidden area lights
    zl = plinth_h - 0.012 + FLOOR_Z
    for name, size, loc in (
        ("Stage LED +x", (0.004, d - 2 * inset, 0.008), (SX1 - inset + 0.002, cy, zl)),
        ("Stage LED -x", (0.004, d - 2 * inset, 0.008), (SX0 + inset - 0.002, cy, zl)),
        ("Stage LED +y", (w - 2 * inset, 0.004, 0.008), (cx, SY1 - inset + 0.002, zl)),
        ("Stage LED -y", (w - 2 * inset, 0.004, 0.008), (cx, SY0 + inset - 0.002, zl)),
    ):
        box(name, size, M["led_warm"], loc)
    col = (1.0, 0.78, 0.52)
    for name, loc, rot, sx, sy in (
        ("Stage glow +x", (SX1 - 0.03, cy, plinth_h - 0.02), (0, -35, 0), 0.02, d - 0.1),
        ("Stage glow -x", (SX0 + 0.03, cy, plinth_h - 0.02), (0, 35, 0), 0.02, d - 0.1),
        ("Stage glow +y", (cx, SY1 - 0.03, plinth_h - 0.02), (35, 0, 0), w - 0.1, 0.02),
        ("Stage glow -y", (cx, SY0 + 0.03, plinth_h - 0.02), (-35, 0, 0), w - 0.1, 0.02),
    ):
        _area(name, loc, rot, sx, sy, 6.0, col)
    # Gaffer-tape marks: white X on the pose spot, yellow foot marks and corner Ls
    zt = STAGE_TOP + FLOOR_Z + 0.0012
    tw, tt = 0.048, 0.0006
    for k, a in enumerate((45, -45)):
        box("Tape X", (0.30, tw, tt), M["tape_white"], (POSE[0], POSE[1], zt + 0.0007 * k), (0, 0, a))
    for s in (-1, 1):   # foot marks shoulder width apart, toes toward the mirror (-X)
        box("Tape foot", (0.16, tw * 0.7, tt), M["tape_yellow"], (POSE[0] - 0.02, POSE[1] + s * 0.17, zt))
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = cx + sx * (w / 2 - 0.08)
            y = cy + sy * (d / 2 - 0.08)
            box("Tape corner", (0.12, tw * 0.6, tt), M["tape_white"], (x - sx * 0.045, y, zt))
            box("Tape corner", (tw * 0.6, 0.12, tt), M["tape_white"], (x, y - sy * 0.045, zt + 0.0007))


def _mirror_led_bars(M):
    """Vertical LED bars on the wall mirror: both ends and over the two panel seams (gym/253, interior/180)."""
    ys = (-10.44, -9.312, -8.123, -6.995)
    z0, z1 = 0.12, 3.10
    hgt = z1 - z0
    chan = box_mesh("Mirror LED channel", (0.030, 0.046, hgt), M["alu"])
    diff = box_mesh("Mirror LED diffuser", (0.004, 0.034, hgt - 0.02), M["led_white"])
    for i, y in enumerate(ys):
        _obj(f"Mirror LED channel {i + 1}", chan, (MIR_X + 0.003 + 0.015, y, (z0 + z1) / 2))
        _obj(f"Mirror LED diffuser {i + 1}", diff, (MIR_X + 0.003 + 0.032, y, (z0 + z1) / 2))
        # Ry(-90): emitter -Z -> +X (into the room), local x -> world z
        _area(f"Mirror LED bar {i + 1}", (MIR_X + 0.040, y, (z0 + z1) / 2), (0, -90, 0), hgt - 0.05, 0.035,
              70.0, (1.0, 0.92, 0.82), shadow=True, specular=0.4)


def _track_rig(M):
    """Suspended black linear bar with brass-ringed cylinder spots aimed at the poser (interior/084, gym/247)."""
    bx, by0, by1, bz = -1.55, -9.85, -7.55, 2.78
    box("Spot bar", (0.035, by1 - by0, 0.045), M["matte_black"], (bx, (by0 + by1) / 2, bz), bevel=0.004)
    for y in (by0 + 0.3, by1 - 0.3):
        cyl("Spot bar rod", 0.005, H - bz - 0.02, M["matte_black"], (bx, y, (H + bz) / 2), seg=8)
        cyl("Spot bar canopy", 0.045, 0.02, M["matte_black"], (bx, y, H - 0.01), seg=20)
    target = Vector((POSE[0], POSE[1], STAGE_TOP + 1.25))
    head_body = cyl_mesh("Spot head body", 0.034, 0.13, M["matte_black"], seg=20)
    head_ring = cyl_mesh("Spot head brass ring", 0.0355, 0.018, M["gold"], seg=20)
    head_lens = cyl_mesh("Spot head lens", 0.026, 0.004, M["led_white"], seg=16, smooth=False)
    for i, y in enumerate((-9.45, -8.95, -8.45, -7.95)):
        mount = Vector((bx, y, bz - 0.0225))
        stem_end = mount + Vector((0, 0, -0.06))
        rod("Spot stem", mount, stem_end, 0.006, M["matte_black"])
        aim = (target + Vector((0, (y - POSE[1]) * 0.25, 0)) - stem_end).normalized()
        piv = _empty(f"Spot head {i + 1}", tuple(stem_end - aim * -0.0))
        piv.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
        # local -Z = beam axis; body centred 0.07 ahead of the yoke
        _obj("Spot head body", head_body, (0, 0, -0.065), parent=piv)
        _obj("Spot head ring", head_ring, (0, 0, -0.125), parent=piv)
        _obj("Spot head lens", head_lens, (0, 0, -0.133), parent=piv)
        loc = stem_end + aim * 0.14
        _spot(f"Track spot {i + 1}", tuple(loc), tuple(loc + aim), 320.0, 30, 0.35, (1.0, 0.93, 0.84), soft=0.03)


def _ring_light(M):
    """18-inch LED ring light on a light stand, aimed at the poser (interior/096 selfie posing)."""
    base = Vector((-1.30, -9.55, FLOOR_Z))
    hub_z = 0.62
    root = _empty("Ring light stand", tuple(base))
    for k in range(3):
        a = math.radians(90 + 120 * k)
        foot = Vector((0.34 * math.cos(a), 0.34 * math.sin(a), 0.012))
        rod("Ring stand leg", (0, 0, hub_z), foot, 0.008, M["black_metal"], parent=root)
        cyl("Ring stand foot", 0.014, 0.016, M["matte_black"], tuple(foot - Vector((0, 0, 0.004))), parent=root,
            seg=10)
        rod("Ring stand brace", (0, 0, 0.36), foot * 0.5 + Vector((0, 0, 0.17)), 0.004, M["black_metal"],
            parent=root)
    cyl("Ring stand hub", 0.022, 0.06, M["matte_black"], (0, 0, hub_z), parent=root, seg=12)
    cyl("Ring stand mast", 0.0125, 1.05, M["black_metal"], (0, 0, 0.60 + 1.05 / 2 - 0.05), parent=root, seg=12)
    cyl("Ring stand collar", 0.017, 0.035, M["matte_black"], (0, 0, 1.12), parent=root, seg=12)
    cyl("Ring stand top tube", 0.0095, 0.27, M["alu"], (0, 0, 1.12 + 0.135), parent=root, seg=12)
    centre = base + Vector((0, 0, 1.62))
    target = Vector((POSE[0], POSE[1], STAGE_TOP + 1.30))
    aim = (target - centre).normalized()
    head = _empty("Ring light head", tuple(centre))
    head.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    _obj("Ring housing", torus_mesh("Ring housing", 0.205, 0.028, M["matte_black"], seg=40, sides=8, rx=0.8),
         (0, 0, 0.008), parent=head)
    _obj("Ring diffuser", torus_mesh("Ring diffuser", 0.205, 0.022, M["led_white"], seg=40, sides=6, rx=0.6),
         (0, 0, -0.010), parent=head)
    # spigot from the stand top to the ring's bottom bracket, phone clamp in the centre
    q = aim.to_track_quat("-Z", "Y")
    bracket = centre + q @ Vector((0, -0.236, 0))
    rod("Ring spigot", tuple(base + Vector((0, 0, 1.385))), tuple(bracket), 0.008, M["black_metal"])
    box("Ring bracket", (0.05, 0.02, 0.03), M["matte_black"], (0, -0.236, 0.0), parent=head, bevel=0.003)
    rod("Ring phone arm", (0, -0.225, 0.0), (0, -0.02, 0.0), 0.005, M["black_metal"], parent=head)
    box("Ring phone clamp", (0.085, 0.022, 0.018), M["matte_black"], (0, 0, 0.0), parent=head, bevel=0.003)
    box("Ring phone", (0.078, 0.162, 0.008), M["matte_black"], (0, 0, -0.014), parent=head, bevel=0.003)
    li = bpy.data.lights.new(PFX + "Ring light", "AREA")
    li.shape = "DISK"
    li.size = 0.40
    li.energy = 90.0
    li.color = (1.0, 0.95, 0.90)
    li.use_shadow = True
    li.specular_factor = 0.0   # the emissive ring mesh already shows in mirrors
    _obj("Ring light", li, (0, 0, -0.025), parent=head)


def _pump_corner(M):
    """Rubber mat, 2-tier light hex dumbbell rack, push-up handles, foam roller (interior/076/079, gym/247)."""
    mx0, mx1, my0, my1 = -3.265, -2.06, -10.48, -9.05
    mt = 0.015
    box("Pump mat", (mx1 - mx0, my1 - my0, mt), M["rubber"],
        ((mx0 + mx1) / 2, (my0 + my1) / 2, FLOOR_Z + 0.001 + mt / 2), bevel=0.003)
    z0 = FLOOR_Z + 0.001 + mt
    # Rack: 0.9 m wide, 0.42 deep, against the back wall, two sloped trays
    rx0, rx1, ry0, ry1 = -3.10, -2.20, -10.46, -10.04
    tube = 0.04
    for x in (rx0 + tube / 2, rx1 - tube / 2):
        box("Rack foot", (tube, ry1 - ry0, tube), M["black_metal"], (x, (ry0 + ry1) / 2, z0 + tube / 2), bevel=0.004)
        rod("Rack upright front", (x, ry1 - 0.06, z0 + tube), (x, ry1 - 0.12, z0 + 0.76), 0.018, M["black_metal"])
        rod("Rack upright back", (x, ry0 + 0.06, z0 + tube), (x, ry0 + 0.10, z0 + 0.86), 0.018, M["black_metal"])
    tilt = -14.0   # front (room side, +y) lower
    tray_w = rx1 - rx0 - 0.08
    trays = ((0.36, (5, 6, 8)), (0.78, (2, 3, 4)))
    head_dims = {2: (0.040, 0.040), 3: (0.045, 0.046), 4: (0.050, 0.050), 5: (0.054, 0.056), 6: (0.057, 0.060),
                 8: (0.063, 0.066)}
    db_meshes = {}
    for kg, (r, L) in head_dims.items():
        bm = bmesh.new()
        hl = 0.065
        for s in (-1, 1):
            m = Matrix.Translation((0, s * (hl + L / 2), 0)) @ Matrix.Rotation(math.radians(90), 4, "X")
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=r, radius2=r, depth=L, matrix=m)
        n_head = len(bm.faces)
        m = Matrix.Rotation(math.radians(90), 4, "X")
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.016, radius2=0.016, depth=2 * hl + 0.01,
                              matrix=m)
        for i, f in enumerate(bm.faces):
            f.material_index = 0 if i < n_head else 1
            f.smooth = i >= n_head
        db_meshes[kg] = (_bm_mesh(f"Hex dumbbell {kg}kg", bm, [M["hex_rubber"], M["chrome"]]), r)
    for hz, kgs in trays:
        zc = z0 + hz
        ctr = Vector(((rx0 + rx1) / 2, (ry0 + ry1) / 2, zc))
        Rt = Matrix.Rotation(math.radians(tilt), 3, "X")
        box("Rack tray", (tray_w + 0.04, ry1 - ry0 - 0.06, 0.012), M["black_metal"], tuple(ctr), (tilt, 0, 0))
        box("Rack tray lip", (tray_w + 0.04, 0.012, 0.04), M["black_metal"],
            tuple(ctr + Rt @ Vector((0, (ry1 - ry0 - 0.06) / 2 + 0.006, 0.014))), (tilt, 0, 0))
        box("Rack tray rail", (0.03, ry1 - ry0 - 0.02, 0.03), M["black_metal"], (rx0 + 0.02, (ry0 + ry1) / 2, zc - 0.02),
            (tilt, 0, 0))
        box("Rack tray rail", (0.03, ry1 - ry0 - 0.02, 0.03), M["black_metal"], (rx1 - 0.02, (ry0 + ry1) / 2, zc - 0.02),
            (tilt, 0, 0))
        n = len(kgs) * 2
        pitch = tray_w / n
        for i in range(n):
            kg = kgs[i // 2]
            me, r = db_meshes[kg]
            x = rx0 + 0.04 + pitch * (i + 0.5)
            # lie on the tray (tilted about X: front lower); hex flat face down -> rot 30 about local Y
            # hex flats are already top/bottom (create_cone puts a vertex on +X)
            nrm = Rt @ Vector((0, 0, 1))
            c = Vector((x, (ry0 + ry1) / 2, zc)) + nrm * (0.006 + r * math.cos(math.radians(30)) + 0.001)
            _obj(f"Hex dumbbell {kg}kg", me, tuple(c), (tilt, 0, 0))
    # push-up handles (2 pairs) and a foam roller on the mat
    bm = bmesh.new()
    for s in (-1, 1):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((s * 0.075, 0, 0.01)) @
                              Matrix.Diagonal((0.05, 0.20, 0.02, 1)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((s * 0.075, 0, 0.065)) @
                              Matrix.Rotation(math.radians(-s * 12), 4, "Y") @ Matrix.Diagonal((0.025, 0.05, 0.10, 1)))
    n_frame = len(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.019, radius2=0.019, depth=0.13,
                          matrix=Matrix.Translation((0, 0, 0.11)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    for i, f in enumerate(bm.faces):
        f.material_index = 0 if i < n_frame else 1
        f.smooth = i >= n_frame
    ph = _bm_mesh("Pushup handle", bm, [M["matte_black"], M["foam"]])
    for i, (x, y, rz) in enumerate(((-2.62, -9.42, 8), (-2.30, -9.40, -6), (-2.85, -9.70, 80), (-2.86, -9.95, 95))):
        _obj("Pushup handle", ph, (x, y, z0), (0, 0, rz))
    cyl("Foam roller", 0.075, 0.45, M["roller"], (-2.38, -9.82, z0 + 0.075), (90, 0, 12), seg=20)
    # a pair of 3 kg dumbbells left on the mat
    me3, r3 = db_meshes[3]
    for i, (x, y) in enumerate(((-2.60, -9.18), (-2.42, -9.22))):
        _obj("Hex dumbbell 3kg floor", me3, (x, y, z0 + r3 * math.cos(math.radians(30)) + 0.001), (0, 0, 3 + 9 * i))


def _band_rail(M):
    """Wall hook rail with hanging power bands, right of the door (gym/247 accessories)."""
    yw = YF - 0.003
    zr = 1.62
    box("Band rail plate", (0.80, 0.012, 0.07), M["black_metal"], (-0.52, yw - 0.006, zr), bevel=0.003)
    bands = (("Yellow", 0.013), ("Red", 0.021), ("Black", 0.032), ("Purple", 0.044), ("Green", 0.064))
    for i, (col, w) in enumerate(bands):
        x = -0.82 + i * 0.15
        hook_tip = Vector((x, yw - 0.07, zr + 0.01))
        rod("Band hook", (x, yw - 0.012, zr - 0.015), (x, yw - 0.07, zr - 0.015), 0.006, M["chrome"])
        rod("Band hook tip", (x, yw - 0.07, zr - 0.018), tuple(hook_tip + Vector((0, 0, 0.03))), 0.006, M["chrome"])
        # loop hanging over the hook bar: two strands, small arc on top, wider U at the bottom (XZ plane)
        Lh = 0.80 + 0.05 * (i % 2)
        rt, rb = 0.010, 0.020 + 0.002 * i
        pts = [(rt * math.cos(math.radians(a)), 0, rt * math.sin(math.radians(a))) for a in range(180, -1, -20)]
        pts += [(rt + (rb - rt) * k / 6, 0, -Lh * k / 6) for k in range(1, 6)]
        pts += [(rb * math.cos(math.radians(a)), 0, -Lh + rb * math.sin(math.radians(a))) for a in range(0, -181, -20)]
        pts += [(-(rt + (rb - rt) * k / 6), 0, -Lh * k / 6) for k in range(5, 0, -1)]
        me = sweep_mesh(f"Power band {col}", pts, w, 0.0045, M["bands"][col])
        _obj(f"Power band {col}", me, (x, yw - 0.045, zr - 0.015), (0, 2.0 * (i - 2), 0))


def _shelf(M):
    """Black steel 4-tier open shelf by the door: towels, tanning oil, water (body-profile prep, interior/091-100)."""
    sx0, sx1, sy0, sy1 = -3.18, -2.28, -7.30, -6.955
    levels = (0.10, 0.52, 0.94, 1.36)
    post = 0.03
    for x in (sx0 + post / 2, sx1 - post / 2):
        for y in (sy0 + post / 2, sy1 - post / 2):
            box("Shelf post", (post, post, 1.40), M["black_metal"], (x, y, FLOOR_Z + 0.008 + 0.70), bevel=0.003)
            cyl("Shelf foot", 0.014, 0.008, M["matte_black"], (x, y, FLOOR_Z + 0.004), seg=10)
    for z in levels:
        box("Shelf board", (sx1 - sx0 - 0.004, sy1 - sy0 - 0.004, 0.018), M["black_metal"],
            ((sx0 + sx1) / 2, (sy0 + sy1) / 2, FLOOR_Z + z), bevel=0.002)
    top = lambda lv: FLOOR_Z + levels[lv] + 0.009 + 0.0008   # noqa: E731
    # Level 3 (top): wire basket of rolled white towels + folded grey stack
    bx, by = -2.94, (sy0 + sy1) / 2
    bw, bd, bh = 0.40, 0.28, 0.14
    z3 = top(3)
    box("Basket base", (bw, bd, 0.006), M["black_metal"], (bx, by, z3 + 0.003))
    for s in (-1, 1):
        box("Basket side", (bw, 0.004, bh), M["black_metal"], (bx, by + s * (bd / 2 - 0.002), z3 + bh / 2))
        box("Basket end", (0.004, bd - 0.008, bh), M["black_metal"], (bx + s * (bw / 2 - 0.002), by, z3 + bh / 2))
    roll = cyl_mesh("Rolled towel", 0.042, 0.26, M["towel_white"], seg=14)
    rolls = [(-0.13, 0.044), (-0.045, 0.044), (0.04, 0.044), (0.125, 0.044), (-0.088, 0.122), (0.0, 0.122),
             (0.085, 0.122)]
    for i, (dx, dz) in enumerate(rolls):
        _obj("Rolled towel", roll, (bx + dx, by, z3 + 0.006 + dz), (90, 0, 0))
    for k in range(4):
        box("Folded towel grey", (0.30, 0.22, 0.045), M["towel_grey"],
            (-2.52 + 0.004 * (k % 2), by + 0.003 * k, z3 + 0.0225 + k * 0.0455), (0, 0, 1.5 * (k % 3 - 1)),
            bevel=0.012, seg=2)
    # Level 2: tanning oil (amber pump bottles), spray tan can, tissue box
    z2 = top(2)
    bottle = lathe_mesh("Tan oil bottle", [(0, 0), (0.030, 0), (0.031, 0.004), (0.031, 0.150), (0.026, 0.162),
                                           (0.012, 0.170), (0.012, 0.182), (0, 0.182)], [M["amber"]], seg=16)
    pump = lathe_mesh("Tan oil pump", [(0, 0), (0.014, 0), (0.014, 0.018), (0.005, 0.020), (0.005, 0.050),
                                       (0, 0.050)], [M["matte_black"]], seg=10)
    label = label_band_mesh("Tan oil label", 0.0318, 0.10, 200, M["label_tan"])
    nozzle = box_mesh("Tan oil nozzle", (0.008, 0.035, 0.010), M["matte_black"])
    for i, (x, rz) in enumerate(((-3.07, -8), (-2.99, 15), (-2.91, -3))):
        y = sy0 + 0.11 + 0.02 * (i % 2)
        _obj("Tan oil bottle", bottle, (x, y, z2), (0, 0, rz))
        _obj("Tan oil label", label, (x, y, z2 + 0.075), (0, 0, rz))
        _obj("Tan oil pump", pump, (x, y, z2 + 0.180), (0, 0, rz))
        _obj("Tan oil nozzle", nozzle, (x + 0.0, y - 0.016, z2 + 0.225), (0, 0, rz))
    can = lathe_mesh("Spray can", [(0, 0), (0.030, 0), (0.032, 0.006), (0.032, 0.175), (0.022, 0.195),
                                   (0.0, 0.200)], [M["gold"]], seg=16)
    _obj("Bronzer spray can", can, (-2.80, sy0 + 0.12, z2))
    cyl("Spray can cap", 0.024, 0.045, M["spray_white"], (-2.80, sy0 + 0.12, z2 + 0.2225), seg=14)
    box("Tissue box", (0.24, 0.12, 0.09), M["spray_white"], (-2.50, by, z2 + 0.045), (0, 0, -4), bevel=0.004)
    box("Tissue slot", (0.12, 0.025, 0.004), M["matte_black"], (-2.50, by, z2 + 0.0905), (0, 0, -4))
    # Level 1: water bottles (row of 6 + a shrink pack in a carton)
    z1 = top(1)
    water = lathe_mesh("Water bottle", [(0, 0), (0.030, 0), (0.033, 0.006), (0.033, 0.150), (0.030, 0.165),
                                        (0.016, 0.195), (0.014, 0.205), (0, 0.205)], [M["pet"]], seg=16)
    wcap = cyl_mesh("Water cap", 0.0145, 0.018, M["cap_blue"], seg=12)
    wlabel = label_band_mesh("Water label", 0.0336, 0.05, 360, M["label_water"], seg=16)
    for i in range(6):
        x = -3.12 + i * 0.07
        y = sy0 + 0.08 + 0.012 * (i % 2)
        _obj("Water bottle", water, (x, y, z1), (0, 0, 20 * i))
        _obj("Water label", wlabel, (x, y, z1 + 0.10), (0, 0, 20 * i))
        _obj("Water cap", wcap, (x, y, z1 + 0.214))
    box("Water carton", (0.36, 0.25, 0.22), M["cardboard"], (-2.52, by + 0.01, z1 + 0.11), (0, 0, 2), bevel=0.004)
    # Level 0: towel return bin (grey) and spare folded white towels
    z0 = top(0)
    box("Towel return bin", (0.40, 0.28, 0.30), M["towel_grey"], (-2.94, by, z0 + 0.15), bevel=0.02)
    for k in range(3):
        box("Folded towel white", (0.30, 0.22, 0.045), M["towel_white"],
            (-2.52, by + 0.004 * k, z0 + 0.0225 + k * 0.0455), (0, 0, 2.0 * (k - 1)), bevel=0.012)


def _acrylic_sign(M):
    """Edge-lit acrylic slogan panel on standoffs (gym/278, 280, 282) above the shelf."""
    cx, cz = -2.73, 2.12
    w, h = 0.82, 0.38
    y = YF - 0.035
    box("Sign acrylic", (w, 0.008, h), M["acrylic"], (cx, y, cz))
    for sx in (-1, 1):
        for sz in (-1, 1):
            rod("Sign standoff", (cx + sx * (w / 2 - 0.03), YF, cz + sz * (h / 2 - 0.03)),
                (cx + sx * (w / 2 - 0.03), y - 0.006, cz + sz * (h / 2 - 0.03)), 0.009, M["chrome"], seg=12)
    box("Sign edge LED", (w - 0.01, 0.006, 0.004), M["led_white"], (cx, y, cz - h / 2 - 0.0005))
    _text("Sign line 1", "오늘의 펌핑이", (cx - 0.07, y - 0.0055, cz + 0.07), (90, 0, 0), 0.085, M["sign_text"])
    _text("Sign line 2", "내일의 바디프로필", (cx + 0.06, y - 0.0055, cz - 0.07), (90, 0, 0), 0.085,
          M["sign_text"])


def _poster(M):
    """A1 pose-guide poster in a thin black frame on the back wall."""
    cx, cz = -1.95, 1.55
    w, h = 0.594, 0.841
    y = YB + 0.004
    box("Poster frame", (w + 0.04, 0.020, h + 0.04), M["matte_black"], (cx, y + 0.010, cz), bevel=0.003)
    _obj("Pose guide poster", quad_mesh("Pose guide poster", w, h, M["poster"], "+y"), (cx, y + 0.0215, cz))


def _arch_mirror(M):
    """Full-length arched mirror with warm halo backlight (interior/152, 180) on the back wall by the stage."""
    cx, w, z0, z1 = -0.62, 0.65, 0.30, 2.18
    r = w / 2
    y_wall = YB
    seg = 16
    pts = [(cx - r, z0), (cx + r, z0)]
    for k in range(seg + 1):
        a = math.pi * k / seg
        pts.append((cx + r * math.cos(a), z1 - r + r * math.sin(a)))
    pts = pts[:2] + pts[2:]   # right side up over the arch to the left side

    def arch_mesh(name, inset, thick, mat):
        bm = bmesh.new()
        ring = []
        for (x, z) in pts:
            dx, dz = x - cx, z - (z1 - r)
            if z > z1 - r:
                k = (r - inset) / r
                x2, z2 = cx + dx * k, (z1 - r) + dz * k
            else:
                x2 = cx + math.copysign(r - inset, dx)
                z2 = z + (inset if z <= z0 + 1e-6 else 0)
            ring.append((x2, z2))
        front = [bm.verts.new((x, -thick / 2, z)) for x, z in ring]
        back = [bm.verts.new((x, thick / 2, z)) for x, z in ring]
        bm.faces.new(front[::-1])
        bm.faces.new(back)
        n = len(ring)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((front[i], front[j], back[j], back[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return _bm_mesh(name, bm, [mat])

    # backer (black, smaller) on the wall, mirror 30 mm proud with a black edge, halo decal on the wall
    _obj("Arch mirror backer", arch_mesh("Arch mirror backer", 0.06, 0.028, M["matte_black"]), (0, y_wall + 0.016, 0))
    _obj("Arch mirror edge", arch_mesh("Arch mirror edge", 0.0, 0.006, M["matte_black"]), (0, y_wall + 0.034, 0))
    _obj("Arch mirror glass", arch_mesh("Arch mirror glass", 0.006, 0.004, M["mirror"]), (0, y_wall + 0.0365, 0))
    box("Arch mirror LED", (w - 0.14, 0.006, 0.006), M["led_warm"], (cx, y_wall + 0.012, z0 + 0.065))
    # halo plane 0.90 x 2.40 m centred so that its arch matches (see make_textures)
    hz = z0 - 0.30 + 1.20
    _obj("Arch mirror halo", quad_mesh("Arch mirror halo", 0.90, 2.40, M["halo"], "+y"), (cx, y_wall + 0.0135, hz))
    _area("Arch halo light", (cx, y_wall + 0.05, (z0 + z1) / 2), (90, 0, 0), w * 0.6, (z1 - z0) * 0.8, 6.0,
          (1.0, 0.82, 0.60))


def _wall_fan(M):
    """45 cm wall-mount fan high over the pump corner, tilted down at the room (interior/100, 073)."""
    root = _empty("Wall fan", (-2.65, YB, 2.52))
    box("Fan wall plate", (0.10, 0.012, 0.14), M["fan_white"], (0, 0.006, 0), parent=root, bevel=0.004)
    rod("Fan arm", (0, 0.012, 0), (0, 0.11, -0.03), 0.012, M["fan_white"], parent=root)
    head = _empty("Fan head", (0, 0.13, -0.04), (-18, 0, 0), parent=root)   # head axis = +Y, tilted down
    cyl("Fan motor", 0.065, 0.14, M["fan_white"], (0, 0.03, 0), (90, 0, 0), parent=head, seg=20)
    cage_y = 0.17
    for yy, R in ((cage_y - 0.045, 0.215), (cage_y + 0.045, 0.215), (cage_y + 0.06, 0.15), (cage_y + 0.068, 0.08)):
        _obj("Fan cage ring", torus_mesh("Fan cage ring", R, 0.004, M["fan_white"], seg=36, sides=4),
             (0, yy, 0), (90, 0, 0), parent=head)
    for k in range(16):
        a = 2 * math.pi * k / 16
        c, s = math.cos(a), math.sin(a)
        rod("Fan cage spoke", (0.03 * c, cage_y + 0.072, 0.03 * s), (0.215 * c, cage_y + 0.045, 0.215 * s), 0.0022,
            M["fan_white"], seg=4, parent=head)
        rod("Fan cage spoke back", (0.07 * c, cage_y - 0.07, 0.07 * s), (0.215 * c, cage_y - 0.045, 0.215 * s), 0.0022,
            M["fan_white"], seg=4, parent=head)
    cyl("Fan badge", 0.04, 0.012, M["fan_white"], (0, cage_y + 0.075, 0), (90, 0, 0), parent=head, seg=16)
    cyl("Fan hub", 0.045, 0.04, M["fan_blade"], (0, cage_y, 0), (90, 0, 0), parent=head, seg=16)
    for k in range(3):
        a = 120 * k
        piv = _empty("Fan blade pivot", (0, cage_y, 0), (0, a, 0), parent=head)
        box("Fan blade", (0.11, 0.004, 0.15), M["fan_blade"], (0, 0, 0.12), (0, 0, 25), parent=piv, bevel=0.0015)


# --------------------------------------------------------------------------------------------
# Entry point --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------
def _clear():
    c = bpy.data.collections.get(COLL)
    if c is None:
        return
    for ob in list(c.all_objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
    for me in [m for m in bpy.data.meshes if m.name.startswith(PFX) and m.users == 0]:
        bpy.data.meshes.remove(me)


def apply() -> dict:
    global _C, _ADDED
    _clear()
    parent = bpy.data.collections.get("SET")
    _C = bpy.data.collections.get(COLL)
    if _C is None:
        _C = bpy.data.collections.new(COLL)
        (parent or bpy.context.scene.collection).children.link(_C)
    _ADDED = []
    M = _materials()
    _floor(M)
    _stage(M)
    _mirror_led_bars(M)
    _track_rig(M)
    _ring_light(M)
    _pump_corner(M)
    _band_rail(M)
    _shelf(M)
    _acrylic_sign(M)
    _poster(M)
    _arch_mirror(M)
    _wall_fan(M)

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    lo, hi = [1e9] * 3, [-1e9] * 3
    for ob in _C.all_objects:
        if ob.type in ("MESH", "FONT"):
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            tris += len(me.loop_triangles)
            mw = ob.matrix_world
            for v in me.vertices:
                p = mw @ v.co
                for i in range(3):
                    lo[i] = min(lo[i], p[i])
                    hi[i] = max(hi[i], p[i])
            ev.to_mesh_clear()
    return {
        "collection": COLL,
        "objects_added": len(_C.all_objects),
        "lights_added": sum(1 for o in _C.all_objects if o.type == "LIGHT"),
        "triangles_added": tris,
        "existing_objects_touched": [],
        "bbox_world": [tuple(round(v, 3) for v in lo), tuple(round(v, 3) for v in hi)],
        "stage_top_z": STAGE_TOP + FLOOR_Z,
    }


if __name__ == "__main__" and (bpy is None or "--textures" in sys.argv):
    make_textures()
