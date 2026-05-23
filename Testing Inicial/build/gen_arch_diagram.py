"""Diagrama de ARQUITECTURA técnica (mapa de capas) para el documento Word.

Fiel a docs/ARCHITECTURE.md: superficies de entrada, hot-path del turno,
always-on de audio, persistencia, recovery/diagnósticos, daemons/lifecycle.
Paleta oscura técnica coherente con el resto de la tesis.
"""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BG="#0A0E14"; PANEL="#141A24"; PANEL2="#1C2430"; STROKE="#2A3340"
INK="#E6EDF3"; MUTE="#8B98A8"
ACCENT="#5BC8FF"; VIOLET="#9D7CFF"; GREEN="#3FB950"; ORANGE="#FF7A59"; YELLOW="#E3B341"

ASSETS=os.path.join(os.path.dirname(__file__),"pptx_assets")
os.makedirs(ASSETS,exist_ok=True)
plt.rcParams.update({"font.family":"DejaVu Sans"})


def _box(ax,x,y,w,h,title,sub=None,*,fc=PANEL,ec=STROKE,tc=INK,lw=1.6,fs=12,bold=True,sub_c=None):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0,rounding_size=1.0",
                 linewidth=lw,edgecolor=ec,facecolor=fc))
    if sub:
        ax.text(x+w/2,y+h*0.62,title,ha="center",va="center",color=tc,fontsize=fs,fontweight="bold" if bold else "normal")
        ax.text(x+w/2,y+h*0.28,sub,ha="center",va="center",color=sub_c or MUTE,fontsize=fs-3)
    else:
        ax.text(x+w/2,y+h/2,title,ha="center",va="center",color=tc,fontsize=fs,fontweight="bold" if bold else "normal")


def _arrow(ax,x1,y1,x2,y2,c=ACCENT,lw=2.0,style="-|>"):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle=style,mutation_scale=16,
                 linewidth=lw,color=c,shrinkA=2,shrinkB=2))


def diagram_layers():
    W,H=13.33,9.2
    fig=plt.figure(figsize=(W,H),dpi=200)
    ax=fig.add_axes([0,0,1,1]); ax.set_xlim(0,100); ax.set_ylim(0,100*H/W); ax.axis("off")
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    HH=100*H/W  # ~69

    def band(y,h,label,c):
        ax.add_patch(FancyBboxPatch((2,y),96,h,boxstyle="round,pad=0,rounding_size=0.8",
                     linewidth=1.2,edgecolor=c,facecolor=PANEL2+ "00" if False else PANEL))
        ax.text(3.5,y+h-2.2,label,ha="left",va="center",color=c,fontsize=11,fontweight="bold")

    # ---- SUPERFICIES (top) ----
    yb=HH-12; band(yb,9.5,"SUPERFICIES · entrada",ACCENT)
    for i,(t,s) in enumerate([("launcher","arranque"),("server.py","FastAPI/uvicorn"),
                              ("chat.py","CLI"),("mcp_server","tools MCP")]):
        _box(ax,6+i*22,yb+1.2,19,5.0,t,s,ec=ACCENT,fs=11)

    # ---- ALWAYS-ON AUDIO (left) y HOT-PATH (right) ----
    yb2=HH-30;
    band(yb2,15.5,"ALWAYS-ON AUDIO  ·  HOT-PATH DEL TURNO",ORANGE)
    # audio chain
    _box(ax,6,yb2+1.5,18,5.2,"audio_io → VAD","Silero · callback no-bloq.",ec=VIOLET,fs=10.5)
    _box(ax,6,yb2+7.6,18,5.2,"wake → pipeline","LiveKit ONNX · 8 Hz",ec=VIOLET,fs=10.5)
    _arrow(ax,15,yb2+7.6,15,yb2+6.7,c=VIOLET,lw=1.8)
    # turn hot-path
    _box(ax,30,yb2+1.5,30,5.2,"agent.run_content","router → LLM (Gemma 4)",ec=ORANGE,fs=11)
    _box(ax,30,yb2+7.6,30,5.2,"dispatch tools → verifiers","try/except × tool · timeout",ec=ORANGE,fs=10.5)
    _arrow(ax,45,yb2+7.6,45,yb2+6.7,c=ORANGE,lw=1.8)
    _box(ax,64,yb2+4.4,30,5.2,"reply → TTS (Piper)","sanitize · mission footer",ec=GREEN,fs=10.5)
    _arrow(ax,60,yb2+4.1,64,yb2+5.5,c=ORANGE,lw=1.8)
    # comando texto: audio -> hot-path
    _arrow(ax,24,yb2+10.2,30,yb2+10.2,c=MUTE,lw=1.8)
    ax.text(27,yb2+11.4,"comando",ha="center",color=MUTE,fontsize=8)

    # ---- PERSISTENCIA + DIAGNOSTICOS ----
    yb3=HH-46; band(yb3,13.5,"PERSISTENCIA  ·  RECOVERY  ·  DIAGNÓSTICOS",GREEN)
    _box(ax,6,yb3+1.5,27,4.6,"state · sessions","escritura atómica (os.replace)",ec=GREEN,fs=10)
    _box(ax,35,yb3+1.5,27,4.6,"experience (SQLite)","recovery: cuarentena DB",ec=GREEN,fs=10)
    _box(ax,64,yb3+1.5,30,4.6,"telemetry","rotate() · poda >30 días",ec=GREEN,fs=10)
    _box(ax,6,yb3+6.8,27,4.6,"tracing","fail-safe (no tumba turno)",ec=YELLOW,fs=10)
    _box(ax,35,yb3+6.8,27,4.6,"log_recorder","listeners sin lock",ec=YELLOW,fs=10)
    _box(ax,64,yb3+6.8,30,4.6,"loop_detection","safety-net anti-bucle",ec=YELLOW,fs=10)

    # ---- DAEMONS / LIFECYCLE (bottom) ----
    yb4=2.5; band(yb4,11.0,"DAEMONS / LIFECYCLE",ACCENT)
    for i,(t,s) in enumerate([("llama_server","manager · atexit · sin huérfanos"),
                              ("profile_watcher","switch VRAM → restart"),
                              ("EventBus","cola bounded · drop-oldest"),
                              ("boot warmup","singletons lazy + lock")]):
        _box(ax,5+i*23,yb4+1.5,21,5.6,t,s,ec=ACCENT,fs=10)

    # flechas verticales entre bandas (flujo)
    _arrow(ax,50,HH-12,50,HH-14.5,c=MUTE,lw=1.6)      # superficies -> turno
    _arrow(ax,50,yb2,50,yb3+13.5,c=MUTE,lw=1.6)        # turno -> persistencia
    _arrow(ax,50,yb3,50,yb4+11,c=MUTE,lw=1.6)          # persistencia -> daemons

    fig.savefig(os.path.join(ASSETS,"architecture_layers.png"),facecolor=BG,bbox_inches=None)
    plt.close(fig)


if __name__=="__main__":
    diagram_layers()
    print("OK -> architecture_layers.png")
