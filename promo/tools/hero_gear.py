"""Reusable hero head-gear builder (Varsity-W baseball cap + silver AirPods Max).

Fits any WatchCoach character rig using per-model skull measurements relative to the
rest-pose `head` bone (approach (b): per-model parametric fitting, 0 mm body mesh edits).
Cap and headset are attached under separate bone-parented empties so either piece can be
toggled independently in Blender's Outliner or via `set_gear(arm, cap=..., headset=...)`.
"""
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import wc_lib as W

# Legacy V6 constants kept for backwards compatibility with reel_gym.py callers.
APM_YE, APM_ZE = -0.095, 1.607
APM_XIN, APM_TILT = 0.0663, 0.20
APM_SQ = 3.2

# ------------------------------------------------------------------ per-model fit table
# All coordinates are in armature-local rest space (meters, +Z up, character faces -Y).
# Characters with uniform armature object scale (trainer_188: 1.0817, extra_blue..green:
# 0.943..1.046) inherit that uniform scale cleanly through the `head` bone parent.

_V6_FIT = {
    "family": "v6",
    "cap_rx": 0.0880,
    "cap_ry": 0.1000,
    "cap_cy": -0.1060,
    "cap_zb": 1.6800,
    "cap_drop": 0.0160,
    "cap_zt": 1.7520,
    "cap_p": 2.8,
    "visor_tuck": 0.0032,
    "visor_len": 0.0810,
    "visor_drop_mid": 0.0110,
    "visor_drop_side": 0.0520,
    "w_height": 0.0340,
    "w_zc": 1.7130,
    "apm_ye": -0.0950,
    "apm_ze": 1.6070,
    "apm_xin": 0.0663,
    "apm_tilt": 0.200,
    "apm_scale": 1.000,
    "apm_sq": 3.2,
    "apm_rail_lift": 0.0200,
    "arm_scale_ref": 1.0000,
}

_ROOKIE_FIT = {
    "family": "rookie_male",
    "cap_rx": 0.0835,
    "cap_ry": 0.1040,
    "cap_cy": -0.0833,
    "cap_zb": 1.6860,
    "cap_drop": 0.0160,
    "cap_zt": 1.7620,
    "cap_p": 2.8,
    "visor_tuck": 0.0020,
    "visor_len": 0.0810,
    "visor_drop_mid": 0.0110,
    "visor_drop_side": 0.0520,
    "w_height": 0.0340,
    "w_zc": 1.7210,
    "apm_ye": -0.0920,
    "apm_ze": 1.6150,
    "apm_xin": 0.0802,
    "apm_tilt": 0.140,
    "apm_scale": 1.000,
    "apm_sq": 3.2,
    "apm_rail_lift": 0.0200,
    "arm_scale_ref": 1.0000,
}

_FEMALE_FIT = {
    "family": "extra_female",
    "cap_rx": 0.0680,
    "cap_ry": 0.0865,
    "cap_cy": -0.0800,
    "cap_zb": 1.5550,
    "cap_drop": 0.0140,
    "cap_zt": 1.6210,
    "cap_p": 2.8,
    "visor_tuck": 0.0020,
    "visor_len": 0.0720,
    "visor_drop_mid": 0.0100,
    "visor_drop_side": 0.0460,
    "w_height": 0.0295,
    "w_zc": 1.5855,
    "apm_ye": -0.0880,
    "apm_ze": 1.4950,
    "apm_xin": 0.0630,
    "apm_tilt": 0.220,
    "apm_scale": 0.920,
    "apm_sq": 3.2,
    "apm_rail_lift": 0.0185,
    "arm_scale_ref": 1.0000,
}

MODEL_FITS = {
    "v6": dict(_V6_FIT, arm_scale_ref=1.0000),
    "trainer_188": dict(_V6_FIT, arm_scale_ref=1.0817),
    "hero_rookie": dict(_ROOKIE_FIT, arm_scale_ref=1.0000),
    "extra_female": dict(_FEMALE_FIT, arm_scale_ref=1.0000),
    "extra_red": dict(_ROOKIE_FIT, arm_scale_ref=1.0000),
    "extra_yellow": dict(_ROOKIE_FIT, arm_scale_ref=1.0286),
    "extra_gray": dict(_ROOKIE_FIT, arm_scale_ref=0.9829),
    "extra_blue": dict(_ROOKIE_FIT, arm_scale_ref=0.9429),
    "extra_green": dict(_ROOKIE_FIT, arm_scale_ref=1.0457),
}


# ------------------------------------------------------------------ skull measurement & auto-fit

def find_body_mesh(arm):
    """Return the rigged body mesh child of `arm`, or None."""
    for child in arm.children:
        if child.type == "MESH" and any(m.type == "ARMATURE" for m in child.modifiers):
            return child
    for child in arm.children:
        if child.type == "MESH" and child.vertex_groups.get("head"):
            return child
    return None


