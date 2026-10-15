"""The model's step: its prompt and grammar, the view as the model reads it, the controls similar to the goal,
the history lines, the retry after a rejected act, and the call itself.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from .semantic.cu_buscar import frame_button, naming_words
from .semantic.missions import KEYS, fold
from .semantic.cu_semejanza import CLICK_SIMILARITY, similar_hints
from .cu_view import (
    _STATUS_KINDS, _disabled_controls, _is_switch, _list_holding_items, _scroll_part, _viewed_control, find_control,
)
from .cu_goals import _goal_target
from .cu_fields import _SEARCH_NAME
from .cu_acts import _ACT_KEYS
from .cu_window import _frame_off_goal, _system_menu_off_goal
from .cu_history import key_without_effect
from .cu_unasked import _REMOVAL_NAME, _safe_to_unfold, unasked_act
from .cu_meaning import SemanticMatcher, _free_goal_label, _semantic_control
from .cu_validate import _opens_its_list_instead
from .cu_unfold import _NOT_ACTIONABLE_KINDS, _assistant_or_creating, _unfold_kind_of_goal
from .cu_model_calls import _gbnf_quoted, _gbnf_string


STEP_PROMPT = (
    "Sos el motor de computer use de BAXY. Ves la ventana de delante como texto: una "
    "lista de controles (índice · tipo · nombre · estado · zona · color) y el texto leído "
    "por zonas. Devolvés EXACTAMENTE UN acto en JSON compacto: "
    '{"act":"click","i":N} (N = índice del control), {"act":"click","text":"…"} (un texto escrito en '
    'pantalla que no es control), {"act":"type","text":"…"}, {"act":"type","text":"…","field":"…"} (pone el '
    'campo de formulario de ese nombre en ese valor: reemplaza lo que tenía), {"act":"key","key":"…"}, '
    '{"act":"scroll","direction":"down|up"}, {"act":"reveal","text":"…"} (trae a la vista el elemento de ese '
    'nombre de una lista larga, sin desplazar a ciegas), {"act":"open","application":"…"}, {"act":"open","i":N} (abre sólo la flecha o la lista del control N '
    '—un botón dividido, un desplegable, un menú collapsed— sin pulsar su acción), {"act":"menu","i":N} (el menú '
    'contextual del control N: las órdenes del clic derecho), {"act":"double","i":N} (doble clic en N), '
    '{"act":"done","evidence":"…"} (texto de la vista que prueba el objetivo) o {"act":"none"}. '
    "Reglas: sólo controles o textos que están en la vista; si el objetivo ya se ve cumplido, done con "
    "la evidencia literal; si el último paso falló, otro control u otro acto, nunca el mismo clic: si el control "
    "está dentro de un desplegable, el desplegable; una tecla «sin efecto» no se repite ni se sigue con otra "
    "tecla: el paso siguiente es un control de la vista; nunca la ayuda ni la web si el pedido no las pide; "
    "en un desplegable abierto elegí la opción que dice lo pedido, nunca una parecida; para escribir hace falta "
    "un campo enfocado; nunca en una contraseña; números, expresiones o textos con type completo y "
    "después key enter si hace falta. Una opción de un ajuste de la ventana (vista, orden, tamaño) está dentro del "
    "control que muestra la opción actual o de uno collapsed que la nombra: abrilo; el campo de búsqueda busca "
    "contenido, no opciones. Si el destino no está en la vista: un campo de búsqueda (click), "
    "o key ctrl_k / ctrl_f, escribí el nombre y elegí el resultado; si no, scroll. Si un clic abrió un "
    "menú, elegí la opción que lleva al destino. done sólo cuando ves la página o sección pedida: citá "
    "algo de ella, no sólo su nombre. El objetivo puede estar dicho en otro idioma que el de la ventana: "
    "elegí el control por su significado, no por sus letras; la línea «Parecidos al objetivo» nombra los controles "
    "que lo dicen con otras palabras. Resolvé sólo el Objetivo actual: el resto del Pedido viene en otros "
    "sub-objetivos, ni lo hagas ni lo cites como hecho. Un clic en un elemento de una lista de "
    "contenido sólo lo elige: para entrar en él, key enter; nunca en un instalador, un programa de una lista de "
    "programas ni un archivo que se ejecuta. Una orden que no está en la vista suele vivir en un menú cerrado: la "
    "flecha de un botón dividido (open) o el menú contextual del elemento sobre el que actúa (menu). atajo=… es la "
    "tecla que la aplicación declara para ese control; key sólo con las teclas del esquema."
)


# The act first and only the fields it needs (measured: the nine-field reply cost ≈148 tokens, ≈3.2 s of the
# ≈4 s model step). Compact JSON, no whitespace: every character is a model pass.
STEP_GRAMMAR = "\n".join([
    'root ::= "{" ' + _gbnf_quoted("act") + ' ":" (click | type | key | scroll | reveal | open | menu | double | done | none) "}"',
    "click ::= " + _gbnf_quoted("click") + ' "," (' + _gbnf_quoted("i") + ' ":" index | '
    + _gbnf_quoted("text") + ' ":" short)',
    "type ::= " + _gbnf_quoted("type") + ' "," ' + _gbnf_quoted("text") + ' ":" long ("," '
    + _gbnf_quoted("field") + ' ":" short)?',
    "reveal ::= " + _gbnf_quoted("reveal") + ' "," ' + _gbnf_quoted("text") + ' ":" short',
    "key ::= " + _gbnf_quoted("key") + ' "," ' + _gbnf_quoted("key") + ' ":" ('
    + " | ".join(_gbnf_quoted(key) for key in KEYS) + ")",
    "scroll ::= " + _gbnf_quoted("scroll") + ' "," ' + _gbnf_quoted("direction") + ' ":" ('
    + _gbnf_quoted("down") + " | " + _gbnf_quoted("up") + ")",
    "open ::= " + _gbnf_quoted("open") + ' "," (' + _gbnf_quoted("application") + ' ":" short | '
    + _gbnf_quoted("i") + ' ":" index)',
    "menu ::= " + _gbnf_quoted("menu") + ' "," ' + _gbnf_quoted("i") + ' ":" index',
    "double ::= " + _gbnf_quoted("double") + ' "," ' + _gbnf_quoted("i") + ' ":" index',
    "done ::= " + _gbnf_quoted("done") + ' "," ' + _gbnf_quoted("evidence") + ' ":" short',
    "none ::= " + _gbnf_quoted("none"),
    "index ::= [0-9] | [1-5] [0-9]",
    _gbnf_string("short", 80),
    _gbnf_string("long", 400),
])


_SHOWN_CONTROLS = 30


def _ranked_controls(
    controls: list, goal: str | None, limit: int, names: Iterable[str] = (), view: dict | None = None,
    similar: Iterable[str] = (),
) -> list:
    """The controls the model is shown: a scroll bar's line and page buttons never (``_scroll_part``), nor the window's
    system menu when the goal does not ask for what it does (``_system_menu_off_goal``), and when there
    are more than ``limit``, the one whose whole name is a name of the goal's place first, then the ones whose names
    share words with the goal or with the place's other names (the other language's, ``names``), then the focused,
    selected and search-like ones, then the rest in screen order, and the window's frame buttons last (measured: a
    Discord view of 250 controls cut at the first 60 hid the server that held the target; on a Spanish Word «Insert a
    table» showed the title bar and the side panel, never «Tabla»). A word of the goal never raises a control that
    removes something or changes the account when the goal does not ask for it. ``similar`` (the names most similar
    to the goal by meaning, P1) come right after the whole-name match. The view's own order is kept."""

    seen = view if isinstance(view, dict) else {"controls": controls}
    controls = [
        control for control in controls
        if not _scroll_part(control, seen) and not _system_menu_off_goal(seen, control, goal)
        and not _frame_off_goal(seen, control, goal)
    ]
    if len(controls) <= limit:
        return controls
    names = tuple(str(name) for name in names if str(name).strip())
    wanted = naming_words(goal or "", *names)
    whole = {fold(name).strip() for name in names if fold(name).strip()}
    alike = {fold(name).strip() for name in similar if fold(name).strip()}
    # Ronda 21 (t-menu-2): the list holding the most items is always kept (its empty space is where a list's own menu
    # opens, and the scroll that brings an item goes over it).
    # Review 1 of ronda 24 (finding 2): the holder the wheel turns (the most items) and the one whose empty space opens
    # the list's menu are both kept.
    holders = {
        _list_holding_items({"controls": controls}),
        _list_holding_items({"controls": controls}, empty_space=True),
    } - {None}

    def raised(name: str) -> bool:
        if _REMOVAL_NAME.search(name) and not _REMOVAL_NAME.search(fold(goal)):
            return False
        return unasked_act(name, goal) is None

    def weight(position: int, control: object) -> tuple[int, int]:
        if not isinstance(control, dict):
            return (9, position)
        name = fold(control.get("name"))
        state = str(control.get("state") or "")
        if whole and name.strip() in whole and raised(name):
            return (0, position)
        if alike and name.strip() in alike:
            return (1, position)
        if wanted and any(word in name for word in wanted) and raised(name):
            return (2, position)
        if frame_button(name):
            return (5, position)
        if "focused" in state or "selected" in state or _SEARCH_NAME.search(name):
            return (3, position)
        if control.get("i") in holders:
            return (3, position)
        return (4, position)

    chosen = sorted(range(len(controls)), key=lambda position: weight(position, controls[position]))[:limit]
    return [controls[position] for position in sorted(chosen)]


