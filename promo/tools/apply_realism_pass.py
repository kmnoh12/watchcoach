"""Apply the photorealism overhaul pass (all 8 DETAIL_* areas) to the open gym scene.

Run headless:
    Blender -b promo/scenes/scene_gym.blend --python promo/tools/apply_realism_pass.py [-- --save]

Every module is idempotent, preserves cameras, armatures, actions, and TossFront* objects,
and packs all newly introduced textures into the blend file.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parent / "realism_pass"
MODULES = ("hall_structure", "hall_props", "gym_structure", "gym_fixtures")
REQUIRED_COLLECTIONS = {
    "hall_surfaces", "hall_storefronts", "hall_props", "gym_floor",
    "gym_ceiling", "gym_wall_graphics", "gym_counter", "gym_freeweight",
}


def _protected(scene):
    return (
        scene.render.engine,
        scene.camera.name if scene.camera else None,
        scene.frame_start,
        scene.frame_end,
        scene.render.fps,
        tuple(
            sorted(
                (o.name, tuple(tuple(row) for row in o.matrix_world), o.data.name if o.data else None)
                for o in scene.objects
                if o.type in {"CAMERA", "ARMATURE"} or o.name.startswith("TossFront")
            )
        ),
        tuple(sorted(a.name for a in bpy.data.actions)),
    )


def apply():
    missing = [n for n in sorted(REQUIRED_COLLECTIONS) if not bpy.data.collections.get(f"DETAIL_{n}")]
    assert not missing, f"Missing required DETAIL_* collections: {missing}"
    scene = bpy.context.scene
    original = _protected(scene)
    results = {}
    for mod_name in MODULES:
        path = ROOT / f"{mod_name}.py"
        spec = spec_from_file_location(f"_realism_{mod_name}", path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        results[mod_name] = module.apply()
    bpy.context.view_layer.update()
    assert original == _protected(scene), "Camera, animation, armature, or TossFront changed"
    for image in bpy.data.images:
        if image.source == "FILE" and image.users and not image.packed_file:
            assert Path(bpy.path.abspath(image.filepath)).is_file(), f"Missing image: {image.name}"
    return results


if __name__ == "__main__":
    print("REALISM_PASS", apply(), flush=True)
    if "--save" in sys.argv:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_mainfile()
        print("REALISM_PASS saved", bpy.data.filepath, flush=True)