def measure_head(arm, body=None):
    """Measure rest-pose cranium landmarks (forehead, occiput, crown, ears) in armature-local space."""
    body = body or find_body_mesh(arm)
    if body is None:
        raise ValueError(f"No rigged body mesh found under armature {arm.name!r}")
    hvg = body.vertex_groups.get("head")
    if hvg is None:
        raise ValueError(f"Body mesh {body.name!r} has no 'head' vertex group")

    hpts = [
        v.co.copy()
        for v in body.data.vertices
        if any(g.group == hvg.index and g.weight >= 0.5 for g in v.groups)
    ]
    z_top = max(p.z for p in hpts)
    z_bot = min(p.z for p in hpts)
    head_h = z_top - z_bot

    # Build a local-space BVH directly from rest mesh data (independent of object scale/pose)
    verts = [v.co.copy() for v in body.data.vertices]
    polys = [list(p.vertices) for p in body.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)

    upper = [p for p in hpts if p.z >= z_top - head_h * 0.42]
    cy0 = (min(p.y for p in upper) + max(p.y for p in upper)) * 0.5

    # Forehead / occiput / side at cap sweatband height (~26% down from crown)
    z_band = z_top - head_h * 0.26
    hf = bvh.ray_cast(Vector((0.0, -0.5, z_band)), Vector((0.0, 1.0, 0.0)), 1.0)
    hb = bvh.ray_cast(Vector((0.0, 0.5, z_band)), Vector((0.0, -1.0, 0.0)), 1.0)
    hl = bvh.ray_cast(Vector((0.5, cy0, z_band)), Vector((-1.0, 0.0, 0.0)), 1.0)

    y_front = hf[0].y if hf[0] is not None else min(p.y for p in upper)
    y_back = hb[0].y if hb[0] is not None else max(p.y for p in upper)
    x_side = hl[0].x if hl[0] is not None else max(abs(p.x) for p in upper)

    # Ear center (~53% down from crown) and side slope
    z_ear = z_top - head_h * 0.53
    h_ear_u = bvh.ray_cast(Vector((0.5, cy0, z_ear + 0.025)), Vector((-1.0, 0.0, 0.0)), 1.0)
    h_ear_m = bvh.ray_cast(Vector((0.5, cy0, z_ear)), Vector((-1.0, 0.0, 0.0)), 1.0)
    h_ear_d = bvh.ray_cast(Vector((0.5, cy0, z_ear - 0.025)), Vector((-1.0, 0.0, 0.0)), 1.0)
    x_ear = h_ear_m[0].x if h_ear_m[0] is not None else x_side * 0.92
    if h_ear_u[0] is not None and h_ear_d[0] is not None:
        slope = max(0.08, min(0.32, (h_ear_u[0].x - h_ear_d[0].x) / 0.050))
    else:
        slope = 0.18

    head_bone = arm.data.bones.get("head")
    return {
        "head_bone_head": list(head_bone.head_local) if head_bone else [0.0, 0.0, z_bot],
        "head_bone_tail": list(head_bone.tail_local) if head_bone else [0.0, 0.0, z_top],
        "z_bot": z_bot,
        "z_top": z_top,
        "head_h": head_h,
        "y_front": y_front,
        "y_back": y_back,
        "cy": (y_front + y_back) * 0.5,
        "x_side": x_side,
        "z_band": z_band,
        "y_ear": cy0 - 0.005,
        "z_ear": z_ear,
        "x_ear": x_ear,
        "side_slope": slope,
        "arm_scale": float(arm.scale.x),
    }


def fit_from_head(metrics):
    """Derive cap & AirPods Max parameters automatically from `measure_head()` output."""
    s = metrics["head_h"] / 0.2240
    z_top = metrics["z_top"]
    zb = metrics["z_band"]
    zt = z_top + 0.011 * min(1.15, max(0.85, s))
    rx = metrics["x_side"] + 0.0032
    ry = (metrics["y_back"] - metrics["y_front"]) * 0.5 + 0.0032
    cy = (metrics["y_front"] + metrics["y_back"]) * 0.5
    apm_scale = max(0.88, min(1.05, metrics["head_h"] / 0.240))
    return {
        "family": "auto",
        "cap_rx": round(rx, 4),
        "cap_ry": round(ry, 4),
        "cap_cy": round(cy, 4),
        "cap_zb": round(zb, 4),
        "cap_drop": round(0.015 * min(1.1, max(0.85, s)), 4),
        "cap_zt": round(zt, 4),
        "cap_p": 2.8,
        "visor_tuck": 0.0020,
        "visor_len": round(0.081 * min(1.0, max(0.85, apm_scale)), 4),
        "visor_drop_mid": round(0.011 * min(1.0, max(0.85, apm_scale)), 4),
        "visor_drop_side": round(0.052 * min(1.0, max(0.85, apm_scale)), 4),
        "w_height": round(0.034 * min(1.0, max(0.85, apm_scale)), 4),
        "w_zc": round(zb + 0.46 * (zt - zb), 4),
        "apm_ye": round(metrics["y_ear"], 4),
        "apm_ze": round(metrics["z_ear"], 4),
        "apm_xin": round(metrics["x_ear"] + 0.0018, 4),
        "apm_tilt": round(metrics["side_slope"], 3),
        "apm_scale": round(apm_scale, 3),
        "apm_sq": 3.2,
        "apm_rail_lift": round(0.020 * min(1.0, max(0.90, apm_scale)), 4),
        "arm_scale_ref": round(metrics["arm_scale"], 4),
    }


def resolve_fit(arm, body=None, profile=None):
    """Return `(profile_name, fit_dict)` for an armature."""
    if isinstance(profile, dict):
        return profile.get("family", "custom"), dict(profile)
    if isinstance(profile, str) and profile in MODEL_FITS:
        return profile, dict(MODEL_FITS[profile])

    name = arm.name.lower()
    if "trainer_188" in name:
        return "trainer_188", dict(MODEL_FITS["trainer_188"])
    if "female" in name:
        return "extra_female", dict(MODEL_FITS["extra_female"])
    if "rookie" in name:
        return "hero_rookie", dict(MODEL_FITS["hero_rookie"])
    for role in ("red", "yellow", "gray", "blue", "green"):
        if f"extra_{role}" in name:
            return f"extra_{role}", dict(MODEL_FITS[f"extra_{role}"])
    if "v5_commonrig" in name or name == "guy" or "v6" in name or "selfie guy" in name:
        return "v6", dict(MODEL_FITS["v6"])

    body = body or find_body_mesh(arm)
    if body is not None:
        vc = len(body.data.vertices)
        if vc == 1401:
            return "v6", dict(MODEL_FITS["v6"])
        metrics = measure_head(arm, body)
        if vc == 2452 and abs(metrics["z_top"] - 1.75) < 0.02:
            return "hero_rookie", dict(MODEL_FITS["hero_rookie"])
        if vc == 2452 and abs(metrics["z_top"] - 1.61) < 0.02:
            return "extra_female", dict(MODEL_FITS["extra_female"])
        return "auto", fit_from_head(metrics)

    return "v6", dict(MODEL_FITS["v6"])


