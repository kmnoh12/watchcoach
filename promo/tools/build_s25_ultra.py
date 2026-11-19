"""Procedural high-precision Samsung Galaxy S25 Ultra (Titanium Silverblue) model builder & studio renderer.

Official specs (Samsung / Namuwiki):
- Dimensions: 162.8 x 77.6 x 8.2 mm
- Display: 6.9" (174.2 mm), 19.5:9 (3120x1440), ~73.0 x 158.2 mm active area, ~1.32 mm bezel
- Finish: Titanium Silverblue matte glass back, Grade 5 brushed titanium flat rails,
          black concentric-ribbed camera rings with thin metallic outer rim.
- Screen object `S25U_Display_Screen` has clean 0..1 planar UVs and `S25U_Screen_Mat`
  pre-wired for instant image/video texture insertion (default: off/black AMOLED).
"""
import math
import os
import sys
import bpy
import bmesh
from mathutils import Matrix, Vector

OUT_BLEND = "/Users/kmnoh/Documents/Default Project/워치코치/promo/models/galaxy_s25_ultra.blend"
OUT_RENDER_DIR = "/Users/kmnoh/.gemini/antigravity/brain/0ae532d4-3484-44ce-96d6-9385d1c49684"
FONT_PATH = "/Users/kmnoh/Documents/Default Project/워치코치/promo/parts/fonts/NanumGothic-Bold.ttf"

# Dimensions in meters (1 mm = 0.001 m)
W = 0.0776      # X width
H = 0.1628      # Z height
D = 0.0082      # Y thickness (front is -Y, back is +Y)
CR = 0.0052     # Outer corner radius (5.2 mm)

