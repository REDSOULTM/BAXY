"""Router evaluation against the hand-curated ground-truth corpus.

Sprint 8 (2026-05-20): a second agent curated the full historical corpus
(this project's logs + Carter v1–v5) into a clean ground truth, every row
labeled by hand/guide (no automatic oracle — that corrupted labels):

    gemma4_agent/data/router_eval_corpus.curated.jsonl   (1733 rows)

Each row: {"q", "expected": ["tool", ...] | [], "source", "label_origin"}
  - expected non-empty → RECALL: at least one acceptable tool must be in
    the router's subset (any one of the listed tools counts as a hit).
  - expected == []     → NO-TOOL: the router must NOT pull a domain tool
    (smalltalk, knowledge the LLM answers itself, behavior directives).

The tools are already in the current 65-compound vocabulary, so no legacy
mapping is needed. We route each query through the REAL planner, passing
the previous user turn as context when available so continuation prompts
get what the planner sees at runtime.

Run:
    python scripts/router_eval.py
    python scripts/router_eval.py --show-fails
    python scripts/router_eval.py --by-tool        # per-tool recall table
    python scripts/router_eval.py --corpus <path>  # eval a different file
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CURATED = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
# Map query → previous user turn, reconstructed from the ordered logs
# (the curated corpus dropped temporal order). Lets continuation prompts
# ("ciérralo", "haz lo mismo") be routed with the context the planner has
# at runtime. Built by the snippet in this sprint; regenerate if logs grow.
_PREV_MAP_PATH = ROOT / "gemma4_agent" / "data" / "router_prev_map.json"
try:
    _PREV_MAP = json.loads(_PREV_MAP_PATH.read_text(encoding="utf-8")) \
        if _PREV_MAP_PATH.exists() else {}
except Exception:
    _PREV_MAP = {}

# Anti-overfit holdout. Each row is assigned to dev (80%) or holdout (20%)
# by a STABLE hash of its query text — independent of file order, fixed
# across runs, and not derivable from the planner. We develop/tune against
# dev ONLY and report the holdout as the honest, never-seen-in-dev number.
_HOLDOUT_SALT = "router-eval-2026-05-20"


def _split_of(q: str) -> str:
    h = hashlib.sha256((_HOLDOUT_SALT + q).encode("utf-8")).hexdigest()
    return "holdout" if (int(h[:8], 16) % 5 == 0) else "dev"

# Utility tools that are always reachable / harmless; their presence does
# NOT count as "the router pulled a domain tool" for the no-tool metric.
_NON_DOMAIN = {"session", "safety", "state", "verify"}


# ---- slice tagging (Step 0, 2026-05-21) --------------------------------------
# Every research model demanded the same anti-overfit discipline: never report
# only an aggregate. A model that scores 0.90 overall by being 0.99 on the easy
# slice and 0.40 on the hard one is worse than a balanced 0.88. So we tag each
# row with the slices it belongs to and report metrics per slice. Slices are
# derived from the query text only (no labels), so they can't leak the answer.
_LANG_HINTS = {
    "en": (" the ", " what ", " how ", " open ", " close ", " play ", " is ",
           "who ", "what'", "show me", " my ", " me ", " to ", " a "),
    "fr": ("ouvre", "ferme", "qu'est", "quel", "pourquoi", " le ", " la ",
           "comment", "qui est", "s'il", "peux-tu"),
    "de": ("öffne", "schließe", "was ist", "wer ist", "wie", " der ", " die ",
           " das ", "kannst du", "bitte"),
    "it": ("apri", "chiudi", "cos'è", "che cosa", "perché", " il ", " la ",
           "chi è", "puoi"),
    "pt": ("abre", "fecha", "o que", "quem é", "por que", " você ", "abrir",
           "qual é", "pode "),
}


def _detect_lang(q: str) -> str:
    """Cheap heuristic language tag for slicing. NOT used for routing — only
    so we can report recall per language and catch a Spanish-only overfit.
    Defaults to 'es' (the dominant language) when no other hint dominates."""
    low = " " + q.casefold() + " "
    scores = {lang: sum(low.count(h) for h in hints)
              for lang, hints in _LANG_HINTS.items()}
    best = max(scores, key=lambda k: scores[k])
    # require at least 2 hint hits to override the Spanish default — one stray
    # English article in a Spanish query shouldn't flip the tag.
    return best if scores[best] >= 2 else "es"


_CONTINUATION_MARKERS = re.compile(
    r"^\s*(lo|la|los|las|le|les)\b|"          # bare clitic pronoun start
    r"\b(cierralo|cierrala|abrelo|abrela|subelo|bajalo|mutealo|ponlo|quitalo|"
    r"dale|otra vez|de nuevo|lo mismo|igual|tambien|ahora|mejor)\b|"
    r"\b(close it|open it|turn it|do the same|again|now|instead)\b",
    re.IGNORECASE,
)


def _slices_of(r: dict) -> set[str]:
    """Slices this row belongs to (from the QUERY only, never the label)."""
    q = r["q"]
    s: set[str] = set()
    wc = len(q.split())
    if wc <= 4:
        s.add("short")
    lang = _detect_lang(q)
    s.add(f"lang:{lang}")
    if lang != "es":
        s.add("multilingual")
    if _CONTINUATION_MARKERS.search(q) or wc <= 2:
        s.add("continuation")
    if not (r.get("expected") or []):
        s.add("no_tool")
    else:
        s.add("tool")
    return s


def run_router(q: str, prev: str | None = None) -> set[str]:
    # safety_enabled=True mirrors production: the planner appends `safety`
    # so risky actions ("formatea el pendrive", "edita el registry") can be
    # gated. Running with it off hid the safety tool from the subset.
    # prev is the PREVIOUS USER TURN (corpus `prev` field), passed as
    # prev_user_text so deictic continuations can resolve their referent —
    # this is what the planner sees at runtime when context is available.
    from gemma4_agent.routing.planner import select_tool_names, plan_mission
    return set(select_tool_names(
        q, plan_mission(q), safety_enabled=True,
        prev_user_text=prev,
    ))


def _warm_router_for_eval() -> None:
    """Mirror production readiness: evaluate the hot semantic router, not the
    degraded fallback used only if boot warmup fails."""
    t0 = time.perf_counter()
    try:
        from gemma4_agent.routing import semantic_router
        if semantic_router.is_enabled():
            semantic_router._ensure_loaded()
        from gemma4_agent.routing import intent_router
        intent_router._ensure_centroids()
        intent_router._ensure_shop_centroids()
        intent_router._ensure_nav_centroids()
        intent_router._ensure_email_centroids()
        try:
            from gemma4_agent.routing import exemplar_router
            exemplar_router.match("warmup")
        except Exception:
            pass
        try:
            from gemma4_agent.safety_pkg import abstain_head, tool_head
            if abstain_head.is_enabled():
                abstain_head.load_model()
            if tool_head.is_enabled():
                tool_head.load()
        except Exception:
            pass
        print(f"  (warmup: semantic router hot in {(time.perf_counter() - t0):.2f}s)")
    except Exception as exc:
        print(f"  (warmup warning: semantic router not hot: {type(exc).__name__}: {exc})")


# ---- runtime inherit_tools simulation -------------------------------------
# The harness above measures the router IN ISOLATION. Production does more:
# when the router returns no domain tool AND the turn is a short continuation
# ("ciérralo", "mutea"), agent.py inherits the tools the PRIOR turn actually
# executed (NOT the prior text — the deictic's referent lives in the executed
# tool). --inherit reproduces that so we see the real production recall.
# We mirror agent.py's rules: <=6 words, and never inherit dangerous tools.
try:
    from gemma4_agent.agent_core.agent import DANGEROUS_TOOLS_NEVER_INHERIT as _DANGEROUS
except Exception:
    _DANGEROUS = frozenset({
        "whatsapp", "whatsapp_send", "file_delete", "file_write",
        "system_shutdown", "system_logoff", "system_restart",
        "subprocess", "shell",
    })


def _build_executed_map(rows: list[dict]) -> dict[str, list[str]]:
    """Approximate 'what tool ran on turn T' by T's curated expected tools.
    This is the signal agent.py inherits from real tool-call history; on the
    corpus the closest proxy is the prior turn's ground-truth label."""
    return {r["q"].strip().lower(): list(r.get("expected") or []) for r in rows}


