# 15 — Skills para el Bench 540

**Fecha**: 2026-05-11
**Insumo**: bench oficial `Extras/Carter_v3_tests/Carter_v3_Testing_100_Maximo_Esplendor_18x30.md` (18 cats × 30 cases = 540).

## Filosofía clave

**No todas las categorías necesitan skill.** Las skills son útiles cuando hay una **cadena multi-paso reutilizable** con high reward (varios casos del bench se resuelven con la misma receta).

**Regla 80/20**: 80% del bench son tools simples que el prompt v3 ya guía. Solo el 20% (cadenas GUI/multi-step) se beneficia realmente de una skill.

---

## Mapeo categoría → ¿skill necesaria?

| Cat | Casos | Tipo | ¿Skill útil? | Por qué |
|---|---|---|---|---|
| **C01** | conversación trivial (hola, mmm, gracias, ok) | conversacional | ❌ NO | Router short-circuit canned reply. Cero tools. |
| **C02** | identidad/límites ("quién eres", "qué puedes hacer") | conversacional | ❌ NO | Prompt v3 ya define identidad |
| **C03** | conocimiento ("qué es Batman", "ley de Ohm") | knowledge | ❌ NO | Archetype KNOWLEDGE pasa tools=[] al LLM |
| **C04** | memoria (recordá, olvidá, qué prefiero) | memory tool | 🟡 ⚠️ útil para flows complejos | Skill **`memory_curate`** opcional |
| **C05** | conversación vs acción | router | ❌ NO | Router clasifica archetype |
| **C06** | router de tools | meta | ❌ NO | Es el router mismo |
| **C07** | abrir/cerrar apps Windows | tool simple | ❌ NO | `app(action=open/close, name=X)` ya cubre |
| **C08** | web/URLs | tool simple | ❌ NO | `web(action=open_url/search)` ya cubre |
| **C09** | Steam | **chain multi-step** | ✅ **SÍ — skill `steam_library_check`** | "buscá X en mi biblioteca sin abrir" requiere deeplink + screenshot + locate + read |
| **C10** | filesystem | mostly tool simple | 🟡 útil para tareas complejas | Skill **`filesystem_workflow`** para casos como C10-22 "buscá ContextoCarter.md" |
| **C11** | terminal | tool simple + safety | ❌ NO | `terminal_run` ya cubre |
| **C12** | safety (destructive) | safety policy | ❌ NO | safety/policy.py + confirm flow |
| **C13** | **GUI/visión** | **chain multi-step** | ✅ **SÍ — skill `gui_visual_action`** | "haz click en botón X si visible" |
| **C14** | **misiones compuestas** | **chain multi-step** | ✅ **SÍ — múltiples skills** | "abre Steam, busca Batman, dime si está instalado" = receta de 5-7 pasos |
| **C15** | latencia | infra | ❌ NO | Es métrica del bench, no skill |
| **C16** | multilingüe/typos | router | ❌ NO | Router + SequenceMatcher cross-lingual |
| **C17** | follow-ups | context | ❌ NO | history + anaphora detection |
| **C18** | regresiones reales | varía por caso | 🟡 caso por caso | Algunos cases pueden necesitar skills nuevas |

---

## Catálogo propuesto: 6 skills core

### Skill 1 — `install_game` ⭐ (ya creada como microagent)

**Archivo**: `microagents/install_game.md`
**Categorías cubiertas**: C09 parcial, C14-01
**Cadena**:
1. `gui_deeplink(steam, search, query)`
2. `gui(screenshot)`
3. `gui(locate, "tarjeta juego")`
4. `gui(click, x, y)`
5. `gui(locate, "botón Instalar")`
6. Si "Instalar" → click + verify download started
7. Si "Comprar" → STOP, reportar honesto

**Honesty rules**: NUNCA clickear "Comprar" sin "sí" del user.

---

### Skill 2 — `steam_library_check` (nueva)

**Cuándo aplica**: el user pregunta si X está en su biblioteca de Steam SIN ejecutarlo.

**Trigger keywords**: `"mi biblioteca"`, `"está instalado"`, `"tengo el juego"`, `"library"`

**Cubre casos del bench**:
- C09-04 "busca Batman en mi biblioteca de Steam"
- C09-05 "si Batman no está en biblioteca, dime eso sin comprar nada"
- C09-06 "busca Hades en mi biblioteca, no lo ejecutes"
- C09-07 "dime si Marvel Rivals está instalado, sin abrirlo"
- C14-01 "abre Steam, ve a biblioteca, busca Batman y dime si está instalado"

**Cadena**:
1. `gui_deeplink(steam, library)` — abrir Steam en Library
2. `gui(screenshot)`
3. `gui(check_blockers)` — modal de login? actualización?
4. `gui(type, value=<game_name>)` — escribir en barra de búsqueda de biblioteca
5. `gui(screenshot)`
6. `gui(locate, "juego <name>")` — buscar el juego en resultados
7. Si visible → reportar "Sí, lo tenés instalado"
8. Si no visible → reportar "No aparece en tu biblioteca. ¿Querés que lo busque en la tienda?"

