"""Estabilización F (orden del dueño 2026-10-11): lo que el suelo determinista sabe decir no lo redacta el modelo.

«Lo que el suelo determinista de frases sabe decir no lo redacta el modelo. Ningún final afirma algo no verificado.»
Los cuatro finales falsos medidos por el juez independiente de las tandas de la fase 1
(``cu-v3/estab_tandas_12_juicio.json``, campo ``falsos``) y el del contenido inventado de t2-c07 (corrida 2), con
sus situaciones tal como las registró ``compose_audit.jsonl``:

- t4-c03 t2 (estab2 t4, traza t10): «mandale a Ron92 que si se conecta a las 9 pa jugar» → ``message.send`` sin
  confirmar → «Se le envió a Ron92 el mensaje de que se conecte a las nueve para jugar, pero no se confirmó si lo hizo.»
- t3-c07 t1 (estab1 t3, traza t7): el mismo envío sin confirmar → «No he enviado el mensaje a ron92 en Discord porque la
  acción pendiente no se ha confirmado.»
- t2-c07 t1 (estab1 t2, traza t19): el mismo → «No pude contarte cómo salió lo que pediste.»
- t2-c18 t1 (estab2 t2, traza t30): Edge ya corría sin ventana → «…y abrí la aplicación «Microsoft Edge»…».
- t2-c07 t1 (estab2 t2, traza t19): envío verificado cuyo recibo sólo traía el hash del texto → el redactor citó
  «Llego en 10 min y llevo el cargador», un texto que nadie dio.

La App (MissionNarration.CreateUncertainEffectMessage, MindPlanBoundary.UncertainStep) ahora manda con el paso sin
confirmar sus propios hechos, y con un envío verificado el texto que su hash prueba (MindPlanBoundary.WithVerifiedContent);
los gemelos de esas situaciones están en tests/data/c03_m107_floor_twins.json («estabf-*»).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import llm, operation_floor  # noqa: E402
from baxy_mind import compose_payload
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind import deterministic_finals

TWINS = {case["id"]: case for case in json.loads(
    (ROOT / "tests" / "data" / "c03_m107_floor_twins.json").read_text(encoding="utf-8"))["cases"]}

# compose_audit.jsonl de tandas_estab2_redpc/t4, traza t10 (la situación que mandaba la App antes de este cambio).
MEASURED_UNVERIFIED = {
    "kind": "failure", "polarity": "failure", "cause": "result_unverified", "step": 2,
    "pendingRequest": "Manda a Ron92 en Discord: «si se conecta a las 9 para jugar».", "effectUncertain": True,
    "verified": False, "pending": True, "canRepeat": False, "evidenceRetained": True,
}
RESOLVED = json.dumps({
    "kind": "operation", "operation": "message.recipient.resolve", "polarity": "success", "verified": True,
    "succeeded": True, "readOnly": True,
    "observed": {"version": 1, "recipientId": "recipient_0645b6087d344fab8f92972740aae988", "channel": "discord",
                 "displayName": "Ron92", "verified": True},
})


def _unconfirmed_send(text: str, pending_request: str, *, terminal: bool = False) -> dict:
    """The facts the App sends now for a plan's message.send left unconfirmed (UncertainStep + the steps made)."""

    return {
        **MEASURED_UNVERIFIED, "pendingRequest": pending_request, "pending": not terminal, "canRepeat": terminal,
        "evidenceRetained": not terminal, "steps": [RESOLVED],
        "reason": {"kind": "operation", "operation": "message.send", "polarity": "failure", "verified": False,
                   "succeeded": False, "effectUncertain": True, "target": "Ron92", "attempted": {"text": text}},
    }


