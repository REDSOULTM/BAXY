"""The capability families of the active catalog, in a stable order, as the composer names them.
"""

from __future__ import annotations




# Familias del catálogo activo, no una lista fija del corpus. El shell manda
# las operaciones configuradas y aquí sólo se les pone nombre de persona: una
# respuesta de capacidades describe lo que el producto sirve hoy.
CAPABILITY_FAMILIES: dict[str, tuple[str, str]] = {
    "app": ("abrir y cerrar programas", "open and close apps"),
    "window": ("mover y enfocar ventanas", "move and focus windows"),
    "audio": ("leer y ajustar el audio", "read and set the audio"),
    "system": (
        "leer la hora y el estado del equipo",
        "read the clock and the PC state",
    ),
    "note": ("tomar notas", "take notes"),
    "task": ("llevar tareas", "keep tasks"),
    "reminder": ("poner recordatorios", "set reminders"),
    "notification": ("avisarte a su hora", "raise your reminders on time"),
    "network": ("mirar la red", "check the network"),
    "wifi": ("manejar el wifi", "manage wifi"),
    "media": ("poner música y vídeo", "play music and video"),
    "streaming": ("abrir lo que ves en streaming", "open what you watch on streaming"),
    "browser": ("navegar por la web", "browse the web"),
    "web": ("buscar en la web", "search the web"),
    "filesystem": ("buscar y ordenar archivos", "find and organize files"),
    "memory": ("recordar lo que me pides", "remember what you tell me"),
    "clipboard": ("usar el portapapeles", "use the clipboard"),
    "calendar": ("ver y crear eventos", "see and create events"),
    "email": ("leer y contestar correo", "read and answer email"),
    "message": ("enviar mensajes", "send messages"),
    "game": ("instalar y lanzar juegos", "install and launch games"),
    "capture": ("mirar la pantalla", "look at the screen"),
    "ocr": ("leer texto de la pantalla", "read text on the screen"),
    "vision": ("describir lo que se ve", "describe what is on screen"),
    "input": ("escribir y hacer clic", "type and click"),
    "routine": ("guardar rutinas", "keep routines"),
    "backup": ("hacer copias de seguridad", "make backups"),
    "bluetooth": ("manejar bluetooth", "manage bluetooth"),
    "peripheral": ("usar impresora y escáner", "use the printer and scanner"),
    "office": ("crear documentos", "create documents"),
    "package": ("instalar programas", "install programs"),
    "process": ("ver los procesos", "list processes"),
}


# Cuántas familias se nombran en una respuesta de capacidades. El resto sigue
# servido: el payload lo dice con `more`, no lo esconde.
CAPABILITY_SAMPLE = 6


def served_capability_families(operations: object) -> list[str]:
    """Familias servidas por el catálogo activo, en orden estable."""

    if not isinstance(operations, (list, tuple)):
        return []
    present: set[str] = set()
    for operation in operations:
        name = str(operation or "").strip()
        family = name.split(".", 1)[0].casefold()
        if family in CAPABILITY_FAMILIES:
            present.add(family)
    return [family for family in CAPABILITY_FAMILIES if family in present]


def _capability_phrases(families: object, language: str) -> list[str]:
    if not isinstance(families, (list, tuple)):
        return []
    index = 1 if language == "en" else 0
    phrases: list[str] = []
    for family in families:
        entry = CAPABILITY_FAMILIES.get(str(family or "").casefold())
        if entry is not None and entry[index] not in phrases:
            phrases.append(entry[index])
    return phrases
