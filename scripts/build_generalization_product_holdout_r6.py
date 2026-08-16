"""Build and preregister BAXY's execution-inert R6 blind product holdout.

R6 raises the sealed population to 600 cases, introduces fresh speech acts,
longer ordered compositions of up to eight effects, catalog-name collisions,
and self-contained conversation requests that mention supported domains.  It
is ownership-aware, execution-inert, disjoint by normalized surface from all
earlier cohorts, and sealed before either product owner is measured.
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


OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_v6.jsonl"
PREREGISTRATION = (
    REPO / "artifacts/holdout/generalization_product_holdout_v6.preregistration.json"
)
MIND_OUTPUT = REPO / "artifacts/holdout/generalization_product_holdout_r6_mind.json"
MIND_AUDIT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r6_mind.raw.jsonl"
)
MEMORY_TRX = REPO / "artifacts/holdout/generalization_product_holdout_r6_memory.trx"
PRODUCT_OUTPUT = (
    REPO / "artifacts/holdout/generalization_product_holdout_r6_product.json"
)
PRIOR_CORPORA = (
    REPO / "artifacts/development/current_catalog_review_development.v1.jsonl",
    REPO / "artifacts/holdout/generalization_surface_holdout_v1.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v2.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v3.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v4.jsonl",
    REPO / "artifacts/holdout/generalization_product_holdout_v5.jsonl",
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
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r6.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r6.py",
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
        "Confirma si Obsidian está disponible como programa instalado",
        "Revisa las aplicaciones instaladas para ver si aparece GIMP",
        "Check whether Obsidian is present in my installed apps",
        "Inspect installed programs for GIMP",
        "Verify si Obsidian is installed aquí",
        "Check installed applications para GIMP",
    ),
    "audio": scenario6(
        ("audio.status",),
        "Detalla el nivel actual y la ruta de salida del sonido",
        "Comprueba en qué estado se encuentra el audio del equipo",
        "State the present output volume and sound route",
        "Inspect the computer's current audio configuration",
        "Reporta el current sound level y output route",
        "Check cómo está el audio setup del equipo",
    ),
    "backup": scenario6(
        ("backup.list",),
        "Enumera las copias de recuperación privadas disponibles",
        "Muéstrame qué respaldos locales se pueden restaurar",
        "Enumerate the available private recovery copies",
        "Show which local backups are restorable",
        "List las private recovery copies disponibles",
        "Dame los local backups that can be restored",
    ),
    "bluetooth": scenario6(
        ("bluetooth.device.list",),
        "Indica qué dispositivos próximos detecta Bluetooth",
        "Consulta la lista de equipos visibles para la radio Bluetooth",
        "Name the nearby devices detected by Bluetooth",
        "Inspect the equipment visible to the Bluetooth radio",
        "Show qué nearby devices Bluetooth detects",
        "Lista el equipment visible por Bluetooth",
    ),
    "browser": scenario6(
        ("browser.tabs.list",),
        "Indica todas las pestañas que mantiene abiertas el navegador",
        "Consulta el conjunto actual de páginas cargadas en tabs",
        "Name every tab the browser currently keeps open",
        "Inspect the current set of loaded browser pages",
        "Show todas las tabs que browser keeps open",
        "Dame el current set de loaded browser pages",
    ),
    "calendar": scenario6(
        ("calendar.event.list",),
        "Consulta las citas anotadas para hoy en mi calendario",
        "Enumera los eventos de agenda previstos para mañana",
        "Inspect the appointments entered for today on my calendar",
        "Enumerate tomorrow's scheduled agenda events",
        "Show las appointments entered para today",
        "Lista tomorrow's scheduled eventos de agenda",
    ),
    "capture": scenario6(
        ("capture.screenshot",),
        "Captura en una imagen el estado visual de la pantalla",
        "Toma una fotografía digital del escritorio completo",
        "Capture the screen's visual state as an image",
        "Take a digital picture of the entire desktop",
        "Capture en image el visual state de la pantalla",
        "Toma a digital picture del whole desktop",
    ),
    "clipboard": scenario6(
        ("clipboard.read.text",),
        "Recítame el texto que espera dentro del portapapeles",
        "Consulta las palabras almacenadas para el próximo pegado",
        "Recite the text waiting inside the clipboard",
        "Inspect the words stored for the next paste",
        "Read el text waiting inside clipboard",
        "Dime las words stored para next paste",
    ),
    "email": scenario6(
        ("email.latest.read",),
        "Lee el contenido del email recibido más recientemente",
        "Consulta qué dice la última pieza de correo del buzón",
        "Read the contents of the most recently received email",
        "Inspect what the newest mailbox item says",
        "Lee el contents del most recently received email",
        "Dime what the newest mailbox item says",
    ),
    "filesystem": scenario6(
        ("filesystem.known.search",),
        "Localiza facturas marzo por nombre dentro de Documentos",
        "Explora Descargas buscando archivos llamados boarding pass",
        "Locate items named March invoices inside Documents",
        "Explore Downloads for files called boarding pass",
        "Find facturas marzo by name en Documents",
        "Search Downloads por files called boarding pass",
    ),
    "game": scenario6(
        ("game.catalog.list",),
        "Enumera los títulos jugables del catálogo local de Steam",
        "Consulta qué videojuegos contiene mi biblioteca instalada",
        "Enumerate the playable titles in the local Steam catalog",
        "Inspect which games my installed library contains",
        "Show los playable titles del local Steam catalog",
        "Dime which games mi installed library contains",
    ),
    "input": scenario6(
        ("input.keyboard.status",),
        "Indica la distribución de entrada activa para este teclado",
        "Consulta con qué mapa de teclas está escribiendo el equipo",
        "State the active input layout for this keyboard",
        "Inspect which key map the computer is typing with",
        "Reporta el active input layout del keyboard",
        "Check con qué key map está typing el equipo",
    ),
    "media": scenario6(
        ("media.status",),
        "Indica el contenido que mantiene la sesión de reproducción",
        "Consulta qué multimedia se está reproduciendo actualmente",
        "State the content held by the current playback session",
        "Inspect which media is playing at present",
        "Dime el content held por current playback session",
        "Check cuál media is playing actualmente",
    ),
    "memory": scenario6(
        ("memory.status",),
        "Revisa si tu memoria personal local está habilitada",
        "Dime en qué condición se encuentran tus recuerdos privados aquí",
        "Report the operational state of your locally stored memories",
        "Check whether Baxy's personal memory kept on this computer is enabled",
        "Tell me la present condition del private recollection store",
        "Confirma whether tus private memories están working locally",
    ),
    "message": scenario6(
        ("message.recipient.resolve", "message.send"),
        "Por WhatsApp dile a Renata que la reserva quedó confirmada",
        "Vía Discord hazle saber a Tomás que llego después de las nueve",
        "Through WhatsApp let Avery know the booking is confirmed",
        "On Discord get the update I arrive after nine to Jordan",
        "Via WhatsApp dile a Casey the booking quedó confirmed",
        "Por Discord let Sam know que arrive after nine",
    ),
    "network": scenario6(
        ("network.status",),
        "Evalúa la condición global de conectividad de esta máquina",
        "Consulta si el computador conserva acceso general a la red",
        "Assess this machine's overall connectivity condition",
        "Inspect whether the computer retains general network access",
        "Reporta la overall connectivity condition de esta máquina",
        "Check si computer retains general network access",
    ),
    "note": scenario6(
        ("note.list",),
        "Enumera todas las notas privadas almacenadas localmente",
        "Consulta el inventario de anotaciones personales guardadas",
        "Enumerate every private note stored locally",
        "Inspect the inventory of saved personal memos",
        "List todas las private notes stored locally",
        "Show el inventory de saved personal memos",
    ),
    "notification": scenario6(
        ("notification.list.due",),
        "Enumera las notificaciones pendientes cuyo plazo venció",
        "Consulta los avisos programados que ya pasaron su hora",
        "Enumerate pending notifications whose deadline expired",
        "Inspect scheduled notices that are already past their time",
        "Show pending notifications cuyo deadline expired",
        "Lista scheduled notices que are past their time",
    ),
    "ocr": scenario6(
        ("capture.screenshot", "ocr.read"),
        "Captura la pantalla y convierte sus letras visibles en texto",
        "Toma una imagen del escritorio y transcribe toda su escritura",
        "Capture the screen and turn its visible lettering into text",
        "Take a desktop image and transcribe all of its writing",
        "Capture la screen y turn visible lettering into text",
        "Toma desktop image y transcribe toda its writing",
    ),
    "office": scenario6(
        ("office.document.create",),
        "Crea un Word llamado Minuta semanal",
        "Construye un libro Excel denominado Gastos de viaje",
        "Create a Word document called Weekly Minutes",
        "Build an Excel workbook named Travel Expenses",
        "Create un Word called Minuta semanal",
        "Build un Excel workbook denominado Travel Expenses",
    ),
    "package": scenario6(
        ("package.install.prepare",),
        "Prepara Microsoft.PowerToys para su instalación",
        "Resuelve VideoLAN.VLC y déjalo listo para instalar",
        "Leave Microsoft.PowerToys staged and ready to install",
        "Resolve VideoLAN.VLC and leave it ready to install",
        "Prepara Microsoft.PowerToys for installation",
        "Resolve VideoLAN.VLC y leave it install-ready",
    ),
    "peripheral": scenario6(
        ("peripheral.list",),
        "Enumera los periféricos físicos conectados externamente",
        "Consulta qué accesorios reconoce enchufados el computador",
        "Enumerate the physical peripherals connected externally",
        "Inspect which accessories the computer recognizes as attached",
        "Show los physical peripherals connected externally",
        "Dime which accessories computer recognizes attached",
    ),
    "reminder": scenario6(
        ("reminder.list",),
        "Enumera los recordatorios futuros que dejé programados",
        "Consulta todo lo que debo recordar más adelante",
        "Enumerate the future reminders I scheduled",
        "Inspect everything I am due to remember later",
        "Show los future reminders que scheduled",
        "Dime everything que debo remember later",
    ),
    "routine": scenario6(
        ("routine.list",),
        "Enumera las rutinas automáticas disponibles en Baxy",
        "Consulta los flujos habituales que conserva el asistente",
        "Enumerate the automated routines available in Baxy",
        "Inspect the habitual workflows retained by the assistant",
        "List las automated routines available en Baxy",
        "Show los habitual workflows retained por assistant",
    ),
    "streaming": scenario6(
        ("streaming.play.named",),
        "Busca Dark en Netflix y comienza la serie",
        "Pon The Crown usando Netflix",
        "Find Dark on Netflix and start the series",
        "Put The Crown on through Netflix",
        "Busca Dark on Netflix y start the series",
        "Pon The Crown through Netflix ahora",
    ),
    "system": scenario6(
        ("system.status",),
        "Evalúa el estado integral de toda la máquina",
        "Consulta la salud general del sistema en este momento",
        "Assess the integral state of the whole machine",
        "Inspect the system's overall health at this moment",
        "Reporta el integral state de whole machine",
        "Check la overall health del system ahora",
    ),
    "task": scenario6(
        ("task.list",),
        "Enumera las tareas abiertas que todavía no resolví",
        "Consulta todos los pendientes de mi lista de obligaciones",
        "Enumerate the open tasks I have not resolved yet",
        "Inspect every pending item on my obligations list",
        "Show las open tasks todavía unresolved",
        "Dime every pending item de obligations list",
    ),
    "vision": scenario6(
        ("capture.screenshot", "vision.describe"),
        "Captura el escritorio y describe los objetos de la imagen",
        "Toma una foto de la pantalla e interpreta la escena visible",
        "Capture the desktop and describe the objects in the image",
        "Take a screen picture and interpret the visible scene",
        "Capture el desktop y describe objects in image",
        "Toma screen picture e interpret la visible scene",
    ),
    "web": scenario6(
        ("web.search",),
        "Investiga en internet cómo duermen los pulpos",
        "Explora la web buscando reseñas de cafeteras italianas",
        "Research online how octopuses sleep",
        "Explore the web for reviews of moka pots",
        "Research en internet cómo octopuses sleep",
        "Busca on the web reviews de moka pots",
    ),
    "wifi": scenario6(
        ("wifi.status",),
        "Evalúa el estado actual de la conexión inalámbrica",
        "Consulta la condición de la señal Wi-Fi de este equipo",
        "Assess the current state of the wireless connection",
        "Inspect this computer's Wi-Fi signal condition",
        "Reporta el current state de wireless connection",
        "Check la Wi-Fi signal condition de este equipo",
    ),
    "window": scenario6(
        ("window.active",),
        "Identifica la ventana que posee el foco en primer plano",
        "Consulta qué aplicación está activa sobre las demás",
        "Identify the window that owns foreground focus",
        "Inspect which application is active above the others",
        "Dime la window que owns foreground focus",
        "Check cuál application está active above others",
    ),
}


CLARIFICATIONS = Scenario(
    ("message.send",),
    (
        Utterance("es", "Avísale a Martina que cambiaron la hora"),
        Utterance("es", "Dile a Facundo el texto ya voy en camino"),
        Utterance("es", "Hazle llegar a Nuria que terminé el borrador"),
        Utterance("es", "Cuéntale a Benjamín que el vuelo se retrasó"),
        Utterance("en", "Let Riley know the appointment moved"),
        Utterance("en", "Get the update I am on my way to Taylor"),
        Utterance("en", "Tell Cameron that the draft is finished"),
        Utterance("en", "Send Morgan the note the flight was delayed"),
        Utterance("spanglish", "Dile a Drew the appointment cambió"),
        Utterance("spanglish", "Let Robin know que voy en camino"),
    ),
)


def composition(language: str, operations: tuple[str, ...], text: str) -> builder.Composition:
    return builder.Composition(operations, Utterance(language, text))


COMPOSITIONS = (
    composition("es", ("system.status", "network.status", "audio.status"), "Muestra estado integral del equipo, acceso general a la red y configuración de sonido"),
    composition("en", ("task.list", "calendar.event.list", "reminder.list"), "Show open tasks, today's calendar, and scheduled reminders"),
    composition("spanglish", ("note.list", "clipboard.read.text", "browser.tabs.list"), "Lista private notes, read clipboard text y show open tabs"),
    composition("es", ("bluetooth.device.list", "peripheral.list", "wifi.status"), "Enumera dispositivos Bluetooth, periféricos externos y señal Wi-Fi"),
    composition("en", ("email.latest.read", "notification.list.due", "calendar.event.list"), "Read the newest mail, overdue notices, and tomorrow's appointments"),
    composition("spanglish", ("backup.list", "routine.list", "reminder.list"), "Show restore copies, saved routines y future reminders"),
    composition("es", ("window.active", "input.keyboard.status", "clipboard.read.text"), "Identifica ventana activa, distribución del teclado y texto del portapapeles"),
    composition("en", ("audio.status", "media.status", "task.list"), "Report sound configuration, current playback, and unfinished tasks"),
    composition("spanglish", ("network.status", "wifi.status", "bluetooth.device.list"), "Check overall network access, Wi-Fi signal y visible Bluetooth devices"),
    composition("es", ("note.list", "reminder.list", "routine.list"), "Consulta notas guardadas, recordatorios futuros y rutinas automáticas"),
    composition("en", ("browser.tabs.list", "window.active", "input.keyboard.status"), "List browser pages, identify the foreground window, and state the key layout"),
    composition("spanglish", ("calendar.event.list", "task.list", "notification.list.due"), "Show today's appointments, open tasks y overdue notifications"),
    composition("es", ("peripheral.list", "bluetooth.device.list", "audio.status"), "Muestra accesorios conectados, equipos Bluetooth y ruta de audio"),
    composition("en", ("game.catalog.list", "backup.list", "routine.list"), "Enumerate local games, recovery copies, and saved routines"),
    composition("spanglish", ("system.status", "media.status", "clipboard.read.text"), "Report whole-machine health, current playback y clipboard words"),
    composition("es", ("email.latest.read", "calendar.event.list", "task.list"), "Lee último correo, consulta calendario de mañana y enumera tareas abiertas"),
    composition("en", ("wifi.status", "peripheral.list", "window.active"), "Inspect the wireless signal, attached accessories, and foreground window"),
    composition("spanglish", ("backup.list", "note.list", "reminder.list"), "List backups, private notes y scheduled reminders"),
    composition("es", ("audio.status", "network.status", "browser.tabs.list"), "Consulta sonido, conectividad general y pestañas del navegador"),
    composition("en", ("input.keyboard.status", "clipboard.read.text", "media.status"), "State the keyboard map, read clipboard text, and report playback"),
    composition("es", ("system.status", "network.status", "audio.status", "media.status"), "Muestra salud del sistema, red general, sonido y reproducción"),
    composition("en", ("task.list", "calendar.event.list", "reminder.list", "notification.list.due"), "List tasks, today's appointments, future reminders, and overdue notices"),
    composition("spanglish", ("note.list", "clipboard.read.text", "browser.tabs.list", "window.active"), "Show notes, clipboard words, browser tabs y front window"),
    composition("es", ("bluetooth.device.list", "peripheral.list", "wifi.status", "network.status"), "Enumera Bluetooth, periféricos, señal Wi-Fi y acceso general a la red"),
    composition("en", ("email.latest.read", "calendar.event.list", "task.list", "backup.list"), "Read newest email, tomorrow's calendar, open tasks, and restore copies"),
    composition("spanglish", ("audio.status", "media.status", "input.keyboard.status", "clipboard.read.text"), "Report sound, playback, keyboard layout y clipboard text"),
    composition("es", ("routine.list", "reminder.list", "note.list", "task.list"), "Consulta rutinas, recordatorios, notas y pendientes en ese orden"),
    composition("en", ("window.active", "browser.tabs.list", "peripheral.list", "bluetooth.device.list"), "Name the front window, list tabs, attached accessories, and Bluetooth devices"),
    composition("spanglish", ("system.status", "network.status", "wifi.status", "audio.status"), "Show whole machine, overall network, Wi-Fi y sound status"),
    composition("es", ("game.catalog.list", "backup.list", "routine.list", "reminder.list"), "Enumera juegos locales, respaldos, rutinas y recordatorios"),
    composition("en", ("calendar.event.list", "email.latest.read", "notification.list.due", "task.list"), "Inspect today's calendar, latest mail, overdue alerts, and tasks"),
    composition("spanglish", ("note.list", "browser.tabs.list", "media.status", "audio.status"), "List private notes, open tabs, current playback y sound route"),
    composition("es", ("peripheral.list", "window.active", "input.keyboard.status", "clipboard.read.text"), "Muestra periféricos, ventana activa, mapa del teclado y portapapeles"),
    composition("en", ("backup.list", "routine.list", "task.list", "reminder.list"), "Show recovery copies, routines, unfinished tasks, and reminders"),
    composition("spanglish", ("bluetooth.device.list", "wifi.status", "network.status", "system.status"), "List Bluetooth devices, Wi-Fi signal, network access y machine health"),
    composition("es", ("browser.tabs.list", "window.active", "media.status", "audio.status"), "Consulta pestañas, ventana frontal, reproducción y salida sonora"),
    composition("en", ("email.latest.read", "calendar.event.list", "notification.list.due", "reminder.list"), "Read latest email, calendar events, overdue notices, and future reminders"),
    composition("spanglish", ("task.list", "note.list", "clipboard.read.text", "input.keyboard.status"), "Show open tasks, saved notes, clipboard text y keyboard map"),
    composition("es", ("system.status", "peripheral.list", "bluetooth.device.list", "wifi.status"), "Muestra sistema integral, accesorios, Bluetooth y conexión inalámbrica"),
    composition("en", ("game.catalog.list", "backup.list", "browser.tabs.list", "window.active"), "Enumerate games, recovery copies, tabs, and the active window"),
    composition("es", ("system.status", "network.status", "audio.status", "media.status", "task.list"), "Reporta sistema, red, audio, reproducción y tareas abiertas"),
    composition("en", ("calendar.event.list", "email.latest.read", "notification.list.due", "reminder.list", "routine.list"), "Show calendar, newest mail, overdue notices, reminders, and routines"),
    composition("spanglish", ("note.list", "clipboard.read.text", "browser.tabs.list", "window.active", "input.keyboard.status"), "List notes, clipboard, tabs, front window y input layout"),
    composition("es", ("bluetooth.device.list", "peripheral.list", "wifi.status", "network.status", "system.status"), "Enumera Bluetooth, periféricos, Wi-Fi, red y estado del equipo"),
    composition("en", ("backup.list", "game.catalog.list", "routine.list", "task.list", "reminder.list"), "List backups, games, routines, tasks, and reminders"),
    composition("spanglish", ("audio.status", "media.status", "window.active", "browser.tabs.list", "clipboard.read.text"), "Report sound, playback, active window, tabs y clipboard"),
    composition("es", ("email.latest.read", "calendar.event.list", "task.list", "notification.list.due", "reminder.list"), "Lee correo, calendario, tareas, alertas vencidas y recordatorios"),
    composition("en", ("system.status", "audio.status", "network.status", "wifi.status", "bluetooth.device.list"), "Inspect machine health, sound, network, Wi-Fi, and Bluetooth devices"),
    composition("spanglish", ("peripheral.list", "input.keyboard.status", "clipboard.read.text", "note.list", "task.list"), "Show peripherals, keyboard map, clipboard, notes y tasks"),
    composition("es", ("routine.list", "backup.list", "game.catalog.list", "browser.tabs.list", "window.active"), "Consulta rutinas, copias, juegos, pestañas y ventana activa"),
    composition("en", ("system.status", "network.status", "audio.status", "media.status", "window.active", "browser.tabs.list"), "Report machine, network, sound, playback, active window, and tabs"),
    composition("spanglish", ("task.list", "calendar.event.list", "email.latest.read", "notification.list.due", "reminder.list", "routine.list"), "Show tasks, calendar, latest mail, overdue alerts, reminders y routines"),
    composition("es", ("note.list", "clipboard.read.text", "input.keyboard.status", "peripheral.list", "bluetooth.device.list", "wifi.status"), "Enumera notas, portapapeles, teclado, periféricos, Bluetooth y Wi-Fi"),
    composition("en", ("backup.list", "game.catalog.list", "browser.tabs.list", "window.active", "media.status", "audio.status"), "List backups, games, tabs, front window, playback, and sound"),
    composition("spanglish", ("system.status", "network.status", "wifi.status", "bluetooth.device.list", "peripheral.list", "window.active"), "Show system, network, Wi-Fi, Bluetooth, peripherals y active window"),
    composition("es", ("calendar.event.list", "task.list", "note.list", "reminder.list", "routine.list", "backup.list", "game.catalog.list"), "Muestra calendario, tareas, notas, recordatorios, rutinas, respaldos y juegos"),
    composition("en", ("window.active", "browser.tabs.list", "input.keyboard.status", "clipboard.read.text", "media.status", "audio.status", "network.status"), "Name window, tabs, key map, clipboard, playback, sound, and network"),
    composition("spanglish", ("email.latest.read", "calendar.event.list", "task.list", "notification.list.due", "reminder.list", "routine.list", "backup.list"), "Read mail, calendar, tasks, overdue notices, reminders, routines y backups"),
    composition("es", ("system.status", "network.status", "audio.status", "media.status", "window.active", "browser.tabs.list", "clipboard.read.text", "input.keyboard.status"), "Consulta sistema, red, audio, reproducción, ventana, pestañas, portapapeles y teclado"),
    composition("en", ("capture.screenshot", "vision.describe", "ocr.read"), "Capture the screen, describe its scene, and transcribe the visible text"),
)


CONVERSATIONS = (
    Utterance("es", "Explícame cómo funciona una red Wi-Fi sin consultar este equipo"),
    Utterance("es", "Reescribe con tono sereno la frase abre la ventana ahora"),
    Utterance("es", "Calcula mentalmente treinta y uno por catorce"),
    Utterance("es", "Dame una receta corta de pan de ajo"),
    Utterance("es", "Compara en general Bluetooth y Wi-Fi sin revisar dispositivos"),
    Utterance("es", "Traduce al inglés la oración cierra Steam mañana"),
    Utterance("es", "Inventa un poema cuya última palabra sea pantalla"),
    Utterance("es", "Qué es un portapapeles de computador"),
    Utterance("es", "Cuéntame un chiste breve sobre teclados"),
    Utterance("es", "Resume el concepto de copia de seguridad en dos frases"),
    Utterance("es", "Sugiere cuatro nombres para una cafetería llamada Ventana"),
    Utterance("es", "Ayúdame a practicar una entrevista sobre redes"),
    Utterance("es", "No leas mi portapapeles; solo define para qué sirve"),
    Utterance("es", "Si tuviera otra computadora, abriría allí el navegador"),
    Utterance("es", "Ayer Steam estaba cerrado cuando llegué"),
    Utterance("en", "Explain how Bluetooth discovery works without scanning devices"),
    Utterance("en", "Rewrite the phrase close the window now in a calm tone"),
    Utterance("en", "Calculate thirty-seven times sixteen mentally"),
    Utterance("en", "Give me a short garlic bread recipe"),
    Utterance("en", "Compare Bluetooth and Wi-Fi in theory without checking this PC"),
    Utterance("en", "Translate the sentence open Discord tomorrow into Spanish"),
    Utterance("en", "Make up a poem whose final word is screen"),
    Utterance("en", "What is a computer clipboard"),
    Utterance("en", "Tell me a short joke about keyboards"),
    Utterance("en", "Summarize the idea of a backup in two sentences"),
    Utterance("en", "Suggest four names for a cafe called Window"),
    Utterance("en", "Help me practice an interview about networks"),
    Utterance("en", "Do not read my clipboard; only explain its purpose"),
    Utterance("en", "If I had another computer, I would open the browser there"),
    Utterance("en", "Steam was closed yesterday when I arrived"),
    Utterance("spanglish", "Explain cómo works Wi-Fi sin check this machine"),
    Utterance("spanglish", "Rewrite con tono calm la frase close window now"),
    Utterance("spanglish", "Calculate mentalmente forty-one times twelve"),
    Utterance("spanglish", "Dame a short recipe de garlic bread"),
    Utterance("spanglish", "Compare Bluetooth y Wi-Fi in general sin revisar PC"),
    Utterance("spanglish", "Translate abre Discord mañana into English"),
    Utterance("spanglish", "Make up un poem cuya final word sea screen"),
    Utterance("spanglish", "What es un computer clipboard"),
    Utterance("spanglish", "Tell me un short joke sobre keyboards"),
    Utterance("spanglish", "Summarize el concepto de backup in two sentences"),
    Utterance("spanglish", "Suggest cuatro names para café Ventana"),
    Utterance("spanglish", "Help me practicar an interview sobre networks"),
    Utterance("spanglish", "No read my clipboard; solo explain its purpose"),
    Utterance("spanglish", "If tuviera another computer, abriría browser allí"),
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
    builder.CAMPAIGN = "r6"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-holdout.v6"
    builder.PREREGISTRATION_SCHEMA = "baxy.generalization-product-preregistration.v6"
    builder.EXPECTED_POPULATION = 600
    builder.MINIMUM_CASES = 600
    builder.METHOD_DESCRIPTION = (
        "31_families_x_6_fresh_bases_x_2_surfaces_plus_"
        "10_clarifications_x_2_surfaces_plus_60_ordered_compositions_"
        "of_3_to_8_effects_x_2_surfaces_plus_"
        "44_lexically_colliding_conversations_x_2_surfaces"
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
        "es": "Oye Baxy — por favor, ",
        "en": "Hey Baxy, please: ",
        "spanglish": "A ver Baxy, please: ",
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
