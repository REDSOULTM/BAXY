"""Tests del splitter multi-intent (investigación 7).

"abrí Spotify y bajá el volumen" = 2 acciones. Un 4B causal colapsa el
multi-intent; lo partimos con regex ANTES del LLM. Conservador: no parte un "y"
entre sustantivos ni nombres propios.
"""
from __future__ import annotations

import os
import unittest

from gemma4_agent.routing.command_splitter import (
    split_command, has_back_reference, plan_clauses,
    extract_click_target, is_key_name, extract_write_payload,
    extract_nav_target, extract_message_to, parse_calc_action,
    extract_app_action,
)


class MessageToExtractTest(unittest.TestCase):
    """extract_message_to: 'escribe/mandale a <contacto> en <app> [y dile/que]
    <mensaje>' -> (contacto, mensaje). Para el macro de envío-de-mensaje en apps de
    chat (Discord/Slack). Validación en vivo 2026-05-25."""

    def test_contact_and_body(self):
        h = "@Ron92 - Discord"
        self.assertEqual(
            extract_message_to("escribe a cbayeah en discord y dile que haces", app_hint=h),
            ("cbayeah", "que haces"))   # "que" se preserva (cambia el sentido si se quita)
        self.assertEqual(
            extract_message_to("mandale a juan en discord: nos vemos", app_hint=h),
            ("juan", "nos vemos"))
        self.assertEqual(
            extract_message_to("decile a GordoFriki que llego tarde", app_hint=h),
            ("GordoFriki", "que llego tarde"))
        self.assertEqual(
            extract_message_to("mandale a cbayeah en discord hola", app_hint=h),
            ("cbayeah", "hola"))

    def test_no_body_opens_chat(self):
        # solo "escribe a X en discord" -> (contacto, "") = abrir el chat, sin enviar.
        self.assertEqual(
            extract_message_to("escribe a cbayeah en discord", app_hint="@Ron92 - Discord"),
            ("cbayeah", ""))

    def test_app_hint_does_not_strip_contact(self):
        # bug 2026-05-25: si el título en foco YA es el del contacto ("@CbaYeah -
        # Discord"), el peeling de app no debe borrar el contacto. Solo pela la APP
        # (último segmento), no cualquier token del título.
        self.assertEqual(
            extract_message_to("escribe a cbayeah en discord", app_hint="@CbaYeah - Discord"),
            ("cbayeah", ""))

    def test_app_write_is_not_a_message(self):
        # CRÍTICO: un tecleo-en-app ("escribí 2+2" en la calc, "escribí hola mundo")
        # NO debe parsearse como mensaje-a-contacto (mandaría texto a un "contacto"
        # inexistente). La preposición de destinatario "a <X>" es obligatoria para
        # "escribe/write"; mandale/decile sí implican destinatario.
        for q in ("escribí 2+2", "escribe 5 por 5 y apretá igual",
                  "escribí hola mundo", "escribe el informe final"):
            self.assertIsNone(extract_message_to(q, app_hint="Calculadora"), msg=q)

    def test_recipient_verbs_imply_destinatario(self):
        # "mandale/decile X" sí es mensaje aunque no repita "a".
        self.assertEqual(extract_message_to("mandale a juan hola"), ("juan", "hola"))
        self.assertEqual(extract_message_to("decile a Ana que ya voy"),
                         ("Ana", "que ya voy"))

    def test_non_message_returns_none(self):
        for q in ("que hora es", "abre discord", "andá al canal general"):
            self.assertIsNone(extract_message_to(q), msg=q)

    def test_first_person_recipient_is_not_a_send(self):
        # mission-eval 2026-06-10: "tell me X" = pedirle al asistente, NO enviar a
        # un contacto "me". El destinatario de 1ª persona -> None (no mensajería).
        for q in ("tell me the time", "tell me a joke", "decime la hora",
                  "dis-moi l'heure"):
            self.assertIsNone(extract_message_to(q), msg=q)

    def test_conjunction_pronoun_is_not_a_contact(self):
        # mission-eval 2026-06-10: "decile QUE ya le mandé el mensaje" -> el 'que'
        # es conjunción, no un contacto -> abría WhatsApp con contacto "que".
        for q in ("decile que ya le mandé el mensaje", "dile que sí",
                  "dis-lui que je suis là"):
            self.assertIsNone(extract_message_to(q), msg=q)
        # pero CON un nombre real sigue siendo envío:
        self.assertEqual(extract_message_to("decile a GordoFriki que sí"),
                         ("GordoFriki", "que sí"))

    def test_bare_send_verb_without_recipient_is_none(self):
        # BUG REPORTADO EN VIVO (2026-05-30): "manda un mensaje por wsp" (SIN
        # destinatario) -> el stem PELADO `manda` hacía implies_recipient=True, no
        # exigía "a", y el PASO 3 agarraba el artículo "un" como contacto ->
        # "Abrí el chat con un" / el 4B alucinaba +34 123456. Un imperativo de
        # envío PELADO (sin clítico dativo -le ni "a <quién>") NO es un mensaje-a-
        # alguien -> None -> el LLM pregunta a quién (honesto, no inventa).
        for q in ("manda un mensaje por wsp",
                  "mandá un wsp",
                  "manda un mensaje por whatsapp",
                  "envia un mensaje",
                  "escribe un mensaje de whatsapp",
                  "decí hola",
                  "schick eine nachricht",   # de pelado
                  "envoie un message",       # fr pelado
                  "invia un messaggio"):     # it pelado
            self.assertIsNone(extract_message_to(q), msg=q)

    def test_clitic_or_explicit_a_still_extracts(self):
        # No-regresión: el clítico dativo -le (mandaLE/deciLE/escribiLE) o el "a
        # <quién>" explícito SIGUEN extrayendo destinatario.
        self.assertEqual(extract_message_to("manda a pedro nos vemos")[0], "pedro")
        self.assertEqual(extract_message_to("escribile a mama que ya voy"),
                         ("mama", "que ya voy"))
        self.assertEqual(extract_message_to("tell juan hi"), ("juan", "hi"))

    def test_reply_verbs_still_none(self):
        # respondele/contestale tienen "-le" pero su destinatario es el ÚLTIMO que
        # escribió (reply-a-último) -> este extractor debe devolver None.
        for q in ("respondele que sí", "contestale que ya voy"):
            self.assertIsNone(extract_message_to(q), msg=q)

    def test_body_does_not_drag_app_when_que_precedes_en_app(self):
        # BUG REAL (log voz turno 7, 2026-06-03): "escríbele a Juan que voy en un
        # momento en Discord" -> el PASO 1-fallback "que" partía dejando body="que
        # voy ... EN DISCORD" (el "en app" no se pelaba del body, solo del contacto)
        # -> se tipeaba el nombre de la app dentro del mensaje. El "en <app>" residual
        # se pela del body SOLO si es una app de mensajería conocida.
        self.assertEqual(
            extract_message_to("escríbele a Juan que voy en un momento en Discord"),
            ("Juan", "que voy en un momento"))
        self.assertEqual(
            extract_message_to("escribile a Ana en WhatsApp que ya salgo"),
            ("Ana", "que ya salgo"))

    def test_body_preserves_real_en_phrase_not_app(self):
        # ANTI-REGRESIÓN del fix anterior: un "en <lugar/tiempo>" legítimo al final
        # del cuerpo NO debe pelarse (solo apps de mensajería conocidas). MEDIDO: el
        # pelado ciego rompía "te espero en casa" -> "te espero".
        c, b = extract_message_to("decile a Juan que te espero en casa")
        self.assertEqual(c, "Juan")
        self.assertIn("en casa", b)
        c2, b2 = extract_message_to("mandale a mama que llego en 10 minutos")
        self.assertEqual(c2, "mama")
        self.assertIn("10 minutos", b2)


