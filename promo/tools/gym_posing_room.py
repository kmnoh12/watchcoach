"""WatchCoach Gym Expansion Phase 2: Posing Room interior (Korean gym posing-room layout).

Sits outside the main gym front wall (Wall_Front, y = -6.69 .. -6.91) behind the Phase 1 posing-room door
(gym_annex.build_gym_doors: x = -1.45, 0.95 m wide, 2.18 m high).
Interior volume: x -3.30 .. +0.40, y -6.90 .. -10.50, floor z = 0, ceiling z = 3.20.

Layout (posing axis runs along X, so the door sits on the poser's side wall):
  x = -3.30  "mirror wall": floor-to-ceiling, wall-to-wall mirror the poser faces
  x = +0.40  "feature wall": long mirror high up, tilted down (shows the poser's back in the big mirror),
             red heavy-type gym slogan under it, black ledge at the bottom for bottles and towels
  centre     the hero's selfie tripod + Galaxy S25 Ultra, aimed at the posing spot
  ceiling    black, hard top-down spots over the posing spot + small recessed downlights
"""
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

import wc_lib as W

X0, X1 = -3.30, 0.40          # inner faces: mirror wall (X0) / feature wall (X1)
Y_FRONT, Y_BACK = -6.90, -10.50
H = 3.20
DOOR_X, DOOR_H = -1.45, 2.18
OPEN_HALF = 0.455              # Phase 1 boolean cutter is 0.91 m wide
CX, CY = (X0 + X1) / 2, (Y_FRONT + Y_BACK) / 2
POSE_SPOT = Vector((-0.50, CY, 0.0))   # where the poser stands, ~0.9 m off the feature wall
RED = (0.62, 0.012, 0.010)

HEAVY_FONTS = (
    r"C:\Windows\Fonts\impact.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/Library/Fonts/Impact.ttf",
    r"C:\Windows\Fonts\ariblk.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
)


def _heavy_font():
    return next((p for p in HEAVY_FONTS if os.path.exists(p)), W.KFONT)


def _bevel(ob, width=0.004, segments=2):
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    return ob


def _text(c, name, body, xyz, size, material, rot_deg, font, spacing=1.0, shear=0.0, extrude=0.006, parent=None):
    data = bpy.data.curves.new(name, "FONT")
    data.body = body
    data.font = W.load_font(font)
    data.size = size
    data.space_character = spacing
    data.shear = shear
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.extrude = extrude
    data.materials.append(material)
    ob = bpy.data.objects.new(name, data)
    ob.location = xyz
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    ob.parent = parent
    c.objects.link(ob)
    return ob


def _area(c, name, loc, size, energy, color, rot_deg, size_y=None, shadow=True, specular=1.0):
    """specular=0 for hidden coves/fills: otherwise EEVEE shows the emitter as a bright panel in every mirror."""
    li = bpy.data.lights.new(name, "AREA")
    li.specular_factor = specular
    li.shape = "RECTANGLE"
    li.size = size
    li.size_y = size_y if size_y is not None else size
    li.energy = energy
    li.color = color
    li.use_shadow = shadow
    ob = bpy.data.objects.new(name, li)
    ob.visible_glossy = specular > 0  # Cycles equivalent of hiding the emitter from mirrors
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    c.objects.link(ob)
    return ob


def _spot(c, name, loc, target, energy, size_deg, blend, color=(1.0, 0.93, 0.84), soft=0.02, shadow=True):
    li = bpy.data.lights.new(name, "SPOT")
    li.energy = energy
    li.color = color
    li.spot_size = math.radians(size_deg)
    li.spot_blend = blend
    li.shadow_soft_size = soft
    li.use_shadow = shadow
    try:
        li.use_shadow_jitter = True
    except AttributeError:
        pass
    ob = bpy.data.objects.new(name, li)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    c.objects.link(ob)
    return ob


