"""WatchCoach gym annex, phase 3: gender-separated Locker room -> Shower -> Restroom suites behind the gym front wall.

build_locker_suites(parent) adds two suites that mirror each other across a central partition at x = 11.60:
  Men   x  7.40 .. 11.55      Women  x 11.65 .. 15.80      y -6.90 (front) .. -15.30 (back), ceiling z = 3.00
  Locker room  y  -6.90 .. -10.50   entered through the MEN / WOMEN doors (x 10.95 / 12.25) of gym_annex.build_gym_doors
  Shower       y -10.50 .. -13.10   frosted glass door from the locker room, 3 booths, drain trench
  Restroom     y -13.10 .. -15.30   door from the shower, 2 WC cubicles, sink + mirror + hand dryer (+ 2 urinals for men)
Every suite works in its own frame: u = distance from the partition face toward the suite's outer wall.
"""
import math

import bpy
import wc_lib as W

Y_FRONT, Y_SHOWER, Y_TOILET, Y_BACK = -6.90, -10.50, -13.10, -15.30
CEIL = 3.00
PART_X, PART_T = 11.60, 0.10   # central partition
WIDTH = 4.15                   # inner width of one suite
SHELL_T = 0.15                 # outer shell walls
WALL_T = 0.10                  # walls between the zones
ENTRY_W, ENTRY_H = 0.91, 2.18  # same opening gym_annex cuts through Wall_Front
GLASS_DOOR = (1.30, 2.20, 2.10)    # locker -> shower opening (u0, u1, top)
WC_DOOR = (0.15, 1.05, 2.10)       # shower -> restroom opening
BOOTHS = (1.30, 2.25, 3.20, 4.15)  # shower booth boundaries in u
BOOTH_FRONT = -12.05
CUBE_U = 2.70                      # WC cubicle front line in u

SUITES = (
    dict(tag="Men", s=-1, door_x=10.95, accent=(0.18, 0.56, 0.96), urinals=True, first_locker=201,
         wood=(0.12, 0.072, 0.042), locker=(0.075, 0.080, 0.088), cubicle=(0.20, 0.22, 0.25)),
    dict(tag="Women", s=1, door_x=12.25, accent=(0.96, 0.32, 0.48), urinals=False, first_locker=301,
         wood=(0.52, 0.37, 0.23), locker=(0.66, 0.62, 0.56), cubicle=(0.62, 0.55, 0.53)),
)

# ------------------------------------------------------------------ materials


