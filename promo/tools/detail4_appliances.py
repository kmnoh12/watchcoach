"""detail4 P6 appliances: real-looking wall fans, desk fans and hair dryers.

The old props (hollow square wall fans, spoke-wheel desk fans, cylinder hair dryers) are hidden (render +
viewport), tagged `detail4_pkg = "appliances"` and their original visibility is stored in custom props.
New props are built at the same place and facing in collection DETAIL4_appliances (under SET):
- 16" wall fan: wall plate, tilt knuckle arm, motor housing, round wire guard (rings + radial wires front and
  rear), clear 3-blade rotor, rim band, blank centre badge, cord looping to a small wall outlet box
  (ref work/refs/interior/185, 128, 023, 031).
- 12" desk fan: round base, column with switch block, same head scaled (ref interior/037, 185).
- hair dryer: body with rear intake grille, flat concentrator nozzle, real-proportion handle, coiled cord,
  wall holster ring + back plate (ref interior/185 black dryers with cords).
Repeated shapes share mesh data (linked duplicates). No text or logos.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_appliances.py [-- --save out.blend]
"""
import json
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

KEY = "appliances"
COLL = "DETAIL4_appliances"
PFX = "D4ap_"

GYM_WALL_FANS = ["Dgym_life_Fan_Back", "Dgym_life_Fan_Front_A", "Dgym_life_Fan_Front_B", "Dgym_life_Fan_Left"]
LOCKER_WALL_FANS = ["Dgym_lockers_Men Wall fan", "Dgym_lockers_Women Wall fan"]   # empties (hide children)
DESK_FAN_PREFIX = "Dgym_lockers_Desk fan"
DRYER_PREFIXES = ("Hair dryer body", "Hair dryer handle", "Hair dryer nozzle", "Hair dryer cord",
                  "Dryer holster ring", "Dryer holster")


# ---------------------------------------------------------------- generic helpers
def _coll():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.data.collections["SET"].children.link(c)
    for ob in list(c.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in [m for m in bpy.data.meshes if m.name.startswith(PFX) and m.users == 0]:
        bpy.data.meshes.remove(me)
    return c


def _principled(name, base, rough, metal=0.0, coat=0.0, alpha=1.0, transmission=0.0, ior=1.45):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.name = "Principled BSDF"
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Alpha"].default_value = alpha
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
        m.use_backface_culling = False
    m.diffuse_color = (*base, alpha)
    m["detail4_pkg"] = KEY
    return m


def _mats():
    return {
        "abs": _principled(PFX + "WhiteABS", (0.80, 0.80, 0.78), 0.40, coat=0.1),
        "abs_grey": _principled(PFX + "GreyABS", (0.42, 0.43, 0.45), 0.42),
        "wire": _principled(PFX + "GuardWireWhite", (0.78, 0.78, 0.76), 0.35),
        "blade": _principled(PFX + "BladeClearBlue", (0.55, 0.72, 0.85), 0.18, alpha=0.55),
        "cord": _principled(PFX + "CordRubber", (0.025, 0.025, 0.027), 0.55),
        "cord_w": _principled(PFX + "CordWhite", (0.75, 0.75, 0.73), 0.50),
        "dryer": _principled(PFX + "DryerBlackGloss", (0.018, 0.018, 0.020), 0.28, coat=0.3),
        "dryer_grille": _principled(PFX + "DryerGrilleGrey", (0.10, 0.10, 0.11), 0.45),
        "steel": _principled(PFX + "HolsterSteel", (0.62, 0.63, 0.65), 0.30, metal=1.0),
        "switch": _principled(PFX + "SwitchGrey", (0.30, 0.31, 0.33), 0.45),
    }


def _bm_to_mesh(bm, name, mats, smooth_mats=None):
    me = bpy.data.meshes.new(name)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True if smooth_mats is None else (p.material_index in smooth_mats)
    me["detail4_pkg"] = KEY
    return me


def _obj(name, me, c, mw):
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.matrix_world = mw
    ob["detail4_pkg"] = KEY
    return ob


def _new_faces(bm, before, mat):
    nf = [f for f in bm.faces if f not in before]
    for f in nf:
        f.material_index = mat
    return nf


def _tube(bm, pts, r, sides=6, cyclic=False, mat=0, caps=True):
    before = set(bm.faces)
    pts = [Vector(p) for p in pts]
    n = len(pts)
    rings = []
    prev_u = None
    for i, p in enumerate(pts):
        if cyclic:
            t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        else:
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        if prev_u is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            u = t.cross(ref).normalized()
        else:   # parallel transport: keep the frame from twisting
            u = (prev_u - t * prev_u.dot(t)).normalized()
        v = t.cross(u).normalized()
        prev_u = u
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r)
                      for k in range(sides)])
    segs = n if cyclic else n - 1
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    if not cyclic and caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    _new_faces(bm, before, mat)


