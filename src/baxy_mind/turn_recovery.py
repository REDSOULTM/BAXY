"""Recovery of a failed turn: the bounded retry without effects, and the one question (or the person's own words)
when two attempts failed.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Callable

from . import turn_audit as turn_audit_module
from . import effect_intent
from .semantic import dialogue as dialogue_slot
from .semantic import listing as semantic_listing
from .effect_intent import conversation_only_content_request
from .failure_wording import talk_reply_tells_a_failure
from .semantic.request import (
    fold as read_fold,
    INTENT_CAPABILITY,
    INTENT_CONTINUE_CONSTRAINT,
    INTENT_IDENTITY,
    INTENT_REFUSE,
    read_request,
)
from .turn_audit import _turn_failure_kind, CONVERSATION_WORDING_FAILURE, LIMIT_WORDING_FAILURE
from .turn_history import _explicit_response_language, _prior_user_texts


def _retry_side_effect_free_turn(
    operation: Callable[[], dict[str, Any]],
    *,
    before_attempt: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Retry one transient turn failure without ever executing an effect."""

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            if before_attempt is not None:
                before_attempt(attempt)
            result = dict(operation())
            result["turn_attempts"] = attempt + 1
            return result
        except Exception as error:  # noqa: BLE001 - bounded local recovery
            last_error = error
            # Tandas 5e/6: a limit whose wording failed its contract fails again on the second attempt —
            # the same decision, the same seeded drafts (identical in every measured turn) — after paying
            # the whole cascade once more (3-4 s). The recovery says the limit instead.
            if _turn_failure_kind(error) == LIMIT_WORDING_FAILURE:
                break
    assert last_error is not None
    raise last_error


_RECOVERY_PROMPT_VOCABULARY = (
    "mensaje actual",
    "current message",
    "pedido actual",
    "current request",
    "la frase que",
    "the sentence you",
    "situacion del turno",
)


# M54 (v3b-final F-p10-t2 «me gustaría que me mostraras el ejemplo de la calculadora científica» → «¿Podrías
# explicarme paso a paso cómo instalar y ejecutar ese código en tu computadora?»): a clarification asks the one thing
# missing; asking the person to explain, teach or show how to do something is their request handed back. Folded.
_RECOVERY_MIRRORED_REQUEST = re.compile(
    r"\b(?:explica|explicame|explicarme|explicas|ensename|ensenarme|ensenas|muestrame|mostrarme|me\s+muestras|"
    r"explain|teach|show)\b(?:\s+\w+){0,5}?\s+(?:como|how)\b|\bpaso\s+a\s+paso\b|\bstep\s+by\s+step\b"
)


def _recovery_question_repeats_a_previous_turn(
    question: str,
    history: object,
) -> bool:
    """La pregunta devuelve una petición que la persona ya hizo antes."""

    if not isinstance(history, list) or len(history) < 2:
        return False
    asked = set(re.findall(r"[a-z]{4,}", read_fold(question)))
    if len(asked) < 2:
        return False
    for item in history[:-1]:
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        previous = set(
            re.findall(r"[a-z]{4,}", read_fold(str(item.get("content") or "")))
        )
        if len(previous) < 2:
            continue
        shared = asked & previous
        if len(shared) >= 2 and len(shared) / len(asked) >= 0.6:
            return True
    return False


