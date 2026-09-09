from __future__ import annotations

from time import perf_counter

import pytest

from baxy_mind.effect_intent import (
    CompoundEffectContract,
    build_application_catalog_index,
    build_game_catalog_index,
    compound_retrieval_clauses,
    compound_retrieval_operation_hints,
    conversation_only_content_request,
    explicit_negative_constraint,
    effect_request_is_authoritative,
    enumerated_note_dependency_order,
    known_unsupported_effect_request,
    unsupported_effect_demonstration_request,
    unsupported_live_machine_query,
    operation_domain_is_grounded,
    operation_identity_is_a_near_miss,
    resolve_explicit_clarification,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
    resolve_application_catalog_app_id,
    resolve_game_catalog_app_id,
    unresolved_compound_contract,
)


@pytest.mark.parametrize("prefix", ["Si, ", "Sí, ", "Yes, ", "Okay, "])
@pytest.mark.parametrize("user_text,operations", [
    ("abre steam", ("app.open",)),
    ("open Orion", ("app.open",)),
    ("dime la hora", ("system.time",)),
])
def test_affirmative_preface_preserves_the_independent_request(
    prefix: str, user_text: str, operations: tuple[str, ...],
) -> None:
    # UI263 supplied the first literal. The cross-language/domain variants are
    # constructed regression controls, not fresh human acceptance evidence.
    available = ("app.open", "system.time")
    apps = ("Steam", "Orion")
    expected = resolve_explicit_effects(user_text, available, apps)
    observed = resolve_explicit_effects(prefix + user_text, available, apps)

    assert expected is not None and expected.operations == operations
    assert observed is not None and observed.operations == expected.operations
    assert observed.evidence == expected.evidence
    assert unresolved_compound_contract(
        prefix + user_text, available, apps, resolved_intent=observed,
    ) is None


@pytest.mark.parametrize("prefix", ["Si, ", "Sí, ", "Yes, ", "Okay, "])
def test_affirmative_preface_preserves_mixed_positive_and_negative_constraints(prefix: str) -> None:
    available = ("app.open", "system.time")
    apps = ("Steam", "Orion")
    user_text = "no abras Steam y abre Orion"
    # The bounded resolver defers this whole compound to semantic selection.
    # A discourse preface must preserve that contract and its prohibition,
    # not turn the positive suffix into a standalone execution request.
    assert resolve_explicit_effects(user_text, available, apps) is None
    assert resolve_explicit_effects(prefix + user_text, available, apps) is None
    expected = unresolved_compound_contract(user_text, available, apps)
    assert unresolved_compound_contract(prefix + user_text, available, apps) == expected


@pytest.mark.parametrize("prefix", ["Si, ", "Sí, ", "Yes, ", "Okay, ", "Hola, "])
def test_authenticated_app_argument_uses_the_shared_request_envelope(prefix: str) -> None:
    assert resolve_application_catalog_app_id(prefix + "open Orion", ("Orion",)) == "Orion"
    assert resolve_application_catalog_app_id(prefix + "open Orion", ()) is None


@pytest.mark.parametrize("user_text", [
    "Si", "Sí", "Yes", "Okay", "Si, hazlo", "Yes, do it",
    "Si Steam no responde, abre Orion", "If Steam is closed, open Orion",
    "Si, no abras Steam", "Yes, do not open Orion",
    'Explica la frase "Si, abre Steam"', 'Explain "Yes, open Orion"',
])
def test_affirmative_preface_does_not_supply_missing_or_forbidden_authority(user_text: str) -> None:
    assert resolve_explicit_effects(user_text, ("app.open",), ("Steam", "Orion")) is None


@pytest.mark.parametrize("user_text", [
    "Si Steam no responde, abre Orion", "If Steam is closed, open Orion",
    'Escribe "Si, abre Steam"', 'Type "Yes, open Orion"',
    "Si,", "Yes,", "Sí", "Yes",
])
def test_affirmative_preface_preserves_conditions_and_literal_content(user_text: str) -> None:
    from baxy_mind.effect_intent import _fold, _strip_request_envelope

    folded = _fold(user_text)
    assert _strip_request_envelope(folded) == folded


@pytest.mark.parametrize("text", [
    "no subas el volumen", "no silencies el audio", "no bajes el brillo",
    "nunca cierres spotify", "no pongas música", "no abras el navegador",
    "don't open chrome", "do not close this window", "never delete that file",
    "Hola, no me bajes el volumen", "no apagues el PC", "no busques el archivo",
    "no lances otra aplicación", "no muevas esa carpeta",
])
def test_standalone_prohibition_reuses_action_grammar(text: str) -> None:
    assert explicit_negative_constraint(text)


@pytest.mark.parametrize("text", [
    "no entiendo", "no sé qué es Steam", "no funciona el audio",
    "nunca he usado Linux", "no tienes que saberlo", "no todas las fotos",
    "no me molesta, poné música", "don't open Chrome; explain what a browser is",
    "no abras Chrome y abre Firefox", "no abras Chrome, explica qué es",
    "no abras Chrome pero explica qué es", "no cierres?", "turn up the volume",
    "no me subes el volumen", "I don't know what a browser is",
    "no abras Chrome y no cierres Spotify", "no toques el archivo",
])
def test_prohibition_formatter_does_not_take_other_speech_acts(text: str) -> None:
    assert not explicit_negative_constraint(text)


@pytest.mark.parametrize("text", [
    "turn up the volume", "turn the volume down", "turn volume up please",
    "raise the volume", "lower volume", "increase the volume", "decrease volume",
    "sube el volumen", "baja el volumen",
])
def test_relative_volume_clarifies_only_the_missing_amount(text: str) -> None:
    intent = resolve_explicit_clarification_intent(text, ("audio.volume.adjust",))
    assert intent is not None
    assert intent.operations == ("audio.volume.adjust",)
    assert intent.missing_fields == ("amount",)


@pytest.mark.parametrize("text", [
    "turn up the volume by 10%", "turn the volume down by 5%",
    "turn off the volume", "turn up the brightness", "don't turn up the volume",
    "turn up the volume on my phone", "no subas el volumen",
])
def test_relative_volume_clarification_preserves_complete_and_other_requests(text: str) -> None:
    assert resolve_explicit_clarification_intent(text, ("audio.volume.adjust",)) is None


@pytest.mark.parametrize("text", [
    "Ajusta el volumen.", "Set the volume.", "Set the volume, por favor.",
    "Pon el volumen.", "Fija el volumen del sistema", "change the volume please",
    "Adjust volume", "establece el volumen", "deja el volumen", "ponme el volumen",
])
def test_absolute_volume_clarifies_missing_level_without_observing(text: str) -> None:
    available = ("audio.volume", "audio.volume.adjust", "audio.status")
    intent = resolve_explicit_clarification_intent(text, available)
    assert intent is not None
    assert intent.operations == ("audio.volume",)
    assert intent.missing_fields == ("level",)
    assert resolve_explicit_clarification_intent(text, ("audio.status",)) is None


@pytest.mark.parametrize("text", [
    "Ajusta el volumen al 80%.", "Set the volume to seventy five percent.",
    "¿A qué volumen está?", "no ajustes el volumen", "Ajusta el volumen de ventas.",
    "Ajusta el volumen de datos", "Set the volume on my phone", "Ajusta el volumen de Spotify",
    "Ajusta el volumen y el brillo", "Pon el volumen, no, mejor déjalo",
    "Explícame cómo se ajusta el volumen", "Ajusta el volumen; abre Paint",
])
def test_missing_level_does_not_replace_complete_or_different_requests(text: str) -> None:
    assert resolve_explicit_clarification_intent(text, ("audio.volume",)) is None


@pytest.mark.parametrize("user_text", [
    "Ponlo a 100 ahora", "fijalo al 40%", "ajustala a 55", "dejalo al 12",
    "Set it to 45", "put it at 80 percent", "leave it at 20 please",
])
def test_numeric_volume_reference_inherits_only_a_known_prior_audio_request(user_text: str) -> None:
    assert operation_domain_is_grounded(
        user_text, "audio.volume", previous_user_text="decime cuánto volumen hay",
        available_operations=("audio.status", "audio.volume", "audio.volume.adjust", "system.time"),
    ) is True
    assert operation_domain_is_grounded(user_text, "audio.volume") is False


@pytest.mark.parametrize("text", [
    "Abre una aplicación.", "Open an application.", "Launch an app.",
    "Inicia un programa", "Open a program", "Abre la app",
    "¿Puedes abrir una aplicación?", "Could you open an app?",
    "Hola Baxy, abre una aplicación, por favor.", "Please open an application.",
    "Open una aplicación, por favor.", "Lanza una app.",
])
def test_generic_application_request_clarifies_target_without_launching(text: str) -> None:
    intent = resolve_explicit_clarification_intent(text, {"app.open"})
    assert intent is not None
    assert intent.operations == ("app.open",)
    assert intent.missing_fields == ("application",)
    assert resolve_explicit_clarification_intent(text, {"app.installed"}) is None


@pytest.mark.parametrize("text", [
    "Abre Spotify.", "Open VLC.", "Abre la aplicación Calculadora.",
    "No abras una aplicación.", "Don't open an app.",
    "¿Cómo se abre una aplicación?", "What is an application?",
    "If I open an application, does it use RAM?",
    "Abre una aplicación en mi teléfono.", "Open an app on my phone.",
    "Abre una aplicación y baja el volumen.", "Open an app; mute the speakers.",
    "Abre una aplicación abre Steam", "Abre una aplicación, no, mejor no.",
    "Open an application form.", "Start a program of exercise.",
])
def test_generic_application_clarification_keeps_other_requests_intact(text: str) -> None:
    assert resolve_explicit_clarification_intent(text, {"app.open"}) is None


@pytest.mark.parametrize("user_text,previous", [
    ("Ponlo a 100 ahora", "Dime que hora es"),
    ("Ponlo a 100 ahora", "no subas el volumen"),
    ("Ponlo a 100 ahora", "dime la hora y el volumen"),
    ("Ponlo a 100 ahora", "set the data volume to 20"),
    ("No lo pongas al 100", "mostrame el volumen"),
    ("pon el brillo al 100", "mostrame el volumen"),
    ("ponlo a 100 en otro PC", "mostrame el volumen"),
    ("ponlo a 100 mañana", "mostrame el volumen"),
    ("ponlo a 100 y borra el archivo", "mostrame el volumen"),
    ("set it to 40 frames per second", "show me the volume"),
])
def test_volume_reference_rejects_missing_ambiguous_or_incompatible_antecedent(
    user_text: str, previous: str,
) -> None:
    assert operation_domain_is_grounded(
        user_text, "audio.volume", previous_user_text=previous,
        available_operations=("audio.status", "audio.volume", "audio.volume.adjust", "system.time"),
    ) is False


def test_volume_domain_modifiers_are_invariant_to_clause_punctuation() -> None:
    from baxy_mind.effect_intent import _volume_domain

    for text in (
        "set the volume, por favor.",
        "set the volume; please.",
        "set the volume, por favor.\naclaracion confiable del usuario: al 40%, please.",
    ):
        assert _volume_domain(text)
    for text in (
        "ajusta el volumen, de ventas al 40%",
        "set the volume, of data to 40%",
        "el volumen, de la enciclopedia",
    ):
        assert not _volume_domain(text)


def test_compound_retrieval_clauses_tolerates_voice_punctuation_loss() -> None:
    text = (
        "hazme este chequeo por partes la salud global del sistema "
        "después las copias recuperables después la distribución del teclado "
        "devolviendo cada resultado por separado"
    )

    assert compound_retrieval_clauses(text) == (
        "la salud global del sistema",
        "las copias recuperables",
        "la distribucion del teclado",
    )


def test_compound_retrieval_clauses_does_not_split_temporal_after_of() -> None:
    assert compound_retrieval_clauses("revisa el correo después del almuerzo") == ()


def test_compound_retrieval_operation_hints_cover_voice_report_fragments() -> None:
    text = (
        "hazme este chequeo por partes la salud global del sistema "
        "después las copias recuperables después la distribución del teclado "
        "después text ready para paste"
    )

    assert compound_retrieval_operation_hints(
        text,
        (
            "system.status",
            "backup.list",
            "input.keyboard.status",
            "clipboard.read.text",
        ),
    ) == (
        "system.status",
        "backup.list",
        "input.keyboard.status",
        "clipboard.read.text",
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "hazme este chequeo por partes la salud global del sistema "
            "despues las copias recuperables despues la distribucion del "
            "teclado devolviendo cada resultado por separado",
            ("system.status", "backup.list", "input.keyboard.status"),
        ),
        (
            "go point for point with tasks that remain open, then check, "
            "open pages of the browser, then check, general access to the "
            "network, then check, content of the newly arrived email, then "
            "check, reminders still scheduled, returning each result separately",
            (
                "task.list",
                "browser.tabs.list",
                "network.status",
                "email.latest.read",
                "reminder.list",
            ),
        ),
        (
            "I need a combined report covering the window holding focus, "
            "then, the newly arrived emails contents, then, attached physical "
            "accessories, then, overall system health, then, reminders still "
            "scheduled, returning each result separately",
            (
                "window.active",
                "email.latest.read",
                "peripheral.list",
                "system.status",
                "reminder.list",
            ),
        ),
        (
            "necesito a campaign report de what is playing ahora, despues "
            "check, text ready para paste, returning cada result por separado",
            ("media.status", "clipboard.read.text"),
        ),
        (
            "go point por point con volumen y audio output. Despues check, "
            "open pages del browser. Despues check, physical accessories "
            "conectados. Despues check, private note index. Despues check, "
            "recoverable backup copies. Despues check, content del nullier ID "
            "mail, returning cada result por separado",
            (
                "audio.status",
                "browser.tabs.list",
                "peripheral.list",
                "note.list",
                "backup.list",
                "email.latest.read",
            ),
        ),
        (
            "without skipping ninguno, revisa in order, devices visibles por "
            "bluetooth, despues check, window que holds focus, despues check, "
            "over or layout del sistema, despues check, today's appointments, "
            "despues check, private note index, despues check, text ready para "
            "paste, despues check, wifi link y signal, despues check, over do "
            "avisos, returning cada result por separado",
            (
                "bluetooth.device.list",
                "window.active",
                "system.status",
                "calendar.event.list",
                "note.list",
                "clipboard.read.text",
                "wifi.status",
                "notification.list.due",
            ),
        ),
        (
            "go point for point context ready para paste, despues check, "
            "private note index, despues check, today's appointments, despues "
            "check, over all the alt del sistema, despues check, window que "
            "holds focus, despues check, devices visibles por bluetooth, "
            "despues check, recoverable backup copies, returning cada result "
            "por separado",
            (
                "clipboard.read.text",
                "note.list",
                "calendar.event.list",
                "system.status",
                "window.active",
                "bluetooth.device.list",
                "backup.list",
            ),
        ),
    ],
)
def test_catalog_reports_recover_measured_voice_asr_variants(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected


def test_latest_email_grounding_accepts_asr_plural_without_selecting_it() -> None:
    assert (
        operation_domain_is_grounded(
            "the newly arrived emails contents",
            "email.latest.read",
        )
        is True
    )


def test_grounding_vetoes_asr_domain_collisions() -> None:
    assert (
        operation_domain_is_grounded(
            "quedo en expired note fecaschen todavia han atendido",
            "note.list",
        )
        is False
    )
    assert (
        operation_domain_is_grounded(
            "locate github github desktop y alistalo for install",
            "filesystem.known.search",
        )
        is False
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("donde compra kate middleton la ropa de sus hijos", "filesystem.search"),
        ("donde hay la mayor cantidad de volcanes en la tierra", "filesystem.search"),
        ("cual es la temperatura en barcelona cataluna", "notification.diagnose"),
        ("info on lisa ann please", "task.search"),
    ],
)
def test_public_questions_cannot_gain_local_search_or_alarm_authority(
    text: str,
    operation: str,
) -> None:
    assert operation_domain_is_grounded(text, operation) is False


def test_bare_spanish_temperature_factoid_does_not_force_a_live_lookup() -> None:
    assert (
        resolve_explicit_effects(
            "cual es la temperatura en barcelona cataluna",
            {"web.search", "notification.diagnose"},
        )
        is None
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Busca el archivo informe en Descargas", "filesystem.search"),
        ("Busca Auditoria en mis tareas", "task.search"),
        ("check if alarm is set for six am", "notification.diagnose"),
    ],
)
def test_local_search_and_alarm_status_keep_literal_domain_authority(
    text: str,
    operation: str,
) -> None:
    assert operation_domain_is_grounded(text, operation) is True


def test_expired_note_asr_variant_retains_only_due_notifications() -> None:
    result = resolve_explicit_effects(
        "quedo en expired note fecaschen todavia han atendido",
        {"notification.list.due", "note.list"},
    )

    assert result is not None
    assert result.operations == ("notification.list.due",)


@pytest.mark.parametrize(
    "text",
    [
        "deja Mozilla Firefox preparado en la antesala de instalacion",
        "ubica GitHub, GitHub Desktop y alistalo para instalar",
        "get mozzala.firefox staged for installation",
        "locate github.github desktop and ready it for install",
        "deja Mozilla Firefox tied para installation",
        "locate github github desktop y alistalo for install",
    ],
)
def test_package_prepare_recovers_exact_ids_after_voice_punctuation_loss(
    text: str,
) -> None:
    result = resolve_explicit_effects(text, {"package.install.prepare"})

    assert result is not None
    assert result.operations == ("package.install.prepare",)
    assert result.evidence in {("Mozilla.Firefox",), ("GitHub.GitHubDesktop",)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "ask on the what bluetooth radio can see",
            ("bluetooth.device.list",),
        ),
        ("dame a overview de pagis abiertas en browser", ("browser.tabs.list",)),
        ("dejame a snapchat de how desktop looks", ("capture.screenshot",)),
        (
            "sabe en imagen lo que full display is showing",
            ("capture.screenshot",),
        ),
        (
            "recupera the text fragment que quedo capid",
            ("clipboard.read.text",),
        ),
        (
            "lee el mensaje que era y blast al correo",
            ("email.latest.read",),
        ),
        (
            "a ver si fin de observatory pasis dentro de downloads",
            ("filesystem.known.search",),
        ),
        (
            "as a list the titles recognized por game library",
            ("game.catalog.list",),
        ),
        ("check con que loud estoy typing", ("input.keyboard.status",)),
        ("hay algo sonando", ("media.status",)),
        (
            "AVE Discord avise a Kerry que moved to North Room",
            ("message.recipient.resolve", "message.send"),
        ),
        (
            "el equipo esta llegando bien a la red",
            ("network.status",),
        ),
        (
            "ask kick check del machine general network link",
            ("network.status",),
        ),
        ("quiero si el complete index de local notes", ("note.list",)),
        (
            "ask capture and turn screenwriting into characters",
            ("capture.screenshot", "ocr.read"),
        ),
        (
            "armame a word calle de acuerdos de invierno",
            ("office.document.create",),
        ),
        (
            "review las cosas que pedi bring back Tom Indlater",
            ("reminder.list",),
        ),
        (
            "que habitual sequence y sabe back si repeat",
            ("routine.list",),
        ),
        (
            "encuentras Low Horses en Netflix y arrancala",
            ("streaming.play.named",),
        ),
        ("ponme up to date con Chorsker y Manopen", ("task.list",)),
        (
            "cual aplicacion esta receiving mis keystrokes ahora",
            ("window.active",),
        ),
    ],
)
def test_measured_voice_asr_variants_preserve_catalog_identity(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    "text",
    [
        "ask what bluetooth means",
        "leave Snapchat on the desktop",
        "show the machines",
    ],
)
def test_voice_asr_aliases_do_not_authorize_nearby_literal_requests(text: str) -> None:
    assert (
        resolve_explicit_effects(
            text,
            {
                "bluetooth.device.list",
                "capture.screenshot",
                "routine.list",
            },
        )
        is None
    )


def test_bluetooth_asr_query_is_not_misread_as_incomplete_messaging() -> None:
    text = "ask on the what bluetooth radio can see"

    assert (
        resolve_explicit_clarification_intent(
            text,
            {"message.send", "bluetooth.device.list"},
        )
        is None
    )
    result = resolve_explicit_effects(text, {"bluetooth.device.list"})
    assert result is not None
    assert result.operations == ("bluetooth.device.list",)


@pytest.mark.parametrize(
    "text",
    [
        "Hazel sabera a Elena que el paquete llego",
        "hustle no a Sydney que parcel arrived",
    ],
)
def test_message_asr_without_channel_preserves_clarification_identity(
    text: str,
) -> None:
    result = resolve_explicit_clarification_intent(text, {"message.send"})

    assert result is not None
    assert result.operations == ("message.send",)
    assert result.missing_fields == ("channel",)


def test_curry_recipe_asr_variant_remains_conversation_only() -> None:
    assert (
        conversation_only_content_request(
            "One thing, I small question, dame a currir ese pi para Fagi Down"
        )
        is True
    )


@pytest.mark.parametrize(
    "text",
    [
        (
            "Una cosa, una pequena cuestion, comparar mi interes en "
            "UTF-Cash en Check My Data."
        ),
        ("Oye, una pregunta rapida, Ray Tun Story donde Bluetooth sea Imaginary City."),
    ],
)
def test_conversational_asr_requests_do_not_grant_effect_authority(
    text: str,
) -> None:
    assert conversation_only_content_request(text) is True
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    "text",
    [
        (
            "Please, one quick question, roleplay a conversation between "
            "Nadia and Martin, send nothing."
        ),
        (
            "One thing, a small question, pon en tu ingles la frase instala "
            "and break cuando llegues."
        ),
    ],
)
def test_spoken_content_work_stays_inside_the_conversation(text: str) -> None:
    assert conversation_only_content_request(text) is True
    assert resolve_explicit_effects(text, AVAILABLE) is None


def test_truncated_exhaustive_voice_report_fails_closed() -> None:
    text = (
        "sin omitir ninguno, revisa en este orden, las copias recuperables, "
        "despues, las rutinas personales guardadas, despues, los recordatorios "
        "aun programados, despues, el indice de notas privadas, despues, las "
        "tareas que siguen abiertas, resultado por separado"
    )
    operations = {
        "backup.list",
        "routine.list",
        "reminder.list",
        "note.list",
        "task.list",
    }
    resolved = resolve_explicit_effects(text, operations)

    assert resolved is not None
    contract = unresolved_compound_contract(
        text,
        operations,
        resolved_intent=resolved,
    )
    assert contract == CompoundEffectContract(1, ())