# ------------------------------------------------------------------ geometry helpers

def _smooth_mesh(obj):
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def _assign_box_uv(bm):
    """Assign clean non-zero cubic-projected UVs in bmesh so QA reports valid UVs."""
    uv_layer = bm.loops.layers.uv.verify()
    scale = 10.0
    for f in bm.faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                loop[uv_layer].uv = (co.x * scale + 0.5, co.y * scale + 0.5)
            elif ax >= ay:
                loop[uv_layer].uv = (co.y * scale + 0.5, co.z * scale + 0.5)
            else:
                loop[uv_layer].uv = (co.x * scale + 0.5, co.z * scale + 0.5)


def _ensure_outward_normals(bm):
    """Recalculate normals and guarantee positive signed volume for closed shells."""
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.faces.ensure_lookup_table()
    # Only flip if the whole mesh is closed (no boundary edges) and signed volume is negative
    if all(len(e.link_faces) == 2 for e in bm.edges) and bm.faces:
        vol = bm.calc_volume(signed=True)
        if vol < 0.0:
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))


def _piping(name, points, radius, material, collection, parent):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, xyz in zip(spline.points, points):
        point.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.parent = parent
    curve.materials.append(material)
    return obj


def _tag_name(prefix, base):
    return f"{prefix}{base}" if prefix else base


# ------------------------------------------------------------------ cap + Varsity W patch

def _cap_varsity_w(collection, head, crown_obj, height=0.034, zc=1.713, prefix=""):
    """Collegiate slab-serif W (Rockwell Bold outline, promo/parts/cap_logo_w.json) as a layered twill patch
    on the cap front: cream backing, cap-tone outline ring, cream letter. Projected onto the crown along +Y."""
    contours = json.load(open(Path(W.PARTS) / "cap_logo_w.json"))["contours"]
    cream = W.mat("Varsity patch cream", (0.80, 0.76, 0.66), rough=0.86)
    ring = W.mat("Varsity patch outline", (0.030, 0.032, 0.031), rough=0.9)
    bvh = BVHTree.FromPolygons(
        [v.co for v in crown_obj.data.vertices],
        [p.vertices for p in crown_obj.data.polygons],
    )
    dg = bpy.context.evaluated_depsgraph_get()
    created = []
    # name, outline offset, material, lift off the cap, thickness
    for base, off, mat, lift, thick in (
        ("Varsity W backing", 0.0019, cream, 0.0002, 0.0006),
        ("Varsity W outline", 0.0011, ring, 0.0007, 0.0005),
        ("Varsity W letter", 0.0, cream, 0.0011, 0.0006),
    ):
        name = _tag_name(prefix, base)
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions, cu.fill_mode, cu.offset, cu.extrude = "2D", "BOTH", off / height, thick / 2
        for c in contours:
            sp = cu.splines.new("POLY")
            sp.points.add(len(c) - 1)
            for pt, (x, y) in zip(sp.points, c):
                pt.co = (x, y, 0, 1)
            sp.use_cyclic_u = True
        tmp = bpy.data.objects.new(name + " tmp", cu)
        collection.objects.link(tmp)
        dg.update()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
        bpy.data.objects.remove(tmp)
        bpy.data.curves.remove(cu)

        bm = bmesh.new()
        bm.from_mesh(me)
        # Weld curve extrude shells before scaling/projecting so the patch is a clean closed shell
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.scale(bm, vec=(height, height, 1.0), verts=bm.verts)
        step = 0.0018
        for k in range(-16, 17):
            g = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=g, plane_co=(k * step, 0, 0), plane_no=(1, 0, 0))
        for k in range(-10, 11):
            g = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=g, plane_co=(0, k * step, 0), plane_no=(0, 1, 0))
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-5)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
        for v in bm.verts:
            u, w, z = v.co
            hit = bvh.ray_cast(Vector((u, -0.6, zc + w)), Vector((0, 1, 0)))
            if hit[0] is None:
                hit = bvh.find_nearest(Vector((u, -0.2, zc + w)))
            n = hit[1] if hit[1].y < 0 else -hit[1]
            v.co = hit[0] + n * (lift + z + thick / 2)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
        # Remove any tiny zero-area sliver faces left by curve offset self-pinch before normal recalc
        tiny = [f for f in bm.faces if f.calc_area() < 1e-10]
        if tiny:
            bmesh.ops.delete(bm, geom=tiny, context="FACES")
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        _ensure_outward_normals(bm)
        _assign_box_uv(bm)
        bm.to_mesh(me)
        bm.free()

        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        ob.parent = head
        me.materials.clear()
        me.materials.append(mat)
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(40))
        created.append(ob)
    return created


