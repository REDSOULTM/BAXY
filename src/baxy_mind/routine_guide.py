"""RUT7: the person's routines are made, listed, turned on or off and deleted by the App itself, by voice, with no model.

**An exception to «no word lists», of the same kind as ring_answer's** (owner, 2026-11-09 ~01:00, literal: «para ciertas
funciones puedes hacer regex… una regla de regex que hardcodeada básicamente para cosas que son que el usuario sí o sí va
a decir en torno a las cosas de la aplicación»; the leader's order of 2026-11-11, ENCARGO_RUT7: «crear, listar,
activar/desactivar y borrar rutinas deja de depender de que el modelo escriba una llamada. Lo hace la App con un camino
guiado, enteramente por voz»). RUT6 measured the stock 4B writing baxy.routines create: the owner's five examples saved
well 38/60 in Esencial and 14/20 in Completo, six effects nobody asked for while «saving», and the tool's text (+1,700
tokens per profile) took the «recuérdame…» reminders from 8/8 to 4/8. documentacion/RUTINAS.md §5 d says the same, the
exact forms and what this may never be used for.

What is compared here is form only, on orders about BAXY's own routines:

- ``heard``: outside a guide, the whole turn (BAXY's name and a few fillers aside) is one of the closed orders below
  («crea una rutina», «qué rutinas tengo», «borra la rutina X»…), or it *begins* with «cuando (te) diga X, …» / «todos
  los días a las H dime …» (the one-breath forms, split by their form: word | order; when | text). Never inside a
  longer request. A one-breath phrase that does not split cleanly opens the guide at its first question.
- ``Guide``: BAXY's questions, one by one, and the person's answers as what they are: the answer to that question, kept
  as said (the order of a routine is their words, whole). Nothing is done while it is made; only the last «sí» saves, as
  one baxy.routines create the kernel authorizes as any call. «cancela» leaves at any step with nothing saved.
- ``spoken``: a time and its days as people say them («a las diez y media de la mañana», «10 pm», «de lunes a
  viernes», «mañana»). What it does not understand whole it does not guess: the guide asks that part again; an hour
  said without «de la mañana / de la tarde» is asked, never assumed.
- ``told``: the fixed sentence for the receipt of the call the guide proposed, from that receipt only.

As a smart speaker's own routines are made by fixed steps (Google Nest Help, «Set up and manage Routines»,
support.google.com/googlenest/answer/7029585; Amazon, «Create a Routine», amazon.com/gp/help/customer/display.html
?nodeId=G202200080; both read 2026-11-11): a starter (a phrase or a time) and what it does, confirmed before saving.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any

from . import ring_answer
from .routines import NAMES, fold, unnamed

# Said around an order without being part of it.
FILLERS = ("por favor", "porfa", "porfis", "please", "pls", "oye", "hey", "bueno", "pues", "a ver", "eh", "ah", "mm",
           "mmm", "um", "uh", "entonces", "ahora")

NEW_ES = ("crea una rutina", "crear una rutina", "crear rutina", "crea rutina", "creame una rutina", "nueva rutina",
          "una nueva rutina", "una rutina nueva", "rutina nueva", "quiero una rutina", "quiero crear una rutina",
          "quiero hacer una rutina", "quiero una nueva rutina", "quiero una rutina nueva", "quiero crear una nueva rutina",
          "quiero armar una rutina", "quiero guardar una rutina", "quiero agregar una rutina", "crea una nueva rutina",
          "crea una rutina nueva", "haz una rutina", "hazme una rutina", "haz una nueva rutina", "agrega una rutina",
          "anade una rutina", "guarda una rutina", "arma una rutina", "armame una rutina", "configura una rutina",
          "vamos a crear una rutina", "necesito una rutina", "necesito crear una rutina", "ayudame a crear una rutina",
          "quisiera una rutina", "quisiera crear una rutina", "me gustaria crear una rutina", "agregar rutina",
          "agregar una rutina", "anadir una rutina", "hacer una rutina")
NEW_EN = ("new routine", "a new routine", "create a routine", "create routine", "create a new routine", "make a routine",
          "make a new routine", "make me a routine", "add a routine", "add a new routine", "add routine",
          "i want a routine", "i want a new routine", "i want to create a routine", "i want to make a routine",
          "i want to add a routine", "set up a routine", "set up a new routine", "i need a routine",
          "i d like a routine", "i d like to create a routine", "let s create a routine", "let s make a routine",
          "help me create a routine", "help me make a routine")
LIST_ES = ("que rutinas tengo", "cuales rutinas tengo", "cuales son mis rutinas", "mis rutinas", "lista mis rutinas",
           "lista las rutinas", "listame las rutinas", "listame mis rutinas", "muestrame mis rutinas",
           "muestra mis rutinas", "muestrame las rutinas", "dime mis rutinas", "dime que rutinas tengo",
           "dime las rutinas", "dime las rutinas que tengo", "que rutinas hay", "ver mis rutinas", "ver rutinas",
           "que rutinas tengo guardadas", "que rutinas tengo activas", "cuantas rutinas tengo", "tengo rutinas",
           "tengo alguna rutina", "que rutinas guarde", "cuales rutinas hay")
LIST_EN = ("what routines do i have", "which routines do i have", "my routines", "list my routines", "list routines",
           "list the routines", "show my routines", "show me my routines", "show routines", "what are my routines",
           "tell me my routines", "do i have any routines", "do i have routines", "how many routines do i have")
# In front of the routine's name or phrase: «borra la rutina X».
NAMED_ES = {
    "delete": ("borra la rutina", "borrar la rutina", "borra mi rutina", "borra rutina", "borrame la rutina",
               "elimina la rutina", "eliminar la rutina", "elimina mi rutina", "elimina rutina", "quita la rutina",
               "quita mi rutina", "quitar la rutina",
               # RUT11 (REV11 B-4): not wanting it any more is deleting it
               "ya no quiero la rutina", "ya no quiero mi rutina", "no quiero la rutina", "no quiero mas la rutina"),
    "disable": ("desactiva la rutina", "desactivar la rutina", "desactiva mi rutina", "desactiva rutina",
                "apaga la rutina", "apaga mi rutina", "deshabilita la rutina", "pausa la rutina"),
    "enable": ("activa la rutina", "activar la rutina", "activa mi rutina", "activa rutina", "enciende la rutina",
               "habilita la rutina", "reactiva la rutina", "vuelve a activar la rutina", "prende la rutina"),
    "run": ("ejecuta la rutina", "ejecutar la rutina", "ejecuta mi rutina", "ejecuta rutina", "corre la rutina",
            "lanza la rutina", "haz la rutina", "prueba la rutina", "probar la rutina"),
    # RUT11 (REV11 B-4): a routine is changed by voice, step by step, as it was made (CHANGE_PART: the part named)
    "change": ("cambia la rutina", "cambiar la rutina", "cambia mi rutina", "modifica la rutina", "modificar la rutina",
               "modifica mi rutina", "edita la rutina", "editar la rutina", "edita mi rutina", "quiero cambiar la rutina",
               "quiero modificar la rutina", "cambia la hora de la rutina", "cambia la hora de mi rutina",
               "cambia el horario de la rutina", "cambia los dias de la rutina", "cambia la palabra de la rutina",
               "cambia la frase de la rutina", "cambia lo que hace la rutina", "cambia la orden de la rutina",
               "cambia lo que dice la rutina", "cambia el texto de la rutina", "cambia el mensaje de la rutina"),
}
NAMED_EN = {
    "delete": ("delete the routine", "delete routine", "delete my routine", "remove the routine", "remove routine",
               "remove my routine", "erase the routine"),
    "disable": ("disable the routine", "disable routine", "disable my routine", "turn off the routine",
                "turn off routine", "turn off my routine", "pause the routine"),
    "enable": ("enable the routine", "enable routine", "enable my routine", "turn on the routine", "turn on routine",
               "turn on my routine"),
    "run": ("run the routine", "run routine", "run my routine", "start the routine", "try the routine",
            "test the routine"),
    "change": ("change the routine", "change routine", "change my routine", "edit the routine", "edit my routine",
               "modify the routine", "modify my routine", "change the time of the routine", "change the time of my routine",
               "change the days of the routine", "change the word of the routine", "change the phrase of the routine",
               "change the order of the routine", "change the text of the routine", "change the message of the routine"),
}
NAMED_EN["delete"] += ("i don t want the routine", "i don t want my routine", "i no longer want the routine")
# RUT11 (REV11 B-4): the part of a routine a change names, by the words of its order; with none, BAXY asks which.
CHANGE_PART = {"hora": "when", "horario": "when", "dias": "when", "time": "when", "days": "when", "palabra": "phrase",
               "frase": "phrase", "word": "phrase", "phrase": "phrase", "hace": "order", "orden": "order", "order": "order",
               "dice": "say", "texto": "say", "mensaje": "say", "text": "say", "message": "say"}
# The answer to «¿Qué cambio…?»: its words name one part.
WHAT = {"phrase": {"palabra", "frase", "word", "phrase", "nombre"},
        "order": {"hace", "haga", "haces", "orden", "accion", "does", "do", "order", "action"},
        "when": {"hora", "horario", "dias", "time", "days", "cuando", "when", "hour"},
        "say": {"dice", "dices", "digas", "texto", "mensaje", "says", "say", "text", "message", "tell"}}
# RUT11 (REV11 B-4): every routine at once; deleting them all waits for its «sí».
ALL_ES = {
    "delete": ("borra todas mis rutinas", "borra todas las rutinas", "borrar todas las rutinas", "borra mis rutinas",
               "elimina todas mis rutinas", "elimina todas las rutinas", "eliminar todas las rutinas", "elimina mis rutinas",
               "quita todas mis rutinas", "quita todas las rutinas", "ya no quiero ninguna rutina", "no quiero ninguna rutina",
               "ya no quiero mis rutinas"),
    "disable": ("desactiva todas mis rutinas", "desactiva todas las rutinas", "desactivar todas las rutinas",
                "desactiva mis rutinas", "apaga todas mis rutinas", "apaga todas las rutinas", "pausa todas las rutinas",
                "pausa todas mis rutinas"),
    "enable": ("activa todas mis rutinas", "activa todas las rutinas", "activar todas las rutinas", "activa mis rutinas",
               "reactiva todas las rutinas", "reactiva todas mis rutinas", "enciende todas las rutinas"),
}
ALL_EN = {
    "delete": ("delete all my routines", "delete all routines", "delete all the routines", "delete my routines",
               "remove all my routines", "remove all routines", "remove all the routines", "erase all my routines"),
    "disable": ("disable all my routines", "disable all routines", "disable all the routines", "turn off all my routines",
                "turn off all routines", "turn off all the routines", "pause all my routines", "pause all routines"),
    "enable": ("enable all my routines", "enable all routines", "enable all the routines", "turn on all my routines",
               "turn on all routines", "turn on all the routines"),
}
# RUT11 (REV11 B-4): a routine said by a pronoun («bórrala») is the one the last exchange named (named_in); with none
# named they are the model's words, as before.
IT_ES = {
    "delete": ("borrala", "eliminala", "quitala", "borra esa rutina", "borra esta rutina", "elimina esa rutina",
               "elimina esta rutina", "quita esa rutina", "ya no la quiero"),
    "disable": ("desactivala", "desactiva esa rutina", "desactiva esta rutina"),
    "enable": ("activala", "reactivala", "activa esa rutina", "activa esta rutina"),
    "change": ("cambiala", "modificala", "editala", "cambia esa rutina", "cambia esta rutina", "modifica esa rutina"),
}
IT_EN = {
    "delete": ("delete it", "remove it", "delete that routine", "delete this routine", "remove that routine"),
    "disable": ("disable it", "disable that routine", "disable this routine"),
    "enable": ("enable it", "enable that routine", "enable this routine"),
    "change": ("change it", "edit it", "change that routine", "change this routine"),
}
# Said after a name without being part of it: «I don't want the routine X anymore».
AFTER_NAME = ("anymore", "any more")
# Said between the order and the name: «borra la rutina de X», «the routine called X».
OF = ("de", "del", "de la", "de las", "de los", "llamada", "que se llama", "called", "named", "for")
CANCEL = ("cancela", "cancelar", "cancelalo", "cancelala", "cancela eso", "cancela la rutina", "olvidalo", "olvidala",
          "dejalo", "dejala", "dejalo asi", "salir", "sal", "ya no", "ya no quiero", "nada", "para", "basta", "cancel",
          "cancel it", "cancel that", "never mind", "nevermind", "forget it", "exit", "quit", "stop",
          # RUT9 (REV9 H4): the ways out people say that were kept as an answer («no, déjalo» as the order)
          "no dejalo", "no dejala", "no olvidalo", "no cancela", "olvidate", "olvidate de eso", "olvidate de esto",
          "mejor otro dia", "otro dia mejor", "mejor despues", "mejor luego", "en otro momento", "no importa",
          "ya no importa", "dejemoslo", "dejemoslo asi", "dejalo para otro dia", "forget about it", "not now",
          "maybe later", "some other time", "no never mind", "no forget it")
YES = ("si", "si guardala", "si guarda", "guardala", "guarda", "guardalo", "dale", "ok", "okey", "okay", "vale", "claro",
       "si claro", "claro que si", "correcto", "si correcto", "eso", "eso es", "asi es", "exacto", "de acuerdo",
       "esta bien", "hazlo", "adelante", "confirmo", "sip", "bueno", "ya", "sale", "yes", "yeah", "yep", "sure", "save it",
       "save", "yes save it", "do it", "correct", "right", "go ahead", "that s right", "please do")
# REM4 (REV14 A-R1): the yeses of YES that say what creating does («guárdala», "save it"). To the guide's other questions
# («¿Borro tu rutina…?», «¿La cambio?») «guárdala» is «keep it»: there they are no «sí» (Guide._said_yes).
SAVE_YES = ("si guardala", "si guarda", "guardala", "guarda", "guardalo", "save it", "save", "yes save it")
PLAIN_YES = tuple(piece for piece in YES if piece not in SAVE_YES)
NO = ("no", "no gracias", "no la guardes", "no guardes", "mejor no", "nop", "nope", "no thanks", "don t", "don t save it",
      "do not save it", "no no")
# The first words of a reply to «¿La guardo?»: led by one of them, an answer is asked again, never taken as another request.
REPLY_HEADS = frozenset(piece.split()[0] for piece in (*YES, *NO))
# RUT9 (REV9 H6): the words that may come before «cuando (te) diga…» (form 2) run into it: when it starts or a wish. Any
# other lead-in is set apart from it by a comma, a colon or a semicolon («hazme una rutina: cuando…», «mirá, cuando…»);
# run into it («escribe cuando te diga…», «recuerda que cuando te diga…») it is a request of its own, the model's.
LEAD_INS = ("desde hoy", "desde ahora", "desde ahora en adelante", "a partir de ahora", "a partir de hoy",
            "de ahora en adelante", "de hoy en adelante", "quiero que", "necesito que", "quisiera que",
            "me gustaria que", "desde hoy quiero que", "from now on", "from today",
            "from today on", "starting today", "starting now", "i want", "i want that", "i d like", "i would like")
# In front of the answer to «¿Qué palabra vas a decir?».
PHRASE_LEAD = ("la palabra es", "la palabra va a ser", "la palabra sera", "la palabra seria", "la frase es",
               "la frase va a ser", "la frase sera", "voy a decir", "dire", "va a ser", "que sea", "seria", "la palabra",
               "la frase", "the word is", "the phrase is", "the word will be", "i will say", "i ll say",
               "i m going to say", "it s", "it is", "the word", "the phrase")
WORD_KIND = {"palabra", "palabras", "frase", "word", "words", "phrase", "voz", "voice", "primera", "primero", "first"}
TIME_KIND = {"hora", "horario", "time", "reloj", "clock", "segunda", "segundo", "second"}
# Alone, the answer to «¿de la mañana o de la tarde?» and to «¿qué días?».
HALF_ALONE = {"manana": "am", "la manana": "am", "morning": "am", "the morning": "am"}
ALL_DAYS = ("todos", "todas", "siempre", "todos ellos", "all", "all of them", "always", "every one")
MOST_PHRASE_WORDS = 6   # a word of theirs, or a short phrase
LEAST_PHRASE_CHARS = 2  # RUT9 (REV9 H7): «a» or «eh» alone is what the ear writes for a sound after «Baxy»
# RUT9 (REV9 H4): a guide left because the person said something else; the model reads it once, with their words.
LEFT_NOTE = ("[Nota interna, no la escribió la persona: la rutina que BAXY estaba creando con la persona quedó sin "
             "guardar, porque lo que dijo no contestaba su pregunta. Dile en pocas palabras que no se guardó y atiende "
             "lo que dijo.]")
# REM8 (REV16 R-1, REV14 A-R5): a «¿Borro…?» or a change left the same way was told «quedó sin guardar… no se guardó»,
# what the guide that creates says: a falsehood the mind asked for. What was asked, and that it was not done.
LEFT_NOTES = {
    "delete": ("[Nota interna, no la escribió la persona: BAXY le preguntaba si borraba una rutina y lo que dijo no "
               "contestaba su pregunta, así que no se borró nada: sus rutinas siguen como estaban. Dile en pocas palabras "
               "que no se borró y atiende lo que dijo.]"),
    "change": ("[Nota interna, no la escribió la persona: BAXY estaba cambiando una rutina con la persona y lo que dijo no "
               "contestaba su pregunta, así que no se cambió nada: la rutina sigue como estaba. Dile en pocas palabras "
               "que no se cambió y atiende lo que dijo.]"),
    "other": ("[Nota interna, no la escribió la persona: BAXY le preguntaba por una de sus rutinas y lo que dijo no "
              "contestaba su pregunta, así que no se hizo nada con ninguna: siguen como estaban. Dile en pocas palabras "
              "que no se hizo y atiende lo que dijo.]"),
}
# RUT9 (second blind review, REV9 S1): the guide dropped after GUIDE_SILENCE_S with its question still in the
# conversation: a late «sí» would reach the model, which has nothing to save with.
SILENT_NOTE = ("[Nota interna, no la escribió la persona: la rutina que BAXY estaba creando con la persona quedó sin "
               "guardar porque pasó mucho rato sin respuesta. No hay nada guardado ni nada que guardar con un «sí»: si "
               "lo que dice responde a eso, díselo y que vuelva a pedirla.]")
MOST_ORDER = 400        # RoutinesHandler's bound for an order
MOST_SAY = 300

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_WORDS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "sabados": 5, "domingo": 6,
             "domingos": 6, "monday": 0, "mondays": 0, "tuesday": 1, "tuesdays": 1, "wednesday": 2, "wednesdays": 2,
             "thursday": 3, "thursdays": 3, "friday": 4, "fridays": 4, "saturday": 5, "saturdays": 5, "sunday": 6,
             "sundays": 6}
DAILY = ("todos los dias de la semana", "todos los dias", "cada dia", "a diario", "diario", "diariamente", "every day",
         "everyday", "daily", "each day", "every single day")
WEEKDAYS = ("de lunes a viernes", "entre semana", "los dias de semana", "dias de semana", "dias habiles",
            "dias laborales", "dias laborables", "weekdays", "every weekday", "weekday", "on weekdays")
WEEKEND = ("fines de semana", "los fines de semana", "el fin de semana", "fin de semana", "weekends", "the weekend",
           "every weekend")
ONCE = ("una sola vez", "solo una vez", "una vez", "just once", "only once", "once", "one time")
# (words, meridiem): how the hour said beside them is read.
MERIDIEM = ((("de", "la", "manana"), "am"), (("por", "la", "manana"), "am"), (("en", "la", "manana"), "am"),
            (("de", "la", "madrugada"), "am"), (("en", "la", "madrugada"), "am"), (("in", "the", "morning"), "am"),
            (("a", "m"), "am"), (("am",), "am"), (("morning",), "am"), (("madrugada",), "am"),
            (("de", "la", "tarde"), "pm"), (("por", "la", "tarde"), "pm"), (("en", "la", "tarde"), "pm"),
            (("in", "the", "afternoon"), "pm"), (("in", "the", "evening"), "pm"), (("p", "m"), "pm"), (("pm",), "pm"),
            (("afternoon",), "pm"), (("evening",), "pm"), (("tarde",), "pm"),
            (("de", "la", "noche"), "night"), (("por", "la", "noche"), "night"), (("en", "la", "noche"), "night"),
            (("at", "night"), "night"), (("noche",), "night"), (("night",), "night"),
            (("del", "mediodia"), "noon"), (("del", "medio", "dia"), "noon"), (("del", "dia"), "noon"))
DATED = ((("pasado", "manana"), 2), (("day", "after", "tomorrow"), 2), (("manana",), 1), (("tomorrow",), 1),
         (("hoy",), 0), (("today",), 0), (("esta", "noche"), 0), (("esta", "tarde"), 0), (("tonight",), 0))
NOON = ("mediodia", "medio dia", "noon", "midday")
MIDNIGHT = ("medianoche", "media noche", "midnight")
NUMBERS = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
           "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
           "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21,
           "veintiun": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
           "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30, "cuarenta": 40,
           "cincuenta": 50, "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
           "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
           "forty": 40, "fifty": 50}
# «once» is eleven in Spanish and «one time» in English: as a number it is read only where an hour or its minutes go.
TENS = {20, 30, 40, 50}
# What a count of these is: a length of time, not an hour.
SPANS = {"minuto", "minutos", "minute", "minutes", "min", "mins", "segundos", "seconds", "veces", "times", "dias", "days",
         "semanas", "weeks", "meses", "months"}
# Said around a time without being part of it.
LINKS = {"a", "al", "las", "la", "los", "el", "y", "e", "de", "del", "en", "por", "para", "at", "on", "the", "and", "every",
         "each", "todos", "todas", "cada", "que", "sea", "solo", "only", "just", "horas", "hora", "hrs", "hs", "h", "o",
         "clock", "oclock", "punto", "dia", "dias", "of", "in"}


def _words(text: Any) -> list[str]:
    return fold(text).split()


def _span(text: Any) -> tuple[list[str], int]:
    """The turn's folded words without BAXY's name in front and the fillers around it, and how many went in front."""
    words = _words(text)
    fillers = [tuple(f.split()) for f in FILLERS]
    changed, front = True, 0
    while changed and words:
        changed = False
        if words[0] in NAMES and len(words) > 1:
            words, front, changed = words[1:], front + 1, True
        for piece in fillers:
            size = len(piece)
            if len(words) > size and tuple(words[:size]) == piece:
                words, front, changed = words[size:], front + size, True
            if len(words) > size and tuple(words[-size:]) == piece:
                words, changed = words[:-size], True
    return words, front


def _core(text: Any) -> str:
    """The turn folded, without BAXY's name in front and the fillers around it."""
    return " ".join(_span(text)[0])


