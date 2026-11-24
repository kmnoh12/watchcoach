"""Detail pass `hall_storefronts`: shop glass-door hardware, window vinyl/stickers, entrance mats, umbrella stand,
A-board and the papered vacant storefront in the sangga hallway outside the WatchCoach gym.

References (work/refs/hall): 127 (frameless glass doors, stainless top/bottom patch rails, floor-hinge plates,
top key cylinders), 128 (vacant shop glass, taped), 129 (floor-hinge pivot, long round pull handle, blue-gray
herringbone entrance mat), 130 (glass-door digital lock on meeting stiles), 131 (frosted film band, CCTV / phone
vinyl lettering, navy logo mat), 132 (red pull stickers by the handles, stainless umbrella stand, frosted band),
135 (store-name band on glass), 004/065/015/096/102 (sangga storefront rhythm, stainless mullions, closers).

Usage (inside Blender, scene_gym.blend open):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_hall_storefronts; detail_hall_storefronts.apply()
Decal textures are generated (outside Blender) with:
    ~/.venvs/pdf/bin/python promo/tools/detail_hall_storefronts.py --gen
"""
import math
import os
import random
import sys

try:
    import bpy
    import bmesh
    from mathutils import Vector
except ImportError:  # texture generation runs in a plain Python with PIL
    bpy = None

KEY = "hall_storefronts"
COLL = "DETAIL_hall_storefronts"
P = "Dhall_storefronts_"
HERE = os.path.dirname(os.path.abspath(__file__))
PART_DIR = os.path.join(os.path.dirname(HERE), "parts", "detail_hall_storefronts")
FONT_B = os.path.join(os.path.dirname(HERE), "parts", "fonts", "NanumGothic-Bold.ttf")
FONT_R = os.path.join(os.path.dirname(HERE), "parts", "fonts", "Cafe24Ssurround.ttf")

# Decal sizes in metres (width, height). Images are generated with exactly this aspect.
DECALS = {
    "gym_letters": (0.56, 0.14),
    "gym_hours": (0.19, 0.25),
    "card_sticker": (0.20, 0.09),
    "cctv_sticker": (0.15, 0.10),
    "qr_sticker": (0.10, 0.13),
    "pull_sticker": (0.055, 0.12),
    "push_sticker": (0.055, 0.12),
    "keypad": (0.052, 0.15),
    "eroom_letters": (0.60, 0.13),
    "eroom_hours": (0.20, 0.26),
    "eroom_phone": (0.42, 0.10),
    "lease_sheet": (0.42, 0.594),
    "notice_mgmt": (0.21, 0.297),
    "notice_mail": (0.21, 0.148),
    "notice_power": (0.21, 0.297),
    "paper_kraft": (0.64, 0.95),
    "paper_news": (0.60, 0.95),
    "paper_white": (0.64, 0.95),
    "mat_gym": (1.30, 0.60),
    "mat_herring": (1.30, 0.55),
    "aboard_front": (0.44, 0.74),
    "aboard_back": (0.44, 0.74),
}


