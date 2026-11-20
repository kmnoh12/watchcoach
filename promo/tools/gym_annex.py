"""WatchCoach Gym Expansion: 4 real architectural doors (Main Entrance + Exit Sign, Posing Room, Men/Women Locker Suites)
and modular interior annex rooms (Posing Room, Men's & Women's Locker -> Shower -> Restroom suites)."""
import math
import os
import bmesh
import bpy
from mathutils import Vector
import wc_lib as W


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

    # Far corridor end walls (with distant exit glow)
    for side in (-1, 1):
        W.box("Hallway far end", (0.08, 2.9, 2.80), end_m, c, (side * 4.65, 1.50, 1.40), parent=hall)
        W.box("Hallway far exit dot", (0.02, 0.22, 0.16), W.shadeless("HallFarExit", (0.08, 0.88, 0.36), strength=3.2),
              c, (side * 4.59, 1.50, 2.38), parent=hall)

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

    # 3 real 3D projecting Korean Sangga lightbox signs sticking out from the opposite wall
    for s_name, img, x_pos, z_pos in (
        ("Sign_Math", "hallway_sign_math.png", -0.82, 2.38),
        ("Sign_Pilates", "hallway_sign_pilates.png", 0.72, 2.38),
        ("Sign_Art", "hallway_sign_art.png", 1.82, 2.38),
    ):
        s_root = W.empty(s_name, c, (x_pos, 2.48, z_pos), parent=hall)
        _molded(f"{s_name}_box", (0.08, 0.58, 0.26), frame_m, c, (0, 0, 0), s_root, 0.005)
        _molded(f"{s_name}_bracket", (0.04, 0.12, 0.20), frame_m, c, (0, 0.32, 0), s_root, 0.003)
        _textured_plane(c, s_root, f"{s_name}_faceL", img, 0.54, 0.22, (-0.044, 0, 0), rot=(0, 0, -math.pi / 2), strength=1.55)
        _textured_plane(c, s_root, f"{s_name}_faceR", img, 0.54, 0.22, (0.044, 0, 0), rot=(0, 0, math.pi / 2), strength=1.55)

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


