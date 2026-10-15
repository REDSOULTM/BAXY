"""Follow-ups on what the last turn did: the dialogue slot a message completes, a correction already held, the
same thing not done again, and the notice just set moved or cancelled.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from . import turn_audit as turn_audit_module
from .semantic import decider as semantic_decider
from .semantic import dialogue as dialogue_slot
from .semantic import levels as semantic_levels
from .semantic import reading as semantic_reading
from .semantic import temporal as semantic_temporal
from .semantic.patterns import output_level_request
from .effect_intent import (
    ApplicationCatalogIndex,
    EffectIntent,
    GameCatalogIndex,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from .semantic.request import response_language as read_language
from .semantic.dialogue import _previous_user_request
from .turn_history import _decisive_request_language, _person_message, _read_reply_language
from .argument_grounding import _ground_explicit_arguments
from .turn_decisions import _explicit_stable_no_effect_turn_decision
from .deterministic_finals import _held_fact_final


def _rearm_in_context(
    message: dict[str, Any],
    *,
    llm: Any,
    available_operations: tuple[str, ...],
    application_names: tuple[str, ...] | ApplicationCatalogIndex = (),
    game_catalog: GameCatalogIndex = GameCatalogIndex(),
    dialogue_state: dialogue_slot.DialogueState | None = None,
) -> tuple[str, str] | None:
    """Fill the dialogue slot: the request this message completes, or None.

    Returns (rearmed request, how) when the message depends on the previous turns
    (``semantic.dialogue.dependency``) and a rearmed request stays inside what was
    said or verified. The pattern path is tried first (pending request + answer); the
    model rewrites, with the verified dialogue state, what the patterns cannot join.
    Talk is never rewritten.
    """

    objective = str(message.get("text", "")).strip()
    history = message.get("history") or []
    slot = dialogue_slot.read_slot(message, history, objective)
    dependency = dialogue_slot.dependency(objective, slot)
    if dependency is None:
        return None

    def effects_of(candidate: str) -> tuple[str, ...]:
        def resolve(clause: str) -> EffectIntent | None:
            return resolve_explicit_effects(clause, available_operations, application_names, game_catalog)

        found = resolve(candidate)
        if found is None:
            uttered = semantic_reading.utterance_form(candidate, resolve)
            found = uttered[1] if uttered is not None else None
        return tuple(found.operations) if found is not None else ()

    def continued_operations() -> tuple[str, ...]:
        # What the message continues: what the last turn verified or was about (an effect, or the one its question
        # asks for), or what the readers read in the last request (a conversation turn reads none).
        if dialogue_state is not None and (dialogue_state.operations or dialogue_state.intended):
            return dialogue_state.operations or dialogue_state.intended
        previous = (dialogue_state.request if dialogue_state is not None else None) or _previous_user_request(
            history, objective,
        )
        return effects_of(previous) if previous else ()

    def audited(rearmed: str | None, how: str, proposal: str | None = None) -> tuple[str, str] | None:
        turn_audit_module._append_turn_audit(
            {
                "schema": "baxy.mind-turn-audit.v1",
                "request_id": message.get("id"),
                "phase": "dialogue_slot",
                "dependency": dependency,
                "rearmed_by": how,
                "rearmed": rearmed,
                "model_proposal": proposal,
            }
        )
        return None if rearmed is None else (rearmed, how)

    def asked_for() -> tuple[str, ...]:
        # The operations the message itself asks for: read, or asked about for a missing value.
        try:
            asked = resolve_explicit_clarification_intent(objective, available_operations, application_names)
        except (TypeError, ValueError):
            asked = None
        return (*effects_of(objective), *(asked.operations if asked is not None else ()))

    def continuing(candidate: str) -> str | None:
        # Tanda 7: a follow-up continues what was done. Its request reads no effect, or only effects of that family
        # (tanda 9: or of what the message itself asks for, «ponme un timer de ese tiempo»); a correction of the
        # alarm or timer just set replaces it instead of setting a second one. None otherwise.
        read = effects_of(candidate)
        if not dialogue_slot.continues(read, (*continued_operations(), *asked_for()), dialogue_state):
            return None
        cancel = (
            dialogue_state.cancel_last_alarm(dialogue_slot.spanish(candidate))
            if dialogue_state is not None and read == ("notification.schedule",)
            and dialogue_slot.followup(objective).replaces_last
            else None
        )
        if cancel is None:
            return candidate
        replaced = f"{cancel} {'y' if dialogue_slot.spanish(candidate) else 'and'} {candidate}"
        return replaced if effects_of(replaced) == ("notification.cancel.latest", "notification.schedule") else None

    level = semantic_levels.read(objective)
    if level is not None and level.setting is not None:
        # «Volume más alto please», «Brillo 20%»: an output level that names its object stands on its own.
        return audited(None, "pattern_kept")
    if level is not None or semantic_levels.answer(objective) is not None:
        # Uso real 2026-09-23: «un 10» after «súbele un poco» was rewritten by the model as «súbele un poco a
        # la canción un 10», and «súbelo a 80» and «bájale» came back as questions about what to raise. An
        # output level is completed from the request it follows, with the object and direction that request
        # carried. A level that is not completed here («bájale», «más bajito») is read as it arrived, and the
        # level readers ask for the amount.
        completed = output_level_request(
            objective, _previous_user_request(history, objective) or slot.pending_request, available_operations,
            asked=slot.last_reply or "",
        )
        if completed is not None and resolve_explicit_effects(
            completed, available_operations, application_names, game_catalog,
        ) is not None:
            return audited(completed, "pattern")
        if level is not None and (
            dependency != "followup"
            or not continued_operations()
            or any(op.startswith(("audio.", "system.settings")) for op in continued_operations())
        ):
            # Tanda 7 «actually make it 9» after a timer is the timer's amount: only a level that follows a level
            # request, or nothing the readers read, stays a level.
            return audited(None, "pattern_kept")

    if (
        dependency == "reference"
        and slot.antecedents
        and dialogue_slot.asks_to_look_up(objective)
        and dialogue_slot.asked_about(slot.antecedents[0])
    ):
        # Fase 3.5 (dueño turn 59): «investigala» after «¿la nueva peli de X es buena?» looks up X.
        # Only words the person said; the rearmed request is classified as usual.
        substituted = dialogue_slot.substituted_reference(objective, slot.antecedents[0])
        if substituted is not None:
            return audited(substituted, "pattern")
    if dependency == "subject":
        # Uso real 2026-09-23: «cuántos años tiene» after «quién es el presidente
        # de chile» is that person's age, looked up, never recited from memory.
        completed = dialogue_slot.subject_completed(objective, slot.antecedents[0])
        if completed is not None:
            return audited(completed, "pattern")
    if dependency == "reference" and slot.antecedents and not dialogue_slot.asks_to_look_up(objective):
        # 2026-09-22: «cerralo» after «abrí el bloc de notas» was read alone as
        # "close the active window" and closed VS Code. With an antecedent, the
        # pronoun is that antecedent's object, never whatever is in front.
        substituted = dialogue_slot.substituted_reference(objective, slot.antecedents[0])
        if substituted is not None and resolve_explicit_effects(
            substituted, available_operations, application_names, game_catalog,
        ) is not None:
            return audited(substituted, "pattern")
        # Tanda 9: «pausalo un toque», «dale, seguí» right after a video — what the last turn acted on, named as the
        # readers name it; the request must read an effect of that family.
        for thing in dialogue_slot.things_acted_on(continued_operations(), read_language(objective) == "es"):
            candidate = dialogue_slot.with_object(objective, thing)
            settled = continuing(candidate) if candidate and effects_of(candidate) else None
            if settled is not None:
                return audited(settled, "pattern")
    if (
        dependency == "answer"
        and slot.pending_request
        and dialogue_slot.is_assent(objective)
        and _explicit_stable_no_effect_turn_decision(
            slot.pending_request, None, pending_clarification=False,
        ) is not None
    ):
        # 0758398ed: a plain «sí» to a yes/no question about a stable no-effect
        # request closes that request; it does not turn the offer into an effect.
        return audited(slot.pending_request, "pattern")
    if dependency == "answer" and slot.pending_request:
        # D61: «no, mejor a las 7:20» to a question about «ponme una alarma a las 7 pa mañana» replaces the hour the
        # request said; joined after it, the hour of 1 to 12 left without its part of the day (no longer asked) would
        # stand next to the new one.
        replaced = dialogue_slot.corrected_request(slot.pending_request, objective)
        replaced_effects = effects_of(replaced) if replaced is not None else ()
        if replaced_effects and dialogue_slot.same_family(replaced_effects, effects_of(slot.pending_request)):
            return audited(replaced, "pattern")
        try:
            asked = resolve_explicit_clarification_intent(
                slot.pending_request, available_operations, application_names,
            )
        except (TypeError, ValueError):
            asked = None
        joined = dialogue_slot.joined_answer(
            slot.pending_request,
            objective,
            percentage=asked is not None and bool({"amount", "level"} & set(asked.missing_fields)),
        )
        if joined is not None:
            try:
                resolved = resolve_explicit_effects(
                    joined, available_operations, application_names, game_catalog,
                )
                still_missing = resolve_explicit_clarification_intent(
                    joined, available_operations, application_names,
                )
            except (TypeError, ValueError):
                resolved, still_missing = None, None
            # The answer completes the question that was asked: the joined
            # request must land in the family of that question, never next to it.
            same_family = asked is None or (
                resolved is not None and bool(set(resolved.operations) & set(asked.operations))
            )
            if resolved is not None and still_missing is None and same_family:
                return audited(joined, "pattern")
    last_request = (dialogue_state.request if dialogue_state is not None else None) or (
        slot.antecedents[0] if slot.antecedents else None
    )
    if dependency == "destination" and last_request:
        # Fase 3.5 (held-out turn 18 «en YouTube mejor» after «tengo ganas de
        # escuchar reggaetón»): only the destination of the last request changes.
        # The model read «mejor» as «mejorar»; the pattern joins the destination
        # to the request as said and keeps it when the readers read it in the family
        # of that request. Tanda 7 «¿y en Mar del Plata?»: the last request is the
        # last turn's as completed («¿va a llover el finde?»), not the previous message.
        joined = dialogue_slot.joined_answer(last_request, objective)
        if (
            joined is not None
            and dialogue_slot.differs(joined, last_request)
            and effects_of(joined)
            and dialogue_slot.same_family(effects_of(joined), effects_of(last_request))
        ):
            return audited(joined, "pattern")
    if dependency == "followup":
        said = dialogue_slot.followup(objective)
        if (said.continued or said.corrected) and not dialogue_slot.refers_back(objective) and effects_of(said.said):
            # Tanda 7 «and remind me at 7:30 to call grandma»: after the connector, a complete request is itself.
            return audited(said.said, "pattern")
        # Tanda 7b: what the person's words already say with the last turn is not left to the model — a new amount,
        # hour or day for the last request, the song a music turn left playing, what was just set.
        music = any(op.startswith("media.") for op in continued_operations())
        for candidate in (
            dialogue_slot.corrected_request(last_request, objective),
            dialogue_slot.as_the_song(objective) if music else None,
            dialogue_state.listing_request(objective) if dialogue_state is not None else None,
            dialogue_slot.again(last_request, objective),
        ):
            settled = continuing(candidate) if candidate and effects_of(candidate) else None
            if settled is not None:
                return audited(settled, "pattern")
        # Tanda 9: «ponme un timer de ese tiempo» — only the value BAXY just gave is put in; the order is the
        # person's own, so whatever it reads is what they asked for.
        valued = dialogue_slot.value_from_reply(objective, slot.last_reply)
        if valued is not None and effects_of(valued):
            return audited(valued, "pattern")
        if not (said.continued or said.corrected) and not dialogue_slot.refers_back(objective) and effects_of(objective):
            # Verification 2026-09-25 (layer A log:147): «para la canción» (stop it) had the form of a place
            # («para la X», for the X), was rewritten and looked up. What reads a request by itself is that request.
            return audited(None, "pattern_kept")
    verified = dialogue_state.lines() if dialogue_state is not None else []
    try:
        rewritten = llm.rewrite_in_context(
            objective, slot.context_lines(), dependency=dependency, verified=verified,
            shape=dialogue_slot.shape(objective, dependency),
        )
    except Exception:  # noqa: BLE001 - a failed rewrite leaves the message as it arrived
        rewritten = None
    if rewritten is not None and not dialogue_slot.differs(rewritten, objective):
        return audited(None, "model_kept", rewritten)
    if rewritten and dialogue_slot.rewrite_stays_in_context(rewritten, objective, slot, verified):
        if dependency not in {"followup", "destination"}:
            return audited(rewritten, "model", rewritten)
        settled = continuing(rewritten)
        return audited(settled, "model" if settled else "model_rejected", rewritten)
    if dependency == "answer" and slot.held and slot.pending_request and rewritten is None:
        # The model was unavailable: the pending request the shell holds and its answer travel together in the
        # form the grounding readers already join (AUDIO1789). A question read only from the history is not held.
        return audited(f"{slot.pending_request}\nAclaración confiable del usuario: {objective}", "joined")
    return audited(None, "model_rejected" if rewritten else "model_failed", rewritten)


_MOVED_NOTIFICATION_PLAN = ("notification.cancel.latest", "notification.schedule")
# M173: the steps of a planned move of a notice — taking it off, and setting it again.
_NOTICE_CANCELS = frozenset({"notification.cancel.at", "notification.cancel.latest", "reminder.delete"})
_NOTICE_SETS = frozenset({"notification.schedule", "reminder.create"})


def _retimed_conversation_notice(
    dialogue_state: dialogue_slot.DialogueState, history: object, objective: str, *, deciding: bool = False,
) -> dialogue_slot.RetimedNotification | None:
    """M115/M173: the notice the last turn set, as a planned move of it moves it: its new time is the one the person's
    message gives (a clock, a new count from the same moment), or the moment it counts from what BAXY said in this
    conversation («30 min antes del partido», M110/M168 ``anchored_offset_request``), or else the one the restatement
    says. None unless the last turn verified setting it and one of them gives a new time."""

    person = _person_message(history, objective)
    lines = [str(item.get("content") or "") for item in reversed(history if isinstance(history, list) else [])
             if isinstance(item, dict)]
    replies = [
        str(item.get("content") or "") for item in reversed(history if isinstance(history, list) else [])
        if isinstance(item, dict) and item.get("role") == "assistant"
    ]
    anchored = semantic_temporal.anchored_offset_request(
        person, replies[0] if replies else None, [line for line in lines if line != person],
    )
    for said in dict.fromkeys(said for said in (person, anchored, objective) if said):
        moved = dialogue_state.retimed_notification(said, deciding=deciding, moving=True)
        if moved is not None:
            return moved
    return None


def _correction_already_held(
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
    llm: Any,
    risk_of: Callable[[str], str | None] | None = None,
) -> dict[str, Any] | None:
    """Ronda 19 (t3-c16 «no, en YouTube» with YouTube already playing → played again; t3-c18 «esa no es la de
    programador wey, sigue en la estandar, cambiala» with Programador read on the screen → four random clicks): a
    correction that the last turn's verified result already holds is answered with that fact before anything is
    decided (``DialogueState.already_holds``); nothing is done again. Encargo TZ-HOLD (tanda z6 t4-c01 t4 «no po, en
    spotify te dije, no en youtube» with Spotify verified playing → «Eso es incorrecto, no estoy reproduciendo en
    Spotify.»): a held effect, what the last turn's verified result read, is said with its sentence (data:
    operation_floor «heldFact»), never drafted — a draft can only lose it or deny it. Only a held count, the items told
    again, and an undo of nothing are worded by the writer (situation ``alreadyHolds``/``undoNothing``); when it cannot,
    or says the last answer again, the turn is decided as before. None otherwise.

    Revisión 2 de la ronda 22: ``risk_of`` is the catalog's risk of an operation; only an operation with an effect
    holds a target the person names (kind target), never a read."""

    if dialogue_state is None:
        return None
    text = str(message.get("text", ""))
    # Revisión 3 de la ronda 22: the last answer the person saw, as the history carries it.
    history = message.get("history") if isinstance(message.get("history"), list) else []
    shown = next(
        (
            str(item.get("content") or "")
            for item in reversed(history)
            if isinstance(item, dict) and item.get("role") == "assistant"
        ),
        None,
    )
    holds = dialogue_state.already_holds(text, risk_of=risk_of, shown=shown)
    # Ronda 24 (r23 t2-c04 #3 «regresala como estaba» after a turn that only asked): an undo whose antecedent changed
    # nothing is told so (``DialogueState.undo_of_nothing``); the computer-use engine is never called for it.
    unchanged = dialogue_state.undo_of_nothing(text, risk_of=risk_of) if holds is None else None
    if holds is None and unchanged is None:
        # Nothing held: the writer is not looked up (a turn decided without the model never touches it).
        return None
    previous = dialogue_state.last_final()
    fact = (
        {"alreadyHolds": {**holds.facts(), "previousReply": (previous or "")[:400]}}
        if holds is not None
        else {"undoNothing": {"request": str(unchanged)[:400], "previousReply": (previous or "")[:400]}}
    )
    situation = {"kind": "conversation", "polarity": "success", **fact}
    language = _read_reply_language(text, message.get("history") or []) or _decisive_request_language(
        dialogue_state.request or ""
    )
    # Encargo TZ-CAL (tanda z2 t3-c18 t3) and TZ-HOLD (tanda z6 t4-c01 t4): a held effect is told from the facts
    # first, as a mission's are (``computer_use_finals._computer_use_floor_first``); without its sentence, the turn is
    # decided as before.
    if holds is not None and holds.effect:
        reply = _held_fact_final(situation, language or "es")
        if not reply:
            return None
    else:
        compose = getattr(llm, "compose_user_message", None)
        if not callable(compose):
            return None
        try:
            reply = compose(text, "conversation", {"situation": situation}, said=text)
        except Exception:  # noqa: BLE001 - the turn is decided as before when the writer cannot word this
            return None
    reply = str(reply or "").strip()
    if not reply or (previous and " ".join(reply.split()) == " ".join(previous.split())):
        return None
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "correction_already_holds" if holds is not None else "undo_of_nothing",
            "raw_decision": {"operations": list(dialogue_state.operations), "request": dialogue_state.request},
        }
    )
    return {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "conversation",
        "operation": None,
        "intentOperations": [],
        "effectOperations": [],
        "preserveObjective": False,
        "question": "",
        "reply": reply[:4096],
        **({"responseLanguage": language} if language in {"es", "en", "mixed"} else {}),
    }


def _undelivered_done_again(
    result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
) -> dict[str, Any]:
    """Ronda 19 (t1-c03 «no wey te pedi 5 nomas, no me sueltes la lista entera» after «No lo encontré.» → «¿Podrías
    decirme solo los 5 títulos de la lista?»): a question decided for a reproach of what the person asked, when the
    last turn failed or did not deliver it, asks them for what they had asked. The last turn's operation is done again
    on its request instead (``DialogueState.undelivered_reproach``). Anything else stays as decided."""

    if dialogue_state is None or result.get("kind") != "clarify":
        return result
    again = dialogue_state.undelivered_reproach(str(message.get("text", "")))
    if again is None:
        return result
    operation, request = again
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "undelivered_done_again",
            "raw_decision": {"operations": [operation], "request": request},
        }
    )
    return {
        **result,
        "kind": "action",
        "operation": operation,
        "intentOperations": [operation],
        "effectOperations": [operation],
        "question": "",
        "objective": request,
    }


def _not_the_same_again(
    result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
    llm: Any,
) -> dict[str, Any]:
    """Uso real 2026-10-07 («si pero quiero buscar un top 3» → the same search, the same film, the same sentence): a
    correction or an insistence decided as exactly what the last turn did is not done again. What the correction
    changes is applied (a place named is ``searched_in_place``, a count is read by the arguments); with nothing
    changed, BAXY says that looking again finds the same and offers the search in the browser. A composition that
    fails leaves the turn as decided (the writer still holds ``sameResultAgain``)."""

    if dialogue_state is None or result.get("kind") not in {"action", "plan"}:
        return result
    text = str(message.get("text", ""))
    operations = result.get("effectOperations") or ([result["operation"]] if result.get("operation") else [])
    if not dialogue_state.repeats_the_last_plan(operations, result.get("objective") or text, text):
        return result
    if dialogue_state.undelivered_reproach(text) is not None:
        # Revisión 2 de la ronda 24 (r23 t1-c03#2 «no wey te pedi 5 nomas» after one name, or after «No lo
        # encontré.»): the last turn did not deliver what was asked (it failed, or listed fewer than the count asked);
        # that looking again finds the same was never seen. The plan is done again (the listing read from the pages).
        return result
    compose = getattr(llm, "compose_user_message", None)
    if not callable(compose):
        return result
    previous = dialogue_state.last_told()
    situation = {
        "kind": "conversation",
        "polarity": "success",
        "sameResultAgain": {
            "operation": operations[0] if len(operations) == 1 else list(operations),
            "searched": dialogue_state.searched_topic() or "",
            "previousReply": (previous or "")[:400],
        },
    }
    try:
        reply = compose(text, "conversation", {"situation": situation}, said=text)
    except Exception:  # noqa: BLE001 - the decided turn stands when the writer cannot word this
        return result
    reply = str(reply or "").strip()
    if not reply or (previous and " ".join(reply.split()) == " ".join(previous.split())):
        return result
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "same_plan_after_correction",
            "raw_decision": {"operations": list(operations), "request": result.get("objective")},
        }
    )
    return {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "conversation",
        "operation": None,
        "intentOperations": [],
        "effectOperations": [],
        "preserveObjective": False,
        "question": "",
        "reply": reply[:4096],
        **({"responseLanguage": result["responseLanguage"]} if result.get("responseLanguage") else {}),
    }


def _third_party_named(
    result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
) -> dict[str, Any]:
    """M179 (DEV-I v5a/v5c/v5d I-w26-t5 «oye y el tecnico de ellos quien es ahora» four turns after «a que hora juega
    chile el martes» → «¿Quién es el técnico de ellos ahora?» searched as said, and the coach of the Tigres answered):
    the third party of a search the decider left as «de ellos / their» is the one name of what this conversation last
    searched (``semantic.decider.with_the_searched_name``). The objective is what the arguments step reads the query
    from; the decider's values were for the pronoun and are not remembered for this one."""

    if dialogue_state is None or result.get("kind") != "action" or result.get("operation") != "web.search":
        return result
    named = semantic_decider.with_the_searched_name(
        str(result.get("objective") or ""), str(message.get("text", "")), dialogue_state.searched_topic(),
    )
    return result if named is None else {**result, "objective": named}


