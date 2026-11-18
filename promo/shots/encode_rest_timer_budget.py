"""Assemble full-size samples made by build_rest_timer_budget.py into a 24 fps Reel."""
from pathlib import Path
import subprocess
import sys

promo = Path(__file__).resolve().parents[1]
folder = Path(sys.argv[1]).resolve()
samples = sorted(folder.glob("sample_[0-9][0-9][0-9].png"))
indices = [int(p.stem.split("_")[1]) for p in samples]
assert len(indices) == 72 and indices[0] == 0
output = promo / "renders/reels/rest_timer_reel_budget.mp4"
# Each PNG stays on screen until the next explicitly rendered sample.
command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "image2pipe", "-framerate", "24", "-c:v", "png", "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
    for path, start, end in zip(samples, indices, indices[1:] + [168]):
        image = path.read_bytes()
        for n in range(start, end):
            encoder.stdin.write(image)
    encoder.stdin.close()
    if encoder.wait():
        raise RuntimeError("FFmpeg failed")
print(output)
