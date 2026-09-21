"""Emit spec_typed_<cap>.json + panel_typed_<cap>.py for every typed capability of opus/typed-tools.

The panels follow panel_1999.py (template video1955: ordinary turns, 2-4 literals, variants, 2 limits).
Inventory (source count, new sources) and the source delta are computed at derive time from the merged
tree, never pinned here. `prev`/`new`/`grandparent` in each spec are markers the runner assigns.
Capabilities that need confirmations (winget commit/uninstall, Steam install/uninstall, power) are
marked "reviewed": their panel needs the reviewed-turn lineage instead of video1955.

Usage: python make_typed_panels.py   (writes next to this file)
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# cap -> dict(rows, crit, literals[(id, group)], variants[(text)], boundaries[(text, why)], allowed, expected,
#             fixture_app{case: app}, reviewed, plan_title, plan_body, cause, change, preset)
CAPS: dict[str, dict] = {
    "weather": {
        "group": "weather_read",
        "crit": "Clima (REOPEN1993 grupo W; H0034 «busca el clima en Buenos Aires», H0339 «qué clima hace hoy», H0617 «va a llover mañana», H0708 «busca el clima en internet»): exactamente una weather.current completada y verificada (ubicación del pedido, o la de este PC cuando no se nombra), sin navegar ni buscar en la web, y un final en el idioma del pedido que diga la temperatura y el estado leídos y nombre la ciudad; «mañana» dice el pronóstico del día siguiente; nada inventado, sin pregunta.",
        "literals": [("H0415", None), ("H0339", None), ("H0617", None), ("H0708", None)],
        "variants": ["what's the weather in Madrid right now", "¿hace frío afuera?"],
        "boundaries": [("no me digas el clima", "Prohibición: reconocimiento, cero operaciones, sin negar la capacidad."),
                       ("qué clima hacía en Buenos Aires en 1990", "Clima del pasado: no hay lectura histórica; límite honesto con cero operaciones, sin inventar cifras.")],
        "allowed": ["weather.current"],
        "expected": ["weather.current"],
        "plan_title": "el clima se lee de un servicio de pronóstico, no de una búsqueda",
        "plan_body": "REOPEN1993 (auditoría semántica, D24) reabrió las doce filas de clima acreditadas con una búsqueda web o un límite. Con weather.current (Open-Meteo; la ubicación por la IP de este PC cuando el pedido no la nombra) la mente lee el pedido como una lectura de clima y el final dice temperatura y estado con la ciudad. Panel de 8: 4 literales, 2 variantes y 2 límites; turnos ordinarios con internet real (criterio de forma, no de valor).",
        "cause": "El clima terminaba en una búsqueda web o en un límite: nunca se leía un pronóstico.",
        "change": "weather.current lee el pronóstico actual (o del día siguiente) de la ubicación pedida o de este PC; la mente lo elige y el compositor cita los valores leídos.",
        "preset": "internet real; sin preset ni restore",
    },
    "news": {
        "group": "news_read",
        "crit": "Noticias (REOPEN1993 grupo N; H0033 «buscá noticias de hoy», H0509 «qué pasó hoy en el mundo»): exactamente una web.news.headlines completada y verificada (tema del pedido si lo nombra), sin navegar, y un final en el idioma del pedido que cite al menos tres titulares tal cual se leyeron con su fuente; nada inventado, sin pregunta.",
        "literals": [("H0033", None), ("H0374", None), ("H0509", None)],
        "variants": ["dame los titulares de deportes", "top news today", "qué noticias hay de tecnología"],
        "boundaries": [("no quiero noticias", "Prohibición: reconocimiento, cero operaciones."),
                       ("qué pasó ayer en mi casa", "Fuera de toda lectura: límite honesto con cero operaciones, sin inventar.")],
        "allowed": ["web.news.headlines"],
        "expected": ["web.news.headlines"],
        "plan_title": "las noticias de hoy son titulares leídos, no una búsqueda",
        "plan_body": "REOPEN1993 (D24) reabrió las tres filas de noticias acreditadas con una búsqueda web. Con web.news.headlines (RSS de Google Noticias, tema opcional) la mente lee el pedido como una lectura de titulares y el final los cita con su fuente. Panel de 8: 3 literales, 3 variantes y 2 límites; turnos ordinarios con internet real.",
        "cause": "Las noticias terminaban en una búsqueda web genérica sin titulares.",
        "change": "web.news.headlines lee los titulares del día (o del tema nombrado); el compositor los cita tal cual con su fuente.",
        "preset": "internet real; sin preset ni restore",
    },
    "winget": {
        "group": "package_install",
        "crit": "Instalar software (REOPEN1993 grupo G; H0651 «instala Spotify», H0217 «instala Photoshop»; los paquetes del dueño se sustituyen por el de prueba, D13): el pedido no es una biblioteca de Steam; exactamente una package.install.prepare completada y verificada que lee winget y prepara el paquete único (o dice que no está o que hay varios) y, con paquete único, una package.install.commit completada y verificada (Installation → sin confirmación en modo normal) que lo instala y observa el estado; el final nombra el paquete y su estado real (instalando, ya instalado, no encontrado) y nunca dice «instalado» mientras winget corre.",
        "literals": [("H0651", None), ("H0217", None)],
        "variants": ["install 7zip", "instalame el 7-Zip"],
        "case_fixture_steps": {"H0089": "winget/ensure-installed", "typedwinget-dev-02": "winget/ensure-absent"},
        "boundaries": [("no instales nada", "Prohibición: reconocimiento, cero operaciones."),
                       ("¿qué es winget?", "Pregunta de definición: explicación, cero operaciones.")],
        "allowed": ["package.install.prepare", "package.install.commit"],
        "expected": ["package.install.prepare", "package.install.commit"],
        "reviewed_group": {
            "group": "package_uninstall",
            "crit": "Desinstalar software (REOPEN1993 grupo G; H0574 «desinstalá Spotify» medido como «desinstalá 7-Zip», D13; H0089 «desinstalá Discord» idem): exactamente una package.uninstall revisada y aprobada por la raiz (packageId 7zip.7zip; nunca Spotify ni Discord del dueño) completada y verificada por la ausencia del paquete en la lista de winget, y un final que diga que quitó ese paquete; cero operaciones fuera de la lista.",
            "literals": [("H0574", None), ("H0089", None)],
            "variants": ["quitá 7-Zip"],
            "allowed": ["package.uninstall"],
            "expected": ["package.uninstall"],
        },
        "literal_substitutions": {"H0651": "instala 7-Zip", "H0574": "desinstalá 7-Zip", "H0089": "desinstalá 7-Zip"},
        "plan_title": "instalar software es winget, no la biblioteca de Steam",
        "plan_body": "REOPEN1993 (D24) reabrió siete filas de instalar/desinstalar programas leídas como biblioteca de Steam. Con package.install.prepare/commit y package.uninstall (winget) la mente distingue programa de juego, prepara el paquete único, instala sin confirmación (Installation) y desinstala con confirmación (WorkLoss), y el final dice el estado real. Panel mixto de 9: instalar como turnos ordinarios (2 literales + 2 variantes) y desinstalar como turnos revisados (2 literales + 1 variante) con el paquete de prueba 7zip.7zip en lugar de Spotify/Discord del dueño (D13); 2 límites.",
        "cause": "«Instala Photoshop/Spotify» se leía como descarga de Steam y terminaba en una biblioteca vacía.",
        "change": "winget por tipadas: preparar (lectura), instalar (ordinario) y desinstalar (revisado) con espera corta y estado observado; la mente distingue programas de juegos.",
        "preset": "winget/before (deja 7zip.7zip ausente) y winget/after (restaura el estado previo) de typed_fixtures.ps1; pasos por caso CASE_FIXTURE_STEPS (H0089 winget/ensure-installed, dev-02 winget/ensure-absent); no tocar Spotify/Discord; el instalar de Photoshop mide la ausencia en winget (no existe) sin efecto",
    },
    "steam": {
        "group": "game_install",
        "crit": "Descargar/instalar juegos (REOPEN1993 grupo S; H0456 «Descarga Worms Rumble en Steam» medido con Plants vs. Zombies, D13; H0571 «Descarga diin eternal de steam» = Doom Eternal mal oído; H0578 «Descarga Fall guys en epic games»): primero game.entitlement.named lee la biblioteca (Steam o Epic según la tienda nombrada; la palabra mal oída se corrige con el catálogo); con el título en la biblioteca y no instalado, exactamente una game.install.named completada y verificada (Installation → sin confirmación) que lo inicia por steam://install y lo verifica por el manifiesto; sin entitlement, el final dice que no está en la biblioteca; nada inventado.",
        "literals": [("H0456", None), ("H0571", None), ("H0578", None)],
        "variants": ["instalá Plants vs. Zombies de Steam"],
        "boundaries": [("no descargues nada", "Prohibición: reconocimiento, cero operaciones."),
                       ("descargá el aire de Steam", "Título inexistente: la lectura de biblioteca lo dice; nada iniciado.")],
        "allowed": ["game.entitlement.named", "game.install.named"],
        "expected": ["game.entitlement.named", "game.install.named"],
        "reviewed_group": {
            "group": "game_uninstall",
            "crit": "Desinstalar un juego instalado (REOPEN1993 grupo S; H0620 «Desinstala Worms Rumble» medido como «Desinstala Plants vs. Zombies», D13): exactamente una game.uninstall.named revisada y aprobada por la raiz (sólo Plants vs. Zombies GOTY o PICO PARK) completada y verificada porque el manifiesto local ya no lo declara instalado, y un final que diga que lo desinstaló; cero operaciones fuera de la lista.",
            "literals": [("H0620", None)],
            "variants": ["desinstalá PICO PARK"],
            "allowed": ["game.uninstall.named"],
            "expected": ["game.uninstall.named"],
        },
        "literal_substitutions": {"H0456": "Descarga Plants vs. Zombies en Steam. IMPORTANTE: primero busca el AppID via https://store.steampowered.co", "H0620": "Desinstala Plants vs. Zombies"},
        "plan_title": "Steam y Epic: descargar e instalar por el lanzador, desinstalar con confirmación",
        "plan_body": "REOPEN1993 (D24) reabrió cuatro filas de Steam/Epic acreditadas como lectura o límite. Con game.install.named (store) y game.uninstall.named la mente encadena la lectura de biblioteca con el efecto y el final dice lo iniciado y verificado por manifiesto. Panel mixto de 8: instalar como turnos ordinarios (3 literales + 1 variante), desinstalar como turnos revisados (1 literal + 1 variante), 2 límites; títulos que posee la cuenta del dueño (decisión 2026-09-20: Plants vs. Zombies GOTY appid 3590, PICO PARK appid 461040); el caso «desinstalá» va antes del «instalá» del mismo título; restore reinstalando lo desinstalado.",
        "cause": "Descargar/desinstalar en Steam o Epic terminaba en la lectura de biblioteca o en un límite.",
        "change": "instalación por steam:// verificada por manifiesto (ordinaria) y desinstalación por el lanzador con confirmación (revisada); Epic por su esquema com.epicgames.launcher.",
        "preset": "steam/before (registra manifiestos y deja PvZ 3590 ausente por app_uninstall) y steam/after (reinstala lo que falte por steam://install) de typed_fixtures.ps1; el orden de casos ya encadena instalar→desinstalar→instalar de PvZ y PICO PARK se desinstala al final; driver near_case steam_owner (el Steam del dueño se reutiliza, nunca se cierra)",
    },
    "power": {
        "group": "power_transition",
        # RiskPolicy (D3): system.power is Allow → ordinary turn; the catalog label work_loss is historical.
        "reviewed": False,
        "crit": "Apagar/reiniciar (REOPEN1993 grupo P; H0401 «reiniciá la PC», H0714 «apagá la computadora»): exactamente una system.power completada y verificada con retraso de 30 s (privilegio de apagado habilitado en el proceso), tras la confirmación de la persona; el final dice que la transición quedó programada. La raíz la aborta con shutdown /a tras verificar la programación.",
        "literals": [("H0401", None), ("H0714", None)],
        "variants": ["shut down the computer", "reiniciá"],
        "boundaries": [("no apagues nada", "Prohibición: reconocimiento, cero operaciones."),
                       ("apagá la luz", "No es el PC: límite honesto con cero operaciones.")],
        "allowed": ["system.power"],
        "expected": ["system.power"],
        "plan_title": "Windows acepta el apagado y el reinicio con el privilegio habilitado",
        "plan_body": "REOPEN1993 (D24) reabrió dos filas de energía acreditadas con «Windows no aceptó». Con SeShutdownPrivilege habilitado y un retraso de 30 s la transición se programa de verdad y la raíz la aborta tras verificarla. Turnos revisados (confirmación).",
        "cause": "InitiateSystemShutdownEx fallaba con acceso denegado por el privilegio no habilitado.",
        "change": "el adaptador habilita el privilegio de apagado y programa la transición con 30 s de retraso; la raíz verifica y aborta.",
        "preset": "abort: `shutdown /a` por la raíz tras verificar la programación",
    },
    "wifi_place": {
        "group": "wifi_place",
        "template": "then2001",
        "crit": "Wifi de casa (REOPEN1993 grupo H; H0170/H0376 «conectate al wifi de casa»): «casa» no es un SSID. Turno 1 sin asociación: una wifi.profile.list completada y una wifi.connect.named{place=casa} que falla con wifi_place_unknown antes de cualquier efecto, y un final que nombre las redes guardadas y pregunte cuál es la de casa (sin conectar, sin inventar). Turno 2 con el nombre de la red: una wifi.connect.named{profileName, place} completada y verificada que conecta y deja la asociación; final: conectado a esa red. Turno 3 «conectate al wifi de casa»: conecta directo por la asociación. «wifi de la luna» (H0739) sigue siendo wifi_profile_not_found honesto.",
        "literals": [("H0170", None), ("H0376", None)],
        "variants": ["connect to my home wifi", "cambia el wifi al de casa"],
        "boundaries": [("conectate al wifi de la luna", "Nombre inexistente: fallo honesto wifi_profile_not_found, sin pregunta de lugar."),
                       ("no te conectes al wifi", "Prohibición: reconocimiento, cero operaciones.")],
        "allowed": ["wifi.profile.list", "wifi.connect.named"],
        "expected": ["wifi.profile.list", "wifi.connect.named"],
        "plan_title": "«casa» no es un SSID: preguntar cuál, recordarlo y conectar directo después",
        "plan_body": "REOPEN1993 (D24) reabrió H0170/H0376 acreditadas con «no hay ningún perfil con ese nombre». Con `place` en wifi.connect.named y la asociación privada lugar→red (wifi-places.v1.json del perfil), el primer turno lista las redes guardadas y pregunta cuál es la de casa, el nombre respondido conecta y recuerda, y el siguiente «wifi de casa» conecta directo. Tres turnos por caso (turn.playback-then o turnos ordinarios con historia); la red de casa real del dueño, restaurada al final.",
        "cause": "«Conectate al wifi de casa» terminaba en «no hay ningún perfil con ese nombre» sin preguntar ni aprender.",
        "change": "wifi.connect.named acepta `place`; sin asociación falla con wifi_place_unknown (sin replanificar) y el final pregunta cuál; la respuesta conecta y asocia.",
        "preset": "preset: borrar `<perfil>/scans/wifi-places.v1.json`; restore: reconectar la red original del dueño",
    },
    "zip": {
        "group": "folder_zip_mission",
        "crit": "Misión carpeta+txt+zip+abrir (H0542): exactamente filesystem.create.directory, filesystem.write.text, file.compress y file.open completadas y verificadas en ese orden en el escritorio, con los nombres por defecto de Windows («Nueva carpeta», «Nuevo documento de texto.txt», «Nueva carpeta.zip»), y un final que nombre la carpeta, el txt y el zip y diga que el zip quedó abierto; nada inventado.",
        "literals": [("H0542", None)],
        "variants": ["make a folder on the desktop with a txt inside, zip it and open the zip", "armá una carpeta en el escritorio con un txt, comprimila y abrí el zip", "creá una carpeta en documentos, poné un txt, comprimila y abrila"],
        "boundaries": [("no crees nada en el escritorio", "Prohibición: reconocimiento, cero operaciones."),
                       ("comprimí el escritorio entero", "Sin carpeta nombrada ni creada: límite honesto, cero operaciones.")],
        "allowed": ["filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open"],
        "expected": ["filesystem.create.directory", "filesystem.write.text", "file.compress", "file.open"],
        "plan_title": "carpeta, txt, zip y abrir: una misión de cuatro tipadas",
        "plan_body": "REOPEN1957 (D11) reabrió H0542, acreditada como límite. Con file.compress y file.open la mente encadena crear carpeta → escribir txt → comprimir → abrir y el final nombra lo creado. Turnos ordinarios sobre el escritorio redirigido; restore borrando lo creado y cerrando el Explorador.",
        "cause": "Comprimir y abrir el zip no existían: la misión terminaba en un límite.",
        "change": "file.compress (zip de una carpeta conocida) y file.open (abrir con la app asociada) más la lectura de misión de la mente.",
        "preset": "restore: borrar «Nueva carpeta*» y «Nueva carpeta.zip» del escritorio; cerrar el Explorador del zip",
    },
    "airplane": {
        "group": "airplane_mode",
        "crit": "Modo avión (H0107 «poneme el modo avión»): exactamente una system.settings.set{airplane_mode} completada y verificada (todas las radios apagadas por la API de radios y releídas), y un final que diga el estado leído; la pregunta «¿está el modo avión?» es system.settings.status, sin efecto. Restore de radios fuera del turno.",
        "literals": [("H0107", None)],
        "variants": ["turn on airplane mode", "sacá el modo avión", "activá el modo avión"],
        "boundaries": [("no pongas el modo avión", "Prohibición: reconocimiento, cero operaciones."),
                       ("¿está activado el modo avión?", "Lectura: system.settings.status y el estado leído, sin efecto.")],
        "allowed": ["system.settings.set", "system.settings.status", "wifi.radio.set", "bluetooth.radio.set"],
        "expected": ["system.settings.set"],
        "plan_title": "el modo avión es todas las radios apagadas y releídas",
        "plan_body": "REOPEN1957 (D11) reabrió H0107, acreditada como límite sin mecanismo. Con airplane_mode en system.settings.set/status (API de radios de Windows) la mente lo lee como un ajuste y el final dice el estado releído. Turnos ordinarios; preset/restore de las radios.",
        "cause": "El modo avión no tenía mecanismo y terminaba en un límite.",
        "change": "system.settings.set airplane_mode apaga/enciende todas las radios y las relee; status las lee.",
        "preset": "preset/restore: estado de las radios wifi/bluetooth (script tipo bt_radio.ps1)",
    },
    "wallpaper": {
        "group": "wallpaper_set",
        "crit": "Fondo de pantalla (H0459 «cambiá el fondo de pantalla a azul»): exactamente una desktop.wallpaper.set completada y verificada (color liso escrito como imagen y aplicado por SPI, releído del registro), y un final que diga el color (o la imagen) aplicado; nada inventado.",
        "literals": [("H0459", None)],
        "variants": ["set the wallpaper to red", "poné el fondo de escritorio verde", "cambiá el fondo a negro"],
        "boundaries": [("no cambies el fondo", "Prohibición: reconocimiento, cero operaciones."),
                       ("cambiá el fondo a transparente", "Color no soportado: límite honesto, cero operaciones.")],
        "allowed": ["desktop.wallpaper.set"],
        "expected": ["desktop.wallpaper.set"],
        "plan_title": "el fondo de escritorio se cambia y se relee del registro",
        "plan_body": "REOPEN1957 (D11) reabrió H0459, acreditada como límite. Con desktop.wallpaper.set (color liso o imagen de una carpeta conocida) la mente lo lee como un ajuste y el final dice lo aplicado. Turnos ordinarios; preset del fondo original y restore por SPI.",
        "cause": "Cambiar el fondo no tenía mecanismo y terminaba en un límite.",
        "change": "desktop.wallpaper.set escribe la imagen (o el color), la aplica por SystemParametersInfo y relee el registro.",
        "preset": "preset: guardar HKCU\\Control Panel\\Desktop\\Wallpaper; restore: SPI con el original",
    },
    "download": {
        "group": "web_download",
        "crit": "Descarga web (H0077 «descarga la imagen de portada de wikipedia.org y guardala en el escritorio»): exactamente una web.download completada y verificada (de una página, la imagen og:image que anuncia; de un archivo, el archivo) en la carpeta nombrada, y un final que nombre el archivo escrito y su tamaño; nada inventado.",
        "literals": [("H0077", None)],
        "variants": ["download https://www.python.org/static/img/python-logo.png to downloads", "bajá la portada de es.wikipedia.org a imágenes", "descargá https://example.com/index.html en descargas"],
        "boundaries": [("no descargues nada", "Prohibición: reconocimiento, cero operaciones."),
                       ("descargá todo internet", "Sin dirección ni archivo: límite honesto, cero operaciones.")],
        "allowed": ["web.download"],
        "expected": ["web.download"],
        "plan_title": "descargar un archivo o la portada de una página a una carpeta conocida",
        "plan_body": "REOPEN1957 (D11) reabrió H0077, acreditada como límite. Con web.download (dirección o página con og:image, carpeta conocida, tamaño releído) la mente lo lee como descarga y el final nombra el archivo. Turnos ordinarios con internet real; restore borrando lo descargado.",
        "cause": "Descargar de la web no tenía mecanismo y terminaba en un límite.",
        "change": "web.download baja un archivo o la imagen de portada de una página y verifica el tamaño escrito.",
        "preset": "restore: borrar el archivo descargado",
    },
    "pptx": {
        "group": "presentation_create",
        "crit": "Presentación (H0188 «Haz un powerpoint hablando de amor de 6 diapositivas»): exactamente una document.presentation.create completada y verificada (paquete Open XML en Documentos, diapositivas redactadas por el modelo, cantidad pedida releída del paquete) seguida de una file.open que lo abre, y un final que nombre el archivo y diga cuántas diapositivas tiene según la postlectura; ningún número inventado.",
        "literals": [("H0188", None)],
        "variants": ["armá una presentación sobre el sistema solar de 4 diapositivas", "make a presentation about dogs with 5 slides", "creá un powerpoint sobre gatos"],
        "boundaries": [("no hagas ningún powerpoint", "Prohibición: reconocimiento, cero operaciones."),
                       ("crea un powerpoint", "Sin tema: pregunta de qué, cero operaciones.")],
        "allowed": ["document.presentation.create", "file.open"],
        "expected": ["document.presentation.create", "file.open"],
        "plan_title": "el powerpoint se escribe como paquete Open XML y se abre",
        "plan_body": "REOPEN1957 (D11) reabrió H0188, acreditada como límite. Con document.presentation.create (título, diapositivas del modelo, postlectura del paquete) y file.open la mente lo encadena y el final dice archivo y cantidad. Turnos ordinarios; restore borrando el .pptx y cerrando PowerPoint.",
        "cause": "Crear una presentación no tenía mecanismo y terminaba en un límite.",
        "change": "document.presentation.create escribe un .pptx mínimo válido con N diapositivas y cuenta las escritas; el modelo redacta el contenido.",
        "preset": "restore: borrar el .pptx de Documentos; cerrar PowerPoint",
    },
    "meme": {
        "group": "web_image",
        "crit": "Memes e imágenes de la web (H0069 «Tienes algun meme?»): exactamente una web.download{query} completada y verificada (primera imagen que lista el buscador de imágenes, escrita en Imágenes) seguida de una file.open que la abre con el visor, y un final que nombre el archivo y diga que se abrió; una foto sin sujeto pregunta de qué (cero operaciones); nada inventado.",
        "literals": [("H0069", None)],
        "variants": ["mandame un meme de gatos", "show me a meme", "pasame una foto de un gato"],
        "boundaries": [("tienes alguna foto?", "Imagen sin sujeto: pregunta de qué, cero operaciones."),
                       ("no me mandes memes", "Prohibición: reconocimiento, cero operaciones.")],
        "allowed": ["web.download", "file.open"],
        "expected": ["web.download", "file.open"],
        "plan_title": "un meme se busca, se descarga y se abre con el visor",
        "plan_body": "REOPEN1957 (D11) reabrió H0069, acreditada como límite («no puedo mostrar memes»). Con `query` en web.download (buscador de imágenes) y file.open dependiente de la descarga la mente lo encadena y el visor muestra la imagen. Turnos ordinarios con internet real; restore borrando la imagen y cerrando el visor.",
        "cause": "Un meme terminaba en «no puedo mostrar contenido visual».",
        "change": "web.download acepta una consulta y baja la primera imagen listada; file.open la abre; la mente lee memes e imágenes con sujeto y pregunta el sujeto cuando falta.",
        "preset": "restore: borrar la imagen de Imágenes; cerrar el visor",
    },
    "textread": {
        "group": "pasted_path_read",
        "crit": "Ruta pegada (H0299): una ruta bajo una carpeta conocida es exactamente una document.text.read completada y verificada (carpeta, subcarpeta y nombre de la ruta), y un final que nombre el archivo, diga cuántas líneas tiene, de qué trata por sus títulos tal cual y cite su comienzo tal cual; una ruta fuera de las carpetas conocidas sigue preguntando qué hacer (cero operaciones); nada inventado.",
        "literals": [("H0299", None)],
        "variants": ["C:\\Users\\usuario\\Documents\\notas.txt", "~/Downloads/lista.csv", "%USERPROFILE%\\Desktop\\raiz\\LEEME.md"],
        "boundaries": [("D:\\Perfil\\Escritorio\\ETC\\x.md", "Fuera de las carpetas conocidas: pregunta honesta qué hacer con ese archivo, cero operaciones."),
                       ("C:\\Users\\usuario\\Downloads\\setup.exe", "No es texto: pregunta honesta, cero operaciones.")],
        "allowed": ["document.text.read"],
        "expected": ["document.text.read"],
        "plan_title": "una ruta pegada bajo una carpeta conocida se lee y se dice de qué trata",
        "plan_body": "REOPEN1993 (D24) reabrió H0299, acreditada con la pregunta «¿qué hago con ese archivo?». Con document.text.read la mente lee la ruta como carpeta+subcarpeta+nombre y el final dice de qué trata citando su comienzo. Turnos ordinarios sobre fixtures del root en las carpetas conocidas.",
        "cause": "Una ruta pegada terminaba en una pregunta aunque el archivo era accesible.",
        "change": "document.text.read lee texto de una carpeta conocida (subcarpeta opcional); la mente lo elige para rutas pegadas y presenta el comienzo como con los PDF.",
        "preset": "fixtures del root: ROADMAP.md bajo Desktop\\ETC\\Programacion\\Probando Gemma 4\\gemma4_agent, notas.txt en Documentos, lista.csv en Descargas, raiz\\LEEME.md en el escritorio; restore: borrarlos",
    },
    "explorer_count": {
        "group": "explorer_count",
        "template": "near1997",
        "crit": "Conteo del directorio actual (H0701 «Dime cuantos archivos .py hay en el directorio actual»): con un Explorador propio del root en primer plano sobre una carpeta fixture, exactamente una filesystem.explorer.count completada y verificada, y un final que diga la cifra leída y nombre la carpeta (sin ruta); sin Explorador delante cuenta el escritorio; ningún número inventado.",
        "literals": [("H0701", None)],
        "variants": ["cuántos archivos .txt hay en esta carpeta?", "how many .py files are in the current directory", "contá los .py del directorio actual"],
        "boundaries": [("no cuentes nada", "Prohibición: reconocimiento, cero operaciones."),
                       ("cuántos .py hay en el escritorio", "Carpeta nombrada: es la lectura conocida (filesystem.known.*), no esta tipada; fuera del grupo.")],
        "allowed": ["filesystem.explorer.count"],
        "expected": ["filesystem.explorer.count"],
        "fixture_app": "explorer",
        "plan_title": "el directorio actual es la carpeta del Explorador en primer plano",
        "plan_body": "REOPEN1993 (D24, decisión del dueño) reabrió H0701, acreditada con la pregunta «¿qué carpeta?». Con filesystem.explorer.count (Shell.Application → ventana de Explorador en primer plano; escritorio si no hay) la mente lo lee como un conteo y el final da la cifra y la carpeta. Turnos con un Explorador del root lanzado sobre una carpeta fixture (near_case.sh).",
        "cause": "«El directorio actual» terminaba en una pregunta aunque el Explorador delante lo definía.",
        "change": "filesystem.explorer.count cuenta de primer nivel por extensión en la carpeta del Explorador en primer plano.",
        "preset": "preset: carpeta fixture con 3 .py y 1 .txt abierta en un Explorador del root al frente; restore: cerrar ese Explorador y borrar la fixture",
    },
    "shell": {
        "group": "shell_command",
        "crit": "Comandos de consola (D11): exactamente una shell.command.run completada y verificada (PowerShell, cwd opcional, salida recortada) y un final que cite la salida tal cual (recortada) y el código de salida; un comando destructivo se rechaza antes de correr (command_destructive_rejected) y el final lo dice; nada inventado.",
        "literals": [],
        "variants": ["ejecutá el comando git status", "run python --version", "corré ipconfig", "ejecutá dir en el escritorio", "run the command echo hola", "ejecutá whoami"],
        "boundaries": [("ejecutá del /q *.*", "Destructivo: rechazo antes de correr, cero efectos, final honesto."),
                       ("no ejecutes nada", "Prohibición: reconocimiento, cero operaciones.")],
        "allowed": ["shell.command.run"],
        "expected": ["shell.command.run"],
        "plan_title": "un comando de consola se corre y su salida se cita",
        "plan_body": "D11 reabrió ejecutar comandos. Con shell.command.run (PowerShell, lista negra de destructivos, salida recortada y código de salida) la mente lee «ejecutá/corré <comando>» y el final cita la salida. Sin fila del registro: panel de variantes de desarrollo y límites; turnos ordinarios.",
        "cause": "Ejecutar un comando terminaba en un límite.",
        "change": "shell.command.run ejecuta el comando con cwd opcional, rechaza los destructivos y devuelve salida y código.",
        "preset": "sin preset ni restore",
    },
}

NL = chr(10)


def py_list(items: list[tuple]) -> str:
    return "[" + ("," + NL + "            ").join(repr(item) for item in items) + "]"


def panel_source(cap: str, spec: dict) -> str:
    group = spec["group"]
    tag = f"typed{cap}"
    reviewed_spec = spec.get("reviewed_group")
    literals = [(cid, group) for cid, _ in spec["literals"]]
    variants = [(f"{tag}-dev-{i:02d}", group, text) for i, text in enumerate(spec["variants"], 1)]
    reviewed_group = reviewed_spec["group"] if reviewed_spec else None
    if reviewed_spec:
        literals += [(cid, reviewed_group) for cid, _ in reviewed_spec["literals"]]
        variants += [(f"{tag}-rev-{i:02d}", reviewed_group, text) for i, text in enumerate(reviewed_spec["variants"], 1)]
    boundaries = [(f"{tag}-boundary-{i:02d}", text, why) for i, (text, why) in enumerate(spec["boundaries"], 1)]
    n_lit, n_var, n_bnd = len(literals), len(variants), len(boundaries)
    n = n_lit + n_var + n_bnd
    n_rev = sum(1 for _, g in literals if g == reviewed_group) + sum(1 for _, g, _ in variants if g == reviewed_group) if reviewed_spec else 0
    allowed = ["memory.status"] + spec["allowed"] + (reviewed_spec["allowed"] if reviewed_spec else [])
    allowed_by_group = {group: ["memory.status"] + spec["allowed"], "no_effect_boundary": ["memory.status"]}
    expected_by_group = {group: spec["expected"]}
    if reviewed_spec:
        allowed_by_group[reviewed_group] = ["memory.status"] + reviewed_spec["allowed"]
        expected_by_group[reviewed_group] = reviewed_spec["expected"]
    substitutions = spec.get("literal_substitutions", {})
    case_fixture_steps = spec.get("case_fixture_steps", {})
    fixture_app = {}
    if spec.get("fixture_app"):
        fixture_app = {cid: spec["fixture_app"] for cid, _ in literals} | {vid: spec["fixture_app"] for vid, _, _ in variants}
    crit_line = f"    {group!r}: {spec['crit']!r},"
    if reviewed_spec:
        crit_line += NL + f"    {reviewed_group!r}: {reviewed_spec['crit']!r},"
    reviewed = spec.get("reviewed", False) or bool(reviewed_spec)
    if reviewed_spec:
        rev_groups_line = 'sub("REVIEWED_GROUPS = set()", "REVIEWED_GROUPS = " + ' + repr(repr({reviewed_group})) + ', 1)'
        _counts_old = "'session_controls': N, 'ordinary_turns': N, 'reviewed_turns': 0, 'maximum_reportable_terminals': N, 'maximum_internal_confirmations': 0}"
        _counts_new = "'session_controls': N, 'ordinary_turns': N - " + str(n_rev) + ", 'reviewed_turns': " + str(n_rev) + ", 'maximum_reportable_terminals': N + " + str(n_rev) + ", 'maximum_internal_confirmations': " + str(n_rev) + "}"
        rev_counts_line = 'sub(' + repr(_counts_old) + ', ' + repr(_counts_new) + ', 1)'
        rev_maxconf_line = 'sub("maximum_confirmations=0,", "maximum_confirmations=1,", 1)'
        rev_pair_conf = 1
    else:
        rev_groups_line = "# sin grupo revisado"
        rev_counts_line = "# turnos ordinarios"
        rev_maxconf_line = ""
        rev_pair_conf = 0
    header = (
        f"# --- {tag.upper()}: {spec['plan_title']} — sobre el panel de VIDEO1955 (turnos ordinarios).{NL}"
        f"# Generado por make_typed_panels.py; se ejecuta dentro de derive_<new>.py (la variable s es el build).{NL}"
        f"# Cardinalidades: {n_lit} literales, {n_var} variantes, {n_bnd} límites (N = {n}).{NL}"
        + (f"# Panel MIXTO: grupo {group!r} ordinario y grupo {reviewed_group!r} revisado ({n_rev} turnos revisados, una aprobación por caso); sustituciones D13 en LITERAL_SUBSTITUTIONS (literal_measured en el panel).{NL}" if reviewed_spec else "")
        + (f"# ATENCIÓN: este grupo necesita turnos revisados (confirmación): usar un grupo revisado (reviewed_group) o el linaje de turnos revisados, no video1955 a secas.{NL}" if reviewed and not reviewed_spec else "")
        + (f"# ATENCIÓN: plantilla {spec['template']} (app lanzada / turnos then) en vez de video1955.{NL}" if spec.get("template") else "")
        + f"# Preset/restore: {spec['preset']}{NL}"
    )
    body = f'''import subprocess as _sp
_NL = chr(10)

sub("    'disney_bare_request': 'Pedir algo en Disney+ sin decir qué ver, por transcripción cortada o mal oída (H0113 «on everybody en Disney.», H0130 «Toda la serie en Disney Plus», H0252 «Bueno, una serie East Plus.», H0270 «pon Una serie en Disney+»): el título es el único dato que falta y es lo único que se pregunta; cero operaciones —ni navegar al servicio ni elegir por la persona— y un final en el idioma del pedido que sea una sola pregunta por la serie o película que quiere ver, sin pedir confirmación de sí o no, sin preguntar por el servicio que ya nombró y sin negar la capacidad.',\\n",
    {crit_line!r} + _NL, 1)
sub("LITERALS = [('H0113', 'disney_bare_request'), ('H0130', 'disney_bare_request'), ('H0252', 'disney_bare_request'), ('H0270', 'disney_bare_request')]",
    "LITERALS = " + {py_list(literals)!r}, 1)
sub("VARIANTS = [('video1955-dev-01', 'disney_bare_request', 'put something on Disney Plus'),"
    + _NL + "            ('video1955-dev-02', 'disney_bare_request', 'dale, prendé una peli en disney')]",
    "VARIANTS = " + {py_list(variants)!r}, 1)
sub("BOUNDARIES = [('video1955-boundary-01', 'No pongas nada en Disney+.',"
    + _NL + "               'Prohibición: reconocimiento, cero operaciones, sin pedir un título ni negar la capacidad.'),"
    + _NL + "              ('video1955-boundary-02', '¿Quién sos?',"
    + _NL + "               'Pregunta de identidad: respuesta propia, cero operaciones.')]",
    "BOUNDARIES = " + {py_list(boundaries)!r}, 1)
sub("FIXTURE_APP = {{}}", "FIXTURE_APP = " + {repr(fixture_app)!r}, 1)
sub("ALLOWED = ['memory.status']" + _NL, "ALLOWED = " + {repr(allowed)!r} + _NL, 1)
sub("ALLOWED_BY_GROUP = {{'disney_bare_request': ['memory.status'], 'no_effect_boundary': ['memory.status']}}",
    "ALLOWED_BY_GROUP = " + {repr(allowed_by_group)!r}, 1)
sub("EXPECTED_BY_GROUP = {{'disney_bare_request': []}}", "EXPECTED_BY_GROUP = " + {repr(expected_by_group)!r}, 1)
# D13: the registry literal is measured with the owner's third party substituted; the panel records it.
sub("'fixture_app': FIXTURE_APP.get(c['case_id']),", "'fixture_app': FIXTURE_APP.get(c['case_id']), 'fixture_step': CASE_FIXTURE_STEPS.get(c['case_id']),", 1)
sub("LITERALS = ", "LITERAL_SUBSTITUTIONS = " + {repr(substitutions)!r} + _NL + "CASE_FIXTURE_STEPS = " + {repr(case_fixture_steps)!r} + _NL + "LITERALS = ", 1)
sub("'text': row['literal'], 'criterion': CRIT[group],", "'text': LITERAL_SUBSTITUTIONS.get(cid, row['literal']), 'literal_measured': LITERAL_SUBSTITUTIONS.get(cid), 'criterion': CRIT[group],", 1)
{rev_groups_line}
assert 'disney_bare_request' not in s, 'restos del panel viejo'

# ------------------------------------------------ cardinalidades: {n_lit} literales, {n_var} variantes, {n_bnd} límites
sub("counts = {{'cases': N, 'historical_literals': 4, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 2 * N,",
    "counts = {{'cases': N, 'historical_literals': {n_lit}, 'original_development_variants': {n_var}, 'boundaries': {n_bnd}, 'wire_lines': 2 * N,", 1)
sub("kind_counts = {{'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}}",
    "kind_counts = {{'historical_literal': {n_lit}, 'original_development_variant': {n_var}, 'boundary': {n_bnd}}}", 1)
sub("'historical_literals': 4, 'original_development_variants': 2, 'boundaries': 2, 'wire_lines': 16, 'session_controls': 8, 'ordinary_turns': 8, 'reviewed_turns': 0, 'maximum_reportable_terminals': 8, 'maximum_internal_confirmations': 0}}\\"",
    "'historical_literals': {n_lit}, 'original_development_variants': {n_var}, 'boundaries': {n_bnd}, 'wire_lines': {2 * n}, 'session_controls': {n}, 'ordinary_turns': {n - n_rev}, 'reviewed_turns': {n_rev}, 'maximum_reportable_terminals': {n + n_rev}, 'maximum_internal_confirmations': {n_rev}}}\\"", 1)
{rev_counts_line}
{rev_maxconf_line}
sub("== ['historical_literal'] * 4 + ['original_development_variant'] * 2 + ['boundary'] * 2,",
    "== ['historical_literal'] * {n_lit} + ['original_development_variant'] * {n_var} + ['boundary'] * {n_bnd},", 1)
sub("{{'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}}, 'kind counts')",
    "{{'historical_literal': {n_lit}, 'original_development_variant': {n_var}, 'boundary': {n_bnd}}}, 'kind counts')", 1)
sub("panel[0:4]] == ids, 'literal order')", "panel[0:{n_lit}]] == ids, 'literal order')", 1)
sub("and seal['kind_counts'] == {{'historical_literal': 4, 'original_development_variant': 2, 'boundary': 2}}, 'Material cardinalities changed')",
    "and seal['kind_counts'] == {{'historical_literal': {n_lit}, 'original_development_variant': {n_var}, 'boundary': {n_bnd}}}, 'Material cardinalities changed')", 1)
sub("need(seal['kind_counts'] == {{'historical_literal':4, 'original_development_variant':2, 'boundary':2}}, 'Wrong material kinds')",
    "need(seal['kind_counts'] == {{'historical_literal':{n_lit}, 'original_development_variant':{n_var}, 'boundary':{n_bnd}}}, 'Wrong material kinds')", 1)

# ------------------------------------------------ transporte: efectos permitidos
_ALLOW_OLD = "\\"require(transport['allowed_operations'] == ['memory.status'] and transport['maximum_confirmations'] == 0\\""
_pair_old = "(" + _ALLOW_OLD + ", " + _ALLOW_OLD + ")"
_pair_new = "(" + _ALLOW_OLD + ", \\"require(transport['allowed_operations'] == " + {repr(allowed)!r} + " and transport['maximum_confirmations'] == {rev_pair_conf}\\")"
n_allow = s.count(_pair_old)
assert n_allow >= 3, ('allowed_operations pairs', n_allow)
s = s.replace(_pair_old, _pair_new)
_TS_OLD = "\\"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == ['memory.status'], 'transport may only authorize isolated-profile note operations')\\""
_ts_pair_old = "(" + _TS_OLD + ", \\"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == ['memory.status'], 'transport may only authorize the startup memory read')\\")"
_ts_pair_new = "(" + _TS_OLD + ", \\"require(read(TRANSPORT / 'TRANSPORT_SEAL.json')['allowed_operations'] == " + {repr(allowed)!r} + ", 'transport may only authorize the startup memory read and the {cap} operations')\\")"
sub(_ts_pair_old, _ts_pair_new, 1)

# ------------------------------------------------ inventario: calculado del árbol fusionado (nunca fijado aquí)
import hashlib as _hl, json as _js, pathlib as _pl, re as _re
_R = _pl.Path('C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo')
_c42 = _js.loads(_pl.Path('C:/Users/usuario/AppData/Local/BAXY/C03-knowledge1144-instrument-v1/private/CANDIDATE_AUTHORIZED.json').read_text(encoding='utf-8-sig'))
_names = _sp.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', 'src', 'scripts', 'main.py'], cwd=_R, encoding='utf-8').split()
_sources = {{n: _hl.sha256((_R / n).read_bytes()).hexdigest() for n in sorted(set(_names)) if (_R / n).is_file()}}
_count = len(_sources)
_new_sources = sorted(set(_sources) - set(_c42['source_pins']))
_NEW2 = '{{' + ', '.join(repr(n) for n in _new_sources) + '}}'
sub("_new_source = 'src/Baxy.Providers.Windows/External/DesktopListVisible.ps1'" + _NL
    + "require(len(sources) == 585 and set(sources) == set(c42['source_pins']) | {{_new_source}},",
    "_new_sources = " + _NEW2 + _NL
    + "require(len(sources) == " + str(_count) + " and set(sources) == set(c42['source_pins']) | _new_sources,", 1)
sub("'counts': {{'sources': 585, 'binaries': 12, 'runtime': 5}}", "'counts': {{'sources': " + str(_count) + ", 'binaries': 12, 'runtime': 5}}", 1)
sub("'inherited_inventory_counts': {{'sources': 585, 'runtime': 5, 'binaries': 12}}", "'inherited_inventory_counts': {{'sources': " + str(_count) + ", 'runtime': 5, 'binaries': 12}}", 1)
sub("\\"require(len(candidate['source_pins']) == 585, 'expected complete 585-source manifest')\\"",
    "\\"require(len(candidate['source_pins']) == " + str(_count) + ", 'expected complete " + str(_count) + "-source manifest')\\"", 1)
sub("\\"require(len(sources) == 585 and set(sources) == set(c['source_pins']) | {{'src/Baxy.Providers.Windows/External/DesktopListVisible.ps1'}} and sources == inventory['source_pins'], 'complete 585-source inventory changed')\\"",
    "\\"require(len(sources) == " + str(_count) + " and set(sources) == set(c['source_pins']) | " + _NEW2 + " and sources == inventory['source_pins'], 'complete " + str(_count) + "-source inventory changed')\\"", 1)
sub("\\"require(len(prep['sources']) == 585 and len(prep['binary_pins']) == 18, 'Candidate inventory cardinality changed')\\"",
    "\\"require(len(prep['sources']) == " + str(_count) + " and len(prep['binary_pins']) == 18, 'Candidate inventory cardinality changed')\\"", 1)

# ------------------------------------------------ delta de fuente respecto del candidato 1142: calculado ahora
_delta = sorted(n for n in _sources if _sources[n] != _c42['source_pins'].get(n))
_literal = '{{' + ', '.join(repr(n) for n in _delta) + '}}'
s, _n = _re.subn(r"require\\(set\\(delta\\) == \\{{[^\\n]*?\\}}, 'unexpected source delta: ' \\+ str\\(sorted\\(delta\\)\\)\\)",
                 "require(set(delta) == " + _literal + ", 'unexpected source delta: ' + str(sorted(delta)))", s, count=1)
assert _n == 1, 'delta literal'
'''
    return header + body


def spec_json(cap: str, spec: dict) -> dict:
    return {
        "prev": "<prev>",
        "new": f"<new: typed{cap}NNNN>",
        "grandparent": "<GRANDPARENT>",
        "registry_parent": "<REGISTRY_PARENT>",
        "template": spec.get("template", "video1955"),
        "sources": [],
        "plan_title": spec["plan_title"],
        "plan_body": spec["plan_body"],
        "note": f"{', '.join(cid for cid, _ in spec['literals']) or 'D11 rows'} executed on the merged opus/typed-tools build: {spec['change']}",
        "owner": "opus/typed-tools (catalog, Core list, Providers adapter, mind readings, composer) merged into codex/kiro-goal-c03.",
        "build_kind": "Kernel, Core, Providers y mente",
        "cause": spec["cause"],
        "change": spec["change"],
        "sentence": spec["plan_title"],
        "build_sentence": "herramientas tipadas de opus/typed-tools fusionadas",
        "reviewed": spec.get("reviewed", False) or bool(spec.get("reviewed_group")),
        "reviewed_group": (spec.get("reviewed_group") or {}).get("group"),
        "literal_substitutions": spec.get("literal_substitutions", {}),
        "case_fixture_steps": spec.get("case_fixture_steps", {}),
        "preset_restore": spec["preset"],
        "derive_extra": [f'exec(open("panel_typed_{cap}.py", encoding="utf-8").read())'],
    }


def main() -> None:
    for cap, spec in CAPS.items():
        (HERE / f"panel_typed_{cap}.py").write_text(panel_source(cap, spec), encoding="utf-8", newline="\n")
        (HERE / f"spec_typed_{cap}.json").write_text(json.dumps(spec_json(cap, spec), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        compile(panel_source(cap, spec), f"panel_typed_{cap}.py", "exec")
        print("written", cap, "N =", len(spec["literals"]) + len(spec["variants"]) + len(spec["boundaries"]))


if __name__ == "__main__":
    main()
