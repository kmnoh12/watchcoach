"""Detail pass 7: Photorealistic Korean glass neon signs for both gym neon signs.

Replaces the two bare/simplified wall neon signs in `promo/scenes/scene_gym.blend`
with authentic hand-bent glass neon assemblies modeled directly from Kyungmin's
9 real-world gym reference photos (`work/refs/neon_signs_20261125/*.jpg`):

  1. Left Wall Sign (`Left Wall Handwriting`: "넌 운동할 때 / 젤 예뻐" + kettlebell)
  2. Back Mirror Wall Sign (`SET_DECOR`: "운동은! / 워치코치에서" + blue bicep)

Preserves the exact text, position, size, and color of both existing signs by
reading their live world-space splines from the scene, then builds:
  - Uniform blown-glass neon tubes with smooth 90-degree rear return bends
  - Glossy black block-out painted glass jumper bridges between strokes
  - Matte-black heat-shrink / silicone electrode boots at glass section ends
  - Slim matte-black steel flat-bar skeleton frame (horizontal rails + 2 vertical
    uprights) with zinc Phillips wall-mounting screws and spacers
  - Black tube-support posts with U-cradles and bare copper tie-wire loops
  - Compact Korean electronic neon transformer ("전자식 네온관용 변압기" MSA 1)
    with side mounting flanges, Phillips screws, red push-button breaker, rubber
    strain-relief grommets, and a packed vertical Korean technical nameplate
  - High-voltage silicone output leads, inter-section jumpers, P-clips, and a
    grounded AC power cord
  - Core-to-rim Fresnel/LayerWeight neon glass shaders and shadowless soft wall
    bounce lights (zero shadow-buffer impact)

100% idempotent and self-contained (zero external asset files required).
Touches ONLY the two neon signs (hides original raw sign objects and builds
everything inside `SET / DETAIL7_neon_signs`).

Standalone usage (never saves unless `--save <path>` is passed):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail7_neon_signs.py [-- --save out.blend]
"""
from __future__ import annotations

import argparse
import base64
import math
import os
import sys
import tempfile
from dataclasses import dataclass, field

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import interpolate_bezier

KEY = "detail7_neon_signs"
COLL = "DETAIL7_neon_signs"
PFX = "D7neon_"

# Compact 260x460 8-color PNG of the vertical Korean electronic neon transformer
# technical nameplate ("전자식 네온관용 변압기 / MSA 1 / 220V -> 15000V 20mA 85W").
_NAMEPLATE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAQQAAAHMCAIAAAC80UGEAABqMUlEQVR42u1deVhM7Rt+ZqYd7YtEZcu+b5FCUqmU0oKo"
    "pEXRol22EG1SyJ4lpCRFKCWkZE3ZS0RJlpI2tM7M74/D/OZrnWnW9N7Xd33X6TTPTM4597zL8zz3jRMWFgUEBAQAPLoE"
    "CAiIDAgIiAwICIgMCAiIDAgIiAwICIgMCAiIDAgIiAwICIgMCAiIDAgIzAQPLS9KTk5AVwqhR0NHxwiNDAgITB0ZaOcW"
    "AgK3gfZ5DRoZEBAQGRAQEBkQEBAZEBB6LBnQlu6/ulRFZEBAQGRAQEBkQEBAZEBAQGRAQEBkQEBAZEBAQGRAQEBkQEBA"
    "ZEBAQGRAQEBkQEBAZEBAQGRAQEBkQEAAJAiA0KtQWPiS8TdRUhqLRgYEBDRNQkBAZEBAQGRAQEBkQEBAZEBAQGRAQEBA"
    "ZEBAQGRAQEBkQEBAZEBAQGRAQEBkQEBAZEBAQGRAQEBkQEBAZEBAQGRAYApSU280NjZixzU1NevWuc6bp+Xru7mu7ici"
    "A0LvwvbtuwgEAgCQSCQHB+ecnCeGhvqPHuX4+wcgMiD0LggI8PPw8ADA2bMxubl5Bw/uc3Ze6+vrnZp6A5AgAEKvgqSk"
    "xLlz5/v27bN7957ly5dOnjwJAISF+zU1NZHJZBwOh8iA0FuwcaOPra1jVVXV9OlTvbzcsZMFBW9GjFDqVUxAZECA8ePH"
    "ZWamf/nyVV5+EB7/Z9q8ZImRru5CtGZA6HXg5+dXVFSgMAEABAUFamvrEBkQehesre1qamqoz5DJ5NOnoxctMkRkQOhd"
    "KC+vMDQ0LSh4g/346VOZhYV1QEDQ6tWrEBkQehfi4qJHjRppZmZ+5cq12Ng4PT3Diorv589Hu7isA7S1itCrICQkFBER"
    "HhFxyMPDh0wmr1xp7uXlxs/PD0h4GKG3ISUllUQiDRkyWFd34dWryW/fvktPvwUAeDx+4UItRAaEXgRXVw8ymUz58cGD"
    "hw8ePAQAHA6HyIDQu/D69TMAcnu/wQGaJiH0KhAIaBMF0G4SAgIiAwICIgMCAiIDAgIiAwICIgMCAqCtVQTofa61aGRA"
    "QEBkQEBAZEBAQGRAQEBkQEBAZEBAQGRAQEBkQEBAZEBAQGRAQEBkQEBAZEBAQGRAQEBk6JWYOnUKB8MRAJVwAxcYfxgZ"
    "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"
)


# ---------------------------------------------------------------------------
# Sign local coordinate frame: world = origin + u*right + v*up + d*normal
# ---------------------------------------------------------------------------

