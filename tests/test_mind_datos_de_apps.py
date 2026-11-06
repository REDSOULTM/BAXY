"""G7 (uso real 2026-11-03): asked its own user name in an open app, the model answered in words with nothing read
(«mi nombre en …es BAXY»), or said it could not read it. In the isolated turn with the real model (encargo 29, 5 seeds,
7 phrases) the fact inside input_visible_controls' «Use when:», with an example, made it look at the window in 17 of 35
turns (0 of 35 before); the same fact as a sentence at the end of the description, 12 of 35."""
from pathlib import Path

from test_mind_final import _mind

CATALOG = {"capabilities": [{"name": "input.visible.controls", "description": "Mira una ventana.", "risk": "read_only",
                             "argumentsSchema": {"type": "object", "properties": {}}}]}


def _use_when(tmp_path: Path) -> str:
    mind, _ = _mind(tmp_path, [])
    mind.configure(CATALOG)
    description = next(t["function"]["description"] for t in mind.tools
                       if t["function"]["name"] == "input_visible_controls")
    return description[description.index("Use when:"):description.index("Do not use when:")]


def test_what_an_app_shows_of_the_person_is_read_from_its_window(tmp_path: Path) -> None:
    use_when = _use_when(tmp_path)
    assert "what it shows of the person (their user name, their status, who is online)" in use_when
    assert "BAXY has no account of its own in their apps" in use_when


def test_its_examples_read_the_persons_own_name_in_an_app_with_its_text(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [])
    mind.configure(CATALOG)
    description = next(t["function"]["description"] for t in mind.tools
                       if t["function"]["name"] == "input_visible_controls")
    examples = description[description.index("Examples:"):]
    assert "«¿con qué nombre salgo en Slack?» (look at Slack with includeText)" in examples