def _recovery_question_is_valid(
    value: object,
    objective: str = "",
    history: object = None,
) -> bool:
    """Accept exactly one compact question, never an action-bearing object.

    Además no nombra el vocabulario del encargo ni devuelve una petición
    anterior, que es lo que hacía cuando un turno de conocimiento fallaba.
    """

    if not isinstance(value, str):
        return False
    if not (
        bool(value)
        and len(value) <= 512
        and value == value.strip()
        and "\n" not in value
        and "\r" not in value
        and not any(
            unicodedata.category(character) in {"Cc", "Cs"} for character in value
        )
        and value.endswith("?")
        and value.count("?") == 1
    ):
        return False
    folded = read_fold(value)
    if any(term in folded for term in _RECOVERY_PROMPT_VOCABULARY):
        return False
    if _RECOVERY_MIRRORED_REQUEST.search(folded) is not None:
        return False
    # M85 (DEV-D v3o D-p04-t1 «Dónde?» → «¿Dónde?»): the person's own question said back asks nothing.
    if objective and dialogue_slot.says_the_message_back(value, objective):
        return False
    # M93 (DEV-D v3u D-s053 «¿Miguel sigue viviendo en Arkansas?» → «¿Te refieres a Miguel o a alguien más?»).
    if objective and dialogue_slot.offers_back_the_named_one(value, objective):
        return False
    return not _recovery_question_repeats_a_previous_turn(value, history)


