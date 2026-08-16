# 18 — Steam tool: solución definitiva al problema "instala doom eternal"

**Fecha**: 2026-05-11 madrugada
**Trigger**: usuario probó "instala doom eternal en steam" → Carter encadenaba 5-8 tools (skill_load + deeplinks + snapshots + locate) sin completar. El patrón openclaw (UIA snapshot+act) NO funciona para Steam porque su UI CEF/React expone solo un fragmento parcial del árbol — las tabs principales TIENDA/BIBLIOTECA viven en sub-hwnds separados y cambian estado out-of-sync con el LLM.

**Resultado**: nuevo tool `steam_game` que sidestep la UI completamente. UNA llamada, ~200ms-1.5s, sin clicks, sin vision, sin VLM.

---

## TL;DR — antes / después

**Antes** (5+ tools, fallaba):
```
skill_load(install-game) → gui_deeplink(steam,library) → gui(snapshot) →
gui(snapshot) → gui_deeplink(search) → gui(snapshot) → ...
"Avancé pero no terminé"
```

**Ahora** (1 tool, funciona):
```
steam_game(action=play_or_install, name="Doom Eternal")
→ {ok: True, appid: "782330", owned: False,
   expected_behavior: "opening store page (not owned)"}
```

Reply real del LLM con Gemma 4 26B-A4B:
> "Doom Eternal está en la tienda de Steam. ¿Querés que lo compre? (sí/no)"

Para juegos que SÍ tiene el usuario:
> Reply para "lanzá hogwarts legacy":
> "¡Dale! Estoy lanzando Hogwarts Legacy por Steam. Un segundo."

Para checks de biblioteca:
> Reply para "tengo cyberpunk 2077?":
> "No lo tenés en tu biblioteca de Steam. Si querés, te puedo buscar en la tienda para ver el precio."

---

## Por qué el patrón openclaw falló para Steam

openclaw funciona perfecto para **navegadores via CDP** porque Chrome expone su árbol ARIA completo cuando se conecta DevTools Protocol. Para apps **CEF embedded (Steam, Discord, Spotify)** el patrón equivalente sería UIA — y de hecho funciona PARA EL HEADER + MENU principal. Pero:

1. **Tabs principales (TIENDA / BIBLIOTECA / COMUNIDAD)** viven en un sub-hwnd `steamwebhelper.exe "Menu"` separado del main window, no son hijos del `Steam` window que UIA enumera por handle.
2. **Estado out-of-sync**: el deeplink `steam://nav/library` cuando Steam ya está abierto **no siempre cambia la vista** — el LLM toma snapshot y ve la página anterior.
3. **Carruseles `IsOffscreen=true`**: contenedores marcados offscreen por CEF aunque sean visibles. Filter por offscreen rompe el tree.
4. **CEF requiere flags**: `--force-renderer-accessibility=complete --enable-features=UiaProvider` deben pasarse al exe. Steam recompila + relanzo costoso.

Validado empíricamente esta sesión: el chain de snapshot+act NUNCA llegó a hacer click en "Install" tras 5 intentos consecutivos del LLM.

---

## La solución real: deeplinks + appid resolution

**Investigación profunda** (3 agentes en paralelo, ~2h equivalentes):

### Tier 0 — Resolver appid localmente

Steam guarda manifests de cada juego instalado en archivos plain text:

```
C:\Program Files (x86)\Steam\steamapps\appmanifest_<appid>.acf
```

Cada `.acf` es formato VDF (Valve Data Format), parseado en ~50 LOC:
```
"AppState"
{
    "appid"        "990080"
    "name"         "Hogwarts Legacy"
    "StateFlags"   "4"     // 4 = fully installed
}
```

`libraryfolders.vdf` lista carpetas de librería en discos secundarios.

**Resolución 100% offline, ~50ms para 47 juegos.**

### Tier 1 — Resolver appid online

Si el juego no está en local manifests, Steam expone una API pública sin auth:

```
GET https://store.steampowered.com/api/storesearch/?term=doom+eternal&l=english&cc=us
→ {"items": [{"id": 782330, "name": "DOOM Eternal", ...}]}
```

**Sin API key, ~200ms, sin scraping.**

### Tier 2 — Disparar el URI mágico

