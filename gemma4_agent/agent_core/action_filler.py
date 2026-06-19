"""Confirm filler: audio inmediato mientras el LLM piensa (2026-06-10).

Enmascara el silencio de 2-4s entre que el usuario termina de hablar y el reply
sale (medido p50 2.2s, max 3.9s en turnos calientes de acción). Patrón estándar
voice-agent (Vapi request-start, Sierra time-to-first-audio): emitir un audio
corto INMEDIATO en cuanto se detecta una acción, mientras el LLM corre en
background. Reduce la latencia PERCIBIDA ~1-2s sin tocar la computacional.

HONESTIDAD (regla del proyecto): el filler NUNCA debe contradecir el resultado.
Dos niveles:
  - GENÉRICO (siempre seguro): "Dame un segundo…", con personalidad. No promete
    NADA concreto -> imposible que mienta, aunque el LLM falle o haga otra cosa.
  - INTENT-AWARE (solo alta confianza): "Abriendo Spotify…" SOLO cuando el router
    tiene una sola acción de apertura clara y el target es conocido. Si hay
    cualquier ambigüedad -> cae al genérico. El riesgo de contradicción se acota
    a casos donde el router casi nunca se equivoca (open/launch con nombre).

NO es respuesta enlatada que reemplace al LLM: es un PREÁMBULO hablado mientras el
LLM genera el reply REAL (que sí sale después). El filler se voca, el reply final
también -> el usuario oye "Dame un segundo… [pausa] Listo, abrí Spotify".

Gate: GEMMA4_ACTION_FILLER=0 desactiva. Default ON (solo modo voz; texto/GUI no
tienen sink). Variedad por índice de turno (sin Math.random, que rompe resume):
se rota el banco por un contador de instancia.

CABLEADO en agent.run_content via _voice_action_filler (2026-06-10). El nivel
INTENT-AWARE quedó OPT-IN (GEMMA4_FILLER_INTENT, default OFF): MEDIDO en vivo
que los opens fáciles los resuelve el app-open net en decide (early_reply ~1s,
sin filler) — al LLM llega el subset que el net NO resolvió, así que "Abriendo
X" dispara sesgado hacia fallos y contradice ("Abriendo jitomatador." -> "No
llegué a ejecutar ninguna acción"). Ver scripts/_validate_action_filler.py.
"""
from __future__ import annotations

import os

# Banco de fillers GENÉRICOS con PERSONALIDAD (Baxy/Maxi). Cortos (~1-1.5s de
# audio), informales, nunca prometen una acción concreta. Multi-idioma por el
# código del perfil de voz; acá ES (el idioma se resuelve en el call-site real).
_GENERIC_ES = [
    "Dame un segundo.",
    "Ya voy con eso.",
    "Enseguida.",
    "Un momento, lo veo.",
    "Dale, ahí va.",
]
# Si el turno se DEMORA (segundo filler, el LLM sigue): más personalidad, sin mentir.
_GENERIC_SLOW_ES = [
    "Sigo en eso, calentando motores.",
    "Aguantame un toque, ya casi.",
    "Tranqui, lo estoy resolviendo.",
]

_GENERIC_EN = [
    "Give me a sec.", "On it.", "One moment.", "Let me check that.", "Right away.",
]
_GENERIC_SLOW_EN = [
    "Still on it, warming up.", "Hang tight, almost there.",
]

# Verbos de apertura -> plantilla intent-aware. SOLO se usa con alta confianza.
_OPEN_TEMPLATE_ES = "Abriendo {target}."
_OPEN_TEMPLATE_EN = "Opening {target}."
# tools cuya acción de apertura es segura para anunciar (open/launch de algo con
# nombre claro). NO incluye web/research/system (target ambiguo o pregunta).
_OPENABLE_TOOLS = frozenset({"app", "steam", "browser", "game_launcher", "media"})


def _enabled() -> bool:
    return os.environ.get("GEMMA4_ACTION_FILLER", "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def _bank(lang: str, slow: bool) -> list[str]:
    if lang == "en":
        return _GENERIC_SLOW_EN if slow else _GENERIC_EN
    return _GENERIC_SLOW_ES if slow else _GENERIC_ES


def pick_filler(
    *,
    lang: str = "es",
    rotate: int = 0,
    slow: bool = False,
    intent_target: str | None = None,
    intent_tool: str | None = None,
) -> str | None:
    """Devuelve el texto del filler a vocar, o None si está desactivado.

    intent_target/intent_tool: si vienen y la tool es openable, intenta el
    intent-aware ("Abriendo X"); si no, genérico con personalidad. `rotate`
    (contador de turno) varía el banco sin random.
    """
    if not _enabled():
        return None
    # INTENT-AWARE: solo si hay un target claro + tool openable + NO es slow
    # (el slow ya implica que algo tardó; ahí mejor genérico tranquilizador).
    if not slow and intent_target and intent_tool in _OPENABLE_TOOLS:
        tmpl = _OPEN_TEMPLATE_EN if lang == "en" else _OPEN_TEMPLATE_ES
        return tmpl.format(target=intent_target)
    bank = _bank(lang, slow)
    if not bank:
        return None
    return bank[rotate % len(bank)]


def intent_target_for_filler(user_text: str, tool_names: list[str] | None) -> tuple[str | None, str | None]:
    """Extrae (target, tool) para el intent-aware filler, SOLO si es seguro:
    la tool líder del router es openable Y el texto trae un nombre propio claro
    tras un verbo de apertura. Si hay cualquier duda -> (None, None) -> genérico.
    CONSERVADOR a propósito: preferimos el filler genérico antes que mentir.
    """
    if not tool_names or not user_text:
        return (None, None)
    lead = tool_names[0]
    if lead not in _OPENABLE_TOOLS:
        return (None, None)
    import re
    # "abrí/abre/lanzá/poné/open/launch <Target>" — captura el target tras el verbo.
    m = re.search(
        r"\b(?:abr[íi]|abre|abrime|lanz[áa]|lanza|ejecut[áa]|inicia|arranca|"
        r"pon[ée]|poné|open|launch|start|play)\s+(?:el|la|los|las|the|a|an|mi|my)?\s*"
        r"([A-Za-zÁÉÍÓÚáéíóúÑñ][\w .\-']{1,28})",
        user_text.strip())
    if not m:
        return (None, None)
    target = m.group(1).strip().rstrip(".,;:!?").strip()
    # target debe parecer un NOMBRE (no un verbo/relleno suelto). Heurística:
    # 1-3 palabras, al menos una empieza con mayúscula o es claramente un nombre.
    if not target or len(target.split()) > 3:
        return (None, None)
    return (target, lead)
