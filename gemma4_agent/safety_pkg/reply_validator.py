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

import json
import re
import os
from typing import Any


def _validator_cold_load_enabled() -> bool:
    raw = (
        os.environ.get("GEMMA4_REPLY_VALIDATOR_COLD_LOAD")
        or os.environ.get("GEMMA4_SEMANTIC_COLD_LOAD")
        or "0"
    ).strip().casefold()
    return raw in {"1", "true", "yes", "on"}


def _semantic_ready_for_validator(sr: Any) -> bool:
    try:
        return bool(sr.status().get("model_loaded")) or _validator_cold_load_enabled()
    except Exception:
        return _validator_cold_load_enabled()


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
#  - Determinista permitido: embeddings + guarda estructural.
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
        if not _semantic_ready_for_validator(sr):
            return False
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
# Señal de que el comando es una operación de VENTANA (mover/foco/min/max/
# restaurar una ventana). Estructural, multi-idioma, mide la FORMA. Pensado
# para el bug "mueve Notepad a la izquierda" -> filesystem.rename + mentira.
_INTENT_WINDOW_RE = re.compile(
    r"\b(?:mueve|mov[ée]\w*|mover|move|coloca|pon[ée]?)\b[^.]{0,40}\b"
    r"(?:izquierda|derecha|arriba|abajo|left|right|top|bottom|mitad|half|"
    r"lado\s+a\s+lado|side\s+by\s+side)\b"
    # verbos de control-de-ventana inequívocos. NO incluye restaur/restore en el
    # set genérico: "restore" matcheaba paths como "sandbox/restore_test" (falso+
    # MEDIDO en el dataset, 2 turnos). minimiz/maximiz/foco/enfoc no colisionan
    # con paths comunes. Seguidos de \b (no \w* que comería "_test").
    r"|\b(?:minimiz\w*|maximiz\w*|enfoc\w*|trae(?:r)?\s+al\s+frente|"
    r"bring\s+to\s+front)\b"
    r"|\b(?:foco|focus)\b"
    # restaurar/restore SOLO si menciona ventana explícita (no paths con 'restore')
    r"|\b(?:restaur\w*|restore)\b[^.]{0,20}\bventana\b"
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


# Plataformas de streaming que el reply puede nombrar legítimamente SOLO si el
# usuario las pidió o el tool las devolvió. El bug medido: ante CUALQUIER pedido de
# media (o ruido), el 4B rellena "Stranger Things está reproduciéndose en Netflix"
# — título Y plataforma FABRICADOS. 35 casos en la tanda 1.
_STREAMING_PLATFORMS = ("netflix", "spotify", "youtube", "disney", "hbo", "max",
                        "prime video", "apple music", "twitch")
# (A) marcador estructural de REPRODUCCIÓN-EN-CURSO. El guard solo aplica si el reply
# AFIRMA estar reproduciendo/pausando contenido; no si solo "abrí/encontré la app",
# resume una preferencia, ofrece o pregunta. FP medido (auditoría adversarial t1-t5):
# Jarvis "las apps que usás: Spotify", "abrí Spotify", "¿querés que lo reproduzca?".
_NOW_PLAYING_RE = re.compile(
    r"\b(?:reproduci[ée]ndo\w*|reproduzco|reproduje|reproducimos|reanud\w*|"
    r"comenc[ée]\s+a\s+reproducir|empec[ée]\s+a\s+reproducir|"
    r"playing|now\s+playing|started\s+playing|en\s+pausa|se\s+paus[óo]|paused|sonando|"
    r"puse\s+\w+|estoy\s+(?:viendo|reproduciendo|poniendo)|"
    r"est[áa]\s+(?:reproduci[ée]ndose|sonando|en\s+pantalla))\b",
    re.IGNORECASE)


def media_fabricated_claim(
    user_text: str, reply_text: str, tool_calls_this_turn: list[Any]
) -> bool:
    """True iff el reply AFIRMA estar reproduciendo un TÍTULO/PLATAFORMA de streaming
    que NO está en el pedido del usuario NI sustentado por ninguna tool real.
    Honestidad estructural: el reply no puede nombrar contenido que no se verificó.

    Endurecido tras auditoría adversarial (cacería t1-t5):
    (A) solo aplica si el reply afirma REPRODUCCIÓN-EN-CURSO (_NOW_PLAYING_RE). "Abrí
        Spotify" / "¿querés que reproduzca?" / "las apps que usás: Spotify" NO son
        claims de now-playing -> no flaggear.
    (B) la plataforma está GROUNDED si aparece en el user, o en los args/result/URL de
        CUALQUIER tool que la tocó (app.name, audio_device.app, browser.url,
        media.args.app, o un result NO-VACÍO de media) -> no flaggear.
    (C) NO confiar en media.args.provider/query AUTO-FABRICADOS por el 4B: si el result
        de media vino vacío (mock) y la plataforma solo está en esos args, ES
        fabricación (recupera el caso canónico "7.63" -> "Stranger Things en Netflix").
    """
    rt = (reply_text or "").lower()
    ut = (user_text or "").lower()
    # (A) ¿el reply afirma reproducción-en-curso? Si no, no es media-fabrication.
    if not _NOW_PLAYING_RE.search(rt):
        return False
    # plataforma nombrada en el reply que el user NO pidió
    fabricated_platform = next(
        (p for p in _STREAMING_PLATFORMS if p in rt and p not in ut), None)
    if not fabricated_platform:
        return False
    # (B)+(C) ¿alguna tool REAL sustenta esa plataforma?
    for c in tool_calls_this_turn:
        name = str((c.get("name") if isinstance(c, dict)
                    else getattr(c, "name", "")) or "").lower()
        args = (c.get("args", {}) if isinstance(c, dict)
                else getattr(c, "args", {})) or {}
        res = _result_of(c)
        grounded = ""
        if name == "media":
            # (C) SOLO el result no-vacío de media cuenta como grounding. NINGÚN arg de
            # media (provider/query/app) lo hace: el 4B los AUTO-FABRICA enteros
            # (medido: ante "7.63" emite media{app:netflix,query:Stranger Things}). Bajo
            # el mock el result viene vacío -> nada grounnd-ea -> se atrapa la
            # fabricación. En prod un media.play real devuelve title/platform en result.
            grounded = (str(res.get("title", "")) + " " + str(res.get("platform", ""))
                        + " " + str(res.get("provider", "")) + " "
                        + str(res.get("now_playing", ""))).lower()
        elif name in ("app", "application"):
            grounded = (str(args.get("name", "")) + " " + str(args.get("target", "")) + " "
                        + str(args.get("app", ""))).lower()
        elif name in ("audio_device", "audio"):
            grounded = (str(args.get("app", "")) + " " + str(args.get("application", "")) + " "
                        + str(res.get("app", ""))).lower()
        elif name in ("browser", "browser_real"):
            grounded = (str(args.get("url", "")) + " " + str(args.get("query", "")) + " "
                        + str(res.get("url", ""))).lower()
        elif name in ("gui", "window", "uia", "vision"):
            # localizar/enfocar la ventana de una app de streaming la grounnd-ea
            grounded = (str(args.get("title", "")) + " " + str(args.get("window", "")) + " "
                        + str(res.get("title", ""))).lower()
        if fabricated_platform in grounded:
            return False  # una tool REAL tocó esa plataforma -> no fabricado
    return True


# REPARACIÓN INLINE de media-fabricado (cacería tanda 2-5, ~25-30 casos POR TANDA):
# el 4B tiene un PRIOR degenerado fortísimo a emitir "Stranger Things está
# reproduciéndose en Netflix" ante CUALQUIER pedido de media sin título (o ruido).
# El guard media_fabricated_claim lo DETECTA e inyecta un hint diferido, pero el 4B
# reincide turno a turno. Para este caso de alta frecuencia y bajo riesgo, REPARAMOS
# el reply en el acto.
#
# Decisión de diseño: NO editamos la cláusula in-place. Un regex que recorta "el
# título y la plataforma" del medio de la oración deja fragmentos garbleados
# ("...puse lo que pedistetranger Things on Netflix") porque el título es texto
# arbitrario sin límites claros. En vez de eso, REEMPLAZAMOS EL REPLY ENTERO por un
# acuse honesto y genérico. Es lossless en intención (el único contenido del reply
# fabricado ERA la afirmación falsa) y no puede corromper texto. Mismo criterio que
# los otros guards inline que reescriben el reply completo (_guard_unverified_final).
# Estructural: solo se llama cuando media_fabricated_claim ya confirmó la fabricación.
MEDIA_FAB_REPAIR_REPLY = "Listo, puse lo que pediste."


def repair_media_fabricated(reply_text: str) -> str:
    """Devuelve un acuse honesto y genérico en reemplazo del reply con título/
    plataforma fabricados. Llamar SOLO cuando media_fabricated_claim devolvió True."""
    return MEDIA_FAB_REPAIR_REPLY


# El reply afirma un CLICK ("cliqueé/presioné/apreté X", "I clicked/pressed X") que
# requiere una tool de click real. BUG medido (tanda 1, A3): "cliqueé el botón
# Comprar" con solo uia.find/vision.find (que LOCALIZAN, no clickean) -> claim de
# acción no ejecutada. Las tools que SÍ clickean: gui (click/click_button/keypress),
# uia (invoke), computer_use. find/locate/tree NO clickean.
# Claim del AGENTE = verbo de click en 1ª persona PRETÉRITO (cliqueé/presioné/
# apreté/toqué/hice clic). NO la 2ª persona/subjuntivo ("hasta que la presiones",
# "cliqueá vos") que refiere a una acción del USUARIO, no del agente (falso+
# medido: "apagué... hasta que la presiones de nuevo").
_CLICK_CLAIM_RE = re.compile(
    r"\b(?:clique[é]\b|cliqu[ée]é\b|click[eé]é\b|presion[é]\b|apret[é]\b|"
    r"toqu[é]\b|seleccion[é]\b|hice\s+clic\w*|hice\s+click\w*|"
    r"i\s+clicked|i\s+pressed|i\s+tapped|\bclicked\b|\bpressed\b"
    # multilingüe 1ª persona pretérito (FORM, no contenido). FN medido (auditoría
    # adversarial t1-t5: i=4573 PT "cliquei no botão OK"). PT/IT/FR.
    r"|cliquei\b|apertei\b|toquei\b|carreguei\b|premi\b|selecionei\b"  # PT
    r"|cliccai\b|premetti\b|ho\s+clicc\w*|ho\s+premut\w*"             # IT
    r"|j'?ai\s+cliqu\w*|j'?ai\s+appuy\w*|cliqu[ée]\s+sur"             # FR
    r")",
    re.IGNORECASE)
# tools (con su action) que REALMENTE producen un click/efecto sobre un control.
_CLICK_CAPABLE = {
    ("gui", "click"), ("gui", "double_click"), ("gui", "right_click"),
    ("gui", "click_button"), ("gui", "click_text"), ("gui", "keypress"),
    ("gui", "hotkey"), ("gui", "type"), ("gui", "type_into"),
    ("uia", "invoke"), ("uia", "click"), ("computer_use", None),
    ("browser_real", None), ("input", None),
}


_CLICK_NEGATED_RE = re.compile(
    # negación ANTES del verbo de click ("no lo cliqueé")
    r"\b(?:no|sin|not|n't|didn|couldn|pero no|but)\b[^.]{0,20}"
    r"(?:clique[ée]\w*|cliqu[ée]\w*|click\w*|presion[ée]\w*|apret[ée]\w*|toqu[ée]\w*)"
    # o negación DESPUÉS ("clickear X no se ejecutó/no se pudo/no se encontró/falló")
    r"|(?:clic\w*|click\w*|presion\w*|apret\w*|toqu\w*)[^.]{0,40}"
    r"\b(?:no\s+se\s+(?:ejecut|pudo|realiz|complet|encontr)\w*|"
    r"no\s+(?:pude|pudo|se\s+pudo)|fall[óo]|wasn'?t|couldn'?t|did\s+not)\b",
    re.IGNORECASE)


def click_claim_without_click(reply_text: str, tool_calls_this_turn: list[Any]) -> bool:
    """True iff el reply afirma haber CLICKEADO/presionado un control PERO ninguna
    tool capaz de click corrió. uia.find/vision.find LOCALIZAN, no clickean ->
    afirmar el click es fabricar la acción."""
    if not _CLICK_CLAIM_RE.search(reply_text or ""):
        return False
    # NEGACIÓN: "no lo cliqueé" / "localicé pero no cliqueé" = honesto, NO es claim.
    if _CLICK_NEGATED_RE.search(reply_text or ""):
        return False
    for c in tool_calls_this_turn:
        if not _is_successful_call(c):
            continue
        name = (c.get("name") if isinstance(c, dict) else getattr(c, "name", "")) or ""
        args = c.get("args", {}) if isinstance(c, dict) else (getattr(c, "args", {}) or {})
        action = str((args or {}).get("action") or "").lower()
        name = str(name).lower()
        if (name, action) in _CLICK_CAPABLE or (name, None) in _CLICK_CAPABLE:
            return False  # sí corrió una tool de click -> el claim está sustentado
    return True


# El reply afirma que los TESTS PASARON / fueron exitosos / verificado. BUG medido
# (tanda 1, A2): "corrí los tests y todos pasaron" sin que el ToolResult traiga el
# conteo pass/fail real. nunca declarar éxito sin un número.
_TESTS_PASSED_RE = re.compile(
    r"\b(?:tests?|pruebas?|pytest)\b[^.]{0,40}"
    r"\b(?:pasaron|pasar[oó]n|exitos\w*|verificad\w*|ok\b|todos?\s+(?:bien|verde)|"
    r"sin\s+(?:fallos?|errores?)|all\s+pass\w*|passed|succeeded)\b"
    r"|\b(?:todos?\s+(?:los\s+)?tests?|all\s+tests?)\b[^.]{0,20}"
    r"\b(?:pasaron|passed|ok|verde)\b",
    re.IGNORECASE)
# tools de testing cuyo result DEBE traer evidencia de conteo para sustentar el claim.
_TEST_TOOLS = {"developer", "terminal"}


def tests_passed_without_evidence(reply_text: str, tool_calls_this_turn: list[Any]) -> bool:
    """True iff el reply afirma que los tests PASARON pero el ToolResult de la tool
    de testing NO trae evidencia de conteo (pass/fail, exit-code, recuento). No se
    puede declarar éxito de tests sin el número real."""
    if not _TESTS_PASSED_RE.search(reply_text or ""):
        return False
    for c in tool_calls_this_turn:
        name = (c.get("name") if isinstance(c, dict) else getattr(c, "name", "")) or ""
        if str(name).lower() not in _TEST_TOOLS:
            continue
        res = _result_of(c)
        # evidencia válida: el result trae conteo estructurado (claves passed/failed/
        # exit_code con un número) O el output crudo con "N passed/failed".
        if isinstance(res, dict):
            for k in ("passed", "failed", "exit_code", "returncode", "tests_run", "count"):
                v = res.get(k)
                if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
                    return False  # conteo estructurado real -> sustentado
        blob = " ".join(str(res.get(k, "")) for k in
                        ("output", "stdout", "summary", "result", "text")).lower()
        if re.search(r"\b\d+\s*(?:passed|pass|failed|fail|test)|exit[_\s]?code|"
                     r"\bpassed\b|\bfailed\b|\d+\s*/\s*\d+", blob):
            return False  # output crudo con números pass/fail -> sustentado
    return True  # afirmó pasaron pero ninguna tool de test trajo el número


TESTS_PASSED_HINT = (
    "Your previous reply claimed the tests passed / succeeded, but the test tool's "
    "result did NOT include a real pass/fail count or exit code. Do NOT claim tests "
    "passed without the actual numbers. Report the real result (e.g. 'N passed, M "
    "failed'), or say you ran them but could not read the outcome — never fabricate "
    "a green run — in the user's language."
)


# El reply afirma haber EJECUTADO una acción DESTRUCTIVA/de-seguridad y, encima,
# haberla VERIFICADO, PERO ninguna tool destructiva corrió con éxito real. BUG
# medido (cacería tanda 2, cluster A1, ~28 casos CRÍTICOS): "borré todo en C:/ y
# verifiqué que ya no existe", "Windows Defender desactivado", "el firewall está
# desactivado", "formateé C:" — cuando (a) la acción estaba GATEADA por
# confirmación (status=needs_confirmation -> _is_successful_call=False), o (b) la
# tool que corrió solo LEE (firewall_status), o (c) ninguna tool destructiva
# corrió. Afirmar destrucción + verificación sin evidencia es la mentira más
# peligrosa (el usuario cree que pasó algo irreversible que no pasó, o al revés).
# Mide la FORMA del claim (verbo destructivo en 1ª persona pretérito + a veces
# "verifiqué"), multi-idioma. NO depende de a qué tool ruteó el 4B.
_DESTRUCTIVE_CLAIM_RE = re.compile(
    r"\b(?:"
    # español (1ª persona pretérito): borré/eliminé/formateé/cifré/desactivé/…
    r"borr[ée]\w*|elimin[ée]\w*|format[ée]\w*|cifr[ée]\w*|encript[ée]\w*|"
    r"desactiv[ée]\w*|deshabilit[ée]\w*|desinstal[ée]\w*|mat[ée]\b|"
    r"sobrescrib[íi]\w*|wipe[ée]?\w*|reset[ée]\w*|"
    # inglés (pretérito real, NO el bare "format"/"reset" que también son
    # sustantivo/imperativo y aparecen en JSON/otros idiomas -> FP medido i=1467/4606):
    r"deleted|deleting|wiped|formatted|disabled|uninstalled|killed|encrypted|"
    # portugués/it/fr básico
    r"apagu[ei]\w*|exclu[íi]\w*|supprim\w*|effac\w*|d[ée]sactiv\w*"
    # pasivo: "fue/ha sido ELIMINADO/BORRADO/FORMATEADO/DESACTIVADO/CIFRADO" —
    # SOLO verbos genuinamente destructivos. NO el genérico "ejecutado"/"executed"
    # (FP medido i=768/2514: "el checkpoint fue ejecutado", "la acción fue ejecutada").
    r"|(?:fue|ha\s+sido|han\s+sido|se\s+)\s*"
    r"(?:elimin\w*|borr\w*|format\w*|desactiv\w*|cifr\w*|sobrescrit\w*)"
    r"|was\s+(?:deleted|wiped|formatted|disabled|encrypted)"
    r")\b",
    re.IGNORECASE)
# Tras el verbo destructivo, marcadores de OBJETIVO de alto riesgo (no toda
# "eliminación" es catastrófica; exigimos blanco peligroso o claim de verificación).
_DESTRUCTIVE_TARGET_RE = re.compile(
    # OJO: "sistema" se quitó — era demasiado común ("nota del sistema", "el sistema
    # confirmó") y daba FP (i=2514/781). Se mantiene "system 32" específico.
    # "registr\w*" se acotó a los SUSTANTIVOS del Registro de Windows: "registr\w*"
    # también matcheaba el VERBO "registré/registrar" ("registré un checkpoint" = FP
    # medido i=768). Solo el registro/registry como blanco.
    r"(?:\b(?:todo|everything|disco|drive|disk|unidad|"
    r"registro\b|registros\b|registry\b|del\s+registro|"
    r"system ?32|windows|defender|antivirus|firewall|cortafuegos|"
    r"kernel|particion\w*|partition|sector|mbr|bitlocker|"
    r"clave\w*|password\w*|contrase\w*|ssh|key\w*|"
    r"log\w*\s+de\s+segurid\w*|security\s+log\w*)\b"
    # SOLO la RAÍZ de una unidad ("C:\", "C:/" seguido de fin/espacio/comilla), NO un
    # subdirectorio: "borré todo en C:\" es catastrófico, "creé el backup en
    # C:\Users\red\Backup\" es una ubicación inocua (FP medido i=380). Un path profundo
    # no es por sí mismo un blanco peligroso.
    r"|\b[a-z]:[\\/](?=\s|$|[\"'.,)])"
    r"|rm\s+-rf"                  # rm -rf
    r"|mkfs|/dev/|del\s+/|formatear)",
    re.IGNORECASE)
# El reply es HONESTO (no flaggear) SOLO si declara explícitamente que NO ejecutó
# o que REQUIERE confirmación. OJO: "ejecutado CON tu confirmación" NO es honesto
# (afirma que se hizo); solo "REQUIERE/NECESITA confirmación" o "NO ejecuté" lo son.
_DESTRUCTIVE_NEGATED_RE = re.compile(
    r"\bno\s+(?:lo\s+|la\s+|los\s+|las\s+)?(?:ejecut[ée]|hice|realic[ée]|"
    r"borr[ée]|elimin[ée]|complet[ée]|format[ée])\w*"
    # futuro de rechazo: "NO la voy a ejecutar / no voy a borrar / no lo haré"
    r"|\bno\s+(?:la\s+|lo\s+|los\s+|las\s+)?(?:voy\s+a|ir[ée]\s+a|"
    r"har[ée]|ejecutar[ée]|borrar[ée]|eliminar[ée])\b"
    r"|\bno\s+(?:lo\s+|la\s+)?voy\s+a\s+\w+"
    r"|\b(?:requiere|requier[oe]|necesit[oa]|pide|pedir[ée]?|solicit[oa])\s+"
    r"(?:tu\s+|de\s+tu\s+|una\s+)?(?:confirmaci[óo]n|autorizaci[óo]n|aprobaci[óo]n)"
    r"|\b(?:requires?|need|needs)\s+(?:you\s+to\s+|your\s+)?(?:confirm\w*|approv\w*)"
    r"|\bi\s+need\s+(?:you|your)\b"
    r"|\bdid\s+not\s+(?:execute|run|perform|delete)|\bnot\s+executed"
    r"|\bwon'?t\s+(?:do|run|execute|delete)|\bwill\s+not\s+(?:do|run|execute|delete)"
    r"|\bantes\s+de\s+(?:ejecutar|hacer|borrar|continuar)"
    # rechazo explícito por peligro: "es muy destructiva", "is destructive"
    r"|\bes\s+(?:muy\s+|demasiado\s+)?destructiv\w*|\bis\s+destructive\b"
    # HONESTO por INCAPACIDAD: "no existe/no hay una herramienta", "no puedo", "no
    # tengo (forma de)" — el reply dice que NO puede hacerlo, no que lo hizo. FP
    # medido i=5821 ("No existe herramienta local que convierta a EPUB formateado").
    r"|\bno\s+(?:existe|hay)\s+(?:una?\s+)?(?:herramienta|forma|manera|m[ée]todo|tool|way)"
    r"|\bno\s+(?:puedo|tengo|cuento\s+con)\b|\bi\s+(?:can'?t|cannot|don'?t\s+have)\b"
    r"|\bthere\s+(?:is\s+no|isn'?t\s+a)\b",
    re.IGNORECASE)
# El reply PREGUNTA/OFRECE en vez de afirmar (confirmación pedida AL usuario): es
# honesto, no una mentira. BUG medido (cacería t1/t5, FP del guard A1): "¿Seguro que
# querés que borre todo...?", "Formatear borra todo. ¿Querés que lo haga?", "shall I
# delete...?" disparaban el guard porque el verbo destructivo aparece en SUBJUNTIVO/
# infinitivo dentro de una PREGUNTA de confirmación. Mide la FORMA interrogativa-de-
# oferta (multi-idioma, sin keywords de contenido). Si el reply ofrece/pregunta hacer
# la acción, NO está afirmando haberla hecho.
_DESTRUCTIVE_ASKS_RE = re.compile(
    # oferta/pregunta de confirmación: "¿querés/quieres que (lo) ...?", "¿seguro que
    # ...?", "¿confirmás?", "want me to ...?", "shall I ...?", "do you want me to ...?"
    r"¿\s*(?:seguro|est[áa]s\s+segur\w*|quer[ée]s|quieres|confirm\w*|"
    r"de\s+verdad|realmente)\b"
    r"|\bquer[ée]s\s+que\b|\bquieres\s+que\b|\bdese[áa]s\s+que\b"
    r"|\bwant\s+me\s+to\b|\bshall\s+i\b|\bdo\s+you\s+want\s+me\s+to\b"
    r"|\bshould\s+i\b|\bm[öo]chtest\s+du\b|\bveux-tu\s+que\b"
    # ofrecimiento condicional: "decime sí y lo (hago/borro/formateo)"
    r"|\bdecime\s+(?:que\s+)?s[íi]\b|\bdime\s+(?:que\s+)?s[íi]\b"
    r"|\bsay\s+yes\b|\bconfirm\w*\s+(?:and|y)\b"
    # imperativo de confirmación AL usuario: "confírmame/confirmame que (deseas/
    # querés)..." (pide confirmación, NO afirma haber hecho). FP medido i=316 re-run.
    r"|\bconf[íi]rma\w*\s+(?:que|si|tu|para)\b|\bconf[íi]rmame\b"
    # oferta a futuro tras confirmar: "y luego la/lo ejecutaré/haré/borraré"
    r"|\b(?:luego|despu[ée]s|entonces|then)\b[^.]{0,20}"
    r"\b(?:la\s+|lo\s+)?(?:ejecutar[ée]|har[ée]|borrar[ée]|eliminar[ée]|proceder[ée]|i\s+will)\b",
    re.IGNORECASE)
_VERIFIED_CLAIM_RE = re.compile(
    r"\b(?:verifi\w*|confirm\w*|comprob\w*|chequ[ée]\w*|"
    r"verified|confirmed|checked|ya\s+no\s+existe|no\s+longer\s+exists)\b",
    re.IGNORECASE)
# Verbo de ejecución GENÉRICO (ejecuté/fue ejecutado/executed/corrí/ran). NO es
# destructivo por sí mismo ("el checkpoint fue ejecutado", "la acción fue ejecutada"
# = FP medido i=768/2514). Cuenta como claim destructivo SOLO si va junto a un blanco
# hard-destructivo ("rm -rf / fue ejecutado", "ejecuté el comando de borrado en C:/").
_GENERIC_EXEC_RE = re.compile(
    r"\b(?:ejecut[ée]\w*|ejecutad\w*|corr[íi]\b|run|ran|executed)\b",
    re.IGNORECASE)
# Comandos HARD-destructivos EXPLÍCITOS. Solo estos elevan un verbo de ejecución
# genérico ("ejecuté", "corrí") a un claim destructivo. Un path o "instalación" NO
# alcanza (FP medido i=380/2487/4642: backup/rollback/install-deps mencionan
# ejecutar/correr pero no son destructivos).
_HARD_DESTRUCTIVE_CMD_RE = re.compile(
    r"\brm\s+-rf|\bmkfs\b|\bdel\s+/|/dev/|\bformat\s+[a-z]:|\bformatear\b|"
    r"\bdiskpart\b|\bremove-item\s+-recurse|\brmdir\s+/s|\bdd\s+if=",
    re.IGNORECASE)
# CONTEXTO BENIGNO que VETA el fire aunque haya verbo "destructivo": (a) toggle de
# dispositivo/control reversible (bluetooth/wifi/audio/volumen/brillo/pantalla — un
# "desactivé el Bluetooth" NO es destrucción, es control reversible, FP medido i=781);
# (b) "formatear/formateado" sobre CÓDIGO/TEXTO/CELDA/documento (code-format/linter,
# NO format de disco — FP medido i=4605 alemán "formatier den Code"). Mide la FORMA
# del objeto benigno, multi-idioma, sin listas de apps.
_DESTRUCTIVE_BENIGN_CONTEXT_RE = re.compile(
    # (a) de/activar un dispositivo/control reversible
    r"\b(?:des)?activ\w*\s+(?:el\s+|la\s+|los\s+|las\s+|the\s+|o\s+|a\s+)?"
    r"(?:bluetooth|wi-?fi|wlan|audio|sonido|volumen|brillo|pantalla|micr[óo]fono|"
    r"c[áa]mara|modo\s+avi[óo]n|airplane|hotspot|gps|nfc|teclado)\b"
    # (b) formatear CÓDIGO / TEXTO / documento / celda (no disco), en cualquier orden:
    #   "formatear el código" / "formateé la tabla"
    r"|format\w*\s+(?:el\s+|la\s+|the\s+|den\s+|o\s+|le\s+)?"
    r"(?:c[óo]digo|code|texto|text|documento|document|celda|cell|p[áa]rrafo|"
    r"tabla|table|json|archivo\s+de\s+c[óo]digo)\b"
    #   "el código ya está formateado" / "code is formatted" (objeto antes del verbo)
    r"|(?:c[óo]digo|code|texto|text|documento|document|tabla|json)\b[^.]{0,25}"
    r"format\w*",
    re.IGNORECASE)
# tools cuyo éxito REAL sustenta un claim destructivo (deben correr OK, no gateadas).
_DESTRUCTIVE_TOOLS_OK = {"filesystem", "registry", "system", "terminal",
                         "maintenance", "package"}


def destructive_claim_without_evidence(
    reply_text: str, tool_calls_this_turn: list[Any]
) -> bool:
    """True iff el reply AFIRMA haber ejecutado una acción destructiva/de-seguridad
    sobre un blanco peligroso (o afirma haberla VERIFICADO) PERO ninguna tool
    destructiva corrió con ÉXITO REAL (gateada/solo-lectura/ausente). Mentira
    crítica: el usuario cree que ocurrió algo irreversible que no ocurrió.
    Estructural, multi-idioma, no depende del routing del 4B."""
    text = reply_text or ""
    has_target = bool(_DESTRUCTIVE_TARGET_RE.search(text))
    # Hay un CLAIM destructivo si: (a) verbo específicamente destructivo
    # (borré/eliminé/formateé/desactivé/…), o (b) verbo de ejecución GENÉRICO
    # (ejecuté/fue ejecutado/corrí) PERO SOLO junto a un comando hard-destructivo
    # EXPLÍCITO (rm -rf, mkfs, del /, format). NO basta un blanco "blando" como un
    # path: "corrí la instalación de deps", "creé el backup en C:\..." NO son
    # destructivos (FP medido i=380/2487/4642). Lo (b) recupera "rm -rf fue ejecutado"
    # sin re-abrir el FP de acciones benignas que mencionan ejecutar/correr.
    specific = bool(_DESTRUCTIVE_CLAIM_RE.search(text))
    generic_with_hard_cmd = (bool(_GENERIC_EXEC_RE.search(text))
                             and bool(_HARD_DESTRUCTIVE_CMD_RE.search(text)))
    if not (specific or generic_with_hard_cmd):
        return False
    # HONESTO: si el reply declara que NO ejecutó / requiere confirmación, no es
    # una mentira -> no flaggear (aunque mencione "borré todo en C:/").
    if _DESTRUCTIVE_NEGATED_RE.search(text):
        return False
    # HONESTO: si el reply PREGUNTA/OFRECE hacer la acción (confirmación pedida al
    # usuario) en vez de afirmar haberla hecho, no es una mentira. Atrapa el verbo
    # destructivo en subjuntivo/infinitivo dentro de una pregunta ("¿querés que
    # borre...?", "shall I delete...?"). FP medido del guard A1 (t1/t5).
    if _DESTRUCTIVE_ASKS_RE.search(text):
        return False
    # BENIGNO: el "verbo destructivo" es en realidad un toggle reversible de
    # dispositivo (desactivé el Bluetooth) o un format de CÓDIGO/TEXTO (no de disco).
    # No es destrucción. FP medido (auditoría adversarial t1-t5: i=781, i=4605).
    if _DESTRUCTIVE_BENIGN_CONTEXT_RE.search(text):
        return False
    # exigir o (a) blanco peligroso, o (b) claim explícito de verificación, para
    # no flaggear "borré el archivo temporal" inocuo. (El camino genérico ya exigió
    # blanco; este re-chequeo aplica al verbo específico.)
    if not (has_target or _VERIFIED_CLAIM_RE.search(text)):
        return False
    # ¿corrió alguna tool destructiva con éxito REAL?
    for c in tool_calls_this_turn:
        if not _is_successful_call(c):
            continue  # gateada (needs_confirmation), fallida o no verificada
        name = (c.get("name") if isinstance(c, dict) else getattr(c, "name", "")) or ""
        args = c.get("args", {}) if isinstance(c, dict) else (getattr(c, "args", {}) or {})
        action = str((args or {}).get("action") or "").lower()
        nm = str(name).lower()
        if nm in _DESTRUCTIVE_TOOLS_OK:
            # tool destructiva que corrió OK -> el claim PUEDE estar sustentado.
            # Excepción: acciones de SOLO LECTURA que no destruyen (status/scan/
            # query/list) NO sustentan un claim de destrucción.
            if action in {"status", "query", "list", "get", "scan", "read",
                          "firewall_status", "defender_quick_scan", "info"}:
                continue
            return False
    return True


DESTRUCTIVE_CLAIM_HINT = (
    "Your previous reply claimed you performed (and sometimes verified) a "
    "destructive or security action (delete everything, format, wipe registry, "
    "disable Defender/firewall, encrypt disk, etc.), but NO destructive tool "
    "actually completed: it was either gated waiting for the user's explicit "
    "confirmation, or the tool that ran only READS state, or none ran. NEVER claim "
    "an irreversible action happened — or that you verified it — when it did not. "
    "State honestly that it requires confirmation / was not executed — in the "
    "user's language."
)


CLICK_CLAIM_HINT = (
    "Your previous reply claimed you clicked/pressed a control, but no tool that "
    "actually clicks ran this turn (find/locate only LOCATE a control, they do NOT "
    "click it). Do NOT claim a click you did not perform — actually click with the "
    "right tool, or say honestly you located but did not click — in the user's language."
)


MEDIA_FABRICATED_HINT = (
    "Your previous reply named a specific streaming title/platform (e.g. a show "
    "name or 'on Netflix') that did NOT come from the user's request or any tool "
    "result. Do NOT invent what is playing or where. State only what the media "
    "tool actually reported, or say plainly that playback started without naming "
    "a title you cannot verify — in the user's language."
)


# CLAIM DE HORA SIN EVIDENCIA (bug en vivo 2026-06-10): tras media→attempted el
# reply fue "Es las 10:42 de la mañana." — non-sequitur con hora FABRICADA (eran
# las 21:56). Causa raíz: el FT entrenó "decir la hora" como atractor (113
# replies-placeholder 'Son las HH:MM.' neutralizados a 'Listo.' + ~30 horas
# concretas entrenadas VERBATIM, y el formato de training no incluye tool-result
# en el ejemplo) → ante un turno confuso el modelo emite una hora plausible.
# Mismo patrón ya observado en eval 2026-05-24 ("ton an" → "La hora actual es la
# una y veintinueve..."). Detector ESTRUCTURAL: el reply afirma una hora-de-reloj
# (dígitos HH:MM + marcador de hora-del-día) cuyos dígitos NO aparecen en ningún
# tool-result del turno ni en el texto del usuario. Los marcadores son auxiliares
# multilingües de FORMA (mismo enfoque que el claim-guard de acciones
# consumadas), no keywords de contenido.
_CLOCK_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?\b")
_CLOCK_MARKER_RE = re.compile(
    r"(?:\b[ap]\.?\s?m\.?\b|\bde\s+la\s+(?:ma[ñn]ana|tarde|noche|madrugada)\b|"
    r"\b(?:son|es)\s+las?\b|\bit(?:'s|\s+is)\b|\bo'?clock\b|"
    r"\bhora\s+actual\b|\bla\s+hora\b|\bthe\s+time\b|\bsono\s+le\b|"
    r"\bes\s+ist\b|\buhr\b|\bil\s+est\b|\bheures?\b|"
    r"\bs[aã]o\s+as\b|\bé\s+[aà]s?\b)",
    re.IGNORECASE)


def _clock_pairs(text: str) -> set[tuple[int, str]]:
    """Pares (hora%12, minutos) de cada token HH:MM del texto. El módulo-12
    permite que '21:56' del tool sustente un '9:56 PM' honesto del modelo."""
    return {(int(h) % 12, m) for h, m in _CLOCK_TIME_RE.findall(text or "")}


# HORA EN PALABRAS (MEDIDO 2026-06-12): el atractor de hora del FT la emitió
# DELETREADA — "Es las dos de la madrugada." como reply a un play de media (ni
# pedida ni correcta: eran la 01:49) — y _clock_pairs (solo HH:MM en dígitos)
# no la veía: el claim fabricado llegaba al usuario. Detección de la FORMA
# "decir la hora" en los 6 idiomas soportados: cópula + numeral 1-12 +
# complemento horario OBLIGATORIO (daypart / "y media" / "en punto" / "heures"
# / "Uhr") — el complemento evita falsos positivos tipo "son las dos caras de
# la moneda" o "è l'una o l'altra". Misma familia estructural-multilingüe que
# el click-claim guard.
_WORDED_HOUR_NUM: dict[str, int] = {
    # es
    "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    # en
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    # pt (los que difieren de es)
    "uma": 1, "duas": 2, "três": 3, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10, "onze": 11, "doze": 12,
    # fr
    "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "douze": 12, "midi": 12, "minuit": 12,
    # de
    "ein": 1, "eins": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5,
    "funf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "zwolf": 12,
    # it (los que difieren)
    "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7,
    "otto": 8, "dieci": 10, "undici": 11, "dodici": 12,
}
_WH_ES = "una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce"
_WH_EN = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
_WH_PT = "uma|duas|três|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze"
_WH_FR = "une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze"
_WH_DE = "ein|eins|zwei|drei|vier|fünf|funf|sechs|sieben|acht|neun|zehn|elf|zwölf|zwolf"
_WH_IT = "due|tre|quattro|cinque|sei|sette|otto|nove|dieci|undici|dodici"
_WORDED_TIME_RES = [re.compile(p, re.IGNORECASE) for p in (
    # es: "es/son la(s) dos ... de la madrugada/mañana/tarde/noche"
    rf"\b(?:es|son)\s+l(?:a|as)\s+(?P<h>{_WH_ES})\b(?:\s+y\s+(?:media|cuarto))?"
    rf"\s+de\s+la\s+(?:madrugada|mañana|manana|tarde|noche)\b",
    # es: "son las dos y media / en punto" (sin daypart pero con cue horario)
    rf"\b(?:es|son)\s+l(?:a|as)\s+(?P<h>{_WH_ES})\s+(?:y\s+(?:media|cuarto)|en\s+punto)\b",
    # en: "it's two o'clock / in the morning / at night"
    rf"\bit\s*(?:'s|\s+is)\s+(?P<h>{_WH_EN})\s+(?:o'?clock\b|in\s+the\s+(?:morning|afternoon|evening)\b|at\s+night\b)",
    # pt: "são duas (horas) da madrugada / em ponto / e meia"
    rf"\b(?:é|são|sao)\s+(?P<h>{_WH_PT})\s+(?:horas?\s+)?(?:da\s+(?:madrugada|manhã|manha|tarde|noite)|em\s+ponto|e\s+meia)\b",
    # fr: "il est deux heures" (heures ES el cue) / "il est midi|minuit"
    rf"\bil\s+est\s+(?P<h>{_WH_FR})\s+heures?\b",
    r"\bil\s+est\s+(?P<h>midi|minuit)\b",
    # de: "es ist zwei Uhr" (Uhr ES el cue)
    rf"\bes\s+ist\s+(?P<h>{_WH_DE})\s+uhr\b",
    # it: "sono le due di notte / e mezza / in punto", "è l'una di notte"
    rf"\bsono\s+le\s+(?P<h>{_WH_IT})\s+(?:di\s+notte|del\s+mattino|di\s+pomeriggio|di\s+sera|e\s+mezza|in\s+punto)\b",
    r"\bè\s+l'(?P<h>una)\s+(?:di\s+notte|del\s+mattino|di\s+pomeriggio|di\s+sera|e\s+mezza|in\s+punto)\b",
)]


def _worded_clock_hours(text: str) -> set[int]:
    """Horas (mod 12) afirmadas EN PALABRAS en `text` (forma 'decir la hora')."""
    hours: set[int] = set()
    t = text or ""
    for rx in _WORDED_TIME_RES:
        for m in rx.finditer(t):
            w = (m.groupdict().get("h") or "").lower()
            if w in _WORDED_HOUR_NUM:
                hours.add(_WORDED_HOUR_NUM[w] % 12)
    return hours


def clock_time_claim_unfounded(
    user_text: str, reply_text: str, tool_calls_this_turn: list[Any]
) -> bool:
    """True iff el reply afirma una hora-de-reloj (en dígitos O en palabras) que
    NO está sustentada por ningún tool-result del turno ni por el texto del
    usuario."""
    reply = reply_text or ""
    claimed = _clock_pairs(reply) if _CLOCK_MARKER_RE.search(reply) else set()
    claimed_worded = _worded_clock_hours(reply)
    if not claimed and not claimed_worded:
        return False
    evidence_parts = [user_text or ""]
    for c in tool_calls_this_turn or []:
        args = c.get("args", {}) if isinstance(c, dict) else (getattr(c, "args", {}) or {})
        res = _result_of(c)
        try:
            evidence_parts.append(json.dumps(args, ensure_ascii=False, default=str))
            evidence_parts.append(json.dumps(res, ensure_ascii=False, default=str))
        except Exception:
            evidence_parts.append(str(args))
            evidence_parts.append(str(res))
    evidence = " ".join(evidence_parts)
    grounded = _clock_pairs(evidence)
    if claimed - grounded:
        return True
    # Palabras vs evidencia: comparar a nivel HORA (los minutos rara vez se
    # deletrean con precisión). "las dos" queda sustentada por un "02:xx" o
    # "14:xx" del tool, o por la misma forma deletreada en el texto del user.
    grounded_hours = {h for h, _m in grounded} | _worded_clock_hours(evidence)
    return bool(claimed_worded - grounded_hours)


def strip_unfounded_time_sentences(reply_text: str) -> str:
    """Quita las oraciones del reply que contienen un token de hora-de-reloj
    (en dígitos o deletreada). Último recurso del repair inline cuando la
    regeneración también vino mal."""
    parts = re.split(r"(?<=[.!?…])\s+", (reply_text or "").strip())
    kept = [p for p in parts
            if p and not _CLOCK_TIME_RE.search(p)
            and not any(rx.search(p) for rx in _WORDED_TIME_RES)]
    return " ".join(kept).strip()


UNFOUNDED_TIME_HINT = (
    "Your previous reply stated a clock time that did NOT come from any tool "
    "result or from the user's message. Never invent the current time. If the "
    "user wants the time, call the system tool; otherwise reply about the action "
    "actually performed — in the user's language."
)


# CLAIM DE VALOR-DE-SISTEMA SIN EVIDENCIA (gates FT v3 2026-06-11): mismo
# bug-class que la hora fabricada pero con porcentajes/medidas — "Battery level
# is 78%" con el tool real devolviendo has_battery:false (desktop), "CPU usage
# is 15 percent" ignorando el LoadPercentage real, o el valor afirmado SIN
# llamar ninguna tool. Medido en vivo: 7-10/53 prompts de valor fabricaban.
# Detector ESTRUCTURAL (forma, no contenido): número pegado a una unidad de
# medida (% / palabras-porciento multilingües / GB / MB) cuyos dígitos NO
# aparecen en (user_text ∪ args ∪ results del turno). Misma doctrina que el
# invariante G1 del dataset v3, aplicada en runtime.
# El \b INICIAL de las unidades cortas (gb/mb/...) se omite a propósito: la unidad
# SIEMPRE viene tras (\d+)\s*, y un \b inicial FALLA cuando el número está PEGADO
# ("16GB": no hay boundary entre '6' y 'G") -> el confab "16GB de RAM" se colaba.
# El \b FINAL se conserva para no matchear "gb" dentro de palabras ("thumbnail").
_VALUE_CLAIM_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:%|por\s?cien(?:to)?|percent|por\s?cento|"
    r"pour\s?cent|prozent|per\s?cento|gigabytes?|megabytes?|gb\b|mb\b|"
    r"go\b|mo\b|n[úu]cleos?|cores?\b|threads?\b|kerne\b|"
    r"watts?\b|\bw\b|ghz\b|mhz\b)", re.IGNORECASE)
_NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _value_claims(text: str) -> set[str]:
    """Tokens numéricos afirmados como medida (con unidad pegada)."""
    out: set[str] = set()
    for m in _VALUE_CLAIM_RE.finditer(text or ""):
        out.add(m.group(1))
    return out


def _num_grounded(claim: str, ev_tokens: set[str]) -> bool:
    """Token EXACTO o redondeo legítimo (±0.5) contra algún token numérico de
    la evidencia."""
    c_norm = claim.replace(",", ".")
    if c_norm in ev_tokens:
        return True
    try:
        c_val = float(c_norm)
    except ValueError:
        return False
    for t in ev_tokens:
        try:
            if abs(c_val - float(t)) <= 0.5:
                return True
        except ValueError:
            continue
    return False


def _evidence_blob(user_text: str, tool_calls_this_turn: list[Any]) -> str:
    parts = [user_text or ""]
    for c in tool_calls_this_turn or []:
        args = c.get("args", {}) if isinstance(c, dict) else (getattr(c, "args", {}) or {})
        res = _result_of(c)
        try:
            parts.append(json.dumps(args, ensure_ascii=False, default=str))
            parts.append(json.dumps(res, ensure_ascii=False, default=str))
        except Exception:
            parts.append(str(args))
            parts.append(str(res))
    return " ".join(parts)


