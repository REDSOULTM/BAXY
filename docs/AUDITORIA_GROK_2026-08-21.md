# Auditoría: qué hay que cambiar en el repositorio para Grok 4.6

## Estado de aplicación — 2026-08-21

El diagnóstico de abajo se hizo primero y **está aplicado**, salvo dos cosas que
siguen abiertas a propósito.

**Hecho:**

- Hallazgo 1 — `AGENTS.md`, `docs/AI_CONTEXT_MAP.md`, la skill `evidencia-baxy` y las
  seis recetas de `GUIA_AGENTES_IA/` ya no dicen `rg`, `sed`, `head` ni `wc`: dicen
  `grep`, `read_file`, `list_dir` y PowerShell.
- Hallazgo 2 — `AGENTS.md` bajo el tope, con el presupuesto escrito en su propio pie;
  `CLAUDE.md` deja de ser un redirect y sólo lista las diferencias de harness.
- Hallazgo 4 — 18 skills bundled apagadas en `~/.grok/config.toml`, instaladas con
  `.grok/install-config.ps1` y verificadas con `grok inspect`.
- Hallazgo 5 — los once goals llevan el mismo bloque **«Cómo trabajas aquí»** y
  apuntan a Grok 4.6; el bloque de tendencias de Opus se retiró, y no se sustituyó
  por otro porque las de Grok no están medidas.
- Hallazgo 6 — `/goal` documentado en `00_INDICE.md` y en `03C_PROMPT.md`.
- Hallazgo 7 — «BAXY no es una aplicación web» dicho en `AGENTS.md` y en cada goal.
- Hallazgo 8 — `.grok/` creado con el método de medición; `.codex/` marcado como
  archivado.

**Abierto, y por qué:**

- Hallazgo 3 — los 77 ficheros sin versionar siguen ahí. Decidir cuáles son evidencia
  que se commitea y cuáles son basura es del dueño del proyecto, no de un agente.
- Hallazgo 9 — ninguna capacidad nueva se ha encendido. Ninguna entra sin medir antes
  con la sonda de `.grok/README.md`.

---

## El diagnóstico

Lo que sigue es la auditoría tal como se midió, antes de aplicar nada.

Medido en esta máquina el **2026-08-21** con **grok 1.0.5** (`grok --version`),
modelo **grok-4.6**, sobre `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`,
rama `main`.

## Cómo se midió

Tres instrumentos, todos reproducibles:

```powershell
grok inspect                 # qué descubre Grok en este directorio
grok inspect --json          # lo mismo, con rutas y conteo de tokens
```

Y la sesión real de Grok 4.6 que cerró el 03B y escribió el 03C, que queda en disco
con el prefijo exacto que vio el modelo:

```
~/.grok/sessions/<cwd-url-encoded>/01a022b0-ac37-72d2-b7ec-53e5297d9e6a/
  system_prompt.txt     6.057 chars — el prompt de sistema de Grok, literal
  prompt_context.json   lo que el harness inyecta (AGENTS.md, CLAUDE.md, shell, os)
  chat_history.jsonl    976 mensajes: 246 turnos de asistente, 477 tool_results
```

Dentro de la TUI: `/context` (reparto del contexto por categorías, con el coste de
las definiciones de tools y del listado de skills), `/session-info`, `/usage`.

## Línea base medida — el prefijo fijo de cada sesión

| Bloque | Chars | ≈ tokens | Origen |
|---|---:|---:|---|
| Prompt de sistema de Grok | 6.057 | 1.510 | Fijo, del harness |
| `<system-reminder>` de skills | 9.494 | 2.370 | 23 skills; **22 son bundled** |
| `AGENTS.md` | 8.746 | 2.225 | Nuestro |
| `<git_status>` | 3.465 | 865 | 62 líneas; hoy ya son 80 |
| `<user_rule>` de verificación en navegador | ~1.300 | ~325 | Fijo, del harness |
| `CLAUDE.md` | 579 | 147 | Nuestro |
| `<user_info>` (os, shell, cwd, fecha) | 223 | 56 | Fijo |
| **Total** | **~30.800** | **~7.700** | |

**Y la lectura honesta de esa tabla:** la ventana de grok-4.6 es de **500.000
tokens** con auto-compactación al 80 %. 7.700 tokens son el **1,5 %**. Recortar
tokens del prefijo **no es la optimización**: es margen que ya sobra.

Lo que sí cuesta caro es distinto, y es de lo que va el resto de este documento:

