"""Finals of computer-use missions: the voice instruction, the defects of a final against the mission's
steps and receipts, and the floor said from its facts.
"""

from __future__ import annotations

import json
import os
import re

from . import operation_floor
from .semantic.normalize import _accent_folded_with_punctuation, fold
from .semantic import claims as semantic_claims
from .semantic import windows as semantic_windows
from .llm_audit import _capture_compose_stage
from .compose_situation import _computer_use_mission, _decoded_reason, _merged_observed, _situation_steps
from .failure_wording import _asserts_failure


# Live 2026-10-07 (v2 voice audit, 239 published computer-use finals): «Ya he entrado en la sección…», «Ya estamos en
# la pestaña…», «Ya te llevé a la sección de sonido…», «…página de inicio de Spotify Premium», «mis playlists»,
# «Descargas dentro de Documentos», two sentences where one was asked. The voice of a mission final, in the request's
# language (documentacion/00_IDENTIDAD.md: first person singular, tuteo, one sentence, the observable state).
COMPUTER_USE_VOICE_PROMPT_ES = (
    "Voz de este final: sólo este pedido y los hechos de esta misión, nada de turnos anteriores. Habla en primera "
    "persona singular, con tuteo chileno y en pretérito simple («llegué», «elegí», «escribí»); nunca «he "
    "entrado», «ha quedado», «estamos», «te llevé». No digas que abriste una aplicación que ya estaba abierta. Nombra el lugar o el resultado tal como lo escribe la ventana, "
    "sin planes ni versiones del producto («Premium», «Pro») y sin decir que un lugar está dentro de otro. Lo de la "
    "persona es suyo («tus listas»), nunca «mis»."
)
COMPUTER_USE_VOICE_PROMPT_EN = (
    "Voice of this final: only this request and this mission's facts, nothing from earlier turns. Speak in the first "
    "person singular, in the simple past («I went to», «I chose», «I typed»); never «we», never «I've "
    "gone», never «I'm already in», never «I took you». Never say you opened an app that was already open. Name the place or the result as the window writes it, with "
    "no plan or edition of the product («Premium», «Pro»), and never say one place is inside another. The person's "
    "things are theirs («your playlists»), never «my»."
)
COMPUTER_USE_VOICE_LENGTH_ES = " Una sola frase corta, de 18 palabras o menos."
COMPUTER_USE_VOICE_LENGTH_EN = " One short sentence of 18 words or fewer."
# cu-r17 (live 2026-10-07: «Abrí Configuración.» for «… y decime el volumen»): a mission that carries the person's
# question answers it in the final, with the value the window wrote, or says it could not see it.
COMPUTER_USE_VOICE_QUESTION_ES = (
    " La persona preguntó «{question}»: tu frase responde eso primero, con el valor tal como lo escribe la ventana "
    "(seen.screen, seen.evidence), como dato y no como lugar («El volumen está en 60.», «El modo es Oscuro.»; nunca "
    "«Llegué al volumen…»); si la ventana no lo muestra, di que no lo pude ver. Nombrar el lugar o la "
    "aplicación no es la respuesta."
)
COMPUTER_USE_VOICE_QUESTION_EN = (
    " The person asked «{question}»: your sentence answers that first, with the value as the window writes it "
    "(seen.screen, seen.evidence), as a fact and not as a place («The volume is at 60.», «The mode is Dark.»; never "
    "«I went to the volume…»); if the window does not show it, say you could not see it. Naming the place or the "
    "app is not the answer."
)


def _computer_use_voice_instruction(situation: dict, language: str) -> str:
    """The voice of a computer-use final: first person singular, preterite, the window's own words, nothing from
    earlier turns; a reached mission (no question about a failure to explain) in one sentence of 18 words or fewer."""

    from . import cu_projection as _cu_projection

    english = language == "en"
    text = COMPUTER_USE_VOICE_PROMPT_EN if english else COMPUTER_USE_VOICE_PROMPT_ES
    mission = _computer_use_mission(situation) or {}
    observed = _merged_observed(mission)
    question = _cu_projection.project_seen(observed, language).get("question") if observed else None
    if isinstance(question, str) and question.strip():
        text += (COMPUTER_USE_VOICE_QUESTION_EN if english else COMPUTER_USE_VOICE_QUESTION_ES).format(
            question=question.strip()
        )
    if observed.get("reached") is True:
        text += COMPUTER_USE_VOICE_LENGTH_EN if english else COMPUTER_USE_VOICE_LENGTH_ES
    return text


