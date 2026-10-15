"""Encargo IMP2: los imprescindibles que fallaron en vivo (corrida imp1, notebook, 2026-10-12 00:47, fase3 7f42014ad;
juez cu-v3/imp1_juez.json) y dos del banco fix1/fix2.

- imp-dc-leer: con el MD de Ron92 ya abierto, la regla de ir al lugar pulsó el botón «Ron92» de la cabecera, que abrió su
  perfil encima de la conversación. Una lectura donde el chat ya está se hace sin actuar (cu_chats.read_in_place).
- imp-dc-salir-voz: sin llamada, la misión hizo un clic que no encontró «desconectar», un scroll y paró con «la pantalla
  dejó de cambiar». Ahora, tras ese clic que no encontró el control, dice que no hay llamada (cu_chats.call_not_found).
- imp-wa-abrir / imp-wa-leer: «musica» escrito en la búsqueda de chats y Escape 550 ms después; el resultado «Música»
  llegó bajo ese Escape (medido en redpc: 750-880 ms tras el texto). Ahora se mira otra vez antes de cerrar la búsqueda
  (código search_pending; la App espera y marca «awaited»).
- imp-wa-enviar: «Intenté enviar…, pero no pude confirmar si se hizo» sobre una búsqueda de contacto que falló antes de
  enviar nada. Lo no hecho se dice no hecho, con la causa de su familia.
- c6 (banco fix1): Discord en la página de un canal de un servidor no muestra el chat ni el buscador de conversaciones;
  el lugar donde Discord lista sus chats tiene dirección (app_places «chats»).
- g1 (banco fix2): el final del límite «…pero lo que sigue no lo puedo hacer…» no llevaba «no puedo» seguido y la App lo
  refutó como resultado invertido; ahora «no puedo hacer lo que sigue».
"""

from __future__ import annotations

from baxy_mind import computer_use as cu
from baxy_mind import cu_finals, cu_model_calls, deterministic_finals, operation_floor
from baxy_mind.cu_chats import CALL_NOT_FOUND, call_not_found, read_in_place
from baxy_mind.cu_lookup import SEARCH_PENDING
from baxy_mind.semantic import app_places, chats
from baxy_mind.semantic.limits import LIMIT_CODE

NAMES = ["Discord", "WhatsApp", "Steam", "Bloc de notas"]
READ = "en Discord leé lo último que me escribió Ron92"
QUESTION = "leé lo último que me escribió Ron92"
LEAVE = "en Discord salí del canal de voz"

# The live look of imp-dc-leer before its first step (journal of imp1, 03:53:59), with the message entries of the DM as
# Discord's tree names them (measured on redpc 2026-10-12: «autor Etiqueta del servidor: X , texto , hora»).
_DM_ENTRIES = [
    "RED Etiqueta del servidor: DEMO , prueba BAXY G1 , 12:41 p. m.",
    "RED Etiqueta del servidor: DEMO , prueba BAXY C6 , ayer a las 01:12 p. m.",
    "RED Etiqueta del servidor: DEMO , prueba BAXY C6 , 01:17 a. m.",
]


def _dm_view(entries: list[str] | None = None, title: str = "@Ron92 - Discord") -> dict:
    controls = [
        {"i": 0, "kind": "Document", "name": "@Ron92", "state": "readonly focused",
         "value": "https://discord.com/channels/@me/788990433829060618"},
        {"i": 1, "kind": "TreeItem", "name": "Mensajes directos", "state": "selected"},
        {"i": 2, "kind": "Button", "name": "Silenciar", "state": "on"},
        {"i": 3, "kind": "Edit", "name": "Mensaje @Ron92"},
        {"i": 4, "kind": "Button", "name": "Ron92"},
        {"i": 5, "kind": "Button", "name": "Ron92 .wolfsoultm.4191"},
        {"i": 6, "kind": "Hyperlink", "name": "Ron92 (mensaje directo)",
         "value": "https://discord.com/channels/@me/788990433829060618"},
        {"i": 7, "kind": "Hyperlink", "name": "Amigos", "value": "https://discord.com/channels/@me"},
    ]
    controls += [{"i": 8 + n, "kind": "Group", "name": name} for n, name in enumerate(entries or [])]
    return {"window": {"title": title, "process": "Discord", "foreground": True}, "controls": controls}


