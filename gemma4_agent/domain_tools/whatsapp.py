"""WhatsApp domain tool.

Módulo hermano de domain_tools/__init__.py, que re-exporta los símbolos públicos
para que los callers existentes (dispatch via ToolRegistry, tests que hacen
`from gemma4_agent.domain_tools import whatsapp_tool` y
`patch("gemma4_agent.domain_tools.whatsapp.<name>")`) sigan funcionando.

GOTCHA de mocking: los tests que parchean internos del flujo whatsapp deben
apuntar a ESTE módulo (`gemma4_agent.domain_tools.whatsapp._X`), NO al re-export en
`gemma4_agent.domain_tools._X` — los callers internos resuelven el nombre en el
namespace de ESTE módulo. (`_find_whatsapp_app`, `subprocess.Popen`, `webbrowser.open`,
`_verify_visible_whatsapp_text_status`, `_capture_whatsapp_chat_area`,
`_whatsapp_chat_area_changed` se parchean acá.)

Contenido: detección de la app (UWP), normalización de teléfono, resolución de
destinatario (con exclude_groups + desempate contacto-vs-grupo), verificación del
chat/header por UIA→OCR (tri-state), captura del área de chat, GUI-search como
último recurso, auto-send con gate de entrega por pantalla, y el entry point
whatsapp_tool.
"""
from __future__ import annotations

import os
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Callable

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState
from .contacts import _RESOLVE_AMBIGUOUS_MARGIN, _contacts_resolve_recipient

Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


# WhatsApp UWP package family name (instalacion estandar desde Microsoft Store).
_WHATSAPP_UWP_PFN = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm"

# Numero E.164 (puede tener +, espacios, guiones, parentesis).
_WHATSAPP_PHONE_RE = re.compile(r"^[\+\d\s\-\(\)]{7,20}$")


def _normalize_phone_for_whatsapp(phone: str) -> str:
    """Normaliza un numero al formato que espera whatsapp:// y wa.me:
    solo digitos, sin el +, sin separadores. Ej. '+54 9 11 1234-5678' -> '54911123456 78'.
    """
    if not phone:
        return ""
    # Mantener solo digitos.
    digits = re.sub(r"\D", "", phone)
    return digits


def _find_whatsapp_app() -> dict[str, str | None]:
    """Detecta si WhatsApp esta instalado como UWP.

    Returns dict con kind ('uwp' | None) y launch_target.
    Reutiliza el patron de _find_streaming_app.
    """
    if os.name != "nt":
        return {"kind": None, "launch_target": None}
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"if (Get-AppxPackage -Name '{_WHATSAPP_UWP_PFN.split('_')[0]}') {{ Write-Output yes }}"],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0 and "yes" in (proc.stdout or "").lower():
            return {"kind": "uwp", "launch_target": f"shell:AppsFolder\\{_WHATSAPP_UWP_PFN}!App"}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"kind": None, "launch_target": None}


def _resolve_whatsapp_recipient(
    args: dict[str, Any], state: AgentState,
) -> tuple[str | None, str | None, str, str | None] | dict[str, Any]:
    """Resuelve el destinatario.

    Acepta en args:
      - phone="<numero>"  -> usado directamente (validado).
      - contact="<nombre>" o recipient="<nombre>"  -> busca en contacts.

    Returns:
      - tupla (raw_phone, normalized_digits, source, name_for_gui_search) si OK.
        Si phone resolvio -> (phone, normalized, source, None) — usar deeplink.
        Si solo hay nombre (contacto sin phone en store, o store vacio) ->
        (None, None, "gui_search", name_query) — usar GUI search en WhatsApp.
      - dict de error _err(...) si no se pudo resolver (sin phone ni nombre).
    """
    explicit_phone = str(args.get("phone") or args.get("number") or "").strip()
    if explicit_phone:
        if not _WHATSAPP_PHONE_RE.match(explicit_phone):
            return _err(
                f"invalid phone format: {explicit_phone!r}",
                hint=("Pass an international format like +54 9 11 1234-5678 or "
                      "just digits 5491112345678. WhatsApp requires country code."),
                status="needs_user",
            )
        normalized = _normalize_phone_for_whatsapp(explicit_phone)
        if len(normalized) < 7:
            return _err(
                f"phone too short after normalization: {normalized!r}",
                hint="Include country code (e.g. 54 for Argentina, 1 for USA).",
                status="needs_user",
            )
        return explicit_phone, normalized, "explicit", None

    # Resolver por nombre.
    name_query = str(
        args.get("contact") or args.get("recipient") or args.get("to")
        or args.get("name") or ""
    ).strip()
    if not name_query:
        return _err(
            "missing recipient: pass phone='+...' OR contact='<name>'",
            status="needs_user",
        )

    # 1. Intentar contacts store local (rapido si esta).
    # exclude_groups=True: un envío directo por NOMBRE nunca debe resolver a un
    # grupo — un nombre que matchea tanto a un contacto como a un grupo no debe
    # caer silenciosamente al grupo. Si el usuario quiere un grupo, el LLM debe
    # pasar el phone/JID del grupo explícito o el contacto marcado is_group debe
    # nombrarse aparte.
    resolve_result = _contacts_resolve_recipient(
        {"query": name_query, "limit": 5, "exclude_groups": True}, state,
    )
    matches = resolve_result.get("matches") or []
    # Grounding: si la resolución es AMBIGUA (dos contactos casi empatados), NO
    # adivinar — pedir desempate. Mandar al chat equivocado es daño irreversible.
    # Mejor preguntar.
    if resolve_result.get("ambiguous") and len(matches) >= 2:
        cand_names = [
            str((m["contact"].get("metadata") or {}).get("name")
                or m["contact"].get("label") or "?")
            for m in matches[:3]
        ]
        return _err(
            f"contacto ambiguo para {name_query!r}",
            status="needs_user",
            contact_name=name_query,
            candidates=cand_names,
            hint=f"¿A cuál querías: {', '.join(cand_names)}?",
        )
    # Colisión contacto-vs-grupo: exclude_groups oculta los grupos ANTES del
    # scoring, así que un nombre que matchea FUERTE tanto a un individuo (con
    # phone) como a un grupo del mismo nombre resolvía SILENCIOSO al individuo —
    # quien quería el grupo (o viceversa) recibía el chat equivocado. Es daño
    # irreversible. Re-resolvemos SIN excluir grupos y, si
    # hay un grupo igual de fuerte que el individuo elegido, NO adivinamos:
    # devolvemos los candidatos (kind contacto/grupo) para que el LLM/usuario
    # desempate. Estructural (mide la FORMA: mismo nombre, dos tipos), sin listas.
    if matches:
        best_individual = matches[0]
        best_ind_score = int(best_individual.get("score") or 0)
        all_result = _contacts_resolve_recipient(
            {"query": name_query, "limit": 5, "exclude_groups": False}, state,
        )
        group_matches = [
            m for m in (all_result.get("matches") or [])
            if bool((m["contact"].get("metadata") or {}).get("is_group", False))
        ]
        if group_matches:
            best_group = group_matches[0]
            best_grp_score = int(best_group.get("score") or 0)
            # "Igual de fuerte" = el grupo cae dentro del mismo margen de
            # ambigüedad que usamos para contactos. Si el grupo es claramente
            # más débil, el individuo gana sin preguntar (no molestamos al user).
            if (best_ind_score - best_grp_score) <= _RESOLVE_AMBIGUOUS_MARGIN:
                ind_name = str(
                    (best_individual["contact"].get("metadata") or {}).get("name")
                    or best_individual["contact"].get("label") or name_query)
                grp_name = str(
                    (best_group["contact"].get("metadata") or {}).get("name")
                    or best_group["contact"].get("label") or name_query)
                return _err(
                    f"'{name_query}' coincide con un contacto y con un grupo",
                    status="needs_user",
                    contact_name=name_query,
                    candidates=[
                        {"name": ind_name, "kind": "contact"},
                        {"name": grp_name, "kind": "group"},
                    ],
                    hint=(
                        f"¿Le mando al contacto '{ind_name}' o al grupo "
                        f"'{grp_name}'? Decímelo y lo envío."
                    ),
                )
    if matches:
        best = matches[0]["contact"]
        meta = best.get("metadata") or {}
        phone = str(meta.get("phone") or "").strip()
        if phone:
            normalized = _normalize_phone_for_whatsapp(phone)
            if len(normalized) >= 7:
                return phone, normalized, f"contact:{best.get('id')}", None
        # Contacto encontrado pero sin phone util -> caer a GUI search.

    # 2. Fallback: GUI search dentro de WhatsApp Desktop.
    # WhatsApp ya tiene la lista de contactos del telefono — usa Ctrl+F /
    # campo de busqueda para encontrar al contacto por nombre. Esto cubre
    # el caso "el contacto existe en WhatsApp pero no en mi store local".
    return None, None, "gui_search", name_query


