"""Stress test del bug CUDA illegal memory access en Gemma 4
(llama.cpp issue #22527).

Reproduce el patron que dispara el crash: prompt grande (~9k tokens),
prompts diversos turno-a-turno, con/sin thinking activado. Mide cuantos
turnos sobrevive antes del crash.

Uso:
  python scripts/stress_test_cuda_crash.py --turns 50
  python scripts/stress_test_cuda_crash.py --turns 50 --thinking
  python scripts/stress_test_cuda_crash.py --turns 50 --thinking --think-budget 256

Variables medidas para reportar a #22527:
  - Turn index del primer crash (o "ninguno" si llego al fin).
  - Total exitos vs fallas.
  - Cache hit ratio promedio.
  - Tiempo total y por-turno.
  - Lineas relevantes del log: "context checkpoint", "memory_seq_rm".

Para validar Plan A del informe v3 (research/latency/v3): correr con
--turns 50 con la config actual de --ctx-checkpoints 0. Si crashes=0,
el Plan A esta validado.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


# Prompts diversos que rompen el LCP de manera distinta cada turn.
PROMPTS = [
    "Abre steam", "Pone musica en youtube", "Cierra la ventana",
    "Sube el volumen", "Abre chrome", "Manda whatsapp a juan",
    "Que ves en pantalla", "Conecta wifi", "Busca tutoriales en google",
    "Hace screenshot", "Hora actual", "Que hace este programa",
    "Cierra steam", "Baja volumen", "Abre notepad",
    "Toma nota: comprar pan", "Que tengo abierto", "Mute",
    "Abre opera", "Pausa musica", "Reanuda musica",
    "Siguiente cancion", "Apaga pantalla", "Bloquea pc",
    "Que pelicula vimos", "Cierra chrome", "Cambia a vram4",
    "Activa modo cine", "Sube brillo", "Pone alarma 8am",
    "Que dia es hoy", "Lista mis tareas", "Crea recordatorio",
    "Abre calculadora", "Cuanto es 23 por 47", "Modo silencio",
    "Habla mas bajo", "Modo presentacion", "Conecta bluetooth",
    "Desconecta bluetooth", "Abre la camara", "Toma foto",
    "Abre discord", "Cambia idioma", "Modo lectura",
    "Habilita nightlight", "Que CPU tengo", "Cuanta RAM",
    "Espacio en disco", "Reinicia",
]

# System prompt grande (~9k tokens, similar al Camino C V3).
BIG_SYSTEM = (
    "You are a helpful local Windows agent powered by Gemma 4. "
    "Be concise. Reply in Spanish.\n"
    * 200
)


def stress_test(
    *,
    turns: int = 50,
    enable_thinking: bool = False,
    think_budget: int = 256,
    server_url: str = "http://127.0.0.1:8080",
    model: str = "vram4-text",
) -> dict:
    """Corre `turns` requests al servidor y mide crashes + latencia."""
    results = {
        "turns_attempted": 0,
        "turns_ok": 0,
        "turns_failed": 0,
        "first_crash_at": None,
        "crashes_by_turn": [],
        "total_ms": 0.0,
        "avg_cache_hit": 0.0,
        "config": {
            "enable_thinking": enable_thinking,
            "think_budget": think_budget,
            "system_chars": len(BIG_SYSTEM),
        },
    }
    cache_hits = []

    for i in range(turns):
        results["turns_attempted"] = i + 1
        prompt = PROMPTS[i % len(PROMPTS)] + f" turno_{i}"  # diverso siempre
        body_data: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": BIG_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 20,
            "temperature": 0,
        }
        if enable_thinking:
            body_data["chat_template_kwargs"] = {"enable_thinking": True}
            body_data["thinking_budget_tokens"] = think_budget

        body = json.dumps(body_data).encode("utf-8")
        req = urllib.request.Request(
            f"{server_url}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())
            dt = (time.perf_counter() - t) * 1000
            results["total_ms"] += dt
            results["turns_ok"] += 1
            tim = resp.get("timings", {})
            c = tim.get("cache_n", 0) or 0
            pn = tim.get("prompt_n", 0) or 0
            hit = c / (c + pn) if (c + pn) else 0
            cache_hits.append(hit)
            ms_str = f"{dt:6.0f}ms"
            print(f"{i:3d} {prompt[:35]:<37} {ms_str} hit={hit:.0%}")
        except Exception as exc:
            err_str = str(exc)[:70]
            results["turns_failed"] += 1
            results["crashes_by_turn"].append(i)
            if results["first_crash_at"] is None:
                results["first_crash_at"] = i
            print(f"{i:3d} {prompt[:35]:<37} FAIL: {err_str}")

    if cache_hits:
        results["avg_cache_hit"] = sum(cache_hits) / len(cache_hits)
    return results


def scan_log_for_crashes(log_path: Path) -> dict:
    """Cuenta CUDA crashes + context checkpoints en el log."""
    if not log_path.is_file():
        return {"checkpoints": 0, "cuda_errors": 0, "memory_seq_rm": 0}
    cnt = {"checkpoints": 0, "cuda_errors": 0, "memory_seq_rm": 0}
    try:
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "created context checkpoint" in line:
                cnt["checkpoints"] += 1
            elif "CUDA error" in line and "illegal" in line:
                cnt["cuda_errors"] += 1
            elif "memory_seq_rm" in line:
                cnt["memory_seq_rm"] += 1
    except OSError:
        pass
    return cnt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=50)
    ap.add_argument("--thinking", action="store_true",
                    help="enable_thinking=True per request")
    ap.add_argument("--think-budget", type=int, default=256)
    ap.add_argument("--server-url", default="http://127.0.0.1:8080")
    ap.add_argument("--model", default="vram4-text")
    ap.add_argument("--report-json", type=Path, default=None,
                    help="if set, write report dict to this JSON path")
    args = ap.parse_args()

    print(f"=== Stress test {args.turns} turns ===")
    print(f"thinking={args.thinking} budget={args.think_budget} "
          f"system_chars={len(BIG_SYSTEM)}")
    print()

    pre_log = scan_log_for_crashes(
        Path("gemma4_agent/logs/llama-server.err.log"))
    pre_log_out = scan_log_for_crashes(
        Path("gemma4_agent/logs/llama-server.out.log"))
    print(f"Pre-test log: out_crashes={pre_log_out['cuda_errors']} "
          f"err_crashes={pre_log['cuda_errors']}")
    print()

    t0 = time.perf_counter()
    results = stress_test(
        turns=args.turns,
        enable_thinking=args.thinking,
        think_budget=args.think_budget,
        server_url=args.server_url,
        model=args.model,
    )
    total_test_s = time.perf_counter() - t0

    post_log = scan_log_for_crashes(
        Path("gemma4_agent/logs/llama-server.err.log"))
    post_log_out = scan_log_for_crashes(
        Path("gemma4_agent/logs/llama-server.out.log"))

    new_crashes_err = post_log["cuda_errors"] - pre_log["cuda_errors"]
    new_crashes_out = post_log_out["cuda_errors"] - pre_log_out["cuda_errors"]
    new_checkpoints = (post_log["checkpoints"] - pre_log["checkpoints"]) + \
                       (post_log_out["checkpoints"] - pre_log_out["checkpoints"])
    new_seq_rm = (post_log["memory_seq_rm"] - pre_log["memory_seq_rm"]) + \
                  (post_log_out["memory_seq_rm"] - pre_log_out["memory_seq_rm"])

    print()
    print("=" * 60)
    print("RESULTADO STRESS TEST")
    print("=" * 60)
    print(f"Turns attempted:        {results['turns_attempted']}")
    print(f"Turns OK:               {results['turns_ok']}")
    print(f"Turns FAILED:           {results['turns_failed']}")
    print(f"First crash at turn:    {results['first_crash_at']}")
    print(f"Total wall time:        {total_test_s:.1f}s")
    if results["turns_ok"]:
        print(f"Avg ms per OK turn:     {results['total_ms']/results['turns_ok']:.0f}ms")
    print(f"Avg cache hit ratio:    {results['avg_cache_hit']:.1%}")
    print()
    print("LOG ANALYSIS (delta during test):")
    print(f"  New CUDA crashes (err): {new_crashes_err}")
    print(f"  New CUDA crashes (out): {new_crashes_out}")
    print(f"  New 'created context checkpoint': {new_checkpoints}")
    print(f"  New 'memory_seq_rm' lines: {new_seq_rm}")
    print()
    if new_crashes_err + new_crashes_out == 0 and results["turns_failed"] == 0:
        print("RESULT: 0 crashes / PLAN A VALIDATED")
        print("  -> publicable en llama.cpp issue #22527")
    elif results["turns_failed"] == 0:
        print("RESULT: 0 client-visible failures but CUDA errors in log")
        print("  -> revisar si fue recovery del cliente que enmascaro")
    else:
        crash_rate = results["turns_failed"] * 100 / results["turns_attempted"]
        print(f"RESULT: {results['turns_failed']}/{results['turns_attempted']} "
              f"failures ({crash_rate:.1f}%) - PLAN A NO BASTA")
        print("  -> activar Plan C (proxy erase-before-request)")

    if args.report_json:
        report = {
            **results,
            "total_test_s": total_test_s,
            "new_crashes_err": new_crashes_err,
            "new_crashes_out": new_crashes_out,
            "new_checkpoints": new_checkpoints,
            "new_seq_rm": new_seq_rm,
        }
        args.report_json.write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report saved to: {args.report_json}")

    return 0 if results["turns_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