class _Writer(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time; it counts how often it was asked."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.asked = 0

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.asked += 1
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _final(said: str, situation: dict, drafts: list[str], intent: str = "error") -> tuple[str, int]:
    writer = _Writer(drafts)
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    return writer.compose_user_message(said, intent, facts), writer.asked


def _claims_the_send(final: str) -> bool:
    folded = final.lower()
    return any(word in folded for word in ("se le envi", "le envi", "envié", "he enviado", "i sent", "was sent"))


# ------------------------------------------------------------------ a step left unconfirmed


@pytest.mark.parametrize(("said", "text", "measured_draft"), [
    ("mandale a Ron92 que si se conecta a las 9 pa jugar", "si se conecta a las 9 para jugar",
     "Se le envió a Ron92 el mensaje de que se conecte a las nueve para jugar, pero no se confirmó si lo hizo."),
    ("mandale a ron92 por discord que ya voy saliendo que me espere en la entrada",
     "ya voy saliendo, espérame en la entrada",
     "No he enviado el mensaje a ron92 en Discord porque la acción pendiente no se ha confirmado."),
    ("mandale a Ron92 por discord que llego en 10 min y que lleve el cargador",
     "llego en 10 min y que lleve el cargador", "Ron92, llego en 10 minutos y trae el cargador."),
])
def test_a_send_left_unconfirmed_is_said_from_the_floor_and_never_drafted(
    said: str, text: str, measured_draft: str,
) -> None:
    situation = _unconfirmed_send(text, said)
    final, asked = _final(said, situation, [measured_draft])
    assert asked == 0
    assert final == f"Intenté enviar el mensaje a «Ron92»: «{text}», pero no pude confirmar si se hizo."
    assert not _claims_the_send(final)
    assert "No pude contarte" not in final


def test_the_measured_send_left_unconfirmed_is_the_twin_the_app_says_too() -> None:
    case = TWINS["estabf-send-unconfirmed"]
    final, asked = _final("mandale a Ron92 que si se conecta a las 9 pa jugar", case["situation"], ["Le envié."])
    assert (final, asked) == (case["es"], 0)
    final, asked = _final("tell Ron92 to hop on at 9 to play", case["situation"], ["I sent it."])
    assert (final, asked) == (case["en"], 0)


def test_a_terminal_unconfirmed_step_is_said_the_same_way() -> None:
    situation = _unconfirmed_send("si se conecta a las 9 para jugar", "mandale", terminal=True)
    assert _final("mandale a Ron92 que si se conecta a las 9 pa jugar", situation, [])[1] == 0


def test_contracase_the_old_bare_unconfirmed_step_has_no_floor_and_stays_the_writer_s() -> None:
    # No step facts (MainWindowViewModel's catch-all result_unverified): the floor names no act, so it says nothing.
    assert operation_floor.floor_final(MEASURED_UNVERIFIED, False) == ""
    assert not operation_floor.tells_first(MEASURED_UNVERIFIED)
    _final_text, asked = _final("mandale", MEASURED_UNVERIFIED, ["No pude confirmar si el mensaje llegó."])
    assert asked == 1


# ------------------------------------------------------------------ a failure of message.send


def test_a_failed_send_whose_cause_the_floor_says_is_said_from_the_floor() -> None:
    reason = {"kind": "operation", "operation": "message.send", "polarity": "failure", "verified": False,
              "succeeded": False, "error": "discord_client_not_running", "target": "Ron92",
              "attempted": {"text": "voy"}}
    situation = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
                 "reason": reason}
    final, asked = _final("mandale a Ron92 que voy", situation, ["Le envié «voy» a Ron92."])
    assert asked == 0
    assert final == "No pude enviar el mensaje a «Ron92»: «voy», porque la aplicación no estaba abierta."


def test_contracase_a_failure_whose_cause_the_floor_cannot_say_stays_the_writer_s() -> None:
    # t1-c01 t4 (estab2 t1, traza t4): media.control with nothing to pause; the cause is a fact the floor has no
    # sentence for, so the writer words it (as today).
    situation = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
                 "reason": {"kind": "operation", "operation": "media.control", "polarity": "failure",
                            "verified": False, "succeeded": False, "error": "media_session_not_found",
                            "attempted": {"action": "pause"}}}
    final, asked = _final("pausa el video", situation,
                          ["No pude pausar la reproducción: no hay nada sonando que pueda controlar."])
    assert asked == 1
    assert final == "No pude pausar la reproducción: no hay nada sonando que pueda controlar."


# ------------------------------------------------------------------ cancelled


