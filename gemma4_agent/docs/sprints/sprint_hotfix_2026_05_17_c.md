# HOTFIX 2026-05-17 (C) — Path-amnesia post-creación de archivos

> Continuá el mismo chat de Claude Code (Sprints 0-8b + voice fixes
> 795f7a6/b38ec32 + hotfix A `c1531a1` + hotfix B `2410cce`).
> Bug compuesto reportado por el usuario en la sesión 15:30-15:32 del
> 2026-05-17.

---

## Contexto: lo que pasó

Del log `~/.gemma4/logs/_pre_session/chat.log` y
`gemma4_agent/data/traces.jsonl`:

```
[15:30:21] YOU: Hazme un PowerPoint de siete diapositivas que hable de los dinosaurios
[15:30:26] TOOL: office.create_presentation → ok
   tool_result.path = "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\gemma4_agent\data\generated\Los_Dinosaurios_20260517_153026.pptx"
[15:30:26] GEMMA: "Listo, creé el PowerPoint de siete diapositivas sobre dinosaurios en la ruta especificada."
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                  NO MENCIONA EL PATH AUNQUE LO TENÍA EN EL TOOL_RESULT

[15:31:40] YOU: dónde posites el PowerPoint
[15:31:41] GEMMA: "no tengo herramienta para eso"
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^
                  EL SUBSET TENÍA `office` Y EL LLM TIENE 65 TOOLS

[15:31:53] YOU: Dónde dejaste el Powerpoint? Que me hiciste
[15:31:55] GEMMA: "No alcancé a completar la acción. ¿La repetimos?"
```

## Causa raíz (CONFIRMADA, no especulación)

Dos bugs en cadena, ambos por inspección directa del código:

### Bug C1 — El LLM no cita el path al responder post-creación

[gemma4_agent/prompts/core.md](gemma4_agent/prompts/core.md) y
[gemma4_agent/prompts/tool_rules/office.md](gemma4_agent/prompts/tool_rules/office.md)
NO le dicen al LLM que cuando crea un archivo debe verbalizar el path
absoluto en su respuesta. La regla actual de `office.md` es defensiva
("no digas que no hay tool para PowerPoint") pero no proactiva.

El LLM entonces hace un resumen genérico: "en la ruta especificada".

### Bug C2 — El path se DROPEA del history en el próximo turn

