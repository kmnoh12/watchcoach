"""Low-poly gym equipment kit. Units: metres, +Z up, the lifter faces -Y. Every part is a small group of flat-shaded primitives
under an empty named P_<part>; its origin is the place the figure holds / sits on, so poses can snap to it.
Run inside Blender; rebuilds the `Kit` collection from scratch."""
import bpy, bmesh, math
from mathutils import Vector, Matrix

COL = {"steel": (0.76, 0.79, 0.84, 1), "plate": (0.018, 0.019, 0.023, 1), "pad": (0.022, 0.024, 0.028, 1),
       "frame": (0.68, 0.035, 0.040, 1), "grip": (0.014, 0.015, 0.018, 1), "accent": (0.95, 0.72, 0.04, 1),
       "silver": (0.055, 0.060, 0.068, 1), "stack": (0.024, 0.027, 0.032, 1), "red": (0.72, 0.04, 0.05, 1),
       "wood": (0.45, 0.28, 0.14, 1)}
PBR = {"steel": (0.16, 0.94), "plate": (0.48, 0.22), "pad": (0.44, 0.0),
       "frame": (0.28, 0.38), "grip": (0.82, 0.0), "accent": (0.28, 0.12),
       "silver": (0.32, 0.58), "stack": (0.42, 0.38), "red": (0.30, 0.28),
       "wood": (0.50, 0.0)}


def _add_bevel(ob, width, segments=3):
    dims = ob.dimensions
    min_dim = min(d for d in (dims.x, dims.y, dims.z) if d > 1e-4) if any(d > 1e-4 for d in dims) else width * 4
    w = min(width, min_dim * 0.35)
    if w < 1e-4:
        return ob
    bev = ob.modifiers.new("Bevel", "BEVEL")
    bev.width = w
    bev.segments = segments
    ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    return ob


def _smooth_cyl(ob):
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return ob


def mat(name):
    m = bpy.data.materials.get("E_" + name) or bpy.data.materials.new("E_" + name)
    c = COL[name]
    m.diffuse_color = c
    if m.node_tree:
        b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b:
            rough, metal = PBR.get(name, (0.5, 0.0))
            b.inputs["Base Color"].default_value = c
            b.inputs["Roughness"].default_value = rough
            b.inputs["Metallic"].default_value = metal
    return m


def _obj(name, bm, parent, material, loc=(0, 0, 0), rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(mat(material))
    bpy.data.collections["Kit"].objects.link(ob)
    ob.parent = parent; ob.location = loc; ob.rotation_euler = tuple(math.radians(a) for a in rot)
    return ob


def cyl(name, parent, r, length, axis="X", mat_name="steel", loc=(0, 0, 0), sides=8, r2=None):
    seg = max(sides, 28 if r >= 0.08 else 20)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=length)
    rot = {"X": (0, 90, 0), "Y": (90, 0, 0), "Z": (0, 0, 0)}[axis]
    return _smooth_cyl(_obj(name, bm, parent, mat_name, loc, rot))


def box(name, parent, size, mat_name="frame", loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.005):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = _obj(name, bm, parent, mat_name, loc, rot)
    if bevel and bevel > 0:
        _add_bevel(ob, bevel, segments=2)
    return ob


def part(name):
    e = bpy.data.objects.new("P_" + name, None); e.empty_display_size = 0.08
    bpy.data.collections["Kit"].objects.link(e)
    return e


def barbell(L=2.2, plate_r=0.225):
    p = part("barbell")
    cyl("bar", p, 0.015, L, "X", "steel", sides=8)
    for s in (-1, 1):
        cyl("sleeve", p, 0.026, 0.42, "X", "steel", (s * (L / 2 - 0.21), 0, 0), 8)
        cyl("endcap", p, 0.030, 0.03, "X", "accent", (s * (L / 2 - 0.015), 0, 0), 8)
        for i, r in enumerate((plate_r, plate_r, plate_r * 0.78)):
            cyl("plate", p, r, 0.032, "X", "plate", (s * (0.52 + i * 0.045), 0, 0), 12)
        cyl("collar", p, 0.036, 0.04, "X", "accent", (s * 0.70, 0, 0), 6)
    return p


def plain_bar(L=1.8):
    p = part("bar"); cyl("bar", p, 0.015, L, "X", "steel", sides=8)
    for s in (-1, 1): cyl("cap", p, 0.022, 0.04, "X", "accent", (s * (L / 2 - 0.02), 0, 0), 8)
    return p