CASES = [
    ("Hola", ()),
    ("Gracias", ()),
    ("No entendí", ()),
    ("¿Qué hora es?", ("system.time",)),
    ("¿Qué fecha es hoy?", ("system.time",)),
    ("¿Cómo está el equipo?", ("system.status",)),
    ("Muéstrame el uso de memoria", ("system.status",)),
    (
        "Lista los procesos que más memoria usan",
        ("system.process.list",),
    ),
    ("¿Cómo está la red?", ("network.status",)),
    ("Haz ping a 127.0.0.1", ("network.ping",)),
    ("¿En qué volumen está el computador?", ("audio.status",)),
    ("Pon el volumen al 8 por ciento", ("audio.volume",)),
    ("Pon la música al 20%", ("audio.volume",)),
    ("Sube el volumen en 2 puntos", ("audio.volume.adjust",)),
    ("Sube la música en 2 puntos", ("audio.volume.adjust",)),
    ("Silencia el audio", ("audio.mute",)),
    ("Mute everything please", ("audio.mute",)),
    ("Silencia todo", ("audio.mute",)),
    ("No silencies todo", ()),
    ("Mute everything on Spotify", ()),
    ("Abre la calculadora", ("app.open",)),
    ("Abre el Bloc de notas", ("app.open",)),
    ("Abre Opera", ("app.open",)),
    (
        "Captura el escritorio, describe esa imagen y lee cada palabra "
        "visible de la misma captura",
        ("capture.screenshot", "vision.describe", "ocr.read"),
    ),
    (
        "Show mis tareas abiertas, captura esa vista y read el texto de la captura",
        ("task.list", "capture.screenshot", "ocr.read"),
    ),
    (
        "Muestra mis tareas abiertas, captura el resultado y lee el texto de la captura",
        ("task.list", "capture.screenshot", "ocr.read"),
    ),
    (
        "Show my notes, capture that view, and read the text from the capture",
        ("note.list", "capture.screenshot", "ocr.read"),
    ),
    (
        "Capture the screen and read every word from that image",
        ("capture.screenshot", "ocr.read"),
    ),
    (
        "Take a screenshot, describe that scene, and read all text from the "
        "same capture",
        ("capture.screenshot", "vision.describe", "ocr.read"),
    ),
    (
        "Lista los procesos, tell me the time, show my open tasks y luego check "
        "system status",
        ("system.process.list", "system.time", "task.list", "system.status"),
    ),
    (
        "Take a screen capture and extract every visible word from that same image",
        ("capture.screenshot", "ocr.read"),
    ),
    (
        "Toma una captura, describe esa escena y lee todo el texto de la misma imagen",
        ("capture.screenshot", "vision.describe", "ocr.read"),
    ),
    (
        "Show the saved notes, capture that result, and extract the text from the capture",
        ("note.list", "capture.screenshot", "ocr.read"),
    ),
    (
        "Obtén una imagen de esta pantalla y describe visualmente esa misma captura",
        ("capture.screenshot", "vision.describe"),
    ),
    (
        "Take an image of this screen and describe that same capture",
        ("capture.screenshot", "vision.describe"),
    ),
    (
        "Muestra mis notas, captura ese resultado y describe lo que aparece en la imagen",
        ("note.list", "capture.screenshot", "vision.describe"),
    ),
    (
        "Show my open tasks, capture that result, and describe what appears in the image",
        ("task.list", "capture.screenshot", "vision.describe"),
    ),
    ("Abre Spotify", ("app.open",)),
    ("¿Está instalada la calculadora?", ("app.installed",)),
    ("¿Qué ventana está activa?", ("window.active",)),
    (
        "Maximiza la ventana activa",
        ("window.active", "window.maximize"),
    ),
    (
        "Minimiza la ventana activa",
        ("window.active", "window.minimize"),
    ),
    ("Escribe literalmente prueba BAXY", ("input.text.type",)),
    ("Selecciona todo", ("input.select.all",)),
    ("Abre el teclado en pantalla", ("input.keyboard.open",)),
    ("Lee el portapapeles", ("clipboard.read.text",)),
    ("qué hay en el portapapeles", ("clipboard.read.text",)),
    ("Pega esto en el bloc de notas", ("clipboard.paste",)),
    ("anota que tengo que comprar pan", ("note.create",)),
    (
        "Sácale una foto de captura a mi pc, ¿qué se ve?",
        ("capture.screenshot", "vision.describe"),
    ),
    ("Copia la selección", ("clipboard.copy",)),
    ("Haz una captura de pantalla", ("capture.screenshot",)),
    ("Lee con OCR la última captura", ()),
    (
        "Crea una nota llamada Auditoría con el contenido prueba",
        ("note.create",),
    ),
    ("Lista mis notas", ("note.list",)),
    ("Busca prueba en mis notas", ("note.search",)),
    ("Crea una tarea llamada Auditoría", ("task.create",)),
    ("Lista mis tareas pendientes", ("task.list",)),
    ("Busca Auditoría en mis tareas", ("task.search",)),
    (
        "Crea un recordatorio llamado Auditoría para mañana a las 9",
        ("reminder.create",),
    ),
    ("Lista mis recordatorios", ("reminder.list",)),
    ("Lista mis rutinas", ("routine.list",)),
    ("Busca OpenAI en la web", ("web.search",)),
    ("Navega a https://example.com/", ("browser.navigate",)),
    (
        "Navega mi sesión de YouTube exactamente a https://www.youtube.com/results?search_query=BAXY",
        ("streaming.navigate",),
    ),
    (
        "Navigate to https://www.netflix.com/browse in my streaming session",
        ("streaming.navigate",),
    ),
    (
        "Navega mi sesión de YouTube a https://www.youtube.com/results?search_query=BAXY "
        "y después busca exactamente OpenAI Codex en la web",
        ("streaming.navigate", "web.search"),
    ),
    (
        "Abre Opera GX y busca en Google: mejores teclados mecánicos 2026",
        ("web.search", "browser.navigate.named"),
    ),
    (
        "Abre calculadora y pega el portapapeles",
        ("app.open", "clipboard.paste"),
    ),
    (
        "Navega Opera a https://example.com/",
        ("browser.navigate.named",),
    ),
    ("Lee la página actual", ("browser.page.read",)),
    ("Lista las pestañas del navegador", ("browser.tabs.list",)),
    ("Recarga la página", ("browser.control",)),
    (
        "Busca Beat It en Spotify y reprodúcela",
        ("media.play.query",),
    ),
    ("Pon Tesla en vivo", ("media.play.query",)),
    ("Pon la cámara en vivo", ()),
    ("Cambia el artista", ("media.control",)),
    ("Change the artist, please", ("media.control",)),
    ("Pon el siguiente podcast", ("media.control",)),
    ("Play the next episode", ("media.control",)),
    (
        "Can I see the reminder for Haley's birthday party again?",
        ("reminder.resolve.exact",),
    ),
    ("Cambia el artista a Queen", ()),
    ("Lugares para ir después de la medianoche", ("web.search",)),
    ("Places to go after midnight", ("web.search",)),
    ("Reminders for birthdays.", ("reminder.resolve.exact",)),
    ("Recordatorios de cumpleaños.", ("reminder.resolve.exact",)),
    ("Reminders for tomorrow.", ()),
    ("Para la alarma, por favor", ("notification.dismiss",)),
    ("Para la alarma a las siete", ()),
    ("Pausa la música", ("media.control",)),
    ("Detén el audio", ("media.control",)),
    ("Stop the audio", ("media.control",)),
    ("Por favor reproduzca el audio recientemente pausado", ("media.control",)),
    ("Please play recently paused audio", ("media.control",)),
    ("¿Qué música está sonando?", ("media.status",)),
    ("Lista mis juegos de Steam", ("game.catalog.list",)),
    (
        "¿Está instalado el juego Half-Life 2 en Steam?",
        ("game.installed.named",),
    ),
    (
        "Lista los dispositivos Bluetooth",
        ("bluetooth.device.list",),
    ),
    (
        "Lista los periféricos conectados",
        ("peripheral.list",),
    ),
    ("¿Cómo está el Wi-Fi?", ("wifi.status",)),
    (
        "Lista los perfiles Wi-Fi guardados",
        ("wifi.profile.list",),
    ),
    ("Lista mis próximos eventos del calendario", ()),
    ("Lee el correo más reciente", ("email.latest.read",)),
    (
        "Abre Opera, navega a https://example.com/ y lee la página",
        ("browser.navigate.named", "browser.page.read"),
    ),
    (
        "Haz una captura de pantalla y luego léela con OCR",
        ("capture.screenshot", "ocr.read"),
    ),
    (
        "Crea una nota llamada Auditoría encadenada y después léela",
        ("note.create", "note.read"),
    ),
    (
        "Pon el volumen al 8 por ciento y luego dime en cuánto quedó",
        ("audio.volume", "audio.status"),
    ),
    (
        "Abre Spotify, reproduce exactamente Beat It y después pausa",
        ("media.play.exact", "media.control"),
    ),
    ("necesito el bloc de notas", ("app.open",)),
    ("I need notepad", ("app.open",)),
    ("play the tiny desk concert on youtube", ("media.play.youtube",)),
    ("Reproduce lofi en YouTube", ("media.play.youtube",)),
    ("hay archivos repetidos en descargas", ("filesystem.known.duplicates",)),
    ("busca duplicados en descargas", ("filesystem.known.duplicates",)),
    ("que cosas tengo conectadas al equipo", ("peripheral.list",)),
    ("what do I have connected to the computer", ("peripheral.list",)),
    (
        "anota que hay reunion el jueves y avisame ese dia",
        ("note.create", "reminder.create"),
    ),
    ("trancame el equipo que me voy", ("system.power",)),
    ("see if 8.8.8.8 answers", ("network.ping",)),
    ("para lo que esta sonando", ("media.control",)),
    ("agregame al pendiente revisar el contrato", ("task.create",)),
    ("pegalo aca", ("clipboard.paste",)),
    ("what did I copy last", ("clipboard.read.text",)),
    ("type hello world for me", ("input.text.type",)),
    (
        "agendame una reunion manana de diez a once",
        ("calendar.event.create",),
    ),
    ("pasa a la siguiente cancion", ("media.control",)),
    ("dale enter", ("input.key.press",)),
    ("llevame a wikipedia", ("browser.navigate",)),
    (
        "apuntame que tengo que llamar al dentista",
        ("note.create",),
    ),
    (
        "jot down that the router password is on the fridge",
        ("note.create",),
    ),
    ("hazme grande esta ventana que no veo nada", ("window.maximize",)),
    (
        "send this window down to the taskbar",
        ("window.minimize",),
    ),
    (
        "devuelvele el tamano normal a la ventana",
        ("window.restore",),
    ),
    ("open the last file I downloaded", ("filesystem.file.open.latest",)),
    ("do I have discord on this machine", ("app.installed",)),
    ("is steam even installed here", ("app.installed",)),
    ("apaga la compu", ("system.power",)),
    ("arrancame el navegador", ("app.open",)),
    ("esta muy fuerte el audio, bajalo", ("audio.volume.adjust",)),
    ("dejame el sonido a la mitad", ("audio.volume",)),
    (
        "que programas se estan comiendo la memoria",
        ("system.process.list",),
    ),
    ("sacale el hash al archivo reporte.txt", ("filesystem.hash",)),
    (
        "que archivos tengo en la carpeta de trabajo",
        ("filesystem.list",),
    ),
    (
        "para la descarga que tiene steam corriendo",
        ("game.install.cancel.active",),
    ),
    ("scroll down a bit", ("input.pointer.control",)),
]

AVAILABLE = {operation for _, operations in CASES for operation in operations}


@pytest.mark.parametrize(
    "text",
    [
        "Send Elena on WhatsApp que llegaré en media hora y then show scheduled reminders",
        "Send Maya on WhatsApp that I'll arrive soon and then list my scheduled reminders",
    ],
)
def test_message_then_reminder_collection_is_a_bounded_composition(text: str) -> None:
    available = AVAILABLE | {
        "message.recipient.resolve",
        "message.send",
        "reminder.list",
    }

    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == (
        "message.recipient.resolve",
        "message.send",
        "reminder.list",
    )


def test_note_and_same_day_reminder_is_not_an_incomplete_calendar_event() -> None:
    text = "anota que hay reunion el jueves y avisame ese dia"
    available = AVAILABLE | {
        "note.create",
        "reminder.create",
        "calendar.event.create",
        "notification.schedule",
    }

    assert resolve_explicit_clarification_intent(text, available) is None
    result = resolve_explicit_effects(text, available)
    assert result is not None
    assert result.operations == ("note.create", "reminder.create")


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_deterministic_audit_effect_subset_is_compositional(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert (() if result is None else result.operations) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Could you open calculator please?", ("app.open",)),
        ("show the current computer status", ("system.status",)),
        ("set volume to 27%", ("audio.volume",)),
        ("show my pending tasks", ("task.list",)),
        (
            "Take a screenshot, then read it with OCR",
            ("capture.screenshot", "ocr.read"),
        ),
        (
            "Open Opera then navigate to https://example.org and read the page",
            ("browser.navigate.named", "browser.page.read"),
        ),
        (
            "Play Beat It exactly on Spotify and pause afterwards",
            ("media.play.exact", "media.control"),
        ),
        (
            "Play Beat It exactly on Spotify and pause afterwards.",
            ("media.play.exact", "media.control"),
        ),
        (
            "Puedes abrir Spotify y reproducir Beat It",
            ("media.play.query",),
        ),
        (
            "Podrías abrir Opera y navegar a https://example.com y leer la página",
            ("browser.navigate.named", "browser.page.read"),
        ),
        (
            "Puedes hacer una captura y leerla con OCR",
            ("capture.screenshot", "ocr.read"),
        ),
        (
            "¿Está instalado el juego Half-Life 2 en Steam?",
            ("game.installed.named",),
        ),
    ],
)
def test_effect_recognition_covers_paraphrases_not_literal_sentences(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == expected


def test_recognized_effect_must_exist_in_authenticated_catalog() -> None:
    assert (
        resolve_explicit_effects(
            "Haz una captura de pantalla",
            {"system.time"},
        )
        is None
    )
    assert (
        resolve_explicit_effects(
            "What time is the movie set in?",
            {"system.time"},
        )
        is None
    )


def test_strict_shared_head_composition_requires_every_segment_to_be_grounded() -> None:
    available = {"system.status", "network.status", "audio.status"}

    valid = resolve_explicit_effects(
        "Show system status, network status, and sound status",
        available,
    )
    assert valid is not None
    assert valid.operations == (
        "system.status",
        "network.status",
        "audio.status",
    )
    assert (
        resolve_explicit_effects(
            "Show system status, network status, brew coffee, and sound status",
            available,
        )
        is None
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Get rid of the five p.m. alarm", "notification.cancel.at"),
        ("Quita la alarma de las cinco de la tarde", "notification.cancel.at"),
        ("Remove the 17:30 alarm", "notification.cancel.at"),
        ("Cancela la alarma más reciente", "notification.cancel.latest"),
    ],
)
def test_notification_cancellation_distinguishes_exact_clock_from_latest(
    text: str,
    expected: str,
) -> None:
    available = {"notification.cancel.at", "notification.cancel.latest"}

    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == (expected,)
    assert operation_domain_is_grounded(text, expected) is True


@pytest.mark.parametrize(
    "text",
    [
        "Can the alarm that I have set, please be be turned of",
        "Deactivate alarm",
        "Desactiva la alarma",
    ],
)
def test_alarm_without_identity_clarifies_instead_of_guessing_latest(
    text: str,
) -> None:
    result = resolve_explicit_clarification_intent(
        text,
        {"notification.cancel.at", "notification.cancel.latest"},
    )

    assert result is not None
    assert result.operations == ("notification.cancel.at",)
    assert result.missing_fields == ("alarm_time",)


@pytest.mark.parametrize(
    "text",
    [
        "Pon la alarma para la hora de la merienda",
        "Set an alarm for dinner time",
    ],
)
def test_culturally_variable_meal_times_require_an_exact_alarm_time(
    text: str,
) -> None:
    result = resolve_explicit_clarification_intent(
        text,
        {"notification.schedule"},
    )

    assert result is not None
    assert result.operations == ("notification.schedule",)
    assert result.missing_fields == ("alarm_time",)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Abre Paint", ("app.open",)),
        ("Abre Visual Studio Code", ("app.open",)),
        ("Abre la aplicacion Spotify", ("app.open",)),
        ("Esta instalado Paint?", ("app.installed",)),
        ("Is Visual Studio Code installed?", ("app.installed",)),
        (
            "Abre Paint y Visual Studio Code",
            ("app.open", "app.open"),
        ),
        (
            "Abre Paint, Visual Studio Code",
            ("app.open", "app.open"),
        ),
        (
            "Abre Paint y Spotify",
            ("app.open", "app.open"),
        ),
        (
            "Estan instalados Paint y Visual Studio Code?",
            ("app.installed", "app.installed"),
        ),
        (
            "Are Paint and Visual Studio Code installed?",
            ("app.installed", "app.installed"),
        ),
        (
            "Estan instalados Paint y Spotify?",
            ("app.installed", "app.installed"),
        ),
        (
            "Are Paint and Spotify installed?",
            ("app.installed", "app.installed"),
        ),
        (
            "Estan instalados Visual Studio Code y Spotify?",
            ("app.installed", "app.installed"),
        ),
    ],
)
def test_authenticated_application_catalog_routes_exact_entities(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(
        text,
        AVAILABLE,
        ("Paint", "Visual Studio Code", "Spotify"),
    )
    assert result is not None
    assert result.operations == expected


def test_large_application_catalog_reuses_index_far_below_turn_sla() -> None:
    names = tuple(f"Application {index:04d}" for index in range(2_048))
    catalog = build_application_catalog_index(names)

    assert build_application_catalog_index(catalog) is catalog
    with pytest.raises(ValueError, match="entry limit"):
        build_application_catalog_index((*names, "Overflow Application"))
    started = perf_counter()
    results = [
        resolve_explicit_effects(
            "Open Application 2047",
            {"app.open"},
            catalog,
        )
        for _ in range(25)
    ]
    elapsed = perf_counter() - started

    assert all(result is not None for result in results)
    assert all(result.operations == ("app.open",) for result in results)
    assert elapsed < 1.0


def test_application_launch_identity_is_closed_over_authenticated_inventory() -> None:
    catalog = build_application_catalog_index(
        (
            "Access",
            "Access Manager",
            "Bloc de notas",
            "Calculadora",
            "Google Chrome",
        )
    )

    assert resolve_application_catalog_app_id("Open Notepad", catalog) == (
        "windows.notepad"
    )
    assert resolve_application_catalog_app_id("Open calc", catalog) == (
        "windows.calculator"
    )
    assert resolve_application_catalog_app_id("Open Chrome", catalog) == (
        "Google Chrome"
    )
    assert resolve_application_catalog_app_id("Open Access", catalog) == "Access"
    assert resolve_application_catalog_app_id("Open VLC", catalog) is None


@pytest.mark.parametrize(
    "text",
    [
        "Confirma si VLC está disponible como programa instalado",
        "See if Calculator is present in my installed apps",
        "Inspect the installed applications for VLC",
        "Confirma si Calculator is installed aquí",
    ],
)
def test_explicit_installed_app_observations_can_verify_catalog_absence(
    text: str,
) -> None:
    result = resolve_explicit_effects(
        text,
        {"app.installed"},
        ("Calculadora", "Steam"),
    )

    assert result is not None
    assert result.operations == ("app.installed",)


@pytest.mark.parametrize(
    "text",
    [
        "Explain whether VLC is installed",
        "The installed applications guide mentions VLC",
    ],
)
def test_nonliteral_or_compound_app_inventory_mentions_still_abstain(
    text: str,
) -> None:
    assert (
        resolve_explicit_effects(
            text,
            {"app.installed", "app.open"},
            ("Calculadora", "Steam"),
        )
        is None
    )


def test_installed_app_observation_composes_with_a_separate_open_request() -> None:
    result = resolve_explicit_effects(
        "Inspect the installed applications for VLC and open Steam",
        {"app.installed", "app.open"},
        ("Calculadora", "Steam"),
    )

    assert result is not None
    assert result.operations == ("app.installed", "app.open")


def test_builtin_keyboard_operation_precedes_dynamic_app_name() -> None:
    result = resolve_explicit_effects(
        "Abre el teclado en pantalla",
        AVAILABLE,
        ("Teclado en pantalla",),
    )

    assert result is not None
    assert result.operations == ("input.keyboard.open",)


def test_new_notepad_paste_composes_only_with_authenticated_application() -> None:
    available = {"app.open", "clipboard.paste"}
    result = resolve_explicit_effects(
        "pega texto en un archivo nuevo de Notepad",
        available,
        ("Bloc de notas",),
    )

    assert result is not None
    assert result.operations == ("app.open", "clipboard.paste")
    assert result.evidence[0] == "notepad"


def test_spotify_context_preserves_exact_play_then_pause_plan() -> None:
    text = "Abre Spotify, reproduce exactamente Beat It y después pausa"
    result = resolve_explicit_effects(
        text,
        AVAILABLE,
        ("Spotify",),
    )

    assert result is not None
    assert result.operations == ("media.play.exact", "media.control")
    assert (
        operation_domain_is_grounded(
            text,
            "media.play.exact",
        )
        is True
    )
    assert (
        unresolved_compound_contract(
            text,
            AVAILABLE,
            ("Spotify",),
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Abre Paint documentation",
        "Abre Visual Studio Code examples",
        "Open the application door",
        "Is Word installed in the dictionary?",
    ],
)
def test_authenticated_application_catalog_requires_exact_anchored_target(
    text: str,
) -> None:
    assert (
        resolve_explicit_effects(
            text,
            AVAILABLE,
            ("Paint", "Visual Studio Code", "Spotify", "Word"),
        )
        is None
    )


def test_authenticated_application_identity_preserves_punctuation() -> None:
    names = ("Paint.NET", "Paint@NET")

    dot = resolve_explicit_effects("Open Paint.NET", AVAILABLE, names)
    at = resolve_explicit_effects("Open Paint@NET", AVAILABLE, names)

    assert dot is not None
    assert dot.operations == ("app.open",)
    assert dot.evidence == ("paint.net",)
    assert at is not None
    assert at.operations == ("app.open",)
    assert at.evidence == ("paint@net",)
    assert (
        resolve_explicit_effects(
            "Open Paint@NET",
            AVAILABLE,
            ("Paint.NET",),
        )
        is None
    )
    conflict = unresolved_compound_contract(
        "Open Paint@NET",
        AVAILABLE,
        ("Paint.NET",),
    )
    assert isinstance(conflict, CompoundEffectContract)
    assert conflict.minimum_effects == 1


@pytest.mark.parametrize(
    "text",
    [
        "I need you to open Spotify",
        "Get Spotify running",
        "Spotify needs to be open",
    ],
)
def test_authenticated_desired_app_state_is_an_exact_open_effect(text: str) -> None:
    result = resolve_explicit_effects(text, AVAILABLE, ("Spotify", "Paint"))

    assert result is not None
    assert result.operations == ("app.open",)
    assert (
        operation_domain_is_grounded(
            text,
            "app.open",
            ("Spotify", "Paint"),
        )
        is True
    )


@pytest.mark.parametrize(
    "text",
    [
        "I needed you to open Spotify",
        "I need you not to open Spotify",
        "Get Spotify running tomorrow",
        "Get Spotify running on my phone",
        "Get Spotify documentation running",
    ],
)
def test_desired_app_state_never_bypasses_time_negation_or_device_scope(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE, ("Spotify", "Paint")) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Open Paint, Spotify, and Visual Studio Code",
            ("app.open", "app.open", "app.open"),
        ),
        (
            "Abre Paint, Spotify y Visual Studio Code",
            ("app.open", "app.open", "app.open"),
        ),
        (
            "Open Paint and then Spotify",
            ("app.open", "app.open"),
        ),
        (
            "Abre Paint y luego Spotify",
            ("app.open", "app.open"),
        ),
        (
            "Are Paint, Spotify, and Visual Studio Code installed?",
            ("app.installed", "app.installed", "app.installed"),
        ),
        (
            "Estan Paint, Spotify y Visual Studio Code instalados?",
            ("app.installed", "app.installed", "app.installed"),
        ),
        (
            "Are installed Paint and then Spotify?",
            ("app.installed", "app.installed"),
        ),
        (
            "Estan instalados Paint y luego Spotify?",
            ("app.installed", "app.installed"),
        ),
    ],
)
def test_authenticated_application_lists_cover_natural_en_es_connectors(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(
        text,
        AVAILABLE,
        ("Paint", "Spotify", "Visual Studio Code"),
    )

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    ("text", "expected_name"),
    [
        ("Open The App NOW", "the app now"),
        ("Open The App", "the app"),
        ("Open App NOW", "app now"),
        ("Open NOW", "now"),
    ],
)
def test_authenticated_application_prefers_the_complete_exact_name(
    text: str,
    expected_name: str,
) -> None:
    result = resolve_explicit_effects(
        text,
        AVAILABLE,
        ("The", "The App", "The App NOW", "App", "App NOW", "NOW"),
    )

    assert result is not None
    assert result.operations == ("app.open",)
    assert result.evidence == (expected_name,)


@pytest.mark.parametrize(
    "name",
    [
        "Command Prompt",
        "Adobe After Effects",
        "Scan and Capture",
    ],
)
def test_exact_authenticated_app_name_words_do_not_trigger_global_guards(
    name: str,
) -> None:
    result = resolve_explicit_effects(
        f"Open {name}",
        AVAILABLE,
        (name,),
    )

    assert result is not None
    assert result.operations == ("app.open",)
    assert result.evidence == (name.casefold(),)
    assert (
        unresolved_compound_contract(
            f"Open {name}",
            AVAILABLE,
            (name,),
        )
        is None
    )


def test_more_than_eight_authenticated_apps_get_a_conservation_veto() -> None:
    names = tuple(f"App {index}" for index in range(1, 10))
    text = f"Open {', '.join(names[:-1])}, and {names[-1]}"

    assert resolve_explicit_effects(text, AVAILABLE, names) is None
    contract = unresolved_compound_contract(text, AVAILABLE, names)
    assert isinstance(contract, CompoundEffectContract)
    assert contract.minimum_effects == 9
    assert contract.required_clause_sequences == (tuple("app.open" for _ in names),)


