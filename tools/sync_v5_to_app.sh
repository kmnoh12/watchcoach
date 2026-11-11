#!/bin/zsh
# Keep the phone app's 3D assets in step with the V5 catalog that the PC viewer (localhost:8765) reads live.
# Runs from launchd every 20 s; rebuilds phone/src/main/assets/viewer3d only when a catalog file, the phone viewer or the camera file changed.
# The assets are regenerated files (gitignored). An installed app only changes when you release a new version.
ROOT=${0:A:h:h}
VIEWER="$HOME/Library/Application Support/WatchGymViewer"
EXTRA="$HOME/Documents/Default Project/워치짐/design/exercise-figure/lowpoly-remake/gemini_job/v5_arm_rebuild/app_rollout_20261109/rolling_trial"
STATE="$HOME/Library/Application Support/WatchGymViewer-sync"
mkdir -p "$STATE"
LOCK="$STATE/lock"
mkdir "$LOCK" 2>/dev/null || { [ -n "$(find "$LOCK" -mmin +10 2>/dev/null)" ] && rmdir "$LOCK"; exit 0; }
trap 'rmdir "$LOCK"' EXIT
FP=$( { find "$VIEWER/v5-catalog" -maxdepth 2 -name '*.json' -exec stat -f '%m %z %N' {} +; stat -f '%m %z %N' "$ROOT/tools/viewer3d/index.html" "$ROOT/tools/viewer3d/camera_views.json" "$ROOT/phone/src/main/assets/viewer3d/exercise_models.json"; } 2>/dev/null | sort | shasum | cut -d' ' -f1)
[ "$FP" = "$(cat "$STATE/fingerprint" 2>/dev/null)" ] && exit 0
echo "$(date '+%F %T') change detected, rebuilding" >> "$STATE/sync.log"
if /usr/bin/python3 "$ROOT/tools/build_app3d_v5.py" --extra "$EXTRA" >> "$STATE/sync.log" 2>&1; then
  FP2=$( { find "$VIEWER/v5-catalog" -maxdepth 2 -name '*.json' -exec stat -f '%m %z %N' {} +; stat -f '%m %z %N' "$ROOT/tools/viewer3d/index.html" "$ROOT/tools/viewer3d/camera_views.json" "$ROOT/phone/src/main/assets/viewer3d/exercise_models.json"; } 2>/dev/null | sort | shasum | cut -d' ' -f1)
  echo "$FP2" > "$STATE/fingerprint"; echo "$(date '+%F %T') ok" >> "$STATE/sync.log"
else
  echo "$(date '+%F %T') FAILED (will retry)" >> "$STATE/sync.log"
fi
