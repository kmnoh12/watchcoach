"""WatchCoach promo-account Blender kit (Blender 5.2, headless-friendly).

Everything a reel needs, built from code so an agent only picks "scene frame + poses + one line":
  new_scene(kind)            flat (one-colour cyclorama) or gym (rough low-poly gym interior); fixed lights + 3 cameras
  add_hero / add_extra       V5 guy (faceless, with the watch) / old low-poly man recoloured by role
  apply_pose / key_pose      poses from poses/pose_library.json (shared by hero and extras: same 52 bones, same rest)
  add_cameo + cameo_move     photo / logo boards (samsung, altman, amodei, gpt, claude) with peek / pass / approach
  fx_*                       comic symbols, speed lines, 1-2 frame flash, zoom punch, camera shake
  props                      plate, phone, towel, shaker, bottle, gym bag, wall clock
Units: metres, +Z up, characters face -Y (towards Cam_Front). Characters stand around the origin.
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, os.path.join(TOOLS, "vendor"))
PARTS = os.path.join(ROOT, "parts")
HERO_SRC = os.path.join(ROOT, "cast", "src_v5_with_watch_copy.blend")
EXTRA_SRC = os.path.join(ROOT, "cast", "src_figure_copy.blend")  # original low-poly man (figure.blend copy)
POSE_LIB = os.path.join(ROOT, "poses", "pose_library.json")
KFONT = os.path.join(PARTS, "fonts", "NanumGothic-Bold.ttf")

FPS = 30
HOLD = 6  # frames per pose = 5 poses per second

BG = {"yellow": (0.95, 0.78, 0.25), "mint": (0.38, 0.80, 0.66), "pink": (0.95, 0.55, 0.62),
      "blue": (0.42, 0.62, 0.92), "gray": (0.62, 0.63, 0.66)}

# role colours for extras: shirt, pants, hair, shoes
ROLES = {  # one flat colour per extra; the colour IS the role
    "red":    {"color": (0.80, 0.12, 0.12), "note": "원판 안 치우는 사람"},
    "yellow": {"color": (0.98, 0.78, 0.12), "note": "거울 앞 폼 잡는 사람"},
    "gray":   {"color": (0.42, 0.43, 0.46), "note": "폰만 보는 사람"},
    "blue":   {"color": (0.16, 0.38, 0.88), "note": "자리 맡아놓고 사라진 사람"},
    "green":  {"color": (0.22, 0.65, 0.32), "note": "여분"},
}

# ------------------------------------------------------------------ basics

def mat(name, color, emit=0.0, rough=0.6, metal=0.0, alpha=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color[:3], 1)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color[:3], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*color[:3], 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def shadeless(name, color=(1, 1, 1), image=None, strength=1.0):
    """Emission-only material (photos, logos, fx) so they read the same under any light. Image alpha is honoured."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image, check_existing=True)
        tex.interpolation = "Closest" if False else "Linear"
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        em.inputs["Color"].default_value = (*color[:3], 1)
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (*color[:3], 1)
    return m


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(ob, c):
    for u in list(ob.users_collection):
        u.objects.unlink(ob)
    c.objects.link(ob)
    return ob