1. Instrucciones que **no se pueden obedecer** porque nombran herramientas que en
   esta máquina no existen para Grok.
2. Un **tope duro de 10.000 caracteres** por fichero de reglas, del que `AGENTS.md`
   ya gasta el 87 %.
3. Ruido que compite por la atención del modelo con lo que sí importa.

## Lo que cambia respecto a Codex y a Claude Code

| Cosa | Codex (lo escrito en `.codex/`) | Grok 1.0.5 | Consecuencia |
|---|---|---|---|
| Fichero de reglas | `AGENTS.md`, tope 32 KiB | `Agents.md` **y** `Claude.md`, tope **10.000 chars cada uno** | Se cargan **los dos**; el tope es 3× más estrecho |
| Config de proyecto | `.codex/config.toml` (inerte en 0.144.1) | `.grok/config.toml` — **sólo `[mcp_servers]`** | Modelo, esfuerzo, subagentes y skills **no** se pueden fijar desde el repositorio |
| Config de usuario | `~/.codex/config.toml` + perfiles | `~/.grok/config.toml` | Sigue haciendo falta un instalador, como `.codex/profiles/install.ps1` |
| Skills | `.agents/skills/` | `.grok/`, `.agents/`, `.claude/`, `.cursor/` — **`.agents/` funciona**, verificado | No hay que mover nada |
| Esfuerzo de razonamiento | `model_reasoning_effort` | `/effort low\|medium\|high\|xhigh`, por defecto `high` | **Existe**, al contrario que en Claude Code |
| Subagentes | Se configuran y se abaratan | `spawn_subagent`, activos por defecto, **heredan el modelo del padre** | La política «por defecto no» hoy sólo vive en `AGENTS.md` |
| Shell | — | **PowerShell** (`shell_path = powershell`, medido) | Ver hallazgo 1 |
| Ventana | ~272K | **500K**, auto-compact al 80 % | Menos presión de compactación |
| Medición del prefijo | `codex debug prompt-input` | `grok inspect --json`, `/context`, y la sesión en disco | Equivalente y mejor |
| Extras del repositorio | — | `.grok/agents/`, `.grok/roles/*.toml`, `.grok/personas/*.toml`, `.grok/hooks/`, `.grok/lsp.json` | Capacidades nuevas, ninguna usada hoy |

Estado descubierto hoy: 1 skill de proyecto (`evidencia-baxy`), 3 agentes builtin,
**0** plugins, **0** MCP, **0** hooks, **0** LSP, config de proyecto **ninguna**.
Los permisos salen de `~/.claude/settings.json` (5 reglas viejas de `pycaw`).

---

## Hallazgo 1 — `rg` y `sed` no existen para Grok. Y son la mitad de `AGENTS.md`

El más importante, y el único que ya está causando daño.

`AGENTS.md` §«Buscar antes de leer» y §«Ficheros que no se leen enteros», más la
skill `evidencia-baxy` entera, están escritas sobre `rg -n`, `sed -n`, `head -3` y
`wc -l`. En esta máquina:

- **`rg` no está instalado.** Existe dentro de Claude Code porque Claude Code
  inyecta una función `rg` en su shell (`type rg` → *is a function*). En PowerShell,
  `Get-Command rg` → nada. La shell de Grok es PowerShell.
- `sed`, `head`, `wc` y `grep` sí resuelven, pero por `C:\Program Files\Git\usr\bin`,
  y el prompt de sistema de Grok le ordena lo contrario: *«prefer `read_file` for
  reading files instead of cat/head/tail, `search_replace` instead of sed/awk.
  Reserve bash exclusively for actual system commands»*.

Medido en la sesión del 03B, sobre **88 comandos de shell**: `rg` **0 veces**, `sed`
**0 veces**, `head`/`wc` **2**. Lo que sí hizo el modelo: 172 `read_file`, 59 `grep`,
y PowerShell puro (`Get-Process`, `Get-ChildItem`, `Test-Path`, `Select-Object`,
here-strings). Es decir: **obedeció al harness y desobedeció a `AGENTS.md`**, y la
disciplina que esas dos secciones querían imponer —localiza, lee sólo el rango, no
abras nada de más de 1 MB— viajó gratis o no viajó.