def _lathe(bm, prof, seg=32, mat=0, axis_mat=None):
    """Revolve (r, z) profile about +Z; optional 4x4 matrix applied after."""
    before = set(bm.faces)
    rings = []
    for r, z in prof:
        if r < 1e-7:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z))
                          for k in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for k in range(seg):
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[k], b[(k + 1) % seg]))
            elif len(b) == 1:
                bm.faces.new((a[k], a[(k + 1) % seg], b[0]))
            else:
                bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    nf = _new_faces(bm, before, mat)
    vs = list({v for f in nf for v in f.verts})
    if axis_mat is not None:
        bmesh.ops.transform(bm, matrix=axis_mat, verts=vs)
    return vs


def _rbox(bm, size, mw=Matrix(), bevel=0.003, mat=0):
    before = set(bm.faces)
    geom = bmesh.ops.create_cube(bm, size=1.0)
    vs = geom["verts"]
    bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
    if bevel > 0:
        edges = list({e for v in vs for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect="EDGES", profile=0.5)
    nf = _new_faces(bm, before, mat)
    vs = list({v for f in nf for v in f.verts})
    bmesh.ops.transform(bm, matrix=mw, verts=vs)
    return vs


# ---------------------------------------------------------------- fan head (axis +Z = blowing direction)
def _fan_head(bm, R, mi, blades=3):
    """Build guard radius R. z=0 is the tilt pivot; motor behind, guard in front. Returns guard front z."""
    s = R / 0.21
    # motor housing (rear, rounded can)
    _lathe(bm, [(0, 0.030 * s), (0.040 * s, 0.032 * s), (0.060 * s, 0.050 * s), (0.066 * s, 0.075 * s),
                (0.066 * s, 0.115 * s), (0.058 * s, 0.135 * s), (0.030 * s, 0.140 * s), (0, 0.140 * s)], 28, mi["abs"])
    # rear grille: shallow bowl around the motor front
    zr = 0.150 * s

    def rear_z(r):
        return zr + 0.035 * s * (r / R) ** 1.6

    # wires are 3-sided tubes (1.3-1.6 mm radius: the section is sub-pixel, caps are single triangles);
    # the rear grille faces the wall/motor, so it is sparser than the front
    for r in [R * f for f in (0.45, 0.68, 0.90)]:
        _tube(bm, [(r * math.cos(a), r * math.sin(a), rear_z(r)) for a in
                   [2 * math.pi * k / 32 for k in range(32)]], 0.0016 * s ** 0.5, 3, cyclic=True, mat=mi["wire"])
    for k in range(16):
        a = 2 * math.pi * (k + 0.5) / 16
        pts = [(r * math.cos(a), r * math.sin(a), rear_z(r)) for r in [R * f for f in (0.30, 0.55, 0.80, 0.99)]]
        _tube(bm, pts, 0.0014 * s ** 0.5, 3, mat=mi["wire"])
    # rear plate collar where the rear grille meets the motor
    _lathe(bm, [(0.060 * s, zr - 0.004 * s), (0.078 * s, zr - 0.002 * s), (0.078 * s, zr + 0.008 * s),
                (0.060 * s, zr + 0.010 * s), (0.060 * s, zr - 0.004 * s)], 28, mi["abs"])
    # rim band joining both guards
    z0, z1 = rear_z(R) - 0.004 * s, rear_z(R) + 0.050 * s
    _lathe(bm, [(R - 0.006 * s, z0), (R + 0.004 * s, z0 + 0.003 * s), (R + 0.006 * s, (z0 + z1) / 2),
                (R + 0.004 * s, z1 - 0.003 * s), (R - 0.006 * s, z1), (R - 0.004 * s, (z0 + z1) / 2),
                (R - 0.006 * s, z0)], 48, mi["abs"])
    # front grille: dome
    zf = z1 - 0.004 * s

    def front_z(r):
        return zf + 0.055 * s * (1 - (r / R) ** 2)

    for r in [R * f for f in (0.30, 0.43, 0.56, 0.69, 0.82, 0.93)]:
        _tube(bm, [(r * math.cos(a), r * math.sin(a), front_z(r)) for a in
                   [2 * math.pi * k / 40 for k in range(40)]], 0.0015 * s ** 0.5, 3, cyclic=True, mat=mi["wire"])
    for k in range(32):
        a = 2 * math.pi * k / 32
        twist = 0.18
        pts = [(r * math.cos(a + twist * r / R), r * math.sin(a + twist * r / R), front_z(r))
               for r in [R * f for f in (0.22, 0.42, 0.62, 0.80, 0.99)]]
        _tube(bm, pts, 0.0013 * s ** 0.5, 3, mat=mi["wire"])
    # blank centre badge on the front grille
    zb = front_z(0.0)
    _lathe(bm, [(0, zb + 0.006 * s), (0.040 * s, zb + 0.004 * s), (0.050 * s, zb - 0.002 * s),
                (0.050 * s, zb - 0.010 * s), (0, zb - 0.010 * s)], 32, mi["abs"])
    # rotor: spinner + blades, between the guards
    zh = rear_z(0.3 * R) + 0.026 * s
    _lathe(bm, [(0, zh - 0.022 * s), (0.034 * s, zh - 0.020 * s), (0.036 * s, zh), (0.028 * s, zh + 0.014 * s),
                (0, zh + 0.020 * s)], 24, mi["abs_grey"])
    for b in range(blades):
        a0 = 2 * math.pi * b / blades
        before = set(bm.faces)
        nr, na = 7, 6
        grid = []
        for i in range(nr):
            r = 0.032 * s + (R * 0.88 - 0.032 * s) * i / (nr - 1)
            half = math.radians(14 + 26 * (i / (nr - 1)) ** 0.8)      # wider towards the tip
            row = []
            for j in range(na):
                f = -1 + 2 * j / (na - 1)
                ang = a0 + half * f + 0.25 * (i / (nr - 1)) ** 2       # swept tip
                pitch = math.radians(28) * f
                z = zh + math.tan(pitch) * r * half * 0.45 - 0.002 * s
                row.append(Vector((r * math.cos(ang), r * math.sin(ang), z)))
            grid.append(row)
        top = [[bm.verts.new(p + Vector((0, 0, 0.0012))) for p in row] for row in grid]
        bot = [[bm.verts.new(p - Vector((0, 0, 0.0012))) for p in row] for row in grid]
        for i in range(nr - 1):
            for j in range(na - 1):
                bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]))
                bm.faces.new((bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]))
        for i in range(nr - 1):
            bm.faces.new((top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0]))
            bm.faces.new((top[i][-1], bot[i][-1], bot[i + 1][-1], top[i + 1][-1]))
        for j in range(na - 1):
            bm.faces.new((top[-1][j], top[-1][j + 1], bot[-1][j + 1], bot[-1][j]))
            bm.faces.new((top[0][j], bot[0][j], bot[0][j + 1], top[0][j + 1]))
        _new_faces(bm, before, mi["blade"])
    return front_z(0.0)


