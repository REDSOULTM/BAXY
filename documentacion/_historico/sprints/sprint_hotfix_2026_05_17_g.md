# HOTFIX 2026-05-17 (G) — Tool rules coverage + prompt drift audit

> Continuá el chat post hotfixes E + F. Foco: 39 de 65 tools no
> tienen tool_rule en `prompts/tool_rules/`. Esta es la deuda de
> prompts más grande del proyecto. Plus tests que pinen que las
> rules referencian actions reales.

---

## Contexto

Auditoría 2026-05-17:
```bash
$ ls gemma4_agent/prompts/tool_rules/ | wc -l
26
$ python -c "from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS; print(len(COMPOUND_TOOL_SCHEMAS))"
65
```

39 tools sin rule:
```
accessibility, audio, backup_sync, clipboard, container,
creative_local, data_analysis, database, dependency,
desktop_layout, device_settings, download, env, filesystem, gui,
habit_tracker, input, job_manager, local_calendar, local_search,
media_edit, memory, notes_tasks, package, peripheral,
photo_library, printer_scanner, registry, safety, session,
skill_load, source_manager, state, system, terminal, uia, verify,
vision, window
```

Cuando el LLM se confunde con una de estas tools, no hay rule que
guíe — depende del schema description (técnico) o adivina.

Adicionalmente: **no hay test** que valide que las actions
nombradas en las .md existan en `tool_schemas.py`. Drift natural
hacia rules promesando acciones que no existen (Bug D4 fue
exactamente eso: `session(action="search")` — acción inventada).

---

## Principio rector — language-agnostic

`gemma4_agent` sirve usuarios que hablan **de cualquier forma**:
voseo argentino, neutro, EN/PT/FR/IT/DE y mezclas. Las tool_rules
**NO deben matchear keywords del idioma del usuario**. En su lugar:

- Describen **qué hace la tool** en una frase técnica.
- Aclaran cuándo **no usar la tool** (la confusión típica contra
  una tool vecina).
- Si la tool tiene patrones de invocación útiles
  (e.g. `office.path-citation` del hotfix C), los describen en
  términos del **comportamiento estructural** del result, no del
  texto del user.
- Los ejemplos de invocación se escriben con verbos abstractos
  ("when the user wants to create a presentation") o con `<X>`
  placeholders, **nunca** con listas de keywords ES/EN.

El propio prompt es leído por el LLM en inglés — el LLM ya
maneja la traducción del input del user a intent. Las rules
guían el mapping `intent → tool`, no `keyword → tool`.

---

## OBJETIVO

Dos commits chicos:

1. `docs(tool-rules)`: agregar tool_rule mínima (1-3 párrafos)
   para las 39 tools sin rule. Cada rule responde:
   - ¿Qué hace esta tool, en una frase?
   - ¿Cuándo NO usarla? (la confusión típica vs tool vecina).
   - ¿Hay precondiciones estructurales? (e.g. tool requiere
     `path` absoluto, devuelve `needs_user` si falta).
2. `test(tool-rules-drift)`: test que valida cada rule.md cite
   actions reales del schema correspondiente.

---

## REGLAS GENERALES

1. PortandoLoMejor.
2. NO modifiques tools.py, tool_schemas.py, modes.py, planner.py,
   router_v2.py.
3. NO toques las 26 rules existentes (salvo que el drift test del
   G2 las marque como buggy).
4. Cada rule.md ≤ 800 chars (el prompt budget es ajustado).
5. **Cada rule debe ser language-agnostic** — sin listas de
   keywords ES/EN/PT/FR/IT/DE.
6. NO instales libs nuevas.
7. NO `git add -A`.

---

## FIX G1 — Add 39 missing tool_rules

### G1.1 — Estudiar el patrón

Leé 3-4 rules existentes para entender el estilo:
- `gemma4_agent/prompts/tool_rules/office.md`
- `gemma4_agent/prompts/tool_rules/browser.md`
- `gemma4_agent/prompts/tool_rules/whatsapp.md`
- `gemma4_agent/prompts/tool_rules/web.md`

Patrón observado:
1. Primera frase: "X rule: <qué hace>".
2. Aclaración de cuándo NO usar / vs qué tool similar.
3. Constraint estructural o ejemplo con `<X>` placeholder.

