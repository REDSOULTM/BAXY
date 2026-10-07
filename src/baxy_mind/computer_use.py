"""Motor de computer use, lado mente (documentacion/computer-use/CONTRATO_VISTA_ACCION.md).

Tres responsabilidades, ninguna sabe de una aplicación concreta:

1. **Leer el pedido** (`mission_request`): «en <app> <hacé X>», «abre <app> y
   <hacé X>», «<hacé X> en <app>», «andá a la pestaña
   de X» → una misión ``mission.computer.use`` con
   aplicación, objetivo y la comprobación de éxito determinista (§4.3). La
   aplicación tiene que estar en el catálogo de Inicio, o ser la categoría
   «navegador» (el navegador predeterminado de la persona) cuando sólo se nombra
   una pestaña; el resto de la frase es el objetivo, con el verbo en cualquier
   persona (tú, vos, usted, infinitivo, inglés).
2. **Elegir un paso** (`decide_step`): la vista compacta se serializa en pocas
   líneas, el modelo contesta UN acto con esquema JSON estricto a temperatura
   0, y unas comprobaciones sin modelo deciden si ese acto es legítimo: la
   etiqueta existe en la vista, la evidencia de «done» está en pantalla, no se
   escribe en una contraseña, no se repite el paso que acaba de fallar.
3. **Proyectar lo observado** para el compositor (`project_seen`,
   `mission_defect`): qué se hizo, con qué evidencia, y los vetos —«entré al
   canal» sin ``seen.joined``, pasado falso, misión no lograda narrada como
   logro—.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from . import effect_intent
from .semantic.missions import (
    KEYS,
    _key_from_words,
    fold,
)

OPERATION = "mission.computer.use"
STEP_REQUEST = "computer.use.step"
STEP_RESULT = "computer.use.step.result"

# El repertorio cerrado del bucle (contrato §2).
ACTS = ("click", "type", "key", "scroll", "open", "done", "none")

# ------------------------------------------------------------- elegir un paso

STEP_PROMPT = (
    "Sos el motor de computer use de BAXY. Ves la ventana de delante como texto: una "
    "lista de controles (índice · tipo · nombre · estado · zona · color) y el texto leído "
    "por zonas. Devolvés EXACTAMENTE UN acto en JSON compacto: "
    '{"act":"click","i":N} (N = índice del control), {"act":"click","text":"…"} (un texto escrito en '
    'pantalla que no es control), {"act":"type","text":"…"}, {"act":"key","key":"…"}, '
    '{"act":"scroll","direction":"down|up"}, {"act":"open","application":"…"}, '
    '{"act":"done","evidence":"…"} (texto de la vista que prueba el objetivo) o {"act":"none"}. '
    "Reglas: sólo controles o textos que están en la vista; si el objetivo ya se ve cumplido, done con "
    "la evidencia literal; si el último paso falló, otro control u otro acto; para escribir hace falta "
    "un campo enfocado; nunca en una contraseña; números, expresiones o textos con type completo y "
    "después key enter si hace falta. Si el destino no está en la vista: un campo de búsqueda (click), "
    "o key ctrl_k / ctrl_f, escribí el nombre y elegí el resultado; si no, scroll. Si un clic abrió un "
    "menú, elegí la opción que lleva al destino. done sólo cuando ves la página o sección pedida: citá "
    "algo de ella, no sólo su nombre."
)


def _gbnf_quoted(value: str) -> str:
    """A GBNF literal that matches the JSON text ``"value"``."""

    return '"\\"' + value + '\\""'


def _gbnf_string(name: str, limit: int) -> str:
    """A JSON string of at most ``limit`` plain characters (no control characters, simple escapes)."""

    return (
        f'{name} ::= "\\"" {name}-char{{0,{limit}}} "\\""\n'
        f'{name}-char ::= [^"\\\\\\x00-\\x1F] | "\\\\" ["\\\\/bfnrt]'
    )


# The act first and only the fields it needs (measured: the nine-field reply cost ≈148 tokens, ≈3.2 s of the
# ≈4 s model step). Compact JSON, no whitespace: every character is a model pass.
STEP_GRAMMAR = "\n".join([
    'root ::= "{" ' + _gbnf_quoted("act") + ' ":" (click | type | key | scroll | open | done | none) "}"',
    "click ::= " + _gbnf_quoted("click") + ' "," (' + _gbnf_quoted("i") + ' ":" index | '
    + _gbnf_quoted("text") + ' ":" short)',
    "type ::= " + _gbnf_quoted("type") + ' "," ' + _gbnf_quoted("text") + ' ":" long',
    "key ::= " + _gbnf_quoted("key") + ' "," ' + _gbnf_quoted("key") + ' ":" ('
    + " | ".join(_gbnf_quoted(key) for key in KEYS) + ")",
    "scroll ::= " + _gbnf_quoted("scroll") + ' "," ' + _gbnf_quoted("direction") + ' ":" ('
    + _gbnf_quoted("down") + " | " + _gbnf_quoted("up") + ")",
    "open ::= " + _gbnf_quoted("open") + ' "," ' + _gbnf_quoted("application") + ' ":" short',
    "done ::= " + _gbnf_quoted("done") + ' "," ' + _gbnf_quoted("evidence") + ' ":" short',
    "none ::= " + _gbnf_quoted("none"),
    "index ::= [0-9] | [1-5] [0-9]",
    _gbnf_string("short", 80),
    _gbnf_string("long", 400),
])


def compact_view_text(view: dict, limit_controls: int = 60, limit_lines: int = 40) -> str:
    """The view as the model reads it: one short line per control, then the text by zone."""

    lines: list[str] = []
    window = view.get("window") if isinstance(view, dict) else None
    if isinstance(window, dict):
        title = str(window.get("title") or "")[:80]
        process = str(window.get("process") or "")[:40]
        lines.append(f"ventana: «{title}» ({process})")
        focused = window.get("focused")
        if isinstance(focused, dict) and focused.get("name"):
            value = focused.get("value")
            lines.append(
                f"foco: {focused.get('kind')} «{str(focused.get('name'))[:60]}»"
                + (f" valor=«{str(value)[:40]}»" if value else "")
            )
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        lines.append("controles:")
        for control in controls[:limit_controls]:
            if not isinstance(control, dict):
                continue
            bits = [str(control.get("i")), str(control.get("kind") or ""), "«" + str(control.get("name") or "")[:60] + "»"]
            state = str(control.get("state") or "")
            if state:
                bits.append(state)
            value = control.get("value")
            if value:
                bits.append("valor=«" + str(value)[:40] + "»")
            zone = control.get("zone")
            if zone:
                bits.append(str(zone))
            color = control.get("color")
            if color and color not in {"gray", "white", "black"}:
                bits.append(str(color))
            repeated = control.get("repeated")
            if isinstance(repeated, int) and repeated > 0:
                bits.append(f"x{repeated + 1}")
            lines.append(" · ".join(bits))
    appeared = view.get("newText") if isinstance(view, dict) else None
    if isinstance(appeared, list) and appeared:
        lines.append("apareció tras el último paso: " + " · ".join("«" + str(line)[:60] + "»" for line in appeared[:12]))
    text = view.get("text") if isinstance(view, dict) else None
    if isinstance(text, dict):
        count = 0
        for zone in ("TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"):
            zone_lines = text.get(zone)
            if not isinstance(zone_lines, list) or not zone_lines:
                continue
            kept = []
            for line in zone_lines:
                if count >= limit_lines:
                    break
                kept.append(str(line)[:80])
                count += 1
            if kept:
                lines.append(f"texto {zone}: " + " | ".join(kept))
    return "\n".join(lines)


def _view_strings(view: dict) -> list[str]:
    found: list[str] = []
    window = view.get("window") if isinstance(view, dict) else None
    if isinstance(window, dict):
        found.append(str(window.get("title") or ""))
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        for control in controls:
            if isinstance(control, dict):
                found.append(str(control.get("name") or ""))
                if control.get("value"):
                    found.append(str(control.get("value")))
    text = view.get("text") if isinstance(view, dict) else None
    if isinstance(text, dict):
        for zone_lines in text.values():
            if isinstance(zone_lines, list):
                found.extend(str(line) for line in zone_lines)
    return found


def view_contains(view: dict, needle: str) -> bool:
    folded = fold(needle)
    if not folded:
        return False
    joined = " ".join(fold(item) for item in _view_strings(view))
    return folded in joined


def _edit_distance(left: str, right: str, cap: int) -> int:
    if abs(len(left) - len(right)) > cap:
        return cap + 1
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, 1):
        current = [row]
        for column, right_char in enumerate(right, 1):
            current.append(min(previous[column] + 1, current[column - 1] + 1, previous[column - 1] + (left_char != right_char)))
        if min(current) > cap:
            return cap + 1
        previous = current
    return previous[-1]


def label_names(label: str, name: str) -> bool:
    """Requested label against a seen name: folded equality, containment, or a typo per five letters."""

    needle, haystack = fold(label), fold(name)
    if not needle or not haystack:
        return False
    if needle == haystack or needle in haystack:
        return True
    allowed = len(needle) // 5
    return allowed > 0 and _edit_distance(needle, haystack, allowed) <= allowed


def find_control(view: dict, label: str, index: int | None = None, kind: str | None = None) -> dict | None:
    """The one control the label (and index, when given; of that kind, when given) names; None when absent or
    ambiguous."""

    listed = view.get("controls") if isinstance(view, dict) else None
    if not isinstance(listed, list):
        return None
    if isinstance(index, int) and 0 <= index < len(listed):
        candidate = listed[index]
        if (
            isinstance(candidate, dict)
            and (kind is None or candidate.get("kind") == kind)
            and label_names(label, str(candidate.get("name") or ""))
        ):
            return candidate
    controls = [control for control in listed if isinstance(control, dict) and (kind is None or control.get("kind") == kind)]
    exact = [control for control in controls if fold(control.get("name")) == fold(label)]
    if len(exact) == 1:
        return exact[0]
    loose = [control for control in controls if label_names(label, str(control.get("name") or ""))]
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        # «Biblioteca» as a navigation item and as a heading: the actionable one wins when unique.
        actionable = [control for control in loose if str(control.get("kind")) in effect_intent_actionable_kinds()]
        if len(actionable) == 1:
            return actionable[0]
    return None


_KIND_WORDS: dict[str, str] = {
    "pestana": "TabItem", "tab": "TabItem", "solapa": "TabItem", "boton": "Button", "button": "Button",
    "enlace": "Hyperlink", "link": "Hyperlink", "casilla": "CheckBox", "checkbox": "CheckBox",
}


def effect_intent_actionable_kinds() -> frozenset[str]:
    return frozenset({
        "Button", "MenuItem", "ListItem", "TabItem", "Hyperlink", "CheckBox", "RadioButton",
        "Edit", "ComboBox", "TreeItem", "SplitButton", "Slider", "Document",
    })


def _text_line_with(view: dict, label: str) -> str | None:
    text = view.get("text") if isinstance(view, dict) else None
    if not isinstance(text, dict):
        return None
    hits = []
    for zone_lines in text.values():
        if isinstance(zone_lines, list):
            for line in zone_lines:
                if label_names(label, str(line)):
                    hits.append(str(line))
    # The OCR reads the window twice (plain and darkened), so a word on screen once is often in two lines; where it
    # is, and whether it is one place, is the click cascade's business (it refuses an ambiguous word).
    return hits[0] if hits else None


def _focused(view: dict) -> dict | None:
    window = view.get("window") if isinstance(view, dict) else None
    focused = window.get("focused") if isinstance(window, dict) else None
    return focused if isinstance(focused, dict) else None


def _focused_is_password(view: dict) -> bool:
    controls = view.get("controls") if isinstance(view, dict) else None
    if isinstance(controls, list):
        for control in controls:
            if isinstance(control, dict) and "focused" in str(control.get("state") or "") and "password" in str(control.get("state") or ""):
                return True
    return False


_COMPOSER_NAME = re.compile(r"\b(?:mensaj|message|chat|escrib|say\s+something|type\s+a\s+message|conversa)")


def _composer_with_text(view: dict) -> bool:
    """Enter over a message composer that holds text reaches a person (contract §2.1)."""

    focused = _focused(view)
    if focused is None:
        return False
    name = fold(focused.get("name"))
    value = str(focused.get("value") or "").strip()
    return bool(value) and _COMPOSER_NAME.search(name) is not None


def application_is_in_front(view: dict, application: str | None) -> bool:
    if not application:
        return True
    window = view.get("window") if isinstance(view, dict) else None
    if not isinstance(window, dict):
        return False
    haystack = fold(window.get("title")) + " " + fold(window.get("process"))
    tokens = [token for token in fold(application).split() if len(token) >= 3 and token not in {"the", "los", "las", "navegador", "browser", "google", "microsoft", "mozilla"}]
    return any(token in haystack for token in tokens) if tokens else fold(application) in haystack


_CALC_TRANSLATE = str.maketrans({"×": "*", "x": "*", "X": "*", "÷": "/", "−": "-", ",": "."})


def _expression_for_typing(expression: str) -> str:
    return "".join(expression.translate(_CALC_TRANSLATE).split())


def _steps_ok(history: list[dict], operation: str, **match: str) -> list[dict]:
    found = []
    for step in history:
        if step.get("operation") != operation or step.get("ok") is not True:
            continue
        if all(fold(step.get(key)) == fold(value) for key, value in match.items()):
            found.append(step)
    return found


def deterministic_step(
    *,
    goal: str,
    view: dict,
    history: list[dict],
    application: str | None = None,
) -> dict[str, object] | None:
    """The step the goal itself dictates when the view shows it (contract §4.2):
    a key to press, a text or an expression to type, a named control to click
    or to switch, a tab to close while more than one is open. No model, no
    application knowledge; anything else, or a step that just failed, goes to
    the model."""

    folded_goal = fold(goal)
    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is not None and last.get("ok") is not True:
        # An opening that could not be verified but left the application in
        # front (measured: the Calculator's hosted window is invisible to the
        # opener's inventory) does not stop what the goal dictates.
        if not (last.get("operation") == "app.open" and application_is_in_front(view, application)):
            return None
    reason = "el objetivo lo dice"
    if folded_goal.startswith("apretar "):
        key = _key_from_words(folded_goal[len("apretar "):])
        if key is not None and not _steps_ok(history, "input.key.press", key=key):
            arguments: dict[str, object] = {"key": key}
            if key == "enter" and _composer_with_text(view):
                arguments["target"] = "message_composer"
            return {"operation": "input.key.press", "arguments": arguments, "reason": reason}
        return None
    if folded_goal.startswith("calcular "):
        expression = _expression_for_typing(goal[len("calcular "):])
        if not expression:
            return None
        if not _steps_ok(history, "input.text.type"):
            return {"operation": "input.text.type", "arguments": {"text": expression}, "reason": reason}
        if not _steps_ok(history, "input.key.press", key="enter"):
            return {"operation": "input.key.press", "arguments": {"key": "enter"}, "reason": reason}
        return None
    if folded_goal.startswith("escribir "):
        text = goal[len("escribir "):].strip()
        if text and not _steps_ok(history, "input.text.type") and not _focused_is_password(view):
            return {"operation": "input.text.type", "arguments": {"text": text}, "reason": reason}
        return None
    for head, wanted in (("ir a ", None), ("hacer clic en ", None), ("activar ", "on"), ("desactivar ", "off")):
        if not folded_goal.startswith(head):
            continue
        target = re.sub(r"^(?:el|la|los|las|the|al|a\s+la|a\s+los|a\s+las)\s+", "", goal[len(head):].strip(), flags=re.IGNORECASE)
        # «la pestaña YouTube», «el botón Guardar»: the kind said before the name narrows the controls to it
        # (a tab's name is its whole title, «Never Gonna Give You Up - YouTube»).
        named_kind = re.match(r"(?P<word>[^\W\d_]+)\s+(?:(?:de|del|of)\s+)?(?P<name>\S.*)$", target)
        kind = _KIND_WORDS.get(fold(named_kind.group("word"))) if named_kind is not None else None
        if named_kind is not None and kind is not None:
            target = named_kind.group("name")
        control = find_control(view, target, kind=kind)
        opened = _menu_opened_by(view, history, target)
        if opened is not None:
            # The click on the destination opened a short menu instead of going there (measured on Steam: «BIBLIOTECA»
            # → «Página principal · Colecciones · Descargas»): its first entry is the destination's own page.
            return {"operation": "input.visible.click", "arguments": {"label": opened}, "reason": "el clic abrió un menú"}
        if control is None:
            # A window drawn without an accessible tree (CEF, Electron, canvas: measured on Steam, one control and
            # the navigation only in the OCR lines): the word written on screen is clicked by its label, and the
            # click's cascade (UIA → OCR → vision) finds where it is.
            if wanted is None and kind is None and _text_line_with(view, target) is not None                     and not _steps_ok(history, "input.visible.click", label=target):
                return {"operation": "input.visible.click", "arguments": {"label": target}, "reason": reason}
            return None
        if wanted is not None and wanted in str(control.get("state") or "").split():
            return None
        if _steps_ok(history, "input.visible.click", label=str(control.get("name") or "")):
            return None
        arguments = {"label": str(control.get("name") or target)}
        if isinstance(control.get("i"), int):
            arguments["index"] = control["i"]
        return {"operation": "input.visible.click", "arguments": arguments, "reason": reason}
    return None


def _menu_opened_by(view: dict, history: list[dict], target: str) -> str | None:
    """The first entry of the short menu the last click, made on ``target``, opened; None otherwise."""

    last = history[-1] if history and isinstance(history[-1], dict) else None
    if last is None or last.get("operation") != "input.visible.click" or last.get("ok") is not True:
        return None
    if not label_names(target, str(last.get("label") or "")):
        return None
    # A menu's entries are short new lines; the OCR also rereads, garbled, the long lines the menu now covers.
    appeared = [
        str(line).strip() for line in (view.get("newText") or [])
        if str(line).strip() and len(str(line).split()) <= 3 and len(str(line)) <= 30
    ]
    if not 1 < len(appeared) <= 6:
        return None
    first = appeared[0]
    return None if label_names(target, first) or _steps_ok(history, "input.visible.click", label=first) else first


def decide_step(
    llm: Any,
    *,
    objective: str,
    goal: str,
    application: str | None,
    success_check: str | None,
    view: dict,
    history: list[dict],
    budget_left: int,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> dict[str, object]:
    """One step for the shell: {operation, arguments, reason}; operation is a
    catalog primitive, «done» or «none»."""

    # Deterministic first: the application named by the request is not in
    # front and nothing was done yet → bring it to the front (app.open reuses a
    # running window). No model needed for what the request already says.
    if application and not history and not application_is_in_front(view, application):
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names)
        if app_id is not None:
            return {"operation": "app.open", "arguments": {"appId": app_id}, "reason": "la aplicación pedida no está delante"}
    dictated = deterministic_step(goal=goal, view=view, history=history, application=application)
    if dictated is not None:
        return dictated
    last_failed = history[-1] if history and isinstance(history[-1], dict) and history[-1].get("ok") is False else None
    user = (
        f"Pedido: {objective}\nObjetivo: {goal}"
        + (f"\nAplicación: {application}" if application else "")
        + (f"\nSe cumple cuando: {success_check}" if success_check else "")
        + f"\nPasos que quedan: {budget_left}\n"
        + ("Historial:\n" + "\n".join(_history_line(step) for step in history[-6:]) + "\n" if history else "")
        + "Vista:\n" + compact_view_text(view)
    )
    payload = {
        "messages": [
            {"role": "system", "content": STEP_PROMPT},
            {"role": "user", "content": user},
        ],
        "grammar": STEP_GRAMMAR,
        "temperature": 0.0,
        "max_tokens": 160,
        "cache_prompt": True,
        "seed": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    raw = _model_step(llm, payload)
    if raw is None:
        return _none("el modelo no dio un paso legible", code="decision_unreadable")
    decision = validate_decision(raw, view=view, history=history, last_failed=last_failed, application_names=application_names, goal=goal)
    if decision["operation"] == "none" and decision.get("code") in {"label_not_visible", "evidence_not_visible", "already_open", "application_unknown"}:
        # One more try with the rejection in front of the model (contract §4.4).
        payload["messages"].append({"role": "assistant", "content": as_json(raw)})
        payload["messages"].append({"role": "user", "content": f"Ese paso no vale: {decision['reason']}. Elegí otro acto de la vista, o none si no hay ninguno."})
        raw = _model_step(llm, payload)
        if raw is None:
            return _none("el modelo no dio un paso legible", code="decision_unreadable")
        decision = validate_decision(raw, view=view, history=history, last_failed=last_failed, application_names=application_names, goal=goal)
    return decision


def _model_step(llm: Any, payload: dict) -> Any:
    """One strict-JSON step from the model; one more try when the reply cannot be read (measured live: a reply cut
    short left the shell without any step)."""

    for _ in range(2):
        try:
            return llm._post_schema_object(payload, "el paso de computer use")
        except (ValueError, RuntimeError, KeyError, TypeError, OSError):
            continue
    return None


def _history_line(step: dict) -> str:
    parts = [f"{step.get('step')}. {step.get('operation')}"]
    for key in ("label", "key", "text", "direction", "appId"):
        if step.get(key):
            parts.append(f"{key}={str(step.get(key))[:40]}")
    parts.append("ok" if step.get("ok") else f"FALLÓ ({step.get('error') or 'sin efecto'})")
    return " ".join(parts)


def _destination(goal: str | None) -> str:
    """«ir a la biblioteca» → «biblioteca»: the place a go-to goal names, folded; empty for other goals."""

    folded = fold(goal or "")
    if not folded.startswith("ir a "):
        return ""
    return re.sub(r"^(?:el|la|los|las|the|al)\s+", "", folded[len("ir a "):]).strip()


def validate_decision(
    raw: Any,
    *,
    view: dict,
    last_failed: dict | None,
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
    history: list[dict] | None = None,
    goal: str | None = None,
) -> dict[str, object]:
    """The model's act, checked against the view without any model (contract §4.4)."""

    if not isinstance(raw, dict):
        return _none("respuesta inválida del modelo")
    act = str(raw.get("act") or "")
    why = str(raw.get("why") or "")[:160]
    if act == "done":
        evidence = str(raw.get("evidence") or "").strip()
        destination = _destination(goal)
        if destination and fold(evidence).strip(" «»\"'") in {destination, f"la {destination}", f"el {destination}"}:
            # Measured on Steam: «BIBLIOTECA» is on screen before and after the click (it opened a menu); the
            # destination's own name proves nothing. Something of the page reached must be cited.
            return _none("el nombre del destino ya estaba en pantalla antes; citá algo de lo que se ve al llegar",
                         code="evidence_not_visible")
        if evidence and view_contains(view, evidence):
            return {"operation": "done", "arguments": {"evidence": evidence}, "reason": why}
        return _none("la evidencia citada no está en la vista", code="evidence_not_visible")
    if act == "click":
        label = str(raw.get("label") or raw.get("text") or "").strip()
        index = raw.get("i") if isinstance(raw.get("i"), int) and not isinstance(raw.get("i"), bool) else None
        if not label and index is not None:
            controls = view.get("controls") if isinstance(view, dict) else None
            if isinstance(controls, list) and 0 <= index < len(controls) and isinstance(controls[index], dict):
                label = str(controls[index].get("name") or "")
        if not label:
            return _none("el clic no nombra ningún control")
        control = find_control(view, label, index)
        if control is not None:
            arguments: dict[str, object] = {"label": str(control.get("name") or label)}
            if isinstance(control.get("i"), int):
                arguments["index"] = control["i"]
            return _guard_repeat({"operation": "input.visible.click", "arguments": arguments, "reason": why}, last_failed)
        line = _text_line_with(view, label)
        if line is not None:
            return _guard_repeat({"operation": "input.visible.click", "arguments": {"label": label}, "reason": why}, last_failed)
        return _none(f"«{label[:40]}» no está en la vista", code="label_not_visible")
    if act == "type":
        text = str(raw.get("text") or "")
        if not text.strip():
            return _none("no hay texto que escribir")
        if _focused_is_password(view):
            return _none("el campo enfocado es una contraseña", code="password_field")
        return _guard_repeat({"operation": "input.text.type", "arguments": {"text": text[:4096]}, "reason": why}, last_failed)
    if act == "key":
        key = str(raw.get("key") or "")
        if key not in KEYS:
            return _none("tecla fuera del catálogo")
        arguments = {"key": key}
        if key == "enter" and _composer_with_text(view):
            arguments["target"] = "message_composer"
        return _guard_repeat({"operation": "input.key.press", "arguments": arguments, "reason": why}, last_failed)
    if act == "scroll":
        direction = str(raw.get("direction") or "down")
        if direction not in {"down", "up"}:
            direction = "down"
        return _guard_repeat({"operation": "input.scroll", "arguments": {"direction": direction, "amount": 3}, "reason": why}, last_failed)
    if act == "open":
        application = str(raw.get("application") or "").strip()
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names) if application else None
        if app_id is None:
            return _none("la aplicación no está en el catálogo", code="application_unknown")
        if history and _steps_ok(history, "app.open", appId=app_id):
            return _none("esa aplicación ya está abierta", code="already_open")
        return _guard_repeat({"operation": "app.open", "arguments": {"appId": app_id}, "reason": why}, last_failed)
    return _none(why or "el modelo no ve por dónde seguir")