def _floor_material():
    """Dark charcoal polished concrete with faint mottling, satin sheen for the spot pools."""
    m = bpy.data.materials.get("Posing_DarkConcrete")
    if m:
        return m
    m = bpy.data.materials.new("Posing_DarkConcrete")
    m.diffuse_color = (0.03, 0.03, 0.032, 1)
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    coord = nodes.new("ShaderNodeTexCoord")
    mottle = nodes.new("ShaderNodeTexNoise")
    mottle.inputs["Scale"].default_value = 1.6
    mottle.inputs["Detail"].default_value = 6.0
    mottle.inputs["Roughness"].default_value = 0.62
    links.new(coord.outputs["Object"], mottle.inputs["Vector"])
    speck = nodes.new("ShaderNodeTexNoise")
    speck.inputs["Scale"].default_value = 140.0
    speck.inputs["Detail"].default_value = 2.0
    links.new(coord.outputs["Object"], speck.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.020, 0.020, 0.022, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.050, 0.050, 0.054, 1)
    links.new(mottle.outputs["Fac"], ramp.inputs["Fac"])
    mix = nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "OVERLAY"
    mix.inputs[0].default_value = 0.25
    links.new(ramp.outputs["Color"], mix.inputs[1])
    links.new(speck.outputs["Color"], mix.inputs[2])
    links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    rough = nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.22
    rough.inputs["To Max"].default_value = 0.45
    links.new(mottle.outputs["Fac"], rough.inputs["Value"])
    links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    return m


def _architecture(c):
    wall_m = W.mat("Posing_WallBlack", (0.016, 0.016, 0.018), rough=0.90)
    ceil_m = W.mat("Posing_CeilingBlack", (0.008, 0.008, 0.009), rough=0.92)
    base_m = W.mat("Posing_Baseboard", (0.006, 0.006, 0.007), rough=0.40, metal=0.35)
    case_m = W.mat("RoomDoorFrame_Charcoal", (0.022, 0.024, 0.028), rough=0.40, metal=0.55)

    t = 0.12
    width, depth = X1 - X0, Y_FRONT - Y_BACK
    # Envelope runs 0.11 m into the main Wall_Front (y -6.69 .. -6.91) and the ceiling slab is thick,
    # so no seam is left for gym light to leak through in low-res reflection shadow maps.
    y_start = -6.80
    env_len = y_start - (Y_BACK - t)
    env_y = y_start - env_len / 2
    W.box("Posing floor", (width + 2 * t, env_len, 0.06), _floor_material(), c, (CX, env_y, -0.03))
    W.box("Posing ceiling", (width + 2 * t, env_len, 0.30), ceil_m, c, (CX, env_y, H + 0.15))
    side_len = y_start - (Y_BACK - t)
    for name, x in (("Posing mirror wall", X0 - t / 2), ("Posing feature wall", X1 + t / 2)):
        W.box(name, (t, side_len, H + 0.1), wall_m, c, (x, y_start - side_len / 2, H / 2))
    W.box("Posing side wall", (width + 2 * t, t, H + 0.1), wall_m, c, (CX, Y_BACK - t / 2, H / 2))

    # Door-side lining over the outer face of the main gym wall, leaving the Phase 1 opening clear.
    ly0, ly1 = -6.915, -6.935
    ly, lt = (ly0 + ly1) / 2, abs(ly1 - ly0)
    left_w = (DOOR_X - OPEN_HALF) - X0
    right_w = X1 - (DOOR_X + OPEN_HALF)
    W.box("Posing door wall L", (left_w, lt, H), wall_m, c, (X0 + left_w / 2, ly, H / 2))
    W.box("Posing door wall R", (right_w, lt, H), wall_m, c, (X1 - right_w / 2, ly, H / 2))
    W.box("Posing door wall header", (2 * OPEN_HALF, lt, H - DOOR_H), wall_m, c, (DOOR_X, ly, DOOR_H + (H - DOOR_H) / 2))
    cy = ly1 - 0.012
    for side in (-1, 1):
        _bevel(W.box("Posing door casing", (0.06, 0.024, DOOR_H + 0.03), case_m, c,
                     (DOOR_X + side * (OPEN_HALF + 0.03), cy, (DOOR_H + 0.03) / 2)))
        W.box("Posing door reveal", (0.012, 0.095, DOOR_H), case_m, c,
              (DOOR_X + side * (OPEN_HALF - 0.006), -6.888, DOOR_H / 2))
    _bevel(W.box("Posing door casing head", (2 * OPEN_HALF + 0.18, 0.024, 0.06), case_m, c, (DOOR_X, cy, DOOR_H + 0.06)))
    W.box("Posing door reveal head", (2 * OPEN_HALF, 0.095, 0.012), case_m, c, (DOOR_X, -6.888, DOOR_H - 0.006))

    for name, size, loc in (
        ("Posing baseboard side", (width, 0.012, 0.07), (CX, Y_BACK + 0.006, 0.035)),
        ("Posing baseboard door L", (left_w, 0.012, 0.07), (X0 + left_w / 2, ly1 - 0.006, 0.035)),
        ("Posing baseboard door R", (right_w, 0.012, 0.07), (X1 - right_w / 2, ly1 - 0.006, 0.035)),
    ):
        W.box(name, size, base_m, c, loc)