def _app_open_records(value: object, depth: int = 0) -> list[dict]:
    """Every app.open record (a mission step, a plan step) a computer-use situation holds."""

    if depth > 6:
        return []
    if isinstance(value, list):
        return [record for item in value for record in _app_open_records(item, depth + 1)]
    if not isinstance(value, dict):
        return []
    own = [value] if value.get("operation") == "app.open" else []
    return own + [record for child in value.values() for record in _app_open_records(child, depth + 1)]


def _computer_use_unreached_defect(text: str, observed: dict) -> str:
    """Ronda 20 P5 (pasada r18 v3-16: «Llegué al editor de la imagen pero no pude poner el filtro blanco y negro porque
    la pantalla se quedó bloqueada.» with subgoals[0].reached false and the stop on no visible step). A mission that did
    not get there, whatever its polarity: a first-person past act over a part not reached that no verified step or
    reached part backs is «unreached_claim» (semantic.claims.claims_unreached_part, judged against subgoals[].reached,
    a fact, never a phrase); a cause the final gives that is neither the observed one (seen.stoppedBecause, in either
    language) nor a fact of the mission is «invented_cause». "" otherwise."""

    from . import cu_projection as _cu_projection

    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    done = [step for step in raw_steps if isinstance(step, dict) and step.get("ok") is True]
    parts = [part for part in observed.get("subgoals") or () if isinstance(part, dict)]
    # Revisión 2 de r20 P5 (bloqueante 1.iii): what a step acted on backs the object as a clicked label does — the text
    # a typing step sent (also one whose effect stayed uncertain: the keys went, v2-v3-30 «escribí «flecha»» with the
    # field showing «flec») and the application an app.open opened.
    sent = [
        step for step in raw_steps
        if isinstance(step, dict) and step.get("ok") is not True and step.get("effectUncertain") is True
    ]
    backers = [step.get(key) for step in done for key in ("label", "name", "text", "appId")] + [
        step.get("text") for step in sent
    ] + [part.get("goal") for part in parts if part.get("reached") is True]
    for part in parts:
        if part.get("reached") is not True and semantic_claims.claims_unreached_part(text, part.get("goal"), backers):
            return "unreached_claim"
    if not observed.get("stoppedBy"):
        return ""
    facts: list[object] = []
    for language in ("es", "en"):
        seen = _cu_projection.project_seen(observed, language)
        facts += [
            seen.get(key) for key in (
                "stoppedBecause", "goal", "application", "windowTitle", "firstUnreached", "gate", "gatePressed",
                "coveredBy", "seenNotDone",
            )
        ]
        facts += list(seen.get("stepsDone") or ()) + list(seen.get("stepsFailed") or ())
        facts.append(json.dumps(seen.get("screen") or {}, ensure_ascii=False))
    # Revisión 3 de r20 P5 (bloqueante 1): the kind of the stop's own cause is a fact of the stop (its code, and the
    # refined cause its steps observed), never the words of its text.
    stops = [_cu_projection.refined_stop(observed) or observed.get("stoppedBy")]
    return "invented_cause" if semantic_claims.invented_cause(text, facts, stops) else ""


