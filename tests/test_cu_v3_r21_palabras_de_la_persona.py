"""Ronda 21, palanca «palabras de la persona con su conversación» (pasada r18: v3-23, v3-65, v3-58, v3-35, t-drag-1,
v3-68). Four points of the routing took the decider's paraphrase, or read the message without its conversation; the
engine now gets the person's words framed in the application the conversation is in, the dictated text is never read
as the order, and the operations chosen on an unfaithful restatement are checked again. Each rule with its counter."""

from __future__ import annotations

from typing import Any

import pytest

from baxy_mind import known_folders
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import cu_tipos, decider, missions
from baxy_mind.semantic.decider import ContextDecision

from test_cu_v3_cobertura import APPS, OPERATIONS, _Decider, _tool
from baxy_mind import turn_decide
from baxy_mind import context_decision
from baxy_mind import engine_handoff
from baxy_mind import compose_facts

PLACES = APPS + ("Configuración", "Visor de eventos", "Servicios", "Programador de tareas", "Explorador de archivos")
FOLDER = r"C:\Users\persona\Documents\baxy-prueba-v3"


class _WholeTurn(_Decider):
    """The model of a whole turn (``_decide_turn_result``): every call besides the decider's is neutral."""

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Dónde?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué necesitas?"

    def public_lookup_requested(self, _text):
        return False

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def prepare_chat(self, *_a, **_k):
        return None

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None


def _whole_turn(turns: list[str], decision: ContextDecision) -> dict[str, Any]:
    history: list[dict[str, str]] = []
    for said in turns[:-1]:
        history += [{"role": "user", "content": said}, {"role": "assistant", "content": "Listo."}]
    history.append({"role": "user", "content": turns[-1]})
    tools = {name: _tool(name) for name in OPERATIONS}
    return turn_decide._decide_turn_result(
        {"id": "r21", "text": turns[-1], "history": history}, llm=_WholeTurn(decision),
        planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _text: (), tool_by_name=tools,
        application_names=PLACES, in_conversation=len(turns) > 1,
    )


def _turn(turns: list[str], decision: ContextDecision) -> dict[str, Any]:
    history: list[dict[str, str]] = []
    for said in turns[:-1]:
        history += [{"role": "user", "content": said}, {"role": "assistant", "content": "Listo."}]
    history.append({"role": "user", "content": turns[-1]})
    return context_decision._context_decided_result(
        {"id": "r21", "text": turns[-1], "history": history}, llm=_Decider(decision),
        planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]), application_names=PLACES,
    )


@pytest.fixture
def the_test_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        known_folders, "located_folders",
        lambda name, base=None: ((FOLDER,), True) if name == "baxy-prueba-v3" else ((), False),
    )


# ------------------------------------------------- (a) the restated primitives the person never said (v3-23, v3-65)

def test_v3_23_going_to_a_place_is_the_persons_words_with_a_place_check() -> None:
    restated = "En el Visor de eventos, haz clic en «Registros de Windows» y luego en «Sistema»."
    result = _turn(
        ["abre el visor de eventos", "ahora anda a registros de windows, sistema"],
        ContextDecision(restated, "action", ("input.visible.click",), ""),
    )
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == "en Visor de eventos, anda a registros de windows, sistema"
    mission = missions.mission_request(result["objective"], PLACES)
    assert mission is not None and mission.application == "Visor de eventos"
    assert mission.steps[-1].success_check.startswith("control:sistema:current")
    assert "stepDone:input.visible.click" not in (mission.goal + "".join(s.success_check or "" for s in mission.steps))


def test_v3_65_a_view_said_is_never_a_label_the_restatement_invented() -> None:
    result = _turn(
        ["abre servicios", "cambiala a la vista estandar"],
        ContextDecision("En Servicios, haz clic en «Vista estándar».", "action", ("input.visible.click",), ""),
    )
    assert result["objective"] == "en Servicios, cambiala a la vista estandar"
    mission = missions.mission_request(result["objective"], PLACES)
    assert mission is not None and "control:estandar:selected" in (mission.success_check or "")


