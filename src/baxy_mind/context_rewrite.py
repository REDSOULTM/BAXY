"""The input and examples of the contextual rewrite of a follow-up message.
"""

from __future__ import annotations




# Fase 3.5: the dialogue slot already knows why the message depends on the
# conversation; saying which dependency it is keeps the 4B model from returning
# «activalo» or «investigala» unchanged.
_REWRITE_DEPENDENCY_HINTS = {
    "answer": (
        "El último mensaje responde a la pregunta que BAXY acaba de hacer: escribe el pedido de la "
        "persona completado con esa respuesta; si sólo dice que sí a lo que BAXY ofreció, escribe ese "
        "ofrecimiento como pedido de la persona."
    ),
    "destination": (
        "El último mensaje sólo cambia dónde (otro lugar, otra aplicación o sitio): repite el último pedido de "
        "la persona (el último pedido hecho, si está verificado) con ese lugar o destino."
    ),
    # Tanda 8: the examples of this hint named things («goleador», «partido») the model copied into rewrites
    # of other conversations; the worked examples are the shared few-shot turns (_REWRITE_EXAMPLES).
    "followup": (
        "El último mensaje sigue la conversación: escribe el pedido anterior de la persona con lo que cambia, o la "
        "pregunta con la cosa, el número, el lugar, el día o el tema que señala."
    ),
    "reference": (
        "El último mensaje usa un pronombre (lo, la, le) que nombra algo que la persona dijo antes: "
        "escríbelo con esa cosa en lugar del pronombre."
    ),
    "topic": (
        "El último mensaje pide buscar o averiguar algo sin decir sobre qué: agrégale el tema que la "
        "persona nombró antes."
    ),
}

# Tanda 8 (official window): with only rules in the system prompt the 4B model returned «y eso por 12?», «40
# percent» and «is the entrance free» unchanged. Worked conversations, one per shape (a number BAXY computed, a
# day, a correction or an answer to BAXY's question, a level answered, an item added to a list or asked about, a
# timer corrected, what is set, a topic, a thing BAXY named, a place said «allá», another song), shown as turns
# of the same form as the real input. None is a phrase of a measured tanda.
# Tanda 8 replay: the twelve cost ~750 prompt tokens (rewrite p50 ~850 ms). Each is tagged with the shapes it
# teaches (``semantic.dialogue.shape``) and a rewrite is shown only the ones of its message's shape.
# (shapes, verified, conversation, message, rewrite).
_REWRITE_EXAMPLES: tuple[tuple[frozenset[str], tuple[str, ...], tuple[tuple[str, str], ...], str, str], ...] = (
    (frozenset({"pointer", "question"}), (), (("persona", "cuánto es 18 por 45"), ("BAXY", "18 por 45 es 810.")),
     "¿y eso dividido en 3?", "cuánto es 810 dividido en 3"),
    (frozenset({"time", "destination"}), ("lugar (place): Lima, Perú",),
     (("persona", "¿llueve hoy?"), ("BAXY", "Hoy en Lima no llueve.")), "¿y pasado mañana?",
     "¿llueve pasado mañana en Lima?"),
    (frozenset({"time", "answer"}), (), (("persona", "recuérdame llamar al dentista mañana a las 5"),
                                         ("BAXY", "¿A las 5 de la mañana o de la tarde?")),
     "no, mejor a las 4 y media", "recuérdame llamar al dentista mañana a las 4 y media"),
    (frozenset({"answer", "amount"}), (), (("persona", "the music is way too loud"), ("BAXY", "What volume do you want?")),
     "25 percent", "set the music volume to 25 percent"),
    # Tanda 9: a time said to BAXY's open question, in a conversation about alarms, is the alarm the person wants.
    (frozenset({"answer", "time"}), (), (("persona", "what alarms do I have?"), ("BAXY", "You have one alarm, at 6:00."),
                                         ("persona", "ok, go ahead"), ("BAXY", "What would you like me to do?")),
     "it'll be for 7:40 am", "set an alarm for 7:40 am"),
    (frozenset({"item"}), (), (("persona", "anota en la lista del súper arroz y aceite"),
                               ("BAXY", "Anoté arroz y aceite en la lista del súper.")),
     "ah, y también azúcar", "anota en la lista del súper azúcar"),
    (frozenset({"listing", "reference"}), (), (("persona", "anota en la lista del súper azúcar"),
                                               ("BAXY", "Anoté azúcar en la lista del súper.")),
     "¿qué tengo ya?", "¿qué tengo ya en la lista del súper?"),
    (frozenset({"amount"}), ("último pedido hecho (last request done): pon un temporizador de 15 minutos para el arroz",
                             "alarma o temporizador creado (alarm or timer set): temporizador de 15 minutos para el arroz"),
     (("persona", "pon un temporizador de 15 minutos para el arroz"), ("BAXY", "Listo, el temporizador suena en 15 minutos.")),
     "mejor que sean 12", "pon un temporizador de 12 minutos para el arroz"),
    (frozenset({"listing"}), ("alarma o temporizador creado (alarm or timer set): timer for the laundry, 40 minutes",
                              "recordatorio creado (reminder set): water the plants"),
     (("persona", "remind me to water the plants at 6"), ("BAXY", "Done, I'll remind you at 6:00.")),
     "what do I have scheduled?", "what alarms, timers and reminders do I have scheduled?"),
    (frozenset({"question", "topic"}), (), (("persona", "who won the Celtics game last night"),
                                            ("BAXY", "The Celtics beat the Knicks 112 to 104.")),
     "and who scored the most points", "who scored the most points in the Celtics game last night"),
    (frozenset({"question", "reference"}), (), (("persona", "recommend me a museum in Rome"),
                                                ("BAXY", "The Vatican Museums are a classic choice.")),
     "are they open on sundays", "are the Vatican Museums open on sundays"),
    (frozenset({"place", "destination"}), ("lugar (place): Tokio, Japón",),
     (("persona", "qué hora es en Tokio"), ("BAXY", "En Tokio son las 10:20.")),
     "y si allá son las 8 de la mañana, qué hora es aquí", "si en Tokio son las 8 de la mañana, qué hora es aquí"),
    (frozenset({"another"}), ("música pedida (music asked for): cumbia",),
     (("persona", "pon algo de cumbia"), ("BAXY", "Suena La Pollera Colorá.")),
     "esa no, otra más lenta", "pon otra de cumbia más lenta"),
    # Tanda 7b «escríbeme … sobre eso» after a question and BAXY's answer: «eso» is what the person asked about.
    (frozenset({"pointer"}), (), (("persona", "quién ganó el Tour de Francia"), ("BAXY", "Lo ganó Tadej Pogačar.")),
     "escribe un poema corto sobre eso", "escribe un poema corto sobre quién ganó el Tour de Francia"),
)
# At most this many worked conversations per rewrite; a shape with none is shown the first ones.
_REWRITE_EXAMPLES_SHOWN = 3


def _rewrite_input(text: str, context: object, verified: object) -> str:
    """The rewrite's input: what was verified, the conversation, and the last message."""

    lines = "\n".join(
        f"{'BAXY' if speaker == 'BAXY' else 'persona'}: {str(line).strip()[:400]}"
        for speaker, line in list(context)[-8:]
    )
    state = "\n".join(f"- {str(line).strip()[:300]}" for line in list(verified)[:12])
    head = f"Lo verificado en esta conversación:\n{state}\n\n" if state else ""
    return f"{head}Conversación:\n{lines}\n\nÚltimo mensaje: {str(text).strip()[:1_024]}"
