import bpy
import numpy as np


def grid(tiles, out, cols):
    imgs = []
    for n, p in tiles:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        imgs.append(a)
        bpy.data.images.remove(im)
    h, w = imgs[0].shape[:2]
    rows = (len(imgs) + cols - 1) // cols
    big = np.ones((rows * h, cols * w, 4), dtype=np.float32)
    for i, a in enumerate(imgs):
        r, c = divmod(i, cols)
        big[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = a
    im = bpy.data.images.new("sheet", cols * w, rows * h, alpha=True)
    im.pixels[:] = big.ravel()
    im.filepath_raw = out
    im.file_format = "PNG"
    im.save()
    # label file
    with open(out.replace(".png", ".txt"), "w") as f:
        for i, (n, _) in enumerate(tiles):
            f.write(f"{i // cols},{i % cols}: {n}\n")