# Display active area (6.9", 19.5:9)
SCR_W = 0.0730
SCR_H = 0.1582
SCR_CR = 0.0036


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def get_bsdf(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def make_mat(name, color, metallic=0.0, roughness=0.3, coat=0.0, coat_rough=0.05, ior=1.45, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = get_bsdf(m)
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = coat_rough
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = ior
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha
    return m


def make_screen_mat():
    """AMOLED screen material: black by default, pre-wired with Image Texture node `Screen_Image`."""
    m = bpy.data.materials.new("S25U_Screen_Mat")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = get_bsdf(m)
    bsdf.inputs["Base Color"].default_value = (0.006, 0.006, 0.008, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.035
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.02
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.65

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.name = "Screen_Image"
    tex.label = "Screen_Image (Drop Image/Video Here)"
    tex.location = (-520, 120)

    uv = nt.nodes.new("ShaderNodeTexCoord")
    uv.location = (-740, 120)
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])

    # Switch/strength: set Emission Strength > 0 (e.g. 1.2) when Screen_Image is assigned
    if "Emission Color" in bsdf.inputs:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 0.0
    return m


def rounded_rect_points(w, h, r, segs=12):
    """2D CCW points in (x, z) for a rounded rectangle centered at (0, 0)."""
    hx, hz = w * 0.5, h * 0.5
    r = min(r, hx * 0.99, hz * 0.99)
    centers = [
        (hx - r, hz - r, 0.0, math.pi * 0.5),
        (-hx + r, hz - r, math.pi * 0.5, math.pi),
        (-hx + r, -hz + r, math.pi, math.pi * 1.5),
        (hx - r, -hz + r, math.pi * 1.5, math.pi * 2.0),
    ]
    pts = []
    for cx, cz, a0, a1 in centers:
        for i in range(segs + 1):
            t = a0 + (a1 - a0) * (i / segs)
            pts.append((cx + r * math.cos(t), cz + r * math.sin(t)))
    return pts


def make_extruded_plate(name, w, h, r, y_front, y_back, bevel_w=0.0, bevel_segs=3, segs=14, mat=None, parent=None, coll=None, uv_planar=False):
    """Create a rounded-rect prism spanning y_front..y_back."""
    pts = rounded_rect_points(w, h, r, segs=segs)
    bm = bmesh.new()
    v_front = [bm.verts.new((x, y_front, z)) for x, z in pts]
    v_back = [bm.verts.new((x, y_back, z)) for x, z in pts]
    bm.verts.ensure_lookup_table()
    # Front face (-Y normal -> CW in XZ viewed from +Y, CCW viewed from -Y)
    bm.faces.new(v_front)
    bm.faces.new(list(reversed(v_back)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([v_front[j], v_front[i], v_back[i], v_back[j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    if bevel_w > 0:
        edges = [e for e in bm.edges if abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-6]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel_w, segments=bevel_segs, affect='EDGES', clamp_overlap=True, profile=0.55)

    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()

    for p in me.polygons:
        p.use_smooth = True

    if uv_planar:
        uv_layer = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                v = me.vertices[me.loops[li].vertex_index].co
                u = (v.x + w * 0.5) / w
                vv = (v.z + h * 0.5) / h
                uv_layer.data[li].uv = (max(0.0, min(1.0, u)), max(0.0, min(1.0, vv)))

    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    coll.objects.link(ob)
    if parent:
        ob.parent = parent
    return ob


def make_flat_screen(name, w, h, r, y_pos, mat, parent, coll):
    """Single-sided rounded-rect display plane facing -Y with exact 0..1 UVs."""
    pts = rounded_rect_points(w, h, r, segs=14)
    bm = bmesh.new()
    verts = [bm.verts.new((x, y_pos, z)) for x, z in pts]
    bm.faces.new(verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Ensure normal faces -Y
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()

    uv_layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            # Looking at front (-Y): left is -X (u=0), right is +X (u=1), bottom is -Z (v=0), top is +Z (v=1)
            u = (v.x + w * 0.5) / w
            vv = (v.z + h * 0.5) / h
            uv_layer.data[li].uv = (u, vv)

    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    return ob


def make_lathe_part(name, profile_rz, loc, mat, parent, coll, segs=64):
    """Revolve a 2D (radius, y_offset) profile around +Y axis at loc."""
    bm = bmesh.new()
    rings = []
    for r, dy in profile_rz:
        ring = []
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ring.append(bm.verts.new((r * math.cos(a), dy, r * math.sin(a))))
        rings.append(ring)
    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Split sharp edges (> 32 deg) so flat top rings stay razor-flat while cylinders stay smooth
    sharp = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(32)]
    if sharp:
        bmesh.ops.split_edges(bm, edges=sharp)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    coll.objects.link(ob)
    ob.parent = parent
    return ob


def add_camera_module(idx, x, z, outer_r, height, mode, mats, parent, coll, has_ring=True):
    """Build authentic Galaxy S25 Ultra camera island matching real close-up & 1:1 official back layout:
    - Big 3 lenses (has_ring=True): slender dark anodized metal top ring (~22% of radius, inner_r = 0.78 * outer_r)
      on a clean brushed-titanium silver outer cylinder wall, with subtle undercut neck.
    - Small 2 right modules (has_ring=False): NO black top ring — low-profile thin silver bezel rim
      holding full-diameter flush dark smoked glass (Laser AF / 3x Tele).
    mode: 'round' | 'periscope' | 'laser'
    """
    y0 = D * 0.5 - 0.00010
    base_loc = (x, y0, z)

    if has_ring:
        inner_r = outer_r * 0.775  # slender ~1.75mm ring width on 7.84mm radius (matches real close-up)

        # 1) Subtle dark undercut neck at base
        neck_profile = [
            (outer_r - 0.00040, 0.0),
            (outer_r - 0.00040, 0.00040),
            (outer_r - 0.00005, 0.00040),
            (outer_r - 0.00005, 0.0),
        ]
        make_lathe_part(f"S25U_CamNeck_{idx}", neck_profile, base_loc, mats["lens_dark"], parent, coll, segs=64)

        # 2) Clean brushed-titanium silver cylindrical side wall
        wall_top = height * 0.86
        wall_profile = [
            (outer_r - 0.00040, 0.00028),
            (outer_r - 0.00004, 0.00034),
            (outer_r,           0.00046),
            (outer_r,           wall_top - 0.00010),
            (outer_r - 0.00008, wall_top),
            (outer_r - 0.00045, wall_top),
            (outer_r - 0.00045, 0.00028),
        ]
        make_lathe_part(f"S25U_CamWall_{idx}", wall_profile, base_loc, mats["ti_frame"], parent, coll, segs=64)

        # 3) Slender flat anodized-black top bezel ring (satin metallic black)
        top_outer = outer_r - 0.00006
        cap_profile = [
            (top_outer,           wall_top - 0.00005),
            (top_outer,           height - 0.00012),
            (top_outer - 0.00014, height),
            (inner_r + 0.00014,   height),
            (inner_r,             height - 0.00014),
            (inner_r,             0.0),
        ]
        make_lathe_part(f"S25U_CamCap_{idx}", cap_profile, base_loc, mats["cam_ring"], parent, coll, segs=64)
    else:
        # Right 2 small sensors: NO thick black ring — just a razor-thin metallic rim + full black glass
        inner_r = outer_r * 0.915  # ultra-thin ~0.38mm outer metal rim only
        rim_profile = [
            (outer_r,           0.0),
            (outer_r,           height - 0.00010),
            (outer_r - 0.00010, height),
            (inner_r + 0.00008, height),
            (inner_r,           height - 0.00010),
            (inner_r,           0.0),
        ]
        make_lathe_part(f"S25U_CamRim_{idx}", rim_profile, base_loc, mats["ti_frame"], parent, coll, segs=64)

    # 4) Deep black inner well backing
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48, radius1=inner_r * 1.01, radius2=inner_r * 1.01, depth=0.00045)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'X'))
    me = bpy.data.meshes.new(f"S25U_CamWell_{idx}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats["lens_dark"])
    well = bpy.data.objects.new(f"S25U_CamWell_{idx}", me)
    well.location = (x, y0 + height - 0.00060, z)
    coll.objects.link(well)
    well.parent = parent

    # 5) Subtle dark inner lens pupil (omit for flat black Laser AF sensor)
    if mode == "periscope":
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, verts=bm.verts, vec=(inner_r * 0.52, 0.00025, inner_r * 0.44))
        me = bpy.data.meshes.new(f"S25U_CamOptic_{idx}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mats["lens_coat"])
        opt = bpy.data.objects.new(f"S25U_CamOptic_{idx}", me)
        opt.location = (x, y0 + height - 0.00038, z)
        coll.objects.link(opt)
        opt.parent = parent
    elif mode == "round":
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=36, radius1=inner_r * 0.30, radius2=inner_r * 0.26, depth=0.00030)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'X'))
        me = bpy.data.meshes.new(f"S25U_CamOptic_{idx}")
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(mats["lens_coat"])
        opt = bpy.data.objects.new(f"S25U_CamOptic_{idx}", me)
        opt.location = (x, y0 + height - 0.00038, z)
        coll.objects.link(opt)
        opt.parent = parent

    # 6) Flush flat dark smoked sapphire cover glass (flat-shaded top face, no dome distortion)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48, radius1=inner_r * 0.995, radius2=inner_r * 0.995, depth=0.00016)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'X'))
    me = bpy.data.meshes.new(f"S25U_CamGlass_{idx}")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(mats["lens_glass"])
    gl = bpy.data.objects.new(f"S25U_CamGlass_{idx}", me)
    gl.location = (x, y0 + height - 0.00010, z)
    coll.objects.link(gl)
    gl.parent = parent


