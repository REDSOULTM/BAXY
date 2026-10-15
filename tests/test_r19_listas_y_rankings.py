"""Ronda 19 «listas-y-rankings»: counted lists are counted and served as asked (uso real v3, tandas r17 t1–t3).

Each failed turn with its real text, and the counter-cases that must stay as they are.
"""

from __future__ import annotations

import pytest

from baxy_mind import conversation_shape
from baxy_mind import previous_answer
from baxy_mind.semantic import listing
from baxy_mind import argument_grounding

FIVE_IDEAS = (
    "1. **Pollo al curry rápido**: Corta el pollo en cubos, saltea con ajo y comino.\n\n"
    "2. **Arroz con pollo y frijoles**: En una sartén, cocina el pollo con cebolla.\n\n"
    "3. **Pollo salteado con arroz y verduras**: Saltea tiras de pollo con pimientos.\n\n"
    "4. **Arroz con pollo y plátano**: Cocina el pollo en salsa de tomate y ajo.\n\n"
    "5. **Pollo al horno con arroz y espinacas**: Precalienta el horno a 200°C."
)
FOUR_GAMES = (
    "Puedes probar con Among Us, Garry's Mod, Portal 2 o Minecraft, que son ligeros y funcionan bien en tu equipo."
)
CAUSES = (
    "Las cuatro causas principales fueron el nacionalismo, los alianzas europeas, el nacionalismo eslavo y el "
    "imperialismo."
)


# --- (a) the inline list is counted when a number was asked ---------------------------------------------------------


def test_inline_list_counted_only_when_a_number_was_asked() -> None:
    # r17 t3-c03/1: four games for five.
    assert listing.listed_items(FOUR_GAMES) == ("Among Us", "Garry's Mod", "Portal 2", "Minecraft")
    assert listing.items_listed(FOUR_GAMES, counted=True) == 4
    assert listing.items_listed(FOUR_GAMES) is None  # no number asked: a clause is not told from a list
    # r17 t2-c09: the four named are four.
    assert listing.items_listed("Los cuatro países son Bolivia, Paraguay, Perú y Uruguay.", counted=True) == 4


def test_numbered_list_items_are_named() -> None:
    assert listing.listed_items(FIVE_IDEAS)[1] == "Arroz con pollo y frijoles"
    assert listing.items_listed(FIVE_IDEAS) == 5


def test_two_names_said_in_a_sentence_are_no_list() -> None:
    # Counter-case: «Abrí Notas y Calculadora» is no list, even counted.
    assert listing.listed_items("Abrí Notas y Calculadora.") == ()
    assert listing.items_listed("Abrí Notas y Calculadora.", counted=True) is None


def test_a_span_of_time_is_no_list() -> None:
    assert listing.enumeration_asked("dame 5 minutos") is None
    assert listing.enumeration_asked("dame un segundo") is None


def test_one_item_said_twice_is_repeated() -> None:
    items = ("el nacionalismo", "las alianzas", "nacionalismo", "el imperialismo")
    assert listing.repeated_items(items) == ("nacionalismo",)
    assert listing.repeated_items(listing.listed_items(CAUSES)) == ()


# --- (b) the writer is told exactly N distinct, the count is a ceiling, and the draft is counted -------------------


def test_every_counted_list_asks_exactly_n_distinct() -> None:
    games = listing.enumeration_asked(
        "dame 5 juegos cooperativos pa jugar con mis primos en la pc que no pidan mucha compu"
    )
    ideas = listing.enumeration_asked("dame 5 ideas de cena con pollo y arroz que no tarden mas de media hora")
    assert games is not None and ideas is not None and ideas.open
    assert "exactamente 5" in conversation_shape._closed_list_instruction(games, "es")
    assert "exactamente 5" in conversation_shape._closed_list_instruction(ideas, "es")
    assert "distinto" in conversation_shape._closed_list_instruction(ideas, "es")


def test_closed_count_is_a_ceiling() -> None:
    # r17 t2-c09 «dame 4 paises de sudamerica que no tengan salida al mar» → two invented.
    asked = listing.enumeration_asked("dame 4 paises de sudamerica que no tengan salida al mar")
    assert asked is not None and not asked.open
    told = conversation_shape._closed_list_instruction(asked, "es")
    assert "tope" in told and "Si existen menos de 4" in told
    assert "fewer than 4 exist" in conversation_shape._closed_list_instruction(asked, "en")


