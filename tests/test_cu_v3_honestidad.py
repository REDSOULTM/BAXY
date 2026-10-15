"""Revisión adversarial r10a de honestidad (C:/Users/usuario/AppData/Local/BAXY/cu-v3/r10a/rev_honestidad.md).

Cada hallazgo con su caso y su contracaso: «Ya estás en X» sin prueba, la relectura que atribuye cualquier página al
buscador, ítems inventados en la lectura de la búsqueda abierta, el libro de actos que aceptaba verbos con cualquier
tecla, la llegada por parecido contada como prueba fuerte, el «Abrí…» cuando la página ya estaba abierta y la prosa
de los finales en código.
"""

from __future__ import annotations

from baxy_mind import cu_validate
from baxy_mind import cu_finals
from baxy_mind import compose_instructions
from baxy_mind import compose_payload
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind import deterministic_finals
from baxy_mind import computer_use_finals
from baxy_mind.semantic import claims
from baxy_mind import compose_facts


def _mission(observed: dict, succeeded: bool = True) -> dict:
    return {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success" if succeeded else "failure",
        "verified": succeeded, "succeeded": succeeded, "cause": "mission_completed", "observed": observed,
    }


# ------------------------------------------------------------------ hallazgo 4: el libro de actos por tecla y etiqueta
_TYPED_THEN_TAB = _mission({
    "goal": "escribir hola", "application": "Bloc de notas", "reached": True, "satisfiedBy": "model_evidence",
    "steps": [
        {"operation": "input.text.type", "ok": True, "text": "hola"},
        {"operation": "input.key.press", "ok": True, "key": "tab"},
    ],
})


def test_any_key_no_longer_backs_saving_or_sending():
    for told in ("Escribí «hola» en el «Bloc de notas» y guardé el archivo.", "Escribí «hola» en el «Bloc de notas» y lo envié."):
        assert computer_use_finals._claims_defect(told, "status", _TYPED_THEN_TAB) == "unbacked_act"


def test_the_shortcut_pressed_backs_its_own_act():
    saved = _mission({**_TYPED_THEN_TAB["observed"], "steps": [
        {"operation": "input.text.type", "ok": True, "text": "hola"},
        {"operation": "input.key.press", "ok": True, "key": "ctrl_s"},
    ]})
    assert computer_use_finals._claims_defect("Escribí «hola» en el «Bloc de notas» y guardé el archivo.", "status", saved) == ""
    # Contracase: Ctrl+S backs saving, never sending.
    assert computer_use_finals._claims_defect("Escribí «hola» y lo envié.", "status", saved) == "unbacked_act"


def test_enter_backs_sending_only_towards_a_message_composer():
    def sent(target: dict) -> dict:
        return _mission({**_TYPED_THEN_TAB["observed"], "steps": [
            {"operation": "input.text.type", "ok": True, "text": "hola"},
            {"operation": "input.key.press", "ok": True, "key": "enter", **target},
        ]})

    assert computer_use_finals._claims_defect("Escribí «hola» y lo envié.", "status", sent({"target": "message_composer"})) == ""
    assert computer_use_finals._claims_defect("Escribí «hola» y lo envié.", "status", sent({})) == "unbacked_act"


def test_a_click_backs_the_act_its_label_says_and_no_other():
    def clicked(label: str, **extra: object) -> dict:
        return _mission({
            "goal": "ir a ajustes", "application": "Configuración", "reached": True, "satisfiedBy": "model_evidence",
            "steps": [{"operation": "input.visible.click", "ok": True, "label": label, **extra}],
        })

    assert computer_use_finals._claims_defect("Pulsé «Guardar» y guardé los cambios.", "status", clicked("Guardar")) == ""
    assert computer_use_finals._claims_defect("Acepté el aviso.", "status", clicked("OK")) == ""
    assert computer_use_finals._claims_defect("Apagué el Bluetooth.", "status", clicked("Pantalla")) == "unbacked_act"
    assert computer_use_finals._claims_defect("Acepté el aviso.", "status", clicked("Pantalla")) == "unbacked_act"
    # A switch the click moved backs turning it on or off.
    assert computer_use_finals._claims_defect("Apagué el Bluetooth.", "status", clicked("Bluetooth", toggled=True)) == ""


def test_a_strong_arrival_backs_its_goals_verb_and_still_judges_the_rest():
    strong = _mission({
        "goal": "ir a ajustes", "reached": True, "satisfiedBy": "control:Ajustes:current",
        "steps": [{"operation": "input.visible.click", "ok": True, "label": "Ajustes"}],
    })
    assert computer_use_finals._act_ledger(strong) is not None
    assert computer_use_finals._claims_defect("Fui a Ajustes, borré el historial y guardé los cambios.", "status", strong) == "unbacked_act"
    assert computer_use_finals._claims_defect("Fui a «Ajustes».", "status", strong) == ""