def compact_view_text(
    view: dict, limit_controls: int = _SHOWN_CONTROLS, limit_lines: int = 40, goal: str | None = None,
    names: Iterable[str] = (), similar: Iterable[str] = (),
) -> str:
    """The view as the model reads it: one short line per control (the ones that matter for the goal when there are
    many, with how many were left out; ``names`` are the other names of the goal's place, ``_ranked_controls``), then
    the text by zone."""

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
        shown = _ranked_controls(controls, goal, limit_controls, names, view, similar)
        lines.append("controles:" if len(shown) == len(controls) else f"controles ({len(shown)} de {len(controls)}):")
        for control in shown:
            if not isinstance(control, dict):
                continue
            bits = [str(control.get("i")), str(control.get("kind") or ""), "«" + str(control.get("name") or "")[:60] + "»"]
            state = str(control.get("state") or "")
            if state:
                bits.append(state)
            value = control.get("value")
            if value:
                bits.append("valor=«" + str(value)[:40] + "»")
            shortcut = str(control.get("shortcut") or "").strip()
            if shortcut:
                # Goal v3 B3: the key the application itself declares for the control (UIA), never a list per app.
                bits.append("atajo=" + shortcut[:24])
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
    disabled = _disabled_controls(view)
    if disabled:
        # Pasada r15b (v3-27, v3-29): «Copiar» and «Buscar» wait for text in their field; the model knows they exist.
        lines.append("deshabilitados (se habilitan con otro paso antes, como escribir en su campo): " + " · ".join(
            f"{control.get('kind')} «{str(control.get('name'))[:40]}»" + (f" {control.get('zone')}" if control.get("zone") else "")
            for control in disabled[:12]
        ))
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