def _decide(objective: str, goal: str, application: str, view: dict, history: list[dict] | None = None,
            success_check: str | None = None) -> dict:
    return cu._decide_step(
        None, objective=objective, goal=goal, application=application, success_check=success_check, view=view,
        history=history or [], budget_left=8, application_names=NAMES, subgoal=0, subgoal_count=1,
        translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )


# ---------------------------------------------------------------------------------------------------- imp-dc-leer

def test_a_reading_where_the_chat_already_is_takes_no_act() -> None:
    goal = f"ir a ron92{operation_floor.floor_data()['computerUse']['questionMark']}{QUESTION}"
    decision = _decide(READ, goal, "Discord", _dm_view(_DM_ENTRIES), success_check="title:ron92")
    assert decision["operation"] == "done"
    assert decision["arguments"]["evidence"] == _DM_ENTRIES[-1]


def test_the_reading_with_no_entry_in_the_view_cites_the_chat_and_still_takes_no_act() -> None:
    decision = read_in_place(QUESTION, _dm_view(), [])
    assert decision is not None and decision["operation"] == "done"
    assert decision["arguments"]["evidence"] == "@Ron92 - Discord"


def test_the_last_entries_all_the_persons_own_say_none_of_ron92() -> None:
    seen = {"question": QUESTION, "reached": True, "messages": list(_DM_ENTRIES)}
    assert cu_finals.question_answer(seen, english=False) == "En lo que muestra el chat no hay mensajes de Ron92."


def test_contracase_the_chat_not_open_yet_is_gone_to() -> None:
    # On the Friends page the chat is not the window's yet: no reading there, the step goes to the chat.
    view = _dm_view(title="Amigos - Discord")
    assert read_in_place(QUESTION, view, []) is None
    # After an act of the sub-goal the shell's own check decides; and a question about something else is no reading.
    assert read_in_place(QUESTION, _dm_view(_DM_ENTRIES), [{"operation": "input.visible.click", "ok": True}]) is None
    assert read_in_place("decime qué plan está activo", _dm_view(_DM_ENTRIES), []) is None


# ----------------------------------------------------------------------------------------------- imp-dc-salir-voz

def _channel_page(*extra: dict) -> dict:
    # The look of imp-dc-salir-voz (imp1): the voice channel's page, no call («Unirse al chat de voz»).
    return {
        "window": {"title": "Cotele!!!😎 | Choche - Discord", "process": "Discord", "foreground": True},
        "controls": [
            {"i": 0, "kind": "Document", "name": "Cotele!!!😎 | Choche",
             "value": "https://discord.com/channels/722182464918781984/777626597033115689"},
            {"i": 1, "kind": "Button", "name": "Unirse al chat de voz"},
            {"i": 2, "kind": "Button", "name": "Silenciar", "state": "on"},
            {"i": 3, "kind": "Button", "name": "Ensordecer", "state": "on"},
            {"i": 4, "kind": "Hyperlink", "name": "general (canal de texto)"},
            *extra,
        ],
    }


_NOT_FOUND = {"step": 1, "operation": "input.visible.click", "source": "model", "label": "desconectar", "ok": False,
              "error": "visible_button_not_found"}


