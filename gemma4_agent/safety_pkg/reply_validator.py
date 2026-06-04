"""Post-reply structural validators.

These run after the LLM emits its turn's final reply. If a
structural anti-pattern is detected, the agent injects a
corrective system message into self.history so the NEXT turn's
LLM sees both its previous mistake and the correction note in
the same context window — deferred correction (Gemma4Agent has
no _regen_reply method, so the fix lands on the next turn, not
the current one).

The validators NEVER match user text — only the shape of the
LLM's own reply and the structural tool_call activity this turn.
"""
from __future__ import annotations

import re
from typing import Any


# 'Listo' is the Spanish marker the fast_action prompt teaches
# the LLM to use as a POST-TOOL ack template. The structural
# anti-pattern is "ack template emitted on a turn where no tool
# ran" — the model defaulted to the template even though it
# shouldn't have. We detect the specific phrase the prompt
# teaches, NOT a generic ack across all languages.
_LISTO_PATTERN = re.compile(
    r"^\s*listo(\b|[,.!])",
    re.IGNORECASE,
)


def _result_of(call: Any) -> dict[str, Any]:
    """Read .result from a ToolEvent or a dict — tests use dicts,
    production code uses dataclasses."""
    if isinstance(call, dict):
        return call.get("result") or {}
    r = getattr(call, "result", None)
    return r if isinstance(r, dict) else {}


def _is_successful_call(call: Any) -> bool:
    """Mirror of agent._is_unverified_result inverted; duplicated
    here so reply_validator can stay decoupled from agent.py."""
    r = _result_of(call)
    if r.get("ok") is False:
        return False
    if r.get("verified") is False:
        return False
    status = str(r.get("status") or "").casefold()
    if status in {"failed", "needs_verification", "attempted", "needs_confirmation"}:
        return False
    return True


def is_listo_on_no_tool_turn(
    reply_text: str,
    tool_calls_this_turn: list[Any],
) -> bool:
    """True iff the reply starts with 'Listo' AND no tool ran
    successfully this turn.

    'Listo' is the template the fast_action prompt teaches for
    POST-TOOL acks. Emitting it without a tool is the anti-pattern:
    the model defaults to the ack template even on a turn where no
    tool ran. The prompt teaches the correct usage; this is the
    structural backstop in case it doesn't.
    """
    if not reply_text or not _LISTO_PATTERN.match(reply_text):
        return False
    successful = [c for c in tool_calls_this_turn if _is_successful_call(c)]
    return not successful


LISTO_REGEN_HINT = (
    "Your previous reply started with 'Listo' but no tool ran "
    "in this turn. 'Listo' is reserved for post-tool acks. "
    "Rewrite your reply naturally — for social acks like a "
    "thank-you, use 'de nada', 'no hay de qué', or the equivalent "
    "in the user's language."
)


# ---------------------------------------------------------------------------
# Anti-unverified-claim (guarda estructural). Detecta cuando el reply AFIRMA que
# una acción/estado externo ocurrió ("ya lo abrí", "the window is open", "el
# volumen quedó en 50") SIN que este turno haya corrido una tool VERIFICADA que
# sustente esa afirmación.
#
# CUMPLE las reglas del proyecto:
#  - NO lista de keywords por idioma: la detección de "afirma efecto" es por
#    SIMILITUD SEMÁNTICA contra anclas multi-idioma (mismo encoder del router).
#  - Mide la FORMA + la actividad de tools del turno, nunca inventa contenido.
#  - FALLBACK SEGURO: sin encoder o margen ambiguo -> NO flaggea (jamás molesta
#    en un reply legítimo). Conservador a propósito.
#  - Determinista permitido (CLAUDE.md): embeddings + guarda estructural.
# ---------------------------------------------------------------------------

# Margen mínimo (claim - conv) para considerar que el reply AFIRMA un efecto.
# Medido (9 casos / 4 idiomas): afirmaciones reales caen en +0.25..+0.39;
# preguntas/conversación en <=+0.16. 0.20 separa limpio con margen.
_CLAIM_MARGIN = 0.20

