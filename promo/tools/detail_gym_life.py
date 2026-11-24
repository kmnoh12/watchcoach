"""Detail package `gym_life`: everyday gym life on the main floor.

Run inside Blender (scene_gym.blend open, cwd = repo):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_gym_life; detail_gym_life.apply()
Regenerate the printed graphics (PIL, outside Blender):
    ~/.venvs/pdf/bin/python promo/tools/detail_gym_life.py --textures

Reference photos (work/refs):
  gym/137 141 239, interior/101 102 174   adjustable benches (black frame, ladder, wheels + handle)
  gym/247 253 255                        stretching kit: standing rolled mats, foam rollers, burgundy gym ball
  interior/185                           white wall fans on brackets, round white wall clock
  interior/148 145 146                   black wire towel shelf with grey + red folded towels, framed notice
  interior/128 108 110                   stickers / instruction decals on weight-stack towers and frames
  interior/101 102 151 153 166           lived-in floors (bottles, plates leaning on racks, towels on benches)
  gym/247 (+ walnut slat walls)          wood slat partition on black steel channels
Everything new lives in collection DETAIL_gym_life. Existing objects touched (tagged detail_pkg="gym_life"):
  * Gym_InfoDesk "Louver *" (11 objects): hidden (replaced by the new slat partition).
  * GymBall_Large, GymBall_Medium, Plyo box (stretching zone): moved from the dumbbell area into the
    stretching zone's front strip so the adjustable benches have room.
"""
import math
import os
import random
import sys

try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix, Euler
except ImportError:  # texture generation outside Blender
    bpy = None

KEY = "gym_life"
COLL = "DETAIL_gym_life"
PFX = "Dgym_life_"
HERE = os.path.dirname(os.path.abspath(__file__))
PART_DIR = os.path.normpath(os.path.join(HERE, "..", "parts", "detail_" + KEY))
FONT = os.path.normpath(os.path.join(HERE, "..", "parts", "fonts", "NanumGothic-Bold.ttf"))

# Scene frame (world metres, probed on scene_gym.blend)
FRONT_Y = -6.68        # front wall face (posing/locker doors)
LEFT_X = -7.47         # left wall face
RIGHT_X = 13.465       # right wall wainscot face
BACK_Y = 4.95          # back wall / mirror face

TEX = ["wood_slat", "station_sign", "spray_label", "clock_face", "caution", "placard_row", "placard_tbar",
       "towel_notice", "bottle_label", "phone_screen", "bin_label"]


# =============================================================================================
# Textures (PIL)
# =============================================================================================
def make_textures():
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    os.makedirs(PART_DIR, exist_ok=True)
    F = lambda s: ImageFont.truetype(FONT, s)
    RED, INK, YEL = (214, 34, 40), (22, 22, 24), (250, 200, 20)

    def ctext(d, cx, y, t, f, fill):
        w = d.textlength(t, font=f)
        d.text((cx - w / 2, y), t, font=f, fill=fill)

    rnd = random.Random(7)
    # 1 walnut slat grain (vertical grain along v)
    W, H = 256, 1024
    im = Image.new("RGB", (W, H))
    px = im.load()
    phase = [rnd.uniform(0, 6.28) for _ in range(6)]
    for x in range(W):
        for y in range(H):
            g = math.sin(x * 0.09 + 2.2 * math.sin(y * 0.004 + phase[0]) + 0.6 * math.sin(y * 0.021 + phase[1]))
            g2 = math.sin(x * 0.31 + math.sin(y * 0.01 + phase[2]) * 3)
            v = 0.5 + 0.28 * g + 0.10 * g2
            r = int(92 + 46 * v); gg = int(58 + 30 * v); b = int(34 + 18 * v)
            px[x, y] = (r, gg, b)
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    im.save(os.path.join(PART_DIR, "wood_slat.png"))

    # 2 sanitiser station sign (A5 landscape)
    im = Image.new("RGB", (600, 420), (250, 250, 248)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 600, 110], fill=RED)
    ctext(d, 300, 22, "기구 소독 스테이션", F(56), (255, 255, 255))
    ctext(d, 300, 140, "운동 후 사용하신 기구는", F(40), INK)
    ctext(d, 300, 195, "소독제로 닦아주세요", F(40), INK)
    d.rounded_rectangle([60, 272, 540, 380], 18, outline=RED, width=5)
    ctext(d, 300, 288, "① 스프레이  →  ② 페이퍼타올로 닦기", F(28), INK)
    ctext(d, 300, 335, "PLEASE WIPE DOWN AFTER USE", F(24), (110, 110, 116))
    im.save(os.path.join(PART_DIR, "station_sign.png"))

    # 3 spray bottle label
    im = Image.new("RGB", (512, 256), (245, 250, 246)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 512, 60], fill=(20, 140, 90))
    ctext(d, 256, 12, "소독용 에탄올", F(36), (255, 255, 255))
    ctext(d, 256, 80, "ETHANOL 75%", F(54), (20, 110, 70))
    ctext(d, 256, 160, "기구·손잡이 소독용  500mL", F(28), INK)
    ctext(d, 256, 206, "화기 주의", F(26), RED)
    im.save(os.path.join(PART_DIR, "spray_label.png"))

    # 4 clock face
    S = 512
    im = Image.new("RGB", (S, S), (246, 246, 244)); d = ImageDraw.Draw(im)
    c = S / 2
    for i in range(60):
        a = math.radians(i * 6)
        r0 = 232 if i % 5 else 214
        d.line([(c + math.sin(a) * r0, c - math.cos(a) * r0), (c + math.sin(a) * 244, c - math.cos(a) * 244)],
               fill=INK, width=3 if i % 5 else 8)
    for h in range(1, 13):
        a = math.radians(h * 30)
        ctext(d, c + math.sin(a) * 178, c - math.cos(a) * 178 - 30, str(h), F(56), INK)
    ctext(d, c, c + 70, "QUARTZ", F(20), (120, 120, 124))
    im.save(os.path.join(PART_DIR, "clock_face.png"))

    # 5 caution sticker for weight stacks
    im = Image.new("RGB", (400, 240), YEL); d = ImageDraw.Draw(im)
    for i in range(-240, 400, 36):
        d.polygon([(i, 0), (i + 18, 0), (i + 18 + 30, 30), (i + 30, 30)], fill=INK)
        d.polygon([(i, 210), (i + 18, 210), (i + 18 + 30, 240), (i + 30, 240)], fill=INK)
    d.polygon([(40, 175), (95, 60), (150, 175)], fill=INK)
    d.polygon([(58, 165), (95, 88), (132, 165)], fill=YEL)
    d.rectangle([90, 108, 100, 142], fill=INK); d.rectangle([90, 150, 100, 158], fill=INK)
    d.text((170, 52), "주 의", font=F(44), fill=INK)
    d.text((170, 108), "손가락 끼임 주의", font=F(28), fill=INK)
    d.text((170, 146), "핀은 끝까지 꽂아주세요", font=F(22), fill=INK)
    im.save(os.path.join(PART_DIR, "caution.png"))

    # 6/7 plate-loaded placards
    def placard(fn, ko, en, steps):
        im = Image.new("RGB", (300, 460), (28, 29, 32)); d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 300, 70], fill=RED)
        ctext(d, 150, 8, ko, F(34), (255, 255, 255))
        ctext(d, 150, 46, en, F(16), (255, 220, 220))
        # pictogram: seated figure pulling handles
        d.ellipse([118, 96, 150, 128], fill=(235, 235, 235))
        d.line([(134, 128), (126, 200)], fill=(235, 235, 235), width=12)
        d.line([(126, 200), (184, 204), (196, 256)], fill=(235, 235, 235), width=11)
        d.line([(132, 148), (190, 160)], fill=(235, 235, 235), width=9)
        d.line([(196, 150), (196, 172)], fill=RED, width=6)
        d.rectangle([60, 270, 240, 276], fill=(90, 90, 96))
        for i, s in enumerate(steps):
            d.ellipse([22, 292 + i * 52, 50, 320 + i * 52], fill=RED)
            ctext(d, 36, 294 + i * 52, str(i + 1), F(20), (255, 255, 255))
            d.text((62, 294 + i * 52), s, font=F(21), fill=(228, 228, 228))
        im.save(os.path.join(PART_DIR, fn + ".png"))
    placard("placard_row", "플레이트 로우", "ISO-LATERAL ROW", ["가슴패드에 밀착", "등 근육으로 당기기", "천천히 제자리로"])
    placard("placard_tbar", "T바 로우", "T-BAR ROW", ["발판에 발 고정", "가슴 패드에 기대기", "팔꿈치를 뒤로"])

    # 8 towel notice (A4 landscape)
    im = Image.new("RGB", (594, 420), (252, 252, 250)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 594, 96], fill=INK)
    ctext(d, 297, 22, "운동복 · 수건 안내", F(46), (255, 255, 255))
    ctext(d, 297, 130, "수건은 1인 1장 사용해 주세요", F(34), INK)
    ctext(d, 297, 190, "사용한 수건은 수거함에", F(34), RED)
    ctext(d, 297, 250, "넣어주세요", F(34), RED)
    ctext(d, 297, 330, "TOWEL  1 PER PERSON", F(24), (110, 110, 116))
    im.save(os.path.join(PART_DIR, "towel_notice.png"))

    # 9 water bottle label (wraps around)
    im = Image.new("RGB", (512, 128), (255, 255, 255)); d = ImageDraw.Draw(im)
    for y in range(128):
        t = y / 127
        d.line([(0, y), (512, y)], fill=(int(40 + 160 * t), int(120 + 110 * t), int(210 + 40 * t)))
    d.polygon([(0, 128), (90, 60), (150, 95), (230, 40), (330, 110), (420, 70), (512, 110), (512, 128)], fill=(240, 248, 255))
    d.text((24, 16), "PURE WATER", font=F(30), fill=(255, 255, 255))
    d.text((300, 16), "500mL", font=F(30), fill=(255, 255, 255))
    im.save(os.path.join(PART_DIR, "bottle_label.png"))

    # 10 phone lock screen
    im = Image.new("RGB", (256, 540)); d = ImageDraw.Draw(im)
    for y in range(540):
        t = y / 539
        d.line([(0, y), (256, y)], fill=(int(30 + 40 * t), int(26 + 20 * t), int(60 + 70 * t)))
    ctext(d, 128, 70, "11월 25일 화요일", F(16), (230, 230, 240))
    ctext(d, 128, 92, "19:42", F(64), (245, 245, 250))
    d.rounded_rectangle([20, 230, 236, 290], 14, fill=(70, 66, 96))
    d.text((32, 240), "WatchCoach", font=F(14), fill=(255, 255, 255))
    d.text((32, 262), "세트 3/4 완료 · 휴식 60초", font=F(14), fill=(220, 220, 230))
    im.save(os.path.join(PART_DIR, "phone_screen.png"))

    # 11 towel bin label
    im = Image.new("RGB", (300, 120), (245, 245, 242)); d = ImageDraw.Draw(im)
    ctext(d, 150, 18, "사용한 수건", F(36), INK)
    ctext(d, 150, 66, "USED TOWELS", F(24), RED)
    im.save(os.path.join(PART_DIR, "bin_label.png"))
    print("textures ->", PART_DIR)