def _resolve_whatsapp_recipient_legacy3(
    args: dict[str, Any], state: AgentState,
) -> tuple[str, str, str] | dict[str, Any]:
    """Backwards-compat 3-tuple form. Solo para tests viejos que esperaban
    (raw, normalized, source). NO usar en codigo nuevo.
    """
    r = _resolve_whatsapp_recipient(args, state)
    if isinstance(r, dict):
        return r
    raw, normalized, source, name = r
    if normalized is None:
        # tests legacy no soportaban el path gui_search; devolver error util.
        return _err(
            f"contact {name!r} found but has no phone number (use new GUI search path)",
            status="needs_user", contact_name=name,
        )
    return raw, normalized, source


def _verify_chat_header_uia(executor: Executor, contact_name: str) -> bool | None:
    """UIA primary: verifica el chat activo leyendo el ÁRBOL DE
    ACCESIBILIDAD de WhatsApp (no OCR, no mmproj, sub-segundo). WhatsApp Desktop
    moderno es WebView2/Chromium: el nombre del contacto aparece como el `Name`
    de un control (heading/text/listitem). Buscamos un token significativo del
    nombre entre los elementos UIA de la ventana de WhatsApp.

    Returns:
        True  -> encontrado en el árbol UIA (chat correcto).
        None  -> UIA no disponible / sin evidencia -> el caller cae a OCR.
        (no devuelve False: ausencia en UIA no PRUEBA chat equivocado; eso lo
         decide el verificador OCR, más sensible al header visible.)
    """
    import re as _re
    try:
        res = executor("uia", {"action": "find", "window": "WhatsApp",
                               "query": contact_name, "limit": 40})
    except Exception:
        return None
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    matches = res.get("matches")
    if not isinstance(matches, list):
        return None
    names = " ".join(
        str(m.get("name", "")) for m in matches if isinstance(m, dict)).lower()
    if not names.strip():
        return None
    names = _re.sub(r"[^a-záéíóúüñ ]", " ", names)
    tokens = [t for t in _re.split(r"\s+", contact_name.lower()) if len(t) >= 3]
    if not tokens:
        return None
    return True if any(t in names for t in tokens) else None


def _verify_chat_header(executor: Executor, contact_name: str) -> bool:
    """Confirma que el chat abierto en WhatsApp es del contacto pedido.

    El Enter a ciegas tras buscar puede abrir el chat equivocado (un nombre puede
    matchear un grupo distinto), así que antes de escribir verificamos el chat
    activo. PRIMERO por UIA (árbol de accesibilidad, barato, sin mmproj); si UIA
    no da evidencia, FALLBACK a OCR de la franja superior. Conservador: si
    NINGUNO verifica, devolvemos False -> el caller NO escribe (mejor no mandar
    que mandar al chat equivocado).

    El match es laxo a propósito: el header puede tener emojis/apodos ("Mamá🍓");
    basta con que un token alfabético >=3 chars del contacto aparezca.
    """
    import re as _re
    # UIA primero (más rápido y fiable que OCR, no carga mmproj).
    uia_ok = _verify_chat_header_uia(executor, contact_name)
    if uia_ok is True:
        return True
    # Fallback: OCR de la franja superior.
    try:
        shot = executor("gui", {"action": "locate_text", "text": contact_name})
    except Exception:
        return False
    if not isinstance(shot, dict):
        return False
    # locate_text devuelve found=True y matches si lo encontró en pantalla.
    if shot.get("found"):
        return True
    # Fallback: el OCR completo puede traer el texto aunque el match exacto falle
    # (emojis, mayúsculas). Buscar un token significativo del nombre en el texto.
    ocr_text = ""
    for key in ("text", "ocr_text", "full_text"):
        v = shot.get(key)
        if isinstance(v, str) and v:
            ocr_text = v
            break
    if not ocr_text and isinstance(shot.get("matches"), list):
        ocr_text = " ".join(
            str(m.get("text", "")) for m in shot["matches"] if isinstance(m, dict))
    ocr_norm = _re.sub(r"[^a-záéíóúüñ ]", " ", ocr_text.lower())
    tokens = [t for t in _re.split(r"\s+", contact_name.lower()) if len(t) >= 3]
    if not tokens:
        # nombre muy corto (p.ej. "mi") -> no podemos verificar con seguridad
        return False
    return any(t in ocr_norm for t in tokens)


