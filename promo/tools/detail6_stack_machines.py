"""detail6 stack_machines: commercial-grade upgrade for the remaining 5 stack machines.

Targets (1 instance each in promo/scenes/scene_gym.blend):
  - P_cable_crossover (dual stack)
  - P_seated_cable_row
  - P_chest_press_machine
  - P_pec_deck
  - P_leg_extension

Reuses modeling helpers from detail6_latpulldown.py without altering P_lat_pulldown or any
shared gym material (E_frame, E_silver, E_pad, E_stack, E_steel, E_grip, E_accent).

What this module does (fully idempotent, custom-prop tagged, never saves unless --save):
  1. Common to all 5 machines:
     - Replaces opaque hfront_wing panels with 2-piece translucent/scratched acrylic stack
       shields (72 mm open center pin slot) + 6 matte-black L-clips with silver washers &
       hex socket bolts per stack, exposing the full-height chrome guide rods behind them.
     - Fixes every floor grounding error (world z = 0.000 m, <= 1 mm error) across sunk
       bases/feet (-4.2 to -28.3 mm) and floating tower feet/footbars (+4.0 to +12.0 mm),
       adding rubber isolation pads, welded L-shaped floor anchor flanges with silver hex
       bolts, and black molded plastic tube end-caps on open tube ends.
     - Creates per-machine dedicated material copies (Ddetail6_SM_<CODE>_*) with macro
       roughness variation, AO crevice darkening, contact-glossy leather, cast-iron stipple,
       vertical-streak chrome, and lightweight Fresnel-blended scratched acrylic.
     - Adds visible stainless hex fasteners at pulley axles, splice brackets, and seat/frame joints.
  2. Per-machine structural fixes (only where audit found real defects):
     - P_cable_crossover: removes stack-blocking post_b/link pillars, converts both stacks
       to full-height (2.26 m) portal towers with 2.03 m chrome guide rods, moves front
       Exercise guides intact onto unobstructed upper headers, cuts open pulley portal slots
       at the top of Perforated uprights, raises Head sheaves to z=2.164 m, and reroutes
       both load cables with 0 frame penetrations + bolted trolley head pulley guards.
     - P_seated_cable_row: replaces clipping Head bearing mount and reroutes low cable along
       an external right-side channel with 3 guarded sheaves (0 penetrations through Pin shaft,
       seat_post, chest_post, or foot_plate) + stopper ball/carabiner at row handle.
     - P_chest_press_machine: raises Head sheave +35 mm with split side hanger brackets to
       clear cover/mount (0 cable penetrations) + drive_cam guard & fasteners.
     - P_pec_deck: lowers front header fascia below z=1.50 m fly_cable plane, adds split
       Head sheave hangers + central cable splitter block (0 cable penetrations), keeping
       seat top untouched for Dgym_life_Phone_on_pecdeck.
     - P_leg_extension: adds split Head sheave hangers, reroutes low cable via guarded front-
       right sheaves outside leg_pivot_body (0 cable penetrations), and upgrades bare shin
       roller cylinder to contoured bolster with concentric molded vinyl end-caps.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_stack_machines.py [-- --save out.blend]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import detail6_latpulldown as lp

COLL = "DETAIL6_stack_machines"
PFX = "Ddetail6_SM_"
PKG_KEY = "detail6_stack_machines"
PROP_PKG = "detail6_sm_pkg"
PROP_ORIG_MAT = "detail6_sm_orig_matrix"
PROP_ORIG_SPLINE = "detail6_sm_orig_spline"
PROP_ORIG_MATS = "detail6_sm_orig_mats"
PROP_ORIG_ZBOUNDS = "detail6_sm_orig_zbounds"

TARGET_ROOTS = (
    ("CC", "P_cable_crossover"),
    ("SCR", "P_seated_cable_row"),
    ("CP", "P_chest_press_machine"),
    ("PD", "P_pec_deck"),
    ("LE", "P_leg_extension"),
)

REPLACED_BY_MACHINE = {
    "CC": (
        "post_b", "post_b.001", "link", "link.001", "foot.001", "foot.002",
        "hfront_wing.004", "hfront_wing.005", "hfront_wing.006", "hfront_wing.007",
        "Side shroud.008", "Side shroud.010", "Side shroud.012", "Side shroud.014",
        "cover.002", "cover.003",
        "Exposed tower tube.004", "Exposed tower tube.005", "Exposed tower tube.006", "Exposed tower tube.007",
        "Cable bay side rail.004", "Cable bay side rail.005", "Cable bay side rail.006", "Cable bay side rail.007",
        "Head bearing mount.002", "Head bearing mount.003",
        "Bearing pedestal.002", "Bearing pedestal.003",
        "Head pulley guard", "Head pulley guard.001", "Head pulley guard.002", "Head pulley guard.003",
    ),
    "SCR": (
        "base.006",
        "hfront_wing.018", "hfront_wing.019",
        "Head bearing mount.009", "Bearing pedestal.009",
        "Cable bay side rail.018", "Cable bay side rail.019",
        "Lower sheave.002", "Lower sheave.003", "Idler bracket.001",
    ),
    "CP": (
        "base.004",
        "hfront_wing.010", "hfront_wing.011",
        "Head bearing mount.005", "Bearing pedestal.005",
        "Cable bay side rail.010", "Cable bay side rail.011",
    ),
    "PD": (
        "base.002",
        "hfront_wing", "hfront_wing.001",
        "Head bearing mount", "Bearing pedestal",
        "Cable bay side rail", "Cable bay side rail.001",
        "cover",
    ),
    "LE": (
        "base.010",
        "hfront_wing.028", "hfront_wing.029",
        "Head bearing mount.014", "Bearing pedestal.014",
        "Cable bay side rail.028", "Cable bay side rail.029",
        "Lower sheave.008", "Lower sheave.009", "Idler bracket.004",
        "roller.001", "roller_cap_l.001", "roller_cap_r.001",
    ),
}


# ==============================================================================
# Shared local helpers (wrapping lp helpers with SM tagging)
# ==============================================================================

def _tag_and_restore_xform(ob):
    if ob.get(PROP_PKG) == PKG_KEY and PROP_ORIG_MAT in ob:
        vals = list(ob[PROP_ORIG_MAT])
        ob.matrix_basis = Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])
    else:
        ob[PROP_PKG] = PKG_KEY
        ob[PROP_ORIG_MAT] = [float(v) for row in ob.matrix_basis for v in row]


def _fix_closed_island_normals(bm):
    """Mathematically guarantee every closed connected island in bm has outward-pointing normals."""
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    visited = set()
    for f in bm.faces:
        if f in visited:
            continue
        stack = [f]
        island = []
        visited.add(f)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf not in visited:
                        visited.add(nf)
                        stack.append(nf)
        # First make winding consistent within the island
        bmesh.ops.recalc_face_normals(bm, faces=island)
        # Check if island is closed (every edge has 2 link faces)
        is_closed = all(len(e.link_faces) == 2 for fc in island for e in fc.edges)
        if not is_closed:
            continue
        # Signed volume relative to island centroid (robust against large offsets)
        verts = {v for fc in island for v in fc.verts}
        ref = sum((v.co for v in verts), Vector((0.0, 0.0, 0.0))) / max(1, len(verts))
        vol6 = 0.0
        for fc in island:
            vs = [v.co - ref for v in fc.verts]
            v0 = vs[0]
            for i in range(1, len(vs) - 1):
                vol6 += v0.dot(vs[i].cross(vs[i + 1]))
        if vol6 < 0.0:
            bmesh.ops.reverse_faces(bm, faces=island)


def _finalize_sm_mesh(name, bm, materials, parent, coll, smooth_angle_deg=36.0,
                      loc=(0, 0, 0), rot=(0, 0, 0)):
    _fix_closed_island_normals(bm)
    ob = lp._finalize_mesh(name, bm, materials, parent, coll, loc=loc, rot=rot,
                           smooth_angle_deg=smooth_angle_deg, add_uv=True)
    # Re-verify signed volume on finalized mesh (since lp._finalize_mesh calls recalc_face_normals)
    bm2 = bmesh.new()
    bm2.from_mesh(ob.data)
    _fix_closed_island_normals(bm2)
    bm2.to_mesh(ob.data)
    bm2.free()
    ob.data.update()
    # Replace lp tag with our package tag
    if lp.PROP_PKG in ob:
        del ob[lp.PROP_PKG]
    ob[PROP_PKG] = PKG_KEY
    return ob


def _ensure_mesh_unique_within_root(ob, root_set):
    """Clone mesh datablock if shared by any object outside this machine's root_set."""
    me = ob.data
    if me is None or ob.type != "MESH":
        return
    shared_ext = any(o.data == me and o not in root_set for o in bpy.data.objects)
    if shared_ext:
        new_me = me.copy()
        new_me.name = PFX + "Mesh_" + ob.name
        ob.data = new_me


def _rescale_mesh_z_bounds(ob, target_z_min, target_z_max, root_set):
    """Idempotently set local-space Z span of an axis-aligned cylinder/column mesh (keeping scale=1)."""
    _tag_and_restore_xform(ob)
    _ensure_mesh_unique_within_root(ob, root_set)
    me = ob.data
    if PROP_ORIG_ZBOUNDS not in ob:
        zs = [v.co.z for v in me.vertices]
        ob[PROP_ORIG_ZBOUNDS] = [float(min(zs)), float(max(zs))]
    cur_zs = [v.co.z for v in me.vertices]
    cur_min, cur_max = min(cur_zs), max(cur_zs)
    cur_h = cur_max - cur_min
    target_h = target_z_max - target_z_min
    target_cz = 0.5 * (target_z_min + target_z_max)
    if cur_h > 1e-5 and abs(cur_h - target_h) > 1e-5:
        mid = 0.5 * (cur_min + cur_max)
        s = target_h / cur_h
        for v in me.vertices:
            v.co.z = (v.co.z - mid) * s
        me.update()
    ob.location.z = target_cz


def _clamp_mesh_top_z(ob, max_world_local_z, root_set):
    """Idempotently clamp top vertices of a vertical column (in root-local Z) to max_world_local_z."""
    _tag_and_restore_xform(ob)
    _ensure_mesh_unique_within_root(ob, root_set)
    me = ob.data
    z_lim = max_world_local_z - ob.location.z
    changed = False
    for v in me.vertices:
        if v.co.z > z_lim + 1e-6:
            v.co.z = z_lim
            changed = True
    if changed:
        me.update()


