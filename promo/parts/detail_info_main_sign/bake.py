"""Optional master bake. Python with fonttools, numpy, manifold3d; pass Arial Black.ttf.

Units here are millimetres; X reads left to right, Y is up, Z faces the desk.
The Blender installer reads the baked sign mesh and needs none of these tools.
"""
import gzip
import json
import sys
from pathlib import Path

import manifold3d as cad
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont


class Outline(BasePen):
    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.loops = []

    def _moveTo(self, point):
        self.loops.append([point])

    def _lineTo(self, point):
        self.loops[-1].append(point)

    def _qCurveToOne(self, control, end):
        start, control, end = map(np.asarray, (self._getCurrentPoint(), control, end))
        for t in np.linspace(0, 1, 9)[1:]:
            self._lineTo((1-t)**2 * start + 2*t*(1-t)*control + t*t*end)

    def _closePath(self):
        pass


def lettering(font_path):
    font = TTFont(font_path)
    glyphs = font.getGlyphSet()
    shapes = []
    cursor = 0
    for word in ('WATCH', 'COACH'):
        for index, char in enumerate(word):
            pen = Outline(glyphs)
            glyphs[font.getBestCmap()[ord(char)]].draw(pen)
            glyph = cad.CrossSection(pen.loops, cad.FillRule.EvenOdd)
            glyph = glyph.offset(26, cad.JoinType.Miter)
            x0, _, x1, _ = glyph.bounds()
            pair = word[max(index-1, 0):index+1]
            cursor -= {"WA": 130, "AT": 165, "TC": 60}.get(pair, 0)
            shapes.append(glyph.translate((cursor - x0, 0)))
            # Optical sidebearings, including the open diagonal pair WA.
            cursor += x1 - x0 + 50
        cursor += 470
    shape = cad.CrossSection.batch_boolean(shapes, cad.OpType.Add)
    x0, y0, x1, y1 = shape.bounds()
    return shape.translate((-(x1+x0)/2, -(y1+y0)/2)).scale((2010/(x1-x0), 161/(y1-y0)))


def bake(font_path):
    section = cad.CrossSection
    plate = section.square((2420, 690), center=True).translate((0, 35))
    parts, slots = [], {}

    def layer(shape, rear, front, material):
        body = shape.extrude(front-rear).translate((0, 0, rear)).as_original()
        slots[body.original_id()] = material
        parts.append(body)

    # Four wall pads contact the mural within its micrometre-scale plane tolerance.
    pads = [section.circle(17, 24).translate((x, y)) for x in (-1130, 1130) for y in (-255, 325)]
    layer(section.compose(pads), 0.002, 9, 0)
    layer(plate, 8, 11, 0)
    frame = plate - plate.offset(-13, cad.JoinType.Miter)
    mullions = [section.square((17, 667), center=True).translate((x, 35)) for x in (-408, 408)]
    header = section.square((2400, 13), center=True).translate((0, 269))
    steel = section.batch_boolean([frame, header, *mullions], cad.OpType.Add)
    layer(steel, 10, 35, 1)

    # Expanded metal with continuous diamond-shaped through-holes.
    holes = []
    for row in range(-36, 43):
        y = row * 9.5
        for col in range(-35, 36):
            x = col*36 + (row % 2)*18
            holes.append([(x-16, y), (x, y-8.4), (x+16, y), (x, y+8.4)])
    net = plate.offset(-6, cad.JoinType.Miter) - section(holes)
    layer(net, 27, 29.2, 2)

    rail = section.square((2370, 52), center=True)
    layer(rail, 31, 50, 3)
    letters = lettering(font_path)
    layer(letters, 49, 80, 4)
    layer(letters, 80, 83, 5)
    bolts = [section.circle(3.4, 12).translate((x, 269)) for x in (-1100, -408, 408, 1100)]
    layer(section.compose(bolts), 34, 37, 1)

    sign = cad.Manifold.batch_boolean(parts, cad.OpType.Add).simplify(0.001)
    assert sign.status() == cad.Error.NoError and len(sign.decompose()) == 1
    mesh = sign.to_mesh64()
    faces = np.asarray(mesh.tri_verts)
    material = np.zeros(len(faces), dtype=int)
    for start, stop, orig in zip(mesh.run_index, mesh.run_index[1:], mesh.run_original_id):
        material[start//3:stop//3] = slots[orig]
    data = dict(vertices=np.round(mesh.vert_properties[:, :3], 5).tolist(),
                faces=faces.tolist(), material=material.tolist())
    target = Path(__file__).with_name('sign.json.gz')
    target.write_bytes(gzip.compress(json.dumps(data, separators=(',', ':')).encode(), mtime=0))


if __name__ == '__main__':
    bake(sys.argv[1])