def test_a_cancelled_plan_is_said_from_the_floor_and_never_drafted() -> None:
    situation = {
        "kind": "status", "polarity": "success", "cause": "remaining_steps_cancelled", "steps": [RESOLVED],
        "cancelledRequest": "mandale a Ron92 prueba", "cancelledAction": {
            "operation": "message.send", "purpose": "mandale a Ron92 prueba",
            "arguments": {"recipientId": "recipient_0645b6087d344fab8f92972740aae988", "text": "prueba"}},
    }
    final, asked = _final("no", situation, ["Envié el mensaje."], intent="status")
    assert asked == 0
    assert final == operation_floor.cancelled_final(situation, False)
    assert final.startswith("No llegué a enviar el mensaje")


# ------------------------------------------------------------------ already open (R11)


STEAM_OPENED = {
    "kind": "operation", "operation": "app.open", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"appId": "Steam", "displayName": "Steam", "alreadyRunning": True, "windowHandle": 3344132},
}


def test_an_app_already_running_is_said_as_already_open_and_never_drafted() -> None:
    final, asked = _final("abre steam", STEAM_OPENED, ["He abierto Steam."], intent="status")
    assert (final, asked) == ("La aplicación «Steam» ya estaba abierta.", 0)
    final, asked = _final("open steam", STEAM_OPENED, ["I opened Steam."], intent="status")
    assert (final, asked) == ("The app «Steam» was already open.", 0)
    assert TWINS["estabf-open-already-running"]["es"] == "La aplicación «Microsoft Edge» ya estaba abierta."


def test_contracase_an_app_launched_now_is_still_the_writer_s() -> None:
    launched = {**STEAM_OPENED, "observed": {**STEAM_OPENED["observed"], "alreadyRunning": False}}
    final, asked = _final("abre steam", launched, ["Abrí Steam."], intent="status")
    assert (final, asked) == ("Abrí Steam.", 1)


def test_t2_c18_edge_running_without_a_window_is_never_told_as_opened() -> None:
    case = TWINS["estabf-place-edge-running-without-window"]
    drafts = [
        "No se pudo colocar Word y Edge uno al lado del otro porque Edge no tenía ventana abierta para moverla.",
        "No se pudo poner Word y Edge uno al lado del otro porque Edge no tenía ninguna ventana abierta en ese momento.",
    ]
    final, _asked = _final("pon el word y el edge uno al lado del otro", case["situation"], drafts)
    assert "abrí la aplicación «Microsoft Edge»" not in final
    assert final == case["es"]
    assert "«Microsoft Edge» ya estaba abierta" in final


# ------------------------------------------------------------------ verified content (t2-c07, corrida 2)


MEASURED_SENT = {
    "kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
    "steps": [RESOLVED, json.dumps({
        "kind": "operation", "operation": "message.send", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "messageId": "message_242d96c386a4988c176a8747",
                     "recipientId": "recipient_0645b6087d344fab8f92972740aae988", "channel": "discord",
                     "displayName": "Ron92",
                     "contentSha256": "d2feab60cbfabf2d27df2319d96861b67d421fd7e063b801fdd433f25297a249",
                     "delivery": "visible_postcondition"},
        "readOnly": False})],
    "completedRequest": "mandale a Ron92 por discord que llego en 10 min y que lleve el cargador",
}
SAID_SENT = "mandale a Ron92 por discord que llego en 10 min y que lleve el cargador"
INVENTED = 'Le envié el mensaje a Ron92 en Discord diciendo: "Llego en 10 min y llevo el cargador".'


def test_a_send_verified_with_its_text_is_said_from_the_floor_with_that_text() -> None:
    case = TWINS["estabf-send-verified-with-its-text"]
    final, asked = _final(SAID_SENT, case["situation"], [INVENTED], intent="status")
    assert (final, asked) == (
        "Envié el mensaje a «Ron92» en Discord: dice «llego en 10 min y que lleve el cargador».", 0)


