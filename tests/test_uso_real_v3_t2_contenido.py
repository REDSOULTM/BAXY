"""Uso real v3, tanda 2 (2026-10-08, official window), diagnosis section (d): counts and lists.

- c02 «dame 5 ideas de cena con pollo y arroz…» gave five; «no, te pedí 5 che, me tiraste menos» was budgeted as a
  one-sentence answer (128, then 160 tokens): both drafts that wrote the five again were cut. The recovery's writer
  got BAXY's answer cut at 320 characters (two of the five ideas) and said «Solo te proporcioné dos recetas».
- c02 «dale, la segunda como se hace?» → the recipe writer asked 420 tokens with a 10 s budget at ≈26 tokens per wall
  second, ran out of time at 8,98 s and left the fallback 0 ms.
- c09 «dame 4 paises de sudamerica que no tengan salida al mar» → «Bolivia, Paraguay, Perú y Ecuador»: two exist.

General fixes, each with its counter-case: a follow-up of written content keeps the content's budget (thanks keep
theirs); the previous answer is referenced whole when it is a list and its item count travels (``previousAnswerItems``)
with a veto on a reply that states another count (the true count passes); the consulted writer's budget is what the
measured speed writes in the time left after the fallback's reserve; a counted list of a closed class is told with what
really exists (an open class — ideas, recipes — is not).
"""

from __future__ import annotations

import json
import time

import pytest

from baxy_mind import llm
from baxy_mind import llm_compose
from baxy_mind import previous_answer
from baxy_mind import visible_defect
from baxy_mind import conversation_shape
from baxy_mind import reply_budget
from baxy_mind.semantic.listing import Enumeration, count_said, enumeration_asked, items_listed, stated_given_count
from baxy_mind import turn_recovery
from baxy_mind import consulted_answers

FIVE_IDEAS = (
    "1. **Pollo al curry rápido**: Corta el pollo en cubos, saltea con ajo y comino, añade leche de coco y un poco de "
    "arroz cocido. Sirve con un poco de cilantro fresco.\n\n"
    "2. **Arroz con pollo y frijoles**: En una sartén, cocina el pollo con cebolla, pimiento y comino. Mezcla con "
    "arroz blanco y frijoles negros pre-cocidos. Termina con un chorrito de limón.\n\n"
    "3. **Pollo salteado con arroz y verduras**: Saltea tiras de pollo con pimientos, cebolla y brócoli en salsa de "
    "soja y jengibre. Sirve inmediatamente sobre una cama de arroz.\n\n"
    "4. **Arroz con pollo y plátano**: Cocina el pollo en salsa de tomate y ajo. Mezcla con arroz y añade rodajas de "
    "plátano maduro para un toque dulce. Ideal para una cena ligera.\n\n"
    "5. **Pollo al horno con arroz y espinacas**: Precalienta el horno a 200°C. Coloca trozos de pollo, arroz cocido y "
    "espinacas en una bandeja, rocía con aceite y hierbas, y hornea 15 minutos."
)
ASKED = "dame 5 ideas de cena con pollo y arroz que no tarden mas de media hora"
DISPUTE = "no, te pedí 5 che, me tiraste menos"


# --- the readers (semantic/listing.py, words in data/listing_words.v1.json) ----------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("dame 4 paises de sudamerica que no tengan salida al mar", Enumeration(4, "paises", False)),
        ("nombra tres rios de Chile", Enumeration(3, "rios", False)),
        ("name 5 planets", Enumeration(5, "planets", False)),
        (ASKED, Enumeration(5, "ideas", True)),
        ("give me 3 stretches i can do at my desk, keep it short", Enumeration(3, "stretches", True)),
        ("dame 3 recetas rapidas con atun y arroz", Enumeration(3, "recetas", True)),
        ("top 3 peliculas de suspenso del 2026", Enumeration(3, "peliculas", True)),
    ],
)
def test_a_counted_list_is_read_with_its_class(text: str, expected: Enumeration) -> None:
    assert enumeration_asked(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "dame 5 minutos", "dame un segundo", "dame 1 idea", DISPUTE, "los mejores restaurantes de Lima",
        "qué es un átomo",
    ],
)
def test_no_counted_list_is_read_where_none_is_asked(text: str) -> None:
    assert enumeration_asked(text) is None


def test_the_items_of_an_answer_are_counted_when_it_lists_them() -> None:
    assert items_listed(FIVE_IDEAS) == 5
    assert items_listed("- uno\n- dos\n- tres") == 3
    # Counter-cases: a list written inline, or a number that is not an item, is not counted.
    assert items_listed("Bolivia, Paraguay, Perú y Ecuador.") is None
    assert items_listed("Hornea a 200 grados. 2. paso suelto") is None


