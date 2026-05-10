"""Live watcher for ALL ongoing benches in this project.

Detecta automaticamente lo que se este ejecutando:
  - Bench Fase 2 (results/extended_*.json) — 60 tests
  - Bench Fase 3 Carter 540 (harness_carter540/results/*.json) — hasta 540 tests
  - Baseline qwen3:4b
  - Audio Block D
Y muestra el ultimo test live + stats acumuladas + barra de progreso global.

Run: python watch.py
"""
import glob
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS_F2 = ROOT / "results"
RESULTS_F3 = ROOT / "harness_carter540" / "results"
TASK_LOG_GLOB = r"C:\Users\usuario\AppData\Local\Temp\claude\c--Users-usuario-Desktop-ETC-Programacion-Probando-Gemma-4\*\tasks\*.output"

PALETTE = {
    "title": "\033[36;1m",
    "ok":    "\033[32m",
    "fail":  "\033[31m",
    "dim":   "\033[90m",
    "user":  "\033[33m",
    "asst":  "\033[35m",
    "tool":  "\033[34m",
    "warn":  "\033[33;1m",
    "phase": "\033[95;1m",
    "reset": "\033[0m",
}


def cls():
    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()


def enable_ansi_on_windows():
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def latest_task_log():
    candidates = glob.glob(TASK_LOG_GLOB)
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p))
    return candidates[-1]


def tail_lines(path, n=80):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk = min(size, n * 250)
            f.seek(size - chunk)
            data = f.read().decode("utf-8", errors="replace")
            return data.splitlines()[-n:]
    except Exception:
        return []


def percentiles(values):
    if not values:
        return (0, 0, 0)
    s = sorted(values)
    def p(k):
        return s[min(int(k * (len(s) - 1)), len(s) - 1)]
    return p(0.5), p(0.9), p(0.99)


def latest_json_in(folder, pattern):
    if not folder.exists():
        return None
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def latest_active_bench():
    """Devuelve (path, kind) del JSON mas recientemente modificado."""
    candidates = []
    if RESULTS_F2.exists():
        for p in RESULTS_F2.glob("extended_*.json"):
            candidates.append((p, "fase2-60tests"))
        for p in RESULTS_F2.glob("baseline_*.json"):
            candidates.append((p, "baseline-qwen"))
        for p in RESULTS_F2.glob("audio_*.json"):
            candidates.append((p, "audio-blockD"))
    if RESULTS_F3.exists():
        for p in RESULTS_F3.glob("*.json"):
            candidates.append((p, "fase3-carter540"))
    if not candidates:
        return None, None
    candidates.sort(key=lambda c: c[0].stat().st_mtime)
    return candidates[-1]


def render_live_log():
    log = latest_task_log()
    if not log:
        print(f"{PALETTE['dim']}No task log encontrado.{PALETTE['reset']}")
        return None
    lines = tail_lines(log, 80)
    bench_lines = [l for l in lines if l.strip() and any(m in l for m in ("[", "->", "===", "VRAM", "Saved", "MODELO", "TOTAL", "Pass rate", "FAIL", "PASS"))]
    if not bench_lines:
        return None
    print(f"{PALETTE['title']}=== LIVE BENCH LOG ==={PALETTE['reset']}  {PALETTE['dim']}({Path(log).name}){PALETTE['reset']}")
    for line in bench_lines[-18:]:
        line = line.rstrip()
        if "===" in line:
            color = PALETTE["title"]
        elif "FAIL" in line or "XX" in line or "ERR" in line:
            color = PALETTE["fail"]
        elif "PASS" in line or "OK" in line or "->" in line:
            color = PALETTE["ok"]
        elif "VRAM" in line:
            color = PALETTE["warn"]
        elif "Saved" in line or "MODELO" in line or "Pass rate" in line:
            color = PALETTE["phase"]
        else:
            color = ""
        print(f"  {color}{line}{PALETTE['reset']}\033[K")


