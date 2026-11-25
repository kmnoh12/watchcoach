"""WatchCoach gym annex, phase 3: gender-separated locker suites behind the gym front wall.

build_locker_suites(parent) adds two suites that mirror each other across a central partition at x = 11.60:
  Men   x  7.40 .. 11.55      Women  x 11.65 .. 15.80      y -6.90 (front) .. -17.10 (back), ceiling z = 3.00
  Locker room  y  -6.90 .. -12.30 (5.4 m deep, ~22.4 m2)   entered through the MEN / WOMEN doors (x 10.95 / 12.25) of gym_annex.build_gym_doors
  Behind the locker room the suite splits in two, both reached straight from the locker room's back wall:
    Shower    (partition side)  open doorway (no door), white marble tile, 3 frameless clear/frosted glass booths
    Restroom  (outer side)      its own door; fluted green-glass vanity with pill mirrors, 2 stainless WC cubicles,
                                stainless towel/dryer unit (+ 2 urinals with screens for men)
Locker room layout (pass 3, Korean gym 탈의실 refs work/refs/interior 002 005 008 011 020 032): 2-tier lockers line
the walls (front run beside the entry, a long outer-wall run, a short run on the partition near the back), the vanity
sits mid-partition and one low bench runs down the middle with >= 1.2 m clear aisles on both sides.
Every suite works in its own frame: u = distance from the partition face toward the suite's outer wall.
"""
import math

import bmesh
import bpy
import wc_lib as W

Y_FRONT, Y_LBACK = -6.90, -12.30
Y_BACK = Y_LBACK - 4.80        # shower + restroom zone keeps its 4.8 m depth behind the locker room
CEIL = 3.00
PART_X, PART_T = 11.60, 0.10   # central partition
WIDTH = 4.15                   # inner width of one suite
SHELL_T = 0.15                 # outer shell walls
WALL_T = 0.10                  # locker back wall
U_DIV, DIV_T = 2.05, 0.10      # wall between shower (u < 2.00) and restroom (u > 2.10)
ENTRY_W, ENTRY_H = 0.91, 2.18  # same opening gym_annex cuts through Wall_Front
SHOWER_OPEN = (0.70, 1.70, 2.20)  # open doorway locker -> shower (u0, u1, top)
WC_DOOR = (2.55, 3.45, 2.10)      # door locker -> restroom
BOOTH_D = 1.05                    # booth depth from the partition wall
BOOTH_Y = tuple(Y_LBACK - d for d in (1.80, 2.80, 3.80, 4.80))
CUBE_Y = Y_LBACK - 3.30            # WC cubicle front line
CUBE_U = (U_DIV + DIV_T / 2, 3.125, WIDTH)
# Locker room layout
LOCKER_CW, LOCKER_D = 0.33, 0.45  # 2-tier column width / carcass depth (front faces 0.47 m off the wall)
N_FRONT, FRONT_U0 = 6, 1.40       # front-wall run beside the entry
N_OUTER, OUTER_GAP = 14, 0.62     # outer-wall run starts 0.62 m behind the front wall (clear of the front run)
VANITY_Y = -9.72                  # powder vanity centre on the partition wall (y -8.62 .. -10.82)
BENCH_U, BENCH_Y = 2.26, (-8.70, -10.60)  # centre bench (aisles >= 1.2 m to the outer lockers and vanity stools)

SUITES = (
    dict(tag="Men", s=-1, door_x=10.95, accent=(0.18, 0.56, 0.96), urinals=True, first_locker=201,
         wood=(0.12, 0.072, 0.042), locker=(0.075, 0.080, 0.088)),
    dict(tag="Women", s=1, door_x=12.25, accent=(0.96, 0.32, 0.48), urinals=False, first_locker=301,
         wood=(0.52, 0.37, 0.23), locker=(0.66, 0.62, 0.56)),
)

# ------------------------------------------------------------------ materials


def _nodes(m):
    nt = m.node_tree
    return nt.nodes, nt.links, next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")


def _mix_rgb(N, blend):
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = blend
    ins = {s.identifier: s for s in mx.inputs}
    outs = {s.identifier: s for s in mx.outputs}
    return ins["Factor_Float"], ins["A_Color"], ins["B_Color"], outs["Result_Color"]


def _plane_coords(N, L, axes):
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    L.new(sep.outputs[axes[0]], comb.inputs["X"])
    if len(axes) > 1:
        L.new(sep.outputs[axes[1]], comb.inputs["Y"])
    return comb.outputs[0]


def _grid(N, L, vec, tile_w, tile_h, grout_w, c1, c2, grout):
    br = N.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.squash = 1.0
    L.new(vec, br.inputs["Vector"])
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = tile_w
    br.inputs["Row Height"].default_value = tile_h
    br.inputs["Mortar Size"].default_value = grout_w
    br.inputs["Mortar Smooth"].default_value = 0.3
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (*c1, 1)
    br.inputs["Color2"].default_value = (*c2, 1)
    br.inputs["Mortar"].default_value = (*grout, 1)
    return br