def test_goal_and_label_acts_read_data():
    assert {"crear", "agregar"} <= claims.goal_acts("crear una escena Pruebas")
    assert "encender" in claims.goal_acts("turn on the wifi")
    assert claims.goal_acts("la biblioteca") == frozenset()
    assert claims.label_acts("Cerrar sesión") == frozenset({"cerrar"})
    assert claims.label_acts("Biblioteca") == frozenset()


# ------------------------------------------------------------------ hallazgo 1: «Ya estás en X» sólo con prueba
_STEAM_STORE = {
    "window": {"title": "Steam"},
    "controls": [
        {"i": 0, "kind": "Button", "name": "TIENDA"}, {"i": 1, "kind": "Button", "name": "BIBLIOTECA"},
        {"i": 2, "kind": "Text", "name": "Ofertas especiales"},
    ],
    "text": {"lines": ["Ofertas especiales", "Destacados"]},
}
_LIBRARY_CHECK = "control:biblioteca:current|title:biblioteca|mark:biblioteca"


def _place(satisfied_by: str, already_running: bool | None, check: str = _LIBRARY_CHECK, steps: list | None = None) -> dict:
    opened: dict = {"operation": "app.open", "ok": True}
    if already_running is not None:
        opened["alreadyRunning"] = already_running
    return {
        "goal": "ir a la biblioteca", "application": "Steam", "reached": True, "satisfiedBy": satisfied_by,
        "successCheck": check, "steps": [opened, *(steps or [])], "window": {"title": "Steam"},
    }


def test_a_done_before_any_act_in_a_place_goal_with_a_check_presses_the_place():
    decided = cu_validate.validate_decision(
        {"act": "done", "evidence": "Destacados"}, view=_STEAM_STORE, last_failed=None, application_names=["Steam"],
        history=[{"operation": "app.open", "ok": True}], goal="ir a la biblioteca", objective="abrí la biblioteca de steam",
        success_check=_LIBRARY_CHECK, application="Steam",
    )
    assert decided["operation"] == "input.visible.click"
    assert decided["arguments"]["label"] == "BIBLIOTECA"


def test_contracase_a_done_after_an_act_or_without_a_check_stays_a_done():
    acted = cu_validate.validate_decision(
        {"act": "done", "evidence": "Destacados"}, view=_STEAM_STORE, last_failed=None, application_names=["Steam"],
        history=[{"operation": "input.visible.click", "ok": True, "label": "BIBLIOTECA"}], goal="ir a la biblioteca",
        success_check=_LIBRARY_CHECK, application="Steam",
    )
    assert acted["operation"] == "done"
    unchecked = cu_validate.validate_decision(
        {"act": "done", "evidence": "Destacados"}, view=_STEAM_STORE, last_failed=None, application_names=["Steam"],
        history=[], goal="ir a la biblioteca", success_check=None, application="Steam",
    )
    assert unchecked["operation"] == "done"


def test_already_there_needs_a_planned_strong_check_in_a_window_already_open():
    assert cu_finals.floor_sentence(_place("mark:biblioteca", True), False, True) == "Ya estás en «biblioteca»."
    # The model's evidence proves nothing: hedged, never «Ya estás en».
    assert cu_finals.floor_sentence(_place("model_evidence", True), False, True) == "Parece que ya estabas en «biblioteca»."
    # A term an alias renamed (not in the planned check) is no proof of «already».
    renamed = _place("control:==Biblioteca de música:current", True)
    assert cu_finals.floor_sentence(renamed, False, True).startswith("Parece que ya estabas")
    # An arrival by resemblance is weak.
    similar = _place("mark:biblioteca&similar:biblioteca", True, check="mark:biblioteca&similar:biblioteca")
    assert cu_finals.floor_sentence(similar, False, True).startswith("Parece que ya estabas")


def test_contracase_baxy_launched_the_application():
    # Opened by BAXY onto the place, with a strong check: the place reached, not «already».
    assert cu_finals.floor_sentence(_place("mark:biblioteca", False), False, True) == "Listo, estoy en «biblioteca»."
    assert cu_finals.floor_sentence(_place("mark:biblioteca", None), False, True) == "Listo, estoy en «biblioteca»."
    # Opened by BAXY, and only the model says it is there.
    assert cu_finals.floor_sentence(_place("model_evidence", False), False, True) == (
        "Parece que estás en «biblioteca»."
    )
    # An act on the way is the place reached, whatever proved it.
    clicked = [{"operation": "input.visible.click", "ok": True, "label": "BIBLIOTECA"}]
    assert cu_finals.floor_sentence(_place("model_evidence", True, steps=clicked), False, True) == "Listo, estoy en «biblioteca»."


