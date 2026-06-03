"""Experimento MÍNIMO (regla #1 medir-antes-del-build): ¿sirve Florence-2-base (MIT)
para grounding de UI en CPU dentro del presupuesto de latencia?

Mide en el screenshot ACTUAL:
  - tiempo de carga del modelo (one-time)
  - latencia + calidad de <OD>, <DENSE_REGION_CAPTION>, <OCR_WITH_REGION>,
    <CAPTION_TO_PHRASE_GROUNDING>
  - RAM
Guarda imágenes anotadas para LEER (Read tool) y juzgar la calidad visual.

Throttle: 4 threads CPU + prioridad baja → no congelar la máquina del user
(misma lección que ONNX busy-wait).
NO toca el agente; NO dispara SendInput. Solo lee pantalla + corre el VLM.
"""
from __future__ import annotations
import os, sys, time, gc
from pathlib import Path

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

# --- throttle CPU: no robarle la máquina al user ---
os.environ["OMP_NUM_THREADS"] = "4"
import torch
torch.set_num_threads(4)
try:
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except Exception:
    pass

import warnings; warnings.filterwarnings("ignore")
from PIL import Image, ImageDraw, ImageGrab

OUT = Path("scripts/_diag/_florence"); OUT.mkdir(parents=True, exist_ok=True)
MODEL_ID = "microsoft/Florence-2-base-ft"   # MIT, ~0.23B

def _rss_mb():
    try:
        import psutil; return psutil.Process().memory_info().rss / 1e6
    except Exception: return -1

print(f"[env] torch {torch.__version__} threads={torch.get_num_threads()} rss={_rss_mb():.0f}MB", flush=True)

# --- 1) grab el screenshot actual ---
shot = ImageGrab.grab()
shot = shot.convert("RGB")
shot.save(str((OUT / "00_screen.png").resolve()))
print(f"[shot] {shot.size} guardado en _florence/00_screen.png", flush=True)

# --- 2) cargar Florence-2 (descarga ~0.5GB la 1ra vez) ---
from transformers import AutoProcessor, AutoModelForCausalLM
# --- shim de compat: el código remoto de Florence-2 (transformers ~4.40) no
# define los flags que transformers 4.57 consulta. Parche SOLO en este proceso
# (atributos de clase en PreTrainedModel), no toca el runtime del agente. ---
from transformers.modeling_utils import PreTrainedModel
for _attr in ("_supports_sdpa", "_supports_flash_attn_2", "_supports_flash_attn",
              "_supports_flex_attn", "_supports_attention_backend"):
    if not hasattr(PreTrainedModel, _attr):
        setattr(PreTrainedModel, _attr, False)
t0 = time.time()
try:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, trust_remote_code=True, torch_dtype=torch.float32,
        attn_implementation="eager",
    ).eval()
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
except Exception as e:
    print(f"[load] FALLO: {type(e).__name__}: {e}", flush=True)
    import traceback; traceback.print_exc()
    sys.exit(1)
t_load = time.time() - t0
print(f"[load] OK en {t_load:.1f}s  rss={_rss_mb():.0f}MB", flush=True)

def run_task(task: str, text_input: str | None = None):
    prompt = task if text_input is None else task + text_input
    inputs = processor(text=prompt, images=shot, return_tensors="pt")
    t0 = time.time()
    with torch.inference_mode():
        gen = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024, num_beams=3, do_sample=False,
        )
    dt = time.time() - t0
    txt = processor.batch_decode(gen, skip_special_tokens=False)[0]
    parsed = processor.post_process_generation(txt, task=task, image_size=shot.size)
    return dt, parsed

def draw(parsed, key, fname, label_key=None):
    """Dibuja cajas (bboxes) sobre una copia del screenshot y la guarda."""
    img = shot.copy(); d = ImageDraw.Draw(img)
    data = parsed.get(key, {}) if isinstance(parsed, dict) else {}
    boxes = data.get("bboxes", []) if isinstance(data, dict) else []
    labels = data.get("labels", data.get(label_key, [])) if isinstance(data, dict) else []
    for i, b in enumerate(boxes):
        try:
            d.rectangle(b, outline=(255, 0, 0), width=2)
            lb = str(labels[i]) if i < len(labels) else ""
            d.text((b[0] + 2, b[1] + 2), lb[:30], fill=(255, 255, 0))
        except Exception: pass
    img.save(str((OUT / fname).resolve()))
    return len(boxes)

# --- 3) tareas ---
TASKS = [
    ("<OD>", None, "01_od.png"),
    ("<DENSE_REGION_CAPTION>", None, "02_dense.png"),
    ("<OCR_WITH_REGION>", None, "03_ocr.png"),
    ("<CAPTION_TO_PHRASE_GROUNDING>", "a button", "04_ground_button.png"),
]
results = []
for task, txt_in, fname in TASKS:
    try:
        dt, parsed = run_task(task, txt_in)
        # la key del resultado suele ser el nombre de la tarea
        key = task
        n = draw(parsed, key, fname)
        # muestra una probada de las labels
        data = parsed.get(key, {}) if isinstance(parsed, dict) else {}
        labels = data.get("labels", []) if isinstance(data, dict) else []
        sample = labels[:8]
        print(f"[{task}{(' '+txt_in) if txt_in else ''}] {dt:.2f}s  cajas={n}  labels={sample}", flush=True)
        results.append((task, dt, n))
    except Exception as e:
        print(f"[{task}] FALLO: {type(e).__name__}: {str(e)[:120]}", flush=True)
        import traceback; traceback.print_exc()

print("\n=== RESUMEN ===", flush=True)
print(f"carga: {t_load:.1f}s (one-time)", flush=True)
for task, dt, n in results:
    print(f"  {task:34s} {dt:5.2f}s  {n} elementos", flush=True)
print(f"rss final: {_rss_mb():.0f}MB", flush=True)
print("[done] imágenes anotadas en scripts/_diag/_florence/", flush=True)
