"""Detail pass 8b: Replace Elev_XBanner_Mart (Opus Mart) with two steel-frame banner stands.

Deletes `Elev_XBanner_Mart` (and all its child canvas/pole/tank objects + orphan meshes/materials/images)
and installs two side-by-side black rectangular steel-frame banner stands matching
`work/banners_20261128/ref_two_banners.jpg` (no planter/flowers):
  - Left stand : `promo/parts/detail8_elevator_real/banner_left_neonmart.png` (860x2330, exact aspect)
  - Right stand: `promo/parts/detail8_elevator_real/banner_right_astratelecom.png` (830x2330, exact aspect)

100% idempotent. Keeps all neighboring objects (Elev_XBanner_Golf, walls, extinguisher,
tactile blocks, delivery boxes) collision-free and untouched.

Usage (never saves unless --save <path> is given):
  Blender -b promo/scenes/scene_gym.blend --python-exit-code 1 -P promo/tools/detail8_banner_stands.py [-- --save out.blend]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

KEY = "detail8_banner_stands"
COLL = "DETAIL8_banner_stands"
PFX = "D8banner_"

REPO_ROOT = Path(__file__).resolve().parents[2]
TEX_DIR = REPO_ROOT / "promo" / "parts" / "detail8_elevator_real"
IMG_LEFT = "banner_left_neonmart.png"
IMG_RIGHT = "banner_right_astratelecom.png"

# Exact native image aspect ratios (width / height) -> zero stretching
LEFT_ASPECT = 860.0 / 2330.0    # 0.3691 -> 0.5352 m x 1.450 m
RIGHT_ASPECT = 830.0 / 2330.0   # 0.3562 -> 0.5165 m x 1.450 m


def _remove_tree(ob) -> tuple[int, set, set]:
    import bpy
    removed = 0
    cand_mats, cand_data = set(), set()
    for ch in list(ob.children):
        r, ms, ds = _remove_tree(ch)
        removed += r
        cand_mats |= ms
        cand_data |= ds
    if hasattr(ob, "material_slots"):
        for sl in ob.material_slots:
            if sl.material is not None:
                cand_mats.add(sl.material)
    if ob.data is not None:
        cand_data.add(ob.data)
    bpy.data.objects.remove(ob, do_unlink=True)
    return removed + 1, cand_mats, cand_data


def _purge_orphans(cand_data: set, cand_mats: set):
    import bpy
    cand_imgs = set()
    for m in list(cand_mats):
        try:
            if m.users == 0:
                if m.node_tree:
                    for n in m.node_tree.nodes:
                        if n.type == "TEX_IMAGE" and n.image is not None:
                            cand_imgs.add(n.image)
                bpy.data.materials.remove(m)
        except ReferenceError:
            pass
    for d in list(cand_data):
        try:
            if d.users != 0:
                continue
            if isinstance(d, bpy.types.Mesh):
                bpy.data.meshes.remove(d)
            elif isinstance(d, bpy.types.Curve):
                bpy.data.curves.remove(d)
        except ReferenceError:
            pass
    for im in list(cand_imgs):
        try:
            if im.users == 0:
                bpy.data.images.remove(im)
        except ReferenceError:
            pass


def _cleanup_existing():
    import bpy
    coll = bpy.data.collections.get(COLL)
    cand_data, cand_mats = set(), set()
    if coll:
        for name in [o.name for o in coll.objects]:
            ob = bpy.data.objects.get(name)
            if ob is not None:
                _, ms, ds = _remove_tree(ob)
                cand_mats |= ms
                cand_data |= ds
        bpy.data.collections.remove(coll)
    for m in list(bpy.data.materials):
        if m.name.startswith(PFX) and m.users == 0:
            cand_mats.add(m)
    _purge_orphans(cand_data, cand_mats)


def _new_mat(name: str):
    import bpy
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf


def _mat_metal(name: str, color: tuple, rough: float, metal: float):
    m, _, b = _new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = 0.5
    m.diffuse_color = (*color, 1.0)
    return m


def _mat_banner_print(name: str, fname: str):
    import bpy
    path = str(TEX_DIR / fname)
    for im in list(bpy.data.images):
        if im.name == fname and im.users == 0:
            bpy.data.images.remove(im)
    im = bpy.data.images.load(path, check_existing=False)
    im.name = fname
    im.pack()

    m, nt, b = _new_mat(name)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = im
    tex.extension = "EXTEND"
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.nodes.active = tex
    # Semi-matte PET banner sheet (realistic print finish, subtle sheen)
    b.inputs["Roughness"].default_value = 0.36
    b.inputs["Specular IOR Level"].default_value = 0.42
    m.diffuse_color = (0.85, 0.85, 0.85, 1.0)
    return m


def _bm_box(bm, lo: tuple, hi: tuple, mat_idx: int = 0, bevel: float = 0.0):
    import bmesh
    from mathutils import Matrix, Vector
    lo_v, hi_v = Vector(lo), Vector(hi)
    ctr = (lo_v + hi_v) * 0.5
    sz = hi_v - lo_v
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(ctr) @ Matrix.Diagonal((sz.x, sz.y, sz.z, 1.0)))
    verts = res["verts"]
    faces = list({f for v in verts for f in v.link_faces})
    edges = list({e for v in verts for e in v.link_edges})
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=1,
                        affect="EDGES", profile=0.5, clamp_overlap=True)
        faces = list(bm.faces)
    for f in faces:
        if f.material_index == 0:
            f.material_index = mat_idx


def _build_banner_stand(coll, name: str, world_xy: tuple, yaw_deg: float,
                        canvas_h: float, aspect: float,
                        mat_frame, mat_base, mat_chrome, mat_back, mat_print):
    """Build one Korean steel-frame banner stand in its own local frame, placed in world space.

    Local axes of stand:
      +Y = front normal (direction printed banner faces)
      +X = viewer's LEFT when looking at front? Wait: looking toward -Y with +Z up,
           viewer's RIGHT is -X, viewer's LEFT is +X.
      +Z = up (z=0 floor)
    `yaw_deg`: angle of stand front normal (+Y) rotated clockwise from +Y toward +X
               (0 deg -> faces +Y; 65 deg -> faces (+sin 65, +cos 65) = east-northeast).
    """
    import bmesh, bpy
    from mathutils import Matrix

    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    root.location = (world_xy[0], world_xy[1], 0.0)
    # Local +Y rotated by -yaw_deg around Z gives (+sin(yaw), +cos(yaw))
    root.rotation_euler = (0.0, 0.0, -math.radians(yaw_deg))

    cw = canvas_h * aspect     # exact aspect width (~0.535 m or ~0.517 m)
    gap_r = 0.012              # 12 mm reveal between printed sheet and steel frame
    tube = 0.022               # 22 mm square black steel tube
    frame_w = cw + 2.0 * gap_r + 2.0 * tube   # ~0.603 m / 0.585 m
    base_w = frame_w + 0.008   # ~0.61 m / 0.59 m
    base_d = 0.260             # 26 cm deep weighted black box
    base_h = 0.230             # 23 cm tall base box
    leg_gap = 0.120            # 12 cm open leg reveal between base top and bottom rail

    z_rail_bot0 = base_h + leg_gap              # 0.350 m
    z_rail_bot1 = z_rail_bot0 + tube            # 0.372 m
    z_canv0 = z_rail_bot1 + gap_r               # 0.384 m
    z_canv1 = z_canv0 + canvas_h                # 1.834 m
    z_rail_top0 = z_canv1 + gap_r               # 1.846 m
    z_rail_top1 = z_rail_top0 + tube            # 1.868 m (~1.85 m total height)

    # 1) Weighted matte-black base box + tiny bottom pads
    bm_base = bmesh.new()
    _bm_box(bm_base, (-base_w / 2, -base_d / 2, 0.004), (base_w / 2, base_d / 2, base_h), 0, bevel=0.003)
    # 4 corner rubber leveling pads touching z=0.000
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = sx * (base_w / 2 - 0.04), sy * (base_d / 2 - 0.035)
            _bm_box(bm_base, (px - 0.02, py - 0.02, 0.0), (px + 0.02, py + 0.02, 0.005), 0)
    bmesh.ops.recalc_face_normals(bm_base, faces=bm_base.faces)
    me_base = bpy.data.meshes.new(name + "_Base")
    bm_base.to_mesh(me_base)
    bm_base.free()
    me_base.materials.append(mat_base)
    ob_base = bpy.data.objects.new(name + "_Base", me_base)
    coll.objects.link(ob_base)
    ob_base.parent = root

    # 2) Black powder-coated steel rectangular frame + two vertical legs + socket collars
    bm_fr = bmesh.new()
    hw_out = frame_w / 2.0
    hw_in = hw_out - tube
    ht = tube / 2.0
    # Left & right continuous upright tubes (from inside base up to top corner)
    _bm_box(bm_fr, (-hw_out, -ht, base_h - 0.01), (-hw_in, ht, z_rail_top1), 0, bevel=0.0018)
    _bm_box(bm_fr, (hw_in, -ht, base_h - 0.01), (hw_out, ht, z_rail_top1), 0, bevel=0.0018)
    # Bottom & top horizontal crossbars
    _bm_box(bm_fr, (-hw_in - 0.001, -ht, z_rail_bot0), (hw_in + 0.001, ht, z_rail_bot1), 0, bevel=0.0018)
    _bm_box(bm_fr, (-hw_in - 0.001, -ht, z_rail_top0), (hw_in + 0.001, ht, z_rail_top1), 0, bevel=0.0018)
    # Small square collar flanges where legs meet base top
    for lx in (-(hw_out + hw_in) / 2, (hw_out + hw_in) / 2):
        _bm_box(bm_fr, (lx - 0.019, -0.019, base_h - 0.002), (lx + 0.019, 0.019, base_h + 0.012), 0, bevel=0.001)
    # 4 corner diagonal tension hooks tying banner corners to inner frame corners
    for sx in (-1, 1):
        for z_c, dz in ((z_canv0, -1), (z_canv1, 1)):
            cx0 = sx * (cw / 2.0 - 0.004)
            cx1 = sx * (hw_in + 0.001)
            cz0 = z_c - dz * 0.004
            cz1 = z_c + dz * (gap_r + 0.001)
            _bm_box(bm_fr, (min(cx0, cx1), -0.0025, min(cz0, cz1)),
                    (max(cx0, cx1), 0.0025, max(cz0, cz1)), 0)
    bmesh.ops.recalc_face_normals(bm_fr, faces=bm_fr.faces)
    me_fr = bpy.data.meshes.new(name + "_Frame")
    bm_fr.to_mesh(me_fr)
    bm_fr.free()
    me_fr.materials.append(mat_frame)
    ob_fr = bpy.data.objects.new(name + "_Frame", me_fr)
    coll.objects.link(ob_fr)
    ob_fr.parent = root

    # 3) Tiny silver corner grommet rings on the 4 corners of the banner
    bm_gr = bmesh.new()
    for sx in (-1, 1):
        for gz in (z_canv0 + 0.015, z_canv1 - 0.015):
            gx = sx * (cw / 2.0 - 0.015)
            bmesh.ops.create_cone(
                bm_gr, cap_ends=True, segments=14, radius1=0.0055, radius2=0.0055, depth=0.0032,
                matrix=Matrix.Translation((gx, 0.0, gz)) @ Matrix.Rotation(math.pi / 2, 4, "X"),
            )
    bmesh.ops.recalc_face_normals(bm_gr, faces=bm_gr.faces)
    me_gr = bpy.data.meshes.new(name + "_Grommets")
    bm_gr.to_mesh(me_gr)
    bm_gr.free()
    me_gr.materials.append(mat_chrome)
    ob_gr = bpy.data.objects.new(name + "_Grommets", me_gr)
    coll.objects.link(ob_gr)
    ob_gr.parent = root

    # 4) Printed PET banner sheet (2 mm thick: front +Y face = printed image, back & edges = white vinyl)
    bm_cv = bmesh.new()
    hcw = cw / 2.0
    hy = 0.0010
    # 8 vertices: front (+Y) and back (-Y)
    # Looking at front (+Y face) from +Y toward -Y: viewer's LEFT is +X, viewer's RIGHT is -X!
    f0 = bm_cv.verts.new(( hcw,  hy, z_canv0))   # bottom-left (u=0, v=0)
    f1 = bm_cv.verts.new((-hcw,  hy, z_canv0))   # bottom-right (u=1, v=0)
    f2 = bm_cv.verts.new((-hcw,  hy, z_canv1))   # top-right (u=1, v=1)
    f3 = bm_cv.verts.new(( hcw,  hy, z_canv1))   # top-left (u=0, v=1)
    b0 = bm_cv.verts.new(( hcw, -hy, z_canv0))
    b1 = bm_cv.verts.new((-hcw, -hy, z_canv0))
    b2 = bm_cv.verts.new((-hcw, -hy, z_canv1))
    b3 = bm_cv.verts.new(( hcw, -hy, z_canv1))

    # Front face normal must face +Y: (f0 -> f1 -> f2 -> f3) has normal (-1,0,0)x(0,0,1) = (0,+1,0)!
    f_front = bm_cv.faces.new((f0, f1, f2, f3))
    f_front.material_index = 0
    f_back = bm_cv.faces.new((b3, b2, b1, b0))
    f_back.material_index = 1
    for quad in ((f0, b0, b1, f1), (f1, b1, b2, f2), (f2, b2, b3, f3), (f3, b3, b0, f0)):
        sf = bm_cv.faces.new(quad)
        sf.material_index = 1
    bmesh.ops.recalc_face_normals(bm_cv, faces=bm_cv.faces)

    uv = bm_cv.loops.layers.uv.new("UVMap")
    uv_map = {f0: (0.0, 0.0), f1: (1.0, 0.0), f2: (1.0, 1.0), f3: (0.0, 1.0)}
    for loop in f_front.loops:
        loop[uv].uv = uv_map[loop.vert]

    me_cv = bpy.data.meshes.new(name + "_Canvas")
    bm_cv.to_mesh(me_cv)
    bm_cv.free()
    me_cv.materials.append(mat_print)
    me_cv.materials.append(mat_back)
    ob_cv = bpy.data.objects.new(name + "_Canvas", me_cv)
    coll.objects.link(ob_cv)
    ob_cv.parent = root

    return root, [ob_base, ob_fr, ob_gr, ob_cv]


def apply() -> dict:
    import bpy
    from mathutils import Vector

    _cleanup_existing()

    # 1) Completely DELETE Elev_XBanner_Mart (and all children + orphan data/materials/images)
    mart_deleted = 0
    cand_mats, cand_data = set(), set()
    mart = bpy.data.objects.get("Elev_XBanner_Mart")
    if mart is not None:
        mart_deleted, cand_mats, cand_data = _remove_tree(mart)
    # Also catch any detached leftovers by name just in case
    for extra in ("Elev_XBanner_Mart_canvas", "Elev_XBanner_Mart_pole", "Elev_XBanner_Mart_tank"):
        ob = bpy.data.objects.get(extra)
        if ob is not None:
            r, ms, ds = _remove_tree(ob)
            mart_deleted += r
            cand_mats |= ms
            cand_data |= ds
    _purge_orphans(cand_data, cand_mats)

    set_c = bpy.data.collections["SET"]
    coll = bpy.data.collections.new(COLL)
    set_c.children.link(coll)

    # 2) Materials
    m_frame = _mat_metal(PFX + "FrameBlackSteel", (0.025, 0.026, 0.028), rough=0.34, metal=0.72)
    m_base = _mat_metal(PFX + "BaseBlackBox", (0.022, 0.023, 0.025), rough=0.40, metal=0.45)
    m_chrome = _mat_metal(PFX + "GrommetSilver", (0.78, 0.80, 0.82), rough=0.18, metal=0.95)
    m_back = _mat_metal(PFX + "VinylWhiteBack", (0.82, 0.82, 0.80), rough=0.58, metal=0.0)
    m_left = _mat_banner_print(PFX + "Print_NeonMart", IMG_LEFT)
    m_right = _mat_banner_print(PFX + "Print_AstraTelecom", IMG_RIGHT)

    # 3) Place the two stands neatly side by side along the west wall in the old Mart spot
    # Both share yaw = 62 deg (facing +X/+Y toward the corridor viewer cleanly),
    # separated by 0.625 m side-by-side (~3 cm gap between outer frames).
    # Verified clear of: west wall plinth (x=-10.33), Elev_XBanner_Golf (y<=-16.45),
    # DeliveryBox_Bottom (y>=-14.74), tactile patch, and elevator doors.
    yaw_deg = 62.0
    th = math.radians(yaw_deg)
    rx, ry = -math.cos(th), math.sin(th)   # unit vector from Left stand -> Right stand
    ctr_x, ctr_y = -9.915, -15.775
    half_sep = 0.312                       # 0.624 m center-to-center (~3 cm frame gap)

    pos_left = (ctr_x - rx * half_sep, ctr_y - ry * half_sep)
    pos_right = (ctr_x + rx * half_sep, ctr_y + ry * half_sep)

    _, parts_l = _build_banner_stand(
        coll, PFX + "Stand_Left_NeonMart", pos_left, yaw_deg,
        canvas_h=1.450, aspect=LEFT_ASPECT,
        mat_frame=m_frame, mat_base=m_base, mat_chrome=m_chrome, mat_back=m_back, mat_print=m_left,
    )
    _, parts_r = _build_banner_stand(
        coll, PFX + "Stand_Right_AstraTelecom", pos_right, yaw_deg,
        canvas_h=1.450, aspect=RIGHT_ASPECT,
        mat_frame=m_frame, mat_base=m_base, mat_chrome=m_chrome, mat_back=m_back, mat_print=m_right,
    )

    bpy.context.view_layer.update()

    # World bounds report for collision verification
    bounds = {}
    tris = 0
    for tag, parts in (("left_neonmart", parts_l), ("right_astratelecom", parts_r)):
        pts = []
        for ob in parts:
            ob.data.calc_loop_triangles()
            tris += len(ob.data.loop_triangles)
            pts.extend(ob.matrix_world @ Vector(c) for c in ob.bound_box)
        bounds[tag] = {
            "x": [round(min(p.x for p in pts), 3), round(max(p.x for p in pts), 3)],
            "y": [round(min(p.y for p in pts), 3), round(max(p.y for p in pts), 3)],
            "z": [round(min(p.z for p in pts), 3), round(max(p.z for p in pts), 3)],
        }

    return {
        "collection": COLL,
        "mart_deleted": mart_deleted,
        "objects_added": len(coll.objects),
        "triangles_added": tris,
        "bounds": bounds,
    }


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    info = apply()
    print("D8BANNER APPLY", info, flush=True)
    if "--save" in argv:
        import bpy
        out = argv[argv.index("--save") + 1]
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print("D8BANNER SAVED", out, flush=True)


if __name__ == "__main__":
    _main()