def _verify_chat_header_status(executor: Executor, contact_name: str) -> str:
    """Tri-state para el envio WhatsApp.

    Returns:
        "confirmed"   -> el header contiene el contacto pedido.
        "wrong_chat"  -> el OCR leyo un header corto y claramente distinto.
        "unknown"     -> UIA/OCR no dio evidencia suficiente.

    Un bool que mezcle "wrong_chat" con "unknown" rompe envíos válidos: cuando
    WebView2 no expone el header, "unknown" se confundiría con chat equivocado y
    abortaría. El tri-state distingue "no hay evidencia" de "chat distinto".
    """
    import re as _re

    def _fold(s: str) -> str:
        s = unicodedata.normalize("NFKD", s.casefold())
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return _re.sub(r"[^a-z0-9 ]", " ", s)

    # No hacer locate_text(contact) sobre TODA la pantalla y confirmar si aparece
    # EN CUALQUIER LADO: el nombre buscado SIGUE ESCRITO en la caja de búsqueda
    # → falso "confirmed" → tipearía/enviaría al chat ABIERTO (equivocado). El
    # destinatario equivocado es daño irreversible.
    # Confirmar SOLO si el nombre aparece en la REGIÓN DEL ENCABEZADO (banda
    # superior del área de chat, a la derecha del sidebar) — NO en el buscador
    # (izquierda) ni en un mensaje (abajo). El texto del header es chico y de baja
    # confianza OCR (~20-24) → min_conf=20 (medido: el header cae a ~0.33W/0.09H).
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        if "whatsapp" not in (win32gui.GetWindowText(hwnd) or "").lower():
            return "unknown"
        L, T, Rr, Bb = win32gui.GetWindowRect(hwnd)
    except Exception:
        return "unknown"
    W, Hh = Rr - L, Bb - T
    if W <= 0 or Hh <= 0:
        return "unknown"
    try:
        shot = executor("gui", {"action": "locate_text", "text": contact_name, "min_conf": 20})
    except Exception:
        return "unknown"
    if not isinstance(shot, dict):
        return "unknown"
    matches = shot.get("matches")
    if not isinstance(matches, list):
        return "unknown"
    # Región del encabezado en coords de PANTALLA. Excluye sidebar (x<0.30W) y
    # mensajes (y>0.18H). locate_text añade screen_x/screen_y pre-traducidos.
    hx0, hx1 = L + W * 0.30, L + W * 0.88
    hy0, hy1 = T + Hh * 0.02, T + Hh * 0.18
    saw_anywhere = False
    for m in matches:
        if not isinstance(m, dict):
            continue
        sxv = m.get("screen_x"); syv = m.get("screen_y")
        if sxv is None or syv is None:
            continue
        saw_anywhere = True
        try:
            if hx0 <= float(sxv) <= hx1 and hy0 <= float(syv) <= hy1:
                return "confirmed"
        except (TypeError, ValueError):
            continue
    # Apareció en pantalla pero NO en el encabezado -> chat equivocado (no enviar).
    # No apareció en ningún lado -> unknown (WebView2 puede no exponer el header).
    return "wrong_chat" if saw_anywhere else "unknown"