MI = {"abs": 0, "abs_grey": 1, "wire": 2, "blade": 3, "cord": 4, "switch": 5}


def _wall_fan_mesh(m):
    """Local frame: wall plane y=0, room towards -y, z=0 at the wall plate centre."""
    bm = bmesh.new()
    # wall plate + arm
    _rbox(bm, (0.090, 0.014, 0.150), Matrix.Translation((0, -0.007, 0.0)), bevel=0.005, mat=MI["abs"])
    _tube(bm, [(0, -0.012, 0.03), (0, -0.075, 0.03), (0, -0.115, 0.01)], 0.017, 12, mat=MI["abs"])
    # tilt knuckle (axis x)
    _lathe(bm, [(0, -0.028), (0.026, -0.028), (0.026, 0.028), (0, 0.028)], 20, MI["abs_grey"],
           axis_mat=Matrix.Translation((0, -0.130, 0.0)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    # head: +Z -> room (-y), tilted 16 deg down, pivot just in front of the knuckle
    tilt = Matrix.Translation((0, -0.150, -0.010)) @ Matrix.Rotation(math.radians(90 + 16), 4, "X")
    hb = bmesh.new()
    _fan_head(hb, 0.205, MI, blades=3)
    # yoke joining knuckle to motor
    _rbox(hb, (0.040, 0.030, 0.050), Matrix.Translation((0, -0.012, 0.030)), bevel=0.006, mat=MI["abs"])
    tmp = bpy.data.meshes.new("_tmp_head")
    hb.to_mesh(tmp)
    hb.free()
    tmp.transform(tilt)
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    # cord: leaves the motor underside, droops and goes into the bottom of the wall plate
    cord = [(0.018, -0.203, -0.088), (0.026, -0.196, -0.140), (0.034, -0.170, -0.195), (0.036, -0.120, -0.225),
            (0.032, -0.070, -0.215), (0.024, -0.035, -0.170), (0.016, -0.020, -0.110), (0.012, -0.016, -0.070)]
    _tube(bm, cord, 0.0035, 6, mat=MI["cord"])
    return _bm_to_mesh(bm, PFX + "WallFan16", [m["abs"], m["abs_grey"], m["wire"], m["blade"], m["cord_w"],
                                                  m["switch"]])


def _desk_fan_mesh(m, cord=None):
    """Local frame: base centre on the counter at origin, blowing towards -y."""
    bm = bmesh.new()
    _lathe(bm, [(0, 0.0005), (0.105, 0.0005), (0.110, 0.006), (0.104, 0.022), (0.060, 0.032), (0.022, 0.036),
                (0, 0.036)], 40, MI["abs"])
    _rbox(bm, (0.060, 0.040, 0.012), Matrix.Translation((0, -0.065, 0.026)) @ Matrix.Rotation(math.radians(-14), 4, "X"),
          bevel=0.003, mat=MI["switch"])                       # button strip on the base slope
    _lathe(bm, [(0, 0.034), (0.017, 0.034), (0.016, 0.180), (0.013, 0.300), (0, 0.300)], 20, MI["abs"])
    _lathe(bm, [(0, 0.29), (0.020, 0.29), (0.020, 0.33), (0, 0.33)], 20, MI["abs_grey"],
           axis_mat=Matrix.Translation((0, 0.0, 0.0)))
    tilt = Matrix.Translation((0, -0.012, 0.335)) @ Matrix.Rotation(math.radians(90 - 4), 4, "X")
    hb = bmesh.new()
    _fan_head(hb, 0.150, MI, blades=5)
    _rbox(hb, (0.036, 0.040, 0.040), Matrix.Translation((0, -0.018, 0.022)), bevel=0.006, mat=MI["abs"])
    tmp = bpy.data.meshes.new("_tmp_dhead")
    hb.to_mesh(tmp)
    hb.free()
    tmp.transform(tilt)
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    # cord leaving the back of the base towards the wall (path given in local coordinates)
    cord = cord or [(0, 0.095, 0.010), (0.01, 0.16, 0.0035), (0.03, 0.25, 0.0035), (0.035, 0.293, 0.0035)]
    _tube(bm, cord, 0.0030, 6, mat=MI["cord"])
    return _bm_to_mesh(bm, PFX + "DeskFan12", [m["abs"], m["abs_grey"], m["wire"], m["blade"], m["cord_w"],
                                                  m["switch"]])


DESK_WALL = 0.25           # desk fan base centre from the wall
DESK_END = 0.21            # ... and from the counter end
DESK_YAW = 55.0            # turned from facing the room towards the entrance (deg)
RING_R = 0.031             # holster ring radius (tube 4 mm -> 27 mm clear for the 20 mm handle)
RING_OFF = 0.110          # holster ring centre distance from the wall
DRYER_Z = 0.012           # dryer origin above the ring centre


def _dryer_mesh(m, counter_z, ring_off=RING_OFF):
    """Local frame: handle axis = z, handle grip centre at origin (in the holster ring), nozzle towards -y."""
    bm = bmesh.new()
    DI = {"body": 0, "grille": 1, "cord": 2, "switch": 3}
    zb = 0.105                     # body axis height above the ring centre
    body = Matrix.Translation((0, 0.0, zb)) @ Matrix.Rotation(math.pi / 2, 4, "X")   # +Z -> -y
    # body (axis along -y): rear intake at +y, nozzle at -y
    _lathe(bm, [(0, -0.085), (0.034, -0.085), (0.042, -0.075), (0.046, -0.050), (0.046, 0.040), (0.042, 0.060),
                (0.035, 0.068), (0, 0.068)], 32, DI["body"], axis_mat=body)
    # rear intake grille disk (slightly recessed ring + mesh disc)
    _lathe(bm, [(0, -0.0875), (0.030, -0.0875), (0.030, -0.0865), (0, -0.0865)], 32, DI["grille"], axis_mat=body)
    for r in (0.010, 0.018, 0.026):
        _tube(bm, [body @ Vector((r * math.cos(a), r * math.sin(a), -0.0885)) for a in
                   [2 * math.pi * k / 24 for k in range(24)]], 0.0012, 4, cyclic=True, mat=DI["body"])
    # concentrator nozzle: round-to-flat
    nz = []
    for i, (z, w, h) in enumerate([(0.068, 0.035, 0.035), (0.090, 0.040, 0.024), (0.112, 0.045, 0.012)]):
        ring = []
        for k in range(24):
            a = 2 * math.pi * k / 24
            ring.append(bm.verts.new(body @ Vector((w * math.cos(a), h * math.sin(a), z))))
        nz.append(ring)
    before = set(bm.faces)
    for a, b in zip(nz, nz[1:]):
        for k in range(24):
            bm.faces.new((a[k], a[(k + 1) % 24], b[(k + 1) % 24], b[k]))
    inner = [bm.verts.new(body @ Vector((0.040 * math.cos(2 * math.pi * k / 24), 0.008 * math.sin(2 * math.pi * k / 24), 0.111)))
             for k in range(24)]
    for k in range(24):
        bm.faces.new((nz[-1][k], inner[k], inner[(k + 1) % 24], nz[-1][(k + 1) % 24]))
    bm.faces.new(list(reversed(inner)))
    _new_faces(bm, before, DI["grille"])
    # handle: tapered, leaning 8 deg forward, rounded end
    hand = Matrix.Translation((0, -0.002, 0.0)) @ Matrix.Rotation(math.radians(-8), 4, "X")
    _lathe(bm, [(0, -0.075), (0.012, -0.074), (0.017, -0.066), (0.0185, -0.010), (0.020, 0.045), (0.024, 0.075),
                (0, 0.075)], 20, DI["body"], axis_mat=hand)
    _rbox(bm, (0.012, 0.010, 0.036), hand @ Matrix.Translation((0, -0.0195, 0.022)), bevel=0.003, mat=DI["switch"])
    # coiled cord: strain relief, helix, then towards the wall outlet (+y) and down
    _lathe(bm, [(0, -0.095), (0.006, -0.095), (0.010, -0.075), (0, -0.075)], 12, DI["grille"], axis_mat=hand)
    base = hand @ Vector((0, 0, -0.095))
    zc = counter_z + 0.0032                     # cord centre resting on the counter
    pts = [base]
    turns, rad = 3, 0.010
    drop = base.z - (zc + 0.016)
    for k in range(1, turns * 12 + 1):
        a = 2 * math.pi * k / 12
        pts.append(base + Vector((rad * math.cos(a) - rad, rad * math.sin(a), -drop * k / (turns * 12))))
    e = pts[-1]
    pts += [Vector((e.x + 0.004, e.y + 0.012, zc + 0.004)), Vector((e.x + 0.010, e.y + 0.035, zc)),
            Vector((0.022, ring_off * 0.55, zc)), Vector((0.030, ring_off - 0.0035, zc)),
            Vector((0.030, ring_off - 0.0035, zc + 0.030))]
    _tube(bm, pts, 0.0028, 6, mat=DI["cord"])
    return _bm_to_mesh(bm, PFX + "HairDryer", [m["dryer"], m["dryer_grille"], m["cord"], m["switch"]])


def _holster_mesh(m, ring_off=RING_OFF):
    """Wall holster: back plate on the wall (y=0, room -y), arm and ring (centre at -ring_off) for the handle."""
    bm = bmesh.new()
    _rbox(bm, (0.060, 0.008, 0.090), Matrix.Translation((0, -0.004, -0.010)), bevel=0.003, mat=0)
    arm_len = ring_off - RING_R - 0.006
    _rbox(bm, (0.022, arm_len, 0.012), Matrix.Translation((0, -0.008 - arm_len / 2 + 0.001, -0.004)), bevel=0.003, mat=0)
    ring = [(RING_R * math.cos(2 * math.pi * k / 32), -ring_off + RING_R * math.sin(2 * math.pi * k / 32), 0.0)
            for k in range(32)]
    _tube(bm, ring, 0.004, 8, cyclic=True, mat=0)
    return _bm_to_mesh(bm, PFX + "DryerHolster", [m["steel"]])


# ---------------------------------------------------------------- hide old props
def _hide(ob, hidden):
    if "detail4_orig_hide_render" not in ob:
        ob["detail4_orig_hide_render"] = ob.hide_render
        ob["detail4_orig_hide_viewport"] = ob.hide_viewport
    ob["detail4_pkg"] = KEY
    ob.hide_render = True
    ob.hide_viewport = True
    hidden.append(ob.name)


def _mw(o):
    """World matrix rebuilt from the parent chain. The old props this module reads are hidden from the viewport
    (by this module, or in a scene saved after it ran), and Blender does not refresh matrix_world for objects
    outside the depsgraph, so their stored matrix_world can be stale."""
    if o.parent is None:
        return o.matrix_basis.copy()
    return _mw(o.parent) @ o.matrix_parent_inverse @ o.matrix_basis


def _wbb(objs):
    cs = [_mw(o) @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector([min(c[i] for c in cs) for i in range(3)]), Vector([max(c[i] for c in cs) for i in range(3)]))


def _yaw_to(f):
    """Rotation about Z that maps local -y to the horizontal direction f."""
    return Matrix.Rotation(math.atan2(f.x, -f.y), 4, "Z")


def apply() -> dict:
    c = _coll()
    m = _mats()
    hidden = []
    placed = []
    wall_fan = _wall_fan_mesh(m)
    vt = bpy.data.objects.get("Vanity top")
    counter_z = _wbb([vt])[1].z if vt else 0.817
    holster = _holster_mesh(m)

    # gym wall fans: object frame already has the wall at local y=0 and the room at -y
    for name in GYM_WALL_FANS:
        old = bpy.data.objects.get(name)
        if old is None:
            continue
        lo, hi = _wbb([old])
        mw = _mw(old)
        rot = mw.to_3x3().normalized().to_4x4()
        wall = mw.translation.copy()
        mw_new = Matrix.Translation(wall) @ rot @ Matrix.Translation((0, -0.001, 0))   # old origin = bracket
        _hide(old, hidden)
        placed.append(_obj(f"{PFX}WallFan_{name[len('Dgym_life_Fan_'):]}", wall_fan, c, mw_new).name)

    # locker wall fans (empty + children)
    for name in LOCKER_WALL_FANS:
        root = bpy.data.objects.get(name)
        if root is None:
            continue
        kids = [o for o in root.children_recursive if o.type == "MESH"]
        bracket = next((o for o in kids if "bracket" in o.name), None)
        motor = next((o for o in kids if "motor" in o.name), None)
        cage = [o for o in kids if "cage" in o.name and "wire" not in o.name]
        if bracket is None or motor is None:
            continue
        blo, bhi = _wbb([bracket])
        f = (_wbb(cage)[0] + _wbb(cage)[1]) / 2 - _mw(motor).translation
        f.z = 0
        f.normalize()
        # wall plane = bracket back face
        wall_pt = Vector(((blo.x + bhi.x) / 2, (blo.y + bhi.y) / 2, (blo.z + bhi.z) / 2))
        wall_pt -= f * (abs(f.dot(bhi - blo)) / 2)
        for o in kids:
            _hide(o, hidden)
        mw_new = Matrix.Translation(wall_pt + f * 0.001) @ _yaw_to(f)
        placed.append(_obj(f"{PFX}WallFan_{name.split()[0].split('_')[-1]}Locker", wall_fan, c, mw_new).name)

    # desk fans: one per vanity. The real 12" fan is much bigger than the old prop, and on the old spot (front edge,
    # end of the counter nearest the entrance) it hid the amenity tray from the locker-room view. It now stands on
    # the same vanity end, against the wall (base 0.25 m from the wall, 0.21 m from the end), turned 55 deg from the
    # room towards the entrance. Probe: amenity rays from the men_locker camera hidden 70/74 -> 2/74, no overlaps.
    holsters = [o for o in bpy.data.objects if o.name.startswith("Dryer holster") and "ring" not in o.name]
    tops = [o for o in bpy.data.objects if o.name.startswith("Vanity top")]
    desk_meshes = {}
    bases = [o for o in bpy.data.objects if o.name.startswith(DESK_FAN_PREFIX + " base")]
    for base in bases:
        parent = base.parent
        group = [o for o in bpy.data.objects if o.name.startswith(DESK_FAN_PREFIX) and o.parent == parent]
        lo, hi = _wbb([base])
        bc = (lo + hi) / 2
        top = next(t for t in tops if _wbb([t])[0].x <= bc.x <= _wbb([t])[1].x and _wbb([t])[0].y <= bc.y <= _wbb([t])[1].y)
        tlo, thi = _wbb([top])
        tc = (tlo + thi) / 2
        hx = [_mw(o).translation.x for o in holsters if tlo.y <= _mw(o).translation.y <= thi.y
              and abs(_mw(o).translation.x - tc.x) < 0.6]
        sx = 1.0 if sum(hx) / len(hx) > tc.x else -1.0          # towards the wall (holsters hang on it)
        sy = 1.0 if bc.y > tc.y else -1.0                         # towards the counter end the old fan stood at
        wall_x = thi.x if sx > 0 else tlo.x
        end_y = thi.y if sy > 0 else tlo.y
        pos = Vector((wall_x - sx * DESK_WALL, end_y - sy * DESK_END, thi.z + 0.0005))
        a = math.radians(DESK_YAW)
        f = Vector((-sx * math.cos(a), sy * math.sin(a), 0.0))
        rot = _yaw_to(f)
        w = rot.inverted().to_3x3() @ Vector((sx, 0.0, 0.0))     # wall direction in the fan's local frame
        p1 = Vector((0.0, 0.15, 0.0035))
        run = (DESK_WALL - 0.002) - p1.dot(w)
        cord = [Vector((0.0, 0.095, 0.010)), p1, p1 + w * (run * 0.5) + Vector((0, 0.01, 0)), p1 + w * run]
        key = tuple(round(v, 4) for p in cord for v in p)
        desk = desk_meshes.setdefault(key, _desk_fan_mesh(m, [tuple(p) for p in cord]))
        for o in group:
            _hide(o, hidden)
        side = "Men" if "Men" in parent.name else "Women"
        placed.append(_obj(f"{PFX}DeskFan_{side}", desk, c, Matrix.Translation(pos) @ rot).name)

    # hair dryers + holsters
    dryers = {}
    for body in [o for o in bpy.data.objects if o.name.startswith("Hair dryer body")]:
        suffix = body.name[len("Hair dryer body"):]
        parts = {p: bpy.data.objects.get(p + suffix) for p in DRYER_PREFIXES}
        if any(v is None for v in parts.values()):
            continue
        ring = parts["Dryer holster ring"]
        plate = parts["Dryer holster"]
        nozzle = parts["Hair dryer nozzle"]
        rc = _mw(ring).translation.copy()
        f = _mw(nozzle).translation - _mw(body).translation
        f.z = 0
        f.normalize()                                  # nozzle direction
        plo, phi = _wbb([plate])
        # wall: the far side of the old holster plate, opposite to the nozzle direction
        to_wall = -f
        wall_d = max((Vector(c) - rc).dot(to_wall) for c in (plo, phi, Vector((plo.x, phi.y, 0)), Vector((phi.x, plo.y, 0))))
        wall_pt = rc + to_wall * wall_d
        wall_pt.z = rc.z
        for o in parts.values():
            _hide(o, hidden)
        yaw = _yaw_to(f)
        ring_c = wall_pt + f * RING_OFF
        dryer = dryers.setdefault(round(ring_c.z, 4), _dryer_mesh(m, counter_z - (ring_c.z + DRYER_Z)))
        side = "Men" if body.parent and "Men" in body.parent.name else "Women"
        placed.append(_obj(f"{PFX}DryerHolster_{side}{suffix.replace('.', '_')}", holster, c,
                           Matrix.Translation(wall_pt + f * 0.0005) @ yaw).name)
        placed.append(_obj(f"{PFX}HairDryer_{side}{suffix.replace('.', '_')}", dryer, c,
                           Matrix.Translation(ring_c + Vector((0, 0, DRYER_Z))) @ yaw).name)

    objs = [bpy.data.objects[n] for n in placed]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    uniq = sum(sum(len(p.vertices) - 2 for p in me.polygons) for me in {o.data for o in objs})
    return {"objects_added": len(objs), "triangles_added": tris, "unique_mesh_triangles": uniq,
            "objects_hidden": hidden}


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    res = apply()
    print(f"[detail4_{KEY}] {json.dumps(res)}")
    if "--save" in argv:
        out = argv[argv.index("--save") + 1]
        if "promo/scenes" in out or "promo/models" in out:
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
        print(f"[detail4_{KEY}] saved copy -> {out}")


if __name__ == "__main__":
    _main()
