# MCP — Servidores conectados (2026-05-29)

Análisis de gaps (68 áreas propias vs 20 servidores MCP): **la mayoría de los MCP
DUPLICAN las tools propias** y perderían por latencia (medido: tool propia 3.6 ms
vs MCP 1210 ms = ~330× — cada call MCP abre un subproceso stdio). MCP solo vale
para **capacidades NUEVAS** que el agente no tiene. Conectamos los 3 keyless/útiles
que NO duplican nada.

## Cómo activar

MCP está **gated OFF** por default (no afecta a nadie que no lo prenda):

```powershell
$env:GEMMA4_MCP = "1"
```

Al arrancar con el flag, el agente descubre las tools de los servidores en
`~/.gemma4/mcp_servers.json`, las enrola al router (namespaced `mcp__server__tool`),
y el cap `MAX_SELECTED_TOOLS=5` las limita junto a las tools propias (el 4B nunca
ve las 44 de golpe).

## Servidores configurados (`~/.gemma4/mcp_servers.json`)

| Server | Tools | Key | Capacidad NUEVA que agrega |
|---|---|---|---|
| **weather** (Open-Meteo) | 17 | NO (keyless) | Clima ESTRUCTURADO (forecast/histórico ERA5/calidad-de-aire/marino/geocoding). Reemplaza el clima-por-web-search que era frágil. |
| **youtube** | 1 | NO (keyless) | `get_transcript`: entender/resumir un video sin reproducirlo. |
| **github** | 26 | **SÍ (PAT)** | Operar GitHub remoto: issues/PRs/code-search/Actions. Tu `developer` es git LOCAL; esto es la capa GitHub. |

## GitHub: falta tu token (PAT)

GitHub descubre las 26 tools sin token, pero las LLAMADAS necesitan un Personal
Access Token. Generá uno en https://github.com/settings/tokens (scope `repo` +
`read:org` alcanza para lo común) y poné el valor de UNA de estas formas:

1. **Por env var** (recomendado, no queda en el JSON):
   ```powershell
   $env:GITHUB_PERSONAL_ACCESS_TOKEN = "ghp_tu_token_aqui"
   ```
2. **En el config** (`~/.gemma4/mcp_servers.json`, campo `env` del server github).

El cliente MCP mergea el `env` del config con el entorno actual; un valor vacío en
el JSON NO pisa la env var (así podés usar la env var sin tocar el archivo).

**Sin token, las tools de GitHub fallan HONESTO** (error de auth, no inventan).

## Por qué NO conectamos los demás (duplican o violan leyes)

- **Duplican tools propias** (perderían en los 330×): filesystem (`filesystem`),
  fetch (`web`/`document`), playwright (`browser_real`), sqlite (`database`),
  slack (`computer_use`), spotify (`media`/`audio`), markdownify (`document`),
  time (SO + `reminder`), memory-graph (`memory`/`knowledge`).
- **Violan las leyes** (API paga / cloud obligatorio): Google Maps (billing),
  Notion (token+cloud), Spotify/Slack (OAuth de cuenta externa).

## Regla de oro (del análisis)

MCP es un **multiplicador de capacidades nuevas**, NO un reemplazo de las tools
propias. Las propias ganan para lo core (archivos/GUI/voz/sistema): ~330× más
rápidas, funcionan offline, y traen verificación estructural (`verified`/`evidence`)
que las MCP no tienen. Conectar un MCP, medir contra un caso concreto, y
desconectar lo que no demuestre su valor.

## Validación (2026-05-29)

- Los 3 servers descubren: weather 17 / youtube 1 / github 26 = **44 tools**.
- EN VIVO: geocoding "Buenos Aires" → coords reales; weather_forecast → datos
  estructurados. El router rankea las weather-tools al top para "qué temperatura
  hace en Madrid", respetando el cap (6 ≤ 7).

## Routing de MCP — fix + techo honesto (medido)

**Causa raíz hallada** (research de routing del proyecto): `planner.py:534`
(`if not names`) descartaba toda la lista semántica `sem` —donde viven las MCP—
cuando una keyword nativa (clima→`web`) ya llenaba `names`. Las MCP nunca llegaban
al 4B → 0/3 en vivo.

**Fix aplicado** (reusa el patrón `media`-por-score, research-aligned):
- Promover la MEJOR tool MCP de `scored` a `names[0]` si supera `_MCP_PEAK_KEEP`
  (bar PROPIO 0.30, porque las MCP usan descripciones crudas y viven en cosine más
  bajo que el bar nativo 0.50). Collapse del cluster a 1 representante.
- Enriquecer la descripción enrolada con el NOMBRE de la tool tokenizado
  (`weather_forecast`→"weather forecast") para subir la señal sin keywords-por-idioma.
- NO toca la keyword `web` (fallback nativo) ni el router nativo (59 tests verdes).

**Resultado MEDIDO (honesto):**
- Subset: la weather MCP entra en 2/3 fraseos de clima + 0 falsos positivos en
  no-clima + nativo intacto. ✓
- EN VIVO: el 4B elige la weather MCP con fraseos EXPLÍCITOS ("dame el pronóstico
  del tiempo") 2/2, pero NO con coloquiales ("qué temperatura hace") 0/3 — ahí
  prefiere `web` (la tool familiar; el research de toolcalling lo predice:
  "unfamiliar tools suppress selection").
- Además entra la variante `seasonal_forecast`/`air_quality` en vez de la ideal
  `weather_forecast` (descripciones casi-idénticas, near-tie de cosine).

**Decisión:** MCP queda **gated OFF** por default. El routing mejoró (de "nunca
entra" a "compite cuando es relevante"), pero el flip a default-ON NO está
justificado: el 4B no elige MCP sobre sus tools nativas con fraseo coloquial, y
forzarlo (sacar `web` del subset) arriesga el router nativo que costó 6 sprints.
Pendiente para un sprint dedicado: (a) hacer entrar `weather_forecast` específico
(no las variantes), (b) un tool-rule que enseñe al 4B cuándo preferir la MCP.
Gate `GEMMA4_MCP=1` + override `GEMMA4_MCP_PEAK_KEEP` para experimentar.