def _computer_use_final_defect(text: str, situation: dict) -> str:
    """cu-r17 (live 2026-10-07): «Abrí Configuración.» said of an app every app.open of the turn found already
    running (extra_claim), and a reached mission carrying the person's question («decime el volumen») told without
    the answer the window showed (unanswered_question). "" for anything else."""

    from . import cu_projection as _cu_projection
    from . import cu_reply_checks as _cu_reply_checks
    from .semantic import mission_answer

    mission = _computer_use_mission(situation)
    observed = _merged_observed(mission) if mission is not None else {}
    if not observed:
        return ""
    seen = _cu_projection.project_seen(observed, "es")
    opened = _app_open_records(situation)
    opened += [record for record in _app_open_records(observed) if record not in opened]
    if opened and all(record.get("alreadyRunning") is True for record in opened):
        names = [seen.get("application"), seen.get("windowTitle"), observed.get("application")] + [
            value for record in opened for value in (record.get("name"), record.get("displayName"))
        ]
        if mission_answer.claims_opening(text, [name for name in names if isinstance(name, str)]):
            return "extra_claim"
    if observed.get("reached") is not True:
        if unreached := _computer_use_unreached_defect(text, observed):
            return unreached
    # Ronda 20b (pasada r18 t-long-3, «…resize the canvas to 500 by 500» over 177×500): a figure the final asserts that
    # a part asks for and no reached part sustains in the last reading (its field there, by name, holds it; revisión 1:
    # the screen alone sustains nothing, and a figure denied in its clause is no claim).
    parts = [part for part in observed.get("subgoals") or () if isinstance(part, dict)]
    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    fields = screen.get("values") if isinstance(screen.get("values"), list) else []
    if parts and semantic_claims.unsustained_figure(text, parts, _cu_reply_checks.screen_texts(seen), fields):
        return "unsustained_figure"
    question = seen.get("question")
    if isinstance(question, str) and question.strip() and seen.get("reached") is True:
        if mission_answer.says_not_seen(text):
            return ""
        raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
        screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
        known = [
            seen.get("goal"), seen.get("application"), seen.get("windowTitle"), screen.get("title"),
            *(step.get(key) for step in raw_steps if isinstance(step, dict) for key in ("label", "name")),
        ]
        shown = _cu_reply_checks.screen_texts(seen)
        states = [
            item.get("state") for item in screen.get("values") or () if isinstance(item, dict)
            and isinstance(item.get("state"), str)
        ]
        # cu-r18 (live v2-c5): the question goes apart so the option the window shows («Oscuro» for «claro u
        # oscuro») or the state it asks about («si el Bluetooth está activado») still answers it.
        if mission_answer.gives_an_answer(
            text, shown, [item for item in known if isinstance(item, str)], question, states
        ) is False:
            return "unanswered_question"
    return ""


_MISSION_CAUSES = frozenset({"mission_completed", "mission_failed"})


def _unbacked_attempt(text: str, situation: dict) -> bool:
    """v3 r5a M6: a computer-use final that tells an attempt («intenté pulsar Detalles», «I tried to click…») which no
    step of the mission made, done or failed (semantic.claims.unbacked_attempt). Judged only over a mission: with no
    step, only the cause it stopped on can be said."""

    if not isinstance(situation, dict):
        return False
    mission = semantic_claims.data()["missionOperation"]
    reason = _decoded_reason(situation)
    for record in (situation, reason):
        if not isinstance(record, dict) or str(record.get("operation") or "") != mission:
            continue
        steps = _merged_observed(record).get("steps")
        operations = [
            str(step.get("operation") or "") for step in (steps if isinstance(steps, list) else ())
            if isinstance(step, dict)
        ]
        return bool(semantic_claims.unbacked_attempt(text, operations))
    return False


def _act_ledger(situation: dict) -> frozenset[str] | None:
    """Falsos éxitos v3 M4: the acts the turn's verified operations back (semantic.claims, data/act_claims.v1.json),
    or None when the turn is not judged — no operation, one the data does not name, a single operation that failed
    (its final tells the failure; so does a mission that failed with no step but its failed reason), a single read
    (only neutral acts: the read-only check judges a change told over it, as reversed_result). A computer-use mission
    whose arrival was strong backs its goal's own verb too (semantic.claims.goal_acts). A mission backs the acts of
    the steps it did; never the request («completedRequest»), which is what was asked, not what was done. A record whose effect
    is uncertain backs its acts (they may have happened; the failure vetoes make the final hedge them), and what an
    operation observed may back more (browser.control «close_all» -> cerrar, clientOpened -> abrir)."""

    if not isinstance(situation, dict):
        return None
    cause = str(situation.get("cause") or "").strip().lower()
    records: list[dict] = [situation] if situation.get("operation") else []
    if cause in _MISSION_CAUSES:
        records.extend(_situation_steps(situation))
        reason = _decoded_reason(situation)
        if reason is not None:
            records.append(reason)
    if not records:
        return None
    mission = semantic_claims.data()["missionOperation"]
    neutral = semantic_claims.neutral_acts()
    backed: set[str] = set(neutral)
    for record in records:
        operation = str(record.get("operation") or "")
        if operation == mission:
            observed = _merged_observed(record)
            # Review r10a (finding 4, note): a strong arrival backs its goal's own verb, it does not switch the book
            # off («fui a Ajustes, borré el historial y guardé los cambios» over a strong «ir a ajustes»).
            if observed.get("reached") is True and not semantic_claims.weak_proof(observed.get("satisfiedBy")):
                backed |= semantic_claims.goal_acts(observed.get("goal"))
            for part in observed.get("subgoals") or ():
                if (
                    isinstance(part, dict) and part.get("reached") is True
                    and not semantic_claims.weak_proof(part.get("satisfiedBy"))
                ):
                    backed |= semantic_claims.goal_acts(part.get("goal"))
            backed |= (semantic_claims.operation_acts(operation) or frozenset()) | semantic_claims.observed_acts(
                operation, observed,
            )
            # Ronda 24b (banco r23 c6): an Enter aimed at a message box backs «enviar» only while the sub-goal of sending
            # did not fail on what the screen showed.
            unsent = semantic_claims.unreached_qualified_acts(observed)
            for step in observed.get("steps") or ():
                if not isinstance(step, dict) or not (step.get("ok") is True or step.get("effectUncertain") is True):
                    continue
                step_operation = str(step.get("operation") or "")
                acts = semantic_claims.operation_acts(step_operation)
                if acts is None:
                    return None
                backed |= acts | (semantic_claims.observed_acts(step_operation, step.get("observed") or step) - unsent)
            continue
        verified = record.get("verified") is True and record.get("succeeded") is True
        if not verified and (record is situation or len(records) == 1):
            # A single failure, or a mission that failed with no step but its reason (m101, effect uncertain or not):
            # its final tells the failure, and the failure vetoes judge it.
            return None
        if not verified and record.get("effectUncertain") is not True:
            continue
        acts = semantic_claims.operation_acts(operation)
        if acts is None:
            return None
        acts = acts | semantic_claims.observed_acts(operation, _merged_observed(record))
        if record is situation and len(records) == 1 and semantic_claims.acts_only_neutral(acts):
            return None
        # Ronda 22 (r18 t4-c07): a receipt that found the state already there backs no «creé/guardé/escribí».
        backed |= acts - semantic_claims.held_state_acts(_merged_observed(record))
    return frozenset(backed)


