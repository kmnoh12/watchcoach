"""detail4 P1 floor_rubber: matte charcoal EPDM rubber flooring with crisp light speckles,
per-tile tonal variation, soft foot-traffic wear paths, rubber scuffs, and faint deadlift chalk.

Touches ONLY:
  - Material slots (OBJECT link) on RubberFloorTiles -> D4floor_EPDM_Machine,
    Dgym_floor_FreeWeight_Tiles & Platform_Base -> D4floor_EPDM_Impact.
    Original material slot state is snapshotted into each object's `d4floor_orig` custom property
    and tagged `detail4_pkg = "floor_rubber"`.
  - New decal meshes in collection `DETAIL4_floor_rubber` under `SET` (scuff marks near benches,
    faint chalk dust on Platform_Base rubber wing).
Does NOT modify `promo/tools/realism_pass/gym_structure.py` or wood deco-tile materials.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_floor_rubber.py [-- --save out.blend]
"""
import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

KEY = "floor_rubber"
COLL = "DETAIL4_floor_rubber"
PFX = "D4floor_"
PROP = "d4floor_orig"

PARTS_DIR = Path(__file__).resolve().parent.parent / "parts" / "detail4_floor_rubber"

# Foot-traffic wear corridors in world XY: (x0, y0, x1, y1, half_width, feather)
# Softly lowers roughness by ~0.10 along heavily walked machine aisles and bench fronts.
WEAR_PATHS = (
    (-3.20, -1.25, 6.80, -1.25, 0.36, 0.30),   # main aisle between front & mid machine rows
    (-3.30, 0.55, -0.35, 0.85, 0.38, 0.32),    # central stretch / lat-pulldown / cable foreground
    (-6.45, 2.15, -4.40, 2.55, 0.36, 0.28),    # front of freeweight adjustable benches
)

# Floor life decals: (name, img_file, center_xyz, size_xy, rot_deg, base_rgb, rough, alpha_mul)
# Lifted +1.6 mm above exact floor surface (RubberFloorTiles z=0.0, FreeWeight z=0.004, Platform_Base z=0.024)
# to prevent z-fighting while remaining visually flush.
DECALS = (
    # Black rubber shoe/bumper scuff streaks near benches & central aisle
    ("Scuff_BenchFW", "scuff_marks.png", (-5.85, 1.38, 0.0016), (0.68, 0.50), 18.0,
     (0.010, 0.010, 0.011), 0.66, 0.72),
    ("Scuff_AisleMid", "scuff_marks.png", (-2.15, 0.85, 0.0016), (0.82, 0.56), -26.0,
     (0.010, 0.010, 0.011), 0.68, 0.65),
    ("Scuff_FWBench", "scuff_marks.png", (0.82, 2.78, 0.0056), (0.72, 0.48), 42.0,
     (0.009, 0.009, 0.010), 0.66, 0.68),
    # Very faint powdery white magnesium chalk dust on open front-right rubber wing of Platform_Base
    ("Chalk_Platform", "chalk_dust.png", (3.84, 2.64, 0.0256), (0.40, 0.56), -8.0,
     (0.72, 0.72, 0.70), 0.95, 0.58),
)


def _node(N, kind, loc=(0, 0)):
    n = N.new("ShaderNode" + kind)
    n.location = loc
    return n