def test_counter_the_click_the_person_says_keeps_the_restatement_and_its_receipt() -> None:
    restated = "En el Visor de eventos, haz clic en «Sistema»."
    result = _turn(
        ["abre el visor de eventos", "ahora hacé clic en Sistema"],
        ContextDecision(restated, "action", ("input.visible.click",), ""),
    )
    assert decider.primitives_unsaid(("input.visible.click",), "ahora hacé clic en Sistema") is False
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == restated


def test_counter_v2_s13_a_name_only_mentioned_stays_in_the_conversations_application() -> None:
    result = _turn(
        ["en Discord abrí el servidor de pruebas", "y ahora andá a configuración"],
        ContextDecision("En Discord, haz clic en Configuración.", "action", ("input.visible.click",), ""),
    )
    assert result["objective"] == "en Discord, andá a configuración"
    mission = missions.mission_request(result["objective"], PLACES)
    assert mission is not None and mission.application == "Discord"
    assert (mission.success_check or "").startswith("control:configuracion:current")


def test_a_quotation_the_person_never_said_is_no_literal_label() -> None:
    assert decider.without_unsaid_quotes(
        "En el Programador de tareas, haz clic en «Ocultar panel de acciones».", "esconde el panel de acciones",
    ) == "En el Programador de tareas, haz clic en Ocultar panel de acciones."
    # Counter: the person's own words keep their quotes.
    assert decider.without_unsaid_quotes("haz clic en «Sistema».", "hacé clic en sistema") == "haz clic en «Sistema»."


# ------------------------------------------- (b) a named application that is the place gone to before (v3-58)

def test_v3_58_the_settings_said_after_edge_went_there_are_edges() -> None:
    history = [
        {"role": "user", "content": "abre edge y anda a la configuracion"},
        {"role": "assistant", "content": "No llegué a la configuración de Edge."},
        {"role": "user", "content": "busca cookies ahi en la configuracion"},
    ]
    again = engine_handoff._the_place_gone_to_again("busca cookies ahi en la configuracion", history, OPERATIONS, PLACES)
    assert again == "en Microsoft Edge, anda a la configuracion y busca cookies ahi"
    result = context_decision._context_decided_result(
        {"id": "r21", "text": history[-1]["content"], "history": history}, llm=_Decider(ContextDecision("", "talk", (), "")),
        planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]), application_names=PLACES,
        decided_beforehand=ContextDecision(again, "action", ("mission.computer.use",), ""),
    )
    assert result["effectOperations"] == ["mission.computer.use"]
    assert missions.mission_request(result["objective"], PLACES).application == "Microsoft Edge"


@pytest.mark.parametrize(
    "before",
    [
        (),  # a first order: the settings application alone
        ("abre edge y busca gatos",),  # the request before went to no place
    ],
)
def test_counter_the_settings_stay_the_settings_without_a_place_gone_to(before: tuple[str, ...]) -> None:
    text = "busca cookies en la configuracion"
    history = [{"role": "user", "content": said} for said in (*before, text)]
    assert engine_handoff._the_place_gone_to_again(text, history, OPERATIONS, PLACES) is None
    assert missions.mission_request(text, PLACES).application == "Configuración"


def test_v3_58_the_whole_turn_goes_back_to_the_place_in_edge() -> None:
    text = "busca cookies ahi en la configuracion"
    result = _whole_turn(
        ["abre edge y anda a la configuracion", text], ContextDecision(text, "action", ("mission.computer.use",), ""),
    )
    assert result["effectOperations"] == ["mission.computer.use"]
    assert missions.mission_request(result["objective"], PLACES).application == "Microsoft Edge"


@pytest.mark.parametrize(
    "text",
    [
        # Revisión 1 (hallazgo 2): the person said whose settings; Edge's are not searched.
        "en configuración de windows busca bluetooth",
        "en la configuracion de windows busca bluetooth",
        "busca cookies en la configuracion de windows",
        "en la configuracion de mi pc busca bluetooth",
    ],
)
def test_counter_a_place_said_with_its_owner_is_not_the_place_gone_to(text: str) -> None:
    before = "abre edge y anda a la configuracion"
    history = [{"role": "user", "content": before}, {"role": "assistant", "content": "Listo."},
               {"role": "user", "content": text}]
    assert engine_handoff._the_place_gone_to_again(text, history, OPERATIONS, PLACES) is None
    result = _whole_turn([before, text], ContextDecision(text, "action", ("mission.computer.use",), ""))
    assert result["effectOperations"] == ["mission.computer.use"]
    objective = result.get("objective")
    assert objective in (None, text)
    if objective is None and missions.mission_request(text, PLACES) is not None:
        assert missions.mission_request(text, PLACES).application == "Configuración"


