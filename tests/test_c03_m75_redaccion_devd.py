"""M75: the four ⚠ (composition_failed) of DEV-D in the official window (v3l-devD, HEAD a017d6fc, 2026-09-29) that M74
did not close. Every draft, payload and situation here is the one the run recorded (compose-audit.jsonl); the request
is the person's message, which is what the writer got for these situations (dialogue_state.understood).

- D-s032 «Noticias sobre Taylor Swift.» (web.news.headlines): the first draft quoted three headlines as written, and
  one of them asks «¿es 'Cleveland' tan mala?»; that question mark was read as BAXY asking (extra_claim), and so was
  the deterministic final. The two paraphrases after it died, rightly, on missing_state.
- D-p02-t2 «¿Serías capaz de hacer foto ahora?» (conversation, gold: the limit): «No puedo hacer fotos.» answers
  whether BAXY is able; three such drafts died on asserted_failure (in v3c, v3d, v3e2, v3f and v3l alike).
- D-w02-t2 «y si allá son las 10 de la mañana acá qué hora es» (error, turn_runtime_failure): every draft was rightly
  vetoed (an invented limit, an invented answer, a guessed reason). No fixed final replaces it (owner's review): the ⚠
  stays until the turn itself is answered (a clock conversion from the place of the previous turn).
- D-w15-t3 «traducelo al ingles que es para mi jefa» (clarification): what is to be translated is only pointed at, so
  asking which is the reply; all three questions died on knowledge_question.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic.conversation import asks_whether_able, translation_without_its_text


class _Drafts(LlmRuntime):
    """The recorded drafts stand in for the model, in order (the last one repeats)."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self.calls = 0

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.calls += 1
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _compose(drafts: list[str], user_text: str, intent: str, situation: str) -> tuple[str, int]:
    runtime = _Drafts(drafts)
    return runtime.compose_user_message(user_text, intent, {"situation": situation}), runtime.calls


# ------------------------------------------------------------------ D-s032: a headline's own question mark
TAYLOR = "Noticias sobre Taylor Swift."
TAYLOR_READ = (
    '{"kind":"operation","operation":"web.news.headlines","polarity":"success","verified":true,"succeeded":true,'
    '"observed":{"version":1,"topic":"Taylor Swift","edition":"es-419/CL","count":5,"headlines":['
    '{"title":"Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026",'
    '"source":"CNN en Español","publishedAt":"Mon, 28 Sep 2026 03:46:00 GMT"},'
    '{"title":"De la elegancia de Taylor Swift a Lisa y Charli XCX: la alfombra roja de los MTV VMA 2026",'
    '"source":"BioBioChile","publishedAt":"Mon, 28 Sep 2026 00:31:50 GMT"},'
    '{"title":"La crítica se harta de Taylor Swift, pero… ¿es ‘Cleveland’ tan mala?",'
    '"source":"Jenesaispop","publishedAt":"Tue, 29 Sep 2026 12:39:16 GMT"},'
    '{"title":"Dakota Johnson tiene malas noticias para los fans que esperaban ver fotos de la boda de Taylor Swift",'
    '"source":"HOLA","publishedAt":"Mon, 28 Sep 2026 22:40:48 GMT"},'
    '{"title":"El vídeo musical ‘Patient Zero’ de Taylor Swift ha llegado —Cómo verlo",'
    '"source":"ELLE","publishedAt":"Mon, 28 Sep 2026 18:11:07 GMT"}],'
    '"authority":"google_news_rss_es419_cl"}}'
)
TAYLOR_FIRST = (
    "Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026; De la elegancia de Taylor Swift a "
    "Lisa y Charli XCX: la alfombra roja de los MTV VMA 2026; La crítica se harta de Taylor Swift, pero… ¿es "
    "'Cleveland' tan mala?"
)
TAYLOR_RETRY = (
    'Taylor Swift ha superado a Beyoncé como la artista más premiada en los MTV VMA 2026, la crítica cuestiona su '
    'último trabajo "Cleveland" y Dakota Johnson ha anunciado malas noticias sobre la boda de la cantante.'
)
TAYLOR_THIRD = (
    "Hoy hay titulares sobre Taylor Swift donde supera a Beyoncé en los MTV VMA 2026, se habla de la crítica de su "
    "álbum 'Cleveland' y se menciona que Dakota Johnson no tiene fotos de su boda."
)