def make_pill_box(name, sx, sy, sz, loc, mat, parent, coll, bevel=0.0004):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=bm.verts, vec=(sx, sy, sz))
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=3, affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    coll.objects.link(ob)
    ob.parent = parent
    return ob


def build_s25_ultra(coll, name_prefix="Galaxy_S25_Ultra"):
    root = bpy.data.objects.new(name_prefix, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.03
    coll.objects.link(root)

    # Materials tuned to Titanium Silverblue official reference images
    mats = {
        # Grade 5 brushed titanium frame: natural cool silver-titanium
        "ti_frame": make_mat("S25U_Titanium_Frame", (0.52, 0.55, 0.60), metallic=0.92, roughness=0.28, coat=0.10),
        # Titanium Silverblue frosted matte back glass: authentic cool silver-blue satin
        "back_glass": make_mat("S25U_Back_Silverblue", (0.36, 0.42, 0.56), metallic=0.32, roughness=0.34, coat=0.30, coat_rough=0.16),
        # Front black glass bezel around display
        "front_bezel": make_mat("S25U_Front_Bezel", (0.006, 0.006, 0.008), metallic=0.0, roughness=0.04, coat=1.0, coat_rough=0.02),
        # Display screen (off black by default, Image Texture node pre-wired)
        "screen": make_screen_mat(),
        # Satin dark anodized metallic top camera ring (matches real close-up sheen)
        "cam_ring": make_mat("S25U_Camera_Ring_Black", (0.015, 0.016, 0.018), metallic=0.65, roughness=0.28, coat=0.12),
        # Deep black optical well
        "lens_dark": make_mat("S25U_Lens_Well", (0.003, 0.003, 0.004), metallic=0.1, roughness=0.18),
        # Subtle deep dark-navy optical coating reflection (realistic, not bright blue)
        "lens_coat": make_mat("S25U_Lens_Coating", (0.007, 0.014, 0.045), metallic=0.65, roughness=0.05, coat=1.0, coat_rough=0.02),
        # Transparent protective lens glass
        "lens_glass": make_mat("S25U_Lens_Glass", (0.008, 0.010, 0.018), metallic=0.0, roughness=0.015, coat=1.0, coat_rough=0.01, ior=1.52, alpha=0.28),
        # LED Flash
        "flash": make_mat("S25U_LED_Flash", (0.85, 0.78, 0.62), metallic=0.12, roughness=0.25, coat=0.7),
        # Antenna band resin (slightly darker cool gray)
        "antenna": make_mat("S25U_Antenna_Band", (0.32, 0.35, 0.40), metallic=0.08, roughness=0.48),
        # Subtle back SAMSUNG wordmark
        "logo": make_mat("S25U_Logo_Silverblue", (0.20, 0.24, 0.34), metallic=0.50, roughness=0.34),
        # Port interior dark
        "port_dark": make_mat("S25U_Port_Dark", (0.010, 0.010, 0.012), metallic=0.3, roughness=0.5),
    }

    # Enable glass transparency for lens glass
    lg_bsdf = get_bsdf(mats["lens_glass"])
    if "Transmission Weight" in lg_bsdf.inputs:
        lg_bsdf.inputs["Transmission Weight"].default_value = 0.85

    # 1) Titanium Outer Frame (flat rails, subtle top/bottom chamfer)
    make_extruded_plate(
        "S25U_Titanium_Frame", W, H, CR,
        y_front=-D * 0.5, y_back=D * 0.5,
        bevel_w=0.00045, bevel_segs=3, segs=16,
        mat=mats["ti_frame"], parent=root, coll=coll,
    )

    # 2) Back Glass Panel (Titanium Silverblue matte glass, inset 0.85mm from titanium rail edge)
    make_extruded_plate(
        "S25U_Back_Glass", W - 0.0017, H - 0.0017, CR - 0.0008,
        y_front=D * 0.5 - 0.0005, y_back=D * 0.5 + 0.00008,
        bevel_w=0.00018, bevel_segs=2, segs=16,
        mat=mats["back_glass"], parent=root, coll=coll,
    )

    # 3) Front Black Glass Bezel (inset 0.85mm from titanium rail edge)
    make_extruded_plate(
        "S25U_Front_Bezel", W - 0.0017, H - 0.0017, CR - 0.0008,
        y_front=-D * 0.5 - 0.00008, y_back=-D * 0.5 + 0.0005,
        bevel_w=0.00015, bevel_segs=2, segs=16,
        mat=mats["front_bezel"], parent=root, coll=coll,
    )

    # 4) Active 6.9" Display Surface (separate object, exact 0..1 planar UVs, black by default)
    make_flat_screen(
        "S25U_Display_Screen", SCR_W, SCR_H, SCR_CR,
        y_pos=-D * 0.5 - 0.00014,
        mat=mats["screen"], parent=root, coll=coll,
    )

    # 5) Front Punch-Hole Camera (top center, 4.8 mm below top display edge, 3.2 mm dia)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=0.0016, radius2=0.0016, depth=0.00015)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'X'))
    me = bpy.data.meshes.new("S25U_Front_Camera")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats["lens_dark"])
    fcam = bpy.data.objects.new("S25U_Front_Camera", me)
    fcam.location = (0.0, -D * 0.5 - 0.00020, SCR_H * 0.5 - 0.0048)
    coll.objects.link(fcam)
    fcam.parent = root

    # Front camera tiny blue lens reflection dot
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24, radius1=0.00065, radius2=0.00065, depth=0.00010)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'X'))
    me = bpy.data.meshes.new("S25U_Front_Camera_Lens")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats["lens_coat"])
    fcl = bpy.data.objects.new("S25U_Front_Camera_Lens", me)
    fcl.location = (0.0, -D * 0.5 - 0.00025, SCR_H * 0.5 - 0.0048)
    coll.objects.link(fcl)
    fcl.parent = root

    # Top earpiece speaker slit
    make_pill_box("S25U_Earpiece", 0.014, 0.0003, 0.00055, (0.0, -D * 0.5 - 0.00005, H * 0.5 - 0.0011), mats["port_dark"], root, coll, bevel=0.0001)

    # 6) Rear Camera Array (viewed from +Y back: left side of back is +X! Wait: let's verify!)
    # Viewed from front (-Y looking +Y): +X is RIGHT, -X is LEFT.
    # Viewed from back (+Y looking -Y): +X is LEFT, -X is RIGHT!
    # In official back photos (images 1, 3, 4), the 3 big lenses are on the TOP-LEFT of the back!
    # Therefore on +Y back face, top-left is POSITIVE X (+0.0215 m)!
    # And the power/volume buttons are on the RIGHT side when viewing front (+X), which is LEFT edge when viewing back (+X)!
    # Let's double check image 4: looking at the back, buttons are on the LEFT rail right next to the 3 big lenses! YES!! Both at +X!
    # Pixel-measured 1:1 from official S25 Ultra back render:
    # Big 3 lenses: x=+24.2mm, z=+66.1 / +48.1 / +30.2mm, outer_r=7.84mm (dia 15.7mm)
    # Small 2 right modules: x=+7.4mm, z=+66.1 / +48.1mm (aligned with top 2 big lenses!), outer_r=4.52mm (dia 9.0mm), NO black ring
    big_x = +0.0242
    small_x = +0.0074
    add_camera_module("UltraWide", big_x, +0.0661, 0.00784, 0.0022, "round",     mats, root, coll, has_ring=True)
    add_camera_module("Main200MP", big_x, +0.0481, 0.00784, 0.0022, "round",     mats, root, coll, has_ring=True)
    add_camera_module("Tele5x",    big_x, +0.0302, 0.00784, 0.0022, "periscope", mats, root, coll, has_ring=True)
    add_camera_module("LaserAF",   small_x, +0.0661, 0.00452, 0.0008, "laser",   mats, root, coll, has_ring=False)
    add_camera_module("Tele3x",    small_x, +0.0481, 0.00452, 0.0008, "round",   mats, root, coll, has_ring=False)

    # LED Flash (centered between LaserAF +66.1mm and Tele3x +48.1mm -> +57.1mm)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=0.0018, radius2=0.0018, depth=0.00020)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'X'))
    me = bpy.data.meshes.new("S25U_LED_Flash")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats["flash"])
    fl = bpy.data.objects.new("S25U_LED_Flash", me)
    fl.location = (small_x, D * 0.5 + 0.00010, +0.0571)
    coll.objects.link(fl)
    fl.parent = root

    # 7) Right-side Titanium Buttons (front-right = +X)
    # Volume rocker (upper) & Power button (lower)
    make_pill_box("S25U_Btn_Volume", 0.0014, 0.0025, 0.0225, (W * 0.5 + 0.00035, 0.0, +0.0320), mats["ti_frame"], root, coll, bevel=0.00045)
    make_pill_box("S25U_Btn_Power",  0.0014, 0.0025, 0.0115, (W * 0.5 + 0.00035, 0.0, +0.0085), mats["ti_frame"], root, coll, bevel=0.00045)

    # 8) Antenna bands on titanium side rails (top & bottom on both sides)
    for sx in (-W * 0.5, W * 0.5):
        for az in (+0.0685, -0.0685):
            make_pill_box(f"S25U_Antenna_{sx>0}_{az>0}", 0.00025, D - 0.0012, 0.0014, (sx, 0.0, az), mats["antenna"], root, coll, bevel=0.00005)

    # 9) Bottom edge details: USB-C port, S-Pen slot cap (front-left = -X), speaker slit
    make_pill_box("S25U_USBC_Port", 0.0092, 0.0032, 0.0006, (0.0, 0.0, -H * 0.5 + 0.0001), mats["port_dark"], root, coll, bevel=0.00025)
    make_pill_box("S25U_SPen_Cap",  0.0062, 0.0044, 0.0006, (-0.0275, 0.0, -H * 0.5 - 0.00008), mats["ti_frame"], root, coll, bevel=0.0003)
    make_pill_box("S25U_Speaker",   0.0110, 0.0014, 0.0005, (-0.0155, 0.0, -H * 0.5 + 0.0001), mats["port_dark"], root, coll, bevel=0.00015)

    # 10) Back SAMSUNG wordmark (subtle low-contrast metallic print near bottom center)
    cu = bpy.data.curves.new("S25U_Logo_Curve", "FONT")
    cu.body = "SAMSUNG"
    cu.size = 0.0046
    cu.space_character = 1.18
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.00004
    if os.path.exists(FONT_PATH):
        fnt = bpy.data.fonts.load(FONT_PATH, check_existing=True)
        if not fnt.packed_file:
            fnt.pack()
        cu.font = fnt
    tmp = bpy.data.objects.new("S25U_Logo_tmp", cu)
    coll.objects.link(tmp)
    tmp.location = (0.0, D * 0.5 + 0.00011, -0.0535)
    tmp.rotation_euler = (math.radians(90), 0.0, math.radians(180))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    me.materials.append(mats["logo"])
    logo = bpy.data.objects.new("S25U_Logo", me)
    logo.location = tmp.location
    logo.rotation_euler = tmp.rotation_euler
    coll.objects.link(logo)
    logo.parent = root
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)

    return root