def test_draft_with_other_count_or_repeated_item_is_written_again() -> None:
    games = listing.enumeration_asked(
        "dame 5 juegos cooperativos pa jugar con mis primos en la pc que no pidan mucha compu"
    )
    assert conversation_shape._enumeration_count_defect(FOUR_GAMES, games)
    assert "pidió 5" in conversation_shape._enumeration_retry_instruction(FOUR_GAMES, games, "es")
    causes = listing.enumeration_asked("dame 4 causas de la primera guerra mundial cortito pa la prueba")
    repeated = "Fueron el nacionalismo, las alianzas, nacionalismo y el imperialismo."
    assert conversation_shape._enumeration_count_defect(repeated, causes)
    assert "repitió" in conversation_shape._enumeration_retry_instruction(repeated, causes, "es")


def test_draft_with_the_count_or_an_honest_fewer_stands() -> None:
    countries = listing.enumeration_asked("dame 4 paises de sudamerica que no tengan salida al mar")
    assert not conversation_shape._enumeration_count_defect("Solo hay 2: Bolivia y Paraguay.", countries)
    assert not conversation_shape._enumeration_count_defect("Son Avatar, Titanic, Avengers y Frozen.", countries)
    ideas = listing.enumeration_asked("dame 5 ideas de cena con pollo y arroz que no tarden mas de media hora")
    assert not conversation_shape._enumeration_count_defect(FIVE_IDEAS, ideas)
    assert not conversation_shape._enumeration_count_defect("Claro, aquí van.", ideas)  # nothing listed: not judged here


def test_count_dispute_after_the_right_count_is_settled_without_rewriting() -> None:
    # r17 t2-c02 T2 «no, te pedí 5 che, me tiraste menos» (16,6 s rewriting five correct ideas).
    prior = ("dame 5 ideas de cena con pollo y arroz que no tarden mas de media hora",)
    assert previous_answer._settled_count_dispute("no, te pedí 5 che, me tiraste menos", prior, FIVE_IDEAS) == 5
    assert "no vuelvas a escribir la lista" in previous_answer._settled_count_instruction(5, "es")


def test_count_dispute_after_a_short_list_is_not_settled() -> None:
    # r17 t3-c17 T2: «no te pedi 4 po, me tiraste como 7, solo 4» after a four-item inline list is four, the list met it.
    prior = ("dame 4 causas de la primera guerra mundial cortito pa la prueba",)
    assert previous_answer._settled_count_dispute("no te pedi 4 po, me tiraste como 7, solo 4", prior, CAUSES) == 4
    games = ("dame 5 juegos cooperativos pa jugar con mis primos en la pc que no pidan mucha compu",)
    assert previous_answer._settled_count_dispute("te pedí 5 y me diste 4", games, FOUR_GAMES) is None
    # A new counted request is no dispute.
    assert previous_answer._settled_count_dispute("dame 3 ideas de postre", prior, CAUSES) is None


def test_previous_answer_items_counts_an_inline_list_after_a_counted_request() -> None:
    facts = {"context": CAUSES, "priorRequests": ["dame 4 causas de la primera guerra mundial cortito pa la prueba"]}
    assert previous_answer._previous_answer_items(facts) == 4
    assert previous_answer._previous_answer_items({"context": CAUSES, "priorRequests": ["hola"]}) is None


# --- (c) an ordinal over BAXY's own list keeps its lookup (review 2 r19: D35, M53, M88) ----------------------------

MOVIES = (
    "1. **Interstellar**: viaje espacial.\n2. **Inception**: sueños.\n3. **Tenet**: tiempo invertido.\n"
    "4. **Memento**: memoria.\n5. **Dunkirk**: guerra."
)
DINNER = "dame 5 ideas de cena con pollo y arroz que no tarden mas de media hora"


def _decided(text: str, history: list[tuple[str, str]], restated: str) -> dict:
    from test_c03_m118_cero_lastre import _Decider, _follow

    from baxy_mind.semantic.decider import ContextDecision

    return _follow(text, history, _Decider(ContextDecision(restated, "talk", (), "")))