def _visible(text: str, intent: str, user_text: str, situation: str) -> str:
    return llm.compose_visible_defect(text, intent, user_text, {"situation": situation})


def test_d_s032_the_headlines_quoted_as_written_are_published_first() -> None:
    assert _visible(TAYLOR_FIRST, "status", TAYLOR, TAYLOR_READ) == ""
    assert _compose([TAYLOR_FIRST], TAYLOR, "status", TAYLOR_READ) == (TAYLOR_FIRST, 1)


def test_d_s032_the_paraphrases_still_die_and_the_deterministic_final_is_published() -> None:
    import json

    payload = {"operation": "web.news.headlines", "seen": json.loads(TAYLOR_READ)["observed"]}
    for draft in (TAYLOR_RETRY, TAYLOR_THIRD):
        assert llm._payload_fact_defect(draft, payload, TAYLOR) == "missing_state"
    published, calls = _compose([TAYLOR_RETRY, TAYLOR_RETRY, TAYLOR_THIRD], TAYLOR, "status", TAYLOR_READ)
    assert calls == 3
    assert published.startswith("Titulares sobre Taylor Swift: «Taylor Swift supera a Beyoncé")
    assert "¿es ‘Cleveland’ tan mala?»" in published


@pytest.mark.parametrize("draft", [
    # A question of BAXY's own beside the quoted headlines is still an unsolicited question.
    TAYLOR_FIRST + " ¿Quieres que te lea más?",
    "¿Quieres que te lea los titulares sobre Taylor Swift?",
    # A headline with no question of its own does not lend one to a draft that asks.
    "¿Sabías que Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026?",
])
def test_d_s032_a_question_of_baxys_own_is_still_extra(draft: str) -> None:
    assert _visible(draft, "status", TAYLOR, TAYLOR_READ) == "extra_claim"


# ------------------------------------------------------------------ D-p02-t2: whether BAXY is able
FOTO = "¿Serías capaz de hacer foto ahora?"
CONVERSATION = '{"kind":"conversation","polarity":"success"}'
FOTO_DRAFTS = [
    "No puedo tomar fotos, pero puedo ayudarte con otras tareas.",
    "No, no puedo hacer fotos.",
    "No puedo hacer fotos.",
]


@pytest.mark.parametrize("draft", FOTO_DRAFTS)
def test_d_p02_t2_no_puedo_answers_whether_baxy_is_able(draft: str) -> None:
    assert _visible(draft, "conversation", FOTO, CONVERSATION) == ""


def test_d_p02_t2_the_first_draft_is_published() -> None:
    assert _compose(FOTO_DRAFTS, FOTO, "conversation", CONVERSATION) == (FOTO_DRAFTS[0], 1)


@pytest.mark.parametrize(("user_text", "draft"), [
    # A failed attempt claimed is still a failure asserted in a conversation.
    (FOTO, "No pude hacer la foto."),
    ("Are you able to take a photo?", "I couldn't take the photo."),
    # Not a question whether BAXY is able: the limit is still not the conversation's to say.
    ("Saca foto ahora", "No puedo hacer fotos."),
    ("keep going without opening apps", "Eso no lo hago."),
])
def test_d_p02_t2_other_failures_in_a_conversation_still_die(user_text: str, draft: str) -> None:
    assert _visible(draft, "conversation", user_text, CONVERSATION) == "asserted_failure"


@pytest.mark.parametrize(("text", "able"), [
    (FOTO, True),
    ("¿Eres capaz de abrir un PDF?", True),
    ("¿Tú eres capaz de leer mi correo?", True),
    ("¿Tienes la capacidad de ver la cámara?", True),
    ("Are you able to take a photo?", True),
    ("Would you be capable of reading my mail?", True),
    ("Do you have the ability to see my screen?", True),
    ("Saca foto ahora", False),
    ("¿Puedes abrir Spotify?", False),
    ("Can you open Spotify?", False),
    ("Mi hermano es capaz de todo", False),
    ("¿Qué puedes hacer?", False),
])
def test_asks_whether_able_reads_the_question_about_baxy_s_ability(text: str, able: bool) -> None:
    assert asks_whether_able(text) is able


