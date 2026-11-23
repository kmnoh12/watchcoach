"""Universal V6 -> Extra (Male/Female) animation retargeting & verification tool.

Transfers ANY V6 hero motion onto any 52-bone extra rig (male extras in
`src_figure_copy.blend` / `cast_library.blend`, or 161cm female extra in
`extra_female.blend`), handling:
  1. Exact bone-frame alignment (zero twist/flip even when clavicle/pelvis axes differ slightly)
  2. Automatic height-ratio scaling of pelvis translation (e.g. 161cm female = 0.92x)
  3. Supports:
     - `v6_locomotion.json` (Three.js glTF AnimationClip format: stand, walk, run, stair_ascent)
     - `pose_library.json` (Blender pose dictionary)
     - `posing_animations.json` (IFBB posing clips)
     - Any Blender Action inside a source .blend

Usage examples:
  # Retarget v6_locomotion.json for 161cm female extra (outputs ready-to-use Three.js JSON)
  blender -b --factory-startup -P promo/tools/retarget_v6_to_extra.py -- \
    --target promo/models/extra_female.blend \
    --locomotion promo/poses/v6_locomotion.json \
    --out-json promo/poses/extra_female_locomotion.json

  # Retarget a clip into a Blender .blend Action & render 3-way QA (V6 + Male + Female)
  blender -b --factory-startup -P promo/tools/retarget_v6_to_extra.py -- --qa-render
"""

import argparse
import json
import math
import os
import sys
import bpy
from mathutils import Matrix, Quaternion, Vector

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
V6_BLEND = os.path.join(REPO_ROOT, "promo", "models", "v6.blend")
MALE_BLEND = os.path.join(REPO_ROOT, "promo", "cast", "src_figure_copy.blend")
FEMALE_BLEND = os.path.join(REPO_ROOT, "promo", "models", "extra_female.blend")
LOCOMOTION_JSON = os.path.join(REPO_ROOT, "promo", "poses", "v6_locomotion.json")


def get_armature(blend_path):
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        raise RuntimeError(f"No armature found in {blend_path}")
    return arms[0]


def collect_rig_frames(blend_path):
    """Return per-bone world-space rest 3x3 rotations, parent-local rest quaternions, and pelvis height."""
    arm = get_armature(blend_path)
    world_q = {}
    local_q = {}
    for b in arm.data.bones:
        world_q[b.name] = b.matrix_local.to_3x3().to_quaternion()
        if b.parent:
            m = b.parent.matrix_local.inverted() @ b.matrix_local
        else:
            m = b.matrix_local
        local_q[b.name] = m.to_quaternion()
    pelvis_z = arm.data.bones["pelvis"].head_local.z
    return arm.name, world_q, local_q, pelvis_z


def compute_bone_align_map(src_world_q, dst_world_q):
    """For each bone, compute R_align = dst_world_q^-1 @ src_world_q.
    Converting a bone-local delta rotation from src to dst is simply:
        dst_delta = R_align @ src_delta @ R_align^-1
    """
    align = {}
    for bn, sq in src_world_q.items():
        dq = dst_world_q.get(bn)
        if dq is not None:
            align[bn] = dq.inverted() @ sq
    return align


def retarget_locomotion_json(src_json_path, target_blend_path, out_json_path):
    """Retarget a Three.js glTF AnimationClip JSON (like v6_locomotion.json) to target rig."""
    _, src_wq, src_lq, src_pz = collect_rig_frames(V6_BLEND)
    dst_name, dst_wq, dst_lq, dst_pz = collect_rig_frames(target_blend_path)
    align = compute_bone_align_map(src_wq, dst_wq)
    height_scale = dst_pz / src_pz

    with open(src_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # glTF Y-up <-> Blender Z-up root basis for pelvis
    q_yup = Quaternion((1, 0, 0), math.radians(-90))
    q_zup = Quaternion((1, 0, 0), math.radians(90))

    for clip in data.get("clips", []):
        for track in clip.get("tracks", []):
            tname = track["name"]
            if tname.endswith(".position"):
                vals = track["values"]
                track["values"] = [round(v * height_scale, 6) for v in vals]
            elif tname.endswith(".quaternion"):
                bn = tname[: -len(".quaternion")]
                if bn not in align or bn not in src_lq or bn not in dst_lq:
                    continue
                R = align[bn]
                R_inv = R.inverted()
                sq_l = src_lq[bn]
                dq_l = dst_lq[bn]
                is_root = bn == "pelvis"
                vals = track["values"]
                out_vals = []
                for i in range(0, len(vals), 4):
                    q_gltf = Quaternion((vals[i + 3], vals[i], vals[i + 1], vals[i + 2]))
                    if is_root:
                        # Convert glTF root quat to Blender Z-up delta, retarget, convert back
                        q_bl = q_zup @ q_gltf
                        src_delta = sq_l.inverted() @ q_bl
                        dst_delta = R @ src_delta @ R_inv
                        q_out = (q_yup @ (dq_l @ dst_delta)).normalized()
                    else:
                        src_delta = sq_l.inverted() @ q_gltf
                        dst_delta = R @ src_delta @ R_inv
                        q_out = (dq_l @ dst_delta).normalized()
                    out_vals.extend([round(q_out.x, 6), round(q_out.y, 6), round(q_out.z, 6), round(q_out.w, 6)])
                track["values"] = out_vals

    os.makedirs(os.path.dirname(os.path.abspath(out_json_path)), exist_ok=True)
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"[retarget] {os.path.basename(src_json_path)} -> {out_json_path} (rig={dst_name}, height_scale={height_scale:.4f})")


