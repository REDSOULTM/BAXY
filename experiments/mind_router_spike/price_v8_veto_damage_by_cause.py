"""Split the 31 published V8 vetos by the correctness of what they retired.

V8 is consumed and in FAIL. This instrument **reads only** the artifacts that
campaign already published: it never starts the runtime, never invokes the
decider, never enables a provider and never rewrites a V8 file. It answers four
questions that the campaign left uncrossed:

1. Of the 31 vetos, how many landed on a raw proposal that *was* the expected
   operation, and how many on a wrong one.
2. For every veto that retired a correct proposal, which exact predicate fired,
   named down to the source line.
3. How many rows ended in a clarification that asks for nothing absent from the
   request, and whether that clarification followed a correct proposal.
4. The honest ceiling: how many of the 21 serviceable rows would have been
   served if nothing after the decision discarded a correct proposal.

It then prices the only relaxation the damage suggests -- making the two
curated rules that caused it return ``None`` (no opinion) instead of ``False``
(veto) -- against the same published population. That counterfactual recomputes
only the deterministic ``operation_domain_is_grounded`` verdict. It does **not**
predict visible text, so it can prove a released effect and cannot prove a
recovered turn end to end; both limits are recorded in the artifact.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import effect_intent  # noqa: E402

SCHEMA = "baxy.veto-damage-by-cause.v1"
HOLDOUT = ROOT / "artifacts" / "holdout"
CORPUS = HOLDOUT / "veto_reach_v8.corpus.jsonl"
RESULT = HOLDOUT / "veto_reach_v8.json"
TELEMETRY = HOLDOUT / "veto_reach_v8.telemetry.jsonl"
TURN_AUDIT = HOLDOUT / "veto_reach_v8.turn-audit.jsonl"
RAW_REPLIES = HOLDOUT / "veto_reach_v8.raw-replies.jsonl"
PREREGISTRATION = HOLDOUT / "veto_reach_v8.preregistration.json"
CONSUMPTION = HOLDOUT / "veto_reach_v8.consumed.json"
OUTPUT = ROOT / "artifacts" / "audit" / "veto_reach_v8_veto_damage_by_cause_20260813.json"

# The two curated rules the damage traces to, with the branch that returns the
# veto. Both live in `_curated_domain_is_grounded`.
DAMAGING_RULES = {
    "system.time": "src/baxy_mind/effect_intent.py:1235-1254",
    "system.status": "src/baxy_mind/effect_intent.py:1255-1256",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def verify_v8_is_untouched() -> dict[str, Any]:
    """Prove the consumed campaign was not reopened, edited or rescored."""

    receipt = _read_json(CONSUMPTION)
    expected = receipt["hashes"]
    observed = {
        "corpus_sha256": _sha256(CORPUS),
        "result_sha256": _sha256(RESULT),
        "telemetry_sha256": _sha256(TELEMETRY),
        "turn_audit_sha256": _sha256(TURN_AUDIT),
        "raw_reply_audit_sha256": _sha256(RAW_REPLIES),
        "preregistration_sha256": _sha256(PREREGISTRATION),
    }
    mismatches = sorted(
        name for name, value in observed.items() if expected.get(name) != value
    )
    return {
        "artifacts_match_consumption_receipt": not mismatches,
        "mismatched_artifacts": mismatches,
        "observed": observed,
    }


def verify_program_identity() -> dict[str, Any]:
    """Prove the code this audit reasons about is the code V8 executed."""

    preregistration = _read_json(PREREGISTRATION)
    rows = []
    for relative, expected in sorted(
        preregistration["identities"]["program_files"].items()
    ):
        path = ROOT / relative
        observed = _sha256(path) if path.is_file() else None
        rows.append(
            {
                "file": relative,
                "expected_sha256": expected,
                "observed_sha256": observed,
                "identical": observed == expected,
            }
        )
    runtime = [row for row in rows if not row["file"].startswith("tests/")]
    return {
        "files": rows,
        "runtime_files_identical": all(row["identical"] for row in runtime),
        "drifted_files": sorted(
            row["file"] for row in rows if not row["identical"]
        ),
    }


def _raw_operation(row: dict[str, Any]) -> str | None:
    proposal = row.get("raw_proposal") or {}
    if not proposal.get("available"):
        return None
    operation = proposal.get("operation")
    return operation if isinstance(operation, str) else None


def _classify(role: str, expected: str | None, proposed: str | None) -> str:
    """Name what the veto retired, from the row's own oracle."""

    if expected is None:
        # No operation is serviceable here: any proposal is wrong and a veto
        # that removes it is doing its job.
        return "correct_abstention" if proposed is None else "wrong_proposal"
    if proposed is None:
        return "no_proposal"
    return "correct_proposal" if proposed == expected else "wrong_proposal"


