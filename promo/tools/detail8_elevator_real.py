"""Detail pass 8: Realistic Korean commercial-building elevator bay matching real reference photos.

Replaces the hallway elevator surround, walls, mirror-stainless portal/transom, arched red
dot-matrix floor indicator, checkerboard-etched twin stainless doors, Korean safety warning
stickers, left-mounted call button panel, 3D brass '3F' sign, and red-header evacuation map
('피난안내도') in `promo/scenes/scene_gym.blend` using Kyungmin's reference photos
(`work/refs/elevator_20261128/01_front.jpg`, `02_door_closeup.jpg`).

Preserves:
  - Existing hallway structure, corridor walls, ceiling, floor, and lighting
  - `DETAIL5_elevator_tactile` (`Ddetail5_ElevTactile_Patch`) tactile paving blocks
  - `D4elev_DoorPlaneProbe` planar reflection probe (aligned to the new door plane)
  - Corridor floor props (`Elev_Extinguisher`, `Elev_XBanner_Golf`, `Elev_XBanner_Mart`)

All replaced elevator wall/frame/door/fixture objects and their orphan data/materials are
deleted cleanly (no hidden originals left behind). 100% idempotent.

Usage:
  1) Generate textures (system Python 3 with Pillow + numpy):
       python3 promo/tools/detail8_elevator_real.py --gen-textures
  2) Apply inside Blender (never saves unless --save <path> is given):
       Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail8_elevator_real.py [-- --save out.blend]
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

KEY = "detail8_elevator_real"
COLL = "DETAIL8_elevator_real"
PFX = "D8elev_"

REPO_ROOT = Path(__file__).resolve().parents[2]
TEX_DIR = REPO_ROOT / "promo" / "parts" / "detail8_elevator_real"

FONT_KR_TTC = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
FONT_KR_FALLBACK = str(REPO_ROOT / "promo" / "parts" / "fonts" / "NanumGothic-Bold.ttf")
FONT_3D_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# Texture filenames
TEX_LIGHT_GRANITE = "light_granite_tile.jpg"
TEX_DARK_GRANITE = "dark_granite_tile.jpg"
TEX_DOOR_COLOR = "door_etch_color.png"
TEX_DOOR_ROUGH = "door_etch_rough.png"
TEX_DOOR_BUMP = "door_etch_bump.png"
TEX_STICKER_L = "sticker_left_hand.png"
TEX_STICKER_R = "sticker_right_lean.png"
TEX_STICKER_ROUGH = "sticker_pvc_rough.png"
TEX_INDICATOR = "indicator_display_3f.png"
TEX_CALL_TOP = "call_panel_top.png"
TEX_CALL_WC = "call_wheelchair.png"
TEX_EVAC_MAP = "evac_map_3f.png"


# =====================================================================================
# 1. Texture generation (Pillow + numpy)
# =====================================================================================
def _kr_font(size: int, weight: str = "bold"):
    from PIL import ImageFont
    # Verified macOS AppleSDGothicNeo.ttc indices:
    # 0=Regular, 2=Medium, 4=SemiBold, 6=Bold, 14=ExtraBold
    idx_map = {"regular": 0, "medium": 2, "semibold": 4, "bold": 6, "extrabold": 14}
    idx = idx_map.get(weight, 6)
    if os.path.exists(FONT_KR_TTC):
        try:
            return ImageFont.truetype(FONT_KR_TTC, size, index=idx)
        except Exception:
            pass
    return ImageFont.truetype(FONT_KR_FALLBACK, size)


def _tile_noise(np, rng, h: int, w: int, cells: int):
    """Smooth periodic bilinear value noise."""
    g = rng.random((cells + 1, cells + 1))
    g[-1, :] = g[0, :]
    g[:, -1] = g[:, 0]
    ys = np.linspace(0, cells, h, endpoint=False)
    xs = np.linspace(0, cells, w, endpoint=False)
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3.0 - 2.0 * fy)
    fx = fx * fx * (3.0 - 2.0 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1.0 - fx) + b * fx) * (1.0 - fy) + (c * (1.0 - fx) + d * fx) * fy


def _fbm(np, rng, h: int, w: int, base: int, octaves: int = 4, gain: float = 0.5):
    out = np.zeros((h, w), dtype=np.float64)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += amp * _tile_noise(np, rng, h, w, base * (2 ** o))
        tot += amp
        amp *= gain
    return out / tot


def _gen_granite_tiles():
    import numpy as np
    from PIL import Image, ImageFilter

    N = 1024
    rng = np.random.default_rng(20261128)

    # ---- Light speckled gray granite (포천석, ref 01_front) ----
    cloud = _fbm(np, rng, N, N, 4, octaves=4, gain=0.55)
    med = _fbm(np, rng, N, N, 32, octaves=3, gain=0.6)
    fine_q = rng.random((N, N))
    fine_b = rng.random((N, N))

    flake_raw = rng.random((N // 2, N // 2))
    flake_img = Image.fromarray((flake_raw * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    flake_img = flake_img.filter(ImageFilter.GaussianBlur(radius=0.85))
    flake = np.asarray(flake_img, dtype=np.float64) / 255.0

    base = np.zeros((N, N, 3), dtype=np.float64)
    base[..., 0] = 179.0 + (cloud - 0.5) * 26.0 + (med - 0.5) * 34.0
    base[..., 1] = 180.0 + (cloud - 0.5) * 26.0 + (med - 0.5) * 34.0
    base[..., 2] = 178.0 + (cloud - 0.5) * 25.0 + (med - 0.5) * 33.0

    q_mask = np.clip((flake - 0.63) * 5.2, 0.0, 1.0)
    base += q_mask[..., None] * 48.0
    base[fine_q > 0.87] += 26.0

    b_mask = np.clip((0.37 - flake) * 5.6, 0.0, 1.0)
    base -= b_mask[..., None] * 98.0
    base[fine_b < 0.14] -= 62.0
    base[fine_b < 0.04] -= 42.0

    light_img = Image.fromarray(np.clip(base, 26, 245).astype(np.uint8))
    light_img.save(TEX_DIR / TEX_LIGHT_GRANITE, "JPEG", quality=93)

    # ---- Dark charcoal speckled granite with natural soft smoky mineral clouds (마천석) ----
    cloud_d = _fbm(np, rng, N, N, 3, octaves=5, gain=0.58)
    wx = _fbm(np, rng, N, N, 2, octaves=3, gain=0.5)
    wy = _fbm(np, rng, N, N, 2, octaves=3, gain=0.5)
    yy, xx = np.mgrid[0:N, 0:N]
    # Domain-warped soft mineral cloud bands (no sharp artificial lines)
    sx = np.clip((xx + (wx - 0.5) * N * 0.28).astype(int) % N, 0, N - 1)
    sy = np.clip((yy + (wy - 0.5) * N * 0.28).astype(int) % N, 0, N - 1)
    warped = cloud_d[sy, sx]
    wisp = np.clip((warped - 0.52) * 3.0, 0.0, 1.0) ** 1.35

    flake_d_raw = rng.random((N // 2, N // 2))
    flake_d_img = Image.fromarray((flake_d_raw * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    flake_d_img = flake_d_img.filter(ImageFilter.GaussianBlur(radius=0.75))
    flake_d = np.asarray(flake_d_img, dtype=np.float64) / 255.0
    fine_d = rng.random((N, N))

    dark = np.zeros((N, N, 3), dtype=np.float64)
    dark[..., 0] = 60.0 + (cloud_d - 0.5) * 26.0
    dark[..., 1] = 63.0 + (cloud_d - 0.5) * 26.0
    dark[..., 2] = 66.0 + (cloud_d - 0.5) * 27.0

    # Silvery-gray fine granite mineral speckles (visible in crop_bottom & crop_callbtn)
    silv = np.clip((flake_d - 0.57) * 4.8, 0.0, 1.0)
    dark += silv[..., None] * 42.0
    dark[fine_d > 0.85] += 26.0
    dark[fine_d < 0.16] -= 22.0

    # Soft pale natural stone mineral wisps (은은한 결무늬)
    dark += wisp[..., None] * np.array([28.0, 29.0, 30.0])

    dark_img = Image.fromarray(np.clip(dark, 18, 165).astype(np.uint8))
    dark_img.save(TEX_DIR / TEX_DARK_GRANITE, "JPEG", quality=93)


def _gen_door_etch_tiles():
    """Seamless 4x4 checkerboard tile (40mm x 40mm real world) matching 02_door_closeup.jpg.

    Bright hairline satin stainless ground with subtle, low-contrast horizontal 3-dash (≡)
    etched squares (no dark grid lines, no harsh mirror flash).
    Saved as RGB PNGs so Metal/OpenGL GPU texture uploads have zero single-channel errors.
    """
    import numpy as np
    from PIL import Image, ImageFilter

    N = 512
    cells = 4
    cs = N // cells  # 128 px per 10mm cell
    rng = np.random.default_rng(7788)

    # Fine vertical hairline brushing (real Korean stainless elevator door finish)
    hair_raw = rng.normal(0.0, 1.0, (N // 16, N))
    hair_img = Image.fromarray(np.clip(128 + hair_raw * 20, 0, 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    hairline = (np.asarray(hair_img, dtype=np.float64) - 128.0) / 128.0

    # Subtle etching mask: 1.0 on the 3 horizontal dashes (≡), 0.0 on satin ground
    bar_mask = np.zeros((N, N), dtype=np.float64)
    cell_tint = np.zeros((N, N), dtype=np.float64)

    x0, x1 = 18, 110
    bar_ys = [(23, 37), (57, 71), (91, 105)]

    for r in range(cells):
        for c in range(cells):
            ry, cx = r * cs, c * cs
            if (r + c) % 2 == 1:
                for y0, y1 in bar_ys:
                    bar_mask[ry + y0:ry + y1, cx + x0:cx + x1] = 1.0
            else:
                # Very faint satin sheen on alternating solid squares (no dark grid border)
                cell_tint[ry + 10:ry + cs - 10, cx + 10:cx + cs - 10] = 1.0

    bar_s = np.asarray(
        Image.fromarray((bar_mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=1.4)),
        dtype=np.float64,
    ) / 255.0
    cell_s = np.asarray(
        Image.fromarray((cell_tint * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=2.0)),
        dtype=np.float64,
    ) / 255.0

    # Base Color: bright light-medium silver stainless (0.785), ≡ bars only +0.032 brighter (subtle!)
    col_val = 0.785 + bar_s * 0.032 + cell_s * 0.008 + hairline * 0.014
    col_rgb = np.stack([col_val * 0.996, col_val * 0.996, col_val * 0.990], axis=-1)
    Image.fromarray(np.clip(col_rgb * 255, 0, 255).astype(np.uint8)).save(TEX_DIR / TEX_DOOR_COLOR, "PNG")

    # Roughness (Non-Color RGB): satin = 0.31, ≡ bars = 0.205 (soft, understated reflection delta ~0.10)
    rough = np.clip(0.31 - bar_s * 0.105 - cell_s * 0.015 + hairline * 0.016, 0.16, 0.38)
    rough_rgb = np.repeat((rough * 255).astype(np.uint8)[..., None], 3, axis=2)
    Image.fromarray(rough_rgb).save(TEX_DIR / TEX_DOOR_ROUGH, "PNG")

    # Bump (Non-Color RGB): very gentle acid-etched micro-relief + fine hairline
    bump = np.clip(0.48 + bar_s * 0.09 + hairline * 0.025, 0.0, 1.0)
    bump_rgb = np.repeat((bump * 255).astype(np.uint8)[..., None], 3, axis=2)
    Image.fromarray(bump_rgb).save(TEX_DIR / TEX_DOOR_BUMP, "PNG")


def _draw_centered_text(d, cx: float, cy: float, text: str, font, fill):
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    d.text((cx - tw / 2.0 - bbox[0], cy - th / 2.0 - bbox[1]), text, font=font, fill=fill)


def _apply_pvc_weathering(img, seed: int, corner_lift_side: str = "left"):
    """Apply subtle real-world PVC sticker UV aging, micro-grain, and outer-edge/corner grime.

    Keeps artwork and Korean text razor sharp while removing sterile digital flatness.
    """
    import numpy as np
    from PIL import Image

    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    H, W, _ = arr.shape
    rng = np.random.default_rng(seed)

    # 1) Soft uneven UV fading / warm aging mottling across the vinyl surface
    mottle = _fbm(np, rng, H, W, 3, octaves=4, gain=0.55)
    fine = _fbm(np, rng, H, W, 24, octaves=2, gain=0.5)
    # Subtle warm-neutral aging tint shift (dull slightly yellowed off-white, not heavy beige)
    arr[..., 0] *= 0.990 + (mottle - 0.5) * 0.042
    arr[..., 1] *= 0.988 + (mottle - 0.5) * 0.038
    arr[..., 2] *= 0.978 + (mottle - 0.5) * 0.035
    # Very faint PVC film micro-grain
    grain = (fine - 0.5) * 4.5 + rng.normal(0.0, 1.4, (H, W))
    arr += grain[..., None]

    # 2) Outer rounded-edge & corner grime (handling dirt along vinyl rim)
    yy, xx = np.mgrid[0:H, 0:W]
    # Distance to nearest rounded-rectangle edge (corner radius ~44 px)
    r = 44.0
    dx = np.maximum(np.maximum(r - xx, xx - (W - 1 - r)), 0.0)
    dy = np.maximum(np.maximum(r - yy, yy - (H - 1 - r)), 0.0)
    corner_dist = r - np.hypot(dx, dy)
    edge_dist = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy))
    d_border = np.where((dx > 0) & (dy > 0), corner_dist, edge_dist)
    d_border = np.clip(d_border, 0.0, 999.0)

    # Rim grime falls off smoothly within ~22 px of border, stronger at corners & bottom edge
    rim = np.exp(-d_border / 9.0)
    corner_boost = 1.0 + 0.85 * np.clip(1.0 - np.hypot(dx, dy) / 140.0, 0.0, 1.0) * ((dx > 0) | (dy > 0))
    # Slightly heavier smudge along bottom and the outer door-gap side where fingers touch
    side_w = (1.0 - xx / W) if corner_lift_side == "left" else (xx / W)
    bot_w = 0.65 + 0.55 * (yy / H)
    grime_noise = 0.55 + 0.90 * _fbm(np, rng, H, W, 6, octaves=3, gain=0.6)
    grime = np.clip(rim * corner_boost * bot_w * (0.75 + 0.45 * side_w) * grime_noise, 0.0, 1.0)

    # Darken toward warm dusty gray-brown along the rim (subtle, realistic ~14-22% max right on the very edge)
    dirt_col = np.array([108.0, 102.0, 94.0])
    alpha_g = np.clip(grime * 0.24, 0.0, 0.30)[..., None]
    arr = arr * (1.0 - alpha_g) + dirt_col * alpha_g

    # Very subtle hairline scuff/wipe marks across the middle vinyl
    scuff = np.clip((_fbm(np, rng, H, W, 8, octaves=3, gain=0.55) - 0.68) * 3.0, 0.0, 1.0)
    arr = arr * (1.0 - scuff[..., None] * 0.04) + np.array([218.0, 216.0, 210.0]) * (scuff[..., None] * 0.04)

    return Image.fromarray(np.clip(arr, 14, 242).astype(np.uint8))


def _gen_warning_stickers():
    """Exact Korean elevator door stickers matching 02_door_closeup.jpg with authentic UV fade & PVC wear."""
    import numpy as np
    from PIL import Image, ImageDraw

    W, H = 1024, 1072
    # Calibrated from ref_stickers_tight.jpg (weathered real-world ink & dull slightly yellowed off-white PVC)
    navy = (40, 78, 122)
    white_outer = (218, 220, 215)       # slightly yellowed dull off-white vinyl border
    white_body_l = (220, 222, 218)      # dull off-white interior
    white_body_r = (212, 214, 210)      # right sticker slightly duller/aged as in closeup
    ink = (36, 37, 40)                  # real slightly faded black ink
    slash_gray_l = (198, 201, 198)      # faded pale gray slash on left
    slash_gray_r = (178, 175, 172)      # faded light gray slash on right-left panel
    slash_orange = (158, 112, 50)       # faded orange-ochre slash on yellow panel
    yellow_bg = (176, 168, 66)          # muted/aged olive-mustard yellow
    bot_txt = (224, 226, 224)           # slightly aged off-white bottom text

    # Geometry matching ref_stickers_tight.jpg exact proportions
    m = 30                              # outer white margin
    bw = 23                             # blue border stroke width
    hdr_h = 136                         # top "주 의" header height
    banner_top = H - m - 166            # straight horizontal top edge of bottom blue bar
    ix0, ix1 = m + bw, W - 1 - m - bw
    iy0_hdr = m + bw
    iy0_body = iy0_hdr + hdr_h + 7      # 7 px blue divider below header
    iy1_body = banner_top

    def make_frame(body_col, header_mode: str, bottom_label: str):
        img = Image.new("RGB", (W, H), white_outer)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([m, m, W - 1 - m, H - 1 - m], radius=96, fill=navy)
        body_mask = Image.new("L", (W, H), 0)
        dm = ImageDraw.Draw(body_mask)
        dm.rounded_rectangle([ix0, iy0_hdr, ix1, iy1_body + 90], radius=72, fill=255)
        dm.rectangle([0, iy1_body, W, H], fill=0)
        img.paste(Image.new("RGB", (W, H), body_col), (0, 0), body_mask)

        hdr_mask = Image.new("L", (W, H), 0)
        dh = ImageDraw.Draw(hdr_mask)
        dh.rounded_rectangle([ix0, iy0_hdr, ix1, iy0_hdr + hdr_h + 72], radius=72, fill=255)
        dh.rectangle([0, iy0_hdr + hdr_h, W, H], fill=0)

        hdr_arr = np.zeros((H, W, 3), dtype=np.float64)
        t = np.linspace(0.0, 1.0, W)[None, :]
        if header_mode == "sage":
            c0 = np.array([194.0, 204.0, 198.0])
            c1 = np.array([186.0, 196.0, 190.0])
            hdr_arr[:] = c0 * (1.0 - t[..., None]) + c1 * t[..., None]
            hdr_txt_col = (214, 220, 216)  # washed-out white, weak contrast against sage
        else:
            c0 = np.array([170.0, 168.0, 164.0])
            c1 = np.array([158.0, 120.0, 116.0])
            t_s = np.clip((t - 0.16) / 0.74, 0.0, 1.0)
            hdr_arr[:] = c0 * (1.0 - t_s[..., None]) + c1 * t_s[..., None]
            hdr_txt_col = (208, 206, 204)  # faded pale white, weak contrast

        img.paste(Image.fromarray(hdr_arr.astype(np.uint8)), (0, 0), hdr_mask)
        d = ImageDraw.Draw(img)
        d.rectangle([ix0, iy0_hdr + hdr_h, ix1, iy0_body], fill=navy)

        # Bold chunky "주   의" matching real sticker header weight
        hf = _kr_font(104, "extrabold")
        for ch, ox in (("주", -112), ("의", 112)):
            bbox = d.textbbox((0, 0), ch, font=hf)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            d.text((W / 2.0 + ox - tw / 2.0 - bbox[0], iy0_hdr + hdr_h / 2.0 - th / 2.0 - bbox[1]),
                   ch, font=hf, fill=hdr_txt_col, stroke_width=2, stroke_fill=hdr_txt_col)

        # Bold chunky bottom label matching ref_stickers_tight.jpg width & weight
        bf = _kr_font(96 if len(bottom_label) <= 7 else 92, "extrabold")
        bbox = d.textbbox((0, 0), bottom_label, font=bf)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((W / 2.0 - tw / 2.0 - bbox[0], (banner_top + H - m) / 2.0 - th / 2.0 - bbox[1] - 3),
               bottom_label, font=bf, fill=bot_txt, stroke_width=2, stroke_fill=bot_txt)
        return img, d

    # =========================================================================
    # LEFT STICKER: 주의 / 손대지 마시오 (Open palm hand + faded gray slash)
    # =========================================================================
    img_l, dl = make_frame(white_body_l, "sage", "손대지 마시오")
    body_l = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dbl = ImageDraw.Draw(body_l)
    cx, cy = (ix0 + ix1) / 2.0 + 22, (iy0_body + iy1_body) / 2.0 + 18

    # 4 upright thick fingers with tight realistic spacing
    f_specs = [
        (cx - 166, cy - 224, cx - 90,  cy + 64),  # index
        (cx - 80,  cy - 270, cx - 4,   cy + 64),  # middle
        (cx + 6,   cy - 264, cx + 82,  cy + 64),  # ring
        (cx + 92,  cy - 212, cx + 162, cy + 64),  # pinky
    ]
    for fx0, fy0, fx1, fy1 in f_specs:
        dbl.rounded_rectangle([fx0, fy0, fx1, fy1], radius=34, fill=ink)

    # Sculpted palm body tapering smoothly to a clean flat wrist at bottom
    palm_poly = [
        (cx - 166, cy + 10),
        (cx + 162, cy + 10),
        (cx + 162, cy + 164),
        (cx + 140, cy + 206),
        (cx + 114, cy + 224),
        (cx + 104, cy + 258),
        (cx - 122, cy + 258),
        (cx - 134, cy + 216),
        (cx - 196, cy + 162),
    ]
    dbl.polygon(palm_poly, fill=ink)
    # Sleek tapered left-angled thumb matching ref_stickers_tight.jpg
    thumb_poly = [
        (cx - 162, cy + 100),
        (cx - 268, cy - 6),
        (cx - 318, cy + 8),
        (cx - 306, cy + 52),
        (cx - 186, cy + 196),
        (cx - 130, cy + 216),
    ]
    dbl.polygon(thumb_poly, fill=ink)
    dbl.ellipse([cx - 322, cy - 8, cx - 262, cy + 48], fill=ink)

    dbl.line([(ix0 - 8, iy0_body + 8), (ix1 + 8, iy1_body - 8)], fill=(*slash_gray_l, 255), width=42)

    clip_l = Image.new("L", (W, H), 0)
    ImageDraw.Draw(clip_l).rectangle([ix0, iy0_body, ix1, iy1_body], fill=255)
    img_l.paste(body_l.convert("RGB"), (0, 0), Image.fromarray(np.minimum(np.asarray(body_l)[..., 3], np.asarray(clip_l))))
    img_l = _apply_pvc_weathering(img_l, seed=4101, corner_lift_side="left")
    img_l.save(TEX_DIR / TEX_STICKER_L, "PNG")

    # =========================================================================
    # RIGHT STICKER: 주의 / 기대면 추락 위험 (Leaning + yellow falling panel)
    # =========================================================================
    img_r, dr = make_frame(white_body_r, "rose", "기대면 추락 위험")
    mid_x = int(ix0 + (ix1 - ix0) * 0.485)

    dr.rectangle([mid_x + 5, iy0_body, ix1, iy1_body], fill=yellow_bg)
    dr.rectangle([mid_x - 6, iy0_body, mid_x + 6, iy1_body], fill=navy)

    # -- Left panel: person leaning back against vertical door line --
    body_rl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    drl = ImageDraw.Draw(body_rl)
    lx0, lx1 = ix0, mid_x - 6
    floor_y = iy1_body - 36
    wall_x = lx1 - 44
    drl.line([(lx0 + 40, floor_y), (wall_x + 6, floor_y)], fill=ink, width=13)
    drl.line([(wall_x, iy0_body + 22), (wall_x, floor_y)], fill=ink, width=18)
    # Head
    drl.ellipse([wall_x - 122, iy0_body + 76, wall_x - 36, iy0_body + 162], fill=ink)
    # Smooth curved upper back & torso leaning against wall (zero step notch)
    drl.ellipse([wall_x - 130, iy0_body + 166, wall_x - 14, iy0_body + 298], fill=ink)
    drl.polygon([
        (wall_x - 124, iy0_body + 220),
        (wall_x - 28,  iy0_body + 266),
        (wall_x - 74,  iy0_body + 412),
        (wall_x - 154, iy0_body + 388),
    ], fill=ink)
    # Two clean thick diagonal legs with rounded shoes
    drl.line([(wall_x - 116, iy0_body + 356), (wall_x - 216, floor_y - 42)], fill=ink, width=60)
    drl.ellipse([wall_x - 246, floor_y - 72, wall_x - 186, floor_y - 12], fill=ink)
    drl.line([(wall_x - 84, iy0_body + 378), (wall_x - 140, floor_y - 40)], fill=ink, width=56)
    drl.ellipse([wall_x - 168, floor_y - 68, wall_x - 112, floor_y - 12], fill=ink)
    drl.line([(lx0 - 6, iy0_body + 6), (lx1 + 6, iy1_body - 6)], fill=(*slash_gray_r, 255), width=28)

    clip_rl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(clip_rl).rectangle([lx0, iy0_body, lx1, iy1_body], fill=255)
    img_r.paste(body_rl.convert("RGB"), (0, 0), Image.fromarray(np.minimum(np.asarray(body_rl)[..., 3], np.asarray(clip_rl))))

    # -- Right panel (yellow): open door + stocky head-first tumbling person + impact burst --
    body_rr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    drr = ImageDraw.Draw(body_rr)
    rx0, rx1 = mid_x + 6, ix1

    # Open elevator door icon at top-left
    drr.polygon([(rx0 + 40, iy0_body + 22), (rx0 + 82, iy0_body + 22),
                 (rx0 + 82, iy0_body + 132), (rx0 + 40, iy0_body + 132)], fill=ink)
    drr.polygon([(rx0 + 98, iy0_body + 22), (rx0 + 144, iy0_body + 22),
                 (rx0 + 180, iy0_body + 118), (rx0 + 128, iy0_body + 118)], fill=ink)
    drr.line([(rx0 + 94, iy0_body + 22), (rx0 + 94, iy0_body + 132)], fill=ink, width=9)

    # Stockier tumbling silhouette matching ref_stickers_tight.jpg
    hx, hy = rx0 + 242, iy1_body - 102
    drr.ellipse([hx - 35, hy - 35, hx + 35, hy + 35], fill=ink)
    # Broad rounded torso
    drr.rounded_rectangle([rx0 + 122, iy0_body + 298, rx0 + 216, hy - 34], radius=36, fill=ink)
    drr.polygon([
        (rx0 + 122, iy0_body + 312),
        (rx0 + 188, iy0_body + 278),
        (hx - 14,   hy - 62),
        (hx - 54,   hy - 28),
    ], fill=ink)
    # Right arm sticking straight right
    drr.line([(rx0 + 194, hy - 86), (hx + 86, hy - 86)], fill=ink, width=30)
    drr.ellipse([hx + 70, hy - 101, hx + 100, hy - 71], fill=ink)
    # Left arm bent smoothly down-left (rounded joints)
    p_sh = (rx0 + 148, hy - 44)
    p_el = (rx0 + 102, hy - 44)
    p_hd = (rx0 + 56,  hy - 110)
    drr.line([p_sh, p_el], fill=ink, width=30)
    drr.ellipse([p_el[0] - 15, p_el[1] - 15, p_el[0] + 15, p_el[1] + 15], fill=ink)
    drr.line([p_el, p_hd], fill=ink, width=28)
    drr.ellipse([p_hd[0] - 14, p_hd[1] - 14, p_hd[0] + 14, p_hd[1] + 14], fill=ink)
    # Two thick kicked-up legs
    p_hip_l = (rx0 + 144, iy0_body + 312)
    p_ft_l = (rx0 + 46,  iy0_body + 240)
    drr.line([p_hip_l, p_ft_l], fill=ink, width=38)
    drr.ellipse([p_ft_l[0] - 19, p_ft_l[1] - 19, p_ft_l[0] + 19, p_ft_l[1] + 19], fill=ink)
    p_hip_r = (rx0 + 188, iy0_body + 298)
    p_ft_r = (rx0 + 218, iy0_body + 178)
    drr.line([p_hip_r, p_ft_r], fill=ink, width=38)
    drr.ellipse([p_ft_r[0] - 19, p_ft_r[1] - 19, p_ft_r[0] + 19, p_ft_r[1] + 19], fill=ink)

    # Jagged impact burst outline below-left of falling head
    burst = [
        (hx - 46, hy + 6),
        (hx - 110, hy - 4),
        (hx - 76, hy + 36),
        (hx - 112, hy + 74),
        (hx - 54, hy + 60),
        (hx - 40, hy + 96),
        (hx - 16, hy + 56),
        (hx + 8,  hy + 74),
        (hx - 4,  hy + 38),
    ]
    drr.line(burst, fill=(*slash_orange, 255), width=12, joint="curve")
    drr.line([(rx0 - 6, iy0_body + 6), (rx1 + 6, iy1_body - 6)], fill=(*slash_orange, 255), width=28)

    clip_rr = Image.new("L", (W, H), 0)
    ImageDraw.Draw(clip_rr).rectangle([rx0, iy0_body, rx1, iy1_body], fill=255)
    img_r.paste(body_rr.convert("RGB"), (0, 0), Image.fromarray(np.minimum(np.asarray(body_rr)[..., 3], np.asarray(clip_rr))))
    img_r = _apply_pvc_weathering(img_r, seed=4202, corner_lift_side="right")
    img_r.save(TEX_DIR / TEX_STICKER_R, "PNG")

    # =========================================================================
    # SHARED PVC SEMI-GLOSS ROUGHNESS MAP (Non-Color RGB)
    # =========================================================================
    # Vinyl center is semi-gloss (0.19..0.27); handled/dirty outer edge is slightly duller (0.34..0.44)
    rng_r = np.random.default_rng(4303)
    smudge = _fbm(np, rng_r, 512, 512, 5, octaves=4, gain=0.55)
    yy, xx = np.mgrid[0:512, 0:512]
    d_edge = np.minimum(np.minimum(xx, 511 - xx), np.minimum(yy, 511 - yy))
    rim_r = np.exp(-d_edge / 14.0)
    r_map = np.clip(0.20 + (smudge - 0.5) * 0.12 + rim_r * 0.18, 0.14, 0.46)
    r_rgb = np.repeat((r_map * 255).astype(np.uint8)[..., None], 3, axis=2)
    Image.fromarray(r_rgb).save(TEX_DIR / TEX_STICKER_ROUGH, "PNG")


def _gen_indicator_display():
    """Arched transom LED dot-matrix display texture ('↓3') matching crop_transom.jpg."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    W, H = 1200, 240
    img = Image.new("RGB", (W, H), (4, 4, 5))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    dg = ImageDraw.Draw(glow)

    GLYPHS = {
        "↓": [
            "..#..",
            "..#..",
            "..#..",
            "..#..",
            "#.#.#",
            ".###.",
            "..#..",
        ],
        "3": [
            ".###.",
            "#...#",
            "....#",
            "..##.",
            "....#",
            "#...#",
            ".###.",
        ],
    }

    pitch = 20
    r_dot = 6.8
    seq = ["↓", "3"]
    total_cols = 5 * len(seq) + 2 * (len(seq) - 1)
    start_x = (W - (total_cols - 1) * pitch) / 2.0
    start_y = H * 0.56 - 3 * pitch

    col_cursor = 0
    for ch in seq:
        grid = GLYPHS[ch]
        for row_i, row_str in enumerate(grid):
            for col_i, c in enumerate(row_str):
                if c == "#":
                    cx = start_x + (col_cursor + col_i) * pitch
                    cy = start_y + row_i * pitch
                    dg.ellipse([cx - r_dot * 1.5, cy - r_dot * 1.5, cx + r_dot * 1.5, cy + r_dot * 1.5],
                               fill=(255, 20, 74))
        col_cursor += 7

    bloom = glow.filter(ImageFilter.GaussianBlur(radius=7.0))
    base_arr = np.asarray(img, dtype=np.float64) + np.asarray(bloom, dtype=np.float64) * 0.85
    out = Image.fromarray(np.clip(base_arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)

    col_cursor = 0
    for ch in seq:
        grid = GLYPHS[ch]
        for row_i, row_str in enumerate(grid):
            for col_i, c in enumerate(row_str):
                if c == "#":
                    cx = start_x + (col_cursor + col_i) * pitch
                    cy = start_y + row_i * pitch
                    d.ellipse([cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot], fill=(255, 42, 92))
                    d.ellipse([cx - r_dot * 0.58, cy - r_dot * 0.58, cx + r_dot * 0.58, cy + r_dot * 0.58],
                              fill=(255, 185, 205))
        col_cursor += 7

    out.save(TEX_DIR / TEX_INDICATOR, "PNG")


def _gen_call_panel_textures():
    """Top service-floor header plaque + blue wheelchair badge matching crop_callbtn.jpg."""
    from PIL import Image, ImageDraw

    W, H = 640, 340
    navy = (32, 62, 108)
    blue_dot = (56, 86, 134)
    white = (242, 244, 246)
    img = Image.new("RGB", (W, H), white)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(160, 166, 174), width=6)
    d.rectangle([8, 8, 466, 98], fill=navy)
    _draw_centered_text(d, 237, 53, "전층 운행", _kr_font(54, "extrabold"), white)

    ecx, ecy, er = 548, 102, 74
    d.ellipse([ecx - er, ecy - er, ecx + er, ecy + er], fill=white, outline=navy, width=10)
    d.polygon([(ecx - 24, ecy - 44), (ecx - 38, ecy - 22), (ecx - 10, ecy - 22)], fill=navy)
    d.rectangle([ecx - 28, ecy - 22, ecx - 20, ecy - 10], fill=navy)
    d.polygon([(ecx + 24, ecy - 10), (ecx + 10, ecy - 32), (ecx + 38, ecy - 32)], fill=navy)
    d.rectangle([ecx + 20, ecy - 44, ecx + 28, ecy - 32], fill=navy)
    d.rounded_rectangle([ecx - 34, ecy + 2, ecx + 34, ecy + 46], radius=6, fill=navy)
    d.rectangle([ecx - 22, ecy + 12, ecx + 22, ecy + 36], fill=white)

    rows = [["B1", "1F", "2F", "3F"], ["4F", "5F"]]
    for ri, row in enumerate(rows):
        cy = 166 + ri * 102
        for ci, lbl in enumerate(row):
            cx = 76 + ci * 106
            rr = 40
            col = (28, 74, 152) if lbl == "3F" else blue_dot
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
            _draw_centered_text(d, cx, cy, lbl, _kr_font(34, "extrabold"), white)

    d.text((405, 274), "워치코치프라자", fill=(72, 82, 98), font=_kr_font(26, "bold"))
    img.save(TEX_DIR / TEX_CALL_TOP, "PNG")

    S = 512
    wc = Image.new("RGB", (S, S), (22, 82, 162))
    dw = ImageDraw.Draw(wc)
    wcol = (238, 242, 248)
    dw.ellipse([214, 72, 286, 144], fill=wcol)
    dw.line([(244, 156), (244, 306)], fill=wcol, width=42)
    dw.line([(244, 214), (350, 214)], fill=wcol, width=32)
    dw.line([(230, 298), (356, 298)], fill=wcol, width=38)
    dw.line([(348, 294), (392, 412)], fill=wcol, width=36)
    dw.line([(384, 404), (428, 392)], fill=wcol, width=28)
    dw.arc([102, 216, 330, 444], start=35, end=278, fill=wcol, width=34)
    wc.save(TEX_DIR / TEX_CALL_WC, "PNG")