def _recover_failed_turn(
    message: dict[str, Any],
    llm: Any | None,
    *,
    attempts: int = 2,
    failure_kinds: tuple[str, ...] = (),
    conversation_kinds: tuple[str | None, ...] = (),
) -> dict[str, Any]:
    """Return a total, fail-closed clarification after two turn failures.

    The semantic recovery receives dialogue only. If local generation is
    unavailable or violates its schema, the protocol keeps the transport alive
    with empty user-facing fields and zero action authority. The shell may make
    one separately bounded ``message.compose`` attempt, but deterministic
    protocol prose must never be presented as model-authored text.

    ``conversation_kinds`` (M104) are the kinds the failed attempts decided: talk whose wording failed is recovered as
    the talk it was understood to be (``conversationKind`` «knowledge», «social», «followup»), never as a conversation
    of no kind.

    D59 §7 (owner, 2026-10-02): when the model ran and still wrote no valid question for a turn it did not understand,
    the question is the one built with the person's own words (``_words_floor_result``).
    """

    objective = str(message.get("text", ""))[:2_048]
    history = message.get("history") or []
    failure_code = (
        "turn_contract_failure"
        if failure_kinds and set(failure_kinds) == {"contract"}
        else "turn_unavailable"
        if not failure_kinds
        else "turn_runtime_failure"
    )

    def audited(result: dict[str, Any]) -> dict[str, Any]:
        turn_audit_module._append_turn_audit(
            {
                "schema": "baxy.mind-turn-audit.v1",
                "request_id": message.get("id"),
                "phase": "recovery",
                "candidate_operations": [],
                "raw_decision": None,
                "stages": [
                    {
                        "name": "total_recovery",
                        "mode": result.get("kind"),
                        # M54 (v3b-devD D-s005, D-s037): a limit recovered after its wording failed is published as
                        # conversationKind «unsupported»; the audit said only «conversation», so the run read it as
                        # talk. The audit carries what the result carries.
                        **(
                            {"conversation_kind": result["conversationKind"]}
                            if result.get("conversationKind")
                            else {}
                        ),
                        "operation": result.get("operation"),
                        "effect_operations": list(result.get("effectOperations") or []),
                        "effect_verification": "not_applicable",
                    }
                ],
                "final": {
                    "kind": result.get("kind"),
                    "intent_operations": list(result.get("intentOperations") or []),
                    "effect_operations": list(result.get("effectOperations") or []),
                },
                "recovery": {
                    "turn_attempts": result.get("turn_attempts"),
                    "kind": result.get("turn_recovery"),
                    "failure_code": result.get("failure_code"),
                    "failure_kinds": list(failure_kinds),
                },
            }
        )
        return result

    # Un turno fallido no convierte una pregunta por las capacidades o los
    # límites en algo que aclarar: eso se contesta con el catálogo. Devolverla
    # como pregunta era el último sitio por donde salía —«¿Qué específicamente
    # no puedes hacer en este PC?», «¿Qué acción específica te niega la política
    # de seguridad de BAXY?»— (limites-16/003..006).
    # cien-37 030 «send flowers to Deimos»: a place no operation reaches
    # has nothing to clarify either; the question asked for the detail of
    # something that cannot be done at all.
    # Uso real 2026-09-23 «prepárame una taza de café»: the turn had already
    # decided this is something BAXY does not do, and only the wording of that
    # limit failed twice. The recovery keeps the verdict — it says the limit —
    # instead of asking an invented question about coffee.
    is_limit = (
        bool(failure_kinds) and set(failure_kinds) == {LIMIT_WORDING_FAILURE}
    ) or effect_intent.out_of_world_request(objective)
    # tanda-02: an identity answer that failed its wording twice is not turned
    # into a question about the question («¿Te refieres a un lugar geográfico?»).
    # Uso real v3 tanda 1 «dame 3 ideas de nombre para mi gata negra» (two runtime failures) → «¿Qué quieres que haga
    # con…?»: content asked to be written here needs no tool and nothing to clarify; the recovery writes it.
    content_asked = conversation_only_content_request(objective)
    nothing_to_clarify = content_asked or bool(
        read_request(objective).intents
        & {INTENT_IDENTITY, INTENT_CAPABILITY, INTENT_REFUSE, INTENT_CONTINUE_CONSTRAINT}
    ) or is_limit or (
        # M72: the turn was understood as conversation and only its wording failed; the recovery answers briefly
        # instead of asking «¿qué quieres que haga BAXY?» about a message nobody misread.
        bool(failure_kinds) and set(failure_kinds) == {CONVERSATION_WORDING_FAILURE}
    )
    if llm is not None:
        try:
            if nothing_to_clarify:
                raise ValueError("capability_question_is_not_clarified")
            question = llm.clarify_after_turn_failure(
                objective,
                history=history,
                timeout=2.5,
            )
            # M99 (DEV-D v3x D-s053 «¿Miguel sigue viviendo en Arkansas?» → «¿Te refieres a Miguel o a alguien más?»):
            # the recovery question is judged against the message too, as the decider's is.
            if not _recovery_question_is_valid(question, objective, history):
                raise ValueError("invalid_recovery_question")
            return audited(
                {
                    "type": "turn.result",
                    "id": message.get("id"),
                    "kind": "clarify",
                    "operation": None,
                    "intentOperations": [],
                    "effectOperations": [],
                    "preserveObjective": False,
                    "question": question,
                    "reply": "",
                    "turn_attempts": max(0, attempts),
                    "turn_recovery": "semantic_clarification",
                    "recovery_attempts": 1,
                    "failure_code": failure_code,
                }
            )
        except Exception:  # noqa: BLE001 - use the protocol safety floor
            pass
        understood_talk = not is_limit and (
            (bool(failure_kinds) and set(failure_kinds) == {CONVERSATION_WORDING_FAILURE}) or content_asked
        )
        # M104 (reserve v3z en13040 «what is the square root of nine» and 17 more → «conversation» with no kind): the
        # kind the attempts decided, when they agree on one talk kind.
        decided_talk_kinds = {kind for kind in conversation_kinds if kind}
        understood_kind = (
            next(iter(decided_talk_kinds))
            if understood_talk and len(decided_talk_kinds) == 1 and decided_talk_kinds <= {"knowledge", "social", "followup"}
            else None
        )
        # Estabilidad cu-v3 2026-10-08 (v2-v3-61): talk understood is never asked back with the person's words, here or
        # in the App's own failure (review r2 finding 3: it travels as understoodAs whatever the attempts' kinds were —
        # mixed, none, or content asked —, not only as the agreed conversationKind).
        understood_as = (understood_kind or "conversation") if understood_talk else ""
        kind, text = (
            _recovery_visible_from_compose(llm, objective, talk=True, history=history)
            if understood_talk else ("conversation", "")
        )
        if not text:
            kind, text = _recovery_visible_from_compose(
                llm, objective, limit=is_limit, history=history, understood_as=understood_as,
            )
        if kind == "clarify" and (not nothing_to_clarify or understood_talk):
            # M97 (reserve A11, DEV-D v3o–v3x composition_failed): talk whose wording failed twice and whose reply the
            # composer could not write either asks back rather than publishing nothing.
            return audited(
                {
                    "type": "turn.result",
                    "id": message.get("id"),
                    "kind": "clarify",
                    "operation": None,
                    "intentOperations": [],
                    "effectOperations": [],
                    "preserveObjective": False,
                    "question": text,
                    "reply": "",
                    "turn_attempts": max(0, attempts),
                    "turn_recovery": "semantic_clarification",
                    "recovery_attempts": 1,
                    "failure_code": failure_code,
                }
            )
        if (
            not text
            # The model ran (its turn attempts failed, its composer answered nothing usable); with the model offline
            # or unavailable, the protocol still writes no prose of its own.
            and failure_kinds
            and callable(getattr(llm, "compose_user_message", None))
            and (floor := _words_floor_result(message, objective, nothing_to_clarify, attempts, failure_code))
        ):
            return audited(floor)
        return audited(
            {
                "type": "turn.result",
                "id": message.get("id"),
                "kind": "conversation",
                "operation": None,
                "intentOperations": [],
                "effectOperations": [],
                "preserveObjective": False,
                "question": "",
                # With nothing to clarify, a composed question is not published
                # as the answer either (tanda-02 «¿cuál es tu lugar de origen?»).
                "reply": text if kind == "conversation" else "",
                # cien-38 060 «ship a piano to Charon»: the recovery composed
                # «I can't ship a piano to Charon—that's outside what I do»
                # and the App refused it as looks_like_failure, because the
                # boundary did not travel with the reply, then published its
                # own «I couldn't understand the request properly», which is
                # false. A limit is a limit also when it is recovered.
                "conversationKind": "unsupported" if is_limit else understood_kind,
                **({"understoodAs": understood_as} if understood_as else {}),
                "turn_attempts": max(0, attempts),
                "turn_recovery": "protocol_fallback",
                "recovery_attempts": 1,
                "failure_code": failure_code,
            }
        )

    return audited(
        {
            "type": "turn.result",
            "id": message.get("id"),
            "kind": "conversation",
            "operation": None,
            "intentOperations": [],
            "effectOperations": [],
            "preserveObjective": False,
            "question": "",
            "reply": "",
            "turn_attempts": max(0, attempts),
            "turn_recovery": "protocol_fallback",
            "recovery_attempts": 0,
            "failure_code": failure_code,
        }
    )


