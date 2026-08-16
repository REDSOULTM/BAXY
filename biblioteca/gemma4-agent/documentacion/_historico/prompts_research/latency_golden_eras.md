# Épocas de oro de Carter Agent — arqueología de latencia y calidad

Análisis forense de `~/.gemma4/logs/_pre_session/full.log` (303 turnos reales,
**2026-05-15 → 2026-05-20**) cruzado con `git log`. Objetivo: encontrar las
ventanas donde el sistema funcionó *mejor* — en **latencia** y en **calidad de
respuesta** — y entender, con evidencia, **qué lo hacía rápido y honesto**, para
poder volver a eso.

Todos los números salen del log real, medidos turno a turno (YOU→GEMMA). Nada
estimado. Cuando algo es hipótesis lo digo.

---

## TL;DR — el ganador

Hay **dos picos**, y conviene no confundirlos:

- **Mejor latencia + honestidad medida: 19 de mayo (`ab8ff66`).** Acciones en
  ~2.7 s, 75 % de turnos <3 s, 0 % de falsas confirmaciones. Es el pico que hay
  que recuperar en velocidad.
- **Mejor calidad/naturalidad de respuesta: 12-14 de mayo (era fundacional de
  chat).** Respuestas con personalidad, humor a pedido, honestas sobre límites —
  con un prompt liviano y pocas tools. Su talón de Aquiles era el **cold-start**
  (23-58 s el primer turno), no el por-turno (acciones ya en 2-3 s).

**No hubo una sola época con AMBAS al máximo simultáneamente**, pero el 19-may es
lo más cerca (rápido + honesto), y la calidad rica del 12-14 se perdió sobre todo
por el **engrosamiento del prompt** (más tools, más guards, más reglas) que vino
con la robustez de los días siguientes.

El resto del TL;DR describe el pico de latencia (19-may), que es el accionable para
la regresión actual:

**La época de oro de latencia es el 19 de mayo (commit `ab8ff66` y sus vecinos del
Sprint 7 de voz).** Tuvo a la vez la **mejor latencia** y la **mejor honestidad**
medidas:

- Acciones de sistema ("abre Steam", volumen…): **p50 2.7 s / p90 2.9 s** — la
  distribución más apretada de toda la historia.
- **75 % de TODOS los turnos bajo 3 s** (vs 19 % el 20 de mayo).
- Respuestas **honestas**: cuando fallaba decía *"No alcancé a completar la acción"*
  en vez de inventar un "Listo". 0 % de falsas confirmaciones de acción ese día.

Lo que la hacía así de buena (verificado en el código de `ab8ff66`):
1. **Acciones SIN reasoning** (`fast_action`, `enable_thinking=False`) → un solo
   pase de LLM corto para emitir el tool-call.
2. **Sin modo router** → un único modelo cargado, **KV-cache prefix-reuse pleno**
   entre turnos (`--cache-reuse 256`, sin el overhead de dos presets text/vision).
3. Subset de tools chico y prompt acotado.

Lo que la rompió (20 de mayo): se metió **thinking ON en acciones** (`9da4fd3`) y
**modo router de dos presets** (`3f1c278`). Subió la fiabilidad de tool-calling
pero **duplicó la latencia**: de ~2.7 s a 6-8 s.

> ⚠️ **Matiz importante de calidad:** la época de oro de *latencia* (May 19) era
> rápida en parte porque **no tenía thinking**, y eso mismo causaba el bug
> "abre steam no abre" (el modelo a veces no emitía el tool-call: 2/6). O sea, la
> velocidad del May 19 y la fiabilidad del May 20 son **el mismo trade-off visto
> desde dos lados**. La meta no es "volver al May 19", es **recuperar su latencia
> SIN perder la fiabilidad** — y eso se logra con técnicas que mantienen el
> invariante "el LLM genera todo" (ver el cierre).

---

## 1. Latencia por día (todo el historial disponible)