def _similar_controls(
    goal: str, view: dict, place_names: Iterable[str], semantic: SemanticMatcher | None,
) -> list[dict]:
    """P2: the controls of the view most similar to the goal's place (``similar_hints``), for the prompt's line and the
    listing's order; none without an encoder, when the encoder fails, or when the place's own name is on screen."""

    if semantic is None:
        return []
    parsed = _goal_target(goal)
    label = parsed[2] if parsed is not None else _free_goal_label(goal)
    if not label:
        return []
    wanted = parsed[1] if parsed is not None else None
    kind = parsed[3] if parsed is not None else None
    others = [name for name in place_names if fold(name).strip() != fold(label).strip()]
    scored = semantic.scored(label, view, others)
    hints = similar_hints(scored, lambda name: _semantic_control(view, name, goal, wanted, kind, clicking=False) is not None)
    controls = view.get("controls") if isinstance(view, dict) else None
    by_name = {
        str(control.get("name") or "").strip(): control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict)
    }
    scores = {str(name).strip(): score for name, score in scored}
    # Ronda 24 (v3-17: Group «Dimensiones», the Pane of the title bar; v3-40: ScrollBar «Vertical»): a frame or a text
    # is never similar to a goal; each hint carries its similarity for the retry (``retry_instruction``).
    similar = [
        {**by_name[name], "similarity": scores.get(name, 0.0)} for name in hints
        if name in by_name and by_name[name].get("kind") not in _STATUS_KINDS
        and by_name[name].get("kind") not in _NOT_ACTIONABLE_KINDS
        and not _system_menu_off_goal(view, by_name[name], goal)
    ]
    if len(similar) == 1 and _unfold_kind_of_goal(goal) == "place" and _opens_a_menu(similar[0]):
        # Revisión 4 de ronda 24 (t-menu-3: «Ver» alone for «view», 0.855): the one name near a goal of a place is the
        # retry's to name under the click's similarity only when pressing it opens a menu, which shows its entries and
        # changes nothing; a tab or a button turns the window's page or acts (v3-03: «Pestaña Archivo» led to Backstage).
        similar[0]["opensMenu"] = True
    return similar


def _opens_a_menu(control: dict) -> bool:
    """Revisión 4 de ronda 24: a menu's entry (``MenuItem``) that sets nothing (``_is_switch``: never a checkable
    entry), creates nothing, calls no assistant and passes the safety filters of a list opened blind."""

    return (
        control.get("kind") == "MenuItem" and not _is_switch(control) and _safe_to_unfold(control)
        and not _assistant_or_creating(control)
    )


def similar_line(similar: list[dict]) -> str:
    """«Parecidos al objetivo: [8] Biblioteca de videos · [3] Videos»: the indices and names the model may press."""

    return "Parecidos al objetivo: " + " · ".join(
        f"[{control.get('i')}] {str(control.get('name') or '')[:60]}" for control in similar
    )


