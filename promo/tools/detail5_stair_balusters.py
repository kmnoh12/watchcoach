"""Add slim vertical infill to the two existing central stair rail bays."""
import bpy
from mathutils import Vector

COLL = "DETAIL5_stair_balusters"
_PREFIX = "Dhall_props_Stair_"
_COUNT = 12
# A 14 mm square section with a 0.8 mm chamfer on its long edges.
_PROFILE = (
    (-.0062, -.007), (.0062, -.007), (.007, -.0062), (.007, .0062),
    (.0062, .007), (-.0062, .007), (-.007, .0062), (-.007, -.0062),
)


def _surface_z(obj, hall, point, direction):
    to_mesh = obj.matrix_world.inverted() @ hall.matrix_world
    hit, pos, _, _ = obj.ray_cast(
        to_mesh @ point, to_mesh.to_3x3() @ Vector((0, 0, direction))
    )
    if not hit:
        raise ValueError(f"Missing joint at {point} on {obj.name}")
    return (to_mesh.inverted() @ pos).z


def _bay_geometry(start, end, rail, curb, hall):
    verts, faces = [], []
    for i in range(1, _COUNT + 1):
        center = start.lerp(end, i / (_COUNT + 1))
        top, base = [], []
        for dx, dy in _PROFILE:
            x, y = center.x + dx, center.y + dy
            # Cast from the clear space between the handrail and curb.
            point = Vector((x, y, center.z))
            base.append((x, y, _surface_z(curb, hall, point, -1) - .001))
            top.append((x, y, _surface_z(rail, hall, point, 1) + .001))
        if max(v[2] for v in base) - min(v[2] for v in base) > .0001:
            raise ValueError(f"Foot straddles a curb riser at {center.x:.4f}")
        offset = len(verts)
        verts.extend(base + top)
        verts.append((center.x, center.y, _surface_z(rail, hall, center, 1) + .001))
        n = len(base)
        faces.append(tuple(offset + j for j in reversed(range(n))))
        for j in range(n):
            a, b = offset + j, offset + (j + 1) % n
            faces.append((a, b, b + n, a + n))
            faces.append((a + n, b + n, offset + 2 * n))
    return verts, faces


def apply() -> dict:
    hall = bpy.data.objects["Sangga_Hallway"]
    rail = bpy.data.objects[_PREFIX + "RailTop"]
    curb = bpy.data.objects[_PREFIX + "Curb"]
    posts = [bpy.data.objects[_PREFIX + f"RailPost{i}"] for i in range(3)]
    centers = [hall.matrix_world.inverted() @ p.matrix_world.translation for p in posts]
    bays = [_bay_geometry(a, b, rail, curb, hall) for a, b in zip(centers, centers[1:])]

    parent = bpy.data.collections["SET"]
    coll = parent.children.get(COLL)
    if coll is None:
        if bpy.data.collections.get(COLL):
            raise ValueError(f"{COLL} already exists outside SET")
        coll = bpy.data.collections.new(COLL)
        parent.children.link(coll)
    for obj in list(coll.objects):
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    triangles = 0
    for i, (verts, faces) in enumerate(bays, 1):
        name = f"Ddetail5_StairBalusters_Bay{i}"
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        mesh.materials.append(rail.active_material)
        obj = bpy.data.objects.new(name, mesh)
        coll.objects.link(obj)
        obj.parent = hall
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
    return dict(objects_added=len(bays), triangles_added=triangles, existing_objects_touched=[])
