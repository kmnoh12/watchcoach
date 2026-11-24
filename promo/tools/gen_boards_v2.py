"""Generate lightweight JPEG textures for:
1) Large Korean sangga Floor Directory (Photo 1 'INFORMATION' style with our building's exact tenants)
2) 4 Top-row A4 management notices (packed into 1 tiny strip) + yellow English flyer + yellow No-Smoking sign
(Bottom-row gym posters reuse existing packed student_discount.jpg and training.jpg in scene_gym.blend for 0 extra bytes!)"""
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


# 1) Large Floor Directory (Photo 1 'INFORMATION' design)
def make_floor_directory():
    W, H = 760, 480
    im = Image.new("RGB", (W, H), (236, 238, 240))
    d = ImageDraw.Draw(im)

    # Top black INFORMATION banner (right of left floor badge column)
    d.rectangle([108, 18, W - 16, 62], fill=(18, 20, 24))
    d.text((312, 26), "I N F O R M A T I O N", font=font(24, 6), fill=(242, 244, 248))
    d.text((572, 30), "워치코치 플라자 상가", font=font(17, 7), fill=(210, 215, 222))

    # Floor definitions: (label, y0, y1, rows_of_shops)
    floors = [
        ("5층", 74, 128, [
            [("501", "더맑은 피부과", "555-1234"), ("502", "하늘정형외과", "555-5020"), ("503", "세무법인 대명", "555-5030"), ("504", "공실 (임대)", "010-2345"), ("505", "법무사 김철수", "555-5050")],
        ]),
        ("4층", 136, 190, [
            [("401", "바른치과의원", "555-4010"), ("402", "연세소아과", "555-4020"), ("403", "나은약국", "555-4030"), ("404", "글로우 필라테스", "555-4040"), ("405", "하늘내과의원", "555-4050")],
        ]),
        ("3층", 198, 252, [
            [("301", "이룸영어교습소", "555-3010"), ("302", "워치코치 짐", "555-3020"), ("303", "임대문의", "010-2345"), ("304", "소리피아노학원", "555-3040"), ("305", "에이스수학학원", "555-3050")],
        ]),
        ("2층", 260, 314, [
            [("201", "워치코치 골프", "555-2010"), ("202", "신동태권도", "555-2020"), ("203", "하나은행", "555-2030"), ("204", "헤어1번지", "555-2040"), ("205", "네일올리브", "555-2050")],
        ]),
        ("1층", 322, 412, [
            [("101", "GS25 편의점", "555-1010"), ("102", "메가커피", "555-1020"), ("103", "황금부동산", "555-1030"), ("104", "명품세탁소", "555-1040"), ("105", "파리바게뜨", "555-1050")],
            [("106", "왕만두", "555-1060"), ("107", "김밥천국", "555-1070"), ("108", "올리브안경", "555-1080"), ("109", "다이소 미니", "555-1090"), ("110", "우리은행 ATM", "555-1100")],
        ]),
        ("B1", 420, 462, [
            [("B01", "오퍼스 마트", "555-0010"), ("B02", "관리사무소", "555-0100"), ("B03", "지하주차장", "2시간 무료")],
        ]),
    ]

    for label, y0, y1, rows in floors:
        # Rounded black floor pill on left (exact Photo 1!)
        d.rounded_rectangle([18, y0, 96, y1], radius=10, fill=(20, 22, 26))
        cy = (y0 + y1) // 2 - 12
        lx = 38 if len(label) == 2 else 32
        d.text((lx, cy), label, font=font(22, 8), fill=(246, 248, 250))

        # Horizontal subtle divider under floor group
        d.line([(106, y1 + 4), (W - 16, y1 + 4)], fill=(208, 212, 218), width=1)

        row_h = (y1 - y0) // len(rows)
        for r_idx, row in enumerate(rows):
            ry0 = y0 + r_idx * row_h + 2
            ry1 = ry0 + row_h - 4
            col_w = (W - 128) // 5
            for c_idx, (room, name, tel) in enumerate(row):
                cx0 = 110 + c_idx * col_w
                cx1 = cx0 + col_w - 6
                # Subtle white plaque with crisp gray border (highlight 302 워치코치 짐 slightly)
                bg = (232, 248, 250) if "워치코치" in name else (248, 249, 250)
                border = (145, 152, 160)
                d.rectangle([cx0, ry0, cx1, ry1], fill=bg, outline=border, width=1)
                # Room number tiny tag on left
                d.rectangle([cx0, ry0, cx0 + 24, ry1], fill=(224, 228, 232), outline=border, width=1)
                d.text((cx0 + 3, ry0 + (ry1 - ry0) // 2 - 6), room, font=font(9, 6), fill=(65, 70, 78))
                # Shop name + phone
                d.text((cx0 + 28, ry0 + 4), name, font=font(13, 8), fill=(25, 28, 34))
                d.text((cx0 + 28, ry0 + 22), tel, font=font(10, 5), fill=(95, 102, 112))

    save_jpg(im, "floor_directory_big.jpg", quality=85)


# 2) Top-row 4 Korean management office A4 notices (240x340 each, lightweight!)
def make_a4_notice(fname, header_col, title, bullets):
    im = Image.new("RGB", (240, 340), (246, 246, 244))
    d = ImageDraw.Draw(im)
    d.rectangle([14, 16, 226, 48], fill=header_col)
    d.text((22, 23), title, font=font(15, 8), fill=(255, 255, 255))
    d.line([(14, 56), (226, 56)], fill=(180, 184, 190), width=1)
    y = 68
    for b in bullets:
        d.text((18, y), b, font=font(11, 6), fill=(35, 38, 44))
        y += 22
    # Mini table grid for official apartment/sangga document look (exact Photo 2!)
    ty = 178
    d.rectangle([18, ty, 222, 286], outline=(145, 150, 158), width=1)
    d.rectangle([18, ty, 222, ty + 22], fill=(225, 228, 234), outline=(145, 150, 158))
    for r in range(1, 5):
        d.line([(18, ty + r * 22), (222, ty + r * 22)], fill=(180, 184, 190), width=1)
    d.line([(92, ty), (92, 286)], fill=(180, 184, 190), width=1)
    d.line([(158, ty), (158, 286)], fill=(180, 184, 190), width=1)
    d.text((54, 304), "워치코치 플라자 관리사무소", font=font(11, 7), fill=(48, 52, 60))
    # Tiny red official stamp square
    d.rectangle([194, 298, 214, 318], outline=(200, 42, 42), width=2)
    save_jpg(im, fname, quality=80)


# 3) Bottom-right bright yellow '원어민 영어' flyer (exact Photo 2!)
def make_yellow_flyer():
    im = Image.new("RGB", (240, 340), (242, 228, 62))
    d = ImageDraw.Draw(im)
    d.rectangle([14, 16, 226, 62], fill=(28, 42, 54))
    d.text((38, 24), "원어민 영어", font=font(28, 8), fill=(255, 245, 110))
    d.text((28, 76), "이룸영어교습소 301호", font=font(17, 8), fill=(28, 32, 36))
    lines = [
        "• 초·중·고 내신 완벽 대비",
        "• 1:1 소수정예 집중 케어",
        "• 원어민 회화 / 스피킹 반",
        "• 무료 레벨테스트 상시 진행",
        "• 형제·친구 동반 등록 할인",
    ]
    for i, ln in enumerate(lines):
        d.text((22, 118 + i * 28), ln, font=font(13, 6), fill=(32, 34, 38))
    d.rounded_rectangle([24, 272, 216, 322], radius=8, fill=(210, 38, 38))
    d.text((42, 286), "상담 02-555-3010", font=font(18, 8), fill=(255, 255, 255))
    save_jpg(im, "flyer_english_yellow.jpg", quality=82)


# 4) Yellow No-Smoking sticker beside bulletin board (exact Photo 2!)
def make_nosmoke_yellow():
    im = Image.new("RGB", (180, 240), (246, 204, 36))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 200, 180, 240], fill=(32, 34, 38))
    d.text((52, 16), "금 연", font=font(34, 8), fill=(208, 28, 28))
    d.text((30, 56), "No Smoking Area", font=font(15, 7), fill=(48, 36, 24))
    # Red prohibition circle + cigarette
    d.ellipse([48, 84, 132, 168], fill=(255, 255, 255), outline=(210, 28, 28), width=9)
    d.rectangle([66, 120, 116, 132], fill=(60, 60, 64))
    d.rectangle([104, 120, 116, 132], fill=(218, 128, 42))
    d.line([(62, 98), (118, 154)], fill=(210, 28, 28), width=8)
    d.text((24, 176), "위반 시 과태료 10만원", font=font(13, 7), fill=(36, 32, 28))
    d.text((38, 212), "워치코치 플라자", font=font(14, 7), fill=(242, 242, 242))
    save_jpg(im, "nosmoke_yellow.jpg", quality=82)


