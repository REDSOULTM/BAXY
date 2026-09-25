"""Uso real 2026-09-25 (tanda 8, 7b): replies written where no operation ran said what never happened.

- «ah, y tomates» → «Agregado: tomates.»: nothing was added (the note had only been asked about). Each
  tense of the claim had its own hand-written verb list and the bare participle of a status label was in
  none; now every done, ongoing and promised form comes from one table of effect verbs.
- «¿qué llevo ya?» → «Ya tienes en la lista: huevos, leche, pan de molde y tomates.»: the list was never
  read, it was recited from the chat. The person is the one who holds it («tienes»), so it is theirs.
- «what have I got set right now?» → «You haven't set anything right now.» with two timers running.
- «está mi orden lista para recoger ya» → «Sí, está lista para recoger.»: a yes or no about something of
  the person's that nothing observed.

Knowledge, jokes, stories, drafts, questions, offers, denials and the person's own statements acknowledged
(«me metí en un accidente hoy» → empathy) stay as they are.
"""

from __future__ import annotations

import pytest

from baxy_mind import llm
from baxy_mind.llm import LlmRuntime, conversation_claim_defect, conversation_world_claim

SHOPPING = ("apúntame en la lista de la compra huevos, leche y pan de molde",)
ORDER = "está mi orden lista para recoger ya"
TIMERS = "what have I got set right now?"


@pytest.mark.parametrize(
    ("reply", "ask", "prior"),
    [
        # Tanda 8, verbatim.
        ("Agregado: tomates.", "ah, y tomates", SHOPPING),
        # Tanda 8, the draft that another veto happened to catch.
        ("Listo, tienes una alarma programada para las 6:15 mañana.", "no, mejor a las 6:15", ()),
        # The same claim, in every tense and both languages.
        ("Añadido a tu lista.", "y también pan", ()),
        ("Listo, tomates agregados.", "agrega tomates", ()),
        ("Hecho.", "ponle queso", ()),
        ("Te lo he apuntado.", "apunta queso", ()),
        ("He añadido los tomates a la lista.", "y tomates", ()),
        ("Quedó guardado.", "guárdalo", ()),
        ("Se eliminó la leche de la lista.", "quita la leche", ()),
        ("Se añadió.", "añade pan", ()),
        ("Ya está anotado.", "anota pan", ()),
        ("Cancelado.", "cancelá", ()),
        ("Agregué los tomates.", "y tomates", ()),
        ("Added: tomatoes.", "and tomatoes", ()),
        ("Added to your shopping list.", "add eggs", ()),
        ("Done!", "remove milk", ()),
        ("I've added tomatoes to the list.", "and tomatoes", ()),
        ("I've set a timer for 9 minutes.", "actually make it 9", ()),
        ("I removed the milk.", "take the milk off", ()),
        ("It has been added.", "add bread", ()),
        ("Ya te la programé para las 6:15.", "no, mejor a las 6:15", ()),
    ],
)
def test_a_reply_where_nothing_ran_claims_no_effect(reply, ask, prior):
    assert conversation_claim_defect(reply, ask, prior) == "effect_claim"


@pytest.mark.parametrize(
    ("reply", "ask", "prior"),
    [
        # Tanda 8 and 7b, verbatim.
        ("Ya tienes en la lista: huevos, leche, pan de molde y tomates.", "¿qué llevo ya?", SHOPPING),
        ("Ya tienes en la lista: huevos, pan de molde y tomates.", "vale, léemela otra vez", SHOPPING),
        ("You haven't set anything right now.", TIMERS, ()),
        ("You have a conversation set right now.", TIMERS, ()),
        ("You have a pasta timer set for 9 minutes and a reminder to call grandma at 7:30.", TIMERS, ()),
        # Earlier runs: games and a to-do list stated with nothing read.
        ("No, no tienes Rocket League instalado.", "¿tengo Rocket League?", ()),
        ("Tienes 0 juegos instalados.", "¿cuáles están instalados?", ()),
        # Paraphrases.
        ("En la lista hay huevos, pan y tomates.", "¿qué tengo?", SHOPPING),
        ("Tienes huevos, pan y tomates en tu lista.", "¿qué hay?", ()),
        ("No tienes nada programado.", "¿tengo alarmas?", ()),
        ("Tienes dos temporizadores activos.", "qué timers tengo", ()),
        ("You have two timers running.", "what timers do I have", ()),
        ("Your order is ready for pickup.", "is my order ready", ()),
        ("Tu pedido llegó ayer.", "llegó mi paquete?", ()),
        ("No, your package hasn't arrived yet.", "did my package arrive", ()),
        ("Sí, tienes una reunión a las 3.", "¿tengo reuniones hoy?", ()),
        ("the list has eggs and milk", "whats on it", ("put eggs and milk on my shopping list",)),
    ],
)
def test_a_reply_where_nothing_was_read_states_none_of_the_persons_records(reply, ask, prior):
    assert conversation_claim_defect(reply, ask, prior) == "unread_records"