def build_info_desk(c):
    """Exact replica of the Korean premium gym reception/info desk reference:
    - Gray veined marble paneled feature wall behind desk
    - Backlit glowing 3D channel sign 'WATCH [emblem] COACH' on the marble wall
    - Vertical warm-wood louver/slat partition screen on the right separating reception from gym floor
    - 2-tier warm walnut wood counter: higher left check-in counter (1.04m) + lower right consultation desk (0.76m)
    - Frosted glass desk dividers, dual monitors, acrylic promo stand, 2 sleek white shell consultation chairs
    - 3 slim brass cylinder pendant lights hanging over the desk + warm beige epoxy reception floor pad."""
    root = W.empty("Gym_InfoDesk", c, (-5.45, -6.02, 0))

    # Materials
    wood_m = W.mat("InfoRef_WarmWood", (0.42, 0.25, 0.14), rough=0.44, metal=0.04)
    louver_m = W.mat("InfoRef_WoodLouver", (0.48, 0.30, 0.17), rough=0.48, metal=0.03)
    charcoal = W.mat("InfoRef_Charcoal", (0.03, 0.032, 0.036), rough=0.40, metal=0.25)
    white_chair = W.mat("InfoRef_WhiteChair", (0.86, 0.87, 0.85), rough=0.35, metal=0.05)
    brass_m = W.mat("InfoRef_BrassPendant", (0.76, 0.62, 0.28), rough=0.24, metal=0.92)
    epoxy_m = W.mat("InfoRef_BeigeEpoxy", (0.56, 0.48, 0.34), rough=0.20, metal=0.04)
    led_white = W.shadeless("InfoRef_SignWhite", (0.96, 0.99, 1.0), strength=5.5)
    led_gold = W.shadeless("InfoRef_SignGold", (1.0, 0.82, 0.08), strength=5.8)
    pend_glow = W.shadeless("InfoRef_PendantGlow", (1.0, 0.92, 0.72), strength=6.0)
    screen_m = W.shadeless("InfoRef_MonitorScr", (0.14, 0.50, 0.86), strength=1.4)
    pop_m = W.shadeless("InfoRef_PromoCard", (0.94, 0.80, 0.22), strength=1.1)

    # Gray veined marble tile feature wall material
    marble_m = bpy.data.materials.new("InfoRef_GrayMarble")
    marble_m.use_nodes = True
    mn, ml = marble_m.node_tree.nodes, marble_m.node_tree.links
    mbsdf = next(n for n in mn if n.type == "BSDF_PRINCIPLED")
    mbsdf.inputs["Roughness"].default_value = 0.28
    mbsdf.inputs["Specular IOR Level"].default_value = 0.52
    mgeo = mn.new("ShaderNodeNewGeometry")
    mnoise = mn.new("ShaderNodeTexNoise")
    mnoise.inputs["Scale"].default_value = 2.6
    mnoise.inputs["Detail"].default_value = 6.0
    mnoise.inputs["Distortion"].default_value = 1.8
    ml.new(mgeo.outputs["Position"], mnoise.inputs["Vector"])
    mramp = mn.new("ShaderNodeValToRGB")
    e0, e1 = mramp.color_ramp.elements
    e0.position, e0.color = 0.36, (0.13, 0.14, 0.155, 1)
    e1.position, e1.color = 0.66, (0.28, 0.295, 0.315, 1)
    ml.new(mnoise.outputs["Fac"], mramp.inputs["Fac"])
    ml.new(mramp.outputs["Color"], mbsdf.inputs["Base Color"])

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

    # 2) Gray marble paneled feature wall mounted flush against Wall_Front (y_local = -0.64 -> world y = -6.66)
    wall_y = -0.62
    for px in (-1.35, -0.45, 0.45, 1.35):
        _molded("Marble wall panel", (0.885, 0.032, 3.05), marble_m, c, (px, wall_y, 1.525), root, 0.003)

    # 3) Backlit 3D glowing channel sign on the marble wall: 'WATCH  [W]  COACH' (facing +Y, so +X is viewer-left!)
    _text(c, root, "InfoLogo_WATCH", "WATCH", ( 0.64, wall_y + 0.036, 2.26), 0.24, led_white, rot=(math.pi / 2, 0, math.pi))
    _text(c, root, "InfoLogo_COACH", "COACH", (-0.64, wall_y + 0.036, 2.26), 0.24, led_white, rot=(math.pi / 2, 0, math.pi))
    # Center glowing gold shield/watch emblem (matching the yellow 'U' badge in the reference!)
    _molded("InfoLogo_BadgeBg", (0.24, 0.030, 0.27), led_gold, c, (0.0, wall_y + 0.030, 2.26), root, 0.012)
    _molded("InfoLogo_BadgeInner", (0.16, 0.034, 0.19), charcoal, c, (0.0, wall_y + 0.032, 2.26), root, 0.008)
    _text(c, root, "InfoLogo_W", "W", (0.0, wall_y + 0.052, 2.255), 0.135, led_gold, rot=(math.pi / 2, 0, math.pi))
    # Subtle soft white halo backlight behind the logo onto the marble wall
    logo_ld = bpy.data.lights.new("InfoLogoHalo", "AREA")
    logo_ld.shape = "RECTANGLE"
    logo_ld.size, logo_ld.size_y = 1.9, 0.24
    logo_ld.energy = 11
    logo_ld.color = (0.94, 0.97, 1.0)
    logo_ld.use_shadow = False
    logo_lo = bpy.data.objects.new(logo_ld.name, logo_ld)
    logo_lo.location = (0.0, wall_y + 0.10, 2.26)
    logo_lo.rotation_euler.x = -math.pi / 2
    logo_lo.parent = root
    c.objects.link(logo_lo)

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
    plyo_m = W.mat("Stretch_PlyoWood", (0.46, 0.30, 0.15), rough=0.58, metal=0.0)
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