Steam soporta protocol handlers documentados ([Valve wiki](https://developer.valvesoftware.com/wiki/Steam_browser_protocol)):

| URI | Comportamiento |
|---|---|
| `steam://rungameid/<appid>` | **Lanza si instalado, descarga+lanza si owned, abre store si no owned**. La pieza clave. |
| `steam://install/<appid>` | Abre wizard de install (con dialog "Next") |
| `steam://store/<appid>` | Página de tienda |

**`rungameid` es el URI universal**: cubre los 3 casos en UNA llamada.

---

## Implementación

### `carter_v5/tools/steam.py` (~340 LOC)

```python
@tool(name="steam_game", description=...)
def steam_game(action: str, name: str = "") -> dict:
    # action ∈ {play_or_install, launch_only, lookup, list_owned}
    ...
```

Internals:
- `_find_steam_root()`: registry HKLM/HKCU `Valve\Steam` + fallback `C:\Program Files (x86)\Steam`
- `_parse_vdf(text)`: parser VDF minimal (no soporta escapes complejos pero alcanza para appmanifests)
- `list_installed_games()`: walk all `appmanifest_*.acf` en todas las library folders
- `resolve_appid_local(query, games)`: exact → substring → fuzzy con `difflib.SequenceMatcher`
- `resolve_appid_online(query)`: HTTP GET storesearch, parse JSON
- `_dispatch_uri(uri)`: `os.startfile(uri)` (Windows shell handler)

### Skills actualizadas

[skills/install-game/SKILL.md](carter_v5/skills/install-game/SKILL.md): reescrito para usar `steam_game(play_or_install)` como path principal. Fallback GUI solo para Epic/Ubi/EA.

[skills/steam-library-check/SKILL.md](carter_v5/skills/steam-library-check/SKILL.md): reescrito para usar `steam_game(lookup)` ONE-CALL.

### Wiring

- Registrado con `@tool` en `carter_v5/tools/__init__.py` autoload
- Agregado a `composite_dispatcher.dispatch()` + `resolve()` + `COMPOSITE_NAMES`
- Agregado al `schemas_consolidated.json` para que el LLM lo vea
- Agregado a `tools_subset.py` de TODOS los tiers (6gb-16gb)

---

## Tests

**20 tests nuevos** en [carter_v5/tests/unit/test_steam_tool.py](carter_v5/tests/unit/test_steam_tool.py):

- VDF parser (2 tests)
- Local resolution: exact / case-insensitive / substring / shortest-name / fuzzy / empty (6 tests)
- Online resolution: empty / parse mock / network failure (3 tests)
- Tool dispatch: no name / unknown action / lookup mocked / lookup online / lookup fail / launch_only refuses / play_or_install dispatches URI (7 tests)
- Registry integration (2 tests)

**Suite total**: 306/306 pass.

---

## Validación con LLM real (Gemma 4 26B-A4B)

Stub mode ON (no abre apps reales, valida que el LLM emite la tool correcta):

| Prompt | Tools | Reply | Outcome |
|---|---|---|---|
| "instala doom eternal en steam" | `steam_game(play_or_install, "Doom Eternal")` | "Doom Eternal está en la tienda de Steam. ¿Querés que lo compre? (sí/no)" | ✅ honesto |
| "lanzá hogwarts legacy" | `steam_game(play_or_install, "Hogwarts Legacy")` | "¡Dale! Estoy lanzando Hogwarts Legacy por Steam." | ✅ |
| "tengo cyberpunk 2077?" | `steam_game(lookup, "Cyberpunk 2077")` → `owned=False source=store_search` | "No lo tenés en tu biblioteca de Steam. Si querés, te puedo buscar en la tienda para ver el precio." | ✅ |
| "tengo hogwarts legacy?" | `steam_game(lookup, "Hogwarts Legacy")` → `owned=True installed=True` | "Sí, lo tenés y además ya está instalado. ¿Querés que lo abra?" | ✅ |
| "qué juegos tengo en steam" | `steam_game(list_owned)` → `count=47` | (server cayó al follow-up por bug #22527, no de Carter) | tool funcionó |

**4/5 perfectos. El 5° fue bug runtime no relacionado.**

---

## Resolución appid validada en vivo

Sobre la biblioteca real del usuario (47 manifests detectados):

| Query | Match | Source | Appid |
|---|---|---|---|
| "Forza Horizon 5" | Forza Horizon 5 | local_manifest | 1551360 |
| "hogwarts" (fuzzy) | Hogwarts Legacy | local_manifest | 990080 |
| "Cyberpunk 2077" (no owned) | Cyberpunk 2077 | store_search | 1091500 |
| "Doom Eternal" (no owned) | DOOM Eternal | store_search | 782330 |

---

## Lo que queda como honest limitation

1. **Bug llama.cpp Issue #22527** sigue afectando sesiones largas con Gemma 4 26B-A4B. El launcher detecta server-down y respawna automático. Esto es upstream, no Carter.

2. **Epic/Ubisoft/EA launchers**: el tool `steam_game` resuelve solo Steam. Para esos, fallback GUI (snapshot+act) que es brittle. Sería un próximo `epic_game.py` con el patrón similar (resolver appid de Epic Store API + dispatch deeplink `com.epicgames.launcher://...`).

3. **No auto-confirma el dialog de install**: si Steam abre el wizard "Install — Next Next Finish", el usuario tiene que clickear. NO hay forma documentada de auto-confirmar via URI ([investigación adjunta](16_openclaw_vs_carter.md)). Workaround posible: GUI snapshot+act del wizard (que SÍ es UIA Win32 nativo, no CEF).

4. **CEF accessibility flags persist**: el primer launch de Steam requiere ~10s de relaunch para activar `--force-renderer-accessibility=complete`. Las siguientes son instant. Ya cableado en `cef_accessibility.py`.

---

## Próximos pasos sugeridos

1. **Epic Games tool** con mismo patrón (resolver Epic App ID + `com.epicgames.launcher://` URI)
2. **Manejar dialog de install wizard via GUI snapshot+act** (es Win32, sí funciona)
3. **Auto-confirmar wizard con keyboard simulation** (Enter para "Next")
4. **Steam Workshop / mods** vía `steam://url/CommunityFilePage/<id>` URIs

---

## Referencias

- Valve: https://developer.valvesoftware.com/wiki/Steam_browser_protocol
- Steamworks IStoreService: https://partner.steamgames.com/doc/webapi/IStoreService
- Steam manifest format: https://github.com/leovp/steamfiles
- Forensic analysis Steam: https://www.forensicxlab.com/blog/steam
- Steam community thread (URI behavior): https://steamcommunity.com/discussions/forum/1/540744935066349428/
- Decky CEF debugging (futuro v5.1): https://wiki.deckbrew.xyz/plugin-dev/cef-debugging
