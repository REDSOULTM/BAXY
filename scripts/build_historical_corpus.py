"""Build the traceable BAXY 1.0 historical-message corpus.

This extractor distinguishes observed user turns, curated historical cases,
acceptance examples, document requirements and engineering instructions.  It
keeps every occurrence and links semantic variants to compact, composable
operation families; it never treats agent-child prompts as user history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.freeze_historical_sources import (
    CUTOFF_UTC,
    canonical_digest,
    sha256_file,
)


REPO = Path(__file__).resolve().parent.parent
PROGRAMACION = REPO.parent
HOME = Path.home()
CUTOFF = datetime.fromisoformat("2026-07-14T10:51:49.161254+00:00")
CORPUS_SCHEMA_VERSION = 2
SEMANTIC_REVISION = "2026-07-15-audio-status-v3"
PRODUCT_LANGUAGE_SCOPE = ("es", "en", "spanglish")
PRODUCT_ACCEPTANCE_SCOPE = "product_1_0"
TRACE_ONLY_ACCEPTANCE_SCOPE = "trace_only_not_acceptance_commitment"
FROZEN_NON_TARGET_LANGUAGE_LABELS = frozenset({"de", "fr", "it", "pt"})

ROOTS = {
    "baxy": REPO,
    "baxy_legacy": REPO / "legacy",
    "probando_gemma4": PROGRAMACION / "Probando Gemma 4",
    "functiongemma": PROGRAMACION / "FunctionGemma",
    "carter_os_ai": PROGRAMACION / "Carter OS AI",
    "gemma4_local": HOME / ".gemma4",
}

SKIP_USER_TAGS = (
    "<environment_context>",
    "<permissions instructions>",
    "<app-context>",
    "<collaboration_mode>",
    "<skills_instructions>",
    "<apps_instructions>",
    "<plugins_instructions>",
)

SECRET_PATTERNS = (
    (
        re.compile(
            r"(?i)\b(password|contrase(?:n|ñ)a|token|api[_ -]?key|secret)\s*([:=])\s*([^\s,;]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)C:[\\/]Users[\\/][^\\/\s]+"), r"%USERPROFILE%"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL_REDACTED]",
    ),
    (re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)"), "[PHONE_REDACTED]"),
)


@dataclass(frozen=True)
class OperationSpec:
    patterns: tuple[str, ...]
    expected: str
    provider: str
    verification: str
    response: str
    fallback: str


@dataclass(frozen=True)
class OperationPolarity:
    """Catalog operations authorized and explicitly denied by the wording."""

    actionable_operations: tuple[str, ...]
    denied_operations: tuple[str, ...]
    kind: str


@dataclass(frozen=True)
class AcceptanceScopeOracle:
    """Manifest-bound evidence used to exclude non-target-language history."""

    source_decisions: dict[tuple[str, str], tuple[str, tuple[str, ...]]]
    cross_source_keys: frozenset[str]
    cross_source_normalized_keys: frozenset[str]
    labels_by_key: dict[str, tuple[str, ...]]
    source_files: tuple[tuple[str, str], ...]
    source_labeled_trace_only_locations: int
    cross_source_trace_only_keys: int
    cross_source_trace_only_normalized_keys: int
    exact_exception_keys: int
    target_wins_or_source_override_keys: int


OP_SPECS: dict[str, OperationSpec] = {
    "app.open": OperationSpec(
        (
            r"\b(abre|abrir|open|launch)\b.*\b(app|aplicaci[oó]n|chrome|discord|whatsapp|spotify|steam|word|excel|powerpoint|notepad|bloc de notas)\b",
        ),
        "La aplicación solicitada queda abierta y enfocada.",
        "app_adapter",
        "Proceso, identidad y ventana corroborados.",
        "Listo, abrí {target}.",
        "Buscar instalación o explicar qué aplicación falta.",
    ),
    "app.close": OperationSpec(
        (
            r"\b(cierra|cerrar|close|quit|sal de)\b.*\b(app|aplicaci[oó]n|chrome|discord|whatsapp|spotify|steam|word|excel|powerpoint|ventana)\b",
        ),
        "La aplicación objetivo queda cerrada sin perder trabajo.",
        "app_adapter",
        "Proceso/ventana ausentes y estado guardado protegido.",
        "Listo, cerré {target}.",
        "Si hay cambios sin guardar, preguntar qué hacer.",
    ),
    "window.manage": OperationSpec(
        (
            r"\b(minimiza|maximiza|restaura|mueve|redimensiona|enfoca|focus|switch|ventana|window)\b",
        ),
        "La ventana queda en el estado y posición pedidos.",
        "window_adapter",
        "HWND, título, proceso y geometría observados.",
        "Listo, ajusté la ventana.",
        "Resolver la ventana exacta o pedir desambiguación.",
    ),
    "audio.volume": OperationSpec(
        (
            r"\b(volumen|volume|sube el audio|baja el audio|m[aá]s fuerte|m[aá]s bajo)\b",
        ),
        "El volumen queda en el nivel solicitado.",
        "audio_adapter",
        "Nivel de sesión/dispositivo leído después del cambio.",
        "Listo, dejé el volumen como pediste.",
        "Elegir dispositivo o sesión si hay ambigüedad.",
    ),
    "audio.mute": OperationSpec(
        (r"\b(mute|silencia|silenciar|desmutea|unmute|sin sonido)\b",),
        "El estado de silencio coincide con la orden.",
        "audio_adapter",
        "Estado mute observado tras la acción.",
        "Listo, ajusté el silencio.",
        "Resolver el dispositivo o sesión objetivo.",
    ),
    "audio.status": OperationSpec(
        (
            r"^\s*(?:¿?\s*qu[eé] volumen tengo|mostrame el volumen|show me the volume|show me el volumen)[?!.]?\s*$",
        ),
        "Se informan el volumen y el silencio actuales de la salida predeterminada.",
        "audio_adapter",
        "Nivel y estado mute leídos de la salida predeterminada sin modificarla.",
        "El volumen actual es {target}.",
        "Explicar si no existe una salida predeterminada o el servicio de audio no está disponible.",
    ),
    "media.play": OperationSpec(
        (
            r"\b(pon|poner|reproduce|reproducir|play|escuchar|m[uú]sica|canci[oó]n|spotify)\b",
        ),
        "El contenido correcto está reproduciéndose.",
        "media_or_streaming_adapter",
        "Sesión multimedia confirma playing, título y artista cuando aplican.",
        "Listo, puse {target}.",
        "Reintentar la app y luego una ruta autorizada alternativa.",
    ),
    "media.control": OperationSpec(
        (
            r"\b(pausa|pause|reanuda|resume|siguiente|next|anterior|previous|det[eé]n|stop)\b.*\b(m[uú]sica|canci[oó]n|video|spotify|reproducci[oó]n)?\b",
        ),
        "La reproducción queda en el estado solicitado.",
        "media_adapter",
        "Estado SMTC/servicio observado.",
        "Listo, ajusté la reproducción.",
        "Resolver la sesión multimedia activa.",
    ),
    "streaming.navigate": OperationSpec(
        (r"\b(netflix|youtube|twitch|streaming|pel[ií]cula|serie)\b",),
        "El servicio muestra o reproduce el contenido solicitado.",
        "streaming_adapter",
        "URL/título y estado de reproducción corroborados.",
        "Listo, dejé {target} preparado.",
        "Buscar el contenido y explicar bloqueo de cuenta/región.",
    ),
    "web.search": OperationSpec(
        (
            r"\b(busca|buscar|investiga|investigar|search|googlea|averigua)\b.*\b(internet|web|google|online|por qu[eé]|informaci[oó]n)?\b",
        ),
        "Se obtienen resultados pertinentes a la consulta.",
        "web_adapter",
        "Consulta, página y contenido relevante verificados.",
        "Encontré esto: {target}.",
        "Probar otro buscador o explicar falta de conexión.",
    ),
    "browser.navigate": OperationSpec(
        (
            r"\b(navega|entra|abre|ve a|go to|open)\b.*\b(web|sitio|p[aá]gina|url|github|youtube|netflix|chrome|browser|navegador)\b",
        ),
        "El navegador queda en la página correcta.",
        "browser_adapter",
        "URL, título y contenido observados.",
        "Listo, abrí {target}.",
        "Usar otro navegador autorizado o devolver el enlace.",
    ),
    "reminder.create": OperationSpec(
        (r"\b(recu[eé]rdame|recordatorio|remind me|av[ií]same)\b",),
        "El recordatorio queda persistido con texto y hora correctos.",
        "reminder_adapter",
        "Store durable y próxima activación coinciden.",
        "Listo, te lo recordaré {target}.",
        "Pedir solo la fecha/hora realmente ambigua.",
    ),
    "calendar.manage": OperationSpec(
        (r"\b(calendario|calendar|evento|event|agenda|cita|meeting|reuni[oó]n)\b",),
        "El evento o consulta de calendario refleja la intención.",
        "calendar_adapter",
        "Registro, zona horaria y campos leídos de vuelta.",
        "Listo, actualicé tu calendario.",
        "Resolver fecha, cuenta o conflicto sin inventar.",
    ),
    "note.manage": OperationSpec(
        (r"\b(nota|note|anota|apunta|apunte)\b",),
        "La nota queda creada, consultada o actualizada correctamente.",
        "note_adapter",
        "Contenido y versión leídos del store.",
        "Listo, guardé la nota.",
        "Desambiguar por título o mostrar coincidencias.",
    ),
    "task.manage": OperationSpec(
        (r"\b(tarea|task|to-?do|pendiente)\b",),
        "La tarea queda en el estado solicitado.",
        "task_adapter",
        "Store confirma identidad, contenido y estado.",
        "Listo, actualicé la tarea.",
        "Desambiguar la tarea exacta.",
    ),
    "filesystem.search": OperationSpec(
        (
            r"\b(busca|buscar|encuentra|find|search)\b.*\b(archivo|file|carpeta|folder|documento)\b",
        ),
        "Se localizan los archivos que cumplen la consulta.",
        "filesystem_adapter",
        "Existencia, ruta y filtros corroborados.",
        "Encontré {target}.",
        "Ampliar el ámbito o pedir una pista concreta.",
    ),
    "filesystem.read": OperationSpec(
        (r"\b(lee|leer|read|muestra|abre)\b.*\b(archivo|file|documento|contenido)\b",),
        "Se obtiene el contenido solicitado sin modificarlo.",
        "filesystem_adapter",
        "Hash/ruta y lectura completa comprobados.",
        "Aquí tienes lo que encontré.",
        "Explicar permisos, formato o corrupción.",
    ),
    "filesystem.write": OperationSpec(
        (
            r"\b(crea|crear|escribe|guardar|save|write)\b.*\b(archivo|file|carpeta|folder|documento)\b",
        ),
        "El contenido recuperable queda escrito en la ruta correcta.",
        "filesystem_adapter",
        "Existencia, hash y contenido releído.",
        "Listo, guardé {target}.",
        "Escribir temporalmente o proponer otra ruta.",
    ),
    "filesystem.transfer": OperationSpec(
        (
            r"\b(copia|copiar|copy|mueve|mover|move|renombra|rename)\b.*\b(archivo|file|carpeta|folder|documento)\b",
        ),
        "Los elementos quedan en el destino correcto sin pérdida.",
        "filesystem_adapter",
        "Origen/destino, hashes y conteos corroborados.",
        "Listo, moví los archivos.",
        "Reanudar o compensar la transferencia parcial.",
    ),
    "filesystem.trash": OperationSpec(
        (
            r"\b(borra|borrar|elimina|delete|remove|papelera|trash)\b.*\b(archivo|file|carpeta|folder|documento)\b",
        ),
        "El elemento va a la Papelera salvo solicitud irreversible confirmada.",
        "filesystem_adapter",
        "Ausencia en origen y presencia recuperable verificadas.",
        "Listo, lo moví a la Papelera.",
        "Bloquear rutas protegidas o pedir confirmación irreversible.",
    ),
    "office.document": OperationSpec(
        (
            r"\b(word|excel|powerpoint|office|documento|document|presentaci[oó]n|spreadsheet|planilla)\b",
        ),
        "El documento queda abierto o editado con el contenido pedido.",
        "office_adapter",
        "Aplicación, documento, contenido y estado Saved/Dirty corroborados.",
        "Listo, avancé con el documento.",
        "Usar formato abierto o preguntar requisitos faltantes.",
    ),
    "message.send": OperationSpec(
        (
            r"\b(manda|mandar|env[ií]a|enviar|send|escribele|dile)\b.*\b(mensaje|message|whatsapp|discord|slack|teams|correo|email|mail|a )\b",
        ),
        "La comunicación correcta queda preparada o enviada al destinatario corroborado.",
        "messaging_adapter",
        "Destinatario, contenido y estado de envío observados.",
        "Listo, envié el mensaje a {target}.",
        "Preparar borrador o pedir destinatario/contenido ambiguo.",
    ),
    "system.status": OperationSpec(
        (
            r"\b(estado del pc|pc status|cpu|ram|gpu|bater[ií]a|battery|temperatura|temperature|espacio en disco|disk space)\b",
        ),
        "Se informa el estado actual medido del equipo.",
        "system_adapter",
        "Métricas leídas de fuentes del sistema.",
        "Tu PC está {target}.",
        "Explicar qué sensor o permiso no está disponible.",
    ),
    "system.settings": OperationSpec(
        (
            r"\b(brillo|brightness|configura|setting|ajuste|plan de energ[ií]a|refresh rate|resoluci[oó]n)\b",
        ),
        "El ajuste del sistema queda en el valor solicitado.",
        "system_adapter",
        "Valor leído después de aplicar.",
        "Listo, ajusté {target}.",
        "Explicar limitación de hardware o privilegios.",
    ),
    "system.power": OperationSpec(
        (
            r"\b(apaga|shutdown|reinicia|restart|reboot|suspende|sleep|hiberna|lock|bloquea el pc)\b",
        ),
        "El equipo entra al estado de energía autorizado.",
        "system_adapter",
        "Evento del sistema o transición observada.",
        "De acuerdo, {target}.",
        "Proteger trabajo no guardado y confirmar si corresponde.",
    ),
    "wifi.manage": OperationSpec(
        (r"\b(wi-?fi|wifi|ssid|red inal[aá]mbrica)\b",),
        "La conexión Wi-Fi queda en el estado solicitado.",
        "network_adapter",
        "Adaptador, perfil, SSID y conectividad corroborados.",
        "Listo, ajusté el Wi-Fi.",
        "Pedir credencial solo si no existe un perfil guardado.",
    ),
    "bluetooth.manage": OperationSpec(
        (r"\b(bluetooth|empareja|pair|dispositivo inal[aá]mbrico)\b",),
        "El dispositivo Bluetooth queda conectado o gestionado.",
        "device_adapter",
        "Estado del dispositivo y enlace corroborados.",
        "Listo, ajusté Bluetooth.",
        "Resolver el dispositivo exacto o explicar permisos.",
    ),
    "package.install": OperationSpec(
        (
            r"\b(instala|instalar|install|desinstala|uninstall|actualiza|update)\b.*\b(app|aplicaci[oó]n|programa|software|paquete|package)\b",
        ),
        "El software confiable queda instalado/actualizado o se explica el bloqueo real.",
        "package_adapter",
        "Fuente, versión, proceso y registro de instalación verificados.",
        "Listo, instalé {target}.",
        "Confirmar solo costo, fuente desconocida o permisos peligrosos.",
    ),
    "game.install": OperationSpec(
        (
            r"\b(inst[aá]l\w*|install\w*|descarg\w*|download\w*|desinstal\w*|uninstall\w*)\b.*\b(juego|game|steam|epic|xbox|arkham|batman)\b",
        ),
        "El estado de instalación o descarga del juego coincide con lo solicitado, sin efectuar compras no confirmadas.",
        "game_adapter",
        "Propiedad, espacio, manifest, estado instalado y progreso corroborados.",
        "Listo, dejé {target} en el estado de instalación solicitado.",
        "Si requiere compra, falta espacio o hay datos locales en riesgo, detenerse y explicar la decisión necesaria.",
    ),
    # The frozen corpus assigns this family through an audited literal oracle
    # below. Keeping the lexical matcher empty prevents generic words such as
    # "library", "store" or "search" from silently changing unrelated rows.
    "game.manage": OperationSpec(
        (),
        "El cliente de juegos queda en la superficie solicitada o devuelve el estado real pedido, sin lanzar ningún juego ni iniciar una instalación que no esté autorizada por game.install.",
        "game_adapter",
        "Cliente/cuenta, vista o consulta, juego objetivo y estado devuelto corroborados; ausencia de proceso de juego o descarga nueva cuando no fue autorizada.",
        "Listo, dejé {target} en el cliente de juegos.",
        "Probar deeplink o API local y luego UI verificada; si falta sesión o cliente, explicar el bloqueo sin lanzar ni instalar.",
    ),
    "game.purchase": OperationSpec(
        (),
        "La selección, el precio y la cuenta quedan corroborados; ninguna compra se completa sin confirmación explícita y recibo verificable.",
        "game_adapter",
        "Producto, precio total, cuenta, confirmación y recibo/estado de orden corroborados.",
        "Tengo {target} preparado; necesito tu confirmación antes de completar la compra.",
        "Detenerse antes del compromiso monetario si cambian precio, cuenta, región o producto.",
    ),
    "game.launch": OperationSpec(
        (r"\b(abre|juega|inicia|launch|play)\b.*\b(juego|game|steam|epic|xbox)\b",),
        "El juego correcto queda iniciado.",
        "game_adapter",
        "Proceso, AppID y ventana corroborados.",
        "Listo, abrí {target}.",
        "Resolver propiedad, instalación o launcher.",
    ),
    "vision.describe": OperationSpec(
        (
            r"\b(qu[eé] ves|mira|describe|pantalla|screen|imagen|image|c[aá]mara|camera|visi[oó]n)\b",
        ),
        "BAXY describe únicamente lo corroborado de pantalla/imagen.",
        "vision_adapter",
        "Captura, ventana/proceso y señales visuales ligadas.",
        "Veo {target}.",
        "Decir que no puede identificarlo y pedir otra señal.",
    ),
    "ocr.read": OperationSpec(
        (r"\b(ocr|lee el texto|read the text|texto de la imagen|texto en pantalla)\b",),
        "Se transcribe el texto visible con incertidumbre explícita.",
        "ocr_adapter",
        "OCR contrastado con región/captura y, cuando aplica, UIA.",
        "El texto dice: {target}.",
        "Aumentar resolución o pedir una región concreta.",
    ),
    "capture.screenshot": OperationSpec(
        (r"\b(captura|screenshot|pantallazo|captura de pantalla)\b",),
        "La captura solicitada queda creada localmente.",
        "capture_adapter",
        "Archivo, dimensiones, timestamp y región corroborados.",
        "Listo, tomé la captura.",
        "Pedir ventana/región si hay contenido sensible ambiguo.",
    ),
    "memory.save": OperationSpec(
        (
            r"\b(recuerda|record[aá]|acu[eé]rdate|remember|me llamo|mi nombre es|prefiero)\b",
        ),
        "El hecho o preferencia queda guardado con procedencia y confianza.",
        "memory_adapter",
        "Memoria releída con tipo, fuente y expiración.",
        "Lo recordaré.",
        "Pedir precisión o guardar como contexto temporal.",
    ),
    "memory.recall": OperationSpec(
        (
            r"\b(qu[eé] recuerdas|c[oó]mo me llamo|what do you remember|mi preferencia|recall|qu[eé].*(?:me gusta|favorit)|what(?:'s| is) my favorite)\b",
        ),
        "Se recupera solo memoria local pertinente.",
        "memory_adapter",
        "Respuesta ligada a entradas locales vigentes.",
        "Recuerdo que {target}.",
        "Decir honestamente que no hay memoria suficiente.",
    ),
    "memory.forget": OperationSpec(
        (
            r"\b(olvida|forget|borra.*(?:memoria|preferencia|favorit)|elimina.*(?:recuerdo|preferencia|favorit)|delete.*favorite)\b",
        ),
        "La memoria indicada queda eliminada o corregida.",
        "memory_adapter",
        "Entrada ausente y evento de borrado registrado.",
        "Listo, lo olvidé.",
        "Desambiguar qué recuerdo debe borrarse.",
    ),
    "clipboard.manage": OperationSpec(
        (r"\b(portapapeles|clipboard|copia esto|paste|pega)\b",),
        "El portapapeles queda en el estado pedido.",
        "clipboard_adapter",
        "Contenido/tipo corroborado sin exponer secretos.",
        "Listo, actualicé el portapapeles.",
        "Bloquear o redactar contenido sensible.",
    ),
    "notification.manage": OperationSpec(
        (r"\b(notificaci[oó]n|notification|alarma|alarm|timer|temporizador)\b",),
        "La notificación/alarma queda programada o gestionada.",
        "notification_adapter",
        "Store y scheduler confirman identidad y hora.",
        "Listo, quedó programado.",
        "Pedir hora solo si cambia el resultado.",
    ),
    "routine.manage": OperationSpec(
        (r"\b(rutina|routine|h[aá]bito|habit|todos los d[ií]as|cada semana)\b",),
        "La rutina queda persistida con recurrencia correcta.",
        "routine_adapter",
        "Regla, próxima ejecución y estado leídos de vuelta.",
        "Listo, guardé la rutina.",
        "Resolver zona horaria o recurrencia ambigua.",
    ),
    "backup.manage": OperationSpec(
        (r"\b(backup|respaldo|copia de seguridad|restaura|restore|sincroniza|sync)\b",),
        "Los datos quedan respaldados/restaurados con integridad comprobada.",
        "backup_adapter",
        "Conteo, hashes y destino corroborados.",
        "Listo, completé el respaldo.",
        "Reanudar, verificar espacio o usar destino alternativo.",
    ),
    "peripheral.manage": OperationSpec(
        (
            r"\b(impresora|printer|scanner|esc[aá]ner|micr[oó]fono|microphone|webcam|perif[eé]rico)\b",
        ),
        "El periférico queda consultado o configurado como se pidió.",
        "device_adapter",
        "Identidad y estado del dispositivo corroborados.",
        "Listo, ajusté el dispositivo.",
        "Resolver dispositivo, driver o permiso.",
    ),
}

COMPILED_OPS = {
    name: tuple(re.compile(pattern, re.IGNORECASE) for pattern in spec.patterns)
    for name, spec in OP_SPECS.items()
}

REQUIREMENT_TAGS = {
    "voice": r"\b(voz|voice|wake word|stt|tts|micr[oó]fono|barge)\b",
    "vision": r"\b(visi[oó]n|vision|ocr|pantalla|screen|c[aá]mara)\b",
    "gui": r"\b(gui|interfaz|interface|dise[nñ]o visual|webview|tauri|react)\b",
    "tools": r"\b(tool|herramienta|operaci[oó]n|provider|workflow|router|planner)\b",
    "verification": r"\b(verifica|verify|estado real|no finj|no diga.*listo)\b",
    "safety": r"\b(seguridad|safety|confirmaci[oó]n|riesgo|privacidad|privacy|destructiv)\b",
    "memory": r"\b(memoria|memory|preferencia|h[aá]bito)\b",
    "resources": r"\b(vram|ram|gpu|4 gb|3 gb|latencia|recursos|cpu fallback)\b",
    "packaging": r"\b(instalador|installer|empaquet|package|actualizaci[oó]n|rollback|desinstal)\b",
    "testing": r"\b(test|prueba|gate|acceptance|smoke|soak|regresi[oó]n)\b",
    "history": r"\b(hist[oó]ric|carter|functiongemma|legacy|genealog[ií]a|corpus)\b",
    "personality": r"\b(jarvis|amigable|personalidad|natural|emocional|spanglish)\b",
    "architecture": r"\b(arquitectura|architecture|stack|\.net|rust|python|ipc|llama\.cpp|gemma)\b",
}


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"^(?:hey\s+)?(?:baxy|baxi|carter|gemma)[,.:!\s]+", "", value)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def sorted_line_digest(values: Iterable[str]) -> str:
    payload = "".join(f"{value}\n" for value in sorted(values))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def redact(text: str) -> tuple[str, bool]:
    result = text.replace("\x00", "")
    changed = result != text
    for pattern, replacement in SECRET_PATTERNS:
        result, count = pattern.subn(replacement, result)
        changed = changed or bool(count)
    return result.strip(), changed


def acceptance_scope_key(text: str) -> str:
    """Redacted exact-text key for cross-source language evidence."""
    literal, _ = redact(text)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", literal).casefold()).strip()


def language(text: str) -> str:
    folded = normalize(text)
    es = len(
        re.findall(
            r"\b(el|la|que|de|por|para|abre|cierra|quiero|puedes|debe|m[uú]sica|archivo)\b",
            folded,
        )
    )
    en = len(
        re.findall(
            r"\b(the|what|how|please|open|close|play|search|file|should|can you)\b",
            folded,
        )
    )
    if es and en:
        return "spanglish"
    if es:
        return "es"
    if en:
        return "en"
    return "other"


def operation_names(text: str) -> list[str]:
    return sorted(
        name
        for name, patterns in COMPILED_OPS.items()
        if any(p.search(text) for p in patterns)
    )


_FROZEN_NO_ACTION_DENIALS: dict[str, frozenset[str]] = {
    "no subas el volumen": frozenset({"audio.volume"}),
    "no cierres spotify": frozenset({"app.close"}),
    "don t open chrome": frozenset({"app.open", "browser.navigate"}),
    "no bajes el brillo": frozenset({"system.settings"}),
    "no pongas musica": frozenset({"media.play"}),
    "evita ocr repetido si uia entrega texto": frozenset({"ocr.read"}),
    "no abras nada solo dime si spotify esta instalado": frozenset({"app.open"}),
    "no abras spotify solo decime si esta instalado": frozenset({"app.open"}),
    "no consultes pantalla para responder esto hola": frozenset({"vision.describe"}),
    "no hagas diagnostico de todo el pc por una pregunta simple": frozenset(
        {"system.status"}
    ),
    "no uses lo que estaba en la ventana activa para responder esto": frozenset(
        {"window.manage"}
    ),
    "no uses vision para esto": frozenset({"vision.describe"}),
    "nunca cierres spotify": frozenset({"app.close"}),
    "si pantalla esta bloqueada no intentes acciones": frozenset(),
    "no abras nada solo dime como buscar un archivo": frozenset({"app.open"}),
    "no quiero que uses el navegador solo decime como buscar python yo mismo": frozenset(
        {"browser.navigate"}
    ),
    "no uses lo anterior": frozenset(),
    "solo responde no uses herramientas abre steam": frozenset({"app.open"}),
    "no abras juegos pesados durante suite minima": frozenset({"game.launch"}),
    "stop don t do it": frozenset(),
}

_FROZEN_PARTIAL_DENIALS: dict[str, frozenset[str]] = {
    "abre youtube busca musica lofi y no reproduzcas nada": frozenset({"media.play"}),
    "abre steam pero no maximices ni lances juegos": frozenset(
        {"game.launch", "window.manage"}
    ),
    "open steam but do not launch any game": frozenset({"game.launch"}),
    "abre steam store de batman en navegador no app": frozenset(
        {"app.open", "game.launch", "game.manage"}
    ),
    "abri la steam store de batman en el navegador no en la app de steam": frozenset(
        {"app.open", "game.launch", "game.manage"}
    ),
    "dejalo asi no toques streaming en la imagen habian mas probelmas arreglalo": frozenset(
        {"streaming.navigate"}
    ),
    "si la ram esta alta no cargues vision": frozenset({"vision.describe"}),
    "busca batman en steam sin abrir juego": frozenset({"game.launch"}),
    "busca hades en mi biblioteca no lo ejecutes": frozenset({"game.launch"}),
    "dime si marvel rivals esta instalado sin abrirlo": frozenset({"game.launch"}),
    "cerca batman su steam senza aprire nessun gioco": frozenset({"game.launch"}),
    "pero la busqueda hacela en la app de steam no en la web": frozenset(
        {"web.search"}
    ),
    "abre la pagina de tienda de un juego no compres nada": frozenset(
        {"game.purchase"}
    ),
    "si batman no esta en biblioteca dime eso sin comprar nada": frozenset(
        {"game.purchase"}
    ),
    (
        "usa control f enter escribir mensaje es asi de simple no uses ocr "
        "es un gasto de latencia innecesario"
    ): frozenset({"ocr.read"}),
}

_FROZEN_ENGINEERING_POLARITY_LITERALS = frozenset(
    {
        (
            "usa control f enter escribir mensaje es asi de simple no uses ocr "
            "es un gasto de latencia innecesario"
        )
    }
)

# These are observed diagnostic payloads, not commands to execute.  IDs bind
# the exception to the frozen source occurrence so matching transcript lines
# remain valid missions when they appear as standalone user turns.
_FROZEN_ENGINEERING_MESSAGE_IDS = frozenset({"msg_43ba649bfe2f0db1366e"})

# This frozen occurrence is a hypothetical question about what an assistant
# would do, not an instruction to install a game or play media.
_FROZEN_CONVERSATION_MESSAGE_IDS = frozenset({"msg_513b25ade5b30e155623"})

# Exact audit exceptions for non-target scripts whose upstream ``lang`` label
# is absent or incorrect.  The main DE/FR/IT/PT oracle is derived from the
# manifest-bound train_v3 source in ``build_acceptance_scope_oracle``.
_FROZEN_TRACE_ONLY_SCOPE_EXCEPTIONS = frozenset(
    acceptance_scope_key(literal)
    for literal in (
        "你好",
        "你是谁",
        "你是什么",
        "现在几点",
        "我的IP是什么",
        "привет",
        "“Адам болмок аста-аста, айбан болмок бир паста” деген макалды түшүндүрүп берчи.",
        "请你给我写一个面试准备计划，我想要去面试微软的程序员岗位",
    )
)

# Some foreign-labelled surfaces are also valid ES/EN/Spanglish.  Thirteen
# audited target overrides stay in product scope even at their source; the
# remaining language-bearing homographs stay source-bound and do not propagate
# unless their exact raw spelling is independently safe below.
_FROZEN_CROSS_SOURCE_TARGET_HOMOGRAPHS = frozenset(
    {
        "a ana",
        "a chiara",
        "a sofia",
        "abre photoshop",
        "apaga",
        "ciao",
        "continua tocando",
        "da play",
        "ja",
        "oi",
        "ola",
        "oui",
        "para john",
        "para mama",
        "para pedro",
        "para sofia",
        "pausa",
        "procura lofi",
        "proxima musica",
        "salve",
        "silence",
        "sim",
        "vincenzo",
    }
)

_FROZEN_CROSS_SOURCE_SAFE_NON_TARGET_LITERALS = frozenset(
    acceptance_scope_key(literal)
    for literal in (
        "à Ana",
        "à Sofía",
        "ciao",
        "dá play",
        "Ja",
        "Oi!",
        "olá",
        "Oui",
        "Salve",
        "Sim",
    )
)

_FROZEN_SOURCE_TARGET_OVERRIDES = frozenset(
    {
        "",
        "a chiara",
        "abre photoshop",
        "apaga",
        "ahah",
        "continua tocando",
        "para john",
        "para mama",
        "para pedro",
        "para sofia",
        "pausa",
        "procura lofi",
        "proxima musica",
        "silence",
        "haha",
        "vincenzo",
    }
)

_FROZEN_ROUTER_EVAL_NON_TARGET_RANGES = (
    (1741, 1747),
    (1754, 1768),
    (1777, 1781),
    (1788, 1799),
    (1807, 1812),
    (1819, 1830),
    (1834, 1837),
    (1839, 1840),
    (1845, 1850),
    (1856, 1856),
    (1858, 1860),
    (2072, 2102),
)

_FROZEN_ROUTER_EVAL_NON_TARGET_RESIDUALS = frozenset(
    {
        "abre o chrome",
        "erstelle eine notiz dass ich brot kaufen muss",
        "fecha o bloco de notas",
        "mach die lautstarke lauter",
        "mets le volume a 95",
        "qual e il mio ip",
        "qual o meu ip",
        "quelle est mon ip",
        "qui es tu",
        "was ist meine ip",
    }
)

_FROZEN_TRAIN_MISLABELED_NON_TARGET_LINES = frozenset(
    {
        4457,
        4460,
        4548,
        4570,
        4603,
        4613,
        4632,
        4652,
        4656,
        4678,
        5118,
        5121,
    }
)


_DIRECT_GAME_FROM_STEAM = re.compile(
    r"^(?:abre|open|lanza|launch)\s+(?!steam\b).{1,80}\s+(?:desde|from)\s+steam$"
)
_STEAM_AND_EXPLICIT_GAME = re.compile(
    r"^(?:abre|open)\s+steam\b.{0,120}\b"
    r"(?:ejecuta|juega|lanza|launch|play|run)\b.{1,100}$"
)
_STEAM_STORE_IN_BROWSER = re.compile(
    r"^abre\s+steam\s+store\b.{0,100}\b(?:en\s+)?navegador\b"
)
_NEGATED_GAME_LAUNCH = re.compile(
    r"\b(?:no|nunca|jamas|don\s+t|do\s+not|never)\s+"
    r"(?:ejecut\w*|jueg\w*|lanz\w*|launch\w*|play\w*|run\w*)\b"
)
_MEDIA_PLAY_EVIDENCE = re.compile(
    r"\b(?:musica|cancion|spotify|track|song|playlist|rock|jazz|podcast|video|"
    r"radio|album|audiolibro|reproduc\w*|play\w*|escuch\w*|toca\w*)\b"
)
_FROZEN_OPERATION_OVERRIDE_GROUPS: tuple[
    tuple[frozenset[str], tuple[str, ...]], ...
] = (
    (
        frozenset({"audio.status"}),
        (
            "mostrame el volumen",
            "que volumen tengo",
            "show me el volumen",
            "show me the volume",
        ),
    ),
    # Catalog notation from an acceptance document, not a user request to
    # uninstall Steam.  Keep the generic uninstall matcher reusable without
    # turning this frozen schema fragment into an executable effect.
    (
        frozenset(),
        ("app uninstall steam install",),
    ),
    (
        frozenset({"app.open", "game.install", "game.manage"}),
        (
            "abre steam busca el juego y empieza la descarga",
            "abre steam busca un juego gratuito e inicia la instalacion usando la gui si hace falta",
            "abre steam revisa si un juego ya esta instalado y si no lo esta inicia la instalacion",
        ),
    ),
    (
        frozenset({"app.open", "game.manage"}),
        (
            "abre epic games y busca rocket league",
            "abre epic games y dime si fortnite esta instalado",
            "abre epic games y navega hasta la biblioteca",
            "abre o steam vai na biblioteca procura batman e me diz se esta instalado",
            "abre stema y busca batman en mi biblio",
            "abre steam click biblioteca escribe batman",
            "abre steam en modo biblioteca",
            "abre steam pls y ponme en la pagina de la tienda de marvel rivals",
            "abre steam ve a biblioteca busca batman y dime si esta instalado",
            "abre steam ve a biblioteca y busca batman",
            "abre steam ve a la biblioteca y busca juegos de batman",
            "abre steam y busca counter strike",
            "abre steam y busca fall guys",
            "abre steam y dime si fall guys ya esta instalado",
            "abre steam y entra a la biblioteca",
            "abre steam y luego navega por la gui hasta biblioteca",
            "abre steam y ve a biblioteca",
            "abre steam y ve a mi biblioteca",
            "abre steam y ve a tienda",
            "abre un launcher de juegos que tengas instalado y dime que juegos aparecen como instalados",
            "entra a steam ve a mi biblioteca y busca juegos de batman",
            "entra a steam y busca juegos de batman en mi biblioteca",
        ),
    ),
    (
        frozenset({"game.manage"}),
        (
            "abre a loja do steam",
            "abre big picture",
            "abre capturas de steam",
            "abre el chat de zhino en steam pls quiero hablar con el",
            "abre la tienda de steam y busca batman",
            "abre mi biblioteca de steam",
            "abre overlay de steam",
            "abre propiedades de portal en steam",
            "abre propiedades de un juego instalado",
            "abre propiedades de un juego solo si esta seleccionado",
            "abre steam library",
            "agora procura batman na minha biblioteca",
            "ahora busca batman en mi biblioteca",
            "apri la libreria di steam",
            "busca batman en biblioteca de steam",
            "busca batman en biblioteca steam",
            "busca batman en campo visible de steam",
            "busca batman en la tienda de steam",
            "busca batman en mi biblioteca de steam",
            "busca batman en steam",
            "busca batman en steam sin abrir juego",
            "busca batman en steam store",
            "busca batmn en steam",
            "busca en biblioteca y dime si no aparece",
            "busca en mi biblioteca de steam todos los juegos tipo metroidvania",
            "busca hades en mi biblioteca no lo ejecutes",
            "busca hollow knight en la tienda de steam",
            "busca juego instalado hades",
            "busca juegos de batman para comprar",
            "busca juegos gratis en steam",
            "busca juegos instalados con batman",
            "busca marvel rivals en steam",
            "busca ofertas de juegos de batman",
            "busca portal en la tienda de steam",
            "busca portal en mi biblioteca",
            "busca precio de hades en steam",
            "busca skyrim en mi biblioteca y si no esta buscalo en la tienda",
            "busca un juego que contenga bat en mi biblioteca",
            "buska batmn en steam",
            "cerca batman su steam senza aprire nessun gioco",
            "cerca tra i giochi installati quelli con batman",
            "cherche batman sur steam",
            "cuanto cuesta hades en steam",
            "cancela cualquier accion pendiente de compra instalacion",
            "deja steam como estaba antes de la prueba",
            "detecta si steam esta en biblioteca o tienda",
            "dime si hay descargas activas en steam",
            "dime si marvel rivals esta instalado sin abrirlo",
            "en steam escribe batman en busqueda de biblioteca",
            "esta instalado hades",
            "esta instalado fall guys",
            "fall guys esta instalado",
            "filtra mis juegos por instalados",
            "geh zum shop in steam",
            "go to my library",
            "haz clic en biblioteca en steam",
            "haz clic en biblioteca",
            "juegos de batman para comprar",
            "limpia el texto de busqueda de biblioteca",
            "navega a biblioteca desde steam visible",
            "ordena biblioteca por instalados si la ui lo permite",
            "ordena mi biblioteca por instalados",
            "pero la busqueda hacela en la app de steam no en la web",
            "podes ir al juego team sonic racing en steam",
            "puedes ver si tengo comprado ese juego en steam",
            "que juegos tengo",
            "que juegos de steam tengo instalados",
            "quiero saber si batman esta en steam",
            "quiero ver lo nuevos juegos de steam",
            "search batman on steam",
            "search for batman in my steam library",
            "si batman no esta en biblioteca dime eso sin comprar nada",
            "si batman no esta instalado buscalo en la tienda",
            "trie ma bibliotheque par jeux installes",
            "ve a la biblioteca de steam",
            "ve a la biblioteca en steam",
            "ve a la tienda de steam",
            "ve a la tienda en steam",
            "ve a mi biblioteca",
            "ve a mi bilioteca en steam",
            "ver la biblioteca de steam",
            "verifica si tengo batman instalado",
            "verifica si steam tiene descargas en curso",
            "vuelve desde tienda a biblioteca",
            "y en mi biblioteca",
        ),
    ),
    (
        frozenset({"browser.navigate"}),
        (
            "abre la pagina de tienda de un juego no compres nada",
            "abre pagina de batman arkham en steam",
            "abre la pagina de steam de marvel rivals",
            "abre la pagina de marvel rivals en steam",
            "abri la steam store de batman en el navegador no en la app de steam",
            "ponme en la pagina de la tienda de marvel rivals",
        ),
    ),
    (
        frozenset({"game.purchase"}),
        (
            "agrega un juego gratis al carrito",
            "compra este juego en steam",
            "compra portal en steam",
            "digame compralo",
            "quiero comprar el red sin evil rey quidem pero compralo por mi por favor compralo en steam",
        ),
    ),
    (
        frozenset({"app.open", "game.install"}),
        (
            "abre steam y instala fall guys",
            "abri steam e instala doom",
            "abri steam y pone a instalar el hollow knight",
            "open steam and install stardew valley",
        ),
    ),
    (
        frozenset({"game.install"}),
        (
            "baja doom eternal en steam",
            "confirmo",
            "descarga worms rumble en seam",
            "desinstala fall guys de steam",
            "desinstala portal",
            "desinstala un juego de steam",
            "desinstala worms rumble en steam",
            "es que mas instalame sifu en steve",
            "instala hades",
            "instala mortal kombat 11",
            "instalala pls",
            "instalame el doom eternal",
            "instalame el terraria",
            "pero te pedi que lo instalaras",
            "te pedi que lo instales no que habras la pagina",
            "quiero que lo instales ya lo tengo comprado",
            "y gemma puedes instalarlo",
        ),
    ),
    (
        frozenset({"game.launch"}),
        (
            "abre counter strike",
            "abre el ultimo juego que jugue",
            "abre lego batman",
            "abre marvel rivalds",
            "abre marvel rivals",
            "abre marvel rivals si esta instalado",
            "abre portal desde steam",
            "abre saints row",
            "abre steam role",
            "abri fall guys",
            "abrime el fifa",
            "ejecuta batman si esta instalado",
            "ejecuta batman si lo tengo instalado",
            "ejecuta hades en steam",
            "juega cualquier cosa",
            "lanza cualquier juego",
            "lanza el ultimo juego que jugue",
            "lanza mortal kombat",
            "lanza mortal kombat en steam",
            "lanza un juego liviano de prueba solo si esta marcado como permitido",
            "launch hollow knight",
            "open lego batman",
            "pero por que carajo no me abriste el juego abrilo ya",
            "why the hell didn t you open the game open it now",
            "y quema abre saint rose",
            "y si lanzalo",
            "ya lo tengo comprado",
            "yes launch it",
        ),
    ),
    (
        frozenset({"app.open", "game.launch"}),
        ("abre steam y ejecuta el juego instalado portal",),
    ),
    (
        frozenset({"app.open"}),
        (
            "abre epic games launcher",
            "abre epic games",
        ),
    ),
)


def _build_frozen_operation_overrides() -> dict[str, frozenset[str]]:
    overrides: dict[str, frozenset[str]] = {}
    for operations, literals in _FROZEN_OPERATION_OVERRIDE_GROUPS:
        unknown = operations - OP_SPECS.keys()
        if unknown:
            raise RuntimeError(f"Unknown frozen operation override: {sorted(unknown)}")
        for literal in literals:
            if literal != normalize(literal):
                raise RuntimeError(
                    f"Frozen operation literal is not normalized: {literal!r}"
                )
            if literal in overrides:
                raise RuntimeError(f"Duplicate frozen operation literal: {literal!r}")
            overrides[literal] = operations
    return overrides


_FROZEN_OPERATION_OVERRIDES = _build_frozen_operation_overrides()


def disambiguate_operation_candidates(
    text: str, operations: Iterable[str]
) -> list[str]:
    """Remove audited lexical collisions without interpreting negation.

    The broad historical matcher intentionally favors recall.  This second
    layer handles only independently enumerated collisions, so a new rule must
    come with a corpus oracle instead of silently changing unrelated messages.
    """
    resolved = set(operations)
    folded = normalize(text)
    if (
        "media.play" in resolved
        and "audio.volume" in resolved
        and re.search(r"\b(?:pon\w*|set)\b.{0,40}\b(?:volumen|volume)\b", folded)
        and not _MEDIA_PLAY_EVIDENCE.search(folded)
    ):
        resolved.remove("media.play")
    if "app.open" in resolved and "game.launch" in resolved:
        direct_game = bool(_DIRECT_GAME_FROM_STEAM.fullmatch(folded))
        explicit_game = bool(
            direct_game
            or (
                _STEAM_AND_EXPLICIT_GAME.fullmatch(folded)
                and not _NEGATED_GAME_LAUNCH.search(folded)
            )
        )
        if not explicit_game:
            resolved.remove("game.launch")
        if direct_game or _STEAM_STORE_IN_BROWSER.search(folded):
            resolved.remove("app.open")
    if folded in _FROZEN_OPERATION_OVERRIDES:
        resolved = set(_FROZEN_OPERATION_OVERRIDES[folded])
    return sorted(resolved)


def resolve_operation_polarity(text: str) -> OperationPolarity:
    """Resolve only audited, frozen-corpus effect denials.

    A previous generic clause regex overreached into preferences, summaries and
    documentation.  The finite 1.0 corpus therefore uses explicit semantic
    oracles: operation matching remains reusable, while every polarity rewrite
    is reviewable and its affected message IDs are asserted by tests.
    """
    folded = normalize(text)
    raw_operations = set(operation_names(text))
    operations = set(disambiguate_operation_candidates(text, raw_operations))
    if folded in _FROZEN_NO_ACTION_DENIALS:
        denied = _FROZEN_NO_ACTION_DENIALS[folded]
        return OperationPolarity((), tuple(sorted(denied)), "no_action")

    denied = set(_FROZEN_PARTIAL_DENIALS.get(folded, ()))
    actionable = operations - denied
    if denied and actionable:
        kind = "partial"
    elif denied:
        kind = "constraint"
    else:
        kind = "actionable"
    return OperationPolarity(
        tuple(sorted(actionable)),
        tuple(sorted(denied)),
        kind,
    )


def requirement_tags(text: str) -> list[str]:
    return sorted(
        name
        for name, pattern in REQUIREMENT_TAGS.items()
        if re.search(pattern, text, re.I)
    )


def classify(
    text: str, origin: str, operations: list[str], *, effect_denied: bool = False
) -> str:
    folded = normalize(text)
    tech_hits = len(
        re.findall(
            r"\b(repo|commit|branch|c[oó]digo|arquitectura|stack|tests?|documentaci[oó]n|agente|prompt|implementa|investiga|benchmark|pull request)\b",
            text,
            re.I,
        )
    )
    if origin in {"observed_user", "current_request"} and (
        tech_hits >= 2 or (len(text) > 600 and tech_hits)
    ):
        return "engineering_instruction"
    if re.search(
        r"\b(system32|destruye|compromet|malware|roba credenciales|disable.*antivirus)\b",
        text,
        re.I,
    ):
        return "safety_instruction"
    if re.search(
        r"\b(baxy|carter)\b.{0,100}\b(debe|deber[aá]|tiene que|nunca|no debe|should|must)\b",
        text,
        re.I | re.S,
    ):
        return "product_requirement"
    if re.search(
        r"\b(no funciona|fall[oó]|falla|incorrect|demora|lento|0 capacidades|no me gusta|se rompi[oó]|bug)\b",
        text,
        re.I,
    ):
        return "feedback_failure"
    if re.search(
        r"\b(prefiero|me gusta|mi favorita|siempre quiero|i prefer|my favorite)\b",
        text,
        re.I,
    ):
        return "preference"
    if effect_denied and not operations:
        return "no_action_constraint"
    if operations:
        return "user_mission"
    if re.fullmatch(
        r"(hola+|holas|hello|hi|hey|gracias|thanks|perfecto|bien|ok(?:ay)?|adi[oó]s)[!. ]*",
        folded,
    ):
        return "conversation_question"
    if "?" in text or re.match(
        r"(?i)\s*(qu[eé]|qui[eé]n|c[oó]mo|cu[aá]ndo|d[oó]nde|por qu[eé]|what|who|how|when|where|why)\b",
        text,
    ):
        return "conversation_question"
    if origin in {"document_requirement", "acceptance_example"}:
        return "product_requirement"
    return "conversation_question"


def risk_policy(
    text: str, operations: list[str], *, message_class: str | None = None
) -> dict[str, str]:
    if message_class == "no_action_constraint":
        return {
            "class": "no_effect",
            "confirmation": "not_required",
            "reason": "La solicitud niega el efecto; no autoriza ninguna operación física.",
        }
    if operations == ["audio.status"]:
        return {
            "class": "read_only",
            "confirmation": "not_required",
            "reason": "La consulta solo lee el estado actual; no autoriza efectos físicos.",
        }
    if re.search(r"(?i)system32|destruye|compromet|malware|roba credenciales", text):
        return {
            "class": "forbidden_destructive",
            "confirmation": "blocked",
            "reason": "El propósito compromete o destruye el equipo.",
        }
    if "game.purchase" in operations:
        folded = normalize(text)
        if re.search(
            r"\b(?:agrega|anade|add)\b.*\b(?:gratis|free)\b.*\b(?:carrito|cart)\b",
            folded,
        ):
            return {
                "class": "low_reversible",
                "confirmation": "not_required",
                "reason": "Preparar un artículo gratuito en el carrito es reversible; cualquier checkout posterior se evalúa aparte.",
            }
        return {
            "class": "monetary",
            "confirmation": "required",
            "reason": "Existe costo o compromiso monetario.",
        }
    if "message.send" in operations:
        return {
            "class": "external_communication",
            "confirmation": "conditional",
            "reason": "Corroborar destinatario y pedir confirmación solo si es ambiguo, sensible o masivo.",
        }
    if "app.close" in operations or "office.document" in operations:
        return {
            "class": "work_loss",
            "confirmation": "conditional",
            "reason": "Confirmar únicamente si hay cambios no guardados.",
        }
    if "filesystem.trash" in operations:
        irreversible = bool(
            re.search(r"(?i)permanente|irreversible|sin papelera|shift\+delete", text)
        )
        return {
            "class": "irreversible" if irreversible else "recoverable_delete",
            "confirmation": "required" if irreversible else "not_required",
            "reason": "La Papelera es reversible; un borrado irreversible requiere confirmación.",
        }
    if "game.install" in operations or "package.install" in operations:
        return {
            "class": "installation",
            "confirmation": "conditional",
            "reason": "No confirmar software conocido/gratuito/adquirido; confirmar costo, fuente, permisos inesperados o una desinstalación que arriesgue datos locales.",
        }
    if "system.power" in operations:
        return {
            "class": "session_disruption",
            "confirmation": "conditional",
            "reason": "Proteger trabajo no guardado antes de interrumpir la sesión.",
        }
    return {
        "class": "low_reversible",
        "confirmation": "not_required",
        "reason": "La orden actual autoriza un efecto ordinario y reversible.",
    }


def mission_signature(
    message_class: str,
    operations: list[str],
    tags: list[str],
    text: str,
    *,
    risk: dict[str, str] | None = None,
    acceptance_scope: str = PRODUCT_ACCEPTANCE_SCOPE,
    denied_operations: Iterable[str] = (),
) -> str:
    if message_class == "no_action_constraint":
        signature = "no_action:effect_denied"
    elif message_class in {"engineering_instruction", "product_requirement"}:
        topic = "+".join(tags or ["general"])
        text_key = hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]
        signature = f"{message_class}:{topic}:text_{text_key}"
    elif message_class == "safety_instruction":
        signature = "safety:forbidden_destructive"
    elif message_class == "conversation_question":
        kind = (
            "smalltalk"
            if re.fullmatch(r"[\w ]{1,30}", normalize(text)) and "?" not in text
            else "knowledge_or_chat"
        )
        signature = f"conversation:{kind}"
    elif operations:
        signature = f"{message_class}:" + "+".join(operations)
    else:
        text_key = hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]
        signature = f"{message_class}:text_{text_key}"

    # A cart preparation with no price commitment and a paid checkout have the
    # same primitive but different confirmation contracts. They must never
    # inherit risk/outcome from whichever row sorts first in a mission group.
    if "game.purchase" in operations and risk is not None:
        signature += f":risk_{risk['class']}_{risk['confirmation']}"
    denied = sorted(set(denied_operations))
    if denied:
        signature += ":deny_" + "+".join(denied)
    if acceptance_scope != PRODUCT_ACCEPTANCE_SCOPE:
        signature += ":scope_trace_only"
    return signature


def mission_id(signature: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "_", signature.casefold()).strip("_")[:54]
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:10]
    return f"mission_{stem}_{digest}"


def source_path(path: Path) -> str:
    resolved = path.resolve()
    for logical, root in ROOTS.items():
        try:
            return f"{logical}/{resolved.relative_to(root.resolve()).as_posix()}"
        except ValueError:
            continue
    return f"external/{path.name}"


class Collector:
    def __init__(
        self,
        cutoff_sha256: str,
        *,
        acceptance_scope_oracle: AcceptanceScopeOracle | None = None,
    ) -> None:
        self.cutoff_sha256 = cutoff_sha256
        self.acceptance_scope_oracle = acceptance_scope_oracle
        self.rows: list[dict[str, Any]] = []
        self._file_hashes: dict[Path, str] = {}
        self._keys: set[tuple[str, str, str]] = set()

    def file_hash(self, path: Path) -> str:
        resolved = path.resolve()
        if resolved not in self._file_hashes:
            self._file_hashes[resolved] = sha256_file(resolved)
        return self._file_hashes[resolved]

    def add(
        self,
        text: str,
        *,
        origin: str,
        source: str,
        location: str,
        source_sha256: str,
        timestamp: str | None = None,
        hints: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(text, str):
            return
        raw = text.strip()
        if not raw or any(raw.startswith(tag) for tag in SKIP_USER_TAGS):
            return
        if len(raw) > 100_000:
            raw = raw[:100_000]
        literal, was_redacted = redact(raw)
        if not literal:
            return
        if origin in {
            "document_example",
            "document_requirement",
            "acceptance_example",
        } and not any(ch.isalnum() for ch in literal):
            return
        text_sha = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
        key = (source, location, text_sha)
        if key in self._keys:
            return
        self._keys.add(key)
        stable = f"{source}|{location}|{text_sha}"
        message_id = "msg_" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]
        scope_key = acceptance_scope_key(literal)
        normalized_scope_key = normalize(literal)
        source_decision = (
            self.acceptance_scope_oracle.source_decisions.get((source, location))
            if self.acceptance_scope_oracle
            else None
        )
        cross_source_exact_match = bool(
            self.acceptance_scope_oracle
            and scope_key in self.acceptance_scope_oracle.cross_source_keys
        )
        cross_source_normalized_match = bool(
            self.acceptance_scope_oracle
            and normalized_scope_key
            in self.acceptance_scope_oracle.cross_source_normalized_keys
        )
        if source_decision:
            acceptance_scope = TRACE_ONLY_ACCEPTANCE_SCOPE
            acceptance_scope_basis, source_language_labels = source_decision
        elif cross_source_exact_match or cross_source_normalized_match:
            acceptance_scope = TRACE_ONLY_ACCEPTANCE_SCOPE
            acceptance_scope_basis = (
                "cross_source_exact_non_target_literal"
                if cross_source_exact_match
                else "cross_source_normalized_non_target_literal"
            )
            source_language_labels = (
                self.acceptance_scope_oracle.labels_by_key.get(scope_key, ())
                if self.acceptance_scope_oracle
                else ()
            )
        else:
            acceptance_scope = PRODUCT_ACCEPTANCE_SCOPE
            acceptance_scope_basis = "not_in_audited_non_target_oracle"
            source_language_labels = (
                self.acceptance_scope_oracle.labels_by_key.get(scope_key, ())
                if self.acceptance_scope_oracle
                else ()
            )
        polarity = resolve_operation_polarity(literal)
        operations = list(polarity.actionable_operations)
        tags = requirement_tags(literal)
        message_class = classify(
            literal,
            origin,
            operations,
            effect_denied=polarity.kind in {"no_action", "constraint"},
        )
        if normalize(literal) in _FROZEN_ENGINEERING_POLARITY_LITERALS:
            message_class = "engineering_instruction"
        if message_id in _FROZEN_ENGINEERING_MESSAGE_IDS:
            message_class = "engineering_instruction"
        if message_id in _FROZEN_CONVERSATION_MESSAGE_IDS:
            message_class = "conversation_question"
            operations = []
        if message_class == "engineering_instruction":
            operations = []
        risk = risk_policy(literal, operations, message_class=message_class)
        signature = mission_signature(
            message_class,
            operations,
            tags,
            literal,
            risk=risk,
            acceptance_scope=acceptance_scope,
            denied_operations=polarity.denied_operations,
        )
        canonical_id = mission_id(signature)
        self.rows.append(
            {
                "message_id": message_id,
                "canonical_mission_id": canonical_id,
                "canonical_signature": signature,
                "class": message_class,
                "acceptance_scope": acceptance_scope,
                "acceptance_scope_basis": acceptance_scope_basis,
                "acceptance_scope_bases": [acceptance_scope_basis],
                "acceptance_scope_source_labels": list(source_language_labels),
                "origin": origin,
                "source": source,
                "source_location": location,
                "source_sha256": source_sha256,
                "cutoff_state_sha256": self.cutoff_sha256,
                "timestamp": timestamp,
                "text_literal": literal,
                "text_sha256": text_sha,
                "redacted": was_redacted,
                "paraphrase": re.sub(r"\s+", " ", literal),
                "language": language(literal),
                "intent": signature,
                "expected_state": expected_state(operations, message_class),
                "operations": operations,
                "denied_operations": list(polarity.denied_operations),
                "possible_chain": len(operations) > 1,
                "requirement_tags": tags,
                "data_or_preferences": data_flags(literal),
                "risk": risk,
                "success_evidence": evidence_for(operations, message_class),
                "natural_response": response_for(operations, message_class),
                "fallback": fallback_for(operations, message_class),
                "source_hints": hints or {},
            }
        )


def data_flags(text: str) -> list[str]:
    flags = []
    for name, pattern in {
        "preference": r"(?i)prefier|favorit|me gusta|i like",
        "person_name": r"(?i)me llamo|mi nombre|my name|contacto|destinatario",
        "account": r"(?i)cuenta|account|spotify|steam|whatsapp|discord",
        "file_content": r"(?i)archivo|file|documento|nota|message|mensaje",
        "screen_content": r"(?i)pantalla|screen|imagen|ocr|camera|c[aá]mara",
    }.items():
        if re.search(pattern, text):
            flags.append(name)
    return flags


def expected_state(operations: list[str], message_class: str) -> str:
    if message_class == "engineering_instruction":
        return "Restricción o procedimiento de ingeniería preservado; no se expone como tool de usuario."
    if message_class == "product_requirement":
        return "Contrato de producto incorporado a diseño y prueba de regresión."
    if message_class == "conversation_question":
        return "Respuesta conversacional correcta sin efectos físicos innecesarios."
    if message_class == "safety_instruction":
        return "Solicitud peligrosa bloqueada con una alternativa segura."
    if message_class == "no_action_constraint":
        return "No se ejecuta ninguna operación física; se respeta la restricción de no actuar."
    if not operations:
        return (
            "Objetivo entendido y conducido honestamente al siguiente paso verificable."
        )
    return " ".join(OP_SPECS[name].expected for name in operations)


def evidence_for(operations: list[str], message_class: str) -> list[str]:
    if message_class in {"engineering_instruction", "product_requirement"}:
        return ["Decisión, implementación o regresión enlazada a la fuente histórica."]
    if message_class == "conversation_question":
        return ["No se invocan operaciones; respuesta natural y pertinente."]
    if message_class == "safety_instruction":
        return ["Policy engine bloquea el efecto y no hay mutación física."]
    if message_class == "no_action_constraint":
        return ["No se invocan operaciones y el estado físico permanece sin cambios."]
    return [OP_SPECS[name].verification for name in operations] or [
        "Estado final observable corroborado."
    ]


def response_for(operations: list[str], message_class: str) -> str:
    if message_class == "conversation_question":
        return "Respuesta natural, breve y suficiente."
    if message_class == "engineering_instruction":
        return "Instrucción registrada y aplicada al proceso de construcción."
    if message_class == "product_requirement":
        return "Requisito incorporado con trazabilidad."
    if message_class == "safety_instruction":
        return "No puedo hacer eso porque dañaría o comprometería tu equipo; puedo ayudarte con una alternativa segura."
    if message_class == "no_action_constraint":
        return "Entendido; no haré esa acción."
    if len(operations) == 1:
        return OP_SPECS[operations[0]].response
    if operations:
        return "Listo; completé y verifiqué cada parte autorizada de la misión."
    return "Necesito un dato concreto para completar la misión sin inventar."


def fallback_for(operations: list[str], message_class: str) -> str:
    if message_class in {"engineering_instruction", "product_requirement"}:
        return "Mantener como blocker si todavía no existe decisión o prueba."
    if message_class == "conversation_question":
        return "Admitir incertidumbre y ofrecer una vía concreta."
    if message_class == "no_action_constraint":
        return "Responder de forma informativa sin ejecutar la operación negada."
    if operations:
        return " ".join(dict.fromkeys(OP_SPECS[name].fallback for name in operations))
    return "Preguntar únicamente el dato que cambia el objetivo o explicar la dependencia externa."


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield number, value


def iter_jsonl_text(text: str) -> Iterator[tuple[int, dict[str, Any]]]:
    for number, line in enumerate(text.splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield number, value


def _source(manifest: dict[str, Any], source_id: str) -> dict[str, Any]:
    return next(row for row in manifest["sources"] if row["id"] == source_id)


def validate_manifest_payload(manifest: dict[str, Any]) -> str:
    """Fail closed unless the manifest payload matches its frozen digest."""
    expected = manifest.get("manifest_payload_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError(
            "Frozen source manifest has no valid manifest_payload_sha256"
        )
    payload = {
        key: value
        for key, value in manifest.items()
        if key not in {"generated_at", "manifest_payload_sha256"}
    }
    actual = canonical_digest(payload)
    if actual != expected:
        raise RuntimeError(
            "Frozen source manifest payload mismatch: "
            f"expected={expected} actual={actual}"
        )
    return expected


def _git_blob(root: Path, commit: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def _verified_live_bytes(path: Path, expected_sha256: str) -> bytes:
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError(
            f"Frozen source changed after cutoff: {source_path(path)} "
            f"expected={expected_sha256} actual={actual}"
        )
    return data


def frozen_source_bytes(path: Path, manifest: dict[str, Any]) -> bytes:
    """Read a source from its frozen Git blob or verify manifested bytes."""
    resolved = path.resolve()
    legacy_root = (REPO / "legacy").resolve()
    if resolved.is_relative_to(legacy_root):
        ref = _source(manifest, "baxy_legacy_checkpoint")
        return _git_blob(
            REPO,
            ref["commit"],
            resolved.relative_to(legacy_root).as_posix(),
        )
    if resolved.is_relative_to(REPO):
        ref = _source(manifest, "baxy_cutoff")
        return _git_blob(REPO, ref["commit"], resolved.relative_to(REPO).as_posix())

    for root, source_id in (
        (
            (ROOTS["probando_gemma4"] / "_tesis_curso" / "entregables").resolve(),
            "probando_thesis_deliverables",
        ),
        (
            (ROOTS["probando_gemma4"] / "documentacion").resolve(),
            "probando_documentation",
        ),
    ):
        if not resolved.is_relative_to(root):
            continue
        relative = resolved.relative_to(root).as_posix()
        ref = _source(manifest, source_id)
        files = {row["path"]: row for row in ref["files"]}
        entry = files.get(relative)
        if entry is None:
            raise RuntimeError(
                f"Source was not present at cutoff: {source_id}/{relative}"
            )
        return _verified_live_bytes(resolved, entry["sha256"])

    for root, source_id in (
        (ROOTS["probando_gemma4"].resolve(), "probando_gemma4"),
        (ROOTS["carter_os_ai"].resolve(), "carter_os_ai"),
    ):
        if not resolved.is_relative_to(root):
            continue
        ref = _source(manifest, source_id)
        relative = resolved.relative_to(root).as_posix()
        if source_id == "probando_gemma4":
            fixed_ids = {
                "gemma4_agent/data/router_corpus_real_logs.jsonl": "probando_router_corpus_real_logs",
                "gemma4_agent/data/traces.jsonl": "probando_runtime_traces",
            }
            if relative in fixed_ids:
                fixed = _source(manifest, fixed_ids[relative])
                return _verified_live_bytes(resolved, fixed["sha256"])
        overlay = {row["path"]: row for row in ref.get("overlay_entries", [])}
        if relative in overlay:
            entry = overlay[relative]
            if not entry.get("exists") or "sha256" not in entry:
                raise RuntimeError(
                    f"Frozen overlay is unavailable: {source_id}/{relative}"
                )
            return _verified_live_bytes(resolved, entry["sha256"])
        return _git_blob(root, ref["head"], relative)

    for root, source_id in (
        (ROOTS["functiongemma"].resolve(), "functiongemma"),
        (ROOTS["gemma4_local"].resolve(), "gemma4_local_history"),
    ):
        if not resolved.is_relative_to(root):
            continue
        relative = resolved.relative_to(root).as_posix()
        ref = _source(manifest, source_id)
        files = {row["path"]: row for row in ref["files"]}
        entry = files.get(relative)
        if entry is None:
            raise RuntimeError(
                f"Source was not present at cutoff: {source_id}/{relative}"
            )
        return _verified_live_bytes(resolved, entry["sha256"])

    raise RuntimeError(f"No frozen-source policy for {source_path(path)}")


def frozen_source_text(path: Path, manifest: dict[str, Any]) -> tuple[str, str]:
    data = frozen_source_bytes(path, manifest)
    text = (
        data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    )
    return text, hashlib.sha256(data).hexdigest()


def build_acceptance_scope_oracle(
    manifest: dict[str, Any],
) -> AcceptanceScopeOracle:
    """Build the audited language-scope oracle from frozen source evidence.

    Decisions bind a source occurrence whenever language provenance exists.
    Cross-source propagation uses accent-preserving exact text only, and skips
    known homographs that are also valid ES/EN/Spanglish utterances.
    """
    root = ROOTS["functiongemma"]
    train = root / "finetune_llm" / "curated" / "train_v3.jsonl"
    router_eval = root / "router" / "data" / "router_eval_corpus.curated.jsonl"
    router_corpus = root / "router" / "data" / "router_corpus_curated_ft.jsonl"
    train_text, train_sha = frozen_source_text(train, manifest)
    eval_text, eval_sha = frozen_source_text(router_eval, manifest)
    corpus_text, corpus_sha = frozen_source_text(router_corpus, manifest)

    language_labels: dict[str, set[str]] = defaultdict(set)
    train_rows = list(iter_jsonl_text(train_text))
    for _, row in train_rows:
        key = acceptance_scope_key(str(row.get("user_text") or ""))
        if key:
            language_labels[key].add(str(row.get("lang")))
    labels_by_key = {
        key: tuple(sorted(labels)) for key, labels in language_labels.items()
    }
    normalized_language_labels: dict[str, set[str]] = defaultdict(set)
    for key, labels in language_labels.items():
        normalized_language_labels[normalize(key)].update(labels)
    target_labels = {"es", "en"}
    source_foreign_keys = {
        key
        for key, labels in language_labels.items()
        if labels
        and labels <= FROZEN_NON_TARGET_LANGUAGE_LABELS
        and not labels.intersection(target_labels)
    }
    target_wins = {
        key
        for key, labels in language_labels.items()
        if labels.intersection(FROZEN_NON_TARGET_LANGUAGE_LABELS)
        and labels.intersection(target_labels)
    }
    normalized_target_wins = {
        key
        for key, labels in normalized_language_labels.items()
        if labels.intersection(FROZEN_NON_TARGET_LANGUAGE_LABELS)
        and labels.intersection(target_labels)
    }
    mislabeled_non_target_keys = {
        acceptance_scope_key(str(row.get("user_text") or ""))
        for line_no, row in train_rows
        if line_no in _FROZEN_TRAIN_MISLABELED_NON_TARGET_LINES
    }

    decisions: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {}

    def bind(
        source: Path,
        line_no: int,
        key: str,
        basis: str,
        labels: Iterable[str] = (),
    ) -> None:
        if normalize(key) in _FROZEN_SOURCE_TARGET_OVERRIDES:
            return
        decisions[(source_path(source), f"line:{line_no}")] = (
            basis,
            tuple(sorted(set(labels))),
        )

    for line_no, row in train_rows:
        key = acceptance_scope_key(str(row.get("user_text") or ""))
        if (
            key in _FROZEN_TRACE_ONLY_SCOPE_EXCEPTIONS
            or line_no in _FROZEN_TRAIN_MISLABELED_NON_TARGET_LINES
        ):
            bind(
                train,
                line_no,
                key,
                "audited_exact_non_target_exception",
                labels_by_key.get(key, ()),
            )

    corpus_rows = list(iter_jsonl_text(corpus_text))
    missing_language_evidence: list[int] = []
    for line_no, row in corpus_rows:
        key = acceptance_scope_key(str(row.get("q") or ""))
        labels = labels_by_key.get(key, ())
        if not labels:
            missing_language_evidence.append(line_no)
            continue
        if key in source_foreign_keys:
            bind(
                router_corpus,
                line_no,
                key,
                "train_v3_non_target_language_label",
                labels,
            )
        elif (
            key in _FROZEN_TRACE_ONLY_SCOPE_EXCEPTIONS
            or key in mislabeled_non_target_keys
        ):
            bind(
                router_corpus,
                line_no,
                key,
                "audited_exact_non_target_exception",
                labels,
            )
    if missing_language_evidence:
        raise RuntimeError(
            "Frozen router corpus lost train_v3 language provenance at lines: "
            + ", ".join(map(str, missing_language_evidence[:20]))
        )

    audited_eval_lines = {
        line_no
        for start, end in _FROZEN_ROUTER_EVAL_NON_TARGET_RANGES
        for line_no in range(start, end + 1)
    }
    eval_evidence_keys: set[str] = set()
    for line_no, row in iter_jsonl_text(eval_text):
        literal = str(row.get("q") or "")
        key = acceptance_scope_key(literal)
        normalized = normalize(redact(literal)[0])
        explicit_language = str(row.get("lang") or "")
        labels = labels_by_key.get(key, ())
        basis = ""
        source_labels: tuple[str, ...] = ()
        if explicit_language in FROZEN_NON_TARGET_LANGUAGE_LABELS:
            basis = "router_eval_non_target_language_label"
            source_labels = (explicit_language,)
        elif line_no in audited_eval_lines:
            basis = "audited_router_eval_non_target_block"
        elif normalized in _FROZEN_ROUTER_EVAL_NON_TARGET_RESIDUALS:
            basis = "audited_router_eval_non_target_residual"
        elif key in source_foreign_keys:
            basis = "train_v3_non_target_language_label"
            source_labels = labels
        elif (
            key in _FROZEN_TRACE_ONLY_SCOPE_EXCEPTIONS
            or key in mislabeled_non_target_keys
        ):
            basis = "audited_exact_non_target_exception"
            source_labels = labels
        if basis:
            bind(router_eval, line_no, key, basis, source_labels)
            eval_evidence_keys.add(key)

    cross_source_keys = (
        source_foreign_keys | eval_evidence_keys | _FROZEN_TRACE_ONLY_SCOPE_EXCEPTIONS
    )
    cross_source_keys = frozenset(
        key
        for key in cross_source_keys
        if (
            normalize(key) not in _FROZEN_CROSS_SOURCE_TARGET_HOMOGRAPHS
            or key in _FROZEN_CROSS_SOURCE_SAFE_NON_TARGET_LITERALS
        )
        and key not in target_wins
        and normalize(key) not in _FROZEN_SOURCE_TARGET_OVERRIDES
    )
    cross_source_normalized_keys = frozenset(
        normalized
        for normalized in (normalize(key) for key in cross_source_keys)
        if normalized
        and normalized not in _FROZEN_CROSS_SOURCE_TARGET_HOMOGRAPHS
        and normalized not in _FROZEN_SOURCE_TARGET_OVERRIDES
        and normalized not in normalized_target_wins
    )
    return AcceptanceScopeOracle(
        source_decisions=decisions,
        cross_source_keys=cross_source_keys,
        cross_source_normalized_keys=cross_source_normalized_keys,
        labels_by_key=labels_by_key,
        source_files=tuple(
            sorted(
                (
                    (source_path(train), train_sha),
                    (source_path(router_eval), eval_sha),
                    (source_path(router_corpus), corpus_sha),
                )
            )
        ),
        source_labeled_trace_only_locations=len(decisions),
        cross_source_trace_only_keys=len(cross_source_keys),
        cross_source_trace_only_normalized_keys=len(cross_source_normalized_keys),
        exact_exception_keys=len(
            _FROZEN_TRACE_ONLY_SCOPE_EXCEPTIONS | mislabeled_non_target_keys
        ),
        target_wins_or_source_override_keys=len(
            set(target_wins) | set(_FROZEN_SOURCE_TARGET_OVERRIDES)
        ),
    )


def text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict) and item.get("type") in {"input_text", "text"}
        ).strip()
    return ""


def codex_session_index() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in (HOME / ".codex" / "sessions").rglob("*.jsonl"):
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                event = json.loads(handle.readline())
            payload = event.get("payload") or {}
            session_id = str(payload.get("id") or payload.get("session_id") or "")
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if session_id:
            result[session_id] = path
    return result


def _verify_codex_prefix(path: Path, record: dict[str, Any]) -> bytes:
    """Return the exact manifested physical prefix after byte verification.

    The frozen manifest was produced from a contiguous JSONL prefix.  Reusing
    the timestamp-filtered freeze helper here would ignore an untimestamped
    line inserted before that prefix, while extraction would still consume the
    injected physical line.  Reading once also removes a verify/use race.
    """
    session_id = str(record.get("session_id") or "")
    required = ("line_count", "bytes", "sha256")
    missing = [key for key in required if key not in record]
    if missing:
        raise RuntimeError(
            f"Frozen Codex prefix metadata missing for {session_id}: "
            + ", ".join(missing)
        )
    selected: list[bytes] = []
    with path.open("rb") as handle:
        for _ in range(record["line_count"]):
            raw_line = handle.readline()
            if not raw_line:
                break
            selected.append(raw_line)
    data = b"".join(selected)
    actual = {
        "line_count": len(selected),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    mismatches = {
        key: {"expected": record[key], "actual": actual[key]}
        for key in required
        if actual[key] != record[key]
    }
    if mismatches:
        raise RuntimeError(
            f"Frozen Codex prefix mismatch for {session_id}: "
            + json.dumps(mismatches, sort_keys=True)
        )
    return data


def extract_codex(collector: Collector, manifest: dict[str, Any]) -> None:
    sources = {row["id"]: row for row in manifest["sources"]}
    root_set = sources["codex_relevant_root_threads"]
    records = list(root_set["records"])
    current = sources["current_codex_thread_prefix"]
    records.append(
        {
            "session_id": current["thread_id"],
            "cwd_id": "baxy",
            "line_count": current["line_count"],
            "bytes": current["bytes"],
            "sha256": current["sha256"],
        }
    )
    index = codex_session_index()
    for record in records:
        session_id = record["session_id"]
        path = index.get(session_id)
        if path is None:
            raise RuntimeError(f"Frozen Codex session unavailable: {session_id}")
        prefix = _verify_codex_prefix(path, record)
        for line_no, event in iter_jsonl_text(prefix.decode("utf-8", errors="replace")):
            timestamp = str(event.get("timestamp") or "")
            try:
                if datetime.fromisoformat(timestamp.replace("Z", "+00:00")) > CUTOFF:
                    break
            except ValueError:
                pass
            payload = event.get("payload") or {}
            if (
                event.get("type") != "response_item"
                or payload.get("type") != "message"
                or payload.get("role") != "user"
            ):
                continue
            content = text_content(payload.get("content"))
            collector.add(
                content,
                origin="observed_user",
                source=f"codex/{record['cwd_id']}/{session_id}",
                location=f"event_line:{line_no}",
                source_sha256=record["sha256"],
                timestamp=timestamp or None,
            )


def extract_current_request(collector: Collector, manifest: dict[str, Any]) -> None:
    source = next(
        row
        for row in manifest["sources"]
        if row["id"] == "current_user_request_attachment"
    )
    path = (
        HOME
        / ".codex"
        / "attachments"
        / "002e6882-e694-4b06-bcc2-cfbee6782402"
        / "pasted-text.txt"
    )
    data = _verified_live_bytes(path, source["sha256"])
    text = (
        data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    )
    collector.add(
        text,
        origin="current_request",
        source="current_user_request_attachment",
        location="file:1",
        source_sha256=source["sha256"],
        timestamp=CUTOFF_UTC,
    )


def extract_gemma_sessions(collector: Collector, manifest: dict[str, Any]) -> None:
    root = ROOTS["gemma4_local"] / "sessions"
    for path in sorted(root.glob("*.json")):
        try:
            text, digest = frozen_source_text(path, manifest)
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for index, turn in enumerate(data.get("turns") or []):
            if isinstance(turn, dict) and turn.get("role") == "user":
                collector.add(
                    str(turn.get("content") or ""),
                    origin="observed_user",
                    source=source_path(path),
                    location=f"turns/{index}",
                    source_sha256=digest,
                    timestamp=turn.get("ts"),
                )


def extract_probando_structured(collector: Collector, manifest: dict[str, Any]) -> None:
    data = ROOTS["probando_gemma4"] / "gemma4_agent" / "data"
    real = data / "router_corpus_real_logs.jsonl"
    if real.is_file():
        text, digest = frozen_source_text(real, manifest)
        for line_no, row in iter_jsonl_text(text):
            collector.add(
                str(row.get("q") or ""),
                origin="curated_history",
                source=source_path(real),
                location=f"line:{line_no}",
                source_sha256=digest,
                timestamp=row.get("ts"),
                hints={"expected": row.get("expected"), "turn_id": row.get("turn_id")},
            )
    traces = data / "traces.jsonl"
    if traces.is_file():
        text, digest = frozen_source_text(traces, manifest)
        for line_no, row in iter_jsonl_text(text):
            if row.get("kind") != "request_start":
                continue
            content = row.get("content") or {}
            text = (
                content.get("text") or content.get("preview")
                if isinstance(content, dict)
                else ""
            )
            collector.add(
                str(text or ""),
                origin="observed_user",
                source=source_path(traces),
                location=f"line:{line_no}",
                source_sha256=digest,
                timestamp=row.get("ts"),
                hints={"turn_id": row.get("turn_id")},
            )


def extract_functiongemma(collector: Collector, manifest: dict[str, Any]) -> None:
    root = ROOTS["functiongemma"]
    train = root / "finetune_llm" / "curated" / "train_v3.jsonl"
    if train.is_file():
        text, digest = frozen_source_text(train, manifest)
        excluded_parts = {"external", "translated_balance", "conversation_balance"}
        for line_no, row in iter_jsonl_text(text):
            if str(row.get("dataset_part")) in excluded_parts:
                continue
            if str(row.get("lang")) not in {"es", "en", "otro", "None"}:
                continue
            part = str(row.get("dataset_part") or "")
            origin = (
                "curated_history"
                if part in {"history_curated", "caceria_failmode_fix"}
                else "acceptance_example"
            )
            collector.add(
                str(row.get("user_text") or ""),
                origin=origin,
                source=source_path(train),
                location=f"line:{line_no}",
                source_sha256=digest,
                hints={
                    "source": row.get("source"),
                    "project": row.get("project"),
                    "category": row.get("category"),
                    "correct_tools": row.get("correct_tools"),
                },
            )
    for name in ("router_eval_corpus.curated.jsonl", "router_corpus_curated_ft.jsonl"):
        path = root / "router" / "data" / name
        if not path.is_file():
            continue
        text, digest = frozen_source_text(path, manifest)
        for line_no, row in iter_jsonl_text(text):
            collector.add(
                str(row.get("q") or ""),
                origin="curated_history",
                source=source_path(path),
                location=f"line:{line_no}",
                source_sha256=digest,
                hints={"expected": row.get("expected"), "source": row.get("source")},
            )


def walk_json_candidates(value: Any, pointer: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        if value.get("role") == "user":
            content = text_content(value.get("content"))
            if content:
                yield pointer + "/content", content
            return
        messages = value.get("messages")
        if isinstance(messages, list):
            for index, message in enumerate(messages):
                if isinstance(message, dict) and message.get("role") == "user":
                    content = text_content(message.get("content"))
                    if content:
                        yield f"{pointer}/messages/{index}", content
        for key in (
            "user_text",
            "prompt",
            "query",
            "q",
            "utterance",
            "input",
            "command",
            "user",
        ):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                yield f"{pointer}/{key}", candidate
                break
        for key, child in value.items():
            if key in {"messages", "tools", "tool_schemas", "schemas"}:
                continue
            if isinstance(child, (dict, list)):
                yield from walk_json_candidates(child, f"{pointer}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json_candidates(child, f"{pointer}/{index}")


def extract_carter_structured(collector: Collector, manifest: dict[str, Any]) -> None:
    root = ROOTS["carter_os_ai"]
    patterns = (
        "legacy/Carter_v2/audit/results/*.json",
        "legacy/Carter_v3/audit/runs/*.json",
        "legacy/Carter_v4/audit/runs/*.json",
        "carter_v5/audit/runs/*.json",
        "legacy/Auditoria30/**/*.json",
        "La razon de carter/*.json",
        "Extras/Carter_v3_tests/*.json",
    )
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(
            path
            for path in root.glob(pattern)
            if path.is_file() and path.stat().st_size <= 50 * 1024 * 1024
        )
    for path in sorted(paths):
        try:
            text, digest = frozen_source_text(path, manifest)
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for pointer, text in walk_json_candidates(data):
            collector.add(
                text,
                origin="historical_test",
                source=source_path(path),
                location=pointer or "/",
                source_sha256=digest,
            )


def markdown_candidates_text(text: str) -> Iterator[tuple[str, str, str]]:
    lines = text.splitlines()
    in_fence = False
    paragraph: list[tuple[int, str]] = []

    def flush() -> Iterator[tuple[str, str, str]]:
        nonlocal paragraph
        if not paragraph:
            return iter(())
        start = paragraph[0][0]
        text = " ".join(part.strip() for _, part in paragraph).strip()
        paragraph = []
        if len(text) <= 3000 and re.search(
            r"\b(BAXY|Baxy|Carter)\b.{0,300}\b(debe|deber[aá]|tiene que|nunca|no debe|must|should)\b",
            text,
            re.I | re.S,
        ):
            return iter(((f"paragraph:{start}", text, "document_requirement"),))
        return iter(())

    table_header: list[str] | None = None
    table_index: int | None = None
    for number, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            yield from flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.search(r"(?i)\b(?:usuario|user)\s*:\s*[“\"']?(.+?)[”\"']?\s*$", line)
        if match:
            yield from flush()
            yield f"line:{number}", match.group(1).strip(), "document_example"
            continue
        if line.lstrip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            lowered = [normalize(cell) for cell in cells]
            if table_header is None and any(
                any(
                    term in cell
                    for term in (
                        "prompt",
                        "comando",
                        "entrada",
                        "frase",
                        "consulta",
                        "user",
                    )
                )
                for cell in lowered
            ):
                table_header = lowered
                table_index = next(
                    index
                    for index, cell in enumerate(lowered)
                    if any(
                        term in cell
                        for term in (
                            "prompt",
                            "comando",
                            "entrada",
                            "frase",
                            "consulta",
                            "user",
                        )
                    )
                )
                continue
            if (
                table_header is not None
                and table_index is not None
                and table_index < len(cells)
            ):
                candidate = cells[table_index].strip('` “"')
                if (
                    candidate
                    and re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", candidate)
                    and not re.fullmatch(r"[-: ]+", candidate)
                ):
                    yield (
                        f"table:{number}:{table_index}",
                        candidate,
                        "acceptance_example",
                    )
                continue
        else:
            table_header = None
            table_index = None
        if not line.strip() or line.lstrip().startswith("#"):
            yield from flush()
        else:
            paragraph.append((number, line))
    yield from flush()


def markdown_candidates(path: Path) -> Iterator[tuple[str, str, str]]:
    yield from markdown_candidates_text(
        path.read_text(encoding="utf-8", errors="replace")
    )


def markdown_sources() -> list[Path]:
    sources: set[Path] = {
        REPO / "BAXY_GPT56_ULTRA_PROMPT.md",
        # Only documents present in the frozen BAXY cutoff commit.  Generated
        # ledgers (06+) must never feed back into their own source corpus.
        *(REPO / "documentacion").glob("0[0-5]_*.md"),
        *(REPO / "legacy" / "docs").glob("*.md"),
        REPO / "legacy" / "README.md",
        *(ROOTS["probando_gemma4"] / "_tesis_curso" / "entregables").glob("*.md"),
        *(ROOTS["probando_gemma4"] / "documentacion").rglob("*.md"),
        *(ROOTS["functiongemma"]).glob("*.md"),
        ROOTS["functiongemma"] / "router" / "README_ROUTER.md",
        *(ROOTS["carter_os_ai"] / "docs").rglob("*.md"),
        *(ROOTS["carter_os_ai"]).glob("*.md"),
    }
    excluded_markers = ("competidores", "evidencia pruebas gemma4")
    return sorted(
        path
        for path in sources
        if path.is_file()
        and path.stat().st_size <= 5 * 1024 * 1024
        and not any(marker in path.as_posix().casefold() for marker in excluded_markers)
    )


def extract_markdown(collector: Collector, manifest: dict[str, Any]) -> None:
    for path in markdown_sources():
        frozen_text, digest = frozen_source_text(path, manifest)
        for location, text, origin in markdown_candidates_text(frozen_text):
            collector.add(
                text,
                origin=origin,
                source=source_path(path),
                location=location,
                source_sha256=digest,
            )


def consolidate_derived_occurrences(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Collapse reruns/derived corpora while retaining every provenance edge."""
    derived_origins = {"historical_test", "curated_history", "acceptance_example"}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    observed: list[dict[str, Any]] = []
    for row in rows:
        if row["origin"] in derived_origins:
            grouped[
                (
                    row["origin"],
                    normalize(row["text_literal"]),
                    row["acceptance_scope"],
                )
            ].append(row)
        else:
            observed.append(row)
    consolidated = list(observed)
    for _, members in sorted(grouped.items(), key=lambda item: item[0]):
        representative = dict(members[0])
        provenance = [
            {
                "source": row["source"],
                "source_location": row["source_location"],
                "source_sha256": row["source_sha256"],
                "acceptance_scope_basis": row["acceptance_scope_basis"],
                "acceptance_scope_source_labels": row.get(
                    "acceptance_scope_source_labels", []
                ),
            }
            for row in members
        ]
        provenance.sort(key=lambda row: (row["source"], row["source_location"]))
        representative["acceptance_scope_bases"] = sorted(
            {
                row["acceptance_scope_basis"]
                for row in members
                if row.get("acceptance_scope_basis")
            }
        )
        representative["acceptance_scope_source_labels"] = sorted(
            {
                label
                for row in members
                for label in row.get("acceptance_scope_source_labels", [])
            }
        )
        representative["provenance_occurrence_count"] = len(provenance)
        representative["provenance_occurrences"] = provenance
        representative["source_hints_variants"] = [
            hint for hint in (row.get("source_hints") or {} for row in members) if hint
        ][:20]
        consolidated.append(representative)
    return consolidated, len(rows)


