"""Gym ceiling & lighting detail pass (package key: gym_ceiling).

Adds exposed-services realism and lighting fixtures under the black gym slab (underside z = 3.59 m), around
the existing lime trusses, spiral duct, cassette ACs, recessed lenses and warm strips (none of them is moved).

Reference photos (work/refs/gym/...): 138 139 140 153 (black-painted exposed slab with conduits, black spiral
ducts, round downlights and black track spots washing the walls), 141 199 229 234 235 245 152 (suspended
linear LED profiles forming long lines and rectangular frames), 200 244 hall/031 (hanger rods, cable trays,
sprinkler mains with pendent heads, smoke detectors, cassette ACs), 146 149 151 201 203 205 206 238
(ceiling devices: smoke detectors, dome CCTVs, round ceiling speakers).

    import sys; sys.path.insert(0, "promo/tools")
    import detail_gym_ceiling; detail_gym_ceiling.apply()
"""
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True

KEY = "gym_ceiling"
COLL = "DETAIL_gym_ceiling"
P = "Dgym_ceiling_"

SLAB = 3.59          # ceiling underside (Ceiling object bottom)
GAP = 0.0015         # clearance kept between our parts and the slab / each other


# ------------------------------------------------------------------ helpers

def _mat(name, color, rough=0.5, metal=0.0, emit=0.0, emit_color=None):
    full = P + name
    m = bpy.data.materials.get(full)
    if m:
        return m
    m = bpy.data.materials.new(full)
    m.diffuse_color = (*color, 1)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*(emit_color or color), 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def _materials():
    return {
        # Painted-black services: same black as the slab but with a slight satin sheen so they read (138, 140).
        "paint": _mat("PaintedBlackSteel", (0.022, 0.022, 0.024), rough=0.48, metal=0.35),
        "pvc": _mat("BlackPVCCable", (0.012, 0.012, 0.013), rough=0.62),
        "grey_cable": _mat("GreyPVCCable", (0.16, 0.16, 0.15), rough=0.6),
        "rod": _mat("ZincThreadedRod", (0.42, 0.43, 0.44), rough=0.42, metal=0.9),
        "duct": _mat("BlackSpiralDuct", (0.03, 0.031, 0.034), rough=0.42, metal=0.55),
        "duct_in": _mat("DuctInterior", (0.005, 0.005, 0.006), rough=0.9),
        "sprk_pipe": _mat("SprinklerPipeBlack", (0.024, 0.022, 0.022), rough=0.45, metal=0.4),
        "brass": _mat("SprinklerBrass", (0.62, 0.45, 0.20), rough=0.32, metal=1.0),
        "bulb": _mat("SprinklerBulbRed", (0.75, 0.05, 0.03), rough=0.1, emit=0.0),
        "alu": _mat("AnodisedBlackAlu", (0.018, 0.018, 0.02), rough=0.32, metal=0.85),
        "diffuser": _mat("LEDOpalDiffuser", (0.9, 0.88, 0.84), rough=0.4, emit=9.0, emit_color=(1.0, 0.93, 0.84)),
        "spot_lens": _mat("SpotLensWarm", (0.95, 0.85, 0.7), rough=0.2, emit=14.0, emit_color=(1.0, 0.82, 0.6)),
        "white": _mat("DeviceOffWhite", (0.78, 0.78, 0.76), rough=0.45),
        "smoked": _mat("SmokedDome", (0.01, 0.01, 0.012), rough=0.06, metal=0.3),
        "grille": _mat("SpeakerGrille", (0.03, 0.03, 0.032), rough=0.55, metal=0.6),
        "led_red": _mat("DetectorLED", (0.9, 0.05, 0.03), emit=3.0),
    }