def _own_notice_moved(
    result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
    tool_by_name: dict[str, dict],
) -> dict[str, Any]:
    """M173 (DEV-I v5c I-w40-t2 «hmm, push it to 6:45 instead», I-w12-t5 «uh no, correla a 30 min antes del partido…»,
    I-w04-t2 «actually make it half three», DEV-F v5c F-w55-t2 «no, mejor media hora antes, una hora es mucho»): the
    decider planned the move right (cancel + set again), but the plan cancelled at the old clock
    (``notification.cancel.at``), which the run's store held more than once («I couldn't cancel the alarm or
    reminder.»), or the notice was a reminder of BAXY's store (``reminder.create``), which notification.cancel.* never
    reads («¿A qué hora y qué tipo de notificación…?»). A planned move of the notice the last turn set, with its new
    time read (``_retimed_conversation_notice``), moves THAT one by how it was set: the latest of its kind cancelled
    and set again while it is the last one of its kind this conversation set and it still has to ring (M145), or the
    reminder of the store deleted by its exact title and made again. A move that names another notice by its clock,
    and anything else, stays as decided."""

    if dialogue_state is None or result.get("kind") != "plan":
        return result
    effects = tuple(str(operation) for operation in result.get("effectOperations") or ())
    if len(effects) != 2 or effects[0] not in _NOTICE_CANCELS or effects[1] not in _NOTICE_SETS:
        return result
    moved = _retimed_conversation_notice(
        dialogue_state, message.get("history"), str(result.get("objective") or ""), deciding=True,
    )
    if moved is None or moved.set_at is None:
        return result
    due = moved.schedule_arguments.get("dueUtc") or ""
    try:
        new = (
            None if due.startswith(("in ", "en "))
            else datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(moved.set_at.tzinfo)
        )
    except ValueError:
        return result
    person = _person_message(message.get("history"), str(message.get("text", "")))
    if any(
        semantic_temporal.names_another_notice(said, moved.set_at, new)
        for said in (person, str(result.get("objective") or ""))
    ):
        # «y la de las 7 pásala a las 8» right after one set at 6:30: another notice, named by its clock.
        return result
    operations = moved.moving_operations
    needed = (*operations, "reminder.resolve.exact") if moved.set_by == "reminder.create" else operations
    if operations == effects or any(operation not in tool_by_name for operation in needed):
        return result
    if moved.set_by != "reminder.create" and not dialogue_state.own_notification_at(moved.kind, None):
        return result
    kept = {**result, "effectOperations": list(operations), "intentOperations": list(operations)}
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "own_notice_moved",
            "raw_decision": {"mode": "action", "request": kept.get("objective"), "effect_operations": list(operations)},
            "stages": [],
            "final": {"kind": "plan", "intent_operations": list(operations), "effect_operations": list(operations)},
        }
    )
    return kept


