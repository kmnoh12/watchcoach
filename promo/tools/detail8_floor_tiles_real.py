"""Finish the gym's three rubber surfaces. Run after gym_floor and floor_rubber.

Blender -b scene.blend -P promo/tools/detail8_floor_tiles_real.py -- --save output.blend
Without --save the pass only updates the loaded scene in memory.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from detail_gym_floor import FW_X, FW_Y, FW_TOP
from detail4_floor_rubber import WEAR_PATHS, _wear_capsule_mask

GAP = 0.00100
RADIUS = 0.00075
MAP = TOOLS.parent / "parts/detail8_floor_tiles/pressed_epdm.png"
TARGETS = ("RubberFloorTiles", "Dgym_floor_FreeWeight_Tiles", "Platform_Base")


class Surface:
    def __init__(self, name):
        name = "D8floor_" + name
        self.mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        self.mat.diffuse_color = (0.019, 0.020, 0.021, 1)
        self.tree = self.mat.node_tree
        self.tree.nodes.clear()
        self.bsdf = self.node("BsdfPrincipled", "Pressed rubber", 800, 100)
        self.bsdf.inputs["IOR"].default_value = 1.50
        out = self.node("OutputMaterial", "Surface", 1120, 100)
        self.link(self.bsdf.outputs[0], out, "Surface")
        self.pos = self.node("NewGeometry", "Metres in the room", -1500, 400).outputs["Position"]

    def node(self, kind, label, x, y):
        n = self.tree.nodes.new("ShaderNode" + kind)
        n.label = label
        n.location = (x, y)
        return n

    def link(self, socket, node, index):
        self.tree.links.new(socket, node.inputs[index])

    def noise(self, label, scale, detail, x, y):
        n = self.node("TexNoise", label, x, y)
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        self.link(self.pos, n, "Vector")
        return n.outputs["Fac"]

    def remap(self, source, label, input_range, output_range, x, y):
        n = self.node("MapRange", label, x, y)
        for key, value in zip(("From Min", "From Max", "To Min", "To Max"), (*input_range, *output_range)):
            n.inputs[key].default_value = value
        self.link(source, n, "Value")
        return n.outputs[0]

    def math(self, operation, a, b, label, x, y):
        n = self.node("Math", label, x, y)
        n.operation = operation
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n, i)
        return n.outputs[0]

    def bump(self, height, distance, strength):
        n = self.node("Bump", "Surface relief in metres", 550, -320)
        n.inputs["Distance"].default_value = distance
        n.inputs["Strength"].default_value = strength
        self.link(height, n, "Height")
        self.link(n.outputs["Normal"], self.bsdf, "Normal")


def top_material(name, origin, pitch, image):
    s = Surface(name)
    s.bsdf.inputs["IOR"].default_value = 1.44
    # A single random translation for each installed tile breaks up the repeating chip map.
    add = s.node("VectorMath", "Grid origin", -1260, 680)
    add.operation = "SUBTRACT"
    s.link(s.pos, add, 0)
    add.inputs[1].default_value = (*origin, -0.1)
    snap = s.node("VectorMath", "Installed tile", -1050, 680)
    snap.operation = "SNAP"
    s.link(add.outputs[0], snap, 0)
    snap.inputs[1].default_value = (pitch, pitch, 1)
    rand = s.node("TexWhiteNoise", "Tile seed", -840, 680)
    s.link(snap.outputs[0], rand, "Vector")
    scale = s.node("VectorMath", "600 mm material sample", -1050, 400)
    scale.operation = "SCALE"
    scale.inputs["Scale"].default_value = 1 / 0.6
    s.link(s.pos, scale, 0)
    uv = s.node("VectorMath", "Sample offset", -590, 540)
    uv.operation = "ADD"
    s.link(scale.outputs[0], uv, 0)
    s.link(rand.outputs["Color"], uv, 1)
    tex = s.node("TexImage", "Embedded cut EPDM chips", -380, 540)
    tex.image = image
    s.link(uv.outputs[0], tex, "Vector")
    grain = s.noise("Compressed granules", 470, 2.4, -370, 210)
    tone = s.remap(grain, "Binder grain", (.25,.75), (.44,.67), -150, 210)
    tile_tone = s.remap(rand.outputs["Value"], "Batch tone", (0,1), (.74,1.18), -150, -25)
    tone = s.math("MULTIPLY", tone, tile_tone, "Tile and binder tone", 40, 220)
    tint = s.node("MixRGB", "Chips pressed flush", 140, 540)
    tint.blend_type = "MULTIPLY"
    tint.inputs[0].default_value = 1
    s.link(tex.outputs["Color"], tint, 1)
    s.link(tone, tint, 2)
    edge = s.node("Attribute", "Pressed lip shading", 60, 830)
    edge.attribute_name = "pressed_lip"
    lip = s.node("MixRGB", "Contact shade along the real lip", 380, 600)
    lip.blend_type = "MULTIPLY"
    s.link(edge.outputs["Fac"], lip, 0)
    s.link(tint.outputs[0], lip, 1)
    lip.inputs[2].default_value = (.54, .54, .54, 1)
    s.link(lip.outputs[0], s.bsdf, "Base Color")

    wear = s.noise("Broad polish patches", 2.3, 3, -1100, -100)
    rough = s.remap(wear, "Satin to unworn", (.26,.74), (.30,.61), -840, -100)
    bias = s.remap(rand.outputs["Value"], "Tile finishing variation", (0,1), (-.055,.055), -600, -100)
    rough = s.math("ADD", rough, bias, "Tile and patch finish", -370, -100)
    paths = []
    for i, path in enumerate(WEAR_PATHS):
        existing = set(s.tree.nodes)
        mask = _wear_capsule_mask(s.tree.nodes, s.tree.links, s.pos, *path, x_off=-3100)
        for node in set(s.tree.nodes) - existing:
            node.location.y -= i * 1060
        paths.append(mask)
    for i, path in enumerate(paths[1:]):
        paths[0] = s.math("MAXIMUM", paths[0], path, "Walked area", -960+i*180, -880)
    polish = s.math("MULTIPLY", paths[0], .085, "Traffic polish", -400, -560)
    s.link(s.math("SUBTRACT", rough, polish, "Local roughness", 200, -100), s.bsdf, "Roughness")
    s.bump(grain, .00018, .21)
    return s.mat


def crumb_material():
    s = Surface("CutCrumb")
    vor = s.node("TexVoronoi", "Fractured black crumb", -880, 480)
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 360
    noise = s.node("TexNoise", "Torn particle boundaries", -1420, 100)
    noise.inputs["Scale"].default_value = 520
    noise.inputs["Detail"].default_value = 2.6
    s.link(s.pos, noise, "Vector")
    warp = s.node("VectorMath", "Submillimetre tear", -1210, 100)
    warp.operation = "SCALE"
    warp.inputs["Scale"].default_value = .0034
    s.link(noise.outputs["Color"], warp, 0)
    distorted = s.node("VectorMath", "Irregular crumb", -1070, 570)
    distorted.operation = "ADD"
    s.link(s.pos, distorted, 0)
    s.link(warp.outputs[0], distorted, 1)
    s.link(distorted.outputs[0], vor, "Vector")
    pore = s.remap(vor.outputs["Distance"], "Recessed boundaries", (.025,.19), (0,1), -600, 480)
    grain = s.noise("Fracture facets", 640, 2, -850, 100)
    relief = s.math("ADD", pore, grain, "Broken crumb faces", -300, 250)
    color = s.remap(relief, "Charcoal facets", (.25,1.8), (.002,.027), 70, 450)
    s.link(color, s.bsdf, "Base Color")
    s.bsdf.inputs["Roughness"].default_value = .83
    s.bump(relief, .00086, .72)
    return s.mat


def build_tiles(ob, boxes, surface, side):
    """Closed slabs with a round-over confined to the top edge and a thin pressed skin."""
    vertices, faces, materials, lip_weights = [], [], [], []
    for x0,x1,y0,y1,z0,z1 in boxes:
        rings = [(0,z0), (0,z1-.002), (0,z1-RADIUS)]
        for step in range(1,5):
            a = math.pi * step / 8
            rings.append((RADIUS*(1-math.cos(a)), z1-RADIUS+RADIUS*math.sin(a)))
        # Fade the pressed lip into the top over another millimetre. No duplicate seam grid.
        rings.append((RADIUS + .0011, z1))
        base = len(vertices)
        for row, (inset, z) in enumerate(rings):
            weight = 0 if row == len(rings)-1 else min(1, .66 + (z1-z)/RADIUS)
            lip_weights.extend([weight]*4)
            vertices.extend([(x0+inset,y0+inset,z),(x1-inset,y0+inset,z),
                             (x1-inset,y1-inset,z),(x0+inset,y1-inset,z)])
        faces.append(tuple(base+i for i in (3,2,1,0)))
        materials.append(1)
        for row in range(len(rings)-1):
            for k in range(4):
                i = base+4*row+k
                j = base+4*row+(k+1)%4
                faces.append((i,j,j+4,i+4))
                materials.append(1 if row==0 else 0)
        faces.append(tuple(range(len(vertices)-4,len(vertices))))
        materials.append(0)
    mesh = ob.data
    mesh.clear_geometry()
    mesh.from_pydata(vertices, [], faces)
    attribute = mesh.attributes.get("pressed_lip") or mesh.attributes.new("pressed_lip", "FLOAT", "POINT")
    attribute.data.foreach_set("value", lip_weights)
    mesh.materials.clear()
    for mat in (surface,side):
        mesh.materials.append(mat)
    for slot,mat in zip(ob.material_slots,(surface,side)):
        slot.material = mat
    mesh.polygons.foreach_set("material_index", materials)
    mesh.update()


def apply():
    machine, heavy, platform = [bpy.data.objects[name] for name in TARGETS]
    if any(o.data.users != 1 for o in (machine, heavy, platform)):
        raise ValueError("Expected three private rubber floor meshes")
    image = bpy.data.images.get("D8floor_PressedEPDM")
    if image is None:
        image = bpy.data.images.load(str(MAP))
        image.name = "D8floor_PressedEPDM"
        image.pack()
        if bpy.data.filepath:
            image.filepath = bpy.path.relpath(str(MAP))
    top = top_material("Machine", (-7.8,-6.8), .6, image)
    impact = top_material("Impact", (FW_X[0],FW_Y[1]), 1, image)
    platform_top = top_material("Platform", (1.69,2.24), 3, image)
    side = crumb_material()
    old_bevel = machine.modifiers.get("Soft rubber edges")
    if old_bevel:
        machine.modifiers.remove(old_bevel)
    half = (.6-GAP)/2
    build_tiles(machine, [(-half,half,-half,half,-.01,.01)], top, side)
    boxes = []
    y = FW_Y[1]
    while y > FW_Y[0]+1e-6:
        x = FW_X[0]
        while x < FW_X[1]-1e-6:
            x1 = min(x+1, FW_X[1])
            boxes.append((x+GAP/2,x1-GAP/2,max(y-1,FW_Y[0])+GAP/2,y-GAP/2,-.004,FW_TOP))
            x = x1
        y -= 1
    build_tiles(heavy, boxes, impact, side)
    build_tiles(platform, [(-1.2,1.2,-1.15,1.15,-.012,.012)], platform_top, side)
    bpy.context.view_layer.update()
    return TARGETS


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    print("Updated rubber tiles", apply())
    if args.save:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(args.save.resolve()), compress=True)
