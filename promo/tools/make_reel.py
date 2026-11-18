"""Turn one shot file (JSON) into a vertical reel: scene frame + cast + poses + lines + cameos + fx -> .blend + .mp4

Run: Blender -b --factory-startup -P tools/make_reel.py -- shots/my_shot.json [--preview] [--still SECONDS] [--no-render]

Times are in seconds (30 fps; frame = 1 + t*30). Poses are held until the next pose of the same character.
See shots/example_plate_meme.json and README.md for every field.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wc_lib as W  # noqa: E402

INTERP = {"constant": "CONSTANT", "linear": "LINEAR", "smooth": "BEZIER", "bezier": "BEZIER"}


def F(t):
    return 1 + int(round(t * W.FPS))


def cam_at(shot, t):
    cam = shot.get("camera", "Cam_Front")
    for c in sorted(shot.get("cuts", []), key=lambda c: c["t"]):
        if c["t"] <= t + 1e-6:
            cam = c["camera"]
    return bpy.data.objects[cam]


def shot_end_frame(shot):
    return F(shot.get("seconds", 10))


def build(shot, preview=False):
    sc = W.new_scene(shot.get("scene", "flat"), bg=shot.get("bg", "yellow"), preview=preview)
    hold = int(shot.get("hold", W.HOLD))
    sc.frame_start = 1
    sc.frame_end = F(shot.get("seconds", 10)) - 1
    interp = INTERP[shot.get("interp", "smooth")]
    blend = int(shot.get("blend", 6))  # smooth mode: frames spent moving from one pose to the next

    # camera + cuts (timeline markers bound to cameras)
    W.use_camera(shot.get("camera", "Cam_Front"))
    for c in shot.get("cuts", []):
        m = sc.timeline_markers.new("cut_%s" % c["camera"], frame=F(c["t"]))
        m.camera = bpy.data.objects[c["camera"]]
    if shot.get("cuts"):
        m = sc.timeline_markers.new("start", frame=1)
        m.camera = bpy.data.objects[shot.get("camera", "Cam_Front")]

    # cast
    cast = {}
    for c in shot.get("cast", []):
        at = c.get("at", [0, 0])
        loc = (at[0], at[1], 0)
        if c.get("kind", "hero") == "hero":
            a = W.add_hero(c.get("id", "Guy"), loc, c.get("face", 0))
        else:
            a = W.add_extra(c.get("role", "red"), c.get("id"), loc, c.get("face", 0), c.get("height", 1.0), c.get("girth", 1.0))
        for pb in a.pose.bones:
            pb.rotation_mode = "QUATERNION"
        cast[c.get("id", a.name)] = a

    # poses (per character: list of (frame, pose)); "seq" repeats a cycle every `hold` frames until `until`
    W.set_keyed_interp(interp)
    keyed = {k: [] for k in cast}
    for p in shot.get("poses", []):
        a = cast[p["who"]]
        if "seq" in p:
            f, end, i = F(p["t"]), F(p["until"]), 0
            while f < end:
                keyed[p["who"]].append((f, p["seq"][i % len(p["seq"])]))
                f += p.get("hold", hold)
                i += 1
        else:
            keyed[p["who"]].append((F(p["t"]), p["pose"]))
    for who, lst in keyed.items():
        lst = sorted(lst)
        for i, (f, name) in enumerate(lst):
            W.key_pose(cast[who], name, f)
            # smooth: hold the pose, then ease into the next one over `blend` frames
            if interp != "CONSTANT" and i + 1 < len(lst):
                nf = lst[i + 1][0]
                hold_end = nf - blend
                if hold_end > f:
                    W.key_pose(cast[who], name, hold_end)
        W.rest(cast[who])

    # moves: stop-motion stepping (one step per hold) unless interp says otherwise
    for m in shot.get("moves", []):
        a = cast[m["who"]]
        f0, f1 = F(m["t"]), F(m["t"] + m["dur"])
        p0 = Vector(m.get("from", list(a.location)[:2]) + [0])
        p1 = Vector(m["to"] + [0])
        mi = INTERP[m.get("interp", "linear" if interp != "CONSTANT" else "constant")]
        a["wc_move_interp"] = mi
        if "face" in m:
            W.key_transform(a, f0, rot_deg=(0, 0, m["face"]))
        steps = max(1, (f1 - f0) // hold) if mi == "CONSTANT" else 1
        for i in range(steps + 1):
            W.key_transform(a, f0 + i * (f1 - f0) // steps, loc=p0.lerp(p1, i / steps))
    W.set_keyed_interp(interp)

    # props
    for p in shot.get("props", []):
        if "attach" in p:
            W.prop(p["kind"], p.get("loc", (0, 0, 0)), p.get("rot", (0, 0, 0)), parent=cast[p["attach"]], bone=p.get("bone", "hand_r"))
        else:
            r = W.prop(p["kind"], p.get("at", (0, 0, 0)), p.get("rot", (0, 0, 0)))
            if p["kind"] == "wall_clock" and "spin" in p:
                W.clock_spin(r, F(p["spin"]["t"]), F(p["spin"]["t"] + p["spin"].get("dur", 1)) - F(p["spin"]["t"]), p["spin"].get("turns", 2))

    # cameos
    for c in shot.get("cameos", []):
        at = c.get("at")
        if at is None and c.get("move") == "peek":
            at = [-1.2 * -c.get("side", -1) * -1, 1.2, 2.05] if c.get("side", -1) == -1 else [1.2, 1.2, 2.05]
        at = at or [0, 1.0, 2.05]
        r = W.add_cameo(c["who"], at, c.get("size"), c.get("face", 0))
        r["wc_interp"] = INTERP[c.get("interp", "smooth")]
        if c.get("float", True):
            W.cameo_float(r, F(c["t"]), shot_end_frame(shot))
        W.cameo_move(r, c.get("move", "pop"), F(c["t"]), (F(c["t"] + c["dur"]) - F(c["t"])) if "dur" in c else None,
                     at=at, side=c.get("side", -1))
        W.hide_until(r, F(c["t"]), F(c["t_out"]) if "t_out" in c else None)  # invisible before its entrance
        W.set_keyed_interp(interp)

    # fx (after poses: symbols read the head position)
    W.set_keyed_interp("CONSTANT")
    for fx in sorted(shot.get("fx", []), key=lambda x: x["t"]):
        f = F(fx["t"])
        cam = cam_at(shot, fx["t"])
        sc.camera = cam
        typ = fx["type"]
        if typ in ("exclaim", "question", "sweat", "anger", "dots"):
            W.fx_symbol(typ, cast[fx["who"]], f, fx.get("frames", 12))
        elif typ == "flash":
            W.fx_flash(cam, f, tuple(fx.get("color", (1, 1, 1))), fx.get("frames", 2))
        elif typ == "speedlines":
            W.fx_speedlines(cam, f, fx.get("frames", 12), color=tuple(fx.get("color", (1, 1, 1))))
        elif typ == "zoom":
            W.fx_zoom_punch(cam, f, fx.get("frames", 4), fx.get("factor", 1.6))
        elif typ == "shake":
            W.fx_shake(cam, f, fx.get("frames", 10), fx.get("amp", 0.06))
        elif typ == "watch_glow":
            W.watch_glow(fx.get("who", "Guy"), f - 1, on=False)
            W.watch_glow(fx.get("who", "Guy"), f, on=True, strength=fx.get("strength", 5))
            if "frames" in fx:
                W.watch_glow(fx.get("who", "Guy"), f + fx["frames"], on=False)
        elif typ == "watch_buzz":
            W.watch_buzz(f, fx.get("frames", 12))
        else:
            raise ValueError(typ)
    # lines (subtitles; TTS audio is added later in editing)
    for ln in shot.get("lines", []):
        cam = cam_at(shot, ln["t"])
        W.fx_caption(cam, ln["text"], F(ln["t"]), F(ln["t"] + ln.get("dur", 2)) - F(ln["t"]),
                     color=tuple(ln.get("color", (1, 1, 1))))
    W.finalize_interp(interp)
    sc.camera = bpy.data.objects[shot.get("camera", "Cam_Front")]
    sc.frame_set(1)
    return sc


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    path = os.path.abspath(argv[0])
    with open(path) as f:
        shot = json.load(f)
    preview = "--preview" in argv
    sc = build(shot, preview)
    name = os.path.splitext(os.path.basename(path))[0]
    blend = W.save(os.path.join(W.ROOT, "scenes", "reels", name + ".blend"))
    out = {"blend": blend}
    if "--still" in argv:
        t = float(argv[argv.index("--still") + 1])
        out["still"] = W.render_still(os.path.join(W.ROOT, "renders", "reels", f"{name}_t{t:.1f}.png"), F(t))
    elif "--no-render" not in argv:
        mp4 = os.path.join(W.ROOT, "renders", "reels", name + ".mp4")
        W.set_video_output(mp4)
        bpy.ops.render.render(animation=True)
        out["mp4"] = mp4
    print("@@JSON@@" + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