def _extend_tower_feet_to_floor(root, foot_names, floor_z, root_set):
    """Extend existing tower_foot cylinders downward cleanly to floor_z (= -root.location.z) idempotently."""
    touched = []
    for nm in foot_names:
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.parent != root:
            continue
        _tag_and_restore_xform(ob)
        _ensure_mesh_unique_within_root(ob, root_set)
        me = ob.data
        if PROP_ORIG_ZBOUNDS not in ob or len(ob[PROP_ORIG_ZBOUNDS]) < 3:
            zs = [v.co.z for v in me.vertices]
            ob[PROP_ORIG_ZBOUNDS] = [float(ob.location.z), float(min(zs)), float(max(zs))]
        orig_loc_z, _orig_zmin, orig_zmax = [float(v) for v in ob[PROP_ORIG_ZBOUNDS][:3]]
        target_top = orig_loc_z + orig_zmax
        _rescale_mesh_z_bounds(ob, floor_z, target_top, root_set)
        touched.append(nm)
    return touched


def _add_anchor_flange(bm, ax, sx, ay, floor_z, wall_h, mat_flange, mat_steel):
    """Add welded L-shaped floor anchor flange (flush at floor_z) + silver hex anchor bolt & washer.

    Guarantees >= 4 mm separation between horizontal plate inner edge and vertical gusset inner edge
    and embeds vertical gusset 5 mm into horizontal plate -> zero QA z-fighting / zero back-to-back.
    """
    _add_box = lp._add_box
    _add_hex_bolt = lp._add_hex_bolt
    # Horizontal floor foot plate: z = [floor_z, floor_z + 0.010]
    _add_box(bm, (ax + sx * 0.032, ay, floor_z + 0.005), (0.072, 0.074, 0.010),
             mat_idx=mat_flange, bevel=0.0015, segments=1)
    # Vertical gusset tab welded to frame side (starts at floor_z+0.005, inner face at ax, 4 mm clear of plate inner edge)
    gh = max(0.025, wall_h - 0.005)
    _add_box(bm, (ax + sx * 0.006, ay, floor_z + 0.005 + gh * 0.5), (0.012, 0.066, gh),
             mat_idx=mat_flange, bevel=0.0015, segments=1)
    # Silver anchor hex bolt & washer centered on foot plate
    _add_hex_bolt(bm, (ax + sx * 0.042, ay, floor_z + 0.010), "Z",
                  head_r=0.009, head_h=0.0065, washer_r=0.0145, washer_h=0.0026,
                  sign=1.0, mat_idx=mat_steel)


def _add_acrylic_stack_front(bm_acr, bm_clips, cx, y_acr, z_bot, z_top, half_w, clip_zs,
                             slot_half=0.036, upright_attach_x=None):
    """Build 2-piece translucent acrylic front shield (open center pin slot) + 6 L-clips & silver hex bolts."""
    # Each panel: width = half_w - slot_half, centered at cx +/- 0.5*(slot_half + half_w)
    pw = half_w - slot_half
    pc_off = slot_half + pw * 0.5
    ph = z_top - z_bot
    zc = 0.5 * (z_bot + z_top)
    for sx in (-1.0, 1.0):
        lp._add_box(bm_acr, (cx + sx * pc_off, y_acr, zc), (pw, 0.004, ph),
                    mat_idx=0, bevel=0.0012, segments=1)

    att_x = (half_w + 0.011) if upright_attach_x is None else upright_attach_x
    for sx in (-1.0, 1.0):
        for cz in clip_zs:
            # Side leg embedded deeply into side shroud/upright (clear of shroud inner X by >= 5 mm -> zero coplanar!)
            lp._add_box(bm_clips, (cx + sx * att_x, y_acr, cz), (0.010, 0.010, 0.042),
                        mat_idx=0, bevel=0.0012, segments=1)
            # Front clamping tab (2 mm clear in front of acrylic y_acr - 0.002)
            tab_x = cx + sx * (half_w - 0.011)
            lp._add_box(bm_clips, (tab_x, y_acr - 0.008, cz), (0.034, 0.008, 0.036),
                        mat_idx=0, bevel=0.0014, segments=1)
            # Rear backing pad (2 mm clear behind acrylic y_acr + 0.002)
            lp._add_box(bm_clips, (tab_x, y_acr + 0.008, cz), (0.030, 0.008, 0.032),
                        mat_idx=0, bevel=0.0012, segments=1)
            # Bolt shank passing cleanly through clip & acrylic
            bx = cx + sx * (half_w - 0.016)
            lp._add_cyl(bm_clips, (bx, y_acr, cz), 0.0045, 0.018, axis="Y", segs=12, mat_idx=1)
            # Front silver stainless washer + hex socket cap bolt
            lp._add_hex_bolt(bm_clips, (bx, y_acr - 0.012, cz), "Y",
                             head_r=0.0070, head_h=0.0052, washer_r=0.0110, washer_h=0.0026,
                             sign=-1.0, mat_idx=1)


def _add_guarded_sheave(bm, center, radius=0.036, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1):
    """Build a compact guarded idler/guide pulley (U-cheek guard + grooved wheel + hex axle bolt & washers)."""
    cx, cy, cz = center
    # Grooved pulley wheel (revolved around axis)
    w_prof = [
        (0.007, -0.0095),
        (radius, -0.0095),
        (radius, -0.0065),
        (radius - 0.006, -0.0030),
        (radius - 0.006,  0.0030),
        (radius,  0.0065),
        (radius,  0.0095),
        (0.007,  0.0095),
    ]
    lp._add_revolved(bm, w_prof, center, axis=axis, segs=24, mat_idx=mat_wheel, cap_ends=True)

    # Sheet-metal cheek plates flanking wheel (gap >= 3 mm from wheel outer face)
    g_h = radius * 2.15
    g_w = radius * 2.05
    if axis == "X":
        for sx in (-1.0, 1.0):
            lp._add_box(bm, (cx + sx * 0.015, cy, cz), (0.005, g_w, g_h),
                        mat_idx=mat_guard, bevel=0.0015, segments=1)
            lp._add_hex_bolt(bm, (cx + sx * 0.0175, cy, cz), "X",
                             head_r=0.0085, head_h=0.0060, washer_r=0.0125, washer_h=0.0026,
                             sign=sx, mat_idx=mat_steel)
        lp._add_cyl(bm, center, 0.0065, 0.032, axis="X", segs=12, mat_idx=mat_steel)
    else:  # axis == "Y"
        for sy in (-1.0, 1.0):
            lp._add_box(bm, (cx, cy + sy * 0.015, cz), (g_w, 0.005, g_h),
                        mat_idx=mat_guard, bevel=0.0015, segments=1)
            lp._add_hex_bolt(bm, (cx, cy + sy * 0.0175, cz), "Y",
                             head_r=0.0085, head_h=0.0060, washer_r=0.0125, washer_h=0.0026,
                             sign=sy, mat_idx=mat_steel)
        lp._add_cyl(bm, center, 0.0065, 0.032, axis="Y", segs=12, mat_idx=mat_steel)


def _add_split_head_hangers(bm, x_c, y_sheave, z_sheave, half_span_x, z_mount, mat_silver=0, mat_steel=1):
    """Build split left/right head-sheave support arms (completely clear of x=x_c vertical/exit cable!)."""
    # Left & right cheek hanger plates at x = x_c +/- 0.027 (width 0.008 -> [0.023, 0.031])
    # Arm embeds cleanly to |dx|=0.027 (4 mm clear of both inner & outer riser ear X faces -> zero z-fighting!)
    for sx in (-1.0, 1.0):
        arm_w = half_span_x - 0.027
        arm_cx = x_c + sx * (0.027 + arm_w * 0.5)
        lp._add_box(bm, (arm_cx, y_sheave, z_mount), (arm_w, 0.044, 0.028),
                    mat_idx=mat_silver, bevel=0.003, segments=1)
        # Vertical riser ear from mounting arm up to sheave axle height
        ear_h = max(0.055, (z_sheave + 0.024) - (z_mount - 0.010))
        ear_cz = (z_mount - 0.010) + ear_h * 0.5
        lp._add_box(bm, (x_c + sx * 0.027, y_sheave, ear_cz), (0.008, 0.054, ear_h),
                    mat_idx=mat_silver, bevel=0.0015, segments=1)
        # Prominent silver hex axle nut/washer on outer ear face
        lp._add_hex_bolt(bm, (x_c + sx * 0.031, y_sheave, z_sheave), "X",
                         head_r=0.0105, head_h=0.007, washer_r=0.0155, washer_h=0.0026,
                         sign=sx, mat_idx=mat_steel)


# ==============================================================================
# Per-machine dedicated material factory (zero edits to shared E_* materials)
# ==============================================================================