@pytest.mark.parametrize(
    ("reply", "ask"),
    [
        # Tanda 8, verbatim.
        ("Sí, está lista para recoger.", ORDER),
        # Paraphrases in both languages and spanglish.
        ("Yes, it's ready for pickup.", "is my order ready for pickup"),
        ("No, you didn't.", "did I leave the stove on?"),
        ("Yep, all set.", "is my alarm set"),
        ("Sí, ya llegó.", "necesito saber si mi paquete ya llegó"),
        ("Yes, it shipped yesterday.", "can you tell me if my amazon order shipped"),
        ("No, todavía no.", "ya llegó mi delivery?"),
    ],
)
def test_a_yes_or_no_about_something_of_the_persons_is_not_invented(reply, ask):
    assert conversation_claim_defect(reply, ask) in {"unobserved_answer", "effect_claim", "unread_records"}
    assert conversation_world_claim(reply, ask) != ""


@pytest.mark.parametrize(
    ("reply", "ask", "prior"),
    [
        # The person's own statement acknowledged.
        ("Lamento mucho que hayas tenido un accidente.", "me metí en un accidente hoy", ()),
        ("¡Qué susto! ¿Estás bien?", "me metí en un accidente hoy", ()),
        ("¡Listo! ¿En qué más puedo ayudarte?", "listo", ()),
        # Saying it is not known is the honest reply.
        ("No sé qué hay en tu lista sin leerla.", "¿qué llevo ya?", SHOPPING),
        ("No sé si tu pedido está listo: no lo veo desde aquí.", ORDER, ()),
        ("I don't have access to your orders.", "is my order ready", ()),
        ("No, no puedo saberlo desde aquí.", ORDER, ()),
        ("No lo añadí: no tengo esa capacidad.", "y tomates", ()),
        # Questions and offers.
        ("¿Quieres que lo añada a tu lista?", "y tomates", ()),
        ("Si quieres, lo apunto en tu lista.", "y tomates", ()),
        # Knowledge, arithmetic and yes/no about the world or about what one may do.
        ("2350 dividido entre 7 es aproximadamente 335,71.", "ahorita cuanto es 2350 entre 7", ()),
        ("Sí, París es la capital de Francia.", "¿París es la capital de Francia?", ()),
        ("No, las uvas son tóxicas para los perros.", "¿mi perro puede comer uvas?", ()),
        ("Yes, you need a visa to visit that country.", "do I need a visa for Russia", ()),
        ("Sí, puedes congelar el pan.", "¿puedo congelar mi pan?", ()),
        ("Tienes varias opciones: Kotlin o Swift.", "qué lenguaje aprendo", ()),
        ("Tienes que practicar todos los días.", "cómo aprendo a programar", ()),
        ("You have to add the flour slowly.", "how do I make bread", ()),
        ("Has hecho una gran pregunta.", "por qué el cielo es azul", ()),
        ("Tienes razón, eso es así.", "eso es verdad", ()),
        ("Añadido el azúcar, se bate hasta que espume.", "cómo hago merengue", ()),
        ("Opened to the public in 1889, the Eiffel Tower is in Paris.", "tell me about the eiffel tower", ()),
        ("Hecho curioso: los pulpos tienen tres corazones.", "dime algo curioso", ()),
        ("Cerrado por reformas hasta marzo.", "¿está abierto el museo?", ()),
        ("En 1990 se añadió una estrella a la bandera.", "historia de la bandera", ()),
        ("La lista de Schindler tiene más de mil nombres.", "qué es la lista de schindler", SHOPPING),
        ("El calendario gregoriano tiene doce meses.", "cuántos meses tiene el calendario", ()),
        ("The list of G7 countries includes Canada and Japan.", "what is the list of G7 countries", ()),
        ("After you've saved the file, close the program.", "how do I close word", ()),
        ("Llegó con un traje de cuero y un sombrero de paja.", "ríe como un villano", ()),
        ("I'm an AI assistant, not a real person.", "i need to know if you are a real person or an ai", ()),
        ("Sí, te escucho.", "¿me escuchas?", ()),
        ("Claro, ¿quieres que te recomiende canciones de reggaetón?", "tengo ganas de escuchar reggaetón", ()),
    ],
)
def test_knowledge_acknowledgements_denials_and_questions_are_not_claims(reply, ask, prior):
    assert conversation_claim_defect(reply, ask, prior) == ""


@pytest.mark.parametrize("shape", ["free_content", "content_draft", "translation"])
def test_content_written_for_the_person_is_not_baxys_report(shape):
    story = "Ayer compré un reloj, lo guardé en el cajón y se me olvidó dónde lo puse."
    assert not llm._shaped_conversation_answer_violates_contract(story, "cuéntame algo", shape)
    assert llm._shaped_conversation_answer_violates_contract(story, "cuéntame algo", None)


def test_the_chat_retry_names_the_yes_or_no_it_may_not_give():
    runtime = object.__new__(LlmRuntime)
    payloads = []

    def post(payload):
        payloads.append(payload)
        content = "Agregado: tomates." if len(payloads) == 1 else '{"answer":"No lo añadí: no leí tu lista."}'
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}

    runtime._post = post
    answer, _ = runtime.chat(
        "ah, y tomates", history=[], temperature=0.0, conversation_kind="knowledge", response_language="es",
    )
    assert answer == "No lo añadí: no leí tu lista."
    hint = payloads[1]["messages"][1]["content"]
    assert "no digas que hiciste, haces o harás algo" in hint
    assert "no contestes sí o no" in hint

