"""Build and preregister BAXY's execution-inert R7 blind product holdout.

R7 is a fresh 700-row population created only after the R6 policy repair.  It
adds colloquial and interrogative requests, discourse wrappers, punctuation
variation, one hundred ordered compositions, and adversarial non-actions that
lexically collide with supported families.  It is sealed before measurement,
contains no normalized surface from prior development or holdout populations,
and never grants execution authority.
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
)


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v7.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v7.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r7_mind.json"
MIND_AUDIT = REPO / "artifacts/holdout/generalization_product_holdout_r7_mind.raw.jsonl"
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r7_memory.trx"
PRODUCT_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r7_product.json"
PRIOR_CORPORA = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl",
    REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v3.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v4.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v5.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v6.jsonl",
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
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r7.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r7.py",
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


def scenario6(
    operations: tuple[str, ...],
    es_one: str,
    es_two: str,
    en_one: str,
    en_two: str,
    mixed_one: str,
    mixed_two: str,
) -> Scenario:
    return Scenario(
        operations,
        (
            Utterance("es", es_one),
            Utterance("es", es_two),
            Utterance("en", en_one),
            Utterance("en", en_two),
            Utterance("spanglish", mixed_one),
            Utterance("spanglish", mixed_two),
        ),
    )


SCENARIOS: dict[str, Scenario] = {
    "app": scenario6(
        ("app.installed",),
        "Averigua en el inventario instalado si tengo Krita",
        "Échale un vistazo a los programas y confirma la presencia de 7-Zip",
        "Could you see in the local app inventory whether Krita is there",
        "Have a look through installed software for 7-Zip",
        "Chequea installed apps para ver si Krita aparece",
        "Have a look en los programas locales for 7-Zip",
    ),
    "audio": scenario6(
        ("audio.status",),
        "¿Cómo anda de volumen y salida este PC? Revísalo",
        "Quiero saber por dónde y a qué nivel está saliendo el sonido",
        "How are volume and output routing doing on this PC? Check them",
        "I want to know where the sound is going and at what level",
        "How anda el volume y la output route? Check it",
        "Quiero saber where sound is going y at what level",
    ),
    "backup": scenario6(
        ("backup.list",),
        "¿Con qué respaldos privados cuento para volver atrás?",
        "Sácame la relación de copias locales recuperables",
        "Which private backups could I roll back to",
        "Pull up the list of recoverable local copies",
        "Which private respaldos puedo use to roll back",
        "Dame la list de recoverable local copies",
    ),
    "bluetooth": scenario6(
        ("bluetooth.device.list",),
        "Haz un recuento de lo que la radio Bluetooth alcanza a ver",
        "¿Qué equipos aparecen alrededor por Bluetooth? Consúltalo",
        "Take stock of what the Bluetooth radio can currently see",
        "Which devices show up nearby over Bluetooth? Check",
        "Haz count de what Bluetooth radio can see",
        "Which equipos show up nearby por Bluetooth? Check",
    ),
    "browser": scenario6(
        ("browser.tabs.list",),
        "Pásame el panorama de páginas abiertas en el navegador",
        "¿Qué tengo cargado en cada pestaña ahora mismo?",
        "Give me an overview of the pages open in the browser",
        "What do I currently have loaded across my tabs",
        "Dame overview de pages abiertas en browser",
        "What tengo loaded across mis tabs ahora",
    ),
    "calendar": scenario6(
        ("calendar.event.list",),
        "Mira mi agenda y dime qué compromisos caen hoy",
        "Quisiera el itinerario de citas que tengo mañana",
        "Look at my calendar and tell me which commitments fall today",
        "I would like the appointment itinerary I have tomorrow",
        "Look at mi agenda y dime today's commitments",
        "Quiero el appointment itinerary que tengo tomorrow",
    ),
    "capture": scenario6(
        ("capture.screenshot",),
        "Déjame una instantánea de cómo se ve el escritorio",
        "Guarda en imagen lo que está mostrando el monitor completo",
        "Leave me a snapshot of how the desktop looks",
        "Save what the full display is showing as an image",
        "Déjame a snapshot de how desktop looks",
        "Save en image lo que full display is showing",
    ),
    "clipboard": scenario6(
        ("clipboard.read.text",),
        "¿Qué palabras tengo listas para pegar? Léelas",
        "Recupera el fragmento textual que quedó copiado",
        "Which words do I have ready to paste? Read them",
        "Retrieve the text fragment that was left copied",
        "Qué words tengo ready to paste? Read them",
        "Recupera the text fragment que quedó copied",
    ),
    "email": scenario6(
        ("email.latest.read",),
        "Abre para lectura el mensaje que entró último al correo",
        "Cuéntame el contenido de lo recién recibido en el buzón",
        "Open the last message that arrived in mail for reading",
        "Tell me the contents of the item just received in my inbox",
        "Lee el message que arrived last al correo",
        "Tell me el content de lo just received in inbox",
    ),
    "filesystem": scenario6(
        ("filesystem.known.search",),
        "Rastrea en Documentos los archivos llamados Plan Boreal",
        "A ver si encuentras pases de tren dentro de Descargas",
        "Track down files named Boreal Plan inside Documents",
        "See whether you can find train passes under Downloads",
        "Track down archivos Plan Boreal inside Documents",
        "A ver si find train passes dentro de Downloads",
    ),
    "game": scenario6(
        ("game.catalog.list",),
        "¿Qué se puede jugar desde mi colección local de Steam?",
        "Hazme un listado de los títulos que reconoce la biblioteca",
        "What can be played from my local Steam collection",
        "Make me a list of the titles recognized by the game library",
        "Qué can I play desde mi local Steam collection",
        "Haz a list de titles recognized por game library",
    ),
    "input": scenario6(
        ("input.keyboard.status",),
        "Comprueba con qué distribución estoy tecleando",
        "¿Qué esquema de entrada tiene activo el teclado?",
        "Check which layout I am typing with",
        "Which input scheme is active on the keyboard",
        "Check con qué layout estoy typing",
        "Qué input scheme tiene active el keyboard",
    ),
    "media": scenario6(
        ("media.status",),
        "¿Hay algo sonando? Dame el estado de reproducción",
        "Identifica la pista o vídeo que controla la sesión multimedia",
        "Is anything playing? Give me the playback state",
        "Identify the track or video controlled by the media session",
        "Hay anything playing? Dame playback state",
        "Identify la track o video que media session controls",
    ),
    "memory": scenario6(
        ("memory.status",),
        "Comprueba si tus recuerdos privados de este PC están operativos",
        "¿Está funcionando ahora tu almacén personal de memoria local?",
        "Check whether your private memories on this PC are operational",
        "Is your personal local-memory store working right now",
        "Check si tus private memories de este PC están operational",
        "Está working ahora tu personal local-memory store",
    ),
    "message": scenario6(
        ("message.recipient.resolve", "message.send"),
        "Escríbele por WhatsApp a Paula: el acceso ya quedó habilitado",
        "Que Discord le avise a Martín que cambiamos al salón norte",
        "Write to Quinn on WhatsApp: access has now been enabled",
        "Have Discord notify Parker that we moved to the north room",
        "Escríbele on WhatsApp a River: access ya quedó enabled",
        "Have Discord avise a Skyler que moved to north room",
    ),
    "network": scenario6(
        ("network.status",),
        "Haz un diagnóstico rápido del enlace general de la máquina",
        "¿El equipo está llegando bien a la red? Verifícalo",
        "Run a quick check of the machine's general network link",
        "Is the computer reaching the network properly? Verify it",
        "Haz quick check del machine general network link",
        "Está computer reaching la red properly? Verify it",
    ),
    "note": scenario6(
        ("note.list",),
        "Reúne los apuntes privados que he ido guardando aquí",
        "Quiero ver el índice completo de mis notas locales",
        "Gather the private memos I have been saving here",
        "I want to see the complete index of my local notes",
        "Gather los private memos que fui saving aquí",
        "Quiero see el complete index de local notes",
    ),
    "notification": scenario6(
        ("notification.list.due",),
        "Señálame los avisos cuyo momento ya pasó y siguen pendientes",
        "¿Quedó alguna notificación vencida sin atender?",
        "Point out notices whose time has passed and remain pending",
        "Are any expired notifications still unattended",
        "Show avisos whose time passed y remain pending",
        "Quedó any expired notification todavía unattended",
    ),
    "ocr": scenario6(
        ("capture.screenshot", "ocr.read"),
        "Haz una captura y pásame a caracteres lo escrito en pantalla",
        "Fotografía el escritorio para sacar de ahí todo el texto legible",
        "Take a capture and turn the writing on screen into characters",
        "Photograph the desktop to pull out all readable text",
        "Haz capture y turn screen writing into characters",
        "Photograph el desktop para pull out readable text",
    ),
    "office": scenario6(
        ("office.document.create",),
        "Ármame un Word que se llame Acuerdos de invierno",
        "Necesito una planilla Excel titulada Costos del taller",
        "Put together a Word file called Winter Agreements",
        "I need an Excel sheet titled Workshop Costs",
        "Ármame a Word called Acuerdos de invierno",
        "Necesito an Excel sheet titulada Workshop Costs",
    ),
    "package": scenario6(
        ("package.install.prepare",),
        "Deja Mozilla.Firefox preparado en la antesala de instalación",
        "Ubica GitHub.GitHubDesktop y alístalo para instalar",
        "Get Mozilla.Firefox staged for installation",
        "Locate GitHub.GitHubDesktop and ready it for install",
        "Deja Mozilla.Firefox staged para installation",
        "Locate GitHub.GitHubDesktop y alístalo for install",
    ),
    "peripheral": scenario6(
        ("peripheral.list",),
        "Haz inventario del hardware externo enchufado al equipo",
        "¿Qué accesorios físicos reconoce conectados Windows?",
        "Inventory the external hardware plugged into the computer",
        "Which physical accessories does Windows recognize as connected",
        "Inventory el external hardware enchufado al computer",
        "Qué physical accessories reconoce Windows as connected",
    ),
    "reminder": scenario6(
        ("reminder.list",),
        "Repasa las cosas que te pedí traerme a la memoria después",
        "Enséñame lo que aún tengo agendado para recordar",
        "Review the things I asked you to bring back to mind later",
        "Show me what I still have scheduled to remember",
        "Review las cosas que pedí bring back to mind later",
        "Show me lo que aún está scheduled para remember",
    ),
    "routine": scenario6(
        ("routine.list",),
        "¿Qué secuencias habituales sabe repetir Baxy?",
        "Pon a la vista las automatizaciones personales guardadas",
        "Which habitual sequences does Baxy know how to repeat",
        "Bring the saved personal automations into view",
        "Qué habitual sequences sabe Baxy repeat",
        "Show las saved personal automations",
    ),
    "streaming": scenario6(
        ("streaming.play.named",),
        "Encuentra Arcane en Netflix y arráncala",
        "Quiero ver The Good Place; ponla desde Netflix",
        "Find Arcane on Netflix and start it",
        "I want to watch The Good Place; put it on from Netflix",
        "Find Arcane en Netflix y arráncala",
        "Quiero watch The Good Place; ponla from Netflix",
    ),
    "system": scenario6(
        ("system.status",),
        "Dame una revisión de conjunto de cómo marcha el computador",
        "¿Está sano el sistema en términos generales? Compruébalo",
        "Give me an overall review of how the computer is running",
        "Is the system healthy overall? Check it",
        "Dame overall review de cómo marcha computer",
        "Is el system healthy en general? Check it",
    ),
    "task": scenario6(
        ("task.list",),
        "Ponme al día con los quehaceres que siguen abiertos",
        "¿Qué asuntos de mi lista todavía esperan resolución?",
        "Bring me up to date on the chores that remain open",
        "Which items on my list are still awaiting resolution",
        "Ponme up to date con chores que remain open",
        "Which asuntos de mi list todavía await resolution",
    ),
    "vision": scenario6(
        ("capture.screenshot", "vision.describe"),
        "Mira el escritorio mediante una captura y explícame la escena",
        "Toma una imagen de pantalla para contarme qué objetos aparecen",
        "Look at the desktop through a capture and explain the scene",
        "Take a screen image and tell me which objects appear",
        "Mira desktop through a capture y explain the scene",
        "Take screen image para contarme which objects appear",
    ),
    "web": scenario6(
        ("web.search",),
        "Rastrea en la web por qué migran las mariposas monarca",
        "Averigua online opiniones sobre molinos manuales de café",
        "Search the web for why monarch butterflies migrate",
        "Find online opinions about manual coffee grinders",
        "Search en la web why monarch butterflies migrate",
        "Averigua online reviews de manual coffee grinders",
    ),
    "wifi": scenario6(
        ("wifi.status",),
        "Revisa cómo está de enlace y señal la conexión sin cable",
        "¿Sigue asociado el Wi-Fi de esta máquina?",
        "Check the link and signal condition of the wireless connection",
        "Is this machine's Wi-Fi still associated",
        "Check link y signal de wireless connection",
        "Sigue associated el Wi-Fi de this machine",
    ),
    "window": scenario6(
        ("window.active",),
        "Ubica qué ventana se quedó con el foco del escritorio",
        "¿Cuál de las aplicaciones está recibiendo mis teclas ahora?",
        "Locate the window that currently holds desktop focus",
        "Which application is receiving my keystrokes right now",
        "Locate qué window holds desktop focus",
        "Cuál application está receiving mis keystrokes ahora",
    ),
}


CLARIFICATIONS = Scenario(
    ("message.send",),
    (
        Utterance("es", "Hazle saber a Rocío que el paquete llegó"),
        Utterance("es", "Pásale a Luciano el aviso salgo al mediodía"),
        Utterance("es", "Escríbele a Abril que ya tengo las entradas"),
        Utterance("es", "Manda a Thiago que hoy trabajo desde casa"),
        Utterance("en", "Get word to Rowan that the parcel arrived"),
        Utterance("en", "Pass Lee the update I leave at noon"),
        Utterance("en", "Write Hayden that I already have the tickets"),
        Utterance("en", "Send Finley that I am working from home today"),
        Utterance("spanglish", "Hazle know a Blair que parcel arrived"),
        Utterance("spanglish", "Send a Alex el update que leave at noon"),
    ),
)


COMPOSITION_PARTS: dict[str, dict[str, str]] = {
    "system.status": {"es": "la salud global del sistema", "en": "overall system health", "spanglish": "overall health del sistema"},
    "network.status": {"es": "el acceso general a la red", "en": "general network access", "spanglish": "general access a la red"},
    "wifi.status": {"es": "la señal y enlace Wi-Fi", "en": "the Wi-Fi link and signal", "spanglish": "Wi-Fi link y signal"},
    "audio.status": {"es": "el volumen y salida de audio", "en": "audio volume and output", "spanglish": "volume y audio output"},
    "media.status": {"es": "lo que se está reproduciendo", "en": "what is currently playing", "spanglish": "what is playing ahora"},
    "window.active": {"es": "la ventana con el foco", "en": "the window holding focus", "spanglish": "window que holds focus"},
    "browser.tabs.list": {"es": "las páginas abiertas del navegador", "en": "the browser's open pages", "spanglish": "open pages del browser"},
    "clipboard.read.text": {"es": "el texto listo para pegar", "en": "the text ready to paste", "spanglish": "text ready para paste"},
    "input.keyboard.status": {"es": "la distribución del teclado", "en": "the keyboard input layout", "spanglish": "keyboard input layout"},
    "peripheral.list": {"es": "los accesorios físicos conectados", "en": "attached physical accessories", "spanglish": "physical accessories conectados"},
    "bluetooth.device.list": {"es": "los equipos visibles por Bluetooth", "en": "devices visible over Bluetooth", "spanglish": "devices visibles por Bluetooth"},
    "task.list": {"es": "las tareas que siguen abiertas", "en": "tasks that remain open", "spanglish": "tasks que remain open"},
    "note.list": {"es": "el índice de notas privadas", "en": "the private-note index", "spanglish": "private note index"},
    "reminder.list": {"es": "los recordatorios aún programados", "en": "reminders still scheduled", "spanglish": "reminders todavía scheduled"},
    "routine.list": {"es": "las rutinas personales guardadas", "en": "saved personal routines", "spanglish": "saved personal routines"},
    "backup.list": {"es": "las copias recuperables", "en": "recoverable backup copies", "spanglish": "recoverable backup copies"},
    "game.catalog.list": {"es": "los juegos del catálogo local", "en": "games in the local catalog", "spanglish": "games del local catalog"},
    "calendar.event.list": {"es": "las citas de hoy", "en": "today's appointments", "spanglish": "today's appointments"},
    "email.latest.read": {"es": "el contenido del correo recién llegado", "en": "the newly arrived email's contents", "spanglish": "content del newly arrived email"},
    "notification.list.due": {"es": "los avisos vencidos", "en": "overdue notices", "spanglish": "overdue avisos"},
    "app.installed": {"es": "si Krita figura instalada", "en": "whether Krita is installed", "spanglish": "si Krita is installed"},
    "filesystem.known.search": {"es": "archivos Plan Boreal en Documentos", "en": "Boreal Plan files in Documents", "spanglish": "Plan Boreal files en Documents"},
}


def _composition_text(language: str, parts: list[str], index: int) -> str:
    intros = {
        "es": (
            "Hazme este chequeo por partes: ",
            "Necesito un parte conjunto de ",
            "Sin omitir ninguno, revisa en este orden: ",
            "Ve punto por punto con ",
        ),
        "en": (
            "Run this check in parts: ",
            "I need a combined report covering ",
            "Without skipping any, inspect in this order: ",
            "Go point by point through ",
        ),
        "spanglish": (
            "Haz este check por parts: ",
            "Necesito a combined report de ",
            "Without skipping ninguno, revisa en order: ",
            "Go point por point con ",
        ),
    }
    separator = "; después, " if language == "es" else "; then, "
    if language == "spanglish":
        separator = "; después check, "
    text = intros[language][index % 4] + separator.join(parts)
    if index >= 60:
        endings = {
            "es": ", devolviendo cada resultado por separado",
            "en": ", returning each result separately",
            "spanglish": ", returning cada result por separado",
        }
        text += endings[language]
    return text


def _generated_compositions() -> tuple[builder.Composition, ...]:
    operations = tuple(COMPOSITION_PARTS)
    steps = (1, 3, 5, 7, 9)
    languages = ("es", "en", "spanglish")
    rows: list[builder.Composition] = []
    for index in range(94):
        size = 3 + index % 6
        step = steps[(index // 6) % len(steps)]
        cursor = (index * 5 + index // 7) % len(operations)
        selected: list[str] = []
        while len(selected) < size:
            operation = operations[cursor]
            if operation not in selected:
                selected.append(operation)
            cursor = (cursor + step) % len(operations)
        language = languages[index % len(languages)]
        parts = [COMPOSITION_PARTS[item][language] for item in selected]
        rows.append(
            builder.Composition(
                tuple(selected),
                Utterance(language, _composition_text(language, parts, index)),
            )
        )
    return tuple(rows)


SPECIAL_COMPOSITIONS = (
    builder.Composition(("capture.screenshot", "ocr.read"), Utterance("es", "Primero retrata la pantalla y, usando esa imagen, entrégame las palabras visibles")),
    builder.Composition(("capture.screenshot", "vision.describe"), Utterance("en", "Capture the desktop first and use that image to explain the visible scene")),
    builder.Composition(("capture.screenshot", "vision.describe", "ocr.read"), Utterance("spanglish", "Take a screen capture; describe la scene y también transcribe its visible words")),
    builder.Composition(("message.recipient.resolve", "message.send", "task.list"), Utterance("es", "Por WhatsApp avisa a Julia que salgo en diez y luego muéstrame mis tareas abiertas")),
    builder.Composition(("task.list", "capture.screenshot", "ocr.read"), Utterance("en", "List my open tasks, then capture the screen and read the text from that capture")),
    builder.Composition(("calendar.event.list", "capture.screenshot", "vision.describe", "clipboard.read.text"), Utterance("spanglish", "Show today's calendar, capture the desktop, describe that image y finally read clipboard text")),
)
COMPOSITIONS = _generated_compositions() + SPECIAL_COMPOSITIONS


CONVERSATIONS = (
    Utterance("es", "Define qué es un sistema operativo sin inspeccionar mi PC"),
    Utterance("es", "Redacta más amable la frase cierra todas las pestañas"),
    Utterance("es", "Si comprara una tableta, abriría allí mis notas"),
    Utterance("es", "No captures nada; explícame qué significa captura de pantalla"),
    Utterance("es", "Por qué los navegadores organizan páginas en pestañas"),
    Utterance("es", "Compara recordatorios y notificaciones sin consultar mis datos"),
    Utterance("es", "Escribe un cuento donde Bluetooth sea una ciudad imaginaria"),
    Utterance("es", "Traduce instala VLC cuando llegues al inglés"),
    Utterance("es", "Ayer el volumen estaba bajo, pero no quiero cambiarlo"),
    Utterance("es", "Qué ocurriría si otro computador perdiera su Wi-Fi"),
    Utterance("es", "Calcula ciento veintisiete dividido por siete"),
    Utterance("es", "Dame una receta de sopa para una noche fría"),
    Utterance("es", "Qué quiere decir OCR en procesamiento de documentos"),
    Utterance("es", "Explica por qué conviene tener respaldos"),
    Utterance("es", "Simula una conversación, no envíes nada, entre Paula y Martín"),
    Utterance("es", "Escribe una lista teórica para ordenar tareas"),
    Utterance("es", "Cuéntame la historia de las ventanas en interfaces gráficas"),
    Utterance("es", "Qué diferencia hay entre teclado mecánico y de membrana"),
    Utterance("en", "Define an operating system without inspecting my PC"),
    Utterance("en", "Rewrite the sentence close every tab more politely"),
    Utterance("en", "If I bought a tablet, I would open my notes there"),
    Utterance("en", "Do not capture anything; explain what screenshot means"),
    Utterance("en", "Why do browsers arrange pages into tabs"),
    Utterance("en", "Compare reminders with notifications without checking my data"),
    Utterance("en", "Write a story where Bluetooth is an imaginary city"),
    Utterance("en", "Translate instala VLC cuando llegues into English"),
    Utterance("en", "The volume was low yesterday, but I do not want it changed"),
    Utterance("en", "What would happen if another computer lost its Wi-Fi"),
    Utterance("en", "Calculate one hundred twenty-seven divided by seven"),
    Utterance("en", "Give me a soup recipe for a cold evening"),
    Utterance("en", "What does OCR mean in document processing"),
    Utterance("en", "Explain why keeping backups is useful"),
    Utterance("en", "Role-play a conversation between Paula and Martin; send nothing"),
    Utterance("en", "Write a theoretical checklist for organizing tasks"),
    Utterance("en", "Tell me the history of windows in graphical interfaces"),
    Utterance("en", "What is the difference between mechanical and membrane keyboards"),
    Utterance("spanglish", "Define qué es operating system sin inspect my PC"),
    Utterance("spanglish", "Rewrite más polite la sentence close every tab"),
    Utterance("spanglish", "If compro una tablet, abriría my notes there"),
    Utterance("spanglish", "No capture nada; explain what screenshot means"),
    Utterance("spanglish", "Why browsers organizan pages en tabs"),
    Utterance("spanglish", "Compare reminders y notifications sin check my data"),
    Utterance("spanglish", "Write un story donde Bluetooth sea imaginary city"),
    Utterance("spanglish", "Pon into English la frase instala VLC cuando llegues"),
    Utterance("spanglish", "Ayer volume was low, pero no change it"),
    Utterance("spanglish", "What pasaría si another computer lost su Wi-Fi"),
    Utterance("spanglish", "Calculate ciento twenty-seven divided by seven"),
    Utterance("spanglish", "Dame a soup recipe para cold evening"),
    Utterance("spanglish", "What quiere decir OCR en document processing"),
    Utterance("spanglish", "Explain por qué keeping backups is useful"),
    Utterance("spanglish", "Role-play una conversation; send nothing a Paula ni Martín"),
    Utterance("spanglish", "Write una theoretical checklist para organize tasks"),
    Utterance("spanglish", "Tell me la history de windows en graphical interfaces"),
    Utterance("spanglish", "Qué difference hay between mechanical y membrane keyboards"),
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
    builder.CAMPAIGN = "r7"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v7"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v7"
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "31_families_x_6_fresh_colloquial_bases_x_2_surfaces_plus_"
        "10_clarifications_x_2_surfaces_plus_100_ordered_compositions_"
        "of_2_to_8_effects_x_2_surfaces_plus_"
        "54_lexically_colliding_conversations_x_2_surfaces"
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
        "es": "Baxy, hazme un favor: ",
        "en": "Baxy — one thing: ",
        "spanglish": "Baxy, una cosa please: ",
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
