"""Construye el dataset COMPLETO de turnos reales del usuario desde traces.jsonl.

Cada turno = user_text (router_reasoning) + subset ofrecido + tools ejecutadas
(tool_call/tool_result) + short-circuits + reply final (final.content) + señales
de fallo (rescue_missed, forced_tool_retry, reply_anti_pattern_detected,
false_confirmation_caught, tool_call_skipped_when_expected, verifier_disagrees).

Filtra los turnos generados por MIS tests (heurística: turnos cuyo user_text es
idéntico a frases de test conocidas y que ocurren en ráfaga 05:xx-06:xx del 04, o
sin reply 'final'). El resultado es lo que el USUARIO realmente dijo por voz.

Uso: python scripts/_diag/_diag_build_turn_dataset.py
Salida: _out_user_turns.json (lista ordenada) + resumen de candidatos a fallo.
"""
import json
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRACES = REPO / "gemma4_agent" / "data" / "traces.jsonl"

FAIL_KINDS = {
    "rescue_missed", "forced_tool_retry", "forced_tool_retry_empty",
    "reply_anti_pattern_detected", "false_confirmation_caught",
    "tool_call_skipped_when_expected", "verifier_disagrees",
    "fallback_emitted", "cu_step_retry", "error_recovery_hint",
}

# Frases que YO usé en tests/diagnósticos esta sesión (para excluirlas del
# análisis de turnos del USUARIO). Se comparan normalizadas/substring.
MY_TEST_PHRASES = [
    "en la calculadora apret", "escribi 2+2", "escribi hola mundo",
    "que juego estoy jugando", "bixby", "paxi", "max ", "que dia es hoy",
    "cuanta ram", "te espero en casa", "llego en 10", "decile a juan que te espero",
    "abre el navegador", "me abri el navegador", "escribile a seba",
    "mandale a mama", "escribile a ana en whatsapp", "decile a pedro en telegram",
    "escribile a juan en slack", "cuanta ram tengo", "what game am i playing",
]


def load(path: Path) -> list[dict]:
    out = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def norm(s: str) -> str:
    return (s or "").strip().lower()


def main() -> None:
    events = load(TRACES)
    turns: "OrderedDict[str, list[dict]]" = OrderedDict()
    for e in events:
        turns.setdefault(e.get("turn_id", "?"), []).append(e)

    rows = []
    for tid, evs in turns.items():
        by_kind = {}
        for e in evs:
            by_kind.setdefault(e.get("kind"), []).append(e)
        rr = by_kind.get("router_reasoning", [{}])[0]
        user_text = rr.get("user_text") or ""
        if not user_text.strip():
            # sin texto de usuario -> no es un turno conversacional (boot, etc.)
            continue
        fin = by_kind.get("final", [{}])[0]
        reply = fin.get("content") or ""
        subset = rr.get("final_subset") or []
        tool_calls = [e.get("name") or e.get("tool") or e.get("args")
                      for e in by_kind.get("tool_call", [])]
        shortcircuits = [k for k in by_kind
                         if k and k.endswith("shortcircuit")]
        fails = [k for k in by_kind if k in FAIL_KINDS]
        ts = evs[0].get("ts", "")

        is_mine = any(p in norm(user_text) for p in MY_TEST_PHRASES)

        rows.append({
            "turn_id": tid, "ts": ts, "user_text": user_text,
            "subset": subset, "tool_calls": tool_calls,
            "shortcircuits": shortcircuits, "fail_signals": fails,
            "reply": reply, "is_my_test": is_mine,
        })

    user_rows = [r for r in rows if not r["is_my_test"]]
    out = Path(__file__).resolve().parent / "_out_user_turns.json"
    out.write_text(json.dumps(user_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Total turnos con user_text: {len(rows)}")
    print(f"  - mis tests (excluidos):  {sum(r['is_my_test'] for r in rows)}")
    print(f"  - turnos del USUARIO:     {len(user_rows)}")
    print(f"-> volcados a {out}")

    flagged = [r for r in user_rows if r["fail_signals"]]
    print(f"\n=== {len(flagged)} turnos del usuario con SEÑAL DE FALLO ===")
    for r in flagged:
        print(f"  [{r['ts'][:19]}] {r['user_text']!r:45} fails={r['fail_signals']}")

    print(f"\n=== TODOS los turnos del usuario (índice) ===")
    for r in user_rows:
        flag = "⚠" if r["fail_signals"] else " "
        print(f" {flag}[{r['ts'][:19]}] {r['user_text']!r:42} -> {(r['reply'] or '(sin reply)')[:55]!r}")


if __name__ == "__main__":
    main()
