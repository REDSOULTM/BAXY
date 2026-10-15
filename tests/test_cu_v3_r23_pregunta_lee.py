"""Ronda 23, pregunta-lee-lo-pertinente (live r21: v3-62 falso éxito, v3-46 la tarjeta sin leer).

- A chained mission's last sub-goal carries the mission's question (``semantic.missions.mission_request``), so it is
  closed by a look that reads the datum, never by receipts alone (v3-46).
- A done of a goal that carries a question cites the datum that answers it (``semantic.answer_evidence``,
  ``computer_use._cites_the_answer``): with «(activa)» on screen for «which network is active», «El firewall está
  activado.» is refused (v3-62).
"""

from __future__ import annotations

from baxy_mind import computer_use
from baxy_mind.semantic import missions
from baxy_mind.semantic.answer_evidence import citation_misses_question, shares_root

APPS = ["Seguridad de Windows", "Información del sistema", "Calculadora", "Configuración"]

# The look of live r21 v2-v3-62 after «Firewall y protección de red» (model_calls.jsonl, request 9).
FIREWALL_VIEW = {
    "window": {"title": "Seguridad de Windows", "process": "SecHealthUI"},
    "controls": [
        {"i": 9, "kind": "ListItem", "name": "Firewall y protección de red", "state": "selected", "zone": "L"},
        {"i": 16, "kind": "Hyperlink", "name": "Red de dominio", "state": "focused", "zone": "TL"},
        {"i": 17, "kind": "Hyperlink", "name": "Red privada", "zone": "L"},
        {"i": 18, "kind": "Hyperlink", "name": "Red pública", "zone": "L"},
        {"i": 36, "kind": "Text", "name": "El firewall está activado.", "zone": "TL"},
    ],
    "text": {
        "TL": ["Seguridad de Windows", "Quién y qué puede tener acceso a las redes.", "Red de dominio",
               "EI firewall está activado."],
        "L": ["Red privada (activa)", "Red privada", "(activa)", "Red pública"],
    },
}
FIREWALL_GOAL = "ir a firewall & network protection; y responder: tell me which network is active"


def _done(evidence: str) -> dict[str, object]:
    return {"operation": "done", "arguments": {"evidence": evidence}, "reason": ""}


def test_the_last_subgoal_of_a_chain_carries_the_question() -> None:
    mission = missions.mission_request(
        "abrí información del sistema, andá a componentes y después a pantalla, y decime qué tarjeta de video tengo",
        APPS,
    )
    assert mission is not None and len(mission.steps) == 2
    assert mission.goal.endswith(missions.QUESTION_MARK + "decime qué tarjeta de video tengo")
    assert mission.steps[-1].goal == "ir a pantalla" + missions.QUESTION_MARK + "decime qué tarjeta de video tengo"
    # Contracase: the earlier sub-goal does only its own part.
    assert missions.QUESTION_MARK not in mission.steps[0].goal


def test_a_chain_without_a_question_is_unchanged() -> None:
    mission = missions.mission_request("abrí información del sistema, andá a componentes y después a pantalla", APPS)
    assert mission is not None and len(mission.steps) == 2
    assert all(missions.QUESTION_MARK not in step.goal for step in mission.steps)


def test_a_single_mission_keeps_its_question_on_its_goal() -> None:
    mission = missions.mission_request(
        "windows security, go to firewall & network protection and tell me which network is active", APPS)
    assert mission is not None and not mission.steps
    assert mission.goal == FIREWALL_GOAL


def test_roots_across_languages() -> None:
    assert shares_root("active", "activa")
    assert shares_root("plan", "planes")
    assert not shares_root("active", "activado")
    assert not shares_root("red", "redes")
    # Revision 2: a participle is another word of the root, an inflection is the same word.
    assert not shares_root("activa", "activado")
    assert not shares_root("activas", "activado")
    assert shares_root("activo", "activos")
    assert shares_root("activa", "activo")
    assert shares_root("memory", "memoria")