# --------------------------------------------------- (c) the dictated text is never the order (v3-35)

@pytest.mark.parametrize(
    "text",
    ["en Notas rápidas, ponle: pagar la luz", "en el bloc de notas escribe: borrar todo",
     'en notas rapidas ponle "pagar la luz"'],
)
def test_a_dictated_text_is_not_a_paying_or_undoing_order(text: str) -> None:
    assert missions.engine_can_try(text, PLACES)


@pytest.mark.parametrize(
    "text",
    ["en Steam pagá el juego", "en el bloc de notas borrá todo", "en el bloc de notas borra: el archivo",
     "en steam compra: el juego"],
)
def test_counter_the_orders_own_verb_still_keeps_it_from_the_engine(text: str) -> None:
    assert not missions.engine_can_try(text, PLACES)


# Revisión 2 (seguridad): only the quotes a writing or putting verb dictates are its text; the quoted label of a click
# is the order, and an undoing or paying label keeps the order from the engine as it did before the round.
QUOTED_LABELS = [
    "En Configuración, haz clic en «Restablecer este PC».",
    'en discord haz clic en "Eliminar servidor"',
    "en steam pulsa «Comprar ahora»",
    'en discord pulsa "salir del servidor"',
    "En Steam, haz clic en «Comprar».",
    "en edge haz clic en «Borrar datos de navegación»",
    'en el bloc de notas escribí hola y pulsa "Eliminar servidor"',
]


@pytest.mark.parametrize("text", QUOTED_LABELS)
def test_counter_the_quoted_label_of_a_click_is_the_order(text: str) -> None:
    assert not missions.engine_can_try(text, PLACES)
    assert missions._orders_undoing_or_paying(missions.fold(text))
    assert missions.mission_request(text, PLACES) is None


@pytest.mark.parametrize(
    "text",
    ['en notas rapidas escribí en la nota "borrar la luz"', "en el bloc de notas ponle «comprar pan»",
     'en notas rapidas anotá: "pagar la luz"'],
)
def test_the_quotes_a_writing_verb_dictates_are_its_text(text: str) -> None:
    assert missions.engine_can_try(text, PLACES)


# Revisión 3 (seguridad): the dictated text after a colon ends at a joiner; an order the mission reader parts from it
# («y despues compralo», «y compralo», «y despues borra la carpeta Documentos») is read as an order again, as before
# the round, and an undoing or paying one never reaches the engine.
DICTATED_THEN_PAYING_OR_UNDOING = [
    "en steam pon en el buscador: hades y despues compralo",
    "en steam agrega a la lista de deseos: hades y compralo",
    "en el explorador de archivos pon en la barra: C:/Users y despues borra la carpeta Documentos",
]


@pytest.mark.parametrize("text", DICTATED_THEN_PAYING_OR_UNDOING)
def test_counter_an_order_after_the_dictated_text_is_still_the_order(text: str) -> None:
    assert not missions.engine_can_try(text, PLACES)
    assert missions.free_form_arguments(text, PLACES) is None
    assert missions.mission_request(text, PLACES) is None
    assert missions._orders_undoing_or_paying(missions.fold(text))


@pytest.mark.parametrize("text", DICTATED_THEN_PAYING_OR_UNDOING)
@pytest.mark.parametrize(
    "operations", [("input.text.type",), ("input.text.type", "input.key.press")],
)
def test_counter_an_order_after_the_dictated_text_never_turns_into_the_engines(
    text: str, operations: tuple[str, ...],
) -> None:
    result = _whole_turn([text], ContextDecision("Escribe «hades» en el buscador y cómpralo.", "action", operations, ""))
    assert "mission.computer.use" not in (result.get("effectOperations") or [])


