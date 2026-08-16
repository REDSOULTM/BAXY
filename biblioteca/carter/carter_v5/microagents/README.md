# Carter v5 microagents

> Pattern from **OpenHands** (`.openhands/microagents/`). Markdown files that
> are conditionally injected into the system prompt when a trigger matches the
> user's text or active context.

## Microagents vs Skills — separación de responsabilidades

Carter v5 tiene DOS sistemas de inyección de contexto. Para evitar overlap:

| | **Microagents** (aquí) | **Skills** (`carter_v5/skills/`) |
|---|---|---|
| Naturaleza | **Referencia pasiva** (glossary, cheat sheets) | **Recipes accionables** (chains de tools) |
| Cuándo se inyecta | Auto, first-turn match, eager body completo | El LLM la pide via `skill_load(name)` (lazy) |
| Costo en tokens | Eager si trigger matchea | Solo nombre+descripcion (50 tokens) hasta que el LLM la cargue |
| Ejemplo válido | `glossary.md` ("qué es deeplink") | `install_game/SKILL.md` (chain Steam) |
| Ejemplo INválido | "install_game.md" (es chain, no referencia) → migrar a skill | "definiciones HKCR" → debería ser microagent |

**Regla de oro**: si el contenido le dice al LLM "QUÉ es algo" → microagent. Si le
dice "CÓMO hacer un chain de tools" → skill. Esto evita duplicación y mantiene
el system_prompt acotado.

## How it works

1. Each `*.md` file has YAML frontmatter declaring `triggers` (regex / keywords).
2. `core/router.py` checks user_text against each microagent's triggers.
3. Matched microagents' content is appended to system_msg as "# CONTEXT: <name>".
4. Carter's LLM sees the relevant microagent ONLY when needed — saves tokens.

## File format

```markdown
---
name: glossary
triggers: ["jerga", "qué significa", "glossary", "vocabulario"]
priority: low
---

# Glossary

- **deeplink**: URI scheme like `steam://`, `spotify:`, etc.
- **HKCR**: Windows registry `HKEY_CLASSES_ROOT`.
- **mmproj**: multimodal projector file for vision/audio in llama.cpp.
- **OUTCOME**: COMPLETED | PARTIAL | FAILED | UNVERIFIED | NEEDS_USER | ...
```

## Built-in microagents

| File | Triggers | Purpose |
|---|---|---|
| `glossary.md` | "que significa", "qué es", "vocabulario" | Domain jargon definitions |
| `tools_cheat_sheet.md` | "qué puedes", "lista", "todas tus" | Tool capability summary |
| `windows_commands.md` | "comando", "terminal", "shell" | Common Windows command equivalents |
| `troubleshoot.md` | "no funciona", "error", "se rompió" | Diagnostic flow for common failures |

## Adding your own

Drop a `*.md` with YAML frontmatter into this directory. The loader picks it up at agent boot. No code changes needed.

## References

- OpenHands microagents: `.openhands/microagents/glossary.md`
