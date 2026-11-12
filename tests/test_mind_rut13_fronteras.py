"""RUT13 (12-11-2026): con las herramientas de rutinas en el catálogo (rut10) la puerta perdió cuatro filas que la 1.4.2
acertaba, y ATR2 las atribuyó a rut10. Medido pieza por pieza (prefijo de la 1.4.2 más una pieza, primera ficha, con el
calentamiento del banco; INFORME_RUT13.md §2), ninguna pieza es la culpable sola: eran tres fronteras que ya estaban al
borde y que cualquier texto nuevo voltea. Las tres se cierran en la descripción de la herramienta que ganaba sin deber
(sin fuente: medición propia, banco de decisiones sobre int33-cand2, semillas 0-4 y 0-9):
  «abre word» creaba «Nuevo documento.docx»   5 de 5 -> 0 de 5 (abre Word, la misma llamada que la 1.4.2)
  «mute Yalimbe real quick» callaba el micro  2 de 10 -> 0 de 10
  «Búscame una receta» sin buscar             3 de 5 -> 0 de 5;  «dale otra vez po» fallaba 5 de 5 (play) -> 0 de 5"""
import json
from pathlib import Path

TOOLS = json.loads((Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "data"
                    / "tool_descriptions.en.v1.json").read_bytes())["tools"]


def _excluded(operation: str) -> str:
    text = TOOLS[operation]
    return text[text.index("Do not use when:"):text.index("Examples:")]


def test_creating_a_document_says_that_opening_the_program_is_not_it() -> None:
    # In 1.4.2 «abre word» was already a near-tie (app_open 0.59, office_document_create 0.41): five of the eight
    # routine pieces flip it each alone. The tool said when not to use it for two neighbours and not for the nearest one.
    assert "opening Word or Excel when no document or text was asked for (use app_open)" in _excluded("office.document.create")


def test_the_microphone_mute_says_it_takes_no_name() -> None:
    # A made-up name to silence («mute Yalimbe») went to the microphone with audio_device_set beside it: 0.26 of the
    # calls, and a low_reversible call is never held by the doubt, so it muted. With the sentence, 0.13 and 0 of 10.
    text = TOOLS["audio.microphone.mute"]
    assert text.startswith("Mute or unmute the default microphone (sound input), the one in use: it takes no name. Use when:")


def test_media_control_is_for_what_already_plays_and_its_examples_carry_no_dale() -> None:
    # Whole in Esencial since RUT6, its «dale play» answered «dale otra vez po» (nothing playing, nothing said before)
    # with play, and its bare «play» took «Búscame una receta» away from the search.
    text = TOOLS["media.control"]
    assert "anterior or play, about what is already playing, without naming new content" in text
    assert "dale play" not in text and "«ponle play»" in text[text.index("Examples:"):]
