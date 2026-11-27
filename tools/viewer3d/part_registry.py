"""Canonical part name normalization, role classification, and material presets for the 3D app viewer.

4-tier safety classification (from work/app_machine_plan/REPORT.md):
  - LOCKED_GRIP    : matches grip_objects() in build_v5_hand_viewer_copy.py -> geometry & animation 100% untouched
  - SURFACE_LOCKED : body-contact surfaces (seat, backrest, rollers) -> contact plane/outer radius locked <= 0.5 mm
  - SHELL_UPGRADE  : structural/visual parts -> replaced with lightweight parametric commercial-gym catalog meshes
  - CLEANUP        : fake-animated static parts stripped to 1 frame; 12-slice carabiners merged into 1 ring
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Material preset IDs (must stay in sync with tools/viewer3d/index.html)
MAT_LEGACY = 0
MAT_FRAME = 1     # matte powder-coat steel (roughness 0.52, metalness 0.28)
MAT_SILVER = 2    # satin brushed metal (roughness 0.34, metalness 0.62)
MAT_CHROME = 3    # polished chrome (roughness 0.16, metalness 0.88)
MAT_PAD = 4       # matte vinyl/leather cushion (roughness 0.72, metalness 0.05)
MAT_ACRYLIC = 5   # smoked translucent shroud (transparent, opacity 0.28, depthWrite: false)
MAT_RUBBER = 6    # matte dark rubber/cable/grip (roughness 0.85, metalness 0.04)
MAT_ACCENT = 7    # anodized accent pins/hubs (roughness 0.32, metalness 0.45)
MAT_SELECTOR_WINDOW = 8  # twin neutral acrylic leaves, distinct from older tinted shrouds

MAT_NAMES = {
    MAT_LEGACY: "legacy",
    MAT_FRAME: "frame",
    MAT_SILVER: "silver",
    MAT_CHROME: "chrome",
    MAT_PAD: "pad",
    MAT_ACRYLIC: "acrylic",
    MAT_RUBBER: "rubber",
    MAT_ACCENT: "accent",
    MAT_SELECTOR_WINDOW: "selector_window",
}

# Exact regex from tools/build_v5_hand_viewer_copy.py:grip_objects()
_GRIP_SELECT = re.compile(
    r"grip|handle|shaft|pullup|bar_main|^bar$|^barbell|^pull_up|dip_bar|^rope_cord"
)
_GRIP_SKIP = re.compile(
    r"mount|link|support|stem|drop|end|stop|swing|eye|knuckle|neck|collar|plate|sleeve"
)

# Rope / swivel / attachment parts that move directly with the grip assembly (keep geometry untouched)
_ATTACHMENT_KEEP = re.compile(r"^(rope_|swivel_)")
_CARABINER_SLICE = re.compile(r"^carabiner_main_\d+$")


@dataclass(frozen=True)
class PartSpec:
    raw_name: str
    base_name: str
    role: str            # LOCKED_GRIP | SURFACE_LOCKED | SHELL_UPGRADE | KEEP_ORIGINAL | CARABINER_SLICE
    catalog_id: str | None
    mat_preset: int


def normalize_base_name(raw_name: str) -> str:
    """Strip Blender numeric suffix (.001) and lowercase."""
    return re.sub(r"\.\d+$", "", raw_name).strip().lower()


def is_grip_locked(raw_name: str) -> bool:
    low = raw_name.lower()
    return bool(_GRIP_SELECT.search(low) and not _GRIP_SKIP.search(low))


def infer_metal_preset(color: list[float] | tuple[float, ...]) -> int:
    """Distinguish dark powder-coat frame vs satin silver-gray metal by luminance."""
    if not color or len(color) < 3:
        return MAT_FRAME
    lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
    return MAT_SILVER if lum >= 0.42 else MAT_FRAME


# Exact alias table: normalized base_name -> (role, catalog_id, default_mat_preset_or_None)
# None for mat_preset means infer from original object color (frame vs silver).
PART_ALIAS_MAP: dict[str, tuple[str, str, int | None]] = {
    # 1. Weight stack plates
    "rest_plate": ("SHELL_UPGRADE", "stack_plate_bevel", MAT_FRAME),
    "selected_plate": ("SHELL_UPGRADE", "stack_plate_bevel", MAT_FRAME),
    "unselected_weight": ("SHELL_UPGRADE", "stack_plate_bevel", MAT_FRAME),
    "resting_plate": ("SHELL_UPGRADE", "stack_plate_bevel", MAT_FRAME),

    # 2. Weight stack shroud / acrylic shield
    "stack_guard": ("SHELL_UPGRADE", "stack_acrylic_shield", MAT_FRAME),
    "stack_side": ("SHELL_UPGRADE", "stack_acrylic_shield", MAT_FRAME),
    "stack_back": ("SHELL_UPGRADE", "stack_acrylic_shield", MAT_FRAME),

    # 3. Pulleys & hubs (paired with U-cheek guard)
    "pulley": ("SHELL_UPGRADE", "pulley_guarded", MAT_FRAME),
    "pulley_hub": ("SHELL_UPGRADE", "pulley_hub_cap", MAT_ACCENT),

    # 4. Chrome guide rods & selector rod
    "guide": ("SHELL_UPGRADE", "guide_rod_chrome", MAT_CHROME),
    "weight_guide": ("SHELL_UPGRADE", "guide_rod_chrome", MAT_CHROME),
    "selector_rod": ("SHELL_UPGRADE", "guide_rod_chrome", MAT_CHROME),

    # 5. Chamfered structural frame tubes
    "upright": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "mast": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "arm": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "post": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "base": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "crossfoot": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "rail": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "beam": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "brace": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "rear_brace": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "seat_post": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "seat_sleeve": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "stack_base": ("SHELL_UPGRADE", "frame_tube_chamfer", MAT_FRAME),
    "thigh_arm": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "thigh_cross": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "angled_support": ("SHELL_UPGRADE", "frame_tube_chamfer", None),
    "eye_plate": ("SHELL_UPGRADE", "frame_tube_chamfer", MAT_SILVER),

    # 6. Rubber feet + anchor flanges
    "foot": ("SHELL_UPGRADE", "foot_flange_rubber", MAT_FRAME),
    "rear_foot": ("SHELL_UPGRADE", "foot_flange_rubber", MAT_FRAME),
    "seat_foot": ("SHELL_UPGRADE", "foot_flange_rubber", MAT_FRAME),
    "front_foot": ("SHELL_UPGRADE", "foot_flange_rubber", MAT_FRAME),
    "foot_cap": ("SHELL_UPGRADE", "foot_flange_rubber", MAT_RUBBER),
    "rubber_foot": ("SHELL_UPGRADE", "foot_flange_rubber", MAT_RUBBER),
    "rear_foot_cap": ("SHELL_UPGRADE", "foot_flange_rubber", MAT_RUBBER),

    # 7. Contoured ergonomic pads (contact plane locked <= 0.5 mm)
    "seat": ("SURFACE_LOCKED", "pad_contoured_seat", MAT_PAD),
    "bench_pad": ("SURFACE_LOCKED", "pad_contoured_seat", MAT_PAD),
    "back_pad": ("SURFACE_LOCKED", "pad_contoured_seat", MAT_PAD),
    "backrest": ("SURFACE_LOCKED", "pad_contoured_seat", MAT_PAD),
    "chest_pad": ("SURFACE_LOCKED", "pad_contoured_seat", MAT_PAD),
    "arm_pad": ("SURFACE_LOCKED", "pad_contoured_seat", MAT_PAD),

    # 8. Contoured foam rollers (axis & max outer radius locked <= 0.5 mm)
    "thigh_roller": ("SURFACE_LOCKED", "roller_contoured", MAT_PAD),
    "shin_roller": ("SURFACE_LOCKED", "roller_contoured", MAT_PAD),
    "leg_roller": ("SURFACE_LOCKED", "roller_contoured", MAT_PAD),
    "ankle_roller": ("SURFACE_LOCKED", "roller_contoured", MAT_PAD),
    "roller": ("SURFACE_LOCKED", "roller_contoured", MAT_PAD),

    # 10. Selector pins & lock knobs
    "selector_pin": ("SHELL_UPGRADE", "selector_pin_t", MAT_ACCENT),
    "seat_lock": ("SHELL_UPGRADE", "selector_pin_t", MAT_ACCENT),
    "lock_pin": ("SHELL_UPGRADE", "selector_pin_t", MAT_ACCENT),
    "pop_pin": ("SHELL_UPGRADE", "selector_pin_t", MAT_ACCENT),

    # 11. Coated cables
    "cable": ("SHELL_UPGRADE", "cable_coated", MAT_RUBBER),
    "cable_out_main": ("SHELL_UPGRADE", "cable_coated", MAT_RUBBER),
    "cable_stack_cable": ("SHELL_UPGRADE", "cable_coated", MAT_RUBBER),
}


def classify_object(raw_name: str, color: list[float] | tuple[float, ...]) -> PartSpec:
    base = normalize_base_name(raw_name)

    # 1. Grip-locked objects MUST keep exact geometry & animation
    if is_grip_locked(raw_name):
        if "grip" in base or "rope" in base:
            mat = MAT_RUBBER
        elif "bar" in base or "shaft" in base:
            mat = MAT_CHROME
        else:
            mat = infer_metal_preset(color)
        return PartSpec(raw_name, base, "LOCKED_GRIP", None, mat)

    # 2. Carabiner 12-slice fragments -> merged into 1 smooth ring
    if _CARABINER_SLICE.match(base):
        return PartSpec(raw_name, base, "CARABINER_SLICE", "carabiner_merged", MAT_CHROME)

    # 3. Rope/swivel attachment sub-parts -> keep exact geometry
    if _ATTACHMENT_KEEP.match(base):
        mat = MAT_CHROME if ("swivel" in base or "clip" in base or "ferrule" in base) else MAT_RUBBER
        return PartSpec(raw_name, base, "KEEP_ORIGINAL", None, mat)

    # 4. Exact alias table
    if base in PART_ALIAS_MAP:
        role, cat_id, mat = PART_ALIAS_MAP[base]
        if mat is None:
            mat = infer_metal_preset(color)
        return PartSpec(raw_name, base, role, cat_id, mat)

    # 5. Prefix match for cable_out_* / cable_stack_*
    if base.startswith("cable_out_") or base.startswith("cable_stack_"):
        return PartSpec(raw_name, base, "SHELL_UPGRADE", "cable_coated", MAT_RUBBER)

    # Fallback: preserve original geometry with inferred material
    return PartSpec(raw_name, base, "KEEP_ORIGINAL", None, infer_metal_preset(color))
