"""BAXY's icon: the face of the design v4 (helmet with its dark visor, two pink eyes with a glint, a smile, the antenna and
its bulb) on the interface's background and carmine. Each size is drawn on its own at 8× and scaled down, with thicker
strokes and fewer details for the small ones (16 and 20 px in the tray). make_icon.py <out.ico> <preview.png>"""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
BG = (10, 14, 20, 255)
PANEL = (15, 20, 25, 255)
CARMINE = (184, 58, 74, 255)
BLUE = (91, 127, 219, 255)
EYE = (255, 90, 110, 255)
BULB = (255, 179, 188, 255)
VISOR = (6, 9, 14, 255)


def superellipse(cx, cy, a, b, e, n=180):
    pts = []
    for i in range(n):
        t = i / n * 2 * math.pi
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + a * math.copysign(abs(c) ** (2 / e), c), cy + b * math.copysign(abs(s) ** (2 / e), s)))
    return pts


def draw(size: int) -> Image.Image:
    k = 8
    W = size * k
    small = size <= 24
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = W * 0.22
    d.rounded_rectangle([0, 0, W - 1, W - 1], radius=r, fill=BG)
    if not small:
        glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse([W * 0.15, W * 0.2, W * 0.85, W * 0.9], fill=(184, 58, 74, 70))
        glow = glow.filter(ImageFilter.GaussianBlur(W * 0.12))
        mask = Image.new("L", (W, W), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, W - 1], radius=r, fill=255)
        img.paste(glow, (0, 0), Image.composite(glow, Image.new("RGBA", (W, W)), mask).getchannel("A"))
        d = ImageDraw.Draw(img)
    border = max(k * 1.0, W * (0.035 if small else 0.028))
    d.rounded_rectangle([border / 2, border / 2, W - 1 - border / 2, W - 1 - border / 2], radius=r - border / 2,
                        outline=CARMINE, width=int(border))

    cx, cy = W / 2, W * 0.56
    hw, hh = W * (0.36 if small else 0.33), W * (0.29 if small else 0.27)
    stroke = max(k * 1.2, W * (0.055 if small else 0.03))
    # antenna and bulb
    top = cy - hh
    d.line([cx, top, cx, top - W * 0.11], fill=BLUE, width=int(stroke * 0.8))
    br = W * (0.075 if small else 0.055)
    if not small:
        halo = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse([cx - br * 2.4, top - W * 0.11 - br * 2.4, cx + br * 2.4, top - W * 0.11 + br * 2.4],
                                     fill=(255, 90, 110, 110))
        halo = halo.filter(ImageFilter.GaussianBlur(br))
        img.alpha_composite(halo)
        d = ImageDraw.Draw(img)
    d.ellipse([cx - br, top - W * 0.11 - br, cx + br, top - W * 0.11 + br], fill=BULB)
    # helmet and visor
    d.polygon(superellipse(cx, cy, hw, hh, 3.1), fill=PANEL, outline=BLUE)
    d.line(superellipse(cx, cy, hw, hh, 3.1) + [superellipse(cx, cy, hw, hh, 3.1)[0]], fill=BLUE, width=int(stroke))
    vw, vh = hw * 0.8, hh * 0.72
    d.polygon(superellipse(cx, cy + hh * 0.06, vw, vh, 3.6), fill=VISOR)
    # ears
    if not small:
        for s in (-1, 1):
            ex = cx + s * (hw + W * 0.03)
            d.rounded_rectangle([ex - W * 0.03, cy - hh * 0.35, ex + W * 0.03, cy + hh * 0.35], radius=W * 0.03, fill=BLUE)
    # eyes
    ew, eh = vw * (0.2 if small else 0.18), vh * (0.36 if small else 0.32)
    ey = cy - vh * 0.05
    for s in (-1, 1):
        ex = cx + s * vw * 0.42
        d.ellipse([ex - ew, ey - eh, ex + ew, ey + eh], fill=EYE)
        if not small:
            gr = ew * 0.32
            d.ellipse([ex - ew * 0.45 - gr, ey - eh * 0.45 - gr, ex - ew * 0.45 + gr, ey - eh * 0.45 + gr], fill=(255, 255, 255, 235))
    # smile
    sw = vw * 0.32
    sy = cy + vh * 0.42
    d.arc([cx - sw, sy - sw * 0.75, cx + sw, sy + sw * 0.35], start=20, end=160, fill=EYE,
          width=int(max(k * 1.2, W * (0.05 if small else 0.028))))
    return img.resize((size, size), Image.LANCZOS)


images = [draw(s) for s in SIZES]
images[-1].save(sys.argv[1], format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
preview = Image.new("RGBA", (sum(SIZES) + 10 * len(SIZES), 270), (243, 244, 247, 255))
x = 5
for im in images:
    preview.alpha_composite(im, (x, 260 - im.size[1]))
    x += im.size[0] + 10
dark = Image.new("RGBA", preview.size, (32, 32, 32, 255))
x = 5
for im in images:
    dark.alpha_composite(im, (x, 260 - im.size[1]))
    x += im.size[0] + 10
sheet = Image.new("RGBA", (preview.size[0], 540))
sheet.paste(preview, (0, 0))
sheet.paste(dark, (0, 270))
sheet.save(sys.argv[2])
print("ok")
