"""Falsos éxitos v3 M4 y la parte de compositor de M5 (cu-v3 r3a/falsos_exitos.md), más el juez de la tanda 1 de uso
real v3 (t1-base): el libro de actos, «completedRequest» como lo pedido, el lugar que nadie observó, el servicio donde
suena, el texto que dejó escrito una misión que no llegó, el estado de la máquina en una conversación que no leyó nada,
el idioma de la persona en el final del tiempo y la plantilla en vez de dos reintentos.

Cada regla con su contracaso: lo que sí se hizo (o se niega) se sigue publicando."""

from __future__ import annotations

import json

from baxy_mind import cu_projection
from baxy_mind import cu_finals
from baxy_mind.visible_defect import compose_visible_defect
from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import weather_facts
from baxy_mind import computer_use_finals
from baxy_mind.semantic import claims


def _step(operation: str, observed: dict, ok: bool = True) -> str:
    return json.dumps({
        "kind": "operation", "operation": operation, "polarity": "success" if ok else "failure",
        "verified": ok, "succeeded": ok, "observed": observed,
    })


def _facts(situation: dict) -> dict:
    return {"situation": json.dumps(situation, ensure_ascii=False)}


# ---------------------------------------------------------------- v3-51: one app.open, «creé una escena»
OBS_REQUEST = "abre obs y agrega una escena nueva que se llame Pruebas"
OBS = {
    "kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 1,
    "steps": [_step("app.open", {"name": "OBS Studio", "alreadyRunning": False})],
    "completedRequest": "Abre OBS y crea una escena nueva llamada Pruebas.",
}


def test_v3_51_a_scene_nobody_created_is_refused():
    reply = "Listo, abrí OBS Studio y creé una nueva escena llamada Pruebas."
    assert compose_visible_defect(reply, "status", OBS_REQUEST, _facts(OBS)) == "unbacked_act"


def test_v3_51_the_open_alone_and_the_denied_scene_are_published():
    for reply in ("Abrí OBS Studio.", "Abrí OBS Studio; la escena no la creé."):
        assert compose_visible_defect(reply, "status", OBS_REQUEST, _facts(OBS)) == "", reply


def test_v3_51_english_twin():
    request = "open obs and add a new scene called Pruebas"
    assert compose_visible_defect(
        "I opened OBS Studio and created the scene Pruebas.", "status", request, _facts(OBS)
    ) == "unbacked_act"
    assert compose_visible_defect("I opened OBS Studio.", "status", request, _facts(OBS)) == ""
    assert compose_visible_defect(
        "I opened OBS Studio, but I didn't create the scene.", "status", request, _facts(OBS)
    ) == ""


def test_two_verified_operations_each_back_their_act():
    situation = {
        "kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
        "steps": [
            _step("app.open", {"name": "Calculadora", "alreadyRunning": False}),
            # Ronda 22 (r18 t1-c13): reachedState true is a folder that already existed, which backs no «creé»; the
            # folder made here is reachedState false.
            _step("filesystem.create.directory", {"name": "facturas octubre", "reachedState": False}),
        ],
        "completedRequest": "Abre la calculadora y crea la carpeta facturas octubre.",
    }
    assert compose_visible_defect(
        "Abrí la Calculadora y creé la carpeta «facturas octubre».", "status", "abre la calcu y crea la carpeta",
        _facts(situation),
    ) == ""
    existed = json.loads(json.dumps(situation))
    existed["steps"][1] = _step("filesystem.create.directory", {"name": "facturas octubre", "reachedState": True})
    assert compose_visible_defect(
        "Abrí la Calculadora y creé la carpeta «facturas octubre».", "status", "abre la calcu y crea la carpeta",
        _facts(existed),
    ) == "unbacked_act"


def test_the_request_travels_as_requested_not_as_a_fact():
    payload = compose_payload._compose_situation_payload(OBS, "es", OBS_REQUEST)
    assert "completedRequest" not in payload
    assert payload["requested"] == "Abre OBS y crea una escena nueva llamada Pruebas."


