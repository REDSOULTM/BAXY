"""The turn: native tool calls decide and write the arguments, and after each verified result the model either calls
again or answers in words (one conversation per session, calls and results included).

Nothing here authorizes or verifies: the kernel authorizes the proposed operation and the provider verifies its
effect. What the model cannot do becomes an honest limit (a question, «no pude», «eso no lo hago»), never a veto.
Everything the model needs comes from how the catalog is presented to it (names, descriptions, the installed
applications and games), not from code that decides for it.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import difflib
import hashlib
import http.client
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
from collections.abc import Callable, Collection, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from .answer_check import asked_for, check as check_answer
from .arithmetic import evaluate
from .doubt import read as read_doubt
from .llm_server import LlmServer, Yielded
from .protocol import whole_code_points
from .speech_text import cardinal, cardinal_en
from .system_one import ANSWER, ASK, OPTION_TEXT, SystemOne, short
from . import behavior, language_id, ring_answer, routine_guide, routines, web_focus
from .wire import Wires, operation_of, plain

_DATA = Path(__file__).with_name("data")
_ENGLISH_FILE = _DATA / "tool_descriptions.en.v1.json"

# What BAXY says when a turn of the person's has said nothing for 2.5 s (SilenceNotice.After) and is still working,
# and again every 10 s while it stays silent (goal identity: a notice that claims no result when the turn will go past
# 3 s in silence). The App times it and asks for it (turn.notice); the words are the model's (al máximo 9.2a: a phrase
# fixed here broke invariant 5, cero respuestas visibles fijas). Feria 2026-10-27: written once at warm-up, it was the
# same phrase in every turn («Estoy procesando tu solicitud.»), which the owner heard as fixed; now the model writes it
# for the call the App is running, from the turn's own conversation, while the GPU waits for that call (Mind.notice_of;
# the App asks only then): never one it already wrote in the turn, none once it answered. What is
# asked is an instruction, not a phrase; a phrase it does not write usably (empty, more than NOTICE_MAX_CHARS or
# NOTICE_MAX_WORDS, more than one line, markup) is not said. Fase 3 (H7): a 1,81 s notice held the reply that came
# behind it; it is said only while a call runs now, before the next decision even starts. Banco ciego c3 (2026-10-31):
# at 6 words and 60 characters 143 of 393 notices were thrown away and 75 of 77 turns silent past 8 s had none; what the
# model writes of what it does takes 7 to 10 words («Abro LibreOffice Writer y entro a Opciones.»).
# Uso-122 (F45, turns.jsonl since 02-11): of 165 notices 55 ran out NOTICE_SECONDS and 14 were written past the limits.
# The ask was a user message, and Qwen3.5's template keeps the empty think block only on the replies after the last
# user message: the request parted from what the slot holds at the turn's first reply, re-read the whole turn, and the
# decision after it read it again (3,476 tokens and 2.1 s at the median, against 94 and 172 ms with no notice). A tool
# result is not that message (it renders as a user turn holding a tool_response, which the template skips), so the ask
# goes in the running call's own result. It says the length, which the model never knew; the limits leave out only what
# goes well past it, and a phrase cut at max_tokens is not said.
NOTICE_ASK = ("[Esto no lo dice la persona. Lo que acabas de pedir a la herramienta sigue en curso y tarda unos segundos. "
              "Escribe sólo una frase de no más de 10 palabras, en presente, que dirás en voz alta para que la persona "
              "sepa qué estás haciendo ahora, sin decir que ya lo hiciste ni ningún resultado.{said}]")
NOTICE_SAID = " Ya dijiste {said}: di otra cosa."
NOTICE_RUNNING = json.dumps({"status": "running"})
NOTICE_MAX_CHARS = 90
NOTICE_MAX_WORDS = 14
# The notice's own budget: the result of the call it speaks of may come meanwhile, and its next decision waits for it.
NOTICE_SECONDS = 1.5
# Uso-124 (RX 7600 on Vulkan, 2026-11-05, driven by hand): a notice took 3.0 to 3.5 s (95 tokens read in 2.2 s, as a turn's
# first decision reads its ~100; 12 to 20 written at 58 ms each), so all of them ran out those 1.5 s and the person heard
# nothing for a whole turn. The budget is what the last short decision says a notice costs here (Mind._next, the same
# read and the 24 tokens a notice may write), with a margin, and never less than those 1.5 s nor more than NOTICE_MOST_S:
# on an NVIDIA GPU, which reads and writes that in about a second, it stays at 1.5 s. A read past NOTICE_SHORT_READ tokens
# says nothing of it (its cost per token hides the first read's fixed part).
NOTICE_WRITTEN = 24
NOTICE_MOST_S = 6.0
NOTICE_SHORT_READ = 512
NOTICE_MARGIN = 1.25

# The name of a conversation that closes (owner, 2026-11-08: «darle un nombre a la conversación de no más de X palabras …
# para después yo poder ubicarla»), written by the model once the App has started the next one, so nobody waits for it.
# Asked after the conversation as the slot still holds it (session.new reads nothing into the slot), it costs the ask
# and a few tokens. Typed: a JSON schema, as the heartbeat's decision. Its length follows Open WebUI's default title
# prompt (backend/open_webui/config.py, DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE: «Keep it short: 2-4 words is best»),
# with one word of room for Spanish's articles; the code only compares that form, and a name past it is no name.
TITLE_MAX_WORDS = 5
# Asked for at most TITLE_MAX_WORDS, a name one word longer is still kept: on 30 held-out conversations the stock model
# wrote 6 for one of them (two questions on one subject), and ChatGPT and Claude name chats in 3 to 6 words.
TITLE_ACCEPTED_WORDS = TITLE_MAX_WORDS + 1
TITLE_MAX_CHARS = 60
TITLE_WRITTEN = 40
TITLE_SECONDS = 15.0
# Asked in the language the person spoke (language_id, as the voice reads it): asked in Spanish, the stock model named
# the 8 English conversations of 30 held out in Spanish (NB, 2026-11-08). A conversation that was only a greeting was
# named after BAXY's reply («Hola, ¿en qué te ayudo?»): the ask says what such a one is called.
TITLE_ASK = ("[Esto no lo dice la persona: la conversación terminó y la App le pone un nombre para que la persona la "
             f"encuentre después en su historial. Escribe un título de 2 a {TITLE_MAX_WORDS} palabras que diga de qué "
             "trató, sin comillas, sin emojis y sin punto final. Si la persona sólo saludó, el título es «Saludo».]")
TITLE_ASK_EN = ("[The person did not say this: the conversation ended and the App names it so the person can find it later "
                f"in their history. Write a title of 2 to {TITLE_MAX_WORDS} words saying what it was about, without "
                "quotes, emojis or a final period. If the person only said hello, the title is «Greeting».]")
TITLE_SCHEMA = {"type": "object", "properties": {"titulo": {"type": "string", "maxLength": TITLE_MAX_CHARS}},
                "required": ["titulo"], "additionalProperties": False}

# Who BAXY is and how it replies open it (behavior.py: the factory texts, which the person may replace in Ajustes →
# Comportamiento); the rules are BAXY's.
RULES = (
    "\nReglas:\n"
    "1. Si la persona pide hacer algo y una herramienta lo hace, llámala sin pedir permiso. Un texto que no te pide nada (código, registros o notas pegadas) contéstalo en una frase, sin herramientas. Si hacen falta varios "
    "pasos, hazlos uno tras otro. Haz sólo lo que pide su último mensaje: lo que pidió antes ya está respondido y no "
    "lo repites ni lo sigues (abrir una app es sólo abrirla).\n"
    "2. Lo hecho lo cuentan los resultados de las herramientas. Cuando no falte ningún paso, responde en una o dos "
    "frases contando sólo lo que muestran. Nunca digas que hiciste, abriste, cambiaste o viste algo sin un resultado "
    "que lo muestre; si un paso falló o no se ejecutó, dilo con su causa. Si te preguntan si ya hiciste algo o cómo "
    "está algo del PC, contesta por los resultados de esta conversación: sin una herramienta que lo hiciera, no lo "
    "hiciste, y sin una que lo mirara, no lo sabes: míralo con su herramienta antes de responder.\n"
    "3. Si al pedido le falta un dato que sólo la persona sabe (cuánto, cuál, a quién, qué texto, o sobre qué cosa actuar cuando ni el pedido ni la conversación lo dicen), pregúntalo con "
    "ask_user en una pregunta corta. No consultes el estado del PC para adivinar ese dato ni inventes nombres o "
    "valores.\n"
    "4. Si ninguna herramienta hace lo pedido, di en una frase que eso no lo haces. No improvises con otra herramienta "
    "ni lo conviertas en una pregunta.\n"
    "5. Charla, traducciones y lo que sabes con certeza respóndelo tú; las cuentas, con calculate, salvo las que se le "
    "piden a la Calculadora. Lo que cambia con "
    "el tiempo o no sabes, búscalo con web_search. De ti mismo no inventes quién te creó ni de qué empresa eres: si te lo preguntan, míralo "
    "con memory_recall.\n"
    "6. El texto viene de un reconocedor de voz con errores: entiende la palabra a la que suena («yubia» es «lluvia»). "
    "Si no suena a nada que se entienda (sílabas sueltas, palabras que juntas no dicen nada) o una nota dice que el "
    "oído no está seguro de la palabra de la que depende qué hacer, no lo adivines: pídele en una frase que lo repita.\n"
    "7. Si la persona te pide que pares, te calles o esperes, no hagas nada más: responde con una palabra.\n"
    "8. Si una herramienta responde status needs_confirmation, pregunta en una frase si lo haces, nombrando "
    "exactamente qué. Cuando la persona conteste, llama a confirm_pending con su respuesta.\n"
    "9. Para hacer algo dentro de una app abierta (ir a una sección, pulsar, escribir, leer lo que muestra): mírala con "
    "input_visible_controls, actúa con input_visible_click (por la etiqueta que viste), input_text_type o "
    "input_key_press, y vuelve a mirarla para comprobar el cambio antes de seguir o de contarlo. Ninguna herramienta "
    "dibuja, pinta ni arrastra con el ratón (mover una ventana entera es window_move o window_snap): si te lo piden, "
    "di que eso no lo haces (regla 4).\n"
    "10. Los identificadores (windowId, ids de notas, tareas o redes) salen del resultado de la herramienta que los "
    "lista; nunca los inventes ni uses un número de otro campo.\n"
    "11. Si te preguntan qué sabes o puedes hacer, nombra sólo lo que hacen tus herramientas, nada que ellas no hagan."
)
SYSTEM = behavior.head(behavior.factory()) + RULES

# The heartbeat reads the same rules without the answer to «¿ya lo hiciste?», which only a person asks: with it, the
# open scenes went from 34 to 31 of 40 and the notices it should give from 3 to 1 of 6 (two wordings, sampled and greedy,
# 2026-10-15). Qwen3.5's template puts the tools before the system text, so the heartbeat's own conversation re-reads
# only this text, as it already re-read its own messages.
_ASKED_IF_DONE = (" Si te preguntan si ya hiciste algo o cómo está algo del PC, contesta por los resultados de esta "
                  "conversación: sin una herramienta que lo hiciera, no lo hiciste, y sin una que lo mirara, no lo "
                  "sabes: míralo con su herramienta antes de responder.")
assert _ASKED_IF_DONE in SYSTEM
# Feria 2026-10-27: asked what it can do, it answered five ways and named things no tool does (editing photos). Only a
# person asks that, so the heartbeat reads none of it; the person's text names the catalog's groups (CAN_DO_AREAS).
_CAN_DO = SYSTEM[SYSTEM.index("\n11. "):]
# P1.4 (noche 2026-10-27): what to do with words that sound like nothing, or with the ear's doubts, is for words someone
# said; in the heartbeat nobody spoke.
_REPEAT = (" Si no suena a nada que se entienda (sílabas sueltas, palabras que juntas no dicen nada) o una nota dice que "
           "el oído no está seguro de la palabra de la que depende qué hacer, no lo adivines: pídele en una frase que lo "
           "repita.")
assert _REPEAT in SYSTEM
BEAT_SYSTEM = SYSTEM.replace(_ASKED_IF_DONE, "").replace(_CAN_DO, "").replace(_REPEAT, "")
# The groups of the App's panel «Qué puedo hacer» (operation-labels.v1.json), each tool's «group» in catalog.configure.
CAN_DO_AREAS = " Por áreas: {areas}."
# VER2 (10-11, 1.3.3 recién instalada: asked which version it is, it said it had no information on it): the
# version this App is, from its stamp (catalog.configure «baxyVersion», UpdatePanel.Installed, the one Ajustes → General
# shows), a fact of this PC as the areas are. None from a development copy: nothing is said then.
VERSION_FACT = "\nVersión de BAXY instalada en este PC (la tuya): {version}."
# TPV1 (dueño, 10-11-2026, prueba en vivo de la 1.3.4: asked to remember a fact, BAXY said its memory was off and to
# turn it on in Settings; «si yo le digo Baxi, activa la memoria, la tiene que activar, no tiene que delegar al usuario
# nada»): a profile without the memory shows none of its tools, not even as a stub (operation-labels «ficha»: false,
# VIVO1 F8: with stubs the 4B claimed to have saved), so the model had nothing that said it is off nor what turns it on.
# A fact of this PC, as the version is: what is off and the call that switches it on, which waits for the person's «sí»
# by itself (OwnBrakes). Diario is the smallest profile with it (operation-labels «p»: 2, test_mente_tpv1).
MEMORY_OFF_FACT = ("\nTu memoria (recordar, guardar y olvidar datos de la persona) está fuera del perfil de herramientas de "
                   "este PC: no puedes guardar ni leer nada. La tiene el perfil Diario; si la persona quiere que recuerdes "
                   "algo o que enciendas la memoria, llama {call}: le pide su sí por sí sola, y desde su próximo pedido "
                   "tendrás la memoria.")
MEMORY_TOOL = "memory.save"
# ESE6 (GUA3/ESE5 lote A, Esencial with the memory off as it is born: «Recuerda que mi perro se llama Chispo.» → that
# call, held → «sí» → Diario, a whole larger profile, 7 of 18, «guardado» with nothing saved 9 of 18 and nothing saved
# after the «sí» 18 of 18). The App now shows memory.save with its arguments (catalog.configure, withheld «whole»),
# holds its call with them and, with the person's «sí», turns the memory on and runs that very call in one step
# (NativeTurnLoop.AnswerMemoryOffHeldAsync). Then the fact names that call, and no profile.
# REM7 (REV15 D-1, REV14 B-E2): it said «no hay nada guardado» without looking at the store, and «apagada» whatever the
# switch was: false for whoever saved and then turned the memory off, or chose Esencial with it on. Only what is known:
# the switch the App read (catalog.configure «memoryOff»; none said, off) or the profile, and that nothing is read nor saved.
MEMORY_HELD_FACT = ("\nTu memoria (recordar, guardar y olvidar datos de la persona) {state}: mientras tanto no lees lo que "
                    "tenga ni guardas nada. Si la persona quiere que recuerdes algo, llama {call} con ese dato: "
                    "la llamada queda esperando su sí, y con su sí BAXY enciende la memoria y lo guarda en el mismo paso; "
                    "su resultado te dice si quedó guardado.")
MEMORY_HELD_OFF = "está apagada en este PC"
MEMORY_HELD_PROFILE = "está encendida, pero sus herramientas están fuera del perfil de herramientas de este PC"
# ESE7 (ESE6 §7, Esencial: «Baxi, activa la memoria.» with nothing to save, 2 of 2: the one call the text gave was the
# save, so the memory was turned on with a filler record, «guardé que está encendida», an effect nobody asked for). The
# memory's switch is held whole too (operation-labels «ficha»: "entera"), and the text says which call is which: only
# when the App shows that call.
MEMORY_SWITCH = "memory.enable"
MEMORY_HELD_SWITCH = (" Si sólo pide encender la memoria, sin un dato que guardar, llama {call}: espera su sí igual, y con "
                      "su sí la memoria queda encendida y no se guarda nada.")
# What the fact adds after the save, one sentence per memory call the App also holds whole, in this order.
MEMORY_HELD_ALSO = ((MEMORY_SWITCH, MEMORY_HELD_SWITCH),)
# Perfiles de herramientas: a withheld tool's stub, after its title (configure). In English, as the tools' descriptions.
OFF_STUB = "Off in this PC's tool profile: nothing is done, saved or read."
# ESE6: the stub of a tool off in the profile whose call the App holds with its arguments (withheld «whole»): the call
# itself does nothing, and the person's yes to it runs it.
HELD_STUB = ("Off on this PC: calling it does nothing yet. Your call waits, with its arguments, for the person's yes; "
             "with their yes BAXY turns it on and runs exactly this call, and that result says how it went.")
# MUS1: where a call to a stub begins after another call in the same reply (the text between calls in Qwen3.5's chat
# template, tokenizer.chat_template of the model file); the request stops there (_next).
STUB_AGAIN = "</tool_call>\n<tool_call>\n<function={wire}>"
# ALR5 (M2, uso real 09-11: with Alarmas outside the profile, one set before rang and no words stopped it; only the card's
# buttons did, MainWindowViewModel.AnswerRingAsync): answering what already rings does not depend on the profile, as a
# phone's ringing alarm is silenced whatever mode it is in. Kept off, schedule.alarms is shown with the part that answers
# a ring and nothing else: the call grammar comes from the schema, so a stub with no arguments could only be called
# empty. The App runs that part only while something rings (ToolProfile.Refusal) and refuses it as off otherwise.
RING_TOOL = "schedule.alarms"
RING_STUB = ("Off in this PC's tool profile: nothing is set, listed or cancelled. Only an alarm or reminder that already "
             "rings is still answered (a note of the turn says which rings, each with its id): action stop silences it, "
             "also when the person just acknowledges it (thanks, it's done, on my way), snooze rings it again later, in "
             "inMinutes or at a local clock time (at, HH:mm), in 10 minutes if no time is said; with id that one, with no id "
             "every one ringing.")
RING_STUB_SCHEMA = {"type": "object", "properties": {
    "action": {"type": "string", "enum": ["snooze", "stop"]}, "at": {"type": "string", "maxLength": 32},
    "id": {"type": "string"}, "inMinutes": {"type": "integer", "minimum": 1, "maximum": 1440}}, "required": ["action"]}

# The heartbeat decides in two moves, both the model's: first it says in JSON what is happening and whether one of the
# reasons applies (grammar-constrained; measured on the open scenes 2026-10-15: a silence token was chosen in 40 of 40
# scenes, the analysis first found 34 of 40), then, only when it decided to intervene, it acts with its tools.
_MOTIVES = ("pedido", "preferencia", "vence", "bloqueo")
BEAT_DECISION = {"type": "object",
                 "properties": {**{m: {"type": "string"} for m in _MOTIVES}, "analisis": {"type": "string"},
                                "intervenir": {"type": "boolean"}},
                 "required": [*_MOTIVES, "analisis", "intervenir"]}
BEAT_DECIDE = ("Responde en JSON, revisando cada motivo con lo que ves arriba: pedido = qué te pidió antes y se "
               "cumple ahora, o «ninguno»; preferencia = qué preferencia suya aplica ahora, o «ninguna»; vence = qué "
               "vence ahora o muy pronto, o «nada»; bloqueo = qué la bloquea o le hará perder trabajo, o «nada»; "
               "analisis = en una frase, qué está pasando; intervenir = true si algún motivo es real, false si no.")
BEAT_ACT = ("Interviene ahora según tu análisis; lo que alcanzaste a leer de su memoria ya está arriba, no lo busques. Si "
            "basta con avisarle algo (lo que pidió saber, un recordatorio que "
            "vence, una alerta), díselo en una frase sin usar herramientas. Si hay que hacer algo de bajo riesgo, hazlo "
            "con su herramienta. Lo de alto riesgo (borrar, vaciar la papelera, enviar un mensaje, apagar o reiniciar, "
            "cerrar o forzar el cierre de una app) no lo preguntes en texto: llama a su herramienta y el sistema le "
            "pedirá el sí a la persona antes de hacerlo. Nunca escribas en sus ventanas ni digas que hiciste algo que "
            "no hiciste. Háblale de tú.")
BEAT_RULES = (
    "Es un latido: nadie te habló. Revisa lo de arriba buscando estos motivos para intervenir:\n"
    "1. Algo que la persona te pidió antes y que ahora se cumple (avisarle, recordarle, enviar algo).\n"
    "2. Una preferencia suya que recuerdas y que aplica a lo que está pasando ahora.\n"
    "3. Un recordatorio o evento que vence ahora o muy pronto.\n"
    "4. Algo que la bloquea o le hará perder trabajo: disco lleno, batería crítica, una app colgada, la red caída.\n"
    "Si hay un motivo: lo de bajo riesgo hazlo tú con su herramienta y avísalo en una frase; lo de alto riesgo "
    "(borrar, vaciar la papelera, enviar mensajes, apagar o reiniciar, cerrar o forzar el cierre de una app, comprar, "
    "instalar) proponlo llamando a su herramienta, que se le preguntará antes; si ninguna herramienta ayuda, díselo en "
    "una frase. Si juega, está en llamada o viendo algo, interviene sólo por un motivo 1, 2 o urgente. Nunca escribas "
    "ni hagas clic en sus ventanas, no comentes datos privados de la pantalla y no repitas un aviso ya dado."
)
# What stands in the person's conversation for a heartbeat that intervened, before what BAXY said and did in it.
BEAT_MARK = "[Latido: nadie te habló; lo que sigue lo dijiste o hiciste por tu cuenta]"


# How a call the kernel holds for the person's «sí» ended, in the words the model reads.
WAITS_FOR_YES = "no se ejecutó: espera el sí de la persona"
# Vivo larga (notebook, 2026-10-27): a call whose question ended unanswered (ENDED) kept «espera el sí» among the
# session's calls for good, and the same call asked again turns later read as maybe answering it (confidence 0.998 the
# first time, 0.53-0.70 after; «¿cierro la Calculadora o confirmo algo pendiente?» with no call, 2 of 5).
UNANSWERED = {"expired": "no se ejecutó: se acabó el tiempo para contestar su pregunta",
              "dropped": "no se ejecutó: su pregunta quedó sin respuesta"}
# How a completed call was verified (the result's «verification»), in the words the model reads.
# Auditoría de falsedades (w5-fals, 2026-10-22): «completado» is a word of something done, and the 4B told it as done
# where nothing was: «¿abriste Spotify?» → a read of its windows («completado: lectura») → «Sí» in 9 of 9 runs of
# pc-t2 (F002), and «¿ya cerraste el bloc de notas?» → «Sí» (F015). Only a call that changed something and was read
# back says «completado»; the others say what happened: already so before the call, sent without looking after it, or
# finished without a verification.
VERIFICATION = {
    "readback": "completado y verificado",
    "unchanged": "ya estaba así antes de esta llamada: no hizo falta cambiar nada",
    "delivered_only": "enviado sin verificar: no se volvió a mirar si hizo efecto",
    "output_only": "completado: su resultado está arriba",
    "none": "terminó sin verificar su efecto",
}
# An output_only call of a read risk (read_only, privacy_sensitive: the catalog's own risk, as the App sent it) only
# looked; shell_command_run and client_channel_locate are output_only too and may change things, so they keep the line
# above.
READ_RISKS = ("read_only", "privacy_sensitive")
# Fase 3 (bisección de V5E008, 8 turnos × 3 semillas con el modelo real): with «; lo que vio está arriba» at its end the
# model took a web_search's snippets as the answer and opened the page 4 of 24 times (1975 after reading it: 2); without
# it, 12 of 24 (7); 8 of 8 before 8.2 put it there. No extra fetch on searches whose snippet already answers (0 of 12).
OUTPUT_READ = "lectura: sólo miró, sin abrir, cerrar ni cambiar nada"
# Feria 2026-10-27: the volume set at the first call and the same set made again, «unchanged» by that first call, told
# as already so before the turn. An unchanged call after the same call of the turn changed it says what left it so.
SET_BY_SAME = "ya había quedado así por la misma llamada hecha antes en este turno: no hizo falta cambiar nada"
# ALR5 (B7): a reminder just set was told «Te he recordado que llames al veterinario en media hora», in the past, as if the
# person had been reminded. A result set for later (its scheduledFor; a snooze's is of one that did ring) says it has
# not rung yet. Answers in that past tense, 3 seeds × 2 on 22 held-out phrases (counted by form, then judged blind in
# INFORME_ALR5): base 20 of 66, with ALR5's description alone 30 of 132, with this line 19 of 132.
SET_FOR_LATER = "; quedó puesto para más tarde: aún no ha sonado ni se le ha recordado nada a la persona"
# Every outcome of a completed call (the App runs the queued calls after one of these).
COMPLETED_OUTCOMES = (*VERIFICATION.values(), OUTPUT_READ, SET_BY_SAME)
# What the facts line adds of a result's own fields (_outcome), and what _deduplicated leaves out of it for that.
ALREADY_OPEN = "; ya estaba abierta antes de esta llamada, que no la abrió"
SAME_WINDOW = "; la ventana no cambió"
AFTER_VIEW = "; su after es la ventana de después"
REREAD = {True: "; releído después: quedó como se pidió", False: "; releído después: no quedó como se pidió"}
# Noche NB r1, hallazgo 5 (T2-bloc, T5-bloc): a text written beside text the field already held (the receipt's
# otherTextInField) was told «escribí» alone, and a window number that is no window (windowFound false) «no encontré el
# campo de texto».
OTHER_TEXT = "; el campo ya tenía otro texto: lo escrito quedó junto a ese texto"
WINDOW_NOT_FOUND = "; la ventana pedida no existe: no se buscó ningún campo en ella"
# What _read_in_part says after the part a read held, in full.
PART_TAIL = "; lo demás no se leyó: un «no está» vale sólo para lo leído"
# Plan c3, fila 0.2 (estado explícito del resultado; research_notes/ft/13 §2, arXiv 2609.14758): a model fabricates 0 %
# after a status:error, 8.1 % after an «ok» with an empty payload and 18.6 % after a partial one, and a status line it
# must read before answering took 14.1 % to 0.87 %. Each call's entry in the facts line is that line: its first words
# are the status (completado / lectura / falló / no se completó / sin confirmar / no se ejecutó / cancelado), and what
# the result's own fields say it held is told after them, derived from those fields and never from the tool: an output
# that came back empty (EMPTY, EMPTY_TEXT), one read or shown only in part (_read_in_part, RESULT_CUT_TOLD,
# OBSERVED_LEFT_OUT) and a failure because what the call named came from a reading that no longer holds (STALE). That
# results of earlier turns are of their time is the clock's (Mind._clock).
EMPTY = "; vacío: no trajo ningún elemento"
EMPTY_TEXT = "; vacío: su texto está en blanco"
STALE = "; obsoleto: el id que usó es de una lectura anterior y ya no vale"
# A failure code that says the id or the reading it named is no longer valid (visible_control_identity_stale,
# invalid_or_expired_window_id, bluetooth_identity_expired…); a confirmation that expired is no reading, and a budget
# spent (tooltip_budget_spent) is no id.
_STALE_CODE = re.compile(r"(?<![a-z])(?:stale|expired)(?![a-z])")
# MEN1 (AMD2 §9, hallazgo E, 2026-11-09): baxy_update failed with baxy_update_development_build (nothing looked for a
# newer version) and the answer was «No hay una versión más reciente disponible para instalar». A result whose own
# «checked» is false says the call did not look at what it is for finding out, whatever its status (a failure before
# looking, a store that updates by itself): another thing than a check that found nothing, which says what it found.
NOT_CHECKED = "; no se comprobó lo pedido: de este resultado no sale ni un «hay» ni un «no hay»"
# The kernel's own marks of a cut (OperationVisibleFacts: «truncated», «resultsMayBeTruncated», any «…Truncated») and of
# an observation left out whole for its size («observedLimit»: «omitted»).
TRUNCATED_PART = "parte de lo leído se cortó por tamaño"
MORE_PART = "hay más sin mostrar"
OBSERVED_LEFT_OUT = "; no se muestra nada de lo que vio: no cabía en el resultado"
# Aid «result_cap»: the cut the mind made said in the line, not in the body (CUT_RESULT only marks where it is).
RESULT_CUT_TOLD = "el resultado se recortó para que quepa el turno: {n} de sus {total} caracteres no se muestran"
# The clock's: a result of an earlier turn is what was read then, not the state now (the reading is old, not wrong).
STALE_TURNS = " y lo leído en turnos anteriores es de entonces"
# Aid «facts_once» (w7-breve, 2026-10-23): on the holdout v4 turn.continue wrote more after a tool (predicted p50 399 →
# 487 ms). A facts line of several calls said the same long wording once per call (E022: «lectura: sólo miró, sin
# abrir, cerrar ni cambiar nada; lo que vio está arriba» seven times), and the answer after it retold the pages; without
# the line it was 16 tokens, with it 37. Each wording is said in full the first time it comes in the line; a later call
# that ended the same way says it in its first words, which still name what happened (only looked, sent without
# looking, already so). Every call keeps its own entry, code, place and part read: only the explanation is not repeated.
SAID_AGAIN = {OUTPUT_READ: "lectura: sólo miró",
              VERIFICATION["delivered_only"]: "enviado sin verificar",
              VERIFICATION["unchanged"]: "ya estaba así antes de esta llamada",
              PART_TAIL: "",
              EMPTY: "; vacío",
              EMPTY_TEXT: "; vacío",
              STALE: "; obsoleto",
              NOT_CHECKED: "; no se comprobó"}
# The wordings above that come after an outcome's first words (the rest open it).
_SAID_WITHIN = (PART_TAIL, EMPTY, EMPTY_TEXT, STALE, NOT_CHECKED)


def _answered_ring(receipt: dict[str, Any]) -> bool:
    """A schedule.alarms stop or snooze whose receipt says it answered one of what rang (its own stopped or snoozed, or
    one of its rings'), even when the call did not complete: with no id the App answers every one ringing, and one it
    did not end in time fails the call (ALR3, WindowsScheduledNotificationAdapter.AnswerRingAsync)."""
    if receipt.get("op") != "schedule.alarms" or (receipt.get("arguments") or {}).get("action") not in ("stop", "snooze"):
        return False
    if receipt.get("completed"):
        return True
    try:
        observed = json.loads(receipt.get("observation") or "").get("observed")
    except (json.JSONDecodeError, AttributeError):
        return False
    if not isinstance(observed, dict):
        return False
    rings = observed["rings"] if isinstance(observed.get("rings"), list) else [observed]
    return any(isinstance(ring, dict) and (ring.get("stopped") is True or ring.get("snoozed") is True) for ring in rings)


def _scalars(observation: str) -> str | None:
    """A result kept for the answer check's rule «stale_state» (Mind._states): its top-level fields and those of its
    «observed» that are a number, a boolean or a short text (its state, name, bytes, next), not its lists or views."""
    try:
        facts = json.loads(observation)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(facts, dict):
        return None

    def kept(where: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in where.items()
                if isinstance(v, (bool, int, float)) or (isinstance(v, str) and len(v) <= 400)}

    observed = facts.get("observed")
    return json.dumps({**kept(facts), **({"observed": kept(observed)} if isinstance(observed, dict) else {})},
                      ensure_ascii=False)


def _outcome(observation: str, read: bool = False) -> str:
    """How a call ended, in the words the model reads: from the result's own status, verification and error. ``read``:
    the call's risk only reads (READ_RISKS)."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return "resultado arriba"
    if not isinstance(facts, dict):
        return "resultado arriba"
    # Ronda final 37 (regla 3): the journal's answer to the same call made earlier (the App's «replayed») ran nothing now.
    if facts.get("replayed"):
        return "respuesta de la misma llamada hecha antes: no se ejecutó de nuevo"
    status = str(facts.get("status") or "failed")
    if status == "needs_confirmation":
        return WAITS_FOR_YES
    if status == "cancelled":
        return "cancelado por la persona"
    # Uso real 2026-10-21 (e2e del notebook): a message stopped before it was written touched the client (an uncertain
    # effect) and the model told «le mandé el mensaje»; what the result knows of the message comes first.
    # Renew al máximo (w9): one typed and stopped just before Enter (the chat no longer named the recipient) was not sent.
    shown = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    if status != "completed" and shown.get("sent") is False and isinstance(shown.get("messageWritten"), bool):
        error = facts.get("error") or facts.get("cause")
        written = "quedó escrito y no se envió" if shown["messageWritten"] else "no se escribió ni se envió"
        return "falló" + (f" ({error})" if error else "") + ": el mensaje " + written
    # Al máximo 8.3 (notebook): an act that failed or stayed unsure but whose state was read again after it says whether
    # what was asked holds now; the result's code and its uncertainty stay as they are.
    after = shown.get("stateAfter")
    reread = ""
    if isinstance(after, dict) and isinstance(after.get("requestedStateReached"), bool):
        reread = REREAD[after["requestedStateReached"]]
    # P2.15: the kernel says effectUncertain when the effect may have happened; a «pending» without it did not complete
    # and is not told «pudo o no ocurrir» (nor «nothing happened»: a stale confirmation challenge comes as one too).
    # Either keeps its code.
    error = facts.get("error") or facts.get("cause")
    code = f" ({error})" if isinstance(error, str) and error else ""
    if facts.get("effectUncertain"):
        return "sin confirmar" + code + ": pudo o no ocurrir" + reread
    stale = (STALE if isinstance(error, str) and _STALE_CODE.search(error) and not error.startswith("confirmation")
             else "")
    left = OBSERVED_LEFT_OUT if facts.get("observedLimit") == "omitted" and "observed" not in facts else ""
    unchecked = NOT_CHECKED if shown.get("checked") is False else ""
    if status == "pending":
        return "no se completó" + code + stale + reread + unchecked
    if status == "completed":
        # Al máximo 8.2: how it was verified is the result's own typed fact (OperationVisibleFacts' table in the kernel,
        # and the App's for memory and for a result it could not read); one without it is not taken as verified.
        # FT/proveedores goal (e2e E006, E017): where a file or folder was made, from its own result, beside the facts
        # the model tells («lo creé en BAXY-bench» after a write that went to the home folder).
        where = shown.get("fullPath")
        where = f" en {where}" if isinstance(where, str) and where else ""
        # Al máximo 7.1 (notebook): an act in a window brings the window as it is after it; what it says is told.
        view = shown.get("after")
        seen = ("" if not isinstance(view, dict) or view.get("omitted")
                else SAME_WINDOW if view.get("same") is True
                else AFTER_VIEW)
        verification = str(facts.get("verification"))
        told = (OUTPUT_READ if read and verification == "output_only"
                else VERIFICATION.get(verification, VERIFICATION["none"]))
        # Auditoría de falsedades (F002): an application BAXY did not start (app_open's alreadyRunning) is said so,
        # or «¿abriste X?» after opening one already open read «completado y verificado» as «Sí, lo abrí».
        before = ALREADY_OPEN if shown.get("alreadyRunning") is True else ""
        # The App's own completed result it could not read (result_unreadable) keeps its code.
        error = facts.get("error")
        code = f" ({error})" if isinstance(error, str) and error else ""
        other = OTHER_TEXT if shown.get("otherTextInField") is True else ""
        # Plan c3 (EMPTY): only a call whose result is its output (output_only) is told empty by what that output holds.
        empty = _empty(shown) if verification == "output_only" else ""
        later = SET_FOR_LATER if isinstance(shown.get("scheduledFor"), str) and "snoozed" not in shown else ""
        return told + code + where + before + other + later + seen + empty + _read_in_part(shown) + unchecked + left
    gone = WINDOW_NOT_FOUND if shown.get("windowFound") is False else ""
    return "falló" + code + stale + reread + gone + _looked_elsewhere(shown) + unchecked + left


# Renew al máximo (w8): file_open of a path that was not there looked only at that path (searchedElsewhere false), and the
# answer was «no está ahí ni en ningún otro lugar que revisé». What a not-found looked at is told in the outcome line.
NOT_SEARCHED_ELSEWHERE = "; sólo se miró la ruta nombrada: no se buscó en ningún otro lugar"
SEARCH_CUT = "; la búsqueda en otros lugares no se completó: lo no visto puede estar ahí"


def _looked_elsewhere(shown: dict[str, Any]) -> str:
    if shown.get("searchedElsewhere") is False:
        return NOT_SEARCHED_ELSEWHERE
    return SEARCH_CUT if shown.get("searchComplete") is False else ""


def _number(facts: dict[str, Any], key: str) -> int | None:
    value = facts.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _empty(shown: dict[str, Any]) -> str:
    """Plan c3 (EMPTY): whether an output says it holds nothing, by its own fields: its «count» of what it shows is 0
    (and no «totalCount» says there is more), or, without a count and with no object of its own that holds something
    (a forecast, a window), every list it brings is empty and its «text», if it has one, is blank. An output with none
    of these (a level, a state) is not told empty."""
    count = _number(shown, "count")
    text = shown.get("text")
    blank = not isinstance(text, str) or not text.strip()
    if count is not None:
        return EMPTY if count == 0 and not _number(shown, "totalCount") and blank else ""
    if any(isinstance(value, dict) and value for value in shown.values()):
        return ""
    lists = [value for value in shown.values() if isinstance(value, list)]
    if lists:
        return EMPTY if not any(lists) and blank else ""
    return EMPTY_TEXT if isinstance(text, str) and blank else ""


def _cut_flagged(shown: dict[str, Any]) -> bool:
    """Whether the result or its search scope carries a cut mark set (TRUNCATED_PART)."""
    scope = shown.get("searchScope") if isinstance(shown.get("searchScope"), dict) else {}
    return any(value is True and (key in ("truncated", "resultsMayBeTruncated") or key.endswith("Truncated"))
               for where in (shown, scope) for key, value in where.items())


def _read_in_part(shown: dict[str, Any]) -> str:
    """Holdout v4 (falsedad): pages of a file read up to line ~1,904 of 3,000, the last read failed, and the answer was
    «revisé todo el archivo y no apareció». A read whose result says it holds only part of what it read (readInPart: a
    page of a file or a web page, a search that did not read every file, a log read that stopped at its limit, a listing
    or a count of a folder's top level with subfolders or hidden entries it did not look at) is told so in the outcome
    line, with how much of the total its own numbers give, and that a «no está» covers only that part. Plan c3: so is a
    list that shows fewer than its total («count» under «totalCount», a list «xShown» under its «xCount»), one with more
    to page («hasMore») and one the kernel or the provider cut for its size (_cut_flagged)."""
    listed, total_entries = _number(shown, "entriesShown"), _number(shown, "count")
    # A listing the observation cut to what it shows (the kernel's «entriesShown») is a part too.
    cut = listed is not None and total_entries is not None and listed < total_entries
    total_count = _number(shown, "totalCount")
    fewer = total_entries is not None and total_count is not None and total_entries < total_count
    lists = [(key[:-5], value, _number(shown, key[:-5] + "Count")) for key, value in shown.items()
             if key.endswith("Shown") and key != "entriesShown" and isinstance(value, int)]
    lists = [(name, value, whole) for name, value, whole in lists if whole is not None and value < whole]
    flagged, more = _cut_flagged(shown), shown.get("hasMore") is True
    if shown.get("readInPart") is not True and not (cut or fewer or lists or flagged or more):
        return ""
    part = []
    if fewer:
        part.append(f"se muestran {total_entries} de {total_count}")
    part.extend(f"{name}: se muestran {value} de {whole}" for name, value, whole in lists)
    first, last, total = (_number(shown, k) for k in ("fromLine", "toLine", "totalLines"))
    offset, returned = _number(shown, "offset"), _number(shown, "returnedCharacters")
    characters = _number(shown, "characters")
    characters = characters if characters is not None else _number(shown, "totalCharacters")
    if first is not None and last is not None and total is not None:
        part.append(f"líneas {first}–{last} de {total}")
    elif offset is not None and characters is not None:
        upto = offset + returned if returned is not None else _number(shown, "nextOffset")
        if upto is not None:
            part.append(f"caracteres {min(offset + 1, upto)}–{upto} de {characters}")
    scope = shown.get("searchScope") if isinstance(shown.get("searchScope"), dict) else {}
    scanned = _number(scope, "filesScanned")
    if scanned is not None:
        skipped = sum(_number(scope, k) or 0 for k in ("skippedTooLarge", "skippedNotText", "skippedUnreadable"))
        part.append(f"{scanned} archivos recorridos" + (f", {skipped} de ellos sin leer su texto" if skipped else ""))
    if scope.get("timeLimitReached") is True:
        part.append("la búsqueda paró en su tiempo límite")
    # Holdout v4 (falsedad: «Sí, porque no había .bak» with three present): a listing or a count of a folder's top level.
    folders = _number(shown, "subfoldersNotOpened")
    if folders:
        part.append(f"sólo lo que está directamente en la carpeta: sus {folders} subcarpetas no se abrieron")
    hidden = _number(shown, "hiddenOrSystemSkipped")
    if hidden:
        part.append(f"{hidden} entradas ocultas o de sistema sin mirar")
    unlisted = (total_entries - listed if listed is not None and total_entries is not None
                else _number(shown, "entriesNotListed"))
    if unlisted:
        part.append(f"{unlisted} entradas sin listar")
    seen, cap = _number(shown, "eventsSeen"), _number(shown, "readCap")
    if cap is not None and seen is not None:
        part.append(f"sólo los {cap} eventos más recientes del registro")
    if shown.get("endReached") is False:
        part.append("no llegó al final")
    if flagged and not part:
        part.append(TRUNCATED_PART)
    if more and not part:
        part.append(MORE_PART)
    detail = (": " + ", ".join(part)) if part else ""
    return f"; leído en parte{detail}{PART_TAIL}"


def _cut_told(outcome: str, left_out: int, total: int) -> str:
    """Aid «result_cap»: an outcome with the mind's cut of the result told among what was read in part."""
    cut = RESULT_CUT_TOLD.format(n=left_out, total=total)
    head, tail, rest = outcome.partition(PART_TAIL)
    if not tail:
        return outcome + "; leído en parte: " + cut + PART_TAIL
    joiner = ", " if ": " in head[head.rfind("; leído en parte"):] else ": "
    return head + joiner + cut + tail + rest


def _said_once(done: list[str]) -> list[str]:
    """Aid «facts_once» (SAID_AGAIN): the turn's calls as the facts line lists them, each long wording in full only the
    first time; a later entry that ended the same way keeps its call, its count, its code and the rest of its outcome."""
    seen: set[str] = set()
    told = []
    for entry in done:
        head, arrow, outcome = entry.partition(" → ")
        if arrow:
            for full, again in SAID_AGAIN.items():
                if full in _SAID_WITHIN:
                    if full in outcome:
                        outcome = outcome.replace(full, again) if full in seen else outcome
                        seen.add(full)
                elif outcome.startswith(full):
                    outcome = again + outcome[len(full):] if full in seen else outcome
                    seen.add(full)
            entry = head + arrow + outcome
        told.append(entry)
    return told


def _deduplicated(observation: str, outcome: str) -> str:
    """Aid «result_dedup» (w6-lat, 2026-10-23): the result without the fields its facts line (``outcome``, _outcome's
    words for it, written right after it) already says, so the model reads each fact once. On the holdout v4 the first
    spoken answer after a tool went 3.4 → 4.3 s p50, turn.continue reading 124 → 156 tokens. Left out only where the line
    says it: a completed call's status and verification («completado y verificado», «lectura: …»), its fullPath («en
    C:\\…»), alreadyRunning true (ALREADY_OPEN), otherTextInField true (OTHER_TEXT), windowFound false
    (WINDOW_NOT_FOUND), an after that is only {"same": true} (SAME_WINDOW), stateAfter's requestedStateReached
    (REREAD), the kernel's «truncated» true (the line's «leído en parte») and its «observedLimit» omitted
    (OBSERVED_LEFT_OUT). The rest stays as it came, in the App's compact JSON; a result with none of them is the App's
    own text."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return observation
    if not isinstance(facts, dict):
        return observation
    shown = dict(facts)
    if shown.get("status") == "completed" and outcome.startswith(COMPLETED_OUTCOMES):
        shown.pop("status")
        shown.pop("verification", None)
    if facts.get("observedLimit") == "omitted" and OBSERVED_LEFT_OUT in outcome:
        shown.pop("observedLimit")
    if isinstance(facts.get("observed"), dict):
        observed = dict(facts["observed"])
        where = observed.get("fullPath")
        if isinstance(where, str) and where and f" en {where}" in outcome:
            del observed["fullPath"]
        if observed.get("alreadyRunning") is True and ALREADY_OPEN in outcome:
            del observed["alreadyRunning"]
        if observed.get("otherTextInField") is True and OTHER_TEXT in outcome:
            del observed["otherTextInField"]
        if observed.get("windowFound") is False and WINDOW_NOT_FOUND in outcome:
            del observed["windowFound"]
        if observed.get("after") == {"same": True} and SAME_WINDOW in outcome:
            del observed["after"]
        after = observed.get("stateAfter")
        if isinstance(after, dict) and isinstance(after.get("requestedStateReached"), bool) \
                and REREAD[after["requestedStateReached"]] in outcome:
            observed["stateAfter"] = {k: v for k, v in after.items() if k != "requestedStateReached"}
        if observed.get("truncated") is True and "; leído en parte" in outcome:
            del observed["truncated"]
        if observed or not facts["observed"]:
            shown["observed"] = observed
        else:
            del shown["observed"]  # all it held is in the line
    if shown == facts:
        return observation
    return json.dumps(shown, ensure_ascii=False, separators=(",", ":"))


def _aid_on(aid: str) -> bool:
    """Whether a model aid (goal «ayudas al modelo», 2026-10-19) is on: BAXY_AYUDAS as the core reads it
    (src/Baxy.Providers.Windows/Infrastructure/ModelAids.cs). Unset, empty or «all», every aid; «none» or «0», none, and
    the mind reads as it did before them; otherwise the comma-separated ids that are on."""
    setting = os.environ.get("BAXY_AYUDAS", "").strip().lower()
    if setting in {"", "all"}:
        return True
    if setting in {"none", "0"}:
        return False
    return aid in {part.strip() for part in setting.split(",")}


# Aid «query_left_name» (cosecha 04-11 F27, «Si busca BAXY en internet» → web_search «trabajos universitarios», the topic of
# the turn before): the search dropped the one name the person said. Only the form is compared (as SaidVerbs compares an
# argument nobody said): names written in the person's words with a capital past the start of a sentence, none of them in the
# query, and no word of four letters or more of those words in it either, so a query in other words of what was said
# («capital de Francia» for «the capital of France») is no finding. Told beside the result the model went on with the results
# (0 of 24 on the bench); held before it runs, with the call that searches the name, as SaidFolders holds a file call, and the
# same call written again runs as written: the model decides. Voice that comes in lower case has no name written: nothing is
# said (a limit).
LEFT_NAME_REFUSED = "no se ejecutó: la búsqueda dejaba fuera el nombre que dijo la persona"


def left_name_not_run(wire: str, names: list[str]) -> str:
    """The result of a web_search held by «query_left_name»: the names it left out and the call that searches them."""
    call = json.dumps({"query": " ".join(names)}, ensure_ascii=False, separators=(",", ":"))
    return json.dumps({"status": "not_run", "next": f"{wire} {call} searches what the person said; this query has none of "
                                                    "the names they said, so it was not searched: the same call again runs "
                                                    "as written", "namesSaid": names}, ensure_ascii=False)


def _names_left_out(text: str, arguments: Any) -> list[str]:
    """The names the person wrote that a web_search's query left out whole, in their spelling; [] when any is in it or the
    query holds a word of theirs."""
    try:
        query = str((json.loads(arguments) if isinstance(arguments, str) else arguments or {}).get("query") or "")
    except (json.JSONDecodeError, AttributeError):
        return []
    asked = {_fold(word) for word in _WORDS.findall(query)}
    said = {_fold(word) for word in _WORDS.findall(text)}
    names = [word for sentence in _SENTENCES.split(text) for word in _WORDS.findall(sentence)[1:] if word[0].isupper()]
    if not names or {_fold(name) for name in names} & asked or {word for word in said & asked if len(word) >= 4}:
        return []
    return list(dict.fromkeys(names))


# Aid «person_folder_sentence» (lever 8): one sentence of fact at the end of a tool's description
# (artifacts/renew/ayudas/DISENO_PALANCAS.md), from what filesystem_list already says (td:63). E027 0/3 → 3/3 in the
# e2e of both machines. Lever 7 (the modes, in system.settings.set) was measured and left out: scenes −2,25.
# Renew al máximo (w9-dudas, practice falsehoods and e2e of int9-int10), each its own switch; measured offline on the
# notebook's int10 catalog, 3 seeds, layer 0 at 0.4 (scripts/renew/ayudas/dudas.py):
# «named_folder_theirs» (F009: «no puedo abrir un archivo de BAXY-bench, es tu carpeta de trabajo» with no call; E020:
# file_find against the work folder's tools at 0.46-0.51 for «el más grande dentro de BAXY-bench»): where BAXY's work
# folder is, in the tools that read or open the person's files and in the work folder's own. E020 file_find 0.47 → 0.57;
# F009 no better (it refuses on 1 seed of 3 with or without it, as on the notebook), worse without file_open's sentence.
# «read_find_split» (E018: «¿cuántas líneas tiene registro.log de BAXY-bench?», file_read against file_find at 0.49 each,
# held by the doubt and asked): which of the two counts a named file's lines, and that file_read finds the file itself.
# file_find 0.56 → file_read 0.58, 3/3.
# «game_epic_look» (F016: «lanza Fortnite», an Epic game, split between game_launch, whose list is Steam's, and three
# reads at 0.28-0.34, held and asked «¿abrir o instalar?»): the list is Steam's, and the read that looks in Steam and
# Epic. Held 3/3 → game_installed_named at 0.66, 0/3; «lanza Rocket League» still game_launch (0.81 → 0.70).
# «unsaved_not_read» (P1.1(b) F024 in falsedades v11, base and candidate: «no había nada sin guardar» after a close or
# a minimize, with nothing read): unsaved changes are not readable, the receipt says so (the App's aid of the same id)
# and the description names it.
WORK_FOLDER = "BAXY's own work folder is only filesystem-sandbox, in BAXY's data under AppData"
NAMED_FOLDER = (" Any folder of the person's home is theirs, even one whose name contains BAXY: it goes in path "
                f"({WORK_FOLDER}).")
SANDBOX_ONLY = (" This work folder is filesystem-sandbox, in BAXY's data under AppData: any other folder of the person's "
                "home is file_find's, whatever its name.")
# Aid «entity_lookup» (G13, uso real 2026-11-03 03:23: «WhatsApp es un mensajero de WhatsApp», twice, and «Meta viene de
# la palabra griega que significa cumbre», each with no call and the call's probability under 0.02). The description's
# «Do not use when: what you know for sure (definitions, … well-known history)» let the model take what it says of a
# named thing for something it knows. Mallen et al. (ACL 2023, arXiv 2212.10511): models fail on facts about less
# popular entities and retrieval helps most there; a 4B's memory of a name is not «for sure».
ENTITY_LOOKUP = (" What something with a name of its own is (an app, brand, company, game, person, work or place), who "
                 "made or founded it, or where its name comes from, is not a definition you know for sure: look it up "
                 "and answer from the results (examples: «¿qué es Twitch?», «¿quién creó Pokémon?»).")
# Aid «office_lookup» (VER1, G-03: «¿Quién es la presidenta del Perú?» answered three times of three with a name it made
# up, «Dina Bustamante», «Diana Hidalgo de Castillo», and no call; blind judges, 2026-11-09). Who holds an office is what
# changes over time: a model's memory of it is as old as its training data and, for a 4B, often not even that (Dhingra et
# al., TACL 2022, arXiv 2106.15110: language models answer time-sensitive facts with the ones of their training period;
# Kasai et al., NeurIPS 2023, arXiv 2207.13332, RealTime QA: retrieval is what keeps such answers current). No example:
# one that named a country («¿quién es el presidente de Perú?») went into the query of «¿quién es el ministro del
# Interior?» two times of three (INFORME_VER1 §3, S30).
OFFICE_LOOKUP = (" Who holds an office or a title now (a president, a minister, a mayor, a CEO, a coach, a champion) changes, "
                 "and a name from memory may be an old one or a wrong one: look it up and answer from the results.")
DESCRIPTION_AIDS = {
    "filesystem.known.trash.named": ((
        "person_folder_sentence",
        " A folder the person names, in their home or anywhere else, is theirs even if its name contains BAXY or bench: "
        "delete from it like from any other folder (BAXY's own work folder is only the one filesystem_list shows)."),),
    "file.open": (("named_folder_theirs", " Any folder of the person's home is theirs, even one whose name contains "
                                          f"BAXY: open from it with that folder in path ({WORK_FOLDER})."),),
    "file.read": (("named_folder_theirs", NAMED_FOLDER),
                  ("read_find_split", " It also tells how many lines a named file has (totalLines), and it looks for the "
                                      "file itself: no file_find before it.")),
    "file.find": (("named_folder_theirs", NAMED_FOLDER),
                  ("read_find_split", " What a named file says, or how many lines it has, is file_read, which looks for "
                                      "the file itself.")),
    "filesystem.list": (("named_folder_theirs", SANDBOX_ONLY),),
    "filesystem.search": (("named_folder_theirs", SANDBOX_ONLY),),
    "game.launch": (("game_epic_look", " The installed games list is Steam's only: a game not in it may be installed "
                                       "from Epic, so before saying it is not installed, game_installed_named looks in "
                                       "Steam and Epic without opening anything."),),
    "game.installed.named": (("game_epic_look", " It is also the look for a game the person wants to play that is not "
                                                "in game_launch's list of installed games (Steam's only)."),),
    "app.close": (("unsaved_not_read", " Whether a window held unsaved changes is not something BAXY can read "
                                       "(unsavedChanges not_readable): closePrompted false says only that it closed "
                                       "without asking to save, never that nothing was unsaved."),),
    "window.minimize": (("unsaved_not_read", " A minimized window stays open as it was, nothing in it lost; whether it "
                                             "holds unsaved changes is not read (unsavedChanges not_readable)."),),
    "web.search": (("entity_lookup", ENTITY_LOOKUP), ("office_lookup", OFFICE_LOOKUP)),
}

def _fold(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).casefold()
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def _words(text: str) -> str:
    """The folded words of a text, one space apart and one at each end, to find a name among them as whole words."""
    return " " + " ".join(re.findall(r"[^\W_]+", _fold(text))) + " "


def _echoes(question: str, said: str) -> bool:
    """Aid «ask_once» (ASKED_ECHO): whether a question (its folded words) is the person's last words back, by the share
    of its letters those words hold in the same order."""
    if not question:
        return False
    matcher = difflib.SequenceMatcher(None, question, _words(said).strip(), autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) >= ASKED_ECHO * len(question)


def _same_twice(question: str) -> bool:
    """Aid «ask_once» (ASKED_SAME_NOT_RUN): whether a question (its folded words) offers the same words as its two last
    options: «¿mail plus o mail plus?»."""
    words = question.split()
    return any(words[-size:] == words[-2 * size - 1:-size - 1] and words[-size - 1] in _OR
               for size in range(1, (len(words) - 1) // 2 + 1))


def _as_read(observation: Any) -> str:
    """A result as its words read, JSON's escapes undone (the App's JSON writes «ó» as \\u00f3)."""
    text = str(observation or "")
    try:
        return json.dumps(json.loads(text), ensure_ascii=False)
    except json.JSONDecodeError:
        return text


def _app_places() -> dict[str, dict[str, str]]:
    """The places of each application with an address of its own (app_places.v1.json, the kernel's data), by folded
    name (its own and the other Start names the data give it, «names»): place → the placeValue it takes, empty for
    none."""
    try:
        data = json.loads((_DATA / "app_places.v1.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    slots = {"{query}": "lo que se busca", "{game}": "el número del juego", "{slug}": "el nombre del juego"}
    return {_fold(name): {place: next((meaning for slot, meaning in slots.items() if slot in str(entry.get("address"))),
                                      "")
                          for place, entry in (body.get("places") or {}).items()}
            for app, body in (data.get("applications") or {}).items() if isinstance(body, dict)
            for name in (app, *(body.get("names") or []))}


APP_PLACES = _app_places()


def _app_places_text() -> str:
    """PLAN_GENERAL A6 (uso real 2026-10-21: Epic had places in the data but the hand-written sentences of app_open did
    not name it, and «busca X en Epic» went to installing): every application with places, from the data, as the
    tools' text names them: «Name» (its summary, or its places)."""
    try:
        data = json.loads((_DATA / "app_places.v1.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    named = [f"«{app}» ({body.get('summary') or ', '.join(body.get('places') or {})})"
             for app, body in (data.get("applications") or {}).items()
             if isinstance(body, dict) and body.get("places")]
    return named[0] if len(named) == 1 else ", ".join(named[:-1]) + " or " + named[-1] if named else ""


APP_PLACES_TEXT = _app_places_text()


def _known_applications() -> list[str]:
    """Aid «ear_known_names» (G11, uso real 2026-11-03: «Shbeomac» and «HBO Mac» for HBO Max, a service and not an
    installed application, so not among the ear's hotwords): the applications and services BAXY knows by name, installed
    or not (app_aliases.v1.json, the kernel's ApplicationAliases), for the ear's hotwords beside the installed ones.
    Measured on synthetic speech (OneCore and Supertonic voices, clean and pink noise, Parakeet Ultra at 1.5 per token,
    2026-11-03): services named 115 → 126 of 150 (HBO Max 21 → 28 of 50), installed names 743 → 744 of 1012, names of
    neither 53 → 53 of 100, sentences with no name 3.41 → 3.48 % WER, none inserted, decode p50 the same."""
    try:
        data = json.loads((_DATA / "app_aliases.v1.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [str(name) for name in (data.get("applications") or {}) if str(name).strip()]


KNOWN_APPLICATIONS = _known_applications()


def places_note(application: str) -> str:
    """Aid «app_places_next» (uso real 2026-10-20: seven clicks in Steam's and Epic's web-drawn windows, whose own
    addresses app_open already opens): after a click or a look there fails or is unsure, the places the application
    opens straight at, as a fact; the model chooses. Empty for an application with none."""
    listed = _places_listed(application)
    if not listed:
        return ""
    return (f"\n[Ayuda: {application} también se abre directo en sus lugares, sin pulsar: app_open con appId "
            f"«{application}» y place {listed}.]")


def opened_places_note(application: str) -> str:
    """Aid «app_places_next» (uso-109, N5): the places of the application this turn's app_open opened with no place, said
    with the next turn and not with the opening's result: in the result one of them was told as where it had opened (F26:
    «Abrí Steam en la comunidad», 8/15), and without them the next request looked at a window with nothing to press.
    Held-out (uso-109), 3 seeds: went to the place 3 → 40 of 48; only opening names no place 24 = 24; 36 other second
    requests 34 = 34. With the opening's result as it was: 10 of 48, and 15 of 24 named one."""
    listed = _places_listed(application)
    return f"[{application} quedó abierta en el turno anterior; sus lugares se abren directo, sin mirar: app_open con appId «{application}» y place {listed}.]" if listed else ""


def _app_knows() -> list[dict[str, Any]]:
    """Aid «app_knows» (uso-109): the short facts of an application or a site that a look at its window does not give
    (app_places.v1.json «knows»: its processes, names or hosts, its text, and the date and version it was checked on
    live). Data only: this code names no application."""
    try:
        data = json.loads((_DATA / "app_places.v1.json").read_bytes())
    except (OSError, json.JSONDecodeError):
        return []
    return [entry for entry in (data.get("knows") or []) if isinstance(entry, dict) and entry.get("text")]


APP_KNOWS = _app_knows()
KNOWS_CALLS = {"app.open", "input.visible.controls", "window.active", "browser.navigate"}
KNOWS_DAYS = 180  # what was last checked longer ago than this is not said: better nothing than something old
_VIEW_PROCESS = re.compile(r"\(([\w.\- ]+), window \d+\)")


def _result_identity(observation: str, args: Any) -> tuple[str, str, str]:
    """Who a result is about, never from the person's words nor from the window in front: the process a look or an opening
    says it saw, the host of the address the call was given, and the name the call gave and the result confirmed."""
    shown = _VIEW_PROCESS.search(observation)
    process = shown.group(1) if shown else ""
    named = args if isinstance(args, dict) else {}
    try:
        facts = json.loads(observation)
    except ValueError:
        facts = None
    seen = facts.get("observed") if isinstance(facts, dict) else None
    if isinstance(seen, dict):
        process = process or str(seen.get("processName") or seen.get("process") or "")
    address = str(named.get("url") or "")
    host = (urllib.parse.urlsplit(address).hostname or "") if "://" in address else ""
    return _fold(process), host.lower(), _fold(str(named.get("appId") or named.get("application") or ""))


def knows_note(observation: str, args: Any, today: _dt.date, conv: list[dict[str, Any]]) -> str:
    """Aid «app_knows»: the facts of the application or site this result is about, beside the receipt, while they are not
    still in the conversation (a note stays in the history). Unknown, or last checked too long ago, says nothing."""
    process, host, name = _result_identity(observation, args)
    for entry in APP_KNOWS:
        known = (process and process in {_fold(p) for p in entry.get("processes") or []}) or (
            host and any(host == h or host.endswith("." + h) for h in entry.get("hosts") or [])) or (
            not process and name and name in {_fold(n) for n in entry.get("names") or []})
        if not known:
            continue
        try:
            age = (today - _dt.date.fromisoformat(str(entry.get("verified")))).days
        except ValueError:
            return ""
        told = any(entry["text"] in str(message.get("content") or "") for message in conv)
        return "" if age > KNOWS_DAYS or told else f"\n[Ayuda: {entry['text']}]"
    return ""


# Renew al máximo (w5): the note said «el campo tiene ahora el cursor» with nothing in the result checking it; the focus
# is told only when the result reports it (a field made the text's destination with the keyboard's focus on it).
FIELD_NOTE = ("\n[Ayuda: tras el clic ya no se ve «{label}» y el resultado dice que el clic dio el foco del teclado a un "
              "campo de texto: lo siguiente que se escriba con input_text_type va ahí, sin pulsarlo otra vez.]")
FIELD_NOTE_UNCHECKED = ("\n[Ayuda: tras el clic ya no se ve «{label}»; el resultado no dice dónde quedó el foco del "
                        "teclado: no se comprobó si un campo tiene el cursor. input_text_type escribe donde esté el foco "
                        "de la ventana.]")


def field_note(observation: str, args: str | None) -> str:
    """Aid «field_focused_next» (uso real 2026-10-21, e2e del notebook: Steam's «Buscar en la tienda» pressed four times
    and «no pude escribir» told without typing): a completed click whose label is no longer on screen, as its own
    result says, is told with what the result shows of the focus: a text field with the keyboard's focus when it says
    so («focused»), otherwise that the focus was not checked."""
    try:
        facts, called = json.loads(observation), json.loads(args or "{}")
    except json.JSONDecodeError:
        return ""
    observed = facts.get("observed") if isinstance(facts, dict) else None
    label = called.get("label") if isinstance(called, dict) else None
    if (not isinstance(observed, dict) or facts.get("status") != "completed"
            or observed.get("labelStillOnScreen") is not False or not isinstance(label, str) or not label.strip()):
        return ""
    note = FIELD_NOTE if observed.get("focused") is True else FIELD_NOTE_UNCHECKED
    return note.format(label=label.strip())


# Renew al máximo (w9-dudas, falsedades F013: «abre el bloc de notas, escribe 'prueba 123' y guárdalo en … como
# prueba.txt»): the text typed into Notepad, then file_write wrote the file, and «guardé prueba.txt» was told while
# Notepad's tab stayed «Sin título». The file is what was saved; the window's text is not, and file_write never touches it.
# Replayed (dudas.py, 3 seeds): the answer told the window apart 0/3 → 3/3.
WRITTEN_NOTE = ("\n[Ayuda: file_write escribió {path} directo en el disco, sin pasar por ninguna ventana: lo escrito antes "
                "en «{title}» ({process}) no se guardó con esta llamada.]")


def written_note(observation: str, receipts: list[dict[str, Any]]) -> str:
    """Aid «written_not_window»: a completed file_write in a turn that typed text into a window before it says the file
    was written straight to the disk and that window's text was not saved by it (the window of the last such typing, as
    its result named it). Empty otherwise."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return ""
    observed = facts.get("observed") if isinstance(facts, dict) else None
    if not isinstance(observed, dict) or facts.get("status") != "completed" or not observed.get("fullPath"):
        return ""
    for receipt in reversed(receipts):
        if receipt["tool"] != "input_text_type" or not receipt["completed"]:
            continue
        try:
            sent = (json.loads(receipt["observation"]).get("observed") or {}).get("sentTo")
        except (json.JSONDecodeError, AttributeError):
            sent = None
        if isinstance(sent, dict) and sent.get("title"):
            return WRITTEN_NOTE.format(path=observed["fullPath"], title=sent["title"], process=sent.get("process") or "?")
    return ""


# Aid «next_not_done» (noche R6-NB-1, sesión larga 7db8, T5): audio_app_volume_set failed with a next naming
# audio_volume, no call came after it, and the answer was «lo puse al 15» with the volume where it was.
NEXT_NOT_DONE = "\n[Ayuda: esta llamada falló y lo que dice su next no lo hizo ella.]"


# Aid «vision_estimate» (uso-106, F32: a vision model wrote that a program was probably open and the answer told it as a
# fact): what a vision model says of a capture is its estimate of an image, not a reading of the
# window. What it tells as probable reaches the model marked so; which words say it is not read.
VISION_ESTIMATE = ("\n[Ayuda: esta descripción es lo que estima un modelo de visión sobre esa captura, no una lectura de "
                   "la ventana: lo que da por probable o dudoso se cuenta como probable o dudoso, y sus cifras, tal cual.]")


# Aid «read_after_navigation» (uso real 04-11: browser_navigate unconfirmed after its wait, then browser_page_read of the
# inbox it asked for, and the answer was «no pude ver si la página cargó»; banco app_contradice, 5 of 15): the read comes
# after the wait that gave up, and what it shows is what is open now, whether it is the page asked for or not.
READ_AFTER_NAVIGATION = ("\n[Ayuda: browser_navigate no alcanzó a confirmar la página en su espera, pero esta lectura es "
                         "de después: lo que el navegador muestra ahora es {url}, y eso sí lo viste.]")


def read_after_navigation_note(observation: str, earlier: list[dict[str, Any]]) -> str:
    """READ_AFTER_NAVIGATION for a page read with an address, after a navigation of the turn left unconfirmed."""
    try:
        observed = json.loads(observation).get("observed")
        url = observed.get("url") if isinstance(observed, dict) else None
        if not url or not any("user_browser_navigation_unconfirmed" == json.loads(r.get("observation") or "{}").get("error")
                              for r in earlier):
            return ""
    except (json.JSONDecodeError, AttributeError):
        return ""
    return READ_AFTER_NAVIGATION.format(url=url)


# Aid «memory_off_next» (uso-83, 3/10; encargo A4): asked «¿qué recuerdas de mí?» with the memory off, a memory call fails
# with memory_disabled and the model asked in words whether to turn it on instead of calling memory_enable (which is the
# call that asks the person, RiskPolicy.PrivacyGuardsRequiringConfirmation), and after the person's «sí» it sometimes
# said it had turned it on without calling it. The failure gets the one next that turns it on, as other failures get
# theirs: the call, who answers, and that it is not on until its own result says so. The aid turns on nothing: the
# person's «sí» is still asked by the App. Same shape as the other `next`s (Rasa/ReAct style observation hints).
MEMORY_OFF_NOTE = ("\n[Ayuda: la memoria está apagada (memory_disabled) y esta llamada no hizo nada. Si la persona quiere "
                   "que se lea o se guarde algo, lo que la enciende es {enable} {{}}: esa llamada es la que le pregunta su sí "
                   "(la App), así que no se lo preguntes tú antes en palabras. No digas que está encendida hasta que el "
                   "resultado de {enable} lo diga; un sí a una pregunta tuya no la enciende por sí solo.]")
# The person's words right after BAXY's own question in words, in a conversation where a memory call just failed off: the
# same `next`, for a «sí» that no call waits for (the App has nothing pending, so the mind cannot take it as the answer to
# a confirmation). Which question BAXY asked is not read from its words: only that it ended in «?» (OFFERED_NOTE's own
# shape) and that the memory failed as off since. It asks the person nothing and calls nothing: the model decides.
MEMORY_ON_OFFER_NOTE = ("[Nota interna, no la escribió la persona: la memoria estaba apagada (memory_disabled) y tu última "
                        "frase fue una pregunta. Si lo que dijo es un sí a encenderla, llama {enable} {{}}: la App le "
                        "pide su sí, y hasta que su resultado lo diga no está encendida ni la des por encendida. "
                        "Si dijo otra cosa, atiende eso.]")


def _memory_off(observation: str) -> bool:
    """Whether a result is the failure the memory gives when it is off (its error code, memory_disabled)."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return False
    return isinstance(facts, dict) and facts.get("error") == "memory_disabled"


def _has_next(observation: str) -> bool:
    """Whether a result carries a next of its own (in observed or beside it), whatever it says."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return False
    if not isinstance(facts, dict):
        return False
    observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    told = observed.get("next") or facts.get("next")
    return isinstance(told, str) and bool(told.strip())


# Measured history (PLAN_GENERAL C2, cf29f2510): told at the third, its risk «sondeos legítimos»: a look repeated at a
# window still loading is a probe that completes each time (al máximo 7.7 compares the content too). Holdout v4 (en
# vivo: «Biblioteca» pressed 7 times in Steam, each visible_button_postread_unchanged, 50 s): a call that failed or
# stayed unsure the same way twice is told at the second; a completed one keeps the third, so a probe stays as measured.
SAME_CALL_TOLD = 3
SAME_CALL_FAILED_TOLD = 2
# Auditoría de falsedades: «ya se hizo» is the call's, never its effect's (a click that failed three times read «ya se
# hizo»): the call was made, and its result is said beside it.
SAME_CALL_NOTE = ("\n[Ayuda: {call} ya se llamó {times} veces en este turno con los mismos argumentos y el mismo "
                  "resultado ({outcome}){options}]")
SAME_CALL_OPTIONS = ("; otra vez igual dará lo mismo. Opciones: otra herramienta, otros argumentos, o decir a la persona "
                     "lo que pasó.")
# Review 2026-10-22: in a turn the App closes, the fact alone (it offered another tool beside «no admite más
# herramientas»).
SAME_CALL_CLOSED = "."
# Holdout v4 (the Steam library): a click repeated in an application of the turn that has places says them among the
# options, from the data (app_places.v1.json), as places_note does.
SAME_CALL_PLACES = (" {application} también se abre directo en sus lugares, sin pulsar: app_open con appId "
                    "«{application}» y place {listed}.")


# Aids «same_call_closes» and «look_click_cap» (w9-bucle; int10's long session of the notebook, 2026-10-23: «abre la
# calculadora», then a look and a click on «Sistema» seven times, the menu opening and closing, 35 model calls and 27.9k
# tokens until context_shrunk; same_call_next told the third look once and the model went on): a call the mind does not
# hand to the App. Its result says why, and the model answers in words from what the turn shows. Measured over the
# practice runs of both machines (10,717 turns, holdouts left out):
# - same_call_closes: the call told by same_call_next, written again as the model's very next decision with the same
#   arguments. 79 such repeats: 73 came back the same, and none of the 6 others ended in what was asked. Later in the
#   turn, after another call, it runs: E011 (calculator_window_not_found twice, app_open, then the same sum) completes.
# - look_click_cap: a click after a look the turn already had LOOK_CLICK_PAIRS times (the same look, the same content
#   seen, the same click). A second such pair came in 58 turns: 47 times the same as the first, and in 3 it did what
#   the first had not (Settings' «Sistema», Steam's «BIBLIOTECA» twice). A third came in 27: none of its clicks did
#   anything (each failed, or opened and closed the calculator's menu again) and all 27 answered that they could not.
LOOK_CLICK_PAIRS = 2
SAME_CALL_NOT_RUN = json.dumps({"status": "not_run", "reason": "this same call, with the same arguments, was already "
                                                               "made in this turn and told so above; it was not made "
                                                               "again"})
LOOK_CLICK_NOT_RUN = json.dumps({"status": "not_run",
                                 "reason": f"this click, after the same look that saw the same, was already made "
                                           f"{LOOK_CLICK_PAIRS} times in this turn; it was not made again"})
# Aid «ask_once» (uso real 2026-10-26): the person's answer to ask_user is that call's result, and the model asked the
# same question again at each answer («¿en todo el sistema o en un programa?» six times, «¿qué quieres que recuerde de
# ti?» three): one question per thing (identity: «una pregunta corta, no un interrogatorio»). A question alike to one
# already asked in the turn (ASKED_ALIKE of its letters, folded) is not asked: the model decides again, without asking.
# uso-107i (05-11, G4): the decision bench holds it against this aid (held-out «no sé» 14/20 on, 20/20 off), so it was
# replayed on turns.jsonl on the PC (82 real answers to a question, 3 seeds, today's model): the question comes back
# 42 times of 243 off, 4 on (those 4 in words, not ask_user), and the 8 real echoes and «X o X» are never asked on (21 of
# 24 samples act). A repeat is what the person complained of; a «no sé» asked again is not a wrong answer but a cheap one.
ASKED_ALIKE = 0.9
ASKED_AGAIN_NOT_RUN = json.dumps({"status": "not_run",
                                  "reason": "this question was already asked in this turn and the person's answer is "
                                            "above; it was not asked again: do with that answer what a tool can do, "
                                            "or say in one sentence that you don't do it"})
# The question the model asked in the decision after that one: no other question is asked in this turn.
ASKED_CLOSED_NOT_RUN = json.dumps({"status": "not_run",
                                   "reason": "no other question is asked in this turn; it was not asked: answer the "
                                             "person in words with what is above"})
# Uso real 30-10 → 03-11 (G4): the person's own words came back as BAXY's question («¿qué es WhatsApp?» → «¿Qué es
# WhatsApp?», «¿cómo me llamo en Discord?» → «¿Cómo te llamas en Discord?»), and the next words had to ask again. The
# shape that tells it is See et al. 2019's «partner repetition» (arXiv 1902.08654, §6.1 and appendix D: a reply's
# n-grams found in the partner's last utterance, which their best models block): here the share of the question's
# letters (folded, as ask_once reads them) that the person's last words hold in the same order (difflib's matching
# blocks), letters and not word pairs because a question turns «me llamo» into «te llamas». Measured on the 169 questions
# of turns.jsonl (15-10 → 03-11): at ASKED_ECHO or more, 10, each one the person's words back (4 of them a «¿borro…?»
# the kernel asks anyway); the first that asked for something the person had not said is at 0.74 («¿Qué juego quiere
# comprar en Epic Games?»). Not asked, the model decides again with its tools and may still ask for a datum the person
# did not give (AskBench, arXiv 2602.11199: ask only for what is missing); a second echo in the turn ends it in words.
ASKED_ECHO = 0.8
ASKED_ECHO_NOT_RUN = json.dumps({"status": "not_run",
                                 "reason": "this question repeats back what the person just said: they asked it of you "
                                           "or left it to you; it was not asked: answer it, do it with a tool or look "
                                           "it up, and ask only for a datum they did not give"})
# Encargo 119 (F10): «qué dice esto» with a window open ended in «¿Qué quieres que lea?», nothing looked at. The mind does
# not know what is in front, and the note of encargo 46, always written beside the clock, moved other decisions at the
# gate (e28-B2 8/10 → 3/10). Told only here, on a question about to be asked: no other decision reads it, as ReALM (SIGDIAL
# 2024) gives the model the screen's entities as text for these same references. The App reads the window when the words
# arrive; a title past FRONT_TITLE_CHARS is cut and says so. Measured on 26 phrases, 2 seeds: with the call and no way back
# to the question 18/48 of the questions that had to stay; the fact alone 16/22; this text 21/22, and looks 19/20 (base 1/20).
FRONT_NOT_ASKED = ("this question was not asked: when the person spoke, the window in front was {window}. If their words "
                   "ask what that window says or shows, input_visible_controls {{\"includeText\":true}} reads it; if they "
                   "ask for anything else, ask your question again as it was")
FRONT_TITLE_CHARS = 200
# Encargo 119 (G7): «cuánto saldo me queda en <app>» with that app open went to a web search, to the person's task list or to
# «no puedo ver»: a name the model does not know reads as anything but a window on this PC. A note only on a turn whose words
# name an open window (the App compares the words with the titles, NetworkEgress.Named), so no other decision reads it.
# Measured on 12 phrases with invented apps, 2 seeds: base 2/24; only the windows named 8/24; with how to read them 14/24, and 18/18 controls.
# ALR1 (owner, 2026-11-08: «Baxi, gracias… Baxi para la alarma, tipos como funcionan de Alexa»): what rings now in the
# App, told with the person's words, as a ringing alarm is the context a smart speaker answers «stop» or «snooze» in
# (Google Nest Help, «Set and manage alarms»: «Stop a ringing alarm: 'Stop'… 'Snooze for 10 minutes'»). The model reads
# what rings and decides; the words are never matched here.
RINGING_NOTE = ("[Nota interna, no la escribió la persona: ahora mismo suena o espera respuesta en este PC {rings}. Como con "
                "un despertador o Alexa, si sus palabras la contestan (dan por recibido el aviso, dicen que ya está hecho "
                "o que ya va, o piden que pare), {call} con action stop la para; si piden más tiempo o que "
                "avise de nuevo más tarde, con action snooze la pospone (inMinutes, o at con la hora; 10 minutos si no "
                "lo dicen); con su id. Sólo queda parada o pospuesta si llamas a {call}. Si piden otra cosa, sigue "
                "sonando.]")
# ALR5 (M1, the model's part): after BAXY's own question in words the rule keeps out, and the stock model, told above that
# words like «ya» or some minutes answer what rings, gave it the answer itself: «¿Te envío el correo?» → «sí, dale»
# stopped the alarm and sent nothing. Stops and snoozes nobody asked for, 3 seeds: on 10 phrases written blind 12 of 30
# with the note above, 0 with this one, and «¿La paro?» → «sí, dale» stopped or snoozed 24/24 (21 before); on the first 19
# phrases 27 of 57 → 11 (base, with the rule, 23), asked-for ones 21/21. With no note of what rings after a question, 0 of
# 57, but the asked-for ones fell to 10/24 with cancels tried. A turn after a question is read as its answer (Alexa Skills
# Kit, Dialog Interface Reference; Dialogflow ES, follow-up intents). Which question it was is the model's to read.
# ALR5's blind review: that first note («only if they name it or ask to stop it») left an acknowledgement after an
# unrelated question ringing: «Baxy, gracias, ya me levanté» after «¿Algo más?» stopped it in 11 of 30 (24 with the rule).
# This one says an acknowledgement stops it, a snooze only when asked for, and a time, minutes, a yes or a no that answer
# the question are the question's: acknowledgements 25/30, answers to the question 1 of 30 stopped, «¿En cuántos
# minutos?» → «10 minutos» set the timer 3/3 (with «más tiempo» → snooze it snoozed what rang 3/3).
RINGING_ASKED_NOTE = ("[Nota interna, no la escribió la persona: ahora mismo suena o espera respuesta en este PC {rings}. Como "
                      "con un despertador o Alexa, si sus palabras dan por recibido el aviso (agradecen, dicen que ya está "
                      "hecho o que ya va) o piden que pare, {call} con action stop la para; si piden explícitamente "
                      "posponerlo o más tiempo para eso, con action snooze la pospone (inMinutes, o at con la hora; 10 "
                      "minutos si no lo dicen); con su id. "
                      "Pero tu último mensaje terminó en una pregunta: una hora, unos minutos, un sí o un no que la "
                      "contestan son para lo que preguntaste y no tocan lo que suena (salvo que preguntaras por lo que "
                      "suena). Sólo queda parada o pospuesta si llamas a {call}.]")
# ALR1: a turn told what rings that ends in words with nothing stopped or snoozed. The stock model said «lo he parado» with
# no call (held-out bench: 12 of the stop samples): it is told the fact, once, before its words are spoken, with its tools
# (as the other checks of the answer); what it writes or calls then is its own.
RINGING_STILL_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo. En este turno no se paró "
                      "ni se pospuso nada: {rings} sigue sonando o esperando respuesta. Responde de nuevo a la persona "
                      "según lo que pidió.]")
NAMED_NOTE = ("[Nota interna, no la escribió la persona: sus palabras nombran estas ventanas abiertas en este PC: {windows}. "
              "Si preguntan por un dato que esa ventana muestra, puedes verlo: input_visible_controls con su application y "
              "includeText.]")
# Uso real 04-11 14:32 (F28): «¿X o X?» about a game, with no entry and no call of that name anywhere in the session, to
# a request for a joke about it. Whichever the person says, nothing is told apart. A question that ends in the same words
# twice with «o» between them: 2 of the 179 questions of turns.jsonl (15-10 → 04-11), this one and one with two windows of
# that name open, where the answer could not tell them apart either: reading them gives what differs. uso-127 (real use
# 05-11): any word between them was taken for the choice, so a story asked for after «¿en qué te ayudo?» got
# «¿Sobre qué cuento te cuento?» refused twice, which closes the turn in words with no way to ask, and those words came out
# as an order («Cuenta un cuento de…», 4/5, base 0/5). «o» is the grammar of offering two things, not a reading of them.
_OR = frozenset({"o", "u", "or"})
ASKED_SAME_NOT_RUN = json.dumps({"status": "not_run",
                                 "reason": "this question offers the same thing twice, so its answer would tell nothing "
                                           "apart; it was not asked: if there really are two, read them and ask by "
                                           "what differs (their titles, their accounts); if not, do what the person "
                                           "asked"})
# Uso real 02-11 21:15 (G10): BAXY offered «Diarios de Vampiros» in its question and the person said «dime un cuento»; the
# words reached the model as the question's answer, and it played the offer. Aid «answer_or_new»: the answer says it may
# be a new request, as a dialogue state tracker reads each person's turn beside the system's last one to decide which
# intent is active (Schema-Guided Dialogue, arXiv 1909.05855, §5.1). Aid «offer_unanswered»: a form's requested slot is
# filled only by an answer that holds it, and otherwise its action is rejected and the conversation handles the
# digression (Rasa, «Writing Stories / Rules for Unhappy Form Paths», ActionExecutionRejection); here, a call with an
# effect whose value only BAXY's question said, the person's words of the turn never, does not run once, and the model,
# told so, decides again: whether «sí» or «esa» chose it is its reading (identity: no interrogation, no guessing).
ANSWERED_NOTE = ("\n[Nota interna, no la escribió la persona: es lo que dijo tras tu pregunta; puede contestarla o ser "
                 "un pedido nuevo, y si es un pedido nuevo, atiende ese y deja lo que ofrecías.]")
# Aid «choice_left» (encargos 46 and 46c): offered three things in words («¿qué te tinca?») and told to choose itself, the
# model asked the same again or said it cannot choose for the person. The words after BAXY's own question in words get a
# note as those after ask_user's do (ANSWERED_NOTE), which also names the choice left to BAXY: dialogue state tracking
# writes it as a filled slot, «dontcare» (DSTC2, Henderson et al., SIGDIAL 2014; MultiWOZ, arXiv 1810.00278), read beside
# the system's last act (Schema-Guided Dialogue, arXiv 1909.05855). Whether they follow a question is told by the shape of
# BAXY's last message (a question mark), never by the person's words. Held-out pairs, 5 seeds, AMD server: after an offer
# 30/40 -> 35/40. The same reading as a sentence of rule 3 (encargo 46) also helped after ask_user, but any change of the
# system prompt moved the decisions at the edge of the decision bench (e28-B2 8/10 -> 1-3/10, or R09 and e35-H-R09a down
# with a shorter sentence); this note is only in a turn after BAXY's question, so the bench does not move; the clause in
# ANSWERED_NOTE gained one pair after ask_user and lost another (30/40 both), so ANSWERED_NOTE stays (INFORME_46b).
# uso-107 (S08): after an open question that offered nothing («Buenas tardes, ¿en qué te ayudo?»), that note had a whole
# request with its datum read as an answer to weigh, and the model asked for what it said: «en el traductor escríbeme en
# el cuadro "dónde queda la estación"» → «¿Qué texto quieres que escriba?», 0/5 against 5/5 after the same greeting
# without «?» (S08-saludo0, -saludo3, D4: 0/15 → 15/15 with the aid off). It says now what to do, not what the words may
# be: a request is attended as any other, a choice left is made. Cases after a question of BAXY's in words (tras_saludo
# and the held-out tras_pregunta_abierta, 5 seeds, the same day): 110/140 → 130/140, controls 59/75 → 61/75 (the
# choices left to BAXY 25/30 → 30/30). «hazlo con lo que dice» alone, without «pregunta sólo un dato que no dé», lost 8
# of 30 controls that lack a datum. uso-107i: without «si la contesta, sigue con eso», a «sí» that repeats what it agrees to
# read as a new request and got told done with nothing to do (u92-H5 10/10 → 5/10); with it, and «si pide algo completo,
# hazlo; si le falta un dato, pregúntalo» for what was in parentheses, u92-H5 9/10, u107-QB1 7/10 → 9/10, u107-QB5 4/10 →
# 8/10 (10 seeds; the same day's other wordings lost the requests or the controls). What it still costs: u107-QB6
# («escrivelo en el cuadro de busqueda», no datum) 7/10 → 1/10, typing those words.
CHOICE_ANSWER = "si te deja la elección a ti, elige tú, hazlo y di qué elegiste"
OFFERED_NOTE = (f"[Nota interna, no la escribió la persona: tu último mensaje terminó en una pregunta. Si lo que sigue "
                f"la contesta, sigue con eso; si pide algo completo, hazlo; si le falta un dato, pregúntalo; "
                f"{CHOICE_ANSWER}.]")
OFFER_NOTE = ("[Nota interna, no la escribió la persona: {call} no se ejecutó. Usaba {values}, que sólo dijiste tú en "
              "tu pregunta; la persona no lo repitió. Si lo que dijo elige eso, vuelve a llamarla; si pide otra cosa, "
              "haz lo que pide ahora.]")
# Aid «say_once» (uso real 2026-10-26): the same words came back turn after turn (the same greeting three times, the
# same «¿te refieres a algo más?» to whatever followed; after searches that all failed, the answer of the turn before
# as if they had found it). An answer that is BAXY's last answer again, letter for letter, in a turn where no call
# completed, is written once more with this note, words only.
SAID_AGAIN_NOTE = ("[Nota interna, no la escribió la persona: ibas a responder exactamente lo mismo que tu respuesta "
                   "anterior. No la repitas: responde a lo que dice ahora la persona, con otras palabras.]")
# Aid «dated_search» (feria 2026-10-27): after «conversación nueva» the model answered every question about something of
# a given year from memory (mundial 2022 «Francia», Copa América 2021 «Chile», Balón de Oro 2023 «Mbappé»: 3 of 5 wrong);
# a sentence in rule 5 alone did not hold past a few answers from memory in a row. The question with one number, a year,
# or a curiosity asked for, answered in words with nothing looked at, is decided once more with this note; the model still
# chooses.
DATED_NOTE = ("[Nota interna, no la escribió la persona: pide un dato concreto (de un año, una curiosidad o algo con "
              "nombre propio), y esos datos de memoria se confunden. Búscalo con web_search y responde con lo que "
              "encuentres.]")
_YEAR_ALONE = re.compile(r"^\D*(?<!\d)(?:1[5-9]|20)\d\d(?!\d)\D*$")
# A curiosity asked for (feria 2026-10-27, «cuéntame un dato curioso…» from memory: «el estribo, en el pie»).
_CURIOUS = re.compile(r"\b(?:datos? curios[oa]s?|curiosidad(?:es)? (?:de|del|sobre|acerca)|algo curioso|fun facts?)\b")
_ASKS = re.compile(r"^\W*(quien|que|cual|cuales|cuando|cuanto|cuantos|cuantas|donde|como|who|what|which|when|how|where)\b")
# Aid «named_fact» (feria 2026-10-27): what a local brand is, answered in words from memory as another kind of
# product, with no doubt to read (p_call 0.05). Words that repeat a name the person wrote with a capital, past the start
# of a sentence, say something of a thing with a name of its own: a form, not what was asked. System One judges then,
# between those words and web_search, what the person asked for; only its web_search is looked up (_look_up_first).
# PC-L, decision v11 2026-10-27: a capital, the letters of an acronym or what was opened, said with a name, went to the
# web as well; only a question about what or who the named thing is, or asking to be told of it, is judged: at the
# start, after a sentence or a comma, or after one word (by voice there is seldom a comma: «oye qué es…»).
_ABOUT = re.compile(r"(?:^|[,;:.!?])\W*(?:[^\W\d_]+ )?(?:(?:que|quien(?:es)?) (?:es|son|era|eran|fue|fueron)"
                    r"|(?:hablame|cuentame) (?:de|del|sobre|acerca)|que sabes (?:de|del|sobre)|conoces"
                    r"|(?:what|who)(?:'s| is| are| was)|tell me about|do you know)\b")
_SENTENCES = re.compile(r"[.!?¿¡:;\n]+")

_WORDS = re.compile(r"[^\W\d_][\w'&-]*")
_TOLD = re.compile(r"[^.!?]+[.!?]*")


def _asked_about(text: str) -> str:
    """The folded word that closes a question about what or who something is (_ABOUT), when it is a few words long;
    empty otherwise. PC-L, decision v6 2026-10-27: the author of a book named before, or a word in a language, went to
    the web: the named thing has to be what is asked about («qué es el jugo X», not «quién es el autor» of X)."""
    folded = _fold(text)
    about = _ABOUT.search(folded)
    if about is None:
        return ""
    clause = _WORDS.findall(re.split(r"[,.;:!?¿¡]| (?:y|e|o|and|or) ", folded[about.end():], maxsplit=1)[0])
    return clause[-1] if 0 < len(clause) <= 4 else ""


SAME_CALL_REFUSED = "no se ejecutó: la misma llamada otra vez tras el aviso"
FLIP_REFUSED = "no se ejecutó: deshacía lo que otra llamada de este turno ya había hecho"


def flip_not_run(before: dict[str, Any], now: dict[str, Any]) -> tuple[str, str]:
    """The result and the facts line of a call «flip_closed» did not make: that it did not run, the values it would have
    set (notMade) and the ones the earlier call of the turn set, which stay (stays). Uso real 2026-11-03 03:31:34: muted
    false ran, muted true was not made, and the answer told them the other way round («lo dejé silenciado… luego lo volví
    a activar»), the result saying only that a call was not made. Anthropic, «Writing effective tools for agents»: a
    result gives the agent the high-signal context it acts on, not a bare status."""
    turned = [k for k in now if isinstance(now[k], bool) and now[k] != before.get(k)]
    stays = {k: before[k] for k in turned}
    result = json.dumps({"status": "not_run", "reason": "this call would turn back what an earlier call of this turn "
                                                        "set; it was not made, and what that call set stays",
                         "notMade": {k: now[k] for k in turned}, "stays": stays}, ensure_ascii=False)
    return result, FLIP_REFUSED + "; sigue " + ", ".join(f"{k}={json.dumps(v)}" for k, v in stays.items())
# Feria 2026-10-27 (the same volume set four times in a row, the last three «unchanged»): a call that acted and came back
# unchanged in this turn showed that making it again changes nothing; the same call again is not made, and its result
# is the first one's. One that changed something each time (a key, a digit) runs again.
UNCHANGED_NOT_RUN = {"status": "not_run", "reason": "this same call, with the same arguments, already came back "
                                                    "unchanged in this turn; it was not made again: its first result "
                                                    "is in «earlier»"}
UNCHANGED_REFUSED = "no se ejecutó: la misma llamada ya había vuelto sin cambios en este turno"
LOOK_CLICK_REFUSED = f"no se ejecutó: la misma mirada y el mismo clic ya iban {LOOK_CLICK_PAIRS} veces"
# Aid «close_unsaid» (feria 2026-10-27, «abre el bloc de notas y escribe …», 3 of 4 runs, the base too): after typing
# and a look, a click on «Cerrar» and on the «Sí» of what it asked, and the Notepad the person was shown closed. A click
# whose label closes or quits, in a turn whose words say nothing of closing, is not handed to the App.
CLOSE_NOT_RUN = json.dumps({"status": "not_run", "reason": "the person did not ask to close anything; this click on "
                                                           "what closes was not made"})
CLOSE_REFUSED = "no se ejecutó: la persona no pidió cerrar nada"
# Minimizing too: after «ahora escribe debajo la fecha de hoy» a click on the window's «Minimizar» (1 of 3 runs).
_CLOSES = re.compile(r"^\W*(?:cerrar|close|salir|exit|quit|minimizar|minimize)\b")
_CLOSE_SAID = re.compile(r"\b(?:cierr\w*|cerr\w*|clos\w*|sal|salir|sali\w*|quit\w*|exit\w*|minimi\w*)\b")
# Aid «unopened_app» (feria 2026-10-27, case 13, «escribe en el bloc de notas hola quién eres» with Notepad not open; a
# live test the same day): the model typed with no window and the text went to whatever window was in front, BAXY's at
# the fair, a window of the person's own in the live test (its receipt said sentTo that window, completed). A typing or a
# key with no window and no field, in a turn whose words name an installed application (catalog.configure's, self.names)
# that no completed call of the turn opened, focused, resolved or acted on, is not handed to the App: its result says so,
# as data, and the model decides again with its tools. Once per turn: a name of the catalog may be a plain word of what
# was said («el cursor», «un correo»), so the model's next typing or key runs as it is.
# PC-L, decision v6 2026-10-27: «escribe … donde tengo el cursor» was held for an app named Cursor and the model opened
# it. A name is where the text goes only said as a place: after «en», «in», «on», «into», «a(l)», «del» or «dentro» and up
# to three words («en un documento de …»); the name's own words are marked \0 in the folded words before the search.
_PLACE = re.compile(r" (?:en|in|on|into|al|a|del|dentro)(?: [^ \0]+){0,3} \0 ")
WRITES_TO_FRONT = frozenset({"input_text_type", "input_key_press"})
OPENS_WINDOW = frozenset({"app_open", "window_focus", "window_resolve"})  # and any completed call that is not a read
TARGET_ARGUMENTS = ("window", "windowId", "index")  # a window, or the field of the last look: not the window in front
UNOPENED_REFUSED = "no se ejecutó: la ventana de la aplicación nombrada no se había abierto ni enfocado en este turno"
UNSEEN_REFUSED = "no se ejecutó: ningún resultado había mostrado la ventana adonde iba"


# I9 (I7's blind judge, A2-TY3 seed 1): a held typing told only where it would go («with no window this call goes to the
# window in front», and that window by name) was answered «I typed hello in Notepad». The App's own typing and key
# results say in «delivered» whether the keys reached a window (WindowsDesktopInteractionAdapter); a held one says it
# too, false, and its reason says first that nothing was typed or pressed, then where the call would have gone. I9 bench
# (forced held typings, blind judge): such a claim right after the hold, 9 of 173 answers before, 0 of 165 after;
# «delivered» alone left 3 of 88, and «this call was not made» first without the sentence on what was typed, 1 of 91.
NOT_DELIVERED = "this call was not made: nothing was typed or pressed in any window. "


def _not_delivered(reason: str, **given: Any) -> str:
    """A held typing or key's result: not run, nothing delivered, why, and the data it names."""
    return json.dumps({"status": "not_run", "delivered": False, "reason": NOT_DELIVERED + reason, **given},
                      ensure_ascii=False)


def unopened_not_run(applications: list[str]) -> str:
    """The result of a typing or a key held by «unopened_app»: why, and the applications the person's words name."""
    return _not_delivered("The person's words name this application, and no call of this turn opened or focused its "
                          "window: with no window this call would have gone to whatever window is in front. If the "
                          "text is for that application, open it first with app_open (or bring it to the front with "
                          "window_focus) and write there; if it is not where the text goes, make the call again",
                          application=applications)


# I7 (AMD A2, 06-11, TY1-3 and KP1: 12 of 12 samples): «escribe … en la ventana de <app>», the app neither installed nor
# open and another window in front, was typed at once with no look: with no window, into the window in front; or with a
# window number no result had shown («window»: 1, which the schema takes). A window no result showed is the form compared,
# never the words: a window number absent from every result of the conversation, or, with no window, the window in front
# as the App read it when the words arrived (encargo 119) when no result showed its process or title and no call of the
# turn acted. Once per turn, with «unopened_app»: the model's next typing or key runs as it is.
_SHOWN_WINDOW = r"window\w*\W{{1,4}}{number}(?!\d)"
NOT_RUN_MARK = '{"status": "not_run"'  # a result the mind wrote for a call it did not make: nothing it shows was seen
# I12 (R4's review of I9, A3): the title or process in front was found as any whole word of any result, so the «"code"» of
# a web search showed VS Code (process «Code») and a typing for an app that is not there went into it. A window is shown
# by the fields that name a window in a result (window_active, window_resolve, app_open, a typing's sentTo), or by the
# form a look writes it in: «title» (process, window N). I13 (R5's review of I12, R5-3 and R5-6): only in the result of
# a call that completed. A lookup that failed found nothing under the name looked for, and listed every window open, the
# one in front among them (WindowControlHandlers.Candidates: «resolve it again by its process»): «escribe hola en la
# ventana de Zumbalo» was looked for, and the typing with no window that followed went into the window in front unheld.
# A failed audio call names the person's browser («personBrowser») the same way, and showed its window.
WINDOW_FIELDS = {"title": "title", "windowTitle": "title", "process": "process", "processName": "process"}


def _shows_window(front: dict[str, Any], contents: list[str], completed: bool = True) -> bool:
    """Whether the result of a call that completed names the window in front by its title or its process, in a field
    or in the form of a look; with ``completed`` false, any result does (one that failed, or the mind's own not_run)."""
    wanted = {key: _fold(str(front.get(key) or "")) for key in ("title", "process")}
    title = str(front.get("title") or "").strip()
    cut = title[:FRONT_TITLE_CHARS] + "…" if len(title) > FRONT_TITLE_CHARS else title
    written = [f"«{_fold(cut)}»"] if title else []
    if wanted["process"]:
        written.append(re.compile(rf"» \({re.escape(wanted['process'])}[,)]"))

    def shows(node: Any) -> bool:
        if isinstance(node, dict):
            return any(isinstance(value, str) and WINDOW_FIELDS.get(key) and wanted[WINDOW_FIELDS[key]]
                       and _fold(value) == wanted[WINDOW_FIELDS[key]] or shows(value) for key, value in node.items())
        if isinstance(node, list):
            return any(shows(value) for value in node)
        if isinstance(node, str):
            text = _fold(node)
            return any(form in text if isinstance(form, str) else form.search(text) for form in written)
        return False

    for content in contents:
        try:
            node = json.loads(content.split(TURN_FACTS, 1)[0])
        except json.JSONDecodeError:
            continue
        # A completed result is kept without its status (_deduplicated: its facts line says it); any other keeps it.
        if isinstance(node, dict) and (not completed or node.get("status", "completed") == "completed") and shows(node):
            return True
    return False


# I12 (R4's review of I9, A1): after the hold the model looked at the window in front by the name the hold gave it and
# typed there (Ctrl+S into Notepad for «el documento de Lumitrak»), the hold being once per turn. The way out is said, and
# the model decides with the person's words (no reader of them here): a window their words name is looked at by its name,
# and one no look shows is not open, so nothing is typed in this one. As DeAction (Ning et al., ICML 2026, arXiv
# 2602.08995) answers a misaligned action before it runs: «structured feedback to guide agents toward corrected,
# task-aligned behavior», not only a block. Measured with the model (I12 bench, held typings forced, 64 cases with 30
# held-out of another hand, 3 seeds): typed or pressed for an app that is not there 79/111 → 64/111, a window number
# nobody showed 6/36 → 2/36, the window in front wanted 23/24 → 23/24; unforced (i7 cases, 5 seeds) «escribe/pulsa» with
# the window in front 34/50 → 39/50, «… en <app que no está>» 40/50 → 37/50. Wordings that held more (79 → 24-43/111)
# cost the window in front 5 to 10 of 24 (answered «no vi la ventana»): not taken.
def unseen_window_not_run(window: Any) -> str:
    """The result of a typing or a key held by «unopened_app» for a window number no result showed."""
    return _not_delivered("No result of this conversation showed this window number, and a window number comes from a "
                          "look at that window (input_visible_controls, «window N») or from app_open («window»). "
                          "Look for the window it is for first and pass the number that look shows; if no look "
                          "shows it, it is not open: say so, and type or press nothing in another window",
                          window=window)


# I13 (R5-2, R5-3): when a failed lookup listed the window in front, or the mind told it (ask_front), «no result
# showed that window» denies what the model read: it says no call found it. Only then: with that wording everywhere the
# model read it as no window open and gave up on the window in front it was asked for (I13 bench, unforced, held-out of
# another hand: «dale enter» 8/8 → 3/8, i7 C-KP 12/15 → 9/15, «No lo presioné: no había ninguna ventana abierta»); after
# ask_front, where the model knows it is open, the window in front wanted stayed 36/39 → 36/39.
def front_unseen_not_run(front: str, mentioned: bool = False) -> str:
    """The result of a typing or a key with no window held by «unopened_app»: the window in front it would have reached.
    ``mentioned``: a result that did not show it (a failed lookup's list, the mind's ask_front) named it."""
    seen = ("no call of this conversation found that window or opened it" if mentioned
            else "no result of this conversation showed that window")
    return _not_delivered(f"With no window it would have gone to the window in front, and {seen}. If it is for that "
                          "window, make the call again as it was: this time it runs. If the person's words name another "
                          "application or window, it is not this one: look at that one (input_visible_controls with "
                          "its name) and pass the window "
                          "number that look shows; if no look shows it, it is not open: say so, and type or press "
                          "nothing in this one", windowInFront=front)


# Aid «said_file_name», I7 (AMD A2, 06-11, L6-ES2: 3 of 3): «crea un archivo llamado nota.txt en la carpeta …\no-existe»
# became file_write to «…\no-existe.txt», a name nobody said, and the reply told it as the file asked for. Only the form is
# compared, as «unopened_app» compares a window: the person's words name a file (a name with an extension) and the path
# writes another of that same extension that neither those words nor any result of the conversation show. Nothing is
# written; once per turn, so the model's next write runs as it is.
_FILE_NAME = re.compile(r"[^\s\\/:*?\"<>|«»“”‘’'`,;()\[\]]+\.([A-Za-z0-9]{1,5})(?!\w)")
FILE_UNSAID_REFUSED = "no se ejecutó: la ruta escribía un archivo que nadie nombró, y la persona nombró otro"


def file_unsaid_not_run(said: list[str], written: str) -> str:
    """The result of a file_write held by «said_file_name»: the names said and the one the path wrote."""
    return json.dumps({"status": "not_run", "reason": "the person's words name the file "
                                                      + " and ".join(f"«{name}»" for name in said)
                                                      + f", and this path writes «{written}», a name neither they nor "
                                                        "any result said: nothing was written. Write the path with the "
                                                        "file they named, keeping every folder they named",
                       "said": said, "written": written}, ensure_ascii=False)


# Aid «said_place», CLI1 (LEG3 on c2a4c76ac, 10-11: 17 of 48 weather requests with no place said became weather_current
# {location: "Santiago"}, the one city of the description's examples, and the reply gave Santiago's weather as the
# person's own). Only the form is compared, as «said_file_name» compares a file name: the location's name (before its
# first comma) has no word in the person's words of the whole conversation nor in any result, not even one alike in
# spelling (an erratum, «London» for «Londres»). Words in another alphabet cannot be compared by form: then it runs. Nothing
# is read; once per turn, so the model's next call runs as it is (the person may have named the place in words this
# cannot match). Without location the adapter reads where this PC is, approximately, and its result says so.
PLACE_UNSAID_REFUSED = "no se ejecutó: el clima pedía un lugar que nadie dijo"


def place_unsaid_not_run(wire: str, location: str) -> str:
    """The result of a weather call held by «said_place»: the place nobody said and the call that reads here."""
    return json.dumps({"status": "not_run", "reason": f"the person did not say «{location}», nor did any result of this "
                                                      "conversation: nothing was read. Without location, "
                                                      f"{wire} reads where this PC is, approximately: call {wire} {{}} "
                                                      "and say which place the weather is of. If the person did name "
                                                      "this place, the same call again reads it",
                       "location": location}, ensure_ascii=False)


def _alike(word: str, other: str) -> bool:
    """Whether two folded words are one name: equal, or of four letters or more and alike in spelling."""
    return word == other or (min(len(word), len(other)) >= 4 and (
        word[:4] == other[:4] or difflib.SequenceMatcher(None, word, other).ratio() >= 0.75))


def _latin_only(text: str) -> bool:
    return all(not ch.isalpha() or "LATIN" in unicodedata.name(ch, "") for ch in text)


# What the model reads at the end of the last result of a turn that takes no more calls.
NO_MORE_CALLS = ("\n[Este turno no admite más herramientas: responde ahora a la persona sólo con lo que muestran los "
                 "resultados.]")


def _flips(before: Any, now: Any) -> bool:
    """Whether ``now`` is ``before`` with only yes/no values turned the other way (the same keys, the rest equal)."""
    if not isinstance(before, dict) or not isinstance(now, dict) or before.keys() != now.keys():
        return False
    turned = [k for k in now if isinstance(now[k], bool) and isinstance(before[k], bool) and now[k] != before[k]]
    return bool(turned) and all(now[k] == before[k] for k in now if k not in turned)


def _call_key(arguments: Any) -> str:
    """A call's arguments as one text, so the same arguments written in another order or with a key left out as null
    are the same call."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return arguments
    if isinstance(arguments, dict):
        arguments = {k: v for k, v in arguments.items() if v is not None}
    return json.dumps(arguments, sort_keys=True, ensure_ascii=False)


def _same_ended(receipt: dict[str, Any], wire: str, arguments: Any, *outcomes: str) -> bool:
    """Whether ``receipt`` is a call of ``wire`` with these arguments that acted and ended in one of ``outcomes``."""
    return (receipt.get("tool") == wire and not receipt.get("read")
            and str(receipt.get("outcome") or "").startswith(outcomes)
            and _call_key(receipt.get("arguments") or {}) == _call_key(arguments))


def _same_done(turn: dict[str, Any], wire: str, arguments: Any, *outcomes: str) -> dict[str, Any] | None:
    """The turn's first call of ``wire`` with these arguments that acted and ended in one of ``outcomes``, or None."""
    return next((r for r in turn.get("receipts") or [] if _same_ended(r, wire, arguments, *outcomes)), None)


def same_call_places(application: str | None) -> str:
    """The places of the turn's application for a repeated click's options; empty for none."""
    listed = _places_listed(application)
    return SAME_CALL_PLACES.format(application=application, listed=listed) if listed else ""


def _places_listed(application: str | None) -> str:
    """The places of an application with what each takes, sorted; empty for none."""
    places = APP_PLACES.get(_fold(application)) if application else None
    return ", ".join(f"{p} (placeValue: {v})" if v else p for p, v in sorted(places.items())) if places else ""


# The provider's count of the same click seen unchanged in a row (WindowsVisibleControlAdapter.RepeatedUnchanged).
REPEAT_KEY = "unchangedInARow"
# A window's single-use handle (WindowsWindowControlProvider.Issue): a new one at every read of the same window.
_WINDOW_HANDLE = re.compile(r"\bwin_[0-9a-f]{32}\b")
_CAPTURE_ID = re.compile(r"\bcapture_[0-9a-f]{32}\b")
# Uso-108 (B4): what differs between two captures of one image: when each was taken, and how a vision server worded it
# (its bytes, captureSha256, are what the description is of).
CAPTURE_MOMENT = {"createdAtUtc", "description"}
CAPTURE_TAKEN = {"captureStartedAtUtc", "captureCompletedAtUtc"}


def _result_key(observation: str) -> str:
    """Al máximo 7.7: the same result is the same content (three looks at a window still loading, each with another view,
    were told «el mismo resultado»), without how long the call took («…Ms»), as the App's TurnClosing compares it.
    Holdout v4: nor a click's own count of its repeats (unchangedInARow) and the «next» that count brings, which differ
    on each repeat of the same unchanged click. Holdout v5 (en vivo, «maximiza Paint»: 13 window.resolve): nor a window's
    single-use handle, new at every read of the same window. Uso-108 (B4): nor a capture's new id, its moment and how
    vision worded it: captures and vision never counted as a repeat, so only the 15 calls or the 90 s ended a loop of
    them; its bytes (sha256, captureSha256) still tell a screen that changed."""
    def only_repeat(node: Any) -> bool:
        return isinstance(node, dict) and REPEAT_KEY in node and set(node) <= {REPEAT_KEY, "next"}

    def untimed(node: Any) -> Any:
        if isinstance(node, str):
            return _CAPTURE_ID.sub("capture_", _WINDOW_HANDLE.sub("win_", node))
        if isinstance(node, dict):
            repeat = REPEAT_KEY in node
            captured = "captureId" in node
            # A result that holds nothing but the count is the same as the first one, which had none.
            return {k: untimed(v) for k, v in node.items()
                    if not k.endswith("Ms") and k != REPEAT_KEY and not (repeat and k == "next")
                    and not only_repeat(v) and k not in CAPTURE_TAKEN and not (captured and k in CAPTURE_MOMENT)}
        return [untimed(v) for v in node] if isinstance(node, list) else node
    try:
        content = json.dumps(untimed(json.loads(observation)), ensure_ascii=False)
    except json.JSONDecodeError:
        content = observation
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

# PLAN_GENERAL C1: an address longer than this reaches the model as a short reference.
LONG_REF_CHARS = 120
REF_PREFIX = "ref:r"
_REF = re.compile(r"ref:r\d+")


def _aids_seen(observation: str) -> dict[str, Any]:
    """The core's aids in a result, by the fields each one writes (ModelAids.cs): for the trace, apart from what the
    model decided after reading them."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return {}
    if not isinstance(facts, dict):
        return {}
    # Renew al máximo (w6, rutas): the App's said_folder (SaidFolders.cs) refused a call that left out the folder the
    # person named, or says where a call routed there (or written again as before) acted.
    said = ({"said_folder": {k: facts[k] for k in ("saidFolders", "next", "saidFolder") if k in facts}}
            if facts.get("error") == "said_folder_left_out" or "saidFolder" in facts else {})
    # Renew al máximo (w7, apps): the App's place_owner (SaidApplication.cs) opened the application of the place asked for
    # instead of the one the model wrote.
    if isinstance(facts.get("placeOwner"), str):
        said["place_owner"] = facts["placeOwner"]
    if not isinstance(facts.get("observed"), dict):
        return said
    observed = facts["observed"]

    def picked(*names: str) -> dict[str, Any]:
        return {name: observed[name] for name in names if name in observed}

    seen: dict[str, Any] = dict(said)
    if facts.get("error") in ("calculator_window_not_found", "calculator_needs_scientific_mode") and "next" in observed:
        seen["calculator_next"] = picked("next")
    if observed.get("setting") == "accessible_mode" and picked("scope", "notAvailableYet"):
        seen["accessible_scope"] = picked("scope", "notAvailableYet")
    if observed.get("placeRequested") and "next" in observed:
        seen["place_unverified"] = picked("next")
    if observed.get("folder") == "baxy_work" and "entries" in observed:
        # Renew al máximo (w5, E020): a look at the working folder (filesystem_list, filesystem_search).
        seen["work_folder_scope"] = picked("folder", "next")
    return seen


_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _when(text: Any) -> _dt.datetime | None:
    """A time the App wrote (ISO, with or without its offset; a reminder's «yyyy-MM-dd HH:mm» is local), or None."""
    try:
        return _dt.datetime.fromisoformat(str(text))
    except ValueError:
        return None


def _span(minutes: int) -> str:
    minutes = abs(minutes)
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{minutes // 60} h" + (f" {minutes % 60} min" if minutes % 60 else "")
    return f"{round(minutes / 1440)} días"


def _relative(due: Any, now: _dt.datetime | None) -> str:
    """Al máximo 10.4 (Test of Time): a reminder's time as its day and hour from the moment and how far it is («hoy
    10:00, en 20 min»), facts the model reads instead of subtracting ISO stamps; as it came when either does not read."""
    when = _when(due)
    if now is None or when is None:
        return str(due)
    if when.tzinfo is None and now.tzinfo is not None:
        when = when.replace(tzinfo=now.tzinfo)  # the App's local time, in the moment's zone
    elif when.tzinfo is not None and now.tzinfo is not None:
        when = when.astimezone(now.tzinfo)
    days = (when.date() - now.date()).days
    day = {0: "hoy", 1: "mañana", -1: "ayer"}.get(days, f"{_WEEKDAYS[when.weekday()]} {when:%d/%m}")
    minutes = round((when.replace(tzinfo=None) - now.replace(tzinfo=None)).total_seconds() / 60)
    far = "ahora" if minutes == 0 else f"en {_span(minutes)}" if minutes > 0 else f"hace {_span(minutes)}"
    return f"{day} {when:%H:%M}, {far}"


def beat_message(context: dict[str, Any]) -> str:
    """What the heartbeat sees, as lines the model reads: the moment, the screen, the PC, what changed, what BAXY
    remembers, the recent conversation and the reminders. Presentation only: every field the App observed is shown."""
    lines = []
    fg = context.get("foreground") or {}
    now = _when(context.get("now"))
    # Al máximo 10.4: the moment as a day and a clock, not an ISO stamp (as it came when it does not read).
    shown = f"{now:%d/%m/%Y %H:%M}" if now else context.get("now", "")
    lines.append(f"Momento: {context.get('weekday', '')} {shown} · la persona está: "
                 f"{context.get('owner_activity', 'desconocido')}")
    if fg:
        lines.append(f"Al frente: {fg.get('title', '')} ({fg.get('process', '')})"
                     + (" en pantalla completa" if fg.get("fullscreen") else ""))
    windows = [f"{w.get('title', '')} ({w.get('process', '')})" for w in context.get("windows") or []]
    if windows:
        lines.append("Ventanas abiertas: " + "; ".join(windows))
    pc = context.get("pc") or {}
    if pc:
        lines.append("PC: " + ", ".join(f"{k}={v}" for k, v in pc.items() if v is not None))
    for title, key in (("Cambios desde el último latido", "events"), ("Lo que recuerdas de la persona", "memory")):
        values = [str(v) for v in context.get(key) or []]
        if values:
            lines.append(f"{title}: " + "; ".join(values))
    history = context.get("history") or []
    if history:
        # Ronda final 45 (regla 3): the older messages left out are said, as the session's own trim says them.
        omitted = int(context.get("history_omitted") or 0)
        shown = f" (los {omitted} mensajes anteriores no se muestran)" if omitted else ""
        lines.append(f"Conversación reciente{shown}: " + " / ".join(
            f"{'persona' if h.get('role') == 'user' else 'tú'} (hace {h.get('ago_min', '?')} min): {h.get('content', '')}"
            for h in history))
    reminders = context.get("reminders") or []
    if reminders:
        # R10.3: one without a time (the App's «y 3 más sin listar») has no empty brackets.
        lines.append("Recordatorios: " + "; ".join(
            f"{r.get('text') or 'sin título'}" + (f" ({_relative(r['due'], now)})" if r.get("due") else "")
            for r in reminders))
    return "\n".join(lines + ["", BEAT_RULES, BEAT_DECIDE])


CLOCK_MARK = "[Reloj:"
# Al máximo W5 (2026-10-23): Qwen3.5's template opens the assistant messages after the last request with an empty
# «<think></think>» block, as it opens the one being generated, and the earlier ones without it. So each new request
# turns the previous turn's calls and answers into another text than the one the slot holds: llama-server keeps the
# cache up to that turn's first assistant message and reads the rest again in turn.decide (falsehood bench of
# 2026-10-22, llama-server.log: a «sí», a «no» or a «¿ya lo borraste?» read 102-348 tokens where their own are ~20-30,
# 120-220 ms more; after a turn that looked at a window, its thousands of tokens of controls too). Once a turn has
# ended, the mind reads its conversation as the next request will show it, while BAXY speaks: the next decision then
# reads only its own words. The model's prompt is the same text; only when it is read changes. BAXY_RENEW_PREFILL=0
# turns it off.
PREFILL_MARK = "[BAXY: lo que diga la persona después]"
# uso-124 (RX 7600, 2026-11-05): a read ahead has the 24 s of any request (LlmServer.REQUEST_SECONDS). At ~100 tokens/s the
# history a web.fetch leaves does not fit them, and with nothing going on with it the next decision read it and ended at
# its own 24 s: the person heard nothing. A prompt cut short leaves in the slot what the server read («n_tokens» at its
# release, in llama-server's log), so with nothing waiting it goes on from there, at most this many rounds per history.
PREFILL_ROUNDS = 5
# Al máximo 8.1 (F015: «¿ya lo cerraste?» → «Sí» with nothing run, 5 of the 10 falsehoods left, which no aid of the
# result touched): the clock also says which calls ran in the session and how each ended, the last ones of a count of
# the session's own (a cut history no longer shows them, and a «none» read from it would be false).
SESSION_CALLS = 8
# The role of the session's own state at the end of an exported conversation (export_session); never a message.
SESSION_STATE = "baxy.session"

# The session's conversation keeps the last turns that fit both bounds; it is only ever cut at a turn's start (the
# model is hybrid: its cache is reused from the front, so the middle of the prompt is edited only where a cut would
# have moved its start anyway: the oldest results that lose their bodies, 1.1).
# P0.11 (noche 27-10): 10 turns, not 8 (see TRIM_TURNS_TO).
HISTORY_TURNS = 10
HISTORY_CHARS = 24000
# Ronda final 44: the context also holds the tool prefix (about 42k of its 49,152 tokens with the descriptions of the
# rondas finales, 37,999 at ff863b47f), so 24,000 characters of history (~7.9k tokens) no longer always fit beside it and
# a turn failed whole. The history keeps the tokens the prefix leaves, less room for the turn: its reply (DECISION_TOKENS)
# and one result (RESULT_TOKENS, the rest).
TURN_ROOM_TOKENS = 3584
# uso-51 (2026-11-03, «aumentar el contexto para tener una conversación decente»): the count and the characters above
# were tuned for ~7.9k tokens of history (24,000 characters, noche P0.2), and they did not grow with the context: past
# them a turn was cut whatever room was left. They grow with the room the context leaves (Mind._bounds), in proportion
# to this, never below.
HISTORY_TOKENS = 7900
# Al máximo 1.4 (2026-10-22): a history past a bound is cut down to this share of every bound, not just under it. A cut
# moves the conversation's start, and the model (hybrid: its cache is reused from the front) re-reads all the history
# after it: 28 % of turn.decide re-read over 500 tokens (p50 761 tokens / 701 ms, p90 2.5k / 1.6 s), and a session at
# its bound cut one turn at every new one. Cut to 60 %, the next turns grow at its end until the bound again.
TRIM_TO = 0.6
# Renew al máximo (w5): a cut also takes the turns down to this share of HISTORY_TURNS (3 of 8), all of them without
# their results' bodies, so the next cut comes six turns later. Each cut re-reads all that is left plus ~500 tokens of
# the prefix (the slot's last checkpoint before the history). Estimated on the measured session's shapes (offline replay
# with the model's chat template, not measured on the model): turn.decide re-reads −3 to −14 % against b84547ed5 on
# that session, −21 % on random 30-turn sessions of its turns; 0.6 here, +1 % and −10 %.
# P0.11 (noche 27-10, offline replay of _trim on the notebook's 12,695 traced turns, not measured on the model): 60 % of
# the cuts came from the count alone and TRIM_TO between 0.4 and 0.8 moved nothing; 10 turns cut to the same 3 (0.3)
# instead of 8 to 3 cut 17 % less often and re-read 12 % less, the next cut eight turns after it (six before).
TRIM_TURNS_TO = 0.3
# Ronda final 45 (regla 3): what is cut is said where the model reads, or it took what is left for the whole session
# («nunca me lo dijiste» about a turn no longer shown).
TRIMMED = ("[Conversación recortada: los {n} turnos más antiguos de esta sesión ya no se muestran; lo que pasó en ellos "
           "no lo sabes]")
# Renew al máximo (w5): a cut turn left nothing of what the person asked or of how its calls ended (a failed delete was
# known only while it was among the clock's last calls). The note of the cut keeps one line per cut turn, the newest
# that fit GIST_CHARS: the person's words and its calls as their turn's facts said them. The note is rewritten only
# when turns are cut, which re-reads the history anyway.
TRIMMED_GIST = ("[Conversación recortada: los {n} turnos más antiguos de esta sesión ya no se muestran enteros; de "
                "{k} de ellos queda sólo lo que pidió la persona y cómo terminó cada llamada:{lines}\nLo demás que pasó "
                "en ellos no lo sabes]")
GIST_LINE = "\n- "
GIST_CHARS = 1200
GIST_WORDS = 100
GIST_NO_CALLS = "sin llamadas"
GIST_NOT_RUN = "no se ejecutó"
# Al máximo 1.1 (2026-10-22): before a cut, the oldest results lose their bodies; their calls and the line of their
# turn's facts (continue_turn writes it last) stay. A turn of 5+ calls held 3.6k tokens (p50): about three turns were
# left. The ids a body carried (windows, controls) are gone with it, and the model is told so (regla 10: look again).
TURN_FACTS = "\n[En este turno: "
COMPACTED = ("[Resultado omitido para que quepa la conversación: los ids de ventanas y controles que traía ya no "
             "valen; si lo necesitas, míralo de nuevo]")
# Renew al máximo (w5): what a kept facts line says of the body it no longer has («su resultado está arriba» after the
# result was left out read as a value the model could still quote), said as it is once the body is gone.
COMPACTED_FACTS = {"su resultado está arriba": "su resultado se omitió",
                   "su after es la ventana de después": "su after se omitió"}
assert "su resultado está arriba" in VERIFICATION["output_only"]
# A read says nothing of its body while it is there (OUTPUT_READ); once the body is gone its line says so, once.
READ_OMITTED = "; lo que vio se omitió"
_READ_KEPT = re.compile(re.escape(OUTPUT_READ) + "(?!" + re.escape(READ_OMITTED) + ")")
# Noche P0.2 (BAXY más torpe con cada mensaje): between cuts every body of the last eight turns travelled whole, up to
# 24,000 characters (~7.9k tokens) beside a prefix of ~38-42k in a context of 53,248, and a result may be 8 KiB (a
# window's controls, a page): the model read what it saw turns ago as much as what it was asked now. A result longer than
# this, of a turn before the newest closed one, keeps only its turn's facts, as a cut leaves it (1.1); by its size and age
# only, never by what it says. The newest closed turn keeps its bodies (the follow-up «el segundo», «¿qué decía?»).
OLD_BODY_CHARS = 1000


def _omitted(facts: str) -> str:
    """Facts of calls whose results lost their bodies, said as they are now (COMPACTED_FACTS)."""
    for told, omitted in COMPACTED_FACTS.items():
        facts = facts.replace(told, omitted)
    return _READ_KEPT.sub(OUTPUT_READ + READ_OMITTED, facts)

# Aid «capture_gone» (MIR1; VIVO3 fila A4, 2026-11-10): the App deletes the captures when a turn ends unless a call waits
# for the person's «sí» (PRV1 PRIV-02 b, MainWindowViewModel.ClearCapturesNoCallWaitsFor), and the next turn's «¿y qué más
# dice ahí?» was answered without a call from the earlier look, as what the screen shows now. A call of an earlier turn
# whose result names a capture («captureId») is told in the clock's calls as the screen of the moment it was taken (the
# capture's own «createdAtUtc») and that its capture is gone, as «clock_omitted» tells a body that is gone; the look's
# body stays (OLD_BODY_CHARS), so «¿qué decía la primera línea?» is still answered from it, as of then.
CAPTURE_GONE = "; su captura ya se borró: lo que mostró es la pantalla de {when}"
# Measured (MIR1 §3, 12 held-out follow-ups × 3 seeds, two blind judges): told only in the clock's list it changed nothing
# (follow-ups that told the old look as the screen now: 9 of 36, as the base); told also as a note of its own just
# before the person's words (where the waiting «sí» and the unsure words go), 3-4 of 36, and it looked again 31 times
# against 27; a question about what was already read («¿qué número era?») looked again 2 of 12 times against 0.
# MIR2 (VIVO5 fila 4: the look went by capture_screenshot + ocr_read): the note names the calls whose results came from
# that capture, as the clock's calls name them, so the text a read gave is tied to the screen of then by its own name.
CAPTURE_NOTE = ("\n[Pantalla: la última captura, de {when}, ya se borró: lo que {shown} es la pantalla de entonces; en "
                "este turno aún no se miró la de ahora.]")
# MIR4 (VIVO8 fila 5, MIR3 §1): with the capture taken in the clock's own minute the note said «de las 22:00 … la
# pantalla de entonces» with the clock at 22:00, and «entonces» read as now (the base looked again 0 of 6 times; a minute
# apart, 5 of 6). The note tells how long ago the capture was taken, from its «createdAtUtc» to the turn's moment
# (_now), so the same minute is not «now» any more; a time it cannot tell as an age (unreadable, ahead of the clock)
# keeps the clock's time.
CAPTURE_AGE_NOTE = ("\n[Pantalla: la última captura se tomó hace {age} y ya se borró: lo que {shown} es la pantalla de "
                    "hace {age}; en este turno aún no se miró la de ahora.]")


def _shown_by(calls: list[str]) -> str:
    """«mostró», or the calls that read one capture: «mostró ocr_read», «mostraron capture_screenshot y ocr_read»."""
    if not calls:
        return "mostró"
    return f"mostró {calls[0]}" if len(calls) == 1 else f"mostraron {', '.join(calls[:-1])} y {calls[-1]}"


def _captures(node: Any) -> list[dict[str, Any]]:
    """The objects of a result that name a capture (its «captureId»), outermost first."""
    if isinstance(node, dict):
        own = [node] if isinstance(node.get("captureId"), str) else []
        return own + [c for value in node.values() for c in _captures(value)]
    return [c for value in node for c in _captures(value)] if isinstance(node, list) else []


def _result_body(content: str) -> Any:
    """A tool message's result as JSON, without its turn's facts and notes, or None when it is not JSON."""
    head = content.split(TURN_FACTS)[0]
    try:
        body = json.loads(head)
    except json.JSONDecodeError:
        body = None
    return body


def _taken_at(created: Any) -> str | None:
    """A capture's «createdAtUtc» as the clock tells the time (local, to the minute), or None."""
    try:
        return f"las {_dt.datetime.fromisoformat(str(created).replace('Z', '+00:00')).astimezone().strftime('%H:%M')}"
    except ValueError:
        return None


def _age(created: Any, now: _dt.datetime) -> str | None:
    """How long before `now` a capture's «createdAtUtc» was («40 segundos», «3 minutos», «2 horas»), or None when it is
    unreadable, has no offset or is ahead of `now`."""
    try:
        taken = _dt.datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        seconds = int((now - taken).total_seconds())
    except (ValueError, TypeError):
        return None
    if seconds < 0:
        return None
    count, unit = ((seconds, "segundo") if seconds < 60 else (seconds // 60, "minuto") if seconds < 3600
                   else (seconds // 3600, "hora"))
    return f"{count} {unit}{'' if count == 1 else 's'}"

# Review 16: the person's own text, when it alone does not fit (decide), keeps its start and the cut is said where the
# model reads it; never cut below this many characters.
CUT_TEXT = "\n[Texto recortado para que quepa el turno: {n} caracteres más de lo que escribió la persona ya no se muestran]"
CUT_TEXT_FLOOR = 500
# P0.10 (noche 27-10): a result past RESULT_TOKENS keeps its start, cut by size and never by what it says, and the cut is
# said where the model reads it: marked here where the kept start ends, and told with its size in the call's facts line
# (RESULT_CUT_TOLD; plan c3: the line says it, so the body no longer says it again).
CUT_RESULT = "…"

# System One, layer 0 (doubt.py): what the model reads when it was not sure of the action it chose. Under BAXY_S1_DOUBT
# (0.4, SYSTEM_ONE); on the 1,839 labelled real requests, below 0.4 held 95 of 210 wrong actions and asked instead of 10
# of 1,530 right ones (phase 0, 2026-10-21).
# How every note that only asks ends (DOUBT_NOTE, DOUBT_OTHER_ASK_NOTE): after it the model writes words only.
ASK_ONLY = "No hagas nada todavía: pregúntale en una frase corta qué quiere exactamente.]"
DOUBT_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a usar "
              "{call}. " + ASK_ONLY)
# Pregunta-eco (noche 2026-10-27): told to ask with no tools, a model unsure of nothing but its own call could only ask
# the request back («¿Quieres que busque…?», «¿Quieres conectarte a la red…?», «¿Quieres cerrar…?»), and a clear request
# became a question (v11, the fair's battery). Layer 0 lets it read the request again with its tools: it does what was
# asked, or asks only what is missing (identity: «una pregunta corta y concreta que desambigua»). System One does not
# hold that reading again (layers 0 and 2), save a call the kernel would run unasked (Mind._unasked, which only asks); the
# kernel's confirmations still apply.
REREAD_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a usar "
               "{call}. Nada se hizo todavía. Vuelve a leer lo que dijo: si pide eso y no cabe otra lectura, hazlo; si "
               "cabe otra lectura o falta un dato, pregúntale en una frase corta sólo lo que falta.]")
# Aid «answer_check» (al máximo, lever 3; answer_check.py): what the model reads when its final answer contradicts the
# turn's results, before it is spoken. Only the facts and what to do with them, never words to say (invariant 5): the
# model writes its answer again, once, with no tools. Offline on the stored practice transcripts it flagged the 11 clear
# falsehoods of the hand-read pc-t2 runs and none of their 232 clean lines (scripts/renew/maximo/chequeo_offline.py).
CHECK_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y no cuadra con los resultados. "
              "{facts} Escribe de nuevo tu respuesta a la persona contando sólo lo que muestran los resultados.]")
CHECK_FACT = "Dice «{said}», pero {fact}."
CHECK_FACTS = 3
# Uso real 2026-11-03 (F4): a decision the model server failed with a 5xx (after its retry) ended the turn mute; the
# owner asks that BAXY say in one sentence that it could not think the answer (Mind._after_server_error).
SERVER_ERROR_NOTE = ("[Nota interna, no la escribió la persona: el servidor del modelo falló (HTTP {code}) al pensar tu "
                     "respuesta, también al reintentarlo, y ese paso no se hizo. Di ahora, sólo con palabras y en una "
                     "frase, que no pudiste pensar la respuesta; si en este turno ya hay resultados, cuenta sólo lo que "
                     "muestran.]")
# The rules of the check that are aids of their own (BAXY_AYUDAS), beside «answer_check» itself.
# What the check finds of how far a reading reached, or of a limit said with a tool at hand, and no act said done: the only
# findings an answer may go out with when the turn's time ran out on writing it again (Mind._check_answer).
SPOKEN_OUT_OF_TIME = ("partial", "named_control", "denial_lookup", "empty_lookup")
CHECK_RULE_AIDS = {"found": "check_found", "read": "check_read", "denial": "check_denial",
                   "already_open": "check_already_open",
                   "stale_state": "check_stale_state", "future_past": "check_future_past",
                   "past_future": "check_past_future",
                   "unmatched": "check_grounding", "recognized_number": "check_recognized_number",
                   "unsourced_number": "check_unsourced", "unopened_page": "check_open_page",
                   "denial_lookup": "check_denial", "empty_lookup": "check_empty_lookup",
                   "weekday_date": "check_weekday_date", "unread_date": "check_weekday_date",
                   "which_way": "check_which_way", "unread_memory": "check_unread_memory",
                   "unbacked_memory": "check_unread_memory", "memory_subject": "check_unread_memory",
                   "memory_off_empty": "check_unread_memory"}
# Aid «check_weekday_date» (VER1, PR-03; answer_check rules «weekday_date» and «unread_date»): an answer that puts a date
# on a weekday the calendar does not («en siete días es el viernes 12»: the 12th was a Thursday), or that tells with its
# weekday a date other than today's that nothing of the turn gave («pasado mañana es martes 10» on Monday the 9th: the
# pair is the calendar's and the date is not the one asked; 6 of 78 answers with the tool at hand). The model is told the
# fact and keeps its tools: system.time works the date out (daysFromToday, month and day, weekday), and which date was
# asked is the model's to read.
DATE_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y cuenta una fecha con su día de "
             "la semana sin que ninguna herramienta la haya calculado. {facts} {time} calcula fechas y días de la semana "
             "(daysFromToday, month y day, weekday): úsala para la fecha que te pidieron y responde con lo que dé.]")
# Aid «check_unsourced» (encargo A2; answer_check rule «unsourced_number»): an answer that tells a number of a calculation
# that nobody gave (the exchange rate the model made up for «cuánto son 50.000 pesos en dólares») or the value it gave.
# The model is told that and its next, a web_search for the real figure, and keeps its tools: a fixed factor of a unit
# it may tell again as it was (the fact says it is its call). Nothing is written for it.
RATE_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y cuenta como cálculo una cifra "
             "que nadie dio. {facts} Si es una tasa o un precio que cambia, el next es buscarlo con web_search y volver "
             "a calcular con lo que diga; si es un factor fijo de una unidad, responde igual.]")
# Aid «check_open_page» (encargo A10, U31 with the fleet's receipts; answer_check rule «unopened_page»): a page asked to
# open gave 404, the search for it was refused and done in the person's browser, its results were read, and the model
# answered «DuckDuckGo found the venv page instead» without opening it (diag-b5bd, 3 of 3). The note says the receipts' fact
# and the person's own words, and what they said is the model's to read: no list of verbs (A12's negation guard did not
# generalize: other verbs of «no la abras» fell 33/33→17/32). Measured (family u31_real, 2 seeds): «si pidió abrir… ábrela;
# si pidió otra cosa, tu respuesta vale» opened 12/12 and kept 13/20 of the controls; the wording here, their words first and
# «do what they said, no more no less», opened 8/8 and kept 7/8, and with 3 seeds 34/45 against the base's 20/45, with the
# «no la abras» of other verbs 24/24. Its tools stay so it may open it.
OPEN_PAGE_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo. La persona dijo: «{request}». "
                  "{facts} Haz lo que la persona dijo, ni más ni menos: si dijo que la abrieras, {how}; si no lo dijo, "
                  "responde igual.]")
# Aid «check_stale_state» (encargo 56; answer_check rule «stale_state»): an answer that tells how something of the PC is
# now with nothing read in the turn, while the last result of that thing says another state (uso real 03-11: «Ya está
# instalado, listo para jugar» after a game_install_named that read «queued», with no call). The model is told what that
# result says and to look, as rule 2 of SYSTEM says, and keeps its tools.
# GUA1 (VIVO13 fila 3a; banco GUA1, K01: «Acabo de guardar que tu perro se llama Chispo.» written again three times
# after CHECK_NOTE): an act told done in a turn with no call at all, which no call of the session did (answer_check rule
# «no_call»). Words only, the model had no result to tell it otherwise (the memory was off) and said it again. Its tools
# stay, as for a denial: it may do the act the person asked and tell its result (memory_save → memory_disabled → the
# offer). It decides; the note asks nothing of the person and calls nothing.
UNDONE_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y cuenta como hecho algo que "
               "ninguna llamada hizo. {facts} Si la persona lo pidió, hazlo ahora con su herramienta y cuenta lo que diga "
               "su resultado; si no, responde de nuevo contando sólo lo que se hizo.]")
STATE_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y cuenta cómo está algo del PC "
              "ahora sin que nada lo leyera en este turno. {facts} Míralo con su herramienta antes de responder.]")
# Aid «check_unread_memory» (MEM1, VIVO12 P1; answer_check rule «unread_memory»): «¿Cuál es mi color favorito?» → «Recuerdo
# que tu color favorito es el azul» in a new conversation with turquesa kept and no memory call (4 of 4 live; 7 of 12 on the
# bench). The model is told that no memory call brought it and which call reads the memory, and keeps its tools, as rule 2
# of SYSTEM says of what nothing looked at; what it does with that is its own call.
def _first_words(conversation: list[dict[str, Any]]) -> bool:
    """Whether the person's words of this turn are the first they said in the conversation (the App's own notes, «[…]», are
    not theirs): only then nothing but a memory call can have brought what they told BAXY before («me dijiste que…» of
    something said three turns up is true)."""
    return sum(1 for m in conversation if m.get("role") == "user" and isinstance(m.get("content"), str)
               and not m["content"].lstrip().startswith("[")) <= 1


MEMORY_READ_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y cuenta como recordado algo "
                    "de la persona que ninguna llamada a tu memoria trajo. {facts} Míralo con {recall} antes de responder; "
                    "si no lo trae, no lo sabes.]")
# Aid «check_denial» (2026-10-25): an answer of a turn with no call that says BAXY cannot do what a tool of the catalog
# does (answer_check rule «denial»: V5E046 «No puedo eliminar carpetas de BAXY-bench», E027, V5E040, V6E015). The model
# is told which tool does it and what its description says, and answers again once; its tools stay, so it may do what
# was asked (whatever it does then is its own call, under the same doubt and confirmations as any other). Offline on the
# 1,968 replies of the c3-*-e2e and ho6-*-e2e-e2e runs (265 of turns with no call): 34 flagged, all false denials by hand
# (V5E046 17, E027 6, V5E040 3, V6E015 3, V6E052 2, and V6E065 3: «¿ya la creaste?» after a call refused for its
# arguments), and none of the 16 other no-call replies that deny something (a coffee, the lights, a pizza, a window of
# Code) (scripts/renew/ayudas/niego_auditoria.py).
DENIAL_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y dice que no puedes hacer algo "
               "que una de tus herramientas hace. {facts} Responde de nuevo a la persona según lo que pidió.]")
# Aid «check_denial» and «check_empty_lookup» (cosecha 04-11 F18, «Indícame cómo publicar en Steam» → «No tengo herramientas
# para abrir Steam…»; F13, «¿sabes algo de X?» → memory_recall → «no tengo nada guardado»; F35, «¿conoces el juego X?» →
# game_installed_named → «no lo veo instalado»; answer_check rules «denial_lookup», «empty_lookup»). What the person wanted
# to know, and whether it was of the world or their own, is theirs to have said and the model's to read: the note says how far
# the look reached and what web_search reaches, with their words, and keeps the tools. A next in those results moved little
# or was followed where it should not be (F13 forced 3/24; F35 22/24 with its controls 18/18→14/18); this note, F13 24/24
# and F35 19/24, with 42/42 in each one's controls (uso-105, family buscar_105).
LOOKUP_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo. La persona dijo: «{request}». {facts} "
               "Haz lo que la persona dijo, ni más ni menos: si preguntó algo del mundo (qué es, cómo se hace, qué pide, "
               "cuánto cuesta), búscalo ahora con {search}; si preguntó por lo suyo o pidió un acto que ninguna de tus "
               "herramientas hace, responde igual.]")
# SIS3 (F1 of REV10, measured in SIS2: 10 of 40 answers that were no yes turned a brake on): whether the person's words
# are their «sí» to the call that waits is the model's to read, in a question of its own with one of three answers.
# Neither the model's confidence (CONFIRM_FLOOR, renew al máximo 2026-10-23) nor a list of yeses (PLAIN_YES, 2026-10-25)
# nor its calling the waiting call again (TPV2, RepeatsTheWaitingCall in the App) told «puede ser», «I guess?» or «sí,
# pero mañana» from a yes. The question holds only that exchange, BAXY's question and their answer (SIS2 arm b: 1 of 40
# no-yes answers read as a yes), and its output is restricted by a GBNF grammar to yes, no or other (llama.cpp
# grammars/README.md). SIS3B, banco (Completo, seed 1): asked instead on the turn's whole conversation, where BAXY's own
# offer stands (a note quoting the exchange, the decision's prefix and tools), it read «puede ser», «I guess?», «eh,
# whatever you think» and «si tú crees...» as yes: 7 of 48 no-yes rows ran (out_v2). It goes apart from
# the conversation the slot holds (LlmServer.ask_apart). The owner's rule (SIS3): in doubt nothing is turned on, so
# leaving the choice to BAXY is other. Only yes runs what waits; anything else is the turn as any other.
# SIS4 (VIVO15: «¿Lo creas?» → «Luego.» created the note, «Puede ser.» turned the web search on 2 of 2): with only yes,
# no and other, the 4B put a delay or a maybe under yes, although the note named both under other. Its answer is now
# what the person's words do, among kinds that each name one (now, no, later, maybe, ask, different, yours), and the
# system text says the rule: only a clear yes to doing it now is now. Only now is their yes. Sonda of the question
# alone (sonda_consulta.py, 155 exchanges of the SIS2 held-out and VIVO15's, product server): VIVO15's three answers
# yes/yes/no → later/maybe/later; no-yes read as yes where something waited 1 → 0 (N084 «bueno, ya, como quieras»);
# yes read as yes 30 → 31 of 31 («please do»). The kinds alone (no rule) kept «puede ser» as now; the rule alone
# (yes/no/other) kept «Luego.» as yes.
THEIR_ANSWER_SYSTEM = ("You read one exchange between a voice assistant and a person. Reply with one word: what the "
                       "person's answer does. Only a clear, unconditional yes to doing it now is now; if there is any "
                       "doubt, it is not now.")
THEIR_ANSWER_NOTE = ("The assistant asked: «{asked}»\nThe person answered: «{said}»\nWhat does the person's answer do? "
                     "now = they accept that the assistant does exactly that, now; no = they refuse it; later = they "
                     "accept it for another time, not now; maybe = they answer maybe, or are not sure, or do not decide; "
                     "ask = they ask something; different = they want something else or only part of it; yours = they "
                     "leave the choice to the assistant.")
# How much of BAXY's last words the note quotes (their end: the question).
THEIR_ANSWER_ASKED = 400
THEIR_ANSWER_KINDS = {"now": "yes", "no": "no", "later": "other", "maybe": "other", "ask": "other",
                      "different": "other", "yours": "other"}
THEIR_ANSWER_GRAMMAR = "root ::= " + " | ".join(f'"{kind}"' for kind in THEIR_ANSWER_KINDS)
THEIR_ANSWERS = ("yes", "no", "other")
# The model's own confirm_pending yes with something waiting, when the question above did not read their words as a yes:
# nothing ran and it still waits (the model may answer what they said and ask again, or do what they asked instead).
NOT_THEIR_YES = json.dumps({"status": "rejected", "error": "not_their_yes",
                            "reason": "their last words are not a yes to the call that waits: nothing ran and it still "
                                      "waits for their answer",
                            "next": "answer what they said; if it still fits, ask them again in one short sentence "
                                    "whether to do it"}, ensure_ascii=False)
NOT_THEIR_YES_REFUSED = "no se ejecutó: lo que dijo no es un sí"
# Layer 2 (system_one.py): the model doubted and the decision model read the request otherwise.
# Pregunta-eco (noche 2026-10-27): 34 of the 65 echoes in the stored runs, 22 of them with the decision model's choice
# the tool expected; it reads again with its tools as after layer 0 (REREAD_NOTE).
DOUBT_OTHER_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a "
                    "usar {call}, pero también podría ser {other}. Nada se hizo todavía. Vuelve a leer lo que dijo: si "
                    "pide una de las dos y no cabe otra lectura, hazla; si caben las dos, pregúntale en una frase corta "
                    "cuál quiere.]")
# C16 (auditoría de la noche): layer 2's question as before pregunta-eco, for a call the kernel would run unasked
# (Mind._unasked): read again, the same call would run, and nobody asked.
DOUBT_OTHER_ASK_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas "
                        "a usar {call}, pero también podría ser {other}. " + ASK_ONLY)
# Al máximo 4.2 (SAGE-Agent): one question per misunderstanding. The person's words right after a doubt question (the
# notes start alike) or an ask_user answer it, and layer 0 does not hold them again: it asked in a loop, with no limit.
# They still go to layer 2 (the decision model and «corrige», with its safeguards).
DOUBT_ASKED = DOUBT_NOTE[:DOUBT_NOTE.index("{call}")]
# P2.43: in Bypass the catalog cannot say whether a call confirms by its arguments (a click on «Enviar» does in normal
# mode, one on «Siguiente» does not), so a doubt that would read again goes to the App as the action with «unsure»
# (_held). The App never runs it: it answers the observation held «would_run_unasked» when the kernel would run that
# exact invocation now without the «sí» normal mode asks for it (the doubt then asks, DOUBT_NOTE), or held HELD_UNSURE
# otherwise (it reads again, REREAD_NOTE); P2.43b: a held outcome it does not know asks too. The mind reads only that
# typed outcome, never the call's words.
UNSURE = object()
HELD_UNSURE = "unsure"
# P2.43b: the reading again after a held doubt may choose another invocation (a click on «Siguiente» weighed, one on
# «Enviar» chosen in doubt on reading again). A reading still under either layer's threshold goes to the App «unsure»
# too when its key (operation and canonical arguments) was not weighed in this turn, at most this many weighings a
# turn; past them its doubt asks, so it never loops and never runs unweighed. The same invocation, weighed, runs.
UNSURE_WEIGHS = 2
# Uso en la feria (2026-10-27): in the noise a short greeting came out in another language or as a word nobody said, and
# the model answered it as said. How sure the ear was of each word (voice.Heard, Parakeet's per-token probabilities)
# reaches the model beside the clock as a fact, as the pending «sí» does: the model decides, in its own words, whether to
# ask the person to say it again.
UNSURE_NOTE = ("[Nota interna, no la escribió la persona: habló por voz y el oído no está seguro de haber oído bien "
               "estas palabras: {words}.]")
# Menos preguntas (2026-10-25): layer 2 asks once too. The answer to its own question went to layer 2 again, which asked
# again at each answer while the decision model read it otherwise, with no limit; that answer may still be corrected.
DOUBT_OTHER_ASKED = DOUBT_OTHER_NOTE[DOUBT_OTHER_NOTE.index("{call}") + len("{call}"):DOUBT_OTHER_NOTE.index("{other}")]
# Layer 2 «corrige» (BAXY_S1_CORRECT=1): when the decision model chose another tool and it is one of these risks, the
# model fills that tool's arguments (LlmServer.fill_call) instead of asking. Simulated on the 156 held-out real requests
# (2026-10-22): right 140 → 148, wrong actions run 10 → 3; forced arguments where Qwen had chosen otherwise 14/15. Any
# other risk still asks: the core authorizes, and a riskier tool it would run unasked is never put in the model's mouth
# (below: what it confirms). Al máximo 5.1: nor
# one with an effect of the catalog (keys, clicks or commands to a window that may be the person's; what the model wrote
# sent out of the PC; a radio, a network, a pairing, airplane or display mode changed), whatever its risk: a call the
# model did not choose never lands there. A catalog without the field (the measurement catalogs saved before it)
# corrects by risk alone, as before.
# Al máximo, System One 3: also the risks the kernel always confirms in normal mode (RiskPolicy.Evaluate: work_loss and
# installation and recoverable_delete are Irreversible there), because its confirmation names the exact action and
# replaces the vague question (P215 «desinstala el Worms»: Laya read game_uninstall_named at 0.91 and BAXY asked what to
# do). Not external_communication: normal mode confirms only four of its operations. Not system.power, which the kernel
# runs unasked or not by its action (RiskPolicy.EndsTheSession: this catalog cannot say which), and none of them in Bypass,
# which runs them unasked too (nothing asks there since the owner's decision of 2026-11-02, repeated 2026-11-07); a mode
# that cannot be read counts as Bypass. With _founded and the effects rule, as for the rest.
CONFIRMED_RISKS = ("work_loss", "installation", "recoverable_delete")
CORRECTABLE_RISKS = ("read_only", "low_reversible", *CONFIRMED_RISKS)
UNCONFIRMED_OPERATIONS = ("system.power",)


def _bypass() -> bool:
    """Whether the kernel's confirmation mode is Bypass, as ConfirmationModeStore reads it: the file «confirmation-mode»
    of the data root (BAXY_DATA_DIR, or %LOCALAPPDATA%\\BAXY\\1), «bypass» or «all»; no file or another word is normal.
    Read at each correction, as the engine reads it at each invocation: the switch can change between turns."""
    root = os.environ.get("BAXY_DATA_DIR", "").strip() or str(Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "1")
    try:
        word = (Path(root) / "confirmation-mode").read_text(encoding="utf-8-sig").strip().lower()
    except FileNotFoundError:
        return False
    except (OSError, UnicodeDecodeError):
        return True  # unreadable: «corrige» puts no confirmed risk in the model's mouth
    return word in ("bypass", "all")


# System One as the benches certified it (phase 0): ask under 0.4 of confidence (layer 0), consult the decision model
# under 0.6 (layer 2), and let it correct a harmless call («corrige»). Entrega 1.1.0 (2026-10-25): scripts/run_renew.cmd
# set them, so BAXY installed and opened from the Start menu decided without System One; now they are the mind's own.
# A variable still sets its value for a bench's arm (empty or 0 turns that layer off), and the owner's switch
# %LOCALAPPDATA%\BAXY\renew\system_one.off (scripts\system_one.cmd off) turns all three off. The App gives no decision
# model (uso-116, MindRuntimeDiscovery): layer 2 runs only where a launcher or a bench gives BAXY_S1_GGUF.
SYSTEM_ONE = {"BAXY_S1_DOUBT": "0.4", "BAXY_S1_VETO": "0.6", "BAXY_S1_CORRECT": "1"}


def system_one_off() -> bool:
    """Whether the owner switched System One off (scripts/system_one.cmd off)."""
    return (Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "system_one.off").exists()


def _system_one(name: str) -> str:
    """A System One setting: the environment's when the variable is there, else its default (SYSTEM_ONE), none with
    the owner's switch off."""
    value = os.environ.get(name)
    if value is None:
        return "" if system_one_off() else SYSTEM_ONE.get(name, "")
    return value.strip()


def _threshold(name: str) -> float:
    """A System One threshold (BAXY_S1_DOUBT, BAXY_S1_VETO), _system_one's; 0 turns that
    layer off."""
    try:
        return max(0.0, min(1.0, float(_system_one(name) or 0)))
    except ValueError:
        return 0.0


NOT_RUN = json.dumps({"status": "not_run", "reason": "the turn ended before this call ran"})
# RUT7: what the model reads as the result of its own baxy.routines call (it opens the guide; _result), and how long the
# guide waits for an answer before it is dropped with nothing saved (seconds).
GUIDE_OPENED = json.dumps({"status": "completed", "observed": {"guide": "opened", "saved": False}})
GUIDE_SILENCE_S = 300.0
# Review 2026-10-22: a call queued behind one that did not complete was chosen on what that one would have done (app_open
# failed and input_text_type then typed into the person's own window): it is not run, and the model decides again.
NOT_RUN_AFTER = json.dumps({"status": "not_run", "reason": "the call before it in this turn did not complete"})
# I12 (R4's review of I9, B1): a key queued behind a held typing («escribe hola y pulsa enter») said only that, with no
# «delivered»: a typing or a key that did not run says nothing reached a window, as the first one (I9), and as Anthropic's
# computer use tool answers every later action of a batch («Not executed: an earlier computer action in this turn failed»).
NOT_RUN_AFTER_KEYS = json.dumps({"status": "not_run", "delivered": False,
                                 "reason": NOT_DELIVERED + "the call before it in this turn did not complete"})


def _status(observation: str) -> str | None:
    """The status a result says it ended with, or None when it is no JSON object."""
    try:
        facts = json.loads(observation)
    except (TypeError, ValueError):
        return None
    return str(facts.get("status")) if isinstance(facts, dict) else None


def _not_run_after(call: dict[str, Any]) -> str:
    """The result of a call queued behind one that did not complete."""
    return NOT_RUN_AFTER_KEYS if call.get("wire") in WRITES_TO_FRONT else NOT_RUN_AFTER
# A call the App was already running when its turn ended: it may have run, and nothing says what it did (audit
# 2026-10-15: the model read «not run» for a call the core had executed).
NO_RESULT = json.dumps({"status": "unknown", "reason": "no result came back for this call: it may have run or not"})
NO_RESULT_RAN = "sin resultado: pudo o no ocurrir"  # the same, among the session's calls (8.1)
# A question of the model's the person saw and did not answer before the turn ended.
ASKED = json.dumps({"status": "asked", "reason": "the person saw the question; their answer, if it comes, is their "
                                                 "next message"})

# The operation the App reads as «the person answered the pending confirmation» (the kernel's challenge): the App sends
# the exact invocation the kernel challenged again with its token, or drops it.
CONFIRM_OPERATION = "confirmation.answer"
# Renew al máximo (F005 of the notebook's falsehood bench, 2026-10-22): «¿ya lo subiste?» was answered with
# confirm_pending approve:true (answer yes today) and nothing waiting for a «sí»; with a confirmation pending it would
# have approved what nobody approved. Without one, the call never reaches the App: its result says so and the model answers in words.
# F010 (int3, 2026-10-22): «nothing waiting» read as «already done» («la borré sin pedirte permiso» after a delete that
# had failed); the result says this call did nothing and that only earlier results tell what was done.
NOTHING_PENDING = json.dumps({"status": "failed", "error": "nothing_pending",
                              "reason": "no action is waiting for the person's confirmation, and this call did nothing; "
                                        "whether anything was done is only what the earlier results of this "
                                        "conversation say"})
# uso-90: confirm_pending in the turn where a call was just held for the person's «sí»: the person has not been asked
# yet, and what they said before the call was held is not their answer to it (invariant 4: the «sí» is the person's,
# to this exact call). The model asks them; their answer comes with their next words.
NOT_ASKED_YET = json.dumps({"status": "failed", "error": "person_not_asked_yet",
                            "reason": "the call that waits for the person's «sí» was held in this turn and they have not "
                                      "been asked yet; what they said before it was held is not their answer to it, and "
                                      "this call did nothing: ask them now whether to do it; their answer comes with "
                                      "their next words"}, ensure_ascii=False)
# Auditoría de confirmaciones (2026-10-23): a question that ended unanswered (its time ran out, or a later line of
# BAXY's left it behind) is not «nothing was asked» (audit 2026-10-15, App 3, lost since F005): the App says which call
# it was with the person's next words, and their «sí» reads how it ended and that asking again is calling it again.
ENDED = {"expired": ("confirmation_expired", "the time to answer ran out"),
         "dropped": ("confirmation_dropped", "something else was said after the question, so it no longer stood")}


def ended_result(ended: dict[str, Any], wire_of: Callable[[str], str] = plain) -> str:
    """What confirm_pending reads when the call the person may think they answer ended without an answer; ``wire_of``:
    the catalog's wire name of an operation (Wires.name)."""
    error, reason = ENDED.get(str(ended.get("ended")), ENDED["dropped"])
    wire = wire_of(str(ended["operation"]))
    # A call the kernel challenged again after it had started (reconciliationRequired) may have had its effect.
    uncertain = ended.get("effectUncertain") is True
    told: dict[str, Any] = {"status": "failed", "error": error, "operation": ended["operation"]}
    if uncertain:
        told["effectUncertain"] = True
    told["reason"] = f"{reason}: {wire} {'may have started before it was asked' if uncertain else 'did not run'}"
    told["next"] = f"to do it now, call {wire} again: the person will be asked again"
    return json.dumps(told)

# Prefijo c3, S4 (T6 of BRIEF_FT_C3): a boolean had no answer for words that settle nothing; «sí pero el otro» and «sí
# no» were approve:true in conf-int7. «unclear» leaves the call waiting and the model asks again (the App, Unclear). The
# examples are none of the 29 answers of the confirmation mini bench (renew_v4\mini), which measures this.
CONFIRM = {
    "type": "function",
    "function": {
        "name": "confirm_pending",
        "description": (
            "Give the person's answer to the confirmation you asked them for (an action that needed their «sí»). "
            "Use when: you asked «¿Lo borro?» and they answered: answer yes for a plain yes («sí, dale»), no for a "
            "plain no («no, déjalo»), unclear when their words do not settle it («sí, pero el de ayer», «no estoy "
            "seguro», «espérate un poco», or they talk about something else, «¿y ese cuál era?»): the action keeps "
            "waiting, neither run nor cancelled, and you ask again. "
            "Do not use when: nothing is waiting for confirmation, or they asked for something new instead."
        ),
        "parameters": {"type": "object", "properties": {"answer": {"type": "string", "enum": ["yes", "no", "unclear"]}},
                       "required": ["answer"]},
    },
}

ASK_USER = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the person ONE short question, in their language, when a value an action needs is missing or the "
            "request could mean two different actions. Use when: «pon una alarma» (no time), «mándale un mensaje» "
            "(no recipient or text). Do not use when: the request is complete, to chat, or when no tool can do what is "
            "asked (ordering food or a taxi, calls, payments, bookings): then say in one sentence that you don't do "
            "that; asking for an address or a number will not make it possible."
        ),
        "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
}

# Feria 2026-10-27: sums done from memory went wrong (12 for two plus two, a digit misheard) and an 18-digit square root
# went to the Calculator, which takes none. The model writes the expression it understood; the mind computes it
# (arithmetic.evaluate, no App call) and its value, or why there is none, is the call's result.
CALCULATE = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Compute arithmetic exactly, to answer the person yourself: a sum, a product, a division, a percentage, a "
            "power, a root or a logarithm. Write the expression you understood with digits and symbols only: + - * / "
            "^ ( ), sqrt(), cbrt(), log10() and ln(), % as a hundredth (p% of n is p% * n), decimals with a point (a "
            "decimal comma becomes a point) and no thousands separators. Do not use when: they ask to do it in the "
            "Calculator app, or ask the open Calculator for an operation (calculator_expression_evaluate); a "
            "conversion or a price needs a rate you were not given, such as an exchange rate (web_search). A question "
            "for the number («¿cuánto es…?») is yours even with the Calculator open, and so is what it cannot type (a "
            "root, a percentage)."
        ),
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"]},
    },
}
CALCULATIONS = 4  # a turn's calculations; the next decision after the last is in words
# Feria 2026-10-27: office_document_create takes the whole body in one call; at 512 tokens a story was cut mid-call. A
# cap, not a length: a short answer still ends at its own end. Measured on the notebook (NB-L): ~36 tokens/s, ~2 tokens
# a word; 768 is ~21 s, inside the App's 30 s for a decision (TurnRequestTimeout) with room for the prefix.
DECISION_TOKENS = 768
# P0.10 (noche 27-10, NB-R1-X5 on the notebook's trace): the mind trusted the kernel's 8 KiB per result, but a process
# list, a console's output or an OCR reach 48,000 characters, and some turn.continue re-read 10-12k tokens (>2000 tokens
# in 0.7 % of the results, p50 3.8 s each). One result takes at most the room the history leaves for it beside the reply.
RESULT_TOKENS = TURN_ROOM_TOKENS - DECISION_TOKENS
CALCULATED_FIRST = json.dumps({"status": "not_run", "reason": "written before the calculation's value; call it again "
                                                              "with that value if it is still needed"})
# Uso real 2026-11-02: «¿cuánto son 450 mil pesos chilenos en pesos colombianos?» was computed as 450000 * 0.0038, a rate
# the model made up (the real one was about 4.3), and «unos 1.710» was told as fact. Aid «unsourced_number»: a
# calculation's value says which numbers of its expression neither the session's messages nor a tool's result gave.
UNSOURCED_NOTE = ("\n[Ayuda: {numbers} de esta expresión no {said} la persona en esta conversación ni {came} de ningún "
                  "resultado de herramienta. Si alguno es una tasa, un precio o una cotización que cambia con los días, "
                  "ese valor no es un cálculo hasta que se tenga la cifra real: web_search la trae (next: web_search "
                  "con la tasa o el precio de hoy como consulta, y volver a calcular con lo que diga). Si es un factor "
                  "fijo de una unidad, el valor vale.]")
# Encargo A2 (HP3 «abre la calculadora y dime cuánto son 50.000 pesos en dólares»): told only which numbers nobody gave,
# the model still told the value or asked the person for the rate (base: 2 of 5 told it, 3 asked, none searched). The
# note now also says what such a number may be and where the one that changes is looked up (its next, as a tool receipt
# gives one: «Tool Receipts», arXiv 2603.10060; a search to ground a figure the model cannot know: ReAct, arXiv
# 2210.03629, Toolformer, arXiv 2302.04761). Whether this number changes is the model's to say: a fixed factor is not
# looked up.
# A number as a text writes it: «450.000» and «1,5» (Chile), «1,234.5» (a result), with its magnitude in words after it.
_GIVEN_NUMBER = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)*)(?:\s*(mil millones|millones|millon|mil|billones|billon|"
                           r"thousand|million|billion)\b)?")
_MAGNITUDES = {"mil": 10 ** 3, "thousand": 10 ** 3, "millon": 10 ** 6, "millones": 10 ** 6, "million": 10 ** 6,
               "mil millones": 10 ** 9, "billion": 10 ** 9, "billon": 10 ** 12, "billones": 10 ** 12}


def _given_values(text: str) -> set[Decimal]:
    """Every value a number in a text can be: its separators all of thousands, or its last one a decimal point, times
    the magnitude said after it; a percentage is its hundredth too, and 100 is then given."""
    values: set[Decimal] = set()
    folded = _fold(text)
    for match in _GIVEN_NUMBER.finditer(folded):
        digits, magnitude = match.group(1), _MAGNITUDES.get(match.group(2) or "", 1)
        head, separator, tail = digits.replace(",", ".").rpartition(".")
        readings = {digits.replace(".", "").replace(",", "")} | ({head.replace(".", "") + "." + tail} if separator else set())
        for reading in readings:
            value = Decimal(reading) * magnitude
            values.add(value)
            if re.match(r"\s*(?:%|por ?ciento|percent)", folded[match.end():]):
                values.update({value / 100, Decimal(100)})
    return values


def _unsourced(expression: str, messages: list[dict[str, Any]]) -> list[str]:
    """The numbers of a calculation's expression that no message of the session gave: neither the person's words and
    the mind's notes (as digits, with their thousands, or as words) nor a tool's result (its aid notes left out). 0 and
    1 carry no magnitude of their own and are never told."""
    given = [str(m.get("content") or "") for m in messages if m.get("role") in ("user", "tool")]
    text = "\n".join(line for content in given for line in content.splitlines() if not line.startswith("[Ayuda:"))
    values, words = _given_values(text), _words(text)
    told: list[str] = []
    for token in re.findall(r"\d+(?:[.,]\d+)?", expression):
        value = Decimal(token.replace(",", "."))
        if value in (0, 1) or value in values or token in told:
            continue
        if value == value.to_integral_value() and value < 10 ** 12:
            said = _fold(cardinal(int(value)))
            forms = {said, re.sub(r"uno$", "un", said), re.sub(r"uno$", "una", said), said.replace("ientos", "ientas")}
            if value < 1000:
                forms.add(cardinal_en(int(value)))
            if any(f" {form} " in words for form in forms):
                continue
        told.append(token)
    return told


def _display_value(observation: str) -> str:
    """The value the Calculator's result shows (observed.value), or empty."""
    try:
        facts = json.JSONDecoder().raw_decode(str(observation or "").lstrip())[0]
        return str((facts.get("observed") or {}).get("value") or "")
    except (json.JSONDecodeError, AttributeError):
        return ""


def _unsourced_entry(expression: str, messages: list[dict[str, Any]], value: str) -> dict[str, Any]:
    """What the check of the answer needs of a calculation with numbers nobody gave: those numbers and its value as a
    plain number (the Calculator's display writes «55,55», evaluate's result «≈ 55.55»), or none."""
    shown = re.search(r"\d+(?:[.,]\d+)?", value.replace(" ", "").replace(" ", ""))
    return {"numbers": _unsourced(expression, messages), "value": shown.group().replace(",", ".") if shown else None}


def unsourced_note(expression: str, messages: list[dict[str, Any]]) -> str:
    """Aid «unsourced_number»: the numbers of a computed expression nobody gave, as a fact; empty when every one was."""
    told = _unsourced(expression, messages)
    if not told:
        return ""
    many = len(told) > 1
    numbers = ", ".join(told[:-1]) + " y " + told[-1] if many else told[0]
    return UNSOURCED_NOTE.format(numbers=numbers, said="los dijo" if many else "lo dijo",
                                 came="salieron" if many else "salió")


# What the model sees of an argument schema: meaning only. Validation-only keywords stay with the kernel, which
# validates the exact schema anyway; contract constants (a const or a one-value enum) are not the model's to write and
# are added back when its call is handed to the App (measured 2026-10-15: −4k tokens of prefix; memory.save wrote 114
# output tokens, its constants among them).
_MEANING_KEYS = {"type", "properties", "required", "items", "enum", "description", "minimum", "maximum", "anyOf",
                 "oneOf", "default", "format"}


def _model_schema(schema: Any, constants: dict[str, Any] | None = None) -> Any:
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _MEANING_KEYS:
            continue
        if key == "type" and isinstance(value, list):
            kinds = [kind for kind in value if kind != "null"]
            value = kinds[0] if len(kinds) == 1 else kinds
        if key == "properties" and isinstance(value, dict):
            props = {}
            for name, prop in value.items():
                if constants is not None and isinstance(prop, dict) and (
                        "const" in prop or (isinstance(prop.get("enum"), list) and len(prop["enum"]) == 1)):
                    constants[name] = prop["const"] if "const" in prop else prop["enum"][0]
                    continue
                props[name] = _model_schema(prop)
            value = props
        elif key == "items":
            value = _model_schema(value)
        elif key in {"anyOf", "oneOf"} and isinstance(value, list):
            value = [_model_schema(item) for item in value]
        out[key] = value
    if constants and isinstance(out.get("required"), list):
        out["required"] = [name for name in out["required"] if name not in constants]
    return out


def _as_written(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aid «calls_as_written» (w6-lat, 2026-10-23): the conversation's calls with each boolean argument as the model
    writes it. Under the call grammar llama-server makes from the tools' schemas the model writes «true» / «false»
    (JSON), and Qwen3.5's template writes a call's top-level value with Jinja's «| string», «True» / «False»: the request
    after a call stopped matching what the slot held at that value, and the hybrid model went back to its checkpoint 4
    tokens before the decision's end and re-read those tokens, the call and the result (CPU probe, b11609, ft c2e1:
    audio_mute {state: true} 54 → 23 tokens, app_open {foreground: true} 65 → 23; 52 of 278 calls of the practice e2e
    have one). Given as the text «true» / «false», the template writes it as it came; objects and lists it already writes
    with tojson, strings and numbers as given. Only the request changes: the conversation keeps its calls as they were."""
    written: list[dict[str, Any]] = []
    for message in messages:
        calls = message.get("tool_calls") if message.get("role") == "assistant" else None
        if not calls:
            written.append(message)
            continue
        told = []
        for call in calls:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                arguments = None
            if not isinstance(arguments, dict) or not any(isinstance(v, bool) for v in arguments.values()):
                told.append(call)
                continue
            arguments = {k: ("true" if v else "false") if isinstance(v, bool) else v for k, v in arguments.items()}
            told.append({**call, "function": {**function, "arguments": json.dumps(arguments, ensure_ascii=False)}})
        written.append({**message, "tool_calls": told})
    return written


# Palanca P2.6: Start menu entries no one opens as an application, by the shape of their (folded) name, never by an
# application's name: an uninstaller («Uninstall X», «Desinstalar X»; «X Uninstaller» is an application), help, a
# manual, documentation or a license, release notes, and a web page. They leave app_open's list of installed
# applications (67 of 600 names on the PC, ~1,7k characters of prefix); app_open still opens any of them by name.
_NOT_AN_APP = re.compile(
    r"\b(?:un-?install|desinstalar)(?!er)"
    r"|\b(?:help|ayuda|manuals?|faq|readme|documentation|documentacion|dokumentation|user guide|release notes"
    r"|what'?s new|que hay de nuevo|reference|website)\b"
    r"|\b(?:on the|en la) web\b|\(online\)|^licen[cs]e\b|\blicen[cs]e agreement\b")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


class Mind:
    # Al máximo 9.4: the voice's look-ahead (Speech.foresee), given the last answer's text as it is written; None: the
    # last answer is not streamed.
    foresee: Any = None

    def __init__(self, server: LlmServer, trace: Path, system_one: SystemOne | None = None) -> None:
        self.server = server
        self.trace = trace
        self.system_one = system_one  # layer 2: the decision model beside Qwen (None: off)
        if system_one is not None:
            # Its server exiting and starting again is said in this trace (system_one.exited, system_one.restarted).
            system_one.on_event = lambda stage, **fields: self._log(stage, time.perf_counter(), None, **fields)
            system_one.until = lambda: self.server.deadline  # it answers within the request's budget, as every call
        self._judged: dict[str, Any] | None = None
        self._unread: list[dict[str, str]] = []  # the last decision's rivals whose names could not be read (P4)
        self.tools: list[dict[str, Any]] = []
        self.system = SYSTEM  # the person's system text: with the last catalog's groups (CAN_DO_AREAS)
        self.names: list[str] = []  # the installed applications and games of the last catalog.configure
        self.heard: list[str] = []  # the names the ear is biased towards (configure)
        self.wire_to_op: dict[str, str] = {}
        # Settings → Tools: the operations the person's profile keeps off, by the wire name each has with every tool; a
        # call the model makes to one anyway goes to the App by its operation, which refuses it as off (ToolProfile).
        self.withheld: dict[str, str] = {}
        self.wires = Wires([])  # the wire name the model sees for each operation of the last catalog, and back
        self._stubs: set[str] = set()  # the wire names shown as a stub, off in the profile (tool_on)
        self._shown: tuple[list[str], list[str]] = ([], [])  # the installed applications and games a tool's text lists
        self.risk: dict[str, str] = {}  # each tool's risk as the App sent it, by wire name (layer 2 «corrige»)
        self.effects: dict[str, list[str]] = {}  # each tool's effects as the App sent them (al máximo 5.1), by wire name
        # P2.41: the modes in which the kernel asks the person before each tool runs, whatever its arguments («normal»,
        # «bypass»: RiskPolicy.Evaluate, as the App sent them), by wire name (_unasked); None: the catalog did not say.
        self.confirms: dict[str, list[str] | None] = {}
        self._turn: dict[str, Any] | None = None
        self._beat: dict[str, Any] | None = None
        self._opened_places = ""  # the places of what a turn opened, for the next turn (opened_places_note)
        self.conversation: list[dict[str, Any]] = []
        self.trimmed_turns = 0
        # The tools and the system prompt in tokens, as the server counted them at warm-up (0 before it).
        self.prefix_tokens = 0
        self._tokens: dict[str, int] = {}  # each turn's text in the conversation and its tokens (_turn_sizes)
        self.constants: dict[str, dict[str, Any]] = {}
        english = json.loads(_ENGLISH_FILE.read_text(encoding="utf-8")) if _ENGLISH_FILE.is_file() else {}
        self.english: dict[str, str] = english.get("tools") or {}
        self.arguments: dict[str, dict[str, str]] = english.get("arguments") or {}
        self.decide_temperature = _env_float("BAXY_RENEW_DECIDE_TEMPERATURE", 0.2)
        self.seed = int(_env_float("BAXY_RENEW_SEED", 0))
        # PLAN_GENERAL C1: the long addresses results carried, by the short reference the model saw, and back.
        self._refs: dict[str, str] = {}
        self._ref_of: dict[str, str] = {}
        # The references made in the session (_refs keeps only those the conversation still shows, _prune_refs): a new
        # one takes the next number, never one still shown.
        self._ref_count = 0
        # Review 2026-10-22: the ids the mind writes itself (a confirmation's call, a call the server gave none, a
        # correction) count up for the whole session: from the conversation's length they repeated once it was trimmed.
        self._ids = 0
        self._ran: list[str] = []  # the session's last calls as «tool → how it ended» (8.1), and how many ran in all
        self._ran_ids: list[str | None] = []  # the id of each of those calls (None: not known), for the clock
        self._captures_kept = False  # whether a call waits for the «sí» at this turn's start (CAPTURE_GONE)
        self._ran_count = 0
        # Aid «answer_check»: every call of the session as (operation, completed, read_only), for the check of the final
        # answer; None when the session is not known whole (one kept before the aid).
        self._calls: list[tuple[str, bool, bool]] | None = []
        # Aid «check_stale_state» (encargo 56): the session's last calls as the answer check reads a receipt, with only
        # the scalar fields of their result (its state, name, bytes, next): the conversation leaves their bodies out
        # once it is trimmed (uso real 03-11: context_shrunk, then «Ya está instalado» over a result that read «queued»).
        self._states: list[dict[str, Any]] = []
        # Review 2026-10-22: the voice thread logs here too (voice.speak, __main__.py): one row at a time.
        self._log_lock = threading.Lock()
        # A person's turn or a heartbeat reached the model in this process: the slot holds more than the prefix, and
        # the warm-up no longer keeps it on disk (al máximo V1).
        self._turned = False
        # The last read ahead gave way to a request (Yielded): its ``clock``, so the loop reads it again once nothing
        # waits (review of NB-R1-X4: the App's session.export after every turn); None when it did not.
        self.gave_way: bool | None = None
        self._prefill_rounds = 0  # of this history (PREFILL_ROUNDS)
        self._notice_budget = NOTICE_SECONDS  # what a notice may take on this machine (_next)
        # Uso 104 (F41, a greeting at 9.2 s with its decision at 1.1 s and nothing in the trace for the rest): when the
        # request being answered reached the mind's reader, set by the loop; its turn.decide row says how long it took to
        # start deciding (before_ms: the queue, the count of the history), and how long the App had held it (app_ms).
        self.arrived: float | None = None
        self._ear_unsure: list[float] = []
        self.app_ms: int | None = None
        # ALR4: the interface's language as the App's turn.decide says it («lang»), set by the loop: the fixed sentence of
        # ring_answer is said in it when the person's words are both languages' («ok», «stop»).
        self.lang = "es"
        # RUT1: the person's routines as the App's turn.decide gives them (RoutinesHandler's store), set by the loop.
        self.routines: list[dict[str, Any]] = []
        # RUT7: the routine BAXY is making with the person, question by question (routine_guide.Guide), and when they
        # last answered: after GUIDE_SILENCE_S of nothing it is dropped and their words are a turn as any other.
        self._guide: routine_guide.Guide | None = None
        self._guide_at = 0.0
        # RUT11 (REV11 B-4): the person's words of the last turn, for «bórrala» (routine_guide.named_in).
        self._heard_last = ""
        # Al máximo, palanca 2 (early.py): while a decision is made early, its trace rows are held here (the thread that
        # makes it, and its rows) and written only if it is used; the voice thread's rows are written as always.
        self._holding: tuple[int, list[dict[str, Any]]] | None = None

    # ---- short references (PLAN_GENERAL C1) ----------------------------------------------------------------
    def _shorten(self, observation: str, compact: bool = False) -> tuple[str, dict[str, str]]:
        """The result with every address longer than LONG_REF_CHARS replaced by its short reference, and the
        references made for it (a known address keeps its reference). Text that is not JSON goes as it came.
        ``compact`` (aid «result_dedup»): written as compact as the App writes it, not with a space after each comma and
        colon (one token more per field)."""
        try:
            facts = json.loads(observation)
        except json.JSONDecodeError:
            return observation, {}
        made: dict[str, str] = {}

        def walk(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: walk(v) for k, v in value.items()}
            if isinstance(value, list):
                return [walk(v) for v in value]
            if isinstance(value, str) and len(value) > LONG_REF_CHARS and value.startswith(("http://", "https://")):
                ref = self._ref_of.get(value)
                if ref is None:
                    self._ref_count = max(self._ref_count, len(self._refs)) + 1
                    ref = f"{REF_PREFIX}{self._ref_count}"
                    self._refs[ref], self._ref_of[value] = value, ref
                made[ref] = value
                return ref
            return value

        shortened = walk(facts)
        if not made:
            return observation, {}
        return json.dumps(shortened, ensure_ascii=False, separators=(",", ":") if compact else None), made

    def _expand(self, value: Any) -> Any:
        """A call's arguments with every short reference the model wrote put back as the address it stands for."""
        if isinstance(value, dict):
            return {k: self._expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._expand(v) for v in value]
        if isinstance(value, str) and REF_PREFIX in value:
            return _REF.sub(lambda m: self._refs.get(m.group(0), m.group(0)), value)
        return value

    def _new_id(self, kind: str) -> str:
        # A hyphen, never an underscore: an id written before the counter (confirm_12, call_5_0) is never repeated.
        self._ids += 1
        return f"{kind}-{self._ids}"

    # ---- catalog -------------------------------------------------------------------------------------------
    def _whole(self, cap: dict[str, Any], wires: "Wires",
               aids: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """One capability of the catalog as the model is shown it: its wire name, its tool and its constants."""
        apps, games = self._shown
        name = str(cap.get("name") or "")
        # Renew al máximo: the places stay in app_open's description too (P2.6 left them only in `place`; e2e E014
        # then opened msconfig for «abre la configuración de sonido», twice, on the notebook, 2026-10-22).
        description = wires.cite((self.english.get(name) or str(cap.get("description") or "")).replace(
            "{app_places}", APP_PLACES_TEXT))
        if name == "app.open" and apps:
            description += " Installed applications (use one of these names as appId): " + "; ".join(apps) + "."
        if name == "game.launch" and games:
            description += " The person's installed games: " + "; ".join(games) + "."
        for aid, sentence in DESCRIPTION_AIDS.get(name, ()):
            if _aid_on(aid):
                description = description.rstrip() + sentence
                aids.setdefault(aid, {})[name] = sentence.strip()
        raw = cap.get("argumentsSchema")
        constants: dict[str, Any] = {}
        schema = _model_schema(raw if isinstance(raw, dict) else {}, constants)
        schema["type"] = "object"
        schema.setdefault("properties", {})
        if name == "baxy.routines":
            # RUT7: the model's call only opens the guide; a routine's arguments are written by the guide
            # (routine_guide), never by the model.
            schema = {"type": "object", "properties": {}}
        # What one argument means, where the model fills it (a folder named by the person went missing from the
        # path when only the tool's text said it: own path set 3/8, with the meaning on the argument 6/8).
        for argument, meaning in (self.arguments.get(name) or {}).items():
            if isinstance(schema["properties"].get(argument), dict):
                schema["properties"][argument]["description"] = wires.cite(
                    meaning.replace("{app_places}", APP_PLACES_TEXT))
        wire = wires.name(name)
        tool = {"type": "function", "function": {"name": wire, "description": description, "parameters": schema}}
        return wire, tool, constants

    @staticmethod
    def _weighed(cap: dict[str, Any]) -> tuple[str, list[str], list[str] | None]:
        """A capability's risk, its effects and the modes that confirm it, as the App sent them."""
        # P2.41b: a catalog without the field (an older App, a bench's --catalog), or with one that is not a list of
        # modes, is not one that confirms nothing: None (_unasked).
        modes = cap.get("confirms")
        return (str(cap.get("risk") or ""), [str(e) for e in cap.get("effects") or []],
                [mode.lower() for mode in modes]
                if isinstance(modes, list) and all(isinstance(mode, str) for mode in modes) else None)

    def tool_on(self, capability: dict[str, Any]) -> bool:
        """TPV7 (VIVO11, 11-11-2026: «sí» to a tool off in Esencial, and BAXY said «Nota creada» with no call): a tool
        the profile kept off, turned on with the person's «sí», is shown whole from the turn's next request on. Its
        stub had no arguments, so the model could only call it empty or say it was done. The whole tool takes the
        stub's own place: everything before it in the prompt stays as the server holds it, and only the stubs after
        it and the conversation are read again. The system text stays as it is until the App restarts the mind with
        the profile's catalog. Whether it was a stub of this catalog."""
        name = str(capability.get("name") or "")
        wire = self.wires.name(name) if name else ""
        at = next((i for i, tool in enumerate(self.tools) if tool["function"]["name"] == wire), None)
        if at is None or wire not in self._stubs:
            return False
        started = time.perf_counter()
        _, tool, constants = self._whole(capability, self.wires, {})
        grown = (len(self.server.tokenize(json.dumps(tool, ensure_ascii=False)))
                 - len(self.server.tokenize(json.dumps(self.tools[at], ensure_ascii=False))))
        self.tools[at] = tool
        self._stubs.discard(wire)
        self.withheld.pop(wire, None)
        self.wire_to_op[wire] = name
        self.risk[wire], self.effects[wire], self.confirms[wire] = self._weighed(capability)
        if constants:
            self.constants[name] = constants
        if self.prefix_tokens:
            self.prefix_tokens += max(grown, 0)  # the room left for the conversation counts the tool it now carries
        self._log("configure.tool_on", started, None, operation=name, at=at, tools=len(self.tools), grown=grown)
        return True

    def configure(self, message: dict[str, Any]) -> int:
        capabilities = list(message.get("capabilities") or [])
        # The person's own texts (Ajustes → Comportamiento) are the person's: the benches take the catalog kept here
        # from one machine to another, so it is kept without them and measures the factory texts.
        chosen = behavior.texts(message.get("behavior"))
        try:  # the exact catalog the App sent, for offline measurement of the presentation
            (self.trace.parent / "catalog.configure.json").write_text(
                json.dumps({key: value for key, value in message.items() if key != "behavior"}, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass
        apps = [str(n) for n in ((message.get("applicationCatalog") or {}).get("names") or [])
                if str(n).strip() and not _NOT_AN_APP.search(_fold(str(n)))]
        games = sorted({f'{e.get("name")} (appId {e.get("appId")}, {e.get("provider")})'
                        for e in ((message.get("gameCatalog") or {}).get("entries") or [])
                        if isinstance(e, dict) and e.get("name")})
        # The same names, for the ear's hotwords (voice.hear_names): what the model is shown is what it may hear.
        self.names = apps + sorted({str(e.get("name")) for e in ((message.get("gameCatalog") or {}).get("entries") or [])
                                    if isinstance(e, dict) and e.get("name")})
        # What the ear is biased towards: those, and the applications and services BAXY knows by name (aid
        # «ear_known_names»); self.names stays the installed ones, as «unopened_app» reads them.
        self.heard = list(dict.fromkeys(self.names + (KNOWN_APPLICATIONS if _aid_on("ear_known_names") else [])))
        tools, wire_to_op, risk, effects, confirms = [ASK_USER, CONFIRM, CALCULATE], {}, {}, {}, {}
        # PC-C72: no wire name is a proper prefix of another one (audio_volume ⊂ audio_volume_adjust made the 4B go on
        # writing the long one); the descriptions cite the names as they are shown.
        # Settings → Tools: the names withheld count too, so every tool keeps the wire name it has with them all.
        # Each withheld entry is its name, or {name, title} from the App (its title in English, operation-labels «en»).
        titled = [(str(item.get("name") or ""), str(item.get("title") or "")) if isinstance(item, dict) else (str(item), "")
                  for item in message.get("withheld") or []]
        withheld = [name for name, _ in titled if name]
        # ESE6: one whose call the App holds with its arguments comes whole beside its title (HELD_STUB).
        held_whole = {str(item.get("name") or ""): item["whole"] for item in message.get("withheld") or []
                      if isinstance(item, dict) and isinstance(item.get("whole"), dict)}
        wires = Wires([*(str(cap.get("name") or "") for cap in capabilities), *withheld],
                      fixed=[tool["function"]["name"] for tool in tools])
        # Auditoría de la mente (w8): the constants of this catalog only; one a tool had in an earlier catalog was still
        # added to its calls.
        constants_of: dict[str, dict[str, Any]] = {}
        aids: dict[str, Any] = {}
        self._shown = (apps, games)
        for cap in capabilities:
            wire, tool, constants = self._whole(cap, wires, aids)
            tools.append(tool)
            name = wire_to_op[wire] = str(cap.get("name") or "")
            if constants:
                constants_of[name] = constants
            risk[wire], effects[wire], confirms[wire] = self._weighed(cap)
        # VIVO1 F8 (09-11): each withheld tool is shown as a stub, its title and that it is off, with no arguments, so a
        # request for it reaches its call and the App's refusal says it is off (NativeTurnLoop.Refused).
        # One the App names without a title has no stub (operation-labels «ficha»: false).
        stubs = {wires.name(name) for name, title in titled if name and title and name not in wire_to_op.values()}
        for name, title in titled:
            if name == RING_TOOL and title and name not in wire_to_op.values():
                # ALR5 (M2): a tool of its own, with the operation's risk in the catalog (ProductCatalog: low and
                # reversible, confirmed in no mode), so its call is weighed as the whole tool's stop and snooze are.
                wire, schema = wires.name(name), json.loads(json.dumps(RING_STUB_SCHEMA))
                if meaning := (self.arguments.get(name) or {}).get("id"):
                    schema["properties"]["id"]["description"] = wires.cite(meaning)
                tools.append({"type": "function", "function": {
                    "name": wire, "description": f"{title}. {RING_STUB}", "parameters": schema}})
                wire_to_op[wire], risk[wire], effects[wire], confirms[wire] = name, "low_reversible", [], []
            elif name and title and name in held_whole and name not in wire_to_op.values():
                # ESE6: a tool of its own too, with the arguments, the constants and the risk the whole one has: the
                # App holds exactly the call the model makes, and the person's yes runs it.
                wire, tool, constants = self._whole(held_whole[name], wires, {})
                tool["function"]["description"] = f"{title}. {HELD_STUB}"
                tools.append(tool)
                wire_to_op[wire] = name
                risk[wire], effects[wire], confirms[wire] = self._weighed(held_whole[name])
                if constants:
                    constants_of[name] = constants
            elif name and title and name not in wire_to_op.values():
                tools.append({"type": "function", "function": {
                    "name": wires.name(name), "description": f"{title}. {OFF_STUB}",
                    "parameters": {"type": "object", "properties": {}}}})
        self.tools, self.wire_to_op, self.risk, self.effects, self.confirms = tools, wire_to_op, risk, effects, confirms
        self.wires, self._stubs = wires, stubs
        self.withheld = {wires.name(op): op for op in withheld if op not in wire_to_op.values()}
        if absent := [wire_to_op[wire] for wire, modes in confirms.items() if modes is None]:
            self._log("configure.confirms_absent", time.perf_counter(), None, operations=absent)
        areas = list(dict.fromkeys(str(cap["group"]) for cap in capabilities if cap.get("group")))
        # The person's texts in their fixed places (behavior.py): with the factory's this is the text written before.
        version = message.get("baxyVersion")
        # MEM4: the switch the App read, for the check's rule «memory_off_empty» (only an «off» said: none said, unknown).
        self._switch_off = message.get("memoryOff") is True
        self.system = (behavior.head(chosen) + RULES + (CAN_DO_AREAS.format(areas="; ".join(areas)) if areas else "")
                       + (VERSION_FACT.format(version=version.strip()) if isinstance(version, str) and version.strip()
                          else "")
                       + (MEMORY_HELD_FACT.format(call=wires.name(MEMORY_TOOL), state=MEMORY_HELD_PROFILE
                                                  if message.get("memoryOff") is False else MEMORY_HELD_OFF)
                          + "".join(sentence.format(call=wires.name(tool), save=wires.name(MEMORY_TOOL))
                                    for tool, sentence in MEMORY_HELD_ALSO
                                    if tool in held_whole and wires.name(tool) in stubs)
                          if MEMORY_TOOL in held_whole and wires.name(MEMORY_TOOL) in stubs
                          else MEMORY_OFF_FACT.format(call=wires.name("baxy.settings.set") + ' {"setting": "tool_profile", '
                                                      '"value": "diario"}')
                          if MEMORY_TOOL in self.withheld.values() and "baxy.settings.set" in wire_to_op.values() else "")
                       + behavior.tail(chosen))
        if own := behavior.custom(chosen):
            self._log("configure.behavior", time.perf_counter(), None, own=own)
        self.constants = constants_of
        if aids:
            # A session's aid in the tools themselves, once: its own trace row, as the aids of a turn.
            self._log("configure.aid", time.perf_counter(), None, aids=aids)
        return len(capabilities)

    def warm(self, on_progress: Callable[[int, int], None] | None = None) -> None:
        """Process the tools and the system prompt once, so every turn starts from a cached prefix. Al máximo V1
        (2026-10-22): that state is kept on disk (LlmServer.save_prefix) with the prefix's tokens, and a start whose
        tools, system prompt, model and server are the same restores it instead (18.3 s → under 1 s). A prefix read
        again is waited for while the server advances through it (LlmServer.read_prefix), each advance told to
        ``on_progress`` (the sidecar tells the App, which waits as long as it comes)."""
        started = time.perf_counter()
        self.call_tokens = self.server.tokenize("<tool_call>")
        if len(self.call_tokens) != 1:
            raise RuntimeError(f"<tool_call> is not one token of this model: {self.call_tokens}")
        warm = {"messages": [{"role": "system", "content": self._system()}, {"role": "user", "content": "hola"}],
                "tools": self.tools, "max_tokens": 1, "chat_template_kwargs": {"enable_thinking": False}}
        key = self.server.prefix_key([warm])
        held = self.server.restore_prefix(key)
        if held is not None and isinstance(held.get("prefix_tokens"), int):
            self.prefix_tokens = self.server.kept = held["prefix_tokens"]
            self._log("warm.prefix", started, None, restored=True)
            return
        reply = self.server.read_prefix(warm, on_progress)
        self.prefix_tokens = self.server.kept = int((reply.get("usage") or {}).get("prompt_tokens") or 0)
        # The file holds the slot: only the prefix (the tools and the system prompt) may be in it, never a person's
        # conversation, so it is saved only before any turn of this process reached the model.
        saved = not self._turned and self.server.save_prefix(key, {"prefix_tokens": self.prefix_tokens})
        self._log("warm.prefix", started, None, restored=False, saved=saved)

    def notice_of(self) -> str:
        """The notice of the person's turn while the App runs its call (NOTICE_ASK): the model's words for that call,
        written from the turn's conversation with the call still running, words only and greedy, on the GPU the call
        leaves idle. Empty, and nothing asked of the model, when no call of a person's turn is running or in a turn kept
        out of the trace (its words would be said aloud); empty too when it wrote nothing usable or one of the turn's
        earlier notices (a form compare), or the call failed."""
        turn = self._turn
        if not turn or not turn.get("awaiting") or turn.get("private"):
            return ""
        said = turn.setdefault("notices", [])
        ask = NOTICE_ASK.format(said=NOTICE_SAID.format(said=", ".join(f"«{s}»" for s in said)) if said else "")
        notice = {"messages": [{"role": "system", "content": self._system()}, *self._history(self._seen(turn)),
                               {"role": "tool", "tool_call_id": turn["awaiting"], "content": f"{NOTICE_RUNNING}\n{ask}"}],
                  "tools": self.tools, "max_tokens": NOTICE_WRITTEN, "temperature": 0.0, "seed": self.seed,
                  "tool_choice": "none",
                  "logit_bias": [[token, False] for token in self.call_tokens],
                  "chat_template_kwargs": {"enable_thinking": False}}
        started = time.perf_counter()
        try:
            reply = self.server.chat(notice, timeout=self._notice_budget)
            written = str(reply["choices"][0]["message"].get("content") or "")
        except Exception:  # noqa: BLE001 - a notice that could not be written is not said; the turn goes on as it was
            self._log("turn.notice", started, None, operation=turn.get("calling"), content=None, written="")
            return ""
        phrase = " ".join(written.strip().strip("«»\"'“”").split())
        usable = (bool(phrase) and reply["choices"][0].get("finish_reason") != "length"
                  and "\n" not in written.strip() and "<" not in phrase
                  and len(phrase) <= NOTICE_MAX_CHARS and len(phrase.split()) <= NOTICE_MAX_WORDS
                  and _words(phrase) not in {_words(s) for s in said})
        if usable:
            said.append(phrase)
        self._log("turn.notice", started, reply, operation=turn.get("calling"), content=phrase if usable else None,
                  written=written)
        return phrase if usable else ""

    def title_of(self, conversation: list[Any]) -> str:
        """The model's name for a conversation that closed (TITLE_ASK), from the conversation as export_session gave it:
        the session's own messages rendered as the slot holds them, the ask after them, greedy and typed (TITLE_SCHEMA).
        Empty, and the model not asked, when the person never asked anything in it; empty too when what it wrote is not
        the schema, was cut, or goes past TITLE_ACCEPTED_WORDS. The name is never written to the trace: it is made of the
        conversation's words, and a private turn keeps them out of it."""
        conv = [m for m in conversation if isinstance(m, dict) and m.get("role") in {"user", "assistant", "tool"}]
        said = " ".join(str(m.get("content") or "") for m in conv if m.get("role") == "user"
                        and not str(m.get("content") or "").startswith("["))
        if not said.strip():
            return ""
        ask = TITLE_ASK_EN if language_id.said_in(said, "es") == "en" else TITLE_ASK
        body = {"messages": [{"role": "system", "content": self._system()}, *self._history(conv),
                             {"role": "user", "content": ask}],
                "tools": self.tools, "tool_choice": "none", "max_tokens": TITLE_WRITTEN, "temperature": 0.0,
                "seed": self.seed, "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {"type": "json_schema", "json_schema": {"name": "titulo", "schema": TITLE_SCHEMA}}}
        started = time.perf_counter()
        try:
            # Nobody waits for a name: it ends as soon as a request does (LlmServer._aside; revisión total, M5).
            reply = self.server.chat(body, timeout=TITLE_SECONDS, gives_way=True)
            choice = reply["choices"][0]
            named = json.loads(str(choice["message"].get("content") or ""))
        except Exception as error:  # noqa: BLE001 - no name: the App keeps the conversation's first sentence and its date
            self._log("session.title", started, None, named=False, gave_way=isinstance(error, Yielded))
            return ""
        title = named.get("titulo") if isinstance(named, dict) else None
        title = " ".join(str(title).strip().strip("«»\"'“”").split()) if isinstance(title, str) else ""
        usable = (bool(title) and choice.get("finish_reason") != "length" and "\n" not in str(named.get("titulo"))
                  and len(title) <= TITLE_MAX_CHARS and len(title.split()) <= TITLE_ACCEPTED_WORDS)
        # how long it was, never what it said: a name past the limit is told from one that was not the schema
        self._log("session.title", started, reply, named=usable, words=len(title.split()),
                  cut=choice.get("finish_reason") == "length")
        return title if usable else ""

    @property
    def notices_are_slow(self) -> bool:
        """Whether a notice takes longer here than NOTICE_SECONDS: the model then reads for long after a call that ended
        while it was written (the App still says it, turn.notice.result ``slow``)."""
        return self._notice_budget > NOTICE_SECONDS

    def _system(self, beat: bool = False) -> str:
        # Constant, so the prefix (tools, system, earlier messages) never changes between turns and is never re-read.
        return BEAT_SYSTEM if beat else self.system

    @staticmethod
    def _seen(turn: dict[str, Any]) -> list[dict[str, Any]]:
        """The conversation the model reads in this turn: the whole of it, but in the turn of a routine's phrase (RUT10)
        only that turn, from its clock on, as a conversation of its own."""
        conv, alone = turn["conv"], turn.get("alone")
        at = next((i for i, m in enumerate(conv) if m is alone), None) if alone is not None else None
        return conv if at is None else conv[at:]

    @staticmethod
    def _history(conv: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The conversation as a request sends it: every request and the prefill render it alike (aid
        «calls_as_written»), or the prefill's text would not be the next prompt's start."""
        return _as_written(conv) if _aid_on("calls_as_written") else conv

    @staticmethod
    def _waits(pending: dict[str, Any] | None) -> bool:
        """Whether the App says a call waits for the person's «sí» with these words."""
        return bool(isinstance(pending, dict) and pending.get("operation") and not pending.get("ended"))

    def _confirming(self, pending: dict[str, Any] | None) -> str | None:
        """The tool of the call that waits for the person's «sí» with these words, as the App says it, or None."""
        return self.wires.name(str(pending["operation"])) if self._waits(pending) else None  # type: ignore[index]

    @classmethod
    def _pending_op(cls, pending: dict[str, Any] | None) -> str | None:
        """The operation a «sí» with these words would confirm, as the App says it (aid «answer_check»: what a
        confirm_pending call did)."""
        return str(pending["operation"]) if cls._waits(pending) else None  # type: ignore[index]

    @staticmethod
    def _ended(pending: dict[str, Any] | None) -> dict[str, Any] | None:
        """The call whose question ended unanswered just before these words, as the App says it, or None."""
        return pending if isinstance(pending, dict) and pending.get("operation") and pending.get("ended") else None

    def _pending_note(self, pending: dict[str, Any] | None) -> str:
        """The call the kernel holds for the person's yes, when one is: after «sí» the model called that tool again
        instead of answering it (e2e practice E021, 3 of 3), and the kernel only asked again."""
        if not isinstance(pending, dict) or not pending.get("operation") or pending.get("ended"):
            return ""
        wire = self.wires.name(str(pending["operation"]))
        arguments = pending.get("arguments")
        shown = f" {json.dumps(arguments, ensure_ascii=False)}" if isinstance(arguments, dict) else ""
        return (f"\n[Espera el sí de la persona: {wire}{shown}. Si sus palabras contestan a tu pregunta, llama a "
                f"confirm_pending con answer yes, no o unclear.]")

    @staticmethod
    def _unsure_note(unsure: list[tuple[str, float]]) -> str:
        """The words of a spoken request the ear was not sure of (voice.Heard), told as a fact the model weighs."""
        if not unsure:
            return ""
        words = ", ".join(f"«{word}» ({round(p * 100)} %)" for word, p in unsure)
        return "\n" + UNSURE_NOTE.format(words=words)

    def _clock(self) -> str:
        # The time is a message of its own just before the person's words (the end of the prompt, the only part that is
        # new anyway). Appended to their words it was copied into arguments: a clipboard text and a web query carried
        # «[Thursday 15/10/2026 04:21 hora local…]» (2026-10-15). It also says no tool has run yet in this turn: the
        # last «[En este turno: …]» the model saw was the previous turn's, and lines of turns without calls were false
        # 24 % of the time against 6 % (falsedades p5-p8); decision2 on the notebook gained by that mechanism (P041
        # stopped inventing, P049 stopped looking up the clock): 227/230 vs 226. Al máximo 8.1: and the session's calls.
        # Plan c3 (estado explícito): and that what the results above show is of when they were read (STALE_TURNS).
        ran = str(self._ran_count or "ninguna")
        if self._ran:
            last = "" if len(self._ran) == self._ran_count else f", las {len(self._ran)} últimas"
            ran += f"{last} ({' / '.join(self._ran_told(self._captures_kept))})"
        return (f"{CLOCK_MARK} {self._clock_time()}; "
                "los campos que terminan en Utc van en UTC; turno nuevo: aún no se ejecutó ninguna herramienta en este "
                f"turno{STALE_TURNS if self._ran_count else ''}; llamadas a herramientas en esta sesión: {ran}]")

    @staticmethod
    def _clock_time() -> str:
        """The clock's time, to the minute: the only part of a turn's prompt the time changes (early.py compares it).
        VER1 (PR-03): the time first, then the date year first, as ISO 8601 writes it (the form every date argument and
        result already has). The 4B carries a number of the date into the one beside it: as «Monday 09/11/2026 22:10» it
        read the 11th for the day (of 54 alarms asked for another day, «mañana», «en tres días», «el viernes», 30 were
        set for the day asked) and as «Monday 2026-11-09 22:10» it read 11 for the hour («son las 23:10», 7 of 30
        answers to the time; none with the time first). So the time stands first, apart from the date."""
        now = _dt.datetime.now().astimezone()
        offset = now.strftime("%z")
        return f"{now.strftime('%H:%M')} hora local, UTC{offset[:3]}:{offset[3:]}, {now.strftime('%A %Y-%m-%d')}"

    @staticmethod
    def _now() -> _dt.datetime:
        """The turn's moment, with its offset: what a capture's age is told from (CAPTURE_AGE_NOTE)."""
        return _dt.datetime.now().astimezone()

    @staticmethod
    def _today() -> _dt.date:
        """The clock's date, the one the clock line tells the model (the rule «future_past» of the answer check)."""
        return _dt.datetime.now().astimezone().date()

    # ---- turn ----------------------------------------------------------------------------------------------
    # One conversation for the whole session (native loop): every tool call the model made, every verified result that
    # came back as a tool message and every answer stay in it, turn after turn. The model reads what was really run in
    # earlier turns, not a retelling of it: a history of bare «Listo, abrí Steam» replies without the calls behind them
    # taught it to answer «Listo» without calling (2026-10-15 01:52, diagnosed on the notebook against the journal).
    # Parallel calls run in order, one per round trip.
    def new_session(self, history: list[dict[str, Any]] | None = None) -> None:
        """Start a fresh conversation, optionally from earlier plain exchanges (a bench case's context)."""
        self._turn = self._beat = None
        self._opened_places = ""
        self.trimmed_turns = 0
        self._refs, self._ref_of, self._ids, self._ref_count = {}, {}, 0, 0
        self._ran, self._ran_ids, self._ran_count = [], [], 0
        self._calls = []
        self._states = []
        self._memory_was_off = False
        self._guide = None
        self._heard_last = ""
        self.conversation = [{"role": m["role"], "content": m["content"]} for m in history or []
                             if m.get("role") in {"user", "assistant"} and str(m.get("content") or "").strip()]

    def export_session(self) -> list[dict[str, Any]]:
        """The session's conversation as it stands (calls and results included), for the App to keep with the session it
        shows (design v4, Sessions); it is asked for between turns. Its last element is the session's own state (review
        2026-10-22: the short references and the ids, or after a relaunch ref:r1 stood for another address; al máximo
        8.1: the session's calls); the App keeps the array as it is."""
        state = {"role": SESSION_STATE, "refs": self._refs, "ids": self._ids, "ran": self._ran,
                 "ran_ids": self._ran_ids, "ran_count": self._ran_count, "states": self._states}
        if self._calls is not None:
            state["calls"] = [list(call) for call in self._calls]
        return json.loads(json.dumps([*self.conversation, state], ensure_ascii=False))

    def load_session(self, conversation: list[Any]) -> None:
        """Go back to a kept session: its conversation exactly as exported, so the model reads what really ran."""
        self.new_session()
        state = next((m for m in conversation if isinstance(m, dict) and m.get("role") == SESSION_STATE), {})
        if isinstance(state.get("refs"), dict):
            self._refs = {str(ref): str(value) for ref, value in state["refs"].items()}
            self._ref_of = {value: ref for ref, value in self._refs.items()}
            self._ref_count = max((int(ref[len(REF_PREFIX):]) for ref in self._refs
                                   if ref.startswith(REF_PREFIX) and ref[len(REF_PREFIX):].isdecimal()), default=0)
        self._ids = state["ids"] if isinstance(state.get("ids"), int) and state["ids"] > 0 else 0
        self.conversation, unanswered = self._answered([self._current_names(m) for m in conversation if isinstance(m, dict)
                                                        and m.get("role") in {"user", "assistant", "tool"}])
        if isinstance(state.get("ran_count"), int) and isinstance(state.get("ran"), list):
            self._ran = [self._current_ran(str(entry)) for entry in state["ran"]][-SESSION_CALLS:]
            self._ran_count = state["ran_count"]
            ids = state.get("ran_ids")
            self._ran_ids = ([i if isinstance(i, str) else None for i in ids][-SESSION_CALLS:]
                             if isinstance(ids, list) and len(ids) == len(state["ran"]) else [None] * len(self._ran))
            for wire in unanswered:
                self._ran_add(wire, NO_RESULT_RAN)
        else:
            # Kept before 8.1: how many calls its conversation shows (their results are in it), never «none».
            self._ran_count = sum(1 for m in self.conversation for c in m.get("tool_calls") or []
                                  if c.get("function", {}).get("name") != ASK_USER["function"]["name"])
        states = state.get("states")
        self._states = ([s for s in states if isinstance(s, dict) and isinstance(s.get("op"), str)][-SESSION_CALLS:]
                        if isinstance(states, list) else [])
        calls = state.get("calls")
        # Kept before «answer_check» (or written otherwise): what ran in it is not known whole, and nothing is checked
        # against the session's calls.
        self._calls = (list(dict.fromkeys((str(c[0]), c[1], c[2]) for c in calls)) if isinstance(calls, list) and all(
            isinstance(c, list) and len(c) == 3 and isinstance(c[1], bool) and isinstance(c[2], bool) for c in calls)
            else None if any(m.get("tool_calls") for m in self.conversation) else [])
        self._trim()

    def _current_names(self, message: dict[str, Any]) -> dict[str, Any]:
        """A kept message whose calls name their tools as this catalog shows them: a session kept with an older catalog
        says the plain name of a tool renamed since (wire.Wires), which is no tool the model is offered now."""
        calls = message.get("tool_calls")
        if not isinstance(calls, list) or not any(self._renamed(c) for c in calls):
            return message
        return {**message, "tool_calls": [
            {**c, "function": {**c["function"], "name": self.wires.name(self.wires.known(c["function"]["name"]))}}
            if self._renamed(c) else c for c in calls]}

    def _renamed(self, call: Any) -> bool:
        name = call.get("function", {}).get("name") if isinstance(call, dict) and isinstance(
            call.get("function"), dict) else None
        op = self.wires.known(name) if isinstance(name, str) else None
        return op is not None and self.wires.name(op) != name

    def _current_ran(self, entry: str) -> str:
        """A kept line of the session's calls («wire → how it ended») with its tool as this catalog shows it."""
        wire, arrow, rest = entry.partition(" → ")
        op = self.wires.known(wire) if arrow else None
        return f"{self.wires.name(op)}{arrow}{rest}" if op is not None else entry

    @staticmethod
    def _answered(conversation: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        """A kept conversation where every call has its result, and the calls that may have run without one (their wire
        names). Auditoría de la mente (w8, 2026-10-23): the App keeps a session between turns, and a turn may be left
        open there (BAXY's question waiting for its answer, a call whose result never came); the open turn is not kept
        with it, so loaded back its calls had no result and the model read them as still open. Each gets what
        _close_open_calls writes: the first call of its message without one ASKED (a question) or NO_RESULT, the ones
        after it NOT_RUN, right after the results its message has."""
        answered = {m.get("tool_call_id") for m in conversation if m.get("role") == "tool"}
        closed: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        unanswered: list[str] = []
        for message in [*conversation, None]:
            if message is None or message.get("role") != "tool":
                closed += missing
                missing = []
            if message is None:
                break
            closed.append(message)
            lacking = [c for c in message.get("tool_calls") or [] if isinstance(c, dict) and c.get("id") not in answered]
            for index, call in enumerate(lacking):
                wire = str((call.get("function") or {}).get("name") or "?")
                content = NOT_RUN if index else ASKED if wire == ASK_USER["function"]["name"] else NO_RESULT
                if content == NO_RESULT:
                    unanswered.append(wire)
                missing.append({"role": "tool", "tool_call_id": call.get("id"), "content": content})
        return closed, unanswered

    @staticmethod
    def _front_window(front: dict[str, Any] | None) -> str:
        """The window in front of the person when they spoke, as the App read it (encargo 119), or nothing."""
        title = str((front or {}).get("title") or "").strip()
        if not title:
            return ""
        if len(title) > FRONT_TITLE_CHARS:
            title = title[:FRONT_TITLE_CHARS] + "…"
        process = str((front or {}).get("process") or "").strip()
        return f"«{title}»" + (f" ({process})" if process else "")

    @classmethod
    def _named_note(cls, named: list[dict[str, Any]] | None) -> str:
        windows = [cls._front_window(window) for window in named or []]
        windows = [window for window in windows if window]
        return "\n" + NAMED_NOTE.format(windows=", ".join(windows)) if windows else ""

    def _ringing_note(self, ringing: list[dict[str, Any]] | None, asked: bool = False) -> str:
        """What rings now in the App (ALR1), as the turn's note, or nothing. ``asked``: BAXY's last words were a question."""
        rings = self._rings_told(ringing)
        note = RINGING_ASKED_NOTE if asked else RINGING_NOTE
        return "\n" + note.format(rings=rings, call=self.wires.name("schedule.alarms")) if rings else ""

    @staticmethod
    def _rings_told(ringing: list[dict[str, Any]] | None) -> str:
        """Each alarm or reminder ringing now with its id, words and time, or nothing."""
        rings = []
        for ring in ringing or []:
            ring_id = str((ring or {}).get("id") or "").strip()
            if not ring_id:
                continue
            title = str(ring.get("title") or "").strip()[:FRONT_TITLE_CHARS]
            kind = "la alarma" if ring.get("kind") == "alarm" else "el recordatorio"
            clock = str(ring.get("clock") or "").strip()
            rings.append(f"{kind} id {ring_id}" + (f" «{title}»" if title else "") + (f" de las {clock}" if clock else ""))
        return "; ".join(rings)

    def decide(self, request_id: Any, text: str, pending: dict[str, Any] | None = None,
               unsure: list[tuple[str, float]] | None = None, front: dict[str, Any] | None = None,
               named: list[dict[str, Any]] | None = None,
               ringing: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """``unsure``: the words of a spoken request the ear was not sure of (voice.Voice.unsure). ``front``: the window
        in front of the person when they spoke, as the App read it (title, process), or None. ``named``: the open windows
        their words name. ``ringing``: the alarms and reminders ringing now in the App (id, kind, title, clock)."""
        # F50: whether the ear's note was told, in the trace; a row without it had no word under voice.UNSURE_P. Its words
        # are the person's: only how sure the ear was.
        self._ear_unsure = [round(p, 3) for _, p in unsure or []]
        # Kept even if the decision fails: the App says how a question ended only once.
        self._ran_unanswered(self._ended(pending))
        # Review 2026-10-22: a decision that fails (the model server down, an error) takes back what it added, so the
        # next turn never reads an old request without its answer as one still to do.
        turn = self._turn
        if turn and turn.get("asked"):
            # The person's next words answer the model's own ask_user: they are that call's result, in the same loop, so
            # the steps already run stay in the conversation and are never run again. A new request instead of an
            # answer reaches the model the same way, and the model reads it as what it is.
            # Renew al máximo (auditoría de confirmaciones, 2026-10-23): what waits for the person's «sí» is what the App
            # says with these words, not what waited when the turn began: a confirmation dropped or expired since then
            # was approved with the answer to the question (the old file, after «sí pero el otro» → «¿cuál?» → «el
            # informe»), and one asked since then got nothing_pending.
            asked, after, said = turn.pop("asked"), turn.pop("after_asked", []), turn["text"]
            was = {"pending": turn.get("pending"), "ended": turn.get("ended"), "said": turn.get("said", said),
                   "asked_question": turn.pop("asked_question", ""), "offer": turn.pop("offer", "")}
            # Aid «unopened_app»: the words of the whole turn, the request with the answers to its questions.
            turn["said"] = was["said"] + "\n" + text
            if _aid_on("offer_unanswered"):
                turn["offer"] = was["asked_question"]  # G10: a value only this question said (_offered)
            answered = ANSWERED_NOTE if _aid_on("answer_or_new") else ""
            offer = self._memory_was_off and "memory.enable" in self.wire_to_op.values()
            if self._memory_was_off and _aid_on("memory_off_next") and "memory.enable" in self.wire_to_op.values():
                answered += "\n" + MEMORY_ON_OFFER_NOTE.format(enable=self.wires.name("memory.enable"))
            self._memory_was_off = False
            answer = {"role": "tool", "tool_call_id": asked,
                      "content": text + self._pending_note(pending) + answered + self._unsure_note(unsure or [])
                      + self._ringing_note(ringing)}
            turn["conv"].append(answer)
            for later in after:
                turn["conv"].append({"role": "tool", "tool_call_id": later, "content": NOT_RUN})
            turn["text"], turn["answering"], turn["pending"] = text, True, self._waits(pending)
            turn["confirming"] = self._confirming(pending)
            turn["ended"], turn["pending_op"] = self._ended(pending), self._pending_op(pending)
            try:
                return self._decide_answering(request_id, turn, offer)
            except Exception:
                self._take_back(turn["conv"], answer)
                turn.update(asked=asked, after_asked=after, text=said, **was)
                raise
        self._close_open_calls()
        self._age_bodies()
        doubts = [note for note in (str(m.get("content") or "") for m in self.conversation[-2:])
                  if note.startswith(DOUBT_ASKED)]
        last = self.conversation[-1] if self.conversation else {}
        # Which question BAXY asked is not read from its words: only that its last ones had a «?».
        asked = (last.get("role") == "assistant" and not last.get("tool_calls")
                 and "?" in str(last.get("content") or ""))
        offered = _aid_on("choice_left") and asked
        # RUT6 (RUTINAS.md §5 c, the person's own shortcut): with nothing of BAXY waiting for these words and nothing
        # ringing, a turn that is, whole, the phrase of a routine kept as an order is that order: the words the person
        # saved take the turn's place and the model decides them as any other request (form only: the phrase compared).
        own = "baxy.routines" in self.wire_to_op.values()
        # RUT7 (RUTINAS.md §5 d): while BAXY makes a routine with the person, their words are the answer to its question,
        # never a request of their own nor a routine's phrase. A call waiting for a «sí», a doubt just asked, the tool
        # gone or GUIDE_SILENCE_S without an answer leave the guide with nothing saved.
        # RUT9 (REV9 H4): GUIDE_SILENCE_S counts from the last answer that answered (_guide_answered), and words that
        # are another request (Guide.leaves) leave it unsaved: they are this turn, and the model reads that it was not
        # saved (routine_guide.LEFT_NOTE) to say so.
        left = ""
        if self._guide is not None and (pending or doubts or not own
                                        or time.monotonic() - self._guide_at > GUIDE_SILENCE_S):
            left = "" if pending or doubts or not own else routine_guide.SILENT_NOTE
            self._guide = None
        elif self._guide is not None and not unsure and self._guide.leaves(text, self.routines, self._today()):
            self._log("turn.routine_guide", time.perf_counter(), None, step=self._guide.step, next=None, saved=False,
                      lang=self._guide.lang, left=True)
            self._guide, left = None, self._guide.left_note()
        guide = self._guide
        free = guide is None and not self._rings_told(ringing) and not pending and not doubts and not unsure and own
        # REM6 (REV15 B-1): the turn that left the guide answered its question: no routine's phrase fires in it.
        order = routines.ordered(text, self.routines) if free and not asked and not left else None
        # RUT7: the fixed orders about the routines themselves («crea una rutina», «qué rutinas tengo», «borra la
        # rutina X») are the App's, whole turn only; the one-breath forms («cuando diga X, …») not after a question of
        # BAXY, where they may be its answer.
        ordered = routine_guide.heard(text, self.lang, whole=asked) if free and order is None else None
        said_before, self._heard_last = self._heard_last, text
        if ordered is not None and ordered.it:
            # RUT11 (REV11 B-4): «bórrala», «borra la rutina»: the one routine the last exchange named.
            answered = str(last.get("content") or "") if last.get("role") == "assistant" else ""
            ordered = self._routine_meant(ordered, said_before, answered)
        if ordered is not None and ordered.name and ordered.guide is None and self.routines:
            # REM4 (REV14 A-R2): a name two routines answer to («07:00», the name of one with none of its own and the
            # clock of «despertar») is no routine yet: BAXY asks which, by their names, and only then asks or acts.
            several = routine_guide.answering(ordered.name, self.routines)
            if len(several) > 1:
                ask = routine_guide.Guide(lang=routine_guide.lang_of(ordered.lang), step="which", mode="which",
                                          act=ordered.action, targets=tuple(routine_guide._named(r) for r in several),
                                          ids=routine_guide.keyed(several))
                ordered = routine_guide.Order(ordered.action, ordered.lang, guide=ask)
        if ordered is not None and ordered.name and ordered.action == "delete" and self.routines:
            # REM2 (REV13 B-1), INT33F: the name goes to RoutinesHandler as said, which acts on a routine's own name,
            # phrase or clock and on nothing else (a name it does not find is routine_not_found: nothing is done). A
            # deletion by its clock alone («borra la rutina 07:00» for «despertar») is not by its name: BAXY's question
            # first, and only their «sí» deletes; a change already ends in its own «sí».
            found = routine_guide.find(ordered.name, self.routines)
            if found is not None and not routine_guide.by_name(ordered.name, found):
                ask = routine_guide.Guide(lang=routine_guide.lang_of(ordered.lang), step="confirm_all", mode="all",
                                          act=ordered.action, targets=(routine_guide._named(found),),
                                          ids=routine_guide.keyed([found]))
                ordered = routine_guide.Order(ordered.action, ordered.lang, guide=ask)
        if ordered is not None and ordered.action == "run":
            # «ejecuta la rutina X» is saying X.
            order = routines.ordered(ordered.name, self.routines) if not asked else None
            ordered = None if order is not None or asked else ordered
        if order is not None:
            # RUT7: the turn is the order alone, as if they had just said it. RUT6's note in front of it («la persona
            # dijo «X», la frase de una rutina suya…») made the 4B ask back («¿a qué altavoces?») where the same
            # order said directly was done: equal to the direct order 37 of 48 with the note, 47 of 48 without.
            # RUT10: and the model reads this turn alone (_seen): said in the conversation where the guide had just
            # saved it, the same order was done 32 of 48 times (the 4B asked «¿lo cambio ahora?» or told it done with no
            # call), 45 of 48 in a new conversation and 46 of 48 said directly; one note in place of the exchange: 32-33.
            self._log("turn.routine_phrase", time.perf_counter(), None, routine=order[0], order=True)
            text = order[2]
        self._captures_kept = self._waits(pending)  # CAPTURE_GONE: the App keeps them while a call waits for the «sí»
        clock = {"role": "user", "content": self._clock()}
        self.conversation.append(clock)
        # Noche 2026-10-27 (P0, P0.8): what only this turn knows (the call waiting for the «sí», the words the ear was
        # unsure of) is a note of its own after the clock, so the prompt still begins with the clock the wake read into
        # the slot (prefill) without it; as a note («[») it stays out of what the person said (_said, _gist, _founded).
        # Aid «choice_left»: and that they follow BAXY's own question in words (OFFERED_NOTE).
        opened, self._opened_places = self._opened_places, ""
        notes = (("\n" + OFFERED_NOTE if offered else "") + ("\n" + opened if opened else "")
                 + self._pending_note(pending) + self._capture_note() + self._unsure_note(unsure or []) + self._named_note(named)
                 + self._ringing_note(ringing, asked) + ("\n" + left if left else ""))
        if offered and self._memory_was_off and _aid_on("memory_off_next") and "memory.enable" in self.wire_to_op.values():
            notes += "\n" + MEMORY_ON_OFFER_NOTE.format(enable=self.wires.name("memory.enable"))
        offer = asked and self._memory_was_off and "memory.enable" in self.wire_to_op.values()
        self._memory_was_off = False
        if notes := notes.lstrip("\n"):
            self.conversation.append({"role": "user", "content": notes})
        request = {"role": "user", "content": text}
        self.conversation.append(request)
        try:
            self._trim()
            if _aid_on("clock_omitted"):
                clock["content"] = self._clock()  # the bodies as the trim left them
            # Review 2026-10-22: a text that alone does not fit beside the prefix (a pasted log) failed the turn whole
            # and wordless, as only earlier turns can be trimmed: it keeps its start, halved until it fits, and the cut
            # is said where the model reads it.
            keep = len(text)
            while keep > CUT_TEXT_FLOOR and not self._fits(self._turn_sizes()):
                keep //= 2
                request["content"] = text[:keep] + CUT_TEXT.format(n=len(text) - keep)
            self._turn = {"conv": self.conversation, "queue": [], "awaiting": None, "text": text, "said": text,
                          "pending": self._waits(pending), "ended": self._ended(pending), "answering": bool(doubts),
                          "answering_other": any(DOUBT_OTHER_ASKED in note for note in doubts),
                          "confirming": self._confirming(pending), "pending_op": self._pending_op(pending),
                          "front": self._front_window(front), "in_front": front or {},
                          "ringing": self._rings_told(ringing), "alone": clock if order is not None else None}
            # ALR4 (owner's exception, ring_answer): with something ringing and nothing of BAXY waiting for these words
            # (a «sí» or one that just went unanswered, its doubt's question), and no word the ear was unsure of, a short
            # acknowledgement answers what rings before the model is asked. ALR5 (M1, REV_MENTE): nor after a question in
            # BAXY's last words, whatever the pieces: «¿Para qué hora?» → «Para las dos» stopped what rang and «¿En
            # cuántos minutos?» → «10 minutos» snoozed it, with no model. The rule compares form and cannot tell an
            # answer from an order.
            answer = (ring_answer.heard(text) if self._turn["ringing"] and (not asked or guide is not None)
                      and not pending and not doubts and not unsure and "schedule.alarms" in self.wire_to_op.values()
                      else None)
            if answer is not None:
                return self._ring_answered(request_id, self._turn, answer, ringing or [])
            if guide is not None:
                return self._guide_answered(request_id, self._turn, guide, text, bool(unsure))
            if ordered is not None:
                return self._routine_ordered(request_id, self._turn, ordered)
            # RUT1 (RUTINAS.md §5 b, the person's own shortcut): with nothing of BAXY waiting for these words and nothing
            # ringing, a turn that is, whole, the phrase of a routine the person saved runs it without the model.
            fired = (routines.fired(text, self.routines) if order is None and not self._turn["ringing"] and not asked
                     and not left and not pending and not doubts and not unsure and "baxy.routines" in self.wire_to_op.values()
                     else None)
            if fired is not None:
                return self._routine_fired(request_id, self._turn, fired)
            # REM6 (REV15 B-3): the phrase of a routine turned off is the person's own words, as if it were not there
            # (rem5 asked «¿La activo?» instead, and a phrase that is an order of its own, «sube el volumen», was never done).
            return self._decide_answering(request_id, self._turn, offer)
        except Exception:
            self._take_back(self.conversation, clock)
            self._turn = None
            raise

    @staticmethod
    def _take_back(conv: list[dict[str, Any]], first: dict[str, Any]) -> None:
        """Remove `first` (that very message) and everything after it."""
        del conv[next(i for i, m in enumerate(conv) if m is first):]

    def _decide_answering(self, request_id: Any, turn: dict[str, Any], offer: bool) -> dict[str, Any]:
        """SIS3: the person's words after a call that waits for their «sí» (the App says so, asked before them), or after
        BAXY's question offering what a result offered (memory_disabled: memory_enable, TPV3), are read first by their
        own closed question (_their_answer). For the waiting call, a yes is their answer, given to it as the model's
        confirm_pending would be; a no or anything else is the model's turn as any other, where its own confirm_pending
        yes is not their yes (NOT_THEIR_YES) and its no or unclear still answer (the App drops a call its next line leaves
        behind). SIS3, banco: given for them, «no» also dropped the questions read as one («¿y eso qué significa…?», «wait,
        is that safe?»: 3 of 3), with no answer to what they asked. For the offer, only a yes lets the App take that call
        as their answer (theirYes on its step, NativeTurnLoop.TakesTheOffer)."""
        turn.pop("their_answer", None)
        turn.pop("their_yes", None)
        if turn.get("pending") and turn.get("confirming"):
            started = time.perf_counter()
            answer = self._their_answer(turn, turn.get("pending_op"))
            turn["their_answer"] = answer
            if answer == "yes":
                call = {"id": self._new_id("call"), "wire": CONFIRM["function"]["name"], "arguments": {"answer": answer}}
                turn["conv"].append({"role": "assistant", "content": "", "tool_calls": [{
                    "id": call["id"], "type": "function",
                    "function": {"name": call["wire"], "arguments": json.dumps(call["arguments"])}}]})
                turn["their_yes"] = CONFIRM_OPERATION
                return self._result(request_id, turn, call, None, "turn.decide", started, "")
        elif offer and self._their_answer(turn, "memory.enable") == "yes":
            turn["their_yes"] = "memory.enable"
        return self._next(request_id, "turn.decide", turn)

    def _their_answer(self, turn: dict[str, Any], operation: str | None) -> str:
        """SIS3: whether the person's last words are a yes to what BAXY asked, as the model reads them in one closed
        question that holds only BAXY's last words and theirs (THEIR_ANSWER_NOTE), apart from the conversation: yes, no
        or other. Other when it cannot be read (the server failed or wrote something else): in doubt nothing runs."""
        started = time.perf_counter()
        conv = turn["conv"]
        asked = ""
        for message in reversed(conv[:-1]):  # the last is the person's (their words, or the answer to ask_user)
            if message.get("role") != "assistant":
                continue
            # REM2 (REV13 A-3): with an ask_user, the App publishes only its question; the words beside it («Encontré
            # la página del museo.») were never heard, and read as BAXY's question they turned a clear «dale» into other.
            asked = next(
                (str(json.loads(call["function"].get("arguments") or "{}").get("question") or "")
                 for call in message.get("tool_calls") or [] if call["function"]["name"] == ASK_USER["function"]["name"]),
                "").strip() or str(message.get("content") or "").strip()
            if asked:
                break
        note = THEIR_ANSWER_NOTE.format(asked=" ".join(asked.split())[-THEIR_ANSWER_ASKED:],
                                        said=" ".join(str(turn["text"]).split()))
        body = {"messages": [{"role": "system", "content": THEIR_ANSWER_SYSTEM}, {"role": "user", "content": note}],
                "max_tokens": 4, "grammar": THEIR_ANSWER_GRAMMAR, "chat_template_kwargs": {"enable_thinking": False},
                "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "seed": self.seed}
        reply, failure = None, None
        try:
            reply = self.server.ask_apart(body)
            read = str(reply["choices"][0]["message"].get("content") or "").strip()
        except (urllib.error.URLError, OSError, KeyError, IndexError, TypeError, ValueError) as error:
            read, failure = "", type(error).__name__
        if read not in THEIR_ANSWER_KINDS:
            failure = failure or "unreadable"
        answer = THEIR_ANSWER_KINDS.get(read, "other")
        private = bool(turn.get("private")) or str(operation or "").startswith("memory.")
        self._log("turn.their_answer", started, reply, text=None if private else turn["text"], kind=answer,
                  read=read or None, operation=operation, arguments=None, content=None,
                  **({"failure": failure} if failure else {}))
        return answer

    def _ring_answered(self, request_id: Any, turn: dict[str, Any], answer: ring_answer.Answer,
                       ringing: list[dict[str, Any]]) -> dict[str, Any]:
        """ALR4: the acknowledgement's schedule.alarms call, proposed as the model's would be (in the conversation, the
        kernel authorizes it and the adapter runs it); continue_turn says its receipt in a fixed sentence."""
        started = time.perf_counter()
        call = {"id": self._new_id("call"), "wire": self.wires.name("schedule.alarms"),
                "arguments": answer.arguments(ringing)}
        turn["conv"].append({"role": "assistant", "content": "", "tool_calls": [{
            "id": call["id"], "type": "function",
            "function": {"name": call["wire"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}]})
        turn["ring_answer"] = answer
        self._log("turn.ring_answer", started, None, action=answer.action, minutes=answer.minutes, lang=answer.lang,
                  kind=call["arguments"].get("kind"))
        return self._result(request_id, turn, call, None, "turn.decide", started, "")

    def _routine_fired(self, request_id: Any, turn: dict[str, Any], name: str) -> dict[str, Any]:
        """RUT1: baxy.routines run of the routine whose phrase the person said, proposed as the model's call would be (in
        the conversation; the kernel authorizes it and the App runs it); continue_turn proposes its steps."""
        started = time.perf_counter()
        call = {"id": self._new_id("call"), "wire": self.wires.name("baxy.routines"),
                "arguments": {"action": "run", "name": name}, "mind": True}
        turn["conv"].append({"role": "assistant", "content": "", "tool_calls": [{
            "id": call["id"], "type": "function",
            "function": {"name": call["wire"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}]})
        self._log("turn.routine_phrase", started, None, routine=name)
        return self._result(request_id, turn, call, None, "turn.decide", started, "")

    def _routine_meant(self, ordered: routine_guide.Order, said: str, answered: str) -> routine_guide.Order | None:
        """RUT11 (REV11 B-4): the routine an order without its name means: the one the last exchange named (the
        person's words beside «rutina», or BAXY's between «»); several named, BAXY asks which; none, its fallback."""
        named = routine_guide.named_in(said, answered, self.routines)
        if len(named) == 1:
            return dataclasses.replace(ordered, name=routine_guide._named(named[0]), it=False)
        if len(named) > 1:
            guide = routine_guide.Guide(lang=ordered.lang, step="which", mode="which", act=ordered.action,
                                        targets=tuple(routine_guide._named(r) for r in named),
                                        ids=routine_guide.keyed(named))
            return routine_guide.Order(ordered.action, ordered.lang, guide=guide)
        return routine_guide.Order("list", ordered.lang) if ordered.fallback == "list" else None

    def _routine_ordered(self, request_id: Any, turn: dict[str, Any], ordered: routine_guide.Order) -> dict[str, Any]:
        """RUT7: a fixed order about the routines. «nueva rutina» (or a one-breath phrase) opens the guide and BAXY
        asks its question; the others are the baxy.routines call they name, proposed as the model's would be.
        RUT11 (REV11 B-4): «cambia la rutina X» opens the guide of its change; every routine at once is one call each
        (deleting them all after its «sí»)."""
        started = time.perf_counter()
        lang = routine_guide.lang_of(ordered.lang)
        if ordered.action == "change" and ordered.guide is None:
            found = routine_guide.find(ordered.name, self.routines)
            if found is None:
                names = [routine_guide._named(r) for r in self.routines if isinstance(r, dict)]
                text = routine_guide.TEXT[lang]
                have = (text["have"].format(items=routine_guide._listed([f"«{n}»" for n in names], lang)) if names
                        else text["have_none"])
                self._log("turn.routine_order", started, None, action="change", lang=lang, step=None, found=False)
                return self._guide_said(request_id, turn, text["not_found"].format(name=ordered.name, have=have),
                                        "turn.decide", started)
            ordered = dataclasses.replace(ordered, guide=routine_guide.Guide.changing(found, lang, ordered.part))
        if ordered.action.endswith("_all"):
            act = ordered.action[:-4]
            chosen = [r for r in self.routines if isinstance(r, dict)
                      and (act == "delete" or (r.get("active") is not False) == (act == "disable"))]
            names = tuple(routine_guide._named(r) for r in chosen)
            self._log("turn.routine_order", started, None, action=ordered.action, lang=lang, step=None, count=len(names))
            if not names:
                text = routine_guide.TEXT[lang]
                none = "none" if act == "delete" or not self.routines else "none_on" if act == "disable" else "none_off"
                return self._guide_said(request_id, turn, text[none], "turn.decide", started)
            if act == "delete":
                guide = routine_guide.Guide(lang=lang, step="confirm_all", mode="all", act=act, targets=names,
                                            ids=routine_guide.keyed(chosen))
                self._guide, self._guide_at = guide, time.monotonic()
                return self._guide_said(request_id, turn, guide.question(), "turn.decide", started)
            return self._routine_calls(request_id, turn, act, list(names), lang, started)
        self._log("turn.routine_order", started, None, action=ordered.action, lang=ordered.lang,
                  step=ordered.guide.step if ordered.guide is not None else None)
        if ordered.guide is not None:
            ended = ordered.guide.step == "steps_only"
            self._guide, self._guide_at = (None if ended else ordered.guide), time.monotonic()
            return self._guide_said(request_id, turn, ordered.said or ordered.guide.question(), "turn.decide", started)
        arguments = {"action": ordered.action, **({"name": ordered.name} if ordered.name else {})}
        return self._routine_call(request_id, turn, arguments, (ordered.action, ordered.lang, ordered.name), started)

    def _routine_calls(self, request_id: Any, turn: dict[str, Any], act: str, names: list[str], lang: str,
                       started: float) -> dict[str, Any]:
        """RUT11 (REV11 B-4): the same baxy.routines action on each of these routines, one call after the other (each
        authorized by the kernel); continue_turn proposes the next on a completed receipt and says them all at the end
        in one sentence (routine_guide.told_all). A receipt that is not completed goes to the model as any other."""
        turn["guide_rest"], turn["guide_done"] = names[1:], []
        return self._routine_call(request_id, turn, {"action": act, "name": names[0]}, ("all", lang, act), started)

    def _guide_answered(self, request_id: Any, turn: dict[str, Any], guide: routine_guide.Guide, text: str,
                        unsure: bool) -> dict[str, Any]:
        """RUT7: the person's words as the answer to the guide's question: its next question, said as it is, or (the
        last «sí») the baxy.routines create of what they answered. Nothing else is done with these words."""
        started = time.perf_counter()
        was = guide.step
        said, arguments, ended = guide.answer(text, self.routines, unsure, self._today())
        # RUT9 (REV9 H4): an answer that answered nothing does not put the silence off.
        self._guide = None if ended else guide
        self._guide_at = self._guide_at if guide.misses and not ended else time.monotonic()
        self._log("turn.routine_guide", started, None, step=was, next=None if ended else guide.step,
                  saved=arguments is not None, lang=guide.lang)
        if arguments is not None and guide.mode == "all":
            turn["guide_named"] = {guide.id_of(name): name for name in guide.targets}
            return self._routine_calls(request_id, turn, guide.act, [guide.id_of(name) for name in guide.targets],
                                       guide.lang, started)
        if arguments is not None:
            # RUT11: the receipt's sentence is the call's own (create, change, or the one «which» chose); REM6: by the
            # name it was asked by, the call by its id
            told = (arguments["action"], guide.lang, guide.name_of(str(arguments.get("name") or "")) or guide.phrase)
            return self._routine_call(request_id, turn, arguments, told, started)
        return self._guide_said(request_id, turn, said, "turn.decide", started)

    def _routine_call(self, request_id: Any, turn: dict[str, Any], arguments: dict[str, Any],
                      told: tuple[str, str, str], started: float, stage: str = "turn.decide") -> dict[str, Any]:
        """RUT7: a baxy.routines call of the mind's own, in the conversation as the model's would be (the kernel
        authorizes it and the App runs it); continue_turn says its receipt in a fixed sentence (routine_guide.told)."""
        call = {"id": self._new_id("call"), "wire": self.wires.name("baxy.routines"), "arguments": arguments,
                "mind": True}
        turn["conv"].append({"role": "assistant", "content": "", "tool_calls": [{
            "id": call["id"], "type": "function",
            "function": {"name": call["wire"], "arguments": json.dumps(arguments, ensure_ascii=False)}}]})
        turn["guide_call"] = told
        return self._result(request_id, turn, call, None, stage, started, "")

    def _guide_said(self, request_id: Any, turn: dict[str, Any], said: str, stage: str,
                    started: float) -> dict[str, Any]:
        """RUT7: a fixed sentence of the guide as BAXY's words of this turn."""
        turn["conv"].append({"role": "assistant", "content": said})
        if self.foresee is not None:
            try:
                self.foresee(said, True)  # its voice is made while the App publishes it, as _next's words
            except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                pass
        return self._result(request_id, turn, None, None, stage, started, said)

    def _routine_steps(self, request_id: Any, turn: dict[str, Any], received: str) -> dict[str, Any] | None:
        """RUT1: after a completed run, its steps as calls of BAXY in this turn, one by one through the App (each one
        authorized by the kernel, its «sí» included); a routine that only says gets its texts said. None: not a run."""
        given = routines.steps(received)
        if given is None:
            return None
        calls, says = given
        started = time.perf_counter()
        if not calls:
            return self._routine_said(request_id, turn, says, started) if says else None
        proposed = [{"id": self._new_id("call"), "wire": self.wires.name(op), "arguments": arguments}
                    for op, arguments in calls]
        turn["conv"].append({"role": "assistant", "content": "", "tool_calls": [{
            "id": call["id"], "type": "function",
            "function": {"name": call["wire"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}
            for call in proposed]})
        turn["queue"] = proposed[1:]
        if says:
            turn["routine_say"] = says
        self._log("turn.routine_steps", started, None, steps=len(proposed), says=len(says))
        return self._result(request_id, turn, proposed[0], None, "turn.continue", started, "")

    def _routine_said(self, request_id: Any, turn: dict[str, Any], says: list[str], started: float) -> dict[str, Any]:
        """RUT1: a routine's «say» steps, once every call of it completed: the person's own texts, said as they wrote
        them (RUTINAS.md §5)."""
        said = " ".join(text.strip() for text in says if text.strip())
        turn["conv"].append({"role": "assistant", "content": said})
        if self.foresee is not None:
            try:
                self.foresee(said, True)
            except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                pass
        return self._result(request_id, turn, None, None, "turn.continue", started, said)

    def beat(self, request_id: Any, context: dict[str, Any]) -> dict[str, Any]:
        """The heartbeat: nobody spoke; the model looks at the moment in a conversation of its own (OpenClaw's isolated
        heartbeat session), says what is happening and whether to intervene, and only then acts, proposes or says
        something. Same tools (the cached prefix: the template puts them first) and a system text without the «¿ya lo
        hiciste?» sentence; what it did joins the person's conversation only if it intervened."""
        started = time.perf_counter()
        self._turned = True
        if self._beat is not None:
            # Review 2026-10-22: a heartbeat the App never ended is closed as end_beat closes it, never overwritten
            # with what BAXY said or did in it unsaid.
            self.end_beat()
        conv = [{"role": "user", "content": beat_message(context)}]
        # Review 2026-10-22: a heartbeat that read the person's memory keeps out of the trace what it deduced from it and
        # what it said, as a turn does from its memory call on (_result).
        private = bool(context.get("memory"))
        # The decision whether to intervene is greedy: on the open scenes 32 → 34 of 40 sampled against greedy.
        reply = self.server.chat({"messages": [{"role": "system", "content": self._system(beat=True)}, *conv],
                                  "tools": self.tools, "tool_choice": "none", "max_tokens": 400,
                                  "chat_template_kwargs": {"enable_thinking": False},
                                  "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                                  "seed": 0,
                                  "response_format": {"type": "json_schema",
                                                      "json_schema": {"name": "latido", "schema": BEAT_DECISION}}})
        content = (reply["choices"][0]["message"].get("content") or "").strip()
        try:
            decision = json.loads(content)
        except json.JSONDecodeError:
            decision = None
        if not isinstance(decision, dict) or not isinstance(decision.get("intervenir"), bool):
            # Unreadable (cut by the token budget, or not the schema): said as what it is, never as a silence.
            self._log("turn.beat.decide", started, reply, text="[latido]", content=None if private else content,
                      failure="unreadable")
            return {"type": "turn.result", "id": request_id, "kind": "failure", "operation": None, "arguments": None,
                    "question": "", "reply": ""}
        intervene = decision["intervenir"]
        self._log("turn.beat.decide", started, reply, text="[latido]", content=None if private else content,
                  intervene=intervene)
        self._beat = {"conv": conv, "queue": [], "awaiting": None, "text": "[latido]", "beat": True,
                      "silent": not intervene, "private": private}
        if not intervene:
            return {"type": "turn.result", "id": request_id, "kind": "silence", "operation": None, "arguments": None,
                    "question": "", "reply": ""}
        # The analysis stays as the model's own words, not as JSON: with its JSON before it, the model answered the
        # second move in JSON again (practice scene P023). Al máximo 10.3: the motives it found go before it, as words
        # too: the move that acts read only the analysis (PALANCAS-nb 10.3, scenes P002 and P023).
        motives = "; ".join(f"{m}: {decision.get(m) or ''}" for m in _MOTIVES)
        conv.append({"role": "assistant", "content": f"{motives}. {decision.get('analisis') or ''}".rstrip()})
        conv.append({"role": "user", "content": BEAT_ACT})
        return self._next(request_id, "turn.beat", self._beat)

    def end_beat(self) -> None:
        """The App ended the heartbeat's turn: a beat that was not silent is part of the conversation from now on (the
        person may answer what BAXY said or proposed); a silent one leaves no trace."""
        beat, self._beat = self._beat, None
        if not beat or beat.get("silent"):
            return
        if beat.get("awaiting"):
            beat["conv"].append({"role": "tool", "tool_call_id": beat["awaiting"], "content": NO_RESULT})
            self._ran_add(beat.get("calling"), NO_RESULT_RAN)
        if beat.get("asked"):
            beat["conv"].append({"role": "tool", "tool_call_id": beat["asked"], "content": ASKED})
        pending = [c["id"] for c in beat.get("queue") or []]
        for call_id in [*beat.get("after_asked", []), *pending]:
            if call_id:
                beat["conv"].append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
        self._close_open_calls()
        # Review 2026-10-22 (R10.2 of the notebook): what the person may answer is what BAXY said and did, not what the
        # heartbeat read (its moment, its rules, its analysis and the order to act, the first three messages).
        acted = beat["conv"][3:]
        if acted:
            self.conversation.extend([{"role": "user", "content": BEAT_MARK}, *acted])
        self._trim()

    def prefill(self, clock: bool = False) -> bool:
        """Al máximo W5 (PREFILL_MARK): with no turn open, the conversation is read into the slot as the next request
        will show it; whether it was. The template is asked for the conversation with a request after it (a user
        message, as the clock of the next turn or a confirmation's label is), and its text is cut where that request
        begins: what comes before it is the start of the next prompt to the character, and it ends in «<|im_end|>\\n»
        before «<|im_start|>», so it is tokenized there as in the whole prompt. Nothing is read while a call waits for
        its result, while the model's question (ask_user) waits for the person's words (they come as its result, and
        the turn's messages keep their form), during a heartbeat, or with nothing to read.

        ``clock`` (al máximo, palanca 5, early.py: «Baxy» was heard): the next turn's clock is read too, as a turn with
        no call waiting for the person's «sí» begins, so the GPU is awake and the slot holds all but the person's words
        when they come. The prompt does not change: a clock of another minute is read by the decision itself from where
        they differ (a call waiting for the «sí» and the ear's unsure words are a note of their own after the clock,
        Mind.decide). BAXY_RENEW_PREFILL does not turn it off (BAXY_RENEW_WAKE_WARM does)."""
        self._prefill_rounds = self._prefill_rounds + 1 if self.gave_way is not None else 1
        turn, self.gave_way = self._turn or {}, None
        if ((not clock and os.environ.get("BAXY_RENEW_PREFILL", "").strip() == "0")
                or (not self.conversation and not clock) or self._beat is not None
                or turn.get("awaiting") or turn.get("asked") or turn.get("queue")):
            return False
        started = time.perf_counter()
        self._age_bodies()  # as the next decision will show it, so it does not re-read from the older turn on
        told = {"clock": True} if clock else {}  # the wake's row says so, whether it was read, failed or gave way
        self._captures_kept = False  # as a turn with nothing waiting will tell it
        after = [{"role": "user", "content": self._clock()}] if clock else []
        body = {"messages": [{"role": "system", "content": self._system()}, *self._history(self.conversation),
                             *after, {"role": "user", "content": PREFILL_MARK}],
                "tools": self.tools, "chat_template_kwargs": {"enable_thinking": False}}
        try:
            rendered = self.server.template(body)
            cut = rendered.rfind("<|im_start|>user\n" + PREFILL_MARK)
            if cut <= 0 or not rendered[:cut].endswith("<|im_end|>\n"):
                self._log("warm.history", started, None, failure="unrendered", **told)
                return False
            # Auditoría de la mente (w8): the slot now holds the person's conversation (a kept session's, loaded before
            # any turn), so the warm-up no longer keeps it on disk (Mind.warm), as after a turn.
            self._turned = True
            reply = self.server.prefill(rendered[:cut])
        except Yielded:  # not a failure: it is read again once the request is answered (gave_way)
            self._log("warm.history", started, None, yielded=True, **told)
            self.gave_way = clock
            return False
        except Exception as error:  # noqa: BLE001 - the next decision reads it itself, as it did before
            self._log("warm.history", started, None, failure=type(error).__name__, **told)
            if isinstance(error, TimeoutError) and self._prefill_rounds < PREFILL_ROUNDS:
                self.gave_way = clock
            return False
        self._log("warm.history", started, reply, messages=len(self.conversation), **told)
        return True

    def _ran_add(self, calling: Any, outcome: str, call_id: str | None = None) -> None:
        """One call of the session and how it ended, for the clock (8.1)."""
        wire = CONFIRM["function"]["name"] if calling == CONFIRM_OPERATION else self.wires.name(str(calling or "?"))
        self._ran, self._ran_count = [*self._ran, f"{wire} → {outcome}"][-SESSION_CALLS:], self._ran_count + 1
        self._ran_ids = [*self._ran_ids, call_id][-SESSION_CALLS:]

    def _ran_unanswered(self, ended: dict[str, Any] | None) -> None:
        """The session's call whose question ended unanswered, as the App says it, no longer waits for a «sí» (8.1): not
        in the clock's calls, nor in the facts lines of the turn that asked."""
        if ended is None:
            return
        wire = self.wires.name(str(ended["operation"]))
        if f"{wire} → {WAITS_FOR_YES}" not in self._ran:
            return
        first = len(self._ran) - 1 - self._ran[::-1].index(f"{wire} → {WAITS_FOR_YES}")
        # Prefijo c3, S4: an unclear answer left the same question waiting, and its confirm_pending says so too (named
        # with aid «confirm_names_call», bare without it).
        confirm = CONFIRM["function"]["name"]
        again = {f"{confirm} ({wire}) → {WAITS_FOR_YES}", f"{confirm} → {WAITS_FOR_YES}"}
        # One the kernel challenged again after it had started may have had its effect (as ended_result tells it).
        how = (NO_RESULT_RAN if ended.get("effectUncertain") is True
               else UNANSWERED.get(str(ended.get("ended")), UNANSWERED["dropped"]))
        for last in [first, *(index for index in range(first + 1, len(self._ran)) if self._ran[index] in again)]:
            waiting = self._ran[last]
            told = waiting[:-len(WAITS_FOR_YES)] + how
            self._ran = [told if index == last else entry for index, entry in enumerate(self._ran)]
            # Sesión larga sobre 8fa1e1430 (R7-NB-2): and so does the turn that asked, which the model reads beside the
            # clock: its facts line still said «espera el sí», and the same close of a new window tramos later was a
            # question again (clarify 0.46 against app 0.41, confirm 0.11 as a rival). Retold from its result to the
            # next clock, once: the prefix is read again from there. The newest result with its id that still says it
            # waits: the model's ids may repeat.
            call_id = self._ran_ids[last]
            results = [i for i, m in enumerate(self.conversation) if call_id and m["role"] == "tool"
                       and m.get("tool_call_id") == call_id and waiting in str(m.get("content") or "")]
            for message in self.conversation[results[-1]:] if results else []:
                if message["role"] == "user" and str(message.get("content") or "").startswith(CLOCK_MARK):
                    break
                if message["role"] == "tool":
                    message["content"] = str(message.get("content") or "").replace(waiting, told)

    def _ran_told(self, captures_kept: bool = False) -> list[str]:
        """The clock's calls of the session (8.1). Aid «clock_omitted» (auditoría de la mente, w8, 2026-10-23): one whose
        result lost its body (1.1, or its turn was cut) is told as the kept facts lines tell it (COMPACTED_FACTS: «lo
        que vio se omitió»), not «lo que vio está arriba» beside those lines saying it was left out. Aid «capture_gone»
        (CAPTURE_GONE): unless `captures_kept`, a call whose result names a capture says it is gone and of when it was."""
        told = self._ran
        if _aid_on("clock_omitted"):
            bodies = {m.get("tool_call_id") for m in self.conversation
                      if m.get("role") == "tool" and not str(m.get("content") or "").startswith(COMPACTED)}
            told = [entry if call_id is None or call_id in bodies else _omitted(entry)
                    for entry, call_id in zip(told, self._ran_ids)]
        if captures_kept or not _aid_on("capture_gone"):
            return told
        named: dict[Any, str] = {}
        taken: dict[str, str] = {}
        for message in self.conversation:
            if message.get("role") != "tool":
                continue
            for capture in _captures(_result_body(str(message.get("content") or ""))):
                named.setdefault(message.get("tool_call_id"), capture["captureId"])
                if (when := _taken_at(capture.get("createdAtUtc"))) is not None:
                    taken[capture["captureId"]] = when
        return [entry + CAPTURE_GONE.format(when=taken.get(named[call_id], "entonces"))
                if call_id is not None and call_id in named else entry
                for entry, call_id in zip(told, self._ran_ids)]

    def _capture_note(self) -> str:
        """Aid «capture_gone» (CAPTURE_NOTE): the newest capture of the earlier turns is gone, unless a call waits."""
        if self._captures_kept or not _aid_on("capture_gone"):
            return ""
        newest, taken, aged, read = None, {}, {}, {}
        names = {call.get("id"): (call.get("function") or {}).get("name") for message in self.conversation
                 for call in message.get("tool_calls") or [] if isinstance(call, dict)}
        now = self._now()
        for message in self.conversation:
            if message.get("role") == "tool":
                for capture in _captures(_result_body(str(message.get("content") or ""))):
                    newest = capture["captureId"]
                    if (when := _taken_at(capture.get("createdAtUtc"))) is not None:
                        taken[newest] = when
                    if (age := _age(capture.get("createdAtUtc"), now)) is not None:
                        aged[newest] = age
                    if isinstance(name := names.get(message.get("tool_call_id")), str):
                        read.setdefault(newest, {})[name] = None
        if newest is None:
            return ""
        shown = _shown_by(list(read.get(newest, {})))
        if newest in aged:
            return CAPTURE_AGE_NOTE.format(age=aged[newest], shown=shown)
        return CAPTURE_NOTE.format(when=taken.get(newest, "un turno anterior"), shown=shown)

    def _receipt(self, turn: dict[str, Any], wire: str, observation: str, outcome: str) -> None:
        """A call of the turn as the answer check reads it (aid «answer_check»), and in the session's calls. A
        confirmation's own call stands for the operation it answered: the one its result names, else the one the App
        said was waiting, else any (CONFIRM_OPERATION)."""
        op = str(turn.get("calling") or "?")
        if op == CONFIRM_OPERATION:
            try:
                named = json.loads(observation).get("operation")
            except (json.JSONDecodeError, AttributeError):
                named = None
            op = str(named or turn.get("pending_op") or CONFIRM_OPERATION)
        completed = outcome.startswith(COMPLETED_OUTCOMES)
        read = self.risk.get(self.wires.name(op)) == "read_only"
        try:
            arguments = json.loads(turn.get("calling_args") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        turn.setdefault("receipts", []).append({"op": op, "tool": wire, "arguments": arguments,
                                                "observation": observation, "outcome": outcome,
                                                "completed": completed, "read": read})
        self._session_call((op, completed, read))
        self._states = [*self._states, {"op": op, "tool": wire, "observation": _scalars(observation), "outcome": outcome,
                                        "completed": completed, "read": read}][-SESSION_CALLS:]

    def _session_call(self, call: tuple[str, bool, bool]) -> None:
        """One call of the session for the answer check, which only asks whether one of a kind completed or ran at all:
        each (operation, completed, read) is kept once (revisión de calidad de la mente: one entry per call, for good,
        exported with the session and deep-copied by every early decision)."""
        if self._calls is not None and call not in self._calls:
            self._calls.append(call)

    def _close_open_calls(self) -> None:
        """A call the App never answered (the turn ended first) gets its honest result, so the conversation stays a
        valid tool transcript and the model never reads an unanswered call as done."""
        turn = self._turn or {}
        if turn.get("awaiting") and (turn.get("unsure") or {}).get("id") != turn["awaiting"]:  # P2.43: never ran
            self.conversation.append({"role": "tool", "tool_call_id": turn["awaiting"], "content": NO_RESULT})
            self._ran_add(turn.get("calling"), NO_RESULT_RAN)
            op = str(turn.get("calling") or "?")  # it may have run: never a completed call of the session
            self._session_call((op, False, self.risk.get(self.wires.name(op)) == "read_only"))
        if turn.get("asked"):
            self.conversation.append({"role": "tool", "tool_call_id": turn["asked"], "content": ASKED})
        pending = [c["id"] for c in turn.get("queue") or []]
        for call_id in [*turn.get("after_asked", []), *pending]:
            if call_id:
                self.conversation.append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
        self._turn = None

    def _trim(self) -> None:
        """Keep the last turns that fit the budget; a turn starts at its clock, so no call loses its result. While they
        fit, nothing already sent changes (the model re-reads from the first changed message on). Past a bound, one
        rewrite: the oldest turns go down to TRIM_TURNS_TO of the count, every kept closed turn loses its results'
        bodies (1.1, in one block), and the oldest turns go until what is left fits TRIM_TO of every bound."""
        # Renew al máximo (w5): 1.1 left out bodies only down to TRIM_TO of the characters and kept every turn, so the
        # count bound came back a turn or two later and the whole history was re-read again (sesión larga, notebook
        # 2026-10-22: turns 12 and 14 re-read 2,844 and 1,932 tokens, the base 747 and 333). One deep rewrite instead.
        turns = self._turn_sizes()
        if len(turns) <= 1 or self._fits(turns):
            return
        dropped = 0
        while dropped < len(turns) - 1 and len(turns) - dropped > self._bounds()[0] * TRIM_TURNS_TO:
            dropped += 1
        starts = [t[0] for t in turns[dropped:]]
        if any([self._compact(self.conversation[start:end]) for start, end in zip(starts, starts[1:])]):
            turns = self._turn_sizes()
        while dropped < len(turns) - 1 and not self._fits(turns[dropped:], TRIM_TO, cut=True):
            dropped += 1
        if dropped:
            self._drop(turns[dropped][0], dropped)
        self._prune_refs()

    def _age_bodies(self) -> None:
        """Aid «old_bodies» (noche P0.2, OLD_BODY_CHARS): before the newest closed turn with results, each result whose
        body is longer than OLD_BODY_CHARS keeps only its turn's facts. The prefix is edited only there, once per turn,
        and the read ahead does it before the next decision (prefill)."""
        starts = self._turn_starts()
        if len(starts) < 2 or not _aid_on("old_bodies"):
            return
        # Revisión de PC-R1-W2: a turn with no results (a question answered in words, a doubt and its answer) aged the
        # reading before it, and a third question about one reading found it gone. Only a newer reading ages one.
        ends = [*starts[1:], len(self.conversation)]
        read = [start for start, end in zip(starts, ends)
                if any(m["role"] == "tool" and TURN_FACTS in str(m.get("content") or "")
                       for m in self.conversation[start:end])]
        old = self.conversation[:read[-1] if read else 0]
        if self._compact([m for m in old if str(m.get("content") or "").rfind(TURN_FACTS) > OLD_BODY_CHARS]):
            self._prune_refs()

    def _prune_refs(self) -> None:
        """Revisión de calidad de la mente (2026-10-25): the short references the conversation no longer shows (their
        turns cut out, their results' bodies left out) are not kept: every address of the session stayed in _refs, and
        with it in the exported session (the App's 1 MiB per line) and in what an early decision deep-copies. An open
        heartbeat's own messages count as shown."""
        if not self._refs:
            return
        shown = json.dumps([self.conversation, (self._beat or {}).get("conv"), (self._turn or {}).get("conv")],
                           ensure_ascii=False)
        alive = set(_REF.findall(shown))
        if len(alive) < len(self._refs):
            self._refs = {ref: value for ref, value in self._refs.items() if ref in alive}
            self._ref_of = {value: ref for ref, value in self._refs.items()}

    def _drop(self, end: int, turns: int) -> None:
        """Take out the oldest `turns`, up to the first kept turn's clock (`end`): an earlier note of what was cut goes
        with them, and the new one says how many are gone and, for the newest of them that fit, what the person asked
        and how each call ended (w5). In place: an open turn's conversation is this same list (the notebook's review of
        1.1/1.2, 2026-10-22)."""
        cut = self.conversation[:end]
        lines = []
        earlier = str(cut[0].get("content") or "") if cut else ""
        if earlier.startswith(TRIMMED[:TRIMMED.index(":")]):
            lines = earlier.split(GIST_LINE)[1:]
            lines[-1:] = [lines[-1].split("\n")[0]] if lines else []
            cut = cut[1:]
            # A kept session starts its count again (load_session): the earlier note's own count is not lost.
            told = re.match(r"\D*(\d+)", earlier)
            self.trimmed_turns = max(self.trimmed_turns, int(told.group(1)) if told else 0)
        starts = [i for i, m in enumerate(cut)
                  if i and m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]
        bounds = [0, *starts, len(cut)]
        lines += [self._gist(cut[a:b]) for a, b in zip(bounds, bounds[1:]) if a < b]
        lines = [line for line in lines if line]
        kept: list[str] = []
        for line in reversed(lines):
            if sum(len(k) for k in kept) + len(line) > GIST_CHARS:
                break
            kept.insert(0, line)
        del self.conversation[:end]
        self.trimmed_turns += turns
        note = (TRIMMED_GIST.format(n=self.trimmed_turns, k=len(kept), lines="".join(GIST_LINE + k for k in kept))
                if kept else TRIMMED.format(n=self.trimmed_turns))
        self.conversation.insert(0, {"role": "user", "content": note})

    @staticmethod
    def _gist(messages: list[dict[str, Any]]) -> str:
        """One cut turn in a line (w5): the person's words, clipped, and how its calls ended, from the facts line each
        loop of calls ended with (a failure keeps its code) and from the results the mind wrote for calls that never got
        one. Empty for a turn with no words of the person (a heartbeat's own)."""
        said = next((str(m.get("content") or "") for m in messages if m["role"] == "user"
                     and not str(m.get("content") or "").startswith("[")), "")  # a note, the clock or BEAT_MARK
        said = " ".join(said.split())
        if not said:
            return ""
        if len(said) > GIST_WORDS:
            said = said[:GIST_WORDS].rstrip() + "…"
        names = {c.get("id"): str((c.get("function") or {}).get("name") or "?")
                 for m in messages for c in m.get("tool_calls") or []}
        calls: list[str] = []
        facts, unrun = "", []
        # A loop of calls (the turn's, or a confirmation's) ends at a message of the person or the mind; its last facts
        # line lists all of its calls, each earlier one a part of it.
        for message in [*messages, {"role": "user"}]:
            content = str(message.get("content") or "")
            at = content.rfind(TURN_FACTS)
            if message["role"] == "tool" and at >= 0:
                # Its body is gone with the turn.
                facts = _omitted(content[at + len(TURN_FACTS):].split("\n")[0].removesuffix("]"))
            elif message["role"] == "tool" and content in {NO_RESULT, NOT_RUN, NOT_RUN_AFTER, NOT_RUN_AFTER_KEYS}:
                ended = NO_RESULT_RAN if content == NO_RESULT else GIST_NOT_RUN
                unrun.append(f"{names.get(message.get('tool_call_id'), '?')} → {ended}")
            elif message["role"] == "user":
                calls += [facts] if facts else []
                calls += unrun
                facts, unrun = "", []
        return f"«{said}» → " + ("; ".join(calls) if calls else GIST_NO_CALLS)

    @staticmethod
    def _compact(messages: list[dict[str, Any]]) -> bool:
        """Each call's result among these messages (the ones that end with their turn's facts) keeps only those facts
        after COMPACTED; the calls stay, so none loses its result. Whether any result changed."""
        compacted = False
        for message in messages:
            content = str(message.get("content") or "")
            at = content.rfind(TURN_FACTS)
            if message["role"] == "tool" and at > len(COMPACTED):
                message["content"] = COMPACTED + _omitted(content[at:])  # w5: the facts no longer point at a body
                compacted = True
        return compacted

    def _turn_sizes(self) -> list[tuple[int, int, int]]:
        """Each turn of the conversation as (its first message, characters, tokens); the first turn takes in what comes
        before its clock (the note of a cut, a bench's history). Al máximo 1.3/1.4 (2026-10-22): the whole history went
        to /tokenize at every check, and the cut checked again after each turn it took out; now each turn's text is
        counted once and kept (their sum differs from the whole text's by a token at most where two turns meet), so a
        check counts only the turns that changed (the open one, the one before once its answer came) and a cut counts
        nothing more. The last reply's
        usage.prompt_tokens was not used: it does not count what came after that reply (a result, the clock, the
        request), and the template's own tokens are not the history's."""
        if not self.conversation:
            return []
        bounds = [0, *self._turn_starts()[1:], len(self.conversation)]
        texts = ["".join(json.dumps(m, ensure_ascii=False) for m in self.conversation[a:b])
                 for a, b in zip(bounds, bounds[1:])]
        if self.prefix_tokens:
            self._tokens = {t: self._tokens[t] if t in self._tokens else len(self.server.tokenize(t)) for t in texts}
        return [(a, len(t), self._tokens.get(t, 0)) for a, t in zip(bounds, texts)]

    def _bounds(self) -> tuple[int, int, int]:
        """The history's bounds (uso-51): turns, characters and the tokens the context leaves beside the prefix and the
        turn. The count and the characters grow with those tokens in proportion to HISTORY_TOKENS, never below
        HISTORY_TURNS and HISTORY_CHARS; before the warm-up the prefix is not known, and they are only those."""
        if not self.prefix_tokens:
            return HISTORY_TURNS, HISTORY_CHARS, 0
        room = self.server.context - self.prefix_tokens - TURN_ROOM_TOKENS
        scale = max(1.0, room / HISTORY_TOKENS)
        return int(HISTORY_TURNS * scale), int(HISTORY_CHARS * scale), room

    def _fits(self, turns: list[tuple[int, int, int]], share: float = 1.0, cut: bool = False) -> bool:
        """Whether these turns fit `share` of every bound (_bounds); what a cut keeps (`cut`), also what the server reads
        again in time (LlmServer.reread_tokens)."""
        count, chars, room = self._bounds()
        tokens = sum(t[2] for t in turns)
        return (len(turns) <= count * share and sum(t[1] for t in turns) <= chars * share
                and (not self.prefix_tokens or (tokens <= room * share and (not cut or tokens <= self.server.reread_tokens))))

    def _turn_starts(self) -> list[int]:
        return [i for i, m in enumerate(self.conversation)
                if m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]

    @staticmethod
    def _web_queries(turn: dict[str, Any]) -> list[str]:
        """What a web page is read for (goal h-web): the person's words and the turn's web.search queries."""
        queries = [str(turn.get("text") or "")]
        for receipt in turn.get("receipts") or []:
            query = receipt.get("arguments", {}).get("query") if receipt.get("op") == "web.search" else None
            if isinstance(query, str):
                queries.append(query)
        return [q for q in queries if q.strip()]

    def continue_turn(self, request_id: Any, observation: str, final: bool = False,
                      beat: bool = False) -> dict[str, Any]:
        """The verified result of the call the App ran goes back as that call's tool message. ``final``: the App closes
        the turn (steps spent, engine down, or a confirmation waiting), so the model answers now in text from what the
        results show. ``beat``: the heartbeat's turn."""
        turn = self._beat if beat else self._turn
        if turn and not turn.get("awaiting") and turn["conv"] and turn["conv"][-1]["role"] == "tool":
            # R7-NB-1 (CU C03): the result is already in the turn and no decision came after it (the request ran past its
            # budget, and the turn ended with no words): the App asks for that decision again, and the model decides
            # from the results it has, without reading the same result in twice; in words when the mind had closed the
            # turn's calls itself (a refused repeat, the calculations' cap: _next's ``closed``).
            self._log("turn.continue", time.perf_counter(), None, kind="asked_again", operation=turn.get("calling"))
            turn["asked_again"] = True
            started, written = time.perf_counter(), turn.get("held_back")
            try:
                result = self._next(request_id, "turn.continue", turn, final=final or bool(turn.get("closed")))
            except TimeoutError:
                if written is None:
                    raise
                result = None
            if written is not None and (result is None or (result.get("kind") == "conversation" and not result.get("reply"))):
                # The App asks only once more: an answer the first request wrote, and the check held back, is all there is.
                self._log("turn.check", started, None, round=2, findings=[], kept=True, timed_out=True)
                return self._spoken_instead(request_id, "turn.continue", turn, written, None, started)
            return result
        if not turn or not turn.get("awaiting"):
            raise RuntimeError("no open turn to continue")
        turn["app_continued"] = True  # the App ran a call of this turn: a request past its time here is asked once more
        conv = turn["conv"]
        if (unsure := turn.get("unsure")) and unsure["id"] == turn["awaiting"]:
            del turn["unsure"]
            held = self._unsure_held(request_id, turn, unsure, observation)
            if held is not None:
                return held
        answered = turn["awaiting"]
        # Every call of the turn so far with how it ended, at the end of the newest result: where the model writes its
        # answer, the facts it may tell are together (it told «no pude abrir Steam» after Steam opened, «lo guardé»
        # after the typing failed, 2026-10-15 falsehood bench).
        done = turn.setdefault("done", [])
        calling = str(turn.get("calling", "?"))
        received = observation
        # REM2 (REV13 A-1): the App kept waiting what the model's «yes», not theirs, reached it as «unclear»: the model
        # reads why (NOT_THEIR_YES); any other receipt (expired, nothing waits) as the App wrote it.
        theirs_not = turn.pop("not_their_yes", None) == answered and _status(observation) == "needs_confirmation"
        if theirs_not:
            observation = NOT_THEIR_YES
        if calling == "web.fetch":
            # Goal h-web: the model reads the lead and the paragraphs nearest to what was asked; the
            # answer check keeps the page as it came (received).
            observation = web_focus.focus(observation, self._web_queries(turn), json.loads(
                turn.get("calling_args") or "{}"))
        calling = CONFIRM["function"]["name"] if calling == CONFIRM_OPERATION else self.wires.name(calling)
        outcome = _outcome(observation, read=self.risk.get(calling) in READ_RISKS)
        if theirs_not:
            outcome = NOT_THEIR_YES_REFUSED
        if outcome.startswith(VERIFICATION["unchanged"]) and _aid_on("same_call_closes") and _same_done(
                turn, calling, turn.get("calling_args"), VERIFICATION["readback"]):
            outcome = SET_BY_SAME + outcome[len(VERIFICATION["unchanged"]):]
        # Aid «result_dedup» (w6-lat): what the facts line below says of this result is not said in it again.
        compact = _aid_on("result_dedup")
        body = _deduplicated(observation, outcome) if compact else observation
        # Aid «short_refs» (PLAN_GENERAL C1; uso real: news addresses of ~500 tokens copied wrong, 11 s each): a long
        # address in a result reaches the model as a short reference, and the mind puts the address back in its calls.
        shown, made = self._shorten(body, compact) if _aid_on("short_refs") else (body, {})
        capped = 0
        if _aid_on("result_cap"):
            fitted, left_out = self._fit_result(shown)
            if left_out:
                # Plan c3: the cut is told in the call's line, as any part read (RESULT_CUT_TOLD).
                capped, outcome, shown = len(shown), _cut_told(outcome, left_out, len(shown)), fitted
        # Aid «confirm_names_call» (auditoría de la mente, w8, P5): an answer to a confirmation says which call it
        # answered («confirm_pending (filesystem_known_trash_named) → …»), here and in the clock; once its turn is cut,
        # «confirm_pending → completado y verificado» no longer said what was done. Only when the App said which call
        # waited (with the person's words) or the press answered the call the turn before had just asked.
        told = (f"{calling} ({turn['confirming']})" if calling == CONFIRM["function"]["name"] and turn.get("confirming")
                and _aid_on("confirm_names_call") else calling)
        entry, same = f"{told} → {outcome}", turn.get("last_call")
        # Grouped only when the result is the same too: a click that worked and then failed are two facts (round 2).
        turn["last_call"] = (calling, turn.get("calling_args"), outcome)
        if done and same == turn["last_call"]:
            turn["repeats"] = turn.get("repeats", 1) + 1
            done[-1] = f"{told} ×{turn['repeats']} con los mismos argumentos → {outcome}"
        else:
            turn["repeats"] = 1
            done.append(entry)
        self._ran_add(told, outcome, turn["awaiting"])
        self._receipt(turn, calling, received, outcome)
        aids = _aids_seen(observation)
        named = json.loads(turn.get("calling_args") or "{}") if calling in {"app_open", "input_visible_controls"} else {}
        # Uso real: a look at another window (the browser's) came between the opening and the failures; the application
        # kept is the last one named that has places of its own.
        application = named.get("appId") or named.get("application") if isinstance(named, dict) else None
        if isinstance(application, str) and _fold(application) in APP_PLACES:
            turn["app_named"] = application
        note = ""
        if (calling == "app_open" and outcome.startswith(COMPLETED_OUTCOMES) and isinstance(application, str)
                and not named.get("place") and _aid_on("app_places_next")):
            self._opened_places = opened_places_note(application)
        if (calling in {"input_visible_click", "input_visible_controls"} and not outcome.startswith(COMPLETED_OUTCOMES)
                and turn.get("app_named") and not turn.get("places_told") and _aid_on("app_places_next")):
            note = places_note(turn["app_named"])
            if note:
                turn["places_told"] = True
                aids["app_places_next"] = note.strip()
        if (outcome.startswith(COMPLETED_OUTCOMES) and operation_of(str(turn.get("calling"))) in KNOWS_CALLS
                and _aid_on("app_knows")):
            knows = knows_note(observation, json.loads(turn.get("calling_args") or "{}"), self._today(), conv)
            if knows:
                note += knows
                aids["app_knows"] = knows.strip()
        if calling == "input_visible_click" and not turn.get("field_told") and _aid_on("field_focused_next"):
            field = field_note(observation, turn.get("calling_args"))
            if field:
                turn["field_told"] = True
                note += field
                aids["field_focused_next"] = field.strip()
        if calling == "file_write" and _aid_on("written_not_window"):
            # The receipts before this call's own (_receipt above put it last).
            written = written_note(observation, turn.get("receipts", [])[:-1])
            if written:
                note += written
                aids["written_not_window"] = written.strip()
        if (calling == self.wires.name("calculator.expression.evaluate") and outcome.startswith(COMPLETED_OUTCOMES)
                and _aid_on("unsourced_number")):
            # Encargo 35 (R18): the Windows Calculator's value, computed with a rate the model made up, was told as the
            # day's conversion; its expression's numbers nobody gave are said, as calculate's are.
            expression = str(json.loads(turn.get("calling_args") or "{}").get("expression") or "")
            unsourced = unsourced_note(expression, conv)
            if unsourced:
                note += unsourced
                aids["unsourced_number"] = unsourced.strip()
                turn.setdefault("unsourced", []).append(_unsourced_entry(expression, conv, _display_value(observation)))
        if (calling == self.wires.name("vision.describe") and outcome.startswith(COMPLETED_OUTCOMES)
                and _aid_on("vision_estimate")):
            note += VISION_ESTIMATE
            aids["vision_estimate"] = VISION_ESTIMATE.strip()
        if (calling == self.wires.name("browser.page.read") and outcome.startswith(COMPLETED_OUTCOMES)
                and _aid_on("read_after_navigation")):
            after_navigation = read_after_navigation_note(observation, turn.get("receipts", [])[:-1])
            if after_navigation:
                note += after_navigation
                aids["read_after_navigation"] = after_navigation.strip()
        if (outcome.startswith("falló") and _memory_off(observation) and "memory.enable" in self.wire_to_op.values()
                and calling != self.wires.name("memory.enable") and _aid_on("memory_off_next")):
            off = MEMORY_OFF_NOTE.format(enable=self.wires.name("memory.enable"))
            note += off
            aids["memory_off_next"] = off.strip()
            self._memory_was_off = True
        if calling == self.wires.name("memory.enable"):
            self._memory_was_off = False
        if outcome.startswith("falló") and _has_next(observation) and _aid_on("next_not_done"):
            note += NEXT_NOT_DONE
            aids["next_not_done"] = NEXT_NOT_DONE.strip()
        # Aid «same_call_next» (PLAN_GENERAL C2; uso real: the same click 5-7 times, a reload and a typing in turn): a
        # call made again in this turn with the same arguments and the same result (its content, _result_key),
        # whatever came between, is told as a fact with its options, once per turn (a loop of a look and a click repeats
        # both): a second time when it failed or stayed unsure, a third when it completed (SAME_CALL_FAILED_TOLD).
        seen = turn.setdefault("calls_seen", {})
        turn.pop("same_told_call", None)  # same_call_closes: only the model's next decision after the notice
        # Uso-108 (B4): vision and OCR of two captures of one image are the same call (the capture's id, in its arguments).
        called = _CAPTURE_ID.sub("capture_", str(turn.get("calling_args")))
        key = json.dumps([calling, called, _result_key(observation)], ensure_ascii=False)
        seen[key] = seen.get(key, 0) + 1
        told_at = SAME_CALL_TOLD if outcome.startswith(COMPLETED_OUTCOMES) else SAME_CALL_FAILED_TOLD
        if seen[key] == told_at and not turn.get("same_told") and _aid_on("same_call_next"):
            turn["same_told"] = True
            turn["same_told_call"] = [turn.get("calling"), _call_key(turn.get("calling_args"))]  # same_call_closes
            # Auditoría de la mente (w8): not the places again when app_places_next just told them in this result.
            options = SAME_CALL_CLOSED if final else SAME_CALL_OPTIONS + (
                same_call_places(turn.get("app_named"))
                if calling == "input_visible_click" and "app_places_next" not in aids else "")
            repeated = SAME_CALL_NOTE.format(call=calling, times=told_at, outcome=outcome, options=options)
            note += repeated
            aids["same_call_next"] = repeated.strip()
        # Aid «look_click_cap»: each click right after a look, by that look, what it saw and the click; a look waits for
        # the call after it.
        pairs = turn.setdefault("look_clicks", {})
        if calling == "input_visible_click" and turn.get("look"):
            pair = json.dumps([*turn["look"], _call_key(turn.get("calling_args"))], ensure_ascii=False)
            pairs[pair] = pairs.get(pair, 0) + 1
        turn["look"] = ([_call_key(turn.get("calling_args")), _result_key(observation)]
                        if calling == "input_visible_controls" else None)
        if made:
            aids["short_refs"] = sorted(made) if turn.get("private") else made
        if capped:
            aids["result_cap"] = capped  # the trace says which results the model read in part
        line = _said_once(done) if _aid_on("facts_once") else done
        conv.append({"role": "tool", "tool_call_id": turn["awaiting"],
                     "content": shown + "\n[En este turno: " + "; ".join(line) + "]" + note})
        turn["awaiting"] = None
        if aids:
            # What the aids told the model, a row of its own: the model's decision after it is the next row.
            self._log("turn.aid", time.perf_counter(), None, operation=turn.get("calling"),
                      aids=sorted(aids) if turn.get("private") else aids)
        if (answer := turn.pop("ring_answer", None)) is not None:
            # ALR4: what the receipt says of each ring, in a fixed sentence (ring_answer.told); any other receipt (one
            # still ringing, a failure, a confirmation) goes to the model as always.
            said = ring_answer.told(received, answer.action, answer.lang or self.lang)
            if said is not None:
                started = time.perf_counter()
                conv.append({"role": "assistant", "content": said})
                if self.foresee is not None:
                    try:
                        self.foresee(said, True)  # its voice is made while the App publishes it, as _next's words
                    except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                        pass
                return self._result(request_id, turn, None, None, "turn.continue", started, said)
        if (told := turn.pop("guide_call", None)) is not None and told[0] == "all":
            # RUT11 (REV11 B-4): one routine of every one done; the next, or all of them said in one sentence. A
            # receipt that is not completed goes to the model, with the ones done before it in the conversation.
            done = routine_guide.done_name(received, told[2])
            if done is not None and not final:
                turn["guide_done"].append(done)
                if turn["guide_rest"]:
                    return self._routine_call(request_id, turn, {"action": told[2], "name": turn["guide_rest"].pop(0)},
                                              told, time.perf_counter(), "turn.continue")
                said = routine_guide.told_all(told[2], told[1], turn["guide_done"])
                return self._guide_said(request_id, turn, said, "turn.continue", time.perf_counter())
            if done is None and not final and not turn["guide_done"] and not turn["guide_rest"]:
                # REM6 (REV15 B-2): the one routine asked about is gone (called by its id, nothing else was touched):
                # said by the name it was asked by, as the guide's other «not found».
                asked = turn.get("guide_named", {}).get(json.loads(turn.get("calling_args") or "{}").get("name"))
                said = routine_guide.told(received, told[2], told[1], asked, routines=self.routines) if asked else None
                if said is not None:
                    return self._guide_said(request_id, turn, said, "turn.continue", time.perf_counter())
        elif told is not None:
            # RUT7: the receipt of a fixed order's call or of the guide's create, in a fixed sentence from that receipt
            # (routine_guide.told); any other receipt (a failure it has no sentence for) goes to the model as always.
            said = routine_guide.told(received, *told, routines=self.routines)
            if said is not None:
                return self._guide_said(request_id, turn, said, "turn.continue", time.perf_counter())
        if (calling == self.wires.name("baxy.routines") and outcome.startswith(COMPLETED_OUTCOMES) and not final
                and json.loads(turn.get("calling_args") or "{}").get("action") == "run"):
            ran = self._routine_steps(request_id, turn, received)
            if ran is not None:
                return ran
        if final:
            # The App closes the turn (its step budget spent, the engine down, or a confirmation waiting for the
            # person): said where the model reads it, at the end of the last result, without a cause the mind does not
            # know.
            conv[-1]["content"] += NO_MORE_CALLS
        completed = outcome.startswith(COMPLETED_OUTCOMES)
        if turn["queue"] and not final and completed:
            turn.pop("same_told_call", None)  # chosen before the notice was read
            return self._result(request_id, turn, turn["queue"].pop(0), None, "turn.continue", time.perf_counter(), "")
        after = turn.pop("unsure_after", None)
        if (unsure := turn.pop("unsure", None)) and after == answered and not final and completed:
            # P2.40 with P2.43: the queued call held «unsure» goes to the App to be weighed once those before it ran;
            # one the mind refuses now (_repeat_refused, _unopened) enters the conversation and _result says why.
            turn.pop("same_told_call", None)  # chosen before the notice was read
            name = self.wire_to_op.get(unsure["wire"], unsure["wire"])
            if self._repeat_refused(turn, name, unsure) or self._unopened(turn, unsure):
                conv.append({"role": "assistant", "content": "", "tool_calls": [
                    {"id": unsure["id"], "type": "function", "function": {
                        "name": unsure["wire"], "arguments": json.dumps(unsure["arguments"], ensure_ascii=False)}}]})
            else:
                turn["unsure"] = unsure
                turn.setdefault("weighed", []).append((unsure["wire"], _call_key(unsure["arguments"])))
            return self._result(request_id, turn, unsure, None, "turn.continue", time.perf_counter(), "")
        says = turn.pop("routine_say", None)
        if says and completed and not final and not turn["queue"]:
            # RUT1: the last step of a routine completed, every one before it too (a failed one ends the queue above).
            return self._routine_said(request_id, turn, says, time.perf_counter())
        for call in turn["queue"]:
            conv.append({"role": "tool", "tool_call_id": call["id"], "content": NOT_RUN if final else _not_run_after(call)})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(call["wire"], call["wire"]), "tool": call["wire"],
                "arguments": call["arguments"], "observation": NOT_RUN, "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(call["wire"]) == "read_only"})
        turn["queue"] = []
        return self._next(request_id, "turn.continue", turn, final=final)

    def _unsure_held(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any],
                     observation: str) -> dict[str, Any] | None:
        """P2.43: the App's answer to a call sent «unsure». Held, it did not run: the doubt asks the person with no tools
        unless the App says the kernel would not run it unasked (HELD_UNSURE): then it reads again with its tools.
        None: an App that does not know «unsure» ran it, so the call enters the conversation and is read as any."""
        try:
            told = json.loads(observation)
        except json.JSONDecodeError:
            told = None
        conv, turn["awaiting"] = turn["conv"], None
        if not isinstance(told, dict) or told.get("status") != "held":
            conv.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": call["id"], "type": "function",
                 "function": {"name": call["wire"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}]})
            turn["awaiting"] = call["id"]
            return None
        asks = told.get("outcome") != HELD_UNSURE
        if not asks:
            turn["reread"] = True
        conv.append({"role": "user", "content": (DOUBT_NOTE if asks else REREAD_NOTE).format(call=call["wire"])})
        self._log("turn.continue", time.perf_counter(), None, text=None if turn.get("private") else turn["text"],
                  kind="doubt_ask" if asks else "doubt_reread", operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None, content=None)
        # Decided again as the person's turn it doubted, as REREAD_NOTE and DOUBT_NOTE are after a doubt held in the mind.
        return self._next(request_id, "turn.decide", turn, final=asks)

    def _fit_result(self, shown: str) -> tuple[str, int]:
        """Aid «result_cap» (P0.10): a result past RESULT_TOKENS keeps the start that fits, marked where it ends
        (CUT_RESULT), before it is sent rather than after a refusal (_make_room); with how many of its characters are
        left out (0: it goes whole), which its facts line tells (RESULT_CUT_TOLD). Counted as the history counts, only
        with the server's tokenizer (a token is at least a character, so a shorter text is never counted). The call has
        already been counted as done when this runs, so a tokenizer that fails does not fail the turn: the result keeps
        RESULT_TOKENS characters, which fit."""
        if not self.prefix_tokens or len(shown) <= RESULT_TOKENS:
            return shown, 0
        try:
            tokens = len(self.server.tokenize(shown))
            if tokens <= RESULT_TOKENS:
                return shown, 0
            keep = len(shown) * RESULT_TOKENS // tokens
            while True:
                cut = shown[:keep] + CUT_RESULT
                tokens = len(self.server.tokenize(cut))
                if tokens <= RESULT_TOKENS or keep == 0:
                    return cut, len(shown) - keep
                keep = max(0, keep - (keep * (tokens - RESULT_TOKENS) // tokens) - 1)
        except (OSError, http.client.HTTPException, RuntimeError, ValueError, KeyError) as error:
            self._log("turn.result_cap", time.perf_counter(), None, error=type(error).__name__)
            keep = RESULT_TOKENS - len(CUT_RESULT)
            return shown[:keep] + CUT_RESULT, len(shown) - keep

    def confirm(self, request_id: Any, approve: bool, label: str) -> dict[str, Any]:
        """The person pressed Sí or No on a pending confirmation: their answer (the button's label) and the
        confirm_pending call it stands for enter the conversation as they are, with no model call in between."""
        started = time.perf_counter()
        # The press answers the card of the call the turn before had just asked (its last result waits for the «sí»): its
        # own, or the one an unclear answer of that turn left waiting (its confirm_pending's result waits too).
        turn = self._turn or {}
        asked = turn.get("last_call")
        confirming = None
        if asked and asked[2] == WAITS_FOR_YES:
            confirming = turn.get("confirming") if asked[0] == CONFIRM["function"]["name"] else asked[0]
        self._close_open_calls()
        call_id = self._new_id("confirm")
        answer = {"answer": "yes" if approve else "no"}
        self.conversation.append({"role": "user", "content": label})
        self.conversation.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": CONFIRM["function"]["name"], "arguments": json.dumps(answer)}}]})
        self._turn = {"conv": self.conversation, "queue": [], "awaiting": call_id, "text": label,
                      "calling": CONFIRM_OPERATION, "confirming": confirming}
        self._log("turn.confirm", started, None, text=label, kind="action", operation=CONFIRM_OPERATION,
                  arguments=answer)
        return {"type": "turn.result", "id": request_id, "kind": "action", "operation": CONFIRM_OPERATION,
                "arguments": answer, "reply": "", "question": ""}

    def _make_room(self, conv: list[dict[str, Any]], final: bool = False) -> bool:
        """One step of room for an open turn past the context, whether there was one: the earlier turns' results leave
        out their bodies, else the oldest earlier turn goes, else the open turn's results but the newest leave out
        theirs, else those of the newest's loop also leave out their facts lines (the newest's lists every call of its
        loop), else, for the last answer only, the newest leaves out its body too. All in place: the person's open turn
        is this same conversation."""
        starts = [i for i, m in enumerate(conv)
                  if m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]
        if conv is self.conversation and len(starts) > 1:
            if not self._compact(conv[:starts[-1]]):
                self._drop(starts[1], 1)
            return True
        begin = starts[-1] if starts else 0
        results = [m for m in conv[begin:] if m["role"] == "tool" and TURN_FACTS in str(m.get("content") or "")]
        if self._compact(results[:-1]):
            return True
        # H6 (holdout v5 V5F028/V5F029): each left-out result kept its own facts line, and each lists every call of its
        # loop before it, so they grew with the square of the calls (14 of them, 5.1k tokens at a log's 15th page) and
        # the last answer did not fit: no answer at all. The newest's line says them all; a loop starts at the last
        # message of the person (or a note) before it.
        loop = max([i for i in range(begin, len(conv)) if conv[i]["role"] == "user"], default=begin)
        bare = False
        for message in conv[loop:]:
            content = str(message.get("content") or "")
            if (message["role"] == "tool" and message is not (results[-1] if results else None)
                    and content.startswith(COMPACTED) and TURN_FACTS in content):
                message["content"] = COMPACTED
                bare = True
        # The last answer always comes: its newest result leaves out its body too (its facts stay, said as omitted).
        return bare or (final and self._compact(results[-1:]))

    def _after_server_error(self, request_id: Any, stage: str, turn: dict[str, Any], code: int,
                            started: float) -> dict[str, Any]:
        """Uso real 2026-11-03 (F4): llama-server answered a decision with a 5xx even after its retry (LlmServer._open),
        and the turn ended with nothing said. The model is asked once for its answer in words only (SERVER_ERROR_NOTE;
        a call cannot be sampled then, so a reply whose call the server failed to read cannot come back); every word
        is its own. If that fails as well, the failure reaches the App (decision_unavailable), as before."""
        turn["server_failed"] = True
        self._log(stage, started, None, kind="server_error", code=code, operation=None, arguments=None, content=None)
        note = {"role": "user", "content": SERVER_ERROR_NOTE.format(code=code)}
        conv = turn["conv"]
        conv.append(note)
        try:
            return self._next(request_id, stage, turn, final=True)
        finally:
            # The note was for that one answer, as the check's (_check_answer).
            for index in range(len(conv) - 1, -1, -1):
                if conv[index] is note:
                    del conv[index]
                    break

    def _next(self, request_id: Any, stage: str, turn: dict[str, Any], final: bool = False) -> dict[str, Any]:
        started = time.perf_counter()
        self._turned = True
        conv = turn["conv"]
        # Pedido del dueño 2026-11-02 («arregla el problema del contexto»): inside a long turn room was made only after
        # llama-server refused the prompt (400) or cut the answer («Listo,»). The turn's last reply says how full the
        # context is; with one more result and the answer it would not fit, so room is made before this request. The
        # refusal and the cut answer below still catch what this estimate misses.
        used = turn.pop("used", 0)
        if (used and self.server.context and used + RESULT_TOKENS + DECISION_TOKENS > self.server.context
                and self._make_room(conv, final)):
            self._log(stage, started, None, kind="context_shrunk", operation=None, arguments=None, content=None)
        messages = [{"role": "system", "content": self._system(bool(turn.get("beat")))}, *self._history(self._seen(turn))]
        body = {"messages": messages, "tools": self.tools, "max_tokens": DECISION_TOKENS, "parallel_tool_calls": True,
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": self.decide_temperature, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                # A fixed seed: the same conversation gets the same decision, so two runs of a bench differ by the
                # change measured, not by sampling noise (±3 of 90 without it). Review 2026-10-22: BAXY_RENEW_SEED moves
                # it, to measure that noise (0 by default).
                "seed": self.seed}
        if self._stubs:
            # MUS1 (VIVO13, «Lee la página …» in Esencial: the offer took 84-87 s): a stub has no arguments, and the 4B
            # wrote «web_fetch {}» 37 times over, to DECISION_TOKENS (768 tokens, 78 s). The request stops where another
            # call to a stub would begin after a call (Qwen3.5's call format, its chat template): the first call and
            # everything before it are as they were; a call to a tool that does nothing, again, is never written.
            body["stop"] = [STUB_AGAIN.format(wire=wire) for wire in sorted(self._stubs)]
        if self._doubted(stage, turn, final):
            # The decision's own token probabilities, for its doubt (doubt.py, System One) and the trace: same call, no
            # other pass. Al máximo 9.5 (2026-10-22): only where the doubt is read; elsewhere (turn.continue, the last
            # answer, the heartbeat) the server sorted the vocabulary at every token for a doubt only the trace kept,
            # which those rows no longer carry (−20 to −100 ms per call, expected).
            body.update(logprobs=True, top_logprobs=10)
        if final:
            turn["closed"] = True  # R7-NB-1: a decision asked for again (continue_turn) keeps it
            # The last answer of an exhausted turn is words only. The tools stay, so the cached prefix (37k tokens)
            # is not evicted by a shorter prompt (llama.cpp PR #24176: a restore re-reads ~4k tokens; measured 2.3-3.6 s
            # on the next order). tool_choice none alone still let Qwen3.5 write a call as XML text that reached the
            # person (llama.cpp #20837; 2026-10-15 E017): the token that opens a call cannot be sampled.
            body["tool_choice"] = "none"
            body["logit_bias"] = [[token, False] for token in self.call_tokens]
        try:
            # Al máximo 9.4: a person's turn streams to the voice, which synthesizes an answer's first sentence while
            # the rest is written (only while it is words; a call dropped what it foresaw); nothing sounds before the
            # App publishes it. Not the decision whose doubt is read (_doubted): its token probabilities are not all
            # sent when streamed (LlmServer.chat). Never a heartbeat.
            streams = self.foresee is not None and not turn.get("beat") and not self._doubted(stage, turn, final)
            reply = self.server.chat(body, on_text=self.foresee) if streams else self.server.chat(body)
        except urllib.error.HTTPError as error:
            if 500 <= error.code < 600 and not turn.get("server_failed"):
                return self._after_server_error(request_id, stage, turn, error.code, started)
            # llama-server refuses a prompt past its context with HTTP 400. Al máximo 1.2 (2026-10-22): its earlier
            # results were cut and the model answered in words at once (15 context_shrunk in the trace, each one ended
            # its mission); now room is made a step at a time (_make_room, said where the model reads) and the turn goes
            # on as it was. With no room left to make, the refusal reaches the App.
            if error.code != 400 or not self._make_room(conv, final):
                raise
            self._log(stage, started, None, kind="context_shrunk", operation=None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=final)
        # Uso real 02-11 (and 13 finals since 31-10): a prompt that fits but leaves the answer no room is not refused;
        # the context fills while the answer is written and it ends at «length» before the max_tokens asked for
        # (53,245 + 3 tokens: the person got «Listo,»). Room is made as for the 400 and it is written again; what the
        # voice foresaw of the cut answer is dropped.
        usage = reply.get("usage") or {}
        if (reply["choices"][0].get("finish_reason") == "length"
                and 0 <= int(usage.get("completion_tokens", DECISION_TOKENS)) < DECISION_TOKENS
                and self._make_room(conv, final)):
            if streams:
                self.foresee(None, True)
            self._log(stage, started, None, kind="context_shrunk", operation=None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=final)
        # What this reply says the context holds now (the prompt it read and what it wrote): the next request of the
        # turn weighs it before it is sent (below, at the start of _next).
        turn["used"] = int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
        timings = reply.get("timings") or {}
        if 0 < int(timings.get("prompt_n") or 0) <= NOTICE_SHORT_READ and int(timings.get("predicted_n") or 0) > 0:
            cost = (float(timings.get("prompt_ms") or 0.0) + NOTICE_WRITTEN * float(timings.get("predicted_ms") or 0.0)
                    / int(timings["predicted_n"])) / 1000
            self._notice_budget = min(NOTICE_MOST_S, max(NOTICE_SECONDS, cost * NOTICE_MARGIN))
        elif not timings and isinstance(took := getattr(self.server, "took_s", None), (int, float)):
            # A server that says no llama-server timings (the translator: a company's API or Ollama, src/baxy_mind/external_model.py)
            # still answers a notice in about what a decision takes there: the same conversation, its cache, a few words. Without
            # this its notices had 1.5 s and none arrived, and with any other model BAXY said nothing during a mission (pedido del
            # dueño 2026-11-08). What it took is the server's own reading (LlmServer.took_s).
            self._notice_budget = min(NOTICE_MOST_S, max(NOTICE_SECONDS, took * NOTICE_MARGIN))
        message = reply["choices"][0]["message"]
        content = (message.get("content") or "").strip()
        calls = []
        for index, call in enumerate(message.get("tool_calls") or []):
            wire = call["function"]["name"]
            raw = call["function"].get("arguments") or "{}"
            try:
                arguments = json.loads(raw)
            except json.JSONDecodeError:
                arguments = None
            if not isinstance(arguments, dict):
                # Not an object: it travels as written, so the rejection says what the model gave.
                arguments = {"unparsedArguments": raw}
            calls.append({"id": call.get("id") or self._new_id("call"), "wire": wire, "arguments": arguments})
        if calls and not final and (offered := self._offered(turn, calls)):
            # G10 (aid «offer_unanswered»): nothing of this reply runs; the model decides again, told why (OFFER_NOTE).
            wire, values = offered
            conv.append({"role": "user", "content": OFFER_NOTE.format(
                call=wire, values=", ".join(f"«{value}»" for value in values))})
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                      kind="offer_unanswered", operation=self.wire_to_op.get(wire, wire), arguments=None,
                      content=None)
            return self._next(request_id, stage, turn)
        held, note = (calls[0],self._held(stage, turn, final, calls[0], reply, body)) if calls else (None, None)
        # P2.40 (C16 M11): the calls queued behind the first run without the model deciding again, so one the kernel
        # would run unasked goes by the same rule, with its own doubt ([app_open, system_power] never asked); in Bypass,
        # so does one the App weighs with its arguments (P2.43: a click on «Enviar» or on «Siguiente»), not one that only
        # reads, is undone, or the kernel confirms in Bypass too.
        for nth, call in enumerate(calls[1:], 1):
            if note is None and (self._unasked(call["wire"]) or _bypass() and self.risk.get(call["wire"]) not in (
                    "read_only", "low_reversible") and "bypass" not in (self.confirms.get(call["wire"]) or ())):
                held, note = call, self._held(stage, turn, final, call, reply, body, nth)
        if isinstance(note, dict):
            # Layer 2 «corrige»: the decision model's tool, with the arguments the model itself wrote for it, replaces
            # the action the model doubted (and anything queued behind it, chosen on the same misreading). Review
            # 2026-10-22 (and B-MED-8): the words it wrote for the doubted call go with it, and the row says whose doubt
            # it carries (doubt_of) beside the operation that runs.
            turn["doubt_of"] = self.wire_to_op.get(held["wire"], held["wire"])
            at = calls.index(held)  # the calls before a queued one held were not doubted: they stay, with their words
            calls, note, content = [*calls[:at], note], None, content if at else ""
        if note is UNSURE:
            # P2.43: the doubted call goes to the App to be weighed with its arguments, not run; it enters the
            # conversation only if an App that does not know «unsure» ran it (continue_turn). One the mind itself
            # refuses (_repeat_refused, _unopened) takes the usual way, which tells the model why. P2.40: held queued
            # behind others, those were not doubted: they run first, with their words, and it is weighed after them.
            name, at = self.wire_to_op.get(held["wire"], held["wire"]), calls.index(held)
            if at or not self._repeat_refused(turn, name, held) and not self._unopened(turn, held):
                turn["unsure"] = held
                if not at:
                    turn.setdefault("weighed", []).append((held["wire"], _call_key(held["arguments"])))
                    return self._result(request_id, turn, held, reply, stage, started, "")
                # Queued, it is weighed (or refused, continue_turn) only once those before it ran.
                calls, turn["unsure_after"] = calls[:at], calls[at - 1]["id"]
            note = None
        if note:
            # System One: the model was not sure of this action (layer 0), or was unsure and the decision model chose
            # otherwise (layer 2). Nothing runs; it is told so where it reads (the call it nearly made never enters the
            # conversation). After layer 0 or 2 it decides again with its tools, once (REREAD_NOTE, DOUBT_OTHER_NOTE); a
            # note that ends in ASK_ONLY (an unsure «sí», a call the kernel would run unasked) only asks the person, in
            # its own words, what they want.
            conv.append({"role": "user", "content": note})
            reread = not note.endswith(ASK_ONLY)
            doubted = self.wire_to_op.get(held["wire"], held["wire"])
            if doubted.startswith("memory."):
                turn["private"] = True  # review 2026-10-22: the words meant for memory, as after a memory call
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                      kind="doubt_reread" if reread else "doubt_ask", operation=doubted, arguments=None, content=None,
                      call_index=calls.index(held))
            return self._next(request_id, stage, turn, final=not reread)
        if calls:
            conv.append({"role": "assistant", "content": content, "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["wire"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                for c in calls]})
            turn["queue"] = calls[1:]
            return self._result(request_id, turn, calls[0], reply, stage, started, content)
        if not final and ("<tool_call>" in content or "<function=" in content):
            # Review 2026-10-22: a call llama-server could not parse stays as text in content, and it reached the person
            # as BAXY's words. It is a failed call: the model answers in words, where a call cannot be written.
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"], kind="malformed_call",
                      operation=None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=True)
        if not content and not final and stage == "turn.continue" and not turn.get("beat"):
            # After a call the model wrote nothing and called nothing: an empty reply is a failed turn that never tells
            # what ran (round 2, as an empty ask_user), so it answers in words from the results.
            return self._next(request_id, stage, turn, final=True)
        if (content and stage == "turn.decide" and not final and not turn.get("beat") and not turn.get("answering")
                and not turn.get("dated") and not turn.get("receipts") and _aid_on("dated_search")
                and self._dated(turn["text"])):
            turn["dated"] = True
            self._log("turn.dated", started, None)
            return self._look_up_first(request_id, stage, turn, body, reply, started)
        if (content and stage == "turn.decide" and not final and not turn.get("beat") and not turn.get("answering")
                and not turn.get("named") and not turn.get("receipts") and not turn.get("private")
                and _aid_on("named_fact") and self.system_one is not None and self.system_one.ready
                and self._unkept(self._names_said(turn["text"], content) & {_asked_about(turn["text"])})):
            looked = self._named_fact(request_id, stage, turn, body, reply, started)
            if looked is not None:
                return looked
        if (content and not turn.get("beat") and not turn.get("said_again")
                and not any(r.get("completed") for r in turn.get("receipts") or [])
                and _aid_on("say_once") and self._said_last(conv, content, turn.get("unheard") or ())):
            return self._say_otherwise(request_id, stage, turn, content, reply, started)
        if (content and turn.get("ringing") and not turn.get("ring_told") and not turn.get("beat")
                and not turn.get("closed")
                and not any(_answered_ring(r) for r in turn.get("receipts") or [])):
            turn["ring_told"] = True
            conv.append({"role": "user", "content": RINGING_STILL_NOTE.format(rings=turn["ringing"])})
            self._log("turn.ringing", started, None)
            return self._next(request_id, stage, turn)
        if content and not turn.get("beat") and _aid_on("answer_check"):
            checked = self._check_answer(request_id, stage, turn, content, reply, started)
            if checked is not None:
                return checked
        if content:
            conv.append({"role": "assistant", "content": content})
            if not streams and self.foresee is not None and not turn.get("beat"):
                # Al máximo V2 (2026-10-22): words that came whole, not streamed (the decision whose doubt is read),
                # never reached the voice's look-ahead (first sound p50 966 ms, p90 2,388): their first sentence is
                # synthesized now, while the App publishes them; it still sounds only when the App asks (voice.speak).
                try:
                    self.foresee(content, True)
                except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                    pass
        return self._result(request_id, turn, None, reply, stage, started, content)

    @staticmethod
    def _dated(text: str) -> bool:
        """Whether the person asks for a fact memory confuses: about something of a given year (a question whose only
        number is a year), or a curiosity."""
        folded = _fold(text)
        return ((bool(_YEAR_ALONE.match(text)) and ("?" in text or bool(_ASKS.match(folded))))
                or bool(_CURIOUS.search(folded)))

    @classmethod
    def _names_said(cls, text: str, content: str) -> set[str]:
        """The person's words, folded, that the answer says in a sentence that is not a question (a question tells no
        fact) and either of them wrote as a name: with a capital past the start of a sentence (aid «named_fact»). PC-L
        review 2026-10-27: the voice may come in lowercase, and the model still writes a name with its capital."""
        told = " ".join(sentence for sentence in _TOLD.findall(content) if not sentence.rstrip().endswith("?"))
        said, said_names = cls._words_and_names(text)
        words, names = cls._words_and_names(told)
        return (said_names | names) & said & words

    def _unkept(self, names: set[str]) -> bool:
        """Whether there are names and none is in what a memory call returned in this conversation (privacy review
        2026-10-27: a contact recalled in an earlier turn is the person's, never a web query)."""
        kept = {c["id"] for m in self.conversation for c in m.get("tool_calls") or []
                if self.wire_to_op.get(c["function"]["name"], "").startswith("memory.")}
        return bool(names) and not any(
            names & self._words_and_names(str(m.get("content") or ""))[0]
            for m in self.conversation if m.get("role") == "tool" and m.get("tool_call_id") in kept)

    @staticmethod
    def _words_and_names(text: str) -> tuple[set[str], set[str]]:
        """The words of a text, folded, and those written as a name: with a capital past the start of a sentence."""
        words: set[str] = set()
        names: set[str] = set()
        for sentence in _SENTENCES.split(text):
            found = _WORDS.findall(sentence)
            words.update(_fold(word) for word in found)
            names.update(_fold(word) for word in found[1:] if word[0].isupper())
        return words, names

    def _named_fact(self, request_id: Any, stage: str, turn: dict[str, Any], body: dict[str, Any],
                    reply: dict | None, started: float) -> dict[str, Any] | None:
        """Aid «named_fact»: System One judges between the words and web_search; its web_search is looked up as a
        dated question is, and None leaves the words as they are."""
        turn["named"] = True
        if not any(t["function"]["name"] == "web_search" for t in self.tools):
            return None
        # PC-L review 2026-10-27 (privacy): who or what the person keeps in memory (a contact) is an option of its own,
        # never looked up on the web.
        options = {t["function"]["name"]: short(t["function"]["description"]) for t in self.tools
                   if t["function"]["name"] in ("web_search", "memory_recall")}
        options[ANSWER] = OPTION_TEXT[ANSWER]
        judged = self.system_one.choose(turn["text"], self._said(), options)  # type: ignore[union-attr]
        self._judged = {"options": list(options), **judged} if judged else {"options": list(options), "choice": None}
        self._log("turn.named", started, None)
        if not judged or judged["choice"] != "web_search":
            return None
        return self._look_up_first(request_id, stage, turn, body, reply, started)

    def _look_up_first(self, request_id: Any, stage: str, turn: dict[str, Any], body: dict[str, Any],
                       reply: dict | None, started: float) -> dict[str, Any]:
        """Aid «dated_search» (DATED_NOTE): the words answered from memory are not said. The model writes the
        web_search itself (LlmServer.fill_call, as System One's «corrige»); a fill that fails or writes no query decides
        once more with the note, which does not stay in the conversation (the soak of 2026-10-27: after the note alone
        «¿Quieres que busque…?» 3 of 8)."""
        conv = turn["conv"]
        try:
            filled = self.server.fill_call(body, "web_search")
        except Exception:  # noqa: BLE001 - a fill that failed falls back to the note
            filled = None
        if (filled and filled.get("name") == "web_search" and isinstance(filled.get("arguments"), dict)
                and str(filled["arguments"].get("query") or "").strip()):
            call = {"id": self._new_id("call"), "wire": "web_search", "arguments": filled["arguments"]}
            conv.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": call["id"], "type": "function",
                 "function": {"name": "web_search", "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}]})
            turn["queue"] = []
            return self._result(request_id, turn, call, reply, stage, started, "")
        note = {"role": "user", "content": DATED_NOTE}
        conv.append(note)
        try:
            return self._next(request_id, stage, turn)
        finally:
            for index in range(len(conv) - 1, -1, -1):
                if conv[index] is note:
                    del conv[index]
                    break

    @staticmethod
    def _said_last(conv: list[dict[str, Any]], content: str, unheard: Sequence[dict[str, Any]] = ()) -> bool:
        """Whether these words are BAXY's last words in the conversation again, letter for letter (folded). REM3 (REV13
        E-1): of the words the person heard: a message of ``unheard`` (GUA2's draft before a note) was never said."""
        last = next((str(m.get("content") or "") for m in reversed(conv)
                     if m.get("role") == "assistant" and str(m.get("content") or "").strip()
                     and not any(m is draft for draft in unheard)), "")
        return bool(last) and re.findall(r"[^\W_]+", _fold(last)) == re.findall(r"[^\W_]+", _fold(content))

    def _say_otherwise(self, request_id: Any, stage: str, turn: dict[str, Any], content: str, reply: dict | None,
                       started: float) -> dict[str, Any]:
        """Aid «say_once» (SAID_AGAIN_NOTE): an answer that is BAXY's last answer again is asked
        once more, words only; the second one is spoken, whatever it says."""
        turn["said_again"] = True
        self._log("turn.repeat", started, None, content=None if turn.get("private") else content)
        if self.foresee is not None:
            try:
                self.foresee(None, True)  # the first sentence the voice synthesized ahead is not the one spoken
            except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                pass
        conv = turn["conv"]
        note = {"role": "user", "content": SAID_AGAIN_NOTE}
        conv.append(note)
        try:
            result = self._next(request_id, stage, turn, final=True)
        finally:
            for index in range(len(conv) - 1, -1, -1):
                if conv[index] is note:
                    del conv[index]
                    break
        if result.get("kind") == "conversation" and not result.get("reply"):
            conv.append({"role": "assistant", "content": content})
            result["reply"] = content
        return result

    @staticmethod
    def _last_words(conv: list[dict[str, Any]]) -> str:
        """BAXY's last words before the person's last message of ``conv`` (what it may have offered them); the mind's own
        notes, written as the user's role, are not the person's."""
        users = [index for index, message in enumerate(conv) if message.get("role") == "user"
                 and not str(message.get("content") or "").startswith("[Nota interna")]
        return next((str(message["content"]) for message in reversed(conv[:users[-1]] if users else [])
                     if message.get("role") == "assistant" and isinstance(message.get("content"), str)
                     and message["content"].strip()), "")

    def _check_answer(self, request_id: Any, stage: str, turn: dict[str, Any], content: str, reply: dict | None,
                      started: float) -> dict[str, Any] | None:
        """Aid «answer_check» (al máximo, lever 3): the final answer read against the turn's results before it is
        spoken (answer_check.check). Contradicted, the model is asked once more, words only, with a note that says the
        facts that contradict it; its second answer is the one spoken, whatever it says, and the trace keeps both
        checks (turn.check). None: the answer stands as it is."""
        # Aid «check_found» (holdout v6 V6E055): the rule «found» of the check («no encontré X» while a result of the turn
        # found X), an aid of its own; aid «check_read» (holdout v6, falsedades): the rule «read» («no leí X» while a read
        # of the turn brought X whole), another.
        # Aid «check_denial»: the rule «denial» reads the catalog and the conversation's earlier calls.
        # Revisión w11-rev4: with earlier turns trimmed out of the conversation, its earlier calls are not known whole and
        # a try that failed there may be what the answer tells: the rule reads nothing.
        denials = (_aid_on(CHECK_RULE_AIDS["denial"]) and not turn.get("receipts") and not turn.get("checked")
                   and not self.trimmed_turns)
        try:
            catalog = {self.wire_to_op[t["function"]["name"]]: str(t["function"].get("description") or "")
                       for t in self.tools if t["function"]["name"] in self.wire_to_op} if denials else None
            findings = [f for f in check_answer(content, str(turn.get("text") or ""), turn.get("receipts") or [],
                                                self._calls, catalog=catalog, wire_of=self.wires.name,
                                                tries=self._tries(turn["conv"]) if denials else None,
                                                earlier=self._states if _aid_on(CHECK_RULE_AIDS["stale_state"])
                                                else None, today=self._today(),
                                                unsourced=turn.get("unsourced"),
                                                memory=(self.wires.name("memory.recall")
                                                        if "memory.recall" in self.wire_to_op.values() else "")
                                                if _first_words(turn["conv"]) else None,
                                                memory_off=getattr(self, "_switch_off", False) or self._memory_was_off)
                        if f["rule"] not in CHECK_RULE_AIDS or _aid_on(CHECK_RULE_AIDS[f["rule"]])]
        except Exception as error:  # noqa: BLE001 - a check that fails finds nothing: the answer stands
            # Revisión de calidad: a heuristic that breaks on some answer never takes the turn with it; the trace says
            # it failed (its type only) and the answer is spoken as it is.
            self._log("turn.check", started, None, round=2 if turn.get("checked") else 1, findings=[], kept=False,
                      error=type(error).__name__)
            return None
        if turn.get("checked"):
            # A2: a number nobody gave is said once. Its note leaves a fixed factor to the model («responde igual»), so
            # the answer after it is the model's decision: told again, the controls (42 millas, 150 libras) got the note
            # a second and a third time and searched for a «tasa» of a unit (2 of 20 on the decision bench).
            # Encargo A10: a page that never opened is said once too; the answer after that note is the model's decision.
            findings = [f for f in findings if f["rule"] not in ("unsourced_number", "unopened_page", "denial_lookup",
                                                                    "empty_lookup")]
        private = bool(turn.get("private"))
        shown = [{"rule": f["rule"], "fact": f["fact"]} if private else f for f in findings]
        if turn.get("checked"):
            # The second answer: the trace says whether it still contradicts. Uso real 2026-10-26: it still said
            # «Spotify se cerró» against the results, and was spoken. Still contradicted, the model is told the facts
            # once more (round 3); that answer is spoken as it is, never asked again (no loop). Cutting the sentence the
            # check quotes was left out: the quote is not always the false one («Busqué su ventana.» of «Busqué su
            # ventana. Listo, cerré Paint.»), and what was left would have been the falsehood.
            third = bool(turn.get("checked_again"))
            # uso-90 (diag-9dea c3-g10, diag-6f20 c4-g10): an answer written after the note that carries BAXY's own
            # words (a tool's name, a result's code: rule «internal») took them from the note, and the voice said
            # «media_play_youtube → sin confirmar (page_requires_sign_in)». It is never spoken: the last answer of the
            # turn that carried none is, the model's own words (nothing is cut out of an answer or written for it).
            clean = turn.get("check_clean")
            if clean and any(f["rule"] == "internal" for f in findings):
                self._log("turn.check", started, None, round=3 if third else 2, findings=shown, kept=False, echo=True)
                return self._spoken_instead(request_id, stage, turn, clean, reply, started)
            self._log("turn.check", started, None, round=3 if third else 2, findings=shown, kept=bool(findings))
            if not any(f["rule"] == "internal" for f in findings):
                turn["check_clean"] = content
            if not findings or third:
                return None
            turn["checked_again"] = True
        elif not findings:
            return None
        else:
            turn["checked"] = True
            turn["check_clean"] = None if any(f["rule"] == "internal" for f in findings) else content
            self._log("turn.check", started, None, round=1, findings=shown, content=None if private else content)
        if self.foresee is not None:
            try:
                self.foresee(None, True)  # the first sentence the voice synthesized ahead is not the one spoken
            except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                pass
        # A denial with no call behind it keeps the tools: the model may do what it had said it could not; a state
        # nothing read keeps them so it may look, and a number nobody gave keeps them so it may look it up (A2). Not in a
        # turn closed to calls (the App's final: a call waiting for the person's «sí», the steps or the time spent, the
        # engine down; or the mind's own): a call after it does not run (NativeTurnLoop, loop.call_after_final), and
        # uso-87 (diag-bc8c F13) the turn ended with no words. There the model writes again in words from what the
        # results show.
        opens = not turn.get("closed")
        denied = opens and any(f["rule"] == "denial" for f in findings)
        # ACT1: «estoy al día» with nothing that looked for a newer version is a state nothing read: the model may look.
        stale = opens and not denied and any(f["rule"] in ("stale_state", "unchecked_update") for f in findings)
        rate = opens and not denied and not stale and any(f["rule"] == "unsourced_number" for f in findings)
        unopened = opens and not denied and not stale and not rate and any(f["rule"] == "unopened_page" for f in findings)
        # MEM1: with the memory among the tools, the model keeps them so it may read it. Before the lookup's note, whose
        # «what is theirs, answer the same» left «No tengo guardada esa información» unread (MEM1 dev, D06).
        asked = not turn.get("receipts") and any(
            f["rule"] == "no_call" and asked_for(f["said"], str(turn.get("text") or ""), self._last_words(turn["conv"]))
            for f in findings)
        recall = (opens and not denied and not stale and not rate and not unopened and not asked
                  and any(f["rule"] == "unread_memory" for f in findings) and "memory.recall" in self.wire_to_op.values())
        lookup = opens and not denied and not stale and not rate and not unopened and not recall and any(
            f["rule"] in ("denial_lookup", "empty_lookup") for f in findings)
        dated = (opens and not denied and not stale and not rate and not unopened and not lookup and not recall
                 and all(f["rule"] in ("weekday_date", "unread_date") for f in findings)
                 and "system.time" in self.wire_to_op.values())
        # GUA1: an act told done in a turn that called nothing keeps the tools (UNDONE_NOTE). GUA3 (REV11 C-1): only when
        # the person's turn asked for that act («Recuerda que…» of «Acabo de guardar»), by its words or by answering BAXY's
        # question that offered it; otherwise («Acabo de cerrar Chrome.» to «¿Chrome gasta mucha RAM?») the note was an
        # invitation to act with no request, and the answer is asked again in words only (CHECK_NOTE), as before.
        undone = (opens and not (denied or stale or rate or unopened or recall or lookup or dated) and not turn.get("receipts")
                  and all(f["rule"] in ("no_call", "unread_memory") for f in findings) and asked
                  and all(asked_for(f["said"], str(turn.get("text") or ""), self._last_words(turn["conv"]))
                          for f in findings if f["rule"] == "no_call"))
        note = {"role": "user", "content": (DENIAL_NOTE if denied else STATE_NOTE if stale else RATE_NOTE if rate
                                            else OPEN_PAGE_NOTE if unopened else MEMORY_READ_NOTE if recall
                                            else LOOKUP_NOTE if lookup else DATE_NOTE if dated
                                            else UNDONE_NOTE if undone
                                            else CHECK_NOTE).format(
            facts=" ".join(CHECK_FACT.format(said=f["said"], fact=f["fact"]) for f in findings[:CHECK_FACTS]),
            how=(f'{self.wires.name("web.search")} busca su dirección real' if any(f.get("unsearched") for f in findings)
                 else f'{self.wires.name("browser.navigate")} con la dirección que traen los resultados'),
            search=self.wires.name("web.search"), request=str(turn.get("text") or ""),
            time=self.wires.name("system.time"), recall=self.wires.name("memory.recall"))}
        conv = turn["conv"]
        # GUA2 (banco GUA1, semilla 1: «Ahora lo tengo guardado en mi memoria.» three times with UNDONE_NOTE): without
        # the answer the note reads, the request was the turn's first one plus the note, and the same seed wrote the same
        # words again. With it before the note, as the model's own (Self-Refine, arXiv 2303.17651; CRITIC, arXiv
        # 2305.11738), the call came: P(call) at that request 0.40 → 0.68 over 9 real answers (tmp\GUA2, sonda_rev).
        draft = {"role": "assistant", "content": content} if undone else None
        if draft is not None:
            conv.append(draft)
            # REM3 (REV13 E-1): the person never heard it; say_once (_said_last) does not take it for BAXY's last words.
            turn.setdefault("unheard", []).append(draft)
        conv.append(note)
        try:
            result = self._next(request_id, stage, turn,
                                final=not (denied or stale or rate or unopened or lookup or dated or recall or undone))
        except TimeoutError:
            # Cosecha 05-11 (uso real con el modelo local): a turn of two minutes wrote its answer twice, the check asked for
            # it again both times, and the conversation's shrink (17 s to read it again) took each request past its 24 s.
            # The App asks only once more, and the person heard nothing until they asked. The first time the App still asks;
            # in the last request (or a turn the App has not continued, which it does not ask again: NativeTurnLoop) the
            # answer in hand is spoken, as the third answer or an empty one are. Only with findings of a reading's reach: a
            # falsehood weighs more than the silence, so an answer found telling an act, a name or a number the results do
            # not show fails as it did. An answer that came later in this request is the one held back. Held-out ciego: a
            # note that ran out of time was never read, so the answer asked for again has been told nothing yet (a rate
            # nobody gave, «said once», went out unread).
            turn.pop("checked_again" if turn.get("checked_again") else "checked", None)
            if not all(f["rule"] in SPOKEN_OUT_OF_TIME for f in findings):
                raise
            if turn.get("app_continued") and not turn.get("asked_again"):
                turn.setdefault("held_back", content)
                raise
            self._log("turn.check", started, None, round=3 if turn.get("checked_again") else 2, findings=shown, kept=True,
                      timed_out=True)
            return self._spoken_instead(request_id, stage, turn, content, reply, started)
        finally:
            # The note was for that one answer: the conversation keeps what was said, not the check (nor the answer it read).
            for gone in (note, draft):
                for index in range(len(conv) - 1, -1, -1):
                    if conv[index] is gone:
                        del conv[index]
                        break
        if result.get("kind") == "conversation" and not result.get("reply"):
            # Nothing written the second time: the first answer is spoken (the trace has it as contradicted).
            conv.append({"role": "assistant", "content": content})
            result["reply"] = content
        elif (denied or stale or rate or unopened or lookup or recall) and result.get("kind") != "conversation":
            turn.pop("checked", None)  # it acted: its answer after the results is checked as any other
        return result

    def _spoken_instead(self, request_id: Any, stage: str, turn: dict[str, Any], content: str, reply: dict | None,
                        started: float) -> dict[str, Any]:
        """An earlier answer of this turn, the model's own words, spoken in place of the one just written (uso-90): the
        voice drops what it foresaw of the latter and synthesizes this one ahead, as words that came whole."""
        if self.foresee is not None:
            try:
                self.foresee(None, True)
                self.foresee(content, True)
            except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                pass
        turn["conv"].append({"role": "assistant", "content": content})
        return self._result(request_id, turn, None, reply, stage, started, content)

    def _tries(self, conv: list[dict[str, Any]]) -> list[tuple[str, str]]:
        """The conversation's calls before this answer as (operation, status of their result): «completed», «failed»,
        «rejected», «needs_confirmation», «cancelled»…, or «unknown» when the result is not there or not a status (a
        body left out, a call never answered). For the rule «denial» of the check."""
        results: dict[Any, str] = {}
        for message in conv:
            if message.get("role") == "tool":
                try:  # the result as the App gave it, before the facts line the mind writes after it
                    facts = json.JSONDecoder().raw_decode(str(message.get("content") or ""))[0]
                except json.JSONDecodeError:
                    facts = None
                status = facts.get("status") if isinstance(facts, dict) else None
                # Revisión de final2: a call the owner switched off in Settings (FieldSettings.Refusal, «*_by_owner») is
                # «rejected» as one refused for its arguments is, but nothing it was asked could have run: a real limit
                # the answer may tell, never a try that left the act to do.
                if status == "rejected" and str(facts.get("error") or "").endswith("_by_owner"):
                    status = "refused_by_owner"
                results[message.get("tool_call_id")] = str(status) if status else "unknown"
        tries = []
        for message in conv:
            for call in message.get("tool_calls") or [] if message.get("role") == "assistant" else []:
                wire = str((call.get("function") or {}).get("name") or "")
                tries.append((self.wire_to_op.get(wire, wire), results.get(call.get("id"), "unknown")))
        return tries

    @staticmethod
    def _doubted(stage: str, turn: dict[str, Any], final: bool) -> bool:
        """Whether this call's decision is read for its doubt: a person's turn deciding, not its last answer, a
        continuation or a heartbeat."""
        return stage == "turn.decide" and not final and not turn.get("beat")

    def _held(self, stage: str, turn: dict[str, Any], final: bool, call: dict[str, Any], reply: dict | None,
              body: dict[str, Any], nth: int = 0) -> str | dict[str, Any] | object | None:
        """The note that holds the turn's first action (or the reply's `nth` call, queued behind it), the call that
        replaces it, UNSURE (in Bypass, the App weighs the doubted call with its arguments before it reads again), or
        None. Layer 0 (BAXY_S1_DOUBT): the
        model's confidence is under the threshold, unless these words answer a question (DOUBT_ASKED) or the call is
        low_reversible, or recoverable_delete and the kernel confirms it. Layer 2
        (BAXY_S1_VETO, with a decision model): under that one, the decision model is asked which of the model's own
        candidates the person meant, and a different answer holds it — or, with BAXY_S1_CORRECT=1 and a tool of
        CORRECTABLE_RISKS, the model fills that tool and it runs instead; a low_reversible call it does not correct
        runs; the answer to layer 2's own question is never turned into another one, nor is the model's reading again
        after either layer (turn["reread"]), save a call the kernel would run unasked (_unasked): that one, at either
        layer, only asks; and, in Bypass, one under either layer's threshold that is another invocation than those
        weighed (P2.43b): UNSURE, or past UNSURE_WEIGHS a question. Asking is never held: it already puts the person in
        the loop; nor is confirming (SIS3: their words are read by _their_answer)."""
        if not self._doubted(stage, turn, final) or call["wire"] in (ASK_USER["function"]["name"],
                                                                     CALCULATE["function"]["name"]):
            return None
        # Aid «dated_search» (soak of the fair, 2026-10-27): the web_search the model chose for a dated question or a
        # curiosity asked for, under the threshold, became «¿Quieres que busque…?» 6 times: it is the call that aid asks
        # for, so its doubt does not hold it; the same for the one «named_fact» asks for (code review 2026-10-27), also
        # when the model chose it itself for what or who a named thing is (live on the notebook after the deploy).
        if call["wire"] == "web_search" and ((_aid_on("dated_search") and self._dated(turn["text"]))
                                             or (_aid_on("named_fact") and (turn.get("named")
                                                                            or _asked_about(turn["text"])))):
            return None
        doubt = read_doubt(reply, nth)
        if doubt is None:
            return None
        if call["wire"] == CONFIRM["function"]["name"]:
            # SIS3: whether the person's words are their «sí» is read by its own question (_their_answer), never by the
            # confidence of this call; a yes it did not read is refused in _result (NOT_THEIR_YES).
            return None
        # Al máximo, System One 2: layer 0 never holds a low_reversible call; its error is undone and the kernel verifies
        # it. On 26 runs of decision2 with System One (2026-10-22) it held 23, 22 of them right without System One (P040
        # ×7, P085 ×15) and none useful; read_only it holds still (24 useful against 5 harmful), and anything riskier.
        # Nor a recoverable_delete the kernel confirms (V9E037): its «sí» names the exact action, and holding it asked in
        # words first and then the kernel asked again. work_loss it still holds (V6D131), and Bypass runs it unasked.
        # P2.34, C16: read again with its tools it could make the same call, and the kernel would run it unasked
        # (_unasked): its doubt asks the person, with no tools, at either layer, also in the reading after another doubt.
        risk = self.risk.get(call["wire"])
        unasked = self._unasked(call["wire"])
        # P2.43b: in Bypass, a reading again (not the person's answer) of another invocation than those weighed is weighed
        # too; past UNSURE_WEIGHS its doubt asks, with no tools, so it neither loops nor runs unweighed.
        weighs = turn.get("weighed") or []
        fresh = turn.get("reread") and _bypass() and not turn.get("answering") \
            and (call["wire"], _call_key(call["arguments"])) not in weighs
        unweighed = UNSURE if len(weighs) < UNSURE_WEIGHS else DOUBT_NOTE.format(call=call["wire"])
        if doubt["confidence"] < _threshold("BAXY_S1_DOUBT") and not turn.get("answering") \
                and (unasked or not turn.get("reread") or fresh) and risk != "low_reversible" \
                and not (risk == "recoverable_delete" and self._kernel_confirms(call["wire"])):
            if unasked:
                return DOUBT_NOTE.format(call=call["wire"])
            if _bypass():
                return unweighed if fresh else UNSURE  # P2.43: the App says whether the kernel would run it unasked
            turn["reread"] = True
            return REREAD_NOTE.format(call=call["wire"])
        # Auditoría de la mente (w8): a decision model not up (loading, or its server gone) answers nothing, so its
        # options are not made: each rival's name was completed on the slot for it (template + complete_name).
        if self.system_one is None or not self.system_one.ready or doubt["confidence"] >= _threshold("BAXY_S1_VETO"):
            return None
        if turn.get("reread") and not unasked:
            # Nor the model's reading again after a doubt (REREAD_NOTE, DOUBT_OTHER_NOTE): it decided. P2.43b: save in
            # Bypass one under BAXY_S1_VETO of another invocation, which the App weighs without the decision model.
            return unweighed if fresh and risk != "low_reversible" else None
        options = self._candidates(call["wire"], doubt, body)
        judged = self.system_one.choose(turn["text"], self._said(), options)
        self._judged = {"options": list(options), **judged} if judged else {"options": list(options), "choice": None}
        if self._unread:
            self._judged["rivals_unread"] = self._unread
        if not judged or judged["choice"] == call["wire"]:
            return None
        corrected = self._corrected(judged["choice"], body, call["wire"])
        if corrected is not None:
            self._judged["corrected"] = True
            return corrected
        if self.risk.get(call["wire"]) == "low_reversible":
            # Al máximo, System One 2: nor does layer 2 turn a low_reversible call into a question; it only corrects it.
            # On the same 26 runs it asked instead of 11, all right without System One (P112 ×4, P124 ×6, P113 ×1);
            # its corrections of them were 6 useful (P257) against 2 harmful.
            return None
        if turn.get("answering_other"):
            return None  # the person already answered layer 2's question about this request
        if self.risk.get(call["wire"]) == "read_only" and not self.effects.get(call["wire"]) \
                and self._reads_first(call["wire"], judged["choice"], body):
            # P2.44 causa 4 (V11D202, V11D086): the model read the window in front, the decision model chose window_snap,
            # which needs the windowId only that read gives. Not two readings: one, in two steps; «¿cuál de las dos?»
            # had the model ask which window or which side. The read runs, and the model decides with its result; a
            # read with an effect of the catalog (what it sends out of the PC) still asks.
            self._judged["reads_first"] = True
            return None
        other = OPTION_TEXT.get(judged["choice"], judged["choice"])
        if unasked:
            return DOUBT_OTHER_ASK_NOTE.format(call=call["wire"], other=other)
        turn["reread"] = True
        return DOUBT_OTHER_NOTE.format(call=call["wire"], other=other)

    def _said(self) -> list[dict[str, str]]:
        """What the person and BAXY said before the words being decided, for the decision model: their messages and
        BAXY's answers and questions (an ask_user's question lives in its call), never an internal note «[...]». Review
        2026-10-22: answering ask_user, the last two messages are not the clock and the request, and the question was
        left out."""
        source = self.conversation
        if source and source[-1].get("role") == "user":
            source = source[:-1]  # the request itself (an answer to ask_user is the tool message, left out by role)
        said = []
        for message in source:
            content = message.get("content")
            if message.get("role") in ("user", "assistant") and isinstance(content, str) and content.strip() \
                    and not content.startswith("["):
                said.append({"role": message["role"], "content": content})
            for call in message.get("tool_calls") or []:
                if call["function"]["name"] == ASK_USER["function"]["name"]:
                    try:
                        question = json.loads(call["function"]["arguments"]).get("question")
                    except (json.JSONDecodeError, AttributeError):
                        question = None
                    if isinstance(question, str) and question.strip():
                        said.append({"role": "assistant", "content": question})
        return said

    def _offered(self, turn: dict[str, Any], calls: list[dict[str, Any]]) -> tuple[str, list[str]] | None:
        """G10 (OFFER_NOTE): the first call with an effect of the catalog (any risk but read_only) whose text or number
        values, as whole words, the question the person just answered said and the person's words of the turn never,
        with those values; once per answer (turn["offer"] is spent)."""
        question = turn.get("offer")
        if not question:
            return None
        asked, said = _words(question), _words(turn.get("said") or turn["text"])
        for call in calls:
            if self.risk.get(call["wire"]) in (None, "read_only"):
                continue
            values = [str(value) for value in call["arguments"].values()
                      if isinstance(value, (str, int, float)) and not isinstance(value, bool)]
            only = [value for value in values if _words(value).strip() and _words(value) in asked
                    and _words(value) not in said]
            if only:
                turn["offer"] = ""
                return call["wire"], only
        return None

    def _kernel_confirms(self, wire: str) -> bool:
        """Whether the kernel asks the person before this tool runs, whatever its arguments: a risk it always confirms in
        normal mode (CONFIRMED_RISKS), not one of UNCONFIRMED_OPERATIONS, and the mode is not Bypass."""
        return self.risk.get(wire) in CONFIRMED_RISKS and self.wire_to_op.get(wire) not in UNCONFIRMED_OPERATIONS \
            and not _bypass()

    def _unasked(self, wire: str) -> bool:
        """Whether the kernel would run this tool without the person's «sí» though normal mode counts its risk as one to
        confirm: one of CONFIRMED_RISKS it does not confirm now (system.power; any in Bypass), or, in Bypass, one the
        kernel confirms in normal mode and not in Bypass, by the modes it sent (self.confirms; P2.41: of
        external_communication, normal mode asks only for those that reach a person, and Bypass none since 2026-11-02).
        P2.41b: a tool the catalog sent without them keeps the rule from before, external_communication."""
        risk, confirms = self.risk.get(wire), self.confirms.get(wire)
        skipped = risk == "external_communication" if confirms is None \
            else "normal" in confirms and "bypass" not in confirms
        return (risk in CONFIRMED_RISKS and not self._kernel_confirms(wire)) or (_bypass() and skipped)

    def _corrected(self, wire: str, body: dict[str, Any], chosen: str = "") -> dict[str, Any] | None:
        """The decision model's tool as a call the model filled itself (piece A), or None — the turn then asks: correcting
        is off, the tool's risk is not in CORRECTABLE_RISKS (or is one of CONFIRMED_RISKS the kernel would not confirm
        now), it has an effect of the catalog the model's own call (`chosen`) did not have, or the model did not write
        that tool's call."""
        risk = self.risk.get(wire)
        effects = set(self.effects.get(wire) or [])
        # Al máximo, System One 4 (decision2 P169, a weekly forecast asked in English, 14 of 14 runs of int0-int4): Qwen
        # chose web_search, Laya weather_current at 0.9, and 5.1 turned the correction into a question because
        # weather_current sends out of the PC — as web_search, the model's own call, already did. A tool that only reads
        # and whose effects the chosen call already has lands nowhere the model had not chosen to go; what it sends is
        # only what the conversation showed (every argument founded, the optional ones too). Keys, clicks and commands
        # (low_reversible and up) still never come from «corrige» (shell_command_run has the same network effect).
        shared = bool(effects) and risk == "read_only" and effects <= set(self.effects.get(chosen) or [])
        if _system_one("BAXY_S1_CORRECT") != "1" or risk not in CORRECTABLE_RISKS \
                or (effects and not shared) or (risk in CONFIRMED_RISKS and not self._kernel_confirms(wire)):
            return None
        # Auditoría de la mente (w8, P4): why a fill did not become the call, in the trace row beside the decision
        # model's answer (system_one.fill): failed (and its error), none (no call written), other (another tool's call)
        # or unfounded (_founded); a correction never tried (off, or the tool not correctable) writes none.
        why = self._judged if self._judged is not None else {}
        try:
            filled = self.server.fill_call(body, wire)
        except Exception as error:  # noqa: BLE001 - a fill that failed falls back to asking
            why["fill"] = {"failed": type(error).__name__}
            return None
        if not filled or filled.get("name") != wire:
            why["fill"] = "none" if not filled else {"other": str(filled.get("name"))}
            return None
        if not self._founded(wire, filled["arguments"], body["messages"], every=shared):
            why["fill"] = "unfounded"
            return None
        return {"id": self._new_id("s1"), "wire": wire, "arguments": filled["arguments"]}

    def _reads_first(self, read: str, wire: str, body: dict[str, Any]) -> bool:
        """Whether the model's read is the step before the decision model's tool: that tool's description names the
        read (window_snap: «Its windowId comes from window_resolve, window_active or app_open»), and, as the model fills
        it, a required argument holds a value no word of the person nor any result showed (_founded). The fill
        «corrige» already made is read, not made again; one that failed, wrote nothing or another tool tells nothing
        (in the trace, as «corrige» writes it). Never ask_user: its question is the model's own words."""
        tool = next((t["function"] for t in self.tools if t["function"]["name"] == wire), None)
        if wire == ASK_USER["function"]["name"] or tool is None \
                or not re.search(rf"(?<!\w){re.escape(read)}(?!\w)", str(tool.get("description") or "")):
            return False
        why = self._judged if self._judged is not None else {}
        if "fill" in why:
            return why["fill"] == "unfounded"
        try:
            filled = self.server.fill_call(body, wire)
        except Exception as error:  # noqa: BLE001 - a fill that failed tells nothing: layer 2 asks, as before
            why["fill"] = {"failed": type(error).__name__}
            return False
        if not filled or filled.get("name") != wire:
            why["fill"] = "none" if not filled else {"other": str(filled.get("name"))}
            return False
        founded = self._founded(wire, filled.get("arguments") or {}, body["messages"])
        why["fill"] = "founded" if founded else "unfounded"
        return not founded

    def _founded(self, wire: str, arguments: dict[str, Any], messages: list[dict[str, Any]],
                 every: bool = False) -> bool:
        """Whether a filled call holds every required argument of its tool and each text or number among them appears
        in what the conversation showed: the person's words or a tool's result (folded, as a whole word). B-MED-1 of the
        notebook (2026-10-22): Laya chose window_snap where Qwen chose window_resolve, and fill_call wrote windowId «1»,
        which no result had listed, and it ran; a web_download got a page of results as its url.
        Al máximo, System One 1: three kinds of value are the catalog's, not the person's words, and count as founded: a
        code of the argument's own enum («downloads» for «Descargas», «pause», «left»), an application or game the mind
        listed to the model in app_open and game_launch, or that game's appId («Worms W.M.D» for «el Worms»), and a file
        name whose name and extension were both said («contrato.pdf» for «el PDF contrato»: Qwen writes it so). Practice
        P203 (26 runs with System One, 2026-10-22): Laya chose file_read at 0.91 in 7 and «corrige» asked every time.
        Ids (windowId, reminderId…) and any other text still have to appear in the conversation or in a result.
        With `every`, the optional arguments it wrote are held to the same rule (one left empty is not written)."""
        tool = next((t["function"] for t in self.tools if t["function"]["name"] == wire), {})
        required = (tool.get("parameters") or {}).get("required") or []
        properties = (tool.get("parameters") or {}).get("properties") or {}
        optional = [name for name in arguments if name not in required
                    and arguments[name] is not None and arguments[name] != ""] if every else []
        seen = _fold(" ".join(str(m.get("content") or "") for m in messages
                              if m.get("role") == "tool" or (m.get("role") == "user"
                                                             and not str(m.get("content") or "").startswith("["))))

        def said(text: str) -> bool:
            return bool(text) and re.search(rf"(?<!\w){re.escape(text)}(?!\w)", seen) is not None

        for name in [*required, *optional]:
            value = arguments.get(name)
            if value is None or value == "":
                return False
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                continue
            prop = properties.get(name)
            if isinstance(value, str) and ((isinstance(prop, dict) and value in (prop.get("enum") or []))
                                           or self._listed(value)):
                continue
            text = _fold(str(int(value) if isinstance(value, float) and value.is_integer() else value))
            stem, dot, extension = text.rpartition(".")
            # Holdout v5 E062 (dictado): «hasta el setenta» founds 70; a transcript writes small numbers in words.
            number = int(text) if text.isdigit() and int(text) < 1000 else None
            if not said(text) and not (dot and re.fullmatch(r"[a-z0-9]{1,5}", extension) and said(stem)
                                       and said(extension)) \
                    and not (number is not None and (said(_fold(cardinal(number))) or said(cardinal_en(number)))):
                return False
        return True

    def _listed(self, value: str) -> bool:
        """Whether a value is a whole entry of the lists configure put in the descriptions of app_open («Installed
        applications (use one of these names as appId): A; B.») and game_launch («The person's installed games: Name
        (appId N, provider); …»): an application's name, a game's name or a game's appId."""
        folded = re.escape(_fold(value))
        lists = {"app_open": ("installed applications (use one of these names as appid): ",
                              rf"(?:^|; ){folded}(?=;|\.(?: |$))"),
                 "game_launch": ("the person's installed games: ", rf"(?:^|; ){folded} \(appid |\(appid {folded}, ")}
        for tool in self.tools:
            marker, entry = lists.get(tool["function"]["name"], ("", ""))
            description = _fold(str(tool["function"].get("description") or ""))
            at = description.find(marker) if marker else -1
            if at >= 0 and re.search(entry, description[at + len(marker):]):
                return True
        return False

    def _candidates(self, chosen: str, doubt: dict[str, Any], body: dict[str, Any]) -> dict[str, str]:
        """The model's own candidates as the decision model's options (as in its training, build_kev_data.py): the tool it
        chose, the tools it nearly wrote at its weakest name token (the rest of each name written greedily on the same
        slot), asking, and answering in words."""
        described = {t["function"]["name"]: short(t["function"]["description"]) for t in self.tools}
        # B-MED-3 (2026-10-22): the rule of its training (qwen_signals.py, rollouts): the chosen tool and the next three
        # tokens of the weakest one, each of p ≥ 0.01 (served, the chosen token took a place and a rival needed 0.02).
        names = [chosen]
        self._unread = []  # w8, P4: the rivals left out because their names could not be read, for the trace
        prompt: str | None = None  # the decision's prompt, rendered once for all of its rivals (al máximo V3)
        for token, p in doubt.get("rivals") or []:
            if p < 0.01 or len(names) >= 4:
                continue
            written = doubt.get("written", "") + token
            try:
                if ">" not in written[written.find("<function="):]:
                    prompt = prompt if prompt is not None else self.server.template(body)
                    written += self.server.complete_name(prompt, written)
            except Exception as error:  # noqa: BLE001 - a rival that cannot be read is left out
                self._unread.append({"token": token, "failed": type(error).__name__})
                continue
            at = written.find("<function=")
            names.append(written[at + len("<function="):].split(">")[0].strip() if at >= 0 else "")
        # A rival closed on the plain name of a renamed tool (audio_volume, an older catalog's) is that tool.
        names = [self.wires.name(op) if (op := self.wires.known(n)) else n for n in names]
        options = {n: described[n] for n in dict.fromkeys(names) if n in described and n != ASK}
        return {**options, ASK: OPTION_TEXT[ASK], ANSWER: OPTION_TEXT[ANSWER]}

    def _result(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any] | None, reply: dict | None,
                stage: str, started: float, content: str) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "turn.result", "id": request_id, "kind": "conversation", "operation": None,
                                  "arguments": None, "question": "", "reply": ""}
        closed = turn.pop("ask_closed", False)  # this decision follows a question not asked again (aid «ask_once»)
        if call is not None and call["wire"] == "ask_user":
            question = " ".join(str(call["arguments"].get("question") or "").split())
            later = [c["id"] for c in turn.get("queue") or []]
            turn["queue"], turn["awaiting"] = [], None
            folded = " ".join(re.findall(r"[^\W_]+", _fold(question)))
            alike = any(difflib.SequenceMatcher(None, folded, asked).ratio() >= ASKED_ALIKE
                        for asked in turn.get("questions", []))
            echo = not alike and _echoes(folded, turn["text"])
            same = not alike and not echo and _same_twice(folded)
            if folded and _aid_on("ask_once") and (closed or alike or echo or same):
                closed = closed or ((echo or same) and turn.get("echoed", False))
                not_run = (ASKED_CLOSED_NOT_RUN if closed else ASKED_AGAIN_NOT_RUN if alike
                           else ASKED_SAME_NOT_RUN if same else ASKED_ECHO_NOT_RUN)
                for call_id in [call["id"], *later]:
                    turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                         "content": not_run if call_id == call["id"] else NOT_RUN})
                self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                          kind=("ask_same" if same else "ask_echo") if (same or echo) and not closed
                          else "ask_repeat_closed", operation=None,
                          arguments=None, content=None)
                # Feria 2026-10-27: the decision after it had no tools, though the answer to the question asked for one
                # (the topic of a presentation to make: it said it could not make it without one). It keeps them; only
                # asking is closed in it, and asking there again ends the turn in words. After an echo asking stays
                # open (a datum the person did not give); a second echo in the turn ends it in words.
                turn["ask_closed"] = alike and not closed
                turn["echoed"] = turn.get("echoed", False) or echo or same
                return self._next(request_id, stage, turn, final=closed)
            # Encargo 119: only the turn's first question, before anything ran and with nothing waiting for a yes; the
            # model may still ask it, and then it is asked.
            front = turn.pop("front", "") if stage == "turn.decide" else ""
            if folded and front and not turn.get("pending") and not turn.get("answering") and _aid_on("front_not_asked"):
                for call_id in [call["id"], *later]:
                    content = FRONT_NOT_ASKED.format(window=front)
                    turn["conv"].append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(
                        {"status": "not_run", "reason": content}, ensure_ascii=False) if call_id == call["id"] else NOT_RUN})
                self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                          kind="ask_front", operation=None, arguments=None, content=None)
                return self._next(request_id, stage, turn)
            if folded:
                turn.setdefault("questions", []).append(folded)
            if question:
                turn["asked"], turn["after_asked"] = call["id"], later
                turn["asked_question"] = question
                result.update(kind="clarify", question=question)
            else:
                # An empty question asks nothing: it and the calls after it did not run, and what the model wrote
                # beside it is its answer.
                for call_id in [call["id"], *later]:
                    turn["conv"].append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
                if not content:
                    # Nothing to say beside it: the model answers in words from what ran (an empty reply after an
                    # action was a failed turn that never told what happened; round 2).
                    self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                              kind="ask_user_empty", operation=None, arguments=None, content=None)
                    return self._next(request_id, stage, turn, final=True)
                result.update(reply=content)
        elif call is not None and call["wire"] == CONFIRM["function"]["name"] and not turn.get("pending"):
            # A question that ended unanswered just before these words is told once, as what it is, and the model may
            # call that tool again (the kernel asks again for that exact invocation) or answer in words.
            ended = turn.pop("ended", None)
            # uso-90 (held-out c90-H4/H5): «entra con mi cuenta…», the click held for the person's «sí», and the model
            # called confirm_pending yes itself in the same turn; told «nothing pending», it said «No hay nada pendiente
            # para confirmar» and asked nothing. A call held in this turn waits for a question not asked yet.
            held = not ended and any(r.get("outcome") == WAITS_FOR_YES for r in turn.get("receipts") or [])
            told = (ended_result(ended, self.wires.name) if ended else NOT_ASKED_YET if held else NOTHING_PENDING)
            for call_id in [call["id"], *(c["id"] for c in turn.get("queue") or [])]:
                turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                     "content": told if call_id == call["id"] else NOT_RUN})
            turn["queue"], turn["awaiting"] = [], None
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                      kind="confirmation_ended" if ended else "not_asked_yet" if held else "nothing_pending",
                      operation=ended["operation"] if ended else None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=not ended)
        elif call is not None and call["wire"] == CALCULATE["function"]["name"]:
            # Computed here, never handed to the App; what the model wrote beside it waits for the value. Code review
            # 2026-10-27: the App's step budget never sees these calls, so the same expression again closes the turn's
            # calls, as a repeat the App runs does (same_call_closes).
            computed = turn.setdefault("calculated", [])
            if _call_key(call["arguments"]) in computed and _aid_on("same_call_closes"):
                return self._close_repeat(request_id, turn, call, reply, stage, started, "same_call_closed",
                                          SAME_CALL_NOT_RUN, SAME_CALL_REFUSED)
            computed.append(_call_key(call["arguments"]))
            kind = "calculated"
            expression = str(call["arguments"].get("expression") or "")
            try:
                told = json.dumps({"status": "completed", "value": evaluate(expression)}, ensure_ascii=False)
                if _aid_on("unsourced_number"):
                    told += unsourced_note(expression, turn["conv"])
                    if "[Ayuda: " in told:
                        turn.setdefault("unsourced", []).append(_unsourced_entry(
                            expression, turn["conv"], evaluate(expression)))
            except ValueError as error:
                told, kind = json.dumps({"status": "failed", "error": str(error)}), "calculation_failed"
            for call_id in [call["id"], *(c["id"] for c in turn.get("queue") or [])]:
                turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                     "content": told if call_id == call["id"] else CALCULATED_FIRST})
            turn["queue"], turn["awaiting"] = [], None
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"], kind=kind,
                      operation=None, arguments=None if turn.get("private") else call["arguments"], content=None)
            # Code review 2026-10-27: new expressions each time never reach the App's budget either; past
            # CALCULATIONS the answer is in words.
            return self._next(request_id, "turn.continue", turn, final=len(computed) >= CALCULATIONS)
        elif call is not None and self.wire_to_op.get(call["wire"]) == "baxy.routines" and not call.get("mind"):
            # RUT7 (RUTINAS.md §5 d): the model's own call of baxy.routines carries nothing: it opens the guide, here,
            # and BAXY's words are its first question. Never handed to the App; what the model wrote beside it and the
            # calls after it are not said nor run (the person is now answering the guide).
            for call_id in [call["id"], *(c["id"] for c in turn.get("queue") or [])]:
                turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                     "content": GUIDE_OPENED if call_id == call["id"] else NOT_RUN})
            turn["queue"], turn["awaiting"] = [], None
            self._guide, self._guide_at = routine_guide.Guide(lang=routine_guide.lang_of(self.lang)), time.monotonic()
            content = self._guide.question()
            turn["conv"].append({"role": "assistant", "content": content})
            if self.foresee is not None:
                try:
                    self.foresee(content, True)
                except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                    pass
            self._log("turn.routine_order", started, None, action="new", lang=self._guide.lang, step="kind", model=True)
            call = None
            result.update(reply=content)
        elif call is not None:
            name = (CONFIRM_OPERATION if call["wire"] == CONFIRM["function"]["name"]
                    else self.wire_to_op.get(call["wire"]) or self.withheld.get(call["wire"], call["wire"]))
            if (name == CONFIRM_OPERATION and turn.get("pending") and call["arguments"].get("answer") == "yes"
                    and turn.get("their_yes") != CONFIRM_OPERATION):
                # SIS3: the model's yes is not the person's; their words were read as no yes (_their_answer).
                # REM2 (REV13 A-1): answered here, its receipt said «it still waits», but the App dropped what waited at
                # the end of the turn: the line asking again was published as a line of this turn after a question of
                # the last (NativeTurnLoop.Publish, DropLeftBehind), and the next «sí» found nothing. The App is told
                # «unclear» (AskedAgain: it keeps waiting and the next line is its question again), and the model reads
                # why (NOT_THEIR_YES, continue_turn) when the App says it waits; the calls behind it do not run.
                for later in turn.get("queue") or []:
                    turn["conv"].append({"role": "tool", "tool_call_id": later["id"], "content": _not_run_after(later)})
                # REM4 (REV14 A-R3): read as no too, still «unclear», never «no» given for them (SIS3, banco: questions
                # read as no, 3 of 3); a line after it that asks nothing drops it in the App (NativeTurnLoop.Publish).
                turn["queue"], turn["not_their_yes"] = [], call["id"]
                call = {**call, "arguments": {"answer": "unclear"}}
            refused = self._repeat_refused(turn, name, call)
            if refused:
                return self._close_repeat(request_id, turn, call, reply, stage, started, *refused)
            unopened = self._unopened(turn, call)
            if unopened:
                held = json.loads(unopened)
                turn["window_told" if "window" in held else "unopened_told"] = True
                refused = UNOPENED_REFUSED if "application" in held else UNSEEN_REFUSED
                return self._held_back(request_id, turn, call, reply, stage, started, unopened, refused, "unopened_app")
            unsaid = self._unsaid_file(turn, name, call)
            if unsaid:
                turn["file_told"] = True
                return self._held_back(request_id, turn, call, reply, stage, started, unsaid, FILE_UNSAID_REFUSED,
                                       "said_file_name")
            unsaid = self._unsaid_place(turn, name, call)
            if unsaid:
                turn["place_told"] = True
                return self._held_back(request_id, turn, call, reply, stage, started, unsaid, PLACE_UNSAID_REFUSED,
                                       "said_place")
            left_out =self._left_out(turn, name, call)
            if left_out:
                return self._left_out_back(request_id, turn, call, reply, stage, started, left_out)
            cut_address = self._cut_address(turn, call)
            if cut_address is not None:
                return self._cut_address_back(request_id, turn, call, reply, stage, started, cut_address)
            turn["awaiting"] = call["id"]
            turn["calling"] = name
            turn["calling_args"] = json.dumps(call["arguments"], sort_keys=True, ensure_ascii=False)
            arguments = self._expand({**call["arguments"], **self.constants.get(name, {})})
            if name == "web.fetch":
                arguments = web_focus.widen(arguments)  # goal h-web: it reads a wider part
            if name == "baxy.routines":
                # RUT1: the store keeps operations, those off in the profile too (the App refuses those steps).
                arguments = routines.named_steps(arguments, {**self.withheld, **self.wire_to_op})
            result.update(kind="action", operation=name, arguments=arguments)
            if turn.get("their_yes") == name:
                result["theirYes"] = True  # SIS3: the person's yes, read by _their_answer, goes with this step
            if turn.get("unsure") is call:
                result["unsure"] = True
        elif content:
            result.update(reply=content)
        doubt_of = {"doubt_of": turn.pop("doubt_of")} if "doubt_of" in turn else {}
        if str(result["operation"] or "").startswith("memory.") or str(doubt_of.get("doubt_of")).startswith("memory."):
            turn["private"] = True
        private = bool(turn.get("private"))
        # What the person keeps in memory stays out of the trace, as in the App's (NativeTurnLoop): from the memory
        # call on, their words, the calls' arguments and the model's text.
        self._log(stage, started, reply, text=None if private else turn["text"],
                  kind="doubt_unsure" if result.get("unsure") else result["kind"], operation=result["operation"], arguments=call["arguments"] if call and not private else None,
                  content=None if private else content, **doubt_of)
        return result

    @staticmethod
    def _asked_of(conv: list[dict[str, Any]], text: str, label: str) -> bool:
        """Whether what BAXY said just before the person's last words was a question that names this label. Cosecha 05-11:
        «¿Le doy a «SALIR»?», «sí, sale»: the click came back «the person did not ask to close anything», and they had to
        say it a third time, in the words the rule reads. The answer to it is the model's to read."""
        wanted = _fold(label).strip()
        words = next((i for i in range(len(conv) - 1, -1, -1)
                      if conv[i].get("role") == "user" and str(conv[i].get("content") or "").startswith(text)), 0)
        before = next((str(m.get("content")) for m in reversed(conv[:words])
                       if m.get("role") == "assistant" and str(m.get("content") or "").strip()), "")
        return "?" in before and bool(wanted) and re.search(rf"(?<!\w){re.escape(wanted)}(?!\w)", _fold(before)) is not None

    @staticmethod
    def _repeat_refused(turn: dict[str, Any], name: str, call: dict[str, Any]) -> tuple[str, str, str] | None:
        """Aids «same_call_closes» and «look_click_cap» (LOOK_CLICK_PAIRS): whether this call of the model is one the
        mind does not hand to the App, as (the trace's kind, its result, its facts); None: it runs."""
        arguments = _call_key(call["arguments"])
        if (call["wire"] == "input_visible_click" and _aid_on("close_unsaid")
                and _CLOSES.match(_fold(str(call["arguments"].get("label") or "")))
                and not _CLOSE_SAID.search(_fold(str(turn.get("text") or "")))
                and not Mind._asked_of(turn["conv"], str(turn.get("text") or ""), str(call["arguments"].get("label") or ""))):
            return "close_unsaid", CLOSE_NOT_RUN, CLOSE_REFUSED
        # Since the last other call that acted, whatever it said (a window already gone, an app opened: the same close
        # runs again); its first result since then is the earlier one.
        unchanged, first = False, None
        for receipt in turn.get("receipts") or []:
            if _same_ended(receipt, call["wire"], call["arguments"], VERIFICATION["unchanged"], SET_BY_SAME):
                unchanged, first = True, first or receipt
            elif not receipt.get("read"):
                unchanged = False
                first = receipt if _same_ended(receipt, call["wire"], call["arguments"], *COMPLETED_OUTCOMES) else None
        if unchanged and first and _aid_on("same_call_closes"):
            return ("unchanged_closed", json.dumps({**UNCHANGED_NOT_RUN, "earlier": json.loads(first["observation"])},
                                                   ensure_ascii=False), UNCHANGED_REFUSED)
        if turn.get("same_told_call") == [name, arguments] and _aid_on("same_call_closes"):
            return "same_call_closed", SAME_CALL_NOT_RUN, SAME_CALL_REFUSED
        if (call["wire"] == "input_visible_click" and turn.get("look") and _aid_on("look_click_cap")
                and (turn.get("look_clicks") or {}).get(json.dumps([*turn["look"], arguments], ensure_ascii=False),
                                                       0) >= LOOK_CLICK_PAIRS):
            return "look_click_closed", LOOK_CLICK_NOT_RUN, LOOK_CLICK_REFUSED
        # Uso real 2026-10-26: the same click on Spotify («Reproducir», the same index) failed five times in a row
        # (protected_window), a look between each that never saw quite the same, for a minute and a half: a click that
        # did not complete LOOK_CLICK_PAIRS times with these arguments since the last call that changed something is
        # not made again, whatever the looks saw (after «Archivo» opened its menu, «Guardar como» runs again).
        if call["wire"] == "input_visible_click" and _aid_on("look_click_cap"):
            missed = 0
            for receipt in turn.get("receipts") or []:
                if receipt.get("completed") and not receipt.get("read"):
                    missed = 0
                elif (receipt.get("tool") == call["wire"] and not receipt.get("completed")
                      and _call_key(receipt.get("arguments") or {}) == arguments):
                    missed += 1
            if missed >= LOOK_CLICK_PAIRS:
                return "look_click_closed", LOOK_CLICK_NOT_RUN, LOOK_CLICK_REFUSED
        # Uso real 2026-10-26: «qué es la inteligencia artificial» read the same Wikipedia page 14 times, only its
        # maximumCharacters going up by 1000, 43 s for one sentence (same_call_closes never saw the same arguments): a
        # page already read LOOK_CLICK_PAIRS times in the turn is not read again, whatever the size asked.
        if call["wire"] == "web_fetch" and _aid_on("same_call_closes"):
            url = str(call["arguments"].get("url") or "").strip().rstrip("/")
            read = sum(r.get("tool") == "web_fetch"
                       and str((r.get("arguments") or {}).get("url") or "").strip().rstrip("/") == url
                       for r in turn.get("receipts") or [])
            if url and read >= LOOK_CLICK_PAIRS:
                return "same_call_closed", SAME_CALL_NOT_RUN, SAME_CALL_REFUSED
        # Uso real 2026-10-26: «baja el volumen a 30» unmuted the PC, then muted it, then unmuted it… seven times, the
        # person having asked for neither: a call that only turns back a yes/no an earlier call of the same operation
        # set in this turn (it would undo what the turn did) is not made.
        earlier = next((r for r in reversed(turn.get("receipts") or []) if r.get("tool") == call["wire"]
                        and r.get("completed") and not r.get("read")
                        and _flips(r.get("arguments") or {}, call["arguments"])), None)
        if earlier is not None and _aid_on("same_call_closes"):
            return "flip_closed", *flip_not_run(earlier.get("arguments") or {}, call["arguments"])
        return None

    def _close_repeat(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any], reply: dict | None,
                      stage: str, started: float, kind: str, result: str, refused: str) -> dict[str, Any]:
        """A refused repeat (_repeat_refused) ends its turn's calls: it and the calls queued behind it do not run, its
        result says why with the turn's facts, and the model answers in words from what the results show, as when the
        App closes a turn (NO_MORE_CALLS)."""
        done = turn.setdefault("done", [])
        done.append(f"{call['wire']} → {refused}")
        line = _said_once(done) if _aid_on("facts_once") else done
        for later in [call, *(turn.get("queue") or [])]:
            told = result + TURN_FACTS + "; ".join(line) + "]" + NO_MORE_CALLS if later is call else NOT_RUN
            turn["conv"].append({"role": "tool", "tool_call_id": later["id"], "content": told})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(later["wire"], later["wire"]), "tool": later["wire"],
                "arguments": later["arguments"], "observation": result if later is call else NOT_RUN,
                "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(later["wire"]) == "read_only"})
        turn["queue"], turn["awaiting"] = [], None
        private = bool(turn.get("private"))
        self._log(stage, started, reply, text=None if private else turn["text"], kind=kind,
                  operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None if private else call["arguments"], content=None)
        return self._next(request_id, stage, turn, final=True)

    def _unopened(self, turn: dict[str, Any], call: dict[str, Any]) -> str:
        """Aid «unopened_app», when this call types or presses a key and the turn has not told it yet: the result that
        holds it, or empty and it runs. Held: a window number no result of the conversation showed (I7); with no window
        and no field, the installed applications the person's words in this turn name when no completed call of the
        turn opened, focused or resolved any of them, or acted naming one (a name that is in a text typed in this turn
        is what is written, not where); and, with none named, the window in front that no result showed, in a turn
        where no call acted (I7)."""
        arguments = call["arguments"]
        receipts = turn.get("receipts") or []

        def targeted(given: dict[str, Any]) -> bool:
            return any(given.get(key) not in (None, "") for key in TARGET_ARGUMENTS)

        if call["wire"] not in WRITES_TO_FRONT or turn.get("beat") or not _aid_on("unopened_app"):
            return ""
        # I13 (R5-2): the window in front the mind told instead of a question (ask_front) is no call that found it: with
        # it counted as shown (I12, R4's A2), «escribe hola en la ventana de Zumbalo» asked first and went into it.
        results = [str(m.get("content") or "") for m in turn["conv"] if m.get("role") == "tool"]
        results = [content for content in results if not content.startswith(NOT_RUN_MARK)]
        shown = " ".join(results)
        window = arguments.get("window")
        # Its own once per turn (I7 bench: told the window in front, the model typed again with «window»: 1).
        if window not in (None, "") and not isinstance(window, bool):
            number = re.escape(str(window))
            return "" if turn.get("window_told") or re.search(_SHOWN_WINDOW.format(number=number), shown,
                                                                re.IGNORECASE) else unseen_window_not_run(window)
        if turn.get("unopened_told"):
            return ""
        # Not when the turn already acts on a window it looked at (a typing with window, then its Enter).
        if targeted(arguments) or any(r.get("completed") and targeted(r.get("arguments") or {}) for r in receipts):
            return ""
        said = _words(str(turn.get("said") or turn.get("text") or ""))
        written = [arguments, *(r.get("arguments") or {} for r in receipts if r.get("tool") in WRITES_TO_FRONT)]
        typed = _words(" ".join(str(given.get(key) or "") for given in written for key in ("text", "replacing")))
        named = [name for name in dict.fromkeys(self.names)
                 if _words(name).strip() and _PLACE.search(said.replace(_words(name), " \0 "))
                 and _words(name) not in typed]
        acted = [r for r in receipts if r.get("completed") and r.get("tool") not in WRITES_TO_FRONT
                 and (r.get("tool") in OPENS_WINDOW or not r.get("read"))]
        if named:
            reached = "".join(_words(json.dumps(r.get("arguments"), ensure_ascii=False) + " "
                                     + _as_read(r.get("observation"))) for r in acted)
            return "" if any(_words(name) in reached for name in named) else unopened_not_run(named)
        front = turn.get("in_front") or {}
        if acted or any(r.get("completed") for r in receipts if r.get("tool") in WRITES_TO_FRONT) or not any(
                str(front.get(key) or "").strip() for key in ("title", "process")) or _shows_window(front, results):
            return ""
        told = [str(m.get("content") or "") for m in turn["conv"] if m.get("role") == "tool"]
        return front_unseen_not_run(self._front_window(front), _shows_window(front, told, completed=False))

    def _unsaid_file(self, turn: dict[str, Any], name: str, call: dict[str, Any]) -> str:
        """Aid «said_file_name» (I7): the result that holds a file_write whose path writes a file of the same extension
        as one the person's words name, when neither those words nor any result of the conversation show the name it
        writes; empty, it runs. Said once in a turn."""
        # By operation and by wire name: a mind with no catalog yet knows only the wire (as ADDRESS_OPS).
        if name not in ("file.write", "file_write") or turn.get("beat") or turn.get("file_told") \
                or not _aid_on("said_file_name"):
            return ""
        written = re.split(r"[\\/]", str(call["arguments"].get("path") or ""))[-1].strip()
        leaf = _FILE_NAME.fullmatch(written)
        if not leaf:
            return ""
        words = str(turn.get("said") or turn.get("text") or "")
        said = list(dict.fromkeys(found.group(0) for found in _FILE_NAME.finditer(words)
                                  if found.group(1).lower() == leaf.group(1).lower()))
        shown = _fold(words + " " + " ".join(str(m.get("content") or "") for m in turn["conv"] if m.get("role") == "tool"
                                             and not str(m.get("content") or "").startswith(NOT_RUN_MARK)))
        if not said or re.search(rf"(?<!\w){re.escape(_fold(written))}(?!\w)", shown):
            return ""
        return file_unsaid_not_run(said, written)

    def _unsaid_place(self, turn: dict[str, Any], name: str, call: dict[str, Any]) -> str:
        """Aid «said_place» (CLI1): the result that holds a weather call whose location neither the person's words of
        the conversation nor any of its results show, not even alike in spelling; empty, it runs. Said once in a
        turn."""
        if name not in ("weather.current", "weather_current") or turn.get("beat") or turn.get("place_told") \
                or not _aid_on("said_place"):
            return ""
        location = str(call["arguments"].get("location") or "").strip()
        place = location.split(",")[0]
        shown = " ".join([str(m.get("content") or "") for m in turn["conv"] if m.get("role") == "user"
                          and not str(m.get("content") or "").startswith("[")]
                         + [str(m.get("content") or "") for m in turn["conv"] if m.get("role") == "tool"
                            and not str(m.get("content") or "").startswith(NOT_RUN_MARK)]
                         + [str(turn.get("said") or turn.get("text") or "")])
        if not place.strip() or not _latin_only(place + shown):
            return ""
        seen = set(_words(shown).split())
        if any(_alike(word, other) for word in _words(place).split() if len(word) >= 3 for other in seen):
            return ""
        return place_unsaid_not_run(call["wire"], location)

    # Encargo A11 (R18 en la flota, diag-6f20): the calls whose «url» _cut_address weighs, by operation and by wire
    # name (a mind with no catalog yet knows only the wire).
    ADDRESS_OPS = ("web.fetch", "browser.navigate", "browser.navigate.named",
                   "web_fetch", "browser_navigate_set", "browser_navigate_named")

    def _cut_address(self, turn: dict[str, Any], call: dict[str, Any]) -> dict[str, Any] | None:
        """A web.fetch whose address ends in «…» or «...» is an address cut where it was copied, not one that exists
        (A7: every web.fetch of «el último Mundial» answered web_fetch_status_404 with «https://…/argentina-vs-espana-la-...»).
        Encargo A11 (R18, diag-6f20): an address with «›» is the form a results page writes under a result's
        title («host › section › section»: the breadcrumb of Google's and DuckDuckGo's pages), copied from the page
        read; it is no address (with its spaces it is not even a URI: RFC 3986) and the fetch failed or waited for
        the person's «sí» on a host nobody gave. The same holds for an address opened in the browser. «…» anywhere
        in it is a cut too.
        Only its form is compared: with the address expanded (a short reference put back), the call is held back
        before it goes out, and the model is told which address of this turn's results begins the same way (the first
        one, in the order the results came), else what the form is. None: it goes."""
        if self.wire_to_op.get(call["wire"], call["wire"]) not in self.ADDRESS_OPS:
            return None
        given = self._expand(call["arguments"].get("url"))
        if not isinstance(given, str):
            return None
        given = given.strip()
        shown = "›" in given
        if shown:
            stem = re.sub(r"\s*›\s*", "/", given).split("…", 1)[0]
        elif "…" in given:
            stem = given.split("…", 1)[0]
        elif given.endswith("..."):
            stem = given.removesuffix("...")
        else:
            return None
        stem = stem.rstrip("./ ")

        def bare(url: str) -> str:
            return re.sub(r"^(https?://)?(www\.)?", "", url.strip(), flags=re.IGNORECASE)

        whole: str | None = None
        for receipt in turn.get("receipts") or []:
            try:
                found = json.loads(receipt.get("observation") or "")
            except (json.JSONDecodeError, TypeError):
                continue
            urls: list[str] = []

            def collect(node: Any) -> None:
                if isinstance(node, dict):
                    for key, value in node.items():
                        if key == "url" and isinstance(value, str):
                            urls.append(value)
                        else:
                            collect(value)
                elif isinstance(node, list):
                    for value in node:
                        collect(value)

            collect(found)
            whole = next((u for u in urls if bare(stem) and bare(u).startswith(bare(stem)) and bare(u) != bare(stem)),
                         None)
            if whole:
                break
        return {"url": given, "whole": whole, "shown": shown}

    def _cut_address_back(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any], reply: dict | None,
                          stage: str, started: float, cut: dict[str, Any]) -> dict[str, Any]:
        """The held-back call of _cut_address goes back to the model as a failure before any request, with the
        whole address as its next when a result of the turn gives it; calls queued behind it do not run."""
        observed: dict[str, Any] = {"url": cut["url"]}
        fetch = call["wire"] == "web_fetch"
        if cut["whole"]:
            observed["next"] = (f'{call["wire"]} {json.dumps({"url": cut["whole"]}, ensure_ascii=False)} '
                                f'{"reads" if fetch else "opens"} the page: that is the whole address of the result '
                                "this one begins like")
        elif cut["shown"]:
            observed["next"] = ("an address written with «›» is how a results page shows where a result is (its "
                                "site › its sections), not an address: the result is opened from the page by its "
                                "title, or a whole address is copied from a result's url")
        else:
            observed["next"] = ("an address ending in «…» or «...» was cut where it was copied; copy a whole address "
                                "from a result of web_search, or search again for the page")
        error = ("url_display_form" if cut["shown"] else "web_fetch_url_truncated" if fetch else "url_truncated")
        told = json.dumps({"status": "failed", "error": error, "observed": observed},
                          ensure_ascii=False, separators=(",", ":"))
        done = turn.setdefault("done", [])
        done.append(f"{call['wire']} → no se ejecutó: "
                    + ("la dirección era la que muestra una página de resultados con «›»" if cut["shown"]
                       else "la dirección estaba cortada con «…»"))
        line = _said_once(done) if _aid_on("facts_once") else done
        for later in [call, *(turn.get("queue") or [])]:
            turn["conv"].append({"role": "tool", "tool_call_id": later["id"],
                                 "content": told + TURN_FACTS + "; ".join(line) + "]" if later is call else _not_run_after(later)})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(later["wire"], later["wire"]), "tool": later["wire"],
                "arguments": later["arguments"], "observation": told if later is call else _not_run_after(later),
                "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(later["wire"]) == "read_only"})
        turn["queue"], turn["awaiting"] = [], None
        private = bool(turn.get("private"))
        self._log(stage, started, reply, text=None if private else turn["text"], kind="cut_address",
                  operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None if private else call["arguments"], content=None)
        return self._next(request_id, "turn.continue", turn)

    @staticmethod
    def _left_out(turn: dict[str, Any], name: str, call: dict[str, Any]) -> list[str]:
        """Aid «query_left_name»: the names the person said that this web_search leaves out; said once in a turn."""
        if name != "web.search" or turn.get("beat") or turn.get("left_told") or not _aid_on("query_left_name"):
            return []
        return _names_left_out(str(turn.get("text") or ""), call["arguments"])

    def _left_out_back(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any], reply: dict | None,
                       stage: str, started: float, names: list[str]) -> dict[str, Any]:
        """A search held by «query_left_name» goes back to the model with the names and the call; nothing queued behind
        it runs: it decides again, with its tools."""
        turn["left_told"] = True
        done = turn.setdefault("done", [])
        done.append(f"{call['wire']} → {LEFT_NAME_REFUSED}")
        line = _said_once(done) if _aid_on("facts_once") else done
        result = left_name_not_run(call["wire"], names)
        for later in [call, *(turn.get("queue") or [])]:
            told = result + TURN_FACTS + "; ".join(line) + "]" if later is call else _not_run_after(later)
            turn["conv"].append({"role": "tool", "tool_call_id": later["id"], "content": told})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(later["wire"], later["wire"]), "tool": later["wire"],
                "arguments": later["arguments"], "observation": result if later is call else _not_run_after(later),
                "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(later["wire"]) == "read_only"})
        turn["queue"], turn["awaiting"] = [], None
        private = bool(turn.get("private"))
        self._log(stage, started, reply, text=None if private else turn["text"], kind="query_left_name",
                  operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None if private else call["arguments"], content=None)
        return self._next(request_id, "turn.continue", turn)

    def _held_back(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any], reply: dict | None,
                   stage: str, started: float, result: str, refused: str, kind: str) -> dict[str, Any]:
        """A call held by «unopened_app» or «said_file_name» goes back to the model with why, and the calls queued
        behind it (chosen on the same reading) do not run: the model decides again, with its tools."""
        done = turn.setdefault("done", [])
        done.append(f"{call['wire']} → {refused}")
        line = _said_once(done) if _aid_on("facts_once") else done
        for later in [call, *(turn.get("queue") or [])]:
            told = result + TURN_FACTS + "; ".join(line) + "]" if later is call else _not_run_after(later)
            turn["conv"].append({"role": "tool", "tool_call_id": later["id"], "content": told})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(later["wire"], later["wire"]), "tool": later["wire"],
                "arguments": later["arguments"], "observation": result if later is call else _not_run_after(later),
                "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(later["wire"]) == "read_only"})
        turn["queue"], turn["awaiting"] = [], None
        private = bool(turn.get("private"))
        self._log(stage, started, reply, text=None if private else turn["text"], kind=kind,
                  operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None if private else call["arguments"], content=None)
        return self._next(request_id, "turn.continue", turn)

    # ---- trace ---------------------------------------------------------------------------------------------
    def forget_trace(self) -> bool:
        """Auditoría de la mente (w8, 2026-10-23): the person had BAXY forget everything («olvida todo») or deleted every
        conversation, and the App deletes its own conversation log then; this trace kept their words, BAXY's answers and
        the calls' arguments in clear text, and so did its archive (turns.jsonl.1, __main__.bounded_trace). Both go, the
        way the voice's rows are written (one at a time); what comes after is traced again. Whether none is left (a file
        another reader holds open is emptied instead; if not even that, it stays and the next forget takes it)."""
        left = False
        with self._log_lock:
            for path in (self.trace, self.trace.with_name(self.trace.name + ".1")):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    try:
                        path.open("w", encoding="utf-8").close()
                    except OSError:
                        left = True
        return not left

    def _log(self, stage: str, started: float, reply: dict[str, Any] | None, **fields: Any) -> None:
        timings = (reply or {}).get("timings") or {}
        # Every time of the trace is read on perf_counter (al máximo V4): on Windows, Python 3.12's monotonic clock
        # moves in steps of ~15.6 ms, and every ms was a multiple of it. The voice's times (voice.speak) too.
        row = {"t": _dt.datetime.now().isoformat(timespec="milliseconds"), "stage": stage,
               "ms": round((time.perf_counter() - started) * 1000),
               "cache_n": timings.get("cache_n"), "prompt_n": timings.get("prompt_n"), "prompt_ms": timings.get("prompt_ms"),
               "predicted_n": timings.get("predicted_n"), "predicted_ms": timings.get("predicted_ms"), **fields}
        if stage == "turn.decide" and self._ear_unsure:
            row["ear_unsure"], self._ear_unsure = self._ear_unsure, []
        if stage == "turn.decide" and self.arrived is not None:
            row["before_ms"], self.arrived = round((started - self.arrived) * 1000), None
            row["app_ms"], self.app_ms = self.app_ms, None
        if timings:
            # Noche P0.5: prompt_n is only what was read again. With the whole prompt (usage) and the prefix (tools,
            # system and the warm-up's few words), each prompt splits into prefix, history and what is new (within those
            # few tokens), and a cut shows as the cache it lost.
            row.update(prompt_tokens=((reply or {}).get("usage") or {}).get("prompt_tokens"),
                       prefix_n=self.prefix_tokens)
        doubt = read_doubt(reply, fields.get("call_index") or 0)  # P2.40: the doubt of the call held, if queued
        if doubt is not None:
            doubt.pop("written", None)  # the call's own text up to its weakest token: only for reading the rivals
            row["doubt"] = doubt
        if self._judged is not None and stage.startswith("turn."):
            # Only a turn's own row carries the decision model's answer: the voice thread logs here too (voice.speak).
            row["system_one"], self._judged = self._judged, None
        self._write_row(row)

    # PRV1 (revisión de privacidad 2026-11-09, PRIV-02): the trace kept, in clear text and for up to 100 MB, every word
    # the person said, BAXY's answers and each call's arguments, and no text of the product said so. The trace is for
    # measuring (times, what was called, what failed); the identity says what BAXY keeps of the person: «las
    # preferencias del usuario, lo que suele pedir, y la conversación reciente», which «se puede ver, editar y borrar
    # entero» (documentacion/00_IDENTIDAD.md, «Memoria y privacidad»), and that is the kept conversations, sealed. So
    # the product's trace keeps no words (trace_words False, set by __main__.trace_words): only these fields of a row,
    # which hold times, counts, names of operations and of rules, and codes. A field not listed here is not written:
    # a new one that carries words stays out without anyone remembering to hide it. A bench's run, or a PC whose
    # owner asks for it (BAXY_TRACE_WORDS=1), keeps the whole row, as every row was until now.
    TRACE_FACTS = frozenset((
        "t", "stage", "ms", "cache_n", "prompt_n", "prompt_ms", "predicted_n", "predicted_ms", "prompt_tokens",
        "prefix_n", "before_ms", "app_ms", "ear_unsure", "doubt", "doubt_of", "kind", "operation", "operations", "code",
        "error", "failure", "call_index", "cleared", "clock", "cut", "echo", "intervene", "kept", "messages", "named",
        "notice", "restored", "round", "saved", "sound_at", "sound_ms", "timed_out", "words", "yielded", "action",
        "lang", "minutes", "exit_code", "restart", "aids", "findings", "early"))
    trace_words = True
    # Revisión a ciegas de PRV1: the name of a row's operation is the one the model wrote for its call, and a name that
    # is no tool of BAXY's (a call written as text, another model through the translator) is the model's own words. A
    # row without words says this of it instead.
    UNLISTED = "(unlisted)"

    def _own_names(self) -> frozenset[str]:
        """Every name of a tool or of an operation that is BAXY's: what the last catalog gave, by both its names."""
        tools = self.tools or (ASK_USER, CONFIRM, CALCULATE)
        return frozenset((CONFIRM_OPERATION, *(tool["function"]["name"] for tool in tools),
                          *self.wire_to_op, *self.wire_to_op.values(), *self.withheld, *self.withheld.values()))

    @classmethod
    def _without_words(cls, row: dict[str, Any], own: Collection[str] | None = None) -> dict[str, Any]:
        kept = {key: value for key, value in row.items() if key in cls.TRACE_FACTS}
        if own is not None:
            for key in ("operation", "doubt_of"):
                if isinstance(kept.get(key), str) and kept[key] not in own:
                    kept[key] = cls.UNLISTED
            if isinstance(kept.get("operations"), (list, tuple)):
                kept["operations"] = [name if name in own else cls.UNLISTED for name in map(str, kept["operations"])]
        if isinstance(kept.get("aids"), (dict, list, tuple, set)):  # which aids, never what they said (as a private turn's row)
            kept["aids"] = sorted(str(aid) for aid in kept["aids"])
        else:
            kept.pop("aids", None)
        if isinstance(kept.get("findings"), list):  # which rules, never what was said nor the fact it was weighed against
            kept["findings"] = [{"rule": finding.get("rule")} for finding in kept["findings"] if isinstance(finding, dict)]
        else:
            kept.pop("findings", None)
        return kept

    def _write_row(self, row: dict[str, Any]) -> None:
        if not self.trace_words:
            row = self._without_words(row, self._own_names())
        holding = self._holding
        if holding is not None and holding[0] == threading.get_ident():
            holding[1].append(row)  # a decision made early: written only if it is used (early.py)
            return
        try:
            line = whole_code_points(json.dumps(row, ensure_ascii=False, default=str))  # a lone surrogate: U+FFFD
            with self._log_lock, self.trace.open("a", encoding="utf-8") as out:
                out.write(line + "\n")
        except OSError:
            pass
