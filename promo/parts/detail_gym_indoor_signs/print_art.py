"""Rebuild the original typeset notices and mirror masks from the repository root with Pillow."""
from pathlib import Path
import math
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
    im=Image.new("RGB",(1500,640),"#19283e")
    d=ImageDraw.Draw(im)
    for bounds,color in [((-70,15,1700,1150),"#b79152"),((-15,29,1680,1160),"#e5c585"),
                         ((15,43,1690,1200),"#faf2df")]:
        d.ellipse(bounds,fill=color)
    gold="#b39457"
    for side in [-1,1]:
        pts=[]
        for i in range(15):
            t=i/14
            x=750+side*(350+134*math.sin(t*1.9))
            y=504-285*t
            pts.append((x,y))
            if 0<i<14:
                for direction in (-1,1):
                    tip=(x+side*direction*24,y-29)
                    d.polygon([(x,y),(x+side*direction*16,y-4),tip,(x+side*direction*7,y-20)],fill=gold)
        d.line(pts,fill=gold,width=3)
    d.text((750,199),"워치코치 바디프로필 프로젝트",anchor="mm",font=typeface(KOREAN,46),fill="#303342")
    d.text((750,341),"회원 성과 전시",anchor="mm",font=typeface(KOREAN,95),fill="#19283e",stroke_width=1)
    d.line((649,442,851,442),fill=gold,width=3)
    cx,cy=1362,112
    for x in [cx-19,cx+19]:
        d.polygon([(x-13,cy+17),(x+14,cy+17),(x+20,cy+66),(x+1,cy+56),(x-13,cy+69)],fill="#9f4f3e")
    d.regular_polygon((cx,cy,47),32,fill="#c09c5d")
    d.ellipse((cx-37,cy-37,cx+37,cy+37),fill="#273247",outline="#f1d796",width=3)
    d.text((cx,cy),"WC",anchor="mm",font=typeface(SYSTEM/"Georgia Bold.ttf",24),fill="#ead39b")
    save(im,"D06_project.jpg")



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

if __name__ == "__main__":
    mirror_lightboxes()
    mirror_notice()
    achievement()