@dataclass(frozen=True)
class When:
    """What was understood of a time and its days: ``hour`` as said (None: not said), ``meridiem`` the words beside it
    (am, pm, night, noon; None: none), ``fixed`` an hour that needs none («20:30», «08:00», «mediodía»), ``repeat``
    daily, days or once (None: not said), ``days`` of the week (0 Monday) and ``offset`` the day said (0 today,
    1 tomorrow)."""
    hour: int | None = None
    minute: int = 0
    meridiem: str | None = None
    fixed: bool = False
    repeat: str | None = None
    days: tuple[int, ...] = ()
    offset: int | None = None

    def hour24(self) -> int | None:
        """The hour of the day, or None while it is not known which half of the day it is in."""
        hour = self.hour
        if hour is None or not 0 <= hour <= 23:
            return None
        if hour >= 13:
            return hour if self.meridiem in (None, "pm", "night") else None
        if hour == 0:
            return hour if self.meridiem in (None, "am", "night") else None
        if self.meridiem is None:
            return hour if self.fixed else None
        if self.meridiem == "am":
            return hour % 12
        if self.meridiem == "pm":
            return hour % 12 + 12
        if self.meridiem == "night":   # «12 de la noche» is midnight, «1 de la noche» the small hours
            return 0 if hour == 12 else hour if hour <= 5 else hour + 12
        if self.meridiem == "noon":
            return 12 if hour == 12 else hour + 12 if hour <= 3 else None
        return None

    def clock(self) -> str | None:
        hour = self.hour24()
        return None if hour is None else f"{hour:02d}:{self.minute:02d}"

    def merged(self, other: When) -> When:
        """This with what a later answer adds."""
        hour = other.hour is not None
        return replace(
            self, hour=other.hour if hour else self.hour, minute=other.minute if hour else self.minute,
            fixed=other.fixed if hour else self.fixed,
            meridiem=other.meridiem if other.meridiem is not None or hour else self.meridiem,
            repeat=other.repeat or self.repeat, days=other.days if other.repeat else self.days,
            offset=other.offset if other.repeat else self.offset)


