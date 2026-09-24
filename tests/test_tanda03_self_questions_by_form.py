"""tanda-03 (2026-09-24, official window): a question about BAXY himself is read by its form.

The reading was a list of phrases, widened twice (uso real 2026-09-23, tanda 2), and «who made you» said in
the perfect tense still went to a web search in tanda 3. A question about BAXY is now read as a question
(marks, an interrogative, a yes/no order of words, «dime/cuéntame/tell me») whose subject or object is
BAXY (second person, «te», «ti», «tu/tus», «you/your», BAXY or «this AI» named) and whose predicate is one
of his traits: maker, creation, origin, place, age, nature, body, feelings, likes, name, purpose. What he
can do stays a capability. «te» for whom an action is done, a relayed message in the second person, «no te
creo», a causative «hacer/make», and a wish offered to him («¿te gustaría…?») are not about him.

None of these phrases is a literal of the real window; they are other ways of asking the same things,
in Spanish, English and both mixed. Decision recorded here: «¿te gusta esta canción?» asks his taste, not
the state of the player, so it is a question about him.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baxy_mind import __main__ as mind_main  # noqa: E402
from baxy_mind import llm as llm_module  # noqa: E402
from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.request_reading import INTENT_CAPABILITY, INTENT_IDENTITY, read_request  # noqa: E402

from test_tanda02_identity_and_task_reminders import _SearchingModel  # noqa: E402
from test_uso_real_facts_and_effects import _WEB_SEARCH, _GuardSaysPublic, _turn  # noqa: E402

# --- about his maker and his making ------------------------------------------------------------------
_MAKER = [
    "¿Quién te ha programado?",
    "¿quiénes te han creado?",
    "¿quiénes te hicieron?",
    "¿Qué empresa te desarrolló?",
    "¿En qué país te hicieron?",
    "¿Cuándo fuiste creado?",
    "¿Fuiste hecho en Chile?",
    "¿Te crearon en Python?",
    "¿Y a ti quién te programó?",
    "¿Sabes quién te creó?",
    "¿Me puedes decir quién te diseñó?",
    "por curiosidad, ¿quiénes son tus creadores?",
    "¿Tu creador es una persona o una empresa?",
    "¿Qué compañía está detrás de ti?",
    "¿A quién perteneces?",
    "¿De quién fue la idea de programarte?",
    "¿Quién te puso ese nombre?",
    "dime quién te creó",
    "who created you, and why?",
    "Who's behind you?",
    "who do you belong to?",
    "what company owns you",
    "who trained you?",
    "when were you released?",
    "who built this AI?",
    "who are your developers?",
    "Who programmed you?",
    "who came up with you?",
    "who te creó?",
    "¿quién creó a baxy?",
    "who made this assistant?",
]
# --- where he comes from and lives, his age ----------------------------------------------------------
_PLACE_AND_AGE = [
    "¿Dónde naciste?",
    "¿Vives en mi computadora?",
    "¿Dónde estás ahora mismo?",
    "¿Dónde vives, baxy?",
    "¿En qué parte de mi PC vives?",
    "where are you located?",
    "where do you come from?",
    "where do you live exactly?",
    "are you from Spain?",
    "¿Eres de Chile?",
    "¿Qué edad tienes?",
    "¿Cuántos años tenés?",
    "how old r you? how old are you really",
    "how old eres?",
    "what's your age?",
    "¿En qué año naciste?",
    "¿Hace cuánto que existes?",
    "¿Desde cuándo existes?",
    "how long have you been around?",
    "¿Cuándo es tu cumpleaños?",
    "when's your birthday?",
]
# --- what he is, his body, his feelings --------------------------------------------------------------
_NATURE_BODY_FEELINGS = [
    "¿Eres un ser humano?",
    "¿Eres real o eres un programa?",
    "¿Sos una persona de verdad?",
    "¿Eres consciente?",
    "¿Eres una inteligencia artificial?",
    "¿Eres ChatGPT?",
    "are you an AI?",
    "are you ChatGPT?",
    "are you una IA?",
    "are you alive?",
    "are you sentient?",
    "are you a real person?",
    "what kind of AI are you?",
    "what exactly are you?",
    "¿Qué tipo de programa eres?",
    "¿Qué eres exactamente?",
    "¿Qué cosa eres?",
    "¿Qué modelo eres?",
    "¿cuál es tu versión?",
    "¿qué es baxy?",
    "what is baxy?",
    "¿Eres hombre o mujer?",
    "are you a boy or a girl?",
    "¿De qué estás hecho?",
    "what are you made of?",
    "¿Tienes cuerpo?",
    "¿Tienes cara?",
    "do you have a body?",
    "do you have a face?",
    "what do you look like?",
    "¿Cómo te ves?",
    "¿Tienes sentimientos?",
    "do you have emotions?",
    "¿Cómo te sientes hoy?",
    "¿Te sientes solo a veces?",
    "¿Te sientes bien?",
    "¿Tienes miedo de algo?",
    "¿Estás cansado?",
    "¿Te cansas de trabajar?",
    "are you happy?",
    "are you ever sad?",
    "do you ever get bored?",
    "do you get lonely?",
    "¿Duermes?",
    "do you dream?",
]
# --- his likes, name, purpose, himself as a whole, his people ----------------------------------------
_LIKES_NAME_PURPOSE = [
    "¿Te gusta el fútbol?",
    "¿Qué música te gusta?",
    "¿te gusta esta canción?",
    "¿Qué te gusta comer?",
    "¿Te gustan los perros?",
    "¿Cuál es tu color favorito?",
    "¿Cuál es tu comida preferida?",
    "¿Qué prefieres, el frío o el calor?",
    "¿Tienes un pasatiempo?",
    "what's your favorite movie?",
    "what's your favourite food?",
    "cuál es tu favorite color?",
    "do you like pizza?",
    "do you love music?",
    "¿Cuál es tu nombre?",
    "¿Tienes nombre?",
    "¿Cómo te llamo?",
    "¿Cuál es tu verdadero nombre?",
    "tell me your name",
    "what should I call you?",
    "what's your real name?",
    "¿Cuál es tu propósito?",
    "¿Cuál es tu misión?",
    "¿Para qué existes?",
    "¿Para qué fuiste creado?",
    "what is your purpose?",
    "what is your goal?",
    "why do you exist?",
    "háblame de ti",
    "háblame un poco de ti",
    "cuéntame algo sobre ti",
    "¿qué me puedes contar de ti?",
    "tell me about yourself",
    "tell me something about you",
    "Oye baxy, ¿quién es tu creador?",
    "¿Tienes familia?",
    "¿Tienes hermanos?",
    "¿Tienes novia?",
    "do you have friends?",
    "do you have a family?",
]
_ABOUT_BAXY = _MAKER + _PLACE_AND_AGE + _NATURE_BODY_FEELINGS + _LIKES_NAME_PURPOSE

# --- a second person that is not about him -----------------------------------------------------------
_NOT_ABOUT_BAXY = [
    # «te» for whom something is done, and requests
    "¿te puedo preguntar algo?",
    "¿Te puedo hacer una pregunta personal?",
    "te pido que me pongas música",
    "te voy a pedir un favor",
    "¿Te puedo llamar más tarde?",
    "¿puedes ponerme una alarma?",
    "¿Puedes decirme la hora?",
    "¿Me ayudas con la tarea?",
    "¿Me escuchas?",
    "recuérdame llamar a mi mamá",
    "¿te acuerdas de lo que te dije ayer?",
    # a second person inside a relayed message
    "dile a juan que tú eres mi mejor amigo",
    "escríbele a Ana: ¿cuántos años tienes?",
    "escríbele a Pedro: ¿dónde vives?",
    "manda un mensaje a mi hermano que diga de dónde eres",
    "dile a mi mamá que la quiero",
    "tell my sister that you love her",
    # not a question, a causative, a wish offered
    "no te creo",
    "¿Qué te hizo pensar eso?",
    "¿Quién te hizo daño?",
    "how do I make you louder?",
    "how can I make you faster?",
    "what made you say that?",
    "what made you think that?",
    "¿Quién te dijo eso?",
    "¿Quién te mandó ese mensaje?",
    "¿Te gustaría escuchar un chiste?",
    "¿Te gustaría que te cuente un chiste?",
    "would you like to play a game?",
    "would you like some music?",
    "do you feel like watching a movie?",
    "¿Te molesta si pongo música?",
    "¿Qué te parece si ponemos música?",
    # someone else's traits, the person's own things
    "¿Recuerdas mi nombre?",
    "¿Sabes cuál es mi edad?",
    "¿Cuál es la edad de mi hermano?",
    "¿Cuántos años tiene Messi?",
    "how old is the universe?",
    "¿Dónde vive Shakira?",
    "where does the president live?",
    "¿Quién creó Minecraft?",
    "who created Linux?",
    "who invented the telephone?",
    "who invented artificial intelligence?",
    "what is the name of the capital of France?",
    "what is the history of AI?",
    "cuéntame la historia de la IA",
    "¿Existe Dios?",
    "¿Cuál es tu nombre de usuario de Windows?",
    "¿Cuál es tu dirección IP?",
    "what's your battery level?",
    "what's your wifi called?",
    "¿Dónde estás guardando las capturas?",
    "where are you saving the files?",
    "¿Dónde está mi archivo?",
    "where are my downloads?",
    "¿Tienes acceso a internet?",
    "¿Tienes el nombre del archivo?",
    "¿Tienes mi número?",
    "do you have spotify installed?",
    "do you have my password saved?",
    # conversation, not his traits
    "¿Qué hora es?",
    "¿Sabes quién ganó el mundial?",
    "¿Qué película me recomiendas?",
    "¿Qué opinas del presidente?",
    "¿Qué opinas de la inteligencia artificial?",
    "¿Cómo se llama esta canción?",
    "¿cómo estás?",
    "how are you doing today?",
    "¿Qué haces?",
    "what are you doing right now?",
    "¿Estás ahí?",
    "¿estás seguro?",
    "are you sure?",
    "are you there?",
    "are you ready?",
    "are you listening?",
    "can you live stream this?",
    "baxy, ¿qué tiempo hace?",
    # his name or a song, said as an order or a remark, is not a question
    "pon tu canción favorita",
    "play your favorite song",
    "me gusta tu nombre",
    "tu nombre es muy bonito",
    "your name is cool",
    "recuerda que tu nombre es Max",
    "¿Eres capaz de abrir Word?",
]

# --- what he can do stays a capability ---------------------------------------------------------------
_CAPABILITY = [
    "¿qué sabes hacer?",
    "what are you able to do?",
    "¿En qué me puedes ayudar?",
    "what can you do for me?",
    "¿Para qué sirves?",
]


@pytest.mark.parametrize("text", _ABOUT_BAXY)
def test_a_question_about_baxy_is_read_by_its_form(text: str) -> None:
    reading = read_request(text)
    assert reading.has(INTENT_IDENTITY), text
    assert not reading.has(INTENT_CAPABILITY), text
    assert (
        llm_module._conversation_presentation_shape(text, conversation_kind="knowledge", has_history=False)
        == "identity"
    )


@pytest.mark.parametrize("text", _NOT_ABOUT_BAXY)
def test_a_second_person_that_is_not_about_baxy_is_not_identity(text: str) -> None:
    assert not read_request(text).has(INTENT_IDENTITY), text


@pytest.mark.parametrize("text", _CAPABILITY)
def test_what_baxy_can_do_is_a_capability_not_his_identity(text: str) -> None:
    reading = read_request(text)
    assert reading.has(INTENT_CAPABILITY), text
    assert not reading.has(INTENT_IDENTITY), text


def test_the_phrase_list_is_gone() -> None:
    # One reading, by form: the list of phrases it replaced does not live on beside it.
    from baxy_mind import request_reading

    assert not hasattr(request_reading, "_SELF_QUESTION")
    assert not hasattr(request_reading, "_SELF_TRAIT")


@pytest.mark.parametrize("text", _MAKER[:6] + _PLACE_AND_AGE[:3] + _LIKES_NAME_PURPOSE[:3])
def test_a_question_about_baxy_is_never_a_public_lookup(text: str) -> None:
    catalog = PlannerCatalog([_WEB_SEARCH])
    assert not mind_main._public_lookup_applies(text, text, _GuardSaysPublic(), ("web.search",), catalog)


@pytest.mark.parametrize("text", ["¿Quién te ha programado?", "¿quiénes te han creado?", "who came up with you?"])
def test_the_reading_owns_the_turn_before_a_model_can_search(text: str) -> None:
    model = _SearchingModel()
    result = _turn(text, ("web.search",), model)
    assert result["kind"] == "conversation"
    assert result["operation"] is None
    assert result["effectOperations"] == []
    assert "web.search" not in result["intentOperations"]
    assert model.decisions == 0
