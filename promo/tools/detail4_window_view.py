"""detail4 P4 window_view: replaces flat right-wall sky vinyl (`Window Sky`) with a real
window opening, 4 glass panes, charcoal horizontal transom bar, dark charcoal semi-sheer roller
blinds (with top cassettes & weighted bottom bars), and a distant 3D Korean apartment & commercial
complex skyline with PIL-generated multi-pane architectural facades and bright daylight sky
(refs gym/221, interior/101, gym/161, 205, 232).

Rules honoured:
  - Hides `Window Sky` and `Wall_Right` (replacing `Wall_Right` with exact cutout geometry
    `D4win_WallRight_Cutout` using the same `Gym_Wall` material so the window opens outdoors).
    Stores original hide flags in custom property `d4win_orig` and tags `detail4_pkg = "window_view"`.
  - Keeps `Window Jamb*`, `Window Head`, `Window Sill`, `Window daylight`, and `Instagram*`
    stickers completely untouched.
  - Zero text, logos, or window decal lettering (Codex domain).
  - Exterior buildings, glass & blind fabric have `visible_shadow = False` (zero shadow cost).
  - Idempotent: running apply() twice yields identical scene state.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_window_view.py [-- --save out.blend]
"""
import json
import os
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

KEY = "window_view"
COLL = "DETAIL4_window_view"
PFX = "D4win_"
PROP = "d4win_orig"

PARTS_DIR = Path(__file__).resolve().parent.parent / "parts" / "detail4_window_view"

# Verified existing Right Wall & Window coordinates (promo/scenes/scene_gym.blend)
WALL_X0, WALL_X1 = 13.496, 13.704
WALL_Y0, WALL_Y1 = -6.904, 5.304
WALL_Z0, WALL_Z1 = -0.029, 3.629

OPEN_Y0, OPEN_Y1 = -4.305, 3.075
# Opening Z clears the 3 middle jambs (z=1.065..2.975) while staying 18 mm inside Window Sill (z_min=1.044)
# and Window Head (z_max=2.996) so there is zero light leak around the outer perimeter frame.
OPEN_Z0, OPEN_Z1 = 1.062, 2.978

# 4 clear window bays between the 5 existing vertical jambs (with 2.5 mm margin clear of jambs)
BAYS = (
    (-4.265, -2.480),   # Bay 0 (Far)
    (-2.400, -0.615),   # Bay 1 (Ext-Join)
    (-0.535,  1.210),   # Bay 2 (Join-Center, behind hanging TV at y=-0.02..1.22)
    ( 1.290,  3.035),   # Bay 3 (Near, closest to mirror wall)
)
BAY_Z0, BAY_Z1 = 1.120, 2.920
TRANSOM_Z = 2.18

# Roller blind drop fraction per bay (matches gym/221: 3 of 4 bays pulled ~33-36% down,
# leaving a clean 8-12 cm bright sky reveal above the z=2.18 transom bar; Bay 2 behind TV stays rolled up).
BLIND_DROPS = (0.35, 0.33, 0.0, 0.36)