def test_counter_a_wish_list_then_buying_stays_a_task_as_before() -> None:
    text = DICTATED_THEN_PAYING_OR_UNDOING[1]
    result = _whole_turn([text], ContextDecision(text, "action", ("mission.computer.use",), ""))
    assert "mission.computer.use" not in (result.get("effectOperations") or [])


def test_counter_a_paying_click_after_steam_stays_a_click_and_never_the_engines() -> None:
    result = _turn(
        ["abre steam", "comprá el juego que está en el carrito"],
        ContextDecision("En Steam, haz clic en «Comprar».", "action", ("input.visible.click",), ""),
    )
    assert result["effectOperations"] == ["input.visible.click"]


# ------------------------------------- (d) a follow-up framed in the conversation's application (v3-35)

def test_v3_35_a_text_put_on_the_new_note_is_written_in_the_application() -> None:
    result = _turn(
        ["crea una nota rapida nueva", "ponle: pagar la luz"],
        ContextDecision("Crea una nota: pagar la luz.", "action", ("note.create",), ""),
    )
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == "en Notas rápidas, ponle: pagar la luz"


@pytest.mark.parametrize(
    ("turns", "decision"),
    [
        (["crea una nota rapida nueva", "anotá en mis notas de BAXY: pagar la luz"],
         ContextDecision("Crea una nota: pagar la luz.", "action", ("note.create",), "")),
        (["crea una nota rapida nueva", "recordame mañana a las 8 pagar la luz"],
         ContextDecision("Recuérdame mañana a las 8 pagar la luz.", "action", ("reminder.create",), "")),
        (["abre spotify", "subí el volumen"],
         ContextDecision("Sube el volumen de Spotify.", "action", ("audio.app.volume.set",), "")),
        (["en spotify subí el volumen"],
         ContextDecision("Sube el volumen de Spotify.", "action", ("audio.app.volume.set",), "")),
        (["abre el bloc de notas", "poné música de queen"],
         ContextDecision("Pon música de Queen.", "action", ("media.play",), "")),
    ],
)
def test_counter_what_a_typed_operation_serves_keeps_its_route(turns: list[str], decision: ContextDecision) -> None:
    assert _turn(turns, decision)["effectOperations"] == list(decision.operations)


@pytest.mark.parametrize(
    "turns",
    [
        # Revisión 1 (hallazgo 1): an application only opened, or one where nothing like a note was made, is no place
        # for the note; the engine would type it in the person's chat, player, browser or store.
        ["abre discord", "anotá: llamar a mamá"],
        ["abre spotify", "anotá: llamar a mamá"],
        ["abre edge", "guardá una nota que diga llamar a mamá"],
        ["abre steam", "haceme una nota: revisar ofertas"],
        ["abre discord", "ponle: llamar a mamá"],
        ["en Discord abrí el servidor de pruebas", "anotá: llamar a mamá"],
    ],
)
def test_counter_a_note_after_an_application_where_no_note_was_made_stays_baxys(turns: list[str]) -> None:
    result = _turn(turns, ContextDecision("Crea una nota: llamar a mamá.", "action", ("note.create",), ""))
    assert result["effectOperations"] == ["note.create"]
    assert "objective" not in result or not str(result["objective"]).lower().startswith("en ")


def test_made_there_before_reads_the_request_that_named_the_application() -> None:
    made = ("note.create",)
    assert missions.made_there_before(["crea una nota rapida nueva"], made, OPERATIONS, PLACES)
    assert not missions.made_there_before(["abre notas rapidas"], made, OPERATIONS, PLACES)
    assert not missions.made_there_before(["abre discord"], made, OPERATIONS, PLACES)
    assert not missions.made_there_before(["en Discord abrí el servidor de pruebas"], made, OPERATIONS, PLACES)
    # Counter: an operation that makes nothing applications make never belongs to the application.
    assert not missions.made_there_before(["crea una nota rapida nueva"], ("reminder.create",), OPERATIONS, PLACES)


# ------------------------------- (e) operations chosen on an unfaithful restatement are checked again (t-drag-1, v3-68)

