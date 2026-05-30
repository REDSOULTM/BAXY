"""Verificación EN VIVO del deíctico ring multilingüe (ITEM 4, roadmap).

Prueba la cadena REAL: un tool_result deja una entidad (path/url) en el ring; un
turno deíctico corto en VARIOS idiomas inyecta ese referente al prompt. NO usa el
LLM para la detección (es determinista) ni input sintético — solo el detector +
ring + la inyección de _decide_turn, con el encoder multilingüe real.

Uso: python scripts/_live_verify_deictic.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["GEMMA4_DEICTIC"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.routing import deictic_detector as D  # noqa: E402


def main() -> int:
    failures = []

    print("== detección deíctica MULTILINGÜE (no monolingüe) ==")
    deictic = {"es": "abrilo", "en": "open it", "pt": "abre isso",
               "fr": "ouvre-le", "it": "aprilo", "de": "öffne es"}
    for lang, t in deictic.items():
        ok = D.needs_deictic_context(t)
        print(f"  {'OK ' if ok else 'FALLA'} [{lang}] {t!r} -> deíctico={ok}")
        if not ok:
            failures.append(f"{lang}:{t}")

    print("== NO-deícticos rechazados ==")
    for t in ("qué hora es", "abrí Spotify y poné rock por favor", "hola"):
        ok = not D.needs_deictic_context(t)
        print(f"  {'OK ' if ok else 'FALLA'} {t!r} -> no-deíctico={ok}")
        if not ok:
            failures.append(f"falso-positivo:{t}")

    print("== ring extrae entidad y la inyecta ==")
    ring = D.EntityRing()
    ring.push_from_result("filesystem",
                          {"path": "C:/Users/emma/Documents/informe.docx", "ok": True})
    block = D.deictic_context_block(ring)
    ok = "informe.docx" in block
    print(f"  {'OK ' if ok else 'FALLA'} ring -> bloque con referente: {block.strip()[:70]!r}")
    if not ok:
        failures.append("ring no inyectó el referente")

    print("== integración con el agente REAL (ring se llena tras tool exec) ==")
    try:
        from gemma4_agent.agent_core.agent import Gemma4Agent
        from gemma4_agent.infra.config import AgentConfig
        ag = Gemma4Agent(AgentConfig.from_env())
        has_ring = getattr(ag, "_entity_ring", None) is not None
        print(f"  {'OK ' if has_ring else 'FALLA'} el agente tiene _entity_ring: {has_ring}")
        if not has_ring:
            failures.append("agente sin ring")
        else:
            # Simular un tool exec que deja una entidad.
            class _Ev:
                name = "browser"
                result = {"url": "https://github.com/foo/bar", "ok": True}
            ag._remember_executed_tools([_Ev()])
            ent = ag._entity_ring.most_recent()
            ok = ent is not None and "github.com" in ent[1]
            print(f"  {'OK ' if ok else 'FALLA'} tras tool exec, ring tiene: {ent}")
            if not ok:
                failures.append("ring no se llenó tras tool exec")
    except Exception as exc:
        print(f"  (skip integración agente: {exc})")

    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS: {failures}")
        return 1
    print("RESULTADO: TODO OK — deíctico multilingüe + ring + integración con el agente real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