def duplicate_hierarchy(root, coll, offset_loc, rot_euler):
    """Create a linked duplicate of the phone hierarchy for studio showcase renders."""
    new_root = bpy.data.objects.new(root.name + "_Copy", None)
    new_root.location = offset_loc
    new_root.rotation_euler = rot_euler
    coll.objects.link(new_root)
    for child in root.children:
        c = child.copy()
        c.parent = new_root
        coll.objects.link(c)
    return new_root


def setup_studio(scene):
    scene.render.engine = 'CYCLES'
    # Try Apple Silicon Metal GPU; fallback to CPU
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        has_gpu = False
        for d in prefs.devices:
            if d.type == 'METAL':
                d.use = True
                has_gpu = True
        scene.cycles.device = 'GPU' if has_gpu else 'CPU'
    except Exception:
        scene.cycles.device = 'CPU'

    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'IMAGE'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'

    # Clean dark-neutral studio world with subtle soft gradient
    w = bpy.data.worlds.new("StudioWorld")
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.030, 0.034, 0.045, 1.0)
    bg.inputs["Strength"].default_value = 0.45

    # Balanced soft studio area lights (no blown-out highlights on matte silver-blue glass)
    lights = [
        ("KeyLight",  (0.42, -0.45, 0.30), (math.radians(56), 0, math.radians(42)), 7.5, 0.50, (1.0, 0.99, 0.98)),
        ("FillLight", (-0.45, -0.35, 0.16), (math.radians(70), 0, math.radians(-52)), 4.2, 0.55, (0.86, 0.92, 1.0)),
        ("BackKey",   (-0.36, 0.48, 0.28), (math.radians(60), 0, math.radians(-140)), 6.5, 0.50, (0.98, 0.99, 1.0)),
        ("BackRim",   (0.38, 0.38, 0.22),  (math.radians(62), 0, math.radians(135)), 4.0, 0.45, (0.85, 0.91, 1.0)),
        ("TopStrip",  (0.0, 0.0, 0.52),    (0.0, 0.0, 0.0), 3.0, 0.50, (0.95, 0.97, 1.0)),
    ]
    for lname, loc, rot, energy, size, col in lights:
        ld = bpy.data.lights.new(lname, type='AREA')
        ld.energy = energy
        ld.size = size
        ld.color = col
        lo = bpy.data.objects.new(lname, ld)
        lo.location = loc
        lo.rotation_euler = rot
        scene.collection.objects.link(lo)