_CLAIM_ANCHORS = [
    # es
    "ya abrí Spotify", "la ventana está abierta", "el volumen quedó en 50",
    "listo, lo cerré", "ya está reproduciendo", "el archivo fue creado",
    # en
    "Spotify is now open", "the file was created", "done, I opened it",
    "I set the volume to 50", "the window is now maximized",
    # pt / fr / de / it
    "pronto, abri o app", "a janela está aberta", "c'est ouvert",
    "fertig, ich habe es geöffnet", "fatto, l'ho aperto",
    # Efecto FÍSICO sobre el mundo (domótica/dispositivos): sin estos anchors el
    # detector (solo de PC) NO reconocía "Listo, bajé la temperatura del termostato"
    # como un claim de éxito FABRICADO. El agente NO controla casa inteligente;
    # afirmar que lo hizo es mentir.
    "listo, prendí las luces", "ya bajé la temperatura del termostato",
    "apagué las luces de la sala", "encendí el aire acondicionado",
    "I turned on the living room lights", "I set the thermostat to 20 degrees",
    "the lights are now on", "done, I turned off the lights",
]
_CONV_ANCHORS = [
    # es
    "¿qué querés que haga?", "no estoy seguro", "¿a cuál te referís?",
    "hola, en qué ayudo", "no tengo esa función", "de nada", "no puedo hacer eso",
    # en
    "what do you want me to do", "I am not sure", "which one did you mean",
    "I don't have that tool",
    # pt / fr / de
    "o que você quer", "je ne suis pas sûr", "ich bin nicht sicher",
]


class _ClaimCentroids:
    __slots__ = ("ready", "claim", "conv")

    def __init__(self) -> None:
        self.ready = False
        self.claim = None
        self.conv = None


_CC = _ClaimCentroids()


def _ensure_claim_centroids() -> bool:
    if _CC.ready:
        return _CC.claim is not None
    try:
        from .. import semantic_router as sr
        if not sr._ensure_loaded():
            _CC.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _CC.claim = _centroid(_CLAIM_ANCHORS)
        _CC.conv = _centroid(_CONV_ANCHORS)
        _CC.ready = True
        return True
    except Exception:
        _CC.ready = True
        return False


def _reply_asserts_effect(reply_text: str) -> bool:
    """True si el reply AFIRMA semánticamente que un efecto externo ocurrió.
    False si no hay encoder (fallback seguro) o si es conversacional/pregunta."""
    txt = (reply_text or "").strip()
    if len(txt) < 4:
        return False
    if not _ensure_claim_centroids() or _CC.claim is None:
        return False  # sin encoder -> no flaggear
    try:
        from .. import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _CC.claim) - float(q @ _CC.conv)) >= _CLAIM_MARGIN
    except Exception:
        return False


def is_unverified_claim(reply_text: str, tool_calls_this_turn: list[Any]) -> bool:
    """True iff el reply AFIRMA un efecto externo PERO ninguna tool verificada
    corrió este turno para sustentarlo. Anti-alucinación de estado.

    Estructural: combina la FORMA del reply (afirma efecto, por embeddings) con
    la actividad real de tools (¿hubo una call exitosa?). Si hubo tool exitosa,
    la afirmación está sustentada -> NO flaggea. Conservador."""
    successful = [c for c in tool_calls_this_turn if _is_successful_call(c)]
    if successful:
        return False  # hubo efecto real -> la afirmación está OK
    return _reply_asserts_effect(reply_text)


UNVERIFIED_CLAIM_REGEN_HINT = (
    "Your previous reply asserted that an action or state happened "
    "(e.g. 'it's open', 'volume is set') but NO tool ran successfully "
    "this turn to make that true. Do NOT claim a side effect you did "
    "not perform. Either call the right tool, or say honestly that you "
    "did not do it / are not sure — in the user's language."
)