def test_no_call_to_leave_is_said_after_its_control_was_not_found() -> None:
    goal = chats.leave_call_goal()
    decision = _decide(LEAVE, goal, "Discord", _channel_page(), [_NOT_FOUND])
    assert decision["operation"] == "none" and decision["code"] == LIMIT_CODE + CALL_NOT_FOUND
    observed = {"goal": goal, "application": "Discord", "reached": False, "steps": [_NOT_FOUND],
                "stoppedBy": "computer_use_limit_" + CALL_NOT_FOUND}
    assert cu_finals.limit_final(observed, english=False) == (
        "No estás en ningún canal de voz ni llamada, así que no pulsé nada.")
    assert cu_finals.limit_final(observed, english=True) == (
        "You're not in any voice channel or call, so I pressed nothing.")


def test_contracase_a_call_on_screen_or_no_click_yet_is_no_absence() -> None:
    goal = chats.leave_call_goal()
    assert call_not_found(goal, _channel_page({"i": 9, "kind": "Button", "name": "Desconectar"}), [_NOT_FOUND]) is None
    assert call_not_found(goal, _channel_page(), []) is None
    assert call_not_found(goal, {**_channel_page(), "partial": True}, [_NOT_FOUND]) is None
    assert call_not_found("hacer clic en unirse al chat de voz", _channel_page(), [_NOT_FOUND]) is None
    assert call_not_found(goal, _channel_page(), [{**_NOT_FOUND, "error": "input_user_interrupted"}]) is None


def test_the_leave_goal_is_one_and_the_same_for_the_reader_and_the_step() -> None:
    from baxy_mind.semantic import missions

    assert missions.going_to("x") is not None
    read = missions._read_act(missions.fold("sali del canal de voz"))
    assert read is not None and read[0] == chats.leave_call_goal()


# ------------------------------------------------------------------------------------------ imp-wa-abrir / leer

def _wa_view(*extra: dict) -> dict:
    # The look of imp-wa-abrir right after «musica» was typed (imp1 journal, 03:57:06.886): the search holds the text
    # and the list still shows the chats from before.
    return {
        "window": {"title": "(5) WhatsApp", "process": "msedgewebview2", "foreground": True,
                   "focused": {"kind": "Edit", "name": "WhatsApp", "value": "musica"}},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Chats", "state": "on"},
            {"i": 1, "kind": "Edit", "name": "WhatsApp", "state": "focused", "value": "musica"},
            {"i": 2, "kind": "TabItem", "name": "Todos", "state": "selected"},
            {"i": 3, "kind": "DataItem", "name": "Contacto A 💕 0:52"},
            {"i": 4, "kind": "DataItem", "name": "15 mensajes no leídos Juanito Ayer"},
            {"i": 5, "kind": "Button", "name": "Archivado", "state": "off"},
            *extra,
        ],
    }


_TYPED = [
    {"step": 1, "operation": "input.visible.click", "source": "model", "label": "Buscar un chat o iniciar uno nuevo",
     "ok": True, "kind": "Edit", "focused": True},
    {"step": 2, "operation": "input.text.type", "source": "model", "into": "Buscar un chat o iniciar uno nuevo",
     "text": "musica", "ok": True, "changed": True, "query": True},
]


def test_a_search_whose_results_are_not_drawn_is_looked_at_again_before_closing() -> None:
    decision = _decide("en WhatsApp abrí el chat Música", "ir a musica", "WhatsApp", _wa_view(), [dict(s) for s in _TYPED])
    assert decision["operation"] == "none" and decision["code"] == SEARCH_PENDING


def test_after_the_wait_the_result_drawn_is_pressed() -> None:
    history = [dict(s) for s in _TYPED]
    history[-1]["awaited"] = True
    view = _wa_view({"i": 6, "kind": "DataItem", "name": "Música 29/9/2026 Tú : . Chat silenciado Archivado"},
                    {"i": 7, "kind": "DataItem", "name": "Música 29/9/2026"})
    decision = _decide("en WhatsApp abrí el chat Música", "ir a musica", "WhatsApp", view, history)
    assert decision["operation"] == "input.visible.click"
    assert "Música" in str(decision["arguments"].get("label"))


