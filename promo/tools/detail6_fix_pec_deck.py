"""Idempotent ergonomic fix for P_pec_deck resting arm angle & sweep.

Fixes the bug where P_pec_deck forearm/elbow pads and grips start way out in
front of the user's knees (pad center Y = -0.280, 37 cm in front of the
backrest and past the front edge of the seat at Y = -0.250).

Root cause:
  P_Moving assembly.004 (left) and P_Moving assembly.005 (right) pivot around
  the overhead hinges at (+/-0.19, +0.03, 1.47). Their Z-rotation drivers
  previously started at 0.0 rad (swing arms angled ~45 deg forward, putting
  pads at X = +/-0.400, Y = -0.280) and swept only 36 deg (+0.6283 rad) to
  Stroke = 1.0.

Fix:
  Rotate the resting start angle outward/back by 30 deg (-/+0.5235987756 rad)
  while preserving the closed chest-squeeze endpoint at +/-36 deg (+/-0.6283185307 rad),
  giving a realistic 66 deg (1.1519173063 rad) butterfly sweep:
    - Stroke = 0.0: pad center at X = +/-0.527, Y = -0.133 (22.6 cm in front
      of backrest front face Y = +0.093, beside shoulders/upper chest),
      pec_grip Y in [-0.153, -0.114].
    - Stroke = 1.0: pad center at X = +/-0.178, Y = -0.344 (in front of chest,
      zero left/right collision).

Touches ONLY P_pec_deck descendants (P_Moving assembly.004 and .005 drivers).
100% idempotent: calling apply() repeatedly sets the exact same driver
expressions and resting rotations.
"""

from __future__ import annotations

import math
import bpy

START_ANGLE_RAD = -math.radians(30.0)   # -0.5235987755982988 rad (left arm at Stroke=0)
END_ANGLE_RAD = math.radians(36.0)      # +0.6283185307179586 rad (left arm at Stroke=1)
SWEEP_ANGLE_RAD = END_ANGLE_RAD - START_ANGLE_RAD  # 1.1519173063162575 rad (66 deg)

_ARM_SPECS = (
    ("P_Moving assembly.004", +1.0),
    ("P_Moving assembly.005", -1.0),
)


def _ensure_z_rot_driver(obj: bpy.types.Object, root: bpy.types.Object, expr: str) -> str:
    """Set or create the rotation_euler[2] driver driven by P_pec_deck['Stroke']."""
    if obj.animation_data is None:
        obj.animation_data_create()

    target_fc = None
    for fc in obj.animation_data.drivers:
        if fc.data_path == "rotation_euler" and fc.array_index == 2:
            target_fc = fc
            break

    if target_fc is None:
        target_fc = obj.driver_add("rotation_euler", 2)

    drv = target_fc.driver
    drv.type = "SCRIPTED"

    # Ensure variable 'v' points to root["Stroke"]
    var = None
    for existing in drv.variables:
        if existing.name == "v":
            var = existing
            break
    if var is None:
        var = drv.variables.new()
        var.name = "v"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = root
    var.targets[0].data_path = '["Stroke"]'

    drv.expression = expr
    return drv.expression


def apply() -> dict:
    """Apply the P_pec_deck resting arm angle and sweep fix (idempotent)."""
    root = bpy.data.objects.get("P_pec_deck")
    if root is None:
        raise RuntimeError("Object 'P_pec_deck' not found in current blend file.")

    # Verify target arms are actually descendants of P_pec_deck
    descendants = set()
    stack = list(root.children)
    while stack:
        cur = stack.pop()
        descendants.add(cur)
        stack.extend(cur.children)

    updated = {}
    for arm_name, sign in _ARM_SPECS:
        arm = bpy.data.objects.get(arm_name)
        if arm is None or arm not in descendants:
            raise RuntimeError(f"Expected descendant '{arm_name}' of 'P_pec_deck' not found.")

        start_val = sign * START_ANGLE_RAD
        sweep_val = sign * SWEEP_ANGLE_RAD
        expr = f"{start_val:.16f}+{sweep_val:.16f}*v"

        final_expr = _ensure_z_rot_driver(arm, root, expr)
        # Keep resting euler in sync with Stroke=0 even before driver evaluation
        arm.rotation_euler[2] = start_val
        updated[arm_name] = {
            "expression": final_expr,
            "start_deg": round(math.degrees(start_val), 2),
            "end_deg": round(math.degrees(start_val + sweep_val), 2),
        }

    bpy.context.view_layer.update()

    # Compute resulting pad & grip Y/X summary in P_pec_deck local space at current Stroke
    inv_root = root.matrix_world.inverted()
    metrics = {}
    for nm in ("pad", "pad.001", "pec_grip", "pec_grip.001"):
        ob = bpy.data.objects.get(nm)
        if ob is not None and ob.type == "MESH" and ob in descendants:
            pts = [inv_root @ ob.matrix_world @ v.co for v in ob.data.vertices]
            metrics[nm] = {
                "x": [round(min(p.x for p in pts), 3), round(max(p.x for p in pts), 3)],
                "y": [round(min(p.y for p in pts), 3), round(max(p.y for p in pts), 3)],
                "z": [round(min(p.z for p in pts), 3), round(max(p.z for p in pts), 3)],
            }

    return {
        "target": "P_pec_deck",
        "start_angle_deg": round(math.degrees(START_ANGLE_RAD), 2),
        "end_angle_deg": round(math.degrees(END_ANGLE_RAD), 2),
        "sweep_deg": round(math.degrees(SWEEP_ANGLE_RAD), 2),
        "stroke": float(root.get("Stroke", 0.0)),
        "arms": updated,
        "metrics": metrics,
    }


if __name__ == "__main__":
    res = apply()
    print("detail6_fix_pec_deck.apply():", res)