# Dominio de cada tool (familias incompatibles). NO es lista de apps: es la
# taxonomía estructural de QUÉ recurso del SO toca cada tool. Acotado a los
# dominios donde se midió el bug (ventana vs archivo, etc.).
_TOOL_DOMAIN = {
    "window": "window", "filesystem": "file", "office": "file",
    "app": "app", "steam": "app", "game_launcher": "app",
    "browser": "web", "browser_real": "web", "web": "web",
    "media": "media", "audio": "audio", "system": "system",
    "notes_tasks": "notes", "memory": "memory", "knowledge": "knowledge",
    "whatsapp": "messaging", "computer_use": "computer_use", "gui": "gui",
    "clipboard": "clipboard", "vision": "vision",
}
# Señal de que el USER pidió una operación de VENTANA (mover/foco/min/max/
# restaurar una ventana). Estructural, multi-idioma, mide la FORMA. Pensado
# para el bug "mueve Notepad a la izquierda" -> filesystem.rename + mentira.
_INTENT_WINDOW_RE = re.compile(
    r"\b(?:mueve|mov[ée]\w*|mover|move|coloca|pon[ée]?)\b[^.]{0,40}\b"
    r"(?:izquierda|derecha|arriba|abajo|left|right|top|bottom|mitad|half|"
    r"lado\s+a\s+lado|side\s+by\s+side)\b"
    r"|\b(?:minimiz|maximiz|restaur|restore|foco|focus|enfoc|"
    r"trae(?:r)?\s+al\s+frente|bring\s+to\s+front)\w*\b"
    # "mover/mové LA VENTANA ..." (ventana explícita) = intención-ventana inequívoca
    r"|\b(?:mueve|mov[ée]\w*|mover|move)\b[^.]{0,15}\bventana\b",
    re.IGNORECASE)
# Afirmación-de-efecto: el detector por embeddings (_reply_asserts_effect) es
# frágil con fraseos compuestos ("moví X y lo renombré"). Para el guard cruzado
# (que YA tiene contexto fuerte: intención-ventana + tool-archivo exitosa), un
# reply que ABRE con un marcador de acción-hecha basta como afirmación. Mide la
# FORMA del inicio del reply, multi-idioma.
_EFFECT_LEAD_RE = re.compile(
    r"^\s*(?:listo|hecho|done|ok|mov[íi]|renombr[ée]|abr[íi]|cerr[ée]|"
    r"hice|cambi[ée]|coloqu[ée]|moved|renamed|i\s+moved)\b",
    re.IGNORECASE)
# Familias-archivo cuyo "éxito" NO sustenta una afirmación de operación-ventana.
_FILE_DOMAINS = {"file"}

INTENT_DOMAIN_MISMATCH_HINT = (
    "Your previous reply claimed you did what the user asked, but the tool that "
    "ran belongs to a DIFFERENT domain than the request. The user asked for a "
    "WINDOW operation (move/focus/minimize a window) and a FILE tool ran instead "
    "(e.g. you renamed a file rather than moving the window). Do NOT claim the "
    "window action succeeded. Use window(...) for window ops, and if you cannot, "
    "say so honestly — in the user's language."
)


def intent_domain_mismatch(
    user_text: str, reply_text: str, tool_calls_this_turn: list[Any]
) -> bool:
    """True iff: el USER pidió una operación de VENTANA, la afirmación del reply
    suena a efecto-hecho, PERO la(s) tool(s) exitosa(s) son de un dominio
    INCOMPATIBLE (archivo) — sin ninguna tool de window. Cierra la mentira
    "moví la ventana y la renombré a X.txt" que pasa porque filesystem.rename
    'tuvo éxito' y el verificador per-tool es ciego a la intención.

    Conservador (gateado por env, default OFF hasta medir): exige (1) señal CLARA
    de intención-ventana en el user_text, (2) el reply afirma efecto, (3) corrió
    ≥1 tool exitosa de dominio-archivo y NINGUNA de window/computer_use/gui (las
    que SÍ podrían mover una ventana). Si window/cu/gui corrió, no flaggea."""
    if not isinstance(user_text, str) or not _INTENT_WINDOW_RE.search(user_text):
        return False
    # afirma efecto: por embeddings O por marcador de acción-hecha al inicio
    # (el embeddings solo es frágil con fraseos compuestos; el contexto ya es
    # fuerte, así que el lead-marker es señal suficiente y robusta).
    if not (_reply_asserts_effect(reply_text)
            or _EFFECT_LEAD_RE.match(reply_text or "")):
        return False
    successful = [c for c in tool_calls_this_turn if _is_successful_call(c)]
    if not successful:
        return False  # ya lo cubre is_unverified_claim
    domains = set()
    for c in successful:
        name = (c.get("name") if isinstance(c, dict) else getattr(c, "name", "")) or ""
        domains.add(_TOOL_DOMAIN.get(str(name).lower(), "other"))
    # Si alguna tool que SÍ puede operar ventanas corrió, no es mismatch.
    if domains & {"window", "computer_use", "gui"}:
        return False
    # Mismatch solo si lo que corrió fue dominio-archivo (la mentira medida).
    return bool(domains & _FILE_DOMAINS)