# ---------------------------------------------------------------- t1-c13: a folder created, told as opened
CREATED = {
    "kind": "operation", "operation": "filesystem.create.directory", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {"resourceId": "fs_1", "name": "facturas octubre", "kind": "directory", "size": 0},
}


def test_t1_c13_created_folder_is_not_told_as_opened():
    request = "crea una carpeta en el escritorio que se llame facturas octubre"
    assert compose_visible_defect(
        "Abrí la carpeta «facturas octubre» en el escritorio.", "status", request, _facts(CREATED)
    ) == "unbacked_act"
    assert compose_visible_defect(
        "Creé la carpeta «facturas octubre» en el escritorio.", "status", request, _facts(CREATED)
    ) == ""


# ---------------------------------------------------------------- t-file-1: a path only the request held
SAVED = {
    "kind": "operation", "operation": "filesystem.write.text", "polarity": "success", "verified": True,
    "succeeded": True, "observed": {"resourceId": "fs_2", "name": "baxy-nota1.txt", "reachedState": False},
}
SAVE_REQUEST = "guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3"


def test_t_file_1_a_path_from_the_request_is_refused():
    assert compose_visible_defect(
        "He guardado el texto en Documentos/baxy-prueba-v3/baxy-nota1.txt.", "status", SAVE_REQUEST, _facts(SAVED)
    ) == "unobserved_place"
    assert compose_visible_defect(
        "Guardé el texto en la carpeta baxy-prueba-v3.", "status", SAVE_REQUEST, _facts(SAVED)
    ) == "unobserved_place"


def test_t_file_1_the_observed_name_is_published():
    assert compose_visible_defect("Guardé «baxy-nota1.txt».", "status", SAVE_REQUEST, _facts(SAVED)) == ""


def test_an_observed_path_may_be_said():
    situation = json.loads(json.dumps(SAVED))
    situation["observed"]["path"] = "D:\\Perfil\\Documentos\\baxy-prueba-v3\\baxy-nota1.txt"
    assert compose_visible_defect(
        "Guardé el texto en Documentos/baxy-prueba-v3/baxy-nota1.txt.", "status", SAVE_REQUEST, _facts(situation)
    ) == ""


# ---------------------------------------------------------------- v3-17 turn 3: a mission with no step
def _mission(observed: dict, *, succeeded: bool = True) -> dict:
    return {
        "kind": "operation", "operation": "mission.computer.use", "polarity": "success" if succeeded else "failure",
        "verified": succeeded, "succeeded": succeeded, "observed": observed,
    }


def test_v3_17_a_copy_no_step_made_is_refused():
    situation = _mission({
        "goal": "guardar la imagen como copia en esa misma carpeta", "application": "Fotos", "reached": True,
        "steps": [], "satisfiedBy": "model_evidence", "window": {"title": "Fotos"},
    })
    assert compose_visible_defect(
        "Copié la imagen a la misma carpeta.", "status", "guárdala como copia en esa misma carpeta",
        _facts(situation),
    ) == "unbacked_act"


def test_a_mission_backs_the_acts_of_its_steps():
    situation = _mission({
        "goal": "ir a pantalla", "application": "Configuración", "reached": True, "satisfiedBy": "model_evidence",
        "steps": [{"step": 1, "operation": "input.visible.click", "label": "Pantalla", "ok": True, "changed": True}],
        "window": {"title": "Configuración"},
    })
    assert compose_visible_defect(
        "Entré a «Pantalla» en Configuración.", "status", "anda a pantalla", _facts(situation)
    ) == ""


def test_a_strong_arrival_backs_the_goals_own_verb():
    situation = _mission({
        "goal": "crear una escena Pruebas", "application": "OBS", "reached": True,
        "satisfiedBy": "title:Pruebas", "steps": [], "window": {"title": "OBS"},
    })
    assert compose_visible_defect("Creé la escena «Pruebas».", "status", "crea la escena", _facts(situation)) == ""


