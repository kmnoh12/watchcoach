"""Generate lightweight Coupang Rocket Fresh (로켓프레시) woven-tarp cooler bag textures."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "parts", "sangga_elev"))
os.makedirs(OUT, exist_ok=True)
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def font(size, idx=7):
    try:
        return ImageFont.truetype(FONT_PATH, size, index=idx)
    except Exception:
        return ImageFont.load_default()


def draw_rocket(d, x, y, scale=1.0, col=(245, 248, 252)):
    s = scale
    # Simple iconic tilted rocket silhouette
    d.polygon([
        (x + 26 * s, y),
        (x + 34 * s, y + 18 * s),
        (x + 18 * s, y + 36 * s),
        (x + 4 * s, y + 26 * s),
        (x + 14 * s, y + 8 * s),
    ], fill=col)
    # Tail flame
    d.polygon([(x + 6 * s, y + 28 * s), (x - 4 * s, y + 40 * s), (x + 14 * s, y + 34 * s)], fill=col)
    # Porthole dot
    d.ellipse([x + 16 * s, y + 13 * s, x + 23 * s, y + 20 * s], fill=(32, 48, 128))


def draw_barcode(d, x, y, w=110, h=28):
    d.rectangle([x, y, x + w, y + h], fill=(248, 248, 246), outline=(210, 210, 208))
    bx = x + 8
    pattern = [3, 1, 2, 1, 4, 2, 1, 3, 1, 2, 3, 1, 2, 1, 3, 2, 1, 4, 1, 2, 2, 1, 3]
    for i, pw in enumerate(pattern):
        if bx + pw > x + w - 8:
            break
        if i % 2 == 0:
            d.rectangle([bx, y + 4, bx + pw, y + h - 8], fill=(24, 24, 26))
        bx += pw + 1
    d.text((x + 28, y + h - 9), "C1-XAWLL", font=font(8, 6), fill=(40, 40, 42))


def make_freshbag(name, primary, secondary, accent, trim):
    # 512x512 atlas-friendly wrap texture (front/side/top colorful Rocket Fresh collage)
    W, H = 512, 512
    im = Image.new("RGB", (W, H), primary)
    d = ImageDraw.Draw(im)

    # Organic colorful color-block shapes (exact Photo 1 & 2 Rocket Fresh art style!)
    d.pieslice([-60, -40, 260, 260], 0, 360, fill=secondary)
    d.pieslice([280, 220, 580, 540], 0, 360, fill=secondary)
    # White milk pitcher / fried egg graphic
    d.ellipse([40, 140, 210, 320], fill=(242, 244, 246))
    d.ellipse([95, 195, 155, 255], fill=(242, 196, 38))  # egg yolk / lemon accent
    # Peach/coral bread & olive branch shapes
    d.ellipse([300, 20, 490, 165], fill=(238, 168, 124))
    for lx, ly in ((340, 200), (390, 185), (430, 215), (365, 245)):
        d.ellipse([lx, ly, lx + 42, ly + 18], fill=accent)
    d.ellipse([388, 228, 412, 256], fill=(28, 32, 36))
    d.ellipse([424, 240, 448, 268], fill=(28, 32, 36))
    # Playful yellow noodle squiggle under logo
    d.arc([78, 392, 220, 442], 170, 360, fill=(235, 190, 48), width=5)
    d.arc([92, 410, 236, 460], 0, 190, fill=(235, 190, 48), width=5)

    # Dark lower front band for high-contrast '🚀 로켓프레시' logo
    d.rectangle([0, 315, W, 425], fill=primary)
    draw_rocket(d, 74, 344, scale=1.15)
    d.text((130, 344), "로켓프레시", font=font(56, 8), fill=(248, 250, 252))

    # Top 'coupang' logo + barcode sticker
    d.text((146, 56), "coupang", font=font(50, 8), fill=(248, 250, 252))
    draw_barcode(d, 56, 124)

    # Subtle woven polypropylene crosshatch lines
    for y in range(0, H, 6):
        d.line([(0, y), (W, y)], fill=tuple(max(0, c - 8) for c in primary), width=1)
    # Trim border line
    d.rectangle([0, 0, W - 1, H - 1], outline=trim, width=6)

    path = os.path.join(OUT, name)
    im.save(path, "JPEG", quality=82, optimize=True)
    print(f"Wrote {name}: {im.size}, {os.path.getsize(path)//1024}KB")


if __name__ == "__main__":
    # Top bag: cobalt blue + forest green + yellow olive (Photo 1 top!)
    make_freshbag("freshbag_blue.jpg", (28, 52, 138), (38, 102, 72), (222, 214, 42), (48, 76, 178))
    # Bottom bag: deep purple + forest green + warm yellow (Photo 1 & 2 bottom!)
    make_freshbag("freshbag_purple.jpg", (92, 34, 118), (32, 108, 68), (232, 188, 36), (118, 48, 148))
