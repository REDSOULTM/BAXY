"""uso-51 (2026-11-03, «aumentar el contexto para tener una conversación decente»): the history the mind keeps
(src/baxy_mind/mind.py, Mind._fits and Mind._trim) grows with the room the model server's context leaves beside the
prefix, instead of stopping at the fixed count and characters tuned for ~7.9k tokens of history; and a cut never leaves
more to re-read than the decision's time allows."""
import pathlib

from baxy_mind import mind as mind_module
from baxy_mind.llm_server import REREAD_TOKENS
from baxy_mind.mind import HISTORY_TURNS, TURN_ROOM_TOKENS
from test_mind_final import _mind, _say

PREFIX = 48541  # the product's prefix, measured on the PC (b11609, catalog of 2026-11-03)


def _session(tmp_path: pathlib.Path, context: int, prefix: int = PREFIX):
    mind, server = _mind(tmp_path, [_say(f"Vale {n}.") for n in range(200)])
    server.context = context
    mind.prefix_tokens = prefix
    return mind, server


def _talk(mind, turns: int, first: int = 1) -> None:
    for turn in range(first, first + turns):
        mind.decide(turn, f"pedido {turn}: " + "palabra " * 40)


def test_a_larger_context_keeps_the_game_named_many_turns_ago(tmp_path: pathlib.Path) -> None:
    # The owner's case: «el último juego que te nombré» was gone a few turns later. With 98,304 cells the history has
    # ~46k tokens beside the prefix: thirty short turns (~110 tokens each here) fit, far past the ten of the count.
    mind, _ = _session(tmp_path, 98304)
    mind.decide(1, "ayer estuve jugando Hades toda la tarde")
    _talk(mind, 30, first=2)
    assert mind.trimmed_turns == 0
    assert len(mind._turn_starts()) == 31 > HISTORY_TURNS
    assert any("Hades" in str(m.get("content") or "") for m in mind.conversation)


def test_the_bounds_grow_with_the_room_and_never_fall_below_the_tuned_ones(tmp_path: pathlib.Path) -> None:
    mind, server = _session(tmp_path, 53248)
    assert mind._bounds() == (HISTORY_TURNS, mind_module.HISTORY_CHARS, 53248 - PREFIX - TURN_ROOM_TOKENS)
    server.context = 98304
    turns, chars, tokens = mind._bounds()
    assert tokens == 98304 - PREFIX - TURN_ROOM_TOKENS
    scale = tokens / mind_module.HISTORY_TOKENS
    assert turns == int(HISTORY_TURNS * scale) and chars == int(mind_module.HISTORY_CHARS * scale)
    mind.prefix_tokens = 0  # before the warm-up the prefix is not known: the tuned bounds, as before
    assert mind._bounds()[:2] == (HISTORY_TURNS, mind_module.HISTORY_CHARS)


def test_a_cut_of_a_long_history_leaves_only_what_reads_in_time(tmp_path: pathlib.Path, monkeypatch) -> None:
    # A cut moves the history's start and the model re-reads all that is left (hybrid: its cache is reused from the
    # front). Measured on the PC past the 48.5k-token prefix: ~1,440 tokens/s alone, 500-660 with another model on the
    # GPU, so 60 % of a 46k-token history would take 19-55 s against the decision's 24. A cut keeps at most REREAD_TOKENS.
    mind, server = _session(tmp_path, 98304)
    texts: list[str] = []
    server.tokenize = lambda text: texts.append(text) or [0] * (len(text) // 4)
    turn = 0
    while not mind.trimmed_turns:
        turn += 1
        mind.decide(turn, f"pedido {turn}: " + "palabra " * 400)
    kept = sum(t[2] for t in mind._turn_sizes())
    assert kept <= REREAD_TOKENS + 50  # and the reply written after the cut
    assert turn > HISTORY_TURNS  # the count alone did not cut it


def test_a_cut_leaves_no_more_than_the_servers_cache_reads_in_time(tmp_path: pathlib.Path) -> None:
    # uso-60: on Vulkan with the q8_0 cache the model server reads the history ~8 times slower than on CUDA, and says
    # how much a cut may leave (LlmServer.reread_tokens): the mind keeps that, not REREAD_TOKENS.
    mind, server = _session(tmp_path, 61440)
    server.reread_tokens = 2048
    server.tokenize = lambda text: [0] * (len(text) // 4)
    turn = 0
    while not mind.trimmed_turns:
        turn += 1
        mind.decide(turn, f"pedido {turn}: " + "palabra " * 400)
    assert sum(t[2] for t in mind._turn_sizes()) <= 2048 + 50