# Frases-caveat por idioma para apps cuyo lanzamiento NO se pudo confirmar. NO
# es una respuesta enlatada (el LLM YA respondió; esto solo AÑADE honestidad a
# una sobre-afirmación que la propia tool marcó como no confirmada). Se elige por
# el idioma del reply de forma simple (heurística de stopwords), con fallback es.
_LAUNCH_HEDGE = {
    "es": " (puede tardar unos segundos en aparecer; no pude confirmarlo todavía)",
    "en": " (it may take a few seconds to appear; I couldn't confirm it yet)",
    "pt": " (pode demorar alguns segundos a aparecer; ainda não consegui confirmar)",
    "fr": " (cela peut prendre quelques secondes à apparaître ; je n'ai pas encore pu le confirmer)",
    "de": " (es kann ein paar Sekunden dauern, bis es erscheint; ich konnte es noch nicht bestätigen)",
    "it": " (potrebbe metterci qualche secondo ad apparire; non ho ancora potuto confermarlo)",
}


def _launch_unconfirmed(tool_calls_this_turn: list[Any]) -> bool:
    """True si alguna call de lanzamiento de app (app.open / steam / game) corrió
    pero quedó SIN CONFIRMAR (verified=false / completion_status=launch_requested
    / status=attempted). Es la señal honesta de "lo mandé pero no vi la ventana".
    NO incluye fallos duros (ok=false): esos el reply ya los admite."""
    for c in tool_calls_this_turn:
        r = _result_of(c)
        name = (c.get("tool") if isinstance(c, dict) else getattr(c, "name", "")) or ""
        if name not in {"app", "steam", "game_launcher"}:
            continue
        if r.get("ok") is False:
            continue  # fallo duro, no es el caso "lanzado sin confirmar"
        cs = str(r.get("completion_status") or "").casefold()
        if r.get("verified") is False or cs == "launch_requested" \
                or str(r.get("status") or "").casefold() == "attempted":
            return True
    return False


def _guess_lang(text: str) -> str:
    """Heurística mínima de idioma por stopwords frecuentes. Fallback 'es'.
    Solo para elegir la frase-caveat / el idioma de la oferta de Jarvis; NO
    decide intención (eso es por embeddings en el router).

    Evita el falso 'fr' en español: " la " es compartida es/fr (señal pobre) y los
    empates iban al primero del dict (fr antes que es) -> "entra a la pagina de
    youtube" daba 'fr'. Por eso: (a) markers DISCRIMINANTES por idioma (sin tokens
    compartidos ambiguos como " la "), (b) empate -> es (default seguro)."""
    t = f" {text.lower()} "
    # Markers elegidos para DISCRIMINAR, no solo "aparecer". Evitamos " la "/" el "
    # (es+fr+otros). Acentos y formas verbales son la señal fuerte por idioma.
    marks = {
        "en": (" the ", " it ", " open ", " i ", " you ", " is ", " couldn",
               " and ", " what ", " how "),
        "pt": (" não ", " está ", " você ", " segundos", " abrir o ", " fazer ",
               " já ", " obrigado"),
        "fr": (" le ", " ouvre", " peut ", " secondes", " je ", " tu ", " vous ",
               " c'est", " d'", " qu'", " merci", " ferme"),
        "de": (" der ", " die ", " das ", " ich ", " kann ", " sekunden",
               " öffne", " und ", " nicht ", " danke"),
        "it": (" il ", " aprire", " secondi", " sto ", " può ", " grazie",
               " chiudi", " apri "),
        "es": (" entra ", " entrá ", " abrí ", " abrir ", " abre ", " está ",
               " segundos", " página", " pagina ", " busca ", " buscá ",
               " poné ", " pon ", " andá ", " cerrá ", " hola ", " gracias",
               " qué ", " cómo ", " y ", " de ", " a la ", " el ", " un "),
    }
    best, score = "es", 0
    for lang, toks in marks.items():
        s = sum(1 for tk in toks if tk in t)
        # empate NO desplaza al actual -> 'es' (procesado primero como default)
        # gana los empates. Sólo un score ESTRICTAMENTE mayor cambia el ganador.
        if s > score:
            best, score = lang, s
    return best


