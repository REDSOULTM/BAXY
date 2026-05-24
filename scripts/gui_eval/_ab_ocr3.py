import sys, os, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from gemma4_agent.ops_tools import ocr_image
from pathlib import Path
imgs=[("white_on_blue","scripts/gui_eval/fixtures/ocr_white_on_blue.png",["enviar","buscar","configuracion","reproducir"]),
      ("dark_on_light","scripts/gui_eval/fixtures/ocr_dark_on_light.png",["presupuesto","reunion","factura","informe"])]
# Tesseract
def tess(img):
    r=ocr_image(Path(img)); return " ".join(w.get("text","") for w in (r.get("words") or [])).lower()
# RapidOCR LATIN (descargar modelo latin si hace falta)
_rapid=None
def rapid(img):
    global _rapid
    if _rapid is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapid=RapidOCR()  # default ch — veremos si lee latín
    res,_=_rapid(img); return " ".join(str(t) for _,t,_ in (res or [])).lower()
for name,img,exp in imgs:
    t=time.time(); tw=tess(img); tt=time.time()-t
    t=time.time(); rw=rapid(img); rt=time.time()-t
    th=sum(1 for e in exp if e in tw); rh=sum(1 for e in exp if e in rw)
    print(f"[{name}] Tesseract {th}/4 ({tt:.2f}s) read={tw[:60]!r}")
    print(f"           RapidOCR  {rh}/4 ({rt:.2f}s) read={rw[:60]!r}")
