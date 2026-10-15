"""Ronda 19 de uso real v3 (r17 t3): lectores que se disparaban por una palabra suelta.

c03/1 «dame 5 juegos … en la pc» → system.status; c14/1 «dame 3 recetas rapidas con atun y arroz» → web.search de
un «plato»; c16/4 «cómo se llamaba el que cantaba» → la búsqueda sin el artista que se vio; c17/4 «buscalo en google
pa poder citarlo» → una pregunta por la URL (sólo la finalidad tras el lugar; sin búsqueda previa decide el decisor).
Cada arreglo lleva su contracaso.
"""

import pytest

from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.semantic import dialogue, knowledge
from baxy_mind import turn_decide


# (a) system.status sólo cuando lo observado es la máquina o su estado.
@pytest.mark.parametrize("text", [
    "dame 5 juegos cooperativos pa jugar con mis primos en la pc que no pidan mucha compu",
    "dame 5 ideas para mi computador",
    "decime 3 juegos que corran en mi pc",
    "show me 5 coop games for my pc",
    "dame juegos para la pc que no pidan mucha ram",
    "mostrame juegos livianos en la pc",
    "recomiendame 3 juegos para mi pc",
])
def test_things_asked_for_the_machine_are_no_reading_of_it(text):
    found = resolve_explicit_effects(text, {"system.status", "web.search", "app.open"})
    assert found is None or "system.status" not in found.operations


@pytest.mark.parametrize("text", [
    "decime cómo está la pc",
    "dame el uso de RAM de la pc",
    "dame el estado de la pc",
    "dame la batería",
    "mostrame la pc",
    "dame info de mi pc",
    "dime cuánta ram tiene la pc",
    # Revisión adversarial 3 (B1): «del» lleva su artículo; lo que va antes es de la máquina.
    "mostrame la tarjeta gráfica del computador",
    "dame la tarjeta de video del notebook",
    "dame los núcleos del procesador del equipo",
    "dame la marca del computador",
    "dame la bios del equipo",
    "dame los drivers del equipo",
    "dame la placa del equipo",
    "mostrame la tarjeta gráfica de la pc",
    "dame los núcleos del procesador de la pc",
])
def test_the_machine_or_its_state_asked_is_still_read(text):
    found = resolve_explicit_effects(text, {"system.status", "web.search", "app.open"})
    assert found is not None and found.operations == ("system.status",)


# (b) una categoría en plural o «con X y Y» no nombra un plato.
@pytest.mark.parametrize("text", [
    "dame 3 recetas rapidas con atun y arroz q tengo poca plata",
    "dame recetas con atun y arroz",
    "3 recetas baratas con pollo",
])
def test_recipe_ideas_without_a_dish_are_talk(text):
    assert knowledge.reference_lookup(text) is None


@pytest.mark.parametrize("text,dish", [
    ("receta del arroz con leche", "arroz con leche"),
    # «how do you make shepherd's pie» ya no era búsqueda antes de esta ronda (M118 pide la cocina dicha y el
    # apóstrofo corta el plato); el contracaso inglés usa la forma que M118 ya lee.
    ("how do you make pancakes? I only have eggs and flour", "pancakes"),
    ("dame la receta de pan amasado", "pan amasado"),
])
def test_a_named_dish_is_still_looked_up(text, dish):
    found = knowledge.reference_lookup(text)
    assert found is not None and found.kind == "recipe" and dish in found.subject


# Revisión adversarial 3 (B2): un calificativo antes de un plato con nombre se quita del plato; el plato se sigue
# buscando (M53/D35), nunca se recita.
@pytest.mark.parametrize("text,dish,query", [
    ("dame la receta de una buena paella", "paella", "receta paella"),
    ("receta de unas buenas empanadas de pino", "empanadas de pino", "receta empanadas de pino"),
    ("dame la receta de una sencilla tortilla de papas", "tortilla de papas", "receta tortilla de papas"),
    ("receta de una ligera ensalada cesar", "ensalada cesar", "receta ensalada cesar"),
    ("quiero hacer una buena carbonara, receta?", "carbonara", "receta carbonara"),
    ("recipe for a cheap lasagna", "lasagna", "recipe lasagna"),
    ("how do you make budget chili? recipe pls", "chili", "recipe chili"),
])
def test_a_qualifier_before_a_named_dish_is_dropped_not_the_search(text, dish, query):
    found = knowledge.reference_lookup(text)
    assert found is not None and found.kind == "recipe"
    assert found.subject == dish and found.query == query


@pytest.mark.parametrize("text", ["dame recetas faciles", "dame recetas sanas con pollo", "receta de comida china"])
def test_a_qualifier_alone_or_before_a_joining_word_names_no_dish(text):
    assert knowledge.reference_lookup(text) is None