# --------------------------------------------------------------------------------------------
# Texture generation (plain Python + PIL)
# --------------------------------------------------------------------------------------------
def generate_textures():
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    os.makedirs(PART_DIR, exist_ok=True)
    PPM = 2000  # pixels per metre for small stickers

    def canvas(key, ppm=PPM, bg=(0, 0, 0, 0), cap=2048):
        w, h = DECALS[key]
        s = min(ppm, cap / max(w, h))
        return Image.new("RGBA", (max(8, int(w * s)), max(8, int(h * s))), bg)

    def font(size, path=FONT_B):
        return ImageFont.truetype(path, max(6, int(size)))

    def text_c(d, img, y, s, size, fill, path=FONT_B, max_w=None, x=None, anchor="mm"):
        max_w = max_w or img.width * 0.9
        f = font(size, path)
        while d.textlength(s, font=f) > max_w and size > 6:
            size *= 0.94
            f = font(size, path)
        d.text((img.width / 2 if x is None else x, y), s, font=f, fill=fill, anchor=anchor)
        return f

    def save(img, key, quality=None):
        path = os.path.join(PART_DIR, key + ".png")
        img.save(path, optimize=True)
        return path

    # 1) Gym cutting letters (white vinyl, transparent) -- matches the existing '워치코치 짐' signage
    im = canvas("gym_letters")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    text_c(d, im, H_ * 0.34, "WATCHCOACH GYM", H_ * 0.40, (250, 250, 250, 255))
    text_c(d, im, H_ * 0.80, "워치코치 짐  ·  24H 헬스 · PT", H_ * 0.24, (250, 250, 250, 255))
    save(im, "gym_letters")

    # 2) Business hours sticker (영업시간)
    im = canvas("gym_hours")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    d.rounded_rectangle((4, 4, W_ - 4, H_ - 4), radius=int(W_ * 0.06), fill=(250, 250, 248, 255))
    d.rectangle((4, int(H_ * 0.05), W_ - 4, int(H_ * 0.22)), fill=(20, 22, 26, 255))
    text_c(d, im, H_ * 0.135, "영업시간  OPEN", H_ * 0.09, (255, 255, 255, 255))
    rows = [("평  일", "06:00 - 24:00"), ("토요일", "08:00 - 22:00"), ("일·공휴일", "10:00 - 20:00")]
    for i, (a, b) in enumerate(rows):
        y = H_ * (0.32 + i * 0.13)
        d.text((W_ * 0.08, y), a, font=font(H_ * 0.058), fill=(30, 30, 30, 255), anchor="lm")
        d.text((W_ * 0.93, y), b, font=font(H_ * 0.062), fill=(30, 30, 30, 255), anchor="rm")
        d.line((W_ * 0.08, y + H_ * 0.055, W_ * 0.92, y + H_ * 0.055), fill=(200, 200, 200, 255), width=2)
    text_c(d, im, H_ * 0.75, "매월 둘째·넷째 일요일 휴관", H_ * 0.05, (200, 30, 40, 255))
    text_c(d, im, H_ * 0.86, "상담문의 053-746-0302", H_ * 0.05, (60, 60, 60, 255))
    save(im, "gym_hours")

    # 3) Card payment sticker (generic invented card icons, no real brands)
    im = canvas("card_sticker")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    d.rounded_rectangle((3, 3, W_ - 3, H_ - 3), radius=int(H_ * 0.12), fill=(255, 255, 255, 255), outline=(40, 80, 170, 255), width=6)
    text_c(d, im, H_ * 0.25, "카드 결제 가능", H_ * 0.20, (30, 60, 150, 255))
    cols = [(220, 50, 60), (40, 120, 200), (240, 170, 30), (40, 160, 90)]
    labels = ["CREDIT", "CHECK", "IC", "MOBILE"]
    cw = W_ * 0.19
    for i, (col, lab) in enumerate(zip(cols, labels)):
        x0 = W_ * 0.06 + i * (cw + W_ * 0.035)
        y0 = H_ * 0.46
        d.rounded_rectangle((x0, y0, x0 + cw, y0 + cw * 0.62), radius=int(cw * 0.09), fill=(*col, 255))
        d.rounded_rectangle((x0 + cw * 0.12, y0 + cw * 0.14, x0 + cw * 0.32, y0 + cw * 0.30), radius=3, fill=(235, 205, 120, 255))
        d.text((x0 + cw / 2, y0 + cw * 0.47), lab, font=font(cw * 0.15), fill=(255, 255, 255, 255), anchor="mm")
    save(im, "card_sticker")

    # 4) CCTV notice (yellow/black)
    im = canvas("cctv_sticker")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    d.rounded_rectangle((3, 3, W_ - 3, H_ - 3), radius=int(H_ * 0.08), fill=(250, 205, 20, 255), outline=(20, 20, 20, 255), width=8)
    # camera pictogram
    cx, cy = W_ * 0.22, H_ * 0.42
    d.polygon([(cx - W_ * 0.12, cy - H_ * 0.10), (cx + W_ * 0.08, cy - H_ * 0.16), (cx + W_ * 0.11, cy + H_ * 0.02), (cx - W_ * 0.10, cy + H_ * 0.08)], fill=(20, 20, 20, 255))
    d.rectangle((cx - W_ * 0.02, cy + H_ * 0.05, cx + W_ * 0.01, cy + H_ * 0.22), fill=(20, 20, 20, 255))
    d.rectangle((cx - W_ * 0.08, cy + H_ * 0.20, cx + W_ * 0.07, cy + H_ * 0.25), fill=(20, 20, 20, 255))
    d.text((W_ * 0.66, H_ * 0.30), "CCTV", font=font(H_ * 0.22), fill=(20, 20, 20, 255), anchor="mm")
    d.text((W_ * 0.66, H_ * 0.56), "24시간 녹화중", font=font(H_ * 0.13), fill=(20, 20, 20, 255), anchor="mm")
    text_c(d, im, H_ * 0.84, "본 매장은 CCTV가 설치되어 있습니다", H_ * 0.085, (20, 20, 20, 255), max_w=W_ * 0.88)
    save(im, "cctv_sticker")

    # 5) QR sticker (pseudo-random pattern, not a real code)
    im = canvas("qr_sticker")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    d.rounded_rectangle((2, 2, W_ - 2, H_ - 2), radius=int(W_ * 0.06), fill=(255, 255, 255, 255), outline=(30, 30, 30, 255), width=5)
    text_c(d, im, H_ * 0.09, "QR 체크인 · 상담예약", H_ * 0.06, (30, 30, 30, 255))
    n = 25
    qs = W_ * 0.80
    x0, y0 = (W_ - qs) / 2, H_ * 0.16
    cell = qs / n
    rng = random.Random(302)
    for i in range(n):
        for j in range(n):
            if rng.random() < 0.48:
                d.rectangle((x0 + i * cell, y0 + j * cell, x0 + (i + 1) * cell, y0 + (j + 1) * cell), fill=(15, 15, 15, 255))
    for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):
        ax, ay = x0 + fx * cell, y0 + fy * cell
        d.rectangle((ax, ay, ax + 7 * cell, ay + 7 * cell), fill=(255, 255, 255, 255))
        d.rectangle((ax, ay, ax + 7 * cell, ay + 7 * cell), outline=(15, 15, 15, 255), width=int(cell))
        d.rectangle((ax + 2 * cell, ay + 2 * cell, ax + 5 * cell, ay + 5 * cell), fill=(15, 15, 15, 255))
    text_c(d, im, H_ * 0.90, "카메라로 스캔하세요", H_ * 0.055, (90, 90, 90, 255))
    save(im, "qr_sticker")

    # 6) Push / pull stickers (red vertical, ref 132)
    for key, ko, en in (("pull_sticker", "당기세요", "PULL"), ("push_sticker", "미세요", "PUSH")):
        im = canvas(key)
        d = ImageDraw.Draw(im)
        W_, H_ = im.size
        d.rounded_rectangle((2, 2, W_ - 2, H_ - 2), radius=int(W_ * 0.15), fill=(205, 30, 40, 255))
        d.rounded_rectangle((W_ * 0.08, H_ * 0.04, W_ * 0.92, H_ * 0.96), radius=int(W_ * 0.12), outline=(255, 255, 255, 255), width=4)
        chars = list(ko)
        fs = min(W_ * 0.58, H_ * 0.62 / len(chars))
        for i, ch in enumerate(chars):
            d.text((W_ / 2, H_ * 0.12 + fs * (i + 0.5) * 1.02), ch, font=font(fs), fill=(255, 255, 255, 255), anchor="mm")
        d.text((W_ / 2, H_ * 0.87), en, font=font(W_ * 0.27), fill=(255, 255, 255, 255), anchor="mm")
        save(im, key)

    # 7) Digital door-lock keypad face (ref 130)
    im = canvas("keypad", bg=(18, 19, 22, 255))
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    d.rounded_rectangle((W_ * 0.1, H_ * 0.08, W_ * 0.9, H_ * 0.62), radius=int(W_ * 0.08), fill=(10, 10, 12, 255), outline=(70, 72, 78, 255), width=3)
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]
    for k, lab in enumerate(keys):
        r, cc = divmod(k, 3)
        x = W_ * (0.27 + cc * 0.23)
        y = H_ * (0.15 + r * 0.13)
        d.text((x, y), lab, font=font(W_ * 0.16), fill=(120, 200, 255, 255), anchor="mm")
    d.ellipse((W_ * 0.35, H_ * 0.72, W_ * 0.65, H_ * 0.72 + W_ * 0.30), fill=(150, 152, 158, 255), outline=(60, 60, 66, 255), width=3)
    d.rectangle((W_ * 0.44, H_ * 0.92, W_ * 0.56, H_ * 0.95), fill=(70, 220, 120, 255))
    save(im, "keypad")

    # 8) English academy cutting letters (navy with white outline, consistent with 이룸하이 영어교습소 signs)
    im = canvas("eroom_letters")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    f = font(H_ * 0.42)
    d.text((W_ / 2, H_ * 0.34), "이룸하이 영어교습소", font=f, fill=(18, 40, 110, 255), anchor="mm", stroke_width=5, stroke_fill=(255, 255, 255, 255))
    d.text((W_ / 2, H_ * 0.80), "EroomHigh English  ·  304호", font=font(H_ * 0.22), fill=(18, 40, 110, 255), anchor="mm", stroke_width=4, stroke_fill=(255, 255, 255, 255))
    save(im, "eroom_letters")

    # 9) Academy class hours sticker
    im = canvas("eroom_hours")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    d.rounded_rectangle((4, 4, W_ - 4, H_ - 4), radius=int(W_ * 0.07), fill=(255, 255, 255, 255), outline=(18, 40, 110, 255), width=8)
    d.rectangle((8, int(H_ * 0.05), W_ - 8, int(H_ * 0.21)), fill=(18, 40, 110, 255))
    text_c(d, im, H_ * 0.13, "수업시간 안내", H_ * 0.085, (255, 255, 255, 255))
    rows = [("월 - 금", "14:00 - 22:00"), ("토요일", "10:00 - 18:00"), ("일요일", "휴  무")]
    for i, (a, b) in enumerate(rows):
        y = H_ * (0.32 + i * 0.13)
        d.text((W_ * 0.09, y), a, font=font(H_ * 0.058), fill=(30, 30, 30, 255), anchor="lm")
        d.text((W_ * 0.92, y), b, font=font(H_ * 0.062), fill=(30, 30, 30, 255), anchor="rm")
    text_c(d, im, H_ * 0.74, "초·중·고 내신 / 수능 영어", H_ * 0.052, (200, 150, 20, 255))
    text_c(d, im, H_ * 0.86, "방문 상담은 사전 예약제", H_ * 0.05, (90, 90, 90, 255))
    save(im, "eroom_hours")

    # 10) Phone / contact vinyl lettering (ref 131 white cut text)
    im = canvas("eroom_phone")
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    d.text((W_ * 0.02, H_ * 0.28), "☎", font=font(H_ * 0.40), fill=(18, 40, 110, 255), anchor="lm")
    d.text((W_ * 0.13, H_ * 0.28), "053 - 746 - 1162", font=font(H_ * 0.36), fill=(18, 40, 110, 255), anchor="lm", stroke_width=3, stroke_fill=(255, 255, 255, 255))
    fs = H_ * 0.19
    while d.textlength("방문 상담을 원하시면 사전 문의 부탁드립니다 :)", font=font(fs)) > W_ * 0.85:
        fs *= 0.95
    d.text((W_ * 0.13, H_ * 0.76), "방문 상담을 원하시면 사전 문의 부탁드립니다 :)", font=font(fs), fill=(18, 40, 110, 255), anchor="lm", stroke_width=2, stroke_fill=(255, 255, 255, 255))
    save(im, "eroom_phone")

    # 11) Vacant-shop sheets
    def paper_noise(img, base, amp, seed, blur=1.2):
        rng = random.Random(seed)
        px = img.load()
        for y in range(img.height):
            for x in range(img.width):
                v = rng.randint(-amp, amp)
                px[x, y] = tuple(max(0, min(255, base[i] + v)) for i in range(3)) + (255,)
        return img.filter(ImageFilter.GaussianBlur(blur))

    def wrinkles(img, seed, n=18, col=(0, 0, 0, 12)):
        rng = random.Random(seed)
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for _ in range(n):
            x0, y0 = rng.uniform(0, img.width), rng.uniform(0, img.height)
            a = rng.uniform(-0.6, 0.6) + (math.pi / 2 if rng.random() < 0.5 else 0)
            L = rng.uniform(0.2, 0.7) * img.height
            d.line((x0, y0, x0 + math.cos(a) * L, y0 + math.sin(a) * L), fill=col, width=rng.randint(2, 5))
            d.line((x0 + 3, y0 + 3, x0 + 3 + math.cos(a) * L, y0 + 3 + math.sin(a) * L), fill=(255, 255, 255, 30), width=2)
        ov = ov.filter(ImageFilter.GaussianBlur(3))
        return Image.alpha_composite(img, ov)

    for key, base, seed in (("paper_kraft", (176, 138, 96), 11), ("paper_white", (236, 234, 226), 12)):
        im = Image.new("RGBA", (384, 570), (0, 0, 0, 255))
        im = paper_noise(im, base, 10, seed)
        im = wrinkles(im, seed)
        save(im, key)

    im = Image.new("RGBA", (384, 608), (0, 0, 0, 255))
    im = paper_noise(im, (214, 210, 198), 6, 13, 0.6)
    d = ImageDraw.Draw(im)
    rng = random.Random(14)
    d.rectangle((20, 16, 364, 70), fill=(60, 60, 60, 255))
    for col in range(4):
        x0 = 20 + col * 87
        y = 86
        while y < 590:
            if rng.random() < 0.08:
                d.rectangle((x0, y, x0 + 78, y + rng.randint(40, 90)), fill=(150, 150, 146, 255))
                y += 100
                continue
            d.line((x0, y, x0 + rng.randint(55, 78), y), fill=(95, 95, 92, 255), width=3)
            y += 8
    im = wrinkles(im, 15)
    save(im, "paper_news")

    # Big 임대문의 phone sheet (consistent with the existing for_lease.png: 303호, 010-2345-6789)
    im = canvas("lease_sheet", ppm=1500, bg=(252, 252, 250, 255))
    d = ImageDraw.Draw(im)
    W_, H_ = im.size
    text_c(d, im, H_ * 0.17, "임대", H_ * 0.20, (205, 25, 30, 255))
    text_c(d, im, H_ * 0.38, "문의", H_ * 0.20, (205, 25, 30, 255))
    d.line((W_ * 0.08, H_ * 0.53, W_ * 0.92, H_ * 0.53), fill=(40, 40, 40, 255), width=4)
    text_c(d, im, H_ * 0.62, "303호 · 실평수 35평", H_ * 0.055, (40, 40, 40, 255))
    text_c(d, im, H_ * 0.70, "즉시입주 · 권리금 없음", H_ * 0.055, (40, 40, 40, 255))
    text_c(d, im, H_ * 0.84, "010-2345-6789", H_ * 0.095, (20, 60, 170, 255), max_w=W_ * 0.94)
    text_c(d, im, H_ * 0.94, "건물주 직거래 · 중개 환영", H_ * 0.04, (110, 110, 110, 255))
    im = wrinkles(im, 21, n=10, col=(0, 0, 0, 14))
    save(im, "lease_sheet")

    for key, lines, seed in (
        ("notice_mgmt", [("안  내", 0.10, (20, 20, 20)), ("", 0.0, None),
                         ("공실 점포 앞 무단 적치 및", 0.045, (40, 40, 40)), ("전단지 부착을 금합니다.", 0.045, (40, 40, 40)),
                         ("", 0.0, None), ("위반 시 즉시 철거합니다.", 0.045, (190, 30, 30)), ("", 0.0, None),
                         ("워치코치 플라자", 0.042, (60, 60, 60)), ("관리사무소 (B1)", 0.042, (60, 60, 60))], 31),
        ("notice_mail", [("우편물 안내", 0.16, (20, 20, 20)), ("303호 우편물은", 0.10, (40, 40, 40)),
                         ("관리사무소에 맡겨 주세요", 0.10, (40, 40, 40))], 32),
        ("notice_power", [("전기·수도 점검", 0.075, (20, 20, 20)), ("", 0.0, None), ("일시: 12월 3일(수) 10:00", 0.045, (40, 40, 40)),
                          ("대상: 3층 공실 303호", 0.045, (40, 40, 40)), ("", 0.0, None), ("점검 중 출입을 삼가 주십시오", 0.042, (40, 40, 40)),
                          ("", 0.0, None), ("관리사무소", 0.045, (60, 60, 60))], 33),
    ):
        im = canvas(key, ppm=1500, bg=(250, 250, 247, 255))
        d = ImageDraw.Draw(im)
        W_, H_ = im.size
        y = H_ * 0.10
        for s, fs, col in lines:
            if not s:
                y += H_ * 0.04
                continue
            y += H_ * fs * 0.6
            text_c(d, im, y, s, H_ * fs, (*col, 255), max_w=W_ * 0.86)
            y += H_ * fs * 0.85
        im = wrinkles(im, seed, n=6, col=(0, 0, 0, 12))
        save(im, key)

    # 12) Entrance mats
    # Gym: navy tufted carpet mat with rubber border + logo (ref 131 'Smile' mat)
    im = Image.new("RGBA", (1040, 480), (0, 0, 0, 255))
    rng = random.Random(41)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            v = rng.randint(-9, 9)
            px[x, y] = (24 + v, 32 + v, 58 + v, 255)
    im = im.filter(ImageFilter.GaussianBlur(0.7))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1039, 479), outline=(14, 14, 16, 255), width=26)
    d.rectangle((26, 26, 1013, 453), outline=(40, 46, 70, 255), width=4)
    d.text((520, 210), "WATCHCOACH", font=font(120), fill=(196, 160, 82, 255), anchor="mm")
    d.text((520, 330), "워치코치 짐  ·  WELCOME", font=font(56), fill=(196, 160, 82, 255), anchor="mm")
    save(im.filter(ImageFilter.GaussianBlur(0.8)), "mat_gym")

    # Academy: blue-gray herringbone needle-punch mat (ref 129)
    im = Image.new("RGBA", (1040, 440), (70, 84, 104, 255))
    d = ImageDraw.Draw(im)
    step = 22
    for col in range(-2, 1040 // step + 3):
        for row in range(-2, 440 // step + 3):
            x, y = col * step, row * step
            sgn = 1 if col % 2 == 0 else -1
            c0 = (86, 100, 122, 255) if (row + col) % 2 else (62, 74, 94, 255)
            d.line((x, y, x + step * sgn * 0.0 + step, y + sgn * step), fill=c0, width=6)
    rng = random.Random(42)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            v = rng.randint(-8, 8)
            px[x, y] = (r + v, g + v, b + v, 255)
    im = im.filter(ImageFilter.GaussianBlur(1.0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1039, 439), outline=(22, 24, 28, 255), width=22)
    save(im, "mat_herring")

    # 13) A-board posters (루나 음악교습소, piano academy next door)
    for key, bg in (("aboard_front", (250, 246, 235)), ("aboard_back", (250, 246, 235))):
        im = canvas(key, ppm=1600, bg=(*bg, 255))
        d = ImageDraw.Draw(im)
        W_, H_ = im.size
        d.rectangle((0, 0, W_, H_ * 0.17), fill=(214, 160, 20, 255))
        text_c(d, im, H_ * 0.06, "루나 음악교습소", H_ * 0.055, (30, 25, 20, 255))
        text_c(d, im, H_ * 0.125, "PIANO · 성인 · 입시", H_ * 0.035, (30, 25, 20, 255))
        # keyboard strip
        kw = W_ / 14
        ky = H_ * 0.18
        for i in range(14):
            d.rectangle((i * kw + 1, ky, (i + 1) * kw - 1, ky + H_ * 0.07), fill=(255, 255, 255, 255), outline=(30, 30, 30, 255))
        for i in (0, 1, 3, 4, 5, 7, 8, 10, 11, 12):
            d.rectangle((i * kw + kw * 0.65, ky, i * kw + kw * 1.35, ky + H_ * 0.045), fill=(25, 25, 25, 255))
        if key == "aboard_front":
            text_c(d, im, H_ * 0.33, "신규 원생 모집", H_ * 0.07, (200, 30, 40, 255))
            items = [("유아·초등 피아노", "월 15만원"), ("성인 취미반", "월 18만원"), ("예중·예고 입시", "상담"), ("1:1 개인레슨", "주 2회")]
            for i, (a, b) in enumerate(items):
                y = H_ * (0.44 + i * 0.085)
                d.text((W_ * 0.07, y), a, font=font(H_ * 0.037), fill=(40, 35, 30, 255), anchor="lm")
                d.text((W_ * 0.93, y), b, font=font(H_ * 0.037), fill=(40, 35, 30, 255), anchor="rm")
                d.line((W_ * 0.07, y + H_ * 0.03, W_ * 0.93, y + H_ * 0.03), fill=(200, 190, 170, 255), width=2)
            d.rounded_rectangle((W_ * 0.08, H_ * 0.80, W_ * 0.92, H_ * 0.90), radius=12, fill=(30, 30, 30, 255))
            text_c(d, im, H_ * 0.85, "첫 상담 · 체험레슨 무료", H_ * 0.04, (255, 220, 80, 255))
            text_c(d, im, H_ * 0.95, "3층 305호  053-746-0305", H_ * 0.032, (60, 60, 60, 255))
        else:
            text_c(d, im, H_ * 0.34, "겨울방학 특강", H_ * 0.07, (30, 70, 160, 255))
            for i, s in enumerate(["체르니 · 소나티네 집중반", "콩쿠르 대비반", "성인 재즈 코드 반주", "주말 원데이 클래스"]):
                text_c(d, im, H_ * (0.46 + i * 0.075), s, H_ * 0.036, (40, 35, 30, 255))
            text_c(d, im, H_ * 0.82, "← 3층 305호", H_ * 0.06, (200, 30, 40, 255))
            text_c(d, im, H_ * 0.93, "053-746-0305", H_ * 0.04, (60, 60, 60, 255))
        save(im, key)
    print("textures written to", PART_DIR)


# --------------------------------------------------------------------------------------------
# Blender side
# --------------------------------------------------------------------------------------------
def _W():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import wc_lib
    return wc_lib


_MATS = {}


def _img(key):
    path = os.path.join(PART_DIR, key + ".png")
    im = bpy.data.images.get(P + key)
    if im is None:
        im = bpy.data.images.load(path, check_existing=True)
        im.name = P + key
    if not im.packed_file:
        im.pack()
    return im


def _decal_mat(key, rough=0.42, metal=0.0, alpha=True, spec=0.5, coat=0.0):
    name = P + "M_" + key
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _img(key)
    tex.extension = "CLIP" if alpha else "REPEAT"
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    if alpha:
        nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    try:
        m.surface_render_method = "DITHERED"
    except AttributeError:
        pass
    m.diffuse_color = (0.8, 0.8, 0.8, 1)
    return m


def _pmat(name, color, rough=0.5, metal=0.0, alpha=1.0, spec=0.5):
    full = P + name
    m = bpy.data.materials.get(full)
    if m:
        return m
    m = bpy.data.materials.new(full)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = "DITHERED"
        except AttributeError:
            pass
    m.diffuse_color = (*color, 1)
    return m


def _brushed_steel():
    full = P + "BrushedSteel"
    m = bpy.data.materials.get(full)
    if m:
        return m
    m = bpy.data.materials.new(full)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.70, 0.71, 0.73, 1)
    b.inputs["Metallic"].default_value = 1.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 140.0)  # long streaks along local X/Y, fine across Z
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 9.0
    nz.inputs["Detail"].default_value = 6.0
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.16
    mr.inputs["To Max"].default_value = 0.30
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    m.diffuse_color = (0.7, 0.71, 0.73, 1)
    return m