def _tile_mat(name, color, grout, tile_w, tile_h, axes="XY", rough=0.45, grout_w=0.003):
    """Grid tiles from world position (stacked Brick texture) with grout bump. axes: which world axes form the face."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, color, rough=rough)
    nt, N, L = m.node_tree, m.node_tree.nodes, m.node_tree.links
    bsdf = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    L.new(sep.outputs[axes[0]], comb.inputs["X"])
    L.new(sep.outputs[axes[1]], comb.inputs["Y"])
    br = N.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.squash = 1.0
    L.new(comb.outputs[0], br.inputs["Vector"])
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = tile_w
    br.inputs["Row Height"].default_value = tile_h
    br.inputs["Mortar Size"].default_value = grout_w
    br.inputs["Mortar Smooth"].default_value = 0.3
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (*color, 1)
    br.inputs["Color2"].default_value = (*[min(1.0, v * 1.06) for v in color], 1)
    br.inputs["Mortar"].default_value = (*grout, 1)
    L.new(br.outputs["Color"], bsdf.inputs["Base Color"])
    bump = N.new("ShaderNodeBump")
    bump.invert = True
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.002
    L.new(br.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _glass(name, color, alpha, rough):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = W.mat(name, color, rough=rough)
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Alpha"].default_value = alpha
    try:
        m.use_transparent_shadow = True
    except AttributeError:
        pass
    return m


def _materials(spec):
    t = spec["tag"]
    return {
        "paint": W.mat("Suite_WarmPaint", (0.43, 0.40, 0.36), rough=0.82),
        "wood": W.mat(f"Suite_Wood_{t}", spec["wood"], rough=0.48),
        "locker": W.mat(f"Suite_LockerDoor_{t}", spec["locker"], rough=0.42, metal=0.08),
        "cubicle": W.mat(f"Suite_Cubicle_{t}", spec["cubicle"], rough=0.40),
        "accent": W.shadeless(f"Suite_Accent_{t}", spec["accent"], strength=2.4),
        "carcass": W.mat("Suite_Carcass", (0.05, 0.052, 0.056), rough=0.55),
        "steel": W.mat("Suite_BlackSteel", (0.028, 0.029, 0.032), rough=0.42, metal=0.65),
        "chrome": W.mat("Suite_Chrome", (0.72, 0.73, 0.74), rough=0.16, metal=1.0),
        "quartz": W.mat("Suite_Quartz", (0.80, 0.79, 0.77), rough=0.22),
        "ceramic": W.mat("Suite_Ceramic", (0.86, 0.87, 0.86), rough=0.10),
        "ceramic_in": W.mat("Suite_CeramicInner", (0.70, 0.72, 0.72), rough=0.12),
        "ceiling": W.mat("Suite_Ceiling", (0.76, 0.76, 0.74), rough=0.92),
        "laminate": W.mat("Suite_ShowerLaminate", (0.16, 0.17, 0.18), rough=0.50),
        "mirror": W.mat("Suite_Mirror", (0.93, 0.94, 0.95), rough=0.02, metal=1.0),
        "frost": _glass("Suite_FrostGlass", (0.82, 0.88, 0.90), 0.42, 0.30),
        "dark": W.mat("Suite_DarkSlot", (0.012, 0.012, 0.014), rough=0.7),
        "white": W.mat("Suite_TowelWhite", (0.84, 0.84, 0.82), rough=0.95),
        "plate": W.mat("Suite_NumberPlate", (0.58, 0.60, 0.62), rough=0.30, metal=0.85),
        "text": W.shadeless("Suite_SignText", (0.94, 0.95, 0.97), strength=1.4),
        "text_dark": W.mat("Suite_PlateText", (0.02, 0.02, 0.025), rough=0.5),
        "glow_warm": W.shadeless("Suite_GlowWarm", (1.0, 0.80, 0.56), strength=3.2),
        "glow_cool": W.shadeless("Suite_GlowCool", (0.88, 0.94, 1.0), strength=3.0),
        "led_red": W.shadeless("Suite_LockRed", (0.95, 0.06, 0.05), strength=2.5),
        "led_green": W.shadeless("Suite_LockGreen", (0.10, 0.90, 0.25), strength=2.5),
        "floor_locker": _tile_mat("Suite_LockerFloor", (0.32, 0.30, 0.275), (0.15, 0.145, 0.14), 0.60, 0.60, "XY", 0.35),
        "floor_shower": _tile_mat("Suite_ShowerFloor", (0.19, 0.195, 0.20), (0.09, 0.09, 0.095), 0.10, 0.10, "XY", 0.78),
        "floor_wc": _tile_mat("Suite_WCFloor", (0.36, 0.36, 0.35), (0.20, 0.20, 0.20), 0.60, 0.30, "XY", 0.40),
        "shower_xz": _tile_mat("Suite_ShowerTile_XZ", (0.44, 0.45, 0.46), (0.25, 0.25, 0.26), 0.30, 0.60, "XZ", 0.30),
        "shower_yz": _tile_mat("Suite_ShowerTile_YZ", (0.44, 0.45, 0.46), (0.25, 0.25, 0.26), 0.30, 0.60, "YZ", 0.30),
        "wc_xz": _tile_mat("Suite_WCTile_XZ", (0.70, 0.70, 0.68), (0.50, 0.50, 0.49), 0.30, 0.60, "XZ", 0.25),
        "wc_yz": _tile_mat("Suite_WCTile_YZ", (0.70, 0.70, 0.68), (0.50, 0.50, 0.49), 0.30, 0.60, "YZ", 0.25),
        "grate": _tile_mat("Suite_DrainGrate", (0.55, 0.56, 0.57), (0.01, 0.01, 0.01), 0.016, 1.0, "XY", 0.25, 0.006),
    }


# ------------------------------------------------------------------ small helpers


def _bevel(ob, radius):
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width = radius
    bv.segments = 2
    bv.limit_method = "ANGLE"
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


def _mirror_probe(c, root, name, xyz, w, h):
    """Planar reflection probe over a mirror in a fixture frame (mirror faces local +Y), like the gym's MirrorProbe.
    Kept unparented in world space and ~1 cm proud of the glass: a parented probe hugging the glass reflected nothing."""
    try:
        lp = bpy.data.lightprobes.new(name, "PLANE")
    except Exception:
        return None
    ob = bpy.data.objects.new(name, lp)
    c.objects.link(ob)
    yaw = root.rotation_euler.z
    lx, ly, lz = xyz[0], xyz[1] + 0.01, xyz[2]
    ob.location = (root.location.x + lx * math.cos(yaw) - ly * math.sin(yaw),
                   root.location.y + lx * math.sin(yaw) + ly * math.cos(yaw), root.location.z + lz)
    ob.rotation_euler = (math.radians(90), 0, yaw + math.pi)
    ob.scale = (w / 2, h / 2, 1.0)
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


def _area_light(c, name, xyz, size, size_y, energy, color):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size, size_y
    ld.energy = energy
    ld.color = color
    try:
        ld.use_shadow = True
        ld.specular_factor = 0.6
    except AttributeError:
        pass
    ob = bpy.data.objects.new(name, ld)
    ob.location = xyz
    c.objects.link(ob)
    return ob


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
        """A wall spanning the full suite width with door openings [(u0, u1, z_top)], two finishes (north / south half)."""
        ym = (y_north + y_south) / 2
        cuts = sorted(openings)
        spans, u = [], -PART_T / 2
        for u0, u1, _ in cuts:
            spans.append((u, u0))
            u = u1
        spans.append((u, WIDTH + SHELL_T))
        for half, (ya, yb, m) in enumerate(((y_north, ym, m_north), (ym, y_south, m_south))):
            for i, (a, b) in enumerate(spans):
                self.box(f"{name} {half}{i}", a, b, ya, yb, 0, CEIL, m)
            for i, (u0, u1, zt) in enumerate(cuts):
                self.box(f"{name} header {half}{i}", u0, u1, ya, yb, zt, CEIL, m)

    def wall_y(self, name, u0, u1, y0, y1, m):
        return self.box(name, u0, u1, y0, y1, 0, CEIL, m)


# ------------------------------------------------------------------ fixtures (local frame: wall at y = 0, front = +Y)


def _locker_run(S, root, n, first_no):
    c, M = S.c, S.M
    cw, d, H, plinth = 0.42, 0.52, 1.90, 0.10
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


def _vanity(S, root, length, sinks, powder):
    """Floating wood vanity, quartz top, vessel basins, backlit mirror. sinks / powder: local x positions."""
    c, M = S.c, S.M
    depth = 0.55
    _lb(c, root, "Vanity cabinet", (length, depth - 0.03, 0.46), M["wood"], (0, (depth - 0.03) / 2, 0.55), 0.008)
    _lb(c, root, "Vanity top", (length + 0.03, depth, 0.035), M["quartz"], (0, depth / 2, 0.80), 0.004)
    _lb(c, root, "Vanity toe light", (length - 0.1, 0.01, 0.01), M["glow_warm"], (0, depth - 0.08, 0.315))
    _lb(c, root, "Vanity mirror glow", (length - 0.02, 0.006, 0.98), M["glow_warm"], (0, 0.004, 1.52))
    _lb(c, root, "Vanity mirror", (length - 0.08, 0.012, 0.92), M["mirror"], (0, 0.014, 1.52))
    _mirror_probe(c, root, f"{S.tag} {root.name} probe", (0, 0.021, 1.52), length - 0.08, 0.92)
    for i, sx in enumerate(sinks):
        _lc(c, root, "Vessel basin", 0.19, 0.12, M["ceramic"], (sx, 0.30, 0.878), seg=32, r2=0.16)
        _lc(c, root, "Vessel basin inside", 0.165, 0.004, M["ceramic_in"], (sx, 0.30, 0.937), seg=32)
        _lc(c, root, "Faucet riser", 0.013, 0.30, M["chrome"], (sx, 0.07, 0.97), seg=12)
        _lc(c, root, "Faucet spout", 0.011, 0.16, M["chrome"], (sx, 0.15, 1.115), (90, 0, 0), seg=12)
        _lb(c, root, "Faucet lever", (0.012, 0.07, 0.012), M["chrome"], (sx + 0.03, 0.06, 1.08), 0.004)
        _lb(c, root, "Soap dispenser", (0.05, 0.05, 0.12), M["chrome"], (sx + 0.28, 0.08, 0.88), 0.01)
    for i, px in enumerate(powder):
        # Wall-holstered hair dryer under the mirror
        _lb(c, root, "Dryer holster", (0.05, 0.11, 0.025), M["steel"], (px, 0.055, 0.95), 0.006)
        _lc(c, root, "Dryer holster ring", 0.045, 0.03, M["steel"], (px, 0.12, 0.95), seg=20)
        _lc(c, root, "Hair dryer handle", 0.02, 0.16, M["carcass"], (px, 0.12, 0.99), seg=12)
        _lc(c, root, "Hair dryer body", 0.045, 0.19, M["carcass"], (px, 0.15, 1.08), (90, 0, 0), seg=20)
        _lc(c, root, "Hair dryer nozzle", 0.03, 0.05, M["steel"], (px, 0.265, 1.08), (90, 0, 0), seg=16, r2=0.024)
        _lc(c, root, "Hair dryer cord", 0.004, 0.16, M["dark"], (px, 0.12, 0.89), seg=6)
        # Round stool
        _lc(c, root, "Stool base", 0.17, 0.02, M["chrome"], (px, 0.78, 0.01), seg=24)
        _lc(c, root, "Stool post", 0.022, 0.56, M["chrome"], (px, 0.78, 0.30), seg=12)
        _lc(c, root, "Stool cushion", 0.17, 0.07, M["carcass"], (px, 0.78, 0.615), seg=24)
    if powder:
        _lb(c, root, "Tissue box", (0.22, 0.11, 0.08), M["white"], (powder[0] + 0.24, 0.20, 0.858), 0.01)


def _sign(S, root, main, sub, z, width=0.60):
    c, M = S.c, S.M
    _lb(c, root, "Sign plaque", (width, 0.022, 0.15), M["carcass"], (0, 0.011, z), 0.005)
    _lb(c, root, "Sign accent", (width - 0.04, 0.005, 0.012), M["accent"], (0, 0.024, z + 0.058))
    _label(c, root, f"{S.tag} sign {main}", main, (0, 0.0235, z + 0.012), 0.050, M["text"])
    _label(c, root, f"{S.tag} sign {main} sub", sub, (0, 0.0235, z - 0.042), 0.032, M["text"])


def _shower_booth(S, root, w):
    """Fixtures on a booth's back wall: rain head, mixer, slide bar + hand shower, shampoo shelf with bottles."""
    c, M = S.c, S.M
    _lc(c, root, "Shower riser", 0.013, 1.10, M["chrome"], (0, 0.045, 1.66), seg=12)
    _lc(c, root, "Shower arm", 0.012, 0.36, M["chrome"], (0, 0.22, 2.20), (90, 0, 0), seg=12)
    _lc(c, root, "Rain shower head", 0.13, 0.014, M["chrome"], (0, 0.36, 2.185), seg=32)
    _lc(c, root, "Rain shower face", 0.115, 0.002, M["dark"], (0, 0.36, 2.177), seg=32)
    _lc(c, root, "Mixer plate", 0.07, 0.012, M["chrome"], (0, 0.006, 1.10), (90, 0, 0), seg=24)
    _lb(c, root, "Mixer lever", (0.12, 0.02, 0.018), M["chrome"], (0.03, 0.035, 1.10), 0.006)
    bx = w / 2 - 0.20
    _lc(c, root, "Slide bar", 0.011, 0.72, M["chrome"], (bx, 0.05, 1.42), seg=12)
    for bz in (1.06, 1.78):
        _lc(c, root, "Slide bar mount", 0.016, 0.05, M["chrome"], (bx, 0.025, bz), (90, 0, 0), seg=12)
    _lc(c, root, "Hand shower grip", 0.017, 0.20, M["chrome"], (bx, 0.075, 1.56), (-20, 0, 0), seg=12)
    _lc(c, root, "Hand shower head", 0.042, 0.03, M["chrome"], (bx, 0.115, 1.66), (70, 0, 0), seg=20)
    # Hose: two short segments looping down to the mixer
    _lc(c, root, "Shower hose", 0.007, 0.55, M["chrome"], (bx - 0.07, 0.07, 1.30), (0, 25, 0), seg=8)
    _lc(c, root, "Shower hose", 0.007, 0.30, M["chrome"], (bx - 0.22, 0.05, 1.07), (0, 80, 0), seg=8)
    sx = -w / 2 + 0.22
    _lb(c, root, "Shampoo shelf", (0.30, 0.12, 0.012), M["chrome"], (sx, 0.06, 1.30), 0.003)
    _lb(c, root, "Shampoo shelf lip", (0.30, 0.008, 0.03), M["chrome"], (sx, 0.12, 1.31), 0.002)
    for i, (col, h) in enumerate((((0.86, 0.86, 0.84), 0.20), ((0.08, 0.09, 0.10), 0.18), (S.spec["accent"], 0.16))):
        mb = W.mat(f"Suite_Bottle_{S.tag}_{i}", col, rough=0.35)
        _lc(c, root, "Shampoo bottle", 0.03, h, mb, (sx - 0.09 + i * 0.09, 0.06, 1.306 + h / 2), seg=14)
        _lc(c, root, "Pump cap", 0.012, 0.035, M["dark"], (sx - 0.09 + i * 0.09, 0.06, 1.306 + h + 0.017), seg=10)