# (c) el rol de una persona lleva lo que la conversación mostró.
SHOWN = ("Está sonando «Soda Stereo - De Musica Ligera (El Último Concierto)» en YouTube.", "¿Cuánto le subo?")


def test_role_holder_carries_the_title_that_was_shown():
    found = knowledge.reference_lookup(
        "¿Cómo se llamaba el que cantaba en «De Música Ligera»?",
        ("poneme algo de Soda Stereo", "no, en YouTube", "subile un poco más"),
        SHOWN[-1],
        SHOWN,
    )
    assert found is not None and found.kind == "person"
    assert "Soda Stereo" in found.query and "De Música Ligera" in found.query
    assert "Concierto" not in found.query


def test_role_holder_with_nothing_shown_is_unchanged():
    found = knowledge.reference_lookup("¿quién es el cantante de Soda Stereo?", (), "", ())
    assert found is not None and found.query == "cantante de Soda Stereo"
    unrelated = knowledge.reference_lookup("¿quién es el cantante de Soda Stereo?", (), "", ("Puse «Bohemian Rhapsody».",))
    assert unrelated is not None and unrelated.query == "cantante de Soda Stereo"


# Revisión adversarial 3 (B3): sólo un título «quién - obra» cuya obra es todo el nombre preguntado añade a quien la
# hace; una nota guardada es privada y nunca llega a una búsqueda, y un título que sólo contiene el nombre es otra obra.
@pytest.mark.parametrize("text,reply,query", [
    ("quién es el cantante de Los Prisioneros?",
     'Guardé la nota "comprar entradas para Los Prisioneros el sábado y pasar por el banco".',
     "cantante de Prisioneros"),
    ("¿quién es el cantante de Queen?", "Está sonando «Queen of the South - Temporada 2 Tráiler»", "cantante de Queen"),
    ("¿quién es el director de Oppenheimer?", "Está sonando «Oppenheimer | Tráiler Oficial 2 (Universal Pictures) HD»",
     "director de Oppenheimer"),
    ("quién es el cantante de Queen", "Puse «Queen - Bohemian Rhapsody (Official Video)».", "cantante de Queen"),
    ("quién es el cantante de Bohemian Rhapsody", "Puse «Queen - Bohemian Rhapsody (Official Video)».",
     "cantante de Bohemian Rhapsody Queen"),
])
def test_only_the_performer_of_the_whole_work_is_added(text, reply, query):
    found = knowledge.reference_lookup(text, (), reply, (reply,))
    assert found is not None and found.kind == "person" and found.query == query


def test_who_sings_this_is_left_to_what_plays():
    # «quién canta esta» names no work: what is playing answers it, not a role lookup.
    assert knowledge.reference_lookup("quién canta esta", (), "", SHOWN) is None


# (d) «búscalo en google pa…»: la finalidad tras el lugar no es lo buscado; con una búsqueda previa se abre esa.
#
# Revisión adversarial 2: tomar sin búsqueda previa el tema de un pedido anterior de la persona (talked_subject) buscaba
# temas viejos o que no lo eran («ti», «razones», «lo que tengo abierto») y preguntaba de más cuando BAXY ya había
# respondido; se retiró. Sin nada buscado, el turno sigue como en la base: va al decisor con toda la conversación.
TOPIC = "causas de la primera guerra mundial"


def _searched_state() -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(TOPIC, ["web.search"])
    state.record({
        "kind": "operation", "operation": "web.search", "verified": True, "succeeded": True, "polarity": "success",
        "observed": {"query": TOPIC, "count": 1, "results": [{"title": "Primera Guerra Mundial", "url": "https://example.org/0"}],
                     "observedAtUtc": "2026-10-09T03:00:00Z"},
    })
    return state


@pytest.mark.parametrize("text", [
    "buscalo en google pa poder citarlo",
    "búscalo en google para verlo",
    "búscalo en google para que lo vea",
    "búscalo en google para leer sobre eso",
    "search it on google so I can cite it",
    "search it on google so that I can read it",
    "search it on google to cite it",
])
def test_a_purpose_after_the_place_searches_what_was_searched(text):
    rewritten = _searched_state().searched_in_place(text)
    assert rewritten is not None and rewritten.endswith(TOPIC)


# Revisión adversarial 3 (B4): «para» con un nombre califica lo buscado («para windows 11»); el turno sigue como en la
# base, con el decisor y la conversación. «pa la tarea» queda igual que en la base: la regla no separa una finalidad
# nominal de un calificativo nominal («para la ps5»).
@pytest.mark.parametrize("topic,text", [
    ("drivers de la impresora hp", "búscalo en google para windows 11"),
    ("whatsapp", "búscalo en google para android"),
    ("whatsapp", "búscalo en google para mac"),
    ("fifa 24", "búscalo en google para la ps5"),
    (TOPIC, "búscalo en google pa la tarea"),
])
def test_a_qualifier_after_the_place_is_not_dropped(topic, text):
    state = dialogue.DialogueState()
    state.expect(topic, ["web.search"])
    state.record({
        "kind": "operation", "operation": "web.search", "verified": True, "succeeded": True, "polarity": "success",
        "observed": {"query": topic, "count": 1, "results": [{"title": topic, "url": "https://example.org/0"}],
                     "observedAtUtc": "2026-10-09T03:00:00Z"},
    })
    assert state.searched_in_place(text) is None


