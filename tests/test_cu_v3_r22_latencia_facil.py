"""Ronda 22, latencia de lo fácil (r18 t4-c05 clima 12 s; t4-c04 t2 brillo repetido 10,2 s)."""

from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import llm
from baxy_mind import compose_payload
from baxy_mind import payload_fact_checks
from baxy_mind import weather_facts

ROOT = Path(__file__).resolve().parents[1]

# The read of r18 t4-c05 («clima»), with the split the provider now adds.
WEATHER_READ = {
    "version": 1,
    "location": "Ñuñoa",
    "country": "Chile",
    "locatedBy": "named_place_geocoded",
    "temperatureC": 14.2,
    "condition": "partly_cloudy",
    "today": {"date": "2026-10-08", "maxC": 18.0, "minC": 9.0},
    "laterDays": [{"date": "2026-10-10", "maxC": 19.0}],
    "elapsedMs": {"place": 1800, "forecast": 3400, "total": 5300},
    "authority": "open_meteo_forecast_v1",
}


def test_the_weather_split_of_time_never_reaches_the_narrator() -> None:
    projected = weather_facts._project_weather_read(dict(WEATHER_READ), "como esta el clima hoy")
    assert "elapsedMs" not in projected
    # Contracaso: the weather itself still travels whole.
    assert projected["temperatureC"] == 14.2
    assert projected["location"] == "Ñuñoa"


def test_a_brightness_set_at_the_asked_level_answers_before_any_set() -> None:
    adapter = (ROOT / "src" / "Baxy.Providers.Windows" / "External" / "WindowsDeviceControlAdapter.cs").read_text(
        encoding="utf-8"
    )
    script = adapter.split("private const string BrightnessScript", 1)[1].split('""";', 1)[0]
    same = script.index("changed=$false")
    assert same < script.index("WmiSetBrightness")
    # Contracaso: another level still sets, waits and reads back.
    assert "changed=$true" in script
    assert script.index("Start-Sleep") > same
    assert "baselineValues=$baseline" in script


# Revisión 1, bloqueante 1: el brillo ya puesto vuelve con changed:false y el final no puede decir que se puso.
def _brightness(before: int, after: int, changed: bool) -> dict:
    return {
        "kind": "operation",
        "operation": "system.settings.set",
        "polarity": "success",
        "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "setting": "brightness", "value": after, "changed": changed,
            "baselineValues": [before], "values": [after], "authority": "wmi_monitor_brightness_postread",
        },
    }


ASKED = "pon el brillo al 40"


def test_a_brightness_already_at_the_level_is_a_fact_the_reply_carries() -> None:
    payload = compose_payload._compose_situation_payload(_brightness(40, 40, False), "es", ASKED)
    assert payload["seen"]["alreadyInState"] is True


def test_a_brightness_that_changed_is_not_told_as_already_there() -> None:
    # Contracaso: 30 → 40 was set.
    payload = compose_payload._compose_situation_payload(_brightness(30, 40, True), "es", ASKED)
    assert "alreadyInState" not in payload["seen"]


@pytest.mark.parametrize(
    "reply",
    [
        "El brillo ya estaba al 40 %.",
        "Ya tenías el brillo al 40 %.",
        "The brightness was already at 40%.",
        "The brightness is already set to 40%.",
        "Cambié el brillo al 40 %.",
        "Listo, ajusté el brillo al 40 %.",
        "Puse el brillo al 40 %.",
        "Subí el brillo al 40 %.",
        "I set the brightness to 40%.",
        "Listo, el brillo está al 40 %.",
    ],
)
def test_the_reply_says_the_brightness_already_was_and_claims_no_set(reply: str) -> None:
    # Encargo I2: a setting already there is the floor's (Estabilización F), so the writer's veto of «puse»/«ya» over
    # alreadyInState was never reached and went away. Whatever the model would draft («Puse el brillo al 40 %.», a reply
    # without «ya»), the person hears the floor's sentence and no draft is asked for.
    drafts = _Drafts([reply])
    assert drafts.compose_user_message(ASKED, "status", {"situation": _brightness(40, 40, False)}) == (
        "El brillo ya estaba al 40 %."
    )
    assert drafts.sent == []


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("Puse el brillo al 40 %.", ""),
        ("Subí el brillo al 40 %.", ""),
        ("Bajé el brillo al 40 %.", "unobserved_direction"),
    ],
)
def test_a_brightness_set_from_30_still_says_it_was_set(reply: str, defect: str) -> None:
    # Contracaso: changed:true 30 → 40 sigue diciendo «puse/subí».
    payload = compose_payload._compose_situation_payload(_brightness(30, 40, True), "es", ASKED)
    assert payload_fact_checks._payload_fact_defect(reply, payload, ASKED) == defect