class AppActionExtractTest(unittest.TestCase):
    """extract_app_action: ACCESIBILIDAD — "escribí/hacé X en app Y", "andá a Y y
    escribí X", screenshot -> orquestador computer_use. MEDIDO (2026-05-31): ~1/10
    de estos pedidos llegaba a computer_use; el resto charlaba/mis-ruteaba."""
    def setUp(self):
        from ..routing.command_splitter import extract_app_action
        self.A = extract_app_action

    def test_act_in_app_needs_verify(self):
        # "escribí X en <app>" -> act_in_app con verify_app=True (el caller confirma
        # por estado del SO que <app> es ventana real).
        for q in ("escribí 'sigo' en Slack",
                  "escribí hola mundo en el bloc de notas",
                  "poné reunión a las 5 en notepad",
                  "type hello world in notepad",
                  "escribí gracias en Discord"):
            r = self.A(q)
            self.assertIsNotNone(r, msg=q)
            self.assertTrue(r["verify_app"], msg=q)
            self.assertEqual(r["goal"], q)

    def test_in_app_act_app_first(self):
        # "en <app> escribí X" (app primero) tambien -> verify_app.
        r = self.A("en Slack escribí quién eres")
        self.assertIsNotNone(r)
        self.assertEqual(r["pattern"], "in_app_act")
        self.assertTrue(r["verify_app"])
        self.assertIn("slack", (r["app_hint"] or "").lower())

    def test_a_preposition_app_target(self):
        # Caso REAL: "escribile sigue a Slack" (con "a", no "en").
        # Dispara act_in_app (verify_app) -> el OS-check decide (Slack abierto
        # -> cu; 'a juan' -> no es ventana -> cae a whatsapp).
        r = self.A("escribile sigue a Slack")
        self.assertIsNotNone(r)
        self.assertTrue(r["verify_app"])

    def test_nav_action_no_verify(self):
        # "andá a <app> y <acción>" -> nav_action, sin OS-check (gramática basta).
        for q in ("andá a Slack y escribí continuá",
                  "andá a notepad y escribí mi nombre",
                  "abrí el word y guardá"):
            r = self.A(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["pattern"], "nav_action", msg=q)
            self.assertFalse(r["verify_app"], msg=q)

    def test_screenshot(self):
        for q in ("sacá un screenshot", "captura de pantalla", "tomá una captura de pantalla"):
            r = self.A(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["pattern"], "screen", msg=q)
            self.assertFalse(r["verify_app"], msg=q)

    def test_does_not_fire_on_non_app_actions(self):
        # Controles: mensajería, notes, audio, web, preguntas, abrir-simple. NO deben
        # disparar a NIVEL DE GRAMÁTICA (mandale/anotá/subí/buscá/qué/abrí-solo).
        for q in ("mandale a juan que ya voy", "anotá comprar pan en mi lista",
                  "recordame comprar pan mañana", "subí el volumen",
                  "buscá noticias de hoy", "qué hora es", "abrí spotify",
                  "reproducí algo en spotify", "cómo está el clima", "gracias"):
            self.assertIsNone(self.A(q), msg=q)

    def test_nav_action_excludes_media_messaging_chains(self):
        # "andá a YouTube y reproducí X" (=media) y "abrí WhatsApp y mandale a juan"
        # (=whatsapp) NO deben ir a cu: reproducir/mandar no están en el set nav.
        self.assertIsNone(self.A("andá a YouTube y reproducí música"))
        self.assertIsNone(self.A("abrí WhatsApp y mandale a juan hola"))

    def test_accented_imperative_escribele(self):
        # BUG real (voz): "escríbele/escríbe" (acento en la 1ra i) debe
        # matchear. Antes 'escrib[íie]' lo perdía -> el comando iba a notes_tasks.
        self.assertIsNotNone(self.A("Abre el bloque de notas y escríbele Hola Mundo"))
        self.assertIsNotNone(self.A("escríbele hola en notepad"))


