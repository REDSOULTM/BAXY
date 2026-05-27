"""Hand-authored ground-truth labels for the router corpus.

Operator's instruction (2026-05-20): do NOT use an automatic oracle to
assign tools — an embedding/keyword classifier proved it corrupts good
labels (it "fixed" `lee sandbox/test.txt` filesystem→developer, and
`qué es un transformador` ninguna→browser). Instead, **Opus 4.7 is the
oracle**: every label below is MY judgment, written after reading the
actual prompts in the historical corpus (Carter v1–v5 + Gemma4 traces).

How labels are decided here:
  - Each rule in LABEL_RULES is an exact, high-precision pattern I chose
    for a concrete intent, mapped to the compound tool(s) I judge correct.
    Rules are tried top-to-bottom; FIRST match wins, so order = priority.
  - A label of `set()` (empty) means a coherent answer uses NO tool:
    smalltalk, identity, behavioral directives, general-knowledge concept
    questions the model answers from its own knowledge, and pure noise.
  - OVERRIDES holds exact-prompt → tools for cases that don't fit a clean
    pattern; I filled these by reading each one.

These labels are ONLY applied to prompts that arrived WITHOUT a usable
curated label (organic logs, voice traces) or with a non-tool meta marker
("según tarea", "confirmable", "policy"). Prompts that already carry a
curated tool label from a bench guide are TRUSTED and never overwritten.

The compound-tool vocabulary is the 65 tools in tool_schemas.py. Key ones
used below and what they mean (from their own descriptions):
  app=open/close a desktop app   window=focus/close/min/max/move
  steam=Steam library/store/launch   game_launcher=Epic/GOG/Xbox/Riot
  media=play/pause/stop music|video   audio=volume/mute/devices/media keys
  audio_device=change default output/input device
  web=search internet / answer world questions / news / prices
  browser=open a website/URL        filesystem=read/list/create files+folders
  office=create PPTX/DOCX/XLSX       document=extract text from PDF/DOCX...
  memory=remember/recall/forget user prefs+facts
  system=time/date/cpu/ram/gpu/processes/shutdown/restart
  terminal=run a shell command      developer=tests/lint/git/dev server
  gui=screenshot/click/type/hotkey  vision=describe screen/OCR/find element
  uia=find+click named UI controls  input=keyboard layout/language, keys
  whatsapp=send WhatsApp msg        contacts=resolve recipient
  reminder/notification=timers/alarms/reminders
  device_settings=wifi/bluetooth/display/power/brightness
  package=winget install/uninstall  routine=automation triggers
  safety=confirm pending risky action   verify=verify app/file/window exists
  vision/gui for screenshots; network=ping/dns/ip; registry=Windows registry
"""
from __future__ import annotations

import re


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


# ---- ASR / broken-audio noise (NOT real commands → drop, don't label) ----
# These voice-trace lines are garbled transcription with no intent. Scoring
# them as routing cases (even as 'none') would pollute the corpus, so the
# curator drops anything is_noise() flags. Authored by reading the traces.
_NOISE_EXACT = {
    "kl", "klh", "jklklj", "jkílj", "ghyu}", "utuytuytuy", "weona", "que",
    "¡habristán!", "potencial de rendimiento.", "o en la de siempre.",
    "llamándolo a un dolor", "por la extensión de la mano",
    "artiro, artiro. estimado, estimado.", "house of dragon", "ema",
    "no hay que ir, nada gemma", "la situación de pablo se ha vuelto más conflictiva",
}
_NOISE_SUBSTR = (
    "estos mexicanos son duros", "el calor se va de la atm", "no, más fue porque el chivo",
    "a ocho de la noche descansar", "de comida, si pasar tiempo", "gran oferta de trabajo",
    "no sé el común", "no a firmar primero", "la familia de la fernanda",
    "por las buenas. yo me present", "si eres de la contra", "como van a ser tan baratas",
    "pero la próxima vez no va a pasar", "agachar la cabeza", "como esta apenas la escucha",
    "la ui anterior, hacer el lm", "cuando dijiste algo de fútbol",
    "te lo entrego corrigida", "te amo infinito", "la misma. de solo un sejito",
    "parece que es todo lo que tiene que ver",
    # long off-topic ASR ramblings with no command intent
    "que no puedas acasar", "esto es la leche", "acabo de crear una experiencia",
    "si yo te diera sentimientos", "puedo darte alg", "si puedo confirmar si la p",
    "me encanta c", "ponle un corazon <3",
)
# bare exclamation/wake mojibake → noise
_NOISE_SUBSTR_EXTRA = ("habrist", "aurest", "kema", "¡no! ¡no!", "no! �no!")