> **Alcance temporal.** El proyecto **Carter Agent nace el 12-may-2026**
> (commit `4748cb6`); antes era el proyecto **Carter** (`harness_carter540`), que
> el usuario descartó por malo y NO se analiza acá. No existe en esta PC ningún
> log/sesión/commit de Gemma 4 anterior al 12-may (verificado en git reflog,
> `~/.gemma4/sessions`, recordings y fechas de archivo). Así que "todo el
> historial" = **12 → 20 de mayo**. Los días **12-14** salen de los JSON de sesión
> (`~/.gemma4/sessions`, resolución 1 s, chat de texto); del **15** en adelante del
> `full.log` por-evento (resolución sub-segundo, voz).

| Día | n | mediana | p25 | p75 | % turnos <3 s | fuente |
|---|---|---|---|---|---|---|
| 2026-05-14 | 88 | 3.0 s | 2.0 | 8.0 | 49 % | session jsons |
| 2026-05-15 | 73 | 3.3 s | 1.9 | 8.1 | 44 % | full.log |
| 2026-05-16 | 67 | 2.9 s | 1.8 | 7.8 | 51 % |
| 2026-05-17 | 69 | 3.8 s | 2.3 | 6.4 | 39 % |
| 2026-05-18 | 30 | 3.8 s | 2.2 | 5.7 | 43 % |
| **2026-05-19** | **16** | **2.6 s** | **2.0** | **3.5** | **75 %** ✅ |
| 2026-05-20 | 48 | **7.4 s** | 3.4 | 14.3 | **19 %** ❌ |

Solo acciones de sistema (abre/cierra/volumen/ventana/screenshot):

| Día | n | p50 | p90 |
|---|---|---|---|
| 2026-05-15 | 27 | 3.1 s | 22.4 s |
| 2026-05-16 | 8 | 2.9 s | 4.6 s |
| 2026-05-17 | 12 | 6.3 s | 8.3 s |
| 2026-05-18 | 9 | 2.5 s | 5.6 s |
| **2026-05-19** | **5** | **2.7 s** | **2.9 s** ✅ |
| 2026-05-20 | 13 | 7.1 s | 17.3 s ❌ |

La curva de "abre Steam" a lo largo del tiempo (cada turno real):

```
May15  10.7 9.4 0.8 2.1 6.4 6.2 6.0 6.1 2.1 1.4 2.4 2.3   (warmup alto, luego 1-2.5s)
May16   2.6 2.5 4.6 3.0                                    (rápido y estable)
May17   3.3 3.2 7.2 6.1 8.0                                (empieza a subir)
May18   4.9 2.2 3.2 4.8 2.2
May19   2.9 2.9 2.7 2.0                                    ← golden: apretado en ~2.7s
May20   3.4 1.4 0.3 16.1 6.3 7.1 7.7                       ← regresión a 6-8s
```

(El 0.3-1.4 s del 20-may 16:44 es engañoso: respondió *"voy a abrir Steam"* —
futuro, sin verificar — no es una acción completada.)

---

## 2. Las épocas, una por una

### 🥇 19 de mayo — golden (latencia + honestidad) · commits Sprint 7 voz, `ab8ff66`

**Qué se medía** (turnos crudos del log):
```
23:25:35  2.9s  "hey gemma abre Steam"  → "Listo, abrí Steam."
23:32:31  2.9s  "hey gemma abre Steam"  → "Listo, abrí Steam."
23:44:19  2.7s  "hey gemma abre Steam"  → "Listo, abrí Steam."
23:46:00  2.0s  "hey gemma abre Steam"  → "No alcancé a completar la acción. ¿La repetimos?"  (honesto al fallar)
```

**Por qué era rápido y honesto** (verificado en `git show ab8ff66`):
- `modes.py`: la acción simple caía en **`fast_action`, `enable_thinking=False`**,
  `max_tokens=384`. **No existía `quick_action`** ni el reasoning en acciones.
  → el pase 1 emitía el tool-call en ~1-1.7 s, sin gastar segundos "pensando".