class ParseTypeActionTest(unittest.TestCase):
    """parse_type_action: extrae (app, payload) para el PLAN DETERMINISTA
    focus_app+type. Evita los planes vacíos / payload-mal del 4B planner (MEDIDO)."""
    def setUp(self):
        from ..routing.command_splitter import parse_type_action
        self.P = parse_type_action

    def test_type_in_app(self):
        for q, app, pay in [
            ("escribí hola mundo en el bloc de notas", "el bloc de notas", "hola mundo"),
            ("escríbele hola en notepad", "notepad", "hola"),
            ("type hello world in notepad", "notepad", "hello world"),
            ("escribí gracias en Discord", "Discord", "gracias"),
        ]:
            r = self.P(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["app"], app, msg=q)
            self.assertEqual(r["payload"], pay, msg=q)

    def test_prefers_en_over_a_locator(self):
        # "poné R a las 5 en notepad": el 'en' final manda, NO el 'a' de 'a las 5'.
        r = self.P("poné reunión a las 5 en el bloc de notas")
        self.assertEqual(r["app"], "el bloc de notas")
        self.assertEqual(r["payload"], "reunión a las 5")

    def test_a_locator_fallback(self):
        # Sin 'en', usa 'a' (caso real "escribile sigue a Slack").
        r = self.P("escribile sigue a Slack")
        self.assertEqual(r["app"], "Slack")
        self.assertEqual(r["payload"], "sigue")

    def test_in_app_first(self):
        r = self.P("en notepad escribí mi nombre")
        self.assertEqual(r["app"], "notepad")
        self.assertEqual(r["payload"], "mi nombre")

    def test_nav_then_type(self):
        for q, pay in [("andá a Slack y escribí continuá", "continuá"),
                       ("abrí la calculadora y escribí 5+5", "5+5"),
                       ("Abre el bloque de notas y escríbele Hola Mundo", "Hola Mundo")]:
            r = self.P(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["payload"], pay, msg=q)

    def test_non_type_returns_none(self):
        for q in ("mandale a juan que ya voy", "anotá comprar pan en mi lista",
                  "subí el volumen", "sacá un screenshot", "qué hora es",
                  "abrí spotify", "hacé clic en guardar"):
            self.assertIsNone(self.P(q), msg=q)


