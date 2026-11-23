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


def make_hydrant():
    """Korean indoor fire hydrant cabinet (옥내소화전)."""
    img = Image.new("RGB", (512, 820), (218, 220, 224))
    d = ImageDraw.Draw(img)
    # Outer metallic bezel
    d.rectangle([8, 8, 504, 812], fill=(205, 208, 212), outline=(120, 124, 130), width=6)
    # Upper bell & indicator panel
    d.rectangle([28, 28, 484, 210], fill=(230, 232, 236), outline=(150, 154, 160), width=3)
    # Red fire bell circle (left) + red alarm lamp (right)
    d.ellipse([72, 56, 200, 184], fill=(196, 26, 26), outline=(120, 14, 14), width=5)
    d.ellipse([122, 106, 150, 134], fill=(230, 180, 180))
    d.ellipse([320, 74, 396, 150], fill=(225, 36, 36), outline=(110, 18, 18), width=4)
    d.text((314, 158), "발신기", fill=(40, 40, 44), font=font(26, 7))

    # Red hydrant title band
    d.rectangle([28, 230, 484, 340], fill=(195, 24, 28))
    d.text((92, 250), "옥내소화전", fill=(255, 255, 255), font=font(68, 8))

    # Lower door panel + instructions
    d.rectangle([28, 358, 484, 788], fill=(226, 228, 232), outline=(145, 148, 154), width=3)
    d.text((76, 405), "화재시 사용방법", fill=(185, 24, 28), font=font(42, 8))
    lines = [
        "1. 소화전 문을 열고 관창을 잡는다",
        "2. 호스를 화재 지점까지 펼친다",
        "3. 개폐밸브를 왼쪽으로 돌린다",
        "4. 노즐을 불을 향해 분사한다",
    ]
    for i, ln in enumerate(lines):
        d.text((54, 485 + i * 52), ln, fill=(45, 48, 52), font=font(28, 5))
    # Chrome door handle on right
    d.rectangle([420, 540, 456, 650], fill=(155, 160, 168), outline=(90, 94, 100), width=3)
    save_img(img, "hydrant_front.png")


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
    make_hydrant()
    make_floor_guide()
    make_notice_orange()
    make_derma_panel()
    make_dental_panel()
    make_golf_xbanner()
    make_mart_xbanner()
    make_for_lease()
    make_elev_stickers()