def _toilet(S, root, half_w, sanitary_bin):
    """Wall-hung WC on a concealed cistern (flush plate), facing local +Y. half_w: half the cubicle width."""
    c, M = S.c, S.M
    _lb(c, root, "Flush plate", (0.24, 0.010, 0.16), M["chrome"], (0, 0.005, 1.02), 0.004)
    _lb(c, root, "Flush button big", (0.10, 0.006, 0.12), M["plate"], (-0.05, 0.011, 1.02), 0.004)
    _lb(c, root, "Flush button small", (0.06, 0.006, 0.12), M["plate"], (0.06, 0.011, 1.02), 0.004)
    _lb(c, root, "WC back", (0.30, 0.14, 0.20), M["ceramic"], (0, 0.07, 0.33), 0.03)
    bowl = _lc(c, root, "WC bowl", 0.18, 0.17, M["ceramic"], (0, 0.31, 0.315), seg=28, r2=0.165)
    bowl.scale.y = 1.42
    seat = _lc(c, root, "WC seat lid", 0.182, 0.035, M["ceramic"], (0, 0.31, 0.418), seg=28)
    seat.scale.y = 1.42
    _bevel(seat, 0.012)
    _lb(c, root, "Paper holder", (0.03, 0.15, 0.03), M["chrome"], (half_w - 0.03, 0.55, 0.72), 0.006)
    _lc(c, root, "Paper roll", 0.055, 0.11, M["white"], (half_w - 0.075, 0.55, 0.69), (90, 0, 0), seg=20)
    _lb(c, root, "Coat hook", (0.02, 0.06, 0.02), M["chrome"], (-half_w + 0.02, 0.50, 1.60), 0.006)
    if sanitary_bin:
        _lb(c, root, "Sanitary bin", (0.18, 0.28, 0.30), M["plate"], (-half_w + 0.12, 0.30, 0.15), 0.02)


