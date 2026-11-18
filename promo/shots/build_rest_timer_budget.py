"""Build the budget master and render its approved 72 samples from the 30 fps motion."""
import math
import sys
import time
from pathlib import Path
import bpy
import gpu

promo = Path(__file__).resolve().parents[1]
work = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
work.mkdir(parents=True, exist_ok=True)
s = bpy.context.scene
for cam in ("Cam_Front", "Cam_Side", "Cam_Low"):
    for suffix in ("panel", "rule", "eyebrow", "title", "subtitle"):
        obj = bpy.data.objects.get(f"{cam} · {suffix}")
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
intervals = [(0,26,4),(26,34,2),(34,50,4),(50,58,1),(58,61,4),
             (61,62,2),(62,64,2),(64,73,2),(73,74,2),(74,82,4),
             (82,84,2),(84,92,2),(92,93,2),(93,115,4),(115,123,1),
             (123,144,4),(144,152,1),(152,168,4)]
samples = [n for a,b,step in intervals for n in range(a,b,step)]
assert len(samples) == 72
s.eevee.taa_render_samples = 16
s.render.filepath = "//../../renders/reels/rest_timer_reel_budget.mp4"
s["Delivery fps"] = 24
s["Delivery sample indices (zero-based)"] = samples
s["Source timing"] = "30 fps editable motion; delivery samples source frame 1+1.25*n."
bpy.context.preferences.filepaths.save_version = 0
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(promo / "scenes/reels/rest_timer_reel_budget.blend"), compress=True)
s.render.image_settings.media_type = "IMAGE"
s.render.image_settings.file_format = "PNG"
s.render.image_settings.color_mode = "RGB"
s.render.image_settings.compression = 15
gpu.init()
print("GPU",gpu.platform.renderer_get(),s.render.engine,s.eevee.taa_render_samples,flush=True)
preview = "--preview" in sys.argv
if preview:
    s.render.resolution_percentage = 40
started = time.perf_counter()
for n in ([12,84,155] if preview else samples):
    src = 1 + 1.25*n
    s.frame_set(math.floor(src), subframe=src%1)
    s.render.filepath = str(work / (("preview" if preview else "sample") + f"_{n:03d}.png"))
    tick = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    print("SAMPLE",n,round(time.perf_counter()-tick,3),flush=True)
print("ELAPSED",round(time.perf_counter()-started,2),flush=True)