# Exterior 3D Korean urban skyline pushed well back (x=62..146 m -> ~49-133 m outside window at x=13.5)
# so upper 35-48% of open glass shows bright Korean daylight sky in both `window_close` and `gym_main`,
# with wide sky corridors between dongs and layered 3-tier urban depth (refs gym/221, interior/101).
# (name, x_front, y_center, depth_x, width_y, z_base, z_top, tex_file, tile_w, tile_h, tier, seed)
BUILDINGS = (
    # Tier 0: Foreground lower commercial/sangga roofs (~5-6F, low z_top in bottom ~25% of window + street gap)
    ("NearSangga_01",  62.0, -24.0, 10.5, 16.0, -20.0,  0.4, "sangga_facade.png",   15.0, 19.2, 0, 101),
    ("NearSangga_02",  66.0,   2.0, 10.0, 14.5, -20.0, -0.2, "sangga_facade.png",   15.0, 19.2, 0, 102),
    ("NearSangga_03",  64.0,  34.0, 11.0, 16.0, -20.0,  0.8, "sangga_facade.png",   15.0, 19.2, 0, 103),
    # Tier 1: Mid-distance Korean high-rise apartment slabs (15-20F, x=91..97 m, wide sky gaps & open y=10..17 corridor)
    ("AptSlab_01",     92.0, -34.0, 11.5, 16.5, -40.0,  3.4, "apt_facade_warm.png", 16.0, 22.4, 1, 201),
    ("AptSlab_02",     95.0,  -7.5, 11.5, 16.0, -40.0,  2.6, "apt_facade_cool.png", 16.0, 22.4, 1, 202),
    ("AptSlab_03",     92.0,  25.5, 11.5, 16.0, -40.0,  3.8, "apt_facade_warm.png", 16.0, 22.4, 1, 203),
    ("AptSlab_04",     97.0,  51.0, 11.5, 17.0, -40.0,  3.2, "apt_facade_cool.png", 16.0, 22.4, 1, 204),
    ("AptSlab_05",     96.0, -60.0, 11.5, 17.0, -40.0,  3.0, "apt_facade_cool.png", 16.0, 22.4, 1, 205),
    # Tier 2: Far-distance apartment complex skyline (20-25F, x=126..134 m, stepped clusters + open sky gap at y=10..20)
    ("AptFar_01",     126.0, -21.0, 12.0, 18.0, -46.0,  5.6, "apt_facade_cool.png", 16.0, 22.4, 2, 301),
    ("AptFar_02",     130.0,   3.0, 12.0, 16.0, -46.0,  4.4, "apt_facade_warm.png", 16.0, 22.4, 2, 302),
    ("AptFar_03",     128.0,  37.0, 12.0, 18.0, -46.0,  6.2, "apt_facade_cool.png", 16.0, 22.4, 2, 303),
    ("AptFar_04",     132.0, -47.0, 12.0, 18.5, -46.0,  5.2, "apt_facade_warm.png", 16.0, 22.4, 2, 304),
    ("AptFar_05",     134.0,  64.0, 12.0, 18.5, -46.0,  5.0, "apt_facade_warm.png", 16.0, 22.4, 2, 305),
)


def _node(N, kind, loc=(0, 0)):
    n = N.new("ShaderNode" + kind)
    n.location = loc
    return n


def _hide_existing(ob_name):
    ob = bpy.data.objects.get(ob_name)
    if ob is None:
        return None
    if PROP not in ob:
        ob[PROP] = json.dumps({
            "hide_render": bool(ob.hide_render),
            "hide_viewport": bool(ob.hide_viewport),
        })
    ob["detail4_pkg"] = KEY
    ob.hide_render = True
    ob.hide_viewport = True
    return {"object": ob_name, "action": "hidden", "orig": json.loads(ob[PROP])}


def _clear_coll(coll):
    for ob in list(coll.objects):
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)


def _add_box_bm(bm, x0, x1, y0, y1, z0, z1, bevel=0.0):
    g = bmesh.ops.create_cube(bm, size=1.0)
    vs = g["verts"]
    for v in vs:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    if bevel > 0.0:
        edges = list({e for v in vs for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=1, affect="EDGES", profile=0.5)
    return vs


def _apply_box_uvs(bm, tile_w, tile_h, y_off=0.0, z_off=0.0):
    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        for loop in f.loops:
            co = loop.vert.co
            if abs(n.x) >= abs(n.y) and abs(n.x) >= abs(n.z):
                u = (co.y + y_off) / tile_w
                v = (co.z + z_off) / tile_h
            elif abs(n.y) >= abs(n.z):
                u = (co.x + y_off) / tile_w
                v = (co.z + z_off) / tile_h
            else:
                u = co.x / tile_w
                v = co.y / tile_w
            loop[uv_layer].uv = (u, v)


def _finish_bm(bm, name, mat, coll, cast_shadow=True):
    me = bpy.data.meshes.new(PFX + name)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if mat is not None:
        me.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, me)
    ob.visible_shadow = cast_shadow
    coll.objects.link(ob)
    return ob


