"""Generate lightweight JPEG textures for extended Korean sangga hallway details."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "parts", "sangga_elev"))
os.makedirs(OUT, exist_ok=True)
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def font(size, idx=6):
    try:
        return ImageFont.truetype(FONT_PATH, size, index=idx)
    except Exception:
        return ImageFont.load_default()


def save_jpg(im, name, quality=84):
    path = os.path.join(OUT, name)
    im.convert("RGB").save(path, "JPEG", quality=quality, optimize=True)
    print(f"Wrote {name}: {im.size}, {os.path.getsize(path)//1024}KB")


# 1) Sangga Bulletin Board (4 slightly uneven Korean A4 notices on dark gray felt board)
def make_bulletin():
    im = Image.new("RGB", (640, 440), (54, 58, 64))
    d = ImageDraw.Draw(im)
    # Header strip
    d.rectangle([0, 0, 640, 46], fill=(32, 62, 112))
    d.text((22, 10), "3층 상가 관리사무소 공지사항", font=font(24, 7), fill=(255, 255, 255))

    notices = [
        (24, 64, 158, 228, (205, 42, 42), "엘리베이터 정기점검", ["일시: 매월 셋째주 수요일", "시간: 13:00 ~ 15:00", "점검 중 계단 이용 부탁", "- 상가 관리사무소 -"]),
        (178, 68, 314, 232, (28, 92, 175), "지하주차장 무료주차", ["상가 이용객 2시간 무료", "각 매장 인포에서 차량등록", "미등록 시 10분당 1,000원", "문의: 관리실 02-555-0100"]),
        (334, 62, 470, 226, (215, 115, 20), "건물 내 금연 안내", ["복도·계단·화장실 전체", "절대 금연구역입니다.", "적발 시 과태료 10만원", "1층 외부 흡연부스 이용"]),
        (488, 66, 616, 230, (42, 125, 72), "분리수거 및 청소", ["일반쓰레기·재활용 분리", "복도 적치물 방치 금지", "상가 청결에 협조 바랍니다", "감사합니다."]),
        (28, 252, 210, 412, (48, 52, 62), "3층 입점 안내", ["301호  이룸영어교습소", "302호  워치코치 짐 (헬스)", "303호  임대문의", "304호  소리피아노학원"]),
        (232, 256, 424, 414, (178, 38, 38), "동파 및 화재 예방", ["비상구 앞 물건 적치 엄금", "퇴근 시 전열기구 차단", "비상연락: 010-1234-5678"]),
        (444, 250, 616, 412, (28, 108, 158), "관리비 납부 안내", ["납부기한: 매월 말일", "자동이체 신청 관리실 문의", "미납 시 연체료 부과"]),
    ]
    for x0, y0, x1, y1, col, title, lines in notices:
        d.rectangle([x0 + 3, y0 + 3, x1 + 3, y1 + 3], fill=(32, 35, 40))
        d.rectangle([x0, y0, x1, y1], fill=(246, 245, 240), outline=(195, 195, 190))
        d.rectangle([x0, y0, x1, y0 + 28], fill=col)
        d.text((x0 + 8, y0 + 5), title, font=font(14, 7), fill=(255, 255, 255))
        # Red/blue pushpin dot at top center
        mx = (x0 + x1) // 2
        d.ellipse([mx - 5, y0 - 4, mx + 5, y0 + 6], fill=(220, 45, 45))
        for i, ln in enumerate(lines):
            d.text((x0 + 8, y0 + 38 + i * 24), ln, font=font(12, 5), fill=(35, 38, 42))
    save_jpg(im, "sangga_bulletin.jpg")


# 2) WatchCoach Gym Directional Poster (left arrow '←' points to +X gym entrance when mounted on Y=0 wall!)
def make_gym_dir_poster():
    im = Image.new("RGB", (400, 580), (20, 24, 32))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 400, 12], fill=(0, 200, 210))
    d.rectangle([0, 568, 400, 580], fill=(0, 200, 210))
    d.text((34, 42), "3F  302호", font=font(30, 7), fill=(0, 215, 225))
    d.text((34, 88), "WATCHCOACH", font=font(44, 8), fill=(255, 255, 255))
    d.text((34, 146), "워치코치 짐", font=font(52, 8), fill=(255, 255, 255))
    d.rectangle([34, 222, 366, 226], fill=(60, 72, 88))
    # Big crisp LEFT arrow pointing toward the gym door (+X)
    d.polygon([(52, 305), (140, 252), (140, 282), (348, 282), (348, 328), (140, 328), (140, 358)], fill=(0, 215, 225))
    d.text((155, 290), "입구 바로 앞", font=font(26, 8), fill=(15, 22, 30))
    # Promo badge
    d.rounded_rectangle([34, 392, 366, 518], radius=14, fill=(32, 38, 50), outline=(0, 200, 210), width=3)
    d.text((54, 408), "신규 회원 오픈 이벤트", font=font(24, 7), fill=(255, 215, 65))
    d.text((54, 446), "• 12개월 등록 시 월 2.9만~", font=font(20, 6), fill=(235, 240, 245))
    d.text((54, 478), "• 무료 인바디 · 1회 체험 가능", font=font(20, 6), fill=(185, 225, 230))
    d.text((54, 534), "상담문의 02-555-3020", font=font(18, 6), fill=(160, 170, 182))
    save_jpg(im, "gym_dir_poster.jpg")


# 3) Fire door sticker
def make_fire_door_sticker():
    im = Image.new("RGB", (320, 220), (248, 248, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([8, 8, 312, 212], outline=(205, 32, 32), width=8)
    d.rectangle([8, 8, 312, 76], fill=(205, 32, 32))
    d.text((52, 22), "방 화 문", font=font(42, 8), fill=(255, 255, 255))
    d.text((34, 96), "항상 닫아두세요", font=font(32, 8), fill=(25, 25, 28))
    d.text((38, 146), "화재 시 연기·화염 차단", font=font(20, 6), fill=(95, 95, 100))
    d.text((56, 176), "KEEP FIRE DOOR CLOSED", font=font(14, 6), fill=(120, 120, 125))
    save_jpg(im, "fire_door_sticker.jpg")


# 4) CCTV & No Smoking sticker
def make_cctv_nosmoke():
    im = Image.new("RGB", (280, 360), (250, 250, 250))
    d = ImageDraw.Draw(im)
    d.rectangle([6, 6, 274, 172], fill=(26, 72, 148))
    d.text((46, 28), "CCTV 작동중", font=font(30, 8), fill=(255, 255, 255))
    d.text((38, 76), "24시간 녹화·감시 중", font=font(20, 6), fill=(220, 235, 255))
    d.text((52, 118), "범죄 예방 및 시설 안전", font=font(16, 5), fill=(190, 215, 245))
    d.rectangle([6, 184, 274, 354], fill=(205, 36, 36))
    d.text((52, 206), "금 연 구 역", font=font(32, 8), fill=(255, 255, 255))
    d.text((38, 256), "건물 내 절대 금연", font=font(22, 7), fill=(255, 235, 120))
    d.text((42, 298), "위반 시 과태료 10만원", font=font(18, 6), fill=(255, 245, 245))
    save_jpg(im, "cctv_nosmoke.jpg")


# 5) Projecting Lightbox Signs (512x220)
def make_sign(name, bg, bar_col, title, sub, title_col=(255, 255, 255), sub_col=(230, 235, 240)):
    im = Image.new("RGB", (512, 220), bg)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 512, 28], fill=bar_col)
    d.rectangle([0, 192, 512, 220], fill=bar_col)
    d.text((36, 54), title, font=font(56, 8), fill=title_col)
    d.text((40, 130), sub, font=font(28, 6), fill=sub_col)
    save_jpg(im, name)


# 6) Wet Floor A-Frame Sign
def make_wet_floor():
    im = Image.new("RGB", (320, 480), (242, 198, 22))
    d = ImageDraw.Draw(im)
    d.rectangle([14, 14, 306, 466], outline=(24, 24, 24), width=8)
    # Warning triangle
    d.polygon([(160, 56), (72, 206), (248, 206)], fill=(242, 198, 22), outline=(205, 28, 28), width=12)
    d.text((146, 98), "!", font=font(86, 8), fill=(24, 24, 24))
    d.text((48, 238), "미끄럼 주의", font=font(44, 8), fill=(22, 22, 24))
    d.rectangle([38, 308, 282, 356], fill=(22, 22, 24))
    d.text((64, 316), "CAUTION", font=font(30, 8), fill=(242, 198, 22))
    d.text((66, 376), "WET FLOOR", font=font(28, 7), fill=(22, 22, 24))
    d.text((64, 418), "바닥 청소 중입니다", font=font(20, 6), fill=(48, 48, 50))
    save_jpg(im, "wet_floor.jpg")


if __name__ == "__main__":
    make_bulletin()
    make_gym_dir_poster()
    make_fire_door_sticker()
    make_cctv_nosmoke()
    make_sign("sign_derma.jpg", (252, 242, 245), (225, 118, 148), "더맑은 피부과", "5F  여드름 · 리프팅 · 제모", (42, 34, 38), (155, 65, 92))
    make_sign("sign_dental.jpg", (242, 248, 255), (42, 118, 202), "바른 치과의원", "4F  임플란트 · 투명교정", (22, 42, 72), (48, 108, 175))
    make_sign("sign_watchcoach.jpg", (20, 26, 34), (0, 200, 210), "워치코치 짐", "302호  헬스 · PT · 24시", (255, 255, 255), (0, 215, 225))
    make_wet_floor()