class Mesh:
    """Accumulates primitives into one bmesh, so every run of parts is a single object."""

    def __init__(self):
        self.bm = bmesh.new()

    def box(self, c, size, rot=None):
        g = bmesh.ops.create_cube(self.bm, size=1.0)
        vs = g["verts"]
        bmesh.ops.scale(self.bm, vec=Vector(size), verts=vs)
        if rot is not None:
            bmesh.ops.transform(self.bm, matrix=rot, verts=vs)
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=vs)
        for f in {f for v in vs for f in v.link_faces}:
            f.smooth = False
        return vs

    def cyl(self, p0, p1, r, seg=12, r2=None, smooth=True, caps=True):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        g = bmesh.ops.create_cone(self.bm, cap_ends=caps, segments=seg, radius1=r,
                                  radius2=r if r2 is None else r2, depth=d.length)
        vs = g["verts"]
        q = d.normalized().to_track_quat("Z", "Y")
        m = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
        bmesh.ops.transform(self.bm, matrix=m, verts=vs)
        axis = d.normalized()
        for f in {f for v in vs for f in v.link_faces}:
            f.smooth = smooth and abs(f.normal.dot(axis)) < 0.5
        return vs

    def sphere_cap(self, c, r, seg=16, rings=5, z_scale=1.0):
        """Lower hemisphere (dome) hanging below c."""
        g = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings * 2, radius=r)
        vs = g["verts"]
        top = [v for v in vs if v.co.z > 1e-5]
        bmesh.ops.delete(self.bm, geom=top, context="VERTS")
        vs = [v for v in g["verts"] if v.is_valid]
        for v in vs:
            v.co.z *= z_scale
            v.co += Vector(c)
        for f in {f for v in vs for f in v.link_faces}:
            f.smooth = True
        return vs

    def build(self, name, material, coll, bevel=0.0):
        me = bpy.data.meshes.new(P + name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-6)
        self.bm.normal_update()
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        me.materials.append(material)
        ob = bpy.data.objects.new(P + name, me)
        coll.objects.link(ob)
        if bevel:
            b = ob.modifiers.new("Bevel", "BEVEL")
            b.width = bevel
            b.segments = 1
            b.limit_method = "ANGLE"
            b.angle_limit = math.radians(40)
            b.harden_normals = False
        return ob


def _light(coll, name, kind, loc, energy, color, rot=None, **kw):
    lt = bpy.data.lights.new(P + name, kind)
    lt.energy = energy
    lt.color = color
    for k, v in kw.items():
        setattr(lt, k, v)
    ob = bpy.data.objects.new(P + name, lt)
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    coll.objects.link(ob)
    return ob


def _rod(m, x, y, z_bottom, r=0.005):
    m.cyl((x, y, z_bottom), (x, y, SLAB - GAP), r, seg=6)


# ------------------------------------------------------------------ 1. exposed services

def build_conduits(coll, M):
    """25 mm EMT conduits painted with the ceiling, saddle clips and junction boxes (138, 140, 031)."""
    pipe, clips = Mesh(), Mesh()
    r = 0.0115
    zc = SLAB - 0.014 - r  # clips hold the tube 14 mm off the slab
    for y in (-5.95, -2.52, 2.20, 4.18):
        pipe.cyl((-7.38, y, zc), (13.38, y, zc), r, seg=10)
        x = -7.0
        while x < 13.3:
            # saddle strap: two feet on the slab + bridge over the tube
            clips.box((x, y, SLAB - GAP - 0.007), (0.02, 0.05, 0.0035 + 0.011))
            x += 1.2
        for x in (-5.2, -0.4, 4.4, 9.2, 12.6):
            clips.box((x, y, SLAB - GAP - 0.03), (0.10, 0.10, 0.06))           # 4" octagon box body
            clips.box((x, y, SLAB - GAP - 0.062), (0.112, 0.112, 0.004))       # cover plate
    a = pipe.build("Conduits", M["paint"], coll)
    b = clips.build("ConduitBoxesClips", M["paint"], coll, bevel=0.002)
    return [a, b]