@pytest.mark.parametrize(
    ("text", "history", "restated"),
    [
        # A plot asked of an item is looked up (M53), even with «explícame».
        ("explícame la tercera, de qué trata", [("user", "dame 5 ideas de películas"), ("assistant", MOVIES)],
         "Explícame de qué trata la película Tenet"),
        ("explain the third one, what is it about", [("user", "give me 5 movie ideas"), ("assistant", MOVIES)],
         "What is the movie Tenet about"),
        # A figure of cooking is looked up (M88), never said from memory.
        ("y la primera cuánta sal le echo, explícame", [("user", DINNER), ("assistant", FIVE_IDEAS)],
         "Cuánta sal lleva el pollo al curry rápido"),
        # A recipe is looked up before anything is said of it (D35), also when it is an item of BAXY's own list.
        ("dale, la segunda como se hace? pasame los pasos cortitos", [("user", DINNER), ("assistant", FIVE_IDEAS)],
         "Dame los pasos cortos de la receta de arroz con pollo y frijoles"),
        ("la segunda, how do i make it? los pasos", [("user", DINNER), ("assistant", FIVE_IDEAS)],
         "Dame los pasos de la receta de arroz con pollo y frijoles"),
    ],
)
def test_an_ordinal_over_baxys_own_list_keeps_its_lookup(text: str, history: list, restated: str) -> None:
    result = _decided(text, history, restated)
    assert result["operation"] == "web.search", result
    assert argument_grounding._reference_lookup(restated, [{"role": r, "content": c} for r, c in history]) is not None


def test_the_settled_dispute_reaches_the_writer() -> None:
    # r17 t2-c02 T2: the writer is told the five were given and not to write them again (one sentence, no 16 s rewrite).
    import json

    from test_uso_real_v3_t2_contenido import ASKED, DISPUTE, ChatRecorder

    client = ChatRecorder([("Ya eran 5.", "stop")])
    client.chat(
        DISPUTE,
        history=[{"role": "user", "content": ASKED}, {"role": "assistant", "content": FIVE_IDEAS}],
        conversation_kind="knowledge",
        response_language="es",
    )
    sent = json.dumps(client.payloads[0]["messages"], ensure_ascii=False)
    assert "ya tenía 5 elementos" in sent and "no vuelvas a escribir la lista" in sent


# --- review r19 (2026-10-09): one counter of first-level items, interjections, and a dispute that is read ----------

NESTED_RECIPES = (
    "Aquí tienes 3 recetas:\n\n"
    "1. **Tortilla**: rápida.\n   1. Bate huevos.\n   2. Cuaja.\n"
    "2. **Arroz**: fácil.\n   1. Lava el arroz.\n   2. Hierve.\n"
    "3. **Ensalada**: fresca.\n   1. Corta.\n   2. Aliña.\n"
)


def test_nested_steps_are_part_of_their_recipe() -> None:
    three = listing.enumeration_asked("dame 3 recetas con sus pasos")
    for answer in (NESTED_RECIPES, NESTED_RECIPES.replace("   ", "")):  # indented, and written flat
        assert listing.listed_items(answer) == ("Tortilla", "Arroz", "Ensalada")
        assert listing.items_listed(answer) == 3
        assert not conversation_shape._enumeration_count_defect(answer, three)
    bullets_under = "1. **Tortilla**:\n   - huevos\n   - papas\n2. **Arroz**:\n   - arroz\n   - agua\n   - sal\n"
    assert listing.listed_items(bullets_under) == ("Tortilla", "Arroz")
    numbered_under = "- Tortilla\n  1. Bate\n  2. Cuaja\n  3. Sirve\n- Arroz\n  1. Lava\n  2. Hierve\n"
    assert listing.items_listed(numbered_under) == 2
    assert listing.items_listed("- A\n  - a1\n  - a2\n- B\n- C") == 3


def test_separate_lists_and_one_line_lists_keep_their_count() -> None:
    # Counter-cases: two lists one after the other are two lists (the longest counts); a list in one line is a list.
    assert listing.items_listed("Ingredientes:\n1. huevo\n2. papa\nPasos:\n1. bate\n2. cuaja\n3. sirve") == 3
    assert listing.listed_items("Opciones: 1. Rojo 2. Verde 3. Azul.") == ("Rojo", "Verde", "Azul.")


def test_an_interjection_before_an_inline_list_is_no_item() -> None:
    # The shape of r17 t3-c03 with five games: five, not six with «Claro».
    games = "Claro, puedes probar con Among Us, Garry's Mod, Portal 2, Terraria o Minecraft."
    assert listing.listed_items(games) == ("Among Us", "Garry's Mod", "Portal 2", "Terraria", "Minecraft")
    assert not conversation_shape._enumeration_count_defect(games, listing.enumeration_asked("dame 5 juegos"))