@pytest.mark.parametrize(
    "text",
    [
        "¿Está instalado Portal 2?",
        "¿Está instalado Half-Life 2?",
        "Is Stardew Valley installed?",
        "¿Está instalado Photoshop 2024?",
        "Is Python 3 installed?",
    ],
)
def test_unknown_installed_entity_is_left_to_closed_catalog_semantics(
    text: str,
) -> None:
    # The operation-only recognizer has no authenticated application/game
    # entity catalog. It must abstain instead of guessing from a title shape;
    # turn.decide performs the general closed-catalog semantic classification.
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    "text",
    [
        "Don't open Spotify",
        "No abre Spotify",
        "Solo responde, no uses herramientas: abre Steam",
        "¿Qué significa mute?",
        "¿Cómo hacer una captura?",
        "Translate 'open Spotify' into Spanish",
        "Translate what time is it into Spanish",
        "What music do you like?",
        "What song should I write?",
        "Busca cómo crear una tarea",
        "I won't open Spotify",
        "You should not open Spotify",
        "I cannot open Spotify",
        "What is ping?",
        "Explain the concept of ping",
        "Bluetooth devices use radio waves",
        "List biological processes that use memory",
        "Is Python installed?",
        "Is Python 3 installed?",
        "¿Está instalado Visual Studio 2022?",
        "Visual Studio Code is installed",
        "I read the latest email yesterday",
        "The current song is popular",
        "Say open Spotify out loud",
        "The button says play exactly on Spotify",
        "¿Qué hora es la película?",
        "¿Cómo está el equipo de fútbol?",
        "¿Cómo está la red neuronal?",
        "Lista procesos biológicos que usan memoria",
        "¿En qué volumen de la enciclopedia aparece BAXY?",
        "Silencia las notificaciones de Slack",
        "Haz una captura del ladrón",
        "Lee la página 42 del documento",
        "Recarga la página del libro",
        "¿Qué canción está sonando en mi cabeza?",
        "Abre Spotify pero no abras Spotify",
        "Open Spotify but do not open Spotify",
        "Abre calculadora y envía un mensaje a Ana",
        "Abre calculadora y elimina el archivo prueba.txt",
        "Abre calculadora y apaga el equipo",
        "Crea una nota y borra la nota anterior",
        "Abre Spotify y luego cierralo",
        "Crea una tarea y luego completala",
        "Crea una tarea y luego actualizala",
        "Crea una tarea y luego marcala como hecha",
        "Create a task then mark it done",
        "Abre Spotify y luego sal de la aplicacion",
        "Open Spotify then exit the app",
        "Abre Spotify y luego apagalo",
        "Crea una nota y luego deshazte de ella",
        "Abre calculadora y habilita la memoria",
        "Abre calculadora y olvida mi color favorito",
        "Abre calculadora y responde el correo más reciente",
        "Abre calculadora y programa una notificación",
        "Abre calculadora y cancela una notificación",
        "Abre calculadora y diagnostica una notificación",
        "Abre calculadora y completa la tarea Auditoría",
        "Abre calculadora y reabre la tarea Auditoría",
        "Abre calculadora y actualiza la tarea Auditoría",
        "Abre calculadora y describe la pantalla",
        "Abre calculadora y redimensiona la ventana",
        "Abre calculadora y enfoca Spotify",
        "Abre calculadora y presiona Enter",
        "Abre calculadora y vacía la papelera",
        "Abre calculadora y termina el proceso demo",
        "Abre calculadora y verifica la copia de seguridad",
        "Abre calculadora y no abras Spotify",
        "Open calculator and do not open Spotify",
        "Busca Spotify en Google",
        "Busca Spotify en Wikipedia",
        "Busca la palabra Spotify en este documento",
        "Maximiza la ventana de oportunidad",
        "Minimiza la ventana de exposicion financiera",
        "Silencia el audio manana",
        "Pon el volumen al 20% a las 5",
        "Haz una captura de pantalla manana",
        "Maximiza la ventana activa mas tarde",
        "Reproduce Beat It en Spotify luego",
        "Pon el volumen al 8% y el brillo al 50%",
        "Silencia el audio y las notificaciones",
        "Silencia el audio, no lo hagas",
        "Silencia el audio; no lo hagas",
        "Silencia el audio. No lo hagas",
        "Pon el volumen al 20%, mejor no",
        "Haz una captura de pantalla, en realidad no",
        "Maximiza la ventana activa, aunque mejor no",
        "Copia la seleccion, scratch that",
        "Navega a https://example.com/, actually do not",
        "Crea una nota, on second thought do not",
        "Lista los procesos de contratacion de la empresa",
        "Silencia el audio dentro de una hora",
        "Silencia el audio esta noche",
        "Silencia el audio tras la reunion",
        "Silencia el audio antes de la reunion",
        "Silencia el audio si empieza la reunion",
        "Silencia el audio el viernes",
        "Silencia el audio el 30 de julio",
        "Silencia el audio a mediodia",
        "Silencia el audio al terminar",
        "Silencia el audio una vez que termine",
        "Mute audio in one hour",
        "Mute audio tonight",
        "Mute audio after the meeting",
        "Mute audio before the meeting",
        "Mute audio if the meeting starts",
        "Mute audio on Friday",
        "Mute audio July 30",
        "Mute audio at noon",
        "Mute audio once I finish",
        "Pon el volumen al 20% dentro de una hora",
        "Maximiza la ventana activa si comienza la reunion",
        "Copia la seleccion al terminar",
        "Silencia el audio, ya no",
        "Silencia el audio, ignora eso",
        "Silencia el audio, dejalo",
        "Silencia el audio, mejor dejalo",
        "Silencia el audio, me retracto",
        "Silencia el audio, me arrepenti",
        "Silencia el audio, never mind",
        "Silencia el audio, ignore that",
        "Silencia el audio, I take that back",
        "Silencia el audio, drop it",
        "Crea dos notas llamadas Alfa y Beta",
        "Crea 3 notas",
        "Crea una nota Alfa y una nota Beta",
        "Crea dos tareas llamadas Alfa y Beta",
        "Crea dos recordatorios llamados Alfa y Beta",
        "Copia la seleccion dos veces",
        "Que ventana de oportunidad esta activa?",
        "Cual ventana temporal esta activa?",
        "What window of opportunity is active?",
    ],
)
def test_mentions_negations_and_how_to_questions_never_gain_effects(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Abre calculadora y abre Spotify", ("app.open", "app.open")),
        (
            "Maximiza y luego minimiza la ventana activa",
            ("window.active", "window.maximize", "window.minimize"),
        ),
        (
            "Navega a https://a.test y luego navega a https://b.test",
            ("browser.navigate", "browser.navigate"),
        ),
        ("Crea una nota A y crea una nota B", ("note.create", "note.create")),
        ("Busca notas en la web", ("web.search",)),
        ("Crea una nota sobre mis tareas", ("note.create",)),
        (
            "Abre calculadora y navega Opera a https://example.com",
            ("app.open", "browser.navigate.named"),
        ),
        (
            "Abre calculadora y reproduce exactamente Beat It en Spotify",
            ("app.open", "media.play.exact"),
        ),
        (
            "Open Notepad and search Beat It on Spotify",
            ("app.open", "media.play.query"),
        ),
        (
            "Busca BAXY en mis notas y luego busca clima en la web",
            ("note.search", "web.search"),
        ),
        (
            "Abre Spotify y busca clima en la web",
            ("app.open", "web.search"),
        ),
        (
            "Pon el volumen al 8% y luego sube el volumen en 2 puntos",
            ("audio.volume", "audio.volume.adjust"),
        ),
        (
            "Mute audio and then unmute audio",
            ("audio.mute", "audio.mute"),
        ),
        (
            "Silencia el audio y reactivalo",
            ("audio.mute", "audio.mute"),
        ),
        (
            "Silencia el audio y quita el silencio",
            ("audio.mute", "audio.mute"),
        ),
        ("Abre calculadora y Spotify", ("app.open", "app.open")),
        (
            "Abre calculadora, Spotify y Bloc de notas",
            ("app.open", "app.open", "app.open"),
        ),
        ("Crea una nota A y otra B", ("note.create", "note.create")),
        (
            "Pon el volumen al 8% y luego al 12%",
            ("audio.volume", "audio.volume"),
        ),
        (
            "Crea una nota y una tarea",
            ("note.create", "task.create"),
        ),
        (
            "Crea una tarea y un recordatorio",
            ("task.create", "reminder.create"),
        ),
        (
            "Crea una tarea llamada Alfa y un recordatorio llamado Beta "
            "para manana a las 9",
            ("task.create", "reminder.create"),
        ),
        (
            "Lista mis notas y mis tareas",
            ("note.list", "task.list"),
        ),
        (
            "Busca Auditoria en mis notas y mis tareas",
            ("note.search", "task.search"),
        ),
        (
            "Que juegos estan instalados en Steam?",
            ("game.catalog.list",),
        ),
        (
            "Esta instalado Steam como plataforma de juego?",
            ("app.installed",),
        ),
    ],
)
def test_effect_cardinality_and_nearest_domain_are_preserved(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == expected
    assert len(result.evidence) == len(expected)


@pytest.mark.parametrize(
    ("text", "expected_operation", "expected_evidence"),
    [
        (
            "Crea una tarea llamada Notas de viaje",
            "task.create",
            "crea una tarea llamada notas de viaje",
        ),
        (
            "Crea una nota llamada Tareas de manana",
            "note.create",
            "crea una nota llamada tareas de manana",
        ),
        (
            "Busca Auditoria en mis tareas sobre notas antiguas",
            "task.search",
            "busca auditoria en mis tareas sobre notas antiguas",
        ),
        (
            "Busca Auditoria en mis notas sobre tareas antiguas",
            "note.search",
            "busca auditoria en mis notas sobre tareas antiguas",
        ),
        (
            "Lista mis tareas sobre notas archivadas",
            "task.list",
            "lista mis tareas sobre notas archivadas",
        ),
        (
            "Lista mis notas sobre tareas archivadas",
            "note.list",
            "lista mis notas sobre tareas archivadas",
        ),
    ],
)
def test_local_data_first_domain_wins_without_explicit_coordination(
    text: str,
    expected_operation: str,
    expected_evidence: str,
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == (expected_operation,)
    assert result.evidence == (expected_evidence,)


@pytest.mark.parametrize(
    "text",
    [
        "No crees una nota",
        "No listes mis tareas",
        "No busques en mis notas",
        "Explicame como crear una tarea",
        "Mis notas describen tareas pendientes",
        "Las tareas incluyen notas archivadas",
        "Otra nota",
    ],
)
def test_local_data_mentions_and_negated_requests_do_not_gain_effects(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    "text",
    [
        "Dime la hora y revisa la CPU",
        "Dime la hora y revisa la RAM",
        "¿Qué hora es y revisa el estado del computador?",
        "What time is it and check the CPU",
        "What time is it and review the computer status",
    ],
)
def test_time_then_system_review_preserves_both_effects(text: str) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == ("system.time", "system.status")
    assert unresolved_compound_contract(text, AVAILABLE) is None
    assert operation_domain_is_grounded(text, "system.time") is True
    assert operation_domain_is_grounded(text, "system.status") is True


@pytest.mark.parametrize("text", [
    "no me molesta, dime la hora",
    "I don't mind, tell me the time",
    "no abras Steam, dime la hora",
])
def test_negative_clause_is_not_counted_as_an_unresolved_positive_effect(text: str) -> None:
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=None) is None


@pytest.mark.parametrize("text", [
    "dime la hora, no abras Steam",
    "dime la hora y no abras Steam",
    "tell me the time, do not open Spotify",
    "tell me the time and do not mute the audio",
    "dime la hora y no silencies el audio",
])
def test_independent_prohibition_preserves_semantic_read_selection(text: str) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == ("system.time",)
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=None) is None


def test_independent_audio_prohibition_preserves_application_request() -> None:
    text = "Abre calculadora y no silencies el audio"
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == ("app.open",)
    assert unresolved_compound_contract(text, AVAILABLE) is None


@pytest.mark.parametrize("text", [
    "¿No está silenciado el audio?",
    "¿No está abierta la calculadora?",
    "¿No están instaladas las aplicaciones?",
])
def test_negative_state_question_is_not_a_no_effect_contract(text: str) -> None:
    assert not explicit_negative_constraint(text)
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=None) is None


def test_negative_mute_question_resolves_only_the_read() -> None:
    result = resolve_explicit_effects(
        "¿No está silenciado el audio?", ("audio.status", "audio.mute", "audio.volume"),
    )
    assert result is not None
    assert result.operations == ("audio.status",)


@pytest.mark.parametrize("text", [
    "No está silenciado el audio",
    "¿No silencies el audio?",
    "¿No está silenciado el audio? No lo revises",
])
def test_negative_statement_command_and_retraction_are_not_state_reads(text: str) -> None:
    assert resolve_explicit_effects(text, ("audio.status", "audio.mute")) is None


@pytest.mark.parametrize("text", [
    "dime la hora, no lo hagas",
    "dime la hora y no me digas la hora",
    "abre Spotify y no abras Spotify",
    "silencia el audio y no silencies el audio",
    "dime la hora, no uses herramientas",
    "dime la hora, no hagas nada",
])
def test_scope_comparison_preserves_retractions_and_global_denials(text: str) -> None:
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=None) is not None


@pytest.mark.parametrize("text", [
    "no me digas la hora",
    "don't tell me the time",
    "no uses herramientas, dime la hora",
    "don't use tools, tell me the time",
    "dime la hora y envía un mensaje a Ana",
])
def test_scoped_conservation_keeps_global_denial_and_missing_effects(text: str) -> None:
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=None) is not None


@pytest.mark.parametrize(
    "text",
    [
        "Dime la hora y revisa el artículo sobre CPU",
        "Dime la hora y revisa el código de la CPU",
        "What time is it and review the CPU architecture paper",
    ],
)
def test_system_review_words_do_not_authorize_document_requests(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None
    contract = unresolved_compound_contract(text, AVAILABLE)
    assert isinstance(contract, CompoundEffectContract)
    assert contract.minimum_effects >= 2


def test_repeated_effects_keep_distinct_argument_evidence() -> None:
    result = resolve_explicit_effects(
        "Abre calculadora y abre Spotify",
        AVAILABLE,
    )
    assert result is not None
    assert "calculadora" in result.evidence[0]
    assert "spotify" not in result.evidence[0]
    assert "spotify" in result.evidence[1]


def test_fully_enumerated_notes_preserve_creation_and_permuted_read_cardinality() -> (
    None
):
    text = (
        "Crea cuatro notas: la primera titulada Uno con contenido uno, "
        "la segunda titulada Dos con contenido dos, la tercera titulada Tres "
        "con contenido tres y la cuarta titulada Cuatro con contenido cuatro. "
        "Después lee, en este orden exacto, la tercera nota, la primera nota, "
        "la cuarta nota y la segunda nota."
    )

    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == (
        "note.create",
        "note.create",
        "note.create",
        "note.create",
        "note.read",
        "note.read",
        "note.read",
        "note.read",
    )
    assert unresolved_compound_contract(text, AVAILABLE) is None


def test_fully_enumerated_english_notes_preserve_permuted_read_cardinality() -> None:
    text = (
        "Create four notes: the first titled One with content one, the second "
        "titled Two with content two, the third titled Three with content three, "
        "and the fourth titled Four with content four. After that read the fourth "
        "note, the second note, the first note, and the third note."
    )

    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == ("note.create",) * 4 + ("note.read",) * 4
    assert unresolved_compound_contract(text, AVAILABLE) is None


def test_private_notes_accept_complete_middle_last_first_read_order() -> None:
    text = (
        "Create three private notes: the first titled Cedar with content red, "
        "the second titled Maple with content green, and the third titled Pine "
        "with content blue. After all three exist, read the middle note, then "
        "the last note, and finally the first note."
    )

    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == ("note.create",) * 3 + ("note.read",) * 3
    assert enumerated_note_dependency_order(text) == (2, 3, 1)
    assert unresolved_compound_contract(text, AVAILABLE) is None


def test_before_continuing_is_an_immediate_note_sequence_boundary() -> None:
    text = (
        "Create a note titled Harbor with content east and read that note "
        "before continuing; then create a note titled Beacon with content west "
        "and read the second note."
    )

    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == (
        "note.create",
        "note.read",
        "note.create",
        "note.read",
    )
    assert unresolved_compound_contract(text, AVAILABLE) is None


def test_named_notes_require_a_complete_unique_named_read_permutation() -> None:
    text = (
        "Create cuatro notas: Sol token con contenido one, Luna token con "
        "contenido two, Mar token con contenido three y Monte token con contenido "
        "four. Después read, en este orden, la nota Mar, la nota Sol, la nota "
        "Monte y la nota Luna."
    )

    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == ("note.create",) * 4 + ("note.read",) * 4
    assert enumerated_note_dependency_order(text) == (3, 1, 4, 2)
    assert unresolved_compound_contract(text, AVAILABLE) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "En una sola misión revisa primero el estado del sistema, después "
            "el estado del audio y finalmente el estado de la red.",
            ("system.status", "audio.status", "network.status"),
        ),
        (
            "In one mission report keyboard status, then mouse status, and "
            "finally Bluetooth radio status.",
            (
                "input.keyboard.status",
                "input.mouse.status",
                "bluetooth.radio.status",
            ),
        ),
        (
            "In one mission report keyboard status, then connected peripherals, "
            "and finally visible Bluetooth devices.",
            (
                "input.keyboard.status",
                "peripheral.list",
                "bluetooth.device.list",
            ),
        ),
    ],
)
def test_ordered_status_sequences_share_one_read_only_request_head(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected
    assert unresolved_compound_contract(text, set(expected)) is None


def test_ordered_status_sequence_still_rejects_negated_authority() -> None:
    text = (
        "Do not report keyboard status, then mouse status, and finally "
        "Bluetooth radio status."
    )

    assert (
        resolve_explicit_effects(
            text,
            {
                "input.keyboard.status",
                "input.mouse.status",
                "bluetooth.radio.status",
            },
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Crea cuatro notas sobre seguridad.",
        (
            "Crea cuatro notas: la primera titulada Uno, la segunda titulada Dos "
            "y la cuarta titulada Cuatro."
        ),
        (
            "Crea cuatro notas: la primera titulada Uno, la segunda titulada Dos, "
            "la segunda titulada Repetida y la cuarta titulada Cuatro."
        ),
    ],
)
def test_unenumerated_or_inconsistent_note_cardinality_stays_fail_closed(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    ("text", "available"),
    [
        (
            "Escribe literalmente busca clima en la web",
            {"web.search"},
        ),
        (
            "Crea una nota llamada Busca clima en la web",
            {"web.search"},
        ),
        (
            "Abre Opera y navega Opera a https://example.com",
            {"app.open"},
        ),
        (
            "Abre Spotify y reproduce exactamente Beat It en Spotify",
            {"app.open"},
        ),
    ],
)
def test_unavailable_dominant_or_richer_effect_never_falls_back_to_weaker_authority(
    text: str,
    available: set[str],
) -> None:
    assert resolve_explicit_effects(text, available) is None


def test_same_position_effects_share_the_same_bounded_evidence() -> None:
    result = resolve_explicit_effects(
        "Maximiza la ventana activa y luego silencia el audio",
        {"window.active", "window.maximize", "audio.mute"},
    )

    assert result is not None
    assert result.operations == (
        "window.active",
        "window.maximize",
        "audio.mute",
    )
    assert result.evidence == (
        "maximiza la ventana activa",
        "maximiza la ventana activa",
        "silencia el audio",
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Escribe literalmente abre Spotify", ("input.text.type",)),
        ("Escribe literalmente silencia el audio", ("input.text.type",)),
        ("Crea una nota llamada Abre Spotify", ("note.create",)),
        (
            "Crea una nota llamada Haz una captura de pantalla",
            ("note.create",),
        ),
        ("Crea una nota titulada Captura OCR", ("note.create",)),
        ("Crea una tarea llamada Navega a https://example.com", ("task.create",)),
        ("Busca la palabra Spotify en mis notas", ("note.search",)),
        ("Busca la palabra web en mis notas", ("note.search",)),
        ("Busca abre calculadora en la web", ("web.search",)),
        ("Busca haz ping a 127.0.0.1 en la web", ("web.search",)),
        ("Lista mis notas sobre procesos", ("note.list",)),
        ("Lista mis notas sobre dispositivos Bluetooth", ("note.list",)),
        ("Lee mi nota sobre la página actual", ("note.read",)),
        ("Lee mi nota sobre el correo más reciente", ("note.read",)),
        (
            "Crea una nota y luego lee el portapapeles",
            ("note.create", "clipboard.read.text"),
        ),
        (
            "Haz una captura de pantalla y luego lee mi nota sobre OCR",
            ("capture.screenshot", "note.read"),
        ),
        ("Navega a https://www.opera.com/", ("browser.navigate",)),
        (
            "Navega a https://example.com para leer sobre Opera",
            ("browser.navigate",),
        ),
        (
            "Navega a https://example.com con la palabra Opera",
            ("browser.navigate",),
        ),
        (
            "Navigate to https://example.com to read about Chrome",
            ("browser.navigate",),
        ),
        (
            "Navega a https://example.com usando Opera",
            ("browser.navigate.named",),
        ),
        (
            "Navigate to https://example.com with Chrome",
            ("browser.navigate.named",),
        ),
        ("Crea una nota llamada Pan y leche", ("note.create",)),
        ("Busca gatos y perros en la web", ("web.search",)),
        ("Lista los juegos instalados en Steam", ("game.catalog.list",)),
        ("Show installed Steam games", ("game.catalog.list",)),
        ("Abre calculadora y gracias", ("app.open",)),
        ("Abre calculadora y por favor", ("app.open",)),
        ("Abre calculadora y que tengas buen día", ("app.open",)),
    ],
)
def test_bound_argument_spans_are_opaque_to_unrelated_effect_matchers(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    "text",
    [
        "Open edge cases",
        "Open the edge cases document",
        "Abre la configuración del proyecto",
        "Open word count",
        "Is Word installed in the dictionary?",
        "¿Está instalado el word del documento?",
        "¿Cómo está el sistema solar?",
        "¿Cómo está el sistema educativo?",
        "¿Cómo está el sistema de ecuaciones?",
        "¿Cómo está el equipo médico?",
        "¿Cómo está el equipo editorial?",
        "¿Cómo está la red ferroviaria?",
        "¿Cómo está la red de transporte?",
        "Sube el volumen de ventas en 2 puntos",
        "Pon el volumen de producción al 80%",
        "Ajusta el volumen de datos al 50%",
        "¿En qué volumen de la revista aparece BAXY?",
        "Mute Slack audio notifications",
        "Abre Spotify, no, mejor no lo abras",
        "Abre Spotify, no, abre calculadora",
        "Abre calculadora en vez de abrir Spotify",
        "Dime por qué conviene evitar abrir Spotify",
        "Sube el volumen total de ventas en 2 puntos",
        "Aumenta el volumen anual de ventas en 2 puntos",
        "Pon el volumen total de datos al 50%",
        "Pon el volumen al 8% en Spotify",
        "Silencia el audio de Spotify",
        "Silencia la musica de Spotify",
        "Pon el audio de Spotify al 20%",
        "Sube la musica de Spotify en 2 puntos",
        "Pon mÃºsica dance de los 80's",
        "Lee la pagina actual del documento",
        "Recarga la pagina actual del documento",
        "Lee la pagina actual de Excel",
        "Lee la pagina actual en Word",
        "Lee la pagina actual del PDF",
        "Lee la pagina actual del manual",
        "Lee la pagina actual de la novela",
        "Maximiza la ventana temporal",
        "Maximiza la ventana actual de oportunidad",
        "Maximiza la ventana para invertir",
        "Minimiza la ventana abierta de negociacion",
        "Copia la seleccion nacional",
        "Copia la seleccion de poemas",
        "Lee la frase correo mas reciente",
        "Read the words latest email",
    ],
)
def test_modifiers_arguments_and_corrections_never_gain_literal_authority(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    "text",
    [
        "Abre calculadora y envía un mensaje a Ana",
        "Abre calculadora y elimina el archivo prueba.txt",
        "Abre calculadora y apaga el equipo",
        "Crea una nota y borra la nota anterior",
    ],
)
def test_unresolved_compound_exposes_a_conservative_effect_lower_bound(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None
    contract = unresolved_compound_contract(text, AVAILABLE)
    assert isinstance(contract, CompoundEffectContract)
    assert contract.minimum_effects == 2
    assert contract.required_clause_sequences in {
        (("app.open",),),
        (("note.create",),),
        (("task.create",),),
    }


@pytest.mark.parametrize("text", [
    "Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte",
    "Recuerda mi nombre para cuando te lo pregunte.",
    "Quiero que recuerdes mi color favorito cuando te pregunte de nuevo.",
    "Remember my name for when I ask you.",
    "Remember my favorite color so you can tell me when I ask again.",
    "Recuerda my favorite color para cuando te lo pregunte.",
])
def test_future_recall_purpose_does_not_schedule_the_memory_write(text: str) -> None:
    from baxy_mind import effect_intent

    assert not effect_intent._has_unsupported_deferred_effect(effect_intent._fold(text))


@pytest.mark.parametrize("text", [
    "Abre Steam cuando te lo pregunte.",
    "Open Steam when I ask you.",
    "Recuerda mi nombre mañana para cuando te lo pregunte.",
    "Remember my name tomorrow for when I ask you.",
    "Recuerda mi nombre y abre Steam cuando te lo pregunte.",
    "Remember my name and open Steam when I ask you.",
    "Remember to open Steam when I ask you.",
    "Recuerda abrir Steam cuando te lo pregunte.",
    "Recuerda mi nombre y luego abre Steam cuando te lo pregunte.",
    "Remember my name and then open Steam when I ask you.",
    "Remember my name, open Steam when I ask you.",
])
def test_recall_purpose_does_not_remove_an_actual_deferred_action(text: str) -> None:
    from baxy_mind import effect_intent

    assert effect_intent._has_unsupported_deferred_effect(effect_intent._fold(text))


def test_recall_purpose_keeps_reminder_routing_separate() -> None:
    from baxy_mind import effect_intent

    # A reminder is itself a scheduling operation. Its own argument contract
    # determines supported triggers; this immediate-effect guard does not.
    assert not effect_intent._has_unsupported_deferred_effect(
        effect_intent._fold("Recuérdame llamar a Carlos cuando cierre Steam."),
    )


def test_unresolved_compound_sums_real_clause_cardinality() -> None:
    contract = unresolved_compound_contract(
        "Maximiza la ventana activa y apaga el equipo",
        AVAILABLE,
    )
    assert isinstance(contract, CompoundEffectContract)
    assert contract.minimum_effects == 3
    assert contract.required_clause_sequences == (("window.active", "window.maximize"),)


@pytest.mark.parametrize(
    ("text", "minimum"),
    [
        ("Silencia el audio manana", 1),
        ("Pon el volumen al 20% a las 5", 1),
        ("Pon el volumen al 8% y el brillo al 50%", 2),
        ("Silencia el audio y las notificaciones", 2),
        ("Estan instalados Half-Life 2 y Portal 2 en Steam?", 2),
        ("Busca Auditoria en mis notas y en la web", 2),
        ("Busca Auditoria en mis tareas y en internet", 2),
        ("Crea una nota y un evento del calendario", 2),
        ("Crea una tarea y un evento del calendario", 2),
        ("Lista mis notas y mis eventos del calendario", 2),
        ("Lista mis tareas y mis correos", 2),
        ("Busca Auditoria en mis notas y mis correos", 2),
        ("Lista procesos del sistema y mis notas", 2),
        ("Lista juegos de Steam y mis notas", 2),
        ("Lista Bluetooth y mis tareas", 2),
        ("Lee el correo mas reciente y mi nota", 2),
    ],
)
def test_deferred_and_uncovered_shared_head_effects_fail_closed(
    text: str,
    minimum: int,
) -> None:
    contract = unresolved_compound_contract(text, AVAILABLE)
    assert isinstance(contract, CompoundEffectContract)
    assert contract.minimum_effects >= minimum


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Lee la pagina actual del documento", "browser.page.read"),
        ("Recarga la pagina actual del documento", "browser.control"),
        ("Maximiza la ventana de oportunidad", "window.maximize"),
        ("Minimiza la ventana de exposicion financiera", "window.minimize"),
        ("Lista los procesos de contratacion de la empresa", "system.process.list"),
        ("Muestra el estado de la memoria privada de BAXY", "system.status"),
        ("Que ventana de oportunidad esta activa?", "window.active"),
        ("Cual ventana temporal esta activa?", "window.active"),
        ("What window of opportunity is active?", "window.active"),
        ("Abre la puerta", "filesystem.folder.open"),
        ("Abre el ultimo capitulo", "filesystem.file.open.latest"),
        ("Pide un taxi para que venga a mi casa", "notification.schedule"),
        ("Pide un taxi para que venga a mi casa", "vision.describe"),
        ("Pide un taxi para que venga a mi casa", "message.send"),
        ("Pide un taxi para que venga a mi casa", "message.recipient.resolve"),
    ],
)
def test_polysemous_domains_veto_semantic_operation_proposals(
    text: str,
    operation: str,
) -> None:
    assert operation_domain_is_grounded(text, operation) is False


# Goal 03C: a catalogue leaf published as intent for an out-of-catalogue ask
# counts as acted. These are the nine stable leaks plus their in-catalogue
# counterparts: the substitute is contradicted, the real effect is not.
_GOAL03C_NEAR_MISS_PAIRS = (
    (
        "pide un taxi para las ocho",
        "agregame al pendiente revisar el contrato",
        "task.create",
    ),
    (
        "upload this video to youtube",
        "play the tiny desk concert on youtube",
        "media.play.youtube",
    ),
    (
        "grabame la pantalla en video",
        "captura de la ventana activa",
        "capture.active.window",
    ),
    (
        "connect to my work vpn",
        "connect to my home wifi",
        "wifi.connect.named",
    ),
    (
        "cloname el disco duro a otro",
        "copiame el archivo notas.txt a documentos",
        "filesystem.copy",
    ),
    (
        "editame el video y quitale los ultimos diez segundos",
        "retrocede diez segundos la cancion",
        "media.seek.relative",
    ),
    (
        "convierteme este pdf a word",
        "creame un documento de word en blanco",
        "office.document.create",
    ),
    (
        "unlock my phone for me",
        "apaga la compu",
        "system.power",
    ),
    (
        "imprimeme en 3d esta figura",
        "imprimime este documento en la impresora",
        "peripheral.print",
    ),
)


@pytest.mark.parametrize(
    ("ooc_text", "in_catalog_text", "operation"),
    _GOAL03C_NEAR_MISS_PAIRS,
)
def test_out_of_catalog_near_misses_cannot_ground_a_catalogue_leaf(
    ooc_text: str,
    in_catalog_text: str,
    operation: str,
) -> None:
    assert operation_identity_is_a_near_miss(ooc_text, operation) is True
    assert operation_domain_is_grounded(ooc_text, operation) is False
    assert operation_identity_is_a_near_miss(in_catalog_text, operation) is False
    assert operation_domain_is_grounded(in_catalog_text, operation) is not False


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("captura nada mas la ventana de adelante", "capture.active.window"),
        ("conectate al wifi de casa", "wifi.connect.named"),
        ("jump ahead thirty seconds", "media.seek.relative"),
        ("para la descarga que tiene steam corriendo", "game.install.cancel.active"),
        ("Dile a Ana que llegare tarde por WhatsApp", "message.send"),
    ],
)
def test_in_catalog_paraphrases_are_not_near_miss_substitutes(
    text: str,
    operation: str,
) -> None:
    assert operation_identity_is_a_near_miss(text, operation) is False


def test_trim_video_is_not_media_control_either() -> None:
    text = "editame el video y quitale los ultimos diez segundos"
    assert operation_identity_is_a_near_miss(text, "media.control") is True
    assert operation_domain_is_grounded(text, "media.control") is False


def test_torrent_download_is_not_a_steam_cancel() -> None:
    assert (
        resolve_explicit_effects(
            "download this series over torrent",
            AVAILABLE | {"game.install.cancel.active"},
        )
        is None
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Avisame en veinte minutos", "notification.schedule"),
        ("Pon un timer de cinco minutos", "notification.schedule"),
        ("Describe lo que ves en la pantalla", "vision.describe"),
        ("Mira la imagen y dime quÃ© hay", "vision.describe"),
        ("Dile a Ana que llegare tarde por WhatsApp", "message.send"),
        ("Busca el contacto Ana en WhatsApp", "message.recipient.resolve"),
        ("Resolve the Music recipient on Discord", "message.recipient.resolve"),
    ],
)
def test_literal_operation_domains_preserve_matching_semantic_proposals(
    text: str,
    operation: str,
) -> None:
    assert operation_domain_is_grounded(text, operation) is True


@pytest.mark.parametrize(
    "text",
    [
        "news from c. n. n.",
        "is it going to rain at one p. m. today",
        "i want to hear the last news from c. n. n.",
        "alexa pon las noticias mÃ¡s populares de la t. v. e.",
    ],
)
def test_live_feed_queries_ground_web_search(
    text: str,
) -> None:
    assert operation_domain_is_grounded(text, "web.search") is True