_CAPTURE_PLACE_VERB = re.compile(
    r"\b(?:guard(?:[eé]|ad[ao]|[oó])|se\s+guard[oó]|qued[oó]|saved|stored|kept)\b"
)
_CAPTURE_PLACE = re.compile(
    r"\b(?:escritorio|desktop|documentos|documents|descargas|downloads|im[aá]genes|pictures|carpeta|folder)\b"
)


def _capture_place_claimed(folded: str) -> bool:
    """H0516: a reply over a capture with no path tells a place it was saved in («se guardó en el escritorio»), a place
    the receipt does not give. «no quedó en el escritorio» is true; only the affirmation counts. Ronda 19 (r17 t3-c11
    «quedó guardada de forma privada, no en el escritorio»): a place negated within the same clause is not claimed
    either. Revisión r19 (bloqueante 5): every place of the clause is judged, not only the first, so «quedó guardada, no
    en descargas sino en el escritorio» and «quedó no solo en tu carpeta privada sino también en el escritorio» still
    claim the desktop. A verb counts, as before, only when a place starts within 40 characters of it."""

    return bool(_capture_places_claimed(folded))


def _capture_places_claimed(folded: str) -> list[str]:
    """The place words a reply over a capture affirms it was kept in (``_capture_place_claimed``), in order."""

    claimed: list[str] = []
    for verb in _CAPTURE_PLACE_VERB.finditer(folded):
        if re.search(
            r"\b(?:no|not|nunca|never|tampoco|didn't|wasn't)\b", folded[max(0, verb.start() - 14):verb.start()]
        ):
            continue
        clause = re.split(r"[.;]", folded[verb.end():], maxsplit=1)[0]
        places = list(_CAPTURE_PLACE.finditer(clause))
        if not places or places[0].start() > 40:
            continue
        claimed += [
            place.group(0) for place in places
            if re.search(
                r"\b(?:no|not|nunca|never)\s+(?:\w+\s+){0,3}$", folded[verb.start():verb.end() + place.start()]
            ) is None
        ]
    return claimed


# Revisión 2 de r22: the known folder each place word names (the catalog's capture «folder» enum).
_CAPTURE_PLACE_FOLDER = {
    "escritorio": "desktop", "desktop": "desktop", "documentos": "documents", "documents": "documents",
    "descargas": "downloads", "downloads": "downloads", "imagenes": "pictures", "imágenes": "pictures",
    "pictures": "pictures",
}
_CAPTURE_TOLD_PRIVATE = re.compile(
    r"\b(?:privad[oa]s?|privately|private|ning[uú]n\s+(?:lado|sitio|lugar)|ninguna\s+parte|anywhere|nowhere)\b"
)