def _wear_capsule_mask(N, L, pos_sock, x0, y0, x1, y1, half_w, feather, x_off=0):
    """Smooth 0..1 mask for a world-XY capsule segment with organic noise-warped edge."""
    # Project pos onto XY (z=0)
    sep = _node(N, "SeparateXYZ", (x_off, -600))
    L.new(pos_sock, sep.inputs["Vector"])
    cmb = _node(N, "CombineXYZ", (x_off + 160, -600))
    L.new(sep.outputs["X"], cmb.inputs["X"])
    L.new(sep.outputs["Y"], cmb.inputs["Y"])
    cmb.inputs["Z"].default_value = 0.0
    p_xy = cmb.outputs["Vector"]

    dx, dy = x1 - x0, y1 - y0
    seg_len_sq = max(dx * dx + dy * dy, 1e-6)

    # pa = p_xy - p0
    pa = _node(N, "VectorMath", (x_off + 320, -600))
    pa.operation = "SUBTRACT"
    L.new(p_xy, pa.inputs[0])
    pa.inputs[1].default_value = (x0, y0, 0.0)

    # t = clamp(dot(pa, ab) / |ab|^2, 0, 1)
    dot = _node(N, "VectorMath", (x_off + 480, -600))
    dot.operation = "DOT_PRODUCT"
    L.new(pa.outputs["Vector"], dot.inputs[0])
    dot.inputs[1].default_value = (dx / seg_len_sq, dy / seg_len_sq, 0.0)

    clamp = _node(N, "Clamp", (x_off + 640, -600))
    clamp.inputs["Min"].default_value = 0.0
    clamp.inputs["Max"].default_value = 1.0
    L.new(dot.outputs["Value"], clamp.inputs["Value"])

    # proj = ab * t
    ab_t = _node(N, "VectorMath", (x_off + 800, -600))
    ab_t.operation = "SCALE"
    ab_t.inputs[0].default_value = (dx, dy, 0.0)
    L.new(clamp.outputs["Result"], ab_t.inputs["Scale"])

    # dist = length(pa - proj)
    diff = _node(N, "VectorMath", (x_off + 960, -600))
    diff.operation = "SUBTRACT"
    L.new(pa.outputs["Vector"], diff.inputs[0])
    L.new(ab_t.outputs["Vector"], diff.inputs[1])

    dist = _node(N, "VectorMath", (x_off + 1120, -600))
    dist.operation = "LENGTH"
    L.new(diff.outputs["Vector"], dist.inputs[0])

    # Organic boundary perturbation
    noise = _node(N, "TexNoise", (x_off + 960, -760))
    noise.inputs["Scale"].default_value = 0.85
    noise.inputs["Detail"].default_value = 3.0
    L.new(p_xy, noise.inputs["Vector"])

    n_map = _node(N, "MapRange", (x_off + 1120, -760))
    n_map.inputs["From Min"].default_value = 0.25
    n_map.inputs["From Max"].default_value = 0.75
    n_map.inputs["To Min"].default_value = -0.14
    n_map.inputs["To Max"].default_value = 0.14
    L.new(noise.outputs["Fac"], n_map.inputs["Value"])

    d_pert = _node(N, "Math", (x_off + 1280, -640))
    d_pert.operation = "ADD"
    L.new(dist.outputs["Value"], d_pert.inputs[0])
    L.new(n_map.outputs["Result"], d_pert.inputs[1])

    # Smoothstep: 1 inside half_w, 0 outside half_w + feather
    mr = _node(N, "MapRange", (x_off + 1440, -640))
    mr.interpolation_type = "SMOOTHSTEP"
    mr.clamp = True
    mr.inputs["From Min"].default_value = half_w
    mr.inputs["From Max"].default_value = half_w + feather
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    L.new(d_pert.outputs["Value"], mr.inputs["Value"])
    return mr.outputs["Result"]