@dataclass
class SignFrame:
    origin: Vector   # reference point on wall face (d = 0)
    right: Vector    # reading direction (+u), unit
    up: Vector       # world +Z (+v), unit
    normal: Vector   # outward from wall (+d), unit

    def world(self, u: float, v: float, d: float) -> Vector:
        return self.origin + self.right * u + self.up * v + self.normal * d

    def local(self, p: Vector) -> tuple[float, float, float]:
        rel = p - self.origin
        return (rel.dot(self.right), rel.dot(self.up), rel.dot(self.normal))

    def rot_matrix(self) -> Matrix:
        # Columns: right (X), normal (Y), up (Z) -> det = (right x normal) . up
        # Ensure right-handed basis: right x up = -normal, so (right, -normal, up) or (right, up, normal)
        # Note: right x up = -normal (since looking at sign from +normal, right is +X, up is +Y, +normal is +Z)
        # Wait: for LeftWall: right=(0,1,0), up=(0,0,1), right x up = (1,0,0) = +normal!
        # For BackWall: right=(1,0,0), up=(0,0,1), right x up = (0,-1,0) = +normal!
        # Both are right-handed with X=right, Y=up, Z=normal!
        return Matrix((
            (self.right.x, self.up.x, self.normal.x, 0.0),
            (self.right.y, self.up.y, self.normal.y, 0.0),
            (self.right.z, self.up.z, self.normal.z, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ))


@dataclass
class Stroke2D:
    pts: list[tuple[float, float]]   # (u, v) in local sign coordinates
    color_key: str                   # "pink", "blue", "white"
    cyclic: bool = False
    group: str = ""                  # e.g. "top", "bottom", "icon"


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def _get_or_new_mat(name: str) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m["detail7_pkg"] = KEY
    return m


def _clear_and_principled(m: bpy.types.Material):
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (520, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (180, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return nt, bsdf, out


def _neon_glass_mat(
    name: str,
    base_rgb: tuple[float, float, float],
    core_rgb: tuple[float, float, float],
    mid_rgb: tuple[float, float, float],
    rim_rgb: tuple[float, float, float],
    core_strength: float,
    rim_strength: float,
) -> bpy.types.Material:
    """Core-to-rim glowing blown glass neon material tuned for AgX EEVEE."""
    m = _get_or_new_mat(PFX + name)
    nt, bsdf, _ = _clear_and_principled(m)
    m.diffuse_color = (*mid_rgb, 1.0)

    bsdf.inputs["Base Color"].default_value = (*base_rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.14
    bsdf.inputs["Specular IOR Level"].default_value = 0.55
    bsdf.inputs["Coat Weight"].default_value = 0.65
    bsdf.inputs["Coat Roughness"].default_value = 0.06

    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.45
    lw.location = (-440, 60)

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-160, 120)
    elts = ramp.color_ramp.elements
    elts[0].position = 0.18
    elts[0].color = (*core_rgb, 1.0)
    elts[1].position = 0.86
    elts[1].color = (*rim_rgb, 1.0)
    mid = elts.new(0.54)
    mid.color = (*mid_rgb, 1.0)

    strength_map = nt.nodes.new("ShaderNodeMapRange")
    strength_map.location = (-160, -140)
    strength_map.clamp = True
    strength_map.inputs["From Min"].default_value = 0.10
    strength_map.inputs["From Max"].default_value = 0.90
    strength_map.inputs["To Min"].default_value = core_strength
    strength_map.inputs["To Max"].default_value = rim_strength

    nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    nt.links.new(lw.outputs["Facing"], strength_map.inputs["Value"])
    nt.links.new(strength_map.outputs["Result"], bsdf.inputs["Emission Strength"])
    return m


def _noisy_pbr_mat(
    name: str,
    base_rgb: tuple[float, float, float],
    rough: float,
    metal: float = 0.0,
    spec: float = 0.45,
    coat: float = 0.0,
    coat_rough: float = 0.06,
    noise_scale: float = 0.0,
    bump_strength: float = 0.0,
    bump_dist: float = 0.0005,
    rough_var: float = 0.0,
) -> bpy.types.Material:
    m = _get_or_new_mat(PFX + name)
    nt, bsdf, _ = _clear_and_principled(m)
    m.diffuse_color = (*base_rgb, 1.0)
    bsdf.inputs["Base Color"].default_value = (*base_rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Specular IOR Level"].default_value = spec
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Coat Roughness"].default_value = coat_rough

    if noise_scale > 0.0 and (bump_strength > 0.0 or rough_var > 0.0):
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.location = (-540, -140)
        ns = nt.nodes.new("ShaderNodeTexNoise")
        ns.location = (-340, -140)
        ns.inputs["Scale"].default_value = noise_scale
        ns.inputs["Detail"].default_value = 5.0
        nt.links.new(tc.outputs["Object"], ns.inputs["Vector"])

        if bump_strength > 0.0:
            bmp = nt.nodes.new("ShaderNodeBump")
            bmp.location = (-80, -220)
            bmp.inputs["Strength"].default_value = bump_strength
            bmp.inputs["Distance"].default_value = bump_dist
            nt.links.new(ns.outputs["Fac"], bmp.inputs["Height"])
            nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])

        if rough_var > 0.0:
            mr = nt.nodes.new("ShaderNodeMapRange")
            mr.location = (-80, -40)
            mr.clamp = True
            mr.inputs["From Min"].default_value = 0.25
            mr.inputs["From Max"].default_value = 0.75
            mr.inputs["To Min"].default_value = max(0.02, rough - rough_var)
            mr.inputs["To Max"].default_value = min(0.98, rough + rough_var)
            nt.links.new(ns.outputs["Fac"], mr.inputs["Value"])
            nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
    return m


def _nameplate_mat() -> bpy.types.Material:
    img_name = PFX + "TransformerNameplate.png"
    old_img = bpy.data.images.get(img_name)
    if old_img is not None:
        bpy.data.images.remove(old_img)

    raw = base64.b64decode(_NAMEPLATE_PNG_B64)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="d7neon_np_", suffix=".png")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(raw)
        img = bpy.data.images.load(tmp_path, check_existing=False)
        img.name = img_name
        img.pack()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    m = _get_or_new_mat(PFX + "Nameplate")
    nt, bsdf, _ = _clear_and_principled(m)
    m.diffuse_color = (0.08, 0.08, 0.09, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.30
    bsdf.inputs["Specular IOR Level"].default_value = 0.45
    bsdf.inputs["Coat Weight"].default_value = 0.28
    bsdf.inputs["Coat Roughness"].default_value = 0.16

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-220, 80)
    tex.image = img
    tex.extension = "CLIP"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.nodes.active = tex
    return m


def _build_materials() -> dict[str, bpy.types.Material]:
    return {
        # Tuned for Blender AgX: saturated RGB emission rolls off naturally to a creamy
        # pastel-white core with a vivid hot-magenta / electric-blue outer rim.
        "pink": _neon_glass_mat(
            "GlassPink",
            base_rgb=(1.0, 0.16, 0.48),
            core_rgb=(1.0, 0.14, 0.48),
            mid_rgb=(1.0, 0.032, 0.36),
            rim_rgb=(1.0, 0.008, 0.26),
            core_strength=18.0,
            rim_strength=8.5,
        ),
        "blue": _neon_glass_mat(
            "GlassBlue",
            base_rgb=(0.04, 0.30, 1.0),
            core_rgb=(0.04, 0.34, 1.0),
            mid_rgb=(0.012, 0.16, 1.0),
            rim_rgb=(0.004, 0.055, 1.0),
            core_strength=18.0,
            rim_strength=9.0,
        ),
        "white": _neon_glass_mat(
            "GlassWhite",
            base_rgb=(0.94, 0.98, 1.0),
            core_rgb=(0.98, 0.995, 1.0),
            mid_rgb=(0.86, 0.94, 1.0),
            rim_rgb=(0.68, 0.85, 1.0),
            core_strength=12.5,
            rim_strength=6.5,
        ),
        # Glossy black block-out paint on bent rear glass return tubes
        "blackout": _noisy_pbr_mat(
            "BlackoutGlass",
            base_rgb=(0.004, 0.004, 0.005),
            rough=0.09,
            metal=0.0,
            spec=0.68,
            coat=1.0,
            coat_rough=0.04,
        ),
        # Matte-satin black powder-coated flat steel bars
        "steel": _noisy_pbr_mat(
            "SteelFrame",
            base_rgb=(0.014, 0.014, 0.016),
            rough=0.42,
            metal=0.42,
            spec=0.48,
            noise_scale=220.0,
            bump_strength=0.06,
            bump_dist=0.0004,
            rough_var=0.06,
        ),
        # Matte black heat-shrink / silicone rubber electrode boots & HV cables
        "rubber": _noisy_pbr_mat(
            "RubberBoot",
            base_rgb=(0.010, 0.010, 0.012),
            rough=0.64,
            metal=0.0,
            spec=0.28,
            noise_scale=380.0,
            bump_strength=0.14,
            bump_dist=0.00035,
            rough_var=0.05,
        ),
        # Fine-pebbled matte-satin black molded ABS electronic transformer box
        "abs": _noisy_pbr_mat(
            "TransformerABS",
            base_rgb=(0.017, 0.017, 0.019),
            rough=0.37,
            metal=0.0,
            spec=0.45,
            coat=0.08,
            coat_rough=0.35,
            noise_scale=620.0,
            bump_strength=0.12,
            bump_dist=0.00025,
            rough_var=0.05,
        ),
        # Crimson red circuit breaker push-button on transformer left side
        "red_btn": _noisy_pbr_mat(
            "RedButton",
            base_rgb=(0.68, 0.032, 0.032),
            rough=0.26,
            metal=0.0,
            spec=0.55,
            coat=0.35,
            coat_rough=0.14,
        ),
        # Brushed zinc-plated silver steel for Phillips screws & washers
        "zinc": _noisy_pbr_mat(
            "ZincScrew",
            base_rgb=(0.74, 0.75, 0.77),
            rough=0.26,
            metal=0.95,
            spec=0.60,
        ),
        # Bare copper tie wire securing neon glass tubes to support saddles
        "copper": _noisy_pbr_mat(
            "CopperWire",
            base_rgb=(0.78, 0.39, 0.21),
            rough=0.24,
            metal=1.0,
            spec=0.65,
        ),
        # Packed Korean spec sticker on transformer front
        "nameplate": _nameplate_mat(),
    }


# ---------------------------------------------------------------------------
# Clean BMesh primitives (manifold, smooth/flat normals, automatic UVs)
# ---------------------------------------------------------------------------

def _dedupe_pts(pts: list[Vector], min_dist: float = 0.0006) -> list[Vector]:
    out: list[Vector] = []
    for p in pts:
        if not out or (p - out[-1]).length >= min_dist:
            out.append(p.copy())
    return out


def _sweep_tube(
    bm: bmesh.types.BMesh,
    pts: list[Vector],
    radii: float | list[float],
    mat_indices: int | list[int] = 0,
    seg: int = 14,
    cap_start: bool = True,
    cap_end: bool = True,
    round_start: bool = False,
    round_end: bool = False,
) -> None:
    """Sweep a smooth, twist-free (Bishop parallel-transport) manifold tube.

    `mat_indices`: either a single int or a list of length `len(pts) - 1`
    assigning each quad band between ring i and ring i+1 its material slot.
    """
    pts = list(pts)
    n = len(pts)
    if n < 2:
        return

    if isinstance(radii, (int, float)):
        r_list = [float(radii)] * n
    else:
        r_list = list(radii)

    if isinstance(mat_indices, int):
        m_list = [mat_indices] * (n - 1)
    else:
        m_list = list(mat_indices)

    # Optionally prepend/append hemispherical cap rings so ends look blown-round
    if round_start:
        t0 = (pts[1] - pts[0]).normalized()
        r0 = r_list[0]
        m0 = m_list[0]
        extra_pts = [
            pts[0] - t0 * (r0 * 0.92),
            pts[0] - t0 * (r0 * 0.55),
        ]
        extra_r = [r0 * 0.36, r0 * 0.82]
        pts = extra_pts + pts
        r_list = extra_r + r_list
        m_list = [m0, m0] + m_list
        n = len(pts)

    if round_end:
        t1 = (pts[-1] - pts[-2]).normalized()
        r1 = r_list[-1]
        m1 = m_list[-1]
        extra_pts = [
            pts[-1] + t1 * (r1 * 0.55),
            pts[-1] + t1 * (r1 * 0.92),
        ]
        extra_r = [r1 * 0.82, r1 * 0.36]
        pts = pts + extra_pts
        r_list = r_list + extra_r
        m_list = m_list + [m1, m1]
        n = len(pts)

    # Compute tangents at every point
    tangents: list[Vector] = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t_prev = (pts[i] - pts[i - 1])
            t_next = (pts[i + 1] - pts[i])
            if t_prev.length > 1e-8:
                t_prev.normalize()
            if t_next.length > 1e-8:
                t_next.normalize()
            t = t_prev + t_next
            if t.length < 1e-6:
                t = t_next if t_next.length > 1e-8 else Vector((0, 0, 1))
        if t.length < 1e-8:
            t = Vector((1, 0, 0))
        tangents.append(t.normalized())

    # Initial Bishop frame
    t0 = tangents[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    n_vec = t0.cross(ref).normalized()
    b_vec = t0.cross(n_vec).normalized()

    # Build in an isolated temporary bmesh so normals are guaranteed outward per island
    tmp = bmesh.new()
    rings: list[list[bmesh.types.BMVert]] = []
    for i in range(n):
        ti = tangents[i]
        if i > 0:
            t_prev = tangents[i - 1]
            axis = t_prev.cross(ti)
            if axis.length > 1e-7:
                angle = math.atan2(axis.length, max(-1.0, min(1.0, t_prev.dot(ti))))
                rot = Matrix.Rotation(angle, 3, axis.normalized())
                n_vec = (rot @ n_vec).normalized()
            # Re-orthogonalize
            n_vec = (n_vec - ti * n_vec.dot(ti))
            if n_vec.length < 1e-6:
                ref = Vector((0, 0, 1)) if abs(ti.z) < 0.9 else Vector((1, 0, 0))
                n_vec = ti.cross(ref).normalized()
            else:
                n_vec.normalize()
            b_vec = ti.cross(n_vec).normalized()

        ring = []
        ri = r_list[i]
        ci = pts[i]
        for k in range(seg):
            ang = 2.0 * math.pi * k / seg
            pos = ci + (n_vec * math.cos(ang) + b_vec * math.sin(ang)) * ri
            ring.append(tmp.verts.new(pos))
        rings.append(ring)

    # Connect rings into smooth quads
    for i in range(n - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        mi = m_list[i]
        for k in range(seg):
            kn = (k + 1) % seg
            try:
                f = tmp.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
                f.smooth = True
                f.material_index = mi
            except ValueError:
                pass

    if cap_start:
        c0 = tmp.verts.new(pts[0])
        r0 = rings[0]
        m0 = m_list[0]
        for k in range(seg):
            kn = (k + 1) % seg
            try:
                f = tmp.faces.new((r0[kn], r0[k], c0))
                f.smooth = round_start
                f.material_index = m0
            except ValueError:
                pass

    if cap_end:
        c1 = tmp.verts.new(pts[-1])
        r1 = rings[-1]
        m1 = m_list[-1]
        for k in range(seg):
            kn = (k + 1) % seg
            try:
                f = tmp.faces.new((r1[k], r1[kn], c1))
                f.smooth = round_end
                f.material_index = m1
            except ValueError:
                pass

    bmesh.ops.recalc_face_normals(tmp, faces=list(tmp.faces))
    _copy_bm_into(tmp, bm)
    tmp.free()


def _copy_bm_into(src: bmesh.types.BMesh, dst: bmesh.types.BMesh) -> None:
    """Copy a finalized, strictly outward-oriented temporary bmesh into dst."""
    bmesh.ops.recalc_face_normals(src, faces=list(src.faces))
    if src.calc_volume(signed=True) < 0.0:
        bmesh.ops.reverse_faces(src, faces=list(src.faces))
    src.verts.ensure_lookup_table()
    src.verts.index_update()
    vmap = {v.index: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v.index] for v in f.verts])
            nf.smooth = f.smooth
            nf.material_index = f.material_index
        except ValueError:
            pass


def _add_local_box(
    bm: bmesh.types.BMesh,
    frame: SignFrame,
    u: float,
    v: float,
    d: float,
    su: float,
    sv: float,
    sd: float,
    mat_idx: int,
    bevel: float = 0.0,
    bevel_seg: int = 2,
) -> None:
    """Create a box in sign local coordinates (u, v, d) with optional bevel."""
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    bmesh.ops.scale(tmp, vec=Vector((su, sv, sd)), verts=tmp.verts)
    if bevel > 0.0:
        bmesh.ops.bevel(
            tmp,
            geom=list(tmp.edges),
            offset=bevel,
            segments=bevel_seg,
            affect="EDGES",
            profile=0.5,
            clamp_overlap=True,
        )
    xform = Matrix.Translation(frame.world(u, v, d)) @ frame.rot_matrix()
    bmesh.ops.transform(tmp, matrix=xform, verts=tmp.verts)
    bmesh.ops.recalc_face_normals(tmp, faces=list(tmp.faces))
    for face in tmp.faces:
        face.smooth = False
        face.material_index = mat_idx
    _copy_bm_into(tmp, bm)
    tmp.free()


def _add_cyl_between(
    bm: bmesh.types.BMesh,
    p0: Vector,
    p1: Vector,
    r0: float,
    r1: float,
    mat_idx: int,
    seg: int = 12,
    cap_ends: bool = True,
) -> None:
    vec = p1 - p0
    length = vec.length
    if length < 1e-6:
        return
    tmp = bmesh.new()
    bmesh.ops.create_cone(
        tmp,
        cap_ends=cap_ends,
        cap_tris=True,
        segments=seg,
        radius1=r0,
        radius2=r1,
        depth=length,
    )
    q = vec.normalized().to_track_quat("Z", "Y")
    xform = Matrix.Translation((p0 + p1) * 0.5) @ q.to_matrix().to_4x4()
    bmesh.ops.transform(tmp, matrix=xform, verts=tmp.verts)
    bmesh.ops.recalc_face_normals(tmp, faces=list(tmp.faces))
    axis = vec.normalized()
    for face in tmp.faces:
        face.smooth = abs(face.normal.dot(axis)) < 0.55
        face.material_index = mat_idx
    _copy_bm_into(tmp, bm)
    tmp.free()


def _add_revolved_profile(
    bm: bmesh.types.BMesh,
    frame: SignFrame,
    u: float,
    v: float,
    profile_dr: list[tuple[float, float]],
    mat_idx: int,
    seg: int = 14,
) -> None:
    """Single watertight revolved solid around local +normal axis with zero internal coplanar caps."""
    tmp = bmesh.new()
    rings = []
    for d_val, r_val in profile_dr:
        ring = []
        for k in range(seg):
            ang = 2.0 * math.pi * k / seg
            pos = frame.world(u + r_val * math.cos(ang), v + r_val * math.sin(ang), d_val)
            ring.append(tmp.verts.new(pos))
        rings.append(ring)

    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        is_flat = abs(profile_dr[i][0] - profile_dr[i + 1][0]) < 1e-5
        for k in range(seg):
            kn = (k + 1) % seg
            f = tmp.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
            f.smooth = not is_flat
            f.material_index = mat_idx

    # Bottom and top triangle fan caps
    c_bot = tmp.verts.new(frame.world(u, v, profile_dr[0][0]))
    c_top = tmp.verts.new(frame.world(u, v, profile_dr[-1][0]))
    for k in range(seg):
        kn = (k + 1) % seg
        fb = tmp.faces.new((rings[0][kn], rings[0][k], c_bot))
        fb.smooth = False
        fb.material_index = mat_idx
        ft = tmp.faces.new((rings[-1][k], rings[-1][kn], c_top))
        ft.smooth = False
        ft.material_index = mat_idx

    bmesh.ops.recalc_face_normals(tmp, faces=list(tmp.faces))
    _copy_bm_into(tmp, bm)
    tmp.free()


def _add_phillips_screw(
    bm: bmesh.types.BMesh,
    frame: SignFrame,
    u: float,
    v: float,
    d_base: float,
    head_r: float = 0.0042,
    head_h: float = 0.0024,
    washer_r: float = 0.0066,
    washer_h: float = 0.0010,
    zinc_idx: int = 0,
    slot_idx: int = 1,
) -> None:
    """Single-piece pan-head zinc Phillips screw with washer and non-overlapping recessed cross."""
    # Single continuous revolved solid (zero stacked coplanar caps!)
    # Slight 0.4mm embed at base prevents back-to-back coplanar touch with mounting plate
    d_start = d_base - 0.0004
    d_w_top = d_base + washer_h
    d_h_mid = d_w_top + head_h * 0.62
    d_h_top = d_w_top + head_h
    profile = [
        (d_start, washer_r),
        (d_w_top, washer_r),
        (d_w_top + 0.0001, head_r),
        (d_h_mid, head_r * 0.94),
        (d_h_top, head_r * 0.56),
    ]
    _add_revolved_profile(bm, frame, u, v, profile, zinc_idx, seg=14)

    # Single watertight 12-vertex '+' prism proud of head top by 0.25mm (zero self-overlap!)
    arm = head_r * 0.52
    half_t = head_r * 0.12
    d0 = d_h_top - 0.00015
    d1 = d_h_top + 0.00028
    # 12 perimeter points of a '+' shape in CCW order
    poly_2d = [
        (-half_t, -arm), (half_t, -arm),
        (half_t, -half_t), (arm, -half_t),
        (arm, half_t), (half_t, half_t),
        (half_t, arm), (-half_t, arm),
        (-half_t, half_t), (-arm, half_t),
        (-arm, -half_t), (-half_t, -half_t),
    ]
    tmp = bmesh.new()
    bot_v = [tmp.verts.new(frame.world(u + pu, v + pv, d0)) for pu, pv in poly_2d]
    top_v = [tmp.verts.new(frame.world(u + pu, v + pv, d1)) for pu, pv in poly_2d]
    m_n = len(poly_2d)
    for k in range(m_n):
        kn = (k + 1) % m_n
        f = tmp.faces.new((bot_v[k], bot_v[kn], top_v[kn], top_v[k]))
        f.smooth = False
        f.material_index = slot_idx
    # Triangulate top & bottom '+' into clean quads (5 quads each: center + 4 arms)
    # Center quad uses inner corners indices 2, 5, 8, 11
    for verts_ring, rev in ((top_v, False), (bot_v, True)):
        quads = [
            (verts_ring[11], verts_ring[2], verts_ring[5], verts_ring[8]),
            (verts_ring[0], verts_ring[1], verts_ring[2], verts_ring[11]),
            (verts_ring[2], verts_ring[3], verts_ring[4], verts_ring[5]),
            (verts_ring[8], verts_ring[5], verts_ring[6], verts_ring[7]),
            (verts_ring[9], verts_ring[10], verts_ring[11], verts_ring[8]),
        ]
        for q in quads:
            f = tmp.faces.new(tuple(reversed(q)) if rev else q)
            f.smooth = False
            f.material_index = slot_idx
    bmesh.ops.recalc_face_normals(tmp, faces=list(tmp.faces))
    _copy_bm_into(tmp, bm)
    tmp.free()


def _assign_box_uvs(bm: bmesh.types.BMesh, scale: float = 4.0) -> None:
    """Assign clean tri-planar box UVs to faces that have zero/unset UVs."""
    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        has_uv = any(loop[uv_layer].uv.length_squared > 1e-8 for loop in f.loops)
        if has_uv:
            continue
        nx, ny, nz = abs(f.normal.x), abs(f.normal.y), abs(f.normal.z)
        for loop in f.loops:
            co = loop.vert.co
            if nx >= ny and nx >= nz:
                loop[uv_layer].uv = (co.y * scale, co.z * scale)
            elif ny >= nx and ny >= nz:
                loop[uv_layer].uv = (co.x * scale, co.z * scale)
            else:
                loop[uv_layer].uv = (co.x * scale, co.y * scale)


def _finalize_mesh(
    coll: bpy.types.Collection,
    name: str,
    bm: bmesh.types.BMesh,
    mats: list[bpy.types.Material],
    parent: bpy.types.Object | None = None,
) -> bpy.types.Object:
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=list(bm.edges))
    # Do NOT run global recalc_face_normals across disconnected islands — each island is
    # already oriented outward in its own temporary bmesh before merging.
    _assign_box_uvs(bm)
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    for mat in mats:
        me.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, me)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


