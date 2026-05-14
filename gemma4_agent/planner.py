"""Lightweight mission planning and dynamic tool selection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


STEP_SPLIT_RE = re.compile(
    r"\b(?:luego|despues|después|entonces|y luego|y despues|y después|,\s*luego)\b|[;]\s*",
    re.IGNORECASE,
)
MAX_SELECTED_TOOLS = 16


@dataclass
class MissionStep:
    index: int
    text: str
    suggested_tools: list[str] = field(default_factory=list)
    verification_hint: str = ""


@dataclass
class MissionPlan:
    goal: str
    steps: list[MissionStep]
    cleanup_expected: bool = False
    needs_pc_action: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "cleanup_expected": self.cleanup_expected,
            "needs_pc_action": self.needs_pc_action,
            "steps": [
                {
                    "index": step.index,
                    "text": step.text,
                    "suggested_tools": step.suggested_tools,
                    "verification_hint": step.verification_hint,
                }
                for step in self.steps
            ],
        }

    def prompt_hint(self) -> str:
        if not self.steps:
            return ""
        lines = [
            "# Current Mission Draft",
            "This is a deterministic draft from the user request. Follow it when it matches the user's intent; do not expose it.",
            f"Goal: {self.goal}",
        ]
        for step in self.steps:
            tools = ", ".join(step.suggested_tools) if step.suggested_tools else "none"
            lines.append(f"{step.index}. {_short_text(step.text, 240)} | suggested_tools={tools} | verify={step.verification_hint or 'result evidence'}")
        if self.cleanup_expected:
            lines.append("Cleanup expected: use state(action='cleanup') or targeted close/delete after completing the mission.")
        return "\n".join(lines)


def plan_mission(content: str | list[dict[str, Any]]) -> MissionPlan:
    text = _content_text(content)
    parts = _split_steps(text)
    steps = [
        MissionStep(index=i + 1, text=part, suggested_tools=_suggest_tools(part), verification_hint=_verify_hint(part))
        for i, part in enumerate(parts)
    ]
    cleanup_expected = bool(re.search(r"\b(limpia|limpiar|cleanup|cierra todo lo que abriste|cerrar al final)\b", text, re.IGNORECASE))
    needs_pc_action = any(step.suggested_tools for step in steps)
    if len(steps) == 1 and not needs_pc_action:
        steps = []
    return MissionPlan(goal=text[:500], steps=steps, cleanup_expected=cleanup_expected, needs_pc_action=needs_pc_action)


def select_tool_names(content: str | list[dict[str, Any]], plan: MissionPlan, *, safety_enabled: bool = False) -> list[str]:
    """Return a small, ordered tool subset for the current turn.

    Strategy:
    1. Keyword match (cheap, deterministic, multi-language regex).
    2. If keywords found nothing, fall back to semantic similarity over
       multilingual sentence embeddings (semantic_router.suggest_tools_semantic).
       This covers languages and wordings the regex keywords don't have.
    3. If both came up empty, return [] (or ["safety"] when enabled).
    """
    raw_text = _content_text(content)
    text = _fold_text(raw_text)
    names: list[str] = []
    for step in plan.steps:
        names.extend(step.suggested_tools)
    if not names:
        names.extend(_suggest_tools(text))

    semantic_fallback_used = False
    if not names and raw_text.strip():
        # Skip the fallback for casual / conversational messages where the model
        # should answer directly without tools. Heuristics:
        # - very short (<=3 words) and no question mark.
        # - greeting / smalltalk pattern.
        word_count = len(raw_text.split())
        casual = re.search(
            r"^\s*(hola|hello|hi|hey|hola!|buenos dias|buenas tardes|buenas noches|buen dia|"
            r"good morning|good afternoon|good evening|"
            r"ola|bom dia|boa tarde|boa noite|"
            r"bonjour|bonsoir|salut|"
            r"ciao|buongiorno|buonasera|"
            r"gracias|thanks|thank you|obrigado|merci|grazie|"
            r"que tal|how are you|como estas|como estan|tudo bem|ca va|come stai)\b",
            _fold_text(raw_text),
        )
        if not casual and (word_count > 3 or "?" in raw_text or "¿" in raw_text):
            from .semantic_router import suggest_tools_semantic
            names = suggest_tools_semantic(raw_text, k=12)
            semantic_fallback_used = bool(names)

    if not names:
        return ["safety"] if safety_enabled else []

    expanded: list[str] = []
    for name in _dedupe(names):
        expanded.append(name)
        expanded.extend(_related_tools(name, text))
    if plan.cleanup_expected or re.search(r"\b(cleanup|limpia|limpiar|cierra todo lo que abriste|rollback|restaura|deshacer)\b", text):
        expanded.append("state")
    if safety_enabled:
        expanded.append("safety")
    capped = _cap_tools(_dedupe(expanded), MAX_SELECTED_TOOLS)
    # Stash signal on the function so the agent can record it in traces.
    select_tool_names._last_fallback_used = semantic_fallback_used  # type: ignore[attr-defined]
    return capped


# Default attribute, overwritten on each call.
select_tool_names._last_fallback_used = False  # type: ignore[attr-defined]


def _content_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content.strip()
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return " ".join(chunks).strip()


def _split_steps(text: str) -> list[str]:
    raw_parts = [part.strip(" ,.") for part in STEP_SPLIT_RE.split(text) if part.strip(" ,.")]
    if len(raw_parts) <= 1:
        return [text.strip()] if text.strip() else []
    merged: list[str] = []
    for part in raw_parts:
        if len(part.split()) <= 2 and merged:
            merged[-1] = f"{merged[-1]} {part}".strip()
        else:
            merged.append(part)
    return merged[:8]


def _suggest_tools(step: str) -> list[str]:
    """Keyword-based tool router. Multi-language by lemma-ish keyword groups.

    The folded text drops accents (NFKD + combining strip) so we can match
    "música" and "musica" with the same pattern. Keywords are grouped in 5
    languages (ES, EN, PT, FR, IT) for the most common verbs/nouns. The
    embedding fallback in select_tool_names handles whatever this misses.
    """
    low = _fold_text(step)
    tools: list[str] = []

    # steam (proper noun, identical in all langs)
    if "steam" in low or re.search(r"\b(biblioteca|tienda|library|store|loja|bibliotheque|biblioteca)\b", low):
        tools.append("steam")
    # media: song / video / play / pause
    if re.search(r"\b(youtube|cancion|musica|video|reproduce|ponme|pon|pausa|reanuda|resume|play|stop|siguiente|anterior|"
                 r"music|song|track|playlist|next|previous|skip|pause|"
                 r"musica|cancao|musique|chanson|musica|canzone|"
                 r"jouer|joue|reproduire|riprodurre|riprodurre)\b", low):
        tools.append("media")
    # audio: volume / mute
    if re.search(r"\b(volumen|mute|silencio|audio|sonido|"
                 r"volume|silence|sound|"
                 r"som|silencio|"
                 r"son|silence|"
                 r"volume|silenzio|suono)\b", low):
        tools.append("audio")
    # audio_device
    if re.search(r"\b(dispositivo de audio|salida de audio|entrada de audio|altavoz|altavoces|microfono|"
                 r"focusrite|aux|realtek|hyperx|scarlett|"
                 r"audio device|audio output|audio input|speaker|speakers|microphone|mic|"
                 r"dispositivo de audio|saida de audio|entrada de audio|alto-falante|microfone|"
                 r"sortie audio|entree audio|haut-parleur|micro|"
                 r"dispositivo audio|altoparlante|microfono)\b", low):
        tools.append("audio_device")

    # browser
    if re.search(r"\b(opera|chrome|edge|firefox|youtube|google|navegador|browser|web|pagina|page|url|tab|pestana|"
                 r"website|site|navigateur|onglet|"
                 r"navegador|aba|"
                 r"sito|browser)\b", low):
        tools.append("browser")
        if re.search(r"\b(lee|leer|investiga|investigar|extrae|extraer|contenido|fuente|noticia|actual|"
                     r"read|research|extract|content|source|news|current|latest|"
                     r"ler|pesquisar|conteudo|noticia|atual|"
                     r"lire|rechercher|extraire|contenu|source|nouvelle|actuel|"
                     r"leggere|cercare|estrarre|contenuto|fonte|notizia|attuale)\b", low):
            tools.append("web")
            tools.append("browser_real")
    if re.search(r"\b(investiga|investigar|fuentes|citas|source|snapshot|referencia|guarda fuente|"
                 r"research|cite|citation|reference|save source|"
                 r"pesquisar|fontes|citacao|referencia|"
                 r"rechercher|sources|citation|reference|"
                 r"cercare|fonti|citazione|riferimento)\b", low):
        tools.extend(["web", "source_manager"])

    # filesystem
    if re.search(r"\b(archivo|carpeta|directorio|escribe|crea|borra|copia|mueve|renombra|zip|extrae|descomprime|"
                 r"file|folder|directory|write|create|delete|copy|move|rename|extract|unzip|"
                 r"arquivo|pasta|diretorio|escrever|criar|apagar|copiar|mover|renomear|extrair|"
                 r"fichier|dossier|repertoire|ecrire|creer|supprimer|copier|deplacer|renommer|extraire|"
                 r"file|cartella|directory|scrivere|creare|cancellare|copiare|spostare|rinominare|estrarre)\b", low):
        tools.append("filesystem")
    # office
    if re.search(r"\b(powerpoint|presentacion|diapositiva|pptx|word|docx|excel|xlsx|spreadsheet|hoja de calculo|pdf|"
                 r"presentation|slide|slides|spreadsheet|workbook|sheet|"
                 r"apresentacao|planilha|folha de calculo|"
                 r"presentation|tableur|feuille de calcul|"
                 r"presentazione|foglio di calcolo)\b", low):
        tools.append("office")
    if re.search(r"\b(csv|tabla|grafico|estadistica|analisis de datos|limpia datos|"
                 r"table|chart|graph|statistics|data analysis|clean data|"
                 r"tabela|estatistica|analise de dados|"
                 r"tableau|graphique|statistique|analyse de donnees|"
                 r"tabella|grafico|statistica|analisi dei dati)\b", low):
        tools.extend(["filesystem", "office"])

    # app
    if re.search(r"\b(abre|abrir|cierra|cerrar|app|programa|juego|"
                 r"open|close|launch|quit|exit|program|application|game|"
                 r"abrir|fechar|programa|jogo|"
                 r"ouvrir|fermer|application|programme|jeu|"
                 r"aprire|chiudere|programma|gioco)\b", low) and "steam" not in low:
        tools.append("app")
    # gui/uia/vision: click/type/screen
    if re.search(r"\b(click|clic|teclea|teclear|escribe en pantalla|pantalla|boton|"
                 r"type|screen|button|"
                 r"clique|digitar|tela|botao|"
                 r"clic|cliquer|taper|ecran|bouton|"
                 r"cliccare|digitare|schermo|pulsante)\b", low):
        tools.extend(["uia", "gui", "vision"])
    if re.search(r"\b(registro|registry|regedit)\b", low):
        tools.append("registry")
    if re.search(r"\b(variable de entorno|environment variable|env var|variavel de ambiente|variable d.environnement|variabile d.ambiente|\benv\b)\b", low):
        tools.append("env")
    if re.search(r"\b(descarga|descargar|download|sha256|hash|firma|"
                 r"baixar|baixe|"
                 r"telecharger|"
                 r"scaricare)\b", low):
        tools.append("download")

    if re.search(r"\b(recuerda|recorda|guarda en memoria|memoria|"
                 r"remember|remind me|save to memory|memory|"
                 r"lembra|lembre|salva na memoria|memoria|"
                 r"souviens|memorise|memoire|"
                 r"ricorda|salva in memoria|memoria)\b", low):
        tools.append("memory")
    if re.search(r"\b(documento|rag|conocimiento|knowledge base|base de conocimiento|"
                 r"document|knowledge|"
                 r"documento|conhecimento|base de conhecimento|"
                 r"document|connaissance|base de connaissance|"
                 r"documento|conoscenza|base di conoscenza)\b", low):
        tools.extend(["memory", "knowledge"])
    if re.search(r"\b(dependencia|dependency|libreria|modulo|instala dependencia|falta|missing|"
                 r"dependencia|biblioteca|modulo|faltando|"
                 r"dependance|bibliotheque|module|manquant|"
                 r"dipendenza|libreria|modulo|mancante)\b", low):
        tools.append("dependency")
    if re.search(r"\b(contacto|telefono|email de|correo de|vcard|"
                 r"contact|phone|email of|"
                 r"contato|telefone|email de|"
                 r"contact|telephone|courriel|"
                 r"contatto|telefono|email)\b", low):
        tools.append("contacts")
    if re.search(r"\b(nota|tarea|lista|checklist|pendiente|"
                 r"note|task|todo|"
                 r"nota|tarefa|lista|pendente|"
                 r"note|tache|liste|"
                 r"nota|compito|lista|pendente)\b", low):
        tools.append("notes_tasks")
    if re.search(r"\b(calendario|agenda|evento|ics|"
                 r"calendar|event|"
                 r"calendario|agenda|evento|"
                 r"calendrier|agenda|evenement|"
                 r"calendario|agenda|evento)\b", low):
        tools.append("local_calendar")
    if re.search(r"\b(habito|racha|streak|habit|hobby|costume|"
                 r"habitude|habito|abitudine)\b", low):
        tools.append("habit_tracker")
    if re.search(r"\b(busca en mis archivos|encuentra archivo|buscar archivo|reciente|"
                 r"search files|find file|recent files|"
                 r"buscar arquivo|encontrar arquivo|recente|"
                 r"chercher fichier|trouver fichier|recent|"
                 r"cercare file|trovare file|recente)\b", low):
        tools.append("local_search")
    if re.search(r"\b(impresora|imprime|imprimir|cola de impresion|scanner|escaner|escanear|"
                 r"printer|print|print queue|scan|"
                 r"impressora|imprimir|fila de impressao|escanear|"
                 r"imprimante|imprimer|file d.impression|numeriser|"
                 r"stampante|stampare|coda di stampa|scansionare)\b", low):
        tools.append("printer_scanner")
    if re.search(r"\b(monitor|pantallas|layout|ventanas|escritorio|workspace|"
                 r"monitor|screen|window|desktop|"
                 r"monitor|telas|janelas|area de trabalho|"
                 r"moniteur|ecran|fenetre|bureau|"
                 r"monitor|finestra|scrivania)\b", low):
        tools.append("desktop_layout")
    if re.search(r"\b(backup|respaldo|copia de seguridad|restore|restaurar|dedupe|duplicados|"
                 r"backup|restore|deduplicate|duplicates|"
                 r"backup|copia de seguranca|restaurar|duplicados|"
                 r"sauvegarde|restaurer|doublons|"
                 r"backup|salvataggio|ripristinare|duplicati)\b", low):
        tools.append("backup_sync")
    if re.search(r"\b(timer|temporizador|alarma|avisame|notificacion|recordatorio|"
                 r"alarm|reminder|notify|notification|"
                 r"temporizador|alarme|notificacao|lembrete|"
                 r"minuteur|alarme|notification|rappel|"
                 r"timer|allarme|notifica|promemoria)\b", low):
        tools.append("notification")
    # Routine triggers including phrase-based ("cuando te diga X haz Y"
    # Alexa-style). We accept several common typos for "cuando" / "diga"
    # ("cuanto", "dija", "diega") because users mistype these often.
    if re.search(r"\b(rutina|automatiza|automatizacion|cuando pase|cada vez|"
                 r"cuando te diga|cuando te dija|cuanto te diga|cuanto te dija|"
                 r"cuando le diga|si te digo|si digo|cada vez que diga|"
                 r"si te escribo|cuando escriba|cuando escribas|cuando ponga|"
                 r"quiero que aprietes|quiero que apriete|quiero que presiones|"
                 r"quiero que pulses|quiero que ejecutes|"
                 r"recuerda esto|recuerda lo siguiente|registra esta rutina|"
                 r"routine|automate|automation|whenever|every time|"
                 r"when i say|whenever i say|every time i say|if i say|"
                 r"remember this|save this routine|"
                 r"rotina|automatizar|automacao|quando eu disser|sempre que eu disser|"
                 r"routine|automatiser|automatisation|quand je dis|chaque fois que je dis|"
                 r"routine|automatizzare|automazione|quando dico|ogni volta che dico)\b", low):
        tools.append("routine")
    # Bare phrase-trigger declaration: user describes a future action without
    # using "routine" verbatim. Matches sentences like "que aprietes <key>",
    # "press <key> when i say", "presiona <tecla>". These nudge the keyword
    # router toward `routine` so Gemma sees the tool in the subset.
    if re.search(r"\b(que aprietes|que apriete|que presiones|que pulses|"
                 r"press the .* key|press the .* button|"
                 r"aperte a tecla|appuie sur la touche|premi il tasto)\b", low):
        if "routine" not in tools:
            tools.append("routine")
        # gui covers keypress / hotkey actions the routine will probably
        # invoke as a step.
        for needed in ("gui", "uia"):
            if needed not in tools:
                tools.append(needed)
    # Direct "tecla de" / "media key" requests should also surface gui.
    if re.search(r"\btecla(s)? de\b|\bmedia key\b|\bplay.?pause\b|\bvolume up\b|\bvolume down\b", low):
        if "gui" not in tools:
            tools.append("gui")
    if re.search(r"\b(mail|email|correo|enviar mensaje|"
                 r"send mail|send email|message|"
                 r"correio|enviar mensagem|"
                 r"courriel|envoyer mail|message|"
                 r"posta|inviare email|messaggio)\b", low):
        tools.append("email")
    if re.search(r"\b(recordatorio graph|microsoft todo|to do|todoist|tarea pendiente cloud)\b", low):
        tools.append("reminder")

    if re.search(r"\b(proceso|process|processus|processo|cpu|ram|gpu|disco|disk|disque|bateria|battery|hora|time|tempo|heure)\b", low):
        tools.append("system")
    if re.search(r"\b(portapapeles|clipboard|copiar al portapapeles|pega|paste|"
                 r"area de transferencia|colar|"
                 r"presse-papiers|coller|"
                 r"appunti|incollare)\b", low):
        tools.append("clipboard")
    if re.search(r"\b(terminal|powershell|cmd|comando|ejecuta|"
                 r"shell|command|run|execute|"
                 r"comando|executar|"
                 r"commande|executer|"
                 r"comando|eseguire)\b", low):
        tools.append("terminal")
    if re.search(r"\b(teclado|idioma|layout|language|input method|"
                 r"keyboard|language|"
                 r"teclado|idioma|"
                 r"clavier|langue|"
                 r"tastiera|lingua)\b", low):
        tools.append("input")
    if re.search(r"\b(winget|paquete|instalar app|desinstalar|"
                 r"package|install app|uninstall|"
                 r"pacote|instalar app|desinstalar|"
                 r"paquet|installer app|desinstaller|"
                 r"pacchetto|installare app|disinstallare)\b", low):
        tools.append("package")

    # ---- Tools added in phases C/D/F3 (multi-lang) ----
    # developer: code, tests, lint, git, dev server
    if re.search(r"\b(repositorio|repo|tests|test|pytest|unitarias|lint|format|formato|prettier|black|ruff|eslint|"
                 r"git status|git diff|git log|dev server|servidor de desarrollo|"
                 r"npm run|yarn|pnpm|cargo|go test|build|compile|"
                 r"unit test|coverage|"
                 r"serveur de developpement|"
                 r"servidor de desenvolvimento|"
                 r"servitore di sviluppo)\b", low):
        tools.append("developer")
    # device_settings
    if re.search(r"\b(wifi|wi-fi|red wifi|red inalambrica|ssid|bluetooth|monitor|monitores|display|resolucion|"
                 r"plan de energia|power plan|economizador|alto rendimiento|brillo|brightness|"
                 r"redes sem fio|"
                 r"reseau sans fil|luminosite|"
                 r"reti wireless|luminosita)\b", low):
        tools.append("device_settings")
    # game_launcher
    if re.search(r"\b(epic|epic games|gog|galaxy gog|xbox|xbox app|microsoft store game|riot|league of legends|valorant|battle\.net|battlenet)\b", low):
        tools.append("game_launcher")
    # media_edit
    if re.search(r"\b(recorta|recortar|cortar video|trim|convierte el video|convierte el audio|transcodifica|extrae audio|subtitulos|normaliza audio|miniatura|thumbnail|ffmpeg|"
                 r"crop video|cut video|transcode|extract audio|subtitles|normalize audio|"
                 r"cortar video|recortar video|extrair audio|legendas|"
                 r"couper video|extraire audio|sous-titres|"
                 r"tagliare video|estrarre audio|sottotitoli)\b", low):
        tools.append("media_edit")
    # maintenance
    if re.search(r"\b(windows update|defender|antivirus|escaneo|firewall|event log|visor de eventos|servicio|"
                 r"servicios de windows|punto de restauracion|restore point|disk cleanup|cleanmgr|limpieza de disco|"
                 r"scan|virus|service|services|"
                 r"servico|ponto de restauracao|limpeza de disco|"
                 r"service|point de restauration|nettoyage de disque|"
                 r"servizio|punto di ripristino|pulizia disco)\b", low):
        tools.append("maintenance")
    # watcher
    if re.search(r"\b(vigila|vigilar|monitorea|monitorear|cuando cambie|cuando se modifique|avisame cuando|watcher|"
                 r"watch|monitor|when changes|notify me when|"
                 r"vigiar|monitorar|me avise quando|"
                 r"surveiller|monitorer|previens-moi quand|"
                 r"sorvegliare|monitorare|avvisami quando)\b", low):
        tools.append("watcher")
    # job_manager
    if re.search(r"\b(en segundo plano|background job|tarea larga|corre en paralelo|deja corriendo|job manager|"
                 r"in background|long-running|run in parallel|"
                 r"em segundo plano|tarefa longa|"
                 r"en arriere-plan|tache longue|"
                 r"in background|attivita lunga)\b", low):
        tools.append("job_manager")
    # network
    if re.search(r"\b(ping|hacer ping|traceroute|tracert|dns|resolver dominio|abre el puerto|puerto cerrado|"
                 r"conexiones activas|ip publica|public ip|public_ip|wireshark|"
                 r"resolve domain|port check|active connections|"
                 r"resolver dominio|porta|conexoes ativas|ip publico|"
                 r"resoudre domaine|port|connexions actives|ip publique|"
                 r"risolvere dominio|porta|connessioni attive|ip pubblico)\b", low):
        tools.append("network")
    # data_analysis
    if re.search(r"\b(csv|pandas|describe|histograma|grafica|grafico de dispersion|scatter|plot|distribucion|"
                 r"estadistica descriptiva|histogram|chart|graph|distribution|descriptive statistics|"
                 r"estatistica descritiva|"
                 r"histogramme|graphique|distribution|"
                 r"istogramma|grafico|distribuzione)\b", low):
        tools.append("data_analysis")
    # fact_check
    if re.search(r"\b(verifica|verificar|es cierto|es verdad|fact check|fact-check|contradice|contradicen|respaldan|"
                 r"fuente lo confirma|fuente lo dice|afirmacion|"
                 r"verify|true|false|claim|contradict|support|"
                 r"verificar|verdade|afirmacao|contradiz|"
                 r"verifier|vrai|faux|affirmation|contredire|"
                 r"verificare|vero|falso|affermazione|contraddire)\b", low):
        tools.append("fact_check")
    # photo_library
    if re.search(r"\b(fotos|foto|imagenes del telefono|exif|miniaturas de fotos|organiza fotos|agrupa por fecha|biblioteca de fotos|raw fotos|"
                 r"photos|photo|pictures|images|thumbnail|organize photos|group by date|photo library|"
                 r"fotos|imagens|miniaturas|organizar fotos|biblioteca de fotos|"
                 r"photos|images|miniature|organiser photos|bibliotheque de photos|"
                 r"foto|immagini|miniatura|organizzare foto|libreria foto)\b", low):
        tools.append("photo_library")
    # container
    if re.search(r"\b(docker|contenedor|contenedores|docker-compose|compose up|compose down|imagen docker|"
                 r"container|containers|docker image|"
                 r"contentor|conteiner|imagem docker|"
                 r"contenant|conteneurs|image docker|"
                 r"contenitore|contenitori|immagine docker)\b", low):
        tools.append("container")
    # database
    if re.search(r"\b(sqlite|base de datos|database|postgres|postgresql|mysql|mariadb|select \*|consulta sql|query sql|"
                 r"sql query|"
                 r"banco de dados|consulta sql|"
                 r"base de donnees|requete sql|"
                 r"base di dati|interrogazione sql)\b", low):
        tools.append("database")
    # creative_local
    if re.search(r"\b(comfyui|stable diffusion|genera imagen|generar imagen|sdxl|flux\.1|flux1|workflow de comfyui|prompt para imagen|"
                 r"generate image|create image|image prompt|"
                 r"gerar imagem|criar imagem|"
                 r"generer image|creer image|"
                 r"generare immagine|creare immagine)\b", low):
        tools.append("creative_local")
    # form_filler
    if re.search(r"\b(rellena el formulario|llena el formulario|completa el formulario|envia formulario|submit form|form fill|"
                 r"fill form|fill the form|complete the form|submit the form|"
                 r"preencher formulario|enviar formulario|"
                 r"remplir formulaire|envoyer formulaire|"
                 r"compilare modulo|inviare modulo)\b", low):
        tools.append("form_filler")
        tools.append("browser_real")
    # peripheral
    if re.search(r"\b(usb|controles |controles$|control xbox|gamepad|joystick|joypad|periferico|periferal|joy-con|"
                 r"dualshock|dualsense|administrador de dispositivos|device manager|hid|"
                 r"controllers|controller|peripheral|peripherals|"
                 r"perifericos|gerenciador de dispositivos|"
                 r"manettes|peripheriques|gestionnaire de peripheriques|"
                 r"controlli|periferiche|gestione dispositivi)\b", low):
        tools.append("peripheral")
    # accessibility
    if re.search(r"\b(lupa|magnifier|narrador|narrator|alto contraste|high contrast|accesibilidad|dictado|"
                 r"accessibility|dictation|"
                 r"acessibilidade|narrador|lupa|ditado|"
                 r"accessibilite|loupe|narrateur|dictee|"
                 r"accessibilita|lente|narratore|dettatura)\b", low):
        tools.append("accessibility")
    # study
    if re.search(r"\b(flashcard|flashcards|tarjeta de estudio|repaso espaciado|spaced repetition|anki|deck de estudio|repeticion espaciada|"
                 r"flashcard|study card|spaced rep|deck|"
                 r"cartao de estudo|repeticao espacada|"
                 r"carte d.etude|repetition espacee|"
                 r"carta di studio|ripetizione spaziata)\b", low):
        tools.append("study")
    # smart_home: any (turn|switch|encender|apagar) + (light|luz|lumiere|luce) anywhere wins.
    # Plus brand keywords (home assistant, hass, mqtt, etc).
    _smart_home_action = re.search(
        r"\b(enciende|encender|enciendan|"
        r"apaga|apague|apaguen|apagar|"
        r"prende|prender|prendan|"
        r"acende|acender|"
        r"turn on|turn off|switch on|switch off|"
        r"allumer|allume|allumez|allumes|"
        r"eteindre|eteins|eteint|eteignez|"
        r"accendere|accendi|accendete|"
        r"spegnere|spegni|spegnete)\b",
        low,
    )
    _smart_home_target = re.search(
        r"\b(luz|luces|lampara|lamparas|light|lights|lamp|lamps|"
        r"luz|luzes|lampada|"
        r"lumiere|lumieres|lampe|"
        r"luce|luci|lampada)\b",
        low,
    )
    if (_smart_home_action and _smart_home_target) or re.search(
        r"\b(home assistant|domotica|escena cine|escena de luces|"
        r"termostato|sensor de temperatura|hass|mqtt|persianas|"
        r"smart home|home automation|scene|thermostat|blinds|"
        r"automacao residencial|cena|"
        r"domotique|scene|stores|"
        r"domotica|scena|tapparelle)\b",
        low,
    ):
        tools.append("smart_home")
    # document: (read|extract|summarize verb) + (pdf|docx|xlsx|pptx|html|documento) wins.
    _doc_verb = re.search(
        r"\b(lee|leer|leyendo|lea|leas|"
        r"extrae|extraer|extraigo|extrayendo|"
        r"resume|resumir|resumiendo|resumelo|"
        r"resumi|resuma|resumas|"
        r"parsea|parsear|parseando|"
        r"ocr|escaneado|escaneada|"
        r"read|reading|"
        r"extract|extracting|"
        r"summarize|summarise|summarizing|summarising|"
        r"parse|parsing|"
        r"ler|lendo|leia|"
        r"extrair|extraindo|"
        r"resumir|resumindo|"
        r"lire|lit|lis|lisez|lisant|"
        r"extraire|extrait|extrayant|"
        r"resumer|resumant|"
        r"leggere|leggo|leggi|leggendo|"
        r"estrarre|estraggo|estraendo|"
        r"riassumere|riassumi|riassumendo|riassumilo)\b",
        low,
    )
    _doc_target = re.search(r"\b(pdf|docx|xlsx|pptx|html?|documento|document|documents)\b", low)
    if (_doc_verb and _doc_target) or re.search(
        r"\b(extrae tablas|extract tables|extract_text|"
        r"extrair tabelas|"
        r"extraire tableaux|"
        r"estrarre tabelle)\b",
        low,
    ):
        tools.append("document")
        # "read|extract|summarize <doc>" wins over "office" (which is for creation).
        if "office" in tools:
            tools.remove("office")

    return _dedupe(tools)


def _verify_hint(step: str) -> str:
    low = _fold_text(step)
    if "steam" in low:
        return "steam result, window focus, screenshot if GUI state is unclear"
    if "youtube" in low or "video" in low or "musica" in low:
        return "direct URL plus screenshot; playback may remain unverified"
    if "archivo" in low or "carpeta" in low:
        return "verify(action='file_exists') or filesystem diff/list"
    if "navegador" in low or "google" in low or "web" in low:
        return "browser_real/web content for reading; browser result only for navigation"
    if "cierra" in low or "cerrar" in low:
        return "verify app/window/process no longer exists"
    return "tool status/evidence"


def _related_tools(name: str, text: str) -> list[str]:
    if name == "steam":
        return ["app", "window", "verify"]
    if name == "app":
        return ["window", "verify"]
    if name == "browser":
        related = ["browser_real"] if re.search(r"\b(click|rellena|lee|texto|tab|pestana|descarga)\b", text) else []
        return related + ["verify"]
    if name == "browser_real":
        return ["browser", "web", "state"]
    if name == "web":
        return ["source_manager"]
    if name == "media":
        return ["browser", "audio"]
    if name == "audio_device":
        return ["audio", "state", "dependency"]
    if name in {"filesystem", "registry", "env", "download", "office", "backup_sync"}:
        return ["verify", "state"]
    if name in {"gui", "uia", "vision", "window", "desktop_layout"}:
        return ["gui", "uia", "vision", "window"]
    if name in {"notification", "routine", "contacts", "notes_tasks", "local_calendar", "habit_tracker", "source_manager"}:
        return ["state"]
    if name == "printer_scanner":
        return ["dependency"]
    # ---- Phase C/D/F3 tools ----
    if name == "developer":
        return ["terminal", "filesystem", "verify"]
    if name == "device_settings":
        return ["state", "verify"]
    if name == "game_launcher":
        return ["app", "window", "verify"]
    if name == "media_edit":
        return ["filesystem", "dependency"]
    if name == "maintenance":
        return ["state", "verify"]
    if name == "watcher":
        return ["state"]
    if name == "job_manager":
        return ["state", "terminal"]
    if name == "network":
        return ["state"]
    if name == "data_analysis":
        return ["filesystem", "dependency"]
    if name == "fact_check":
        return ["knowledge", "web", "source_manager"]
    if name == "photo_library":
        return ["filesystem", "dependency"]
    if name == "container":
        return ["terminal", "dependency"]
    if name == "database":
        return ["filesystem"]
    if name == "creative_local":
        return ["filesystem", "dependency"]
    if name == "form_filler":
        return ["browser_real", "state", "safety"]
    if name == "peripheral":
        return ["state"]
    if name == "accessibility":
        return ["state"]
    if name == "study":
        return ["state"]
    if name == "smart_home":
        return ["state", "dependency"]
    if name == "document":
        return ["filesystem", "knowledge", "dependency"]
    return []


_PRIMARY_TOOLS = {
    # Strong domain anchors: keep these high when matched.
    "steam", "media", "browser_real", "browser", "web",
    "office", "document", "knowledge", "fact_check",
    "filesystem", "app", "window", "gui", "uia", "vision",
    "audio", "audio_device",
    "system", "terminal", "clipboard",
    "developer", "device_settings", "game_launcher", "media_edit",
    "maintenance", "network", "data_analysis", "container", "database",
    "photo_library", "creative_local", "form_filler", "peripheral",
    "accessibility", "study", "smart_home",
    "memory", "notification", "routine", "watcher", "job_manager",
    "contacts", "notes_tasks", "local_calendar", "habit_tracker",
    "local_search", "printer_scanner", "desktop_layout", "backup_sync",
    "source_manager", "email", "reminder",
    "registry", "env", "input", "download", "package",
}
_UTILITY_TOOLS = {"verify": 90, "state": 91, "dependency": 92, "safety": 99}


def _cap_tools(names: list[str], limit: int) -> list[str]:
    if len(names) <= limit:
        return names
    # Tier policy:
    # - Primary tools (those that matched a keyword or are a related dep) keep
    #   their original position (so earliest-mentioned wins).
    # - Utility tools (verify/state/dependency/safety) go to the back regardless.
    # - Anything not classified gets a mid-tier slot at 50.
    indexed = list(enumerate(names))
    def rank(pair: tuple[int, str]) -> tuple[int, int]:
        order, name = pair
        if name in _UTILITY_TOOLS:
            return (_UTILITY_TOOLS[name], order)
        if name in _PRIMARY_TOOLS:
            return (order, order)  # original mention order
        return (50, order)
    indexed.sort(key=rank)
    selected = {name for _, name in indexed[:limit]}
    return [name for name in names if name in selected]


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _fold_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _short_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 32].rstrip() + " ...[mission text trimmed]"