def _moved_notification_result(
    message: dict[str, Any], request: str, operations: tuple[str, ...] = _MOVED_NOTIFICATION_PLAN,
) -> dict[str, Any]:
    """M102: the turn that moves the notification just set — cancel the latest of its kind and set it again — as the
    plan the shell runs, with ``request`` (``DialogueState.moved_notification_request``) as its objective. M173: a
    reminder of the store is deleted and made again instead (``operations``, ``DialogueState.moving_operations``)."""

    result: dict[str, Any] = {
        "type": "turn.result",
        "id": message.get("id"),
        "kind": "plan",
        "operation": None,
        "intentOperations": list(operations),
        "effectOperations": list(operations),
        "question": "",
        "reply": "",
        "objective": request,
    }
    language = _read_reply_language(str(message.get("text", "")), message.get("history") or [])
    if language in {"es", "en", "mixed"}:
        result["responseLanguage"] = language
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "moved_notification",
            "raw_decision": {"mode": "action", "request": request, "effect_operations": list(operations)},
            "stages": [],
            "final": {
                "kind": "plan",
                "intent_operations": list(operations),
                "effect_operations": list(operations),
            },
        }
    )
    return result


def _cancelled_clock(text: str, schema: dict[str, object]) -> dict[str, object] | None:
    """M145: the clock and kind a cancellation in ``text`` selects, as ``notification.cancel.at``'s arguments: of a
    move («Cambia la alarma de las 7 a las 7:30»), the old clock; of a cancellation, its own. A move that names no old
    clock is of the last one set: its kind alone, with ``hour`` None. None without a kind and an hour."""

    change = semantic_temporal.notification_change(text)
    if change is not None:
        if change.old is None:
            return {"kind": change.kind, "hour": None}
        text = change.cancel_request()
    selected = _ground_explicit_arguments("notification.cancel.at", text, schema)
    if not isinstance(selected, dict) or not isinstance(selected.get("hour"), int) or selected.get("kind") not in {
        "alarm", "reminder",
    }:
        return None
    return selected