# =============================================================================================
# Blender helpers
# =============================================================================================
def _mat(name, color, rough=0.5, metal=0.0, image=None, emit=0.0, alpha=None, coat=0.0):
    nm = PFX + name
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    m.diffuse_color = (*color[:3], 1 if alpha is None else alpha)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color[:3], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = (*color[:3], 1)
        b.inputs["Emission Strength"].default_value = emit
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            pass
    if image:
        p = os.path.join(PART_DIR, image + ".png")
        img = bpy.data.images.load(p, check_existing=True)
        if not img.packed_file:
            img.pack()
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
        if emit:
            nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        nt.nodes.active = tex
    return m


class MB:
    """Merged mesh builder: primitives placed with matrices, per-primitive material slots."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.verify()
        self.mats = []

    def _mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def _tag(self, verts, m, smooth):
        mi = self._mi(m)
        fs = {f for v in verts for f in v.link_faces}
        for f in fs:
            f.material_index = mi
            f.smooth = smooth
        return fs

    @staticmethod
    def _M(c, rot):
        R = Euler([math.radians(a) for a in rot]).to_matrix().to_4x4() if rot else Matrix()
        return Matrix.Translation(Vector(c)) @ R

    def box(self, size, c, m, rot=None, bevel=0.0, seg=1, smooth=False):
        res = bmesh.ops.create_cube(self.bm, size=1.0)
        vs = res["verts"]
        bmesh.ops.scale(self.bm, vec=Vector(size), verts=vs)
        if bevel > 0:
            es = list({e for v in vs for e in v.link_edges})
            r = bmesh.ops.bevel(self.bm, geom=es + vs, offset=min(bevel, min(size) * 0.45), segments=seg,
                                profile=0.5, affect="EDGES", clamp_overlap=True)
            vs = list(set(vs) | set(r["verts"]))
            vs = list({v for f in r["faces"] for v in f.verts} | {v for v in vs if v.is_valid})
        bmesh.ops.transform(self.bm, matrix=self._M(c, rot), verts=vs)
        self._tag(vs, m, smooth)
        return vs

    def cyl(self, r, h, c, m, rot=None, seg=16, r2=None, smooth=True, caps=True, spin=0.0):
        res = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r,
                                    radius2=r if r2 is None else r2, depth=h)
        vs = res["verts"]
        if spin:
            bmesh.ops.rotate(self.bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(spin), 3, "Z"))
        bmesh.ops.transform(self.bm, matrix=self._M(c, rot), verts=vs)
        fs = self._tag(vs, m, smooth)
        if smooth and caps:
            for f in fs:
                if len(f.verts) > 4:
                    f.smooth = False
                    for e in f.edges:
                        e.smooth = False
        return vs

    def tube(self, p0, p1, r, m, seg=8, smooth=True):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        q = d.to_track_quat("Z", "Y")
        M = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=d.length)
        vs = res["verts"]
        bmesh.ops.transform(self.bm, matrix=M, verts=vs)
        self._tag(vs, m, smooth)
        return vs

    def sphere(self, r, c, m, seg=16, rings=8, scale=(1, 1, 1), rot=None):
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings, radius=r)
        vs = res["verts"]
        bmesh.ops.scale(self.bm, vec=Vector(scale), verts=vs)
        bmesh.ops.transform(self.bm, matrix=self._M(c, rot), verts=vs)
        self._tag(vs, m, True)
        return vs

    def torus(self, R, r, c, m, seg=32, mseg=6, rot=None):
        verts = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            for j in range(mseg):
                b = 2 * math.pi * j / mseg
                rr = R + r * math.cos(b)
                verts.append(self.bm.verts.new((rr * math.cos(a), rr * math.sin(a), r * math.sin(b))))
        for i in range(seg):
            for j in range(mseg):
                a = verts[i * mseg + j]; b = verts[((i + 1) % seg) * mseg + j]
                cc = verts[((i + 1) % seg) * mseg + (j + 1) % mseg]; d = verts[i * mseg + (j + 1) % mseg]
                self.bm.faces.new((a, b, cc, d))
        bmesh.ops.transform(self.bm, matrix=self._M(c, rot), verts=verts)
        self._tag(verts, m, True)
        return verts

    def decal(self, w, h, c, m, rot=None, u0=0.0, u1=1.0, v0=0.0, v1=1.0):
        """Rectangle in local XZ plane, normal -Y (faces the viewer looking along +Y)."""
        pts = [(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)]
        uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        M = self._M(c, rot)
        vs = [self.bm.verts.new(M @ Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        for lp, uv in zip(f.loops, uvs):
            lp[self.uv].uv = uv
        f.normal_update()
        self._tag(vs, m, False)
        return vs

    def disc(self, r, c, m, rot=None, seg=32):
        """Disc in local XZ plane facing -Y, with planar UVs."""
        M = self._M(c, rot)
        vs = [self.bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * i / seg), 0, r * math.sin(2 * math.pi * i / seg))))
              for i in range(seg)]
        f = self.bm.faces.new(vs)
        for i, lp in enumerate(f.loops):
            a = 2 * math.pi * i / seg
            lp[self.uv].uv = (0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a))
        self._tag(vs, m, False)
        return vs

    def wrap(self, r, h, c, m, seg=24, rot=None):
        """Open cylinder (label sleeve) with wrap-around UVs."""
        M = self._M(c, rot)
        ring0, ring1 = [], []
        for i in range(seg + 1):
            a = 2 * math.pi * i / seg
            ring0.append(self.bm.verts.new(M @ Vector((r * math.cos(a), r * math.sin(a), -h / 2))))
            ring1.append(self.bm.verts.new(M @ Vector((r * math.cos(a), r * math.sin(a), h / 2))))
        allv = ring0 + ring1
        for i in range(seg):
            f = self.bm.faces.new((ring0[i], ring0[i + 1], ring1[i + 1], ring1[i]))
            for lp, uv in zip(f.loops, [(i / seg, 0), ((i + 1) / seg, 0), ((i + 1) / seg, 1), (i / seg, 1)]):
                lp[self.uv].uv = uv
        bmesh.ops.remove_doubles(self.bm, verts=allv, dist=1e-6)
        allv = [v for v in allv if v.is_valid]
        self._tag(allv, m, True)
        return allv

    def mesh(self, name):
        bmesh.ops.recalc_face_normals(self.bm, faces=[f for f in self.bm.faces if len(f.verts) > 2 and not self._is_decal(f)])
        me = bpy.data.meshes.new(PFX + name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        return me

    @staticmethod
    def _is_decal(f):
        return any(len(e.link_faces) == 1 for e in f.edges)


def _ob(name, me, coll, loc=(0, 0, 0), rot=(0, 0, 0), scale=None, parent=None):
    ob = bpy.data.objects.new(PFX + name, me)
    coll.objects.link(ob)
    if parent:
        ob.parent = parent
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    if scale:
        ob.scale = scale
    return ob


def _wall_contact(p, inward):
    """Slide p onto the wall surface: cast from 0.6 m inside the room back toward the wall."""
    dg = bpy.context.evaluated_depsgraph_get()
    o = p + inward * 0.6
    hit, loc, nrm, idx, ob, mtx = bpy.context.scene.ray_cast(dg, o, -inward, distance=1.0)
    if hit and not ob.name.startswith(PFX):
        return tuple(loc + inward * 0.001)
    return tuple(p)


def _surface_z(x, y, z0=2.5, ignore=()):
    """Ray cast straight down to find the top of whatever is at (x, y)."""
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    o = Vector((x, y, z0))
    for _ in range(12):
        hit, loc, nrm, idx, ob, mtx = sc.ray_cast(dg, o, Vector((0, 0, -1)))
        if not hit:
            return 0.0
        if ob.name.startswith(PFX) or ob.name in ignore:
            o = loc - Vector((0, 0, 0.0005))
            continue
        return loc.z
    return 0.0


# =============================================================================================
# Materials
# =============================================================================================
def _materials():
    M = {}
    M["black_steel"] = _mat("BlackSteel", (0.018, 0.019, 0.021), 0.42, 0.65)
    M["red_frame"] = _mat("RedFrame", (0.68, 0.035, 0.04), 0.33, 0.0, coat=0.3)
    M["pad"] = _mat("VinylPad", (0.022, 0.024, 0.028), 0.45)
    M["chrome"] = _mat("Chrome", (0.80, 0.82, 0.85), 0.12, 1.0)
    M["rubber"] = _mat("Rubber", (0.012, 0.012, 0.014), 0.85)
    M["white_plastic"] = _mat("WhitePlastic", (0.86, 0.87, 0.86), 0.35)
    M["fan_blade"] = _mat("FanBlade", (0.62, 0.72, 0.80), 0.30)
    M["fan_blue"] = _mat("FanHub", (0.10, 0.32, 0.70), 0.35)
    M["wood"] = _mat("WalnutSlat", (0.42, 0.26, 0.15), 0.62, image="wood_slat")
    M["sign"] = _mat("StationSign", (0.9, 0.9, 0.9), 0.4, image="station_sign")
    M["spray_label"] = _mat("SprayLabel", (0.9, 0.95, 0.9), 0.35, image="spray_label")
    M["spray_body"] = _mat("SprayBody", (0.90, 0.92, 0.92), 0.28)
    M["spray_head"] = _mat("SprayTrigger", (0.12, 0.42, 0.80), 0.35)
    M["paper"] = _mat("PaperTowel", (0.93, 0.93, 0.90), 0.9)
    M["clock"] = _mat("ClockFace", (0.95, 0.95, 0.95), 0.4, image="clock_face")
    M["caution"] = _mat("CautionSticker", (0.98, 0.78, 0.08), 0.45, image="caution")
    M["placard_row"] = _mat("PlacardRow", (0.2, 0.2, 0.2), 0.5, image="placard_row")
    M["placard_tbar"] = _mat("PlacardTbar", (0.2, 0.2, 0.2), 0.5, image="placard_tbar")
    M["notice"] = _mat("TowelNotice", (0.95, 0.95, 0.95), 0.4, image="towel_notice")
    M["bottle_label"] = _mat("BottleLabel", (0.4, 0.7, 0.95), 0.35, image="bottle_label")
    M["bottle"] = _mat("BottlePET", (0.78, 0.88, 0.95), 0.08, alpha=0.45)
    M["water_cap"] = _mat("BottleCap", (0.10, 0.36, 0.78), 0.4)
    M["screen"] = _mat("PhoneScreen", (0.2, 0.2, 0.35), 0.15, image="phone_screen", emit=0.6)
    M["bin_label"] = _mat("BinLabel", (0.9, 0.9, 0.9), 0.4, image="bin_label")
    M["towel_grey"] = _mat("TowelGrey", (0.36, 0.37, 0.39), 0.95)
    M["towel_ivory"] = _mat("TowelIvory", (0.78, 0.76, 0.70), 0.95)
    M["towel_red"] = _mat("TowelRed", (0.55, 0.05, 0.06), 0.95)
    M["bin_grey"] = _mat("BinGrey", (0.30, 0.31, 0.33), 0.55)
    M["frame_alu"] = _mat("FrameAlu", (0.55, 0.56, 0.58), 0.3, 0.9)
    M["bump_blue"] = _mat("BumperBlue", (0.05, 0.16, 0.48), 0.75)
    M["bump_green"] = _mat("BumperGreen", (0.04, 0.32, 0.12), 0.75)
    M["iron"] = _mat("CastIron", (0.06, 0.065, 0.07), 0.55, 0.7)
    M["shaker_black"] = _mat("ShakerBlack", (0.03, 0.03, 0.035), 0.35)
    M["shaker_clear"] = _mat("ShakerClear", (0.85, 0.85, 0.88), 0.1, alpha=0.4)
    M["shaker_red"] = _mat("ShakerRed", (0.70, 0.06, 0.06), 0.35)
    M["ball_burgundy"] = _mat("GymBallBurgundy", (0.30, 0.04, 0.07), 0.38)
    M["roller_black"] = _mat("RollerGridBlack", (0.025, 0.025, 0.028), 0.8)
    M["roller_orange"] = _mat("RollerOrange", (0.85, 0.32, 0.05), 0.7)
    M["roller_blue"] = _mat("RollerBlue", (0.06, 0.20, 0.55), 0.8)
    M["phone_body"] = _mat("PhoneBody", (0.05, 0.05, 0.06), 0.3, 0.6)
    M["hex_rubber"] = _mat("HexRubber", (0.02, 0.02, 0.022), 0.7)
    for k, col in (("mat_purple", (0.25, 0.12, 0.42)), ("mat_navy", (0.05, 0.10, 0.28)), ("mat_grey", (0.18, 0.19, 0.21)),
                   ("mat_teal", (0.04, 0.32, 0.32)), ("mat_pink", (0.62, 0.20, 0.30)), ("mat_black", (0.03, 0.03, 0.035))):
        M[k] = _mat("YogaMat_" + k[4:], col, 0.8)
    return M


# =============================================================================================
# Builders (each returns list of objects)
# =============================================================================================
def build_partition(C, M):
    """Walnut slats on black steel channels, replacing the bare white louver beside the desk."""
    mb = MB()
    x0, y0, y1, H = -3.61, -6.665, -4.835, 2.877
    Z0 = 0.013   # sits on the info-desk epoxy pad edge
    L = y1 - y0
    mb.box((0.07, L, 0.05), (x0, (y0 + y1) / 2, 0.025), M["black_steel"], bevel=0.003)        # floor channel
    mb.box((0.07, L, 0.05), (x0, (y0 + y1) / 2, H - 0.025), M["black_steel"], bevel=0.003)    # head channel
    for yy in (y0 + 0.02, y1 - 0.02):
        mb.box((0.07, 0.04, H - 0.1), (x0, yy, H / 2), M["black_steel"], bevel=0.003)          # end posts
    n = 22
    pitch = (L - 0.12) / n
    for i in range(n):
        yy = y0 + 0.06 + pitch * (i + 0.5)
        vs = mb.box((0.06, 0.03, H - 0.104), (x0 + 0.0, yy, H / 2), M["wood"], bevel=0.003)
        # wrap UVs along the slat (u across, v along height) with per-slat offset
        fs = {f for v in vs for f in v.link_faces}
        off = (i * 0.137) % 1.0
        for f in fs:
            for lp in f.loops:
                co = lp.vert.co
                lp[mb.uv].uv = (((co.y - yy) / 0.06 + (co.x - x0) / 0.06) * 0.25 + off, co.z / H * 0.9 + off * 0.1)
    return [_ob("SlatPartition", mb.mesh("SlatPartition"), C, (0, 0, Z0))]


def _station_head(M):
    """Wall unit: black backplate, sign, paper roll on arms, wire ring + 500 mL spray bottle. Origin = wall
    contact centre, faces local -Y (mounted onto a surface whose normal is -Y in local)."""
    mb = MB()
    mb.box((0.30, 0.012, 0.52), (0, -0.006, 0), M["black_steel"], bevel=0.003)
    mb.decal(0.21, 0.147, (0, -0.0132, 0.17), M["sign"])
    # paper towel roll holder
    for sx in (-0.13, 0.13):
        mb.box((0.012, 0.13, 0.03), (sx, -0.075, 0.02), M["black_steel"], bevel=0.002)
    mb.tube((-0.13, -0.12, 0.02), (0.13, -0.12, 0.02), 0.008, M["chrome"])
    mb.cyl(0.058, 0.23, (0, -0.12, 0.02), M["paper"], rot=(0, 90, 0), seg=20)
    mb.cyl(0.021, 0.232, (0, -0.12, 0.02), M["shaker_black"], rot=(0, 90, 0), seg=12)  # core (dark hole look)
    # torn sheet hanging
    mb.box((0.20, 0.002, 0.09), (0, -0.177, -0.03), M["paper"], rot=(6, 0, 0))
    # wire ring for the spray bottle
    mb.box((0.02, 0.07, 0.012), (0.0, -0.035, -0.19), M["black_steel"])
    mb.torus(0.045, 0.004, (0.0, -0.085, -0.19), M["black_steel"], seg=20, mseg=4)
    # spray bottle (body, label, neck, trigger head)
    bx, by = 0.0, -0.085
    mb.cyl(0.038, 0.19, (bx, by, -0.16), M["spray_body"], seg=20)
    mb.wrap(0.0392, 0.09, (bx, by, -0.17), M["spray_label"], seg=20, rot=(0, 0, -90))
    mb.cyl(0.016, 0.03, (bx, by, -0.05), M["spray_body"], seg=12)
    mb.box((0.035, 0.075, 0.045), (bx, by - 0.02, -0.015), M["spray_head"], bevel=0.008, seg=2, smooth=True)
    mb.box((0.012, 0.03, 0.05), (bx, by - 0.035, -0.055), M["spray_head"], rot=(-20, 0, 0), bevel=0.004)
    mb.cyl(0.007, 0.02, (bx, by - 0.066, -0.01), M["shaker_black"], rot=(90, 0, 0), seg=8)
    return mb.mesh("StationHead")


def build_stations(C, M):
    head = _station_head(M)
    obs = []
    # wall units on the two hazard-wrapped pillars (faces at x -1.631 / +10.631)
    obs.append(_ob("Station_PillarL", head, C, (-1.632, -0.40, 1.18), (0, 0, -90)))
    obs.append(_ob("Station_PillarR", head, C, (10.632, -0.40, 1.18), (0, 0, 90)))
    # floor stand version (base + post + same head)
    mb = MB()
    mb.box((0.30, 0.30, 0.012), (0, 0, 0.006), M["black_steel"], bevel=0.003)
    for sx in (-0.12, 0.12):
        for sy in (-0.12, 0.12):
            mb.cyl(0.015, 0.006, (sx, sy, 0.003), M["rubber"], seg=10)
    mb.box((0.04, 0.04, 1.20), (0, 0.06, 0.612), M["black_steel"], bevel=0.003)
    stand = mb.mesh("StationStand")
    for nm, (x, y, rz) in (("Station_StandFront", (6.55, -3.02, 180)), ("Station_StandBack", (7.55, 0.20, 0))):
        st = _ob(nm, stand, C, (x, y, 0), (0, 0, rz))
        h = _ob(nm + "_head", head, C, (0, 0.04, 1.02), (0, 0, 0), parent=st)
        obs += [st, h]
    return obs


def _fan_mesh(M):
    """45 cm wall fan (ref interior/185): wall plate, swivel arm, motor, 5 blades, wire guard. Origin = wall
    contact, fan axis = local -Y."""
    mb = MB()
    W = M["white_plastic"]
    mb.box((0.11, 0.02, 0.15), (0, -0.01, 0), W, bevel=0.006, seg=2)
    mb.box((0.04, 0.16, 0.04), (0, -0.10, 0), W, bevel=0.008, seg=2, smooth=True)
    mb.sphere(0.03, (0, -0.18, 0), W, seg=12, rings=6)
    # motor housing tilted down 18 deg about X at the knuckle
    tilt = -18
    R = Euler((math.radians(tilt), 0, 0)).to_matrix()
    k = Vector((0, -0.18, 0))
    P = lambda v: tuple(k + R @ Vector(v))
    mb.cyl(0.075, 0.17, P((0, -0.06, 0.03)), W, rot=(90 + tilt, 0, 0), seg=20)
    mb.sphere(0.075, P((0, 0.025, 0.03)), W, seg=20, rings=8, scale=(1, 0.5, 1), rot=(tilt, 0, 0))
    hub = Vector(P((0, -0.20, 0.03)))
    mb.cyl(0.04, 0.05, tuple(hub), M["fan_blue"], rot=(90 + tilt, 0, 0), seg=16)
    for i in range(5):
        a = i * 72
        Rb = Euler((math.radians(tilt), 0, 0)).to_matrix().to_4x4() @ Euler((0, math.radians(a), 0)).to_matrix().to_4x4()
        vs = mb.sphere(0.095, (0, 0, 0), M["fan_blade"], seg=12, rings=6, scale=(0.62, 0.06, 1.0))
        bmesh.ops.transform(mb.bm, matrix=Matrix.Translation(hub) @ Rb @ Matrix.Translation((0, 0, 0.12))
                            @ Euler((0, math.radians(12), math.radians(14))).to_matrix().to_4x4(), verts=vs)
    # wire guard: concentric rings front + back, radial spokes, rim
    for yy, rings in ((-0.24, (0.06, 0.12, 0.175, 0.225)), (-0.15, (0.09, 0.16, 0.225))):
        for rr in rings:
            mb.torus(rr, 0.0025, P((0, yy, 0.03)), W, seg=36, mseg=4, rot=(90 + tilt, 0, 0))
    mb.torus(0.227, 0.007, P((0, -0.195, 0.03)), W, seg=40, mseg=6, rot=(90 + tilt, 0, 0))
    for i in range(16):
        a = 2 * math.pi * i / 16
        for yy in (-0.24, -0.15):
            p0 = P((0.05 * math.cos(a), yy, 0.03 + 0.05 * math.sin(a)))
            p1 = P((0.225 * math.cos(a), yy, 0.03 + 0.225 * math.sin(a)))
            mb.tube(p0, p1, 0.0022, W, seg=4, smooth=False)
        mb.tube(P((0.226 * math.cos(a), -0.24, 0.03 + 0.226 * math.sin(a))),
                P((0.226 * math.cos(a), -0.15, 0.03 + 0.226 * math.sin(a))), 0.0022, W, seg=4, smooth=False)
    mb.disc(0.045, P((0, -0.2425, 0.03)), M["fan_blue"], rot=(tilt, 0, 0), seg=20)
    # pull cord
    mb.tube(P((0.05, -0.02, -0.04)), P((0.05, -0.02, -0.40)), 0.0015, W, seg=4)
    mb.sphere(0.008, P((0.05, -0.02, -0.41)), W, seg=8, rings=4)
    return mb.mesh("WallFan")


def build_fans(C, M):
    fan = _fan_mesh(M)
    spots = [("Fan_Front_A", (1.0, FRONT_Y, 2.55), 180), ("Fan_Front_B", (8.65, FRONT_Y, 2.62), 180),
             ("Fan_Left", (LEFT_X, -1.85, 2.62), 90), ("Fan_Back", (10.85, BACK_Y + 0.02, 2.88), 0)]
    # local -Y must point into the room; rot z: front wall (room is +Y) -> 180, left wall (+X) -> 90, back (-Y) -> 0
    obs = []
    for i, (n, loc, rz) in enumerate(spots):
        inward = Matrix.Rotation(math.radians(rz), 3, "Z") @ Vector((0, -1, 0))
        loc = _wall_contact(Vector(loc), inward)
        obs.append(_ob(n, fan, C, loc, (0, 0, rz)))
    return obs


def build_clock(C, M):
    mb = MB()
    mb.cyl(0.18, 0.045, (0, -0.0225, 0), M["black_steel"], rot=(90, 0, 0), seg=40)
    mb.disc(0.165, (0, -0.0455, 0), M["clock"], seg=40)
    mb.torus(0.172, 0.009, (0, -0.045, 0), M["frame_alu"], seg=40, mseg=6, rot=(90, 0, 0))
    # hands at 19:42 -> hour 7.7 h, minute 42
    def hand(ang_deg, L, w, y, m):
        a = math.radians(ang_deg)
        c = (math.sin(a) * L / 2 - math.sin(a) * 0.02, y, math.cos(a) * L / 2 - math.cos(a) * 0.02)
        mb.box((w, 0.002, L), c, m, rot=(0, ang_deg, 0))
    hand(7.7 * 30, 0.095, 0.010, -0.049, M["rubber"])
    hand(42 * 6, 0.140, 0.007, -0.052, M["rubber"])
    hand(13 * 6, 0.145, 0.002, -0.055, M["red_frame"])
    mb.cyl(0.008, 0.012, (0, -0.052, 0), M["rubber"], rot=(90, 0, 0), seg=12)
    loc = _wall_contact(Vector((5.9, FRONT_Y, 2.58)), Vector((0, 1, 0)))
    return [_ob("WallClock", mb.mesh("WallClock"), C, loc, (0, 0, 180))]


def _towel_stack(M, n, seed, m):
    rnd = random.Random(seed)
    mb = MB()
    z = 0.0
    for i in range(n):
        t = 0.026 + rnd.uniform(-0.003, 0.004)
        mb.box((0.30, 0.22, t), (rnd.uniform(-0.008, 0.008), rnd.uniform(-0.008, 0.008), z + t / 2), m,
               rot=(0, 0, rnd.uniform(-2.5, 2.5)), bevel=0.011, seg=2, smooth=True)
        z += t - 0.001
    return mb.mesh(f"TowelStack_{seed}"), z


def build_towel_shelf(C, M):
    obs = []
    mb = MB()
    x0, x1, y0, y1, H = 13.00, 13.45, -6.40, -5.50, 1.55
    S = M["black_steel"]
    for x in (x0 + 0.012, x1 - 0.012):
        for y in (y0 + 0.012, y1 - 0.012):
            mb.cyl(0.0125, H, (x, y, H / 2), M["chrome"] if False else S, seg=10)
            mb.cyl(0.018, 0.02, (x, y, 0.01), M["rubber"], seg=10)
    shelves = (0.12, 0.52, 0.92, 1.32)
    for z in shelves:
        for x in (x0 + 0.012, x1 - 0.012):
            mb.box((0.012, y1 - y0, 0.02), (x, (y0 + y1) / 2, z), S)
        for y in (y0 + 0.012, y1 - 0.012):
            mb.box((x1 - x0, 0.012, 0.02), ((x0 + x1) / 2, y, z), S)
        for k in range(13):
            y = y0 + 0.03 + k * (y1 - y0 - 0.06) / 12
            mb.box((x1 - x0 - 0.02, 0.004, 0.004), ((x0 + x1) / 2, y, z + 0.008), S)
    obs.append(_ob("TowelShelf", mb.mesh("TowelShelf"), C))
    # towel stacks: grey on the middle shelves, red + ivory on top, a short stack low
    tops = {z: z + 0.012 for z in shelves}
    layout = [(0.92, -6.17, "towel_grey", 9, 1), (0.92, -5.75, "towel_grey", 8, 2), (0.52, -6.17, "towel_grey", 10, 3),
              (0.52, -5.75, "towel_grey", 7, 4), (1.32, -6.17, "towel_red", 6, 5), (1.32, -5.75, "towel_ivory", 5, 6),
              (0.12, -6.1, "towel_grey", 3, 7)]
    for z, y, mk, n, seed in layout:
        me, _ = _towel_stack(M, n, seed, M[mk])
        obs.append(_ob(f"Towels_{seed}", me, C, (13.22, y, tops[z]), (0, 0, 90 + random.Random(seed).uniform(-3, 3))))
    # framed notice on the right wall above the shelf
    mb = MB()
    mb.box((0.33, 0.012, 0.24), (0, 0.006, 0), M["frame_alu"], bevel=0.003)
    mb.decal(0.297, 0.21, (0, -0.0005, 0), M["notice"])
    obs.append(_ob("TowelNotice", mb.mesh("TowelNotice"), C, (RIGHT_X - 0.013, -5.95, 1.85), (0, 0, -90)))
    # used-towel bin (round grey hamper on casters) with two crumpled towels and label
    mb = MB()
    mb.cyl(0.20, 0.50, (0, 0, 0.30), M["bin_grey"], seg=28, r2=0.215)
    mb.cyl(0.185, 0.012, (0, 0, 0.553), M["towel_grey"], seg=24, caps=True)
    mb.torus(0.215, 0.012, (0, 0, 0.55), M["bin_grey"], seg=28, mseg=6)
    for a in (45, 135, 225, 315):
        mb.sphere(0.025, (0.15 * math.cos(math.radians(a)), 0.15 * math.sin(math.radians(a)), 0.03), M["rubber"], seg=8, rings=4)
    mb.sphere(0.12, (0.04, 0.03, 0.575), M["towel_grey"], seg=14, rings=7, scale=(1.2, 0.9, 0.45))
    mb.sphere(0.09, (-0.07, -0.05, 0.585), M["towel_ivory"], seg=12, rings=6, scale=(1.1, 1.0, 0.5))
    mb.decal(0.16, 0.064, (0, -0.2135, 0.40), M["bin_label"], rot=(-1.6, 0, 0))
    obs.append(_ob("TowelBin", mb.mesh("TowelBin"), C, (13.22, -5.18, 0), (0, 0, 70)))
    return obs


def build_stack_stickers(C, M):
    """Yellow caution sticker on the outer face of every weight-stack rear guard (pin-loaded machines)."""
    mb = MB()
    n = 0
    for g in bpy.data.objects:
        if not g.name.startswith("Rear stack guard") or g.type != "MESH" or g.hide_render:
            continue
        root = g
        while root.parent:
            root = root.parent
        if not root.name.startswith("P_"):
            continue
        pts = [g.matrix_world @ Vector(c) for c in g.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        ext = hi - lo
        thin = 0 if ext.x < ext.y else 1
        # selector plates of the same tower: closest selector plate object to the guard centre
        cen = (lo + hi) / 2
        sel = [o for o in root.children_recursive if o.name.startswith("Selector plate")]
        if not sel:
            continue
        sc = min((o.matrix_world.translation for o in sel), key=lambda p: (p - cen).length)
        scen = min(([(o.matrix_world @ Vector(c)) for c in o.bound_box] for o in sel),
                   key=lambda ps: (sum(ps, Vector()) / 8 - cen).length)
        sc = sum(scen, Vector()) / 8
        sign = 1 if cen[thin] > sc[thin] else -1
        face = hi[thin] if sign > 0 else lo[thin]
        c = cen.copy()
        c[thin] = face + sign * 0.0015
        c.z = hi.z - 0.22
        # decal faces -Y locally; rotate so its normal points along +sign on the thin axis
        if thin == 1:
            rz = 0 if sign < 0 else 180
        else:
            rz = -90 if sign < 0 else 90
        shrouds = []
        for o in root.children_recursive:
            if o.type == "MESH" and o is not g and not o.name.startswith(("Mark", "Selector plate")):
                q = [o.matrix_world @ Vector(cc) for cc in o.bound_box]
                shrouds.append((Vector((min(p.x for p in q), min(p.y for p in q), min(p.z for p in q))),
                                Vector((max(p.x for p in q), max(p.y for p in q), max(p.z for p in q)))))
        lat = 1 - thin
        for w in (0.15, 0.11, 0.08):
            slo, shi = c.copy(), c.copy()
            slo[thin] -= 0.001; shi[thin] += 0.001
            slo[lat] -= w / 2; shi[lat] += w / 2
            slo.z -= w * 0.3; shi.z += w * 0.3
            hit = any(all(slo[i] < b1[i] and shi[i] > b0[i] for i in range(3)) for b0, b1 in shrouds)
            if not hit:
                mb.decal(w, w * 0.6, tuple(c), M["caution"], rot=(0, 0, rz))
                n += 1
                break
    obs = [_ob("StackCautionStickers", mb.mesh("StackCautionStickers"), C)] if n else []
    # plate-loaded machines: printed instruction placards on flat frame faces
    mb = MB()
    # plate row centre post faces x = 0.68 / 0.82 (post.002), T-bar chest mount face x = -1.052
    mb.decal(0.13, 0.20, (0.6785, -2.375, 0.42), M["placard_row"], rot=(0, 0, -90))
    mb.decal(0.13, 0.20, (0.8215, -2.375, 0.42), M["placard_row"], rot=(0, 0, 90))
    obs.append(_ob("PlateLoadedPlacards", mb.mesh("PlateLoadedPlacards"), C))
    return obs, n


def _adj_bench(M, incline_deg):
    """Adjustable FID bench (refs gym/137 141 239): seat end at +Y, back pad hinged behind it."""
    mb = MB()
    F, P, S = M["red_frame"], M["pad"], M["chrome"]
    # feet
    mb.box((0.56, 0.07, 0.05), (0, 0.0, 0.025), F, bevel=0.006)          # rear foot (handle end)
    mb.box((0.50, 0.07, 0.05), (0, 1.10, 0.025), F, bevel=0.006)         # front foot (wheel end)
    for sx in (-0.27, 0.27):
        mb.cyl(0.02, 0.012, (sx, 0.0, 0.006), M["rubber"], seg=10)
    for sx in (-0.26, 0.26):
        mb.cyl(0.042, 0.03, (sx, 1.12, 0.042), M["rubber"], rot=(0, 90, 0), seg=16)
        mb.cyl(0.012, 0.034, (sx, 1.12, 0.042), S, rot=(0, 90, 0), seg=8)
    # rear handle
    mb.tube((-0.09, -0.02, 0.06), (-0.09, -0.12, 0.14), 0.012, S)
    mb.tube((0.09, -0.02, 0.06), (0.09, -0.12, 0.14), 0.012, S)
    mb.tube((-0.10, -0.12, 0.14), (0.10, -0.12, 0.14), 0.016, M["rubber"], seg=12)
    # legs + spine
    mb.box((0.08, 0.08, 0.30), (0, 0.02, 0.20), F, bevel=0.006)
    mb.box((0.08, 0.08, 0.36), (0, 1.08, 0.23), F, bevel=0.006)
    mb.box((0.08, 1.12, 0.08), (0, 0.55, 0.36), F, bevel=0.006)
    # seat
    mb.box((0.30, 0.38, 0.075), (0, 0.92, 0.47), P, rot=(-4, 0, 0), bevel=0.02, seg=3, smooth=True)
    mb.box((0.26, 0.30, 0.03), (0, 0.92, 0.42), F)
    # back pad hinge at y 0.70, z 0.47
    a = math.radians(incline_deg)
    L = 0.80
    hy, hz = 0.70, 0.475
    cy, cz = hy - math.cos(a) * L / 2, hz + math.sin(a) * L / 2
    mb.box((0.29, L, 0.075), (0, cy, cz), P, rot=(incline_deg, 0, 0), bevel=0.02, seg=3, smooth=True)
    mb.box((0.06, L * 0.9, 0.04), (0, cy + math.sin(a) * 0.055, cz - math.cos(a) * 0.055), F, rot=(incline_deg, 0, 0))
    # ladder + support strut from spine to back frame
    mb.box((0.07, 0.42, 0.03), (0, 0.30, 0.415), S)
    for k in range(6):
        mb.cyl(0.006, 0.08, (0, 0.13 + k * 0.065, 0.435), S, rot=(0, 90, 0), seg=6)
    if incline_deg > 3:
        foot = Vector((0, 0.18 + 0.05 * min(incline_deg, 60) / 60, 0.43))
        top = Vector((0, cy + math.sin(a) * 0.075, cz - math.cos(a) * 0.075))
        mb.tube(foot, top, 0.018, F, seg=8)
    mb.cyl(0.02, 0.10, (0, hy, hz - 0.03), S, rot=(0, 90, 0), seg=10)
    return mb


def _hex_db(M, kg):
    mb = MB()
    hw = 0.05 + 0.004 * kg ** 0.5 * 2.2
    hl = 0.035 + 0.0032 * kg
    hl = min(hl, 0.09)
    hw = min(hw, 0.12)
    gl = 0.135
    for s in (-1, 1):
        mb.cyl(hw / 2 / math.cos(math.radians(30)), hl, (s * (gl / 2 + hl / 2), 0, 0), M["hex_rubber"],
               rot=(0, 90, 0), seg=6, smooth=False, spin=30)
        mb.cyl(0.02, 0.012, (s * (gl / 2 + 0.006), 0, 0), M["chrome"], rot=(0, 90, 0), seg=12)
    mb.cyl(0.0165, gl, (0, 0, 0), M["chrome"], rot=(0, 90, 0), seg=12)
    return mb, hw / 2


def build_benches(C, M):
    obs = []
    for nm, x, inc in (("Bench_AdjIncline", -6.45, 40), ("Bench_AdjFlat", -5.45, 0)):
        mb = _adj_bench(M, inc)
        obs.append(_ob(nm, mb.mesh(nm), C, (x, 1.96, 0), (0, 0, 0)))
    # 12 kg pair lying beside the flat bench (pass-1 style rubber hex)
    mb, r = _hex_db(M, 12)
    me = mb.mesh("Dumbbell12")
    zmin = min(v.co.z for v in me.vertices)
    zf = _surface_z(-4.9, 2.2, 1.0)
    obs.append(_ob("Dumbbell12_a", me, C, (-4.98, 2.55, zf - zmin + 0.0005), (0, 0, 90)))
    obs.append(_ob("Dumbbell12_b", me, C, (-4.84, 2.62, zf - zmin + 0.0005), (0, 0, 84)))
    return obs


def _draped_towel(M, mat, pad_w, pad_top, length=0.78, width=0.34, seed=1):
    """Towel thrown across a pad of width pad_w (local X), flat on top, falling down both sides."""
    rnd = random.Random(seed)
    nx, ny = 26, 8
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u = (i / nx - 0.5) * length + 0.03
            v = (j / ny - 0.5) * width
            half = pad_w / 2 + 0.012
            if abs(u) <= half:
                x, z = u, pad_top + 0.004
            else:
                d = abs(u) - half
                r = 0.03
                if d < math.pi / 2 * r:
                    t = d / r
                    x = math.copysign(half + r * math.sin(t), u)
                    z = pad_top + 0.004 - r * (1 - math.cos(t))
                else:
                    dd = d - math.pi / 2 * r
                    x = math.copysign(half + r + 0.06 * dd, u)
                    z = pad_top + 0.004 - r - dd
            z += 0.004 * math.sin(v * 40 + rnd.uniform(0, 3)) * (1 if abs(u) > half else 0.3)
            row.append(bm.verts.new((x, v + 0.01 * math.sin(u * 9), z)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(PFX + f"DrapedTowel_{seed}")
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    return me


def build_clutter(C, M):
    obs = []
    # --- bumper plates leaning on the power rack's right side (between the uprights)
    def bumper(mat, D=0.45, t=0.06):
        mb = MB()
        mb.cyl(D / 2, t, (0, 0, 0), mat, rot=(0, 90, 0), seg=32)
        mb.cyl(0.095, t + 0.004, (0, 0, 0), M["chrome"], rot=(0, 90, 0), seg=20)
        mb.cyl(0.026, t + 0.006, (0, 0, 0), M["rubber"], rot=(0, 90, 0), seg=12)
        return mb
    th = 12.0
    t = 0.06
    D = 0.45
    xc = 3.562 + (t / 2) * math.cos(math.radians(th)) + (D / 2) * math.sin(math.radians(th))
    zc = (D / 2) * math.cos(math.radians(th)) + (t / 2) * math.sin(math.radians(th))
    z0 = _surface_z(3.70, 3.22, 1.0)
    zc += z0
    me20 = bumper(M["bump_blue"]).mesh("Bumper20")
    obs.append(_ob("Bumper20_lean_a", me20, C, (xc, 3.22, zc), (0, -th, 0)))
    obs.append(_ob("Bumper20_lean_b", me20, C, (xc + t + 0.004, 3.22, zc + 0.004), (0, -th, 0)))
    me10 = bumper(M["bump_green"], D=0.45, t=0.035).mesh("Bumper10")
    xc10 = 3.562 + 0.0175 * math.cos(math.radians(th)) + 0.225 * math.sin(math.radians(th))
    obs.append(_ob("Bumper10_lean", me10, C, (xc10, 3.62, zc), (0, -th, 0)))
    # --- 10 kg iron plate left flat on the floor next to the leg press
    mb = MB()
    mb.cyl(0.17, 0.03, (0, 0, 0.015), M["iron"], seg=32)
    mb.torus(0.15, 0.008, (0, 0, 0.03), M["iron"], seg=32, mseg=4)
    mb.cyl(0.026, 0.032, (0, 0, 0.015), M["rubber"], seg=12)
    obs.append(_ob("IronPlate10_floor", mb.mesh("IronPlate10"), C, (6.52, -1.90, 0.0), (0, 0, 20)))

    # --- water bottles (500 mL PET)
    mb = MB()
    mb.cyl(0.032, 0.17, (0, 0, 0.087), M["bottle"], seg=16)
    mb.wrap(0.0328, 0.065, (0, 0, 0.10), M["bottle_label"], seg=16)
    mb.cyl(0.032, 0.03, (0, 0, 0.187), M["bottle"], seg=16, r2=0.014)
    mb.cyl(0.0145, 0.022, (0, 0, 0.212), M["water_cap"], seg=12)
    bottle = mb.mesh("WaterBottle")
    for nm, (x, y), rz in (("Bottle_benches", (-5.95, 2.95), 30), ("Bottle_latpull", (-2.86, 0.62), 110),
                           ("Bottle_stationF", (6.40, -2.80), 200)):
        obs.append(_ob(nm, bottle, C, (x, y, _surface_z(x, y, 1.0)), (0, 0, rz)))
    # one bottle lying on its side under the incline bench
    obs.append(_ob("Bottle_lying", bottle, C, (-6.18, 2.30, _surface_z(-6.08, 2.26, 0.3) + 0.032), (90, 0, 65)))

    # --- shakers (black lid / smoke body)
    mb = MB()
    mb.cyl(0.048, 0.15, (0, 0, 0.075), M["shaker_clear"], seg=20, r2=0.052)
    mb.cyl(0.040, 0.05, (0, 0, 0.03), M["shaker_red"], seg=20)   # pre-mixed drink left in it
    mb.cyl(0.054, 0.035, (0, 0, 0.168), M["shaker_black"], seg=20)
    mb.cyl(0.018, 0.02, (0.02, 0, 0.195), M["shaker_black"], seg=10)
    mb.torus(0.022, 0.005, (-0.03, 0, 0.2), M["shaker_black"], seg=12, mseg=4, rot=(90, 0, 0))
    shaker = mb.mesh("Shaker")
    for nm, (x, y) in (("Shaker_chestpress", (4.86, 1.62)), ("Shaker_benches", (-6.85, 2.78))):
        obs.append(_ob(nm, shaker, C, (x, y, _surface_z(x, y, 1.0)), (0, 0, 40)))

    # --- towels thrown over benches (existing flat bench + new flat adjustable bench)
    me = _draped_towel(M, M["towel_grey"], 0.30, _surface_z(0.15, 3.05, 1.0), seed=3)
    tw = _ob("Towel_on_flatbench", me, C, (0.15, 3.05, 0), (0, 0, 4))
    sol = tw.modifiers.new("Thickness", "SOLIDIFY"); sol.thickness = 0.006; sol.offset = 1.0
    obs.append(tw)
    me = _draped_towel(M, M["towel_ivory"], 0.30, 0.514, length=0.70, seed=5)   # flat adj bench seat top (own mesh)
    tw = _ob("Towel_on_adjbench", me, C, (-5.45, 2.86, 0), (0, 0, -6))
    sol = tw.modifiers.new("Thickness", "SOLIDIFY"); sol.thickness = 0.006; sol.offset = 1.0
    obs.append(tw)

    # --- phone left on the pec deck seat
    mb = MB()
    mb.box((0.077, 0.162, 0.0085), (0, 0, 0.00425), M["phone_body"], bevel=0.006, seg=3, smooth=True)
    vs = mb.decal(0.071, 0.155, (0, 0, 0.0088), M["screen"], rot=(-90, 0, 0))
    for v in vs:
        pass
    mb.box((0.03, 0.03, 0.002), (-0.018, 0.055, -0.0005), M["rubber"])
    x, y = 6.93, 0.98
    obs.append(_ob("Phone_on_pecdeck", mb.mesh("Phone"), C, (x, y, _surface_z(x, y, 1.0) + 0.004), (0, 0, 160)))
    return obs


def build_stretch_kit(C, M):
    obs = []
    # yoga mat rack against the left wall, front strip of the stretching zone (ref gym/253)
    mb = MB()
    S = M["black_steel"]
    x0, x1, y0, y1, H = -7.45, -7.13, -2.27, -1.73, 0.80
    for x in (x0 + 0.012, x1 - 0.012):
        for y in (y0 + 0.012, y1 - 0.012):
            mb.box((0.025, 0.025, H), (x, y, H / 2), S, bevel=0.002)
    for z in (0.04, 0.42, H - 0.015):
        mb.box((x1 - x0, 0.02, 0.02), ((x0 + x1) / 2, y0 + 0.012, z), S)
        mb.box((x1 - x0, 0.02, 0.02), ((x0 + x1) / 2, y1 - 0.012, z), S)
        mb.box((0.02, y1 - y0, 0.02), (x1 - 0.012, (y0 + y1) / 2, z), S)
        mb.box((0.02, y1 - y0, 0.02), (x0 + 0.012, (y0 + y1) / 2, z), S)
    mb.box((x1 - x0 - 0.02, y1 - y0 - 0.02, 0.012), ((x0 + x1) / 2, (y0 + y1) / 2, 0.03), S)
    mb.box((0.02, y1 - y0, 0.02), ((x0 + x1) / 2, (y0 + y1) / 2, H - 0.015), S)
    cols = ["mat_purple", "mat_navy", "mat_grey", "mat_teal", "mat_pink", "mat_black", "mat_navy", "mat_grey"]
    rnd = random.Random(11)
    k = 0
    for ix, xx in enumerate((x0 + 0.085, x1 - 0.085)):
        for iy in range(4):
            if k == 7:
                break
            yy = y0 + 0.075 + iy * 0.13
            h = rnd.choice((0.61, 0.61, 0.68))
            r = rnd.uniform(0.055, 0.063)
            tilt = rnd.uniform(-1.2, 1.2)
            mb.cyl(r, h, (xx, yy, 0.036 + h / 2), M[cols[k]], rot=(tilt, rnd.uniform(-1.2, 1.2), 0), seg=16, caps=False)
            mb.cyl(r * 0.92, 0.004, (xx, yy, 0.036 + h - 0.002), M[cols[k]], seg=16)
            mb.torus(r * 0.55, r * 0.17, (xx, yy, 0.036 + h - 0.002), M[cols[k]], seg=16, mseg=4)
            mb.cyl(r * 0.25, 0.006, (xx, yy, 0.036 + h - 0.001), M["mat_black"], seg=10)
            k += 1
    obs.append(_ob("YogaMatRack", mb.mesh("YogaMatRack"), C, (0, 0, _surface_z(-7.29, -2.0, 1.0) + 0.001)))

    # grid foam roller (black/orange) + long blue roller + ab wheel + burgundy gym ball
    mb = MB()
    mb.cyl(0.072, 0.33, (0, 0, 0), M["roller_black"], rot=(0, 90, 0), seg=20, smooth=False)
    for s in (-0.12, -0.04, 0.04, 0.12):
        mb.cyl(0.0735, 0.03, (s, 0, 0), M["roller_orange"], rot=(0, 90, 0), seg=20, caps=False)
    mb.cyl(0.05, 0.332, (0, 0, 0), M["roller_orange"], rot=(0, 90, 0), seg=16, caps=True)
    obs.append(_ob("FoamRoller_grid", mb.mesh("FoamRollerGrid"), C, (-6.35, 1.62, 0.016 + 0.073), (0, 0, 8)))
    mb = MB()
    mb.cyl(0.075, 0.90, (0, 0, 0), M["roller_blue"], rot=(90, 0, 0), seg=20)
    obs.append(_ob("FoamRoller_long", mb.mesh("FoamRollerLong"), C, (-6.42, 0.95, 0.039 + 0.075), (0, 0, 78)))
    mb = MB()
    mb.cyl(0.09, 0.07, (0, 0, 0), M["rubber"], rot=(0, 90, 0), seg=24)
    mb.cyl(0.07, 0.074, (0, 0, 0), M["shaker_red"], rot=(0, 90, 0), seg=20)
    mb.cyl(0.011, 0.36, (0, 0, 0), M["chrome"], rot=(0, 90, 0), seg=10)
    for s in (-1, 1):
        mb.cyl(0.018, 0.11, (s * 0.12, 0, 0), M["rubber"], rot=(0, 90, 0), seg=12)
    obs.append(_ob("AbWheel", mb.mesh("AbWheel"), C, (-5.55, -0.30, 0.039 + 0.09), (0, 0, 35)))
    mb = MB()
    mb.sphere(0.30, (0, 0, 0.30), M["ball_burgundy"], seg=28, rings=14)
    obs.append(_ob("GymBall_Burgundy", mb.mesh("GymBallBurgundy"), C, (-5.42, 1.58, 0.014), (0, 0, 0)))
    return obs


# =============================================================================================
# Edits to existing objects (tagged, reversible, non-stacking)
# =============================================================================================
def _tag_store(ob):
    if ob.get("detail_pkg") != KEY:
        ob["detail_pkg"] = KEY
        ob["detail_orig_matrix"] = [v for row in ob.matrix_basis for v in row]
        ob["detail_orig_hide_render"] = ob.hide_render
        ob["detail_orig_hide_viewport"] = ob.hide_viewport


def _restore(ob):
    if ob.get("detail_pkg") == KEY:
        vals = list(ob["detail_orig_matrix"])
        ob.matrix_basis = Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])
        ob.hide_render = bool(ob["detail_orig_hide_render"])
        ob.hide_viewport = bool(ob["detail_orig_hide_viewport"])


def _edit_existing():
    touched = []
    # 1) hide the bare white louver (superseded by the slat partition)
    for ob in bpy.data.objects:
        if ob.name.startswith("Louver") and ob.parent and ob.parent.name == "Gym_InfoDesk":
            _restore(ob); _tag_store(ob)
            ob.hide_render = True
            ob.hide_viewport = True
            touched.append((ob.name, "hidden (replaced by Dgym_life_SlatPartition)"))
    # 2) move stretching balls + plyo box out of the dumbbell area into the stretching zone's front strip
    targets = {"GymBall_Large": ((-6.62, -1.99), 0), "GymBall_Medium": ((-5.98, -1.99), 0), "Plyo box": ((-5.33, -1.99), 90)}
    bpy.context.view_layer.update()
    for nm, ((tx, ty), rz) in targets.items():
        ob = bpy.data.objects.get(nm)
        if not ob:
            continue
        _restore(ob); _tag_store(ob)
        bpy.context.view_layer.update()
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        cen = Vector((sum(p.x for p in pts) / 8, sum(p.y for p in pts) / 8, 0))
        R = Matrix.Rotation(math.radians(rz), 4, "Z")
        Mw = Matrix.Translation((tx, ty, 0)) @ R @ Matrix.Translation(-cen) @ ob.matrix_world
        ob.matrix_world = Mw
        touched.append((nm, f"moved to ({tx}, {ty}) rot {rz}"))
    bpy.context.view_layer.update()
    return touched


# =============================================================================================
def apply():
    if not os.path.exists(os.path.join(PART_DIR, "wood_slat.png")):
        raise RuntimeError("run: ~/.venvs/pdf/bin/python promo/tools/detail_gym_life.py --textures")
    parent = bpy.data.collections["SET"]
    C = bpy.data.collections.get(COLL)
    if C is None:
        C = bpy.data.collections.new(COLL)
        parent.children.link(C)
    for ob in list(C.objects):
        me = ob.data if ob.type == "MESH" else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    touched = _edit_existing()
    M = _materials()
    obs = []
    obs += build_partition(C, M)
    obs += build_stations(C, M)
    obs += build_fans(C, M)
    obs += build_clock(C, M)
    obs += build_towel_shelf(C, M)
    st, n_stickers = build_stack_stickers(C, M)
    obs += st
    obs += build_benches(C, M)
    obs += build_clutter(C, M)
    obs += build_stretch_kit(C, M)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in C.objects:
        if ob.type == "MESH":
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            tris += len(me.loop_triangles)
            ev.to_mesh_clear()
    return {"objects_added": len(C.objects), "triangles_added": tris, "stack_stickers": n_stickers,
            "existing_touched": touched}


if __name__ == "__main__" and "--textures" in sys.argv:
    make_textures()
