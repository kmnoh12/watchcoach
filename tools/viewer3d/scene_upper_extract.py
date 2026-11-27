"""Extract the shared wide selector casting from the saved gym scene."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import casting


def extract():
    # Upper stations share the original casting envelope. The assisted towers
    # have off-centre selector handles, requiring a wider through socket.
    guides = ((-.124, .029, .024), (0, .025, .025), (.124, .029, .024))
    return {"stack_casting": casting(True, guides=guides, socket=(.060, .026))}


if __name__ == "__main__":
    result = extract()
    output = Path(__file__).with_name("scene_upper_source.json")
    encoded = json.dumps(result, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert output.read_text() == encoded
    else:
        output.write_text(encoded)
    print({name: sum(len(part["t"])//3 for part in parts) for name, parts in result.items()})