# ---------------------------------------------------------------- t-form-2: the text a failed mission left typed
FORM = _mission({
    "goal": "reemplazar casa por hogar", "application": "Bloc de notas", "reached": False,
    "stoppedBy": "computer_use_no_step_visible",
    "steps": [
        {"step": 1, "operation": "input.text.type", "text": "casa", "ok": True},
        {"step": 2, "operation": "input.text.type", "text": "hogar", "ok": True},
    ],
    "window": {"title": "Bloc de notas"},
}, succeeded=False)


def test_t_form_2_a_failure_that_hides_the_typed_text_is_refused():
    assert compose_visible_defect(
        "No pude hacerlo en «Bloc de notas»: no vi en la pantalla un control con el que seguir.", "error",
        "reemplazá casa por hogar", _facts(FORM),
    ) == "unstated_effect"


def test_t_form_2_the_floor_says_the_typed_text():
    sentence = cu_finals.floor_sentence(FORM["observed"], False, False)
    assert sentence.endswith("; antes de parar escribí «casa» y «hogar».")
    assert compose_visible_defect(sentence, "error", "reemplazá casa por hogar", _facts(FORM)) == ""
    english = cu_finals.floor_sentence(FORM["observed"], True, False)
    assert english.endswith("; before stopping I typed «casa» and «hogar».")


def test_a_failure_that_typed_nothing_owes_no_text():
    observed = dict(FORM["observed"], steps=[])
    assert cu_finals.floor_sentence(observed, False, False) == (
        "No pude hacerlo en «Bloc de notas»: no vi en la pantalla un control con el que seguir."
    )


def test_the_steps_done_carry_the_typed_text():
    seen = cu_projection.project_seen(FORM["observed"] | {"steps": [
        {"step": 1, "operation": "input.text.type", "text": "casa", "ok": True},
    ]}, "es")
    assert seen["stepsDone"] == ["escribió «casa»"]


# ---------------------------------------------------------------- t1-c01 / t1-c07: the service where it plays
def _played(operation: str, provider: str | None) -> dict:
    observed = {"title": "Idealism - Snowfall", "playbackStatus": "playing", "query": "lo-fi"}
    if provider:
        observed["provider"] = provider
    return {
        "kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
        "observed": observed,
    }


def test_t1_c07_a_song_put_on_without_its_service_is_refused():
    situation = _played("media.play.query", "spotify")
    assert compose_visible_defect(
        "Ahora se está reproduciendo «Idealism - Snowfall».", "status", "pon lo-fi en spotify", _facts(situation)
    ) == "missing_place"
    assert compose_visible_defect(
        "Está sonando «Idealism - Snowfall» en Spotify.", "status", "pon lo-fi en spotify", _facts(situation)
    ) == ""


def test_the_template_names_the_service():
    situation = _played("media.play.query", "spotify")
    payload = compose_payload._compose_situation_payload(situation, "es", "pon lo-fi en spotify")
    assert deterministic_finals._deterministic_final(situation, payload, "pon lo-fi en spotify", "es") == (
        "Está sonando «Idealism - Snowfall» en Spotify."
    )
    youtube = _played("media.play.youtube", None)
    payload = compose_payload._compose_situation_payload(youtube, "en", "play it on youtube")
    assert deterministic_finals._deterministic_final(youtube, payload, "play it on youtube", "en") == (
        "Now playing «Idealism - Snowfall» on YouTube."
    )


def test_a_mute_names_no_service():
    situation = {
        "kind": "operation", "operation": "audio.mute", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"muted": True, "level": 40},
    }
    assert not computer_use_finals._unnamed_service("Silencié el sonido.", situation)


