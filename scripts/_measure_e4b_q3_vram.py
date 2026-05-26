"""Mide VRAM real (delta sobre idle) de los E4B-Q3 candidatos para el target <4GB.
Cada uno: TEXTO solo (residente normal, visión-lazy) y +VISIÓN (pico con mmproj).
Puerto 8091 para no chocar con el server real. Reusa la mecánica de
measure_vram_profiles.py (llama-server + nvidia-smi delta)."""
import json, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
E4B = ROOT / "models" / "E4B"
LLAMA = next(ROOT.glob("**/llama-server.exe"), None) or Path("llama-server.exe")
HOST, PORT = "127.0.0.1", 8091
MMPROJ = E4B / "mmproj-F16.gguf"

CASES = [
    ("E4B-Q4_K_M     ctx16k novis (BASELINE)", E4B/"gemma-4-E4B-it-Q4_K_M.gguf",   16384, None),
    ("E4B-Q4_K_M     ctx16k +VIS  (BASELINE)", E4B/"gemma-4-E4B-it-Q4_K_M.gguf",   16384, MMPROJ),
    ("E4B-UD-Q3_K_XL ctx16k novis",            E4B/"gemma-4-E4B-it-UD-Q3_K_XL.gguf",16384, None),
    ("E4B-UD-Q3_K_XL ctx16k +VIS",             E4B/"gemma-4-E4B-it-UD-Q3_K_XL.gguf",16384, MMPROJ),
    ("E4B-UD-IQ3_XXS ctx16k novis",            E4B/"gemma-4-E4B-it-UD-IQ3_XXS.gguf",16384, None),
    ("E4B-UD-IQ3_XXS ctx16k +VIS",             E4B/"gemma-4-E4B-it-UD-IQ3_XXS.gguf",16384, MMPROJ),
]

def vram_used_mb():
    out = subprocess.run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=10).stdout
    return int(out.strip().splitlines()[0])

def health_ok():
    try:
        urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=2)
        return True
    except Exception:
        return False

def measure(label, model, ctx, mmproj):
    if not model.is_file():
        return {"label": label, "error": "model missing"}
    idle = vram_used_mb()
    cmd = [str(LLAMA),"-m",str(model),"-c",str(ctx),"-ngl","99","--flash-attn","on",
           "--swa-full","--host",HOST,"--port",str(PORT),"--no-webui"]
    if mmproj and mmproj.is_file():
        cmd += ["--mmproj", str(mmproj)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    peak = idle; ok = False
    try:
        for _ in range(90):
            time.sleep(1)
            try: peak = max(peak, vram_used_mb())
            except Exception: pass
            if health_ok():
                ok = True
                for _ in range(3):
                    time.sleep(1); peak = max(peak, vram_used_mb())
                break
            if proc.poll() is not None: break
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except Exception: proc.kill()
        for _ in range(25):
            time.sleep(1)
            if vram_used_mb() <= idle + 200: break
    return {"label":label,"ok":ok,"idle_mb":idle,"peak_mb":peak,
            "delta_mb":peak-idle,"disk_mb":model.stat().st_size//(1024*1024)}

def main():
    print(f"llama-server: {LLAMA}", flush=True)
    res=[]
    for label,model,ctx,mmproj in CASES:
        print(f"measuring {label} ...", flush=True)
        r=measure(label,model,ctx,mmproj); res.append(r)
        print(f"  -> {json.dumps(r)}", flush=True)
    print("\n==== RESUMEN (delta = VRAM real sobre idle Windows) ====", flush=True)
    print(f"{'caso':40s} {'disco':>7s} {'cargado':>8s} {'<4GB?':>6s} ok", flush=True)
    for r in res:
        if "error" in r: print(f"{r['label']:40s}  {r['error']}"); continue
        lt4 = "SI" if r['delta_mb'] < 4096 else "no"
        print(f"{r['label']:40s} {r['disk_mb']:5d}MB {r['delta_mb']:6d}MB {lt4:>6s} {'Y' if r['ok'] else 'N'}", flush=True)
    out=ROOT/"scripts"/"gui_eval"/"_e4b_q3_vram.json"; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(res,indent=2),encoding="utf-8")
    print("WROTE",out, flush=True)

if __name__=="__main__": main()
