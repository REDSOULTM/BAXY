"""Runner del eval-set GUI — Fase 0 (2026-05-24).

Ejecuta cada misión contra el AGENTE REAL y mide el éxito por el ESTADO DEL SO
(goal_verifier), no por lo que el agente diga. Reporta las métricas que pide el
roadmap:
  - task_success_rate REAL (goal_verifier pass=True)
  - steps por misión (tool_events)
  - latencia por misión (wall-clock)
  - FALSO PASS: el agente reportó éxito (reply afirma hecho / sin error) PERO el
    goal_verifier dice pass=False. Este número es EL crítico — es el bug que
    hundió a Carter.

Uso:
  python -m scripts.gui_eval.run_eval                 # todas las misiones
  python -m scripts.gui_eval.run_eval --tier 1        # solo tier 1
  python -m scripts.gui_eval.run_eval --dry-baseline  # NO corre el agente; solo
       verifica reproducibilidad: reset -> verify debe dar el estado base
       conocido (gate Fase 0). No toca el agente ni el LLM.

NO requiere que el agente esté "bien" — es una FOTO del estado actual para tener
contra qué medir las fases siguientes. Espera que muchas fallen hoy (el GAP del
'click ciego' es justamente lo que vamos a cerrar).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from eval_set import GuiMission, missions_for_tier, get_master_volume, is_muted  # noqa: E402


def _agent_reported_success(reply: str, events: list) -> bool:
    """Heurística honesta de 'el agente CREE que lo hizo': hubo al menos un tool
    event sin error, o el reply no admite fallo. Esto NO es el verificador — es
    para detectar el FALSO PASS (agente cree que sí, SO dice que no)."""
    txt = (reply or "").lower()
    admits_fail = any(k in txt for k in (
        "no pude", "no puedo", "no tengo", "error", "falló", "no encontré",
        "couldn't", "could not", "i can't", "failed", "unable",
        # admisiones de NO completar (el agente fue honesto — no es falso-PASS):
        "no alcancé", "no alcance", "no complet", "no logré", "no logre",
        "¿la repetimos", "la repetimos", "no terminé", "no termine",
        "didn't finish", "did not finish", "couldn't complete", "incomplete",
        "no se completó", "no se completo", "pendiente"))
    return (not admits_fail) and bool(events)


def run_mission(agent, m: GuiMission) -> dict:
    # 1) reset: el HARNESS fija la precondición (no el agente)
    try:
        m.reset()
    except Exception as exc:
        return {"id": m.id, "tier": m.tier, "skipped": f"reset_failed: {exc}"}
    if not m.precheck():
        return {"id": m.id, "tier": m.tier, "skipped": "precheck_false"}
    time.sleep(0.3)

    # 2) ejecutar la utterance contra el AGENTE REAL
    t0 = time.time()
    reply, events, err = "", [], None
    try:
        result = agent.run_text(m.utterance)
        reply = getattr(result, "content", "") or ""
        events = list(getattr(result, "tool_events", []) or [])
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    latency = time.time() - t0
    time.sleep(0.5)  # settling antes de leer el SO

    # 3) verificar por ESTADO DEL SO
    try:
        v = m.goal_verifier()
    except Exception as exc:
        v = {"pass": None, "evidence": f"verifier_raised: {exc}", "actual": None}

    agent_thinks_ok = _agent_reported_success(reply, events)
    false_pass = bool(agent_thinks_ok and v.get("pass") is False)

    return {
        "id": m.id, "tier": m.tier, "utterance": m.utterance,
        "pass": v.get("pass"), "evidence": v.get("evidence"),
        "steps": len(events), "latency_s": round(latency, 2),
        "agent_thinks_ok": agent_thinks_ok, "false_pass": false_pass,
        "reply": reply[:120], "error": err,
    }


def baseline_repro(missions: list[GuiMission]) -> dict:
    """Gate Fase 0: tras reset(), el goal_verifier debe dar un estado CONOCIDO y
    REPRODUCIBLE (sin correr el agente). Para misiones de volumen, reset fija un
    valor != target, así que el verifier debe dar pass=False de forma estable
    (el estado base NO satisface la misión). Esto valida que el verificador LEE
    el SO de forma determinista."""
    rows = []
    for m in missions:
        try:
            m.reset(); time.sleep(0.2)
            v1 = m.goal_verifier(); time.sleep(0.1); v2 = m.goal_verifier()
            stable = v1.get("pass") == v2.get("pass")
            rows.append({"id": m.id, "v1": v1.get("pass"), "v2": v2.get("pass"),
                         "stable": stable, "evidence": v1.get("evidence")})
        except Exception as exc:
            rows.append({"id": m.id, "error": str(exc), "stable": False})
    stable_n = sum(1 for r in rows if r.get("stable"))
    return {"stable": stable_n, "total": len(rows),
            "all_stable": stable_n == len(rows), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, default=None)
    ap.add_argument("--dry-baseline", action="store_true",
                    help="solo reproducibilidad de verificadores, sin agente")
    ap.add_argument("--out", default=str(_HERE / "results_phase0.json"))
    args = ap.parse_args()

    missions = missions_for_tier(args.tier)
    print(f"[gui-eval] {len(missions)} misiones (tier={args.tier or 'all'})")

    if args.dry_baseline:
        print("[gui-eval] DRY BASELINE — reproducibilidad de verificadores (sin agente)")
        rep = baseline_repro(missions)
        for r in rep["rows"]:
            mark = "OK " if r.get("stable") else "XX "
            print(f"  {mark}{r['id']:20} v1={r.get('v1')} v2={r.get('v2')} | {r.get('evidence') or r.get('error')}")
        print(f"\n[gate Fase 0] verificadores estables: {rep['stable']}/{rep['total']} "
              f"-> {'PASS' if rep['all_stable'] else 'FAIL (verificador no determinista)'}")
        return 0 if rep["all_stable"] else 1

    # Corrida real contra el agente
    import os
    os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
    from gemma4_agent.agent import Gemma4Agent
    agent = Gemma4Agent()
    print("[gui-eval] agente construido; corriendo misiones contra el SO real...\n")

    # progreso incremental observable: una línea JSON por misión, flush inmediato.
    prog_path = Path(args.out).with_suffix(".progress.jsonl")
    prog_path.write_text("", encoding="utf-8")
    rows = []
    for idx, m in enumerate(missions, 1):
        r = run_mission(agent, m)
        rows.append(r)
        if "skipped" in r:
            line = f"[{idx}/{len(missions)}] SKIP {r['id']} ({r['skipped']})"
        else:
            mark = {True: "PASS", False: "FAIL", None: "INCONC"}.get(r["pass"], "?")
            fp = " <<FALSO-PASS" if r["false_pass"] else ""
            line = (f"[{idx}/{len(missions)}] {mark:6} {r['id']:24} "
                    f"steps={r['steps']} {r.get('latency_s')}s | {r.get('evidence')}{fp}")
        print(line, flush=True)            # flush para monitoreo en vivo
        with prog_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")  # incremental a disco
        try:
            agent.clear()
        except Exception:
            pass

    scored = [r for r in rows if "skipped" not in r]
    passes = sum(1 for r in scored if r["pass"] is True)
    fails = sum(1 for r in scored if r["pass"] is False)
    inconc = sum(1 for r in scored if r["pass"] is None)
    false_passes = sum(1 for r in scored if r["false_pass"])
    lat = [r["latency_s"] for r in scored if r.get("latency_s")]
    lat.sort()
    p50 = lat[len(lat)//2] if lat else 0
    p95 = lat[int(len(lat)*0.95)] if lat else 0
    summary = {
        "total": len(scored), "pass": passes, "fail": fails, "inconclusive": inconc,
        "task_success_rate": round(passes / max(1, len(scored)), 3),
        "false_pass_count": false_passes,
        "false_pass_rate": round(false_passes / max(1, len(scored)), 3),
        "latency_p50_s": p50, "latency_p95_s": p95,
    }
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows},
                                          indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== RESUMEN FASE 0 (estado actual, contra el SO real) ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n>> FALSO-PASS rate = {summary['false_pass_rate']} "
          f"(el número crítico: agente cree que sí, SO dice que no)")
    print(f">> resultados en {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
