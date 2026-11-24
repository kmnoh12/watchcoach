"""WatchCoach Gym Expansion: 4 real architectural doors (Main Entrance + Exit Sign, Posing Room, Men/Women Locker Suites)
and modular interior annex rooms (Posing Room, Men's & Women's Locker -> Shower -> Restroom suites)."""
import math
import os
import bmesh
import bpy
from mathutils import Matrix, Vector
import wc_lib as W
from toss_front import build_toss_front


def _molded(name, size, material, c, xyz, parent=None, radius=0.006):
    ob = W.box(name, size, material, c, xyz, parent=parent)
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width = min(radius, min(size) * 0.42)
    bv.segments = 2
    return ob


def _text(c, parent, name, body, xyz, size, material, rot=(math.pi / 2, 0, 0)):
    data = bpy.data.curves.new(name, "FONT")
    data.body = body
    data.font = W.load_font(W.KFONT)
    data.size = size
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.fill_mode = "FRONT"
    data.materials.append(material)
    ob = bpy.data.objects.new(name, data)
    ob.location = xyz
    ob.rotation_euler = rot
    ob.parent = parent
    c.objects.link(ob)
    return ob


def cut_wall_opening(target_names, center, size, cutter_coll):
    """Cut a clean rectangular doorway opening through wall/wainscot/mural meshes using Boolean DIFFERENCE."""
    cutter = W.box(f"DoorCutter_{center[0]:.1f}_{center[1]:.1f}", size, W.mat("CutterMat", (0.1, 0.1, 0.1)), cutter_coll, center)
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    cutter.hide_viewport = True
    for name in target_names:
        ob = bpy.data.objects.get(name)
        if not ob or ob.type != "MESH":
            continue
        mod = ob.modifiers.new(f"Cut_{cutter.name}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        try:
            mod.solver = "FLOAT"
        except (AttributeError, TypeError):
            pass


def _beechwood_mat(name, base_col=(0.66, 0.41, 0.21), dark_col=(0.48, 0.27, 0.12), rough=0.46, scale=14.0):
    """Procedural warm beechwood grain shader with subtle bump for realistic wooden craft props."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.8, 12.0, 12.0)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 4.2
    wave.inputs["Detail"].default_value = 6.0
    wave.inputs["Detail Scale"].default_value = 2.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 90.0
    noise.inputs["Detail"].default_value = 8.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*base_col, 1.0)
    mix.inputs["B"].default_value = (*dark_col, 1.0)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.001
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _cotton_rope_mat(name):
    """Soft twisted ivory cotton rope shader with fine fiber bump."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.91, 0.87, 0.79, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.92
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.45
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 180.0
    noise.inputs["Detail"].default_value = 10.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.14
    bump.inputs["Distance"].default_value = 0.0015
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _brushed_brass_mat(name):
    """Warm satin brushed brass shader matching the photoreal dome bell."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.76, 0.55, 0.19, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.96
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.5, 1.5, 45.0)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 12.0
    noise.inputs["Detail"].default_value = 6.0
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.18
    mr.inputs["To Max"].default_value = 0.30
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
    return m


def _set_smooth(obj):
    if obj.type == "MESH":
        for p in obj.data.polygons:
            p.use_smooth = True


def _link_under(obj, c, parent):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    c.objects.link(obj)
    obj.parent = parent
    return obj


def _make_curve_tube(name, pts, radius, mat, c, parent, bev_res=6, res_u=12, cyclic=False):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = bev_res
    curve.resolution_u = res_u
    curve.use_fill_caps = not cyclic
    sp = curve.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    sp.use_cyclic_u = cyclic
    for kp, pt in zip(sp.bezier_points, pts):
        kp.co = pt
        kp.handle_left_type = kp.handle_right_type = "AUTO"
    curve.materials.append(mat)
    obj = bpy.data.objects.new(name, curve)
    c.objects.link(obj)
    obj.parent = parent
    return obj


def build_shop_doorbell(c, parent, loc=(0.24, -0.028, 2.08)):
    """High-detail photoreal Korean Aekmagi Myeongtae (액막이 명태) doorbell:
    silver magnetic J-hook, brass carabiner ring, 2-strand twisted cotton rope + waist knot,
    beechwood pollock fish with wood grain, curved gill, 3 tail grooves, and drilled eye,
    thin black V-cord, light wooden bead, and seamless lathe-turned brushed brass dome bell."""
    import bmesh

    bell_root = W.empty("Entrance_Doorbell", c, loc, parent=parent)
    chrome_m = W.mat("Myeongtae_HookSilver", (0.76, 0.78, 0.80), rough=0.16, metal=0.96)
    brass_m = _brushed_brass_mat("Myeongtae_BrushedBrass")
    rope_m = _cotton_rope_mat("Myeongtae_CottonRope")
    # Reuse the real info-desk wood image texture rotated horizontally along the fish body!
    wood_m = _walnut_wood_mat("Myeongtae_InfoDeskWood", value_mult=0.90, sat_mult=1.24, scale=(2.6, 2.6, 2.6), rough=0.44, bump_str=0.06)
    # Rotate texture mapping 90 deg so wood grain runs horizontally along fish length (X axis)
    for n_node in wood_m.node_tree.nodes:
        if n_node.type == "MAPPING":
            n_node.inputs["Rotation"].default_value = (0.0, math.radians(90), 0.0)
            n_node.inputs["Scale"].default_value = (3.5, 3.5, 1.4)
    bead_m = _beechwood_mat("Myeongtae_LightBead", (0.84, 0.74, 0.58), (0.72, 0.60, 0.44), rough=0.46, scale=10.0)
    engrave_m = W.mat("Myeongtae_Engrave", (0.12, 0.055, 0.02), rough=0.78)
    dark_m = W.mat("Myeongtae_BlackCord", (0.03, 0.03, 0.04), rough=0.70)

    # 1. Silver magnetic cup base + curved J-hook
    bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=0.013, radius2=0.0085, depth=0.011, location=(0, -0.0055, 0.0), rotation=(math.radians(90), 0, 0))
    mag = _link_under(bpy.context.active_object, c, bell_root)
    mag.name = "Myeongtae mag base"
    mag.data.materials.append(chrome_m)
    _set_smooth(mag)
    _make_curve_tube(
        "Myeongtae J-hook",
        [(0, -0.009, 0.0), (0, -0.022, -0.001), (0, -0.028, -0.008), (0, -0.031, -0.002), (0, -0.031, 0.008)],
        0.0028, chrome_m, c, bell_root, bev_res=6, res_u=12,
    )

    # Swing pivot hanging from the J-hook saddle
    swing = W.empty("Doorbell_Swing", c, (0, -0.028, -0.005), parent=bell_root)

    # 2. Smooth gold carabiner ring + subtle clasp sleeve on right side
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.018, minor_radius=0.0030, major_segments=36, minor_segments=14,
        location=(0, 0, -0.016), rotation=(math.radians(90), 0, 0),
    )
    ring = _link_under(bpy.context.active_object, c, swing)
    ring.name = "Myeongtae gold ring"
    ring.data.materials.append(brass_m)
    _set_smooth(ring)
    # Carabiner hinge collar on +X side of ring
    bpy.ops.mesh.primitive_cylinder_add(vertices=18, radius=0.0038, depth=0.009, location=(0.0175, 0, -0.012), rotation=(0, math.radians(-18), 0))
    clasp = _link_under(bpy.context.active_object, c, swing)
    clasp.name = "Myeongtae ring clasp"
    clasp.data.materials.append(brass_m)
    _set_smooth(clasp)

    # 3. Realistic 2-strand twisted cotton rope from ring down through fish waist
    for strand in (0, 1):
        phase = strand * math.pi
        pts = []
        for k in range(22):
            t = k / 21.0
            z = -0.029 - t * 0.118
            ang = phase + t * math.pi * 6.5
            r_h = 0.0048 * (1.0 - 0.15 * math.sin(t * math.pi))
            pts.append((math.cos(ang) * r_h, math.sin(ang) * r_h, z))
        _make_curve_tube(f"Myeongtae_Rope_{strand}", pts, 0.0056, rope_m, c, swing, bev_res=6, res_u=8)

    # Horizontal knot collar right above fish back + vertical rope loop hugging fish belly
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.0115, minor_radius=0.0052, major_segments=28, minor_segments=12,
        location=(0, 0, -0.104), rotation=(math.radians(6), math.radians(-8), 0),
    )
    knot = _link_under(bpy.context.active_object, c, swing)
    knot.name = "Myeongtae waist knot"
    knot.data.materials.append(rope_m)
    _set_smooth(knot)

    for s_off in (-0.0032, 0.0032):
        _make_curve_tube(
            f"Myeongtae_WaistWrap_{s_off:+.4f}",
            [
                (s_off, -0.009, -0.106),
                (s_off, -0.012, -0.129),
                (s_off, -0.006, -0.152),
                (s_off, 0.006, -0.152),
                (s_off, 0.012, -0.129),
                (s_off, 0.009, -0.106),
            ],
            0.0050, rope_m, c, swing, bev_res=6, res_u=10, cyclic=True,
        )

    # 4. Sculpted Beechwood Pollock Fish (smooth multi-point silhouette + beveled edges)
    fish_xz = [
        (-0.088, 0.005), (-0.076, 0.011), (-0.060, 0.016), (-0.042, 0.020),
        (-0.022, 0.022), (-0.004, 0.020), (0.018, 0.016), (0.042, 0.011),
        (0.064, 0.008), (0.080, 0.012), (0.094, 0.017), (0.089, 0.007),
        (0.084, 0.000), (0.089, -0.007), (0.095, -0.016), (0.080, -0.011),
        (0.063, -0.007), (0.040, -0.010), (0.016, -0.013), (-0.008, -0.017),
        (-0.024, -0.020), (-0.042, -0.017), (-0.060, -0.013), (-0.078, -0.007),
        (-0.089, -0.003), (-0.078, 0.001), (-0.074, 0.003),
    ]
    n = len(fish_xz)
    half_t = 0.0058
    fz0 = -0.129
    verts = [(x, -half_t, fz0 + z) for x, z in fish_xz] + [(x, half_t, fz0 + z) for x, z in fish_xz]
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, j + n, i + n))
    fmesh = bpy.data.meshes.new("Myeongtae_Fish_Mesh")
    fmesh.from_pydata(verts, [], faces)
    fmesh.materials.append(wood_m)
    fobj = bpy.data.objects.new("Myeongtae fish", fmesh)
    c.objects.link(fobj)
    fobj.parent = swing
    bev = fobj.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.0022
    bev.segments = 3

    # Drilled eye (dark recessed dot + subtle rim), curved gill arc, and 3 engraved tail-fin lines
    for y_s in (-half_t - 0.0004, half_t + 0.0004):
        W.cyl("Myeongtae eye", 0.0032, 0.0014, engrave_m, c, (-0.065, y_s, fz0 + 0.005), (90, 0, 0), parent=swing, seg=18)
        # Curved gill arc (3-point bezier)
        _make_curve_tube(
            f"Myeongtae_Gill_{y_s:+.4f}",
            [(-0.046, y_s, fz0 + 0.011), (-0.042, y_s, fz0 + 0.000), (-0.048, y_s, fz0 - 0.010)],
            0.0011, engrave_m, c, swing, bev_res=4, res_u=8,
        )
        # 3 laser-engraved tail fin rays
        for idx_r, (z0, z1) in enumerate(((0.005, 0.010), (0.000, 0.000), (-0.005, -0.010))):
            _make_curve_tube(
                f"Myeongtae_TailRay_{y_s:+.4f}_{idx_r}",
                [(0.072, y_s, fz0 + z0), (0.085, y_s, fz0 + z1)],
                0.0009, engrave_m, c, swing, bev_res=3, res_u=4,
            )

    # 5. Thin black V-cord hanging from rope bottom to wooden bead
    _make_curve_tube(
        "Myeongtae black cord",
        [(-0.007, 0, -0.150), (-0.004, 0, -0.184), (-0.001, 0, -0.214)],
        0.0010, dark_m, c, swing, bev_res=4, res_u=6,
    )
    _make_curve_tube(
        "Myeongtae black cord R",
        [(0.007, 0, -0.150), (0.004, 0, -0.184), (0.001, 0, -0.214)],
        0.0010, dark_m, c, swing, bev_res=4, res_u=6,
    )

    # 6. Smooth light beechwood bead
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=18, radius=0.0115, location=(0, 0, -0.222))
    bead = _link_under(bpy.context.active_object, c, swing)
    bead.name = "Myeongtae wood bead"
    bead.data.materials.append(bead_m)
    _set_smooth(bead)

    # 7. Seamless lathe-turned brushed brass dome bell (single smooth revolved mesh!)
    bm = bmesh.new()
    bell_profile = [
        (0.000, -0.233),
        (0.006, -0.234),
        (0.012, -0.236),
        (0.017, -0.241),
        (0.020, -0.248),
        (0.021, -0.256),
        (0.021, -0.266),
        (0.0205, -0.271),
        (0.0185, -0.2725),
        (0.0175, -0.270),
        (0.0185, -0.252),
        (0.000, -0.237),
    ]
    segs = 36
    rings = []
    for r_val, z_val in bell_profile:
        if r_val < 1e-5:
            rings.append([bm.verts.new((0.0, 0.0, z_val))])
        else:
            rings.append([
                bm.verts.new((r_val * math.cos(2 * math.pi * s / segs), r_val * math.sin(2 * math.pi * s / segs), z_val))
                for s in range(segs)
            ])
    for r_i in range(len(rings) - 1):
        a, b = rings[r_i], rings[r_i + 1]
        if len(a) == 1 and len(b) > 1:
            for s in range(segs):
                bm.faces.new((a[0], b[(s + 1) % segs], b[s]))
        elif len(a) > 1 and len(b) == 1:
            for s in range(segs):
                bm.faces.new((a[s], a[(s + 1) % segs], b[0]))
        else:
            for s in range(segs):
                sn = (s + 1) % segs
                bm.faces.new((a[s], a[sn], b[sn], b[s]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh_data = bpy.data.meshes.new("Myeongtae_BrassBell_Mesh")
    bm.to_mesh(bmesh_data)
    bm.free()
    bmesh_data.materials.append(brass_m)
    bell_obj = bpy.data.objects.new("Myeongtae brass bell", bmesh_data)
    c.objects.link(bell_obj)
    bell_obj.parent = swing
    _set_smooth(bell_obj)

    return bell_root


def build_entrance_door(c, loc, rot_deg=90):
    """Commercial Korean gym double tempered-glass entrance door (1.65 x 2.25 m) + RFID reader + Korean EXIT sign above."""
    from reel_gym import korean_exit_sign

    root = W.empty("Door_MainEntrance", c, loc)
    root.rotation_euler.z = math.radians(rot_deg)

    frame_m = W.mat("DoorAlum_Charcoal", (0.028, 0.030, 0.035), rough=0.38, metal=0.65)
    chrome_m = W.mat("DoorSteel_Brushed", (0.64, 0.66, 0.68), rough=0.22, metal=0.92)
    # True crystal-clear commercial glass (Transparent + subtle Glossy reflection) for Blender 5.2 EEVEE
    def _clear_glass(name, tint, reflect_fac, rough):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            pass
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = reflect_fac
        trans = nt.nodes.new("ShaderNodeBsdfTransparent")
        trans.inputs["Color"].default_value = (*tint, 1.0)
        gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
        gloss.inputs["Color"].default_value = (0.90, 0.94, 0.98, 1.0)
        gloss.inputs["Roughness"].default_value = rough
        nt.links.new(trans.outputs["BSDF"], mix.inputs[1])
        nt.links.new(gloss.outputs["BSDF"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
        return m

    glass_m = _clear_glass("EntranceGlass_Tinted", (0.94, 0.97, 0.98), 0.10, 0.04)
    frost_m = _clear_glass("EntranceGlass_Frost", (0.95, 0.96, 0.97), 0.42, 0.55)
    rfid_m = W.mat("RFID_Body", (0.02, 0.022, 0.026), rough=0.32, metal=0.25)
    rfid_led = W.shadeless("RFID_LED", (0.08, 0.82, 1.0), strength=3.2)

    w, h = 1.65, 2.25
    # Outer aluminum jambs & header
    for side in (-1, 1):
        _molded("Entrance jamb", (0.075, 0.24, h), frame_m, c, (side * (w / 2 - 0.0375), 0, h / 2), root, 0.004)
    _molded("Entrance header", (w, 0.24, 0.085), frame_m, c, (0, 0, h - 0.0425), root, 0.004)
    _molded("Entrance threshold", (w, 0.24, 0.016), chrome_m, c, (0, 0, 0.008), root, 0.002)

    # Twin glass door leaves
    leaf_w = (w - 0.16) / 2 - 0.006
    for side in (-1, 1):
        cx = side * (leaf_w / 2 + 0.004)
        # Top/bottom stiles
        _molded("Glass door bottom rail", (leaf_w, 0.048, 0.14), frame_m, c, (cx, 0, 0.086), root, 0.003)
        _molded("Glass door top rail", (leaf_w, 0.048, 0.09), frame_m, c, (cx, 0, h - 0.13), root, 0.003)
        _molded("Glass door outer stile", (0.048, 0.048, h - 0.16), frame_m, c, (cx + side * (leaf_w / 2 - 0.024), 0, h / 2), root, 0.003)
        # Glass pane & frosted safety band
        W.box("Entrance glass pane", (leaf_w - 0.05, 0.012, h - 0.34), glass_m, c, (cx - side * 0.02, 0, h / 2 + 0.02), parent=root)
        W.box("Entrance frost band", (leaf_w - 0.05, 0.014, 0.16), frost_m, c, (cx - side * 0.02, 0, 1.18), parent=root)
        # Tall vertical stainless push/pull handle
        hx = side * 0.085
        for y_face in (-0.055, 0.055):
            W.cyl("Entrance handle bar", 0.015, 0.62, chrome_m, c, (hx, y_face, 1.08), parent=root, seg=16)
            for hz in (0.82, 1.34):
                W.cyl("Entrance handle standoff", 0.010, 0.055, chrome_m, c, (hx, y_face * 0.5, hz), (90, 0, 0), parent=root, seg=12)

    # Lightweight 3D Korean commercial building hallway (상가 복도) outside the glass entrance!
    build_sangga_hallway(c, root)

    # RFID membership access reader beside the door on the interior wall
    _molded("RFID reader", (0.085, 0.028, 0.145), rfid_m, c, (w / 2 + 0.14, -0.105, 1.18), root, 0.006)
    _molded("RFID glow ring", (0.048, 0.004, 0.048), rfid_led, c, (w / 2 + 0.14, -0.120, 1.20), root, 0.004)

    # Korean standard medium EXIT sign (피난구유도등) mounted directly above the main entrance!
    ex = W.empty("Emergency exit sign entrance", c, (0, -0.105, h + 0.22), parent=root)
    korean_exit_sign(c, ex)

    # Storefront magnetic brass doorbell ('띠링~') on interior top rail of the right glass door
    build_shop_doorbell(c, root, loc=(0.24, -0.028, h - 0.13))
    return root


def _textured_plane(c, parent, name, img_name, width, height, loc, rot=(0, 0, 0), strength=1.0, shaded=False):
    """Create a UV-mapped image plane (either emissive/shadeless or PBR shaded)."""
    img_path = os.path.join(W.PARTS, img_name)
    im = bpy.data.images.load(img_path, check_existing=True)
    if not im.packed_file:
        im.pack()
    if shaded:
        m = bpy.data.materials.new(f"Mat_{name}")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Roughness"].default_value = 0.45
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = im
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        m = W.shadeless(f"Mat_{name}", image=img_path, strength=strength)
    hw, hh = width / 2, height / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for loop, coord in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = coord
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    ob.parent = parent
    c.objects.link(ob)
    return ob


def _textured_disc(c, parent, name, img_name, radius, loc, rot=(0, 0, 0), strength=1.55, seg=32):
    """Create a UV-mapped circular emissive acrylic sign face in the same XZ local plane as _textured_plane."""
    img_path = os.path.join(W.PARTS, img_name)
    im = bpy.data.images.load(img_path, check_existing=True)
    if not im.packed_file:
        im.pack()
    m = W.shadeless(f"Mat_{name}", image=img_path, strength=strength)
    me = bpy.data.meshes.new(name)
    verts = [(0.0, 0.0, 0.0)]
    for i in range(seg):
        a = 2.0 * math.pi * i / seg
        verts.append((radius * math.cos(a), 0.0, radius * math.sin(a)))
    faces = [(0, i + 1, (i + 1) % seg + 1) for i in range(seg)]
    me.from_pydata(verts, [], faces)
    # Ensure normal faces -Y (matching _textured_plane!)
    for poly in me.polygons:
        if poly.normal.y > 0:
            me.flip_normals()
            break
    uv = me.uv_layers.new()
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (0.5 + v.x / (2.0 * radius), 0.5 + v.z / (2.0 * radius))
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    ob.parent = parent
    c.objects.link(ob)
    return ob


def _projecting_sign(c, parent, name, style, img_rel, x_pos, y_wall=2.84, z_pos=2.36):
    """Build 3 authentic Korean commercial projecting lightbox sign styles:
    - 'rect': deep matte-black rectangular acrylic box (Photo 1 '준 인테리어')
    - 'square': sleek glowing square cube lightbox (Photo 2 'GLOW')
    - 'round': double-sided white molded circular acrylic sign with dark mid-seam & twin brackets (Photo 3 '나빈피아노')"""
    frame_m = bpy.data.materials.get("Hallway_SignFrame") or W.mat("Hallway_SignFrame", (0.04, 0.045, 0.05), rough=0.40, metal=0.55)
    white_rim_m = bpy.data.materials.get("Sign_WhiteAcrylicRim") or W.mat("Sign_WhiteAcrylicRim", (0.90, 0.91, 0.92), rough=0.22, metal=0.04)
    seam_m = bpy.data.materials.get("Sign_DarkMidSeam") or W.mat("Sign_DarkMidSeam", (0.04, 0.04, 0.045), rough=0.55, metal=0.35)

    if style == "rect":
        w, h, t = 0.56, 0.30, 0.14
        s_root = W.empty(name, c, (x_pos, y_wall - w / 2 - 0.06, z_pos), parent=parent)
        _molded(f"{name}_box", (t, w, h), frame_m, c, (0, 0, 0), s_root, 0.008)
        _molded(f"{name}_bracket", (0.05, 0.12, h * 0.72), frame_m, c, (0, w / 2 + 0.03, 0), s_root, 0.003)
        _textured_plane(c, s_root, f"{name}_faceL", img_rel, w - 0.036, h - 0.036, (-t / 2 - 0.002, 0, 0), rot=(0, 0, -math.pi / 2), strength=1.65)
        _textured_plane(c, s_root, f"{name}_faceR", img_rel, w - 0.036, h - 0.036, (t / 2 + 0.002, 0, 0), rot=(0, 0, math.pi / 2), strength=1.65)
        return s_root
    elif style == "square":
        w, h, t = 0.36, 0.36, 0.13
        s_root = W.empty(name, c, (x_pos, y_wall - w / 2 - 0.04, z_pos), parent=parent)
        _molded(f"{name}_box", (t, w, h), frame_m, c, (0, 0, 0), s_root, 0.005)
        _molded(f"{name}_bracket", (0.06, 0.08, h * 0.80), frame_m, c, (0, w / 2 + 0.02, 0), s_root, 0.003)
        _textured_plane(c, s_root, f"{name}_faceL", img_rel, w - 0.024, h - 0.024, (-t / 2 - 0.002, 0, 0), rot=(0, 0, -math.pi / 2), strength=1.70)
        _textured_plane(c, s_root, f"{name}_faceR", img_rel, w - 0.024, h - 0.024, (t / 2 + 0.002, 0, 0), rot=(0, 0, math.pi / 2), strength=1.70)
        return s_root
    else:  # 'round'
        r, t = 0.23, 0.12
        s_root = W.empty(name, c, (x_pos, y_wall - r - 0.11, z_pos - 0.02), parent=parent)
        # Double-sided white molded acrylic shells + recessed dark center seam groove (exact Photo 3!)
        W.cyl(f"{name}_shellL", r, t * 0.42, white_rim_m, c, (-t * 0.29, 0, 0), (0, 90, 0), parent=s_root, seg=28)
        W.cyl(f"{name}_shellR", r, t * 0.42, white_rim_m, c, (t * 0.29, 0, 0), (0, 90, 0), parent=s_root, seg=28)
        W.cyl(f"{name}_midSeam", r * 0.90, t * 0.24, seam_m, c, (0, 0, 0), (0, 90, 0), parent=s_root, seg=28)
        # Twin black steel wall brackets
        for bz in (-0.09, 0.09):
            _molded(f"{name}_arm_{bz}", (0.032, 0.15, 0.032), frame_m, c, (0, r + 0.045, bz), s_root, 0.003)
        _molded(f"{name}_wallPlate", (0.055, 0.018, 0.25), frame_m, c, (0, r + 0.115, 0), s_root, 0.003)
        # Circular UV-mapped emissive faces
        _textured_disc(c, s_root, f"{name}_faceL", img_rel, r - 0.018, (-t * 0.505, 0, 0), rot=(0, 0, -math.pi / 2), strength=1.55)
        _textured_disc(c, s_root, f"{name}_faceR", img_rel, r - 0.018, (t * 0.505, 0, 0), rot=(0, 0, math.pi / 2), strength=1.55)
        return s_root


def build_sangga_hallway(c, entrance_root):
    """Realistic 3D Korean commercial sangga hallway right outside the transparent entrance door:
    speckled terrazzo marble floor, black granite plinth, 3D brushed stainless storefront mullions,
    opposite English academy storefront (blue vinyl panels, transparent double glass doors with handles,
    digital keypad lock, and lit classroom whiteboard inside), adjacent yellow piano academy,
    acoustic ceiling + fluorescent troffers + conduit pipe, projecting signs, yellow X-banner, and extinguisher."""
    hall = W.empty("Sangga_Hallway", c, (0, 0, 0), parent=entrance_root)

    # 1) Glossy Korean terrazzo (도끼다시) floor with tiled mineral aggregate texture
    floor_m = bpy.data.materials.new("Hallway_TerrazzoFloor")
    floor_m.use_nodes = True
    fn, fl = floor_m.node_tree.nodes, floor_m.node_tree.links
    fbsdf = next(n for n in fn if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Specular IOR Level"].default_value = 0.55
    ftex = fn.new("ShaderNodeTexImage")
    tz_path = os.path.join(W.PARTS, "sangga_terrazzo.png")
    tz_im = bpy.data.images.load(tz_path, check_existing=True)
    if not tz_im.packed_file:
        tz_im.pack()
    ftex.image = tz_im
    fcoord = fn.new("ShaderNodeTexCoord")
    fmap = fn.new("ShaderNodeMapping")
    fmap.inputs["Scale"].default_value = (7.5, 2.4, 1.0)
    fl.new(fcoord.outputs["UV"], fmap.inputs["Vector"])
    fl.new(fmap.outputs["Vector"], ftex.inputs["Vector"])
    fl.new(ftex.outputs["Color"], fbsdf.inputs["Base Color"])
    fnoise = fn.new("ShaderNodeTexNoise")
    fnoise.inputs["Scale"].default_value = 6.0
    fl.new(fcoord.outputs["Object"], fnoise.inputs["Vector"])
    frmap = fn.new("ShaderNodeMapRange")
    frmap.inputs["To Min"].default_value = 0.11
    frmap.inputs["To Max"].default_value = 0.25
    fl.new(fnoise.outputs["Fac"], frmap.inputs["Value"])
    fl.new(frmap.outputs["Result"], fbsdf.inputs["Roughness"])

    ceil_m = W.mat("Hallway_TexCeiling", (0.72, 0.72, 0.70), rough=0.86, metal=0.0)
    granite_m = W.mat("Hallway_BlackGranite", (0.025, 0.026, 0.030), rough=0.14, metal=0.12)
    steel_m = W.mat("Hallway_StainlessMullion", (0.72, 0.74, 0.76), rough=0.20, metal=0.94)
    wood_grip_m = W.mat("Hallway_WoodHandle", (0.28, 0.11, 0.05), rough=0.35, metal=0.05)
    lock_m = W.mat("Hallway_DigitalLock", (0.62, 0.64, 0.66), rough=0.28, metal=0.80)
    blue_band_m = W.mat("Hallway_BlueBand", (0.07, 0.19, 0.50), rough=0.32, metal=0.05)
    wall_m = W.mat("Hallway_WallBeige", (0.58, 0.57, 0.54), rough=0.72, metal=0.0)
    class_wall_m = W.mat("Hallway_ClassWall", (0.78, 0.81, 0.82), rough=0.78, metal=0.0)
    class_floor_m = W.mat("Hallway_ClassFloor", (0.72, 0.70, 0.65), rough=0.35, metal=0.0)
    wb_frame_m = W.mat("Hallway_WBFrame", (0.64, 0.54, 0.36), rough=0.45, metal=0.10)
    wb_face_m = W.mat("Hallway_WBFace", (0.92, 0.93, 0.94), rough=0.18, metal=0.0)
    end_m = W.mat("Hallway_FarEnd", (0.14, 0.15, 0.16), rough=0.75, metal=0.0)
    led_m = W.shadeless("Hallway_DownlightLED", (0.94, 0.96, 1.0), strength=5.0)
    troffer_m = W.mat("Hallway_TrofferHousing", (0.48, 0.50, 0.52), rough=0.38, metal=0.70)
    frame_m = W.mat("Hallway_SignFrame", (0.04, 0.045, 0.05), rough=0.40, metal=0.55)
    red_m = W.mat("Hallway_ExtRed", (0.72, 0.04, 0.05), rough=0.30, metal=0.25)
    dark_m = W.mat("Hallway_DarkSteel", (0.03, 0.032, 0.036), rough=0.45, metal=0.50)

    # Hallway box shell (depth y=0.14..2.86, length x=-4.6..+4.6, height z=0..2.75)
    W.box("Hallway floor", (9.4, 2.9, 0.04), floor_m, c, (0, 1.50, -0.02), parent=hall)
    W.box("Hallway ceiling", (9.4, 2.9, 0.06), ceil_m, c, (0, 1.50, 2.78), parent=hall)
    # Subtle acoustic Tex ceiling grid lines (60cm spacing)
    grid_m = W.mat("Hallway_TexGrid", (0.45, 0.46, 0.45), rough=0.80, metal=0.0)
    for gx in [i * 0.65 for i in range(-6, 7)]:
        W.box("Tex grid X", (0.012, 2.86, 0.006), grid_m, c, (gx, 1.50, 2.748), parent=hall)
    for gy in (0.65, 1.30, 1.95, 2.60):
        W.box("Tex grid Y", (9.2, 0.012, 0.006), grid_m, c, (0, gy, 2.748), parent=hall)

    # Exposed silver electrical conduit pipe running along ceiling/opposite wall corner (Photo 1 detail!)
    W.cyl("Hallway conduit pipe", 0.014, 9.0, steel_m, c, (0, 2.74, 2.69), (0, 90, 0), parent=hall, seg=12)

    # Far corridor end wall on +X side only (-X side extends to the elevator hall!)
    W.box("Hallway far end", (0.08, 2.9, 2.80), end_m, c, (4.65, 1.50, 1.40), parent=hall)
    W.box("Hallway far exit dot", (0.02, 0.22, 0.16), W.shadeless("HallFarExit", (0.08, 0.88, 0.36), strength=3.2),
          c, (4.59, 1.50, 2.38), parent=hall)

    # Opposite storefront wall backing (split around the glass double door opening x = -0.82 .. +0.72)
    W.box("Opposite wall left", (3.8, 0.08, 2.80), wall_m, c, (-2.72, 2.92, 1.40), parent=hall)
    W.box("Opposite wall right", (3.8, 0.08, 2.80), wall_m, c, (2.62, 2.92, 1.40), parent=hall)
    # Polished black granite plinth along bottom of opposite storefront (exact Photo 2 detail!)
    W.box("Opposite granite plinth", (9.2, 0.14, 0.10), granite_m, c, (0, 2.85, 0.05), parent=hall)

    # --- Real 3D Brushed Stainless Steel Storefront Frame (Photo 2: EroomHigh english) ---
    # Spanning x = -1.92 .. +1.82 (left blue panel: -1.92..-0.82, center glass doors: -0.82..+0.72, right blue panel: +0.72..+1.82)
    sf_y = 2.84
    for mx in (-1.92, -0.82, 0.72, 1.82, 3.10):
        _molded("Storefront mullion V", (0.055, 0.075, 2.66), steel_m, c, (mx, sf_y, 1.43), hall, 0.004)
    for mz, mh in ((0.11, 0.045), (2.18, 0.075), (2.71, 0.055)):
        _molded("Storefront mullion H", (5.10, 0.078, mh), steel_m, c, (0.58, sf_y, mz), hall, 0.004)

    # Royal-Blue vinyl academy panels (left, right, top transom) mounted flush inside the stainless mullions
    _textured_plane(c, hall, "Sangga_BlueLeft", "sangga_blue_left.png", 1.04, 2.02, (-1.37, sf_y - 0.02, 1.14), shaded=True)
    _textured_plane(c, hall, "Sangga_BlueRight", "sangga_blue_right.png", 1.04, 2.02, (1.27, sf_y - 0.02, 1.14), shaded=True)
    _textured_plane(c, hall, "Sangga_BlueTransom", "sangga_blue_transom.png", 1.48, 0.45, (-0.05, sf_y - 0.02, 2.45), shaded=True)
    # Side transom dark-blue headers
    W.box("Transom side L", (1.04, 0.02, 0.45), blue_band_m, c, (-1.37, sf_y - 0.01, 2.45), parent=hall)
    W.box("Transom side R", (1.04, 0.02, 0.45), blue_band_m, c, (1.27, sf_y - 0.01, 2.45), parent=hall)
    # Adjacent warm mustard-yellow Piano Academy storefront on the right (Photo 1 vibe!)
    _textured_plane(c, hall, "Sangga_PianoPanel", "sangga_piano_panel.png", 1.22, 2.02, (2.46, sf_y - 0.02, 1.14), shaded=True)

    # --- Center Opposite Academy Glass Double Doors + Lit Classroom Interior Behind Them! ---
    # Classroom mini-box behind the opposite glass doors (y = 2.86 .. 4.45)
    W.box("OppClass back wall", (2.4, 0.06, 2.75), class_wall_m, c, (-0.05, 4.40, 1.38), parent=hall)
    W.box("OppClass floor", (2.4, 1.65, 0.04), class_floor_m, c, (-0.05, 3.62, -0.02), parent=hall)
    W.box("OppClass baseboard", (2.4, 0.04, 0.10), wb_frame_m, c, (-0.05, 4.35, 0.05), parent=hall)
    # Framed whiteboard on the classroom back wall (exact Photo 2 detail!)
    _molded("OppClass WB frame", (1.18, 0.04, 0.82), wb_frame_m, c, (-0.32, 4.35, 1.48), hall, 0.005)
    W.box("OppClass WB surface", (1.10, 0.02, 0.74), wb_face_m, c, (-0.32, 4.32, 1.48), parent=hall)
    # Classroom bright interior light
    cl_ld = bpy.data.lights.new("OppClassLight", "AREA")
    cl_ld.shape = "RECTANGLE"
    cl_ld.size, cl_ld.size_y = 1.4, 0.8
    cl_ld.energy = 110
    cl_ld.color = (0.96, 0.98, 1.0)
    cl_ld.use_shadow = False
    cl_ob = bpy.data.objects.new(cl_ld.name, cl_ld)
    cl_ob.location = (-0.05, 3.65, 2.55)
    cl_ob.parent = hall
    c.objects.link(cl_ob)

    # Opposite glass door blue logo band + 3D stainless/wood handles + silver digital keypad doorlock!
    W.box("OppDoor blue tape", (1.46, 0.012, 0.13), blue_band_m, c, (-0.05, sf_y - 0.02, 1.04), parent=hall)
    for side in (-1, 1):
        hx = -0.05 + side * 0.12
        W.cyl("OppDoor handle steel", 0.014, 0.72, steel_m, c, (hx, sf_y - 0.06, 1.02), parent=hall, seg=14)
        W.cyl("OppDoor handle wood", 0.017, 0.34, wood_grip_m, c, (hx, sf_y - 0.06, 1.02), parent=hall, seg=14)
    _molded("OppDoor digital lock", (0.075, 0.036, 0.16), lock_m, c, (-0.05, sf_y - 0.03, 1.12), hall, 0.005)

    # Recessed fluorescent ceiling troffers + twin rows of circular LED downlights
    for tx in (-2.4, 0.0, 2.4):
        _molded("Hallway troffer frame", (0.95, 0.28, 0.02), troffer_m, c, (tx, 1.50, 2.742), hall, 0.004)
        W.box("Hallway troffer tube", (0.86, 0.16, 0.010), led_m, c, (tx, 1.50, 2.736), parent=hall)
    for y_row in (0.62, 2.34):
        for x_pos in (-3.6, -2.4, -1.2, 0.0, 1.2, 2.4, 3.6):
            W.cyl("Hallway LED lens", 0.050, 0.008, led_m, c, (x_pos, y_row, 2.746), parent=hall, seg=16)

    # 3 real 3D projecting Korean Sangga lightbox signs in varied shapes (rect, square, round)
    for s_name, style, img, x_pos, z_pos in (
        ("Sign_Math", "rect", "sangga_elev/sign_eroom.jpg", -0.82, 2.38),
        ("Sign_Pilates", "square", "sangga_elev/sign_pilates.jpg", 0.72, 2.36),
        ("Sign_Art", "round", "sangga_elev/sign_piano.jpg", 1.82, 2.34),
    ):
        _projecting_sign(c, hall, s_name, style, img, x_pos, y_wall=2.84, z_pos=z_pos)

    # Standing yellow Korean X-Banner + red fire extinguisher on the right side of the opposite storefront
    ban = W.empty("Hallway_XBanner", c, (0.98, 2.32, 0), parent=hall)
    ban.rotation_euler.z = math.radians(-18)
    _molded("XBanner base", (0.48, 0.30, 0.02), dark_m, c, (0, 0.04, 0.01), ban, 0.004)
    W.cyl("XBanner pole", 0.009, 1.54, dark_m, c, (0, 0.05, 0.79), parent=ban, seg=10)
    _textured_plane(c, ban, "XBanner_Graphic", "hallway_banner.png", 0.52, 1.44, (0, 0.0, 0.85), shaded=True)

    ext = W.empty("Hallway_Extinguisher", c, (-1.12, 2.50, 0), parent=hall)
    ext.rotation_euler.z = math.radians(12)
    korean_fire_extinguisher(c, ext)

    # Balanced cool-neutral Korean commercial hallway lighting (brings out terrazzo sheen & stainless mullion glints!)
    for lx in (-1.6, 1.6):
        ld = bpy.data.lights.new(f"HallwayLight_{lx}", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = 2.6, 1.0
        ld.energy = 155
        ld.color = (0.94, 0.96, 1.0)
        ld.use_shadow = False
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (lx, 1.55, 2.66)
        lo.parent = hall
        c.objects.link(lo)

    build_hallway_extension(c, hall, floor_m, ceil_m, granite_m, steel_m)


def _standing_xbanner(c, parent, name, img_rel, loc, rot_z_deg=0.0, width=0.56, height=1.52):
    """Korean commercial standing X-banner with weighted water-tank base and rear support pole."""
    dark_m = bpy.data.materials.get("Hallway_DarkSteel") or W.mat("Hallway_DarkSteel", (0.03, 0.032, 0.036), rough=0.45, metal=0.50)
    tank_m = bpy.data.materials.get("XBanner_TankGray") or W.mat("XBanner_TankGray", (0.28, 0.30, 0.32), rough=0.55, metal=0.05)
    root = W.empty(name, c, loc, parent=parent)
    root.rotation_euler.z = math.radians(rot_z_deg)
    # Gray plastic water-tank base
    _molded(f"{name}_tank", (0.36, 0.30, 0.12), tank_m, c, (0, 0.09, 0.06), root, 0.012)
    # Support pole cleanly behind the reclined canvas (tilted to match so it never pokes through!)
    pole = W.cyl(f"{name}_pole", 0.008, height, dark_m, c, (0, 0.13, height / 2 + 0.08), parent=root, seg=8)
    pole.rotation_euler.x = math.radians(-6.5)
    # Banner canvas slightly reclined backward (6.5 deg)
    plane = _textured_plane(c, root, f"{name}_canvas", img_rel, width, height, (0, 0.0, height / 2 + 0.10), shaded=True)
    plane.rotation_euler.x = math.radians(-6.5)
    return root


def _speckled_granite_mat(name="Elev_GrayGranite"):
    """Procedural Korean commercial building speckled gray granite stone (화강석) shader."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.34
    bsdf.inputs["Specular IOR Level"].default_value = 0.50
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # Fine salt-and-pepper granite mineral grains
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 140.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 55.0
    noise.inputs["Detail"].default_value = 8.0
    mix_f = nt.nodes.new("ShaderNodeMix")
    mix_f.data_type = "FLOAT"
    mix_f.inputs["Factor"].default_value = 0.45
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = (0.14, 0.14, 0.135, 1.0)
    e1 = ramp.color_ramp.elements.new(0.45)
    e1.color = (0.44, 0.43, 0.41, 1.0)
    ramp.color_ramp.elements[-1].position = 0.82
    ramp.color_ramp.elements[-1].color = (0.64, 0.63, 0.60, 1.0)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(vor.outputs["Distance"], mix_f.inputs["A"])
    nt.links.new(noise.outputs["Fac"], mix_f.inputs["B"])
    nt.links.new(mix_f.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def build_hallway_extension(c, hall, floor_m, ceil_m, granite_m, steel_m):
    """Extend Sangga_Hallway along -X (x = -11.55 .. -4.65) for a ~10-second protagonist walk,
    terminating at a Korean commercial sangga elevator lobby exterior (Photos #1 & #2):
    - Center: polished black granite surround, recessed brushed stainless portal, 1호기 + red LED '3' header,
      separable Elev_Door_L / Elev_Door_R sliding doors with safety stickers, call button plate, twin round wall lamps.
    - Left: Korean indoor fire hydrant cabinet (옥내소화전) + red floor fire extinguisher + 3F marker.
    - Right: cluttered commercial ad panels (dermatology, dental), floor guide + orange notice,
      standing X-banners (screen golf, B1 mart), and a vacant storefront (임대문의) along the corridor."""
    ext = W.empty("Sangga_Hallway_Ext", c, (0, 0, 0), parent=hall)

    gray_granite_m = _speckled_granite_mat("Elev_GrayGranite")
    wall_m = bpy.data.materials.get("Hallway_WallBeige") or W.mat("Hallway_WallBeige", (0.58, 0.57, 0.54), rough=0.72, metal=0.0)
    grid_m = bpy.data.materials.get("Hallway_TexGrid") or W.mat("Hallway_TexGrid", (0.45, 0.46, 0.45), rough=0.80, metal=0.0)
    troffer_m = bpy.data.materials.get("Hallway_TrofferHousing") or W.mat("Hallway_TrofferHousing", (0.48, 0.50, 0.52), rough=0.38, metal=0.70)
    led_m = bpy.data.materials.get("Hallway_DownlightLED") or W.shadeless("Hallway_DownlightLED", (0.94, 0.96, 1.0), strength=5.0)
    dark_m = bpy.data.materials.get("Hallway_DarkSteel") or W.mat("Hallway_DarkSteel", (0.03, 0.032, 0.036), rough=0.45, metal=0.50)
    chrome_m = W.mat("Elev_Chrome", (0.82, 0.84, 0.86), rough=0.14, metal=0.96)
    door_steel_m = W.mat("Elev_DoorStainless", (0.68, 0.70, 0.72), rough=0.22, metal=0.92)
    seam_m = W.mat("Elev_DarkSeam", (0.015, 0.015, 0.018), rough=0.60, metal=0.20)
    lamp_glow_m = W.shadeless("Elev_WallLampGlow", (1.0, 0.96, 0.88), strength=3.6)
    gold_m = W.mat("Elev_GoldLetter", (0.82, 0.65, 0.22), rough=0.24, metal=0.92)
    red_led_m = W.shadeless("Elev_RedIndicator", (1.0, 0.12, 0.06), strength=5.0)
    btn_glow_m = W.shadeless("Elev_BtnGlow", (0.95, 0.78, 0.35), strength=2.6)
    frosted_m = W.mat("Vacant_FrostedGlass", (0.68, 0.72, 0.75), rough=0.28, metal=0.05)

    # 1) Corridor extension shell: X = -11.55 .. -4.65 (length = 6.90m, center X = -8.10)
    W.box("HallExt floor", (6.94, 2.92, 0.04), floor_m, c, (-8.10, 1.46, -0.02), parent=ext)
    W.box("HallExt ceiling", (6.94, 2.92, 0.06), ceil_m, c, (-8.10, 1.46, 2.78), parent=ext)
    # Acoustic Tex ceiling grid lines continuing seamlessly
    for gx in [round(-4.55 - i * 0.65, 3) for i in range(1, 11)]:
        W.box("HallExt grid X", (0.012, 2.86, 0.006), grid_m, c, (gx, 1.46, 2.748), parent=ext)
    for gy in (0.65, 1.30, 1.95, 2.60):
        W.box("HallExt grid Y", (6.90, 0.012, 0.006), grid_m, c, (-8.10, gy, 2.748), parent=ext)
    # Ceiling electrical conduit pipe continuing along right ceiling corner
    W.cyl("HallExt conduit", 0.014, 6.90, steel_m, c, (-8.10, 2.74, 2.69), (0, 90, 0), parent=ext, seg=10)

    # 2) Side walls: Left (Y = 0.0, gym side) & Right (Y = 2.86, opposite commercial side)
    # Left wall (gray granite wainscot + beige plaster upper + black granite plinth)
    W.box("HallExt wall L upper", (6.94, 0.08, 1.65), wall_m, c, (-8.10, -0.02, 1.95), parent=ext)
    W.box("HallExt wall L lower", (6.94, 0.09, 1.12), gray_granite_m, c, (-8.10, -0.01, 0.56), parent=ext)
    W.box("HallExt plinth L", (6.94, 0.11, 0.10), granite_m, c, (-8.10, 0.01, 0.05), parent=ext)
    # Right wall (gray granite near elevator lobby + opposite wall)
    W.box("HallExt wall R", (6.94, 0.08, 2.80), gray_granite_m, c, (-8.10, 2.90, 1.40), parent=ext)
    W.box("HallExt plinth R", (6.94, 0.14, 0.10), granite_m, c, (-8.10, 2.85, 0.05), parent=ext)

    # 3) Black granite square floor border inlay right in front of elevator (Photo #1 detail!)
    inlay_z = 0.003
    W.box("ElevInlay_N", (0.14, 2.08, 0.004), granite_m, c, (-11.35, 1.42, inlay_z), parent=ext)
    W.box("ElevInlay_S", (0.14, 2.08, 0.004), granite_m, c, (-9.65, 1.42, inlay_z), parent=ext)
    W.box("ElevInlay_L", (1.84, 0.14, 0.004), granite_m, c, (-10.50, 0.45, inlay_z), parent=ext)
    W.box("ElevInlay_R", (1.84, 0.14, 0.004), granite_m, c, (-10.50, 2.39, inlay_z), parent=ext)

    # 4) Fluorescent ceiling troffers + practical AREA lights along extended corridor
    for tx in (-6.4, -9.8):
        _molded(f"HallExt_Troffer_{tx}", (1.18, 0.34, 0.04), troffer_m, c, (tx, 1.44, 2.74), ext, 0.005)
        W.box(f"HallExt_LED_{tx}", (1.10, 0.26, 0.01), led_m, c, (tx, 1.44, 2.718), parent=ext)
        ld = bpy.data.lights.new(f"HallExtLight_{tx}", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = 2.4, 1.0
        ld.energy = 145
        ld.color = (0.94, 0.96, 1.0)
        ld.use_shadow = False
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (tx, 1.44, 2.66)
        lo.parent = ext
        c.objects.link(lo)

    # 5) ELEVATOR END WALL at X = -11.50 (facing +X, viewer's LEFT = smaller Y, RIGHT = larger Y)
    ex = -11.50
    # Left gray granite flank (Y = 0.00 .. 0.72) & Right gray granite flank (Y = 2.12 .. 2.86)
    W.box("ElevWall_Left", (0.10, 0.74, 2.80), gray_granite_m, c, (ex - 0.05, 0.36, 1.40), parent=ext)
    W.box("ElevWall_Right", (0.10, 0.78, 2.80), gray_granite_m, c, (ex - 0.05, 2.50, 1.40), parent=ext)
    # Center polished black granite surround (Y = 0.72 .. 2.12, flush slightly proud of gray granite)
    W.box("ElevGranite_L", (0.12, 0.16, 2.80), granite_m, c, (ex - 0.04, 0.80, 1.40), parent=ext)
    W.box("ElevGranite_R", (0.12, 0.16, 2.80), granite_m, c, (ex - 0.04, 2.04, 1.40), parent=ext)
    W.box("ElevGranite_Top", (0.12, 1.40, 0.42), granite_m, c, (ex - 0.04, 1.42, 2.58), parent=ext)

    # Recessed brushed stainless steel elevator portal (opening Y = 0.88 .. 1.96, width = 1.08m, height = 2.38m)
    # Outer stainless trim frame
    _molded("ElevFrame_L", (0.04, 0.035, 2.40), steel_m, c, (ex + 0.01, 0.88, 1.20), ext, 0.003)
    _molded("ElevFrame_R", (0.04, 0.035, 2.40), steel_m, c, (ex + 0.01, 1.96, 1.20), ext, 0.003)
    _molded("ElevFrame_Top", (0.04, 1.12, 0.04), steel_m, c, (ex + 0.01, 1.42, 2.39), ext, 0.003)
    # Deep recessed side jambs & soffit (X = -11.50 back to -11.74)
    W.box("ElevJamb_L", (0.26, 0.025, 2.38), steel_m, c, (ex - 0.12, 0.88, 1.19), parent=ext)
    W.box("ElevJamb_R", (0.26, 0.025, 2.38), steel_m, c, (ex - 0.12, 1.96, 1.19), parent=ext)
    W.box("ElevSoffit", (0.26, 1.08, 0.03), steel_m, c, (ex - 0.12, 1.42, 2.07), parent=ext)
    # Stainless transom header fascia (Z = 2.07 .. 2.38) + '1호기' & red LED '3' texture
    W.box("ElevHeader_Back", (0.06, 1.08, 0.31), steel_m, c, (ex - 0.02, 1.42, 2.225), parent=ext)
    _textured_plane(c, ext, "ElevHeader_Display", "sangga_elev/elev_header_3f.png", 1.06, 0.29,
                    (ex + 0.015, 1.42, 2.225), rot=(0, 0, math.pi / 2), strength=1.15, shaded=False)
    # Dark interior backing behind doors (exterior-only for now; doors slide cleanly in front of it)
    W.box("ElevShaft_Backing", (0.04, 1.12, 2.10), seam_m, c, (ex - 0.28, 1.42, 1.04), parent=ext)
    # Floor threshold sill (brushed metal track)
    _molded("Elev_Sill", (0.24, 1.08, 0.012), chrome_m, c, (ex - 0.12, 1.42, 0.006), ext, 0.002)

    # Separable twin sliding doors (Elev_Door_L & Elev_Door_R — ready to animate open/close along Y!)
    door_x = ex - 0.23
    door_l = _molded("Elev_Door_L", (0.032, 0.534, 2.05), door_steel_m, c, (door_x, 1.150, 1.032), ext, 0.002)
    door_r = _molded("Elev_Door_R", (0.032, 0.534, 2.05), door_steel_m, c, (door_x, 1.690, 1.032), ext, 0.002)
    # Safety stickers near top-center of each door leaf (parented to each door so they move with it!)
    _textured_plane(c, door_l, "ElevSticker_L", "sangga_elev/elev_sticker.png", 0.09, 0.11,
                    (0.019, 0.18, 0.66), rot=(0, 0, math.pi / 2), shaded=True)
    _textured_plane(c, door_r, "ElevSticker_R", "sangga_elev/elev_sticker.png", 0.09, 0.11,
                    (0.019, -0.18, 0.66), rot=(0, 0, math.pi / 2), shaded=True)

    # Twin round white wall lamps flanking the elevator (Photo #1 & #2 signature detail!)
    for side_tag, ly in (("L", 0.78), ("R", 2.05)):
        for idx, lz in enumerate((2.04, 2.24)):
            W.cyl(f"ElevLampBase_{side_tag}{idx}", 0.042, 0.025, chrome_m, c, (ex + 0.025, ly, lz), (0, 90, 0), parent=ext, seg=14)
            W.cyl(f"ElevLampBulb_{side_tag}{idx}", 0.034, 0.038, lamp_glow_m, c, (ex + 0.042, ly, lz), (0, 90, 0), parent=ext, seg=14)

    # Elevator call button panel on right black granite strip (Y = 2.05, Z = 1.08)
    _molded("ElevCallPlate", (0.018, 0.085, 0.24), steel_m, c, (ex + 0.022, 2.05, 1.08), ext, 0.003)
    for b_idx, bz in enumerate((1.13, 1.05)):
        W.cyl(f"ElevBtnRing_{b_idx}", 0.016, 0.012, chrome_m, c, (ex + 0.033, 2.05, bz), (0, 90, 0), parent=ext, seg=12)
        W.cyl(f"ElevBtnGlow_{b_idx}", 0.011, 0.014, btn_glow_m, c, (ex + 0.035, 2.05, bz), (0, 90, 0), parent=ext, seg=12)

    # 6) LEFT SIDE (Y = 0.00 .. 0.72): Korean indoor fire hydrant (옥내소화전) + floor extinguisher + 3F sign
    # High-detail 3D stainless fire hydrant cabinet (alarm panel + hose door) flush on the left gray granite flank
    build_indoor_fire_hydrant(c, ext, (ex + 0.03, 0.36, 1.24))
    # Gold '3F' floor number above hydrant (Photo #1 style!)
    _text(c, ext, "Elev_3F_Label", "3F", (ex + 0.018, 0.36, 2.02), 0.16, gold_m, rot=(math.pi / 2, 0, math.pi / 2))
    # Red Korean 3.3kg fire extinguisher on floor right in front of hydrant
    ext_left = W.empty("Elev_Extinguisher", c, (ex + 0.24, 0.32, 0.0), parent=ext)
    ext_left.rotation_euler.z = math.radians(78)
    korean_fire_extinguisher(c, ext_left)

    # 7) RIGHT SIDE (Y = 2.12 .. 2.86 & right corridor wall): Floor guide, orange notice, X-banners, cluttered clinic ads
    # Floor directory (층별안내) & orange notice on right gray granite flank
    _molded("ElevFloorGuide_Frame", (0.022, 0.64, 0.44), steel_m, c, (ex + 0.015, 2.48, 1.66), ext, 0.003)
    _textured_plane(c, ext, "ElevFloorGuide_Face", "sangga_elev/floor_guide.png", 0.61, 0.41,
                    (ex + 0.028, 2.48, 1.66), rot=(0, 0, math.pi / 2), shaded=True)
    _textured_plane(c, ext, "ElevOrangeNotice_Face", "sangga_elev/notice_orange.png", 0.60, 0.38,
                    (ex + 0.015, 2.48, 1.14), rot=(0, 0, math.pi / 2), shaded=True)

    # Two standing X-banners crowding the right side near the elevator (exact Photo #1 cluttered sangga vibe!)
    _standing_xbanner(c, ext, "Elev_XBanner_Golf", "sangga_elev/xbanner_golf.jpg",
                      (ex + 0.42, 2.34, 0.0), rot_z_deg=68.0, width=0.54, height=1.48)
    _standing_xbanner(c, ext, "Elev_XBanner_Mart", "sangga_elev/xbanner_mart.png",
                      (ex + 1.18, 2.46, 0.0), rot_z_deg=38.0, width=0.56, height=1.52)

    # Cluttered commercial clinic & shop ad panels along the right corridor wall (Y = 2.85, facing -Y)
    ad_y = 2.845
    # Dermatology clinic panel (피부과)
    _molded("AdPanel_Derma_Frame", (1.18, 0.03, 0.84), steel_m, c, (-9.85, ad_y, 1.62), ext, 0.004)
    _textured_plane(c, ext, "AdPanel_Derma", "sangga_elev/ad_derma.png", 1.14, 0.80,
                    (-9.85, ad_y - 0.018, 1.62), shaded=True)
    # Dental clinic panel (치과)
    _molded("AdPanel_Dental_Frame", (1.18, 0.03, 0.84), steel_m, c, (-8.45, ad_y, 1.62), ext, 0.004)
    _textured_plane(c, ext, "AdPanel_Dental", "sangga_elev/ad_dental.png", 1.14, 0.80,
                    (-8.45, ad_y - 0.018, 1.62), shaded=True)
    # Extra lower notice board below dermatology/dental panels for authentic sangga clutter
    _molded("AdPanel_Notice_Frame", (0.76, 0.025, 0.48), dark_m, c, (-9.15, ad_y, 0.86), ext, 0.003)
    _textured_plane(c, ext, "AdPanel_Notice", "sangga_elev/notice_orange.png", 0.72, 0.44,
                    (-9.15, ad_y - 0.016, 0.86), shaded=True)

    # Vacant commercial storefront with stainless mullions + big red '임대문의' banner cleanly inside left bay (X = -7.50 .. -4.85)
    for mx in (-7.50, -6.18, -4.85):
        _molded("Vacant_MullionV", (0.055, 0.075, 2.64), steel_m, c, (mx, 2.84, 1.42), ext, 0.004)
    for mz, mh in ((0.11, 0.045), (2.18, 0.075), (2.71, 0.055)):
        _molded("Vacant_MullionH", (2.70, 0.078, mh), steel_m, c, (-6.175, 2.84, mz), ext, 0.004)
    W.box("Vacant_Glass", (2.60, 0.02, 2.55), frosted_m, c, (-6.175, 2.85, 1.40), parent=ext)
    _textured_plane(c, ext, "Vacant_ForLease", "sangga_elev/for_lease.png", 1.12, 0.84,
                    (-6.84, 2.825, 1.44), shaded=True)
    # Clean stainless vertical trim pillar at the gym-wall junction (X = -4.65, Y = 0.02)
    _molded("HallExt_GymJunctionTrim", (0.06, 0.08, 2.75), steel_m, c, (-4.65, 0.02, 1.375), ext, 0.004)

    build_hallway_ext_details(c, ext, steel_m, granite_m)


def build_hallway_ext_details(c, ext, steel_m, granite_m):
    """Lived-in Korean commercial 3rd-floor sangga hallway details along the 7m extended corridor:
    - Gym-side wall (Y = 0.0, facing +Y): steel fire stair door + green EXIT sign + door closer + lever handle,
      aluminum sangga notice bulletin board, WatchCoach Gym directional poster, CCTV/No-Smoking sign.
    - Ceiling (Z = 2.75): 3 projecting illuminated lightbox signs (Derma, Dental, WatchCoach Gym),
      2 dome CCTV cameras, 3 smoke detectors with red LED dots, 2 recessed PA speakers.
    - Floor corners (clear of walkway): stainless hallway trash bin, yellow Wet Floor A-frame sign,
      2 stacked kraft cardboard delivery boxes."""
    det = W.empty("Sangga_Hallway_Ext_Details", c, (0, 0, 0), parent=ext)

    frame_m = bpy.data.materials.get("Hallway_SignFrame") or W.mat("Hallway_SignFrame", (0.04, 0.045, 0.05), rough=0.40, metal=0.55)
    dark_m = bpy.data.materials.get("Hallway_DarkSteel") or W.mat("Hallway_DarkSteel", (0.03, 0.032, 0.036), rough=0.45, metal=0.50)
    chrome_m = bpy.data.materials.get("Elev_Chrome") or W.mat("Elev_Chrome", (0.82, 0.84, 0.86), rough=0.14, metal=0.96)
    door_gray_m = W.mat("FireDoor_SteelGray", (0.34, 0.36, 0.38), rough=0.44, metal=0.35)
    door_frame_m = W.mat("FireDoor_FrameDark", (0.14, 0.15, 0.16), rough=0.42, metal=0.45)
    wire_glass_m = W.mat("FireDoor_WireGlass", (0.16, 0.20, 0.22), rough=0.18, metal=0.10)
    exit_green_m = W.shadeless("HallExt_ExitGreen", (0.06, 0.92, 0.34), strength=3.4)
    white_plast_m = W.mat("Ceil_WhitePlastic", (0.86, 0.87, 0.86), rough=0.42, metal=0.02)
    dome_glass_m = W.mat("CCTV_SmokedDome", (0.02, 0.022, 0.028), rough=0.06, metal=0.12)
    red_dot_m = W.shadeless("SmokeDet_RedLED", (1.0, 0.08, 0.05), strength=4.5)
    yellow_m = W.mat("WetFloor_Yellow", (0.88, 0.68, 0.03), rough=0.35, metal=0.04)
    kraft_m = W.mat("Cardboard_Kraft", (0.48, 0.34, 0.20), rough=0.84, metal=0.0)
    tape_m = W.mat("Cardboard_Tape", (0.64, 0.52, 0.34), rough=0.35, metal=0.0)
    label_m = W.mat("Cardboard_Label", (0.90, 0.90, 0.88), rough=0.65, metal=0.0)

    # 1) Steel Fire Stair Door on Y = 0.0 wall at X = -8.65 (facing +Y)
    fd = W.empty("HallExt_FireDoor", c, (-8.65, 0.04, 0.0), parent=det)
    # Outer dark steel doorframe
    _molded("FD_Frame_L", (0.06, 0.08, 2.14), door_frame_m, c, (0.49, 0.01, 1.07), fd, 0.004)
    _molded("FD_Frame_R", (0.06, 0.08, 2.14), door_frame_m, c, (-0.49, 0.01, 1.07), fd, 0.004)
    _molded("FD_Frame_T", (1.04, 0.08, 0.06), door_frame_m, c, (0.0, 0.01, 2.12), fd, 0.004)
    # Recessed painted steel door slab
    _molded("FD_Slab", (0.92, 0.045, 2.07), door_gray_m, c, (0.0, 0.005, 1.045), fd, 0.004)
    # Narrow wired-glass vision panel on the handle side
    _molded("FD_GlassFrame", (0.18, 0.055, 0.72), door_frame_m, c, (0.24, 0.012, 1.48), fd, 0.003)
    W.box("FD_GlassPane", (0.13, 0.060, 0.67), wire_glass_m, c, (0.24, 0.014, 1.48), parent=fd)
    # Chrome lever handle + escutcheon plate
    _molded("FD_Plate", (0.05, 0.012, 0.22), chrome_m, c, (0.37, 0.032, 0.98), fd, 0.003)
    W.cyl("FD_HandleStem", 0.011, 0.05, chrome_m, c, (0.37, 0.055, 1.00), (90, 0, 0), parent=fd, seg=10)
    _molded("FD_Lever", (0.12, 0.018, 0.022), chrome_m, c, (0.32, 0.082, 1.00), fd, 0.004)
    # Hydraulic door closer box + arm at top
    _molded("FD_CloserBox", (0.20, 0.05, 0.055), chrome_m, c, (-0.24, 0.05, 2.02), fd, 0.004)
    _molded("FD_CloserArm", (0.22, 0.016, 0.016), dark_m, c, (-0.12, 0.065, 2.06), fd, 0.002)
    # '방화문 항상 닫아두세요' sticker on door face (+Y normal -> rot Z = pi)
    _textured_plane(c, fd, "FD_Sticker", "sangga_elev/fire_door_sticker.jpg", 0.26, 0.18,
                    (-0.14, 0.031, 1.48), rot=(0, 0, math.pi), shaded=True)
    # Glowing green EXIT sign above the fire door
    _molded("FD_ExitBox", (0.34, 0.06, 0.15), white_plast_m, c, (0.0, 0.03, 2.34), fd, 0.004)
    W.box("FD_ExitGlow", (0.29, 0.012, 0.11), exit_green_m, c, (0.0, 0.062, 2.34), parent=fd)
    _text(c, fd, "FD_ExitText", "비상구", (0.0, 0.070, 2.34), 0.062, white_plast_m, rot=(math.pi / 2, 0, math.pi))

    # 2) Large Glossy Floor Directory ('INFORMATION 워치코치 플라자 상가', Photo 1 style!) at X = -10.32
    _molded("FloorDir_Frame", (1.44, 0.028, 0.90), steel_m, c, (-10.32, 0.042, 1.50), det, 0.004)
    fd_face = _textured_plane(c, det, "FloorDir_Face", "sangga_elev/floor_directory_big.jpg", 1.38, 0.85,
                              (-10.32, 0.059, 1.50), rot=(0, 0, math.pi), shaded=True)
    # Give floor directory glossy acrylic reflection matching Photo 1!
    for n in fd_face.data.materials[0].node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Roughness"].default_value = 0.14
            if "Coat Weight" in n.inputs:
                n.inputs["Coat Weight"].default_value = 0.65

    # 3) 8-Pocket Acrylic Poster Bulletin Board ('WATCHCOACH PLAZA', Photo 2 style!) at X = -6.72
    # Reuses existing packed student_discount.jpg & training.jpg datablocks in scene_gym.blend (0 extra bytes!)
    pb = W.empty("HallExt_PosterBoard", c, (-6.72, 0.042, 1.44), parent=det)
    burgundy_m = W.mat("Board_Burgundy", (0.20, 0.08, 0.11), rough=0.38, metal=0.12)
    pocket_rim_m = W.mat("Board_PocketSilver", (0.64, 0.66, 0.68), rough=0.30, metal=0.72)
    empty_dark_m = W.mat("Board_EmptyDark", (0.04, 0.04, 0.045), rough=0.45, metal=0.05)
    # Outer silver trim + burgundy backing + bottom silver channel bar
    _molded("PB_OuterFrame", (1.46, 0.026, 0.98), pocket_rim_m, c, (0, 0, 0), pb, 0.004)
    _molded("PB_Backing", (1.40, 0.022, 0.92), burgundy_m, c, (0, 0.006, 0), pb, 0.003)
    _molded("PB_BottomBar", (1.38, 0.018, 0.055), pocket_rim_m, c, (0, 0.016, -0.425), pb, 0.003)
    # Arched burgundy top crest with white 'WATCHCOACH PLAZA' title
    _molded("PB_CrestOuter", (0.56, 0.026, 0.13), pocket_rim_m, c, (0, 0, 0.54), pb, 0.012)
    _molded("PB_CrestInner", (0.52, 0.028, 0.11), burgundy_m, c, (0, 0.004, 0.535), pb, 0.010)
    _text(c, pb, "PB_CrestText", "WATCHCOACH PLAZA", (0, 0.022, 0.535), 0.042, white_plast_m, rot=(math.pi / 2, 0, math.pi))

    def _reused_pocket_plane(pname, img_key, loc_xyz):
        im = bpy.data.images.get(img_key)
        if not im:
            return
        m = bpy.data.materials.new(f"Mat_{pname}")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Roughness"].default_value = 0.25
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = im
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        hw, hh = 0.265 / 2, 0.355 / 2
        me = bpy.data.meshes.new(pname)
        me.from_pydata([(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new()
        for loop, coord in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop.uv = coord
        me.materials.append(m)
        ob = bpy.data.objects.new(pname, me)
        ob.location = loc_xyz
        ob.rotation_euler = (0, 0, math.pi)
        ob.parent = pb
        c.objects.link(ob)

    # 8 individual 3D silver acrylic pockets (2 rows x 4 cols; on Y=0 wall facing +Y, viewer's left->right is +X->-X!)
    col_xs = (0.48, 0.16, -0.16, -0.48)
    row_zs = (0.24, -0.18)
    top_imgs = ("sangga_elev/notice_a4_1.jpg", "sangga_elev/notice_a4_2.jpg",
                "sangga_elev/notice_a4_3.jpg", "sangga_elev/notice_a4_4.jpg")
    for r_i, pz in enumerate(row_zs):
        for c_i, px in enumerate(col_xs):
            tag = f"PB_P{r_i}_{c_i}"
            _molded(f"{tag}_frame", (0.295, 0.016, 0.385), pocket_rim_m, c, (px, 0.018, pz), pb, 0.002)
            # Iconic semicircular thumb-cutout notch at top center of each acrylic pocket
            W.cyl(f"{tag}_notch", 0.018, 0.018, burgundy_m, c, (px, 0.022, pz + 0.184), (90, 0, 0), parent=pb, seg=12)
            if r_i == 0:
                _textured_plane(c, pb, f"{tag}_doc", top_imgs[c_i], 0.265, 0.355,
                                (px, 0.028, pz), rot=(0, 0, math.pi), shaded=True)
            else:
                if c_i == 0:
                    # Empty dark acrylic pocket (exact Photo 2 lived-in realism!)
                    W.box(f"{tag}_empty", (0.265, 0.004, 0.355), empty_dark_m, c, (px, 0.026, pz), parent=pb)
                elif c_i == 1:
                    _reused_pocket_plane(f"{tag}_student", "student_discount.jpg", (px, 0.028, pz))
                elif c_i == 2:
                    _reused_pocket_plane(f"{tag}_training", "training.jpg", (px, 0.028, pz))
                else:
                    _textured_plane(c, pb, f"{tag}_flyer", "sangga_elev/flyer_english_yellow.jpg", 0.265, 0.355,
                                    (px, 0.028, pz), rot=(0, 0, math.pi), shaded=True)

    # Yellow '금연 No Smoking Area' sticker right beside the bulletin board (Photo 2 detail!)
    _molded("PB_NoSmokeBack", (0.23, 0.012, 0.30), white_plast_m, c, (-5.84, 0.040, 1.56), det, 0.002)
    _textured_plane(c, det, "PB_NoSmokeFace", "sangga_elev/nosmoke_yellow.jpg", 0.215, 0.285,
                    (-5.84, 0.049, 1.56), rot=(0, 0, math.pi), shaded=True)

    # 4) WatchCoach Gym Directional Poster ('← 워치코치 짐 302호', pointing toward +X gym entrance!) at X = -5.22
    _molded("GymDir_Frame", (0.58, 0.025, 0.84), dark_m, c, (-5.22, 0.042, 1.48), det, 0.004)
    _textured_plane(c, det, "GymDir_Face", "sangga_elev/gym_dir_poster.jpg", 0.54, 0.80,
                    (-5.22, 0.058, 1.48), rot=(0, 0, math.pi), shaded=True)

    # 5) 3 Projecting Illuminated Lightbox Signs in varied shapes (square, rect, round)
    for s_name, style, img_rel, x_pos, z_pos in (
        ("Sign_Derma", "square", "sangga_elev/sign_derma.jpg", -9.70, 2.36),
        ("Sign_Dental", "rect", "sangga_elev/sign_dental.jpg", -8.25, 2.38),
        ("Sign_WatchCoach", "round", "sangga_elev/sign_watchcoach.jpg", -5.65, 2.34),
    ):
        _projecting_sign(c, det, s_name, style, img_rel, x_pos, y_wall=2.84, z_pos=z_pos)

    # 6) Ceiling Hardware: 2 Dome CCTV Cameras, 3 Smoke Detectors, 2 Recessed PA Speakers
    for idx, (cx, cy) in enumerate(((-10.40, 0.38), (-5.90, 2.52))):
        W.cyl(f"CCTV_Base_{idx}", 0.068, 0.032, white_plast_m, c, (cx, cy, 2.73), parent=det, seg=16)
        bm_d = bmesh.new()
        bmesh.ops.create_uvsphere(bm_d, u_segments=14, v_segments=8, radius=0.052)
        me_d = bpy.data.meshes.new(f"CCTV_Dome_{idx}")
        bm_d.to_mesh(me_d)
        bm_d.free()
        me_d.materials.append(dome_glass_m)
        ob_d = bpy.data.objects.new(f"CCTV_Dome_{idx}", me_d)
        ob_d.location = (cx, cy, 2.708)
        ob_d.parent = det
        c.objects.link(ob_d)
    for idx, sx in enumerate((-9.10, -7.20, -5.20)):
        W.cyl(f"SmokeDet_Body_{idx}", 0.055, 0.024, white_plast_m, c, (sx, 1.46, 2.735), parent=det, seg=14)
        W.cyl(f"SmokeDet_LED_{idx}", 0.008, 0.010, red_dot_m, c, (sx + 0.028, 1.46, 2.722), parent=det, seg=8)
    for idx, px in enumerate((-10.50, -6.50)):
        W.cyl(f"CeilSpeaker_Rim_{idx}", 0.095, 0.012, white_plast_m, c, (px, 1.46, 2.742), parent=det, seg=18)
        W.cyl(f"CeilSpeaker_Mesh_{idx}", 0.072, 0.014, door_gray_m, c, (px, 1.46, 2.740), parent=det, seg=16)

    # 7) Stainless Hallway Trash Bin tucked beside the fire door (X = -7.80, Y = 0.24)
    tb = W.empty("HallExt_TrashBin", c, (-7.80, 0.24, 0.0), parent=det)
    _molded("TrashBin_Body", (0.34, 0.28, 0.68), steel_m, c, (0, 0, 0.34), tb, 0.010)
    _molded("TrashBin_Rim", (0.36, 0.30, 0.04), dark_m, c, (0, 0, 0.69), tb, 0.006)
    _molded("TrashBin_Slot", (0.24, 0.16, 0.02), granite_m, c, (0, 0.02, 0.705), tb, 0.004)

    # 8) Yellow '미끄럼 주의 (CAUTION WET FLOOR)' A-Frame Sign near vacant storefront corner (X = -7.05, Y = 2.48)
    wf = W.empty("HallExt_WetFloorSign", c, (-7.05, 2.48, 0.0), parent=det)
    wf.rotation_euler.z = math.radians(-16.0)
    for side, ang in ((-1, -13.0), (1, 13.0)):
        board = _molded(f"WetFloor_Board_{side}", (0.30, 0.014, 0.60), yellow_m, c, (0, side * 0.07, 0.295), wf, 0.003)
        board.rotation_euler.x = math.radians(ang)
        _textured_plane(c, board, f"WetFloor_Face_{side}", "sangga_elev/wet_floor.jpg", 0.26, 0.42,
                        (0, side * 0.009, 0.01), rot=(0, 0, 0 if side < 0 else math.pi), shaded=True)
    # Top hinge / carrying handle bar where both boards meet
    _molded("WetFloor_Top", (0.30, 0.032, 0.03), yellow_m, c, (0, 0, 0.585), wf, 0.006)

    # 9) Stacked Cardboard Delivery Boxes tucked against right clinic wall (X = -8.95, Y = 2.58)
    bx = W.empty("HallExt_DeliveryBoxes", c, (-8.95, 2.58, 0.0), parent=det)
    b1 = _molded("DeliveryBox_Bottom", (0.44, 0.34, 0.30), kraft_m, c, (0, 0, 0.15), bx, 0.005)
    b1.rotation_euler.z = math.radians(6.0)
    W.box("DeliveryBox_Tape1", (0.445, 0.05, 0.004), tape_m, c, (0, 0, 0.152), parent=b1)
    W.box("DeliveryBox_Label1", (0.11, 0.004, 0.08), label_m, c, (0.08, -0.171, 0.03), parent=b1)
    b2 = _molded("DeliveryBox_Top", (0.34, 0.26, 0.22), kraft_m, c, (-0.03, 0.02, 0.41), bx, 0.005)
    b2.rotation_euler.z = math.radians(-11.0)
    W.box("DeliveryBox_Tape2", (0.345, 0.045, 0.004), tape_m, c, (0, 0, 0.112), parent=b2)
    W.box("DeliveryBox_Label2", (0.09, 0.004, 0.07), label_m, c, (-0.04, -0.131, 0.02), parent=b2)




# ---------------------------------------------------------------------------
# Korean indoor fire hydrant cabinet (옥내소화전 + 발신기 경보 패널), built part by part.
# All parts live under a "face" empty whose local axes are: x = across the cabinet (viewer's right),
# y = up, z = out of the wall (z = 0 is the wall surface). Sizes below are in metres.
# ---------------------------------------------------------------------------

def _hyd_brushed_mat(name, vertical=False):
    """Brushed stainless with fine hairline grain (direction = along x, or along y when vertical)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1400.0, 4.0, 4.0) if vertical else (4.0, 1400.0, 4.0)
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 1.0
    fine.inputs["Detail"].default_value = 4.0
    broad = nt.nodes.new("ShaderNodeTexNoise")
    broad.inputs["Scale"].default_value = 9.0
    broad.inputs["Detail"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.45
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[0].color = (0.57, 0.575, 0.58, 1.0)
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = (0.68, 0.685, 0.69, 1.0)
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["From Min"].default_value = 0.3
    rough.inputs["From Max"].default_value = 0.7
    rough.inputs["To Min"].default_value = 0.34
    rough.inputs["To Max"].default_value = 0.46
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.02
    bump.inputs["Distance"].default_value = 0.0003
    L = nt.links.new
    L(tc.outputs["Object"], mp.inputs["Vector"])
    L(mp.outputs["Vector"], fine.inputs["Vector"])
    L(tc.outputs["Object"], broad.inputs["Vector"])
    L(fine.outputs["Fac"], mix.inputs["A"])
    L(broad.outputs["Fac"], mix.inputs["B"])
    L(mix.outputs["Result"], ramp.inputs["Fac"])
    L(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    L(fine.outputs["Fac"], rough.inputs["Value"])
    L(rough.outputs["Result"], bsdf.inputs["Roughness"])
    L(fine.outputs["Fac"], bump.inputs["Height"])
    L(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Metallic"].default_value = 1.0
    m.diffuse_color = (0.6, 0.6, 0.61, 1)
    return m


def _hyd_glass_mat(name="Hyd_ClearCover"):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.92, 0.94, 0.96, 1)
    b.inputs["Roughness"].default_value = 0.04
    b.inputs["Alpha"].default_value = 0.16
    try:
        m.surface_render_method = "BLENDED"
    except (AttributeError, TypeError):
        pass
    return m


def _hyd_lamp_mat(name="Hyd_LampDomeRed"):
    """Glowing red alarm-lamp dome: small pinkish-white hot core fading to saturated red, deep red at the rim."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.55, 0.02, 0.02, 1)
    b.inputs["Roughness"].default_value = 0.12
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / 0.030, 1 / 0.030, 0.0)
    grad = nt.nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.30, 0.0, 0.0, 1)
    els[1].position, els[1].color = 1.0, (1.0, 0.80, 0.74, 1)
    for pos, col in ((0.25, (0.80, 0.02, 0.015, 1)), (0.62, (1.0, 0.08, 0.04, 1)), (0.82, (1.0, 0.42, 0.34, 1))):
        e = els.new(pos)
        e.color = col
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 3.0
    m.diffuse_color = (1.0, 0.1, 0.05, 1)
    return m


def _hyd_smooth(ob, angle=38.0):
    me = ob.data
    try:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(angle))
    except (AttributeError, TypeError):
        for p in me.polygons:
            p.use_smooth = True
    return ob


def _hyd_bevel(ob, width, segments=3, angle=40.0):
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width = width
    bv.segments = segments
    bv.limit_method = "ANGLE"
    bv.angle_limit = math.radians(angle)
    return bv


def _hyd_stadium(w, h, n=14):
    """Outline of a vertical pill (stadium) shape centred on the origin, counter-clockwise."""
    r = w / 2
    s = max(h / 2 - r, 0.0)
    pts = [(r * math.cos(math.pi * i / n), s + r * math.sin(math.pi * i / n)) for i in range(n + 1)]
    pts += [(r * math.cos(math.pi + math.pi * i / n), -s + r * math.sin(math.pi + math.pi * i / n)) for i in range(n + 1)]
    return pts


def _hyd_prism(name, pts, z0, z1, material, c, parent, loc=(0, 0, 0)):
    """Extrude a convex 2D outline (x, y) between z0 and z1."""
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, z0)) for x, y in pts]
    hi = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(hi)
    bm.faces.new(list(reversed(lo)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return W.mesh_obj(name, bm, material, c, loc, (0, 0, 0), parent)


def _hyd_disc(name, r, z0, z1, material, c, parent, xy, seg=48):
    ob = W.cyl(name, r, z1 - z0, material, c, (xy[0], xy[1], (z0 + z1) / 2), parent=parent, seg=seg)
    return _hyd_smooth(ob)


def _hyd_dome(name, r, height, z_base, material, c, parent, xy, seg=40):
    """Half UV-sphere squashed to `height`, sitting on z_base and bulging toward +z."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -1e-6], context="VERTS")
    bmesh.ops.scale(bm, vec=(1.0, 1.0, height / r), verts=bm.verts)
    ob = W.mesh_obj(name, bm, material, c, (xy[0], xy[1], z_base), (0, 0, 0), parent)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def _hyd_apply_cuts(ob, cutters):
    """Bake the object's modifier stack plus boolean DIFFERENCE cuts into its mesh, then drop the cutters."""
    for k, cu in enumerate(cutters):
        md = ob.modifiers.new(f"Cut{k}", "BOOLEAN")
        md.operation = "DIFFERENCE"
        md.object = cu
        md.solver = "EXACT"
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = ob.name
    bpy.data.meshes.remove(old)
    for cu in cutters:
        cm = cu.data
        bpy.data.objects.remove(cu, do_unlink=True)
        bpy.data.meshes.remove(cm)
    return ob


def _hyd_pocket_handle(name, w, h, z_face, c, parent, xy, plastic_m, cavity_m, depth=0.0095, rim=0.0045):
    """Recessed grey plastic pull pocket: pill-shaped 2 mm flange on the panel and a hollow tray behind it.
    Returns the cutter outline (w, h) that has to be cut through the panel."""
    t, lip, n = 0.0014, 0.0018, 16
    outer = _hyd_stadium(w, h, n)
    inner = _hyd_stadium(w - 2 * rim, h - 2 * rim, n)
    mid = _hyd_stadium(w - 2 * rim + 2 * t, h - 2 * rim + 2 * t, n)
    loops = [(outer, z_face + lip), (outer, z_face), (mid, z_face), (mid, z_face - depth - t),
             (inner, z_face - depth), (inner, z_face + lip)]
    bm = bmesh.new()
    rings = [[bm.verts.new((x, y, z)) for x, y in pts] for pts, z in loops]
    m = len(outer)
    for a, b_ in ((0, 1), (1, 2), (2, 3), (4, 5), (5, 0)):
        ra, rb = rings[a], rings[b_]
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    bm.faces.new(rings[3])
    bm.faces.new(list(reversed(rings[4])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    tray = W.mesh_obj(name, bm, plastic_m, c, (xy[0], xy[1], 0), (0, 0, 0), parent)
    tray.data.materials.append(cavity_m)
    for p in tray.data.polygons:  # darker, slightly sooty inner floor of the pocket
        if p.normal.z > 0.9 and p.center.z < z_face - depth * 0.5:
            p.material_index = 1
    _hyd_smooth(tray, 50.0)
    return (w - 2 * rim + 2 * t + 0.0008, h - 2 * rim + 2 * t + 0.0008)


def _hyd_letter(name, body, size, xy, z_back, material, c, parent, extrude=0.0024, bevel=0.0012, embolden=0.0):
    """Real 3D bevelled letter mesh whose back face floats ~1.5 mm in front of z_back (soft contact shadow)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = W.load_font(W.KFONT)
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    cu.offset = embolden
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    c.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    off = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
    for v in me.vertices:
        v.co -= off
    me.materials.clear()
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.parent = parent
    ob.location = (xy[0], xy[1], z_back + 0.0015)
    return _hyd_smooth(ob, 32.0)


def _hyd_decal(name, img_name, w, h, xy, z, c, parent, rough=0.38):
    """UV-mapped image plane facing +z (sticker / printed plate) with a shaded semi-gloss material."""
    im = bpy.data.images.load(os.path.join(W.PARTS, img_name), check_existing=True)
    if not im.packed_file:
        im.pack()
    m = bpy.data.materials.new(f"Mat_{name}")
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Roughness"].default_value = rough
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = im
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    hw, hh = w / 2, h / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for loop, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = co
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = (xy[0], xy[1], z)
    ob.parent = parent
    c.objects.link(ob)
    return ob


def build_indoor_fire_hydrant(c, parent, loc, name="Elev_FireHydrant"):
    """High-detail Korean flush-mounted indoor fire hydrant cabinet (옥내소화전) matching the reference photo:
    mitered brushed-stainless outer frame, upper alarm panel (pull pocket, red round 발신기 with blue plate and
    clear push-button window, glowing red 표시등 + chrome pilot lamp, red pump switch box with clear cover,
    perforated speaker grille, red 관리번호 plate) split by a stainless bar from the lower door (사용방법 sticker,
    pull pocket, raised bevelled gold 소/화/전 and 방수구 letters). 0.60 m x 1.06 m, 22 mm proud of the wall.
    `loc` is the cabinet centre in `parent` space, 30 mm in front of a wall facing parent +X."""
    root = W.empty(name, c, loc, parent=parent)
    face = W.empty("Hydrant_FaceFrame", c, (-0.03, 0.0, 0.0), parent=root, size=0.05)
    face.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)

    W2, H2, F = 0.300, 0.530, 0.035          # half width, half height, frame band
    IW, IH = W2 - F, H2 - F                   # inner opening half sizes (0.265, 0.495)
    Z_FRAME, Z_PANEL, Z_DOOR, Z_BACK = 0.022, 0.016, 0.0172, 0.0062

    steel_h = _hyd_brushed_mat("Hyd_BrushedSteel_H")
    steel_v = _hyd_brushed_mat("Hyd_BrushedSteel_V", vertical=True)
    seam_m = W.mat("Hyd_DarkSeam", (0.012, 0.012, 0.014), rough=0.7, metal=0.1)
    plastic_m = W.mat("Hyd_GreyPlastic", (0.30, 0.32, 0.34), rough=0.42, metal=0.0)
    cavity_m = W.mat("Hyd_PocketShadow", (0.17, 0.18, 0.19), rough=0.6, metal=0.0)
    red_m = W.mat("Hyd_RedPlastic", (0.62, 0.035, 0.03), rough=0.30, metal=0.0)
    red_dark_m = W.mat("Hyd_RedPlasticDark", (0.46, 0.025, 0.022), rough=0.36, metal=0.0)
    blue_m = W.mat("Hyd_BluePlate", (0.04, 0.16, 0.55), rough=0.32, metal=0.0)
    white_m = W.mat("Hyd_WhitePlastic", (0.86, 0.86, 0.84), rough=0.26, metal=0.0)
    lightgrey_m = W.mat("Hyd_WindowBack", (0.70, 0.71, 0.72), rough=0.45, metal=0.0)
    knob_m = W.mat("Hyd_DarkKnob", (0.05, 0.05, 0.055), rough=0.35, metal=0.2)
    chrome_m = W.mat("Hyd_Chrome", (0.86, 0.87, 0.89), rough=0.10, metal=1.0)
    pilot_m = W.mat("Hyd_PilotLensDark", (0.22, 0.008, 0.01), rough=0.08, metal=0.0)
    gold_m = W.mat("Hyd_GoldBrass", (1.0, 0.76, 0.32), rough=0.32, metal=1.0)
    glass_m = _hyd_glass_mat()
    lamp_m = _hyd_lamp_mat()

    # 1) Dark back pan: shows as the thin black gap lines around the panels and through the speaker holes
    W.box("Hydrant_BackPan", (2 * IW + 0.012, 2 * IH + 0.012, Z_BACK - 0.0006), seam_m, c,
          (0, 0, (Z_BACK + 0.0006) / 2), parent=face)

    # 2) Mitered (45 deg) brushed stainless outer frame; bevels make the fine V-groove at each miter
    bands = {
        "Top": ([(-W2, H2), (W2, H2), (W2 - F, H2 - F), (-W2 + F, H2 - F)], steel_h),
        "Bottom": ([(-W2, -H2), (-W2 + F, -H2 + F), (W2 - F, -H2 + F), (W2, -H2)], steel_h),
        "Left": ([(-W2, -H2), (-W2, H2), (-W2 + F, H2 - F), (-W2 + F, -H2 + F)], steel_v),
        "Right": ([(W2, -H2), (W2 - F, -H2 + F), (W2 - F, H2 - F), (W2, H2)], steel_v),
    }
    for side, (pts, m) in bands.items():
        fr = _hyd_prism(f"Hydrant_Frame_{side}", pts, 0.0006, Z_FRAME, m, c, face)
        _hyd_bevel(fr, 0.0011, 2, 30.0)

    # 3) Horizontal stainless divider bar between the alarm panel and the door
    SEP_LO, SEP_HI = 0.2550, 0.2840
    sep = W.box("Hydrant_DividerBar", (2 * IW - 0.0004, SEP_HI - SEP_LO, 0.020), steel_h, c,
                (0, (SEP_LO + SEP_HI) / 2, 0.0106), parent=face)
    _hyd_bevel(sep, 0.0012, 2, 30.0)

    # 4) Upper alarm panel (recessed 6 mm behind the frame face), speaker holes + pocket cut through it
    P_LO, P_HI = SEP_HI + 0.0025, IH - 0.0025
    panel = W.box("Hydrant_AlarmPanel", (2 * IW - 0.005, P_HI - P_LO, Z_PANEL - Z_BACK), steel_h, c,
                  (0, (P_LO + P_HI) / 2, (Z_PANEL + Z_BACK) / 2), parent=face)
    _hyd_bevel(panel, 0.0008, 1, 30.0)
    cutters = []
    # radial speaker perforation (centre + 4 staggered rings)
    spk = (0.208, 0.388)
    bm = bmesh.new()
    holes = [(0.0, 0.0)]
    for ring, (rad, cnt) in enumerate(((0.0105, 6), (0.0210, 10), (0.0315, 14), (0.0415, 16))):
        for k in range(cnt):
            a = 2 * math.pi * k / cnt + ring * 0.21
            holes.append((rad * math.cos(a), rad * math.sin(a)))
    for hx, hy in holes:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=0.0021, radius2=0.0021, depth=0.04,
                              matrix=Matrix.Translation((spk[0] + hx, spk[1] + hy, Z_PANEL)))
    cutters.append(W.mesh_obj("Hydrant_SpeakerCutter", bm, None, c, (0, 0, 0), (0, 0, 0), face))
    # pull pocket (upper)
    cut_w, cut_h = _hyd_pocket_handle("Hydrant_PocketHandle_Top", 0.037, 0.140, Z_PANEL, c, face,
                                      (-0.200, 0.391), plastic_m, cavity_m)
    cutters.append(_hyd_prism("Hydrant_PocketCutter_Top", _hyd_stadium(cut_w, cut_h, 16), -0.01, 0.05, None, c, face,
                              (-0.200, 0.391, 0)))
    _hyd_apply_cuts(panel, cutters)

    # 4a) Round red 발신기 (P-type manual call point)
    hx, hy = -0.105, 0.393
    housing = _hyd_disc("Hydrant_CallPoint_Housing", 0.068, Z_PANEL - 0.001, Z_PANEL + 0.024, red_m, c, face, (hx, hy), 64)
    _hyd_bevel(housing, 0.006, 4, 30.0)
    zf = Z_PANEL + 0.024
    plate = W.box("Hydrant_CallPoint_BluePlate", (0.044, 0.018, 0.0012), blue_m, c, (hx, hy + 0.045, zf + 0.0005), parent=face)
    _hyd_bevel(plate, 0.0004, 1, 30.0)
    _hyd_letter("Hydrant_CallPoint_Label", "발 신 기", 0.0095, (hx, hy + 0.0475), zf + 0.0011 - 0.0015, white_m, c, face,
                extrude=0.00012, bevel=0.0)
    _hyd_letter("Hydrant_CallPoint_SubLabel", "P형1급 발신기  누름스위치", 0.0026, (hx, hy + 0.0393), zf + 0.0011 - 0.0015,
                white_m, c, face, extrude=0.00006, bevel=0.0)
    boss = _hyd_disc("Hydrant_CallPoint_Boss", 0.0075, zf - 0.001, zf + 0.0022, red_dark_m, c, face, (hx, hy + 0.016), 32)
    _hyd_bevel(boss, 0.0012, 3, 30.0)
    wy = hy - 0.033
    ring = _hyd_disc("Hydrant_CallPoint_WindowRing", 0.0195, zf - 0.001, zf + 0.0026, red_dark_m, c, face, (hx, wy), 48)
    _hyd_bevel(ring, 0.0011, 3, 30.0)
    _hyd_disc("Hydrant_CallPoint_WindowBack", 0.0158, zf + 0.0026, zf + 0.0030, lightgrey_m, c, face, (hx, wy), 48)
    btn = _hyd_disc("Hydrant_CallPoint_PushButton", 0.0062, zf + 0.0030, zf + 0.0072, knob_m, c, face, (hx, wy), 32)
    _hyd_bevel(btn, 0.0012, 3, 30.0)
    _hyd_dome("Hydrant_CallPoint_ClearCover", 0.0165, 0.0075, zf + 0.0026, glass_m, c, face, (hx, wy))
    _hyd_disc("Hydrant_CallPoint_Screw", 0.0034, zf - 0.0005, zf + 0.0008, chrome_m, c, face, (hx, hy - 0.060), 20)

    # 4b) Glowing red 표시등 (white bezel) + dark red pilot lamp in a chrome bezel just below
    lx, ly = 0.004, 0.425
    bez = _hyd_disc("Hydrant_IndicatorLamp_Bezel", 0.038, Z_PANEL - 0.001, Z_PANEL + 0.012, white_m, c, face, (lx, ly), 64)
    _hyd_bevel(bez, 0.004, 4, 30.0)
    _hyd_disc("Hydrant_IndicatorLamp_Seat", 0.0315, Z_PANEL + 0.0105, Z_PANEL + 0.0125, red_dark_m, c, face, (lx, ly), 64)
    _hyd_dome("Hydrant_IndicatorLamp_Dome", 0.0300, 0.0150, Z_PANEL + 0.0118, lamp_m, c, face, (lx, ly), 48)
    ld = bpy.data.lights.new("Hydrant_IndicatorLamp_Glow", "POINT")
    ld.energy = 0.10
    ld.color = (1.0, 0.10, 0.05)
    ld.shadow_soft_size = 0.02
    ld.use_shadow = False
    lo = bpy.data.objects.new(ld.name, ld)
    lo.location = (lx, ly, Z_PANEL + 0.045)
    lo.parent = face
    c.objects.link(lo)
    px, py = 0.002, 0.348
    pb = _hyd_disc("Hydrant_PilotLamp_Bezel", 0.013, Z_PANEL - 0.001, Z_PANEL + 0.005, chrome_m, c, face, (px, py), 40)
    _hyd_bevel(pb, 0.0015, 3, 30.0)
    _hyd_dome("Hydrant_PilotLamp_Lens", 0.0088, 0.0048, Z_PANEL + 0.0045, pilot_m, c, face, (px, py), 32)

    # 4c) Red pump-start switch box: recessed housing, white toggle switch, clear flip cover, two dark screws
    sx, sy, sw, sh = 0.105, 0.3845, 0.072, 0.101
    box = W.box("Hydrant_PumpSwitch_Housing", (sw, sh, 0.027), red_m, c, (sx, sy, Z_PANEL + 0.0125), parent=face)
    _hyd_bevel(box, 0.003, 3, 30.0)
    rcut = W.box("Hydrant_PumpSwitch_RecessCutter", (0.054, 0.079, 0.02), None, c, (sx, sy, Z_PANEL + 0.024), parent=face)
    _hyd_apply_cuts(box, [rcut])
    zr = Z_PANEL + 0.014                     # recess floor (12 mm deep)
    W.box("Hydrant_PumpSwitch_Base", (0.050, 0.075, 0.004), white_m, c, (sx, sy, zr + 0.002), parent=face)
    lev = W.box("Hydrant_PumpSwitch_Lever", (0.016, 0.044, 0.0036), white_m, c, (sx, sy + 0.004, zr + 0.0058), parent=face)
    _hyd_bevel(lev, 0.0012, 3, 30.0)
    for k, dy in enumerate((-0.026, 0.030)):
        W.box(f"Hydrant_PumpSwitch_Tab{k}", (0.020, 0.008, 0.002), lightgrey_m, c, (sx, sy + dy, zr + 0.0050), parent=face)
    cov = W.box("Hydrant_PumpSwitch_ClearCover", (0.0525, 0.0775, 0.0016), glass_m, c, (sx, sy, Z_PANEL + 0.0235), parent=face)
    _hyd_bevel(cov, 0.0005, 1, 30.0)
    for k, dy in enumerate((-0.0455, 0.0455)):
        _hyd_disc(f"Hydrant_PumpSwitch_Screw{k}", 0.0024, Z_PANEL + 0.0255, Z_PANEL + 0.0275, knob_m, c, face, (sx, sy + dy), 16)

    # 4d) Red management-number plate (top right)
    np_ = W.box("Hydrant_NumberPlate", (0.113, 0.036, 0.0012), white_m, c, (0.199, 0.469, Z_PANEL + 0.0006), parent=face)
    _hyd_bevel(np_, 0.0004, 1, 30.0)
    _hyd_decal("Hydrant_NumberPlate_Print", "sangga_elev/hydrant_nameplate.png", 0.1126, 0.0356, (0.199, 0.469),
               Z_PANEL + 0.00123, c, face, rough=0.32)

    # 5) Lower hose-cabinet door (vertical hairline), with its own pull pocket cut through
    D_LO, D_HI = -IH + 0.0025, SEP_LO - 0.0025
    door = W.box("Hydrant_Door", (2 * IW - 0.005, D_HI - D_LO, Z_DOOR - Z_BACK), steel_v, c,
                 (0, (D_LO + D_HI) / 2, (Z_DOOR + Z_BACK) / 2), parent=face)
    _hyd_bevel(door, 0.0009, 1, 30.0)
    cut_w, cut_h = _hyd_pocket_handle("Hydrant_PocketHandle_Door", 0.038, 0.113, Z_DOOR, c, face,
                                      (-0.201, -0.1355), plastic_m, cavity_m)
    dcut = _hyd_prism("Hydrant_PocketCutter_Door", _hyd_stadium(cut_w, cut_h, 16), -0.01, 0.05, None, c, face,
                      (-0.201, -0.1355, 0))
    _hyd_apply_cuts(door, [dcut])

    # 5a) '소화전 사용방법' instruction sticker (top-left of the door)
    _hyd_decal("Hydrant_UsageSticker", "sangga_elev/hydrant_sticker.png", 0.190, 0.152, (-0.162, 0.171),
               Z_DOOR + 0.0003, c, face, rough=0.42)

    # 5b) Raised bevelled brass letters: 소 / 화 / 전 down the centre, 방 수 구 across the bottom
    for ch, y in (("소", 0.030), ("화", -0.138), ("전", -0.306)):
        _hyd_letter(f"Hydrant_GoldLetter_{ch}", ch, 0.068, (0.0, y), Z_DOOR, gold_m, c, face, embolden=0.0012)
    for ch, x in (("방", -0.115), ("수", 0.0), ("구", 0.115)):
        _hyd_letter(f"Hydrant_GoldLetter_{ch}", ch, 0.055, (x, -0.382), Z_DOOR, gold_m, c, face, embolden=0.0010)
    return root


def korean_fire_extinguisher(c, root):
    """High-detail Korean 3.3kg ABC fire extinguisher on sloped red pedestal stand,
    faithfully matching the Sketchfab reference (sloped '소 화 기 / FIRE EXTINGUISHER' stand with gray inner rim & back inset,
    glossy red domed tank, chartreuse '3.3kg KJ' wrap-around label, yellow hose strap clip, silver valve + pressure gauge +
    white safety ring pin, dual weathered black squeeze levers, arched black rubber hose + silver ferrule + yellow flared nozzle)."""
    red_tank_m = W.mat("KExt_RedTank", (0.76, 0.032, 0.035), rough=0.22, metal=0.18)
    red_stand_m = W.mat("KExt_RedStand", (0.72, 0.038, 0.042), rough=0.36, metal=0.05)
    gray_inset_m = W.mat("KExt_GrayInset", (0.72, 0.73, 0.72), rough=0.48, metal=0.05)
    yellow_m = W.mat("KExt_YellowClip", (0.88, 0.76, 0.04), rough=0.35, metal=0.05)
    silver_m = W.mat("KExt_SilverValve", (0.70, 0.72, 0.74), rough=0.25, metal=0.88)
    lever_m = W.mat("KExt_BlackLever", (0.045, 0.048, 0.052), rough=0.42, metal=0.65)
    hose_m = W.mat("KExt_BlackHose", (0.028, 0.030, 0.034), rough=0.72, metal=0.02)
    pin_m = W.mat("KExt_WhitePin", (0.88, 0.89, 0.90), rough=0.32, metal=0.35)
    dial_m = W.mat("KExt_GaugeDial", (0.90, 0.92, 0.90), rough=0.25, metal=0.0)

    # 1) Sloped red pedestal stand (front face -Y slopes inward from bottom y=-0.125 to top y=-0.085, height 0.118)
    stand_bm = bmesh.new()
    v0 = stand_bm.verts.new((-0.105, -0.128, 0.0))
    v1 = stand_bm.verts.new(( 0.105, -0.128, 0.0))
    v2 = stand_bm.verts.new(( 0.105,  0.105, 0.0))
    v3 = stand_bm.verts.new((-0.105,  0.105, 0.0))
    v4 = stand_bm.verts.new((-0.105, -0.086, 0.118))
    v5 = stand_bm.verts.new(( 0.105, -0.086, 0.118))
    v6 = stand_bm.verts.new(( 0.105,  0.105, 0.118))
    v7 = stand_bm.verts.new((-0.105,  0.105, 0.118))
    for quad in ((v0, v3, v2, v1), (v4, v5, v6, v7), (v0, v1, v5, v4), (v1, v2, v6, v5), (v2, v3, v7, v6), (v3, v0, v4, v7)):
        stand_bm.faces.new(quad)
    stand_me = bpy.data.meshes.new("KExt_Stand")
    stand_bm.to_mesh(stand_me); stand_bm.free()
    stand_ob = bpy.data.objects.new("KExt_Stand", stand_me)
    stand_ob.data.materials.append(red_stand_m)
    stand_ob.parent = root
    c.objects.link(stand_ob)
    bv = stand_ob.modifiers.new("Bevel", "BEVEL")
    bv.width = 0.004; bv.segments = 2

    # Sloped front graphic ('소 화 기 / FIRE EXTINGUISHER')
    slope_ang = math.atan2(0.042, 0.118)
    _textured_plane(c, root, "KExt_StandFront", "korean_ext_stand_front.png", 0.194, 0.114,
                    (0, -0.1095, 0.059), rot=(-slope_ang, 0, 0), shaded=True)
    # Top circular light-gray inner cradle rim + back vertical gray inset panel
    W.cyl("KExt_StandRim", 0.077, 0.006, gray_inset_m, c, (0, 0.008, 0.119), parent=root, seg=28)
    W.box("KExt_StandBackInset", (0.178, 0.006, 0.094), gray_inset_m, c, (0, 0.106, 0.059), parent=root)

    # 2) Glossy red tank cylinder + smooth domed shoulder (lathe/stack profile)
    r_tank = 0.068
    z_base = 0.118
    W.cyl("KExt_TankBody", r_tank, 0.305, red_tank_m, c, (0, 0.008, z_base + 0.1525), parent=root, seg=32)
    # Smooth hemispherical dome shoulder (z = 0.423 .. 0.483)
    dome_bm = bmesh.new()
    bmesh.ops.create_uvsphere(dome_bm, u_segments=32, v_segments=16, radius=r_tank)
    for v in list(dome_bm.verts):
        if v.co.z < -0.002:
            dome_bm.verts.remove(v)
        else:
            v.co.z *= 0.88
    dome_me = bpy.data.meshes.new("KExt_TankDome")
    dome_bm.to_mesh(dome_me); dome_bm.free()
    dome_ob = bpy.data.objects.new("KExt_TankDome", dome_me)
    dome_ob.data.materials.append(red_tank_m)
    dome_ob.location = (0, 0.008, z_base + 0.305)
    dome_ob.parent = root
    c.objects.link(dome_ob)
    for p in dome_me.polygons:
        p.use_smooth = True

    # 3) Wrap-around chartreuse '3.3kg KJ' label (open cylinder covering front/sides, z = 0.295 .. 0.415)
    lab_path = os.path.join(W.PARTS, "korean_ext_label.png")
    lab_im = bpy.data.images.load(lab_path, check_existing=True)
    if not lab_im.packed_file:
        lab_im.pack()
    lab_m = bpy.data.materials.new("KExt_LabelMat")
    lab_m.use_nodes = True
    ln, ll = lab_m.node_tree.nodes, lab_m.node_tree.links
    lbsdf = next(n for n in ln if n.type == "BSDF_PRINCIPLED")
    lbsdf.inputs["Roughness"].default_value = 0.34
    ltex = ln.new("ShaderNodeTexImage")
    ltex.image = lab_im
    ll.new(ltex.outputs["Color"], lbsdf.inputs["Base Color"])

    lab_bm = bmesh.new()
    segs = 28
    r_lab = r_tank + 0.0012
    z0, z1 = 0.298, 0.414
    uv_layer = lab_bm.loops.layers.uv.new()
    # Arc spanning -135 deg to +135 deg centered on -Y (front)
    verts_b, verts_t = [], []
    for i in range(segs + 1):
        u = i / segs
        ang = math.radians(-130 + 260 * u) - math.pi / 2
        x, y = math.cos(ang) * r_lab, 0.008 + math.sin(ang) * r_lab
        verts_b.append(lab_bm.verts.new((x, y, z0)))
        verts_t.append(lab_bm.verts.new((x, y, z1)))
    for i in range(segs):
        f = lab_bm.faces.new((verts_b[i], verts_b[i + 1], verts_t[i + 1], verts_t[i]))
        u0, u1 = i / segs, (i + 1) / segs
        for loop, uv_co in zip(f.loops, ((u0, 0), (u1, 0), (u1, 1), (u0, 1))):
            loop[uv_layer].uv = uv_co
    lab_me = bpy.data.meshes.new("KExt_Label")
    lab_bm.to_mesh(lab_me); lab_bm.free()
    for p in lab_me.polygons:
        p.use_smooth = True
    lab_ob = bpy.data.objects.new("KExt_Label", lab_me)
    lab_ob.data.materials.append(lab_m)
    lab_ob.parent = root
    c.objects.link(lab_ob)

    # 4) Bright yellow retaining strap ring + side hose clip loop (viewer's left: -X)
    W.cyl("KExt_YellowStrap", r_tank + 0.0038, 0.018, yellow_m, c, (0, 0.008, 0.232), parent=root, seg=32)
    _molded("KExt_HoseClip", (0.028, 0.022, 0.019), yellow_m, c, (-r_tank - 0.015, 0.008, 0.232), root, 0.004)

    # 5) Silver neck collar, valve block, front pressure gauge, dual black squeeze levers, white safety pull-ring
    W.cyl("KExt_Neck", 0.024, 0.028, silver_m, c, (0, 0.008, 0.492), parent=root, seg=20)
    W.cyl("KExt_ValveBody", 0.019, 0.044, silver_m, c, (0, 0.008, 0.524), parent=root, seg=20)
    # Front pressure gauge on -Y face of valve
    W.cyl("KExt_GaugeBezel", 0.015, 0.014, silver_m, c, (0, -0.014, 0.526), (90, 0, 0), parent=root, seg=20)
    W.cyl("KExt_GaugeDial", 0.012, 0.003, dial_m, c, (0, -0.021, 0.526), (90, 0, 0), parent=root, seg=20)
    # Dual black metal handles extending to +X (lower fixed handle + upper arched squeeze lever)
    _molded("KExt_LowerHandle", (0.115, 0.022, 0.010), lever_m, c, (0.056, 0.008, 0.532), root, 0.003)
    upper_lv = _molded("KExt_UpperLever", (0.125, 0.024, 0.011), lever_m, c, (0.058, 0.008, 0.562), root, 0.003)
    upper_lv.rotation_euler.y = math.radians(-16)
    # White/silver circular safety pin pull ring on back-right side of valve
    ring_c = bpy.data.curves.new("KExt_SafetyRing", "CURVE")
    ring_c.dimensions = "3D"
    ring_c.bevel_depth = 0.0024
    ring_c.bevel_resolution = 4
    sp = ring_c.splines.new("POLY")
    pts_r = [(math.cos(a) * 0.015, math.sin(a) * 0.015, 0) for a in [i * math.tau / 16 for i in range(16)]]
    sp.points.add(len(pts_r) - 1)
    for pt, co in zip(sp.points, pts_r):
        pt.co = (*co, 1.0)
    sp.use_cyclic_u = True
    ring_c.materials.append(pin_m)
    ring_ob = bpy.data.objects.new("KExt_SafetyRing", ring_c)
    ring_ob.location = (0.024, 0.028, 0.538)
    ring_ob.rotation_euler = (math.radians(25), 0, 0)
    ring_ob.parent = root
    c.objects.link(ring_ob)

    # 6) Arched black rubber hose + silver ferrule + bright yellow flared conical nozzle (on -X side)
    hose_c = bpy.data.curves.new("KExt_Hose", "CURVE")
    hose_c.dimensions = "3D"
    hose_c.resolution_u = 16
    hose_c.bevel_depth = 0.0095
    hose_c.bevel_resolution = 6
    hsp = hose_c.splines.new("NURBS")
    hose_pts = [
        (-0.016, 0.008, 0.526),
        (-0.068, 0.008, 0.530),
        (-0.122, 0.004, 0.455),
        (-0.118, 0.002, 0.335),
        (-0.088, 0.006, 0.232),  # passes through yellow retaining clip
        (-0.106, -0.002, 0.165),
    ]
    hsp.points.add(len(hose_pts) - 1)
    for pt, co in zip(hsp.points, hose_pts):
        pt.co = (*co, 1.0)
    hsp.use_endpoint_u = True
    hose_c.materials.append(hose_m)
    hose_ob = bpy.data.objects.new("KExt_Hose", hose_c)
    hose_ob.parent = root
    c.objects.link(hose_ob)

    # Silver ferrule + bright yellow flared conical nozzle at hose tip
    ferrule = W.cyl("KExt_NozzleFerrule", 0.0115, 0.018, silver_m, c, (-0.111, -0.004, 0.156), (0, 22, 0), parent=root, seg=18)
    noz_bm = bmesh.new()
    bmesh.ops.create_cone(noz_bm, cap_ends=True, cap_tris=False, segments=22, radius1=0.019, radius2=0.011, depth=0.058)
    noz_me = bpy.data.meshes.new("KExt_YellowNozzle")
    noz_bm.to_mesh(noz_me); noz_bm.free()
    for p in noz_me.polygons:
        p.use_smooth = True
    noz_ob = bpy.data.objects.new("KExt_YellowNozzle", noz_me)
    noz_ob.data.materials.append(yellow_m)
    noz_ob.location = (-0.125, -0.008, 0.122)
    noz_ob.rotation_euler = (0, math.radians(24), 0)
    noz_ob.parent = root
    c.objects.link(noz_ob)


def build_room_door(c, loc, rot_deg, name_tag, label, sublabel, accent_color, handle_side=1):
    """Sleek modern Korean gym interior door (0.95 x 2.18 m) with frame, lever handle, kickplate, and overhead room plaque."""
    root = W.empty(f"Door_{name_tag}", c, loc)
    root.rotation_euler.z = math.radians(rot_deg)

    frame_m = W.mat("RoomDoorFrame_Charcoal", (0.022, 0.024, 0.028), rough=0.40, metal=0.55)
    leaf_m = W.mat("RoomDoorLeaf_Matte", (0.042, 0.045, 0.052), rough=0.52, metal=0.12)
    trim_m = W.mat(f"RoomDoorAccent_{name_tag}", accent_color, rough=0.35, metal=0.25)
    chrome_m = W.mat("DoorSteel_Brushed", (0.64, 0.66, 0.68), rough=0.22, metal=0.92)
    plaque_bg = W.mat("RoomPlaque_BG", (0.018, 0.020, 0.024), rough=0.36, metal=0.40)
    txt_glow = W.shadeless(f"RoomPlaque_Text_{name_tag}", (0.94, 0.96, 0.98), strength=1.55)
    acc_glow = W.shadeless(f"RoomPlaque_Acc_{name_tag}", accent_color, strength=2.2)

    w, h = 0.95, 2.18
    # Steel door frame
    for side in (-1, 1):
        _molded("Room door jamb", (0.058, 0.24, h), frame_m, c, (side * (w / 2 - 0.029), 0, h / 2), root, 0.004)
    _molded("Room door header", (w, 0.24, 0.062), frame_m, c, (0, 0, h - 0.031), root, 0.004)

    # Flush modern door leaf with subtle vertical accent groove & stainless kickplate
    lw, lh = w - 0.12, h - 0.07
    _molded("Room door leaf", (lw, 0.046, lh), leaf_m, c, (0, 0.01, lh / 2 + 0.008), root, 0.004)
    _molded("Room door kickplate", (lw - 0.03, 0.006, 0.18), chrome_m, c, (0, -0.015, 0.10), root, 0.002)
    _molded("Room door accent bar", (0.016, 0.006, lh - 0.36), trim_m, c, (-handle_side * (lw / 2 - 0.09), -0.015, lh / 2 + 0.05), root, 0.002)

    # Lever handle (both sides)
    hx = handle_side * (lw / 2 - 0.085)
    for y_dir in (-1, 1):
        W.cyl("Door rosette", 0.026, 0.010, chrome_m, c, (hx, 0.01 + y_dir * 0.028, 1.02), (90, 0, 0), parent=root, seg=18)
        W.cyl("Door stem", 0.010, 0.042, chrome_m, c, (hx, 0.01 + y_dir * 0.046, 1.02), (90, 0, 0), parent=root, seg=12)
        _molded("Door lever", (0.125, 0.016, 0.020), chrome_m, c, (hx - handle_side * 0.052, 0.01 + y_dir * 0.064, 1.02), root, 0.005)

    # Overhead room sign plaque (facing -Y into the gym)
    _molded("Room plaque", (0.56, 0.024, 0.16), plaque_bg, c, (0, -0.115, h + 0.16), root, 0.005)
    _molded("Room plaque strip", (0.52, 0.006, 0.014), acc_glow, c, (0, -0.128, h + 0.224), root, 0.002)
    _text(c, root, f"Label_{name_tag}", label, (0, -0.130, h + 0.172), 0.056, txt_glow)
    if sublabel:
        _text(c, root, f"Sublabel_{name_tag}", sublabel, (0, -0.130, h + 0.116), 0.036, txt_glow)

    return root


def _walnut_wood_mat(name, value_mult=1.0, sat_mult=1.0, scale=(0.75, 0.75, 0.75), rot_y=0.0, rough=0.78, spec=0.16, bump_str=0.04):
    """PBR architectural matte wood material driven by compressed seamless walnut_wood.jpg with Box projection & subtle grain bump."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    n, l = nt.nodes, nt.links
    bsdf = next(nd for nd in n if nd.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = spec
    coord = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Rotation"].default_value = (0.0, rot_y, 0.0)
    l.new(coord.outputs["Object"], mp.inputs["Vector"])
    tex = n.new("ShaderNodeTexImage")
    tex.projection = "BOX"
    tex.projection_blend = 0.20
    img_path = os.path.join(W.PARTS, "gym_wall_opt", "walnut_wood.jpg")
    im = bpy.data.images.load(img_path, check_existing=True)
    if not im.packed_file:
        im.pack()
    tex.image = im
    l.new(mp.outputs["Vector"], tex.inputs["Vector"])
    hsv = n.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = sat_mult
    hsv.inputs["Value"].default_value = value_mult
    l.new(tex.outputs["Color"], hsv.inputs["Color"])
    l.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])
    # Subtle grain bump + roughness breakup
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = bump_str
    bump.inputs["Distance"].default_value = 0.002
    l.new(tex.outputs["Color"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def build_info_desk(c):
    """Exact replica of the Korean premium gym reception/info desk reference:
    - Real walnut wood grain 2-tier counter & vertical wood louver partition
    - Crisp 3D extruded channel sign 'WATCH [W] COACH' directly on bodybuilder mural wall
    - Frosted glass desk dividers, dual monitors, acrylic promo stand, 2 sleek white consultation chairs
    - 3 slim brass cylinder pendant lights + warm beige epoxy reception floor pad."""
    root = W.empty("Gym_InfoDesk", c, (-5.45, -6.02, 0))

    # Materials: soft matte natural architectural wood (brighter, less saturated, low sheen!)
    wood_m = _walnut_wood_mat("InfoRef_WarmWood", value_mult=1.52, sat_mult=0.72, scale=(0.85, 0.85, 0.85), rough=0.78, spec=0.15, bump_str=0.04)
    louver_m = _walnut_wood_mat("InfoRef_WoodLouver", value_mult=1.58, sat_mult=0.68, scale=(1.1, 1.1, 0.7), rough=0.80, spec=0.14, bump_str=0.03)
    charcoal = W.mat("InfoRef_Charcoal", (0.025, 0.027, 0.032), rough=0.38, metal=0.35)
    white_chair = W.mat("InfoRef_WhiteChair", (0.86, 0.87, 0.85), rough=0.35, metal=0.05)
    brass_m = W.mat("InfoRef_BrassPendant", (0.76, 0.62, 0.28), rough=0.24, metal=0.92)
    epoxy_m = W.mat("InfoRef_BeigeEpoxy", (0.52, 0.44, 0.30), rough=0.20, metal=0.04)
    # Controlled crisp architectural LED channel letters (no blown-out fog!)
    led_white = W.shadeless("InfoRef_SignWhite", (0.94, 0.97, 1.0), strength=2.1)
    led_gold = W.shadeless("InfoRef_SignGold", (0.96, 0.74, 0.02), strength=2.4)
    pend_glow = W.shadeless("InfoRef_PendantGlow", (1.0, 0.92, 0.72), strength=4.5)
    screen_m = W.shadeless("InfoRef_MonitorScr", (0.14, 0.50, 0.86), strength=1.4)
    pop_m = W.shadeless("InfoRef_PromoCard", (0.94, 0.80, 0.22), strength=1.1)

    # Frosted acrylic desk divider glass
    frost_m = bpy.data.materials.new("InfoRef_FrostedGlass")
    frost_m.use_nodes = True
    try:
        frost_m.surface_render_method = "BLENDED"
    except AttributeError:
        pass
    fnt = frost_m.node_tree
    fnt.nodes.clear()
    fout = fnt.nodes.new("ShaderNodeOutputMaterial")
    fmix = fnt.nodes.new("ShaderNodeMixShader")
    fmix.inputs["Fac"].default_value = 0.56
    ftrans = fnt.nodes.new("ShaderNodeBsdfTransparent")
    ftrans.inputs["Color"].default_value = (0.86, 0.92, 0.94, 1)
    fdiff = fnt.nodes.new("ShaderNodeBsdfPrincipled")
    fdiff.inputs["Base Color"].default_value = (0.76, 0.84, 0.86, 1)
    fdiff.inputs["Roughness"].default_value = 0.45
    fnt.links.new(ftrans.outputs["BSDF"], fmix.inputs[1])
    fnt.links.new(fdiff.outputs["BSDF"], fmix.inputs[2])
    fnt.links.new(fmix.outputs["Shader"], fout.inputs["Surface"])

    # 1) Warm beige glossy epoxy reception floor pad (cleanly delineates info zone from dark rubber floor)
    _molded("InfoDesk epoxy pad", (3.65, 2.55, 0.012), epoxy_m, c, (0.05, 0.55, 0.006), root, 0.004)

    # 2) Real 3D extruded bold architectural channel sign directly on the bodybuilder mural wall: 'WATCH [W] COACH'
    wall_y = -0.64
    bold_font = bpy.data.fonts.load("C:/Windows/Fonts/arialbd.ttf", check_existing=True) if os.path.exists("C:/Windows/Fonts/arialbd.ttf") else W.load_font(W.KFONT)
    for tag, word, lx in (("WATCH", "WATCH", 0.70), ("COACH", "COACH", -0.70)):
        # Dark aluminum channel backing + crisp satin-white extruded front letter (no blown-out wall fog!)
        for depth_off, mat_use, ext, nm_suf in ((0.012, charcoal, 0.016, "Back"), (0.029, led_white, 0.004, "Face")):
            fdata = bpy.data.curves.new(f"InfoLogo_{tag}_{nm_suf}", "FONT")
            fdata.body = word
            fdata.font = bold_font
            fdata.size = 0.25
            fdata.space_character = 1.06
            fdata.align_x = "CENTER"
            fdata.align_y = "CENTER"
            fdata.extrude = ext
            fdata.bevel_depth = 0.002
            fdata.materials.append(mat_use)
            fob = bpy.data.objects.new(fdata.name, fdata)
            fob.location = (lx, wall_y + depth_off, 2.26)
            fob.rotation_euler = (math.pi / 2, 0, math.pi)
            fob.parent = root
            c.objects.link(fob)
    # Sculpted 3D gold shield/watch emblem in the center (dark metal sides + crisp rich gold front!)
    _molded("InfoLogo_BadgeSide", (0.24, 0.026, 0.27), charcoal, c, (0.0, wall_y + 0.014, 2.26), root, 0.010)
    _molded("InfoLogo_BadgeFace", (0.22, 0.008, 0.25), led_gold, c, (0.0, wall_y + 0.028, 2.26), root, 0.008)
    _molded("InfoLogo_BadgeCut", (0.145, 0.010, 0.175), charcoal, c, (0.0, wall_y + 0.030, 2.26), root, 0.005)
    w_data = bpy.data.curves.new("InfoLogo_W", "FONT")
    w_data.body = "W"
    w_data.font = bold_font
    w_data.size = 0.13
    w_data.align_x = "CENTER"
    w_data.align_y = "CENTER"
    w_data.extrude = 0.004
    w_data.materials.append(led_gold)
    w_ob = bpy.data.objects.new("InfoLogo_W", w_data)
    w_ob.location = (0.0, wall_y + 0.036, 2.255)
    w_ob.rotation_euler = (math.pi / 2, 0, math.pi)
    w_ob.parent = root
    c.objects.link(w_ob)

    # 4) Vertical warm-wood louver/slat partition screen on the right side (separating reception from gym machines!)
    louv_x = 1.84
    _molded("Louver top rail", (0.06, 1.88, 0.06), louver_m, c, (louv_x, 0.26, 2.86), root, 0.004)
    _molded("Louver bottom rail", (0.06, 1.88, 0.06), louver_m, c, (louv_x, 0.26, 0.03), root, 0.004)
    for i in range(9):
        ly = -0.58 + i * 0.21
        _molded("Louver vertical slat", (0.045, 0.055, 2.82), louver_m, c, (louv_x, ly, 1.44), root, 0.004)

    # 5) 2-Tier Step-Down Warm Walnut Wood Counter Desk (exact shape from reference!)
    # Left higher check-in block: x = -1.62 .. -0.56 (width 1.06m, height 1.04m, depth 0.68m)
    _molded("Desk high body", (1.06, 0.64, 1.00), wood_m, c, (-1.09, 0.42, 0.50), root, 0.008)
    _molded("Desk high top", (1.10, 0.70, 0.042), wood_m, c, (-1.09, 0.42, 1.02), root, 0.006)
    # Right lower consultation desk: x = -0.56 .. +1.46 (width 2.02m, height 0.76m, depth 0.68m, knee space underneath)
    _molded("Desk low top", (2.04, 0.70, 0.048), wood_m, c, (0.45, 0.42, 0.74), root, 0.006)
    _molded("Desk low modesty", (2.00, 0.05, 0.68), wood_m, c, (0.45, 0.14, 0.36), root, 0.005)
    _molded("Desk low right leg", (0.06, 0.66, 0.72), wood_m, c, (1.44, 0.42, 0.36), root, 0.005)

    # 6) Two Frosted Glass Privacy Dividers on the lower consultation desk (exact reference!)
    for dx in (0.18, 0.88):
        _molded("Frosted divider", (0.012, 0.62, 0.44), frost_m, c, (dx, 0.42, 0.98), root, 0.003)

    # 7) Desk Props: Check-in Monitor + Promo POP stand (high left), Consultation Monitor + File Box (low right)
    for m_name, mx, mz, rot_z in (("Checkin_Mon", -1.26, 1.04, -18), ("Consult_Mon", -0.18, 0.765, 10)):
        mon = W.empty(m_name, c, (mx, 0.36, mz), parent=root)
        mon.rotation_euler.z = math.radians(rot_z)
        _molded("Mon foot", (0.18, 0.14, 0.012), charcoal, c, (0, 0, 0.006), mon, 0.003)
        _molded("Mon neck", (0.036, 0.028, 0.16), charcoal, c, (0, 0.02, 0.09), mon, 0.003)
        _molded("Mon bezel", (0.46, 0.024, 0.28), charcoal, c, (0, 0.01, 0.24), mon, 0.004)
        W.box("Mon screen", (0.43, 0.004, 0.25), screen_m, c, (0, -0.004, 0.24), parent=mon)
    # Acrylic promo POP stand on high counter
    _molded("Promo POP stand", (0.16, 0.018, 0.24), pop_m, c, (-0.82, 0.56, 1.16), root, 0.003)
    # White file organizer box on consultation desk
    _molded("Desk file box", (0.12, 0.24, 0.28), white_chair, c, (0.56, 0.42, 0.905), root, 0.004)
    # Toss Front 2 customer payment terminal on the high check-in counter, screen turned toward the customer (+Y)
    build_toss_front(c, root, (-1.00, 0.66, 1.041), rot_z_deg=172.0, name="TossFront")

    # 8) Two Sleek White Modern Consultation Chairs in front (+Y) of the lower desk!
    for cx, cz_rot in ((0.44, -14), (1.06, -22)):
        ch = W.empty(f"Consult_Chair_{cx:.1f}", c, (cx, 0.98, 0), parent=root)
        ch.rotation_euler.z = math.radians(cz_rot)
        for lx in (-0.17, 0.17):
            for ly in (-0.16, 0.16):
                leg = W.cyl("Chair leg", 0.013, 0.45, white_chair, c, (lx, ly, 0.22), parent=ch, seg=10)
                leg.rotation_euler.x = math.radians(6 if ly > 0 else -6)
                leg.rotation_euler.y = math.radians(-5 if lx > 0 else 5)
        _molded("Chair seat", (0.42, 0.40, 0.042), white_chair, c, (0, 0, 0.44), ch, 0.014)
        back = _molded("Chair back", (0.40, 0.036, 0.40), white_chair, c, (0, 0.19, 0.64), ch, 0.014)
        back.rotation_euler.x = math.radians(8)

    # 9) 3 Slim Brass Cylinder Pendant Lights hanging from ceiling over the info desk!
    for px in (-0.85, 0.05, 0.95):
        W.cyl("Pendant cord", 0.004, 0.85, charcoal, c, (px, 0.42, 3.16), parent=root, seg=8)
        W.cyl("Pendant brass tube", 0.016, 0.36, brass_m, c, (px, 0.42, 2.58), parent=root, seg=16)
        W.cyl("Pendant tip glow", 0.014, 0.012, pend_glow, c, (px, 0.42, 2.398), parent=root, seg=14)


def build_stretching_zone(c):
    """Spacious dedicated stretching & warm-up zone along the expanded left entry wall (x = -7.45..-4.85, y = -2.2..+2.2):
    floor zone border, 3 cushioned mats, wall-mounted stretching mirror, foam rollers, stability balls, and plyo box."""
    root = W.empty("Gym_StretchingZone", c, (-6.15, -0.20, 0))

    zone_m = W.mat("Stretch_TurfBase", (0.024, 0.032, 0.028), rough=0.86, metal=0.0)
    trim_m = W.mat("Stretch_Trim", (0.020, 0.022, 0.026), rough=0.45, metal=0.40)
    mat_cols = [
        W.mat("StretchMat_Sage", (0.05, 0.34, 0.22), rough=0.72, metal=0.0),
        W.mat("StretchMat_Navy", (0.06, 0.14, 0.30), rough=0.72, metal=0.0),
        W.mat("StretchMat_Charcoal", (0.08, 0.09, 0.11), rough=0.72, metal=0.0),
    ]
    roller_m = W.mat("Stretch_FoamRoller", (0.035, 0.038, 0.042), rough=0.68, metal=0.0)
    ball1_m = W.mat("Stretch_GymBall1", (0.08, 0.38, 0.42), rough=0.38, metal=0.05)
    ball2_m = W.mat("Stretch_GymBall2", (0.14, 0.15, 0.17), rough=0.38, metal=0.05)
    plyo_m = _walnut_wood_mat("Stretch_PlyoWood", value_mult=1.28, sat_mult=0.84, scale=(1.2, 1.2, 1.2), rough=0.52, bump_str=0.06)
    mirror_m = W.mat("Gym_Mirror", (0.78, 0.80, 0.84), rough=0.0, metal=1.0)

    # Low cushioned stretching zone flooring pad (2.30 x 4.20 m)
    _molded("Stretching zone mat base", (2.30, 4.20, 0.014), zone_m, c, (0, 0, 0.007), root, 0.004)

    # 3 neatly laid exercise mats side-by-side along the stretching zone
    for i, (my, mm) in enumerate(zip((-1.15, 0.0, 1.15), mat_cols)):
        _molded(f"Stretch mat {i+1}", (1.72, 0.68, 0.022), mm, c, (0.08, my, 0.025), root, 0.008)

    # Full-length framed stretching mirror mounted on the expanded left wall (x_local = -1.32 -> world x = -7.47)
    _molded("Stretch mirror frame", (0.04, 2.48, 2.08), trim_m, c, (-1.32, 0.0, 1.38), root, 0.005)
    W.box("Stretch mirror glass", (0.012, 2.40, 2.00), mirror_m, c, (-1.298, 0.0, 1.38), parent=root)

    # Compact foam roller holder + 3 standing foam rollers at the back edge of the stretching zone
    _molded("Roller rack base", (0.34, 0.88, 0.04), trim_m, c, (-1.04, 1.82, 0.02), root, 0.005)
    for ry in (1.55, 1.82, 2.09):
        W.cyl("Stretch foam roller", 0.072, 0.66, roller_m, c, (-1.04, ry, 0.36), parent=root, seg=18)

    # 2 stability gym balls (짐볼) tucked neatly in the far-left stretching corner
    for name, loc, r, bm_mat in (
        ("GymBall_Large", (-0.82, 2.68, 0.32), 0.32, ball1_m),
        ("GymBall_Medium", (-0.18, 2.78, 0.27), 0.27, ball2_m),
    ):
        s_bm = bmesh.new()
        bmesh.ops.create_uvsphere(s_bm, u_segments=24, v_segments=16, radius=r)
        s_me = bpy.data.meshes.new(name)
        s_bm.to_mesh(s_me); s_bm.free()
        for p in s_me.polygons:
            p.use_smooth = True
        s_ob = bpy.data.objects.new(name, s_me)
        s_ob.data.materials.append(bm_mat)
        s_ob.location = loc
        s_ob.parent = root
        c.objects.link(s_ob)

    # 3-in-1 wooden plyometric box beside the stretching mats
    _molded("Plyo box", (0.50, 0.60, 0.40), plyo_m, c, (0.58, 2.55, 0.20), root, 0.010)


def build_gym_doors(parent):
    """Plan B Phase 1 + Left Entry Wing: 4 real doors + wall openings, Info Desk, Stretching Zone, and connected Annex Rooms."""
    c = W.coll("Gym Doors", parent)
    cutters = W.coll("Gym Door Cutters", parent)

    # 1) Main Entrance on expanded Wall_Left (x = -7.55) + Korean EXIT sign & Sangga Hallway outside
    cut_wall_opening(("Wall_Left", "Wainscot_Left"), (-7.58, -5.55, 1.125), (0.60, 1.60, 2.25), cutters)
    build_entrance_door(c, (-7.55, -5.55, 0), rot_deg=90)

    # Info Desk beside entrance + dedicated Stretching Zone along the expanded left entry wall
    build_info_desk(c)
    build_stretching_zone(c)

    # 2) Posing Room on Wall_Front (front-left, clear of posters & stretching corner)
    cut_wall_opening(("Wall_Front", "Wainscot_Front", "Locker wall mural"), (-1.45, -6.75, 1.09), (0.91, 0.60, 2.18), cutters)
    build_room_door(c, (-1.45, -6.72, 0), rot_deg=180, name_tag="PosingRoom",
                    label="POSING ROOM", sublabel="포징룸", accent_color=(0.95, 0.72, 0.12), handle_side=1)

    # 3 & 4) Men's & Women's Locker Room doors side-by-side on Wall_Front right next to the public lockers (101-116)
    cut_wall_opening(("Wall_Front", "Wainscot_Front", "Locker wall mural"), (10.95, -6.75, 1.09), (0.91, 0.60, 2.18), cutters)
    build_room_door(c, (10.95, -6.72, 0), rot_deg=180, name_tag="MenLocker",
                    label="MEN", sublabel="남자 탈의실", accent_color=(0.18, 0.56, 0.96), handle_side=1)

    cut_wall_opening(("Wall_Front", "Wainscot_Front", "Locker wall mural"), (12.25, -6.75, 1.09), (0.91, 0.60, 2.18), cutters)
    build_room_door(c, (12.25, -6.72, 0), rot_deg=180, name_tag="WomenLocker",
                    label="WOMEN", sublabel="여자 탈의실", accent_color=(0.96, 0.32, 0.48), handle_side=-1)

    # Phase 2 & 3: Connected Annex Rooms (Posing Room + Men's & Women's Locker/Shower/Restroom Suites)
    import importlib
    import gym_posing_room
    import gym_locker_suites
    importlib.reload(gym_posing_room)
    importlib.reload(gym_locker_suites)
    gym_posing_room.build_posing_room(parent)
    gym_locker_suites.build_locker_suites(parent)

    return c