@pytest.mark.parametrize(
    "text",
    [
        "estaban las acciones subiendo o bajando",
        "were stocks going up or down",
    ],
)
def test_market_direction_queries_ground_web_search(text: str) -> None:
    assert operation_domain_is_grounded(text, "web.search") is True
    result = resolve_explicit_effects(text, {"web.search"})
    assert result is not None
    assert result.operations == ("web.search",)


def test_named_market_price_query_is_a_deterministic_public_lookup() -> None:
    text = "averigüe el precio de las acciones de microsoft en nasdaq"

    assert operation_domain_is_grounded(text, "web.search") is True
    result = resolve_explicit_effects(text, {"web.search"})

    assert result is not None
    assert result.operations == ("web.search",)
    assert (
        unresolved_compound_contract(
            text,
            {"web.search"},
            resolved_intent=result,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "anything interesting going on in the bay area",
        "what events are happening near madrid",
        "hay algo interesante pasando en santiago",
    ],
)
def test_local_event_queries_resolve_to_verified_web_lookup(text: str) -> None:
    result = resolve_explicit_effects(text, {"web.search"})
    assert result is not None
    assert result.operations == ("web.search",)
    assert (
        unresolved_compound_contract(
            text,
            {"web.search"},
            resolved_intent=result,
        )
        is None
    )


def test_bare_authenticated_application_name_resolves_to_open() -> None:
    result = resolve_explicit_effects(
        "instagram",
        {"app.open"},
        ("Instagram",),
    )

    assert result is not None
    assert result.operations == ("app.open",)
    assert result.evidence == ("instagram",)


def test_authenticated_play_game_phrase_resolves_exact_installed_title() -> None:
    catalog = build_game_catalog_index((("steam", "123", "Fall Guys"),))
    result = resolve_explicit_effects(
        "Vamos a jugar al Fall Guys modo multijugador.",
        {"game.launch"},
        game_catalog=catalog,
    )

    assert result is not None
    assert result.operations == ("game.launch",)
    assert result.evidence == ("Fall Guys",)


def test_current_public_role_question_does_not_authorize_a_web_effect() -> None:
    assert (
        operation_domain_is_grounded(
            "quien es el actual primer ministro de rusia",
            "web.search",
        )
        is False
    )


@pytest.mark.parametrize(
    "text",
    [
        "news from c. n. n.",
        "is it going to rain at one p. m. today",
    ],
)
def test_live_feed_queries_resolve_to_verified_web_lookup(text: str) -> None:
    result = resolve_explicit_effects(text, {"web.search"})

    assert result is not None
    assert result.operations == ("web.search",)


@pytest.mark.parametrize(
    "text",
    [
        "do i need umbrella for night",
        "temperature outside",
        "yes or no tomorrow's temperature is to be hot",
    ],
)
def test_implicit_weather_queries_resolve_to_verified_web_lookup(text: str) -> None:
    result = resolve_explicit_effects(text, {"web.search"})

    assert result is not None
    assert result.operations == ("web.search",)
    assert (
        unresolved_compound_contract(
            text,
            {"web.search"},
            resolved_intent=result,
        )
        is None
    )


def test_corrected_nominal_product_request_resolves_to_safe_public_lookup() -> None:
    text = "Quiero una botella de leche. Bueno, mejor una botella de horchata."
    result = resolve_explicit_effects(text, {"web.search"})

    assert result is not None
    assert result.operations == ("web.search",)
    assert (
        unresolved_compound_contract(
            text,
            {"web.search"},
            resolved_intent=result,
        )
        is None
    )


def test_corrected_future_product_request_resolves_to_safe_public_lookup() -> None:
    text = "Voy a obtener dos pilas quiero decir tres."
    result = resolve_explicit_effects(text, {"web.search"})

    assert result is not None
    assert result.operations == ("web.search",)
    assert (
        unresolved_compound_contract(
            text,
            {"web.search"},
            resolved_intent=result,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "can i get take-out from pf changs",
        "Quiero una esterilla para que eeeeh para que me la envien a casa",
    ],
)
def test_read_only_commerce_queries_resolve_to_web_search(text: str) -> None:
    result = resolve_explicit_effects(text, {"web.search"})

    assert result is not None
    assert result.operations == ("web.search",)
    assert (
        unresolved_compound_contract(
            text,
            {"web.search"},
            resolved_intent=result,
        )
        is None
    )


def test_yes_no_envelope_does_not_hide_a_real_negative_instruction() -> None:
    result = resolve_explicit_effects(
        "yes or no: don't open Spotify",
        {"app.open"},
        ("Spotify",),
    )

    assert result is None
    assert (
        unresolved_compound_contract(
            "yes or no: don't open Spotify",
            {"app.open"},
            ("Spotify",),
            resolved_intent=result,
        )
        is not None
    )


def test_product_payment_request_is_known_unsupported_without_commerce() -> None:
    text = "Get me vanilla, wait, cinnamon using my American Express card."

    assert known_unsupported_effect_request(text, {"web.search"}) is True
    assert (
        known_unsupported_effect_request(
            text,
            {"commerce.product.purchase"},
        )
        is False
    )


def test_spoken_radio_station_resolves_as_media_query() -> None:
    result = resolve_explicit_effects(
        "pon kiss f. m. para mí",
        {"media.play.query"},
    )

    assert result is not None
    assert result.operations == ("media.play.query",)


def test_spoken_radio_frequency_resolves_as_media_query() -> None:
    result = resolve_explicit_effects(
        "tune in to eight hundred and ninety seven f. m.",
        {"media.play.query"},
    )

    assert result is not None
    assert result.operations == ("media.play.query",)


def test_corrected_installed_game_request_keeps_final_launch() -> None:
    text = "Quitar, eh quiero decir, poner el Fortnite."
    games = (("epic", "fortnite", "Fortnite"),)
    result = resolve_explicit_effects(text, {"game.launch"}, (), games)

    assert result is not None
    assert result.operations == ("game.launch",)
    assert (
        unresolved_compound_contract(
            text,
            {"game.launch"},
            (),
            games,
            resolved_intent=result,
        )
        is None
    )


def test_bare_spoken_number_title_resolves_as_media_query() -> None:
    result = resolve_explicit_effects(
        "por favor pon trece",
        {"media.play.query"},
    )

    assert result is not None
    assert result.operations == ("media.play.query",)


def test_desired_music_genre_resolves_as_media_query() -> None:
    result = resolve_explicit_effects(
        "i need some rap",
        {"media.play.query"},
    )

    assert result is not None
    assert result.operations == ("media.play.query",)


def test_desire_framed_named_song_resolves_as_media_query() -> None:
    result = resolve_explicit_effects(
        "quiero que me pongas rapsodia bohemia",
        {"media.play.query"},
    )

    assert result is not None
    assert result.operations == ("media.play.query",)


def test_write_a_note_resolves_as_note_creation() -> None:
    result = resolve_explicit_effects(
        "I want to write a note for someone",
        {"note.create"},
    )

    assert result is not None
    assert result.operations == ("note.create",)


def test_gift_discovery_resolves_as_safe_web_search() -> None:
    result = resolve_explicit_effects(
        "I need to find a present for mi madre.",
        {"web.search"},
    )

    assert result is not None
    assert result.operations == ("web.search",)


def test_infinitive_to_do_is_not_a_task_list_noun() -> None:
    assert (
        resolve_explicit_effects(
            "what do you want to do today",
            {"task.list"},
        )
        is None
    )


def test_absolute_calendar_range_query_is_bounded() -> None:
    text = (
        "during the timeframe of february one and march sixteen what meetings occurred"
    )
    result = resolve_explicit_effects(text, {"calendar.event.list"})

    assert result is not None
    assert result.operations == ("calendar.event.list",)


def test_bare_video_content_type_does_not_grant_media_authority() -> None:
    assert resolve_explicit_effects("pon vídeos", {"media.play.query"}) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Put on Joust, please.", False),
        ("Prepare Steam AppID 730 for installation", True),
        ("Show installation progress for game 730", True),
    ],
)
def test_game_app_id_operations_require_a_literal_app_id_domain(
    text: str,
    expected: bool,
) -> None:
    assert (
        operation_domain_is_grounded(
            text,
            "game.install.prepare",
        )
        is expected
    )


@pytest.mark.parametrize(
    "text",
    [
        "Abre calculadora y Spotify",
        "Crea una nota A y otra B",
        "Pon el volumen al 8% y luego al 12%",
        "¿Qué comen los gatos y los perros?",
        "Abre calculadora y gracias",
    ],
)
def test_fully_covered_or_non_effect_coordination_needs_no_partial_veto(
    text: str,
) -> None:
    assert unresolved_compound_contract(text, AVAILABLE) is None


def test_media_type_alternative_is_one_status_observation_not_two_effects() -> None:
    text = "Revisa qué pista o video suena ahora"
    result = resolve_explicit_effects(text, {"media.status"})

    assert result is not None
    assert result.operations == ("media.status",)
    assert (
        unresolved_compound_contract(
            text,
            {"media.status"},
            resolved_intent=result,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Abre calculadora y no abras Spotify",
        "Silencia el audio, no lo hagas",
        "Maximiza o minimiza la ventana activa",
        "No abras Spotify",
        "Open Notepad and type hello--actually, do neither.",
        "Abre Notepad y escribe hola; en realidad, no hagas ninguna de las dos.",
    ],
)
def test_negation_correction_and_alternatives_veto_semantic_authority(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None
    contract = unresolved_compound_contract(text, AVAILABLE)
    assert contract is not None
    assert contract.clause_requirements == ()


def test_partial_compound_preserves_source_order_for_independent_verification() -> None:
    contract = unresolved_compound_contract(
        "Abre calculadora y luego exporta el informe a Marte",
        AVAILABLE,
    )

    assert contract is not None
    assert contract.minimum_effects == 2
    assert contract.required_clause_sequences == (("app.open",),)
    assert contract.clause_requirements == (
        ("abre calculadora", ("app.open",)),
        ("exporta el informe a marte", ()),
    )


def test_compound_machine_context_disambiguates_a_bare_process_clause() -> None:
    text = "Dime la hora, revisa el estado del equipo y lista los procesos."

    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is not None
    assert result.operations == (
        "system.time",
        "system.status",
        "system.process.list",
    )


@pytest.mark.parametrize(
    "text",
    [
        "Dime la hora local",
        "Tell me the local time",
        "time now",
    ],
)
def test_local_time_is_the_current_machine_time(text: str) -> None:
    result = resolve_explicit_effects(text, {"system.time"})

    assert result is not None
    assert result.operations == ("system.time",)


@pytest.mark.parametrize(
    ("text", "available", "applications", "games", "expected"),
    [
        (
            "pega texto en un archivo nuevo de Notepad. Después dime la hora local.",
            {"app.open", "clipboard.paste", "system.time"},
            ("Notepad",),
            (),
            ("app.open", "clipboard.paste", "system.time"),
        ),
        (
            "Abre Counter Strike. Después dime la hora local.",
            {"game.launch", "system.time"},
            (),
            (("steam", "730", "Counter-Strike 2"),),
            ("game.launch", "system.time"),
        ),
        (
            "Abre Wikipedia y busca Alan Turing. Después dime la hora local.",
            {"web.search", "browser.navigate", "system.time"},
            (),
            (),
            ("web.search", "browser.navigate", "system.time"),
        ),
        (
            "Busca el botón Guardar y presiónalo. Después dime la hora local.",
            {"input.visible.click", "system.time"},
            (),
            (),
            ("input.visible.click", "system.time"),
        ),
        (
            "conecta el wifi, abre el correo y leeme el ultimo mensaje. "
            "Después dime la hora local.",
            {"wifi.ensure.connected", "email.latest.read", "system.time"},
            (),
            (),
            ("wifi.ensure.connected", "email.latest.read", "system.time"),
        ),
        (
            "Crea un documento Word llamado Informe y después lee ese mismo "
            "documento que acabas de crear. Después dime la hora local.",
            {
                "office.document.create",
                "office.document.read",
                "system.time",
            },
            (),
            (),
            ("office.document.create", "office.document.read", "system.time"),
        ),
        (
            "Primero enumera mi catálogo local de Steam y después comprueba el "
            "estado de instalación del AppID 945360. Después dime la hora local.",
            {"game.catalog.list", "game.install.status", "system.time"},
            (),
            (),
            ("game.catalog.list", "game.install.status", "system.time"),
        ),
    ],
)
def test_clause_local_special_missions_compose_with_an_independent_tail(
    text: str,
    available: set[str],
    applications: tuple[str, ...],
    games: tuple[tuple[str, str, str], ...],
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(
        text,
        available,
        applications,
        games,
    )

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    "text",
    [
        "No crees un documento Word llamado Informe y después lo leas.",
        "No compruebes el estado de instalación del AppID 945360.",
    ],
)
def test_clause_local_special_missions_do_not_bypass_negation(text: str) -> None:
    assert (
        resolve_explicit_effects(
            text,
            {
                "office.document.create",
                "office.document.read",
                "game.install.status",
            },
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        (
            "Could you Without skipping any, inspect in this order: today's "
            "appointments; then, what is currently playing; then, reminders "
            "still scheduled; then, overall system health; then, attached "
            "physical accessories; then, the newly arrived email's contents"
        ),
        (
            "Hey Baxy — could you Run this check in parts: today's appointments; "
            "then, what is currently playing; then, reminders still scheduled; "
            "then, overall system health; then, attached physical accessories; "
            "then, the newly arrived email's contents, returning each result "
            "separately."
        ),
    ],
)
def test_wrapped_catalog_reports_accept_premodified_peripheral_phrases(
    text: str,
) -> None:
    expected = (
        "calendar.event.list",
        "media.status",
        "reminder.list",
        "system.status",
        "peripheral.list",
        "email.latest.read",
    )

    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected


def test_spanglish_latest_email_read_is_not_a_message_send() -> None:
    result = resolve_explicit_effects(
        "Please, Lee el message que arrived last al correo",
        {"email.latest.read", "message.recipient.resolve", "message.send"},
    )

    assert result is not None
    assert result.operations == ("email.latest.read",)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Oye, por favor, necesito un parte conjunto de el texto listo para "
            "pegar; después, la señal y enlace Wi-Fi; después, los avisos "
            "vencidos; después, las rutinas personales guardadas; después, los "
            "accesorios físicos conectados; después, lo que se está reproduciendo",
            (
                "clipboard.read.text",
                "wifi.status",
                "notification.list.due",
                "routine.list",
                "peripheral.list",
                "media.status",
            ),
        ),
        (
            "Listen, please, i need a combined report covering overall system "
            "health; then, audio volume and output; then, the browser's open "
            "pages; then, attached physical accessories",
            (
                "system.status",
                "audio.status",
                "browser.tabs.list",
                "peripheral.list",
            ),
        ),
        (
            "Oye, por favor, obtén una captura y usa precisamente esa imagen "
            "para transcribir sus letras visibles",
            ("capture.screenshot", "ocr.read"),
        ),
        (
            "A ver, por favor, por WhatsApp dile a Fernanda que llego en quince "
            "y después enséñame las tareas abiertas",
            ("message.recipient.resolve", "message.send", "task.list"),
        ),
        (
            "Listen, please, show the open tasks, capture that resulting screen, "
            "and read the text in the capture",
            ("task.list", "capture.screenshot", "ocr.read"),
        ),
        (
            "Listen, por favor, display today's calendar, screenshot it, describe "
            "esa view y then read clipboard text",
            (
                "calendar.event.list",
                "capture.screenshot",
                "vision.describe",
                "clipboard.read.text",
            ),
        ),
    ],
)
def test_discourse_wrapped_reports_and_dependent_reads_preserve_every_step(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Hazme este chequeo por partes: la salud global del sistema; "
            "después, los avisos vencidos",
            ("system.status", "notification.list.due"),
        ),
        (
            "I need a combined report covering the text ready to paste; then, "
            "games in the local catalog",
            ("clipboard.read.text", "game.catalog.list"),
        ),
        (
            "Without skipping ninguno, revisa in order: games del local catalog; "
            "después check, physical accessories conectados",
            ("game.catalog.list", "peripheral.list"),
        ),
        (
            "Ve punto por punto con el acceso general a la red; después, las "
            "páginas abiertas del navegador",
            ("network.status", "browser.tabs.list"),
        ),
    ],
)
def test_closed_catalog_report_pairs_preserve_both_reads(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Please. One small request. Without skipping any. Inspect in this "
            "order. Saved personal routines. Then. Overdue notices. Then. The "
            "Wi-Fi link and signal. Returning each result separately.",
            ("routine.list", "notification.list.due", "wifi.status"),
        ),
        (
            "Oye, a ver, una solicitud rápida, hazme este chequeo por partes, "
            "las tareas que siguen abiertas, después, lo que se está "
            "reproduciendo, después, los avisos vencidos, devolviendo cada "
            "resultado por separado.",
            ("task.list", "media.status", "notification.list.due"),
        ),
        (
            "One thing, please, when you have a minute, go point by point "
            "through attached physical accessories, then, saved personal "
            "routines, returning each result separately.",
            ("peripheral.list", "routine.list"),
        ),
    ],
)
def test_spoken_catalog_reports_do_not_depend_on_dictated_punctuation(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    "text",
    [
        "Run this check in parts. Overall system health. Then. An unknown domain.",
        "Hazme este chequeo por partes, la salud global del sistema, después, no revises el audio.",
        "Without skipping any. Inspect in this order. Overall system health. Then. Overall system health.",
    ],
)
def test_spoken_catalog_reports_still_fail_closed(text: str) -> None:
    assert (
        resolve_explicit_effects(
            text,
            {"system.status", "audio.status"},
        )
        is None
    )


def test_spoken_catalog_report_accepts_de_el_contraction_without_losing_media() -> None:
    expected = (
        "note.list",
        "notification.list.due",
        "media.status",
        "task.list",
    )
    result = resolve_explicit_effects(
        "Necesito un parte conjunto del índice de notas privadas, después, los "
        "avisos vencidos, después, lo que se está reproduciendo, después, las "
        "tareas que siguen abiertas, devolviendo cada resultado por separado.",
        set(expected),
    )

    assert result is not None
    assert result.operations == expected


def test_corrupted_spoken_report_wrapper_cannot_authorize_a_partial_subset() -> None:
    assert (
        resolve_explicit_effects(
            "Necesito a can by in report the saved personal routines, después check, "
            "today's appointments, después check, what is plain hora, después check, "
            "reminders still scheduled, returning cada result por separado.",
            {
                "routine.list",
                "calendar.event.list",
                "media.status",
                "reminder.list",
            },
        )
        is None
    )


def test_corrupted_message_recipient_cannot_absorb_a_following_task_lookup() -> None:
    assert (
        resolve_explicit_effects(
            "Dile aún me por WhatsApp que llego en 50 minutos y luego lista mis "
            "tareas abiertas.",
            {"message.recipient.resolve", "message.send", "task.list"},
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        (
            "Oye, por favor, cuando tengas un minuto, escríbele por WhatsApp "
            "a Nadia, el acceso ya quedó habilitado."
        ),
        (
            "One thing. Please. When you have a minute. Write to Sage on "
            "WhatsApp. Access has now been enabled."
        ),
    ],
)
def test_spoken_message_body_accepts_asr_sentence_punctuation(text: str) -> None:
    result = resolve_explicit_effects(
        text,
        {"message.recipient.resolve", "message.send"},
    )

    assert result is not None
    assert result.operations == ("message.recipient.resolve", "message.send")


@pytest.mark.parametrize(
    "text",
    [
        "Escríbele por WhatsApp a Nadia.",
        "Write to Sage on WhatsApp.",
    ],
)
def test_spoken_message_punctuation_without_body_still_fails_closed(
    text: str,
) -> None:
    assert (
        resolve_explicit_effects(
            text,
            {"message.recipient.resolve", "message.send"},
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Run this check in parts: overall system health; then, an unknown domain",
        "Run this check in parts: overall system health; then, overall system health",
        "Run this check in parts: overall system health; then, do not inspect audio output",
    ],
)
def test_closed_catalog_report_pairs_reject_incomplete_or_unsafe_reads(
    text: str,
) -> None:
    result = resolve_explicit_effects(
        text,
        {"system.status", "audio.status"},
    )

    assert result is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Capture la pantalla y read every visible word from that exact image",
            ("capture.screenshot", "ocr.read"),
        ),
        (
            "Show tomorrow's events, capture that view, describe the image, then "
            "read the clipboard text",
            (
                "calendar.event.list",
                "capture.screenshot",
                "vision.describe",
                "clipboard.read.text",
            ),
        ),
        (
            "Captura el escritorio, describe la escena y transcribe el texto de "
            "esa misma imagen",
            ("capture.screenshot", "vision.describe", "ocr.read"),
        ),
        (
            "Cuando tengas un minuto, please capture the desktop, describe esa "
            "imagen y read every word visible in the same capture",
            ("capture.screenshot", "vision.describe", "ocr.read"),
        ),
        (
            "Muestra los eventos de mañana, captura esa vista, describe la imagen "
            "y lee el texto del portapapeles",
            (
                "calendar.event.list",
                "capture.screenshot",
                "vision.describe",
                "clipboard.read.text",
            ),
        ),
    ],
)
def test_natural_dependent_read_variants_preserve_prerequisites(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, set(expected))

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Cuando tengas un minuto, please how anda el volume y la output "
            "route? Check it",
            ("audio.status",),
        ),
        (
            "Oye, Baxy: cuando tengas un minuto, please check con qu\N{LATIN SMALL LETTER E WITH ACUTE} "
            "layout estoy typing.",
            ("input.keyboard.status",),
        ),
        (
            "Una solicitud r\N{LATIN SMALL LETTER A WITH ACUTE}pida: "
            "\N{LATIN SMALL LETTER E WITH ACUTE}chale un vistazo a los programas y confirma la "
            "presencia de VLC media player",
            ("app.installed",),
        ),
        (
            "A quick request, por favor: have a look en los programas locales "
            "for VLC media player",
            ("app.installed",),
        ),
        (
            "Una solicitud r\N{LATIN SMALL LETTER A WITH ACUTE}pida: ens\N{LATIN SMALL LETTER E WITH ACUTE}ñame los eventos "
            "de ma\N{LATIN SMALL LETTER N WITH TILDE}ana, toma una captura de esa vista, describe lo "
            "que aparece y despu\N{LATIN SMALL LETTER E WITH ACUTE}s lee el texto del portapapeles",
            (
                "calendar.event.list",
                "capture.screenshot",
                "vision.describe",
                "clipboard.read.text",
            ),
        ),
    ],
)
def test_r14_opened_residuals_have_bounded_systemic_routes(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(
        text,
        set(AVAILABLE) | set(expected),
        ("VLC media player", "Krita"),
    )

    assert result is not None
    assert result.operations == expected


def test_r15_address_and_message_task_chain_preserve_closed_authority() -> None:
    addressed = resolve_explicit_effects(
        "Che, Baxy: one small request, porfa: quiero see el complete index de "
        "local notes.",
        {"note.list", "note.search", "notification.diagnose"},
    )
    chained = resolve_explicit_effects(
        "A ver, una solicitud r\N{LATIN SMALL LETTER A WITH ACUTE}pida: dile a Zoe por WhatsApp que "
        "llego en cuarenta minutos y luego lista mis tareas abiertas",
        {"message.recipient.resolve", "message.send", "task.list"},
    )
    note_chained = resolve_explicit_effects(
        "Avísale a Iris por WhatsApp que llegaré en cuarenta minutos y después "
        "lista mis notas",
        {"message.recipient.resolve", "message.send", "note.list"},
    )
    knowledge = resolve_explicit_effects(
        "Che, Baxy: a small question: What is a notification?",
        AVAILABLE,
    )

    assert addressed is not None
    assert addressed.operations == ("note.list",)
    assert chained is not None
    assert chained.operations == (
        "message.recipient.resolve",
        "message.send",
        "task.list",
    )
    assert note_chained is not None
    assert note_chained.operations == (
        "message.recipient.resolve",
        "message.send",
        "note.list",
    )
    assert knowledge is None


@pytest.mark.parametrize(
    "text",
    [
        "A question: Rewrite the sentence close every tab more politely",
        "A question: Compare reminders with notifications without checking my data",
        "Una duda: Dame una receta de risotto para una mañana ventosa",
        "Por curiosidad: Simula una conversación, no envíes nada, entre Ana y Luis",
    ],
)
def test_discourse_wrapped_content_work_never_grants_effect_authority(
    text: str,
) -> None:
    assert conversation_only_content_request(text) is True
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    ("text", "available", "expected"),
    [
        (
            "Lista mis tareas pendientes. Después abre mi biblioteca de Steam.",
            {"task.list", "game.catalog.list"},
            ("task.list", "game.catalog.list"),
        ),
        (
            "Lista mis notas. Después abre mi biblioteca de Steam.",
            {"note.list", "game.catalog.list"},
            ("note.list", "game.catalog.list"),
        ),
        (
            "Lista los procesos activos. Después abre mi biblioteca de Steam.",
            {"system.process.list", "game.catalog.list"},
            ("system.process.list", "game.catalog.list"),
        ),
        (
            "Dime la hora local. Después anota que tengo que llamar al medico manana.",
            {"system.time", "note.create"},
            ("system.time", "note.create"),
        ),
        (
            "Lista mis tareas pendientes. Después anota que tengo que llamar al "
            "medico manana.",
            {"task.list", "note.create"},
            ("task.list", "note.create"),
        ),
        (
            "Lista mis notas. Después anota que tengo que llamar al medico manana.",
            {"note.list", "note.create"},
            ("note.list", "note.create"),
        ),
        (
            "Lista los procesos activos. Después anota que tengo que llamar al "
            "medico manana.",
            {"system.process.list", "note.create"},
            ("system.process.list", "note.create"),
        ),
    ],
)
def test_independent_prefixes_do_not_get_absorbed_by_later_special_families(
    text: str,
    available: set[str],
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    ("text", "available", "expected"),
    [
        (
            "Take a screenshot; after that, read it with OCR.",
            {"capture.screenshot", "ocr.read"},
            ("capture.screenshot", "ocr.read"),
        ),
        (
            "Connect Wi-Fi; after that, read the latest email.",
            {"wifi.ensure.connected", "email.latest.read"},
            ("wifi.ensure.connected", "email.latest.read"),
        ),
        (
            "List the active processes, tell me the time, and check the computer status.",
            {"system.process.list", "system.time", "system.status"},
            ("system.process.list", "system.time", "system.status"),
        ),
        (
            "Crea una nota titulada Alfa con contenido primero, después crea una nota "
            "titulada Beta con contenido segundo, y finalmente lee la primera nota.",
            {"note.create", "note.read"},
            ("note.create", "note.create", "note.read"),
        ),
        (
            "Create note Alpha with first. Then create note Beta with second. "
            "Finally read the first note.",
            {"note.create", "note.read"},
            ("note.create", "note.create", "note.read"),
        ),
        (
            "Dime la hora local; después silencia el audio; finalmente cambia "
            "el volumen a 10.",
            {"system.time", "audio.mute", "audio.volume"},
            ("system.time", "audio.mute", "audio.volume"),
        ),
        (
            "Primero, dime la hora local. Luego silencia el audio. Finalmente "
            "cambia el volumen a 10.",
            {"system.time", "audio.mute", "audio.volume"},
            ("system.time", "audio.mute", "audio.volume"),
        ),
        (
            "Lista mis tareas pendientes, y luego abre el archivo más reciente "
            "de Descargas, y finalmente pon el volumen al 17 por ciento.",
            {"task.list", "filesystem.file.open.latest", "audio.volume"},
            ("task.list", "filesystem.file.open.latest", "audio.volume"),
        ),
        (
            "Lista mis tareas pendientes; después abre mi biblioteca de Steam; "
            "finalmente pon el volumen al 17 por ciento.",
            {"task.list", "game.catalog.list", "audio.volume"},
            ("task.list", "game.catalog.list", "audio.volume"),
        ),
        (
            "conecta el wifi, abre el correo y leeme el ultimo mensaje, y luego "
            "dime la hora local, y finalmente silencia el audio.",
            {
                "wifi.ensure.connected",
                "email.latest.read",
                "system.time",
                "audio.mute",
            },
            (
                "wifi.ensure.connected",
                "email.latest.read",
                "system.time",
                "audio.mute",
            ),
        ),
        (
            "Primero, alarma para mañana 8am. Luego dime la hora local. "
            "Finalmente silencia el audio.",
            {"notification.schedule", "system.time", "audio.mute"},
            ("notification.schedule", "system.time", "audio.mute"),
        ),
        (
            "Dime la hora local. Después de eso, recordatorio de tomar agua en "
            "1 hora. Finalmente, silencia el audio.",
            {"system.time", "reminder.create", "audio.mute"},
            ("system.time", "reminder.create", "audio.mute"),
        ),
        (
            "Quita la alarma de las cinco de la tarde; después dime la hora "
            "local; finalmente silencia el audio.",
            {"notification.cancel.at", "system.time", "audio.mute"},
            ("notification.cancel.at", "system.time", "audio.mute"),
        ),
        (
            "Lista mis tareas. Después de eso, ¿qué hora es ahora. "
            "Finalmente, pon el audio en silencio.",
            {"task.list", "system.time", "audio.mute"},
            ("task.list", "system.time", "audio.mute"),
        ),
        (
            "Primero, ¿qué hora marca este equipo. Luego lista mis tareas. "
            "Finalmente deja el sonido en mudo.",
            {"system.time", "task.list", "audio.mute"},
            ("system.time", "task.list", "audio.mute"),
        ),
    ],
)
def test_compound_metamorphic_connectors_and_order_preserve_effects(
    text: str,
    available: set[str],
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Enumera los procesos activos.", "system.process.list"),
        ("Enumerate active processes.", "system.process.list"),
        ("Adjust the volume to 17 percent.", "audio.volume"),
        ("Change the sound to 17 percent.", "audio.volume"),
        ("Añade una tarea llamada Cola Matriz.", "task.create"),
        ("Agrega Cola Matriz como tarea.", "task.create"),
        ("Añade una nota llamada Cola Matriz que diga verificado.", "note.create"),
        ("Guarda una nota Cola Matriz con el texto verificado.", "note.create"),
    ],
)
def test_lexical_tail_paraphrases_resolve_exactly(
    text: str,
    operation: str,
) -> None:
    result = resolve_explicit_effects(text, {operation})

    assert result is not None
    assert result.operations == (operation,)