class ParseKeypressActionTest(unittest.TestCase):
    """parse_keypress_action: extrae (app, key) para el PLAN DETERMINISTA
    focus_app+keypress. MEDIDO en vivo (2026-06-01): "en la calculadora apretá el 5"
    caía a cu(goal genérico) -> el 4B planner devolvía "no pude planificar la acción"
    para un keypress trivial. La TECLA debe ser inequívoca (dígito/tecla-nombrada/letra
    sola) -> NO le roba a click_button ('apretá enviar') ni a media ('tocá una canción').
    """
    def setUp(self):
        from ..routing.command_splitter import parse_keypress_action
        self.P = parse_keypress_action

    def test_in_app_first(self):
        for q, app, key in [
            ("en la calculadora apretá el 5", "la calculadora", "5"),
            ("en Discord apretá enter", "Discord", "enter"),
            ("en la calc tocá el 7", "la calc", "7"),
            ("en notepad apretá la a", "notepad", "a"),
            ("en el teclado apretá espacio", "el teclado", "space"),
            ("en Discord tocá f5", "Discord", "f5"),
        ]:
            r = self.P(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["app"], app, msg=q)
            self.assertEqual(r["key"], key, msg=q)

    def test_action_first(self):
        for q, app, key in [
            ("apretá el 5 en la calculadora", "la calculadora", "5"),
            ("presioná enter en Discord", "Discord", "enter"),
            ("pulsá escape en el navegador", "el navegador", "escape"),
            ("apretá arriba en el juego", "el juego", "up"),
        ]:
            r = self.P(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["app"], app, msg=q)
            self.assertEqual(r["key"], key, msg=q)

    def test_multilingual_verbs(self):
        for q, key in [("press 5 in the calculator", "5"),
                       ("tap tab in the browser", "tab"),
                       ("toca intro en discord", "enter")]:   # intro -> enter
            r = self.P(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["key"], key, msg=q)

    def test_key_synonyms_canonicalize(self):
        # intro/retorno->enter, espacio->space, supr->delete, arriba->up.
        for q, key in [("en notepad apretá intro", "enter"),
                       ("en notepad apretá espacio", "space"),
                       ("en notepad apretá supr", "delete")]:
            self.assertEqual(self.P(q)["key"], key, msg=q)

    def test_precision_does_not_steal(self):
        # 'enviar'/'guardar'=BOTÓN (click_button); 'una canción'=PLAY (media);
        # 'escribí hola'=TYPE; 'sumá 2+2'=CALC; '25'=ambiguo (2 dígitos); 'clic'=button.
        for q in ("apretá enviar en WhatsApp",
                  "tocá una canción en Spotify",
                  "escribí hola en notepad",
                  "en la calculadora sumá 2+2",
                  "apretá el botón de guardar en Word",
                  "apretá 25 en la calculadora",
                  "hacé clic en guardar en Word",
                  "en spotify tocá play",
                  "abrí la calculadora",
                  "reproducí música en spotify"):
            self.assertIsNone(self.P(q), msg=q)

    def test_empty_and_degenerate_safe(self):
        for q in ("", "   ", "apretá", "en la calculadora apretá", None):
            self.assertIsNone(self.P(q), msg=repr(q))


class DependentOpenTest(unittest.TestCase):
    """is_dependent_open: "instalá VLC Y ABRILO" -> 'abrilo' abre el referente (VLC)
    de la cláusula previa. ETAPA 2 encadenamiento dependiente (2026-05-31)."""
    def setUp(self):
        from ..routing.command_splitter import is_dependent_open
        self.D = is_dependent_open

    def test_fires_on_bare_open_clitic(self):
        for q in ("abrilo", "abrila", "abrilos", "abrir", "lanzalo", "ejecutalo",
                  "corrélo", "abrí eso", "open it", "run it", "launch it"):
            self.assertTrue(self.D(q), msg=q)

    def test_not_on_explicit_target(self):
        # con target propio o sin verbo de apertura -> NO es dependiente
        for q in ("abrí el bloc de notas", "escribí hola", "poné rock",
                  "instalá VLC", "abrí Spotify", "buscá gatos", "subí el volumen"):
            self.assertFalse(self.D(q), msg=q)