def test_a_quote_no_fact_gave_is_refused_and_the_measured_receipt_is_said_without_a_text() -> None:
    # The receipt as it was measured (only the hash): the made-up quote is refused, and since revisión F (H4) the
    # floor says the verified send without any text, before any draft.
    payload = compose_payload._compose_situation_payload(MEASURED_SENT, "es", SAID_SENT)
    assert payload_fact_checks._payload_fact_defect(INVENTED, payload, SAID_SENT) == "unsourced_quote"
    assert operation_floor.tells_first(MEASURED_SENT)
    final, asked = _final(SAID_SENT, MEASURED_SENT, [INVENTED, "Le envié el mensaje a Ron92 en Discord."],
                          intent="status")
    assert (final, asked) == ("Envié el mensaje a «Ron92» en Discord.", 0)


def test_contracase_a_quote_the_facts_or_the_person_wrote_passes() -> None:
    payload = compose_payload._compose_situation_payload(MEASURED_SENT, "es", SAID_SENT)
    assert payload_fact_checks._payload_fact_defect(
        "Le envié a Ron92 «llego en 10 min y que lleve el cargador».", payload, SAID_SENT) != "unsourced_quote"
    # One quoted word is a name, not a content told.
    assert payload_fact_checks._payload_fact_defect("Le envié el mensaje a «Ron92».", payload, SAID_SENT) != "unsourced_quote"
    # A turn with no operation quotes freely (a conversation).
    assert not deterministic_finals._quotes_what_it_was_not_given('Como dijo Hamlet, "ser o no ser".', {"kind": "conversation"}, "", None)


# ------------------------------------------------------------------ a state that already held (M69)


def test_an_asked_state_already_held_is_said_from_the_floor() -> None:
    situation = {"kind": "operation", "operation": "audio.microphone.mute", "polarity": "failure",
                 "verified": False, "succeeded": False, "error": "microphone_already_muted"}
    final, asked = _final("silencia mi micrófono", situation, ["Intenté silenciarlo, pero no hubo cambios."])
    assert asked == 0
    assert final == operation_floor.failure_sentences()["microphone_already_muted"][0]


# ------------------------------------------------------------------ contracases: what stays the writer's


def test_contracase_a_verified_success_is_drafted_as_today() -> None:
    snapped = {"kind": "operation", "operation": "window.snap", "polarity": "success", "verified": True,
               "succeeded": True, "observed": {"version": 1, "side": "left",
                                               "window": {"title": "Documento1 - Word", "processName": "WINWORD"}}}
    assert not operation_floor.tells_first(snapped)
    final, asked = _final("pon el word a la izquierda", snapped, ["Puse Word a la izquierda."], intent="status")
    assert (final, asked) == ("Puse Word a la izquierda.", 1)


def test_contracase_a_conversation_with_no_operation_does_not_change() -> None:
    talk = {"kind": "conversation", "polarity": "success"}
    assert not operation_floor.tells_first(talk)
    final, asked = _final("hola, ¿cómo estás?", talk, ["Bien, ¿y tú?"], intent="conversation")
    assert (final, asked) == ("Bien, ¿y tú?", 1)


def test_contracase_a_confirmation_still_owed_is_never_told() -> None:
    pending = {"kind": "operation", "operation": "message.send", "polarity": "pending", "verified": False,
               "succeeded": False}
    assert not operation_floor.tells_first(pending)


# ------------------------------------------------------------------ revisión F


GOOGLE_OPENED = {
    "kind": "operation", "operation": "browser.navigate", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"version": 1, "url": "https://www.google.com/search?q=Rayuela+pel%C3%ADcula", "title": "Google"},
}


def test_h1_a_query_read_inside_its_url_is_no_unsourced_quote() -> None:
    # t4-c02 t4: the draft published at the first try quoted the query the URL carries percent-encoded.
    payload = compose_payload._compose_situation_payload(GOOGLE_OPENED, "es", "buscalo en google asi veo el trailer")
    draft = "He abierto en Google la búsqueda de «Rayuela película»."
    assert payload_fact_checks._payload_fact_defect(draft, payload, "buscalo en google asi veo el trailer") != "unsourced_quote"
    assert deterministic_finals._quotes_what_it_was_not_given(
        "Abrí en Google «la explicación de la segunda causa»", {"operation": "browser.navigate", "observed": {
            "url": "https://www.google.com/search?q=la+explicaci%C3%B3n+de+la+segunda+causa"}}, "buscalo", None,
    ) is False


