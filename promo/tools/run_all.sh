#!/bin/bash
# Rebuild everything: scene frames, asset libraries + QA + sheets, key art, then the 10 s test cut.
cd "$(dirname "$0")/.."
B="${BLENDER_BIN:-blender}"
set -e
"$B" -b --factory-startup --python-exit-code 1 -P tools/build_scenes.py -- all 2>&1 | grep -E "@@JSON|Error|Traceback" || true
for s in cast props cameos fx group; do  # gymqa (slow, 10 rounds) only when the gym builder changes
  "$B" -b --factory-startup --python-exit-code 1 -P tools/build_assets.py -- "$s" 2>&1 | grep -E "@@JSON|Error|Traceback" || true
done
mkdir -p renders/reels
"$B" -b --factory-startup --python-exit-code 1 -P tools/make_reel.py -- shots/test_plate_meme.json > renders/reels/render_log.txt 2>&1
tail -2 renders/reels/render_log.txt
