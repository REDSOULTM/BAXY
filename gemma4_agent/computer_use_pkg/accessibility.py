"""Accessibility modes for the Carter agent.

Un MODO de accesibilidad es una capa de comportamiento más fuerte que una
`persona` (personas.py): además de un `system_hint` (que modula CÓMO responde
el LLM, multilingüe, sin frases enlatadas), trae FLAGS ESTRUCTURALES que el
runtime usa para garantizar invariantes que un usuario con discapacidad
necesita — p. ej. que TODA acción se confirme por voz para alguien no vidente,
o que el control sea 100% por voz para alguien con discapacidad motriz.

Diseño (alineado a CLAUDE.md):
- NADA de respuestas enlatadas ni keywords por idioma: el `system_hint` describe
  el COMPORTAMIENTO esperado; el LLM responde. Las garantías duras (narrar,
  confirmar) son guardas ESTRUCTURALES que miden la forma del turno, no su
  contenido, y se resuelven por estado del runtime.
- Tres modos respaldados por WCAG 2.1/2.2 (necesidades perceptuales vs motoras
  son distintas — https://www.audioeye.com/post/wcag-22/ ,
  https://www.levelaccess.com/blog/wcag-2-1-exploring-new-success-criteria/):
    * normal     — comportamiento base (sin cambios).
    * no_vidente — todo por audio: narra cada acción, lee pantalla on-demand,
                   describe errores/diálogos visuales. (perceptual)
    * movilidad  — control 100% por voz: nunca asume teclado/mouse del usuario;
                   confirma por voz lo irreversible. Ve la pantalla. (motor)

Persistencia: ~/.gemma4/active_accessibility_mode.txt (una línea), igual patrón
que profiles.active_profile.txt. Override por env: GEMMA4_ACCESSIBILITY_MODE.
Activación por voz: la decide una capa semántica (multilingüe) fuera de este
módulo; acá sólo vive el catálogo + get/set + persistencia.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ACTIVE_MODE_PATH = Path.home() / ".gemma4" / "active_accessibility_mode.txt"


@dataclass(frozen=True)
class AccessibilityMode:
    name: str
    display_name: str
    description: str
    system_hint: str
    # --- flags estructurales (garantías duras del runtime, no del LLM) ---
    # Narrar por voz el resultado de CADA acción ejecutada (no asumir que el
    # usuario ve el toast / la pantalla). Para no_vidente.
    narrate_all_actions: bool = False
    # Habilitar la lectura on-demand de la pantalla ("¿qué hay en pantalla?",
    # "leeme esto", "leeme el error") como salida hablada. Para no_vidente.
    read_screen_on_demand: bool = False
    # El control debe ser 100% por voz: el runtime NUNCA debe pedir al usuario
    # que toque teclado/mouse para completar una tarea. Para movilidad.
    hands_free_only: bool = False
    # Confirmar por VOZ (sí/no hablado) antes de acciones irreversibles, en vez
    # de un diálogo visual. Para movilidad.
    confirm_irreversible_spoken: bool = False
    # Herramientas que conviene priorizar en este modo (merge con el subset del
    # router, igual que personas.preferred_tools). Vacío = sin sesgo.
    preferred_tools: tuple[str, ...] = field(default_factory=tuple)


MODES: dict[str, AccessibilityMode] = {
    "normal": AccessibilityMode(
        name="normal",
        display_name="Normal",
        description="Comportamiento base, sin ajustes de accesibilidad.",
        system_hint="",
    ),
    "no_vidente": AccessibilityMode(
        name="no_vidente",
        display_name="No vidente",
        description=(
            "El usuario no ve la pantalla. Todo se comunica por audio: cada "
            "acción se narra, la pantalla se lee a pedido, los errores y "
            "diálogos visuales se describen en voz alta."
        ),
        system_hint=(
            "# Modo de accesibilidad: usuario NO VIDENTE\n"
            "La persona con la que hablás NO VE la pantalla. Toda la información "
            "le llega por audio, así que tu respuesta debe ser autosuficiente "
            "habladamente, en el idioma del usuario.\n"
            "- Después de CADA acción, decí en una frase corta QUÉ pasó y cuál "
            "es el estado resultante (no asumas que vio un cartel o la pantalla). "
            "Si algo no se pudo verificar, decilo con honestidad.\n"
            "- Cuando el usuario pida saber qué hay en pantalla, o leer algo, "
            "CAPTURÁ la pantalla con la herramienta de visión (vision: "
            "describe_screen para describirla, o uia/ocr para leer el texto) y "
            "recién entonces describí el contenido relevante de forma concreta "
            "y ordenada (de arriba a abajo, lo más importante primero). Nunca "
            "inventes lo que no leíste con una herramienta.\n"
            "- Ante un error o un diálogo, leé el texto real (capturándolo) y las "
            "opciones disponibles, y ofrecé el siguiente paso.\n"
            "- Evitá referencias puramente visuales ('hacé clic en el botón "
            "azul de arriba a la derecha') sin nombrarlo; identificá los "
            "elementos por su nombre/etiqueta."
        ),
        narrate_all_actions=True,
        read_screen_on_demand=True,
        # `vision` trae describe_screen/ocr (leer la pantalla en voz alta); uia da
        # el árbol de accesibilidad (más fiel que OCR cuando está disponible).
        preferred_tools=("vision", "uia", "gui", "computer_use", "browser_real"),
    ),
    "movilidad": AccessibilityMode(
        name="movilidad",
        display_name="Movilidad reducida",
        description=(
            "El usuario ve bien pero no puede usar teclado/mouse. Todo se "
            "controla por voz; el agente nunca le pide que toque algo y "
            "confirma por voz lo irreversible."
        ),
        system_hint=(
            "# Modo de accesibilidad: MOVILIDAD REDUCIDA (manos libres)\n"
            "La persona VE la pantalla pero NO puede usar teclado ni mouse: "
            "opera todo por voz. Respondé en el idioma del usuario.\n"
            "- NUNCA le pidas que escriba, haga clic, apriete una tecla o toque "
            "algo: vos ejecutás la acción por ella usando las herramientas de "
            "control del PC. Si una tarea parece requerir input manual, buscá "
            "la forma de hacerla vos.\n"
            "- No hace falta narrar todo (ella ve), pero ANTES de una acción "
            "IRREVERSIBLE o sensible (borrar, enviar, comprar, cerrar sin "
            "guardar) pedí confirmación hablada y esperá un sí/no por voz.\n"
            "- Mantené las confirmaciones breves; ella no quiere dictar de más."
        ),
        hands_free_only=True,
        confirm_irreversible_spoken=True,
        preferred_tools=("computer_use", "uia", "gui", "app", "window", "media"),
    ),
}


def get(name: str | None) -> AccessibilityMode:
    """Resuelve un modo por nombre. Cae a 'normal' silenciosamente."""
    key = (name or "normal").strip().casefold()
    return MODES.get(key, MODES["normal"])


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def get_active_mode() -> AccessibilityMode:
    """Modo activo. Orden: env GEMMA4_ACCESSIBILITY_MODE > archivo persistido >
    'normal'. El env NO pisa el archivo (no lo escribe); sólo manda en runtime
    para esta sesión, útil en tests/automation."""
    env = (os.environ.get("GEMMA4_ACCESSIBILITY_MODE") or "").strip().casefold()
    if env in MODES:
        return MODES[env]
    try:
        if ACTIVE_MODE_PATH.is_file():
            name = ACTIVE_MODE_PATH.read_text(encoding="utf-8").strip().casefold()
            if name in MODES:
                return MODES[name]
    except OSError:
        pass
    return MODES["normal"]


def set_active_mode(name: str) -> AccessibilityMode:
    """Persiste el modo activo atómicamente y lo devuelve. Lanza ValueError
    si el nombre no es un modo conocido (callers ya deberían normalizar)."""
    key = (name or "").strip().casefold()
    if key not in MODES:
        raise ValueError(f"unknown accessibility mode: {name!r} (valid: {list_names()})")
    _atomic_write_text(ACTIVE_MODE_PATH, key)
    return MODES[key]


def list_names() -> list[str]:
    # 'normal' primero, después el resto ordenado, para UIs/menus.
    rest = sorted(n for n in MODES if n != "normal")
    return ["normal", *rest]