def _own_notification_cancellation(
    result: dict[str, Any],
    message: dict[str, Any],
    dialogue_state: dialogue_slot.DialogueState | None,
    tool_by_name: dict[str, dict],
) -> dict[str, Any]:
    """M145 (DEV-H v4p H-w29-t2 «no espera, mejor a las 7:30» after «…¿me pones una alarma a las 7 porfa?» → «varias
    alarmas o recordatorios a esa misma hora… no se pudieron distinguir»; H-w45-t4 «cancel the 7 one»): the store also
    held alarms of other conversations at 19:00, and ``notification.cancel.at`` refuses two at one clock. When the clock
    this turn cancels (or moves from) is that of the alarm, timer or reminder this conversation set and verified, and
    it is the last one it set of its kind (``DialogueState.own_notification_at``), the cancellation is of that one: the
    latest BAXY set of its kind (``notification.cancel.latest``). Without one of its own there, the turn stays as it
    was decided and the ambiguity is told as before."""

    if dialogue_state is None or result.get("kind") not in {"action", "plan"}:
        return result
    effects = [str(operation) for operation in result.get("effectOperations") or ()]
    tool = tool_by_name.get("notification.cancel.at")
    if (
        effects.count("notification.cancel.at") != 1
        or "notification.cancel.latest" in effects
        or "notification.cancel.latest" not in tool_by_name
        or tool is None
    ):
        return result
    schema = tool["function"]["parameters"]
    selected = next(
        (
            found for found in (
                _cancelled_clock(str(result.get("objective") or ""), schema),
                _cancelled_clock(_person_message(message.get("history"), str(message.get("text", ""))), schema),
            )
            if found is not None
        ),
        None,
    )
    if selected is None or not dialogue_state.own_notification_at(
        str(selected["kind"]), selected["hour"], int(selected.get("minute") or 0),
        selected.get("period") if selected.get("period") in {"am", "pm"} else None,
    ):
        return result

    def own(operations: object) -> list[str]:
        return [
            "notification.cancel.latest" if operation == "notification.cancel.at" else str(operation)
            for operation in operations or ()
        ]

    kept = {**result, "effectOperations": own(effects), "intentOperations": own(result.get("intentOperations"))}
    if kept.get("operation") == "notification.cancel.at":
        kept["operation"] = "notification.cancel.latest"
    turn_audit_module._append_turn_audit(
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": message.get("id"),
            "phase": "final",
            "decision_path": "own_notification",
            "raw_decision": {"mode": "action", "request": kept.get("objective"), "effect_operations": kept["effectOperations"]},
            "stages": [],
            "final": {
                "kind": kept["kind"],
                "intent_operations": kept["intentOperations"],
                "effect_operations": kept["effectOperations"],
            },
        }
    )
    return kept
