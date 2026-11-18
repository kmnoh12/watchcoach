"""Build the editable, camera-directed rest timer Reel with Blender 5.2."""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

PROMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROMO / "tools"))
import make_reel
import wc_lib as W

shot = json.loads((PROMO / "shots/rest_timer_reel.json").read_text(encoding="utf-8-sig"))
scene = make_reel.build(shot)
fx = W.coll("FX")

def frame_camera(name, location, subject, lens):
    camera = bpy.data.objects[name]
    camera.location = location
    camera.rotation_euler = (Vector(subject) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = lens
    return camera

opening = frame_camera("Cam_Front", (-0.2, -3.2, 1.55), (0, -0.4, 1.57), 46)
detail = frame_camera("Cam_Side", (0.43, -1.23, 0.67), (0.15, -0.77, 1.17), 60)
closing = frame_camera("Cam_Low", (-0.2, -3.2, 1.55), (0, -0.4, 1.68), 43)

# Units below use the full frame height, centered on the camera.
ink = (0.009, 0.018, 0.023)
mint = (0.20, 1.0, 0.59)
paper = (0.96, 0.98, 0.96)

def anchor(obj, camera, x, y, depth):
    height = 2 * depth * max(abs(v.y / v.z) for v in camera.data.view_frame(scene=scene))
    obj.parent = camera
    obj.location = (x * height, y * height, -depth)
    obj.scale = (height,) * 3

def plate(name, camera, top, bottom, color, start, end, left=-0.285, right=0.285):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(left, bottom, 0), (right, bottom, 0), (right, top, 0), (left, top, 0)], [], [(0,1,2,3)])
    obj = bpy.data.objects.new(name, mesh)
    fx.objects.link(obj)
    obj.data.materials.append(W.shadeless(name, color))
    anchor(obj, camera, 0, 0, 0.135)
    W.hide_until(obj, start, end)
    return obj

def label(name, camera, text, y, size, color, start, end):
    obj = W._text(name, text, size, color, fx, font=W.KFONT, extrude=0)
    obj.data.align_x = "LEFT"
    anchor(obj, camera, -0.229, y, 0.12)
    W.hide_until(obj, start, end)
    return obj

for camera, start, end, kicker, headline, second in [
    (opening, 1, 73, "세트 사이", "몇 초 남았지?", ""),
    (detail, 73, 154, "휴식 타이머", "시간이 다 되면", "손목에서 진동."),
    (closing, 154, 211, "워치코치", "WatchCoach", "다음 세트, 시작.")
]:
    plate(camera.name+" · panel", camera, 0.515, 0.16, ink, start, end)
    plate(camera.name+" · rule", camera, 0.164, 0.16, mint, start, end)
    label(camera.name+" · eyebrow", camera, kicker, 0.355, 0.035, mint, start, end)
    label(camera.name+" · title", camera, headline, 0.280 if second else 0.246, 0.066, paper, start, end)
    if second:
        label(camera.name+" · subtitle", camera, second, 0.207, 0.050, paper, start, end)

# Graphic haptic pulses stay legible at phone size.
from math import cos, sin, radians
for beat, (start, end) in enumerate([(78, 92), (103, 116)]):
    for side in (-1, 1):
        for lane in range(2):
            curve = bpy.data.curves.new("Haptic pulse", "CURVE")
            curve.dimensions = "3D"
            curve.bevel_depth = 0.0028
            curve.bevel_resolution = 3
            spline = curve.splines.new("POLY")
            spline.points.add(16)
            radius = 0.088 + lane * 0.019
            for i, pt in enumerate(spline.points):
                angle = radians(-38 + 76 * i / 16)
                pt.co = (-0.017 + side * radius * cos(angle), -0.075 + radius * sin(angle), 0, 1)
            obj = bpy.data.objects.new(f"Pulse {beat+1}-{side}-{lane}", curve)
            fx.objects.link(obj)
            curve.materials.append(W.shadeless("Signal mint", mint))
            anchor(obj, detail, 0, 0, 0.13)
            W.hide_until(obj, start + lane * 2, end)

scene.frame_set(1)
scene.render.resolution_percentage = 100
out_dir = PROMO / "renders/reels"
out_dir.mkdir(parents=True, exist_ok=True)
W.set_video_output("//../../renders/reels/rest_timer_reel.mp4")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.file.pack_all()
W.save(str(PROMO / "scenes/reels/rest_timer_reel.blend"))
