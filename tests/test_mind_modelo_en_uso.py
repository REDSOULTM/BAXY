"""MODX1 (en vivo, 16-11-2026: Gemma-4-12B por API contestó «Estoy utilizando el modelo de serie por defecto de BAXY» a «¿Qué
modelo estás usando?»): a model the person chose in place of BAXY's own is told in the system text which one it is, as a fact
of this PC; with BAXY's own model the system text is exactly the one before."""
from __future__ import annotations

from baxy_mind import harness_language
from baxy_mind import mind as M


def test_nothing_is_said_with_baxys_own_model():
    assert M.model_in_use_fact({}) == ""
    assert M.model_in_use_fact({"BAXY_MIND_MODEL_IN_USE": ""}) == ""
    # A form the App does not write is not read as a model.
    assert M.model_in_use_fact({"BAXY_MIND_MODEL_IN_USE": "gemma"}) == ""
    assert M.model_in_use_fact({"BAXY_MIND_MODEL_IN_USE": "gemma|nube"}) == ""


def test_the_model_and_where_it_runs_are_said():
    ollama = M.model_in_use_fact({"BAXY_MIND_MODEL_IN_USE": "unsloth/gemma-4-12b-it-GGUF:Q4_K_M|ollama"})
    api = M.model_in_use_fact({"BAXY_MIND_MODEL_IN_USE": "/modelos/g4e12.gguf|api"})
    assert "unsloth/gemma-4-12b-it-GGUF:Q4_K_M (en Ollama, en este PC)" in ollama
    assert "/modelos/g4e12.gguf (por API)" in api
    assert "en lugar del modelo de serie" in api
    assert "own.gguf (en el motor de BAXY, en este PC)" in M.model_in_use_fact({"BAXY_MIND_MODEL_IN_USE": "own.gguf|gguf"})


def test_in_english_it_is_said_in_english():
    harness_language.use("en")
    try:
        said = M.model_in_use_fact({"BAXY_MIND_MODEL_IN_USE": "ministral|ollama"})
    finally:
        harness_language.use("es")
    assert said.startswith("\nYou now think with the model ministral (in Ollama, on this PC)")