if __name__ == "__main__":
    make_floor_directory()
    make_a4_notice("notice_a4_1.jpg", (54, 62, 74), "관리비 납부 및 정산 안내", ["1. 납부기한: 매월 말일까지", "2. 자동이체 신청: 관리사무소", "3. 연체 시 가산금 2% 부과", "4. 영수증 발급: 1층 안내실"])
    make_a4_notice("notice_a4_2.jpg", (38, 82, 148), "엘리베이터 정기점검 안내", ["1. 점검일시: 매월 셋째 수요일", "2. 점검시간: 13:00 ~ 15:00", "3. 점검대상: 1호기 전체", "4. 점검 중 비상계단 이용"])
    make_a4_notice("notice_a4_3.jpg", (52, 108, 72), "지하주차장 무료주차 안내", ["1. 상가 이용객 2시간 무료", "2. 매장 인포에서 차량 등록", "3. 미등록 시 10분당 1,000원", "4. 월정기권 관리실 문의"])
    make_a4_notice("notice_a4_4.jpg", (152, 48, 48), "동파·화재 예방 안전 공고", ["1. 비상구 앞 물건 적치 금지", "2. 퇴근 시 전열기구 차단", "3. 복도 내 절대 금연 구역", "4. 비상연락: 02-555-0100"])
    make_yellow_flyer()
    make_nosmoke_yellow()
