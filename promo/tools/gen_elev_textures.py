"""Generate crisp Korean commercial sangga elevator hall & ad panel textures using Pillow."""
import os
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(REPO_ROOT, "promo", "parts", "sangga_elev")
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def font(size, index=6):
    # AppleSDGothicNeo.ttc: index 0=Regular, 5=Medium, 6=SemiBold, 7=Bold, 8=ExtraBold
    try:
        return ImageFont.truetype(FONT_PATH, size, index=index)
    except Exception:
        return ImageFont.truetype(FONT_PATH, size)


def save_img(img, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    img.save(path, "PNG")
    print("saved", path)


def _rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def _hydrant_icon(d, kind, box):
    """Tiny flat cartoon panels for the 4-step hydrant instructions (person, hose coil, valve, nozzle spray)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    skin, coat, helmet = (246, 214, 176), (232, 196, 58), (236, 206, 72)
    dark, hose_c = (52, 56, 64), (150, 156, 166)
    def person(px, py, s=1.0, arm_dx=40):
        d.ellipse([px - 26 * s, py - 92 * s, px + 26 * s, py - 42 * s], fill=skin, outline=dark, width=3)
        d.pieslice([px - 30 * s, py - 104 * s, px + 30 * s, py - 56 * s], 180, 360, fill=helmet, outline=dark, width=3)
        _rrect(d, [px - 30 * s, py - 44 * s, px + 30 * s, py + 30 * s], int(10 * s), fill=coat, outline=dark, width=3)
        d.line([px + 18 * s, py - 24 * s, px + arm_dx * s, py - 30 * s], fill=dark, width=int(12 * s))
        d.rectangle([px - 24 * s, py + 30 * s, px - 6 * s, py + 62 * s], fill=dark)
        d.rectangle([px + 6 * s, py + 30 * s, px + 24 * s, py + 62 * s], fill=dark)
    def coil(px, py, r):
        for k in range(4):
            rr = r - k * 13
            d.ellipse([px - rr, py - rr * 0.62, px + rr, py + rr * 0.62], outline=hose_c, width=9)
        d.ellipse([px - 22, py - 14, px + 22, py + 14], fill=(90, 96, 106))
    def hand(px, py):
        _rrect(d, [px - 52, py - 34, px + 46, py + 34], 30, fill=skin, outline=(170, 130, 96), width=4)
        for k in range(3):
            d.line([px - 30 + k * 24, py - 30, px - 30 + k * 24, py - 6], fill=(190, 150, 112), width=4)
    if kind == 1:
        person(x0 + 78, cy + 22, 0.95, 62)
        _rrect(d, [cx + 26, y0 + 26, x1 - 26, y1 - 26], 8, fill=(168, 172, 180), outline=dark, width=4)
        for k in range(5):
            d.line([cx + 40, y0 + 52 + k * 22, x1 - 40, y0 + 52 + k * 22], fill=(120, 124, 132), width=4)
        d.ellipse([cx + 54, y0 + 36, cx + 82, y0 + 64], fill=(214, 34, 34), outline=dark, width=3)
    elif kind in (2, 4):
        coil(cx + 20, cy, 76)
        hand(cx - 46, cy + (8 if kind == 2 else -6))
    else:
        flame = [(x0 + 40, cy + 60), (x0 + 26, cy), (x0 + 52, cy - 40), (x0 + 62, cy - 8), (x0 + 80, cy - 70),
                 (x0 + 104, cy - 6), (x0 + 120, cy - 30), (x0 + 128, cy + 60)]
        d.polygon(flame, fill=(236, 92, 28), outline=(180, 40, 20))
        d.polygon([(x0 + 58, cy + 56), (x0 + 60, cy + 10), (x0 + 82, cy - 20), (x0 + 100, cy + 20), (x0 + 110, cy + 56)],
                  fill=(252, 200, 60))
        for k in range(5):
            d.line([x0 + 150, cy - 4 + (k - 2) * 7, x0 + 138 - k * 3, cy - 4 + (k - 2) * 14], fill=(96, 170, 236), width=5)
        d.line([x0 + 150, cy - 4, x1 - 90, cy - 10], fill=(70, 74, 82), width=12)
        person(x1 - 64, cy + 22, 0.95, -44)


def make_hydrant_sticker():
    """'소화전 사용방법' 4-step white instruction sticker on the hydrant door (190 x 152 mm @ 8 px/mm)."""
    W, H = 1520, 1216
    img = Image.new("RGB", (W, H), (250, 250, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(196, 198, 202), width=6)
    # Title block
    _rrect(d, [48, 36, W - 48, 232], 26, fill=(255, 255, 255), outline=(150, 152, 158), width=5)
    title = "소화전  사용방법"
    tf = font(104, 14)
    tw = d.textlength(title, font=tf)
    d.text(((W - tw) / 2, 50), title, fill=(178, 28, 34), font=tf)
    sub = "Operation of Starting System Fire Wall Cabinet"
    sf = font(36, 6)
    d.text(((W - d.textlength(sub, font=sf)) / 2, 160), sub, fill=(40, 42, 48), font=sf)
    sub2 = "옥내소화전설비  ·  화재시 사용요령"
    sf2 = font(28, 2)
    d.text(((W - d.textlength(sub2, font=sf2)) / 2, 198), sub2, fill=(120, 122, 128), font=sf2)
    steps = [
        ("문을 열고 ", "발신기 누름버튼", "을 눌러 알린다",
         "Open the cabinet door and push the alarm button.", "화재경보가 울리고 펌프가 자동으로 기동됩니다."),
        ("소화전 ", "호스", "를 꺼내 불이 난 곳까지 펼친다",
         "Pull the hose out toward the fire without kinks.", "호스가 꼬이지 않도록 길게 펼쳐 주세요."),
        ("노즐을 잡고 ", "앵글밸브", "를 왼쪽으로 돌려 연다",
         "Hold the nozzle and turn the valve counterclockwise.", "두 사람이 함께 조작하면 더욱 안전합니다."),
        ("불을 향해 방수한 뒤 ", "소화전함 문", "을 닫는다",
         "Spray at the base of the fire, then close the cabinet.", "사용 후에는 관리사무소에 꼭 알려 주세요."),
    ]
    row_top, row_h, gap = 262, 222, 12
    kf, kfb, ef, jf = font(42, 6), font(42, 14), font(31, 2), font(29, 2)
    for i, (k1, kk, k2, en, k3) in enumerate(steps):
        y0 = row_top + i * (row_h + gap)
        y1 = y0 + row_h
        d.rectangle([48, y0, 196, y1], fill=(166, 40, 38))
        nf = font(176, 14)
        n = str(i + 1)
        d.text((122 - d.textlength(n, font=nf) / 2, y0 + 4), n, fill=(255, 255, 255), font=nf)
        _rrect(d, [206, y0, 1146, y1], 18, fill=(255, 255, 255), outline=(150, 152, 158), width=4)
        x = 230
        d.text((x, y0 + 24), k1, fill=(28, 44, 96), font=kf)
        x += d.textlength(k1, font=kf)
        d.text((x, y0 + 24), kk, fill=(196, 28, 34), font=kfb)
        x += d.textlength(kk, font=kfb)
        d.text((x, y0 + 24), k2, fill=(28, 44, 96), font=kf)
        d.text((230, y0 + 96), "• " + en, fill=(46, 48, 56), font=ef)
        d.text((230, y0 + 150), "• " + k3, fill=(96, 98, 106), font=jf)
        _rrect(d, [1160, y0, W - 48, y1], 18, fill=(255, 255, 255), outline=(150, 152, 158), width=4)
        _hydrant_icon(d, i + 1, (1160, y0, W - 48, y1))
    save_img(img, "hydrant_sticker.png")


def make_hydrant_nameplate(label="소화전 3번   1계통 32"):
    """Small red management-number plate in the top-right of the hydrant alarm panel (113 x 36 mm @ 12 px/mm)."""
    W, H = 1356, 432
    img = Image.new("RGB", (W, H), (226, 228, 230))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(168, 170, 176), width=8)
    d.rectangle([44, 52, W - 44, H - 52], fill=(232, 96, 102), outline=(176, 34, 44), width=10)
    f = font(118, 6)
    tw = d.textlength(label, font=f)
    d.text(((W - tw) / 2, (H - 118) / 2 - 20), label, fill=(150, 18, 30), font=f)
    save_img(img, "hydrant_nameplate.png")


def make_floor_guide():
    """Korean sangga blue-bar floor directory (층별안내) matching reference 1 & 2."""
    img = Image.new("RGB", (640, 380), (235, 237, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 108, 380], fill=(24, 104, 212))
    for i, ch in enumerate("층별안내"):
        d.text((28, 44 + i * 74), ch, fill=(255, 222, 60), font=font(56, 8))
    d.rectangle([108, 0, 640, 380], fill=(242, 244, 246), outline=(170, 174, 180), width=4)
    floors = [
        ("5F", "더맑은 피부과 · 성형외과 / 스터디카페"),
        ("4F", "이룸 치과의원 / 필라테스 스튜디오"),
        ("3F", "워치짐 피트니스 / 이룸하이 영어 / 피아노"),
        ("2F", "SG 스크린골프 / 수학전문학원 / 태권도"),
        ("1F", "편의점 / 부동산 / 약국 / 커피전문점"),
        ("B1", "오퍼스 마트 / 주차장"),
    ]
    for i, (fl, desc) in enumerate(floors):
        y = 26 + i * 56
        bg = (232, 240, 252) if fl == "3F" else (248, 249, 251)
        d.rectangle([126, y, 622, y + 46], fill=bg, outline=(200, 206, 214), width=2)
        d.text((140, y + 8), fl, fill=(24, 96, 200) if fl == "3F" else (45, 50, 58), font=font(28, 8))
        d.text((208, y + 10), desc, fill=(32, 36, 42), font=font(23, 6))
    save_img(img, "floor_guide.png")


def make_notice_orange():
    """Orange-bordered sangga elevator notice matching reference 1."""
    img = Image.new("RGB", (512, 340), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 504, 332], fill=(255, 255, 255), outline=(235, 92, 34), width=14)
    d.rounded_rectangle([104, 28, 408, 84], radius=24, fill=(34, 128, 228))
    d.text((134, 40), "상가 전용 엘리베이터", fill=(255, 255, 255), font=font(30, 8))
    d.text((48, 118), "상가 방문 고객님 전용입니다.", fill=(34, 36, 40), font=font(32, 7))
    d.text((48, 172), "지하 주차장 및 헬스장(3F) 이용 시", fill=(215, 65, 25), font=font(28, 7))
    d.text((48, 218), "본 엘리베이터를 이용해 주세요.", fill=(34, 36, 40), font=font(28, 6))
    d.text((48, 274), "※ 건물 내 금연 · 무단 전단지 부착 금지", fill=(110, 114, 120), font=font(21, 5))
    save_img(img, "notice_orange.png")


def make_derma_panel():
    """Cluttered Korean dermatology clinic wall ad panel (피부과 광고 판넬)."""
    img = Image.new("RGB", (512, 680), (248, 240, 244))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 512, 165], fill=(224, 72, 118))
    d.text((34, 24), "5F 더맑은 피부과의원", fill=(255, 255, 255), font=font(44, 8))
    d.text((38, 92), "여드름 · 리프팅 · 보톡스 · 제모", fill=(255, 232, 180), font=font(30, 7))
    items = [
        ("슈링크 리프팅 300샷", "9.9만", (255, 244, 248)),
        ("국산 턱보톡스 50U", "2.9만", (255, 255, 255)),
        ("아쿠아필 + LED 진정", "3.5만", (255, 244, 248)),
        ("남성 수염 레이저 제모", "4.9만", (255, 255, 255)),
    ]
    for i, (title, price, bg) in enumerate(items):
        y = 190 + i * 96
        d.rectangle([22, y, 490, y + 80], fill=bg, outline=(232, 165, 188), width=3)
        d.text((38, y + 22), title, fill=(40, 35, 42), font=font(28, 7))
        d.text((360, y + 18), price, fill=(220, 42, 92), font=font(36, 8))
    d.rectangle([0, 588, 512, 680], fill=(42, 34, 48))
    d.text((42, 610), "평일 야간진료 20:30 · 예약 02-555-1234", fill=(255, 255, 255), font=font(25, 6))
    save_img(img, "ad_derma.png")


def make_dental_panel():
    """Korean dental clinic wall ad panel (치과 광고 판넬)."""
    img = Image.new("RGB", (512, 420), (236, 246, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 512, 118], fill=(18, 98, 186))
    d.text((34, 22), "4F 이룸 치과의원", fill=(255, 255, 255), font=font(44, 8))
    d.text((38, 76), "임플란트 · 투명교정 · 스케일링", fill=(180, 228, 255), font=font(24, 6))
    d.rounded_rectangle([28, 144, 484, 232], radius=16, fill=(255, 255, 255), outline=(38, 132, 224), width=4)
    d.text((48, 166), "국산 정품 임플란트  59만원~", fill=(18, 86, 172), font=font(32, 8))
    d.rounded_rectangle([28, 252, 484, 336], radius=16, fill=(255, 246, 200), outline=(230, 168, 24), width=4)
    d.text((54, 274), "매주 화·목 야간진료 / 점심 1시", fill=(52, 46, 36), font=font(28, 7))
    d.text((40, 364), "엘리베이터 4층 하차 바로 우측", fill=(60, 74, 92), font=font(24, 6))
    save_img(img, "ad_dental.png")


def make_golf_xbanner():
    """Screen golf X-banner matching reference 1 right side."""
    img = Image.new("RGB", (480, 1200), (34, 118, 214))
    d = ImageDraw.Draw(img)
    # Gradient-like bands
    d.rectangle([0, 0, 480, 380], fill=(162, 198, 236))
    d.rectangle([0, 380, 480, 860], fill=(104, 168, 232))
    d.rectangle([0, 860, 480, 1200], fill=(22, 82, 178))
    d.text((95, 42), "2F SG GOLF", fill=(20, 62, 140), font=font(52, 8))
    d.text((36, 128), "스크린에 가면", fill=(255, 255, 255), font=font(58, 8))
    d.text((28, 202), "필드가 보인다!", fill=(255, 238, 88), font=font(64, 8))
    # Stylized golf ball + green fairway badge
    d.ellipse([110, 360, 370, 620], fill=(245, 248, 252), outline=(200, 210, 224), width=8)
    d.ellipse([130, 560, 350, 720], fill=(42, 172, 92))
    d.text((155, 460), "GOLF", fill=(24, 92, 185), font=font(62, 8))
    d.rounded_rectangle([38, 750, 442, 840], radius=24, fill=(255, 224, 48))
    d.text((70, 770), "오전 타임 1만원 특가!", fill=(22, 34, 58), font=font(38, 8))
    d.text((62, 910), "SG GOLF", fill=(255, 255, 255), font=font(76, 8))
    d.text((58, 1015), "스크린골프는 역시 2층!", fill=(195, 225, 255), font=font(36, 7))
    d.text((92, 1105), "예약 02-555-7788", fill=(255, 255, 255), font=font(32, 6))
    save_img(img, "xbanner_golf.png")


def make_mart_xbanner():
    """Basement mart X-banner matching reference 1 far-right navy/yellow banner."""
    img = Image.new("RGB", (480, 1200), (24, 44, 128))
    d = ImageDraw.Draw(img)
    d.rectangle([16, 16, 464, 1184], outline=(255, 214, 34), width=10)
    d.text((54, 56), "오퍼스", fill=(255, 224, 42), font=font(110, 8))
    d.text((54, 180), "마트", fill=(255, 224, 42), font=font(118, 8))
    d.text((48, 340), "위치: 지하1층(B1)", fill=(255, 255, 255), font=font(42, 7))
    d.text((48, 400), "엘리베이터 앞", fill=(255, 255, 255), font=font(42, 7))
    d.rounded_rectangle([38, 486, 442, 606], radius=18, fill=(255, 214, 34))
    d.text((64, 502), "영업시간", fill=(24, 38, 96), font=font(34, 8))
    d.text((56, 548), "오전07:50~새벽01:00", fill=(24, 38, 96), font=font(34, 8))
    items = ["담 배", "아이스커피", "야채 · 과일", "음료 · 닭가슴살", "아이스크림", "초특가 할인판매!"]
    for i, it in enumerate(items):
        col = (255, 226, 60) if i == len(items) - 1 else (245, 248, 255)
        d.text((56, 650 + i * 78), it, fill=col, font=font(46, 8))
    save_img(img, "xbanner_mart.png")


def make_for_lease():
    """Korean vacant sangga white paper '임대문의' sign."""
    img = Image.new("RGB", (640, 420), (250, 250, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([14, 14, 626, 406], outline=(210, 32, 32), width=12)
    d.text((76, 58), "임 대 문 의", fill=(210, 26, 26), font=font(108, 8))
    d.text((88, 218), "303호 (35평 · 즉시입주)", fill=(34, 36, 40), font=font(44, 7))
    d.text((92, 296), "010-2345-6789", fill=(22, 72, 180), font=font(60, 8))
    save_img(img, "for_lease.png")


def make_elev_stickers():
    """Elevator door safety stickers + '1호기' header plate + red LED '3'."""
    # Safety sticker (yellow/blue)
    img = Image.new("RGB", (256, 300), (248, 248, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 248, 292], outline=(40, 96, 195), width=8)
    d.rectangle([16, 16, 240, 82], fill=(248, 206, 32))
    d.text((48, 30), "손끼임 주의", fill=(28, 28, 32), font=font(32, 8))
    d.ellipse([68, 108, 188, 228], fill=(220, 40, 40), outline=(140, 18, 18), width=6)
    d.line([92, 132, 164, 204], fill=(255, 255, 255), width=12)
    d.text((42, 246), "문에 기대지 마세요", fill=(36, 40, 46), font=font(22, 7))
    save_img(img, "elev_sticker.png")

    # Header plate: 1호기 + red LED 3
    hdr = Image.new("RGB", (512, 160), (20, 22, 26))
    dh = ImageDraw.Draw(hdr)
    dh.rectangle([176, 10, 336, 68], fill=(32, 34, 38), outline=(190, 195, 200), width=4)
    dh.text((208, 18), "1호기", fill=(245, 248, 252), font=font(38, 8))
    dh.rectangle([0, 82, 512, 152], fill=(12, 13, 16))
    dh.text((238, 92), "3", fill=(255, 42, 32), font=font(52, 8))
    save_img(hdr, "elev_header_3f.png")


if __name__ == "__main__":
    make_hydrant_sticker()
    make_hydrant_nameplate()
    make_floor_guide()
    make_notice_orange()
    make_derma_panel()
    make_dental_panel()
    make_golf_xbanner()
    make_mart_xbanner()
    make_for_lease()
    make_elev_stickers()