def _guard_repeat(decision: dict[str, object], last_failed: dict | None) -> dict[str, object]:
    if last_failed is None or last_failed.get("operation") != decision["operation"]:
        return decision
    arguments = decision["arguments"]
    assert isinstance(arguments, dict)
    same = all(
        fold(last_failed.get(key)) == fold(arguments.get(key))
        for key in ("label", "key", "text", "direction", "appId")
        if key in arguments or key in last_failed
    )
    return _none("repetiría el paso que acaba de fallar", code="repeated_step") if same else decision


def _none(reason: str, *, code: str = "no_step_visible") -> dict[str, object]:
    return {"operation": "none", "arguments": {}, "reason": reason, "code": code}


# --------------------------------------------------------------- compositor


def describe_step(step: dict, language: str) -> str:
    operation = str(step.get("operation") or "")
    if operation == "input.visible.click":
        return (f"clicked «{step.get('label')}»" if language == "en" else f"clic en «{step.get('label')}»")
    if operation == "input.key.press":
        return (f"pressed {step.get('key')}" if language == "en" else f"tecla {step.get('key')}")
    if operation == "input.text.type":
        return "typed the text" if language == "en" else "escribió el texto"
    if operation == "input.scroll":
        return "scrolled" if language == "en" else "desplazó la vista"
    if operation == "app.open":
        return "brought the application to the front" if language == "en" else "trajo la aplicación al frente"
    return operation