# ---------------------------------------------------------------- v3-61: a conversation states no machine state
def test_v3_61_a_conversation_does_not_state_the_pcs_records():
    facts = {"situation": json.dumps({"kind": "conversation"})}
    reply = (
        "En la configuración actual de seguridad de Windows no hay un registro específico de cuándo se realizó el "
        "último escaneo de antivirus."
    )
    assert compose_visible_defect(reply, "conversation", "cuándo fue el último examen de virus", facts) == (
        "unobserved_machine_state"
    )


def test_a_conversation_may_explain_where_to_look():
    facts = {"situation": json.dumps({"kind": "conversation"})}
    reply = "La fecha del último análisis se ve en Seguridad de Windows, en Protección antivirus y contra amenazas."
    assert compose_visible_defect(reply, "conversation", "cuándo fue el último examen de virus", facts) == ""


# ---------------------------------------------------------------- t1-c06: an English weather final in English
def test_t1_c06_the_english_forecast_says_its_sky_in_english():
    day = {"condition": "mayormente despejado", "minC": 7.1, "maxC": 20, "rainProbabilityPercent": 0}
    said = weather_facts._forecast_day_said(day, True)
    assert "mayormente" not in said and said.startswith("mostly clear")
    assert weather_facts._forecast_day_said(day, False).startswith("mayormente despejado")
    assert weather_facts._weekday_said("sábado", True) == "Saturday"


# ---------------------------------------------------------------- the reader
def test_the_reader_reads_only_acts_told_as_done():
    assert [word for word, _ in claims.claimed_acts("¿Quieres que la cree?")] == []
    assert [word for word, _ in claims.claimed_acts("No la he creado.")] == []
    assert [word for word, _ in claims.claimed_acts("Escribí «abrí la puerta».")] == ["escribí"]
    assert sorted(next(iter(lemmas)) for _, lemmas in claims.claimed_acts("Te he programado un aviso.")) == [
        "programar"
    ]


def test_template_suffices_is_data():
    assert claims.template_suffices("unbacked_act")
    assert claims.template_suffices("missing_name", "media.control")
    assert not claims.template_suffices("internal_code")


def test_template_suffices_leaves_the_other_reads_their_own_repairs():
    # Revisión adversarial: missing_name / missing_state / the older extra_claim vetoes of an inventory, a scope limit
    # or a weather read keep their own repairs; the shortcut is the book's defects and what plays.
    assert not claims.template_suffices("missing_name", "window.list")
    assert not claims.template_suffices("missing_state", "audio.volume.adjust")
    assert not claims.template_suffices("extra_claim", "media.control")


# ---------------------------------------------------------------- revisión adversarial: true finals are published
def _verified(operation: str, observed: dict) -> dict:
    return {
        "kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
        "observed": observed,
    }


def test_browser_control_backs_the_act_of_its_action():
    # m122: «close_all» closes tabs, not only «mover la página»; another action does not back closing.
    closed = _verified("browser.control", {"action": "close_all", "closedTabs": 3, "tabCount": 1})
    said = "cierra todas las pestañas"
    assert compose_visible_defect("Cerré 3 pestañas; queda una abierta.", "status", said, _facts(closed)) == ""
    back = _verified("browser.control", {"action": "back", "observedState": "navigated_back"})
    assert compose_visible_defect("Volví a la página anterior.", "status", "atrás", _facts(back)) == ""
    assert compose_visible_defect("Cerré la pestaña.", "status", "atrás", _facts(back)) == "unbacked_act"


def test_an_observed_fact_backs_its_act():
    # m120: message.draft with clientOpened true says it opened the client; with it false it may not.
    draft = {"channel": "whatsapp", "displayName": "Tere", "text": "llego en diez", "draftVisible": True,
             "sent": False}
    said = "déjale escrito a Tere en whatsapp que llego en diez"
    final = "Abrí WhatsApp y dejé escrito «llego en diez» en el chat con Tere, sin enviarlo."
    opened = _verified("message.draft", draft | {"clientOpened": True})
    assert compose_visible_defect(final, "status", said, _facts(opened)) == ""
    already = _verified("message.draft", draft | {"clientOpened": False})
    assert compose_visible_defect(final, "status", said, _facts(already)) == "unbacked_act"


