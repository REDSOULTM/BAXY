"""Build and preregister BAXY's execution-inert R4 blind product holdout.

R4 broadens the prior ownership-aware matrix with unseen compositional pairs
and explicit out-of-scope conversation.  The population remains lexically
disjoint from all prior development and blind cohorts and is sealed before
either product owner sees a row.
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


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v4.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v4.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r4_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r4_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r4_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r4_product.json"
)
PRIOR_CORPORA = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl",
    REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v3.jsonl",
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
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r4.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r4.py",
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
        "Consulta el software local para saber si está Audacity",
        "Comprueba en el menú Inicio la presencia de Paint",
        "Look through the local software inventory for Audacity",
        "Find out whether Paint exists among the Start menu apps",
        "Chequea si Audacity figura en el software de este PC",
    ),
    "audio": scenario(
        ("audio.status",),
        "Cuéntame el nivel de volumen y la salida de sonido vigentes",
        "Averigua cómo quedó el audio del equipo",
        "Describe the machine's present volume and sound output",
        "Find out how computer audio is set at the moment",
        "Dame el volume level y la sound output de ahora",
    ),
    "backup": scenario(
        ("backup.list",),
        "Enséñame los puntos de recuperación privados que existen",
        "Cuáles son las copias recuperables guardadas en el equipo",
        "Present the private recovery points stored on this machine",
        "List the restorable copies currently kept here",
        "Muéstrame los private recovery points disponibles",
    ),
    "bluetooth": scenario(
        ("bluetooth.device.list",),
        "Qué equipos cercanos reconoce la conexión Bluetooth",
        "Enséñame los accesorios hallados por Bluetooth",
        "Which nearby devices does the Bluetooth connection recognize",
        "Present the accessories found through Bluetooth discovery",
        "Dame los nearby devices encontrados por Bluetooth",
    ),
    "browser": scenario(
        ("browser.tabs.list",),
        "Cuéntame qué sitios permanecen abiertos en pestañas",
        "Enséñame la colección de tabs del navegador",
        "Tell me which sites remain open in browser tabs",
        "Present the browser's collection of currently open pages",
        "Dame la colección de browser tabs que sigue abierta",
    ),
    "calendar": scenario(
        ("calendar.event.list",),
        "Qué compromisos marca mi agenda para esta jornada",
        "Consulta las actividades calendarizadas para mañana",
        "Which commitments are on my agenda for this day",
        "Retrieve the activities scheduled on tomorrow's calendar",
        "Muéstrame tomorrow's actividades de agenda",
    ),
    "capture": scenario(
        ("capture.screenshot",),
        "Fotografía el contenido visible del monitor",
        "Guarda una instantánea de mi escritorio en este instante",
        "Photograph the content visible on the monitor",
        "Save an instant picture of my desktop right now",
        "Haz una instant picture del desktop visible",
    ),
    "clipboard": scenario(
        ("clipboard.read.text",),
        "Recítame las palabras almacenadas en el portapapeles",
        "Qué contenido de texto está listo para pegar",
        "Recite the words stored in the clipboard",
        "What textual content is ready to be pasted",
        "Dime qué words están ready to paste",
    ),
    "email": scenario(
        ("email.latest.read",),
        "Cuéntame el contenido del email que acaba de llegar",
        "Recupera el mensaje más nuevo de la bandeja de entrada",
        "Tell me the contents of the email that just arrived",
        "Retrieve the newest item from the inbox",
        "Lee el email que just arrived al buzón",
    ),
    "filesystem": scenario(
        ("filesystem.known.search",),
        "Rastrea en Documentos elementos llamados contrato",
        "Explora Descargas hasta hallar archivos de reserva",
        "Scan Documents for items named contract",
        "Explore Downloads to locate reservation files",
        "Busca reservation files dentro de Descargas",
    ),
    "game": scenario(
        ("game.catalog.list",),
        "Qué títulos jugables reconoce Steam en esta máquina",
        "Enséñame la lista de videojuegos disponibles localmente",
        "Which playable titles does Steam recognize on this machine",
        "Present the list of video games available locally",
        "Muéstrame los playable titles del Steam local",
    ),
    "input": scenario(
        ("input.keyboard.status",),
        "Dime con qué mapa de teclas estoy escribiendo",
        "Averigua la distribución de entrada que usa el sistema",
        "Tell me which key map I am typing with",
        "Find the input layout the system is using",
        "Dime cuál key map está usando el teclado",
    ),
    "media": scenario(
        ("media.status",),
        "Qué contenido multimedia está corriendo en este instante",
        "Cuéntame el estado de la sesión de reproducción",
        "What media content is running at this instant",
        "Tell me the state of the playback session",
        "Dime qué media content está running ahora",
    ),
    "memory": scenario(
        ("memory.status",),
        "Indica el estado de tus recuerdos privados en este dispositivo",
        "Confirma si la memoria guardada localmente funciona",
        "State whether your private memories on this device are active",
        "Confirm that locally stored memory is working",
        "Dime si tus private memories están activas aquí",
    ),
    "message": scenario(
        ("message.recipient.resolve", "message.send"),
        "Escríbele en Discord a Carla que ya terminé",
        "Pasa por WhatsApp a Diego el mensaje llego en diez",
        "Write to Avery on Discord that I have finished",
        "Pass Jordan the message see you in ten through WhatsApp",
        "Escribe a Taylor via Discord que I'm ready",
    ),
    "network": scenario(
        ("network.status",),
        "Cuéntame cómo anda el acceso de este PC a la red",
        "Determina la condición global de conectividad",
        "Tell me how this PC's access to the network is doing",
        "Determine the overall connectivity condition",
        "Dime la overall connectivity de esta máquina",
    ),
    "note": scenario(
        ("note.list",),
        "Qué anotaciones privadas conservo en el equipo",
        "Enséñame el índice de apuntes locales",
        "Which private notes do I keep on this computer",
        "Present the index of locally saved notes",
        "Dame el index de mis local notes",
    ),
    "notification": scenario(
        ("notification.list.due",),
        "Qué alertas pendientes ya superaron su hora",
        "Enséñame los avisos cuyo plazo se cumplió",
        "Which pending alerts have gone past their time",
        "Present the notices whose deadline has elapsed",
        "Dame los pending alerts que ya expired",
    ),
    "ocr": scenario(
        ("capture.screenshot", "ocr.read"),
        "Fotografía la pantalla y conviértela en palabras",
        "Guarda una instantánea del monitor y lee sus letras",
        "Photograph the screen and turn it into words",
        "Save a monitor snapshot and read its lettering",
        "Toma un screen snapshot y conviértelo en text",
    ),
    "office": scenario(
        ("office.document.create",),
        "Produce un documento Word llamado Acta semanal",
        "Arma una hoja Excel con el nombre Inventario agosto",
        "Produce a Word file named Weekly Minutes",
        "Assemble an Excel sheet called August Inventory",
        "Crea una Excel sheet llamada Inventario agosto",
    ),
    "package": scenario(
        ("package.install.prepare",),
        "Prepara el paquete VideoLAN.VLC para su instalación",
        "Ubica Git.Git y déjalo listo para instalar",
        "Stage the VideoLAN.VLC package for installation",
        "Locate Git.Git and make it ready to install",
        "Resuelve Git.Git y déjalo ready para instalar",
    ),
    "peripheral": scenario(
        ("peripheral.list",),
        "Qué dispositivos externos están conectados físicamente",
        "Enséñame el inventario de accesorios enchufados",
        "Which external devices are physically attached",
        "Present the inventory of plugged-in accessories",
        "Lista los external devices enchufados ahora",
    ),
    "reminder": scenario(
        ("reminder.list",),
        "Qué cosas me pediste recordar más adelante",
        "Enséñame todos mis avisos programados",
        "Which things did I ask you to remember for later",
        "Present all of my scheduled reminders",
        "Muéstrame todos my scheduled reminders",
    ),
    "routine": scenario(
        ("routine.list",),
        "Qué secuencias automáticas tengo configuradas",
        "Enséñame mis automatizaciones habituales",
        "Which automatic sequences have I configured",
        "Present my habitual automations",
        "Dame mis automatic routines configuradas",
    ),
    "streaming": scenario(
        ("streaming.play.named",),
        "Pon Dark usando Netflix",
        "Localiza Stranger Things en Netflix e iníciala",
        "Put on Dark through Netflix",
        "Find Stranger Things in Netflix and start it",
        "Inicia Dark through Netflix",
    ),
    "system": scenario(
        ("system.status",),
        "Cuéntame cómo se encuentra la máquina en conjunto",
        "Haz un chequeo del estado integral del computador",
        "Tell me how the machine is doing as a whole",
        "Check the computer's overall operating condition",
        "Dime la overall condition del computador",
    ),
    "task": scenario(
        ("task.list",),
        "Qué asuntos siguen sin completar en mi lista",
        "Enséñame los pendientes que permanecen abiertos",
        "Which items remain unfinished on my list",
        "Present the to-dos that are still open",
        "Dame los to-dos que siguen unfinished",
    ),
    "vision": scenario(
        ("capture.screenshot", "vision.describe"),
        "Fotografía el monitor y cuéntame qué representa la imagen",
        "Guarda una instantánea del escritorio e interpreta su contenido",
        "Photograph the monitor and tell me what the image depicts",
        "Save a desktop snapshot and interpret its contents",
        "Toma un desktop snapshot y describe la image",
    ),
    "web": scenario(
        ("web.search",),
        "Averigua en internet cómo se forman las auroras",
        "Consulta la red acerca de cafeteras italianas",
        "Research online how auroras are formed",
        "Consult the web about Italian coffee makers",
        "Investiga online cómo se forman auroras",
    ),
    "wifi": scenario(
        ("wifi.status",),
        "Cuéntame cómo está el enlace inalámbrico del PC",
        "Determina la condición actual de la señal Wi-Fi",
        "Tell me how the PC's wireless link is doing",
        "Determine the present condition of the Wi-Fi signal",
        "Dime la current condition del Wi-Fi link",
    ),
    "window": scenario(
        ("window.active",),
        "Qué programa está recibiendo mis teclas ahora",
        "Identifica la ventana situada delante de las demás",
        "Which program is receiving my keystrokes now",
        "Identify the window sitting in front of all others",
        "Dime qué window está receiving keyboard input",
    ),
}


CLARIFICATIONS = scenario(
    ("message.send",),
    "Avísale a Elena que la reunión cambió",
    "Escríbele a Martín el texto ya voy de camino",
    "Let Casey know that the meeting moved",
    "Write Quinn the message I am on my way",
    "Dile a Robin que the report is done",
)


COMPOSITIONS = (
    builder.Composition(
        ("system.status", "audio.status"),
        Utterance("es", "Comprueba el estado integral del PC y también su sonido"),
    ),
    builder.Composition(
        ("network.status", "wifi.status"),
        Utterance("es", "Dime cómo anda la red y luego el enlace Wi-Fi"),
    ),
    builder.Composition(
        ("clipboard.read.text", "note.list"),
        Utterance("es", "Lee lo listo para pegar y después enumera mis anotaciones"),
    ),
    builder.Composition(
        ("calendar.event.list", "task.list"),
        Utterance("es", "Consulta la agenda de hoy junto con mis tareas sin completar"),
    ),
    builder.Composition(
        ("reminder.list", "notification.list.due"),
        Utterance("es", "Enséñame mis recordatorios y las alertas que vencieron"),
    ),
    builder.Composition(
        ("app.installed", "peripheral.list"),
        Utterance("es", "Revisa si Audacity está instalado y qué accesorios están enchufados"),
    ),
    builder.Composition(
        ("browser.tabs.list", "clipboard.read.text"),
        Utterance("es", "Enumera las páginas abiertas y recítame el portapapeles"),
    ),
    builder.Composition(
        ("game.catalog.list", "media.status"),
        Utterance("es", "Muestra los juegos locales y qué reproducción está corriendo"),
    ),
    builder.Composition(
        ("bluetooth.device.list", "audio.status"),
        Utterance("en", "Show detected Bluetooth gear and the current sound output"),
    ),
    builder.Composition(
        ("window.active", "input.keyboard.status"),
        Utterance("en", "Identify the front window and the keyboard map in use"),
    ),
    builder.Composition(
        ("email.latest.read", "task.list"),
        Utterance("en", "Retrieve the newest inbox item and list unfinished tasks"),
    ),
    builder.Composition(
        ("backup.list", "note.list"),
        Utterance("en", "Present the private recovery points and my saved notes"),
    ),
    builder.Composition(
        ("routine.list", "reminder.list"),
        Utterance("en", "Show configured routines along with scheduled reminders"),
    ),
    builder.Composition(
        ("filesystem.known.search", "web.search"),
        Utterance("en", "Find contract in Documents and research contract templates online"),
    ),
    builder.Composition(
        ("capture.screenshot", "clipboard.read.text"),
        Utterance("en", "Photograph the screen, then read the clipboard text"),
    ),
    builder.Composition(
        ("package.install.prepare", "app.installed"),
        Utterance("spanglish", "Deja Git.Git ready y check si Audacity está installed"),
    ),
    builder.Composition(
        ("streaming.play.named", "audio.status"),
        Utterance("spanglish", "Pon Dark through Netflix y dime el sound level"),
    ),
    builder.Composition(
        ("wifi.status", "bluetooth.device.list"),
        Utterance("spanglish", "Check the Wi-Fi signal y lista Bluetooth devices cercanos"),
    ),
    builder.Composition(
        ("office.document.create", "calendar.event.list"),
        Utterance("spanglish", "Crea un Word llamado Acta y show today's agenda"),
    ),
    builder.Composition(
        ("capture.screenshot", "vision.describe", "ocr.read"),
        Utterance("spanglish", "Toma una snapshot, describe la escena y read its text"),
    ),
)


CONVERSATIONS = (
    Utterance("es", "Explícame por qué cambian de color las hojas"),
    Utterance("es", "Cuéntame un chiste corto sobre pingüinos"),
    Utterance("es", "Resume las causas principales de la Revolución francesa"),
    Utterance("es", "Propón tres nombres para una cafetería de barrio"),
    Utterance("es", "Traduce al francés la frase buenos días amiga"),
    Utterance("es", "Ayúdame a practicar una entrevista laboral"),
    Utterance("es", "Explica la diferencia entre masa y peso"),
    Utterance("en", "Explain why the sky can look red at sunset"),
    Utterance("en", "Tell me a brief joke about penguins"),
    Utterance("en", "Summarize the main causes of the French Revolution"),
    Utterance("en", "Suggest three names for a neighborhood coffee shop"),
    Utterance("en", "Translate good morning my friend into French"),
    Utterance("en", "Help me rehearse for a job interview"),
    Utterance("en", "Explain the difference between mass and weight"),
    Utterance("spanglish", "Explícame why leaves change color"),
    Utterance("spanglish", "Cuéntame a short penguin joke"),
    Utterance("spanglish", "Resume the causes de la Revolución francesa"),
    Utterance("spanglish", "Sugiere three names para una cafetería"),
    Utterance("spanglish", "Traduce good morning al francés"),
    Utterance("spanglish", "Ayúdame to rehearse una job interview"),
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
    builder.CAMPAIGN = "r4"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v4"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v4"
    builder.EXPECTED_POPULATION = 400
    builder.MINIMUM_CASES = 400
    builder.METHOD_DESCRIPTION = (
        "31_families_x_5_lexical_bases_x_2_surfaces_plus_"
        "5_clarifications_x_2_surfaces_plus_20_compositions_x_2_surfaces_plus_"
        "20_out_of_scope_conversations_x_2_surfaces"
    )
    builder.REFERENCES = (
        "https://arxiv.org/abs/2008.09335",
        "https://aclanthology.org/2021.eacl-main.257/",
        "https://aclanthology.org/2020.acl-main.442/",
        "https://arxiv.org/abs/2007.08970",
        "https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm",
    )
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, por favor, ",
        "en": "Baxy, would you please ",
        "spanglish": "Baxy, porfa, ",
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