def _capture_saved_place_contradicted(folded: str, saved: set[str]) -> bool:
    """Revisión 2 de r22 (bloqueante 2): over a capture the receipt says was saved in ``saved`` (savedFolder), a reply
    that affirms it kept in another known folder, or kept private / nowhere, contradicts the receipt. A place or
    privacy negated in its own clause («no quedó privada») is not affirmed."""

    if any(_CAPTURE_PLACE_FOLDER.get(word, next(iter(saved))) not in saved for word in _capture_places_claimed(folded)):
        return True
    return any(
        re.search(
            r"\b(?:no|not|nunca|never|ya\s+no|isn'?t|wasn'?t)\s+(?:\w+\s+){0,2}$",
            re.split(r"[.;:,]", folded[: match.start()])[-1],
        ) is None
        # «no la guardé en ningún lado» denies the place before it: the nowhere is what it affirms.
        or match.group(0).startswith(("ningun", "ningún", "ninguna", "anywhere", "nowhere"))
        for match in _CAPTURE_TOLD_PRIVATE.finditer(folded)
    )


def _screen_value_told_as_act(text: str, situation: dict) -> str:
    """Ronda 19 (r17 t3-c18/2 «Llegué al Programador… y elegí el modo Decimal.», t3-c19/3 «…y ahora el pincel está
    listo.», t2-c04 «He cambiado la escala a 125…»): over a verified computer-use result, the object of an act told in
    the first person, or a thing told as ready, must be a step done or the goal (semantic.claims.screen_only_object).
    Returns the word told as done that only the screen shows, or the number nothing saw; "" otherwise."""

    if not isinstance(situation, dict) or situation.get("polarity") == "failure":
        return ""
    # Revisión adversarial 3 de r19: only an act that picks its object on the screen is judged (a mission, a visible
    # click); a key pressed or a text typed acts on what the request gave, which its receipt does not carry as object.
    judged = set(semantic_claims.data()["screenObject"]["operations"]["judged"])
    records = [
        (str(record.get("operation") or ""), _merged_observed(record))
        for record in (situation, *_situation_steps(situation))
        if isinstance(record, dict) and record.get("verified") is True and record.get("succeeded") is True
    ]
    # What the turn did is every verified record's, so in a chain the app another step opened backs «Abrí el Bloc de
    # notas y hice clic en…» while the click is judged.
    done: list[object] = []
    for _operation, observed in records:
        done += [observed.get(key) for key in ("goal", "application", "name", "label", "displayName", "key", "text")]
        done += [part.get("goal") for part in observed.get("subgoals") or () if isinstance(part, dict)]
        done += [
            (step.get("label"), step.get("name"), step.get("text"), step.get("key"))
            for step in observed.get("steps") or () if isinstance(step, dict) and step.get("ok") is True
        ]
    folded_done = fold(json.dumps(done, ensure_ascii=False, default=str))
    for operation, observed in records:
        if operation not in judged:
            continue
        # Revisión r19 (bloqueante d): what was seen is the values only, not the keys nor the window's identity.
        seen = {key: value for key, value in observed.items() if key not in {"observedText", "steps", "goal"}}
        found = semantic_claims.screen_only_object(text, folded_done, semantic_claims.screen_seen(seen))
        if found:
            return found
    return ""


def _observed_text(situation: dict) -> str:
    """Every value the turn observed, folded, without the request: «completedRequest» is what was asked."""

    observed = {
        key: value for key, value in situation.items()
        if key not in {"completedRequest", "pendingRequest", "cancelledRequest", "objective", "request"}
    }
    return fold(json.dumps(observed, ensure_ascii=False, default=str).replace("\\\\", "/"))


def _unobserved_place(text: str, situation: dict) -> str:
    """Falsos éxitos v3 M4 (t-file-1 «He guardado el texto en Documentos/baxy-prueba-v3/baxy-nota1.txt.» with only the
    file's name observed and reachedState false): a path or a folder the reply names that nothing in the turn's facts
    holds came from the request, not from the PC. Returns the place, or ""."""

    if not isinstance(situation, dict) or not (situation.get("operation") or situation.get("steps")):
        return ""
    observed = _observed_text(situation)
    for place in semantic_claims.named_places(text):
        if fold(place) not in observed:
            return place
    return ""


