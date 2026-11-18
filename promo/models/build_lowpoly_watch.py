"""Build a low-poly Galaxy-Watch-like round smartwatch for a stylized cartoon character.

Run: blender -b -P build_lowpoly_watch.py [-- --no-render]
Units: meters (real size, case width ~0.045). Origin = display center, +Z out of screen,
+Y = 12 o'clock, +X = 3 o'clock (side buttons). Strap wraps toward -Z in the YZ plane.
Outputs (next to this script): lowpoly_watch.blend, lowpoly_watch.glb, renders/*.png
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_DIR = os.path.join(HERE, "renders")
SEG = 24  # round parts: enough sides to read as a circle, still faceted

# ---------------------------------------------------------------- helpers

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0


def make_material(name, color, metallic=0.0, roughness=0.5):
    m = bpy.data.materials.new(name)
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    m.diffuse_color = (*color, 1.0)
    m.metallic = metallic
    m.roughness = roughness
    return m


def finish_object(bm, name, mats, parent):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = False  # faceted low-poly look
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    return ob


def lathe(bm, profile, seg=SEG, cap_start=None, cap_end=None):
    """Revolve (r, z) profile around Z. Caps are triangle fans at the given z."""
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg),
                                    r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    for ring, z in ((rings[0], cap_start), (rings[-1], cap_end)):
        if z is None:
            continue
        c = bm.verts.new((0, 0, z))
        for i in range(seg):
            faces.append(bm.faces.new((c, ring[i], ring[(i + 1) % seg])))
    return rings, faces

# ---------------------------------------------------------------- parts

def build_case(root, mat):
    bm = bmesh.new()
    # (r, z) from the display well floor, up the inner bezel wall, over the bezel, down the side,
    # to the sensor back.
    profile = [
        (0.0178, -0.0010),   # well floor edge
        (0.0178, 0.0010),    # inner bezel wall top
        (0.0200, 0.0016),    # bezel flat
        (0.0222, 0.0004),    # bezel outer chamfer
        (0.0224, -0.0060),   # case side
        (0.0205, -0.0092),   # lower chamfer
        (0.0160, -0.0108),   # sensor dome edge
        (0.0080, -0.0118),   # sensor dome
    ]
    lathe(bm, profile, cap_start=-0.0010, cap_end=-0.0121)
    return finish_object(bm, "Watch_Case", [mat], root)


def build_display(root, mat):
    bm = bmesh.new()
    r = 0.0174
    rings, faces = lathe(bm, [(r, -0.0007), (r, 0.0003)], cap_start=-0.0007, cap_end=0.0003)
    ob = finish_object(bm, "Watch_Display", [mat], root)
    # Screen face: planar UV filling 0..1, so a square screen image (round face inscribed) maps
    # straight on. The hidden back and rim go into unused square corners outside that circle.
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        nz = poly.normal.z
        ca = math.atan2(poly.center.y, poly.center.x)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if nz > 0.5:      # front: the screen
                uv.data[li].uv = (co.x / (2 * r) + 0.5, co.y / (2 * r) + 0.5)
            elif nz < -0.5:   # back: small disc in the top-right corner
                uv.data[li].uv = (0.93 + co.x / r * 0.06, 0.93 + co.y / r * 0.06)
            else:             # rim: strip in the bottom-left corner
                a = math.atan2(co.y, co.x) % (2 * math.pi)
                if a < (ca % (2 * math.pi)) - math.pi:   # quad straddling the 0-degree seam
                    a += 2 * math.pi
                u = a / (2 * math.pi)
                uv.data[li].uv = (0.01 + u * 0.13, 0.01 + (co.z + 0.0007) / 0.001 * 0.02)
    return ob


def build_button(root, mat, name, y):
    bm = bmesh.new()
    # pill-ish block on the +X edge, sunk 0.6 mm into the case side
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 0.0022, v.co.y * 0.0050, v.co.z * 0.0026))
    # chamfer the 4 edges that run along X so it looks rounded from the side
    along_x = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) > 1e-6]
    bmesh.ops.bevel(bm, geom=along_x, offset=0.0007, segments=1, affect="EDGES", profile=0.5)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])  # no n-gons
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0222, y, -0.0034))
    return finish_object(bm, name, [mat], root)


# strap path: ellipse in the YZ plane around the wrist
EL_C = Vector((0.0, -0.0300))   # (y, z) center
EL_A, EL_B = 0.0320, 0.0300     # semi-axis along y, along z
STRAP_W, STRAP_T = 0.0200, 0.0026


def el_point(th):
    return Vector((EL_C.x + EL_A * math.sin(th), EL_C.y + EL_B * math.cos(th)))


def el_frame(th):
    """point, tangent (direction of increasing |th| path), outward normal; all (y, z)."""
    p = el_point(th)
    t = Vector((EL_A * math.cos(th), -EL_B * math.sin(th))).normalized()
    n = Vector((t.y, -t.x))
    if n.dot(p - EL_C) < 0:
        n = -n
    return p, t, n


def build_strap_piece(bm, th_start, th_end, holes, hole_mat_idx):
    """Swept rectangular band from th_start to th_end. holes: list of theta centers.
    Cross-section has 4 x-columns on the outer face so the middle cell can become a hole."""
    hole_half = 0.0016 / EL_A   # angular half-length of a hole (~3 mm long)
    step = math.radians(9)
    ths = []
    n = max(2, int(abs(th_end - th_start) / step) + 1)
    for i in range(n + 1):
        ths.append(th_start + (th_end - th_start) * i / n)
    for h in holes:
        ths += [h - hole_half, h + hole_half]
    sgn = 1 if th_end > th_start else -1
    ths = sorted(set(round(t, 6) for t in ths), key=lambda t: sgn * t)
    # drop path samples that crowd a hole edge
    keep = []
    edges = [h + d for h in holes for d in (-hole_half, hole_half)]
    for t in ths:
        if any(abs(t - e) < 1e-6 for e in edges) or all(abs(t - e) > hole_half * 0.9 for e in edges):
            keep.append(t)
    ths = keep
    xs = [-STRAP_W / 2, -0.0018, 0.0018, STRAP_W / 2]
    rings = []
    for th in ths:
        p, _, nrm = el_frame(th)
        outer = p + nrm * (STRAP_T / 2)
        inner = p - nrm * (STRAP_T / 2)
        ro = [bm.verts.new((x, outer.x, outer.y)) for x in xs]
        ri = [bm.verts.new((x, inner.x, inner.y)) for x in xs]
        rings.append((th, ro, ri))
    hole_faces = []
    for (ta, ao, ai), (tb, bo, bi) in zip(rings, rings[1:]):
        mid = (ta + tb) / 2
        is_hole = any(abs(mid - h) < hole_half for h in holes)
        for k in range(3):
            f = bm.faces.new((ao[k], ao[k + 1], bo[k + 1], bo[k]))
            if k == 1 and is_hole:
                hole_faces.append(f)
            bm.faces.new((ai[k], bi[k], bi[k + 1], ai[k + 1]))
        bm.faces.new((ao[0], bo[0], bi[0], ai[0]))
        bm.faces.new((ao[3], ai[3], bi[3], bo[3]))
    for _, o, i in (rings[0], rings[-1]):  # end caps as 3 quads
        for k in range(3):
            bm.faces.new((o[k], o[k + 1], i[k + 1], i[k]))
    return hole_faces


def build_strap(root, mat, hole_mat):
    bm = bmesh.new()
    a0 = math.radians(36)  # starts tucked under the case side
    # 12 o'clock strap with holes (long tail), 6 o'clock strap carries the buckle
    holes = [math.radians(d) for d in (112, 124, 136, 148, 160)]
    hole_faces = build_strap_piece(bm, a0, math.radians(176), holes, 1)
    build_strap_piece(bm, -a0, -math.radians(150), [], 1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # hole = inset the middle outer cell and push it into the strap (blind pocket, stays manifold)
    res = bmesh.ops.inset_individual(bm, faces=hole_faces, thickness=0.0004, depth=-0.0018)
    for f in hole_faces + list(res.get("faces", [])):
        f.material_index = 1
    return finish_object(bm, "Watch_Strap", [mat, hole_mat], root)


def build_buckle(root, mat):
    """Rectangular frame + prong at the free end of the 6 o'clock strap."""
    bm = bmesh.new()
    th = -math.radians(150)
    p, t, n = el_frame(th)
    t = -t if t.dot(el_point(th - 0.01) - p) < 0 else t  # point away from the strap
    # frame lies in the plane of (X, t), thickness along n
    def V(x, s, h):
        q = p + t * s + n * h
        return Vector((x, q.x, q.y))
    ox, ix = 0.0130, 0.0112            # outer / inner half-width
    s0, s1, s2, s3 = -0.0030, -0.0012, 0.0055, 0.0075  # along t: back bar, front bar
    hh = 0.0018                         # half thickness
    outer = [(-ox, s0), (ox, s0), (ox, s3), (-ox, s3)]
    inner = [(-ix, s1), (ix, s1), (ix, s2), (-ix, s2)]
    top_o = [bm.verts.new(V(x, s, hh)) for x, s in outer]
    top_i = [bm.verts.new(V(x, s, hh)) for x, s in inner]
    bot_o = [bm.verts.new(V(x, s, -hh)) for x, s in outer]
    bot_i = [bm.verts.new(V(x, s, -hh)) for x, s in inner]
    for k in range(4):
        j = (k + 1) % 4
        bm.faces.new((top_o[k], top_o[j], top_i[j], top_i[k]))
        bm.faces.new((bot_o[k], bot_i[k], bot_i[j], bot_o[j]))
        bm.faces.new((top_o[k], bot_o[k], bot_o[j], top_o[j]))
        bm.faces.new((top_i[k], top_i[j], bot_i[j], bot_i[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # prong: thin bar from the back bar across the opening, resting on the strap tail
    pr = bmesh.new()
    bmesh.ops.create_cube(pr, size=1.0)
    for v in pr.verts:
        # spans the opening, ends buried 0.4 mm inside both bars, top well below the frame top
        s = (s1 + s2) / 2 + v.co.y * (s2 - s1 + 0.0008)
        v.co = V(v.co.x * 0.0014, s, hh * 0.3 + v.co.z * 0.0012)
    tmp = bpy.data.meshes.new("tmp_prong")
    pr.to_mesh(tmp)
    pr.free()
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    return finish_object(bm, "Watch_Buckle", [mat], root)


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

# ---------------------------------------------------------------- render

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_render_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 900
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Review_World")
    sc.world = world
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.82, 0.83, 0.85, 1)
    bg.inputs["Strength"].default_value = 0.35
    col = bpy.data.collections.new("ReviewRig")  # lights/camera kept out of the export
    sc.collection.children.link(col)
    for name, loc, energy, size in (("Key", (0.25, -0.15, 0.30), 2.5, 0.25),
                                    ("Fill", (-0.30, -0.10, 0.12), 0.9, 0.30),
                                    ("Rim", (0.00, 0.30, 0.20), 1.5, 0.20)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = energy, size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        look_at(lo, (0, 0, -0.02))
        col.objects.link(lo)
    cam = bpy.data.objects.new("ReviewCam", bpy.data.cameras.new("ReviewCam"))
    cam.data.lens = 85
    cam.data.clip_start = 0.005
    col.objects.link(cam)
    sc.camera = cam
    return cam


def render_views(cam):
    os.makedirs(RENDER_DIR, exist_ok=True)
    target = Vector((0, 0, -0.024))
    views = {
        "front": ((0.0, 0.0, 0.30), (0, 0, -0.012)),
        "three_quarter_ref": ((0.15, -0.035, 0.15), (0, -0.004, -0.016)),
        "side_buttons": ((0.30, 0.0, -0.02), target),
        "side_profile": ((0.0001, -0.30, -0.02), target),
        "back_three_quarter": ((-0.17, 0.13, -0.19), target),
    }
    out = []
    for name, (loc, tgt) in views.items():
        cam.location = loc
        look_at(cam, tgt)
        path = os.path.join(RENDER_DIR, f"{name}.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out.append(path)
    return out

# ---------------------------------------------------------------- main

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    reset_scene()
    root = bpy.data.objects.new("LowPolyWatch", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.02
    bpy.context.scene.collection.objects.link(root)

    m_case = make_material("Watch_Case_Graphite", (0.105, 0.108, 0.115), 0.85, 0.32)
    m_disp = make_material("Watch_Display_Black", (0.004, 0.004, 0.005), 0.0, 0.08)
    m_strap = make_material("Watch_Strap_DarkGray", (0.075, 0.080, 0.088), 0.0, 0.72)
    m_hole = make_material("Watch_Strap_Hole", (0.012, 0.012, 0.014), 0.0, 0.9)
    m_buck = make_material("Watch_Buckle_Metal", (0.62, 0.63, 0.65), 1.0, 0.28)

    parts = [build_case(root, m_case), build_display(root, m_disp),
             build_button(root, m_case, "Watch_ButtonA", 0.0042),
             build_button(root, m_case, "Watch_ButtonB", -0.0042),
             build_strap(root, m_strap, m_hole), build_buckle(root, m_buck)]
    for ob in parts:
        if ob.name != "Watch_Display":
            smart_uv(ob)

    tris = {ob.name: sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob in parts}
    faces = {ob.name: len(ob.data.polygons) for ob in parts}
    print("WATCH_STATS faces", faces, "total", sum(faces.values()))
    print("WATCH_STATS tris", tris, "total", sum(tris.values()))
    print("WATCH_STATS width_x", round(max(v.co.x for v in parts[0].data.vertices) * 2, 4))

    blend = os.path.join(HERE, "lowpoly_watch.blend")
    glb = os.path.join(HERE, "lowpoly_watch.glb")
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for ob in parts:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True)
    if "--no-render" not in args:
        cam = setup_render_scene()
        print("WATCH_RENDERS", render_views(cam))
    else:
        setup_render_scene()
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("WATCH_SAVED", blend, glb)


if __name__ == "__main__":
    main()
