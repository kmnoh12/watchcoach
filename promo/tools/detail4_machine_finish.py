"""detail4 P5 machine_finish: powder-coat / leather / stack finish on the shared gym equipment materials.

Only values of five shared materials change (E_frame, E_red, E_silver, E_pad, E_stack). Geometry is untouched.
The original node values are snapshotted into each material's custom property `d4mf_orig` on the first run;
every run restores that snapshot first, removes the nodes this module added (prefix `D4mf_`) and applies the
new finish again, so running twice gives the same result.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_machine_finish.py [-- --save out.blend]
"""
import json
import sys

import bpy

KEY = "machine_finish"
COLL = "DETAIL4_machine_finish"   # no new objects in this package; kept for the shared API
PFX = "D4mf_"
PROP = "d4mf_orig"
TARGETS = ("E_frame", "E_red", "E_silver", "E_pad", "E_stack")
BSDF_KEYS = ("Base Color", "Metallic", "Roughness", "Coat Weight", "Coat Roughness", "Specular IOR Level")

# Reference: work/refs/gym/229, 234, 235, interior/128, 076, 077 (semi-gloss powder coat, deep red, satin black).
SPEC = {
    # red frames: deep semi-gloss red (RAL 3020-like, linear G/B ~0) with a clear coat and very light orange peel
    "E_frame": dict(base=(0.56, 0.004, 0.005), rough=(0.29, 0.36), coat=0.22, coat_rough=0.14,
                    peel=(420.0, 0.045), metallic=0.0),
    "E_red": dict(base=(0.56, 0.004, 0.005), rough=(0.29, 0.36), coat=0.22, coat_rough=0.14,
                  peel=(420.0, 0.045), metallic=0.0),
    # "silver" is actually the black frame / selector tower shroud: black satin powder coat (dielectric)
    "E_silver": dict(base=(0.022, 0.023, 0.026), rough=(0.28, 0.36), coat=0.35, coat_rough=0.08,
                     peel=(420.0, 0.035), metallic=0.0),
    # upholstery: black vinyl / faux leather with a fine pebble grain
    "E_pad": dict(base=(0.020, 0.021, 0.024), rough=(0.46, 0.58), coat=0.0, coat_rough=0.03,
                  grain=(650.0, 0.10), metallic=0.0),
    # weight-stack plates: semi-metallic painted steel
    "E_stack": dict(metallic=0.60, rough_value=0.34),
}


def _val(sock):
    v = sock.default_value
    return list(v) if hasattr(v, "__len__") else float(v)


def _snapshot(mat):
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    snap = {"bsdf": {k: _val(bsdf.inputs[k]) for k in BSDF_KEYS}}
    mr = nt.nodes.get("Map Range")
    if mr:
        snap["map_range"] = [_val(mr.inputs["To Min"]), _val(mr.inputs["To Max"])]
    bump = nt.nodes.get("Bump")
    if bump:
        snap["bump"] = [_val(bump.inputs["Strength"]), _val(bump.inputs["Distance"])]
    return snap


def _restore(mat, snap):
    nt = mat.node_tree
    for nd in [n for n in nt.nodes if n.name.startswith(PFX)]:
        nt.nodes.remove(nd)
    bsdf = nt.nodes["Principled BSDF"]
    for k, v in snap["bsdf"].items():
        bsdf.inputs[k].default_value = v
    mr = nt.nodes.get("Map Range")
    if mr and "map_range" in snap:
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = snap["map_range"]
    bump = nt.nodes.get("Bump")
    if bump and "bump" in snap:
        bump.inputs["Strength"].default_value, bump.inputs["Distance"].default_value = snap["bump"]
        noise = nt.nodes.get("Noise Texture")
        if noise and not bump.inputs["Height"].is_linked:
            nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    # original materials never fed the coat normal
    for l in list(nt.links):
        if l.to_node == bsdf and l.to_socket.name == "Coat Normal":
            nt.links.remove(l)


def _tex_coord(nt):
    tc = nt.nodes.get("Texture Coordinate")
    if tc is None:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.name = PFX + "TexCoord"
        tc.location = (-1100, -300)
    return tc


def _apply_paint(mat, s):
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*s["base"], 1.0)
    bsdf.inputs["Metallic"].default_value = s["metallic"]
    bsdf.inputs["Coat Weight"].default_value = s["coat"]
    bsdf.inputs["Coat Roughness"].default_value = s["coat_rough"]
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    mr = nt.nodes["Map Range"]
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = s["rough"]
    bump = nt.nodes["Bump"]
    tc = _tex_coord(nt)
    if "peel" in s:
        scale, strength = s["peel"]
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.name = n.label = PFX + "OrangePeel"
        n.location = (-700, -420)
        n.noise_dimensions = "3D"
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = 2.0
        n.inputs["Roughness"].default_value = 0.45
        nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
        height = n.outputs["Fac"]
        dist = 0.0005
    else:
        scale, strength = s["grain"]
        v = nt.nodes.new("ShaderNodeTexVoronoi")
        v.name = v.label = PFX + "LeatherGrain"
        v.location = (-700, -420)
        v.feature = "SMOOTH_F1"
        v.inputs["Scale"].default_value = scale
        v.inputs["Smoothness"].default_value = 0.6
        nt.links.new(tc.outputs["Object"], v.inputs["Vector"])
        height = v.outputs["Distance"]
        dist = 0.0004
    nt.links.new(height, bump.inputs["Height"])
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = dist
    if s["coat"] > 0:
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Coat Normal"])


def apply() -> dict:
    touched = []
    for name in TARGETS:
        mat = bpy.data.materials.get(name)
        if mat is None or not mat.use_nodes or "Principled BSDF" not in mat.node_tree.nodes:
            print(f"[detail4_{KEY}] skip {name}: missing or unexpected node tree")
            continue
        if PROP not in mat:
            mat[PROP] = json.dumps(_snapshot(mat))
        _restore(mat, json.loads(mat[PROP]))
        s = SPEC[name]
        if name == "E_stack":
            bsdf = mat.node_tree.nodes["Principled BSDF"]
            bsdf.inputs["Metallic"].default_value = s["metallic"]
            bsdf.inputs["Roughness"].default_value = s["rough_value"]
        else:
            _apply_paint(mat, s)
        mat["detail4_pkg"] = KEY
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        mat.diffuse_color = tuple(bsdf.inputs["Base Color"].default_value)
        users = sum(1 for o in bpy.data.objects
                    if o.type == "MESH" and any(sl.material == mat for sl in o.material_slots))
        touched.append({"material": name, "mesh_users": users})
    return {"objects_added": 0, "triangles_added": 0, "materials_touched": touched, "objects_touched": []}


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    res = apply()
    print(f"[detail4_{KEY}] {json.dumps(res)}")
    if "--save" in argv:
        out = argv[argv.index("--save") + 1]
        if "promo/scenes" in out or "promo/models" in out:
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
        print(f"[detail4_{KEY}] saved copy -> {out}")


if __name__ == "__main__":
    _main()