def test_contracase_a_text_not_typed_into_a_search_box_is_never_awaited() -> None:
    # Encargo TZ-WA2: going to a WhatsApp chat is cu_chats.chat_search_step, which types only the chat's name and only
    # into the chat search (data app_places «chatSearch»); the wait follows that text. A text typed elsewhere in the
    # sub-goal (not the chat's name: a message into the composer) is never awaited. (Before: the «query» flag of the
    # generic search, which this sub-goal no longer takes.)
    history = [dict(s) for s in _TYPED]
    history[-1] = {**history[-1], "text": "hola", "into": "Escribir un mensaje para Juanito"}
    del history[-1]["query"]
    decision = _decide("en WhatsApp abrí el chat Música", "ir a musica", "WhatsApp", _wa_view(), history)
    assert decision.get("code") != SEARCH_PENDING


def test_contracase_after_the_wait_with_nothing_drawn_the_chat_is_not_found() -> None:
    # Encargo TZ-WA2 (banco zu2, zu3: after the search, Escape and the other ways ended on «Nuevo chat» and on the
    # «No leídos» filter, left on for the cases after): the chat search that holds the name and shows no entry of that
    # chat after the wait says the chat was not found; nothing else is pressed. (Before: Escape, then the next way.)
    history = [dict(s) for s in _TYPED]
    history[-1]["awaited"] = True
    decision = _decide("en WhatsApp abrí el chat Música", "ir a musica", "WhatsApp", _wa_view(), history)
    assert decision["operation"] == "none" and decision["code"] == "no_step_visible"


# ------------------------------------------------------------------------------------------------- imp-wa-enviar

_RESOLVE_FAILED = {
    "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
    "reason": {"kind": "operation", "operation": "message.recipient.resolve", "polarity": "failure", "verified": False,
               "succeeded": False, "error": "search_focus_not_verified", "cause": "external_effect_ambiguous",
               "effectUncertain": True, "target": "Música", "attempted": {"channel": "whatsapp", "recipient": "Música"},
               "notDone": [{"operation": "message.send", "target": "Música"}]},
}


def test_a_send_never_reached_is_said_not_done_with_its_cause() -> None:
    said = deterministic_finals._floor_first_final(_RESOLVE_FAILED, {}, 'en WhatsApp mandale a Música "prueba BAXY imp"', "es")
    assert said == ("No pude enviar el mensaje a «Música», porque el buscador de chats no tomó el nombre, así que no "
                    "abrí el chat ni envié nada.")
    assert "Intenté" not in said and "confirmar" not in said


def test_contracase_an_uncertain_send_keeps_its_own_but() -> None:
    sent = {"kind": "operation", "operation": "message.send", "polarity": "failure", "verified": False,
            "succeeded": False, "error": "message_draft_not_verified", "effectUncertain": True, "target": "Música"}
    assert operation_floor.floor_final(sent, False).startswith("Intenté enviar el mensaje")


# ------------------------------------------------------------------------------------------------------- c6 Discord

def _server_page() -> dict:
    # The look of c6 (banco fix1, 04:08:05): a voice channel's page of a server; no chat with Ron92, no search of chats.
    return {
        "window": {"title": "Cotele!!!😎 | Choche - Discord", "process": "Discord", "foreground": True},
        "controls": [
            {"i": 0, "kind": "Document", "name": "Cotele!!!😎 | Choche",
             "value": "https://discord.com/channels/722182464918781984/777626597033115689"},
            {"i": 1, "kind": "TreeItem", "name": "Mensajes directos"},
            {"i": 2, "kind": "Hyperlink", "name": "general (canal de texto)"},
            {"i": 3, "kind": "Button", "name": "Unirse al chat de voz"},
        ],
    }


C6 = 'en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo'


def test_a_chat_the_window_does_not_show_is_gone_to_from_where_the_chats_are() -> None:
    decision = _decide(C6, "ir a ron92", "Discord", _server_page(), success_check="title:ron92")
    assert decision["operation"] == "app.open"
    assert decision["arguments"]["place"] == "directs"
    assert app_places.chats_place("Discord", "ir a ron92") == ("directs", "ron92")


