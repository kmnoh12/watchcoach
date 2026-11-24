"""Detail package `hall_surfaces`: the sangga hallway shell outside the gym entrance.

Run inside the open scene_gym.blend (never saved here):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_hall_surfaces; detail_hall_surfaces.apply()

Builds (all in hallway-local metres, parented to `Sangga_Hallway`):
  * Floor: glossy beige-grey polished porcelain tile 600x1200 (폴리싱 타일), thin light grout
    (refs hall 068 070 072 073 075 076 088 092). Material swap on `Hallway floor` + `HallExt floor`.
  * Ceiling: white mineral-fibre tex board (텍스) in a light 600x600 M-bar grid, a centre row of round
    LED downlights that really light the corridor (spot lights), sprinkler heads, smoke detectors,
    ceiling speaker, emergency light and 450 inspection hatches (refs 035 057 062 088 092 006 013 005 042 090).
  * Walls: ivory paint above a speckled granite wainscot + black granite skirting on the bare gym-side
    wall, infill of the open gap between the hallway extension and the gym front wall, PVC corner guard
    on the new outside corner (refs 088 092 093 062 065 070).

Textures are generated (numpy inside Blender) into promo/parts/detail_hall_surfaces/:
    Blender -b --factory-startup --python promo/tools/detail_hall_surfaces.py -- --gen-textures
"""
import math
import os
import sys

KEY = "hall_surfaces"
COLL = "DETAIL_hall_surfaces"
PFX = "Dhall_surfaces_"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX_DIR = os.path.join(ROOT, "parts", "detail_hall_surfaces")
FLOOR_IMG = "floor_polished_tile_2400.jpg"      # 2.4 m x 2.4 m: 4 rows x 2 cols of 600x1200 tiles
FLOOR_GROUT = "floor_grout_mask_2400.png"
CEIL_IMG = "ceiling_tex_board_1200.jpg"          # 1.2 m x 1.2 m: 2 x 2 tex boards (600x600)

# ---- layout (hallway local frame: x along corridor, y=0 gym side, z up) ----
X_MIN, X_MAX = -11.50, 4.61       # elevator wall .. far end wall
CEIL_Z = 2.75                     # ceiling underside
GRID_PHASE = 0.30                 # M-bar joints at x = 0.3 + 0.6 k
GRID_Y = (0.56, 1.16, 1.76, 2.36)  # joints across (centre tile row = 1.16..1.76)
ROW_C, ROW_G, ROW_O = 1.46, 0.86, 2.06   # tile-centre rows: centre / gym side / opposite side
# Downlights in the centre row; ext positions skip existing smoke detectors, speakers, hanging sign
DOWNLIGHTS_X = (-10.8, -9.6, -7.8, -6.0, -4.8, -3.6, -2.4, -1.2, 0.0, 1.2, 2.4, 3.6)
SPRINKLERS = [(x, ROW_G) for x in (-10.2, -7.8, -5.4, -3.0, -0.6, 1.8, 4.2)]
SMOKE_DET = [(-3.0, ROW_O), (3.0, ROW_O)]          # ext already has 3 on its centre line
SPEAKERS = [(-1.8, ROW_O)]                          # ext already has 2
EMERGENCY = [(2.4, ROW_G), (-9.0, ROW_O)]
HATCHES = [(4.2, ROW_O), (-7.2, ROW_O)]
GYM_WALL_Y = 0.154                # hallway face of the gym's Wall_Left (x >= -1.35)
WALL_STEP_X = -1.35               # end of Wall_Left; gap to the ext wall is open before this package
DOOR_X = 0.80                     # gym entrance opening half width (wall cutter), height 2.25
DOOR_H = 2.25
WAINSCOT_H = 1.12                 # matches HallExt wall L lower

HIDE_PREFIXES = ("Tex grid X", "Tex grid Y", "HallExt grid X", "HallExt grid Y",
                 "Hallway troffer frame", "Hallway troffer tube", "HallExt_Troffer_", "HallExt_LED_",
                 "Hallway LED lens", "HallwayLight_", "HallExtLight_")