_CLOCK = re.compile(r"(?<![\d:])(\d{1,2})\s*[:.]\s*(\d{2})(?![\d:])")
_MERIDIEM_DOTS = re.compile(r"\b([ap])\s?\.\s?m\b\.?", re.IGNORECASE)
_GLUED = re.compile(r"(\d)\s*(am|pm|hs|hrs|h)\b", re.IGNORECASE)


def _time_words(text: str) -> list[str]:
    """The answer's words, folded; a clock written with digits stays one word («10:30»)."""
    lowered = unicodedata.normalize("NFC", str(text or ""))
    lowered = _MERIDIEM_DOTS.sub(lambda m: " " + m.group(1) + "m ", lowered)
    lowered = _GLUED.sub(r"\1 \2", lowered)
    words: list[str] = []
    at = 0
    for match in _CLOCK.finditer(lowered):
        words += _words(lowered[at:match.start()])
        words.append(f"{match.group(1)}:{match.group(2)}")
        at = match.end()
    return words + _words(lowered[at:])


def _number(words: list[str], at: int, most: int) -> tuple[int, int] | None:
    """The number at ``at`` (digits or words, «treinta y cinco», «forty five») up to ``most``, and where it ends."""
    if at >= len(words):
        return None
    word = words[at]
    if re.fullmatch(r"\d{1,2}", word):
        value, end = int(word), at + 1
    elif word in NUMBERS:
        value, end = NUMBERS[word], at + 1
        if value in TENS:
            unit = at + 2 if words[at + 1:at + 2] == ["y"] else at + 1
            if unit < len(words) and words[unit] in NUMBERS and 1 <= NUMBERS[words[unit]] <= 9:
                value, end = value + NUMBERS[words[unit]], unit + 1
    else:
        return None
    return (value, end) if value <= most else None


def _seq(words: list[str], at: int, pieces: tuple[str, ...]) -> int:
    """How many words the longest of ``pieces`` takes at ``at`` (0: none is there)."""
    best = 0
    for piece in pieces:
        said = piece.split()
        if words[at:at + len(said)] == said:
            best = max(best, len(said))
    return best


def spoken(text: str) -> When | None:
    """The time and the days these words say, or None when some of them are not understood (never a guess)."""
    words = _time_words(text)
    while words and words[0] in NAMES:
        words = words[1:]
    hour: int | None = None
    minute, fixed, hours = 0, False, 0
    meridiem: str | None = None
    repeat: str | None = None
    days: list[int] = []
    offset: int | None = None
    at, understood = 0, False
    while at < len(words):
        word = words[at]
        size = _seq(words, at, DAILY)
        if size:
            repeat, at, understood = "daily", at + size, True
            continue
        size = _seq(words, at, WEEKDAYS)
        if size:
            repeat, days, at, understood = "days", [*days, 0, 1, 2, 3, 4], at + size, True
            continue
        size = _seq(words, at, WEEKEND)
        if size:
            repeat, days, at, understood = "days", [*days, 5, 6], at + size, True
            continue
        # «de lunes a jueves», «monday to friday», «monday through friday»
        if (word in DAY_WORDS and words[at + 1:at + 2] in (["a"], ["al"], ["to"], ["through"], ["hasta"])
                and words[at + 2:at + 3] and words[at + 2] in DAY_WORDS):
            first, last = DAY_WORDS[word], DAY_WORDS[words[at + 2]]
            span = [(first + i) % 7 for i in range((last - first) % 7 + 1)]
            repeat, days, at, understood = "days", [*days, *span], at + 3, True
            continue
        if word in DAY_WORDS:
            repeat, days, at, understood = "days", [*days, DAY_WORDS[word]], at + 1, True
            continue
        dated = next(((len(said), days_on) for said, days_on in DATED if tuple(words[at:at + len(said)]) == said), None)
        marked = next(((len(said), half) for said, half in MERIDIEM if tuple(words[at:at + len(said)]) == said), None)
        # «mañana por la mañana», «esta noche»: the day, and the half of it the words after say.
        if marked and marked[0] > 1 or (marked and not dated):
            if meridiem not in (None, marked[1]):
                return None
            meridiem, at, understood = marked[1], at + marked[0], True
            continue
        if dated:
            if offset not in (None, dated[1]):
                return None
            offset, understood = dated[1], True
            if words[at:at + 2] in (["esta", "noche"], ["esta", "tarde"]) or word == "tonight":
                meridiem = "night" if word == "tonight" or words[at + 1] == "noche" else "pm"
            at += dated[0]
            continue
        size = _seq(words, at, NOON) or _seq(words, at, MIDNIGHT)
        if size:
            hours += 1
            hour, minute, fixed = (12 if _seq(words, at, NOON) else 0), 0, True
            at, understood = at + size, True
            continue
        size = _seq(words, at, ONCE)
        # «once» alone after «a las» is eleven: one time only when no hour can go there.
        if size and not (word == "once" and (at > 0 and words[at - 1] in ("las", "a") or words[at + 1:at + 2] and
                                             words[at + 1] in ("de", "y", "menos", "en", "por", "pm", "am", "p"))):
            repeat, at, understood = repeat or "once", at + size, True
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}", word):
            given, minutes = word.split(":")
            if int(given) > 23 or int(minutes) > 59:
                return None
            hours += 1
            hour, minute, fixed = int(given), int(minutes), len(given) == 2 and given.startswith("0")
            at, understood = at + 1, True
            continue
        # English: «half past ten», «quarter to nine», «ten past eight»
        counted = _number(words, at, 59)
        if word in ("half", "quarter") or (counted is not None and words[counted[1]:counted[1] + 1] in (["past"], ["to"])):
            part, link = (30, at + 1) if word == "half" else (15, at + 1) if word == "quarter" else counted  # type: ignore[misc]
            if words[link:link + 1] not in (["past"], ["to"]):
                return None
            base = _number(words, link + 1, 23)
            if base is None:
                return None
            hours += 1
            hour, minute = (base[0], part) if words[link] == "past" else ((base[0] - 1) % 24 or 12, 60 - part)
            at, understood = base[1], True
            continue
        number = _number(words, at, 23)
        if number is not None:
            value, end = number
            if words[end:end + 1] and (words[end] in SPANS or words[end] in ("horas", "hora") and at > 0
                                       and words[at - 1] in ("cada", "en", "dentro", "de", "por", "durante")):
                return None   # «en 10 minutos», «tres veces», «cada 2 horas»: not an hour
            hours += 1
            hour, minute, fixed = value, 0, value >= 13 or value == 0
            if words[end:end + 2] in (["y", "media"], ["y", "cuarto"]):
                minute, end = (30 if words[end + 1] == "media" else 15), end + 2
            elif words[end:end + 2] == ["menos", "cuarto"]:
                hour, minute, end = (12 if value == 1 else (value - 1) % 24), 45, end + 2
            elif words[end:end + 1] == ["menos"] and (part := _number(words, end + 1, 30)) and part[0] >= 1:
                hour, minute, end = (12 if value == 1 else (value - 1) % 24), 60 - part[0], part[1]
            elif words[end:end + 2] == ["en", "punto"]:
                end += 2
            elif words[end:end + 1] in (["y"], ["con"]) and (part := _number(words, end + 1, 59)):
                minute, end = part[0], part[1]
            elif words[end:end + 1] == ["cero"] and (part := _number(words, end + 1, 9)):
                minute, end = part[0], part[1]
            elif (part := _number(words, end, 59)) and words[end] not in ("un", "una", "a", "once") and not (
                    words[part[1]:part[1] + 1] and words[part[1]] in SPANS):
                minute, end = part[0], part[1]
            at, understood = end, True
            continue
        if word in LINKS:
            at += 1
            continue
        return None
    if not understood or hours > 1 or (hour is None and meridiem is None and repeat is None and offset is None):
        return None
    if offset is not None:
        if repeat in ("daily", "days"):
            return None   # «mañana» and «todos los días» at once: which one is not ours to choose
        repeat = "once"
    found = When(hour, minute, meridiem, fixed, repeat, tuple(sorted(set(days))) if repeat == "days" else (), offset)
    if hour is not None and meridiem is not None and found.hour24() is None:
        return None   # «15 de la mañana»
    return found