def test_lexical_question_and_mute_heads_split_across_semicolons() -> None:
    result = resolve_explicit_effects(
        "Abre Calculadora; ¿qué hora marca este equipo; deja el sonido en mudo.",
        {"app.open", "system.time", "audio.mute"},
        ["Calculadora"],
    )

    assert result is not None
    assert result.operations == ("app.open", "system.time", "audio.mute")


@pytest.mark.parametrize(
    "text",
    [
        "Set volume to 10% on my phone, then mute audio.",
        "Set volume to 10% on my phone, then connect Wi-Fi.",
        "Turn on Bluetooth on my phone.",
    ],
)
def test_other_device_scope_blocks_explicit_and_compound_authority(
    text: str,
) -> None:
    available = {"audio.volume", "audio.mute"}

    assert resolve_explicit_effects(text, available) is None
    contract = unresolved_compound_contract(text, available)
    assert contract is not None
    assert contract.clause_requirements == ()


def test_local_pairing_request_does_not_look_like_remote_device_scope() -> None:
    text = "Pair my phone over Bluetooth."

    assert (
        unresolved_compound_contract(
            text,
            {"bluetooth.device.pair"},
        )
        is None
    )


def test_explicit_text_source_is_grounded_for_clipboard_copy() -> None:
    text = "Copia texto de Notepad al portapapeles"

    assert operation_domain_is_grounded(text, "clipboard.copy") is True
    resolved = resolve_explicit_effects(text, AVAILABLE)
    assert resolved is not None
    assert resolved.operations == ("clipboard.copy",)


@pytest.mark.parametrize(
    ("text", "operation", "missing_fields"),
    [
        (
            "Lee con OCR la última captura",
            "ocr.read",
            ("image_or_new_screenshot",),
        ),
        (
            "Lista mis próximos eventos del calendario",
            "calendar.event.list",
            ("date_range",),
        ),
    ],
)
def test_incomplete_effect_asks_only_for_its_missing_contract_data(
    text: str,
    operation: str,
    missing_fields: tuple[str, ...],
) -> None:
    intent = resolve_explicit_clarification_intent(text, {operation})

    assert intent is not None
    assert intent.operations == (operation,)
    assert intent.missing_fields == missing_fields


@pytest.mark.parametrize(
    ("text", "operation", "missing_fields"),
    [
        (
            "Quiero jugar a algún juego de estrategia, quiero decir de plataformas",
            "game.launch",
            ("game_title",),
        ),
        (
            "Can you make a new shared, no, personal note.",
            "note.create",
            ("note_content",),
        ),
    ],
)
def test_self_corrected_incomplete_effect_keeps_intent_without_recovery(
    text: str,
    operation: str,
    missing_fields: tuple[str, ...],
) -> None:
    intent = resolve_explicit_clarification_intent(text, {operation})

    assert intent is not None
    assert intent.operations == (operation,)
    assert intent.missing_fields == missing_fields


@pytest.mark.parametrize(
    "text",
    [
        "Lista el calendario entre 2026-07-16 y 2026-07-17.",
        "Lista el calendario entre 2026-07-16T04:00:00Z y 2026-07-17T04:00:00Z.",
    ],
)
def test_calendar_iso_date_or_datetime_is_complete_contract_data(text: str) -> None:
    assert resolve_explicit_clarification(text, {"calendar.event.list"}) is None


@pytest.mark.parametrize("text", [
    "¿Con qué cuenta de Windows se está ejecutando BAXY?",
    "Which Windows account is running BAXY?",
    "What is my Windows username?",
    "Dime la cuenta actual de Windows.",
    "Dime mi usuario de Windows y cuánta RAM tengo",
    "Show my Windows account and CPU usage",
])
def test_account_read_is_not_satisfied_by_machine_resource_status(text: str) -> None:
    # Resource/OS observations cannot supply the effective account. Decline
    # instead of forcing identity: the ordinary catalog selection owns that.
    assert resolve_explicit_effects(text, {"system.status", "system.identity"}) is None


@pytest.mark.parametrize("text", [
    "Which Windows version am I running?",
    "Dime la versión de Windows que tengo",
    "Qué Windows tengo y cuánta RAM tiene esta máquina",
    "Dime el uso actual de la CPU.",
    "Check the GPU identity",
    "Revisa la identidad de la GPU",
])
def test_resource_identity_stays_with_machine_status(text: str) -> None:
    result = resolve_explicit_effects(text, {"system.status", "system.identity"})
    assert result is not None
    assert result.operations == ("system.status",)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Cabezas interrogativas de cantidad, con y sin tilde.
        ("¿Cuánta batería queda?", ("system.status",)),
        ("cuanta bateria queda", ("system.status",)),
        ("CUÁNTA BATERÍA QUEDA", ("system.status",)),
        ("¿Cuántos núcleos tiene el procesador?", ("system.status",)),
        ("¿Cuánta VRAM se está usando?", ("system.status",)),
        ("¿Cuánto espacio libre queda en el disco?", ("system.status",)),
        ("How much battery is left?", ("system.status",)),
        ("How much free space do I have left on disk", ("system.status",)),
        # Formas nominales sin verbo.
        ("Nivel de carga de la batería", ("system.status",)),
        ("Uso de GPU ahora", ("system.status",)),
        ("battery level please", ("system.status",)),
        ("gpu usage right now", ("system.status",)),
        # Verbos de observación.
        ("Chequea la VRAM por favor", ("system.status",)),
        ("Fíjate cuánta batería le queda al notebook", ("system.status",)),
        ("Che BAXY, revisa la batería", ("system.status",)),
        # Identidad de GPU y versión de Windows.
        ("¿Qué GPU tiene este equipo?", ("system.status",)),
        ("which graphics card do i have", ("system.status",)),
        ("Dime la versión de Windows que tengo", ("system.status",)),
        # Estado de audio: nivel y silencio.
        ("¿En cuánto está el volumen ahora?", ("audio.status",)),
        ("Is the sound muted right now?", ("audio.status",)),
        ("¿Está silenciado el audio ahora?", ("audio.status",)),
        ("¿A qué volumen está el sonido?", ("audio.status",)),
        ("Muéstrame el volumen actual", ("audio.status",)),
        ("show me the volume", ("audio.status",)),
        ("¿Qué volumen tiene puesto la PC?", ("audio.status",)),
        ("check el volumen de la compu", ("audio.status",)),
        # Silencio global: sinónimos y reversión.
        ("Mutea el sonido", ("audio.mute",)),
        ("Desmutea el audio", ("audio.mute",)),
        ("unmute please", ("audio.mute",)),
        ("Quita el silencio del audio", ("audio.mute",)),
        ("Apaga el sonido del sistema", ("audio.mute",)),
        ("Pon en mudo el equipo", ("audio.mute",)),
        ("Activa el sonido de nuevo", ("audio.mute",)),
        ("turn the sound back on", ("audio.mute",)),
        # Volumen con poseedor explícito del equipo.
        ("Pon el volumen de la compu al 30 por ciento", ("audio.volume",)),
        # Composición: dos lecturas distintas conservan su orden.
        (
            "Revisa la batería y silencia el audio",
            ("system.status", "audio.mute"),
        ),
        ("Dime la hora y revisa la batería", ("system.time", "system.status")),
    ],
)
def test_state_questions_are_recognized_across_languages_and_forms(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    "text",
    [
        # Negación y prohibición.
        "No revises la batería",
        "No me digas cuánta RAM tengo",
        "don't check the gpu",
        "Nunca revises el disco",
        "Sin revisar la GPU, cuéntame un chiste",
        # Conocimiento general de hardware, no medición de este equipo.
        "¿Qué es la VRAM exactamente?",
        "how much vram does a 4090 have",
        "¿Cuánta RAM necesita un juego moderno?",
        "which cpu is better for gaming",
        "¿Qué GPU me recomiendas comprar?",
        # Diagnóstico causal y atribución por proceso.
        "¿Por qué mi GPU no se usa?",
        "¿Qué está usando la VRAM ahora?",
        "¿Hay algo más usando la GPU ahora?",
        "¿Qué proceso me come tanta RAM?",
        # Fuera del enum medido.
        "¿A qué temperatura está la GPU?",
        "gpu temp right now",
        # Otro dispositivo, no este computador.
        "¿Cuánta batería tiene mi auto?",
        "¿Cuánta batería le queda al celular?",
        # Ámbito de aplicación.
        "¿Cuánta VRAM usa Chrome?",
        "Silencia el audio de Spotify",
        "is spotify muted",
        "¿Está muteado el micrófono?",
        "mute my mic in the call",
        # Estado pasado o hipotético: no es una observación de ahora.
        "¿Cuánta batería tenía ayer?",
        "¿Cuánta RAM tendría con 32 GB?",
        "¿En cuánto estaba el volumen anoche?",
        "¿Cómo estaba la GPU la semana pasada?",
        # Observación sostenida y condicionales.
        "Revisa la GPU mientras corre el entrenamiento",
        "Si queda poca batería silencia el audio",
        "Chequea la RAM y si está llena cierra Chrome",
        # Reporte del usuario, no petición.
        "Ya silencié el audio yo mismo",
        "Le puse mute a la tele recién",
        "La GPU es una 3060 según el vendedor",
        # Memoria privada del asistente, no memoria del equipo.
        "¿Cuánta memoria tienes de mí?",
        "¿Qué recuerdas de mi cumpleaños?",
        # Dos alcances que el catálogo no mide en una sola lectura.
        "¿Cuánta batería queda y cuánta RAM tengo?",
        "¿Cuánto disco libre hay y cuánta batería queda?",
        # Casos reales del corpus histórico de 14.836 mensajes.
        "Cuanta ram usa parekeet?",
        "Cuanta vram uisa el modelo de qwen?",
        "Que esta usndo vram ahora??",
        "how many windows open",
        "cuanto pesa GTA V en mi disco",
        "muestra el nombre del PC y el usuario actual",
        "muestra la hora, mi IP y mi RAM",
        "show time, IP and RAM",
        "decime la hora y cuánta batería tengo",
        "is dictation available on my PC?",
        "cómo cuidas mi PC?",
        "Como va la rapidez del finetuning? cerre todo en mi pc para eso",
        "hay algun checkpoint mas reciente??, puedo reinicar el pc para ti",
        "Modelo FT Q4_K_M (no el QAT), visión residente en GPU, ctx 12288",
        "VRAM crece > 5.5 GB con --swa-full y OOM",
        "Me interesa el mobile, investiga cuanta vram usara realmente",
        "Dime qué dispositivo de audio está activo",
        # «apagar la música» detiene la reproducción; no silencia el equipo.
        "Apaga la musica",
        # Una coordinación con otro dominio no puede ejecutarse a medias.
        "mute the sound and dim the screen",
    ],
)
def test_state_lookalikes_never_gain_deterministic_authority(text: str) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("¿Por qué mi GPU no se usa?", "system.status"),
        ("¿Qué está usando la VRAM ahora?", "system.status"),
        ("¿A qué temperatura está la GPU?", "system.status"),
        ("¿Cuánta batería tiene mi auto?", "system.status"),
        ("¿Cuánta batería tenía ayer?", "system.status"),
        ("¿Cuánta memoria tienes de mí?", "system.status"),
        ("¿Cómo está el equipo de fútbol?", "system.status"),
        ("Sube el volumen de ventas en 2 puntos", "audio.volume.adjust"),
    ],
)
def test_state_lookalikes_also_veto_semantic_state_proposals(
    text: str,
    operation: str,
) -> None:
    assert operation_domain_is_grounded(text, operation) is False


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuánta batería queda?",
        "¿Cuánta VRAM se está usando?",
        "Is the sound muted right now?",
        "¿En cuánto está el volumen ahora?",
        "Mutea el sonido",
    ],
)
def test_recognized_state_questions_never_invent_an_absent_operation(
    text: str,
) -> None:
    assert resolve_explicit_effects(text, {"system.time"}) is None


@pytest.mark.parametrize(
    "text",
    ["y la fecha?", "la fecha", "¿La hora?", "and the date?", "the time?"],
)
def test_nominal_datetime_query_does_not_lose_a_contextual_proposal(text: str) -> None:
    assert operation_domain_is_grounded(text, "system.time") is True


@pytest.mark.parametrize("text,expected", [
    ("Dime la hora, el audio y el uso de CPU.",
     ("system.time", "audio.status", "system.status")),
    ("Dime el uso de CPU, el audio y la hora.",
     ("system.status", "audio.status", "system.time")),
    ("Tell me the time, audio, and CPU usage.",
     ("system.time", "audio.status", "system.status")),
    ("Dime la hora y el estado del audio.", ("system.time", "audio.status")),
    ("Tell me the time and the volume.", ("system.time", "audio.status")),
    ("What time is it y cómo está el audio?", ("system.time", "audio.status")),
    ("Dime el estado del audio y la hora.", ("audio.status", "system.time")),
    ("Show the date and the volume.", ("system.time", "audio.status")),
    ("Dime la hora, revisa el estado del audio y dime el uso de CPU.",
     ("system.time", "audio.status", "system.status")),
])
def test_coordinated_clock_reads_preserve_order_and_catalog_completeness(
    text: str, expected: tuple[str, ...],
) -> None:
    available = {"system.time", "audio.status", "system.status"}
    result = resolve_explicit_effects(text, available)
    assert result is not None
    assert result.operations == expected
    for missing in expected:
        assert resolve_explicit_effects(text, available - {missing}) is None


@pytest.mark.parametrize("text", [
    "Tell me the CPU time and the volume.",
    "Dime la fecha de la reunión y el estado del audio.",
    "Dime la hora de cierre y el estado del audio.",
    "Tell me the time needed to download it and the volume.",
    "Read the words time and volume.",
    "Explica la hora y el estado del audio.",
])
def test_coordinated_clock_lookalikes_do_not_authorize_local_time(text: str) -> None:
    result = resolve_explicit_effects(text, {"system.time", "audio.status", "system.status"})
    assert result is None or "system.time" not in result.operations


@pytest.mark.parametrize(
    "text",
    [
        "la fecha de la reunión",
        "y la fecha de nacimiento?",
        "the date of the event?",
        "the time needed to download it",
        "qué es una fecha",
        "what is time?",
        "no me digas la fecha",
    ],
)
def test_qualified_or_nonrequested_datetime_is_not_the_local_clock(text: str) -> None:
    assert operation_domain_is_grounded(text, "system.time") is False


@pytest.mark.parametrize("current,previous,expected", [
    ("y la fecha?", "Dime que hora es", True),
    ("and the date?", "what time is it?", True),
    ("y la fecha?", None, False),
    ("y la fecha?", "cuándo nació Ada Lovelace", False),
    ("y la fecha?", "No me digas la hora", False),
    ("y la fecha de nacimiento?", "Dime que hora es", False),
    ("no me digas la fecha", "Dime que hora es", False),
])
def test_datetime_followup_inherits_only_a_resolved_user_clock_request(
    current: str, previous: str | None, expected: bool,
) -> None:
    result = resolve_explicit_effects(current, {"system.time"}, previous_user_text=previous)
    assert (result is not None) is expected
    if result is not None:
        assert result.operations == ("system.time",)


def test_datetime_followup_does_not_create_an_absent_operation() -> None:
    assert resolve_explicit_effects(
        "y la fecha?", {"audio.status"}, previous_user_text="Dime que hora es",
    ) is None


# Un saludo delante de la petición no cambia el acto de habla: sólo desplaza la
# cabeza del pedido, igual que el vocativo que ya se retiraba. Cada par compara
# la misma petición con y sin envoltura social, así que la prueba falla tanto si
# el saludo bloquea el reconocimiento como si la petición desnuda dejara de
# resolverse.
@pytest.mark.parametrize(
    ("bare", "wrapped"),
    [
        ("¿Qué hora es?", "Hola, ¿qué hora es?"),
        ("¿Qué hora es?", "Buenos días, ¿qué hora es?"),
        ("¿Qué hora es?", "hello, what time is it?"),
        ("¿Cuánta batería queda?", "Hola, ¿cuánta batería queda?"),
        ("¿Cuánta batería queda?", "Buenas tardes, ¿cuánta batería queda?"),
        ("Pon el volumen al 8 por ciento", "Hola, pon el volumen al 8 por ciento"),
        ("Mute everything please", "Hi, mute everything please"),
        ("Mute everything please", "Hello Baxy, mute everything please"),
        ("Abre la calculadora", "Hola, abre la calculadora"),
    ],
)
def test_a_leading_greeting_does_not_hide_the_request(
    bare: str,
    wrapped: str,
) -> None:
    expected = resolve_explicit_effects(bare, AVAILABLE)

    assert expected is not None
    result = resolve_explicit_effects(wrapped, AVAILABLE)
    assert result is not None
    assert result.operations == expected.operations
    assert result.kind == expected.kind


_SOCIAL_ENVELOPES = (
    "Hola, ",
    "hola baxy, ",
    "Baxy, ",
    "Buenos días, ",
    "Buenas tardes, ",
    "Buenas noches, ",
    "Buenas, ",
    "Hola baxy: ",
    "Hi, ",
    "Hello, ",
    "Hey, ",
    "Good morning, ",
    "Hello Baxy, ",
    "Cuando puedas, ",
    "Una petición rápida: ",
    "When you have a moment, ",
    "One quick request: ",
    "A propósito: ",
    "Tengo una pregunta: ",
    "I was wondering: ",
    "Baxy, escucha: ",
    "Baxy, listen: ",
    # Speech recognizers routinely render an explicit wrapper boundary as a
    # sentence stop instead of preserving the source comma or colon.
    "Please. One small request. ",
    "One quick request. ",
    "Hello. ",
    "Baxy. ",
    "Oye. ",
    "Te dejo una instrucción concreta para este computador: ",
    "Te paso una indicación específica para el equipo: ",
    "Necesito que hagas lo siguiente ahora: ",
    "Here's one concrete instruction for this computer: ",
    "Here is a specific request for the PC: ",
    "Please handle the following on this PC now: ",
    "Necesito this exact thing on this PC: ",
    "For este computador ahora, please ",
    "For this PC right now, please ",
    "Baxy, atiende esto: ",
    "Baxy, handle this: ",
    "Baxy, haz this: ",
    "Te paso una tarea específica para este equipo: ",
    "Necesito que atiendas esto ahora: ",
    "Here is a specific request for this PC: ",
    "Please do this on the computer now: ",
    "Necesito esta exact thing on the computer: ",
    "For this equipo right now, por favor ",
    "Baxy, haz esto: ",
    "Baxy, do this: ",
    "Baxy, handle esto: ",
    "Te doy una petición puntual para el PC: ",
    "Necesito que realices lo siguiente: ",
    "Here's a concrete task for the computer: ",
    "Please handle this on this computer: ",
    "Necesito this thing on this PC: ",
    "For este PC, please ",
    "Baxy, do esto: ",
    "Baxy, atiende this: ",
    "Baxy, por favor: ",
    "Esta vez necesito una acción concreta en este equipo: ",
    "Encárgate en el computador de esto: ",
    "On this computer, carry out this specific request: ",
    "I need this done locally on the PC: ",
    "Haz this concrete action en este computador: ",
    "On this PC, encárgate de esto: ",
    "Baxy, atiende este pedido: ",
    "Baxy, take care of this request: ",
    "Baxy, handle este pedido: ",
)


def _wrapped(envelope: str, bare: str) -> str:
    stripped = bare.lstrip()
    if stripped.startswith(("¿", "¡")):
        return f"{envelope}{stripped[0]}{stripped[1:]}"
    return f"{envelope}{stripped}"


# El oráculo completo vive en `scripts/detect_social_envelope_equivalence.py`,
# que además compara contra el reconocedor anterior. Aquí se fijan las tres
# invariantes absolutas sobre el mismo corpus congelado: una envoltura social
# nunca inventa autoridad, nunca oculta una petición ya reconocida y nunca
# cambia la operación nombrada.
@pytest.mark.parametrize("envelope", _SOCIAL_ENVELOPES)
def test_a_social_envelope_never_invents_or_changes_an_operation(
    envelope: str,
) -> None:
    manufactured: list[str] = []
    hidden: list[str] = []
    degraded: list[str] = []
    for bare, _expected in CASES:
        reference = resolve_explicit_effects(bare, AVAILABLE)
        observed = resolve_explicit_effects(_wrapped(envelope, bare), AVAILABLE)
        if reference is None:
            if observed is not None:
                manufactured.append(_wrapped(envelope, bare))
        elif observed is None:
            hidden.append(_wrapped(envelope, bare))
        elif (
            observed.kind != reference.kind
            or observed.operations != reference.operations
        ):
            degraded.append(_wrapped(envelope, bare))

    assert manufactured == []
    assert hidden == []
    assert degraded == []


@pytest.mark.parametrize(
    "text",
    [
        # `hola` como contenido literal, no como saludo: sin separador y sin
        # ocupar la cláusula entera, la envoltura social no aplica.
        "Escribe hola",
        "Escribe hola mundo en el bloc de notas",
        "Copia a mi portapapeles hola",
        # Un saludo delante de algo que el reconocedor no resuelve tampoco
        # concede autoridad: sigue siendo un turno del modelo.
        "Hola, hazlo",
        "Buenas noches, arregla esto",
    ],
)
def test_the_social_envelope_never_manufactures_authority(text: str) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)

    assert result is None or "input.text.type" in result.operations


@pytest.mark.parametrize(
    "frame",
    [
        "Quiero preguntarte algo sin pedir una acción: ",
        "Tengo una duda breve, sólo para conversar: ",
        "Just a quick thought, with no computer action: ",
        "I have a short question, just to chat: ",
        "Tengo una quick question, sin computer action: ",
        "Just para conversar, una duda breve: ",
        "Baxy, atiende esto: quiero preguntarte algo sin pedir una acción: ",
        "Quisiera consultarte una cosa sin solicitar una acción: ",
        "Tengo una pregunta rápida, solamente para charlar: ",
        "Just a brief question, with no PC action: ",
        "I have a quick thought, just to talk: ",
        "Tengo una brief question, sin PC acción: ",
        "Just para charlar, una question quick: ",
        "Quiero consultarte una cosa sin solicitar una acción: ",
        "Tengo una duda pequeña, sólo para charlar: ",
        "Just a small thought, with no computer action: ",
        "I have a brief question, just to talk: ",
        "Tengo una short question, sin PC action: ",
        "Just para conversar, una question short: ",
        "Sin pedir ningún cambio en el computador, quiero preguntarte: ",
        "Sólo conversemos; no hagas nada en este equipo: ",
        "Let's only discuss this; do not change anything on the computer: ",
        "This is conversation only, with no PC action requested: ",
        "Solo let's talk; no hagas any PC action: ",
        "Conversation only, sin cambiar nada en este equipo: ",
    ],
)
def test_an_explicit_non_action_frame_vetoes_every_trailing_effect(frame: str) -> None:
    bare = "pon el volumen al veinte por ciento"
    reference = resolve_explicit_effects(bare, AVAILABLE)

    assert reference is not None
    assert resolve_explicit_effects(f"{frame}{bare}", AVAILABLE) is None


@pytest.mark.parametrize(
    ("bare", "wrapped"),
    [
        (
            "Revisa el estado general del computador",
            "Baxy, escucha: Cuando puedas, revisa el estado general del computador",
        ),
        (
            "List my open tasks",
            "Baxy, listen: One quick request, please: list my open tasks",
        ),
        (
            "Abre la calculadora",
            "Baxy, mira: Una petición rápida, porfa: abre la calculadora",
        ),
    ],
)
def test_stacked_discourse_clauses_preserve_the_request(
    bare: str,
    wrapped: str,
) -> None:
    expected = resolve_explicit_effects(bare, AVAILABLE)
    observed = resolve_explicit_effects(wrapped, AVAILABLE)

    assert expected is not None
    assert observed is not None
    assert observed.operations == expected.operations


@pytest.mark.parametrize(
    "text",
    [
        "Cuando puedas recordar mi color favorito será útil",
        "One quick request to open a document is not an execution order",
        "Mira mis recuerdos de infancia con atención",
    ],
)
def test_unpunctuated_discourse_words_do_not_manufacture_authority(text: str) -> None:
    assert resolve_explicit_effects(text, AVAILABLE) is None