def _twill_material():
    twill = W.mat("Washed charcoal twill", (0.029, 0.031, 0.030), rough=0.9)
    nodes = twill.node_tree.nodes
    if not nodes.get("Woven grain"):
        coords = nodes.new("ShaderNodeTexCoord")
        grain = nodes.new("ShaderNodeTexNoise")
        grain.name = "Woven grain"
        grain.inputs["Scale"].default_value = 1750
        grain.inputs["Detail"].default_value = 2
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.18
        bump.inputs["Distance"].default_value = 0.00016
        links = twill.node_tree.links
        links.new(coords.outputs["Object"], grain.inputs["Vector"])
        links.new(grain.outputs["Fac"], bump.inputs["Height"])
        surface = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
        links.new(bump.outputs["Normal"], surface.inputs["Normal"])
        dye = nodes.new("ShaderNodeValToRGB")
        dye.color_ramp.elements[0].color = (0.018, 0.019, 0.018, 1)
        dye.color_ramp.elements[1].color = (0.048, 0.049, 0.046, 1)
        links.new(grain.outputs["Fac"], dye.inputs["Fac"])
        links.new(dye.outputs["Color"], surface.inputs["Base Color"])
    return twill


def build_cap(collection, head, fit=None, *, prefix="", with_varsity_w=True):
    """Build the charcoal six-panel baseball cap (+ Varsity W patch) fitted by `fit`.
    Returns `(crown_obj, created_objects)`."""
    fit = fit or _V6_FIT
    twill = _twill_material()
    thread = W.mat("Charcoal topstitch", (0.048, 0.049, 0.046), rough=0.9)
    under = W.mat("Charcoal underbill", (0.021, 0.022, 0.021), rough=0.94)

    cap_rx = fit["cap_rx"]
    cap_ry = fit["cap_ry"]
    cap_cy = fit["cap_cy"]
    cap_zb = fit["cap_zb"]
    cap_drop = fit["cap_drop"]
    cap_zt = fit["cap_zt"]
    cap_p = fit["cap_p"]
    visor_tuck = fit.get("visor_tuck", 0.0032)
    visor_len = fit.get("visor_len", 0.081)
    visor_drop_mid = fit.get("visor_drop_mid", 0.011)
    visor_drop_side = fit.get("visor_drop_side", 0.052)

    def crown(angle, elevation):
        r = math.cos(elevation) ** (2 / cap_p)
        side = math.cos(angle)
        base = cap_zb - cap_drop * side ** 2
        z = base + (cap_zt - base) * math.sin(elevation) ** (2 / cap_p)
        folds = math.sin(6 * angle + 0.55 * math.sin(3 * angle)) ** 8
        r *= 1 - 0.022 * folds * math.exp(-((elevation - 0.24) / 0.24) ** 2)
        return Vector((cap_rx * r * side, cap_cy + cap_ry * r * math.sin(angle), z))

    def loft(base_name, rings, materials, bottom_index=0):
        bm = bmesh.new()
        loops = [[bm.verts.new(point) for point in row] for row in rings]
        count = len(loops[0])
        for a, b in zip(loops, loops[1:]):
            for i in range(count):
                j = (i + 1) % count
                bm.faces.new((a[i], a[j], b[j], b[i]))
        bm.faces.new(loops[0]).material_index = bottom_index
        bm.faces.new(loops[-1])
        _ensure_outward_normals(bm)
        _assign_box_uv(bm)
        obj = W.mesh_obj(_tag_name(prefix, base_name), bm, materials[0], collection, parent=head)
        for mat in materials[1:]:
            obj.data.materials.append(mat)
        return _smooth_mesh(obj)

    created = []
    angles = [i * math.tau / 96 for i in range(96)]
    elevations = [i * 1.558 / 24 for i in range(25)]
    crown_obj = loft("Soft six panel cap", [[crown(a, e) for a in angles] for e in elevations], [twill])
    created.append(crown_obj)

    for i in range(6):
        a = math.pi / 6 + i * math.pi / 3
        created.append(
            _piping(_tag_name(prefix, "Felled panel seam"), [crown(a, e) for e in elevations], 0.00048, thread, collection, head)
        )
    created.append(
        _piping(_tag_name(prefix, "Bound lower edge"), [crown(a, 0.016) for a in angles + [math.tau]], 0.00085, twill, collection, head)
    )

    # Visor inner seam tucks cleanly into the crown without penetrating the forehead, while keeping tip length exact.
    len_eff = visor_len - (0.005 - visor_tuck)

    def bill(u, v):
        angle = -math.pi / 2 + u * 1.19
        p = crown(angle, 0.036)
        extent = max(0.012, math.cos(u * math.pi / 2)) ** 0.67
        p.y += visor_tuck - v * len_eff * extent
        p.x += u * 0.006 * v * extent
        p.z -= v * (visor_drop_mid + visor_drop_side * u * u) * extent
        return p

    bm = bmesh.new()
    grids = []
    for layer in (0, 1):
        grid = []
        for j in range(17):
            row = []
            for i in range(65):
                p = bill(i / 32 - 1, j / 16)
                p.z -= layer * 0.0032
                row.append(bm.verts.new(p))
            grid.append(row)
        for j in range(16):
            for i in range(64):
                bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])).material_index = layer
        grids.append(grid)

    def rim(grid):
        return grid[0] + [row[-1] for row in grid[1:]] + grid[-1][-2::-1] + [row[0] for row in grid[-2:0:-1]]

    top, bottom = map(rim, grids)
    for i in range(len(top)):
        bm.faces.new((top[i - 1], top[i], bottom[i], bottom[i - 1])).material_index = 1
    _ensure_outward_normals(bm)
    _assign_box_uv(bm)
    brim = W.mesh_obj(_tag_name(prefix, "Rolled crescent visor"), bm, twill, collection, parent=head)
    brim.data.materials.append(under)
    bevel = brim.modifiers.new("Soft fabric edge", "BEVEL")
    bevel.width = 0.001
    bevel.segments = 3
    _smooth_mesh(brim)
    created.append(brim)

    for v in (0.81, 0.91):
        created.append(
            _piping(
                _tag_name(prefix, "Visor stitch"),
                [bill(i / 40, v) + Vector((0, 0, 0.00014)) for i in range(-38, 39)],
                0.00037,
                thread,
                collection,
                head,
            )
        )

    if with_varsity_w:
        created.extend(
            _cap_varsity_w(
                collection,
                head,
                crown_obj,
                height=fit["w_height"],
                zc=fit["w_zc"],
                prefix=prefix,
            )
        )
    return crown_obj, created