def mesh_obj(name, bm, material, c, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    if material:
        me.materials.append(material)
    c.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def box(name, size, material, c, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    return mesh_obj(name, bm, material, c, loc, rot, parent)


def cyl(name, r, h, material, c, loc=(0, 0, 0), rot=(0, 0, 0), seg=8, r2=None, parent=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    return mesh_obj(name, bm, material, c, loc, rot, parent)


def empty(name, c, loc=(0, 0, 0), parent=None, size=0.2):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    c.objects.link(e)
    e.parent = parent
    e.location = loc
    return e


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def anim_fcurves(id_):
    ad = getattr(id_, "animation_data", None)
    if not ad or not ad.action:
        return []
    out = []
    for layer in ad.action.layers:
        for st in layer.strips:
            for cb in st.channelbags:
                out.extend(cb.fcurves)
    return out


def set_interp(id_, kind, prefix=None, exclude=None):
    """Force interpolation on an ID's keys. prefix/exclude filter by data_path start (e.g. 'pose.bones')."""
    n = 0
    for fc in anim_fcurves(id_):
        dp = fc.data_path
        if prefix and not dp.startswith(prefix):
            continue
        if exclude and dp.startswith(exclude):
            continue
        for k in fc.keyframe_points:
            k.interpolation = kind
            n += 1
    return n


def finalize_interp(pose_kind="CONSTANT"):
    """Everything stop-motion (CONSTANT) except what asked otherwise via custom props:
    characters: pose keys -> pose_kind, object moves -> ob['wc_move_interp']; cameos -> ob['wc_interp']."""
    for ob in bpy.data.objects:
        if ob.type == "ARMATURE":
            set_interp(ob, pose_kind, prefix="pose.bones")
            set_interp(ob, ob.get("wc_move_interp", "CONSTANT"), exclude="pose.bones")
        else:
            set_interp(ob, ob.get("wc_interp", "CONSTANT"))
            if ob.data is not None and hasattr(ob.data, "animation_data"):
                set_interp(ob.data, "CONSTANT")
    for m in bpy.data.materials:
        if m.node_tree:
            set_interp(m.node_tree, "CONSTANT")


def set_keyed_interp(kind):
    """'CONSTANT' (stop-motion, default) / 'LINEAR' / 'BEZIER' for every key inserted after this call."""
    bpy.context.preferences.edit.keyframe_new_interpolation_type = kind


# ------------------------------------------------------------------ scene frames

def render_settings(sc, preview=False):
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = 50 if preview else 100
    sc.render.fps = FPS
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    ee = sc.eevee
    ee.taa_render_samples = 16 if preview else 32
    try:
        ee.use_raytracing = True
    except AttributeError:
        pass
    try:
        ee.use_shadows = True
    except AttributeError:
        pass


GYM_FILL_ENERGY = {"Key": 0.24, "Fill": 0.16, "Rim": 0.30}


def fixed_lights(c, kind="flat"):
    """Same light angles in every reel: warm key from front-left-high, cool fill front-right, rim from behind.
    In the gym these support the ceiling fixtures."""
    out = {}
    specs = (
        [
            ("Key", "SUN", GYM_FILL_ENERGY["Key"], (1.0, 0.84, 0.55), (22, 0, -20), {"angle": math.radians(6)}),
            ("Fill", "SUN", GYM_FILL_ENERGY["Fill"], (0.70, 0.78, 1.0), (65, 0, 45), {"angle": math.radians(35)}),
            ("Rim", "SUN", GYM_FILL_ENERGY["Rim"], (1.0, 0.88, 0.65), (-48, 0, 160), {"angle": math.radians(6)}),
        ]
        if kind == "gym"
        else [
            ("Key", "SUN", 1.5, (1.0, 0.96, 0.9), (50, 0, -35), {"angle": math.radians(8)}),
            ("Fill", "SUN", 0.35, (0.85, 0.9, 1.0), (60, 0, 50), {"angle": math.radians(30)}),
            ("Rim", "SUN", 0.9, (1.0, 1.0, 1.0), (-55, 0, 160), {"angle": math.radians(5)}),
        ]
    )
    for name, typ, energy, color, rot, extra in specs:
        ld = bpy.data.lights.new(name, typ)
        ld.energy = energy
        ld.color = color
        for k, v in extra.items():
            setattr(ld, k, v)
        if name != "Key":
            try:
                ld.use_shadow = False
                ld.specular_factor = 0.0
            except AttributeError:
                pass
        else:
            try:
                ld.specular_factor = 0.12 if kind == "gym" else 0.15
            except AttributeError:
                pass
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = [math.radians(a) for a in rot]
        c.objects.link(ob)
        out[name] = ob
    return out


CAMS = {  # name: (location, target, lens)
    "Cam_Front": ((0.0, -6.2, 1.25), (0.0, 0.0, 1.0), 42),
    "Cam_Side": ((6.2, -0.6, 1.25), (0.0, -0.2, 1.0), 42),
    "Cam_Low": ((0.7, -3.1, 0.22), (0.0, 0.0, 1.25), 24),
}


CAMS_GYM = dict(CAMS, Cam_Side=((4.1, -0.9, 1.25), (0.0, -0.1, 1.0), 26))


def fixed_cameras(c, kind="flat"):
    """Three camera angles as templates. Each camera sits under a CamShake empty (shake is keyed on that parent)."""
    out = {}
    for name, (loc, tgt, lens) in (CAMS_GYM if kind == "gym" else CAMS).items():
        rig = empty(name + "_Shake", c, (0, 0, 0), size=0.1)
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.sensor_fit = "AUTO"
        cd.clip_end = 100
        cam = bpy.data.objects.new(name, cd)
        c.objects.link(cam)
        cam.parent = rig
        cam.location = loc
        look_at(cam, tgt)
        out[name] = cam
    bpy.context.scene.camera = out["Cam_Front"]
    return out


def use_camera(name):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects[name]
    return sc.camera


def frame_gym_interior():
    scene = bpy.context.scene
    camera = use_camera("Cam_Front")
    camera.location = (4.50, -6.43, 1.65)
    camera.data.lens = 20
    look_at(camera, (4.25, 3.5, 1.62))
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100


def build_flat_set(c, color="yellow"):
    col = BG.get(color, color)
    w = bpy.context.scene.world
    w.color = col
    bg = w.node_tree.nodes.get("Background") or next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    amb = tuple(0.55 + 0.45 * x for x in col)  # mostly neutral ambient so the guy is not tinted
    bg.inputs["Color"].default_value = (*amb, 1)
    bg.inputs["Strength"].default_value = 0.5
    # bowl cyclorama: flat floor that curves up into a round wall, so no camera angle sees a horizon or an edge
    prof = [(0.0, 0.0), (9.0, 0.0)]
    R = 3.0
    for i in range(1, 10):
        a = math.radians(90 * i / 9)
        prof.append((9.0 + R * math.sin(a), R - R * math.cos(a)))
    prof.append((9.0 + R, 80.0))
    bm = bmesh.new()
    seg = 48
    rings = []
    for (r, z) in prof[1:]:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z)) for k in range(seg)])
    centre = bm.verts.new((0, 0, 0))
    for k in range(seg):
        bm.faces.new((centre, rings[0][k], rings[0][(k + 1) % seg]))
    for ra, rb in zip(rings, rings[1:]):
        for k in range(seg):
            k2 = (k + 1) % seg
            bm.faces.new((ra[k], rb[k], rb[k2], ra[k2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:  # normals must face the inside (towards the centre / up)
        if f.normal.z < -0.01 or (abs(f.normal.z) < 0.99 and f.normal.dot(-f.calc_center_median().normalized()) < 0):
            f.normal_flip()
    # the lit floor ends up ~1.6x brighter than its albedo, so darken it to land on the chosen colour
    m = mat("BG_cyc_" + (color if isinstance(color, str) else "custom"), tuple(x * 0.78 for x in col), rough=0.9)
    ob = mesh_obj("Set_Cyclorama", bm, m, c)
    ob.visible_shadow = False
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


PILLAR = (-1.4, -0.4)  # gym pillar centre (x, y)


def _kit_collection():
    if "Kit" not in bpy.data.collections:
        k = bpy.data.collections.new("Kit")
        bpy.context.scene.collection.children.link(k)
    return bpy.data.collections["Kit"]


def _hazard_band(name, x0, y0, wx, wy, z0, dz, h, mat_ob, c):
    """Flush parallelogram hazard stripe wrapped around a rectangular column (no sawtooth corner overhang)."""
    bm = bmesh.new()
    hx, hy = wx / 2, wy / 2
    # 8 corners of the skewed box: left side (-hx) is at z0, right side (+hx) is at z0 + dz
    verts = [
        bm.verts.new((-hx, -hy, 0.0)),
        bm.verts.new((+hx, -hy, dz)),
        bm.verts.new((+hx, +hy, dz)),
        bm.verts.new((-hx, +hy, 0.0)),
        bm.verts.new((-hx, -hy, h)),
        bm.verts.new((+hx, -hy, dz + h)),
        bm.verts.new((+hx, +hy, dz + h)),
        bm.verts.new((-hx, +hy, h)),
    ]
    for f in [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (3, 2, 1, 0)]:
        bm.faces.new([verts[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_obj(name, bm, mat_ob, c, (x0, y0, z0))


def load_font(path):
    font = bpy.data.fonts.load(path, check_existing=True)
    if not font.packed_file:
        font.pack()
    return font


def _wall_text(name, text, loc, size, mat_ob, c, align_x="LEFT", offset=0.0022, extrude=0.003, shear=0.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.size = size
    cu.align_x = align_x
    cu.align_y = "CENTER"
    cu.offset = offset
    cu.extrude = extrude
    cu.shear = shear
    cu.font = load_font(KFONT)
    ob = bpy.data.objects.new(name, cu)
    c.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (math.radians(90), 0, 0)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(mat_ob)
    mob = bpy.data.objects.new(name, me)
    mob.location = ob.location
    mob.rotation_euler = ob.rotation_euler
    c.objects.link(mob)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    return mob


def build_gym_floor(c):
    pitch = 0.60
    backing = mat("Gym_FloorBacking", (0.002, 0.002, 0.002), rough=0.98)
    box("FloorBacking", (9.6, 12.2, 0.100), backing, c, (0, -0.8, -0.068))

    rubber = mat("Gym_SpeckledRubber", (0.019, 0.020, 0.022), rough=0.91)
    nodes = rubber.node_tree.nodes
    links = rubber.node_tree.links
    shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Specular IOR Level"].default_value = 0.32
    position = nodes.new("ShaderNodeNewGeometry")
    grains = nodes.new("ShaderNodeTexVoronoi")
    grains.inputs["Scale"].default_value = 63.0
    links.new(position.outputs["Position"], grains.inputs["Vector"])
    flecks = nodes.new("ShaderNodeValToRGB")
    flecks.color_ramp.interpolation = "EASE"
    light, dark = flecks.color_ramp.elements
    light.position, light.color = 0.15, (0.18, 0.18, 0.17, 1)
    dark.position, dark.color = 0.23, (0.019, 0.020, 0.022, 1)
    links.new(grains.outputs["Distance"], flecks.inputs["Fac"])
    # The grid gives each tile its own sheen. Low-frequency noise breaks up highlights within a tile.
    align_grid = nodes.new("ShaderNodeVectorMath")
    align_grid.operation = "ADD"
    align_grid.inputs[1].default_value = (0, 0.2, 0.1)
    links.new(position.outputs["Position"], align_grid.inputs[0])
    grid = nodes.new("ShaderNodeVectorMath")
    grid.operation = "SNAP"
    grid.inputs[1].default_value = (pitch, pitch, pitch)
    links.new(align_grid.outputs["Vector"], grid.inputs[0])
    tile_variation = nodes.new("ShaderNodeTexWhiteNoise")
    links.new(grid.outputs["Vector"], tile_variation.inputs["Vector"])
    grain_surface = nodes.new("ShaderNodeTexNoise")
    grain_surface.inputs["Scale"].default_value = 5.5
    links.new(position.outputs["Position"], grain_surface.inputs["Vector"])

    sheen = nodes.new("ShaderNodeMixRGB")
    sheen.inputs[0].default_value = 0.38
    links.new(tile_variation.outputs["Value"], sheen.inputs[1])
    links.new(grain_surface.outputs["Fac"], sheen.inputs[2])
    roughness = nodes.new("ShaderNodeMapRange")
    roughness.inputs["To Min"].default_value = 0.44
    roughness.inputs["To Max"].default_value = 0.80
    links.new(sheen.outputs["Color"], roughness.inputs["Value"])
    links.new(roughness.outputs["Result"], shader.inputs["Roughness"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.21
    bump.inputs["Distance"].default_value = 0.012
    links.new(grain_surface.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])

    shade = nodes.new("ShaderNodeMapRange")
    shade.inputs["To Min"].default_value = 0.91
    shade.inputs["To Max"].default_value = 1.09
    links.new(tile_variation.outputs["Value"], shade.inputs["Value"])
    tinted_rubber = nodes.new("ShaderNodeMixRGB")
    tinted_rubber.blend_type = "MULTIPLY"
    tinted_rubber.inputs[0].default_value = 1.0
    links.new(flecks.outputs["Color"], tinted_rubber.inputs[1])
    links.new(shade.outputs["Result"], tinted_rubber.inputs[2])
    links.new(tinted_rubber.outputs["Color"], shader.inputs["Base Color"])

    width = pitch - 0.009
    tile = box("RubberFloorTiles", (width, width, 0.020), rubber, c, (-4.5, -6.5, -0.010))
    bevel = tile.modifiers.new("Soft rubber edges", "BEVEL")
    bevel.width = 0.0008
    for name, count, offset in (("Columns", 16, (pitch, 0, 0)), ("Rows", 20, (0, pitch, 0))):
        array = tile.modifiers.new(name, "ARRAY")
        array.count = count
        array.use_relative_offset = False
        array.use_constant_offset = True
        array.constant_offset_displace = offset


def add_gym_light_glow(scene):
    tree = bpy.data.node_groups.new("Gym tube glow", "CompositorNodeTree")
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = tree.nodes.new("CompositorNodeRLayers")
    glow = tree.nodes.new("CompositorNodeGlare")
    glow.inputs["Type"].default_value = "Fog Glow"
    glow.inputs["Quality"].default_value = "High"
    glow.inputs["Threshold"].default_value = 5.4
    glow.inputs["Strength"].default_value = 0.48
    glow.inputs["Size"].default_value = 0.37
    output = tree.nodes.new("NodeGroupOutput")
    tree.links.new(layers.outputs["Image"], glow.inputs["Image"])
    tree.links.new(glow.outputs["Image"], output.inputs["Image"])
    scene.compositing_node_group = tree


def build_gym_strip_lights(c):
    """Warm strips run parallel to the mirror, with a soft ceiling wash."""
    channel = mat("Gym_StripChannel", (0.012, 0.012, 0.015), rough=0.8)
    strip = shadeless("Gym_WarmStripDiffuser", (1.0, 0.62, 0.25), strength=12.0)
    length = 8.65
    for position, y in (("Front", -0.24), ("Back", 2.64)):
        box("StripChannel_" + position, (length, 0.068, 0.064), channel, c, (0, y, 3.560))
        cyl("CeilingStrip_" + position, 0.016, length - 0.01, strip, c, (0, y, 3.519), (0, 90, 0), seg=16)

        # Use real area lights for the room and the warm bounce around each diffuser.
        for name, z, tilt, width, energy, color in (
            ("StripArea", 3.499, 0, 0.25, 435, (1.0, 0.84, 0.63)),
            ("StripWash", 3.495, math.pi, 0.38, 105, (1.0, 0.73, 0.47)),
        ):
            light = bpy.data.lights.new(f"{name}_{position}", "AREA")
            light.shape = "RECTANGLE"
            light.size = length
            light.size_y = width
            light.energy = energy
            light.color = color
            light.specular_factor = 0.42 if tilt == 0 else 0.0
            light.use_shadow = tilt == 0
            ob = bpy.data.objects.new(light.name, light)
            ob.location = (0, y, z)
            ob.rotation_euler.x = tilt
            c.objects.link(ob)


def build_gym_ceiling_lights(c):
    build_gym_strip_lights(c)
    downlight = shadeless("Gym_Downlight", (1.0, 0.87, 0.64), strength=1.45)
    for x in (-2.45, 0.0, 2.45):
        for y in (-1.8, 0.65, 3.95):
            # The ceiling underside is z=3.59 m. Only the lens face is visible.
            cyl("RecessedLens", 0.047, 0.012, downlight, c, (x, y, 3.587), seg=24)
            light = bpy.data.lights.new("RecessedSpot", "SPOT")
            light.energy = 24
            light.color = (1.0, 0.88, 0.72)
            light.spot_size = math.radians(78)
            light.spot_blend = 0.65
            light.use_shadow = False
            ob = bpy.data.objects.new(light.name, light)
            ob.location = (x, y, 3.575)
            c.objects.link(ob)


def build_gym_back_baseboard(c, trim):
    box("Baseboard_BackLeft", (1.70, 0.04, 0.10), trim, c, (-3.65, 4.985, 0.05))
    box("Baseboard_BackRight", (1.10, 0.04, 0.10), trim, c, (3.95, 4.985, 0.05))


def extend_gym_right(c):
    """Extend the room shell and built-in fixtures to the right of the original set."""
    extension = 9.0
    mirror_extension = 10.0

    def extend_mesh(obj, distance, axis=0):
        # The back-wall pipe and light tubes are cylinders with local Z along world X.
        coords = [v.co[axis] for v in obj.data.vertices]
        length = (max(coords) - min(coords)) * obj.scale[axis]
        obj.scale[axis] *= (length + distance) / length
        obj.location.x += distance / 2

    for name in ("FloorBacking", "Wall_Back", "Wall_Front", "Wainscot_Back", "Wainscot_Front", "Ceiling"):
        extend_mesh(c.objects[name], extension)
    for obj in c.objects:
        if obj.name.startswith("CeilBeam"):
            extend_mesh(obj, extension)
    for name in ("Wall_Right", "Wainscot_Right"):
        c.objects[name].location.x += extension
    floor_columns = c.objects["RubberFloorTiles"].modifiers["Columns"]
    floor_columns.count += round(extension / floor_columns.constant_offset_displace.x)
    extend_mesh(c.objects["Pipe_Back"], extension, axis=2)

    for name in ("MirrorFrame", "Mirror"):
        extend_mesh(c.objects[name], mirror_extension)
    probe = c.objects.get("MirrorProbe")
    if probe is not None:
        probe.location.x += mirror_extension / 2
        probe.scale.x += mirror_extension / 2
    mullion = max((obj for obj in c.objects if obj.name.startswith("MirrorMullion")), key=lambda obj: obj.location.x)
    for offset in (1.7, 3.4, 5.1, 6.8, 8.39, 9.89):
        panel = mullion.copy()
        panel.location.x += offset
        c.objects.link(panel)
    right_baseboard = c.objects["Baseboard_BackRight"]
    extend_mesh(right_baseboard, extension - mirror_extension)
    right_baseboard.location.x += mirror_extension

    for position in ("Front", "Back"):
        extend_mesh(c.objects["StripChannel_" + position], extension)
        extend_mesh(c.objects["CeilingStrip_" + position], extension, axis=2)
        for name in ("StripArea_", "StripWash_"):
            light = c.objects[name + position]
            light.data.energy *= (light.data.size + extension) / light.data.size
            light.data.size += extension
            light.location.x += extension / 2
    right_downlights = [
        obj for obj in c.objects
        if obj.name.startswith(("RecessedLens", "RecessedSpot")) and math.isclose(obj.location.x, 2.45, abs_tol=1e-5)
    ]
    for x in (5.45, 8.45, 11.45):
        for obj in right_downlights:
            new_light = obj.copy()
            new_light.location.x = x
            c.objects.link(new_light)


def add_symmetric_gym_pillars(c):
    middle = (c.objects["Wall_Left"].location.x + c.objects["Wall_Right"].location.x) / 2
    original_x = c.objects["Pillar"].location.x
    parts = [obj for obj in c.objects if obj.name == "Pillar" or obj.name.startswith("Pillar_")]
    for label, offset in (("Center", middle - original_x), ("Right", 2 * (middle - original_x))):
        for part in parts:
            copy = part.copy()
            copy.name = f"{part.name}_{label}"
            copy.location.x += offset
            c.objects.link(copy)


def build_gym_neon(c, mirror):
    # Hand-drawn centerlines let the Korean lettering read as bent tube, including the round consonants.
    glyphs = {
        "운": ("*.50,.93 .31,.87 .30,.71 .48,.65 .67,.71 .67,.86",
              ".12,.52 .49,.54 .91,.56", ".51,.51 .48,.37", ".27,.30 .26,.10 .53,.09 .83,.13"),
        "동": (".72,.92 .28,.91 .26,.70 .47,.67 .76,.70", ".51,.66 .49,.49",
              ".12,.48 .50,.48 .90,.50", "*.52,.33 .35,.29 .32,.15 .49,.08 .68,.13 .70,.26"),
        "은": ("*.50,.92 .30,.85 .31,.69 .48,.64 .68,.70 .71,.84",
              ".12,.49 .52,.51 .91,.53", ".27,.35 .24,.12 .49,.09 .79,.13"),
        "!": (".35,.91 .29,.68 .25,.39", ".25,.17 .24,.12"),
        "워": ("*.30,.92 .15,.83 .16,.63 .30,.57 .46,.65 .47,.82",
              ".06,.42 .30,.43 .55,.46", ".29,.42 .27,.18", ".57,.65 .78,.66", ".78,.93 .76,.55 .74,.10"),
        "치": (".29,.93 .37,.86", ".09,.76 .33,.75 .57,.78",
              ".34,.72 .28,.53 .19,.39 .07,.29", ".29,.53 .43,.43 .57,.32", ".81,.92 .78,.53 .78,.12"),
        "코": (".24,.91 .53,.93 .77,.90 .74,.73 .67,.60", ".22,.72 .48,.73 .72,.74",
              ".49,.55 .48,.34", ".10,.33 .46,.34 .87,.36"),
        "에": ("*.30,.77 .15,.69 .14,.48 .29,.36 .44,.46 .45,.66",
              ".47,.56 .65,.58", ".64,.90 .64,.59 .61,.24", ".83,.91 .84,.54 .83,.13"),
        "서": (".35,.84 .29,.68 .20,.53 .08,.41", ".27,.65 .40,.52 .52,.43",
              ".55,.60 .76,.61", ".79,.92 .76,.58 .76,.13"),
    }

    def tube(name, paths, radius, material):
        curve = bpy.data.curves.new(name, "CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 12
        curve.bevel_depth = radius
        curve.bevel_resolution = 4
        curve.use_fill_caps = True
        curve.materials.append(material)
        for coords, closed in paths:
            spline = curve.splines.new("BEZIER")
            spline.bezier_points.add(len(coords) - 1)
            spline.use_cyclic_u = closed
            for point, (x, z) in zip(spline.bezier_points, coords):
                point.co = (x, 4.946, z)
                point.handle_left_type = point.handle_right_type = "AUTO"
        obj = bpy.data.objects.new(name, curve)
        c.objects.link(obj)

    def lettering(text, x, z, width, height, offsets):
        for index, char in enumerate(text):
            for stroke in glyphs[char]:
                points = (tuple(map(float, pair.split(","))) for pair in stroke.lstrip("*").split())
                yield ([(x + index * width + width * (u + 0.12 * v), z + height * v + offsets[index])
                        for u, v in points], stroke.startswith("*"))

    pink = shadeless("Gym_NeonTubePink", (1.0, 0.10, 0.42), strength=23)
    blue = shadeless("Gym_NeonTubeBlue", (0.025, 0.42, 1.0), strength=20)
    tube("Neon_HandwrittenTop", lettering("운동은!", -0.57, 2.83, 0.202, 0.194, (0, 0.008, -0.002, 0.015)), 0.0046, pink)
    tube("Neon_HandwrittenBottom", lettering("워치코치에서", -0.60, 2.60, 0.225, 0.187, (0, -0.005, 0.010, -0.002, 0.008, 0.004)), 0.0047, pink)

    # One rounded arm outline and the inner bend of the wrist, as on the reference sign.
    arm = [(0.245, 2.828), (0.24, 2.877), (0.293, 2.918), (0.351, 2.931),
           (0.404, 2.926), (0.438, 2.906), (0.511, 2.923), (0.501, 2.976),
           (0.472, 3.019), (0.398, 3.014), (0.372, 3.040), (0.401, 3.068),
           (0.497, 3.073), (0.554, 3.048), (0.625, 2.990), (0.690, 2.917),
           (0.705, 2.872), (0.669, 2.839), (0.582, 2.822), (0.472, 2.805),
           (0.371, 2.801), (0.284, 2.805)]
    tube("Neon_RoundedBicep", [(arm, True), ([(0.502, 2.976), (0.552, 2.947), (0.570, 2.914)], False)], 0.0065, blue)

    for name, loc, color, energy in (
        ("PinkLeft", (-0.39, 4.84, 2.78), (1.0, 0.045, 0.37), 14),
        ("PinkRight", (0.23, 4.85, 2.69), (1.0, 0.035, 0.43), 12),
        ("Blue", (0.48, 4.81, 2.94), (0.035, 0.23, 1.0), 24),
    ):
        light = bpy.data.lights.new("NeonGlow_" + name, "POINT")
        light.energy = energy
        light.color = color
        light.shadow_soft_size = 0.15
        light.use_shadow = False
        obj = bpy.data.objects.new(light.name, light)
        obj.location = loc
        c.objects.link(obj)

    # The wall-mounted sign sits above the glass. Add the tint that spills over the mirror's top edge.
    tree = mirror.data.materials[0].node_tree
    shader = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    position = tree.nodes.new("ShaderNodeNewGeometry")
    combined = tree.nodes.new("ShaderNodeVectorMath")
    combined.operation = "ADD"
    for index, (anchor, radius, color) in enumerate((
        ((-0.14, 4.962, 2.53), 0.66, (0.075, 0.004, 0.028)),
        ((0.51, 4.962, 2.59), 0.56, (0.004, 0.025, 0.09)),
    )):
        distance = tree.nodes.new("ShaderNodeVectorMath")
        distance.operation = "DISTANCE"
        distance.inputs[1].default_value = anchor
        tree.links.new(position.outputs["Position"], distance.inputs[0])
        falloff = tree.nodes.new("ShaderNodeMapRange")
        falloff.interpolation_type = "SMOOTHSTEP"
        falloff.inputs["From Max"].default_value = radius
        falloff.inputs["To Min"].default_value = 1
        falloff.inputs["To Max"].default_value = 0
        tree.links.new(distance.outputs["Value"], falloff.inputs["Value"])
        tint = tree.nodes.new("ShaderNodeVectorMath")
        tint.operation = "SCALE"
        tint.inputs[0].default_value = color
        tree.links.new(falloff.outputs["Result"], tint.inputs["Scale"])
        tree.links.new(tint.outputs["Vector"], combined.inputs[index])
    tree.links.new(combined.outputs["Vector"], shader.inputs["Emission Color"])
    shader.inputs["Emission Strength"].default_value = 1


def build_left_wall_neon(parent, wall):
    """Hand-bent paths in front-photo pixel coordinates. Depth is measured from plaster."""
    c = coll("Left Wall Handwriting", parent)
    import numpy as np
    from mathutils.geometry import interpolate_bezier

    scale = 0.0035

    def xyz(u, v, depth):
        return (-4.5 + depth, -3.4 + (u - 412) * scale, 2.22 - (v - 275) * scale)

    steel = mat("Neon dark powder coat", (.006, .005, .006), rough=.52, metal=.38)
    rubber = mat("Neon black insulation", (.004, .0035, .004), rough=.68)
    pink = mat("Neon rose glass", (1, .039, .36), emit=11, rough=.24)
    white = mat("Neon milk glass", (.86, .97, 1), emit=7, rough=.22)

    rubber_tree = rubber.node_tree
    rubber_surface = next(node for node in rubber_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    rubber_surface.inputs['Specular IOR Level'].default_value = .28
    sheath = rubber_tree.nodes.new('ShaderNodeTexNoise')
    sheath.inputs['Scale'].default_value = 360
    sheath_coordinates = rubber_tree.nodes.new('ShaderNodeTexCoord')
    rubber_tree.links.new(sheath_coordinates.outputs['Object'], sheath.inputs['Vector'])
    sheath_bump = rubber_tree.nodes.new('ShaderNodeBump')
    sheath_bump.inputs['Strength'].default_value = .16
    sheath_bump.inputs['Distance'].default_value = .0004
    rubber_tree.links.new(sheath.outputs['Fac'], sheath_bump.inputs['Height'])
    rubber_tree.links.new(sheath_bump.outputs['Normal'], rubber_surface.inputs['Normal'])

    # The rose tube fades from its pale center into a saturated rim.
    tube_tree = pink.node_tree
    tube_surface = next(node for node in tube_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    facing = tube_tree.nodes.new('ShaderNodeLayerWeight')
    tint = tube_tree.nodes.new('ShaderNodeValToRGB')
    tint.color_ramp.elements[0].color = (1, .068, .32, 1)
    tint.color_ramp.elements[0].position = .13
    tint.color_ramp.elements[1].color = (1, .008, .19, 1)
    tube_tree.links.new(facing.outputs['Facing'], tint.inputs[0])
    tube_tree.links.new(tint.outputs[0], tube_surface.inputs['Emission Color'])

    def stroke(name, points, radius, material, depth):
        curve = bpy.data.curves.new(name, 'CURVE')
        curve.dimensions = '3D'
        curve.resolution_u = 10
        curve.bevel_depth = radius
        curve.bevel_resolution = 4
        curve.use_fill_caps = True
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(len(points) - 1)
        for point, (u, v) in zip(spline.bezier_points, points):
            point.co = xyz(u, v, depth)
            point.handle_left_type = point.handle_right_type = 'AUTO'
        obj = bpy.data.objects.new(name, curve)
        c.objects.link(obj)
        curve.materials.append(material)
        return obj

    # Each line is one uninterrupted bend, keeping the dark electrode gaps.
    bends = [
        [(96,204),(97,220),(99,235),(108,236),(128,233)],
        [(114,218),(135,216)], [(139,203),(137,221),(137,247),(141,253)],
        [(116,251),(116,271),(122,274),(147,272)],
        [(213,230),(201,224),(198,213),(203,203),(214,199),(224,202),(230,213),(226,224),(219,229)],
        [(189,244),(204,241),(224,240),(241,240)], [(218,246),(219,258)],
        [(203,253),(204,270),(211,272),(235,271)],
        [(298,202),(276,202),(263,204),(262,218),(267,222),(301,221)],
        [(281,226),(281,237)], [(255,239),(282,238),(306,237)],
        [(281,250),(272,252),(268,261),(271,271),(280,276),(290,273),(296,263),(294,255),(286,251)],
        [(332,195),(351,197)], [(324,209),(341,208),(359,209)],
        [(338,214),(329,218),(327,228),(333,236),(344,238),(354,232),(357,222),(353,215),(347,213)],
        [(373,200),(370,216),(371,242)], [(372,216),(386,216)],
        [(346,249),(369,249),(373,259),(351,262),(351,273),(378,272)],
        [(437,202),(425,203),(424,219),(425,237),(435,239)],
        [(455,204),(443,205),(440,219),(442,238),(455,237)],
        [(464,197),(463,220),(465,254)], [(464,219),(477,219)], [(480,196),(478,223),(479,255)],
        [(344,320),(359,321),(371,319)], [(359,323),(357,339),(355,355)],
        [(358,342),(365,343),(378,348)], [(374,333),(384,332)],
        [(387,317),(385,337),(385,357)], [(403,315),(399,331),(400,356)],
        [(373,366),(398,365),(401,371),(398,377),(380,380),(380,392),(407,392)],
        [(455,357),(445,355),(440,345),(443,332),(453,326),(465,328),(472,339),(470,350),(461,357)],
        [(473,330),(486,329)], [(474,351),(487,351)], [(488,318),(488,342),(490,374)],
        [(503,316),(501,341),(503,376)],
        [(521,318),(523,340),(525,358),(536,361),(554,358),(555,339),(556,317)],
        [(539,320),(540,338),(539,357)], [(524,339),(553,338)], [(557,339),(574,339)],
        [(578,317),(577,342),(579,373)],
    ]
    bell = [
        [(597,303),(580,285),(569,264),(568,248),(577,229),(599,212),(628,196),(655,191),(679,196),(693,213),(700,236),(702,258),(712,268),(728,289),(735,311),(732,334),(724,350),(706,359),(678,371),(655,381),(635,374),(616,359),(605,340),(601,322),(600,308)],
        [(600,268),(589,251),(590,243),(602,231),(627,218),(649,212),(661,214),(671,226),(680,247),(678,251),(657,251),(638,256),(621,267),(608,281),(600,268)]
    ]
    tubes = [stroke("Bent neon glass", path, .009, material, .087)
             for paths, material in ((bends, pink), (bell, white)) for path in paths]

    for u1, v1, u2, v2 in [(99,212,690,204),(102,240,696,235),(95,273,701,273),
                           (335,321,732,320),(334,347,723,346),(334,375,696,375)]:
        angle = math.degrees(math.atan2(v1 - v2, u2 - u1))
        rail = box("Steel crossbar", (.016, math.hypot(u2-u1, v2-v1)*scale, .021),
                   steel, c, xyz((u1+u2)/2, (v1+v2)/2, .045), (angle, 0, 0))
        bevel = rail.modifiers.new("Rolled steel edge", 'BEVEL')
        bevel.width, bevel.segments = .0013, 2
    for u, top, bottom in [(101,206,273),(342,174,459),(470,173,461),(599,183,376)]:
        box("Steel upright", (.016,.020,(bottom-top)*scale), steel,c,xyz(u,(top+bottom)/2,.03))
    for u in (342,470):
        stroke("Hanging eye",[(u-3,177),(u-4,172),(u,165),(u+4,172),(u+3,177),(u-3,177)],.003,steel,.031)
        cyl("Wall anchor", .009,.034,steel,c,xyz(u,170,.017),(0,90,0),seg=16)
    for name, radius, depth, points in (
        ("Lead behind first letter", .005, .066, [(141,253),(134,256),(124,254),(116,251)]),
        ("First bottom jumper", .005, .063, [(147,272),(173,272),(203,270)]),
        ("First upper rail jumper", .006, .057, [(136,219),(167,216),(186,221),(209,217)]),
        ("Hanging jumper", .006, .070, [(241,240),(247,254),(243,272),(234,289),(245,280),(267,259),(278,251)]),
        ("Hanging jumper return", .005, .057, [(236,286),(252,277),(272,267),(291,269)]),
        ("Upper frame jumper", .006, .062, [(299,202),(316,200),(324,196),(333,200),(343,205)]),
        ("Black loop between letters", .006, .069, [(384,218),(389,225),(390,249),(387,278),(393,266),(402,250)]),
        ("Long diagonal feed", .007, .060, [(458,234),(441,239),(428,248),(414,278),(393,317)]),
        ("Right top return", .005, .066, [(480,198),(484,219),(487,246),(491,264),(495,258)]),
        ("Bottom left hanging loop", .006, .077, [(351,346),(351,365),(355,380),(340,398),(327,414),(324,432),(330,447),(348,455)]),
        ("Transformer return loop", .006, .068, [(393,415),(415,410),(431,394),(441,371),(452,336),(457,309),(463,296),(462,316),(454,346)]),
        ("Lower rail return", .006, .069, [(531,357),(547,363),(563,372),(585,376)]),
        ("Kettlebell handle feed", .006, .066, [(602,290),(618,277),(634,259),(653,244),(662,230),(669,225)]),
        ("Kettlebell body feed", .007, .072, [(594,279),(597,301),(603,323),(616,344),(632,362)]),
        ("Long mains lead", .007, .091, [(466,443),(476,448),(482,462),(489,490),(497,530),(508,594),(515,658),(516,730)]),
    ):
        stroke(name, points, radius, rubber, depth)

    for u, v, angle in [(217,240,5),(280,238,4),(371,236,90),(464,236,90),
                         (355,321,10),(457,313,105),(577,346,95),(581,267,85),
                         (663,230,128),(600,303,88),(714,346,35)]:
        clip = box("Cable clip", (.016,.032,.014), steel, c, xyz(u,v,.069), (angle,0,0))
        cyl("Clip rivet", .003,.004,steel,c, (clip.location.x + .010,clip.location.y,clip.location.z),
            (0,90,0), seg=12)
    for points in ([(236,287),(241,279),(245,269)], [(646,251),(654,243),(659,235)],
                   [(610,334),(617,346),(624,353)], [(463,447),(475,450),(480,457)]):
        stroke("Insulated splice sleeve", points, .009, rubber, .074)
    box("Neon transformer",(.095,.45,.185),steel,c,xyz(407,438,.058))
    lid = box("Transformer lid", (.014,.43,.168), rubber, c, xyz(407,438,.107))
    bevel = lid.modifiers.new("Rounded molded edges", 'BEVEL')
    bevel.width, bevel.segments = .004, 3
    for u, v in [(235,285),(390,268),(458,312),(604,325),(651,247)]:
        stroke("Cable tie", [(u-2,v-2),(u,v-1),(u+2,v+1),(u+3,v+3)], .002, rubber, .078)
    for u,v in [(348,417),(466,417),(348,458),(466,458)]:
        cyl("Cover screw",.004,.004,steel,c,xyz(u,v,.115),(0,90,0),seg=12)
    # Bounced light is evaluated only on the inward face of the plaster.
    plaster = wall.data.materials[0].copy()
    plaster.name = "Left wall plaster under neon"
    wall.data.materials[0] = plaster
    tree = plaster.node_tree
    surface = next(node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED')
    geometry = tree.nodes.new('ShaderNodeNewGeometry')

    def vector(operation, first, second):
        node = tree.nodes.new('ShaderNodeVectorMath')
        node.operation = operation
        for index, value in enumerate((first, second)):
            if isinstance(value, bpy.types.NodeSocket):
                tree.links.new(value, node.inputs[index])
            else:
                node.inputs[index].default_value = value
        return node.outputs['Value' if operation == 'DOT_PRODUCT' else 'Vector']

    def math_node(operation, first, second=0):
        node = tree.nodes.new('ShaderNodeMath')
        node.operation = operation
        for index, value in enumerate((first, second)):
            if isinstance(value, bpy.types.NodeSocket):
                tree.links.new(value, node.inputs[index])
            else:
                node.inputs[index].default_value = value
        return node.outputs[0]

    # Integrate the wall-facing irradiance along the actual round tube paths.
    # Pack the result inside the blend so the builder needs no external image.
    width, height = 1024, 784
    left, bottom = -112, 692
    pixels = np.zeros((height, width, 4), dtype=np.float32)
    pixels[:, :, 3] = 1
    for tube in tubes:
        is_pink = tube.data.materials[0] == pink
        color = np.array((1, .037, .28) if is_pink else (.89, .99, 1.035), dtype=np.float32)
        distance = 24 if is_pink else 28
        intensity = 5.5 if is_pink else 5.0
        points = tube.data.splines[0].bezier_points
        for start, end in zip(points, list(points)[1:]):
            samples = interpolate_bezier(start.co, start.handle_right, end.handle_left, end.co, 9)
            for first, second in zip(samples, samples[1:]):
                length = (second - first).length / scale
                center = (first + second) * .5
                x = 412 + (center.y + 3.4) / scale - left
                y = bottom - (275 - (center.z - 2.22) / scale)
                radius = 155
                x0, x1 = max(0, int(x) - radius), min(width, int(x) + radius + 1)
                y0, y1 = max(0, int(y) - radius), min(height, int(y) + radius + 1)
                r2 = (np.arange(x0, x1) - x)**2 + (np.arange(y0, y1)[:, None] - y)**2
                irradiance = distance / (r2 + distance**2)**1.5
                fade = np.maximum(1 - r2 / radius**2, 0)**2
                pixels[y0:y1, x0:x1, :3] += (irradiance * fade * length * intensity)[:, :, None] * color

    # Soft second bounce in the gaps between the rails and around dense bends.
    # The metal and plaster spread some light farther than the direct tube wash.
    rows, columns = np.ogrid[:height, :width]
    for u, v, spread_x, spread_y, color in (
        (149, 236, 51, 41, (.19, .003, .049)),
        (277, 241, 119, 88, (.115, .002, .029)),
        (367, 289, 87, 53, (.20, .004, .051)),
        (442, 351, 97, 63, (.23, .004, .067)),
        (403, 396, 55, 30, (.17, .003, .047)),
        (648, 317, 57, 68, (.042, .059, .068)),
    ):
        distance_2 = ((columns + left - u) / spread_x)**2 + ((bottom - rows - v) / spread_y)**2
        pixels[:, :, :3] += np.exp(-distance_2)[:, :, None] * np.asarray(color)

    bounce = bpy.data.images.new("Left wall neon irradiance", width, height, alpha=True, float_buffer=True)
    bounce.colorspace_settings.name = 'Non-Color'
    bounce.pixels.foreach_set(pixels.ravel())
    bounce.pack()
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image = bounce
    texture.extension = 'CLIP'
    offset = vector('SUBTRACT', geometry.outputs['Position'], xyz(left, bottom, 0))
    uv = tree.nodes.new('ShaderNodeVectorRotate')
    uv.rotation_type = 'Z_AXIS'
    uv.inputs['Angle'].default_value = -math.pi / 2
    tree.links.new(offset, uv.inputs['Vector'])
    # Rotation about X maps the normalized height onto the image's V axis.
    normalized = vector('MULTIPLY', uv.outputs['Vector'], (1 / (width * scale), 0, 1 / (height * scale)))
    vertical = tree.nodes.new('ShaderNodeVectorRotate')
    vertical.rotation_type = 'X_AXIS'
    vertical.inputs['Angle'].default_value = -math.pi / 2
    tree.links.new(normalized, vertical.inputs['Vector'])
    tree.links.new(vertical.outputs['Vector'], texture.inputs['Vector'])

    fill_offset = vector('SUBTRACT', geometry.outputs['Position'], xyz(385, 260, 0))
    fill_distance = vector('MULTIPLY', fill_offset, (0, 1 / (665 * scale), 1 / (500 * scale)))
    fill = math_node('EXPONENT', math_node('MULTIPLY', vector('DOT_PRODUCT', fill_distance, fill_distance), -1))
    warm = tree.nodes.new('ShaderNodeVectorMath')
    warm.operation = 'SCALE'
    warm.inputs[0].default_value = (.080, .047, .028)
    tree.links.new(fill, warm.inputs['Scale'])
    reflected = vector('ADD', texture.outputs['Color'], warm.outputs['Vector'])

    # Fine plaster grain breaks up the reflected light and catches the fill.
    grain = tree.nodes.new('ShaderNodeTexNoise')
    grain.inputs['Scale'].default_value = 210
    tree.links.new(geometry.outputs['Position'], grain.inputs['Vector'])
    mottling = tree.nodes.new('ShaderNodeTexNoise')
    mottling.inputs['Scale'].default_value = 12
    tree.links.new(geometry.outputs['Position'], mottling.inputs['Vector'])
    fine_variation = math_node('MULTIPLY', grain.outputs['Fac'], .14)
    broad_variation = math_node('MULTIPLY', mottling.outputs['Fac'], .18)
    variation = math_node('ADD', math_node('ADD', fine_variation, broad_variation), .84)
    inward = math_node('MAXIMUM', vector('DOT_PRODUCT', geometry.outputs['Normal'], (1, 0, 0)), 0)
    tree.links.new(reflected, surface.inputs['Emission Color'])
    tree.links.new(math_node('MULTIPLY', inward, variation), surface.inputs['Emission Strength'])
    bump = tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .23
    bump.inputs['Distance'].default_value = .003
    tree.links.new(grain.outputs['Fac'], bump.inputs['Height'])
    tree.links.new(bump.outputs['Normal'], surface.inputs['Normal'])

    # Low-energy, wall-facing light gives the rails and cables soft physical highlights.
    receivers = bpy.data.collections.new("Left wall neon light receivers")
    receivers.objects.link(wall)
    for obj in c.objects:
        receivers.objects.link(obj)
    for name, u, v, depth, width, height, color, power in (
        ("Warm neon fill", 393, 286, 1.43, 2.55, 1.9, (1, .65, .42), 16),
        ("Rose neon bounce", 301, 241, .26, 1.35, .29, (1, .022, .19), 2.5),
        ("Lower rose neon bounce", 457, 346, .27, .85, .28, (1, .022, .19), 2.4),
        ("White neon bounce", 660, 285, .29, .49, .60, (.85, .96, 1), 2.5),
    ):
        light = bpy.data.lights.new(name, 'AREA')
        light.shape = 'RECTANGLE'
        light.size, light.size_y = width, height
        light.color, light.energy = color, power
        light.use_shadow = depth > 1
        light.specular_factor = .65 if depth > 1 else .32
        light.use_custom_distance = True
        light.cutoff_distance = 2.0 if depth > 1 else .8
        lamp = bpy.data.objects.new(name, light)
        c.objects.link(lamp)
        lamp.location = xyz(u, v, depth)
        look_at(lamp, xyz(u, v, 0))
        lamp.light_linking.receiver_collection = receivers


def build_gym_instagram_stickers(parent):
    """White vinyl on the last full-height mirror panel."""
    decals = coll("Instagram Mirror Stickers", parent)
    x, y = 12.59, 4.952
    width = 1.28

    for name, file, height, z in (
        ("InstagramHeader", "instagram_mirror_header.png", 0.165, 2.235),
        ("InstagramActions", "instagram_mirror_actions.png", 0.135, 1.050),
    ):
        image = os.path.join(PARTS, file)
        material = shadeless(name, image=image)
        texture = next(node for node in material.node_tree.nodes if node.type == "TEX_IMAGE")
        if not texture.image.packed_file:
            texture.image.pack()
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([
            (x - width / 2, y, z - height / 2), (x + width / 2, y, z - height / 2),
            (x + width / 2, y, z + height / 2), (x - width / 2, y, z + height / 2),
        ], [], [(0, 1, 2, 3)])
        mesh.materials.append(material)
        uvs = mesh.uv_layers.new(name="UVMap")
        for loop, uv in zip(uvs.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop.uv = uv
        decals.objects.link(bpy.data.objects.new(name, mesh))

    vinyl = shadeless("Instagram White Vinyl")
    _wall_text("InstagramGymName", "워치코치", (x, y, 2.085), 0.110, vinyl, decals,
               align_x="CENTER", offset=0.0011, extrude=0.0003, shear=0.08)
    for name, text, z, size in (
        ("InstagramLikes", "♥ 1,000,000개 Likes", 0.923, 0.080),
        ("InstagramHashtag1", "#워치코치 #경대점", 0.824, 0.106),
        ("InstagramHashtag2", "#경대헬스장 #PT맛집 #오운완", 0.721, 0.106),
        ("InstagramHashtag3", "#24시연중무휴헬스장", 0.618, 0.106),
        ("InstagramHandle", "@watchcoach.app", 0.500, 0.106),
    ):
        label = _wall_text(name, text, (11.962, y, z), size, vinyl, decals,
                           offset=0.0018, extrude=0.0003, shear=0.12)
        right = max(vertex.co.x for vertex in label.data.vertices)
        label.scale.x = min(1.0, 1.23 / right)


def build_gym_daylight_window(parent, wall):
    """A static sky panel and broad room fill stand in for an exterior."""
    window = coll("Right Wall Daylight Window", parent)
    bpy.context.view_layer.update()
    x = min((wall.matrix_world @ Vector(point)).x for point in wall.bound_box)
    y, z = 1.25, 2.02
    width, height = 3.65, 1.85
    left, right = y - width / 2, y + width / 2
    bottom, top = z - height / 2, z + height / 2
    artwork = shadeless("Window Sky Vinyl", image=os.path.join(PARTS, "gym_window_sky.png"), strength=1.15)
    sky = next(node.image for node in artwork.node_tree.nodes if node.type == "TEX_IMAGE")
    if not sky.packed_file:
        sky.pack()

    mesh = bpy.data.meshes.new("Window Sky")
    mesh.from_pydata([
        (x - 0.014, right, bottom), (x - 0.014, left, bottom),
        (x - 0.014, left, top), (x - 0.014, right, top),
    ], [], [(0, 1, 2, 3)])
    uv_map = mesh.uv_layers.new(name="UVMap")
    for loop, uv in zip(uv_map.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = uv
    mesh.materials.append(artwork)
    window.objects.link(bpy.data.objects.new("Window Sky", mesh))

    frame = mat("Window Charcoal Frame", (0.046, 0.049, 0.052), rough=0.58, metal=0.15)
    for name, yy in (("Far", left), ("Center", y), ("Near", right)):
        box("Window Jamb " + name, (0.106, 0.075, height + 0.06), frame, window, (x - 0.018, yy, z))
    for name, zz in (("Head", top + 0.014), ("Sill", bottom - 0.014)):
        box("Window " + name, (0.126, width + 0.08, 0.074), frame, window, (x - 0.025, y, zz))

    for name, location, target, size_x, size_y, power, color, shadow in (
        ("Window daylight", (x - 0.22, y, z), (6.7, 0.1, 1.0), 3.55, 1.77, 1020, (0.87, 0.94, 1.0), True),
        ("Daylight room fill", (10.7, -2.4, 3.28), (4.4, 1.6, 0.85), 6.5, 4.0, 462, (0.93, 0.96, 1.0), False),
    ):
        light = bpy.data.lights.new(name, "AREA")
        light.shape = "RECTANGLE"
        light.size, light.size_y = size_x, size_y
        light.energy, light.color = power, color
        light.use_shadow = shadow
        light.specular_factor = 0.32 if shadow else 0
        obj = bpy.data.objects.new(name, light)
        window.objects.link(obj)
        obj.location = location
        look_at(obj, target)


def build_gym_right_equipment(parent):
    import equipment_kit as K
    import equipment_machines as M
    import equipment_machines2 as M2

    equipment = coll("Right Side Equipment", parent)

    def treadmill():
        machine = K.part("treadmill")
        K.box("Treadmill deck", machine, (0.82, 2.02, 0.13), "silver", (0, 0, 0.091))
        K.box("Running belt", machine, (0.57, 1.57, 0.021), "grip", (0, 0.13, 0.160))
        K.box("Motor cover", machine, (0.75, 0.36, 0.13), "silver", (0, -0.822, 0.170))
        for side in (-1, 1):
            x = side * 0.34
            K.box("Treadmill foot", machine, (0.12, 1.85, 0.038), "pad", (x, 0.015, 0.019))
            K.box("Treadmill side rail", machine, (0.11, 1.56, 0.045), "silver", (x, 0.135, 0.167))
            M.beam("Console upright", machine, (x, -0.83, 0.10), (x, -0.64, 1.17), 0.071, "silver")
            M.rod("Treadmill grip", machine, (x, -0.64, 1.05), (x, -0.20, 0.98), 0.031, "grip")
        K.box("Console housing", machine, (0.76, 0.32, 0.086), "silver", (0, -0.66, 1.181), (19, 0, 0))
        K.box("Console screen", machine, (0.31, 0.18, 0.015), "plate", (0, -0.674, 1.228), (19, 0, 0))
        K.box("Stop button", machine, (0.058, 0.040, 0.015), "red", (0, -0.541, 1.271), (19, 0, 0))
        return machine

    # Leave the far-right mirror clear for the Instagram photo spot.
    placements = (
        (treadmill, (11.95, -0.86, 0), 90),
        (treadmill, (11.95, 0.67, 0), 90),
        (M2.shoulder_press_machine, (5.99, 3.46, 0), 0),
        (M.chest_press_machine, (8.12, 3.46, 0), 0),
        (M2.seated_leg_curl, (10.02, 3.46, 0), 0),
        (M.leg_press_45, (7.50, -2.55, 0), -12),
    )
    return place_gym_equipment(equipment, placements)


def build_gym_extra_equipment(parent):
    import equipment_machines as M
    import equipment_machines2 as M2

    equipment = coll("Extra Gym Equipment", parent)
    return place_gym_equipment(equipment, (
        (M.smith_machine, (1.10, -2.30, 0), 8),
        (M.seated_cable_row, (-2.98, -2.88, 0), 90),
        (M.leg_extension, (9.70, -3.10, 0), -12),
        (M2.hip_abductor, (11.90, -3.10, 0), -90),
    ))


def place_gym_equipment(equipment, placements):
    kit = _kit_collection()
    roots = []
    for build, location, heading in placements:
        machine = build()
        machine.location = location
        machine.rotation_euler.z = math.radians(heading)
        for obj in (machine, *machine.children_recursive):
            link(obj, equipment)
        roots.append(machine)
    bpy.context.view_layer.update()
    for machine in roots:
        bottom = min((obj.matrix_world @ Vector(point)).z
                     for obj in machine.children_recursive if obj.type == "MESH" for point in obj.bound_box)
        machine.location.z -= bottom
    if not kit.all_objects:
        bpy.data.collections.remove(kit)
    return roots


def build_gym_set(c):
    """Dark industrial K-gym room: matte black walls/ceiling, yellow-black hazard stripe pillar, lime-green ceiling
    monkey-bar truss, twin warm ceiling strips and recessed downlights, glowing pink/blue neon sign, central mirror with
    white vinyl sticker texts (#오운완, #바디체크, #정리정돈_필수 #안하면_근손실), and red/black machines."""
    import importlib
    import equipment_kit as K
    import equipment_machines as M
    import equipment_machines2 as M2
    for mod in (K, M, M2):
        importlib.reload(mod)
    w = bpy.context.scene.world
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.04, 0.04, 0.05, 1)
    bg.inputs["Strength"].default_value = 0.20
    bpy.context.scene.view_settings.exposure = -0.15

    wall_m = mat("Gym_Wall", (0.016, 0.017, 0.022), rough=0.85)
    wain_m = mat("Gym_Wainscot", (0.010, 0.011, 0.014), rough=0.72)
    ceil_m = mat("Gym_Ceil", (0.012, 0.012, 0.015), rough=0.88)
    beam_m = mat("Gym_Beam", (0.025, 0.027, 0.032), rough=0.50, metal=0.45)
    lime_m = mat("Gym_LimeTruss", (0.36, 0.76, 0.12), rough=0.38, metal=0.20)
    haz_yel = mat("Gym_HazardYel", (0.95, 0.68, 0.04), rough=0.42)
    pipe_yel = mat("Gym_PipeYel", (0.88, 0.72, 0.18), rough=0.38, metal=0.30)
    wood_m = mat("Gym_Wood", (0.42, 0.26, 0.13), rough=0.55)
    mat_grn = mat("Gym_MatGreen", (0.04, 0.38, 0.20), rough=0.65)
    mirror_m = mat("Gym_Mirror", (0.78, 0.80, 0.84), rough=0.0, metal=1.0)
    sticker_m = shadeless("Gym_MirrorSticker", (0.96, 0.97, 0.99), strength=1.18)
    trim_m = mat("Gym_Trim", (0.012, 0.012, 0.015), rough=0.50, metal=0.30)
    red_m = mat("Gym_SportRed", (0.70, 0.035, 0.04), rough=0.35, metal=0.25)

    build_gym_floor(c)

    # Oak & rubber deadlift/rack platform under power rack (x=2.9, y=3.4)
    box("Platform_Base", (2.4, 2.3, 0.024), trim_m, c, (2.9, 3.4, 0.012))
    box("Platform_Wood", (1.1, 2.18, 0.024), wood_m, c, (2.9, 3.4, 0.020))
    box("Platform_Line", (2.36, 0.04, 0.024), haz_yel, c, (2.9, 2.27, 0.016))

    # 4 closed dark walls & lower wainscot
    box("Wall_Back", (9.2, 0.2, 3.65), wall_m, c, (0, 5.1, 1.80))
    box("Wall_Front", (9.2, 0.2, 3.65), wall_m, c, (0, -6.8, 1.80))
    box("Wall_Left", (0.2, 12.2, 3.65), wall_m, c, (-4.6, -0.8, 1.80))
    box("Wall_Right", (0.2, 12.2, 3.65), wall_m, c, (4.6, -0.8, 1.80))
    box("Wainscot_Back", (9.0, 0.03, 0.85), wain_m, c, (0, 4.99, 0.42))
    box("Wainscot_Front", (9.0, 0.03, 0.85), wain_m, c, (0, -6.69, 0.42))
    box("Wainscot_Left", (0.03, 11.8, 0.85), wain_m, c, (-4.49, -0.8, 0.42))
    box("Wainscot_Right", (0.03, 11.8, 0.85), wain_m, c, (4.49, -0.8, 0.42))
    build_gym_back_baseboard(c, trim_m)
    box("Baseboard_Left", (0.04, 11.8, 0.10), trim_m, c, (-4.485, -0.8, 0.05))

    # Yellow conduit pipe along upper walls (Photo 1 style)
    cyl("Pipe_Back", 0.055, 9.0, pipe_yel, c, (0, 4.92, 3.18), (0, 90, 0), seg=10)
    cyl("Pipe_Left", 0.055, 11.8, pipe_yel, c, (-4.42, -0.8, 3.18), (90, 0, 0), seg=10)

    # Full-length mirror with a dark frame and mullions. The lower edges sit just inside the floor.
    box("MirrorFrame", (6.2, 0.03, 2.514), trim_m, c, (0.3, 4.992, 1.253))
    box("Mirror", (6.08, 0.036, 2.464), mirror_m, c, (0.3, 4.980, 1.228))
    for mx in (-1.35, 0.25, 1.95):
        box("MirrorMullion", (0.022, 0.042, 2.484), trim_m, c, (mx, 4.976, 1.238))

    # Planar reflection probe on the mirror
    try:
        lp = bpy.data.lightprobes.new("MirrorProbe", "PLANE")
        lp_ob = bpy.data.objects.new("MirrorProbe", lp)
        c.objects.link(lp_ob)
        lp_ob.location = (0.3, 4.95, 1.228)
        lp_ob.rotation_euler = (math.radians(90), 0, 0)
        lp_ob.scale = (3.1, 1.25, 1.0)
    except Exception:
        pass

    # Ceiling + Lime-Green overhead monkey-bar / truss ladders (Photo 1 signature look)
    box("Ceiling", (9.4, 12.2, 0.12), ceil_m, c, (0, -0.8, 3.65))
    for y_beam in (-5.2, -3.0, -0.8, 1.4, 3.6):
        box("CeilBeam", (9.1, 0.14, 0.12), beam_m, c, (0, y_beam, 3.54))
    for lx in (-0.55, 1.65):  # two parallel lime-green overhead monkey-bar ladders running front-to-back
        for s in (-0.34, 0.34):
            box("TrussRail", (0.055, 10.6, 0.065), lime_m, c, (lx + s, -0.4, 3.08))
        for ry in [y * 0.65 - 4.8 for y in range(15)]:
            box("TrussRung", (0.68, 0.04, 0.04), lime_m, c, (lx, ry, 3.08))
        for hy in (-4.4, -2.0, 0.4, 2.8, 4.6):
            for s in (-0.34, 0.34):
                box("TrussHanger", (0.05, 0.05, 0.56), lime_m, c, (lx + s, hy, 3.34))
            box("TrussCross", (0.72, 0.045, 0.045), lime_m, c, (lx, hy, 3.32))

    build_gym_ceiling_lights(c)

    # Pillar with flush black and yellow diagonal hazard stripes
    px0, py0 = PILLAR[:2]
    box("Pillar", (0.45, 0.45, 3.62), wall_m, c, (px0, py0, 1.80))
    box("Pillar_Base", (0.48, 0.48, 0.10), trim_m, c, (px0, py0, 0.05))
    box("Pillar_Cap", (0.48, 0.48, 0.12), trim_m, c, (px0, py0, 3.54))
    for hz_i in range(6):
        z_hz = 0.28 + hz_i * 0.26
        _hazard_band("Pillar_Hazard", px0, py0, 0.462, 0.462, z_hz, 0.13, 0.11, haz_yel, c)

    # Back-wall hazard pilaster column on the left side of the mirror (-2.95, 4.92)
    box("WallCol_L", (0.42, 0.18, 3.62), wall_m, c, (-2.95, 4.94, 1.80))
    for hz_i in range(6):
        z_hz = 0.28 + hz_i * 0.26
        _hazard_band("WallCol_Hazard", -2.95, 4.94, 0.432, 0.192, z_hz, 0.13, 0.11, haz_yel, c)

    # Decorative collection for Neon Sign + Mirror Vinyl Stickers (linked to scene so they render, kept separate from structural QA)
    decc = coll("SET_DECOR", c)
    build_gym_neon(decc, c.objects["Mirror"])
    build_left_wall_neon(decc, c.objects["Wall_Left"])

    # 2) White Vinyl Sticker Texts on the Mirror (Photos 2, 3, 4 style)
    # Photo-zone corner brackets on upper-left mirror + #바디체크 / #오운완
    box("Sticker_FrameTop", (0.72, 0.006, 0.014), sticker_m, decc, (-0.72, 4.956, 2.38))
    box("Sticker_FrameBot", (0.72, 0.006, 0.014), sticker_m, decc, (-0.72, 4.956, 1.88))
    box("Sticker_FrameL",   (0.014, 0.006, 0.51), sticker_m, decc, (-1.07, 4.956, 2.13))
    box("Sticker_FrameR",   (0.014, 0.006, 0.51), sticker_m, decc, (-0.37, 4.956, 2.13))
    _wall_text("Sticker_BodyCheck", "#바디체크", (-0.72, 4.954, 2.22), 0.13, sticker_m, decc, align_x="CENTER", offset=0.0025)
    _wall_text("Sticker_Ounwan", "#오운완", (-0.82, 4.954, 1.18), 0.145, sticker_m, decc, align_x="CENTER", offset=0.0028)
    # Right side of mirror above the dumbbell rack: #정리정돈_필수 / #안하면_근손실
    _wall_text("Sticker_Clean1", "#정리정돈_필수", (1.32, 4.954, 1.56), 0.125, sticker_m, decc, align_x="LEFT", offset=0.0024)
    _wall_text("Sticker_Clean2", "#안하면_근손실", (1.32, 4.954, 1.38), 0.125, sticker_m, decc, align_x="LEFT", offset=0.0024)

    kit = _kit_collection()
    placed = {}

    def put(name, fn, loc, rz=0):
        p = fn()
        p.location = loc
        p.rotation_euler.z = math.radians(rz)
        for o in [p] + list(p.children_recursive):
            link(o, c)
        placed[name] = p
        return p

    put("power_rack", M.power_rack, (2.9, 3.4, 0))
    bb = put("barbell", K.barbell, (2.9, 3.4 - 0.62, 1.38))

    put("pec_deck", M.pec_deck, (-2.55, 3.95, 0), 0)
    put("lat_pulldown", M.lat_pulldown, (-3.7, 0.4, 0), -90)
    put("cable_crossover", M.cable_crossover, (-3.9, 3.4, 0), -90)
    put("flat_bench", M.flat_bench, (1.5, 1.3, 0), 90)
    put("adjustable_bench", M.adjustable_bench, (-0.95, 3.35, 0), 25)
    # Green exercise mat & standing black foam rollers near the pillar/mirror (Photo 1 bottom-right detail)
    box("GymMat_Pad", (0.55, 1.15, 0.035), mat_grn, c, (-1.85, 2.45, 0.018), (0, 0, -15))
    cyl("FoamRoller_1", 0.075, 0.62, trim_m, c, (-1.62, 1.88, 0.31), seg=12)
    cyl("FoamRoller_2", 0.075, 0.62, trim_m, c, (-1.45, 2.02, 0.31), seg=12)

    # Multi-tier dumbbell rack in front of the mirror loaded with yellow-ringed black dumbbells (Photo 2)
    shelf_m = K.mat("silver")
    rack = empty("P_dumbbell_rack", c, (0.45, 4.55, 0))
    for z in (0.45, 0.85):
        box("shelf", (2.5, 0.42, 0.04), shelf_m, c, (0, 0, z), (0, 0, 0), rack)
        box("shelf_lip", (2.52, 0.03, 0.06), red_m, c, (0, -0.20, z + 0.01), (0, 0, 0), rack)
    for x in (-1.18, 0.0, 1.18):
        box("leg", (0.07, 0.42, 0.9), shelf_m, c, (x, 0, 0.45), (0, 0, 0), rack)
    for row, z in enumerate((0.47, 0.87)):
        for i in range(6):
            d = K.dumbbell()
            d.parent = rack
            d.location = (-0.95 + i * 0.38, 0, z + 0.082)
            d.rotation_euler.z = math.radians(90)
            for o in [d] + list(d.children_recursive):
                link(o, c)
    placed["dumbbell_rack"] = rack

    # Plate tree with black & yellow-ringed plates
    tree = empty("P_plate_tree", c, (4.0, 1.6, 0))
    box("tree_base", (0.6, 0.6, 0.05), red_m, c, (0, 0, 0.025), (0, 0, 0), tree)
    box("tree_post", (0.08, 0.08, 1.5), red_m, c, (0, 0, 0.75), (0, 0, 0), tree)
    for i, (z, s) in enumerate([(0.30, 1), (0.30, -1), (0.80, 1), (0.80, -1), (1.30, 1)]):
        box("peg", (0.04, 0.25, 0.04), K.mat("steel"), c, (0, s * 0.12, z), (0, 0, 0), tree)
        for k in range(2 if i < 4 else 1):
            pl = M2.weight_plate()
            pl.parent = tree
            pl.rotation_euler.z = math.radians(90)
            pl.location = (0, s * (0.08 + k * 0.085), z - 0.225)
            for o in [pl] + list(pl.children_recursive):
                link(o, c)
    placed["plate_tree"] = tree
    # QA fixes on the copied builders: plate ring was 1 mm off the plate face (z-fighting) -> thicken the ring;
    # power-rack 'hole' decals float 1 mm off the posts -> drop them
    for o in list(c.all_objects):
        par = o.parent.name if o.parent else ""
        if o.type == "MESH" and par.startswith("P_weight_plate"):
            if o.name.startswith("ring"):
                o.scale.z = 1.25   # 0.056 -> 0.070: clear of the face (0.058) and plate (0.05)
            elif o.name.startswith("hub"):
                o.scale.z = 1.3    # 0.060 -> 0.078: clear of the ring caps
        if o.type == "MESH" and par.startswith("P_barbell"):
            if o.name.startswith("bar"):
                o.scale.z = 0.985  # bar ends sat flush with the end caps
            elif o.name.startswith("endcap"):
                o.location.x += 0.004 if o.location.x > 0 else -0.004  # sleeve end was flush with the cap
            elif o.name.startswith("collar"):
                o.location.x += 0.006 if o.location.x > 0 else -0.006  # collar face was flush with the sleeve end
        if o.type == "MESH" and o.name.startswith("low_pulley") and par.startswith("P_cable_crossover"):
            o.scale.z = 1.2        # pulley sides were flush with the slot plate
        if o.type == "MESH" and o.name.startswith("hole") and o.parent and o.parent.name.startswith("P_power_rack"):
            bpy.data.objects.remove(o, do_unlink=True)
    # remaining coplanar joints inside the machine builders: grow the smaller part of each pair by 4 mm a side
    # (list written by tools/build_assets.py gymqa -> scenes/gym_zfix.json, deterministic object names)
    zfix = os.path.join(ROOT, "scenes", "gym_zfix.json")
    if os.path.exists(zfix):
        with open(zfix) as f:
            grow = json.load(f)
        bpy.context.view_layer.update()
        for n, mm in grow.items():  # {object name: metres added per side}
            o = bpy.data.objects.get(n)
            if o and o.type == "MESH":
                d = o.dimensions
                o.scale = [sc * (dd + 2 * mm) / dd if dd > 1e-4 else sc for sc, dd in zip(o.scale, (d.x, d.y, d.z))]
    # remove the now-empty Kit collection
    if not kit.all_objects:
        bpy.data.collections.remove(kit)
    extend_gym_right(c)
    add_symmetric_gym_pillars(c)
    build_gym_instagram_stickers(decc)
    build_gym_daylight_window(decc, c.objects["Wall_Right"])
    build_gym_right_equipment(c)
    build_gym_extra_equipment(c)
    return placed


def new_scene(kind="flat", bg="yellow", preview=False):
    """Fresh file with the fixed look. kind: 'flat' | 'gym'."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "Reel"
    if not sc.world:
        sc.world = bpy.data.worlds.new("World")
    render_settings(sc, preview)
    sc.frame_start, sc.frame_end = 1, 300
    setc = coll("SET")
    rigc = coll("LOOK")  # lights + cameras: never move these, that's the fixed look
    fixed_lights(rigc, kind)
    fixed_cameras(rigc, kind)
    coll("CAST")
    coll("CAMEO")
    coll("PROPS")
    coll("FX")
    if kind == "gym":
        build_gym_set(setc)
        add_gym_light_glow(sc)
    else:
        build_flat_set(setc, bg)
    set_keyed_interp("CONSTANT")
    return sc


# ------------------------------------------------------------------ cast

def _append_objects(path, names):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in names]
    return [o for o in dst.objects if o]


def apply_hero_viewer_material(body, hero_name):
    # The phone viewer's Lambert body color is #63d6de in sRGB.
    # Blender's shader sockets expect linear RGB.
    color = tuple(((channel / 255 + 0.055) / 1.055) ** 2.4 for channel in (0x63, 0xD6, 0xDE))
    material = mat(hero_name + "_ViewerBody", color, emit=0.22, rough=1.0)
    shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Specular IOR Level"].default_value = 0
    body.data.materials.clear()
    body.data.materials.append(material)
    for polygon in body.data.polygons:
        polygon.material_index = 0


def add_hero(name="Guy", loc=(0, 0, 0), face_deg=0.0):
    """V5 guy with the watch on the left wrist. Faceless. Returns the armature."""
    c = coll("CAST")
    objs = _append_objects(HERO_SRC, {"V5_CommonRig", "V5_Body", "LowPolyWatch", "Watch_Buckle", "Watch_ButtonA",
                                      "Watch_ButtonB", "Watch_Case", "Watch_Display", "Watch_Strap"})
    arm = next(o for o in objs if o.type == "ARMATURE")
    body = next(o for o in objs if o.name.startswith("V5_Body"))
    for o in objs:
        link(o, c)
    arm.name = name
    body.name = name + "_Body"
    body.data = body.data.copy()
    for polygon in body.data.polygons:
        polygon.use_smooth = False
    apply_hero_viewer_material(body, name)
    # the buckle sat exactly on the strap (z-fighting, found by asset QA);
    # it sits under the wrist and never reads on camera, so it is simply dropped
    bk = next((o for o in objs if o.name.startswith("Watch_Buckle")), None)
    if bk:
        objs.remove(bk)
        bpy.data.objects.remove(bk, do_unlink=True)
    # watch screen: make it emissive + keyable (Watch_Glow strength)
    disp = next((o for o in objs if o.name.startswith("Watch_Display")), None)
    if disp:
        disp.data = disp.data.copy()
        sm = mat(name + "_WatchScreen", (0.20, 0.95, 0.70), emit=0.0, rough=0.3)
        disp.data.materials.clear()
        disp.data.materials.append(sm)
    arm.location = loc
    arm.rotation_euler.z = math.radians(face_deg)
    arm["wc_kind"] = "hero"
    return arm


def add_extra(role="red", name=None, loc=(0, 0, 0), face_deg=0.0, height=1.0, girth=1.0):
    """The ORIGINAL low-poly man (figure.blend 'BASE_Low Poly Man' + Fig.rig, copied) covered in ONE flat colour per role.
    Same 52-bone rig as the hero, so every pose in the library works on him. Returns the armature."""
    c = coll("CAST")
    r = ROLES[role]
    name = name or ("Extra_" + role)
    objs = _append_objects(EXTRA_SRC, {"Fig.rig", "BASE_Low Poly Man"})
    arm = next(o for o in objs if o.type == "ARMATURE")
    body = next(o for o in objs if o.type == "MESH")
    for o in objs:
        link(o, c)
    arm.name = name
    body.name = name + "_Body"
    body.data = body.data.copy()
    me = body.data
    me.materials.clear()
    me.materials.append(mat(name + "_Color", r["color"], rough=0.7))
    for p in me.polygons:
        p.material_index = 0
    arm.location = loc
    arm.rotation_euler.z = math.radians(face_deg)
    arm.scale = (girth, girth, height)
    arm["wc_kind"] = "extra"
    arm["wc_role"] = role
    return arm


# ------------------------------------------------------------------ poses

_LIB = None


def pose_lib(reload=False):
    global _LIB
    if _LIB is None or reload:
        with open(POSE_LIB) as f:
            _LIB = json.load(f)
    return _LIB


def rest(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.matrix_basis = Matrix.Identity(4)


def apply_pose(arm, pose_name):
    """Set a library pose (local transforms per bone, identical rest on hero and extras)."""
    lib = pose_lib()
    data = lib["poses"][pose_name]["bones"]
    rest(arm)
    for bn, (loc, q) in data.items():
        pb = arm.pose.bones.get(bn)
        if pb:
            pb.location = loc
            pb.rotation_quaternion = q
    # extras may be scaled: keep feet on the floor
    if abs(arm.scale.z - 1) > 1e-3 and lib["poses"][pose_name].get("grounded", True):
        pass  # pelvis offset is local to the armature, so scaled rigs stay grounded automatically
    bpy.context.view_layer.update()


def key_pose(arm, pose_name, frame):
    apply_pose(arm, pose_name)
    for pb in arm.pose.bones:
        pb.keyframe_insert("location", frame=frame)
        pb.keyframe_insert("rotation_quaternion", frame=frame)


def key_transform(ob, frame, loc=None, rot_deg=None, scale=None):
    if loc is not None:
        ob.location = loc
        ob.keyframe_insert("location", frame=frame)
    if rot_deg is not None:
        ob.rotation_euler = [math.radians(a) for a in rot_deg]
        ob.keyframe_insert("rotation_euler", frame=frame)
    if scale is not None:
        ob.scale = scale if hasattr(scale, "__len__") else (scale,) * 3
        ob.keyframe_insert("scale", frame=frame)


# ------------------------------------------------------------------ cameo boards

CAMEOS = {
    "samsung": ("samsung_portrait_original.webp", 1.0, "photo"),  # original portrait ratio (700x1078)
    "altman": ("altman_square.png", 1.0, "photo"),
    "amodei": ("amodei_square.png", 1.0, "photo"),
    "gpt": ("gpt_logo_filled.png", 1.0, "logo"),
    "claude": ("claude_logo.png", 1.0, "logo"),
    "gemini": ("gemini_logo.png", 1.0, "logo"),
}


def add_cameo(who, loc=(0, 0, 2.0), size=None, face_deg=0.0, name=None):
    """A big floating photo / logo plane (no stick, no frame border), in the image's own aspect ratio.
    Default size: photos 1.0 m, logos 0.75 m. Origin = board centre. Board faces -Y (towards Cam_Front)."""
    c = coll("CAMEO")
    fn, aspect, kind = CAMEOS[who]
    size = size or (1.0 if kind == "photo" else 0.75)  # = board HEIGHT; width follows the image's own ratio
    img = os.path.join(PARTS, fn)
    im = bpy.data.images.load(img, check_existing=True)
    ratio = im.size[0] / im.size[1] if im.size[1] else 1.0
    m = shadeless("Cameo_" + who, image=img, strength=1.0)
    m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    try:
        m.surface_render_method = "BLENDED" if kind == "logo" else "DITHERED"
    except AttributeError:
        pass
    bm = bmesh.new()
    s = size / 2
    sx = s * ratio
    vs = [bm.verts.new(v) for v in [(-sx, 0, -s), (sx, 0, -s), (sx, 0, s), (-sx, 0, s)]]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    for l, (u, v) in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        l[uv].uv = (u, v)
    root = empty(name or ("Cameo_" + who), c, loc, size=0.15)
    root.rotation_euler.z = math.radians(face_deg)
    face = mesh_obj((name or ("Cameo_" + who)) + "_Face", bm, m, c, (0, 0, 0), parent=root)
    # no frame border (경민 2026-11-18): the photo itself floats
    root["wc_cameo"] = who
    return root


def cameo_float(root, start, end, amp=0.07, period=48, sway_deg=4):
    """Idle floating: slow up/down bob + slight sway on delta transforms (does not fight entrance keys)."""
    f, i = start, 0
    while f <= end:
        root.delta_location = (0, 0, amp if i % 2 == 0 else -amp)
        root.keyframe_insert("delta_location", frame=f)
        root.delta_rotation_euler = (0, math.radians(sway_deg if i % 2 == 0 else -sway_deg), 0)
        root.keyframe_insert("delta_rotation_euler", frame=f)
        f += period // 2
        i += 1
    root["wc_interp"] = root.get("wc_interp", "BEZIER")


def cameo_move(root, move, start, dur=None, at=None, side=-1):
    """Keyed entrances (interpolation follows set_keyed_interp, LINEAR is nice for slides):
       peek     : slides out from behind the gym pillar / frame edge, stops, stares (samsung)
       pass     : slides across the frame and leaves (altman)
       approach : comes slowly straight at the camera (amodei)
       pop      : appears with a tiny scale pop (logos)"""
    at = Vector(at or root.location)
    if move == "peek":  # slides in from the frame edge on `side` (-1 = screen left), stops half-in / in
        dur = dur or 18
        hid = at + Vector((side * 1.4, 0.0, 0))
        key_transform(root, start, loc=hid)
        key_transform(root, start + dur, loc=at)
    elif move == "pass":
        dur = dur or 45
        key_transform(root, start, loc=at + Vector((side * 3.2, 0, 0)))
        key_transform(root, start + dur, loc=at + Vector((-side * 3.2, 0, 0)))
    elif move == "approach":
        dur = dur or 90
        key_transform(root, start, loc=at + Vector((0, 3.5, 0)))
        key_transform(root, start + dur, loc=at)
    elif move == "pop":
        dur = dur or 6
        key_transform(root, start - 1, scale=0.001)
        key_transform(root, start, scale=1.25)
        key_transform(root, start + dur, scale=1.0)
    return root


def hide_until(ob, frame, until_end=None):
    """Hide object (and children) before `frame` (and after `until_end`)."""
    for o in [ob] + list(ob.children_recursive):
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=1)
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=frame)
        if until_end:
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=until_end)
        for fc in _fcurves(o):
            for k in fc.keyframe_points:
                k.interpolation = "CONSTANT"


def _fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        return list(cb.fcurves) if cb else []
    except Exception:
        out = []
        for layer in act.layers:
            for st in layer.strips:
                for cb in st.channelbags:
                    out.extend(cb.fcurves)
        return out


# ------------------------------------------------------------------ fx

def _text(name, body, size, color, c, font=None, extrude=0.02):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = extrude
    if font:
        cu.font = load_font(font)
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(shadeless("FX_" + name.split(".")[0] + "_m", color))
    c.objects.link(ob)
    return ob


def _billboard(ob):
    cn = ob.constraints.new("TRACK_TO")
    cn.target = bpy.context.scene.camera
    cn.track_axis = "TRACK_Z"
    cn.up_axis = "UP_Y"


def fx_symbol(kind, char_arm, frame, dur=12, offset=(0.16, 0.0, 0.22)):
    """Comic symbol over a character's head: 'exclaim' (!), 'question' (?), 'sweat' (drop), 'anger' (#), 'dots' (...).
    Call after the character's poses are keyed: it reads the head position at `frame`."""
    c = coll("FX")
    sc = bpy.context.scene
    sc.frame_set(frame)
    head = char_arm.matrix_world @ char_arm.pose.bones["head"].tail
    if kind == "sweat":
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.06)
        for v in bm.verts:
            if v.co.z > 0:
                k = max(0.0, 1 - v.co.z / 0.06)
                v.co.x *= k
                v.co.y *= k
                v.co.z *= 2.2
        ob = mesh_obj("FX_sweat", bm, shadeless("FX_sweat_m", (0.45, 0.75, 1.0)), c)
        offset = (0.17, 0.0, 0.0)
    else:
        body = {"exclaim": "!", "question": "?", "anger": "#", "dots": "..."}[kind]
        color = {"exclaim": (1.0, 0.15, 0.1), "question": (1.0, 0.85, 0.1), "anger": (1.0, 0.1, 0.1), "dots": (0.1, 0.1, 0.1)}[kind]
        ob = _text("FX_" + kind, body, 0.5, color, c, extrude=0.03)
        ob.data.font = load_font(KFONT)
        _billboard(ob)
    ob.location = head + Vector(offset)
    hide_until(ob, frame, frame + dur)
    key_transform(ob, frame, scale=1.35)
    key_transform(ob, frame + 2, scale=1.0)
    if kind == "sweat":  # slides down a bit, stop-motion
        for k in range(0, dur, 3):
            key_transform(ob, frame + k, loc=head + Vector(offset) - Vector((0, 0, 0.02 * k / 3)))
    return ob


def fx_cam_overlay(cam, name, ob):
    """Parent an overlay object to the camera at the near plane."""
    ob.parent = cam
    ob.location = (0, 0, -0.5)
    ob.rotation_euler = (0, 0, 0)
    return ob


def _overlay_plane(name, cam, material, w=None):
    c = coll("FX")
    cd = cam.data
    # plane that exactly fills the frame at distance d
    d = 0.5
    sensor = cd.sensor_width
    fov = 2 * math.atan(sensor / 2 / cd.lens)  # AUTO fit: sensor spans the longer (vertical) side
    h = 2 * d * math.tan(fov / 2) * 1.05
    wdt = h * 9 / 16
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in [(-wdt / 2, -h / 2, 0), (wdt / 2, -h / 2, 0), (wdt / 2, h / 2, 0), (-wdt / 2, h / 2, 0)]]
    bm.faces.new(vs)
    ob = mesh_obj(name, bm, material, c)
    ob.parent = cam
    ob.location = (0, 0, -d)
    return ob, wdt, h, d


def fx_flash(cam, frame, color=(1, 1, 1), frames=2):
    """1-2 frame solid colour impact frame (full screen)."""
    ob, *_ = _overlay_plane("FX_Flash", cam, shadeless("FX_flash_%d%d%d" % tuple(int(x * 9) for x in color), color))
    hide_until(ob, frame, frame + frames)
    return ob


def fx_speedlines(cam, frame, dur=12, count=40, color=(1, 1, 1), radial=True):
    """Manga focus lines: thin wedges from the frame edge toward the centre, on a camera overlay."""
    c = coll("FX")
    _, wdt, h, d = _overlay_plane("FX_tmp", cam, None)
    bpy.data.objects.remove(bpy.data.objects["FX_tmp"], do_unlink=True)
    bm = bmesh.new()
    rnd = random.Random(7)
    R = math.hypot(wdt, h) * 0.6
    for i in range(count):
        a = 2 * math.pi * i / count + rnd.uniform(-0.05, 0.05)
        r0 = R * rnd.uniform(0.45, 0.62)
        wd = rnd.uniform(0.006, 0.016) * d * 2
        p0 = Vector((math.cos(a) * r0, math.sin(a) * r0, 0))
        p1 = Vector((math.cos(a) * R, math.sin(a) * R, 0))
        n = Vector((-math.sin(a), math.cos(a), 0)) * wd
        vs = [bm.verts.new(p) for p in (p0, p1 + n, p1 - n)]
        bm.faces.new(vs)
    ob = mesh_obj("FX_SpeedLines", bm, shadeless("FX_speed_m", color), c)
    ob.parent = cam
    ob.location = (0, 0, -d * 0.99)
    hide_until(ob, frame, frame + dur)
    # jitter the lines every 2 frames (rotation), stop-motion style
    for k in range(0, dur, 2):
        key_transform(ob, frame + k, rot_deg=(0, 0, rnd.uniform(-4, 4)))
    return ob


def fx_zoom_punch(cam, frame, frames=4, factor=1.6):
    """Snap zoom in for a few frames (shock cut), then back."""
    base = cam.data.lens
    cam.data.lens = base
    cam.data.keyframe_insert("lens", frame=frame - 1)
    cam.data.lens = base * factor
    cam.data.keyframe_insert("lens", frame=frame)
    cam.data.lens = base
    cam.data.keyframe_insert("lens", frame=frame + frames)


def fx_shake(cam, frame, dur=10, amp=0.06, seed=3):
    """Camera shake: random jumps of the camera's shake parent every frame (constant keys)."""
    rig = cam.parent
    rnd = random.Random(seed + frame)
    for k in range(dur):
        fall = 1 - k / dur
        rig.location = (rnd.uniform(-amp, amp) * fall, 0, rnd.uniform(-amp, amp) * fall)
        rig.keyframe_insert("location", frame=frame + k)
    rig.location = (0, 0, 0)
    rig.keyframe_insert("location", frame=frame + dur)


def fx_caption(cam, text, frame, dur, y=-0.33, size=0.032, color=(1, 1, 1)):
    """Subtitle line in Korean at the lower part of the frame (camera overlay), with a black outline plate."""
    c = coll("FX")
    _, wdt, h, d = _overlay_plane("FX_tmp", cam, None)
    bpy.data.objects.remove(bpy.data.objects["FX_tmp"], do_unlink=True)
    # size relative to the frame height (same look on every lens); shrink long lines to fit the width
    if len(text) > 13 and "\n" not in text and " " in text:  # long line -> two lines, split at the space nearest the middle
        sp = min((i for i, ch in enumerate(text) if ch == " "), key=lambda i: abs(i - len(text) / 2))
        text = text[:sp] + "\n" + text[sp + 1:]
    longest = max(len(l) for l in text.split("\n"))
    px = min(0.058 * h, 0.9 * wdt / max(1, longest * 0.95))
    ob = _text("FX_Caption", text, px, color, c, font=KFONT, extrude=0)
    ob.parent = cam
    ob.location = (0, y * h, -d * 0.98)
    bg = bpy.data.curves.new("cap_bg", "FONT")
    sh = ob.copy()
    sh.data = ob.data.copy()
    sh.data.materials.clear()
    sh.data.materials.append(shadeless("FX_capshadow_m", (0, 0, 0)))
    sh.data.offset = 0.0
    sh.data.extrude = 0
    try:
        sh.data.offset = px * 0.03
    except Exception:
        pass
    sh.location = (px * 0.06, y * h - px * 0.06, -d * 0.985)
    c.objects.link(sh)
    bpy.data.curves.remove(bg)
    hide_until(ob, frame, frame + dur)
    hide_until(sh, frame, frame + dur)
    return ob


# ------------------------------------------------------------------ watch coach

def watch_parts(hero_arm):
    return [o for o in bpy.data.objects if o.name.startswith("Watch_") and o.parent and
            (o.parent.name.startswith("LowPolyWatch"))]


def watch_glow(hero_name, frame, on=True, strength=4.0):
    m = bpy.data.materials[hero_name + "_WatchScreen"]
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Emission Strength"].default_value = strength if on else 0.0
    b.inputs["Emission Strength"].keyframe_insert("default_value", frame=frame)


def watch_buzz(frame, dur=12, amp_deg=8):
    """Vibration: the watch root jitters in rotation every frame + buzz arcs appear next to it."""
    w = next(o for o in bpy.data.objects if o.name.startswith("LowPolyWatch"))
    rnd = random.Random(frame)
    base = w.rotation_euler.copy()
    for k in range(dur):
        w.delta_rotation_euler = (0, 0, math.radians(rnd.choice((-1, 1)) * amp_deg))
        w.keyframe_insert("delta_rotation_euler", frame=frame + k)
    w.delta_rotation_euler = (0, 0, 0)
    w.keyframe_insert("delta_rotation_euler", frame=frame + dur)
    c = coll("FX")
    arcs = []
    for s in (-1, 1):
        bm = bmesh.new()
        for i in range(3):
            r = 0.05 + i * 0.03
            pts = []
            for j in range(6):
                a = math.radians(-35 + 70 * j / 5)
                pts.append(bm.verts.new((s * r * math.cos(a), 0, r * math.sin(a))))
                pts.append(bm.verts.new((s * (r + 0.008) * math.cos(a), 0, (r + 0.008) * math.sin(a))))
            for j in range(5):
                bm.faces.new((pts[2 * j], pts[2 * j + 2], pts[2 * j + 3], pts[2 * j + 1]))
        ob = mesh_obj("FX_Buzz", bm, shadeless("FX_buzz_m", (1, 1, 1)), c)
        cn = ob.constraints.new("COPY_LOCATION")
        cn.target = w
        _billboard(ob)
        hide_until(ob, frame, frame + dur)
        arcs.append(ob)
    return arcs


# ------------------------------------------------------------------ props

def prop(kind, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, bone=None, name=None):
    """Small meme props. If `parent` (armature) + `bone` are given, the prop follows that bone (e.g. hand_r)."""
    c = coll("PROPS")
    root = empty(name or ("PR_" + kind), c, (0, 0, 0), size=0.05)
    if kind == "plate":
        cyl("plate", 0.225, 0.05, mat("PR_plate_m", (0.09, 0.09, 0.10)), c, (0, 0, 0), (0, 90, 0), 14, parent=root)
        cyl("ring", 0.15, 0.056, mat("PR_accent_m", (0.30, 0.78, 0.62)), c, (0, 0, 0), (0, 90, 0), 14, parent=root)
        cyl("hub", 0.05, 0.06, mat("PR_steel_m", (0.6, 0.6, 0.62), metal=0.6, rough=0.4), c, (0, 0, 0), (0, 90, 0), 8, parent=root)
    elif kind == "phone":
        box("phone", (0.075, 0.009, 0.155), mat("PR_phone_m", (0.05, 0.05, 0.06), rough=0.3), c, parent=root)
        box("screen", (0.068, 0.002, 0.145), mat("PR_screen_m", (0.55, 0.75, 1.0), emit=2.5), c, (0, -0.0052, 0), parent=root)
    elif kind == "towel":
        # folded towel lying on a bench: one bent strip, accent band at both ends (material per face, no extra parts)
        bm = bmesh.new()
        prof = [(-0.30, 0.0), (-0.24, 0.0), (-0.12, 0.0), (-0.06, 0.03), (0.06, 0.03), (0.12, 0.0), (0.24, 0.0), (0.30, 0.0)]
        rows = [[bm.verts.new((x, y, z)) for x in (-0.22, 0.0, 0.22)] for (y, z) in prof]
        for i, (a_, b_) in enumerate(zip(rows, rows[1:])):
            for j in range(2):
                f = bm.faces.new((a_[j], a_[j + 1], b_[j + 1], b_[j]))
                f.material_index = 1 if i in (0, len(rows) - 2) else 0
        ob = mesh_obj("towel", bm, mat("PR_towel_m", (0.95, 0.95, 0.92), rough=1.0), c, parent=root)
        ob.data.materials.append(mat("PR_accent_m", (0.30, 0.78, 0.62)))
        sm = ob.modifiers.new("thick", "SOLIDIFY")
        sm.thickness = 0.014
        sm.offset = 1.0
    elif kind == "shaker":
        cyl("cup", 0.045, 0.16, mat("PR_shaker_m", (0.95, 0.95, 0.97), rough=0.3), c, (0, 0, 0.08), seg=10, r2=0.052, parent=root)
        cyl("lid", 0.055, 0.035, mat("PR_shakerlid_m", (0.30, 0.78, 0.62)), c, (0, 0, 0.177), seg=10, parent=root)
        cyl("spout", 0.015, 0.03, mat("PR_shakerlid_m", (0.30, 0.78, 0.62)), c, (0.02, 0, 0.205), seg=6, parent=root)
    elif kind == "bottle":
        cyl("body", 0.035, 0.2, mat("PR_bottle_m", (0.2, 0.45, 0.85), rough=0.2), c, (0, 0, 0.1), seg=8, parent=root)
        cyl("cap", 0.02, 0.04, mat("PR_black_m", (0.05, 0.05, 0.05)), c, (0, 0, 0.22), seg=8, parent=root)
    elif kind == "gym_bag":
        box("bag", (0.55, 0.28, 0.28), mat("PR_bag_m", (0.15, 0.18, 0.40), rough=0.9), c, (0, 0, 0.14), parent=root)
        box("band", (0.56, 0.29, 0.05), mat("PR_black_m", (0.05, 0.05, 0.05)), c, (0, 0, 0.18), parent=root)
        for s in (-1, 1):
            box("handle", (0.03, 0.03, 0.14), mat("PR_black_m", (0.05, 0.05, 0.05)), c, (s * 0.12, 0, 0.33), parent=root)
        box("handle_top", (0.30, 0.036, 0.03), mat("PR_black_m", (0.05, 0.05, 0.05)), c, (0, 0, 0.4), parent=root)
    elif kind == "wall_clock":
        cyl("rim", 0.26, 0.05, mat("PR_black_m", (0.05, 0.05, 0.05)), c, (0, 0, 0), (90, 0, 0), 16, parent=root)
        cyl("face", 0.235, 0.05, mat("PR_clockface_m", (0.97, 0.97, 0.95)), c, (0, -0.006, 0), (90, 0, 0), 16, parent=root)
        hm = empty("PR_clock_hour", c, (0, -0.032, 0), parent=root, size=0.05)
        mm = empty("PR_clock_minute", c, (0, -0.037, 0), parent=root, size=0.05)
        box("hand_h", (0.018, 0.006, 0.13), mat("PR_black_m", (0.05, 0.05, 0.05)), c, (0, 0, 0.055), parent=hm)
        box("hand_m", (0.012, 0.006, 0.21), mat("PR_red_m", (0.8, 0.1, 0.1)), c, (0, 0, 0.085), parent=mm)
    else:
        raise ValueError(kind)
    root.location = loc
    root.rotation_euler = [math.radians(a) for a in rot]
    if parent is not None and bone:
        cn = root.constraints.new("CHILD_OF")
        cn.target = parent
        cn.subtarget = bone
        cn.inverse_matrix = Matrix.Identity(4)
    elif parent is not None:
        root.parent = parent
    return root


def clock_spin(clock_root, frame, dur=30, turns=2):
    """Fast-forwarding wall clock (휴식 10분 joke): minute hand spins `turns` times in stop-motion steps."""
    mm = next(o for o in clock_root.children if o.name.startswith("PR_clock_minute"))
    hm = next(o for o in clock_root.children if o.name.startswith("PR_clock_hour"))
    steps = max(2, dur // 2)
    for i in range(steps + 1):
        f = frame + int(i * dur / steps)
        a = -360 * turns * i / steps
        key_transform(mm, f, rot_deg=(0, a, 0))
        key_transform(hm, f, rot_deg=(0, a / 12, 0))


# ------------------------------------------------------------------ render

def render_still(path, frame=1):
    sc = bpy.context.scene
    sc.frame_set(frame)
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def set_video_output(path):
    sc = bpy.context.scene
    im = sc.render.image_settings
    try:
        im.media_type = "VIDEO"
    except (AttributeError, TypeError):
        pass
    im.file_format = "FFMPEG"
    ff = sc.render.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    ff.constant_rate_factor = "HIGH"
    try:
        ff.audio_codec = "AAC"
    except TypeError:
        pass
    sc.render.filepath = path


def save(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    return path