TEXT = {
    "es": {
        "kind": "¿Con una palabra tuya o a una hora?",
        "kind_again": "No te entendí. Di «con una palabra» o «a una hora»; o «cancela» para dejarlo.",
        "phrase": "¿Qué palabra vas a decir?",
        "phrase_again": "No entendí la palabra. ¿Qué palabra vas a decir?",
        "phrase_long": "Eso es muy largo para decirlo cada vez. Dime una palabra o una frase corta.",
        "phrase_taken": "Ya tienes una rutina con «{phrase}». Dime otra palabra, o «cancela».",
        "phrase_mine": "«{phrase}» ya es una orden mía y no puede ser el nombre de una rutina. Dime otra palabra.",
        "order": "¿Qué quieres que haga cuando la digas?",
        "order_again": "No te entendí. ¿Qué quieres que haga cuando digas «{phrase}»?",
        "order_long": "Esa orden es muy larga para guardarla. Dímela más corta.",
        "when": "¿A qué hora, y qué días?",
        "when_again": "No entendí la hora. Dímela así: «a las ocho de la mañana, todos los días».",
        "hour": "¿A qué hora?",
        "half": "¿A las {clock} de la mañana o de la tarde?",
        "half_one": "¿A la {clock} de la madrugada o de la tarde?",
        "half_twelve": "¿A las {clock} del mediodía o de la noche?",
        "days": "¿Qué días? Puedes decir «todos los días», «de lunes a viernes» o «solo mañana».",
        "say": "¿Qué quieres que te diga?",
        "say_again": "No te entendí. ¿Qué quieres que te diga a esa hora?",
        "say_long": "Ese texto es muy largo. Dímelo más corto.",
        "confirm_word": "Cuando digas «{phrase}»: «{order}». ¿La guardo?",
        "confirm_time": "{when}, te digo: «{say}». ¿La guardo?",
        "confirm_again": "Di «sí» para guardarla o «no» para dejarla. {confirm}",
        "unsure": "No te oí bien. {question}",
        "cancelled": "Listo, lo dejo: no guardé ninguna rutina.",
        "not_saved": "No la guardé.",
        "saved_word": "Guardada. Cuando digas «{phrase}», hago lo que pediste. Ahora no hice nada de eso.",
        "saved_time": ("Guardada. {when} te lo digo, sin alarma; si BAXY está cerrada, te sale un aviso de Windows. La "
                       "primera vez, {first}."),
        "saved_time_plain": "Guardada. {when} te lo digo, sin alarma; si BAXY está cerrada, te sale un aviso de Windows.",
        "saved_once": ("Guardada. Te lo digo {first}, una sola vez y sin alarma; si BAXY está cerrada, te sale un aviso de "
                       "Windows."),
        "duplicate": "No la guardé: ya tienes una rutina activa con «{phrase}».",
        "duplicate_name": "No la guardé: ya tienes una rutina con ese nombre.",
        "full": "No la guardé: ya tienes el máximo de rutinas. Borra una primero.",
        "passed": "No la guardé: esa hora ya pasó.",
        "scheduler": "No la guardé: no pude programarla en Windows.",
        "task_left": ("No la guardé, pero no pude quitar lo que dejé programado en Windows: puede que te lo diga igual. "
                      "«Olvidar todo», en el panel de memoria, lo quita."),
        "none": "No tienes ninguna rutina guardada. Di «nueva rutina» para crear una.",
        "list_one": "Tienes una rutina: {items}.",
        "list": "Tienes {count} rutinas: {items}.",
        "off": " (desactivada)",
        "item_order": "«{phrase}» hace «{order}»",
        "item_steps": "«{phrase}» (por pasos)",
        "item_time": "{when} te digo «{say}»",
        "deleted": "Borré la rutina «{name}».",
        "enabled": "Activé la rutina «{name}».",
        "disabled": "Desactivé la rutina «{name}».",
        "not_found": "No tengo ninguna rutina «{name}». {have}",
        "have": "Tienes: {items}.",
        "have_none": "No tienes rutinas guardadas.",
        "opened": "Vamos a crearla. ",
        "what_word": "¿Qué cambio de «{name}»: la palabra o lo que hace?",
        "what_time": "¿Qué cambio de «{name}»: la hora o lo que te digo?",
        "what_again_word": "No te entendí. Di «la palabra» o «lo que hace»; o «cancela» para dejarlo.",
        "what_again_time": "No te entendí. Di «la hora» o «lo que me dices»; o «cancela» para dejarlo.",
        "confirm_change_word": "«{name}» quedará así: cuando digas «{phrase}»: «{order}». ¿La cambio?",
        "confirm_change_time": "«{name}» quedará así: {when}, te digo: «{say}». ¿La cambio?",
        "cancelled_change": "Listo, lo dejo: no cambié ninguna rutina.",
        "not_changed": "No la cambié.",
        "changed": "Cambié la rutina «{name}»: {item}.",
        "by_steps": ("«{name}» es una rutina por pasos: su palabra se cambia hablando, lo que hace no. Para eso, bórrala y "
                     "créala de nuevo."),
        "which": "¿Cuál de tus rutinas? Tienes: {items}.",
        "which_again": "No tengo esa rutina. ¿Cuál de estas? {items}.",
        "left": "Listo, lo dejo.",
        "confirm_delete_all": "¿Borro tus {count} rutinas: {items}?",
        "confirm_delete_one": "¿Borro tu rutina «{name}»?",
        "kept_all": "No borré nada.",
        "deleted_all": "Borré tus {count} rutinas: {items}.",
        "disabled_all": "Desactivé tus {count} rutinas: {items}.",
        "enabled_all": "Activé tus {count} rutinas: {items}.",
        "none_on": "No tienes ninguna rutina activa.",
        "none_off": "No tienes ninguna rutina desactivada.",
        "order_mine": ("Eso es una orden sobre las rutinas, y una rutina no puede crear, cambiar ni borrar rutinas: "
                       "pídemelo directo cuando quieras. ¿Qué otra cosa quieres que haga cuando digas «{phrase}»?"),
        "phrase_everyday": ("«{phrase}» se dice en cualquier conversación, y como frase de una rutina la harías sin "
                            "querer. Dime otra palabra."),
    },
    "en": {
        "kind": "With a word of yours or at a time?",
        "kind_again": "I didn't get that. Say «with a word» or «at a time»; or «cancel» to leave it.",
        "phrase": "What word will you say?",
        "phrase_again": "I didn't get the word. What word will you say?",
        "phrase_long": "That is too long to say each time. Tell me a word or a short phrase.",
        "phrase_taken": "You already have a routine with «{phrase}». Tell me another word, or «cancel».",
        "phrase_mine": "«{phrase}» is already an order of mine and cannot name a routine. Tell me another word.",
        "order": "What should I do when you say it?",
        "order_again": "I didn't get that. What should I do when you say «{phrase}»?",
        "order_long": "That order is too long to save. Tell me a shorter one.",
        "when": "At what time, and which days?",
        "when_again": "I didn't get the time. Say it like this: «at eight in the morning, every day».",
        "hour": "At what time?",
        "half": "At {clock} in the morning or in the afternoon?",
        "half_one": "At {clock} in the morning or in the afternoon?",
        "half_twelve": "At {clock} noon or at night?",
        "days": "Which days? You can say «every day», «Monday to Friday» or «only tomorrow».",
        "say": "What should I tell you?",
        "say_again": "I didn't get that. What should I tell you at that time?",
        "say_long": "That text is too long. Tell me a shorter one.",
        "confirm_word": "When you say «{phrase}»: «{order}». Shall I save it?",
        "confirm_time": "{when}, I'll tell you: «{say}». Shall I save it?",
        "confirm_again": "Say «yes» to save it or «no» to leave it. {confirm}",
        "unsure": "I didn't hear you well. {question}",
        "cancelled": "Okay, leaving it: I didn't save any routine.",
        "not_saved": "I didn't save it.",
        "saved_word": "Saved. When you say «{phrase}», I'll do what you asked. I haven't done any of it now.",
        "saved_time": ("Saved. {when} I'll tell you, with no alarm; if BAXY is closed, you get a Windows notification "
                       "instead. The first time, {first}."),
        "saved_time_plain": ("Saved. {when} I'll tell you, with no alarm; if BAXY is closed, you get a Windows "
                             "notification instead."),
        "saved_once": ("Saved. I'll tell you {first}, only once and with no alarm; if BAXY is closed, you get a Windows "
                       "notification instead."),
        "duplicate": "I didn't save it: you already have an active routine with «{phrase}».",
        "duplicate_name": "I didn't save it: you already have a routine with that name.",
        "full": "I didn't save it: you already have the most routines there can be. Delete one first.",
        "passed": "I didn't save it: that time has already passed.",
        "scheduler": "I didn't save it: I couldn't schedule it in Windows.",
        "task_left": ("I didn't save it, but I couldn't take off what I had scheduled in Windows: I may say it anyway. "
                      "«Forget everything», in the memory panel, takes it off."),
        "none": "You have no routines saved. Say «new routine» to make one.",
        "list_one": "You have one routine: {items}.",
        "list": "You have {count} routines: {items}.",
        "off": " (off)",
        "item_order": "«{phrase}» does «{order}»",
        "item_steps": "«{phrase}» (by steps)",
        "item_time": "{when} I tell you «{say}»",
        "deleted": "I deleted the routine «{name}».",
        "enabled": "I turned on the routine «{name}».",
        "disabled": "I turned off the routine «{name}».",
        "not_found": "I have no routine «{name}». {have}",
        "have": "You have: {items}.",
        "have_none": "You have no routines saved.",
        "opened": "Let's make it. ",
        "what_word": "What do I change of «{name}»: the word or what it does?",
        "what_time": "What do I change of «{name}»: the time or what I tell you?",
        "what_again_word": "I didn't get that. Say «the word» or «what it does»; or «cancel» to leave it.",
        "what_again_time": "I didn't get that. Say «the time» or «what you tell me»; or «cancel» to leave it.",
        "confirm_change_word": "«{name}» will be: when you say «{phrase}»: «{order}». Shall I change it?",
        "confirm_change_time": "«{name}» will be: {when}, I'll tell you: «{say}». Shall I change it?",
        "cancelled_change": "Okay, leaving it: I didn't change any routine.",
        "not_changed": "I didn't change it.",
        "changed": "I changed the routine «{name}»: {item}.",
        "by_steps": ("«{name}» is a routine of steps: its word can be changed by voice, what it does cannot. For that, "
                     "delete it and make it again."),
        "which": "Which of your routines? You have: {items}.",
        "which_again": "I have no such routine. Which of these? {items}.",
        "left": "Okay, leaving it.",
        "confirm_delete_all": "Shall I delete your {count} routines: {items}?",
        "confirm_delete_one": "Shall I delete your routine «{name}»?",
        "kept_all": "I didn't delete anything.",
        "deleted_all": "I deleted your {count} routines: {items}.",
        "disabled_all": "I turned off your {count} routines: {items}.",
        "enabled_all": "I turned on your {count} routines: {items}.",
        "none_on": "You have no routine on.",
        "none_off": "You have no routine off.",
        "order_mine": ("That is an order about the routines, and a routine cannot make, change or delete routines: ask me "
                       "directly whenever you want. What else should I do when you say «{phrase}»?"),
        "phrase_everyday": ("«{phrase}» is said in any conversation, and as a routine's phrase you would run it without "
                            "meaning to. Tell me another word."),
    },
}
DAY_NAMES = {"es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"),
             "en": ("Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays")}


def lang_of(lang: Any) -> str:
    return "en" if str(lang or "").lower().startswith("en") else "es"


def said_clock(clock: str, lang: str) -> str:
    """«20:30» as BAXY says it, with the half of the day in words so a wrong one is heard: «8:30 de la noche»."""
    hour, minute = int(clock[:2]), clock[3:5]
    if lang == "en":
        return f"{hour % 12 or 12}:{minute} {'AM' if hour < 12 else 'PM'}"
    half = ("de la noche" if hour == 0 or hour >= 20 else "de la madrugada" if hour <= 5 else "de la mañana"
            if hour <= 11 else ("del mediodía" if minute == "00" else "de la tarde") if hour == 12 else "de la tarde")
    return f"{hour % 12 or 12}:{minute} {half}"


def _listed(items: list[str], lang: str) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + (" and " if lang == "en" else " y ") + items[-1]