def _gen_evac_map():
    """Red-header '피 난 안 내 도' evacuation map plaque matching crop_sign_map.jpg."""
    from PIL import Image, ImageDraw

    W, H = 1320, 980
    paper = (242, 243, 245)
    crimson = (156, 28, 34)
    gold_ln = (224, 178, 52)
    ink = (36, 40, 46)
    mid = (118, 124, 134)
    room_bg = (222, 224, 228)
    corr_bg = (246, 247, 248)
    red_arr = (176, 34, 40)
    blue_here = (24, 92, 186)

    img = Image.new("RGB", (W, H), paper)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(200, 202, 206), width=4)

    mx = 54
    d.rectangle([mx, 44, W - mx, 178], fill=crimson)
    _draw_centered_text(d, W / 2.0, 108, "피   난   안   내   도", _kr_font(74, "extrabold"), (246, 247, 248))
    d.line([(mx + 120, 158), (W - mx - 120, 158)], fill=gold_ln, width=6)

    d.rectangle([mx, H - 72, W - mx, H - 46], fill=crimson)

    px0, py0, px1, py1 = 92, 232, W - 92, H - 118
    d.rectangle([px0, py0, px1, py1], fill=room_bg, outline=ink, width=6)

    corr_y0, corr_y1 = py0 + 250, py0 + 345
    corr_x0, corr_x1 = px0 + 180, px1 - 120
    d.rectangle([corr_x0, corr_y0, corr_x1, corr_y1], fill=corr_bg)
    d.rectangle([px0 + 92, py0 + 110, px0 + 190, py1 - 40], fill=corr_bg)

    d.rectangle([px0 + 310, py0, px0 + 730, corr_y0], fill=room_bg, outline=ink, width=5)
    d.rectangle([px0 + 730, py0, px0 + 930, corr_y0], fill=room_bg, outline=ink, width=5)
    d.rectangle([px0 + 930, py0, px1 - 110, corr_y0], fill=room_bg, outline=ink, width=5)
    d.rectangle([px1 - 110, py0, px1, corr_y0], fill=(208, 212, 218), outline=ink, width=5)
    for sy in range(py0 + 24, corr_y0 - 20, 16):
        d.line([(px1 - 102, sy), (px1 - 8, sy)], fill=mid, width=3)

    d.rectangle([px0 + 380, corr_y1, px0 + 760, py1], fill=room_bg, outline=ink, width=5)
    d.rectangle([px0 + 760, corr_y1, px0 + 960, py1], fill=room_bg, outline=ink, width=5)
    d.rectangle([px0 + 960, corr_y1, px1, py1], fill=room_bg, outline=ink, width=5)

    d.rectangle([px0, py0, px0 + 92, py1], fill=(214, 218, 224), outline=ink, width=4)
    ex0, ey0, ex1, ey1 = px0 + 245, corr_y1 + 56, px0 + 365, py1 - 18
    d.rectangle([ex0, ey0, ex1, ey1], fill=(232, 235, 240), outline=ink, width=5)
    d.line([(ex0, ey0), (ex1, ey1)], fill=mid, width=3)
    d.line([(ex0, ey1), (ex1, ey0)], fill=mid, width=3)
    sx0, sy0, sx1, sy1 = px0 + 188, corr_y1 + 56, px0 + 245, py1 - 18
    d.rectangle([sx0, sy0, sx1, sy1], fill=(210, 214, 220), outline=ink, width=4)
    for sy in range(sy0 + 16, sy1 - 12, 14):
        d.line([(sx0 + 6, sy), (sx1 - 6, sy)], fill=mid, width=3)

    d.rectangle([px0 + 92, py0, px0 + 260, py0 + 106], fill=(236, 240, 242), outline=ink, width=5)
    _draw_centered_text(d, px0 + 176, py0 + 52, "비상구", _kr_font(30, "extrabold"), ink)

    for cx, cy in [(px0 + 460, py0 + 42), (px0 + 640, py0 + 42), (px0 + 500, py1 - 42), (px0 + 680, py1 - 42)]:
        d.rectangle([cx - 10, cy - 10, cx + 10, cy + 10], fill=ink)

    _draw_centered_text(d, px0 + 520, py0 + 130, "워치짐 피트니스", _kr_font(30, "bold"), (58, 62, 70))
    _draw_centered_text(d, px0 + 570, corr_y1 + 140, "이룸하이 영어", _kr_font(28, "bold"), (58, 62, 70))
    _draw_centered_text(d, px0 + 860, corr_y1 + 140, "피아노", _kr_font(26, "bold"), (58, 62, 70))

    hx, hy = px0 + 142, corr_y1 + 115
    d.ellipse([hx - 14, hy - 14, hx + 14, hy + 14], fill=blue_here)
    _draw_centered_text(d, hx, hy + 30, "현위치", _kr_font(22, "extrabold"), blue_here)

    def arrow(x0, y0, x1, y1):
        d.line([(x0, y0), (x1, y1)], fill=red_arr, width=8)
        ang = math.atan2(y1 - y0, x1 - x0)
        hl = 17
        p1 = (x1 - hl * math.cos(ang - 0.55), y1 - hl * math.sin(ang - 0.55))
        p2 = (x1 - hl * math.cos(ang + 0.55), y1 - hl * math.sin(ang + 0.55))
        d.polygon([(x1, y1), p1, p2], fill=red_arr)

    cy_mid = (corr_y0 + corr_y1) / 2.0
    for ax in range(corr_x1 - 30, px0 + 280, -76):
        arrow(ax, cy_mid, ax - 42, cy_mid)
    arrow(px0 + 250, cy_mid, px0 + 210, cy_mid - 42)
    arrow(px0 + 195, cy_mid - 65, px0 + 160, cy_mid - 110)
    for ay in range(hy - 32, py0 + 140, -68):
        arrow(hx, ay, hx, ay - 38)

    img.save(TEX_DIR / TEX_EVAC_MAP, "PNG")