# ---------------------------------------------------------------------------
# Extract existing strokes cleanly from the scene's original curves
# ---------------------------------------------------------------------------

def _sample_spline_world(
    ob: bpy.types.Object,
    spline: bpy.types.Spline,
    steps_per_seg: int = 8,
) -> tuple[list[Vector], bool]:
    mw = ob.matrix_world
    pts: list[Vector] = []
    if spline.type == "BEZIER":
        bps = spline.bezier_points
        count = len(bps)
        if count < 2:
            return [], False
        seg_count = count if spline.use_cyclic_u else count - 1
        for i in range(seg_count):
            p0 = bps[i]
            p1 = bps[(i + 1) % count]
            w0 = mw @ p0.co
            hr = mw @ p0.handle_right
            hl = mw @ p1.handle_left
            w1 = mw @ p1.co
            seg_pts = interpolate_bezier(w0, hr, hl, w1, steps_per_seg)
            if pts:
                pts.extend(seg_pts[1:])
            else:
                pts.extend(seg_pts)
        return _dedupe_pts(pts, 0.0012), bool(spline.use_cyclic_u)
    else:
        raw = [mw @ Vector(p.co[:3]) for p in spline.points]
        if spline.use_cyclic_u and raw:
            raw.append(raw[0].copy())
        return _dedupe_pts(raw, 0.0012), bool(spline.use_cyclic_u)


def _open_cyclic_loop_2d(
    pts: list[tuple[float, float]],
    gap: float,
    preferred_angle_deg: float = -35.0,
) -> list[tuple[float, float]]:
    """Open a closed 2D loop with a realistic glass-bender gap."""
    if len(pts) < 6:
        return pts
    # Remove duplicate closing point if present
    if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-4:
        pts = pts[:-1]
    n = len(pts)
    cu = sum(p[0] for p in pts) / n
    cv = sum(p[1] for p in pts) / n
    target_rad = math.radians(preferred_angle_deg)

    # Pick vertex closest to preferred angle from loop centroid
    def ang_diff(p):
        a = math.atan2(p[1] - cv, p[0] - cu)
        d = (a - target_rad + math.pi) % (2.0 * math.pi) - math.pi
        return abs(d)

    split_idx = min(range(n), key=lambda i: ang_diff(pts[i]))
    ordered = pts[split_idx:] + pts[:split_idx] + [pts[split_idx]]

    # Trim half-gap off both ends along arc length
    half = gap * 0.5
    def trim_front(seq, dist):
        acc = 0.0
        for i in range(len(seq) - 1):
            du = seq[i + 1][0] - seq[i][0]
            dv = seq[i + 1][1] - seq[i][1]
            seg_l = math.hypot(du, dv)
            if acc + seg_l >= dist and seg_l > 1e-6:
                t = (dist - acc) / seg_l
                p_new = (seq[i][0] + du * t, seq[i][1] + dv * t)
                return [p_new] + seq[i + 1:]
            acc += seg_l
        return seq

    trimmed = trim_front(ordered, half)
    trimmed = list(reversed(trim_front(list(reversed(trimmed)), half)))
    return trimmed if len(trimmed) >= 3 else ordered


def _polyline_length_2d(pts: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        for i in range(len(pts) - 1)
    )


def _trim_ends_2d(
    pts: list[tuple[float, float]], trim_dist: float
) -> list[tuple[float, float]]:
    if len(pts) < 2 or trim_dist <= 0.0:
        return pts
    total = _polyline_length_2d(pts)
    if total <= 2.6 * trim_dist:
        trim_dist = total * 0.18

    def trim_one(seq, d):
        acc = 0.0
        for i in range(len(seq) - 1):
            du = seq[i + 1][0] - seq[i][0]
            dv = seq[i + 1][1] - seq[i][1]
            seg_l = math.hypot(du, dv)
            if acc + seg_l >= d and seg_l > 1e-6:
                t = (d - acc) / seg_l
                return [(seq[i][0] + du * t, seq[i][1] + dv * t)] + seq[i + 1:]
            acc += seg_l
        return seq

    out = trim_one(pts, trim_dist)
    out = list(reversed(trim_one(list(reversed(out)), trim_dist)))
    return out if len(out) >= 2 else pts


def _sample_bezier_3d(
    p0: Vector, p1: Vector, p2: Vector, p3: Vector, steps: int = 12
) -> list[Vector]:
    out = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        p = (
            p0 * (mt ** 3)
            + p1 * (3.0 * mt * mt * t)
            + p2 * (3.0 * mt * t * t)
            + p3 * (t ** 3)
        )
        out.append(p)
    return out


def _catmull_rom_3d(ctrl: list[Vector], steps_per_seg: int = 8) -> list[Vector]:
    if len(ctrl) <= 2:
        return list(ctrl)
    pts = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out: list[Vector] = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(steps_per_seg):
            t = s / steps_per_seg
            t2 = t * t
            t3 = t2 * t
            v = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            out.append(v)
    out.append(ctrl[-1])
    return _dedupe_pts(out, 0.001)


# ---------------------------------------------------------------------------
# Core neon sign builder (unified for both Left Wall & Back Mirror Wall)
# ---------------------------------------------------------------------------

def _order_strokes_for_bending(strokes: list[Stroke2D]) -> list[Stroke2D]:
    """Cluster strokes into Korean characters left-to-right, then chain within each character
    so black-out glass jumpers only bridge local strokes and adjacent characters."""
    if len(strokes) <= 1:
        return list(strokes)

    # Group strokes whose horizontal [u_min, u_max] intervals overlap (within small margin)
    spans = sorted(
        [(min(p[0] for p in s.pts), max(p[0] for p in s.pts), s) for s in strokes],
        key=lambda x: x[0],
    )
    clusters: list[list[Stroke2D]] = []
    cur_u1 = -1e9
    for u0, u1, st in spans:
        if not clusters or u0 > cur_u1 + 0.014:
            clusters.append([st])
            cur_u1 = u1
        else:
            clusters[-1].append(st)
            cur_u1 = max(cur_u1, u1)

    ordered: list[Stroke2D] = []
    for cl in clusters:
        rem = list(cl)
        if not ordered:
            # Start with leftmost stroke of first character
            rem.sort(key=lambda s: min(p[0] for p in s.pts))
            first = rem.pop(0)
            if first.pts[0][0] > first.pts[-1][0]:
                first = Stroke2D(list(reversed(first.pts)), first.color_key, False, first.group)
            ordered.append(first)
        while rem:
            cur_end = ordered[-1].pts[-1]
            best_i = 0
            best_flip = False
            best_d = 1e9
            for i, st in enumerate(rem):
                d_s = math.hypot(st.pts[0][0] - cur_end[0], st.pts[0][1] - cur_end[1])
                d_e = math.hypot(st.pts[-1][0] - cur_end[0], st.pts[-1][1] - cur_end[1])
                if d_s < best_d:
                    best_d, best_i, best_flip = d_s, i, False
                if d_e < best_d:
                    best_d, best_i, best_flip = d_e, i, True
            chosen = rem.pop(best_i)
            if best_flip:
                chosen = Stroke2D(list(reversed(chosen.pts)), chosen.color_key, False, chosen.group)
            ordered.append(chosen)
    return ordered