def _mirror_wall(c):
    """Full-height, wall-to-wall mirror in three panels with hairline seams (x = X0, facing +X)."""
    mirror_m = W.mat("Posing_Mirror", (0.82, 0.84, 0.86), rough=0.0, metal=1.0)
    trim_m = W.mat("Posing_MirrorTrim", (0.010, 0.010, 0.012), rough=0.40, metal=0.55)
    y0, y1 = Y_BACK, -6.935
    z0, z1 = 0.07, H
    span = y1 - y0
    W.box("Mirror wall plinth", (0.03, span, z0), trim_m, c, (X0 + 0.015, (y0 + y1) / 2, z0 / 2))
    seam = 0.004
    pw = (span - 2 * seam) / 3
    for i in range(3):
        yc = y0 + pw / 2 + i * (pw + seam)
        W.box(f"Posing wall mirror {i + 1}", (0.008, pw, z1 - z0), mirror_m, c, (X0 + 0.012, yc, (z0 + z1) / 2))
    for i in (1, 2):
        ys = y0 + i * pw + (i - 0.5) * seam
        W.box("Mirror seam", (0.010, seam, z1 - z0), trim_m, c, (X0 + 0.009, ys, (z0 + z1) / 2))
    _planar(c, "PosingWallMirrorProbe", (X0 + 0.017, (y0 + y1) / 2, (z0 + z1) / 2), (0, 90, 0),
            ((z1 - z0) / 2, span / 2, 1.0))


def _feature_wall(c):
    """Opposite wall: tilted overhead mirror, red slogan, black ledge with a warm under-glow."""
    mirror_m = W.mat("Posing_Mirror", (0.82, 0.84, 0.86), rough=0.0, metal=1.0)
    frame_m = W.mat("Posing_MirrorTrim", (0.010, 0.010, 0.012), rough=0.40, metal=0.55)
    ledge_m = W.mat("Posing_LedgeBlack", (0.012, 0.012, 0.013), rough=0.55, metal=0.15)
    plinth_m = W.mat("Posing_LedgePlinth", (0.006, 0.006, 0.007), rough=0.70)
    led_m = W.shadeless("Posing_LedgeLED", (1.0, 0.78, 0.52), strength=3.0)
    red_m = W.mat("Posing_SloganRed", RED, emit=0.35, rough=0.45, metal=0.05)

    y0, y1 = Y_BACK + 0.06, -6.995
    span = y1 - y0
    ymid = (y0 + y1) / 2

    # Long overhead mirror tilted 32 deg down: from the wall-mirror side it shows the floor and the poser's back.
    tilt = math.radians(32)
    mh = 1.02
    pivot = W.empty("Tilted mirror pivot", c, (X1 - 0.035, ymid, 2.02))
    pivot.rotation_euler.y = -tilt
    W.box("Tilted mirror back", (0.020, span, mh), frame_m, c, (0.0, 0, mh / 2), parent=pivot)
    W.box("Tilted mirror glass", (0.006, span - 0.03, mh - 0.03), mirror_m, c, (-0.013, 0, mh / 2), parent=pivot)
    for z in (0.0, mh):
        _bevel(W.box("Tilted mirror rail", (0.034, span + 0.01, 0.022), frame_m, c, (-0.006, 0, z), parent=pivot), 0.003)
    for s in (-1, 1):
        _bevel(W.box("Tilted mirror stile", (0.034, 0.022, mh), frame_m, c, (-0.006, s * span / 2, mh / 2), parent=pivot), 0.003)
    _planar(c, "PosingTiltMirrorProbe", (-0.017, 0, mh / 2), (0, -90, 0), (mh / 2, span / 2, 1.0), parent=pivot)
    # Wall standoff arms holding the top edge out.
    top = Vector((X1 - 0.035 - mh * math.sin(tilt), 0, 2.02 + mh * math.cos(tilt)))
    for yy in (y0 + 0.25, ymid, y1 - 0.25):
        a, b = Vector((X1, yy, top.z - 0.03)), Vector((top.x + 0.02, yy, top.z - 0.03))
        arm = W.cyl("Tilted mirror arm", 0.011, (b - a).length, frame_m, c, tuple((a + b) / 2), seg=12)
        arm.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    # Hidden warm LED under the mirror's bottom rail washing down over the slogan.
    W.box("Tilted mirror LED", (0.012, span - 0.06, 0.006), led_m, c, (X1 - 0.05, ymid, 1.995))
    # -18 deg about Y tips the -Z emitter toward the wall (+X); local Y stays along the wall.
    _area(c, "Slogan wash", (X1 - 0.07, ymid, 1.98), 0.04, 55, (1.0, 0.80, 0.58), (0, -18, 0), size_y=span - 0.1, shadow=False, specular=0.0)

    # Red heavy-type slogan, painted on the wall (faces -X, reads left-to-right from the mirror side).
    font = _heavy_font()
    rot = (90, 0, -90)
    _text(c, "Posing slogan main", "WATCHCOACH", (X1 - 0.004, ymid, 1.30), 0.50, red_m, rot, font,
          spacing=1.02, shear=0.12, extrude=0.004)
    _text(c, "Posing slogan sub", "NO EXCUSES. JUST GAINS.", (X1 - 0.004, ymid, 0.92), 0.13, red_m, rot, font,
          spacing=1.25, shear=0.12, extrude=0.003)

    # Black ledge for bottles, towels and phones.
    d, top_z = 0.40, 0.45
    _bevel(W.box("Posing ledge top", (d, span, 0.04), ledge_m, c, (X1 - d / 2, ymid, top_z - 0.02)), 0.006)
    W.box("Posing ledge plinth", (d - 0.08, span - 0.04, top_z - 0.04), plinth_m, c, (X1 - (d - 0.08) / 2, ymid, (top_z - 0.04) / 2))
    W.box("Posing ledge LED", (0.010, span - 0.04, 0.006), led_m, c, (X1 - d + 0.035, ymid, top_z - 0.046))
    glow = _area(c, "Ledge under-glow", (X1 - d + 0.06, ymid, top_z - 0.05), 0.05, 40, (1.0, 0.78, 0.52), (0, 0, 0),
                 size_y=span - 0.06, shadow=False, specular=0.0)
    glow.rotation_euler = (0, math.radians(20), 0)  # spill forward onto the floor in front of the ledge
    return top_z