def soften_unverified_launch(reply_text: str, tool_calls_this_turn: list[Any]) -> str:
    """Si el reply AFIRMA haber abierto/completado algo pero la tool de
    lanzamiento quedó SIN CONFIRMAR, añade un caveat honesto en el idioma del
    reply. Cierra el falso-PASS donde el 4B dice "abrí Discord" aunque app.open
    devolvió verified=false (Discord/Squirrel tarda >ventana de verificación).

    Determinista y estructural: actúa por la FORMA (afirma efecto) + el ESTADO de
    la tool (no confirmada), no por contenido por-app/idioma. Si el reply ya
    admite duda o no afirma efecto, lo deja igual. Idempotente."""
    if not reply_text or not reply_text.strip():
        return reply_text
    if not _launch_unconfirmed(tool_calls_this_turn):
        return reply_text
    if not _reply_asserts_effect(reply_text):
        return reply_text  # el reply no afirma un efecto -> nada que suavizar
    low = reply_text.lower()
    # ya hedgea (evita doble caveat / idempotencia)
    if any(k in low for k in ("puede tardar", "no pude confirmar", "couldn't confirm",
                              "may take", "no consegui", "pas encore", "bestätigen",
                              "confermarlo", "unos segundos", "few seconds")):
        return reply_text
    lang = _guess_lang(reply_text)
    return reply_text.rstrip() + _LAUNCH_HEDGE.get(lang, _LAUNCH_HEDGE["es"])


# ---------------------------------------------------------------------------
# Anti-"pedir input manual" (MODO MOVILIDAD). En modo movilidad el usuario NO
# puede usar teclado/mouse: el agente debe ACTUAR por él, nunca pedirle que toque
# algo. Esta guarda estructural detecta cuando el reply le INSTRUYE al usuario una
# acción MANUAL ("hacé clic en...", "apretá Enter", "escribí tu contraseña",
# "andá a Configuración y tocá..."). Solo se evalúa cuando el modo movilidad está
# activo (el caller lo gatea) — nunca afecta a normal/no_vidente.
#
# CUMPLE las reglas (igual que _reply_asserts_effect):
#  - NO keywords por idioma: detección por SIMILITUD SEMÁNTICA contra anclas
#    multi-idioma (mismo encoder del router).
#  - Mide la FORMA del reply del LLM, nunca el texto del usuario.
#  - FALLBACK SEGURO: sin encoder o margen ambiguo -> NO flaggea.
# ---------------------------------------------------------------------------

# Margen mínimo (manual - ok) para considerar que el reply PIDE input manual.
# CONSERVADOR a propósito (CLAUDE.md §3): preferimos un falso-NEGATIVO ocasional
# (una instrucción manual que se cuela) antes que un falso-POSITIVO (regen
# espurio sobre un reply legítimo, p.ej. una pregunta aclaratoria). El system_hint
# de movilidad es la defensa primaria; esta guarda es el backstop estructural.
# Medido (encoder real, 14 casos): 13/14, 0 falsos-positivos.
_HANDS_FREE_MARGIN = float(__import__("os").environ.get("GEMMA4_HANDS_FREE_MARGIN", "0.15"))