# ------------------------------------------------------------------ hallazgo 2: la relectura es de la búsqueda abierta
_QUERY = "un top 3 peliculas de suspenso del 2026"
_SEARCH = {"site": "Google", "query": _QUERY}
_SEARCH_URL = "https://www.google.com/search?q=un+top+3+peliculas+de+suspenso+del+2026"
_SAID = "si pero quiero buscar un top 3"


def _search_on_show() -> object:
    from baxy_mind.semantic import dialogue

    state = dialogue.DialogueState()
    state.expect("Podrias buscarme en google " + _QUERY, ["browser.navigate"])
    state.told(
        {"kind": "operation", "operation": "browser.navigate", "polarity": "success", "verified": True,
         "succeeded": True, "observed": {"requestedUrl": _SEARCH_URL, "finalUrl": _SEARCH_URL}},
        "Abrí en Google la búsqueda.",
    )
    decided = {
        "type": "turn.result", "id": "9", "kind": "action", "operation": "browser.navigate",
        "intentOperations": ["browser.navigate"], "effectOperations": ["browser.navigate"],
        "objective": "Busca en Google un top 3 de películas de suspenso del 2026.", "question": "", "reply": "",
    }
    compose_facts._read_the_page_on_show(decided, {"id": "9", "text": _SAID}, state, {"browser.page.read": object(), "browser.navigate": object()})
    return state


def _read(url: str, title: str, text: str) -> dict:
    return {
        "kind": "operation", "operation": "browser.page.read", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"url": url, "title": title, "text": text},
    }


def test_another_page_in_front_is_not_told_as_the_search():

    state = _search_on_show()
    inbox = _read("https://mail.example.com/inbox", "Bandeja de entrada", "1. Factura luz 2. Reunión lunes 3. Banco")
    situation = compose_facts._with_listing_and_repetition_facts({"situation": inbox}, inbox, state, _SAID, _SAID)["situation"]
    assert "openSearch" not in situation
    assert situation["searchOutOfView"] == _SEARCH
    assert "Factura" not in str(situation) and "mail.example.com" not in str(situation)
    instruction = compose_instructions._compose_shape_instruction(situation, "es", _SAID)
    assert "no longer in front" in instruction and "give the top" not in instruction
    final = deterministic_finals._told_result_final(situation, {}, _SAID, "es")
    assert final.startswith(f"La búsqueda de «{_QUERY}» en Google ya no está al frente")
    again = deterministic_finals._told_result_final({**situation, "correctedFinal": {"previousReply": final}}, {}, _SAID, "es")
    assert again != final and _QUERY in again


def test_contracase_the_search_itself_in_front_is_read():

    state = _search_on_show()
    results = _read(_SEARCH_URL + "&sca_esv=1", _QUERY + " - Buscar con Google", "1. Sinners 2. Weapons 3. The Eyes")
    situation = compose_facts._with_listing_and_repetition_facts({"situation": results}, results, state, _SAID, _SAID)["situation"]
    assert situation["openSearch"] == _SEARCH and situation["askedCount"] == 3
    assert "searchOutOfView" not in situation


# ------------------------------------------------------------------ hallazgo 3: los ítems del «top N» salen de lo leído
def _open_search_read(text: str) -> dict:
    return {**_read(_SEARCH_URL, _QUERY + " - Buscar con Google", text), "openSearch": _SEARCH, "askedCount": 3}


def test_items_the_read_page_does_not_hold_are_refused():
    read = _open_search_read(
        "Todo Imágenes Videos Noticias. Las mejores películas de suspenso de 2026 según la crítica. Iniciar sesión"
    )
    payload = compose_payload._compose_situation_payload(read, "es", _SAID)
    for draft in (
        "Según la página " + _QUERY + " - Buscar con Google, el top 3 es: 1. Sinners 2. Weapons 3. The Eyes. Dice "
        "«Las mejores películas de suspenso de 2026 según la crítica».",
        "Según Google, el top 3 es Sinners, Weapons y The Eyes: «Las mejores películas de suspenso de 2026 según la crítica».",
    ):
        assert payload_fact_checks._payload_fact_defect(draft, payload, _SAID, said=_SAID) == "page_unread_item"


def test_contracase_items_the_page_lists_are_published():
    read = _open_search_read("Las mejores películas de suspenso de 2026: 1. Sinners 2. Weapons 3. The Eyes")
    payload = compose_payload._compose_situation_payload(read, "es", _SAID)
    draft = "Según Google, el top 3 es: 1. Sinners 2. Weapons 3. The Eyes. Dice «Las mejores películas de suspenso de 2026»."
    assert payload_fact_checks._payload_fact_defect(draft, payload, _SAID, said=_SAID) == ""