def build_outputs(
    rows: list[dict[str, Any]],
    cutoff_sha256: str,
    source_occurrences: int,
    acceptance_scope_oracle: AcceptanceScopeOracle | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows.sort(
        key=lambda row: (row["source"], row["source_location"], row["message_id"])
    )
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exact_first: dict[tuple[str, str], str] = {}
    normalized_literals: set[str] = set()
    for row in rows:
        groups[row["canonical_mission_id"]].append(row)
        normalized = normalize(row["text_literal"])
        normalized_literals.add(normalized)
        duplicate_key = (row["acceptance_scope"], normalized)
        row["duplicate_of"] = exact_first.get(duplicate_key)
        row["dedup_status"] = (
            "duplicate" if duplicate_key in exact_first else "canonical_source"
        )
        exact_first.setdefault(duplicate_key, row["message_id"])

    missions: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    for canonical_id, members in sorted(groups.items()):
        first = members[0]
        acceptance_scopes = {row["acceptance_scope"] for row in members}
        if len(acceptance_scopes) != 1:
            raise RuntimeError(
                f"Mixed acceptance scopes in canonical mission {canonical_id}: "
                f"{sorted(acceptance_scopes)}"
            )
        acceptance_scope = first["acceptance_scope"]
        acceptance_scope_bases = sorted(
            {
                basis
                for row in members
                for basis in row.get(
                    "acceptance_scope_bases", [row["acceptance_scope_basis"]]
                )
            }
        )
        acceptance_scope_source_labels = sorted(
            {
                label
                for row in members
                for label in row.get("acceptance_scope_source_labels", [])
            }
        )
        risk_contracts = {
            (row["risk"]["class"], row["risk"]["confirmation"]) for row in members
        }
        if len(risk_contracts) != 1:
            raise RuntimeError(
                f"Mixed risk contracts in canonical mission {canonical_id}: "
                f"{sorted(risk_contracts)}"
            )
        denied_contracts = {tuple(row.get("denied_operations", [])) for row in members}
        if len(denied_contracts) != 1:
            raise RuntimeError(
                f"Mixed denied-operation contracts in canonical mission {canonical_id}: "
                f"{sorted(denied_contracts)}"
            )
        historical_operations = sorted(
            {op for row in members for op in row["operations"]}
        )
        denied_operations = list(first.get("denied_operations", []))
        test_id = "hist_" + hashlib.sha256(canonical_id.encode()).hexdigest()[:14]
        trace_only = acceptance_scope == TRACE_ONLY_ACCEPTANCE_SCOPE
        if trace_only:
            operations: list[str] = []
            providers: list[str] = []
            outcome = "historical_trace_only"
            expected = (
                "La ocurrencia histórica conserva semántica y procedencia sin "
                "crear un compromiso funcional para BAXY 1.0."
            )
            plan = [
                "Conservar ID, fuente, hash, mapping y operación histórica; no incorporar al replay 1.0."
            ]
            verification = [
                "La traza permanece ligada al cutoff y separada de las misiones target ES/EN/spanglish."
            ]
            natural_response = (
                "Caso histórico preservado fuera del compromiso funcional 1.0."
            )
            fallback = "No crear reglas ni providers solo para aumentar cobertura fuera de alcance."
            contract_risk = {
                "class": "no_effect",
                "confirmation": "not_required",
                "reason": "La traza histórica no autoriza un efecto en BAXY 1.0.",
            }
            implementation_status = TRACE_ONLY_ACCEPTANCE_SCOPE
        else:
            operations = historical_operations
            providers = sorted({OP_SPECS[op].provider for op in operations})
            outcome = outcome_type(first["class"], first["risk"], operations)
            expected = first["expected_state"]
            plan = [f"Ejecutar y verificar {op}." for op in operations] or [
                "Responder o aplicar la restricción sin tools de usuario."
            ]
            verification = first["success_evidence"]
            natural_response = first["natural_response"]
            fallback = first["fallback"]
            contract_risk = first["risk"]
            implementation_status = "specified_pending_implementation"
        mission = {
            "canonical_mission_id": canonical_id,
            "signature": first["canonical_signature"],
            "class": first["class"],
            "acceptance_scope": acceptance_scope,
            "acceptance_scope_bases": acceptance_scope_bases,
            "acceptance_scope_source_labels": acceptance_scope_source_labels,
            "outcome_type": outcome,
            "message_count": len(members),
            "message_ids": [row["message_id"] for row in members],
            "source_count": len(
                {
                    occurrence["source"]
                    for row in members
                    for occurrence in row.get(
                        "provenance_occurrences", [{"source": row["source"]}]
                    )
                }
            ),
            "languages": sorted({row["language"] for row in members}),
            "examples": [row["text_literal"] for row in members[:5]],
            "expected_state": expected,
            "plan": plan,
            "operations": operations,
            "historical_operations": historical_operations,
            "denied_operations": denied_operations,
            "provider_roles": providers,
            "verification": verification,
            "risk": contract_risk,
            "natural_response": natural_response,
            "fallback": fallback,
            "acceptance_test_id": test_id,
            "implementation_status": implementation_status,
        }
        missions.append(mission)
        for row in members:
            mappings.append(
                {
                    "message_id": row["message_id"],
                    "canonical_mission_id": canonical_id,
                    "acceptance_scope": acceptance_scope,
                    "acceptance_scope_basis": row["acceptance_scope_basis"],
                    "acceptance_scope_bases": row.get(
                        "acceptance_scope_bases", [row["acceptance_scope_basis"]]
                    ),
                    "acceptance_scope_source_labels": row.get(
                        "acceptance_scope_source_labels", []
                    ),
                    "outcome_type": outcome,
                    "plan": mission["plan"],
                    "operations": operations,
                    "historical_operations": row["operations"],
                    "denied_operations": row.get("denied_operations", []),
                    "risk": contract_risk,
                    "historical_risk": row["risk"],
                    "provider_roles": providers,
                    "verification": mission["verification"],
                    "natural_response": mission["natural_response"],
                    "acceptance_test_id": test_id,
                    "status": implementation_status,
                }
            )

    trace_only_rows = [
        row for row in rows if row["acceptance_scope"] == TRACE_ONLY_ACCEPTANCE_SCOPE
    ]
    oracle_report: dict[str, Any] = {
        "name": "frozen_audited_non_target_oracle",
        "coverage_claim": "positive_source_evidence_and_exact_audit_not_heuristic_exhaustiveness",
        "matched_rows": len(trace_only_rows),
        "matched_source_occurrences": sum(
            row.get("provenance_occurrence_count", 1) for row in trace_only_rows
        ),
        "matched_literal_keys": len(
            {acceptance_scope_key(row["text_literal"]) for row in trace_only_rows}
        ),
        "message_id_sha256": sorted_line_digest(
            row["message_id"] for row in trace_only_rows
        ),
        "literal_key_sha256": sorted_line_digest(
            {acceptance_scope_key(row["text_literal"]) for row in trace_only_rows}
        ),
        "message_contract_sha256": sorted_line_digest(
            f"{row['message_id']}|{row['class']}|{','.join(row['operations'])}|"
            f"{','.join(row.get('denied_operations', []))}"
            for row in trace_only_rows
        ),
    }
    if acceptance_scope_oracle is not None:
        oracle_report.update(
            {
                "source_files": [
                    {"path": path, "sha256": digest}
                    for path, digest in acceptance_scope_oracle.source_files
                ],
                "source_labeled_trace_only_locations": acceptance_scope_oracle.source_labeled_trace_only_locations,
                "cross_source_trace_only_keys": acceptance_scope_oracle.cross_source_trace_only_keys,
                "cross_source_trace_only_normalized_keys": acceptance_scope_oracle.cross_source_trace_only_normalized_keys,
                "exact_exception_keys": acceptance_scope_oracle.exact_exception_keys,
                "target_wins_or_source_override_keys": acceptance_scope_oracle.target_wins_or_source_override_keys,
            }
        )

    report = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "semantic_revision": SEMANTIC_REVISION,
        "product_language_scope": list(PRODUCT_LANGUAGE_SCOPE),
        "non_target_language_history_policy": TRACE_ONLY_ACCEPTANCE_SCOPE,
        "acceptance_scope_oracle": oracle_report,
        "cutoff_utc": CUTOFF_UTC,
        "cutoff_state_sha256": cutoff_sha256,
        "raw_messages": len(rows),
        "source_occurrences": source_occurrences,
        "unique_literal_normalized": len(normalized_literals),
        "unique_scope_literal_contracts": len(exact_first),
        "canonical_missions": len(missions),
        "exact_duplicates": sum(
            1 for row in rows if row["dedup_status"] == "duplicate"
        ),
        "by_origin": dict(sorted(Counter(row["origin"] for row in rows).items())),
        "by_class": dict(sorted(Counter(row["class"] for row in rows).items())),
        "by_acceptance_scope": dict(
            sorted(Counter(row["acceptance_scope"] for row in rows).items())
        ),
        "by_language": dict(sorted(Counter(row["language"] for row in rows).items())),
        "by_operation": dict(
            sorted(Counter(op for row in rows for op in row["operations"]).items())
        ),
        "by_denied_operation": dict(
            sorted(
                Counter(
                    op for row in rows for op in row.get("denied_operations", [])
                ).items()
            )
        ),
        "messages_with_denied_operations": sum(
            bool(row.get("denied_operations")) for row in rows
        ),
        "operation_catalog_size": len(OP_SPECS),
        "by_source_family": dict(
            sorted(Counter(row["source"].split("/", 1)[0] for row in rows).items())
        ),
        "dynamic_unclassified_missions": sum(
            1
            for mission in missions
            if mission["signature"] == "user_mission:dynamic_goal"
        ),
        "redacted_messages": sum(1 for row in rows if row["redacted"]),
        "messages_sha256": canonical_digest(rows),
        "missions_sha256": canonical_digest(missions),
        "mapping_sha256": canonical_digest(mappings),
    }
    return missions, mappings, report


