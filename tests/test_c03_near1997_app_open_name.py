"""NEAR1997 (H0227 «abre Steel.»): an app.open final names the application the receipt
opened. The receipt carries the catalog name as `appId`; «La app ya estaba abierta.» left the
person who said «Steel» without knowing what BAXY understood."""

from __future__ import annotations

import pytest

from baxy_mind.llm import _app_open_observed_name, compose_visible_defect

SITUATION = {
    "kind": "operation",
    "operation": "app.open",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
    "observed": {"appId": "Steam", "alreadyRunning": True, "processId": 21132},
}
FACTS = {"situation": SITUATION}


def test_app_open_receipt_names_the_app_by_its_id() -> None:
    assert _app_open_observed_name(SITUATION) == "Steam"
    assert _app_open_observed_name({"observed": {"app": "Calculadora"}}) == "Calculadora"
    assert _app_open_observed_name({"observed": {"processId": 1}}) is None


def test_store_app_receipts_name_the_app_by_display_name_not_catalog_id() -> None:
    # THEN2001 H0097: «windows.notepad» is the catalog id; «Bloc de notas» is what the person calls it.
    observed = {"appId": "windows.notepad", "displayName": "Bloc de notas", "alreadyRunning": False}
    assert _app_open_observed_name({"observed": observed}) == "Bloc de notas"
    assert _app_open_observed_name({"observed": {"appId": "windows.notepad"}}) is None
    facts = {"situation": {**SITUATION, "observed": observed}}
    assert compose_visible_defect("Abrí el Bloc de notas.", "operation", "abrí el bloc de notas", facts) != "missing_name"
    assert compose_visible_defect("Ya está abierto.", "operation", "abrí el bloc de notas", facts) == "missing_name"


@pytest.mark.parametrize("reply", ["La app ya estaba abierta.", "Ya estaba abierta."])
def test_app_open_final_without_the_app_name_is_rejected(reply: str) -> None:
    assert compose_visible_defect(reply, "operation", "abre Steel.", FACTS) == "missing_name"


@pytest.mark.parametrize(
    "reply",
    ["Steam ya estaba abierto.", "Dale, ya está abierto el Steam.", "Opened Steam. It was already running before."],
)
def test_app_open_final_naming_the_app_passes_the_name_check(reply: str) -> None:
    assert compose_visible_defect(reply, "operation", "abre Steel.", FACTS) != "missing_name"


def test_app_open_final_may_name_a_multiword_app_by_one_of_its_words() -> None:
    facts = {"situation": {**SITUATION, "observed": {"appId": "Google Chrome", "alreadyRunning": False}}}
    assert compose_visible_defect("Abrí Chrome.", "operation", "abrí chrome", facts) != "missing_name"
    assert compose_visible_defect("Ya está abierto.", "operation", "abrí chrome", facts) == "missing_name"


def test_opening_a_closed_app_in_the_past_tense_is_its_state() -> None:
    # THEN2003: «Abrí el Bloc de notas.» carries no «abierto» but says the app was opened now.
    observed = {"appId": "windows.notepad", "displayName": "Bloc de notas", "alreadyRunning": False}
    facts = {"situation": {**SITUATION, "observed": observed}}
    assert compose_visible_defect("Abrí el Bloc de notas.", "operation", "abrí el bloc de notas", facts) == ""
    assert compose_visible_defect("El Bloc de notas.", "operation", "abrí el bloc de notas", facts) == "missing_state"


def test_the_english_name_of_a_spanish_store_app_counts() -> None:
    # THEN2007 «open notepad»: «I opened Notepad.» names «Bloc de notas».
    observed = {"appId": "windows.notepad", "displayName": "Bloc de notas", "alreadyRunning": False}
    facts = {"situation": {**SITUATION, "observed": observed}}
    assert compose_visible_defect("I opened Notepad.", "operation", "open notepad", facts) == ""
