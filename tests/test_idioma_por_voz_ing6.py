"""ING6: what the change of language by voice costs the Spanish prefix. ing5-voz gave baxy_settings_set a clause, two
examples and a sentence in «value»: +69 tokens in every Spanish prefix. Measured on the PC's GPU (INFORME_ING6 §1), with
the harness in Spanish: with nothing of it (the 1.5.2) «cambia el idioma a inglés» changes the setting 0 of 28 times and
turns BAXY's voice on or off 16 of 28; with the setting and its two values in the schema and nothing said (+10) 23 of
28; with the clause «its language (language: spanish or english)» and no more (+19) 27 of 28, as the +69 did. So in
Spanish the description says that and no more. In English the prefix is another one, which no Spanish row reads: it
keeps the whole clause and its examples."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "data"
SPANISH = json.loads((DATA / "tool_descriptions.en.v1.json").read_text("utf-8"))
ENGLISH = json.loads((DATA / "tool_descriptions.en_only.v1.json").read_text("utf-8"))
TOOL = "baxy.settings.set"


def test_in_spanish_the_description_names_the_setting_and_its_two_values_and_no_more() -> None:
    told = SPANISH["tools"][TOOL]
    assert ", its language (language: spanish or english) or its tool profile (" in told
    for extra in ("cambia el idioma", "switch to Spanish", "starts anew", "own rules"):
        assert extra not in told
    assert "language" not in SPANISH["arguments"][TOOL]["value"]


def test_in_english_the_description_keeps_what_it_said_and_its_examples() -> None:
    told = ENGLISH["tools"][TOOL]
    assert "its language (language: spanish or english: the language BAXY's own rules, screen and answers are in" in told
    assert "«change the language to English», «switch to Spanish»" in told
    assert "With language: spanish or english." in ENGLISH["arguments"][TOOL]["value"]