@pytest.mark.parametrize(
    ("reply", "count"),
    [
        ("Solo te proporcioné dos recetas de pollo en lugar de cinco.", 2),
        ("No, solo te di cuatro: nacionalismo, imperialismo…", 4),
        ("I gave you five ideas.", 5),
        ("Te di 5: pollo al curry…", 5),
        ("Te di la receta completa.", None),
        ("Te paso los pasos.", None),
        # Counter-cases: an article is no count, and a bare English verb is any clause.
        ("Te di una lista con cinco ideas.", None),
        ("Te di un par de opciones distintas.", None),
        ("The recipe suggested 2 cups of rice.", None),
        ("I only listed 3 of them.", 3),
    ],
)
def test_a_reply_that_says_how_many_it_gave_is_read(reply: str, count: int | None) -> None:
    assert stated_given_count(reply) == count


def test_a_count_said_in_a_follow_up_is_read() -> None:
    assert count_said(DISPUTE) == 5
    assert count_said("no te pedi 4 po, me tiraste como siete") == 4
    assert count_said("me tiraste menos") is None
    assert count_said("la segunda como se hace") is None


# --- 1. the budget of a follow-up of written content ---------------------------------------------------------------

def test_a_follow_up_of_written_content_keeps_its_budget() -> None:
    assert conversation_shape._follows_written_content((ASKED,), FIVE_IDEAS)
    assert conversation_shape._follows_written_content(("haz un relato basado en el año 2090",), "En el año 2090…")
    assert reply_budget._conversation_max_tokens(None, "knowledge", DISPUTE, follows_content=True) == 320
    assert reply_budget._conversation_max_tokens(None, "knowledge", DISPUTE, retry=True, follows_content=True) == 320


def test_thanks_after_written_content_keep_their_own_budget() -> None:
    # Counter-cases: thanks or a social reaction after the content, and a follow-up of a plain answer.
    assert reply_budget._conversation_max_tokens(None, "social", "gracias", follows_content=True) == 64
    assert reply_budget._conversation_max_tokens(None, "knowledge", "gracias", follows_content=True) == 128
    assert not conversation_shape._follows_written_content(("qué es un átomo",), "Un átomo es la unidad más pequeña de la materia.")
    assert reply_budget._conversation_max_tokens(None, "knowledge", "y por qué", follows_content=False) == 128


class ChatRecorder(llm.LlmRuntime):
    def __init__(self, replies: list[tuple[str, str]]) -> None:
        self._gguf = "granite-4.2-3b-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.payloads: list[dict] = []

    def _post(self, payload: dict, **_: object) -> dict:
        self.payloads.append(payload)
        content, finish = next(self.replies)
        return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}


def test_the_dispute_after_five_ideas_is_written_with_the_content_budget() -> None:
    client = ChatRecorder([("Te di cinco ideas; aquí van de nuevo.", "stop")])
    client.chat(
        DISPUTE,
        history=[{"role": "user", "content": ASKED}, {"role": "assistant", "content": FIVE_IDEAS}],
        conversation_kind="knowledge",
        response_language="es",
    )
    assert client.payloads[0]["max_tokens"] == 320


def test_thanks_after_five_ideas_keep_the_social_budget() -> None:
    client = ChatRecorder([("¡De nada!", "stop")])
    client.chat(
        "gracias",
        history=[{"role": "user", "content": ASKED}, {"role": "assistant", "content": FIVE_IDEAS}],
        conversation_kind="social",
        response_language="es",
    )
    assert client.payloads[0]["max_tokens"] == 64


# --- 2. the recovery knows the previous answer and its count ---------------------------------------------------------

def test_the_recovery_carries_the_previous_answer_and_its_item_count() -> None:
    history = [
        {"role": "user", "content": ASKED},
        {"role": "assistant", "content": FIVE_IDEAS},
        {"role": "user", "content": DISPUTE},
    ]
    facts = turn_recovery._recovery_conversation_facts(history, DISPUTE)
    assert facts["context"] == FIVE_IDEAS
    assert facts["previousAnswerItems"] == 5
    # Counter-case: an answer that lists nothing carries no count.
    plain = turn_recovery._recovery_conversation_facts(
        [{"role": "user", "content": "qué es un átomo"}, {"role": "assistant", "content": "La unidad de la materia."}],
        "y eso",
    )
    assert "previousAnswerItems" not in plain