def _build_section_tubes_and_boots(
    bm_tubes: bmesh.types.BMesh,
    bm_cables: bmesh.types.BMesh,
    frame: SignFrame,
    strokes: list[Stroke2D],
    r_tube: float,
    d_front: float,
    d_back: float,
    glow_mat_idx: int,
    blackout_mat_idx: int,
    boot_mat_idx: int,
    boot_dir_start: tuple[float, float],
    boot_dir_end: tuple[float, float],
    seg: int = 12,
) -> tuple[tuple[Vector, Vector], tuple[Vector, Vector]]:
    """Build one continuous bent-glass neon section:
    glowing strokes + smooth 90-deg rear return bends + glossy black-out jumpers +
    matte-black silicone electrode boots at both electrical ends.

    Returns ((boot_start_exit_pos, boot_start_dir), (boot_end_exit_pos, boot_end_dir)).
    """
    ordered = _order_strokes_for_bending(strokes)
    r_bend = min(0.013, 1.65 * r_tube)
    # Keep rear bend depth clear of front plane by at least r_bend
    d_rear = min(d_back, d_front - r_bend - 0.008)

    rear_entries: list[tuple[float, float, float, float]] = []  # (u, v, tu_out, tv_out)
    rear_exits: list[tuple[float, float, float, float]] = []

    for st in ordered:
        pts2 = st.pts
        if len(pts2) < 2:
            continue
        length = _polyline_length_2d(pts2)
        local_rb = min(r_bend, max(0.004, length * 0.32))
        trimmed = _trim_ends_2d(pts2, local_rb * 0.55)
        if len(trimmed) < 2:
            trimmed = pts2

        # Outward unit tangents in (u, v) at start and end
        du0 = trimmed[0][0] - trimmed[1][0]
        dv0 = trimmed[0][1] - trimmed[1][1]
        l0 = math.hypot(du0, dv0) or 1.0
        tu0, tv0 = du0 / l0, dv0 / l0

        du1 = trimmed[-1][0] - trimmed[-2][0]
        dv1 = trimmed[-1][1] - trimmed[-2][1]
        l1 = math.hypot(du1, dv1) or 1.0
        tu1, tv1 = du1 / l1, dv1 / l1

        # Build continuous path:
        # rear_start (d_rear) -> 90-deg forward arc -> front glowing stroke ->
        # 90-deg backward arc -> rear_end (d_rear)
        arc_steps = 6
        start_arc: list[Vector] = []
        start_mats: list[int] = []
        # Straight rear stub into start arc
        u_s_rear = trimmed[0][0] + tu0 * local_rb
        v_s_rear = trimmed[0][1] + tv0 * local_rb
        start_arc.append(frame.world(u_s_rear, v_s_rear, d_rear))
        for k in range(arc_steps + 1):
            # theta goes 90 deg (rear) -> 0 deg (front stroke start)
            theta = math.radians(90.0 * (1.0 - k / arc_steps))
            u = trimmed[0][0] + tu0 * local_rb * math.sin(theta)
            v = trimmed[0][1] + tv0 * local_rb * math.sin(theta)
            d = d_front - local_rb * (1.0 - math.cos(theta))
            start_arc.append(frame.world(u, v, d))
            # Switch from black-out paint to glowing phosphor at ~42 deg
            if k == 0:
                start_mats.append(blackout_mat_idx)
            else:
                mid_deg = 90.0 * (1.0 - (k - 0.5) / arc_steps)
                start_mats.append(glow_mat_idx if mid_deg <= 42.0 else blackout_mat_idx)

        front_pts = [frame.world(u, v, d_front) for (u, v) in trimmed[1:]]
        front_mats = [glow_mat_idx] * len(front_pts)

        end_arc: list[Vector] = []
        end_mats: list[int] = []
        for k in range(1, arc_steps + 1):
            # theta goes 0 deg (front stroke end) -> 90 deg (rear)
            theta = math.radians(90.0 * (k / arc_steps))
            u = trimmed[-1][0] + tu1 * local_rb * math.sin(theta)
            v = trimmed[-1][1] + tv1 * local_rb * math.sin(theta)
            d = d_front - local_rb * (1.0 - math.cos(theta))
            end_arc.append(frame.world(u, v, d))
            mid_deg = 90.0 * ((k - 0.5) / arc_steps)
            end_mats.append(glow_mat_idx if mid_deg <= 42.0 else blackout_mat_idx)

        u_e_rear = trimmed[-1][0] + tu1 * local_rb
        v_e_rear = trimmed[-1][1] + tv1 * local_rb
        end_arc.append(frame.world(u_e_rear, v_e_rear, d_rear))
        end_mats.append(blackout_mat_idx)

        full_pts = start_arc + front_pts + end_arc
        full_mats = start_mats + front_mats + end_mats
        # Filter near-duplicate points while keeping material indices aligned
        clean_pts = [full_pts[0]]
        clean_mats: list[int] = []
        for idx in range(1, len(full_pts)):
            if (full_pts[idx] - clean_pts[-1]).length >= 0.0004:
                clean_pts.append(full_pts[idx])
                clean_mats.append(full_mats[idx - 1])

        _sweep_tube(
            bm_tubes,
            clean_pts,
            r_tube,
            mat_indices=clean_mats,
            seg=seg,
            cap_start=True,
            cap_end=True,
        )
        rear_entries.append((u_s_rear, v_s_rear, tu0, tv0))
        rear_exits.append((u_e_rear, v_e_rear, tu1, tv1))

    # Glossy black-out painted glass jumper bridges linking consecutive strokes at d_rear
    # Offset jumper endpoints +2.2mm into the rear stub so flat end-caps are never coplanar (zero z-fighting!)
    for i in range(len(rear_exits) - 1):
        ua, va, _, _ = rear_exits[i]
        ub, vb, _, _ = rear_entries[i + 1]
        pa = frame.world(ua, va, d_rear + 0.0022)
        pb = frame.world(ub, vb, d_rear + 0.0022)
        dist = (pb - pa).length
        if dist < 0.002:
            continue
        # Slight back-bow so jumper clears adjacent rear stubs cleanly
        bow = min(0.009, 0.003 + dist * 0.06)
        ctrl1 = frame.world(ua + (ub - ua) * 0.28, va + (vb - va) * 0.28, d_rear - bow)
        ctrl2 = frame.world(ua + (ub - ua) * 0.72, va + (vb - va) * 0.72, d_rear - bow)
        j_pts = _sample_bezier_3d(pa, ctrl1, ctrl2, pb, steps=10)
        _sweep_tube(
            bm_tubes,
            j_pts,
            r_tube * 0.90,
            mat_indices=blackout_mat_idx,
            seg=max(10, seg - 2),
            cap_start=True,
            cap_end=True,
        )

    # Electrode boots (matte-black heat-shrink / silicone caps) at the two section ends
    def add_electrode_boot(u: float, v: float, dir_uv: tuple[float, float]) -> tuple[Vector, Vector]:
        du, dv = dir_uv
        dl = math.hypot(du, dv) or 1.0
        du, dv = du / dl, dv / dl
        p_glass0 = frame.world(u, v, d_rear + 0.0024)
        # Black-out glass electrode stem angles gently back & toward cable direction
        dir_w = (frame.right * du + frame.up * dv - frame.normal * 0.22).normalized()
        p_glass1 = p_glass0 + dir_w * 0.020
        _sweep_tube(
            bm_tubes,
            [p_glass0, p_glass1],
            r_tube * 0.92,
            mat_indices=blackout_mat_idx,
            seg=10,
            cap_start=True,
            cap_end=True,
        )
        # Heat-shrink silicone electrode boot overlapping the glass stem and tapering to the HV cable
        r_b = r_tube + 0.0028
        boot_pts = [
            p_glass0 + dir_w * 0.005,
            p_glass0 + dir_w * 0.013,
            p_glass0 + dir_w * 0.029,
            p_glass0 + dir_w * 0.037,
            p_glass0 + dir_w * 0.045,
            p_glass0 + dir_w * 0.052,
        ]
        boot_r = [r_b * 0.96, r_b, r_b * 0.98, r_b * 0.84, r_b * 0.64, 0.0042]
        _sweep_tube(
            bm_cables,
            boot_pts,
            boot_r,
            mat_indices=boot_mat_idx,
            seg=12,
            cap_start=True,
            cap_end=True,
        )
        return boot_pts[-1] - dir_w * 0.002, dir_w

    u0, v0, _, _ = rear_entries[0]
    u1, v1, _, _ = rear_exits[-1]
    term_start = add_electrode_boot(u0, v0, boot_dir_start)
    term_end = add_electrode_boot(u1, v1, boot_dir_end)
    return term_start, term_end


def _add_tube_supports_and_copper_wires(
    bm_supports: bmesh.types.BMesh,
    frame: SignFrame,
    strokes: list[Stroke2D],
    rails: list[tuple[float, float, float]],  # (v_rail, u_min, u_max)
    r_tube: float,
    d_rail_front: float,
    d_front: float,
    steel_idx: int,
    zinc_idx: int,
    copper_idx: int,
    min_spacing: float,
) -> int:
    """Place realistic black tube-support posts with saddles & copper tie-wire loops."""
    placed: list[tuple[float, float]] = []

    for v_rail, r_umin, r_umax in rails:
        # Collect candidate stroke points near this horizontal rail
        cands: list[tuple[float, float, float, float, float]] = []  # (dist_v, u, v, tu, tv)
        for st in strokes:
            pts = st.pts
            for i in range(1, len(pts) - 1):
                u, v = pts[i]
                if u < r_umin + 0.015 or u > r_umax - 0.015:
                    continue
                dv = abs(v - v_rail)
                if dv <= 0.036:
                    du_t = pts[i + 1][0] - pts[i - 1][0]
                    dv_t = pts[i + 1][1] - pts[i - 1][1]
                    tl = math.hypot(du_t, dv_t) or 1.0
                    cands.append((dv, u, v, du_t / tl, dv_t / tl))
        cands.sort(key=lambda x: x[0])

        for dv, u, v, tu, tv in cands:
            if any(math.hypot(u - pu, v - pv) < min_spacing for pu, pv in placed):
                continue
            placed.append((u, v))

            # 1) Mounting foot on horizontal rail + tiny zinc screw head (embedded 0.6mm to avoid coplanar caps)
            _add_local_box(
                bm_supports, frame, u, v_rail, d_rail_front + 0.0011,
                0.012, 0.010, 0.0034, steel_idx, bevel=0.0005, bevel_seg=1,
            )
            _add_cyl_between(
                bm_supports,
                frame.world(u, v_rail, d_rail_front + 0.0014),
                frame.world(u, v_rail, d_rail_front + 0.0044),
                0.0024, 0.0020, zinc_idx, seg=10,
            )

            # 2) Slim tapered black support stem from inside foot to back of glass tube
            p_base = frame.world(u, v_rail, d_rail_front + 0.0012)
            p_saddle = frame.world(u, v, d_front - r_tube - 0.0012)
            _add_cyl_between(
                bm_supports, p_base, p_saddle, 0.0030, 0.0023, steel_idx, seg=10,
            )

            # 3) Small U-cradle cup hugging back half of the glass tube
            t_vec = (frame.right * tu + frame.up * tv).normalized()
            n_perp = frame.normal.cross(t_vec).normalized()
            p_tube = frame.world(u, v, d_front)
            cradle_pts = []
            for k in range(7):
                ang = math.radians(-70.0 + 140.0 * k / 6.0)
                pt = p_tube + (n_perp * math.sin(ang) - frame.normal * math.cos(ang)) * (r_tube + 0.0016)
                cradle_pts.append(pt)
            _sweep_tube(
                bm_supports, cradle_pts, 0.0022, mat_indices=steel_idx, seg=8,
                cap_start=True, cap_end=True,
            )

            # 4) Bare copper tie wire looped snugly around the front of the glass tube!
            wire_pts = []
            r_wire_loop = r_tube + 0.00075
            for k in range(13):
                ang = math.radians(-165.0 + 330.0 * k / 12.0)
                pt = p_tube + (n_perp * math.sin(ang) + frame.normal * math.cos(ang)) * r_wire_loop
                wire_pts.append(pt)
            # Tiny twisted tail tucked behind saddle
            wire_pts.append(p_saddle + n_perp * 0.0035 - frame.normal * 0.002)
            _sweep_tube(
                bm_supports, wire_pts, 0.00068, mat_indices=copper_idx, seg=6,
                cap_start=True, cap_end=True,
            )

    return len(placed)