def test_contracase_from_the_direct_messages_the_chat_is_pressed_and_never_opened_by_address() -> None:
    view = _dm_view(title="Amigos - Discord")
    decision = _decide(C6, "ir a ron92", "Discord", view, success_check="title:ron92")
    assert decision["operation"] != "app.open"
    # Opened once: the sub-goal goes on with the window.
    opened = [{"step": 1, "operation": "app.open", "place": "directs", "ok": True}]
    assert _decide(C6, "ir a ron92", "Discord", _server_page(), opened, success_check="title:ron92")["operation"] != "app.open"
    # A declared place is its own address, and an application with no «chats» gets none.
    assert app_places.chats_place("Discord", "ir a mensajes directos") is None
    assert app_places.chats_place("Steam", "ir a ron92") is None


# ------------------------------------------------------------------------------- imp-wa-enviar: the send is a mission

WA_SEND = 'en WhatsApp mandale a Música "prueba BAXY imp"'


def test_a_whatsapp_send_is_the_chain_that_sends_in_discord() -> None:
    from baxy_mind.semantic import missions

    mission = missions.mission_request(WA_SEND, NAMES)
    assert mission is not None
    assert [step["goal"] for step in mission.arguments()["steps"]] == [
        "ir a musica", "escribir prueba BAXY imp", "enviar"]
    assert mission.arguments()["steps"][2]["successCheck"] == "stepDone:input.key.press:enter&sent:prueba BAXY imp"
    # Said with the client after it, the same chain.
    after = missions.send_in_place('mandale a Música "prueba BAXY imp" en WhatsApp', NAMES)
    assert after is not None and after.arguments()["steps"] == mission.arguments()["steps"]


def test_the_whatsapp_send_turn_is_the_mission_and_discords_keeps_its_typed_send() -> None:
    from test_estab_imp_mensajeria import _whole_turn

    assert _whole_turn(WA_SEND)["operation"] == "mission.computer.use"
    # Contracase: Discord's send is not in the data («sendInPlace»): its typed route (s14, c6 typed) is unchanged.
    discord = _whole_turn('en Discord mandale a Ron92 "prueba BAXY 14"')
    assert discord["effectOperations"] == ["message.recipient.resolve", "message.send"]
    from baxy_mind.semantic import missions

    assert missions.send_in_place('en Discord mandale a Ron92 "hola"', NAMES) is None
    assert missions.send_in_place("en WhatsApp leé lo último que me escribieron en Música", NAMES) is None
    # A text written in a place of the window is no message to someone (tests/test_cu_v3_texto_webview.py wa-1).
    assert missions.send_in_place("en WhatsApp escribí BaxyPrueba en el buscador de chats", NAMES) is None


# ------------------------------------------------------- imp2 imp-wa-leer / -enviar: the search kept from the turn before

def _wa_kept_search() -> dict:
    # The first look of imp2 imp-wa-leer (journal 06:09:12): the chat search still holds «musica» and lists its results.
    return {
        "window": {"title": "(5) WhatsApp", "process": "msedgewebview2", "requested": True,
                   "focused": {"kind": "Document", "name": "(5) WhatsApp"}},
        "controls": [
            {"i": 0, "kind": "Document", "name": "(5) WhatsApp", "state": "readonly focused"},
            {"i": 1, "kind": "Button", "name": "Chats", "state": "on"},
            {"i": 2, "kind": "Edit", "name": "WhatsApp", "value": "musica"},
            {"i": 3, "kind": "TabItem", "name": "Todos", "state": "selected"},
            {"i": 4, "kind": "DataItem", "name": "Música 29/9/2026 Tú : . Chat silenciado Archivado"},
            {"i": 5, "kind": "DataItem", "name": "Música 29/9/2026"},
            {"i": 6, "kind": "DataItem", "name": "Juanito 29/9/2026 pasame esa musica"},
            {"i": 7, "kind": "DataItem", "name": "Contacto B 18/9/2026 Tú : Música"},
            {"i": 8, "kind": "DataItem", "name": "Música 26/6/2026 Tú : hola a musica"},
            {"i": 9, "kind": "Button", "name": "Archivado", "state": "off"},
        ],
    }