# =====================================================================================
# texture generation (numpy, run once; results are committed as files in TEX_DIR)
# =====================================================================================
def _value_noise(np, rng, h, w, cells):
    """Tileable bilinear value noise with `cells` cells across."""
    g = rng.random((cells + 1, cells + 1))
    g[-1, :] = g[0, :]
    g[:, -1] = g[:, 0]
    ys = np.linspace(0, cells, h, endpoint=False)
    xs = np.linspace(0, cells, w, endpoint=False)
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _fbm(np, rng, h, w, base, octaves=5, gain=0.5):
    out = np.zeros((h, w))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += amp * _value_noise(np, rng, h, w, base * 2 ** o)
        tot += amp
        amp *= gain
    return out / tot


def _marble_tile(np, rng, h, w):
    """One 600x1200 polished porcelain face: beige-grey base, domain-warped taupe clouds, a few faint
    light veins and fine crystal speckle (ref 070/072/073)."""
    wx = _fbm(np, rng, h, w, 2, 4)
    wy = _fbm(np, rng, h, w, 2, 4)
    yy, xx = np.mgrid[0:h, 0:w]
    # domain warp by resampling a cloud field at displaced coordinates
    big = _fbm(np, rng, h, w, 4, 6)
    sx = np.clip((xx + (wx - 0.5) * w * 0.35).astype(int), 0, w - 1)
    sy = np.clip((yy + (wy - 0.5) * h * 0.35).astype(int), 0, h - 1)
    clouds = big[sy, sx]
    fine = _fbm(np, rng, h, w, 24, 3)
    ang = rng.uniform(-0.5, 0.5)
    t = ((xx / w) * math.cos(ang) + (yy / w) * math.sin(ang)) * rng.uniform(1.4, 2.4) + wx * 2.5
    vein = np.exp(-np.abs(np.sin(t * math.pi)) * 70.0)
    base = np.array([214, 206, 194], float) * rng.uniform(0.98, 1.02)
    dark = np.array([182, 169, 154], float)
    light = np.array([232, 228, 220], float)
    m = np.clip((clouds - 0.46) * 3.0, 0, 1) ** 1.3
    m = m * (0.75 + fine * 0.5)
    col = base * (1 - m[..., None] * 0.7) + dark * (m[..., None] * 0.7)
    col = col * (1 - vein[..., None] * 0.35) + light * (vein[..., None] * 0.35)
    speck = rng.random((h, w))
    col[speck > 0.997] *= 0.88
    col[speck < 0.002] = col[speck < 0.002] * 0.6 + light * 0.4
    return col