def build_cable_tray(coll, M):
    """Ladder cable tray along the left wall, hung on threaded rods with trapeze channels (031, 200)."""
    tray, rods = Mesh(), Mesh()
    cables = {"pvc": Mesh(), "grey": Mesh()}
    x0, w = -7.15, 0.30
    y0, y1 = -6.45, 4.75
    zb = 3.36                    # rung top / cable bed
    L = y1 - y0
    yc = (y0 + y1) / 2
    for sx in (-1, 1):           # C side rails 60 mm tall
        x = x0 + sx * (w / 2)
        tray.box((x, yc, zb + 0.027), (0.004, L, 0.06))
        tray.box((x - sx * 0.008, yc, zb + 0.055), (0.016, L, 0.004))
        tray.box((x - sx * 0.008, yc, zb - 0.001), (0.016, L, 0.004))
    y = y0 + 0.15
    while y < y1:
        tray.box((x0, y, zb - 0.006), (w - 0.012, 0.025, 0.010))
        y += 0.30
    y = y0 + 0.6
    while y < y1:
        tray.box((x0, y, zb - 0.032), (w + 0.10, 0.041, 0.041))   # unistrut trapeze under the tray
        for sx in (-1, 1):
            _rod(rods, x0 + sx * (w / 2 + 0.035), y, zb - 0.052)
        y += 1.5
    for dx, r, mk in (((-0.10, 0.011, "pvc"), (-0.07, 0.009, "pvc"), (-0.045, 0.012, "grey"),
                                     (-0.015, 0.008, "pvc"), (0.02, 0.010, "grey"), (0.06, 0.013, "pvc"),
                                     (0.095, 0.008, "pvc"))):
        z = zb + r + 0.0005
        cables[mk].cyl((x0 + dx, y0 + 0.02, z), (x0 + dx, y1 - 0.02, z), r, seg=8)
    out = [tray.build("CableTray", M["paint"], coll, bevel=0.0015),
           rods.build("CableTrayRods", M["rod"], coll)]
    out.append(cables["pvc"].build("CableTrayCablesBlack", M["pvc"], coll))
    out.append(cables["grey"].build("CableTrayCablesGrey", M["grey_cable"], coll))
    return out


def build_sprinkler_main(coll, M):
    """50A black sprinkler branch line with pendent heads on drops and clevis hangers (140, 031)."""
    pipe, heads, rods, bulbs = Mesh(), Mesh(), Mesh(), Mesh()
    y, z, r = -1.25, 3.43, 0.0305
    x0, x1 = -7.30, 13.30
    pipe.cyl((x0, y, z), (x1, y, z), r, seg=14)
    pipe.cyl((x0 - 0.002, y, z), (x0 + 0.04, y, z), r + 0.006, seg=14)  # end cap
    for x in (-6.0, -3.0, 0.0, 3.0, 6.0, 9.0, 12.0):
        pipe.cyl((x - 0.02, y, z), (x + 0.02, y, z), r + 0.009, seg=14)  # clevis ring
        _rod(rods, x, y, z + r + 0.008, r=0.0048)
    for x in (-5.4, -2.2, 0.6, 3.8, 7.0, 10.2, 12.7):
        pipe.cyl((x, y, z - r + 0.004), (x, y, z - 0.105), 0.0135, seg=10)       # 25A drop nipple
        pipe.cyl((x, y, z - 0.035), (x, y, z - 0.05), 0.0175, seg=10)           # tee/reducer collar
        heads.cyl((x, y, z - 0.105), (x, y, z - 0.118), 0.011, seg=10)          # head body
        for a in (0, 180):                                                       # frame arms
            ca = math.radians(a)
            heads.cyl((x + 0.008 * math.cos(ca), y + 0.008 * math.sin(ca), z - 0.118),
                      (x + 0.008 * math.cos(ca), y + 0.008 * math.sin(ca), z - 0.150), 0.0022, seg=6)
        heads.cyl((x, y, z - 0.150), (x, y, z - 0.153), 0.018, seg=14)          # deflector
        bulbs.cyl((x, y, z - 0.119), (x, y, z - 0.147), 0.0022, seg=6)          # red glass bulb
    return [pipe.build("SprinklerMain", M["sprk_pipe"], coll),
            heads.build("SprinklerPendents", M["brass"], coll),
            bulbs.build("SprinklerBulbs", M["bulb"], coll),
            rods.build("SprinklerHangerRods", M["rod"], coll)]