- `agent.py`: **0 referencias a router mode** (`grep router_model` = 0). Un único
  modelo cargado → el **KV-cache prefix-reuse** (`--cache-reuse 256`) reutilizaba el
  prefijo del system prompt entre turnos. Sin overhead de resolver preset por turno.
- Guards de honestidad ya activos: el fallback *"No alcancé a completar la acción"*
  reemplazaba falsas confirmaciones. Por eso ese día hay 0 % de "Listo" mentiroso.

**El costo oculto:** sin thinking, el tool-calling NO era 100 % fiable. El mismo log
muestra `23:46:00 "abre Steam" → "No alcancé"` (el modelo no emitió el tool-call).
Medido luego en `9da4fd3`: `enable_thinking=False` daba **2/6** tool-calls a través
del agente completo. La velocidad del May 19 venía, en parte, de esta fragilidad.

---

### 🥈 16 de mayo — buena latencia de acciones, calidad MIXTA · `aa99458`..`6bd2bde`

- Acciones de sistema **p50 2.9 s / p90 4.6 s** — segunda mejor.
- "abre steam" en 2.5-2.6 s, "Steam se ha abierto." / "Listo, abrí Steam."
- **Pero la calidad era inconsistente en streaming** (Netflix/Disney+):
  ```
  16:01  23.0s  "pon loki en disney"    → "Listo, intenté reproducir Loki…"   (lento)
  16:02  21.5s  "daredevil born again"  → "Listo, estoy viendo Daredevil…"    ← FALSA confirmación
  11:43   9.2s  "Hola"                  → "Guardé tu perfil de HBO Max como 'Hola'"  ← trató saludo como perfil
  ```
- O sea: **rápido para acciones locales, pero alucinaba/mentía en flujos de
  streaming** y confundía smalltalk con datos. No es oro de calidad.

Mismo motor base que May 19 (sin thinking en acciones, sin router) → de ahí la
latencia parecida en acciones simples. La diferencia de calidad vino de fixes de
routing/pending-intent que llegaron *después* (May 19-20).

---

### 12-14 de mayo — era fundacional (texto/chat) · `4748cb6`..`3f77637`

Los primeros días de Carter Agent, sobre todo **chat de texto** (la GUI PyQt6 y el
runtime de voz aún se estaban armando; el wake/STT redesign llega recién el 19).
Datos de los JSON de sesión (resolución 1 s):

```
05-14 20:14  2s  "Abre steam"               → "Steam se ha abierto. ¿Qué te gustaría hacer…"
05-14 20:14  3s  "Pon el volumen del pc a 10"→ "El volumen del PC ha sido ajustado al 10."
05-14 20:15  3s  "cierra whatsapp"          → "WhatsApp ha sido cerrado correctamente."
05-14 21:06  1s  "El agua es h2o?"          → "Sí, la fórmula química del agua es H₂O."
05-14 21:08  0s  "El agua moja? con humor"  → "¿Qué hace el agua en el gimnasio? ¡Nada! 😂"
```

**Calidad de respuesta: excelente y con personalidad** — natural, honesta sobre sus
límites ("Como modelo… no puedo enviar mensajes" cuando esa tool aún no existía),
con humor cuando se lo pedían. Acciones simples ya en **2-3 s** una vez warm.

**El gran problema de esta era era el cold-start**, no el por-turno:
```
05-14 19:40  58s  "hOLA?"   → "Sí, estoy aquí…"
05-14 21:03  40s  "Hola"    → "¡Hola!…"
05-14 20:13  26s  "hola"    → "¡Hola!…"
```
El primer turno tras arrancar pagaba 23-58 s (carga de modelo + warmup KV). Esto se
atacó después (`9614770 perf(boot): warm … kill the 14s cold start`).

Por qué las acciones simples eran rápidas: mismo motor sin thinking (igual que May
19), modelo único, sin router. La calidad venía de un prompt todavía liviano y de
que el set de tools era chico (42→61 tools se agregaron justo en estos días).

---

