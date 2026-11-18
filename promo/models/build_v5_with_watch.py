"""Put the low-poly watch on the V5 character's LEFT wrist, bone-parented to lowerarm_l.

Run: blender -b -P build_v5_with_watch.py
Reads (never writes) the V5 rig blend: it is copied to a temp file first.
Outputs next to this script: v5_with_watch.blend, renders_v5_watch/*.png + fit_report.json
The watch case/display/buttons are appended from lowpoly_watch.blend; the strap and buckle
are regenerated (same builder code as build_lowpoly_watch.py) along the V5 forearm outline.
"""
import importlib.util
import json
import math
import os
import shutil
import tempfile

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
RIG_SRC = os.path.join(os.path.dirname(HERE), "cast", "src_v5_rig.blend")
WATCH_BLEND = os.path.join(HERE, "lowpoly_watch.blend")
OUT_BLEND = os.path.join(HERE, "v5_with_watch.blend")
RENDER_DIR = os.path.join(HERE, "renders_v5_watch")

K = 1.2              # watch scale: a bit oversized so it reads on camera
WRIST_DIST = 0.055   # watch center: this far up the forearm from the wrist joint (m)
BONE = "lowerarm_l"
CASE_BACK = 0.0121   # local depth of the sensor dome below the display center

spec = importlib.util.spec_from_file_location("lpw", os.path.join(HERE, "build_lowpoly_watch.py"))
lpw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lpw)


# ---------------------------------------------------------------- scene / measuring

def open_rig_copy():
    tmp = os.path.join(tempfile.mkdtemp(prefix="v5watch_"), "V5_common_rig_copy.blend")
    shutil.copy2(RIG_SRC, tmp)
    bpy.ops.wm.open_mainfile(filepath=tmp)
    return bpy.data.objects["V5_CommonRig"], bpy.data.objects["V5_Body"]


def rest_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def forearm_frame(arm):
    B = arm.data.bones
    e, w = B[BONE].head_local, B[BONE].tail_local
    A = (w - e).normalized()                                   # toward the hand
    L = B["index_01_l"].head_local - B["pinky_01_l"].head_local
    F = (B["middle_01_l"].tail_local - B["middle_01_l"].head_local).normalized()
    D = L.cross(F)                                             # back of the hand (left hand)
    D = (D - A * D.dot(A)).normalized()
    return w, A, D, D.cross(A)


def arm_section(body, P, A):
    """Cut the rest-pose body across the forearm over the strap's width; points projected to P's plane."""
    me = body.data
    pts = []
    for off in (-0.012, -0.006, 0.0, 0.006, 0.012):   # strap width x K = 24 mm
        bm = bmesh.new()
        bm.from_mesh(me)
        Q = P + A * off
        r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                   plane_co=Q, plane_no=A)
        for v in r["geom_cut"]:
            if isinstance(v, bmesh.types.BMVert) and (v.co - Q).length < 0.08:
                pts.append(v.co - A * (v.co - P).dot(A))
        bm.free()
    return pts


# ---------------------------------------------------------------- strap fit

def convex_hull(pts):
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


def hull_radius(hull, C, d):
    best = 0.0
    for i in range(len(hull)):
        p, q = hull[i], hull[(i + 1) % len(hull)]
        e = q - p
        den = d.x * e.y - d.y * e.x
        if abs(den) < 1e-12:
            continue
        w = p - C
        t = (w.x * e.y - w.y * e.x) / den
        u = (w.x * d.y - w.y * d.x) / den
        if t > 0 and -1e-9 <= u <= 1 + 1e-9:
            best = max(best, t)
    return best