def test_a_listed_previous_answer_is_referenced_whole() -> None:
    facts = {"context": FIVE_IDEAS, "priorRequests": [ASKED]}
    referenced = previous_answer._referenced_previous_answer(DISPUTE, facts)
    assert referenced == FIVE_IDEAS and items_listed(referenced) == 5
    # A count said right after the list is about it; a message that stands on its own is not.
    assert previous_answer._referenced_previous_answer("no te pedi 5 po, me tiraste como 3", facts) == FIVE_IDEAS
    assert previous_answer._referenced_previous_answer("me tiraste 5 pero eran 4 lo que queria", facts) == FIVE_IDEAS
    assert previous_answer._referenced_previous_answer("qué hora es en Tokio", facts) == ""
    # Counter-cases: a number that is neither the list's count nor the one asked, or a new counted list, is a message
    # of its own; with the list and «si pidió menos, deja sólo esos» it would become a cut of the old list.
    assert previous_answer._referenced_previous_answer("cuanto es 3 por 4", facts) == ""
    assert previous_answer._referenced_previous_answer("dame 5 ideas de postre con chocolate", facts) == ""
    # Counter-case: a plain answer keeps its 320-character bound.
    long_plain = "Una respuesta sin lista. " * 30
    assert len(previous_answer._referenced_previous_answer("¿y eso?", {"context": long_plain})) <= 320


def _facts(items: int | None = 5, context: str = FIVE_IDEAS) -> dict:
    return {
        "context": context,
        **({"previousAnswerItems": items} if items is not None else {}),
        "priorRequests": [ASKED],
        "situation": json.dumps({"kind": "conversation", "polarity": "success"}),
    }


def test_a_reply_that_contradicts_the_count_given_is_refused() -> None:
    defect = visible_defect.compose_visible_defect(
        "Solo te proporcioné dos recetas de pollo en lugar de cinco.", "conversation", DISPUTE, _facts(), said=DISPUTE,
    )
    assert defect == "contradicts_previous_answer"


def test_the_true_count_and_a_reply_that_completes_a_short_list_pass() -> None:
    assert visible_defect.compose_visible_defect(
        "Te di cinco ideas: pollo al curry, arroz con frijoles, salteado con verduras, arroz con plátano y pollo al "
        "horno.",
        "conversation", DISPUTE, _facts(), said=DISPUTE,
    ) == ""
    # Counter-case: BAXY really gave fewer; saying so is the truth, not a contradiction.
    two = "1. Pollo al curry.\n2. Arroz con frijoles."
    assert visible_defect.compose_visible_defect(
        "Tienes razón, te di 2; aquí van las otras tres: salteado, plátano y horno.",
        "conversation", DISPUTE, _facts(2, two), said=DISPUTE,
    ) == ""


class ComposeRecorder(llm.LlmRuntime):
    def __init__(self, replies: list[str]) -> None:
        self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_: object) -> dict:
        self.requests.append(payload)
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


def test_the_recovery_writer_sees_the_whole_list_and_its_count_and_is_corrected() -> None:
    client = ComposeRecorder([
        "Solo te proporcioné dos recetas de pollo en lugar de cinco.",
        "Te di cinco ideas: pollo al curry, arroz con frijoles, salteado, arroz con plátano y pollo al horno.",
    ])
    reply = client.compose_user_message(DISPUTE, "conversation", _facts())
    assert reply.startswith("Te di cinco ideas")
    first = client.requests[0]["messages"][-1]["content"]
    assert "Pollo al horno con arroz y espinacas" in first  # the fifth idea, past the old 320-character cut
    assert "previousAnswerItems" in first and "tenía 5 elementos" in first
    retry_system = client.requests[1]["messages"][0]["content"]
    assert "di que le diste 5" in retry_system


# --- 3. the consulted writer's budget follows the measured speed ------------------------------------------------------

def test_the_writer_asks_only_what_the_measured_speed_writes_in_time() -> None:
    # Tanda 2: ≈26 tokens per wall second and ~9,9 s left; 420 tokens would take 16 s.
    affordable = reply_budget._affordable_max_tokens(420, 9.9, 26.0)
    assert reply_budget._CONSULTED_MIN_TOKENS <= affordable < 420
    # The fallback keeps its own time: what is asked always leaves its reserve.
    assert affordable / 26.0 + reply_budget._FALLBACK_RESERVE_TOKENS / 26.0 < 9.9
    # Counter-cases: no deadline, or a fast model with time to spare, keeps the whole budget; no time, nothing.
    assert reply_budget._affordable_max_tokens(420, None, 26.0) == 420
    assert reply_budget._affordable_max_tokens(420, 30.0, 60.0) == 420
    assert reply_budget._affordable_max_tokens(420, 1.0, 26.0) == 0
    # Without a measure yet, the tanda's prior is used.
    assert reply_budget._affordable_max_tokens(420, 9.9, None) == affordable