def _ledge_props(c, top_z):
    from reel_gym import folded_gym_towel, shaker_bottle
    for name, (y, rz), body, lid, acc, metal in (
        ("Ledge shaker red", (-7.55, 20), (0.70, 0.04, 0.04), (0.03, 0.03, 0.035), (0.88, 0.90, 0.92), 0.06),
        ("Ledge tumbler", (-9.85, -30), (0.05, 0.05, 0.055), (0.02, 0.02, 0.022), (0.30, 0.31, 0.33), 0.85),
    ):
        root = W.empty(name, c, (X1 - 0.17, y, top_z))
        root.rotation_euler.z = math.radians(rz)
        shaker_bottle(c, root, body, lid, acc, metal=metal)
    towel = W.empty("Ledge towel", c, (X1 - 0.20, -9.30, top_z))
    towel.rotation_euler.z = math.radians(84)
    folded_gym_towel(c, towel, (0.10, 0.10, 0.11))
    phone_m = W.mat("Ledge phone", (0.015, 0.015, 0.018), rough=0.30, metal=0.40)
    _bevel(W.box("Ledge spare phone", (0.075, 0.16, 0.009), phone_m, c, (X1 - 0.22, -8.05, top_z + 0.0045), (0, 0, 12)), 0.004)


def _selfie_tripod(c):
    """The hero's own selfie tripod + Galaxy S25 Ultra (same builder/asset as reel_gym.stage), in the room centre."""
    from reel_gym import tripod
    # Room centre, nudged toward the door side so it frames the poser instead of blocking him.
    stand = W.empty("Posing selfie tripod", c, (-1.55, CY + 0.60, 0))
    aim = POSE_SPOT - Vector(stand.location)
    # At rotation 0 the clamp/phone faces -Y (reel_gym stage); turn local -Y onto the posing spot.
    stand.rotation_euler.z = math.atan2(aim.x, -aim.y)
    tripod(c, stand)
    blend = Path(W.ROOT) / "models" / "galaxy_s25_ultra.blend"
    with bpy.data.libraries.load(str(blend)) as (src, dst):
        dst.objects = [n for n in src.objects if n == "Galaxy_S25_Ultra" or n.startswith("S25U_") and not n.endswith("_Copy")]
    loaded = [o for o in dst.objects if o is not None]
    phone = next(o for o in loaded if o.name.startswith("Galaxy_S25_Ultra"))
    for o in [phone] + list(phone.children_recursive):
        W.link(o, c)
    phone.parent = stand
    phone.location = (0, 0, 1.48)
    return stand, phone