**Honesty rules**:
- NUNCA decir "instalado" sin que vision_locate confirme visible=True.
- NUNCA lanzar el juego (V13 GUI on-demand + V20 no acción si user dijo "no lo ejecutes").

**Estimación bench impact**: cubre 5 cases (C09-04, 05, 06, 07; C14-01).

---

### Skill 3 — `gui_visual_action` (nueva)

**Cuándo aplica**: el user pide "haz click en X" o "escribí Y en pantalla" o "busca el botón Z".

**Trigger keywords**: `"haz click"`, `"clickea"`, `"presiona"`, `"escribí"`, `"tipea"`

**Cubre casos del bench**:
- C13-02 "haz click en el botón Aceptar si está visible"
- C13-03 "si no ves el botón Aceptar, no hagas click"
- C13-04 "abre Notepad y escribe hola con GUI"
- C13-05 "selecciona todo el texto en Notepad"
- C14-26 "abre navegador, busca Python, abre docs y copia título"

**Cadena**:
1. `gui(screenshot)` — siempre primero ver pantalla
2. `gui(check_blockers)` — verificar no hay modal bloqueante
3. `gui(locate, target_description=<elemento>)` — encontrar el target
4. Si `visible=True` y user dijo "si visible" → `gui(click, x, y)` + verify frame_diff
5. Si `visible=False` y user dijo "si no ves no hagas" → REPORT "no encontré, no clickeé" (V3 honest)
6. Si user pidió escribir/tipear → tras click, `gui(type, value=<texto>)` + verify frame_diff

**Honesty rules**:
- Si vision_locate devuelve `visible=False` → respetar la condición negativa del user (C13-03 "no hagas click").
- NEVER claim "clicked" si frame_diff = 0 (verificador estructural).
- Loop detection: si 3+ vision_locate consecutivos devuelven visible=False → STOP, report.

**Estimación bench impact**: cubre 8-12 cases de C13 + algunos de C14.

---

### Skill 4 — `filesystem_workflow` (nueva)

**Cuándo aplica**: el user pide cadena de filesystem (crear + escribir + abrir, o buscar + leer + reportar).

**Trigger keywords**: `"crea ... y "`, `"busca archivo"`, `"backup"`, `"revisa el archivo"`

**Cubre casos del bench**:
- C14-04 "crea carpeta, archivo, escribe texto y ábrelo"
- C14-05 "revisa RESIDUAL.md, clasifica bugs y no toques código"
- C14-09 "crea backup, edita archivo y corre test afectado"
- C14-13 "busca un archivo; si existe ábrelo, si no créalo en sandbox"
- C10-22 "busca ContextoCarter.md"

**Cadena para "crea + escribe + abre"**:
1. `filesystem(create_dir, path)` si necesario
2. `filesystem(write, path, content)` — verifier valida que el archivo existe
3. `filesystem(open, path)` o `app(open, name="notepad")` + `gui(type)` según contexto

**Cadena para "busca archivo; si existe ábrelo, si no créalo"**:
1. `filesystem(search, query=<name>)` o `filesystem(list, path)`
2. Si resultados → `filesystem(open, path)` o `filesystem(read)`
3. Si no resultados → `filesystem(create_dir)` + `filesystem(write)`

**Honesty rules**:
- NUNCA editar sin backup si user dijo "con backup".
- read-only si user dijo "no toques código" (V20 distinguir conv/acción).

**Estimación bench impact**: cubre 6-8 cases de C10 + C14.

---

### Skill 5 — `dev_workflow` (nueva)

**Cuándo aplica**: el user pide cadenas de desarrollo (correr tests, verificar resultados, rollback).

**Trigger keywords**: `"corre tests"`, `"pytest"`, `"git status"`, `"build"`, `"deploy"`

**Cubre casos del bench**:
- C14-06 "corre tests rápidos, hardcode_guard y resume resultados"
- C14-07 "si falla un test, detente y reporta sin arreglar"
- C14-08 "arregla solo un bug real y agrega regresión"
- C14-22 "corrige un bug y agrega test permanente que falle antes"
- C14-24 "haz rollback si baja el runner global"

**Cadena para "corre tests + resume"**:
1. `terminal_session(cd <project>)` (persistent shell, OpenHands pattern)
2. `terminal_session(pytest tests/ -v --tb=short)`
3. Parsear stdout para PASS/FAIL counts
4. `filesystem(read)` si hay archivo de resumen
5. Reportar honesto: "X passed, Y failed. Fallos: ..."

**Cadena para "si falla detente"**:
1. Correr tests UNA vez
2. Si exit_code != 0 → STOP. NO arreglar nada. Reportar.
3. Si exit_code == 0 → reportar PASS.

**Honesty rules**:
- NUNCA decir "tests OK" sin parsear exit_code real.
- C14-07 explícito: NO auto-fix sin permiso.

**Estimación bench impact**: 4-6 cases C14.