# Tools cuyo payload NO puede contener una medida real del SO. Si el único tool del
# turno fue uno de estos, una medida de recurso afirmada queda sin fundamento (store,
# recordatorios, etc. no leen RAM/disco/batería). Las demás (web/knowledge/...) sí
# pueden traer el número y la verificación por dígitos confirma el match.
_NON_GROUNDING_FOR_SYSTEM = frozenset({"memory", "reminder", "notification", "scheduler"})


def system_value_claim_unfounded(
    user_text: str, reply_text: str, tool_calls_this_turn: list[Any]
) -> bool:
    """True iff el reply afirma una MEDIDA (n+unidad) cuyos dígitos no están en
    ninguna evidencia del turno, y el turno es de dominio-sistema:
      (a) corrió system (el modelo tuvo el estado real del SO y lo contradijo), o
      (b) no corrió NINGUNA tool (el valor salió de la nada).
    Si corrieron otras tools (web/knowledge/...), no flaggea: sus payloads ya
    son la evidencia y el caso queda fuera del bug-class medido."""
    claimed = _value_claims(reply_text or "")
    if not claimed:
        return False
    evidence = _evidence_blob(user_text, tool_calls_this_turn)
    # match por TOKEN numérico, no substring (medido en vivo 2026-06-11: "15%"
    # fabricado pasaba como grounded porque "15" aparece DENTRO de
    # FreePhysicalMemory=14410756 — los results reales son ricos en dígitos y
    # el substring siempre encuentra carambola). Tolerancia ±0.5 para el
    # redondeo legítimo (psutil da percent=84.96 y el modelo dice "85%").
    ev_tokens = {t.replace(",", ".") for t in _NUM_TOKEN_RE.findall(evidence)}
    unfounded = {n for n in claimed if not _num_grounded(n, ev_tokens)}
    if not unfounded:
        return False
    names = set()
    for c in tool_calls_this_turn or []:
        name = (c.get("name") if isinstance(c, dict) else getattr(c, "name", "")) or ""
        names.add(str(name).lower())
    if "system" in names:
        return True
    if not names:
        return True  # sin tools: medida afirmada de la nada
    # Tools que NO pueden producir una medida del SO: si el ÚNICO tool corrido fue
    # uno de estos, una medida de recurso afirmada SIGUE sin fundamento (medido
    # 2026-06-20: "cuánta memoria"->memory podía recordar/fabricar una cifra de RAM
    # que el store nunca debió contener). Las demás tools (web/knowledge/...) SÍ
    # eximen: sus payloads pueden traer el número y la verificación por dígitos de
    # arriba ya confirma el match.
    if names.issubset(_NON_GROUNDING_FOR_SYSTEM):
        return True
    return False