def test_a_citation_without_the_marked_datum_misses_the_question() -> None:
    texts = computer_use._view_texts(FIREWALL_VIEW)
    said = ("ir a firewall & network protection", "Seguridad de Windows")
    assert citation_misses_question("EI firewall está activado.", "tell me which network is active", texts, said)
    assert citation_misses_question("Red de dominio", "tell me which network is active", texts, said)
    assert not citation_misses_question("Red privada (activa)", "tell me which network is active", texts, said)


def test_a_citation_part_of_the_bearing_text_answers() -> None:
    # Contracase (v3-43): «Equilibrado» is the datum of «Cambiar la configuración del plan Equilibrado».
    texts = ["Opciones de energía", "Cambiar la configuración del plan Equilibrado", "Equilibrado"]
    assert not citation_misses_question("Equilibrado", "qué plan está activo", texts, ("abrir Opciones de energía",))


def test_nothing_of_the_question_on_screen_judges_nothing() -> None:
    # Contracase (v3-46): the table says «Nombre» and the card; no word of «tarjeta de video» is written there.
    texts = ["Pantalla", "Nombre", "AMD Radeon(TM) Graphics", "RAM de adaptador"]
    assert not citation_misses_question("AMD Radeon(TM) Graphics", "decime qué tarjeta de video tengo", texts)


def test_the_step_refuses_a_done_that_does_not_cite_the_answer() -> None:
    head, _, question = FIREWALL_GOAL.partition(missions.QUESTION_MARK)
    refused = computer_use._cites_the_answer(_done("EI firewall está activado."), question, head, FIREWALL_VIEW)
    assert refused["operation"] == "none"
    assert refused["code"] == "evidence_not_visible"
    assert refused["code"] in computer_use._RETRIED
    kept = computer_use._cites_the_answer(_done("Red privada (activa)"), question, head, FIREWALL_VIEW)
    assert kept["operation"] == "done"
    # Contracase: a goal without a question is never judged so.
    plain = computer_use._cites_the_answer(_done("EI firewall está activado."), "", head, FIREWALL_VIEW)
    assert plain["operation"] == "done"


# Revisión 1: the window writes a label and its value as separate texts (a row's cells, a slider's value, a switch's
# state); a citation that is only the value is read with its label.
SYSTEM_INFO_VIEW = {
    "window": {"title": "Información del sistema", "process": "msinfo32"},
    "controls": [
        {"i": 20, "kind": "DataItem", "name": "Procesador", "zone": "TR"},
        {"i": 21, "kind": "Text", "name": "Procesador", "zone": "TR"},
        {"i": 22, "kind": "Text", "name": "AMD Ryzen 7 5800H with Radeon Graphics, 3201 Mhz", "zone": "TR"},
        {"i": 23, "kind": "DataItem", "name": "Memoria física instalada (RAM)", "zone": "TR"},
        {"i": 24, "kind": "Text", "name": "Memoria física instalada (RAM)", "zone": "TR"},
        {"i": 25, "kind": "Text", "name": "16,0 GB", "zone": "TR"},
        {"i": 26, "kind": "DataItem", "name": "Fabricante del sistema", "zone": "TR"},
        {"i": 27, "kind": "Text", "name": "Fabricante del sistema", "zone": "TR"},
        {"i": 28, "kind": "Text", "name": "ASUSTeK COMPUTER INC.", "zone": "TR"},
    ],
    "text": {},
}
SOUND_VIEW = {
    "window": {"title": "Configuración"},
    "controls": [
        {"i": 3, "kind": "Slider", "name": "Volumen", "value": "75", "zone": "C"},
        {"i": 4, "kind": "Slider", "name": "Brillo", "value": "40", "zone": "C"},
        {"i": 5, "kind": "ListItem", "name": "Vecino_2G", "zone": "C"},
        {"i": 6, "kind": "Text", "name": "Protegida", "zone": "C"},
        {"i": 7, "kind": "ListItem", "name": "MiCasa_5G", "zone": "C"},
        {"i": 8, "kind": "Text", "name": "Conectado, protegida", "zone": "C"},
    ],
    "text": {},
}