def test_sentences_with_commas_are_no_inline_list() -> None:
    for said in (
        "Hola, ¿cómo estás? Bien, gracias y tú",
        "Sí, claro, lo abro y te aviso",
        "Bueno, mira, depende del clima y del tráfico.",
        "Well, honestly, it depends on the weather and traffic.",
    ):
        assert listing.listed_items(said) == (), said
        assert listing.items_listed(said, counted=True) is None, said
        facts = {"context": said, "priorRequests": ["dame 5 ideas de cena"]}
        assert previous_answer._previous_answer_items(facts) is None, said


def test_a_dispute_of_the_count_is_read() -> None:
    prior = ("dame 5 ideas de cena con pollo y arroz que no tarden mas de media hora",)
    for said in (
        "no, te pedí 5 che, me tiraste menos",
        "me tiraste menos",
        "you gave me fewer than 5",
        "I asked for five",
        "eso no son 5",
    ):
        assert listing.count_disputed(said), said
        assert previous_answer._settled_count_dispute(said, prior, FIVE_IDEAS) == 5, said


def test_a_number_said_about_the_list_is_no_dispute() -> None:
    # Counter-cases (review r19): the same number after a list of five asks more, points at an item or thanks.
    prior = ("dame 5 ideas de cena",)
    for said in (
        "dame otras 5",
        "quiero 5 más",
        "explícame la 5",
        "y la número 5 cómo se hace?",
        "dame la receta de la 5",
        "el 5 me gusta",
        "ok, la 5",
        "tell me more about number 5",
        "son 5 o 4?",
        "las 5 están buenas, gracias",
        "me diste 5 ideas, dame otras 5",
        "give me another 5",
    ):
        assert not listing.count_disputed(said), said
        assert previous_answer._settled_count_dispute(said, prior, FIVE_IDEAS) is None, said


def test_new_list_after_five_is_written_not_settled() -> None:
    # «dame otras 5» after five ideas reaches the writer with no «ya tenía 5 elementos».
    import json

    from test_uso_real_v3_t2_contenido import ASKED, ChatRecorder

    client = ChatRecorder([("1. Uno\n2. Dos\n3. Tres\n4. Cuatro\n5. Cinco", "stop")])
    client.chat(
        "dame otras 5",
        history=[{"role": "user", "content": ASKED}, {"role": "assistant", "content": FIVE_IDEAS}],
        conversation_kind="knowledge",
        response_language="es",
    )
    sent = json.dumps(client.payloads[0]["messages"], ensure_ascii=False)
    assert "ya tenía 5 elementos" not in sent


def test_the_settled_dispute_is_only_told_in_talk() -> None:
    # Counter-case: a shaped or non-talk turn is not told the count.
    import json

    from test_uso_real_v3_t2_contenido import ASKED, DISPUTE, ChatRecorder

    client = ChatRecorder([("¡Claro!", "stop")])
    client.chat(
        DISPUTE,
        history=[{"role": "user", "content": ASKED}, {"role": "assistant", "content": FIVE_IDEAS}],
        conversation_kind="social",
        response_language="es",
    )
    sent = json.dumps(client.payloads[0]["messages"], ensure_ascii=False)
    assert "ya tenía 5 elementos" not in sent


# --- review 2 r19 (2026-10-09): a correction of what the list was is no dispute of its count; a right list stands ---


@pytest.mark.parametrize(
    "said",
    [
        "te pedí 5 vegetarianas",
        "no, te pedí 5 que no tarden más de media hora",
        "I asked for 5 vegetarian ones",
        "quería 5 de postre, no de cena",
        "me diste 5 con pollo y yo quería con carne",
        "te pedí 5 sin pescado",
    ],
)
def test_a_correction_of_the_content_is_no_count_dispute(said: str) -> None:
    import json

    from test_uso_real_v3_t2_contenido import ASKED, ChatRecorder

    assert not listing.count_disputed(said, "ideas"), said
    assert previous_answer._settled_count_dispute(said, (ASKED,), FIVE_IDEAS) is None, said
    language = "en" if said.startswith("I ") else "es"
    listed = ("One", "Two", "Three", "Four", "Five") if language == "en" else ("Uno", "Dos", "Tres", "Cuatro", "Cinco")
    draft = "".join(f"{n}. {name}\n" for n, name in enumerate(listed, 1))
    client = ChatRecorder([(draft, "stop"), (draft, "stop")])
    client.chat(
        said,
        history=[{"role": "user", "content": ASKED}, {"role": "assistant", "content": FIVE_IDEAS}],
        conversation_kind="knowledge",
        response_language=language,
    )
    sent = json.dumps(client.payloads[0]["messages"], ensure_ascii=False)
    assert "ya tenía 5 elementos" not in sent and "already listed 5" not in sent, said


