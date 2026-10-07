"""M128 (D58, 2026-10-02): the decider reads what was said in the conversation, never the App's failure marker.

Evidence (windows v4i-devF / v4i-devD at 8a65e023, history rebuilt from the run's activity events: 612 of 612 turns
match the App's message count): when every draft of a reply is refused, the App shows «⚠ (code)» in BAXY's place
(``MainWindowViewModel.CompositionFailureFallback``) and sends it as an assistant turn (``BuildMindHistory``). 4 of
612 BAXY messages were that marker; F-w22-t3 «the signed one» after «can you summarize the lease PDF in there?» → ⚠
was decided file.open where the isolated decider, reading the conversation without it, read the PDF.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic import decider

SYSTEM = "S"
ROOT = pathlib.Path(__file__).resolve().parents[1]


def _said(messages: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(message["role"], message["content"]) for message in messages]


def test_the_failure_marker_is_not_read_and_the_request_before_it_stays() -> None:
    history = [
        {"role": "user", "content": "could you open my Downloads folder please"},
        {"role": "assistant", "content": "I have opened your Downloads folder."},
        {"role": "user", "content": "great, can you summarize the lease PDF in there?"},
        {"role": "assistant", "content": "⚠ (no_response;retry_exhausted)"},
        {"role": "user", "content": "the signed one"},
    ]
    assert _said(decider.messages(SYSTEM, "the signed one", history)) == [
        ("system", SYSTEM),
        ("user", "could you open my Downloads folder please"),
        ("assistant", "I have opened your Downloads folder."),
        ("user", "great, can you summarize the lease PDF in there?"),
        ("user", "the signed one"),
    ]


def test_every_diagnostic_code_the_app_writes_is_the_marker() -> None:
    for code in ("no_response;retry_exhausted", "no_response;recovery:no_response;retry_exhausted",
                 "reversed_result;retry_exhausted", "compose_unavailable"):
        sent = decider.messages(SYSTEM, "y ahora?", [
            {"role": "user", "content": "pon lofi"}, {"role": "assistant", "content": f"⚠ ({code})"},
        ])
        assert _said(sent)[1:] == [("user", "pon lofi"), ("user", "y ahora?")]


def test_the_marker_does_not_take_a_place_of_the_window() -> None:
    history = [
        {"role": "user", "content": "pon la playlist de lofi"},
        {"role": "assistant", "content": "Suena «Lofi para estudiar» en Spotify."},
        {"role": "user", "content": "sube el volumen al 30"},
        {"role": "assistant", "content": "Volumen al 30 %."},
        {"role": "user", "content": "bájale un poco"},
        {"role": "assistant", "content": "⚠ (no_response;retry_exhausted)"},
        {"role": "user", "content": "como 15"},
    ]
    sent = decider.messages(SYSTEM, "como 15", history)
    assert len(sent) == 2 + decider.HISTORY_TURNS
    assert _said(sent)[1:-1] == [
        ("assistant", "Suena «Lofi para estudiar» en Spotify."),
        ("user", "sube el volumen al 30"),
        ("assistant", "Volumen al 30 %."),
        ("user", "bájale un poco"),
    ]


def test_what_baxy_or_the_person_said_is_kept_even_with_the_sign() -> None:
    reply = "⚠ (aviso) La batería está al 9 %: conecta el cargador."
    said = "⚠ (no_response;retry_exhausted)"
    history = [
        {"role": "user", "content": "cómo va la batería"},
        {"role": "assistant", "content": reply},
        {"role": "user", "content": said},
        {"role": "assistant", "content": "¿Qué significa ese aviso para ti?"},
    ]
    assert _said(decider.messages(SYSTEM, "nada, olvídalo", history))[1:] == [
        ("user", "cómo va la batería"),
        ("assistant", reply),
        ("user", said),
        ("assistant", "¿Qué significa ese aviso para ti?"),
        ("user", "nada, olvídalo"),
    ]


def test_the_marker_is_the_one_the_app_writes() -> None:
    source = (ROOT / "src" / "Baxy.App" / "MainWindowViewModel.cs").read_text(encoding="utf-8")
    source = source.replace("\r\n", "\n")
    # Live 2026-10-07: the App writes the floor's compositionFailures line, the marker only when the data has none;
    # the decider drops both (``decider._is_composition_failure``).
    assert "OperationFloor.CompositionFailureSentence(" in source
    assert '?? "⚠ (" + failure + ")";' in source


class _Runtime(LlmRuntime):
    """The runtime without a server: ``_post`` records the request the decider sends."""

    def __init__(self) -> None:
        self._gguf = None
        self._parallel_turn_verification = False
        self.posts: list[dict[str, Any]] = []

    def _post(self, payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        self.posts.append(payload)
        content = json.dumps({"request": "Lee el PDF.", "decision": "talk", "operations": [], "question": ""})
        return {"choices": [{"message": {"content": content}}]}


def test_the_decider_request_after_a_failed_reply_is_the_one_without_the_marker() -> None:
    tools = (("document.pdf.read", "Lee un PDF."), ("file.open", "Abre un archivo."))
    signatures = {"document.pdf.read": ("path",), "file.open": ("path",)}
    asked = [{"role": "user", "content": "summarize the lease PDF in Downloads"}]
    runtime = _Runtime()
    runtime.decide_in_context(
        "the signed one",
        [*asked, {"role": "assistant", "content": "⚠ (no_response;retry_exhausted)"},
         {"role": "user", "content": "the signed one"}],
        tools, signatures=signatures,
    )
    assert runtime.posts[0] == runtime._decider_payload("the signed one", asked, tools, signatures)[0]