def _without_quoted_focused_field(text: str, situation: object) -> str:
    """Revisión 1 de r24b (B3): ``text`` with the quotation of the field a computer-use mission's window had the
    keyboard in (observed focusedField, as the floor quotes it) blanked; the text unchanged otherwise."""

    mission = _computer_use_mission(situation) if isinstance(situation, dict) else None
    field = _merged_observed(mission).get("focusedField") if mission is not None else None
    if not isinstance(field, str) or not field.strip():
        return text
    return re.sub(r"[«\"“]\s*" + re.escape(field.strip()) + r"\s*[»\"”]", " ", text)


def _search_told_as_place(text: str, situation: dict) -> str:
    """Revisión 1 de r24b (B3, banco r23 x7 «Ya estamos en la pestaña de búsqueda de Spotify»): a mission part reached
    only on a focused field (cu_finals._search_opened_proof, data «computerUse.searchOpened.atoms») showed a cursor in
    a box, never a place: a draft that tells it as a place BAXY or the person is in or went to
    (semantic.claims.search_told_as_place) is refused, and the template says the search opened and where the cursor is.
    Returns the clause, or ""."""

    from . import cu_finals as _cu_finals

    mission = _computer_use_mission(situation) if isinstance(situation, dict) else None
    if mission is None or not (mission.get("verified") is True and mission.get("succeeded") is True):
        return ""
    observed = _merged_observed(mission)
    if observed.get("reached") is not True:
        return ""
    parts = [part for part in observed.get("subgoals") or () if isinstance(part, dict) and part.get("reached") is True]
    terms = [part.get("satisfiedBy") for part in parts] if parts else [observed.get("satisfiedBy")]
    proved = [term for term in terms if _cu_finals._search_opened_proof(term)]
    if not proved:
        return ""
    # The focused field's own label («focus:search» -> «search») names the search too.
    fields = [
        atom.split(":", 1)[1].strip()
        for term in proved for atom in term.split("&") if ":" in atom and _cu_finals._search_opened_proof(atom)
    ]
    # Revisión 2 de r24b (B1): the field the cursor is in (observed focusedField, quoted by the template) is no place
    # either: «estoy en «¿Qué quieres reproducir?»» tells it as one.
    focused = observed.get("focusedField")
    if isinstance(focused, str) and focused.strip():
        fields.append(focused.strip())
    return semantic_claims.search_told_as_place(text, fields)


def _unnamed_service(text: str, situation: dict) -> bool:
    """Uso real tanda 1 (t1-c01, t1-c07): what was put on in a service is told with the service («en YouTube»)."""

    if not isinstance(situation, dict) or situation.get("operation") not in semantic_claims.service_operations():
        return False
    if not (situation.get("verified") is True and situation.get("succeeded") is True):
        return False
    service = semantic_claims.service_of(situation.get("operation"), _merged_observed(situation).get("provider"))
    return bool(service) and not semantic_claims.names_the_service(text, service)


def _unstated_effect(text: str, situation: dict) -> str:
    """Falsos éxitos v3 M4 (t-form-2: «No pude hacerlo en «Bloc de notas»…» after typing «casa» and «hogar» into the
    document): a computer-use mission that did not get there says the text it left typed. Encargo H1 (tandas fin1/fin2
    t3-c02 t1: Excel was not open, the mission started it and the final said «Llegué a Excel pero no pude…»): and the
    application it started (an opening whose receipt says «alreadyRunning» false), told as opened. Returns the first
    typed text or application the reply leaves out, or ""."""

    from . import cu_vocabulary as _cu_vocabulary
    from .semantic import mission_answer

    mission = _computer_use_mission(situation) if isinstance(situation, dict) else None
    observed = _merged_observed(mission) if mission is not None else {}
    if not observed or observed.get("reached") is True or mission.get("succeeded") is True:
        return ""
    folded = fold(text)
    for step in observed.get("steps") or ():
        if not isinstance(step, dict) or step.get("ok") is not True:
            continue
        if step.get("operation") == "input.text.type":
            # The same texts the floor says (cu_finals._typed_left): a text too long to quote is not owed.
            typed = _cu_vocabulary._floor_name(step.get("text"))
            if typed and fold(typed) not in folded:
                return typed
        if step.get("operation") == "app.open" and step.get("alreadyRunning") is False:
            names = [_cu_vocabulary._floor_name(step.get(key)) for key in ("appId", "name", "displayName")]
            names += [_cu_vocabulary._floor_name(observed.get("application"))]
            names = [name for name in names if name]
            if names and not mission_answer.claims_opening(text, names):
                return names[0]
    return ""