def test_t_drag_1_a_drag_said_in_a_folder_is_the_known_limit(the_test_folder: None) -> None:
    # Estabilización L: dragging is a declared limit; t-drag-1 is neither the engine's (it has no act for it) nor the
    # sandbox's filesystem.move of the decider's unfaithful restatement: the turn says the limit.
    text = "arrastrá lista.txt adentro de la carpeta archivo, en baxy-prueba-v3"
    assert missions.mission_request(text, PLACES) is None
    result = _whole_turn(
        [text], ContextDecision("Mueve archivo.txt de la carpeta de trabajo a archivo/ en baxy-prueba-v3.", "action",
                                ("filesystem.move",), ""),
    )
    assert result["kind"] == "conversation" and result.get("conversationKind") == "unsupported", result
    assert not result.get("effectOperations")
    # The folder said as the tail still makes the Explorer the place of an order that is no drag.
    mission = missions.mission_request("seleccioná lista.txt, en baxy-prueba-v3", PLACES)
    assert mission is not None and mission.application == "Explorador de archivos"
    assert mission.steps[0].goal == f"ir a {FOLDER.lower()}"


def test_counter_a_folder_said_without_the_comma_is_the_orders_object(the_test_folder: None) -> None:
    assert missions.mission_request("descargá el instalador en Descargas", PLACES) is None
    assert missions.mission_request("seleccioná lista.txt, en otra-carpeta", PLACES) is None
    result = _turn(
        ["descargá el instalador en Descargas"],
        ContextDecision("Descarga el instalador en Descargas.", "action", ("web.download",), ""),
    )
    assert result["effectOperations"] == ["web.download"]


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        # Revisión 2 (regresión): a known folder said bare as the tail is where the typed operation works.
        ("pon música relajante, en Música", "media.play.query"),
        ("descargá el instalador, en Descargas", "web.download"),
        ("busca fotos de gatos, en Imágenes", "filesystem.known.search"),
        ("buscá el informe.pdf, en Documentos", "filesystem.known.search"),
        ("crea un archivo notas.txt, en Escritorio", "note.create"),
    ],
)
def test_counter_a_known_folder_said_bare_as_the_tail_keeps_the_typed_operation(text: str, operation: str) -> None:
    assert missions.mission_request(text, PLACES) is None
    result = _whole_turn([text], ContextDecision(text, "action", (operation,), ""))
    assert result["effectOperations"] == [operation]


def test_the_tail_said_as_a_folder_is_still_the_place(the_test_folder: None) -> None:
    mission = missions.mission_request("seleccioná lista.txt, en la carpeta baxy-prueba-v3", PLACES)
    assert mission is not None and mission.application == "Explorador de archivos"


def test_v3_68_a_click_on_an_unfaithful_restatement_is_not_kept() -> None:
    text = "en el programador de tareas esconde el panel de acciones de la derecha"
    result = _turn(
        [text],
        ContextDecision("En el Administrador de tareas, haz clic en «Ocultar panel de acciones».", "action",
                        ("input.visible.click",), ""),
    )
    assert result["effectOperations"] == ["mission.computer.use"]
    assert result["objective"] == text


def test_primitives_said_and_not_chosen() -> None:
    assert decider.primitives_said_unchosen(("filesystem.move",), "hacé clic en Archivo") == ("input.visible.click",)
    assert decider.primitives_said_unchosen(("input.visible.click",), "hacé clic en Archivo") == ()
    # Estabilización L: dragging is a declared limit (semantic.drag), no primitive of the screen any more.
    assert decider.primitives_said_unchosen(("filesystem.move",), "arrastrá lista.txt a archivo") == ()


# ------------------------------------------------------------------ (f) hiding and folding are orders

@pytest.mark.parametrize("head", ["esconde", "oculta", "hide", "contrae", "colapsa"])
def test_hiding_heads_an_order(head: str) -> None:
    assert head in cu_tipos.ORDER_HEADS
    assert missions.ordered_in_application(f"en el programador de tareas {head} el panel de acciones", PLACES) == (
        "Programador de tareas"
    )


def test_counter_a_word_that_heads_no_order_still_heads_none() -> None:
    assert "el" not in cu_tipos.ORDER_HEADS


# ---------------------------------- (g) a note made in BAXY's store beside an application says where it is (v3-35)

def _made(operation: str = "note.create") -> dict[str, Any]:
    return {"kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
            "observed": {"title": "pagar la luz"}}