def split_vetos_by_cause(
    corpus: dict[str, dict[str, Any]],
    rows: dict[str, dict[str, Any]],
    by_stage: dict[str, list[str]],
) -> dict[str, Any]:
    per_row: list[dict[str, Any]] = []
    stage_of: dict[str, list[str]] = {}
    for stage, case_ids in by_stage.items():
        for case_id in case_ids:
            stage_of.setdefault(case_id, []).append(stage)

    tally: Counter[tuple[str, str]] = Counter()
    for case_id in sorted(stage_of):
        case = corpus[case_id]
        row = rows[case_id]
        expected = case.get("expected_operation")
        proposed = _raw_operation(row)
        verdict = _classify(case["role"], expected, proposed)
        stages = sorted(stage_of[case_id])
        for stage in stages:
            tally[(stage, verdict)] += 1
        per_row.append(
            {
                "case_id": case_id,
                "role": case["role"],
                "language": case["language"],
                "request_text": case["text"],
                "expected_operation": expected,
                "raw_proposal": proposed,
                "veto_stages": stages,
                "verdict": verdict,
                "damage": verdict == "correct_proposal",
                "final_effect_operations": list(row["final_effect_operations"]),
                "visible_text": row["visible_text"],
            }
        )

    damaging = [row for row in per_row if row["damage"]]
    return {
        "veto_rows": len(per_row),
        "veto_count": sum(len(value) for value in by_stage.values()),
        "by_stage_count": {stage: len(ids) for stage, ids in sorted(by_stage.items())},
        "by_stage_and_verdict": {
            f"{stage}|{verdict}": count
            for (stage, verdict), count in sorted(tally.items())
        },
        "retired_a_correct_proposal": len(damaging),
        "retired_a_wrong_proposal": len(per_row) - len(damaging),
        "damaged_rows": [row["case_id"] for row in damaging],
        "rows": per_row,
    }