def _inherit_from_prev(q: str, prev: str | None,
                       executed: dict[str, list[str]]) -> set[str]:
    """Mirror agent.py inherit_tools: for a short continuation with a known
    prior turn, inherit that turn's executed (non-dangerous) tools."""
    if not prev:
        return set()
    if len(q.split()) > 6:           # same <=6-word gate as runtime
        return set()
    # Step 5: mirror agent.py — do NOT inherit when the abstain head is
    # confident the turn is conversational (smalltalk/meta), only when it's a
    # genuine deictic continuation. Keeps with-context no-tool keep honest.
    if _head_strongly_abstains(q):
        return set()
    prior = executed.get(prev.strip().lower())
    if not prior:
        return set()
    return {t for t in prior if t not in _DANGEROUS}


def _head_strongly_abstains(q: str) -> bool:
    """True when the calibrated abstain head is confident (p >= max(thr,0.80))
    that q is no-tool. Matches the runtime inherit gate in agent.py."""
    try:
        from gemma4_agent.safety_pkg.abstain_head import (
            load_model, build_features, is_enabled,
        )
        if not is_enabled():
            return False
        m = load_model()
        if m is None:
            return False
        from gemma4_agent.routing.intent_router import classify_intent
        from gemma4_agent.routing.semantic_router import suggest_tools_scored
        intent = None
        try:
            intent = classify_intent(q)
        except Exception:
            intent = None
        feats = build_features(q, intent=intent,
                               scored=suggest_tools_scored(q, k=12),
                               keyword_fired=False)
        return m.p_no_tool(feats) >= m.threshold
    except Exception:
        return False