NO uses listas de keywords del estilo "cuando el user dice
'instala' o 'install' o 'installer'". Eso es lo que router_v2 hace
bien por su lado (e5-small multilingual + Tool2Vec). Las rules
existen para guiar la **selección entre tools confundibles**, no
para suplir el routing.

### G1.2 — Extraer actions reales

```bash
python -c "
from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS
for s in COMPOUND_TOOL_SCHEMAS:
    n = s['function']['name']
    d = s['function']['description'][:250]
    print(f'### {n}')
    print(d)
    print()
"
```

### G1.3 — Templates language-agnostic

Te paso 6 ejemplos. El resto sigue el mismo patrón LEYENDO el
schema description.

**`gemma4_agent/prompts/tool_rules/system.md`**:
```
System rule: system(...) is the Windows control surface for
read-only system state and power actions. Actions: time,
processes, cpu_ram_gpu, disk, battery, brightness_get,
brightness_set, shutdown, restart, sleep.

ANSWER-FROM-TOOL: questions whose answers come from the live OS
(current time, disk usage, battery, CPU/RAM/GPU info) MUST go
through system with the matching action — never answer from
memory (see ANTI-HALLUCINATION in core.md).

DESTRUCTIVE: shutdown, restart, sleep change global PC state.
With safety_enabled the agent layer requires confirmation; without
it, the call goes through immediately. Do not call these unless
the user clearly requested the action.
```

**`gemma4_agent/prompts/tool_rules/filesystem.md`**:
```
Filesystem rule: filesystem(...) for create/move/copy/delete/list
of local files. Distinct from download(...) (web fetches) and
backup_sync(...) (cloud sync, version history).

DESTRUCTIVE: delete actions remove files. With safety disabled the
removal is immediate. Prefer rollback-aware patterns when
available (state checkpoint, recycle bin).

PATH HANDLING: friendly references like "desktop", "downloads",
"documents" resolve to %USERPROFILE%/Desktop etc. Always echo the
resolved absolute path in your reply so subsequent turns retain
it (see EVIDENCE CITATION).
```

**`gemma4_agent/prompts/tool_rules/clipboard.md`**:
```
Clipboard rule: clipboard(...) for read/write/inspect the Windows
clipboard. Supports text, images, files. Read history with
action='history'; wipe with action='clear'.

NOT FOR: long text persistence (use notes_tasks) or screenshots
to disk (use gui screenshot). Clipboard is volatile — contents
clear on logoff.
```

**`gemma4_agent/prompts/tool_rules/terminal.md`**:
```
Terminal rule: terminal(...) spawns PowerShell / cmd / WSL bash
sessions to run arbitrary shell commands. Lower-level than
developer(...) (which is git/build-aware).

NEVER bypass purchase-guard or safety via terminal (e.g. don't
shell-out an installer that requires payment). If the user
requests a destructive command (rm -rf, format, reg delete),
confirm even without safety_enabled.

Prefer developer(action='git_*') for git workflows over
terminal — developer is aware of the project root and stack.
```

**`gemma4_agent/prompts/tool_rules/package.md`**:
```
Package rule: package(...) installs/uninstalls/updates desktop
applications via winget / scoop / chocolatey. Distinct from
dependency(...) (Python libraries, system binaries needed by the
agent itself).

CONFIRM BEFORE INSTALL: if the user requests an install of a tool
that has a paid version (e.g. PyCharm Professional vs Community),
confirm which edition. If the tool is paid only, surface the
purchase-guard before proceeding.
```

**`gemma4_agent/prompts/tool_rules/session.md`**:
```
Session rule: session(action='cancel_turn') is the ONLY available
action. Use it when the user is interrupting / aborting the agent
mid-turn (any phrasing in any language signaling "stop, wait, hold
on, cancel"). Not a domain tool — does not perform filesystem /
network / etc. work.

DO NOT invent other actions (e.g. session(action='search') was a
real hallucination from a bug report — that intent belongs to
web(...)).
```

### G1.4 — Lista de los 39 a crear

```
accessibility, audio, backup_sync, clipboard ✓ (template),
container, creative_local, data_analysis, database, dependency,
desktop_layout, device_settings, download, env, filesystem ✓,
gui, habit_tracker, input, job_manager, local_calendar,
local_search, media_edit, memory, notes_tasks, package ✓,
peripheral, photo_library, printer_scanner, registry, safety,
session ✓, skill_load, source_manager, state, system ✓,
terminal ✓, uia, verify, vision, window
```