@pytest.mark.parametrize(
    "said", ["te dije 5 rápidas, esas tardan una hora", "no son 5 personas, son 6", "te dije 5 minutos"],
)
def test_a_number_said_of_something_else_is_no_count_dispute(said: str) -> None:
    assert not listing.count_disputed(said), said
    assert not listing.count_disputed(said, "ideas"), said


def test_a_dispute_may_name_the_class_asked() -> None:
    assert listing.count_disputed("te pedí 5 ideas", "ideas")
    assert listing.count_disputed("me diste menos de lo que te pedí")
    assert previous_answer._settled_count_dispute("te pedí 5 ideas, me diste menos", (DINNER,), FIVE_IDEAS) == 5


GAMES = "dame 5 juegos cooperativos pa jugar con mis primos en la pc"
BOLD_NUMBERED = "\n".join(f"**{n}. Juego {n}**: cooperativo, ligero y gratis." for n in range(1, 6))
SECTIONS = "**Online:**\n1. Juego A\n2. Juego B\n3. Juego C\n\n**En la misma PC:**\n1. Juego D\n2. Juego E"


@pytest.mark.parametrize("draft", [BOLD_NUMBERED, SECTIONS])
def test_a_right_list_is_not_written_again(draft: str) -> None:
    from test_uso_real_v3_t2_contenido import ChatRecorder

    games = listing.enumeration_asked(GAMES)
    assert not conversation_shape._enumeration_count_defect(draft, games)
    client = ChatRecorder([(draft, "stop"), ("otra", "stop")])
    client.chat(GAMES, history=[], conversation_kind="knowledge", response_language="es")
    assert len(client.payloads) == 1


def test_a_bold_numbered_list_is_counted_by_its_markers() -> None:
    assert listing.items_listed(BOLD_NUMBERED) == 5
    assert listing.listed_items(BOLD_NUMBERED)[0] == "Juego 1"
    assert listing.counts_listed(SECTIONS) == (3, 5)
    facts = {"context": BOLD_NUMBERED, "priorRequests": ["dame 5 ideas de cena"]}
    assert previous_answer._previous_answer_items(facts) == 5
    # A short list in bold is still counted short, and written again.
    short = "\n".join(f"**{n}. Juego {n}**: cooperativo, ligero y gratis." for n in range(1, 4))
    assert conversation_shape._enumeration_count_defect(short, listing.enumeration_asked(GAMES))


# --- review 3 r19 (2026-10-09): a right draft is published at once, another count is no settled dispute, and the
# recovery states no count read from prose ---------------------------------------------------------------------------

BOLD_NUMBERS = (
    "**1.** Among Us: social, rápido y gratis.\n**2.** Stardew Valley: tranquilo, cooperativo y barato.\n"
    "**3.** Terraria: ligero, creativo y divertido.\n**4.** Portal 2: corto, ingenioso y cooperativo.\n"
    "**5.** Minecraft: abierto, creativo y clásico."
)
SLEEP_ES = (
    "Claro. Primero, evita pantallas una hora antes de dormir. Segundo, mantén horarios fijos. Tercero, cuida la "
    "cafeína, el alcohol y las cenas pesadas."
)
SLEEP_EN = (
    "Sure! First, avoid screens an hour before bed. Second, keep a fixed schedule. Third, cut caffeine, alcohol and "
    "heavy dinners."
)
HEADED_RECIPES = (
    "### 1. Tortilla\n- huevos\n- papas\n### 2. Arroz\n- arroz\n- agua\n- sal\n### 3. Ensalada\n- lechuga\n- tomate"
)
TWO_DINNERS = "Puedes hacer pasta o pedir sushi, ambas son rápidas, baratas y ricas."
LANDLOCKED = "Solo hay 2: Bolivia y Paraguay. Chile, Perú y Ecuador sí tienen mar."
REVIEW3_DRAFTS = [
    ("dame 5 juegos cooperativos pa jugar con mis primos", BOLD_NUMBERS, "es"),
    ("dame 3 consejos para dormir mejor", SLEEP_ES, "es"),
    ("give me 3 tips to sleep better", SLEEP_EN, "en"),
    ("dame 3 recetas faciles", HEADED_RECIPES, "es"),
    ("dame 2 opciones para cenar", TWO_DINNERS, "es"),
    ("dame 4 paises de sudamerica que no tengan salida al mar", LANDLOCKED, "es"),
]