def aim_cam(cam, loc, target):
    cam.location = Vector(loc)
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def main():
    clear_scene()
    scene = bpy.context.scene
    phone_coll = bpy.data.collections.new("Galaxy_S25_Ultra")
    scene.collection.children.link(phone_coll)

    root = build_s25_ultra(phone_coll)

    # Save clean asset .blend (just the phone at origin, ready to append into any reel scene!)
    os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print("SAVED_BLEND:", OUT_BLEND)

    # Now set up temporary studio lighting & cameras for showcase renders (do NOT overwrite .blend)
    studio_coll = bpy.data.collections.new("STUDIO_TMP")
    scene.collection.children.link(studio_coll)
    setup_studio(scene)

    cam_data = bpy.data.cameras.new("StudioCam")
    cam_obj = bpy.data.objects.new("StudioCam", cam_data)
    studio_coll.objects.link(cam_obj)
    scene.camera = cam_obj

    # 1) Hero 3/4 Dual Shot (Full Back + Full Front side by side with generous framing)
    root.location = (-0.048, 0.0, 0.0)
    root.rotation_euler = (math.radians(-6), math.radians(4), math.radians(160))
    front_copy = duplicate_hierarchy(root, studio_coll, (+0.048, 0.008, 0.0), (math.radians(-6), math.radians(-4), math.radians(-18)))

    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    cam_data.lens = 68
    aim_cam(cam_obj, (0.0, -0.58, 0.02), (0.0, 0.0, 0.0))
    scene.render.filepath = f"{OUT_RENDER_DIR}/s25u_hero_pair.png"
    bpy.ops.render.render(write_still=True)

    # 2) Dramatic Back Camera & Titanium Rail Close-up (like Samsung official key art!)
    front_copy.hide_render = True
    for c in front_copy.children:
        c.hide_render = True
    root.location = (0.0, 0.0, 0.0)
    root.rotation_euler = (0.0, 0.0, 0.0)

    scene.render.resolution_x = 1280
    scene.render.resolution_y = 920
    cam_data.lens = 82
    aim_cam(cam_obj, (0.125, 0.165, 0.095), (0.017, 0.004, 0.049))
    scene.render.filepath = f"{OUT_RENDER_DIR}/s25u_camera_closeup.png"
    bpy.ops.render.render(write_still=True)

    # 3) Clean Full Front + Back Straight-On Pair
    front_copy.hide_render = False
    for c in front_copy.children:
        c.hide_render = False
    root.location = (-0.046, 0.0, 0.0)
    root.rotation_euler = (0.0, 0.0, math.radians(180))  # back facing -Y
    front_copy.location = (+0.046, 0.0, 0.0)
    front_copy.rotation_euler = (0.0, 0.0, 0.0)          # front facing -Y

    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1000
    cam_data.lens = 85
    aim_cam(cam_obj, (0.0, -0.66, 0.0), (0.0, 0.0, 0.0))
    scene.render.filepath = f"{OUT_RENDER_DIR}/s25u_front_back.png"
    bpy.ops.render.render(write_still=True)

    print("S25U_STUDIO_DONE")


if __name__ == "__main__":
    main()