def _build_cutout_right_wall(coll):
    """Exact replacement of Wall_Right with a single watertight manifold mesh (16 verts, 16 quads,
    0 non-manifold edges, 0 boundary edges, 0 internal faces) framing the rectangular window opening."""
    wall_orig = bpy.data.objects.get("Wall_Right")
    mat = wall_orig.data.materials[0] if (wall_orig and wall_orig.data.materials) else bpy.data.materials.get("Gym_Wall")
    bm = bmesh.new()

    # 8 vertices on inner wall plane (x = WALL_X0) and 8 on outer wall plane (x = WALL_X1):
    # outer ring: 0=(Y0,Z0), 1=(Y1,Z0), 2=(Y1,Z1), 3=(Y0,Z1)
    # inner opening ring: 4=(OY0,OZ0), 5=(OY1,OZ0), 6=(OY1,OZ1), 7=(OY0,OZ1)
    ring_out = ((WALL_Y0, WALL_Z0), (WALL_Y1, WALL_Z0), (WALL_Y1, WALL_Z1), (WALL_Y0, WALL_Z1))
    ring_in = ((OPEN_Y0, OPEN_Z0), (OPEN_Y1, OPEN_Z0), (OPEN_Y1, OPEN_Z1), (OPEN_Y0, OPEN_Z1))

    f_out = [bm.verts.new((WALL_X0, y, z)) for y, z in ring_out]
    f_in = [bm.verts.new((WALL_X0, y, z)) for y, z in ring_in]
    b_out = [bm.verts.new((WALL_X1, y, z)) for y, z in ring_out]
    b_in = [bm.verts.new((WALL_X1, y, z)) for y, z in ring_in]

    for i in range(4):
        j = (i + 1) % 4
        # Front face (x = WALL_X0, normal -X)
        bm.faces.new((f_out[i], f_in[i], f_in[j], f_out[j]))
        # Back face (x = WALL_X1, normal +X)
        bm.faces.new((b_out[i], b_out[j], b_in[j], b_in[i]))
        # Outer wall perimeter rim
        bm.faces.new((f_out[i], f_out[j], b_out[j], b_out[i]))
        # Inner window reveal rim
        bm.faces.new((f_in[i], b_in[i], b_in[j], f_in[j]))

    return _finish_bm(bm, "WallRight_Cutout", mat, coll, cast_shadow=True)