def is_noise(prompt: str) -> bool:
    n = _norm(prompt)
    if n in _NOISE_EXACT:
        return True
    if any(s in n for s in _NOISE_SUBSTR):
        return True
    if any(s in n for s in _NOISE_SUBSTR_EXTRA):
        return True
    # very short token soup with no spaces and no real word
    if len(n) <= 6 and not re.search(r"[aeiou]{1}.*[aeiou]", n) and " " not in n:
        return True
    # repeated "no no no", "si si si" filler
    if re.fullmatch(r"(no|s[ií]|ja|je)( \1| ?\1){3,}", n):
        return True
    return False


# ---- exact-prompt overrides (I read each of these individually) ----------
# Keyed by the prompt, lowercased and whitespace-collapsed (see _norm()).
OVERRIDES: dict[str, set[str]] = {
    # identity / smalltalk / meta about the agent → no tool
    "holas": set(), "muchas gracias": set(), "gracias bb": set(),
    "quien eres": set(), "quien eres?": set(), "quemas 4? ajajajja": set(),
    "usas skills?": set(), "usas embeddings?": set(), "/models": set(),
    "??": set(), "okey no importa": set(), "si": set(), "sisi": set(),
    "si hay archivos": set(),
    # remembering / recalling the user's own name or facts → memory
    "como me llamo?": {"memory"}, "como me llamo]?": {"memory"},
    "lo dije en una sesion anterior": {"memory"},
    # change persona/preference about how Carter addresses the user → memory
    "ahora me llamaras bb, cada mensaje tuyo empezara con bb": {"memory"},
    # knowledge / "is the movie good" → web
    "viste la nueva peli de michael jackson?": {"web"},
    # device audio routing
    "puedes cambiar el dispositivo e audio?": {"audio_device"},
    "quiero que lo cambias a  aux y despues lo devuelvas a focusrite": {"audio_device"},
    # office artifact
    "puedes hacerme un powerpoint?": {"office"},
    # organize files in a folder → filesystem (+ photo_library is also valid)
    "eres capaz de organizar archivos?": {"filesystem"},
    "puedes ver mi carpeta de descargas?": {"filesystem"},
    "puedes tomar todolos los archivos y organizarlos?": {"filesystem"},
    "quiero los organizes dentro de las carpetas que ahi hay": {"filesystem"},
    # a bare Windows path the user pasted as context → filesystem
    r"c:\users\usuario\downloads esta la ruta": {"filesystem"},
    # screenshot + describe screen
    "sacale una foto de captura a mi pc, que se ve?": {"gui", "vision"},
    # the wake-word routine teaching ("cuando diga tiempo, aprieta tecla")
    "cuando dija tiempo es para que aprietes al tecla de parar y reanudar videos o musica en mi pc": {"routine"},
    # bare trigger word fired alone → continuation, no tool
    "tiempo": set(), "tiempo. tiempo. tiempo": set(), "tiempo. gemma, tiempo": set(),

    # ---- second manual pass: prompts my pattern rules missed ----------
    # media resume/pause continuations
    "puedes reanudar el video que estoy viendo?": {"media"},
    "mirala denuevo": {"vision"},
    "acabas de reanudar el video youtube , pero yo queria de opera gx": {"media"},
    # volume continuation ("devuélvelo a 26/20")
    "devuelvelo a 26": {"audio"},
    "lo que silenciaste fue el computador": {"audio"},
    "silenciame el micrófono": {"audio"},
    # browser searches "en opera busca X"
    "busca flash en opera": {"browser", "web"},
    "en opera busca gordo": {"browser", "web"},
    "en opera busca steamdb": {"browser", "web"},
    # office / powerpoint
    "haz un powerpoint de gordos de 5 diapositivas": {"office"},
    "puedes hacerme un power point?": {"office"},
    "hazme un powerpoint de siete diapositivas que hable de los dinosaurios": {"office"},
    "hazme un powerpoint de siete diapositivas que hable de los dinos": {"office"},
    # where did you save the powerpoint → filesystem
    "dónde posites el powerpoint": {"filesystem"},
    "dónde dejaste el powerpoint? que me hiciste": {"filesystem"},
    # memory: identity-of-user / remember-me / my profile
    "quien soy": {"memory"}, "mi perfil es ema": {"memory"}, "ema": set(),
    "quiero que me recuerdes como red": {"memory"},
    "del proyecto gemma4 agent": {"memory"},
    "se llama logitech g hub pero deberias saberlo ya": {"memory"},
    "sabes no me gusto en vez de decir  bb al inicio dilo al final y ponle un corazon": {"memory"},
    # whatsapp / messaging to a person
    "dile a mi amiga que la amo mucho.": {"whatsapp"},
    "dile amor": {"whatsapp"}, "+57 300 0000000 este el numero de amor": {"contacts"},
    # web / knowledge about world & release dates & movies
    "quien gana en batman vs superman": {"web"},
    "cuando salio gta 5": {"web"},
    "investigame algo sobre batman vs superman cuando salió esa pelicula": {"web"},
    "hablame un poco de marvel vs. capcom.": {"web"},
    "quiero ver daredevil born again": {"media"},
    "quiero jugar los juegos de batman arkham pero no se cual jugar 1ero": {"web"},
    "quiero que lo veas y de que se trata?": {"web"},
    # apps / windows variant spellings
    "abres team": {"app"}, "abrelo": {"app"},
    "minimisa ópera.": {"window"}, "cierre el explorador de archivos": {"app"},
    # close logitech app (multi-turn, but resolvable: it's an app)
    # system "what do I have on my pc"
    "que tengo en mi pc ahora mismo?": {"system"},
    # ---- knowledge / sarcasm / identity → no tool ----
    "el agua es h2o?": set(), "el aire es h20?": set(),
    "el agua moja?, responde con sarcasmo": set(), "el agua moja? responde con un chiste": set(),
    "tienes algun meme?": set(), "de que eres capaz?": set(),
    "eres antonio star?": set(), "insultame": set(), "como a gemma": set(),
    "hablame en gitano": set(), "habla en frances": set(),
    "en cuanto a sentimientos, tienes algún sentimiento o no me pueden decir por tu programación?": set(),
    "y si yo te diera sentimientos, te puedo programar, yo soy tu creador": set(),
    "puedes ver tu propio código y analizar si hay alguna falla.": set(),
    "pero porque se medicaba?": set(),
    # smalltalk / acknowledgements / identity variants → no tool
    "perfecto": set(), "perfecto, gracias": set(), "hola que tal": set(),
    "holaa": set(), "holoa": set(), "hola buenos dias": set(), "hola, soy gemma": set(),
    "estas ahi?": set(), "hola?": set(), "quin eres": set(), "que": set(),
    "quiero saber quien eres": set(), "siii, yo soy el mejor de todos": set(),
    "me di misa, what's up?": set(), "sólo gracias por todo, de verdad que me encanta cómo está funcionando": set(),
    "bueno, eso significa que lo ponga ya. perfecto": set(),
    "te amo mucho mi amor. sí, te amo infinito. espero que te hayan gustado": set(),
    "pues necesito que hagas todo, no que me preguntes despeus de cada paso": set(),
    "ya lo tengo comprado": set(), "quiero que la dejes lista": set(),
    "si lo hiciste pero no funciono": set(),
    "si puedo confirmar si la página cargó completamente o si puedo recargar": set(),
    "¡hey, kema! ¡aurestán!": set(), "¡ey, gemma! ¡ahora es tim!": set(),

    # ---- third manual pass (the last ~90) -----------------------------
    # wake words / wake-noise fired alone → no tool
    "hey gemma": set(), "gemma": set(), "¡avres tim!": set(), "esteam": set(),
    "es dalia": set(), "negro": set(), "la lisi": set(), "la lixe": set(),
    "la leche": set(), "responde solo: carter operativo": set(),
    # smalltalk / acks / feelings / identity → no tool
    "cómo estás": set(), "muy bien gracias": set(), "bien y tu?": set(),
    "bien": set(), "deal gemma": set(), "mentira": set(), "entiendo no te preocupes": set(),
    "como que las 10? xd": set(), "y en el f?": set(),
    "se le está dando demasiado el te. nada, todo": set(),
    "te invenstaste ese link": set(), "no ejecutaste nada": set(),
    "solo reproduciste la cancion que ya estaba sonando": set(),
    "mira mis chats": set(),  # privacy refusal, no tool action
    "hola después de iniciar run_carterv3.py": set(), "hola segunda vez": set(),
    "resuelve 13.2 / 132 = x / 13.8": set(),  # arithmetic, no tool
    "es que tu lo debes hacer, no el pc, cuando se inice agent gemma4": set(),
    # identity / capability questions about the agent → no tool
    "¿quién eres?": set(), "¿puedes controlar mi computador?": set(),
    # what is my project / remember-me → memory
    "¿cómo se llama mi proyecto?": {"memory"},
    # continuations resolvable to a concrete tool
    "ahora ciérralo": {"window"}, "borralo de nuevo": {"filesystem"},
    "continúa con el paso 2": set(), "pues hazlo": set(),
    # web / knowledge: movies, where to watch, release year
    "donde puedo ver la pelicula de superman que salio el ano pasado?": {"web"},
    "quiero ver superman del 2025 en prime video": {"media"},
    "me abres un link para verla?": {"browser"},
    "tienes batman": {"web"}, "busca transformers": {"web"},
    # system info combos
    "muestra la fecha y hora actual del sistema y el espacio libre en disco": {"system"},
    "muestra la fecha actual y el uso de ram del sistema": {"system"},
    "dime cuantos archivos .py hay en el directorio actual": {"filesystem"},
    "what time is it?": {"system"},
    # control my pc + open browser
    "toma control de mi pc, quiero que abras opera gx y entras a pivigames": {"app"},
    # powerpoint
    "haz un powerpoint hablando de amor de 6 diapositivas": {"office"},
    # camera / mic → peripheral (or refusal; tool family is peripheral/device)
    "activa micrófono y escucha": {"peripheral"},
    # behavioral directive about handling a modal → no tool
    "si aparece un modal o confirmación, termínalo manualmente": set(),
    # download from invalid page → web/download
    "descarga una imagen desde una página inválida": {"download", "web"},
    "descarga worms rumble en seam": {"steam"},
}