def build_second_duct(coll, M):
    """Smaller 220 mm black spiral duct run with couplers, straps and round side diffusers (138, 139, 153)."""
    duct, rings, rods, holes = Mesh(), Mesh(), Mesh(), Mesh()
    y, z, r = -2.20, 3.365, 0.11
    x0, x1 = -6.6, 12.6
    duct.cyl((x0, y, z), (x1, y, z), r, seg=28)
    for xe in (x0, x1):  # end caps (slightly larger)
        s = 1 if xe == x1 else -1
        rings.cyl((xe - s * 0.03, y, z), (xe + s * 0.002, y, z), r + 0.006, seg=28)
    x = x0 + 1.5
    while x < x1:
        rings.cyl((x - 0.018, y, z), (x + 0.018, y, z), r + 0.007, seg=28)
        x += 3.0
    for x in (-5.4, -2.4, 3.0, 6.0, 9.0, 11.8):   # strap + 2 rods (truss zone x -0.9..2.0 left alone)
        rings.cyl((x - 0.013, y, z), (x + 0.013, y, z), r + 0.004, seg=28)
        for dy in (-1, 1):
            _rod(rods, x, y + dy * (r + 0.012), z, r=0.005)
            rings.box((x, y + dy * (r + 0.012), z), (0.026, 0.012, 0.02))
    for x in (-4.0, 0.5, 4.5, 7.5, 10.5):          # side diffusers angled down toward both sides
        for side in (-1, 1):
            ang = math.radians(50)
            d = Vector((0, side * math.sin(ang), -math.cos(ang)))
            base = Vector((x, y, z)) + d * (r - 0.02)
            tip = base + d * 0.09
            rings.cyl(base, tip, 0.055, seg=18)
            holes.cyl(tip - d * 0.004, tip + d * 0.0015, 0.047, seg=18)
    return [duct.build("SpiralDuct2", M["duct"], coll),
            rings.build("SpiralDuct2Fittings", M["duct"], coll),
            holes.build("SpiralDuct2Openings", M["duct_in"], coll),
            rods.build("SpiralDuct2Rods", M["rod"], coll)]


# ------------------------------------------------------------------ 2. lighting

FRAMES = (  # (x0, x1, y0, y1) suspended LED profile rectangles (229, 234, 235, 199)
    (-6.8, -2.2, -3.30, -1.00),
    (2.8, 9.6, -3.30, -1.00),
    (-6.8, -2.2, 1.10, 2.45),
    (2.8, 9.6, 1.10, 2.45),
)
FRAME_Z = 3.06           # profile centre height
PW, PH = 0.05, 0.07      # 50 x 70 mm aluminium profile


