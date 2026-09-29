"""M64: the decider's restatement travels only with what was said, the decider's argument fields are audited, and a
search nobody could report names what was looked up.

Pinned on the real restatements of the official-window runs v3d/v3e2/v3f (final and DEV-D) with the conversation
the decider read (tests/data/c03_m64_fidelity_situations.json, from their turn-audit.jsonl and RUN.jsonl):

- v3f-final F-w01-t4 «¿y cuánto sale más o menos ese pisco en el líder? el mistral de 35» → «…Mistral de 350 ml…»:
  «350 ml» nobody said; v3e2-final restated the same turn «…Mistral de 35…», which stays.
- F-s054 «Estará storming mañana» → «…mañana en Santiago?»; F-w05-t3 «…un mes antes» → «…para el 1 de octubre…».
- What stays: «ñuñoa» → «Ñuñoa», «a la mitad» → «al 50», «NeYo» → «Ne-Yo», «control» → «Ctrl», «sonido del
  PC» for audio.mute, «on Netflix» for streaming.play.named, «media hora antes» of «las 10» → «09:30».
- v3f-final F-w12-t4 «¿Cuánto está el dólar blue hoy?»: three drafts fell and «No lo encontré.» left F-w12-t5 «Anotame
  ese valor» without its topic.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import LlmRuntime
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision, catalog_line, faithful_request
from baxy_mind.semantic.web import searched_clause

RECORDED = json.loads(
    (Path(__file__).parent / "data" / "c03_m64_fidelity_situations.json").read_text(encoding="utf-8")
)
REWRITES = {(row["run"], row["id"]): row for row in RECORDED["rewrites"]}
NOW = datetime(2026, 9, 29, 12, 0)


def _fidelity(run: str, case: str):  # noqa: ANN202
    row = REWRITES[(run, case)]
    return faithful_request(
        row["request"],
        row["text"],
        [turn["content"] for turn in row["history"]],
        world=[catalog_line(operation, "") for operation in row["ops"] or ()],
        now=NOW,
    )


# ------------------------------------------------------------------ what the restatement brought is not the objective

@pytest.mark.parametrize(
    ("run", "case", "kind", "objective", "introduced"),
    [
        ("v3f-final", "F-w01-t4", "person", "¿y cuánto sale más o menos ese pisco en el líder? el mistral de 35",
         ("350 ml",)),
        ("v3f-final", "F-s054", "trimmed", "¿Está lloviendo mañana?", ("Santiago",)),
        ("v3f-final", "F-w05-t3", "trimmed", "Crea un recordatorio para renovar el contrato del piso.",
         ("1 de octubre",)),
        ("v3f-devD", "D-w03-t4", "trimmed", "¿Cuánto vale el dólar hoy?", ("Argentina",)),
        ("v3f-devD", "D-w08-t2", "trimmed", "¿Cuándo juega el siguiente partido?", ("Atlético", "Nacional")),
        ("v3f-devD", "D-w02-t3", "person", "ponme una alarma media hora antes de eso", ("a las 10:30",)),
        ("v3e2-devD", "D-w02-t3", "person", "ponme una alarma media hora antes de eso", ("a las 9:14",)),
    ],
)
def test_what_nobody_said_never_travels_as_the_objective(
    run: str, case: str, kind: str, objective: str, introduced: tuple[str, ...],
) -> None:
    fidelity = _fidelity(run, case)

    assert (fidelity.kind, fidelity.request, fidelity.introduced) == (kind, objective, introduced)


@pytest.mark.parametrize(
    ("run", "case"),
    [
        ("v3e2-final", "F-w01-t4"),  # «el mistral de 35» kept as «Mistral de 35»
        ("v3f-final", "F-w01-t6"),  # «en ñuñoa» → «Ñuñoa»
        ("v3f-final", "F-w03-t2"),  # «a la mitad» → «al 50»
        ("v3f-final", "F-s017"),  # «NeYo» → «Ne-Yo»
        ("v3f-final", "F-s038"),  # «control» → «Ctrl»
        ("v3f-final", "F-s003"),  # «sonido del PC», audio.mute's own words
        ("v3f-devD", "D-p22-t2"),  # «on Netflix», streaming.play.named's own service
        ("v3d-devD-np2", "D-w02-t3"),  # «media hora antes» of «las 10 de la mañana» → «09:30»
        ("v3f-devD", "D-w04-t4"),  # «a las 6 en punto» → «a las 6:00»
    ],
)
def test_a_restatement_that_joins_what_was_said_is_kept(run: str, case: str) -> None:
    fidelity = _fidelity(run, case)

    assert (fidelity.kind, fidelity.request) == ("kept", REWRITES[(run, case)]["request"])


def test_the_operations_own_words_count_only_for_the_operation_that_names_them() -> None:
    row = REWRITES[("v3f-devD", "D-p22-t2")]

    alone = faithful_request(row["request"], row["text"], [turn["content"] for turn in row["history"]], now=NOW)

    assert alone.introduced == ("Netflix",)


@pytest.mark.parametrize(
    ("text", "restated", "kept"),
    [
        ("súbele a treinta y cinco", "Sube el volumen a 35.", True),
        ("súbele a treinta y cinco", "Sube el volumen a 53.", False),
        ("ponle cien mil doscientas veintitrés", "Escribe 100223.", True),
        ("ponme una alarma en 20 minutos", "Pon una alarma a las 12:20.", True),
        ("ponme una alarma en 20 minutos", "Pon una alarma a las 12:40.", False),
        ("recuérdamelo mañana", "Crea un recordatorio para el 30 de septiembre.", True),
        ("recuérdamelo mañana", "Crea un recordatorio para el 2 de octubre.", False),
        ("¿cuánto cuestan 5.000 pesos en dólares?", "¿Cuántos dólares son 5000 pesos?", True),
        ("¿cuánto vale el pisco de 35?", "¿Cuánto vale el pisco de 35 grados?", False),
        ("¿cuánto cuestan 2 litros de leche?", "¿Cuánto cuestan 2 l de leche?", True),
    ],
)
def test_numbers_units_clocks_and_dates_are_said_in_any_form(text: str, restated: str, kept: bool) -> None:
    assert (faithful_request(restated, text, [], now=NOW).kind == "kept") is kept


def test_a_complement_is_taken_out_only_when_the_message_keeps_its_own_numbers() -> None:
    # «de 350 ml» taken out would leave «Mistral» without the «35» the person said: the message itself travels.
    fidelity = faithful_request(
        "¿Cuánto sale el pisco Mistral de 350 ml en el Líder?", "¿y el mistral de 35 en el líder?", [], now=NOW,
    )

    assert fidelity.kind == "person"


def test_what_is_not_a_complement_is_never_cut_out() -> None:
    fidelity = faithful_request("Abre Spotify.", "ábreme eso", ["¿qué hora es?", "Son las 12:00."], now=NOW)

    assert (fidelity.kind, fidelity.request) == ("person", "ábreme eso")


# ------------------------------------------------------------------ through the turn: objective and audit

OPERATIONS = ("web.search", "notification.schedule", "weather.current")


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            },
        },
    }


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        return self.decision

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"


def _turn(row: dict, decision: ContextDecision, monkeypatch: pytest.MonkeyPatch) -> tuple[dict, list[dict]]:
    audits: list[dict] = []
    monkeypatch.setattr(sidecar, "_append_turn_audit", audits.append)
    tools = {name: _tool(name) for name in OPERATIONS}
    result = sidecar._prepare_turn_result(
        {"id": "m64", "text": row["text"], "history": [*row["history"], {"role": "user", "content": row["text"]}]},
        llm=_Decider(decision),
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )
    return result, [record for record in audits if record.get("phase") == "final"]


def test_the_person_s_words_are_the_objective_and_the_audit_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    row = REWRITES[("v3f-final", "F-w01-t4")]
    decision = ContextDecision(
        row["request"], "action", ("web.search",), "", (("query", "precio pisco Mistral 350 ml Líder"),),
    )

    result, audits = _turn(row, decision, monkeypatch)

    assert result["objective"] == row["text"]
    raw = audits[-1]["raw_decision"]
    assert raw["argument_fields"] == ["query"]
    assert raw["decider_request"] == row["request"]
    assert raw["fidelity"] == {"kind": "person", "introduced": ["350 ml"]}
    assert "precio" not in json.dumps(raw["argument_fields"])


def test_a_faithful_restatement_is_audited_with_its_fields_and_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    row = REWRITES[("v3e2-final", "F-w01-t4")]
    decision = ContextDecision(row["request"], "action", ("web.search",), "", (("query", "pisco Mistral 35 Líder"),))

    result, audits = _turn(row, decision, monkeypatch)

    assert result["objective"] == row["request"]
    raw = audits[-1]["raw_decision"]
    assert raw["argument_fields"] == ["query"]
    assert "fidelity" not in raw and "decider_request" not in raw


# ------------------------------------------------------------------ the not-found names what was looked up

@pytest.mark.parametrize(
    ("text", "language", "clause"),
    [
        ("¿Cuánto está el dólar blue hoy?", "es", ("cuánto está el dólar blue hoy", True)),
        ("¿Cuál es el importe de la factura de este mes?", "es", ("cuál es el importe de la factura de este mes", True)),
        ("¿Quién trabaja en Chuck E. Cheese?", "es", ("quién trabaja en Chuck E. Cheese", True)),
        ("Cuántos años tiene Luis Miguel", "es", ("cuántos años tiene Luis Miguel", True)),
        ("¿Cuánto me sale cargar 40 litros de nafta Super en Córdoba?", "es",
         ("cuánto te sale cargar 40 litros de nafta Super en Córdoba", True)),
        ("¿Va a llover mañana en Ñuñoa?", "es", ("si va a llover mañana en Ñuñoa", True)),
        ("Busca en internet el horario del Líder de Ñuñoa", "es", ("el horario del Líder de Ñuñoa", False)),
        ("oye che, ¿qué dijo la crítica de Oppenheimer?", "es", ("qué dijo la crítica de Oppenheimer", True)),
        ("any new status updates", "en", ("any new status updates", False)),
        ("What's the latest song from Ne-Yo?", "en", ("what the latest song from Ne-Yo is", True)),
        ("how much is a Big Mac in Chile", "en", ("how much a Big Mac in Chile is", True)),
        ("who won the Champions League", "en", ("who won the Champions League", True)),
        # Not one plain lookup in BAXY's words: the plain not-found stays.
        ("¿y cuánto sale más o menos ese pisco en el líder? el mistral de 35", "es", None),
        ("precio pisco mistral 35 lider", "es", None),
        ("taquerías cerca que tengan servicio a domicilio", "es", None),
        ("Get train schedules to Manchester on Wednesday.", "en", None),
        ("Get the train schedules to Manchester on Wednesday.", "en",
         ("the train schedules to Manchester on Wednesday", False)),
        ("¿Qué me recomiendas?", "es", None),
        ("¿Qué tengo que llevar?", "es", None),
        ("Does Bob live in France?", "en", None),
        ("when does the new Batman come out", "en", None),
        ("¿Cuánto está el dólar blue hoy?", "en", None),
    ],
)
def test_what_was_looked_up_is_said_in_the_persons_words(
    text: str, language: str, clause: tuple[str, bool] | None,
) -> None:
    assert searched_clause(text, language) == clause


class _Drafts(LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats)."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _compose(user_text: str, situation: dict, case: str = "F-w12-t4") -> str:
    recorded = RECORDED[case]
    writer = _Drafts([draft["draft"] for draft in recorded["drafts"]])
    return writer.compose_user_message(
        user_text, recorded["intent"], {"situation": json.dumps(situation, ensure_ascii=False)},
    )


def test_f_w12_t4_the_three_fallen_drafts_end_naming_the_dollar() -> None:
    recorded = RECORDED["F-w12-t4"]

    published = _compose(recorded["userText"], copy.deepcopy(recorded["situation"]))

    assert recorded["published"] == "No lo encontré."
    assert published == "No encontré cuánto está el dólar blue hoy."


def test_a_request_that_is_not_one_lookup_names_the_query_sent_or_nothing() -> None:
    recorded = RECORDED["F-w12-t4"]
    situation = copy.deepcopy(recorded["situation"])

    assert _compose("¿y el blue? dale", situation) == "No encontré cuánto está el dólar blue hoy."
    situation["observed"]["query"] = "dolar blue hoy cotizacion"
    assert _compose("¿y el blue? dale", situation) == "No lo encontré."


def test_f_s012_the_english_not_found_names_what_the_query_asked_for() -> None:
    recorded = RECORDED["F-s012"]

    published = _compose(recorded["userText"], copy.deepcopy(recorded["situation"]), "F-s012")

    assert recorded["published"] == "I couldn't find it."
    assert published == "I couldn't find any new status updates."
