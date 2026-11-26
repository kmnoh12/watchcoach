"""detail5 hall_ceiling_air: HVAC outlets in the sangga hallway ceiling.

The hallway ceiling already has downlights, sprinklers, smoke detectors, speakers, emergency lights, CCTV and
inspection hatches, but no air outlet at all. Refs: hall/090 (round anemostat diffuser in a white tex
ceiling), hall/004 (square ceiling outlet next to the cassette in a 600 grid), hall/092 (round outlet in the
lobby ceiling).

Adds, in the Sangga_Hallway local frame (x along corridor, y=0 gym side, ceiling underside z=2.75):
  * 3 round anemostat supply diffusers (face 400 mm, 3 stepped cones over a dark throat) on the gym-side tile
    row, midway between the existing sprinklers, 4.8 m apart;
  * 2 lay-in 570 mm louvred return grilles on the opposite tile row.
All sit inside free 600x600 tiles of the existing M-bar grid (checked against every ceiling device).

    import detail5_hall_ceiling_air as m; m.apply()
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail5_hall_ceiling_air.py [-- --save new.blend]
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy

COLL = "DETAIL5_hall_ceiling_air"
PFX = "Ddetail5_HallAir_"
CEIL_Z = 2.75
ROW_G, ROW_O = 0.86, 2.06               # tile-centre rows (gym side / opposite side)
DIFFUSERS = [(-9.0, ROW_G), (-4.2, ROW_G), (0.6, ROW_G)]
RETURNS = [(-6.6, ROW_O), (2.4, ROW_O)]
SEG = 40

# Round diffuser: closed (r, depth-below-ceiling) profiles, each revolved into one ring.
# Depth 0 = ceiling plane; every part keeps >= 1 mm off the ceiling so nothing is coplanar with it.
_RINGS = (
    # outer flange + first cone (face 400 mm)
    ((0.200, 0.0012), (0.200, 0.0060), (0.172, 0.0110), (0.150, 0.0220), (0.144, 0.0220),
     (0.166, 0.0070), (0.192, 0.0012)),
    # second cone
    ((0.126, 0.0100), (0.126, 0.0140), (0.102, 0.0300), (0.096, 0.0300), (0.118, 0.0100)),
    # third cone
    ((0.080, 0.0180), (0.080, 0.0220), (0.058, 0.0380), (0.052, 0.0380), (0.072, 0.0180)),
    # centre plaque
    ((0.0, 0.0400), (0.040, 0.0400), (0.040, 0.0440), (0.0, 0.0455)),
)
_THROAT = (0.165, 0.0016, 0.0030)       # dark disc seen through the gaps: radius, depth top, depth bottom


def _mats():
    def pbr(name, color, rough, metal=0.0):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        if m.node_tree is None:
            m.use_nodes = True
        nt = m.node_tree
        b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b is None:
            nt.nodes.clear()
            b = nt.nodes.new("ShaderNodeBsdfPrincipled")
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
        b.inputs["Base Color"].default_value = (*color, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*color, 1.0)
        return m
    # powder-coated white steel (slightly warmer than the tex board so the outline reads)
    return pbr(PFX + "WhiteSteel", (0.80, 0.80, 0.78), 0.42), pbr(PFX + "DuctDark", (0.025, 0.025, 0.025), 0.9)


def _lathe(bm, profile, z_of, mat_index):
    """Revolve a closed (r, depth) polygon around the local z axis. r == 0 points become poles."""
    rings = []
    for r, d in profile:
        z = z_of(d)
        if r < 1e-9:
            rings.append([bm.verts.new((0.0, 0.0, z))] * SEG)
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / SEG),
                                        r * math.sin(2 * math.pi * i / SEG), z)) for i in range(SEG)])
    n = len(rings)
    for a in range(n):
        ra, rb = rings[a], rings[(a + 1) % n]
        for i in range(SEG):
            j = (i + 1) % SEG
            vs = []
            for v in (ra[i], ra[j], rb[j], rb[i]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                f = bm.faces.new(vs)
                f.material_index = mat_index
                f.smooth = True


def _diffuser_mesh(white, dark):
    bm = bmesh.new()
    z_of = lambda d: CEIL_Z - d  # noqa: E731
    for prof in _RINGS:
        _lathe(bm, prof, z_of, 0)
    r, d0, d1 = _THROAT
    _lathe(bm, ((0.0, d0), (r, d0), (r, d1), (0.0, d1)), z_of, 1)
    # 4 radial support fins hang each cone from the throat disc (real anemostats use such cross bars).
    # Stepped so every segment stays above the cone it holds and only sinks 0.5 mm into it.
    fin_steps = ((0.112, 0.175, 0.0105),   # flange + 2nd cone
                 (0.066, 0.118, 0.0185),   # 2nd + 3rd cone
                 (0.030, 0.060, 0.0405))   # 3rd cone + centre plaque
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        ca, sa = math.cos(a), math.sin(a)
        for r0, r1, dbot in fin_steps:
            quad = ((r0, -0.001), (r1, -0.001), (r1, 0.001), (r0, 0.001))
            top = [bm.verts.new((r_ * ca - t * sa, r_ * sa + t * ca, z_of(0.0025))) for r_, t in quad]
            bot = [bm.verts.new((r_ * ca - t * sa, r_ * sa + t * ca, z_of(dbot))) for r_, t in quad]
            faces = [top[::-1], bot] + [[top[i], top[(i + 1) % 4], bot[(i + 1) % 4], bot[i]] for i in range(4)]
            for fv in faces:
                bm.faces.new(fv).material_index = 0
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(PFX + "Diffuser_mesh")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(white)
    me.materials.append(dark)
    me.set_sharp_from_angle(angle=math.radians(35))
    return me


def _box(bm, lo, hi, mi):
    vs = [bm.verts.new((x, y, z)) for z in (lo[2], hi[2]) for y in (lo[1], hi[1]) for x in (lo[0], hi[0])]
    for q in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
        bm.faces.new([vs[i] for i in q]).material_index = mi


def _return_mesh(white, dark):
    """570 mm lay-in louvred return grille, centred at the origin, hanging from the ceiling plane."""
    bm = bmesh.new()
    h, f = 0.285, 0.028                   # half size, frame face width
    zt, zf = CEIL_Z - 0.0010, CEIL_Z - 0.0100  # top of parts, frame face
    for lo, hi in (((-h, -h, zf), (h, -h + f, zt)), ((-h, h - f, zf), (h, h, zt)),
                   ((-h, -h + f, zf), (-h + f, h - f, zt)), ((h - f, -h + f, zf), (h, h - f, zt))):
        _box(bm, lo, hi, 0)
    # dark plenum seen between the blades (2 mm under the ceiling plane, inside the frame)
    _box(bm, (-h + f, -h + f, CEIL_Z - 0.0040), (h - f, h - f, CEIL_Z - 0.0020), 1)
    # 15 fixed blades along x, 3 mm thick, 22 mm deep, pitch ~34 mm
    inner = 2 * (h - f)
    n = 15
    for i in range(n):
        yc = -h + f + inner * (i + 0.5) / n
        _box(bm, (-h + f, yc - 0.0015, CEIL_Z - 0.0260), (h - f, yc + 0.0015, CEIL_Z - 0.0041), 0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(PFX + "Return_mesh")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(white)
    me.materials.append(dark)
    return me


def _clear(coll):
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.name.startswith(PFX) and me.users == 0:
            bpy.data.meshes.remove(me)


def apply() -> dict:
    hall = bpy.data.objects["Sangga_Hallway"]
    parent = bpy.data.collections["SET"]
    coll = parent.children.get(COLL)
    if coll is None:
        if bpy.data.collections.get(COLL):
            raise ValueError(f"{COLL} already exists outside SET")
        coll = bpy.data.collections.new(COLL)
        parent.children.link(coll)
    _clear(coll)
    white, dark = _mats()
    dme, rme = _diffuser_mesh(white, dark), _return_mesh(white, dark)
    added = []
    for i, (x, y) in enumerate(DIFFUSERS):
        added.append((f"{PFX}Diffuser_{i}", dme, (x, y, 0.0)))
    for i, (x, y) in enumerate(RETURNS):
        added.append((f"{PFX}Return_{i}", rme, (x, y, 0.0)))
    tris = 0
    for name, me, loc in added:
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob.parent = hall          # no parent inverse: location is in hallway-local metres
        ob.location = loc
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
    return dict(objects_added=len(added), triangles_added=tris,
                unique_mesh_triangles=sum(len(m.loop_triangles) for m in (dme, rme)),
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
    print("detail5_hall_ceiling_air", apply())
    if save is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save), copy=True, compress=True)
        print("saved", save)


if __name__ == "__main__":
    _main()