# The typed stop reasons as facts the final can state (the model words them;
# «operación» is a forbidden term in finals, so no cause says it).
_STOP_CAUSES: dict[str, dict[str, str]] = {
    "computer_use_no_step_visible": {"es": "no vi en la pantalla un control con el que seguir", "en": "I did not see on the screen a control to go on with"},
    "computer_use_evidence_not_visible": {"es": "la pantalla no mostró la prueba de que se hubiera logrado", "en": "I did not find on the screen the proof that it was done"},
    "computer_use_budget_exhausted": {"es": "se agotaron los pasos previstos sin llegar", "en": "the planned steps ran out before getting there"},
    "computer_use_time_exhausted": {"es": "se agotó el tiempo previsto sin llegar", "en": "the planned time ran out before getting there"},
    "computer_use_surface_unchanged": {"es": "la pantalla dejó de cambiar tras lo que hice", "en": "the screen stopped changing after what I did"},
    "computer_use_view_unavailable": {"es": "la ventana no se dejó leer", "en": "I could not read the window"},
    "computer_use_decision_unavailable": {"es": "el siguiente paso quedó sin decidir", "en": "I could not decide the next step"},
    "computer_use_repeated_step": {"es": "el único paso que veía ya había fallado", "en": "the only step I could see had already failed"},
    "computer_use_step_failed": {"es": "un paso no se pudo hacer", "en": "a step could not be done"},
    "computer_use_step_arguments_invalid": {"es": "el paso elegido no era válido", "en": "the chosen step was not valid"},
    "computer_use_window_covered": {"es": "otra ventana tapa la aplicación", "en": "another window covers the application"},
}