---

### Skill 6 — `media_workflow` (nueva)

**Cuándo aplica**: control de Spotify/YouTube/playback con cadenas.

**Trigger keywords**: `"abre Spotify"`, `"pon música"`, `"reproduce"`, `"baja volumen"`, `"siguiente canción"`

**Cubre casos del bench**:
- C14-03 "abre Spotify, pon música y baja volumen a 20"
- C14-02 "abre YouTube, busca música lofi y no reproduzcas nada"

**Cadena para "abre Spotify, pon música, baja volumen a 20"**:
1. `gui_deeplink(spotify, search, query="música" o playlist preferida)`
2. `gui(screenshot)`
3. `gui(locate, "botón Play" o "primera canción")`
4. `gui(click, x, y)` — play
5. `system_control(set_volume, level=20)`
6. Verify volumen via `system_info(volume)`

**Cadena para "no reproduzcas nada"**:
1. `gui_deeplink(youtube, ...)` o `web(open_url)`
2. `gui(type, value="música lofi")` — solo buscar
3. `gui(screenshot)` — confirmar resultados visibles
4. STOP. Reportar "abrí YouTube en búsqueda lofi. NO reproduje nada como pediste".

**Honesty rules**:
- Respetar la negación (V20): "no reproduzcas" = NUNCA click play.

**Estimación bench impact**: 2-3 cases.

---

## Skills opcionales para casos puntuales

### Skill 7 — `memory_curate` (opcional)

Para C04 casos complejos como "olvidá X pero mantenete Y". Si MissionGoal estructural alcanza, no necesario.

### Skill 8 — `troubleshoot_workflow` (opcional)

Ya cubierto por el microagent `troubleshoot.md` que escribí. Convertible a skill formal si el v5.1 lo justifica.

---

## Tabla resumen: impacto esperado en bench 540

| Skill | Cases cubiertos | Prioridad |
|---|---|---|
| `install_game` ⭐ (ya creada) | C14-01 (instala juego), parte de C09 | **P0** |
| `steam_library_check` | C09-04, 05, 06, 07; C14-01 = 5 cases | **P0** |
| `gui_visual_action` | C13-02, 03, 04, 05; C14-26 = 8-12 cases | **P0** |
| `filesystem_workflow` | C14-04, 05, 09, 13; C10-22 = 6-8 cases | **P0** |
| `dev_workflow` | C14-06, 07, 08, 22, 24 = 4-6 cases | **P1** |
| `media_workflow` | C14-02, 03 = 2-3 cases | **P1** |
| `troubleshoot_workflow` | varios C18 | P2 |
| `memory_curate` | algunos C04 | P2 |

**Estimación total P0**: ~25-32 cases del bench cubiertos con skills.

**Casos sin skill (otros 510)**: cubiertos por router + prompt v3 + tools simples ya implementados.

---

## Costo en tokens (worst case)

| Set activo | Tokens |
|---|---|
| 1 skill cargada (matched) | +500-800 |
| 2 skills cargadas | +1000-1500 |
| 3 skills cargadas (cap) | +1500-2000 |
| **+ CORE_PROMPT v3** | **+3500 (fijo)** |
| **+ tools schemas consolidated** | **+1745 (fijo)** |
| **Worst case total system** | **~7000 tokens** |

Para tier_16gb (context 8192): **deja 1200 tokens para conversación**. Apretado.
Para tier_10gb (context 16384): **deja 9000 tokens**. Cómodo.

**Decisión**: aplicar las 4 skills P0 con CUIDADO en triggers (específicos), y cap=3 ya implementado evita overload.

---

## Plan de implementación

### Fase 1 (P0, antes de bench)

1. **`install_game.md`** — ya hecho ✅
2. **`steam_library_check.md`** — crear ahora
3. **`gui_visual_action.md`** — crear ahora
4. **`filesystem_workflow.md`** — crear ahora

### Fase 2 (P1, después de medir baseline)

5. `dev_workflow.md`
6. `media_workflow.md`

### Fase 3 (P2, si bench muestra que hace falta)

7. `troubleshoot_workflow.md` (mejorar el actual)
8. `memory_curate.md`

---

## Honesta opinión

**No todas las "soluciones" requieren una skill nueva.** El 80% del bench se resuelve con:
- Router estructural correcto
- Prompt v3 con reglas claras
- 16 composite tools con descripciones precisas
- MissionGoal verifier honesto

**Las skills son la diferencia entre 75% PASS y 90% PASS** en las categorías donde la cadena es no-trivial (C09 Steam, C13 GUI, C14 multi-step).

Si querés llegar a 540/540 o cerca, **las 4 skills P0 son necesarias**. Si te conformás con 85%, alcanza con `install_game` + el prompt v3 actual.

---

## Próximo paso

¿Querés que cree las 3 skills P0 faltantes (`steam_library_check`, `gui_visual_action`, `filesystem_workflow`) ahora, o esperamos a tener una medición de baseline con solo `install_game` para ver dónde estamos?