def test_a_mission_that_failed_with_only_its_reason_is_not_judged_by_the_book():
    # m101: a mission that failed with no step but its reason (effect uncertain or not) is told by the failure
    # vetoes, as a single failed operation is.
    uncertain = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
                 "reason": {"kind": "operation", "operation": "media.play.youtube", "polarity": "failure",
                            "verified": False, "succeeded": False, "effectUncertain": True}}
    assert computer_use_finals._act_ledger(uncertain) is None
    failed = dict(uncertain, reason={"kind": "operation", "operation": "app.open", "polarity": "failure",
                                     "verified": False, "succeeded": False, "error": "app_not_found"})
    assert computer_use_finals._act_ledger(failed) is None
    # With a step done, the failed reason backs nothing and the step's act is still the only one backed.
    stepped = dict(failed, stepCount=1, steps=[_step("app.open", {"name": "Calculadora"})])
    assert claims.unbacked_act("Abrí la Calculadora.", computer_use_finals._act_ledger(stepped)) == ""
    assert claims.unbacked_act("Abrí la Calculadora y creé la nota.", computer_use_finals._act_ledger(stepped)) == "creé"


def test_a_single_read_is_left_to_the_read_only_check():
    # m153: a change told over a read is reversed_result (the payload check), not the book's label.
    tasks = _verified("task.list", {"tasks": [], "count": 0})
    assert computer_use_finals._act_ledger(tasks) is None


def test_auxiliaries_and_pro_verbs_tell_no_act_of_their_own():
    for reply in (
        "Abrí OBS Studio; he tenido que esperar un poco.",
        "He estado esperando y ya abrí OBS Studio.",
        "Listo, he conseguido abrir OBS Studio.",
        "Lo he logrado: abrí OBS Studio.",
        "Listo, lo hice: abrí OBS Studio.",
    ):
        assert compose_visible_defect(reply, "status", OBS_REQUEST, _facts(OBS)) == "", reply
    # The infinitive after the auxiliary is the act told, and it is still judged.
    for reply in ("Abrí OBS Studio y he conseguido crear la escena.", "Abrí OBS Studio y logré crear la escena."):
        assert compose_visible_defect(reply, "status", OBS_REQUEST, _facts(OBS)) == "unbacked_act", reply
    volume = _verified("audio.volume", {"level": 40})
    assert compose_visible_defect("Hecho, lo hice, volumen en 40.", "status", "volumen a 40", _facts(volume)) == ""


def test_v3_51_the_act_told_without_the_first_person_is_refused():
    for reply in (
        "Listo, abrí OBS Studio; la escena Pruebas quedó creada.",
        "Abrí OBS Studio y se creó la escena Pruebas.",
        "Abrí OBS Studio y te dejé creada la escena Pruebas.",
    ):
        assert compose_visible_defect(reply, "status", OBS_REQUEST, _facts(OBS)) == "unbacked_act", reply
    for reply in (
        "Abrí OBS Studio; la escena no quedó creada.",
        "Abrí OBS Studio, pero no se creó la escena.",
        "Abrí OBS Studio, pero no sé si se creó la escena.",
    ):
        assert compose_visible_defect(reply, "status", OBS_REQUEST, _facts(OBS)) == "", reply
    # A failure explains what happened in the third person; it is not read there (tanda 6 «…se presionó antes…»).
    assert claims.unbacked_act("La nota se guardó antes de tiempo.", {"abrir"}, third_person=False) == ""
    assert claims.unbacked_act("La nota se guardó antes de tiempo.", {"abrir"}) == "se guardó"
    # The world's events are told in the third person too (D-w08-t2 «el del 27 de septiembre ya se jugó»).
    assert claims.unbacked_act("El partido ya se jugó; la tienda quedó cerrada.", {"buscar"}) == ""
    assert claims.unbacked_act("Te dejé abierta la página.", {"buscar"}) == "dejé abierta"


