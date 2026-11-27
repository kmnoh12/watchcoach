"""Re-fit the saved gym casting to the upper stations without saving the Blender scene."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import casting

# Shared oval bores cover the two native guide spacings after instance scaling.
GUIDES = ((-.116, .028, .024), (0, .025, .025), (.116, .028, .024))


def extract():
    return {
        # The lateral machine has a shallow selector tongue 9 mm above the
        # plate center. Its shallow mouth relief is part of the shared casting.
        "stack_casting": casting(
            True, guides=GUIDES, socket=(.0255, .023),
            front_relief=([-.029, -.150, -.010], [.029, -.128, .048]),
        ),
    }


if __name__ == "__main__":
    result = extract()
    path = Path(__file__).with_name("scene_press_source.json")
    encoded = json.dumps(result, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == encoded
    else:
        path.write_text(encoded)
    print({name: sum(len(p["t"]) // 3 for p in slots) for name, slots in result.items()})
