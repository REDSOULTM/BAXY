---
name: install-game
description: Install or launch a game. For Steam → use `steam_game(action=play_or_install, name=<game>)` — single deterministic call, no GUI clicks. Other launchers (Epic/Ubi/EA) → UIA snapshot+act chain.
priority: high
---

# Install / launch a game — Steam-first, GUI as fallback

## Steam (preferred path — ONE TOOL CALL)

If the user mentions Steam OR if you suspect it's a Steam game (most games are):

```
steam_game(action="play_or_install", name="<game name>")
```

That's it. ONE call. The tool:
- Resolves the appid locally if the game is in the user's library (~50ms)
- Otherwise queries Steam's public store API (~200ms, no key)
- Dispatches `steam://rungameid/<appid>` which:
  - Launches if installed
  - Downloads + launches if owned but not installed
  - Opens store page if not owned (Steam handles the redirect)

**Examples**:
- User: "instala doom eternal" → `steam_game(action="play_or_install", name="Doom Eternal")`
- User: "jugá portal 2" → `steam_game(action="play_or_install", name="Portal 2")`
- User: "lanzá Hades" → `steam_game(action="play_or_install", name="Hades")`

The tool returns `source: "local_manifest" | "owned_localconfig" | "store_search"` AND `expected_behavior`. Use BOTH to write an honest reply. `owned` is TRUE for installed games AND owned-but-not-installed (read from `userdata/<id>/config/localconfig.vdf`).
- `expected_behavior="launching installed game"` → "Listo, lancé <game>."
- `expected_behavior="downloading + launching (owned)"` (owned=True, installed=False) → "Lo tenés comprado pero no instalado. Steam ya está descargándolo y lo va a lanzar cuando termine."
- `expected_behavior="opening store page (not owned — Steam will show buy UI)"` (owned=False) → "<game> no lo tenés comprado, te abrí la página de Steam para que decidas. ¿Querés que lo comprés?"
NUNCA digas "no está en tu biblioteca" si `owned: true`. Verificá el campo SIEMPRE antes de afirmar ownership.

## Honesty rules

- NEVER claim "Listo, lancé X" without checking `expected_behavior` in the tool result.
- If `ok: false` → report the actual error from the tool, never fake success.
- For "comprá <game>" (purchase intent), use `action="lookup"` first to get price + appid, report price + ask "¿confirmás la compra?", DO NOT auto-launch. Real money rule.

## Other launchers (Epic / Ubisoft / EA / GOG)

There's no equivalent tool for those yet. Fallback chain:

1. `app(action="open", name="<launcher_exe>")` — open the launcher app.
2. `gui(action="snapshot", wait_for="<App Title>", wait_seconds=15)` — read the UIA tree.
3. Find the game in the tree text, click via `gui(action="act", ref="<ref>", kind="click")`.
4. Snapshot again, find Install/Play button, click.

This GUI path is brittle (depends on each launcher's UIA tree). For now, if the user names a non-Steam launcher, try this chain but report honestly when the snapshot can't find the game.

## Quick reference

- "instala X" / "install X" / "descarga X" → `steam_game(play_or_install)`
- "jugá X" / "abrí X" / "launch X" → `steam_game(play_or_install)` (rungameid covers both)
- "lanzá X solo si está instalado" → `steam_game(launch_only)`
- "tengo X?" / "está instalado X?" → `steam_game(lookup)` then read `installed`
- "qué juegos tengo?" → `steam_game(list_owned)`