def test_a_conversation_may_say_how_to_do_it_on_the_persons_pc():
    facts = {"situation": json.dumps({"kind": "conversation"})}
    for reply, asked in (
        ("En tu PC hay que abrir Configuración y luego Personalización.", "cómo cambio el color"),
        ("Si en tu equipo no aparece la opción, busca «Colores» en Inicio.", "cómo cambio el color"),
        ("Sí, en tu Windows tienes que ir a Configuración > Hora e idioma.", "cómo cambio la hora"),
        ("On your PC there is a Colors page under Settings.", "how do I change the colors"),
    ):
        assert compose_visible_defect(reply, "conversation", asked, facts) == "", reply
    assert compose_visible_defect(
        "En tu PC el modo oscuro está activado.", "conversation", "tengo el modo oscuro?", facts
    ) == "unobserved_machine_state"


def test_a_unit_is_not_a_place():
    # D-s048: «8.1 µg/m³» over an air quality read fell as unobserved_place.
    assert claims.named_places("The air quality index is 48 with a PM2.5 level of 8.1 µg/m³.") == []
    assert claims.named_places("Sopla a 20 km/h y/o más.") == []
    assert claims.named_places("Lo guardé en Documentos/baxy-prueba-v3/nota.txt.") == [
        "Documentos", "baxy-prueba-v3", "nota.txt"
    ]


# ---------------------------------------------------------------- v3-27 r7: «he abierto … y copiado …»
KEYBOARD = {
    "kind": "operation", "operation": "input.keyboard.open", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"ok": True, "effectObserved": True, "action": "keyboard",
                 "authority": "windows_osk_process_window_visible_postread"},
}
CHARMAP_REQUEST = "abre el mapa de caracteres y copia el simbolo del euro"


def test_v3_27_a_participle_joined_to_the_perfect_is_an_act_told():
    # Live r7: the retry «Abrí … y copié …» died on unbacked_act and the third draft passed with the same claim in the
    # perfect, after a single input.keyboard.open.
    reply = "He abierto el mapa de caracteres y copiado el símbolo del euro."
    assert compose_visible_defect(reply, "status", CHARMAP_REQUEST, _facts(KEYBOARD)) == "unbacked_act"
    assert [word for word, _ in claims.claimed_acts(reply)] == ["he abierto", "y copiado"]


def test_v3_27_contracase_what_the_operation_backs_or_is_denied_is_published():
    assert compose_visible_defect("He abierto el teclado en pantalla.", "status", CHARMAP_REQUEST, _facts(KEYBOARD)) == ""
    assert [word for word, _ in claims.claimed_acts("He abierto la app y el estado es bueno.")] == ["he abierto"]
    assert claims.claimed_acts("No he abierto ni copiado nada.") == []
    joined = "He abierto la carpeta, creado el archivo y guardado el texto."
    assert [next(iter(lemmas)) for _, lemmas in claims.claimed_acts(joined)] == ["abrir", "crear", "guardar"]


def test_v3_27_a_participle_that_agrees_with_a_noun_describes_it_and_an_auxiliary_tells_its_infinitive():
    # Review r7: a participle that agrees with a noun after the perfect («la carpeta, ordenada por fecha») is no act,
    # and «y conseguido copiar» tells the copy, as «he conseguido copiar» does.
    assert [next(iter(lemmas)) for _, lemmas in claims.claimed_acts("He abierto la carpeta Descargas, ordenada por fecha.")] == ["abrir"]
    assert [next(iter(lemmas)) for _, lemmas in claims.claimed_acts("Ya he abierto la ventana, cerrada antes por error.")] == ["abrir"]
    assert [next(iter(lemmas)) for _, lemmas in claims.claimed_acts("He abierto Paint y conseguido copiar la imagen.")] == ["abrir", "copiar"]