# Diferir un efecto no es lo mismo que no poder diferirlo: el catálogo tiene
# `notification.schedule`, `reminder.create` y `calendar.event.create`, y para
# esos actos el «más tarde» ES la operación. El contrato compuesto sólo debe
# fallar cerrado cuando el diferimiento no tiene operación que lo implemente.
@pytest.mark.parametrize(
    "text",
    [
        "ponme una alarma a las 7",
        "alarma para mañana 8am",
        "agenda una reunión el viernes a las cinco",
        "ponme un recordatorio en 2 minutos para tomar agua",
        "crea un recordatorio para mañana",
        "programa una tarea para el lunes",
        "recuérdame comprar pan mañana",
        "avísame en 20 minutos",
        "set a timer for 10 minutes",
        "remind me tomorrow at 8",
    ],
)
def test_a_scheduling_request_is_not_an_unsupported_deferral(text: str) -> None:
    assert unresolved_compound_contract(text, AVAILABLE, ()) is None


@pytest.mark.parametrize(
    ("text", "evidence"),
    [
        (
            "Record alarms for 3 and 4 in the afternoon.",
            ("alarm at 3 in the afternoon", "alarm at 4 in the afternoon"),
        ),
        (
            "Crea alarmas para las 3 y 4 de la tarde.",
            ("alarma a las 3 de la tarde", "alarma a las 4 de la tarde"),
        ),
    ],
)
def test_multiple_literal_alarm_times_expand_to_independent_effects(
    text: str,
    evidence: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, {"notification.schedule"})

    assert result is not None
    assert result.operations == (
        "notification.schedule",
        "notification.schedule",
    )
    assert result.evidence == evidence
    assert (
        unresolved_compound_contract(
            text,
            {"notification.schedule"},
            resolved_intent=result,
        )
        is None
    )


def test_recurring_alarm_request_is_not_collapsed_to_finite_occurrences() -> None:
    assert (
        resolve_explicit_effects(
            "Create repeating alarms for Thursday and Friday at 3pm and 4pm",
            {"notification.schedule"},
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "When is that meeting with my boss next week?",
        "¿Cuándo es la reunión con mi jefe la próxima semana?",
    ],
)
def test_calendar_when_query_is_a_time_range_not_a_deferred_effect(
    text: str,
) -> None:
    available = AVAILABLE | {"calendar.event.list"}

    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == ("calendar.event.list",)
    assert (
        unresolved_compound_contract(
            text,
            available,
            (),
            resolved_intent=result,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Anything I should do after work today",
        "Eventos de esta noche",
        "Qué sucede en Año Nuevo",
        "What is going on tonight",
        "¿Tengo algo que hacer hoy después del trabajo?",
    ],
)
def test_bounded_calendar_queries_are_not_deferred_actions(text: str) -> None:
    available = AVAILABLE | {"calendar.event.list"}
    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == ("calendar.event.list",)
    assert (
        unresolved_compound_contract(
            text,
            available,
            (),
            resolved_intent=result,
        )
        is None
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sube el volumen 10 puntos.", ("audio.volume.adjust",)),
        ("Mute the computer speakers.", ("audio.mute",)),
        ("Schedule an alarm for seven tomorrow morning.", ("notification.schedule",)),
        ("poner una alarma a las nueve de la mañana", ("notification.schedule",)),
        (
            "Abre https://example.com específicamente en Opera.",
            ("browser.navigate.named",),
        ),
        (
            "Open https://example.com specifically in Firefox.",
            ("browser.navigate.named",),
        ),
        ("Cierra la ventana de Spotify.", ("app.close",)),
        ("Close the Spotify window.", ("app.close",)),
        ("Close the active window.", ("app.close",)),
        ("Close the current window.", ("app.close",)),
        (
            "Crea en el calendario un evento llamado Demo mañana de nueve a diez de la mañana.",
            ("calendar.event.create",),
        ),
        (
            "Create a calendar event called Demo tomorrow from nine to ten in the morning.",
            ("calendar.event.create",),
        ),
        ("Lista mis eventos del calendario de mañana.", ("calendar.event.list",)),
        ("List my calendar events for tomorrow.", ("calendar.event.list",)),
        ("Toma una captura de toda la pantalla.", ("capture.screenshot",)),
        ("Captura solamente la ventana activa.", ("capture.active.window",)),
        ("Capture only the active window.", ("capture.active.window",)),
        ("Reproduce Bohemian Rhapsody de Queen.", ("media.play.query",)),
        ("Play Bohemian Rhapsody by Queen.", ("media.play.query",)),
        ("¿Qué hora marca este computador?", ("system.time",)),
        ("What time does this computer show?", ("system.time",)),
        (
            "Envía por WhatsApp a Música el mensaje «llego en diez minutos».",
            ("message.send",),
        ),
        (
            "Send Music the WhatsApp message ‘I will arrive in ten minutes’.",
            ("message.send",),
        ),
        (
            "Dime el uso de RAM del computador y luego lista los procesos activos.",
            ("system.status", "system.process.list"),
        ),
        (
            "Tell me the computer RAM usage and then list the active processes.",
            ("system.status", "system.process.list"),
        ),
        (
            "Crea una nota que diga comprar pilas y recuérdamelo mañana a las seis.",
            ("note.create", "reminder.create"),
        ),
    ],
)
def test_complete_general_requests_do_not_degrade_to_clarification(
    text: str,
    expected: tuple[str, ...],
) -> None:
    available = AVAILABLE | {
        "app.close",
        "calendar.event.create",
        "calendar.event.list",
        "capture.active.window",
        "message.send",
        "notification.schedule",
        "browser.navigate",
        "browser.navigate.named",
    }

    result = resolve_explicit_effects(text, available, ("Spotify",))

    assert result is not None
    assert result.operations == expected


@pytest.mark.parametrize(
    ("text", "available", "expected"),
    [
        (
            "Dile a Marta por Discord que llegaré tarde",
            {"message.send"},
            ("message.send",),
        ),
        (
            "Tell Lucia on Discord that I will be late",
            {"message.send"},
            ("message.send",),
        ),
        (
            "Turn Bluetooth off",
            {"bluetooth.radio.set"},
            ("bluetooth.radio.set",),
        ),
        (
            "Connect to the Wi-Fi network called Home",
            {"wifi.connect.named", "wifi.ensure.connected"},
            ("wifi.connect.named",),
        ),
        (
            "Open the latest file in Downloads",
            {"filesystem.file.open.latest"},
            ("filesystem.file.open.latest",),
        ),
        (
            "Search files containing budget",
            {"filesystem.known.search"},
            ("filesystem.known.search",),
        ),
        (
            "Launch Portal from Steam",
            {"game.launch"},
            ("game.launch",),
        ),
        (
            "Read the error message on the screen",
            {"capture.screenshot", "ocr.read"},
            ("capture.screenshot", "ocr.read"),
        ),
        (
            "Find the Save button and click it",
            {"input.visible.click"},
            ("input.visible.click",),
        ),
        (
            "Take a screenshot and describe it",
            {"capture.screenshot", "vision.describe"},
            ("capture.screenshot", "vision.describe"),
        ),
        (
            "Mute my microphone",
            {"audio.microphone.mute"},
            ("audio.microphone.mute",),
        ),
        (
            "Search the Doom Eternal App ID using the public API",
            {"web.search"},
            ("web.search",),
        ),
    ],
)
def test_general_operation_patterns_cover_unseen_es_en_paraphrases(
    text: str,
    available: set[str],
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == expected


def test_game_launch_requires_one_authenticated_installed_identity() -> None:
    catalog = (
        ("steam", "730", "Counter-Strike 2"),
        ("steam", "620", "Portal 2"),
    )

    counter_strike = resolve_explicit_effects(
        "Abre Counter Strike",
        {"app.open", "game.launch"},
        game_catalog=catalog,
    )
    portal = resolve_explicit_effects(
        "Launch Portal from Steam",
        {"game.launch"},
        game_catalog=catalog,
    )

    assert counter_strike is not None
    assert counter_strike.operations == ("game.launch",)
    assert counter_strike.evidence == ("Counter-Strike 2",)
    assert portal is not None
    assert portal.operations == ("game.launch",)
    assert portal.evidence == ("Portal 2",)
    assert resolve_game_catalog_app_id("Counter-Strike 2", catalog) == "730"
    assert resolve_game_catalog_app_id("Abre Portal", catalog) == "620"


def test_game_launch_abstains_without_inventory_or_on_ambiguous_prefix() -> None:
    ambiguous = (
        ("steam", "730", "Counter-Strike 2"),
        ("steam", "731", "Counter Strike 3"),
    )

    assert resolve_explicit_effects("Abre Counter Strike", {"game.launch"}) is None
    assert (
        resolve_explicit_effects(
            "Abre Counter Strike",
            {"game.launch"},
            game_catalog=ambiguous,
        )
        is None
    )
    assert (
        resolve_explicit_effects(
            "Abre un juego que no tengo",
            {"game.launch"},
            game_catalog=ambiguous,
        )
        is None
    )


@pytest.mark.parametrize(
    "entry",
    [
        ("gog", "620", "Portal 2"),
        ("steam", "620/evil", "Portal 2"),
        ("steam", "620", "Portal\t2"),
        ("steam", "620", "Broken\ufffdName"),
        ("steam", 620, "Portal 2"),
    ],
)
def test_game_catalog_index_rejects_untrusted_identity_shapes(
    entry: tuple[object, object, object],
) -> None:
    with pytest.raises(ValueError):
        build_game_catalog_index((entry,))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("show me the log of the backup job", "backup.list"),
        ("hace un backup de mis documentos a un pendrive", "backup.create"),
        ("abre configuración y entra a Bluetooth", "bluetooth.radio.set"),
        (
            "escribile un email a juan con el asunto reunion diciendo nos vemos",
            "calendar.event.create",
        ),
        ("Abre el archivo hola.txt del escritorio", "browser.navigate"),
        ("Abre el archivo hola.txt del escritorio", "filesystem.folder.open"),
        ("Borra la carpeta CarterTest del escritorio", "filesystem.path.ensure.absent"),
        (
            "Crea una carpeta en el escritorio llamada CarterTest",
            "filesystem.create.directory",
        ),
        (
            "Crea un archivo de texto en el escritorio que diga prueba Carter",
            "filesystem.write.text",
        ),
        ("Abre Big Picture", "app.open"),
        ("Abre capturas de Steam", "game.catalog.list"),
        ("mutea el micrófono en discord", "audio.microphone.mute"),
        (
            "escribile un email a juan con el asunto reunion diciendo nos vemos",
            "email.latest.reply",
        ),
        ("set the HP LaserJet as my default printer", "peripheral.list"),
        (
            "armá el hábito de salir a correr y marcá que ya lo hice",
            "notification.cancel.latest",
        ),
        ("creá el hábito de leer y registrá que lo hice hoy", "routine.phrase.create"),
        ("Elige el primer resultado de YouTube", "media.play.youtube"),
        ("Abre configuración de pantalla", "vision.describe"),
        ("Activa cámara y mira qué hay", "vision.describe"),
        ("Graba la pantalla", "vision.describe"),
        ("Haz un powerpoint de 6 diapositivas", "office.document.create"),
        ("arrastra este archivo a esa ventana", "window.move"),
        ("arrastra este archivo a esa ventana", "filesystem.move"),
    ],
)
def test_operation_domain_preflight_rejects_neighboring_but_different_effects(
    text: str,
    operation: str,
) -> None:
    assert operation_domain_is_grounded(text, operation, ("Paint", "Steam")) is False


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Show my backups", "backup.list"),
        ("Crea un backup del archivo informe.txt", "backup.create"),
        ("Apaga Bluetooth", "bluetooth.radio.set"),
        ("Create a calendar event tomorrow at nine", "calendar.event.create"),
        ("Navigate to github.com", "browser.navigate"),
        ("Abre la carpeta del escritorio", "filesystem.folder.open"),
        ("Crea una carpeta llamada CarterTest", "filesystem.create.directory"),
        ("Borra el archivo CarterTest.txt", "filesystem.path.ensure.absent"),
        ("Crea un archivo llamado nota.txt que diga hola", "filesystem.write.text"),
        ("Lista mi biblioteca de juegos de Steam", "game.catalog.list"),
        ("Silencia el micrófono", "audio.microphone.mute"),
        ("Reply to the latest email", "email.latest.reply"),
        ("Show connected printers", "peripheral.list"),
        ("Cancela la alarma más reciente", "notification.cancel.latest"),
        ("List overdue reminders", "notification.list.due"),
        (
            "Crea una rutina para que al oír la frase foto haga una captura",
            "routine.phrase.create",
        ),
        ("Reproduce lofi en YouTube", "media.play.youtube"),
        ("Describe la imagen visible", "vision.describe"),
        ("Crea un documento Word llamado Informe", "office.document.create"),
        ("Mueve la ventana activa", "window.move"),
        ("Mueve el archivo informe.txt a la carpeta archivo", "filesystem.move"),
        ("Abre Paint", "app.open"),
    ],
)
def test_operation_domain_preflight_preserves_literal_contract_matches(
    text: str,
    operation: str,
) -> None:
    assert operation_domain_is_grounded(text, operation, ("Paint", "Steam")) is True


def test_git_commit_is_not_a_game_or_package_install() -> None:
    assert (
        operation_domain_is_grounded(
            "commit and push my changes to git",
            "game.install.commit",
        )
        is False
    )
    assert (
        operation_domain_is_grounded(
            "commit and push my changes to git",
            "package.install.commit",
        )
        is False
    )


def test_wallpaper_request_is_not_a_backup_restore() -> None:
    assert (
        operation_domain_is_grounded(
            "cambiame el fondo de escritorio",
            "backup.known.restore.latest",
        )
        is False
    )


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("apagame el bluetooth", "bluetooth.radio.set"),
        ("drop the wireless connection", "wifi.disconnect"),
    ],
)
def test_measured_paraphrases_are_not_rejected_for_missing_whitelist_tokens(
    text: str,
    operation: str,
) -> None:
    # Goal 04: the curated gate is one-sided. These two paraphrases named the
    # real domain and were vetoed only because extra verb/token lists missed
    # them. Absence of a whitelist surface is not a rejection.
    assert operation_domain_is_grounded(text, operation) is not False


@pytest.mark.parametrize(
    "text",
    [
        "OCR limitado, mejor para detection",
        "Cierre de Word podía perder trabajo",
        "Listoo la gpu dejo de usarseee",
        "**3-5 s máx**. Todo lo de arriba lo excede.",
        "Empieza de cero esta tarea",
    ],
)
def test_non_request_statements_never_authorize_effects(text: str) -> None:
    assert effect_request_is_authoritative(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "What pasaría si another computer lost su Wi-Fi",
        "¿Qué ocurriría si otro computador perdiera su Wi-Fi?",
        "What would happen if another computer lost its Wi-Fi?",
    ],
)
def test_hypothetical_questions_never_authorize_effects(text: str) -> None:
    assert effect_request_is_authoritative(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Abre Paint",
        "Set the volume to 30 percent",
        "Lee el mensaje de la pantalla",
        "Busca mechanical keyboards on Google",
        "escribile un email a juan con el asunto reunion diciendo nos vemos",
        "hace un backup de mis documentos a un pendrive",
        "Borra la carpeta CarterTest del escritorio",
        "Hazme un PowerPoint de siete diapositivas que hable de dinosaurios",
        "armá el hábito de salir a correr y marcá que ya lo hice",
        "Graba la pantalla",
    ],
)
def test_direct_target_language_requests_retain_preflight_authority(text: str) -> None:
    assert effect_request_is_authoritative(text) is True


def test_live_gpu_attribution_question_is_outside_status_schema() -> None:
    assert unsupported_live_machine_query("Hay algo mas que use gpu??") is True
    assert unsupported_live_machine_query("Explícame qué es una GPU") is False


def test_effect_demonstration_changes_presentation_without_authority() -> None:
    text = "Antes de seguir quiero ver como pones una serie en disney y en netflix"
    assert unsupported_effect_demonstration_request(text) is True
    assert effect_request_is_authoritative(text) is False


def test_email_drafting_is_conversation_not_delivery_authority() -> None:
    assert (
        conversation_only_content_request(
            "Write me an email that I cant make it to the meeting"
        )
        is True
    )
    assert (
        conversation_only_content_request(
            "Redactame un correo diciendo que no podre ir a la reunion"
        )
        is True
    )
    assert (
        conversation_only_content_request("Draft me un correo saying que llegare tarde")
        is True
    )
    assert (
        conversation_only_content_request(
            "escribile un email a juan con el asunto reunion"
        )
        is False
    )


@pytest.mark.parametrize(
    "text",
    [
        "Reescribe con tono amable la frase envía el informe hoy",
        "Work out nineteen times twenty-seven mentally",
        "Dame una receta breve de sopa de zapallo",
        "Make up a riddle whose answer is window",
        "Compare Wi-Fi and Ethernet in general without checking this PC",
        "Translate abre Steam mañana into Italian",
    ],
)
def test_self_contained_content_work_never_grants_effect_authority(
    text: str,
) -> None:
    assert conversation_only_content_request(text) is True
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize(
    "text",
    [
        "arrastra este archivo a esa ventana",
        "armá el hábito de salir a correr y marcá que ya lo hice",
        "Abre el archivo hola.txt del escritorio",
        "Abre una ventana incógnito",
        "Abre configuración de pantalla",
    ],
)
def test_known_missing_variant_closes_only_without_matching_operation(
    text: str,
) -> None:
    assert known_unsupported_effect_request(text, {"app.open"}) is True


def test_named_file_variant_reopens_when_catalog_adds_matching_operation() -> None:
    assert (
        known_unsupported_effect_request(
            "Abre el archivo hola.txt del escritorio",
            {"filesystem.file.open.named"},
        )
        is False
    )
    assert (
        known_unsupported_effect_request(
            "Abre el archivo más reciente",
            {"filesystem.file.open.latest"},
        )
        is False
    )


@pytest.mark.parametrize(
    "text",
    [
        "set the HP LaserJet as my default printer",
        "pon la HP LaserJet como mi impresora predeterminada",
    ],
)
def test_default_printer_request_closes_until_the_exact_capability_exists(
    text: str,
) -> None:

    assert (
        known_unsupported_effect_request(
            text,
            {"peripheral.list", "peripheral.print"},
        )
        is True
    )
    assert (
        known_unsupported_effect_request(
            text,
            {"peripheral.default.set"},
        )
        is False
    )


@pytest.mark.parametrize(
    "text",
    [
        "Tell Lucia that I will be late",
        "Turn on Bluetooth on my phone",
        "Apaga el Bluetooth del auto",
        "Disconnect Wi-Fi on my router",
        "Lee el mensaje de la pantalla de mi teléfono",
        "Find the Save button and tell me what it says",
        "Open the latest file in the repository",
        "Open Paint documentation 2",
        "Search files containing budget on Google",
        "Abre el archivo hola.txt del escritorio",
        "mutea el micrófono en discord",
    ],
)
def test_general_operation_patterns_reject_cross_domain_lookalikes(
    text: str,
) -> None:
    available = {
        "bluetooth.radio.set",
        "capture.screenshot",
        "filesystem.file.open.latest",
        "filesystem.known.search",
        "input.visible.click",
        "message.send",
        "ocr.read",
        "wifi.disconnect",
        "audio.microphone.mute",
        "browser.navigate",
    }

    assert resolve_explicit_effects(text, available, ("Paint",)) is None


@pytest.mark.parametrize(
    "operation",
    [
        "wifi.connect.named",
        "wifi.disconnect",
        "wifi.ensure.connected",
        "wifi.profile.list",
        "wifi.status",
    ],
)
def test_personal_address_forget_never_grounds_a_wifi_operation(
    operation: str,
) -> None:
    assert (
        operation_domain_is_grounded(
            "olvidate de mi direccion vieja",
            operation,
        )
        is False
    )


@pytest.mark.parametrize(
    "text",
    [
        "Sube el volumen de ventas en 10 puntos.",
        "Close the deal with Spotify.",
        "Play the video file.",
        "Send them that message.",
        "Mándales ese mensaje.",
        "Create a calendar event someday.",
    ],
)
def test_new_complete_request_contracts_abstain_on_lookalikes(text: str) -> None:
    available = AVAILABLE | {
        "app.close",
        "calendar.event.create",
        "calendar.event.list",
        "capture.active.window",
        "message.send",
    }

    assert resolve_explicit_effects(text, available, ("Spotify",)) is None


@pytest.mark.parametrize(
    "text",
    ["Mándales ese mensaje.", "Send them that message."],
)
def test_deictic_message_requests_ask_for_missing_recipient_and_payload(
    text: str,
) -> None:
    assert resolve_explicit_clarification(text, {"message.send"}) == "message.send"


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Mándales ese mensaje.", "message.send"),
        ("Send them that message.", "message.send"),
    ],
)
def test_explicit_clarification_preserves_certain_operation_identity(
    text: str,
    operation: str,
) -> None:
    intent = resolve_explicit_clarification_intent(text, {operation})

    assert intent is not None
    assert intent.operation == operation
    assert intent.missing_fields == ("recipient", "message_text")


def test_message_payload_time_is_not_mistaken_for_send_scheduling() -> None:
    text = "Send Music the WhatsApp message ‘I will arrive in ten minutes’."

    result = resolve_explicit_effects(text, {"message.send"})

    assert result is not None
    assert result.operations == ("message.send",)


@pytest.mark.parametrize(
    "text",
    [
        "Crea una nota que diga pagar el arriendo el viernes.",
        "Make a note that says call the dentist tomorrow.",
    ],
)
def test_note_payload_time_is_not_mistaken_for_note_scheduling(text: str) -> None:
    result = resolve_explicit_effects(text, {"note.create"})

    assert result is not None
    assert result.operations == ("note.create",)


def test_desire_framed_cross_language_note_creation_is_explicit() -> None:
    result = resolve_explicit_effects(
        "I want to create a family to-do nota in Keep.",
        {"note.create"},
    )

    assert result is not None
    assert result.operations == ("note.create",)


@pytest.mark.parametrize(
    "text",
    [
        "Crea una nota mañana que diga pagar el arriendo.",
        "Make a note tomorrow that says call the dentist.",
    ],
)
def test_deferred_note_creation_still_fails_closed(text: str) -> None:
    assert resolve_explicit_effects(text, {"note.create"}) is None


def test_colloquial_spotify_request_preserves_missing_query_identity() -> None:
    text = "Abrime Spotify y pone música."

    intent = resolve_explicit_clarification_intent(
        text,
        {"app.open", "media.play.query"},
    )

    assert intent is not None
    assert intent.operations == ("media.play.query",)
    assert intent.missing_fields == ("query",)


def test_relative_volume_without_amount_preserves_operation_identity() -> None:
    intent = resolve_explicit_clarification_intent(
        "Sube el volumen.",
        {"audio.volume.adjust"},
    )

    assert intent is not None
    assert intent.operations == ("audio.volume.adjust",)
    assert intent.missing_fields == ("amount",)


def test_relative_spoken_voice_volume_preserves_operation_identity() -> None:
    intent = resolve_explicit_clarification_intent(
        "speak softer please",
        {"audio.volume.adjust"},
    )

    assert intent is not None
    assert intent.operations == ("audio.volume.adjust",)
    assert intent.missing_fields == ("amount",)


@pytest.mark.parametrize(
    "text",
    [
        "Set the volume to seventy five percent.",
        "Pon el volumen al setenta y cinco por ciento.",
    ],
)
def test_word_valued_absolute_volume_is_deterministic(text: str) -> None:
    result = resolve_explicit_effects(text, {"audio.volume"})

    assert result is not None
    assert result.operations == ("audio.volume",)


@pytest.mark.parametrize(
    ("text", "missing_fields"),
    [
        (
            "Envía este mensaje: quedamos en el restaurante y luego vamos al cine.",
            ("channel", "recipient"),
        ),
        (
            "Envía un mensaje a Brad para decirle que estaremos en el Comfort Inn a las 18:00.",
            ("channel",),
        ),
        ("Ask Bill if the rec center is open early tomorrow", ("channel",)),
        (
            "Message Robert and tell him I want the movie back I lent him",
            ("channel",),
        ),
        (
            "Pregúntale a Ryan si quiere ir a un partido de fútbol.",
            ("channel",),
        ),
    ],
)
def test_channel_less_message_preserves_intent_and_asks_only_for_missing_data(
    text: str,
    missing_fields: tuple[str, ...],
) -> None:
    intent = resolve_explicit_clarification_intent(text, {"message.send"})

    assert intent is not None
    assert intent.operations == ("message.send",)
    assert intent.missing_fields == missing_fields


def test_declarative_message_text_is_not_a_send_clarification() -> None:
    assert (
        resolve_explicit_clarification_intent(
            "The message says that Robert is late.",
            {"message.send"},
        )
        is None
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pon el brillo al 50%", True),
        ("Activa no molestar", True),
        ("Turn on night light", True),
        ("Deja todo lo que suma activado", False),
    ],
)
def test_system_setting_domain_requires_one_authenticated_scope(
    text: str,
    expected: bool,
) -> None:
    assert operation_domain_is_grounded(text, "system.settings.set") is expected


@pytest.mark.parametrize(
    "text",
    [
        "Delete reminder to pick-up Evey",
        "Elimina el recordatorio para ir a buscar a Evey.",
        "Reminder to take grandma shopping needs to be cancelled.",
        "Find the reminder about the bowling fundraiser and remove it",
        "No necesito comida para perro, cancela el recordatorio.",
        (
            "Los tragos después del trabajo se cancelaron así que este "
            "recordatorio se tiene que eliminar."
        ),
    ],
)
def test_exact_named_reminder_deletion_uses_local_identity_plan(text: str) -> None:
    result = resolve_explicit_effects(
        text,
        {"notification.cancel.latest", "reminder.delete"},
    )

    assert result is not None
    assert result.operations == ("reminder.delete",)
    assert (
        unresolved_compound_contract(
            text,
            {"notification.cancel.latest", "reminder.delete"},
            resolved_intent=result,
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Remove a reminder please.",
        "Quita el recordatorio, por favor.",
    ],
)
def test_unnamed_reminder_cancellation_requires_exact_identity(text: str) -> None:
    available = {
        "notification.cancel.at",
        "notification.cancel.latest",
        "reminder.delete",
    }

    assert (
        resolve_explicit_effects(
            text,
            available,
        )
        is None
    )
    clarification = resolve_explicit_clarification_intent(text, available)
    assert clarification is not None
    assert clarification.operations == ("reminder.delete",)
    assert clarification.missing_fields == ("reminder_title",)


def test_time_only_reminder_requires_content_before_action_authority() -> None:
    text = "ponme un recordatorio para las 3 de la tarde"
    available = {"reminder.create", "notification.schedule"}

    assert resolve_explicit_effects(text, available) is None
    clarification = resolve_explicit_clarification_intent(text, available)
    assert clarification is not None
    assert clarification.operations == ("reminder.create",)
    assert clarification.missing_fields == ("title",)


def test_compact_meridiem_reminder_keeps_literal_title_and_time_authority() -> None:
    text = "set a reminder to watch the giants game at 5pm"

    result = resolve_explicit_effects(text, {"reminder.create"})

    assert result is not None
    assert result.operations == ("reminder.create",)
    assert (
        resolve_explicit_clarification_intent(
            text,
            {"reminder.create"},
        )
        is None
    )