**Qué hacer.** Reescribir esas dos secciones y la skill en el vocabulario real de
Grok: `grep` (que ya es ripgrep por dentro) con su ámbito por defecto, `read_file`
con rango de líneas, `list_dir`, y PowerShell (`Get-Item ... .Length`,
`Get-Content -TotalCount 3`, `git ls-tree -r -l HEAD -- ruta`) para lo que de verdad
necesita shell. La regla que hay que conservar es la de siempre —índice, título,
fragmento, documento— no la sintaxis.

Beneficio secundario: son los caracteres más caros del fichero, y liberan sitio bajo
el tope de 10.000.

## Hallazgo 2 — `AGENTS.md` gasta el 87 % del tope y `CLAUDE.md` se carga además

`AGENTS.md` = 8.746 chars de un tope de **10.000**. Quedan 1.254. Al pasarse, Grok
**trunca** el fichero con un aviso, y lo que se pierde es el final: «Subagentes»,
«Handoff y terminado». Es decir, justo las reglas que evitan gasto y pérdida de
trabajo.

`CLAUDE.md` (579 chars) se carga **también**, como segunda instrucción de proyecto,
porque Grok busca `Agents.md`/`Claude.md`/`AGENT.md`/`AGENTS.md` y Windows no
distingue mayúsculas. Su contenido hoy le dice a Grok que lea `AGENTS.md` —que ya
tiene cargado— y le habla de Claude Code.

**Qué hacer.** Dos decisiones separadas:

- El tope: presupuestar `AGENTS.md` explícitamente (una línea al final del fichero
  con el número), y comprobarlo con `grok inspect` en el mismo commit que lo toque.
  El hallazgo 1 devuelve espacio; no hace falta amputar nada más.
- `CLAUDE.md`: o desaparece, o deja de ser un redirect y pasa a ser lo que su nombre
  promete —**las diferencias de harness**, una lista corta, sin repetir `AGENTS.md`—.
  Hoy paga 147 tokens por decir algo que el propio harness ya resolvió.

## Hallazgo 3 — 72 artefactos sin versionar inflan el arranque de cada sesión

`git status --short` imprime hoy **80 líneas**, 77 de ellas `??`, 72 bajo
`artifacts/` (19,8 MB). Grok inyecta ese `git status` entero en el primer mensaje de
cada sesión: 3.465 chars medidos cuando eran 62 líneas.

No es el coste en tokens lo que preocupa —ya está dicho que sobra ventana—, es que
el **primer** contexto que ve el modelo son 72 rutas de corridas ya hechas, y que el
estado real del árbol queda ilegible. Los commits del 03B/03C sí versionan sus
artefactos (`goal03: rec5e2e3 serves 95/124`): éstos son restos, no una política.

**Qué hacer.** Decidir uno por uno —commit como evidencia fechada, o `.gitignore`— y
dejar `git status` en algo que quepa de un vistazo. Es trabajo de 20 minutos y
mejora todas las sesiones futuras, sean de Grok o no.

## Hallazgo 4 — el catálogo de skills: 22 de 23 no son de este repositorio

El `<system-reminder>` de skills son 9.494 chars, más que `AGENTS.md`. Dentro:
`evidencia-baxy` (la nuestra) y 22 bundled — `game-animation-frames`,
`game-character-consistency`, `game-tilesets`, `game-ui-icons`, `game-asset-core`,
`imagine`, `design`, `docx`, `pptx`, `pdf`, `pr-babysit`, `resume-claude`,
`resume-codex`, `resume-cursor`… Para un producto .NET + Python + PowerShell + React
que se desarrolla en local, casi ninguna aplica.

Se apagan, y se pueden apagar **conservando** las que sí sirven
(`code-review`, `review`, `implement`, `execute-plan`, `create-skill`):

```toml
# ~/.grok/config.toml
[skills]
disabled = ["game-tilesets", "game-ui-icons", "imagine", "docx", "pptx", "pdf"]
```

`disabled` las deja listadas pero **fuera del prompt de sistema**; `ignore` las
esconde del todo.

**Qué hacer.** Como es config de **usuario** y no de repositorio, va igual que en
Codex: una plantilla versionada más un instalador, sustituyendo `.codex/profiles/`.
Y se verifica con `grok inspect`, que marca `[disabled]` lo que quedó apagado.

## Hallazgo 5 — los goals apuntan a dos modelos y ninguno es el de hoy

`documentacion/sprints/00_INDICE.md` reparte así: 01–04 reescritos para **Claude
Opus 5**, `sol/` guardado para **GPT-5.6 Sol**, 03B/03C para **Grok 4.6**, y **05–11
todavía para Sol**. El fichero explica por qué se hablan distinto, y `sol/00_LEEME.md`
detalla la conversión a Opus.

