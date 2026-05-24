"""Tests del splitter multi-intent (investigación 7).

"abrí Spotify y bajá el volumen" = 2 acciones. Un 4B causal colapsa el
multi-intent; lo partimos con regex ANTES del LLM. Conservador: no parte un "y"
entre sustantivos ni nombres propios.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.command_splitter import (
    split_command, has_back_reference, plan_clauses,
    extract_click_target, is_key_name, extract_write_payload,
)


class SplitterTest(unittest.TestCase):
    def test_two_actions_split(self):
        for cmd in (
            "abrí Spotify y bajá el volumen",
            "abre Steam y pon música",
            "muteá el sonido y abrí la calculadora",
        ):
            self.assertEqual(len(split_command(cmd)), 2, cmd)

    def test_innocent_y_does_not_split(self):
        # 'y' entre sustantivos / nombres propios / dentro de un mensaje -> NO parte
        for cmd in (
            "pon sal y pimienta en la lista",
            "reproducí Tom y Jerry",
            "mandale a mamá que la quiero y la extraño",
            "¿qué hora es?",
            "abre Spotify",
        ):
            self.assertEqual(len(split_command(cmd)), 1, cmd)

    def test_dependent_clause_detected(self):
        clauses = plan_clauses("buscá un Word y abrilo")
        self.assertEqual(len(clauses), 2)
        self.assertFalse(clauses[0]["depends_on_prev"])
        self.assertTrue(clauses[1]["depends_on_prev"])  # 'abrilo' refiere al Word

    def test_back_reference_helper(self):
        self.assertTrue(has_back_reference("abrilo"))
        self.assertTrue(has_back_reference("ciérralo"))
        self.assertTrue(has_back_reference("ponelo en pausa"))
        self.assertFalse(has_back_reference("abrí Chrome"))

    def test_cap_on_too_many_clauses(self):
        # MAX_CLAUSES=5 (techo computer-use): hasta 5 cláusulas SÍ parte; más
        # de 5 -> no confiar, tratar como un comando (ruido/lista).
        from gemma4_agent.command_splitter import MAX_CLAUSES
        self.assertEqual(MAX_CLAUSES, 5)
        # exactamente 5 -> parte (misión válida de 5 pasos)
        cmd5 = "abre A y abre B y abre C y abre D y abre E"
        self.assertEqual(len(split_command(cmd5)), 5)
        # 6 -> excede el cap -> no parte (status quo, el LLM ve todo)
        cmd6 = "abre A y abre B y abre C y abre D y abre E y abre F"
        self.assertEqual(len(split_command(cmd6)), 1)

    def test_empty_and_none_safe(self):
        self.assertEqual(split_command(""), [""])
        self.assertEqual(split_command("   "), ["   "])

    def test_chain_of_3_4_5_steps(self):
        # Fase A/B: cadenas de 3-5 pasos parten correctamente (verbos de click/
        # navegación/guardado ahora en _IMPERATIVE).
        self.assertEqual(
            len(split_command("abrí la calculadora y escribí 2+2 y apretá enter")), 3)
        self.assertEqual(
            len(split_command("abrí Spotify y bajá el volumen y poné música y cerrá la ventana")), 4)
        self.assertEqual(
            len(split_command(
                "abrí Chrome y andá a Configuración y activá el modo oscuro y guardá y cerrá")), 5)

    def test_noise_does_not_split_as_chain(self):
        # listas/nombres no son misiones aunque tengan muchos "y".
        self.assertEqual(len(split_command("sal y pimienta y azúcar y harina y huevos y leche")), 1)
        self.assertEqual(len(split_command("Tom y Jerry")), 1)

    def test_asyndeton_comma_splits_actions(self):
        # Regresión del eval Tier-4 (2026-05-24): una coma SIN conjunción antes
        # de una acción ("abrí la calc, escribí X y apretá enter") dejaba dos
        # acciones pegadas -> el 4B abría pero no tecleaba. La coma+imperativo
        # ahora parte; la coma+sustantivo (listas) NO.
        self.assertEqual(
            len(split_command("abrí la calculadora, escribí 5+3 y apretá enter")), 3)
        self.assertEqual(
            len(split_command("abrí el bloc de notas, escribí hola mundo y apretá enter")), 3)
        # ruido: sustantivos separados por coma no parten (no son imperativos)
        self.assertEqual(len(split_command("sal, pimienta, azúcar, harina")), 1)
        self.assertEqual(len(split_command("comprá pan, leche y huevos")), 1)


class ClickTargetExtractTest(unittest.TestCase):
    """Fase B: extract_click_target separa el verbo-click del label, multi-idioma,
    y descarta clicks posicionales. is_key_name distingue tecla de botón."""

    def test_extracts_button_label_multilang(self):
        cases = {
            "apretá enter": "enter",
            "clickeá el botón Guardar": "botón Guardar",
            "clickeá en el botón Aceptar": "botón Aceptar",
            "tocá Aceptar": "Aceptar",
            "seleccioná Configuración": "Configuración",
            "click Save": "Save",            # en
            "press Cancel": "Cancel",        # en
            "clique em Enviar": "Enviar",    # pt
            "klick auf OK": "OK",            # de
        }
        for inp, exp in cases.items():
            self.assertEqual(extract_click_target(inp), exp, msg=inp)

    def test_non_click_returns_none(self):
        for inp in ("escribí hola", "abrí Chrome", "apretá", "bajá el volumen"):
            self.assertIsNone(extract_click_target(inp), msg=inp)

    def test_positional_click_returns_none(self):
        # "clickeá ahí/aquí" es coordenada, no un control por Name -> None.
        for inp in ("clickeá ahí", "click here", "tocá acá"):
            self.assertIsNone(extract_click_target(inp), msg=inp)

    def test_is_key_name(self):
        for k in ("enter", "Enter", "ESC", "tab", "espacio", "f5", "arriba"):
            self.assertTrue(is_key_name(k), msg=k)
        for not_k in ("Guardar", "Aceptar", "OK", "botón Enviar", "", None):
            self.assertFalse(is_key_name(not_k), msg=str(not_k))

    def test_write_and_click_are_disjoint(self):
        # una cláusula de escritura no se confunde con click y viceversa.
        self.assertIsNone(extract_click_target("escribí hola mundo"))
        self.assertIsNone(extract_write_payload("clickeá Guardar"))


from gemma4_agent.command_splitter import _ensure_action_centroids

_HAS_ENCODER = _ensure_action_centroids()


@unittest.skipUnless(_HAS_ENCODER, "encoder multilingüe no disponible")
class MultilingualSplitTest(unittest.TestCase):
    """CAPA 2: parte multi-intent en CUALQUIER idioma (no solo español), por
    embeddings. Sustantivos coordinados ('Tom and Jerry') NO parten. Principio
    universal del proyecto (CLAUDE.md): nada de regex es-only."""

    def setUp(self):
        os.environ["GEMMA4_SPLIT_MULTILANG"] = "1"

    def test_two_actions_split_multilang(self):
        for cmd in (
            "open Spotify and turn down the volume",   # en
            "öffne Spotify und mach leiser",            # de
            "abre o Spotify e baixa o volume",          # pt
            "ouvre Spotify et baisse le son",           # fr
        ):
            self.assertEqual(len(split_command(cmd)), 2, cmd)

    def test_coordinated_nouns_do_not_split_multilang(self):
        # 'y'/'and' entre sustantivos o nombres propios -> NO parte (1 sola)
        for cmd in (
            "play Tom and Jerry",
            "add salt and pepper to the list",
            "what is the weather and the time",
        ):
            self.assertEqual(len(split_command(cmd)), 1, cmd)

    def test_disabled_layer2_falls_back_to_spanish_only(self):
        os.environ["GEMMA4_SPLIT_MULTILANG"] = "0"
        try:
            # sin capa 2, un multi-intent inglés NO parte (degradación elegante)
            self.assertEqual(
                len(split_command("open Spotify and turn down the volume")), 1)
            # el español (capa 1) sigue partiendo
            self.assertEqual(
                len(split_command("abrí Spotify y bajá el volumen")), 2)
        finally:
            os.environ["GEMMA4_SPLIT_MULTILANG"] = "1"


if __name__ == "__main__":
    unittest.main()
