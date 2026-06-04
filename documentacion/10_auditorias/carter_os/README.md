# Auditoría profunda — Carter OS AI vs Baxy (este proyecto, antes Gemma 4 Agent, brevemente Carter)

> Nota de nomenclatura: **"Carter OS AI" / "Carter v1..v5" / `carter_v5/`** son el
> **proyecto de referencia externo** que se audita acá — NO cambian de nombre. "Baxy"
> es **este** proyecto (el asistente propio), que antes se llamó "Gemma 4 Agent" y
> brevemente "Carter". Donde el texto diga "Carter Agent" / "este proyecto" /
> "nosotros", se refiere a **Baxy**.

**Fecha:** 2026-05-23
**Pedido por:** RED — "audita ambas carpetas de investigaciones + TODO el proyecto
Carter OS AI (≥6 versiones, cada una mejor que la otra); algo de ahí nos sirve.
Dejá el resultado en una carpeta aparte en docs."

**Alcance auditado:**
- `gemma4_agent/docs/research/` (este proyecto — ya minado, base de los commits recientes).
- `Carter OS AI/docs/investigaciones/` (57 .md: opus dossiers, patterns A-P, GUI, audio, "la razón de carter").
- `Carter OS AI/` **proyecto completo**: `legacy/Carter_v1..v4`, `carter_v5/` (actual),
  `legacy/Mark-XXXIX-main`, `legacy/Referencia OpenClaw`, docs de evolución
  (`11_lecciones_v1_a_v4.md`, `REEVALUACION_CARTER_V4`, `MIGRATION_PLAN_GEMMA4`).

---

## TL;DR — el hallazgo que cambia todo

**Carter v5 NO es "otro proyecto con otro modelo".** Es una re-arquitectura del
MISMO asistente sobre el MISMO stack que nosotros: Gemma 4 E4B-it + llama.cpp
b9090 `--jinja`, multi-perfil por VRAM, mmproj-F16, sampling oficial Google,
verificadores estructurales. Su propio README cita **"the validated harness
`Probando Gemma 4` (540/540 PASS)"** como ground-truth — ese harness es ESTE
proyecto. Carter v5 es nuestro primo modular.

Consecuencia: **el código de v5 es directamente transferible** (no aplica el
caveat "es Qwen3/Ollama" — eso era v1-v3). Y el documento `11_lecciones_v1_a_v4.md`
es **la lista de anti-patrones ya pagados** por 4 generaciones del mismo asistente
— oro puro para no repetirlos.

Tres categorías de resultado:
1. **Carter VALIDA lo que ya hacemos** (refuerza decisiones nuestras).
2. **Anti-patrones que Carter pagó caro** — verificar que NO los tenemos.
3. **Features concretas que v5 tiene y nosotros no** — candidatos priorizados.

Ver detalle en:
- [`01_lo_que_valida.md`](01_lo_que_valida.md) — 13 decisiones nuestras que Carter confirma.
- [`02_antipatrones_a_revisar.md`](02_antipatrones_a_revisar.md) — errores que Carter pagó; verificados contra nuestro código.
- [`03_features_candidatas.md`](03_features_candidatas.md) — features de v5 que no tenemos (primer pase, alto nivel).
- [`04_de_las_investigaciones.md`](04_de_las_investigaciones.md) — cruce de los 57 .md de investigación.
- **[`05_analisis_profundo_codigo.md`](05_analisis_profundo_codigo.md)** — ⭐ lectura módulo-por-módulo del CÓDIGO real (core/mission/verify/loop/memory/safety/tools de v5 + lo perdido en v3/v4 + OpenClaw). 84+ técnicas con archivo:línea y umbrales.
- **[`06_matriz_gaps_verificada.md`](06_matriz_gaps_verificada.md)** — ⭐ 23 hallazgos cruzados por grep contra NUESTRO código (✅/⚠️/❌/🚫) + top accionables re-priorizados.

> **05 y 06 son el análisis profundo** pedido (lectura del código real de todo
> Carter, no solo docs). 01-04 fueron el primer pase de alto nivel.

---

## Mapa del proyecto Carter OS AI (lo que se auditó)

| Versión | Modelo | Estado final (según `11_lecciones`) |
|---|---|---|
| v1 | qwen3:14b → qwen3:4b | Audit reveló 61% PASS real (vs 85% "bench bonito"). Rebuild. |
| v2 | qwen3:8b in-process | 1454 tests verdes pero respuestas malas en uso real. |
| v3 | qwen3:4b-2507 | Stage A-E → 524/540 (97%). Acumuló heurísticas post-LLM. |
| v4 | **gemma-4-E4B-Q6_K (llama-server b9090)** | Migró a NUESTRO stack. Calidad real "pobre" por debt heredado. |
| **v5** ⭐ | **gemma-4 E4B/26B-A4B por tier** | Re-arquitectura LIMPIA y modular. La que nos sirve. |

Carpetas de referencia externa dentro de Carter:
- `Mark-XXXIX-main` — patrón de error-recovery (clasificador externo de errores).
- `Referencia OpenClaw` (openclaw-main) — origen de `active_recall` (recall pre-turno).

### Estructura modular de carter_v5 (≈22k LOC, 113 archivos)

```
core/        agent_base, router, execution, context_builder, durable_state, workspace
mission/     goal.py (MissionGoal verifier Voyager), outcomes, verifier
verify/      core.py (verificadores estructurales por-tool: pycaw, EnumWindows, frame_diff)
loop/        detection.py (v2 result-aware + 5º patrón no_progress)
memory/      store.py (SQLite + e5-small), active_recall.py (recall pre-turno), wiki.py
skills/      registry.py (Anthropic Agent Skills, SKILL.md)
microagents/ loader.py
safety/      confirm.py + policy.py (destructivo multilingüe por Snowball stems)
multimodal/  whisper STT + image_url base64
hardware/    VRAM detection + tier selector
profiles/    una carpeta por tier (6/8/10/12/16 GB): agent/prompt/config/tools_subset
observability/ tracing jsonl por turno
adapters/    llamacpp (OpenAI-compat)
```

**Lo notable:** v5 separó lo que en nuestro proyecto vive concentrado en
`agent.py` (≈3.2k LOC). Su lección L9: "agent.py < 500 LOC, módulos < 300".
No es mandato para nosotros (Inv 0/T5 ya dijo: no refactorizar si el sistema se
estabiliza), pero su separación facilita ver QUÉ pieza hace qué.

---

## Disclaimer de honestidad

- Carter v5 **nunca terminó su bench 540** (se abortó por decisión humana en v4;
  v5 es scaffolding + módulos, no un sistema con número de PASS publicado). Sus
  módulos están bien diseñados pero **no todos validados end-to-end**. Tomar las
  IDEAS, medir nosotros.
- Varias cifras de Carter vienen de SU matriz de bench, no de la nuestra. No son
  trasladables como número, sí como dirección.
- Lo que SÍ está validado 540/540 es el harness `Probando Gemma 4` = nosotros.
