"""Prove a social envelope never changes which effect a request names.

A greeting carries no propositional content, so wrapping a request in one must
not change what the request asks for.  The deterministic recognizer used to
break that invariant in one arbitrary place: it stripped ``hola baxy,`` but not
``hola,``, so ``hola baxy, cuanta bateria queda`` resolved to ``system.status``
while ``hola, cuanta bateria queda`` was handed to the primary policy, which
answered it with a clarification four times out of four.

Exact decision equality against the model cannot gate this change.  That gate
can only be passed by a variant where the model was already right, so it
structurally rejects every case in which widening the recognizer *fixes* an
answer.  This detector applies the gate that R3 and R10 used instead: an oracle
corpus over the already frozen case list, asserting that the wrapped form
resolves exactly as the bare form the recognizer already owns -- including the
cases where the bare form deliberately abstains, which must keep abstaining.

Both arms are evaluated, so the artifact also states how many wrapped requests
the previous behaviour was dropping.  The model is never asked anything, no
Core operation is dispatched and no registered asset changes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
TESTS = REPO / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from baxy_mind import __main__ as sidecar  # noqa: E402
from baxy_mind import effect_intent  # noqa: E402

OUTPUT = REPO / "artifacts" / "fixes" / "social_envelope_equivalence_20260731.json"

# The exact patterns the change widens. Restoring them reproduces the previous
# recognizer inside the same product code, so both arms run one implementation.
_BASELINE_REQUEST_PREFIX = (
    r"(?:(?:por favor|please)\s*[,;:]?\s*|"
    r"(?:puedes|podrias|can you|could you|would you)\s+|"
    r"(?:(?:che|oye|oiga|hey|ey|ok|okay|hola|escucha|listen)\s+)?"
    r"baxy\s*[,;:]?\s*)?"
)
_BASELINE_SOCIAL_CLAUSE = (
    r"^[¿?¡!\s]*(?:gracias|thanks|thank you|por favor|please|"
    r"que tengas (?:un )?buen dia)\b|"
    r"^[¿?¡!\s]*(?:(?:che|oye|oiga|hey|ey|ok|okay|hola|escucha|"
    r"listen)\s+)?baxy[\s?!.,;:]*$"
)

# Every envelope is a complete social act plus a separator: nothing here names
# an operation, an argument or a target.
ENVELOPES_ES: tuple[str, ...] = (
    "Hola, ",
    "hola baxy, ",
    "Baxy, ",
    "Buenos días, ",
    "Buenas tardes, ",
    "Buenas noches, ",
    "Buenas, ",
    "Hola baxy: ",
)
ENVELOPES_EN: tuple[str, ...] = (
    "Hi, ",
    "Hello, ",
    "Hey, ",
    "Good morning, ",
    "Hello Baxy, ",
)
ENVELOPES = ENVELOPES_ES + ENVELOPES_EN

# `hola` and `hello` as literal content rather than as a greeting. The envelope
# must never reach inside these, in either arm.
CONTENT_NOT_GREETING: tuple[str, ...] = (
    "Escribe hola",
    "escribe hola mundo en el bloc de notas",
    "Copia a mi portapapeles hola",
    "type hello",
    "open notepad and type hello there",
    "mandale hola a Lucas por whatsapp",
    "manda un mensaje a Musica en whatsapp que diga hola",
    "run 'echo hello'",
    "no consultes pantalla para responder esto: hola",
)


def _wrap(envelope: str, bare: str) -> str:
    """Apply the envelope, keeping Spanish inverted punctuation attached."""

    stripped = bare.lstrip()
    if stripped.startswith(("¿", "¡")):
        return f"{envelope}{stripped[0]}{stripped[1:]}"
    return f"{envelope}{stripped}"


def _install(arm: str, candidate: dict[str, Any]) -> None:
    if arm == "baseline":
        effect_intent._REQUEST_PREFIX = _BASELINE_REQUEST_PREFIX
        effect_intent._is_social_clause = (
            lambda text: effect_intent._has(text, _BASELINE_SOCIAL_CLAUSE))
        sidecar._explicit_social_turn_decision = candidate["baseline_social"]
    else:
        effect_intent._REQUEST_PREFIX = candidate["prefix"]
        effect_intent._is_social_clause = candidate["clause"]
        sidecar._explicit_social_turn_decision = candidate["social"]


def _resolve(text: str, available: Any) -> dict[str, Any] | None:
    intent = effect_intent.resolve_explicit_effects(text, available, ())
    if intent is None:
        return None
    return {"kind": intent.kind, "operations": list(intent.operations)}


def run() -> dict[str, Any]:
    import test_effect_intent as frozen

    cases = list(frozen.CASES)
    available = frozen.AVAILABLE
    candidate = {
        "prefix": effect_intent._REQUEST_PREFIX,
        "clause": effect_intent._is_social_clause,
        "social": sidecar._explicit_social_turn_decision,
        "baseline_social": sidecar._explicit_social_turn_decision,
    }

    results: dict[str, dict[str, Any]] = {}
    equivalent_pairs: dict[str, set[tuple[str, str]]] = {}
    for arm in ("baseline", "candidate"):
        _install(arm, candidate)
        preserved = 0
        hidden: list[dict[str, Any]] = []
        degraded: list[dict[str, Any]] = []
        manufactured: list[dict[str, Any]] = []
        equivalent_pairs[arm] = set()
        for bare, _expected in cases:
            reference = _resolve(bare, available)
            for envelope in ENVELOPES:
                wrapped = _wrap(envelope, bare)
                observed = _resolve(wrapped, available)
                entry = {
                    "bare": bare, "wrapped": wrapped,
                    "expected": reference, "observed": observed,
                }
                if observed == reference:
                    preserved += 1
                    equivalent_pairs[arm].add((envelope, bare))
                elif reference is None:
                    # The bare request abstains and the wrapped one does not:
                    # authority invented by the envelope. Never acceptable.
                    manufactured.append(entry)
                elif observed is None:
                    # The envelope merely hides a request the recognizer owns.
                    # Conservative: the turn goes to the model instead.
                    hidden.append(entry)
                else:
                    # Both resolve, but not to the same thing. This is the worst
                    # shape short of manufacturing, because it acts on a target
                    # the person did not name.
                    degraded.append(entry)
        content = [
            {"text": text, "resolution": _resolve(text, available)}
            for text in CONTENT_NOT_GREETING
        ]
        results[arm] = {
            "comparisons": len(cases) * len(ENVELOPES),
            "equivalent": preserved,
            "request_hidden_by_the_envelope": hidden,
            "operation_degraded_by_the_envelope": degraded,
            "authority_manufactured_by_the_envelope": manufactured,
            "content_not_greeting": content,
        }

    _install("candidate", candidate)

    # The social decision outranks an explicit intent in `_prepare_turn_result`,
    # so no member of the social vocabulary may also name an effect.
    social_vocabulary = (
        "hola", "hola baxy", "buenas", "buenas tardes", "buenas noches",
        "buenos dias", "hola, todo bien?", "que tal", "como estas",
        "chau baxy", "adios", "hasta luego", "nos vemos", "gracias",
        "muchas gracias", "perfecto gracias", "hi", "hello", "hello there",
        "hey", "good morning", "how are you", "bye", "goodbye baxy",
        "see you later", "good night", "perfect, thanks",
    )
    overlaps = [
        text for text in social_vocabulary
        if _resolve(text, available) is not None
        or effect_intent.resolve_explicit_clarification(text, available) is not None
    ]

    # The promotion gate: no pair the previous recognizer already kept
    # equivalent may stop being equivalent. Perfect envelope invariance is a
    # different, larger claim and is reported as residual instead of asserted.
    regressions = sorted(
        equivalent_pairs["baseline"] - equivalent_pairs["candidate"])
    residual = results["candidate"]["request_hidden_by_the_envelope"]
    new_degradations = [
        entry for entry in results["candidate"]["operation_degraded_by_the_envelope"]
        if entry not in results["baseline"]["operation_degraded_by_the_envelope"]
    ]

    baseline, candidate_result = results["baseline"], results["candidate"]
    report = {
        "schema": "baxy.social-envelope-equivalence.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "model_invocations": 0,
        "question": (
            "does wrapping a request in a social envelope change which effect "
            "the deterministic recognizer says it names?"),
        "gate": (
            "for every frozen case and every envelope, the wrapped form must "
            "resolve exactly as the bare form -- same kind, same operations -- "
            "and a bare form that abstains must keep abstaining. Authority "
            "manufactured by an envelope is the one failure that is never "
            "acceptable, and it is reported separately from a request the "
            "envelope merely hides."),
        "why_not_exact_equality_against_the_model": (
            "an exact-equality gate against a P baseline can only be passed by "
            "a variant where P was already right, so it structurally rejects "
            "every case in which widening the recognizer fixes an answer. "
            "social_envelope_20260731.json records two such cases: `buenos "
            "dias, cuanta bateria queda`, which the baseline answered with a "
            "clarification 4 times out of 4 while resolving the bare form to "
            "system.status, and `hola, pon el volumen al 30 por ciento`, which "
            "the baseline turned into a plan over audio.volume.adjust while "
            "resolving the bare form to audio.volume. This corpus is the gate "
            "R3 and R10 used: an oracle, not the model."),
        "corpus": {
            "frozen_cases": len(cases),
            "source": "tests/test_effect_intent.py CASES (already frozen)",
            "envelopes": list(ENVELOPES),
            "comparisons_per_arm": len(cases) * len(ENVELOPES),
        },
        "baseline": {
            "equivalent": baseline["equivalent"],
            "request_hidden_by_the_envelope": len(
                baseline["request_hidden_by_the_envelope"]),
            "operation_degraded_by_the_envelope": len(
                baseline["operation_degraded_by_the_envelope"]),
            "authority_manufactured_by_the_envelope": len(
                baseline["authority_manufactured_by_the_envelope"]),
        },
        "candidate": {
            "equivalent": candidate_result["equivalent"],
            "request_hidden_by_the_envelope": len(
                candidate_result["request_hidden_by_the_envelope"]),
            "operation_degraded_by_the_envelope": len(
                candidate_result["operation_degraded_by_the_envelope"]),
            "authority_manufactured_by_the_envelope": len(
                candidate_result["authority_manufactured_by_the_envelope"]),
        },
        "regressions_against_the_previous_recognizer": [
            {"envelope": envelope, "bare": bare} for envelope, bare in regressions
        ],
        "residual_not_yet_envelope_invariant": {
            "count": len(residual),
            "note": (
                "Every recognized bare request must remain recognized with "
                "the same kind and exact operation sequence under every "
                "social envelope. Any residual abstention fails this gate."),
            "cases": residual,
        },
        "degradation_that_predates_this_change": {
            "count": len(candidate_result["operation_degraded_by_the_envelope"]),
            "new_in_this_change": len(new_degradations),
            "note": (
                "This compatibility field is retained for historical artifact "
                "readers. The current gate accepts no degraded operation, "
                "regardless of which revision first exposed it."),
            "cases": candidate_result["operation_degraded_by_the_envelope"],
        },
        "passed": (
            not regressions
            and not residual
            and not candidate_result["authority_manufactured_by_the_envelope"]
            and not candidate_result["operation_degraded_by_the_envelope"]
            and not overlaps
        ),
        "social_vocabulary_overlapping_an_effect": overlaps,
        "detail": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_known_args()
    report = run()
    print(json.dumps({
        "corpus": report["corpus"],
        "baseline": report["baseline"],
        "candidate": report["candidate"],
        "regressions_against_the_previous_recognizer": (
            report["regressions_against_the_previous_recognizer"]),
        "residual_not_yet_envelope_invariant": (
            report["residual_not_yet_envelope_invariant"]["count"]),
        "degradation_that_predates_this_change": (
            report["degradation_that_predates_this_change"]),
        "social_vocabulary_overlapping_an_effect": (
            report["social_vocabulary_overlapping_an_effect"]),
        "passed": report["passed"],
    }, ensure_ascii=False, indent=1))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