@pytest.mark.parametrize(
    ("turns", "application"),
    [
        (["abre notas rapidas", "ponle: pagar la luz"], "Notas rápidas"),
        (["abre onenote", "anotá: pagar la luz"], "OneNote"),
        (["en onenote anotá: pagar la luz"], "OneNote"),
    ],
)
def test_v3_35_a_note_kept_in_baxy_beside_an_application_is_told_as_baxys(turns: list[str], application: str) -> None:
    result = _whole_turn(turns, ContextDecision("Crea una nota: pagar la luz.", "action", ("note.create",), ""))
    if len(turns) > 1:
        assert result["effectOperations"] == ["note.create"]
    facts = compose_facts._with_made_in_store(
        {"situation": _made(), "priorRequests": turns[:-1]}, _made(), turns[-1], PLACES,
    )
    assert facts["situation"]["madeIn"] == {"store": "BAXY", "notIn": application}
    final = compose_facts._told_where_it_was_made("He creado la nota.", facts["situation"], False)
    assert final == f"He creado la nota. Quedó guardado en BAXY, no en {application}."
    english = compose_facts._told_where_it_was_made("I created the note.", facts["situation"], True)
    assert english == f"I created the note. It is saved in BAXY, not in {application}."


@pytest.mark.parametrize(
    ("turns", "situation"),
    [
        (["anotá: pagar la luz"], _made()),
        (["abre notas rapidas", "anotá en BAXY: pagar la luz"], _made()),
        (["abre notas rapidas", "recordame mañana pagar la luz"], _made("reminder.create")),
        (["abre spotify", "subí el volumen"], _made("audio.app.volume.set")),
        (["abre notas rapidas", "ponle: pagar la luz"], {**_made(), "verified": False, "succeeded": False}),
    ],
)
def test_counter_a_thing_made_with_no_application_beside_it_carries_no_store(
    turns: list[str], situation: dict[str, Any],
) -> None:
    facts = {"situation": situation, "priorRequests": turns[:-1]}
    assert compose_facts._with_made_in_store(facts, situation, turns[-1], PLACES) is facts
    assert compose_facts._told_where_it_was_made("He creado la nota.", situation, False) == "He creado la nota."


def test_counter_a_final_that_says_the_store_or_is_empty_stays_as_written() -> None:
    situation = {**_made(), "madeIn": {"store": "BAXY", "notIn": "Notas rápidas"}}
    said = "Guardé la nota en BAXY."
    assert compose_facts._told_where_it_was_made(said, situation, False) == said
    assert compose_facts._told_where_it_was_made("", situation, False) == ""


# Revisión 3 (falso éxito): what makes a real file on the person's disk (a text file, a .pptx, an Office package) is
# never said to be kept in BAXY's store, whatever application the request or the conversation is in.
@pytest.mark.parametrize(
    ("turns", "operation", "final"),
    [
        (["abre powerpoint", "haceme una presentacion de 3 diapositivas sobre gatos"], "document.presentation.create",
         "Listo, quedó en Documentos."),
        (["abre el bloc de notas", "guarda un archivo hola.txt en el escritorio que diga hola"], "filesystem.write.text",
         "Listo, quedó en el Escritorio."),
        (["en el bloc de notas guarda un archivo hola.txt en el escritorio que diga hola"], "filesystem.write.text",
         "Listo, quedó en el Escritorio."),
        (["abre powerpoint", "haceme un documento de word sobre gatos"], "office.document.create",
         "Listo, quedó en Documentos."),
    ],
)
def test_counter_a_file_made_on_the_disk_is_never_told_as_kept_in_baxy(
    turns: list[str], operation: str, final: str,
) -> None:
    if len(turns) > 1 and operation != "office.document.create":
        result = _whole_turn(turns, ContextDecision(turns[-1], "action", (operation,), ""))
        assert result["effectOperations"] == [operation]
    situation = _made(operation)
    facts = {"situation": situation, "priorRequests": turns[:-1]}
    assert compose_facts._with_made_in_store(facts, situation, turns[-1], PLACES) is facts
    assert "madeIn" not in facts["situation"]
    assert compose_facts._told_where_it_was_made(final, situation, False) == final
