"""Detail package `hall_props`: the +X dead end of the sangga corridor and everyday facilities.

Builds (all in hallway-local coordinates, parented to `Sangga_Hallway`):
  * a real corridor end: open-plan public restroom entrance (개방화장실 plate, projecting 남/여 sign, tiled
    vestibule with sink, mirror and two dark laminate doors) and a stair hall with a grey steel fire door held
    open against the wall, exit light, 3F floor plate, granite stairs going up and down, nosing strips,
    stainless railings and a yellow tactile warning strip in front of it;
  * lived-in clutter: red mop bucket with a string mop and a flat mop by the restroom, a 4-way recycling bin
    row, a wall-mounted flyer rack with printed flyers, a taped "no bicycles" notice and a cleaning checklist.

Run inside Blender (scene open):   import detail_hall_props; detail_hall_props.apply()
Regenerate the decal images (PIL): ~/.venvs/pdf/bin/python promo/tools/detail_hall_props.py --textures
"""
import math
import os
import random
import sys

try:
    import bpy
    import bmesh
    from mathutils import Matrix, Vector
except ImportError:  # texture generation runs outside Blender
    bpy = None

KEY = "hall_props"
COLL = "DETAIL_hall_props"
PFX = "Dhall_props_"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../promo
PART_DIR = os.path.join(ROOT, "parts", "detail_hall_props")
FONT = os.path.join(ROOT, "parts", "fonts", "NanumGothic-Bold.ttf")

# Existing objects this package replaces (hidden, tagged, restorable)
REPLACED = ("Hallway far end.001", "Hallway far exit dot.001", "Hallway far end", "Hallway far exit dot")

# ----------------------------------------------------------------------------------------------------------
# Layout constants (hallway local frame: x along corridor, y=0 gym-side wall, y≈2.88 storefront wall)
END_X0, END_X1 = 4.62, 4.76          # new end wall thickness
R_Y0, R_Y1 = 0.78, 1.56              # restroom opening
S_Y0, S_Y1 = 1.82, 2.78              # stair opening (incl. 4 cm steel frame)
OPEN_H = 2.10
VEST_X1 = 6.50                       # restroom vestibule back wall face
ST_X1, ST_Y0, ST_Y1 = 9.45, 1.72, 4.10   # stair hall interior
ST_Z0, ST_Z1 = -1.65, 3.78
RISE, TREAD, NSTEP = 0.17, 0.28, 9
FLIGHT_X0 = 5.75
SPLIT_Y0, SPLIT_Y1 = 2.88, 2.98      # curb between up flight (y<2.88) and down flight (y>2.98)