def retry_instruction(
    reason: str, similar: list[dict], arrow: dict | None = None, *, admits_done: bool = False,
) -> str:
    """The retry after a rejected act: with a similar control on screen it is named and «none» is not offered. Ronda
    20 P4: after a command that already created what was asked (``admits_done``), «done» citing what it made is
    offered first. A rejected click on a control with an arrow (``_rejected_arrow``) offers the opening of its list
    (ronda 20b, palanca 6: v3-38 answered «none» with «Configuración» inside the list of the control it had chosen).
    Integración 20b: when the rejected act would create again what is already there, «done» comes first even on a
    control with an arrow; opening its list is no way to what is already made."""

    if admits_done:
        return (f"Ese paso no vale: {reason}. Si lo creado se ve, elegí done citando lo que apareció; si no, otro acto "
                "de la vista, o none si no hay ninguno.")
    if arrow is not None:
        index = arrow.get("i")
        return (
            f"Ese paso no vale: {reason}. [{index}] «{str(arrow.get('name') or '')[:60]}» tiene flecha: "
            f"{{\"act\":\"open\",\"i\":{index}}} abre su lista sin pulsarlo; elegí un acto de la vista para el "
            "objetivo actual."
        )
    # Ronda 24 (v3-03: «Pestaña Archivo», v3-04: «Tarea siguiente», v3-17: «Examinar texto» named on a low
    # similarity): the retry names a similar control only when it is a control to act on and passes the click's
    # similarity (revisión 1: being the most similar name of the view is no exception; v3-04's «Tarea siguiente» was
    # the first; revisión 3: nor being the one name near a place, v3-03's «Pestaña Archivo» at 0.845 led to Backstage;
    # revisión 4: but the one name near a place that opens a menu, ``opensMenu`` of ``_similar_controls``, t-menu-3);
    # a hint without a measured similarity was chosen by its caller. Otherwise «none» stays offered.
    named = [
        control for control in similar
        if isinstance(control, dict) and control.get("kind") not in _NOT_ACTIONABLE_KINDS and (
            "similarity" not in control or control.get("opensMenu") is True
            or float(control.get("similarity") or 0.0) >= CLICK_SIMILARITY
        )
    ]
    if named:
        first = named[0]
        return (
            f"Ese paso no vale: {reason}. En la vista está [{first.get('i')}] «{str(first.get('name') or '')[:60]}», "
            "parecido al objetivo actual: elegí un acto de la vista para el objetivo actual."
        )
    return f"Ese paso no vale: {reason}. Elegí otro acto de la vista, o none si no hay ninguno."


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
    for key in _ACT_KEYS:
        if step.get(key):
            parts.append(f"{key}={str(step.get(key))[:40]}")
    parts.append("ok" if step.get("ok") else f"FALLÓ ({step.get('error') or 'sin efecto'})")
    if key_without_effect(step):
        parts.append("(sin efecto: la ventana quedó igual)")
    if step.get("checkUnmet") is True:
        # Ronda 23 (v2-s01): the App refused a «done» after this step, the planned check's exact atoms (a result, a
        # value, a count, a file) still false; the model sees why instead of a close the screen contradicts.
        parts.append(CHECK_UNMET_NOTE)
    if step.get("searchNothingNew") is True:
        # Revision 1 of r24b (v1): what bears the query typed was on the window before the search started (the App's
        # «searchNothingNew»): the search showed no new results, and the model never takes that for its answer.
        parts.append(SEARCH_NOTHING_NEW_NOTE)
    return " ".join(parts)


# What the model reads on the step after which its «done» was refused because the screen contradicts the exact part of
# «Se cumple cuando» (the App's «checkUnmet» mark).
CHECK_UNMET_NOTE = (
    "(tras este paso dijiste done, pero la pantalla no muestra el resultado, el valor, la cantidad o el archivo exactos "
    "que pide «Se cumple cuando»: no está hecho; hacé el paso que lo produce o lo evalúa)"
)


# What the model reads on the step after which the query shows only where the window already showed it before the
# search started (the App's «searchNothingNew» mark). Revision 3 of r24b: only what was seen, never a cause guessed
# (whether the search ran is not known from the view).
SEARCH_NOTHING_NEW_NOTE = (
    "(la búsqueda no mostró resultados nuevos: lo que nombra la consulta ya estaba en la ventana antes de buscar y "
    "nada lo filtró)"
)


def _rejected_arrow(raw: object, view: dict, last_failed: dict | None) -> dict | None:
    """The control a rejected click named, when it has an arrow whose opening did not just fail (``retry_instruction``
    offers its «open»)."""

    if not isinstance(raw, dict) or raw.get("act") != "click":
        return None
    index = raw.get("i") if isinstance(raw.get("i"), int) and not isinstance(raw.get("i"), bool) else None
    label = str(raw.get("label") or raw.get("text") or "").strip()
    control = _viewed_control(view, index) if index is not None else (find_control(view, label) if label else None)
    return control if control is not None and _opens_its_list_instead(control, last_failed) else None


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
