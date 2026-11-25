"""Install the reception sign into the current gym scene, without saving it."""
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


_ASSET = Path(__file__).resolve().parents[1] / "parts/detail_info_main_sign/sign.json.gz"
# Viewport fallback (linear RGB, metallic, roughness) and flat BSDF defaults.
_FINISHES = (
    ("Backpan", (0.04, 0.04, 0.042), 0.0, 0.88),
    ("Frame", (0.72, 0.74, 0.77), 1.0, 0.30),
    ("ExpandedMetal", (0.24, 0.25, 0.27), 1.0, 0.36),
    ("Raceway", (0.012, 0.013, 0.014), 0.0, 0.43),
    ("LetterReturn", (0.050, 0.052, 0.055), 0.65, 0.33),
    ("OpalFace", (0.95, 0.935, 0.91), 0.0, 0.30),
    ("LEDTube", (0.98, 0.98, 0.96), 0.0, 0.22),
)

# Sign dimensions in mm (x: left->right, up: vertical relative to letter center z=2.360m, depth: from mural y=-6.680m).
_SIGN_W = 2420.0
_SIGN_UP_LO = -310.0
_SIGN_UP_HI = 380.0
_MULLION_TOP_UP = 1225.0  # z = 3.585m (5mm below ceiling slab at 3.590m)
_MULLION_XS = (-408.0, 408.0)
_MULLION_W = 24.0
_HEADER_UP = 276.0
_HEADER_H = 22.0
_LED_UP = 374.0
_LED_RADIUS = 10.0  # 20mm diameter tube


def _reset_tree(mat):
    if mat.node_tree is None:
        mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (280, 0)
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return tree, bsdf