def _verify_visible_whatsapp_text_status(executor: Executor, target_text: str) -> str:
    """Confirma por OCR que un texto reciente quedo visible en WhatsApp."""
    import re as _re

    def _fold(s: str) -> str:
        s = unicodedata.normalize("NFKD", s.casefold())
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return _re.sub(r"[^a-z0-9 ]", " ", s)

    target = (target_text or "").strip()
    if not target:
        return "unknown"
    try:
        import win32gui  # type: ignore
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "unknown"
        title = win32gui.GetWindowText(hwnd) or ""
        if "whatsapp" not in title.lower():
            return "unknown"
        rect = win32gui.GetWindowRect(hwnd)
    except Exception:
        return "unknown"

    try:
        shot = executor("gui", {"action": "screenshot", "monitor": "all"})
    except Exception:
        return "unknown"
    if not isinstance(shot, dict) or not shot.get("ok") or not shot.get("image_path"):
        return "unknown"

    try:
        from PIL import Image
        from ..tools_pkg.ops_tools import ocr_find_text
        image_path = Path(str(shot["image_path"]))
        img = Image.open(image_path)
        screen_left = int(shot.get("left", 0))
        screen_top = int(shot.get("top", 0))
        left, top, right, bottom = [int(v) for v in rect]
        box = (
            max(0, left - screen_left),
            max(0, top - screen_top),
            min(img.width, right - screen_left),
            min(img.height, bottom - screen_top),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return "unknown"
        crop_path = image_path.with_name(image_path.stem + "_whatsapp_crop.png")
        img.crop(box).save(crop_path)
        found = ocr_find_text(crop_path, target[:80], lang="spa+eng", min_conf=25)
    except Exception:
        return "unknown"

    if not isinstance(found, dict):
        return "unknown"
    if found.get("found"):
        return "confirmed"
    ocr_text = str(found.get("ocr_text") or found.get("text") or "")
    if not ocr_text:
        return "unknown"
    ocr_norm = _fold(ocr_text)
    target_tokens = [t for t in _fold(target).split() if len(t) >= 4]
    if not target_tokens:
        return "unknown"
    needed = target_tokens[: min(4, len(target_tokens))]
    return "confirmed" if all(t in ocr_norm for t in needed) else "unknown"


def _capture_whatsapp_chat_area(executor: Executor) -> dict[str, Any] | None:
    """Captura la zona de mensajes del chat activo, excluyendo sidebar e input."""
    try:
        import win32gui  # type: ignore
        from PIL import Image

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or ""
        if "whatsapp" not in title.lower():
            return None
        left, top, right, bottom = [int(v) for v in win32gui.GetWindowRect(hwnd)]
        shot = executor("gui", {"action": "screenshot", "monitor": "all"})
        if not isinstance(shot, dict) or not shot.get("ok") or not shot.get("image_path"):
            return None
        img = Image.open(Path(str(shot["image_path"]))).convert("RGB")
        screen_left = int(shot.get("left", 0))
        screen_top = int(shot.get("top", 0))
        w = max(1, right - left)
        h = max(1, bottom - top)
        # WhatsApp desktop: sidebar a la izquierda, header arriba, composer abajo.
        box = (
            max(0, int(left + w * 0.35) - screen_left),
            max(0, int(top + h * 0.14) - screen_top),
            min(img.width, int(right - w * 0.02) - screen_left),
            min(img.height, int(bottom - h * 0.13) - screen_top),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        crop = img.crop(box)
        return {"image": crop, "box": box}
    except Exception:
        return None


def _whatsapp_chat_area_changed(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> bool:
    try:
        from PIL import ImageChops, ImageStat

        if not before or not after:
            return False
        a = before.get("image")
        b = after.get("image")
        if a is None or b is None:
            return False
        if a.size != b.size:
            b = b.resize(a.size)
        diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        bbox = diff.getbbox()
        if bbox is None:
            return False
        area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1, a.size[0] * a.size[1])
        mean_delta = sum(ImageStat.Stat(diff).mean) / 3.0
        return area_ratio >= 0.01 and mean_delta >= 0.35
    except Exception:
        return False


def _whatsapp_send_via_gui_search(
    executor: Executor,
    contact_name: str,
    text: str,
    wait_seconds: float,
    auto_send: bool,
) -> dict[str, Any]:
    """Abre WhatsApp generico, busca el contacto por nombre via Ctrl+N,
    selecciona el primer match, escribe el mensaje y opcionalmente envia.

    Flujo (todos los pasos requieren focus verification antes de teclear):
      1. Dispatch whatsapp:// (sin args -> abre la app generica).
      2. Wait wait_seconds para que cargue.
      3. Focus WhatsApp + verify active window title.
      4. Ctrl+N (abre nuevo chat / selector global de contacto).
      5. Type contact_name.
      6. Wait ~1s (deja que filtre los resultados).
      7. Enter (selecciona el primer chat).
      8. Wait ~0.5s (entra al chat).
      9. Type text del mensaje.
      10. Si auto_send: Enter (envia).

    Returns dict con keys:
      - sent: bool
      - chat_opened: bool
      - search_term: str
      - abort_reason: str | None
      - steps: list[str] — pasos completados (para debug)
    """
    import time as _time

    steps: list[str] = []
    action_results: list[dict[str, Any]] = []

    def _compact_result(result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {"type": type(result).__name__}
        keep = (
            "ok", "error", "reason", "status", "completion_status", "verified",
            "state_changed", "state_verify", "method", "keys", "chars",
            "exit_code", "events", "found", "source", "action",
        )
        compact = {k: result.get(k) for k in keep if k in result}
        nested = result.get("result")
        if isinstance(nested, dict):
            compact["result"] = {
                k: nested.get(k)
                for k in ("ok", "error", "action", "title", "process", "pid", "hwnd")
                if k in nested
            }
        return compact

    def _result_failure(label: str, result: Any, *, require_effect: bool = False) -> str | None:
        if not isinstance(result, dict):
            return f"{label} returned non-dict result"
        if result.get("ok") is not True:
            return str(result.get("error") or result.get("reason") or "ok was not true")
        nested = result.get("result")
        if isinstance(nested, dict) and nested.get("ok") is False:
            return str(nested.get("error") or "nested result ok=false")
        if result.get("found") is False:
            return str(result.get("error") or "target window/control was not found")
        if require_effect and result.get("state_changed") is False:
            return str(result.get("state_verify") or "action caused no visible state change")
        events = result.get("events")
        if isinstance(events, (int, float)) and events <= 0:
            return "input injector reported zero events"
        exit_code = result.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            return f"input command returned exit_code={exit_code}"
        return None

    def _abort(
        label: str,
        reason: str,
        *,
        chat_opened: bool = False,
        result: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sent": False,
            "chat_opened": chat_opened,
            "search_term": contact_name,
            "abort_reason": f"{label}: {reason}",
            "steps": steps,
            "physical_actions_ok": False,
            "gui_action_results": action_results,
        }
        if result is not None:
            payload["failed_step"] = label
            payload["failed_result"] = _compact_result(result)
        if extra:
            payload.update(extra)
        return payload

    def _checked_executor(
        tool: str,
        args: dict[str, Any],
        label: str,
        *,
        require_effect: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if tool == "gui" and str(args.get("action") or "") in {
            "click", "double_click", "right_click", "type", "type_into",
            "click_button", "keypress", "hotkey", "scroll", "drag",
        }:
            _wait_until_not_user_active()
        try:
            result = executor(tool, args)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
        failure = _result_failure(label, result, require_effect=require_effect)
        if failure:
            return result, failure
        action_results.append({"step": label, "tool": tool, **_compact_result(result)})
        return result, None

    def _focus_and_verify() -> tuple[bool, str | None, Any]:
        # window.focus ahora hace restore + maximize si la ventana es chica
        # (regla universal aplicada en tools.py:window_control). Damos grace
        # de 0.5s para que el maximize tome efecto antes de verificar.
        last_active: Any = None
        last_title = ""
        for attempt in range(3):
            focus, abort = _checked_executor(
                "window", {"action": "focus", "title": "WhatsApp"}, "focus WhatsApp")
            if abort is not None:
                return False, abort, focus
            _time.sleep(0.5 + 0.25 * attempt)
            active, abort = _checked_executor("window", {"action": "active"}, "read active window")
            if abort is not None:
                return False, abort, active
            last_active = active
            active_title = ""
            a = active.get("active") if isinstance(active, dict) else None
            if isinstance(a, dict):
                active_title = str(a.get("title") or "")
            elif isinstance(active, dict):
                active_title = str(active.get("title") or "")
            last_title = active_title
            if "whatsapp" in active_title.lower():
                return True, None, active
        return False, f"active window is not WhatsApp: {last_title!r}", last_active

    def _focus_compose_box() -> tuple[dict[str, Any] | None, str | None]:
        """Click en la caja de mensaje del chat activo sin depender del idioma UI."""
        try:
            import win32gui  # type: ignore
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, "no foreground window"
            title = win32gui.GetWindowText(hwnd) or ""
            if "whatsapp" not in title.lower():
                return None, f"active window is not WhatsApp: {title!r}"
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception as exc:
            return None, f"could not locate WhatsApp compose box: {exc}"
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = int(left + width * 0.72)
        y = int(bottom - max(44, min(72, height * 0.05)))
        return _checked_executor(
            "gui", {"action": "click", "x": x, "y": y}, "focus compose box")

    def _wait_until_not_user_active(timeout_s: float = 3.0) -> None:
        try:
            from . import gui_safety
        except Exception:
            return
        deadline = _time.monotonic() + max(0.0, timeout_s)
        while _time.monotonic() < deadline:
            try:
                if not gui_safety.user_is_active():
                    return
            except Exception:
                return
            _time.sleep(0.2)

    # 1. Abrir WhatsApp (deeplink generico).
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "whatsapp://"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, FileNotFoundError) as exc:
        return {
            "sent": False, "chat_opened": False, "search_term": contact_name,
            "abort_reason": f"failed to launch WhatsApp: {exc}", "steps": steps,
            "physical_actions_ok": False, "gui_action_results": action_results,
        }
    steps.append("dispatched_deeplink")
    _time.sleep(max(0.5, wait_seconds))

    # 2. Focus + verify (incluye restore+maximize implicito).
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus WhatsApp after launch",
            reason or "could not focus WhatsApp window after launch",
            result=result,
        )
    steps.append("focused")
    # Extra grace tras maximize — el window manager necesita repaint.
    _time.sleep(0.4)

    # 3. BUSCADOR PRINCIPAL (NO Ctrl+N). Ctrl+N abre "Nuevo chat" que busca solo
    # CONTACTOS, no GRUPOS -> un nombre de grupo da "sin resultados" y el texto
    # termina en el chat ABIERTO (destinatario equivocado, daño irreversible).
    # El buscador principal (arriba-izq) SÍ encuentra grupos Y contactos. Lo enfocamos
    # por OCR del placeholder "Buscar" (fallback: coords sup-izq de la ventana).
    _search_pt = None
    try:
        import win32gui as _wg  # type: ignore
        _hwnd = _wg.GetForegroundWindow()
        _L, _T, _R, _B = _wg.GetWindowRect(_hwnd); _W, _H = _R - _L, _B - _T
        # Default: coords sup-izq de la ventana (donde vive el buscador principal).
        # OCR del placeholder "Buscar" lo refina si hay screenshot disponible.
        _search_pt = (int(_L + _W * 0.12), int(_T + _H * 0.095))
        _sshot = executor("gui", {"action": "screenshot", "monitor": "all"})
        if isinstance(_sshot, dict) and _sshot.get("image_path"):
            from ..tools_pkg.ops_tools import ocr_find_text as _oft
            _sx0 = int(_sshot.get("left", 0)); _sy0 = int(_sshot.get("top", 0))
            _f = _oft(Path(str(_sshot["image_path"])), "Buscar", min_conf=20)
            for _m in (_f.get("matches", []) if _f.get("found") else []):
                _cx = _m["center_x"] + _sx0; _cy = _m["center_y"] + _sy0
                if _cx < _L + _W * 0.32 and _cy < _T + _H * 0.20:
                    _search_pt = (int(_cx), int(_cy)); break
    except Exception:
        _search_pt = None
    if _search_pt is None:
        return _abort("focus main search", "could not locate WhatsApp search box")
    result, reason = _checked_executor(
        "gui", {"action": "click", "x": _search_pt[0], "y": _search_pt[1]},
        "focus main search box")
    if reason:
        return _abort("focus main search box", reason, result=result)
    steps.append("focused_main_search")
    _time.sleep(0.5)

    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "ctrl+a",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "select contact search text",
    )
    if reason:
        return _abort("select contact search text", reason, result=result)
    steps.append("selected_contact_search_text")
    _time.sleep(0.1)

    # 4. Type del nombre del contacto.
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before typing contact name",
            reason or "lost WhatsApp focus before typing contact name",
            result=result,
        )
    result, reason = _checked_executor(
        "gui",
        {
            "action": "type", "text": contact_name,
            "window": "WhatsApp", "method": "sendkeys",
        },
        "type contact name",
    )
    if reason:
        return _abort("type contact name", reason, result=result)
    steps.append("typed_contact_name")
    _time.sleep(1.0)  # tiempo para que WhatsApp filtre

    # 5. Enter para seleccionar primer resultado y entrar al chat.
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before selecting contact",
            reason or "lost WhatsApp focus before selecting contact",
            result=result,
        )
    # En el buscador principal hay que BAJAR al primer resultado y abrirlo (Down+Enter).
    _checked_executor(
        "gui", {"action": "keypress", "keys": "down", "window": "WhatsApp", "method": "sendkeys"},
        "highlight first result")
    _time.sleep(0.3)
    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "enter",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "select first contact match",
    )
    if reason:
        return _abort("select first contact match", reason, result=result)
    steps.append("selected_first_match")
    _time.sleep(0.8)  # entrar al chat

    # Enter normalmente cierra el selector de nuevo chat. No mandamos Escape aqui:
    # necesitamos conservar el presupuesto fisico para enfocar la caja de mensaje.

    # 5b. Verificacion hard gate. Nunca escribir/enviar si no vemos evidencia
    # del header del chat pedido. Dejar pasar "unknown" podría marcar sent=True
    # aunque el texto hubiera quedado en un buscador o en otro chat.
    chat_status = _verify_chat_header_status(executor, contact_name)
    chat_verified = chat_status == "confirmed"
    steps.append(f"chat_header_verified:{chat_verified}")
    steps.append(f"chat_header_status:{chat_status}")
    # GATE de destinatario por nivel de RIESGO:
    #  - ENVIAR (text presente, DESTRUCTIVO): exigir "confirmed". Nunca escribir a
    #    ciegas — el destinatario equivocado es daño irreversible.
    #    "unknown"/"wrong_chat" -> abort.
    #  - ABRIR (open_chat, sin text, NO destructivo): basta con NO detectar un chat
    #    EQUIVOCADO. "unknown" (WebView2 no expone el header por OCR/UIA) SIGUE: el chat
    #    casi seguro abrió con Down+Enter sobre el primer resultado y el usuario lo ve
    #    por screenshot. Solo "wrong_chat" (header corto y distinto) aborta.
    #    Caso típico: un contacto que no está en el store local (-> gui_search) cuyo
    #    header no es OCR-legible abortaría en "unknown" aunque el chat ya esté abierto.
    _is_send = bool(text)
    _gate_fail = (chat_status != "confirmed") if _is_send else (chat_status == "wrong_chat")
    if _gate_fail:
        return {
            "sent": False,
            "chat_opened": chat_status == "wrong_chat",
            "search_term": contact_name,
            "abort_reason": (
                f"no pude confirmar que el chat abierto es de '{contact_name}' "
                "despues de buscarlo — no escribo para no mandar al chat equivocado."
            ),
            "steps": steps, "chat_verified": False, "chat_header_status": chat_status,
            "physical_actions_ok": False, "gui_action_results": action_results,
        }
    chat_area_before_send = _capture_whatsapp_chat_area(executor)

    # 6. Type del mensaje (focus moved al input del chat).
    if not text:
        # open_chat: solo queriamos llegar al chat, no mandar.
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status, "physical_actions_ok": True,
            "gui_action_results": action_results,
        }
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before typing message",
            reason or "lost WhatsApp focus before typing message",
            chat_opened=True,
            result=result,
        )
    result, reason = _focus_compose_box()
    if reason:
        return _abort("focus compose box", reason, chat_opened=True, result=result)
    steps.append("focused_compose_box")
    _time.sleep(0.2)
    result, reason = _checked_executor(
        "gui",
        {
            "action": "type", "text": text,
            "window": "WhatsApp", "method": "sendkeys",
        },
        "type message",
    )
    if reason:
        return _abort("type message", reason, chat_opened=True, result=result)
    steps.append("typed_message")
    _time.sleep(0.4)

    # 7. Enviar si auto_send.
    if not auto_send:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status, "physical_actions_ok": True,
            "gui_action_results": action_results,
        }
    focused, reason, result = _focus_and_verify()
    if not focused:
        return _abort(
            "focus before sending",
            reason or "lost WhatsApp focus before sending",
            chat_opened=True,
            result=result,
        )
    result, reason = _checked_executor(
        "gui",
        {
            "action": "keypress", "keys": "enter",
            "window": "WhatsApp", "method": "sendkeys",
        },
        "send message",
    )
    if reason:
        return _abort("send message", reason, chat_opened=True, result=result)
    steps.append("sent_enter")
    _time.sleep(0.8)
    chat_area_after_send = _capture_whatsapp_chat_area(executor)
    visual_changed = _whatsapp_chat_area_changed(chat_area_before_send, chat_area_after_send)
    steps.append(f"sent_message_area_changed:{visual_changed}")
    message_status = _verify_visible_whatsapp_text_status(executor, text)
    steps.append(f"sent_message_visible:{message_status}")
    if message_status != "confirmed" and not visual_changed:
        return {
            "sent": False, "chat_opened": True, "search_term": contact_name,
            "abort_reason": (
                "no pude verificar en pantalla que el mensaje enviado aparezca "
                "en el chat despues de presionar Enter."
            ),
            "steps": steps, "chat_verified": chat_verified,
            "chat_header_status": chat_status,
            "sent_message_visible_status": message_status,
            "sent_message_area_changed": visual_changed,
            "physical_actions_ok": False,
            "gui_action_results": action_results,
        }
    return {
        "sent": True, "chat_opened": True, "search_term": contact_name,
        "abort_reason": None, "steps": steps, "chat_verified": chat_verified,
        "chat_header_status": chat_status, "physical_actions_ok": True,
        "sent_message_visible_status": message_status,
        "sent_message_area_changed": visual_changed,
        "gui_action_results": action_results,
    }