### 15 de mayo — fundacional, latencia bimodal · `5730937`..`e70c09b`

- Acciones simples ya en **0.8-2.5 s una vez warm** (el mismo
  `gemma-4-E4B-it-Q4_K_M.gguf`, ctx 16384, sin thinking, sin router).
- **Pero p90 22.4 s**: los primeros turnos pagaban cold-start (10.7 s, 9.4 s) y los
  flujos de streaming se iban a decenas de segundos.
- Confirma que **el modelo nunca fue el problema** — es el mismo GGUF que hoy.

---

### 17-18 de mayo — degradación gradual · hotfix-day

- p50 sube a 3.8-6.3 s. Coincide con el "hotfix day" (6 bugs en una sesión: wake FP,
  VAD reject, Spotify race, "Listo" overuse, WhatsApp slot-filling). Se ganó
  robustez/calidad a costa de prompt más pesado y más verificación.

---

### ❌ 20 de mayo — la regresión · `9da4fd3` + `3f1c278`

- p50 **7.4 s**, solo 19 % de turnos <3 s, "abre Steam" en 6-8 s.
- **Dos causas raíz, ambas del 20-may, ambas trade-offs deliberados:**

  1. **`9da4fd3` (17:45) "enable reasoning for action commands"** — metió
     `quick_action` con `enable_thinking=True` para acciones simples. El propio
     commit lo justifica midiendo fiabilidad:
     ```
     full agent prompt, enable_thinking=False:  2/6 tool-calls  ← "abre steam no abre"
     full agent prompt, enable_thinking=True:   6/6 tool-calls  ← fiable
     costo estimado en el commit: "~+1s (0.8s -> 1.7s), dentro del budget"
     ```
     **La estimación falló en producción:** los stamps reales muestran el pase 1 con
     thinking costando **2-4 s**, no +1 s. (Medido hoy: "pon el volumen al 30" pase 1
     = 3.93 s.)

  2. **`3f1c278` (19:20) "lazy-vision via llama.cpp router mode"** — dos presets por
     perfil (`-text` / `-vision`) y resolución de modelo por request. Cambió cómo se
     sirve el modelo; hipótesis (a confirmar): el cambio de preset y/o el mmproj del
     preset vision **degradan el prefix-reuse del KV cache** que el May 19 disfrutaba
     pleno.

- **El doble pase de LLM** (pase 1 decide tool + pase 2 dice "Listo") existió siempre,
  pero con thinking ON el pase 1 pasó de ~1.5 s a 2-4 s, y el total a 6-8 s. Medido:
  ```
  'pon el volumen al 30' total=6.6s  → pase1(thinking) 3.93s + tool 0.08s + pase2 2.51s
  'abre steam'           total=4.5s  → pase1 2.00s + tool 0.56s + pase2 1.89s
  ```

---

## 3. La tabla maestra: qué tenía cada época

| Dimensión | May 19 (oro) | May 20 (hoy) |
|---|---|---|
| Modo de acción simple | `fast_action` | `quick_action` |
| `enable_thinking` en acción | **OFF** | **ON** (budget 384) |
| Pase 1 (decidir tool) | ~1-1.7 s | 2-4 s |
| Pase 2 (resumen "Listo") | ~1.5 s | 1.9-2.5 s |
| Servir modelo | 1 modelo, cache-reuse pleno | router 2 presets, reuse dudoso |
| Resolución de modelo/turn | ninguna | GET /v1/models (cacheado 30 s) |
| Fiabilidad tool-call | **2/6** ⚠️ | **6/6** ✅ |
| Honestidad (fallback al fallar) | ✅ | ✅ |
| Falsas confirmaciones | 0 % | ~4 % |
| **Latencia acción p50** | **2.7 s** ✅ | **7.1 s** ❌ |
| Modelo GGUF | `E4B-it-Q4_K_M` | `E4B-it-UD-Q4_K_XL` (vram8) |