def _build_machine_materials(code):
    """Create dedicated Ddetail6_SM_<CODE>_* material set with realistic wear & crisp diagonal acrylic."""
    pfx = f"{PFX}{code}_"
    mats = {}

    def clone_base(src_name, dst_name):
        src = bpy.data.materials[src_name]
        m = src.copy()
        m.name = dst_name
        m[PROP_PKG] = PKG_KEY
        return m

    def add_macro_wear_paint(mat, base_rgb, worn_rgb, rough_lo, rough_hi, coat_w, coat_r_lo, coat_r_hi):
        nt = mat.node_tree
        bsdf = lp._find_node(nt, "BSDF_PRINCIPLED")
        tc = lp._find_node(nt, "TEX_COORD") or nt.nodes.new("ShaderNodeTexCoord")

        n_macro = nt.nodes.new("ShaderNodeTexNoise")
        n_macro.location = (-900, 260)
        n_macro.inputs["Scale"].default_value = 4.2
        n_macro.inputs["Detail"].default_value = 4.0
        n_macro.inputs["Roughness"].default_value = 0.58
        nt.links.new(tc.outputs["Object"], n_macro.inputs["Vector"])

        n_med = nt.nodes.new("ShaderNodeTexNoise")
        n_med.location = (-900, 40)
        n_med.inputs["Scale"].default_value = 15.0
        n_med.inputs["Detail"].default_value = 3.0
        n_med.inputs["Roughness"].default_value = 0.50
        nt.links.new(tc.outputs["Object"], n_med.inputs["Vector"])

        mix_w = nt.nodes.new("ShaderNodeMix")
        mix_w.data_type = "FLOAT"
        mix_w.location = (-650, 180)
        mix_w.inputs["Factor"].default_value = 0.35
        nt.links.new(n_macro.outputs["Fac"], mix_w.inputs["A"])
        nt.links.new(n_med.outputs["Fac"], mix_w.inputs["B"])

        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.samples = 8
        ao.only_local = True
        ao.location = (-650, 420)
        ao.inputs["Distance"].default_value = 0.09
        ao.inputs["Color"].default_value = (*base_rgb, 1.0)

        mr_ao = nt.nodes.new("ShaderNodeMapRange")
        mr_ao.clamp = True
        mr_ao.location = (-500, 380)
        mr_ao.inputs["From Min"].default_value = 0.35
        mr_ao.inputs["From Max"].default_value = 0.98
        nt.links.new(ao.outputs["AO"], mr_ao.inputs["Value"])

        mix_col = nt.nodes.new("ShaderNodeMix")
        mix_col.data_type = "RGBA"
        mix_col.location = (-360, 420)
        mix_col.inputs["A"].default_value = (base_rgb[0] * 0.72, base_rgb[1] * 0.72, base_rgb[2] * 0.72, 1.0)
        mix_col.inputs["B"].default_value = (*worn_rgb, 1.0)
        nt.links.new(mr_ao.outputs["Result"], mix_col.inputs["Factor"])
        nt.links.new(mix_col.outputs["Result"], bsdf.inputs["Base Color"])

        mr_r = nt.nodes.new("ShaderNodeMapRange")
        mr_r.clamp = True
        mr_r.location = (-440, 160)
        mr_r.inputs["From Min"].default_value = 0.25
        mr_r.inputs["From Max"].default_value = 0.75
        mr_r.inputs["To Min"].default_value = rough_lo
        mr_r.inputs["To Max"].default_value = rough_hi
        nt.links.new(mix_w.outputs["Result"], mr_r.inputs["Value"])

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

    # 1. Red powder coat
    m_frame = clone_base("E_frame", pfx + "Frame")
    add_macro_wear_paint(
        m_frame, (0.56, 0.004, 0.005), (0.60, 0.008, 0.009),
        0.22, 0.40, 0.26, 0.08, 0.20,
    )
    mats["frame"] = m_frame

    # 2. Dark satin powder coat
    m_silver = clone_base("E_silver", pfx + "Silver")
    add_macro_wear_paint(
        m_silver, (0.021, 0.022, 0.025), (0.028, 0.030, 0.034),
        0.21, 0.41, 0.38, 0.06, 0.18,
    )
    mats["silver"] = m_silver

    # 3. Black vinyl upholstery with contact polish
    m_pad = clone_base("E_pad", pfx + "Pad")
    nt = m_pad.node_tree
    bsdf = lp._find_node(nt, "BSDF_PRINCIPLED")
    tc = lp._find_node(nt, "TEX_COORD") or nt.nodes.new("ShaderNodeTexCoord")
    geom = nt.nodes.new("ShaderNodeNewGeometry")
    sep_n = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geom.outputs["Normal"], sep_n.inputs["Vector"])
    n_wear = nt.nodes.new("ShaderNodeTexNoise")
    n_wear.inputs["Scale"].default_value = 6.5
    n_wear.inputs["Detail"].default_value = 4.0
    n_wear.inputs["Roughness"].default_value = 0.6
    nt.links.new(tc.outputs["Object"], n_wear.inputs["Vector"])
    mr_pad = nt.nodes.new("ShaderNodeMapRange")
    mr_pad.clamp = True
    mr_pad.inputs["From Min"].default_value = 0.25
    mr_pad.inputs["From Max"].default_value = 0.78
    mr_pad.inputs["To Min"].default_value = 0.34
    mr_pad.inputs["To Max"].default_value = 0.62
    nt.links.new(n_wear.outputs["Fac"], mr_pad.inputs["Value"])
    mr_up = nt.nodes.new("ShaderNodeMapRange")
    mr_up.clamp = True
    mr_up.inputs["From Min"].default_value = 0.45
    mr_up.inputs["From Max"].default_value = 0.95
    mr_up.inputs["To Min"].default_value = 0.0
    mr_up.inputs["To Max"].default_value = -0.10
    nt.links.new(sep_n.outputs["Z"], mr_up.inputs["Value"])
    add_r = nt.nodes.new("ShaderNodeMath")
    add_r.operation = "ADD"
    add_r.use_clamp = True
    nt.links.new(mr_pad.outputs["Result"], add_r.inputs[0])
    nt.links.new(mr_up.outputs["Result"], add_r.inputs[1])
    nt.links.new(add_r.outputs["Value"], bsdf.inputs["Roughness"])
    bsdf.inputs["Coat Weight"].default_value = 0.08
    bsdf.inputs["Coat Roughness"].default_value = 0.26
    bsdf.inputs["Sheen Weight"].default_value = 0.06
    m_pad.diffuse_color = (0.020, 0.021, 0.024, 1.0)
    mats["pad"] = m_pad

    # 4. Cast-iron weight plates
    m_stack = clone_base("E_stack", pfx + "Stack")
    nt = m_stack.node_tree
    bsdf = lp._find_node(nt, "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n_cast = nt.nodes.new("ShaderNodeTexNoise")
    n_cast.inputs["Scale"].default_value = 520.0
    n_cast.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n_cast.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.065
    bump.inputs["Distance"].default_value = 0.0004
    nt.links.new(n_cast.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    n_sw = nt.nodes.new("ShaderNodeTexNoise")
    n_sw.inputs["Scale"].default_value = 9.0
    n_sw.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n_sw.inputs["Vector"])
    mr_sw = nt.nodes.new("ShaderNodeMapRange")
    mr_sw.clamp = True
    mr_sw.inputs["From Min"].default_value = 0.28
    mr_sw.inputs["From Max"].default_value = 0.72
    mr_sw.inputs["To Min"].default_value = 0.27
    mr_sw.inputs["To Max"].default_value = 0.44
    nt.links.new(n_sw.outputs["Fac"], mr_sw.inputs["Value"])
    nt.links.new(mr_sw.outputs["Result"], bsdf.inputs["Roughness"])
    ao_s = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao_s.samples = 8
    ao_s.only_local = True
    ao_s.inputs["Distance"].default_value = 0.05
    mix_sc = nt.nodes.new("ShaderNodeMix")
    mix_sc.data_type = "RGBA"
    mix_sc.inputs["A"].default_value = (0.014, 0.016, 0.019, 1.0)
    mix_sc.inputs["B"].default_value = (0.028, 0.031, 0.037, 1.0)
    nt.links.new(ao_s.outputs["AO"], mix_sc.inputs["Factor"])
    nt.links.new(mix_sc.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.62
    m_stack.diffuse_color = (0.025, 0.028, 0.033, 1.0)
    mats["stack"] = m_stack

    # 5. Polished chrome steel with vertical sliding micro-streaks
    m_steel = clone_base("E_steel", pfx + "Steel")
    nt = m_steel.node_tree
    bsdf = lp._find_node(nt, "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (18.0, 18.0, 2.2)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    n_ch = nt.nodes.new("ShaderNodeTexNoise")
    n_ch.inputs["Scale"].default_value = 8.0
    n_ch.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], n_ch.inputs["Vector"])
    mr_ch = nt.nodes.new("ShaderNodeMapRange")
    mr_ch.clamp = True
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
    m_grip = clone_base("E_grip", pfx + "Grip")
    nt = m_grip.node_tree
    bsdf = lp._find_node(nt, "BSDF_PRINCIPLED")
    tc = lp._find_node(nt, "TEX_COORD") or nt.nodes.new("ShaderNodeTexCoord")
    n_gr = nt.nodes.new("ShaderNodeTexNoise")
    n_gr.inputs["Scale"].default_value = 10.0
    n_gr.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n_gr.inputs["Vector"])
    mr_gr = nt.nodes.new("ShaderNodeMapRange")
    mr_gr.clamp = True
    mr_gr.inputs["From Min"].default_value = 0.25
    mr_gr.inputs["From Max"].default_value = 0.75
    mr_gr.inputs["To Min"].default_value = 0.56
    mr_gr.inputs["To Max"].default_value = 0.76
    nt.links.new(n_gr.outputs["Fac"], mr_gr.inputs["Value"])
    nt.links.new(mr_gr.outputs["Result"], bsdf.inputs["Roughness"])
    m_grip.diffuse_color = (0.015, 0.016, 0.019, 1.0)
    mats["grip"] = m_grip

    # 7. Yellow accent
    m_accent = clone_base("E_accent", pfx + "Accent")
    nt = m_accent.node_tree
    bsdf = lp._find_node(nt, "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n_ac = nt.nodes.new("ShaderNodeTexNoise")
    n_ac.inputs["Scale"].default_value = 12.0
    n_ac.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], n_ac.inputs["Vector"])
    mr_ac = nt.nodes.new("ShaderNodeMapRange")
    mr_ac.clamp = True
    mr_ac.inputs["From Min"].default_value = 0.25
    mr_ac.inputs["From Max"].default_value = 0.75
    mr_ac.inputs["To Min"].default_value = 0.22
    mr_ac.inputs["To Max"].default_value = 0.36
    nt.links.new(n_ac.outputs["Fac"], mr_ac.inputs["Value"])
    nt.links.new(mr_ac.outputs["Result"], bsdf.inputs["Roughness"])
    m_accent.diffuse_color = (0.95, 0.72, 0.04, 1.0)
    mats["accent"] = m_accent

    # 8. Translucent scratched/smudged front acrylic shield (EEVEE Fresnel BLENDED, crisp diagonal wipes)
    m_acr = bpy.data.materials.new(pfx + "Acrylic")
    m_acr[PROP_PKG] = PKG_KEY
    if m_acr.node_tree is None:
        m_acr.use_nodes = True
    m_acr.surface_render_method = "BLENDED"
    m_acr.use_backface_culling = True
    nt = m_acr.node_tree
    bsdf = lp._find_node(nt, "BSDF_PRINCIPLED")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["IOR"].default_value = 1.49
    bsdf.inputs["Specular IOR Level"].default_value = 0.74
    bsdf.inputs["Coat Weight"].default_value = 0.45
    bsdf.inputs["Coat Roughness"].default_value = 0.05

    tc = nt.nodes.new("ShaderNodeTexCoord")

    # Diagonal wipe-scratch layer A (+40 deg in XZ plane -> rotate around Y)
    mp_a = nt.nodes.new("ShaderNodeMapping")
    mp_a.inputs["Rotation"].default_value = (0.0, math.radians(40.0), 0.0)
    mp_a.inputs["Scale"].default_value = (2.8, 2.8, 64.0)
    nt.links.new(tc.outputs["Object"], mp_a.inputs["Vector"])
    n_sa = nt.nodes.new("ShaderNodeTexNoise")
    n_sa.inputs["Scale"].default_value = 2.8
    n_sa.inputs["Detail"].default_value = 6.0
    n_sa.inputs["Roughness"].default_value = 0.64
    nt.links.new(mp_a.outputs["Vector"], n_sa.inputs["Vector"])
    mr_sa = nt.nodes.new("ShaderNodeMapRange")
    mr_sa.clamp = True
    mr_sa.inputs["From Min"].default_value = 0.52
    mr_sa.inputs["From Max"].default_value = 0.76
    nt.links.new(n_sa.outputs["Fac"], mr_sa.inputs["Value"])

    # Diagonal wipe-scratch layer B (-32 deg)
    mp_b = nt.nodes.new("ShaderNodeMapping")
    mp_b.inputs["Rotation"].default_value = (0.0, math.radians(-32.0), 0.0)
    mp_b.inputs["Scale"].default_value = (2.4, 2.4, 54.0)
    nt.links.new(tc.outputs["Object"], mp_b.inputs["Vector"])
    n_sb = nt.nodes.new("ShaderNodeTexNoise")
    n_sb.inputs["Scale"].default_value = 2.4
    n_sb.inputs["Detail"].default_value = 5.0
    n_sb.inputs["Roughness"].default_value = 0.60
    nt.links.new(mp_b.outputs["Vector"], n_sb.inputs["Vector"])
    mr_sb = nt.nodes.new("ShaderNodeMapRange")
    mr_sb.clamp = True
    mr_sb.inputs["From Min"].default_value = 0.54
    mr_sb.inputs["From Max"].default_value = 0.78
    nt.links.new(n_sb.outputs["Fac"], mr_sb.inputs["Value"])

    # Cloudy smudges
    n_sm = nt.nodes.new("ShaderNodeTexNoise")
    n_sm.inputs["Scale"].default_value = 5.2
    n_sm.inputs["Detail"].default_value = 4.0
    n_sm.inputs["Roughness"].default_value = 0.65
    nt.links.new(tc.outputs["Object"], n_sm.inputs["Vector"])
    mr_sm = nt.nodes.new("ShaderNodeMapRange")
    mr_sm.clamp = True
    mr_sm.inputs["From Min"].default_value = 0.44
    mr_sm.inputs["From Max"].default_value = 0.76
    nt.links.new(n_sm.outputs["Fac"], mr_sm.inputs["Value"])

    max_sc = nt.nodes.new("ShaderNodeMath")
    max_sc.operation = "MAXIMUM"
    max_sc.use_clamp = True
    nt.links.new(mr_sa.outputs["Result"], max_sc.inputs[0])
    nt.links.new(mr_sb.outputs["Result"], max_sc.inputs[1])

    mix_hz = nt.nodes.new("ShaderNodeMix")
    mix_hz.data_type = "FLOAT"
    mix_hz.inputs["Factor"].default_value = 0.42
    nt.links.new(max_sc.outputs["Value"], mix_hz.inputs["A"])
    nt.links.new(mr_sm.outputs["Result"], mix_hz.inputs["B"])

    mix_ac = nt.nodes.new("ShaderNodeMix")
    mix_ac.data_type = "RGBA"
    mix_ac.inputs["A"].default_value = (0.76, 0.81, 0.87, 1.0)
    mix_ac.inputs["B"].default_value = (0.95, 0.96, 0.98, 1.0)
    nt.links.new(mix_hz.outputs["Result"], mix_ac.inputs["Factor"])
    nt.links.new(mix_ac.outputs["Result"], bsdf.inputs["Base Color"])

    mr_ar = nt.nodes.new("ShaderNodeMapRange")
    mr_ar.clamp = True
    mr_ar.inputs["To Min"].default_value = 0.055
    mr_ar.inputs["To Max"].default_value = 0.44
    nt.links.new(mix_hz.outputs["Result"], mr_ar.inputs["Value"])
    nt.links.new(mr_ar.outputs["Result"], bsdf.inputs["Roughness"])

    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.25
    mr_fr = nt.nodes.new("ShaderNodeMapRange")
    mr_fr.clamp = True
    mr_fr.inputs["To Min"].default_value = 0.14
    mr_fr.inputs["To Max"].default_value = 0.44
    nt.links.new(lw.outputs["Facing"], mr_fr.inputs["Value"])

    alpha_add = nt.nodes.new("ShaderNodeMath")
    alpha_add.operation = "MULTIPLY_ADD"
    alpha_add.use_clamp = True
    alpha_add.inputs[1].default_value = 0.19
    nt.links.new(mix_hz.outputs["Result"], alpha_add.inputs[0])
    nt.links.new(mr_fr.outputs["Result"], alpha_add.inputs[2])

    alpha_cap = nt.nodes.new("ShaderNodeMath")
    alpha_cap.operation = "MINIMUM"
    alpha_cap.inputs[1].default_value = 0.56
    nt.links.new(alpha_add.outputs["Value"], alpha_cap.inputs[0])
    nt.links.new(alpha_cap.outputs["Value"], bsdf.inputs["Alpha"])

    bmp_a = nt.nodes.new("ShaderNodeBump")
    bmp_a.inputs["Strength"].default_value = 0.075
    bmp_a.inputs["Distance"].default_value = 0.0003
    nt.links.new(max_sc.outputs["Value"], bmp_a.inputs["Height"])
    nt.links.new(bmp_a.outputs["Normal"], bsdf.inputs["Normal"])

    m_acr.diffuse_color = (0.78, 0.84, 0.90, 0.28)
    mats["acrylic"] = m_acr

    m_smoke = m_acr.copy()
    m_smoke.name = pfx + "AcrylicSmoke"
    m_smoke[PROP_PKG] = PKG_KEY
    for n in m_smoke.node_tree.nodes:
        if n.type == "MIX" and n.data_type == "RGBA":
            n.inputs["A"].default_value = (0.12, 0.13, 0.16, 1.0)
            n.inputs["B"].default_value = (0.24, 0.26, 0.30, 1.0)
    m_smoke.diffuse_color = (0.16, 0.18, 0.22, 0.35)
    mats["acrylic_smoke"] = m_smoke
    return mats