def dumbbell(head_r=0.082, head_len=0.085, handle_len=0.165):
    p = part("dumbbell")
    cyl("handle", p, 0.017, handle_len, "X", "steel", sides=20)
    offset = handle_len / 2 + head_len / 2 - 0.008
    for s in (-1, 1):
        cyl("head", p, head_r, head_len, "X", "plate", (s * offset, 0, 0), 24)
        cyl("ring", p, head_r * 0.78, head_len + 0.006, "X", "accent", (s * offset, 0, 0), 24)
        cyl("cap", p, head_r * 0.54, head_len + 0.011, "X", "plate", (s * offset, 0, 0), 24)
    return p


def ez_bar():
    p = part("ez_bar")
    pts = [(-0.55, 0), (-0.22, 0), (-0.12, 0.04), (0, 0), (0.12, 0.04), (0.22, 0), (0.55, 0)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        ln = math.hypot(x1 - x0, y1 - y0); ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        o = cyl("seg", p, 0.015, ln, "X", "steel", ((x0 + x1) / 2, (y0 + y1) / 2, 0), 8)
        o.rotation_euler = (0, math.radians(90), math.radians(ang))
    for s in (-1, 1): cyl("cap", p, 0.022, 0.04, "X", "accent", (s * 0.55, 0, 0), 8)
    return p


def bench():
    """Adjustable bench: P_bench (origin: floor under the seat centre) with a hinged back pad: child P_bench_back
    pivots about the X axis at the seat's rear edge. rotation_euler.x = -back angle (0 = flat, 90 = upright)."""
    p = part("bench")
    box("seat", p, (0.30, 0.34, 0.09), "pad", (0, 0.0, 0.43))
    box("seat_trim", p, (0.32, 0.36, 0.03), "grip", (0, 0.0, 0.385))
    box("spine", p, (0.07, 0.62, 0.07), "frame", (0, 0.04, 0.30), (0, 0, 0))
    box("post", p, (0.07, 0.07, 0.30), "frame", (0, -0.08, 0.19))
    for s in (-1, 1):
        box("foot_f", p, (0.46, 0.06, 0.04), "frame", (0, -0.20, 0.02))
        box("foot_b", p, (0.46, 0.06, 0.04), "frame", (0, 0.30, 0.02))
    for y in (-0.20, 0.30):
        box("leg", p, (0.07, 0.07, 0.30), "frame", (0, y, 0.17))
    pv = part("bench_back"); pv.parent = p; pv.location = (0, 0.19, 0.46)
    box("back", pv, (0.30, 0.74, 0.09), "pad", (0, 0.38, 0.0))
    box("back_trim", pv, (0.32, 0.76, 0.03), "grip", (0, 0.38, -0.05))
    box("brace", pv, (0.06, 0.45, 0.05), "frame", (0, 0.28, -0.10))
    return p


def cable_tower():
    """Cable machine: base, two posts, a slotted front column with the weight stack (slabs + selector pin), a top pulley,
    and a sliding carriage (P_cable_pulley) with a pulley and a hook. The cable is drawn per pose."""
    p = part("cable_tower")
    box("base", p, (1.00, 0.95, 0.07), "frame", (0, 0.30, 0.035))
    for s in (-1, 1):
        box("post", p, (0.12, 0.14, 2.25), "frame", (s * 0.46, 0, 1.12))
        box("brace", p, (0.07, 0.60, 0.07), "frame", (s * 0.46, 0.30, 0.15), (0, 0, 0))
    box("top", p, (1.04, 0.16, 0.12), "frame", (0, 0, 2.25))
    box("rail", p, (0.05, 0.05, 1.95), "steel", (-0.30, -0.02, 1.15))
    box("rail", p, (0.05, 0.05, 1.95), "steel", (0.30, -0.02, 1.15))
    # weight stack behind the posts: 12 slabs, with a selector pin in one of them
    for i in range(12):
        box("slab", p, (0.46, 0.30, 0.095), "plate", (0, 0.42, 0.20 + i * 0.105))
    box("stack_rod", p, (0.05, 0.05, 1.50), "steel", (0, 0.42, 0.95))
    box("pin", p, (0.07, 0.34, 0.05), "accent", (0, 0.42, 0.20 + 5 * 0.105 + 0.07))
    box("cover", p, (0.56, 0.05, 1.55), "pad", (0, 0.14, 0.97))
    cyl("top_pulley", p, 0.09, 0.05, "X", "accent", (0, -0.02, 2.17), 10)
    box("hole_plate", p, (0.20, 0.03, 1.60), "grip", (0, -0.075, 1.10))
    pu = part("cable_pulley"); pu.parent = p; pu.location = (0, -0.12, 1.20)
    box("carriage", pu, (0.62, 0.10, 0.12), "steel", (0, 0.04, 0))
    cyl("pulley", pu, 0.07, 0.04, "X", "accent", (0, -0.03, 0), 10)
    box("hook", pu, (0.03, 0.03, 0.09), "grip", (0, -0.06, -0.11))
    return p


def handle_straight():
    p = part("handle_straight"); cyl("bar", p, 0.016, 0.55, "X", "grip", sides=8)
    for s in (-1, 1): box("end", p, (0.04, 0.04, 0.10), "steel", (s * 0.26, 0, 0.05))
    box("ring", p, (0.08, 0.03, 0.03), "steel", (0, 0, 0.10))
    return p


def handle_rope():
    p = part("handle_rope")
    for s in (-1, 1):
        cyl("rope", p, 0.022, 0.30, "Z", "grip", (s * 0.06, 0, -0.15), 6)
        cyl("stop", p, 0.035, 0.03, "Z", "accent", (s * 0.06, 0, -0.30), 6)
    box("top", p, (0.16, 0.04, 0.04), "steel", (0, 0, 0))
    return p


def handle_d():
    p = part("handle_d"); cyl("grip", p, 0.018, 0.14, "X", "grip", sides=8)
    box("loop", p, (0.16, 0.025, 0.05), "steel", (0, 0, 0.04))
    for s in (-1, 1): box("side", p, (0.02, 0.025, 0.08), "steel", (s * 0.075, 0, 0.02))
    return p


def smith():
    """Smith machine: two guide rods in a frame with long feet, top beam, safety catches, and a bar on sliders (P_smith_bar)."""
    p = part("smith")
    for s in (-1, 1):
        box("post", p, (0.10, 0.10, 2.30), "frame", (s * 0.66, 0, 1.15))
        cyl("rod", p, 0.018, 2.15, "Z", "steel", (s * 0.66, -0.07, 1.14), 8)
        box("foot", p, (0.14, 1.10, 0.07), "frame", (s * 0.66, 0.15, 0.035))
        for i in range(6):
            box("catch", p, (0.07, 0.10, 0.04), "accent" if i == 1 else "steel", (s * 0.66, -0.07, 0.35 + i * 0.30))
        box("brace", p, (0.06, 0.55, 0.06), "frame", (s * 0.66, 0.30, 1.30), (-35, 0, 0))
    box("top", p, (1.46, 0.12, 0.12), "frame", (0, 0, 2.30))
    sb = part("smith_bar"); sb.parent = p; sb.location = (0, -0.12, 1.20)
    cyl("bar", sb, 0.016, 1.80, "X", "steel", sides=8)
    for s in (-1, 1):
        box("slider", sb, (0.10, 0.12, 0.16), "accent", (s * 0.66, 0.04, 0))
        for i, r in enumerate((0.22, 0.22, 0.17)):
            cyl("plate", sb, r, 0.032, "X", "plate", (s * (0.80 + i * 0.045), 0, 0), 12)
    return p


def pullup_bar():
    p = part("pullup_bar")
    for s in (-1, 1):
        box("post", p, (0.09, 0.09, 2.45), "frame", (s * 0.60, 0, 1.225))
        box("foot", p, (0.12, 0.80, 0.06), "frame", (s * 0.60, 0.10, 0.03))
        box("arm", p, (0.09, 0.30, 0.09), "frame", (s * 0.60, -0.15, 2.38))
    cyl("bar", p, 0.017, 1.20, "X", "steel", (0, -0.28, 2.38), 8)
    for s in (-1, 1): cyl("grip", p, 0.022, 0.18, "X", "grip", (s * 0.40, -0.28, 2.38), 8)
    return p


BUILD = [("barbell", barbell), ("bar", plain_bar), ("dumbbell", dumbbell), ("ez_bar", ez_bar), ("bench", bench),
         ("cable_tower", cable_tower), ("handle_straight", handle_straight), ("handle_rope", handle_rope),
         ("handle_d", handle_d), ("smith", smith), ("pullup_bar", pullup_bar)]


def build_all():
    old = bpy.data.collections.get("Kit")
    if old:
        for o in list(old.objects): bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new("Kit"); bpy.context.scene.collection.children.link(col)
    return {n: f() for n, f in BUILD}
