"""Detect turns whose contractual decision can depend on semantic readiness.

``catalog.configure`` publishes a lexical ``PlannerCatalog`` synchronously and
promotes a semantic one in the background, so for the first seconds of a
session the prompt of the primary contract is composed without preferred
families, semantic scores or retrieved evidence.  Any turn whose prompt
composition differs between those two regimes *can* receive a different
decision purely because of when it arrived.

This detector reproduces both regimes over the same corpus without asking the
model anything:

* a turn resolved by the deterministic recognizer never reaches the prompt, so
  it is regime-independent by construction;
* for every other turn it diffs the shortlist, the preferred families and the
  retrieved evidence between the lexical regime and the promoted one;
* it repeats the promoted regime with warm caches to prove the semantic
  resources are themselves deterministic.

It dispatches no Core operation, changes no registered asset and produces one
JSON artifact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
from typing import Any


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    public_runtime_identity,
    resolve_runtime_from_args,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    TURN_TEXTS,
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)

DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "promotion_boundary_decisions_20260730.json"
)
PROMOTION_DEADLINE_SECONDS = 185.0


def _corpus() -> list[tuple[str, str]]:
    """Return (source, text) rows for every corpus this campaign owns."""

    from baxy_mind.tools.router_bank_sources import ABSTAIN_POOLS, POSITIVE_POOLS

    rows: list[tuple[str, str]] = [
        (f"workload:turn-{index:02d}", text)
        for index, text in enumerate(TURN_TEXTS)
    ]
    for label, texts in POSITIVE_POOLS.items():
        rows.extend((f"positive:{label}", text) for text in texts)
    for label, texts in ABSTAIN_POOLS.items():
        rows.extend((f"abstain:{label}", text) for text in texts)
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for source, text in rows:
        key = " ".join(text.split()).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append((source, text))
    return unique


def _composition(
    catalog: Any,
    turn_evidence: Any,
    encoder: Any,
    text: str,
    *,
    semantic: bool,
) -> dict[str, Any]:
    """Reproduce exactly what the primary contract would see for one turn."""

    from baxy_mind.__main__ import _turn_evidence_query

    families = (
        tuple(turn_evidence.candidate_families(text, encoder)) if semantic else ()
    )
    shortlist = catalog.shortlist(text, preferred_families=families)
    names = [tool.name for tool in shortlist]
    evidence = (
        turn_evidence.retrieve(_turn_evidence_query(text, []), encoder, names)
        if semantic
        else []
    )
    return {
        "families": list(families),
        "shortlist": names,
        "evidence": [str(item.get("operation") or "") for item in evidence],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)

    runtime = resolve_runtime_from_args(arguments)
    if str(runtime.python_path) not in sys.path:
        sys.path.insert(0, str(runtime.python_path))
    # El worker E5 se lanza como subproceso con ``sys.executable``: hereda el
    # entorno, no ``sys.path``. Se publica el mismo entorno que usa el sidecar.
    existing_python_path = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(runtime.python_path) + (
        os.pathsep + existing_python_path if existing_python_path else ""
    )
    os.environ["PYTHONUTF8"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"

    core = discover_core(arguments.core, candidates=DEFAULT_CORE_CANDIDATES)
    capabilities = current_core_capabilities(core)

    from baxy_mind.__main__ import (
        BACKGROUND_ENCODER_TIMEOUT_SECONDS,
        _create_planner_resources,
        configure_tools,
    )
    from baxy_mind.effect_intent import (
        build_application_catalog_index,
        resolve_explicit_effects,
    )
    from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
    from baxy_mind.turn_evidence import TurnEvidenceService

    tools = configure_tools(capabilities)
    available_operations = tuple(
        tool["function"]["canonical_name"] for tool in tools
    )
    applications = build_application_catalog_index(())

    lexical_catalog, _ = _create_planner_resources(tools)
    router = ProcessIntentRouter()
    turn_evidence = TurnEvidenceService()
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    try:
        encoder = RequestBudgetEncoder(
            router,
            offline_timeout=BACKGROUND_ENCODER_TIMEOUT_SECONDS,
        )
        turn_evidence.start(encoder, lambda: router.try_ready(0.5))
        deadline = time.monotonic() + PROMOTION_DEADLINE_SECONDS
        while turn_evidence.state == "building" and time.monotonic() < deadline:
            time.sleep(0.1)
        readiness_seconds = round(time.monotonic() - started, 3)
        if turn_evidence.state != "ready" or not router.try_ready(
            max(0.5, deadline - time.monotonic()),
        ):
            raise RuntimeError(
                "las resources semánticas no quedaron listas dentro del plazo"
            )
        semantic_catalog, _ = _create_planner_resources(tools, encoder)

        for source, text in _corpus():
            explicit = resolve_explicit_effects(
                text,
                available_operations,
                applications,
            )
            if explicit is not None:
                rows.append(
                    {
                        "source": source,
                        "text": text,
                        "regime": "deterministic",
                        "operations": list(explicit.operations),
                        "differs": False,
                    }
                )
                continue
            lexical = _composition(
                lexical_catalog,
                turn_evidence,
                encoder,
                text,
                semantic=False,
            )
            semantic = _composition(
                semantic_catalog,
                turn_evidence,
                encoder,
                text,
                semantic=True,
            )
            repeated = _composition(
                semantic_catalog,
                turn_evidence,
                encoder,
                text,
                semantic=True,
            )
            lexical_names = set(lexical["shortlist"])
            semantic_names = set(semantic["shortlist"])
            rows.append(
                {
                    "source": source,
                    "text": text,
                    "regime": "model",
                    # Cualquier diferencia de composición, incluido el orden.
                    "differs": lexical != semantic,
                    # Diferencia material: una operación visible en un régimen
                    # e invisible en el otro sí puede cambiar la decisión.
                    "visible_operations_differ": lexical_names != semantic_names,
                    "only_lexical": sorted(lexical_names - semantic_names),
                    "only_semantic": sorted(semantic_names - lexical_names),
                    "top_candidate_differs": (
                        lexical["shortlist"][:1] != semantic["shortlist"][:1]
                    ),
                    "cache_unstable": semantic != repeated,
                    "lexical": lexical,
                    "semantic": semantic,
                }
            )
    finally:
        turn_evidence.stop(5.0)
        router.close()

    deterministic = [row for row in rows if row["regime"] == "deterministic"]
    model_rows = [row for row in rows if row["regime"] == "model"]
    differing = [row for row in model_rows if row["differs"]]
    material = [row for row in model_rows if row["visible_operations_differ"]]
    top_differing = [row for row in model_rows if row["top_candidate_differs"]]
    unstable = [row for row in model_rows if row.get("cache_unstable")]
    report = {
        "schema": "baxy.promotion-boundary-decisions.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "runtime": public_runtime_identity(runtime),
        "catalog_operations": len(available_operations),
        "semantic_readiness_seconds": readiness_seconds,
        "corpus_rows": len(rows),
        "deterministic_rows": len(deterministic),
        "model_rows": len(model_rows),
        "prompt_composition_differs": len(differing),
        "visible_operations_differ": len(material),
        "top_candidate_differs": len(top_differing),
        "semantic_cache_unstable": len(unstable),
        "material": material,
        "unstable": unstable,
        "deterministic": [
            {
                "source": row["source"],
                "text": row["text"],
                "operations": row["operations"],
            }
            for row in deterministic
        ],
    }
    write_json_atomic(arguments.output, report)
    print(
        f"corpus={len(rows)} deterministas={len(deterministic)} "
        f"modelo={len(model_rows)} composicion_difiere={len(differing)} "
        f"operaciones_visibles_difieren={len(material)} "
        f"primer_candidato_difiere={len(top_differing)} "
        f"cache_inestable={len(unstable)} -> {arguments.output}"
    )
    return 0 if not unstable else 1


if __name__ == "__main__":
    raise SystemExit(main())