def _clear_glass():
    """Same recipe as the existing entrance glass (Transparent + faint Glossy), so the doors match."""
    full = P + "ClearGlass"
    m = bpy.data.materials.get(full)
    if m:
        return m
    m = bpy.data.materials.new(full)
    try:
        m.surface_render_method = "DITHERED"
    except AttributeError:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.18
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    trans.inputs["Color"].default_value = (0.93, 0.97, 0.96, 1)
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Color"].default_value = (0.90, 0.94, 0.98, 1)
    gloss.inputs["Roughness"].default_value = 0.03
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    add.inputs[1].default_value = 0.06
    nt.links.new(lw.outputs["Fresnel"], add.inputs[0])
    nt.links.new(add.outputs[0], mix.inputs["Fac"])
    nt.links.new(trans.outputs[0], mix.inputs[1])
    nt.links.new(gloss.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (0.85, 0.92, 0.95, 0.2)
    return m


def _link(ob, c, parent):
    c.objects.link(ob)
    ob.parent = parent
    return ob


def _plane(c, parent, name, w, h, mat, loc, face="-Y", tilt=0.0):
    """UV-mapped rectangle in the local XZ plane. face='-Y' is readable from -Y, face='+Y' from +Y.
    face='+Z' lies flat (w along X, h along Y). tilt = in-plane rotation (deg)."""
    hw, hh = w / 2, h / 2
    if face == "+Z":
        verts = [(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)]
    elif face == "+Y":
        verts = [(hw, 0, -hh), (-hw, 0, -hh), (-hw, 0, hh), (hw, 0, hh)]
    else:
        verts = [(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)]
    me = bpy.data.meshes.new(P + name)
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for loop, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = co
    me.materials.append(mat)
    ob = bpy.data.objects.new(P + name, me)
    ob.location = loc
    if tilt:
        ob.rotation_euler = (0, 0, math.radians(tilt)) if face == "+Z" else (0, math.radians(tilt), 0)
    return _link(ob, c, parent)


def _bm_obj(c, parent, name, bm, mat, loc=(0, 0, 0), rot=(0, 0, 0), smooth=False):
    me = bpy.data.meshes.new(P + name)
    bm.to_mesh(me)
    bm.free()
    if isinstance(mat, (list, tuple)):
        for mm in mat:
            me.materials.append(mm)
    else:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(P + name, me)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    return _link(ob, c, parent)


def _box(c, parent, name, size, mat, loc, rot=(0, 0, 0), bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = _bm_obj(c, parent, name, bm, mat, loc, rot)
    if bevel:
        mod = ob.modifiers.new("Bevel", "BEVEL")
        mod.width = min(bevel, min(size) * 0.42)
        mod.segments = 2
        mod.limit_method = "ANGLE"
        ob.data.polygons.foreach_set("use_smooth", [False] * len(ob.data.polygons))
    return ob


def _cyl(c, parent, name, r, h, mat, loc, rot=(0, 0, 0), seg=16, r2=None, smooth=True, caps=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    ob = _bm_obj(c, parent, name, bm, mat, loc, rot, smooth=smooth)
    if smooth:
        try:
            ob.modifiers.new("Smooth", "SMOOTH_BY_ANGLE")
        except Exception:
            pass
        _auto_smooth(ob)
    return ob


def _auto_smooth(ob, angle=40.0):
    """Flat caps / smooth sides without operators: mark sharp edges by face angle."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(angle):
            e.smooth = False
    bm.to_mesh(me)
    bm.free()
    for m in list(ob.modifiers):
        if m.type == "SMOOTH_BY_ANGLE" or m.name == "Smooth":
            ob.modifiers.remove(m)


def _slab(c, parent, name, w, d, t, chamfer, mat, loc, rot_z=0.0):
    """Floor mat: bevelled frustum slab, top face fully UV-mapped (texture border wraps the chamfer)."""
    hw, hd = w / 2, d / 2
    ch = chamfer
    v = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
         (-hw + ch, -hd + ch, t), (hw - ch, -hd + ch, t), (hw - ch, hd - ch, t), (-hw + ch, hd - ch, t)]
    f = [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (3, 2, 1, 0)]
    me = bpy.data.meshes.new(P + name)
    me.from_pydata(v, [], f)
    uv = me.uv_layers.new()
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, _ = v[me.loops[li].vertex_index]
            uv.data[li].uv = (x / w + 0.5, y / d + 0.5)
    me.materials.append(mat)
    ob = bpy.data.objects.new(P + name, me)
    ob.location = loc
    ob.rotation_euler = (0, 0, math.radians(rot_z))
    return _link(ob, c, parent)


def _tube_curve(c, parent, name, pts, radius, mat):
    cu = bpy.data.curves.new(P + name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1.0)
    cu.materials.append(mat)
    ob = bpy.data.objects.new(P + name, cu)
    return _link(ob, c, parent)


# ---------------------------------------------------------------- components
def _pull_handle(c, parent, tag, x, y_bar, y_glass, z0, z1, steel, objs, r=0.0125):
    """Long round stainless pull handle: bar + two standoffs reaching the glass face (ref 127/129/132)."""
    objs.append(_cyl(c, parent, f"{tag}_bar", r, z1 - z0, steel, (x, y_bar, (z0 + z1) / 2), seg=16))
    for i, zz in enumerate((z0 + 0.06, z1 - 0.06)):
        L = abs(y_glass - y_bar)
        objs.append(_cyl(c, parent, f"{tag}_standoff{i}", r * 0.7, L, steel, (x, (y_glass + y_bar) / 2, zz), rot=(90, 0, 0), seg=12))


def build_gym_entrance(c, hall, steel, objs):
    """Hall-side face of the existing gym glass double door (local y = 0 plane, hall on +Y)."""
    dark = _pmat("LockBody", (0.03, 0.032, 0.036), rough=0.30, metal=0.4)
    silver = _pmat("LockSilver", (0.62, 0.63, 0.65), rough=0.28, metal=0.9)
    key_m = _decal_mat("keypad", rough=0.18, alpha=False, coat=0.6)
    gy = 0.0105  # decal plane 4.5 mm off glass (glass face 0.006, frost band face 0.007)

    # 1) Floor-hinge cover plates in front of each pivot (ref 127: plates at both outer bottom corners)
    for s in (-1, 1):
        x = s * 0.665
        objs.append(_box(c, hall, f"GymFloorHinge_{'R' if s > 0 else 'L'}", (0.11, 0.20, 0.004), steel, (x, 0.226, 0.0025), bevel=0.0015))
        for dx in (-0.038, 0.038):
            for dy in (-0.08, 0.08):
                objs.append(_cyl(c, hall, f"GymHingeScrew_{s}_{dx}_{dy}", 0.0045, 0.0012, silver, (x + dx, 0.226 + dy, 0.0049), seg=8, smooth=False))
    # 2) Top-rail key cylinders / flush bolts at the meeting stiles (ref 127, 132)
    for s in (-1, 1):
        objs.append(_box(c, hall, f"GymTopBoltPlate_{s}", (0.045, 0.004, 0.065), steel, (s * 0.035, 0.0262, 2.12), bevel=0.0012))
        objs.append(_cyl(c, hall, f"GymTopCylinder_{s}", 0.011, 0.007, silver, (s * 0.035, 0.0315, 2.12), rot=(90, 0, 0), seg=16))
        objs.append(_box(c, hall, f"GymTopKeySlot_{s}", (0.0025, 0.002, 0.012), dark, (s * 0.035, 0.0352, 2.12)))
    # 3) Glass-door digital lock across the meeting stiles (ref 130): keypad outside, body inside
    objs.append(_box(c, hall, "GymLock_Keypad", (0.058, 0.022, 0.16), dark, (0.036, 0.0205, 1.02), bevel=0.004))
    objs.append(_plane(c, hall, "GymLock_KeypadFace", 0.052, 0.15, key_m, (0.036, 0.0318, 1.02), face="+Y"))
    objs.append(_box(c, hall, "GymLock_Inside", (0.060, 0.030, 0.19), silver, (0.036, -0.0245, 1.02), bevel=0.005))
    objs.append(_box(c, hall, "GymLock_Strike", (0.030, 0.018, 0.09), silver, (-0.022, 0.0185, 1.02), bevel=0.003))
    objs.append(_box(c, hall, "GymLock_StrikeIn", (0.030, 0.018, 0.09), silver, (-0.022, -0.0185, 1.02), bevel=0.003))

    # 4) Window vinyl & stickers on the hall side (face '+Y'). +X is the viewer's LEFT from the hallway.
    objs.append(_plane(c, hall, "GymVinyl_LettersL", 0.56, 0.14, _decal_mat("gym_letters", rough=0.35), (0.37, gy, 1.64), face="+Y"))
    objs.append(_plane(c, hall, "GymVinyl_LettersR", 0.56, 0.14, _decal_mat("gym_letters", rough=0.35), (-0.37, gy, 1.64), face="+Y"))
    objs.append(_plane(c, hall, "GymSticker_Hours", 0.19, 0.25, _decal_mat("gym_hours", rough=0.3), (0.46, gy, 1.40), face="+Y"))
    objs.append(_plane(c, hall, "GymSticker_Card", 0.20, 0.09, _decal_mat("card_sticker", rough=0.3), (-0.42, gy, 1.33), face="+Y"))
    objs.append(_plane(c, hall, "GymSticker_CCTV", 0.15, 0.10, _decal_mat("cctv_sticker", rough=0.3), (-0.42, gy, 1.46), face="+Y"))
    objs.append(_plane(c, hall, "GymSticker_QR", 0.10, 0.13, _decal_mat("qr_sticker", rough=0.3), (-0.62, gy, 1.40), face="+Y"))
    for s in (-1, 1):
        objs.append(_plane(c, hall, f"GymSticker_Pull_{s}", 0.055, 0.12, _decal_mat("pull_sticker", rough=0.3), (s * 0.15, gy, 1.43), face="+Y"))


def build_opposite_doors(c, hall, steel, glass, objs):
    """English academy (이룸하이) double door: the existing scene has handles/lock/blue tape but no glass,
    so add frameless tempered glass leaves with stainless top/bottom patch rails (ref 127), handle standoffs,
    a frosted film band (ref 131/132) and vinyl stickers on the hall side (face '-Y')."""
    gy0 = 2.836          # glass centre plane
    gt = 0.010           # 10 mm tempered glass -> hall face at 2.831
    z0, z1 = 0.142, 2.138
    leaves = ((-0.788, -0.053), (-0.047, 0.687))
    for i, (xa, xb) in enumerate(leaves):
        w = xb - xa
        cx = (xa + xb) / 2
        objs.append(_box(c, hall, f"OppGlass_{i}", (w, gt, z1 - z0 - 0.004), glass, (cx, gy0, (z0 + z1) / 2)))
        # stainless patch rails (bottom 100 mm, top 75 mm), 30 mm deep around the glass
        objs.append(_box(c, hall, f"OppRail_Bottom_{i}", (w, 0.030, 0.100), steel, (cx, gy0, z0 + 0.050), bevel=0.003))
        objs.append(_box(c, hall, f"OppRail_Top_{i}", (w, 0.030, 0.075), steel, (cx, gy0, z1 - 0.0375), bevel=0.003))
        # top-rail key cylinder near the meeting edge
        mx = xb - 0.04 if i == 0 else xa + 0.04
        objs.append(_cyl(c, hall, f"OppTopCylinder_{i}", 0.010, 0.006, _pmat("LockSilver", (0.62, 0.63, 0.65), rough=0.28, metal=0.9),
                         (mx, gy0 - 0.018, z1 - 0.0375), rot=(90, 0, 0), seg=16))
    # handle standoffs: existing bars at x=-0.17 / 0.07, y=2.78, z 0.66..1.38 float in front of nothing
    for i, hx in enumerate((-0.17, 0.07)):
        for j, zz in enumerate((0.72, 1.32)):
            L = (gy0 - gt / 2) - 2.794
            objs.append(_cyl(c, hall, f"OppHandleStandoff_{i}{j}", 0.0085, L + 0.002, steel, (hx, 2.794 + L / 2, zz), rot=(90, 0, 0), seg=12))
    # frosted film band at eye level (z 1.20..1.48), hall face of the glass
    frost = _pmat("FrostFilm", (0.93, 0.94, 0.95), rough=0.55, alpha=0.62)
    fy = 2.8295
    for i, (xa, xb) in enumerate(leaves):
        objs.append(_plane(c, hall, f"OppFrostBand_{i}", xb - xa - 0.01, 0.28, frost, ((xa + xb) / 2, fy, 1.34)))
    dy = 2.8270  # stickers 2.5 mm in front of the band, 4 mm in front of glass
    objs.append(_plane(c, hall, "OppVinyl_LettersL", 0.60, 0.13, _decal_mat("eroom_letters", rough=0.35), (-0.42, dy, 1.70)))
    objs.append(_plane(c, hall, "OppVinyl_LettersR", 0.60, 0.13, _decal_mat("eroom_letters", rough=0.35), (0.32, dy, 1.70)))
    objs.append(_plane(c, hall, "OppSticker_Hours", 0.20, 0.26, _decal_mat("eroom_hours", rough=0.3), (0.40, dy, 1.36)))
    objs.append(_plane(c, hall, "OppSticker_CCTV", 0.15, 0.10, _decal_mat("cctv_sticker", rough=0.3), (-0.50, dy, 1.42)))
    objs.append(_plane(c, hall, "OppSticker_QR", 0.10, 0.13, _decal_mat("qr_sticker", rough=0.3), (-0.66, dy, 1.30)))
    objs.append(_plane(c, hall, "OppSticker_Card", 0.20, 0.09, _decal_mat("card_sticker", rough=0.3), (0.40, dy, 0.80)))
    objs.append(_plane(c, hall, "OppVinyl_Phone", 0.42, 0.10, _decal_mat("eroom_phone", rough=0.35), (-0.45, dy, 0.62)))
    for i, hx in enumerate((-0.25, 0.15)):
        objs.append(_plane(c, hall, f"OppSticker_Push_{i}", 0.055, 0.12, _decal_mat("push_sticker", rough=0.3), (hx, dy, 1.27)))


def build_vacant_shop(c, hall, steel, objs):
    """Vacant 303호 (hallway extension x -7.50 .. -4.85): glass papered over from the hall side with kraft,
    newsprint and white sheets taped at the corners (ref 128/135), a big 임대문의 phone sheet, taped notices,
    and a pair of long pull handles that mark the right bay as the shop door."""
    py = 2.8335   # paper plane (glass hall face 2.840, existing 임대문의 banner at 2.825)
    tape = _pmat("MaskingTape", (0.80, 0.74, 0.58), rough=0.7)
    bays = ((-7.472, -6.207), (-6.152, -4.877))
    zlo, zhi = 0.140, 2.135
    rng = random.Random(303)
    kinds = ["paper_kraft", "paper_news", "paper_white"]
    n = 0
    for b, (xa, xb) in enumerate(bays):
        cols = 2
        rows = 2
        cw = (xb - xa - 0.012) / cols
        rh = (zhi - zlo - 0.012) / rows
        for ci in range(cols):
            for ri in range(rows):
                # leave the top-left sheet off in bay 2 so the frosted glass shows through (half-papered look)
                if b == 1 and ci == 0 and ri == 1:
                    continue
                k = kinds[(ci + ri * 2 + b) % 3]
                w = cw - 0.010 - rng.uniform(0.0, 0.03)
                h = rh - 0.010 - rng.uniform(0.0, 0.05)
                x = xa + 0.006 + cw * (ci + 0.5) + rng.uniform(-0.008, 0.008)
                z = zlo + 0.006 + rh * (ri + 0.5) + rng.uniform(-0.01, 0.01)
                objs.append(_plane(c, hall, f"VacPaper_{b}{ci}{ri}", w, h, _decal_mat(k, rough=0.88, alpha=False, spec=0.25), (x, py, z),
                                   tilt=rng.uniform(-0.6, 0.6)))
                # masking-tape strips on the corners, 2 mm in front of the paper
                for sx in (-1, 1):
                    for sz in (-1, 1):
                        n += 1
                        objs.append(_plane(c, hall, f"VacTape_{b}{ci}{ri}_{sx}{sz}", 0.065, 0.022, tape,
                                           (x + sx * (w / 2 - 0.045), py - 0.002, z + sz * (h / 2 - 0.012)), tilt=sx * sz * 40))
    # 임대문의 phone sheet (A2) and taped A4/A5 notices on the door bay, 4 mm in front of the paper
    ny = py - 0.004
    sheets = (("VacLeaseSheet", "lease_sheet", 0.42, 0.594, (-5.82, ny, 1.38), 1.5),
              ("VacNoticeMgmt", "notice_mgmt", 0.21, 0.297, (-5.20, ny, 1.52), -2.0),
              ("VacNoticePower", "notice_power", 0.21, 0.297, (-5.17, ny, 1.17), 1.0),
              ("VacNoticeMail", "notice_mail", 0.21, 0.148, (-6.88, ny, 0.78), -1.5))
    for nm, key, w, h, loc, tilt in sheets:
        objs.append(_plane(c, hall, nm, w, h, _decal_mat(key, rough=0.8, alpha=False, spec=0.3), loc, tilt=tilt))
        for sx in (-1, 1):
            t = math.radians(tilt)
            ox, oz = sx * (w / 2 - 0.03), h / 2 - 0.006
            rx = ox * math.cos(t) + oz * math.sin(t)
            rz = -ox * math.sin(t) + oz * math.cos(t)
            objs.append(_plane(c, hall, f"{nm}_tape{sx}", 0.07, 0.024, tape, (loc[0] + rx, ny - 0.002, loc[2] + rz), tilt=tilt + sx * 12))
    # Long stainless pull handles on the door bay (meeting line at x = -5.51)
    for i, hx in enumerate((-5.585, -5.435)):
        _pull_handle(c, hall, f"VacHandle_{i}", hx, 2.786, 2.840, 0.80, 1.42, steel, objs)


def build_mats(c, hall, objs):
    gym_m = _decal_mat("mat_gym", rough=0.92, alpha=False, spec=0.2)
    her_m = _decal_mat("mat_herring", rough=0.95, alpha=False, spec=0.15)
    # gym door mat starts after the floor-hinge plates (y 0.126..0.326)
    objs.append(_slab(c, hall, "Mat_GymEntrance", 1.30, 0.60, 0.011, 0.008, gym_m, (0.0, 0.66, 0.0005)))
    # academy door mat in front of the granite plinth (plinth face y = 2.78)
    objs.append(_slab(c, hall, "Mat_Academy", 1.30, 0.55, 0.010, 0.008, her_m, (-0.06, 2.48, 0.0005), rot_z=1.2))


def build_umbrella_stand(c, hall, steel, objs):
    """Stainless umbrella stand beside the gym door (ref 132), with a navy and a clear convenience-store umbrella."""
    root_loc = (1.08, 0.32, 0.0)
    r_out, h = 0.105, 0.52
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=r_out, radius2=r_out, depth=h)
    bottom = [e for e in bm.edges if all(v.co.z < -h / 2 + 1e-4 for v in e.verts)]
    bmesh.ops.edgeloop_fill(bm, edges=bottom)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    body = _bm_obj(c, hall, "Umbrella_StandBody", bm, steel, (root_loc[0], root_loc[1], h / 2 + 0.022), smooth=True)
    sol = body.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.0025
    sol.offset = -1.0
    _auto_smooth(body, 50)
    objs.append(body)
    black = _pmat("BlackPlastic", (0.02, 0.02, 0.022), rough=0.45)
    objs.append(_cyl(c, hall, "Umbrella_StandBase", r_out + 0.008, 0.022, black, (root_loc[0], root_loc[1], 0.0115), seg=32))
    objs.append(_cyl(c, hall, "Umbrella_StandTray", r_out - 0.006, 0.004, black, (root_loc[0], root_loc[1], 0.026), seg=24, smooth=False))
    # rolled rim as a bevelled circle curve
    cu = bpy.data.curves.new(P + "Umbrella_StandRim", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.004
    cu.bevel_resolution = 2
    sp = cu.splines.new("NURBS")
    pts = [(r_out * math.cos(a), r_out * math.sin(a), 0) for a in [i * 2 * math.pi / 16 for i in range(16)]]
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1.0)
    sp.use_cyclic_u = True
    sp.order_u = 3
    cu.materials.append(steel)
    rim_ob = bpy.data.objects.new(P + "Umbrella_StandRim", cu)
    rim_ob.location = (root_loc[0], root_loc[1], h + 0.022)
    _link(rim_ob, c, hall)
    objs.append(rim_ob)

    navy = _pmat("UmbrellaNavy", (0.03, 0.05, 0.12), rough=0.55)
    clear = _pmat("UmbrellaClearVinyl", (0.90, 0.93, 0.95), rough=0.18, alpha=0.38)
    shaft_m = _pmat("UmbrellaShaft", (0.55, 0.56, 0.58), rough=0.3, metal=0.9)
    hand_m = _pmat("UmbrellaHandle", (0.06, 0.05, 0.045), rough=0.4)
    for i, (dx, dy, lean_x, lean_y, cm) in enumerate(((-0.03, 0.02, -7, -4, navy), (0.035, -0.025, -9, 6, clear))):
        root = bpy.data.objects.new(P + f"Umbrella_{i}", None)
        root.location = (root_loc[0] + dx, root_loc[1] + dy, 0.03)
        root.rotation_euler = (math.radians(lean_x), math.radians(lean_y), math.radians(30 * i))
        _link(root, c, hall)
        objs.append(root)
        objs.append(_cyl(c, root, f"Umbrella_{i}_tip", 0.004, 0.06, shaft_m, (0, 0, 0.03), seg=8))
        objs.append(_cyl(c, root, f"Umbrella_{i}_canopy", 0.010, 0.56, cm, (0, 0, 0.34), seg=8, r2=0.034, smooth=False))
        objs.append(_cyl(c, root, f"Umbrella_{i}_strap", 0.036, 0.03, cm, (0, 0, 0.52), seg=8, smooth=False))
        objs.append(_cyl(c, root, f"Umbrella_{i}_shaft", 0.0055, 0.24, shaft_m, (0, 0, 0.73), seg=8))
        pts = [(0, 0, 0.84), (0, 0, 0.88)] + [(0.03 - 0.03 * math.cos(a), 0, 0.88 + 0.03 * math.sin(a)) for a in [k * math.pi / 6 for k in range(1, 7)]]
        objs.append(_tube_curve(c, root, f"Umbrella_{i}_handle", pts, 0.009, hand_m))


def build_aboard(c, hall, objs):
    """Stand-up A-board (입간판) for 루나 음악교습소 beside its vinyl panel (opposite wall, x 1.85..3.07)."""
    root = bpy.data.objects.new(P + "ABoard", None)
    root.location = (2.62, 2.43, 0.0)
    root.rotation_euler = (0, 0, math.radians(-14))
    _link(root, c, hall)
    objs.append(root)
    frame = _pmat("ABoardFrame", (0.025, 0.026, 0.03), rough=0.42, metal=0.55)
    H, Wd, splay = 0.86, 0.50, math.radians(13)
    for s, key in ((-1, "aboard_front"), (1, "aboard_back")):
        leaf = bpy.data.objects.new(P + f"ABoard_leaf{s}", None)
        leaf.location = (0, 0, H)
        leaf.rotation_euler = (s * splay, 0, 0)
        _link(leaf, c, root)
        objs.append(leaf)
        # leaf hangs down from the hinge (local -Z), outer face towards s*Y
        objs.append(_box(c, leaf, f"ABoard_panel{s}", (Wd, 0.012, H - 0.02), frame, (0, s * 0.008, -(H - 0.02) / 2 - 0.01), bevel=0.004))
        face = _plane(c, leaf, f"ABoard_poster{s}", 0.44, 0.74, _decal_mat(key, rough=0.3, alpha=False, coat=0.5),
                      (0, s * 0.0155, -0.45), face="+Y" if s > 0 else "-Y")
        objs.append(face)
        for fx in (-1, 1):
            objs.append(_box(c, leaf, f"ABoard_foot{s}{fx}", (0.04, 0.03, 0.02), _pmat("BlackPlastic", (0.02, 0.02, 0.022), rough=0.45),
                             (fx * (Wd / 2 - 0.03), s * 0.008, -(H - 0.012) / math.cos(splay) + 0.0), bevel=0.003))
    objs.append(_cyl(c, root, "ABoard_hinge", 0.008, Wd + 0.01, frame, (0, 0, H + 0.002), rot=(0, 90, 0), seg=12))


# ---------------------------------------------------------------- main
def _clear_collection(col):
    for ob in list(col.all_objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and getattr(data, "users", 1) == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)


def _tri_count(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return 0
    if me is None:
        return 0
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    ev.to_mesh_clear()
    return n


def apply() -> dict:
    if not os.path.exists(os.path.join(PART_DIR, "lease_sheet.png")):
        raise RuntimeError("decal textures missing: run ~/.venvs/pdf/bin/python promo/tools/detail_hall_storefronts.py --gen")
    W = _W()
    set_coll = bpy.data.collections["SET"]
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
    if c.name not in set_coll.children:
        set_coll.children.link(c)
    _clear_collection(c)
    hall = bpy.data.objects["Sangga_Hallway"]

    steel = _brushed_steel()
    glass = _clear_glass()
    objs = []
    build_gym_entrance(c, hall, steel, objs)
    build_opposite_doors(c, hall, steel, glass, objs)
    build_vacant_shop(c, hall, steel, objs)
    build_mats(c, hall, objs)
    build_umbrella_stand(c, hall, steel, objs)
    build_aboard(c, hall, objs)
    for ob in c.objects:
        ob["detail_pkg"] = KEY
    bpy.context.view_layer.update()
    tris = sum(_tri_count(o) for o in c.objects if o.type in ("MESH", "CURVE"))
    return {"collection": COLL, "objects_added": len(c.objects), "triangles_added": tris, "existing_objects_touched": []}


if __name__ == "__main__" and bpy is None:
    if "--gen" in sys.argv:
        generate_textures()