def said_when(clock: str, repeat: str, days: Any, offset: int | None, lang: str) -> str:
    """When a routine at a time speaks, as BAXY says it back: «Todos los días a las 8:00 de la mañana»."""
    told = said_clock(clock, lang)
    at = f"at {told}" if lang == "en" else f"{'a la' if told.startswith('1:') else 'a las'} {told}"
    index = [DAYS.index(day) if day in DAYS else day for day in (days or [])]
    index = [day for day in index if isinstance(day, int) and 0 <= day <= 6]
    if repeat == "daily" or (repeat == "days" and len(set(index)) == 7):
        return f"Every day {at}" if lang == "en" else f"Todos los días {at}"
    if repeat == "days" and index:
        if sorted(set(index)) == [0, 1, 2, 3, 4]:
            return f"Monday to Friday {at}" if lang == "en" else f"De lunes a viernes {at}"
        names = _listed([DAY_NAMES[lang][day] for day in sorted(set(index))], lang)
        return f"On {names} {at}" if lang == "en" else f"Los {names} {at}"
    if offset == 1:
        return f"Tomorrow {at}" if lang == "en" else f"Mañana {at}"
    if offset == 0:
        return f"Today {at}" if lang == "en" else f"Hoy {at}"
    if offset == 2:
        return f"The day after tomorrow {at}" if lang == "en" else f"Pasado mañana {at}"
    return f"Once, {at}" if lang == "en" else f"Una vez, {at}"


def _plain(text: Any) -> str:
    """The person's words as they are kept: one line, without the quotes or the signs around them."""
    return " ".join(str(text or "").split()).strip(" \t«»\"“”'‘’¡!¿?.,;:").strip()


def _kept(text: Any) -> str:
    """An order or a text to say as it is kept: the person's words, whole, on one line."""
    return " ".join(str(text or "").split()).strip(" \t«»\"“”")


def _is(text: str, pieces: tuple[str, ...]) -> bool:
    return _core(text) in pieces


def _within(words: list[str], pieces: tuple[str, ...]) -> bool:
    """Whether one of ``pieces`` is in these words, whole words in a row («muy bien guardala» has «guardala»)."""
    return any(words[at:at + len(piece.split())] == piece.split() for piece in pieces for at in range(len(words)))


def mine(phrase: str) -> bool:
    """Words that already are an order to BAXY itself: they cannot be a routine's phrase."""
    core = _core(phrase)
    fixed = (*NEW_ES, *NEW_EN, *LIST_ES, *LIST_EN, *CANCEL, *YES, *NO,
             *(piece for pieces in (*ALL_ES.values(), *ALL_EN.values(), *IT_ES.values(), *IT_EN.values())
               for piece in pieces))
    named = [lead for leads in (*NAMED_ES.values(), *NAMED_EN.values()) for lead in leads]
    return (not core or core in fixed or any(core == lead or core.startswith(lead + " ") for lead in named)
            or ring_answer.heard(phrase) is not None)


# RUT11 (REV11 B-S1, the leader's decision): the plain yeses the App took, alone, as a «sí» to its question until SIS3
# (mind.PLAIN_YES and YES_SOFTENERS, int33-pre3; SIS3 reads that «sí» with the model and took the list out of the mind).
# Moved here whole, the same words, for the one use left: a routine's phrase cannot be one (everyday).
EVERYDAY_YES = ("si", "sip", "ya", "dale", "ok", "okay", "okey", "oki", "vale", "va", "venga", "claro", "claro que si",
                "obvio", "obviamente", "hagale", "hagalo", "hazlo", "hacelo", "dele", "de una", "por supuesto",
                "adelante", "bueno", "listo", "perfecto", "correcto", "exacto", "afirmativo", "de acuerdo", "andale",
                "orale", "sale", "simon", "yes", "yep", "yeah", "sure", "go ahead", "do it", "of course")
EVERYDAY_SOFTENERS = ("po", "pues", "porfa", "por favor", "please")
_EVERY_YES, _EVERY_SOFT = ("(?:" + "|".join(r"\s+".join(map(re.escape, p.split())) for p in phrases) + ")"
                           for phrases in (EVERYDAY_YES, EVERYDAY_SOFTENERS))
_EVERYDAY = re.compile(rf"\W*{_EVERY_YES}(?:\W+(?:{_EVERY_YES}|{_EVERY_SOFT}))*\W*")


CLITIC = r"[ae](?:lo|la|los|las)?"   # «bórrala», «cámbialo», «bórralas», «borra»: the verb said back, its object after it
OBJECT_EN = ("it", "them", "that")


def _yes_said(text: str, verb: str = "", lang: str = "es", every: bool = False) -> bool:
    """REM4 (REV14 A-R1): a «sí» to a question that does not create: made only of plain yeses (PLAIN_YES and the App's
    EVERYDAY_YES, with their softeners), the verb of BAXY's own question said back with its object («¿Borro…?» →
    «bórrala», "Shall I delete…?" → "delete it"; ``verb`` its Spanish stem or its English word) and, for several
    routines, «todas» (ALL_DAYS). Any other word («guárdala», «desactívalas», «la otra») is no such «sí»: BAXY asks again
    (RUT12's _yes_said, leader's proposal in REV14, here without rut11's model path)."""
    words = _core(text).split()
    yeses = sorted({tuple(piece.split()) for piece in (*PLAIN_YES, *EVERYDAY_YES)}, key=len, reverse=True)
    others = sorted({tuple(piece.split()) for piece in (*EVERYDAY_SOFTENERS, *(ALL_DAYS if every else ()))},
                    key=len, reverse=True)
    at, said = 0, False
    while at < len(words):
        size = next((len(piece) for piece in yeses if tuple(words[at:at + len(piece)]) == piece), 0)
        if not size and verb and (words[at] == verb if lang == "en"
                                  else re.fullmatch(re.escape(verb) + CLITIC, words[at]) is not None):
            size = 1 + (lang == "en" and at + 1 < len(words) and words[at + 1] in OBJECT_EN)
        said = said or size > 0
        if not size:
            size = next((len(piece) for piece in others if tuple(words[at:at + len(piece)]) == piece), 0)
        if not size:
            return False
        at += size
    return said


def everyday(phrase: str) -> bool:
    """RUT11 (REV11 B-S1, the leader's decision): plain yeses (EVERYDAY_YES with its softeners: «por supuesto», «sí
    hazlo», «de acuerdo»): said in any conversation, as a routine's phrase they would run it with no intention."""
    core = unnamed(phrase)
    return bool(core) and _EVERYDAY.fullmatch(core) is not None


def about_routines(order: str) -> bool:
    """RUT11 (REV11 B-5): an order that is itself one of the fixed orders about the routines («borra la rutina X», «crea
    una rutina», «qué rutinas tengo»): said by a routine's phrase it goes to the model, which cannot do it (it only
    opens the guide of a new one), so it is not kept as what a routine does."""
    return heard(order, whole=True) is not None


def not_a_phrase(text: str, lang: str = "es") -> bool:
    """REM5 (VIVO15): words that by their form are no routine's phrase: a question («?» or «¿») or a routine said in
    one breath with its order («cuando te diga X, haz Y»: «cuando te diga X» alone answers the question). A long answer or a closed order alone
    («borra la rutina») is still asked again with its reason the first time (RUT9); a second one refused leaves."""
    said = str(text or "")
    if "?" in said or "¿" in said:
        return True
    ordered = heard(said, lang)
    return ordered is not None and ordered.guide is not None and bool(ordered.guide.order)


def thin(phrase: str) -> bool:
    """RUT9 (REV9 H2, H7): a phrase nothing could fire or anything would: BAXY's name alone (it is taken off every
    turn), fewer than LEAST_PHRASE_CHARS letters or digits, or a filler alone («eh», «bueno»)."""
    core = unnamed(phrase)
    return len(core.replace(" ", "")) < LEAST_PHRASE_CHARS or core in FILLERS


def _taken(phrase: str, routines: Any, but: str = "") -> bool:
    folded = unnamed(phrase)
    return any(isinstance(r, dict) and r.get("active") is not False and isinstance(r.get("trigger"), dict)
               and unnamed(r["trigger"].get("phrase")) == folded and not (but and _named(r) == but)
               for r in routines or [])


def _keys(routine: dict[str, Any]) -> set[str]:
    """How a routine is named: its name, its phrase and its clock, folded."""
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    return {unnamed(routine.get("name")), unnamed(trigger.get("phrase")), fold(trigger.get("at"))} - {""}


def by_name(name: str, routine: dict[str, Any]) -> bool:
    """REM2 (REV13 B-1): whether the name said is the routine's own name or phrase, word for word once folded: what
    lets an order act on it at once. Found any other way (by what it says or does, by a time), BAXY asks first."""
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    said = unnamed(name)
    return bool(said) and said in {unnamed(routine.get("name")), unnamed(trigger.get("phrase"))}


def find(name: str, routines: Any) -> dict[str, Any] | None:
    """RUT11: the routine a name says, as RoutinesHandler finds it: its own name, phrase or clock first; the clock
    without its leading zero after, and only among the ones at a time («9:55» is «09:55»)."""
    said = unnamed(name)
    kept = [r for r in routines or [] if isinstance(r, dict)]
    # REM4 (REV14 A-R2): over the whole list, its own name first, then its phrase, then its clock, as RoutinesHandler
    # (NamedBy): in one pass «07:00», the name of a routine with none of its own, was «despertar» at that clock.
    for part in ("name", "phrase", "at"):
        found = next((r for r in kept if said and _key(r, part) == said), None)
        if found is not None:
            return found
    return next((r for r in kept if re.fullmatch(r"0\d:\d\d", str((r.get("trigger") or {}).get("at") or ""))
                 and fold(str(r["trigger"]["at"])[1:]) == said), None)


def _key(routine: dict[str, Any], part: str) -> str:
    """One of a routine's names, folded: ``part`` name, phrase or at (its clock)."""
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    return unnamed(routine.get("name")) if part == "name" else unnamed(trigger.get("phrase")) if part == "phrase" \
        else fold(trigger.get("at"))


def answering(name: str, routines: Any) -> list[dict[str, Any]]:
    """REM4 (REV14 A-R2): every routine a name said answers to, by its name, its phrase or its clock (with or without
    its leading zero): two or more, and BAXY asks which before doing anything («despertar» at 07:00 and another named
    «07:00» both answer to «07:00»)."""
    said = unnamed(name)

    def clocks(routine: dict[str, Any]) -> set[str]:
        told = (str(routine.get("name") or ""), str((routine.get("trigger") or {}).get("at") or ""))
        return {fold(clock[1:]) for clock in told if re.fullmatch(r"0\d:\d\d", clock)}

    return [r for r in routines or [] if isinstance(r, dict) and isinstance(r.get("trigger") or {}, dict)
            and said and (said in _keys(r) or said in clocks(r))]


def named_in(said: str, answered: str, routines: Any) -> list[dict[str, Any]]:
    """RUT11 (REV11 B-4): the routines the last exchange named, for «bórrala»: in BAXY's last words, a routine's name,
    phrase or clock between «» (or its clock, as BAXY's list says it); in the person's last words, one of them as whole
    words beside «rutina»/«routine»."""
    quoted = {unnamed(piece) for piece in re.findall(r"«([^»]+)»", str(answered or ""))}
    told = fold(answered).split()
    words = fold(said).split()
    asked = any(word in ("rutina", "rutinas", "routine", "routines") for word in words)

    def clocks(routine: dict[str, Any]) -> tuple[str, ...]:
        at = str((routine.get("trigger") or {}).get("at") or "") if isinstance(routine.get("trigger"), dict) else ""
        return (fold(at), fold(at[1:])) if re.fullmatch(r"\d{2}:\d{2}", at) else ()

    return [r for r in routines or [] if isinstance(r, dict)
            and (_keys(r) & quoted or _within(told, clocks(r)) or (asked and _within(words, tuple(_keys(r)))))]