def outcome_type(
    message_class: str, risk: dict[str, str], operations: list[str]
) -> str:
    if message_class == "engineering_instruction":
        return "engineering_constraint"
    if message_class == "product_requirement":
        return "product_requirement"
    if message_class == "conversation_question":
        return "conversation_no_tool"
    if message_class == "no_action_constraint":
        return "conversation_no_tool"
    if risk["class"] == "forbidden_destructive":
        return "safe_refusal"
    if risk["confirmation"] in {"required", "conditional"}:
        return "risk_or_external_dependency_flow"
    if operations:
        return "mission_must_implement"
    return "conversation_no_tool"


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/corpus_cutoff/source_manifest.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("tests/data"))
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/corpus_cutoff/extraction_report.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = (
        args.manifest if args.manifest.is_absolute() else REPO / args.manifest
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cutoff_sha = validate_manifest_payload(manifest)
    acceptance_scope_oracle = build_acceptance_scope_oracle(manifest)
    collector = Collector(cutoff_sha, acceptance_scope_oracle=acceptance_scope_oracle)
    extract_codex(collector, manifest)
    extract_current_request(collector, manifest)
    extract_gemma_sessions(collector, manifest)
    extract_probando_structured(collector, manifest)
    extract_functiongemma(collector, manifest)
    extract_carter_structured(collector, manifest)
    extract_markdown(collector, manifest)
    consolidated_rows, source_occurrences = consolidate_derived_occurrences(
        collector.rows
    )
    missions, mappings, report = build_outputs(
        consolidated_rows,
        cutoff_sha,
        source_occurrences,
        acceptance_scope_oracle,
    )

    output_dir = (
        args.output_dir if args.output_dir.is_absolute() else REPO / args.output_dir
    )
    write_jsonl(output_dir / "historical_messages.jsonl", consolidated_rows)
    write_jsonl(output_dir / "historical_missions.jsonl", missions)
    write_jsonl(output_dir / "historical_message_mapping.jsonl", mappings)
    report_path = args.report if args.report.is_absolute() else REPO / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
