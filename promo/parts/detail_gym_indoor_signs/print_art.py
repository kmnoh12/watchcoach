"""Rebuild the original typeset notices and mirror masks from the repository root with Pillow."""
from pathlib import Path
import math
import random
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "fonts"
SYSTEM = Path("/System/Library/Fonts/Supplemental")
KOREAN = FONTS / "NanumGothic-Bold.ttf"


def typeface(path, size):
    return ImageFont.truetype(str(path), size)


def save(im, name):
    im.save(HERE / name, quality=92, subsampling=0, optimize=True)


def mirror_notice():
    im = Image.new("RGB", (1188, 840), "#f6f4ee")
    draw = ImageDraw.Draw(im)
    draw.text((594, 64), "〈샤워장 수칙〉", font=typeface(KOREAN, 55), anchor="mt", fill="#242223")
    lines = ["샤워 중 오줌 싸고 태연한 척 하지 않기", "공용 바지 입을 때 팬티 입기", "샤워 후 물기 닦고 나오기",
             "샤워실에서 셀카는 자제하기", "드라이기로 대놓고 언더헤어 말리지 않기", "거울 오래 사용하지 않기",
             "사람 있을 때 거울보고 포징 연습하지 않기", "다른 사람 몸 아래위로 쳐다보지 않기", "봤어도 소문내지 않기"]
    for i, line in enumerate(lines):
        draw.text((97, 202+i*64), f"{i+1}.  {line}", font=typeface(KOREAN, 42), fill="#252325", anchor="lm")
    save(im, "A09_notice.jpg")


def achievement():
    from runpy import run_path
    run_path(str(HERE / "draw_award.py"))["achievement"]()


def mirror_lightboxes():
    # Reverse-engraved lettering in one mirror face. Both the diffuser and the viewport
    # swatch come from the same high-resolution, antialiased engraving master.
    for title, subtitle in [("MAN", "남자 탈의실"), ("WOMAN", "여자 탈의실")]:
        mask=Image.new("L",(1584,760),0)
        pen=ImageDraw.Draw(mask)
        pen.text((792,297),title,anchor="mm",font=typeface(SYSTEM/"Georgia Bold.ttf",165),fill=255)
        pen.text((792,433),"Fitting Room",anchor="mm",font=typeface(SYSTEM/"Georgia Bold.ttf",62),fill=255)
        pen.text((792,533),subtitle,anchor="mm",font=typeface(KOREAN,70),fill=255)
        mask.save(HERE/f"B03_{title}_inlay.png",optimize=True)
        preview=Image.composite(Image.new("RGB",mask.size,"#fff1d9"),
                                Image.new("RGB",mask.size,"#9d886e"),mask)
        save(preview,f"B03_{title}_face.jpg")

