"""Generate lightweight 5-face 'Spider-Man interior mapping' textures for the opposite English academy (이룸영어교습소)."""
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


def save_jpg(im, name, quality=82):
    path = os.path.join(OUT, name)
    im.convert("RGB").save(path, "JPEG", quality=quality, optimize=True)
    print(f"Wrote {name}: {im.size}, {os.path.getsize(path)//1024}KB")


# 1) Back wall: Korean English academy classroom (whiteboard + EROOM sign + clock + bookshelf + desks)
def make_back():
    W, H = 512, 420
    im = Image.new("RGB", (W, H), (238, 236, 228))
    d = ImageDraw.Draw(im)
    # Soft warm ambient ceiling-to-floor gradient & lower birch wainscot
    d.rectangle([0, 305, W, H], fill=(214, 198, 174))
    d.rectangle([0, 300, W, 307], fill=(168, 145, 115))
    d.rectangle([0, H - 18, W, H], fill=(115, 96, 74))

    # Top title lettering 'EROOM ENGLISH'
    d.text((134, 24), "EROOM ENGLISH", font=font(30, 8), fill=(36, 74, 142))
    # Wall clock on top right
    d.ellipse([424, 22, 474, 72], fill=(252, 252, 250), outline=(58, 62, 70), width=4)
    d.line([(449, 47), (449, 31)], fill=(30, 30, 34), width=3)
    d.line([(449, 47), (463, 52)], fill=(30, 30, 34), width=2)

    # Large framed whiteboard in center-left
    d.rectangle([48, 86, 356, 258], fill=(248, 250, 252), outline=(172, 140, 96), width=8)
    d.text((70, 104), "Unit 4. 관계대명사 & to부정사", font=font(18, 8), fill=(32, 68, 148))
    d.line([(70, 130), (328, 130)], fill=(195, 205, 220), width=2)
    d.text((72, 142), "• who / which / that 용법 정리", font=font(15, 6), fill=(42, 46, 52))
    d.text((72, 168), "• 숙제: 워크북 p.42 ~ p.48", font=font(15, 6), fill=(192, 48, 48))
    d.text((72, 194), "• 단어시험: Day 15 (90점 통과)", font=font(15, 6), fill=(42, 46, 52))
    # Marker tray
    d.rectangle([90, 254, 290, 264], fill=(185, 188, 192))

    # Wooden textbook shelf on the right
    d.rectangle([382, 108, 486, 398], fill=(178, 144, 102), outline=(128, 98, 66), width=4)
    book_cols = [(42, 92, 168), (212, 68, 58), (54, 148, 88), (232, 178, 42), (128, 72, 158)]
    for sy in (148, 208, 268, 328):
        d.rectangle([386, sy, 482, sy + 8], fill=(142, 112, 76))
        bx = 392
        for j in range(7):
            bw = 10
            bh = 34 + (j % 3) * 5
            d.rectangle([bx, sy - bh, bx + bw, sy], fill=book_cols[(j + sy) % len(book_cols)], outline=(40, 40, 44))
            bx += bw + 2

    # Painted student desk row silhouettes at bottom for depth
    for dx in (56, 170, 284):
        d.rectangle([dx, 336, dx + 92, 350], fill=(224, 202, 166), outline=(142, 118, 86), width=2)
        d.rectangle([dx + 8, 350, dx + 14, 412], fill=(92, 96, 102))
        d.rectangle([dx + 78, 350, dx + 84, 412], fill=(92, 96, 102))
        # Blue classroom chair back
        d.rounded_rectangle([dx + 22, 314, dx + 70, 344], radius=6, fill=(52, 98, 168), outline=(34, 68, 122), width=2)

    save_jpg(im, "academy_back.jpg")


# 2) Side wall: English academy posters + wainscot + subtle desk edge
def make_side():
    W, H = 420, 420
    im = Image.new("RGB", (W, H), (232, 230, 222))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 305, W, H], fill=(208, 192, 168))
    d.rectangle([0, 300, W, 307], fill=(162, 140, 110))
    d.rectangle([0, H - 18, W, H], fill=(112, 94, 72))
    # Two framed study posters
    d.rectangle([48, 92, 186, 256], fill=(246, 250, 255), outline=(42, 86, 158), width=5)
    d.rectangle([48, 92, 186, 134], fill=(42, 86, 158))
    d.text((64, 102), "GRAMMAR", font=font(20, 8), fill=(255, 255, 255))
    for i in range(5):
        d.rectangle([64, 150 + i * 18, 168, 158 + i * 18], fill=(195, 205, 218))

    d.rectangle([224, 92, 366, 256], fill=(255, 250, 232), outline=(218, 158, 32), width=5)
    d.rectangle([224, 92, 366, 134], fill=(218, 158, 32))
    d.text((246, 102), "내신 1등급", font=font(20, 8), fill=(255, 255, 255))
    for i in range(5):
        d.rectangle([240, 150 + i * 18, 348, 158 + i * 18], fill=(224, 212, 178))

    save_jpg(im, "academy_side.jpg")


# 3) Warm light-oak classroom floor
def make_floor():
    W, H = 320, 320
    im = Image.new("RGB", (W, H), (206, 184, 150))
    d = ImageDraw.Draw(im)
    for y in range(0, H, 28):
        col = (200, 176, 142) if (y // 28) % 2 == 0 else (212, 190, 156)
        d.rectangle([0, y, W, y + 27], fill=col)
        d.line([(0, y), (W, y)], fill=(172, 148, 116), width=1)
    save_jpg(im, "academy_floor.jpg", quality=78)


# 4) Bright fluorescent acoustic ceiling
def make_ceil():
    W, H = 320, 320
    im = Image.new("RGB", (W, H), (222, 224, 222))
    d = ImageDraw.Draw(im)
    for g in range(0, W, 64):
        d.line([(g, 0), (g, H)], fill=(188, 190, 188), width=2)
        d.line([(0, g), (W, g)], fill=(188, 190, 188), width=2)
    # 2 bright LED panels
    d.rectangle([52, 68, 268, 126], fill=(255, 255, 255), outline=(165, 168, 172), width=3)
    d.rectangle([52, 196, 268, 254], fill=(255, 255, 255), outline=(165, 168, 172), width=3)
    save_jpg(im, "academy_ceil.jpg", quality=78)


if __name__ == "__main__":
    make_back()
    make_side()
    make_floor()
    make_ceil()