def _add_transformer(
    bm_tx: bmesh.types.BMesh,
    frame: SignFrame,
    u_cx: float,
    v_cz: float,
    tx_w: float,
    tx_h: float,
    tx_d: float,
    d_upright_front: float,
    abs_idx: int,
    steel_idx: int,
    red_idx: int,
    rubber_idx: int,
    zinc_idx: int,
    np_idx: int,
) -> tuple[Vector, Vector, Vector]:
    """Build authentic Korean electronic neon transformer ("전자식 네온관용 변압기").

    Returns (left_ac_grommet_pos, right_hv_upper_pos, right_hv_lower_pos).
    """
    # 1) Rear steel/ABS mounting flange tabs resting on the 2 vertical uprights
    flange_t = 0.0036
    flange_w = tx_w + 0.044
    flange_h = tx_h * 0.90
    d_flange_c = d_upright_front + flange_t * 0.5 - 0.0004
    _add_local_box(
        bm_tx, frame, u_cx, v_cz, d_flange_c,
        flange_w, flange_h, flange_t, abs_idx, bevel=0.0008, bevel_seg=1,
    )

    # 4 zinc Phillips screws at upper/lower corners of mounting ears — clear of side grommets!
    ear_u = tx_w * 0.5 + 0.012
    ear_v = flange_h * 0.36
    d_flange_front = d_flange_c + flange_t * 0.5
    for su in (-1.0, 1.0):
        for sv in (-1.0, 1.0):
            _add_phillips_screw(
                bm_tx, frame, u_cx + su * ear_u, v_cz + sv * ear_v,
                d_flange_front,
                head_r=0.0040, head_h=0.0024, washer_r=0.0062, washer_h=0.0010,
                zinc_idx=zinc_idx, slot_idx=steel_idx,
            )

    # 2) Molded black ABS body with rounded vertical corners + subtle front lid seam
    # Embed 1.2mm into rear flange so rear face never coplanarly touches flange front
    d_body0 = d_flange_front - 0.0012
    lid_d = 0.012
    base_d = tx_d - lid_d + 0.0012
    # Main rear shell
    _add_local_box(
        bm_tx, frame, u_cx, v_cz, d_body0 + base_d * 0.5,
        tx_w, tx_h, base_d, abs_idx, bevel=0.0055, bevel_seg=3,
    )
    # Recessed seam collar (bridges rear shell into front lid without coplanar end faces)
    _add_local_box(
        bm_tx, frame, u_cx, v_cz, d_body0 + base_d + 0.0005,
        tx_w - 0.0045, tx_h - 0.0045, 0.0046, steel_idx, bevel=0.0005, bevel_seg=1,
    )
    # Slightly domed front lid (starts 1.2mm past rear shell so zero z-fighting with shell front)
    d_lid_start = d_body0 + base_d + 0.0014
    d_front_face = d_lid_start + lid_d
    _add_local_box(
        bm_tx, frame, u_cx, v_cz, d_lid_start + lid_d * 0.5,
        tx_w - 0.0015, tx_h - 0.0015, lid_d, abs_idx, bevel=0.0045, bevel_seg=3,
    )

    # 3) Vertical Korean spec nameplate sticker (closed 1.5mm thin solid plate embedded 0.8mm into front lid
    #    so front sticker face sits 0.7mm proud with ZERO boundary edges and ZERO z-fighting!)
    np_h = tx_h * 0.78
    np_w = np_h * (260.0 / 460.0)
    np_u = u_cx - tx_w * 0.27
    np_d_back = d_front_face - 0.0008
    np_d_front = d_front_face + 0.0012
    tmp_np = bmesh.new()
    b_bl = tmp_np.verts.new(frame.world(np_u - np_w * 0.5, v_cz - np_h * 0.5, np_d_back))
    b_br = tmp_np.verts.new(frame.world(np_u + np_w * 0.5, v_cz - np_h * 0.5, np_d_back))
    b_tr = tmp_np.verts.new(frame.world(np_u + np_w * 0.5, v_cz + np_h * 0.5, np_d_back))
    b_tl = tmp_np.verts.new(frame.world(np_u - np_w * 0.5, v_cz + np_h * 0.5, np_d_back))
    f_bl = tmp_np.verts.new(frame.world(np_u - np_w * 0.5, v_cz - np_h * 0.5, np_d_front))
    f_br = tmp_np.verts.new(frame.world(np_u + np_w * 0.5, v_cz - np_h * 0.5, np_d_front))
    f_tr = tmp_np.verts.new(frame.world(np_u + np_w * 0.5, v_cz + np_h * 0.5, np_d_front))
    f_tl = tmp_np.verts.new(frame.world(np_u - np_w * 0.5, v_cz + np_h * 0.5, np_d_front))
    f_front = tmp_np.faces.new((f_bl, f_br, f_tr, f_tl))
    f_front.material_index = np_idx
    f_back = tmp_np.faces.new((b_tl, b_tr, b_br, b_bl))
    f_back.material_index = abs_idx
    for q in (
        (b_bl, b_br, f_br, f_bl),
        (b_br, b_tr, f_tr, f_br),
        (b_tr, b_tl, f_tl, f_tr),
        (b_tl, b_bl, f_bl, f_tl),
    ):
        fs = tmp_np.faces.new(q)
        fs.material_index = abs_idx
    for f in tmp_np.faces:
        f.smooth = False
    bmesh.ops.recalc_face_normals(tmp_np, faces=list(tmp_np.faces))
    if tmp_np.calc_volume(signed=True) < 0.0:
        bmesh.ops.reverse_faces(tmp_np, faces=list(tmp_np.faces))
    # Copy sticker into bm_tx and set exact UVs on front sticker face
    tmp_np.verts.ensure_lookup_table()
    tmp_np.verts.index_update()
    vmap = {v.index: bm_tx.verts.new(v.co) for v in tmp_np.verts}
    uv_layer = bm_tx.loops.layers.uv.verify()
    for f in tmp_np.faces:
        nf = bm_tx.faces.new([vmap[v.index] for v in f.verts])
        nf.smooth = False
        nf.material_index = f.material_index
        if f is f_front:
            for loop, uv in zip(nf.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
                loop[uv_layer].uv = uv
    tmp_np.free()

    # 4) Left side: crimson red push-button breaker + black collar + AC cable grommet
    d_side_mid = d_body0 + tx_d * 0.48
    u_left = u_cx - tx_w * 0.5
    v_btn = v_cz + tx_h * 0.02
    # Black threaded collar (embedded 3mm inside wall)
    _add_cyl_between(
        bm_tx,
        frame.world(u_left + 0.003, v_btn, d_side_mid),
        frame.world(u_left - 0.004, v_btn, d_side_mid),
        0.0072, 0.0068, steel_idx, seg=14,
    )
    # Red push button plunger (starts 2mm inside collar)
    _add_cyl_between(
        bm_tx,
        frame.world(u_left - 0.0015, v_btn, d_side_mid),
        frame.world(u_left - 0.0095, v_btn, d_side_mid),
        0.0052, 0.0046, red_idx, seg=14,
    )
    # AC power cord strain-relief grommet (below red button, cleanly between flange screws)
    v_ac = v_cz - tx_h * 0.17
    _add_cyl_between(
        bm_tx,
        frame.world(u_left + 0.003, v_ac, d_side_mid - 0.003),
        frame.world(u_left - 0.011, v_ac, d_side_mid - 0.003),
        0.0058, 0.0042, rubber_idx, seg=12,
    )
    p_ac_out = frame.world(u_left - 0.009, v_ac, d_side_mid - 0.003)

    # 5) Right side: two HV silicone output grommets (centered cleanly between flange screws!)
    u_right = u_cx + tx_w * 0.5
    v_hv_hi = v_cz + tx_h * 0.14
    v_hv_lo = v_cz - tx_h * 0.14
    hv_outs = []
    for v_g in (v_hv_hi, v_hv_lo):
        _add_cyl_between(
            bm_tx,
            frame.world(u_right - 0.003, v_g, d_side_mid - 0.003),
            frame.world(u_right + 0.011, v_g, d_side_mid - 0.003),
            0.0056, 0.0040, rubber_idx, seg=12,
        )
        hv_outs.append(frame.world(u_right + 0.009, v_g, d_side_mid - 0.003))

    return p_ac_out, hv_outs[0], hv_outs[1]


def _add_cable_clip(
    bm_cables: bmesh.types.BMesh,
    frame: SignFrame,
    u: float,
    v: float,
    d_rail_front: float,
    d_cable: float,
    steel_idx: int,
) -> None:
    """Small black steel P-clip anchoring an HV cable against a steel rail."""
    _add_local_box(
        bm_cables, frame, u, v, (d_rail_front + d_cable) * 0.5,
        0.010, 0.014, max(0.004, d_cable - d_rail_front + 0.004),
        steel_idx, bevel=0.0008, bevel_seg=1,
    )


def _add_area_light(
    coll: bpy.types.Collection,
    name: str,
    loc: Vector,
    target: Vector,
    size_x: float,
    size_y: float,
    color: tuple[float, float, float],
    energy: float,
    cutoff: float,
    specular: float = 0.45,
    parent: bpy.types.Object | None = None,
) -> bpy.types.Object:
    ld = bpy.data.lights.new(PFX + name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size = size_x
    ld.size_y = size_y
    ld.color = color
    ld.energy = energy
    ld.use_shadow = False
    ld.specular_factor = specular
    ld.use_custom_distance = True
    ld.cutoff_distance = cutoff
    ob = bpy.data.objects.new(PFX + name, ld)
    coll.objects.link(ob)
    ob.location = loc
    d = target - loc
    if d.length > 1e-6:
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if parent is not None:
        ob.parent = parent
    return ob


# ---------------------------------------------------------------------------
# Sign-specific assembly builders
# ---------------------------------------------------------------------------

def _wall_bbox(name: str) -> tuple[Vector, Vector]:
    ob = bpy.data.objects[name]
    pts = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _build_left_wall_sign(coll: bpy.types.Collection, mats: dict[str, bpy.types.Material]) -> dict:
    """Detail up Sign 1: Left Wall ("넌 운동할 때 / 젤 예뻐" + kettlebell)."""
    src_coll = bpy.data.collections.get("Left Wall Handwriting")
    if src_coll is None:
        raise RuntimeError("Collection 'Left Wall Handwriting' not found in scene.")

    wall_lo, wall_hi = _wall_bbox("Wall_Left")
    wall_x = wall_hi.x  # inner face of Wall_Left (~ -7.500)
    frame = SignFrame(
        origin=Vector((wall_x, 0.0, 0.0)),
        right=Vector((0.0, 1.0, 0.0)),
        up=Vector((0.0, 0.0, 1.0)),
        normal=Vector((1.0, 0.0, 0.0)),
    )

    # Extract existing glass strokes in world space and hide original raw sign objects
    strokes_top_left: list[Stroke2D] = []
    strokes_top_right: list[Stroke2D] = []
    strokes_bottom: list[Stroke2D] = []
    strokes_icon: list[Stroke2D] = []
    hidden_names: list[str] = []

    raw_pink: list[Stroke2D] = []
    raw_white: list[Stroke2D] = []

    for ob in list(src_coll.objects):
        ob.hide_viewport = True
        ob.hide_render = True
        hidden_names.append(ob.name)
        if ob.type != "CURVE" or not ob.name.startswith("Bent neon glass"):
            continue
        mat_name = ob.data.materials[0].name if ob.data.materials else ""
        ckey = "white" if "milk" in mat_name.lower() or "white" in mat_name.lower() else "pink"
        for sp in ob.data.splines:
            w_pts, is_cyc = _sample_spline_world(ob, sp, steps_per_seg=8)
            if len(w_pts) < 2:
                continue
            pts2 = [(frame.local(p)[0], frame.local(p)[1]) for p in w_pts]
            st = Stroke2D(pts=pts2, color_key=ckey, cyclic=is_cyc)
            if ckey == "white":
                raw_white.append(st)
            else:
                raw_pink.append(st)

    if not raw_pink:
        raise RuntimeError("No 'Bent neon glass' curves found in 'Left Wall Handwriting'.")

    # Split pink strokes into Top row ("넌 운동할 때", v > 2.13) and Bottom row ("젤 예뻐", v <= 2.13)
    v_split = 2.14
    top_all = [s for s in raw_pink if (sum(p[1] for p in s.pts) / len(s.pts)) > v_split]
    strokes_bottom = [s for s in raw_pink if (sum(p[1] for p in s.pts) / len(s.pts)) <= v_split]
    # Split top row into 2 glass sections ("넌 운동" / "할 때") near horizontal midpoint
    top_us = [p[0] for s in top_all for p in s.pts]
    u_mid_top = (min(top_us) + max(top_us)) * 0.52
    for s in top_all:
        cu = sum(p[0] for p in s.pts) / len(s.pts)
        if cu < u_mid_top:
            strokes_top_left.append(s)
        else:
            strokes_top_right.append(s)

    # Open kettlebell strokes cleanly if closed so they have real neon glass return bends
    for s in raw_white:
        pts2 = s.pts
        if s.cyclic or math.hypot(pts2[0][0] - pts2[-1][0], pts2[0][1] - pts2[-1][1]) < 0.025:
            pts2 = _open_cyclic_loop_2d(pts2, gap=0.018, preferred_angle_deg=-135.0)
        strokes_icon.append(Stroke2D(pts=pts2, color_key="white", cyclic=False, group="icon"))

    all_strokes = strokes_top_left + strokes_top_right + strokes_bottom + strokes_icon

    # Dimensions & layering depths (mm from Wall_Left face)
    r_tube = 0.0082
    d_upright_back = 0.004
    d_upright_front = 0.008
    d_rail_front = 0.012
    d_cable = 0.020
    d_back = 0.036
    d_front = 0.064

    root = bpy.data.objects.new(PFX + "Left_Root", None)
    root.empty_display_size = 0.15
    coll.objects.link(root)

    # 1) Glass tubes + glossy black-out return bends + silicone electrode boots
    bm_tubes = bmesh.new()
    bm_cables = bmesh.new()
    tube_mats = [mats["pink"], mats["white"], mats["blackout"]]
    cable_mats = [mats["rubber"], mats["steel"]]

    t_tl_0, t_tl_1 = _build_section_tubes_and_boots(
        bm_tubes, bm_cables, frame, strokes_top_left, r_tube, d_front, d_back,
        glow_mat_idx=0, blackout_mat_idx=2, boot_mat_idx=0,
        boot_dir_start=(0.3, -1.0), boot_dir_end=(0.8, -0.5), seg=12,
    )
    t_tr_0, t_tr_1 = _build_section_tubes_and_boots(
        bm_tubes, bm_cables, frame, strokes_top_right, r_tube, d_front, d_back,
        glow_mat_idx=0, blackout_mat_idx=2, boot_mat_idx=0,
        boot_dir_start=(-0.8, -0.5), boot_dir_end=(0.5, -0.8), seg=12,
    )
    t_bot_0, t_bot_1 = _build_section_tubes_and_boots(
        bm_tubes, bm_cables, frame, strokes_bottom, r_tube, d_front, d_back,
        glow_mat_idx=0, blackout_mat_idx=2, boot_mat_idx=0,
        boot_dir_start=(-0.3, -1.0), boot_dir_end=(0.5, -0.8), seg=12,
    )
    t_ico_0, t_ico_1 = _build_section_tubes_and_boots(
        bm_tubes, bm_cables, frame, strokes_icon, r_tube, d_front, d_back,
        glow_mat_idx=1, blackout_mat_idx=2, boot_mat_idx=0,
        boot_dir_start=(-0.9, -0.4), boot_dir_end=(-0.7, -0.7), seg=12,
    )

    # 2) Slim black flat-steel skeleton frame (4 horizontal rails + 2 vertical uprights)
    top_u_all = [p[0] for s in (strokes_top_left + strokes_top_right + strokes_icon) for p in s.pts]
    top_v_all = [p[1] for s in (strokes_top_left + strokes_top_right) for p in s.pts]
    bot_u_all = [p[0] for s in (strokes_bottom + strokes_icon) for p in s.pts]
    bot_v_all = [p[1] for s in strokes_bottom for p in s.pts]
    bot_only_u = [p[0] for s in strokes_bottom for p in s.pts]

    v_top_hi = min(top_v_all) + (max(top_v_all) - min(top_v_all)) * 0.78
    v_top_lo = min(top_v_all) + (max(top_v_all) - min(top_v_all)) * 0.20
    v_bot_hi = min(bot_v_all) + (max(bot_v_all) - min(bot_v_all)) * 0.78
    v_bot_lo = min(bot_v_all) + (max(bot_v_all) - min(bot_v_all)) * 0.18

    rails = [
        (v_top_hi, min(top_u_all) + 0.02, max(top_u_all) - 0.15),
        (v_top_lo, min(top_u_all) + 0.01, max(top_u_all) - 0.06),
        (v_bot_hi, min(bot_u_all) + 0.01, max(bot_u_all) - 0.05),
        (v_bot_lo, min(bot_u_all) + 0.02, max(bot_u_all) - 0.18),
    ]

    # Transformer position: compact MSA-1 centered under bottom row ("젤 예뻐"), well above InBody
    tx_w, tx_h, tx_d = 0.248, 0.104, 0.056
    tx_u = (min(bot_only_u) + max(bot_only_u)) * 0.5 - 0.06
    tx_v = min(bot_v_all) - 0.138  # ~ 1.67 m, cleanly above InBody top (~1.50 m)

    # 2 vertical uprights aligned directly behind transformer's left & right mounting ears
    ear_u_off = tx_w * 0.5 + 0.012
    upright_us = (tx_u - ear_u_off, tx_u + ear_u_off)
    up_v_top = v_top_hi + 0.055
    up_v_bot = tx_v - tx_h * 0.5 - 0.044

    bm_frame = bmesh.new()
    frame_mats = [mats["steel"], mats["zinc"]]

    # Horizontal flat bars (4mm thick x 19mm tall, 0.6mm embed into upright front avoids coplanar z-fight)
    for vr, u0, u1 in rails:
        _add_local_box(
            bm_frame, frame, (u0 + u1) * 0.5, vr, (d_upright_front + d_rail_front) * 0.5,
            u1 - u0, 0.019, d_rail_front - d_upright_front + 0.0008, 0, bevel=0.0006, bevel_seg=1,
        )

    # Vertical flat-bar uprights (4mm thick x 20mm wide) + wall spacers + Phillips wall screws
    for uu in upright_us:
        _add_local_box(
            bm_frame, frame, uu, (up_v_top + up_v_bot) * 0.5, (d_upright_back + d_upright_front) * 0.5,
            0.020, up_v_top - up_v_bot, d_upright_front - d_upright_back, 0, bevel=0.0006, bevel_seg=1,
        )
        # Top & bottom wall spacer cylinders (embedded 0.8mm into upright) + silver Phillips wall screws
        for v_scr in (up_v_top - 0.016, up_v_bot + 0.016):
            _add_cyl_between(
                bm_frame, frame.world(uu, v_scr, 0.0), frame.world(uu, v_scr, d_upright_back + 0.0008),
                0.0068, 0.0068, 0, seg=12,
            )
            _add_phillips_screw(
                bm_frame, frame, uu, v_scr, d_upright_front,
                head_r=0.0044, head_h=0.0025, washer_r=0.0068, washer_h=0.0010,
                zinc_idx=1, slot_idx=0,
            )
        # Small black-oxide cross-joint bolts where horizontal rails cross vertical uprights
        for vr, u0, u1 in rails:
            if u0 <= uu <= u1:
                _add_cyl_between(
                    bm_frame,
                    frame.world(uu, vr, d_rail_front - 0.0008),
                    frame.world(uu, vr, d_rail_front + 0.0024),
                    0.0030, 0.0028, 0, seg=10,
                )

    # 3) Tube supports + saddles + bare copper tie-wire loops
    bm_supports = bmesh.new()
    support_mats = [mats["steel"], mats["zinc"], mats["copper"]]
    n_supports = _add_tube_supports_and_copper_wires(
        bm_supports, frame, all_strokes, rails, r_tube, d_rail_front, d_front,
        steel_idx=0, zinc_idx=1, copper_idx=2, min_spacing=0.115,
    )

    # 4) Electronic neon transformer box + nameplate + red button + grommets
    bm_tx = bmesh.new()
    tx_mats = [
        mats["abs"], mats["steel"], mats["red_btn"],
        mats["rubber"], mats["zinc"], mats["nameplate"],
    ]
    p_ac_out, p_hv_hi, p_hv_lo = _add_transformer(
        bm_tx, frame, tx_u, tx_v, tx_w, tx_h, tx_d, d_upright_front,
        abs_idx=0, steel_idx=1, red_idx=2, rubber_idx=3, zinc_idx=4, np_idx=5,
    )

    # 5) High-voltage silicone cables, inter-section jumpers, P-clips & grounded AC cord
    def route_cable(ctrl_pts: list[Vector], radius: float = 0.0032):
        pts = _catmull_rom_3d(ctrl_pts, steps_per_seg=8)
        _sweep_tube(bm_cables, pts, radius, mat_indices=0, seg=10, cap_start=True, cap_end=True)

    # HV Lead 1 (upper right grommet -> buttery smooth arc right, up, and smoothly curving left above box)
    u_r_exit = tx_u + tx_w * 0.5
    route_cable([
        p_hv_hi,
        frame.world(u_r_exit + 0.048, tx_v + 0.032, d_cable + 0.006),
        frame.world(u_r_exit + 0.072, tx_v + 0.090, d_cable + 0.002),
        frame.world(u_r_exit + 0.020, tx_v + 0.125, d_cable),
        frame.world(tx_u - 0.080, v_bot_lo - 0.018, d_cable),
        t_bot_0[0] + t_bot_0[1] * 0.032,
        t_bot_0[0],
    ], radius=0.0033)

    # HV Lead 2 (lower right grommet -> sweeps wider graceful C-arc right & up to kettlebell/right feed)
    route_cable([
        p_hv_lo,
        frame.world(u_r_exit + 0.068, tx_v - 0.005, d_cable + 0.008),
        frame.world(u_r_exit + 0.118, tx_v + 0.065, d_cable + 0.005),
        frame.world(u_r_exit + 0.125, v_bot_hi - 0.010, d_cable),
        t_ico_1[0] + t_ico_1[1] * 0.036,
        t_ico_1[0],
    ], radius=0.0033)

    # Inter-section HV jumpers routed neatly behind horizontal rails & vertical uprights (NO stray diagonals!)
    def route_jumper(term_a: tuple[Vector, Vector], term_b: tuple[Vector, Vector], sag: float = 0.035):
        pa, da = term_a
        pb, db = term_b
        la = frame.local(pa)
        lb = frame.local(pb)
        mid = frame.world((la[0] + lb[0]) * 0.5, (la[1] + lb[1]) * 0.5 - sag, d_cable)
        route_cable([pa, pa + da * 0.030, mid, pb + db * 0.030, pb], radius=0.0030)

    route_jumper(t_tl_1, t_tr_0, sag=0.025)
    route_jumper(t_tr_1, t_ico_0, sag=0.022)
    route_jumper(t_bot_1, t_ico_1, sag=0.025)
    # Route top-left ("넌") to bottom-left ("젤") neatly along the lower top rail & down to "젤"
    la_tl = frame.local(t_tl_0[0])
    lb_bt = frame.local(t_bot_0[0])
    route_cable([
        t_tl_0[0],
        t_tl_0[0] + t_tl_0[1] * 0.025,
        frame.world(la_tl[0] + 0.10, v_top_lo - 0.005, d_cable),
        frame.world((la_tl[0] + lb_bt[0]) * 0.5, v_top_lo - 0.008, d_cable),
        frame.world(lb_bt[0] - 0.02, v_top_lo - 0.015, d_cable),
        frame.world(lb_bt[0] - 0.01, (v_top_lo + lb_bt[1]) * 0.5, d_cable),
        t_bot_0[0] + t_bot_0[1] * 0.028,
        t_bot_0[0],
    ], radius=0.0030)

    # P-clips securing cables neatly to horizontal rails
    for vr, u0, u1 in rails:
        for frac in (0.32, 0.68):
            _add_cable_clip(bm_cables, frame, u0 + (u1 - u0) * frac, vr, d_rail_front, d_cable, steel_idx=1)

    # AC power cord from left grommet -> smooth realistic slack loop down behind InBody to wall outlet (-3.55, 0.34)
    outlet_u, outlet_v = -3.55, 0.36
    ac_u0, ac_v0, ac_d0 = frame.local(p_ac_out)
    route_cable([
        p_ac_out,
        frame.world(ac_u0 - 0.048, ac_v0 - 0.018, ac_d0 - 0.006),
        frame.world(ac_u0 - 0.085, ac_v0 - 0.095, 0.016),
        frame.world(outlet_u - 0.025, 1.28, 0.010),
        frame.world(outlet_u, 0.85, 0.009),
        frame.world(outlet_u, outlet_v, 0.009),
    ], radius=0.0034)
    # Tiny molded black plug head seated at wall outlet
    _add_local_box(bm_cables, frame, outlet_u, outlet_v, 0.012, 0.024, 0.028, 0.018, 0, bevel=0.003, bevel_seg=2)

    ob_tubes = _finalize_mesh(coll, "Left_Tubes", bm_tubes, tube_mats, parent=root)
    ob_frame = _finalize_mesh(coll, "Left_Frame", bm_frame, frame_mats, parent=root)
    ob_supp = _finalize_mesh(coll, "Left_Supports", bm_supports, support_mats, parent=root)
    ob_tx = _finalize_mesh(coll, "Left_Transformer", bm_tx, tx_mats, parent=root)
    ob_cab = _finalize_mesh(coll, "Left_Cables", bm_cables, cable_mats, parent=root)

    # 6) Balanced shadowless soft neon bounce lights (highlights rails, transformer top, blackout glass)
    u_pink_top = (min(top_us) + max(top_us)) * 0.5
    v_pink_top = (min(top_v_all) + max(top_v_all)) * 0.5
    u_pink_bot = (min(bot_only_u) + max(bot_only_u)) * 0.5
    v_pink_bot = (min(bot_v_all) + max(bot_v_all)) * 0.5
    ico_us = [p[0] for s in strokes_icon for p in s.pts]
    ico_vs = [p[1] for s in strokes_icon for p in s.pts]
    u_ico = (min(ico_us) + max(ico_us)) * 0.5
    v_ico = (min(ico_vs) + max(ico_vs)) * 0.5

    _add_area_light(
        coll, "Left_PinkTopBounce",
        frame.world(u_pink_top, v_pink_top, 0.24),
        frame.world(u_pink_top, v_pink_top, 0.0),
        1.25, 0.30, (1.0, 0.05, 0.36), 4.8, cutoff=1.1, specular=0.55, parent=root,
    )
    _add_area_light(
        coll, "Left_PinkBotBounce",
        frame.world(u_pink_bot, v_pink_bot, 0.24),
        frame.world(u_pink_bot, v_pink_bot - 0.06, 0.0),
        0.85, 0.30, (1.0, 0.05, 0.36), 3.8, cutoff=1.0, specular=0.55, parent=root,
    )
    _add_area_light(
        coll, "Left_WhiteIconBounce",
        frame.world(u_ico, v_ico, 0.26),
        frame.world(u_ico, v_ico, 0.0),
        0.50, 0.58, (0.88, 0.96, 1.0), 3.6, cutoff=1.0, specular=0.45, parent=root,
    )

    return {
        "sign": "Left Wall Handwriting (넌 운동할 때 / 젤 예뻐 + 케틀벨)",
        "hidden_originals": len(hidden_names),
        "strokes": len(all_strokes),
        "supports": n_supports,
        "objects": [ob_tubes.name, ob_frame.name, ob_supp.name, ob_tx.name, ob_cab.name],
    }


def _build_back_wall_sign(coll: bpy.types.Collection, mats: dict[str, bpy.types.Material]) -> dict:
    """Detail up Sign 2: Back Mirror Wall ("운동은! / 워치코치에서" + blue bicep)."""
    src_names = ("Neon_HandwrittenTop", "Neon_HandwrittenBottom", "Neon_RoundedBicep")
    src_objs = [bpy.data.objects.get(n) for n in src_names]
    if any(o is None for o in src_objs):
        missing = [n for n, o in zip(src_names, src_objs) if o is None]
        raise RuntimeError(f"Missing back-wall neon objects: {missing}")

    wall_lo, _ = _wall_bbox("Wall_Back")
    wall_y = wall_lo.y  # inner face of Wall_Back (~ +5.000)
    frame = SignFrame(
        origin=Vector((0.0, wall_y, 0.0)),
        right=Vector((1.0, 0.0, 0.0)),
        up=Vector((0.0, 0.0, 1.0)),
        normal=Vector((0.0, -1.0, 0.0)),
    )

    # Check vertical bounds of MirrorFrame top and Pipe_Back bottom to prevent any clipping
    mirror_top_z = 2.510
    if "MirrorFrame" in bpy.data.objects:
        _, m_hi = _wall_bbox("MirrorFrame")
        mirror_top_z = m_hi.z
    pipe_bot_z = 3.125
    if "Pipe_Back" in bpy.data.objects:
        p_lo, _ = _wall_bbox("Pipe_Back")
        pipe_bot_z = p_lo.z

    # Hide original raw back-wall neon curves & point lights
    hidden_names: list[str] = []
    for n in (*src_names, "NeonGlow_PinkLeft", "NeonGlow_PinkRight", "NeonGlow_Blue"):
        ob = bpy.data.objects.get(n)
        if ob is not None:
            ob.hide_viewport = True
            ob.hide_render = True
            hidden_names.append(n)

    def extract_strokes(ob: bpy.types.Object, ckey: str, open_gap: float, pref_deg: float) -> list[Stroke2D]:
        out: list[Stroke2D] = []
        for sp in ob.data.splines:
            w_pts, is_cyc = _sample_spline_world(ob, sp, steps_per_seg=8)
            if len(w_pts) < 2:
                continue
            pts2 = [(frame.local(p)[0], frame.local(p)[1]) for p in w_pts]
            if is_cyc:
                pts2 = _open_cyclic_loop_2d(pts2, gap=open_gap, preferred_angle_deg=pref_deg)
            out.append(Stroke2D(pts=pts2, color_key=ckey, cyclic=False))
        return out

    r_tube = 0.0066
    strokes_top = extract_strokes(src_objs[0], "pink", open_gap=0.011, pref_deg=-35.0)
    strokes_bot = extract_strokes(src_objs[1], "pink", open_gap=0.011, pref_deg=-35.0)
    strokes_bicep = extract_strokes(src_objs[2], "blue", open_gap=0.015, pref_deg=-120.0)
    all_strokes = strokes_top + strokes_bot + strokes_bicep

    # Depth layers from Wall_Back face (matches original Sign 2 front depth y=4.946 -> d=0.054!)
    d_upright_back = 0.004
    d_upright_front = 0.008
    d_rail_front = 0.012
    d_cable = 0.019
    d_back = 0.030
    d_front = 0.054

    root = bpy.data.objects.new(PFX + "Back_Root", None)
    root.empty_display_size = 0.15
    coll.objects.link(root)

    # 1) Glass neon tubes + glossy black-out return bends + silicone electrode boots
    bm_tubes = bmesh.new()
    bm_cables = bmesh.new()
    tube_mats = [mats["pink"], mats["blue"], mats["blackout"]]
    cable_mats = [mats["rubber"], mats["steel"]]

    t_top_0, t_top_1 = _build_section_tubes_and_boots(
        bm_tubes, bm_cables, frame, strokes_top, r_tube, d_front, d_back,
        glow_mat_idx=0, blackout_mat_idx=2, boot_mat_idx=0,
        boot_dir_start=(-0.3, -1.0), boot_dir_end=(0.6, -0.8), seg=12,
    )
    t_bot_0, t_bot_1 = _build_section_tubes_and_boots(
        bm_tubes, bm_cables, frame, strokes_bot, r_tube, d_front, d_back,
        glow_mat_idx=0, blackout_mat_idx=2, boot_mat_idx=0,
        boot_dir_start=(0.4, -1.0), boot_dir_end=(-0.4, -1.0), seg=12,
    )
    t_bic_0, t_bic_1 = _build_section_tubes_and_boots(
        bm_tubes, bm_cables, frame, strokes_bicep, r_tube + 0.0003, d_front, d_back,
        glow_mat_idx=1, blackout_mat_idx=2, boot_mat_idx=0,
        boot_dir_start=(-0.7, -0.7), boot_dir_end=(-0.4, -0.9), seg=12,
    )

    # 2) Slim black flat-steel skeleton frame (4 horizontal rails + 2 vertical uprights)
    top_u_all = [p[0] for s in (strokes_top + strokes_bicep) for p in s.pts]
    top_v_all = [p[1] for s in strokes_top for p in s.pts]
    bot_u_all = [p[0] for s in strokes_bot for p in s.pts]
    bot_v_all = [p[1] for s in strokes_bot for p in s.pts]

    v_top_hi = min(top_v_all) + (max(top_v_all) - min(top_v_all)) * 0.78
    v_top_lo = min(top_v_all) + (max(top_v_all) - min(top_v_all)) * 0.18
    v_bot_hi = min(bot_v_all) + (max(bot_v_all) - min(bot_v_all)) * 0.76
    v_bot_lo = min(bot_v_all) + (max(bot_v_all) - min(bot_v_all)) * 0.18

    rails = [
        (v_top_hi, min(top_u_all) + 0.01, max(top_u_all) - 0.03),
        (v_top_lo, min(top_u_all) + 0.01, max(top_u_all) - 0.02),
        (v_bot_hi, min(bot_u_all) + 0.01, max(bot_u_all) - 0.01),
        (v_bot_lo, min(bot_u_all) + 0.01, max(bot_u_all) - 0.01),
    ]

    # Compact MSA-1 electronic transformer positioned cleanly in the dark wall band
    # between MirrorFrame top and bottom of "워치코치에서" (with safe margin)
    bot_min_v = min(bot_v_all)
    band_h = bot_min_v - mirror_top_z  # ~0.105 m
    tx_w = 0.205
    tx_h = min(0.078, max(0.064, band_h - 0.024))
    tx_d = 0.046
    tx_u = (min(bot_u_all) + max(bot_u_all)) * 0.5
    tx_v = mirror_top_z + tx_h * 0.5 + 0.012  # sits cleanly ~12 mm above MirrorFrame top!

    ear_u_off = tx_w * 0.5 + 0.012
    upright_us = (tx_u - ear_u_off, tx_u + ear_u_off)
    up_v_top = min(pipe_bot_z - 0.020, max(v_top_hi + 0.055, max(top_v_all) + 0.035))
    up_v_bot = max(mirror_top_z + 0.004, tx_v - tx_h * 0.5 - 0.010)

    bm_frame = bmesh.new()
    frame_mats = [mats["steel"], mats["zinc"]]

    for vr, u0, u1 in rails:
        _add_local_box(
            bm_frame, frame, (u0 + u1) * 0.5, vr, (d_upright_front + d_rail_front) * 0.5,
            u1 - u0, 0.016, d_rail_front - d_upright_front + 0.0008, 0, bevel=0.0005, bevel_seg=1,
        )

    for uu in upright_us:
        _add_local_box(
            bm_frame, frame, uu, (up_v_top + up_v_bot) * 0.5, (d_upright_back + d_upright_front) * 0.5,
            0.018, up_v_top - up_v_bot, d_upright_front - d_upright_back, 0, bevel=0.0005, bevel_seg=1,
        )
        # Top wall spacer + Phillips wall screw
        v_top_scr = up_v_top - 0.014
        _add_cyl_between(
            bm_frame, frame.world(uu, v_top_scr, 0.0), frame.world(uu, v_top_scr, d_upright_back + 0.0008),
            0.0060, 0.0060, 0, seg=12,
        )
        _add_phillips_screw(
            bm_frame, frame, uu, v_top_scr, d_upright_front,
            head_r=0.0038, head_h=0.0022, washer_r=0.0058, washer_h=0.0009,
            zinc_idx=1, slot_idx=0,
        )
        # Bottom spacer behind transformer ear zone (clamped safely above MirrorFrame)
        v_bot_scr = max(up_v_bot + 0.008, mirror_top_z + 0.012)
        _add_cyl_between(
            bm_frame, frame.world(uu, v_bot_scr, 0.0), frame.world(uu, v_bot_scr, d_upright_back + 0.0008),
            0.0060, 0.0060, 0, seg=12,
        )
        for vr, u0, u1 in rails:
            if u0 <= uu <= u1:
                _add_cyl_between(
                    bm_frame,
                    frame.world(uu, vr, d_rail_front - 0.0008),
                    frame.world(uu, vr, d_rail_front + 0.0022),
                    0.0026, 0.0024, 0, seg=10,
                )

    # 3) Tube supports + U-cradles + bare copper tie wires
    bm_supports = bmesh.new()
    support_mats = [mats["steel"], mats["zinc"], mats["copper"]]
    n_supports = _add_tube_supports_and_copper_wires(
        bm_supports, frame, all_strokes, rails, r_tube, d_rail_front, d_front,
        steel_idx=0, zinc_idx=1, copper_idx=2, min_spacing=0.088,
    )

    # 4) Electronic neon transformer box + nameplate + red button + grommets
    bm_tx = bmesh.new()
    tx_mats = [
        mats["abs"], mats["steel"], mats["red_btn"],
        mats["rubber"], mats["zinc"], mats["nameplate"],
    ]
    p_ac_out, p_hv_hi, p_hv_lo = _add_transformer(
        bm_tx, frame, tx_u, tx_v, tx_w, tx_h, tx_d, d_upright_front,
        abs_idx=0, steel_idx=1, red_idx=2, rubber_idx=3, zinc_idx=4, np_idx=5,
    )

    # 5) High-voltage silicone leads, inter-section jumpers, P-clips & AC power cord
    def route_cable(ctrl_pts: list[Vector], radius: float = 0.0028):
        pts = _catmull_rom_3d(ctrl_pts, steps_per_seg=8)
        _sweep_tube(bm_cables, pts, radius, mat_indices=0, seg=10, cap_start=True, cap_end=True)

    # HV Lead 1 (upper right grommet -> smooth curve right & up along lower rail to bottom-right electrode)
    u_r_exit = tx_u + tx_w * 0.5
    route_cable([
        p_hv_hi,
        frame.world(u_r_exit + 0.055, tx_v + 0.018, d_cable + 0.006),
        frame.world(u_r_exit + 0.140, tx_v + 0.048, d_cable + 0.002),
        frame.world(u_r_exit + 0.340, v_bot_lo - 0.012, d_cable),
        t_bot_1[0] + t_bot_1[1] * 0.025,
        t_bot_1[0],
    ], radius=0.0029)

    # HV Lead 2 (lower right grommet -> wider graceful arc right & up to blue bicep feed, matching 132755.jpg!)
    route_cable([
        p_hv_lo,
        frame.world(u_r_exit + 0.068, tx_v - 0.006, d_cable + 0.007),
        frame.world(u_r_exit + 0.120, tx_v + 0.045, d_cable + 0.004),
        frame.world(u_r_exit + 0.145, v_bot_hi + 0.015, d_cable),
        t_bic_1[0] + t_bic_1[1] * 0.028,
        t_bic_1[0],
    ], radius=0.0029)

    def route_jumper(term_a: tuple[Vector, Vector], term_b: tuple[Vector, Vector], sag: float = 0.025):
        pa, da = term_a
        pb, db = term_b
        la = frame.local(pa)
        lb = frame.local(pb)
        mid = frame.world((la[0] + lb[0]) * 0.5, (la[1] + lb[1]) * 0.5 - sag, d_cable)
        route_cable([pa, pa + da * 0.024, mid, pb + db * 0.024, pb], radius=0.0027)

    route_jumper(t_top_1, t_bic_0, sag=0.022)
    route_jumper(t_top_0, t_bot_0, sag=0.030)

    for vr, u0, u1 in rails:
        for frac in (0.30, 0.70):
            _add_cable_clip(bm_cables, frame, u0 + (u1 - u0) * frac, vr, d_rail_front, d_cable, steel_idx=1)

    # AC power cord exits left grommet -> natural catenary curve left just above MirrorFrame top
    # tucking neatly behind the black-and-yellow column / mirror top lip (matching 132825.jpg!)
    ac_u0, ac_v0, ac_d0 = frame.local(p_ac_out)
    v_lip = mirror_top_z + 0.006
    route_cable([
        p_ac_out,
        frame.world(ac_u0 - 0.045, ac_v0 - 0.008, ac_d0 - 0.006),
        frame.world(ac_u0 - 0.180, v_lip + 0.004, 0.014),
        frame.world(min(bot_u_all) - 0.10, v_lip + 0.003, 0.010),
        frame.world(min(bot_u_all) - 0.28, v_lip, 0.006),
    ], radius=0.0030)

    ob_tubes = _finalize_mesh(coll, "Back_Tubes", bm_tubes, tube_mats, parent=root)
    ob_frame = _finalize_mesh(coll, "Back_Frame", bm_frame, frame_mats, parent=root)
    ob_supp = _finalize_mesh(coll, "Back_Supports", bm_supports, support_mats, parent=root)
    ob_tx = _finalize_mesh(coll, "Back_Transformer", bm_tx, tx_mats, parent=root)
    ob_cab = _finalize_mesh(coll, "Back_Cables", bm_cables, cable_mats, parent=root)

    # 6) Balanced shadowless soft neon wall-wash & room-glow lights (matches 132755/132811/132825!)
    top_u_c = (min(p[0] for s in strokes_top for p in s.pts) + max(p[0] for s in strokes_top for p in s.pts)) * 0.5
    top_v_c = (min(top_v_all) + max(top_v_all)) * 0.5
    bot_u_c = (min(bot_u_all) + max(bot_u_all)) * 0.5
    bot_v_c = (min(bot_v_all) + max(bot_v_all)) * 0.5
    bic_us = [p[0] for s in strokes_bicep for p in s.pts]
    bic_vs = [p[1] for s in strokes_bicep for p in s.pts]
    bic_u_c = (min(bic_us) + max(bic_us)) * 0.5
    bic_v_c = (min(bic_vs) + max(bic_vs)) * 0.5

    # Wall-facing soft neon halos on dark Wall_Back (rich magenta + deep cobalt, no pipe washout)
    _add_area_light(
        coll, "Back_PinkWallGlowTop",
        frame.world(top_u_c, top_v_c, 0.19),
        frame.world(top_u_c, top_v_c, 0.0),
        0.78, 0.20, (1.0, 0.02, 0.34), 6.2, cutoff=0.75, specular=0.62, parent=root,
    )
    _add_area_light(
        coll, "Back_PinkWallGlowBot",
        frame.world(bot_u_c, bot_v_c, 0.19),
        frame.world(bot_u_c, bot_v_c - 0.03, 0.0),
        1.20, 0.22, (1.0, 0.02, 0.35), 7.8, cutoff=0.80, specular=0.62, parent=root,
    )
    _add_area_light(
        coll, "Back_BlueWallGlow",
        frame.world(bic_u_c, bic_v_c, 0.19),
        frame.world(bic_u_c, bic_v_c, 0.0),
        0.48, 0.26, (0.01, 0.16, 1.0), 10.5, cutoff=0.80, specular=0.68, parent=root,
    )
    # Gentle room-facing ambient spill so nearby metal/ceiling catches subtle magenta+blue tint
    _add_area_light(
        coll, "Back_RoomSpillPink",
        frame.world(bot_u_c - 0.10, (top_v_c + bot_v_c) * 0.5, 0.12),
        frame.world(bot_u_c - 0.10, (top_v_c + bot_v_c) * 0.5, 1.20),
        1.05, 0.38, (1.0, 0.03, 0.36), 4.5, cutoff=1.8, specular=0.35, parent=root,
    )
    _add_area_light(
        coll, "Back_RoomSpillBlue",
        frame.world(bic_u_c, bic_v_c, 0.12),
        frame.world(bic_u_c, bic_v_c, 1.20),
        0.46, 0.28, (0.015, 0.18, 1.0), 5.8, cutoff=1.6, specular=0.40, parent=root,
    )

    return {
        "sign": "Back Mirror Wall Neon (운동은! / 워치코치에서 + 파란 이두근)",
        "hidden_originals": len(hidden_names),
        "strokes": len(all_strokes),
        "supports": n_supports,
        "transformer_z": [round(tx_v - tx_h * 0.5, 4), round(tx_v + tx_h * 0.5, 4)],
        "mirror_top_z": round(mirror_top_z, 4),
        "objects": [ob_tubes.name, ob_frame.name, ob_supp.name, ob_tx.name, ob_cab.name],
    }


# ---------------------------------------------------------------------------
# Idempotent collection cleanup & public entry point
# ---------------------------------------------------------------------------

def _reset_collection() -> bpy.types.Collection:
    parent = bpy.data.collections.get("SET") or bpy.context.scene.collection
    c = bpy.data.collections.get(COLL)
    if c is not None:
        for ob in list(c.objects):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Light):
                    bpy.data.lights.remove(data)
                elif isinstance(data, bpy.types.Curve):
                    bpy.data.curves.remove(data)
    else:
        c = bpy.data.collections.new(COLL)
        parent.children.link(c)
    if c.name not in parent.children:
        parent.children.link(c)

    # Purge any orphaned D7neon_ meshes/lights/materials from prior runs
    for pool in (bpy.data.meshes, bpy.data.lights, bpy.data.curves):
        for blk in list(pool):
            if blk.name.startswith(PFX) and blk.users == 0:
                pool.remove(blk)
    return c


def apply() -> dict:
    c = _reset_collection()
    mats = _build_materials()
    left_info = _build_left_wall_sign(c, mats)
    back_info = _build_back_wall_sign(c, mats)
    bpy.context.view_layer.update()

    dg = bpy.context.evaluated_depsgraph_get()
    total_tris = 0
    per_obj = {}
    for ob in c.objects:
        if ob.type == "MESH":
            me = ob.evaluated_get(dg).data
            me.calc_loop_triangles()
            t = len(me.loop_triangles)
            total_tris += t
            per_obj[ob.name] = t

    return {
        "collection": COLL,
        "objects_added": len(c.objects),
        "triangles_added": total_tris,
        "per_object_tris": per_obj,
        "signs": [left_info, back_info],
    }


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="", help="Optional output .blend path to save")
    return ap.parse_args(argv)


if __name__ == "__main__":
    import json
    args = _parse_args()
    result = apply()
    print("DETAIL7_NEON_SIGNS_RESULT:", json.dumps(result, ensure_ascii=False))
    if args.save:
        out_path = os.path.abspath(args.save)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True, relative_remap=False)
        print("SAVED:", out_path)
