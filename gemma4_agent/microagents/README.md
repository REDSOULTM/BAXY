# Carter Agent microagents

Markdown files con frontmatter YAML que se inyectan condicionalmente al
system_prompt cuando alguno de sus `triggers` aparece (case+accent insensitive)
en el primer mensaje del usuario del turn.

Diferencia con `TOOL_RULES` (en `agent.py`):
- `TOOL_RULES["smart_home"]` → cómo USAR la tool smart_home cuando está
  en el subset del router. Es una regla de uso de tool.
- microagent `glossary.md` → qué SIGNIFICA "HKCR", "mmproj", "deeplink".
  Es conocimiento de dominio del proyecto.

Ambos coexisten sin colisión.

## Formato

```markdown
---
name: my-context
triggers: ["palabra clave", "otra", "regex no"]
priority: medium
---

# Title del bloque
- algun bullet
- otra cosa
```

Reglas:
- `name`: lowercase, sin espacios. Usado como `## <name>` en el prompt.
- `triggers`: lista de strings (substring match, no regex). Case+accent
  insensitive (`"qué"` ≡ `"que"` ≡ `"QUE"`).
- `priority`: `high` | `medium` (default) | `low`. Sort para `max_microagents=3`.
- Body: hasta ~2000 chars sano. Más grande genera warning en log.

## Comandos CLI

```powershell
# Listar todos los microagents cargados
python -m gemma4_agent.memory_pkg.microagents list

# Probar match con un texto
python -m gemma4_agent.memory_pkg.microagents test "qué significa HKCR"
```

## Opt-out

`GEMMA4_MICROAGENTS_OFF=1` desactiva el sistema entero.

## Microagents incluidos

| File | Triggers (resumen) | Cuándo se carga |
|---|---|---|
| `glossary.md` | "qué es", "qué significa", "HKCR", "mmproj", ... | preguntas definicionales |
| `windows_commands.md` | "comando", "terminal", "powershell", "cmd" | dudas sobre comandos |
| `troubleshoot.md` | "no funciona", "se rompió", "error" | diagnóstico de fallas |
| `tools_cheat_sheet.md` | "qué puedes hacer", "lista de herramientas" | usuario nuevo / inventario |