def _bluetooth_view(bluetooth: str, swift_pair: str) -> dict:
    words = {"on": "Activado", "off": "Desactivado"}
    return {
        "window": {"title": "Configuración"},
        "controls": [
            {"i": 9, "kind": "ListItem", "name": "Bluetooth y dispositivos", "state": "selected", "zone": "L"},
            {"i": 10, "kind": "Button", "name": "Bluetooth", "state": bluetooth, "zone": "C"},
            {"i": 11, "kind": "Text", "name": words[bluetooth], "zone": "C"},
            {"i": 12, "kind": "Hyperlink", "name": "Ver más dispositivos", "zone": "C"},
            {"i": 14, "kind": "Button", "name": "Swift Pair", "state": swift_pair, "zone": "C"},
            {"i": 15, "kind": "Text", "name": words[swift_pair], "zone": "C"},
        ],
        "text": {"C": ["Bluetooth", words[bluetooth], "Swift Pair", words[swift_pair]]},
    }


def _judged(evidence: str, goal: str, view: dict) -> str:
    head, _, question = goal.partition(missions.QUESTION_MARK)
    return str(computer_use._cites_the_answer(_done(evidence), question, head, view)["operation"])


def test_a_value_written_apart_from_its_label_answers() -> None:
    ram = "abrir Información del sistema; y responder: decime cuánta memoria RAM tengo"
    assert _judged("16,0 GB", ram, SYSTEM_INFO_VIEW) == "done"
    assert _judged("Memoria física instalada (RAM)", ram, SYSTEM_INFO_VIEW) == "done"
    # Contracase: the value of another row does not carry the memory.
    assert _judged("ASUSTeK COMPUTER INC.", ram, SYSTEM_INFO_VIEW) == "none"
    cpu = "abrir Información del sistema; y responder: decime qué procesador tengo"
    assert _judged("AMD Ryzen 7 5800H with Radeon Graphics", cpu, SYSTEM_INFO_VIEW) == "done"
    assert _judged("16,0 GB", cpu, SYSTEM_INFO_VIEW) == "none"


def test_a_slider_value_and_a_listed_state_answer() -> None:
    assert _judged("75", "abrir Configuración; y responder: decime el volumen", SOUND_VIEW) == "done"
    assert _judged("40", "abrir Configuración; y responder: decime el brillo", SOUND_VIEW) == "done"
    wifi = "abrir Configuración; y responder: a qué red wifi estoy conectado"
    assert _judged("MiCasa_5G", wifi, SOUND_VIEW) == "done"
    # Contracases: the other slider's value, the network beside which nothing says connected.
    assert _judged("40", "abrir Configuración; y responder: decime el volumen", SOUND_VIEW) == "none"
    assert _judged("Vecino_2G", wifi, SOUND_VIEW) == "none"


def test_a_yes_no_question_takes_the_mark_of_what_it_asks() -> None:
    goal = "ir a bluetooth y dispositivos; y responder: decime si el bluetooth está activado"
    off = _bluetooth_view("off", "on")
    assert _judged("Desactivado", goal, off) == "done"
    # The other switch's «Activado» is not the bluetooth's.
    assert _judged("Activado", goal, off) == "none"
    # Contracases: with the bluetooth on, its «Activado» answers and the other switch's «Desactivado» does not.
    on = _bluetooth_view("on", "off")
    assert _judged("Activado", goal, on) == "done"
    assert _judged("Desactivado", goal, on) == "none"
    assert _judged("Bluetooth Activado", goal, on) == "done"