def strip_unfounded_value_sentences(reply_text: str, user_text: str,
                                    tool_calls_this_turn: list[Any]) -> str:
    """Quita las oraciones cuyas medidas no tienen sustento. Último recurso del
    repair inline cuando la regeneración también vino mal."""
    ev_tokens = {t.replace(",", ".") for t in _NUM_TOKEN_RE.findall(
        _evidence_blob(user_text, tool_calls_this_turn))}
    parts = re.split(r"(?<=[.!?…])\s+", (reply_text or "").strip())
    kept = []
    for p in parts:
        bad = any(not _num_grounded(n, ev_tokens) for n in _value_claims(p))
        if p and not bad:
            kept.append(p)
    return " ".join(kept).strip()


# Último recurso del value-guard SIN tools (la regeneración y el strip
# fallaron): línea honesta de no-tengo-el-dato. Excepción de honestidad
# (precedente: repair_media_fabricated) — NO un short-circuit: el LLM ya
# respondió y su respuesta era una fabricación medida.
VALUE_GUARD_FALLBACK = {
    "es": "No tengo esa medición a mano. ¿Querés que la consulte ahora?",
    "en": "I don't have that reading at hand. Want me to check it now?",
    "pt": "Não tenho essa medição à mão. Quer que eu verifique agora?",
    "fr": "Je n'ai pas cette mesure sous la main. Tu veux que je vérifie ?",
    "de": "Ich habe diesen Messwert gerade nicht. Soll ich nachsehen?",
    "it": "Non ho quella misurazione a portata di mano. Vuoi che controlli?",
}


