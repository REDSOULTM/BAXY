"""Build and preregister BAXY's execution-inert R5 blind product holdout.

R5 stresses language variety, speech-like disfluency, unseen entities,
out-of-scope lexical collisions, and productivity/order through compositions
of up to five supported families.  It remains ownership-aware, lexically
disjoint from every earlier cohort, and is sealed before either owner runs.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402
from scripts.build_generalization_surface_holdout import (  # noqa: E402
    Scenario,
    Utterance,
    scenario,
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v5.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v5.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r5_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r5_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r5_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r5_product.json"
)
PRIOR_CORPORA = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl",
    REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v3.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v4.jsonl",
    REPO / "experiments/mind_router_spike/data/exact_operation_development.v1.jsonl",
)
POLICY_SOURCES = (
    REPO / "src/baxy_mind/effect_intent.py",
    REPO / "src/baxy_mind/router.py",
    REPO / "src/baxy_mind/llm.py",
    REPO / "src/baxy_mind/turn_evidence.py",
    REPO / "src/baxy_mind/planner.py",
    REPO / "src/baxy_mind/__main__.py",
    REPO / "src/Baxy.App/NaturalMemoryRequestParser.cs",
    REPO / "src/Baxy.Kernel/Operations/ProductCatalog.cs",
)
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r5.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r5.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/probe_current_catalog_review.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    REPO / "scripts/build_generalization_product_holdout_r3.py",
    REPO / "scripts/build_generalization_surface_holdout.py",
)


SCENARIOS: dict[str, Scenario] = {
    "app": scenario(
        ("app.installed",),
        "A ver, confirma si Obsidian aparece entre el software del equipo",
        "Necesito saber si GIMP está en las aplicaciones de Inicio",
        "Establish whether Obsidian is part of the local app inventory",
        "I need to know if GIMP shows up among installed programs",
        "Mira si Obsidian shows up como software instalado",
    ),
    "audio": scenario(
        ("audio.status",),
        "Antes que nada, cuéntame cómo están volumen y salida sonora",
        "Oye, averigua qué configuración de sonido rige ahora mismo",
        "Give me a reading of the current volume and sound route",
        "I need the machine's audio setup as it stands now",
        "Checa el current volume y la ruta de sound",
    ),
    "backup": scenario(
        ("backup.list",),
        "A ver, qué instantáneas recuperables conserva Baxy",
        "Necesito el inventario de respaldos privados restaurables",
        "Bring up the private restore snapshots available on this PC",
        "I need the list of locally recoverable backup copies",
        "Show las recoverable snapshots privadas que quedan",
    ),
    "bluetooth": scenario(
        ("bluetooth.device.list",),
        "Oye, qué aparatos ha descubierto Bluetooth por aquí",
        "A ver, enumera el hardware próximo que ve la radio Bluetooth",
        "Bring up the nearby gear discovered over Bluetooth",
        "I need every device currently visible to Bluetooth discovery",
        "Lista el nearby gear que Bluetooth can see",
    ),
    "browser": scenario(
        ("browser.tabs.list",),
        "A ver, qué páginas siguen cargadas en el navegador",
        "Oye, recorre las pestañas que permanecen abiertas",
        "Bring up every page still loaded across my browser tabs",
        "I need the browser's presently open tab set",
        "Dame las pages still loaded en browser tabs",
    ),
    "calendar": scenario(
        ("calendar.event.list",),
        "Necesito los compromisos de agenda que caen en el día de hoy",
        "A ver, qué encuentros tiene el calendario para mañana",
        "Bring up today's commitments from my calendar",
        "I need tomorrow's booked appointments from the agenda",
        "Show los booked appointments de tomorrow",
    ),
    "capture": scenario(
        ("capture.screenshot",),
        "Oye, conserva una imagen de lo que muestra el escritorio",
        "A ver, registra visualmente el monitor tal como está ahora",
        "Preserve an image of whatever the desktop is showing now",
        "Record the monitor's current visual state as a picture",
        "Save una image de whatever the desktop shows",
    ),
    "clipboard": scenario(
        ("clipboard.read.text",),
        "Necesito escuchar las palabras que tengo preparadas para pegar",
        "A ver, revela el texto retenido en el portapapeles",
        "Read back the words currently waiting to be pasted",
        "Reveal the textual payload held by the clipboard",
        "Read back las words waiting en el clipboard",
    ),
    "email": scenario(
        ("email.latest.read",),
        "Oye, qué dice el correo que entró hace un momento",
        "Necesito el contenido del mensaje más reciente del buzón",
        "Read out the mailbox item that came in moments ago",
        "I need the contents of the most recently received email",
        "Dime qué says el mail que came in moments ago",
    ),
    "filesystem": scenario(
        ("filesystem.known.search",),
        "A ver, rastrea presupuesto anual dentro de Documentos",
        "Oye, inspecciona Descargas por archivos llamados itinerario",
        "Hunt through Documents for items named annual budget",
        "Search Downloads for files whose name includes itinerary",
        "Find archivos itinerary dentro de Downloads",
    ),
    "game": scenario(
        ("game.catalog.list",),
        "Necesito ver los juegos que reconoce mi instalación de Steam",
        "A ver, qué títulos locales figuran como jugables",
        "Bring up the games recognized by this Steam installation",
        "I need the locally playable title inventory",
        "Show el locally playable inventory de Steam",
    ),
    "input": scenario(
        ("input.keyboard.status",),
        "Oye, con qué distribución de teclas estoy redactando ahora",
        "A ver, identifica el mapa de entrada activo del teclado",
        "Tell me the key arrangement I am writing with right now",
        "Identify the active input map for this keyboard",
        "Dime el key arrangement con que estoy writing",
    ),
    "media": scenario(
        ("media.status",),
        "A ver, qué sesión audiovisual se encuentra activa",
        "Oye, dime qué contenido está en reproducción en este momento",
        "Report the audiovisual session that is active right now",
        "Tell me what content the playback session currently holds",
        "Dime qué content la playback session tiene now",
    ),
    "memory": scenario(
        ("memory.status",),
        "A ver, dime si tu almacenamiento privado de recuerdos está operativo",
        "Oye, confirma la condición de la memoria personal local de Baxy",
        "Report whether your private recollection store is operational",
        "I need the condition of Baxy's locally kept personal memory",
        "Check si your private recollection store está working",
    ),
    "message": scenario(
        ("message.recipient.resolve", "message.send"),
        "Por Discord hazle llegar a Inés que el informe quedó firmado",
        "En WhatsApp cuéntale a Óscar que aterrizo a las seis",
        "Through Discord let Harper know the report has been signed",
        "On WhatsApp get the note landing at six to Rowan",
        "Via Discord dile a Morgan the report got signed",
    ),
    "network": scenario(
        ("network.status",),
        "A ver, cómo se encuentra la comunicación general del computador",
        "Oye, determina si el equipo mantiene acceso a la red",
        "Give me the computer's overall communication condition",
        "Determine whether this machine still has network access",
        "Dime la overall communication condition del PC",
    ),
    "note": scenario(
        ("note.list",),
        "Necesito el repertorio de apuntes privados guardados aquí",
        "A ver, qué anotaciones locales conservo todavía",
        "Bring up the private memos retained on this device",
        "I need the inventory of locally kept personal notes",
        "Show los private memos retained aquí",
    ),
    "notification": scenario(
        ("notification.list.due",),
        "Oye, cuáles avisos pendientes ya quedaron fuera de plazo",
        "A ver, presenta las alertas cuya hora programada pasó",
        "Bring up pending notices that have crossed their scheduled time",
        "I need alerts whose due time has already passed",
        "Show pending notices que crossed su scheduled time",
    ),
    "ocr": scenario(
        ("capture.screenshot", "ocr.read"),
        "Registra el monitor como imagen y extrae todas sus palabras",
        "Oye, conserva lo visible en pantalla y transcribe sus letras",
        "Record the monitor as an image and extract all of its words",
        "Preserve the visible screen, then transcribe its lettering",
        "Save la visible screen y extract all its words",
    ),
    "office": scenario(
        ("office.document.create",),
        "Necesito un documento Word denominado Informe trimestral",
        "Arma un libro Excel que se llame Control de turnos",
        "Make a Word document named Quarterly Report",
        "Put together an Excel workbook called Shift Control",
        "Build un Excel workbook llamado Control de turnos",
    ),
    "package": scenario(
        ("package.install.prepare",),
        "Oye, deja Notepad++.Notepad++ preparado para instalarse",
        "A ver, resuelve Python.Python.3.13 y alista su instalación",
        "Get Notepad++.Notepad++ staged for installation",
        "Resolve Python.Python.3.13 and leave its install ready",
        "Stage Python.Python.3.13 para que quede install-ready",
    ),
    "peripheral": scenario(
        ("peripheral.list",),
        "A ver, qué accesorios físicos reconoce conectados el PC",
        "Necesito el recuento de dispositivos enchufados externamente",
        "Bring up the physical accessories attached to this computer",
        "I need an inventory of externally plugged devices",
        "Show los physical accessories attached al PC",
    ),
    "reminder": scenario(
        ("reminder.list",),
        "Oye, qué asuntos tengo programados para recordar después",
        "Necesito la relación completa de avisos recordatorios futuros",
        "Bring up everything I scheduled myself to remember later",
        "I need the full set of future reminder notices",
        "Show everything scheduled para remember later",
    ),
    "routine": scenario(
        ("routine.list",),
        "A ver, qué flujos habituales tiene guardados el asistente",
        "Necesito el repertorio de secuencias automatizadas disponibles",
        "Bring up the habitual workflows saved in the assistant",
        "I need the available set of automated sequences",
        "Show los habitual workflows guardados en Baxy",
    ),
    "streaming": scenario(
        ("streaming.play.named",),
        "Quiero ver Ozark mediante Netflix",
        "Oye, encuentra Wednesday dentro de Netflix y ponla",
        "Put Ozark on using Netflix",
        "Find Wednesday inside Netflix and start the show",
        "Pon Ozark using Netflix ahora",
    ),
    "system": scenario(
        ("system.status",),
        "A ver, dame una lectura global de cómo se encuentra el equipo",
        "Oye, evalúa la condición conjunta del sistema ahora mismo",
        "Give me a whole-machine reading of how this computer is doing",
        "Assess the system's combined operating condition right now",
        "Dame a whole-machine reading del equipo",
    ),
    "task": scenario(
        ("task.list",),
        "Necesito saber qué obligaciones siguen abiertas en mi lista",
        "A ver, presenta los pendientes todavía sin resolver",
        "Bring up the obligations that remain open on my list",
        "I need every unresolved to-do still pending",
        "Show las obligations que remain open",
    ),
    "vision": scenario(
        ("capture.screenshot", "vision.describe"),
        "Registra visualmente el escritorio y explícame la escena resultante",
        "Oye, conserva la pantalla como imagen e interpreta lo que contiene",
        "Record the desktop visually and explain the resulting scene",
        "Preserve the screen as an image and interpret what it contains",
        "Save la screen as image y explain the resulting scene",
    ),
    "web": scenario(
        ("web.search",),
        "A ver, indaga en línea cómo migran las ballenas jorobadas",
        "Oye, busca en internet reseñas de molinos manuales",
        "Investigate online how humpback whales migrate",
        "Look across the web for reviews of hand coffee grinders",
        "Research online cómo humpback whales migrate",
    ),
    "wifi": scenario(
        ("wifi.status",),
        "A ver, en qué condición está el vínculo inalámbrico de esta PC",
        "Oye, comprueba cómo anda la señal de Wi-Fi en este instante",
        "Give me the condition of this PC's wireless connection",
        "Check how the Wi-Fi signal is behaving at this moment",
        "Dime cómo the Wi-Fi signal is behaving ahora",
    ),
    "window": scenario(
        ("window.active",),
        "A ver, qué aplicación posee el foco de escritura en este instante",
        "Oye, señala la ventana que está por encima del resto",
        "Identify the application that owns typing focus right now",
        "Point out the window currently above the rest",
        "Dime qué app owns typing focus ahora",
    ),
}


CLARIFICATIONS = scenario(
    ("message.send",),
    "Hazle saber a Valentina que cambiaron el salón",
    "Cuéntale a Joaquín el mensaje ya salí",
    "Get the update the room changed to Cameron",
    "Let Peyton know I have already left",
    "Dile a Alex the room has changed",
)


COMPOSITIONS = (
    builder.Composition(
        ("system.status", "network.status", "audio.status"),
        Utterance("es", "Dame la condición del equipo, después la red y por último el sonido"),
    ),
    builder.Composition(
        ("task.list", "calendar.event.list", "reminder.list"),
        Utterance("es", "Presenta mis pendientes, la agenda de hoy y los recordatorios futuros"),
    ),
    builder.Composition(
        ("note.list", "clipboard.read.text", "browser.tabs.list"),
        Utterance("es", "Enumera mis apuntes, lee lo listo para pegar y muestra las páginas abiertas"),
    ),
    builder.Composition(
        ("bluetooth.device.list", "peripheral.list", "wifi.status"),
        Utterance("es", "Lista lo visto por Bluetooth, los accesorios enchufados y la señal Wi-Fi"),
    ),
    builder.Composition(
        ("app.installed", "game.catalog.list", "package.install.prepare"),
        Utterance("es", "Confirma Obsidian instalado, enseña los juegos locales y alista GitHub.cli"),
    ),
    builder.Composition(
        ("email.latest.read", "notification.list.due", "calendar.event.list"),
        Utterance("en", "Read the newest email, show overdue alerts, and bring up today's calendar"),
    ),
    builder.Composition(
        ("backup.list", "routine.list", "reminder.list"),
        Utterance("en", "List private restore copies, saved routines, and future reminders"),
    ),
    builder.Composition(
        ("window.active", "input.keyboard.status", "clipboard.read.text"),
        Utterance("en", "Identify the focused window, current key map, and clipboard words"),
    ),
    builder.Composition(
        ("filesystem.known.search", "web.search", "browser.tabs.list"),
        Utterance("en", "Find itinerary in Downloads, research travel templates online, then list browser tabs"),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        Utterance("en", "Record the screen, interpret the scene, and transcribe its visible writing"),
    ),
    builder.Composition(
        ("audio.status", "media.status", "streaming.play.named"),
        Utterance("spanglish", "Dime sound setup, what is playing y pon Ozark on Netflix"),
    ),
    builder.Composition(
        ("network.status", "wifi.status", "bluetooth.device.list"),
        Utterance("spanglish", "Check network access, the Wi-Fi link y nearby Bluetooth gear"),
    ),
    builder.Composition(
        ("calendar.event.list", "task.list", "note.list", "reminder.list"),
        Utterance("es", "Consulta agenda, tareas, notas y recordatorios, exactamente en ese orden"),
    ),
    builder.Composition(
        ("app.installed", "peripheral.list", "game.catalog.list", "backup.list"),
        Utterance("en", "Check Obsidian installation, attached accessories, local games, and restore copies"),
    ),
    builder.Composition(
        ("browser.tabs.list", "window.active", "input.keyboard.status", "clipboard.read.text"),
        Utterance("en", "List tabs, name the front window, report the keyboard map, then read the clipboard"),
    ),
    builder.Composition(
        ("system.status", "audio.status", "network.status", "wifi.status"),
        Utterance("spanglish", "Report system health, sound, network access y Wi-Fi signal"),
    ),
    builder.Composition(
        ("email.latest.read", "calendar.event.list", "task.list", "notification.list.due"),
        Utterance("spanglish", "Read newest mail, today's agenda, open tasks y overdue alerts"),
    ),
    builder.Composition(
        ("office.document.create", "package.install.prepare", "app.installed"),
        Utterance("spanglish", "Build un Word named Brief, stage GitHub.cli y check Obsidian installed"),
    ),
    builder.Composition(
        ("note.list", "reminder.list", "routine.list", "backup.list", "task.list"),
        Utterance("es", "Dame notas, recordatorios, rutinas, respaldos y tareas sin cambiar el orden"),
    ),
    builder.Composition(
        ("window.active", "browser.tabs.list", "clipboard.read.text", "media.status", "audio.status"),
        Utterance("en", "Name the front window, list tabs, read clipboard text, report playback, and give sound status"),
    ),
)


CONVERSATIONS = (
    Utterance("es", "Explícame cómo funciona Bluetooth sin revisar ningún dispositivo"),
    Utterance("es", "Reescribe con tono amable la frase envía el informe hoy"),
    Utterance("es", "Calcula mentalmente cuánto es diecisiete por veintitrés"),
    Utterance("es", "Dame una receta breve de sopa de zapallo"),
    Utterance("es", "Compara en teoría Wi-Fi y Ethernet sin mirar este computador"),
    Utterance("es", "Traduce al italiano la oración abre Steam mañana"),
    Utterance("es", "Inventa una adivinanza cuya respuesta sea ventana"),
    Utterance("en", "Explain how a computer clipboard works without reading mine"),
    Utterance("en", "Rewrite the phrase send the report today in a warmer tone"),
    Utterance("en", "Work out nineteen times twenty-seven mentally"),
    Utterance("en", "Give me a short pumpkin soup recipe"),
    Utterance("en", "Compare Wi-Fi and Ethernet in general without checking this PC"),
    Utterance("en", "Translate the sentence open Steam tomorrow into Italian"),
    Utterance("en", "Make up a riddle whose answer is window"),
    Utterance("spanglish", "Explain cómo funciona el clipboard sin leer mine"),
    Utterance("spanglish", "Rewrite con tono friendly la frase send it today"),
    Utterance("spanglish", "Calculate mentalmente nineteen times eleven"),
    Utterance("spanglish", "Dame a quick recipe de pumpkin soup"),
    Utterance("spanglish", "Compare Wi-Fi y Ethernet en general, not this PC"),
    Utterance("spanglish", "Translate abre Steam mañana into Italian"),
)


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.PRIOR_CORPORA = PRIOR_CORPORA
    builder.POLICY_SOURCES = POLICY_SOURCES
    builder.MEASUREMENT_SOURCES = MEASUREMENT_SOURCES
    builder.BUILDER_DEPENDENCIES = BUILDER_DEPENDENCIES
    builder.CAMPAIGN = "r5"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v5"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v5"
    builder.EXPECTED_POPULATION = 400
    builder.MINIMUM_CASES = 400
    builder.METHOD_DESCRIPTION = (
        "31_families_x_5_speech_like_bases_x_2_surfaces_plus_"
        "5_clarifications_x_2_surfaces_plus_20_productive_compositions_"
        "of_3_to_5_families_x_2_surfaces_plus_"
        "20_lexically_colliding_out_of_scope_conversations_x_2_surfaces"
    )
    builder.REFERENCES = (
        "https://aclanthology.org/2021.acl-long.341/",
        "https://aclanthology.org/2021.acl-long.192/",
        "https://aclanthology.org/2023.findings-acl.91/",
        "https://aclanthology.org/D18-1300/",
        "https://arxiv.org/abs/1909.02027",
        "https://aclanthology.org/2024.acl-long.36/",
        "https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm",
    )
    builder.ADDRESSED_PREFIXES = {
        "es": "A ver Baxy: ",
        "en": "Hey Baxy — ",
        "spanglish": "Oye Baxy, please: ",
    }
    builder.SCENARIOS = SCENARIOS
    builder.CLARIFICATIONS = CLARIFICATIONS
    builder.COMPOSITIONS = COMPOSITIONS
    builder.CONVERSATIONS = CONVERSATIONS


def main() -> int:
    configure()
    return builder.main()


if __name__ == "__main__":
    raise SystemExit(main())