def gen_textures():
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    _gen_granite_tiles()
    _gen_door_etch_tiles()
    _gen_warning_stickers()
    _gen_indicator_display()
    _gen_call_panel_textures()
    _gen_evac_map()
    print(f"Generated textures in {TEX_DIR}")


# =====================================================================================
# 2. Blender Scene Construction (Hallway-local metres, parented to Sangga_Hallway_Ext)
# =====================================================================================
REMOVE_EXACT = (
    "ElevWall_Left", "ElevWall_Right",
    "ElevGranite_L", "ElevGranite_R", "ElevGranite_Top",
    "ElevFrame_L", "ElevFrame_R", "ElevFrame_Top",
    "D4elev_FrameFace_L", "D4elev_FrameFace_R", "D4elev_FrameFace_Top",
    "ElevJamb_L", "ElevJamb_R", "ElevSoffit",
    "ElevHeader_Back", "ElevHeader_Display",
    "ElevShaft_Backing", "Elev_Sill",
    "Elev_Door_L", "Elev_Door_R",
    "ElevSticker_L", "ElevSticker_R",
    "ElevLampBase_L0", "ElevLampBase_L1", "ElevLampBase_R0", "ElevLampBase_R1",
    "ElevLampBulb_L0", "ElevLampBulb_L1", "ElevLampBulb_R0", "ElevLampBulb_R1",
    "ElevCallPlate", "ElevBtnRing_0", "ElevBtnRing_1", "ElevBtnGlow_0", "ElevBtnGlow_1",
    "Elev_3F_Label",
    "ElevFloorGuide_Frame", "ElevFloorGuide_Face", "ElevOrangeNotice_Face",
    "Elev_FireHydrant",
)


