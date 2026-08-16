# Análisis: Skills, Microagents y Subagents — ¿están bien aplicados?

> Pregunta del usuario (2026-05-30): "siento que no hacen nada". Este informe
> determina, con evidencia MEDIDA sobre 117.764 eventos reales de los logs, si
> los tres sistemas están bien aplicados, qué dice el research, cómo lo hace la
> competencia, y si estamos a su nivel.

---

## 0. TL;DR (la respuesta directa)

Tu intuición es **parcialmente correcta**. La mitad del sistema está **muerta**,
la otra mitad **funciona pero es invisible**.

| Componente | Estado | Evidencia (117.764 eventos reales) |
|------------|--------|-------------------------------------|
| `skill_load` (el 4B carga skills) | ❌ **MUERTO** | **1** invocación en toda la historia |
| `subagent` (delegación a child agent) | ❌ **INERTE** | **0** invocaciones. Nunca. |
| Skills vía **auto-inject** | ✅ **VIVO** | **41** inyecciones reales, 6 skills distintas |
| `purchase-guard` (skill critical) | ✅ **VIVO** | se inyecta siempre (regla de seguridad) |
| Microagents (glossary, troubleshoot…) | ✅ **VIVO** | trigger-based, ligeros, correctos para voz |

**Causa de "no hacen nada":** la parte que el modelo debe DECIDIR usar
(`skill_load`, `subagent`) está muerta porque el 4B (modelo chico) no hace
meta-pasos. La parte que funciona (auto-inject + microagents) es **determinista
y por detrás**, así que no se nota.

**¿Estamos al nivel de la competencia?** En el patrón correcto para un modelo
chico, **SÍ y en algunos aspectos por delante**. Pero hay deuda concreta:
`subagent` debería borrarse o reconvertirse, y `skill_load` debería sacarse del
menú del 4B. Detalle abajo.

---

## 1. Qué hay implementado (los tres sistemas)

### 1.1 Skills (recetas markdown estilo Anthropic Agent Skills)
- **10 skills** en `gemma4_agent/skills/*/SKILL.md`: purchase-guard (critical),
  install-steam-game, safe-file-cleanup, backup-then-clean, research-and-summarize,
  screenshot-and-analyze, debug-app-crash, schedule-recurring-task,
  voice-record-transcribe, new-development-project.
- **Dos vías de activación:**
  - `skill_load(name)` — el LLM la pide. Lazy. **El camino muerto.**
  - **Auto-inject** (`autoinject_skill()`, 2026-05-29) — si el texto del usuario
    matchea por embedding (umbral 0.45) una skill, se inyecta su receta full al
    prompt automáticamente. **El camino vivo.**
  - `priority: critical` — eager, inyectada siempre (solo purchase-guard).
- Gates: `GEMMA4_SKILLS_OFF` (kill total), `GEMMA4_SKILLS_AUTOINJECT` (default ON).
- Cap por profile: vram4 = 3 skills/turno.

### 1.2 Microagents (inyección de conocimiento condicional)
- **4 microagents** en `gemma4_agent/microagents/*.md`: glossary, tools_cheat_sheet,
  troubleshoot, windows_commands.
- Markdown con frontmatter `triggers: [...]`. Si una keyword aparece en el primer
  mensaje del turno → se inyecta el body (~2 KB) al system prompt.
- **Esto es lo que mejor funciona** — ligero, condicional, correcto para voz.

### 1.3 Subagents (delegar a un child agent fresco)
- `gemma4_agent/tools_pkg/subagent.py`: la tool `subagent(action="run", task=...)`
  arranca una instancia fresca de `Gemma4Agent` con historia vacía, tools
  filtradas, `max_turns` acotado. Síncrono.
- Bien diseñado, bien testeado (contrato), **nunca invocado por el 4B**.

---

## 2. La evidencia dura (logs reales, no intuición)

Medido sobre `gemma4_agent/data/traces.jsonl` — **117.764 eventos**:

```
tool_call skill_load: 1          ← el 4B casi nunca carga una skill
tool_call subagent:   0          ← el 4B NUNCA delega
skill_autoinjected:   41         ← el auto-inject SÍ dispara
```

Skills auto-inyectadas (las 41):
```
20  screenshot-and-analyze     7  backup-then-clean
 6  research-and-summarize     3  voice-record-transcribe
 2  debug-app-crash            2  schedule-recurring-task
```