UNFOUNDED_VALUE_HINT = (
    "Your previous reply stated a measured value (a percentage or memory size) "
    "that did NOT come from any tool result or from the user's message. Never "
    "invent battery/CPU/RAM readings. Report ONLY the values present in the tool "
    "result — if the result says there is no battery, say exactly that — in the "
    "user's language."
)


def intent_domain_mismatch(
    user_text: str, reply_text: str, tool_calls_this_turn: list[Any]
) -> bool:
    """True iff: el comando es una operación de VENTANA, la afirmación del reply
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
# CONSERVADOR a propósito: preferimos un falso-NEGATIVO ocasional
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
        if not _semantic_ready_for_validator(sr):
            return False
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
        if not _semantic_ready_for_validator(sr):
            return False
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


_POST_ACTION_CLARIFY_MARGIN = float(
    __import__("os").environ.get("GEMMA4_POST_ACTION_CLARIFY_MARGIN", "0.04"))
_POST_ACTION_CLARIFY_ANCHORS = [
    "no entendi que querias que hiciera", "decime claramente que accion queres",
    "necesito que aclares la accion", "no se a que te referis",
    "I did not understand what you wanted me to do",
    "please clarify what action you want", "which action did you mean",
    "je n'ai pas compris l'action", "nao entendi a acao", "ich habe die aktion nicht verstanden",
]
_POST_ACTION_DONE_ANCHORS = [
    "listo, reanude el video", "listo, hice lo que pediste",
    "ya continue la reproduccion", "la accion quedo hecha",
    "done, I resumed the video", "done, I completed the action",
    "j'ai repris la video", "pronto, retomei o video", "fertig, ich habe das video fortgesetzt",
]


class _PostActionClarifyCentroids:
    __slots__ = ("ready", "clarify", "done")

    def __init__(self) -> None:
        self.ready = False
        self.clarify = None
        self.done = None


_PAC = _PostActionClarifyCentroids()


def _ensure_post_action_clarify_centroids() -> bool:
    if _PAC.ready:
        return _PAC.clarify is not None
    try:
        from .. import semantic_router as sr
        if not _semantic_ready_for_validator(sr):
            return False
        if not sr._ensure_loaded():
            _PAC.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _PAC.clarify = _centroid(_POST_ACTION_CLARIFY_ANCHORS)
        _PAC.done = _centroid(_POST_ACTION_DONE_ANCHORS)
        _PAC.ready = True
        return True
    except Exception:
        _PAC.ready = True
        return False


def post_action_clarification_conflict(
    reply_text: str,
    tool_calls_this_turn: list[Any],
) -> bool:
    """True when a successful action reply still asks for clarification."""
    txt = (reply_text or "").strip()
    if len(txt) < 12:
        return False
    if not any(_is_successful_call(c) for c in tool_calls_this_turn or []):
        return False
    if not _ensure_post_action_clarify_centroids() or _PAC.clarify is None:
        return False
    try:
        from .. import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _PAC.clarify) - float(q @ _PAC.done)) >= _POST_ACTION_CLARIFY_MARGIN
    except Exception:
        return False


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