def test_a_search_left_holding_the_name_has_its_result_pressed() -> None:
    decision = _decide("en WhatsApp leé lo último que me escribieron en Música", "ir a musica", "WhatsApp",
                       _wa_kept_search(), success_check="control:musica:current|title:musica|page:musica|mark:musica")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Música 29/9/2026"


def test_contracase_a_search_holding_another_text_is_not_read_as_the_places() -> None:
    view = _wa_kept_search()
    view["controls"][2]["value"] = "juanito"
    decision = _decide("en WhatsApp leé lo último que me escribieron en Música", "ir a musica", "WhatsApp", view,
                       success_check="control:musica:current|title:musica|page:musica|mark:musica")
    assert not (decision["operation"] == "input.visible.click" and "Juanito" in str(decision["arguments"].get("label")))


# ------------------------------------------- imp3 imp-wa-leer: a chat without an accessible tree, read from its lines

from baxy_mind import cu_chat_lines  # noqa: E402

# The geometry of the open group read on redpc (2026-10-12, msedgewebview2 drawn by itself, 1920×1044; three identical
# reads), in fractions of the window, with neutral texts: the person's bubbles start right of the centre and end with
# their time and read marks («u»); dates sit centred.
_OWN = [
    {"text": "ya voy", "x": 0.9125, "y": 0.1217, "w": 0.0208, "h": 0.0153},
    {"text": "19:14 u", "x": 0.9365, "y": 0.1274, "w": 0.0224, "h": 0.0105},
    {"text": "prueba uno de la mañana", "x": 0.7885, "y": 0.3946, "w": 0.1422, "h": 0.0153},
    {"text": "19:55 u", "x": 0.9365, "y": 0.4004, "w": 0.0224, "h": 0.0105},
    {"text": "20/9/2026", "x": 0.5984, "y": 0.6092, "w": 0.0297, "h": 0.0105},
    {"text": "otra prueba", "x": 0.8823, "y": 0.8688, "w": 0.0578, "h": 0.0153},
    {"text": "4:35 u", "x": 0.9417, "y": 0.8774, "w": 0.0193, "h": 0.0105},
]
_THEIRS = [
    {"text": "nos vemos a las nueve", "x": 0.262, "y": 0.70, "w": 0.11, "h": 0.0153},
    {"text": "21:10", "x": 0.38, "y": 0.706, "w": 0.02, "h": 0.0105},
]
_LIST = [{"text": "Música 4:36", "x": 0.04, "y": 0.2, "w": 0.1, "h": 0.015}]  # the chat list, outside the region
_READ = "en WhatsApp leé lo último que me escribieron en Música"


def _seen(lines: list[dict], question: str = "leé lo último que me escribieron en Música") -> dict:
    return {"question": question, "reached": True, "application": "WhatsApp", "chatLines": lines, "messages": []}


def test_every_bubble_the_persons_own_is_said_so() -> None:
    assert cu_finals.question_answer(_seen(_LIST + _OWN), english=False) == (
        "En lo que muestra el chat, lo último es tuyo: no hay mensajes de otra persona.")


def test_the_last_bubble_not_the_persons_own_is_quoted_with_its_time() -> None:
    assert cu_finals.question_answer(_seen(_LIST + _OWN + _THEIRS), english=False) == (
        "Lo último que te escribieron fue «nos vemos a las nueve» (21:10).")