def _remove_tree(ob) -> tuple[int, set, set]:
    """Delete an object and all its descendants cleanly (never leave hidden replaced originals)."""
    import bpy
    removed = 0
    cand_mats = set()
    cand_data = set()
    for ch in list(ob.children):
        r, ms, ds = _remove_tree(ch)
        removed += r
        cand_mats |= ms
        cand_data |= ds
    if hasattr(ob, "material_slots"):
        for sl in ob.material_slots:
            if sl.material is not None:
                cand_mats.add(sl.material)
    if ob.data is not None:
        cand_data.add(ob.data)
    bpy.data.objects.remove(ob, do_unlink=True)
    return removed + 1, cand_mats, cand_data


def _purge_orphans(cand_data: set, cand_mats: set):
    import bpy
    cand_imgs = set()
    for m in list(cand_mats):
        try:
            if m.users == 0:
                if m.node_tree:
                    for n in m.node_tree.nodes:
                        if n.type == "TEX_IMAGE" and n.image is not None:
                            cand_imgs.add(n.image)
                bpy.data.materials.remove(m)
        except ReferenceError:
            pass
    for d in list(cand_data):
        try:
            if d.users != 0:
                continue
            if isinstance(d, bpy.types.Mesh):
                bpy.data.meshes.remove(d)
            elif isinstance(d, bpy.types.Curve):
                bpy.data.curves.remove(d)
            elif isinstance(d, bpy.types.Light):
                bpy.data.lights.remove(d)
            elif isinstance(d, bpy.types.LightProbe):
                bpy.data.lightprobes.remove(d)
        except ReferenceError:
            pass
    for im in list(cand_imgs):
        try:
            if im.users == 0:
                bpy.data.images.remove(im)
        except ReferenceError:
            pass


def _cleanup_detail8():
    """Remove existing DETAIL8_elevator_real objects/materials so apply() is 100% idempotent."""
    import bpy
    coll = bpy.data.collections.get(COLL)
    cand_data, cand_mats = set(), set()
    if coll:
        for name in [o.name for o in coll.objects]:
            ob = bpy.data.objects.get(name)
            if ob is not None:
                _, ms, ds = _remove_tree(ob)
                cand_mats |= ms
                cand_data |= ds
        bpy.data.collections.remove(coll)
    for m in list(bpy.data.materials):
        if m.name.startswith(PFX) and m.users == 0:
            cand_mats.add(m)
    _purge_orphans(cand_data, cand_mats)