def _urinal(S, root, idx):
    c, M = S.c, S.M
    body = _lc(c, root, "Urinal body", 0.19, 0.66, M["ceramic"], (0, 0.08, 0.86), seg=28)
    body.scale.y = 1.15
    cutter = _lc(c, root, f"{S.tag} urinal cutter {idx}", 0.15, 0.50, M["dark"], (0, 0.20, 0.93), seg=24)
    cutter.hide_render = True
    cutter.hide_viewport = True
    cutter.display_type = "WIRE"
    bo = body.modifiers.new("Bowl", "BOOLEAN")
    bo.operation = "DIFFERENCE"
    bo.object = cutter
    _bevel(body, 0.01)
    _lc(c, root, "Urinal drain", 0.04, 0.01, M["chrome"], (0, 0.13, 0.68), seg=16)
    _lc(c, root, "Flush valve pipe", 0.016, 0.26, M["chrome"], (0, 0.05, 1.32), seg=12)
    _lb(c, root, "Flush sensor", (0.10, 0.05, 0.12), M["chrome"], (0, 0.03, 1.50), 0.01)
    _lb(c, root, "Flush sensor eye", (0.03, 0.004, 0.018), M["led_red"], (0, 0.057, 1.48))


def _hand_dryer(S, root):
    c, M = S.c, S.M
    _lb(c, root, "Hand dryer body", (0.30, 0.20, 0.62), M["plate"], (0, 0.10, 1.12), 0.04)
    _lb(c, root, "Hand dryer slot", (0.26, 0.06, 0.08), M["dark"], (0, 0.18, 1.14))
    _lb(c, root, "Hand dryer led", (0.05, 0.004, 0.01), M["glow_cool"], (0, 0.202, 1.36))
    _lc(c, root, "Trash bin", 0.16, 0.56, M["chrome"], (0, 0.22, 0.28), seg=24)
    _lc(c, root, "Trash bin lid", 0.162, 0.03, M["steel"], (0, 0.22, 0.575), seg=24)