def _evaluate(rows: list[dict], use_prev: bool = False,
              inherit: bool = False, all_rows: list[dict] | None = None,
              equiv: bool = False):
    recall_total = recall_ok = 0
    notool_total = notool_ok = 0
    recall_fails: list[tuple[str, list[str], list[str]]] = []
    notool_fails: list[tuple[str, list[str]]] = []
    per_tool = collections.defaultdict(lambda: [0, 0])
    # PRECISIÓN (2026-05-29, pedido del usuario: ofrecer SOLO lo necesario, no ruido).
    # Para cada turno-con-tool medimos el RUIDO = tools de dominio ofrecidas que NO
    # estaban esperadas. domain_subset = subset menos las non-domain (session/safety/
    # state/verify, siempre alcanzables). noise = |domain_subset \ expected|.
    # Un router perfecto: domain_subset == expected (noise 0). Hoy ~3.7 de ruido.
    precision_rows = 0          # turnos con tool evaluados
    domain_size_sum = 0         # suma de |domain_subset| (para el promedio)
    noise_sum = 0               # suma de tools de dominio EXTRA (el ruido)
    noisy_examples: list[tuple[str, list[str], list[str]]] = []  # (q, expected, extra)
    # per-slice [recall_ok, recall_total, notool_ok, notool_total]
    per_slice = collections.defaultdict(lambda: [0, 0, 0, 0])
    # executed-tool map for the inherit simulation (built from the WHOLE
    # corpus, not just this split, because a continuation's prior turn may
    # live in the other split).
    executed = _build_executed_map(all_rows if all_rows is not None else rows) if inherit else {}

    for r in rows:
        q = r["q"]
        expected = r.get("expected") or []
        # --use-prev measures the realistic production case: the planner
        # gets the previous user turn (corpus `prev`) so deictic
        # continuations can resolve. Default (no prev) is the honest
        # isolated number — how the router does with zero context.
        prev = (r.get("prev") if (use_prev or inherit) else None)
        subset = run_router(q, prev)
        # --inherit: reproduce agent.py's continuation inheritance. Like the
        # runtime, only kicks in when the router pulled NO domain tool.
        if inherit and not (subset - _NON_DOMAIN):
            subset |= _inherit_from_prev(q, prev, executed)
        slices = _slices_of(r)
        if expected:
            recall_total += 1
            # --equiv: cuenta hit si el router ofreció una tool del MISMO dominio
            # (expected_equiv), no solo la exacta. Separa el miss-real del label
            # ruidoso. El RUIDO (precisión) se sigue midiendo contra el estricto.
            _hit_set = set(r.get("expected_equiv") or expected) if equiv else set(expected)
            hit = bool(subset & _hit_set)
            if hit:
                recall_ok += 1
            else:
                recall_fails.append((q, expected, sorted(subset)))
            # PRECISIÓN: cuánto RUIDO (tools de dominio extra) ofrece el router.
            domain_subset = subset - _NON_DOMAIN
            extra = domain_subset - set(expected)
            precision_rows += 1
            domain_size_sum += len(domain_subset)
            noise_sum += len(extra)
            if len(extra) >= 3:  # turnos especialmente ruidosos
                noisy_examples.append((q, expected, sorted(extra)))
            for t in expected:
                per_tool[t][1] += 1
                if hit:
                    per_tool[t][0] += 1
            for sl in slices:
                per_slice[sl][1] += 1
                if hit:
                    per_slice[sl][0] += 1
        else:
            notool_total += 1
            ok = not (subset - _NON_DOMAIN)
            if ok:
                notool_ok += 1
            else:
                notool_fails.append((q, sorted(subset - _NON_DOMAIN)))
            for sl in slices:
                per_slice[sl][3] += 1
                if ok:
                    per_slice[sl][2] += 1
    return {
        "recall_ok": recall_ok, "recall_total": recall_total,
        "notool_ok": notool_ok, "notool_total": notool_total,
        "recall_fails": recall_fails, "notool_fails": notool_fails,
        "per_tool": per_tool, "per_slice": per_slice,
        "precision_rows": precision_rows,
        "domain_size_sum": domain_size_sum, "noise_sum": noise_sum,
        "noisy_examples": noisy_examples,
    }