Para las meta-tools (`safety`, `verify`, `state`, `skill_load`,
`subagent`, `session`): rules muy cortas que enfatizan que NO son
tools de domain action.

### G1.5 — Verificación pre-commit

```bash
$ ls gemma4_agent/prompts/tool_rules/ | wc -l   # debe ser 65
65
$ python -c "
from gemma4_agent.agent_prompt import build_system_prompt
sp = build_system_prompt(['filesystem', 'terminal', 'system'])
for needle in ['Filesystem rule:', 'Terminal rule:', 'System rule:']:
    assert needle in sp, needle
print('ok')
"
```

### G1.6 — Commit

`docs(tool-rules): add minimal language-agnostic rule for the 39 tools without one`

Mensaje:

```
docs(tool-rules): add minimal language-agnostic rule for the 39 tools

Audit 2026-05-17: only 26/65 compound tools had a
prompts/tool_rules/ file. The other 39 had no guidance beyond the
schema description (technical). When the LLM got confused (e.g.
calling session(action='search') in Bug D4), there was nothing to
steer it.

Fix: 39 new minimal rules (~3-6 lines each, total under 30KB
combined). Each rule answers:
1. What the tool does in one sentence.
2. When NOT to use it / distinct from which neighbor tool.
3. Destructive-action callout when relevant.

Language-agnostic by construction: no keyword lists in any
language. The rules describe tool semantics and inter-tool
boundaries; router_v2 (the e5-small multilingual retriever) is
responsible for mapping user phrasing → tool name, regardless of
dialect or language.

Actions cited in each rule come from the tool's actual schema
description — no invented actions.

Pure documentation. No code change.
```

---

## FIX G2 — Test: tool-rule action drift

### G2.1 — Crear test

`gemma4_agent/test_tool_rule_action_drift.py`:

```python
"""Validate every prompts/tool_rules/*.md references actions that
actually exist in tool_schemas.py.

Hotfix G 2026-05-17. Without this test, prompt rules can drift
into promising actions that don't exist — e.g. the Bug D4
'session(action="search")' hallucination. If a rule said it, the
drift would have stuck.

The check: for each rule.md, parse `tool(action='X')` /
`tool(action="X")` patterns, look up the tool's real action list
(extracted from its schema description), and assert each
referenced action exists.

Schemas that don't enumerate actions in the description (rare;
mostly meta-tools) are skipped without failing.
"""
from __future__ import annotations

import os
import re
import unittest

from gemma4_agent.tools import COMPOUND_TOOL_SCHEMAS


_RULES_DIR = os.path.join(os.path.dirname(__file__), "prompts", "tool_rules")


def _actions_for_tool(tool_name: str) -> set[str] | None:
    """Extract the action list from a schema's description.

    Most schemas have "Actions: a, b, c, d." near the start. If
    the schema has no such enumeration, return None and the test
    skips action checks for that tool.
    """
    for s in COMPOUND_TOOL_SCHEMAS:
        if s.get("function", {}).get("name") != tool_name:
            continue
        desc = s.get("function", {}).get("description") or ""
        m = re.search(r"Actions?:\s*([a-z_,\s]+)", desc[:600], re.IGNORECASE)
        if not m:
            return None
        raw = m.group(1).split(".")[0]
        return {a.strip() for a in raw.split(",") if a.strip()}
    return None


_ACTION_REF = re.compile(
    r"\b([a-z_]+)\(\s*action\s*=\s*['\"]([a-z_]+)['\"]"
)

# Negative-mention exclusion. Pre-flight check 2026-05-17 detected
# browser.md says: `NOT browser(action="minimize")`. That's an
# intentional negative example — the rule warns the LLM NOT to use
# that action. The drift test should ignore matches whose
# left-context is `NOT `, `not `, `don't ` (any case) or similar
# negative-mention markers, otherwise the test flags valid
# pedagogical content as drift.
_NEGATIVE_PREFIX = re.compile(
    r"(?:NOT\s+|not\s+|don'?t\s+(?:use\s+)?|never\s+|avoid\s+)$",
    re.IGNORECASE,
)