def _words_floor_result(
    message: dict[str, Any], objective: str, nothing_to_clarify: bool, attempts: int, failure_code: object,
) -> dict[str, Any] | None:
    """D59 §7 (owner, 2026-10-02): a turn not understood whose recovery wrote no valid question asks with the person's
    own words (``semantic.dialogue.words_floor_question``), never a fixed «no pude entender»; None when the turn had
    nothing to clarify (a limit, a capability, talk understood) or the message has no word to quote."""

    if nothing_to_clarify:
        return None
    question = dialogue_slot.words_floor_question(
        objective, "en" if _explicit_response_language(objective) == "en" else "es",
    )
    if not question:
        return None
    return {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "clarify",
        "operation": None,
        "intentOperations": [],
        "effectOperations": [],
        "preserveObjective": False,
        "question": question,
        "reply": "",
        "turn_attempts": max(0, attempts),
        "turn_recovery": "words_floor_question",
        "recovery_attempts": 1,
        "failure_code": failure_code,
    }


def _recovery_conversation_facts(history: object, objective: str) -> dict[str, Any]:
    """M109 (DEV-D v4d D-p23-t5, D-p24-t5): what the recovery's composer knows of the conversation — BAXY's last message
    («context») and the person's earlier ones («priorRequests») —, the same data the App's composition carries. Without
    them the writer told «if your earlier messages say you do not do that, say so again» had no earlier message."""

    items = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    last = next(
        (str(item.get("content") or "") for item in reversed(items) if item.get("role") == "assistant"), "",
    ).strip()
    prior = list(_prior_user_texts(history, objective))
    # Uso real v3 tanda 2 («dame 5 ideas…», five given; «no, te pedí 5 che, me tiraste menos» → two drafts cut, then the
    # recovery «Solo te proporcioné dos recetas»): how many items BAXY's last answer listed travels with it, so the
    # writer neither believes a wrong count nor states one (llm.compose_visible_defect «contradicts_previous_answer»).
    listed = semantic_listing.items_listed(last)
    return {
        **({"context": last} if last else {}),
        **({"previousAnswerItems": listed} if listed is not None else {}),
        **({"priorRequests": prior} if prior else {}),
    }


