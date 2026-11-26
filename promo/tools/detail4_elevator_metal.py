"""detail4 P9 elevator_metal: bright hairline stainless elevator doors / frame + a planar reflection probe on the door wall.

Problem: the hallway has no reflection probe, so the 0.92-metal elevator doors (`Elev_DoorStainless`) reflect the
dark world and read as dark grey slabs, inside a black granite surround (work/detail4/survey/current_hall_elevator.jpg).
References work/refs/hall/045, 092 (Korean sangga elevator halls): light vertical-hairline stainless doors and a
~50-70 mm stainless frame wrapping the doors and the transom (floor display) panel, on a light stone wall.

This module:
  - Doors `Elev_Door_L/R`: material swapped to a copy `D4elev_DoorHairline` (base 0.78, vertical hairline =
    roughness 0.18..0.30 from a noise stretched along the door height + a very faint matching bump; metallic 0.85 with
    the default planar probe, 1.0 otherwise). EEVEE ignores Principled "Anisotropic" (identical pixels at 0.0 / 0.8).
  - Frame parts `ElevFrame_L/R/Top`, `ElevJamb_L/R`, `ElevSoffit`, `ElevHeader_Back` (shared `Hallway_StainlessMullion`,
    30 users -> NOT edited): their slot gets `D4elev_FrameHairline` instead (metallic 1.0).
  - New 53 mm stainless frame faces (`D4elev_FrameFace_L/R/Top`) in front of the 35-40 mm `ElevFrame_*` bars. They keep
    2 mm clear of the floor display panel `ElevHeader_Display` (x -9.50..-8.44, z 2.08..2.37) and of `ElevHeader_Back`.
  - Option SURROUND_GRAY (default True): the black granite portal `ElevGranite_L/R/Top` gets the hall wall's own
    `Elev_GrayGranite` material, as in ref 045 / 092. `--keep-black` or SURROUND_GRAY = False keeps the black granite.
  - Default reflection: planar probe `D4elev_DoorPlaneProbe` on the door wall (centre (-8.97, -17.01, 1.22), half size
    0.62 x 1.23 m, influence 0.30 m): covers doors, frame and wall lamps, not the hydrant.
    Why not a sphere probe: a sphere probe also lights the elevator doors that the hallway restroom mirror (Neon) sees
    18 m away, and that reflection turned into white fog (red items lost). A planar probe only changes the doors' own
    shading; the mirror reflection stays as sharp as the original (work/detail4/elevator_metal/REPORT.md).
    Neon's mirror probe `Dhall_props_HP_RestMirrorProbe` already covers that mirror and is NOT touched.
Every touched existing object stores its original material in ob["d4elev_orig_mat"]; re-runs restore first.
Untouched on purpose: call buttons, floor display, 3F label, hydrant, X-banners, stickers, floor inlay.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_elevator_metal.py -- \
      [--keep-black] [--sphere-probe | --no-sphere-probe | --no-probe] [--save out.blend]
  (default)         : planar probe on the door wall, doors metallic 0.85.
  --sphere-probe    : old sphere probe `D4elev_HallSphereProbe` (r 1.35), metallic 1.0 (fogs the restroom mirror).
  --no-sphere-probe / --no-door-probe : no probe at all, materials metallic 1.0 (doors reflect the dark world).
  --no-probe        : no probe AND half-dielectric stainless (metal 0.5) so the doors still read light grey.
  apply(surround_gray=None, door_probe="plane"|"sphere"|None, half_metal=False) is the same in Python.
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector

KEY = "elevator_metal"
COLL = "DETAIL4_elevator_metal"
PFX = "D4elev_"
ORIG = "d4elev_orig_mat"

SURROUND_GRAY = True
DOOR_PROBE = "plane"     # "plane" | "sphere" | None
DOOR_METAL_PLANE = 0.85
PLANE_CENTER = (-8.97, -17.010, 1.22)
PLANE_HALF = (0.62, 1.23, 1.0)   # x -9.59..-8.35, z -0.01..2.45
PLANE_INFLUENCE = 0.30
PROBE_CENTER = (-8.97, -16.75, 1.05)   # door bay only; doors (x -9.51..-8.43, z 0..2.06) stay within 93 % of the radius
PROBE_RADIUS = 1.35
DOORS = ("Elev_Door_L", "Elev_Door_R")
FRAME_PARTS = ("ElevFrame_L", "ElevFrame_R", "ElevFrame_Top", "ElevJamb_L", "ElevJamb_R", "ElevSoffit",
               "ElevHeader_Back")
SURROUND = ("ElevGranite_L", "ElevGranite_R", "ElevGranite_Top")


def _hairline(name, base, rough_lo, rough_hi, bump, metallic=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Specular IOR Level"].default_value = 0.5
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    # object-space position, squashed along Z -> long vertical streaks (hairline brushed along the height)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (900.0, 900.0, 1.6)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 1.0
    fine.inputs["Detail"].default_value = 4.0
    fine.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], fine.inputs["Vector"])
    # broad, softer variation (polishing / handling marks) so the doors are not perfectly uniform
    mp2 = nt.nodes.new("ShaderNodeMapping")
    mp2.inputs["Scale"].default_value = (7.0, 7.0, 0.8)
    nt.links.new(tc.outputs["Object"], mp2.inputs["Vector"])
    broad = nt.nodes.new("ShaderNodeTexNoise")
    broad.inputs["Scale"].default_value = 1.0
    broad.inputs["Detail"].default_value = 2.0
    nt.links.new(mp2.outputs["Vector"], broad.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.35
    nt.links.new(fine.outputs["Fac"], mix.inputs["A"])
    nt.links.new(broad.outputs["Fac"], mix.inputs["B"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.3
    mr.inputs["From Max"].default_value = 0.7
    mr.inputs["To Min"].default_value = rough_lo
    mr.inputs["To Max"].default_value = rough_hi
    nt.links.new(mix.outputs["Result"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.0002
    nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = (*base, 1)
    return m


def _swap(ob, mat):
    if ORIG not in ob:
        ob[ORIG] = ob.material_slots[0].material.name
    ob.material_slots[0].material = mat
    ob["detail4_pkg"] = KEY


def _restore():
    for ob in bpy.data.objects:
        if ORIG in ob and ob.get("detail4_pkg") == KEY:
            ob.material_slots[0].material = bpy.data.materials[ob[ORIG]]


def _box(name, lo, hi, mat, coll):
    me = bpy.data.meshes.get(name)
    if me:
        bpy.data.meshes.remove(me)
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    size = Vector(hi) - Vector(lo)
    bmesh.ops.scale(bm, vec=size, verts=r["verts"])
    # 1.5 mm bevel on the visible edges
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0015, segments=1, affect="EDGES", clamp_overlap=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = (Vector(lo) + Vector(hi)) / 2
    ob["detail4_pkg"] = KEY
    return ob


_DEFAULT = "default"


def apply(surround_gray=None, door_probe=_DEFAULT, half_metal=False, sphere_probe=None) -> dict:
    """door_probe: "plane" (default) = planar probe on the door wall, doors metallic 0.85;
    "sphere" = sphere probe in front of the doors, doors metallic 1.0 (brighter, but the hallway restroom mirror then
    reflects a bright elevator lobby, see REPORT); None = no probe, metallic 1.0 (dark doors).
    half_metal=True: no-probe fallback, all stainless metallic 0.5 (flat, painted look).
    sphere_probe: old argument, True -> "sphere", False -> None."""
    if surround_gray is None:
        surround_gray = SURROUND_GRAY
    if sphere_probe is not None:
        door_probe = "sphere" if sphere_probe else None
    elif door_probe == _DEFAULT:
        door_probe = DOOR_PROBE
    if door_probe == "none":
        door_probe = None
    _restore()
    set_coll = bpy.data.collections["SET"]
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        set_coll.children.link(coll)
    for ob in list(coll.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.LightProbe) and data.users == 0:
            bpy.data.lightprobes.remove(data)

    metal = 0.5 if half_metal else 1.0
    # with the planar probe the doors keep 15 % diffuse (brushed stainless scatters a little); measured 113 -> 142
    door_metal = 0.5 if half_metal else (DOOR_METAL_PLANE if door_probe == "plane" else 1.0)
    door = _hairline(PFX + "DoorHairline", (0.78, 0.78, 0.77), 0.18, 0.30, 0.010, door_metal)
    frame = _hairline(PFX + "FrameHairline", (0.76, 0.76, 0.75), 0.20, 0.32, 0.008, metal)
    touched = []
    for n in DOORS:
        _swap(bpy.data.objects[n], door); touched.append(n)
    for n in FRAME_PARTS:
        _swap(bpy.data.objects[n], frame); touched.append(n)
    if surround_gray:
        gray = bpy.data.materials["Elev_GrayGranite"]
        for n in SURROUND:
            _swap(bpy.data.objects[n], gray); touched.append(n)

    # 53 mm frame faces in front of ElevFrame_L/R/Top (35-40 mm). World coords; door centre x = -8.97.
    # ElevFrame_L x -8.447..-8.412, y -17.06..-17.02 ; ElevFrame_Top z 2.37..2.41 ; granite face y -17.03.
    # Floor display ElevHeader_Display: x -9.50..-8.44, z 2.08..2.37, plane y -17.035; ElevHeader_Back front y -17.04.
    # Faces stay 2 mm clear of both: inner side edges at x -8.438 / -9.502, top face bottom at z 2.372, back y -17.038.
    # 53 mm wide so the right face also clears the call plate / wall lamps (x <= -9.557).
    yb, yf = -17.038, -17.012
    added = [
        _box(PFX + "FrameFace_L", (-8.438, yb, 0.0005), (-8.385, yf, 2.437), frame, coll),
        _box(PFX + "FrameFace_R", (-9.555, yb, 0.0005), (-9.502, yf, 2.437), frame, coll),
        _box(PFX + "FrameFace_Top", (-9.5545, yb + 0.001, 2.372), (-8.3855, yf - 0.001, 2.4365), frame, coll),
    ]
    # the top face runs into the side faces at the corners; it sits 1 mm back so no face is coplanar

    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in added)
    info = {"triangles_added": tris, "existing_touched": touched, "surround_gray": bool(surround_gray),
            "half_metal": bool(half_metal), "door_probe": door_probe, "door_metallic": door_metal}
    if door_probe is None:
        return {"objects_added": len(added), "probe": None, **info}
    if door_probe == "plane":
        # planar probe 2 mm in front of the new frame faces; influence 0.30 m reaches back to the door faces
        # (y -17.264) and covers doors + frame + lamps, but not the hydrant cabinet (x >= -8.18).
        lp = bpy.data.lightprobes.new(PFX + "DoorPlaneProbe", "PLANE")
        pr = bpy.data.objects.new(PFX + "DoorPlaneProbe", lp)
        coll.objects.link(pr)
        pr.location = PLANE_CENTER
        pr.rotation_euler = (math.radians(-90), 0, 0)      # probe normal faces +y (the corridor)
        pr.scale = PLANE_HALF
        lp.influence_distance = PLANE_INFLUENCE
    else:
        lp = bpy.data.lightprobes.new(PFX + "HallSphereProbe", "SPHERE")
        pr = bpy.data.objects.new(PFX + "HallSphereProbe", lp)
        coll.objects.link(pr)
        # the doors must sit well inside the influence (at the very edge the weight is ~0: first try had dark doors)
        pr.location = PROBE_CENTER
        lp.influence_distance = PROBE_RADIUS
        lp.clip_start = 0.05
    pr["detail4_pkg"] = KEY
    return {"objects_added": len(added) + 1, "probe": pr.name, **info}

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    no_probe = "--no-probe" in argv
    if no_probe or "--no-door-probe" in argv or "--no-sphere-probe" in argv:
        mode = "none"
    elif "--sphere-probe" in argv:
        mode = "sphere"
    else:
        mode = _DEFAULT
    print("D4ELEV APPLY", apply(surround_gray=False if "--keep-black" in argv else None, door_probe=mode,
                                half_metal=no_probe), flush=True)
    if "--save" in argv:
        out = argv[argv.index("--save") + 1]
        if "promo/scenes" in out or "promo/models" in out:
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        bpy.ops.wm.save_as_mainfile(filepath=out, copy=True)
        print("D4ELEV SAVED", out, flush=True)