def test_the_speed_is_measured_from_completed_calls() -> None:
    assert reply_budget._decode_rate_of({"timings": {"predicted_n": 269}}, 10.375) == pytest.approx(25.9, abs=0.1)
    # Counter-cases: a short decode is mostly prompt time, and a failed call measures nothing.
    assert reply_budget._decode_rate_of({"timings": {"predicted_n": 9}}, 0.45) is None
    assert reply_budget._decode_rate_of(None, 4.0) is None
    # A reader that reads a long prompt and writes little: its prompt read is not writing speed.
    assert reply_budget._decode_rate_of({"timings": {"predicted_n": 40, "prompt_ms": 2000.0}}, 3.0) == pytest.approx(40.0)
    # Counter-case: a prompt time beyond the wall time (clock skew) is not subtracted.
    skewed = {"timings": {"predicted_n": 40, "prompt_ms": 5000.0}}
    assert reply_budget._decode_rate_of(skewed, 3.0) == pytest.approx(13.33, abs=0.01)


class TimedRecorder(llm.LlmRuntime):
    def __init__(self, rate: float) -> None:
        self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        self._measured_decode_rate = rate
        self.payloads: list[dict] = []

    def _post(self, payload: dict, **_: object) -> dict:
        self.payloads.append(payload)
        return {"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]}


RECIPE_SITUATION = {"operation": "web.search"}


def _consulted(client: TimedRecorder, seconds_left: float) -> None:
    reference = {
        "kind": "recipe", "title": "Arroz con pollo", "text": "Ingredientes: 1 taza de arroz…", "servings": None,
        "seen": {},
    }
    original = consulted_answers._reference_of
    llm_compose._reference_of = lambda situation: reference  # type: ignore[assignment]
    try:
        client._compose_consulted_answer(
            "la segunda como se hace? pasame los pasos cortitos", {"priorRequests": [ASKED]}, RECIPE_SITUATION, "es",
            client._post, time.monotonic() + seconds_left, "",
        )
    finally:
        llm_compose._reference_of = original  # type: ignore[assignment]


def test_the_recipe_writer_is_sized_to_the_time_left_and_told_so() -> None:
    client = TimedRecorder(26.0)
    _consulted(client, 9.9)
    first = client.payloads[0]
    assert reply_budget._CONSULTED_MIN_TOKENS <= first["max_tokens"] < 420
    assert any("Tienes espacio para unas" in str(message["content"]) for message in first["messages"])


def test_a_fast_writer_keeps_the_whole_recipe_budget_and_no_time_starts_none() -> None:
    fast = TimedRecorder(80.0)
    _consulted(fast, 9.9)
    assert fast.payloads[0]["max_tokens"] == 420
    assert not any("Tienes espacio" in str(message["content"]) for message in fast.payloads[0]["messages"])
    late = TimedRecorder(26.0)
    _consulted(late, 3.0)
    assert late.payloads == []  # the fallback answers with the time left


# --- 4. a closed list is told with what really exists -----------------------------------------------------------------

def test_a_closed_list_asks_to_say_how_many_really_exist() -> None:
    client = ChatRecorder([("Solo hay dos: Bolivia y Paraguay.", "stop")])
    client.chat(
        "dame 4 paises de sudamerica que no tengan salida al mar", history=[], conversation_kind="knowledge",
        response_language="es",
    )
    sent = " ".join(str(message["content"]) for message in client.payloads[0]["messages"])
    assert "Si existen menos de 4, di cuántos hay de verdad" in sent


@pytest.mark.parametrize(
    "text",
    [ASKED, "dame 3 recetas rapidas con atun y arroz", "qué es un átomo"],
)
def test_an_open_list_or_a_plain_question_is_not_told_to_count_what_exists(text: str) -> None:
    client = ChatRecorder([("Aquí van.", "stop")])
    client.chat(text, history=[], conversation_kind="knowledge", response_language="es")
    sent = " ".join(str(message["content"]) for message in client.payloads[0]["messages"])
    assert "di cuántos hay de verdad" not in sent
