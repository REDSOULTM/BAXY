# -*- coding: utf-8 -*-
"""Lock de los gates de FORMA del FG router (caza 2026-06-20): detección de
preguntas (WH + SÍ/NO), de órdenes NEGADAS y de pedidos imperativos de LECTURA.

Son señales ESTRUCTURALES (gramática, no listas de contenido) — el contrato es
que distinguen FORMA, así que estos casos no deben regresar. Funciones puras:
no bootean ni el encoder ni FG.
"""
import os

os.environ.setdefault("GEMMA4_ENCODER_ONNX", "1")

from gemma4_agent.routing.fg_router import (  # noqa: E402
    _is_interrogative,
    _is_negated_command,
    _is_read_request,
)


class TestInterrogative:
    def test_wh_questions(self):
        for q in ["qué hora es", "cuántos procesos hay", "what time is it",
                  "cuál es la capital", "dónde está", "quién sos"]:
            assert _is_interrogative(q), q

    def test_yes_no_questions_without_mark(self):
        # inversión verbo-sujeto, sin "?" (vienen de STT) — antes caían a no_tool->confab
        for q in ["está corriendo spotify", "tengo discord abierto", "tengo internet",
                  "estoy conectado a internet", "is spotify running", "is chrome open",
                  "hay alguna ventana abierta", "está silenciado el audio"]:
            assert _is_interrogative(q), q

    def test_question_mark_anywhere(self):
        assert _is_interrogative("y disco?")
        assert _is_interrogative("¿está abierto?")

    def test_imperatives_are_not_questions(self):
        for q in ["abrí chrome", "poné música", "subí el volumen", "bajá el brillo",
                  "cerrá spotify", "reproducí despacito", "apagá la pc"]:
            assert not _is_interrogative(q), q

    def test_tener_que_is_not_a_question(self):
        # "tengo que <verbo>" = obligación (afirmación), NO pregunta -> no debe
        # bloquear la acción vía el read/write guard.
        for q in ["tengo que apagar la pc", "tengo que cerrar discord",
                  "tienes que reiniciar"]:
            assert not _is_interrogative(q), q


class TestNegatedCommand:
    def test_negated_commands(self):
        for q in ["no abras chrome", "no subas el volumen", "no pongas música",
                  "no cierres spotify", "no silencies el audio", "no bajes el brillo",
                  "don't open chrome", "do not open chrome", "no apagues la pc",
                  "mejor no abras la calculadora", "no quiero música"]:
            assert _is_negated_command(q), q

    def test_affirmatives_not_negated(self):
        for q in ["abrí chrome", "poné música", "subí el volumen", "apagá la pc",
                  "reproducí despacito"]:
            assert not _is_negated_command(q), q

    def test_clitic_after_no_is_not_a_command_negation(self):
        # "no me gusta..., poné otra" niega un SENTIMIENTO, no la orden -> la
        # acción ("poné otra") debe proceder.
        for q in ["no me gusta esta canción poné otra", "no me digas la hora",
                  "no se puede"]:
            assert not _is_negated_command(q), q

    def test_bare_no_is_not_a_command(self):
        assert not _is_negated_command("no")


class TestReadRequest:
    def test_imperative_read_requests(self):
        # "-me" = "mostraME / deciME a mí" = leer
        for q in ["mostrame el volumen", "mostrame el brillo", "decime la hora",
                  "muéstrame las ventanas", "show me the volume", "tell me the time"]:
            assert _is_read_request(q), q

    def test_not_read_requests(self):
        # imperativos de acción (sin -me) y preguntas no son read-request
        for q in ["subí el volumen", "poné música", "abrí chrome", "qué hora es",
                  "mostrá el escritorio"]:
            assert not _is_read_request(q), q