# Anclas "pedile al usuario que haga una acción MANUAL en pantalla".
_MANUAL_INSTRUCTION_ANCHORS = [
    # es
    "hacé clic en el botón aceptar", "apretá la tecla enter",
    "escribí tu contraseña en el campo", "andá a configuración y tocá guardar",
    "presioná el botón de la esquina", "hacé doble clic en el ícono",
    "seleccioná la opción con el mouse",
    # en
    "click the OK button", "press the enter key",
    "type your password in the field", "go to settings and tap save",
    "double click the icon", "select the option with your mouse",
    # pt / fr / de / it
    "clique no botão", "pressione a tecla enter",
    "cliquez sur le bouton", "appuyez sur la touche entrée",
    "klicken sie auf die schaltfläche", "drücken sie die eingabetaste",
    "fai clic sul pulsante", "premi il tasto invio",
]
# Anclas "el agente lo hace por el usuario", "pregunta qué hacer" o "pide que el
# usuario DIGA un dato por voz" (todo OK en manos libres — NO pide acción manual).
_AGENT_ACTS_ANCHORS = [
    # es — agente actúa / pregunta
    "ya lo hice por vos", "lo abro yo ahora", "lo hago por vos",
    "¿querés que lo haga?", "¿a cuál te referís?", "listo, lo cerré",
    "te lo dejo abierto", "decime qué necesitás",
    # es — pedir un dato HABLADO (válido: el usuario lo dice, no lo escribe)
    "decime el nombre y lo busco yo", "¿con qué otro nombre lo probamos?",
    "decime qué querés y lo hago", "no la encontré, ¿cómo se llama?",
    # en
    "I did it for you", "I'll open it now", "I'll handle it",
    "do you want me to do it", "which one did you mean", "done, I closed it",
    "tell me the name and I'll search it", "couldn't find it, what's it called",
    # pt / fr / de / it
    "eu faço por você", "je le fais pour toi",
    "ich mache es für dich", "lo faccio io per te",
]


class _HandsFreeCentroids:
    __slots__ = ("ready", "manual", "ok")

    def __init__(self) -> None:
        self.ready = False
        self.manual = None
        self.ok = None


_HF = _HandsFreeCentroids()


def _ensure_hands_free_centroids() -> bool:
    if _HF.ready:
        return _HF.manual is not None
    try:
        from .. import semantic_router as sr
        if not sr._ensure_loaded():
            _HF.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _HF.manual = _centroid(_MANUAL_INSTRUCTION_ANCHORS)
        _HF.ok = _centroid(_AGENT_ACTS_ANCHORS)
        _HF.ready = True
        return True
    except Exception:
        _HF.ready = True
        return False


def asks_user_manual_action(reply_text: str) -> bool:
    """True si el reply le PIDE al usuario una acción MANUAL (clic/tecla/typeo).
    False si no hay encoder (fallback seguro) o si el agente actúa / pregunta.

    Estructural y multilingüe. El CALLER debe gatear esto a modo movilidad: en
    otros modos pedirle al usuario que haga clic es perfectamente válido."""
    txt = (reply_text or "").strip()
    if len(txt) < 4:
        return False
    if not _ensure_hands_free_centroids() or _HF.manual is None:
        return False
    try:
        from .. import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _HF.manual) - float(q @ _HF.ok)) >= _HANDS_FREE_MARGIN
    except Exception:
        return False


HANDS_FREE_REGEN_HINT = (
    "MOVILIDAD: tu respuesta le pidió al usuario que hiciera una acción manual "
    "(hacer clic, apretar una tecla, escribir). En este modo el usuario NO "
    "puede usar teclado ni mouse. NO le pidas que toque nada: ejecutá vos la "
    "acción con las herramientas de control del PC (computer_use / gui / uia). "
    "Si de verdad necesitás un dato suyo, pedíselo para que lo DIGA por voz, no "
    "para que lo escriba. Reescribí tu respuesta en el idioma del usuario."
)