[gemma4_agent/agent.py:1391-1394](gemma4_agent/agent.py#L1391) en
`_compact_completed_history`:

```python
for msg in self.history:
    role = str(msg.get("role") or "")
    if role == "tool":
        continue                  # ← DROPS tool_result messages
    if role == "assistant" and msg.get("tool_calls"):
        continue                  # ← DROPS assistant.tool_calls
    ...
```

Después de un turn que llamó una tool, lo único que sobrevive al
próximo turn es el `assistant.content` final. Como el Bug C1 hace
que ese content NO mencione el path, **el LLM literalmente no puede
ver dónde guardó el archivo en el turn siguiente**.

Cuando el usuario pregunta "¿dónde lo posiste?", el LLM:
- Ve `office` en el subset (correcto).
- No ve ningún path en el history.
- Interpreta la pregunta como "buscame un PowerPoint en mi PC" — eso
  no es lo que hace `office.create_presentation` (la action `inspect`
  o `open` requeriría un path como input).
- Concluye "no tengo herramienta para eso".

## Lo que NO es la causa raíz (descartado)

- **`compact_tool_result`** en `agent_compaction.py` SÍ preserva
  `path` en `core_keys` (línea 179). El path está bien en el momento
  del turn de creación. El problema NO es la compactación dentro
  del turn.
- **El router** está bien — el subset `office, verify, state,
  session` ya incluía `office`. El bug NO es de routing.
- **El schema de `office`** está bien — devuelve `path` como key
  top-level. El bug NO es del backend de la tool.

---

## OBJETIVO DEL HOTFIX

Tres commits chicos, tres archivos modificados:

1. `fix(prompt-office)`: actualizar `office.md` para EXIGIR citar el
   path absoluto cuando la tool retorna un path.
2. `fix(prompt-core)`: agregar al `core.md` una regla universal —
   cuando una tool retorna `path` o `url`, citala en el reply.
3. `fix(history)`: en `_compact_completed_history`, ANTES de dropear
   los tool messages, extraer un breadcrumb chico (`{tool, path, url,
   selected_title}`) y appendearlo al assistant.content del turn
   asociado, para que sobreviva el compact.

Los 3 fixes se complementan: 1+2 son defensa preventiva (el LLM cita
el path así no hace falta breadcrumb), 3 es defensa reactiva (si el
LLM falla en citarlo, el breadcrumb queda en history).

---

## REGLAS GENERALES

1. PortandoLoMejor. Commits chicos, prefijos `fix(prompt-office):`,
   `fix(prompt-core):`, `fix(history):`.
2. NO toques router_v2, planner, agent_runner, voice/*,
   tool_descriptions.yaml, modes.py, tool_schemas.py.
3. NO modifiques las 65 compound tools NI sus schemas.
4. NO `git add -A`.
5. Verificación post-commit:
   - `python -m pytest gemma4_agent/ -q` debe pasar (812+ passed,
     1 pre-existing failure).
   - `python -c "from gemma4_agent.agent_prompt import CORE_PROMPT; print(len(CORE_PROMPT))"` OK.
   - `python -m gemma4_agent.launcher status` corre.

---

## FIX C1 — Tool rule de office: exigir cita del path

### C1.1 — Editar `gemma4_agent/prompts/tool_rules/office.md`

Contenido actual (una sola línea, verificado a mano):

```
Office/document rule: if the user asks for a PowerPoint, Word document, Excel file, spreadsheet, or PDF export, use office(...). Do not say there is no tool for PowerPoint. If office returns needs_dependency, report the missing local dependency and the install hint.
```

Reemplazar por:

```
Office/document rule: if the user asks for a PowerPoint, Word document, Excel file, spreadsheet, or PDF export, use office(...). Do not say there is no tool for PowerPoint. If office returns needs_dependency, report the missing local dependency and the install hint.

PATH CITATION (mandatory when a file was created or modified): when office returns a `path` field, your reply MUST include that absolute path verbatim. Do NOT paraphrase as "en la ruta especificada" / "in the specified path" / "in the default folder" — say the actual path. Example:
  tool returned path="C:\Users\me\Documents\report.docx"
  reply: "Listo, creé report.docx en C:\Users\me\Documents\report.docx."
This is critical because in subsequent turns the tool_result is dropped from history; only your reply text survives. If you don't cite the path, the user (and your future self) will lose track of where the file is.

LOCATION FOLLOW-UP (where did you save it?): if the user asks "¿dónde guardaste X?" / "where did you save X?" and there is NO path visible in recent history, DO NOT say "no tengo herramienta" — instead say honestly: "No tengo el path en mi memoria reciente. Puedo buscarlo con filesystem o local_search si me dejás." This is a known limitation of how history is compacted across turns.
```

### C1.2 — Commit

`fix(prompt-office): mandate path citation in office tool replies`

Mensaje:

```
fix(prompt-office): mandate path citation in office tool replies

User report: created a PowerPoint about dinosaurs; Gemma replied
"Listo, creé el PowerPoint ... en la ruta especificada" without
including the actual path. One minute later: "dónde posites el
PowerPoint?" → "no tengo herramienta para eso".

The tool_result HAD the path verbatim (verified in traces.jsonl).
The LLM had it in context at reply time. But the existing
office.md rule didn't require citing it, and the next turn's
_compact_completed_history dropped the tool_result entirely.

Fix: extend office.md with a PATH CITATION mandate (cite the
absolute path verbatim when present) and a LOCATION FOLLOW-UP
fallback (when asked "where did you save X" with no path in
history, admit it honestly and offer filesystem/local_search).

Pure prompt change.
```

---

## FIX C2 — `core.md`: regla universal de citación de evidencia

### C2.1 — Editar `gemma4_agent/prompts/core.md`

Buscar en `core.md` un lugar natural para agregar (cerca de las reglas
de comportamiento de tools). Agregar un párrafo nuevo:

```
EVIDENCE CITATION: when a tool returns concrete locators in its
result (key `path`, `url`, `selected_title`, `image_path`, `deeplink`),
include them in your reply VERBATIM unless they are extremely long
(>200 chars). Do NOT paraphrase. Reasons:
- The user often needs to act on the locator (open the file, navigate
  to the URL).
- In subsequent turns the tool result is dropped from history; your
  reply text is the only persistent record.
- The post-tool verifier checks that your reply mentions the action
  result; vague replies like "en la ruta especificada" weaken the
  audit trail.

If the user explicitly says "no me digas la ruta" / "skip the URL",
honor that.
```

Pegalo después del bloque de reglas generales de tools, o al final
del archivo si no hay un lugar obvio. Buscar:

```bash
grep -n "tool\|result\|verifier" gemma4_agent/prompts/core.md | head
```

para encontrar el bloque relevante.

### C2.2 — Commit

`fix(prompt-core): mandate verbatim citation of tool-result locators (path, url, etc.)`

Mensaje:

```
fix(prompt-core): mandate verbatim citation of tool-result locators

Generalize the office.md path-citation rule to a universal
behavior across all tools: when a tool returns `path`, `url`,
`selected_title`, `image_path`, or `deeplink`, the reply MUST
include the locator verbatim.

Rationale documented inline in the rule: subsequent turns drop
the tool_result from history, so the reply text is the only
persistent record. Vague phrases like "en la ruta especificada"
break cross-turn continuity (verified bug 2026-05-17 with
office.create_presentation).

Pure prompt change.
```

---

## FIX C3 — Breadcrumb survival across turns

### C3.1 — Modificar `_compact_completed_history` en agent.py

En [gemma4_agent/agent.py:1374-1398](gemma4_agent/agent.py#L1374),
ANTES de iterar dropeando tool messages, hacer un pase preliminar
que extraiga locators de los tool_results y los appendee al
assistant.content del mismo turn.

Estrategia:
1. Recorrer `self.history` linealmente.
2. Cuando encuentres un mensaje `role="tool"`, parsea el content como
   JSON. Si tiene `path`, `url`, `selected_title`, `image_path`, o
   `deeplink` → guardalos en una lista temporal.
3. Cuando encuentres el siguiente `role="assistant"` SIN `tool_calls`
   (es decir, el reply final del turn), si su content NO menciona
   ninguno de los locators recopilados, anexale al final un sufijo
   discreto: `\n[breadcrumb: path=X url=Y]`.
4. DESPUÉS de esto, correr la lógica vieja de drop.

Implementación concreta (reemplazar el cuerpo de
`_compact_completed_history` por lo siguiente, manteniendo todo lo
que viene después de la línea 1398 intacto):

```python
def _compact_completed_history(self) -> None:
    """Keep future turns small after a completed tool cycle.

    PRE-PASS (Sprint hotfix C 2026-05-17): before dropping tool
    messages, harvest locator-keys from tool_results and stitch
    them as a discreet breadcrumb onto the assistant reply of the
    same turn. This preserves "where did the file get saved" across
    turns even if the LLM forgot to cite it explicitly. Bug repro:
    create a PowerPoint, next turn ask "where is it" — without
    breadcrumb the path was lost because tool messages get dropped
    below.

    Two-stage strategy inspired by OpenHands:
    1. Cheap pass: drop tool messages and tool_calls, shorten strings.
    2. If estimated context usage is still > 75% of context_size, ask
       Gemma 4 itself to summarize the oldest half of the conversation
       into a single 'summary so far' assistant message. The most recent
       turns are kept verbatim.

    Bypassed entirely with GEMMA4_AGENT_SUMMARIZATION=false. Stage 1 always
    runs as a safety net even when summarization is disabled.
    """
    # PRE-PASS: harvest tool-result locators and stitch onto the next
    # assistant reply if absent. Locator keys are picked from the same
    # set agent_compaction.compact_tool_result preserves in core_keys.
    _LOCATOR_KEYS = ("path", "url", "selected_title", "image_path", "deeplink")
    pending_locators: list[tuple[str, str]] = []  # [(key, value), ...]
    for msg in self.history:
        role = str(msg.get("role") or "")
        if role == "tool":
            # Tool content is JSON-serialized (str). Try to parse.
            raw = msg.get("content")
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = None
            elif isinstance(raw, dict):
                parsed = raw
            else:
                parsed = None
            if isinstance(parsed, dict):
                for k in _LOCATOR_KEYS:
                    v = parsed.get(k)
                    if isinstance(v, str) and v.strip() and len(v) <= 400:
                        pending_locators.append((k, v.strip()))
            continue
        if role == "assistant" and not msg.get("tool_calls") and pending_locators:
            # This is the final assistant reply of the tool cycle.
            existing_content = msg.get("content") or ""
            if isinstance(existing_content, list):
                # multimodal-shape content; coerce to plain text repr
                existing_text = "".join(
                    str(it.get("text", "")) for it in existing_content
                    if isinstance(it, dict)
                )
            else:
                existing_text = str(existing_content)
            # Only add locators that aren't already mentioned verbatim.
            missing = [
                (k, v) for k, v in pending_locators if v not in existing_text
            ]
            if missing:
                trail = " ".join(f"{k}={v}" for k, v in missing)
                breadcrumb = f"\n[breadcrumb: {trail}]"
                # Bound the addition so we don't push the assistant
                # message past sane limits. 600 chars of breadcrumb max.
                if len(breadcrumb) > 600:
                    breadcrumb = breadcrumb[:600] + "...]"
                msg["content"] = existing_text + breadcrumb
            pending_locators = []

    # ORIGINAL drop pass starts here ↓ ↓ ↓ (keep unchanged)
    budget = _compute_context_budget(self.config.context_size)
    compacted: list[dict[str, Any]] = []
    for msg in self.history:
        ...
```

(continuar con el código existente sin cambios)

**Notas importantes:**
- Asegurate de tener `import json` en agent.py si no está ya (probable
  que sí, pero verificá).
- El breadcrumb se appendea al `assistant.content` final del turn,
  NO al user message. Eso es deliberado: queremos que el LLM "se
  acuerde" de qué dijo.
- Si el assistant content ya menciona el path verbatim (porque
  C1+C2 funcionaron), `missing` queda vacío y NO se agrega
  breadcrumb. Idempotente.

### C3.2 — Test

Crear `gemma4_agent/test_history_breadcrumb.py`:

```python
"""Regression test for the breadcrumb pre-pass in
_compact_completed_history. Bug repro 2026-05-17: tool returned
path="C:\\...\\file.pptx", LLM replied "en la ruta especificada"
without the path, next turn asked "where is it?" and the LLM
had no access to the path because tool messages get dropped.
"""
from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock


class BreadcrumbStitchTest(unittest.TestCase):
    def _make_agent_with_history(self, hist: list[dict[str, Any]]) -> Any:
        # Build a minimal agent-like object with the right attrs to
        # exercise _compact_completed_history. We use a stripped-down
        # MagicMock pointing at the real method.
        from gemma4_agent.agent import AgentRunner
        # AgentRunner has a heavy __init__; bypass it by allocating
        # the instance and only setting the fields the method touches.
        agent = AgentRunner.__new__(AgentRunner)
        agent.history = list(hist)
        agent.config = MagicMock()
        agent.config.context_size = 32768
        agent.trace = MagicMock()
        agent._turn_counter = 1
        agent._summarize_last_run_turn = 0
        return agent

    def test_path_stitched_onto_assistant_reply_when_missing(self) -> None:
        path = r"C:\Users\me\Desktop\report.pptx"
        hist = [
            {"role": "user", "content": "Hazme un powerpoint"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "office", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1",
             "content": json.dumps({"ok": True, "path": path, "kind": "presentation"})},
            {"role": "assistant", "content": "Listo, creé el PowerPoint en la ruta especificada."},
        ]
        agent = self._make_agent_with_history(hist)
        agent._compact_completed_history()
        # The final assistant content should now contain the path or a
        # breadcrumb mentioning it (depending on whether drop ran).
        final_content_str = ""
        for m in agent.history:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                c = m.get("content")
                final_content_str += str(c) if not isinstance(c, list) else " ".join(
                    str(it.get("text", "")) for it in c if isinstance(it, dict)
                )
        self.assertIn(path, final_content_str,
                      f"path should have been stitched: {final_content_str!r}")

    def test_path_NOT_duplicated_when_already_cited(self) -> None:
        path = r"C:\Users\me\Desktop\report.pptx"
        hist = [
            {"role": "user", "content": "Hazme un powerpoint"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "office", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1",
             "content": json.dumps({"ok": True, "path": path})},
            {"role": "assistant", "content": f"Listo, lo guardé en {path}."},
        ]
        agent = self._make_agent_with_history(hist)
        agent._compact_completed_history()
        final_content_str = ""
        for m in agent.history:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                c = m.get("content")
                final_content_str += str(c) if not isinstance(c, list) else ""
        # The path should appear exactly once (not duplicated by breadcrumb).
        self.assertEqual(final_content_str.count(path), 1,
                         f"path duplicated: {final_content_str!r}")
        self.assertNotIn("[breadcrumb:", final_content_str)

    def test_url_locator_stitched(self) -> None:
        url = "https://www.youtube.com/watch?v=abc123"
        hist = [
            {"role": "user", "content": "pon un video"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "media", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1",
             "content": json.dumps({"ok": True, "url": url})},
            {"role": "assistant", "content": "Listo, video abierto."},
        ]
        agent = self._make_agent_with_history(hist)
        agent._compact_completed_history()
        final_content_str = ""
        for m in agent.history:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                final_content_str += str(m.get("content") or "")
        self.assertIn(url, final_content_str)

    def test_no_op_when_no_tool_messages(self) -> None:
        hist = [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "hola, ¿en qué te ayudo?"},
        ]
        agent = self._make_agent_with_history(hist)
        agent._compact_completed_history()
        final_content = next(
            m for m in agent.history
            if m.get("role") == "assistant"
        )["content"]
        self.assertNotIn("[breadcrumb:", str(final_content))


if __name__ == "__main__":
    unittest.main()
```

**Si el test es complicado de cablear** porque `AgentRunner.__new__`
sin `__init__` falla por atributos faltantes, alternativas:

a) Extraer la lógica del pre-pass a una función pura
   `_stitch_breadcrumbs(history: list[dict]) -> list[dict]` en
   `agent.py` (puramente funcional, no toca self), llamarla desde
   `_compact_completed_history`, y testear la función pura directo.
   Esa es la opción más limpia. Hacé esto si el `__new__` trick es
   frágil.

b) Si nada funciona, marcá los tests `@unittest.skip("requires
   AgentRunner full init")` y dejá un TODO. NO inviertas más de
   45 min en wiring de tests.

### C3.3 — Commit

`fix(history): stitch tool-result locators as breadcrumb onto assistant reply pre-drop`

Mensaje:

```
fix(history): stitch tool-result locators as breadcrumb before drop

Root cause for the "where did you save the powerpoint" amnesia:
_compact_completed_history dropped role=tool messages entirely,
so the path key was gone in the next turn. The LLM's reply
("en la ruta especificada") was the only thing left, and it
didn't include the actual path.

Fix: in _compact_completed_history, before the drop loop, harvest
locator keys (path, url, selected_title, image_path, deeplink)
from tool_result messages and stitch them as a [breadcrumb: ...]
suffix onto the assistant reply of the SAME turn. Idempotent: if
the reply already mentions the locator verbatim, nothing is added.

Defense-in-depth alongside fix(prompt-office) which makes the LLM
cite the path proactively. With both in place, the path survives
even if the LLM forgets to cite it.

Test: test_history_breadcrumb.py covers stitch, no-duplicate, url
locator, and no-op-without-tools cases.
```

---

## REPORTE FINAL

Devolveme:

1. Hash de los 3 commits.
2. Output de `python -m pytest gemma4_agent/test_history_breadcrumb.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
4. Una verificación manual: corré este snippet y devolveme el output:

```python
import json
from gemma4_agent.agent_prompt import CORE_PROMPT, build_system_prompt

print("CORE_PROMPT contains EVIDENCE CITATION:", "EVIDENCE CITATION" in CORE_PROMPT)
sp = build_system_prompt(["office"])
print("\nfull system prompt for office subset:")
print(sp[:3000])
```

## CRITERIO DE ÉXITO

- 3 commits aterrizados.
- Tests nuevos del breadcrumb verdes (mínimo 2 de los 4; los más
  importantes son `stitched_onto_assistant_reply_when_missing` y
  `NOT_duplicated_when_already_cited`).
- Suite completa verde (modulo Sprint 3a pre-existing failure).
- Working tree limpio.
- `python -m gemma4_agent.launcher status` OK.
- El system prompt resultante contiene tanto la regla de
  `EVIDENCE CITATION` como `PATH CITATION (mandatory ...)`.

## NO HACER (anti-scope)

- NO toques router, planner, voice/*, agent_runner, modes.py.
- NO modifiques las 65 compound tools.
- NO toques `compact_tool_result` ni los locator-keys del módulo
  agent_compaction — funcionan bien.
- NO migrés `_LOCATOR_KEYS` a config — está en una sola función,
  hardcoded es OK.
- NO agregués UN BREADCRUMB MASIVO con todo el tool_result — solo
  los locators (5 keys). El budget de prompt no aguanta más.
- NO inviertas tiempo en testear cross-turn behavior con LLM real
  — eso lo prueba el usuario.