def gen_textures():
    import numpy as np
    import bpy
    os.makedirs(TEX_DIR, exist_ok=True)
    rng = np.random.default_rng(2026)

    # --- floor: 2048 px = 2.4 m; rows of 600 (512 px) along y, 1200 (1024 px) along x, half-bond ---
    N = 2048
    floor = np.zeros((N, N, 3))
    grout = np.ones((N, N))
    th, tw = 512, 1024
    for r in range(4):
        off = 0 if r % 2 == 0 else tw // 2
        for k in range(-1, 2):
            x0 = k * tw + off
            tile = _marble_tile(np, rng, th, tw)
            xs0, xs1 = max(x0, 0), min(x0 + tw, N)
            if xs1 <= xs0:
                continue
            floor[r * th:(r + 1) * th, xs0:xs1] = tile[:, xs0 - x0:xs1 - x0]
            grout[r * th:(r + 1) * th, xs0:xs0 + 1] = 0.0
            grout[r * th:(r + 1) * th, xs1 - 1:xs1] = 0.0
        grout[r * th:r * th + 1, :] = 0.0
        grout[(r + 1) * th - 1:(r + 1) * th, :] = 0.0
    gcol = np.array([186, 179, 168], float)
    floor = floor * grout[..., None] + gcol * (1 - grout[..., None])
    _save_img(bpy, np, floor / 255.0, FLOOR_IMG, "JPEG")
    _save_img(bpy, np, np.repeat(grout[..., None], 3, axis=2), FLOOR_GROUT, "PNG")

    # --- ceiling: 2048 px = 1.2 m = 2 x 2 tex boards with fissures + pinholes (ref 035 057) ---
    ceil = np.zeros((N, N, 3))
    half = N // 2
    for by in range(2):
        for bx in range(2):
            mott = _fbm(np, rng, half, half, 6, 4)
            base = np.array([236, 235, 230], float) * (0.985 + mott[..., None] * 0.03)
            col = base.copy()
            # short fissure "worms" (1-2 px wide, 6-40 px long) as on mineral-fibre tex boards
            for _ in range(2600):
                x, y = rng.uniform(0, half, 2)
                a = rng.uniform(0, 2 * math.pi)
                shade = rng.uniform(150, 195)
                for _s in range(int(rng.integers(4, 22))):
                    a += rng.normal(0, 0.6)
                    x = (x + 1.6 * math.cos(a)) % half
                    y = (y + 1.6 * math.sin(a)) % half
                    ix, iy = int(x), int(y)
                    col[iy, ix] = shade
                    col[iy, (ix + 1) % half] = (shade + 235) / 2
            holes = rng.random((half, half)) > 0.9975
            col[holes] = [140, 140, 136]
            col[:3, :] *= 0.93
            col[-3:, :] *= 0.93
            col[:, :3] *= 0.93
            col[:, -3:] *= 0.93
            ceil[by * half:(by + 1) * half, bx * half:(bx + 1) * half] = col
    _save_img(bpy, np, ceil / 255.0, CEIL_IMG, "JPEG")


def _save_img(bpy, np, arr, fname, fmt):
    h, w, _ = arr.shape
    im = bpy.data.images.new("gen_" + fname, w, h, alpha=False)
    px = np.ones((h, w, 4))
    px[..., :3] = np.clip(arr[::-1], 0, 1)
    im.pixels.foreach_set(px.ravel().astype(np.float32))
    im.filepath_raw = os.path.join(TEX_DIR, fname)
    im.file_format = fmt
    if fmt == "JPEG":
        bpy.context.scene.render.image_settings.quality = 90
    im.save()
    bpy.data.images.remove(im)


# =====================================================================================
# scene helpers
# =====================================================================================
def _img(bpy, fname, non_color=False):
    im = bpy.data.images.load(os.path.join(TEX_DIR, fname), check_existing=True)
    if not im.packed_file:
        im.pack()
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def _new_mat(bpy, name):
    m = bpy.data.materials.get(name)
    if m:
        return m, False
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, True


def _hall_coords(nt, hall, scale, offset=(0.0, 0.0, 0.0)):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = hall
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = offset
    mp.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return tc, mp