Para Grok, la conversión **no** es la de Opus, es más corta:

- **`reasoning.effort` existe otra vez.** `/effort high` es el suelo y `xhigh` está
  disponible en 4.6 (en 4.5 no). Esa línea de los goals de Sol vuelve a ser válida,
  literalmente. Es el punto donde la versión `sol/` está **más cerca** que la de Opus.
- **El bloque de cuatro correcciones de Opus sobra casi entero.** El prompt de
  sistema de Grok ya ordena, de fábrica: mantener a la vista todos los requisitos
  explícitos hasta cumplirlos, **no afirmar que algo está hecho o probado sin
  salida de herramienta que lo sostenga**, mantener el cambio dentro de lo pedido,
  y responder en vez de devolver una pregunta cuando la respuesta está en el
  contexto. Repetirlo no lo refuerza: gasta el tope de 10.000 y le dice al modelo
  cosas que ya cree.
- **Lo que sí falta es la tendencia propia de Grok, y no está medida.** No la
  inventes: la sesión del 03B está en disco con 976 mensajes y se puede leer. Eso
  es una tarea de medición, no de redacción.

**Qué hacer.** Repuntar el índice, convertir 05–11 partiendo de la versión de Sol
(no de la de Opus), y sustituir el bloque de correcciones por lo que se mida.

## Hallazgo 6 — `/goal` es exactamente el flujo de este repositorio, y ya se usó

La consigna del repo es «cada goal se lanza en una sesión nueva, se pega entero, y
corre hasta cumplirse». Grok trae eso como mecanismo:

```
/goal <objetivo> [--budget <tokens>]
/goal status | pause | resume | clear
```

Trabaja por rondas y **sólo marca el goal cumplido después de una revisión de
evidencia independiente**; si esa revisión no reproduce el resultado o no encuentra
evidencia utilizable, el goal sigue activo o se para con los huecos concretos. La
sesión del 03B lo usó: en el historial aparece `A goal has been set: …` con el
prompt del 03B dentro.

Eso encaja con el invariante 2 del producto y con «la entrega se cierra en nivel 3,
verde entero». **Qué hacer:** documentarlo donde se documenta cómo se lanza un goal
—`documentacion/sprints/00_INDICE.md` y `03C_PROMPT.md` ya son «pégalo entero»— y
decidir si el criterio de cierre de cada goal se le entrega a `/goal` literalmente.

## Hallazgo 7 — BAXY no es una app web, y Grok cree que puede serlo

El harness inyecta un `<user_rule>` fijo de ~1.300 chars que obliga a verificar en
el navegador cualquier cambio que toque UI, rutas o estado que se renderiza. No es
configurable desde el repositorio y no se ha encontrado interruptor.

En BAXY la UI es `src/Baxy.FieldUi` dentro de un shell de escritorio, y no hay
herramientas de navegador en esta máquina. La regla misma dice qué hacer cuando no
las hay —verificar por el sustituto más cercano y decir qué no se pudo verificar—,
pero conviene que lo diga el repositorio, en una línea, antes de que un goal de UI
(06, 08) lo descubra a mitad.

## Hallazgo 8 — `.codex/` es una capa sustituida (ley 2)

`.codex/` son cinco ficheros bien escritos y medidos el 2026-08-18 que hoy describen
un harness que ya no se usa, y `.codex/README.md` documenta que `gpt-5.6-sol` exige
ChatGPT Pro. La ley 2 dice que si se añade una capa se retira la que sustituye.

**Qué hacer.** No borrarlo a ciegas: su estructura es el molde de lo que hay que
escribir para Grok (medición, modos, higiene de máquina, sonda repetible). Lo
razonable es **portarlo** a `.grok/` + una nota corta de que Codex queda archivado, y
que la parte de medición se rehaga con `grok inspect` y `/context`.

## Hallazgo 9 — capacidades de Grok que este repositorio pediría y no usa

Ninguna es gratis; van en orden de «lo pide una ley del proyecto» a «habría que
medirlo antes».

- **`web_fetch` está desactivado por defecto** (`GROK_WEB_FETCH=1`). `web_search` sí
  está. La ley 1 obliga a mirar el estado del arte, y varios goals lo exigen: hoy el
  agente puede buscar pero no abrir lo que encuentra.