def test_a_group_bubble_names_who_wrote_it_only_when_asked_about_that_person() -> None:
    signed = [{"text": "Juanito", "x": 0.262, "y": 0.69, "w": 0.03, "h": 0.0153}] + _THEIRS
    asked = "leé lo último que me escribió Juanito"
    assert cu_finals.question_answer(_seen(_OWN + signed, asked), english=False).startswith(
        "Lo último que te escribió Juanito fue «Juanito nos vemos a las nueve»")
    # Contracase: a bubble not signed by who was asked, in a group named otherwise, is not attributed.
    seen = _seen(_OWN + _THEIRS, "leé lo último que me escribió Juanito en Música")
    assert cu_chat_lines.last_written(seen["chatLines"], app_places.conversation("WhatsApp")) is not None


def test_contracase_no_line_in_the_conversation_says_nothing_read() -> None:
    # Encargo WR: said by the floor, no longer left to a draft over the window's lines (which quoted «Borrar todo»).
    assert cu_finals.question_answer(_seen(_LIST), english=False) == (
        "En lo que muestra el chat no pude leer ningún mensaje de otra persona.")
    # An application with no conversation in its data (Discord reads its tree) keeps its own answer.
    assert cu_finals.question_answer({**_seen(_OWN), "application": "Discord"}, english=False) == ""


def test_a_result_pressed_is_given_a_moment_before_another_is_pressed() -> None:
    # imp3 imp-wa-leer: «Música 29/9/2026» pressed, the look 700 ms later still the list: «Juanito … musica» came next.
    pressed = [{"step": 1, "operation": "input.visible.click", "ok": True, "label": "Música 29/9/2026", "kind": "DataItem",
                "surfaceChanged": True}]
    decision = _decide(_READ, "ir a musica", "WhatsApp", _wa_kept_search(), pressed,
                       success_check="control:musica:current|title:musica|page:musica|mark:musica")
    assert decision["operation"] == "none" and decision["code"] == SEARCH_PENDING
    # Contracase: once waited, the step is the rules' again (never the same wait twice).
    waited = [{**pressed[0], "awaited": True}]
    again = _decide(_READ, "ir a musica", "WhatsApp", _wa_kept_search(), waited,
                    success_check="control:musica:current|title:musica|page:musica|mark:musica")
    assert again.get("code") != SEARCH_PENDING


# ---------------- encargo WR (imp-wa-leer on the notebook: «fue «Borrar todo» (22:55)», «fue «2314» (23:14)», «fue «Ayer»»)

# Positions of the five frozen reads (evidencia_wab1…wac3, a window narrower than redpc's: the chat list reaches x≈0.33,
# inside the data's region), with neutral texts where the owner's chats were: the list's column of times and dates, a
# button of the recent searches, a reading of one box twice, the header's tooltip, the empty chat's buttons in a row.
_ABUELA = "leé lo último que me escribió Abuela"
_NARROW_LIST = [
    {"text": "Contacto uno", "x": 0.119, "y": 0.276, "w": 0.031, "h": 0.014},
    {"text": "2311", "x": 0.300, "y": 0.279, "w": 0.021, "h": 0.011},
    {"text": "23:11", "x": 0.300, "y": 0.279, "w": 0.021, "h": 0.011},
    {"text": "2314", "x": 0.300, "y": 0.375, "w": 0.023, "h": 0.011},
    {"text": "23:14", "x": 0.300, "y": 0.375, "w": 0.023, "h": 0.011},
    {"text": "Ayer", "x": 0.304, "y": 0.471, "w": 0.019, "h": 0.014},
    {"text": "prueba BAXY imp", "x": 0.120, "y": 0.498, "w": 0.101, "h": 0.018},
]
_INTERFACE = [
    {"text": "haz clic aquí para ver la información de contacto", "x": 0.408, "y": 0.094, "w": 0.220, "h": 0.016},
    {"text": "Borrar todo", "x": 0.269, "y": 0.218, "w": 0.056, "h": 0.014},
    {"text": "22:55", "x": 0.300, "y": 0.517, "w": 0.023, "h": 0.011},
    {"text": "Enviar documento", "x": 0.494, "y": 0.563, "w": 0.075, "h": 0.012},
    {"text": "Añadir contacto", "x": 0.595, "y": 0.562, "w": 0.067, "h": 0.013},
    {"text": "Invite a friend", "x": 0.688, "y": 0.563, "w": 0.056, "h": 0.012},
]
_SEPARATORS = [
    {"text": "Haz clic aquí para obtener mensajes anteriores de tu teléfono.", "x": 0.537, "y": 0.274, "w": 0.271,
     "h": 0.016},
    {"text": "5/2/2026", "x": 0.652, "y": 0.335, "w": 0.039, "h": 0.012},
]
_OWN_HELLO = [  # wac3: the person's bubble and its time beside it
    {"text": "hola prueba", "x": 0.864, "y": 0.384, "w": 0.035, "h": 0.014},
    {"text": "17:18", "x": 0.904, "y": 0.395, "w": 0.023, "h": 0.011},
]
_THEIR_LINE = [  # someone else's bubble at the conversation's left, its time under its last line
    {"text": "llego a las ocho", "x": 0.345, "y": 0.640, "w": 0.090, "h": 0.015},
    {"text": "21:07", "x": 0.420, "y": 0.657, "w": 0.020, "h": 0.011},
]