def build_led_frames(coll, M):
    housing, diff, wires = Mesh(), Mesh(), Mesh()
    lights = []
    zc = FRAME_Z
    zb = zc - PH / 2
    col = (1.0, 0.93, 0.84)  # ~4000 K
    for i, (x0, x1, y0, y1) in enumerate(FRAMES):
        segs = []
        for y in (y0, y1):   # long sides run full length, short sides butt between them
            segs.append(((x0 + x1) / 2, y, x1 - x0 + PW, "x"))
        for x in (x0, x1):
            segs.append((x, (y0 + y1) / 2, y1 - y0 - PW, "y"))
        for j, (cx, cy, L, ax) in enumerate(segs):
            size = (L, PW, PH) if ax == "x" else (PW, L, PH)
            housing.box((cx, cy, zc), size)
            # opal lens inset 5 mm each side; long-side lenses stop short of the corners, short ones butt them
            dsize = (L - 0.012, PW - 0.010, 0.004) if ax == "x" else (PW - 0.010, L - 0.002, 0.004)
            diff.box((cx, cy, zb - 0.0018), dsize)
            ls = (L, 0.045) if ax == "x" else (0.045, L)
            lights.append(_light(coll, f"LEDFrame{i}_{j}", "AREA", (cx, cy, zb - 0.006), energy=17.0 * L,
                                 color=col, shape="RECTANGLE", size=ls[0], size_y=ls[1],
                                 specular_factor=0.5, use_shadow=True))
        # aircraft-cable suspension with ceiling canopies, inset from corners and ~1.7 m apart
        pts = []
        for y in (y0, y1):
            n = max(2, round((x1 - x0) / 1.7) + 1)
            for k in range(n):
                pts.append((x0 + 0.2 + (x1 - x0 - 0.4) * k / (n - 1), y))
        for x, y in pts:
            if abs(x - (-4.42)) < 0.12:       # keep clear of the yellow Pipe_Left
                x += 0.25
            wires.cyl((x, y, zc + PH / 2), (x, y, SLAB - 0.014), 0.0012, seg=5)
            wires.cyl((x, y, SLAB - 0.014), (x, y, SLAB - GAP), 0.022, seg=16)       # canopy
            wires.cyl((x, y, zc + PH / 2 + 0.0005), (x, y, zc + PH / 2 + 0.03), 0.006, seg=8)  # gripper
        # power feed: black cord from one corner to the nearest canopy
        fx, fy = x0 + 0.2, y0
        wires.cyl((fx + 0.05, fy, zc + PH / 2), (fx + 0.05, fy, SLAB - GAP), 0.0035, seg=6)
    return [housing.build("LEDProfileHousings", M["alu"], coll, bevel=0.002),
            diff.build("LEDProfileDiffusers", M["diffuser"], coll),
            wires.build("LEDSuspension", M["alu"], coll)] , lights


def build_track_spots(coll, M):
    """Black 3-circuit tracks with cylinder spots washing the mirror wall and the front wall (138, 139, 234)."""
    track, heads, lenses = Mesh(), Mesh(), Mesh()
    lights = []
    runs = (
        # y, x0, x1, wall direction (+1 back/mirror wall, -1 front wall), spot xs
        (4.42, -2.45, 13.15, 1, (-2.0, 2.6, 4.1, 5.6, 7.1, 8.6, 10.1, 12.4)),
        (-6.32, -3.6, 13.15, -1, (-3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0, 7.5, 9.0, 10.5, 12.0)),
    )
    for y, x0, x1, wd, xs in runs:
        track.box(((x0 + x1) / 2, y, SLAB - GAP - 0.017), (x1 - x0, 0.036, 0.034))
        for xe in (x0, x1):
            track.box((xe, y, SLAB - GAP - 0.017), (0.012, 0.04, 0.036))
        for x in xs:
            zt = SLAB - GAP - 0.034
            heads.box((x, y, zt - 0.025), (0.05, 0.034, 0.05))                    # adapter/driver
            heads.cyl((x, y, zt - 0.05), (x, y, zt - 0.10), 0.006, seg=8)          # stem
            tilt = math.radians(32)
            d = Vector((0, wd * math.sin(tilt), -math.cos(tilt)))
            c = Vector((x, y, zt - 0.10)) + d * 0.02
            back = c - d * 0.07
            front = c + d * 0.08
            heads.cyl(back, front, 0.040, seg=18)                                  # cylinder head
            heads.cyl(front - d * 0.012, front + d * 0.0, 0.043, seg=18)          # front ring
            lenses.cyl(front - d * 0.016, front - d * 0.0115, 0.034, seg=18)      # recessed lens
            rot = d.to_track_quat("-Z", "Y").to_euler()
            lights.append(_light(coll, f"TrackSpot_{'B' if wd > 0 else 'F'}{x:+.1f}", "SPOT",
                                 tuple(front + d * 0.003), energy=55.0, color=(1.0, 0.84, 0.66), rot=rot,
                                 spot_size=math.radians(38), spot_blend=0.45, shadow_soft_size=0.03,
                                 use_shadow=True))
    return [track.build("TrackRails", M["alu"], coll, bevel=0.0015),
            heads.build("TrackSpotHeads", M["alu"], coll),
            lenses.build("TrackSpotLenses", M["spot_lens"], coll)], lights