# ---------------------------------------------------------------------------
# Anti-DELEGACIÓN / tarea-abandonada-a-medias (MOVILIDAD + NO VIDENTE).
# Patrón: en movilidad, "comprá X en Instant Gaming" -> el agente hace UN paso
# (búsqueda en Google) y responde "revisá los resultados para ver el precio". Eso
# NO es pedir un clic explícito (la guarda hands-free no lo atrapa) pero le PASA
# la tarea al usuario — que en movilidad/no_vidente no puede revisar/elegir/
# clickear. Esta guarda detecta cuando el reply DELEGA la continuación de la tarea
# en el usuario (revisá/fijate/elegí cuál/mirá la pantalla y decidí) en vez de
# seguir actuando hasta completar o trabarse.
#
# Estructural y multilingüe (embeddings). Distingue DELEGAR (malo) de: el agente
# YA terminó, el agente pregunta un dato puntual por voz, o el agente avisa
# HONESTAMENTE que se trabó (eso último es válido por decisión de producto:
# avanzar lo más posible + avisar).
# ---------------------------------------------------------------------------
_DELEGATE_MARGIN = float(__import__("os").environ.get("GEMMA4_DELEGATE_MARGIN", "0.10"))

_DELEGATE_ANCHORS = [
    # es — le pasa la tarea al usuario para que revise/elija/decida/mire (UNIVERSAL,
    # no solo compras: archivos, configuración, listas, resultados, lo que sea)
    "revisá los resultados y elegí cuál querés", "fijate en la pantalla cuál te sirve",
    "mirá las opciones y decidí cuál comprar", "elegí vos el que prefieras",
    "revisá la lista y avisame cuál", "ahí tenés los resultados, mirálos",
    "decidí vos cuál de estos", "mirá la pantalla y decidí qué hacer",
    "fijate en la configuración cuál opción activar", "elegí el archivo que quieras abrir",
    "revisá las opciones de ajustes y seleccioná", "mirá vos cuál te conviene",
    "verificá si querés que abra el enlace", "verifica si queres que abra el enlace",
    "decime si querés que abra el resultado",
    "avisame si querés que abra el link directo", "confirmame si querés que lo abra",
    # en
    "review the results and pick the one you want", "look at the screen and choose",
    "check the options and decide which to buy", "pick whichever you prefer",
    "look at the screen and decide what to do", "choose the file you want to open",
    "check the settings and pick an option",
    "tell me if you want me to open the link",
    "let me know if you want me to open the result",
    "should I open the direct link for you",
    # pt / fr / de / it
    "veja os resultados e escolha", "regarde les résultats et choisis",
    "schau dir die ergebnisse an und wähle", "guarda i risultati e scegli",
]
_PROCEED_OR_DONE_ANCHORS = [
    # es — el agente ACTÚA / terminó / pregunta por voz / avisa honesto del límite
    "ya lo abrí y lo dejé listo", "lo agrego al carrito ahora",
    "abrí la página del juego, sigo con la compra", "¿confirmás la compra? sí o no",
    "confirmás esta acción de pago sí o no", "necesito confirmación hablada para pagar",
    "llegué hasta el pago, ahí me detengo", "me trabé en este paso, no pude seguir",
    "decime el título exacto y lo busco yo", "lo estoy comprando por vos",
    # en
    "I opened it and it's ready", "I'm adding it to the cart now",
    "I opened the game page, continuing with the purchase",
    "do you confirm the purchase yes or no", "confirm this paid action yes or no",
    "I got stuck on this step",
    # pt / fr / de / it
    "abri a página e continuo", "j'ai ouvert la page et je continue",
    "ich habe es geöffnet und mache weiter", "ho aperto la pagina e continuo",
]


class _DelegateCentroids:
    __slots__ = ("ready", "delegate", "proceed")

    def __init__(self) -> None:
        self.ready = False
        self.delegate = None
        self.proceed = None


_DG = _DelegateCentroids()


def _ensure_delegate_centroids() -> bool:
    if _DG.ready:
        return _DG.delegate is not None
    try:
        from .. import semantic_router as sr
        if not sr._ensure_loaded():
            _DG.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _DG.delegate = _centroid(_DELEGATE_ANCHORS)
        _DG.proceed = _centroid(_PROCEED_OR_DONE_ANCHORS)
        _DG.ready = True
        return True
    except Exception:
        _DG.ready = True
        return False