def test_wr_the_interface_and_the_list_column_are_never_quoted_as_a_message() -> None:
    for lines in (_NARROW_LIST, _INTERFACE, _NARROW_LIST + _INTERFACE + _SEPARATORS):
        assert cu_chat_lines.last_written(lines, app_places.conversation("WhatsApp")) is None
        assert cu_finals.question_answer(_seen(lines, _ABUELA), english=False) == (
            "En lo que muestra el chat no pude leer ningún mensaje de Abuela.")
    assert cu_finals.question_answer(_seen(_INTERFACE, "read the last message from Abuela"), english=True) == (
        "In what the chat shows I could not read any message from Abuela.")


def test_wr_only_the_persons_own_bubble_says_none_of_theirs() -> None:
    lines = _NARROW_LIST + _SEPARATORS + _OWN_HELLO
    assert cu_finals.question_answer(_seen(lines, _ABUELA), english=False) == (
        "En lo que muestra el chat no hay mensajes de Abuela.")


def test_wr_contracase_their_message_among_the_interface_is_quoted_with_its_time() -> None:
    lines = _NARROW_LIST + _INTERFACE + _SEPARATORS + _OWN_HELLO + _THEIR_LINE
    assert cu_finals.question_answer(_seen(lines, _ABUELA), english=False) == (
        "Lo último que te escribió Abuela fue «llego a las ocho» (21:07).")
    # A long bubble of theirs ends with its time past the centre: still theirs, wrapped lines joined.
    long_bubble = [
        {"text": "primera línea larga", "x": 0.345, "y": 0.700, "w": 0.300, "h": 0.015},
        {"text": "y la segunda", "x": 0.345, "y": 0.719, "w": 0.060, "h": 0.015},
        {"text": "21:09", "x": 0.640, "y": 0.728, "w": 0.020, "h": 0.011},
    ]
    found = cu_chat_lines.last_written(lines + long_bubble, app_places.conversation("WhatsApp"))
    assert (found.text, found.time) == ("primera línea larga y la segunda", "21:09")


def test_wr_contracase_a_time_far_under_a_text_or_a_twin_reading_closes_no_bubble() -> None:
    region = app_places.conversation("WhatsApp")
    far = [{**_THEIR_LINE[0]}, {**_THEIR_LINE[1], "y": 0.700}]
    assert cu_chat_lines.bubbles(far, region) == []
    twin = [{"text": "2109", "x": 0.420, "y": 0.657, "w": 0.020, "h": 0.011}]
    assert [bubble.texts for bubble in cu_chat_lines.bubbles(_THEIR_LINE[:1] + twin + _THEIR_LINE[1:], region)] == [
        ("llego a las ocho",)]
