"""The output budget of a reply: tokens by the reply's shape, and what the time left lets a writer ask for.
"""

from __future__ import annotations

from .semantic import dialogue as dialogue_slot
from .semantic.conversation import asks_an_extended_answer


_CONTENT_SHAPES = frozenset({"content_draft", "roleplay_draft"})
_BRIEF_SHAPES = frozenset({
    "constraint_ack", "reassurance_ack", "preference_ack", "versus_opinion", "sarcastic_answer",
    "assistant_desire", "misnamed_greeting", "identity", "visual_content_boundary", "spelling",
    "news_watch_limit",
})


def _conversation_max_tokens(
    presentation_shape: str | None, conversation_kind: str | None, text: str, *, retry: bool = False,
    follows_content: bool = False,
) -> int:
    """The output budget of a conversational reply, sized to the reply's shape.

    ``follows_content``: the turn follows written content (``_follows_written_content``) and keeps its budget."""

    if presentation_shape in _CONTENT_SHAPES:
        # Tanda 4f «haz un relato basado en el año 2090»: 128 tokens cut the
        # story mid-sentence («…del norte de la Antártida, donde»).
        return 320
    if presentation_shape in {"how_it_works", "free_content"}:
        return 160
    if presentation_shape in _BRIEF_SHAPES:
        return 128
    if presentation_shape is not None:
        return 64
    if follows_content and conversation_kind in {"knowledge", "followup", None} and not dialogue_slot.is_social(text):
        # Uso real v3 tanda 2 «dame 5 ideas de cena…» then «no, te pedí 5 che, me tiraste menos»: the follow-up had no
        # shape of its own, was budgeted as a one-sentence answer, and both drafts that wrote the five ideas again were
        # cut (128 and 160 tokens, finish=length); the recovery then said «Solo te proporcioné dos recetas». A
        # follow-up of written content keeps the content's budget; thanks or a social reaction keeps its own.
        return 320
    if retry:
        # Verification 2026-09-25 (layer A, real log «Por dios, odio estos fallos»): the repair is written inside a JSON
        # wrapper, and at 96 tokens a two-sentence Spanish reply was cut twice (truncated_structured_reply) and the turn
        # became a question. The prompt keeps it short; the cap only has to hold the wrapper and two sentences.
        return 160
    if conversation_kind in {"knowledge", None}:
        return 256 if asks_an_extended_answer(text) else 128
    return {"social": 64, "unsupported": 96, "unsupported_language": 96}.get(conversation_kind, 128)


# Uso real v3 tanda 2 «dale, la segunda como se hace? pasame los pasos cortitos»: the recipe writer asked 420 tokens
# with a 10 s composition budget; the model was writing ≈26 tokens per wall second beside the turn's other work (the
# prepared reply of the same tanda: 269 tokens in 10,4 s), so the draft ran out of time at 8,98 s and the fallback was
# left 0 ms. A writer's budget is what the measured speed can write in the time left, after the fallback's own time.
_DECODE_RATE_PRIOR = 26.0  # tokens per wall second, the tanda's measure, until this process measures its own
_DECODE_RATE_WEIGHT = 0.3  # the weight of the newest measure in the running estimate
_DECODE_RATE_MIN_TOKENS = 32  # a shorter decode is mostly prompt time and says little of the speed
_FALLBACK_RESERVE_TOKENS = 48  # the fallback's one sentence, written after a writer that gave nothing
_COMPOSE_OVERHEAD_SECONDS = 0.5  # prompt read and transport of one composition
_CONSULTED_MIN_TOKENS = 120  # below this a recipe, a plot or an analysis is not worth starting: the fallback answers
_WORDS_PER_TOKEN = 0.6  # Spanish and English prose, with the margin a list's markup takes
# M146 (DEV-D v4m–v4p D-p35-t1): below this much of the request's own budget no retry is asked, the last resort answers.
_RETRY_MIN_REQUEST_SECONDS = 3.0


def _decode_rate_of(response: object, elapsed_seconds: float) -> float | None:
    """Tokens written per wall second by one completed call (prompt, queue and decode together), None when the call
    wrote too few tokens to tell."""

    if not isinstance(response, dict) or elapsed_seconds <= 0:
        return None
    timings = response.get("timings") if isinstance(response.get("timings"), dict) else {}
    written = timings.get("predicted_n")
    if not isinstance(written, (int, float)) or isinstance(written, bool) or written < _DECODE_RATE_MIN_TOKENS:
        return None
    # The call's own prompt read is not writing speed: a reader that reads 3,000 tokens and writes 40 would otherwise
    # measure ~15 tokens per second and leave every later recipe under _CONSULTED_MIN_TOKENS. The writer's own prompt
    # is reserved apart (_COMPOSE_OVERHEAD_SECONDS); the queue and the other work beside it stay in the measure.
    prompt_ms = timings.get("prompt_ms")
    numeric = isinstance(prompt_ms, (int, float)) and not isinstance(prompt_ms, bool)
    read_seconds = prompt_ms / 1000.0 if numeric else 0.0
    if 0 < read_seconds < elapsed_seconds:
        elapsed_seconds -= read_seconds
    return float(written) / elapsed_seconds


def _affordable_max_tokens(wanted: int, remaining_seconds: float | None, rate: float | None) -> int:
    """The tokens a writer can ask for: ``wanted`` when no deadline binds, else what ``rate`` writes in the time left
    after the fallback's reserve (``_FALLBACK_RESERVE_TOKENS``) and the call's overhead; never more than ``wanted``,
    and 0 when nothing fits."""

    if remaining_seconds is None:
        return wanted
    speed = rate if isinstance(rate, (int, float)) and rate > 0 else _DECODE_RATE_PRIOR
    usable = remaining_seconds - _COMPOSE_OVERHEAD_SECONDS * 2 - _FALLBACK_RESERVE_TOKENS / speed
    return max(0, min(wanted, int(usable * speed)))