# ==========================================================================================================
# 1) Decal textures (PIL, self-generated; nothing copied from the reference photos)
# ==========================================================================================================
def make_textures():
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    os.makedirs(PART_DIR, exist_ok=True)

    def F(size):
        return ImageFont.truetype(FONT, size)

    def ctext(d, xy, s, size, fill, anchor="mm"):
        d.text(xy, s, font=F(size), fill=fill, anchor=anchor)

    def man(d, cx, top, h, fill):
        u = h / 10.0
        d.ellipse([cx - 1.1 * u, top, cx + 1.1 * u, top + 2.2 * u], fill=fill)
        d.rounded_rectangle([cx - 1.9 * u, top + 2.6 * u, cx + 1.9 * u, top + 6.2 * u], radius=0.8 * u, fill=fill)
        d.rectangle([cx - 1.5 * u, top + 5.5 * u, cx - 0.15 * u, top + 10 * u], fill=fill)
        d.rectangle([cx + 0.15 * u, top + 5.5 * u, cx + 1.5 * u, top + 10 * u], fill=fill)

    def woman(d, cx, top, h, fill):
        u = h / 10.0
        d.ellipse([cx - 1.1 * u, top, cx + 1.1 * u, top + 2.2 * u], fill=fill)
        d.polygon([(cx - 0.9 * u, top + 2.6 * u), (cx + 0.9 * u, top + 2.6 * u),
                   (cx + 2.4 * u, top + 7.0 * u), (cx - 2.4 * u, top + 7.0 * u)], fill=fill)
        d.rectangle([cx - 1.0 * u, top + 6.8 * u, cx - 0.25 * u, top + 10 * u], fill=fill)
        d.rectangle([cx + 0.25 * u, top + 6.8 * u, cx + 1.0 * u, top + 10 * u], fill=fill)

    def save(im, name):
        im.save(os.path.join(PART_DIR, name))

    # --- 개방화장실 plate (navy, silver border, red/blue pictograms) — ref hall/090
    im = Image.new("RGB", (440, 640), (22, 36, 78))
    d = ImageDraw.Draw(im)
    d.rectangle([6, 6, 433, 633], outline=(170, 176, 186), width=6)
    d.ellipse([70, 50, 370, 350], fill=(228, 230, 234), outline=(150, 156, 166), width=8)
    woman(d, 170, 95, 210, (206, 30, 38))
    d.rectangle([217, 95, 223, 305], fill=(40, 40, 46))
    man(d, 270, 95, 210, (22, 70, 170))
    ctext(d, (220, 425), "개방화장실", 66, (255, 255, 255))
    ctext(d, (220, 495), "Public Toilet", 36, (230, 232, 236))
    d.line([60, 545, 380, 545], fill=(120, 130, 160), width=2)
    ctext(d, (220, 585), "하늘프라자 관리사무소", 26, (210, 214, 224))
    save(im, "toilet_plate.png")

    # --- projecting dark pictogram sign, ref hall/087
    im = Image.new("RGB", (640, 440), (38, 40, 46))
    d = ImageDraw.Draw(im)
    woman(d, 225, 70, 230, (240, 240, 240))
    d.rectangle([317, 70, 323, 300], fill=(200, 200, 200))
    man(d, 415, 70, 230, (240, 240, 240))
    ctext(d, (320, 360), "화장실  TOILET", 46, (235, 235, 235))
    save(im, "toilet_projecting.png")

    # --- door pictogram stickers (transparent)
    for name, fn, col in (("pict_man.png", man, (30, 80, 180)), ("pict_woman.png", woman, (205, 32, 40))):
        im = Image.new("RGBA", (256, 320), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        fn(d, 128, 18, 220, col + (255,))
        ctext(d, (128, 290), "남자" if "man.png" == name[-7:] and "wo" not in name else "여자", 44, col + (255,))
        save(im, name)

    # --- green 비상구 exit light (피난구 유도등), ref hall/104 105
    im = Image.new("RGB", (640, 240), (0, 150, 72))
    d = ImageDraw.Draw(im)
    d.rectangle([30, 28, 190, 212], outline=(255, 255, 255), width=12)        # door
    d.rectangle([42, 40, 178, 200], fill=(0, 150, 72))
    w = (255, 255, 255)
    d.ellipse([228, 34, 270, 76], fill=w)                                       # running figure
    d.line([(246, 82), (222, 140)], fill=w, width=22)
    d.line([(244, 92), (205, 110), (190, 130)], fill=w, width=16)
    d.line([(244, 92), (282, 118), (300, 104)], fill=w, width=16)
    d.line([(222, 140), (258, 168), (246, 208)], fill=w, width=18)
    d.line([(222, 140), (192, 172), (160, 178)], fill=w, width=18)
    ctext(d, (470, 105), "비상구", 92, w)
    ctext(d, (470, 190), "EXIT", 48, w)
    save(im, "exit_sign.png")

    # --- 3F floor plate beside the stair door (white acrylic)
    im = Image.new("RGB", (400, 580), (238, 238, 234))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 399, 579], outline=(60, 60, 60), width=6)
    ctext(d, (200, 170), "3F", 230, (20, 22, 26))
    d.rectangle([40, 300, 360, 306], fill=(230, 160, 20))
    ctext(d, (200, 365), "계단실  STAIRS", 38, (30, 30, 30))
    ctext(d, (200, 440), "▲ 4F · 5F · 옥상", 34, (40, 40, 40))
    ctext(d, (200, 505), "▼ 2F · 1F · B1", 34, (40, 40, 40))
    save(im, "floor_plate_3f.png")

    # --- stair wall super-graphics (transparent, like ref hall/106 "B1")
    for name, big, small in (("stair_graphic_4f.png", "4F", "▲ UP"), ("stair_graphic_3f.png", "3F", "계단 3층"),
                             ("stair_graphic_2f.png", "2F", "▼ DOWN")):
        im = Image.new("RGBA", (720, 720), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for k in range(5):
            d.polygon([(20, 230 + k * 40), (190, 130 + k * 40), (190, 152 + k * 40), (20, 252 + k * 40)],
                      fill=(24, 24, 28, 255))
        ctext(d, (465, 330), big, 360, (24, 24, 28, 255))
        ctext(d, (360, 640), small, 70, (24, 24, 28, 255))
        save(im, name)

    # --- 방화문 sticker on the fire door
    im = Image.new("RGB", (360, 220), (250, 250, 250))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 359, 219], outline=(200, 20, 30), width=10)
    d.rectangle([0, 0, 359, 70], fill=(200, 20, 30))
    ctext(d, (180, 36), "방 화 문", 44, (255, 255, 255))
    ctext(d, (180, 115), "항상 닫아 두십시오", 32, (30, 30, 30))
    ctext(d, (180, 170), "소방시설법 제16조", 22, (90, 90, 90))
    save(im, "firedoor_sticker.png")

    # --- notice: no bicycles / no items in the corridor (A4)
    im = Image.new("RGB", (600, 850), (252, 252, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 599, 140], fill=(196, 24, 30))
    ctext(d, (300, 72), "안   내", 70, (255, 255, 255))
    ctext(d, (300, 230), "복도 내 자전거", 58, (20, 20, 20))
    ctext(d, (300, 305), "주차 및 물건 적치", 58, (20, 20, 20))
    ctext(d, (300, 380), "금 지", 76, (196, 24, 30))
    for i, ln in enumerate(("복도는 피난 통로입니다.", "자전거·박스·화분 등을 두지 마시고", "지정된 장소를 이용해 주십시오.",
                            "미이행 시 임의 처리될 수 있습니다.")):
        ctext(d, (300, 480 + i * 48), ln, 28, (50, 50, 50))
    d.line([60, 700, 540, 700], fill=(150, 150, 150), width=2)
    ctext(d, (300, 750), "하늘프라자 관리사무소  ☎ 053-000-0000", 26, (40, 40, 40))
    save(im, "notice_bicycle.png")

    # --- restroom cleaning checklist (A4, in a clear sleeve)
    rnd = random.Random(7)
    im = Image.new("RGB", (600, 850), (250, 250, 246))
    d = ImageDraw.Draw(im)
    ctext(d, (300, 60), "화장실 청소 점검표", 48, (20, 20, 20))
    ctext(d, (300, 112), "2026년 11월   (3층 개방화장실)", 24, (60, 60, 60))
    x0, y0, cw, rh = 30, 150, [90, 90, 90, 90, 100, 100], 34
    heads = ("날짜", "09:00", "12:00", "15:00", "18:00", "확인")
    xs = [x0]
    for wv in cw:
        xs.append(xs[-1] + wv)
    for r in range(19):
        y = y0 + r * rh
        d.line([x0, y, xs[-1], y], fill=(60, 60, 60), width=2)
    for x in xs:
        d.line([x, y0, x, y0 + 18 * rh], fill=(60, 60, 60), width=2)
    for i, h in enumerate(heads):
        ctext(d, ((xs[i] + xs[i + 1]) / 2, y0 + rh / 2), h, 20, (20, 20, 20))
    for r in range(1, 18):
        y = y0 + r * rh + rh / 2
        ctext(d, ((xs[0] + xs[1]) / 2, y), f"11/{r + 3:02d}", 18, (30, 30, 30))
        if r < 15:
            for col in range(1, 5):
                if rnd.random() < 0.9:
                    cx = (xs[col] + xs[col + 1]) / 2 + rnd.uniform(-8, 8)
                    d.line([(cx - 10, y), (cx - 2, y + 8), (cx + 12, y - 10)], fill=(25, 45, 150), width=3)
            sx = xs[5] + 15
            pts = [(sx + k * 9, y + rnd.uniform(-7, 7)) for k in range(8)]
            d.line(pts, fill=(25, 25, 25), width=2)
    save(im, "clean_checklist.png")

    # --- recycling labels
    for name, txt, sub, col in (("recycle_general.png", "일반쓰레기", "GENERAL", (90, 92, 96)),
                                ("recycle_plastic.png", "플라스틱", "PLASTIC", (20, 90, 190)),
                                ("recycle_can.png", "캔 · 병", "CAN · BOTTLE", (20, 140, 70)),
                                ("recycle_paper.png", "종이", "PAPER", (230, 130, 20))):
        im = Image.new("RGB", (360, 300), (248, 248, 246))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 359, 120], fill=col)
        ctext(d, (180, 62), txt, 56, (255, 255, 255))
        ctext(d, (180, 175), sub, 34, col)
        ctext(d, (180, 245), "분리수거에 협조해 주세요", 22, (70, 70, 70))
        save(im, name)

    # --- flyer rack header (ref hall/118 red header)
    im = Image.new("RGB", (720, 180), (180, 22, 28))
    d = ImageDraw.Draw(im)
    d.ellipse([30, 40, 130, 140], outline=(240, 200, 120), width=6)
    ctext(d, (80, 90), "H", 52, (240, 200, 120))
    ctext(d, (410, 70), "하늘프라자", 72, (255, 255, 255))
    ctext(d, (410, 140), "홍보물 비치대 · 광고문의 관리사무소", 26, (250, 230, 230))
    save(im, "rack_header.png")

    # --- six printed flyers (A4-ish 420x600)
    def photo_block(im, box, base, seed):
        r = random.Random(seed)
        x0, y0, x1, y1 = box
        blk = Image.new("RGB", (x1 - x0, y1 - y0), base)
        dd = ImageDraw.Draw(blk)
        for _ in range(26):
            cx, cy = r.randint(0, x1 - x0), r.randint(0, y1 - y0)
            rr = r.randint(10, 40)
            c = tuple(max(0, min(255, base[i] + r.randint(-90, 90))) for i in range(3))
            dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c)
        blk = blk.filter(ImageFilter.GaussianBlur(3))
        im.paste(blk, (x0, y0))

    def flyer_mart():
        im = Image.new("RGB", (420, 600), (255, 250, 236))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 419, 120], fill=(214, 28, 30))
        ctext(d, (210, 45), "행복마트", 54, (255, 255, 255))
        ctext(d, (210, 98), "주말 장날 대잔치!", 30, (255, 236, 90))
        for i in range(6):
            bx, by = 15 + (i % 2) * 205, 135 + (i // 2) * 150
            photo_block(im, (bx, by, bx + 185, by + 100), ((230, 120, 40), (60, 150, 60), (190, 40, 60))[i % 3], i)
            d.ellipse([bx + 120, by + 70, bx + 190, by + 140], fill=(255, 220, 0))
            ctext(d, (bx + 155, by + 105), ("990", "1,980", "3,900", "4,980", "2,480", "990")[i], 20, (200, 0, 0))
            ctext(d, (bx + 60, by + 122), ("사과", "삼겹살", "계란30구", "한우", "두부", "대파")[i], 20, (30, 30, 30))
        d.rectangle([0, 570, 419, 599], fill=(214, 28, 30))
        ctext(d, (210, 585), "배달문의 053-000-1234", 20, (255, 255, 255))
        return im

    def flyer_chicken():
        im = Image.new("RGB", (420, 600), (24, 22, 20))
        d = ImageDraw.Draw(im)
        ctext(d, (210, 60), "바삭치킨", 62, (255, 200, 40))
        ctext(d, (210, 118), "오픈 기념 3,000원 할인", 28, (255, 255, 255))
        photo_block(im, (30, 150, 390, 380), (180, 100, 30), 11)
        for i, (m, p) in enumerate((("후라이드", "18,000"), ("양념치킨", "19,000"), ("반반치킨", "19,000"))):
            ctext(d, (110, 420 + i * 40), m, 26, (240, 240, 240))
            ctext(d, (310, 420 + i * 40), p, 26, (255, 200, 40))
        d.rectangle([0, 540, 419, 599], fill=(200, 30, 30))
        ctext(d, (210, 570), "☎ 010-0000-5555", 30, (255, 255, 255))
        return im

    def flyer_academy():
        im = Image.new("RGB", (420, 600), (245, 248, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 419, 170], fill=(18, 60, 150))
        ctext(d, (210, 55), "겨울방학 특강", 44, (255, 255, 255))
        ctext(d, (210, 120), "중·고등 수학 전문", 32, (255, 230, 80))
        for i, ln in enumerate(("· 내신 대비 1:4 소수정예", "· 수능 기출 완성반", "· 무료 레벨테스트", "· 셔틀 운행")):
            ctext(d, (40, 215 + i * 44), ln, 26, (30, 40, 70), anchor="lm")
        photo_block(im, (40, 400, 380, 520), (120, 150, 200), 21)
        ctext(d, (210, 565), "다온수학학원 4층  053-000-7788", 22, (18, 60, 150))
        return im

    def flyer_pilates():
        im = Image.new("RGB", (420, 600), (246, 226, 224))
        d = ImageDraw.Draw(im)
        photo_block(im, (0, 0, 420, 300), (210, 170, 160), 31)
        ctext(d, (210, 340), "GRAND OPEN", 40, (120, 60, 70))
        ctext(d, (210, 395), "필라테스 3+1개월", 38, (60, 30, 40))
        ctext(d, (210, 445), "체험권 1회 무료", 28, (140, 70, 80))
        d.rectangle([60, 490, 360, 540], fill=(120, 60, 70))
        ctext(d, (210, 515), "선착순 30명", 28, (255, 255, 255))
        ctext(d, (210, 575), "5층 루미필라테스", 20, (80, 40, 50))
        return im

    def flyer_realty():
        im = Image.new("RGB", (420, 600), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 419, 90], fill=(240, 200, 0))
        ctext(d, (210, 45), "상가 임대 · 매매", 44, (20, 20, 20))
        photo_block(im, (20, 110, 400, 300), (150, 160, 170), 41)
        for i, ln in enumerate(("1층 코너 22평  보증 3천/월 180", "2층 학원자리 35평  즉시입주", "3층 사무실 18평  관리비 별도")):
            ctext(d, (210, 340 + i * 46), ln, 22, (30, 30, 30))
        d.rectangle([0, 500, 419, 599], fill=(30, 50, 110))
        ctext(d, (210, 530), "프라자공인중개사", 32, (255, 255, 255))
        ctext(d, (210, 572), "010-0000-2580", 26, (240, 200, 0))
        return im

    def flyer_church():
        im = Image.new("RGB", (420, 600), (24, 110, 70))
        d = ImageDraw.Draw(im)
        ctext(d, (210, 70), "다시 뛰는 4060", 44, (255, 255, 255))
        ctext(d, (210, 125), "신중년을 위한 토크콘서트", 28, (240, 240, 200))
        photo_block(im, (40, 170, 380, 420), (200, 180, 150), 51)
        ctext(d, (210, 470), "12월 6일(토) 오후 2시", 30, (255, 230, 120))
        ctext(d, (210, 520), "참가비 무료 · 다과 제공", 24, (255, 255, 255))
        d.rectangle([0, 560, 419, 599], fill=(240, 200, 30))
        ctext(d, (210, 580), "하늘교회 비전홀", 22, (24, 60, 40))
        return im

    for i, fn in enumerate((flyer_mart, flyer_chicken, flyer_academy, flyer_pilates, flyer_realty, flyer_church)):
        save(fn(), f"flyer_{i}.png")
    print("textures written to", PART_DIR)


