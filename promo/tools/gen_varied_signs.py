"""Generate 6 varied Korean commercial projecting sign textures modeled after the 3 reference styles:
- Style A (Rect): matte-black deep lightbox with clean warm-white face + icon + Korean/English title
- Style B (Square): minimalist square glowing cube with luxury curved header + bold typography
- Style C (Round): circular acrylic sign with bold graphic icon (piano keys / dumbbell-watch) + rounded Korean title"""
import math
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


def save_jpg(im, name, quality=86):
    path = os.path.join(OUT, name)
    im.convert("RGB").save(path, "JPEG", quality=quality, optimize=True)
    print(f"Wrote {name}: {im.size}, {os.path.getsize(path)//1024}KB")


# 1) Sign_Derma (Square Style B — inspired by GLOW nail salon cube)
def make_sign_derma():
    im = Image.new("RGB", (420, 420), (248, 245, 247))
    d = ImageDraw.Draw(im)
    d.rectangle([16, 16, 404, 404], outline=(228, 206, 214), width=3)
    d.text((112, 82), "DERMATOLOGY", font=font(24, 5), fill=(165, 92, 114))
    d.line([(135, 122), (285, 122)], fill=(208, 148, 166), width=2)
    d.text((78, 152), "더맑은", font=font(86, 8), fill=(48, 34, 42))
    d.text((92, 256), "피부과의원", font=font(54, 6), fill=(158, 72, 98))
    d.text((126, 336), "5F  LIFTING · SKIN", font=font(20, 5), fill=(135, 122, 128))
    save_jpg(im, "sign_derma.jpg")


# 2) Sign_Dental (Rect Style A — inspired by 준 인테리어 glowing warm-white box + round icon)
def make_sign_dental():
    im = Image.new("RGB", (560, 300), (253, 252, 249))
    d = ImageDraw.Draw(im)
    # Left round icon badge (clean medical blue circle + white cross/tooth motif)
    d.ellipse([44, 78, 184, 218], fill=(38, 118, 198))
    d.rounded_rectangle([98, 106, 130, 190], radius=6, fill=(255, 255, 255))
    d.rounded_rectangle([72, 132, 156, 164], radius=6, fill=(255, 255, 255))
    # Right bilingual typography
    d.text((212, 92), "B A R U N   D E N T A L", font=font(22, 5), fill=(120, 135, 152))
    d.text((208, 130), "바른치과의원", font=font(56, 8), fill=(32, 42, 54))
    d.text((212, 204), "4F · 임플란트 · 투명교정", font=font(22, 6), fill=(72, 118, 168))
    save_jpg(im, "sign_dental.jpg")


# 3) Sign_WatchCoach (Round Style C — circular acrylic sign with bold dark/cyan gym-watch badge)
def make_sign_watchcoach():
    im = Image.new("RGB", (512, 512), (16, 26, 38))
    d = ImageDraw.Draw(im)
    # Outer cyan accent ring
    d.ellipse([24, 24, 488, 488], outline=(0, 212, 224), width=14)
    # Stylized dumbbell + watch circle graphic at top
    d.rounded_rectangle([144, 126, 174, 214], radius=8, fill=(0, 212, 224))
    d.rounded_rectangle([178, 142, 198, 198], radius=5, fill=(0, 212, 224))
    d.rounded_rectangle([338, 126, 368, 214], radius=8, fill=(0, 212, 224))
    d.rounded_rectangle([314, 142, 334, 198], radius=5, fill=(0, 212, 224))
    d.rectangle([196, 162, 316, 178], fill=(235, 245, 250))
    # Center watch dial icon
    d.ellipse([226, 140, 286, 200], fill=(16, 26, 38), outline=(255, 255, 255), width=6)
    d.line([(256, 170), (256, 152)], fill=(0, 212, 224), width=5)
    d.line([(256, 170), (270, 176)], fill=(255, 255, 255), width=4)
    # Bold Korean title
    d.text((104, 248), "워치코치 짐", font=font(64, 8), fill=(255, 255, 255))
    d.text((146, 334), "302호 · 24시 헬스", font=font(30, 7), fill=(0, 218, 228))
    d.text((168, 382), "WATCHCOACH GYM", font=font(20, 6), fill=(168, 188, 205))
    save_jpg(im, "sign_watchcoach.jpg")