def render_active_bench():
    """Lo que este vivo ahora — formato unificado fase2/fase3."""
    path, kind = latest_active_bench()
    if not path:
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{PALETTE['fail']}Error leyendo {path.name}: {e}{PALETTE['reset']}")
        return

    age_min = (time.time() - path.stat().st_mtime) / 60

    # Fase 3 Carter (formato distinto: tiene "summary" + "results")
    if kind == "fase3-carter540" and isinstance(data, dict) and "summary" in data:
        s = data["summary"]
        print(f"\n{PALETTE['phase']}=== {kind}: {s.get('model', '?')} ==={PALETTE['reset']}  {PALETTE['dim']}({age_min:.1f} min ago){PALETTE['reset']}\033[K")
        print(f"  Tests: {s.get('completed', 0)}/{s.get('total', 0)}   PASS: {PALETTE['ok']}{s.get('pass', 0)}{PALETTE['reset']}   PARTIAL: {s.get('partial', 0)}   FAIL: {PALETTE['fail']}{s.get('fail', 0)}{PALETTE['reset']}")
        print(f"  {PALETTE['title']}Pass rate: {s.get('pass_rate', 0)}%{PALETTE['reset']}\033[K")
        results = data.get("results", [])
        if results:
            # Por categoria (top 5 mejor + top 5 peor)
            by_cat = s.get("by_category", {})
            cat_rates = []
            for cat, vals in by_cat.items():
                tot = sum(vals.values())
                rate = round(vals["pass"] / tot * 100, 1) if tot else 0
                cat_rates.append((int(cat), vals["pass"], tot, rate))
            cat_rates.sort(key=lambda x: x[3])
            if cat_rates:
                print(f"\n  {PALETTE['fail']}Peores categorias:{PALETTE['reset']}\033[K")
                for cat, p, tot, rate in cat_rates[:5]:
                    print(f"    C{cat:02d} {p}/{tot} ({rate}%)\033[K")
                print(f"\n  {PALETTE['ok']}Mejores categorias:{PALETTE['reset']}\033[K")
                for cat, p, tot, rate in cat_rates[-5:]:
                    print(f"    C{cat:02d} {p}/{tot} ({rate}%)\033[K")

            # Last 2 tests
            print(f"\n  {PALETTE['title']}Ultimos 2 tests:{PALETTE['reset']}\033[K")
            for r in results[-2:]:
                color = PALETTE["ok"] if r.get("status") == "PASS" else (PALETTE["warn"] if r.get("status") == "PARTIAL" else PALETTE["fail"])
                print(f"    {color}[{r.get('cid')}] {r.get('status')} ({r.get('latency_ms')}ms){PALETTE['reset']}\033[K")
                print(f"      {PALETTE['user']}prompt:{PALETTE['reset']} {r.get('prompt', '')[:90]}\033[K")
                reply = (r.get("reply") or "").replace("\n", " ")[:120]
                print(f"      {PALETTE['asst']}reply:{PALETTE['reset']}  {reply}\033[K")
                if r.get("tools"):
                    print(f"      {PALETTE['tool']}tools:{PALETTE['reset']}  {r.get('tools')}\033[K")
                if r.get("reasons"):
                    print(f"      {PALETTE['fail']}reasons:{PALETTE['reset']} {r.get('reasons')}\033[K")
        return

    # Fase 2 (60 tests por modelo)
    if kind == "fase2-60tests" and isinstance(data, dict) and "tests" in data:
        tests = data["tests"]
        n = len(tests)
        errors = [t for t in tests if t.get("error")]
        latencies = [t["total_latency_s"] for t in tests if t.get("total_latency_s") is not None]
        p50, p90, p99 = percentiles(latencies)
        n_with_tools = sum(1 for t in tests if any(turn.get("tool_calls") for turn in t.get("turns", [])))
        print(f"\n{PALETTE['phase']}=== {kind}: {data.get('model', '?')} ==={PALETTE['reset']}  {PALETTE['dim']}({age_min:.1f} min ago){PALETTE['reset']}\033[K")
        print(f"  Tests: {n}/60   Errors: {len(errors)}   Tool-using: {n_with_tools}/{n}\033[K")
        print(f"  Latency p50/p90/p99: {p50:.2f}s / {p90:.2f}s / {p99:.2f}s\033[K")
        for t in tests[-2:]:
            color = PALETTE["fail"] if t.get("error") else PALETTE["ok"]
            print(f"\n  {color}[{t['id']}] block={t.get('block')} pattern={t.get('pattern')}  {t.get('total_latency_s')}s{PALETTE['reset']}\033[K")
            print(f"    {PALETTE['user']}USER:{PALETTE['reset']} {t.get('prompt', '')[:90]}\033[K")
            for turn in t.get("turns", []):
                content = (turn.get("content") or "").strip()
                tcs = turn.get("tool_calls") or []
                if content:
                    print(f"    {PALETTE['asst']}reply:{PALETTE['reset']} {content[:140]}\033[K")
                for tc in tcs:
                    args = tc.get("args", {})
                    args_str = json.dumps(args, ensure_ascii=False)[:100]
                    print(f"    {PALETTE['tool']}-> {tc['name']}({args_str}){PALETTE['reset']}\033[K")
        return

    # Otros formatos (audio, baseline) — mostramos meta
    print(f"\n{PALETTE['phase']}=== {kind}: {path.name} ==={PALETTE['reset']}  {PALETTE['dim']}({age_min:.1f} min ago){PALETTE['reset']}\033[K")
    print(f"  Size: {path.stat().st_size // 1024} KB\033[K")


def render_progress_summary():
    f2_done = len(list(RESULTS_F2.glob("extended_*.json"))) if RESULTS_F2.exists() else 0
    f3_files = list(RESULTS_F3.glob("*.json")) if RESULTS_F3.exists() else []
    f3_runs = [f for f in f3_files if "smoke" in f.name.lower() or "per" in f.name.lower() or "_run" in f.name.lower() or "full" in f.name.lower()]

    print(f"{PALETTE['title']}=== PROGRESO GLOBAL ==={PALETTE['reset']}\033[K")
    print(f"  Fase 2 (60-tests): {f2_done}/21 modelos\033[K")
    print(f"  Fase 3 (540 cases Carter): {len(f3_runs)} bench runs\033[K")
    print()


def main():
    enable_ansi_on_windows()
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    print("Watching live bench. Ctrl+C to stop.")
    while True:
        cls()
        render_progress_summary()
        render_live_log()
        render_active_bench()
        print(f"\n{PALETTE['dim']}refresh cada 2s — Ctrl+C para salir{PALETTE['reset']}\033[K\033[J")
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