def reply_delegates_task(reply_text: str) -> bool:
    """True si el reply DELEGA la continuación de la tarea en el usuario
    (revisá/elegí/fijate y decidí), en vez de actuar o avisar honesto del
    límite. Multilingüe, por embeddings. El caller lo gatea a movilidad/
    no_vidente. Fallback seguro: sin encoder -> False."""
    txt = (reply_text or "").strip()
    if len(txt) < 4:
        return False
    if not _ensure_delegate_centroids() or _DG.delegate is None:
        return False
    try:
        from .. import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _DG.delegate) - float(q @ _DG.proceed)) >= _DELEGATE_MARGIN
    except Exception:
        return False


DELEGATE_REGEN_HINT = (
    "ACCESIBILIDAD: tu respuesta le pasó la tarea al usuario ('revisá los "
    "resultados', 'elegí cuál', 'fijate en la pantalla'). En este modo el "
    "usuario NO puede revisar ni elegir con mouse/teclado, y puede que no vea la "
    "pantalla. NO delegues: SEGUÍ actuando vos hasta completar la tarea — "
    "capturá la pantalla con la tool vision (describe_screen/ocr) si necesitás "
    "leer los resultados, abrí el resultado correcto vos mismo con gui/uia/"
    "computer_use, y avanzá al siguiente paso. Si de verdad te trabás en un "
    "paso, decílo con honestidad ('llegué "
    "hasta acá, me trabé en X') — pero NUNCA le pidas al usuario que revise o "
    "elija algo en pantalla. Reescribí tu respuesta en el idioma del usuario."
)


# ---------------------------------------------------------------------------
# Anti-respuesta-muda (MODO NO VIDENTE). Un usuario que no ve necesita que
# el resultado de una acción se le DIGA: una respuesta como "Listo." tras abrir
# una app no le informa NADA (no ve la ventana). Esta guarda detecta el caso
# estructural "corrió una tool con éxito PERO el reply es demasiado escueto para
# informar a alguien que no ve" y pide una confirmación descriptiva hablada.
#
# Es ESTRUCTURAL (no keywords de contenido): combina (a) hubo tool exitosa este
# turno, con (b) el reply es muy corto o es el ack-template 'Listo'. No mira el
# significado del reply, solo su forma + la actividad de tools. El CALLER lo
# gatea a modo no_vidente (en otros modos un "Listo." es perfectamente válido).
# ---------------------------------------------------------------------------

# Umbral de "demasiado escueto" para un usuario no vidente, en caracteres. Una
# confirmación informativa ("Abrí Spotify y está sonando tu lista de Favoritos")
# supera esto cómodo; un "Listo." / "Hecho." / "Ok" no. Conservador.
_TERSE_REPLY_MAX_CHARS = int(__import__("os").environ.get("GEMMA4_NARRATE_MIN_CHARS", "40"))


def reply_too_terse_for_blind(reply_text: str, tool_calls_this_turn: list[Any]) -> bool:
    """True iff corrió una tool con éxito este turno PERO el reply es demasiado
    escueto para informar a alguien que no ve (muy corto, o un ack 'Listo' pelado).

    Estructural: tool-éxito + forma del reply (longitud / ack-template). No mira
    el contenido semántico. El caller debe gatearlo a modo no_vidente."""
    successful = [c for c in tool_calls_this_turn if _is_successful_call(c)]
    if not successful:
        return False  # no hubo acción que narrar -> nada que exigir
    txt = (reply_text or "").strip()
    if not txt:
        return True  # reply vacío tras una acción: mudo total
    # ack-template pelado ("Listo.", "Listo, abrí X" con X muy corto) o reply
    # demasiado corto en general -> no informa a quien no ve.
    if len(txt) <= _TERSE_REPLY_MAX_CHARS:
        return True
    return False


NARRATE_ACTION_REGEN_HINT = (
    "NO VIDENTE: ejecutaste una acción pero tu respuesta es demasiado escueta. "
    "El usuario NO VE la pantalla, así que un 'Listo' no le dice nada. Describí "
    "en una o dos frases QUÉ hiciste y cuál es el estado resultante observable "
    "(qué app/ventana quedó al frente, qué está pasando ahora), en el idioma del "
    "usuario. Sé concreto pero breve; no inventes detalles que no puedas verificar."
)