# ------------------------------------------------------------------ D-w02-t2: a turn that was not understood
HORA_ALLA = "y si allá son las 10 de la mañana acá qué hora es"
NOT_UNDERSTOOD = (
    '{"kind":"failure","polarity":"failure","cause":"turn_runtime_failure","operationAttempted":false,'
    '"retryable":true}'
)
HORA_DRAFTS = [
    "No puedo determinar la hora en tu lugar porque no tengo acceso a tu ubicación ni a la hora actual de tu zona "
    "horaria.",
    "Como te tuteo y estamos en la misma zona horaria, si allá son las 10 de la mañana acá también son las 10 de la "
    "mañana.",
    "No entiendo esa pregunta porque no tengo información sobre la ubicación del interlocutor.",
]


def test_d_w02_t2_the_recorded_drafts_are_still_vetoed() -> None:
    assert [_visible(draft, "error", HORA_ALLA, NOT_UNDERSTOOD) for draft in HORA_DRAFTS] == [
        "internal_code", "missing_failure", "missing_failure",
    ]


def test_d_w02_t2_stays_without_a_fixed_final() -> None:
    # Owner's review of M75: a fixed «No pude entender…» would turn the ⚠ into a false failure (the message was
    # understood; its wording failed) and the product has no fixed visible replies. The ⚠ stays; the cause is open.
    assert _compose(HORA_DRAFTS, HORA_ALLA, "error", NOT_UNDERSTOOD) == ("", 3)


# ------------------------------------------------------------------ D-w15-t3: a translation of something pointed at
TRADUCELO = "traducelo al ingles que es para mi jefa"
AMBIGUOUS = (
    '{"kind":"clarification","polarity":"pending","cause":"ambiguous_request"}'
)
# M99 (DEV-D v3x D-w15-t3, independent review): the English drafts v3l published were wrong — the question back is in
# the person's language, not the one the translation is asked into. They are refused now; the Spanish ones are asked.
TRADUCELO_ENGLISH_DRAFTS = [
    "Could you clarify which specific detail is missing?",
    "Can you tell me which detail is missing?",
    "Could you please confirm the specific detail you need for your boss?",
]
TRADUCELO_DRAFTS = [
    "¿Qué texto quieres que traduzca al inglés?",
    "¿Cuál es el texto que quieres traducir para tu jefa?",
    "¿Qué quieres que traduzca?",
]


@pytest.mark.parametrize("draft", TRADUCELO_DRAFTS)
def test_d_w15_t3_asking_what_to_translate_is_the_reply(draft: str) -> None:
    assert _visible(draft, "clarification", TRADUCELO, AMBIGUOUS) == ""


@pytest.mark.parametrize("draft", TRADUCELO_ENGLISH_DRAFTS)
def test_d_w15_t3_the_question_back_in_the_translations_language_is_refused(draft: str) -> None:
    assert _visible(draft, "clarification", TRADUCELO, AMBIGUOUS) == "wrong_language"


def test_d_w15_t3_the_first_question_is_published() -> None:
    assert _compose(TRADUCELO_DRAFTS, TRADUCELO, "clarification", AMBIGUOUS) == (TRADUCELO_DRAFTS[0], 1)


@pytest.mark.parametrize(("user_text", "draft"), [
    # The text to translate is in the message: the translation is the reply, not a question.
    ("traduce 'good evening' al español", "¿Qué quieres que traduzca?"),
    ("translate this: good morning", "What would you like me to translate?"),
    ("what is a time zone, one line", "What is a time zone?"),
])
def test_d_w15_t3_a_complete_knowledge_ask_is_still_answered(user_text: str, draft: str) -> None:
    assert _visible(draft, "clarification", user_text, AMBIGUOUS) == "knowledge_question"


def test_d_w15_t3_a_pointed_translation_still_owes_a_question() -> None:
    assert _visible("Lo traduzco enseguida.", "clarification", TRADUCELO, AMBIGUOUS) == "clarification_not_a_question"


@pytest.mark.parametrize(("text", "pointing"), [
    (TRADUCELO, True),
    ("Tradúcemelo al inglés", True),
    ("traduce eso al portugués", True),
    ("translate it to English", True),
    ("translate that please", True),
    ("traduce 'good evening' al español", False),
    ("traduce esto: hola mundo", False),
    ("translate this sentence into Spanish", False),
    ("traduce hola al inglés", False),
    ("¿Qué es un exoplaneta?", False),
])
def test_translation_without_its_text_reads_a_translation_only_pointed_at(text: str, pointing: bool) -> None:
    assert translation_without_its_text(text) is pointing