- **Subagentes activos por defecto y heredando el modelo del padre.** La política del
  repositorio es «por defecto no», y en la sesión del 03B se cumplió (0 spawns en
  976 mensajes). Pero hoy eso depende de que el modelo lea `AGENTS.md`. Grok permite
  fijarlo —`[subagents] enabled = false`, o `[subagents.models]` y roles de sólo
  lectura en `.grok/roles/*.toml`— que es la forma que el propio `.codex/config.toml`
  ya defendía: el padre decide y escribe, la exploración se delega barata.
- **Hooks en `.grok/hooks/`**, con eventos de pre/post-tool y de sesión. Es el único
  sitio donde la escalera de validación podría dejar de ser una promesa. Ojo con la
  ley 2: sólo si sustituye algo, no encima.
- **LSP** (`lsp_tools = false`, `.grok/lsp.json`): pyright, el servidor de C# y
  tsserver darían definición y referencias reales sobre 174 ficheros de código vivo.
  Hay que medir si baja tool calls antes de adoptarlo.
- **`codebase_indexing = true`** por defecto, sobre un árbol de ~6.400 ficheros donde
  5.200 son evidencia. Acepta globs. Medir, y acotarlo a `src tests scripts main.py`
  si el índice está comiéndose `artifacts/` y `biblioteca/`.
- **Memoria** (`GROK_MEMORY=1`): guarda en `~/.grok/memory/`, **fuera del
  repositorio**. Choca de frente con «el estado se deja escrito en el repositorio a
  medida que avanzas». Recomendación: **dejarla apagada**; el handoff sigue mandando.
  `/flush` antes de una compactación es la excepción defendible.

## Lo que no hay que tocar

- **`permission_mode = "always-approve"`** ya está puesto en `~/.grok/config.toml` y
  coincide con «permisos totales, no preguntes». El sandbox está en `off`.
- **La shell es PowerShell** y el repositorio ya es PowerShell (`run_mvp.ps1`,
  `scripts/*.ps1`). Aquí no hay nada que arreglar: los comandos de la escalera de
  validación son correctos tal cual.
- **`.agents/skills/`** funciona con Grok. No hay que mover la skill a `.grok/skills/`.
- El contenido de los goals —objetivo, evidencia heredada, criterios de cierre— no lo
  toca nada de esto.

## Orden de trabajo propuesto para la sesión siguiente

1. Hallazgo 3 (artefactos sin versionar). Barato, mejora todo lo demás, y deja el
   `git status` legible antes de medir nada.
2. Hallazgo 1 (reescribir búsqueda y lectura en el vocabulario de Grok) + hallazgo 2
   (tope de 10.000 y decisión sobre `CLAUDE.md`). Van juntos: el primero libera el
   espacio que el segundo necesita.
3. Hallazgo 4 (skills apagadas) y hallazgo 8 (`.grok/` sustituye a `.codex/`), con el
   instalador y la nota de medición.
4. Hallazgo 5 (goals 05–11 desde la versión de Sol, no desde la de Opus) — pero sólo
   después de **medir** las tendencias de Grok sobre la sesión del 03B que hay en
   disco. Sin esa medición, el bloque nuevo sería opinión.
5. Hallazgo 9, uno por uno y con número delante. Ninguno entra «porque existe».

**Cómo se comprueba que sirvió.** La sonda de cinco tareas de `.codex/README.md`
sigue siendo válida —está escrita sobre este repositorio, no sobre Codex— y ahora se
puede correr sin TUI:

```powershell
grok --output-format json -p "<tarea>"
```

Se compara **entre configuraciones**, nunca en absoluto, y se mira lo mismo que
antes: número de tool calls, ficheros abiertos, si abrió algo de más de 1 MB, si
repitió una búsqueda, y si la respuesta es correcta. Una configuración que baja
tokens y sube tool calls no es una mejora.

## Lo que esta auditoría no ha medido

- Las tendencias de Grok 4.6 en este repositorio (hallazgo 5). Hay 976 mensajes en
  disco para hacerlo; no se ha hecho.
- Qué significa exactamente `compactions_remaining: 1` en el catálogo del modelo. La
  sesión del 03B compactó al menos una vez y siguió. Hasta saberlo, el handoff
  escrito en el repositorio es la única red.
- El coste real de las definiciones de tools y del índice de código, que `/context`
  sí desglosa dentro de una sesión y `grok inspect` no ve.
- Si `.grok/config.toml` acabará aceptando más que `[mcp_servers]` en versiones
  siguientes, como pasó con el ámbito de proyecto de Codex.