def _whatsapp_auto_send(
    executor: Executor, wait_seconds: float, text: str = "",
) -> dict[str, Any]:
    """Tras abrir el chat con el deeplink, esperar carga, asegurar focus
    de la ventana WhatsApp, y mandar Enter.

    Devuelve dict con keys:
      - "sent": bool — True SOLO si confirmamos que el mensaje quedó en el chat.
      - "focus_verified": bool — si confirmamos que la ventana activa era WhatsApp.
      - "abort_reason": str | None — por que NO mandamos / no confirmamos (si aplica).
      - "wait_seconds": float — cuanto esperamos antes del Enter.
      - "delivery_verified": str — "confirmed" | "changed" | "unverified".

    Seguridad: NUNCA mandar Enter si no podemos confirmar que la ventana
    activa contiene "WhatsApp" en el titulo. De lo contrario el Enter va a
    la app que el user tenia en focus (IDE, browser, terminal con comando
    peligroso, etc.).

    Login pre-check: declarar sent=True ni bien se aprieta Enter, sin mirar la
    pantalla, es falso si WhatsApp está DESLOGUEADO (pantalla de QR): el deeplink
    abre igual, el título sigue conteniendo "WhatsApp", y el mensaje nunca sale.
    Este path comparte el mismo gate ESTRUCTURAL y MULTILINGÜE que el path
    GUI-search: el mensaje se declara enviado SOLO si el texto aparece en el chat
    (OCR) o el área de chat cambió visualmente tras el Enter. Si no hay evidencia
    -> sent=False con abort honesto (cubre desloguear/QR y cualquier fallo de
    entrega). NO usamos listas de strings "Escanea el QR" por idioma (frágil,
    monolingüe): medimos la FORMA (apareció el mensaje / cambió el área), no el
    contenido del cartel de login.
    """
    import time as _time
    # 1. Esperar a que WhatsApp termine de cargar el chat + rellenar texto.
    _time.sleep(max(0.5, wait_seconds))

    # 2. Asegurar focus: pedir explicitamente que la ventana de WhatsApp
    #    venga al frente. Si no esta abierta, esto falla silenciosamente.
    try:
        focus_result = executor("window", {"action": "focus", "title": "WhatsApp"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": f"focus call failed: {exc}",
            "wait_seconds": wait_seconds,
            "delivery_verified": "unverified",
        }
    focus_ok = bool(focus_result.get("ok"))

    # 3. Verificar que la ventana activa es realmente WhatsApp antes del Enter.
    #    Damos un pequeño grace para que el focus tome efecto.
    _time.sleep(0.3)
    try:
        active = executor("window", {"action": "active"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": f"active check failed: {exc}",
            "wait_seconds": wait_seconds,
            "delivery_verified": "unverified",
        }
    active_title = str(
        (active.get("active") or {}).get("title")
        if isinstance(active.get("active"), dict)
        else (active.get("title") or "")
    ).lower()
    if "whatsapp" not in active_title:
        return {
            "sent": False, "focus_verified": False,
            "abort_reason": (
                f"active window is {active_title!r}, not WhatsApp. "
                "Refusing to send Enter to a different app."
            ),
            "wait_seconds": wait_seconds,
            "focus_call_ok": focus_ok,
            "delivery_verified": "unverified",
        }

    # 3b. Snapshot del área de chat ANTES del Enter (para detectar el cambio
    #     visual que prueba que el mensaje salió). Si el cliente está deslogueado
    #     (QR) no hay área de chat -> no habrá cambio -> no confirmamos.
    chat_area_before = _capture_whatsapp_chat_area(executor)

    # 4. Enter — la ventana correcta esta en foco, podemos enviar el mensaje.
    try:
        keypress_result = executor("gui", {"action": "keypress", "keys": "enter"})
    except Exception as exc:
        return {
            "sent": False, "focus_verified": True,
            "abort_reason": f"keypress failed: {exc}",
            "wait_seconds": wait_seconds,
            "delivery_verified": "unverified",
        }
    if not keypress_result.get("ok"):
        return {
            "sent": False, "focus_verified": True,
            "abort_reason": f"keypress returned: {keypress_result.get('error', 'unknown')}",
            "wait_seconds": wait_seconds,
            "delivery_verified": "unverified",
        }

    # 5. GATE de entrega: confirmar por PANTALLA que el mensaje salió.
    #    "confirmed" = el texto del mensaje aparece en el chat (OCR).
    #    "changed"   = el área de chat cambió tras el Enter (mensaje nuevo).
    #    "unverified"= ni una ni otra -> probablemente deslogueado / QR / falló.
    _time.sleep(0.8)
    chat_area_after = _capture_whatsapp_chat_area(executor)
    visual_changed = _whatsapp_chat_area_changed(chat_area_before, chat_area_after)
    message_status = (
        _verify_visible_whatsapp_text_status(executor, text) if text else "unknown"
    )
    if message_status == "confirmed":
        delivery = "confirmed"
    elif visual_changed:
        delivery = "changed"
    else:
        delivery = "unverified"

    if delivery == "unverified":
        # No vimos el mensaje ni cambio de pantalla: NO afirmar sent=True.
        # Cubre el caso deslogueado/QR y cualquier no-entrega silenciosa.
        return {
            "sent": False, "focus_verified": True,
            "abort_reason": (
                "no pude confirmar en pantalla que el mensaje se haya enviado "
                "(WhatsApp puede estar deslogueado/mostrando el QR, o el chat no "
                "cargó). No afirmo el envío sin verlo en el chat."
            ),
            "wait_seconds": wait_seconds,
            "active_window_title": active_title,
            "delivery_verified": delivery,
            "sent_message_visible_status": message_status,
            "sent_message_area_changed": visual_changed,
        }

    return {
        "sent": True, "focus_verified": True,
        "abort_reason": None,
        "wait_seconds": wait_seconds,
        "active_window_title": active_title,
        "delivery_verified": delivery,
        "sent_message_visible_status": message_status,
        "sent_message_area_changed": visual_changed,
    }


def whatsapp_tool(
    args: dict[str, Any],
    state: AgentState,
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Compound WhatsApp tool.

    Actions:
      - status:        report whether WhatsApp Desktop (UWP) is installed.
      - send_message:  open WhatsApp chat with phone + pre-filled text.
                        With auto_send=True (default) the tool waits for the
                        chat to load, focuses the WhatsApp window, verifies
                        active window is WhatsApp, then sends Enter — message
                        is actually delivered. With auto_send=False the chat
                        opens but Enter is NOT pressed (legacy behavior).
      - open_chat:     same as send_message but without text (just opens chat,
                        auto_send is ignored here).

    Phone resolution priority:
      1. args.phone (explicit, validated and normalized)
      2. args.contact / args.recipient / args.to / args.name -> lookup in
         state contacts (using existing _contacts_resolve_recipient).

    Safety for auto_send:
      - NEVER sends Enter without confirming the active window title contains
        "WhatsApp". This prevents sending Enter to a wrong window (IDE,
        terminal with destructive command, browser form, etc.).
      - If focus or active-window check fails, returns sent=False with
        abort_reason — the user sees the chat opened and can press Enter
        themselves.

    Defaults:
      auto_send=True for send_message (Meta deeplink doesn't actually auto-send;
      we provide a safe wrapper that does it via a verified keypress sequence).
      Pass auto_send=False if you only want the chat opened for the user to
      review/edit before sending.
    """
    import urllib.parse

    action = str(args.get("action") or "send_message").casefold()

    if action == "status":
        app_info = _find_whatsapp_app()
        return _ok(
            installed=app_info["kind"] is not None,
            app_kind=app_info["kind"],
            launch_target=app_info["launch_target"],
            web_fallback="https://wa.me/<phone>?text=<msg>",
            auto_send_supported=executor is not None,
            note=(
                "send_message with auto_send=True (default) opens chat AND sends "
                "after verifying focus. Set auto_send=False to only open the chat."
            ),
        )

    if action not in {"send_message", "open_chat", "send"}:
        return _err(
            f"unknown action: {action!r}",
            hint="Use action='send_message', 'open_chat', or 'status'.",
        )

    # Resolver destinatario.
    resolved = _resolve_whatsapp_recipient(args, state)
    if isinstance(resolved, dict):  # error
        return resolved
    raw_phone, normalized, source, gui_search_name = resolved

    # Mensaje (opcional para open_chat).
    text = str(args.get("text") or args.get("message") or args.get("body") or "").strip()
    if action in {"send_message", "send"} and not text:
        return _err(
            "missing text for send_message",
            hint="Pass text='<your message>' or use action='open_chat' to just open the chat.",
            status="needs_user",
        )

    # auto_send default True para send_message; False para open_chat.
    # Acepta string truthy/falsy y bool. Si executor=None, no podemos auto_send.
    auto_send_raw = args.get("auto_send", action != "open_chat")
    if isinstance(auto_send_raw, str):
        auto_send = auto_send_raw.strip().lower() not in {"", "false", "0", "no", "off"}
    else:
        auto_send = bool(auto_send_raw)
    if executor is None:
        auto_send = False  # sin executor no podemos focus+keypress
    # open_chat nunca envia: solo abre.
    if action == "open_chat":
        auto_send = False

    # PATH GUI SEARCH: si el resolver indico que necesitamos buscar el
    # contacto via la UI de WhatsApp (porque no tenemos phone), usar el
    # flujo Ctrl+F + type contact_name + Enter + type message + Enter.
    # Esto cubre contactos que existen en WhatsApp pero no en nuestro
    # contacts store local.
    if source == "gui_search" and gui_search_name and executor is not None:
        app_info = _find_whatsapp_app()
        if not app_info["kind"]:
            return _err(
                f"WhatsApp Desktop not installed; cannot search for contact {gui_search_name!r}",
                status="needs_user", provider="whatsapp",
                hint=("Install WhatsApp Desktop from Microsoft Store, OR add "
                      f"the contact phone first: contacts(action='create', "
                      f"name='{gui_search_name}', phone='+...')."),
            )
        wait_seconds_raw = args.get("wait_seconds") or args.get("send_delay_s") or 2.0
        try:
            wait_seconds = max(0.5, min(10.0, float(wait_seconds_raw)))
        except (TypeError, ValueError):
            wait_seconds = 2.0
        gui_result = _whatsapp_send_via_gui_search(
            executor, gui_search_name, text, wait_seconds, auto_send,
        )
        sent = bool(gui_result.get("sent"))
        chat_opened = bool(gui_result.get("chat_opened"))
        return _ok(
            action=action,
            provider="whatsapp_desktop_gui_search",
            recipient_contact=gui_search_name,
            recipient_source="gui_search",
            text=text or None,
            opened=chat_opened or gui_result.get("steps", []) != [],
            sent=sent,
            chat_opened=chat_opened,
            auto_send_attempted=auto_send,
            physical_actions_ok=bool(gui_result.get("physical_actions_ok")),
            gui_search_info=gui_result,
            verified=sent,
            status="dispatched" if sent else "attempted",
            completion_search="message_sent_via_gui_search" if sent
                               else "chat_search_partial",
            completion_status="message_sent" if sent
                               else ("chat_opened_pending_message"
                                     if chat_opened else "search_aborted"),
            note=(
                f"Sent {text!r} to {gui_search_name!r} via WhatsApp Desktop GUI search."
                if sent else
                f"WhatsApp GUI search for {gui_search_name!r} did not complete. "
                f"Reason: {gui_result.get('abort_reason') or 'unknown'}. "
                f"Steps completed: {gui_result.get('steps')}."
            ),
        )
    if source == "gui_search" and executor is None:
        return _err(
            f"contact {gui_search_name!r} requires GUI search but no executor "
            "available (CLI mode)",
            status="needs_user",
            hint=(
                "From CLI, pass phone='+...' explicitly, or run inside the agent "
                "where executor is wired."
            ),
        )
    # Tiempo de espera tras el deeplink antes de mandar Enter. Configurable
    # via args.wait_seconds. Default 1.8s — suficiente para que WhatsApp
    # Desktop ya este corriendo cargue el chat y rellene el input. Primera
    # vez en frio puede tardar mas; el user puede subirlo.
    wait_seconds_raw = args.get("wait_seconds") or args.get("send_delay_s") or 1.8
    try:
        wait_seconds = float(wait_seconds_raw)
    except (TypeError, ValueError):
        wait_seconds = 1.8
    wait_seconds = max(0.3, min(10.0, wait_seconds))

    # Construir URLs. Deeplink desktop scheme y wa.me como fallback.
    encoded_text = urllib.parse.quote(text) if text else ""
    deeplink = f"whatsapp://send?phone={normalized}"
    if encoded_text:
        deeplink += f"&text={encoded_text}"
    web_url = f"https://wa.me/{normalized}"
    if encoded_text:
        web_url += f"?text={encoded_text}"

    app_info = _find_whatsapp_app()
    desktop_err: str | None = None

    # PATH 1: WhatsApp Desktop instalado -> deeplink whatsapp://
    if app_info["kind"] and os.name == "nt":
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", deeplink],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, FileNotFoundError) as exc:
            desktop_err = str(exc)
        else:
            # Auto-send si esta habilitado y tenemos executor.
            auto_send_info: dict[str, Any] | None = None
            if auto_send and executor is not None:
                auto_send_info = _whatsapp_auto_send(executor, wait_seconds, text)
            sent = bool(auto_send_info and auto_send_info.get("sent"))
            return _ok(
                action=action,
                provider="whatsapp_desktop",
                recipient_phone=raw_phone,
                recipient_normalized=normalized,
                recipient_source=source,
                text=text or None,
                deeplink=deeplink,
                app_kind=app_info["kind"],
                opened=True,
                sent=sent,
                auto_send_attempted=auto_send,
                auto_send_info=auto_send_info,
                verified=sent,
                status="dispatched" if sent else "attempted",
                completion_status="message_sent" if sent
                                   else "chat_opened_pending_enter",
                note=(
                    "Message sent: WhatsApp focused + verified active window + Enter pressed."
                    if sent
                    else (
                        f"WhatsApp Desktop opened with chat pre-filled. "
                        f"{'Auto-send aborted: ' + (auto_send_info or {}).get('abort_reason', '?') + '. ' if auto_send_info and not sent else ''}"
                        "User can press Enter manually."
                    )
                ),
            )

    # PATH 2: fallback a wa.me (web). Auto_send aqui es mas fragil porque
    # depende del estado del browser (loguead/no, "Continuar al chat" click,
    # etc). Mantenemos auto_send=False en este path por seguridad.
    try:
        import webbrowser
        opened = webbrowser.open(web_url)
        if opened:
            result = _ok(
                action=action,
                provider="whatsapp_web",
                recipient_phone=raw_phone,
                recipient_normalized=normalized,
                recipient_source=source,
                text=text or None,
                url=web_url,
                opened=True,
                sent=False,
                auto_send_attempted=auto_send,
                auto_send_info={"abort_reason": "web fallback does not support auto_send safely"}
                                if auto_send else None,
                verified=False,
                status="attempted",
                completion_status="chat_opened_pending_enter",
                note=(
                    "wa.me (WhatsApp Web) opened in default browser. Auto-send "
                    "is disabled on the web path because we cannot reliably "
                    "verify the chat input has focus. User must click "
                    "'Continuar al chat' and press Enter."
                ),
            )
            if desktop_err:
                result["fallback_from"] = "whatsapp_desktop"
                result["fallback_reason"] = desktop_err
            return result
    except Exception as exc:
        return _err(
            f"Could not open WhatsApp (desktop deeplink and web both failed): {exc}",
            status="failed", provider="whatsapp",
            desktop_error=desktop_err,
        )
    return _err(
        "WhatsApp: no desktop app and webbrowser refused to open wa.me",
        status="needs_user", provider="whatsapp",
        install_hint="winget install WhatsApp.WhatsApp",
    )