class IsBareInappNavTest(unittest.TestCase):
    """is_bare_inapp_nav: nav PELADA a un destino DENTRO de una app, para el
    chain-context ("abrí Discord y andá al canal X" -> clause2 navega en la app).
    Excluye 'abrí'=app-open y los verbos de tipeo/click/envío (2026-05-31)."""
    def setUp(self):
        from ..routing.command_splitter import is_bare_inapp_nav
        self.N = is_bare_inapp_nav

    def test_fires_on_bare_nav(self):
        for q in ("andá al canal general", "entrá al canal de música",
                  "ve a la playlist de rock", "navegá a la pestaña de tareas",
                  "andá a youtube", "go to the general channel", "entrá a configuración"):
            self.assertTrue(self.N(q), msg=q)

    def test_not_on_open_type_click_send(self):
        # 'abrí' (app-open ambiguo), tipeo, click, envío, charla -> NO es nav in-app
        for q in ("abrí Discord", "abrí Spotify", "escribí hola", "clickeá Guardar",
                  "poné rock", "mandale a juan que ya voy", "qué hora es",
                  "subí el volumen", "buscá gatos", "ve el partido"):
            self.assertFalse(self.N(q), msg=q)


class ReadScreenRequestTest(unittest.TestCase):
    """is_read_screen_request: pedir LEER/MOSTRAR la pantalla ('mostrame las tareas')
    para el chain-context-read (tras navegar a una página, leer su contenido por visión,
    no la tool local). FLAGSHIP: 'entrá a Canvas y mostrame las tareas'."""
    def setUp(self):
        from ..routing.command_splitter import is_read_screen_request
        self.R = is_read_screen_request

    def test_fires_on_read_show(self):
        for q in ("mostrame las tareas", "mostrame las tareas que debo hacer",
                  "leeme lo que dice", "ve las tareas", "mirá qué hay en la pantalla",
                  "fijate las notificaciones", "show me the tasks", "leé el mensaje"):
            self.assertTrue(self.R(q), msg=q)

    def test_not_on_other(self):
        # 'decime' (ambiguo), nav ('ve a X'), tipeo, play, controles -> NO leer-pantalla
        for q in ("decime qué hora es", "ve a youtube", "andá al canal general",
                  "poné rock", "escribí hola", "subí el volumen", "buscá gatos"):
            self.assertFalse(self.R(q), msg=q)


class NavExcludesAmbiguousTest(unittest.TestCase):
    """ETAPA 2 (2026-05-31): "abrí Spotify y poné rock" NO debe ser nav_action
    (poné=play=media, no tipear). Solo verbos de tipeo/click inequívocos."""
    def setUp(self):
        from ..routing.command_splitter import extract_app_action
        self.A = extract_app_action

    def test_pone_play_not_nav(self):
        # poné/colocá/metá ambiguos -> NO nav_action -> split -> media
        self.assertIsNone(self.A("abrí Spotify y poné rock"))
        self.assertIsNone(self.A("abrí YouTube y poné música relajante"))

    def test_unambiguous_type_still_nav(self):
        for q in ("abrí el bloc de notas y escribí hola",
                  "andá a Word y escribí mi nombre",
                  "abrí el word y guardá"):
            r = self.A(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r["pattern"], "nav_action", msg=q)


class AppOpenTest(unittest.TestCase):
    """extract_app_open: "abrí la calculadora" -> 'calculadora' (open pelado de app).
    MEDIDO físico (2026-05-31): el 4B NO ruteaba calculadora/discord a app.open
    consistentemente. El caller intenta app.open; la tool resuelve o cae al flujo."""
    def setUp(self):
        from ..routing.command_splitter import extract_app_open
        self.E = extract_app_open

    def test_extracts_app_name(self):
        for q, app in [("abrí la calculadora", "calculadora"), ("abrí discord", "discord"),
                       ("abrí el bloc de notas", "bloc de notas"), ("abrí spotify", "spotify"),
                       ("open calculator", "calculator"), ("lanzá steam", "steam")]:
            self.assertEqual(self.E(q), app, msg=q)

    def test_excludes_non_apps(self):
        # chat (in-app), carpeta (filesystem), URL (browser), página, no-open-verb
        for q in ("abrí el chat de juan", "abrí la carpeta descargas", "abrí instagram.com",
                  "abrí la página de google", "escribí hola", "subí el volumen",
                  "qué hora es", "abrí el canal general"):
            self.assertIsNone(self.E(q), msg=q)

    def test_nav_prep_word_boundary_preserves_app_name(self):
        # BUG real (eval run3): "open Notepad and type X" -> _AA_PREP incluía n[oa]
        # sin word-boundary y comía el "No" de "Notepad" -> app="tepad" ->
        # focus_app("tepad") fallaba. El \b de cierre evita consumir parte de la app.
        from ..routing.command_splitter import parse_type_action
        r = parse_type_action("open Notepad and type my todo list")
        self.assertIsNotNone(r)
        self.assertEqual(r["app"].lower(), "notepad")
        r2 = parse_type_action("abrí Notepad y escribí hola")
        self.assertEqual(r2["app"].lower(), "notepad")
        # no-regresión: la preposición real ("a"/"en") sigue consumiéndose bien.
        self.assertEqual(parse_type_action("andá a Discord y escribí hola")["app"], "Discord")

    def test_execute_command_is_not_app_open(self):
        # BUG real (eval dataset run2, 2026-06-04): "ejecuta pytest" matcheaba
        # _APP_OPEN_VERB (incluía ejecut/run/start) -> app.open("pytest") -> fallback
        # web abría pytest.org y MENTÍA "Listo, abrí pytest". "ejecutar X" es un
        # COMANDO (terminal/developer), no abrir-app -> debe devolver None y llegar
        # al router+LLM. 42 comandos del dataset estaban siendo hijackeados.
        for q in ("ejecuta pytest", "ejecuta python --version", "ejecuta npm install",
                  "ejecuta git status", "run pytest", "start the server",
                  "ejecutá los tests", "run the build"):
            self.assertIsNone(self.E(q), msg=q)
        # No-regresión: abrir-app legítimo sigue funcionando.
        self.assertEqual(self.E("abrí discord"), "discord")
        self.assertEqual(self.E("lanzá Chrome"), "Chrome")