@pytest.mark.parametrize(("asked", "draft", "language"), REVIEW3_DRAFTS)
def test_a_right_draft_is_published_with_one_call(asked: str, draft: str, language: str) -> None:
    from test_uso_real_v3_t2_contenido import ChatRecorder

    assert not conversation_shape._enumeration_count_defect(draft, listing.enumeration_asked(asked)), draft
    client = ChatRecorder([(draft, "stop"), ("otra", "length")])
    client.chat(asked, history=[], conversation_kind="knowledge", response_language=language)
    assert len(client.payloads) == 1, draft


def test_the_markers_of_a_list_are_read_as_written() -> None:
    assert listing.listed_items(BOLD_NUMBERS) == ("Among Us", "Stardew Valley", "Terraria", "Portal 2", "Minecraft")
    assert listing.listed_items(HEADED_RECIPES) == ("Tortilla", "Arroz", "Ensalada")
    for prose in (SLEEP_ES, SLEEP_EN, TWO_DINNERS, LANDLOCKED):
        assert listing.items_listed(prose, counted=True) is None, prose


def test_a_list_written_again_keeps_the_first_draft_budget() -> None:
    # A real short list is written again, with no less budget than its first draft.
    import json

    from test_uso_real_v3_t2_contenido import ChatRecorder

    short = "\n".join(f"{n}. Juego {n}" for n in range(1, 4))
    right = "\n".join(f"{n}. Juego {n}" for n in range(1, 6))
    client = ChatRecorder([(short, "stop"), (json.dumps({"answer": right}), "stop")])
    client.chat(GAMES, history=[], conversation_kind="knowledge", response_language="es")
    assert len(client.payloads) == 2
    assert client.payloads[1]["max_tokens"] >= client.payloads[0]["max_tokens"]


@pytest.mark.parametrize(
    "said",
    [
        "me diste 5 y quería 10",
        "yo quería 6 y me diste 5",
        "bro me diste 5 y yo queria 7",
        "I wanted 10, you gave me 5",
        "you gave me 5, I wanted 8",
        "no son 5, son 6",
        "no eran 5 eran 6",
    ],
)
def test_another_count_asked_is_no_settled_dispute(said: str) -> None:
    import json

    from test_uso_real_v3_t2_contenido import ChatRecorder

    assert previous_answer._settled_count_dispute(said, (DINNER,), FIVE_IDEAS) is None, said
    language = "en" if said[0] in "Iy" else "es"
    listed = ("One", "Two", "Three", "Four", "Five") if language == "en" else ("Uno", "Dos", "Tres", "Cuatro", "Cinco")
    draft = "".join(f"{n}. {name}\n" for n, name in enumerate(listed, 1))
    client = ChatRecorder([(draft, "stop"), (draft, "stop")])
    client.chat(
        said,
        history=[{"role": "user", "content": DINNER}, {"role": "assistant", "content": FIVE_IDEAS}],
        conversation_kind="knowledge",
        response_language=language,
    )
    sent = json.dumps(client.payloads[0]["messages"], ensure_ascii=False)
    assert "ya tenía 5 elementos" not in sent and "already listed 5" not in sent, said


def test_what_baxy_gave_is_told_from_what_was_asked() -> None:
    assert listing.given_counts("no te pedi 4 po, me tiraste como 7, solo 4") == (7,)
    assert listing.given_counts("me diste 5 y quería 10") == (5,)
    assert listing.given_counts("I wanted 10, you gave me 5") == (5,)
    assert listing.given_counts("no son 5, son 6") == ()


def test_the_recovery_states_no_count_read_from_prose() -> None:
    games = {"context": BOLD_NUMBERS, "priorRequests": ["dame 5 juegos cooperativos pa jugar con mis primos"]}
    assert previous_answer._previous_answer_items(games) == 5
    assert not previous_answer._contradicts_previous_count("Te di 5 juegos.", games)
    sleep = {"context": SLEEP_ES, "priorRequests": ["dame 3 consejos para dormir mejor"]}
    assert previous_answer._previous_answer_items(sleep) is None
    assert not previous_answer._contradicts_previous_count("Te di 3 consejos.", sleep)
