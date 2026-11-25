"""Install the reception sign into the current gym scene, without saving it."""
import gzip
import json
from pathlib import Path

import bpy


_ASSET = Path(__file__).resolve().parents[1] / "parts/detail_info_main_sign/sign.json.gz"
# Viewport fallback (linear RGB, metallic, roughness) and flat BSDF defaults.
# Galvanized frame and expanded-metal mesh build procedural PBR node trees below.
_FINISHES = (
    ("Backpan", (0.010, 0.011, 0.012), 0.0, 0.90),
    ("Frame", (0.76, 0.79, 0.83), 0.78, 0.26),
    ("ExpandedMetal", (0.24, 0.26, 0.29), 0.62, 0.29),
    ("Raceway", (0.012, 0.013, 0.014), 0.0, 0.43),
    ("LetterReturn", (0.057, 0.059, 0.062), 0.56, 0.33),
    ("OpalFace", (0.94, 0.925, 0.90), 0.0, 0.32),
)


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


def _build_galvanized_frame(tree, bsdf):
    """Bright silver galvanized steel (spangle crystals + broad mottled sheen)."""
    nodes, links = tree.nodes, tree.links

    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 0)

    # Crystalline zinc spangle (~18mm cells along mullions/header).
    vor = nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-680, 220)
    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 55.0
    vor.inputs["Randomness"].default_value = 0.85
    links.new(tc.outputs["Object"], vor.inputs["Vector"])

    spangle = nodes.new("ShaderNodeRGBToBW")
    spangle.location = (-460, 220)
    links.new(vor.outputs["Color"], spangle.inputs["Color"])

    # Broad mottled oxidation / mill-sheen patches (~250mm scale).
    mottle = nodes.new("ShaderNodeTexNoise")
    mottle.location = (-680, -20)
    mottle.noise_dimensions = "3D"
    mottle.inputs["Scale"].default_value = 3.8
    mottle.inputs["Detail"].default_value = 6.0
    mottle.inputs["Roughness"].default_value = 0.60
    mottle.inputs["Distortion"].default_value = 0.15
    links.new(tc.outputs["Object"], mottle.inputs["Vector"])

    # Fine rolled-metal micro-grain.
    fine = nodes.new("ShaderNodeTexNoise")
    fine.location = (-680, -260)
    fine.noise_dimensions = "3D"
    fine.inputs["Scale"].default_value = 85.0
    fine.inputs["Detail"].default_value = 4.0
    fine.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], fine.inputs["Vector"])

    # Blend 0.35 * spangle + 0.50 * mottle + 0.15 * fine.
    m_sp = nodes.new("ShaderNodeMath")
    m_sp.operation = "MULTIPLY"
    m_sp.inputs[1].default_value = 0.35
    links.new(spangle.outputs["Val"], m_sp.inputs[0])

    m_mo = nodes.new("ShaderNodeMath")
    m_mo.operation = "MULTIPLY"
    m_mo.inputs[1].default_value = 0.50
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

    # Cool bright silver-zinc Base Color variation.
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-60, 240)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.72, 0.76, 0.81, 1.0)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (0.91, 0.94, 0.97, 1.0)
    links.new(galva_fac.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    # Metallic varies subtly between oxidized zinc (0.72) and bright crystal (0.84).
    met_map = nodes.new("ShaderNodeMapRange")
    met_map.location = (-60, 20)
    met_map.clamp = True
    met_map.inputs[1].default_value = 0.25
    met_map.inputs[2].default_value = 0.78
    met_map.inputs[3].default_value = 0.72
    met_map.inputs[4].default_value = 0.84
    links.new(galva_fac.outputs[0], met_map.inputs[0])
    links.new(met_map.outputs[0], bsdf.inputs["Metallic"])

    # Brighter crystals are glossier (0.18); duller mottled patches are satin (0.38).
    rgh_map = nodes.new("ShaderNodeMapRange")
    rgh_map.location = (-60, -180)
    rgh_map.clamp = True
    rgh_map.inputs[1].default_value = 0.25
    rgh_map.inputs[2].default_value = 0.78
    rgh_map.inputs[3].default_value = 0.38
    rgh_map.inputs[4].default_value = 0.18
    links.new(galva_fac.outputs[0], rgh_map.inputs[0])
    links.new(rgh_map.outputs[0], bsdf.inputs["Roughness"])

    bsdf.inputs["Specular IOR Level"].default_value = 0.60
    bsdf.inputs["Coat Weight"].default_value = 0.18
    bsdf.inputs["Coat Roughness"].default_value = 0.10

    # Micro-facet spangle bump breaks flat reflection uniformity.
    b_sp = nodes.new("ShaderNodeMath")
    b_sp.operation = "MULTIPLY"
    b_sp.inputs[1].default_value = 0.60
    links.new(spangle.outputs["Val"], b_sp.inputs[0])

    b_fi = nodes.new("ShaderNodeMath")
    b_fi.operation = "MULTIPLY"
    b_fi.inputs[1].default_value = 0.40
    links.new(fine.outputs["Fac"], b_fi.inputs[0])

    b_sum = nodes.new("ShaderNodeMath")
    b_sum.operation = "ADD"
    links.new(b_sp.outputs[0], b_sum.inputs[0])
    links.new(b_fi.outputs[0], b_sum.inputs[1])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (40, -380)
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.0015
    links.new(b_sum.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _build_expanded_metal(tree, bsdf):
    """Dark gunmetal expanded mesh whose diamond strands catch lobby light cleanly."""
    nodes, links = tree.nodes, tree.links

    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (-820, 0)

    grain = nodes.new("ShaderNodeTexNoise")
    grain.location = (-580, 120)
    grain.noise_dimensions = "3D"
    grain.inputs["Scale"].default_value = 18.0
    grain.inputs["Detail"].default_value = 5.0
    grain.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], grain.inputs["Vector"])

    micro = nodes.new("ShaderNodeTexNoise")
    micro.location = (-580, -140)
    micro.noise_dimensions = "3D"
    micro.inputs["Scale"].default_value = 110.0
    micro.inputs["Detail"].default_value = 4.0
    micro.inputs["Roughness"].default_value = 0.55
    links.new(tc.outputs["Object"], micro.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-160, 180)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.24, 0.26, 0.29, 1.0)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (0.36, 0.38, 0.42, 1.0)
    links.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    bsdf.inputs["Metallic"].default_value = 0.62

    rgh_map = nodes.new("ShaderNodeMapRange")
    rgh_map.location = (-160, -40)
    rgh_map.clamp = True
    rgh_map.inputs[1].default_value = 0.25
    rgh_map.inputs[2].default_value = 0.78
    rgh_map.inputs[3].default_value = 0.38
    rgh_map.inputs[4].default_value = 0.22
    links.new(grain.outputs["Fac"], rgh_map.inputs[0])
    links.new(rgh_map.outputs[0], bsdf.inputs["Roughness"])

    bsdf.inputs["Specular IOR Level"].default_value = 0.65

    bump = nodes.new("ShaderNodeBump")
    bump.location = (20, -220)
    bump.inputs["Strength"].default_value = 0.035
    bump.inputs["Distance"].default_value = 0.001
    links.new(micro.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def apply():
    root = bpy.context.scene.objects["Gym_InfoDesk"]
    old = [obj for obj in bpy.context.scene.objects
           if obj.parent == root and obj.name.startswith("InfoLogo_")]
    collection = old[0].users_collection[0] if old else root.users_collection[0]
    with gzip.open(_ASSET, "rt", encoding="utf-8") as source:
        asset = json.load(source)

    mesh = bpy.data.meshes.new("Reception sign assembly")
    mesh.from_pydata([(-x/1000, depth/1000, up/1000) for x, up, depth in asset["vertices"]],
                     [], asset["faces"])
    for finish, color, metallic, roughness in _FINISHES:
        name = "InfoMainSign_" + finish
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name)
        mat.diffuse_color = (*color, 1)
        mat.metallic = metallic
        mat.roughness = roughness
        tree, shader = _reset_tree(mat)
        if finish == "Frame":
            _build_galvanized_frame(tree, shader)
        elif finish == "ExpandedMetal":
            _build_expanded_metal(tree, shader)
        else:
            shader.inputs["Base Color"].default_value = (*color, 1)
            shader.inputs["Metallic"].default_value = metallic
            shader.inputs["Roughness"].default_value = roughness
            if finish == "Backpan":
                shader.inputs["Specular IOR Level"].default_value = 0.10
            elif finish == "OpalFace":
                shader.inputs["Emission Color"].default_value = (1, 0.975, 0.93, 1)
                shader.inputs["Emission Strength"].default_value = 3.2
        mesh.materials.append(mat)
    mesh.polygons.foreach_set("material_index", asset["material"])
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
    return obj
