"""Generate ultra-lightweight Korean clinic corridor vinyl sheet (시트지) & hanging no-smoking sign textures."""
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


# 1) Full-width sleek metallic-gray clinic vinyl sheet band (directly copying left wall of reference photo!)
def make_clinic_facade_sheet():
    W, H = 960, 380
    im = Image.new("RGB", (W, H), (168, 170, 172))
    d = ImageDraw.Draw(im)
    # Subtle top & bottom dark trim hairlines
    d.rectangle([0, 0, W, 5], fill=(118, 122, 126))
    d.rectangle([0, H - 5, W, H], fill=(118, 122, 126))

    # Left section: 진료시간 (rounded dark pill + neat schedule)
    d.rounded_rectangle([38, 62, 152, 102], radius=18, fill=(58, 52, 54))
    d.text((56, 70), "진료시간", font=font(21, 8), fill=(248, 248, 248))

    hours = [
        ("평    일", "오전 09:30 ~ 오후 08:30"),
        ("토 요 일", "오전 09:30 ~ 오후 03:00"),
        ("점심시간", "오후 01:00 ~ 오후 02:00"),
        ("야간진료", "매주 화 · 목 오후 08:30"),
    ]
    for i, (k, v) in enumerate(hours):
        y = 66 + i * 38
        d.text((168, y), k, font=font(17, 7), fill=(48, 48, 52))
        d.text((238, y), v, font=font(17, 5), fill=(58, 60, 64))
    d.text((168, 248), "일요일 · 공휴일 휴진", font=font(16, 7), fill=(152, 52, 58))
    d.text((168, 286), "예약 및 상담  02-555-1234", font=font(17, 7), fill=(44, 48, 54))

    # Vertical subtle divider
    d.line([(450, 48), (450, 332)], fill=(140, 144, 148), width=2)

    # Right 3 specialty columns with colored pill headers (exact reference photo rhythm!)
    cols = [
        (482, (42, 86, 152), "피부·레이저", ["• 여드름 · 흉터 집중치료", "• 슈링크 리프팅 · 탄력", "• 보톡스 · 필러 · 스킨부스터", "• 아쿠아필 · LED 진정관리", "• 남성 수염 레이저 제모"]),
        (648, (54, 112, 168), "치과·임플란트", ["• 네비게이션 임플란트", "• 투명교정 · 부분교정", "• 충치 · 신경 · 잇몸치료", "• 사랑니 당일 발치", "• 스케일링 · 치아미백"]),
        (812, (62, 128, 138), "비만·체형클리닉", ["• 인바디 정밀 체성분 분석", "• 비만 약물 · 주사 처방", "• 수액 · 비타민 영양클리닉", "• 3F 워치코치 짐 제휴할인"]),
    ]
    for cx, col, title, items in cols:
        d.rounded_rectangle([cx, 62, cx + 128, 96], radius=14, fill=col)
        d.text((cx + 12, 69), title, font=font(17, 8), fill=(255, 255, 255))
        for j, it in enumerate(items):
            d.text((cx + 2, 118 + j * 36), it, font=font(13, 6), fill=(246, 248, 250))

    save_jpg(im, "clinic_facade_sheet.jpg", quality=84)


# 2) Hanging dark-green ceiling No-Smoking sign (exact center ceiling sign of reference photo!)
def make_ceil_nosmoke():
    W, H = 480, 180
    im = Image.new("RGB", (W, H), (22, 54, 46))
    d = ImageDraw.Draw(im)
    d.rectangle([8, 8, W - 8, H - 8], outline=(62, 108, 94), width=3)
    d.text((34, 34), "본 병의원은", font=font(30, 7), fill=(235, 240, 238))
    d.text((196, 30), "금연", font=font(36, 8), fill=(245, 212, 68))
    d.text((274, 34), "장소입니다.", font=font(30, 7), fill=(235, 240, 238))
    d.text((48, 94), "금연장소에서는 절대로 담배를 피우지 맙시다.", font=font(18, 6), fill=(195, 215, 208))
    d.text((168, 134), "워치코치 플라자 관리단", font=font(16, 6), fill=(165, 192, 184))
    save_jpg(im, "ceil_nosmoke_hanging.jpg", quality=84)


if __name__ == "__main__":
    make_clinic_facade_sheet()
    make_ceil_nosmoke()