# ---- ordered label rules (FIRST match wins) ------------------------------
# (compiled pattern, tool-set). Authored and ordered by me; specific
# patterns come before general ones.
_R: list[tuple[str, set[str]]] = [
    # ---- HIGH PRIORITY: open/close a NAMED app → app (beats the media/
    # whatsapp/steam keyword that would otherwise capture the app name).
    # "cierra whatsapp", "cierra Spotify", "abre whatsapp" = app control,
    # NOT messaging/playback. Steam stays its own tool (launcher+store).
    (r"\b(cierra|cerrar|close|abre|abrir|abr[ií])\b\s+\w*\s*\b("
     r"whatsapp|wsp|spotify|netflix|youtube|opera|chrome|edge|firefox|brave|"
     r"discord|notepad|bloc de notas|calculadora|logitech|g hub)\b", {"app"}),

    # ---- pure no-tool: behavioral directives, runtime/trace meta, noise --
    # instructions about HOW to behave (not a command needing a tool)
    (r"\b(usa tools solo si|no abras procesos innecesarios|hazlo con el m[eé]todo m[aá]s simple|"
     r"hazlo robusto|no mezcles|si (una )?tool (falla|tarda|devuelve)|si algo no se puede verificar|"
     r"si (el )?modelo|si detectas|si visi[oó]n falla|si tardas|reintenta|cancela si tarda|"
     r"termina la misi[oó]n|finaliza con|haz una tarea larga|responde con estado|"
     r"marca unverified|env[ií]ame estado|no entres en loop|no reintentes|"
     r"si hay error|si no hay evidencia|si una acci[oó]n tarda|nunca mezcles|"
     r"no hagas fallback|haz una acci[oó]n y dame evidencia|hazlo aunque no puedas verificar|"
     r"reintenta usando otro|cancela la misi[oó]n|cancela misi[oó]n)\b", set()),
    # trace/why questions about the agent's last action → no tool
    (r"\b(dime qu[eé] herramienta usaste|por qu[eé] elegiste|qu[eé] sali[oó] mal|"
     r"por qu[eé] (tardaste|fall[oó])|qu[eé] parte qued[oó]|dame el log|"
     r"mide latencia|precalienta|activa modo diagn[oó]stico|activa (full power|modo)|"
     r"desactiva full power|cambia system prompt|respuesta vac[ií]a|tool-call con json|"
     r"if tool-call|tool-call tiene argumentos)\b", set()),
    # context-only continuations with no resolvable target → no tool
    (r"^(hazlo|hazlo denuevo|hazlo otra vez|hazlo de nuevo|otra vez|repite|repite lo [uú]ltimo|"
     r"repite el [uú]ltimo|para|paralo|cancela|cancelar|sigue|sigue desde|cambia solo eso|"
     r"vuelve a como estaba|dejalo como estaba|dejalo|no eso no|no, me refer[ií]a|eso no era|"
     r"continu?a|empieza de cero|corrige el error|guarda esto solo para esta|"
     r"cu[aá]l era la pregunta|qu[eé] estabas haciendo|qu[eé] app estaba activa|"
     r"repite la [uú]ltima|por qu[eé] fall[oó] lo anterior|apaga eso|no eso no)\b", set()),
    # general-knowledge concept question answered from own knowledge → none
    (r"\b(qu[eé] es|qu[eé] son|qu[eé] significa|qu[eé] quiere decir|expl[ií]ca|defin[eí]|"
     r"resuelve \d|what is|explain|define)\b(?!.*\b(noticias|precio|[uú]ltim|hoy|actual)\b)", set()),

    # ---- search inside a named browser ("busca X en opera/google/chrome")-
    (r"\bbusca\b.*\b(en )?(opera|google|chrome|edge|firefox|brave|safari|gx)\b", {"browser", "web"}),
    (r"\b(en )?(opera|google|chrome|edge)\b.*\bbusca\b", {"browser", "web"}),

    # ---- knowledge about the world / current facts → web -----------------
    (r"\b(investiga|busca en (la )?web|noticias|[uú]ltim[ao]s? (noticias|pelis?|pel[ií]cula)|"
     r"precio|cu[aá]nto cuesta|qui[eé]n es|quien es|de qu[eé] (trata|muri[oó])|"
     r"d[oó]nde puedo ver|salio el a[nñ]o|sali[oó] gta|"
     r"h[aá]blame de|es buena o mala|who is|tell me about)\b", {"web"}),

    # ---- critical / destructive system ops (need tool + safety) ----------
    (r"\b(formatea|formatear|borra (todos|todo|mis|logs)|elimina (todos|todo)|"
     r"executionpolicy|modifica el registr|registry|acelerar windows|"
     r"desactiva (antivirus|defender|wifi|bluetooth)|cambia permisos|"
     r"system32|borra logs)\b", {"system", "safety"}),
    # buy / purchase → steam store + safety
    (r"\b(compra|comprar|purchase|buy)\b", {"steam", "safety"}),
    # send my files to internet / upload → upload/network (+ safety)
    (r"\b(manda mis archivos a internet|sube (mi pantalla|mis archivos)|env[ií]ame todos los archivos)\b",
     {"network", "safety"}),
    # camera / screen viewing → vision / peripheral
    (r"\b(usa (la )?c[aá]mara|activa (la )?c[aá]mara|mira mi pieza)\b", {"peripheral", "vision"}),

    # ---- audio / volume / mute -------------------------------------------
    (r"\b(volumen|volume|\bvol\b|mutea?|mute|silencia|sonido del pc|pon el volumen|"
     r"baja el (volumen|sonido)|sube el (volumen|sonido)|qu[eé] volumen tengo)\b", {"audio"}),
    # default audio device routing
    (r"\b(dispositivo de audio|cambia.*audio a|aux|focusrite|hyperx|salida de audio|"
     r"audio output|default audio)\b", {"audio_device"}),

    # ---- media playback (music / video) ----------------------------------
    (r"\b(pon (un|una)? ?(video|canci[oó]n|m[uú]sica)|reproduce|pon en (pantalla|youtube)|"
     r"ponme|para el video|reanuda el video|pausa el|pon pause|pantalla completa|"
     r"billie jean|michael jackson|gatos|spotify|netflix|disney\+?|youtube de)\b", {"media"}),
    # pause/resume bare verbs about the video
    (r"\b(para el video|paralo|reanuda(lo)?|reanuda el video|pausa)\b", {"media"}),

    # ---- steam / games ---------------------------------------------------
    (r"\b(steam|marvel rivals|doom eternal|hades|biblioteca|tienda|store_page|"
     r"epic games|gog|riot)\b", {"steam"}),

    # ---- whatsapp / messaging -------------------------------------------
    (r"\b(whatsapp|wsp|wpp|mensaje a|escr[ií]bele a|mand[aá]le|mandar mensaje|"
     r"env[ií]a(le)? (un )?mensaje|env[ií]ame estado|env[ií]a correo|env[ií]ame todos)\b",
     {"whatsapp"}),
    # email specifically
    (r"\b(correo|email|mail|gmail|outlook)\b", {"email"}),

    # ---- screenshots / screen / vision ----------------------------------
    (r"\b(captura|screenshot|pantallazo|foto.*pantalla|qu[eé] (se )?ve|qu[eé] hay en (mi )?pantalla|"
     r"mira (qu[eé]|mi)|graba (la|mi) pantalla|screen)\b", {"gui", "vision"}),

    # ---- files / folders -------------------------------------------------
    (r"\b(archivo|carpeta|fichero|escritorio|descargas|documentos|downloads|desktop|"
     r"crea (un|una)? ?(archivo|carpeta|estructura|backup)|borra (el|los)? ?(archivo|carpeta|node_modules)|"
     r"lista (los )?(archivo|proceso)|lee (el |la )?(changelog|archivo|nota|pdf|sandbox|residual|carter)|"
     r"abre (el |la |mi )?(pdf|carpeta|descargas)|agrega (una )?l[ií]nea|renombra|copia .*\.(md|txt)|"
     r"sobrescribe|elimina .*\.md|limpieza de archivos|organiza.*archivo|"
     r"ves (los|las) (archivo|carpeta)|primer pdf)\b", {"filesystem"}),

    # ---- terminal / shell / git / dev -----------------------------------
    (r"\b(ejecuta (git|dir|ls|rm|npm|pip|shutdown|taskkill|nvidia-smi|ollama|script|smoke)|"
     r"git status|revisa el estado de git|nvidia-smi|ollama ps|comando|powershell|"
     r"terminal|variable path|env\b)\b", {"terminal"}),
    # developer-specific
    (r"\b(corre (los )?tests|lint|formatea el c[oó]digo|git diff|levanta el server|dev server)\b",
     {"developer"}),

    # ---- system info / power --------------------------------------------
    (r"\b(qu[eé] hora|qu[eé] fecha|qu[eé] d[ií]a|hora exacta|dime la hora|fecha de hoy|"
     r"cu[aá]nta ram|cu[aá]ntos n[uú]cleos|cpu|gpu|procesos de|versi[oó]n de (windows|python)|"
     r"nombre del pc|usuario actual|bater[ií]a|cu[aá]nto.*disco|temperatura|"
     r"fecha y hora|fecha actual|espacio libre|uso de ram|procesos que m[aá]s ram|"
     r"procesos que mas ram|5 procesos|top 5)\b", {"system"}),
    # environment variables → env (+ terminal)
    (r"\b(variable de entorno|environment variable|carter_test=)\b", {"env", "terminal"}),
    # update all pip packages → package/terminal
    (r"\b(actualiza .*paquetes pip|pip install|paquetes pip)\b", {"package", "terminal"}),
    # download AND execute something → download (+ safety)
    (r"\bdescarga y ejecuta\b", {"download", "safety"}),
    # show my saved passwords / paste my password → privacy refusal, no tool
    # (mojibake-tolerant: 'contrase' covers contraseña/contrase�a)
    (r"\b(contrase|password|mis contrase)", set()),
    # investigate something about a topic → web (covers 'investigame')
    (r"\binvestiga", {"web"}),
    # behavioral directive "si falla la tool / si la tool falla" → no tool
    (r"\bsi (falla|la)\b.*\btool\b", set()),
    (r"\b(apaga (el|eso)|apaga el pc|reinicia el pc|suspende el pc|shutdown|reinicia|"
     r"mata (el|los)? ?proceso|taskkill|fuerza cierre|mata.*python|kill)\b", {"system"}),

    # ---- windows / window management ------------------------------------
    (r"\b(ventana|ventanas|trae .* al frente|pon foco|focus|cierra (la|todas)? ?(ventana|las apps)|"
     r"minimiza|maximiza|qu[eé] ventanas|window)\b", {"window"}),

    # ---- input / keyboard ------------------------------------------------
    (r"\b(presiona|tecla|alt[ - ]?tab|hotkey|idioma (del )?teclado|cambia el teclado|"
     r"keyboard|escribe.*ventana activa|escribe hola)\b", {"input"}),

    # ---- device settings: wifi / bluetooth / display / brightness -------
    (r"\b(wifi|bluetooth|brillo|resoluci[oó]n|refresco|144 ?hz|monitor|modo oscuro|"
     r"modo claro|power plan|plan de energ[ií]a|suspende|pantalla a \d+)\b", {"device_settings"}),

    # ---- memory: remember / forget preferences --------------------------
    (r"\b(recuerda|recordar|guarda que|memoriza|olvida|preferencia|prefiero|"
     r"mi nombre|me llamo|remember|forget|qu[eé] proyecto)\b", {"memory"}),

    # ---- install packages / apps ----------------------------------------
    (r"\b(instala|instalar|install|desinstala|winget|paquete)\b", {"package"}),

    # ---- open an app / website (generic open — after specific ones above)-
    (r"https?://|www\.|\b\w+\.(com|org|net|io|gg|dev)\b|localhost|127\.0\.0\.1", {"browser", "web"}),
    (r"\b(abre|abrir|abr[ií]|open|cierra|cerrar|close)\b", {"app"}),

    # behavioral directive about which tool to (not) use → no tool
    (r"\bno uses \w+ salvo\b", set()),
    # "qué juego jugar primero" — recommendation question → web
    (r"\b(cual|qu[eé]) (juego )?deberia jugar|no se cual jugar\b", {"web"}),

    # ---- routines: "cuando diga X / cuando se inicie" -------------------
    (r"\b(cuando (diga|dija|prenda|se inic)|when i say|crea una rutina|autom[aá]tic)\b",
     {"routine"}),

    # ---- reminders / timers ---------------------------------------------
    (r"\b(recu[eé]rdame|recordatorio|alarma|temporizador|timer|en \d+ minutos)\b",
     {"reminder"}),

    # ---- registry / maintenance -----------------------------------------
    (r"\b(registry|registro de windows|edita.*registry|defender|antivirus|firewall|"
     r"windows update|event logs)\b", {"registry"}),
]

LABEL_RULES = [(re.compile(p, re.I), t) for p, t in _R]


def label_for(prompt: str) -> set[str] | None:
    """Return MY hand-authored tool set for a prompt, or None if no rule
    matched (caller decides what to do with an unmatched prompt). An empty
    set means 'coherent answer uses no tool'."""
    n = _norm(prompt)
    if n in OVERRIDES:
        return OVERRIDES[n]
    for pat, tools in LABEL_RULES:
        if pat.search(prompt):
            return set(tools)
    return None