@dataclass
class Guide:
    """The routine being made: the question BAXY asked last (``step``) and what the person answered so far."""
    lang: str = "es"
    step: str = "kind"      # kind, phrase, order, when, say, confirm; RUT11: what, which, confirm_all
    kind: str | None = None  # word, time
    phrase: str = ""
    order: str = ""
    say: str = ""
    when: When = field(default_factory=When)
    misses: int = 0         # answers in a row that answered nothing of the question (RUT9, REV9 H4)
    refused: bool = False   # REM5: the last answer to «¿Qué palabra…?» was a word said and refused, not one unheard
    taken: bool = False     # REM6: and that word is the phrase of an active routine of theirs
    # RUT11 (REV11 B-4): ``mode`` create, change (the routine ``target``, its ``part`` phrase, order, when or say), all
    # (``act`` on every routine of ``targets``, after its «sí») or which (``act`` on the one of ``targets`` they name).
    mode: str = "create"
    target: str = ""
    part: str = ""
    act: str = ""
    # REM6 (REV15 B-2): (name, id) of the routines it asks about, so the call after their «sí» names the one asked by its
    # id: by name, one gone meanwhile left another answering to it (a phrase, a clock), and that one was touched.
    ids: tuple[tuple[str, str], ...] = ()
    targets: tuple[str, ...] = ()
    steps_only: bool = False

    def _state(self) -> tuple[Any, ...]:
        return self.step, self.kind, self.phrase, self.order, self.say, self.when, self.part, self.mode

    @classmethod
    def changing(cls, routine: dict[str, Any], lang: str, part: str = "") -> Guide:
        """RUT11 (REV11 B-4): the change of a routine kept, step by step as it was made: what it is now, and the step
        of the part to change (asked first when none was said or it is not one of its kind)."""
        trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
        guide = cls(lang=lang, mode="change", target=_named(routine), ids=keyed([routine]))
        clock = str(trigger.get("at") or "")
        if re.fullmatch(r"\d{2}:\d{2}", clock):
            days = tuple(DAYS.index(day) for day in trigger.get("days") or [] if day in DAYS)
            guide.kind, guide.when = "time", When(hour=int(clock[:2]), minute=int(clock[3:]), fixed=True,
                                                 repeat=str(trigger.get("repeat") or "once"), days=days)
            guide.say = " ".join(str(step.get("say")) for step in routine.get("steps") or []
                                 if isinstance(step, dict) and step.get("say"))
        else:
            guide.kind, guide.phrase = "word", str(trigger.get("phrase") or "").strip()
            guide.order = str(routine.get("order") or "").strip()
            guide.steps_only = not guide.order
        guide._to(part if part else "phrase" if guide.steps_only else "")
        return guide

    def _to(self, part: str) -> None:
        """The change goes to the step of that part; one not of its kind (or none) asks which."""
        if part == "order" and self.steps_only:
            self.part, self.step = "order", "steps_only"
            return
        if part not in (("phrase", "order") if self.kind == "word" else ("when", "say")):
            self.part, self.step = "", "what"
            return
        self.part, self.step = part, part
        if part == "when":
            self.when = When(repeat=self.when.repeat, days=self.when.days)   # the hour asked again, its days kept

    def leaves(self, text: str, routines: Any = None, today: _dt.date | None = None) -> bool:
        """RUT9 (REV9 H4): whether these words leave the guide unsaved and go on as a turn of their own, so the guide
        does not swallow what the person says next. At «¿La guardo?», words that are neither its «sí» or «no» nor a
        short reply to it (two words at most, led by one of YES or NO, or with one of them inside: «sí, pero…», «muy
        bien, guárdala» are asked again); at any other step, a second answer in a row that answers nothing of its
        question, never a time understood («a las 8» said again). «cancela» and its kind are answer's."""
        if _is(text, CANCEL) or (self.step == "when" and spoken(text) is not None):
            return False
        if self.step == "phrase" and not_a_phrase(text, self.lang):
            # REM5 (VIVO15): by their form no phrase (a question, a routine said in one breath)
            return True
        trial = replace(self)
        _, _, ended = trial._answer(text, routines, False, today)
        if ended or trial._state() != self._state():
            return False
        if self.step in ("confirm", "confirm_all"):
            words = _core(text).split()
            return len(words) > 2 and words[0] not in REPLY_HEADS and not _within(words, (*YES, *NO))
        if self.step == "phrase" and trial.taken:
            # REM6 (REV15 B-1): the phrase of an active routine of theirs is said taken, never left with: let go, the
            # turn reached routines.ordered and ran what nobody asked (they were saying the new routine's phrase).
            return False
        if self.step == "phrase":
            # REM5 (VIVO15): after a word refused («sí», «para»), the next two orders were taken as «otra palabra»
            # («Cuando te diga para…» → «Eso es muy largo…», «¿Qué rutinas tengo?» → «ya es una orden mía»). A second
            # answer refused in a row leaves the guide (those no phrase by their form left above), and the model reads
            # that it was not saved (LEFT_NOTE).
            return self.misses >= 1 and self.refused
        # where an answer is a choice or a time
        return self.misses >= 1 and self.step in ("kind", "when", "what", "which")

    def left_note(self) -> str:
        """REM8 (REV16 R-1): what the model reads when the person's words left this guide: by what it was doing."""
        if self.mode == "create":
            return LEFT_NOTE
        act = "change" if self.mode == "change" else self.act
        return LEFT_NOTES.get(act, LEFT_NOTES["other"])

    def id_of(self, name: str) -> str:
        """REM6 (REV15 B-2): the id of the routine asked about by this name (the name itself if it had none)."""
        return next((key for named, key in self.ids if named == name and key), name)

    def name_of(self, key: str) -> str:
        """REM6: the name it was asked by, for the routine of this id (what BAXY says, never the id)."""
        return next((named for named, kept in self.ids if kept == key), key)

    def _t(self, key: str, **values: Any) -> str:
        return TEXT[self.lang][key].format(**values)

    def question(self) -> str:
        """What BAXY asks at this step."""
        if self.step == "when":
            if self.when.hour is None:
                return self._t("when") if self.when.repeat is None else self._t("hour")
            if self.when.clock() is None:
                clock = f"{self.when.hour}:{self.when.minute:02d}"
                return self._t("half_one" if self.when.hour == 1 else "half_twelve" if self.when.hour == 12 else "half",
                               clock=clock)
            return self._t("days")
        if self.step == "confirm":
            change = "_change" if self.mode == "change" else ""
            if self.kind == "word":
                return self._t("confirm" + change + "_word", phrase=self.phrase, order=self.order, name=self.target)
            return self._t("confirm" + change + "_time", say=self.say, name=self.target, when=said_when(
                self.when.clock() or "", self.when.repeat or "once", self.when.days, self.when.offset, self.lang))
        if self.step == "what":
            return self._t("what_word" if self.kind == "word" else "what_time", name=self.target)
        if self.step == "which":
            return self._t("which", items=self._names())
        if self.step == "confirm_all":
            if len(self.targets) == 1:
                return self._t("confirm_delete_one", name=self.targets[0])
            return self._t("confirm_delete_all", count=len(self.targets), items=self._names())
        if self.step == "steps_only":
            return self._t("by_steps", name=self.target)
        if self.step == "order" and self.mode == "change":
            return self._t("order_again", phrase=self.phrase).split(". ", 1)[-1]
        return self._t(self.step)

    def _names(self) -> str:
        return _listed([f"«{name}»" for name in self.targets], self.lang)

    def view(self) -> dict[str, Any]:
        """The step in progress, for the panel: what is asked and what is already answered."""
        timed = self.when.clock() is not None and self.when.repeat is not None
        return {"step": self.step, "kind": self.kind, "question": self.question(), "phrase": self.phrase or None,
                "order": self.order or None, "say": self.say or None,
                "when": said_when(self.when.clock() or "", self.when.repeat or "once", self.when.days,
                                  self.when.offset, self.lang) if timed else None}

    def _after_when(self) -> str:
        if self.when.clock() is None or self.when.repeat is None:
            return self.question()
        self.step = "confirm" if self.say else "say"
        return self.question()

    def answer(self, text: str, routines: Any = None, unsure: bool = False,
               today: _dt.date | None = None) -> tuple[str, dict[str, Any] | None, bool]:
        """The person's words as the answer to the step's question: (what BAXY says, the baxy.routines create to
        propose or None, whether the guide ended). ``today`` is the clock's date, for a day said («mañana»)."""
        before = self._state()
        said, arguments, ended = self._answer(text, routines, unsure, today)
        self.misses = 0 if ended or unsure or self._state() != before else self.misses + 1
        return said, arguments, ended

    def _answer(self, text: str, routines: Any, unsure: bool,
                today: _dt.date | None) -> tuple[str, dict[str, Any] | None, bool]:
        if _is(text, CANCEL):
            left = {"change": "cancelled_change", "all": "kept_all", "which": "left"}.get(self.mode, "cancelled")
            return self._t(left), None, True
        if unsure:
            return self._t("unsure", question=self.question()), None, False
        if self.step == "what":
            words = set(_words(text))
            parts = [part for part, said in WHAT.items() if words & said
                     and part in (("phrase", "order") if self.kind == "word" else ("when", "say"))]
            if len(parts) != 1:
                return self._t("what_again_word" if self.kind == "word" else "what_again_time"), None, False
            self._to(parts[0])
            return self.question(), None, self.step == "steps_only"
        if self.step == "which":
            found = find(text, routines)
            if found is None or _named(found) not in self.targets:
                found = next((r for r in routines or [] if isinstance(r, dict) and _named(r) in self.targets
                              and _keys(r) & {_core(text)}), None)
            if found is None:
                return self._t("which_again", items=self._names()), None, False
            if self.act == "change":
                changed = Guide.changing(found, self.lang)
                for name in ("mode", "target", "part", "step", "kind", "phrase", "order", "say", "when", "steps_only"):
                    setattr(self, name, getattr(changed, name))
                return self.question(), None, self.step == "steps_only"
            if self.act == "delete":
                # REM2 (REV13 B-2): «¿Cuál de tus rutinas?» never said what would be done to it: the one chosen to
                # delete is asked by its name («¿Borro tu rutina «X»?») and only their «sí» deletes it. INT33F: without
                # rut11's model path only «bórrala» with several named comes here; turning one off or on is undone.
                self.step, self.mode, self.targets, self.ids = "confirm_all", "all", (_named(found),), keyed([found])
                return self.question(), None, False
            return "", {"action": self.act, "name": _named(found)}, True   # this turn, the routine in the list now
        if self.step == "confirm_all":
            if self._said_yes(text):
                return "", {"action": self.act, "name": self.id_of(self.targets[0])}, True
            words = _core(text).split()
            if _is(text, NO) or (words[:1] == ["no"] and not _within(words[1:], self._yeses())):
                return self._t("kept_all"), None, True
            return self._t("confirm_again", confirm=self.question()).replace("guardarla", "borrarlas").replace(
                "dejarla", "dejarlas").replace("save it", "delete them").replace("leave it", "leave them"), None, False
        if self.step == "kind":
            words = set(_words(text))
            timed = spoken(text) if not words & (WORD_KIND | TIME_KIND) else None
            if words & WORD_KIND and not words & TIME_KIND:
                self.kind, self.step = "word", "phrase"
            elif words & TIME_KIND and not words & WORD_KIND:
                self.kind, self.step = "time", "when"
            elif timed is not None and (timed.hour is not None or timed.repeat is not None):
                self.kind, self.step, self.when = "time", "when", timed
                return self._after_when(), None, False
            else:
                return self._t("kind_again"), None, False
            return self.question(), None, False
        if self.step == "phrase":
            phrase = _plain(text)
            words = _words(phrase)
            while words and words[0] in NAMES:
                words = words[1:]
            for lead in sorted(PHRASE_LEAD, key=len, reverse=True):
                said = lead.split()
                if len(words) > len(said) and words[:len(said)] == said:
                    words = words[len(said):]
                    break
            if len(words) != len(_words(phrase)):   # a lead-in went: the words left, as they were written
                phrase = " ".join(re.findall(r"[^\W_]+", phrase)[-len(words):]) if words else ""
            self.refused = bool(words) and not thin(phrase)
            self.taken = self.refused and _taken(phrase, routines, but=self.target)
            if not self.refused:
                return self._t("phrase_again"), None, False
            if len(words) > MOST_PHRASE_WORDS:
                return self._t("phrase_long"), None, False
            if mine(phrase):
                return self._t("phrase_mine", phrase=phrase), None, False
            if everyday(phrase):
                return self._t("phrase_everyday", phrase=phrase), None, False
            if _taken(phrase, routines, but=self.target):
                return self._t("phrase_taken", phrase=phrase), None, False
            # RUT11: a change, or a one-breath phrase whose order was already said, goes on to its «sí»
            self.phrase, self.step = phrase, "confirm" if self.mode == "change" or self.order else "order"
            return self.question(), None, False
        if self.step == "order":
            order = _kept(text)
            if not fold(order):
                return self._t("order_again", phrase=self.phrase), None, False
            if len(order) > MOST_ORDER:
                return self._t("order_long"), None, False
            if about_routines(order):
                return self._t("order_mine", phrase=self.phrase), None, False
            self.order, self.step = order, "confirm"
            return self.question(), None, False
        if self.step == "when":
            given = spoken(text)
            core = _core(text)
            if self.when.hour is not None and self.when.clock() is None and core in HALF_ALONE:
                given = When(meridiem=HALF_ALONE[core])   # «mañana» here is the morning, not tomorrow
            elif self.when.clock() is not None and self.when.repeat is None and core in ALL_DAYS:
                given = When(repeat="daily")
            if given is None:
                return self._t("when_again") if self.when.hour is None else self.question(), None, False
            self.when = self.when.merged(given)
            return self._after_when(), None, False
        if self.step == "say":
            say = _kept(text)
            if not fold(say):
                return self._t("say_again"), None, False
            if len(say) > MOST_SAY:
                return self._t("say_long"), None, False
            self.say, self.step = say, "confirm"
            return self.question(), None, False
        if self._said_yes(text):
            return "", self.arguments(today), True
        words = _core(text).split()
        if _is(text, NO) or (words[:1] == ["no"] and not _within(words[1:], self._yeses())):
            # «no, mejor cambia la palabra»: led by its «no», it is not saved
            return self._t("not_changed" if self.mode == "change" else "not_saved"), None, True
        again = self._t("confirm_again", confirm=self.question())
        if self.mode == "change":
            again = again.replace("guardarla", "cambiarla").replace("save it", "change it")
        return again, None, False

    def _yeses(self) -> tuple[str, ...]:
        return YES if self.mode == "create" else PLAIN_YES

    def _said_yes(self, text: str) -> bool:
        """REM4 (REV14 A-R1): the «sí» to this question: YES to «¿La guardo?»; to «¿Borro…?» and «¿La cambio?» only a
        plain one or its own verb said back (_yes_said), never «guárdala» (keep it) or another act («desactívalas»)."""
        if self.mode == "create":
            return _is(text, YES)
        return _yes_said(text, self._verb(), self.lang, every=len(self.targets) > 1)

    def _verb(self) -> str:
        """REM4 (RUT12's): the verb of BAXY's own question: its Spanish stem («¿Borro…?» → «borr», «¿La cambio?» →
        «cambi») or its English word («Shall I delete…?» → «delete»), or nothing."""
        asked = self.question()
        if self.lang == "en":
            verb = re.findall(r"\bshall i ([a-z]+)", fold(asked))
            return verb[-1] if verb else ""
        verb = re.findall(r"¿\s*(?:(?:la|lo|las|los)\s+)?([^\W\d_]+)", asked, flags=re.IGNORECASE)
        word = fold(verb[-1]) if verb else ""
        return word[:-1] if word.endswith("o") and len(word) > 3 else ""

    def arguments(self, today: _dt.date | None = None) -> dict[str, Any]:
        """baxy.routines create for what was answered; RUT11: change of the part answered, by the routine's name."""
        if self.mode == "change":
            if self.part in ("phrase", "order"):
                return {"action": "change", "name": self.id_of(self.target), self.part: getattr(self, self.part)}
            if self.part == "say":
                return {"action": "change", "name": self.id_of(self.target), "steps": ["say: " + self.say]}
            timed = self._timed(today)
            del timed["steps"]
            return {"action": "change", "name": self.id_of(self.target), **timed}
        if self.kind == "word":
            return {"action": "create", "phrase": self.phrase, "order": self.order}
        return {"action": "create", **self._timed(today)}

    def _timed(self, today: _dt.date | None) -> dict[str, Any]:
        repeat = self.when.repeat or "once"
        at = self.when.clock()
        if repeat == "once" and self.when.offset is not None and today is not None:
            # A day said is that date; with none said the store takes the next time that clock comes.
            at = f"{(today + _dt.timedelta(days=self.when.offset)).isoformat()}T{at}"
        return {"at": at, "repeat": repeat,
                **({"days": [DAYS[day] for day in self.when.days]} if repeat == "days" else {}),
                "steps": ["say: " + self.say]}


