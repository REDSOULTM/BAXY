"""Diff the OFFICIAL handoff prototype render against my frozen build render.
Both are 1080x640 dsf=2 with border frozen at 90deg. I crop my titlebar+gap off
the top so the instrument aligns. Reports a number per column band so I can see
WHERE design differs (left substrate / center field / right activity)."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image, ImageChops

REPO = Path(__file__).resolve().parents[2]
import sys
proto = Image.open(REPO / "_render_proto.png").convert("RGB")        # no titlebar
_mine_file = sys.argv[1] if len(sys.argv) > 1 else "_render_aligned.png"
mine = Image.open(REPO / _mine_file).convert("RGB")                  # has titlebar
print("proto", proto.size, " mine", mine.size)

# crop my titlebar+gap+top-padding off so the red frame top aligns with proto.
# window content = pad-top(8)+titlebar(32)+gap(6)+frame(632); proto has no titlebar
# but DOES have the same #root padding 24 all around. Easiest: autocrop both to
# the red frame, then crop mine's extra top band = (titlebar+gap)/window.
def autocrop(im, thr=22):
    a = np.asarray(im.convert("L"))
    m = a > thr
    rows = np.where(m.any(axis=1))[0]; cols = np.where(m.any(axis=0))[0]
    return im.crop((int(cols[0]), int(rows[0]), int(cols[-1])+1, int(rows[-1])+1))

p = autocrop(proto)
mi = autocrop(mine)
# mine's autocropped image still has titlebar text on top; remove that band.
band = (32 + 6) / (32 + 6 + 632)
mi = mi.crop((0, int(mi.size[1]*band), mi.size[0], mi.size[1]))
print("after align  proto", p.size, " mine", mi.size)

mi_r = mi.resize(p.size, Image.LANCZOS)
diff = ImageChops.difference(mi_r, p)
per = np.asarray(diff).astype(float).mean(axis=2)
W = p.size[0]
cols = {"LEFT substrate 0-19%": (0, int(W*0.19)),
        "CENTER field 19-72%": (int(W*0.19), int(W*0.72)),
        "RIGHT activity 72-100%": (int(W*0.72), W)}
print(f"\nOVERALL mean diff: {per.mean():.2f}   >30: {(per>30).mean()*100:.1f}%")
for name, (a, b) in cols.items():
    seg = per[:, a:b]
    print(f"  {name}: mean {seg.mean():.2f}  >30 {(seg>30).mean()*100:.1f}%")

Image.fromarray(np.clip(per,0,255).astype("uint8")).save(REPO / "_diff_proto_heatmap.png")
gap = 8
sbs = Image.new("RGB", (p.size[0]*2+gap, p.size[1]), (20,20,28))
sbs.paste(p,(0,0)); sbs.paste(mi_r,(p.size[0]+gap,0))
sbs.save(REPO / "_sbs_proto_mine.png")
print("wrote _diff_proto_heatmap.png + _sbs_proto_mine.png (PROTO left, MINE right)")
