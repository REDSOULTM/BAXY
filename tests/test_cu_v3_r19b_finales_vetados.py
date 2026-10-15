"""Ronda 19b, palanca «finales vetados» (auditoría estab2/hallazgos.md 13, 17 y 19; tandas_r17).

a. t3-c14 «dame 3 recetas rapidas con atun y arroz…»: web.search verificado con resultados, el redactor vence el
   tiempo antes de cualquier borrador y la mente no contestaba nada; la App publicaba «No pude contarte cómo salió lo
   que pediste.». Ahora la mente dice la causa con lo pedido (datos: operation_floor «searchUntold»). Contracasos:
   tres borradores vetados siguen en el no-encontrado; una búsqueda sin resultados o fallida no toma esta frase.
b. t3-c04 «He bajado el brillo al 30%.» / «Bajé el brillo al 30%.» vetados por unbacked_act sobre system.settings.set:
   el set respalda subir/bajar, y la dirección sólo pasa cuando el nivel leído antes (baselineValues, que el
   proveedor ahora guarda) la muestra. Contracasos: sin lectura previa, o con la dirección contraria, sigue vetada.
c. t1-c09 (t21) «No envié el mensaje a Ron92 en Discord porque el cliente… no estaba abierto.» vetado dos veces por
   missing_failure sobre un message.recipient.resolve que dejó message.send sin hacer (notDone). Contracasos: «No
   cerré Discord» sigue vetado, y el reintento real que dice el envío como hecho («le envié el mensaje…, pero no se
   envió») también.

Textos de los compose_audit reales."""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm, operation_floor
from baxy_mind import compose_payload
from baxy_mind import payload_fact_checks
from baxy_mind import search_report
from baxy_mind.visible_defect import compose_visible_defect


# ---------------------------------------------------------------- c. lo no hecho del plan es el acto fallido
DISCORD_SITUATION = (
    '{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":'
    '"operation","operation":"message.recipient.resolve","polarity":"failure","verified":false,"succeeded":false,'
    '"error":"discord_client_not_running","target":"Ron92","attempted":{"channel":"discord","recipient":"Ron92"},'
    '"notDone":[{"operation":"message.send","target":"Ron92"}]}}'
)
DISCORD_SAID = "mandale a ron92 por discord que hoy no juego, que arranquen sin mi"


def _discord_defect(draft: str) -> str:
    return compose_visible_defect(draft, "error", DISCORD_SAID, {"situation": DISCORD_SITUATION})


def test_c_the_failure_told_as_the_send_not_done_is_published():
    # t1 compose_audit línea 44 (first, missing_failure).
    draft = "No envié el mensaje a Ron92 en Discord porque el cliente de la aplicación no estaba abierto."
    assert _discord_defect(draft) == ""


@pytest.mark.parametrize(
    "draft",
    [
        # t1 compose_audit línea 46 (retry): dice el envío como hecho antes de negarlo.
        "A Ron92 en Discord le envié el mensaje de que no jugué hoy y que arranquen sin mí, pero el mensaje no se "
        "envió porque el cliente de Discord no estaba abierto.",
        # Un acto que ni el paso fallido ni lo no hecho son.
        "No cerré Discord porque el cliente no estaba abierto.",
        # Una falla dicha como éxito.
        "Le envié el mensaje a Ron92 en Discord.",
        "Envié el mensaje a Ron92.",
    ],
)
def test_c_a_failure_told_as_done_or_another_act_is_still_refused(draft):
    assert _discord_defect(draft) == "missing_failure", draft


def test_c_the_not_done_of_the_situation_counts_and_the_retry_that_tells_it_done_is_still_refused():
    # Revisión r19b: lo-no-hecho (ronda 19) lee también el notDone de la situación; el reintento contradictorio
    # sigue vetado ahí también, porque el acto negado y afirmado no cuenta.
    situation = json.loads(DISCORD_SITUATION)
    situation["notDone"] = situation["reason"].pop("notDone")
    facts = {"situation": json.dumps(situation)}
    honest = "No envié el mensaje a Ron92 en Discord porque el cliente de la aplicación no estaba abierto."
    retry = (
        "A Ron92 en Discord le envié el mensaje de que no jugué hoy y que arranquen sin mí, pero el mensaje no se "
        "envió porque el cliente de Discord no estaba abierto."
    )
    assert compose_visible_defect(honest, "error", DISCORD_SAID, facts) == ""
    assert compose_visible_defect(retry, "error", DISCORD_SAID, facts) == "missing_failure"


def test_c_without_not_done_only_the_failed_steps_own_acts_count():
    situation = json.loads(DISCORD_SITUATION)
    del situation["reason"]["notDone"]
    draft = "No envié el mensaje a Ron92 en Discord porque el cliente de la aplicación no estaba abierto."
    assert compose_visible_defect(draft, "error", DISCORD_SAID, {"situation": json.dumps(situation)}) == (
        "missing_failure"
    )


