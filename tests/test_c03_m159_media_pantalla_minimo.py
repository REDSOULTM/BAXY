"""M159 (2026-10-04): a window that does not fit in half the screen is placed against the asked side and told so.

On DEV-I v4w, I-s048 «pasame la ventana de spotify a la derecha» (no history), I-w21-t2, H-w01-t2 and F-w28-t3 all
ended «No se pudo colocar la ventana de Spotify en la mitad derecha porque la verificación del lado derecho falló.»:
half of the 1536-wide work area is 768 and Spotify will not be narrower than about 814, so the exact-half check could
never pass. The provider now leaves such a window flush against the asked edge at its own minimum and verifies that
placement (C#: WindowSnapMinimumSizeTests, M159SnapBeyondHalfFactTests); the receipt carries ``fitsInHalf`` false and
the half's width. Here: the writer is told that fact, a draft that says only «la mitad derecha» is refused, a draft
that says it does not fit is published, the floor says it too, and a window that fits is told as before.

Every phrasing below except the row's own is ours.
"""

from __future__ import annotations

import json

from baxy_mind import llm, operation_floor


class _Scripted(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time; it keeps what it was sent."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload)
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _compose(text: str, situation: dict, drafts: list[str]) -> tuple[str, _Scripted]:
    writer = _Scripted(drafts)
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    return writer.compose_user_message(text, "status", facts), writer


def _window(x: int, width: int) -> dict:
    return {"windowId": "win_5bd1b7a3c2e94f0a8d6e1f2a3b4c5d6e", "processId": 9120, "processName": "Spotify",
            "title": "Mon Laferte - Mi Buen Amor", "state": "normal", "foreground": True, "x": x, "y": 0,
            "width": width, "height": 816}


def _snap(side: str, window: dict, **beyond: object) -> dict:
    return {"kind": "operation", "operation": "window.snap", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "side": side, "window": window, **beyond}}


def _plan(snap: dict) -> dict:
    """What the shell's mission returns for «resolve the window, then place it» (I-s048's plan)."""

    resolved = {"kind": "operation", "operation": "window.resolve", "polarity": "success", "verified": True,
                "succeeded": True, "readOnly": True,
                "observed": {"version": 1, "windows": [_window(722, 814)], "count": 1}}
    return {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
            "steps": [json.dumps(resolved, ensure_ascii=False),
                      json.dumps({**snap, "readOnly": False}, ensure_ascii=False)]}


SPOTIFY_RIGHT = _snap("right", _window(722, 814), fitsInHalf=False, halfWidth=768)
SPOTIFY_LEFT = _snap("left", _window(0, 814), fitsInHalf=False, halfWidth=768)
WORD_LEFT = _snap("left", {**_window(0, 768), "processName": "WINWORD", "title": "Word"})


def _sent_text(writer: _Scripted) -> str:
    return "\n".join(message["content"] for payload in writer.sent for message in payload["messages"])


# ------------------------------------------------------------------ the row, and the fact it is told


def test_the_row_is_told_on_its_side_and_not_in_half_the_screen() -> None:
    final, writer = _compose(
        "pasame la ventana de spotify a la derecha",
        _plan(SPOTIFY_RIGHT),
        [
            "He colocado la ventana de Spotify en la mitad derecha de la pantalla.",
            "Puse Spotify a la derecha, pero no cabe en media pantalla y ocupa un poco más.",
        ],
    )
    assert final == "Puse Spotify a la derecha, pero no cabe en media pantalla y ocupa un poco más."
    assert "fitsInHalf=false" in _sent_text(writer)


def test_the_fact_reaches_the_writer_single_step_and_in_a_plan() -> None:
    for situation in (SPOTIFY_RIGHT, _plan(SPOTIFY_RIGHT)):
        payload = llm._compose_situation_payload(situation, "es", "pasame la ventana de spotify a la derecha")
        seen = llm._snap_beyond_half(payload)
        assert seen is not None
        assert (seen["side"], seen["fitsInHalf"], seen["halfWidth"], seen["window"]["width"]) == (
            "right", False, 768, 814)


def test_english_and_other_words_say_it_their_way() -> None:
    final, _ = _compose(
        "snap spotify to the right side",
        SPOTIFY_RIGHT,
        [
            "I snapped Spotify to the right half of the screen.",
            "I put Spotify on the right, but it doesn't fit in half the screen, so it takes a little more.",
        ],
    )
    assert final == "I put Spotify on the right, but it doesn't fit in half the screen, so it takes a little more."
    final, _ = _compose(
        "mandá spotify al lado izquierdo",
        SPOTIFY_LEFT,
        ["Spotify quedó en la mitad izquierda.", "Dejé Spotify a la izquierda; es un poco más ancha que la mitad."],
    )
    assert final == "Dejé Spotify a la izquierda; es un poco más ancha que la mitad."


def test_when_every_draft_says_only_the_half_the_floor_says_it_does_not_fit() -> None:
    final, _ = _compose(
        "pasame la ventana de spotify a la derecha",
        SPOTIFY_RIGHT,
        ["Coloqué Spotify en la mitad derecha.", "Listo, Spotify está en la mitad derecha.", "Ya está a la derecha."],
    )
    assert "a la derecha" in final
    assert "no cabe en media pantalla y ocupa un poco más" in final
    assert operation_floor.floor_final(SPOTIFY_RIGHT, True).endswith(
        "it does not fit in half the screen and takes a little more.")


# ------------------------------------------------------------------ what does not change


def test_a_window_that_fits_is_told_as_before() -> None:
    final, writer = _compose(
        "poné word a la izquierda",
        WORD_LEFT,
        ["Coloqué la ventana de Word en la mitad izquierda de la pantalla."],
    )
    assert final == "Coloqué la ventana de Word en la mitad izquierda de la pantalla."
    assert "fitsInHalf" not in _sent_text(writer)
    assert "no cabe" not in operation_floor.floor_final(WORD_LEFT, False)


def test_a_failed_snap_carries_no_such_fact() -> None:
    failed = {"kind": "operation", "operation": "window.snap", "polarity": "failure", "verified": False,
              "succeeded": False, "error": "verification_failed", "attempted": {"side": "right"}}
    payload = llm._compose_situation_payload(failed, "es", "pasame la ventana de spotify a la derecha")
    assert llm._snap_beyond_half(payload) is None
    assert not llm._snap_beyond_half_untold("No pude colocar la ventana a la derecha.", payload)
