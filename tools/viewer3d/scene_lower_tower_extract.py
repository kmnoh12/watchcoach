"""Extract the common lower-stack casting and full leg-extension roller from scene_gym.blend."""

import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import casting, mesh, slots


def extract():
    v, t, m = mesh("Ddetail6_SM_LE_ShinRoller", "P_leg_lever")
    v -= (v.min(0) + v.max(0)) / 2
    assert len(t) == 1216 and set(m) == {0, 1}
    # App rollers use local Z as the axle. Preserve winding and all the molded rings.
    roller = slots(v[:, [2, 1, 0]] * [-1, 1, 1], t, m)
    return {
        # The torso selector enters 15 mm above its plate center. The shared
        # bore retains clearance for that pin as well as the centered pins.
        "stack_casting": casting(True, guides=((-0.115, 0.035, 0.035), (0, 0.035, 0.035), (0.115, 0.035, 0.035)),
                                 socket=(0.029, 0.027), socket_z=0.006),
        "leg_roller": roller,
    }


if __name__ == "__main__":
    out = Path(__file__).with_name("scene_lower_tower_source.json")
    encoded = json.dumps(extract(), separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert out.read_text() == encoded
    else:
        out.write_text(encoded)