def test_pronoun_search_at_the_start_has_nothing_to_search():
    state = dialogue.DialogueState()
    assert state.searched_in_place("buscalo en google") is None
    assert state.searched_in_place("buscalo en google pa poder citarlo") is None


@pytest.mark.parametrize("text", ["no lo busques en google", "busca en google el estreno de Dune"])
def test_forbidden_or_named_searches_are_not_rewritten(text):
    assert _searched_state().searched_in_place(text) is None


def _talk(*said):
    return [{"role": "user" if index % 2 == 0 else "assistant", "content": text} for index, text in enumerate(said)]


# Cada sonda de la revisión adversarial 2: sin búsqueda previa, nada se reescribe ni se pregunta antes del decisor.
UNSEARCHED = [
    # B1: un pedido con tema que no se lee no deja buscar uno más viejo.
    (_talk("qué es la fotosíntesis", "Es el proceso…", "pon música de soda stereo",
           "Está sonando «Soda Stereo - De Música Ligera» en YouTube."), "búscalo en google"),
    (_talk("qué es la fotosíntesis", "Es el proceso…", "y quién la descubrió?", "Jan Ingenhousz en 1779."),
     "búscalo en google"),
    (_talk("háblame de la revolución francesa", "La Revolución francesa…", "dame el nombre del rey que guillotinaron",
           "Luis XVI."), "búscalo en google pa la tarea"),
    (_talk("dame 3 recetas rapidas con atun y arroz", "1. …", "la segunda", "Ensalada de atún y arroz…"),
     "búscalo en google"),
    # B2: lo buscado está en lo que BAXY respondió.
    (_talk("cuánto mide el everest", "8.849 m."), "búscalo en google"),
    (_talk("quién ganó el mundial 2010", "España."), "búscalo en google"),
    (_talk("recomiéndame una película de ciencia ficción", "Te recomiendo «Interstellar» (2014)…"),
     "búscalo en google"),
    (_talk("recommend me a sci-fi movie", "I'd go with «Interstellar»…"), "search it on google"),
    (_talk("qué opinas de la última película de Nolan", "Oppenheimer me parece…"), "búscalo en google"),
    # B3: lo que no es tema.
    (_talk("háblame de ti", "Soy BAXY…"), "búscalo en google"),
    (_talk("dame 4 razones para dormir temprano", "1. …"), "búscalo en google"),
    (_talk("explícame por qué no funcionó", "…"), "búscalo en google"),
    (_talk("qué es lo que tengo abierto", "…"), "búscalo en google"),
    (_talk("dame 2 juegos para mi pc", "…"), "búscalo en google pa verlos"),
    (_talk("what is going on", "…"), "search it on google"),
    (_talk("dame 3 opciones", "…"), "búscalo en google"),
    (_talk("dime cosas", "…"), "búscalo en google"),
    (_talk("qué alarmas tengo", "…"), "búscalo en google"),
    (_talk("what's the weather like", "…"), "search it on google"),
    (_talk("cuál es tu nombre", "Soy BAXY."), "búscalo en google"),
    (_talk("cómo estuvo tu día", "…"), "búscalo en google"),
    (_talk("háblame de su vida", "…"), "búscalo en google"),
    (_talk("repite lo último que te dije", "…"), "búscalo en google"),
    (_talk("qué hace este botón", "…"), "búscalo en google"),
    (_talk("tell me why you closed chrome", "…"), "search it on google"),
]


@pytest.mark.parametrize("history,text", UNSEARCHED)
def test_with_nothing_searched_the_pronoun_goes_to_the_decider_with_the_conversation(monkeypatch, history, text):
    decided: list[dict] = []

    def _decided(message, **_):
        decided.append(message)
        return {"type": "turn.result", "id": message.get("id"), "kind": "answer", "operation": None, "reply": "…"}

    monkeypatch.setattr(turn_decide, "_decide_turn_result", _decided)
    assert dialogue.DialogueState().searched_in_place(text) is None
    turn = history + [{"role": "user", "content": text}]
    result = turn_decide._prepare_turn_result(
        {"id": "t1", "text": text, "history": turn},
        llm=None, planner_catalog=None, encoder=None, tool_by_name={}, dialogue_state=dialogue.DialogueState(),
    )
    assert result["kind"] == "answer" and "turn_recovery" not in result
    assert [message["text"] for message in decided] == [text]
    assert decided[0]["history"] == turn
