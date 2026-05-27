"""Broad end-to-end smoke test through the FULL agent.

Categories with 5+ commands each. For each: route through ag.run_text(),
record whether a domain tool was called (when expected), the reply, and
latency. Assumes a llama-server is healthy on :8080 (the active profile).

--fresh : build a NEW agent per case (clean history). This mirrors PROD,
          where history is compacted between turns; the shared-session mode
          (default) stress-tests long-context degradation on weak quants.
          NOTE --fresh is much slower (re-warm per case).

Run: python scripts/smoke_e2e.py [--runs 1] [--fresh] [--only cat1,cat2]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# (category, command, expects_tool)
CASES: list[tuple[str, str, bool]] = [
    # --- apps (open/close) ---
    ("apps", "abre steam", True),
    ("apps", "abre la calculadora", True),
    ("apps", "cierra el bloc de notas", True),
    ("apps", "abre el explorador de archivos", True),
    ("apps", "abre el bloc de notas", True),
    ("apps", "abre la configuracion de windows", True),
    # --- audio (volume/mute) ---
    ("audio", "pon el volumen al 30", True),
    ("audio", "sube el volumen", True),
    ("audio", "mutea el sonido", True),
    ("audio", "baja el volumen a la mitad", True),
    ("audio", "pon el volumen al maximo", True),
    ("audio", "quita el silencio", True),
    # --- media (play/pause/next) ---
    ("media", "pon musica en spotify", True),
    ("media", "pausa la musica", True),
    ("media", "reproduce la siguiente cancion", True),
    ("media", "pon un video de lofi en youtube", True),
    ("media", "cancion anterior", True),
    ("media", "reanuda la musica", True),
    # --- window (minimize/maximize/close) ---
    ("window", "minimiza todas las ventanas", True),
    ("window", "maximiza la ventana actual", True),
    ("window", "cierra esta ventana", True),
    ("window", "minimiza la ventana actual", True),
    ("window", "restaura la ventana", True),
    # --- system (screenshot/processes/time) ---
    ("system", "saca un screenshot", True),
    ("system", "que hora es", False),       # answerable from system tool OR text
    ("system", "cuanta RAM estoy usando", True),
    ("system", "que dia es hoy", False),
    ("system", "lista los procesos que mas consumen", True),
    # --- knowledge (no tool needed; web optional) ---
    ("knowledge", "quien es batman", False),
    ("knowledge", "de que trata la pelicula inception", False),
    ("knowledge", "que es una GPU", False),
    ("knowledge", "cuanto es 25 por 4", False),
    ("knowledge", "explicame que es la fotosintesis", False),
    # --- chitchat (NO tool, no 'Listo') ---
    ("chitchat", "hola", False),
    ("chitchat", "gracias", False),
    ("chitchat", "como estas", False),
    ("chitchat", "quien eres", False),
    ("chitchat", "buenas noches", False),
    ("chitchat", "que puedes hacer", False),
    # --- multilingual action ---
    ("multilang", "open steam", True),
    ("multilang", "take a screenshot", True),
    ("multilang", "ouvre le navigateur", True),
    ("multilang", "schliesse das fenster", True),
    ("multilang", "turn up the volume", True),
    ("multilang", "apri la calcolatrice", True),
    # --- multi-step ---
    ("multistep", "abre chrome y busca gatos", True),
    ("multistep", "abre spotify y pon rock", True),
    ("multistep", "saca un screenshot y guardalo", True),
    ("multistep", "sube el volumen y pon musica", True),
]


def _build_agent():
    from gemma4_agent.agent import Gemma4Agent
    from gemma4_agent.config import AgentConfig
    return Gemma4Agent(AgentConfig.from_env())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--fresh", action="store_true",
                    help="new agent per case (clean history, prod-like)")
    ap.add_argument("--only", type=str, default="",
                    help="comma-separated categories to run")
    args = ap.parse_args()
    os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")

    only = {c.strip() for c in args.only.split(",") if c.strip()}
    cases = [c for c in CASES if not only or c[0] in only]

    shared = None
    if not args.fresh:
        shared = _build_agent()
        shared.run_text("hola")  # warm

    by_cat: dict[str, list[bool]] = defaultdict(list)
    lat_cat: dict[str, list[float]] = defaultdict(list)
    fails: list[tuple[str, str, str]] = []

    for cat, cmd, expects in cases:
        for _ in range(args.runs):
            ag = _build_agent() if args.fresh else shared
            seen: list[str] = []

            def progress(stage, info=None):
                seen.append(stage)

            t = time.time()
            try:
                r = ag.run_text(cmd, progress=progress)
                reply = (getattr(r, "content", None) or "")[:70]
                err = getattr(r, "error", None)
            except Exception as exc:
                reply = ""; err = f"EXC {type(exc).__name__}: {exc}"
            dt = time.time() - t
            called = any("tool_start" in s or "tool_end" in s for s in seen)
            lat_cat[cat].append(dt)
            if err:
                ok = False
                fails.append((cat, cmd, f"ERROR: {err}"))
            elif expects:
                ok = called
                if not ok:
                    fails.append((cat, cmd, f"no tool called; reply={reply!r}"))
            else:
                # chitchat: must NOT falsely claim an action / 'Listo' on no tool
                bad_listo = (not called) and reply.lower().startswith("listo")
                ok = not bad_listo
                if not ok:
                    fails.append((cat, cmd, f"'Listo' on no-tool turn: {reply!r}"))
            by_cat[cat].append(ok)
            print(f"  [{cat:9s}] {'OK ' if ok else 'XX '} {cmd[:38]:40s} "
                  f"tool={called} {dt:4.1f}s | {reply!r}", flush=True)

    mode = "FRESH/turn" if args.fresh else "SHARED session"
    print(f"\n==== SMOKE E2E SUMMARY ({mode}) ====")
    tot_ok = tot = 0
    for cat in dict.fromkeys(c for c, _, _ in cases):
        oks = by_cat[cat]
        avg = sum(lat_cat[cat]) / max(1, len(lat_cat[cat]))
        tot_ok += sum(oks); tot += len(oks)
        print(f"  {cat:10s} {sum(oks)}/{len(oks)}  avg {avg:4.1f}s"
              + ("" if sum(oks) == len(oks) else "  <-- has failures"))
    print(f"\n  OVERALL: {tot_ok}/{tot} = {tot_ok/max(1,tot):.2f}")
    if fails:
        print(f"\n  === {len(fails)} FAILURES ===")
        for cat, cmd, why in fails:
            print(f"    [{cat}] {cmd!r}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