def _mat_glass():
    name = PFX + "Glass"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m["detail4_pkg"] = KEY
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    if hasattr(m, "use_transparency_overlap"):
        m.use_transparency_overlap = False
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    N.clear()
    out = _node(N, "OutputMaterial", (450, 0))
    bsdf = _node(N, "BsdfPrincipled", (150, 0))
    bsdf.inputs["Base Color"].default_value = (0.60, 0.65, 0.68, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Specular IOR Level"].default_value = 0.68
    bsdf.inputs["Coat Weight"].default_value = 0.45
    bsdf.inputs["Coat Roughness"].default_value = 0.02
    bsdf.inputs["Alpha"].default_value = 0.17
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


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


def _mat_blind_fabric():
    """Opaque matte dark-charcoal woven roller-blind cloth (ref gym/221, 205):
    zero glassy see-through or reflection, fine woven horizontal/vertical textile slub,
    cloth sheen, and soft diffused backlit cloth warmth."""
    name = PFX + "RollerBlindFabric"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (0.04, 0.042, 0.046, 1.0)
    m["detail4_pkg"] = KEY
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    if hasattr(m, "use_transparency_overlap"):
        m.use_transparency_overlap = False
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    N.clear()
    out = _node(N, "OutputMaterial", (860, 0))
    bsdf = _node(N, "BsdfPrincipled", (500, 0))
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.95
    bsdf.inputs["Specular IOR Level"].default_value = 0.08
    bsdf.inputs["Coat Weight"].default_value = 0.0
    bsdf.inputs["Alpha"].default_value = 1.0
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.45
    if "Sheen Roughness" in bsdf.inputs:
        bsdf.inputs["Sheen Roughness"].default_value = 0.65
    if "Sheen Tint" in bsdf.inputs:
        bsdf.inputs["Sheen Tint"].default_value = (0.72, 0.74, 0.78, 1.0)
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    geo = _node(N, "NewGeometry", (-720, 0))
    pos = geo.outputs["Position"]

    # Horizontal weft threads + vertical warp screen weave (fine visible cloth grain)
    sc_h = _node(N, "VectorMath", (-500, 180))
    sc_h.operation = "MULTIPLY"
    L.new(pos, sc_h.inputs[0])
    sc_h.inputs[1].default_value = (1.0, 28.0, 220.0)

    weft = _node(N, "TexNoise", (-300, 180))
    weft.inputs["Scale"].default_value = 1.0
    weft.inputs["Detail"].default_value = 3.0
    weft.inputs["Roughness"].default_value = 0.55
    L.new(sc_h.outputs["Vector"], weft.inputs["Vector"])

    sc_v = _node(N, "VectorMath", (-500, -40))
    sc_v.operation = "MULTIPLY"
    L.new(pos, sc_v.inputs[0])
    sc_v.inputs[1].default_value = (1.0, 210.0, 32.0)

    warp = _node(N, "TexNoise", (-300, -40))
    warp.inputs["Scale"].default_value = 1.0
    warp.inputs["Detail"].default_value = 2.0
    L.new(sc_v.outputs["Vector"], warp.inputs["Vector"])

    weave = _node(N, "Mix", (-100, 80))
    weave.data_type = "FLOAT"
    weave.inputs["Factor"].default_value = 0.42
    L.new(weft.outputs["Fac"], weave.inputs["A"])
    L.new(warp.outputs["Fac"], weave.inputs["B"])

    # Gentle large-scale fabric roll-memory undulation (makes surface read as hanging textile, not flat glass)
    fold_sc = _node(N, "VectorMath", (-500, -240))
    fold_sc.operation = "MULTIPLY"
    L.new(pos, fold_sc.inputs[0])
    fold_sc.inputs[1].default_value = (1.0, 1.8, 4.5)

    fold = _node(N, "TexNoise", (-300, -240))
    fold.inputs["Scale"].default_value = 1.2
    fold.inputs["Detail"].default_value = 2.0
    L.new(fold_sc.outputs["Vector"], fold.inputs["Vector"])

    tex_mix = _node(N, "Mix", (70, 110))
    tex_mix.data_type = "FLOAT"
    tex_mix.inputs["Factor"].default_value = 0.30
    L.new(weave.outputs["Result"], tex_mix.inputs["A"])
    L.new(fold.outputs["Fac"], tex_mix.inputs["B"])

    col = _node(N, "ValToRGB", (240, 150))
    col.color_ramp.elements[0].position = 0.25
    col.color_ramp.elements[0].color = (0.032, 0.034, 0.037, 1.0)
    col.color_ramp.elements[1].position = 0.78
    col.color_ramp.elements[1].color = (0.056, 0.059, 0.064, 1.0)
    L.new(tex_mix.outputs["Result"], col.inputs["Fac"])
    L.new(col.outputs["Color"], bsdf.inputs["Base Color"])

    # Soft diffused fabric backlight (no crisp see-through silhouette, just warm woven cloth glow)
    emit_col = _node(N, "ValToRGB", (240, -20))
    emit_col.color_ramp.elements[0].position = 0.25
    emit_col.color_ramp.elements[0].color = (0.022, 0.025, 0.029, 1.0)
    emit_col.color_ramp.elements[1].position = 0.80
    emit_col.color_ramp.elements[1].color = (0.044, 0.049, 0.055, 1.0)
    L.new(tex_mix.outputs["Result"], emit_col.inputs["Fac"])
    L.new(emit_col.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.14

    # Combine fine textile bump + subtle hanging cloth wave
    b_fine = _node(N, "Bump", (120, -220))
    b_fine.inputs["Strength"].default_value = 0.22
    b_fine.inputs["Distance"].default_value = 0.0008
    L.new(weave.outputs["Result"], b_fine.inputs["Height"])

    b_fold = _node(N, "Bump", (300, -220))
    b_fold.inputs["Strength"].default_value = 0.08
    b_fold.inputs["Distance"].default_value = 0.004
    L.new(fold.outputs["Fac"], b_fold.inputs["Height"])
    L.new(b_fine.outputs["Normal"], b_fold.inputs["Normal"])
    L.new(b_fold.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _mat_charcoal_hardware():
    m = bpy.data.materials.get("Window Charcoal Frame")
    if m is not None:
        return m
    name = PFX + "CharcoalHardware"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m["detail4_pkg"] = KEY
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.046, 0.049, 0.052, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.52
    bsdf.inputs["Metallic"].default_value = 0.25
    return m


def _mat_building_textured(tag, tex_file, dist_x, tier):
    """Daylight-lit Korean apartment/sangga building using crisp PIL multi-pane facade PNG,
    strong directional sun/sky shading for 3D balcony slabs & side walls, and tier-calibrated
    aerial perspective haze (crisp near/mid, stronger haze only on far skyline)."""
    name = PFX + f"Facade_{tag}"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m["detail4_pkg"] = KEY
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    N.clear()

    out = _node(N, "OutputMaterial", (920, 0))
    bsdf = _node(N, "BsdfPrincipled", (620, 0))
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.88
    bsdf.inputs["Specular IOR Level"].default_value = 0.0
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex = _node(N, "TexImage", (-300, 180))
    img_path = PARTS_DIR / tex_file
    tex.image = _load_packed_image(img_path)
    tex.extension = "REPEAT"

    # Roof & top parapet/balcony slab faces (+Z) and slab undersides (-Z) get clean architectural concrete tones
    geo = _node(N, "NewGeometry", (-560, -140))
    nrm = geo.outputs["Normal"]
    sep_n = _node(N, "SeparateXYZ", (-360, -40))
    L.new(nrm, sep_n.inputs["Vector"])

    is_horiz = _node(N, "Math", (-160, -40))
    is_horiz.operation = "ABSOLUTE"
    L.new(sep_n.outputs["Z"], is_horiz.inputs[0])

    is_slab = _node(N, "Math", (0, -40))
    is_slab.operation = "GREATER_THAN"
    L.new(is_horiz.outputs["Value"], is_slab.inputs[0])
    is_slab.inputs[1].default_value = 0.7

    base_col = _node(N, "Mix", (140, 140))
    base_col.data_type = "RGBA"
    L.new(is_slab.outputs["Value"], base_col.inputs["Factor"])
    L.new(tex.outputs["Color"], base_col.inputs["A"])
    base_col.inputs["B"].default_value = (0.64, 0.65, 0.64, 1.0)  # architectural concrete roof/balcony slab

    # Strong directional daylight shading so 3D balcony slab undersides (-Z) and side walls read with real depth
    sun_dot = _node(N, "VectorMath", (-320, -240))
    sun_dot.operation = "DOT_PRODUCT"
    L.new(nrm, sun_dot.inputs[0])
    sun_dot.inputs[1].default_value = (-0.42, 0.52, 0.74)

    shade = _node(N, "MapRange", (-120, -240))
    shade.clamp = True
    shade.inputs["From Min"].default_value = -0.80
    shade.inputs["From Max"].default_value = 0.85
    shade.inputs["To Min"].default_value = 0.42
    shade.inputs["To Max"].default_value = 1.08
    L.new(sun_dot.outputs["Value"], shade.inputs["Value"])

    s_cmb = _node(N, "CombineColor", (80, -220))
    for ch in ("Red", "Green", "Blue"):
        L.new(shade.outputs["Result"], s_cmb.inputs[ch])

    shaded = _node(N, "Mix", (300, 120))
    shaded.data_type = "RGBA"
    shaded.blend_type = "MULTIPLY"
    shaded.inputs["Factor"].default_value = 1.0
    L.new(base_col.outputs["Result"], shaded.inputs["A"])
    L.new(s_cmb.outputs["Color"], shaded.inputs["B"])

    # Tier-calibrated Korean aerial perspective haze: crisp near (8%), light mid (19%), strong far (42%)
    haze_amt = (0.08, 0.19, 0.42)[tier]
    haze = _node(N, "Mix", (460, 120))
    haze.data_type = "RGBA"
    haze.inputs["Factor"].default_value = haze_amt
    L.new(shaded.outputs["Result"], haze.inputs["A"])
    haze.inputs["B"].default_value = (0.82, 0.88, 0.95, 1.0)

    L.new(haze.outputs["Result"], bsdf.inputs["Emission Color"])
    # Slightly brighter as buildings recede into bright daytime sky (matches gym/221 & interior/101)
    bsdf.inputs["Emission Strength"].default_value = (1.65, 1.95, 2.25)[tier]
    return m


def _mat_sky_backdrop():
    """Bright Korean daytime partly-cloudy sky gradient behind the city skyline (refs gym/221, interior/101)."""
    name = PFX + "SkyBackdrop"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (0.70, 0.83, 0.96, 1.0)
    m["detail4_pkg"] = KEY
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    N.clear()

    out = _node(N, "OutputMaterial", (800, 0))
    bsdf = _node(N, "BsdfPrincipled", (520, 0))
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.0
    bsdf.inputs["Emission Strength"].default_value = 3.15
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    geo = _node(N, "NewGeometry", (-720, 0))
    sep = _node(N, "SeparateXYZ", (-520, 100))
    L.new(geo.outputs["Position"], sep.inputs["Vector"])

    # Vertical sky gradient calibrated to x=166 m sightline (z=0 horizon haze -> z=32 clear pale blue sky)
    z_map = _node(N, "MapRange", (-320, 120))
    z_map.clamp = True
    z_map.inputs["From Min"].default_value = -2.0
    z_map.inputs["From Max"].default_value = 32.0
    z_map.inputs["To Min"].default_value = 0.0
    z_map.inputs["To Max"].default_value = 1.0
    L.new(sep.outputs["Z"], z_map.inputs["Value"])

    grad = _node(N, "ValToRGB", (-80, 140))
    els = grad.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (0.91, 0.94, 0.97, 1.0)   # luminous hazy Korean urban horizon
    els[1].position = 0.38
    els[1].color = (0.70, 0.83, 0.96, 1.0)
    e2 = els.new(1.0)
    e2.color = (0.48, 0.70, 0.94, 1.0)       # crisp airy daytime sky blue
    L.new(z_map.outputs["Result"], grad.inputs["Fac"])

    c_sc = _node(N, "VectorMath", (-520, -140))
    c_sc.operation = "MULTIPLY"
    L.new(geo.outputs["Position"], c_sc.inputs[0])
    c_sc.inputs[1].default_value = (0.015, 0.022, 0.075)

    cloud = _node(N, "TexNoise", (-320, -140))
    cloud.inputs["Scale"].default_value = 1.05
    cloud.inputs["Detail"].default_value = 5.0
    cloud.inputs["Roughness"].default_value = 0.56
    L.new(c_sc.outputs["Vector"], cloud.inputs["Vector"])

    c_mask = _node(N, "MapRange", (-100, -140))
    c_mask.clamp = True
    c_mask.inputs["From Min"].default_value = 0.44
    c_mask.inputs["From Max"].default_value = 0.72
    c_mask.inputs["To Min"].default_value = 0.0
    c_mask.inputs["To Max"].default_value = 0.72
    L.new(cloud.outputs["Fac"], c_mask.inputs["Value"])

    mix = _node(N, "Mix", (220, 40))
    mix.data_type = "RGBA"
    L.new(c_mask.outputs["Result"], mix.inputs["Factor"])
    L.new(grad.outputs["Color"], mix.inputs["A"])
    mix.inputs["B"].default_value = (0.98, 0.99, 1.0, 1.0)
    L.new(mix.outputs["Result"], bsdf.inputs["Emission Color"])
    return m


def _mat_exterior_ground():
    name = PFX + "ExteriorGround"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m["detail4_pkg"] = KEY
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.95
    bsdf.inputs["Emission Color"].default_value = (0.48, 0.52, 0.56, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 1.15
    return m


def apply() -> dict:
    parent = bpy.data.collections["SET"]
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        parent.children.link(coll)
    elif coll.name not in parent.children:
        parent.children.link(coll)
    _clear_coll(coll)

    touched = []
    for ob_name in ("Window Sky", "Wall_Right"):
        info = _hide_existing(ob_name)
        if info:
            touched.append(info)

    added = []
    # 1. Exact cutout right wall
    added.append(_build_cutout_right_wall(coll))

    # 2. Charcoal horizontal transom bars at z=2.18 across all 4 bays
    m_frame = _mat_charcoal_hardware()
    transom_bm = bmesh.new()
    for y0, y1 in BAYS:
        _add_box_bm(transom_bm, 13.442, 13.524, y0, y1, TRANSOM_Z - 0.022, TRANSOM_Z + 0.022, bevel=0.002)
    added.append(_finish_bm(transom_bm, "TransomBars", m_frame, coll, cast_shadow=True))

    # 3. 4 window glass panes (x=13.504..13.508, >= 2 mm clear of transom/jambs/blinds)
    m_glass = _mat_glass()
    glass_bm = bmesh.new()
    for y0, y1 in BAYS:
        _add_box_bm(glass_bm, 13.504, 13.508, y0 + 0.002, y1 - 0.002, BAY_Z0 + 0.002, TRANSOM_Z - 0.024)
        _add_box_bm(glass_bm, 13.504, 13.508, y0 + 0.002, y1 - 0.002, TRANSOM_Z + 0.024, BAY_Z1 - 0.002)
    added.append(_finish_bm(glass_bm, "GlassPanes", m_glass, coll, cast_shadow=False))

    # 4. Roller blinds: top cassettes in all 4 bays + dark charcoal semi-sheer fabric & bottom hem bar
    #    in 3 lowered bays (Bay 0, 1, 3). Seated cleanly at x=13.428..13.488 (behind hanging TV x<=13.357).
    m_fabric = _mat_blind_fabric()
    hw_bm = bmesh.new()
    fab_bm = bmesh.new()
    bay_h = BAY_Z1 - BAY_Z0
    for (y0, y1), drop in zip(BAYS, BLIND_DROPS):
        by0, by1 = y0 + 0.012, y1 - 0.012
        _add_box_bm(hw_bm, 13.428, 13.488, by0, by1, 2.858, 2.918, bevel=0.002)
        for ye in (by0 - 0.004, by1 + 0.004):
            _add_box_bm(hw_bm, 13.426, 13.490, ye - 0.003, ye + 0.003, 2.854, 2.919)
        if drop > 0.05:
            z_bot = BAY_Z1 - bay_h * drop
            _add_box_bm(fab_bm, 13.434, 13.437, by0 + 0.006, by1 - 0.018, z_bot + 0.019, 2.856)
            _add_box_bm(hw_bm, 13.429, 13.442, by0 + 0.004, by1 - 0.016, z_bot, z_bot + 0.018, bevel=0.002)
            _add_box_bm(hw_bm, 13.434, 13.438, by1 - 0.010, by1 - 0.006, z_bot - 0.14, 2.856)

    added.append(_finish_bm(hw_bm, "RollerBlind_Hardware", m_frame, coll, cast_shadow=True))
    added.append(_finish_bm(fab_bm, "RollerBlind_Fabric", m_fabric, coll, cast_shadow=False))

    # 5. Exterior 3D Korean urban apartment & commercial skyline (x=62..146 m)
    #    Every sub-volume inside a building (main tower, parapet, penthouse, side stepped wing,
    #    3D protruding balcony slab ledges, vertical facade pilasters) is strictly disjoint (>= 20 mm)
    #    and every building pair is disjoint (0 BVH overlaps).
    for bname, xf, yc, dx, wy, bz, tz, tex_f, tw, th, tier, seed in BUILDINGS:
        bm = bmesh.new()
        y0, y1 = yc - wy * 0.5, yc + wy * 0.5
        _add_box_bm(bm, xf, xf + dx, y0, y1, bz, tz)
        rng = random.Random(seed)

        # Parapet cap resting 20 mm above main tower roof (no coplanar overlap)
        par_z0 = tz + 0.02
        par_z1 = tz + 0.68
        _add_box_bm(bm, xf - 0.18, xf + dx + 0.18, y0 - 0.18, y1 + 0.18, par_z0, par_z1)

        # Elevator/mechanical rooftop penthouse resting 20 mm above parapet top
        pw = wy * rng.uniform(0.24, 0.34)
        pd = dx * rng.uniform(0.40, 0.54)
        ph = rng.uniform(1.6, 2.5)
        py_off = rng.uniform(-wy * 0.15, wy * 0.15)
        _add_box_bm(bm, xf + dx * 0.24, xf + dx * 0.24 + pd,
                    yc + py_off - pw * 0.5, yc + py_off + pw * 0.5, par_z1 + 0.02, par_z1 + 0.02 + ph)

        # 3D facade relief on visible upper floors (near & mid tiers): vertical structural pilasters
        # and protruding horizontal balcony slab bands (strictly >= 20 mm clear of tower & each other)
        if tier in (0, 1):
            z_vis_lo = max(bz + 1.0, -12.0 if tier == 0 else -16.0)
            pil_w = 0.65
            # Left, center-stairwell, and right vertical pilasters
            pil_spans = (
                (y0, y0 + pil_w),
                (yc - pil_w * 0.6, yc + pil_w * 0.6),
                (y1 - pil_w, y1),
            )
            for py0, py1 in pil_spans:
                _add_box_bm(bm, xf - 0.44, xf - 0.02, py0, py1, z_vis_lo, tz - 0.02)

            # Horizontal protruding balcony/spandrel slab ledges between pilasters (cast real underside shade)
            floor_h = 3.2 if tier == 0 else 2.8
            bay_spans = (
                (y0 + pil_w + 0.04, yc - pil_w * 0.6 - 0.04),
                (yc + pil_w * 0.6 + 0.04, y1 - pil_w - 0.04),
            )
            z_cur = tz - floor_h
            while z_cur > z_vis_lo + 0.5:
                for by0, by1 in bay_spans:
                    _add_box_bm(bm, xf - 0.58, xf - 0.02, by0, by1, z_cur - 0.26, z_cur)
                z_cur -= floor_h

        # Stepped apartment side wing positioned 20 mm off the side of mid/far slabs (strictly clear of neighbors)
        if tier in (1, 2):
            side = 1.0 if (seed % 2 == 0) else -1.0
            wing_w = 2.4
            if side > 0:
                wy0, wy1 = y1 + 0.04, y1 + 0.04 + wing_w
            else:
                wy0, wy1 = y0 - 0.04 - wing_w, y0 - 0.04
            _add_box_bm(bm, xf + 1.4, xf + dx - 1.0, wy0, wy1, bz, tz - 2.6)

        bm.normal_update()
        _apply_box_uvs(bm, tw, th, y_off=rng.uniform(0.0, tw), z_off=-bz)
        mat_b = _mat_building_textured(bname, tex_f, xf, tier)
        added.append(_finish_bm(bm, bname, mat_b, coll, cast_shadow=False))

    # 6. Exterior ground & bright daylight sky backdrop (strictly clear of buildings & each other)
    g_bm = bmesh.new()
    _add_box_bm(g_bm, 14.0, 164.0, -130.0, 130.0, -47.2, -46.2)
    added.append(_finish_bm(g_bm, "ExteriorGround", _mat_exterior_ground(), coll, cast_shadow=False))

    sky_bm = bmesh.new()
    _add_box_bm(sky_bm, 166.0, 166.5, -180.0, 180.0, -50.0, 95.0)
    added.append(_finish_bm(sky_bm, "SkyBackdrop", _mat_sky_backdrop(), coll, cast_shadow=False))

    bpy.context.view_layer.update()
    tris = 0
    bboxes = {}
    for ob in added:
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        bboxes[ob.name] = (
            [round(min(p[i] for p in pts), 3) for i in range(3)]
            + [round(max(p[i] for p in pts), 3) for i in range(3)]
        )

    return {
        "collection": COLL,
        "objects_added": [o.name for o in added],
        "objects_added_count": len(added),
        "triangles_added": tris,
        "existing_touched": touched,
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