# 4) Sign_Math / Eroom English (Rect Style A — warm-white face + terracotta/navy icon like 준 인테리어)
def make_sign_eroom():
    im = Image.new("RGB", (560, 300), (254, 251, 244))
    d = ImageDraw.Draw(im)
    # Left round terracotta-orange house/roof icon (directly echoing Photo 1!)
    d.ellipse([44, 78, 184, 218], fill=(182, 114, 72))
    d.polygon([(114, 102), (68, 146), (160, 146)], fill=(254, 251, 244))
    d.rectangle([82, 146, 146, 196], fill=(254, 251, 244))
    d.rectangle([98, 156, 110, 168], fill=(182, 114, 72))
    d.rectangle([118, 156, 130, 168], fill=(182, 114, 72))
    d.rectangle([98, 174, 110, 186], fill=(182, 114, 72))
    d.rectangle([118, 174, 130, 186], fill=(182, 114, 72))
    d.text((210, 96), "E R O O M   E N G L I S H", font=font(22, 5), fill=(158, 132, 112))
    d.text((208, 134), "이룸영어교습소", font=font(50, 8), fill=(58, 44, 34))
    d.text((212, 204), "초·중·고 내신 · 수능 전문", font=font(21, 6), fill=(138, 104, 78))
    save_jpg(im, "sign_eroom.jpg")


# 5) Sign_Pilates (Square Style B — exact GLOW minimalist cool-white cube vibe!)
def make_sign_pilates():
    im = Image.new("RGB", (420, 420), (235, 242, 255))
    d = ImageDraw.Draw(im)
    d.text((104, 96), "PILATES STUDIO", font=font(26, 5), fill=(35, 42, 58))
    d.text((66, 152), "GLOW", font=font(104, 7), fill=(18, 22, 32))
    d.line([(120, 286), (300, 286)], fill=(70, 85, 115), width=2)
    d.text((120, 304), "글로우 필라테스", font=font(28, 6), fill=(42, 52, 72))
    save_jpg(im, "sign_pilates.jpg")


# 6) Sign_Piano (Round Style C — directly copying Photo 3 hot-pink circular piano sign!)
def make_sign_piano():
    im = Image.new("RGB", (512, 512), (238, 56, 146))
    d = ImageDraw.Draw(im)
    # Dark charcoal grand piano body silhouette in upper half
    d.rounded_rectangle([116, 44, 396, 252], radius=24, fill=(38, 46, 56))
    # Cut curve on top-right to suggest grand piano wing
    d.ellipse([268, 24, 412, 132], fill=(238, 56, 146))
    # Crisp white piano keys
    key_x0 = 136
    key_w = 24
    for i in range(10):
        kx = key_x0 + i * (key_w + 2)
        d.rectangle([kx, 152, kx + key_w, 240], fill=(255, 255, 255))
    # Black sharp keys
    for i in (0, 1, 3, 4, 5, 7, 8):
        bx = key_x0 + i * (key_w + 2) + 16
        d.rectangle([bx, 152, bx + 15, 206], fill=(38, 46, 56))
    # Bold white rounded Korean title (matching Photo 3!)
    d.text((92, 276), "소리피아노", font=font(76, 8), fill=(255, 255, 255))
    d.text((168, 372), "교습소", font=font(56, 8), fill=(255, 255, 255))
    save_jpg(im, "sign_piano.jpg")


if __name__ == "__main__":
    make_sign_derma()
    make_sign_dental()
    make_sign_watchcoach()
    make_sign_eroom()
    make_sign_pilates()
    make_sign_piano()