def _lighting(c):
    house_m = W.mat("Posing_SpotHousing", (0.006, 0.006, 0.007), rough=0.35, metal=0.60)
    optic_m = W.shadeless("Posing_SpotOptic", (1.0, 0.95, 0.86), strength=8.0)
    small_m = W.shadeless("Posing_Downlight", (1.0, 0.95, 0.88), strength=5.0)

    def can(name, x, y, r=0.06):
        W.cyl(f"{name} trim", r + 0.014, 0.010, house_m, c, (x, y, H - 0.005), seg=32)
        W.cyl(f"{name} optic", r * 0.55, 0.004, optic_m if r > 0.05 else small_m, c, (x, y, H - 0.012), seg=24)

    # Hard top-down posing spots: slightly in front of the poser so brows, pecs and abs cast deep shadows.
    chest = POSE_SPOT + Vector((0, 0, 1.0))
    for i, (dy, e, size) in enumerate(((0.0, 1500, 34), (-0.55, 800, 28), (0.55, 800, 28)), 1):
        x, y = POSE_SPOT.x - 0.25, CY + dy
        can(f"Posing pin spot {i}", x, y)
        target = Vector((chest.x + 0.10, chest.y + dy * 0.4, 0.0))
        _spot(c, f"Posing pin spot {i}", (x, y, H - 0.016), target, e, size, 0.18)

    # Small recessed downlights across the rest of the ceiling (ref: dotted black ceiling).
    for x in (-2.75, -1.95, -1.15):
        for y in (-7.45, -8.70, -9.95):
            can(f"Downlight {x}_{y}", x, y, r=0.035)
            _spot(c, f"Downlight {x}_{y}", (x, y, H - 0.014), (x, y, 0.0), 45, 95, 0.9,
                  color=(1.0, 0.94, 0.86), soft=0.04, shadow=False)  # fill only; keeps the shadow pool for the pin spots

    # Very faint room fill so black walls read as black, not void.
    _area(c, "Posing room fill", (CX, CY, H - 0.03), 3.0, 18, (1.0, 0.93, 0.86), (0, 0, 0), size_y=3.0, shadow=False, specular=0.0)

    # Sphere probe: fallback reflections for the glossy floor and off-screen rays.
    try:
        lp = bpy.data.lightprobes.new("PosingRoomSphereProbe", "SPHERE")
        lp.influence_distance = 2.7
        ob = bpy.data.objects.new("PosingRoomSphereProbe", lp)
        c.objects.link(ob)
        ob.location = (CX, CY, 1.50)
    except Exception:
        pass


def _planar(c, name, loc, rot_deg, scale, parent=None):
    """Planar reflection probe: its local +Z must point out of the mirror, into the room."""
    try:
        lp = bpy.data.lightprobes.new(name, "PLANE")
    except Exception:
        return None
    ob = bpy.data.objects.new(name, lp)
    c.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    ob.scale = scale
    return ob


def build_posing_room(parent):
    """Phase 2: build the posing room interior behind the Phase 1 door. Returns the collection."""
    c = W.coll("Annex - Posing Room", parent)
    _architecture(c)
    _mirror_wall(c)
    top_z = _feature_wall(c)
    _ledge_props(c, top_z)
    _selfie_tripod(c)
    _lighting(c)
    return c


def use_posing_room_cycles(scene=None, samples=128, preview=False):
    """Render settings for any shot inside the posing room.

    EEVEE cannot trace a mirror seen in another mirror (the tilted mirror warps inside the wall mirror) and its
    reflection shadow maps leak gym light as dotted streaks; Cycles path-traces both correctly.
    ~20 s per 1080x1350 frame at 128 samples on an RTX 4060. Keeps the scene's colour management (AgX).
    """
    sc = scene or bpy.context.scene
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    device = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                device = kind
                break
    except Exception:
        pass
    cy.device = "CPU" if device == "CPU" else "GPU"
    cy.samples = 32 if preview else samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    if device == "OPTIX":
        cy.denoiser = "OPTIX"
    # Enough glossy depth for mirror -> mirror -> poser, and clamping against spot-light fireflies on the glass.
    cy.max_bounces = 16
    cy.glossy_bounces = 12
    cy.diffuse_bounces = 3
    cy.transmission_bounces = 4
    cy.transparent_max_bounces = 8
    cy.sample_clamp_indirect = 8.0
    sc.render.use_persistent_data = True  # reuse BVH between frames of an animation
    return device
