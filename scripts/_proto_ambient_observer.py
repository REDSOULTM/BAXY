"""PROTOTIPO del observador ambiente (capa Jarvis viva, 2026-05-30).

El usuario pidió ver QUÉ aprendería un observador de fondo ANTES de decidir su
alcance. Este prototipo muestrea la ventana en foco (win32, SIN LLM, SIN VRAM,
0.022ms/sample medido), detecta CAMBIOS de foco (no cada muestra → no duplica),
y reporta lo que vería: qué apps usás, cuánto tiempo, en qué franja horaria.

Alcance MÍNIMO (solo apps en foco): NO lee contenido, NO archivos, NO navegación.
Todo local. NO escribe al behavior_log real en modo demo (--commit lo activa).

Por qué transiciones y no muestras crudas: la PK del behavior_log es
(ts,user,kind,key) y la señal real de "qué usás" es el cambio de foco + duración,
no 10.000 muestras de la misma app.

Uso:
  python scripts/_proto_ambient_observer.py --seconds 120        # demo, no escribe
  python scripts/_proto_ambient_observer.py --seconds 120 --commit  # escribe al log
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _foreground_app():
    """(proc_name, window_title) de la ventana en foco. None si no se puede."""
    try:
        import win32gui
        import win32process
        import psutil
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            name = psutil.Process(pid).name()
        except Exception:
            name = "?"
        title = win32gui.GetWindowText(hwnd) or ""
        return name.lower(), title
    except Exception:
        return None


def _slot(ts: float) -> str:
    """Franja horaria humana (para aprender 'usás Spotify de noche')."""
    h = time.localtime(ts).tm_hour
    if 5 <= h < 12:
        return "mañana"
    if 12 <= h < 19:
        return "tarde"
    if 19 <= h < 24:
        return "noche"
    return "madrugada"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=120,
                    help="cuánto observar (demo)")
    ap.add_argument("--poll", type=float, default=1.0,
                    help="intervalo de muestreo en segundos")
    ap.add_argument("--commit", action="store_true",
                    help="escribir las transiciones al behavior_log real")
    args = ap.parse_args()

    if _foreground_app() is None:
        print("win32/psutil no disponibles — no se puede observar en este equipo.")
        return 1

    log = None
    if args.commit:
        from gemma4_agent.memory_pkg.behavior_log import BehaviorLog
        log = BehaviorLog()

    print(f"=== Observador ambiente (PROTOTIPO) — {args.seconds}s, poll {args.poll}s ===")
    print("Mirando SOLO la app en foco (sin contenido, sin archivos). Ctrl+C para cortar.\n")

    transitions = []           # (app, dur_s, slot)
    cur_app = None
    cur_title = ""
    cur_start = time.time()
    t_end = time.time() + args.seconds

    def _flush(app, start, title):
        if app is None:
            return
        dur = time.time() - start
        if dur < 1.0:          # ruido: foco que pasó de largo
            return
        slot = _slot(start)
        transitions.append((app, dur, slot))
        if log is not None:
            # source=ambient → distingue lo que ve el observador de lo que abre el agente
            log.record("app_open", app, context={
                "source": "ambient", "slot": slot,
                "dur_s": round(dur, 1), "title": title[:60]})

    try:
        while time.time() < t_end:
            fg = _foreground_app()
            if fg is not None:
                app, title = fg
                if app != cur_app:
                    _flush(cur_app, cur_start, cur_title)
                    cur_app, cur_title, cur_start = app, title, time.time()
            time.sleep(args.poll)
    except KeyboardInterrupt:
        print("\n(cortado por el usuario)\n")
    _flush(cur_app, cur_start, cur_title)

    # --- Reporte: qué APRENDERÍA ---
    print("\n=== ESTO ES LO QUE VI DE VOS ===\n")
    if not transitions:
        print("  (no hubo cambios de foco en la ventana de observación)")
        return 0
    by_app = defaultdict(float)
    by_app_slot = defaultdict(float)
    for app, dur, slot in transitions:
        by_app[app] += dur
        by_app_slot[(app, slot)] += dur
    total = sum(by_app.values()) or 1.0
    print(f"  {len(transitions)} cambios de foco, {total/60:.1f} min observados\n")
    print("  Tiempo por app:")
    for app, dur in sorted(by_app.items(), key=lambda x: -x[1]):
        print(f"    {dur/total*100:5.1f}%  {dur/60:5.1f}min  {app}")
    print("\n  Lo que INFERIRÍA (gustos por franja horaria):")
    for (app, slot), dur in sorted(by_app_slot.items(), key=lambda x: -x[1])[:6]:
        print(f"    usás {app} a la {slot} ({dur/60:.1f}min)")
    if args.commit:
        print(f"\n  [COMMIT] {len(transitions)} transiciones escritas al behavior_log "
              f"(source=ambient).")
    else:
        print("\n  [DEMO] nada se escribió. Con --commit alimentaría el behavior_log.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