# ---------------------------------------------------------------- b. la dirección del brillo observada
def _brightness(before: int | None, value: int = 30, setting: str = "brightness") -> dict:
    observed = {"version": 1, "setting": setting, "value": value, "authority": "wmi_monitor_brightness_postread"}
    if before is not None:
        observed["baselineValues"] = [before]
    return {
        "kind": "operation", "operation": "system.settings.set", "polarity": "success", "verified": True,
        "succeeded": True, "observed": observed,
    }


def _brightness_defect(draft: str, situation: dict, said: str = "bajale el brillo al 30") -> str:
    facts = {"situation": json.dumps(situation, ensure_ascii=False)}
    payload = compose_payload._compose_situation_payload(situation, "es", said)
    return compose_visible_defect(draft, "status", said, facts, said=said) or payload_fact_checks._payload_fact_defect(
        draft, payload, said, said=said,
    )


# t3 compose_audit líneas 9, 11 y 13 (trace t4).
LOWERED_FINALS = ["He bajado el brillo al 30%.", "Bajé el brillo al 30%.", "He reducido el brillo a 30."]


@pytest.mark.parametrize("draft", LOWERED_FINALS)
def test_b_a_lowering_the_readings_show_is_published(draft):
    assert _brightness_defect(draft, _brightness(before=80)) == "", draft


def test_b_a_raise_the_readings_show_is_published():
    assert _brightness_defect("Subí el brillo al 70%.", _brightness(before=20, value=70), "subí el brillo al 70") == ""


@pytest.mark.parametrize("draft", LOWERED_FINALS)
def test_b_without_the_level_before_no_direction_is_said(draft):
    assert _brightness_defect(draft, _brightness(before=None)) != "", draft


@pytest.mark.parametrize("draft", ["Bajé el brillo al 30%.", "He bajado el brillo al 30%."])
def test_b_a_direction_the_readings_contradict_is_refused(draft):
    # The level was 10 before: setting 30 raised it.
    assert _brightness_defect(draft, _brightness(before=10)) != "", draft


def test_b_the_plain_final_still_passes_without_the_level_before():
    assert _brightness_defect("Puse el brillo al 30 %.", _brightness(before=None)) == ""


def _chain(*levels: dict) -> dict:
    steps = [json.dumps(level, ensure_ascii=False) for level in levels]
    steps.append(json.dumps({
        "kind": "operation", "operation": "app.open", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"name": "Calculadora", "alreadyRunning": False},
    }))
    return {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": len(steps),
            "steps": steps}


CHAIN_SAID = "bajale el brillo al 30 y abre la calculadora"


@pytest.mark.parametrize("before", [10, None])
def test_b_in_a_chain_a_direction_the_readings_do_not_show_is_refused(before):
    # Revisión r19b: the set backs «bajar» in any step, so the direction is judged on each level step of the mission
    # too; from 10 (or with no level read before) setting 30 lowered nothing.
    draft = "Bajé el brillo al 30 % y abrí la Calculadora."
    assert _brightness_defect(draft, _chain(_brightness(before=before)), CHAIN_SAID) == "unobserved_direction"


def test_b_in_a_chain_the_lowering_the_readings_show_and_the_plain_set_are_published():
    assert _brightness_defect(
        "Bajé el brillo al 30 % y abrí la Calculadora.", _chain(_brightness(before=80)), CHAIN_SAID,
    ) == ""
    assert _brightness_defect(
        "Puse el brillo al 30 % y abrí la Calculadora.", _chain(_brightness(before=10)), CHAIN_SAID,
    ) == ""


def test_b_in_a_chain_each_direction_needs_a_step_that_shows_it():
    # Two level steps: brightness lowered from 80, a second set raised from 10. «subí» and «bajé» each have their
    # step; a raise with only lowerings observed does not.
    lowered, raised = _brightness(before=80), _brightness(before=10, value=60)
    said = "bajale el brillo al 30, despues al 60 y abre la calculadora"
    both = "Bajé el brillo al 30 %, lo subí al 60 % y abrí la Calculadora."
    assert _brightness_defect(both, _chain(lowered, raised), said) == ""
    assert _brightness_defect(both, _chain(lowered, _brightness(before=90, value=60)), said) == (
        "unobserved_direction"
    )


def test_b_the_direction_acts_back_no_other_setting():
    # Airplane mode has no level read before: «subí» stays unsaid.
    situation = _brightness(before=None, value=1, setting="airplane_mode")
    assert _brightness_defect("Subí el modo avión.", situation, "pone el modo avion") != ""


def test_b_the_set_receipt_carries_the_level_read_before():
    from pathlib import Path

    adapter = (
        Path(__file__).resolve().parents[1] / "src" / "Baxy.Providers.Windows" / "External"
        / "WindowsDeviceControlAdapter.cs"
    ).read_text(encoding="utf-8")
    script = adapter.split("private const string BrightnessScript", 1)[1].split('""";', 1)[0]
    assert "baselineValues=$baseline" in script