# ------------------------------------------------------------------ AirPods Max (silver)

def _apm_knit(name, color, groove=0.62, cell=0.0011):
    """AirPods Max knit mesh: fine 3D sine lattice of raised knit beads (~1.1 mm)."""
    m = W.mat(name, color, rough=0.9)
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    if nodes.get("Knit lattice"):
        return m
    shader = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    co = nodes.new("ShaderNodeTexCoord")
    k = math.tau / (2 * cell)
    waves = []
    for d in ((1, 1, 1), (1, -1, 1), (1, 1, -1)):
        dot = nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        dot.inputs[1].default_value = Vector(d).normalized()
        links.new(co.outputs["Object"], dot.inputs[0])
        mul = nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = k
        links.new(dot.outputs["Value"], mul.inputs[0])
        sin = nodes.new("ShaderNodeMath")
        sin.operation = "SINE"
        links.new(mul.outputs[0], sin.inputs[0])
        waves.append(sin)
    acc = None
    for i, j in ((0, 1), (0, 2), (1, 2)):
        pr = nodes.new("ShaderNodeMath")
        pr.operation = "MULTIPLY"
        links.new(waves[i].outputs[0], pr.inputs[0])
        links.new(waves[j].outputs[0], pr.inputs[1])
        ab = nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        links.new(pr.outputs[0], ab.inputs[0])
        if acc is None:
            acc = ab
        else:
            ad = nodes.new("ShaderNodeMath")
            ad.operation = "ADD"
            links.new(acc.outputs[0], ad.inputs[0])
            links.new(ab.outputs[0], ad.inputs[1])
            acc = ad
    h = nodes.new("ShaderNodeMath")
    h.operation = "MULTIPLY"
    h.inputs[1].default_value = 0.5
    h.name = "Knit lattice"
    h.use_clamp = True
    links.new(acc.outputs[0], h.inputs[0])
    fuzz = nodes.new("ShaderNodeTexNoise")
    fuzz.inputs["Scale"].default_value = 5200
    links.new(co.outputs["Object"], fuzz.inputs["Vector"])
    mix = nodes.new("ShaderNodeMath")
    mix.operation = "MULTIPLY_ADD"
    mix.inputs[1].default_value = 0.85
    links.new(h.outputs[0], mix.inputs[0])
    fz = nodes.new("ShaderNodeMath")
    fz.operation = "MULTIPLY"
    fz.inputs[1].default_value = 0.15
    links.new(fuzz.outputs["Fac"], fz.inputs[0])
    links.new(fz.outputs[0], mix.inputs[2])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.00035
    links.new(mix.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*[c * groove for c in color], 1)
    ramp.color_ramp.elements[1].color = (*color, 1)
    ramp.color_ramp.elements[1].position = 0.75
    links.new(mix.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    if "Sheen Weight" in shader.inputs:
        shader.inputs["Sheen Weight"].default_value = 0.4
    return m


def _apm_ring(a, b, n=72, e=APM_SQ):
    out = []
    for i in range(n):
        t = math.tau * i / n
        c, s = math.cos(t), math.sin(t)
        out.append((math.copysign(a * abs(c) ** (2 / e), c), math.copysign(b * abs(s) ** (2 / e), s)))
    return out


def _apm_loft(name, rings, mats, collection, parent, close_first=True, close_last=True, first_mat=0, apex=None):
    bm = bmesh.new()
    loops = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(loops[0])
    for a, b in zip(loops, loops[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if close_first:
        bm.faces.new(loops[0]).material_index = first_mat
    if apex is not None:
        tip = bm.verts.new(apex)
        for i in range(n):
            bm.faces.new((loops[-1][i], loops[-1][(i + 1) % n], tip))
    elif close_last:
        bm.faces.new(loops[-1])
    _ensure_outward_normals(bm)
    _assign_box_uv(bm)
    ob = W.mesh_obj(name, bm, mats[0], collection, parent=parent)
    for m in mats[1:]:
        ob.data.materials.append(m)
    return _smooth_mesh(ob)


def _apm_solid(name, bm, mat, collection, parent, bevel=None):
    _ensure_outward_normals(bm)
    _assign_box_uv(bm)
    ob = W.mesh_obj(name, bm, mat, collection, parent=parent)
    if bevel:
        mod = ob.modifiers.new("Soft edge", "BEVEL")
        mod.width, mod.segments, mod.limit_method = bevel, 3, "ANGLE"
    return _smooth_mesh(ob)


def _apm_cylinder(name, start, end, radius, mat, collection, parent, seg=40, bevel=None):
    a, b = Vector(start), Vector(end)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=radius, radius2=radius, depth=(b - a).length)
    rot = (b - a).to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=bm.verts)
    ob = _apm_solid(name, bm, mat, collection, parent, bevel)
    axis = (b - a).normalized()
    for p in ob.data.polygons:
        p.use_smooth = abs(p.normal.dot(axis)) < 0.5
    return ob


def build_airpods_max(collection, head, crown_obj=None, fit=None, *, prefix=""):
    """Build silver AirPods Max worn over the fitted cap (or bare head if `crown_obj` is None).
    Returns list of created objects."""
    fit = fit or _V6_FIT
    alu = W.mat("AirPods Max silver aluminum", (0.90, 0.905, 0.91), rough=0.42, metal=1.0)
    frame = W.mat("AirPods Max silver frame", (0.66, 0.67, 0.68), rough=0.36, metal=0.65)
    steel = W.mat("AirPods Max polished steel", (0.93, 0.93, 0.93), rough=0.09, metal=1.0)
    knit = _apm_knit("AirPods Max white knit", (0.72, 0.73, 0.73))
    scrim = _apm_knit("AirPods Max inner scrim", (0.24, 0.25, 0.26), groove=0.45, cell=0.0007)
    slot = W.mat("AirPods Max mic slot", (0.012, 0.012, 0.014), rough=0.6)

    apm_ye = fit["apm_ye"]
    apm_ze = fit["apm_ze"]
    apm_xin = fit["apm_xin"]
    apm_tilt = fit["apm_tilt"]
    sc = fit.get("apm_scale", 1.0)
    apm_sq = fit.get("apm_sq", APM_SQ)
    rail_lift = fit.get("apm_rail_lift", 0.020)

    c, s = 1 / math.hypot(1, apm_tilt), apm_tilt / math.hypot(1, apm_tilt)

    def to_side(sign, u, y, w):
        u, y, w = u * sc, y * sc, w * sc
        return Vector((sign * (apm_xin + u * c + w * s), apm_ye + y, apm_ze - u * s + w * c))

    def side_rings(sign, profile):
        return [[to_side(sign, u, y, w) for y, w in _apm_ring(a, b, e=apm_sq)] for u, a, b in profile]

    cushion = [
        (0.0150, 0.0170, 0.0270),
        (0.0050, 0.0188, 0.0288),
        (0.0012, 0.0210, 0.0312),
        (0.0000, 0.0245, 0.0350),
        (0.0004, 0.0295, 0.0398),
        (0.0025, 0.0335, 0.0438),
        (0.0070, 0.0362, 0.0465),
        (0.0140, 0.0374, 0.0477),
        (0.0230, 0.0372, 0.0475),
    ]
    cup = [
        (0.0200, 0.0372, 0.0472),
        (0.0215, 0.0398, 0.0498),
        (0.0245, 0.0409, 0.0509),
        (0.0330, 0.0412, 0.0512),
        (0.0405, 0.0404, 0.0504),
        (0.0455, 0.0384, 0.0484),
        (0.0488, 0.0350, 0.0450),
        (0.0505, 0.0300, 0.0400),
        (0.0513, 0.0220, 0.0320),
        (0.0516, 0.0120, 0.0180),
    ]

    def w_top(y, a=0.0405, b=0.0505):
        return b * max(0.0, 1 - (abs(y) / a) ** apm_sq) ** (1 / apm_sq)

    created = []
    stems = {}
    for sign, tag in ((1, "L"), (-1, "R")):
        created.append(
            _apm_loft(
                _tag_name(prefix, f"AirPodsMax_Cushion_{tag}"),
                side_rings(sign, cushion),
                [knit, scrim],
                collection,
                head,
                first_mat=1,
            )
        )
        created.append(
            _apm_loft(
                _tag_name(prefix, f"AirPodsMax_Cup_{tag}"),
                side_rings(sign, cup),
                [alu],
                collection,
                head,
                apex=to_side(sign, 0.0518, 0, 0),
            )
        )
        j0, j1 = to_side(sign, 0.040, 0, w_top(0) - 0.0015), to_side(sign, 0.040, 0, w_top(0) + 0.0062)
        created.append(
            _apm_cylinder(_tag_name(prefix, f"AirPodsMax_Swivel_{tag}"), j0, j1, 0.0047 * sc, steel, collection, head, bevel=0.0006 * sc)
        )
        stems[sign] = j1

        ring = _apm_ring(0.0393, 0.0493, 400, e=apm_sq)
        k = int(0.63 * 400 / 2)
        (y0, w0), (y1, w1) = ring[k - 1], ring[k + 1]
        tan = Vector((0, y1 - y0, w1 - w0)).normalized()
        nrm = (
            Vector((0, -tan.z, tan.y))
            if (ring[k][0] * -tan.z + ring[k][1] * tan.y) > 0
            else Vector((0, tan.z, -tan.y))
        )
        ctr = Vector((0.044, ring[k][0], ring[k][1]))
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1)
        for v in bm.verts:
            q = ctr + Vector((v.co.x * 0.0014, 0, 0)) + nrm * (v.co.y * 0.0010) + tan * (v.co.z * 0.0036)
            v.co = to_side(sign, q.x, q.y, q.z)
        created.append(_apm_solid(_tag_name(prefix, f"AirPodsMax_MicSlot_{tag}"), bm, slot, collection, head))

    # Digital Crown (rear) and noise-control button (front) on top of the wearer's right cup.
    r0, r1 = to_side(-1, 0.040, 0.019, w_top(0.019) - 0.0015), to_side(-1, 0.040, 0.019, w_top(0.019) + 0.0058)
    created.append(
        _apm_cylinder(_tag_name(prefix, "AirPodsMax_DigitalCrown"), r0, r1, 0.0059 * sc, alu, collection, head, seg=48, bevel=0.0007 * sc)
    )
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=10, radius=1)
    bmesh.ops.scale(bm, vec=(0.0024, 0.0064, 0.0016), verts=bm.verts)
    for v in bm.verts:
        v.co = to_side(-1, 0.040 + v.co.x, -0.018 + v.co.y, w_top(-0.018) + 0.0002 + v.co.z)
    created.append(_apm_solid(_tag_name(prefix, "AirPodsMax_NoiseButton"), bm, alu, collection, head))

    # Headband arch over the cap crown
    xr = abs(stems[1].x)
    zs = stems[1].z + 0.016 * sc
    crown_top_z = max(v.co.z for v in crown_obj.data.vertices) if crown_obj is not None else fit["cap_zt"]
    ztop = crown_top_z + rail_lift
    hn, hy, sep, nexp = 0.0050 * sc, 0.0040 * sc, 0.019 * sc, 2.4
    nst = 161
    st = []
    for i in range(nst):
        ph = math.pi * i / (nst - 1)
        cp, sp = math.cos(ph), math.sin(ph)
        st.append(Vector((math.copysign(xr * abs(cp) ** (2 / nexp), cp), apm_ye, zs + (ztop - zs) * sp ** (2 / nexp))))
    frames = []
    for i, p in enumerate(st):
        t = (st[min(i + 1, nst - 1)] - st[max(i - 1, 0)]).normalized()
        frames.append((p, Vector((t.z, 0, -t.x)).normalized()))
    hf = [(p.z - zs) / max(1e-6, ztop - zs) for p in st]

    def smoothstep(e0, e1, x):
        x = min(1, max(0, (x - e0) / (e1 - e0)))
        return x * x * (3 - 2 * x)

    sv = [sep * smoothstep(0.30, 0.95, h) for h in hf]
    Y = Vector((0, 1, 0))

    def section(i, yc, half_y, rad_scale=1.0):
        p, nrm = frames[i]
        return [
            p + Y * yc + nrm * (hn * rad_scale * u) + Y * (half_y * rad_scale * v)
            for u, v in _apm_ring(1, 1, 40, 4.0)
        ]

    fork = 0.55
    fa = next(i for i in range(nst) if hf[i] >= fork)
    fb = nst - 1 - fa
    created.append(
        _apm_loft(_tag_name(prefix, "AirPodsMax_Arm_L"), [section(i, 0, hy + sv[i]) for i in range(0, fa + 1)], [frame], collection, head)
    )
    created.append(
        _apm_loft(_tag_name(prefix, "AirPodsMax_Arm_R"), [section(i, 0, hy + sv[i]) for i in range(fb, nst)], [frame], collection, head)
    )
    # Start rails 0.6 mm tucked inside Arm_L/R at the fork with a smaller cross-section so no cap/wall is coplanar
    for side, tag in ((-1, "Front"), (1, "Back")):
        rings = [section(fa - 1, side * sv[fa - 1], hy, rad_scale=0.80)]
        rings.append(section(fa, side * sv[fa], hy, rad_scale=0.85))
        rings.extend(section(i, side * sv[i], hy, rad_scale=1.0) for i in range(fa + 1, fb))
        rings.append(section(fb, side * sv[fb], hy, rad_scale=0.85))
        rings.append(section(fb + 1, side * sv[fb + 1], hy, rad_scale=0.80))
        created.append(_apm_loft(_tag_name(prefix, f"AirPodsMax_Rail_{tag}"), rings, [frame], collection, head))

    for sign in (1, -1):
        top = stems[sign]
        tag = "L" if sign > 0 else "R"
        created.append(
            _apm_cylinder(
                _tag_name(prefix, f"AirPodsMax_Stem_{tag}"),
                top,
                Vector((top.x, top.y, zs + 0.002 * sc)),
                0.0022 * sc,
                steel,
                collection,
                head,
                seg=24,
            )
        )
        # Keep collar top 1.2 mm below Arm_L/R end cap at zs so cap faces are never coplanar
        created.append(
            _apm_cylinder(
                _tag_name(prefix, f"AirPodsMax_Collar_{tag}"),
                Vector((top.x, top.y, zs - 0.0062 * sc)),
                Vector((top.x, top.y, zs - 0.0012 * sc)),
                0.0062 * sc,
                steel,
                collection,
                head,
                bevel=0.0005 * sc,
            )
        )

    # Knit canopy slung between rails, settling cleanly onto the cap crown (1.8 mm clearance)
    bvh = (
        BVHTree.FromPolygons([v.co for v in crown_obj.data.vertices], [p.vertices for p in crown_obj.data.polygons])
        if crown_obj is not None
        else None
    )
    idx = list(range(fa, fb + 1))
    acc = [0.0]
    for i0, i1 in zip(idx, idx[1:]):
        acc.append(acc[-1] + (st[i1] - st[i0]).length)
    total = acc[-1]
    d = []
    for k, i in enumerate(idx):
        p, nrm = frames[i]
        if bvh is not None:
            hit = bvh.ray_cast(p, -nrm)
            req = (hit[3] - 0.0018) if hit[0] is not None else 1.0
        else:
            req = rail_lift * 0.35
        d.append([min(req, 0.45 * min(acc[k], total - acc[k])), req])
    for _ in range(6):
        d = [
            [min(req, (d[max(k - 1, 0)][0] + 2 * v + d[min(k + 1, len(d) - 1)][0]) / 4), req]
            for k, (v, req) in enumerate(d)
        ]
    rows = []
    across = 11
    for k, i in enumerate(idx):
        p, nrm = frames[i]
        wc = max(0.001, sv[i] - hy * 0.45)
        rows.append(
            [
                p
                + Y * ((j / (across - 1) - 0.5) * 2 * wc)
                - nrm * (d[k][0] + 0.0012 * (1 - (2 * j / (across - 1) - 1) ** 2) * min(1, d[k][0] / 0.004))
                for j in range(across)
            ]
        )
    bm = bmesh.new()
    grid = [[bm.verts.new(v) for v in r] for r in rows]
    for a, b in zip(grid, grid[1:]):
        for j in range(across - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # Guarantee canopy face normals point outward (+Z at crown apex) so SOLIDIFY offset=+1 grows UPWARD off the cap
    if bm.faces and sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    _assign_box_uv(bm)
    canopy = W.mesh_obj(_tag_name(prefix, "AirPodsMax_Canopy"), bm, knit, collection, parent=head)
    sol = canopy.modifiers.new("Knit thickness", "SOLIDIFY")
    sol.thickness, sol.offset = 0.0026 * sc, 1.0
    _smooth_mesh(canopy)
    created.append(canopy)
    return created


# ------------------------------------------------------------------ bone-parent attachment & visibility toggle

def _make_head_root(name, arm, collection, role):
    """Create an Empty bone-parented to `arm`'s rest-pose `head` bone so children authored in
    armature-local rest space align identically regardless of armature location, scale, or active pose."""
    root = W.empty(name, collection, size=0.06)
    root.parent = arm
    root.parent_type = "BONE"
    root.parent_bone = "head"
    hb = arm.data.bones["head"]
    rest_bone_mat = Matrix.Translation(hb.tail_local) @ hb.matrix_local.to_3x3().to_4x4()
    root.matrix_parent_inverse = rest_bone_mat.inverted()
    root.matrix_basis = Matrix.Identity(4)
    root["hero_gear_role"] = role
    return root


def _set_tree_visible(root, visible):
    hide = not bool(visible)
    for ob in (root, *root.children_recursive):
        ob.hide_viewport = hide
        ob.hide_render = hide


def remove_gear(arm):
    """Remove any hero_gear roots (and their children) currently parented to `arm`."""
    roots = [c for c in list(arm.children) if c.get("hero_gear_role") in ("cap", "headset")]
    removed = 0
    for r in roots:
        for ch in list(r.children_recursive):
            data = ch.data
            bpy.data.objects.remove(ch, do_unlink=True)
            if data and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Curve):
                    bpy.data.curves.remove(data)
            removed += 1
        bpy.data.objects.remove(r, do_unlink=True)
        removed += 1
    return removed