def _floor_mat(bpy, hall):
    m, new = _new_mat(bpy, PFX + "PolishedTile")
    if not new:
        return m
    nt = m.node_tree
    L = nt.links.new
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc, mp = _hall_coords(nt, hall, (1 / 2.4, 1 / 2.4, 1.0), (0.0, 0.05 / 2.4, 0.0))
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = _img(bpy, FLOOR_IMG)
    gr = nt.nodes.new("ShaderNodeTexImage")
    gr.image = _img(bpy, FLOOR_GROUT, non_color=True)
    for t in (col, gr):
        L(mp.outputs["Vector"], t.inputs["Vector"])
    # broad, very low contrast cloudiness to break the 2.4 m repeat
    big = nt.nodes.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.35
    big.inputs["Detail"].default_value = 2.0
    L(tc.outputs["Object"], big.inputs["Vector"])
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 0.12
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.9, 0.9, 0.9, 1)
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
    L(big.outputs["Fac"], ramp.inputs["Fac"])
    L(col.outputs["Color"], tint.inputs["A"])
    L(ramp.outputs["Color"], tint.inputs["B"])
    L(tint.outputs["Result"], b.inputs["Base Color"])
    # roughness: polished face 0.05..0.12 (fine smudge noise), grout 0.55
    sm = nt.nodes.new("ShaderNodeTexNoise")
    sm.inputs["Scale"].default_value = 2.2
    sm.inputs["Detail"].default_value = 6.0
    L(tc.outputs["Object"], sm.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["From Min"].default_value = 0.35
    rr.inputs["From Max"].default_value = 0.65
    rr.inputs["To Min"].default_value = 0.05
    rr.inputs["To Max"].default_value = 0.12
    L(sm.outputs["Fac"], rr.inputs["Value"])
    gmix = nt.nodes.new("ShaderNodeMix")
    gmix.data_type = "FLOAT"
    gmix.inputs["B"].default_value = 0.55
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    L(gr.outputs["Color"], inv.inputs[1])
    L(inv.outputs["Value"], gmix.inputs["Factor"])
    L(rr.outputs["Result"], gmix.inputs["A"])
    L(gmix.outputs["Result"], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.0008
    L(gr.outputs["Color"], bump.inputs["Height"])
    L(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Specular IOR Level"].default_value = 0.5
    m.diffuse_color = (0.62, 0.58, 0.53, 1)
    return m


def _ceiling_mat(bpy, hall):
    m, new = _new_mat(bpy, PFX + "TexBoard")
    if not new:
        return m
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc, mp = _hall_coords(nt, hall, (1 / 1.2, 1 / 1.2, 1.0), (-GRID_PHASE / 1.2, -GRID_Y[0] / 1.2, 0.0))
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = _img(bpy, CEIL_IMG)
    nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.88
    b.inputs["Specular IOR Level"].default_value = 0.3
    m.diffuse_color = (0.82, 0.82, 0.80, 1)
    return m


def _paint_mat(bpy):
    m, new = _new_mat(bpy, PFX + "IvoryPaint")
    if not new:
        return m
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.74, 0.72, 0.665, 1)
    b.inputs["Roughness"].default_value = 0.55
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 260.0          # roller orange-peel
    nz.inputs["Detail"].default_value = 3.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    bump.inputs["Distance"].default_value = 0.0003
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = (0.74, 0.72, 0.665, 1)
    return m


def _emit_mat(bpy, name, color, strength):
    m, new = _new_mat(bpy, name)
    if new:
        b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = strength
        b.inputs["Roughness"].default_value = 0.3
        m.diffuse_color = (*color, 1)
    return m


# ---- mesh building ----
def _bm_box(bmesh, Matrix, bm, lo, hi):
    cx, cy, cz = [(a + b) / 2 for a, b in zip(lo, hi)]
    sx, sy, sz = [b - a for a, b in zip(lo, hi)]
    mat = Matrix.Translation((cx, cy, cz)) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def _mesh_from_boxes(bpy, bmesh, Matrix, name, boxes, mat, c, parent, bevel=0.0):
    bm = bmesh.new()
    for lo, hi in boxes:
        _bm_box(bmesh, Matrix, bm, lo, hi)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES",
                        profile=0.5, clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.parent = parent
    return ob


def _cyl_mesh(bpy, bmesh, name, parts):
    """parts: list of (r1, r2, z0, z1, seg, mat_index) -> one mesh (z = local, centred at origin xy)."""
    from mathutils import Matrix
    bm = bmesh.new()
    for r1, r2, z0, z1, seg, mi in parts:
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=z1 - z0,
                                    matrix=Matrix.Translation((0, 0, (z0 + z1) / 2)))
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = mi
            f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _inst(bpy, c, parent, name, me, loc, rot_z=0.0):
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = (0, 0, rot_z)
    return ob


def _descendants(ob):
    out = []
    for ch in ob.children:
        out.append(ch)
        out += _descendants(ch)
    return out


def _tag_swap(ob, mat):
    if "dhs_orig_mats" not in ob:
        ob["dhs_orig_mats"] = ",".join(s.material.name if s.material else "" for s in ob.material_slots)
    ob["detail_pkg"] = KEY
    for s in ob.material_slots:
        s.material = mat


def _tag_hide(ob):
    if "dhs_orig_hide" not in ob:
        ob["dhs_orig_hide"] = [int(ob.hide_render), int(ob.hide_viewport)]
    ob["detail_pkg"] = KEY
    ob.hide_render = True
    ob.hide_viewport = True


def revert():
    """Undo every change this package made to existing objects and remove its collection."""
    import bpy
    for ob in bpy.data.objects:
        if ob.get("detail_pkg") != KEY:
            continue
        if "dhs_orig_mats" in ob:
            names = ob["dhs_orig_mats"].split(",")
            for s, n in zip(ob.material_slots, names):
                s.material = bpy.data.materials.get(n) if n else None
            del ob["dhs_orig_mats"]
        if "dhs_orig_hide" in ob:
            ob.hide_render, ob.hide_viewport = bool(ob["dhs_orig_hide"][0]), bool(ob["dhs_orig_hide"][1])
            del ob["dhs_orig_hide"]
        del ob["detail_pkg"]
    c = bpy.data.collections.get(COLL)
    if c:
        for ob in list(c.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(c)


# =====================================================================================
# apply
# =====================================================================================
def apply() -> dict:
    import bmesh
    import bpy
    from mathutils import Matrix

    hall = bpy.data.objects["Sangga_Hallway"]
    set_c = bpy.data.collections["SET"]
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        set_c.children.link(c)
    for ob in list(c.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    root = bpy.data.objects.new(PFX + "Root", None)
    c.objects.link(root)
    root.parent = hall          # identity local transform: children work in hallway-local metres

    # ---------------- materials ----------------
    floor_m = _floor_mat(bpy, hall)
    ceil_m = _ceiling_mat(bpy, hall)
    paint_m = _paint_mat(bpy)
    granite_m = bpy.data.materials.get("Elev_GrayGranite")          # reuse the ext wainscot granite
    black_m = bpy.data.materials.get("Hallway_BlackGranite")        # reuse the existing skirting granite

    def pmat(name, color, rough, metal=0.0):
        m, new = _new_mat(bpy, PFX + name)
        if new:
            b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            b.inputs["Base Color"].default_value = (*color, 1)
            b.inputs["Roughness"].default_value = rough
            b.inputs["Metallic"].default_value = metal
            m.diffuse_color = (*color, 1)
        return m

    mbar_m = pmat("MBarWhite", (0.80, 0.80, 0.78), 0.45, 0.3)
    trim_m = pmat("DownlightTrim", (0.86, 0.86, 0.85), 0.35, 0.2)
    plastic_m = pmat("DevicePlastic", (0.84, 0.84, 0.82), 0.45)
    grille_m = pmat("SpeakerGrille", (0.62, 0.62, 0.61), 0.6, 0.3)
    chrome_m = pmat("SprinklerChrome", (0.80, 0.80, 0.78), 0.18, 1.0)
    bulb_m = pmat("SprinklerBulbRed", (0.75, 0.04, 0.03), 0.1)
    guard_m = pmat("CornerGuardPVC", (0.80, 0.79, 0.76), 0.35)
    lens_m = _emit_mat(bpy, PFX + "DownlightLens", (1.0, 0.97, 0.93), 12.0)
    emer_lens_m = _emit_mat(bpy, PFX + "EmergencyLens", (0.95, 0.95, 0.92), 0.4)
    led_red_m = _emit_mat(bpy, PFX + "LedRed", (1.0, 0.06, 0.04), 4.0)
    led_green_m = _emit_mat(bpy, PFX + "LedGreen", (0.1, 1.0, 0.3), 4.0)

    # ---------------- existing-object edits (tagged, reversible, non-stacking) ----------------
    touched = []
    hall_desc = _descendants(hall)
    for ob in hall_desc:
        n = ob.name
        if ob.type == "MESH" and n in ("Hallway floor", "HallExt floor"):
            _tag_swap(ob, floor_m); touched.append((n, "material -> " + floor_m.name))
        elif ob.type == "MESH" and n in ("Hallway ceiling", "HallExt ceiling"):
            _tag_swap(ob, ceil_m); touched.append((n, "material -> " + ceil_m.name))
        elif ob.type == "MESH" and (n in ("HallExt wall L upper", "Opposite wall left", "Opposite wall right")
                                    or n.startswith("Hallway far end")):
            _tag_swap(ob, paint_m); touched.append((n, "material -> " + paint_m.name))
        elif n.startswith(HIDE_PREFIXES):
            _tag_hide(ob); touched.append((n, "hidden (superseded)"))

    added = []

    # ---------------- ceiling: M-bar grid (one mesh) ----------------
    zb, zt = CEIL_Z - 0.0035, CEIL_Z - 0.0005
    boxes = []
    k0 = math.ceil((X_MIN - GRID_PHASE) / 0.6)
    k1 = math.floor((X_MAX - GRID_PHASE) / 0.6)
    for k in range(k0, k1 + 1):
        gx = GRID_PHASE + 0.6 * k
        boxes.append(((gx - 0.005, 0.0, zb), (gx + 0.005, 2.88, zt)))
    for gy in GRID_Y:
        boxes.append(((X_MIN, gy - 0.005, zb), (X_MAX, gy + 0.005, zt)))
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "MBarGrid", boxes, mbar_m, c, root))

    # ---------------- ceiling devices (shared meshes = linked duplicates) ----------------
    dl_me = _cyl_mesh(bpy, bmesh, PFX + "Downlight_mesh",
                      [(0.090, 0.088, -0.0065, -0.0005, 32, 0), (0.072, 0.072, -0.008, -0.004, 32, 1)])
    dl_me.materials.append(trim_m); dl_me.materials.append(lens_m)
    sd_me = _cyl_mesh(bpy, bmesh, PFX + "SmokeDet_mesh",
                      [(0.060, 0.058, -0.0125, -0.0005, 24, 0), (0.050, 0.042, -0.040, -0.0125, 24, 0),
                       (0.020, 0.020, -0.042, -0.040, 16, 0)])
    sd_me.materials.append(plastic_m)
    led_me = _cyl_mesh(bpy, bmesh, PFX + "SmokeLed_mesh", [(0.004, 0.004, -0.004, 0.0, 8, 0)])
    led_me.materials.append(led_red_m)
    sp_me = _cyl_mesh(bpy, bmesh, PFX + "Sprinkler_mesh",
                      [(0.032, 0.022, -0.0105, -0.0005, 20, 0), (0.008, 0.007, -0.040, -0.0105, 10, 0),
                       (0.015, 0.015, -0.052, -0.050, 12, 0), (0.0025, 0.0025, -0.050, -0.040, 6, 0),
                       (0.0032, 0.0032, -0.049, -0.037, 8, 1)])
    sp_me.materials.append(chrome_m); sp_me.materials.append(bulb_m)
    spk_me = _cyl_mesh(bpy, bmesh, PFX + "Speaker_mesh",
                       [(0.110, 0.106, -0.0085, -0.0005, 32, 0), (0.088, 0.088, -0.0095, -0.0080, 32, 1)])
    spk_me.materials.append(plastic_m); spk_me.materials.append(grille_m)

    for i, x in enumerate(DOWNLIGHTS_X):
        added.append(_inst(bpy, c, root, f"{PFX}Downlight_{i:02d}", dl_me, (x, ROW_C, CEIL_Z)))
    for i, (x, y) in enumerate(SPRINKLERS):
        added.append(_inst(bpy, c, root, f"{PFX}Sprinkler_{i:02d}", sp_me, (x, y, CEIL_Z)))
    for i, (x, y) in enumerate(SMOKE_DET):
        added.append(_inst(bpy, c, root, f"{PFX}SmokeDet_{i:02d}", sd_me, (x, y, CEIL_Z)))
        added.append(_inst(bpy, c, root, f"{PFX}SmokeLed_{i:02d}", led_me, (x + 0.030, y, CEIL_Z - 0.0400)))
    for i, (x, y) in enumerate(SPEAKERS):
        added.append(_inst(bpy, c, root, f"{PFX}Speaker_{i:02d}", spk_me, (x, y, CEIL_Z)))

    # emergency light (비상조명등): white box, two lamp lenses, green pilot LED
    for i, (x, y) in enumerate(EMERGENCY):
        e = _mesh_from_boxes(bpy, bmesh, Matrix, f"{PFX}Emergency_{i:02d}",
                             [((x - 0.13, y - 0.05, CEIL_Z - 0.048), (x + 0.13, y + 0.05, CEIL_Z - 0.0005))],
                             plastic_m, c, root, bevel=0.006)
        added.append(e)
        lm = _cyl_mesh(bpy, bmesh, f"{PFX}EmergencyLamps_{i:02d}",
                       [(0.026, 0.024, -0.006, 0.0, 20, 0)])
        lm.materials.append(emer_lens_m)
        for j, dx in enumerate((-0.075, 0.075)):
            added.append(_inst(bpy, c, root, f"{PFX}EmergencyLamp_{i:02d}{j}", lm, (x + dx, y, CEIL_Z - 0.0475)))
        gm = _cyl_mesh(bpy, bmesh, f"{PFX}EmergencyPilot_{i:02d}", [(0.004, 0.004, -0.003, 0.0, 8, 0)])
        gm.materials.append(led_green_m)
        added.append(_inst(bpy, c, root, f"{PFX}EmergencyPilot_{i:02d}", gm, (x, y + 0.03, CEIL_Z - 0.0475)))

    # inspection hatch (점검구 450): white aluminium frame + tex panel, sits inside one board
    for i, (x, y) in enumerate(HATCHES):
        h = 0.235
        fr = [((x - h, y - h, CEIL_Z - 0.0065), (x + h, y - h + 0.016, CEIL_Z - 0.0005)),
              ((x - h, y + h - 0.016, CEIL_Z - 0.0065), (x + h, y + h, CEIL_Z - 0.0005)),
              ((x - h, y - h + 0.016, CEIL_Z - 0.0065), (x - h + 0.016, y + h - 0.016, CEIL_Z - 0.0005)),
              ((x + h - 0.016, y - h + 0.016, CEIL_Z - 0.0065), (x + h, y + h - 0.016, CEIL_Z - 0.0005))]
        added.append(_mesh_from_boxes(bpy, bmesh, Matrix, f"{PFX}HatchFrame_{i:02d}", fr, mbar_m, c, root))
        added.append(_mesh_from_boxes(bpy, bmesh, Matrix, f"{PFX}HatchPanel_{i:02d}",
                                      [((x - h + 0.016, y - h + 0.016, CEIL_Z - 0.0050),
                                        (x + h - 0.016, y + h - 0.016, CEIL_Z - 0.0010))], ceil_m, c, root))
        added.append(_mesh_from_boxes(bpy, bmesh, Matrix, f"{PFX}HatchLatch_{i:02d}",
                                      [((x + h - 0.06, y - 0.012, CEIL_Z - 0.0075),
                                        (x + h - 0.036, y + 0.012, CEIL_Z - 0.0045))], chrome_m, c, root))

    # ---------------- walls ----------------
    zc = CEIL_Z + 0.01
    # (a) infill of the open gap x = ext junction .. gym front wall (gym side), continuing the ext wall build-up
    xa, xb = -4.63, WALL_STEP_X
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "GymSideInfill_Paint",
                                  [((xa, -0.17, 0.001), (-1.30, 0.020, zc))], paint_m, c, root))
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "GymSideInfill_Wainscot",
                                  [((-4.62, 0.0, 0.001), (xb - 0.04, 0.040, WAINSCOT_H))], granite_m, c, root))
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "GymSideInfill_Skirting",
                                  [((-4.62, 0.0, 0.0015), (xb - 0.04, 0.050, 0.10))], black_m, c, root, bevel=0.003))
    # (b) skin over the gym Wall_Left hallway face (x -1.35 .. far end), opening for the entrance door
    y0, y1 = GYM_WALL_Y - 0.010, GYM_WALL_Y + 0.004
    xe = 4.600   # stop at the hall_props end wall plinth (x 4.602)
    skin = [((xb, y0, 0.001), (-DOOR_X, y1, zc)), ((DOOR_X, y0, 0.001), (xe, y1, zc)),
            ((-DOOR_X, y0, DOOR_H), (DOOR_X, y1, zc)),
            ((xb - 0.006, 0.020, 0.001), (xb - 0.001, y1, zc))]            # return face at the outside corner
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "GymWall_PaintSkin", skin, paint_m, c, root))
    wy1 = GYM_WALL_Y + 0.012   # thin stone cladding: keeps wall-standing props clear
    wain = [((xb, y0, 0.001), (-DOOR_X - 0.025, wy1, WAINSCOT_H)),
            ((DOOR_X + 0.025, y0, 0.001), (xe, wy1, WAINSCOT_H)),
            ((xb - 0.04, 0.035, 0.001), (xb, wy1, WAINSCOT_H))]           # wraps the outside corner
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "GymWall_Wainscot", wain, granite_m, c, root,
                                  bevel=0.002))
    sk1 = GYM_WALL_Y + 0.015
    skirt = [((xb, y0, 0.0015), (-DOOR_X - 0.025, sk1, 0.10)),
             ((DOOR_X + 0.025, y0, 0.0015), (xe, sk1, 0.10)),
             ((xb - 0.05, 0.045, 0.0015), (xb, sk1, 0.10))]   # far end skirting belongs to hall_props' end wall
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "GymWall_Skirting", skirt, black_m, c, root,
                                  bevel=0.003))
    # (c) PVC corner guard (L angle 30x30) on the new outside corner, above the wainscot
    gx, gy = xb - 0.006, y1                     # paint corner: main face y=gy, return face x=gx
    guard = [((gx - 0.003, gy + 0.0005, WAINSCOT_H + 0.002), (gx + 0.030, gy + 0.0035, 2.40)),
             ((gx - 0.0035, gy - 0.030, WAINSCOT_H + 0.002), (gx - 0.0005, gy + 0.0035, 2.40))]
    added.append(_mesh_from_boxes(bpy, bmesh, Matrix, PFX + "CornerGuard", guard, guard_m, c, root))

    # ---------------- lighting: one spot per downlight + floor-bounce fill ----------------
    for i, x in enumerate(DOWNLIGHTS_X):
        ld = bpy.data.lights.get(f"{PFX}DownlightSpot") or bpy.data.lights.new(f"{PFX}DownlightSpot", "SPOT")
        ld.energy = 75.0
        ld.color = (1.0, 0.97, 0.93)
        ld.spot_size = math.radians(115)
        ld.spot_blend = 0.65
        ld.shadow_soft_size = 0.07
        ld.use_shadow = True
        lo = bpy.data.objects.new(f"{PFX}DownlightSpot_{i:02d}", ld)
        c.objects.link(lo)
        lo.parent = root
        lo.location = (x, ROW_C, CEIL_Z - 0.012)
        added.append(lo)
    # light reflected off the bright polished floor onto the white ceiling and walls (soft, no shadows)
    for nm, x0, x1 in (("Main", -4.65, 4.61), ("Ext", -11.50, -4.65)):
        ld = bpy.data.lights.get(f"{PFX}FloorBounce_{nm}") or bpy.data.lights.new(f"{PFX}FloorBounce_{nm}", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = x1 - x0, 2.4
        ld.energy = 22.0 * (x1 - x0)
        ld.color = (1.0, 0.97, 0.92)
        ld.use_shadow = False
        lo = bpy.data.objects.new(f"{PFX}FloorBounce_{nm}", ld)
        c.objects.link(lo)
        lo.parent = root
        lo.location = ((x0 + x1) / 2, ROW_C, 0.03)
        lo.rotation_euler = (math.pi, 0, 0)     # emit upward
        added.append(lo)

    # ---------------- stats ----------------
    deps = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in c.objects:
        if ob.type == "MESH":
            tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    return {"collection": COLL, "objects_added": len(c.objects), "triangles_added": tris,
            "existing_touched": touched}


if __name__ == "__main__":
    if "--gen-textures" in sys.argv:
        gen_textures()
        print("textures written to", TEX_DIR)