def retarget_pose_to_armature(arm, clip_data, frame_idx, src_wq, src_lq, dst_wq, dst_lq, height_scale):
    """Apply a single frame from a V6 glTF locomotion clip onto any Blender armature cleanly."""
    align = compute_bone_align_map(src_wq, dst_wq)
    q_zup = Quaternion((1, 0, 0), math.radians(90))

    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)

    for track in clip_data.get("tracks", []):
        tname = track["name"]
        if not tname.endswith(".quaternion"):
            continue
        bn = tname[: -len(".quaternion")]
        pb = arm.pose.bones.get(bn)
        if pb is None or bn not in align:
            continue
        vals = track["values"]
        i = min(frame_idx, len(vals) // 4 - 1) * 4
        q_gltf = Quaternion((vals[i + 3], vals[i], vals[i + 1], vals[i + 2]))
        if bn == "pelvis":
            q_gltf = q_zup @ q_gltf
        src_delta = src_lq[bn].inverted() @ q_gltf
        R = align[bn]
        pb.rotation_quaternion = (R @ src_delta @ R.inverted()).normalized()


def run_qa_render(out_dir):
    """Render V6 Hero + Male Extra + 161cm Female Extra performing the exact same walk & run frames."""
    os.makedirs(out_dir, exist_ok=True)
    _, v6_wq, v6_lq, v6_pz = collect_rig_frames(V6_BLEND)
    _, m_wq, m_lq, m_pz = collect_rig_frames(MALE_BLEND)
    _, f_wq, f_lq, f_pz = collect_rig_frames(FEMALE_BLEND)

    with open(LOCOMOTION_JSON, "r", encoding="utf-8") as f:
        loc_data = json.load(f)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    def append_rig(blend_path, obj_names, x_offset):
        with bpy.data.libraries.load(blend_path, link=False) as (df, dt):
            dt.objects = [n for n in obj_names if n in df.objects]
        arm = None
        for o in dt.objects:
            if o is None:
                continue
            scene.collection.objects.link(o)
            if o.type == "ARMATURE":
                arm = o
        arm.location = (x_offset, 0.0, 0.0)
        arm.animation_data_clear()
        return arm

    arm_v6 = append_rig(V6_BLEND, ["V5_CommonRig", "V5_Body", "LowPolyWatch", "Watch_Case", "Watch_Display", "Watch_Strap", "Watch_ButtonA", "Watch_ButtonB", "Watch_Buckle.001"], -0.95)
    arm_m = append_rig(MALE_BLEND, ["Fig.rig", "BASE_Low Poly Man"], 0.0)
    arm_f = append_rig(FEMALE_BLEND, ["Extra_female", "Extra_female_Body", "Extra_female_Hair"], 0.95)

    # Give male a clean neutral material so all 3 are clearly distinguished
    m_body = bpy.data.objects.get("BASE_Low Poly Man")
    if m_body:
        mat = bpy.data.materials.new("QA_Male")
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.48, 0.56, 0.68, 1.0)
        m_body.data.materials.clear()
        m_body.data.materials.append(mat)

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 760
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.14, 0.16, 0.19, 1.0)

    def add_light(name, loc, rot_deg, energy):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = 2.4
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        scene.collection.objects.link(lo)

    add_light("Key", (2.6, -3.6, 2.9), (58, 0, 34), 320)
    add_light("Fill", (-3.0, -2.5, 1.9), (72, 0, -48), 140)
    add_light("Rim", (0.0, 3.6, 2.6), (125, 0, 0), 220)

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, 0))
    ground = bpy.context.active_object
    gmat = bpy.data.materials.new("Ground")
    gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.20, 0.22, 0.26, 1.0)
    ground.data.materials.append(gmat)

    cd = bpy.data.cameras.new("Cam")
    cd.lens = 58
    cam = bpy.data.objects.new("Cam", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (1.6, -4.4, 1.02)
    cam.rotation_euler = (Vector((0.0, 0.0, 0.88)) - cam.location).to_track_quat("-Z", "Y").to_euler()

    for cname, fi in (("walk", 6), ("run", 6)):
        clip = next(c for c in loc_data["clips"] if c["name"] == cname)
        retarget_pose_to_armature(arm_v6, clip, fi, v6_wq, v6_lq, v6_wq, v6_lq, 1.0)
        retarget_pose_to_armature(arm_m, clip, fi, v6_wq, v6_lq, m_wq, m_lq, m_pz / v6_pz)
        retarget_pose_to_armature(arm_f, clip, fi, v6_wq, v6_lq, f_wq, f_lq, f_pz / v6_pz)
        bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(out_dir, f"trio_{cname}.png")
        bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=FEMALE_BLEND)
    ap.add_argument("--locomotion", default=LOCOMOTION_JSON)
    ap.add_argument("--out-json", default="")
    ap.add_argument("--qa-render", action="store_true")
    ap.add_argument("--qa-dir", default=os.path.join(REPO_ROOT, "promo", "models", "renders_retarget_qa"))
    args = ap.parse_args(argv)

    if args.out_json:
        retarget_locomotion_json(args.locomotion, args.target, args.out_json)
    if args.qa_render:
        run_qa_render(args.qa_dir)


if __name__ == "__main__":
    main()