def _load_img(fname: str, non_color: bool = False):
    import bpy
    path = str(TEX_DIR / fname)
    for im in list(bpy.data.images):
        if im.name == fname and im.users == 0:
            bpy.data.images.remove(im)
    im = bpy.data.images.load(path, check_existing=False)
    im.name = fname
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    im.pack()
    return im


def _new_mat(name: str):
    import bpy
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf


def _mat_stone(name: str, img_name: str, rough_lo: float, rough_hi: float,
               bump_str: float, diffuse_prev: tuple, hall_ref, tint_mult: float = 1.0):
    """Granite material using real-world metre UVs + subtle per-slab random tonal variation."""
    m, nt, b = _new_mat(name)
    L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = hall_ref

    oinfo = nt.nodes.new("ShaderNodeObjectInfo")
    # Per-slab UV offset so adjacent slabs never show identical speckles
    vadd = nt.nodes.new("ShaderNodeVectorMath")
    vadd.operation = "ADD"
    comb_off = nt.nodes.new("ShaderNodeCombineXYZ")
    mul_off = nt.nodes.new("ShaderNodeMath")
    mul_off.operation = "MULTIPLY"
    mul_off.inputs[1].default_value = 0.67
    L(oinfo.outputs["Random"], mul_off.inputs[0])
    L(oinfo.outputs["Random"], comb_off.inputs["X"])
    L(mul_off.outputs["Value"], comb_off.inputs["Y"])
    L(tc.outputs["UV"], vadd.inputs[0])
    L(comb_off.outputs["Vector"], vadd.inputs[1])

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _load_img(img_name)
    L(vadd.outputs["Vector"], tex.inputs["Vector"])
    nt.nodes.active = tex

    # Subtle slab-to-slab brightness variation (real stone panels)
    rmap = nt.nodes.new("ShaderNodeMapRange")
    rmap.inputs["From Min"].default_value = 0.0
    rmap.inputs["From Max"].default_value = 1.0
    rmap.inputs["To Min"].default_value = 0.94 * tint_mult
    rmap.inputs["To Max"].default_value = 1.05 * tint_mult
    L(oinfo.outputs["Random"], rmap.inputs["Value"])

    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    L(rmap.outputs["Result"], hsv.inputs["Value"])
    L(tex.outputs["Color"], hsv.inputs["Color"])
    L(hsv.outputs["Color"], b.inputs["Base Color"])

    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 14.0
    nz.inputs["Detail"].default_value = 4.0
    L(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.30
    mr.inputs["From Max"].default_value = 0.70
    mr.inputs["To Min"].default_value = rough_lo
    mr.inputs["To Max"].default_value = rough_hi
    L(nz.outputs["Fac"], mr.inputs["Value"])
    L(mr.outputs["Result"], b.inputs["Roughness"])

    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump_str
    bp.inputs["Distance"].default_value = 0.0006
    L(tex.outputs["Color"], bp.inputs["Height"])
    L(bp.outputs["Normal"], b.inputs["Normal"])

    b.inputs["Specular IOR Level"].default_value = 0.55
    m.diffuse_color = (*diffuse_prev, 1.0)
    return m


def _mat_mirror_stainless(name: str, metallic: float = 0.94, rough_lo: float = 0.035, rough_hi: float = 0.08):
    m, nt, b = _new_mat(name)
    L = nt.links.new
    b.inputs["Base Color"].default_value = (0.86, 0.86, 0.85, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Specular IOR Level"].default_value = 0.6

    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.2
    nz.inputs["Detail"].default_value = 2.0
    L(tc.outputs["Object"], nz.inputs["Vector"])

    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.30
    mr.inputs["From Max"].default_value = 0.70
    mr.inputs["To Min"].default_value = rough_lo
    mr.inputs["To Max"].default_value = rough_hi
    L(nz.outputs["Fac"], mr.inputs["Value"])
    L(mr.outputs["Result"], b.inputs["Roughness"])

    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.004
    bp.inputs["Distance"].default_value = 0.0005
    L(nz.outputs["Fac"], bp.inputs["Height"])
    L(bp.outputs["Normal"], b.inputs["Normal"])

    m.diffuse_color = (0.80, 0.81, 0.82, 1.0)
    return m


def _mat_etched_door(name: str, hall_ref):
    """Bright hairline satin stainless door with understated 3-dash (≡) checkerboard etching.

    Calibrated to 02_door_closeup.jpg & 01_front.jpg:
      - Light-medium neutral silver hairline ground (Metallic 0.60 so EEVEE keeps a bright
        brushed-metal body instead of dropping to dark charcoal)
      - Subtle roughness delta (~0.31 satin vs ~0.205 ≡ bars, slightly glossier on lower half
        of the door so gentle reflections catch there as in 02_door_closeup)
      - Soft micro-bump (0.008) so stickers stay clean focal points
    """
    m, nt, b = _new_mat(name)
    L = nt.links.new
    b.inputs["Metallic"].default_value = 0.60
    b.inputs["Specular IOR Level"].default_value = 0.45

    tc_uv = nt.nodes.new("ShaderNodeTexCoord")
    t_col = nt.nodes.new("ShaderNodeTexImage")
    t_col.image = _load_img(TEX_DOOR_COLOR)
    t_rgh = nt.nodes.new("ShaderNodeTexImage")
    t_rgh.image = _load_img(TEX_DOOR_ROUGH, non_color=True)
    t_bmp = nt.nodes.new("ShaderNodeTexImage")
    t_bmp.image = _load_img(TEX_DOOR_BUMP, non_color=True)
    for t in (t_col, t_rgh, t_bmp):
        L(tc_uv.outputs["UV"], t.inputs["Vector"])
    nt.nodes.active = t_col

    L(t_col.outputs["Color"], b.inputs["Base Color"])

    # Gentle vertical roughness bias: lower half of door slightly glossier (-0.04) like photo 02,
    # eye-level around stickers calm and soft (+0.015)
    tc_h = nt.nodes.new("ShaderNodeTexCoord")
    tc_h.object = hall_ref
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L(tc_h.outputs["Object"], sep.inputs["Vector"])
    z_map = nt.nodes.new("ShaderNodeMapRange")
    z_map.inputs["From Min"].default_value = 0.35
    z_map.inputs["From Max"].default_value = 1.45
    z_map.inputs["To Min"].default_value = -0.042
    z_map.inputs["To Max"].default_value = 0.015
    z_map.clamp = True
    L(sep.outputs["Z"], z_map.inputs["Value"])

    # Fine vertical hairline brushing micro-variation along height
    mp_hl = nt.nodes.new("ShaderNodeMapping")
    mp_hl.inputs["Scale"].default_value = (700.0, 700.0, 1.8)
    L(tc_h.outputs["Object"], mp_hl.inputs["Vector"])
    nz_hl = nt.nodes.new("ShaderNodeTexNoise")
    nz_hl.inputs["Scale"].default_value = 1.0
    nz_hl.inputs["Detail"].default_value = 3.0
    L(mp_hl.outputs["Vector"], nz_hl.inputs["Vector"])
    hl_map = nt.nodes.new("ShaderNodeMapRange")
    hl_map.inputs["From Min"].default_value = 0.30
    hl_map.inputs["From Max"].default_value = 0.70
    hl_map.inputs["To Min"].default_value = -0.014
    hl_map.inputs["To Max"].default_value = 0.014
    L(nz_hl.outputs["Fac"], hl_map.inputs["Value"])

    r_add1 = nt.nodes.new("ShaderNodeMath")
    r_add1.operation = "ADD"
    L(t_rgh.outputs["Color"], r_add1.inputs[0])
    L(z_map.outputs["Result"], r_add1.inputs[1])

    r_add2 = nt.nodes.new("ShaderNodeMath")
    r_add2.operation = "ADD"
    r_add2.use_clamp = True
    L(r_add1.outputs["Value"], r_add2.inputs[0])
    L(hl_map.outputs["Result"], r_add2.inputs[1])
    L(r_add2.outputs["Value"], b.inputs["Roughness"])

    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.008
    bp.inputs["Distance"].default_value = 0.0002
    L(t_bmp.outputs["Color"], bp.inputs["Height"])
    L(bp.outputs["Normal"], b.inputs["Normal"])

    m.diffuse_color = (0.76, 0.76, 0.75, 1.0)
    return m


def _mat_simple(name: str, color: tuple, rough: float = 0.4, metal: float = 0.0,
                emit: tuple | None = None, emit_str: float = 0.0):
    m, _, b = _new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit is not None and emit_str > 0:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = emit_str
    m.diffuse_color = (*color, 1.0)
    return m


def _mat_pvc_sticker(name: str, fname: str, diffuse_prev: tuple = (0.84, 0.84, 0.82)):
    """Semi-gloss weathered PVC vinyl sticker shader (thin specular sheen + subtle vinyl waviness)."""
    m, nt, b = _new_mat(name)
    L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord")

    t_col = nt.nodes.new("ShaderNodeTexImage")
    t_col.image = _load_img(fname)
    t_col.extension = "EXTEND"
    L(tc.outputs["UV"], t_col.inputs["Vector"])
    L(t_col.outputs["Color"], b.inputs["Base Color"])
    nt.nodes.active = t_col

    t_rgh = nt.nodes.new("ShaderNodeTexImage")
    t_rgh.image = _load_img(TEX_STICKER_ROUGH, non_color=True)
    t_rgh.extension = "EXTEND"
    L(tc.outputs["UV"], t_rgh.inputs["Vector"])
    L(t_rgh.outputs["Color"], b.inputs["Roughness"])

    # Thin PVC film semi-gloss specular + subtle clearcoat sheen catching hallway reflections
    b.inputs["Specular IOR Level"].default_value = 0.52
    b.inputs["Coat Weight"].default_value = 0.28
    b.inputs["Coat Roughness"].default_value = 0.15

    # Ultra-subtle vinyl adhesive waviness / surface micro-ripple
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 22.0
    nz.inputs["Detail"].default_value = 3.0
    L(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.014
    bp.inputs["Distance"].default_value = 0.0004
    L(nz.outputs["Fac"], bp.inputs["Height"])
    L(bp.outputs["Normal"], b.inputs["Normal"])

    m.diffuse_color = (*diffuse_prev, 1.0)
    return m


def _add_pvc_sticker_x(coll, parent, name: str, x_back: float, y0: float, y1: float,
                       z0: float, z1: float, mat_face, mat_edge,
                       thickness: float = 0.00075, corner_r: float = 0.0048,
                       lift_side: str = "left"):
    """3D rounded-corner PVC vinyl sticker facing +X with thin physical thickness and subtle corner lift."""
    import bmesh, bpy
    yc, zc = (y0 + y1) * 0.5, (z0 + z1) * 0.5
    hw, hh = (y1 - y0) * 0.5, (z1 - z0) * 0.5
    r = min(corner_r, hw * 0.4, hh * 0.4)
    n_seg = 6

    # Build CCW rounded-rectangle boundary in local (ly, lz)
    corners = [
        ( hw - r, -hh + r, -math.pi / 2, 0.0),           # bottom-right
        ( hw - r,  hh - r,  0.0,         math.pi / 2),   # top-right
        (-hw + r,  hh - r,  math.pi / 2, math.pi),       # top-left
        (-hw + r, -hh + r,  math.pi,     1.5 * math.pi), # bottom-left
    ]
    pts = []
    for cy_c, cz_c, a0, a1 in corners:
        for i in range(n_seg + 1):
            a = a0 + (a1 - a0) * (i / n_seg)
            pts.append((cy_c + r * math.cos(a), cz_c + r * math.sin(a)))

    # Subtle physical corner lift (~0.28 mm max at outer/bottom corners so edge catches micro shadow)
    def lift(py, pz):
        u = (py + hw) / (2.0 * hw)  # 0=left, 1=right
        v = (pz + hh) / (2.0 * hh)  # 0=bottom, 1=top
        # Lift very gently at outer corners (especially bottom-outer and top-outer)
        outer = (1.0 - u) if lift_side == "left" else u
        c_bot = max(0.0, outer - 0.68) * max(0.0, (1.0 - v) - 0.65)
        c_top = max(0.0, outer - 0.72) * max(0.0, v - 0.72)
        return (c_bot * 2.6 + c_top * 1.4) * 0.0010

    bm = bmesh.new()
    back_v = [bm.verts.new((lift(py, pz), py, pz)) for py, pz in pts]
    front_v = [bm.verts.new((thickness + lift(py, pz), py, pz)) for py, pz in pts]
    n = len(pts)

    # Back face (hidden against door) & Front printed face (material 0)
    bm.faces.new(back_v[::-1])
    f_front = bm.faces.new(front_v)
    f_front.material_index = 0
    # Rounded vinyl side rim (material 1: slightly dirty off-white PVC edge)
    for i in range(n):
        j = (i + 1) % n
        sf = bm.faces.new((back_v[i], back_v[j], front_v[j], front_v[i]))
        sf.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if f_front.normal.x < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)

    # Crisp 0..1 UV mapping across front face
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = ((co.y + hw) / (2.0 * hw), (co.z + hh) / (2.0 * hh))

    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat_face)
    me.materials.append(mat_edge)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = (x_back, yc, zc)
    return ob


def _mat_textured_card(name: str, fname: str, rough: float = 0.30, use_alpha: bool = False,
                       emit_strength: float = 0.0, diffuse_prev: tuple = (0.85, 0.85, 0.85)):
    m, nt, b = _new_mat(name)
    L = nt.links.new
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _load_img(fname)
    tex.extension = "EXTEND"
    L(tex.outputs["Color"], b.inputs["Base Color"])
    nt.nodes.active = tex
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.45
    if use_alpha:
        L(tex.outputs["Alpha"], b.inputs["Alpha"])
    if emit_strength > 0.0:
        L(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit_strength
    m.diffuse_color = (*diffuse_prev, 1.0)
    return m


# ---- Geometry builders (all in Sangga_Hallway_Ext local coords) ----
def _assign_box_world_uv(bm, ctr, uv_scale_m: float):
    """Box-project UVMap in hallway-local metres (distortion-free on both vertical and horizontal faces)."""
    uv = bm.loops.layers.uv.verify()
    inv = 1.0 / uv_scale_m
    for f in bm.faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            p = loop.vert.co + ctr
            if az >= ax and az >= ay:
                loop[uv].uv = (p.y * inv, p.x * inv)
            elif ax >= ay:
                loop[uv].uv = (p.y * inv, p.z * inv)
            else:
                loop[uv].uv = (p.x * inv, p.z * inv)


def _add_box(coll, parent, name: str, lo: tuple, hi: tuple, mat, bevel: float = 0.0, uv_scale: float | None = None):
    import bmesh, bpy
    from mathutils import Matrix, Vector
    bm = bmesh.new()
    lo_v, hi_v = Vector(lo), Vector(hi)
    ctr = (lo_v + hi_v) * 0.5
    sz = hi_v - lo_v
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((sz.x, sz.y, sz.z, 1.0)))
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1,
                        affect="EDGES", profile=0.5, clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if uv_scale is not None:
        _assign_box_world_uv(bm, ctr, uv_scale)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = ctr
    return ob


def _add_uv_plane_x(coll, parent, name: str, x: float, y0: float, y1: float, z0: float, z1: float, mat):
    """Single quad facing +X (toward corridor viewer). Viewer's LEFT = y0, RIGHT = y1."""
    import bmesh, bpy
    bm = bmesh.new()
    v0 = bm.verts.new((0.0, y0 - (y0 + y1) / 2, z0 - (z0 + z1) / 2))
    v1 = bm.verts.new((0.0, y1 - (y0 + y1) / 2, z0 - (z0 + z1) / 2))
    v2 = bm.verts.new((0.0, y1 - (y0 + y1) / 2, z1 - (z0 + z1) / 2))
    v3 = bm.verts.new((0.0, y0 - (y0 + y1) / 2, z1 - (z0 + z1) / 2))
    f = bm.faces.new((v0, v1, v2, v3))
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, co in zip(f.loops, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]):
        loop[uv].uv = co
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if f.normal.x < 0:
        bmesh.ops.reverse_faces(bm, faces=[f])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = (x, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
    return ob


def _add_splayed_jamb(coll, parent, name: str, x_back: float, x_front: float,
                      y_front_outer: float, y_front_inner: float, y_back_inner: float,
                      z0: float, z1: float, mat):
    """Thick mirror-stainless side jamb with narrow front face + deep slightly-splayed return wall."""
    import bmesh, bpy
    bm = bmesh.new()
    pts = [
        (x_back,  y_front_outer),
        (x_front, y_front_outer),
        (x_front, y_front_inner),
        (x_back,  y_back_inner),
    ]
    bot = [bm.verts.new((px, py, z0)) for px, py in pts]
    top = [bm.verts.new((px, py, z1)) for px, py in pts]
    bm.faces.new(bot[::-1])
    bm.faces.new(top)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0012, segments=1,
                    affect="EDGES", profile=0.5, clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    return ob


def _add_arched_indicator(coll, parent, name: str, x_back: float, x_front: float,
                          y_ctr: float, half_w: float, z_bot: float, h_side: float, h_ctr: float,
                          mat_body, mat_face):
    """Glossy black arched display window (flat bottom, gentle convex arch top, matching crop_transom.jpg)."""
    import bmesh, bpy
    n_arc = 32
    pts = [(y_ctr - half_w, z_bot), (y_ctr + half_w, z_bot)]
    for i in range(n_arc + 1):
        t = 1.0 - i / n_arc
        u = (t * 2.0) - 1.0
        py = y_ctr + u * half_w
        arch = (1.0 - u * u)
        pz = z_bot + h_side + (h_ctr - h_side) * arch
        pts.append((py, pz))

    bm = bmesh.new()
    back_v = [bm.verts.new((x_back, py, pz)) for py, pz in pts]
    front_v = [bm.verts.new((x_front, py, pz)) for py, pz in pts]
    n = len(pts)
    bm.faces.new(back_v[::-1])
    f_front = bm.faces.new(front_v)
    f_front.material_index = 1
    for i in range(n):
        j = (i + 1) % n
        sf = bm.faces.new((back_v[i], back_v[j], front_v[j], front_v[i]))
        sf.material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    uv = bm.loops.layers.uv.new("UVMap")
    y_min, y_max = y_ctr - half_w, y_ctr + half_w
    z_min, z_max = z_bot, z_bot + h_ctr
    for loop in f_front.loops:
        co = loop.vert.co
        loop[uv].uv = ((co.y - y_min) / (y_max - y_min), (co.z - z_min) / (z_max - z_min))

    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat_body)
    me.materials.append(mat_face)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    return ob