# ------------------------------------------------------------------ 3. ceiling devices

SMOKE = ((-5.0, -4.6), (3.2, -4.6), (8.0, -4.6), (12.0, -4.6), (-3.8, -0.45), (5.5, -0.45), (12.2, -0.45),
         (-5.6, 1.85), (4.0, 1.75), (9.6, 1.75), (-5.6, 4.6), (7.7, 4.0))
DOMES = ((-6.6, -4.6), (12.6, 4.0), (6.0, -5.7), (-6.6, 4.1))
SPEAKERS = ((-3.0, -4.6), (5.6, -4.65), (10.2, -4.6), (-3.6, 0.2), (12.3, 0.2), (3.3, 4.0), (7.0, 3.95))


def build_devices(coll, M):
    white, dark, grille, led = Mesh(), Mesh(), Mesh(), Mesh()
    top = SLAB - GAP
    for x, y in SMOKE:   # photoelectric detector: base plate + 100 mm head + vent ring
        white.cyl((x, y, top), (x, y, top - 0.012), 0.062, seg=24)
        white.cyl((x, y, top - 0.012), (x, y, top - 0.040), 0.050, r2=0.046, seg=24)
        dark.cyl((x, y, top - 0.020), (x, y, top - 0.032), 0.0505, seg=24, smooth=True, caps=False)
        led.cyl((x + 0.03, y, top - 0.040), (x + 0.03, y, top - 0.0425), 0.004, seg=8)
    for x, y in DOMES:    # mini dome CCTV: white trim ring + smoked bubble
        white.cyl((x, y, top), (x, y, top - 0.035), 0.065, r2=0.060, seg=28)
        dark.sphere_cap((x, y, top - 0.035), 0.048, seg=20, rings=5, z_scale=0.9)
    for x, y in SPEAKERS:  # surface ceiling speaker: black can + perforated grille face
        dark.cyl((x, y, top), (x, y, top - 0.075), 0.105, r2=0.10, seg=28)
        grille.cyl((x, y, top - 0.075), (x, y, top - 0.079), 0.092, seg=28)
        dark.cyl((x, y, top - 0.079), (x, y, top - 0.081), 0.02, seg=12)
    return [white.build("DevicesWhite", M["white"], coll),
            dark.build("DevicesDark", M["smoked"], coll),
            grille.build("SpeakerGrilles", M["grille"], coll),
            led.build("DetectorLEDs", M["led_red"], coll)]


# ------------------------------------------------------------------ entry point

def _clear(coll):
    for ob in list(coll.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)


def apply() -> dict:
    set_coll = bpy.data.collections["SET"]
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        set_coll.children.link(coll)
    elif coll.name not in set_coll.children:
        set_coll.children.link(coll)
    _clear(coll)
    M = _materials()

    meshes = []
    meshes += build_conduits(coll, M)
    meshes += build_cable_tray(coll, M)
    meshes += build_sprinkler_main(coll, M)
    meshes += build_second_duct(coll, M)
    frames, lights_a = build_led_frames(coll, M)
    meshes += frames
    spots, lights_b = build_track_spots(coll, M)
    meshes += spots
    meshes += build_devices(coll, M)
    for ob in coll.objects:
        ob["detail_pkg"] = KEY

    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        ev.to_mesh_clear()
    return {"collection": COLL, "objects_added": len(coll.objects), "mesh_objects": len(meshes),
            "lights_added": len(lights_a) + len(lights_b), "triangles_added": tris,
            "existing_objects_touched": []}