class NavTargetExtractTest(unittest.TestCase):
    """extract_nav_target: 'entrá/andá a [app] al [servidor/canal] X' -> X (control
    a clickear por Name UIA dentro de la app abierta). Validación Discord 2026-05-25."""

    def test_extracts_target_with_app_hint(self):
        # el caso real: pelar la app del frente para dejar el target.
        self.assertEqual(
            extract_nav_target("entra a Discord al servidor Servidor de prueba",
                               app_hint="Amigos - Discord"),
            "Servidor de prueba")

    def test_extracts_channel(self):
        # pela el contenedor "canal" -> solo el nombre del control.
        self.assertEqual(extract_nav_target("entra al canal general"), "general")
        self.assertEqual(extract_nav_target("andá al servidor VALORANT"), "VALORANT")

    def test_extracts_chat_target_varied_phrasings(self):
        # Bug reportado 2026-05-25: "Ve a discord y pon el chat de X" debe dejar X
        # (pelar "y pon el chat de"); "al chat de X" debe pelar el "de" final.
        h = "@Ron92 - Discord"
        self.assertEqual(
            extract_nav_target("Ve a discord y pon el chat de cbayeah", app_hint=h),
            "cbayeah")
        self.assertEqual(
            extract_nav_target("andá a discord al chat de GordoFriki", app_hint=h),
            "GordoFriki")
        self.assertEqual(
            extract_nav_target("ve a discord y abrí el chat de juan", app_hint=h),
            "juan")
        self.assertEqual(extract_nav_target("entrá al canal de soporte"), "soporte")

    def test_non_nav_returns_none(self):
        for q in ("que hora es", "contame un chiste", "mutea el audio"):
            self.assertIsNone(extract_nav_target(q), msg=q)


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
        # MAX_CLAUSES=3 (techo VERIFICADO: cadenas 2-3 pasos medidas estables).
        # hasta 3 cláusulas SÍ parte; más -> no confiar (ruido/lista). El soporte
        # del código llega a más, pero NO se afirma >3 sin medición estable.
        from gemma4_agent.routing.command_splitter import MAX_CLAUSES
        self.assertEqual(MAX_CLAUSES, 3)
        # exactamente 3 -> parte (misión válida de 3 pasos)
        cmd3 = "abre A y abre B y abre C"
        self.assertEqual(len(split_command(cmd3)), 3)
        # 4 -> excede el cap -> no parte (status quo, el LLM ve todo)
        cmd4 = "abre A y abre B y abre C y abre D"
        self.assertEqual(len(split_command(cmd4)), 1)

    def test_empty_and_none_safe(self):
        self.assertEqual(split_command(""), [""])
        self.assertEqual(split_command("   "), ["   "])

    def test_chain_of_3_steps(self):
        # VERIFICADO: cadenas de hasta 3 pasos parten (verbos de click/escritura
        # en _IMPERATIVE). Cadenas de >3 no se afirman (cap=3): el código las
        # soporta pero no se midieron estables -> no se parten por ahora.
        self.assertEqual(
            len(split_command("abrí la calculadora y escribí 2+2 y apretá enter")), 3)
        self.assertEqual(
            len(split_command("abrí el bloc de notas, escribí hola y apretá enter")), 3)
        # >3 cláusulas: no parte (cap conservador en lo medido)
        self.assertEqual(
            len(split_command("abrí Spotify y bajá el volumen y poné música y cerrá la ventana")), 1)

    def test_noise_does_not_split_as_chain(self):
        # listas/nombres no son misiones aunque tengan muchos "y".
        self.assertEqual(len(split_command("sal y pimienta y azúcar y harina y huevos y leche")), 1)
        self.assertEqual(len(split_command("Tom y Jerry")), 1)

    def test_bare_nav_to_app_prefix_does_not_split(self):
        # Bug medido 2026-05-25: "Ve a discord y pon el chat de cbayeah" se partía en
        # ["Ve a discord","pon el chat de cbayeah"]; la 2da cláusula AISLADA perdía
        # "discord" y el router la mandaba a WhatsApp (whatsapp=0.58) -> abría el chat
        # en la app equivocada. Un "ir/entrar a <app>" PURO es prefijo de contexto, no
        # una acción aparte: NO se parte, para que la navegación-en-app vea la app.
        for cmd in (
            "Ve a discord y pon el chat de cbayeah",
            "andá a discord y mandale hola a juan",
            "entrá a Spotify y poné rock",
        ):
            self.assertEqual(len(split_command(cmd)), 1, cmd)

    def test_open_app_still_chains(self):
        # PERO "abrí <app>" SÍ es una acción que encadena (abrir != navegar): no se
        # debe colapsar. _PURE_NAV_VERB excluye 'abrí'/'abre'/'open' a propósito.
        self.assertEqual(len(split_command("abrí Spotify y bajá el volumen")), 2)
        self.assertEqual(
            len(split_command("abrí la calculadora y escribí 2+2 y apretá enter")), 3)
        self.assertEqual(len(split_command("abre el bloc de notas y escribí hola")), 2)

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

    def test_periphrastic_click_extracts_label(self):
        # BUG real #click_boton (log voz 2026-06-04): "hace click en el boton rojo"
        # NO matcheaba -> el 4B respondía cualquier cosa ("Soy Gemma"). La perífrasis
        # "hacé/haz/make/do + click" ahora se reconoce (lookahead exige que el
        # sustantivo sea click, sin sobre-captura).
        cases = {
            "hace click en el boton rojo": "boton rojo",
            "hacer click en aceptar": "aceptar",
            "haz click en Enviar": "Enviar",
            "haz un click en OK": "OK",
            "make a click on OK": "OK",
            "do click on Cancel": "Cancel",
        }
        for inp, exp in cases.items():
            self.assertEqual(extract_click_target(inp), exp, msg=inp)

    def test_periphrastic_does_not_overcapture(self):
        # El lookahead evita que "hacé/haz X" no-click matchee como click.
        for inp in ("hacé la tarea", "haz que suene rock", "hace una foto",
                    "haz un resumen", "hacé un café"):
            self.assertIsNone(extract_click_target(inp), msg=inp)

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