# ------------------------------------------------------------------ suite assembly


def _shell(S):
    M = S.M
    t = SHELL_T
    # Floors (top at z = 0, flush with the gym floor plane)
    S.box("Floor locker", -PART_T / 2, WIDTH + t, Y_FRONT, Y_SHOWER, -0.06, 0.0, M["floor_locker"])
    S.box("Floor shower", -PART_T / 2, WIDTH + t, Y_SHOWER, Y_TOILET, -0.06, 0.0, M["floor_shower"])
    S.box("Floor restroom", -PART_T / 2, WIDTH + t, Y_TOILET, Y_BACK - t, -0.06, 0.0, M["floor_wc"])
    # Half of the central partition + the outer wall, finished per zone
    for zone, y0, y1, part_m, outer_m in (
        ("locker", Y_FRONT, Y_SHOWER, M["wood"], M["paint"]),
        ("shower", Y_SHOWER, Y_TOILET, M["shower_yz"], M["shower_yz"]),
        ("restroom", Y_TOILET, Y_BACK, M["wc_yz"], M["wc_yz"]),
    ):
        S.wall_y(f"Partition {zone}", -PART_T / 2, 0, y0, y1, part_m)
        S.wall_y(f"Outer wall {zone}", WIDTH, WIDTH + t, y0, y1, outer_m)
    S.box("Back wall", -PART_T / 2, WIDTH + t, Y_BACK, Y_BACK - t, 0, CEIL, M["wc_xz"])
    # Front liner on the back face of the gym wall, with the entrance opening
    du, hw = S.door_u, ENTRY_W / 2
    S.box("Front liner a", 0, du - hw, Y_FRONT, Y_FRONT - 0.02, 0, CEIL, M["paint"])
    S.box("Front liner b", du + hw, WIDTH, Y_FRONT, Y_FRONT - 0.02, 0, CEIL, M["paint"])
    S.box("Front liner header", du - hw, du + hw, Y_FRONT, Y_FRONT - 0.02, ENTRY_H, CEIL, M["paint"])
    for side in (-1, 1):  # door casing on the suite side
        S.box("Entry casing", du + side * (hw + 0.035), du + side * (hw - 0.005), Y_FRONT - 0.02, Y_FRONT - 0.045,
              0, ENTRY_H + 0.04, M["steel"], 0.004)
    S.box("Entry casing head", du - hw - 0.075, du + hw + 0.075, Y_FRONT - 0.02, Y_FRONT - 0.045,
          ENTRY_H, ENTRY_H + 0.07, M["steel"], 0.004)
    S.box("Entry reveal floor", du - hw, du + hw, Y_FRONT + 0.20, Y_FRONT, -0.05, 0.004, M["floor_locker"])
    S.box("Entry threshold", du - hw, du + hw, Y_FRONT + 0.06, Y_FRONT - 0.04, 0, 0.012, M["chrome"], 0.003)
    # Zone walls
    S.wall_u("Shower wall", Y_SHOWER + WALL_T / 2, Y_SHOWER - WALL_T / 2, [GLASS_DOOR], M["paint"], M["shower_xz"])
    S.wall_u("Restroom wall", Y_TOILET + WALL_T / 2, Y_TOILET - WALL_T / 2, [WC_DOOR], M["shower_xz"], M["wc_xz"])
    # Ceiling slab (named SuiteCeiling so test renders can find it)
    S.box("SuiteCeiling slab", -PART_T / 2, WIDTH + t, Y_FRONT, Y_BACK - t, CEIL, CEIL + 0.08, M["ceiling"])


