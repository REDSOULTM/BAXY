"""v3 point 0 (arreglo 4): a computer-use mission opens its application behind the person's window; only a request
that asks to see it in front sets app.open «foreground». A bare «adelante» (go on) is no request for the front."""

from __future__ import annotations

import pytest

from baxy_mind import computer_use
from baxy_mind.semantic.windows import asks_for_the_front


@pytest.mark.parametrize(
    "text",
    [
        "abrí spotify y traelo al frente",
        "abre paint y ponelo en primer plano",
        "bring Paint to the front and draw a line",
        "enfocá discord y escribile hola a Valeria",
        "show me the calculator in the foreground",
    ],
)
def test_a_request_for_the_front_is_read(text: str) -> None:
    assert asks_for_the_front(text)


@pytest.mark.parametrize(
    "text",
    [
        "abrí spotify y poné la canción",
        "dale, seguí adelante con eso",
        "abre paint y dibuja un círculo",
        "abrí la calculadora y calculá 5 por 3",
        "open notepad and go forward to the next page",
        "abrí la calculadora y cambiá a modo científico",
        "open Edge and switch to the second tab",
        "",
    ],
)
def test_working_in_an_application_is_no_request_for_the_front(text: str) -> None:
    assert not asks_for_the_front(text)


def _open_step(objective: str) -> dict:
    view = {"window": {"title": "Visual Studio Code", "process": "Code"}, "controls": []}
    return computer_use.decide_step(
        None,
        objective=objective,
        goal="ir a biblioteca",
        application="Steam",
        success_check=None,
        view=view,
        history=[],
        budget_left=8,
        application_names=["Steam"],
    )


def test_the_missions_opening_stays_behind_the_persons_window() -> None:
    step = _open_step("abrí steam y andá a la biblioteca")

    assert step["operation"] == "app.open"
    assert "foreground" not in step["arguments"]


def test_the_missions_opening_comes_to_the_front_when_asked() -> None:
    step = _open_step("abrí steam, traelo al frente y andá a la biblioteca")

    assert step["operation"] == "app.open"
    assert step["arguments"].get("foreground") is True