def _recovery_visible_from_compose(
    llm: Any, objective: str, *, limit: bool = False, talk: bool = False, history: object = None,
    understood_as: str = "",
) -> tuple[str, str]:
    """Use model-authored recovery text. A question is a question, not silence.

    Returns ``("clarify", question)``, ``("conversation", reply)`` or
    ``("conversation", "")`` when the model produces nothing usable.

    ``talk`` (M97, reserve A11 «tengo una reunión hoy al mediodía» → «»): the turn understood talk and only the wording
    of its reply failed; the composer answers it as conversation (the App's conversation situation), and a reply that
    asks back is still the reply.

    ``understood_as`` (estabilidad cu-v3 2026-10-08, v2-v3-61): the kind a turn was understood as, when only its
    wording failed; it travels with the question back, so the composer's floor never asks the person's own words back
    (``llm._not_understood_floor``).
    """

    compose = getattr(llm, "compose_user_message", None)
    if not callable(compose):
        return "conversation", ""
    conversation = _recovery_conversation_facts(history, objective)
    if talk:
        try:
            reply = str(
                compose(
                    objective,
                    "conversation",
                    {
                        **conversation,
                        "situation": json.dumps({"kind": "conversation", "polarity": "success"}, ensure_ascii=False),
                    },
                )
                or ""
            ).strip()
        except Exception:  # noqa: BLE001 - the clarification below is the next floor
            return "conversation", ""
        if (
            not reply
            or len(reply) > 4_096
            or dialogue_slot.says_the_message_back(reply, objective)
            or (reply.endswith("?") and _RECOVERY_MIRRORED_REQUEST.search(read_fold(reply)) is not None)
            # M101 (DEV-D v3z D-p31-t2): a talk reply that tells a failure is refused by the App, whose turn failure
            # then had no final; the clarification below asks back instead.
            or talk_reply_tells_a_failure(reply, objective)
        ):
            return "conversation", ""
        return "conversation", reply
    try:
        text = str(
            compose(
                objective,
                # A place no operation reaches, or a limit the turn already
                # decided, is a boundary, not a failed reading: «I couldn't
                # understand the request to send flowers to Deimos» is false.
                # Tanda 3 and 4 2026-09-24: anything else is asked about — the
                # one thing missing to do it —, never answered with «no pude
                # entender bien la solicitud, explícalo de nuevo».
                "error" if limit else "clarification",
                {
                    # M109: the question back asks about this conversation, not about the message alone.
                    **({} if limit else conversation),
                    "situation": json.dumps(
                        {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}
                        if limit
                        else {
                            "kind": "clarification", "cause": "ambiguous_request", "polarity": "pending",
                            **({"understoodAs": understood_as} if understood_as else {}),
                        },
                        ensure_ascii=False,
                    )
                },
            )
            or ""
        ).strip()
    except Exception:  # noqa: BLE001 - empty reply is the honest floor
        return "conversation", ""
    if not text or len(text) > 4_096:
        return "conversation", ""
    if _recovery_question_is_valid(text, objective):
        return "clarify", text
    if text.endswith("?") and (
        _RECOVERY_MIRRORED_REQUEST.search(read_fold(text)) is not None
        # M99 (DEV-D v3x D-s053): a question that offers back the one named asks nothing, here too.
        or (_recovery_question_is_valid(text) and not _recovery_question_is_valid(text, objective))
    ):
        # M54: the person's request handed back is neither a question to publish nor a reply.
        return "conversation", ""
    return "conversation", text