def project_seen(observed: dict, language: str) -> dict[str, object]:
    """What the composer may say about a mission: only what the loop observed."""

    raw_steps = observed.get("steps")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    done = [step for step in steps if isinstance(step, dict) and step.get("ok") is True]
    failed = [step for step in steps if isinstance(step, dict) and step.get("ok") is not True]
    raw_window = observed.get("window")
    window: dict[str, Any] = raw_window if isinstance(raw_window, dict) else {}
    seen: dict[str, object] = {
        "goal": observed.get("goal"),
        "reached": observed.get("reached") is True,
        "stepsDone": [describe_step(step, language) for step in done][:8],
        "windowTitle": window.get("title"),
        "joined": observed.get("joined") is True,
    }
    if observed.get("application"):
        seen["application"] = observed.get("application")
    if failed:
        seen["stepsFailed"] = [describe_step(step, language) for step in failed][:4]
    if observed.get("evidence"):
        seen["evidence"] = observed.get("evidence")
    if observed.get("satisfiedBy"):
        seen["satisfiedBy"] = observed.get("satisfiedBy")
    if isinstance(observed.get("screen"), dict):
        seen["screen"] = observed.get("screen")
    cover = window.get("coveredBy")
    if isinstance(cover, dict) and (cover.get("title") or cover.get("process")):
        seen["coveredBy"] = str(cover.get("title") or cover.get("process"))
    if observed.get("stoppedBy"):
        seen["stoppedBy"] = observed.get("stoppedBy")
        seen["stoppedBecause"] = _STOP_CAUSES.get(str(observed.get("stoppedBy")), {}).get(
            "en" if language == "en" else "es", str(observed.get("stoppedBy")).replace("_", " ")
        )
        if observed.get("stoppedBy") == "computer_use_window_covered" and seen.get("coveredBy"):
            seen["stoppedBecause"] = (
                f"the window «{seen['coveredBy']}» covers the application"
                if language == "en"
                else f"la ventana «{seen['coveredBy']}» tapa la aplicación"
            )
    if observed.get("procedure") in {"replayed", "learned", "relearned"}:
        seen["procedure"] = observed.get("procedure")
    return seen