El modelo cambió de quant entre épocas (Q4_K_M → UD-Q4_K_XL en vram8), pero **el
May 15 ya corría Q4_K_M rápido**, así que la quant no es la causa de la regresión;
las dos causas son thinking-ON y router-mode.

---

## 4. Qué hacía que "funcionara perfecto" — síntesis

La combinación ideal, sacada de la evidencia, sería:

1. **Latencia tipo May 19**: un solo pase corto para decidir el tool, sin gastar 2-4 s
   en reasoning; KV-cache prefix-reuse pleno (modelo único o router que no rompa el
   reuse); subset de tools chico.
2. **Fiabilidad tipo May 20**: tool-calling 6/6, no 2/6.
3. **Honestidad de siempre**: el guard que reemplaza falsas confirmaciones por un
   fallback honesto — presente en ambas épocas, **mantenerlo**.

El conflicto es (1)↔(2): el May 19 era rápido porque NO pensaba, y por eso fallaba
tool-calls; el May 20 es fiable porque piensa, y por eso es lento. **Recuperar la
edad de oro = romper ese trade-off**, no elegir un lado.

### Caminos para romper el trade-off (sin volver atrás en fiabilidad ni en honestidad)

> Invariante de producto: **todo texto que el usuario escucha lo genera el LLM**
> (nada de plantillas). Las opciones de abajo lo respetan. Ver
> `docs/architecture/latency_research_prompt.md` para el detalle a investigar.

- **Tool-calling fiable SIN thinking**: `tool_choice=required` + grammar/constrained
  decoding podría dar 6/6 sin el costo de 2-4 s del reasoning. Si funciona, recupera
  la latencia del May 19 con la fiabilidad del May 20. *(la hipótesis más prometedora)*
- **Thinking adaptativo**: reasoning ON solo cuando el subset de tools es ambiguo;
  OFF cuando es chico y obvio (1 tool claro como "abre steam").
- **Pase 2 más barato sin templatizar**: streaming token→TTS (empezar a hablar al
  primer token), o un modelo más chico SOLO para el resumen, o menos contexto al
  pase 2. El LLM sigue generando cada palabra.
- **Confirmar/recuperar el prefix-reuse en router mode**: medir si el cambio de
  preset rompe el cache-reuse que el May 19 tenía pleno; si lo rompe, mitigarlo.
- **Recortar el end-of-speech**: ortogonal a lo anterior pero suma — el silence
  window y el STT batch agregan dead-time percibido en cada turno.

---

## 5. Anti-patrón explícitamente descartado

El short-circuit del pase 2 por **plantilla** (`_maybe_template_summary` /
`_pending_template_reply`, explorado el 20-may) bajaba "abre steam" a 2.7 s **pero
reemplazaba el texto del LLM por un f-string** → viola el invariante de producto
"todo lo que el usuario oye lo genera el LLM". **Se descarta y se revierte.** La
edad de oro hay que recuperarla con generación real, no con texto enlatado.

---

## Apéndice — cómo se sacaron estos números

- Fuente: `~/.gemma4/logs/_pre_session/full.log` (6635 líneas, 6421 con timestamp,
  rango 2026-05-15T11:47 → 2026-05-20T21:55). Eventos `type=activity` con
  `entry.src ∈ {YOU, CONTEXT, TOOL, GEMMA}`.
- Latencia de turno = `ts(GEMMA) − ts(YOU)` del primer GEMMA tras cada YOU
  (incluye espera de fin-de-habla + STT + LLM×2 + tool + TTS-start).
- Calidad: % de turnos con fallback honesto, % con pregunta de aclaración, % de
  falsas confirmaciones (afirma acción con 0 tools ejecutados), nº de tools ofrecidas
  (solo loggeado desde `ab8ff66`, 19-may).
- Commits: `git log --all --date=format` cruzado por fecha/hora con cada ventana;
  inspección del código histórico con `git show <sha>:<archivo>`.
- Desglose por etapa (pase 1 / tool / pase 2): stamps en vivo medidos hoy contra el
  servidor vram8 + `gemma4_agent/data/traces.jsonl`.