# ---------------------------------------------------------------- a. el redactor sin tiempo sobre una búsqueda
class _OutOfTime(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time (or fails with ``error``)."""

    def __init__(self, drafts: list[str] | None = None, error: OSError | None = None) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts or ())
        self.error = error

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        if not self.drafts:
            raise self.error or TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


RECIPES_SAID = "dame 3 recetas rapidas con atun y arroz q tengo poca plata"


def _search(results: list[dict] | None = None, ok: bool = True, query: str = "recetas rapidas con atun y arroz") -> dict:
    results = [
        {"title": "Arroz con atún fácil y económico", "url": "https://www.recetasbaratas.cl/arroz-con-atun/",
         "snippet": "Un arroz con atún listo en 20 minutos con ingredientes de despensa."},
        {"title": "Tortilla de arroz y atún", "url": "https://cocinarapida.com/tortilla-arroz-atun",
         "snippet": "Mezcla arroz cocido, atún y huevo y cuaja en sartén."},
    ] if results is None else results
    situation: dict = {"kind": "operation", "operation": "web.search", "polarity": "success" if ok else "failure",
                       "verified": ok, "succeeded": ok}
    if ok:
        situation["observed"] = {"version": 1, "query": query, "count": len(results), "results": results}
    else:
        situation["error"] = "web_search_unavailable"
    return situation


def _compose(said: str, situation: dict, drafts: list[str] | None = None, intent: str = "status") -> str:
    facts = {"situation": json.dumps(situation, ensure_ascii=False)}
    return _OutOfTime(drafts).compose_user_message(said, intent, facts, said=said)


def _untold() -> dict:
    return operation_floor.floor_data()["searchUntold"]


def test_a_a_search_whose_writer_ran_out_of_time_says_the_cause():
    # t3-c14: the request is no plain question to name, so the bare sentence.
    assert _compose(RECIPES_SAID, _search()) == _untold()["es"]["bare"]


def test_a_the_asked_question_is_named_with_the_cause():
    said = "cuantos gramos es una taza de harina"
    final = _compose(said, _search(query=said))
    assert final == _untold()["es"]["asked"].format(clause="cuántos gramos es una taza de harina")


def test_a_in_english_too():
    said = "who won the 2010 world cup?"
    final = _compose(said, _search(query="2010 world cup winner"))
    assert final.startswith("I ran out of time before I could tell you"), final


def test_a_the_sentence_is_data_and_shows_no_search():
    for language in ("es", "en"):
        for template in _untold()[language].values():
            assert not search_report._search_report_shows_the_search(template.format(clause="x"), {"seen": {}}, "")
            assert "busqu" not in template.casefold() and "looked" not in template.casefold()


def test_a_drafts_that_all_died_are_still_the_not_found():
    # Three drafts refused (a time the facts do not hold, twice empty): the pages answered nothing, the owner's rule.
    final = _compose(RECIPES_SAID, _search(), ["Son las 07:45.", "", ""])
    assert final not in _untold()["es"].values()


def test_a_a_search_without_results_never_takes_the_time_sentence():
    with pytest.raises(TimeoutError):
        _compose(RECIPES_SAID, _search(results=[]))


def test_a_a_failed_search_never_takes_the_time_sentence():
    try:
        final = _compose(RECIPES_SAID, _search(ok=False), intent="error")
    except TimeoutError:
        final = ""
    assert final not in _untold()["es"].values()


@pytest.mark.parametrize(
    "error",
    [ConnectionResetError(10054, "conexión reiniciada"), ConnectionError("llama-server cerró la conexión")],
)
@pytest.mark.parametrize("drafts", [[], ["Son las 07:45."]])
def test_a_a_dropped_local_connection_is_not_told_as_the_time_that_ran_out(error, drafts):
    # Revisión r19b: last_resort is reached from any OSError, a dropped local connection too (post_chat_completion
    # with max_attempts=1). Nothing ran out of time there, so the time sentence is not said; the turn keeps its way.
    try:
        final = _OutOfTime(drafts, error).compose_user_message(
            RECIPES_SAID, "status", {"situation": json.dumps(_search(), ensure_ascii=False)}, said=RECIPES_SAID,
        )
    except OSError as raised:
        assert raised is error
        final = ""
    assert final not in _untold()["es"].values()
    assert "tiempo" not in final


def test_a_a_timeout_urllib_wraps_is_still_the_time_that_ran_out():
    import socket
    import urllib.error

    wrapped = urllib.error.URLError(socket.timeout("timed out"))
    final = _OutOfTime([], wrapped).compose_user_message(
        RECIPES_SAID, "status", {"situation": json.dumps(_search(), ensure_ascii=False)}, said=RECIPES_SAID,
    )
    assert final == _untold()["es"]["bare"]