def _rebind_machine_materials(root, code, mats):
    """Rebind all kept children of root from E_* to Ddetail6_SM_<CODE>_* safely (cloning external data)."""
    src_to_dst = {
        "E_frame": mats["frame"],
        "E_silver": mats["silver"],
        "E_pad": mats["pad"],
        "E_stack": mats["stack"],
        "E_steel": mats["steel"],
        "E_grip": mats["grip"],
        "E_accent": mats["accent"],
    }
    m_objs = set(lp._descendants(root)) | {root}
    ext_meshes = {o.data for o in bpy.data.objects if o not in m_objs and o.type == "MESH" and o.data}
    ext_curves = {o.data for o in bpy.data.objects if o not in m_objs and o.type == "CURVE" and o.data}

    cloned = {}
    rebound = 0
    for ob in lp._descendants(root):
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
        is_ext = (ob.type == "MESH" and data in ext_meshes) or (ob.type == "CURVE" and data in ext_curves)
        if is_ext:
            if data not in cloned:
                nd = data.copy()
                nd.name = f"{PFX}{code}_{data.name}"
                cloned[data] = nd
            ob.data = cloned[data]

        for idx, orig_name in enumerate(orig_names):
            if idx < len(ob.data.materials):
                if orig_name in src_to_dst:
                    ob.data.materials[idx] = src_to_dst[orig_name]
                elif orig_name is not None and orig_name in bpy.data.materials:
                    ob.data.materials[idx] = bpy.data.materials[orig_name]
        rebound += 1
    return rebound


# ==============================================================================
# 1. P_cable_crossover (Dual full-height towers, open pulley slots, grounded base)
# ==============================================================================