def _reached_but_unread_report(text: str, situation: dict) -> bool:
    """v3 r5a M3 (v3-43): three honest drafts «No pude ver qué plan… está cargando» over a mission that reached its
    place died as asserted_failure. Arriving and not being able to read the answer is no failure of the mission
    (cu_finals.reached_but_unread); a draft that denies the arrival still is."""

    from . import cu_finals as _cu_finals

    mission = _computer_use_mission(situation) if isinstance(situation, dict) else None
    if mission is None or not (mission.get("verified") is True and mission.get("succeeded") is True):
        return False
    folded = _accent_folded_with_punctuation(text)
    if not _cu_finals.reached_but_unread(folded, _merged_observed(mission)):
        return False
    # Review of M3: only the unread answer is exempt. «No pude hacerlo: no se ve ningún plan.» still tells the mission
    # failed once its read failures are taken out.
    return not _asserts_failure(_cu_finals.read_failure_residue(folded))


def _computer_use_floor(situation: dict, english: bool) -> str:
    """Live 2026-10-07 (v2-v9, v2-u7, v2-w1, v2-n5, v2-e2): every draft of a computer-use final refused, the generic
    floor said «Lo hice en la aplicación «Reloj»; hay 2: «Reloj mundial».» (the steps counted as a list read) or «No pude
    hacerlo en la aplicación «Configuración».» (no cause). The mission's own floor says the place reached, or what
    could not be done and why, from the observed facts alone."""

    from . import cu_finals as _cu_finals

    mission = _computer_use_mission(situation)
    observed = _merged_observed(mission) if mission is not None else {}
    if not observed:
        return ""
    succeeded = mission.get("verified") is True and mission.get("succeeded") is True
    return _cu_finals.floor_sentence(observed, english, succeeded)


def _capture_floor_first(
    trace: str, intent: str, language: str, situation: dict, final: str, payload: dict | None = None,
) -> None:
    """Revisión 1 de la ronda 24b (B4): a final said from the facts with no draft («Listo: 25 × 4 = 100.») goes to the
    compose audit as any draft does: its payload is the mission's projected facts, the measured witness of the term that
    closed it and the numbers the facts gave it, so the judge sets what it says beside what was read."""

    if not os.environ.get("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH", "").strip():
        return
    from . import cu_projection as _cu_projection

    mission = _computer_use_mission(situation)
    observed = _merged_observed(mission) if mission is not None else {}
    payload = dict(payload or {})
    if observed:
        seen = _cu_projection.project_seen(observed, "en" if language == "en" else "es")
        payload["seen"] = seen
        screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
        # The numbers the facts gave the final: the screen's and each sub-goal's (the App's «numbers»).
        payload["numbers"] = [
            *(screen.get("numbers") or ()),
            *(number for item in observed.get("subgoals") or () if isinstance(item, dict)
              for number in item.get("numbers") or ()),
        ]
        if isinstance(observed.get("witness"), dict):
            payload["witness"] = observed["witness"]
        witnesses = [
            item.get("witness") for item in observed.get("subgoals") or ()
            if isinstance(item, dict) and isinstance(item.get("witness"), dict)
        ]
        if witnesses:
            payload["subgoalWitnesses"] = witnesses
    _capture_compose_stage(
        trace=trace, stage="floor_first", intent=intent, language=language, greeting="", payload=payload,
        raw=final, clipped=final, reason="said_from_facts", finish_reason="", published=True,
        situation=json.dumps(situation, ensure_ascii=False),
    )


def _computer_use_floor_first(situation: dict, language: str) -> str:
    """Voice audit 2026-10-07 (cu-r16): a third of the model's mission finals had a defect («Ya te llevé a la sección
    de sonido», «Abrazé a la sección de Bluetooth», «mis playlists»). A mission whose request asks nothing about the
    window is told from its facts first (cu_finals.floor_first); "" leaves it to the model."""

    from . import cu_finals as _cu_finals

    mission = _computer_use_mission(situation)
    if mission is None or str(situation.get("kind") or "") not in {"operation", "status", "failure", "error"}:
        return ""
    observed = _merged_observed(mission)
    if not observed:
        return ""
    succeeded = mission.get("verified") is True and mission.get("succeeded") is True
    return _cu_finals.floor_first(observed, language == "en", succeeded)


