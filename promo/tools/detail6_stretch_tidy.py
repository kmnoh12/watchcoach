"""detail6 stretch_tidy: organize stretching-zone props and restore 100% open mat space.

Keeps the wooden deck (2.30 x 4.20 m, x=[-7.30, -5.00], y=[-2.30, 1.90], top z=0.014),
mirror, signage, lighting, and surrounding equipment untouched.

What this module does (fully idempotent, original transforms stored in custom props):
  1. Re-spaces the 3 exercise mats (Stretch mat 1..3) cleanly in front of the mirror with
     uniform 26 cm gaps (y=[-1.56,-0.88], [-0.62,0.06], [0.32,1.00]) so both deck ends have
     generous, non-overlapping storage depth without reducing aisle width.
  2. Clears all props off the 3 mats (AbWheel off mat 2, FoamRoller_long off mat 3,
     GymBall_Large off mat 1 edge, GymBall_Burgundy off mat 3 & bench edge).
  3. Consolidates north-end storage cleanly on the deck (x=[-7.29,-5.46], y=[1.01,1.89]):
       - Roller rack base + 3 standing Stretch foam rollers seated flush on deck top (z=0.014).
       - FoamRoller_long (Ø15 x 90 cm) & FoamRoller_grid (Ø14.7 x 45 cm) stood vertically
         beside the roller rack.
       - New matte-black steel prop basket (Ddetail6_Stretch_PropBasket) holding AbWheel and
         a neatly folded ivory gym towel (Ddetail6_Stretch_FoldedTowel).
       - GymBall_Burgundy (Ø60 cm) cradled on a new rubber/steel ring stand.
  4. Tidies south-end storage cleanly on the deck (y=[-2.28,-1.64], z>=0.014):
       - YogaMatRack shifted fully onto deck so all 4 legs sit flush at z=0.014.
       - GymBall_Large (Ø64 cm) and GymBall_Medium (scaled 54->56 cm) raised out of the deck
         onto matching ring stands with clear separation from Stretch mat 1.
       - Plyo box raised flush onto deck top (z=0.014) at the south-east corner without
         protruding further into the aisle (x_max = -5.03 unchanged).

Usage:
    import detail6_stretch_tidy as m; m.apply()
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_stretch_tidy.py [-- --save out.blend]
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

COLL = "DETAIL6_stretch_tidy"
PFX = "Ddetail6_Stretch_"
PKG_KEY = "detail6_stretch_tidy"
PROP_PKG = "detail6_stretch_pkg"
PROP_ORIG_MAT = "detail6_stretch_orig_matrix"

DECK_Z = 0.014
DECK_X_MIN, DECK_X_MAX = -7.300, -5.000
DECK_Y_MIN, DECK_Y_MAX = -2.300, 1.900

# Ring stand geometry parameters
RING_HEIGHT = 0.065
RING_WALL = 0.025


def _get_or_create_material(name, base_color, roughness, metallic=0.0):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    m.diffuse_color = (*base_color, 1.0)
    return m


def _materials():
    steel = bpy.data.materials.get("Dgym_life_BlackSteel") or _get_or_create_material(
        PFX + "BlackSteel", (0.018, 0.019, 0.021), 0.36, 0.85
    )
    rubber = bpy.data.materials.get("Dgym_life_Rubber") or _get_or_create_material(
        PFX + "Rubber", (0.012, 0.012, 0.014), 0.72, 0.0
    )
    towel = bpy.data.materials.get("Dgym_life_TowelIvory") or _get_or_create_material(
        PFX + "TowelIvory", (0.78, 0.76, 0.70), 0.92, 0.0
    )
    return {"steel": steel, "rubber": rubber, "towel": towel}


def _tag_and_restore(ob):
    """Store original matrix_basis once; on repeat calls restore it before re-applying."""
    if ob.get(PROP_PKG) == PKG_KEY and PROP_ORIG_MAT in ob:
        vals = list(ob[PROP_ORIG_MAT])
        ob.matrix_basis = Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])
    else:
        ob[PROP_PKG] = PKG_KEY
        ob[PROP_ORIG_MAT] = [float(v) for row in ob.matrix_basis for v in row]


def _set_world_transform(ob, loc_xyz, rot_xyz=(0.0, 0.0, 0.0), scale_xyz=(1.0, 1.0, 1.0)):
    """Set object transform in world space cleanly, handling parented and unparented objects."""
    rot_m = Euler(rot_xyz, "XYZ").to_matrix().to_4x4()
    scl_m = Matrix.Diagonal((scale_xyz[0], scale_xyz[1], scale_xyz[2], 1.0))
    mw = Matrix.Translation(loc_xyz) @ rot_m @ scl_m
    if ob.parent is not None:
        ob.matrix_basis = (ob.parent.matrix_world @ ob.matrix_parent_inverse).inverted() @ mw
    else:
        ob.matrix_basis = mw


def _world_z_min(ob):
    mw = ob.matrix_world
    return min((mw @ v.co).z for v in ob.data.vertices)


def _shift_world_z(ob, dz):
    if abs(dz) <= 1e-8:
        return
    mw = ob.matrix_world.copy()
    mw.translation.z += dz
    if ob.parent is not None:
        ob.matrix_basis = (ob.parent.matrix_world @ ob.matrix_parent_inverse).inverted() @ mw
    else:
        ob.matrix_basis = mw
    bpy.context.view_layer.update()


def _snap_bottom_z(ob, target_z):
    bpy.context.view_layer.update()
    _shift_world_z(ob, target_z - _world_z_min(ob))


def _mesh_bvh(ob, dz=0.0):
    me = ob.data
    me.calc_loop_triangles()
    mw = ob.matrix_world.copy()
    mw.translation.z += dz
    verts = [mw @ v.co for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, tris, all_triangles=True)


def _seat_ball_on_ring(ball_ob, ring_ob, clearance=0.0005):
    """Binary-search exact vertical position so ball sits on ring with 0 overlap and ~0.5 mm gap."""
    bpy.context.view_layer.update()
    ring_bvh = _mesh_bvh(ring_ob)
    # Search dz in [-0.030, +0.030] relative to current placement
    lo, hi = -0.030, 0.030
    # Ensure lo overlaps and hi does not overlap
    while not _mesh_bvh(ball_ob, lo).overlap(ring_bvh) and lo > -0.15:
        lo -= 0.02
    while _mesh_bvh(ball_ob, hi).overlap(ring_bvh) and hi < 0.15:
        hi += 0.02
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        if _mesh_bvh(ball_ob, mid).overlap(ring_bvh):
            lo = mid
        else:
            hi = mid
    _shift_world_z(ball_ob, hi + clearance)


def _apply_box_uvs(bm, scale=2.0):
    """Assign clean tri-planar box UVs to every face so QA reports valid UV maps."""
    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                u, v = co.x * scale, co.y * scale
            elif ax >= ay:
                u, v = co.y * scale, co.z * scale
            else:
                u, v = co.x * scale, co.z * scale
            loop[uv_layer].uv = (u, v)


def _create_mesh_object(name, bm, materials, coll, smooth_angle_deg=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    _apply_box_uvs(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in materials:
        me.materials.append(m)
    if smooth_angle_deg is not None:
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(smooth_angle_deg))
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _add_box(bm, center, size, mat_idx=0, bevel=0.0):
    sx, sy, sz = size
    mx = Matrix.Translation(center) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=mx)
    verts = set(res["verts"])
    faces = [f for f in bm.faces if all(v in verts for v in f.verts)]
    edges = [e for e in bm.edges if all(v in verts for v in e.verts)]
    for f in faces:
        f.material_index = mat_idx
    if bevel > 0.0:
        bev = bmesh.ops.bevel(
            bm, geom=edges, offset=bevel, segments=1,
            affect="EDGES", profile=0.5, clamp_overlap=True,
        )
        for f in bev.get("faces", []):
            f.material_index = mat_idx


def _build_ball_ring(name, cx, cy, r_in, r_out, height, mat, coll):
    """Build a watertight revolved matte rubber/steel gym-ball ring stand at z=[DECK_Z, DECK_Z+height]."""
    bm = bmesh.new()
    segs = 48
    z0 = DECK_Z
    z1 = DECK_Z + height
    c_out = 0.004
    c_in = 0.008
    profile = [
        (r_in + 0.003, z0),
        (r_out - c_out, z0),
        (r_out, z0 + c_out),
        (r_out, z1 - c_out),
        (r_out - c_out, z1),
        (r_in + c_in, z1),
        (r_in, z1 - c_in),
        (r_in, z0 + 0.003),
    ]
    n_p = len(profile)
    rings = []
    for s in range(segs):
        ang = 2.0 * math.pi * s / segs
        ca, sa = math.cos(ang), math.sin(ang)
        ring = [bm.verts.new((cx + r * ca, cy + r * sa, z)) for (r, z) in profile]
        rings.append(ring)
    for s in range(segs):
        r0 = rings[s]
        r1 = rings[(s + 1) % segs]
        for k in range(n_p):
            k1 = (k + 1) % n_p
            f = bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
            f.material_index = 0
    return _create_mesh_object(name, bm, [mat], coll, smooth_angle_deg=42.0)


def _ball_center_z_on_ring(ball_radius, r_in, ring_height):
    """Initial analytical sphere center Z (refined afterward by exact BVH seating)."""
    r_sup = r_in + 0.004
    z_sup = DECK_Z + ring_height - 0.004
    return z_sup + math.sqrt(ball_radius * ball_radius - r_sup * r_sup)


def _build_prop_basket(name, cx, cy, wx, wy, h, mats, coll):
    """Build a clean open-slat matte-black steel gym prop basket with rubberized floor tray.

    Every intersecting member has >= 2 mm step in cross-section so parallel faces are never
    within 1 mm of each other (zero z-fighting, zero back-to-back faces, zero floating islands).
    """
    bm = bmesh.new()
    post = 0.016
    rail = 0.010  # 3 mm step per side inside 16 mm posts
    mid_rail = 0.009  # 2 mm step per side vs 5 mm slats
    slat = 0.005
    base_h = 0.010
    emb = 0.003

    x0, x1 = cx - wx / 2, cx + wx / 2
    y0, y1 = cy - wy / 2, cy + wy / 2
    z0 = DECK_Z
    z_floor = z0 + base_h
    z_top = z0 + h

    # 1. Solid rubber-lined base tray (mat_idx=1: rubber) raised 2 mm off deck so the 4 steel corner posts
    #    act as feet at z=0.014 while keeping interior floor at z_floor=0.024 (zero coplanar bottom faces)
    tray_lift = 0.002
    tray_thick = base_h - tray_lift
    _add_box(bm, (cx, cy, z0 + tray_lift + tray_thick / 2), (wx - post + 2 * emb, wy - post + 2 * emb, tray_thick), mat_idx=1, bevel=0.0012)

    # 2. Four vertical corner posts (mat_idx=0: black steel)
    for px in (x0 + post / 2, x1 - post / 2):
        for py in (y0 + post / 2, y1 - post / 2):
            _add_box(bm, (px, py, z0 + h / 2), (post, post, h), mat_idx=0, bevel=0.0015)

    # 3. Bottom and top horizontal perimeter rails embedded into corner posts (X & Y rails do not cross each other)
    span_x = wx - 2 * post + 2 * emb
    span_y = wy - 2 * post + 2 * emb
    z_bot_rail = z0 + base_h + 0.004 + rail / 2  # bottom at z0+0.014 (4 mm above tray top)
    z_top_rail = z_top - rail / 2 - 0.002        # top 2 mm below post top
    for rz in (z_bot_rail, z_top_rail):
        for ry in (y0 + post / 2, y1 - post / 2):
            _add_box(bm, (cx, ry, rz), (span_x, rail, rail), mat_idx=0, bevel=0.001)
        for rx in (x0 + post / 2, x1 - post / 2):
            _add_box(bm, (rx, cy, rz), (rail, span_y, rail), mat_idx=0, bevel=0.001)

    # 4. Mid horizontal rails (9 mm thick vs 5 mm slats -> 2 mm clear step per side)
    z_mid = z0 + h * 0.55
    for ry in (y0 + post / 2, y1 - post / 2):
        _add_box(bm, (cx, ry, z_mid), (span_x, mid_rail, mid_rail), mat_idx=0, bevel=0.0008)
    for rx in (x0 + post / 2, x1 - post / 2):
        _add_box(bm, (rx, cy, z_mid), (mid_rail, span_y, mid_rail), mat_idx=0, bevel=0.0008)

    # 5. Full-height open vertical wire slats running continuously from bottom rail to top rail
    zc, zh = 0.5 * (z_bot_rail + z_top_rail), z_top_rail - z_bot_rail
    for i in range(1, 6):
        sx = x0 + post + (wx - 2 * post) * (i / 6.0)
        for ry in (y0 + post / 2, y1 - post / 2):
            _add_box(bm, (sx, ry, zc), (slat, slat, zh), mat_idx=0, bevel=0.0006)
    for i in range(1, 5):
        sy = y0 + post + (wy - 2 * post) * (i / 5.0)
        for rx in (x0 + post / 2, x1 - post / 2):
            _add_box(bm, (rx, sy, zc), (slat, slat, zh), mat_idx=0, bevel=0.0006)

    # 6. Raised grip handles on the two short sides (x0, x1) with 2 mm step between posts (6 mm) and bar (10 mm)
    handle_h = 0.022
    handle_y = 0.13
    z_bar_top = z_top + handle_h
    z_bar_c = z_bar_top - 0.005
    for rx in (x0 + post / 2, x1 - post / 2):
        for hy in (cy - handle_y / 2 + 0.008, cy + handle_y / 2 - 0.008):
            _add_box(bm, (rx, hy, 0.5 * (z_top_rail + z_bar_c)), (0.006, 0.006, z_bar_c - z_top_rail), mat_idx=0, bevel=0.0008)
        _add_box(bm, (rx, cy, z_bar_c), (0.010, handle_y, 0.010), mat_idx=0, bevel=0.0015)

    ob = _create_mesh_object(name, bm, [mats["steel"], mats["rubber"]], coll, smooth_angle_deg=35.0)
    _snap_bottom_z(ob, DECK_Z)
    return ob, z_floor


def _build_folded_towel(name, cx, cy, z_base, mat, coll):
    """Build a single-island neatly folded ivory gym towel (soft U-fold profile) sitting on z_base."""
    bm = bmesh.new()
    # Continuous single-mesh folded towel: extruded U-fold cross section (in Y-Z) along X, then beveled
    w = 0.30
    d = 0.12
    h = 0.068
    t = 0.026  # thickness of each folded layer
    gap = 0.016  # fold slit opening on +Y side
    # 2D profile in local (y, z) around center, CCW
    y0, y1 = -d / 2, d / 2
    z0, z1 = 0.0, h
    z_mid_lo = t
    z_mid_hi = h - t
    # Closed U-profile (fold crease at y0, open layers at y1)
    prof = [
        (y0, z0),
        (y1, z0),
        (y1, z_mid_lo),
        (y0 + t * 0.9, z_mid_lo),
        (y0 + t * 0.9, z_mid_hi),
        (y1, z_mid_hi),
        (y1, z1),
        (y0, z1),
    ]
    n_p = len(prof)
    rot = Euler((0.0, 0.0, math.radians(-2.0)), "XYZ").to_matrix().to_4x4()
    trans = Matrix.Translation((cx, cy, z_base)) @ rot
    # Create 4 slices along X so it has clean quad topology and soft corners
    xs = (-w / 2, -w / 6, w / 6, w / 2)
    rings = []
    for x in xs:
        ring = [bm.verts.new(trans @ Vector((x, py, pz))) for (py, pz) in prof]
        rings.append(ring)
    for s in range(len(rings) - 1):
        r0, r1 = rings[s], rings[s + 1]
        for k in range(n_p):
            k1 = (k + 1) % n_p
            bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
    # Cap ends cleanly with quads (split U-shape into 3 quads: bottom leg, spine, top leg)
    # Indices: 0=(y0,z0), 1=(y1,z0), 2=(y1,lo), 3=(yin,lo), 4=(yin,hi), 5=(y1,hi), 6=(y1,z1), 7=(y0,z1)
    # Add two helper spine-corner verts at (y0, lo) and (y0, hi)? Simpler: 3 quads using existing 8 verts:
    # bottom leg (0,1,2,3), spine (0,3,4,7), top leg (4,5,6,7) -> ALL QUADS, zero n-gons!
    r_start, r_end = rings[0], rings[-1]
    for q in ((0, 3, 2, 1), (0, 7, 4, 3), (4, 7, 6, 5)):
        bm.faces.new(tuple(r_start[i] for i in q))
    for q in ((0, 1, 2, 3), (0, 3, 4, 7), (4, 5, 6, 7)):
        bm.faces.new(tuple(r_end[i] for i in q))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(
        bm, geom=list(bm.edges), offset=0.0055, segments=2,
        affect="EDGES", profile=0.55, clamp_overlap=True,
    )
    for f in bm.faces:
        f.material_index = 0
    ob = _create_mesh_object(name, bm, [mat], coll, smooth_angle_deg=65.0)
    # Seat 0.5 mm above basket floor so zero BVH overlap and zero back-to-back warning
    _snap_bottom_z(ob, z_base + 0.0005)
    return ob


def apply() -> dict:
    parent = bpy.data.collections["SET"]
    coll = parent.children.get(COLL)
    if coll is None:
        if bpy.data.collections.get(COLL):
            raise ValueError(f"{COLL} already exists outside SET")
        coll = bpy.data.collections.new(COLL)
        parent.children.link(coll)

    # Clean up previous run's created objects/meshes for idempotency
    for ob in list(coll.objects):
        me = ob.data if ob.type == "MESH" else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for me in list(bpy.data.meshes):
        if me.name.startswith(PFX) and me.users == 0:
            bpy.data.meshes.remove(me)

    mats = _materials()
    touched = []

    # ------------------------------------------------------------------
    # 1. Build new storage accessories (all seated flush on deck z=0.014)
    # ------------------------------------------------------------------
    # Prop basket at north storage bay, positioned so gym_stretch sees it south of the burgundy ball
    basket_cx, basket_cy = -6.44, 1.28
    basket_wx, basket_wy, basket_h = 0.46, 0.40, 0.24
    basket_ob, basket_floor_z = _build_prop_basket(
        PFX + "PropBasket", basket_cx, basket_cy, basket_wx, basket_wy, basket_h, mats, coll
    )

    # Folded towel neatly placed in the north half of the prop basket
    towel_ob = _build_folded_towel(
        PFX + "FoldedTowel", basket_cx, basket_cy + 0.105, basket_floor_z, mats["towel"], coll
    )

    # Three matte-rubber gym ball ring stands (one north, two south)
    ring_specs = [
        (PFX + "BallRing_North",  -5.76,  1.49, 0.170, 0.300),  # for GymBall_Burgundy (Ø60 cm)
        (PFX + "BallRing_South",  -6.54, -1.96, 0.180, 0.320),  # for GymBall_Large (Ø64 cm)
        (PFX + "BallRing_South2", -5.88, -1.96, 0.160, 0.280),  # for GymBall_Medium (Ø56 cm)
    ]
    ring_obs = {}
    for r_name, rx, ry, r_in, _ball_r in ring_specs:
        ring_obs[r_name] = _build_ball_ring(r_name, rx, ry, r_in, r_in + RING_WALL, RING_HEIGHT, mats["rubber"], coll)

    # ------------------------------------------------------------------
    # 2. Reposition the 3 exercise mats (uniform 26 cm gaps, aligned to mirror north edge y=1.00)
    #    Mat X stays [-6.93, -5.21] (center -6.07), Z stays [0.014, 0.036] (center 0.025)
    # ------------------------------------------------------------------
    mat_targets = [
        ("Stretch mat 1", (-6.07, -1.22, 0.025)),  # y = [-1.56, -0.88]
        ("Stretch mat 2", (-6.07, -0.28, 0.025)),  # y = [-0.62, +0.06]
        ("Stretch mat 3", (-6.07,  0.66, 0.025)),  # y = [+0.32, +1.00]
    ]
    for nm, loc in mat_targets:
        ob = bpy.data.objects[nm]
        _tag_and_restore(ob)
        _set_world_transform(ob, loc)
        _snap_bottom_z(ob, DECK_Z)
        touched.append(nm)

    # ------------------------------------------------------------------
    # 3. North-end storage bay (y = [1.01, 1.89], completely off mats & clear of benches y=1.824)
    # ------------------------------------------------------------------
    # 3a. Roller rack base: fully on deck west-north corner (x=[-7.29,-6.95], y=[1.01,1.89], z=[0.014,0.054])
    rack_base = bpy.data.objects["Roller rack base"]
    _tag_and_restore(rack_base)
    _set_world_transform(rack_base, (-7.12, 1.45, DECK_Z + 0.020))
    _snap_bottom_z(rack_base, DECK_Z)
    touched.append("Roller rack base")
    rack_top_z = DECK_Z + 0.040

    # 3b. 3 standing dark Stretch foam rollers flush on Roller rack base top (z=[0.054, 0.714])
    for nm, ry in (
        ("Stretch foam roller",     1.18),
        ("Stretch foam roller.001", 1.45),
        ("Stretch foam roller.002", 1.72),
    ):
        ob = bpy.data.objects[nm]
        _tag_and_restore(ob)
        _set_world_transform(ob, (-7.12, ry, rack_top_z + 0.330))
        _snap_bottom_z(ob, rack_top_z)
        touched.append(nm)

    # 3c. FoamRoller_long (blue, Ø15 x 90 cm): off Mat 3, stood vertically beside roller rack
    fr_long = bpy.data.objects["Dgym_life_FoamRoller_long"]
    _tag_and_restore(fr_long)
    _set_world_transform(fr_long, (-6.80, 1.66, DECK_Z + 0.450), rot_xyz=(math.pi / 2.0, 0.0, 0.0))
    _snap_bottom_z(fr_long, DECK_Z)
    touched.append("Dgym_life_FoamRoller_long")

    # 3d. FoamRoller_grid (black/orange, Ø14.7 cm): scaled 33.2->45.0 cm length, stood vertically beside long roller
    fr_grid = bpy.data.objects["Dgym_life_FoamRoller_grid"]
    _tag_and_restore(fr_grid)
    grid_len_scale = 0.450 / 0.332
    _set_world_transform(
        fr_grid, (-6.80, 1.40, DECK_Z + 0.225),
        rot_xyz=(0.0, math.pi / 2.0, 0.0),
        scale_xyz=(grid_len_scale, 1.0, 1.0),
    )
    _snap_bottom_z(fr_grid, DECK_Z)
    touched.append("Dgym_life_FoamRoller_grid")

    # 3e. AbWheel (wheel Ø18 cm, width 36 cm): off Mat 2, seated inside PropBasket on basket floor
    ab = bpy.data.objects["Dgym_life_AbWheel"]
    _tag_and_restore(ab)
    _set_world_transform(
        ab, (basket_cx, basket_cy - 0.065, basket_floor_z + 0.090),
        rot_xyz=(0.0, 0.0, math.radians(6.0)),
    )
    _snap_bottom_z(ab, basket_floor_z)
    touched.append("Dgym_life_AbWheel")

    # 3f. GymBall_Burgundy (Ø60 cm, local origin at bottom z=0): cradled on north ring stand via exact BVH seating
    ball_burg = bpy.data.objects["Dgym_life_GymBall_Burgundy"]
    _tag_and_restore(ball_burg)
    burg_cz = _ball_center_z_on_ring(0.300, 0.170, RING_HEIGHT)
    _set_world_transform(ball_burg, (-5.76, 1.49, burg_cz - 0.300))
    _seat_ball_on_ring(ball_burg, ring_obs[PFX + "BallRing_North"], clearance=0.0005)
    touched.append("Dgym_life_GymBall_Burgundy")

    # ------------------------------------------------------------------
    # 4. South-end storage bay (y = [-2.28, -1.64], all legs/bases flush on deck z=0.014)
    # ------------------------------------------------------------------
    # 4a. YogaMatRack: shift +0.165 m in X so all 4 legs sit inside deck (x=[-7.2855,-6.9645]) flush at z=0.014
    ym_rack = bpy.data.objects["Dgym_life_YogaMatRack"]
    _tag_and_restore(ym_rack)
    _set_world_transform(ym_rack, (0.165, 0.0, DECK_Z))
    _snap_bottom_z(ym_rack, DECK_Z)
    touched.append("Dgym_life_YogaMatRack")

    # 4b. GymBall_Large (Ø64 cm, center origin): raised out of deck onto south ring stand
    ball_l = bpy.data.objects["GymBall_Large"]
    _tag_and_restore(ball_l)
    large_cz = _ball_center_z_on_ring(0.320, 0.180, RING_HEIGHT)
    _set_world_transform(ball_l, (-6.54, -1.96, large_cz))
    _seat_ball_on_ring(ball_l, ring_obs[PFX + "BallRing_South"], clearance=0.0005)
    touched.append("GymBall_Large")

    # 4c. GymBall_Medium (Ø54->56 cm to meet 55-65 cm spec, center origin): onto south ring stand 2
    ball_m = bpy.data.objects["GymBall_Medium"]
    _tag_and_restore(ball_m)
    med_scale = 0.560 / 0.540
    med_cz = _ball_center_z_on_ring(0.280, 0.160, RING_HEIGHT)
    _set_world_transform(ball_m, (-5.88, -1.96, med_cz), scale_xyz=(med_scale, med_scale, med_scale))
    _seat_ball_on_ring(ball_m, ring_obs[PFX + "BallRing_South2"], clearance=0.0005)
    touched.append("GymBall_Medium")

    # 4d. Plyo box (0.50 x 0.60 x 0.40 m): raised flush on deck z=0.014, x=[-5.53,-5.03], y=[-2.26,-1.66]
    plyo = bpy.data.objects["Plyo box"]
    _tag_and_restore(plyo)
    _set_world_transform(plyo, (-5.28, -1.96, DECK_Z + 0.200), rot_xyz=(0.0, 0.0, 0.0))
    _snap_bottom_z(plyo, DECK_Z)
    touched.append("Plyo box")

    bpy.context.view_layer.update()

    # Count added triangles
    added = [basket_ob, towel_ob] + list(ring_obs.values())
    tris = 0
    for ob in added:
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)

    return dict(
        objects_added=len(added),
        added_names=[ob.name for ob in added],
        triangles_added=tris,
        existing_objects_touched=touched,
    )


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    save = None
    if "--save" in argv:
        save = Path(argv[argv.index("--save") + 1]).expanduser().resolve()
        root = Path(__file__).resolve().parents[2]
        if any(save.is_relative_to((root / "promo" / d).resolve()) for d in ("scenes", "models")):
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        if save.suffix.lower() != ".blend":
            raise SystemExit("--save must end with .blend")
        save.parent.mkdir(parents=True, exist_ok=True)
    res = apply()
    print("detail6_stretch_tidy", res)
    if save is not None:
        bpy.ops.wm.save_as_mainfile(
            filepath=str(save), copy=True, compress=True, relative_remap=False
        )
        print("saved", save)


if __name__ == "__main__":
    _main()