@pytest.mark.parametrize(("situation", "draft", "said"), [
    (STEAM_OPENED, "Abrí Steam.", "no, ábrelo"),
    (STEAM_OPENED, "Listo, abrí Steam de nuevo.", "ábrelo otra vez"),
    ({"kind": "operation", "operation": "audio.microphone.mute", "polarity": "failure", "verified": False,
      "succeeded": False, "error": "microphone_already_unmuted"},
     "El micrófono ya estaba activo, por lo que no hubo cambios al intentar silenciarlo.", "que lo actives te dije"),
])
def test_h2_a_correction_over_what_the_floor_says_is_never_handed_to_the_writer(
    situation: dict, draft: str, said: str,
) -> None:
    first = deterministic_finals._floor_first_final(situation, {}, said, "es")
    corrected = {**situation, "correctedFinal": {"previousReply": first}}
    final, asked = _final(said, corrected, [draft, draft, draft], intent="status")
    assert asked == 0
    assert final == operation_floor.again(first, False)
    assert "abrí" not in final.lower() and "intent" not in final.lower()


def test_h3_only_the_app_the_plan_found_running_may_be_told_open() -> None:
    opened = json.dumps({"kind": "operation", "operation": "app.open", "polarity": "success", "verified": True,
                         "succeeded": True, "observed": {"displayName": "Discord", "alreadyRunning": True}})
    situation = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 2,
                 "steps": [opened, RESOLVED],
                 "reason": {"kind": "operation", "operation": "message.send", "polarity": "failure",
                            "verified": False, "succeeded": False, "error": "message_delivery_not_verified"}}
    facts = {"situation": json.dumps(situation)}
    for invented in ("Abrí Discord y dejé abierta la conversación con Ron92, pero no pude enviar el mensaje.",
                     "No pude enviar el mensaje, pero el chat quedó abierto con el texto escrito."):
        assert visible_defect.compose_visible_defect(invented, "error", "mandale hola a Ron92", facts) == "reversed_polarity"
    told = "La aplicación «Discord» ya estaba abierta, pero no pude enviar el mensaje."
    assert visible_defect.compose_visible_defect(told, "error", "mandale hola a Ron92", facts) != "reversed_polarity"


def test_h4_a_text_the_floor_cannot_quote_is_said_without_any_text() -> None:
    case = TWINS["estabf-send-verified-text-unquotable"]
    final, asked = _final("mandale a Ron92 que llego en 10", case["situation"],
                          ["Le envié a Ron92: «Llego en 10 minutos».", "Le envié a Ron92 que llegas en 10 minutos."],
                          intent="status")
    assert (final, asked) == ("Envié el mensaje a «Ron92» en Discord.", 0)
    payload = compose_payload._compose_situation_payload(MEASURED_SENT, "es", SAID_SENT)
    assert payload_fact_checks._payload_fact_defect("Le envié a Ron92 'llego en diez minutitos'.", payload, SAID_SENT) == (
        "unsourced_quote")
    assert payload_fact_checks._payload_fact_defect("I couldn't say it's sent.", payload, SAID_SENT) != "unsourced_quote"


def test_h5_the_floor_keeps_what_was_observed() -> None:
    assert TWINS["estabf-brightness-uncertain"]["es"] == (
        "Intenté poner el brillo: 30 %, pero no pude confirmar si se hizo.")
    assert TWINS["brightness-already-at-level"]["es"] == "El brillo ya estaba al 40 %."
    assert TWINS["estabf-send-verified-text-unquotable"]["es"] == "Envié el mensaje a «Ron92» en Discord."
    cotele = {"operation": "input.visible.click", "arguments": {"label": "Cotele!!!😎, Canal de voz, Choche"}}
    cancelled = {"kind": "status", "polarity": "success", "cause": "remaining_steps_cancelled", "steps": [],
                 "cancelledAction": cotele}
    assert "Canal de voz" not in operation_floor.cancelled_final(cancelled, False)