def attach_gear(
    arm,
    body=None,
    profile=None,
    *,
    include_cap=True,
    include_headset=True,
    show_cap=True,
    show_headset=True,
    collection=None,
    separate_collections=True,
    prefix=None,
    replace=True,
):
    """Attach fitted cap and/or AirPods Max to `arm`'s `head` bone with independent toggle roots."""
    if replace:
        remove_gear(arm)

    body = body or find_body_mesh(arm)
    profile_name, fit = resolve_fit(arm, body=body, profile=profile)
    base_prefix = prefix if prefix is not None else f"{arm.name}_"

    parent_col = collection or bpy.context.scene.collection
    if separate_collections:
        cap_col = W.coll(f"{base_prefix}Gear_Cap", parent_col) if include_cap else None
        hs_col = W.coll(f"{base_prefix}Gear_Headset", parent_col) if include_headset else None
    else:
        cap_col = parent_col
        hs_col = parent_col

    cap_root = None
    cap_objs = []
    crown_obj = None
    if include_cap:
        cap_root = _make_head_root(f"{base_prefix}Cap", arm, cap_col, "cap")
        crown_obj, cap_objs = build_cap(cap_col, cap_root, fit=fit, prefix=base_prefix)
        _set_tree_visible(cap_root, show_cap)

    hs_root = None
    hs_objs = []
    if include_headset:
        hs_root = _make_head_root(f"{base_prefix}Headset", arm, hs_col, "headset")
        hs_objs = build_airpods_max(hs_col, hs_root, crown_obj=crown_obj, fit=fit, prefix=base_prefix)
        _set_tree_visible(hs_root, show_headset)

    bpy.context.view_layer.update()
    return {
        "profile": profile_name,
        "fit": fit,
        "cap_root": cap_root,
        "headset_root": hs_root,
        "crown_obj": crown_obj,
        "cap_objects": cap_objs,
        "headset_objects": hs_objs,
    }