def _grout_bump(N, L, bsdf, fac, strength=0.35):
    bump = N.new("ShaderNodeBump")
    bump.invert = True
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.002
    L.new(fac, bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _tile_mat(name, color, grout, tile_w, tile_h, axes="XY", rough=0.45, grout_w=0.003, glow=0.0):
    """Plain grid tiles from world position (stacked Brick texture) with grout bump.
    glow: faint self-illumination standing in for bounce light (ceiling tiles above downlights)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, color, emit=glow, rough=rough)
    N, L, bsdf = _nodes(m)
    br = _grid(N, L, _plane_coords(N, L, axes), tile_w, tile_h, grout_w, color,
               [min(1.0, v * 1.06) for v in color], grout)
    L.new(br.outputs["Color"], bsdf.inputs["Base Color"])
    _grout_bump(N, L, bsdf, br.outputs["Fac"])
    return m


def _stone_mat(name, base, vein, grout, tile_w, tile_h, axes, rough=0.12, veins=1.0, vein_scale=0.9, grout_w=0.0025):
    """Polished stone / marble porcelain tile. Every tile gets its own vein pattern (random offset per tile),
    soft cloudy variation, thin veins, light grout lines and slight roughness variation."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, base, rough=rough)
    N, L, bsdf = _nodes(m)
    vec = _plane_coords(N, L, axes)
    snap = N.new("ShaderNodeVectorMath")
    snap.operation = "SNAP"
    snap.inputs[1].default_value = (tile_w, tile_h, 1.0)
    L.new(vec, snap.inputs[0])
    wn = N.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    L.new(snap.outputs["Vector"], wn.inputs["Vector"])
    off = N.new("ShaderNodeVectorMath")
    off.operation = "MULTIPLY_ADD"
    L.new(wn.outputs["Color"], off.inputs[0])
    off.inputs[1].default_value = (9.0, 9.0, 9.0)
    L.new(vec, off.inputs[2])
    wave = N.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.wave_profile = "SIN"
    wave.inputs["Scale"].default_value = vein_scale
    wave.inputs["Distortion"].default_value = 5.5
    wave.inputs["Detail"].default_value = 4.0
    wave.inputs["Detail Scale"].default_value = 1.8
    wave.inputs["Detail Roughness"].default_value = 0.55
    L.new(off.outputs["Vector"], wave.inputs["Vector"])
    vramp = N.new("ShaderNodeValToRGB")
    e0, e1 = vramp.color_ramp.elements
    vcol = [b + (v - b) * veins for b, v in zip(base, vein)]
    e0.position, e0.color = 0.955, (*base, 1)  # only the wave crests become veins: thin hairline veining
    e1.position, e1.color = 0.998, (*vcol, 1)
    L.new(wave.outputs["Fac"], vramp.inputs["Fac"])
    cloud = N.new("ShaderNodeTexNoise")
    cloud.inputs["Scale"].default_value = 2.2
    cloud.inputs["Detail"].default_value = 6.0
    L.new(off.outputs["Vector"], cloud.inputs["Vector"])
    cramp = N.new("ShaderNodeValToRGB")
    c0, c1 = cramp.color_ramp.elements
    c0.position, c0.color = 0.35, (0.93, 0.93, 0.93, 1)
    c1.position, c1.color = 0.70, (1.0, 1.0, 1.0, 1)
    L.new(cloud.outputs["Fac"], cramp.inputs["Fac"])
    f, a, b, res = _mix_rgb(N, "MULTIPLY")
    f.default_value = 1.0
    L.new(vramp.outputs["Color"], a)
    L.new(cramp.outputs["Color"], b)
    br = _grid(N, L, vec, tile_w, tile_h, grout_w, (1, 1, 1), (1, 1, 1), grout)
    f2, a2, b2, res2 = _mix_rgb(N, "MIX")
    L.new(br.outputs["Fac"], f2)
    L.new(res, a2)
    b2.default_value = (*grout, 1)
    L.new(res2, bsdf.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange")
    L.new(cloud.outputs["Fac"], rr.inputs["Value"])
    rr.inputs["To Min"].default_value = rough * 0.75
    rr.inputs["To Max"].default_value = rough * 1.6
    L.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
    _grout_bump(N, L, bsdf, br.outputs["Fac"], 0.25)
    return m


def _brushed_mat(name, color, rough=0.30):
    """Brushed stainless: vertically stretched noise drives a fine bump and roughness streaks."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, color, rough=rough, metal=1.0)
    N, L, bsdf = _nodes(m)
    geo = N.new("ShaderNodeNewGeometry")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (260.0, 260.0, 2.5)
    L.new(geo.outputs["Position"], mp.inputs["Vector"])
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 2.0
    L.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rr = N.new("ShaderNodeMapRange")
    L.new(nz.outputs["Fac"], rr.inputs["Value"])
    rr.inputs["To Min"].default_value = rough - 0.08
    rr.inputs["To Max"].default_value = rough + 0.08
    L.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.0006
    L.new(nz.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _fluted_mat(name):
    """Backlit green fluted (reeded) glass: 3 cm vertical ribs as bump, ribs glow brighter on their crests."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, (0.42, 0.66, 0.52), rough=0.10)
    N, L, bsdf = _nodes(m)
    wave = N.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.wave_profile = "SIN"
    wave.inputs["Scale"].default_value = 10.5  # period = 2*pi / (20 * scale) = 3 cm
    wave.inputs["Distortion"].default_value = 0.0
    L.new(_plane_coords(N, L, "Y"), wave.inputs["Vector"])  # restroom vanity glass sits on a YZ wall
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.004
    L.new(wave.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Emission Color"].default_value = (0.50, 0.95, 0.66, 1)
    rr = N.new("ShaderNodeMapRange")
    L.new(wave.outputs["Fac"], rr.inputs["Value"])
    rr.inputs["To Min"].default_value = 0.35
    rr.inputs["To Max"].default_value = 0.95
    L.new(rr.outputs["Result"], bsdf.inputs["Emission Strength"])
    try:
        bsdf.inputs["Coat Weight"].default_value = 0.6
    except KeyError:
        pass
    return m


def _glass(name, color, alpha, rough):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, color, rough=rough)
    _, _, bsdf = _nodes(m)
    bsdf.inputs["Alpha"].default_value = alpha
    for attr, val in (("use_transparent_shadow", True), ("surface_render_method", "BLENDED")):
        try:  # blended (not dithered) transparency: smooth frosted glass without sample grain
            setattr(m, attr, val)
        except (AttributeError, TypeError):
            pass
    return m


def _ceramic(name, color, rough):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, color, rough=rough)
    _, _, bsdf = _nodes(m)
    try:
        bsdf.inputs["Coat Weight"].default_value = 0.45
        bsdf.inputs["Coat Roughness"].default_value = 0.04
    except KeyError:
        pass
    return m


def _materials(spec):
    t = spec["tag"]
    marble = dict(base=(0.80, 0.80, 0.78), vein=(0.50, 0.51, 0.52), grout=(0.70, 0.70, 0.69))
    greige = dict(base=(0.56, 0.53, 0.48), vein=(0.47, 0.45, 0.41), grout=(0.47, 0.45, 0.42))
    return {
        "paint": W.mat("Suite_WarmPaint", (0.43, 0.40, 0.36), rough=0.82),
        "wood": W.mat(f"Suite_Wood_{t}", spec["wood"], rough=0.48),
        "locker": W.mat(f"Suite_LockerDoor_{t}", spec["locker"], rough=0.42, metal=0.08),
        "accent": W.shadeless(f"Suite_Accent_{t}", spec["accent"], strength=2.4),
        "carcass": W.mat("Suite_Carcass", (0.05, 0.052, 0.056), rough=0.55),
        "steel": W.mat("Suite_BlackSteel", (0.028, 0.029, 0.032), rough=0.42, metal=0.65),
        "chrome": W.mat("Suite_Chrome", (0.72, 0.73, 0.74), rough=0.12, metal=1.0),
        "brushed": _brushed_mat("Suite_BrushedSteel", (0.60, 0.61, 0.625), 0.30),
        "quartz": W.mat("Suite_Quartz", (0.80, 0.79, 0.77), rough=0.22),
        "solid": W.mat("Suite_SolidSurface", (0.86, 0.86, 0.84), rough=0.28),
        "ceramic": _ceramic("Suite_Porcelain", (0.88, 0.88, 0.86), 0.10),
        "ceiling": W.mat("Suite_Ceiling", (0.76, 0.76, 0.74), rough=0.92),
        "mirror": W.mat("Suite_Mirror", (0.93, 0.94, 0.95), rough=0.02, metal=1.0),
        "clear": _glass("Suite_ClearGlass", (0.70, 0.86, 0.82), 0.16, 0.02),
        "frost": _glass("Suite_FrostGlass", (0.78, 0.87, 0.85), 0.72, 0.42),
        "fluted": _fluted_mat("Suite_FlutedGlass"),
        "dark": W.mat("Suite_DarkSlot", (0.012, 0.012, 0.014), rough=0.7),
        "white": W.mat("Suite_TowelWhite", (0.84, 0.84, 0.82), rough=0.95),
        "shelf": W.mat("Suite_WhiteABS", (0.86, 0.86, 0.85), rough=0.30),
        "plate": W.mat("Suite_NumberPlate", (0.58, 0.60, 0.62), rough=0.30, metal=0.85),
        "teal": W.mat("Suite_TealBin", (0.02, 0.30, 0.32), rough=0.42),
        "liner": _glass("Suite_BinLiner", (0.86, 0.90, 0.88), 0.55, 0.30),
        "hose": W.mat("Suite_GreyHose", (0.30, 0.31, 0.32), rough=0.60),
        "amber": W.mat("Suite_AmberBottle", (0.42, 0.22, 0.05), rough=0.18),
        "label": W.mat("Suite_BottleLabel", (0.82, 0.78, 0.66), rough=0.70),
        "text": W.shadeless("Suite_SignText", (0.94, 0.95, 0.97), strength=1.4),
        "text_dark": W.mat("Suite_PlateText", (0.02, 0.02, 0.025), rough=0.5),
        "glow_warm": W.shadeless("Suite_GlowWarm", (1.0, 0.80, 0.56), strength=3.2),
        "glow_white": W.shadeless("Suite_GlowWhite", (1.0, 0.97, 0.92), strength=4.0),
        "glow_cool": W.shadeless("Suite_GlowCool", (0.88, 0.94, 1.0), strength=3.0),
        "glow_green": W.shadeless("Suite_GlowGreen", (0.45, 1.0, 0.62), strength=2.6),
        "ceramic_in": _ceramic("Suite_PorcelainInner", (0.74, 0.75, 0.74), 0.10),
        "led_red": W.shadeless("Suite_LockRed", (0.95, 0.06, 0.05), strength=2.5),
        "led_green": W.shadeless("Suite_LockGreen", (0.10, 0.90, 0.25), strength=2.5),
        "floor_locker": _tile_mat("Suite_LockerFloor", (0.32, 0.30, 0.275), (0.15, 0.145, 0.14), 0.60, 0.60, "XY", 0.35),
        "ceil_tile": _tile_mat("Suite_CeilingTile", (0.88, 0.88, 0.86), (0.62, 0.62, 0.61), 0.60, 0.60, "XY", 0.85, 0.004, 0.35),
        "grate": _tile_mat("Suite_DrainGrate", (0.55, 0.56, 0.57), (0.01, 0.01, 0.01), 0.016, 1.0, "XY", 0.25, 0.006),
        "marble_xz": _stone_mat("Suite_Marble_XZ", tile_w=0.60, tile_h=1.20, axes="XZ", rough=0.10, **marble),
        "marble_yz": _stone_mat("Suite_Marble_YZ", tile_w=0.60, tile_h=1.20, axes="YZ", rough=0.10, **marble),
        "floor_shower": _stone_mat("Suite_MarbleFloor", tile_w=0.30, tile_h=0.60, axes="XY", rough=0.22, vein_scale=1.4, **marble),
        "wc_xz": _stone_mat("Suite_Porcelain_XZ", tile_w=0.60, tile_h=1.20, axes="XZ", rough=0.16, veins=0.35, **greige),
        "wc_yz": _stone_mat("Suite_Porcelain_YZ", tile_w=0.60, tile_h=1.20, axes="YZ", rough=0.16, veins=0.35, **greige),
        "floor_wc": _stone_mat("Suite_PorcelainFloor", tile_w=0.60, tile_h=1.20, axes="XY", rough=0.14, veins=0.30,
                               base=(0.56, 0.53, 0.49), vein=(0.46, 0.44, 0.41), grout=(0.47, 0.45, 0.42)),
    }


# ------------------------------------------------------------------ small helpers


def _bevel(ob, radius, harden=False):
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width = radius
    bv.segments = 2
    bv.limit_method = "ANGLE"
    bv.harden_normals = harden
    return ob


def _lb(c, root, name, size, m, xyz, bevel=0.0, rot=(0, 0, 0)):
    """Box in a fixture's local frame (front = +Y, wall at y = 0)."""
    ob = W.box(name, size, m, c, xyz, rot, parent=root)
    if bevel:
        _bevel(ob, min(bevel, min(size) * 0.45))
    return ob


def _lc(c, root, name, r, h, m, xyz, rot=(0, 0, 0), seg=16, r2=None):
    ob = W.cyl(name, r, h, m, c, xyz, rot, seg=seg, r2=r2, parent=root)
    for p in ob.data.polygons:  # smooth the round sides (quads), keep the caps (n-gons) flat
        p.use_smooth = len(p.vertices) == 4
    return ob


def _stadium(c, root, name, w, h, depth, m, xyz, seg=20):
    """Pill-shaped slab (vertical stadium) in a fixture frame: back face at xyz, `depth` toward local +Y."""
    r, s = w / 2, max(h - w, 0.0) / 2
    pts = [(r * math.cos(math.pi * i / seg), s + r * math.sin(math.pi * i / seg)) for i in range(seg + 1)]
    pts += [(r * math.cos(math.pi + math.pi * i / seg), -s + r * math.sin(math.pi + math.pi * i / seg)) for i in range(seg + 1)]
    bm = bmesh.new()
    vb = [bm.verts.new((x, 0.0, z)) for x, z in pts]
    vf = [bm.verts.new((x, depth, z)) for x, z in pts]
    bm.faces.new(vf)
    bm.faces.new(list(reversed(vb)))
    n = len(pts)
    for i in range(n):
        bm.faces.new((vb[i], vb[(i + 1) % n], vf[(i + 1) % n], vf[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return W.mesh_obj(name, bm, m, c, xyz, parent=root)


def _torus(c, root, name, R, r, m, xyz, seg=36, rseg=10):
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        rings.append([bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
                      for b in (2 * math.pi * j / rseg for j in range(rseg))])
    for i in range(seg):
        for j in range(rseg):
            bm.faces.new((rings[i][j], rings[(i + 1) % seg][j], rings[(i + 1) % seg][(j + 1) % rseg], rings[i][(j + 1) % rseg]))
    ob = W.mesh_obj(name, bm, m, c, xyz, parent=root)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def _tube(c, root, name, points, radius, m):
    """Smooth NURBS tube through local points (shower hoses)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.resolution_u = 10
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for p, xyz in zip(sp.points, points):
        p.co = (*xyz, 1.0)
    sp.order_u = 3
    sp.use_endpoint_u = True
    cu.materials.append(m)
    ob = bpy.data.objects.new(name, cu)
    ob.parent = root
    c.objects.link(ob)
    return ob


def _label(c, root, name, body, xyz, size, m):
    """Flat text in a fixture frame, readable from local +Y."""
    data = bpy.data.curves.new(name, "FONT")
    data.body = body
    data.font = W.load_font(W.KFONT)
    data.size = size
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.materials.append(m)
    ob = bpy.data.objects.new(name, data)
    ob.location = xyz
    ob.rotation_euler = (math.pi / 2, 0, math.pi)
    ob.parent = root
    c.objects.link(ob)
    return ob


def _to_world(root, xyz):
    """Local fixture-frame point -> world (fixture roots are unparented empties rotated about Z only)."""
    yaw = root.rotation_euler.z
    x, y, z = xyz
    return (root.location.x + x * math.cos(yaw) - y * math.sin(yaw),
            root.location.y + x * math.sin(yaw) + y * math.cos(yaw), root.location.z + z)


def _mirror_probe(c, root, name, xyz, w, h):
    """Planar reflection probe over a mirror in a fixture frame (mirror faces local +Y), like the gym's MirrorProbe.
    Kept unparented in world space and ~1 cm proud of the glass: a parented probe hugging the glass reflected nothing."""
    try:
        lp = bpy.data.lightprobes.new(name, "PLANE")
    except Exception:
        return None
    ob = bpy.data.objects.new(name, lp)
    c.objects.link(ob)
    ob.location = _to_world(root, (xyz[0], xyz[1] + 0.01, xyz[2]))
    ob.rotation_euler = (math.radians(90), 0, root.rotation_euler.z + math.pi)
    ob.scale = (w / 2, h / 2, 1.0)
    return ob


def _room_probe(S, name, u0, u1, y0, y1):
    """Box sphere-probe filling one room so brushed steel and chrome reflect the room instead of going black."""
    try:
        lp = bpy.data.lightprobes.new(f"{S.tag} {name}", "SPHERE")
    except Exception:
        return None
    ob = bpy.data.objects.new(f"{S.tag} {name}", lp)
    S.c.objects.link(ob)
    ob.location = (S.x((u0 + u1) / 2), (y0 + y1) / 2, CEIL / 2)
    ob.scale = (abs(u1 - u0) / 2, abs(y1 - y0) / 2, CEIL / 2)
    for attr, val in (("influence_type", "BOX"), ("influence_distance", 1.0), ("falloff", 0.1),
                      ("use_custom_parallax", True), ("parallax_type", "BOX"), ("parallax_distance", 1.0)):
        try:
            setattr(lp, attr, val)
        except (AttributeError, TypeError):
            pass
    return ob


def _light(c, name, kind, xyz, energy, color, shadow=True, rot=(0, 0, 0), **kw):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    for k, v in kw.items():
        setattr(ld, k, v)
    try:
        ld.use_shadow = shadow
        ld.specular_factor = 0.7
        ld.shadow_maximum_resolution = 0.008  # coarse shadow pages: keeps EEVEE's shadow pool from overflowing
    except AttributeError:
        pass
    ob = bpy.data.objects.new(name, ld)
    ob.location = xyz
    ob.rotation_euler = [math.radians(a) for a in rot]
    c.objects.link(ob)
    return ob


def _area_light(c, name, xyz, size, size_y, energy, color, shadow=True, rot=(0, 0, 0)):
    return _light(c, name, "AREA", xyz, energy, color, shadow, rot, shape="RECTANGLE", size=size, size_y=size_y)


def _spot(c, name, xyz, energy, color, shadow=True):
    """Recessed downlight: narrow-ish cone so it paints the soft scallops seen on tiled shower walls."""
    return _light(c, name, "SPOT", xyz, energy, color, shadow, spot_size=math.radians(105), spot_blend=0.75,
                  shadow_soft_size=0.04)


class _Suite:
    """One gender's suite. u runs from the partition face (u = 0) to the outer wall (u = WIDTH)."""

    def __init__(self, c, spec):
        self.c, self.spec, self.tag, self.s = c, spec, spec["tag"], spec["s"]
        self.x0 = PART_X + self.s * PART_T / 2
        self.door_u = abs(spec["door_x"] - self.x0)
        self.M = _materials(spec)

    def x(self, u):
        return self.x0 + self.s * u

    def box(self, name, u0, u1, y0, y1, z0, z1, m, bevel=0.0):
        size = (abs(u1 - u0), abs(y1 - y0), abs(z1 - z0))
        loc = (self.x((u0 + u1) / 2), (y0 + y1) / 2, (z0 + z1) / 2)
        ob = W.box(f"{self.tag} {name}", size, m, self.c, loc)
        if bevel:
            _bevel(ob, min(bevel, min(size) * 0.45))
        return ob

    def frame(self, name, u, y, face, z=0.0):
        """Empty whose local +Y points `face` ('+u', '-u', '+y', '-y'); fixtures are built against its y = 0 plane."""
        rot = {"+u": -self.s * 90, "-u": self.s * 90, "+y": 0, "-y": 180}[face]
        e = W.empty(f"{self.tag} {name}", self.c, (self.x(u), y, z))
        e.rotation_euler.z = math.radians(rot)
        return e

    def hinge(self, name, u, y, d, open_deg, along="u"):
        """Door hinge empty. along='u': closed leaf runs from u toward u + d*w; it swings toward -y.
        along='y': closed leaf runs toward -y, swings toward +u."""
        if along == "u":
            base = 0 if self.s * d > 0 else 180
            rot = base - self.s * d * open_deg
        else:
            rot = -90 + self.s * open_deg
        e = W.empty(f"{self.tag} {name}", self.c, (self.x(u), y, 0))
        e.rotation_euler.z = math.radians(rot)
        return e

    def wall_u(self, name, y_north, y_south, openings, m_north, m_south):
        """Wall across the suite width with openings [(u0, u1, z_top)] and a finish per half.
        A finish is one material or [(u_end, material), ...] to change it along u."""
        ym = (y_north + y_south) / 2
        cuts = sorted(openings)
        solid, u = [], -PART_T / 2
        for u0, u1, _ in cuts:
            solid.append((u, u0))
            u = u1
        solid.append((u, WIDTH + SHELL_T))
        pieces = [(a, b, 0.0, CEIL) for a, b in solid] + [(u0, u1, zt, CEIL) for u0, u1, zt in cuts]
        for half, (ya, yb, fin) in enumerate(((y_north, ym, m_north), (ym, y_south, m_south))):
            fin = fin if isinstance(fin, list) else [(WIDTH + SHELL_T, fin)]
            for i, (a, b, z0, z1) in enumerate(pieces):
                lo = a
                for j, (lim, m) in enumerate(fin):
                    hi = min(b, lim)
                    if hi > lo + 1e-6:
                        self.box(f"{name} {half}{i}{j}", lo, hi, ya, yb, z0, z1, m)
                    lo = max(lo, hi)

    def wall_y(self, name, u0, u1, y0, y1, m):
        return self.box(name, u0, u1, y0, y1, 0, CEIL, m)


# ------------------------------------------------------------------ fixtures (local frame: wall at y = 0, front = +Y)


def _locker_run(S, root, n, first_no):
    c, M = S.c, S.M
    cw, d, H, plinth = LOCKER_CW, LOCKER_D, 1.90, 0.10
    L = n * cw
    _lb(c, root, "Locker carcass", (L, d, H), M["carcass"], (L / 2, d / 2, plinth + H / 2))
    _lb(c, root, "Locker plinth", (L, d - 0.06, plinth), M["steel"], (L / 2, (d - 0.06) / 2, plinth / 2))
    _lb(c, root, "Locker crown", (L + 0.02, d + 0.03, 0.05), M["wood"], (L / 2, (d + 0.03) / 2, plinth + H + 0.025), 0.006)
    _lb(c, root, "Locker accent strip", (L, 0.006, 0.012), M["accent"], (L / 2, d + 0.034, plinth + H + 0.01))
    th = H / 2
    no = first_no
    for i in range(n):
        cx = (i + 0.5) * cw
        for t in (1, 0):  # upper first so numbers read top-to-bottom
            zc = plinth + th * (t + 0.5)
            _lb(c, root, "Locker door", (cw - 0.014, 0.020, th - 0.014), M["locker"], (cx, d + 0.010, zc), 0.004)
            _lb(c, root, "Locker pull", (0.016, 0.024, 0.16), M["chrome"], (cx + cw * 0.33, d + 0.032, zc), 0.004)
            _lc(c, root, "Locker key lock", 0.011, 0.012, M["chrome"], (cx + cw * 0.33, d + 0.026, zc + 0.13), (90, 0, 0), seg=12)
            _lb(c, root, "Locker number plate", (0.085, 0.004, 0.046), M["plate"], (cx - 0.05, d + 0.022, zc + th * 0.33), 0.002)
            _label(c, root, f"{S.tag} locker no {no}", str(no), (cx - 0.05, d + 0.0245, zc + th * 0.33), 0.032, M["text_dark"])
            for vz in (-0.012, 0.012):  # vent slots
                _lb(c, root, "Locker vent", (0.18, 0.004, 0.006), M["dark"], (cx - 0.02, d + 0.021, zc - th * 0.32 + vz))
            no += 1
    return no


def _powder_vanity(S, root, length, sinks, powder):
    """Locker-room vanity: floating wood cabinet, quartz top, vessel basins, backlit mirror, holstered dryers, stools."""
    c, M = S.c, S.M
    depth = 0.55
    _lb(c, root, "Vanity cabinet", (length, depth - 0.03, 0.46), M["wood"], (0, (depth - 0.03) / 2, 0.55), 0.008)
    _lb(c, root, "Vanity top", (length + 0.03, depth, 0.035), M["quartz"], (0, depth / 2, 0.80), 0.004)
    _lb(c, root, "Vanity toe light", (length - 0.1, 0.01, 0.01), M["glow_warm"], (0, depth - 0.08, 0.315))
    _lb(c, root, "Vanity mirror glow", (length - 0.02, 0.006, 0.98), M["glow_warm"], (0, 0.004, 1.52))
    _lb(c, root, "Vanity mirror", (length - 0.08, 0.012, 0.92), M["mirror"], (0, 0.014, 1.52))
    _mirror_probe(c, root, f"{S.tag} locker vanity probe", (0, 0.021, 1.52), length - 0.08, 0.92)
    for sx in sinks:
        _lc(c, root, "Vessel basin", 0.19, 0.12, M["ceramic"], (sx, 0.30, 0.878), seg=32, r2=0.16)
        _lc(c, root, "Vessel basin inside", 0.165, 0.004, M["ceramic_in"], (sx, 0.30, 0.937), seg=32)
        _lc(c, root, "Faucet riser", 0.013, 0.30, M["chrome"], (sx, 0.07, 0.97), seg=12)
        _lc(c, root, "Faucet spout", 0.011, 0.16, M["chrome"], (sx, 0.15, 1.115), (90, 0, 0), seg=12)
        _lb(c, root, "Faucet lever", (0.012, 0.07, 0.012), M["chrome"], (sx + 0.03, 0.06, 1.08), 0.004)
        _lb(c, root, "Soap dispenser", (0.05, 0.05, 0.12), M["chrome"], (sx + 0.28, 0.08, 0.88), 0.01)
    for px in powder:
        _lb(c, root, "Dryer holster", (0.05, 0.11, 0.025), M["steel"], (px, 0.055, 0.95), 0.006)
        _lc(c, root, "Dryer holster ring", 0.045, 0.03, M["steel"], (px, 0.12, 0.95), seg=20)
        _lc(c, root, "Hair dryer handle", 0.02, 0.16, M["carcass"], (px, 0.12, 0.99), seg=12)
        _lc(c, root, "Hair dryer body", 0.045, 0.19, M["carcass"], (px, 0.15, 1.08), (90, 0, 0), seg=20)
        _lc(c, root, "Hair dryer nozzle", 0.03, 0.05, M["steel"], (px, 0.265, 1.08), (90, 0, 0), seg=16, r2=0.024)
        _lc(c, root, "Hair dryer cord", 0.004, 0.16, M["dark"], (px, 0.12, 0.89), seg=6)
        _lc(c, root, "Stool base", 0.17, 0.02, M["chrome"], (px, 0.70, 0.01), seg=24)
        _lc(c, root, "Stool post", 0.022, 0.56, M["chrome"], (px, 0.70, 0.30), seg=12)
        _lc(c, root, "Stool cushion", 0.17, 0.07, M["carcass"], (px, 0.70, 0.615), seg=24)
    if powder:
        _lb(c, root, "Tissue box", (0.22, 0.11, 0.08), M["white"], (powder[0] + 0.24, 0.20, 0.858), 0.01)


def _sign(S, root, main, sub, z, width=0.60):
    c, M = S.c, S.M
    _lb(c, root, "Sign plaque", (width, 0.022, 0.15), M["carcass"], (0, 0.011, z), 0.005)
    _lb(c, root, "Sign accent", (width - 0.04, 0.005, 0.012), M["accent"], (0, 0.024, z + 0.058))
    _label(c, root, f"{S.tag} sign {main}", main, (0, 0.0235, z + 0.012), 0.050, M["text"])
    _label(c, root, f"{S.tag} sign {main} sub", sub, (0, 0.0235, z - 0.042), 0.032, M["text"])


def _shower_column(S, root, idx):
    """Exposed thermostatic rain column on a booth wall: white shelf-mixer with knobs and bottles, riser,
    round rain head, slider with hand shower and a looping hose."""
    c, M = S.c, S.M
    rx = -0.10  # riser x
    # Thermostatic shelf mixer (white body, chrome knobs, glass-rail on top) + bottles
    _lb(c, root, "Shelf mixer body", (0.52, 0.12, 0.075), M["shelf"], (0.02, 0.06, 1.05), 0.012)
    _lb(c, root, "Shelf mixer rail", (0.48, 0.006, 0.035), M["chrome"], (0.02, 0.118, 1.105), 0.002)
    for kx in (-0.06, 0.10):
        _lc(c, root, "Mixer knob", 0.024, 0.035, M["chrome"], (kx, 0.135, 1.05), (90, 0, 0), seg=20)
        _lc(c, root, "Mixer knob cap", 0.012, 0.012, M["chrome"], (kx, 0.156, 1.05), (90, 0, 0), seg=12)
    for i, (bx, h, mat) in enumerate(((-0.17, 0.17, "amber"), (-0.09, 0.19, "amber"), (0.0, 0.12, "shelf"), (0.09, 0.17, "amber"))):
        if idx == 2 and i == 3:
            continue  # lived-in: one booth is missing a bottle
        r = 0.026 if mat == "amber" else 0.018
        _lc(c, root, "Bottle", r, h, M[mat], (bx, 0.055, 1.0875 + h / 2), seg=16)
        _lc(c, root, "Bottle label", r + 0.0015, h * 0.45, M["label"], (bx, 0.055, 1.0875 + h * 0.42), seg=16)
        if mat == "amber":
            _lc(c, root, "Bottle pump", 0.008, 0.05, M["shelf"], (bx, 0.055, 1.0875 + h + 0.025), seg=10)
            _lb(c, root, "Bottle pump nozzle", (0.012, 0.04, 0.012), M["shelf"], (bx, 0.07, 1.0875 + h + 0.045))
    # Riser, elbow, arm and round rain head
    _lc(c, root, "Riser", 0.012, 1.02, M["chrome"], (rx, 0.055, 1.60), seg=14)
    _lc(c, root, "Riser wall bracket", 0.016, 0.055, M["chrome"], (rx, 0.027, 1.95), (90, 0, 0), seg=12)
    _lc(c, root, "Rain arm", 0.011, 0.32, M["chrome"], (rx, 0.21, 2.12), (78, 0, 0), seg=12)
    _lc(c, root, "Rain head", 0.12, 0.014, M["chrome"], (rx, 0.37, 2.15), (-6, 0, 0), seg=40)
    _lc(c, root, "Rain head face", 0.108, 0.002, M["dark"], (rx, 0.37, 2.142), (-6, 0, 0), seg=40)
    # Slider + hand shower
    _lb(c, root, "Slider", (0.04, 0.05, 0.05), M["chrome"], (rx, 0.075, 1.55), 0.008)
    _lc(c, root, "Hand shower grip", 0.016, 0.21, M["chrome"], (rx + 0.015, 0.10, 1.60), (-18, 12, 0), seg=14)
    _lc(c, root, "Hand shower head", 0.046, 0.03, M["chrome"], (rx + 0.03, 0.135, 1.71), (62, 0, 0), seg=24)
    hose = [(rx + 0.008, 0.10, 1.49), (rx + 0.03, 0.12, 1.20), (0.20, 0.13, 0.62), (0.26, 0.11, 0.80), (0.23, 0.07, 1.00)]
    _tube(c, root, f"{S.tag} shower hose {idx}", hose, 0.0065, M["chrome"])


def _restroom_vanity(S, root, length, sinks):
    """Restroom vanity from the reference photo: backlit green fluted glass wall, white solid-surface floating
    counter, oval vessel basins with tall faucets, LED-haloed pill mirrors, exposed chrome traps."""
    c, M = S.c, S.M
    depth, top = 0.52, 0.86
    gh = 2.62 - top
    _lb(c, root, "Fluted glass backlight", (length + 0.04, 0.008, gh + 0.03), M["glow_green"], (0, 0.004, top + gh / 2))
    _lb(c, root, "Fluted glass panel", (length, 0.02, gh), M["fluted"], (0, 0.018, top + gh / 2))
    _lb(c, root, "Fluted glass cap", (length + 0.02, 0.035, 0.018), M["brushed"], (0, 0.018, top + gh + 0.009), 0.003)
    _lb(c, root, "Counter slab", (length + 0.02, depth, 0.05), M["solid"], (0, depth / 2, top - 0.025), 0.008)
    _lb(c, root, "Counter apron", (length + 0.02, 0.022, 0.12), M["solid"], (0, depth - 0.011, top - 0.08), 0.006)
    for i, sx in enumerate(sinks):
        _stadium(c, root, f"{S.tag} pill mirror halo {i}", 0.45, 0.82, 0.006, M["glow_white"], (sx, 0.028, top + 0.63))
        _stadium(c, root, f"{S.tag} pill mirror {i}", 0.42, 0.79, 0.012, M["mirror"], (sx, 0.034, top + 0.63))
        body = _lc(c, root, "Oval vessel basin", 0.17, 0.13, M["ceramic"], (sx, 0.29, top + 0.065), seg=48, r2=0.16)
        body.scale.x = 1.35
        cut = _lc(c, root, f"{S.tag} basin cutter {i}", 0.148, 0.14, M["dark"], (sx, 0.29, top + 0.092), seg=48, r2=0.152)
        cut.scale.x = 1.35
        cut.hide_render = cut.hide_viewport = True
        bo = body.modifiers.new("Bowl", "BOOLEAN")
        bo.operation = "DIFFERENCE"
        bo.object = cut
        _bevel(body, 0.006, harden=True)
        _lc(c, root, "Basin drain", 0.028, 0.004, M["chrome"], (sx, 0.29, top + 0.024), seg=20)
        # Tall single-lever faucet with curved spout
        _lc(c, root, "Faucet base", 0.026, 0.02, M["chrome"], (sx, 0.075, top + 0.01), seg=20)
        _lc(c, root, "Faucet body", 0.015, 0.30, M["chrome"], (sx, 0.075, top + 0.17), seg=16)
        _lc(c, root, "Faucet spout", 0.012, 0.15, M["chrome"], (sx, 0.14, top + 0.315), (80, 0, 0), seg=14)
        _lc(c, root, "Faucet tip", 0.012, 0.045, M["chrome"], (sx, 0.212, top + 0.30), (20, 0, 0), seg=14)
        _lb(c, root, "Faucet lever", (0.012, 0.012, 0.075), M["chrome"], (sx + 0.03, 0.075, top + 0.29), 0.004, rot=(0, 25, 0))
        # Exposed chrome trap + angle valves under the floating counter
        _lc(c, root, "Drain tail", 0.017, 0.26, M["chrome"], (sx, 0.29, top - 0.18), seg=14)
        _lc(c, root, "Trap arm", 0.017, 0.25, M["chrome"], (sx, 0.165, top - 0.31), (90, 0, 0), seg=14)
        _lc(c, root, "Trap escutcheon", 0.036, 0.012, M["chrome"], (sx, 0.006, top - 0.31), (90, 0, 0), seg=20)
        for vx in (-0.11, 0.11):
            _lc(c, root, "Angle valve", 0.014, 0.05, M["chrome"], (sx + vx, 0.025, top - 0.26), (90, 0, 0), seg=12)
            _lc(c, root, "Braided hose", 0.005, 0.18, M["brushed"], (sx + vx * 0.6, 0.06, top - 0.15), (0, -vx * 120, 0), seg=8)
    _mirror_probe(c, root, f"{S.tag} restroom pill probe", (0, 0.046, top + 0.63), length, 0.80)
    # Wall soap dispenser between the mirrors
    _lb(c, root, "Soap dispenser body", (0.10, 0.07, 0.17), M["shelf"], (0, 0.063, top + 0.52), 0.015)
    _lb(c, root, "Soap dispenser push", (0.06, 0.006, 0.05), M["chrome"], (0, 0.099, top + 0.47), 0.003)
    _lb(c, root, "Soap dispenser window", (0.04, 0.004, 0.03), M["dark"], (0, 0.098, top + 0.56), 0.002)
    # Green spill from the backlit glass onto the counter and floor
    wx = _to_world(root, (0, 0.12, top + gh / 2))
    _area_light(c, f"{S.tag} Fluted glass spill", wx, length, gh, 30, (0.55, 1.0, 0.70), shadow=False,
                rot=(90, 0, math.degrees(root.rotation_euler.z)))


def _toilet(S, root, half_w, sanitary_bin):
    """Wall-hung WC on a concealed cistern (flush plate), facing local +Y. half_w: half the cubicle width."""
    c, M = S.c, S.M
    _lb(c, root, "Flush plate", (0.24, 0.010, 0.16), M["brushed"], (0, 0.005, 1.02), 0.004)
    _lb(c, root, "Flush button big", (0.10, 0.006, 0.12), M["chrome"], (-0.05, 0.011, 1.02), 0.004)
    _lb(c, root, "Flush button small", (0.06, 0.006, 0.12), M["chrome"], (0.06, 0.011, 1.02), 0.004)
    _lb(c, root, "WC back", (0.30, 0.14, 0.20), M["ceramic"], (0, 0.07, 0.33), 0.03)
    bowl = _lc(c, root, "WC bowl", 0.18, 0.17, M["ceramic"], (0, 0.31, 0.315), seg=36, r2=0.165)
    bowl.scale.y = 1.42
    seat = _lc(c, root, "WC seat lid", 0.182, 0.035, M["ceramic"], (0, 0.31, 0.418), seg=36)
    seat.scale.y = 1.42
    _bevel(seat, 0.012, harden=True)
    _lb(c, root, "Paper holder", (0.03, 0.15, 0.03), M["chrome"], (half_w - 0.03, 0.55, 0.72), 0.006)
    _lc(c, root, "Paper roll", 0.055, 0.11, M["white"], (half_w - 0.075, 0.55, 0.69), (90, 0, 0), seg=20)
    _lb(c, root, "Coat hook", (0.02, 0.06, 0.02), M["chrome"], (-half_w + 0.02, 0.50, 1.60), 0.006)
    if sanitary_bin:
        _lb(c, root, "Sanitary bin", (0.18, 0.28, 0.30), M["brushed"], (-half_w + 0.12, 0.30, 0.15), 0.02)


def _urinal(S, root, idx):
    """Sensor-integrated wall-hung urinal (real-product model in urinal_model.py)."""
    import urinal_model
    urinal_model.urinal(S, root, idx)


def _steel_unit(S, root):
    """Recessed-look brushed stainless towel dispenser / hand dryer panel."""
    c, M = S.c, S.M
    _lb(c, root, "Steel unit body", (0.40, 0.035, 0.82), M["brushed"], (0, 0.0175, 1.24), 0.012)
    _lb(c, root, "Steel unit towel slot", (0.26, 0.006, 0.022), M["dark"], (0, 0.036, 1.55), 0.003)
    _lb(c, root, "Paper towel tip", (0.12, 0.012, 0.05), M["white"], (0, 0.038, 1.525))
    _lb(c, root, "Steel unit dryer outlet", (0.22, 0.006, 0.045), M["dark"], (0, 0.036, 0.92), 0.004)
    _lb(c, root, "Steel unit sensor", (0.035, 0.004, 0.016), M["dark"], (0, 0.036, 0.99), 0.002)
    _lc(c, root, "Steel unit lock", 0.008, 0.006, M["chrome"], (0.15, 0.037, 1.60), (90, 0, 0), seg=12)


def _trash_bin(S, root):
    """Teal swing bin with a milky plastic liner folded over the rim."""
    c, M = S.c, S.M
    _lc(c, root, "Teal bin body", 0.150, 0.56, M["teal"], (0, 0, 0.28), seg=32, r2=0.172)
    _lc(c, root, "Teal bin rim", 0.176, 0.022, M["teal"], (0, 0, 0.552), seg=32)
    _lc(c, root, "Bin liner fold", 0.181, 0.11, M["liner"], (0, 0, 0.515), seg=32, r2=0.178)
    _lc(c, root, "Bin liner puff", 0.172, 0.05, M["liner"], (0, 0, 0.585), seg=32, r2=0.15)
    _lc(c, root, "Bin liner inside", 0.15, 0.005, M["liner"], (0, 0, 0.58), seg=32)


# ------------------------------------------------------------------ suite assembly


def _shell(S):
    M = S.M
    t = SHELL_T
    yb = Y_LBACK - WALL_T / 2
    S.box("Floor locker", -PART_T / 2, WIDTH + t, Y_FRONT, Y_LBACK, -0.06, 0.0, M["floor_locker"])
    S.box("Floor shower", -PART_T / 2, U_DIV, Y_LBACK, Y_BACK - t, -0.06, 0.0, M["floor_shower"])
    S.box("Floor restroom", U_DIV, WIDTH + t, Y_LBACK, Y_BACK - t, -0.06, 0.0, M["floor_wc"])
    S.wall_y("Partition locker", -PART_T / 2, 0, Y_FRONT, Y_LBACK, M["wood"])
    S.wall_y("Partition shower", -PART_T / 2, 0, Y_LBACK, Y_BACK, M["marble_yz"])
    S.wall_y("Outer wall locker", WIDTH, WIDTH + t, Y_FRONT, Y_LBACK, M["paint"])
    S.wall_y("Outer wall restroom", WIDTH, WIDTH + t, Y_LBACK, Y_BACK, M["wc_yz"])
    S.wall_y("Divider wall shower side", U_DIV - DIV_T / 2, U_DIV, yb, Y_BACK, M["marble_yz"])
    S.wall_y("Divider wall restroom side", U_DIV, U_DIV + DIV_T / 2, yb, Y_BACK, M["wc_yz"])
    S.box("Back wall shower", -PART_T / 2, U_DIV, Y_BACK, Y_BACK - t, 0, CEIL, M["marble_xz"])
    S.box("Back wall restroom", U_DIV, WIDTH + t, Y_BACK, Y_BACK - t, 0, CEIL, M["wc_xz"])
    # Front liner on the back face of the gym wall, with the entrance opening
    du, hw = S.door_u, ENTRY_W / 2
    S.box("Front liner a", 0, du - hw, Y_FRONT, Y_FRONT - 0.02, 0, CEIL, M["paint"])
    S.box("Front liner b", du + hw, WIDTH, Y_FRONT, Y_FRONT - 0.02, 0, CEIL, M["paint"])
    S.box("Front liner header", du - hw, du + hw, Y_FRONT, Y_FRONT - 0.02, ENTRY_H, CEIL, M["paint"])
    for side in (-1, 1):
        S.box("Entry casing", du + side * (hw + 0.035), du + side * (hw - 0.005), Y_FRONT - 0.02, Y_FRONT - 0.045,
              0, ENTRY_H + 0.04, M["steel"], 0.004)
    S.box("Entry casing head", du - hw - 0.075, du + hw + 0.075, Y_FRONT - 0.02, Y_FRONT - 0.045,
          ENTRY_H, ENTRY_H + 0.07, M["steel"], 0.004)
    S.box("Entry reveal floor", du - hw, du + hw, Y_FRONT + 0.20, Y_FRONT, -0.05, 0.004, M["floor_locker"])
    S.box("Entry threshold", du - hw, du + hw, Y_FRONT + 0.06, Y_FRONT - 0.04, 0, 0.012, M["chrome"], 0.003)
    # Locker back wall: open shower doorway + restroom door; marble / porcelain on the far side
    S.wall_u("Locker back wall", Y_LBACK + WALL_T / 2, yb, [SHOWER_OPEN, WC_DOOR], M["paint"],
             [(U_DIV, M["marble_xz"]), (WIDTH + t, M["wc_xz"])])
    S.box("SuiteCeiling slab", -PART_T / 2, WIDTH + t, Y_FRONT, Y_BACK - t, CEIL, CEIL + 0.08, M["ceiling"])


def _locker_room(S):
    M, c = S.M, S.c
    sb, z0 = 0.32, 2.82
    yw = Y_LBACK + WALL_T / 2
    for name, u0, u1, y0, y1 in (
        ("front", 0, WIDTH, Y_FRONT, Y_FRONT - sb), ("back", 0, WIDTH, yw + sb, yw),
        ("part", 0, sb, Y_FRONT - sb, yw + sb), ("outer", WIDTH - sb, WIDTH, Y_FRONT - sb, yw + sb),
    ):
        S.box(f"SuiteCeiling soffit {name}", u0, u1, y0, y1, z0, CEIL, M["ceiling"])
    yi0, yi1 = Y_FRONT - sb, yw + sb
    S.box("SuiteCeiling cove f", sb, WIDTH - sb, yi0 - 0.005, yi0 - 0.02, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    S.box("SuiteCeiling cove b", sb, WIDTH - sb, yi1 + 0.02, yi1 + 0.005, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    S.box("SuiteCeiling cove p", sb + 0.005, sb + 0.02, yi0, yi1, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    S.box("SuiteCeiling cove o", WIDTH - sb - 0.02, WIDTH - sb - 0.005, yi0, yi1, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    for u in (sb / 2, WIDTH - sb / 2):
        for y in (-7.9, -9.6, -11.3):
            W.cyl(f"{S.tag} SuiteCeiling downlight", 0.045, 0.006, M["glow_warm"], c, (S.x(u), y, z0 - 0.003), seg=16)

    # Two-tier lockers: a long run on the outer wall, a run on the front wall beside the entry
    n = S.spec["first_locker"]
    run_len = N_OUTER * LOCKER_CW
    y_start = Y_FRONT - OUTER_GAP - run_len if S.s > 0 else Y_FRONT - OUTER_GAP
    n = _locker_run(S, S.frame("Lockers outer wall", WIDTH, y_start, "-u"), N_OUTER, n)
    x_hi = max(S.x(FRONT_U0), S.x(FRONT_U0 + N_FRONT * LOCKER_CW))
    root = W.empty(f"{S.tag} Lockers front wall", c, (x_hi, Y_FRONT - 0.02, 0))
    root.rotation_euler.z = math.pi
    _locker_run(S, root, N_FRONT, n)

    # Centre bench (detail_gym_lockers hides it and puts its padded bench on the same spot)
    bu, by, bl = BENCH_U, sum(BENCH_Y) / 2, abs(BENCH_Y[1] - BENCH_Y[0]) / 2
    S.box("Bench top", bu - 0.18, bu + 0.18, by + bl, by - bl, 0.425, 0.47, M["wood"], 0.01)
    for ly in (by + bl - 0.20, by - bl + 0.20):
        S.box("Bench leg", bu - 0.19, bu + 0.19, ly + 0.02, ly - 0.02, 0.0, 0.425, M["steel"], 0.004)
        S.box("Bench foot", bu - 0.19, bu + 0.19, ly + 0.03, ly - 0.03, 0.0, 0.02, M["steel"], 0.004)
    S.box("Gym bag on bench", bu - 0.15, bu + 0.12, by + 0.55, by + 0.12, 0.47, 0.70, M["carcass"], 0.06)
    S.box("Folded towel bench", bu - 0.12, bu + 0.12, by - 0.30, by - 0.62, 0.47, 0.52, M["white"], 0.02)

    _powder_vanity(S, S.frame("Vanity", 0, VANITY_Y, "+u"), 2.2, sinks=(-0.75, -0.25), powder=(0.35, 0.85))

    # Back wall, left to right: towel return | open shower doorway | full mirror | restroom door
    root = S.frame("Towel return", 0.35, yw, "+y")
    _lb(c, root, "Towel bin body", (0.50, 0.42, 0.80), M["wood"], (0, 0.21, 0.40), 0.01)
    _lb(c, root, "Towel bin slot", (0.38, 0.30, 0.012), M["dark"], (0, 0.22, 0.805))
    _lb(c, root, "Towel bin label", (0.36, 0.005, 0.10), M["carcass"], (0, 0.423, 0.60), 0.003)
    _label(c, root, f"{S.tag} towel label", "USED TOWEL · 사용한 수건", (0, 0.4265, 0.60), 0.026, M["text"])
    _lb(c, root, "Towel in bin", (0.30, 0.20, 0.06), M["white"], (0.02, 0.22, 0.83), 0.02)
    root = S.frame("Full mirror", 2.12, yw, "+y")
    _lb(c, root, "Full mirror frame", (0.62, 0.03, 1.80), M["wood"], (0, 0.015, 1.10), 0.006)
    _lb(c, root, "Full mirror glass", (0.54, 0.012, 1.72), M["mirror"], (0, 0.034, 1.10))
    _mirror_probe(c, root, f"{S.tag} full mirror probe", (0, 0.041, 1.10), 0.54, 1.72)
    _sign(S, S.frame("Shower sign", (SHOWER_OPEN[0] + SHOWER_OPEN[1]) / 2, yw, "+y"), "SHOWER", "샤워실", 2.36)
    _sign(S, S.frame("Restroom sign", (WC_DOOR[0] + WC_DOOR[1]) / 2, yw, "+y"), "RESTROOM", "화장실", 2.36)

    _area_light(c, f"{S.tag} Locker light", (S.x(WIDTH / 2), (Y_FRONT + Y_LBACK) / 2, CEIL - 0.05),
                WIDTH - 0.7, abs(Y_LBACK - Y_FRONT) - 0.7, 630, (1.0, 0.86, 0.70))


def _shower_room(S):
    """Marble shower (u 0 .. 2.00): open doorway, dry aisle, 3 frameless glass booths on the partition wall."""
    M, c = S.M, S.c
    u_in = U_DIV - DIV_T / 2
    y_in = Y_LBACK - WALL_T / 2
    u0, u1, top = SHOWER_OPEN
    # Doorway: brushed steel edge trims and a linear drain just inside
    for u in (u0, u1):
        S.box("Shower doorway trim", u - 0.012, u + 0.012, Y_LBACK + WALL_T / 2 + 0.005, y_in - 0.005, 0, top, M["brushed"], 0.003)
    S.box("Shower doorway head trim", u0 - 0.012, u1 + 0.012, Y_LBACK + WALL_T / 2 + 0.005, y_in - 0.005, top - 0.012, top,
          M["brushed"], 0.003)
    S.box("Entrance linear drain", u0, u1, y_in - 0.15, y_in - 0.25, -0.004, 0.002, M["grate"])

    for i, (ya, yb) in enumerate(zip(BOOTH_Y[:-1], BOOTH_Y[1:])):
        yc = (ya + yb) / 2
        # Booth side glass (frosted below, clear on top) — the last booth closes on the back wall
        S.box(f"Booth side frosted {i}", 0.005, BOOTH_D, ya + 0.005, ya - 0.005, 0.05, 1.75, M["frost"])
        S.box(f"Booth side clear {i}", 0.005, BOOTH_D, ya + 0.005, ya - 0.005, 1.75, 2.10, M["clear"])
        for z in (0.40, 1.85):
            S.box(f"Glass wall clamp {i}", 0.0, 0.05, ya + 0.02, ya - 0.02, z - 0.03, z + 0.03, M["chrome"], 0.004)
        S.box(f"Glass floor pin {i}", BOOTH_D - 0.04, BOOTH_D - 0.01, ya + 0.015, ya - 0.015, 0, 0.05, M["chrome"])
        # Front: fixed panel + hinged door, both frosted below / clear above
        yf = ya - 0.37
        S.box(f"Booth fixed frosted {i}", BOOTH_D - 0.005, BOOTH_D + 0.005, ya - 0.005, yf, 0.05, 1.75, M["frost"])
        S.box(f"Booth fixed clear {i}", BOOTH_D - 0.005, BOOTH_D + 0.005, ya - 0.005, yf, 1.75, 2.10, M["clear"])
        hg = S.hinge(f"Booth door hinge {i}", BOOTH_D, yf - 0.005, d=0, open_deg=85 if i == 1 else 0, along="y")
        dw = abs(yf - yb) - 0.02
        _lb(c, hg, "Booth door frosted", (dw, 0.010, 1.68), M["frost"], (dw / 2, 0, 0.07 + 0.84))
        _lb(c, hg, "Booth door clear", (dw, 0.010, 0.34), M["clear"], (dw / 2, 0, 1.75 + 0.17))
        for z in (0.32, 1.80):
            _lb(c, hg, "Glass hinge clamp", (0.07, 0.035, 0.085), M["chrome"], (0.0, 0, z), 0.005)
        for side in (-1, 1):
            _lc(c, hg, "Door knob stem", 0.008, 0.03, M["chrome"], (dw - 0.07, side * 0.02, 1.05), (90, 0, 0), seg=10)
            _lc(c, hg, "Door knob", 0.016, 0.02, M["chrome"], (dw - 0.07, side * 0.04, 1.05), (90, 0, 0), seg=16, r2=0.011)
        # Fixtures, drain, light
        _shower_column(S, S.frame(f"Shower column {i}", 0, yc, "+u"), i)
        S.box(f"Booth drain {i}", 0.72, 0.86, yb + 0.32, yb + 0.18, -0.004, 0.003, M["grate"])
        W.cyl(f"{S.tag} SuiteCeiling diffuser {i}", 0.12, 0.012, M["shelf"], c, (S.x(0.50), yc, CEIL - 0.022), seg=32)
        W.cyl(f"{S.tag} SuiteCeiling diffuser vent {i}", 0.085, 0.004, M["dark"], c, (S.x(0.50), yc, CEIL - 0.03), seg=32)
        W.cyl(f"{S.tag} SuiteCeiling shower downlight {i}", 0.045, 0.006, M["glow_white"], c,
              (S.x(0.30), yc - 0.25, CEIL - 0.018), seg=20)
        _spot(c, f"{S.tag} Booth spot {i}", (S.x(0.30), yc - 0.25, CEIL - 0.03), 48, (1.0, 0.90, 0.78))

    # Tiled grid ceiling over the whole shower
    S.box("SuiteCeiling shower tiles", 0, u_in, y_in, Y_BACK, CEIL - 0.015, CEIL - 0.001, M["ceil_tile"])
    # Dry aisle: towel hooks along the divider wall, a couple of towels hanging
    root = S.frame("Hook rail", u_in, Y_LBACK - 3.35, "-u")
    _lb(c, root, "Hook rail bar", (2.2, 0.025, 0.035), M["brushed"], (0, 0.0125, 1.66), 0.004)
    for i in range(6):
        hx = -0.95 + i * 0.38
        _lc(c, root, "Towel hook", 0.011, 0.07, M["chrome"], (hx, 0.055, 1.66), (90, 0, 0), seg=10)
        if i in (1, 4):
            _lb(c, root, "Hanging towel", (0.30, 0.03, 0.62), M["white"], (hx, 0.09, 1.34), 0.012)
    for y in (Y_LBACK - 0.60, Y_LBACK - 2.10):
        W.cyl(f"{S.tag} SuiteCeiling aisle downlight", 0.045, 0.006, M["glow_white"], c, (S.x(1.55), y, CEIL - 0.018), seg=20)
        _spot(c, f"{S.tag} Aisle spot {y}", (S.x(1.55), y, CEIL - 0.03), 40, (1.0, 0.91, 0.80), shadow=False)
    _area_light(c, f"{S.tag} Shower fill", (S.x(u_in / 2), (y_in + Y_BACK) / 2, CEIL - 0.05),
                u_in - 0.3, abs(Y_BACK - y_in) - 0.4, 45, (1.0, 0.93, 0.84), shadow=False)


def _restroom(S):
    """Restroom (u 2.10 .. 4.15) in the reference-photo style."""
    M, c = S.M, S.c
    u_in = U_DIV + DIV_T / 2
    y_in = Y_LBACK - WALL_T / 2
    u0, u1, top = WC_DOOR
    # Door from the locker room (no overhead sign), opens into the restroom
    for u in (u0, u1):
        a, b = (u - 0.02, u + 0.015) if u == u0 else (u - 0.015, u + 0.02)
        S.box("WC door jamb", a, b, Y_LBACK + WALL_T / 2 + 0.01, y_in - 0.01, 0, top, M["brushed"], 0.003)
    S.box("WC door head", u0 - 0.02, u1 + 0.02, Y_LBACK + WALL_T / 2 + 0.01, y_in - 0.01, top - 0.03, top, M["brushed"], 0.003)
    hg = S.hinge("WC door hinge", u1, y_in + 0.02, d=-1, open_deg=82)
    w = u1 - u0 - 0.02
    _lb(c, hg, "WC door leaf", (w, 0.04, top - 0.04), M["brushed"], (w / 2 + 0.01, -0.02, (top - 0.04) / 2 + 0.01), 0.004)
    for side in (-1, 1):
        _lb(c, hg, "WC door pull", (0.02, 0.02, 0.40), M["chrome"], (w - 0.08, -0.02 + side * 0.035, 1.05), 0.006)

    # Vanity on the divider wall, steel unit + teal bin after it, coiled hose under the counter
    _restroom_vanity(S, S.frame("Restroom vanity", u_in, Y_LBACK - 1.25, "+u"), 1.40, sinks=(-0.35, 0.35))
    _trash_bin(S, S.frame("Teal bin", u_in + 0.24, Y_LBACK - 2.18, "+u"))
    _steel_unit(S, S.frame("Steel towel unit", u_in, Y_LBACK - 2.75, "+u"))
    hose = S.frame("Floor hose", u_in + 0.26, Y_LBACK - 0.80, "+u")
    _torus(c, hose, f"{S.tag} hose coil a", 0.15, 0.016, M["hose"], (0, 0, 0.016))
    _torus(c, hose, f"{S.tag} hose coil b", 0.14, 0.016, M["hose"], (0.02, 0.01, 0.048))

    # Two stainless WC cubicles across the back wall
    S.box("Cubicle headrail", u_in, WIDTH, CUBE_Y + 0.02, CUBE_Y - 0.02, 2.05, 2.09, M["chrome"], 0.004)
    S.box("Cubicle divider", CUBE_U[1] - 0.0125, CUBE_U[1] + 0.0125, CUBE_Y, Y_BACK, 0.15, 2.05, M["brushed"], 0.004)
    _lc(c, None, f"{S.tag} Cubicle divider leg", 0.02, 0.15, M["chrome"], (S.x(CUBE_U[1]), CUBE_Y - 0.06, 0.075), seg=14)
    for i, (ua, ub) in enumerate(zip(CUBE_U[:-1], CUBE_U[1:])):
        dw = 0.62
        uh = (ua + ub) / 2 - dw / 2
        S.box(f"Cubicle pilaster a{i}", ua, uh - 0.005, CUBE_Y + 0.0125, CUBE_Y - 0.0125, 0.15, 2.05, M["brushed"], 0.004)
        S.box(f"Cubicle pilaster b{i}", uh + dw + 0.005, ub, CUBE_Y + 0.0125, CUBE_Y - 0.0125, 0.15, 2.05, M["brushed"], 0.004)
        for u in (uh - 0.03, uh + dw + 0.03):
            _lc(c, None, f"{S.tag} Cubicle leg", 0.02, 0.15, M["chrome"], (S.x(u), CUBE_Y, 0.075), seg=14)
        occupied = i == 0
        hg = S.hinge(f"Cubicle door hinge {i}", uh, CUBE_Y, d=1, open_deg=0 if occupied else 58)
        _lb(c, hg, "Cubicle door", (dw - 0.01, 0.025, 1.88), M["brushed"], (dw / 2, 0, 0.15 + 0.94), 0.004)
        for hz in (0.40, 1.70):
            _lc(c, hg, "Cubicle hinge", 0.009, 0.10, M["chrome"], (0.005, 0, hz), seg=10)
        led = M["led_red"] if occupied else M["led_green"]
        for side in (-1, 1):
            _lb(c, hg, "Cubicle lock body", (0.06, 0.012, 0.04), M["chrome"], (dw - 0.06, side * 0.018, 1.02), 0.003)
            _lb(c, hg, "Cubicle lock indicator", (0.035, 0.004, 0.012), led, (dw - 0.06, side * 0.025, 1.022))
            _lc(c, hg, "Cubicle lock turn", 0.012, 0.016, M["chrome"], (dw - 0.06, side * 0.032, 0.99), (90, 0, 0), seg=10)
        _toilet(S, S.frame(f"WC {i}", (ua + ub) / 2, Y_BACK, "+y"), (ub - ua) / 2 - 0.02,
                sanitary_bin=not S.spec["urinals"])

    if S.spec["urinals"]:
        for i, y in enumerate((Y_LBACK - 1.80, Y_LBACK - 2.50)):
            _urinal(S, S.frame(f"Urinal {i}", WIDTH, y, "-u"), i)
        for i, y in enumerate((Y_LBACK - 1.45, Y_LBACK - 2.15, Y_LBACK - 2.85)):
            S.box(f"Urinal screen {i}", WIDTH - 0.46, WIDTH, y + 0.0125, y - 0.0125, 0.42, 1.62, M["brushed"], 0.006)

    S.box("SuiteCeiling restroom tiles", u_in, WIDTH, y_in, Y_BACK, CEIL - 0.015, CEIL - 0.001, M["ceil_tile"])
    for y in (Y_LBACK - 1.10, Y_LBACK - 2.40):
        S.box("SuiteCeiling LED panel", 2.80, 3.40, y + 0.30, y - 0.30, CEIL - 0.020, CEIL - 0.014, M["glow_white"])
    _area_light(c, f"{S.tag} Restroom light", (S.x((u_in + WIDTH) / 2), (y_in + CUBE_Y) / 2, CEIL - 0.05),
                1.2, 2.2, 105, (1.0, 0.97, 0.93))
    _area_light(c, f"{S.tag} Cubicle light", (S.x((u_in + WIDTH) / 2), (CUBE_Y + Y_BACK) / 2, CEIL - 0.05),
                1.6, 1.0, 50, (1.0, 0.98, 0.95), shadow=False)


def _exterior(c):
    """Close the women's suite front where it runs past the gym's right wall (gym wall ends at x = 13.70)."""
    m = bpy.data.materials.get("Gym_Wall") or W.mat("Suite_ExteriorWall", (0.05, 0.05, 0.055), rough=0.85)
    W.box("Annex front wall outside gym", (15.95 - 13.70, 0.20, CEIL + 0.08), m, c, ((13.70 + 15.95) / 2, -6.80, (CEIL + 0.08) / 2))


def build_locker_suites(parent):
    """Build both gender suites under `parent`. Returns {'Men': collection, 'Women': collection}."""
    root = W.coll("Gym Locker Suites", parent)
    out = {}
    for spec in SUITES:
        c = W.coll(f"Annex - {spec['tag']} Suite", root)
        S = _Suite(c, spec)
        _shell(S)
        _locker_room(S)
        _shower_room(S)
        _restroom(S)
        yb = Y_LBACK - WALL_T / 2
        _room_probe(S, "Locker reflection probe", 0, WIDTH, Y_FRONT, Y_LBACK + WALL_T / 2)
        _room_probe(S, "Shower reflection probe", 0, U_DIV - DIV_T / 2, yb, Y_BACK)
        _room_probe(S, "Restroom reflection probe", U_DIV + DIV_T / 2, WIDTH, yb, Y_BACK)
        out[spec["tag"]] = c
    _exterior(out["Women"])
    return out
