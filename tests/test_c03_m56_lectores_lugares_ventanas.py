"""M56 (2026-09-28, review of the official-window run v3c-final): three general repairs, each on the real messages and
payloads of that run (%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3c-final/: RUN.jsonl, turn-audit.jsonl,
compose-audit.jsonl, shell-trace.jsonl and the profile's journal).

1. F-s017 «what's the latest song from NeYo» was looked up as «ranking latest song» (trot music from Korea), and
   F-w14-t1 «escribeme un query de sql…» was sent to the web by the public-lookup guard (request 1072, stage
   ``public_lookup``). A ranking is asked only by the superlative of an attribute the world is ordered by; code asked
   for is written, never looked up.
2. F-p06-t2 «¿Podrías buscar aparcamiento en la Plaza de las Salesas en Madrid?» told five car parks of Cartagena as
   Madrid's: Nominatim found nothing for «la Plaza de las Salesas, Madrid» (the sentence's article) and the square alone
   only in Cartagena (provider tests in ExternalAdaptersTests). The mind lists and lets be told only the places inside
   the city the query named.
3. F-w06-t1/t2 (Word installed, no window) and F-w08-t1 (Slack not installed on the test PC): the plan stopped at the
   first failed resolve and the reply guessed which window was missing, or no plan was made at all and «the plan is
   incomplete» reached the person. A window absent from the catalog keeps its name in the plan (the PC says it is not
   there); the App steps over a failed read to place the other window (PlannerAppBoundaryTests); the planning codes
   are facts, not jargon.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent
from baxy_mind.deterministic_finals import _deterministic_final
from baxy_mind.payload_fact_checks import _payload_fact_defect
from baxy_mind.compose_situation import _CAUSE_FACT
from baxy_mind.compose_situation import _cause_in_prose
from baxy_mind.planner import validate_json_schema_instance
from baxy_mind.semantic import knowledge
from baxy_mind.semantic.web import not_a_public_lookup, place_containers
from baxy_mind import argument_grounding
from baxy_mind import plan_shape
from baxy_mind.semantic import arguments as semantic_arguments

# ------------------------------------------------------------------ 1. rankings and code

F_S017 = "what's the latest song from NeYo"
F_S017_RESTATED = "What's the latest song from Ne-Yo?"  # turn-audit request 112
F_W14_T1 = "baxy escribeme un query de sql q me saque los users activos del ultimo mes"
F_W14_T2 = "ahora q salgan ordenados por fecha, los mas recientes primero"


@pytest.mark.parametrize(
    "text",
    [
        F_S017,
        F_S017_RESTATED,
        "what are the newest phones",
        "which is the most recent album of Shakira",
        "cuáles son las películas más recientes de Nolan",
        "dime las canciones más nuevas de Bad Bunny",
        "cuáles son los últimos discos de Soda Stereo",
        "what are the best movies of 2020",
        "cuáles son las series más populares",
        F_W14_T1,
        F_W14_T2,
        "hazme un script en python que liste los archivos más grandes de la carpeta",
    ],
)
def test_a_newest_thing_an_opinion_or_code_is_no_ranking(text: str) -> None:
    assert knowledge.reference_lookup(text) is None


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("cuáles son las ciudades más pobladas del mundo", "ranking ciudades pobladas del mundo"),
        ("what are the most populous countries", "ranking most populous countries"),
        ("dime los 5 ríos más largos de América", "ranking rios largos de america"),
        ("cuáles son los edificios más altos del mundo", "ranking edificios altos del mundo"),
        ("which are the brightest stars in the sky", "ranking brightest stars in the sky"),
    ],
)
def test_a_superlative_of_an_orderable_attribute_is_a_ranking(text: str, query: str) -> None:
    lookup = knowledge.reference_lookup(text)
    assert lookup is not None and (lookup.kind, lookup.query) == ("ranking", query)


def test_the_latest_song_and_the_sql_query_keep_the_person_s_words() -> None:
    # The arguments step of the decided web.search (request 112) and the decider's talk conversion read this.
    assert argument_grounding._reference_lookup(F_S017_RESTATED, [{"role": "user", "content": F_S017}]) is None
    assert argument_grounding._reference_lookup(F_W14_T1, []) is None


def test_code_asked_for_is_never_a_public_lookup() -> None:
    assert not_a_public_lookup(F_W14_T1)
    assert not_a_public_lookup("write me a regex that matches emails")
    # Public information stays a lookup.
    assert not not_a_public_lookup("cuánto está el dólar hoy en chile")
    assert not not_a_public_lookup("qué películas salen esta semana")


# ------------------------------------------------------------------ 2. places inside the named city

F_P06_T2 = "¿Podrías buscar aparcamiento en la Plaza de las Salesas en Madrid?"
# v3c-final RUN.jsonl t117: what OpenStreetMap returned around the Plaza de las Salesas of Cartagena.
F_P06_T2_PAYLOAD = {
    "operation": "web.search",
    "seen": {
        "query": "aparcamiento en la Plaza de las Salesas en Madrid",
        "count": 5,
        "results": [
            {"title": "parking", "url": "https://www.openstreetmap.org/way/256163049",
             "snippet": "Calle Jorge Juan, Ensanche, Cartagena Casco, Cartagena, Campo de Cartagena y Mar Menor, "
                        "Región de Murcia, 30204, España"},
            {"title": "parking", "url": "https://www.openstreetmap.org/way/305418869",
             "snippet": "Plaza Pedro Ros, Ensanche, Cartagena Casco, Cartagena, Campo de Cartagena y Mar Menor, "
                        "Región de Murcia, 30203, España"},
            {"title": "parking", "url": "https://www.openstreetmap.org/way/346931611",
             "snippet": "Avenida de Murcia, Ensanche, Cartagena Casco, Cartagena, Campo de Cartagena y Mar Menor, "
                        "Región de Murcia, 30203, España"},
            {"title": "parking", "url": "https://www.openstreetmap.org/way/305417786",
             "snippet": "Plaza de las Descalzas, Barriada Virgen de la Caridad, Cartagena Casco, Cartagena, Campo de "
                        "Cartagena y Mar Menor, Región de Murcia, 30203, España"},
            {"title": "Plaza Atenea", "url": "https://www.openstreetmap.org/way/56061964",
             "snippet": "Plaza Atenea, Ciudad Jardín, San Antonio Abad, Cartagena, Campo de Cartagena y Mar Menor, "
                        "Región de Murcia, 30204, España"},
        ],
        "authority": "openstreetmap_nominatim",
    },
}
F_P06_T2_SITUATION = {
    "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
    "observed": F_P06_T2_PAYLOAD["seen"],
}


@pytest.mark.parametrize(
    ("query", "containers"),
    [
        ("aparcamiento en la Plaza de las Salesas en Madrid", (frozenset({"madrid"}),)),
        ("aparcamiento en la calle Génova en Madrid", (frozenset({"madrid"}),)),
        ("Encuentrame aparcamiento cerca de La Puntilla, El Puerto.", (frozenset({"puerto"}),)),
        ("aparcamiento en Plaza del Polvorista", ()),
        ("Show me gas stations in Buford.", ()),
        ("comida para llevar cerca Curico", ()),
    ],
)
def test_the_city_a_place_search_names_is_read_as_the_provider_reads_it(query: str, containers: tuple) -> None:
    assert place_containers(query) == containers


def test_p06_t2_places_of_another_city_are_neither_listed_nor_told() -> None:
    # The fixed listing does not tell the car parks of Cartagena as the answer.
    assert _deterministic_final(F_P06_T2_SITUATION, F_P06_T2_PAYLOAD, F_P06_T2, "es") == ""
    # The published v3c reply and any other that states them are vetoed; «not found» is what fits.
    published = "Encontré: Calle Jorge Juan, Plaza Pedro Ros y Avenida de Murcia."
    assert _payload_fact_defect(published, F_P06_T2_PAYLOAD, F_P06_T2) == "search_report_off_subject"
    assert _payload_fact_defect("No encontré aparcamiento en la Plaza de las Salesas.", F_P06_T2_PAYLOAD, F_P06_T2) == ""


def test_places_inside_the_named_city_are_still_the_answer() -> None:
    inside = {
        "operation": "web.search",
        "seen": dict(F_P06_T2_PAYLOAD["seen"], results=[
            {"title": "parking", "url": "https://www.openstreetmap.org/way/1",
             "snippet": "Calle de Campoamor, Chueca, Justicia, Centro, Madrid, Comunidad de Madrid, 28004, España"},
            F_P06_T2_PAYLOAD["seen"]["results"][0],
        ]),
    }
    situation = dict(F_P06_T2_SITUATION, observed=inside["seen"])
    told = _deterministic_final(situation, inside, F_P06_T2, "es")
    assert told == "Encontré: Calle de Campoamor."
    assert _payload_fact_defect(told, inside, F_P06_T2) == ""


# ------------------------------------------------------------------ 3. two windows, one absent

# The applications of the test PC: Word and Chrome installed, Slack not.
INSTALLED = ("Word", "Google Chrome", "Excel", "Spotify")
RESOLVE_SCHEMA = {
    "type": "object",
    "properties": {
        "applicationName": {"type": "string", "maxLength": 256},
        "byTitle": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "offset": {"type": "integer", "minimum": 0},
        "process": {"type": "string", "maxLength": 260},
    },
    "required": [],
    "additionalProperties": False,
}
F_W08_RESTATED = "Snap the Chrome window to the left half and the Slack window to the right half of the screen."
F_W08_T1 = (
    "Morning! I've got a standup in twenty minutes and my screen is a total mess. Can you put Chrome on the left half "
    "and Slack on the right so I can see the board and the chat at the same time?"
)


def test_w08_a_window_the_pc_does_not_have_keeps_its_name_in_the_plan() -> None:
    # The pairs reader alone still authorizes only catalog windows (M55's contract) …
    assert effect_intent.application_snap_pairs(F_W08_RESTATED, INSTALLED) is None
    # … and the plan of the placing the decider chose keeps the name the person gave the absent one.
    pairs = effect_intent.application_snap_pairs(F_W08_RESTATED, INSTALLED, absent=True)
    assert pairs is not None
    assert [(name, side) for name, side, _ in pairs] == [("Google Chrome", "left"), ("Slack", "right")]
    split = mind.window_snap_plan_split(("window.snap",), (F_W08_RESTATED,), F_W08_RESTATED, INSTALLED)
    assert split is not None and split[0] == ("window.snap", "window.snap")
    skeleton = plan_shape._explicit_plan_skeleton(*split)
    grounded = []
    for step in skeleton["steps"]:
        if step["operation"] == "window.resolve":
            arguments = argument_grounding._ground_explicit_arguments("window.resolve", step["purpose"], RESOLVE_SCHEMA, INSTALLED)
            assert validate_json_schema_instance(arguments, RESOLVE_SCHEMA)
            assert argument_grounding._normalize_grounded_operation_arguments("window.resolve", arguments, F_W08_RESTATED) == arguments
        else:
            arguments = semantic_arguments.window_snap_side_for_step(F_W08_RESTATED, step["purpose"], INSTALLED)
        grounded.append((step["operation"], arguments))
    assert grounded == [
        ("window.resolve", {"applicationName": "Google Chrome"}),
        ("window.snap", {"side": "left"}),
        ("window.resolve", {"applicationName": "Slack"}),
        ("window.snap", {"side": "right"}),
    ]


def test_w08_the_person_s_own_sentence_splits_too() -> None:
    pairs = effect_intent.application_snap_pairs(F_W08_T1.split("Can you ", 1)[1], INSTALLED, absent=True)
    assert pairs is not None and [(name, side) for name, side, _ in pairs] == [
        ("Google Chrome", "left"), ("Slack", "right"),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "pon eso a la izquierda y chrome a la derecha",
        "pon la otra ventana a la izquierda y chrome a la derecha",
        "pon esta ventana a la izquierda y chrome a la derecha",
        "pon chrome a la izquierda y chrome a la derecha",
        "pon el word a la izquierda y abre spotify",
    ],
)
def test_an_absent_name_is_a_name_never_a_pointer(text: str) -> None:
    assert effect_intent.application_snap_pairs(text, INSTALLED, absent=True) is None


def test_w06_both_windows_installed_split_as_before() -> None:
    restated = "Coloca la ventana de Word en la mitad izquierda y la de Chrome en la mitad derecha."
    split = mind.window_snap_plan_split(("window.snap",), (restated,), restated, INSTALLED)
    assert split == (
        ("window.snap", "window.snap"),
        ("coloca la ventana de word en la mitad izquierda", "coloca la de chrome en la mitad derecha"),
    )


@pytest.mark.parametrize(
    "code", ["plan_incomplete", "plan_unverified", "step_data_missing", "step_unlinkable", "step_unverified",
             "continue_unsafe", "turn_budget_exhausted"],
)
def test_planning_codes_reach_the_reply_as_facts_not_jargon(code: str) -> None:
    fact = _cause_in_prose(code, "en")
    assert fact == _CAUSE_FACT[code]
    assert "plan" not in fact and "step" not in fact and "_" not in fact
