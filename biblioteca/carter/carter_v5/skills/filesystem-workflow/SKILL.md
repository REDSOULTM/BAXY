---
name: filesystem-workflow
description: Multi-step filesystem flows — create+write+open, search+read+report, backup+edit+test. Use when user chains filesystem actions ("crea X y abrilo", "buscá archivo Y", "hacé backup y editá", "si existe ábrelo, si no creálo").
priority: high
---

# Filesystem workflow (multi-step)

**Tools used**: `filesystem`, `app`, `gui`.
**Honesty-critical**: yes — read-only when user says "no toques código"; always backup first if user said "con backup".

The user is asking for a chain involving filesystem operations. Three common
patterns; pick the matching one:

## Pattern A — "crea carpeta/archivo, escribí <texto> y abrilo"

1. `filesystem(action="create_dir", path="<dir>")` if a new folder is needed.
2. `filesystem(action="write", path="<file>", content="<text>")` — verifier checks file exists.
3. Open: prefer `filesystem(action="open", path="<file>")` for default-app open. If the user explicitly said "Notepad", use `app(action="open", name="notepad")` then `gui(action="type", value="<text>")`.

## Pattern B — "buscá <archivo>; si existe ábrelo, si no creálo en sandbox"

1. `filesystem(action="search", query="<filename>")` or `filesystem(action="list", path="<dir>")`.
2. If results contain the file → `filesystem(action="open", path="<found path>")` (or `filesystem(action="read")` if user wants content).
3. If no results → `filesystem(action="create_dir", path="<sandbox>")` + `filesystem(action="write", path="<sandbox>/<file>", content="")`.

## Pattern C — "hacé backup, editá <file> y corré test"

1. `filesystem(action="copy", src="<file>", dst="<file>.bak")` — explicit backup first.
2. `filesystem(action="write", path="<file>", content="<new>")`.
3. `terminal_run(command="<test command>")`. Report output.

## Honesty rules (NEVER violate)

- If user said "con backup" → ALWAYS do the copy step first. Skipping it = lying.
- If user said "no toques código" → READ-ONLY mode. Use `filesystem(read/list/search)` only. NEVER `write`/`delete`/`move`.
- If `filesystem(write)` returns `ok=False` → report the actual error (permission denied, path not found, etc.). Don't claim success.
- If search returns 0 results → don't assume "doesn't exist". Could be path/extension/case issue — report what you searched for and the empty result.

## Loop prevention

- Max 8 tool calls per workflow.
- If 2 consecutive `filesystem` operations return errors → STOP and report.

## Examples

User: "crea carpeta tmp, archivo notas.txt, escribí 'hola' y abrilo"
→ Pattern A: create_dir(tmp) → write(tmp/notas.txt, "hola") → open(tmp/notas.txt).

User: "buscá ContextoCarter.md; si existe abrilo"
→ Pattern B: search("ContextoCarter.md") → if found, open the first match → if not, report "no encontrado".

User: "revisá RESIDUAL.md y clasificame los bugs, no toques código"
→ Pattern B read-only: search/read("RESIDUAL.md") → analyze content in reply → NO writes.

User: "hacé backup de config.yaml, editalo poniendo debug=true y corré pytest"
→ Pattern C: copy(config.yaml → config.yaml.bak) → write(config.yaml, new content) → terminal_run("pytest").
