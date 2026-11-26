"""detail6 latpulldown: full-height commercial tower overhaul for P_lat_pulldown.

Implements items 1-6 from work/compare/gta6_latpulldown/REPORT.md (excluding item 7
placard typography owned by Codex):
  1. Structure: removes the stack-blocking front mast (155x186 mm) and converts the
     weight tower into a full-height (2.25 m) twin-upright portal frame with commercial
     tube proportions (54x100 mm uprights, 64x84 mm cantilever boom, gussets & splice
     plates). Reroutes the load cable above the upper header and below the top boom
     (0 frame penetrations) via raised head sheave + new guarded front pulley (sheet-metal
     U-cheek guard, grooved yellow/black spinning wheel driven by Stroke, large hex axle
     bolt + washers) and lat-bar connection hardware (stopper ball, cable ferrule,
     carabiner, swivel clevis parented to P_lat_bar).
  2. Acrylic stack shields: twin front transparent/translucent acrylic panels with open
     central pin slot (72 mm), 6 matte-black L-clips + silver washers & hex socket bolts,
     rear upper smoked shield, and full-height chrome guide rods (2.02 m) visible behind
     the scratched/smudged Fresnel-blended EEVEE acrylic shader.
  3. Floor grounding: fixes sunk base (-24 mm) and floating foot/front_foot (+15..20 mm)
     so every floor-contacting foot pad and welded L-shaped anchor flange (with hex anchor
     bolts & washers) sits flush at z = 0.000 m (<= 1 mm error), plus black plastic tube
     end-caps on all open rectangular tube ends.
  4. Seat & thigh rollers: replaces the boxy seat with a lofted superellipse cushion
     (matching equipment_machines.pad() welt + E_stitch stitching) and ABS under-trim
     preserving seat top z = 0.500 m; upgrades thigh rollers with a vertical receiver
     sleeve, diagonal truss brace, square chrome telescoping post (5 index holes),
     spring pop-pin with red pull-knob, and contoured rollers with concentric molded
     vinyl end-caps preserving roller z = [0.594, 0.726].
  5. Material usage wear: creates dedicated lat-pulldown copies (Ddetail6_LP_*) of
     E_frame, E_silver, E_pad, E_stack, E_steel, E_grip, E_accent with macro roughness
     breakup, touch-zone polish, AO crevice darkening, and cast-iron stipple — leaving
     shared gym materials completely untouched.
  6. Fasteners: hex bolts, washers, clips, and end-caps at pulley axle, boom splice,
     acrylic clips, seat bracket, anchor flanges, and open tube ends.

Preserves:
  - P_lat_pulldown origin/location/rotation, seat top z=0.500, lat bar z=1.76..1.88 &
    width 1.11 m, thigh roller z=0.594..0.726.
  - All Pin row & Stroke drivers, Selector coiled lanyard shape-key driver, kg/lb 3D
    plate numbers, Molded accessory tray, rear stack guard & caution sticker, and
    Exercise guide text/graphics (front guide moved intact onto unobstructed upper header).
  - Fully idempotent: running apply() twice produces identical scene state.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_latpulldown.py [-- --save out.blend]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

COLL = "DETAIL6_latpulldown"
PFX = "Ddetail6_LP_"
PKG_KEY = "detail6_latpulldown"
PROP_PKG = "detail6_lp_pkg"
PROP_ORIG_MAT = "detail6_lp_orig_matrix"
PROP_ORIG_SPLINE = "detail6_lp_orig_spline"
PROP_ORIG_MATS = "detail6_lp_orig_mats"
PROP_ORIG_MESH_Z = "detail6_lp_orig_zbounds"

ROOT_NAME = "P_lat_pulldown"

# Old P_lat_pulldown children replaced by upgraded geometry
REPLACED_NAMES = (
    "mast",
    "arm",
    "pulley",
    "base.003",
    "foot",
    "front_foot",
    "front_foot.001",
    "seat.001",
    "seat_post.001",
    "roller_stay",
    "thigh_roller",
    "thigh_roller.001",
    "roller_end",
    "roller_end.001",
    "hfront_wing.002",
    "hfront_wing.003",
    "Side shroud.004",
    "Side shroud.006",
    "cover.001",
    "Exposed tower tube.002",
    "Exposed tower tube.003",
    "Cable bay side rail.002",
    "Cable bay side rail.003",
    "Head bearing mount.001",
    "Bearing pedestal.001",
)

# Shared gym material -> dedicated lat-pulldown copy name
MAT_MAP = {
    "E_frame": PFX + "Frame",
    "E_silver": PFX + "Silver",
    "E_pad": PFX + "Pad",
    "E_stack": PFX + "Stack",
    "E_steel": PFX + "Steel",
    "E_grip": PFX + "Grip",
    "E_accent": PFX + "Accent",
}

# Structural constants (P_lat_pulldown local coords, metres)
REAR_SHEAVE_POS = Vector((0.0, 0.522, 2.090))
REAR_SHEAVE_R = 0.058
FRONT_PULLEY_POS = Vector((0.0, -0.382, 2.080))
FRONT_PULLEY_R = 0.068
CABLE_TOP_Z = 2.148  # exact common tangent: 2.090 + 0.058 == 2.080 + 0.068
CABLE_DROP_Y = -0.450  # exact front tangent: -0.382 - 0.068 == -0.450 (over P_lat_bar)


# ==============================================================================
# Low-level helpers (idempotency, mesh creation, UVs, primitives)
# ==============================================================================

def _descendants(ob):
    out = []
    for c in ob.children:
        out.append(c)
        out.extend(_descendants(c))
    return out


def _tag_and_restore_xform(ob):
    if ob.get(PROP_PKG) == PKG_KEY and PROP_ORIG_MAT in ob:
        vals = list(ob[PROP_ORIG_MAT])
        ob.matrix_basis = Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])
    else:
        ob[PROP_PKG] = PKG_KEY
        ob[PROP_ORIG_MAT] = [float(v) for row in ob.matrix_basis for v in row]


def _apply_box_uvs(bm, scale=2.0, layer_name=None):
    uv_layer = (
        bm.loops.layers.uv.get(layer_name) or bm.loops.layers.uv.new(layer_name)
        if layer_name
        else bm.loops.layers.uv.verify()
    )
    for f in bm.faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                u, v = co.x * scale, co.y * scale
            elif ax >= ay:
                u, v = co.y * scale, co.z * scale
            else:
                u, v = co.x * scale, co.z * scale
            loop[uv_layer].uv = (u, v)


def _finalize_mesh(name, bm, materials, parent, coll, loc=(0, 0, 0), rot=(0, 0, 0),
                   smooth_angle_deg=38.0, add_uv=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if add_uv:
        _apply_box_uvs(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in materials:
        me.materials.append(m)
    if smooth_angle_deg is not None:
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(smooth_angle_deg))
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = Vector(loc)
    ob.rotation_euler = Euler(rot, "XYZ")
    ob[PROP_PKG] = PKG_KEY
    return ob


def _add_box(bm, center, size, mat_idx=0, bevel=0.0, segments=2, rot_euler=None):
    sx, sy, sz = size
    mx = Matrix.Translation(center)
    if rot_euler is not None:
        mx = mx @ Euler(rot_euler, "XYZ").to_matrix().to_4x4()
    mx = mx @ Matrix.Diagonal((sx, sy, sz, 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=mx)
    verts = set(res["verts"])
    faces = [f for f in bm.faces if all(v in verts for v in f.verts)]
    edges = [e for e in bm.edges if all(v in verts for v in e.verts)]
    for f in faces:
        f.material_index = mat_idx
    if bevel > 0.0:
        bev = bmesh.ops.bevel(
            bm, geom=edges, offset=bevel, segments=segments,
            affect="EDGES", profile=0.5, clamp_overlap=True,
        )
        for f in bev.get("faces", []):
            f.material_index = mat_idx


def _add_beam_ab(bm, a, b, s_y, s_z, mat_idx=0, bevel=0.004, segments=2):
    a, b = Vector(a), Vector(b)
    d = b - a
    if d.length < 1e-5:
        return
    q = d.to_track_quat("X", "Z")
    mx = Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((d.length, s_y, s_z, 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=mx)
    verts = set(res["verts"])
    faces = [f for f in bm.faces if all(v in verts for v in f.verts)]
    edges = [e for e in bm.edges if all(v in verts for v in e.verts)]
    for f in faces:
        f.material_index = mat_idx
    if bevel > 0.0:
        bev = bmesh.ops.bevel(
            bm, geom=edges, offset=bevel, segments=segments,
            affect="EDGES", profile=0.5, clamp_overlap=True,
        )
        for f in bev.get("faces", []):
            f.material_index = mat_idx


def _add_cyl(bm, center, radius, depth, axis="Z", segs=20, mat_idx=0, bevel=0.0, r2=None):
    rot_map = {
        "Z": (0.0, 0.0, 0.0),
        "X": (0.0, math.pi * 0.5, 0.0),
        "Y": (math.pi * 0.5, 0.0, 0.0),
    }
    mx = Matrix.Translation(center) @ Euler(rot_map[axis], "XYZ").to_matrix().to_4x4()
    res = bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segs,
        radius1=radius, radius2=radius if r2 is None else r2, depth=depth, matrix=mx,
    )
    verts = set(res["verts"])
    faces = [f for f in bm.faces if all(v in verts for v in f.verts)]
    for f in faces:
        f.material_index = mat_idx
    if bevel > 0.0:
        # Bevel only the two cap rims (edges adjacent to an n-gon cap face)
        cap_faces = {f for f in faces if len(f.verts) > 4}
        rim_edges = [e for e in bm.edges if all(v in verts for v in e.verts)
                     and any(f in cap_faces for f in e.link_faces)]
        if rim_edges:
            bev = bmesh.ops.bevel(
                bm, geom=rim_edges, offset=bevel, segments=1,
                affect="EDGES", profile=0.5, clamp_overlap=True,
            )
            for f in bev.get("faces", []):
                f.material_index = mat_idx


def _add_revolved(bm, profile_rz, center, axis="X", segs=32, mat_idx=0, cap_ends=True):
    """Revolve a list of (radius, axial_offset) points into a watertight solid around axis."""
    rot_map = {
        "Z": Matrix.Identity(4),
        "X": Euler((0.0, math.pi * 0.5, 0.0), "XYZ").to_matrix().to_4x4(),
        "Y": Euler((-math.pi * 0.5, 0.0, 0.0), "XYZ").to_matrix().to_4x4(),
    }
    xf = Matrix.Translation(center) @ rot_map[axis]
    rings = []
    for r, ax in profile_rz:
        ring = []
        for s in range(segs):
            ang = math.tau * s / segs
            p = xf @ Vector((r * math.cos(ang), r * math.sin(ang), ax))
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        for s in range(segs):
            s1 = (s + 1) % segs
            f = bm.faces.new((r0[s], r0[s1], r1[s1], r1[s]))
            f.material_index = mat_idx
    if cap_ends:
        # Cap start and end with triangle fans around axial center points (zero n-gons on curved ends)
        c0 = bm.verts.new(xf @ Vector((0.0, 0.0, profile_rz[0][1])))
        c1 = bm.verts.new(xf @ Vector((0.0, 0.0, profile_rz[-1][1])))
        for s in range(segs):
            s1 = (s + 1) % segs
            f0 = bm.faces.new((c0, rings[0][s1], rings[0][s]))
            f0.material_index = mat_idx
            f1 = bm.faces.new((c1, rings[-1][s], rings[-1][s1]))
            f1.material_index = mat_idx


def _add_hex_bolt(bm, pos, normal_axis, head_r=0.0085, head_h=0.006, washer_r=0.0125,
                  washer_h=0.0026, sign=1.0, mat_idx=0):
    """Add washer + hexagonal bolt head protruding along sign * normal_axis from pos.

    Embeds washer 2.5 mm into the mounting face and hex head 2.0 mm into the washer so
    no two parallel faces sit within 1.5 mm (zero z-fighting / zero back-to-back in QA).
    """
    d_vec = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[normal_axis] * sign
    embed_w = 0.0025
    w_depth = washer_h + embed_w
    w_center = Vector(pos) + d_vec * (washer_h - w_depth * 0.5)
    _add_cyl(bm, w_center, washer_r, w_depth, axis=normal_axis, segs=16, mat_idx=mat_idx)
    embed_h = 0.0020
    h_depth = head_h + embed_h
    h_center = Vector(pos) + d_vec * (washer_h + head_h - h_depth * 0.5)
    _add_cyl(bm, h_center, head_r, h_depth, axis=normal_axis, segs=6, mat_idx=mat_idx, bevel=0.0008)


def _add_tube_cap(bm, face_center, normal_axis, sign, w1, w2, depth=0.010, mat_idx=0):
    """Molded black plastic end-cap slightly stepped inside tube outer dims with beveled lip."""
    embed = 0.0035
    total = depth + embed
    shift = sign * (depth - total * 0.5)
    if normal_axis == "X":
        size = (total, w1 - 0.004, w2 - 0.004)
        offset = Vector((shift, 0.0, 0.0))
    elif normal_axis == "Y":
        size = (w1 - 0.004, total, w2 - 0.004)
        offset = Vector((0.0, shift, 0.0))
    else:
        size = (w1 - 0.004, w2 - 0.004, total)
        offset = Vector((0.0, 0.0, shift))
    _add_box(bm, Vector(face_center) + offset, size, mat_idx=mat_idx, bevel=0.0022, segments=2)


def _add_extruded_polygon_x(bm, pts_yz, x0, x1, mat_idx=0, bevel=0.0015):
    """Extrude a 2D CCW polygon in (y, z) from x0 to x1 cleanly (watertight)."""
    n = len(pts_yz)
    v0 = [bm.verts.new((x0, y, z)) for (y, z) in pts_yz]
    v1 = [bm.verts.new((x1, y, z)) for (y, z) in pts_yz]
    f_l = bm.faces.new(v0[::-1])
    f_r = bm.faces.new(v1)
    f_l.material_index = mat_idx
    f_r.material_index = mat_idx
    new_verts = set(v0 + v1)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((v0[i], v0[j], v1[j], v1[i]))
        f.material_index = mat_idx
    if bevel > 0.0:
        edges = [e for e in bm.edges if all(v in new_verts for v in e.verts)]
        bev = bmesh.ops.bevel(
            bm, geom=edges, offset=bevel, segments=1,
            affect="EDGES", profile=0.5, clamp_overlap=True,
        )
        for f in bev.get("faces", []):
            f.material_index = mat_idx


# ==============================================================================
# Dedicated lat-pulldown materials (zero modification to shared gym materials)
# ==============================================================================

def _find_node(nt, ntype):
    return next((n for n in nt.nodes if n.type == ntype), None)


def _build_materials():
    """Clone shared equipment materials to Ddetail6_LP_* with realistic usage wear, plus acrylic."""
    # Remove any previous run's dedicated materials cleanly
    for mn in list(bpy.data.materials.keys()):
        if mn.startswith(PFX):
            m = bpy.data.materials[mn]
            bpy.data.materials.remove(m, do_unlink=True)

    mats = {}

    def clone_base(src_name, dst_name):
        src = bpy.data.materials[src_name]
        m = src.copy()
        m.name = dst_name
        m[PROP_PKG] = PKG_KEY
        return m

    def add_macro_wear_paint(mat, base_rgb, worn_rgb, rough_lo, rough_hi, coat_w, coat_r_lo, coat_r_hi):
        """Augment cloned detail4 powder-coat material with macro roughness breakup, AO crevices, and edge sheen."""
        nt = mat.node_tree
        bsdf = _find_node(nt, "BSDF_PRINCIPLED")
        tc = _find_node(nt, "TEX_COORD")
        if tc is None:
            tc = nt.nodes.new("ShaderNodeTexCoord")
            tc.location = (-1200, 0)

        # Macro low-frequency grunge/smudge noise (Object space)
        n_macro = nt.nodes.new("ShaderNodeTexNoise")
        n_macro.name = PFX + "MacroWear"
        n_macro.location = (-900, 260)
        n_macro.inputs["Scale"].default_value = 4.2
        n_macro.inputs["Detail"].default_value = 4.0
        n_macro.inputs["Roughness"].default_value = 0.58
        nt.links.new(tc.outputs["Object"], n_macro.inputs["Vector"])

        # Medium hand-touch smudge patches
        n_med = nt.nodes.new("ShaderNodeTexNoise")
        n_med.name = PFX + "TouchSmudge"
        n_med.location = (-900, 40)
        n_med.inputs["Scale"].default_value = 15.0
        n_med.inputs["Detail"].default_value = 3.0
        n_med.inputs["Roughness"].default_value = 0.50
        nt.links.new(tc.outputs["Object"], n_med.inputs["Vector"])

        # Combine macro + medium wear
        mix_w = nt.nodes.new("ShaderNodeMix")
        mix_w.data_type = "FLOAT"
        mix_w.location = (-650, 180)
        mix_w.inputs["Factor"].default_value = 0.35
        nt.links.new(n_macro.outputs["Fac"], mix_w.inputs["A"])
        nt.links.new(n_med.outputs["Fac"], mix_w.inputs["B"])

        # Ambient Occlusion (works in EEVEE): crevices matte & slightly darker, exposed corners crisper
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.name = PFX + "AO"
        ao.samples = 8
        ao.only_local = True
        ao.location = (-650, 420)
        ao.inputs["Distance"].default_value = 0.09
        ao.inputs["Color"].default_value = (*base_rgb, 1.0)

        # Subtle albedo shift: crevices slightly darker, exposed rubbed surfaces slightly lifted
        mix_col = nt.nodes.new("ShaderNodeMix")
        mix_col.data_type = "RGBA"
        mix_col.location = (-360, 420)
        mix_col.inputs["A"].default_value = (base_rgb[0] * 0.72, base_rgb[1] * 0.72, base_rgb[2] * 0.72, 1.0)
        mix_col.inputs["B"].default_value = (*worn_rgb, 1.0)
        # Map AO [0.35..0.98] -> [0..1]
        mr_ao = nt.nodes.new("ShaderNodeMapRange")
        mr_ao.clamp = True
        mr_ao.location = (-500, 380)
        mr_ao.inputs["From Min"].default_value = 0.35
        mr_ao.inputs["From Max"].default_value = 0.98
        nt.links.new(ao.outputs["AO"], mr_ao.inputs["Value"])
        nt.links.new(mr_ao.outputs["Result"], mix_col.inputs["Factor"])
        nt.links.new(mix_col.outputs["Result"], bsdf.inputs["Base Color"])

        # Map combined wear to Roughness [rough_lo..rough_hi], pushed rougher in crevices
        mr_r = nt.nodes.new("ShaderNodeMapRange")
        mr_r.clamp = True
        mr_r.location = (-440, 160)
        mr_r.inputs["From Min"].default_value = 0.25
        mr_r.inputs["From Max"].default_value = 0.75
        mr_r.inputs["To Min"].default_value = rough_lo
        mr_r.inputs["To Max"].default_value = rough_hi
        nt.links.new(mix_w.outputs["Result"], mr_r.inputs["Value"])

        # Add crevice matte boost: (1 - AO_mapped) * 0.10
        inv_ao = nt.nodes.new("ShaderNodeMath")
        inv_ao.operation = "SUBTRACT"
        inv_ao.location = (-340, 260)
        inv_ao.inputs[0].default_value = 1.0
        nt.links.new(mr_ao.outputs["Result"], inv_ao.inputs[1])

        crev_r = nt.nodes.new("ShaderNodeMath")
        crev_r.operation = "MULTIPLY_ADD"
        crev_r.use_clamp = True
        crev_r.location = (-200, 180)
        crev_r.inputs[1].default_value = 0.10
        nt.links.new(inv_ao.outputs["Value"], crev_r.inputs[0])
        nt.links.new(mr_r.outputs["Result"], crev_r.inputs[2])
        nt.links.new(crev_r.outputs["Value"], bsdf.inputs["Roughness"])

        # Vary clear-coat roughness slightly too (hand-polished glossy spots vs duller patches)
        mr_cr = nt.nodes.new("ShaderNodeMapRange")
        mr_cr.clamp = True
        mr_cr.location = (-260, 0)
        mr_cr.inputs["From Min"].default_value = 0.25
        mr_cr.inputs["From Max"].default_value = 0.75
        mr_cr.inputs["To Min"].default_value = coat_r_lo
        mr_cr.inputs["To Max"].default_value = coat_r_hi
        nt.links.new(mix_w.outputs["Result"], mr_cr.inputs["Value"])
        bsdf.inputs["Coat Weight"].default_value = coat_w
        nt.links.new(mr_cr.outputs["Result"], bsdf.inputs["Coat Roughness"])

        mat.diffuse_color = (*base_rgb, 1.0)

    # 1. Red powder-coat frame
    m_frame = clone_base("E_frame", PFX + "Frame")
    add_macro_wear_paint(
        m_frame,
        base_rgb=(0.56, 0.004, 0.005),
        worn_rgb=(0.60, 0.008, 0.009),
        rough_lo=0.22, rough_hi=0.40,
        coat_w=0.26, coat_r_lo=0.08, coat_r_hi=0.20,
    )
    mats["frame"] = m_frame

    # 2. Dark satin black powder-coat (tower, arm, shrouds, guards)
    m_silver = clone_base("E_silver", PFX + "Silver")
    add_macro_wear_paint(
        m_silver,
        base_rgb=(0.021, 0.022, 0.025),
        worn_rgb=(0.028, 0.030, 0.034),
        rough_lo=0.21, rough_hi=0.41,
        coat_w=0.38, coat_r_lo=0.06, coat_r_hi=0.18,
    )
    mats["silver"] = m_silver

    # 3. Black vinyl / leather upholstery (seat & thigh rollers) with contact polish
    m_pad = clone_base("E_pad", PFX + "Pad")
    nt = m_pad.node_tree
    bsdf = _find_node(nt, "BSDF_PRINCIPLED")
    tc = _find_node(nt, "TEX_COORD") or nt.nodes.new("ShaderNodeTexCoord")
    geom = nt.nodes.new("ShaderNodeNewGeometry")
    geom.location = (-1000, 320)
    sep_n = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep_n.location = (-820, 320)
    nt.links.new(geom.outputs["Normal"], sep_n.inputs["Vector"])

    # Upward/contact faces get smoother glossy skin-oil polish
    n_wear = nt.nodes.new("ShaderNodeTexNoise")
    n_wear.name = PFX + "PadWear"
    n_wear.location = (-900, 120)
    n_wear.inputs["Scale"].default_value = 6.5
    n_wear.inputs["Detail"].default_value = 4.0
    n_wear.inputs["Roughness"].default_value = 0.6
    nt.links.new(tc.outputs["Object"], n_wear.inputs["Vector"])

    mr_pad = nt.nodes.new("ShaderNodeMapRange")
    mr_pad.clamp = True
    mr_pad.location = (-600, 140)
    mr_pad.inputs["From Min"].default_value = 0.25
    mr_pad.inputs["From Max"].default_value = 0.78
    mr_pad.inputs["To Min"].default_value = 0.34
    mr_pad.inputs["To Max"].default_value = 0.62
    nt.links.new(n_wear.outputs["Fac"], mr_pad.inputs["Value"])

    # Polish reduction on upward-facing contact area (Normal.z > 0.5)
    mr_up = nt.nodes.new("ShaderNodeMapRange")
    mr_up.clamp = True
    mr_up.location = (-600, 340)
    mr_up.inputs["From Min"].default_value = 0.45
    mr_up.inputs["From Max"].default_value = 0.95
    mr_up.inputs["To Min"].default_value = 0.0
    mr_up.inputs["To Max"].default_value = -0.10
    nt.links.new(sep_n.outputs["Z"], mr_up.inputs["Value"])

    add_r = nt.nodes.new("ShaderNodeMath")
    add_r.operation = "ADD"
    add_r.use_clamp = True
    add_r.location = (-360, 220)
    nt.links.new(mr_pad.outputs["Result"], add_r.inputs[0])
    nt.links.new(mr_up.outputs["Result"], add_r.inputs[1])
    nt.links.new(add_r.outputs["Value"], bsdf.inputs["Roughness"])
    bsdf.inputs["Coat Weight"].default_value = 0.08
    bsdf.inputs["Coat Roughness"].default_value = 0.26
    bsdf.inputs["Sheen Weight"].default_value = 0.06
    mats["pad"] = m_pad

    # 4. Cast-iron painted weight plates (fine cast stipple + AO gap darkening + wear)
    m_stack = clone_base("E_stack", PFX + "Stack")
    nt = m_stack.node_tree
    bsdf = _find_node(nt, "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-950, 0)
    n_cast = nt.nodes.new("ShaderNodeTexNoise")
    n_cast.name = PFX + "CastStipple"
    n_cast.location = (-680, -200)
    n_cast.inputs["Scale"].default_value = 520.0
    n_cast.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n_cast.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (-380, -200)
    bump.inputs["Strength"].default_value = 0.065
    bump.inputs["Distance"].default_value = 0.0004
    nt.links.new(n_cast.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    n_sw = nt.nodes.new("ShaderNodeTexNoise")
    n_sw.name = PFX + "StackWear"
    n_sw.location = (-680, 100)
    n_sw.inputs["Scale"].default_value = 9.0
    n_sw.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n_sw.inputs["Vector"])
    mr_sw = nt.nodes.new("ShaderNodeMapRange")
    mr_sw.clamp = True
    mr_sw.location = (-400, 100)
    mr_sw.inputs["From Min"].default_value = 0.28
    mr_sw.inputs["From Max"].default_value = 0.72
    mr_sw.inputs["To Min"].default_value = 0.27
    mr_sw.inputs["To Max"].default_value = 0.44
    nt.links.new(n_sw.outputs["Fac"], mr_sw.inputs["Value"])
    nt.links.new(mr_sw.outputs["Result"], bsdf.inputs["Roughness"])

    ao_s = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao_s.samples = 8
    ao_s.only_local = True
    ao_s.location = (-680, 320)
    ao_s.inputs["Distance"].default_value = 0.05
    mix_sc = nt.nodes.new("ShaderNodeMix")
    mix_sc.data_type = "RGBA"
    mix_sc.location = (-360, 320)
    mix_sc.inputs["A"].default_value = (0.014, 0.016, 0.019, 1.0)
    mix_sc.inputs["B"].default_value = (0.028, 0.031, 0.037, 1.0)
    nt.links.new(ao_s.outputs["AO"], mix_sc.inputs["Factor"])
    nt.links.new(mix_sc.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.62
    m_stack.diffuse_color = (0.025, 0.028, 0.033, 1.0)
    mats["stack"] = m_stack

    # 5. Bright polished chrome steel (guide rods, telescoping post, bolts, lat bar)
    m_steel = clone_base("E_steel", PFX + "Steel")
    nt = m_steel.node_tree
    bsdf = _find_node(nt, "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-950, 0)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-740, 0)
    # Stretched vertically for realistic guide-rod linear sliding micro-streaks
    mp.inputs["Scale"].default_value = (18.0, 18.0, 2.2)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    n_ch = nt.nodes.new("ShaderNodeTexNoise")
    n_ch.location = (-520, 0)
    n_ch.inputs["Scale"].default_value = 8.0
    n_ch.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], n_ch.inputs["Vector"])
    mr_ch = nt.nodes.new("ShaderNodeMapRange")
    mr_ch.clamp = True
    mr_ch.location = (-300, 0)
    mr_ch.inputs["From Min"].default_value = 0.25
    mr_ch.inputs["From Max"].default_value = 0.78
    mr_ch.inputs["To Min"].default_value = 0.065
    mr_ch.inputs["To Max"].default_value = 0.165
    nt.links.new(n_ch.outputs["Fac"], mr_ch.inputs["Value"])
    bsdf.inputs["Base Color"].default_value = (0.86, 0.88, 0.91, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.96
    bsdf.inputs["Anisotropic"].default_value = 0.28
    nt.links.new(mr_ch.outputs["Result"], bsdf.inputs["Roughness"])
    m_steel.diffuse_color = (0.82, 0.84, 0.87, 1.0)
    mats["steel"] = m_steel

    # 6. Matte rubber / vinyl / end-caps / cable jacket
    m_grip = clone_base("E_grip", PFX + "Grip")
    nt = m_grip.node_tree
    bsdf = _find_node(nt, "BSDF_PRINCIPLED")
    tc = _find_node(nt, "TEX_COORD") or nt.nodes.new("ShaderNodeTexCoord")
    n_gr = nt.nodes.new("ShaderNodeTexNoise")
    n_gr.name = PFX + "GripMacro"
    n_gr.location = (-680, 180)
    n_gr.inputs["Scale"].default_value = 10.0
    n_gr.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n_gr.inputs["Vector"])
    mr_gr = nt.nodes.new("ShaderNodeMapRange")
    mr_gr.clamp = True
    mr_gr.location = (-400, 180)
    mr_gr.inputs["From Min"].default_value = 0.25
    mr_gr.inputs["From Max"].default_value = 0.75
    mr_gr.inputs["To Min"].default_value = 0.56
    mr_gr.inputs["To Max"].default_value = 0.76
    nt.links.new(n_gr.outputs["Fac"], mr_gr.inputs["Value"])
    nt.links.new(mr_gr.outputs["Result"], bsdf.inputs["Roughness"])
    m_grip.diffuse_color = (0.015, 0.016, 0.019, 1.0)
    mats["grip"] = m_grip

    # 7. Yellow accent (pulley wheel, pin tip)
    m_accent = clone_base("E_accent", PFX + "Accent")
    nt = m_accent.node_tree
    bsdf = _find_node(nt, "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-720, 0)
    n_ac = nt.nodes.new("ShaderNodeTexNoise")
    n_ac.location = (-500, 0)
    n_ac.inputs["Scale"].default_value = 12.0
    n_ac.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], n_ac.inputs["Vector"])
    mr_ac = nt.nodes.new("ShaderNodeMapRange")
    mr_ac.clamp = True
    mr_ac.location = (-280, 0)
    mr_ac.inputs["From Min"].default_value = 0.25
    mr_ac.inputs["From Max"].default_value = 0.75
    mr_ac.inputs["To Min"].default_value = 0.22
    mr_ac.inputs["To Max"].default_value = 0.36
    nt.links.new(n_ac.outputs["Fac"], mr_ac.inputs["Value"])
    nt.links.new(mr_ac.outputs["Result"], bsdf.inputs["Roughness"])
    m_accent.diffuse_color = (0.95, 0.72, 0.04, 1.0)
    mats["accent"] = m_accent

    # 8. Translucent scratched/smudged front acrylic shield (lightweight EEVEE Fresnel BLENDED)
    m_acr = bpy.data.materials.new(PFX + "Acrylic")
    m_acr[PROP_PKG] = PKG_KEY
    if m_acr.node_tree is None:
        m_acr.use_nodes = True
    m_acr.surface_render_method = "BLENDED"
    m_acr.use_backface_culling = True
    nt = m_acr.node_tree
    bsdf = _find_node(nt, "BSDF_PRINCIPLED")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["IOR"].default_value = 1.49
    bsdf.inputs["Specular IOR Level"].default_value = 0.72
    bsdf.inputs["Coat Weight"].default_value = 0.45
    bsdf.inputs["Coat Roughness"].default_value = 0.05

    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1350, 0)

    # Diagonal wipe-scratch layer A (+34 deg)
    mp_a = nt.nodes.new("ShaderNodeMapping")
    mp_a.location = (-1100, 260)
    mp_a.inputs["Rotation"].default_value = (0.0, math.radians(34.0), 0.0)
    mp_a.inputs["Scale"].default_value = (4.5, 4.5, 95.0)
    nt.links.new(tc.outputs["Object"], mp_a.inputs["Vector"])
    n_sa = nt.nodes.new("ShaderNodeTexNoise")
    n_sa.location = (-880, 260)
    n_sa.inputs["Scale"].default_value = 2.6
    n_sa.inputs["Detail"].default_value = 6.0
    n_sa.inputs["Roughness"].default_value = 0.62
    nt.links.new(mp_a.outputs["Vector"], n_sa.inputs["Vector"])
    mr_sa = nt.nodes.new("ShaderNodeMapRange")
    mr_sa.clamp = True
    mr_sa.location = (-660, 260)
    mr_sa.inputs["From Min"].default_value = 0.54
    mr_sa.inputs["From Max"].default_value = 0.78
    nt.links.new(n_sa.outputs["Fac"], mr_sa.inputs["Value"])

    # Diagonal wipe-scratch layer B (-24 deg)
    mp_b = nt.nodes.new("ShaderNodeMapping")
    mp_b.location = (-1100, -10)
    mp_b.inputs["Rotation"].default_value = (0.0, math.radians(-24.0), 0.0)
    mp_b.inputs["Scale"].default_value = (3.8, 3.8, 72.0)
    nt.links.new(tc.outputs["Object"], mp_b.inputs["Vector"])
    n_sb = nt.nodes.new("ShaderNodeTexNoise")
    n_sb.location = (-880, -10)
    n_sb.inputs["Scale"].default_value = 2.2
    n_sb.inputs["Detail"].default_value = 5.0
    n_sb.inputs["Roughness"].default_value = 0.58
    nt.links.new(mp_b.outputs["Vector"], n_sb.inputs["Vector"])
    mr_sb = nt.nodes.new("ShaderNodeMapRange")
    mr_sb.clamp = True
    mr_sb.location = (-660, -10)
    mr_sb.inputs["From Min"].default_value = 0.56
    mr_sb.inputs["From Max"].default_value = 0.80
    nt.links.new(n_sb.outputs["Fac"], mr_sb.inputs["Value"])

    # Cloudy hand smudges / fingerprints
    n_sm = nt.nodes.new("ShaderNodeTexNoise")
    n_sm.location = (-880, -280)
    n_sm.inputs["Scale"].default_value = 5.5
    n_sm.inputs["Detail"].default_value = 4.0
    n_sm.inputs["Roughness"].default_value = 0.65
    nt.links.new(tc.outputs["Object"], n_sm.inputs["Vector"])
    mr_sm = nt.nodes.new("ShaderNodeMapRange")
    mr_sm.clamp = True
    mr_sm.location = (-660, -280)
    mr_sm.inputs["From Min"].default_value = 0.44
    mr_sm.inputs["From Max"].default_value = 0.76
    nt.links.new(n_sm.outputs["Fac"], mr_sm.inputs["Value"])

    # Combine scratches A + B
    max_sc = nt.nodes.new("ShaderNodeMath")
    max_sc.operation = "MAXIMUM"
    max_sc.use_clamp = True
    max_sc.location = (-440, 140)
    nt.links.new(mr_sa.outputs["Result"], max_sc.inputs[0])
    nt.links.new(mr_sb.outputs["Result"], max_sc.inputs[1])

    # Combined haze = 0.55 * scratches + 0.45 * smudges
    mix_hz = nt.nodes.new("ShaderNodeMix")
    mix_hz.data_type = "FLOAT"
    mix_hz.location = (-260, 0)
    mix_hz.inputs["Factor"].default_value = 0.45
    nt.links.new(max_sc.outputs["Value"], mix_hz.inputs["A"])
    nt.links.new(mr_sm.outputs["Result"], mix_hz.inputs["B"])

    # Base color: clean subtle blue-grey tint -> milky light grey on scratched/smudged areas
    mix_ac = nt.nodes.new("ShaderNodeMix")
    mix_ac.data_type = "RGBA"
    mix_ac.location = (-80, 320)
    mix_ac.inputs["A"].default_value = (0.76, 0.81, 0.87, 1.0)
    mix_ac.inputs["B"].default_value = (0.94, 0.95, 0.97, 1.0)
    nt.links.new(mix_hz.outputs["Result"], mix_ac.inputs["Factor"])
    nt.links.new(mix_ac.outputs["Result"], bsdf.inputs["Base Color"])

    # Roughness: 0.05 clean acrylic -> 0.42 scratched/cloudy haze
    mr_ar = nt.nodes.new("ShaderNodeMapRange")
    mr_ar.clamp = True
    mr_ar.location = (-80, 100)
    mr_ar.inputs["From Min"].default_value = 0.0
    mr_ar.inputs["From Max"].default_value = 1.0
    mr_ar.inputs["To Min"].default_value = 0.055
    mr_ar.inputs["To Max"].default_value = 0.42
    nt.links.new(mix_hz.outputs["Result"], mr_ar.inputs["Value"])
    nt.links.new(mr_ar.outputs["Result"], bsdf.inputs["Roughness"])

    # Alpha: Fresnel [0.14..0.44] + haze boost [+0.16] -> clamped <= 0.56 so stack & chrome rods shine clearly
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-440, -480)
    lw.inputs["Blend"].default_value = 0.25
    mr_fr = nt.nodes.new("ShaderNodeMapRange")
    mr_fr.clamp = True
    mr_fr.location = (-240, -480)
    mr_fr.inputs["From Min"].default_value = 0.0
    mr_fr.inputs["From Max"].default_value = 1.0
    mr_fr.inputs["To Min"].default_value = 0.14
    mr_fr.inputs["To Max"].default_value = 0.44
    nt.links.new(lw.outputs["Facing"], mr_fr.inputs["Value"])

    alpha_add = nt.nodes.new("ShaderNodeMath")
    alpha_add.operation = "MULTIPLY_ADD"
    alpha_add.use_clamp = True
    alpha_add.location = (-60, -220)
    alpha_add.inputs[1].default_value = 0.18
    nt.links.new(mix_hz.outputs["Result"], alpha_add.inputs[0])
    nt.links.new(mr_fr.outputs["Result"], alpha_add.inputs[2])

    alpha_cap = nt.nodes.new("ShaderNodeMath")
    alpha_cap.operation = "MINIMUM"
    alpha_cap.location = (80, -220)
    alpha_cap.inputs[1].default_value = 0.56
    nt.links.new(alpha_add.outputs["Value"], alpha_cap.inputs[0])
    nt.links.new(alpha_cap.outputs["Value"], bsdf.inputs["Alpha"])

    # Fine scratch bump for directional specular glints
    bmp_a = nt.nodes.new("ShaderNodeBump")
    bmp_a.location = (-60, -400)
    bmp_a.inputs["Strength"].default_value = 0.065
    bmp_a.inputs["Distance"].default_value = 0.0003
    nt.links.new(max_sc.outputs["Value"], bmp_a.inputs["Height"])
    nt.links.new(bmp_a.outputs["Normal"], bsdf.inputs["Normal"])

    m_acr.diffuse_color = (0.78, 0.84, 0.90, 0.28)
    mats["acrylic"] = m_acr

    # 9. Smoked rear acrylic shield (darker tint, cleaner look behind guide rods)
    m_smoke = m_acr.copy()
    m_smoke.name = PFX + "AcrylicSmoke"
    m_smoke[PROP_PKG] = PKG_KEY
    nt_s = m_smoke.node_tree
    for n in nt_s.nodes:
        if n.type == "MIX" and n.data_type == "RGBA":
            n.inputs["A"].default_value = (0.12, 0.13, 0.16, 1.0)
            n.inputs["B"].default_value = (0.24, 0.26, 0.30, 1.0)
    m_smoke.diffuse_color = (0.16, 0.18, 0.22, 0.35)
    mats["acrylic_smoke"] = m_smoke

    # Keep shared E_stitch for seat stitching (read-only reuse, never modified)
    mats["stitch"] = bpy.data.materials["E_stitch"]
    return mats


# ==============================================================================
# Geometry builders
# ==============================================================================

def _build_tower_and_boom(root, coll, mats):
    """Build full-height twin-upright portal frame, upper header, top boom, gussets & bolts."""
    created = []

    # 1. Twin full-height front uprights + top crossbar + rear upper frame (Ddetail6_LP_Silver)
    #    Uprights: 54 x 100 mm commercial rectangular tubing at x = +/-[0.202, 0.256], y = [0.382, 0.482], z = [0.120, 2.252]
    bm = bmesh.new()
    for sx in (-1.0, 1.0):
        ux = sx * 0.229
        # Main vertical upright (sits embedded 4.5 mm into housing top z=0.1245; 4 mm inside housing x=+/-0.260)
        _add_box(bm, (ux, 0.432, 1.186), (0.054, 0.100, 2.132), mat_idx=0, bevel=0.005, segments=2)
        # Base mounting collar flange at housing top (z = 0.123..0.141, stepped 3 mm above upright bottom z=0.120!)
        _add_box(bm, (ux, 0.432, 0.132), (0.062, 0.108, 0.018), mat_idx=0, bevel=0.002, segments=1)
        # Horizontal side tie-bars bridging front upright (y=0.482) to full-height chrome side tube (y=0.542)
        for tz in (0.720, 1.360, 2.195):
            _add_box(bm, (ux, 0.512, tz), (0.044, 0.070, 0.044), mat_idx=0, bevel=0.003, segments=1)
        # Guide-rod top retaining bracket (split left/right so x=0 vertical load cable has 95 mm clearance!)
        # Spans x = +/- [0.095, 0.206], y = [0.556, 0.604], z = [2.095, 2.125]
        _add_box(bm, (sx * 0.1505, 0.580, 2.110), (0.111, 0.048, 0.030), mat_idx=0, bevel=0.003, segments=1)
        # Bracket tie-arm forward to rear chrome tube (y=0.542) — stepped 4 mm in Z vs retaining bracket
        _add_box(bm, (sx * 0.220, 0.562, 2.110), (0.036, 0.056, 0.022), mat_idx=0, bevel=0.002, segments=1)

    # Top horizontal portal crossbar (z = [2.174, 2.246] -> 6 mm stepped vs upright top 2.252 & boom 2.252)
    _add_box(bm, (0.0, 0.432, 2.210), (0.412, 0.092, 0.072), mat_idx=0, bevel=0.004, segments=2)

    # Rear top crossbeam behind head sheave (z = [2.174, 2.242], y = [0.548, 0.600])
    _add_box(bm, (0.0, 0.574, 2.208), (0.472, 0.052, 0.068), mat_idx=0, bevel=0.004, segments=2)

    # Upper front header fascia panel (holds Exercise guide.003 at z=2.005; top z=2.094 is 50 mm clear below cable!)
    _add_box(bm, (0.0, 0.408, 2.008), (0.410, 0.036, 0.172), mat_idx=0, bevel=0.004, segments=2)

    # Rear head sheave upper hanger cheeks bridging Pulley cheek.002/.003 up to TopBeam (z=2.174, embedded 6 mm)
    for sx in (-1.0, 1.0):
        _add_box(bm, (sx * 0.020, 0.522, 2.128), (0.006, 0.062, 0.100), mat_idx=0, bevel=0.0015, segments=1)

    created.append(_finalize_mesh(PFX + "TowerFrame", bm, [mats["silver"]], root, coll, smooth_angle_deg=35.0))

    # 2. Full-height exposed chrome side accent tubes + guide-rod top chrome caps (Ddetail6_LP_Steel)
    bm_ch = bmesh.new()
    for sx in (-1.0, 1.0):
        _add_cyl(bm_ch, (sx * 0.228, 0.542, 1.158), 0.018, 2.076, axis="Z", segs=24, mat_idx=0, bevel=0.002)
        # Chrome retaining cap & nut on top of each guide rod (embedded 3 mm into bracket top z=2.125)
        _add_cyl(bm_ch, (sx * 0.1196, 0.580, 2.128), 0.016, 0.014, axis="Z", segs=16, mat_idx=0, bevel=0.001)
        _add_cyl(bm_ch, (sx * 0.1196, 0.580, 2.138), 0.011, 0.014, axis="Z", segs=6, mat_idx=0, bevel=0.0008)
    created.append(_finalize_mesh(PFX + "TowerChromeTubes", bm_ch, [mats["steel"]], root, coll, smooth_angle_deg=42.0))

    # 3. Top cantilever boom beam (64 x 84 mm) + gussets + splice plates + end-caps + junction bolts
    #    Beam bottom z = 2.168 (16 mm clear above horizontal cable top z = 2.152!), top z = 2.252
    bm_b = bmesh.new()
    # Main cantilever boom: x=[-0.032, 0.032], y=[-0.490, +0.606], z=[2.168, 2.252]
    _add_box(bm_b, (0.0, 0.058, 2.210), (0.064, 1.096, 0.084), mat_idx=0, bevel=0.005, segments=2)
    # Side splice plates & triangular reinforcement gussets at boom-to-tower junction
    # Embedded 4 mm into boom side (x = +/-[0.028, 0.040]), bottom z = 2.096 (> 26 mm CLEAR above Exercise guide.003!)
    for sx in (-1.0, 1.0):
        x0, x1 = (0.028, 0.040) if sx > 0 else (-0.040, -0.028)
        gusset_pts = [
            (0.220, 2.172),
            (0.386, 2.096),
            (0.386, 2.244),
            (0.220, 2.244),
        ]
        _add_extruded_polygon_x(bm_b, gusset_pts, x0, x1, mat_idx=0, bevel=0.0015)
        # Bolts clamping splice plates to boom & tower
        for by, bz in ((0.255, 2.210), (0.345, 2.210), (0.352, 2.138)):
            _add_hex_bolt(bm_b, (sx * 0.040, by, bz), "X", head_r=0.008, head_h=0.0055,
                          washer_r=0.012, washer_h=0.0026, sign=sx, mat_idx=1)

    # Molded black plastic end-caps at both open ends of TopBeam (y=-0.490 and y=+0.606)
    _add_tube_cap(bm_b, (0.0, -0.490, 2.210), "Y", -1.0, 0.064, 0.084, depth=0.011, mat_idx=2)
    _add_tube_cap(bm_b, (0.0, 0.606, 2.210), "Y", 1.0, 0.064, 0.084, depth=0.011, mat_idx=2)

    created.append(_finalize_mesh(
        PFX + "TopBoom", bm_b, [mats["silver"], mats["steel"], mats["grip"]], root, coll, smooth_angle_deg=35.0
    ))
    return created


def _build_front_pulley_and_bar_hardware(root, coll, mats):
    """Build guarded front upper pulley (U-cheek guard, spinning grooved wheel, hex axle) & lat-bar hardware."""
    created = []
    py, pz = FRONT_PULLEY_POS.y, FRONT_PULLEY_POS.z  # (-0.382, 2.080)

    # 1. Sheet-metal U-shaped cheek guard + mounting bolts + large hex axle bolt & washers
    bm_g = bmesh.new()
    # Build contoured cheek silhouette in (y, z): semicircular bottom around (py, pz) R=0.080, rising cleanly to TopBeam z=2.174
    cheek_pts = []
    # Top edge under boom from front (y = py - 0.082 = -0.464) to rear (y = py + 0.088 = -0.294)
    # Semicircle arc around (py, pz) from angle 0 (rear, +Y) through -pi/2 (bottom, -Z) to -pi (front, -Y)
    n_arc = 14
    r_guard = 0.080
    # Front-top corner
    cheek_pts.append((py - 0.080, 2.174))
    # Arc from front (-Y, ang=pi) through bottom (ang=3pi/2) to rear (+Y, ang=2pi)
    for i in range(n_arc + 1):
        ang = math.pi + math.pi * i / n_arc
        cheek_pts.append((py + r_guard * math.cos(ang), pz + r_guard * math.sin(ang)))
    # Rear-top swept fillet corner
    cheek_pts.append((py + 0.095, 2.174))

    for sx in (-1.0, 1.0):
        x0, x1 = (0.017, 0.024) if sx > 0 else (-0.024, -0.017)
        _add_extruded_polygon_x(bm_g, cheek_pts, x0, x1, mat_idx=0, bevel=0.0014)
        # Upper mounting side flange ears hugging TopBeam sides (embedded 3.5 mm into cheek -> zero coplanar touch!)
        _add_box(bm_g, (sx * 0.0295, py, 2.188), (0.019, 0.148, 0.044), mat_idx=0, bevel=0.002, segments=1)
        # 2 silver mounting bolts per side fixing guard ears to TopBeam
        for by in (py - 0.046, py + 0.046):
            _add_hex_bolt(bm_g, (sx * 0.039, by, 2.192), "X", head_r=0.007, head_h=0.0055,
                          washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)

    # Curved lower-rear bridge strap linking the two cheeks behind & below pulley (embedded 3 mm into each cheek)
    _add_box(bm_g, (0.0, py + 0.070, pz - 0.024), (0.040, 0.012, 0.072), mat_idx=0, bevel=0.002, segments=1)
    # Lower cable-retainer spacer pin across front-bottom of guard (end caps protruding 5 mm outside cheeks)
    _add_cyl(bm_g, (0.0, py - 0.018, pz - 0.070), 0.0055, 0.058, axis="X", segs=12, mat_idx=1)

    # Prominent large silver hex axle bolt + machined washers on BOTH sides (iconic GTA6 detail!)
    _add_cyl(bm_g, (0.0, py, pz), 0.011, 0.044, axis="X", segs=16, mat_idx=1)
    for sx in (-1.0, 1.0):
        _add_hex_bolt(bm_g, (sx * 0.024, py, pz), "X", head_r=0.0155, head_h=0.011,
                      washer_r=0.0225, washer_h=0.0032, sign=sx, mat_idx=1)

    # Rubber bumper sleeve right above stopper ball (x=0, y=-0.450, z=2.008..2.020) — open ring around cable!
    r_in, r_out = 0.009, 0.0185
    z_b0, z_b1 = 2.008, 2.020
    segs_b = 20
    b_prof = [(r_in, z_b0), (r_out, z_b0), (r_out, z_b1), (r_in, z_b1)]
    b_rings = []
    for s in range(segs_b):
        ang = math.tau * s / segs_b
        ca, sa = math.cos(ang), math.sin(ang)
        b_rings.append([bm_g.verts.new((r * ca, CABLE_DROP_Y + r * sa, z)) for (r, z) in b_prof])
    for s in range(segs_b):
        r0, r1 = b_rings[s], b_rings[(s + 1) % segs_b]
        for k in range(4):
            k1 = (k + 1) % 4
            f = bm_g.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
            f.material_index = 2
    # Two thin side tabs tying the bumper ring to the guard cheeks (embedded 3.5 mm into cheeks, stepped 2 mm in Z)
    for sx in (-1.0, 1.0):
        _add_box(bm_g, (sx * 0.0175, CABLE_DROP_Y + 0.009, 2.014), (0.007, 0.018, 0.008), mat_idx=0, bevel=0.001, segments=1)

    created.append(_finalize_mesh(
        PFX + "FrontPulleyGuard", bm_g, [mats["silver"], mats["steel"], mats["grip"]], root, coll, smooth_angle_deg=36.0
    ))

    # 2. Rotating grooved front pulley wheel (spindle empty + Stroke driver)
    spindle = bpy.data.objects.new(PFX + "FrontPulleySpindle", None)
    coll.objects.link(spindle)
    spindle.parent = root
    spindle.location = FRONT_PULLEY_POS.copy()
    spindle[PROP_PKG] = PKG_KEY
    # Add Stroke rotation driver: bar drops 0.48 m -> wheel turns -0.48 / R_front radians around X
    fc = spindle.driver_add("rotation_euler", 0)
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "v"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = root
    var.targets[0].data_path = '["Stroke"]'
    drv.expression = f"{-0.48 / FRONT_PULLEY_R:.6f}*v"
    created.append(spindle)

    # Revolved grooved pulley profile around local X axis (mat 0 = yellow accent rim, mat 1 = dark groove, mat 2 = chrome hub)
    bm_w = bmesh.new()
    # Outer yellow wheel with V-groove (r_flange=0.074, r_groove=0.062, half-width=0.0125)
    wheel_prof = [
        (0.012, -0.0135),
        (0.022, -0.0135),
        (0.022, -0.0115),
        (0.056, -0.0115),
        (0.058, -0.0125),
        (0.074, -0.0125),
        (0.074, -0.0085),
        (0.062, -0.0040),
        (0.062,  0.0040),
        (0.074,  0.0085),
        (0.074,  0.0125),
        (0.058,  0.0125),
        (0.056,  0.0115),
        (0.022,  0.0115),
        (0.022,  0.0135),
        (0.012,  0.0135),
    ]
    _add_revolved(bm_w, wheel_prof, (0, 0, 0), axis="X", segs=32, mat_idx=0, cap_ends=True)
    # Paint groove inner faces dark grip (mat_idx=1) and central bearing hub chrome (mat_idx=2)
    for f in bm_w.faces:
        c = f.calc_center_median()
        r = math.hypot(c.y, c.z)
        if abs(c.x) < 0.0082 and r > 0.059:
            f.material_index = 1
        elif r < 0.023:
            f.material_index = 2
    created.append(_finalize_mesh(
        PFX + "FrontPulleyWheel", bm_w, [mats["accent"], mats["grip"], mats["steel"]],
        spindle, coll, smooth_angle_deg=40.0
    ))

    # 3. Lat-bar connection hardware (parented to P_lat_bar so it moves with Stroke!)
    lat_bar = bpy.data.objects["P_lat_bar"]
    bm_hw = bmesh.new()
    # Local coordinates on P_lat_bar (bar center is at z=0.060, radius=0.017 -> bar top z=0.077)
    # a) Welded swivel clevis collar around center of lat bar (mat 0: steel)
    _add_cyl(bm_hw, (0.0, 0.0, 0.060), 0.021, 0.036, axis="X", segs=20, mat_idx=0, bevel=0.0015)
    # Vertical swivel lug loop on top of collar (z = 0.076 .. 0.105)
    for sx in (-1.0, 1.0):
        _add_box(bm_hw, (sx * 0.011, 0.0, 0.090), (0.006, 0.014, 0.026), mat_idx=0, bevel=0.0012, segments=1)
    _add_cyl(bm_hw, (0.0, 0.0, 0.099), 0.0045, 0.032, axis="X", segs=12, mat_idx=0)

    # b) Oval steel snap-hook carabiner (z = 0.094 .. 0.150, lying in YZ plane)
    # Built as a smooth closed 3D swept oval tube (wire radius 0.0045)
    r_wire = 0.0045
    n_path = 24
    n_ring = 10
    cy_mid, cz_mid = 0.0, 0.122
    ry_oval, rz_oval = 0.014, 0.027
    path_pts = [
        Vector((0.0, cy_mid + ry_oval * math.cos(math.tau * i / n_path),
                cz_mid + rz_oval * math.sin(math.tau * i / n_path)))
        for i in range(n_path)
    ]
    c_rings = []
    for i in range(n_path):
        p_prev = path_pts[(i - 1) % n_path]
        p_next = path_pts[(i + 1) % n_path]
        t_vec = (p_next - p_prev).normalized()
        n_vec = Vector((1.0, 0.0, 0.0))
        b_vec = t_vec.cross(n_vec).normalized()
        ring = []
        for j in range(n_ring):
            a = math.tau * j / n_ring
            pt = path_pts[i] + r_wire * (math.cos(a) * n_vec + math.sin(a) * b_vec)
            ring.append(bm_hw.verts.new(pt))
        c_rings.append(ring)
    for i in range(n_path):
        r0, r1 = c_rings[i], c_rings[(i + 1) % n_path]
        for j in range(n_ring):
            j1 = (j + 1) % n_ring
            f = bm_hw.faces.new((r0[j], r0[j1], r1[j1], r1[j]))
            f.material_index = 0
    # Carabiner knurled gate sleeve on front (-Y) leg
    _add_cyl(bm_hw, (0.0, -ry_oval, cz_mid), 0.0068, 0.022, axis="Z", segs=12, mat_idx=0, bevel=0.001)

    # c) Steel crimped cable thimble & ferrule collar (z = 0.145 .. 0.172)
    _add_cyl(bm_hw, (0.0, 0.0, 0.158), 0.0085, 0.026, axis="Z", segs=16, mat_idx=0, bevel=0.0015)

    # d) Molded black rubber stopper ball (Ø38 mm revolved barrel-sphere at z = 0.168 .. 0.204 -> z_world = 1.968..2.004)
    sb_prof = [
        (0.009, -0.018),
        (0.014, -0.016),
        (0.018, -0.010),
        (0.0195, -0.003),
        (0.0195,  0.003),
        (0.018,  0.010),
        (0.014,  0.016),
        (0.009,  0.018),
    ]
    _add_revolved(bm_hw, sb_prof, (0.0, 0.0, 0.186), axis="Z", segs=24, mat_idx=1, cap_ends=True)

    created.append(_finalize_mesh(
        PFX + "BarHardware", bm_hw, [mats["steel"], mats["grip"]], lat_bar, coll, smooth_angle_deg=45.0
    ))
    return created


def _build_acrylic_shields_and_clips(root, coll, mats):
    """Build 2-piece front translucent acrylic shields, 6 L-clips + hex bolts, and rear upper smoked shield."""
    created = []

    # 1. Twin front acrylic panels (left & right, open 72 mm center pin slot x=[-0.036, +0.036])
    #    Each panel: x = +/-[0.036, 0.200] (164 mm wide), y = [0.401, 0.405] (4 mm thick), z = [0.132, 1.915] (1.783 m tall)
    bm_a = bmesh.new()
    for sx in (-1.0, 1.0):
        _add_box(bm_a, (sx * 0.118, 0.403, 1.0235), (0.164, 0.004, 1.783), mat_idx=0, bevel=0.0012, segments=1)
    created.append(_finalize_mesh(PFX + "AcrylicFront", bm_a, [mats["acrylic"]], root, coll, smooth_angle_deg=35.0))

    # 2. Rear upper smoked acrylic panel behind guide rods above accessory tray (z = 1.390 .. 1.915, y = [0.598, 0.602])
    bm_r = bmesh.new()
    _add_box(bm_r, (0.0, 0.600, 1.6525), (0.396, 0.004, 0.525), mat_idx=0, bevel=0.0012, segments=1)
    created.append(_finalize_mesh(PFX + "AcrylicRearUpper", bm_r, [mats["acrylic_smoke"]], root, coll, smooth_angle_deg=35.0))

    # 3. 6 front L-clips + silver washers + hex socket bolts (3 left, 3 right at bottom/mid/top like GTA6!)
    #    Plus 4 small rear clips holding AcrylicRearUpper to rear chrome tubes
    bm_c = bmesh.new()
    clip_zs = (0.230, 1.025, 1.815)
    for sx in (-1.0, 1.0):
        for cz in clip_zs:
            # Side leg embedded 3 mm into upright inner face (x = +/-0.202); Y stepped >= 3 mm inside tabs (no coplanar faces)
            _add_box(bm_c, (sx * 0.202, 0.403, cz), (0.010, 0.010, 0.044), mat_idx=0, bevel=0.0012, segments=1)
            # Front clamping tab overlapping acrylic edge (y = [0.391, 0.399], 2 mm clear of acrylic y=0.401)
            _add_box(bm_c, (sx * 0.189, 0.395, cz), (0.036, 0.008, 0.038), mat_idx=0, bevel=0.0015, segments=1)
            # Rear backing pad behind acrylic (y = [0.407, 0.415], 2 mm clear of acrylic y=0.405)
            _add_box(bm_c, (sx * 0.189, 0.411, cz), (0.032, 0.008, 0.034), mat_idx=0, bevel=0.0012, segments=1)
            # Stainless bolt shank spanning cleanly from front tab (0.394) through acrylic to rear pad (0.412)
            _add_cyl(bm_c, (sx * 0.184, 0.403, cz), 0.0046, 0.018, axis="Y", segs=12, mat_idx=1)
            # Front silver stainless washer + hex socket cap head (prominent metallic dot on black clip, like GTA6!)
            _add_hex_bolt(bm_c, (sx * 0.184, 0.391, cz), "Y", head_r=0.0072, head_h=0.0055,
                          washer_r=0.0115, washer_h=0.0026, sign=-1.0, mat_idx=1)

        # 2 rear upper shield clips per side (at z = 1.460, 1.840) linking AcrylicRearUpper to rear chrome tubes
        for rz in (1.460, 1.840):
            _add_box(bm_c, (sx * 0.205, 0.576, rz), (0.036, 0.042, 0.026), mat_idx=0, bevel=0.0015, segments=1)
            _add_cyl(bm_c, (sx * 0.186, 0.598, rz), 0.0042, 0.014, axis="Y", segs=10, mat_idx=1)
            _add_hex_bolt(bm_c, (sx * 0.186, 0.605, rz), "Y", head_r=0.006, head_h=0.005,
                          washer_r=0.009, washer_h=0.0024, sign=1.0, mat_idx=1)

    created.append(_finalize_mesh(
        PFX + "ShieldClips", bm_c, [mats["grip"], mats["steel"]], root, coll, smooth_angle_deg=35.0
    ))
    return created


def _build_lower_chassis_and_grounding(root, coll, mats):
    """Build accurately grounded lower base spine, front crossbar, stabilizer feet, L-anchor flanges & end-caps."""
    created = []

    # 1. Red structural lower chassis: base spine + front crossbar + seat post + diagonal roller brace + 4 L-anchor flanges
    bm = bmesh.new()
    # Main base spine (64 x 74 mm, z=[0.016, 0.090], y=[-0.550, +0.400] embedded cleanly into housing.001)
    _add_box(bm, (0.0, -0.075, 0.053), (0.064, 0.950, 0.074), mat_idx=0, bevel=0.005, segments=2)

    # Front crossbar (72 x 64 mm, x=[-0.360, +0.360], y=[-0.586, -0.514], z=[0.012, 0.076])
    _add_box(bm, (0.0, -0.550, 0.044), (0.720, 0.072, 0.064), mat_idx=0, bevel=0.005, segments=2)

    # Seat post (60 x 76 mm, y=[-0.218, -0.142], z=[0.084, 0.412])
    _add_box(bm, (0.0, -0.180, 0.248), (0.060, 0.076, 0.328), mat_idx=0, bevel=0.005, segments=2)
    # Welded seat-post base gusset collar
    _add_box(bm, (0.0, -0.180, 0.098), (0.072, 0.094, 0.024), mat_idx=0, bevel=0.0025, segments=1)

    # Diagonal structural truss brace from seat post to thigh-roller vertical receiver sleeve (44 x 44 mm)
    _add_beam_ab(bm, (0.0, -0.180, 0.235), (0.0, -0.530, 0.385), 0.044, 0.044, mat_idx=0, bevel=0.0035, segments=2)

    # Front stabilizer feet (dark satin mat_idx=1: 56 x 54 mm, x=+/-0.280, y=[-0.770, -0.550], z=[0.014, 0.068])
    for sx in (-1.0, 1.0):
        _add_box(bm, (sx * 0.280, -0.660, 0.041), (0.056, 0.220, 0.054), mat_idx=1, bevel=0.0045, segments=2)
        # Tube open end-caps (mat_idx=2: matte black plastic)
        _add_tube_cap(bm, (sx * 0.360, -0.550, 0.044), "X", sx, 0.072, 0.064, depth=0.010, mat_idx=2)
        _add_tube_cap(bm, (sx * 0.280, -0.770, 0.041), "Y", -1.0, 0.056, 0.054, depth=0.010, mat_idx=2)

    # Molded heavy rubber floor pads seated DEAD FLUSH at z = 0.000 m (embedded >= 3 mm into tube underside)
    for sx in (-1.0, 1.0):
        # Front crossbar outer rubber pads (z = [0.000, 0.017], clear of front_foot z_min=0.014 by 3 mm)
        _add_box(bm, (sx * 0.295, -0.550, 0.0085), (0.090, 0.062, 0.017), mat_idx=2, bevel=0.0018, segments=1)
        # Front stabilizer foot front rubber pads (x = +/-[0.258, 0.302] -> 2 mm clear of anchor flange x=+/-0.304!)
        _add_box(bm, (sx * 0.280, -0.720, 0.009), (0.044, 0.088, 0.018), mat_idx=2, bevel=0.0018, segments=1)
    # Center base spine mid rubber pad (z = [0.000, 0.020])
    _add_box(bm, (0.0, 0.220, 0.010), (0.072, 0.140, 0.020), mat_idx=2, bevel=0.0018, segments=1)

    # 4 Welded L-shaped steel floor anchor flanges with silver floor-anchor hex bolts & washers (z_min = 0.0000!)
    anchor_specs = [
        # (attach_x, out_sign, center_y, wall_h, mat_idx)
        (-0.308, -1.0, -0.710, 0.056, 0),  # front-left stabilizer foot
        ( 0.308,  1.0, -0.710, 0.056, 0),  # front-right stabilizer foot
        (-0.260, -1.0,  0.475, 0.086, 0),  # tower base left
        ( 0.260,  1.0,  0.475, 0.086, 0),  # tower base right
    ]
    for ax, sx, ay, wh, midx in anchor_specs:
        # Horizontal floor foot plate: z = [0.000, 0.010], inner edge at ax - 4 mm (4 mm clear of gusset inner edge ax)
        _add_box(bm, (ax + sx * 0.032, ay, 0.005), (0.072, 0.074, 0.010), mat_idx=midx, bevel=0.0015, segments=1)
        # Vertical gusset tab welded to frame side (inner face at ax, 4 mm clear of foot plate inner face ax - 4 mm!)
        _add_box(bm, (ax + sx * 0.006, ay, 0.005 + (wh - 0.005) * 0.5), (0.012, 0.066, wh - 0.005),
                 mat_idx=midx, bevel=0.0015, segments=1)
        # Silver floor-anchor hex bolt & washer centered on foot plate
        bx = ax + sx * 0.042
        _add_hex_bolt(bm, (bx, ay, 0.010), "Z", head_r=0.009, head_h=0.0065,
                      washer_r=0.0145, washer_h=0.0026, sign=1.0, mat_idx=3)

    # Under-seat steel mounting plate + 4 downward-facing silver hex flange bolts
    _add_box(bm, (0.0, -0.180, 0.410), (0.210, 0.190, 0.012), mat_idx=1, bevel=0.002, segments=1)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            _add_hex_bolt(bm, (sx * 0.078, -0.180 + sy * 0.068, 0.404), "Z",
                          head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=-1.0, mat_idx=3)

    created.append(_finalize_mesh(
        PFX + "LowerChassis", bm, [mats["frame"], mats["silver"], mats["grip"], mats["steel"]],
        root, coll, smooth_angle_deg=35.0
    ))
    return created


def _build_seat_and_thigh_rollers(root, coll, mats):
    """Build contoured lofted seat cushion (top z=0.500 m) and adjustable thigh-roller assembly (z=0.594..0.726)."""
    created = []

    # 1. Contoured lofted seat cushion (same tapered superellipse welt+stitch geometry as equipment_machines.pad())
    #    Size (0.36, 0.34, 0.086), centered at (0.0, -0.180, 0.4570) -> top z = 0.5000 m, bottom z = 0.4140 m
    bm_s = bmesh.new()
    sx_w, sy_l, sz_h = 0.360, 0.340, 0.086
    profile = (
        (-0.50, 0.89), (-0.355, 0.978), (-0.345, 0.9803), (-0.18, 0.99), (-0.12, 0.965),
        (-0.05, 1.00), (0.27, 0.985), (0.455, 0.9217), (0.465, 0.90125), (0.50, 0.77),
    )
    sew = bm_s.loops.layers.uv.new("Stitch pitch")
    segs = 32
    rings = []
    for index, (depth, fullness) in enumerate(profile):
        ring = []
        for i in range(segs):
            t = math.tau * i / segs
            u, v = math.cos(t), math.sin(t)
            u = math.copysign(abs(u) ** 0.40, u)
            v = math.copysign(abs(v) ** 0.40, v)
            px = 0.5 * sx_w * u * fullness * (1.0 - 0.08 * max(0.0, v))
            py = 0.5 * sy_l * v * fullness
            pz = sz_h * depth
            ring.append(bm_s.verts.new((px, py, pz)))
        if rings:
            dist = 0.0
            for i in range(segs):
                j = (i + 1) % segs
                face = bm_s.faces.new((rings[-1][i], rings[-1][j], ring[j], ring[i]))
                if index in (2, 8):
                    face.material_index = 1
                    end = dist + (ring[j].co - ring[i].co).length
                    for loop, (u_val, v_val) in zip(face.loops, ((dist, 0.0), (end, 0.0), (end, 0.01), (dist, 0.01))):
                        loop[sew].uv = (u_val, v_val)
                    dist = end
                else:
                    face.material_index = 0
        rings.append(ring)
    # Cap bottom & top with quad-friendly fans around center points (zero n-gons!)
    c_bot = bm_s.verts.new((0.0, 0.0, sz_h * profile[0][0]))
    c_top = bm_s.verts.new((0.0, 0.0, sz_h * profile[-1][0]))
    for i in range(segs):
        j = (i + 1) % segs
        f_b = bm_s.faces.new((c_bot, rings[0][j], rings[0][i]))
        f_b.material_index = 0
        f_t = bm_s.faces.new((c_top, rings[-1][i], rings[-1][j]))
        f_t.material_index = 0
    # Populate UV map on non-stitch faces too
    for f in bm_s.faces:
        if f.material_index != 1:
            for loop in f.loops:
                loop[sew].uv = (loop.vert.co.x * 2.0, loop.vert.co.y * 2.0)

    seat_ob = _finalize_mesh(
        PFX + "Seat", bm_s, [mats["pad"], mats["stitch"]], root, coll,
        loc=(0.0, -0.180, 0.4570), smooth_angle_deg=55.0, add_uv=False,
    )
    created.append(seat_ob)

    # Molded black under-seat ABS pan trim (hugging seat underside z = 0.412..0.422)
    bm_tr = bmesh.new()
    _add_box(bm_tr, (0.0, -0.180, 0.416), (0.312, 0.292, 0.012), mat_idx=0, bevel=0.004, segments=2)
    created.append(_finalize_mesh(PFX + "SeatTrim", bm_tr, [mats["grip"]], root, coll, smooth_angle_deg=35.0))

    # 2. Thigh-roller telescoping post assembly (receiver sleeve + wear collar + square chrome post + index holes + pop-pin)
    ry, rz = -0.530, 0.660
    bm_rp = bmesh.new()
    # Vertical outer receiver sleeve (56 x 56 mm, z=[0.072, 0.506], dark satin mat_idx=0)
    _add_box(bm_rp, (0.0, ry, 0.289), (0.056, 0.056, 0.434), mat_idx=0, bevel=0.0045, segments=2)
    # Molded black plastic wear-collar bezel at sleeve top (z=[0.496, 0.516], mat_idx=2: grip)
    _add_box(bm_rp, (0.0, ry, 0.506), (0.064, 0.064, 0.020), mat_idx=2, bevel=0.003, segments=2)

    # Square chrome telescoping vertical post (40 x 40 mm, z=[0.478, 0.668] -> 18 mm below collar bottom 0.496!)
    _add_box(bm_rp, (0.0, ry, 0.573), (0.040, 0.040, 0.190), mat_idx=1, bevel=0.0035, segments=2)
    # 5 dark index-hole detents along front (-Y) and right (+X) faces of chrome post
    # Spaced cleanly below roller hub bottom (z=0.631) so zero tangential z-fighting!
    for hz in (0.526, 0.550, 0.574, 0.598, 0.622):
        _add_cyl(bm_rp, (0.0, ry - 0.0189, hz), 0.0048, 0.0058, axis="Y", segs=12, mat_idx=2)
        _add_cyl(bm_rp, (0.0189, ry, hz), 0.0048, 0.0058, axis="X", segs=12, mat_idx=2)

    # Spring pop-pin height adjuster mounted on +X side of receiver sleeve (single continuous revolved solid!)
    pz_pin = 0.462
    pop_prof = [
        (0.0145, 0.023),  # embedded 5 mm inside sleeve wall (x=0.028)
        (0.0145, 0.039),  # dark receiver boss collar
        (0.0105, 0.041),  # chrome threaded barrel step
        (0.0105, 0.061),
        (0.0065, 0.062),  # chrome spring plunger stem
        (0.0065, 0.070),
        (0.0145, 0.072),  # red ergonomic pull-knob
        (0.0165, 0.077),
        (0.0142, 0.082),  # finger grip waist
        (0.0168, 0.088),
        (0.0158, 0.094),
        (0.0110, 0.0965),
        (0.0075, 0.0970), # chrome end button
        (0.0075, 0.0995),
    ]
    n_pop_before = len(bm_rp.faces)
    _add_revolved(bm_rp, pop_prof, (0.0, ry, pz_pin), axis="X", segs=20, mat_idx=0, cap_ends=True)
    for f in list(bm_rp.faces)[n_pop_before:]:
        cx = f.calc_center_median().x
        if cx < 0.040:
            f.material_index = 0  # dark boss
        elif cx < 0.0705:
            f.material_index = 1  # chrome barrel & stem
        elif cx < 0.0968:
            f.material_index = 3  # red pull-knob
        else:
            f.material_index = 1  # chrome tip button

    # Roller cross-axle hub & steel shaft at z = 0.660 (mat 0: dark satin collar, mat 1: chrome shaft)
    _add_cyl(bm_rp, (0.0, ry, rz), 0.029, 0.054, axis="X", segs=24, mat_idx=0, bevel=0.0025)
    _add_cyl(bm_rp, (0.0, ry, rz), 0.016, 0.440, axis="X", segs=16, mat_idx=1)

    created.append(_finalize_mesh(
        PFX + "RollerPost", bm_rp, [mats["silver"], mats["steel"], mats["grip"], mats["frame"]],
        root, coll, smooth_angle_deg=38.0
    ))

    # 3. Contoured thigh rollers + concentric molded vinyl end-caps (z = [0.5940, 0.7260] exact!)
    bm_rl = bmesh.new()
    for sx in (-1.0, 1.0):
        # Revolved foam bolster profile from inner edge (|x|=0.024) to outer cap (|x|=0.228)
        # Outer radius = 0.0660 m -> z = 0.660 +/- 0.066 = [0.5940, 0.7260] exact!
        # Coordinates are along local axis from inner (0.024) to outer (0.228)
        raw_prof = [
            (0.030, 0.024),   # inner cuff around collar
            (0.056, 0.026),   # inner beveled shoulder
            (0.0635, 0.033),
            (0.0658, 0.048),
            (0.0660, 0.120),  # full Ø132 mm bolster crown
            (0.0656, 0.195),
            (0.0630, 0.211),  # outer shoulder before piping welt
            (0.0642, 0.215),  # raised vinyl piping bead
            (0.0600, 0.219),  # recessed concentric seam groove
            (0.0540, 0.222),  # molded concentric vinyl end-cap outer ring
            (0.0440, 0.220),  # recessed concentric ring
            (0.0360, 0.224),  # raised inner molded dome
            (0.0160, 0.2265), # flat center cap plateau
            (0.0110, 0.2255), # subtle center dimple
        ]
        if sx > 0:
            prof = [(r, ax) for (r, ax) in raw_prof]
        else:
            prof = [(r, -ax) for (r, ax) in reversed(raw_prof)]
        n_before = len(bm_rl.faces)
        _add_revolved(bm_rl, prof, (0.0, ry, rz), axis="X", segs=32, mat_idx=0, cap_ends=True)
        # Assign molded vinyl cap material (mat_idx=1: grip) to outer end-cap faces (|x| > 0.214)
        for f in list(bm_rl.faces)[n_before:]:
            if abs(f.calc_center_median().x) > 0.214:
                f.material_index = 1

    created.append(_finalize_mesh(
        PFX + "ThighRollers", bm_rl, [mats["pad"], mats["grip"]], root, coll, smooth_angle_deg=50.0
    ))
    return created


# ==============================================================================
# Existing-object updates (reposition, reroute cables, extend guide rods, rebind mats)
# ==============================================================================

def _extend_guide_rods(root):
    """Extend existing chrome guide_rod.002/.003 vertically to full tower height (z = 0.100 .. 2.120 m)."""
    touched = []
    target_z_min = 0.100
    target_z_max = 2.120
    target_h = target_z_max - target_z_min
    target_cz = 0.5 * (target_z_min + target_z_max)

    for nm in ("guide_rod.002", "guide_rod.003"):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        _tag_and_restore_xform(ob)
        # Record original mesh Z span once, then rescale mesh vertices cleanly in local Z (keep scale=(1,1,1))
        me = ob.data
        if PROP_ORIG_MESH_Z not in ob:
            zs = [v.co.z for v in me.vertices]
            ob[PROP_ORIG_MESH_Z] = [float(min(zs)), float(max(zs))]
        orig_min, orig_max = ob[PROP_ORIG_MESH_Z]
        orig_h = orig_max - orig_min
        cur_zs = [v.co.z for v in me.vertices]
        cur_h = max(cur_zs) - min(cur_zs)
        if orig_h > 1e-4 and abs(cur_h - target_h) > 1e-4:
            # First normalize from current span back to [-0.5, +0.5], then scale to target_h
            c_mid = 0.5 * (min(cur_zs) + max(cur_zs))
            scale_z = target_h / cur_h
            for v in me.vertices:
                v.co.z = (v.co.z - c_mid) * scale_z
            me.update()
        ob.location.z = target_cz
        touched.append(nm)
    return touched


def _reroute_cables_and_sheave(root):
    """Raise P_Head sheave.001 to top of tower and reroute load & lat-bar cables with zero penetrations."""
    touched = []

    # 1. Move P_Head sheave.001 up to REAR_SHEAVE_POS (preserving spindle & Stroke rotation driver!)
    sheave = bpy.data.objects.get("P_Head sheave.001")
    if sheave is not None:
        _tag_and_restore_xform(sheave)
        sheave.location = REAR_SHEAVE_POS.copy()
        touched.append(sheave.name)

    # 2. Reroute Coated load cable.001 (19 points: vertical stack -> 90-deg wrap around rear sheave -> horizontal to front pulley)
    #    Keep spline point 0 driver (0.9433 + 0.28*v) intact!
    load_cable = bpy.data.objects.get("Coated load cable.001")
    if load_cable is not None:
        _tag_and_restore_xform(load_cable)
        sp = load_cable.data.splines[0]
        if PROP_ORIG_SPLINE not in load_cable:
            load_cable[PROP_ORIG_SPLINE] = json.dumps([[float(c) for c in pt.co] for pt in sp.points])
        pts_new = [(0.0, 0.580, 0.9433)]
        for i in range(17):
            # Angle from 0 (back tangent y=+R, z=0) to pi/2 (top tangent y=0, z=+R)
            t = (math.pi * 0.5) * i / 16.0
            py = REAR_SHEAVE_POS.y + REAR_SHEAVE_R * math.cos(t)
            pz = REAR_SHEAVE_POS.z + REAR_SHEAVE_R * math.sin(t)
            pts_new.append((0.0, py, pz))
        # Final point meets front pulley top tangent seamlessly
        pts_new.append((0.0, FRONT_PULLEY_POS.y, CABLE_TOP_Z))
        assert len(pts_new) == len(sp.points), f"Expected {len(sp.points)} pts, got {len(pts_new)}"
        for pt, xyz in zip(sp.points, pts_new):
            pt.co = (*xyz, 1.0)
        load_cable.data.bevel_depth = 0.0045
        touched.append(load_cable.name)

    # 3. Reroute Lat bar cable (13 points: 90-deg wrap around front pulley -> dead-vertical drop at y=-0.450 to ferrule)
    #    Update points[11] and points[12] driver base Z values so cable meets BarHardware cleanly at all Strokes!
    bar_cable = bpy.data.objects.get("Lat bar cable")
    if bar_cable is not None:
        _tag_and_restore_xform(bar_cable)
        sp = bar_cable.data.splines[0]
        if PROP_ORIG_SPLINE not in bar_cable:
            bar_cable[PROP_ORIG_SPLINE] = json.dumps([[float(c) for c in pt.co] for pt in sp.points])
        pts_bar = []
        for i in range(11):
            # Angle from 0 (top tangent y=0, z=+R) to pi/2 (front tangent y=-R, z=0)
            t = (math.pi * 0.5) * i / 10.0
            py = FRONT_PULLEY_POS.y - FRONT_PULLEY_R * math.sin(t)
            pz = FRONT_PULLEY_POS.z + FRONT_PULLEY_R * math.cos(t)
            pts_bar.append((0.0, py, pz))
        # Dead-vertical drop at y = -0.450 down into stopper ball (z=2.000) and cable ferrule (z=1.954)
        pts_bar.append((0.0, CABLE_DROP_Y, 2.000))
        pts_bar.append((0.0, CABLE_DROP_Y, 1.954))
        assert len(pts_bar) == len(sp.points), f"Expected {len(sp.points)} pts, got {len(pts_bar)}"
        for pt, xyz in zip(sp.points, pts_bar):
            pt.co = (*xyz, 1.0)
        bar_cable.data.bevel_depth = 0.0045

        # Update existing Stroke drivers on points[11].co.z and points[12].co.z
        if bar_cable.data.animation_data and bar_cable.data.animation_data.drivers:
            for fc in bar_cable.data.animation_data.drivers:
                if fc.data_path == "splines[0].points[11].co" and fc.array_index == 2:
                    fc.driver.expression = "2.000-0.48*v"
                elif fc.data_path == "splines[0].points[12].co" and fc.array_index == 2:
                    fc.driver.expression = "1.954-0.48*v"
        touched.append(bar_cable.name)

    return touched


def _move_front_exercise_guide(root):
    """Move Exercise guide.003 (and all 11 children intact, text untouched) onto unobstructed upper header."""
    guide = bpy.data.objects.get("Exercise guide.003")
    if guide is None:
        return []
    _tag_and_restore_xform(guide)
    # Front face of HeaderPanel is y = 0.390, z = [1.922, 2.094]; boom gusset bottom is z = 2.096
    # Place Exercise guide.003 centered at (0.0, 0.381, 2.005) -> top z = 2.069 (27 mm clear below gusset!)
    guide.location = Vector((0.0, 0.381, 2.005))
    guide.rotation_euler = Euler((math.radians(86.0), 0.0, 0.0), "XYZ")
    return [guide.name]


def _rebind_latpulldown_materials(root, mats):
    """Switch P_lat_pulldown kept objects from shared E_* materials to dedicated Ddetail6_LP_* copies.

    Uses PROP_ORIG_MATS snapshot so repeat apply() runs restore and rebind deterministically.
    Always clones mesh/curve datablocks shared outside P_lat_pulldown so no other machine is affected.
    """
    src_to_dst = {k: bpy.data.materials[v] for k, v in MAT_MAP.items() if v in bpy.data.materials}
    lp_objs = set(_descendants(root))
    lp_objs.add(root)

    external_meshes = set()
    external_curves = set()
    for ob in bpy.data.objects:
        if ob in lp_objs:
            continue
        if ob.type == "MESH" and ob.data is not None:
            external_meshes.add(ob.data)
        elif ob.type == "CURVE" and ob.data is not None:
            external_curves.add(ob.data)

    cloned_data = {}
    rebound = []
    for ob in _descendants(root):
        if ob.name.startswith(PFX):
            continue
        if ob.type not in ("MESH", "CURVE") or ob.data is None:
            continue

        if PROP_ORIG_MATS in ob:
            orig_names = json.loads(ob[PROP_ORIG_MATS])
        else:
            orig_names = [m.name if m else None for m in ob.data.materials]
            if not any(n in src_to_dst for n in orig_names):
                continue
            ob[PROP_ORIG_MATS] = json.dumps(orig_names)
            ob[PROP_PKG] = PKG_KEY

        data = ob.data
        is_shared_externally = (
            (ob.type == "MESH" and data in external_meshes)
            or (ob.type == "CURVE" and data in external_curves)
        )
        if is_shared_externally:
            if data not in cloned_data:
                new_d = data.copy()
                new_d.name = PFX + data.name
                cloned_data[data] = new_d
            ob.data = cloned_data[data]

        for idx, orig_name in enumerate(orig_names):
            if idx < len(ob.data.materials):
                if orig_name in src_to_dst:
                    ob.data.materials[idx] = src_to_dst[orig_name]
                elif orig_name is not None and orig_name in bpy.data.materials:
                    ob.data.materials[idx] = bpy.data.materials[orig_name]
        rebound.append(ob.name)
    return rebound


# ==============================================================================
# Main entry point (idempotent)
# ==============================================================================

def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"{ROOT_NAME} not found in scene")

    parent_coll = bpy.data.collections["SET"]
    coll = parent_coll.children.get(COLL)
    if coll is None:
        if bpy.data.collections.get(COLL):
            raise ValueError(f"{COLL} already exists outside SET")
        coll = bpy.data.collections.new(COLL)
        parent_coll.children.link(coll)

    # 1. Clean up any previous run's created objects & orphan meshes (idempotency)
    for ob in list(coll.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
    for ob in list(bpy.data.objects):
        if ob.name.startswith(PFX):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
    for me in list(bpy.data.meshes):
        if me.name.startswith(PFX) and me.users == 0:
            bpy.data.meshes.remove(me)

    # 2. Remove replaced obsolete P_lat_pulldown objects (no-op on 2nd run)
    removed = []
    for nm in REPLACED_NAMES:
        ob = bpy.data.objects.get(nm)
        if ob is not None and ob.parent == root:
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            removed.append(nm)

    # 3. Build dedicated lat-pulldown materials (zero edits to shared gym materials)
    mats = _build_materials()

    # 4. Update kept objects (guide rods, head sheave, cables, front exercise guide)
    touched = []
    touched.extend(_extend_guide_rods(root))
    touched.extend(_reroute_cables_and_sheave(root))
    touched.extend(_move_front_exercise_guide(root))

    # 5. Build upgraded geometry assemblies
    created = []
    created.extend(_build_tower_and_boom(root, coll, mats))
    created.extend(_build_front_pulley_and_bar_hardware(root, coll, mats))
    created.extend(_build_acrylic_shields_and_clips(root, coll, mats))
    created.extend(_build_lower_chassis_and_grounding(root, coll, mats))
    created.extend(_build_seat_and_thigh_rollers(root, coll, mats))

    # 6. Rebind kept P_lat_pulldown objects to dedicated material copies
    rebound = _rebind_latpulldown_materials(root, mats)

    # Clean up any leftover orphan cloned meshes from prior runs
    for me in list(bpy.data.meshes):
        if me.name.startswith(PFX) and me.users == 0:
            bpy.data.meshes.remove(me)

    bpy.context.view_layer.update()

    # Compute total triangle count across P_lat_pulldown
    deps = bpy.context.evaluated_depsgraph_get()
    lp_tris = 0
    added_tris = 0
    for ob in _descendants(root):
        if ob.type in ("MESH", "CURVE", "FONT"):
            eo = ob.evaluated_get(deps)
            me = eo.to_mesh()
            if me and len(me.vertices):
                me.calc_loop_triangles()
                t = len(me.loop_triangles)
                lp_tris += t
                if ob.name.startswith(PFX):
                    added_tris += t
            eo.to_mesh_clear()

    return dict(
        objects_removed=len(removed),
        removed_names=removed,
        objects_added=len(created),
        added_names=[o.name for o in created],
        existing_objects_touched=touched,
        materials_created=sorted(m.name for m in mats.values() if m.name.startswith(PFX)),
        objects_rebound_materials=len(rebound),
        added_triangles=added_tris,
        latpulldown_total_triangles=lp_tris,
        latpulldown_total_objects=len(_descendants(root)),
    )


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    save = None
    if "--save" in argv:
        save = Path(argv[argv.index("--save") + 1]).expanduser().resolve()
        root_dir = Path(__file__).resolve().parents[2]
        if any(save.is_relative_to((root_dir / "promo" / d).resolve()) for d in ("scenes", "models")):
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        if save.suffix.lower() != ".blend":
            raise SystemExit("--save must end with .blend")
        save.parent.mkdir(parents=True, exist_ok=True)
    res = apply()
    print("detail6_latpulldown", json.dumps(res, ensure_ascii=False))
    if save is not None:
        bpy.ops.wm.save_as_mainfile(
            filepath=str(save), copy=True, compress=True, relative_remap=False
        )
        print("saved", save)


if __name__ == "__main__":
    _main()
