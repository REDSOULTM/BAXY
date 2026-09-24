"""Uso real tanda 4d (2026-09-24): «show me las aplicaciones» died in ⚠ retry_exhausted.

Edge titles its window «<página> - <perfil>: Microsoft​ Edge», a zero-width space inside the browser's name. The
narrator wrote the page with the browser in front and the identity check, which wants each observed title, refused
every draft. The visible title is the page, without invisible characters; the browser is the window's process.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic import levels


def _situation(*titles: tuple[str, str]) -> dict:
    windows = [
        {"windowId": f"win_{index}", "processName": process, "title": title, "state": "normal", "foreground": False}
        for index, (process, title) in enumerate(titles)
    ]
    observed = {"version": 1, "windows": windows, "count": len(windows), "offset": 0, "observedCount": len(windows),
                "complete": True, "totalCount": len(windows), "hasMore": False}
    return {"kind": "operation", "operation": "window.resolve", "polarity": "success", "verified": True,
            "succeeded": True, "observed": observed}


@pytest.mark.parametrize(
    ("process", "title", "shown"),
    [
        ("msedge", "Receta de lentejas - Personal: Microsoft​ Edge", "Receta de lentejas"),
        ("msedge", "Weather radar - Work: Microsoft Edge", "Weather radar"),
        ("chrome", "Horario del metro - Google Chrome", "Horario del metro"),
        ("firefox", "Mapa de Chile — Mozilla Firefox", "Mapa de Chile"),
        # Not a browser suffix: the whole title stays.
        ("notepad", "notas - Bloc de notas", "notas - Bloc de notas"),
        ("msedge", "Restaurar páginas", "Restaurar páginas"),
        # A title that is only the browser keeps it.
        ("msedge", "Microsoft​ Edge", "Microsoft Edge"),
    ],
)
def test_the_narrator_sees_the_page_the_window_shows(process, title, shown):
    payload = llm._compose_situation_payload(_situation((process, title)), "es", "muéstrame las ventanas")
    assert [window["title"] for window in payload["seen"]["windows"]] == [shown]
    assert "​" not in json.dumps(payload, ensure_ascii=False)


def test_a_draft_naming_the_page_is_not_refused_for_the_browser_suffix():
    situation = _situation(
        ("Taskmgr", "Administrador de tareas"),
        ("msedge", "Receta de lentejas - Personal: Microsoft​ Edge"),
    )
    user_text = "show me las aplicaciones"
    payload = llm._compose_situation_payload(situation, "es", user_text)
    draft = "Tienes abiertas estas ventanas:\n- Administrador de tareas\n- Receta de lentejas (Microsoft Edge)"
    assert llm._payload_fact_defect(draft, payload, user_text) == ""
    # A window left out of the answer is still refused.
    assert llm._payload_fact_defect("Tienes abierto el Administrador de tareas.", payload, user_text) != ""


# «Incrementa el brightness al level 8» (brightness at 100) was stepped up by 8 and stayed at 100: a level said
# after «a/al/to» names where the level ends, like «al 8»; a counted step («un nivel») still has no amount.
@pytest.mark.parametrize(
    ("text", "setting", "target"),
    [
        ("Incrementa el brillo al nivel 8", "brightness", 8),
        ("raise the brightness to level 8", "brightness", 8),
        ("pon el volumen a nivel 30", "volume", 30),
        ("set volume to level 5", "volume", 5),
        ("turn the volume up to level 40", "volume", 40),
        ("baja la luminosidad al nivel veinte", "brightness", 20),
    ],
)
def test_a_level_named_after_to_is_the_target(text, setting, target):
    level = levels.read(text)
    assert level is not None and level.setting == setting
    assert level.target == target and level.amount is None


@pytest.mark.parametrize("text", ["sube el brillo un nivel", "baja el volumen dos niveles", "turn it up a level"])
def test_a_counted_step_stays_without_amount(text):
    level = levels.read(text)
    assert level is not None and level.target is None and level.amount is None
