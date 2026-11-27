"""Build the Rookie Hero (`promo/models/hero_rookie.blend`) from the original standard-height
low-poly figure (`promo/cast/src_figure_copy.blend`, 175 cm, 52-bone V6-compatible rig).

Applies:
  1. App aqua #63d6de monochrome material matching V6 (`wc_lib.apply_hero_viewer_material`).
  2. Real-size 44.8 mm WatchCoach smartwatch fitted to the rookie's left wrist (`lowerarm_l`).
  3. Varsity-W charcoal baseball cap + silver AirPods Max via `promo/tools/hero_gear.py`,
     fitted to the rookie's skull (`head` bone) with independent toggle roots (both ON by default).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
      -P promo/models/build_rookie_hero.py
"""
import importlib.util
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO = os.path.dirname(HERE)
TOOLS = os.path.join(PROMO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import wc_lib as W
import hero_gear as HG

SRC_FIG = os.path.join(PROMO, "cast", "src_figure_copy.blend")
WATCH_BLEND = os.path.join(HERE, "lowpoly_watch.blend")
OUT_BLEND = os.path.join(HERE, "hero_rookie.blend")

# Real-size 44.8 mm watch parameters (matching build_v5_with_watch.py)
WATCH_SCALE = 1.0
WRIST_DIST = 0.045
WATCH_BONE = "lowerarm_l"
CASE_BACK = 0.0121

_lpw_spec = importlib.util.spec_from_file_location("lpw", os.path.join(HERE, "build_lowpoly_watch.py"))
lpw = importlib.util.module_from_spec(_lpw_spec)
_lpw_spec.loader.exec_module(lpw)


# ------------------------------------------------------------------ wrist & strap fitting

def rest_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def forearm_frame(arm):
    bones = arm.data.bones
    elbow = bones[WATCH_BONE].head_local
    wrist = bones[WATCH_BONE].tail_local
    axis = (wrist - elbow).normalized()
    across_knuckles = bones["index_01_l"].head_local - bones["pinky_01_l"].head_local
    finger_dir = (bones["middle_01_l"].tail_local - bones["middle_01_l"].head_local).normalized()
    dorsal = across_knuckles.cross(finger_dir)
    dorsal = (dorsal - axis * dorsal.dot(axis)).normalized()
    return wrist, axis, dorsal, dorsal.cross(axis)


def arm_section(body, center_pt, axis):
    """Cross-section points of the rest forearm across the 24 mm strap width, projected to center_pt."""
    me = body.data
    pts = []
    for off in (-0.012, -0.006, 0.0, 0.006, 0.012):
        bm = bmesh.new()
        bm.from_mesh(me)
        q = center_pt + axis * off
        res = bmesh.ops.bisect_plane(
            bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=q, plane_no=axis
        )
        for v in res["geom_cut"]:
            if isinstance(v, bmesh.types.BMVert) and (v.co - q).length < 0.08:
                pts.append(v.co - axis * (v.co - center_pt).dot(axis))
        bm.free()
    return pts


def convex_hull_2d(pts):
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return [Vector(p) for p in lo[:-1] + up[:-1]]


def hull_radius(hull, center, direction):
    best = 0.0
    for i in range(len(hull)):
        p, q = hull[i], hull[(i + 1) % len(hull)]
        e = q - p
        den = direction.x * e.y - direction.y * e.x
        if abs(den) < 1e-12:
            continue
        w = p - center
        t = (w.x * e.y - w.y * e.x) / den
        u = (w.x * direction.y - w.y * direction.x) / den
        if t > 0 and -1e-9 <= u <= 1 + 1e-9:
            best = max(best, t)
    return best


def make_strap_path(local_pts, clearance_m=0.0016):
    hull = convex_hull_2d(local_pts)
    ys, zs = [p.x for p in hull], [p.y for p in hull]
    center = Vector(((min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    off = lpw.STRAP_T / 2 + clearance_m / WATCH_SCALE
    rim = []
    for i in range(360):
        th = math.radians(i)
        d = Vector((math.sin(th), math.cos(th)))
        rim.append(center + d * (hull_radius(hull, center, d) + off))
    lugs = {s: Vector((s * 0.018, -0.0070)) for s in (-1, 1)}
    outline = convex_hull_2d(rim + list(lugs.values()))
    att = {}
    for side, lug in lugs.items():
        v = lug - center
        att[side] = (math.atan2(v.x, v.y), v.length)

    radii = [
        hull_radius(outline, center, Vector((math.sin(math.radians(i)), math.cos(math.radians(i)))))
        for i in range(360)
    ]
    sm = [sum(radii[(i + j) % 360] for j in range(-10, 11)) / 21 for i in range(360)]

    def el_point(th):
        deg = math.degrees(th) % 360
        i = int(deg)
        r = sm[i] + (deg - i) * (sm[(i + 1) % 360] - sm[i])
        return center + Vector((math.sin(th), math.cos(th))) * r

    def el_frame(th):
        p = el_point(th)
        t = (el_point(th + 1e-4) - el_point(th - 1e-4)).normalized()
        n = Vector((t.y, -t.x))
        if n.dot(p - center) < 0:
            n = -n
        return p, t, n

    return el_point, el_frame, center, att, sum(sm) / len(sm)


def build_fitted_strap(el_point, el_frame, center, att, r_mean, mats):
    lpw.el_point, lpw.el_frame, lpw.EL_A, lpw.EL_C = el_point, el_frame, r_mean, center
    bm = bmesh.new()
    holes = [math.radians(d) for d in (112, 124, 136, 148, 160)]
    hole_faces = lpw.build_strap_piece(bm, abs(att[1][0]), math.radians(202), holes, 1)
    # Stop 6-o'clock strap 1.2 deg before buckle back bar (-150 deg) to avoid coplanar end-cap z-fighting
    lpw.build_strap_piece(bm, -abs(att[-1][0]), -math.radians(148.8), [], 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    res = bmesh.ops.inset_individual(bm, faces=hole_faces, thickness=0.0004, depth=-0.0018)
    for f in hole_faces + list(res.get("faces", [])):
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    strap = bpy.data.meshes.new("Watch_Strap_Rookie")
    bm.to_mesh(strap)
    bm.free()
    for m in mats:
        strap.materials.append(m)
    tmp = lpw.build_buckle(None, bpy.data.materials["Watch_Buckle_Metal"])
    buckle = tmp.data
    bpy.data.objects.remove(tmp)
    # Lift buckle 0.80 mm radially outward from strap center so prong/frame never z-fights strap face
    _, _, b_nrm = el_frame(-math.radians(150))
    for v in buckle.vertices:
        v.co.y += b_nrm.x * 0.00080
        v.co.z += b_nrm.y * 0.00080
    buckle.update()
    for me in (strap, buckle):
        for p in me.polygons:
            p.use_smooth = False
    return strap, buckle


def smart_uv(ob):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def fit_watch_to_rookie(arm, body):
    """Append real-size 44.8 mm watch, fit strap around rookie's left forearm, bone-parent to lowerarm_l."""
    wrist, axis, dorsal, side_vec = forearm_frame(arm)
    center_pt = wrist - axis * WRIST_DIST
    pts = arm_section(body, center_pt, axis)
    hull = convex_hull_2d([((p - center_pt).dot(side_vec), (p - center_pt).dot(dorsal)) for p in pts])
    across = max((a - b for a in hull for b in hull), key=lambda v: v.length_squared)
    if across.x < 0:
        across.negate()
    side_vec = (side_vec * across.x + dorsal * across.y).normalized()
    dorsal = axis.cross(side_vec).normalized()

    ys = [(p - center_pt).dot(side_vec) for p in pts]
    yc = (min(ys) + max(ys)) / 2
    ztop = max((p - center_pt).dot(dorsal) for p in pts if abs((p - center_pt).dot(side_vec) - yc) < 0.016)
    # Seat sensor dome flush above skin (0.8 mm positive clearance so case never penetrates)
    origin = center_pt + side_vec * yc + dorsal * (ztop + (CASE_BACK + 0.0008) * WATCH_SCALE)
    local = [
        Vector((((p - origin).dot(side_vec)) / WATCH_SCALE, ((p - origin).dot(dorsal)) / WATCH_SCALE))
        for p in pts
    ]
    el_point, el_frame, center, att, r_mean = make_strap_path(local, clearance_m=0.0018)

    names = [
        "LowPolyWatch",
        "Watch_Case",
        "Watch_Display",
        "Watch_ButtonA",
        "Watch_ButtonB",
        "Watch_Strap",
        "Watch_Buckle",
    ]
    with bpy.data.libraries.load(WATCH_BLEND, link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
    col = W.coll("Watch")
    for ob in dst.objects:
        col.objects.link(ob)
    obs = {ob.name: ob for ob in dst.objects}
    root = obs["LowPolyWatch"]

    strap_me, buckle_me = build_fitted_strap(
        el_point, el_frame, center, att, r_mean, list(obs["Watch_Strap"].data.materials)
    )
    for key, me in (("Watch_Strap", strap_me), ("Watch_Buckle", buckle_me)):
        old = obs[key].data
        obs[key].data = me
        bpy.data.meshes.remove(old)
        me.name = key
        smart_uv(obs[key])

    frame = Matrix((axis, side_vec, dorsal)).transposed()
    world_mat = Matrix.Translation(origin) @ frame.to_4x4() @ Matrix.Scale(WATCH_SCALE, 4)
    root.parent = arm
    root.parent_type = "BONE"
    root.parent_bone = WATCH_BONE
    bpy.context.view_layer.update()
    root.matrix_world = world_mat
    bpy.context.view_layer.update()
    return root, list(root.children)


def measure_watch_clearance(body, parts):
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)
    dirs = [Vector(d).normalized() for d in ((0.31, 0.52, 0.80), (-0.7, 0.2, -0.68), (0.1, -0.9, 0.42))]

    def inside(co):
        votes = 0
        for d in dirs:
            o, n = co.copy(), 0
            for _ in range(64):
                hit = bvh.ray_cast(o, d, 5.0)
                if hit[0] is None:
                    break
                n += 1
                o = hit[0] + d * 1e-5
            votes += n % 2
        return votes >= 2

    out = {}
    for ob in parts:
        me = ob.evaluated_get(dg).to_mesh()
        mw = ob.matrix_world
        depth, n_in, gaps = 0.0, 0, []
        for v in me.vertices:
            co = mw @ v.co
            d = bvh.find_nearest(co)[3]
            if inside(co):
                n_in += 1
                depth = max(depth, d)
            else:
                gaps.append(d)
        ob.evaluated_get(dg).to_mesh_clear()
        out[ob.name] = {
            "inside": n_in,
            "of": n_in + len(gaps),
            "max_depth_mm": round(depth * 1000, 2),
            "min_gap_mm": round(min(gaps) * 1000, 2) if gaps else None,
        }
    return out


# ------------------------------------------------------------------ main build

def build(out_path=OUT_BLEND):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0

    with bpy.data.libraries.load(SRC_FIG, link=False) as (src, dst):
        dst.objects = ["Fig.rig", "BASE_Low Poly Man"]
    for ob in dst.objects:
        if ob is not None:
            sc.collection.objects.link(ob)

    arm = bpy.data.objects["Fig.rig"]
    body = bpy.data.objects["BASE_Low Poly Man"]
    arm.name = "Hero_Rookie"
    arm.data.name = "Hero_Rookie_Rig"
    body.name = "Hero_Rookie_Body"
    body.data.name = "Hero_Rookie_Mesh"
    arm.location = (0.0, 0.0, 0.0)
    arm.rotation_euler = (0.0, 0.0, 0.0)
    arm.scale = (1.0, 1.0, 1.0)
    body.location = (0.0, 0.0, 0.0)
    body.rotation_euler = (0.0, 0.0, 0.0)
    body.scale = (1.0, 1.0, 1.0)
    if body.data.shape_keys is not None:
        body.shape_key_clear()
    rest_pose(arm)

    # 1. App aqua #63d6de monochrome material matching V6 hero
    for p in body.data.polygons:
        p.use_smooth = False
    W.apply_hero_viewer_material(body, "Hero_Rookie")
    # Clean box UV so asset QA passes cleanly on body too
    bm = bmesh.new()
    bm.from_mesh(body.data)
    HG._assign_box_uv(bm)
    bm.to_mesh(body.data)
    bm.free()

    # 2. Left-wrist 44.8 mm watch fitted to rookie forearm
    watch_root, watch_parts = fit_watch_to_rookie(arm, body)
    watch_clear = measure_watch_clearance(body, watch_parts)

    # 3. Fitted Varsity-W cap + silver AirPods Max (both ON by default, independently toggleable)
    gear = HG.attach_gear(
        arm,
        body=body,
        profile="hero_rookie",
        include_cap=True,
        include_headset=True,
        show_cap=True,
        show_headset=True,
        separate_collections=True,
        prefix="Hero_Rookie_",
    )

    rest_pose(arm)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)

    zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
    summary = {
        "out": out_path,
        "height_m": round(max(zs) - min(zs), 4),
        "body_verts": len(body.data.vertices),
        "body_polys": len(body.data.polygons),
        "bones": len(arm.data.bones),
        "watch_clearance": watch_clear,
        "gear_profile": gear["profile"],
        "cap_objects": len(gear["cap_objects"]),
        "headset_objects": len(gear["headset_objects"]),
    }
    print("ROOKIE_HERO_BUILT", json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    out = OUT_BLEND
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        if "--out" in args:
            out = args[args.index("--out") + 1]
    build(out)