def _upgrade_cable_crossover(root, coll, mats):
    code = "CC"
    pfx = f"{PFX}{code}_"
    root_set = set(lp._descendants(root)) | {root}
    floor_z = -root.location.z  # 0.0
    created = []
    touched = []

    # 1a. Extend all 4 chrome guide rods to full height (z = 0.100 .. 2.130)
    for nm in ("guide_rod.004", "guide_rod.005", "guide_rod.006", "guide_rod.007"):
        ob = bpy.data.objects.get(nm)
        if ob:
            _rescale_mesh_z_bounds(ob, 0.100, 2.130, root_set)
            touched.append(nm)

    # 1b. Shorten trolley guide rods top slightly from 2.24 -> 2.192 (clears horizontal cable at z=2.222 by 25 mm!)
    for nm in ("guide", "guide.001"):
        ob = bpy.data.objects.get(nm)
        if ob:
            _rescale_mesh_z_bounds(ob, 0.220, 2.192, root_set)
            touched.append(nm)

    # 1c. Trim Perforated uprights top above z=2.185 so open 64 mm center cable tunnel clears horizontal cable at z=2.222
    for nm in ("Perforated upright.004", "Perforated upright.005"):
        ob = bpy.data.objects.get(nm)
        if ob:
            _clamp_mesh_top_z(ob, 2.185, root_set)
            touched.append(nm)

    # 1d. Raise both Head sheaves up to z = 2.164 (top tangent = 2.164 + 0.058 = 2.222 exact match to Trolley head pulley!)
    for nm, cx in (("P_Head sheave.002", -1.05), ("P_Head sheave.003", 1.05)):
        ob = bpy.data.objects.get(nm)
        if ob:
            _tag_and_restore_xform(ob)
            ob.location = Vector((cx, 0.522, 2.164))
            touched.append(nm)

    # 1e. Reroute both Coated load cables (vertical stack -> 90 deg around raised sheave -> dead horizontal at z=2.222)
    for nm, cx in (("Coated load cable.002", -1.05), ("Coated load cable.003", 1.05)):
        ob = bpy.data.objects.get(nm)
        if ob:
            _tag_and_restore_xform(ob)
            sp = ob.data.splines[0]
            if PROP_ORIG_SPLINE not in ob:
                ob[PROP_ORIG_SPLINE] = json.dumps([[float(c) for c in pt.co] for pt in sp.points])
            pts = [(cx, 0.580, 0.9433)]
            for i in range(17):
                t = (math.pi * 0.5) * i / 16.0
                pts.append((cx, 0.522 + 0.058 * math.cos(t), 2.164 + 0.058 * math.sin(t)))
            pts.append((cx, -0.134, 2.222))
            for pt, xyz in zip(sp.points, pts):
                pt.co = (*xyz, 1.0)
            ob.data.bevel_depth = 0.0045
            touched.append(nm)

    # 1f. Move front Exercise guides intact (text untouched!) onto unobstructed upper tower headers (z=1.998)
    for nm, cx in (("Exercise guide.005", -1.05), ("Exercise guide.007", 1.05)):
        ob = bpy.data.objects.get(nm)
        if ob:
            _tag_and_restore_xform(ob)
            ob.location = Vector((cx, 0.402, 1.998))
            ob.rotation_euler = Euler((math.radians(86.0), 0.0, 0.0), "XYZ")
            touched.append(nm)

    # 1g. Build twin full-height portal tower frames + upper tie-beams + slotted upright caps + pulley guards
    bm_fr = bmesh.new()   # mat 0=silver, 1=frame(red), 2=steel, 3=grip
    bm_ch = bmesh.new()   # chrome accent tubes + guide rod caps
    bm_acr = bmesh.new()
    bm_smk = bmesh.new()
    bm_clp = bmesh.new()

    for side, cx in ((-1.0, -1.05), (1.0, 1.05)):
        # Twin vertical portal uprights flanking each stack: x = cx +/- [0.168, 0.212] (44 x 92 mm), z = [0.112, 2.276]
        for sx in (-1.0, 1.0):
            ux = cx + sx * 0.190
            lp._add_box(bm_fr, (ux, 0.456, 1.194), (0.044, 0.092, 2.164), mat_idx=0, bevel=0.004, segments=2)
            # Base collar flange stepped 3 mm above upright bottom
            lp._add_box(bm_fr, (ux, 0.456, 0.124), (0.052, 0.100, 0.018), mat_idx=0, bevel=0.002, segments=1)
            # Horizontal side tie-bars bridging front upright to full-height chrome tube (y=0.545)
            for tz in (0.700, 1.310, 2.220):
                lp._add_box(bm_fr, (ux, 0.514, tz), (0.036, 0.068, 0.040), mat_idx=0, bevel=0.0025, segments=1)
            # Split guide-rod top retaining bracket (x = cx +/- [0.074, 0.172], z = [2.112, 2.140], clear of x=cx cable!)
            lp._add_box(bm_fr, (cx + sx * 0.123, 0.580, 2.126), (0.098, 0.046, 0.028), mat_idx=0, bevel=0.0025, segments=1)
            lp._add_box(bm_fr, (cx + sx * 0.184, 0.562, 2.126), (0.032, 0.050, 0.020), mat_idx=0, bevel=0.002, segments=1)
            # Full-height chrome side tube (z=[0.116, 2.232] -> 8 mm stepped inside top tie-bar z=2.240, zero z-fighting!)
            lp._add_cyl(bm_ch, (cx + sx * 0.194, 0.545, 1.174), 0.017, 2.116, axis="Z", segs=20, mat_idx=0, bevel=0.002)
            lp._add_cyl(bm_ch, (cx + sx * 0.104, 0.580, 2.144), 0.015, 0.014, axis="Z", segs=16, mat_idx=0, bevel=0.001)
            lp._add_cyl(bm_ch, (cx + sx * 0.104, 0.580, 2.154), 0.010, 0.014, axis="Z", segs=6, mat_idx=0, bevel=0.0008)

        # Top portal crossbar (z = [2.238, 2.272] -> 12 mm ABOVE horizontal cable z=2.222, stepped vs upright top 2.276!)
        lp._add_box(bm_fr, (cx, 0.456, 2.255), (0.344, 0.084, 0.034), mat_idx=0, bevel=0.003, segments=1)
        # Rear top crossbeam behind head sheave (z = [2.238, 2.272], y = 0.574)
        lp._add_box(bm_fr, (cx, 0.574, 2.255), (0.396, 0.048, 0.034), mat_idx=0, bevel=0.003, segments=1)
        # Upper front header fascia panel (holds Exercise guide at z=1.998; top z=2.084 is 134 mm clear below cable!)
        lp._add_box(bm_fr, (cx, 0.428, 1.998), (0.342, 0.034, 0.172), mat_idx=0, bevel=0.0035, segments=2)

        # Twin upper overhead tie-rails linking tower top forward to Perforated upright top (x = cx +/- 0.054 -> 108 mm open cable channel!)
        for sx in (-1.0, 1.0):
            lp._add_box(bm_fr, (cx + sx * 0.054, 0.240, 2.258), (0.034, 0.480, 0.046), mat_idx=0, bevel=0.003, segments=1)
            # Rear head sheave hanger ear from overhead tie-rail down to sheave axle (z=2.164, x = cx +/- 0.025)
            lp._add_box(bm_fr, (cx + sx * 0.025, 0.522, 2.200), (0.008, 0.056, 0.112), mat_idx=0, bevel=0.0015, segments=1)
            lp._add_hex_bolt(bm_fr, (cx + sx * 0.029, 0.522, 2.164), "X",
                             head_r=0.010, head_h=0.0065, washer_r=0.0145, washer_h=0.0026, sign=sx, mat_idx=2)
            # Mid horizontal tie-strut linking tower upright forward to Perforated upright at z=1.794 (completely clear of stack front!)
            lp._add_box(bm_fr, (cx + sx * 0.054, 0.220, 1.794), (0.036, 0.360, 0.056), mat_idx=0, bevel=0.0035, segments=1)
            lp._add_hex_bolt(bm_fr, (cx + sx * 0.072, 0.365, 1.794), "X",
                             head_r=0.0075, head_h=0.0055, washer_r=0.011, washer_h=0.0026, sign=sx, mat_idx=2)
            # Slotted red portal cheek plates bridging Perforated upright top (z=2.185) up into top beam (z=2.223..2.377)
            # Leaves a 64 mm open center tunnel (x = cx +/- 0.032) for horizontal cable at z=2.222!
            lp._add_box(bm_fr, (cx + sx * 0.054, 0.000, 2.214), (0.044, 0.164, 0.068), mat_idx=1, bevel=0.003, segments=1)
            lp._add_hex_bolt(bm_fr, (cx + sx * 0.076, 0.000, 2.220), "X",
                             head_r=0.0085, head_h=0.006, washer_r=0.0125, washer_h=0.0026, sign=sx, mat_idx=2)

        # Solid connected L-bracket holding outer Storage pin cleanly at y=0.30, z=0.62 back into tower upright (y=0.456)
        # Stepped heights (0.090 / 0.040 / 0.048) guarantee >= 4 mm face offsets -> zero coplanar z-fighting!
        lp._add_box(bm_fr, (cx + side * 0.095, 0.300, 0.620), (0.044, 0.044, 0.090), mat_idx=0, bevel=0.003, segments=1)
        lp._add_box(bm_fr, (cx + side * 0.145, 0.300, 0.620), (0.114, 0.032, 0.040), mat_idx=0, bevel=0.0025, segments=1)
        lp._add_box(bm_fr, (cx + side * 0.186, 0.380, 0.620), (0.030, 0.172, 0.048), mat_idx=0, bevel=0.0025, segments=1)

        # Bolted U-cheek guards + large silver hex axle bolts on Trolley head pulley ((cx, -0.134, 2.18))
        for sx in (-1.0, 1.0):
            lp._add_box(bm_fr, (cx + sx * 0.018, -0.134, 2.180), (0.006, 0.078, 0.088), mat_idx=0, bevel=0.0015, segments=1)
            lp._add_hex_bolt(bm_fr, (cx + sx * 0.021, -0.134, 2.180), "X",
                             head_r=0.011, head_h=0.0075, washer_r=0.016, washer_h=0.0026, sign=sx, mat_idx=2)

        # Grounded red base runner replacing sunk foot.001/.002 (-28.3 mm!) -> z = [0.014, 0.094], rubber pads & L-anchors at z=0.000!
        lp._add_box(bm_fr, (cx, 0.058, 0.054), (0.104, 0.724, 0.080), mat_idx=1, bevel=0.005, segments=2)
        lp._add_tube_cap(bm_fr, (cx, -0.304, 0.054), "Y", -1.0, 0.104, 0.080, depth=0.011, mat_idx=3)
        # Molded rubber isolation pads under base runner (z = [0.000, 0.018])
        for py in (-0.230, 0.240):
            lp._add_box(bm_fr, (cx, py, 0.009), (0.096, 0.120, 0.018), mat_idx=3, bevel=0.002, segments=1)
        # Welded L-shaped anchor flanges (front outer + tower outer, flush at z=0.0000!)
        _add_anchor_flange(bm_fr, cx + side * 0.052, side, -0.230, floor_z, 0.068, 1, 2)
        _add_anchor_flange(bm_fr, cx + side * 0.222, side,  0.490, floor_z, 0.084, 1, 2)

        # Acrylic front shield (2-piece, 72 mm center pin slot) + 6 L-clips + rear upper smoked acrylic + 4 rear clips
        _add_acrylic_stack_front(
            bm_acr, bm_clp, cx=cx, y_acr=0.424, z_bot=0.124, z_top=1.908,
            half_w=0.166, clip_zs=(0.220, 1.010, 1.805), slot_half=0.036, upright_attach_x=0.168,
        )
        lp._add_box(bm_smk, (cx, 0.600, 1.624), (0.330, 0.004, 0.568), mat_idx=0, bevel=0.0012, segments=1)
        for sx in (-1.0, 1.0):
            for rz in (1.420, 1.830):
                lp._add_box(bm_clp, (cx + sx * 0.174, 0.576, rz), (0.034, 0.042, 0.026), mat_idx=0, bevel=0.0014, segments=1)
                lp._add_cyl(bm_clp, (cx + sx * 0.156, 0.598, rz), 0.0042, 0.014, axis="Y", segs=10, mat_idx=1)
                lp._add_hex_bolt(bm_clp, (cx + sx * 0.156, 0.605, rz), "Y",
                                 head_r=0.006, head_h=0.005, washer_r=0.009, washer_h=0.0024, sign=1.0, mat_idx=1)

    created.append(_finalize_sm_mesh(
        pfx + "Frame", bm_fr, [mats["silver"], mats["frame"], mats["steel"], mats["grip"]], root, coll, 35.0
    ))
    created.append(_finalize_sm_mesh(pfx + "ChromeTubes", bm_ch, [mats["steel"]], root, coll, 42.0))
    created.append(_finalize_sm_mesh(pfx + "AcrylicFront", bm_acr, [mats["acrylic"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "AcrylicRearUpper", bm_smk, [mats["acrylic_smoke"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "ShieldClips", bm_clp, [mats["grip"], mats["steel"]], root, coll, 35.0))
    return created, touched


# ==============================================================================
# 2. P_seated_cable_row (Zero-penetration external side low-cable + grounded chassis)
# ==============================================================================

def _upgrade_seated_cable_row(root, coll, mats):
    code = "SCR"
    pfx = f"{PFX}{code}_"
    root_set = set(lp._descendants(root)) | {root}
    floor_z = -root.location.z  # -0.0120 (world z=0)
    created = []
    touched = []

    # 2a. Extend 4 tower_foot cylinders down to floor_z = -0.0120 (world z = 0.0000!)
    touched.extend(_extend_tower_feet_to_floor(
        root, ("tower_foot.036", "tower_foot.037", "tower_foot.038", "tower_foot.039"), floor_z, root_set
    ))

    # 2b. Raise Head sheave slightly (+0.015 m to z=1.500) so exit cable clears cover.009 (z_max=1.415) cleanly
    sheave = bpy.data.objects.get("P_Head sheave.009")
    if sheave:
        _tag_and_restore_xform(sheave)
        sheave.location = Vector((0.0, 0.892, 1.500))
        touched.append(sheave.name)

    # 2c. Reroute Coated load cable.009 with 0 structural penetrations & 100% unobstructed front acrylic/placard:
    #     stack (0, 0.95, 0.9733+0.28*v) -> Head sheave (0, 0.892, 1.500) -> outer-right upper pulley (0.258, 0.775, 1.485)
    #     -> dead vertical outside right shroud to (0.258, 0.775, 0.145) -> low run beside base spine to (0.145, -0.455, 0.145)
    #     -> vertical rise behind foot_plate to (0.145, -0.455, 0.385) -> horizontal above foot_plate to front exit (0.0, -0.555, 0.385)!
    lc = bpy.data.objects.get("Coated load cable.009")
    if lc:
        _tag_and_restore_xform(lc)
        sp = lc.data.splines[0]
        if PROP_ORIG_SPLINE not in lc:
            lc[PROP_ORIG_SPLINE] = json.dumps([[float(c) for c in pt.co] for pt in sp.points])
        pts = [(0.0, 0.950, 0.9733)]
        for i in range(15):
            t = (math.pi * 0.56) * i / 14.0
            pts.append((0.0, 0.892 + 0.058 * math.cos(t), 1.500 + 0.058 * math.sin(t)))
        pts.extend([
            (0.258,  0.775, 1.485),  # outer-right upper redirection pulley (35 mm clear outside right shroud!)
            (0.258,  0.775, 0.145),  # outer-right lower pulley
            (0.145, -0.455, 0.145),  # lower-right front pulley (83 mm clear of seat_post & chest_post!)
            (0.145, -0.455, 0.385),  # upper-right front pulley (31 mm behind foot_plate, 83 mm above foot_plate!)
            (0.000, -0.555, 0.385),  # front center exit pulley cleanly above foot_plate & in front of chest_post!
        ])
        assert len(pts) == len(sp.points), f"SCR cable expected {len(sp.points)}, got {len(pts)}"
        for pt, xyz in zip(sp.points, pts):
            pt.co = (*xyz, 1.0)
        lc.data.bevel_depth = 0.0045
        touched.append(lc.name)

    # 2d. Update Row cable start point to match front exit pulley (0.0, -0.555, 0.385) (preserve points[1].co.y driver!)
    rc = bpy.data.objects.get("Row cable")
    if rc:
        _tag_and_restore_xform(rc)
        sp = rc.data.splines[0]
        if PROP_ORIG_SPLINE not in rc:
            rc[PROP_ORIG_SPLINE] = json.dumps([[float(c) for c in pt.co] for pt in sp.points])
        sp.points[0].co = (0.0, -0.555, 0.385, 1.0)
        rc.data.bevel_depth = 0.0045
        touched.append(rc.name)

    # 2e. Build grounded chassis, anchor flanges, tube end-caps, split head hangers, 5 guarded pulleys, fasteners
    bm_fr = bmesh.new()   # mat 0=silver, 1=steel, 2=grip, 3=frame
    bm_pl = bmesh.new()   # guarded sheaves separated from structural frame -> clean cable-vs-frame checks
    # Grounded dark-satin base spine (84 x 82 mm, z_local = [0.002, 0.084], y = [-0.650, +0.780])
    lp._add_box(bm_fr, (0.0, 0.065, 0.043), (0.084, 1.430, 0.082), mat_idx=0, bevel=0.005, segments=2)
    lp._add_tube_cap(bm_fr, (0.0, -0.650, 0.043), "Y", -1.0, 0.084, 0.082, depth=0.010, mat_idx=2)
    # Rubber floor pads flush at floor_z = -0.0120 (embedded 4 mm into base spine underside z=0.002)
    for py in (-0.580, 0.050, 0.620):
        lp._add_box(bm_fr, (0.0, py, floor_z + 0.009), (0.094, 0.130, 0.018), mat_idx=2, bevel=0.002, segments=1)
    # 4 welded L-shaped floor anchor flanges (2 at front base sides, 2 flanking tower housing.009, flush at floor_z!)
    for sx in (-1.0, 1.0):
        _add_anchor_flange(bm_fr, sx * 0.042, sx, -0.580, floor_z, 0.066, 0, 1)
        _add_anchor_flange(bm_fr, sx * 0.240, sx,  0.860, floor_z, 0.098, 0, 1)

    # Split head-sheave hanger brackets flanking P_Head sheave.009 (z=1.500, clear of vertical cable!)
    _add_split_head_hangers(bm_fr, 0.0, 0.892, 1.500, 0.210, 1.415, mat_silver=0, mat_steel=1)

    # 5 guarded sheaves along the outer-right channel + front exit (brackets stay >= 15 mm clear of cable lines!)
    # 1) Upper-right redirection pulley outside Side shroud.038 (bracket z_top=1.416 -> 8 mm stepped below shroud top 1.424!)
    lp._add_box(bm_fr, (0.232, 0.810, 1.404), (0.056, 0.042, 0.024), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.812, 1.444), (0.026, 0.028, 0.072), mat_idx=0, bevel=0.002, segments=1)
    _add_guarded_sheave(bm_pl, (0.258, 0.775, 1.460), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)
    # 2) Outer-right lower pulley mounted to tower base side (bracket below cable z<=0.105!)
    lp._add_box(bm_fr, (0.140, 0.775, 0.064), (0.245, 0.040, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.775, 0.102), (0.028, 0.036, 0.056), mat_idx=0, bevel=0.002, segments=1)
    _add_guarded_sheave(bm_pl, (0.258, 0.775, 0.145), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)
    # 3 & 4) Front-right vertical guide column at (0.114, -0.455) holding lower & upper front pulleys (15 mm clear inside cable x=0.145!)
    lp._add_box(bm_fr, (0.074, -0.455, 0.064), (0.112, 0.038, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.114, -0.455, 0.212), (0.028, 0.030, 0.300), mat_idx=0, bevel=0.0025, segments=1)
    _add_guarded_sheave(bm_pl, (0.145, -0.455, 0.145), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)
    _add_guarded_sheave(bm_pl, (0.145, -0.455, 0.385), radius=0.028, axis="Y", mat_guard=0, mat_wheel=2, mat_steel=1)
    # 5) Front center exit pulley pedestal rising from base spine (x=0, y=-0.555, below z=0.352 -> clear of cable!)
    lp._add_box(bm_fr, (0.0, -0.555, 0.206), (0.038, 0.038, 0.285), mat_idx=0, bevel=0.0025, segments=1)
    _add_guarded_sheave(bm_pl, (0.0, -0.555, 0.385), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # Seat & chest post mounting plate bolts
    for sx in (-1.0, 1.0):
        lp._add_hex_bolt(bm_fr, (sx * 0.062, 0.050, 0.350), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)
        lp._add_hex_bolt(bm_fr, (sx * 0.062, -0.360, 0.560), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)

    # Stopper ball + steel ferrule parented to P_row_handle (moves with Stroke!)
    rh = bpy.data.objects.get("P_row_handle")
    if rh:
        bm_rh = bmesh.new()
        lp._add_cyl(bm_rh, (0.0, -0.185, 0.040), 0.011, 0.028, axis="Y", segs=16, mat_idx=0, bevel=0.0015)
        sb_prof = [(0.008, -0.016), (0.015, -0.013), (0.018, 0.0), (0.015, 0.013), (0.008, 0.016)]
        lp._add_revolved(bm_rh, sb_prof, (0.0, -0.205, 0.040), axis="Y", segs=20, mat_idx=1, cap_ends=True)
        created.append(_finalize_sm_mesh(pfx + "HandleHardware", bm_rh, [mats["steel"], mats["grip"]], rh, coll, 42.0))

    # Acrylic front shields (replacing hfront_wing.018/.019, z = [0.138, 1.224]) + 6 L-clips
    bm_acr = bmesh.new()
    bm_clp = bmesh.new()
    _add_acrylic_stack_front(
        bm_acr, bm_clp, cx=0.0, y_acr=0.770, z_bot=0.138, z_top=1.224,
        half_w=0.194, clip_zs=(0.230, 0.680, 1.135), slot_half=0.036, upright_attach_x=0.205,
    )

    created.append(_finalize_sm_mesh(
        pfx + "Frame", bm_fr, [mats["silver"], mats["steel"], mats["grip"], mats["frame"]], root, coll, 35.0
    ))
    created.append(_finalize_sm_mesh(
        pfx + "Pulleys", bm_pl, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 38.0
    ))
    created.append(_finalize_sm_mesh(pfx + "AcrylicFront", bm_acr, [mats["acrylic"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "ShieldClips", bm_clp, [mats["grip"], mats["steel"]], root, coll, 35.0))
    return created, touched


# ==============================================================================
# 3. P_chest_press_machine (Grounded footbars/tower, zero-penetration head exit, acrylic)
# ==============================================================================

def _upgrade_chest_press(root, coll, mats):
    code = "CP"
    pfx = f"{PFX}{code}_"
    root_set = set(lp._descendants(root)) | {root}
    floor_z = -root.location.z  # -0.0042 (world z=0)
    created = []
    touched = []

    # 3a. Extend 4 tower_foot cylinders down to floor_z = -0.0042 (world z = 0.0000!)
    touched.extend(_extend_tower_feet_to_floor(
        root, ("tower_foot.020", "tower_foot.021", "tower_foot.022", "tower_foot.023"), floor_z, root_set
    ))

    # 3b. Raise P_Head sheave.005 by +0.035 m (z = 1.610) so Coated load cable.005 clears cover.005 (z_max=1.504) by 26 mm!
    sheave = bpy.data.objects.get("P_Head sheave.005")
    if sheave:
        _tag_and_restore_xform(sheave)
        sheave.location.z = 1.610
        touched.append(sheave.name)

    lc = bpy.data.objects.get("Coated load cable.005")
    if lc:
        _tag_and_restore_xform(lc)
        sp = lc.data.splines[0]
        if PROP_ORIG_SPLINE not in lc:
            lc[PROP_ORIG_SPLINE] = json.dumps([[float(c) for c in pt.co] for pt in sp.points])
        orig_pts = json.loads(lc[PROP_ORIG_SPLINE])
        for idx, (pt, co) in enumerate(zip(sp.points, orig_pts)):
            if 1 <= idx <= 17:
                pt.co = (co[0], co[1], co[2] + 0.035, 1.0)
            else:
                pt.co = tuple(co)
        lc.data.bevel_depth = 0.0045
        touched.append(lc.name)

    # 3c. Grounded base spine, footbar rubber pads, 4 L-anchor flanges, 6 tube end-caps, split head hangers, cam guard
    bm_fr = bmesh.new()   # mat 0=silver, 1=steel, 2=grip
    # Grounded dark-satin base spine replacing base.004 (86 x 84 mm, z_local = [0.008, 0.092], y = [-0.850, +0.660])
    lp._add_box(bm_fr, (0.0, -0.095, 0.050), (0.086, 1.510, 0.084), mat_idx=0, bevel=0.005, segments=2)
    lp._add_tube_cap(bm_fr, (0.0, -0.850, 0.050), "Y", -1.0, 0.086, 0.084, depth=0.010, mat_idx=2)
    # Rubber pads under base spine & under floating footbar / footbar.001 (z_local = [-0.0042, +0.011])
    for py in (-0.770, 0.050, 0.520):
        lp._add_box(bm_fr, (0.0, py, floor_z + 0.008), (0.094, 0.120, 0.016), mat_idx=2, bevel=0.002, segments=1)
    for sx in (-1.0, 1.0):
        fx = sx * 0.400
        # Rubber pads under footbar front & rear ends (embedded 4 mm into footbar z_min=+0.0035!)
        for py in (-0.760, 0.310):
            lp._add_box(bm_fr, (fx, py, floor_z + 0.007), (0.084, 0.130, 0.014), mat_idx=2, bevel=0.002, segments=1)
        # Black plastic tube end-caps on front (-0.850) & rear (+0.400) open ends of footbar
        lp._add_tube_cap(bm_fr, (fx, -0.850, 0.050), "Y", -1.0, 0.093, 0.093, depth=0.010, mat_idx=2)
        lp._add_tube_cap(bm_fr, (fx,  0.400, 0.050), "Y",  1.0, 0.093, 0.093, depth=0.010, mat_idx=2)
        # 4 welded L-anchor flanges (2 on outer footbars, 2 flanking tower housing.005, flush at floor_z!)
        _add_anchor_flange(bm_fr, sx * 0.446, sx, -0.740, floor_z, 0.072, 0, 1)
        _add_anchor_flange(bm_fr, sx * 0.250, sx,  0.740, floor_z, 0.092, 0, 1)

    # Split head-sheave hanger brackets flanking angled P_Head sheave.005 (x_c=0.0266, y=0.7685, z=1.610)
    # Arms embed cleanly into both riser centers (-0.032 & +0.086) -> solid bridged assembly, zero gap, zero z-fighting!
    for sx in (-1.0, 1.0):
        bx_in = 0.086 if sx > 0 else -0.032
        bx_out = sx * 0.215
        arm_w = abs(bx_out - bx_in)
        lp._add_box(bm_fr, (0.5 * (bx_in + bx_out), 0.768, 1.500), (arm_w, 0.044, 0.028), mat_idx=0, bevel=0.003, segments=1)
    # Pedestal risers flanking sheave (axle rod protrudes 6 mm past outer riser faces -> zero coplanar z-fighting!)
    lp._add_box(bm_fr, (-0.032, 0.768, 1.555), (0.014, 0.048, 0.118), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, ( 0.086, 0.768, 1.555), (0.014, 0.048, 0.118), mat_idx=0, bevel=0.002, segments=1)
    lp._add_cyl(bm_fr, (0.027, 0.768, 1.610), 0.010, 0.144, axis="X", segs=12, mat_idx=1)

    # Protective rear-bottom sheet-metal guard cheek on drive_cam.001 + pivot bridge bolts
    lp._add_box(bm_fr, (0.352, 0.200, 0.915), (0.006, 0.120, 0.110), mat_idx=0, bevel=0.0015, segments=1)
    for sx in (-1.0, 1.0):
        lp._add_hex_bolt(bm_fr, (sx * 0.340, 0.161, 0.560), "Y",
                         head_r=0.008, head_h=0.0055, washer_r=0.012, washer_h=0.0026, sign=-1.0, mat_idx=1)
        lp._add_hex_bolt(bm_fr, (sx * 0.054, -0.050, 0.140), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)

    # Acrylic front shields (replacing hfront_wing.010/.011, y=0.630, z=[0.130, 1.298]) + 6 L-clips
    bm_acr = bmesh.new()
    bm_clp = bmesh.new()
    _add_acrylic_stack_front(
        bm_acr, bm_clp, cx=0.0, y_acr=0.630, z_bot=0.130, z_top=1.298,
        half_w=0.204, clip_zs=(0.225, 0.710, 1.205), slot_half=0.036, upright_attach_x=0.215,
    )

    created.append(_finalize_sm_mesh(pfx + "Frame", bm_fr, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "AcrylicFront", bm_acr, [mats["acrylic"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "ShieldClips", bm_clp, [mats["grip"], mats["steel"]], root, coll, 35.0))
    return created, touched


# ==============================================================================
# 4. P_pec_deck (Lowered header fascia clear of fly_cable, grounded base, acrylic)
# ==============================================================================

def _upgrade_pec_deck(root, coll, mats):
    code = "PD"
    pfx = f"{PFX}{code}_"
    floor_z = -root.location.z  # 0.0
    created = []
    touched = []

    # Note: seat top z=0.495 stays 100% untouched for Dgym_life_Phone_on_pecdeck (z=0.497)!
    # Coated load cable already runs cleanly once Head bearing mount & cover (z_max=1.515) are replaced
    # by our split hangers + lowered header fascia (z_max=1.462 -> 33 mm clear below fly_cable z=1.500!).

    bm_fr = bmesh.new()   # mat 0=silver, 1=steel, 2=grip
    # Grounded dark-satin base spine replacing sunk base.002 (-4.2 mm!) -> z=[0.012, 0.096], y=[-0.450, +0.620]
    lp._add_box(bm_fr, (0.0, 0.085, 0.054), (0.086, 1.070, 0.084), mat_idx=0, bevel=0.005, segments=2)
    lp._add_tube_cap(bm_fr, (0.0, -0.450, 0.054), "Y", -1.0, 0.086, 0.084, depth=0.010, mat_idx=2)
    # Rubber pads flush at z=0.000
    for py in (-0.370, 0.050, 0.480):
        lp._add_box(bm_fr, (0.0, py, floor_z + 0.008), (0.094, 0.120, 0.016), mat_idx=2, bevel=0.002, segments=1)
    # 4 welded L-anchor flanges (2 at front base sides, 2 flanking tower housing, flush at z=0.000!)
    for sx in (-1.0, 1.0):
        _add_anchor_flange(bm_fr, sx * 0.043, sx, -0.370, floor_z, 0.068, 0, 1)
        _add_anchor_flange(bm_fr, sx * 0.258, sx,  0.700, floor_z, 0.096, 0, 1)

    # Lowered front header fascia (z=[1.304, 1.462], y=[0.574, 0.606]) -> holds Exercise guide.001 (z=1.375)
    # while leaving 33 mm clean vertical gap below fly_cable (z=1.495..1.505)!
    lp._add_box(bm_fr, (0.0, 0.590, 1.383), (0.420, 0.032, 0.158), mat_idx=0, bevel=0.004, segments=2)

    # Split head-sheave hanger brackets flanking P_Head sheave ((0.0, 0.722, 1.575)) — completely clear of vertical cable!
    _add_split_head_hangers(bm_fr, 0.0, 0.722, 1.575, 0.215, 1.495, mat_silver=0, mat_steel=1)

    # Cable splitter cheek block at (0, 0.60, 1.50) below fly_cable (z=1.460..1.488) with twin guide bolts
    lp._add_box(bm_fr, (0.0, 0.600, 1.474), (0.072, 0.054, 0.026), mat_idx=0, bevel=0.0025, segments=1)
    for sx in (-1.0, 1.0):
        lp._add_hex_bolt(bm_fr, (sx * 0.036, 0.600, 1.474), "X",
                         head_r=0.007, head_h=0.005, washer_r=0.010, washer_h=0.0024, sign=sx, mat_idx=1)
        # Fasteners on overhead crosshead & seat post
        lp._add_hex_bolt(bm_fr, (sx * 0.095, -0.005, 1.460), "Y",
                         head_r=0.0075, head_h=0.0055, washer_r=0.011, washer_h=0.0026, sign=-1.0, mat_idx=1)
        lp._add_hex_bolt(bm_fr, (sx * 0.054, -0.050, 0.140), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)

    # Acrylic front shields (replacing hfront_wing/.001, y=0.590, z=[0.138, 1.296]) + 6 L-clips
    bm_acr = bmesh.new()
    bm_clp = bmesh.new()
    _add_acrylic_stack_front(
        bm_acr, bm_clp, cx=0.0, y_acr=0.590, z_bot=0.138, z_top=1.296,
        half_w=0.204, clip_zs=(0.230, 0.715, 1.205), slot_half=0.036, upright_attach_x=0.215,
    )

    created.append(_finalize_sm_mesh(pfx + "Frame", bm_fr, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "AcrylicFront", bm_acr, [mats["acrylic"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "ShieldClips", bm_clp, [mats["grip"], mats["steel"]], root, coll, 35.0))
    return created, touched


# ==============================================================================
# 5. P_leg_extension (Grounded chassis, zero-penetration low cable, contoured shin roller, acrylic)
# ==============================================================================

def _upgrade_leg_extension(root, coll, mats):
    code = "LE"
    pfx = f"{PFX}{code}_"
    root_set = set(lp._descendants(root)) | {root}
    floor_z = -root.location.z  # -0.0042 (world z=0)
    created = []
    touched = []

    # 5a. Extend 4 tower_foot cylinders down to floor_z = -0.0042 (world z = 0.0000!)
    touched.extend(_extend_tower_feet_to_floor(
        root, ("tower_foot.056", "tower_foot.057", "tower_foot.058", "tower_foot.059"), floor_z, root_set
    ))

    # 5b. Raise P_Head sheave.014 slightly (+0.025 m to z=1.500) so exit clears cover.014 (z_max=1.405) cleanly
    sheave = bpy.data.objects.get("P_Head sheave.014")
    if sheave:
        _tag_and_restore_xform(sheave)
        sheave.location = Vector((0.0485, 0.7682, 1.500))
        touched.append(sheave.name)

    # 5c. Reroute Coated load cable.014 with 0 penetrations & 100% unobstructed front acrylic/placard:
    #     stack (0, 0.80, 0.9633+0.28*v) -> Head sheave -> outer-right upper pulley (0.258, 0.625, 1.485)
    #     (35 mm outside right shroud, 100% clear of LEG EXTENSION placard & acrylic!) -> vertical drop to
    #     (0.258, 0.625, 0.145) -> low horizontal run to (0.200, -0.050, 0.145) -> straight up to cam underside (0.200, -0.050, 0.326)!
    lc = bpy.data.objects.get("Coated load cable.014")
    if lc:
        _tag_and_restore_xform(lc)
        sp = lc.data.splines[0]
        if PROP_ORIG_SPLINE not in lc:
            lc[PROP_ORIG_SPLINE] = json.dumps([[float(c) for c in pt.co] for pt in sp.points])
        d_xy = Vector((0.258, 0.625 - 0.800, 0.0)).normalized()
        sh_c = Vector((0.0, 0.800, 1.500)) + d_xy * 0.058
        if sheave:
            sheave.location = sh_c
        pts = [(0.0, 0.800, 0.9633)]
        for i in range(16):
            t = (math.pi * 0.55) * i / 15.0
            p_arc = sh_c - 0.058 * math.cos(t) * d_xy + Vector((0.0, 0.0, 0.058 * math.sin(t)))
            pts.append((p_arc.x, p_arc.y, p_arc.z))
        pts.extend([
            (0.258,  0.625, 1.485),  # outer-right upper redirection pulley (35 mm clear outside right shroud!)
            (0.258,  0.625, 0.145),  # outer-right lower pulley
            (0.200, -0.050, 0.145),  # lower pulley directly under cam arm (142 mm behind leg_pivot_body & pop_pin!)
            (0.200, -0.050, 0.326),  # meets cam underside cleanly (0 penetrations across all Stroke!)
        ])
        assert len(pts) == len(sp.points), f"LE cable expected {len(sp.points)}, got {len(pts)}"
        for pt, xyz in zip(sp.points, pts):
            pt.co = (*xyz, 1.0)
        lc.data.bevel_depth = 0.0045
        touched.append(lc.name)

    # 5d. Grounded base spine, 4 L-anchor flanges, split head hangers, 3 guarded pulleys, bolts
    bm_fr = bmesh.new()   # mat 0=silver, 1=steel, 2=grip
    bm_pl = bmesh.new()   # guarded sheaves separated from structural frame -> clean cable-vs-frame checks
    lp._add_box(bm_fr, (0.0, -0.005, 0.050), (0.084, 1.290, 0.084), mat_idx=0, bevel=0.005, segments=2)
    lp._add_tube_cap(bm_fr, (0.0, -0.650, 0.050), "Y", -1.0, 0.084, 0.084, depth=0.010, mat_idx=2)
    for py in (-0.570, 0.000, 0.520):
        lp._add_box(bm_fr, (0.0, py, floor_z + 0.008), (0.094, 0.120, 0.016), mat_idx=2, bevel=0.002, segments=1)
    for sx in (-1.0, 1.0):
        _add_anchor_flange(bm_fr, sx * 0.042, sx, -0.570, floor_z, 0.068, 0, 1)
        _add_anchor_flange(bm_fr, sx * 0.240, sx,  0.720, floor_z, 0.092, 0, 1)

    # Split head-sheave hanger brackets flanking angled head sheave (embedded cleanly at riser centers!)
    lp._add_box(bm_fr, (-0.129, 0.768, 1.405), (0.168, 0.042, 0.026), mat_idx=0, bevel=0.0025, segments=1)
    lp._add_box(bm_fr, ( 0.165, 0.768, 1.405), (0.094, 0.042, 0.026), mat_idx=0, bevel=0.0025, segments=1)
    lp._add_box(bm_fr, (-0.045, 0.768, 1.456), (0.014, 0.046, 0.106), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, ( 0.118, 0.768, 1.456), (0.014, 0.046, 0.106), mat_idx=0, bevel=0.002, segments=1)

    # 3 guarded pulleys along outer-right channel (support brackets stay clear of cable lines!)
    # 1) Upper-right redirection pulley outside Side shroud.058 (bracket at y=0.662, z=1.405 -> clear of drop at y=0.625!)
    lp._add_box(bm_fr, (0.232, 0.662, 1.405), (0.056, 0.042, 0.026), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.662, 1.442), (0.026, 0.028, 0.066), mat_idx=0, bevel=0.002, segments=1)
    _add_guarded_sheave(bm_pl, (0.258, 0.625, 1.460), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # 2) Outer-right lower pulley (bracket z<=0.105 -> cleanly below cable z=0.145!)
    lp._add_box(bm_fr, (0.140, 0.625, 0.064), (0.245, 0.040, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.625, 0.100), (0.028, 0.034, 0.052), mat_idx=0, bevel=0.002, segments=1)
    _add_guarded_sheave(bm_pl, (0.258, 0.625, 0.145), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # 3) Lower front pulley under cam arm (bracket z<=0.105 -> cleanly below cable z=0.145!)
    lp._add_box(bm_fr, (0.115, -0.050, 0.064), (0.195, 0.040, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.200, -0.050, 0.100), (0.028, 0.034, 0.052), mat_idx=0, bevel=0.002, segments=1)
    _add_guarded_sheave(bm_pl, (0.200, -0.050, 0.145), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # Seat & back post mounting bolts
    for sx in (-1.0, 1.0):
        lp._add_hex_bolt(bm_fr, (sx * 0.058, 0.000, 0.360), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)
        lp._add_hex_bolt(bm_fr, (sx * 0.0465, 0.360, 0.700), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)

    # 5e. Contoured shin bolster roller with concentric molded vinyl end-caps (parented to P_leg_lever!)
    #     Exact same local center (0, -0.32, -0.02) and outer radius 0.062 -> z=[0.218, 0.342] exact!
    lv = bpy.data.objects.get("P_leg_lever")
    if lv:
        bm_sr = bmesh.new()
        half_prof = [
            (0.0620, 0.000),
            (0.0620, 0.188),
            (0.0595, 0.203),
            (0.0608, 0.207),  # raised piping bead
            (0.0565, 0.211),  # recessed seam groove
            (0.0510, 0.214),  # concentric molded end-cap outer ring
            (0.0410, 0.212),  # recessed ring
            (0.0330, 0.216),  # inner raised dome
            (0.0150, 0.2185), # center plateau
            (0.0100, 0.2175), # dimple
        ]
        full_prof = [(r, -ax) for (r, ax) in reversed(half_prof[1:])] + list(half_prof)
        lp._add_revolved(bm_sr, full_prof, (0.0, -0.320, -0.020), axis="X", segs=32, mat_idx=0, cap_ends=True)
        for f in bm_sr.faces:
            if abs(f.calc_center_median().x) > 0.206:
                f.material_index = 1
        created.append(_finalize_sm_mesh(pfx + "ShinRoller", bm_sr, [mats["pad"], mats["grip"]], lv, coll, 48.0))

    # Acrylic front shields (replacing hfront_wing.028/.029, y=0.620, z=[0.130, 1.212]) + 6 L-clips
    bm_acr = bmesh.new()
    bm_clp = bmesh.new()
    _add_acrylic_stack_front(
        bm_acr, bm_clp, cx=0.0, y_acr=0.620, z_bot=0.130, z_top=1.212,
        half_w=0.194, clip_zs=(0.220, 0.670, 1.125), slot_half=0.036, upright_attach_x=0.205,
    )

    created.append(_finalize_sm_mesh(pfx + "Frame", bm_fr, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "Pulleys", bm_pl, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 38.0))
    created.append(_finalize_sm_mesh(pfx + "AcrylicFront", bm_acr, [mats["acrylic"]], root, coll, 35.0))
    created.append(_finalize_sm_mesh(pfx + "ShieldClips", bm_clp, [mats["grip"], mats["steel"]], root, coll, 35.0))
    return created, touched


# ==============================================================================
# Main entry point (idempotent)
# ==============================================================================

def apply() -> dict:
    parent_coll = bpy.data.collections["SET"]
    coll = parent_coll.children.get(COLL)
    if coll is None:
        if bpy.data.collections.get(COLL):
            raise ValueError(f"{COLL} already exists outside SET")
        coll = bpy.data.collections.new(COLL)
        parent_coll.children.link(coll)

    # 1. Clean up previous run's created objects, meshes, and dedicated materials (idempotency)
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
    for mn in list(bpy.data.materials.keys()):
        if mn.startswith(PFX):
            bpy.data.materials.remove(bpy.data.materials[mn], do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.name.startswith(PFX) and me.users == 0:
            bpy.data.meshes.remove(me)

    builders = {
        "CC": _upgrade_cable_crossover,
        "SCR": _upgrade_seated_cable_row,
        "CP": _upgrade_chest_press,
        "PD": _upgrade_pec_deck,
        "LE": _upgrade_leg_extension,
    }

    per_machine = {}
    for code, root_name in TARGET_ROOTS:
        root = bpy.data.objects.get(root_name)
        if root is None:
            raise RuntimeError(f"{root_name} not found in scene")

        # Remove replaced obsolete parts inside this machine's hierarchy (no-op on 2nd run)
        desc_set = set(lp._descendants(root))
        removed = []
        for nm in REPLACED_BY_MACHINE[code]:
            ob = bpy.data.objects.get(nm)
            if ob is not None and ob in desc_set:
                data = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                removed.append(nm)

        mats = _build_machine_materials(code)
        created, touched = builders[code](root, coll, mats)
        rebound = _rebind_machine_materials(root, code, mats)

        per_machine[root_name] = {
            "code": code,
            "removed": len(removed),
            "added": len(created),
            "added_names": [o.name for o in created],
            "touched": touched,
            "rebound": rebound,
        }

    # Cleanup any orphan cloned meshes
    for me in list(bpy.data.meshes):
        if me.name.startswith(PFX) and me.users == 0:
            bpy.data.meshes.remove(me)

    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    for code, root_name in TARGET_ROOTS:
        root = bpy.data.objects[root_name]
        tot_tris = 0
        add_tris = 0
        for ob in lp._descendants(root):
            if ob.type in ("MESH", "CURVE", "FONT"):
                eo = ob.evaluated_get(deps)
                me = eo.to_mesh()
                if me and len(me.vertices):
                    me.calc_loop_triangles()
                    t = len(me.loop_triangles)
                    tot_tris += t
                    if ob.name.startswith(PFX):
                        add_tris += t
                eo.to_mesh_clear()
        per_machine[root_name]["total_objects"] = len(lp._descendants(root))
        per_machine[root_name]["total_triangles"] = tot_tris
        per_machine[root_name]["added_triangles"] = add_tris

    return {"machines": per_machine}


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
    print("detail6_stack_machines", json.dumps(res, ensure_ascii=False))
    if save is not None:
        bpy.ops.wm.save_as_mainfile(
            filepath=str(save), copy=True, compress=True, relative_remap=False
        )
        print("saved", save)


if __name__ == "__main__":
    _main()