**Conclusión medida:** El 4B (E2B-FT) **no hace meta-pasos** — no "carga una
herramienta para después seguirla" ni "delega a otro agente". Eso es esperable:
es un modelo chico optimizado para acción directa, no para orquestación
reflexiva. El proyecto YA lo descubrió (Sprint 2.1: "0 skill_load en 6727
eventos") y reaccionó bien con el auto-inject. Pero dejó `skill_load` y
`subagent` en el menú, donde solo agregan ruido.

---

## 3. Qué dice el research (interno)

Los informes en `gemma4_agent/docs/research/investigaciones_recibidas/` son
claros sobre cómo un 4B local debe usar estos sistemas:

1. **`0_arquitectura_general.md`**: el patrón ganador para un 4B NO es delegar a
   subagentes, es el **"microagente de continuación"** — auto-ejecutar el
   next-action determinista (ej: search devuelve 1 hit → abrir sin re-llamar al
   LLM). Ahorra ~1.5–2 s. (Esto es exactamente la filosofía del auto-inject.)

2. **`4_contexto.md`**: para voz, los microagents deben inyectarse
   **condicionalmente según el texto del usuario** (no por turno anterior).
   Es lo que el sistema hace. ✅

3. **`11_plan_computer_use_windows_4b.md`**: para GUI, NO usar skills como
   recetas del LLM (rompe el presupuesto de latencia) — usar **macros
   deterministas** que hacen observe→act→verify internamente. El proyecto YA
   migró a esto (click_button, etc.).

**Veredicto del research:** un 4B debe operar por **inyección determinista**
(auto-inject, microagents, macros), NO por **decisión reflexiva del LLM**
(skill_load, subagent). El proyecto está alineado con su propio research en la
parte viva; la parte muerta contradice el research (espera que el 4B decida).

---

## 4. Cómo lo hace la competencia (8 proyectos analizados)

Carpeta: `Carter OS AI\Extras\Competidores`.

### 4.1 Skills

| Proyecto | Qué es una skill | Activación | Self-improve |
|----------|------------------|-----------|--------------|
| **OS-Copilot / FRIDAY** | **Código Python generado** | retrieval vectorial (Chroma) | ✅ genera→ejecuta→juzga→repara→guarda |
| **goose (Block)** | Markdown + sub-recipes | `load_skill()` (el LLM la pide) | manual / CI |
| **open-interpreter** | Python guardado en `~/.config` | lazy-load + implícito | colaborativo en conversación |
| **OpenHands** | Markdown + triggers | keywords (`/codereview`) | manual (27 de fábrica) |
| **Mark-XXXIX** (Jarvis-like) | Funciones Python | siempre disponibles (sin triggers) | — |
| **Gemma 4 (nosotros)** | Markdown receta | **auto-inject por embedding** + skill_load | manual |

**Observación clave:** TODOS los que dependen de que el LLM PIDA la skill
(goose `load_skill`, OpenHands `/triggers`, nuestro `skill_load`) **asumen un
modelo grande capaz de meta-pasos**. Con un 4B eso no funciona — y nosotros lo
medimos. Nuestro **auto-inject por embeddings es MÁS robusto para modelo chico**
que el `load_skill` de goose o el `/trigger` de OpenHands: no depende de que el
LLM decida, dispara solo.

OS-Copilot/FRIDAY es el más avanzado (self-learning de skills como código), pero
asume un modelo grande + presupuesto de latencia laxo (no es tier-Alexa). No es
el target de un asistente de voz local de 4-5 s.

### 4.2 Subagents / multi-agent

| Proyecto | Quién decide delegar | Overhead |
|----------|---------------------|----------|
| **AutoGen** | el LLM (vía prompt selector) o handoff | llamada LLM por decisión |
| **LangGraph** | **determinístico** (routing del grafo) | ~0 (lógica local) |
| **OpenHands** | single-agent en esta rama | — |
| **Gemma 4 (nosotros)** | el 4B (que nunca lo hace) | — (inerte) |

**Observación clave:** AutoGen delega vía LLM = caro. LangGraph delega
**determinísticamente** = el patrón correcto para modelo chico. Nuestro
`subagent` copia el modelo de AutoGen (el LLM decide) — y por eso está muerto:
el 4B nunca decide delegar. Si quisiéramos subagents reales, el disparo debería
ser **determinista** (como LangGraph), no del 4B.

---

## 5. ¿Estamos al nivel de la competencia?

**En el patrón correcto para un modelo chico: SÍ, y en partes por delante.**

✅ **Donde estamos bien o adelante:**
- **Auto-inject por embeddings** > `load_skill`/`/trigger` de la competencia para
  modelo chico (no depende de que el LLM decida; multilingüe; fallback seguro).
- **Microagents trigger-based** = igual de buenos que OpenHands, correctos para voz.
- **Macros deterministas para GUI** (no recetas) = alineado con el research, mejor
  que cargar recetas al LLM en cada paso.
- **purchase-guard como skill critical eager** = guardia de seguridad sólida.

⚠️ **Donde estamos peor / con deuda:**
- **Sin self-learning de skills** (OS-Copilot/FRIDAY sí: aprende skills como
  código, las verifica y las guarda). Nosotros tenemos skills estáticas escritas
  a mano. *Pero:* el self-learning de FRIDAY asume modelo grande + latencia laxa;
  no es obvio que valga para voz tier-Alexa. Es una mejora opcional, no una
  carencia crítica.
- **`subagent` muerto en el menú** — copia el patrón AutoGen (LLM decide) que no
  funciona con 4B. Deuda: borrarlo o reconvertirlo a disparo determinista.
- **`skill_load` en el menú del 4B** — gasta tokens del prompt en una tool que el
  4B no usa (1/117.764). Deuda: sacarlo del menú visible al 4B.

---

## 6. Recomendaciones (qué hacer)

Ordenadas por valor/riesgo. Cada una es MEDIBLE.

### R1 — Sacar `skill_load` del menú visible al 4B (alto valor, bajo riesgo)
El 4B no lo usa (1/117.764). Su descripción ocupa tokens del prompt en CADA
turno. El auto-inject ya cubre el caso de uso. **Acción:** mantener la tool en el
dispatcher (por si un modelo futuro la usa) pero NO listarla en el menú
`# SKILLS AVAILABLE` ni en el subset del router. **Medir:** tokens de prompt
ahorrados + 0 regresión en que las skills sigan disparando vía auto-inject.

### R2 — Decidir el destino de `subagent` (medio valor, bajo riesgo)
0 invocaciones en la historia. Dos opciones:
- **(a) Borrarlo** del menú/schema (mantener el código por si sirve después).
  Es la opción honesta: una feature que nunca se usa es ruido.
- **(b) Reconvertirlo a disparo DETERMINISTA** (estilo LangGraph): el agente
  delega a un child SOLO cuando una condición programática se cumple (ej: una
  misión larga con un sub-paso claramente acotado, detectado por reglas
  estructurales — no por el 4B). Esto lo volvería útil sin depender del 4B.
- **Recomendación:** (a) ahora (sacarlo del menú del 4B, gastar 0 tokens), y
  dejar (b) documentado como sprint futuro si aparece un caso real de misión
  larga que lo justifique.

### R3 — Más skills auto-inject de alto valor (medio valor, medio riesgo)
El auto-inject funciona (41 disparos, 6 skills). Vale la pena cubrir más
intenciones frecuentes de los logs con skills nuevas (ej: las que aparecen mucho
en `traces.jsonl` y se beneficiarían de una receta multi-tool). **Medir:** tasa
de auto-inject correcto en vivo (gate: ≥ el 0-falsos-positivos actual).

### R4 — (Opcional, futuro) Self-learning de skills estilo FRIDAY
Solo si se justifica: aprender una macro verificada por misión y guardarla como
skill reutilizable. El `mission_goal` verifier ya es el gate natural. Es un
sprint grande; el research lo menciona pero NO es prioritario para voz.

### NO hacer
- NO esperar que el 4B "decida" cargar skills o delegar — está medido que no lo
  hace. Todo debe ser inyección determinista.
- NO meter subagents en el loop de voz (cada uno es un prefill nuevo, rompe el
  presupuesto tier-Alexa de 4-5 s).

---

## 7. Resumen para el usuario

- **Tu sensación de que "no hacen nada" es cierta para `skill_load` y
  `subagent`** — están muertos (1 y 0 usos en 117.764 eventos). Para `subagent`,
  es 100% correcto: nunca hizo nada.
- **Pero las skills SÍ funcionan** por una vía que no ves: el auto-inject (41
  disparos reales). Cuando pedís "saca una captura y decime qué ves", se inyecta
  la receta `screenshot-and-analyze` sola, sin que el 4B la pida.
- **Los microagents también funcionan** (glosario, troubleshooting) — ligeros y
  por trigger.
- **Estamos al nivel de la competencia** en el patrón correcto para modelo chico
  (auto-inject por embeddings es incluso más robusto que el `load_skill` de goose
  o los triggers de OpenHands). Nos falta el self-learning de FRIDAY, pero eso
  asume un modelo grande.
- **La deuda concreta:** sacar `skill_load` y `subagent` del menú del 4B (gastan
  tokens sin usarse). Eso es lo que hace que "sientas" que no sirven — están a la
  vista pero inertes.

---

## Fuentes (archivos verificados esta sesión)

- `gemma4_agent/tools_pkg/skills_registry.py` (auto-inject, scan, menú)
- `gemma4_agent/tools_pkg/subagent.py` (la tool inerte)
- `gemma4_agent/agent_core/agent.py` (wiring, trigger-inject, telemetría)
- `gemma4_agent/data/traces.jsonl` (117.764 eventos: 1 skill_load, 0 subagent, 41 autoinject)
- `gemma4_agent/skills/` (10 skills), `gemma4_agent/microagents/` (4 microagents)
- `gemma4_agent/docs/research/investigaciones_recibidas/{0,4,11}_*.md` (research interno)
- Competidores: OS-Copilot, goose, open-interpreter, OpenHands, Mark-XXXIX,
  AutoGen, LangGraph (`Carter OS AI\Extras\Competidores`)
