"""MEDICIÓN (CLAUDE.md): ¿el build 9090 de llama.cpp reusa el prompt-cache en
turnos de TEXTO cuando el mmproj está cargado RESIDENTE? (issue ggml-org #21133).

Si SÍ -> 'visión siempre cargada' NO tiene penalidad en texto -> el pedido del
user no tiene tradeoff. Si NO -> el tradeoff (+~1.9s/turno texto) es real.

Arranca un llama-server PROPIO en :8090 con --mmproj residente (sin router-mode),
manda 2 requests de texto que comparten un prefijo largo, y compara el
prompt_n / prompt_ms del 2do (cache hit => prompt_n chico). NO toca el server
de prod en :8080.
"""
import sys, os, subprocess, time, json, urllib.request

sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

EXE = r"C:/llamacpp-cuda/bin/llama-server.exe"
MODEL = r"C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\E2B\gemma-4-E2B-it-Q4_K_M.gguf"
MMPROJ = r"C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\E2B\mmproj-F16.gguf"
PORT = 8090
BASE = f"http://127.0.0.1:{PORT}"


def _post(path, payload, timeout=120):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _wait_health(timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
                if json.loads(r.read().decode()).get("status") == "ok":
                    return True
        except Exception:
            time.sleep(1.0)
    return False


def main():
    # FLAGS EXACTOS DE PROD (gemma4_agent/infra/llama_server.py llama_command):
    # mmproj residente + swa-full + keep -1 + flash-attn off + las mitigaciones
    # CUDA de GPU (--cache-ram 0 desactiva el prompt-cache RAM; el reuse de texto
    # queda SOLO por LCP in-slot). SIN --cache-reuse (removido por #17109). Así
    # medimos lo que el usuario realmente correría, no un setup optimista.
    cmd = [
        EXE, "-m", MODEL, "--mmproj", MMPROJ,
        "--host", "127.0.0.1", "--port", str(PORT),
        "-ngl", "99", "-c", "12288", "--no-mmproj-offload",
        "--flash-attn", "off", "--keep", "-1", "--swa-full",
        "--ctx-checkpoints", "0", "--cache-ram", "0", "--no-cache-idle-slots",
        "--no-webui",
    ]
    print("[boot] arrancando server con --mmproj RESIDENTE + flags de PROD en :8090 ...", flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not _wait_health():
            print("[boot] FALLÓ health", flush=True); return
        print("[boot] OK\n", flush=True)

        # Prefijo LARGO compartido (system) + pregunta corta distinta -> 2da debe
        # reusar todo el prefijo si el cache de texto funciona con mmproj.
        big_system = ("You are Baxy, a local Windows voice assistant. " * 200).strip()

        def ask(q):
            return _post("/v1/chat/completions", {
                "messages": [{"role": "system", "content": big_system},
                             {"role": "user", "content": q}],
                "max_tokens": 8, "temperature": 0, "cache_prompt": True,
            })

        r1 = ask("Say hi in one word.")
        t1 = r1.get("timings", {})
        print(f"  Turno 1 (cold): prompt_n={t1.get('prompt_n')} "
              f"prompt_ms={t1.get('prompt_ms', 0):.0f}", flush=True)

        r2 = ask("Say bye in one word.")   # MISMO system, user distinto corto
        t2 = r2.get("timings", {})
        pn2 = t2.get("prompt_n")
        print(f"  Turno 2 (warm): prompt_n={pn2} "
              f"prompt_ms={t2.get('prompt_ms', 0):.0f}", flush=True)

        print("\n=== VEREDICTO TEXTO ===", flush=True)
        if isinstance(pn2, int) and isinstance(t1.get("prompt_n"), int):
            ratio = pn2 / max(1, t1["prompt_n"])
            if pn2 < 50 or ratio < 0.15:
                print(f"  ✅ CACHE REUSE FUNCIONA con mmproj residente "
                      f"(turno 2 solo re-evaluó {pn2} tokens). El build 9090 YA "
                      f"trae el fix #21133 -> 'visión siempre' SIN penalidad en texto.",
                      flush=True)
            else:
                print(f"  ❌ NO reusa cache (turno 2 re-evaluó {pn2} tokens, ~todo "
                      f"el prompt). El tradeoff es REAL: visión residente -> +latencia "
                      f"en cada turno de texto.", flush=True)
        else:
            print("  ⚠ timings incompletos; revisar manualmente:", t1, t2, flush=True)

        # ---- TURNO CON IMAGEN: el mmproj residente debe responder SIN lazy-load --
        print("\n=== TURNO CON IMAGEN (mmproj residente) ===", flush=True)
        import base64, io
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (200, 80), "white")
            ImageDraw.Draw(img).rectangle([20, 20, 180, 60], fill="red")
            buf = io.BytesIO(); img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            timg0 = time.time()
            ri = _post("/v1/chat/completions", {
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "What primary color is the rectangle? One word."},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]}],
                "max_tokens": 32, "temperature": 0,
            })
            dt = time.time() - timg0
            ans = (((ri.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
            print(f"  imagen respondida en {dt:.2f}s -> {ans!r}", flush=True)
            if "red" in ans.lower() or "roj" in ans.lower():
                print("  ✅ La visión RESPONDE bien y SIN segundo server lazy "
                      "(mmproj ya estaba cargado: no hubo carga on-demand).", flush=True)
            else:
                print("  ⚠ respondió pero no reconoció el color (revisar manual).",
                      flush=True)
        except ImportError:
            print("  (PIL no disponible; salteo el turno de imagen)", flush=True)
    finally:
        print("\n[cleanup] cerrando server de medición :8090", flush=True)
        proc.terminate()
        try: proc.wait(timeout=10)
        except Exception: proc.kill()


if __name__ == "__main__":
    main()