@dataclass(frozen=True)
class Order:
    """A fixed order about the routines: ``action`` new, list, delete, enable, disable or run; ``name`` for the named
    ones; ``guide`` for new, where it starts (a one-breath phrase starts further on)."""
    action: str
    lang: str
    name: str = ""
    guide: Guide | None = None
    # RUT11 (REV11 B-4): ``part`` the part a change named; ``it`` the routine was not named («bórrala», «borra la
    # rutina»): the last exchange says which (Mind._routine_meant), or, with none, ``fallback`` «list» (BAXY says the
    # ones there are) or «model» (the words are the model's); ``said`` what BAXY says first instead of its question.
    part: str = ""
    it: bool = False
    fallback: str = "list"
    said: str = ""


_ASIDE = r"(?:(?:oye|hey|ok|bueno|por favor|porfa|please|che)\W+)*"
_LEAD = r"^\W*" + _ASIDE + r"(?:(?:baxy|baxi)\W+)?" + _ASIDE
MOST_BEFORE = 4   # words that may come before «cuando diga» («a partir de ahora, …», «quiero que …»); more: another request
_BEFORE = r"((?:[^\W_]+\W+){0,%d}?)" % MOST_BEFORE
_WHEN_SAID = (
    (re.compile(_LEAD + _BEFORE + r"(?:cuando|cada vez que|siempre que)\s+(?:yo\s+)?(?:(?:te|le)\s+)?(diga|digo)\b\s*(.*)$",
                re.IGNORECASE | re.DOTALL), "es"),
    (re.compile(_LEAD + _BEFORE + r"(?:when|whenever|every time|each time|any ?time)\s+i\s+(say)\b\s*(.*)$",
                re.IGNORECASE | re.DOTALL), "en"),
)
LEAST_AFTER = 3   # with words before it, what follows must carry a word and its order («¿qué pasa cuando te diga X?»: no)
MOST_SAID_WORDS = 3   # the word of a one-breath phrase: longer, it is asked for (or it was no word: «cuando te diga la calle…»)
# A short question hung at the end («…, ¿vale?», "…, ok?"): it asks nothing about the routine, and it is not part of the order.
_TAG = re.compile(r"(?:\s*[,;.]\s*¿?\s*|\s*¿\s*)(?:[^\W_]+\s+)?[^\W_]+\s*\?\s*$")
_SAID_WORD = re.compile(r"^(?:la palabra|la frase|the word|the phrase)\s+", re.IGNORECASE)
_QUOTED = re.compile(r"^[«\"“‘']\s*([^»\"”’']+?)\s*[»\"”’']\s*[,:;.]?\s*(.+)$", re.DOTALL)
# RUT9 (REV9 H8): a clock's colon («cuando te diga 8:00, …») is not where the phrase ends.
_COMMA = re.compile(r"^((?:[^,:;]|(?<=\d):(?=\d))+?)\s*(?:[,;]|(?<!\d):|:(?!\d))\s*(.+)$", re.DOTALL)
# RUT9 (REV9 H6): "you say" / "I say" tell what happens, not what is asked: the model's. («me dices» stays: it is how
# people ask for it, «los martes a las seis me dices que toca natación», and a complaint of the same form only reaches
# the repetition, never a save without «sí»: RUTINAS.md §5 d.)
_TELL = (
    (re.compile(r"\b(?:dime|me dices|me digas|me dirás|d[ií]game)\b", re.IGNORECASE), "es"),
    (re.compile(r"\btell me\b|(?<!\byou )(?<!\bi )\bsay\b", re.IGNORECASE), "en"),
)
_NAME_FIRST = re.compile(r"^(?:(?:baxy|baxi)\b\W*)+", re.IGNORECASE)
_LEAD_ONLY = re.compile(_LEAD, re.IGNORECASE)
REPEATS = (*DAILY, *WEEKDAYS, *WEEKEND)


