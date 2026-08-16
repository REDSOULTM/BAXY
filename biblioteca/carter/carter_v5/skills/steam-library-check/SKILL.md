---
name: steam-library-check
description: Check if a game is in the user's Steam library — read-only, no launch. Use when user asks "tengo X", "está instalado X", "X está en mi biblioteca". PREFER `steam_game(action="lookup", name=X)` — ONE call, no GUI.
priority: high
---

# Check Steam library — ONE TOOL CALL

## The single-call path (preferred)

```
steam_game(action="lookup", name="<game name>")
```

The tool reads local appmanifest_*.acf files (faster + offline). Returns:
- `appid`: Steam app id
- `owned: bool`: true if the game is in the user's library
- `installed: bool`: true if actually downloaded
- `source: "local_manifest" | "store_search"`: where the info came from

**Read these fields and reply honestly:**

| owned | installed | reply pattern |
|---|---|---|
| true | true | "Sí, <name> está instalado." |
| true | false | "Lo tenés comprado pero no está instalado." |
| false | false (source=store_search) | "No lo tenés en tu biblioteca. ¿Querés que lo busque en la tienda?" |

NEVER launch the game from this check — the user explicitly didn't ask for that. The `lookup` action only reads, never dispatches a URI.

## Examples

User: "tengo cyberpunk 2077?"
→ `steam_game(action="lookup", name="Cyberpunk 2077")` → read result → reply.

User: "decime si Hogwarts Legacy está instalado"
→ Same. ONE call.

User: "qué juegos tengo en Steam"
→ `steam_game(action="list_owned")` returns the full list. Format it as bullets in the reply.

## Honesty rules

- NEVER say "está instalado" without checking `installed=true` in the result.
- NEVER launch the game from this check (the tool's `lookup` action never dispatches a launch URI — that's by design).
- If the lookup fails (e.g. Steam not installed) → report honestly: "no pude leer tu biblioteca de Steam".