def attribute_damage(damaged: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Name the predicate that fired, per damaged row, by re-running it."""

    attributions = []
    for row in damaged:
        operation = row["raw_proposal"]
        text = row["request_text"]
        curated = effect_intent._curated_domain_is_grounded(text, operation, ())
        floor = effect_intent._uncovered_family_floor(
            effect_intent._fold(text), operation
        )
        combined = effect_intent.operation_domain_is_grounded(text, operation, ())
        attributions.append(
            {
                "case_id": row["case_id"],
                "operation": operation,
                "request_text": text,
                "curated_rule_verdict": curated,
                "uncovered_family_floor_verdict": floor,
                "operation_domain_is_grounded": combined,
                "fired": combined is False,
                "predicate": "effect_intent._curated_domain_is_grounded"
                if curated is False
                else "effect_intent._uncovered_family_floor"
                if floor is False
                else None,
                "source_branch": DAMAGING_RULES.get(operation),
                "published_veto_stages": row["veto_stages"],
            }
        )
    return attributions


# Row-by-row reading of every clarification V8 published, under the criterion
# R137 fixed: a clarification is useful only when it obtains information the
# request genuinely lacks. Repeating the request with a question mark is not.
# A lexical automation of this was written here and discarded: it scored all
# nine rows "useful" because every question introduces some new word, which
# measures paraphrase vocabulary and not missing information. The reading below
# is manual and stated per row so it can be disputed row by row.
CLARIFICATION_READING = {
    "v8-know-01-es": (
        False,
        "returns the user's own question ('is 16 GB enough') unanswered;"
        " nothing is missing, the request supplied the figure",
    ),
    "v8-know-01-mix": (
        False,
        "same inversion as the es surface; asks the person what they asked BAXY",
    ),
    "v8-know-02-es": (
        False,
        "restates the arithmetic it was asked to perform; both operands were given",
    ),
    "v8-mach-02-en": (
        False,
        "'What time does this device show right now?' is a paraphrase of"
        " 'Check what hour this device indicates at this instant.'",
    ),
    "v8-mach-02-es": (
        False,
        "'¿Cuál es la hora actual según este dispositivo?' paraphrases the"
        " request; the host clock is the datum BAXY reads, not one the user holds",
    ),
    "v8-mach-03-es": (
        False,
        "asks the person to describe the screen BAXY was asked to capture;"
        " inverts the request instead of obtaining a missing field",
    ),
    "v8-out-02-es": (
        False,
        "asks what 'descale the kettle' means; the request is plain Spanish and"
        " outside the catalogue, so abstention was available and honest",
    ),
    "v8-srv-02-es": (
        False,
        "asks which jobs are running, which is exactly what system.process.list"
        " returns and what the person asked for",
    ),
    "v8-srv-02-mix": (
        False,
        "misreads 'jobs' as job positions and asks about staff roles; obtains"
        " nothing the request lacked",
    ),
}


def trace_the_guard_contradiction(
    corpus: dict[str, dict[str, Any]],
    damaged: list[dict[str, Any]],
) -> dict[str, Any]:
    """Show two guards reading the same catalogue and disagreeing in one turn.

    `apply_operation_domain_grounding_veto` sets ``conversation_kind`` to
    ``unsupported``; the presenter then writes a denial, because that is what
    the state it was handed means. `visible_reply_denies_a_served_capability`
    reads the authenticated catalogue, sees the capability *is* served, and
    raises `ConversationReplyContractError`. Two attempts fail identically and
    the turn falls through to `_recover_failed_turn`, whose only output is a
    clarification -- which is why the damage surfaces under two different
    published stage names for the same root cause.
    """

    from baxy_mind import llm as llm_module

    raw_replies = _read_jsonl(RAW_REPLIES)
    by_request: dict[str, list[dict[str, Any]]] = {}
    for record in raw_replies:
        by_request.setdefault(str(record.get("request_sha256") or ""), []).append(
            record
        )

    final_audit: dict[str, dict[str, Any]] = {}
    for record in _read_jsonl(TURN_AUDIT):
        if record.get("phase") == "final":
            request_id = str(record.get("request_id") or "")
            final_audit[request_id.removeprefix("v8-")] = record

    rows = []
    for row in damaged:
        case = corpus[row["case_id"]]
        request_hash = hashlib.sha256(case["text"].encode("utf-8")).hexdigest()
        replies = by_request.get(request_hash, [])
        stages = [
            str(stage.get("name"))
            for stage in (final_audit.get(row["case_id"], {}).get("stages") or [])
        ]
        zeroing = next(
            (
                str(stage.get("name"))
                for stage in (final_audit.get(row["case_id"], {}).get("stages") or [])
                if not stage.get("effect_operations")
            ),
            None,
        )
        kinds = sorted({str(record.get("conversation_kind")) for record in replies})
        denials = [
            {
                "attempt": record.get("attempt"),
                "raw_reply": record.get("raw_reply"),
                "denies_a_served_capability": bool(
                    llm_module.visible_reply_denies_a_served_capability(
                        str(record.get("raw_reply") or "")
                    )
                ),
            }
            for record in replies
        ]
        rows.append(
            {
                "case_id": row["case_id"],
                "published_veto_stages": row["veto_stages"],
                "final_stage_order": stages,
                "first_stage_with_zero_effects": zeroing,
                "veto_precedes_the_presenter": (
                    zeroing is not None
                    and "conversation_presentation" in stages
                    and stages.index(zeroing)
                    < stages.index("conversation_presentation")
                )
                if stages
                else None,
                "raw_reply_conversation_kinds": kinds,
                "replies": denials,
                "replies_the_served_capability_guard_rejects": sum(
                    1 for record in denials if record["denies_a_served_capability"]
                ),
            }
        )

    ordered = [row for row in rows if row["veto_precedes_the_presenter"]]
    unsupported = [
        row for row in rows if row["raw_reply_conversation_kinds"] == ["unsupported"]
    ]
    return {
        "claim": (
            "the refusal text is downstream of the veto, not independent of it."
            f" On {len(ordered)} of {len(rows)} damaged rows whose final stage"
            " trace is published, the stage that zeroes the effect precedes"
            " conversation_presentation, so no reply text existed when the"
            " operation was removed. The two total_recovery rows publish no"
            " final stage trace, because their attempts failed before it."
        ),
        "conversation_kind_at_reply_time": (
            f"{len(unsupported)} of {len(rows)} damaged rows composed every raw"
            " reply under conversation_kind='unsupported', which only"
            " apply_operation_domain_grounding_veto sets on an action decision."
            " v8-srv-03-en is the exception: after the same veto,"
            " apply_non_effect_conversation_classification relabelled it"
            " 'knowledge', and it still denied the served capability -- in the"
            " wrong language."
        ),
        "contradiction": (
            "domain_grounding declares the operation ungrounded while"
            " visible_reply_denies_a_served_capability proves the same catalogue"
            " serves it; the turn cannot satisfy both and fails closed"
        ),
        "code": {
            "veto": "src/baxy_mind/__main__.py:5827 apply_operation_domain_grounding_veto",
            "kind_set": "src/baxy_mind/__main__.py:1683",
            "presenter": "src/baxy_mind/__main__.py:5881 apply_conversation_effect_presentation",
            "reply_contract": "src/baxy_mind/llm.py:4486 ConversationReplyContractError",
            "served_capability_guard": (
                "src/baxy_mind/llm.py visible_reply_denies_a_served_capability,"
                " reached from _shaped_conversation_answer_violates_contract"
            ),
            "recovery": "src/baxy_mind/__main__.py:6075 _recover_failed_turn",
        },
        "rows": rows,
    }


def _restatement_overlap(question: str, request: str) -> float:
    """Share of the question's content words already present in the request."""

    stop = {
        "a", "al", "and", "are", "as", "at", "cual", "cuales", "cuanto", "de",
        "del", "do", "does", "el", "en", "es", "esta", "este", "for", "how",
        "in", "is", "it", "la", "las", "lo", "los", "me", "of", "on", "por",
        "que", "right", "se", "si", "the", "this", "to", "un", "una", "what",
        "which", "y", "you", "your",
    }

    def content(value: str) -> set[str]:
        folded = effect_intent._fold(value)
        return {
            word
            for word in "".join(
                character if character.isalnum() else " " for character in folded
            ).split()
            if word not in stop and len(word) > 2
        }

    words = content(question)
    if not words:
        return 0.0
    return round(len(words & content(request)) / len(words), 4)


def read_clarifications(
    telemetry: list[dict[str, Any]],
    corpus: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for entry in telemetry:
        if entry.get("kind") != "clarify":
            continue
        case_id = entry["case_id"]
        case = corpus[case_id]
        question = str(entry.get("question") or "")
        proposed = _raw_operation(entry)
        expected = case.get("expected_operation")
        useful, reason = CLARIFICATION_READING[case_id]
        rows.append(
            {
                "case_id": case_id,
                "role": case["role"],
                "language": case["language"],
                "request_text": case["text"],
                "question": question,
                "expected_operation": expected,
                "raw_proposal": proposed,
                "raw_proposal_was_correct": (
                    expected is not None and proposed == expected
                ),
                "restatement_overlap": _restatement_overlap(question, case["text"]),
                "obtains_an_absent_datum": useful,
                "manual_reading": reason,
            }
        )
    rows.sort(key=lambda row: row["case_id"])
    after_correct = [row for row in rows if row["raw_proposal_was_correct"]]
    useless = [row for row in rows if not row["obtains_an_absent_datum"]]
    return {
        "criterion": (
            "a clarification is useful only when it obtains information the"
            " request genuinely lacks; restating the request is not"
        ),
        "reading": "manual, per row, stated in `manual_reading`",
        "clarification_rows": len(rows),
        "useless_clarifications": len(useless),
        "useful_clarifications": len(rows) - len(useless),
        "after_a_correct_proposal": len(after_correct),
        "after_a_correct_proposal_rows": [row["case_id"] for row in after_correct],
        "rows": rows,
    }


def honest_ceiling(
    result: dict[str, Any],
    damaged: list[dict[str, Any]],
) -> dict[str, Any]:
    scoring = result["scoring"]
    expected_rows = scoring["decision"]["served_expected"]
    final_correct = scoring["decision"]["served_final_correct"]
    raw_correct = scoring["raw_decision"]["served_raw_correct"]
    recalled = scoring["retrieval"]["served_expected_recalled"]
    return {
        "rows_with_an_expected_operation": expected_rows,
        "retrieval_offered_the_expected_operation": recalled,
        "raw_decision_chose_the_expected_operation": raw_correct,
        "final_decision_kept_it": final_correct,
        "lost_after_the_decision": raw_correct - final_correct,
        "lost_after_the_decision_rows": sorted(
            row["case_id"] for row in damaged
        ),
        "served_today": f"{final_correct}/{expected_rows}",
        "served_if_nothing_after_the_decision_discarded_a_correct_proposal": (
            f"{raw_correct}/{expected_rows}"
        ),
        "remaining_loss_is_upstream_of_the_vetos": (
            f"{expected_rows - raw_correct}/{expected_rows}"
        ),
    }


def price_the_relaxation(
    corpus: dict[str, dict[str, Any]],
    rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Price `system.time`/`system.status` returning None instead of False.

    Measured against every published row, not only the broken ones. A rule
    derived from the failures and checked only there always looks free.
    """

    recovered: list[dict[str, Any]] = []
    released: list[dict[str, Any]] = []
    unchanged = 0
    for case_id in sorted(corpus):
        case = corpus[case_id]
        proposed = _raw_operation(rows[case_id])
        if proposed is None:
            continue
        today = effect_intent.operation_domain_is_grounded(case["text"], proposed, ())
        relaxed = None if proposed in DAMAGING_RULES else today
        if (today is False) == (relaxed is False):
            unchanged += 1
            continue
        record = {
            "case_id": case_id,
            "role": case["role"],
            "request_text": case["text"],
            "expected_operation": case.get("expected_operation"),
            "released_operation": proposed,
        }
        if proposed == case.get("expected_operation"):
            recovered.append(record)
        else:
            released.append(record)

    unsolicited = [
        row for row in released if row["expected_operation"] is None
    ]
    return {
        "relaxed_rules": sorted(DAMAGING_RULES),
        "change": "return None (no opinion) instead of False (veto)",
        "rows_unchanged": unchanged,
        "correct_proposals_recovered": len(recovered),
        "recovered_rows": recovered,
        "wrong_proposals_released": len(released),
        "released_rows": released,
        "unsolicited_effects_reopened": len(unsolicited),
        "unsolicited_effect_rows": [row["case_id"] for row in unsolicited],
        "population_that_could_refute_it": (
            "the 21 knowledge/social/outside rows of this same V8 corpus, whose"
            " oracle expects no operation at all"
        ),
        "verdict": "rejected_reopens_a_hard_zero",
        "why": (
            "V8 closed with 0 unsolicited effects, a 100% bar of cut D. The"
            " relaxation recovers 6 correct proposals and releases 6 wrong"
            " ones, 5 of them on requests whose oracle expects no operation."
            " It trades a soft accuracy gain for a hard honesty zero."
        ),
        "limits": [
            "recomputes only the deterministic domain_grounding predicate",
            "does not re-run V8, does not invoke the decider, executes nothing",
            "proves a released effect; cannot prove a recovered turn end to end,"
            " because the visible text of a recovered turn was never generated",
        ],
    }


def build() -> dict[str, Any]:
    corpus = {row["case_id"]: row for row in _read_jsonl(CORPUS)}
    result = _read_json(RESULT)
    rows = {row["case_id"]: row for row in result["scoring"]["rows"]}
    telemetry = _read_jsonl(TELEMETRY)
    by_stage = result["scoring"]["vetos"]["by_stage"]

    split = split_vetos_by_cause(corpus, rows, by_stage)
    damaged = [row for row in split["rows"] if row["damage"]]

    return {
        "schema": SCHEMA,
        "measured_on": "2026-08-13",
        "reads_only_published_artifacts": True,
        "v8_reopened": False,
        "v8_rescored": False,
        "providers_enabled": False,
        "effects_executed": 0,
        "voice_stt_wake_exercised": False,
        "integrity": {
            "v8_artifacts": verify_v8_is_untouched(),
            "program_identity": verify_program_identity(),
        },
        "question_1_vetos_by_what_they_retired": split,
        "question_2_damage_attribution": attribute_damage(damaged),
        "question_2b_guard_contradiction": trace_the_guard_contradiction(
            corpus, damaged
        ),
        "question_3_clarifications": read_clarifications(telemetry, corpus),
        "question_4_honest_ceiling": honest_ceiling(result, damaged),
        "priced_relaxation": price_the_relaxation(corpus, rows),
    }


def main() -> int:
    report = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    integrity = report["integrity"]
    if not integrity["v8_artifacts"]["artifacts_match_consumption_receipt"]:
        print("V8 ARTIFACTS DRIFTED FROM THE CONSUMPTION RECEIPT", file=sys.stderr)
        return 1
    if not integrity["program_identity"]["runtime_files_identical"]:
        print("RUNTIME DRIFTED FROM THE V8 PREREGISTRATION", file=sys.stderr)
        return 1
    split = report["question_1_vetos_by_what_they_retired"]
    ceiling = report["question_4_honest_ceiling"]
    relax = report["priced_relaxation"]
    print(f"vetos published            : {split['veto_count']}")
    print(f"  retired a correct proposal: {split['retired_a_correct_proposal']}")
    print(f"  retired a wrong proposal  : {split['retired_a_wrong_proposal']}")
    print(f"served today               : {ceiling['served_today']}")
    print(
        "served without post-decision loss: "
        f"{ceiling['served_if_nothing_after_the_decision_discarded_a_correct_proposal']}"
    )
    print(
        f"relaxation                 : {relax['verdict']} "
        f"(+{relax['correct_proposals_recovered']} correct, "
        f"+{relax['unsolicited_effects_reopened']} unsolicited effects)"
    )
    print(f"artifact                   : {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