def _one_breath(text: str, lang: str) -> Order | None:
    """«cuando diga X, orden» and «todos los días a las H dime texto», split by their form; None: not one of them."""
    for pattern, said_in in _WHEN_SAID:
        match = pattern.match(text)
        if match is None:
            continue
        rest = _SAID_WORD.sub("", match.group(3).strip())
        stated = fold(match.group(2)) == "digo"   # «cada vez que digo X…» tells what happens as often as it asks for it
        aside = re.search(r"[,:;]\s*$", match.group(1)) is not None or fold(match.group(1)) in LEAD_INS
        if match.group(1) and (stated or len(_words(rest)) < LEAST_AFTER or not aside):
            continue   # «no me escuchas cuando te digo…», «¿qué pasa cuando te diga X?», «escribe cuando…»: the model's
        split = _QUOTED.match(rest) or _COMMA.match(rest)
        # RUT9 (REV9 H2): BAXY's name in front of the phrase is not kept (the turn is compared without it)
        phrase = _plain(_NAME_FIRST.sub("", _plain(split.group(1)))) if split else ""
        order = _kept(split.group(2)).rstrip(".") if split else ""
        clean = split and fold(order) and len(order) <= MOST_ORDER and not thin(phrase)
        if clean and len(_words(phrase)) <= MOST_SAID_WORDS and not stated:
            # RUT11 (REV11 B-S1, B-5): split cleanly, a phrase that is BAXY's own order or everyday words, or an order
            # about the routines themselves, is said, and that part is asked again with the other one kept.
            guide = Guide(lang=said_in, kind="word", phrase=phrase, order=order)
            if mine(phrase) or everyday(phrase):
                # REM5 (VIVO15): the word refused here is the first answer refused (Guide.leaves: a second one leaves)
                guide.step, guide.phrase, guide.misses, guide.refused = "phrase", "", 1, True
                told = TEXT[said_in]["phrase_mine" if mine(phrase) else "phrase_everyday"].format(phrase=phrase)
                return Order("new", said_in, guide=guide, said=told)
            if about_routines(order):
                guide.step, guide.order = "order", ""
                return Order("new", said_in, guide=guide, said=TEXT[said_in]["order_mine"].format(phrase=phrase))
        if (not split or thin(phrase) or len(_words(phrase)) > MOST_SAID_WORDS or not fold(order)
                or len(order) > MOST_ORDER or mine(phrase) or everyday(phrase)):
            if stated:
                continue
            return Order("new", said_in, guide=Guide(lang=said_in))
        return Order("new", said_in, guide=Guide(lang=said_in, step="confirm", kind="word", phrase=phrase, order=order))
    for pattern, said_in in _TELL:
        match = pattern.search(text)
        if match is None:
            continue
        head = _LEAD_ONLY.sub("", text[:match.start()], count=1)
        words = _time_words(head)
        starts = bool(_seq(words, 0, REPEATS)) or any(
            word in DAY_WORDS for word in words[:3] if words[0] in ("los", "cada", "todos", "every", "on", "de", "el")
            or words[0] in DAY_WORDS)
        if not starts:
            continue
        given = spoken(head)
        if given is None:
            return None   # more than a time in front of «dime» («todos los días me pasa lo mismo, dime por qué»)
        say = _kept(text[match.end():]).rstrip(".").strip()
        if given.repeat not in ("daily", "days") or len(say) > MOST_SAY:
            return Order("new", said_in, guide=Guide(lang=said_in))
        guide = Guide(lang=said_in, step="when", kind="time", when=given, say=say if fold(say) else "")
        guide._after_when()
        return Order("new", said_in, guide=guide)
    return None


def heard(text: str, lang: Any = "es", whole: bool = False) -> Order | None:
    """The fixed order about the routines these whole words are, or None: then they go on as any other turn. With
    ``whole`` only the closed orders, not the one-breath forms (after a question of BAXY they may be its answer)."""
    kept, front = _span(text)
    core = " ".join(kept)
    if not core:
        return None
    for pieces, action, said_in in ((NEW_ES, "new", "es"), (NEW_EN, "new", "en"), (LIST_ES, "list", "es"),
                                    (LIST_EN, "list", "en")):
        if core in pieces:
            return Order(action, said_in, guide=Guide(lang=said_in) if action == "new" else None)
    # RUT11 (REV11 B-4): every routine at once, and one said by a pronoun
    for every, it, said_in in ((ALL_ES, IT_ES, "es"), (ALL_EN, IT_EN, "en")):
        for action, pieces in every.items():
            if core in pieces:
                return Order(action + "_all", said_in)
        for action, pieces in it.items():
            if core in pieces:
                return Order(action, said_in, it=True, fallback="model")
    for named, said_in in ((NAMED_ES, "es"), (NAMED_EN, "en")):
        for action, leads in named.items():
            for lead in sorted(leads, key=len, reverse=True):
                part = next((CHANGE_PART[word] for word in lead.split() if word in CHANGE_PART), "") \
                    if action == "change" else ""
                if core == lead:
                    # which one was not said: the one the last exchange named, or BAXY says the ones there are
                    return Order(action, said_in, part=part, it=True)
                if core.startswith(lead + " "):
                    words = core[len(lead):].split()
                    last = front + len(kept)
                    for tail in sorted(AFTER_NAME, key=len, reverse=True):
                        if len(words) > len(tail.split()) and words[-len(tail.split()):] == tail.split():
                            words, last = words[:-len(tail.split())], last - len(tail.split())
                            break
                    for link in sorted(OF, key=len, reverse=True):
                        said = link.split()
                        if len(words) > len(said) and words[:len(said)] == said:
                            words = words[len(said):]
                            break
                    # The name as it was written (its accents): those same words of the turn.
                    written = re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text))
                    name = (" ".join(written[last - len(words):last]) if len(written) == len(_words(text))
                            else " ".join(words)) if words else ""
                    return Order(action, said_in, name=name, part=part) if name else None
    if whole:
        return None
    text = _TAG.sub("", text, count=1)
    if "?" in text or "¿" in text:
        return None
    return _one_breath(text, lang_of(lang))


def _when_of(routine: dict[str, Any], lang: str) -> str | None:
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    clock = str(trigger.get("at") or "")
    if not re.fullmatch(r"\d{2}:\d{2}", clock):
        return None
    return said_when(clock, str(trigger.get("repeat") or "once"), trigger.get("days"), None, lang)


def _item(routine: dict[str, Any], lang: str) -> str:
    text = TEXT[lang]
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    off = text["off"] if routine.get("active") is False else ""
    when = _when_of(routine, lang)
    if when is not None:
        says = " ".join(str(step.get("say")) for step in routine.get("steps") or []
                        if isinstance(step, dict) and step.get("say"))
        return text["item_time"].format(when=when[0].lower() + when[1:], say=says) + off
    phrase = str(trigger.get("phrase") or routine.get("name") or "").strip()
    order = str(routine.get("order") or "").strip()
    return (text["item_order"].format(phrase=phrase, order=order) if order
            else text["item_steps"].format(phrase=phrase)) + off


def _told_whole(routine: dict[str, Any]) -> bool:
    """Whether the fixed sentence can say this routine as it was saved: one at a time with its words and, said on days
    of the week, those days."""
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    if _when_of(routine, "es") is None:
        return True
    says = [step.get("say") for step in routine.get("steps") or [] if isinstance(step, dict)]
    days = trigger.get("days")
    return (bool(says) and all(isinstance(said, str) and said.strip() for said in says)
            and (trigger.get("repeat") != "days"
                 or (isinstance(days, list) and bool(days) and all(day in DAYS for day in days))))


def keyed(routines: Any) -> tuple[tuple[str, str], ...]:
    """REM6 (REV15 B-2): (name, id) of these routines, for Guide.ids."""
    return tuple((_named(r), str(r.get("id") or "").strip()) for r in routines or [] if isinstance(r, dict))


def _named(routine: dict[str, Any]) -> str:
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    return str(routine.get("name") or trigger.get("phrase") or trigger.get("at") or "").strip()


def told(observation: str, action: str, lang: str, name: str = "", routines: Any = None) -> str | None:
    """The fixed sentence for the receipt of the call a fixed order or the guide proposed, from that receipt (and, for
    a name that is no routine, the routines the App gave this turn); None for any other receipt: the model reads it."""
    lang = lang_of(lang)
    text = TEXT[lang]
    try:
        facts = json.loads(observation)
    except (TypeError, ValueError):
        return None
    if not isinstance(facts, dict):
        return None
    status, error = facts.get("status"), str(facts.get("error") or "")
    observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    if status != "completed":
        if error == "routine_not_found" and action in ("delete", "enable", "disable", "run", "change"):
            names = [_named(r) for r in routines or [] if isinstance(r, dict) and _named(r)]
            have = text["have"].format(items=_listed([f"«{n}»" for n in names], lang)) if names else text["have_none"]
            return text["not_found"].format(name=name, have=have)
        if action not in ("create", "change") or observed.get("saved") is True:
            return None
        if action == "change" and error not in ("routine_duplicate_phrase", "routine_time_passed"):
            return None   # RUT11: the others' sentences say «no la guardé»; the model reads that receipt
        if error == "routine_duplicate_phrase":
            return text["duplicate"].format(phrase=str(observed.get("phrase") or name))
        fixed = {"routine_duplicate_name": "duplicate_name", "routine_routines_full": "full", "routines_full": "full",
                 "routine_time_passed": "passed", "routine_scheduler_unavailable": "scheduler",
                 "routine_task_not_verified": "scheduler", "routine_task_not_removed": "task_left"}.get(error)
        return text[fixed] if fixed else None
    if action == "list":
        kept = observed.get("routines")
        if not isinstance(kept, list) or not all(isinstance(r, dict) for r in kept):
            return None
        if not kept:
            return text["none"]
        if not all(_told_whole(r) for r in kept) or observed.get("truncated") or observed.get("count") not in (None, len(kept)):
            return None   # RUT9 (REV9 H1): what it says, its days or some routines did not arrive; never «una vez … te digo «»»
        items = "; ".join(_item(r, lang) for r in kept)
        return text["list_one"].format(items=items) if len(kept) == 1 else text["list"].format(count=len(kept), items=items)
    routine = observed.get("deleted" if action == "delete" else "routine")
    if not isinstance(routine, dict):
        return None
    if action == "delete":
        return text["deleted"].format(name=_named(routine))
    if action in ("enable", "disable"):
        if routine.get("active") is not (action == "enable"):
            return None
        return text["enabled" if action == "enable" else "disabled"].format(name=_named(routine))
    if action == "change":
        # RUT11 (REV11 B-4): the routine as the receipt says it was saved
        if observed.get("saved") is not True or not _told_whole(routine):
            return None
        item = _item(routine, lang)
        return text["changed"].format(name=_named(routine), item=item)
    if action != "create" or observed.get("saved") is not True:
        return None
    when = _when_of(routine, lang)
    if when is None:
        trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
        phrase = str(trigger.get("phrase") or "").strip()
        return text["saved_word"].format(phrase=phrase) if phrase and routine.get("order") else None
    first = _first(observed, lang)
    trigger = routine.get("trigger") if isinstance(routine.get("trigger"), dict) else {}
    if first and trigger.get("repeat") not in ("daily", "days"):
        return text["saved_once"].format(first=first)
    return (text["saved_time"].format(when=when, first=first) if first else text["saved_time_plain"].format(when=when))


def done_name(observation: str, action: str) -> str | None:
    """RUT11: the routine a completed delete, enable or disable receipt says it acted on, or None (not completed, or
    not that)."""
    try:
        facts = json.loads(observation)
    except (TypeError, ValueError):
        return None
    if not isinstance(facts, dict) or facts.get("status") != "completed" or not isinstance(facts.get("observed"), dict):
        return None
    routine = facts["observed"].get("deleted" if action == "delete" else "routine")
    if not isinstance(routine, dict) or (action != "delete" and routine.get("active") is not (action == "enable")):
        return None
    return _named(routine) or None


def told_all(action: str, lang: str, names: list[str]) -> str:
    """RUT11 (REV11 B-4): every routine acted on, one receipt each (done_name), in one sentence."""
    lang = lang_of(lang)
    if len(names) == 1:
        return TEXT[lang]["deleted" if action == "delete" else action + "d"].format(name=names[0])
    return TEXT[lang][action + "d_all"].format(count=len(names), items=_listed([f"«{n}»" for n in names], lang))


def _first(observed: dict[str, Any], lang: str) -> str:
    """«mañana a las 8:00 de la mañana», from the receipt's nextRunLocal and scheduledFor; nothing when they are not
    as expected."""
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})", str(observed.get("nextRunLocal") or ""))
    day = str(observed.get("scheduledFor") or "")
    if match is None:
        return ""
    told_at = said_clock(match.group(2), lang)
    at = f"at {told_at}" if lang == "en" else f"{'a la' if told_at.startswith('1:') else 'a las'} {told_at}"
    if day == "today":
        return f"today {at}" if lang == "en" else f"hoy {at}"
    if day == "tomorrow":
        return f"tomorrow {at}" if lang == "en" else f"mañana {at}"
    return f"on {match.group(1)} {at}" if lang == "en" else f"el {match.group(1)} {at}"
