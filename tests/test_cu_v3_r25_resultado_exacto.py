"""Ronda 25 (libro de cuentas §4.3): el resultado y el eco se leen con una sola prueba.

Nombre exacto; el nombre como palabras enteras sólo en una entrada corta de una lista, un enlace o un menú, o en una
línea corta que apareció con el acto; una errata sólo en la única entrada así nombrada. Nunca el eco de lo tecleado ni
del valor de un campo. Casos del banco r23: c7, n5, s04, s13 y u1.
"""

from __future__ import annotations

from baxy_mind import cu_view
from baxy_mind import cu_lookup


def _typed(text: str) -> list[dict]:
    return [{"step": 1, "operation": "input.text.type", "text": text, "ok": True}]


def _view(*controls: dict, lines: list[str] | None = None, new: list[str] | None = None) -> dict:
    view = {
        "window": {"title": "Ventana", "process": "app"},
        "controls": [{"i": index, **control} for index, control in enumerate(controls)],
        "text": {"C": lines or []},
    }
    if new is not None:
        view["newText"] = new
    return view


def _label(step: dict | None) -> str | None:
    return None if step is None else step["arguments"]["label"]


# ------------------------------------------------ n5: una frase que menciona el nombre no es el lugar


_PROXY = [
    "Usa un servidor proxy para conexiones Ethernet o Wi-Fi. Esta configuración no se aplica a las conexiones VPN.",
    "Servidor proxy para las conexiones Wi-Fi y Ethernet",
]


def test_n5_a_sentence_that_mentions_the_place_is_no_written_place() -> None:
    assert cu_view._text_line_with(_view(lines=_PROXY), "Wi-Fi") is None


def test_n5_counter_case_the_line_that_is_the_place_is_written() -> None:
    assert cu_view._text_line_with(_view(lines=[*_PROXY, "Wi-Fi"]), "Wi-Fi") == "Wi-Fi"
    # The OCR reads the window twice: a misread line seen twice is still the only one.
    assert cu_view._text_line_with(_view(lines=["Wi-Fl", "Wi-Fl"]), "Wi-Fi") == "Wi-Fl"


def test_n5_a_description_after_typing_is_no_result() -> None:
    view = _view(
        {"kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "value": "wi-fi"},
        *({"kind": "Text", "name": line} for line in _PROXY),
        lines=_PROXY, new=_PROXY,
    )
    assert cu_lookup._result_naming(view, "wi-fi", _typed("wi-fi")) is None


# ------------------------------------------------ u1: un botón que sólo menciona el nombre no es el resultado


def test_u1_a_button_already_there_that_mentions_the_place_is_no_result() -> None:
    view = _view(
        {"kind": "ComboBox", "name": "¿Qué quieres reproducir?", "value": "tu biblioteca"},
        {"kind": "Button", "name": "Comprimir Tu biblioteca"},
        {"kind": "Button", "name": "Abre Tu biblioteca"},
        new=["tu biblioteca"],
    )
    assert cu_lookup._result_naming(view, "tu biblioteca", _typed("tu biblioteca")) is None
    # Counter-case: the button that came with the search holds the name and is its result.
    view["newText"].append("Abre Tu biblioteca")
    assert _label(cu_lookup._result_naming(view, "tu biblioteca", _typed("tu biblioteca"))) == "Abre Tu biblioteca"


def test_u1_counter_case_the_entry_named_so_is_the_result() -> None:
    view = _view(
        {"kind": "Button", "name": "Comprimir Tu biblioteca"},
        {"kind": "ListItem", "name": "Tu biblioteca"},
    )
    assert _label(cu_lookup._result_naming(view, "tu biblioteca", _typed("tu biblioteca"))) == "Tu biblioteca"


# ------------------------------------------------ s04: la pestaña que repite la consulta no es resultado


def test_s04_the_tab_that_repeats_the_query_is_no_result() -> None:
    view = _view({"kind": "TabItem", "name": "descargas - Resultados de la búsqueda en Este equipo"})
    assert cu_lookup._result_naming(view, "descargas", _typed("descargas")) is None


def test_s04_counter_case_an_entry_of_the_results_that_holds_the_name_is_a_result() -> None:
    view = _view(
        {"kind": "TabItem", "name": "descargas - Resultados de la búsqueda en Este equipo"},
        {"kind": "ListItem", "name": "Descargas (C:)"},
    )
    assert _label(cu_lookup._result_naming(view, "descargas", _typed("descargas"))) == "Descargas (C:)"


# ------------------------------------------------ c7 y s13: el eco del campo, aunque el OCR lo lea con errata


def _discord(*more: dict, new: list[str] | None = None) -> dict:
    return _view(
        {"kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "value": "cotele"},
        {"kind": "Text", "name": "cotele"},
        *more,
        lines=["cotele", *(new or [])], new=new,
    )


def test_c7_the_text_a_search_box_draws_with_its_value_is_no_result() -> None:
    assert cu_lookup._result_naming(_discord(), "cotele", _typed("cotele")) is None


def test_s13_a_line_that_misreads_the_name_is_never_its_result() -> None:
    assert cu_lookup._result_naming(_discord(new=["cotete"]), "cotele", _typed("cotele")) is None


def test_c7_counter_case_the_channel_entry_is_the_result() -> None:
    view = _discord({"kind": "ListItem", "name": "Cotele!!!, Canal de voz"})
    assert _label(cu_lookup._result_naming(view, "cotele", _typed("cotele"))) == "Cotele!!!, Canal de voz"


def test_counter_case_the_persons_typo_is_mended_by_the_one_entry_named_so() -> None:
    # «lo mal dicho lo arregla BAXY» (2026-09-19): the person's typo still reaches the one entry it names.
    one = _view({"kind": "ListItem", "name": "Cotele"})
    assert _label(cu_lookup._result_naming(one, "cotle", _typed("cotle"))) == "Cotele"
    two = _view({"kind": "ListItem", "name": "Cotele"}, {"kind": "ListItem", "name": "Cotle2"})
    assert cu_lookup._result_naming(two, "cotle", _typed("cotle")) is None


def test_c7_counter_case_the_echo_beside_the_glyph_and_a_button_named_by_typo_are_no_result() -> None:
    # Twins of SearchBurstTests: «Q cotele» is the box's echo; a typo reaches only an entry of a list.
    assert cu_lookup._result_naming(_view({"kind": "Text", "name": "Q cotele"}), "cotele", _typed("cotele")) is None
    assert cu_lookup._result_naming(_view({"kind": "Button", "name": "Cotele"}), "cotle", _typed("cotle")) is None


# ------------------------------------------------ revisión: la prueba de foco de la caja escrita no se debilita


_PROMPT = "Buscar por nombre"


def test_g_a_placeholder_inside_a_longer_line_is_still_on_screen() -> None:
    view = _view(lines=["Página principal Colecciones Q Buscar por nombre Avanzado Juegos recientes Ver todo"], new=[])
    assert cu_lookup._written_box_took_keyboard(view, _PROMPT) is False


def test_h_a_placeholder_misread_twice_differently_is_still_on_screen() -> None:
    view = _view(lines=["Buscar por nonbre", "Buscar par nombre", "Biblioteca"], new=[])
    assert cu_lookup._written_box_took_keyboard(view, _PROMPT) is False


def test_counter_case_a_placeholder_cleared_for_the_caret_proves_the_keyboard() -> None:
    view = _view(lines=["Página principal", "Colecciones", "Biblioteca"], new=[])
    assert cu_lookup._written_box_took_keyboard(view, _PROMPT) is True
