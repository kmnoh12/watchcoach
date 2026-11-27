"""Apply shared gym parts to the upper-station overlays of the new-hand viewer."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import tube
from upgrade_app3d_pull_stations import (
    HERE, append_batch, assemble, load, load_source as load_tower_source, slider_bottom, vertices, world,
)
from body_fit import fit_body_part
from pull_pad_fit import axial_gap
from part_registry import MAT_CHROME, MAT_FRAME
from scene_lat_parts import build_seat, palette
from selector_tower import cylinder, drilled_slider

TARGETS = "upper_station_targets.json"
REPORT = "upper_station_fit.json"


def load_source():
    return {**load_tower_source(), **load(HERE/"scene_upper_source.json")}


def fit_seat(raw, mapping, source, skin, base, emit):
    if "seat" not in mapping:
        return {}
    objects = {o["name"]: o for o in raw["objects"]}
    seat = objects["seat"]
    matrix = np.asarray(seat["m"][0]).reshape(4, 4)
    center = matrix[3, :3]
    up, across = matrix[2, :3], matrix[0, :3]
    if not np.allclose(matrix[:3, :3], np.eye(3), atol=3e-5):
        raise ValueError("Seat does not match the original vertical slider")
    stock = vertices(seat)
    cushion = build_seat(stock.min(0), stock.max(0))
    surface = np.vstack([part.verts for part in cushion]) + center
    target = fit_body_part(skin, base, "seat_pad", center, surface, -up, across)
    shift = target - center
    # The pelvis may sit over a rounded front edge, not the top of the bounding box.
    layers = [(part.verts + target, part.tris) for part in cushion]
    clearance = axial_gap(skin, base, "seat_pad", layers, up)
    if not .002 <= clearance <= .005:
        shift = shift + up * (clearance - .0035)

    sleeve = world(objects["seat_socket"])[0]
    low, high = sleeve.min(0), sleeve.max(0)
    pin_name = "seat_adjust" if "seat_adjust" in mapping else "seat_pin"
    pin = world(objects[pin_name])[0]
    collar = (low + high)/2
    collar[2] = (pin[:, 2].max() + pin[:, 2].min())/2
    collar_half = .016
    slider_top = surface[:, 2].min() + shift[2] + .002
    slider_start = max(low[2]+.010, collar[2]-.060)
    if slider_top <= collar[2]+collar_half+.005 or abs(shift[2]) > .10:
        raise ValueError("Seat height falls outside the usable socket travel")
    foot = slider_bottom(slider_start, slider_top, collar[2])
    if not low[2] < foot < collar[2]-collar_half:
        raise ValueError("Seat slider cannot stay engaged at fitted height")

    for part in cushion:
        emit("seat", part.verts, part.tris, part.mat_preset, part.color,
             shift=shift, smooth=part.smooth, contact=True)
    gray, steel = palette()["casting"], palette()["steel"]
    identity = [0., 0., 0., 1.]
    width = (high-low)[:2]/.042

    def hardware(name, shape, pos, dimensions, mat, color):
        emit(name, *shape, mat, color, scale=dimensions, pose=(pos, identity), contact=True)

    start = np.array([*collar[:2], low[2]])
    hardware("seat_socket", tube(), start, [*width, collar[2]-collar_half-low[2]], MAT_FRAME, gray)
    hardware("seat_socket", tube(True), collar, [*width, collar_half/.010], MAT_FRAME, gray)

    slide, faces = drilled_slider()
    slide = slide + [0, 0, .12]
    height = (slider_top-foot)/.24
    at = np.array([*collar[:2], (slider_top+foot)/2])
    hardware("seat_slide", (slide, faces), at, [*width, height], MAT_CHROME, steel)
    pin_start = collar[0] - .011*width[0]
    pin_end = max(high[0], pin[:, 0].min()) + .004
    spindle = np.array([(pin_start+pin_end)/2, *collar[1:]])
    hardware("seat_socket", cylinder(.0031*min(*width, height), pin_end-pin_start, 0, 20),
             spindle, [1, 1, 1], MAT_CHROME, steel)

    gap = axial_gap(skin, base, "seat_pad", [(part.verts + center + shift, part.tris) for part in cushion], up)
    return {"seat": dict(role="seat_pad", axis=up.tolist(), normal=(-up).tolist(), across=across.tolist(),
                         origin=center.tolist(), offset=shift.tolist(), gap_mm=gap*1000, gap_method="axial_surface")}


def build_model(key, raw, mapping, source, human, base):
    return assemble(key, raw, mapping, source, human, base, fit_layers=fit_seat)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    append_batch(parser.parse_args().view, targets_file=TARGETS, report_file=REPORT,
                 source_loader=load_source, build_model=build_model)
