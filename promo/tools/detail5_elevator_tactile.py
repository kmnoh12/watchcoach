"""detail5 elevator_tactile: yellow dot-type tactile warning blocks (점형블록) in front of the elevator.

The hallway only has one tactile patch (in front of the stair door). Korean refs put a 2-block dot patch
on the floor in front of the elevator call button / door: hall/092 (two blocks beside the door, call-button
side), hall/041 and hall/042 (patch in front of the elevator), hall/045 (patch at the door's button corner).

Adds one 600 x 300 mm patch (two 300 mm blocks, 6 x 6 domes each, same spec and the same shared
`Dhall_props_TactileYellow` material as the existing stair patch) 0.25 m in front of the elevator sill,
from the call-button side edge into the door opening. It sits inside the existing black granite inlay frame
and clear of the X-banner base. Hallway-local frame (x along corridor, y=0 gym side), floor z=0.

    import detail5_elevator_tactile as m; m.apply()
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail5_elevator_tactile.py [-- --save new.blend]
"""
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix

COLL = "DETAIL5_elevator_tactile"
PFX = "Ddetail5_ElevTactile_"
TILE = 0.30
# hallway-local patch: x across the elevator front (0.30 deep), y along the elevator wall (2 tiles)
X0, Y0 = -11.25, 1.51            # world x -9.66..-9.06, y -16.80..-16.50
NX, NY = 1, 2                     # tiles
PITCH, R_BOT, R_TOP, DOME_H = 0.05, 0.013, 0.009, 0.005
Z_BOT, Z_TOP = -0.002, 0.004      # plate is set 2 mm into the floor, top 4 mm proud (as the stair patch)
EXISTING_MAT = "Dhall_props_TactileYellow"


def _material():
    m = bpy.data.materials.get(EXISTING_MAT)
    if m is not None:
        return m
    # fallback only if the stair patch material is missing from the scene
    m = bpy.data.materials.get(PFX + "Yellow") or bpy.data.materials.new(PFX + "Yellow")
    if m.node_tree is None:
        m.use_nodes = True
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is not None:
        b.inputs["Base Color"].default_value = (0.85, 0.62, 0.02, 1.0)
        b.inputs["Roughness"].default_value = 0.55
    m.diffuse_color = (0.85, 0.62, 0.02, 1.0)
    return m


def _mesh(name, build, mat, smooth_angle=None):
    bm = bmesh.new()
    build(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    if smooth_angle is not None:
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=smooth_angle)
    return me


def _plate(bm):
    x1, y1 = X0 + NX * TILE, Y0 + NY * TILE
    lo, hi, b = (X0, Y0, Z_BOT), (x1, y1, Z_TOP), 0.0015
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.LocRotScale(
        ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2), None,
        (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=1, affect="EDGES", profile=0.5,
                    clamp_overlap=True)


def _dots(bm):
    per = round(TILE / PITCH)
    for ix in range(NX * per):
        for iy in range(NY * per):
            # cones start 0.5 mm inside the plate top so every dome is welded to the plate
            ctr = Matrix.Translation((X0 + PITCH / 2 + ix * PITCH, Y0 + PITCH / 2 + iy * PITCH,
                                      Z_TOP - 0.0005 + DOME_H / 2))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=R_BOT, radius2=R_TOP,
                                  depth=DOME_H, matrix=ctr)


def apply() -> dict:
    import math
    hall = bpy.data.objects["Sangga_Hallway"]
    parent = bpy.data.collections["SET"]
    coll = parent.children.get(COLL)
    if coll is None:
        if bpy.data.collections.get(COLL):
            raise ValueError(f"{COLL} already exists outside SET")
        coll = bpy.data.collections.new(COLL)
        parent.children.link(coll)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.name.startswith(PFX) and me.users == 0:
            bpy.data.meshes.remove(me)
    mat = _material()

    def build(bm):
        _plate(bm)
        _dots(bm)
    me = _mesh(PFX + "Patch", build, mat, math.radians(50))
    ob = bpy.data.objects.new(PFX + "Patch", me)
    coll.objects.link(ob)
    ob.parent = hall              # no parent inverse: coordinates are hallway-local metres
    me.calc_loop_triangles()
    tris, added = len(me.loop_triangles), [ob.name]
    return dict(objects_added=len(added), triangles_added=tris, material=mat.name,
                existing_objects_touched=[])


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    save = None
    if "--save" in argv:
        save = Path(argv[argv.index("--save") + 1]).expanduser().resolve()
        root = Path(__file__).resolve().parents[2]
        if any(save.is_relative_to((root / "promo" / d).resolve()) for d in ("scenes", "models")):
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        if save.suffix.lower() != ".blend" or save.exists():
            raise SystemExit("--save must name a new .blend file")
    print("detail5_elevator_tactile", apply())
    if save is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save), copy=True, compress=True)
        print("saved", save)


if __name__ == "__main__":
    _main()