def _build_backpan(tree, bsdf):
    """Dark charcoal backpan with subtle top & bottom warm light wash gradient like ref 027."""
    nodes, links = tree.nodes, tree.links

    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 0)
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-700, 0)
    links.new(tc.outputs["Object"], sep.inputs["Vector"])

    # Normalize local Z from [-0.310, +0.380] -> [0, 1]
    norm_z = nodes.new("ShaderNodeMapRange")
    norm_z.location = (-480, 120)
    norm_z.clamp = True
    norm_z.inputs["From Min"].default_value = _SIGN_UP_LO / 1000.0
    norm_z.inputs["From Max"].default_value = _SIGN_UP_HI / 1000.0
    links.new(sep.outputs["Z"], norm_z.inputs["Value"])

    # Subtle matte plaster grain
    grain = nodes.new("ShaderNodeTexNoise")
    grain.location = (-480, -160)
    grain.inputs["Scale"].default_value = 35.0
    grain.inputs["Detail"].default_value = 4.0
    links.new(tc.outputs["Object"], grain.inputs["Vector"])

    # Vertical luminance gradient: brighter warm-beige wash at top & bottom, dark charcoal in middle.
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 180)
    ramp.color_ramp.interpolation = "B_SPLINE"
    el = ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.28, 0.265, 0.235, 1.0)
    el[1].position = 1.0
    el[1].color = (0.42, 0.40, 0.355, 1.0)
    for pos, col in (
        (0.16, (0.065, 0.064, 0.060, 1.0)),
        (0.42, (0.022, 0.023, 0.025, 1.0)),
        (0.62, (0.024, 0.025, 0.027, 1.0)),
        (0.84, (0.085, 0.082, 0.075, 1.0)),
    ):
        e = el.new(pos)
        e.color = col
    links.new(norm_z.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    # Gentle indirect bounce glow at very top & bottom edges (0 in middle) so diamond holes read against light wash.
    em_ramp = nodes.new("ShaderNodeValToRGB")
    em_ramp.location = (-200, -120)
    em_ramp.color_ramp.interpolation = "B_SPLINE"
    eel = em_ramp.color_ramp.elements
    eel[0].position = 0.0
    eel[0].color = (0.30, 0.28, 0.24, 1.0)
    eel[1].position = 1.0
    eel[1].color = (0.48, 0.45, 0.39, 1.0)
    for pos, col in (
        (0.18, (0.012, 0.012, 0.011, 1.0)),
        (0.50, (0.0, 0.0, 0.0, 1.0)),
        (0.82, (0.020, 0.019, 0.017, 1.0)),
    ):
        e = eel.new(pos)
        e.color = col
    links.new(norm_z.outputs["Result"], em_ramp.inputs["Fac"])
    links.new(em_ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.20

    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.88
    bsdf.inputs["Specular IOR Level"].default_value = 0.12

    bump = nodes.new("ShaderNodeBump")
    bump.location = (40, -260)
    bump.inputs["Strength"].default_value = 0.04
    bump.inputs["Distance"].default_value = 0.0008
    links.new(grain.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _build_galvanized_frame(tree, bsdf):
    """True metallic galvanized steel (Metallic 1.0, Coat 0, bold mottled spangle & wide roughness swing)."""
    nodes, links = tree.nodes, tree.links

    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (-960, 0)

    # Crystalline zinc spangle (~22mm cells).
    vor = nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-720, 260)
    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 45.0
    vor.inputs["Randomness"].default_value = 0.88
    links.new(tc.outputs["Object"], vor.inputs["Vector"])

    spangle = nodes.new("ShaderNodeRGBToBW")
    spangle.location = (-480, 260)
    links.new(vor.outputs["Color"], spangle.inputs["Color"])

    # Broad mottled mill-sheen patches (~200-350mm scale, clearly visible at lobby distance).
    mottle = nodes.new("ShaderNodeTexNoise")
    mottle.location = (-720, 0)
    mottle.noise_dimensions = "3D"
    mottle.inputs["Scale"].default_value = 4.2
    mottle.inputs["Detail"].default_value = 6.0
    mottle.inputs["Roughness"].default_value = 0.62
    mottle.inputs["Distortion"].default_value = 0.28
    links.new(tc.outputs["Object"], mottle.inputs["Vector"])

    # Fine rolled-steel micro-grain.
    fine = nodes.new("ShaderNodeTexNoise")
    fine.location = (-720, -260)
    fine.noise_dimensions = "3D"
    fine.inputs["Scale"].default_value = 80.0
    fine.inputs["Detail"].default_value = 4.0
    fine.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], fine.inputs["Vector"])

    # Blend 0.30 * spangle + 0.55 * mottle + 0.15 * fine.
    m_sp = nodes.new("ShaderNodeMath")
    m_sp.operation = "MULTIPLY"
    m_sp.inputs[1].default_value = 0.30
    links.new(spangle.outputs["Val"], m_sp.inputs[0])

    m_mo = nodes.new("ShaderNodeMath")
    m_mo.operation = "MULTIPLY"
    m_mo.inputs[1].default_value = 0.55
    links.new(mottle.outputs["Fac"], m_mo.inputs[0])

    m_fi = nodes.new("ShaderNodeMath")
    m_fi.operation = "MULTIPLY"
    m_fi.inputs[1].default_value = 0.15
    links.new(fine.outputs["Fac"], m_fi.inputs[0])

    add1 = nodes.new("ShaderNodeMath")
    add1.operation = "ADD"
    links.new(m_sp.outputs[0], add1.inputs[0])
    links.new(m_mo.outputs[0], add1.inputs[1])

    galva_fac = nodes.new("ShaderNodeMath")
    galva_fac.operation = "ADD"
    links.new(add1.outputs[0], galva_fac.inputs[0])
    links.new(m_fi.outputs[0], galva_fac.inputs[1])

    # High-contrast cool zinc Base Color range: (0.55,0.57,0.60) ~ (0.85,0.87,0.90).
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-80, 220)
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[0].color = (0.55, 0.57, 0.60, 1.0)
    ramp.color_ramp.elements[1].position = 0.70
    ramp.color_ramp.elements[1].color = (0.85, 0.87, 0.90, 1.0)
    links.new(galva_fac.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    bsdf.inputs["Metallic"].default_value = 1.0

    # Wide Roughness variation (0.20..0.45) driven by mottle & spangle so LED highlights shimmer unevenly.
    rgh_map = nodes.new("ShaderNodeMapRange")
    rgh_map.location = (-80, -40)
    rgh_map.clamp = True
    rgh_map.inputs[1].default_value = 0.30
    rgh_map.inputs[2].default_value = 0.70
    rgh_map.inputs[3].default_value = 0.45
    rgh_map.inputs[4].default_value = 0.20
    links.new(galva_fac.outputs[0], rgh_map.inputs[0])
    links.new(rgh_map.outputs[0], bsdf.inputs["Roughness"])

    bsdf.inputs["Coat Weight"].default_value = 0.0

    # Spangle + micro-grain bump breaks specular flatness.
    b_sp = nodes.new("ShaderNodeMath")
    b_sp.operation = "MULTIPLY"
    b_sp.inputs[1].default_value = 0.65
    links.new(spangle.outputs["Val"], b_sp.inputs[0])

    b_fi = nodes.new("ShaderNodeMath")
    b_fi.operation = "MULTIPLY"
    b_fi.inputs[1].default_value = 0.35
    links.new(fine.outputs["Fac"], b_fi.inputs[0])

    b_sum = nodes.new("ShaderNodeMath")
    b_sum.operation = "ADD"
    links.new(b_sp.outputs[0], b_sum.inputs[0])
    links.new(b_fi.outputs[0], b_sum.inputs[1])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (60, -280)
    bump.inputs["Strength"].default_value = 0.07
    bump.inputs["Distance"].default_value = 0.0015
    links.new(b_sum.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _build_expanded_metal(tree, bsdf):
    """Dark metallic expanded steel mesh (Metallic 1.0, Base 0.20~0.30, Rough 0.30~0.45)."""
    nodes, links = tree.nodes, tree.links

    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (-820, 0)

    grain = nodes.new("ShaderNodeTexNoise")
    grain.location = (-580, 120)
    grain.noise_dimensions = "3D"
    grain.inputs["Scale"].default_value = 16.0
    grain.inputs["Detail"].default_value = 5.0
    grain.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], grain.inputs["Vector"])

    micro = nodes.new("ShaderNodeTexNoise")
    micro.location = (-580, -140)
    micro.noise_dimensions = "3D"
    micro.inputs["Scale"].default_value = 100.0
    micro.inputs["Detail"].default_value = 4.0
    micro.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], micro.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-160, 180)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.20, 0.21, 0.23, 1.0)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (0.30, 0.31, 0.33, 1.0)
    links.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Coat Weight"].default_value = 0.0

    rgh_map = nodes.new("ShaderNodeMapRange")
    rgh_map.location = (-160, -40)
    rgh_map.clamp = True
    rgh_map.inputs[1].default_value = 0.25
    rgh_map.inputs[2].default_value = 0.78
    rgh_map.inputs[3].default_value = 0.45
    rgh_map.inputs[4].default_value = 0.30
    links.new(grain.outputs["Fac"], rgh_map.inputs[0])
    links.new(rgh_map.outputs[0], bsdf.inputs["Roughness"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (20, -220)
    bump.inputs["Strength"].default_value = 0.03
    bump.inputs["Distance"].default_value = 0.001
    links.new(micro.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _mm_pt(x_mm, up_mm, depth_mm):
    return (-x_mm / 1000.0, depth_mm / 1000.0, up_mm / 1000.0)


def _add_box_mm(bm, x0, x1, up0, up1, d0, d1, mat_idx, bevel_mm=0.0):
    cx = 0.5 * (x0 + x1)
    cu = 0.5 * (up0 + up1)
    cd = 0.5 * (d0 + d1)
    sx = (x1 - x0) / 1000.0
    sy = (d1 - d0) / 1000.0
    sz = (up1 - up0) / 1000.0
    mat = Matrix.Translation(_mm_pt(cx, cu, cd)) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    verts = ret["verts"]
    vset = set(verts)
    faces = [f for f in bm.faces if all(v in vset for v in f.verts)]
    for f in faces:
        f.material_index = mat_idx
    if bevel_mm > 0.0:
        edges = list({e for f in faces for e in f.edges})
        bev = bmesh.ops.bevel(
            bm, geom=edges, offset=bevel_mm / 1000.0, segments=2,
            affect="EDGES", clamp_overlap=True, profile=0.5,
        )
        for f in bev.get("faces", ()):
            f.material_index = mat_idx


def _add_cyl_y_mm(bm, cx, cu, d0, d1, radius_mm, mat_idx, segments=20):
    """Cylinder along depth (+Y) axis in sign coordinates."""
    depth = (d1 - d0) / 1000.0
    cd = 0.5 * (d0 + d1)
    mat = Matrix.Translation(_mm_pt(cx, cu, cd)) @ Matrix.Rotation(math.radians(90.0), 4, "X")
    ret = bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=radius_mm / 1000.0, radius2=radius_mm / 1000.0, depth=depth, matrix=mat,
    )
    vset = set(ret["verts"])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = mat_idx
            f.smooth = (len(f.verts) == 4)


def _add_cyl_x_mm(bm, x0, x1, cu, cd, radius_mm, mat_idx, segments=24):
    """Horizontal cylinder along sign width (X) axis for the linear LED tube."""
    length = (x1 - x0) / 1000.0
    cx = 0.5 * (x0 + x1)
    mat = Matrix.Translation(_mm_pt(cx, cu, cd)) @ Matrix.Rotation(math.radians(90.0), 4, "Y")
    ret = bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=radius_mm / 1000.0, radius2=radius_mm / 1000.0, depth=length, matrix=mat,
    )
    vset = set(ret["verts"])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = mat_idx
            f.smooth = (len(f.verts) == 4)


def _add_expanded_metal_mm(bm, x_lo, x_hi, up_lo, up_hi, d0, d1, mat_idx):
    """Build a continuous watertight diamond-hole expanded metal sheet (43x22mm pitch)."""
    pw = 43.0   # horizontal diamond pitch (mm)
    ph = 22.0   # full vertical pitch (mm); staggered row step = 11mm
    hx = 18.2   # hole half-width (leaves ~3.3mm diagonal strands)
    hy = 8.4    # hole half-height

    sub = bmesh.new()
    # Staggered brick layout of 43 x 11 mm half-rows tiled cleanly across [x_lo, x_hi] x [up_lo, up_hi]
    row_h = ph / 2.0
    n_rows = int(math.ceil((up_hi - up_lo) / row_h))
    n_cols = int(math.ceil((x_hi - x_lo) / pw)) + 1

    # Use clean non-overlapping rectangular cells of size (pw, ph) with staggered row shifts,
    # clipped to [x_lo, x_hi] x [up_lo, up_hi]. Simpler: regular grid of (pw/2, ph/2) half-cells!
    # Every (iw, ih) cell of size (pw/2, ph/2) has ONE diagonal strand corner depending on (iw + ih) % 2!
    # Wait: even cleaner — in a diamond grid with centers at (col*pw + (row%2)*pw/2, row*ph/2),
    # each rectangle [cx - pw/2, cx + pw/2] x [cy - ph/2, cy + ph/2] overlaps adjacent staggered rows.
    # Instead, decompose the plane into exact tiling squares/rectangles of size (pw/2, ph/2) = (21.5, 11.0)!
    # Inside each half-cell [0, cw] x [0, ch], ONE corner is a diamond center (hole) and the OPPOSITE
    # corner is a strand intersection! Removing the triangular hole corner leaves a single clean quad/trapezoid
    # whose edges match neighbors identically -> 100% watertight, zero overlaps, zero T-junctions!
    cw = pw / 2.0  # 21.5 mm
    ch = ph / 2.0  # 11.0 mm
    # Hole corner leg lengths along cell edges (t in (0, 1)):
    # Strand width ~3.3mm => hole covers ~84% of half-pitch along X and ~78% along Y
    fx = hx / cw   # ~0.846
    fy = hy / ch   # ~0.764

    i0 = int(math.floor(x_lo / cw))
    i1 = int(math.ceil(x_hi / cw))
    j0 = int(math.floor(up_lo / ch))
    j1 = int(math.ceil(up_hi / ch))

    def clip_poly_rect(poly, x0, x1, y0, y1):
        def clip_edge(pts, inside, intersect):
            if not pts:
                return []
            out = []
            prev = pts[-1]
            prev_in = inside(prev)
            for curr in pts:
                curr_in = inside(curr)
                if curr_in:
                    if not prev_in:
                        out.append(intersect(prev, curr))
                    out.append(curr)
                elif prev_in:
                    out.append(intersect(prev, curr))
                prev, prev_in = curr, curr_in
            return out

        pts = poly
        pts = clip_edge(pts, lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0])))
        pts = clip_edge(pts, lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0])))
        pts = clip_edge(pts, lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0))
        pts = clip_edge(pts, lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1))
        return pts

    vcache = {}
    def get_v(x, y):
        key = (round(x, 4), round(y, 4))
        v = vcache.get(key)
        if v is None:
            v = sub.verts.new(_mm_pt(x, y, d0))
            vcache[key] = v
        return v

    for j in range(j0, j1):
        ya = j * ch
        yb = (j + 1) * ch
        for i in range(i0, i1):
            xa = i * cw
            xb = (i + 1) * cw
            # Diamond centers lie at grid vertices where (i + j) is even.
            # Every cell (i, j) has TWO even corners (diagonal pair): (i, j) & (i+1, j+1) if (i+j)%2==0,
            # else (i+1, j) & (i, j+1). Cutting a triangle (fx*cw, fy*ch) off BOTH even corners leaves
            # a clean 6-gon (actually a diagonal band/strip connecting the two odd corners)!
            # Wait: two adjacent cells share the exact cut points along their shared edge!
            if (i + j) % 2 == 0:
                # Even corners are bottom-left (xa, ya) and top-right (xb, yb) -> cut both!
                poly = [
                    (xa + fx * cw, ya),
                    (xb, ya),
                    (xb, yb - fy * ch),
                    (xb - fx * cw, yb),
                    (xa, yb),
                    (xa, ya + fy * ch),
                ]
            else:
                # Even corners are bottom-right (xb, ya) and top-left (xa, yb) -> cut both!
                poly = [
                    (xa, ya),
                    (xb - fx * cw, ya),
                    (xb, ya + fy * ch),
                    (xb, yb),
                    (xa + fx * cw, yb),
                    (xa, yb - fy * ch),
                ]
            clipped = clip_poly_rect(poly, x_lo, x_hi, up_lo, up_hi)
            # Deduplicate consecutive identical points
            clean = []
            for pt in clipped:
                if not clean or abs(pt[0] - clean[-1][0]) > 1e-4 or abs(pt[1] - clean[-1][1]) > 1e-4:
                    clean.append(pt)
            if len(clean) >= 3 and abs(clean[0][0] - clean[-1][0]) <= 1e-4 and abs(clean[0][1] - clean[-1][1]) <= 1e-4:
                clean.pop()
            if len(clean) < 3:
                continue
            vs = [get_v(px, py) for px, py in clean]
            # Remove any duplicate vertex refs
            uniq = []
            for v in vs:
                if v not in uniq:
                    uniq.append(v)
            if len(uniq) >= 3:
                try:
                    sub.faces.new(uniq)
                except ValueError:
                    pass

    bmesh.ops.remove_doubles(sub, verts=sub.verts[:], dist=1e-5)
    # Drop any tiny detached corner scraps clipped at the sheet boundary so the mesh is 1 continuous island.
    sub.faces.ensure_lookup_table()
    visited_f = set()
    islands = []
    for f0 in sub.faces:
        if f0 in visited_f:
            continue
        comp = []
        stk = [f0]
        visited_f.add(f0)
        while stk:
            cur = stk.pop()
            comp.append(cur)
            for e in cur.edges:
                for lf in e.link_faces:
                    if lf not in visited_f:
                        visited_f.add(lf)
                        stk.append(lf)
        islands.append(comp)
    if len(islands) > 1:
        islands.sort(key=len, reverse=True)
        scrap_faces = [f for isl in islands[1:] for f in isl]
        bmesh.ops.delete(sub, geom=scrap_faces, context="FACES")
        loose = [v for v in sub.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(sub, geom=loose, context="VERTS")
    # Extrude sheet along +Y (depth d0 -> d1) into a closed solid
    orig_faces = sub.faces[:]
    ret = bmesh.ops.extrude_face_region(sub, geom=orig_faces)
    extruded_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(sub, verts=extruded_verts, vec=Vector((0.0, (d1 - d0) / 1000.0, 0.0)))
    bmesh.ops.recalc_face_normals(sub, faces=sub.faces[:])
    if sub.calc_volume(signed=True) < 0.0:
        bmesh.ops.reverse_faces(sub, faces=sub.faces[:])
    for f in sub.faces:
        f.material_index = mat_idx

    # Copy into main bmesh
    vert_map = {}
    for v in sub.verts:
        vert_map[v] = bm.verts.new(v.co)
    for f in sub.faces:
        try:
            nf = bm.faces.new([vert_map[v] for v in f.verts])
            nf.material_index = mat_idx
        except ValueError:
            pass
    sub.free()


def _clip_tri_outside_band(tri_2d, y_lo, y_hi):
    """Split a 2D triangle into polygons strictly below y_lo or strictly above y_hi."""
    def clip_half(pts, keep_fn, y_cut):
        if not pts:
            return []
        out = []
        prev = pts[-1]
        prev_in = keep_fn(prev[1])
        for curr in pts:
            curr_in = keep_fn(curr[1])
            if curr_in:
                if not prev_in:
                    t = (y_cut - prev[1]) / (curr[1] - prev[1])
                    out.append((prev[0] + t * (curr[0] - prev[0]), y_cut))
                out.append(curr)
            elif prev_in:
                t = (y_cut - prev[1]) / (curr[1] - prev[1])
                out.append((prev[0] + t * (curr[0] - prev[0]), y_cut))
            prev, prev_in = curr, curr_in
        return out

    result = []
    below = clip_half(tri_2d, lambda y: y <= y_lo, y_lo)
    if len(below) >= 3:
        result.append(below)
    above = clip_half(tri_2d, lambda y: y >= y_hi, y_hi)
    if len(above) >= 3:
        result.append(above)
    return result


def _add_letters_from_asset(bm, asset, ret_d0, ret_d1, face_d0, face_d1, mat_ret, mat_face):
    """Extract the 10 WATCH COACH letter shapes from sign.json.gz, widen tight tracking by ~4%,
    add crisp 027-style 6% horizontal stencil slits to C and O, and extrude clean manifold channel letters."""
    verts = asset["vertices"]
    faces = asset["faces"]
    mats = asset["material"]

    front_tris = [
        f for f, m in zip(faces, mats)
        if m == 5 and all(abs(verts[vi][2] - 83.0) < 0.02 for vi in f)
    ]
    adj = defaultdict(set)
    for f in front_tris:
        for i in range(3):
            a, b = f[i], f[(i + 1) % 3]
            adj[a].add(b)
            adj[b].add(a)

    seen = set()
    comp_verts = []
    for v in adj:
        if v in seen:
            continue
        stack = [v]
        comp = set()
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            comp.add(u)
            stack.extend(adj[u] - seen)
        comp_verts.append(comp)

    # Sort left to right: W(0) A(1) T(2) C(3) H(4)  C(5) O(6) A(7) C(8) H(9)
    comp_info = []
    for comp in comp_verts:
        xs = [verts[i][0] for i in comp]
        ys = [verts[i][1] for i in comp]
        comp_info.append((min(xs), max(xs), min(ys), max(ys), comp))
    comp_info.sort(key=lambda item: item[0])

    # Map vertex -> component index
    v2c = {}
    for ci, (_, _, _, _, comp) in enumerate(comp_info):
        for vi in comp:
            v2c[vi] = ci

    tris_by_comp = [[] for _ in comp_info]
    for f in front_tris:
        tris_by_comp[v2c[f[0]]].append([(verts[vi][0], verts[vi][1]) for vi in f])

    # Add +4% (~6.5mm) tracking between letters within each word, preserving overall 2010mm span & center.
    extra_gap = 6.5  # mm (~4% of 161mm letter height)
    shifts = []
    acc = 0.0
    for ci in range(len(comp_info)):
        if ci > 0 and ci != 5:  # widen inter-letter gaps within WATCH and COACH
            acc += extra_gap
        elif ci == 5:  # keep word gap crisp
            acc += extra_gap * 1.2
        shifts.append(acc)

    new_x0 = comp_info[0][0] + shifts[0]
    new_x1 = comp_info[-1][1] + shifts[-1]
    orig_w = 2010.0
    scale_x = orig_w / (new_x1 - new_x0)
    mid_x = 0.5 * (new_x0 + new_x1)

    # Stencil slit on C (indices 3, 5, 8) and O (index 6): 6% of 161mm = 9.6mm horizontal cut on left spine.
    slit_half = 4.8
    stencil_indices = {3, 5, 6, 8}

    def extrude_2d_polys(polys_2d, d_back, d_front, mat_idx):
        sub = bmesh.new()
        vc = {}
        def gv(x, y):
            k = (round(x, 4), round(y, 4))
            v = vc.get(k)
            if v is None:
                v = sub.verts.new(_mm_pt(x, y, d_back))
                vc[k] = v
            return v
        for poly in polys_2d:
            vs = []
            for px, py in poly:
                v = gv(px, py)
                if not vs or v != vs[-1]:
                    vs.append(v)
            if len(vs) >= 3 and vs[0] == vs[-1]:
                vs.pop()
            if len(vs) >= 3 and len(set(vs)) == len(vs):
                try:
                    sub.faces.new(vs)
                except ValueError:
                    pass
        bmesh.ops.remove_doubles(sub, verts=sub.verts[:], dist=1e-5)
        bmesh.ops.dissolve_degenerate(sub, dist=1e-5, edges=sub.edges[:])
        ret = bmesh.ops.extrude_face_region(sub, geom=sub.faces[:])
        ev = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(sub, verts=ev, vec=Vector((0.0, (d_front - d_back) / 1000.0, 0.0)))
        bmesh.ops.recalc_face_normals(sub, faces=sub.faces[:])
        vmap = {v: bm.verts.new(v.co) for v in sub.verts}
        for f in sub.faces:
            try:
                nf = bm.faces.new([vmap[v] for v in f.verts])
                nf.material_index = mat_idx
            except ValueError:
                pass
        sub.free()

    for ci, (lx0, lx1, ly0, ly1, _) in enumerate(comp_info):
        dx = shifts[ci]
        x_mid_local = 0.5 * (lx0 + lx1)
        # For O (index 6), cut only left half of ring so right half stays solid like 027's O;
        # for C (3, 5, 8), cut left spine (x <= x_mid_local + 10mm) cleanly.
        polys = []
        for tri in tris_by_comp[ci]:
            if ci in stencil_indices:
                tri_cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3.0
                if tri_cx < x_mid_local:
                    pieces = _clip_tri_outside_band(tri, -slit_half, slit_half)
                else:
                    pieces = [tri]
            else:
                pieces = [tri]
            for p in pieces:
                polys.append([((x + dx - mid_x) * scale_x, y) for x, y in p])

        extrude_2d_polys(polys, ret_d0, ret_d1, mat_ret)
        extrude_2d_polys(polys, face_d0, face_d1, mat_face)


def _ensure_outward_normals(bm):
    """Guarantee every closed connected island has positive signed volume (outward normals)."""
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    visited = set()
    for f0 in bm.faces:
        if f0 in visited:
            continue
        island = []
        stack = [f0]
        visited.add(f0)
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for lf in e.link_faces:
                    if lf not in visited:
                        visited.add(lf)
                        stack.append(lf)
        # Copy island into a temporary bmesh and use Blender's exact signed volume (handles concave ngons).
        tmp = bmesh.new()
        vmap = {}
        for f in island:
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = tmp.verts.new(v.co)
            try:
                tmp.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                pass
        vol = tmp.calc_volume(signed=True)
        tmp.free()
        if vol < 0.0:
            bmesh.ops.reverse_faces(bm, faces=island)


def apply():
    root = bpy.context.scene.objects["Gym_InfoDesk"]
    old = [obj for obj in bpy.context.scene.objects
           if obj.parent == root and obj.name.startswith("InfoLogo_")]
    collection = old[0].users_collection[0] if old else root.users_collection[0]
    with gzip.open(_ASSET, "rt", encoding="utf-8") as source:
        asset = json.load(source)

    bm = bmesh.new()

    # 1. Four wall standoffs (2.0..11.0mm from mural y=-6.680 -> exact 2.0mm clearance!) + Backpan (10.2..13.2mm).
    for px in (-1120.0, 1120.0):
        for pu in (-255.0, 325.0):
            _add_cyl_y_mm(bm, px, pu, 2.0, 11.0, 17.0, 0, segments=20)
    _add_box_mm(bm, -_SIGN_W / 2.0, _SIGN_W / 2.0, _SIGN_UP_LO, _SIGN_UP_HI, 10.2, 13.2, 0)

    # 2. Expanded metal diamond sheet (43x22mm pitch, open edges — no picture-frame border!).
    _add_expanded_metal_mm(bm, -_SIGN_W / 2.0, _SIGN_W / 2.0, _SIGN_UP_LO, _SIGN_UP_HI, 25.0, 27.4, 2)

    # 3. Architectural galvanized steel mullions extending from sign bottom up to ceiling (z=3.585m),
    #    plus 3-segment horizontal header bar (no bottom/left/right outer frame border!) & rivet heads.
    mw = _MULLION_W / 2.0
    for mx in _MULLION_XS:
        _add_box_mm(bm, mx - mw, mx + mw, _SIGN_UP_LO, _MULLION_TOP_UP, 27.0, 39.0, 1, bevel_mm=1.6)
        # Rear wall mounting standoffs along upper extended mullion (2.0mm clear of mural, anchored into mullion).
        for bu in (560.0, 920.0, 1180.0):
            _add_box_mm(bm, mx - 8.0, mx + 8.0, bu - 14.0, bu + 14.0, 2.0, 28.0, 1)

    hh = _HEADER_H / 2.0
    header_spans = (
        (-_SIGN_W / 2.0, _MULLION_XS[0] - mw - 0.3),
        (_MULLION_XS[0] + mw + 0.3, _MULLION_XS[1] - mw - 0.3),
        (_MULLION_XS[1] + mw + 0.3, _SIGN_W / 2.0),
    )
    for hx0, hx1 in header_spans:
        _add_box_mm(bm, hx0, hx1, _HEADER_UP - hh, _HEADER_UP + hh, 27.0, 39.0, 1, bevel_mm=1.6)
    for bx in (-1120.0, -408.0, 408.0, 1120.0):
        _add_cyl_y_mm(bm, bx, _HEADER_UP, 38.5, 41.8, 3.4, 1, segments=14)

    # 4. Linear LED tube (20mm diameter, white emissive) right above upper header bar + dark backing channel
    #    mounted proud on the front of the mullions (no coplanar faces with mullions!).
    _add_box_mm(bm, -_SIGN_W / 2.0, _SIGN_W / 2.0, _LED_UP - 8.0, _LED_UP + 10.0, 38.4, 44.0, 3)
    _add_cyl_x_mm(bm, -_SIGN_W / 2.0 + 4.0, _SIGN_W / 2.0 - 4.0, _LED_UP, 49.0, _LED_RADIUS, 6, segments=24)

    # 5. Horizontal black raceway behind WATCH COACH (anchored cleanly into mullions and letter backs).
    _add_box_mm(bm, -1185.0, 1185.0, -26.0, 26.0, 38.4, 52.6, 3, bevel_mm=1.0)

    # 6. Channel letters WATCH COACH (return 52.0..82.2mm, luminous opal face 82.0..85.0mm).
    _add_letters_from_asset(bm, asset, 52.0, 82.2, 82.0, 85.0, 4, 5)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    _ensure_outward_normals(bm)
    mesh = bpy.data.meshes.new("Reception sign assembly")
    bm.to_mesh(mesh)
    bm.free()

    for finish, color, metallic, roughness in _FINISHES:
        name = "InfoMainSign_" + finish
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name)
        mat.diffuse_color = (*color, 1)
        mat.metallic = metallic
        mat.roughness = roughness
        tree, shader = _reset_tree(mat)
        if finish == "Backpan":
            _build_backpan(tree, shader)
        elif finish == "Frame":
            _build_galvanized_frame(tree, shader)
        elif finish == "ExpandedMetal":
            _build_expanded_metal(tree, shader)
        else:
            shader.inputs["Base Color"].default_value = (*color, 1)
            shader.inputs["Metallic"].default_value = metallic
            shader.inputs["Roughness"].default_value = roughness
            if finish == "OpalFace":
                shader.inputs["Emission Color"].default_value = (1, 0.975, 0.93, 1)
                shader.inputs["Emission Strength"].default_value = 3.2
            elif finish == "LEDTube":
                shader.inputs["Emission Color"].default_value = (1.0, 0.985, 0.96, 1.0)
                shader.inputs["Emission Strength"].default_value = 11.0
        mesh.materials.append(mat)
    mesh.update()

    retired_data = {obj.data for obj in old if obj.data is not None}
    for obj in old:
        bpy.data.objects.remove(obj, do_unlink=True)
    for data in retired_data:
        if data.users == 0:
            bpy.data.batch_remove(ids=(data,))

    mesh.name = "InfoLogo_MainSign"
    obj = bpy.data.objects.new("InfoLogo_MainSign", mesh)
    collection.objects.link(obj)
    obj.parent = root
    obj.location = (0, -0.660, 2.360)

    # Linear area light coupled to the LED tube (no shadow cost) so Metallic 1.0 galvanized frame
    # catches a crisp bright horizontal specular highlight strip just like ref 027.
    led_data = bpy.data.lights.new("InfoLogo_MainSign_LEDWash", "AREA")
    led_data.shape = "RECTANGLE"
    led_data.size = 2.38
    led_data.size_y = 0.022
    led_data.energy = 24.0
    led_data.color = (1.0, 0.98, 0.95)
    led_data.use_shadow = False
    if hasattr(led_data, "spread"):
        led_data.spread = math.radians(115.0)
    led_obj = bpy.data.objects.new("InfoLogo_MainSign_LEDWash", led_data)
    collection.objects.link(led_obj)
    led_obj.parent = root
    led_obj.location = (0.0, -0.660 + 0.058, 2.360 + _LED_UP / 1000.0 - 0.014)
    # Aim slightly downward & back toward the galvanized header bar and mesh face.
    led_obj.rotation_euler = (math.radians(32.0), 0.0, 0.0)
    led_obj.visible_camera = False

    return obj