# ==========================================================================================================
# 2) Blender helpers
# ==========================================================================================================
_ADDED = []


def _W():
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import wc_lib as W
    return W


def _reg(ob):
    _ADDED.append(ob)
    return ob


def _img(name):
    path = os.path.join(PART_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: run `~/.venvs/pdf/bin/python promo/tools/detail_hall_props.py --textures`")
    im = bpy.data.images.load(path, check_existing=True)
    if not im.packed_file:
        im.pack()
    return im


def _pbr(name, color, rough=0.5, metal=0.0, coat=0.0):
    nm = PFX + name
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*color, 1)
    return m


def _img_mat(name, img_name, rough=0.45, emit=0.0, alpha=False):
    """Printed decal / acrylic face: image-driven Principled BSDF (optional self-glow for light boxes)."""
    nm = PFX + name
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _img(img_name)
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    if emit:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    if alpha:
        nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    return m


def _tile_mat(name, plane, tile_w, tile_h, base, grout, rough, gloss_var=0.04):
    """Procedural ceramic tile grid (stack bond) in world space. plane: 'XY' floor, 'XZ' / 'YZ' walls."""
    nm = PFX + name
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    comb = N.new("ShaderNodeCombineXYZ")
    a, c = {"XY": (0, 1), "XZ": (0, 2), "YZ": (1, 2)}[plane]
    L.new(sep.outputs[a], comb.inputs[0])
    L.new(sep.outputs[c], comb.inputs[1])
    brick = N.new("ShaderNodeTexBrick")
    brick.offset = 0.0
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Brick Width"].default_value = tile_w
    brick.inputs["Row Height"].default_value = tile_h
    brick.inputs["Mortar Size"].default_value = 0.0025
    brick.inputs["Mortar Smooth"].default_value = 0.2
    brick.inputs["Color1"].default_value = (*base, 1)
    brick.inputs["Color2"].default_value = tuple(min(1, v * 0.93) for v in base) + (1,)
    brick.inputs["Mortar"].default_value = (*grout, 1)
    brick.inputs["Bias"].default_value = 0.0
    L.new(comb.outputs[0], brick.inputs["Vector"])
    L.new(brick.outputs["Color"], b.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["From Min"].default_value = 0.0
    rr.inputs["From Max"].default_value = 1.0
    rr.inputs["To Min"].default_value = rough
    rr.inputs["To Max"].default_value = 0.85
    L.new(brick.outputs["Fac"], rr.inputs["Value"])
    L.new(rr.outputs["Result"], b.inputs["Roughness"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.002
    L.new(brick.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = (*base, 1)
    return m


def _granite_mat():
    """Grey speckled granite for stair treads (ref hall/106, 104 terrazzo-granite landings)."""
    nm = PFX + "StairGranite"
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    tc = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 160.0
    noise.inputs["Detail"].default_value = 2.0
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.38, (0.12, 0.12, 0.13, 1)
    el[1].position, el[1].color = 0.52, (0.46, 0.46, 0.45, 1)
    e2 = el.new(0.66)
    e2.color = (0.62, 0.61, 0.59, 1)
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.32
    m.diffuse_color = (0.45, 0.45, 0.44, 1)
    return m


def _two_tone_wall_mat():
    """Stair-hall paint: white upper wall, grey lower wainscot (ref hall/103, 106)."""
    nm = PFX + "StairWallPaint"
    m = bpy.data.materials.get(nm)
    if m:
        return m
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    lt_hi = N.new("ShaderNodeMath"); lt_hi.operation = "LESS_THAN"; lt_hi.inputs[1].default_value = 1.05
    gt_lo = N.new("ShaderNodeMath"); gt_lo.operation = "GREATER_THAN"; gt_lo.inputs[1].default_value = -0.05
    pit = N.new("ShaderNodeMath"); pit.operation = "LESS_THAN"; pit.inputs[1].default_value = -0.50
    both = N.new("ShaderNodeMath"); both.operation = "MULTIPLY"
    anyg = N.new("ShaderNodeMath"); anyg.operation = "MAXIMUM"
    for nd in (lt_hi, gt_lo, pit):
        L.new(sep.outputs[2], nd.inputs[0])
    L.new(lt_hi.outputs[0], both.inputs[0]); L.new(gt_lo.outputs[0], both.inputs[1])
    L.new(both.outputs[0], anyg.inputs[0]); L.new(pit.outputs[0], anyg.inputs[1])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.80, 0.80, 0.78, 1)
    mix.inputs["B"].default_value = (0.36, 0.37, 0.38, 1)
    L.new(anyg.outputs[0], mix.inputs["Factor"])
    L.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    m.diffuse_color = (0.75, 0.75, 0.73, 1)
    return m


def _smooth(ob, angle=35.0):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(angle))
    except Exception:
        pass
    return ob


def _bevel(ob, width=0.004, seg=2):
    md = ob.modifiers.new("Bevel", "BEVEL")
    md.width = width
    md.segments = seg
    md.limit_method = "ANGLE"
    return ob


def _plane(c, parent, name, w, h, mat, loc, rot_deg=(0, 0, 0)):
    """UV plane in local XZ facing -Y (rot z: 0 → faces -Y, 180 → +Y, -90 → -X, +90 → +X)."""
    hw, hh = w / 2, h / 2
    me = bpy.data.meshes.new(PFX + name)
    me.from_pydata([(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for lp, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp.uv = co
    me.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, me)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    ob.parent = parent
    c.objects.link(ob)
    return _reg(ob)


def _box(c, parent, name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    W = _W()
    ob = W.box(PFX + name, (x1 - x0, y1 - y0, z1 - z0), mat, c, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), parent=parent)
    if bevel:
        _bevel(ob, bevel)
    return _reg(ob)


def _cyl(c, parent, name, r, h, mat, loc, rot=(0, 0, 0), seg=16, r2=None, smooth=True):
    W = _W()
    ob = W.cyl(PFX + name, r, h, mat, c, loc, rot, seg=seg, r2=r2, parent=parent)
    if smooth:
        _smooth(ob)
    return _reg(ob)


def _tube(c, parent, name, p0, p1, r, mat, seg=12):
    """Cylinder between two local points."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    W = _W()
    ob = W.cyl(PFX + name, r, d.length, mat, c, (p0 + p1) / 2, (0, 0, 0), seg=seg, parent=parent)
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    _smooth(ob)
    return _reg(ob)


def _prism_xz(c, parent, name, pts, y0, y1, mat):
    """Extrude a closed XZ profile (counter-clockwise seen from -Y) between y0 and y1."""
    bm = bmesh.new()
    front = [bm.verts.new((x, y0, z)) for x, z in pts]
    back = [bm.verts.new((x, y1, z)) for x, z in pts]
    n = len(pts)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, me)
    ob.parent = parent
    c.objects.link(ob)
    return _reg(ob)


def _instance(c, src, name, loc, rot_deg=(0, 0, 0)):
    ob = bpy.data.objects.new(PFX + name, src.data)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    ob.parent = src.parent
    for md in src.modifiers:
        nm = ob.modifiers.new(md.name, md.type)
        if md.type == "BEVEL":
            nm.width, nm.segments, nm.limit_method = md.width, md.segments, md.limit_method
    c.objects.link(ob)
    return _reg(ob)


def _area_light(c, parent, name, loc, size, energy, color=(1.0, 0.98, 0.95)):
    ld = bpy.data.lights.get(PFX + name) or bpy.data.lights.new(PFX + name, "AREA")
    ld.shape = "SQUARE"
    ld.size = size
    ld.energy = energy
    ld.color = color
    ob = bpy.data.objects.new(PFX + name, ld)
    ob.location = loc
    ob.parent = parent
    c.objects.link(ob)
    return _reg(ob)


# ==========================================================================================================
# 3) Builders
# ==========================================================================================================
def _mats():
    W = _W()
    M = {}
    M["wall"] = bpy.data.materials.get("Hallway_WallBeige") or _pbr("WallBeige", (0.58, 0.57, 0.54), 0.72)
    M["granite_black"] = bpy.data.materials.get("Hallway_BlackGranite") or _pbr("BlackGranite", (0.025, 0.026, 0.03), 0.14, 0.12)
    M["steel_frame"] = _pbr("SteelFrameGrey", (0.30, 0.31, 0.32), 0.42, 0.55)
    M["firedoor"] = _pbr("FireDoorGrey", (0.40, 0.41, 0.42), 0.38, 0.35)
    M["stainless"] = _pbr("Stainless", (0.74, 0.75, 0.76), 0.22, 1.0)
    M["chrome"] = _pbr("Chrome", (0.86, 0.87, 0.88), 0.06, 1.0)
    M["black_plastic"] = _pbr("BlackPlastic", (0.02, 0.02, 0.022), 0.5)
    M["rubber"] = _pbr("Rubber", (0.015, 0.015, 0.015), 0.85)
    M["nosing"] = _pbr("NosingOchre", (0.55, 0.38, 0.06), 0.7)
    M["tactile"] = _pbr("TactileYellow", (0.85, 0.62, 0.02), 0.55)
    M["paint"] = _two_tone_wall_mat()
    M["stair"] = _granite_mat()
    M["ceil"] = _pbr("CeilingWhite", (0.82, 0.82, 0.80), 0.85)
    M["wall_tile_yz"] = _tile_mat("WallTileYZ", "YZ", 0.6, 0.3, (0.86, 0.86, 0.84), (0.62, 0.62, 0.60), 0.12)
    M["wall_tile_xz"] = _tile_mat("WallTileXZ", "XZ", 0.6, 0.3, (0.86, 0.86, 0.84), (0.62, 0.62, 0.60), 0.12)
    M["floor_tile"] = _tile_mat("FloorTileDark", "XY", 0.3, 0.3, (0.16, 0.13, 0.11), (0.30, 0.29, 0.27), 0.30)
    M["door_lam"] = _pbr("DoorLaminateBrown", (0.06, 0.035, 0.025), 0.35)
    M["mirror"] = _pbr("Mirror", (0.62, 0.66, 0.68), 0.06, 0.6)
    M["porcelain"] = _pbr("Porcelain", (0.88, 0.88, 0.86), 0.12, 0.0, coat=0.6)
    M["led"] = W.shadeless(PFX + "CeilingLED", (0.98, 0.98, 1.0), strength=6.0)
    M["bucket_red"] = _pbr("BucketRed", (0.62, 0.03, 0.03), 0.38)
    M["water"] = _pbr("DirtyWater", (0.12, 0.12, 0.10), 0.05)
    M["mop_cotton"] = _pbr("MopCotton", (0.62, 0.60, 0.55), 0.95)
    M["alu"] = _pbr("MopHandleAlu", (0.70, 0.71, 0.73), 0.3, 1.0)
    M["handle_blue"] = _pbr("HandleGripBlue", (0.03, 0.12, 0.45), 0.45)
    M["pad_blue"] = _pbr("MicrofiberBlue", (0.08, 0.22, 0.60), 0.95)
    M["grey_plastic"] = _pbr("BinGreyPlastic", (0.55, 0.56, 0.56), 0.45)
    M["rack_metal"] = _pbr("RackSilverGrey", (0.50, 0.51, 0.53), 0.35, 0.8)
    M["paper"] = _pbr("PaperStack", (0.85, 0.85, 0.82), 0.8)
    M["tape"] = _pbr("ClearTape", (0.80, 0.78, 0.66), 0.25)
    M["sleeve"] = _pbr("ClearSleeve", (0.90, 0.90, 0.90), 0.08)
    for k, col in (("lid_general", (0.10, 0.10, 0.11)), ("lid_plastic", (0.02, 0.14, 0.45)),
                   ("lid_can", (0.02, 0.30, 0.10)), ("lid_paper", (0.60, 0.25, 0.02))):
        M[k] = _pbr("BinLid_" + k.split("_")[1], col, 0.4)
    return M


def build_end_wall(c, hall, M):
    """New corridor end: end wall with restroom + stair openings, frames, signs (refs 089 090 087 104 105)."""
    # wall piers + lintels (x 4.62..4.76)
    _box(c, hall, "EndWall_PierA", END_X0, END_X1, 0.152, R_Y0, 0.0, 2.80, M["wall"])
    _box(c, hall, "EndWall_PierB", END_X0, END_X1, R_Y1, S_Y0, 0.0, 2.80, M["wall"])
    _box(c, hall, "EndWall_PierC", END_X0, END_X1, S_Y1, 2.958, 0.0, 2.80, M["wall"])
    _box(c, hall, "EndWall_CornerFill", 4.522, END_X0, 2.881, 2.958, 0.0, 2.80, M["wall"])
    _box(c, hall, "EndWall_LintelR", END_X0, END_X1, R_Y0, R_Y1, OPEN_H, 2.80, M["wall"])
    _box(c, hall, "EndWall_LintelS", END_X0, END_X1, S_Y0, S_Y1, OPEN_H, 2.80, M["wall"])
    # closes the stair hall above the corridor ceiling and beside it (behind the storefront wall)
    _box(c, hall, "EndWall_Upper", END_X0, END_X1, 0.152, 2.958, 2.80, ST_Z1 + 0.08, M["paint"])
    _box(c, hall, "EndWall_StairSide", END_X0, END_X1, 2.958, ST_Y1 + 0.06, ST_Z0, ST_Z1 + 0.08, M["paint"])
    # black granite skirting like the storefront plinth
    for nm, y0, y1 in (("A", 0.152, R_Y0), ("B", R_Y1, S_Y0), ("C", S_Y1, 2.878)):
        _box(c, hall, f"EndWall_Plinth{nm}", END_X0 - 0.018, END_X0, y0, y1, 0.0, 0.10, M["granite_black"])
    # thresholds (granite) through both openings
    _box(c, hall, "Threshold_R", END_X0 - 0.01, END_X1 + 0.02, R_Y0, R_Y1, -0.012, 0.004, M["granite_black"], 0.002)
    _box(c, hall, "Threshold_S", END_X0 - 0.01, END_X1 + 0.02, S_Y0, S_Y1, -0.012, 0.004, M["granite_black"], 0.002)

    # restroom opening: stainless edge trims
    for nm, y0, y1 in (("L", R_Y0, R_Y0 + 0.025), ("R", R_Y1 - 0.025, R_Y1)):
        _box(c, hall, f"RestTrim_{nm}", END_X0 - 0.006, END_X1 + 0.004, y0, y1, 0.004, OPEN_H, M["stainless"], 0.002)
    _box(c, hall, "RestTrim_Head", END_X0 - 0.006, END_X1 + 0.004, R_Y0, R_Y1, OPEN_H - 0.025, OPEN_H, M["stainless"], 0.002)

    # stair opening: pressed-steel fire door frame (ref 102 104)
    fz = OPEN_H
    _box(c, hall, "FireFrame_JambR", END_X0 - 0.02, END_X1 + 0.01, S_Y0, S_Y0 + 0.045, 0.004, fz, M["steel_frame"], 0.003)
    _box(c, hall, "FireFrame_JambL", END_X0 - 0.02, END_X1 + 0.01, S_Y1 - 0.045, S_Y1, 0.004, fz, M["steel_frame"], 0.003)
    _box(c, hall, "FireFrame_Head", END_X0 - 0.02, END_X1 + 0.01, S_Y0, S_Y1, fz - 0.045, fz, M["steel_frame"], 0.003)

    # grey steel fire door held open flat against the storefront-side wall (hinge at the y=2.735 jamb)
    door = _W().empty(PFX + "FireDoor", c, (END_X0 - 0.02, S_Y1 - 0.045, 0.0), parent=hall)
    _reg(door)
    dw, dh, dt = 0.90, 2.04, 0.045
    _box(c, door, "FireDoor_Leaf", -dw, -0.004, -0.01 - dt, -0.01, 0.012, 0.012 + dh, M["firedoor"], 0.004)
    face_y = -0.01 - dt - 0.0012   # corridor-facing side (-Y)
    # lever handle + rose (ref 106 lever), pull side faces corridor
    _cyl(c, door, "FireDoor_Rose", 0.028, 0.012, M["stainless"], (-dw + 0.07, face_y - 0.006, 1.0), (90, 0, 0), seg=20)
    _tube(c, door, "FireDoor_LeverNeck", (-dw + 0.07, face_y - 0.004, 1.0), (-dw + 0.07, face_y - 0.055, 1.0), 0.009, M["stainless"])
    _tube(c, door, "FireDoor_Lever", (-dw + 0.07, face_y - 0.055, 1.0), (-dw + 0.20, face_y - 0.055, 0.995), 0.009, M["stainless"])
    # overhead door closer body + arm (ref 102 104)
    _box(c, door, "FireDoor_CloserBody", -0.34, -0.06, face_y - 0.055, face_y, 1.93, 1.99, M["rack_metal"], 0.008)
    _tube(c, door, "FireDoor_CloserArm", (-0.10, face_y - 0.04, 2.0), (0.02, face_y - 0.14, 2.06), 0.007, M["rack_metal"])
    # 방화문 sticker and horseshoe door stopper (말발굽)
    _plane(c, door, "FireDoor_Sticker", 0.18, 0.11, _img_mat("FireDoorSticker", "firedoor_sticker.png"),
           (-dw / 2, face_y, 1.48), (0, 0, 0))
    _box(c, door, "FireDoor_StopperBody", -dw + 0.05, -dw + 0.11, face_y - 0.035, face_y, 0.04, 0.10, M["stainless"], 0.004)
    _box(c, door, "FireDoor_StopperFoot", -dw + 0.06, -dw + 0.10, face_y - 0.045, face_y - 0.015, 0.0, 0.04, M["rubber"], 0.004)
    # hinges (3)
    for z in (0.25, 1.05, 1.85):
        _cyl(c, door, f"FireDoor_Hinge_{z:.2f}", 0.008, 0.10, M["stainless"], (-0.002, -0.01 - dt / 2, z), seg=12)

    # green 비상구 light box above the stair door (ref 104 105)
    _box(c, hall, "ExitSign_Body", END_X0 - 0.07, END_X0, 2.06, 2.54, 2.24, 2.42, _pbr("ExitBodyWhite", (0.85, 0.86, 0.86), 0.4), 0.004)
    _plane(c, hall, "ExitSign_Face", 0.44, 0.15, _img_mat("ExitFace", "exit_sign.png", emit=2.2), (END_X0 - 0.0715, 2.30, 2.33), (0, 0, -90))

    # floor plate 3F (pier B) and 개방화장실 plate + cleaning checklist (pier A)
    _box(c, hall, "FloorPlate_Back", END_X0 - 0.008, END_X0, 1.58, 1.80, 1.31, 1.69, M["stainless"], 0.002)
    _plane(c, hall, "FloorPlate_Face", 0.20, 0.36, _img_mat("FloorPlate3F", "floor_plate_3f.png", 0.3), (END_X0 - 0.0092, 1.69, 1.50), (0, 0, -90))
    _box(c, hall, "ToiletPlate_Back", END_X0 - 0.008, END_X0, 0.225, 0.455, 1.385, 1.715, M["rack_metal"], 0.002)
    _plane(c, hall, "ToiletPlate_Face", 0.22, 0.32, _img_mat("ToiletPlate", "toilet_plate.png", 0.25), (END_X0 - 0.0092, 0.34, 1.55), (0, 0, -90))
    _box(c, hall, "Checklist_Sleeve", END_X0 - 0.004, END_X0, 0.51, 0.73, 1.30, 1.61, M["sleeve"])
    _plane(c, hall, "Checklist_Sheet", 0.21, 0.297, _img_mat("Checklist", "clean_checklist.png", 0.6), (END_X0 - 0.0046, 0.62, 1.455), (0, 0, -90))

    # projecting double-sided pictogram sign on the gym-side wall, facing down the corridor (ref 087)
    sx = 4.30
    _box(c, hall, "ToiletProj_Bracket", sx - 0.04, sx + 0.04, 0.152, 0.20, 2.30, 2.60, M["black_plastic"], 0.003)
    _box(c, hall, "ToiletProj_Box", sx - 0.017, sx + 0.017, 0.20, 0.62, 2.30, 2.60, _pbr("SignCharcoal", (0.035, 0.037, 0.042), 0.4), 0.004)
    pm = _img_mat("ToiletProj", "toilet_projecting.png", 0.35, emit=0.35)
    _plane(c, hall, "ToiletProj_FaceW", 0.40, 0.275, pm, (sx - 0.0182, 0.41, 2.45), (0, 0, -90))
    _plane(c, hall, "ToiletProj_FaceE", 0.40, 0.275, pm, (sx + 0.0182, 0.41, 2.45), (0, 0, 90))


def build_restroom(c, hall, M):
    """Shallow restroom vestibule behind the restroom opening (refs 089 091 094)."""
    vx0, vy0, vy1 = END_X1, 0.27, 1.60
    _box(c, hall, "Rest_Floor", vx0 - 0.02, VEST_X1, vy0, vy1, -0.02, 0.0, M["floor_tile"])
    _box(c, hall, "Rest_Ceiling", vx0, VEST_X1, 0.152, vy1 + 0.06, 2.45, 2.50, M["ceil"])
    _box(c, hall, "Rest_WallBack", VEST_X1, VEST_X1 + 0.06, 0.152, vy1 + 0.06, -0.02, 2.50, M["wall_tile_yz"])
    _box(c, hall, "Rest_WallRight", vx0, VEST_X1, 0.152, vy0, -0.02, 2.50, M["wall_tile_xz"])
    _box(c, hall, "Rest_WallLeft", vx0, VEST_X1, vy1, vy1 + 0.055, -0.02, 2.50, M["wall_tile_xz"])
    _cyl(c, hall, "Rest_Downlight", 0.075, 0.01, M["led"], (5.62, 0.94, 2.444), seg=24, smooth=False)
    _area_light(c, hall, "Rest_Light", (5.62, 0.94, 2.40), 0.6, 28.0)
    # mirror + pedestal sink on the back wall (ref 094)
    _box(c, hall, "Rest_MirrorFrame", VEST_X1 - 0.012, VEST_X1, 1.07, 1.53, 1.08, 1.82, M["stainless"], 0.003)
    _plane(c, hall, "Rest_Mirror", 0.42, 0.70, M["mirror"], (VEST_X1 - 0.0135, 1.30, 1.45), (0, 0, -90))
    _box(c, hall, "Rest_SinkBasin", VEST_X1 - 0.42, VEST_X1 - 0.002, 1.08, 1.52, 0.70, 0.84, M["porcelain"], 0.03)
    _box(c, hall, "Rest_SinkBowl", VEST_X1 - 0.36, VEST_X1 - 0.08, 1.14, 1.46, 0.835, 0.842, _pbr("BasinShadow", (0.55, 0.56, 0.56), 0.1))
    _cyl(c, hall, "Rest_SinkPedestal", 0.085, 0.70, M["porcelain"], (VEST_X1 - 0.12, 1.30, 0.35), seg=20, r2=0.07)
    _cyl(c, hall, "Rest_FaucetBody", 0.02, 0.12, M["chrome"], (VEST_X1 - 0.05, 1.30, 0.90), seg=14)
    _tube(c, hall, "Rest_FaucetSpout", (VEST_X1 - 0.05, 1.30, 0.95), (VEST_X1 - 0.16, 1.30, 0.93), 0.009, M["chrome"])
    # dark laminate doors (ref 094 cubicle doors) with pictogram stickers
    _box(c, hall, "Rest_DoorMen", VEST_X1 - 0.035, VEST_X1 - 0.004, 0.32, 1.00, 0.0, 2.05, M["door_lam"], 0.003)
    _cyl(c, hall, "Rest_DoorMenKnob", 0.025, 0.05, M["stainless"], (VEST_X1 - 0.06, 0.94, 1.0), (0, 90, 0), seg=16)
    _plane(c, hall, "Rest_PictMen", 0.13, 0.16, _img_mat("PictMen", "pict_man.png", 0.4, alpha=True),
           (VEST_X1 - 0.0365, 0.66, 1.55), (0, 0, -90))
    _box(c, hall, "Rest_DoorWomen", 5.05, 5.80, vy0, vy0 + 0.032, 0.0, 2.05, M["door_lam"], 0.003)
    _cyl(c, hall, "Rest_DoorWomenKnob", 0.025, 0.05, M["stainless"], (5.12, vy0 + 0.058, 1.0), (90, 0, 0), seg=16)
    _plane(c, hall, "Rest_PictWomen", 0.13, 0.16, _img_mat("PictWomen", "pict_woman.png", 0.4, alpha=True),
           (5.43, vy0 + 0.0335, 1.55), (0, 0, 180))


def build_stair_hall(c, hall, M):
    """Stair hall: entry landing, up flight straight ahead, down flight to the left (refs 104 105 106 102)."""
    x0 = END_X1
    # shell
    _box(c, hall, "Stair_WallRight", x0, ST_X1, ST_Y0 - 0.06, ST_Y0, ST_Z0, ST_Z1, M["paint"])
    _box(c, hall, "Stair_WallLeft", x0, ST_X1, ST_Y1, ST_Y1 + 0.06, ST_Z0, ST_Z1, M["paint"])
    _box(c, hall, "Stair_WallBack", ST_X1, ST_X1 + 0.06, ST_Y0 - 0.06, ST_Y1 + 0.06, ST_Z0, ST_Z1, M["paint"])
    _box(c, hall, "Stair_Ceiling", x0, ST_X1 + 0.06, ST_Y0 - 0.06, ST_Y1 + 0.06, ST_Z1, ST_Z1 + 0.08, M["ceil"])
    _box(c, hall, "Stair_EntryLanding", x0 - 0.02, FLIGHT_X0, ST_Y0, ST_Y1, -0.25, 0.0, M["stair"])
    _box(c, hall, "Stair_PitFloor", x0, ST_X1, ST_Y0, ST_Y1, ST_Z0 - 0.02, ST_Z0, M["stair"])

    # up flight (y ST_Y0..SPLIT_Y0) straight ahead; down flight (y SPLIT_Y1..ST_Y1) to the left; curb between
    up, dn, curb = [(FLIGHT_X0, ST_Z0)], [(FLIGHT_X0, ST_Z0)], [(FLIGHT_X0, ST_Z0)]
    for i in range(NSTEP):
        x = FLIGHT_X0 + i * TREAD
        up += [(x, i * RISE), (x, (i + 1) * RISE)]
        dn += [(x, -i * RISE), (x, -(i + 1) * RISE)]
        curb += [(x, (i + 1) * RISE + 0.12)]
        curb += [(x + TREAD if i < NSTEP - 1 else ST_X1, (i + 1) * RISE + 0.12)]
    up += [(ST_X1, NSTEP * RISE), (ST_X1, ST_Z0)]
    dn += [(ST_X1, -NSTEP * RISE), (ST_X1, ST_Z0)]
    curb += [(ST_X1, ST_Z0)]
    _prism_xz(c, hall, "Stair_UpFlight", up, ST_Y0, SPLIT_Y0, M["stair"])
    _prism_xz(c, hall, "Stair_DownFlight", dn, SPLIT_Y1, ST_Y1, M["stair"])
    _prism_xz(c, hall, "Stair_Curb", curb, SPLIT_Y0, SPLIT_Y1, M["paint"])

    # anti-slip nosing strips: one mesh, linked instances (ref 106 / 104)
    strip = _box(c, hall, "Stair_Nosing_up1", FLIGHT_X0 + 0.012, FLIGHT_X0 + 0.062, ST_Y0 + 0.04, SPLIT_Y0 - 0.04,
                 RISE + 0.0005, RISE + 0.0035, M["nosing"])
    for i in range(1, NSTEP - 1):
        _instance(c, strip, f"Stair_Nosing_up{i + 1}", (strip.location.x + i * TREAD, strip.location.y, strip.location.z + i * RISE))
    dstrip = _box(c, hall, "Stair_Nosing_dn0", FLIGHT_X0 - 0.062, FLIGHT_X0 - 0.012, SPLIT_Y1 + 0.04, ST_Y1 - 0.04,
                  0.0005, 0.0035, M["nosing"])
    for i in range(1, NSTEP):
        _instance(c, dstrip, f"Stair_Nosing_dn{i}", (dstrip.location.x + i * TREAD, dstrip.location.y, dstrip.location.z - i * RISE))

    # stainless railing on the curb + wall handrail with brackets (ref 106)
    slope = RISE / TREAD

    def nose_z(x):
        return RISE + (x - FLIGHT_X0) * slope

    ry = (SPLIT_Y0 + SPLIT_Y1) / 2
    xa, xb = FLIGHT_X0 + 0.08, FLIGHT_X0 + (NSTEP - 1) * TREAD - 0.05
    _tube(c, hall, "Stair_RailTop", (xa, ry, nose_z(xa) + 0.90), (xb, ry, nose_z(xb) + 0.90), 0.021, M["stainless"], seg=16)
    for k, px in enumerate((xa + 0.02, (xa + xb) / 2, xb - 0.02)):
        base = math.floor((px - FLIGHT_X0) / TREAD + 1) * RISE + 0.12
        _tube(c, hall, f"Stair_RailPost{k}", (px, ry, base), (px, ry, nose_z(px) + 0.885), 0.016, M["stainless"], seg=12)
    wy = ST_Y0 + 0.065
    _tube(c, hall, "Stair_WallRail", (FLIGHT_X0 - 0.25, wy, 0.88), (xb, wy, nose_z(xb) + 0.88), 0.019, M["stainless"], seg=16)
    _tube(c, hall, "Stair_WallRailLevel", (x0 + 0.15, wy, 0.88), (FLIGHT_X0 - 0.25, wy, 0.88), 0.019, M["stainless"], seg=16)
    for k, px in enumerate((x0 + 0.25, FLIGHT_X0 + 0.6, FLIGHT_X0 + 1.5)):
        zt = 0.88 if px < FLIGHT_X0 - 0.25 else nose_z(px) + 0.88
        _tube(c, hall, f"Stair_RailBracketV{k}", (px, wy, zt - 0.075), (px, wy, zt - 0.02), 0.008, M["stainless"])
        _tube(c, hall, f"Stair_RailBracketH{k}", (px, ST_Y0, zt - 0.075), (px, wy, zt - 0.075), 0.008, M["stainless"])
    # wall super-graphics (ref 106 "B1" door graphic → floor numbers)
    _plane(c, hall, "Stair_Graphic4F", 0.80, 0.80, _img_mat("StairGfx4F", "stair_graphic_4f.png", 0.7, alpha=True),
           (ST_X1 - 0.002, 2.30, NSTEP * RISE + 0.75), (0, 0, -90))
    _plane(c, hall, "Stair_Graphic3F", 0.90, 0.90, _img_mat("StairGfx3F", "stair_graphic_3f.png", 0.7, alpha=True),
           (5.20, ST_Y1 - 0.002, 1.35), (0, 0, 0))
    _plane(c, hall, "Stair_Graphic2F", 0.70, 0.70, _img_mat("StairGfx2F", "stair_graphic_2f.png", 0.7, alpha=True),
           (ST_X1 - 0.002, 3.55, -NSTEP * RISE + 0.95), (0, 0, -90))
    # ceiling lights
    for k, (lx, ly) in enumerate(((5.30, 2.90), (7.70, 2.90))):
        _cyl(c, hall, f"Stair_CeilLamp{k}", 0.16, 0.05, _pbr("LampBodyWhite", (0.85, 0.85, 0.84), 0.4),
             (lx, ly, ST_Z1 - 0.025), seg=28)
        _cyl(c, hall, f"Stair_CeilLampLens{k}", 0.14, 0.004, M["led"], (lx, ly, ST_Z1 - 0.052), seg=28, smooth=False)
    _area_light(c, hall, "Stair_LightA", (5.30, 2.90, ST_Z1 - 0.10), 0.8, 70.0)
    _area_light(c, hall, "Stair_LightB", (7.70, 2.90, ST_Z1 - 0.10), 0.8, 60.0)
    _area_light(c, hall, "Stair_LightPit", (7.70, 3.55, 0.6), 0.6, 25.0)

    # yellow tactile warning blocks in front of the stair door (ref 087 092 104)
    tile = 0.30
    tb = _box(c, hall, "Tactile_Plate", 4.00, 4.00 + 2 * tile, 1.80, 1.80 + 3 * tile, -0.002, 0.004, M["tactile"], 0.0015)
    bm = bmesh.new()
    for ix in range(12):
        for iy in range(18):
            ctr = Matrix.Translation((4.00 + 0.025 + ix * 0.05, 1.80 + 0.025 + iy * 0.05, 0.004 + 0.0025))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.013, radius2=0.009, depth=0.005, matrix=ctr)
    me = bpy.data.meshes.new(PFX + "Tactile_Dots")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["tactile"])
    ob = bpy.data.objects.new(PFX + "Tactile_Dots", me)
    ob.parent = hall
    c.objects.link(ob)
    _reg(ob)
    _smooth(ob, 50)


def build_cleaning(c, hall, M):
    """Red mop bucket with a string mop + a blue flat mop by the restroom (ref 092)."""
    bx, by = 4.36, 0.40
    root = _W().empty(PFX + "MopBucket", c, (bx, by, 0.0), parent=hall)
    _reg(root)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=28, radius1=0.135, radius2=0.165, depth=0.30,
                          matrix=Matrix.Translation((0, 0, 0.18)))
    me = bpy.data.meshes.new(PFX + "MopBucket_Shell")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["bucket_red"])
    shell = bpy.data.objects.new(PFX + "MopBucket_Shell", me)
    shell.parent = root
    c.objects.link(shell)
    _reg(shell)
    sol = shell.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.005
    sol.offset = 1.0
    _smooth(shell, 40)
    _cyl(c, root, "MopBucket_Bottom", 0.135, 0.01, M["bucket_red"], (0, 0, 0.035), seg=28)
    _cyl(c, root, "MopBucket_Rim", 0.168, 0.014, M["bucket_red"], (0, 0, 0.328), seg=28)
    _cyl(c, root, "MopBucket_Water", 0.149, 0.004, M["water"], (0, 0, 0.17), seg=28)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        _cyl(c, root, f"MopBucket_Caster{k}", 0.016, 0.022, M["black_plastic"],
             (0.12 * math.cos(a), 0.12 * math.sin(a), 0.016), (90, 0, math.degrees(a)), seg=12)
    # wire bail handle
    pts = [(0.168 * math.cos(math.radians(t)), 0.0, 0.31 + 0.13 * math.sin(math.radians(t))) for t in range(0, 181, 15)]
    for k in range(len(pts) - 1):
        _tube(c, root, f"MopBucket_Bail{k}", pts[k], pts[k + 1], 0.003, M["stainless"], seg=6)
    # wringer basket hanging on the rim (탈수기), grey plastic
    _box(c, root, "MopBucket_Wringer", -0.16, -0.03, -0.09, 0.09, 0.20, 0.36, M["grey_plastic"], 0.01)
    _tube(c, root, "MopBucket_WringerLever", (-0.10, 0.0, 0.36), (-0.12, 0.0, 0.62), 0.008, M["grey_plastic"])

    # string mop standing in the bucket, leaning onto the end wall (pier A)
    lean = math.degrees(math.atan2(END_X0 - 0.015 - (bx + 0.05), 1.00))
    mop = _W().empty(PFX + "StringMop", c, (bx + 0.05, by + 0.02, 0.30), parent=hall)
    mop.rotation_euler = (0, math.radians(lean), 0)
    _reg(mop)
    _cyl(c, mop, "StringMop_Handle", 0.012, 0.90, M["alu"], (0, 0, 0.52), seg=12)
    _cyl(c, mop, "StringMop_Grip", 0.015, 0.16, M["handle_blue"], (0, 0, 0.92), seg=12)
    _cyl(c, mop, "StringMop_Clamp", 0.03, 0.06, M["grey_plastic"], (0, 0, 0.08), seg=14)
    rnd = random.Random(3)
    bm = bmesh.new()
    for k in range(40):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.0, 0.028)
        tilt = rnd.uniform(6, 22)
        L = rnd.uniform(0.20, 0.28)
        rot = Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(math.radians(tilt), 4, "X")
        mtx = Matrix.Translation((r * math.cos(a), r * math.sin(a), 0.06)) @ rot @ Matrix.Translation((0, 0, -L / 2))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=5, radius1=0.007, radius2=0.009, depth=L, matrix=mtx)
    me = bpy.data.meshes.new(PFX + "StringMop_Strands")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["mop_cotton"])
    st = bpy.data.objects.new(PFX + "StringMop_Strands", me)
    st.parent = mop
    c.objects.link(st)
    _reg(st)
    _smooth(st, 60)

    # flat mop (blue microfiber pad flat on the floor, handle leaning to the wall)
    fx, fy = 4.38, 0.665
    fl_lean = math.degrees(math.atan2(END_X0 - 0.014 - fx, 1.16))
    _box(c, hall, "FlatMop_Pad", fx - 0.21, fx + 0.21, fy - 0.06, fy + 0.06, 0.0, 0.022, M["pad_blue"], 0.008)
    _box(c, hall, "FlatMop_Plate", fx - 0.19, fx + 0.19, fy - 0.045, fy + 0.045, 0.022, 0.034, M["grey_plastic"], 0.004)
    fm = _W().empty(PFX + "FlatMop", c, (fx, fy, 0.045), parent=hall)
    fm.rotation_euler = (0, math.radians(fl_lean), 0)
    _reg(fm)
    _cyl(c, fm, "FlatMop_Joint", 0.016, 0.04, M["grey_plastic"], (0, 0, 0.0), seg=12)
    _cyl(c, fm, "FlatMop_Handle", 0.011, 1.08, M["alu"], (0, 0, 0.56), seg=12)
    _cyl(c, fm, "FlatMop_Grip", 0.014, 0.14, M["handle_blue"], (0, 0, 1.06), seg=12)


def build_recycling(c, hall, M):
    """Four-way 분리수거 bin row against the gym-side wall."""
    labels = (("general", "recycle_general.png"), ("plastic", "recycle_plastic.png"),
              ("can", "recycle_can.png"), ("paper", "recycle_paper.png"))
    y0, y1 = 0.17, 0.53
    body = None
    for i, (k, img) in enumerate(labels):
        x0 = 3.00 + i * 0.285
        if body is None:
            body = _box(c, hall, f"Bin_{k}_Body", x0, x0 + 0.27, y0, y1, 0.0, 0.66, M["grey_plastic"], 0.012)
        else:
            _instance(c, body, f"Bin_{k}_Body", (x0 + 0.135, body.location.y, body.location.z))
        _box(c, hall, f"Bin_{k}_Lid", x0 - 0.004, x0 + 0.274, y0 - 0.004, y1 + 0.006, 0.66, 0.71, M["lid_" + k], 0.012)
        _box(c, hall, f"Bin_{k}_Slot", x0 + 0.06, x0 + 0.21, y0 + 0.12, y0 + 0.24, 0.708, 0.7115, M["black_plastic"], 0.004)
        _plane(c, hall, f"Bin_{k}_Label", 0.20, 0.167, _img_mat("BinLabel_" + k, img, 0.35), (x0 + 0.135, y1 + 0.0012, 0.47), (0, 0, 180))
    # taped notice above the bins (no bicycles / no stored items)
    _plane(c, hall, "Notice_Bicycle", 0.21, 0.297, _img_mat("NoticeBicycle", "notice_bicycle.png", 0.6), (3.55, 0.157, 1.32), (0, 0, 180))
    for k, (dx, dz) in enumerate(((-0.095, 0.14), (0.095, 0.14), (-0.095, -0.14), (0.095, -0.14))):
        _plane(c, hall, f"Notice_Tape{k}", 0.05, 0.018, M["tape"], (3.55 + dx, 0.159, 1.32 + dz), (0, 35 if k % 3 == 0 else -35, 180))


def build_flyer_rack(c, hall, M):
    """Wall-mounted flyer rack: grey metal frame, red header, wire pockets, 2x3 flyers (ref 118 121 125)."""
    wall_y = 2.88
    x0, x1 = 3.20, 3.66
    _box(c, hall, "Rack_Back", x0, x1, wall_y - 0.012, wall_y - 0.002, 0.58, 1.60, M["rack_metal"], 0.002)
    for k, x in enumerate((x0 + 0.01, x1 - 0.01)):
        _box(c, hall, f"Rack_Side{k}", x - 0.01, x + 0.01, wall_y - 0.13, wall_y - 0.012, 0.56, 1.62, M["rack_metal"], 0.003)
    _box(c, hall, "Rack_HeaderPlate", x0, x1, wall_y - 0.135, wall_y - 0.12, 1.60, 1.74, M["rack_metal"], 0.002)
    _plane(c, hall, "Rack_Header", 0.44, 0.11, _img_mat("RackHeader", "rack_header.png", 0.35), ((x0 + x1) / 2, wall_y - 0.1365, 1.67))
    tilt = -10.0
    fw, fh = 0.20, 0.285
    for t, zb in enumerate((0.60, 0.94, 1.28)):
        _box(c, hall, f"Rack_Tray{t}", x0 + 0.02, x1 - 0.02, wall_y - 0.12, wall_y - 0.012, zb - 0.008, zb, M["rack_metal"], 0.002)
        for kz, dz in enumerate((0.07, 0.17)):
            _tube(c, hall, f"Rack_Wire{t}_{kz}", (x0 + 0.02, wall_y - 0.118, zb + dz), (x1 - 0.02, wall_y - 0.118, zb + dz), 0.0025,
                  M["rack_metal"], seg=6)
        _tube(c, hall, f"Rack_Div{t}", ((x0 + x1) / 2, wall_y - 0.118, zb), ((x0 + x1) / 2, wall_y - 0.118, zb + 0.18), 0.0025,
              M["rack_metal"], seg=6)
        for s in range(2):
            idx = t * 2 + s
            cx = x0 + 0.12 + s * 0.22
            by = wall_y - 0.085
            a = math.radians(tilt)
            cy, cz = by - (fh / 2) * math.sin(a), zb + 0.004 + (fh / 2) * math.cos(a)
            stack = _box(c, hall, f"Flyer{idx}_Stack", cx - fw / 2, cx + fw / 2, -0.004, 0.004, -fh / 2, fh / 2, M["paper"])
            stack.location = (cx, cy + 0.006, cz)
            stack.rotation_euler = (a, 0, 0)
            _plane(c, hall, f"Flyer{idx}", fw, fh, _img_mat(f"Flyer{idx}", f"flyer_{idx}.png", 0.55),
                   (cx, cy + 0.006 - 0.0045 * math.cos(a), cz - 0.0045 * math.sin(a)), (tilt, 0, 0))


# ==========================================================================================================
# 4) Public API
# ==========================================================================================================
def _touch_existing():
    touched = []
    for n in REPLACED:
        ob = bpy.data.objects.get(n)
        if not ob:
            continue
        if "detail_orig_hide_render" not in ob:
            ob["detail_orig_hide_render"] = ob.hide_render
            ob["detail_orig_hide_viewport"] = ob.hide_viewport
        ob["detail_pkg"] = KEY
        ob.hide_render = True
        ob.hide_viewport = True
        touched.append(f"{n}: hidden (superseded by the new end wall / exit light)")
    return touched


def restore_existing():
    for ob in bpy.data.objects:
        if ob.get("detail_pkg") == KEY and "detail_orig_hide_render" in ob:
            ob.hide_render = bool(ob["detail_orig_hide_render"])
            ob.hide_viewport = bool(ob["detail_orig_hide_viewport"])


def _clear(c):
    for ob in list(c.all_objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and getattr(data, "users", 1) == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)


def apply() -> dict:
    _ADDED.clear()
    hall = bpy.data.objects["Sangga_Hallway"]
    set_c = bpy.data.collections["SET"]
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
    if c.name not in [ch.name for ch in set_c.children]:
        set_c.children.link(c)
    _clear(c)
    touched = _touch_existing()
    M = _mats()
    build_end_wall(c, hall, M)
    build_restroom(c, hall, M)
    build_stair_hall(c, hall, M)
    build_cleaning(c, hall, M)
    build_recycling(c, hall, M)
    build_flyer_rack(c, hall, M)

    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in c.all_objects:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        ev.to_mesh_clear()
    return {"collection": COLL, "objects_added": len(c.all_objects), "triangles_added": tris,
            "existing_touched": touched}


if __name__ == "__main__" and "--textures" in sys.argv:
    make_textures()