# ------------------------------------------------------------------ hallazgo 6: ya estaba abierta, no «Abrí»
def _navigated(authority: str) -> dict:
    return {
        "kind": "operation", "operation": "browser.navigate", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"requestedUrl": _SEARCH_URL, "finalUrl": _SEARCH_URL, "browser": "Opera GX", "authority": authority},
    }


def test_a_search_already_on_show_is_not_told_as_opened():
    final = deterministic_finals._told_result_final(_navigated("user_browser_front_already_showed"), {}, _SAID, "es")
    assert final == f"La búsqueda de «{_QUERY}» en Google ya estaba abierta en tu navegador."
    assert not final.startswith("Abrí")


def test_contracase_a_search_seen_opening_is_told_as_opened():
    final = deterministic_finals._told_result_final(_navigated("user_browser_uia_address_postread"), {}, _SAID, "es")
    assert final == f"Abrí en Google la búsqueda de «{_QUERY}» en tu navegador."


# ------------------------------------------------------------------ hallazgo 7: buscadores y plantillas en datos
def test_search_engines_are_data():
    from baxy_mind.semantic.search_address import search_of_address

    assert search_of_address(_SEARCH_URL) == ("Google", _QUERY)
    assert search_of_address("https://duckduckgo.com/?q=clima+nunoa") == ("DuckDuckGo", "clima nunoa")
    assert search_of_address("https://www.youtube.com/results?search_query=lofi") == ("YouTube", "lofi")
    # Contracase: a page of the same site that is no results page, and a look-alike host.
    assert search_of_address("https://www.google.com/maps?q=nunoa") is None
    assert search_of_address("https://notgoogle.com/search?q=x") is None


def test_the_web_search_finals_are_data():
    import inspect

    source = inspect.getsource(deterministic_finals._open_search_final) + inspect.getsource(deterministic_finals._told_result_final)
    assert "está abierta en tu navegador" not in source and "Abrí en {site}" not in source


# ------------------------------------------------------------------ revisión de los arreglos (contexto nuevo)
def test_a_read_without_its_address_is_the_search_only_when_its_title_says_the_words():
    # The receipt's «url» is empty when the address field could not be read (UserBrowserSurface.ReadPageAsync).

    state = _search_on_show()
    inbox = _read("", "Bandeja de entrada", "1. Factura luz 2. Reunión lunes 3. Banco")
    situation = compose_facts._with_listing_and_repetition_facts({"situation": inbox}, inbox, state, _SAID, _SAID)["situation"]
    assert "openSearch" not in situation and situation["searchOutOfView"] == _SEARCH
    assert "Factura" not in str(situation)
    # Contracase: the results page titled with the words searched is the search.
    state = _search_on_show()
    results = _read("", _QUERY + " - Buscar con Google", "1. Sinners 2. Weapons 3. The Eyes")
    situation = compose_facts._with_listing_and_repetition_facts({"situation": results}, results, state, _SAID, _SAID)["situation"]
    assert situation["openSearch"] == _SEARCH and "searchOutOfView" not in situation


def test_a_page_already_on_show_is_never_told_as_opened_by_a_draft():
    said = "buscame en google " + _QUERY
    shown = _navigated("user_browser_front_already_showed")
    opened = f"Abrí en Google la búsqueda de «{_QUERY}» en tu navegador."
    assert visible_defect.compose_visible_defect(opened, "status", said, {"situation": shown}, said=said) == "unstated_already_shown"
    # Its own final («ya estaba abierta») is the fact, not an invented prior state.
    final = deterministic_finals._told_result_final(shown, {}, said, "es")
    assert visible_defect.compose_visible_defect(final, "status", said, {"situation": shown}, said=said) == ""
    # Contracase: a page seen opening is still never told as already open.
    seen = _navigated("user_browser_uia_address_postread")
    assert visible_defect.compose_visible_defect(final, "status", said, {"situation": seen}, said=said) == "invented_prior_open_state"
    assert visible_defect.compose_visible_defect(opened, "status", said, {"situation": seen}, said=said) == ""


def test_the_close_sign_and_the_opener_keys_back_their_acts():
    def one(step: dict) -> dict:
        return _mission({"goal": "cerrar el aviso", "reached": True, "satisfiedBy": "model_evidence", "steps": [step]})

    assert computer_use_finals._claims_defect("Cerré el aviso.", "status", one({"operation": "input.visible.click", "ok": True, "label": "×"})) == ""
    assert computer_use_finals._claims_defect(
        "Abrí el Administrador de tareas.", "status", one({"operation": "input.key.press", "ok": True, "key": "ctrl_shift_escape"})
    ) == ""
    # Contracase: the sign backs closing, nothing else.
    assert computer_use_finals._claims_defect("Guardé el aviso.", "status", one({"operation": "input.visible.click", "ok": True, "label": "×"})) == "unbacked_act"