# Revisión 2: the same question asked in Spanish («cuál está activa»), where the other control's participle
# («activado») begins like the mark asked («(activa)»). The live look writes the first network's link and the firewall's
# line one after the other (i 35, 36), so the line is read with the network.
FIREWALL_VIEW_LIVE = {
    **FIREWALL_VIEW,
    "controls": [
        {"i": 9, "kind": "ListItem", "name": "Firewall y protección de red", "state": "selected", "zone": "L"},
        {"i": 35, "kind": "Hyperlink", "name": "Red de dominio", "state": "focused", "zone": "TL"},
        {"i": 36, "kind": "Text", "name": "El firewall está activado.", "zone": "TL"},
        {"i": 40, "kind": "Hyperlink", "name": "Red privada", "zone": "L"},
        {"i": 41, "kind": "Text", "name": "El firewall está activado.", "zone": "L"},
    ],
}


def test_a_spanish_question_takes_the_mark_not_another_controls_participle() -> None:
    for asked in ("decime qué red está activa", "cuál red está activa", "decime cuál está activa"):
        goal = "ir a firewall y protección de red; y responder: " + asked
        for view in (FIREWALL_VIEW, FIREWALL_VIEW_LIVE):
            assert _judged("El firewall está activado.", goal, view) == "none", asked
            assert _judged("Red de dominio", goal, view) == "none", asked
            # Contracase: the network the window marks answers.
            assert _judged("Red privada (activa)", goal, view) == "done", asked
    # Contracase: asked whether the firewall is on, its «activado» answers it.
    on = "ir a firewall y protección de red; y responder: decime si el firewall está activado"
    assert _judged("El firewall está activado.", on, FIREWALL_VIEW_LIVE) == "done"


# Revisión 3 (s01): the calculator always writes «Separador decimal», and «decime» shares its root; the word with which
# the question asks for its answer is never what it asks about.
CALCULATOR_VIEW = {
    "window": {"title": "Calculadora", "process": "CalculatorApp"},
    "controls": [
        {"i": 3, "kind": "Text", "name": "La pantalla muestra 444", "zone": "TR"},
        {"i": 4, "kind": "Text", "name": "Expresión es 37 × 12=", "zone": "TR"},
        {"i": 5, "kind": "Text", "name": "Estándar", "zone": "TL"},
        {"i": 30, "kind": "Button", "name": "Separador decimal", "zone": "B"},
    ],
    "text": {},
}
CALCULATOR_HISTORY_VIEW = {
    **CALCULATOR_VIEW,
    "controls": [*CALCULATOR_VIEW["controls"], {"i": 40, "kind": "ListItem", "name": "37 × 12= 444", "zone": "R"}],
}


def test_the_word_that_asks_for_the_answer_is_no_root_of_the_question() -> None:
    mission = missions.mission_request("en la calculadora decime el resultado", APPS)
    assert mission is not None and not mission.steps
    assert mission.goal.endswith(missions.QUESTION_MARK + "decime el resultado")
    for asked in ("decime", "dime"):
        result = mission.goal.replace("decime", asked)
        assert _judged("La pantalla muestra 444", result, CALCULATOR_VIEW) == "done", asked
        assert _judged("444", result, CALCULATOR_VIEW) == "done", asked
        assert _judged("37 × 12= 444", f"ir a historial; y responder: {asked} cuál fue el último cálculo",
                       CALCULATOR_HISTORY_VIEW) == "done", asked
        assert _judged("Estándar", f"abrir Calculadora; y responder: {asked} en qué modo está",
                       CALCULATOR_VIEW) == "done", asked
        counted = mission.goal.replace("decime el resultado", f"{asked} qué cuenta quedó")
        assert _judged("Expresión es 37 × 12=", counted, CALCULATOR_VIEW) == "done", asked
    # Contracase: a question about the separator still finds it in the window, and another text does not answer it.
    separator = "abrir Calculadora; y responder: decime cuál es el separador decimal"
    assert _judged("Separador decimal", separator, CALCULATOR_VIEW) == "done"
    assert _judged("Estándar", separator, CALCULATOR_VIEW) == "none"
