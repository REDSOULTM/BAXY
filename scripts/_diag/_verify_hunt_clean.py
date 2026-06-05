"""Verificación POST-FIX de un (o varios) _hunt_tanda_*.jsonl: chequea que la salida
del re-run con los fixes activos esté limpia, usando detectores OBJETIVOS (sin el
juez LLM, cuyo campo `i` es poco fiable en t3+).

Reporta, agregando sobre todos los archivos pasados:
  - histograma de hard_signals (empty/leak/old_name/tool_call_leaked/tool_loop/slow…)
  - media-fabricado RESIDUAL: replies que TODAVÍA afirman título/plataforma no pedida
    (debería ser 0 tras el inline-repair commit 13ef80f)
  - casos destructivos: replies que afirman destrucción sin evidencia (guard A1)
  - totales por archivo

Uso:
  python scripts/_diag/_verify_hunt_clean.py scripts/_diag/_hunt_tanda_0.jsonl [...]
  python scripts/_diag/_verify_hunt_clean.py            # auto: todos los _hunt_tanda_*.jsonl
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from gemma4_agent.safety_pkg.reply_validator import (  # noqa: E402
    media_fabricated_claim, destructive_claim_without_evidence,
)

DIAG = ROOT / "scripts" / "_diag"
args = sys.argv[1:]
files = ([Path(a) for a in args] if args
         else sorted(DIAG.glob("_hunt_tanda_*.jsonl")))

grand_sig = Counter()
grand_total = 0
grand_media = 0
grand_destr = 0
media_examples = []
destr_examples = []

print(f"Verificando {len(files)} archivo(s)\n")
for f in files:
    if not f.exists():
        print(f"  (falta {f.name})")
        continue
    recs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    sig = Counter()
    media = destr = 0
    for r in recs:
        for s in (r.get("hard_signals") or []):
            # normalizar tool_loop(N)/slow(Ns) a su prefijo para histograma
            key = s.split("(")[0]
            sig[key] += 1
        rep = r.get("reply") or ""
        ut = r.get("user_text") or ""
        tools = r.get("tools") or []
        tc = [{"name": (t.get("name") if isinstance(t, dict) else t),
               "result": {"ok": True}, "args": (t.get("args") if isinstance(t, dict) else {})}
              for t in tools]
        try:
            if media_fabricated_claim(ut, rep, tc):
                media += 1
                if len(media_examples) < 12:
                    media_examples.append((r.get("i"), ut[:40], rep[:70]))
        except Exception:
            pass
        try:
            if destructive_claim_without_evidence(rep, tc):
                destr += 1
                if len(destr_examples) < 12:
                    destr_examples.append((r.get("i"), ut[:40], rep[:70]))
        except Exception:
            pass
    grand_sig += sig
    grand_total += len(recs)
    grand_media += media
    grand_destr += destr
    sig_str = " ".join(f"{k}={v}" for k, v in sorted(sig.items())) or "(ninguna)"
    print(f"  {f.name}: {len(recs)} casos | media_fab_residual={media} destr_residual={destr}")
    print(f"      hard_signals: {sig_str}")

print(f"\n=== TOTAL: {grand_total} casos ===")
print(f"hard_signals: " + " ".join(f"{k}={v}" for k, v in sorted(grand_sig.items())))
print(f"media-fabricado RESIDUAL (debe ser 0 post inline-repair): {grand_media}")
print(f"destructivo-sin-evidencia RESIDUAL (debe ser 0 post guard): {grand_destr}")
if media_examples:
    print("\nEjemplos media-fab residual (BUG si aparecen):")
    for e in media_examples:
        print("  i=%s u=%r -> %r" % e)
if destr_examples:
    print("\nEjemplos destructivo residual (BUG si aparecen):")
    for e in destr_examples:
        print("  i=%s u=%r -> %r" % e)
