"""ING6 (`w2a-APP_INVENTADA-13`, INT36A §4.4): «mute Yalimbe real quick» in a turn with no call → «No puedo silenciar
aplicaciones que no están instaladas en este PC»: BAXY denies an act a tool of the catalog does (audio_mute, by the
application's name) and gives as its reason an absence nothing read. The rule «denial» read neither: silencing was no
act of its table (the answer fell to «denial_lookup», whose fact is what web_search reaches), and «no están instaladas»
counted as a limit of the tools although no call of the conversation had looked. An absence is a reading: it excuses
the denial only when some call of the conversation may have read it."""
import pytest

from baxy_mind.answer_check import check

CATALOG = {
    "audio.mute": "Mute or unmute sound output: all of the PC's sound (scope pc: the speakers, headphones or headset), or "
                  "one application's own sound (scope app, with its name in app; the rest keeps sounding). Use when: "
                  "silencia, mutea or quita el silencio.",
    "file.open": "Open a specific file by its name from a known folder with its default app.",
    "file.find": "List the top level of a known folder, or find files under it by name. Use when: busca un archivo.",
    "web.search": "Search the web.",
}


def _found(answer: str, tries: list | None = None, catalog: dict | None = None) -> list[dict]:
    return [f for f in check(answer, "", [], [], catalog=CATALOG if catalog is None else catalog, tries=tries or [])
            if f["rule"] in ("denial", "denial_lookup")]


@pytest.mark.parametrize("answer", [
    # The answers of INT36A's arm z (ing5-voz alone), seeds 0, 3, 7, 8 and 9: nothing was called in the turn.
    "No puedo silenciar aplicaciones que no están instaladas en este PC. ¿Te refieres a Yalimbe como una aplicación "
    "específica o es un error de nombre?",
    "No puedo silenciar aplicaciones que no están instaladas. ¿Te refieres a \"Spotify\" o a otra aplicación específica?",
    "No puedo silenciar aplicaciones que no están en la lista de aplicaciones de audio.",
    "No puedo mutear el sonido de una app que no encontré.",
    "I can't mute apps that are not installed on this PC.",
    "I can't silence an application that was not found.",
])
def test_silencing_denied_with_no_call_names_the_tool_that_silences(answer: str) -> None:
    found = _found(answer)
    assert [f["rule"] for f in found] == ["denial"]
    assert "audio_mute" in found[0]["fact"]
    assert CATALOG["audio.mute"].split(". ")[0] in found[0]["fact"]


@pytest.mark.parametrize("answer", [
    # ING6B: answers of the row with no absence said (arm ck, seeds 9 and 35, and others of its 40). Sent back as a
    # «denial» with audio_mute's sentence, the model answered «Silencio el sonido del PC.» with no call, 2 of 2 times.
    "No puedo silenciar aplicaciones llamadas \"Yalimbe\". ¿Te refieres a otra aplicación?",
    "No puedo silenciar aplicaciones ni dispositivos de audio específicos con ese nombre.",
    "I can't mute an app called Yalimbe.",
])
def test_a_plain_refusal_to_silence_is_read_as_before_ing6(answer: str) -> None:
    assert [f["rule"] for f in _found(answer)] == ["denial_lookup"]


def test_an_absence_nothing_read_excuses_no_denial_of_another_act_either() -> None:
    found = _found("No puedo abrir el archivo zarpazo.docx porque no lo encontré.")
    assert [f["rule"] for f in found] == ["denial"]
    assert "file_open" in found[0]["fact"]


@pytest.mark.parametrize("answer", [
    "No puedo silenciar aplicaciones que no están instaladas en este PC.",
    "No puedo abrir el archivo zarpazo.docx porque no lo encontré.",
])
def test_an_absence_holds_when_a_call_of_the_conversation_may_have_read_it(answer: str) -> None:
    # Any earlier call: what it read is not known here, so the answer may be telling it.
    assert _found(answer, tries=[("app.list", "completed")]) == []


@pytest.mark.parametrize("answer", [
    # A condition, a policy limit, a question, no act of the PC: as before.
    "No puedo silenciar la aplicación si no me dices cuál es.",
    "No puedo silenciar esa aplicación sin que lo confirmes.",
    "¿No puedo silenciar aplicaciones?",
    "No puedo silenciar a tu vecino.",
    "No silencié ninguna aplicación.",
    "Puedo silenciar la aplicación si quieres.",
])
def test_conditions_limits_and_what_is_no_sound_of_the_pc_are_not_a_denial(answer: str) -> None:
    assert [f for f in _found(answer) if f["rule"] == "denial"] == []


def test_the_answer_that_says_it_does_not_know_which_application_is_read_as_before() -> None:
    # The 1.5.2's own answer (arm d, 7 of 10): it denies nothing of the tools, it says it does not know the name.
    answer = "No puedo silenciar \"Yalimbe\" porque no sé qué aplicación es ni cómo se llama realmente."
    assert [f["rule"] for f in _found(answer)] == ["denial_lookup"]


def test_an_absence_nothing_read_adds_no_lookup_where_no_tool_does_the_act() -> None:
    # «denial_lookup» (what web_search reaches) is no answer to an absence: where the table has no tool for the act,
    # the sentence is read as it was (nothing found).
    assert _found("No puedo abrirlo: DaVinci Resolve no aparece en el catálogo de programas de Windows.") == []
    assert _found("No puedo pedir pizza: la aplicación no está instalada.") == []


def test_without_the_tool_in_the_catalog_there_is_no_denial() -> None:
    catalog = {k: v for k, v in CATALOG.items() if k != "audio.mute"}
    found = _found("No puedo silenciar aplicaciones que no están en la lista de aplicaciones de audio.", catalog=catalog)
    assert [f for f in found if f["rule"] == "denial"] == []


def test_an_earlier_try_to_silence_that_did_not_complete_may_be_what_it_tells() -> None:
    found = _found("No puedo silenciar aplicaciones con ese nombre.", tries=[("audio.mute", "failed")])
    assert [f for f in found if f["rule"] == "denial"] == []