def set_gear(arm, cap=None, headset=None):
    """Toggle cap and/or headset visibility (both viewport & render) on `arm`."""
    found = {}
    for child in arm.children:
        role = child.get("hero_gear_role")
        if role == "cap" and cap is not None:
            _set_tree_visible(child, cap)
            found["cap"] = bool(cap)
        elif role == "headset" and headset is not None:
            _set_tree_visible(child, headset)
            found["headset"] = bool(headset)
    return found


def get_gear_roots(arm):
    """Return `{'cap': obj_or_None, 'headset': obj_or_None}` for `arm`."""
    out = {"cap": None, "headset": None}
    for child in arm.children:
        role = child.get("hero_gear_role")
        if role in out:
            out[role] = child
    return out


# ------------------------------------------------------------------ legacy wrappers for reel_gym.py

def cap(collection, head, profile="v6"):
    """Drop-in replacement for `reel_gym.cap(collection, head)` (builds V6 cap + AirPods Max)."""
    fit = dict(MODEL_FITS[profile]) if isinstance(profile, str) else dict(profile)
    crown_obj, cap_objs = build_cap(collection, head, fit=fit, prefix="")
    hs_objs = build_airpods_max(collection, head, crown_obj=crown_obj, fit=fit, prefix="")
    return crown_obj, cap_objs + hs_objs