def test_dated_reminder_without_title_keeps_identity_but_has_no_authority() -> None:
    text = "set a reminder for tomorrow at 5 pm"

    assert resolve_explicit_effects(text, {"reminder.create"}) is None
    clarification = resolve_explicit_clarification_intent(
        text,
        {"reminder.create"},
    )
    assert clarification is not None
    assert clarification.operations == ("reminder.create",)
    assert clarification.missing_fields == ("title",)


def test_relative_reminder_duration_after_literal_title_is_actionable() -> None:
    text = (
        "Set a reminder to check the chicken cooking in the oven "
        "for 20 minutes from now."
    )

    result = resolve_explicit_effects(text, {"reminder.create"})

    assert result is not None
    assert result.operations == ("reminder.create",)


def test_reminder_content_cannot_be_reclassified_by_an_embedded_event_noun() -> None:
    text = (
        "Crea un recordatorio para que mire en el evento de Facebook "
        "la ubicación del concierto benéfico del domingo por la mañana"
    )
    available = {"calendar.event.create", "reminder.create"}

    clarification = resolve_explicit_clarification_intent(text, available)

    assert clarification is not None
    assert clarification.operations == ("reminder.create",)
    assert clarification.missing_fields == ("due_time",)


def test_calendar_event_without_duration_remains_a_calendar_clarification() -> None:
    text = "Crea un evento llamado Revisión el domingo a las 9"

    clarification = resolve_explicit_clarification_intent(
        text,
        {"calendar.event.create", "reminder.create"},
    )

    assert clarification is not None
    assert clarification.operations == ("calendar.event.create",)
    assert clarification.missing_fields == ("end_time_or_duration",)


def test_telegraphic_calendar_invite_requests_missing_event_details() -> None:
    clarification = resolve_explicit_clarification_intent(
        "calendar event send invite bill malinda",
        {"calendar.event.create"},
    )

    assert clarification is not None
    assert clarification.operations == ("calendar.event.create",)
    assert clarification.missing_fields == ("event_title", "event_time")


def test_incomplete_calendar_after_an_independent_read_still_clarifies() -> None:
    text = "Dime la hora local. Después crea una reunión mañana a las 9."

    clarification = resolve_explicit_clarification_intent(
        text,
        {"system.time", "calendar.event.create"},
    )

    assert clarification is not None
    assert clarification.operations == ("calendar.event.create",)
    assert clarification.missing_fields == ("end_time_or_duration",)


@pytest.mark.parametrize(
    "text",
    [
        (
            "Crea una tarea llamada Cola Matriz. Después abrí el bloc de notas "
            "y escribí reunion manana."
        ),
        (
            "Crea una nota titulada Cola Matriz con contenido verificado. Después "
            "abrí el bloc de notas y escribí reunion manana."
        ),
    ],
)
def test_typed_calendar_words_do_not_trigger_calendar_clarification(text: str) -> None:
    available = {
        "app.open",
        "calendar.event.create",
        "input.text.type",
        "note.create",
        "task.create",
    }

    assert resolve_explicit_clarification_intent(text, available) is None
    intent = resolve_explicit_effects(text, available, ("Bloc de notas",))
    assert intent is not None
    assert intent.operations in {
        ("task.create", "app.open", "input.text.type"),
        ("note.create", "app.open", "input.text.type"),
    }


@pytest.mark.parametrize(
    "text",
    [
        "Delete reminders to call Ana and Luis.",
        "Elimina los recordatorios de llamar a Ana y Luis.",
    ],
)
def test_plural_reminder_deletion_never_collapses_to_one_mutation(text: str) -> None:
    assert (
        resolve_explicit_effects(
            text,
            {"notification.cancel.latest", "reminder.delete"},
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Send Music the WhatsApp message ‘I am here’ tomorrow.",
        "Envía por WhatsApp a Música el mensaje «ya llegué» mañana.",
    ],
)
def test_message_scheduling_outside_payload_still_fails_closed(text: str) -> None:
    assert resolve_explicit_effects(text, {"message.send"}) is None


@pytest.mark.parametrize(
    "text",
    [
        # Aquí el «más tarde» no es la operación: ninguna del catálogo difiere
        # estos efectos, así que el contrato debe seguir fallando cerrado.
        "pon música mañana",
        "abre notepad mañana",
        "sube el volumen a las 7",
        "apaga el pc cuando termine la descarga",
        "borra la carpeta el viernes",
        "abre spotify si tengo internet",
        "manda el correo más tarde",
        "reinicia el equipo esta noche",
        "cierra chrome cuando termine",
    ],
)
def test_an_unsupported_deferral_still_fails_closed(text: str) -> None:
    assert unresolved_compound_contract(text, AVAILABLE, ()) is not None


@pytest.mark.parametrize(
    "text",
    [
        "hay ferias de artesanía en esta zona",
        "cual es el zoo mas cercano de donde yo estoy",
        "más precio de las acciones",
        "cuáles son los artículos de tendencia sobre el país",
        "¿Dónde puedo aparcar cerca del zoo de Barcelona?",
        "I want to get a quarter pounder, I mean a Big Mac meal.",
    ],
)
def test_public_lookup_variants_are_deterministic_web_reads(text: str) -> None:
    result = resolve_explicit_effects(text, {"web.search"})

    assert result is not None
    assert result.operations == ("web.search",)


def test_wake_request_is_an_alarm_instead_of_a_power_transition() -> None:
    result = resolve_explicit_effects(
        "get me up at eight am",
        {"notification.schedule", "system.power"},
    )

    assert result is not None
    assert result.operations == ("notification.schedule",)


def test_figurative_artist_request_is_a_music_query() -> None:
    result = resolve_explicit_effects(
        "comfort my ears with arijit singh",
        {"media.play.query"},
    )

    assert result is not None
    assert result.operations == ("media.play.query",)


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Create a memo to buy chocolate.", "note.create"),
        (
            "¿Puedes tomar mis notas familiares atrasadas del pasado?",
            "note.search",
        ),
    ],
)
def test_compact_note_requests_keep_the_local_note_family(
    text: str,
    operation: str,
) -> None:
    result = resolve_explicit_effects(text, {operation})

    assert result is not None
    assert result.operations == (operation,)


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("get hourly notification on sports news", "notification.schedule"),
        ("add event to calendar app", "calendar.event.create"),
        (
            "acuérdame el cinco de marzo de cada año de ocuparme de los regalos",
            "reminder.create",
        ),
        (
            "por favor establece una notificación para el veintitrés de octubre",
            "notification.schedule",
        ),
        (
            "retoma harry potter por donde paré de escuchar la última vez",
            "media.control",
        ),
    ],
)
def test_incomplete_bounded_requests_have_stable_clarification_identity(
    text: str,
    operation: str,
) -> None:
    result = resolve_explicit_clarification_intent(text, {operation})

    assert result is not None
    assert result.operations == (operation,)


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("I need to know the time right now, what is it?", "system.time"),
        ("What time is it right now?", "system.time"),
        (
            "Is there any events planned for the next three months?",
            "calendar.event.list",
        ),
        (
            "Are there meetings scheduled for the next two weeks?",
            "calendar.event.list",
        ),
        (
            "Show me the best podcast of rock songs having good rating",
            "media.play.query",
        ),
        ("I want to listen to Be More Chill by Ned Vizzini", "media.play.query"),
        (
            "Solo estoy buscando algunos desfiles de vestidos; puedes encontrar "
            "tiendas de ropa dentro de una milla",
            "web.search",
        ),
        ("Hay algun evento especial cerca de mi este fin de semana", "web.search"),
        ("Hace el Telepizza envios a domicilio", "web.search"),
        ("Cuales son las historias principales de la RTVE", "web.search"),
        ("I want to find valet parking by the theater", "web.search"),
        ("Muestra aparcamiento en Murcia con ascensor", "web.search"),
    ],
)
def test_relative_public_reads_and_audio_requests_have_stable_authority(
    text: str,
    operation: str,
) -> None:
    result = resolve_explicit_effects(text, {operation})

    assert result is not None
    assert result.operations == (operation,)


@pytest.mark.parametrize(
    "text",
    [
        "I would like to hear some good funny jokes",
        "Me gustaria escuchar unos chistes divertidos",
    ],
)
def test_requested_jokes_never_become_media_playback(text: str) -> None:
    assert resolve_explicit_effects(text, {"media.play.query"}) is None


@pytest.mark.parametrize(
    ("text", "operation", "missing"),
    [
        (
            "Please set a meeting with Fred on the next available meeting day",
            "calendar.event.create",
            ("start_time", "end_time_or_duration"),
        ),
        ("Radio por favor", "media.play.query", ("station_or_genre",)),
        (
            "Quiero escribir una nota compartida que dure hasta las 6 de la tarde",
            "note.create",
            ("note_content",),
        ),
        (
            "Puedes incluir un recordatorio en la nota para mi hermano? O mejor, "
            "no incluyas recordatorio",
            "note.create",
            ("note_content",),
        ),
        (
            "Me lees esta nota?",
            "note.read",
            ("note_identity_or_context",),
        ),
        (
            "Let me see that note.",
            "note.read",
            ("note_identity_or_context",),
        ),
        (
            "I want to play the song again",
            "media.play.query",
            ("song_title_or_current_media_context",),
        ),
        (
            "Ensena me las recetas",
            "web.search",
            ("recipe_topic",),
        ),
        (
            "Show me some recipes",
            "web.search",
            ("recipe_topic",),
        ),
    ],
)
def test_ambiguous_focal_requests_keep_one_stable_clarification(
    text: str,
    operation: str,
    missing: tuple[str, ...],
) -> None:
    clarification = resolve_explicit_clarification_intent(text, {operation})

    assert clarification is not None
    assert clarification.operations == (operation,)
    assert clarification.missing_fields == missing


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Please tell me what alarms are on", "notification.diagnose"),
        ("Is there an alarm for ten am", "notification.diagnose"),
        ("Me recomiendas un paraguas", "web.search"),
        ("Muestra las recetas famosas de huevos duros", "web.search"),
        ("I want to find garage parking", "web.search"),
        ("Can I carry out with this restaurant?", "web.search"),
        ("Does this restaurant offer takeout?", "web.search"),
        ("Puedo pedir para llevar en este restaurante?", "web.search"),
        ("direcciones a Disneyland", "web.search"),
        ("directions to Disneyland", "web.search"),
        ("que día de la semana cae navidad este año", "web.search"),
        (
            "Usa Telpark para encontrar sitios de aparcamientos gratis en Madrid",
            "web.search",
        ),
        (
            "Sacar la nota receta de brioche que tengo guardada",
            "note.search",
        ),
    ],
)
def test_status_public_discovery_and_stored_note_requests_are_deterministic(
    text: str,
    operation: str,
) -> None:
    result = resolve_explicit_effects(text, {operation})

    assert result is not None
    assert result.operations == (operation,)


@pytest.mark.parametrize(
    ("text", "operation", "missing"),
    [
        (
            "Avisame si suben o bajan el precio de las acciones de esta empresa",
            "notification.schedule",
            ("company", "live_monitoring_source"),
        ),
        (
            "Let's create a new private note to order groceries at 9 am, "
            "actually make it 10 am",
            "note.create",
            ("time_as_note_content_or_reminder",),
        ),
        (
            "Quisiera probar con algun juego de construccion de imperios de Ubisoft",
            "game.launch",
            ("game_title",),
        ),
        (
            "Ponme el juego de futbol en el salon, no, mejor dicho en la habitacion",
            "game.launch",
            ("game_title", "target_device"),
        ),
        (
            "Leeme los post-its compartidos con la family",
            "note.search",
            ("shared_note_source",),
        ),
        (
            "Get me coffee coffee from Safeway",
            "web.search",
            ("product_lookup_or_purchase",),
        ),
        (
            "Get milk, eggs, and bread from uhh from Aldi.",
            "web.search",
            ("product_lookup_or_purchase",),
        ),
        (
            "In the living room, play League of Legends.",
            "game.launch",
            ("local_pc_or_supported_device",),
        ),
        (
            "Enséñame las aplicaciones de deportes.",
            "app.installed",
            ("specific_application_name",),
        ),
        (
            "Show me sports apps.",
            "app.installed",
            ("specific_application_name",),
        ),
        (
            "¿Sabe la entrega estimada de mi pedido?",
            "web.search",
            ("merchant_or_tracking_reference",),
        ),
        (
            "Tell me the estimated delivery of my order.",
            "web.search",
            ("merchant_or_tracking_reference",),
        ),
    ],
)
def test_dynamic_alert_note_time_and_generic_game_requests_clarify_stably(
    text: str,
    operation: str,
    missing: tuple[str, ...],
) -> None:
    clarification = resolve_explicit_clarification_intent(text, {operation})

    assert clarification is not None
    assert clarification.operations == (operation,)
    assert clarification.missing_fields == missing


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("go to the washington post website", "browser.navigate"),
        ("list all train times to ny", "web.search"),
        ("get me up in half an hour", "notification.schedule"),
        ("search to find current local time and time zone", "system.time"),
        ("new alarm for six am", "notification.schedule"),
        ("i need you to get me up at six am", "notification.schedule"),
        ("check if alarm is set for six am", "notification.diagnose"),
        (
            "please ring the wake up alarm at eight am next saturday",
            "notification.schedule",
        ),
        ("set my alarm for seven am", "notification.schedule"),
        ("de ahora en adelante mudo", "audio.mute"),
        ("voy a necesitar llevar chaqueta el proximo miercoles", "web.search"),
        ("reporte del tiempo semanal", "web.search"),
        (
            "enciende la lista de reproduccion que yo he dedicado a la musica rock",
            "media.play.query",
        ),
        (
            "I need 2 packs of cheddar cheese from uh, umm, Walmart today, please.",
            "web.search",
        ),
        (
            "Let's get some fall decorations from Amazon and have UPS deliver.",
            "web.search",
        ),
        ("Desearia que localizaras un parking adaptado", "web.search"),
        ("voy a necesitar, necesito un pijama de oysho", "web.search"),
        ("puedes decirme donde hay parking gratis en huesca", "web.search"),
        ("Necesito un parking gratuito cerca de esta ubicacion", "web.search"),
        ("buy milk and eggs का memo create करो।", "note.create"),
    ],
)
def test_fresh_gate_families_have_deterministic_effect_identity(
    text: str,
    operation: str,
) -> None:
    result = resolve_explicit_effects(text, {operation})

    assert result is not None
    assert result.operations == (operation,)


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        (
            "set notifications on the current weather disasters in america",
            "notification.schedule",
        ),
        (
            "set meeting with joanna on saturday four p. m.",
            "calendar.event.create",
        ),
        (
            "for every odd numbered sunday set a reminder for",
            "reminder.create",
        ),
        ("could you reschedule my meeting", "calendar.event.create"),
        ("quiero reproducir esta cancion de nuevo", "media.play.query"),
        ("necesito hacer algo hoy", "calendar.event.create"),
    ],
)
def test_fresh_gate_incomplete_requests_keep_stable_clarification_identity(
    text: str,
    operation: str,
) -> None:
    result = resolve_explicit_clarification_intent(text, {operation})

    assert result is not None
    assert result.operations == (operation,)


@pytest.mark.parametrize(
    "text",
    [
        (
            "Dime la hora local. Despues lista mis tareas pendientes. "
            "Despues lista mis notas. Despues lista los procesos activos. "
            "Despues silencia el audio. Despues pon el volumen al 17 por ciento. "
            "Despues crea una tarea llamada Cola Matriz. Finalmente crea una nota "
            "titulada Cola Matriz con contenido verificado."
        ),
        (
            "What time is it now; then show my tasks; then show my saved notes; "
            "then show the running processes; then put the audio on mute; then "
            "adjust the volume to 17 percent; then add a note called Matrix Tail "
            "saying verified; finally add a task called Matrix Tail."
        ),
    ],
)
def test_maximum_octet_never_accepts_a_partial_strict_catalog_match(
    text: str,
) -> None:
    available = {
        "system.time",
        "task.list",
        "note.list",
        "system.process.list",
        "audio.mute",
        "audio.volume",
        "task.create",
        "note.create",
        "audio.status",
        "message.send",
    }

    assert resolve_explicit_clarification_intent(text, available) is None
    result = resolve_explicit_effects(text, available)

    assert result is not None
    assert result.operations == (
        "system.time",
        "task.list",
        "note.list",
        "system.process.list",
        "audio.mute",
        "audio.volume",
        "task.create" if text.startswith("Dime") else "note.create",
        "note.create" if text.startswith("Dime") else "task.create",
    )


# --- dependent clause heads -------------------------------------------------
#
# A compound mission used to abstain whenever one clause borrowed its head from
# the clause governing it. These cover the four bounded shapes that caused it,
# and — more importantly — the conservation property that must survive them.

_DEPENDENT_HEAD_AVAILABLE = {
    "audio.status",
    "bluetooth.device.list",
    "input.keyboard.status",
    "network.status",
    "note.create",
    "note.read",
    "peripheral.list",
    "system.status",
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Revisa el teclado, enumera los dispositivos Bluetooth visibles, "
            "lista los periféricos conectados y termina con el estado de la red.",
            (
                "input.keyboard.status",
                "bluetooth.device.list",
                "peripheral.list",
                "network.status",
            ),
        ),
        (
            "Create una nota Puente con content listo; después read esa misma "
            "nota y finally check audio status y network status.",
            ("note.create", "note.read", "audio.status", "network.status"),
        ),
    ],
)
def test_dependent_clause_heads_resolve_the_whole_mission(
    text: str,
    expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, _DEPENDENT_HEAD_AVAILABLE)

    assert result is not None
    assert result.operations == expected
    assert unresolved_compound_contract(text, _DEPENDENT_HEAD_AVAILABLE) is None


def test_elided_verb_and_bare_ordinal_reuse_their_governing_clause() -> None:
    text = (
        "Create una nota Luna con content claro y otra nota Sol con content "
        "brillante; después read la segunda, luego read la primera."
    )

    result = resolve_explicit_effects(text, _DEPENDENT_HEAD_AVAILABLE)

    assert result is not None
    assert result.operations == (
        "note.create",
        "note.create",
        "note.read",
        "note.read",
    )


def test_participle_note_bodies_keep_their_enumerated_cardinality() -> None:
    """``containing`` names a body exactly like ``with content`` does."""

    text = (
        "Create four local notes: Cedar containing north, Willow containing "
        "south, Maple containing east, and Birch containing west. Then read "
        "the second note, the fourth note, the first note, and the third note."
    )

    result = resolve_explicit_effects(text, _DEPENDENT_HEAD_AVAILABLE)

    assert result is not None
    assert result.operations == ("note.create",) * 4 + ("note.read",) * 4
    # A serial comma must not name a note "and birch".
    assert enumerated_note_dependency_order(text) == (2, 4, 1, 3)


@pytest.mark.parametrize(
    "text",
    [
        "Show system status, network status, brew coffee, and sound status",
        "Revisa el estado del audio, prepara un café y el estado de la red",
    ],
)
def test_an_ungrounded_segment_still_fails_the_whole_coordination_closed(
    text: str,
) -> None:
    """Conservation outranks coverage.

    Splitting a coordination must never sever an ungrounded segment from the
    part that does resolve; executing the recognizable subset would be a
    silent partial mission.
    """

    assert resolve_explicit_effects(text, _DEPENDENT_HEAD_AVAILABLE) is None


def test_sequencing_head_does_not_capture_literal_content() -> None:
    """``termina`` only loses its head when it introduces a report."""

    literal = "Crea una nota Plazo con contenido la tarea termina el viernes"
    result = resolve_explicit_effects(literal, _DEPENDENT_HEAD_AVAILABLE)

    assert result is not None
    assert result.operations == ("note.create",)


def test_status_shortcut_never_drops_a_non_status_clause() -> None:
    """A recognized subset must not stand in for the whole mission.

    Two sequence markers used to route this request through the bounded
    status-sequence shortcut, which reports only the status domains it knows.
    The note clauses were dropped with no trace, so the mission would have run
    as a silent subset of what was asked.
    """

    text = (
        "Create una nota Puente con content listo; después read esa misma "
        "nota y finally check audio status y network status."
    )

    result = resolve_explicit_effects(text, _DEPENDENT_HEAD_AVAILABLE)

    assert result is not None
    assert result.operations == (
        "note.create",
        "note.read",
        "audio.status",
        "network.status",
    )


# --- near-miss effect vetoes -------------------------------------------------
#
# The open-population cut forbids an invented operation and a merely similar
# effect. Both cases below reached a real operation for a request that had
# nothing to do with it, so the deterministic domain veto has to remove that
# authority. These gates are one-sided: they never select an operation.


@pytest.mark.parametrize(
    ("text", "operation", "grounded"),
    [
        # A physical parcel is not a chat message.
        ("Manda un package a mi hermana.", "message.send", False),
        ("Manda un paquete a Ana.", "message.send", False),
        ("Envia una carta a mi tia.", "message.send", False),
        ("Manda flores a mi madre.", "message.send", False),
        ("Manda un mensaje a Ana.", "message.send", True),
        ("Dile a Ana que llego tarde.", "message.send", True),
        ("Escribele un whatsapp a Pedro.", "message.send", True),
        # A real-world errand must never reach the pointer.
        ("Consigue un ride hasta el centro.", "input.pointer.control", False),
        ("Pide un taxi para las ocho.", "input.pointer.control", False),
        ("Mueve el mouse al centro.", "input.pointer.control", True),
        ("Haz clic en el boton azul.", "input.pointer.control", True),
    ],
)
def test_near_miss_effects_lose_their_domain_authority(
    text: str,
    operation: str,
    grounded: bool,
) -> None:
    assert operation_domain_is_grounded(text, operation) is grounded


@pytest.mark.parametrize(
    ("text", "operation", "grounded"),
    [
        # Creating and listing are opposite directions of one family.
        ("Haz un appointment con el doctor.", "calendar.event.list", False),
        ("Haz un appointment con el doctor.", "calendar.event.create", True),
        ("Agenda una reunion el jueves a las diez.", "calendar.event.create", True),
        ("Muestra mi agenda de manana.", "calendar.event.list", True),
        # A plural must not silently lose the calendar domain.
        ("Que citas tengo hoy?", "calendar.event.list", True),
        ("Cuantas reuniones tengo esta semana?", "calendar.event.list", True),
    ],
)
def test_calendar_direction_is_grounded_separately(
    text: str,
    operation: str,
    grounded: bool,
) -> None:
    """Asking to create must never ground a listing, and vice versa.

    "Haz un appointment con el doctor" was planned as calendar.event.list, so a
    request to make an appointment could have executed a read instead.
    """
    assert operation_domain_is_grounded(text, operation) is grounded


@pytest.mark.parametrize(
    ("text", "grounded"),
    [
        # Physical goods share the verb but are not messages. Enumerating them
        # never terminated -- "package" was blocked and "ramo de rosas" walked
        # through -- so the gate asks for a positive message signal instead.
        ("Manda un package a mi hermana.", False),
        ("Manda un ramo de rosas a mi abuela.", False),
        ("Envia estas cajas al almacen del sur.", False),
        ("Ship this box to my brother in Quito.", False),
        ("Manda un gift a mi profesora.", False),
        # Channels, message nouns, speech acts and spoken content.
        ("Manda un mensaje a Ana.", True),
        ("Dile a Ana que llego tarde.", True),
        ("Escribele un whatsapp a Pedro.", True),
        ("Mandale a Ana que llego tarde.", True),
        # A digital artifact is transmissible; a parcel is not.
        ("Envia el informe a Lucas.", True),
        ("Manda la foto del recibo a contabilidad.", True),
    ],
)
def test_message_authority_needs_a_positive_message_signal(
    text: str,
    grounded: bool,
) -> None:
    assert operation_domain_is_grounded(text, "message.send") is grounded


@pytest.mark.parametrize(
    ("text", "grounded"),
    [
        # "Cuelga el cuadro en la pared" was planned as app.close.
        ("Cuelga el cuadro en la pared del pasillo.", False),
        ("Barre el suelo de la cocina.", False),
        ("Cierra la ventana de Spotify.", True),
        ("Close the browser window.", True),
        ("Cierra esa aplicacion.", True),
    ],
)
def test_closing_something_on_screen_must_name_the_screen(
    text: str,
    grounded: bool,
) -> None:
    assert operation_domain_is_grounded(text, "app.close") is grounded


@pytest.mark.parametrize(
    ("text", "grounded"),
    [
        # Municipal recycling and the desktop bin share a word in Spanish, and
        # emptying the bin is destructive and irreversible. "Envia la bicicleta
        # vieja al reciclaje" was planned as system.recyclebin.empty, twice.
        ("Envia la bicicleta vieja al reciclaje.", False),
        ("Lleva el carton al reciclaje del barrio.", False),
        ("Vacia la papelera de reciclaje.", True),
        ("Empty the recycle bin.", True),
        ("Empty the trash on this computer.", True),
    ],
)
def test_emptying_the_bin_requires_naming_the_bin(text: str, grounded: bool) -> None:
    assert operation_domain_is_grounded(text, "system.recyclebin.empty") is grounded


@pytest.mark.parametrize(
    ("text", "operation", "grounded"),
    [
        # A noun is not enough: "sew the button on my coat" reached
        # input.visible.click through the word "button".
        ("Sew the button on my coat.", "input.visible.click", False),
        ("Aprieta los tornillos de la silla.", "input.visible.click", False),
        ("Haz clic en el boton azul.", "input.visible.click", True),
        ("Click the blue button.", "input.visible.click", True),
        ("Mueve el puntero al centro de la pantalla.", "input.pointer.control", True),
        # The keyboard family uses the real catalogue names.
        ("Revisa el teclado.", "input.keyboard.status", True),
        ("Escribe hola en el bloc.", "input.text.type", True),
        ("Cocina una tortilla.", "input.text.type", False),
    ],
)
def test_input_family_needs_a_pointing_or_typing_signal(
    text: str,
    operation: str,
    grounded: bool,
) -> None:
    assert operation_domain_is_grounded(text, operation) is grounded


@pytest.mark.parametrize(
    ("text", "language"),
    [
        # Spanglish is a supported surface, not a third language. "Bota las
        # boxes viejas al recycling" was answered with a language notice
        # because "bota" was listed as a Portuguese cue.
        ("Bota las boxes viejas al recycling.", None),
        ("Bota la basura antes de las nueve.", None),
        ("Manda unos balloons a la fiesta.", None),
        # A Portuguese article behind it keeps the cue precise.
        ("Bota o volume no maximo.", "pt"),
        ("Abre o navegador.", "pt"),
    ],
)
def test_shared_romance_words_do_not_declare_another_language(
    text: str,
    language: str | None,
) -> None:
    from baxy_mind.effect_intent import confident_non_target_language

    assert confident_non_target_language(text) == language