from gemma4_agent.routing.command_splitter import _ensure_action_centroids

_HAS_ENCODER = _ensure_action_centroids()


@unittest.skipUnless(_HAS_ENCODER, "encoder multilingüe no disponible")
class MultilingualSplitTest(unittest.TestCase):
    """CAPA 2: parte multi-intent en CUALQUIER idioma (no solo español), por
    embeddings. Sustantivos coordinados ('Tom and Jerry') NO parten. Principio
    universal del proyecto: nada de regex es-only."""

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


class ParseCalcActionTest(unittest.TestCase):
    """parse_calc_action: 'suma 2+2 en la calculadora' -> {'expr': '2+2'} (plan
    determinista focus_app(calc)+type+enter). MEDIDO 2026-05-31: el 4B tipeaba sin
    enfocar la Calc -> verifier 'type failed' -> 4 reintentos. Estructural+aritmético."""

    def test_arithmetic_in_calculator(self):
        cases = {
            "Suma 2 más 2 en la Calculadora": "2+2",
            "Suma dos más dos en la Calculadora": "2+2",
            "gemma Suma 2 más 2 en la Calculadora": "2+2",
            "en la calculadora hacé 5 por 3": "5*3",
            "calculá 100 dividido 4 con la calculadora": "100/4",
            "multiplicá 6 por 7 en la calc": "6*7",
        }
        for q, exp in cases.items():
            got = parse_calc_action(q)
            self.assertIsNotNone(got, msg=q)
            self.assertEqual(got.get("expr"), exp, msg=q)

    def test_none_when_not_calc_arithmetic(self):
        # sin app calc, o sin aritmética pura -> None (no se hijackea)
        for q in ("abrí la calculadora", "suma 2+2",                # falta uno de los dos
                  "anotá la reunión en mi lista", "poné hola en notepad",
                  "qué hora es", ""):
            self.assertIsNone(parse_calc_action(q), msg=q)