def _build_epdm_material(name, base_rgb, flecks, tile_pitch, tile_offset,
                         rough_range=(0.82, 0.92), specular=0.34, wear_drop=0.10):
    """Build matte charcoal EPDM rubber shader with dual-scale jagged granules,
    per-tile tonal/roughness variation, tile seam darkening, and smooth foot-traffic wear."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*base_rgb, 1.0)
    mat["detail4_pkg"] = KEY

    nt = mat.node_tree
    N, L = nt.nodes, nt.links
    N.clear()

    out = _node(N, "OutputMaterial", (900, 0))
    bsdf = _node(N, "BsdfPrincipled", (580, 0))
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = specular
    bsdf.inputs["Coat Weight"].default_value = 0.0
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    geo = _node(N, "NewGeometry", (-1600, 100))
    pos = geo.outputs["Position"]

    # --- 1. Warp position slightly with high-frequency noise so Voronoi flecks are irregular cut rubber chips ---
    def _fleck_layer(scale, cover, r_lo, r_hi, warp_amp, y_base):
        wn = _node(N, "TexNoise", (-1350, y_base))
        wn.inputs["Scale"].default_value = scale * 2.1
        wn.inputs["Detail"].default_value = 3.0
        L.new(pos, wn.inputs["Vector"])

        w_sub = _node(N, "VectorMath", (-1180, y_base))
        w_sub.operation = "SUBTRACT"
        L.new(wn.outputs["Color"], w_sub.inputs[0])
        w_sub.inputs[1].default_value = (0.5, 0.5, 0.5)

        w_sc = _node(N, "VectorMath", (-1020, y_base))
        w_sc.operation = "SCALE"
        L.new(w_sub.outputs["Vector"], w_sc.inputs[0])
        w_sc.inputs["Scale"].default_value = warp_amp

        w_pos = _node(N, "VectorMath", (-860, y_base))
        w_pos.operation = "ADD"
        L.new(pos, w_pos.inputs[0])
        L.new(w_sc.outputs["Vector"], w_pos.inputs[1])

        vor = _node(N, "TexVoronoi", (-680, y_base))
        vor.voronoi_dimensions = "2D"
        vor.feature = "F1"
        vor.distance = "EUCLIDEAN"
        vor.inputs["Scale"].default_value = scale
        vor.inputs["Randomness"].default_value = 0.95
        L.new(w_pos.outputs["Vector"], vor.inputs["Vector"])

        sep = _node(N, "SeparateColor", (-500, y_base))
        L.new(vor.outputs["Color"], sep.inputs["Color"])

        # Select `cover` fraction of Voronoi cells
        sel = _node(N, "Math", (-320, y_base + 40))
        sel.operation = "LESS_THAN"
        L.new(sep.outputs["Red"], sel.inputs[0])
        sel.inputs[1].default_value = cover

        # Crisp chip edge with small AA feather (prevents shimmer while staying sharp at 2-6 m)
        near = _node(N, "MapRange", (-320, y_base - 110))
        near.clamp = True
        near.inputs["From Min"].default_value = r_lo
        near.inputs["From Max"].default_value = r_hi
        near.inputs["To Min"].default_value = 1.0
        near.inputs["To Max"].default_value = 0.0
        L.new(vor.outputs["Distance"], near.inputs["Value"])

        mask = _node(N, "Math", (-140, y_base))
        mask.operation = "MULTIPLY"
        L.new(sel.outputs["Value"], mask.inputs[0])
        L.new(near.outputs["Result"], mask.inputs[1])

        # Fleck colour from cell Green channel (constant ramp across fleck palette)
        ramp = _node(N, "ValToRGB", (-320, y_base + 210))
        ramp.color_ramp.interpolation = "CONSTANT"
        els = ramp.color_ramp.elements
        total_share = sum(sh for _, sh in flecks)
        acc = 0.0
        for idx, (rgb, sh) in enumerate(flecks):
            e = els[idx] if idx < len(els) else els.new(acc)
            e.position = acc
            e.color = (*rgb, 1.0)
            acc += sh / total_share
        while len(els) > len(flecks):
            els.remove(els[-1])
        L.new(sep.outputs["Green"], ramp.inputs["Fac"])
        return mask.outputs["Value"], ramp.outputs["Color"]

    # Medium-fine chips (~2.4–3.2 mm, calm EPDM speckle at 2–6 m): cell 6.1 mm, cover 0.38, disk ~0.115 -> ~4.4%
    mask_med, col_med = _fleck_layer(scale=165.0, cover=0.38, r_lo=0.16, r_hi=0.22, warp_amp=0.0009, y_base=420)
    # Fine chips (~1.4–2.1 mm, dense fine rubber granules): cell 3.5 mm, cover 0.60, disk ~0.14 -> ~8.4%
    # Combined coverage ~12.4% (real EPDM 12–15% smaller chips, matches gym/208, 212, 216, interior/101)
    mask_fine, col_fine = _fleck_layer(scale=285.0, cover=0.60, r_lo=0.18, r_hi=0.24, warp_amp=0.00045, y_base=60)

    # Rubber binder micro-mottling (dark charcoal crumb variation)
    binder_n = _node(N, "TexNoise", (-680, 740))
    binder_n.inputs["Scale"].default_value = 55.0
    binder_n.inputs["Detail"].default_value = 4.0
    L.new(pos, binder_n.inputs["Vector"])

    binder_r = _node(N, "ValToRGB", (-440, 740))
    binder_r.color_ramp.elements[0].position = 0.22
    binder_r.color_ramp.elements[0].color = tuple(c * 0.72 for c in base_rgb) + (1.0,)
    binder_r.color_ramp.elements[1].position = 0.78
    binder_r.color_ramp.elements[1].color = tuple(c * 1.24 for c in base_rgb) + (1.0,)
    L.new(binder_n.outputs["Fac"], binder_r.inputs["Fac"])

    # Combine binder + fine chips + coarse chips (coarse wins on overlap)
    mix_f = _node(N, "Mix", (-40, 460))
    mix_f.data_type = "RGBA"
    L.new(mask_fine, mix_f.inputs["Factor"])
    L.new(binder_r.outputs["Color"], mix_f.inputs["A"])
    L.new(col_fine, mix_f.inputs["B"])

    mix_m = _node(N, "Mix", (130, 460))
    mix_m.data_type = "RGBA"
    L.new(mask_med, mix_m.inputs["Factor"])
    L.new(mix_f.outputs["Result"], mix_m.inputs["A"])
    L.new(col_med, mix_m.inputs["B"])

    fleck_any = _node(N, "Math", (40, 220))
    fleck_any.operation = "MAXIMUM"
    L.new(mask_med, fleck_any.inputs[0])
    L.new(mask_fine, fleck_any.inputs[1])

    # --- 2. Per-tile tonal & sheen variation + 1.8 mm tile seam darkening (600 mm / 1000 mm grid) ---
    t_add = _node(N, "VectorMath", (-1050, -320))
    t_add.operation = "ADD"
    L.new(pos, t_add.inputs[0])
    t_add.inputs[1].default_value = tile_offset

    t_snap = _node(N, "VectorMath", (-880, -320))
    t_snap.operation = "SNAP"
    L.new(t_add.outputs["Vector"], t_snap.inputs[0])
    t_snap.inputs[1].default_value = (tile_pitch, tile_pitch, tile_pitch)

    t_wn = _node(N, "TexWhiteNoise", (-700, -320))
    L.new(t_snap.outputs["Vector"], t_wn.inputs["Vector"])

    # Per-tile brightness multiplier (0.88 .. 1.12)
    t_val = _node(N, "MapRange", (-500, -240))
    t_val.inputs["To Min"].default_value = 0.87
    t_val.inputs["To Max"].default_value = 1.13
    L.new(t_wn.outputs["Value"], t_val.inputs["Value"])

    # Tile seam via Brick Texture aligned to exact tile pitch & offset
    brick = _node(N, "TexBrick", (-700, -500))
    brick.offset = 0.0
    brick.offset_frequency = 1
    brick.squash = 1.0
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Brick Width"].default_value = tile_pitch
    brick.inputs["Row Height"].default_value = tile_pitch
    brick.inputs["Mortar Size"].default_value = 0.0028
    brick.inputs["Mortar Smooth"].default_value = 0.30
    brick.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
    brick.inputs["Color2"].default_value = (1.0, 1.0, 1.0, 1.0)
    brick.inputs["Mortar"].default_value = (0.10, 0.10, 0.10, 1.0)
    L.new(t_add.outputs["Vector"], brick.inputs["Vector"])

    # Multiply albedo by per-tile tone
    t_cmb = _node(N, "CombineColor", (-300, -240))
    for ch in ("Red", "Green", "Blue"):
        L.new(t_val.outputs["Result"], t_cmb.inputs[ch])

    mul_tile = _node(N, "Mix", (280, 420))
    mul_tile.data_type = "RGBA"
    mul_tile.blend_type = "MULTIPLY"
    mul_tile.inputs["Factor"].default_value = 1.0
    L.new(mix_m.outputs["Result"], mul_tile.inputs["A"])
    L.new(t_cmb.outputs["Color"], mul_tile.inputs["B"])

    # Darken 2 mm joints
    mul_seam = _node(N, "Mix", (420, 420))
    mul_seam.data_type = "RGBA"
    mul_seam.blend_type = "MULTIPLY"
    mul_seam.inputs["Factor"].default_value = 1.0
    L.new(mul_tile.outputs["Result"], mul_seam.inputs["A"])
    L.new(brick.outputs["Color"], mul_seam.inputs["B"])
    L.new(mul_seam.outputs["Result"], bsdf.inputs["Base Color"])

    # --- 3. Roughness: high matte 0.82..0.92 + subtle per-tile shift + organic wear paths (-0.10) ---
    macro_r = _node(N, "TexNoise", (-700, -80))
    macro_r.inputs["Scale"].default_value = 0.75
    macro_r.inputs["Detail"].default_value = 4.0
    L.new(pos, macro_r.inputs["Vector"])

    r_blend = _node(N, "Mix", (-480, -80))
    r_blend.data_type = "FLOAT"
    r_blend.inputs["Factor"].default_value = 0.35
    L.new(macro_r.outputs["Fac"], r_blend.inputs["A"])
    L.new(t_wn.outputs["Value"], r_blend.inputs["B"])

    r_base = _node(N, "MapRange", (-280, -80))
    r_base.clamp = True
    r_base.inputs["From Min"].default_value = 0.20
    r_base.inputs["From Max"].default_value = 0.80
    r_base.inputs["To Min"].default_value = rough_range[0]
    r_base.inputs["To Max"].default_value = rough_range[1]
    L.new(r_blend.outputs["Result"], r_base.inputs["Value"])

    # Foot-traffic wear corridors (smoothly subtract wear_drop from roughness)
    wear_masks = [
        _wear_capsule_mask(N, L, pos, x0, y0, x1, y1, hw, fth, x_off=-1400 + i * 200)
        for i, (x0, y0, x1, y1, hw, fth) in enumerate(WEAR_PATHS)
    ]
    w_comb = wear_masks[0]
    for idx, wm in enumerate(wear_masks[1:]):
        mx = _node(N, "Math", (160 + idx * 140, -640))
        mx.operation = "MAXIMUM"
        L.new(w_comb, mx.inputs[0])
        L.new(wm, mx.inputs[1])
        w_comb = mx.outputs["Value"]

    w_delta = _node(N, "Math", (140, -140))
    w_delta.operation = "MULTIPLY"
    L.new(w_comb, w_delta.inputs[0])
    w_delta.inputs[1].default_value = wear_drop

    r_worn = _node(N, "Math", (290, -80))
    r_worn.operation = "SUBTRACT"
    L.new(r_base.outputs["Result"], r_worn.inputs[0])
    L.new(w_delta.outputs["Value"], r_worn.inputs[1])

    # Keep joints fully matte (0.95)
    r_joint = _node(N, "Mix", (420, -80))
    r_joint.data_type = "FLOAT"
    L.new(brick.outputs["Fac"], r_joint.inputs["Factor"])
    L.new(r_worn.outputs["Value"], r_joint.inputs["A"])
    r_joint.inputs["B"].default_value = 0.95
    L.new(r_joint.outputs["Result"], bsdf.inputs["Roughness"])

    # --- 4. Granular rubber relief bump (crumb grain + chip edges + tile seam groove) ---
    grain = _node(N, "TexNoise", (-440, -390))
    grain.inputs["Scale"].default_value = 260.0
    grain.inputs["Detail"].default_value = 4.0
    L.new(pos, grain.inputs["Vector"])

    f_bump = _node(N, "Math", (-140, -340))
    f_bump.operation = "MULTIPLY"
    L.new(fleck_any.outputs["Value"], f_bump.inputs[0])
    f_bump.inputs[1].default_value = 0.45

    h1 = _node(N, "Math", (40, -340))
    h1.operation = "ADD"
    L.new(grain.outputs["Fac"], h1.inputs[0])
    L.new(f_bump.outputs["Value"], h1.inputs[1])

    # Drop height in tile seam
    seam_drop = _node(N, "Math", (40, -480))
    seam_drop.operation = "MULTIPLY"
    L.new(brick.outputs["Fac"], seam_drop.inputs[0])
    seam_drop.inputs[1].default_value = 1.2

    h2 = _node(N, "Math", (220, -360))
    h2.operation = "SUBTRACT"
    L.new(h1.outputs["Value"], h2.inputs[0])
    L.new(seam_drop.outputs["Value"], h2.inputs[1])

    bump = _node(N, "Bump", (390, -340))
    bump.inputs["Strength"].default_value = 0.24
    bump.inputs["Distance"].default_value = 0.0010
    L.new(h2.outputs["Value"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def _load_packed_image(img_path: Path):
    """Load or reload an image from disk and pack it cleanly without creating duplicate datablocks."""
    p_str = str(img_path.resolve())
    img = bpy.data.images.get(img_path.name)
    if img is None:
        img = bpy.data.images.load(p_str, check_existing=True)
    else:
        if img.packed_file is not None:
            try:
                img.unpack(method="REMOVE")
            except Exception:
                pass
        img.filepath = p_str
        img.reload()
    try:
        img.pack()
    except Exception:
        pass
    return img


def _build_decal_material(name, img_path, base_rgb, rough, alpha_mul):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat["detail4_pkg"] = KEY
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    if hasattr(mat, "use_transparency_overlap"):
        mat.use_transparency_overlap = False

    nt = mat.node_tree
    N, L = nt.nodes, nt.links
    N.clear()

    out = _node(N, "OutputMaterial", (600, 0))
    bsdf = _node(N, "BsdfPrincipled", (300, 0))
    bsdf.inputs["Base Color"].default_value = (*base_rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = 0.30
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex = _node(N, "TexImage", (-240, 0))
    tex.image = _load_packed_image(img_path)
    tex.extension = "CLIP"

    a_mul = _node(N, "Math", (40, -140))
    a_mul.operation = "MULTIPLY"
    L.new(tex.outputs["Alpha"], a_mul.inputs[0])
    a_mul.inputs[1].default_value = alpha_mul
    L.new(a_mul.outputs["Value"], bsdf.inputs["Alpha"])

    # Modulate base colour subtly by image RGB for chalk/scuff variation
    c_mix = _node(N, "Mix", (40, 80))
    c_mix.data_type = "RGBA"
    c_mix.blend_type = "MULTIPLY"
    c_mix.inputs["Factor"].default_value = 0.5
    c_mix.inputs["A"].default_value = (*base_rgb, 1.0)
    L.new(tex.outputs["Color"], c_mix.inputs["B"])
    L.new(c_mix.outputs["Result"], bsdf.inputs["Base Color"])
    return mat


def _make_decal_plane(name, center, size_xy, rot_deg, mat, coll):
    sx, sy = size_xy
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    hx, hy = sx * 0.5, sy * 0.5
    v0 = bm.verts.new((-hx, -hy, 0.0))
    v1 = bm.verts.new((hx, -hy, 0.0))
    v2 = bm.verts.new((hx, hy, 0.0))
    v3 = bm.verts.new((-hx, hy, 0.0))
    f = bm.faces.new((v0, v1, v2, v3))
    coords = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    for loop, uv_c in zip(f.loops, coords):
        loop[uv].uv = uv_c
    bm.normal_update()

    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)

    ob = bpy.data.objects.new(name, me)
    ob.location = center
    ob.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
    ob.visible_shadow = False  # decal never casts spurious shadow onto floor
    coll.objects.link(ob)
    return ob


def _swap_object_material(ob_name, new_mat):
    ob = bpy.data.objects.get(ob_name)
    if ob is None or not ob.material_slots:
        return None
    slot = ob.material_slots[0]
    if PROP not in ob:
        ob[PROP] = json.dumps({
            "link": slot.link,
            "material": slot.material.name if slot.material else None,
        })
    ob["detail4_pkg"] = KEY
    slot.link = "OBJECT"
    slot.material = new_mat
    return {"object": ob_name, "orig": json.loads(ob[PROP]), "new_material": new_mat.name}


def apply() -> dict:
    parent = bpy.data.collections["SET"]
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        parent.children.link(coll)
    elif coll.name not in parent.children:
        parent.children.link(coll)

    # Clear previously created objects in our collection (idempotent)
    for ob in list(coll.objects):
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)

    # Build/rebuild our EPDM materials (reference: gym/208, 212, 216, 138, 207; interior/101, 151)
    # Real EPDM contrast (~8-10x): charcoal SBR base 0.020-0.023 with calm light-grey chips 0.16-0.22
    bright_w = (0.215, 0.218, 0.214)
    soft_w = (0.182, 0.185, 0.185)
    mid_g = (0.160, 0.162, 0.165)
    blue_g = (0.095, 0.145, 0.220)

    # Machine EPDM: matte charcoal (0.022 linear), rough 0.85-0.93, Specular 0.30,
    # ~12.4% smaller grey flecks (~7.3-9.8x contrast), 600 mm tiles with subtle per-tile shade shift.
    # RubberFloorTiles seams sit at x = 0.6*k, y = 0.6*k - 0.2 -> offset (0.0, 0.2, 0.0)
    m_machine = _build_epdm_material(
        PFX + "EPDM_Machine",
        base_rgb=(0.0215, 0.0220, 0.0230),
        flecks=[(bright_w, 0.45), (soft_w, 0.35), (mid_g, 0.20)],
        tile_pitch=0.60,
        tile_offset=(0.0, 0.20, 0.0),
        rough_range=(0.85, 0.93),
        specular=0.30,
        wear_drop=0.10,
    )

    # Impact EPDM: slightly deeper charcoal (0.0205 linear), rough 0.83-0.92, Specular 0.30,
    # adds ~2.5% subtle blue-grey flecks (~20% of ~12.4% flecks); preserves P2 dumbbell bounce >= 60.
    # Dgym_floor_FreeWeight_Tiles laid from x=-3.45 (+1 m), y=4.955 (-1 m) -> offset (3.45, -4.955, 0.0)
    m_impact = _build_epdm_material(
        PFX + "EPDM_Impact",
        base_rgb=(0.0200, 0.0206, 0.0220),
        flecks=[(bright_w, 0.38), (soft_w, 0.27), (mid_g, 0.15), (blue_g, 0.20)],
        tile_pitch=1.00,
        tile_offset=(3.45, -4.955, 0.0),
        rough_range=(0.83, 0.92),
        specular=0.30,
        wear_drop=0.09,
    )

    touched = []
    for ob_name, mat in (
        ("RubberFloorTiles", m_machine),
        ("Dgym_floor_FreeWeight_Tiles", m_impact),
        ("Platform_Base", m_impact),
    ):
        info = _swap_object_material(ob_name, mat)
        if info:
            touched.append(info)

    added = []
    for dname, fname, center, size_xy, rot_deg, rgb, rough, alpha_mul in DECALS:
        img_path = PARTS_DIR / fname
        if not img_path.exists():
            print(f"[detail4_{KEY}] warning: missing decal image {img_path}")
            continue
        dmat = _build_decal_material(PFX + dname + "_Mat", img_path, rgb, rough, alpha_mul)
        ob = _make_decal_plane(PFX + dname, center, size_xy, rot_deg, dmat, coll)
        added.append(ob)

    bpy.context.view_layer.update()
    tris = 0
    bboxes = {}
    for ob in added:
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        bboxes[ob.name] = (
            [round(min(p[i] for p in pts), 4) for i in range(3)]
            + [round(max(p[i] for p in pts), 4) for i in range(3)]
        )

    return {
        "collection": COLL,
        "objects_added": [o.name for o in added],
        "objects_added_count": len(added),
        "triangles_added": tris,
        "existing_touched": touched,
        "materials_created": [m_machine.name, m_impact.name] + [PFX + d[0] + "_Mat" for d in DECALS],
        "bbox_world": bboxes,
    }


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    res = apply()
    print(f"[detail4_{KEY}] {json.dumps(res)}")
    if "--save" in argv:
        out = argv[argv.index("--save") + 1]
        norm = os.path.normpath(out).replace("\\", "/")
        if "promo/scenes" in norm or "promo/models" in norm:
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
        print(f"[detail4_{KEY}] saved copy -> {out}")


if __name__ == "__main__":
    _main()