def _print_block(name: str, m: dict) -> None:
    rt, ro = m["recall_total"], m["recall_ok"]
    nt, no = m["notool_total"], m["notool_ok"]
    print(f"  [{name}]  TOOL RECALL {ro}/{rt}={ro/max(1,rt):.4f}   "
          f"NO-TOOL keep {no}/{nt}={no/max(1,nt):.4f}   "
          f"(recall misses {len(m['recall_fails'])}, "
          f"over-offers {len(m['notool_fails'])})")
    # PRECISIÓN (pedido del usuario): subset de dominio promedio + ruido promedio.
    pr = m.get("precision_rows", 0)
    if pr:
        avg_dom = m["domain_size_sum"] / pr
        avg_noise = m["noise_sum"] / pr
        print(f"  [{name}]  PRECISIÓN: subset-dominio medio {avg_dom:.2f} tools/turno  "
              f"RUIDO medio {avg_noise:.2f} extra/turno  "
              f"(turnos muy ruidosos ≥3: {len(m['noisy_examples'])})")


def main() -> int:
    # Fix ceguera cp1252 (2026-05-29): en Windows el stdout default es cp1252 y
    # crashea al imprimir queries non-latin (ru/ja/zh/ar) del held-out de idioma.
    # Forzar UTF-8 para poder EVALUAR esos idiomas (antes ni se imprimían).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--prod-exemplars", action="store_true",
                    help="usar el exemplar store COMPLETO (incl. holdout). Default: "
                         "se EXCLUYE el holdout del store (eval honesto — el holdout "
                         "no se matchea contra sí mismo, que inflaba el recall a 100%).")
    ap.add_argument("--show-fails", action="store_true")
    ap.add_argument("--by-tool", action="store_true")
    ap.add_argument("--slices", action="store_true",
                    help="report recall + no-tool keep per slice (short, "
                         "continuation, multilingual, per-language). Anti-"
                         "overfit: a balanced 0.88 beats a lopsided 0.90.")
    ap.add_argument("--corpus", type=Path, default=CURATED)
    ap.add_argument("--equiv", action="store_true",
                    help="cuenta hit si el router ofreció una tool del MISMO "
                         "dominio (expected_equiv), separando miss-real de label "
                         "ruidoso. Solo aplica a corpus con expected_equiv.")
    ap.add_argument("--split", choices=["dev", "holdout", "all", "both"],
                    default="both")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-warmup", action="store_true",
                    help="measure degraded/no-warmup router path instead of "
                         "the production hot path")
    ap.add_argument("--use-prev", action="store_true",
                    help="pass the previous user turn (realistic production "
                         "context) so deictic continuations can resolve")
    ap.add_argument("--inherit", action="store_true",
                    help="simulate agent.py inherit_tools: short continuations "
                         "with no router tool inherit the prior turn's executed "
                         "tools. This is the REAL production recall (the router "
                         "alone under-measures it).")
    args = ap.parse_args()

    if not args.corpus.exists():
        print(f"corpus missing: {args.corpus}")
        return 1
    rows = [json.loads(l) for l in args.corpus.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    dev = [r for r in rows if _split_of(r["q"]) == "dev"]
    hold = [r for r in rows if _split_of(r["q"]) == "holdout"]

    print("=" * 70)
    print(f"Router eval — {args.corpus.name}  ({len(rows)} rows; "
          f"dev={len(dev)} holdout={len(hold)})")
    print("=" * 70)
    if not args.skip_warmup:
        _warm_router_for_eval()

    # EVAL HONESTO: excluir el holdout del exemplar store -> el holdout no se matchea
    # contra sí mismo (memorización). El store de PRODUCCIÓN no se toca. --prod-exemplars
    # vuelve al comportamiento viejo (store completo, recall inflado a 100%).
    if not args.prod_exemplars:
        try:
            from gemma4_agent.routing import exemplar_router as _exr
            _exr.set_exclude({r["q"] for r in hold})
            print(f"  [eval honesto] exemplar store SIN holdout ({len(hold)} queries "
                  f"excluidas); el recall de holdout es generalización real, no memoria.")
        except Exception as _exc:
            print(f"  WARN: no se pudo excluir el holdout del exemplar: {_exc}")

    targets = []
    if args.split in ("dev", "both"):
        targets.append(("dev", dev))
    if args.split in ("holdout", "both"):
        targets.append(("holdout", hold))
    if args.split == "all":
        targets.append(("all", rows))

    if args.use_prev:
        print("  (context mode: passing previous user turn — production-like)")
    if args.inherit:
        print("  (inherit mode: simulating agent.py continuation inheritance "
              "— REAL production recall)")
    last = None
    for name, subset_rows in targets:
        m = _evaluate(subset_rows, use_prev=args.use_prev,
                      inherit=args.inherit, all_rows=rows, equiv=args.equiv)
        _print_block(name, m)
        last = (name, m)

    # detail uses the LAST evaluated split (so --split holdout --show-fails
    # shows holdout fails; default 'both' shows holdout detail).
    if last and (args.by_tool or args.show_fails or args.slices):
        name, m = last
        if args.slices:
            print(f"\n  per-slice on [{name}]  (recall | no-tool keep):")
            order = ["tool", "no_tool", "short", "continuation", "multilingual",
                     "lang:es", "lang:en", "lang:fr", "lang:de", "lang:it",
                     "lang:pt"]
            ps = m["per_slice"]
            for sl in order:
                if sl not in ps:
                    continue
                ro, rt, no, nt = ps[sl]
                rec = f"{ro}/{rt}={ro/rt:.3f}" if rt else "    n/a    "
                ntk = f"{no}/{nt}={no/nt:.3f}" if nt else "    n/a    "
                print(f"    {sl:14s} recall {rec:18s} no-tool {ntk}")
        if args.by_tool:
            print(f"\n  per-tool recall on [{name}] (hit/total):")
            for t, (h, n) in sorted(m["per_tool"].items(), key=lambda x: -x[1][1]):
                flag = "" if h == n else "  <-- misses"
                print(f"    {t:16s} {h:4d}/{n:<4d} = {h/max(1,n):.3f}{flag}")
        if args.show_fails:
            print(f"\n--- RECALL misses on [{name}] ---")
            for q, exp, sub in m["recall_fails"][:120]:
                print(f"  {q[:60]!r}\n     expected={exp}  subset={sub}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