class DisfluencyStripTest(unittest.TestCase):
    """split_command quita muletillas/disfluencias iniciales (ruido del STT) antes de
    partir. MEDIDO 2026-05-31: 'Eh, pon una canción' -> ['Eh','pon una canción'] y la
    cláusula 'Eh' generaba reply junk ('listo, cancelo') que se concatenaba."""

    def test_strips_leading_fillers(self):
        self.assertEqual(split_command("Eh, pon una canción en Spotify"),
                         ["pon una canción en Spotify"])
        self.assertEqual(split_command("Dije, cierra WhatsApp"), ["cierra WhatsApp"])
        self.assertEqual(split_command("ah, subí el volumen"), ["subí el volumen"])
        self.assertEqual(split_command("gemma, reproduce el video"),
                         ["reproduce el video"])
        self.assertEqual(split_command("Dale, reanuda lo que estaba viendo."),
                         ["reanuda lo que estaba viendo"])

    def test_does_not_eat_real_word_prefixes(self):
        # 'ahora' NO es 'ah'+'ora'; 'umbral' NO es 'um'+'bral'; 'este'/'a ver' = contenido
        for q in ("ahora pon música", "umbral de 5", "ahí está",
                  "este documento abrilo", "a ver las tareas"):
            self.assertEqual(split_command(q), [q], msg=q)


class ExtractAppActionNavInAppTest(unittest.TestCase):
    """nav-en-app: 've a <dest> en <app>' -> pattern 'nav_in_app' -> cu(focus_app+open).
    MEDIDO en vivo 2026-05-31: 'gemma Ve a Cotele en Discord' no llegaba a computer_use
    (ve=nav sin 2da acción -> extract_app_action=None -> 'No alcancé a completar')."""

    def test_routes_nav_in_named_app(self):
        cases = {
            "ve a Cotele en Discord": "Discord",
            "gemma Ve a Cotele en Discord": "Discord",          # wake-word
            "entrá al canal general en Discord": "Discord",     # prep 'al'
            "abrí la playlist rock en Spotify": "Spotify",      # sin prep
            "open the chat with Ana in Telegram": "Telegram",   # inglés
        }
        for q, app in cases.items():
            r = extract_app_action(q)
            self.assertIsNotNone(r, msg=q)
            self.assertEqual(r.get("pattern"), "nav_in_app", msg=q)
            self.assertEqual(r.get("app_hint"), app, msg=q)
            self.assertTrue(r.get("verify_app"), msg=q)   # gate por estado del SO

    def test_browsers_and_plain_nav_not_hijacked(self):
        # navegadores tienen tool dedicada; nav sin 'en <app>' va a browser.open
        for q in ("ve a github", "ve a la página de pivigames",
                  "ve a las noticias en Opera", "ve a noticias en el navegador"):
            r = extract_app_action(q)
            self.assertNotEqual(
                (r or {}).get("pattern"), "nav_in_app", msg=q)

    def test_type_and_open_patterns_unchanged(self):
        # no regresar los patrones existentes
        self.assertEqual(extract_app_action("escribí hola en notepad")["pattern"], "act_in_app")
        self.assertEqual(extract_app_action("en notepad escribí hola")["pattern"], "in_app_act")
        self.assertIsNone(extract_app_action("abrí Spotify"))          # app-open puro
        self.assertIsNone(extract_app_action("gemma reproduce el video"))

    def test_media_provider_not_hijacked_by_act_in_app(self):
        # "poné <título> en <provider>" es PLAY (media tiene tool dedicada), NO
        # una misión GUI dentro de la app. MEDIDO 2026-06-12: act_in_app se lo
        # comía -> cu focus_app fallaba (14.5s) y media nunca corría.
        for q in ("Pone Bohemian Rhapsody en Spotify",
                  "poné rock en spotify",
                  "pon stranger things en Netflix",
                  "poné la película en Disney+",
                  "pon mi playlist en YouTube Music",
                  "en spotify poné jazz"):
            self.assertIsNone(extract_app_action(q), msg=q)

    def test_media_provider_guard_no_overreach(self):
        # apps NO-provider siguen ruteando a computer_use como siempre
        self.assertEqual(extract_app_action("poné hola en notepad")["pattern"], "act_in_app")
        self.assertEqual(extract_app_action("escribile sigo en Slack")["pattern"], "act_in_app")


if __name__ == "__main__":
    unittest.main()
