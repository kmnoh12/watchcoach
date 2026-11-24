"""Gym wall graphics detail pass: 3D wall lettering, edge-lit acrylic LED signs and zone plates.

Run on an open scene_gym.blend (never saves):
    import sys; sys.path.insert(0, "promo/tools")
    import detail_gym_wall_graphics; detail_gym_wall_graphics.apply()

Reference photos (work/refs/gym/...):
  137, 138, 140, 147  stand-off cut-out lettering running along a wall band above head height
  278, 280, 282, 283  edge-lit acrylic LED signs: clear plate, black top LED rail, glowing side/bottom
                      edges, white/coloured etched text, black lead to the right
  284, 285, 279       neon colour palette (cool white / blue / pink) on dark walls
  hall/023            white zone plate with dark lettering ("freeweight" signage)
Everything is generated geometry (font outlines converted to meshes); no image files are needed.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wc_lib as W  # noqa: E402

KEY = "gym_wall_graphics"
COLL = "DETAIL_gym_wall_graphics"
P = "Dgym_wall_graphics_"

AQUA = (0.388, 0.839, 0.871)  # app aqua #63d6de

EN_FONTS = (
    "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
    r"C:\Windows\Fonts\bahnschrift.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
)


def _en_font():
    return next((p for p in EN_FONTS if os.path.exists(p)), W.KFONT)


# ------------------------------------------------------------------ materials

def _principled(name, color, rough=0.5, metal=0.0, emit=0.0, emit_color=None, alpha=1.0,
                aniso=0.0, coat=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        nt.nodes.clear()
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Anisotropic"].default_value = aniso
    b.inputs["Coat Weight"].default_value = coat
    ec = emit_color or color
    b.inputs["Emission Color"].default_value = (*ec, 1)
    b.inputs["Emission Strength"].default_value = emit
    b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*color, 1)
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
        m.use_transparency_overlap = False
        m.use_backface_culling = False
    return m


def _materials():
    return {
        # Cut-out lettering: satin white powder coat (ref 147 letters, inverted for a dark wall).
        "ko": _principled(P + "PowderWhite", (0.80, 0.80, 0.78), rough=0.42, coat=0.15),
        # Brushed stainless lettering for the cardio wall (ref 137 metal letters).
        "en": _principled(P + "BrushedSteel", (0.86, 0.86, 0.88), rough=0.30, metal=1.0, aniso=0.6),
        # Clear cast acrylic plate.
        "acrylic": _principled(P + "ClearAcrylic", (0.92, 0.96, 1.0), rough=0.04, alpha=0.10),
        # LED rail / black anodised aluminium.
        "rail": _principled(P + "BlackAnodised", (0.012, 0.012, 0.013), rough=0.38, metal=0.6),
        "cable": _principled(P + "BlackCable", (0.008, 0.008, 0.008), rough=0.6),
        "chrome": _principled(P + "ChromeStandoff", (0.90, 0.90, 0.90), rough=0.16, metal=1.0),
        # Edge-lit text / edges (emission tuned for AgX, exposure 0.22, EEVEE).
        "led_white": _principled(P + "LED_CoolWhite", (0.85, 0.95, 1.0), rough=0.3,
                                 emit=9.0, emit_color=(0.82, 0.94, 1.0)),
        "led_aqua": _principled(P + "LED_Aqua", AQUA, rough=0.3, emit=11.0, emit_color=(0.20, 0.85, 0.95)),
        "led_pink": _principled(P + "LED_Pink", (1.0, 0.12, 0.55), rough=0.3, emit=10.0,
                                emit_color=(1.0, 0.06, 0.52)),
        # Zone plates: white acrylic face, graphite lettering, aqua accent (hall ref 023).
        "plate": _principled(P + "PlateWhite", (0.78, 0.78, 0.76), rough=0.35, coat=0.3),
        "plate_ink": _principled(P + "PlateGraphite", (0.035, 0.037, 0.04), rough=0.5),
        "plate_accent": _principled(P + "PlateAqua", AQUA, rough=0.4),
    }


# ------------------------------------------------------------------ geometry helpers

def _collection():
    parent = bpy.data.collections["SET"]
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        parent.children.link(c)
    elif c.name not in parent.children:
        parent.children.link(c)
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
    return c


def _obj(c, name, me, parent):
    ob = bpy.data.objects.new(P + name, me)
    c.objects.link(ob)
    ob.parent = parent
    return ob


def _box(c, name, size, center, mat, parent, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES",
                        profile=0.5, clamp_overlap=True)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    me = bpy.data.meshes.new(P + name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return _obj(c, name, me, parent)


def _cyl_y(c, name, r, y0, y1, x, z, mat, parent, seg=12):
    """Cylinder along local Y (wall normal) from y0 to y1."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=abs(y1 - y0))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"))
    bmesh.ops.translate(bm, vec=Vector((x, (y0 + y1) / 2, z)), verts=bm.verts)
    me = bpy.data.meshes.new(P + name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    return _obj(c, name, me, parent)


def _text(c, name, body, font_path, size, depth, front_y, x, z, mat, parent,
          align="CENTER", bevel=0.0, spacing=1.0, resolution=3):
    """Font outline -> mesh in the anchor frame: reads along +X, faces -Y, front face at front_y."""
    cu = bpy.data.curves.new(P + name + "_tmp", "FONT")
    cu.body = body
    font = bpy.data.fonts.load(font_path, check_existing=True)
    cu.font = font
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_character = spacing
    flat = depth <= 0.002  # etched / printed lettering: single flat face, no sides
    cu.extrude = 0.0 if flat else max(depth / 2 - bevel, 0.0)
    cu.bevel_depth = bevel
    cu.bevel_resolution = 1 if bevel else 0
    cu.resolution_u = resolution
    tmp = bpy.data.objects.new(P + name + "_tmp", cu)
    c.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    if font.users == 0:
        bpy.data.fonts.remove(font)
    me.name = P + name
    # Curve plane XY (extrude on Z) -> wall frame XZ, front toward -Y.
    me.transform(Matrix.Rotation(math.radians(90), 4, "X"))
    half = 0.0 if flat else depth / 2
    me.transform(Matrix.Translation((x, front_y + half, z)))
    for p in me.polygons:
        p.use_smooth = False
    me.materials.clear()
    me.materials.append(mat)
    return _obj(c, name, me, parent)


def _cable(c, name, pts, r, mat, parent):
    cu = bpy.data.curves.new(P + name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 1
    cu.resolution_u = 6
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, co in zip(sp.bezier_points, pts):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    tmp = bpy.data.objects.new(P + name + "_tmp", cu)
    c.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    me.name = P + name
    for p in me.polygons:
        p.use_smooth = True
    me.materials.clear()
    me.materials.append(mat)
    return _obj(c, name, me, parent)


def _anchor(c, name, loc, rot_z_deg):
    e = bpy.data.objects.new(P + name, None)
    e.empty_display_size = 0.3
    e.empty_display_type = "ARROWS"
    c.objects.link(e)
    e.location = loc
    e.rotation_euler = (0, 0, math.radians(rot_z_deg))
    return e


def _light(c, name, parent, loc, color, energy, radius=0.25):
    li = bpy.data.lights.new(P + name, "POINT")
    li.color = color
    li.energy = energy
    li.shadow_soft_size = radius
    li.use_shadow = False
    ob = bpy.data.objects.new(P + name, li)
    c.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    return ob


# ------------------------------------------------------------------ elements

def _acrylic_sign(c, M, anchor, tag, w, h, cx, cz, lines, led, light_color, light_energy,
                  standoff=0.035, thick=0.008, cable_side=1):
    """Edge-lit LED acrylic sign (ref 278/280/283): clear plate on four chrome stand-offs, black LED
    rail along the top edge, the other three edges glow, etched text glows."""
    y_back = -standoff
    y_front = y_back - thick
    yc = (y_back + y_front) / 2
    x0, x1, z0, z1 = cx - w / 2, cx + w / 2, cz - h / 2, cz + h / 2
    _box(c, f"{tag}_Plate", (w, thick, h), (cx, yc, cz), M["acrylic"], anchor)
    # LED rail on the top edge (aluminium channel that hides the strip), 1 mm clear of the plate.
    rail_h = 0.026
    _box(c, f"{tag}_LEDRail", (w + 0.012, 0.020, rail_h), (cx, yc, z1 + 0.001 + rail_h / 2),
         M["rail"], anchor, bevel=0.002)
    # Lit edges: thin emissive bands set 0.5 mm off the plate edges.
    e = 0.003
    g = 0.0005
    _box(c, f"{tag}_EdgeBottom", (w, thick * 0.9, e), (cx, yc, z0 - g - e / 2), led, anchor)
    _box(c, f"{tag}_EdgeLeft", (e, thick * 0.9, h), (x0 - g - e / 2, yc, cz), led, anchor)
    _box(c, f"{tag}_EdgeRight", (e, thick * 0.9, h), (x1 + g + e / 2, yc, cz), led, anchor)
    # Stand-offs: barrel from inside the wall to the plate back, cap 0.5 mm in front of the plate.
    for i, (sx, sz) in enumerate(((x0 + 0.04, z1 - 0.045), (x1 - 0.04, z1 - 0.045),
                                  (x0 + 0.04, z0 + 0.04), (x1 - 0.04, z0 + 0.04))):
        _cyl_y(c, f"{tag}_Standoff{i}", 0.0085, 0.004, y_back - 0.0005, sx, sz, M["chrome"], anchor)
        _cyl_y(c, f"{tag}_StandoffCap{i}", 0.0095, y_front - 0.0005, y_front - 0.0075, sx, sz,
               M["chrome"], anchor)
    # Etched lettering, lit: very thin glowing layer 0.7 mm in front of the acrylic face.
    for j, (body, font, size, lx, lz) in enumerate(lines):
        _text(c, f"{tag}_Text{j}", body, font, size, 0.0006, y_front - 0.0007, cx + lx, cz + lz, led,
              anchor, resolution=2)
    # Power lead out of the rail end, dropping down the wall (ref 278/280 black lead).
    xe = (x1 + 0.006) if cable_side > 0 else (x0 - 0.006)
    s = cable_side
    _cable(c, f"{tag}_Lead", [(xe, yc, z1 + 0.012), (xe + s * 0.05, yc + 0.01, z1 - 0.01),
                              (xe + s * 0.07, -0.006, z1 - 0.20), (xe + s * 0.06, -0.006, z0 - 0.25)],
           0.0025, M["cable"], anchor)
    _light(c, f"{tag}_Glow", anchor, (cx, -0.35, cz), light_color, light_energy, radius=max(w, h) / 2)


def _zone_plate(c, M, anchor, tag, cx, cz, en, ko, w=1.05, h=0.22):
    """Zone plate (hall ref 023 style): white acrylic plate, graphite lettering, aqua index bar,
    four brushed stand-off caps."""
    standoff, thick = 0.020, 0.006
    y_back = -standoff
    y_front = y_back - thick
    _box(c, f"{tag}_Plate", (w, thick, h), (cx, (y_back + y_front) / 2, cz), M["plate"], anchor, bevel=0.0015)
    bar_w = 0.045
    bx = cx - w / 2 + 0.035 + bar_w / 2
    _box(c, f"{tag}_Accent", (bar_w, 0.002, h - 0.06), (bx, y_front - 0.001 - 0.001, cz),
         M["plate_accent"], anchor)
    tx = bx + bar_w / 2 + 0.035
    _text(c, f"{tag}_EN", en, _en_font(), 0.105, 0.0015, y_front - 0.0012, tx, cz + 0.022,
          M["plate_ink"], anchor, align="LEFT", spacing=1.08)
    _text(c, f"{tag}_KO", ko, W.KFONT, 0.050, 0.0015, y_front - 0.0012, tx + 0.003, cz - 0.060,
          M["plate_ink"], anchor, align="LEFT", spacing=1.05, resolution=2)
    for i, (sx, sz) in enumerate(((cx - w / 2 + 0.018, cz + h / 2 - 0.018), (cx + w / 2 - 0.018, cz + h / 2 - 0.018),
                                  (cx - w / 2 + 0.018, cz - h / 2 + 0.018), (cx + w / 2 - 0.018, cz - h / 2 + 0.018))):
        _cyl_y(c, f"{tag}_Standoff{i}", 0.006, 0.004, y_back - 0.0005, sx, sz, M["chrome"], anchor, seg=10)
        _cyl_y(c, f"{tag}_Cap{i}", 0.0075, y_front - 0.0005, y_front - 0.0055, sx, sz, M["chrome"], anchor,
               seg=10)


# ------------------------------------------------------------------ main

def _wall_faces():
    def bb(name):
        ob = bpy.data.objects[name]
        ws = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
        return ([min(v[i] for v in ws) for i in range(3)], [max(v[i] for v in ws) for i in range(3)])
    return {"back_y": bb("Wall_Back")[0][1], "right_x": bb("Wall_Right")[0][0], "left_x": bb("Wall_Left")[1][0]}


def apply() -> dict:
    c = _collection()
    M = _materials()
    f = _wall_faces()
    ko_font = W.KFONT
    en_font = _en_font()

    # Anchor frames: local X = reading direction, local -Y = out of the wall, local Z up, origin on
    # the wall face.
    back = _anchor(c, "Anchor_BackWall", (0.0, f["back_y"], 0.0), 0)       # faces -Y
    right = _anchor(c, "Anchor_RightWall", (f["right_x"], 0.0, 0.0), -90)  # faces -X, reads toward -Y
    left = _anchor(c, "Anchor_LeftWall", (f["left_x"], 0.0, 0.0), 90)      # faces +X, reads toward +Y

    # 1a. Korean stand-off lettering on the blank back-wall bay left of the column (x -7.5 .. -3.2),
    #     band just under the service pipe, like ref 147/138.
    _text(c, "Lettering_KO", "어제보다 한 세트 더", ko_font, 0.36, 0.022, -0.030, -5.30, 2.78, M["ko"], back,
          bevel=0.0012, spacing=1.04, resolution=2)
    # 1b. English brushed-steel lettering above the cardio window on the right wall (ref 137/140).
    #     Right-wall anchor: local x = -world y, so world y -0.6 is local x +0.6.
    _text(c, "Lettering_EN", "SWEAT NOW. SHINE LATER.", en_font, 0.34, 0.018, -0.028, 0.62, 3.215, M["en"],
          right, bevel=0.0010, spacing=1.06)

    # 2a. Gym-name edge-lit acrylic sign under the Korean lettering (ref 283 two-line layout,
    #     ref 280 white edge glow), app aqua.
    #     Placed on the left wall above the barbell rack: the back-wall bay below the Korean lettering
    #     is the gym_freeweight mirror wall.
    _acrylic_sign(c, M, left, "NameSign", 1.50, 0.56, 3.45, 1.95,
                  [("워치코치 짐", ko_font, 0.19, 0.0, 0.075), ("WATCH  COACH  GYM", en_font, 0.135, 0.0, -0.125)],
                  M["led_aqua"], (0.25, 0.85, 0.95), 9.0, cable_side=1)
    # 2b. Small pink portrait sign in the stretching corner (ref 278 right-hand plate).
    #     Left-wall anchor: local x = world y.
    _acrylic_sign(c, M, left, "StretchSign", 0.46, 0.56, 1.72, 1.62,
                  [("천천히", ko_font, 0.088, 0.0, 0.155), ("끝까지", ko_font, 0.088, 0.0, 0.040),
                   ("몸은 기억한다", ko_font, 0.040, 0.0, -0.085), ("WATCH COACH GYM", en_font, 0.034, 0.0, -0.175)],
                  M["led_pink"], (1.0, 0.18, 0.55), 4.0, standoff=0.030, cable_side=1)

    # 3. Zone plates where the zones really are.
    #    FREE WEIGHT: above the mirror, over the dumbbell/EZ racks (x -3.4 .. 1.4).
    _zone_plate(c, M, back, "Zone_FreeWeight", -1.95, 2.66, "FREE WEIGHT", "프리웨이트 존")
    #    CARDIO: right wall beside the treadmill/climber row, clear of the window (y > 3.12).
    _zone_plate(c, M, right, "Zone_Cardio", -4.05, 2.40, "CARDIO", "유산소 존", w=0.80)
    #    STRETCHING: above the stretching mirror (y -1.44 .. 1.04) over the mats.
    _zone_plate(c, M, left, "Zone_Stretching", -0.20, 2.62, "STRETCHING", "스트레칭 존", w=1.00)

    bpy.context.view_layer.update()
    objs = [o for o in c.objects]
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for o in objs:
        if o.type == "MESH":
            me = o.evaluated_get(dg).data
            me.calc_loop_triangles()
            tris += len(me.loop_triangles)
    return {"collection": COLL, "objects_added": len(objs), "triangles_added": tris,
            "existing_objects_touched": []}


if __name__ == "__main__":
    print(apply())