def _add_gold_3d_text(coll, parent, name: str, text: str, loc: tuple, size: float,
                      extrude: float, bevel: float, mat):
    import bpy
    fc = bpy.data.curves.new(name + "_curve", "FONT")
    fc.body = text
    fc.size = size
    fc.align_x = "CENTER"
    fc.align_y = "CENTER"
    fc.extrude = extrude
    fc.bevel_depth = bevel
    fc.bevel_resolution = 2
    fc.space_character = 1.04
    if os.path.exists(FONT_3D_BOLD):
        fc.font = bpy.data.fonts.load(FONT_3D_BOLD, check_existing=True)
    ob = bpy.data.objects.new(name, fc)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = (math.pi / 2.0, 0.0, math.pi / 2.0)
    ob.data.materials.append(mat)
    return ob


def _add_call_button_assembly(coll, parent, ex_front: float, y_ctr: float, z_bot: float,
                              mat_black, mat_braille, mat_bezel, mat_chrome, mat_top, mat_wc, mat_led):
    """Left-pier vertical black call button panel matching crop_callbtn.jpg."""
    import bmesh, bpy
    from mathutils import Matrix

    added = []
    pw = 0.102
    ph = 0.300
    pd = 0.008
    y0, y1 = y_ctr - pw / 2.0, y_ctr + pw / 2.0
    z1 = z_bot + ph

    added.append(_add_box(coll, parent, PFX + "CallPanel_Bezel",
                          (ex_front - 0.002, y0 - 0.004, z_bot - 0.004),
                          (ex_front + pd - 0.001, y1 + 0.004, z1 + 0.004), mat_bezel, bevel=0.0012))
    added.append(_add_box(coll, parent, PFX + "CallPanel_Face",
                          (ex_front, y0, z_bot), (ex_front + pd, y1, z1), mat_black, bevel=0.001))

    xf = ex_front + pd + 0.0007
    # 1) Top service-floor sign plaque flush across full bezel width (as in crop_callbtn)
    added.append(_add_box(coll, parent, PFX + "CallPanel_TopBacking",
                          (ex_front + pd, y0 - 0.004, z1 - 0.056),
                          (ex_front + pd + 0.002, y1 + 0.004, z1 + 0.003), mat_bezel, bevel=0.0005))
    added.append(_add_uv_plane_x(coll, parent, PFX + "CallPanel_TopSign",
                                 ex_front + pd + 0.0024, y0 - 0.003, y1 + 0.003, z1 - 0.055, z1 + 0.002, mat_top))

    # 2) Blue square wheelchair accessibility badge
    wc_s = 0.044
    wc_z0 = z_bot + 0.168
    added.append(_add_uv_plane_x(coll, parent, PFX + "CallPanel_Wheelchair",
                                 xf, y_ctr - wc_s / 2.0, y_ctr + wc_s / 2.0, wc_z0, wc_z0 + wc_s, mat_wc))

    # 3) Tactile braille plate right below wheelchair icon (real 3D braille dots)
    bm = bmesh.new()
    br_z0, br_z1 = z_bot + 0.122, z_bot + 0.156
    br_w = 0.044
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((ex_front + pd + 0.0012, y_ctr, (br_z0 + br_z1) / 2))
                          @ Matrix.Diagonal((0.0024, br_w, br_z1 - br_z0, 1.0)))
    for r in range(2):
        for c in range(6):
            by = y_ctr - 0.015 + c * 0.006
            bz = br_z0 + 0.010 + r * 0.012
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.0013,
                                       matrix=Matrix.Translation((ex_front + pd + 0.0025, by, bz)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me_br = bpy.data.meshes.new(PFX + "CallPanel_Braille")
    bm.to_mesh(me_br)
    bm.free()
    me_br.materials.append(mat_braille)
    ob_br = bpy.data.objects.new(PFX + "CallPanel_Braille", me_br)
    coll.objects.link(ob_br)
    ob_br.parent = parent
    added.append(ob_br)

    # 4) Single oval/circular call button with shiny chrome ring + dark cap + glowing symbol
    btn_z = z_bot + 0.072
    bm_r = bmesh.new()
    bmesh.ops.create_cone(bm_r, cap_ends=True, segments=28, radius1=0.019, radius2=0.018, depth=0.005,
                          matrix=Matrix.Translation((ex_front + pd + 0.0025, y_ctr, btn_z))
                          @ Matrix.Rotation(math.pi / 2, 4, "Y")
                          @ Matrix.Diagonal((0.82, 1.08, 1.0, 1.0)))
    bmesh.ops.recalc_face_normals(bm_r, faces=bm_r.faces)
    me_r = bpy.data.meshes.new(PFX + "CallBtn_Ring")
    bm_r.to_mesh(me_r)
    bm_r.free()
    me_r.materials.append(mat_chrome)
    ob_r = bpy.data.objects.new(PFX + "CallBtn_Ring", me_r)
    coll.objects.link(ob_r)
    ob_r.parent = parent
    added.append(ob_r)

    bm_b = bmesh.new()
    bmesh.ops.create_cone(bm_b, cap_ends=True, segments=28, radius1=0.0155, radius2=0.015, depth=0.006,
                          matrix=Matrix.Translation((ex_front + pd + 0.0032, y_ctr, btn_z))
                          @ Matrix.Rotation(math.pi / 2, 4, "Y")
                          @ Matrix.Diagonal((0.82, 1.08, 1.0, 1.0)))
    bmesh.ops.recalc_face_normals(bm_b, faces=bm_b.faces)
    me_b = bpy.data.meshes.new(PFX + "CallBtn_Cap")
    bm_b.to_mesh(me_b)
    bm_b.free()
    me_b.materials.append(mat_black)
    ob_b = bpy.data.objects.new(PFX + "CallBtn_Cap", me_b)
    coll.objects.link(ob_b)
    ob_b.parent = parent
    added.append(ob_b)

    added.append(_add_box(coll, parent, PFX + "CallBtn_Symbol",
                          (ex_front + pd + 0.0060, y_ctr - 0.0025, btn_z - 0.005),
                          (ex_front + pd + 0.0068, y_ctr + 0.0025, btn_z + 0.005), mat_led))

    bm_k = bmesh.new()
    bmesh.ops.create_cone(bm_k, cap_ends=True, segments=16, radius1=0.0042, radius2=0.0042, depth=0.003,
                          matrix=Matrix.Translation((ex_front + pd + 0.001, y_ctr, z_bot + 0.022))
                          @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    bmesh.ops.recalc_face_normals(bm_k, faces=bm_k.faces)
    me_k = bpy.data.meshes.new(PFX + "CallPanel_Screw")
    bm_k.to_mesh(me_k)
    bm_k.free()
    me_k.materials.append(mat_chrome)
    ob_k = bpy.data.objects.new(PFX + "CallPanel_Screw", me_k)
    coll.objects.link(ob_k)
    ob_k.parent = parent
    added.append(ob_k)
    return added


def apply() -> dict:
    import bpy

    needed = [TEX_LIGHT_GRANITE, TEX_DARK_GRANITE, TEX_DOOR_COLOR, TEX_DOOR_ROUGH, TEX_DOOR_BUMP,
              TEX_STICKER_L, TEX_STICKER_R, TEX_STICKER_ROUGH, TEX_INDICATOR, TEX_CALL_TOP, TEX_CALL_WC, TEX_EVAC_MAP]
    if any(not (TEX_DIR / f).exists() for f in needed):
        gen_textures()

    _cleanup_detail8()

    ext = bpy.data.objects["Sangga_Hallway_Ext"]
    hall = bpy.data.objects["Sangga_Hallway"]
    set_c = bpy.data.collections["SET"]
    coll = bpy.data.collections.new(COLL)
    set_c.children.link(coll)

    # Delete superseded old elevator objects & orphan data/materials (never keep hidden originals)
    removed_count = 0
    cand_mats, cand_data = set(), set()
    for name in REMOVE_EXACT:
        ob = bpy.data.objects.get(name)
        if ob is not None:
            r, ms, ds = _remove_tree(ob)
            removed_count += r
            cand_mats |= ms
            cand_data |= ds
    _purge_orphans(cand_data, cand_mats)

    # ---- Materials ----
    m_light_stone = _mat_stone(PFX + "LightGranite", TEX_LIGHT_GRANITE, 0.24, 0.34, 0.06,
                               (0.65, 0.66, 0.65), hall, tint_mult=1.0)
    m_dark_stone = _mat_stone(PFX + "DarkGranite", TEX_DARK_GRANITE, 0.14, 0.24, 0.05,
                              (0.20, 0.21, 0.22), hall, tint_mult=1.0)
    m_grout = _mat_simple(PFX + "StoneGrout", (0.14, 0.15, 0.16), rough=0.82, metal=0.0)
    m_mirror_ss = _mat_mirror_stainless(PFX + "MirrorStainless", metallic=0.90, rough_lo=0.035, rough_hi=0.08)
    m_jamb_ss = _mat_mirror_stainless(PFX + "JambStainless", metallic=0.88, rough_lo=0.04, rough_hi=0.08)
    m_door_etch = _mat_etched_door(PFX + "DoorEtched", hall)
    m_dark_seam = _mat_simple(PFX + "DarkSeam", (0.02, 0.02, 0.025), rough=0.75, metal=0.0)
    m_ind_body = _mat_simple(PFX + "IndicatorBody", (0.015, 0.015, 0.018), rough=0.08, metal=0.05)
    m_ind_face = _mat_textured_card(PFX + "IndicatorFace", TEX_INDICATOR, rough=0.06,
                                    emit_strength=6.0, diffuse_prev=(0.05, 0.02, 0.02))
    m_stick_l = _mat_pvc_sticker(PFX + "StickerL", TEX_STICKER_L, diffuse_prev=(0.82, 0.84, 0.83))
    m_stick_r = _mat_pvc_sticker(PFX + "StickerR", TEX_STICKER_R, diffuse_prev=(0.82, 0.80, 0.62))
    m_stick_edge = _mat_simple(PFX + "StickerEdge", (0.72, 0.70, 0.66), rough=0.45, metal=0.0)
    m_call_black = _mat_simple(PFX + "CallBlack", (0.020, 0.022, 0.026), rough=0.14, metal=0.12)
    m_call_braille = _mat_simple(PFX + "CallBraille", (0.065, 0.070, 0.078), rough=0.35, metal=0.15)
    m_call_bezel = _mat_simple(PFX + "CallBezel", (0.28, 0.29, 0.31), rough=0.28, metal=0.82)
    m_call_chrome = _mat_simple(PFX + "CallChrome", (0.86, 0.87, 0.89), rough=0.10, metal=0.96)
    m_call_top = _mat_textured_card(PFX + "CallTop", TEX_CALL_TOP, rough=0.28, diffuse_prev=(0.80, 0.84, 0.90))
    m_call_wc = _mat_textured_card(PFX + "CallWheelchair", TEX_CALL_WC, rough=0.26, diffuse_prev=(0.12, 0.35, 0.68))
    m_call_led = _mat_simple(PFX + "CallLed", (0.95, 0.96, 1.0), rough=0.2,
                             emit=(0.95, 0.97, 1.0), emit_str=3.5)
    m_brass = _mat_simple(PFX + "BrassGold", (0.68, 0.53, 0.20), rough=0.23, metal=0.94)
    m_evac_back = _mat_simple(PFX + "EvacAcrylic", (0.92, 0.92, 0.93), rough=0.26, metal=0.0)
    m_evac_face = _mat_textured_card(PFX + "EvacMap", TEX_EVAC_MAP, rough=0.24, diffuse_prev=(0.90, 0.85, 0.85))

    # ---- Layout coordinates (Sangga_Hallway_Ext local metres) ----
    ex = -11.500
    ex_dark = -11.486
    ex_trim = -11.479
    ex_transom = -11.483
    ex_door = -11.735

    y_min, y_max = -0.020, 2.880
    y_ctr = 1.420

    ys0, ys1 = 0.660, 2.180
    zs_top = 2.650

    yp0, yp1 = 0.900, 1.940
    zp_top = 2.240
    z_door_top = 1.945
    trim_w = 0.022

    z_skirt = 0.095
    z_b1_0, z_b1_1 = 1.240, 1.315
    z_b2_0, z_b2_1 = 2.310, 2.385
    z_ceil = 2.755
    gap = 0.0025

    uv_light = 0.68
    uv_dark = 0.82
    uv_etch = 0.040  # 4x4 cells = 40 mm -> each checkerboard square = 10 mm

    added = []

    # ---- 1) Recessed grout backing behind entire elevator wall ----
    added.append(_add_box(coll, ext, PFX + "WallGroutBack_L",
                          (ex - 0.06, y_min, 0.0), (ex - 0.003, yp0 + 0.02, z_ceil), m_grout))
    added.append(_add_box(coll, ext, PFX + "WallGroutBack_R",
                          (ex - 0.06, yp1 - 0.02, 0.0), (ex - 0.003, y_max, z_ceil), m_grout))
    added.append(_add_box(coll, ext, PFX + "WallGroutBack_Top",
                          (ex - 0.06, yp0, z_door_top), (ex - 0.003, yp1, z_ceil), m_grout))

    # ---- 2) Light speckled granite wall slabs + 2 dark horizontal bands + dark skirting ----
    light_z_courses = [
        (z_skirt + gap, 0.670 - gap / 2, "C1"),
        (0.670 + gap / 2, z_b1_0 - gap, "C2"),
        (z_b1_1 + gap, 1.825 - gap / 2, "C3"),
        (1.825 + gap / 2, z_b2_0 - gap, "C4"),
        (z_b2_1 + gap, z_ceil, "C5"),
    ]
    for side, ya, yb in (("L", y_min, ys0 - gap), ("R", ys1 + gap, y_max)):
        added.append(_add_box(coll, ext, f"{PFX}Skirt_{side}",
                              (ex - 0.018, ya, 0.0), (ex + 0.002, yb, z_skirt),
                              m_dark_stone, bevel=0.0012, uv_scale=uv_dark))
        for bi, (zb0, zb1) in enumerate(((z_b1_0, z_b1_1), (z_b2_0, z_b2_1))):
            added.append(_add_box(coll, ext, f"{PFX}DarkBand_{side}{bi}",
                                  (ex - 0.018, ya, zb0), (ex + 0.001, yb, zb1),
                                  m_dark_stone, bevel=0.0012, uv_scale=uv_dark))
        for z0, z1, tag in light_z_courses:
            added.append(_add_box(coll, ext, f"{PFX}LightSlab_{side}_{tag}",
                                  (ex - 0.018, ya, z0), (ex, yb, z1),
                                  m_light_stone, bevel=0.0014, uv_scale=uv_light))

    for side, ya, yb in (("L", ys0, y_ctr - gap / 2), ("R", y_ctr + gap / 2, ys1)):
        added.append(_add_box(coll, ext, f"{PFX}LightSlab_Over_{side}",
                              (ex - 0.018, ya, zs_top + gap), (ex, yb, z_ceil),
                              m_light_stone, bevel=0.0012, uv_scale=uv_light))

    # ---- 3) Dark gray granite elevator surround (exact slab cuts of ref 01_front: only center seam above frame!) ----
    # Left & Right piers stop cleanly at zp_top (top of stainless frame), split at z_b1_0 (above call button)
    pier_z = [
        (0.000, z_b1_0 - gap / 2, "Bot"),
        (z_b1_0 + gap / 2, zp_top - gap / 2, "Mid"),
    ]
    for side, ya, yb in (("L", ys0, yp0), ("R", yp1, ys1)):
        for z0, z1, tag in pier_z:
            added.append(_add_box(coll, ext, f"{PFX}DarkPier_{side}_{tag}",
                                  (ex - 0.015, ya, z0), (ex_dark, yb, z1),
                                  m_dark_stone, bevel=0.0018, uv_scale=uv_dark))

    # Full-width lintel band directly above stainless frame (zp_top .. z_b2_1), split ONLY at center y_ctr
    for side, ya, yb in (("L", ys0, y_ctr - gap / 2), ("R", y_ctr + gap / 2, ys1)):
        added.append(_add_box(coll, ext, f"{PFX}DarkLintel_{side}",
                              (ex - 0.015, ya, zp_top + gap / 2), (ex_dark, yb, z_b2_1 - gap / 2),
                              m_dark_stone, bevel=0.0018, uv_scale=uv_dark))

    # Full-width upper header slabs (z_b2_1 .. zs_top), split ONLY at center y_ctr
    for side, ya, yb in (("L", ys0, y_ctr - gap / 2), ("R", y_ctr + gap / 2, ys1)):
        added.append(_add_box(coll, ext, f"{PFX}DarkHeader_{side}",
                              (ex - 0.015, ya, z_b2_1 + gap / 2), (ex_dark, yb, zs_top),
                              m_dark_stone, bevel=0.0018, uv_scale=uv_dark))

    # ---- 4) Dark granite threshold slab inside portal recess + front floor border strip ----
    added.append(_add_box(coll, ext, PFX + "Threshold_Slab",
                          (ex_door + 0.005, yp0 + 0.015, -0.002), (ex_dark + 0.002, yp1 - 0.015, 0.0055),
                          m_dark_stone, bevel=0.001, uv_scale=uv_dark))
    border_x0, border_x1 = ex_dark + 0.003, -11.355
    for tag, ya, yb in (("L", y_min, ys0 - gap), ("CL", ys0, y_ctr - gap / 2),
                        ("CR", y_ctr + gap / 2, ys1), ("R", ys1 + gap, y_max)):
        added.append(_add_box(coll, ext, f"{PFX}FloorBorder_{tag}",
                              (border_x0, ya, -0.002), (border_x1, yb, 0.0052),
                              m_dark_stone, bevel=0.0008, uv_scale=uv_dark))
    added.append(_add_box(coll, ext, PFX + "DoorTrackSill",
                          (ex_door - 0.035, yp0 + 0.02, -0.001), (ex_door + 0.005, yp1 - 0.02, 0.007),
                          m_mirror_ss, bevel=0.0008))

    # ---- 5) Mirror-finish stainless portal trim, deep splayed side jambs, soffit & transom ----
    added.append(_add_box(coll, ext, PFX + "FrameTrim_L",
                          (ex_dark - 0.006, yp0, 0.004), (ex_trim, yp0 + trim_w, zp_top), m_mirror_ss, bevel=0.0012))
    added.append(_add_box(coll, ext, PFX + "FrameTrim_R",
                          (ex_dark - 0.006, yp1 - trim_w, 0.004), (ex_trim, yp1, zp_top), m_mirror_ss, bevel=0.0012))
    added.append(_add_box(coll, ext, PFX + "FrameTrim_Top",
                          (ex_dark - 0.006, yp0 + trim_w - 0.001, zp_top - trim_w),
                          (ex_trim - 0.0005, yp1 - trim_w + 0.001, zp_top), m_mirror_ss, bevel=0.0012))

    y_open_l_front = yp0 + trim_w
    y_open_r_front = yp1 - trim_w
    y_open_l_back = y_open_l_front + 0.026
    y_open_r_back = y_open_r_front - 0.026
    added.append(_add_splayed_jamb(coll, ext, PFX + "Jamb_L",
                                   ex_door - 0.006, ex_transom + 0.001,
                                   yp0 + 0.006, y_open_l_front, y_open_l_back,
                                   0.004, z_door_top + 0.002, m_jamb_ss))
    added.append(_add_splayed_jamb(coll, ext, PFX + "Jamb_R",
                                   ex_door - 0.006, ex_transom + 0.001,
                                   yp1 - 0.006, y_open_r_front, y_open_r_back,
                                   0.004, z_door_top + 0.002, m_jamb_ss))

    added.append(_add_box(coll, ext, PFX + "Soffit",
                          (ex_door - 0.01, y_open_l_front, z_door_top),
                          (ex_transom, y_open_r_front, z_door_top + 0.026), m_jamb_ss, bevel=0.001))

    added.append(_add_box(coll, ext, PFX + "Transom_Panel",
                          (ex_transom - 0.035, y_open_l_front, z_door_top),
                          (ex_transom, y_open_r_front, zp_top - trim_w), m_mirror_ss, bevel=0.0012))

    # ---- 6) Arched black floor indicator window ('↓3' red dot-matrix) ----
    added.append(_add_arched_indicator(coll, ext, PFX + "FloorIndicator",
                                       x_back=ex_transom - 0.002, x_front=ex_transom + 0.006,
                                       y_ctr=y_ctr, half_w=0.295,
                                       z_bot=z_door_top + 0.042, h_side=0.052, h_ctr=0.084,
                                       mat_body=m_ind_body, mat_face=m_ind_face))

    # ---- 7) Twin checkerboard-etched stainless doors + center seam + dark shaft backing ----
    door_gap = 0.006
    door_l_y0, door_l_y1 = y_open_l_back - 0.010, y_ctr - door_gap / 2.0
    door_r_y0, door_r_y1 = y_ctr + door_gap / 2.0, y_open_r_back + 0.010
    door_l = _add_box(coll, ext, PFX + "Door_L",
                      (ex_door - 0.032, door_l_y0, 0.007), (ex_door, door_l_y1, z_door_top + 0.006),
                      m_door_etch, bevel=0.0016, uv_scale=uv_etch)
    door_r = _add_box(coll, ext, PFX + "Door_R",
                      (ex_door - 0.032, door_r_y0, 0.007), (ex_door, door_r_y1, z_door_top + 0.006),
                      m_door_etch, bevel=0.0016, uv_scale=uv_etch)
    added.extend([door_l, door_r])
    added.append(_add_box(coll, ext, PFX + "DoorCenterSeam",
                          (ex_door - 0.038, y_ctr - 0.007, 0.006), (ex_door - 0.0025, y_ctr + 0.007, z_door_top + 0.005),
                          m_dark_seam))
    added.append(_add_box(coll, ext, PFX + "ShaftBacking",
                          (ex_door - 0.090, yp0, -0.01), (ex_door - 0.045, yp1, z_door_top + 0.03),
                          m_dark_seam))

    # ---- 8) Two 3D weathered PVC warning stickers parented to Door_L & Door_R ----
    st_w, st_h = 0.112, 0.117
    st_z0 = 1.495
    st_gap = 0.0045
    dl_c = door_l.location
    dr_c = door_r.location
    added.append(_add_pvc_sticker_x(
        coll, door_l, PFX + "Sticker_L",
        (ex_door + 0.0002) - dl_c.x,
        (y_ctr - door_gap / 2 - st_gap - st_w) - dl_c.y,
        (y_ctr - door_gap / 2 - st_gap) - dl_c.y,
        st_z0 - dl_c.z, (st_z0 + st_h) - dl_c.z,
        m_stick_l, m_stick_edge, thickness=0.0008, corner_r=0.0048, lift_side="left",
    ))
    added.append(_add_pvc_sticker_x(
        coll, door_r, PFX + "Sticker_R",
        (ex_door + 0.0002) - dr_c.x,
        (y_ctr + door_gap / 2 + st_gap) - dr_c.y,
        (y_ctr + door_gap / 2 + st_gap + st_w) - dr_c.y,
        st_z0 - dr_c.z, (st_z0 + st_h) - dr_c.z,
        m_stick_r, m_stick_edge, thickness=0.0008, corner_r=0.0048, lift_side="right",
    ))

    # ---- 9) Left-pier call button panel ----
    pier_l_ctr = (ys0 + yp0) / 2.0
    added.extend(_add_call_button_assembly(
        coll, ext, ex_dark, pier_l_ctr, z_bot=0.900,
        mat_black=m_call_black, mat_braille=m_call_braille, mat_bezel=m_call_bezel,
        mat_chrome=m_call_chrome, mat_top=m_call_top, mat_wc=m_call_wc, mat_led=m_call_led,
    ))

    # ---- 10) Left light-granite wall: 3D Brass '3F' floor letters + red-header '피난안내도' ----
    left_wall_ctr = ys0 / 2.0
    added.append(_add_gold_3d_text(coll, ext, PFX + "FloorSign_3F", "3F",
                                   loc=(ex + 0.010, left_wall_ctr, 1.840),
                                   size=0.175, extrude=0.011, bevel=0.002, mat=m_brass))
    ev_w, ev_h = 0.315, 0.235
    ev_z0 = 1.470
    added.append(_add_box(coll, ext, PFX + "EvacMap_Plaque",
                          (ex, left_wall_ctr - ev_w / 2, ev_z0),
                          (ex + 0.005, left_wall_ctr + ev_w / 2, ev_z0 + ev_h), m_evac_back, bevel=0.0008))
    added.append(_add_uv_plane_x(coll, ext, PFX + "EvacMap_Face",
                                 ex + 0.0056, left_wall_ctr - ev_w / 2 + 0.001, left_wall_ctr + ev_w / 2 - 0.001,
                                 ev_z0 + 0.001, ev_z0 + ev_h - 0.001, m_evac_face))

    # ---- 11) Planar reflection probes: one right on door plane + one right on mirror transom ----
    # Exact plane alignment gives crisp 1:1 mirror reflections in EEVEE with zero restroom-mirror bleed
    probe = bpy.data.objects.get("D4elev_DoorPlaneProbe")
    if probe is not None and probe.type == "LIGHT_PROBE":
        probe.location = (-8.97, -17.270, 0.98)
        probe.rotation_euler = (math.radians(-90), 0.0, 0.0)
        probe.scale = (0.52, 1.02, 1.0)
        probe.data.influence_distance = 0.08

    lp_t = bpy.data.lightprobes.new(PFX + "TransomPlaneProbe", "PLANE")
    lp_t.influence_distance = 0.06
    pr_t = bpy.data.objects.new(PFX + "TransomPlaneProbe", lp_t)
    coll.objects.link(pr_t)
    pr_t.location = (-8.97, -17.026, 2.09)
    pr_t.rotation_euler = (math.radians(-90), 0.0, 0.0)
    pr_t.scale = (0.55, 0.20, 1.0)

    bpy.context.view_layer.update()
    tris = 0
    for ob in coll.objects:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            tris += len(ob.data.loop_triangles)
    return {
        "collection": COLL,
        "objects_added": len(coll.objects),
        "triangles_added": tris,
        "old_objects_deleted": removed_count,
    }


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if "--gen-door-textures" in argv:
        TEX_DIR.mkdir(parents=True, exist_ok=True)
        _gen_door_etch_tiles()
        print(f"Generated door etch textures in {TEX_DIR}")
        return
    if "--gen-textures" in argv:
        gen_textures()
        return
    info = apply()
    print("D8ELEV APPLY", info, flush=True)
    if "--save" in argv:
        import bpy
        out = argv[argv.index("--save") + 1]
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print("D8ELEV SAVED", out, flush=True)


if __name__ == "__main__":
    _main()
