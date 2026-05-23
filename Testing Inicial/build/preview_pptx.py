"""Previsualiza el .pptx renderizando cada slide a PNG con matplotlib, usando
las MISMAS coordenadas (en pulgadas) que el builder. Sirve para verificar
visualmente que nada se sale ni se pisa, sin LibreOffice.

Lee las shapes reales del .pptx (cajas, textos, imágenes) y las dibuja a escala.
"""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE

HERE = os.path.dirname(__file__)
PPTX = os.path.join(HERE, "Gemma4_Agent_Tesis.pptx")
OUT = os.path.join(HERE, "preview")
os.makedirs(OUT, exist_ok=True)

W_IN, H_IN = 13.333, 7.5

def emu_in(v):
    return Emu(v).inches if v is not None else 0


def rgb_of(shape):
    try:
        c = shape.fill.fore_color.rgb
        return "#" + str(c)
    except Exception:
        return None


def line_rgb(shape):
    try:
        return "#" + str(shape.line.color.rgb)
    except Exception:
        return None


prs = Presentation(PPTX)
for idx, slide in enumerate(prs.slides, 1):
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W_IN); ax.set_ylim(0, H_IN); ax.axis("off")
    ax.invert_yaxis()  # pptx y crece hacia abajo

    for shp in slide.shapes:
        x = emu_in(shp.left); y = emu_in(shp.top)
        w = emu_in(shp.width); h = emu_in(shp.height)
        if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
            try:
                img = shp.image.blob
                import io
                from PIL import Image
                im = Image.open(io.BytesIO(img))
                ax.imshow(im, extent=(x, x + w, y + h, y), aspect="auto", zorder=2)
            except Exception:
                ax.add_patch(Rectangle((x, y), w, h, fc="#222", ec="#555", zorder=2))
            continue
        if shp.has_text_frame and not shp.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            pass
        # autoshape (caja)
        fc = rgb_of(shp)
        if fc and shp.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            ec = line_rgb(shp) or "none"
            ax.add_patch(FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0,rounding_size=0.06",
                         fc=fc, ec=ec if ec else "none",
                         lw=1.2 if ec != "none" else 0, zorder=1))
        # texto
        if shp.has_text_frame:
            tf = shp.text_frame
            # estimar posición de cada párrafo
            n_par = len(tf.paragraphs)
            for pi, p in enumerate(tf.paragraphs):
                full = "".join(r.text for r in p.runs)
                if not full.strip():
                    continue
                # color/size del primer run
                run = p.runs[0]
                try: size = run.font.size.pt
                except Exception: size = 14
                try: col = "#" + str(run.font.color.rgb)
                except Exception: col = "#E6EDF3"
                # alineacion
                from pptx.enum.text import PP_ALIGN
                al = p.alignment
                ha = "center" if al == PP_ALIGN.CENTER else ("right" if al == PP_ALIGN.RIGHT else "left")
                tx = x + w/2 if ha == "center" else (x + w - 0.05 if ha == "right" else x + 0.08)
                # y aproximada: repartir
                ty = y + (h * (pi + 0.5) / max(n_par, 1))
                ax.text(tx, ty, full, ha=ha, va="center", color=col,
                        fontsize=size * 0.92, zorder=3,
                        fontweight="bold" if run.font.bold else "normal")

    fig.savefig(os.path.join(OUT, f"slide_{idx:02d}.png"), facecolor="#0A0E14")
    plt.close(fig)
    print("rendered slide", idx)

print("OK ->", OUT)
