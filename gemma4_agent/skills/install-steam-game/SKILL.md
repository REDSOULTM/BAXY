---
name: install-steam-game
description: Install or launch a Steam game by name. Searches user's library first, falls back to store with purchase confirmation. Verifies the game/store opened.
priority: high
metadata:
  examples:
    - "instalá este juego de steam"
    - "abrí este juego de mi biblioteca de steam"
    - "descargá e instalá tal juego en steam"
    - "lanzá el juego de steam por nombre"
    - "install this steam game by name"
    - "instale este jogo da steam"
requires:
  any_bins: [steam, steam.exe]
  os: [windows]
---

# Install / launch a Steam game

**Tools used**: `steam`, `verify`, `gui` (optional), `app`.
**Honesty-critical**: yes — apply `purchase-guard` if the game is not owned.

## Cuándo usar este skill

El usuario dice algo como:
- "instalá Doom Eternal"
- "abrí Half-Life 2"
- "jugá <game>"
- "buscá <game> en mi Steam"

Si el game es **online/web** (Geforce Now, Xbox Cloud), NO usar este skill;
ir a browser.

## Steps

### 1. Buscar en biblioteca del usuario primero

```
steam(action="search_library", query="<game name>")
```

Devuelve `matches` ranked. Si el primer match tiene `score >= 90` y
`local_match_verified=True`, el juego **ya está instalado**.

### 2a. Si está en la biblioteca → lanzar directo

```
steam(action="launch_game", query="<game name>")
```

Después verificar:

```
verify(action="app_opened", name="<expected exe>")
```

Steam games tardan 5-30s en aparecer como proceso. Si `verify` retorna
`found=False`, NO insistir de inmediato — esperar 5s y reintentar **una sola
vez**. Si sigue sin aparecer, reportar UNVERIFIED honestamente.

### 2b. Si NO está en la biblioteca → ir a la tienda

```
steam(action="store_page", query="<game name>")
```

Inspeccionar el resultado:
- Si trae `price` o `edition` info → tomar nota.
- Reportar al usuario: "<Game> no está en tu biblioteca. En la Steam Store
  está por <precio>. ¿Querés que lo compre? (sí/no)"

**APLICAR PURCHASE-GUARD**: NO emitir click sobre "Comprar"/"Buy" hasta
que el usuario diga "sí" en el próximo turn.

### 3. Verificar visualmente (opcional)

Si el usuario quiere confirmación visual:

```
gui(action="screenshot")
```

Reportar lo que se ve en la captura: ventana de Steam, juego en biblioteca,
precio en store, etc.

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Game ya estaba abierto y se enfocó | "Steam estaba abierto, te traje el juego adelante." |
| Game se lanzó y verificó | "Lancé <game>." |
| Game se lanzó pero verify no encontró el proceso en 5s | "Inicié <game>, pero todavía no veo el proceso. Esperá unos segundos a que cargue." |
| Game NO está en biblioteca, store abierto | "<Game> no lo tenés. En la tienda Steam está por <precio>. ¿Lo compro? (sí/no)" |
| Game ni en biblioteca ni en store | "No encontré <game> en tu Steam. ¿Probás con otro nombre o lo busco en Epic/GOG?" |

## Anti-patterns

- ❌ Saltar directo a la store sin chequear biblioteca (el usuario podría
  ya tenerlo).
- ❌ Clickear "Comprar" sin permiso explícito (viola purchase-guard).
- ❌ Decir "lanzé <game>" si el verify_app_opened retornó found=False.
- ❌ Inventar AppIDs de Steam (si necesitás uno, usá `steam(action="search_store")`).