def compose_instruction(seen: dict, language: str) -> str:
    del language
    if seen.get("reached"):
        return (
            "This result is a computer-use mission that REACHED its goal: seen.goal is what was asked, "
            "seen.stepsDone the acts done in order (clicks, keys, typing) on the window seen.windowTitle, "
            "seen.evidence the text on screen that proves it when present, seen.screen what the window showed "
            "at the end (seen.screen.numbers: the controls and lines carrying a number, such as a display or a "
            "counter; seen.screen.values: its fields; seen.screen.lines: a few lines). When the goal asked for a "
            "calculation, a number or a value, quote the matching entry of seen.screen.numbers exactly; do not "
            "list the other lines of the window. Say in one short sentence, in "
            "the person's language, in the FIRST PERSON (you are the one who acted; never the third person, never "
            "your own name) and in the past tense, what you did and what you saw; when the goal was a "
            "result, lead with it; quote seen.evidence "
            "exactly when it exists. seen.joined says whether a voice channel or call was joined: say you "
            "joined only if it is true. Never add steps, times or results that are not in seen: when the goal was "
            "pressing a key or typing, say only that you did it in that app, never that it completed something or "
            "what it caused."
        )
    return (
        "This result is a computer-use mission that did NOT reach its goal: seen.goal is what was asked, "
        "seen.stepsDone what was done before stopping, seen.stepsFailed what could not be done, "
        "seen.stoppedBecause the cause in the person's words. Say in one or two short sentences, in the person's "
        "language and in the FIRST PERSON (you are the one who acted; never the third person), what was done and "
        "that the goal was not reached, giving seen.stoppedBecause as the "
        "cause (reword it lightly, never say «operación» or «operation»). Never say it succeeded and never "
        "invent a cause that is not in seen."
    )