def test_the_floor_says_the_brightness_already_was() -> None:
    from baxy_mind import operation_floor

    already = operation_floor.floor_final(_brightness(40, 40, False), False, None)
    assert "ya estaba" in already and "puse" not in already.lower()
    # Contracaso: the set from 30 is told as done.
    assert "puse el brillo" in operation_floor.floor_final(_brightness(30, 40, True), False, None).lower()


class _Drafts(llm.LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self.sent: list[str] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload["messages"][-1]["content"])
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def test_a_setting_that_already_was_is_said_from_the_floor_and_never_drafted() -> None:
    # Estabilización F: a state that already held is said from the floor (data «unchanged»), before any draft; «Puse
    # el brillo al 40 %.» is never asked for.
    drafts = _Drafts(["Puse el brillo al 40 %.", "El brillo ya estaba al 40 %."])
    text = drafts.compose_user_message(ASKED, "status", {"situation": _brightness(40, 40, False)})
    assert text == "El brillo ya estaba al 40 %."
    assert drafts.sent == []


def test_the_composer_is_not_told_already_for_a_set_from_30() -> None:
    drafts = _Drafts(["Subí el brillo al 40 %."])
    text = drafts.compose_user_message(ASKED, "status", {"situation": _brightness(30, 40, True)})
    assert text == "Subí el brillo al 40 %."
    assert "alreadyInState" not in drafts.sent[0]


# Revisión 1, bloqueante 2: el primer turno que llega con el precalentamiento del decisor todavía leyendo el catálogo.
def test_a_decision_asked_while_the_warmup_reads_waits_on_its_slot_and_keeps_its_prefix() -> None:
    import json
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch

    from baxy_mind import llm_transport

    tools = (("app.open", "Abre una aplicación."), ("web.search", "Busca en la web."))
    signatures = {"app.open": ("appId",), "web.search": ("query",)}
    gate = threading.Event()

    class _Runtime(llm.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            self._gguf = None
            self._parallel_turn_verification = True
            self.posts: list[tuple[dict, dict]] = []
            self.prepared: list[object] = []

        def _decider_slot_state(self, payload):  # noqa: ANN001, ANN201
            return ("estado", payload["messages"][0]["content"])

        # Estabilización A (revisión H5): the warmup builds the decider's saved slot state instead of a chat request.
        def _prepare_slot(self, state, cancellation):  # noqa: ANN001, ANN201
            self.prepared.append(state)
            gate.wait(5)

        def _post(self, payload, **kwargs):  # noqa: ANN001, ANN201
            self.posts.append((payload, kwargs))
            content = json.dumps({"request": "abre spotify", "decision": "talk", "operations": [], "question": ""})
            return {"choices": [{"message": {"content": content}}]}

    runtime = _Runtime()
    runtime.warm_decider(tools, signatures=signatures)
    deadline = time.monotonic() + 5
    while not runtime.prepared and time.monotonic() < deadline:
        time.sleep(0.005)
    warming = runtime._decider_warmup
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], tools, signatures=signatures)
    while not runtime.posts and time.monotonic() < deadline:
        time.sleep(0.005)
    (decision, decision_kwargs), = runtime.posts
    # The warmup is not cancelled by the turn: the state it builds is the one the decision starts from.
    assert warming is not None and not warming.cancelled
    assert decision_kwargs["reserved_slot"] is True and decision["cache_prompt"] is True
    assert decision_kwargs["slot_state"] == runtime.prepared[0]
    gate.set()
    runtime.end_request()

    # The slot pool sends both to the one reserved slot, the decision after the warmup: the server then reads
    # only the decision's own message after the saved catalog state, never the catalog a second time beside it.
    pool = llm_transport.ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    warm_bytes = b""
    decision_bytes = json.dumps(decision).encode()
    with (
        patch("baxy_mind.llm_transport.http.client.HTTPConnection"),
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        warm_lease = pool.acquire("http://127.0.0.1:1/v1/chat/completions", 1.0, reserved=True,
                                  request_data=warm_bytes)
        waiting = executor.submit(pool.acquire, "http://127.0.0.1:1/v1/chat/completions", 2.0, reserved=True,
                                  request_data=decision_bytes)
        time.sleep(0.05)
        assert not waiting.done()
        pool.release(warm_lease, reusable=True)
        assert waiting.result(timeout=1.0).slot == warm_lease.slot
    pool.close()