def _is_negative_mention(text: str, match_start: int) -> bool:
    """True if the `tool(action='X')` match is preceded by a
    negative-mention marker like 'NOT ', "don't ", 'never ',
    'avoid '. The window is the 20 chars immediately preceding
    the match.
    """
    left = text[max(0, match_start - 20):match_start]
    return bool(_NEGATIVE_PREFIX.search(left))


class ToolRuleActionDriftTest(unittest.TestCase):
    def test_every_rule_references_real_actions(self) -> None:
        if not os.path.isdir(_RULES_DIR):
            self.skipTest(f"no rules dir at {_RULES_DIR}")
        problems: list[str] = []
        for fname in os.listdir(_RULES_DIR):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(_RULES_DIR, fname)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            for m in _ACTION_REF.finditer(body):
                ref_tool, ref_action = m.group(1), m.group(2)
                if _is_negative_mention(body, m.start()):
                    # Intentional negative example (e.g. 'NOT
                    # browser(action="minimize")'). Skip.
                    continue
                schema_actions = _actions_for_tool(ref_tool)
                if schema_actions is None:
                    continue
                if ref_action not in schema_actions:
                    problems.append(
                        f"{fname}: references {ref_tool}(action='{ref_action}') "
                        f"but {ref_tool} schema only lists "
                        f"{sorted(schema_actions)}"
                    )
        if problems:
            self.fail("Tool rule action drift detected:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    unittest.main()
```

### G2.2 — Correr el test

```bash
python -m pytest gemma4_agent/test_tool_rule_action_drift.py -v
```

**Si falla** (probable que detecte drift real), arreglá las rules
identificadas — son bugs reales. Documentá los arreglos en el
commit body. Posibles falsos positivos:
- Esquemas que listan actions con prefijos compuestos
  (`event_create`, `event_list` en local_calendar). Si el regex
  no los captura, ajustá el normalizador.
- Si el test falla en >5 rules pre-existentes (pre-G1), arreglalo
  en este mismo commit — esa es la deuda escondida que justifica
  el test.

### G2.3 — Commit

`test(tool-rules): assert every rule.md references real schema actions`

Mensaje:

```
test(tool-rules): assert every rule.md references real schema actions

Without this test, tool_rule files can drift into promising
actions that don't exist (e.g. the Bug D4
session(action='search') hallucination — the LLM made that up
because nothing constrained it, and if a rule had said it the
drift would have stuck).

Fix: parse every prompts/tool_rules/*.md for tool(action='X')
patterns and look them up against the schema's action list
(extracted from the description's "Actions: a, b, c"
enumeration). Each rule's referenced actions must be a subset of
the schema's real actions.

Schemas that don't enumerate actions (rare; mostly meta-tools)
are skipped without failing.

If this commit also fixes existing drift in pre-existing rules,
list the fixes in the body.
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 2 commits.
2. `ls gemma4_agent/prompts/tool_rules/ | wc -l` debe ser 65.
3. Output de `python -m pytest gemma4_agent/test_tool_rule_action_drift.py -v`.
4. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
5. Verificar que las rules nuevas NO contienen listas de keywords:
   ```bash
   grep -lE "\b(when the user|the user says|si el user)\s+(says|dice|writes|escribe)" gemma4_agent/prompts/tool_rules/ || echo "no keyword lists detected — good"
   ```

## CRITERIO DE ÉXITO

- 65 archivos en tool_rules.
- Drift test verde.
- Suite completa verde (modulo Sprint 3a pre-existing failure).
- Cada rule ≤ 800 chars (`find prompts/tool_rules -name '*.md'
  -size +800c` debe devolver solo rules pre-existentes ya grandes
  como office.md / routine.md).
- Ninguna rule nueva contiene listas tipo "user dice X|Y|Z".

## NO HACER (anti-scope)

- NO reescribas las 26 rules pre-existentes (salvo que el drift
  test las marque como buggy).
- NO inventés actions para tools cuyo schema description no
  enumera Actions: — déjalas con rule mínima sin citar action
  específica.
- NO modifiques el schema description en tool_schemas.py.
- NO migres rules a un formato YAML / structured. El .md es lo
  que el LLM consume bien.
- NO copies blocks de core.md a las rules (DRY: si una regla
  global cubre el tema, la rule no la repite).
- NO incluyas listas de keywords como guidance del tipo
  "trigger this tool when user says X". Esa función la cumple
  router_v2 (e5-small multilingual). Las rules solo cubren
  "qué hace + cuándo no usar + constraints estructurales".