_JOIN_CLAIM = re.compile(
    r"\b(?:me\s+uni|me\s+he\s+unido|nos\s+unimos|joined|entre\s+(?:a|al)\s+(?:el\s+)?canal\s+de\s+voz|estoy\s+en\s+el\s+canal\s+de\s+voz|te\s+uni|ya\s+estoy\s+en\s+la\s+llamada|in\s+the\s+call)\b"
)
_JOIN_NEGATED = re.compile(
    r"\b(?:no|not|sin|didn't|did\s+not|without|todavia\s+no|aun\s+no|never|nunca)\s+(?:\w+\s+){0,2}(?:uni\w*|unir\w*|join\w*|entr\w*)\b"
)
_FALSE_PAST = re.compile(
    r"\b(?:ayer|anoche|antier|anteayer|antes\s+de\s+ayer|la\s+semana\s+pasada|el\s+otro\s+dia|hace\s+(?:un|unos|varios|dos|tres)\s+(?:dia|dias|semana|semanas|hora|horas)|"
    r"yesterday|last\s+night|last\s+week|the\s+other\s+day|days?\s+ago|hours?\s+ago|weeks?\s+ago)\b"
)
_SUCCESS_CLAIM = re.compile(
    r"\b(?:listo|hecho|logrado|conseguido|cumplido|done|achieved|completed|entre\s+a|llegue\s+a|ya\s+estas\s+en|ya\s+esta\s+en|quedo\s+activado|quedo\s+activo|active|activado)\b"
)


def mission_defect(folded_reply: str, seen: dict) -> str | None:
    """Vetos of a mission final: a join never observed, a false past time, a
    failed mission told as a success (contract §4.5)."""

    if _FALSE_PAST.search(folded_reply):
        return "extra_claim"
    claims_join = _JOIN_CLAIM.search(folded_reply) is not None and _JOIN_NEGATED.search(folded_reply) is None
    if claims_join and seen.get("joined") is not True:
        return "joined_claimed"
    if seen.get("joined") is True and _JOIN_NEGATED.search(folded_reply) is not None:
        return "joined_claimed"
    if seen.get("reached") is not True and _SUCCESS_CLAIM.search(folded_reply) and not re.search(r"\b(?:no|not)\b", folded_reply):
        return "reversed_polarity"
    return None


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
