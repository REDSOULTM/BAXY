"""M69: the owner script replayed in the real app (guion v3h, dueno-2026-09-21 turns 46 and 47).

- t46 «activalo» after the microphone was muted: audio.microphone.mute {state:false} succeeded with muted=false, and
  the final said «El micrófono está desactivado.» — the opposite. The narrator reads the microphone's state in words
  (seen.microphone) and a draft that says it off over muted=false dies as reversed_mute.
- t47 «activa mi microfono» already active: the adapter said microphone_already_unmuted before any boundary and the
  final said «…no hubo cambios al intentar silenciarlo». The typed «asked state already held» failure names what was
  asked, carries outcome already_as_asked, and a draft that claims an attempt dies as extra_claim. A limit reached
  («volume_already_at_*») stays an ordinary failure.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm


def _unmuted() -> dict[str, object]:
    return {
        "kind": "operation",
        "operation": "audio.microphone.mute",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1,
            "baselineMuted": True,
            "muted": False,
            "authority": "windows_core_audio_capture_endpoint_postread",
        },
    }


def _muted() -> dict[str, object]:
    situation = _unmuted()
    situation["observed"] = dict(situation["observed"], baselineMuted=False, muted=True)  # type: ignore[arg-type]
    return situation


def _held(code: str, operation: str = "audio.microphone.mute") -> dict[str, object]:
    return {
        "kind": "operation",
        "operation": operation,
        "polarity": "failure",
        "verified": False,
        "succeeded": False,
        "error": code,
    }


def _defect(text: str, user_text: str, situation: dict[str, object], intent: str = "status") -> str:
    return llm.compose_visible_defect(text, intent, user_text, {"situation": situation})


@pytest.mark.parametrize(
    ("language", "now", "before"),
    [
        ("es", "activo: encendido, sin silenciar, capta sonido", "silenciado: no capta sonido"),
        ("en", "active: on, not muted, picking up sound", "muted: silenced, not picking up sound"),
    ],
)
def test_the_narrator_reads_the_microphone_state_in_words(language: str, now: str, before: str) -> None:
    payload = llm._compose_situation_payload(_unmuted(), language, "activalo")
    # The bare booleans (muted, baselineMuted) are gone: the state is said in words.
    assert payload["seen"] == {"microphone": now, "microphoneBefore": before}
    assert "seen.microphone" in llm._compose_shape_instruction(_unmuted(), language, "activalo")


@pytest.mark.parametrize(
    ("text", "user_text", "expected"),
    [
        ("El micrófono está desactivado.", "activalo", "reversed_mute"),
        ("Tu micrófono está apagado.", "activalo", "reversed_mute"),
        ("The microphone is off.", "unmute my microphone", "reversed_mute"),
        ("El micrófono está activo.", "activalo", ""),
        ("Activé el micrófono; ya no está silenciado.", "activalo", ""),
        ("The microphone was muted and is now active.", "unmute my microphone", ""),
    ],
)
def test_an_unmuted_microphone_is_never_told_off(text: str, user_text: str, expected: str) -> None:
    assert _defect(text, user_text, _unmuted()) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("El micrófono está activo.", "reversed_mute"),
        ("El micrófono está silenciado.", ""),
        ("El micrófono ya no está activo.", ""),
        ("El micrófono estaba activo y ahora está silenciado.", ""),
    ],
)
def test_a_muted_microphone_is_never_told_on(text: str, expected: str) -> None:
    assert _defect(text, "silencia mi micrófono", _muted()) == expected


def test_the_asked_state_that_already_held_names_what_was_asked() -> None:
    payload = llm._compose_situation_payload(_held("microphone_already_unmuted"), "es", "activa mi microfono")
    assert payload["outcome"] == "already_as_asked"
    assert "asked to turn the microphone on" in payload["cause"]
    assert "nothing was attempted" in payload["cause"]
    limit = llm._compose_situation_payload(_held("volume_already_at_maximum", "audio.volume.adjust"), "es", "sube")
    assert limit["outcome"] == "failed"


@pytest.mark.parametrize(
    ("code", "held"),
    [
        ("microphone_already_muted", True),
        ("microphone_already_unmuted", True),
        ("airplane_mode_already_on", True),
        ("airplane_mode_already_off", True),
        ("volume_already_at_maximum", False),
        ("volume_already_at_maximum_muted", False),
        ("volume_already_at_minimum", False),
        ("zip_already_exists", False),
    ],
)
def test_only_the_asked_state_family_is_held(code: str, held: bool) -> None:
    assert llm._failure_is_an_asked_state_held(_held(code)) is held
    wrapped = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "reason": json.dumps(_held(code))}
    assert llm._failure_is_an_asked_state_held(wrapped) is held


@pytest.mark.parametrize(
    ("text", "user_text", "expected"),
    [
        ("El micrófono ya estaba activo, por lo que no hubo cambios al intentar silenciarlo.",
         "activa mi microfono", "extra_claim"),
        ("Intenté activarlo, pero ya estaba activo.", "activa mi microfono", "extra_claim"),
        ("I tried to unmute it, but it was already on.", "unmute my microphone", "extra_claim"),
        ("El micrófono ya estaba desactivado.", "activa mi microfono", "reversed_mute"),
        ("The microphone was already off.", "unmute my microphone", "reversed_mute"),
        ("Listo, activé el micrófono.", "activa mi microfono", "reversed_polarity"),
        ("El micrófono ya está activo.", "activa mi microfono", ""),
        ("Tu micrófono ya estaba activo, no cambié nada.", "activa mi microfono", ""),
        ("The microphone is already active.", "unmute my microphone", ""),
    ],
)
def test_an_unmute_that_already_held_is_told_as_the_state(text: str, user_text: str, expected: str) -> None:
    assert _defect(text, user_text, _held("microphone_already_unmuted")) == expected


def test_a_mute_that_already_held_is_never_told_on() -> None:
    held = _held("microphone_already_muted")
    assert _defect("El micrófono ya estaba activo.", "silencia mi microfono", held) == "reversed_mute"
    assert _defect("El micrófono ya estaba silenciado.", "silencia mi microfono", held) == ""


def test_a_mission_step_that_already_held_names_its_cause() -> None:
    # A plan step whose asked state already held counts as done and travels among the summary's steps.
    summary = {
        "kind": "status",
        "polarity": "success",
        "cause": "mission_completed",
        "steps": [json.dumps(_held("microphone_already_muted"))],
    }
    assert "microphone_already_muted" in llm._situation_error_codes(summary)