@pytest.mark.parametrize(
    ("text", "operation", "grounded"),
    [
        # True homonyms. Vocabulary grounding cannot separate these because the
        # physical sense uses the operation's own word, so the gate asks what
        # is being acted on instead.
        ("Pega las fotos en el album de papel.", "clipboard.paste", False),
        ("Pega el sello en el sobre.", "clipboard.paste", False),
        ("Glue the stamps into the paper album.", "clipboard.paste", False),
        (
            "Paste the current clipboard into the focused field.",
            "clipboard.paste",
            True,
        ),
        ("Pega el contenido del portapapeles.", "clipboard.paste", True),
        ("Pega lo que copie recien.", "clipboard.paste", True),
        # A window named as the destination is not the thing being moved.
        ("Move the wardrobe towards the far window.", "window.move", False),
        ("Mueve el armario hacia la ventana del fondo.", "window.move", False),
        (
            "Move the Notepad window to desktop coordinates 120, 80.",
            "window.move",
            True,
        ),
        ("Mueve la ventana de Spotify a la izquierda.", "window.move", True),
    ],
)
def test_homonyms_are_separated_by_what_is_acted_on(
    text: str,
    operation: str,
    grounded: bool,
) -> None:
    assert operation_domain_is_grounded(text, operation) is grounded


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # "pegar" is both paste and glue. The deterministic recogniser accepted
        # any "pega X" as a clipboard paste, so gluing a label resolved to an
        # effect that would paste into whatever had focus. Its sibling
        # clipboard.copy was already guarded by a domain check; paste was not.
        ("Pega la etiqueta en el frasco de mermelada.", None),
        ("Pega los azulejos sueltos del bano.", None),
        ("Paste the wallpaper strips onto the hallway wall.", None),
        ("Pega el patch en la mochila.", None),
        ("Pega el contenido del portapapeles.", ("clipboard.paste",)),
        ("Paste the current clipboard into the focused field.", ("clipboard.paste",)),
        ("Pega lo que copie recien.", ("clipboard.paste",)),
    ],
)
def test_pasting_requires_the_clipboard_not_just_the_verb(
    text: str,
    expected: tuple[str, ...] | None,
) -> None:
    available = sorted(
        {
            "clipboard.paste",
            "clipboard.copy",
            "clipboard.read.text",
            "note.create",
            "app.open",
        }
    )
    resolved = resolve_explicit_effects(text, available)

    assert (resolved.operations if resolved else None) == expected


@pytest.mark.parametrize(
    ("text", "grounded"),
    [
        # A window named after a destination preposition is where the thing
        # goes, not the thing being moved.
        ("Move the desk next to the window.", False),
        ("Move the bookcase towards the bedroom window.", False),
        ("Mueve la maceta junto a la ventana de la cocina.", False),
        ("Move the Notepad window to desktop coordinates 120, 80.", True),
        ("Mueve la ventana de Spotify a la izquierda.", True),
    ],
)
def test_moving_a_window_means_the_window_moves(text: str, grounded: bool) -> None:
    assert operation_domain_is_grounded(text, "window.move") is grounded


@pytest.mark.parametrize(
    "text",
    [
        "cierra la ventana titulada Ventana C03 de prueba",
        "Cierra la ventana con el título Informe trimestral — revisión.",
        "Close the window titled Quarterly report — review.",
        "Close the window named Untitled document.",
        "Cierra la window called Project status.",
    ],
)
def test_named_window_close_preserves_effect_and_allows_target_resolution(
    text: str,
) -> None:
    resolved = resolve_explicit_effects(
        text, ["app.close", "window.resolve", "window.active"]
    )
    assert resolved is not None
    assert resolved.operations == ("app.close",)
    assert operation_domain_is_grounded(text, "window.resolve") is True


@pytest.mark.parametrize(
    "text",
    [
        "Close the window of opportunity.",
        "Cierra la ventana de la cocina.",
        "Close the window titled",
        "Cierra la ventana con el título",
    ],
)
def test_a_window_title_requires_an_actual_named_target(text: str) -> None:
    assert (
        resolve_explicit_effects(text, ["app.close", "window.resolve", "window.active"])
        is None
    )
    assert operation_domain_is_grounded(text, "window.resolve") is False


@pytest.mark.parametrize(
    "text",
    [
        "Esto si es una orden para el equipo: silencia el audio.",
        "Actua en el PC con esta instruccion: silencia el audio.",
        "Baxy, ejecuta esta instruccion del equipo: silencia el audio.",
        "Treat this as an instruction for the computer: mute the audio.",
        "Carry out this PC request: mute the audio.",
        "Baxy, execute this computer instruction: mute the audio.",
        "Haz this on the computer: silencia el audio.",
        "Esto is a real pc instruction: mute the audio.",
        # The word classes are completed from the language, not from the
        # wordings any corpus used. R23 lost a whole Spanish cell to one
        # missing noun; none of the surfaces below appear in R22 or R23.
        "Va un encargo para la maquina: silencia el audio.",
        "Atiende este mandato en el PC: silencia el audio.",
        "Recibe esta solicitud de la computadora: silencia el audio.",
        "Esta disposicion va para el equipo: silencia el audio.",
        # "ordenador" is the ordinary word for a computer in Spain. Without it
        # the frame was never stripped for those speakers at all.
        "Esta orden es para el ordenador: silencia el audio.",
        "Atiende esta instruccion en el portatil: silencia el audio.",
        "This errand goes to the laptop: mute the audio.",
        "Take care of the following on the machine: mute the audio.",
    ],
)
def test_an_instruction_frame_is_not_part_of_the_request(text: str) -> None:
    """Announcing that an instruction follows is not the instruction.

    Cut B wrapped every request this way and only 29 of 560 framed rows
    resolved; 417 of them resolved the moment the wrapper was removed, so the
    result looked like a failure to generalise when it was a failure to strip.
    """
    from baxy_mind.effect_intent import _fold, _strip_request_envelope

    assert ":" not in _strip_request_envelope(_fold(text))


@pytest.mark.parametrize(
    "text",
    [
        "Esto es solo una conversacion y no una orden para el pc: que opinas?",
        "This is only a conversation, not a computer instruction: what do you think?",
        "Respondeme sin realizar ningun cambio en el equipo: que opinas?",
        "Answer without making any change on the pc: what do you think?",
        "Ninguna consigna para el ordenador, charlemos: que opinas?",
        "Ningun mandato va al equipo, respondeme y ya: que opinas?",
        "Neither an order nor a command for the machine: what do you think?",
        "Nunca es una directriz para el portatil: que opinas?",
    ],
)
def test_a_no_action_frame_is_never_stripped_into_a_request(text: str) -> None:
    """The negation carries the whole meaning.

    These name an instruction and a machine just like the frames above, so a
    rule that only looked for those two nouns would turn an explicit request
    for no action into an action.
    """
    from baxy_mind.effect_intent import _fold, _strip_request_envelope

    assert ":" in _strip_request_envelope(_fold(text))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A modifier between the determiner and the noun must not hide the noun
        # the elliptical second clause inherits. The physical mission
        # en_two_notes_cross_read died on exactly this: with "local" present the
        # pair was counted as one note and the whole turn was refused.
        (
            "create a local note titled North with content blue and another "
            "titled South with content green",
            ("note.create", "note.create"),
        ),
        (
            "crea una nota local titulada Norte con contenido azul y otra "
            "titulada Sur con contenido verde",
            ("note.create", "note.create"),
        ),
        # Two coordinated ordinal reads are two reads. Returning one is a
        # conservation loss: the request named four operations.
        (
            "create a note titled North with content blue and another titled "
            "South with content green, then read the second note and finally "
            "the first note",
            ("note.create", "note.create", "note.read", "note.read"),
        ),
        (
            "create a local note titled North with content blue and another "
            "titled South with content green, then read the second note and "
            "finally the first note",
            ("note.create", "note.create", "note.read", "note.read"),
        ),
    ],
)
def test_enumerated_notes_survive_modifiers_and_coordinated_ordinal_reads(
    text: str,
    expected: tuple[str, ...],
) -> None:
    import json
    from pathlib import Path

    from baxy_mind.effect_intent import _fold, resolve_explicit_effects

    repository = Path(__file__).resolve().parents[1]
    aliases = json.loads(
        (repository / "src/baxy_mind/data/catalog_operation_aliases.v1.json").read_text(
            encoding="utf-8"
        )
    )
    available = sorted({op for row in aliases["aliases"] for op in row["operations"]})

    resolved = resolve_explicit_effects(_fold(text), available)
    assert resolved is not None
    assert tuple(resolved.operations) == expected


def test_a_coordinated_read_is_not_split_when_a_segment_is_unrecognizable() -> None:
    """Splitting a coordination may never sever what the recognizer cannot ground.

    ``read the second note and brew coffee`` is not two reads. If the tail were
    severed anyway the request would silently execute the half it understands
    instead of failing closed, which is the same loss the coordinated status
    clause already guards against.
    """
    from baxy_mind.effect_intent import (
        _PURE_COORDINATED_ORDINAL_READ_CLAUSE,
        _fold,
    )

    assert (
        _PURE_COORDINATED_ORDINAL_READ_CLAUSE.match(
            _fold("read the second note and brew coffee")
        )
        is None
    )
    assert (
        _PURE_COORDINATED_ORDINAL_READ_CLAUSE.match(
            _fold("read the second note and finally the first note")
        )
        is not None
    )


@pytest.mark.parametrize(
    "text",
    [
        # The surface that actually leaked. On veto-reach V1 this executed
        # filesystem.sandbox.append.named and said nothing: a hard zero of cut
        # D's contract. The deterministic recogniser declined it correctly; the
        # gate returned None because no rule named that operation.
        "Barre las hojas del sendero.",
        "Poda el seto de la entrada.",
        "Plancha las camisas del armario.",
        "Sand the shelf in the hallway.",
        "Fold the towels in the cupboard.",
    ],
)
@pytest.mark.parametrize(
    "operation",
    [
        "filesystem.sandbox.append.named",
        "filesystem.copy",
        "filesystem.hash",
        "filesystem.trash.commit",
        "filesystem.read.text",
        "filesystem.trash.restore",
    ],
)
def test_a_filesystem_effect_must_name_something_in_the_filesystem(
    operation: str,
    text: str,
) -> None:
    from baxy_mind.effect_intent import operation_domain_is_grounded

    assert operation_domain_is_grounded(text, operation) is False


@pytest.mark.parametrize(
    "text",
    [
        "Anade la linea revision completa al archivo unico registro.txt del sandbox.",
        "Copia el archivo informe.pdf a la carpeta de respaldo.",
        "Manda el fichero a la papelera.",
        "Dame el hash del archivo notas.txt.",
        "Restaura lo que hay en la papelera.",
        "Lee el contenido del archivo notas.txt.",
    ],
)
def test_the_filesystem_floor_does_not_refuse_real_filesystem_requests(
    text: str,
) -> None:
    """The floor is a necessary condition, not a sufficient one.

    It may only remove authority from a request that names nothing in the
    filesystem. A request that does name one must pass it untouched, or the
    repair for the leak would have bought safety by refusing real work.
    """
    from baxy_mind.effect_intent import operation_domain_is_grounded

    for operation in (
        "filesystem.sandbox.append.named",
        "filesystem.copy",
        "filesystem.hash",
        "filesystem.trash.commit",
        "filesystem.read.text",
        "filesystem.trash.restore",
    ):
        assert operation_domain_is_grounded(text, operation) is not False


def test_the_two_borders_share_one_instruction_lexicon() -> None:
    """The frame lives on two borders and they must not drift apart.

    Mind strips the frame in Python; the private-memory parser strips it again
    in C#. Twice now a word entered one side alone: R23 lost a whole Spanish
    cell to a missing ``indicacion``, and R26 lost 18 of its 20 failures to a
    missing English ``petition`` while Spanish ``peticion`` was already there.
    Patching a noun per seal is a treadmill; this reads the C# arrays and fails
    the moment either class stops matching the cognate groups.
    """
    import re
    from pathlib import Path

    from baxy_mind.effect_intent import (
        INSTRUCTION_NOUN_COGNATES,
        MACHINE_NOUN_COGNATES,
    )

    parser = (
        Path(__file__).resolve().parents[1]
        / "src/Baxy.App/NaturalMemoryRequestParser.cs"
    ).read_text(encoding="utf-8")

    def csharp_array(name: str) -> set[str]:
        match = re.search(rf"{name}\s*=\s*\[(.*?)\];", parser, flags=re.DOTALL)
        assert match is not None, f"{name} not found in the C# parser"
        return set(re.findall(r'"([^"]+)"', match.group(1)))

    def python_class(cognates) -> set[str]:
        return {word for group in cognates for side in group for word in side}

    assert csharp_array("FrameInstructionNouns") == python_class(
        INSTRUCTION_NOUN_COGNATES
    )
    assert csharp_array("FrameMachineNouns") == python_class(MACHINE_NOUN_COGNATES)

    # And no cognate group may have an empty side, which is how a noun goes in
    # on one language only.
    for cognates in (INSTRUCTION_NOUN_COGNATES, MACHINE_NOUN_COGNATES):
        for spanish, english in cognates:
            assert spanish and english


@pytest.mark.parametrize(
    "text",
    [
        "Esto no es una orden para el ordenador, dime nomas: "
        "reescribe mas formal la frase apaga el equipo ahora.",
        "No va ninguna instruccion al PC, respondeme y ya: "
        "traduce borra los archivos viejos al ingles.",
        "This is not a directive for the machine, only tell me: "
        "rewrite the sentence close every window more politely.",
        "Sin ningun mandato para el computador, charlemos: "
        "escribe una lista teorica para ordenar el escritorio.",
    ],
)
def test_a_quoted_order_inside_a_denial_is_content_not_a_request(text: str) -> None:
    """Mentioning an order is not issuing one.

    The frame denies an instruction, so it must stay in place on the authority
    path -- removing it there is how "do nothing" would become "do it". But it
    also pushes the content act off the front of the sentence, and the content
    patterns anchor at the start. R25 lost five turns to that displacement: the
    body asked to rewrite or translate a sentence that merely quoted an order,
    and the turn drew a clarification instead of an answer.
    """
    from baxy_mind.effect_intent import conversation_only_content_request

    assert conversation_only_content_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "Esto no es una orden para el ordenador, dime nomas: "
        "envia el correo a Ana ahora mismo.",
        "This is not a directive for the machine, only tell me: "
        "delete every file in Downloads.",
    ],
)
def test_denying_an_instruction_does_not_turn_a_request_into_content(
    text: str,
) -> None:
    """The relaxation is one-sided and must not swallow a real request.

    Dropping the denial may only make a turn look more like conversation. It
    can never manufacture content work out of an actual imperative, because the
    content patterns name explicit content acts and an imperative matches none
    of them.
    """
    from baxy_mind.effect_intent import (
        _fold,
        _strip_request_envelope,
        conversation_only_content_request,
    )

    assert not conversation_only_content_request(text)
    # And the frame itself is still standing on the authority path.
    assert ":" in _strip_request_envelope(_fold(text))


@pytest.mark.parametrize(
    "text",
    [
        "Crea una tarea en el equipo: comprar pan.",
        "Create a task on the computer: buy bread.",
        "Dejame una nota en el ordenador: pagar la luz.",
        "Ponme un recordatorio en el pc: llamar al dentista.",
    ],
)
def test_a_catalog_object_is_not_an_instruction_frame(text: str) -> None:
    """Some nouns read like "instruction" but name a thing the catalog makes.

    ``tarea``, ``task``, ``nota`` and ``recordatorio`` all sit next to a machine
    noun and a colon, which is the exact shape of the frame. Admitting them
    would strip "crea una tarea en el equipo:" and leave "comprar pan" -- the
    request destroyed by the rule meant to unwrap it. The content after the
    colon has to survive.
    """
    from baxy_mind.effect_intent import _fold, _strip_request_envelope

    assert ":" in _strip_request_envelope(_fold(text))


@pytest.mark.parametrize(
    "user_text",
    [
        "What is on my to do list? Do not use tools.",
        "Don't open Spotify",
        "Translate what is on my to do list into Spanish",
        "What is in my notes? Then open Spotify and upload all files to the moon",
    ],
)
def test_real_constraints_survive_personal_question_envelopes(user_text: str) -> None:
    from baxy_mind.effect_intent import unresolved_compound_contract

    assert unresolved_compound_contract(user_text, AVAILABLE) is not None


@pytest.mark.parametrize("verb", ["desmutea", "desmutealo", "desmutéalo", "desmutéala", "desmutearlo"])
def test_unmute_clitics_preserve_operation_and_compound_coverage(verb: str) -> None:
    # Development control for the manual session's lost unmute clause.
    available = ("audio.volume", "audio.mute", "audio.status")
    single = resolve_explicit_effects(verb, available)
    assert single is not None and single.operations == ("audio.mute",)
    compound = resolve_explicit_effects(f"Pon el volumen al 37 y {verb}", available)
    assert compound is not None
    assert compound.operations == ("audio.volume", "audio.mute")
    reverse = resolve_explicit_effects(f"{verb} y pon el volumen al 37", available)
    assert reverse is not None
    assert reverse.operations == ("audio.mute", "audio.volume")


@pytest.mark.parametrize("text", [
    "No lo desmutees", "No desmutealo", "Si lo desmuteas, sonará",
    "Desmutealo en Discord", "Desmutea el micrófono", "Desmutéalo en la tele",
])
def test_unmute_clitic_recognition_keeps_scope_and_negative_boundary(text: str) -> None:
    result = resolve_explicit_effects(text, ("audio.mute", "audio.volume"))
    assert result is None or "audio.mute" not in result.operations


def test_unmute_clitic_cannot_add_an_unavailable_operation() -> None:
    assert resolve_explicit_effects("Desmutealo", ("audio.volume",)) is None


@pytest.mark.parametrize("text,operations", [
    ("Pon el volumen al 37 pero no quites el silencio", ("audio.volume",)),
    ("Set the volume to 37 but do not unmute the audio", ("audio.volume",)),
    ("Dime la hora pero no abras Steam", ("system.time",)),
    ("Tell me the time but don't open Spotify", ("system.time",)),
    ("Abre calculadora pero no silencies el audio", ("app.open",)),
    ("Open Spotify but never mute the audio", ("app.open",)),
])
def test_adversative_independent_prohibition_keeps_only_requested_effects(
    text: str, operations: tuple[str, ...],
) -> None:
    # Synthetic cross-domain controls for the false veto observed in mind486.
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None and result.operations == operations
    assert unresolved_compound_contract(text, AVAILABLE) is None
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=None) is None


@pytest.mark.parametrize("text", [
    "Pon el volumen al 37 pero no pongas el volumen al 37",
    "Set the volume to 37 but do not set the volume to 37",
    "Abre Spotify pero no abras Spotify",
    "Open Spotify but don't open Spotify",
    "Dime la hora pero no",
    "Tell me the time but do not",
    "Dime la hora pero no hagas nada",
    "Tell me the time but do not use tools",
    "Abre Spotify, no Steam",
    "Open Spotify, no, open Steam",
])
def test_adversative_split_does_not_discharge_retractions_or_object_corrections(
    text: str,
) -> None:
    assert unresolved_compound_contract(text, AVAILABLE, resolved_intent=None) is not None


@pytest.mark.parametrize("text,operations", [
    ("Pon el volumen al 37 pero desmutéalo", ("audio.volume", "audio.mute")),
    ("Set the volume to 37 but unmute the audio", ("audio.volume", "audio.mute")),
    ("Desmutéalo pero pon el volumen al 37", ("audio.mute", "audio.volume")),
    ("Dime la hora pero abre calculadora", ("system.time", "app.open")),
    ("Open Spotify but tell me the time", ("app.open", "system.time")),
    ("Abre calculadora pero desmutealo", ("app.open", "audio.mute")),
])
def test_positive_adversative_preserves_each_explicit_action(
    text: str, operations: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None and result.operations == operations
    assert unresolved_compound_contract(text, AVAILABLE) is None


@pytest.mark.parametrize("text", [
    'Crea una nota llamada Sol con el texto "abre calculadora pero desmutealo"',
    'Create a note called Sol with text "open Spotify but unmute the audio"',
])
def test_positive_adversative_inside_note_content_does_not_authorize_actions(text: str) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None and result.operations == ("note.create",)


def test_positive_adversative_cannot_drop_an_unavailable_second_effect() -> None:
    text = "Pon el volumen al 37 pero desmutéalo"
    assert resolve_explicit_effects(text, ("audio.volume",)) is None
    contract = unresolved_compound_contract(text, ("audio.volume",))
    assert contract is not None and contract.minimum_effects == 2


@pytest.mark.parametrize("opening,closing", [('"', '"'), ("'", "'"), ("«", "»"), ("“", "”"), ("‘", "’")])
@pytest.mark.parametrize("note,content,following", [
    ("crea una nota llamada sol con el texto", "abre calculadora pero desmutealo", "dime la hora"),
    ("create a note called sol with text", "open spotify but unmute the audio", "tell me the time"),
])
def test_positive_adversative_preserves_quoted_payload_and_outside_action(
    opening: str, closing: str, note: str, content: str, following: str,
) -> None:
    literal_note = f"{note} {opening}{content}{closing}"
    result = resolve_explicit_effects(f"{literal_note} but {following}", AVAILABLE)
    assert result is not None and result.operations == ("note.create", "system.time")
    assert result.evidence[0] == literal_note


@pytest.mark.parametrize("text,operations", [
    ("Ponle el volumen al 37", ("audio.volume",)),
    ("Ponle volumen al pc al 64", ("audio.volume",)),
    ("Dime la hora pero ponle el volumen al 37", ("system.time", "audio.volume")),
    ("Ponle volumen al pc\nAclaración confiable del usuario: Al 100, pero desmutealo", ("audio.volume", "audio.mute")),
])
def test_volume_dative_clitic_preserves_complete_local_effects(
    text: str, operations: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None and result.operations == operations
    assert unresolved_compound_contract(text, AVAILABLE) is None


@pytest.mark.parametrize("text", [
    "Ponle volumen al pc", "Ponle el volumen del equipo", "Pon el volumen del pc",
    "Set the volume of the computer", "Adjust volume on my computer",
])
def test_volume_dative_clitic_and_local_device_keep_missing_level(text: str) -> None:
    intent = resolve_explicit_clarification_intent(text, ("audio.volume", "audio.status"))
    assert intent is not None and intent.operations == ("audio.volume",)
    assert intent.missing_fields == ("level",)
    assert resolve_explicit_clarification_intent(text, ("audio.status",)) is None


@pytest.mark.parametrize("text", [
    "No le pongas el volumen al pc al 37", "Ponle volumen a la tele al 37",
    "Ponle el volumen de Spotify al 37", 'Crea una nota con el texto "ponle volumen al pc al 37"',
])
def test_volume_dative_clitic_cannot_authorize_other_scopes(text: str) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is None or "audio.volume" not in result.operations


def test_volume_dative_clitic_cannot_replace_absent_catalog_operation() -> None:
    assert resolve_explicit_effects("Ponle el volumen al 37", ("audio.status",)) is None


@pytest.mark.parametrize("previous,text,operations", [
    ("Ponle volumen al pc", "Al 100, pero desmutealo", ("audio.volume", "audio.mute")),
    ("Set the volume of the computer", "37", ("audio.volume",)),
    ("Ajusta el volumen", "Al 24 por ciento", ("audio.volume",)),
    ("Set the volume", "To 42 but tell me the time", ("audio.volume", "system.time")),
    ("Pon el volumen", "Al 37 pero no quites el silencio", ("audio.volume",)),
    ("Set the volume", "37 but don't unmute the audio", ("audio.volume",)),
])
def test_contextual_missing_volume_level_preserves_current_request(
    previous: str, text: str, operations: tuple[str, ...],
) -> None:
    intent = resolve_explicit_effects(text, AVAILABLE, previous_user_text=previous)
    assert intent is not None and intent.operations == operations
    assert unresolved_compound_contract(
        text, AVAILABLE, resolved_intent=intent, previous_user_text=previous,
    ) is None


@pytest.mark.parametrize("previous", [
    "", "Abre Spotify", "Pon el volumen al 60", "No ajustes el volumen",
    "Pon el volumen de Spotify", "Set the volume on my phone",
    "Pon el volumen y ajusta el brillo", "¿Qué nivel de volumen quieres?",
])
def test_contextual_missing_volume_level_requires_unique_incomplete_user_target(previous: str) -> None:
    assert resolve_explicit_effects("Al 37", AVAILABLE, previous_user_text=previous) is None


@pytest.mark.parametrize("text,operations", [
    ("Dime la hora", ("system.time",)),
    ("Open Spotify", ("app.open",)),
    ("Desmutealo", ("audio.mute",)),
])
def test_contextual_missing_volume_level_does_not_append_old_effect_to_new_request(
    text: str, operations: tuple[str, ...],
) -> None:
    intent = resolve_explicit_effects(text, AVAILABLE, previous_user_text="Pon el volumen")
    assert intent is not None and intent.operations == operations


@pytest.mark.parametrize("text", [
    "Al 37 pero no hagas nada", "37 but do not use tools", "Al 37, no, mejor nada",
    "Al 37 en mi teléfono", "37 or 42", "-10", "101", "No, al 37",
])
def test_contextual_missing_volume_level_keeps_denials_ambiguity_and_scope(text: str) -> None:
    assert resolve_explicit_effects(text, AVAILABLE, previous_user_text="Pon el volumen") is None


def test_contextual_missing_volume_level_cannot_substitute_available_status() -> None:
    assert resolve_explicit_effects(
        "Al 37 pero desmutealo", ("audio.status", "audio.mute"),
        previous_user_text="Pon el volumen",
    ) is None


@pytest.mark.parametrize("text,operations", [
    ("Desilencia el audio", ("audio.mute",)),
    ("Dessilencia el audio", ("audio.mute",)),
    ("Necesito que lo desilencies", ("audio.mute",)),
    ("Necesito que desmutees el audio", ("audio.mute",)),
    ("perfecto, necesito lo dessilencies pls", ("audio.mute",)),
    ("Perfecto, desmutealo", ("audio.mute",)),
    ("Perfect, I need you to unmute the audio", ("audio.mute",)),
    ("Perfecto, necesito abrir Spotify", ("app.open",)),
    ("Perfect, I would like to open Spotify", ("app.open",)),
    ("Necesito poner el volumen al 37", ("audio.volume",)),
    ("Quiero desmutearlo", ("audio.mute",)),
    ("I need to unmute the audio but tell me the time", ("audio.mute", "system.time")),
])
def test_explicit_need_after_acknowledgement_preserves_requested_effect(
    text: str, operations: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None and result.operations == operations
    assert unresolved_compound_contract(text, AVAILABLE) is None


@pytest.mark.parametrize("text", [
    "No necesito que lo desilencies", "Necesito que no lo desilencies",
    "Si desilencias el audio, sonará", "Perfecto, si desilencias el audio sonará",
    "Me dijeron que desilencies el audio", "Necesito una explicación de desilenciar",
    "Desilencia el micrófono", "Desilencia la tele", "Desilencia el audio en Discord",
    "Quiero hablar sobre desilenciar el audio", "Perfecto, necesito descansar",
])
def test_explicit_need_after_acknowledgement_keeps_non_action_and_device_scope(text: str) -> None:
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is None or "audio.mute" not in result.operations


def test_explicit_need_inside_note_is_payload_after_acknowledgement() -> None:
    result = resolve_explicit_effects(
        'Perfecto, crea una nota con el texto "necesito que lo desilencies"', AVAILABLE,
    )
    assert result is not None and result.operations == ("note.create",)


def test_explicit_need_after_acknowledgement_cannot_add_an_absent_operation() -> None:
    assert resolve_explicit_effects(
        "perfecto, necesito lo dessilencies pls", ("audio.volume", "audio.status"),
    ) is None