def _locker_room(S):
    M, c = S.M, S.c
    # Indirect-light ceiling: dropped soffit band with a warm cove line around a recessed field
    sb, z0 = 0.32, 2.82
    for name, u0, u1, y0, y1 in (
        ("front", 0, WIDTH, Y_FRONT, Y_FRONT - sb), ("back", 0, WIDTH, Y_SHOWER + WALL_T / 2 + sb, Y_SHOWER + WALL_T / 2),
        ("part", 0, sb, Y_FRONT - sb, Y_SHOWER + WALL_T / 2 + sb), ("outer", WIDTH - sb, WIDTH, Y_FRONT - sb, Y_SHOWER + WALL_T / 2 + sb),
    ):
        S.box(f"SuiteCeiling soffit {name}", u0, u1, y0, y1, z0, CEIL, M["ceiling"])
    yi0, yi1 = Y_FRONT - sb, Y_SHOWER + WALL_T / 2 + sb
    S.box("SuiteCeiling cove f", sb, WIDTH - sb, yi0 - 0.005, yi0 - 0.02, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    S.box("SuiteCeiling cove b", sb, WIDTH - sb, yi1 + 0.02, yi1 + 0.005, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    S.box("SuiteCeiling cove p", sb + 0.005, sb + 0.02, yi0, yi1, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    S.box("SuiteCeiling cove o", WIDTH - sb - 0.02, WIDTH - sb - 0.005, yi0, yi1, CEIL - 0.03, CEIL - 0.005, M["glow_warm"])
    for u in (sb / 2, WIDTH - sb / 2):
        for y in (-7.9, -9.5):
            W.cyl(f"{S.tag} SuiteCeiling downlight", 0.045, 0.006, M["glow_warm"], c, (S.x(u), y, z0 - 0.003), seg=16)

    # Two-tier lockers: 7 columns on the outer wall, 5 on the front wall
    n = S.spec["first_locker"]
    run_len = 7 * 0.42
    y_start = Y_FRONT - 0.26 - run_len if S.s > 0 else Y_FRONT - 0.26
    root = S.frame("Lockers outer wall", WIDTH, y_start, "-u")
    n = _locker_run(S, root, 7, n)
    x_lo, x_hi = sorted((S.x(1.40), S.x(1.40 + 5 * 0.42)))
    root = W.empty(f"{S.tag} Lockers front wall", c, (x_hi, Y_FRONT - 0.02, 0))
    root.rotation_euler.z = math.pi
    _locker_run(S, root, 5, n)

    # Centre bench: oiled wood top on black steel sled legs
    bu, by = 2.35, -8.75
    S.box("Bench top", bu - 0.21, bu + 0.21, by + 0.95, by - 0.95, 0.425, 0.47, M["wood"], 0.01)
    for ly in (by + 0.75, by - 0.75):
        S.box("Bench leg", bu - 0.19, bu + 0.19, ly + 0.02, ly - 0.02, 0.0, 0.425, M["steel"], 0.004)
        S.box("Bench foot", bu - 0.19, bu + 0.19, ly + 0.03, ly - 0.03, 0.0, 0.02, M["steel"], 0.004)
    S.box("Gym bag on bench", bu - 0.15, bu + 0.12, by + 0.55, by + 0.12, 0.47, 0.70, M["carcass"], 0.06)
    S.box("Folded towel bench", bu - 0.12, bu + 0.12, by - 0.30, by - 0.62, 0.47, 0.52, M["white"], 0.02)

    # Powder / wash counter on the partition wall (wood wall behind)
    root = S.frame("Vanity", 0, -8.85, "+u")
    _vanity(S, root, 2.2, sinks=(-0.75, -0.25), powder=(0.35, 0.85))

    # Shower wall (locker side): towel return bin, full-length mirror, SHOWER sign over the glass door
    yw = Y_SHOWER + WALL_T / 2
    root = S.frame("Towel return", 2.62, yw, "+y")
    _lb(c, root, "Towel bin body", (0.50, 0.42, 0.80), M["wood"], (0, 0.21, 0.40), 0.01)
    _lb(c, root, "Towel bin slot", (0.38, 0.30, 0.012), M["dark"], (0, 0.22, 0.805))
    _lb(c, root, "Towel bin label", (0.36, 0.005, 0.10), M["carcass"], (0, 0.423, 0.60), 0.003)
    _label(c, root, f"{S.tag} towel label", "USED TOWEL · 사용한 수건", (0, 0.4265, 0.60), 0.026, M["text"])
    _lb(c, root, "Towel in bin", (0.30, 0.20, 0.06), M["white"], (0.02, 0.22, 0.83), 0.02)
    root = S.frame("Full mirror", 3.30, yw, "+y")
    _lb(c, root, "Full mirror frame", (0.64, 0.03, 1.80), M["wood"], (0, 0.015, 1.10), 0.006)
    _lb(c, root, "Full mirror glass", (0.56, 0.012, 1.72), M["mirror"], (0, 0.034, 1.10))
    _mirror_probe(c, root, f"{S.tag} full mirror probe", (0, 0.041, 1.10), 0.56, 1.72)
    root = S.frame("Shower sign", (GLASS_DOOR[0] + GLASS_DOOR[1]) / 2, yw, "+y")
    _sign(S, root, "SHOWER", "샤워실", 2.36)

    _area_light(c, f"{S.tag} Locker light", (S.x(WIDTH / 2), (Y_FRONT + Y_SHOWER) / 2, CEIL - 0.05),
                WIDTH - 0.7, abs(Y_SHOWER - Y_FRONT) - 0.7, 420, (1.0, 0.86, 0.70))


def _door_frame(S, name, u0, u1, y_mid, top, m):
    for u in (u0, u1):  # jambs sit slightly inside the opening so their faces never share the wall's end plane
        a, b = (u - 0.02, u + 0.015) if u == u0 else (u - 0.015, u + 0.02)
        S.box(f"{name} jamb", a, b, y_mid + WALL_T / 2 + 0.01, y_mid - WALL_T / 2 - 0.01, 0, top, m, 0.003)
    S.box(f"{name} head", u0 - 0.03, u1 + 0.03, y_mid + WALL_T / 2 + 0.01, y_mid - WALL_T / 2 - 0.01, top - 0.03, top, m, 0.003)


def _shower_room(S):
    M, c = S.M, S.c
    u0, u1, top = GLASS_DOOR
    _door_frame(S, "Glass door frame", u0, u1, Y_SHOWER, top, M["chrome"])
    # Frameless frosted glass door, hinged at u0, standing slightly open into the shower
    hg = S.hinge("Glass door hinge", u0, Y_SHOWER, d=1, open_deg=28)
    w = u1 - u0 - 0.02
    _lb(c, hg, "Glass door panel", (w, 0.012, top - 0.04), M["frost"], (w / 2 + 0.01, 0, (top - 0.04) / 2 + 0.01))
    for hz in (0.25, top - 0.25):
        _lb(c, hg, "Glass door pivot", (0.06, 0.03, 0.08), M["chrome"], (0.04, 0, hz), 0.004)
    for side in (-1, 1):
        _lc(c, hg, "Glass door pull", 0.012, 0.50, M["chrome"], (w - 0.08, side * 0.035, 1.05), seg=12)

    # Three booths on the restroom wall: opaque side panels, frosted front doors, chrome header rail
    yb = Y_TOILET + WALL_T / 2
    for i, u in enumerate(BOOTHS[:-1]):
        S.box(f"Booth panel {i}", u - 0.0125, u + 0.0125, BOOTH_FRONT, yb, 0.10, 2.05, M["laminate"], 0.004)
        S.box(f"Booth panel foot {i}", u - 0.02, u + 0.02, BOOTH_FRONT + 0.02, BOOTH_FRONT - 0.05, 0, 0.10, M["chrome"], 0.004)
    S.box("Booth header rail", BOOTHS[0] - 0.02, WIDTH, BOOTH_FRONT + 0.02, BOOTH_FRONT - 0.02, 2.05, 2.09, M["chrome"], 0.004)
    for i, (a, b) in enumerate(zip(BOOTHS[:-1], BOOTHS[1:])):
        S.box(f"Booth glass {i}", a + 0.03, b - 0.03, BOOTH_FRONT + 0.006, BOOTH_FRONT - 0.006, 0.18, 1.98, M["frost"])
        S.box(f"Booth glass handle {i}", b - 0.12, b - 0.10, BOOTH_FRONT + 0.03, BOOTH_FRONT + 0.01, 0.85, 1.25, M["chrome"], 0.004)
        root = S.frame(f"Booth {i}", (a + b) / 2, yb, "+y")
        _shower_booth(S, root, b - a)
    # Drain trench across the booths, stainless slot grate
    S.box("Drain trench", BOOTHS[0] + 0.02, WIDTH - 0.02, yb + 0.22, yb + 0.10, -0.004, 0.004, M["grate"])
    S.box("Drain trench rim", BOOTHS[0] + 0.01, WIDTH - 0.01, yb + 0.235, yb + 0.085, -0.006, 0.002, M["chrome"])
    # Dry side: towel hook rail on the partition, TOILET sign over the restroom door
    root = S.frame("Hook rail", 0, -11.75, "+u")
    _lb(c, root, "Hook rail board", (1.6, 0.03, 0.12), M["wood"], (0, 0.015, 1.62), 0.006)
    for i in range(5):
        hx = -0.64 + i * 0.32
        _lc(c, root, "Towel hook", 0.012, 0.08, M["chrome"], (hx, 0.07, 1.62), (90, 0, 0), seg=10)
        if i in (1, 3):
            _lb(c, root, "Hanging towel", (0.26, 0.03, 0.55), M["white"], (hx, 0.10, 1.36), 0.01)
    root = S.frame("Toilet sign", (WC_DOOR[0] + WC_DOOR[1]) / 2, yb, "+y")
    _sign(S, root, "TOILET", "화장실", 2.36)
    for u in (1.0, 2.75):
        W.cyl(f"{S.tag} SuiteCeiling shower downlight", 0.07, 0.006, M["glow_cool"], c, (S.x(u), -11.5, CEIL - 0.003), seg=20)
    _area_light(c, f"{S.tag} Shower light", (S.x(WIDTH / 2), (Y_SHOWER + Y_TOILET) / 2, CEIL - 0.05),
                WIDTH - 0.6, abs(Y_TOILET - Y_SHOWER) - 0.6, 140, (0.90, 0.95, 1.0))


def _restroom(S):
    M, c = S.M, S.c
    u0, u1, top = WC_DOOR
    _door_frame(S, "WC door frame", u0, u1, Y_TOILET, top, M["steel"])
    hg = S.hinge("WC door hinge", u1, Y_TOILET - WALL_T / 2 + 0.02, d=-1, open_deg=72)
    w = u1 - u0 - 0.02
    _lb(c, hg, "WC door leaf", (w, 0.04, top - 0.04), M["cubicle"], (w / 2 + 0.01, -0.02, (top - 0.04) / 2 + 0.01), 0.004)
    _lb(c, hg, "WC door kickplate", (w - 0.04, 0.004, 0.18), M["chrome"], (w / 2 + 0.01, -0.042, 0.11))
    for side in (-1, 1):
        _lb(c, hg, "WC door lever", (0.12, 0.015, 0.018), M["chrome"], (w - 0.10, -0.02 + side * 0.04, 1.02), 0.005)

    yi = Y_TOILET - WALL_T / 2  # restroom side of the shower wall
    # Two WC cubicles against the outer wall
    ymid = (yi + Y_BACK) / 2
    S.box("Cubicle divider", CUBE_U, WIDTH, ymid + 0.0125, ymid - 0.0125, 0.15, 2.05, M["cubicle"], 0.004)
    S.box("Cubicle divider foot", CUBE_U, CUBE_U + 0.05, ymid + 0.02, ymid - 0.02, 0, 0.15, M["chrome"])
    S.box("Cubicle headrail", CUBE_U - 0.02, CUBE_U + 0.02, yi, Y_BACK, 2.05, 2.09, M["chrome"], 0.004)
    for i, (ya, yb) in enumerate(((yi, ymid), (ymid, Y_BACK))):
        dw = 0.62
        dc = (ya + yb) / 2
        y_h, y_e = dc + dw / 2, dc - dw / 2
        S.box(f"Cubicle pilaster a{i}", CUBE_U - 0.0125, CUBE_U + 0.0125, ya, y_h + 0.005, 0.15, 2.05, M["cubicle"], 0.004)
        S.box(f"Cubicle pilaster b{i}", CUBE_U - 0.0125, CUBE_U + 0.0125, y_e - 0.005, yb, 0.15, 2.05, M["cubicle"], 0.004)
        S.box(f"Cubicle foot {i}", CUBE_U - 0.02, CUBE_U + 0.02, y_e - 0.01, y_e - 0.05, 0, 0.15, M["chrome"])
        occupied = i == 0
        hg = S.hinge(f"Cubicle door hinge {i}", CUBE_U, y_h, d=0, open_deg=0 if occupied else 62, along="y")
        _lb(c, hg, "Cubicle door", (dw - 0.01, 0.025, 1.88), M["cubicle"], (dw / 2, 0, 0.15 + 0.94), 0.004)
        for hz in (0.40, 1.70):
            _lc(c, hg, "Cubicle hinge", 0.009, 0.10, M["chrome"], (0.005, 0, hz), seg=10)
        led = M["led_red"] if occupied else M["led_green"]
        for side in (-1, 1):
            _lb(c, hg, "Cubicle lock body", (0.06, 0.012, 0.04), M["chrome"], (dw - 0.06, side * 0.018, 1.02), 0.003)
            _lb(c, hg, "Cubicle lock indicator", (0.035, 0.004, 0.012), led, (dw - 0.06, side * 0.025, 1.022))
            _lc(c, hg, "Cubicle lock turn", 0.012, 0.016, M["chrome"], (dw - 0.06, side * 0.032, 0.99), (90, 0, 0), seg=10)
        root = S.frame(f"WC {i}", WIDTH, dc, "-u")
        _toilet(S, root, abs(ya - yb) / 2 - 0.02, sanitary_bin=not S.spec["urinals"])

    # Sink counter + mirror on the partition wall
    root = S.frame("Restroom vanity", 0, -14.70, "+u")
    _vanity(S, root, 1.10, sinks=(-0.27, 0.27), powder=())
    # Hand dryer + bin on the shower wall's restroom face
    root = S.frame("Hand dryer", 1.85, yi, "-y")
    _hand_dryer(S, root)

    if S.spec["urinals"]:
        for i, u in enumerate((1.30, 2.00)):
            root = S.frame(f"Urinal {i}", u, Y_BACK, "+y")
            _urinal(S, root, i)
        for i, u in enumerate((0.95, 1.65, 2.35)):  # privacy screens
            S.box(f"Urinal screen {i}", u - 0.0125, u + 0.0125, Y_BACK, Y_BACK + 0.46, 0.42, 1.62, M["cubicle"], 0.006)

    S.box("SuiteCeiling linear light", 0.9, 2.4, -14.17, -14.25, CEIL - 0.006, CEIL, M["glow_cool"])
    _area_light(c, f"{S.tag} Restroom light", (S.x(WIDTH / 2), (yi + Y_BACK) / 2, CEIL - 0.05),
                WIDTH - 0.6, abs(Y_BACK - yi) - 0.5, 130, (0.96, 0.97, 1.0))


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
        out[spec["tag"]] = c
    _exterior(out["Women"])
    return out
