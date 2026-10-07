"""Ronda 18 (2026-10-07): the question's own options and states answer it (v2-c5 «decime si el modo es claro u oscuro»
→ «El modo es Oscuro.» was refused as unanswered_question), and a confirmed send is told in BAXY's own preterite from
the mission's goal (v2-c6 «sí» → «Envié «prueba BAXY C6» a Ron92.» was refused as ungrounded_word)."""

import json

from baxy_mind import computer_use, llm
from baxy_mind.semantic.normalize import fold

# Copied verbatim from cu-universal-evidencia compose_audit.jsonl: v2-c5's situation, v2-c6's payload seen (its
# situation was cut at 2048 characters in the audit).
C5 = json.loads(r'''{"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,"observed":{"goal":"ir a personalizacion; luego ir a colores; y responder: decime si el modo es claro u oscuro","application":"Configuración","reached":true,"stepCount":3,"steps":[{"step":1,"operation":"app.open","source":"procedure","subgoal":0,"appId":"Configuración","ok":true,"alreadyRunning":true,"changed":true},{"step":2,"operation":"input.visible.click","source":"procedure","subgoal":0,"label":"Personalización","index":11,"ok":true,"cascadeStage":"uia","surfaceChanged":false,"absentOrDisabled":false,"selected":true,"toggled":false,"name":"Personalización","kind":"ListItem","changed":true},{"step":3,"operation":"input.visible.click","source":"procedure","subgoal":1,"label":"Colores","ok":true,"cascadeStage":"uia_surface","surfaceChanged":true,"absentOrDisabled":false,"selected":false,"toggled":false,"name":"Colores","kind":"ListItem","changed":true}],"window":{"title":"Configuración","process":"SystemSettings","requested":true,"rect":{"x":58,"y":0,"w":1282,"h":1002},"focused":{"kind":"ComboBox","name":"Elige tu modo"}},"joined":false,"elapsedMs":3741,"modelMs":0,"authority":"shell_loop_over_uia_ocr_postread","subgoals":[{"goal":"ir a personalizacion","application":"Configuración","reached":true,"stepCount":2,"satisfiedBy":"control:personalizacion:current"},{"goal":"ir a colores","application":"Configuración","reached":true,"stepCount":1,"satisfiedBy":"page:colores"}],"satisfiedBy":"page:colores","screen":{"title":"Configuración","values":[{"name":"Personalización","state":"selected"},{"name":"Oscuro","state":"selected"},{"name":"Manual","state":"selected"}],"lines":["Buscar una opción de configuración","Colores",">","Elige tu modo","Cambiar los colores que aparecen en Windows y en las aplicaciones","Efectos de transparencia"]}}}''')
C6_SEEN = json.loads(r'''{"goal": "ir a ron92; luego escribir prueba BAXY C6; luego enviar", "reached": true, "stepsDone": ["clic en «@Ron92»", "escribió el texto", "tecla enter"], "windowTitle": "@Ron92 - Discord", "joined": false, "application": "Discord", "satisfiedBy": "stepDone:input.key.press:enter", "screen": {"title": "@Ron92 - Discord", "values": [{"name": "Ron92 (mensaje directo), Inactivo", "value": "https://discord.com/channels/@me/788990433829060618"}, {"name": "@Ron92", "value": "https://discord.com/channels/@me/788990433829060618"}, {"name": "Ayuda", "value": "https://support.discord.com/"}, {"name": "Mensajes directos", "state": "selected"}, {"name": "Amigos", "value": "https://discord.com/channels/@me"}, {"name": "Nitro", "value": "https://discord.com/store"}, {"name": "Tienda", "value": "https://discord.com/shop"}, {"name": "Misiones", "value": "https://discord.com/quest-home"}], "numbers": ["@Ron92", "Juegos y Software, carpeta , 7 menciones sin leer Juegos y Software", "7 menciones, Marvel Rivals", "Servidor de prueba , te amo <3", "Ron92", "Ron92 (mensaje directo), Inactivo"]}, "subgoals": [{"goal": "ir a ron92", "application": "Discord", "reached": true}, {"goal": "escribir prueba BAXY C6", "application": "Discord", "reached": true}, {"goal": "enviar", "application": "Discord", "reached": true}]}''')

BLUETOOTH = {
    "kind": "operation",
    "operation": "mission.computer.use",
    "polarity": "success",
    "verified": True,
    "succeeded": True,
    "observed": {
        "goal": "ir a bluetooth y dispositivos; y responder: decime si el Bluetooth está activado",
        "reached": True,
        "application": "Configuración",
        "window": {"title": "Configuración"},
        "steps": [{"operation": "input.visible.click", "ok": True, "label": "Bluetooth y dispositivos"}],
        "screen": {
            "title": "Configuración",
            "values": [{"name": "Bluetooth y dispositivos", "state": "selected"}, {"name": "Bluetooth", "state": "on"}],
            "lines": ["Bluetooth", "Activado", "Agregar dispositivo", "Ver más dispositivos"],
        },
    },
}


def test_the_option_the_window_shows_answers_the_question() -> None:
    assert llm._computer_use_final_defect("El modo es Oscuro.", C5) == ""
    assert llm._computer_use_final_defect("El modo que aparece seleccionado es Oscuro.", C5) == ""


def test_a_draft_without_the_answer_is_still_refused() -> None:
    assert llm._computer_use_final_defect("Llegué a Colores en Configuración.", C5) == "unanswered_question"
    assert llm._computer_use_final_defect("Fui a Colores para ver si el modo es claro u oscuro.", C5) == (
        "unanswered_question"
    )
    assert llm._computer_use_final_defect("El modo puede ser claro u oscuro.", C5) == "unanswered_question"


def test_a_yes_no_question_is_answered_by_its_state() -> None:
    assert llm._computer_use_final_defect("Sí, el Bluetooth está activado.", BLUETOOTH) == ""
    assert llm._computer_use_final_defect("Sí, está activado.", BLUETOOTH) == ""
    assert llm._computer_use_final_defect("Llegué a Bluetooth y dispositivos.", BLUETOOTH) == "unanswered_question"
    assert llm._computer_use_final_defect("Fui a Bluetooth para ver si está activado.", BLUETOOTH) == (
        "unanswered_question"
    )


def test_a_yes_no_state_shown_only_as_the_switch_state_answers() -> None:
    switch_only = json.loads(json.dumps(BLUETOOTH))
    switch_only["observed"]["screen"]["lines"] = ["Bluetooth", "Agregar dispositivo"]
    assert llm._computer_use_final_defect("Sí, el Bluetooth está activado.", switch_only) == ""
    assert llm._computer_use_final_defect("Llegué a Bluetooth y dispositivos.", switch_only) == "unanswered_question"


def test_a_confirmed_send_is_told_from_the_mission_goal() -> None:
    seen = C6_SEEN
    assert computer_use.ungrounded_word(fold("Envié «prueba BAXY C6» a Ron92."), seen, "sí") is None
    assert computer_use.ungrounded_word(fold("Escribí «prueba BAXY C6» y lo envié a Ron92."), seen, "sí") is None
    assert computer_use.ungrounded_word(fold("Bloqueé a Ron92."), seen, "sí") == "bloquee"
    unsent = {**seen, "goal": "ir a ron92; luego escribir prueba BAXY C6", "subgoals": seen["subgoals"][:2]}
    assert computer_use.ungrounded_word(fold("Envié «prueba BAXY C6» a Ron92."), unsent, "sí") == "envie"