def event_board():
    """Draw the D04 blackboard at print resolution from original lettering and marker paths."""
    rng = random.Random(1104)
    scale = 2
    board = Image.new("RGB", (800 * scale, 1176 * scale), (5, 5, 5))
    draw = ImageDraw.Draw(board)
    blue, peach, pink = "#74cbe9", "#f7b784", "#efa397"
    cream, mint, lemon = "#f0eedf", "#a8d794", "#e6dc91"
    font = typeface(KOREAN, 164)

    def letters(text, box, ink, tilt=2):
        # Ink each glyph separately. Keep its aspect and baseline variation local so
        # short particles remain small and a line never overflows the physical board.
        run = Image.new("L", (int(font.getlength(text)) + len(text) * 40 + 64, 258))
        cursor = 12
        for ch in text:
            advance = font.getlength(ch)
            if ch != " ":
                glyph = Image.new("L", (242, 236))
                ImageDraw.Draw(glyph).text((24, 172), ch, font=font, anchor="ls", fill=255)
                glyph = glyph.rotate(rng.uniform(-tilt, tilt), Image.Resampling.BICUBIC,
                                     center=(103, 120))
                run.paste(255, (round(cursor) - 12, rng.randint(1, 8)), glyph)
            cursor += advance * rng.uniform(.99, 1.04) + 3
        x, y, w, h = box
        mask = run.crop(run.getbbox()).resize((w * scale, h * scale), Image.Resampling.LANCZOS)
        board.paste(ink, (x * scale, y * scale), mask)

    def stroke(points, ink, width):
        pts = [(round(x * scale), round(y * scale)) for x, y in points]
        radius = width * scale / 2
        draw.line(pts, fill=ink, width=round(2 * radius), joint="curve")
        for x, y in (pts[0], pts[-1]):
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=ink)

    def bezier_segments(start, segments):
        points = [start]
        for b, c, end in segments:
            a = points[-1]
            for j in range(1, 19):
                t = j / 18
                points.append(tuple((1-t)**3*a[k] + 3*(1-t)**2*t*b[k]
                                    + 3*(1-t)*t*t*c[k] + t**3*end[k] for k in (0, 1)))
        return points

    # Hand-drawn, upright, disconnected E-v-e-n-t. The turns and crossbars have
    # slightly different lengths, as on the in-store board.
    letters("11", (64, 60, 164, 140), blue)
    letters("월", (244, 49, 71, 94), blue)
    for points in [
        [(418,62),(343,65),(346,190),(422,186)], [(346,124),(402,120)],
        [(431,105),(463,183),(493,101)],
        bezier_segments((511,140), [((524,136),(550,137),(565,134)),
            ((568,78),(507,84),(506,143)),((506,182),(538,198),(569,172))]),
        bezier_segments((592,183), [((592,162),(591,120),(590,101)),
            ((597,137),(597,102),(620,99)),((653,89),(650,144),(654,180))]),
        bezier_segments((704,65), [((706,105),(702,147),(706,168)),((709,186),(722,184),(733,180))]),
        [(679,106),(711,103),(737,101)],
    ]:
        stroke(points, peach, 11)

    def number_badge(n, y):
        path = bezier_segments((36,y+19), [((62,y+25),(93,y-17),(133,y-6)),
            ((169,y+9),(158,y+66),(116,y+72)),((68,y+82),(44,y+60),(36,y+19))])
        stroke([(x+3, yy+4) for x,yy in path], mint, 7)
        stroke(path, cream, 4)
        letters(n, (78,y+11,34,43), cream)

    number_badge("1", 275)
    letters("공동구매", (192, 258, 356, 102), cream)
    letters("1:1", (597, 230, 120, 63), mint)
    letters("PT", (608, 311, 109, 68), mint)
    letters("200회", (220, 421, 287, 92), cream)
    letters("한정!", (554, 420, 175, 80), peach)
    stroke([(212,473),(288,475),(362,483),(444,486),(505,490)], pink, 8)

    letters("잔여수량", (53, 600, 219, 58), cream)
    letters("115", (325, 563, 214, 107), cream)
    letters("회", (582, 574, 76, 89), lemon)
    stroke([(325,694),(398,692),(473,695),(543,686)], lemon, 7)

    number_badge("2", 776)
    letters("7번", (185, 780, 100, 75), peach)
    letters("운동 인증하고", (310, 774, 420, 74), cream)
    letters("회원권", (199, 908, 199, 71), cream)
    letters("7일", (421, 897, 113, 78), pink)
    letters("받자!", (565, 891, 167, 80), cream)

    letters("카운터", (47, 1073, 154, 58), mint)
    letters("또는", (222, 1083, 88, 43), cream)
    letters("담당 선생님", (337, 1068, 264, 61), mint)
    letters("문의", (630, 1063, 113, 60), cream)
    stroke([(49,1141),(99,1137),(149,1139),(202,1135)], lemon, 4)
    stroke([(340,1140),(405,1137),(479,1139),(550,1134),(602,1133)], lemon, 4)
    save(board.resize((1024, 1505), Image.Resampling.LANCZOS), "D04_marker.jpg")


if __name__ == "__main__":
    event_board()
    mirror_lightboxes()
    mirror_notice()
    achievement()