def make_strap_path(local_pts):
    """Strap midline r(theta) around the arm center (watch-local units). theta=0 points up (+Z),
    +theta toward +Y. Hugs the arm's convex outline with a small gap and eases into the case side."""
    hull = convex_hull(local_pts)
    ys, zs = [p.x for p in hull], [p.y for p in hull]
    C = Vector(((min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    off = 0.0010 / K + lpw.STRAP_T / 2
    N = 360
    raw = [hull_radius(hull, C, Vector((math.sin(2 * math.pi * i / N), math.cos(2 * math.pi * i / N)))) + off
           for i in range(N)]
    win = 12  # +-12 deg moving average rounds the low-poly corners
    sm = [sum(raw[(i + j) % N] for j in range(-win, win + 1)) / (2 * win + 1) for i in range(N)]
    # smoothing can pull the path inside convex corners: never go below the raw outline
    sm = [max(a, b) for a, b in zip(sm, raw)]
    attach = {s: Vector((s * 0.0205, -0.0080)) - C for s in (1, -1)}   # strap ends inside the lower case side
    att = {s: (math.atan2(v.x, v.y), v.length) for s, v in attach.items()}
    blend = math.radians(40)

    def r_of(th):
        f = math.degrees(th) % 360.0
        i0 = int(f) % N
        t = f - int(f)
        r = sm[i0] * (1 - t) + sm[(i0 + 1) % N] * t
        tha, ra = att[1 if th >= 0 else -1]
        dth = abs(th) - abs(tha)
        if dth < blend:
            u = max(0.0, dth / blend)
            u = u * u * (3 - 2 * u)
            r = max(ra * (1 - u) + r * u, r)   # ease out of the case without denting inward
        return r

    def el_point(th):
        return C + Vector((math.sin(th), math.cos(th))) * r_of(th)

    def el_frame(th):
        p = el_point(th)
        t = (el_point(th + 1e-4) - el_point(th - 1e-4)).normalized()
        n = Vector((t.y, -t.x))
        if n.dot(p - C) < 0:
            n = -n
        return p, t, n

    return el_point, el_frame, C, att, sum(sm) / N


def build_fitted_strap(el_point, el_frame, C, att, r_mean, mats):
    lpw.el_point, lpw.el_frame, lpw.EL_A, lpw.EL_C = el_point, el_frame, r_mean, C
    bm = bmesh.new()
    holes = [math.radians(d) for d in (112, 124, 136, 148, 160)]
    hole_faces = lpw.build_strap_piece(bm, abs(att[1][0]), math.radians(176), holes, 1)
    lpw.build_strap_piece(bm, -abs(att[-1][0]), -math.radians(150), [], 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    res = bmesh.ops.inset_individual(bm, faces=hole_faces, thickness=0.0004, depth=-0.0018)
    for f in hole_faces + list(res.get("faces", [])):
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    strap = bpy.data.meshes.new("Watch_Strap_fitV5")
    bm.to_mesh(strap)
    bm.free()
    for m in mats:
        strap.materials.append(m)
    tmp = lpw.build_buckle(None, bpy.data.materials["Watch_Buckle_Metal"])
    buckle = tmp.data
    bpy.data.objects.remove(tmp)
    for me in (strap, buckle):
        for p in me.polygons:
            p.use_smooth = False
    return strap, buckle


def append_watch():
    names = ["LowPolyWatch", "Watch_Case", "Watch_Display", "Watch_ButtonA", "Watch_ButtonB",
             "Watch_Strap", "Watch_Buckle"]
    with bpy.data.libraries.load(WATCH_BLEND, link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
    col = bpy.data.collections.new("Watch")
    bpy.context.scene.collection.children.link(col)
    for ob in dst.objects:
        col.objects.link(ob)
    return {ob.name: ob for ob in dst.objects}


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


# ---------------------------------------------------------------- posing

def bone_axis(arm, name):
    pb = arm.pose.bones[name]
    h = arm.matrix_world @ pb.head
    return h, (arm.matrix_world @ pb.tail - h).normalized()


def rotate_bone_world(arm, name, q, pivot):
    pb = arm.pose.bones[name]
    M = arm.matrix_world @ pb.matrix
    M = Matrix.Translation(pivot) @ q.to_matrix().to_4x4() @ Matrix.Translation(-pivot) @ M
    pb.matrix = arm.matrix_world.inverted() @ M
    bpy.context.view_layer.update()


def aim_bone(arm, name, direction):
    h, cur = bone_axis(arm, name)
    rotate_bone_world(arm, name, cur.rotation_difference(Vector(direction).normalized()), h)


def roll_bone(arm, name, deg):
    h, ax = bone_axis(arm, name)
    rotate_bone_world(arm, name, Quaternion(ax, math.radians(deg)), h)


def watch_twist_needed(arm, watch, target):
    """Degrees to roll the forearm about its axis so the watch face points along `target`."""
    _, ax = bone_axis(arm, BONE)
    wz = watch.matrix_world.to_3x3().col[2].normalized()
    t = target.normalized()
    pz, pt = wz - ax * wz.dot(ax), t - ax * t.dot(ax)
    ang = pz.angle(pt)
    return math.degrees(-ang if pz.cross(pt).dot(ax) < 0 else ang)


def apply_pose(arm, watch, p):
    """Aim upper arm and forearm; if the watch should face something, split the needed roll between
    the shoulder (upper-arm roll, keeps the elbow in place) and forearm pronation, so neither the
    elbow nor the shoulder gets a 180-degree candy-wrap twist."""
    def target():
        if "face_point" in p:
            return Vector(p["face_point"]) - watch.matrix_world.translation
        return Vector(p["face_dir"])

    best = None
    for psi in range(-180, 180, 5) if ("face_point" in p or "face_dir" in p) else [0]:
        rest_pose(arm)
        aim_bone(arm, "upperarm_l", p["upper"])
        roll_bone(arm, "upperarm_l", psi)
        aim_bone(arm, BONE, p["lower"])
        tw = watch_twist_needed(arm, watch, target()) if psi is not None and ("face_point" in p or "face_dir" in p) else 0.0
        cost = psi * psi + 1.5 * tw * tw
        if best is None or cost < best[0]:
            best = (cost, psi, tw)
    _, psi, tw = best
    rest_pose(arm)
    aim_bone(arm, "upperarm_l", p["upper"])
    roll_bone(arm, "upperarm_l", psi)
    aim_bone(arm, BONE, p["lower"])
    if tw:
        roll_bone(arm, BONE, tw)
    return psi, tw


POSES = {
    "pose1_arm_down": dict(upper=(0.25, 0.0, -1.0), lower=(0.22, -0.12, -1.0)),
    "pose2_check_watch": dict(upper=(0.25, -0.75, -0.6), lower=(-0.85, -0.38, 0.30),
                              face_point=(0.0, -0.12, 1.60)),
    "pose3_arm_forward": dict(upper=(0.08, -1.0, -0.05), lower=(0.04, -1.0, 0.0),
                              face_dir=(0.0, 0.0, 1.0)),
}


def clearance(body, parts):
    """Per part: verts inside the posed body (ray parity, 3 directions, majority vote),
    the deepest one, and the smallest gap of the outside ones."""
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
        out[ob.name] = dict(inside=n_in, of=n_in + len(gaps), max_depth_mm=round(depth * 1000, 1),
                            min_gap_mm=round(min(gaps) * 1000, 1) if gaps else None)
    return out


# ---------------------------------------------------------------- render

def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Review_World")
    sc.world = world
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.78, 0.80, 0.83, 1)
    bg.inputs["Strength"].default_value = 0.6
    col = bpy.data.collections.new("ReviewRig")
    sc.collection.children.link(col)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(8)
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    col.objects.link(sun)
    cam = bpy.data.objects.new("ReviewCam", bpy.data.cameras.new("ReviewCam"))
    cam.data.clip_start = 0.01
    col.objects.link(cam)
    sc.camera = cam
    return cam


def render(cam, name, loc, target, lens=50, res=(900, 900)):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    cam.data.lens = lens
    cam.location = Vector(loc)
    look_at(cam, target)
    path = os.path.join(RENDER_DIR, name + ".png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def closeup(cam, name, watch, back=0.55, side=0.18, up=0.06):
    wz = watch.matrix_world.to_3x3().col[2].normalized()
    wpos = watch.matrix_world.translation.copy()
    s = wz.cross(Vector((0, 0, 1)))
    s = s.normalized() if s.length > 1e-3 else Vector((1, 0, 0))
    return render(cam, name, wpos + wz * back + s * side + Vector((0, 0, up)), wpos, lens=85)


# ---------------------------------------------------------------- main

def main():
    os.makedirs(RENDER_DIR, exist_ok=True)
    arm, body = open_rig_copy()
    body_vcount = len(body.data.vertices)
    rest_pose(arm)

    # --- fit -------------------------------------------------------------
    w, A, D, S = forearm_frame(arm)
    P = w - A * WRIST_DIST
    pts = arm_section(body, P, A)
    ys = [(p - P).dot(S) for p in pts]
    yc = (min(ys) + max(ys)) / 2
    ztop = max((p - P).dot(D) for p in pts if abs((p - P).dot(S) - yc) < 0.012)
    origin = P + S * yc + D * (ztop + (CASE_BACK + 0.0004) * K)
    local = [Vector((((p - origin).dot(S)) / K, ((p - origin).dot(D)) / K)) for p in pts]
    el_point, el_frame, C, att, r_mean = make_strap_path(local)

    # --- watch -----------------------------------------------------------
    obs = append_watch()
    root = obs["LowPolyWatch"]
    strap_me, buckle_me = build_fitted_strap(el_point, el_frame, C, att, r_mean,
                                             list(obs["Watch_Strap"].data.materials))
    for key, me in (("Watch_Strap", strap_me), ("Watch_Buckle", buckle_me)):
        old = obs[key].data
        obs[key].data = me
        bpy.data.meshes.remove(old)
        me.name = key
        smart_uv(obs[key])

    frame = Matrix((A, S, D)).transposed()   # columns: X=toward hand, Y=across wrist, Z=out of back
    M = Matrix.Translation(origin) @ frame.to_4x4() @ Matrix.Scale(K, 4)
    root.parent = arm
    root.parent_type = "BONE"
    root.parent_bone = BONE
    bpy.context.view_layer.update()
    root.matrix_world = M
    bpy.context.view_layer.update()
    err = max(abs(x - y) for r1, r2 in zip(root.matrix_world, M) for x, y in zip(r1, r2))
    parts = list(root.children)

    report = dict(scale=K, bone=BONE, wrist_dist=WRIST_DIST,
                  strap_path_local=dict(center=[round(C.x, 4), round(C.y, 4)], mean_radius=round(r_mean, 4)),
                  bind_error=err, body_verts=body_vcount, rest=clearance(body, parts), poses={})

    cam = setup_render()
    renders = [render(cam, "00_fullbody_front", (0.0, -4.6, 0.95), (0.0, 0.0, 0.88), lens=50, res=(800, 1100)),
               closeup(cam, "01_wrist_closeup", root),
               render(cam, "02_wrist_closeup_side", root.matrix_world.translation + Vector((0.55, -0.15, 0.10)),
                      root.matrix_world.translation, lens=85)]

    cams = {
        "pose1_arm_down": ((1.5, -2.2, 1.3), (0.25, -0.05, 1.0)),
        "pose2_check_watch": ((0.9, -1.5, 2.1), (0.1, -0.25, 1.3)),
        "pose3_arm_forward": ((2.0, -1.4, 1.6), (0.15, -0.35, 1.25)),
    }
    for name, p in POSES.items():
        psi, tw = apply_pose(arm, root, p)
        report["poses"][name] = dict(upperarm_roll_deg=psi, forearm_twist_deg=round(tw, 1),
                                     clearance=clearance(body, parts),
                                     watch_pos=[round(x, 3) for x in root.matrix_world.translation])
        loc, tgt = cams[name]
        renders.append(render(cam, name, loc, tgt, lens=50))
        renders.append(closeup(cam, name + "_closeup", root))

    rest_pose(arm)   # saved file stays in rest pose
    report["body_verts_after"] = len(body.data.vertices)
    report["renders"] = renders
    with open(os.path.join(RENDER_DIR, "fit_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print("V5WATCH", json.dumps({k: v for k, v in report.items() if k != "renders"}))
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print("V5WATCH_SAVED", OUT_BLEND)


main()