def _elevated_read_floor(situation: dict, language: str, said: str) -> str:
    """Pasada r15b2 (v3-22 t3 «¿cuáles tienen impacto alto?»): a look at a window that runs as administrator reads
    only its frame (Windows keeps its controls from another application; no text was read either), so no draft can
    answer from it: the turn before had said that limit, and this one drafted «las de impacto alto son aquellas que
    consumen más CPU…», a definition the window never showed, which no veto caught. The read is told as that limit,
    in the words the mission's floor says it (data: computerUse.es/en «notApp» + «cause», causes
    «computer_use_window_elevated»); "" for any other read. Review of the branch: a question about the window itself
    («¿qué ventana tengo delante?») is answered from its frame (``semantic_windows.asks_about_the_window_frame``), so it
    is drafted; telling it as the limit would be a failure that never happened."""

    if str(situation.get("kind") or "") != "operation" or situation.get("operation") != "input.visible.controls":
        return ""
    if semantic_windows.asks_about_the_window_frame(said):
        return ""
    observed = _merged_observed(situation)
    window = observed.get("window") if isinstance(observed, dict) else None
    if not isinstance(window, dict) or window.get("elevated") is not True:
        return ""
    text = observed.get("text")
    if any(line for zone in (text.values() if isinstance(text, dict) else ()) if isinstance(zone, list) for line in zone):
        return ""
    title = str(window.get("title") or "").strip()
    english = language == "en"
    cause = operation_floor.cause_clause("computer_use_window_elevated", english)
    if not title or not cause:
        return ""
    words = operation_floor.floor_data()["computerUse"]["en" if english else "es"]
    return words["cause"].format(head=words["notApp"].format(app=f"«{title}»"), cause=cause) + "."


def _unmatched_play(situation: dict) -> bool:
    return situation.get("verified") is True and semantic_claims.unmatched_play(
        situation.get("operation"), _merged_observed(situation),
    )


# The codes of an effect that may have happened (ExternalCapabilityHandlers): they name no cause, only that nothing
# confirmed it, which the floor's «intenté…, pero no pude confirmar» says.
_UNCONFIRMED_ONLY_CODES = frozenset({"external_effect_ambiguous", "external_verification_failed"})


def _claims_defect(text: str, intent: str, reported: dict) -> str:
    """Falsos éxitos v3 M4/M5 and uso real v3 tanda 1, judged after the named vetoes (a draft with one of them is told
    that one first). The book of acts: only acts a verified operation of the turn backs are told as done — the request
    (completedRequest) is what was asked; a place told is one the facts hold; what was put on in a service names the
    service; a mission that did not get there says the text it left typed; and a reply that read nothing states no
    state of this PC, nor its absence."""

    if intent in {"status", "error"} and reported.get("kind") != "conversation":
        if _unbacked_attempt(text, reported):
            # v3 r5a M6 (v3-21 «I tried to click the Details tab…» with no step): an attempt needs its step.
            return "unbacked_attempt"
        ledger = _act_ledger(reported)
        # A failure explains what happened in the third person («se presionó antes de que…»): only a success is
        # read there too («quedó creada», «se creó la escena», v3-51).
        third_person = intent == "status" and reported.get("polarity") != "failure"
        # v2-g1 (review r2 finding 1): a turn that observed its own stop may say it stopped, only of its own work.
        own_stop = any(
            isinstance(record, dict) and semantic_claims.observed_stop(_merged_observed(record))
            for record in (reported, _decoded_reason(reported))
        )
        if ledger is not None and semantic_claims.unbacked_act(text, ledger, third_person, own_stop):
            # Its own label (not extra_claim): its retry hint and the template shortcut are the book's, and the
            # older extra_claim vetoes keep their own repairs.
            return "unbacked_act"
        if _screen_value_told_as_act(text, reported):
            # Ronda 19 (r17 t3-c18/2 «…y elegí el modo Decimal», t2-c04 «He cambiado la escala a 125»): the act's
            # object must be a step done or the goal; what only the screen shows is an observation, not an act.
            return "unbacked_act"
        if _unobserved_place(text, reported):
            return "unobserved_place"
        if _search_told_as_place(text, reported):
            return "search_told_as_place"
        if _unnamed_service(text, reported):
            return "missing_place"
        if _unstated_effect(text, reported):
            return "unstated_effect"
        return ""
    if (
        (intent == "conversation" or reported.get("kind") == "conversation")
        and not any(reported.get(key) for key in ("operation", "steps", "observed", "reason"))
        and semantic_claims.claims_machine_state(text)
    ):
        return "unobserved_machine_state"
    return ""
